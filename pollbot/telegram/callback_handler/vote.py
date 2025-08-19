"""Callback functions needed during creation of a Poll."""
import logging
from typing import Optional
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import NoResultFound, ObjectDeletedError, StaleDataError
from sqlalchemy.orm.scoping import scoped_session

from pollbot.display.poll.compilation import get_poll_text_and_vote_keyboard
from pollbot.enums import CallbackResult, PollType
from pollbot.helper.stats import increase_stat
from pollbot.i18n import i18n
from pollbot.models import Vote
from pollbot.models.option import Option
from pollbot.models.poll import Poll
from pollbot.poll.helper import poll_allows_cumulative_votes
from pollbot.poll.update import update_poll_messages
from pollbot.telegram.callback_handler.context import CallbackContext

logger = logging.getLogger(__name__)


async def handle_vote(
    session: scoped_session, context: CallbackContext
) -> Optional[str]:
    """Handle any clicks on vote buttons."""
    # Extract option from callback data
    # Callback data format: vote_type:option_id:additional_param
    option_id = int(context.payload)  # This is the option ID from the callback data
    option = session.query(Option).get(option_id)

    # Remove the poll, in case it got deleted
    if option is None:
        message = i18n.t("deleted.polls", locale=context.user.locale)
        if context.query and context.query.message:
            await context.query.message.edit_text(message)
        elif context.query:
            await context.bot.edit_message_text(
                message,
                inline_message_id=context.query.inline_message_id,
            )
        return message

    poll = option.poll
    update_poll = False

    # Log the vote attempt
    logger.info(
        "Vote attempt - Poll ID: %s, Option: '%s', User: %s (@%s), Poll Type: %s",
        poll.id,
        option.name,
        context.user.id,
        context.user.username or "no_username",
        poll.poll_type,
    )

    try:
        # Single vote
        if poll.poll_type == PollType.single_vote.name:
            update_poll = handle_single_vote(session, context, option)
        # Block vote
        elif poll.poll_type == PollType.block_vote.name:
            update_poll = handle_block_vote(session, context, option)
        # Limited vote
        elif poll.poll_type == PollType.limited_vote.name:
            update_poll = handle_limited_vote(session, context, option)
        # Cumulative vote
        elif poll.poll_type == PollType.cumulative_vote.name:
            update_poll = handle_cumulative_vote(session, context, option)
        else:
            raise ValueError(f"Unknown poll type {poll.poll_type}")

        if update_poll:
            # Log successful vote
            logger.info(
                "Vote successful - Poll ID: %s, Option: '%s', User: %s (@%s)",
                poll.id,
                option.name,
                context.user.id,
                context.user.username or "no_username",
            )

            # Update all poll messages (synchronous function, don't await)
            update_poll_messages(session, context.bot, poll)

            # Show updated poll results to the user immediately
            text, keyboard = get_poll_text_and_vote_keyboard(session, poll, context.user)
            await context.query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return None

        return i18n.t("callback.vote.unchanged", locale=context.user.locale)

    except (IntegrityError, StaleDataError, ObjectDeletedError, NoResultFound) as e:
        logger.error(
            f"Error during vote: {str(e)} - Poll: {poll.id}, User: {context.user.id}"
        )
        session.rollback()
        return i18n.t("callback.vote.error", locale=context.user.locale)


def respond_to_vote(
    session: scoped_session,
    line: str,
    context: CallbackContext,
    poll: Poll,
    remaining_votes: Optional[int] = None,
    limited: bool = False,
) -> None:
    """Get the formatted response for a user."""
    locale = poll.locale
    votes = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.poll == poll)
        .all()
    )

    if limited:
        line += i18n.t("callback.vote.votes_left", locale=locale, count=remaining_votes)

    lines = [line]
    lines.append(i18n.t("callback.vote.your_votes", locale=locale))
    for vote in votes:
        if poll_allows_cumulative_votes(poll):
            lines.append(f" {vote.option.name} ({vote.vote_count}), ")
        else:
            lines.append(f" {vote.option.name}")

    message = "".join(lines)

    # Inline query responses cannot be longer than 200 characters
    # Restrict it, since we get an MessageTooLong error otherwise
    if len(message) > 190:
        message = message[0:190]

    context.query.answer(message)


def handle_single_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a single vote."""
    existing_vote = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.poll == option.poll)
        .first()
    )

    # Changed vote
    if existing_vote and existing_vote.option != option:
        existing_vote.option = option
        return True

    # Already voted for this option
    elif existing_vote and existing_vote.option == option:
        return False

    # First vote
    new_vote = Vote(context.user, option)
    session.add(new_vote)
    return True


def handle_block_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a block vote."""
    existing_vote = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.option == option)
        .first()
    )

    if existing_vote:
        session.delete(existing_vote)
        return True

    new_vote = Vote(context.user, option)
    session.add(new_vote)
    return True


def handle_limited_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a limited vote."""
    existing_vote = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.option == option)
        .first()
    )

    if existing_vote:
        session.delete(existing_vote)
        return True

    vote_count = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.poll == option.poll)
        .count()
    )

    if vote_count >= option.poll.number_of_votes:
        return False

    new_vote = Vote(context.user, option)
    session.add(new_vote)
    return True


def handle_cumulative_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a cumulative vote."""
    if not poll_allows_cumulative_votes(session, context.user, option.poll):
        return False

    new_vote = Vote(context.user, option)
    session.add(new_vote)
    return True


def handle_doodle_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a doodle vote."""
    locale = option.poll.locale
    vote = (
        session.query(Vote)
        .filter(Vote.option == option)
        .filter(Vote.user == context.user)
        .one_or_none()
    )

    if context.callback_result is None:
        raise Exception("Unknown callback result")

    # Remove vote
    if vote is not None:
        vote.type = context.callback_result.name
        changed = i18n.t(
            "callback.vote.doodle_changed", locale=locale, vote_type=vote.type
        )
        context.query.answer(changed)

    # Add vote
    else:
        vote = Vote(context.user, option)
        vote.type = context.callback_result.name
        session.add(vote)
        registered = i18n.t(
            "callback.vote.doodle_registered", locale=locale, vote_type=vote.type
        )
        context.query.answer(registered)

    return True


def handle_priority_vote(
    session: scoped_session, context: CallbackContext, option: Option
) -> bool:
    """Handle a priority vote"""
    vote = (
        session.query(Vote)
        .filter(Vote.option == option)
        .filter(Vote.user == context.user)
        .one()
    )

    previous_priority = vote.priority
    # allow next vote to take this vote's place
    vote.priority = -1

    if context.callback_result is None:
        raise Exception("Unknown callback result")

    if context.callback_result.name == CallbackResult.increase_priority.name:
        direction = -1
    else:
        direction = 1

    next_vote = (
        session.query(Vote)
        .filter(Vote.user == context.user)
        .filter(Vote.poll == vote.poll)
        .filter(Vote.priority == previous_priority + direction)
        .one_or_none()
    )

    if next_vote is None:
        session.rollback()
        return False

    next_vote.priority -= direction
    session.flush()
    vote.priority = previous_priority + direction

    registered = i18n.t("callback.vote.registered", locale=option.poll.locale)
    context.query.answer(registered)

    return True
