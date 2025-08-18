from __future__ import annotations

from sentry_sdk import add_breadcrumb
from sqlalchemy.orm.scoping import scoped_session
from telegram import Update
from telegram.ext import CallbackContext as TelegramCallbackContext

from pollbot.enums import CallbackResult, CallbackType
from pollbot.models import Poll


class CallbackContext:
    """Contains all important information for handling with callbacks."""

    def __init__(self, session: scoped_session, bot, query, user):
        """Create a new CallbackContext from a query."""
        self.bot = bot
        self.query = query
        self.user = user

        # Extract the callback type, task id
        self.data = self.query.data.split(":")
        self.callback_type = CallbackType(int(self.data[0]))
        self.payload = self.data[1]
        try:
            self.action = int(self.data[2])
        except ValueError:
            self.action = self.data[2]

        self.poll = session.query(Poll).get(self.payload)

        # Try to resolve the callback result, if possible
        self.callback_result = None
        try:
            self.callback_result = CallbackResult(self.action)
        except (ValueError, KeyError):
            pass

        if self.query.message:
            # Get chat entity and telegram chat
            self.tg_chat = self.query.message.chat

        # Add deep linking support for shared polls
        if self.poll and not hasattr(self, 'tg_chat'):
            self.shared = True
        else:
            self.shared = False

    def __repr__(self):
        """Print as string."""
        representation = (
            f"Context: query-{self.data}, poll-({self.poll}), user-({self.user}), "
        )
        representation += f"type-{self.callback_type}, action-{self.action}"
        if self.shared:
            representation += ", shared-True"

        return representation


def get_context(bot, update: Update, session: scoped_session, user) -> CallbackContext:
    """Get the callback context from a single update."""
    add_breadcrumb(
        category="context",
        message=f"Context for user {user}.",
        level="info",
    )

    # Handle callback queries
    query = update.callback_query
    if query:
        return CallbackContext(session, bot, query, user)

    # Handle deep linking for shared polls
    if update.message and update.message.text and update.message.text.startswith('/start poll_'):
        poll_id = update.message.text.split('_')[1]
        poll = session.query(Poll).get(poll_id)
        if poll:
            context = CallbackContext(session, bot, None, user)
            context.poll = poll
            context.shared = True
            return context

    return None
