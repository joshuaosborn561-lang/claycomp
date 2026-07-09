from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMCompletion:
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    provider: str = ""
    model: str = ""


@dataclass
class ProviderInfo:
    id: str
    name: str
    env_key: str
    models: list[str]
    default_model: str
    configured: bool
