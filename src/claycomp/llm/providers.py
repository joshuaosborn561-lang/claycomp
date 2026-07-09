from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from claycomp.llm.types import LLMCompletion, LLMMessage, LLMToolCall, ProviderInfo


class LLMProvider(ABC):
    id: str
    name: str
    env_key: str
    default_model: str
    models: list[str]

    def is_configured(self) -> bool:
        return bool(os.getenv(self.env_key))

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            env_key=self.env_key,
            models=self.models,
            default_model=self.default_model,
            configured=self.is_configured(),
        )

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        json_mode: bool = False,
        tools: list[dict] | None = None,
    ) -> LLMCompletion:
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        ...


def _to_openai_messages(messages: list[LLMMessage]) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _parse_tool_calls(msg) -> list[LLMToolCall]:
    if not msg.tool_calls:
        return []
    return [
        LLMToolCall(
            id=tc.id,
            name=tc.function.name,
            arguments=json.loads(tc.function.arguments),
        )
        for tc in msg.tool_calls
    ]


class OpenAIProvider(LLMProvider):
    id = "openai"
    name = "OpenAI"
    env_key = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"
    models = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=os.getenv(self.env_key))

    async def complete(self, messages, *, model=None, temperature=0.4, max_tokens=None, json_mode=False, tools=None):
        kwargs: dict[str, Any] = {
            "model": model or os.getenv("OPENAI_MODEL", self.default_model),
            "messages": _to_openai_messages(messages),
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        resp = await self._client().chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        return LLMCompletion(
            content=msg.content,
            tool_calls=_parse_tool_calls(msg),
            provider=self.id,
            model=kwargs["model"],
        )

    async def stream(self, messages, *, model=None, temperature=0.4):
        stream = await self._client().chat.completions.create(
            model=model or os.getenv("OPENAI_MODEL", self.default_model),
            messages=_to_openai_messages(messages),
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class PerplexityProvider(LLMProvider):
    id = "perplexity"
    name = "Perplexity"
    env_key = "PERPLEXITY_API_KEY"
    default_model = "sonar"
    models = ["sonar", "sonar-pro", "sonar-reasoning-pro"]

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=os.getenv(self.env_key),
            base_url="https://api.perplexity.ai",
        )

    async def complete(self, messages, *, model=None, temperature=0.4, max_tokens=None, json_mode=False, tools=None):
        kwargs: dict[str, Any] = {
            "model": model or os.getenv("PERPLEXITY_MODEL", self.default_model),
            "messages": _to_openai_messages(messages),
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await self._client().chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        return LLMCompletion(
            content=msg.content,
            tool_calls=[],
            provider=self.id,
            model=kwargs["model"],
        )

    async def stream(self, messages, *, model=None, temperature=0.4):
        stream = await self._client().chat.completions.create(
            model=model or os.getenv("PERPLEXITY_MODEL", self.default_model),
            messages=_to_openai_messages(messages),
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class AnthropicProvider(LLMProvider):
    id = "anthropic"
    name = "Anthropic"
    env_key = "ANTHROPIC_API_KEY"
    default_model = "claude-sonnet-4-20250514"
    models = ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]

    async def complete(self, messages, *, model=None, temperature=0.4, max_tokens=None, json_mode=False, tools=None):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError("Install anthropic: pip install anthropic") from e

        client = AsyncAnthropic(api_key=os.getenv(self.env_key))
        system = next((m.content for m in messages if m.role == "system"), "")
        user_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        kwargs: dict[str, Any] = {
            "model": model or os.getenv("ANTHROPIC_MODEL", self.default_model),
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system:
            kwargs["system"] = system
        if json_mode:
            kwargs["system"] = (system + "\nRespond with valid JSON only.").strip()

        resp = await client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return LLMCompletion(content=text, provider=self.id, model=kwargs["model"])

    async def stream(self, messages, *, model=None, temperature=0.4):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError("Install anthropic: pip install anthropic") from e

        client = AsyncAnthropic(api_key=os.getenv(self.env_key))
        system = next((m.content for m in messages if m.role == "system"), "")
        user_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        async with client.messages.stream(
            model=model or os.getenv("ANTHROPIC_MODEL", self.default_model),
            max_tokens=1024,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=user_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


PROVIDERS: dict[str, LLMProvider] = {
    "openai": OpenAIProvider(),
    "perplexity": PerplexityProvider(),
    "anthropic": AnthropicProvider(),
}

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "openai")


def get_provider(provider_id: str | None = None) -> LLMProvider:
    pid = provider_id or DEFAULT_PROVIDER
    if pid not in PROVIDERS:
        raise ValueError(f"Unknown provider '{pid}'. Available: {', '.join(PROVIDERS)}")
    return PROVIDERS[pid]


def list_providers() -> list[ProviderInfo]:
    return [p.info() for p in PROVIDERS.values()]


async def llm_complete(
    messages: list[LLMMessage],
    *,
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> LLMCompletion:
    p = get_provider(provider)
    if not p.is_configured():
        raise RuntimeError(f"{p.env_key} not set for {p.name}")
    return await p.complete(messages, model=model, **kwargs)


async def llm_stream(
    messages: list[LLMMessage],
    *,
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> AsyncIterator[str]:
    p = get_provider(provider)
    if not p.is_configured():
        yield f"Set {p.env_key} in your .env to use {p.name}."
        return
    async for token in p.stream(messages, model=model, **kwargs):
        yield token
