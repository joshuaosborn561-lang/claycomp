from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from claycomp.storage.redis_config import redis_credentials


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TableStore(ABC):
    @abstractmethod
    async def list_tables(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_table(self, table_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def save_table(self, table: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    async def delete_table(self, table_id: str) -> bool:
        ...


class FileTableStore(TableStore):
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.getenv("CLAYCOMP_DATA_DIR", "./data/tables"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def _read_index(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text())

    def _write_index(self, items: list[dict]) -> None:
        self.index_path.write_text(json.dumps(items, indent=2))

    async def list_tables(self) -> list[dict[str, Any]]:
        return sorted(self._read_index(), key=lambda t: t.get("updated_at", ""), reverse=True)

    async def get_table(self, table_id: str) -> dict[str, Any] | None:
        path = self.root / f"{table_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    async def save_table(self, table: dict[str, Any]) -> dict[str, Any]:
        table_id = table.get("id") or str(uuid.uuid4())
        table["id"] = table_id
        table["updated_at"] = _now()
        if "created_at" not in table:
            table["created_at"] = table["updated_at"]

        (self.root / f"{table_id}.json").write_text(json.dumps(table))
        index = [t for t in self._read_index() if t.get("id") != table_id]
        index.append({
            "id": table_id,
            "name": table.get("name", "Untitled"),
            "row_count": len(table.get("records", [])),
            "updated_at": table["updated_at"],
            "created_at": table["created_at"],
        })
        self._write_index(index)
        return table

    async def delete_table(self, table_id: str) -> bool:
        path = self.root / f"{table_id}.json"
        if path.exists():
            path.unlink()
        index = [t for t in self._read_index() if t.get("id") != table_id]
        self._write_index(index)
        return True


class UpstashTableStore(TableStore):
    """Redis-backed storage via Upstash REST API (works on Vercel)."""

    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.prefix = "claycomp:table:"
        self.index_key = "claycomp:tables:index"

    async def _cmd(self, *args: str) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=list(args),
            )
            resp.raise_for_status()
            return resp.json().get("result")

    async def list_tables(self) -> list[dict[str, Any]]:
        raw = await self._cmd("GET", self.index_key)
        if not raw:
            return []
        return sorted(json.loads(raw), key=lambda t: t.get("updated_at", ""), reverse=True)

    async def get_table(self, table_id: str) -> dict[str, Any] | None:
        raw = await self._cmd("GET", f"{self.prefix}{table_id}")
        return json.loads(raw) if raw else None

    async def save_table(self, table: dict[str, Any]) -> dict[str, Any]:
        table_id = table.get("id") or str(uuid.uuid4())
        table["id"] = table_id
        table["updated_at"] = _now()
        if "created_at" not in table:
            table["created_at"] = table["updated_at"]

        await self._cmd("SET", f"{self.prefix}{table_id}", json.dumps(table))
        index = await self.list_tables()
        index = [t for t in index if t.get("id") != table_id]
        index.append({
            "id": table_id,
            "name": table.get("name", "Untitled"),
            "row_count": len(table.get("records", [])),
            "updated_at": table["updated_at"],
            "created_at": table["created_at"],
        })
        await self._cmd("SET", self.index_key, json.dumps(index))
        return table

    async def delete_table(self, table_id: str) -> bool:
        await self._cmd("DEL", f"{self.prefix}{table_id}")
        index = [t for t in await self.list_tables() if t.get("id") != table_id]
        await self._cmd("SET", self.index_key, json.dumps(index))
        return True


def get_table_store() -> TableStore:
    creds = redis_credentials()
    if creds:
        return UpstashTableStore(*creds)
    return FileTableStore()
