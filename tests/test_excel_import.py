"""Excel digest + CSV conversion tests."""

from __future__ import annotations

import io

import pandas as pd

from claycomp.io import dataframe_to_csv_bytes, read_table_bytes, table_bytes_to_csv_bytes
from claycomp.records import load_table_bytes


def _xlsx_bytes(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def test_read_excel_bytes_to_dataframe():
    data = _xlsx_bytes(
        [
            {"First Name": "Ada", "Email": "ada@example.com", "Company": "Analytical"},
            {"First Name": "Grace", "Email": "grace@example.com", "Company": "Navy"},
        ]
    )
    df = read_table_bytes(data, filename="leads.xlsx")
    assert list(df.columns) == ["First Name", "Email", "Company"]
    assert len(df) == 2
    assert df.iloc[0]["First Name"] == "Ada"


def test_excel_converts_to_csv_bytes():
    data = _xlsx_bytes(
        [
            {"first_name": "Ada", "email": "ada@example.com"},
            {"first_name": "Grace", "email": "grace@example.com"},
        ]
    )
    csv_bytes = table_bytes_to_csv_bytes(data, filename="people.xlsx")
    text = csv_bytes.decode("utf-8")
    assert "first_name,email" in text.replace("\r\n", "\n")
    assert "Ada,ada@example.com" in text
    assert "Grace,grace@example.com" in text


def test_load_table_bytes_maps_records():
    data = _xlsx_bytes(
        [
            {
                "First Name": "Ada",
                "Last Name": "Lovelace",
                "Email": "ada@analytical.com",
                "Company Name": "Analytical Engines",
            }
        ]
    )
    records = load_table_bytes(data, filename="apollo.xlsx")
    assert len(records) == 1
    assert records[0].first_name == "Ada"
    assert records[0].email == "ada@analytical.com"
    assert records[0].company == "Analytical Engines"
    assert records[0].raw["First Name"] == "Ada"


def test_csv_still_works_via_table_reader():
    csv = b"email,company\nhello@x.com,Acme\n"
    records = load_table_bytes(csv, filename="leads.csv")
    assert len(records) == 1
    assert records[0].email == "hello@x.com"


def test_dataframe_to_csv_bytes_roundtrip():
    df = pd.DataFrame([{"a": "1", "b": "two"}])
    out = dataframe_to_csv_bytes(df).decode()
    assert "a,b" in out
    assert "1,two" in out
