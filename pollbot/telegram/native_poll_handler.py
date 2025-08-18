"""Handle native telegram polls."""
import logging
from sqlalchemy.orm import Session
from telegram import Bot, Update
from telegram import Poll as NativePoll
from telegram.ext import ContextTypes

from pollbot.enums import ExpectedInput
from pollbot.i18n import i18n
from pollbot.models import Poll, User
from pollbot.poll.native_polls import merge_from_native_poll
from pollbot.poll.option import add_multiple_options
from pollbot.telegram.keyboard.creation import get_cancel_creation_keyboard
from pollbot.telegram.session import message_wrapper

logger = logging.getLogger(__name__)


@message_wrapper
async def create_from_native_poll(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create a pollbot poll from a native telegram poll."""
    session: Session = context.session
    user: User = context.user
    native_poll = update.message.poll

    # Check if user is already creating a poll
    if user.current_poll is not None and not user.current_poll.created:
        await update.effective_chat.send_message(
            i18n.t("creation.already_creating", locale=user.locale),
            reply_markup=get_cancel_creation_keyboard(user.current_poll),
        )
        return

    # Create a new poll
    poll = Poll.create(user, session)
    merge_from_native_poll(poll, native_poll, session)

    # Send success message
    await update.effective_chat.send_message(
        i18n.t("creation.native_poll.success", locale=user.locale),
    )

    logger.info(
        f"Poll created from native poll - Poll ID: {poll.id}, User: {user.id} (@{user.username or 'no_username'})"
    )


@message_wrapper
async def send_error_quiz_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send error message for unsupported quiz polls."""
    user = context.user
    await update.effective_chat.send_message(
        i18n.t("creation.native_poll.quiz_unsupported", locale=user.locale)
    )
