from __future__ import annotations

import json
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from claycomp.keys import set_request_keys


class ApiKeysMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        raw = request.headers.get("x-claycomp-keys", "")
        keys: dict[str, str] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    keys = {k: str(v) for k, v in parsed.items() if v}
            except json.JSONDecodeError:
                pass
        set_request_keys(keys)
        return await call_next(request)
