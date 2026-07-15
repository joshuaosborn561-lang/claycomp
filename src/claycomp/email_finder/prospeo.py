"""Prospeo email finder via Enrich Person API.

Docs: https://prospeo.io/api-docs/enrich-person
Auth header: X-KEY
"""

from __future__ import annotations

import httpx

from claycomp.email_finder.lead_inputs import lead_domain, lead_linkedin, lead_names
from claycomp.email_finder.types import EmailFinderResult
from claycomp.keys import get_api_key
from claycomp.models import Record

URL = "https://api.prospeo.io/enrich-person"
PROVIDER = "prospeo"


async def find_email(record: Record) -> EmailFinderResult:
    api_key = get_api_key("PROSPEO_API_KEY")
    if not api_key:
        return EmailFinderResult(email=None, provider=PROVIDER, status="skipped", detail="PROSPEO_API_KEY not set")

    first, last, full = lead_names(record)
    domain = lead_domain(record)
    linkedin = lead_linkedin(record)
    company = record.company

    data: dict = {}
    if linkedin:
        data["linkedin_url"] = linkedin
    if first:
        data["first_name"] = first
    if last:
        data["last_name"] = last
    if full and not (first and last):
        data["full_name"] = full
    if domain:
        data["company_website"] = domain
    if company:
        data["company_name"] = company

    # Minimum matching requirements from Prospeo docs
    has_linkedin = bool(data.get("linkedin_url"))
    has_name_company = bool(
        ((data.get("first_name") and data.get("last_name")) or data.get("full_name"))
        and (data.get("company_website") or data.get("company_name") or data.get("company_linkedin_url"))
    )
    if not has_linkedin and not has_name_company:
        return EmailFinderResult(
            email=None,
            provider=PROVIDER,
            status="skipped",
            detail="need LinkedIn URL, or name + company website/name",
        )

    payload = {
        "only_verified_email": True,
        "enrich_mobile": False,
        "data": data,
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            URL,
            headers={"X-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )

    try:
        body = res.json()
    except Exception:
        body = {"raw": res.text[:300]}

    if res.status_code == 400 and isinstance(body, dict) and body.get("error_code") == "NO_MATCH":
        return EmailFinderResult(email=None, provider=PROVIDER, status="miss", detail="NO_MATCH", raw=body)

    if res.status_code >= 400 or (isinstance(body, dict) and body.get("error") is True):
        detail = None
        if isinstance(body, dict):
            detail = body.get("error_code") or body.get("message") or str(body)[:200]
        return EmailFinderResult(
            email=None,
            provider=PROVIDER,
            status="error",
            detail=detail or f"HTTP {res.status_code}",
            raw=body if isinstance(body, dict) else {},
        )

    person = (body or {}).get("person") or {}
    email_obj = person.get("email") or {}
    email = email_obj.get("email") if isinstance(email_obj, dict) else None
    status = email_obj.get("status") if isinstance(email_obj, dict) else None
    if email:
        return EmailFinderResult(
            email=str(email),
            provider=PROVIDER,
            status="found",
            verification=str(status) if status else "VERIFIED",
            detail="enrich-person",
            raw={"person_id": person.get("person_id")},
        )
    return EmailFinderResult(email=None, provider=PROVIDER, status="miss", detail="no email in response", raw=body)
