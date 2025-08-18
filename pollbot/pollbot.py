"""A bot which checks if there is a new record in the server section of hetzner."""
import logging
import datetime
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    filters,
)

from pollbot.config import config
from pollbot.telegram.callback_handler import (
    handle_async_callback_query,
    handle_callback_query,
)
from pollbot.telegram.callback_handler.mapping import (
    get_async_callback_mapping_regex,
    get_callback_mapping_regex,
)
from pollbot.telegram.commands.admin import broadcast, reset_broadcast, test_broadcast
from pollbot.telegram.commands.external import notify
from pollbot.telegram.commands.misc import send_help
from pollbot.telegram.commands.poll import (
    cancel_poll_creation,
    create_poll,
    list_closed_polls,
    list_polls,
    handle_shared_poll,
)
from pollbot.telegram.commands.start import start
from pollbot.telegram.commands.user import delete_me, open_user_settings_command, stop
from pollbot.telegram.filters import CustomFilters
from pollbot.telegram.inline_query import search
from pollbot.telegram.inline_result_handler import handle_chosen_inline_result
from pollbot.telegram.job import (
    cleanup,
    create_daily_stats,
    delete_polls,
    message_update_job,
    perma_ban_checker,
    send_notifications,
)
from pollbot.telegram.message_handler import handle_private_text
from pollbot.telegram.native_poll_handler import (
    create_from_native_poll,
    send_error_quiz_unsupported,
)

# Setup logging
logging.basicConfig(
    level=config["logging"]["log_level"],
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def log_poll_event(event_type: str, poll_id: int, user_id: int, details: str = None):
    """Log poll-related events."""
    log_message = f"{event_type} - Poll ID: {poll_id}, User: {user_id}"
    if details:
        log_message += f", Details: {details}"
    logger.info(log_message)

# Initialize application with job queue enabled
application = (
    Application.builder()
    .token(config["telegram"]["api_key"])
    .build()
)

# Disable scheduled jobs to avoid conflicts during debugging
# Jobs configuration - commented out to disable scheduler
# if application.job_queue:
#     # Schedule jobs
#     application.job_queue.run_repeating(
#         message_update_job, interval=60, first=10, name="message_update"
#     )
#     application.job_queue.run_repeating(
#         delete_polls, interval=60 * 60, first=20, name="delete_polls"
#     )
#     application.job_queue.run_repeating(
#         send_notifications, interval=60, first=30, name="send_notifications"
#     )
#     application.job_queue.run_repeating(
#         perma_ban_checker, interval=60 * 60, first=40, name="perma_ban_checker"
#     )
#     application.job_queue.run_daily(
#         create_daily_stats, time=datetime.time(hour=0, minute=0, second=0)
#     )
#     application.job_queue.run_repeating(
#         cleanup, interval=60 * 60 * 24, first=50, name="cleanup"
#     )

logger.info("Scheduler jobs disabled for debugging")

command_filter = ~filters.UpdateType.EDITED_MESSAGE
# Poll commands
application.add_handler(
    CommandHandler(
        ["create", "new", "add"],
        create_poll,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        ["cancel", "abort"],
        cancel_poll_creation,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "list",
        list_polls,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "list_closed",
        list_closed_polls,
        filters=command_filter,
    )
)

# Handle shared polls via deep linking
application.add_handler(
    MessageHandler(
        filters.TEXT & filters.Regex(r"^/start poll_\d+$"),
        handle_shared_poll
    )
)

# Misc commands
application.add_handler(
    CommandHandler(
        "start",
        start,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "stop",
        stop,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "delete_me",
        delete_me,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "settings",
        open_user_settings_command,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "help",
        send_help,
        filters=command_filter,
    )
)

# External commands
application.add_handler(
    CommandHandler(
        "notify",
        notify,
        filters=command_filter,
    )
)

# Admin command
application.add_handler(
    CommandHandler(
        "broadcast",
        broadcast,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "reset_broadcast",
        reset_broadcast,
        filters=command_filter,
    )
)
application.add_handler(
    CommandHandler(
        "test_broadcast",
        test_broadcast,
        filters=command_filter,
    )
)

# Poll handler - only handle actual Telegram polls, not text messages
application.add_handler(
    MessageHandler(
        filters.POLL & ~CustomFilters.quiz & filters.ChatType.PRIVATE,
        create_from_native_poll,
    )
)
application.add_handler(
    MessageHandler(
        filters.POLL & CustomFilters.quiz & filters.ChatType.PRIVATE,
        send_error_quiz_unsupported,
    )
)

# Callback handler
application.add_handler(
    CallbackQueryHandler(handle_callback_query, pattern=get_callback_mapping_regex())
)
application.add_handler(
    CallbackQueryHandler(
        handle_async_callback_query,
        pattern=get_async_callback_mapping_regex(),
    )
)

# InlineQuery handler
application.add_handler(InlineQueryHandler(search))

# InlineQuery result handler
application.add_handler(
    ChosenInlineResultHandler(handle_chosen_inline_result)
)

# Message handler
application.add_handler(
    MessageHandler(
        filters.TEXT
        & filters.ChatType.PRIVATE
        & (~filters.UpdateType.EDITED_MESSAGE)
        & (~filters.REPLY)
        & (~filters.UpdateType.CHANNEL_POST),
        handle_private_text,
    )
)

# Error handler
async def error_handler(update, context):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

application.add_error_handler(error_handler)

# Start the bot
if __name__ == "__main__":
    application.run_polling()
