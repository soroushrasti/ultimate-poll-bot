import logging

def log_poll_event(event_type: str, poll_id: int, user_id: int, details: str = None):
    """Log poll-related events."""
    log_message = f"{event_type} - Poll ID: {poll_id}, User: {user_id}"
    if details:
        log_message += f", Details: {details}"
    logging.info(log_message)
