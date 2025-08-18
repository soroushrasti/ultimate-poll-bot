"""Session helper functions."""
import asyncio
import traceback
from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Any, Union

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut, Forbidden
from telegram.ext import ContextTypes

from pollbot.config import config
from pollbot.db import get_session
from pollbot.exceptions import RollbackException
from pollbot.helper import remove_markdown_characters
from pollbot.helper.stats import increase_stat
from pollbot.i18n import i18n
from pollbot.models import User, UserStatistic
from pollbot.sentry import ignore_job_exception, sentry


def ignore_exception(exception: Exception) -> bool:
    """Check whether this exception should be ignored."""
    if type(exception) in [TimedOut, RetryAfter, NetworkError]:
        return True

    # Handle user not found and user blocked bot
    if type(exception) == BadRequest:
        bad_requests = [
            "Chat not found",
            "Message is not modified",
            "Bot was blocked by the user",
            "User is deactivated",
            "Chat_write_forbidden",
            "Channel_private",
            "Have no rights to send a message",
        ]
        for message in bad_requests:
            if message in str(exception):
                return True

    if type(exception) == Forbidden:
        return True

    return False


def should_report_exception(context: ContextTypes.DEFAULT_TYPE, exception: Exception) -> bool:
    """Check whether this exception should be reported to sentry."""
    if ignore_exception(exception):
        return False

    if type(exception) in [ObjectDeletedError, IntegrityError]:
        return False

    return True


def job_wrapper(func: Callable):
    """Wrapper for jobs to catch exceptions and handle sessions."""
    @wraps(func)
    async def wrapper(context: ContextTypes.DEFAULT_TYPE):
        session = get_session()
        try:
            await func(context, session)
            session.commit()
        except Exception as e:
            session.rollback()
            if should_report_exception(context, e):
                sentry.capture_exception(e)
            if not ignore_job_exception(e):
                raise e
        finally:
            session.close()
    return wrapper


def message_wrapper(func: Callable):
    """Wrapper for message handlers to catch exceptions and handle sessions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        session = get_session()
        try:
            # Inject session and user into context
            context.session = session
            context.user = get_user(session, update)

            await func(update, context)
            session.commit()
        except RollbackException:
            session.rollback()
        except Exception as e:
            session.rollback()
            if should_report_exception(context, e):
                sentry.capture_exception(e)
            if not ignore_exception(e):
                raise e
        finally:
            session.close()
    return wrapper


def callback_query_wrapper(func: Callable):
    """Wrapper for callback query handlers to catch exceptions and handle sessions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        session = get_session()
        try:
            # Inject session and user into context
            context.session = session
            context.user = get_user(session, update)

            await func(update, context)
            session.commit()
        except RollbackException:
            session.rollback()
        except Exception as e:
            session.rollback()
            if should_report_exception(context, e):
                sentry.capture_exception(e)
            if not ignore_exception(e):
                raise e
        finally:
            session.close()
    return wrapper


def inline_query_wrapper(func: Callable):
    """Wrapper for inline query handlers to catch exceptions and handle sessions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        session = get_session()
        try:
            # Inject session and user into context
            context.session = session
            context.user = get_user(session, update)

            await func(update, context)
            session.commit()
        except Exception as e:
            session.rollback()
            if should_report_exception(context, e):
                sentry.capture_exception(e)
            if not ignore_exception(e):
                raise e
        finally:
            session.close()
    return wrapper


def inline_result_wrapper(func: Callable):
    """Wrapper for inline result handlers to catch exceptions and handle sessions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        session = get_session()
        try:
            await func(update, context, session)
            session.commit()
        except Exception as e:
            session.rollback()
            if should_report_exception(context, e):
                sentry.capture_exception(e)
            if not ignore_exception(e):
                raise e
        finally:
            session.close()
    return wrapper


def get_user(session: Session, update: Update) -> User:
    """Get the user from the update."""
    from_user = update.effective_user
    if from_user is None:
        raise Exception("No user in update")

    user = session.query(User).filter(User.id == from_user.id).one_or_none()

    # Create user if it doesn't exist
    if user is None:
        user = User(from_user.id, from_user.username)
        session.add(user)
        session.commit()

    # Update username if it changed
    if user.username != from_user.username:
        user.username = from_user.username

    return user


def get_user_from_context(session: Session, context: ContextTypes.DEFAULT_TYPE) -> User:
    """Get the user from the job context."""
    user_id = context.job.data
    user = session.query(User).filter(User.id == user_id).one_or_none()
    return user


def create_or_get_user(session: Session, user_id: int, username: str = None) -> User:
    """Create or get a user."""
    user = session.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        user = User(user_id, username)
        session.add(user)

    return user


def extract_update_info(update):
    """Extract all possible info from telegram update."""
    # Extract user info
    user = None
    if update.effective_user is not None:
        user = {
            "id": update.effective_user.id,
            "name": update.effective_user.full_name,
            "username": update.effective_user.username,
        }

    # Extract chat info
    chat = None
    if update.effective_chat is not None:
        chat = {
            "id": update.effective_chat.id,
            "name": update.effective_chat.title,
            "type": update.effective_chat.type,
        }

    # Extract message info
    message_info = None
    if update.effective_message is not None:
        message_info = {
            "message_id": update.effective_message.message_id,
            "text": update.effective_message.text,
        }

    return {
        "user": user,
        "chat": chat,
        "message": message_info,
    }
