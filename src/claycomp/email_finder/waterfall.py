from __future__ import annotations

from typing import Any, Awaitable, Callable

from claycomp.email_finder import ai_ark, prospeo
from claycomp.email_finder.types import EmailFinderResult
from claycomp.models import Record

EMAIL_PROVIDERS: dict[str, Callable[[Record], Awaitable[EmailFinderResult]]] = {
    "ai_ark": ai_ark.find_email,
    "prospeo": prospeo.find_email,
}

# User always wants AI Ark available; keep it first by default.
DEFAULT_PROVIDERS = ["ai_ark", "prospeo"]


def normalize_providers(providers: list[str] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for key in providers or DEFAULT_PROVIDERS:
        k = (key or "").strip().lower()
        if k in EMAIL_PROVIDERS and k not in seen:
            ordered.append(k)
            seen.add(k)
    # Always include AI Ark somewhere in the waterfall (user requirement)
    if "ai_ark" not in seen:
        ordered.append("ai_ark")
    if not ordered:
        ordered = list(DEFAULT_PROVIDERS)
    return ordered


async def run_email_waterfall(
    record: Record,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    chain = normalize_providers(providers)
    attempts: list[dict[str, Any]] = []

    for key in chain:
        finder = EMAIL_PROVIDERS[key]
        result = await finder(record)
        attempts.append({
            "provider": result.provider,
            "status": result.status,
            "email": result.email,
            "verification": result.verification,
            "detail": result.detail,
        })
        if result.found:
            return {
                "email": result.email,
                "provider": result.provider,
                "verification": result.verification,
                "attempts": attempts,
                "talking_point": f"{result.email} via {result.provider}",
                "value": result.email,
            }

    return {
        "email": None,
        "provider": None,
        "verification": None,
        "attempts": attempts,
        "talking_point": "No email found",
        "value": None,
        "skip_reason": "all providers missed or skipped",
    }
