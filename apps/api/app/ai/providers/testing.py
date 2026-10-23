"""Deterministic fixtures only. Never a selectable real-user inference provider."""

from .base import Completion, ProviderUnavailable


class TestProvider:
    __test__ = False

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = []

    def health(self):
        return True

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        if not self.replies:
            raise ProviderUnavailable("test_script_exhausted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
