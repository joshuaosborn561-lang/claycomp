from __future__ import annotations

import json
from typing import Any, AsyncIterator

from claycomp.enrichers import get_enricher
from claycomp.llm import LLMMessage, llm_stream
from claycomp.models import Record
from claycomp.web.schemas import ChatMessage, RecordDTO, dto_to_record, record_to_dto

CHAT_SYSTEM = """You are Claycomp, an AI assistant for lead enrichment and cold outreach personalization.

You help users enrich lead lists (from Apollo, ZoomInfo, etc.) with personalized data like:
- Normalized first names (Robert → Rob)
- Local area nicknames ("the Bay Area", "ATX")
- Nearest sports teams
- Top restaurants nearby
- Company Google reviews

When the user asks to enrich data, explain what you'll do clearly and concisely.
If they share lead data, reference specific people and locations in your answers.
Suggest practical email openers using the enrichment data.

Be warm, concise, and actionable. Use markdown sparingly for clarity."""


async def stream_chat(
    messages: list[ChatMessage],
    records: list[RecordDTO],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    context = _build_context(records)

    openai_messages = [
        LLMMessage(role="system", content=CHAT_SYSTEM + "\n\n" + context),
    ]
    for msg in messages:
        openai_messages.append(LLMMessage(role=msg.role, content=msg.content))

    last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    enricher_key = _detect_enricher_intent(last_user)
    if enricher_key and records:
        yield _sse({"type": "token", "content": f"Running **{enricher_key}** enrichment on {len(records)} leads...\n\n"})
        enricher = get_enricher(enricher_key, provider=provider, model=model)
        recs = [dto_to_record(r) for r in records]
        for i, rec in enumerate(recs):
            try:
                result = await enricher.enrich(rec)
                rec.set_enriched(enricher.output_column(), result.value)
                preview = _format_value(result.value)
                yield _sse({
                    "type": "enrichment",
                    "row_id": rec.id,
                    "column": enricher.output_column(),
                    "value": result.value,
                    "name": rec.display_name(),
                    "preview": preview,
                    "done": i + 1,
                    "total": len(recs),
                })
            except Exception as e:
                yield _sse({"type": "error", "error": str(e), "row_id": rec.id})

        yield _sse({"type": "records", "records": [record_to_dto(r).model_dump() for r in recs]})
        summary = _summarize_enrichment(enricher_key, recs)
        yield _sse({"type": "token", "content": summary})
        yield _sse({"type": "done"})
        return

    try:
        async for token in llm_stream(openai_messages, provider=provider, model=model, temperature=0.6):
            yield _sse({"type": "token", "content": token})
    except Exception as e:
        yield _sse({"type": "token", "content": f"Error: {e}. Check your API key in .env"})

    yield _sse({"type": "done"})


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _build_context(records: list[RecordDTO]) -> str:
    if not records:
        return "No leads loaded yet. The user can upload a CSV or load sample data."

    lines = [f"Loaded {len(records)} leads. Sample:"]
    for r in records[:5]:
        loc = r.location or ", ".join(p for p in [r.city, r.state] if p) or "unknown"
        lines.append(f"- {r.full_name or r.first_name or r.email}: {r.title or '?'} at {r.company or '?'}, {loc}")
        if r.enriched:
            for k, v in r.enriched.items():
                lines.append(f"  • {k}: {_format_value(v)}")
    if len(records) > 5:
        lines.append(f"...and {len(records) - 5} more")
    return "\n".join(lines)


def _detect_enricher_intent(text: str) -> str | None:
    lower = text.lower()
    triggers = {
        "baseball": ["baseball", "mlb"],
        "name": ["normalize name", "first name", "nickname"],
        "area": ["area", "location nickname", "colloquial"],
        "restaurant": ["restaurant", "food", "dining"],
        "review": ["google review", "rating", "reviews"],
    }
    if not any(w in lower for w in ["enrich", "run", "find", "get", "add column", "lookup"]):
        return None
    for key, words in triggers.items():
        if any(w in lower for w in words):
            return key
    return None


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        if "talking_point" in value:
            return str(value["talking_point"])
        if "nickname" in value:
            return str(value.get("how_to_reference") or value["nickname"])
        if "snippet" in value:
            return str(value["snippet"])
        if "team" in value:
            return str(value["team"])
        if "name" in value:
            return str(value["name"])
        return json.dumps(value)
    return str(value)


def _summarize_enrichment(key: str, records: list[Record]) -> str:
    lines = ["\n\n**Done!** Here's a sample opener you could use:\n"]
    for rec in records[:2]:
        name = rec.enriched.get("normalized_first_name") or rec.first_name or "there"
        parts = []
        for col, val in rec.enriched.items():
            if col.endswith("_error"):
                continue
            formatted = _format_value(val)
            if formatted and formatted != "—":
                parts.append(formatted)
        if parts:
            lines.append(f'> Hey {name} — noticed you\'re {" / ".join(parts[:2])}. Worth a quick chat?')
    lines.append("\nSwitch to **Table** mode to see all enriched columns, or ask me to run another enrichment.")
    return "\n".join(lines)
