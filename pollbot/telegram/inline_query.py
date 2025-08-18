"""Handle inline query results."""
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import ContextTypes

from pollbot.config import config
from pollbot.enums import CallbackType, ReferenceType
from pollbot.i18n import i18n
from pollbot.models import Poll
from pollbot.models.user import User
from pollbot.telegram.session import inline_query_wrapper


@inline_query_wrapper
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries for poll search and sharing."""
    session = context.session
    user = context.user
    query = update.inline_query.query.strip()

    # Check if it's a direct poll ID share
    if query.isdigit():
        poll_id = int(query)
        poll = session.query(Poll).get(poll_id)

        if poll and not poll.deleted:
            # Create a shareable poll result
            from pollbot.display.poll.compilation import get_poll_text_and_vote_keyboard

            poll_text, vote_keyboard = get_poll_text_and_vote_keyboard(session, poll, user)

            # Ensure we have valid text
            if not poll_text or poll_text.strip() == "":
                poll_text = f"📊 *{poll.name}*\n\n{poll.description or 'Click to vote!'}"

            # Create the shareable content
            content = InputTextMessageContent(
                message_text=poll_text,
                parse_mode='Markdown'
            )

            results = [
                InlineQueryResultArticle(
                    id=str(poll.id),
                    title=f"📊 {poll.name}",
                    description="Click to share this poll with voting options",
                    input_message_content=content,
                    reply_markup=vote_keyboard
                )
            ]

            await update.inline_query.answer(results, cache_time=1)
            return

    # Original search functionality for user's own polls
    closed_polls = 'closed_polls' in query
    query = query.replace('closed_polls', '').strip()

    # Search polls
    polls = session.query(Poll) \
        .filter(Poll.user == user) \
        .filter(Poll.deleted.is_(False))

    if not closed_polls:
        polls = polls.filter(Poll.closed.is_(False))

    # Set the query
    if query.strip() != '':
        polls = polls.filter(Poll.name.ilike(f'%{query}%'))

    polls = polls.order_by(Poll.created_at.desc()) \
        .limit(10) \
        .all()

    results = []
    # Create an article for each poll that shares the actual poll with voting
    for poll in polls:
        # Get the full poll text with voting options
        from pollbot.display.poll.compilation import get_poll_text_and_vote_keyboard
        poll_text, vote_keyboard = get_poll_text_and_vote_keyboard(session, poll, user)

        # Ensure we have valid text
        if not poll_text or poll_text.strip() == "":
            poll_text = f"📊 *{poll.name}*\n\n{poll.description or 'No description'}"

        # Create the shareable content with voting keyboard
        content = InputTextMessageContent(
            message_text=poll_text,
            parse_mode='Markdown'
        )

        # Use the poll title as the inline result title
        title = poll.name or "Untitled Poll"
        description = poll.description[:100] if poll.description else "Click to vote on this poll"

        results.append(
            InlineQueryResultArticle(
                id=str(poll.id),
                title=title,
                description=description,
                input_message_content=content,
                reply_markup=vote_keyboard  # Use the actual voting keyboard
            )
        )

    await update.inline_query.answer(results, cache_time=1)
