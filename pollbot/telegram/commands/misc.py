"""Misc commands."""
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.ext import ContextTypes

from pollbot.display.misc import get_help_text_and_keyboard
from pollbot.models.user import User
from pollbot.telegram.session import message_wrapper


@message_wrapper
async def send_help(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help text."""
    session = context.session
    user = context.user
    text, keyboard = get_help_text_and_keyboard(user, "intro")
    await update.message.chat.send_message(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
