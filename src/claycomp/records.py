from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from claycomp.io import COLUMN_MAP, _normalize_col, _record_id, load_csv
from claycomp.models import Record

__all__ = ["load_csv", "load_csv_bytes", "records_to_dicts", "records_from_dicts", "records_to_csv_bytes"]


def load_csv_bytes(data: bytes) -> list[Record]:
  df = pd.read_csv(io.BytesIO(data), dtype=str).fillna("")
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


def load_sample() -> list[Record]:
  sample_path = Path(__file__).parent / "data" / "sample_leads.csv"
  return load_csv(sample_path)


def records_to_dicts(records: list[Record]) -> list[dict]:
  return [r.model_dump() for r in records]


def records_from_dicts(data: list[dict]) -> list[Record]:
  return [Record.model_validate(item) for item in data]


def records_to_csv_bytes(records: list[Record]) -> bytes:
  import json

  rows: list[dict] = []
  enriched_keys: set[str] = set()
  for r in records:
    enriched_keys.update(r.enriched.keys())

  for r in records:
    row = {**r.raw, "_id": r.id}
    for key in sorted(enriched_keys):
      val = r.enriched.get(key, "")
      if isinstance(val, (dict, list)):
        val = json.dumps(val)
      row[f"enriched_{key}"] = val
    rows.append(row)

  buf = io.StringIO()
  pd.DataFrame(rows).to_csv(buf, index=False)
  return buf.getvalue().encode()
