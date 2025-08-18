"""Callback query handling."""
from datetime import date

from sqlalchemy.exc import IntegrityError
from telegram.ext import ContextTypes

from pollbot.enums import CallbackType
from pollbot.helper.stats import increase_stat, increase_user_stat
from pollbot.models import Option, UserStatistic
from pollbot.telegram.callback_handler.context import CallbackContext
from pollbot.telegram.session import callback_query_wrapper

from .context import get_context
from .mapping import async_callback_mapping, callback_mapping
from .vote import handle_vote


@callback_query_wrapper
async def handle_callback_query(update, context: ContextTypes.DEFAULT_TYPE):
    """Handle synchronous callback queries."""
    session = context.session
    user = context.user
    query = update.callback_query

    callback_context = get_context(context.bot, update, session, user)

    increase_user_stat(session, callback_context.user, "callback_calls")
    session.commit()

    response = await callback_mapping[callback_context.callback_type](session, callback_context)

    # Callback handler functions always return the callback answer
    if response is not None and callback_context.callback_type != CallbackType.vote:
        await query.answer(response)
    else:
        await query.answer("")

    increase_stat(session, "callback_calls")


@callback_query_wrapper
async def handle_async_callback_query(update, context: ContextTypes.DEFAULT_TYPE):
    """Handle asynchronous callback queries."""
    session = context.session
    user = context.user
    query = update.callback_query

    callback_context = get_context(context.bot, update, session, user)

    # Vote logic needs some special handling
    if callback_context.callback_type == CallbackType.vote:
        try:
            # Handle vote with proper error handling
            response = await handle_vote(session, callback_context)
            if response:
                await query.answer(response)
            else:
                await query.answer("")
            return
        except IntegrityError as e:
            session.rollback()
            # This can happen if people click on a vote button multiple times
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                await query.answer("Vote already registered!")
                return
            raise e

    increase_user_stat(session, callback_context.user, "callback_calls")

    try:
        response = await async_callback_mapping[callback_context.callback_type](session, callback_context)

        # Callback handler functions always return the callback answer
        if response is not None:
            await query.answer(response)
        else:
            await query.answer("")

    except KeyError:
        await query.answer("Unknown callback type!")

    increase_stat(session, "callback_calls")
