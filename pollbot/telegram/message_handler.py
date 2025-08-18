"""Handle messages."""
from typing import Optional

from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update, Chat
from telegram.ext import ContextTypes

from pollbot.display import get_settings_text
from pollbot.display.poll.option import next_option
from pollbot.enums import ExpectedInput, PollType, ReferenceType
from pollbot.helper import markdown_characters
from pollbot.i18n import i18n
from pollbot.models import Reference
from pollbot.models.poll import Poll
from pollbot.models.user import User
from pollbot.poll.helper import remove_old_references
from pollbot.poll.option import add_options_multiline
from pollbot.poll.update import update_poll_messages
from pollbot.poll.creation import create_poll
from pollbot.telegram.keyboard.creation import (
    get_open_datepicker_keyboard,
    get_skip_description_keyboard,
    get_options_entered_keyboard,
)
from pollbot.telegram.keyboard.settings import get_settings_keyboard
from pollbot.telegram.session import message_wrapper


@message_wrapper
async def handle_private_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle private text messages."""
    session = context.session
    user = context.user

    # Handle expected input based on user state
    if user.expected_input == ExpectedInput.name.name:
        await handle_poll_name_input(update, context)
    elif user.expected_input == ExpectedInput.description.name:
        await handle_poll_description_input(update, context)
    elif user.expected_input == ExpectedInput.options.name:
        await handle_poll_options_input(update, context)
    elif user.expected_input == ExpectedInput.vote_count.name:
        await handle_vote_count_input(update, context)
    else:
        # No expected input, send help message
        await update.message.reply_text(
            i18n.t("misc.unknown_command", locale=user.locale)
        )


async def handle_poll_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll name input during creation."""
    session = context.session
    user = context.user
    text = update.message.text

    if user.current_poll is None:
        await update.message.reply_text(
            i18n.t("creation.no_poll", locale=user.locale)
        )
        return

    # Set poll name
    user.current_poll.name = text
    user.expected_input = ExpectedInput.description.name

    # Ask for description
    await update.message.reply_text(
        i18n.t("creation.description", locale=user.locale),
        reply_markup=get_skip_description_keyboard(user.current_poll),
    )


async def handle_poll_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll description input during creation."""
    session = context.session
    user = context.user
    text = update.message.text

    if user.current_poll is None:
        await update.message.reply_text(
            i18n.t("creation.no_poll", locale=user.locale)
        )
        return

    # Set poll description
    user.current_poll.description = text
    user.expected_input = ExpectedInput.options.name

    # Ask for first option
    await update.message.reply_text(
        i18n.t("creation.option.first", locale=user.locale),
        reply_markup=get_open_datepicker_keyboard(user.current_poll),
    )


async def handle_poll_options_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll options input during creation."""
    session = context.session
    user = context.user
    text = update.message.text

    if user.current_poll is None:
        await update.message.reply_text(
            i18n.t("creation.no_poll", locale=user.locale)
        )
        return

    # Add options (multiline support) and get the list of added options
    added_options = add_options_multiline(session, user.current_poll, text)
    session.commit()

    # Set expected input for next option
    user.expected_input = ExpectedInput.options.name

    # Send confirmation message manually since next_option() uses old API
    if len(added_options) == 1:
        await update.message.reply_text(
            f"✅ Added option: *{added_options[0]}*\n\nSend another option or use the buttons below.",
            parse_mode="Markdown",
            reply_markup=get_options_entered_keyboard(user.current_poll)
        )
    elif len(added_options) > 1:
        options_text = "\n".join([f"• *{opt}*" for opt in added_options])
        await update.message.reply_text(
            f"✅ Added {len(added_options)} options:\n{options_text}\n\nSend another option or use the buttons below.",
            parse_mode="Markdown",
            reply_markup=get_options_entered_keyboard(user.current_poll)
        )
    else:
        await update.message.reply_text(
            "⚠️ No valid options were added. Please try again."
        )


async def handle_vote_count_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle vote count input for limited/cumulative polls."""
    session = context.session
    user = context.user
    text = update.message.text

    if user.current_poll is None:
        await update.message.reply_text(
            i18n.t("creation.no_poll", locale=user.locale)
        )
        return

    try:
        vote_count = int(text)
        if vote_count <= 0:
            raise ValueError("Vote count must be positive")

        user.current_poll.number_of_votes = vote_count
        user.expected_input = None

        # Create the poll
        await create_poll(session, user.current_poll, user, update.message.chat, update.message)

    except ValueError:
        await update.message.reply_text(
            i18n.t("creation.vote_count_invalid", locale=user.locale)
        )
