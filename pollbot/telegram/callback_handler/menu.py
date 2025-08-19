"""Callback functions needed during creation of a Poll."""

from sqlalchemy.orm.scoping import scoped_session

from pollbot.decorators import poll_required
from pollbot.display import get_settings_text
from pollbot.display.poll.compilation import (
    get_poll_text,
    get_poll_text_and_vote_keyboard,
)
from pollbot.enums import CallbackResult, ExpectedInput, ReferenceType
from pollbot.i18n import i18n
from pollbot.models import Reference
from pollbot.models.poll import Poll
from pollbot.poll.helper import remove_old_references
from pollbot.poll.vote import init_votes
from pollbot.telegram.callback_handler.context import CallbackContext
from pollbot.telegram.keyboard.management import (
    get_close_confirmation,
    get_deletion_confirmation,
    get_management_keyboard,
)
from pollbot.telegram.keyboard.settings import get_settings_keyboard


@poll_required
async def go_back(session: scoped_session, context: CallbackContext, poll: Poll) -> None:
    """Go back to the original step."""
    # Parse the callback result from the action field
    try:
        callback_result = CallbackResult(context.action)
    except (ValueError, TypeError):
        # Default to main menu if parsing fails
        callback_result = CallbackResult.main_menu

    if callback_result in [CallbackResult.main_menu, CallbackResult.back_to_main]:
        text = get_poll_text(session, poll)
        keyboard = get_management_keyboard(poll)
        poll.in_settings = False

    elif callback_result == CallbackResult.settings:
        text = get_settings_text(poll)
        keyboard = get_settings_keyboard(poll)
    else:
        # Default to main menu for unknown callback results
        text = get_poll_text(session, poll)
        keyboard = get_management_keyboard(poll)
        poll.in_settings = False

    await context.query.message.edit_text(
        text,
        parse_mode="markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

    # Reset the expected input from the previous option
    context.user.expected_input = None


@poll_required
async def show_vote_menu(
    session: scoped_session, context: CallbackContext, poll: Poll
) -> None:
    """Show the vote keyboard in the management interface."""
    if poll.is_priority():
        init_votes(session, poll, context.user)
        session.commit()

    text, keyboard = get_poll_text_and_vote_keyboard(
        session, poll, user=context.user, show_back=True
    )
    # Set the expected_input to votes, since the user might want to vote multiple times
    context.user.expected_input = ExpectedInput.votes.name
    await context.query.message.edit_text(
        text,
        parse_mode="markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@poll_required
async def show_settings(_: scoped_session, context: CallbackContext, poll: Poll) -> None:
    """Show the settings tab."""
    text = get_settings_text(poll)
    keyboard = get_settings_keyboard(poll)
    await context.query.message.edit_text(
        text,
        parse_mode="markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    poll.in_settings = True


@poll_required
async def show_deletion_confirmation(
    _: scoped_session, context: CallbackContext, poll: Poll
) -> None:
    """Show the delete confirmation message."""
    import logging

    # Log the poll and keyboard details
    logging.debug(f"Poll: {poll}")
    keyboard = get_deletion_confirmation(poll)
    logging.debug(f"Generated Keyboard: {keyboard}")

    await context.query.message.edit_text(
        i18n.t("management.delete", locale=poll.user.locale),
        reply_markup=get_deletion_confirmation(poll),
    )


@poll_required
async def show_close_confirmation(
    _: scoped_session, context: CallbackContext, poll: Poll
) -> None:
    """Show the permanent close confirmation message."""
    await context.query.message.edit_text(
        i18n.t("management.permanently_close", locale=poll.user.locale),
        reply_markup=get_close_confirmation(poll),
    )


@poll_required
async def show_menu(session: scoped_session, context: CallbackContext, poll: Poll) -> None:
    """Replace the current message with the main poll menu."""
    message = context.query.message
    await message.edit_text(
        get_poll_text(session, poll),
        parse_mode="markdown",
        reply_markup=get_management_keyboard(poll),
        disable_web_page_preview=True,
    )
    await remove_old_references(session, context.bot, poll, context.user)

    reference = Reference(
        poll, ReferenceType.admin.name, user=context.user, message_id=message.message_id
    )
    session.add(reference)
    session.flush()
