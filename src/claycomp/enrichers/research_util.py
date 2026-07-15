from __future__ import annotations

import json
import re
from typing import Any

from claycomp.models import Record


def lead_context(record: Record) -> dict[str, Any]:
    return {
        "name": record.display_name(),
        "email": record.email,
        "title": record.title,
        "company": record.company,
        "location": record.display_location(),
        "linkedin_url": record.linkedin_url,
        "raw": {k: v for k, v in list(record.raw.items())[:20] if v},
        "enriched": {
            k: v
            for k, v in record.enriched.items()
            if not str(k).endswith("_error")
        },
    }


def parse_json_object(content: str | None) -> dict[str, Any]:
    if not content:
        return {}
    text = content.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def enriched_field(record: Record, *keys: str) -> Any:
    for key in keys:
        if key in record.enriched:
            return record.enriched[key]
        for existing, value in record.enriched.items():
            if str(existing).lower() == key.lower():
                return value
    return None
