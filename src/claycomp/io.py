from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from claycomp.models import Record

# Common Apollo / export column aliases → our schema
COLUMN_MAP = {
    "email": "email",
    "work_email": "email",
    "corporate_email": "email",
    "business_email": "email",
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
    "organization": "company",
    "city": "city",
    "state": "state",
    "country": "country",
    "location": "location",
    "linkedin_url": "linkedin_url",
    "person_linkedin_url": "linkedin_url",
    "linkedin": "linkedin_url",
}


def _normalize_col(name: str) -> str:
    return name.strip().lstrip("\ufeff").lower().replace(" ", "_")


def _identity_from_row(row: dict) -> str | None:
    """Best stable identifier from raw CSV columns (handles Apollo header casing)."""
    email: str | None = None
    linkedin: str | None = None
    for col, val in row.items():
        if not val:
            continue
        norm = _normalize_col(str(col))
        text = str(val).strip()
        if norm in ("email", "work_email", "corporate_email", "business_email") and not email:
            email = text.lower()
        elif norm in ("linkedin_url", "person_linkedin_url", "linkedin") and not linkedin:
            linkedin = text.lower()
    return email or linkedin


def _record_id(row: dict, index: int) -> str:
    """Unique per row — index suffix prevents duplicate-email collisions in the UI."""
    identity = _identity_from_row(row)
    basis = identity or "|".join(str(v) for v in row.values() if v) or f"row-{index}"
    return hashlib.md5(f"{basis}:{index}".encode()).hexdigest()[:12]


def dataframe_to_records(df: pd.DataFrame) -> list[Record]:
    df = df.fillna("")
    records: list[Record] = []

    for index, (_, row) in enumerate(df.iterrows()):
        mapped: dict[str, str] = {}
        raw = {str(k): ("" if pd.isna(v) else str(v)) for k, v in row.items()}

        for col, val in raw.items():
            norm = _normalize_col(col)
            field = COLUMN_MAP.get(norm)
            if field and val:
                mapped[field] = str(val)

        records.append(
            Record(
                id=_record_id(raw, index),
                raw=raw,
                **{k: v or None for k, v in mapped.items()},
            )
        )

    return records


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data), dtype=str, encoding="utf-8-sig", keep_default_na=False)


def load_csv(path: Path) -> list[Record]:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    return dataframe_to_records(df)


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
