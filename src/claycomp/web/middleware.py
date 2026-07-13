from __future__ import annotations

import json
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from claycomp.keys import set_request_keys
from claycomp.storage.api_keys import get_api_key_store


class ApiKeysMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        stored = await get_api_key_store().get_keys()

        header_keys: dict[str, str] = {}
        raw = request.headers.get("x-claycomp-keys", "")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    header_keys = {k: str(v) for k, v in parsed.items() if v}
            except json.JSONDecodeError:
                pass

        merged = {**stored, **header_keys}
        set_request_keys(merged)
        return await call_next(request)
