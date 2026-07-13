from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from claycomp.models import Record

# Common Apollo / export column aliases → our schema
COLUMN_MAP = {
    "email": "email",
    "work_email": "email",
    "first_name": "first_name",
    "firstname": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "name": "full_name",
    "full_name": "full_name",
    "title": "title",
    "job_title": "title",
    "company": "company",
    "organization_name": "company",
    "company_name": "company",
    "city": "city",
    "state": "state",
    "country": "country",
    "location": "location",
    "linkedin_url": "linkedin_url",
    "person_linkedin_url": "linkedin_url",
}


def _normalize_col(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _record_id(row: dict, index: int) -> str:
    email = row.get("email") or row.get("work_email")
    if email:
        return hashlib.md5(str(email).lower().encode()).hexdigest()[:12]
    return f"row-{index}"


def load_csv(path: Path) -> list[Record]:
    df = pd.read_csv(path, dtype=str).fillna("")
    records: list[Record] = []

    for i, row in df.iterrows():
        mapped: dict[str, str] = {}
        raw = {str(k): ("" if pd.isna(v) else str(v)) for k, v in row.items()}

        for col, val in raw.items():
            norm = _normalize_col(col)
            field = COLUMN_MAP.get(norm)
            if field and val:
                mapped[field] = val

        records.append(
            Record(
                id=_record_id(raw, int(i)),
                raw=raw,
                **{k: v or None for k, v in mapped.items()},
            )
        )

    return records


def save_csv(records: list[Record], path: Path) -> None:
    rows: list[dict] = []
    enriched_keys: set[str] = set()

    for r in records:
        enriched_keys.update(r.enriched.keys())

    for r in records:
        row = {**r.raw}
        row["_id"] = r.id
        for key in sorted(enriched_keys):
            val = r.enriched.get(key, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row[f"enriched_{key}"] = val
        rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
