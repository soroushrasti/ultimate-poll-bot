"""Poll related commands."""
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.ext import ContextTypes

from pollbot.display.misc import get_poll_list
from pollbot.i18n import i18n
from pollbot.models import Poll
from pollbot.models.user import User
from pollbot.poll.creation import initialize_poll
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
    session = context.session
    user = context.user

    if not update.message.text.startswith("/start poll_"):
        return

    try:
        poll_id = int(update.message.text.split("_")[1])
        poll = session.query(Poll).get(poll_id)

        if poll is None:
            await update.message.reply_text(
                i18n.t("poll.not_found", locale=user.locale),
            )
            return

        # Retrieve poll options
        options = session.query(pollbot.models.option.Option).filter_by(poll_id=poll.id).order_by(pollbot.models.option.Option.index).all()
        option_names = [option.name for option in options]

        # Send the poll using send_poll
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=poll.name,
            options=option_names,
            is_anonymous=poll.anonymous,
            allows_multiple_answers=(poll.poll_type == "multiple_vote"),
        )
    except Exception as e:
        await update.message.reply_text(f"Error sharing poll: {str(e)}")


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
    session = context.session
    user = context.user

    polls = (
        session.query(Poll)
        .filter(Poll.user == user)
        .filter(Poll.deleted.is_(False))
        .filter(Poll.closed.is_(False))
        .order_by(Poll.created_at.desc())
        .all()
    )

    if not polls:
        await update.message.reply_text(
            i18n.t("poll.no_polls", locale=user.locale)
        )
        return

    text = get_poll_list(polls, user.locale)
    await update.message.reply_text(text, parse_mode="Markdown")


@message_wrapper
async def list_closed_polls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a list of all closed polls for the current user."""
    session = context.session
    user = context.user

    polls = (
        session.query(Poll)
        .filter(Poll.user == user)
        .filter(Poll.deleted.is_(False))
        .filter(Poll.closed.is_(True))
        .order_by(Poll.created_at.desc())
        .all()
    )

    if not polls:
        await update.message.reply_text(
            i18n.t("poll.no_closed_polls", locale=user.locale)
        )
        return

    text = get_poll_list(polls, user.locale)
    await update.message.reply_text(text, parse_mode="Markdown")
