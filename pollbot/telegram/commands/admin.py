"""Admin related stuff."""
import time
from datetime import datetime, timedelta

from matplotlib import pyplot as plt
from sqlalchemy.orm.scoping import scoped_session
from telegram import Bot, Update, ReplyKeyboardRemove
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from pollbot.decorators import admin_required
from pollbot.models import User
from pollbot.telegram.session import message_wrapper

@admin_required
@message_wrapper
async def reset_broadcast(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> str:
    """Reset the broadcast_sent flag for all users."""
    session = context.session
    session.query(User).update({"broadcast_sent": False})
    session.commit()

    await update.message.reply_text("All broadcast flags resetted")


def remaining_time(total, current, start):
    """Small helper to calculate remaining runtime of a command."""
    elapsed = (datetime.now() - start).seconds
    remaining_factor = total / current
    total_time = elapsed * remaining_factor
    remaining_time = ((total - current) / total) * total_time
    return timedelta(seconds=int(remaining_time))

@admin_required
@message_wrapper
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a message to all users."""
    session = context.session
    chat = update.message.chat
    message = update.message.text.split(" ", 1)[1].strip()
    user_count = (
        session.query(User)
        .filter(User.notifications_enabled.is_(True))
        .filter(User.started.is_(True))
        .filter(User.banned.is_(False))
        .filter(User.broadcast_sent.is_(False))
        .count()
    )

    start_time = datetime.now()
    await chat.send_message(f"Sending broadcast to {user_count} chats.")

    sent_count = 0
    batch_size = 1000
    # Send the broadcast to 1000 users at a time (minimize ram usage)
    while sent_count <= user_count:
        users = (
            session.query(User)
            .filter(User.notifications_enabled.is_(True))
            .filter(User.started.is_(True))
            .filter(User.banned.is_(False))
            .filter(User.broadcast_sent.is_(False))
            .limit(batch_size)
            .all()
        )

        for user in users:
            try:
                bot.send_message(
                    user.id,
                    message,
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardRemove(),
                )
                user.broadcast_sent = True

            # The chat does no longer exist, delete it
            except BadRequest as e:
                if e.message == "Chat not found":
                    user.started = False

            # We are not allowed to contact this user.
            except Forbidden:
                user.started = False

            except TimeoutError:
                pass

            session.commit()
            # Sleep a little bit to not trigger flood prevention
            time.sleep(0.07)

            sent_count += 1
            if sent_count == 500:
                remaining = remaining_time(user_count, sent_count, start_time)
                chat.send_message(f"First 500 are done. Remaining time: {remaining}")

            if sent_count % 5000 == 0:
                remaining = remaining_time(user_count, sent_count, start_time)
                chat.send_message(
                    f"Sent to {sent_count} users. Remaining time: {remaining}"
                )

    update.message.chat.send_message("All messages sent")

@admin_required
@message_wrapper
async def test_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test broadcast functionality."""
    await update.message.reply_text("Test broadcast message sent successfully!")
