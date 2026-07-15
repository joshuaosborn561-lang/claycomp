from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from claycomp.storage.config import STORAGE_SETUP_MESSAGE, redis_credentials, supabase_configured
from claycomp.storage.supabase_client import SupabaseClient, SupabaseError

API_KEY_NAMES = (
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_PLACES_API_KEY",
    "AI_ARK_API_KEY",
    "PROSPEO_API_KEY",
)

SETTINGS_ROW_ID = "api_keys"


class StorageNotConfiguredError(RuntimeError):
    pass


def mask_api_key(value: str) -> str:
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}...{value[-4:]}"


class ApiKeyStore(ABC):
    @abstractmethod
    async def get_keys(self) -> dict[str, str]:
        ...

    @abstractmethod
    async def save_keys(self, updates: dict[str, str]) -> dict[str, str]:
        ...


class FileApiKeyStore(ApiKeyStore):
    """Local development only."""

    def __init__(self, path: Path | None = None):
        root = Path(os.getenv("CLAYCOMP_DATA_DIR", "./data"))
        root.mkdir(parents=True, exist_ok=True)
        self.path = path or root / "api_keys.json"

    async def get_keys(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        return {k: str(v) for k, v in data.items() if k in API_KEY_NAMES and v}

    async def save_keys(self, updates: dict[str, str]) -> dict[str, str]:
        current = await self.get_keys()
        for name, value in updates.items():
            if name not in API_KEY_NAMES:
                continue
            trimmed = value.strip()
            if trimmed:
                current[name] = trimmed
            else:
                current.pop(name, None)
        self.path.write_text(json.dumps(current, indent=2))
        return current


class SupabaseApiKeyStore(ApiKeyStore):
    TABLE = "claycomp_settings"

    def __init__(self, client: SupabaseClient | None = None):
        self.client = client or SupabaseClient.from_env()

    async def get_keys(self) -> dict[str, str]:
        rows = await self.client.select(
            self.TABLE,
            columns="keys",
            filters={"id": f"eq.{SETTINGS_ROW_ID}"},
            limit=1,
        )
        if not rows:
            return {}
        raw = rows[0].get("keys") or {}
        if not isinstance(raw, dict):
            return {}
        return {k: str(v) for k, v in raw.items() if k in API_KEY_NAMES and v}

    async def save_keys(self, updates: dict[str, str]) -> dict[str, str]:
        current = await self.get_keys()
        for name, value in updates.items():
            if name not in API_KEY_NAMES:
                continue
            trimmed = value.strip()
            if trimmed:
                current[name] = trimmed
            else:
                current.pop(name, None)
        await self.client.upsert(
            self.TABLE,
            {
                "id": SETTINGS_ROW_ID,
                "keys": current,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return current


class UpstashApiKeyStore(ApiKeyStore):
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.key = "claycomp:settings:api_keys"

    async def _cmd(self, *args: str) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=list(args),
            )
            resp.raise_for_status()
            return resp.json().get("result")

    async def get_keys(self) -> dict[str, str]:
        raw = await self._cmd("GET", self.key)
        if not raw:
            return {}
        data = json.loads(raw)
        return {k: str(v) for k, v in data.items() if k in API_KEY_NAMES and v}

    async def save_keys(self, updates: dict[str, str]) -> dict[str, str]:
        current = await self.get_keys()
        for name, value in updates.items():
            if name not in API_KEY_NAMES:
                continue
            trimmed = value.strip()
            if trimmed:
                current[name] = trimmed
            else:
                current.pop(name, None)
        await self._cmd("SET", self.key, json.dumps(current))
        return current


class UnconfiguredVercelApiKeyStore(ApiKeyStore):
    async def get_keys(self) -> dict[str, str]:
        return {}

    async def save_keys(self, updates: dict[str, str]) -> dict[str, str]:
        raise StorageNotConfiguredError(STORAGE_SETUP_MESSAGE)


def get_api_key_store() -> ApiKeyStore:
    if supabase_configured():
        return SupabaseApiKeyStore()
    creds = redis_credentials()
    if creds:
        return UpstashApiKeyStore(*creds)
    if os.getenv("VERCEL"):
        return UnconfiguredVercelApiKeyStore()
    return FileApiKeyStore()
