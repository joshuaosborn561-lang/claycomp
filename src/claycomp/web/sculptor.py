from __future__ import annotations

import json
from typing import Any, AsyncIterator

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.llm import LLMMessage, llm_complete, llm_stream
from claycomp.web.schemas import ChatMessage, RecordDTO, dto_to_record

SCULPTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_column",
            "description": "Propose a new enrichment column for the table",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string", "description": "Snake_case column name"},
                    "label": {"type": "string", "description": "Human-readable label"},
                    "enricher_key": {
                        "type": "string",
                        "enum": list(ENRICHERS.keys()) + ["custom"],
                        "description": "Built-in enricher or 'custom' for AI prompt",
                    },
                    "custom_prompt": {
                        "type": "string",
                        "description": "Prompt for custom enricher (required if enricher_key is custom)",
                    },
                    "reasoning": {"type": "string", "description": "Why this column helps outreach"},
                },
                "required": ["column_name", "label", "enricher_key", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_columns",
            "description": "Recommend multiple enrichment columns based on table data",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "enricher_key": {"type": "string"},
                                "label": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["recommendations"],
            },
        },
    },
]

SCULPTOR_SYSTEM = """You are Sculptor — Claycomp's GTM co-pilot for lead enrichment tables.

You help users build enrichment workflows using natural language. You can:
- Recommend enrichment columns based on what's in their table
- Propose new AI columns with custom prompts
- Explain how to personalize cold outreach
- Suggest sandbox testing before running on full table

Available built-in enrichers:
- name: normalize first names (Robert → Rob)
- area: conversational location nicknames ("the Bay Area")
- baseball: nearest MLB team
- restaurant: top-rated nearby restaurant (needs Google API)
- review: company Google rating (needs Google API)
- custom: your own AI prompt per row

When proposing columns, use propose_column or recommend_columns tools.
Be concise, practical, and outreach-focused. Reference actual data from their table."""


def _table_context(records: list[RecordDTO], columns: list[dict]) -> str:
    lines = [f"Table: {len(records)} rows"]

    if columns:
        lines.append("Existing enrichment columns: " + ", ".join(c.get("label", c.get("enricherKey", "?")) for c in columns))

    lines.append("\nSample rows:")
    for r in records[:5]:
        loc = r.location or ", ".join(p for p in [r.city, r.state] if p) or "?"
        lines.append(f"- {r.first_name or r.full_name or r.email}: {r.title or '?'} @ {r.company or '?'}, {loc}")
        if r.enriched:
            for k, v in list(r.enriched.items())[:3]:
                lines.append(f"    {k}: {v}")

    cols_present = set()
    for r in records:
        if r.city or r.state:
            cols_present.add("location")
        if r.first_name:
            cols_present.add("first_name")
        if r.company:
            cols_present.add("company")

    lines.append(f"\nData available: {', '.join(sorted(cols_present)) or 'minimal'}")
    return "\n".join(lines)


async def stream_sculptor(
    messages: list[ChatMessage],
    records: list[RecordDTO],
    columns: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    context = _table_context(records, columns)

    openai_messages = [
        LLMMessage(role="system", content=SCULPTOR_SYSTEM + "\n\n" + context),
    ]
    for m in messages:
        openai_messages.append(LLMMessage(role=m.role, content=m.content))

    try:
        result = await llm_complete(
            openai_messages,
            provider=provider,
            model=model,
            temperature=0.5,
            tools=SCULPTOR_TOOLS,
        )
    except Exception as e:
        yield _sse({"type": "token", "content": f"Error: {e}"})
        yield _sse({"type": "done"})
        return

    if result.tool_calls:
        for call in result.tool_calls:
            if call.name == "propose_column":
                yield _sse({"type": "proposal", "proposal": call.arguments})
                summary = (
                    f"\n\n**Proposed column:** `{call.arguments.get('label')}`\n"
                    f"_{call.arguments.get('reasoning', '')}_\n\n"
                    f"Use **Sandbox** to test on 3 rows, then **Apply** to add to your table."
                )
                yield _sse({"type": "token", "content": summary})
            elif call.name == "recommend_columns":
                recs = call.arguments.get("recommendations", [])
                yield _sse({"type": "recommendations", "recommendations": recs})
                lines = ["\n\n**Recommended enrichments:**\n"]
                for r in recs:
                    lines.append(f"- **{r.get('label', r.get('enricher_key'))}** — {r.get('reason', '')}")
                lines.append("\nClick any recommendation to add it, or ask me to customize.")
                yield _sse({"type": "token", "content": "\n".join(lines)})
    elif result.content:
        yield _sse({"type": "token", "content": result.content})

    yield _sse({"type": "done"})


async def stream_sculptor_chat_fallback(
    messages: list[ChatMessage],
    records: list[RecordDTO],
    columns: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Streaming variant for providers without tool support."""
    context = _table_context(records, columns)
    openai_messages = [
        LLMMessage(role="system", content=SCULPTOR_SYSTEM + "\n\n" + context),
    ]
    for m in messages:
        openai_messages.append(LLMMessage(role=m.role, content=m.content))

    try:
        async for token in llm_stream(openai_messages, provider=provider, model=model, temperature=0.5):
            yield _sse({"type": "token", "content": token})
    except Exception as e:
        yield _sse({"type": "token", "content": f"Error: {e}"})

    yield _sse({"type": "done"})


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
