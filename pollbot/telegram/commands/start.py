"""The start command handler."""
import logging
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.ext import ContextTypes

from pollbot.config import config
from pollbot.display.poll.compilation import (
    compile_poll_text,
    get_poll_text_and_vote_keyboard,
)
from pollbot.enums import ExpectedInput, ReferenceType, StartAction
from pollbot.helper.stats import increase_stat
from pollbot.helper.text import split_text
from pollbot.i18n import i18n
from pollbot.models import Poll, Reference
from pollbot.models.user import User
from pollbot.poll.vote import init_votes
from pollbot.telegram.keyboard.external import (
    get_external_add_option_keyboard,
    get_external_share_keyboard,
)
from pollbot.telegram.keyboard.user import get_main_keyboard
from pollbot.telegram.session import message_wrapper

logger = logging.getLogger(__name__)


@message_wrapper
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a start text."""
    session = context.session
    user = context.user

    # Truncate the /start command
    text = update.message.text[6:].strip()
    user.started = True

    # Handle poll sharing via deep links
    if text:
        try:
            # Extract UUID from the deep link
            poll_uuid = text.split("-")[0]
            poll = session.query(Poll).filter_by(uuid=poll_uuid).one_or_none()

            if poll is None:
                await update.message.reply_text(
                    i18n.t("poll.not_found", locale=user.locale),
                )
                return

            # Log poll access
            logger.info(f"Poll accessed via deep link - Poll UUID: {poll.uuid}, User: {user.id}")

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
            return

        except Exception as e:
            logger.error(f"Error handling deep link: {e}")
            await update.message.reply_text(
                i18n.t("poll.invalid_link", locale=user.locale),
            )
            return

    # Default start message
    await update.message.reply_text(
        i18n.t("misc.start", locale=user.locale),
        reply_markup=get_main_keyboard(user),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    increase_stat(session, "started")
