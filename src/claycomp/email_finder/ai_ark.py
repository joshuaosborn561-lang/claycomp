"""AI Ark email finder.

Clay often mishandles AI Ark by treating the async trackId email-finder as if it were
synchronous. For per-row enrichment we use the documented real-time path:

  POST /v1/people/export/single
    - LinkedIn URL → { "url": "https://linkedin.com/in/..." }
    - AI Ark person id → { "id": "..." }

When we only have name + domain, we first resolve a person id via People Search
(`/v1/people`), then call export/single with that id. We intentionally do NOT use
`/v1/people/email-finder` (trackId one-shot async) for table waterfall cells.
"""

from __future__ import annotations

from typing import Any

import httpx

from claycomp.email_finder.lead_inputs import lead_domain, lead_linkedin, lead_names
from claycomp.email_finder.types import EmailFinderResult
from claycomp.keys import get_api_key
from claycomp.models import Record

BASE = "https://api.ai-ark.com/api/developer-portal"
PROVIDER = "ai_ark"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "X-TOKEN": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _pick_email(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    email_block = payload.get("email") or {}
    outputs = email_block.get("output") or []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        if item.get("found") is False:
            continue
        address = item.get("address")
        status = str(item.get("status") or "").upper()
        if address and status in ("", "VALID", "CATCH_ALL", "CATCHALL"):
            return str(address), status or "VALID"
        if address and item.get("found") is True:
            return str(address), status or "FOUND"
    # Some payloads may flatten email
    flat = payload.get("email")
    if isinstance(flat, str) and "@" in flat:
        return flat, "VALID"
    return None, None


async def _export_single(client: httpx.AsyncClient, api_key: str, body: dict[str, str]) -> EmailFinderResult:
    res = await client.post(f"{BASE}/v1/people/export/single", headers=_headers(api_key), json=body, timeout=60)
    if res.status_code == 404:
        return EmailFinderResult(email=None, provider=PROVIDER, status="miss", detail="no email found")
    if res.status_code >= 400:
        detail = res.text[:300]
        try:
            detail = str(res.json().get("error") or detail)
        except Exception:
            pass
        return EmailFinderResult(email=None, provider=PROVIDER, status="error", detail=detail, raw={"status": res.status_code})

    data = res.json()
    email, verification = _pick_email(data if isinstance(data, dict) else {})
    if email:
        return EmailFinderResult(
            email=email,
            provider=PROVIDER,
            status="found",
            verification=verification,
            detail="export/single",
            raw={"id": data.get("id"), "linkedin": (data.get("link") or {}).get("linkedin")},
        )
    return EmailFinderResult(email=None, provider=PROVIDER, status="miss", detail="response missing email", raw=data)


async def _search_person_id(
    client: httpx.AsyncClient,
    api_key: str,
    *,
    full_name: str,
    domain: str,
) -> str | None:
    """Resolve an AI Ark person id from name + domain. Size=1 for waterfall use."""
    payload = {
        "page": 0,
        "size": 1,
        "account": {
            "domain": {
                "any": {
                    "include": [domain],
                }
            }
        },
        "contact": {
            "fullName": {
                "any": {
                    "include": {
                        "mode": "SMART",
                        "content": [full_name],
                    }
                }
            }
        },
    }
    res = await client.post(f"{BASE}/v1/people", headers=_headers(api_key), json=payload, timeout=45)
    if res.status_code >= 400:
        return None
    data = res.json()
    content = data.get("content") or data.get("data") or []
    if isinstance(content, dict):
        content = content.get("content") or []
    if not content:
        return None
    first = content[0]
    person_id = first.get("id") if isinstance(first, dict) else None
    return str(person_id) if person_id else None


async def find_email(record: Record) -> EmailFinderResult:
    api_key = get_api_key("AI_ARK_API_KEY")
    if not api_key:
        return EmailFinderResult(email=None, provider=PROVIDER, status="skipped", detail="AI_ARK_API_KEY not set")

    linkedin = lead_linkedin(record)
    first, last, full = lead_names(record)
    domain = lead_domain(record)

    async with httpx.AsyncClient() as client:
        # Preferred: LinkedIn URL → real-time export/single (sync)
        if linkedin:
            return await _export_single(client, api_key, {"url": linkedin})

        # Fallback: People Search → person id → export/single (still sync; avoid trackId async)
        if full and domain:
            person_id = await _search_person_id(client, api_key, full_name=full, domain=domain)
            if not person_id:
                return EmailFinderResult(
                    email=None,
                    provider=PROVIDER,
                    status="miss",
                    detail=f"no people search match for {full} @ {domain}",
                )
            return await _export_single(client, api_key, {"id": person_id})

        missing = []
        if not linkedin:
            missing.append("linkedin_url")
        if not full:
            missing.append("name")
        if not domain:
            missing.append("company domain/website")
        return EmailFinderResult(
            email=None,
            provider=PROVIDER,
            status="skipped",
            detail="need LinkedIn URL, or name + company domain — missing: " + ", ".join(missing),
        )
