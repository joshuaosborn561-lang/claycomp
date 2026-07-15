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


EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
CSV_EXTENSIONS = {".csv", ".tsv", ".txt"}


def _extension(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def is_excel_filename(filename: str | None) -> bool:
    return _extension(filename) in EXCEL_EXTENSIONS


def sniff_table_format(data: bytes, filename: str | None = None) -> str:
    """Return 'csv', 'excel_xlsx', or 'excel_xls'."""
    ext = _extension(filename)
    if ext in CSV_EXTENSIONS:
        return "csv"
    if ext in {".xlsx", ".xlsm"}:
        return "excel_xlsx"
    if ext == ".xls":
        return "excel_xls"
    # Magic-byte fallback when the client omits/rewrites the filename.
    if data[:4] == b"PK\x03\x04":
        return "excel_xlsx"
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return "excel_xls"
    return "csv"


def _stringify_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Excel/CSV frames to all-string cells (empty instead of NaN)."""
    out = df.copy()
    out.columns = [str(c).strip() if c is not None else "" for c in out.columns]
    # Drop completely empty "Unnamed: N" columns Excel often invents.
    drop_cols = [
        c
        for c in out.columns
        if (not c or str(c).startswith("Unnamed")) and out[c].isna().all()
    ]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    out = out.fillna("")
    return out.astype(str).replace({"nan": "", "NaT": "", "None": "", "<NA>": ""})


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    return _stringify_df(
        pd.read_csv(io.BytesIO(data), dtype=str, encoding="utf-8-sig", keep_default_na=False)
    )


def read_excel_bytes(data: bytes, filename: str | None = None) -> pd.DataFrame:
    """Read the first sheet of an Excel workbook into a string DataFrame."""
    kind = sniff_table_format(data, filename)
    if kind == "csv":
        raise ValueError("File does not look like Excel (.xlsx / .xls)")

    bio = io.BytesIO(data)
    engine = "xlrd" if kind == "excel_xls" else "openpyxl"
    try:
        df = pd.read_excel(bio, dtype=str, keep_default_na=False, engine=engine)
    except ImportError as exc:
        needed = "xlrd" if engine == "xlrd" else "openpyxl"
        raise ValueError(
            f"Reading Excel requires the '{needed}' package. "
            f"Install it or re-save the file as CSV."
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface a clean API error
        raise ValueError(f"Could not read Excel file: {exc}") from exc

    if df.empty and len(df.columns) == 0:
        raise ValueError("Excel file has no rows or columns on the first sheet")
    return _stringify_df(df)


def read_table_bytes(data: bytes, filename: str | None = None) -> pd.DataFrame:
    """Read CSV or Excel uploads into a normalized DataFrame."""
    if not data:
        raise ValueError("Uploaded file is empty")
    kind = sniff_table_format(data, filename)
    if kind.startswith("excel"):
        return read_excel_bytes(data, filename=filename)
    try:
        return read_csv_bytes(data)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not read CSV file: {exc}") from exc


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    _stringify_df(df).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def table_bytes_to_csv_bytes(data: bytes, filename: str | None = None) -> bytes:
    """Digest CSV/Excel bytes and return UTF-8 CSV bytes."""
    return dataframe_to_csv_bytes(read_table_bytes(data, filename=filename))


def load_csv(path: Path) -> list[Record]:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    return dataframe_to_records(_stringify_df(df))


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
