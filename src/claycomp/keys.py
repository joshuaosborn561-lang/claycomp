from __future__ import annotations

import os
from contextvars import ContextVar

_request_keys: ContextVar[dict[str, str]] = ContextVar("request_keys", default={})


def set_request_keys(keys: dict[str, str]) -> None:
    _request_keys.set(keys)


def get_request_keys() -> dict[str, str]:
    return _request_keys.get()


def get_api_key(name: str) -> str | None:
    val = _request_keys.get().get(name) or os.getenv(name)
    return val if val else None


def has_api_key(name: str) -> bool:
    return bool(get_api_key(name))
