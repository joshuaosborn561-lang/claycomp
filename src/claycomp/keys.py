from __future__ import annotations

import json
import os
from contextvars import ContextVar

from claycomp.storage.api_keys import get_api_key_store

_request_keys: ContextVar[dict[str, str] | None] = ContextVar("request_keys", default=None)


def set_request_keys(keys: dict[str, str]) -> None:
    _request_keys.set(keys)


def get_request_keys() -> dict[str, str]:
    val = _request_keys.get()
    return val if val is not None else {}


async def bind_api_keys(header_raw: str = "") -> dict[str, str]:
    """Load stored API keys and bind them to the current async context."""
    stored = await get_api_key_store().get_keys()

    header_keys: dict[str, str] = {}
    if header_raw:
        try:
            parsed = json.loads(header_raw)
            if isinstance(parsed, dict):
                header_keys = {k: str(v) for k, v in parsed.items() if v}
        except json.JSONDecodeError:
            pass

    merged = {**stored, **header_keys}
    set_request_keys(merged)
    return merged


def get_api_key(name: str) -> str | None:
    val = get_request_keys().get(name) or os.getenv(name)
    return val if val else None


def has_api_key(name: str) -> bool:
    return bool(get_api_key(name))
