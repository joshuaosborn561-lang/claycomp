"""Structured table knowledge for Sculptor (chat + architect)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from claycomp.web.schemas import RecordDTO


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        email = value.get("email")
        if isinstance(email, str) and "@" in email:
            return True
        for key in ("value", "team", "name", "nickname", "snippet", "talking_point"):
            if _nonempty(value.get(key)):
                return True
        return False
    return bool(str(value).strip())


def _record_email(r: RecordDTO) -> str | None:
    if r.email and "@" in r.email:
        return r.email
    for key, val in (r.raw or {}).items():
        nk = str(key).lower().replace(" ", "_")
        if nk in {"email", "work_email", "corporate_email", "business_email"} and isinstance(val, str) and "@" in val:
            return val
    for key, val in (r.enriched or {}).items():
        if isinstance(val, dict):
            email = val.get("email")
            if isinstance(email, str) and "@" in email:
                return email
        elif isinstance(val, str) and "@" in val and "email" in str(key).lower():
            return val
    return None


def build_table_knowledge(
    records: list[RecordDTO],
    columns: list[dict],
    business_context: str | None = None,
) -> dict[str, Any]:
    n = len(records)
    if n == 0:
        return {
            "row_count": 0,
            "summary": "No leads loaded. Ask the user to import a CSV/Excel or load sample data.",
        }

    raw_headers: list[str] = []
    seen_headers: set[str] = set()
    for r in records:
        for key in (r.raw or {}).keys():
            if key not in seen_headers:
                seen_headers.add(key)
                raw_headers.append(str(key))

    field_counts = {
        "email": sum(1 for r in records if _record_email(r)),
        "first_name": sum(1 for r in records if _nonempty(r.first_name)),
        "last_name": sum(1 for r in records if _nonempty(r.last_name)),
        "company": sum(1 for r in records if _nonempty(r.company)),
        "title": sum(1 for r in records if _nonempty(r.title)),
        "location": sum(1 for r in records if _nonempty(r.location) or _nonempty(r.city) or _nonempty(r.state)),
        "linkedin_url": sum(1 for r in records if _nonempty(r.linkedin_url)),
    }
    completeness = {k: round(v / n * 100, 1) for k, v in field_counts.items()}

    companies = Counter(r.company for r in records if r.company).most_common(8)
    titles = Counter(r.title for r in records if r.title).most_common(8)
    states = Counter(r.state for r in records if r.state).most_common(8)

    enriched_filled: dict[str, int] = {}
    for r in records:
        for k, v in (r.enriched or {}).items():
            if k.endswith("_error"):
                continue
            if _nonempty(v):
                enriched_filled[k] = enriched_filled.get(k, 0) + 1

    configured = []
    for c in columns:
        configured.append({
            "label": c.get("label") or c.get("enricherKey") or "?",
            "enricher": c.get("enricherKey") or c.get("enricher_key"),
            "column_name": c.get("columnName") or c.get("column_name"),
            "has_prompt": bool(c.get("customPrompt") or c.get("custom_prompt")),
            "run_condition": c.get("runCondition") or c.get("run_condition") or {},
        })

    sample_rows = []
    for r in records[:12]:
        sample_rows.append({
            "id": r.id,
            "name": r.full_name or r.first_name or r.email or r.id,
            "title": r.title,
            "company": r.company,
            "email": _record_email(r),
            "location": r.location or ", ".join(p for p in [r.city, r.state] if p) or None,
            "linkedin": r.linkedin_url,
            "enriched_keys": [k for k, v in (r.enriched or {}).items() if _nonempty(v) and not k.endswith("_error")][:6],
        })

    missing_email = [
        (r.full_name or r.first_name or r.company or r.id)
        for r in records
        if not _record_email(r)
    ][:10]
    missing_location = [
        (r.full_name or r.first_name or r.email or r.id)
        for r in records
        if not (_nonempty(r.location) or _nonempty(r.city) or _nonempty(r.state))
    ][:10]

    return {
        "row_count": n,
        "raw_headers": raw_headers,
        "field_counts": field_counts,
        "completeness_pct": completeness,
        "top_companies": [{"name": c, "count": cnt} for c, cnt in companies],
        "top_titles": [{"title": t, "count": cnt} for t, cnt in titles],
        "top_states": [{"state": s, "count": cnt} for s, cnt in states],
        "enriched_fill_counts": enriched_filled,
        "configured_columns": configured,
        "sample_rows": sample_rows,
        "missing_email_examples": missing_email,
        "missing_location_examples": missing_location,
        "rows_missing_email": n - field_counts["email"],
        "rows_missing_location": n - field_counts["location"],
        "business_context": business_context or "",
        "outreach_ready_score": round(
            (
                completeness.get("first_name", 0)
                + completeness.get("company", 0)
                + completeness.get("location", 0)
                + completeness.get("email", 0)
            )
            / 4,
            1,
        ),
    }


def knowledge_to_prompt_block(kb: dict[str, Any]) -> str:
    if kb.get("row_count", 0) == 0:
        return kb.get("summary", "Empty table.")

    lines = [
        "=== TABLE KNOWLEDGE BASE (ground truth — use these numbers) ===",
        f"Rows: {kb['row_count']}",
        f"Outreach-ready score: {kb.get('outreach_ready_score', 0)}%",
        f"Source headers: {', '.join(kb.get('raw_headers') or []) or '(none)'}",
        f"Completeness %: {kb.get('completeness_pct')}",
        f"Rows missing email: {kb.get('rows_missing_email')}",
        f"Rows missing location: {kb.get('rows_missing_location')}",
    ]
    if kb.get("top_companies"):
        lines.append(
            "Top companies: "
            + ", ".join(f"{c['name']} ({c['count']})" for c in kb["top_companies"][:5])
        )
    if kb.get("top_titles"):
        lines.append(
            "Top titles: "
            + ", ".join(f"{t['title']} ({t['count']})" for t in kb["top_titles"][:5])
        )
    if kb.get("configured_columns"):
        lines.append("Configured enrichment columns:")
        for c in kb["configured_columns"]:
            cond = c.get("run_condition") or {}
            cond_bits = []
            if cond.get("skipIfOutputFilled") or cond.get("skip_if_output_filled"):
                cond_bits.append("skip-if-filled")
            src = cond.get("skipIfSourceFilled") or cond.get("skip_if_source_filled")
            if src:
                cond_bits.append(f"skip-if-{src}")
            lines.append(
                f"  - {c.get('label')} [{c.get('enricher')}]"
                + (f" ({', '.join(cond_bits)})" if cond_bits else "")
            )
    if kb.get("enriched_fill_counts"):
        lines.append(
            "Enriched field fills: "
            + ", ".join(f"{k}={v}" for k, v in list(kb["enriched_fill_counts"].items())[:8])
        )
    if kb.get("business_context"):
        lines.append(f"Business context:\n{kb['business_context']}")
    lines.append("Sample leads:")
    for row in kb.get("sample_rows") or []:
        bits = [
            str(row.get("name") or "?"),
            f"{row.get('title') or '?'} @ {row.get('company') or '?'}",
            row.get("location") or "?",
        ]
        if row.get("email"):
            bits.append(str(row["email"]))
        if row.get("enriched_keys"):
            bits.append("enriched:" + ",".join(row["enriched_keys"]))
        lines.append(f"- [{row.get('id')}] " + " · ".join(bits))
    if kb["row_count"] > len(kb.get("sample_rows") or []):
        lines.append(f"... +{kb['row_count'] - len(kb.get('sample_rows') or [])} more rows")
    lines.append("=== END KNOWLEDGE BASE ===")
    return "\n".join(lines)


def answer_table_query(question: str, kb: dict[str, Any]) -> dict[str, Any]:
    """Return factual slices of the KB tailored to a natural-language question."""
    q = (question or "").lower()
    facts: list[str] = []
    if kb.get("row_count", 0) == 0:
        return {"facts": ["The table is empty."], "knowledge": kb}

    facts.append(f"There are {kb['row_count']} rows in the table.")
    completeness = kb.get("completeness_pct") or {}
    facts.append(
        "Completeness — "
        + ", ".join(f"{k}: {v}%" for k, v in completeness.items())
    )

    if any(w in q for w in ("email", "waterfall", "contact")):
        facts.append(
            f"{kb.get('field_counts', {}).get('email', 0)} rows already have an email; "
            f"{kb.get('rows_missing_email', 0)} still need one."
        )
        if kb.get("missing_email_examples"):
            facts.append(
                "Examples missing email: " + ", ".join(map(str, kb["missing_email_examples"][:5]))
            )

    if any(w in q for w in ("location", "city", "state", "geo", "where")):
        facts.append(
            f"{kb.get('field_counts', {}).get('location', 0)} rows have location; "
            f"{kb.get('rows_missing_location', 0)} missing."
        )
        if kb.get("top_states"):
            facts.append(
                "Top states: "
                + ", ".join(f"{s['state']} ({s['count']})" for s in kb["top_states"][:5])
            )

    if any(w in q for w in ("company", "account", "employer")):
        if kb.get("top_companies"):
            facts.append(
                "Top companies: "
                + ", ".join(f"{c['name']} ({c['count']})" for c in kb["top_companies"][:5])
            )

    if any(w in q for w in ("title", "role", "job")):
        if kb.get("top_titles"):
            facts.append(
                "Top titles: "
                + ", ".join(f"{t['title']} ({t['count']})" for t in kb["top_titles"][:5])
            )

    if any(w in q for w in ("column", "enrich", "sculptor", "workflow", "prompt", "setting")):
        cols = kb.get("configured_columns") or []
        if not cols:
            facts.append("No enrichment columns are configured yet.")
        else:
            facts.append(
                "Configured columns: "
                + ", ".join(f"{c.get('label')} [{c.get('enricher')}]" for c in cols)
            )

    if any(w in q for w in ("prioritize", "priority", "who", "segment", "outreach")):
        facts.append(f"Outreach-ready score: {kb.get('outreach_ready_score')}%")
        if kb.get("top_titles"):
            facts.append(f"Largest title cluster: {kb['top_titles'][0]['title']}")
        if kb.get("top_companies"):
            facts.append(f"Largest company cluster: {kb['top_companies'][0]['name']}")

    return {
        "facts": facts,
        "knowledge_snapshot": {
            "row_count": kb.get("row_count"),
            "completeness_pct": completeness,
            "configured_columns": kb.get("configured_columns"),
            "top_companies": kb.get("top_companies"),
            "top_titles": kb.get("top_titles"),
            "rows_missing_email": kb.get("rows_missing_email"),
            "rows_missing_location": kb.get("rows_missing_location"),
        },
    }
