from __future__ import annotations

from typing import Any

import httpx

from claycomp.storage.config import STORAGE_SETUP_MESSAGE, supabase_credentials


class SupabaseError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.base = f"{url.rstrip('/')}/rest/v1"
        self.key = key

    @classmethod
    def from_env(cls) -> SupabaseClient:
        creds = supabase_credentials()
        if not creds:
            raise SupabaseError(STORAGE_SETUP_MESSAGE)
        return cls(*creds)

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def _request(self, method: str, table: str, *, prefer: str | None = None, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                method,
                f"{self.base}/{table}",
                headers=self._headers(prefer=prefer),
                **kwargs,
            )
        if resp.status_code >= 400:
            detail = resp.text
            if "does not exist" in detail or resp.status_code == 404:
                raise SupabaseError(STORAGE_SETUP_MESSAGE, status=resp.status_code)
            raise SupabaseError(detail or f"Supabase error {resp.status_code}", status=resp.status_code)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": columns}
        for key, value in (filters or {}).items():
            params[key] = value
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        result = await self._request("GET", table, params=params)
        return result or []

    async def upsert(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        result = await self._request(
            "POST",
            table,
            prefer="resolution=merge-duplicates,return=representation",
            json=row,
        )
        return result or []

    async def delete(self, table: str, *, filters: dict[str, str]) -> None:
        await self._request("DELETE", table, params=filters)
