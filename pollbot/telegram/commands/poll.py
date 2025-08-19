"""Poll related commands."""
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.ext import ContextTypes

from pollbot.display.misc import get_poll_list
from pollbot.i18n import i18n
from pollbot.models import Poll
from pollbot.models.user import User
from pollbot.poll.creation import initialize_poll
from pollbot.helper.logging import log_poll_event
from pollbot.telegram.session import message_wrapper


@message_wrapper
async def create_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new poll."""
    session = context.session
    user = context.user
    await initialize_poll(session, user, update.message.chat)


@message_wrapper
async def handle_shared_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when a user clicks on a shared poll."""
    import logging

    session = context.session
    user = context.user

    if not update.message.text.startswith("/start poll_"):
        return

    try:
        poll_id = int(update.message.text.split("_")[1])
        poll = session.query(Poll).get(poll_id)

        if poll is None:
            logging.debug("Poll not found.")
            await update.message.reply_text(
                i18n.t("poll.not_found", locale=user.locale),
            )
            return

        logging.debug(f"Poll found: {poll.name}, Options: {poll.options}")

        # Log the shared poll access
        log_poll_event("Shared Poll Accessed", poll.id, user.id, f"Poll Name: {poll.name}")

        # Retrieve poll options and display the poll
        message = await update.message.reply_text(
            f"Poll: {poll.name}\n\nOptions:\n" + "\n".join([option.name for option in poll.options]),
            parse_mode="Markdown",
        )
        logging.debug(f"Message sent: {message}")

    except (ValueError, AttributeError) as e:
        logging.error(f"Error handling shared poll: {e}")
        await update.message.reply_text(
            i18n.t("poll.invalid_link", locale=user.locale),
        )


@message_wrapper
async def cancel_poll_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the creation of the current poll."""
    session = context.session
    user = context.user

    if user.current_poll is not None:
        session.delete(user.current_poll)
        user.current_poll = None
        session.commit()
        await update.message.reply_text(
            i18n.t("poll.creation_cancelled", locale=user.locale)
        )
    else:
        await update.message.reply_text(
            i18n.t("poll.no_active_creation", locale=user.locale)
        )


@message_wrapper
async def list_polls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a list of all active polls for the current user."""
    import logging

    session = context.session
    user = context.user

    polls = (
        session.query(Poll)
        .filter(Poll.user == user)
        .filter(Poll.delete.is_(None))
        .filter(Poll.closed.is_(False))
        .order_by(Poll.created_at.desc())
        .all()
    )

    logging.debug(f"Retrieved polls: {polls}")

    if not polls:
        await update.message.reply_text(
            i18n.t("poll.no_polls", locale=user.locale)
        )
        return

    # Use offset=0 for initial /list command, closed=False for active polls
    text, _ = get_poll_list(session, user, offset=0, closed=False)
    logging.debug(f"Poll list text: {text}")

    await update.message.reply_text(text, parse_mode="Markdown")


@message_wrapper
async def list_closed_polls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a list of all closed polls for the current user."""
    session = context.session
    user = context.user

    polls = (
        session.query(Poll)
        .filter(Poll.user == user)
        .filter(Poll.delete.is_(None))
        .filter(Poll.closed.is_(True))
        .order_by(Poll.created_at.desc())
        .all()
    )

    if not polls:
        await update.message.reply_text(
            i18n.t("poll.no_closed_polls", locale=user.locale)
        )
        return

    # Use offset=0 for initial /list_closed_polls command, closed=True for closed polls
    text, _ = get_poll_list(session, user, offset=0, closed=True)
    await update.message.reply_text(text, parse_mode="Markdown")
