from __future__ import annotations

from collections import Counter
from typing import Any

from claycomp.web.schemas import RecordDTO


def analyze_table(records: list[RecordDTO], columns: list[dict]) -> dict[str, Any]:
    if not records:
        return {"error": "No records loaded", "row_count": 0}

    n = len(records)
    fields = {
        "email": sum(1 for r in records if r.email),
        "first_name": sum(1 for r in records if r.first_name),
        "company": sum(1 for r in records if r.company),
        "title": sum(1 for r in records if r.title),
        "location": sum(1 for r in records if r.city or r.state or r.location),
    }
    completeness = {k: round(v / n * 100, 1) for k, v in fields.items()}

    companies = Counter(r.company for r in records if r.company).most_common(5)
    titles = Counter(r.title for r in records if r.title).most_common(5)
    states = Counter(r.state for r in records if r.state).most_common(5)

    enriched_cols: set[str] = set()
    error_cols: list[str] = []
    for r in records:
        for k in r.enriched:
            if k.endswith("_error"):
                error_cols.append(k)
            else:
                enriched_cols.add(k)

    missing_location = [r.first_name or r.email or r.id for r in records if not (r.city or r.state or r.location)][:5]

    return {
        "row_count": n,
        "completeness_pct": completeness,
        "top_companies": [{"name": c, "count": cnt} for c, cnt in companies],
        "top_titles": [{"title": t, "count": cnt} for t, cnt in titles],
        "top_states": [{"state": s, "count": cnt} for s, cnt in states],
        "enrichment_columns": list(enriched_cols),
        "configured_columns": [c.get("label", c.get("enricherKey")) for c in columns],
        "enrichment_errors": len(error_cols),
        "rows_missing_location": missing_location,
        "outreach_ready_score": round(
            (completeness.get("first_name", 0) + completeness.get("company", 0) + completeness.get("location", 0)) / 3,
            1,
        ),
    }


def estimate_credits(records: list[RecordDTO], column_count: int = 1) -> dict[str, Any]:
    rows = len(records)
    # Rough estimate: ~1 credit per AI cell (Clay-like messaging)
    ai_cells = rows * column_count
    return {
        "rows": rows,
        "columns": column_count,
        "estimated_ai_calls": ai_cells,
        "sandbox_cost": min(3, rows) * column_count,
        "note": "Sandbox uses 3 rows. Non-AI enrichers (baseball) are free.",
    }
