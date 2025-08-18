"""Filters for various messages."""
from telegram import Poll, Message
from telegram.ext.filters import BaseFilter


class _Quiz(BaseFilter):
    name = "Filters.quiz"

    def filter(self, message: Message) -> bool:
        return bool(message.poll) and message.poll.type == Poll.QUIZ


class CustomFilters:
    quiz = _Quiz()
