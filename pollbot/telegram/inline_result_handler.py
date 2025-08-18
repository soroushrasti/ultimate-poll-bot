"""Handle inline query results."""
import logging
from telegram import Update
from telegram.ext import CallbackContext

from pollbot.enums import ReferenceType
from pollbot.helper.stats import increase_user_stat
from pollbot.models import Poll, Reference
from pollbot.poll.update import try_update_reference
from pollbot.telegram.session import inline_query_wrapper

logger = logging.getLogger(__name__)


@inline_query_wrapper
async def handle_chosen_inline_result(update: Update, context: CallbackContext) -> None:
    """Save the chosen inline result and handle poll sharing."""
    session = context.session
    user = context.user
    result = update.chosen_inline_result
    poll_id = result.result_id

    # Try to get the poll and create a reference
    poll = session.query(Poll).get(poll_id)
    if poll is None:
        logger.warning(f"Poll {poll_id} doesn't exist (Inline chosen result)")
        return

    # Create a reference
    reference = Reference(
        poll,
        ReferenceType.inline.name,
        result.inline_message_id,
    )
    session.add(reference)
    session.commit()

    # Increase the inline shares counter
    increase_user_stat(session, poll.user, "inline_shares")
    session.commit()

    # Try to update the reference
    try:
        await try_update_reference(session, context.bot, reference)
    except Exception as e:
        logger.error(f"Error while updating reference: {str(e)}")

    # Log the sharing event
    logger.info(
        f"Poll shared - Poll ID: {poll_id}, User: {user.id} (@{user.username or 'no_username'}), Type: inline"
    )
