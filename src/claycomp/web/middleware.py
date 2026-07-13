from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from claycomp.keys import bind_api_keys


class ApiKeysMiddleware:
    """Pure ASGI middleware — BaseHTTPMiddleware breaks ContextVar during streaming."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            header_raw = ""
            for name, value in scope.get("headers", []):
                if name.lower() == b"x-claycomp-keys":
                    header_raw = value.decode("latin-1")
                    break
            await bind_api_keys(header_raw)
        await self.app(scope, receive, send)
