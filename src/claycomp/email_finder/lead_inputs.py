from __future__ import annotations

import re
from urllib.parse import urlparse

from claycomp.models import Record

DOMAIN_KEYS = (
    "website",
    "company_website",
    "company website",
    "domain",
    "company_domain",
    "company domain",
    "Company Website",
    "Website",
    "Domain",
)


def _raw_get(record: Record, *keys: str) -> str | None:
    lowered = {str(k).lower().replace(" ", "_"): v for k, v in record.raw.items()}
    for key in keys:
        val = record.raw.get(key) or lowered.get(key.lower().replace(" ", "_"))
        if val and str(val).strip():
            return str(val).strip()
    return None


def extract_domain(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if "@" in text and "://" not in text:
        text = text.split("@", 1)[1]
    if "://" not in text and not text.startswith("www."):
        # bare domain like acme.com
        candidate = text.lower().strip().strip("/")
        if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", candidate):
            return candidate.removeprefix("www.")
    if "://" not in text:
        text = "https://" + text
    try:
        host = urlparse(text).hostname or ""
    except Exception:
        return None
    host = host.lower().removeprefix("www.")
    return host or None


def lead_domain(record: Record) -> str | None:
    for key in DOMAIN_KEYS:
        domain = extract_domain(_raw_get(record, key))
        if domain:
            return domain
    if record.email and "@" in record.email:
        # Only use personal email domain if it looks corporate
        domain = extract_domain(record.email)
        free = {
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
            "aol.com", "protonmail.com", "mail.com", "live.com",
        }
        if domain and domain not in free:
            return domain
    # company field sometimes holds a domain
    return extract_domain(record.company)


def lead_linkedin(record: Record) -> str | None:
    url = record.linkedin_url or _raw_get(
        record,
        "linkedin_url",
        "linkedin",
        "person_linkedin_url",
        "LinkedIn",
        "Person Linkedin Url",
    )
    if not url:
        return None
    url = url.strip()
    if "linkedin.com" not in url.lower():
        return None
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def lead_names(record: Record) -> tuple[str | None, str | None, str | None]:
    first = record.first_name or _raw_get(record, "first_name", "First Name", "firstname")
    last = record.last_name or _raw_get(record, "last_name", "Last Name", "lastname")
    full = record.full_name or _raw_get(record, "full_name", "name", "Name", "Full Name")
    if not full:
        parts = [p for p in (first, last) if p]
        full = " ".join(parts) if parts else None
    if full and (not first or not last):
        bits = full.split()
        if len(bits) >= 2:
            first = first or bits[0]
            last = last or bits[-1]
    return first, last, full
