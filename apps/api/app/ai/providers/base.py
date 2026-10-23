from dataclasses import dataclass, field
from typing import Protocol


class ProviderUnavailable(Exception):
    """Safe, categorised failure; never carries credentials or response bodies."""

    def __init__(self, code="provider_unavailable"):
        self.code = code
        super().__init__(code)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Completion:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    def health(self) -> bool: ...
    def complete(self, messages: list[dict], tools: list[dict]) -> Completion: ...
