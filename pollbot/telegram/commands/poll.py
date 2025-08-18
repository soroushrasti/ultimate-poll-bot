"""Poll related commands."""
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.ext import ContextTypes

from pollbot.display.misc import get_poll_list
from pollbot.display.poll.compilation import get_poll_text_and_vote_keyboard
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

        # Log poll sharing event
        from pollbot.pollbot import log_poll_event
        log_poll_event("Poll Shared", poll.id, user.id, f"Poll: {poll.name}")

        # Show the poll to the user with voting options
        text, keyboard = get_poll_text_and_vote_keyboard(session, poll, user)

        # Ensure we have valid text to avoid "message text is empty" error
        if not text or text.strip() == "":
            text = f"📊 {poll.name}\n\n{i18n.t('poll.vote_prompt', locale=user.locale)}"

        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except (ValueError, IndexError) as e:
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
