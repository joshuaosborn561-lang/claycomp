from __future__ import annotations

import json
from typing import Any, AsyncIterator

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.llm import LLMMessage, llm_complete, llm_stream
from claycomp.llm.errors import format_llm_error
from claycomp.web.sculptor_analytics import analyze_table, estimate_credits
from claycomp.web.schemas import ChatMessage, RecordDTO, dto_to_record, record_to_dto

ENRICHERS_DOC = "\n".join(
    f"- {k}: {cls().description}" for k, cls in ENRICHERS.items()
) + "\n- custom: your own AI prompt per row"

SCULPTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_column",
            "description": "Propose a new enrichment column with config",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string"},
                    "label": {"type": "string"},
                    "enricher_key": {"type": "string", "enum": list(ENRICHERS.keys()) + ["custom"]},
                    "custom_prompt": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": ["column_name", "label", "enricher_key", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_columns",
            "description": "Recommend multiple enrichment columns for this table",
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
                                "column_name": {"type": "string"},
                                "custom_prompt": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["enricher_key", "label", "reason"],
                        },
                    },
                },
                "required": ["recommendations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_workflow",
            "description": "Propose an ordered multi-step enrichment workflow",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "enricher_key": {"type": "string"},
                                "label": {"type": "string"},
                                "column_name": {"type": "string"},
                                "custom_prompt": {"type": "string"},
                            },
                        },
                    },
                    "reasoning": {"type": "string"},
                },
                "required": ["name", "steps", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_table",
            "description": "Analyst mode: compute patterns, completeness, and insights from table data",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "What to focus on: outreach, geography, titles, completeness, etc.",
                    },
                    "insights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-5 actionable insights based on the analysis",
                    },
                    "priority_segment": {
                        "type": "string",
                        "description": "Who to prioritize for outreach and why",
                    },
                },
                "required": ["insights"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_outreach",
            "description": "Draft personalized cold email openers for specific leads",
            "parameters": {
                "type": "object",
                "properties": {
                    "drafts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lead_name": {"type": "string"},
                                "lead_id": {"type": "string"},
                                "subject": {"type": "string"},
                                "opener": {"type": "string"},
                                "full_email": {"type": "string"},
                            },
                            "required": ["lead_name", "opener"],
                        },
                    },
                },
                "required": ["drafts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sandbox",
            "description": "Run an enrichment in sandbox mode on first 3 rows (safe preview)",
            "parameters": {
                "type": "object",
                "properties": {
                    "enricher_key": {"type": "string"},
                    "column_name": {"type": "string"},
                    "custom_prompt": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["enricher_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_table",
            "description": "Troubleshoot enrichment issues, missing data, and configuration problems",
            "parameters": {
                "type": "object",
                "properties": {
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {"type": "string", "enum": ["error", "warning", "info"]},
                                "issue": {"type": "string"},
                                "fix": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["issues"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_cost",
            "description": "Estimate AI usage for a planned enrichment",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_count": {"type": "integer"},
                    "summary": {"type": "string"},
                },
                "required": ["column_count", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_column_prompt",
            "description": "Suggest an improved prompt or config for an existing custom column",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_label": {"type": "string"},
                    "improved_prompt": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": ["column_label", "improved_prompt", "reasoning"],
            },
        },
    },
]

SCULPTOR_SYSTEM = f"""You are Sculptor — Clay's GTM co-pilot, rebuilt for Claycomp lead tables.

You can do everything Clay Sculptor does for table workflows:

**List & table building**
- Recommend enrichments based on table data
- Propose single columns or full multi-step workflows
- Configure custom AI prompts (Claygent-style)

**Analyst mode**
- Query the table: patterns, segments, who to prioritize
- Use analyze_table with real insights from the data

**Enrichment ops**
- propose_column / recommend_columns / propose_workflow
- execute_sandbox to preview on 3 rows before going live (always prefer sandbox first)
- diagnose_table when user has errors or missing data
- estimate_cost before large runs

**Outreach**
- draft_outreach: personalized email openers using enrichments + lead data
- Reference actual names, companies, locations from the table

**Formulas & config**
- edit_column_prompt to refine AI column prompts

Built-in enrichers:
{ENRICHERS_DOC}

Rules:
- Always reference actual table data (names, companies, locations)
- Prefer sandbox before full runs
- Use tools proactively — don't just describe what to do, DO it via tools
- Be concise and actionable like Clay Sculptor
- If business context is provided, tailor all recommendations to it"""


def _table_context(records: list[RecordDTO], columns: list[dict], business_context: str | None) -> str:
    stats = analyze_table(records, columns)
    lines = [
        f"Table: {stats['row_count']} rows",
        f"Outreach-ready score: {stats.get('outreach_ready_score', 0)}%",
        f"Field completeness: {json.dumps(stats.get('completeness_pct', {}))}",
    ]
    if columns:
        lines.append("Configured columns: " + ", ".join(c.get("label", "?") for c in columns))
    if stats.get("enrichment_columns"):
        lines.append("Enriched fields: " + ", ".join(stats["enrichment_columns"]))
    if business_context:
        lines.append(f"\nBusiness context:\n{business_context}")
    lines.append("\nLeads:")
    for r in records[:8]:
        loc = r.location or ", ".join(p for p in [r.city, r.state] if p) or "?"
        name = r.full_name or r.first_name or r.email or r.id
        line = f"- [{r.id}] {name}: {r.title or '?'} @ {r.company or '?'}, {loc}"
        if r.enriched:
            previews = [f"{k}={v}" for k, v in list(r.enriched.items())[:4] if not k.endswith("_error")]
            if previews:
                line += " | " + "; ".join(previews)
        lines.append(line)
    if len(records) > 8:
        lines.append(f"... +{len(records) - 8} more rows")
    return "\n".join(lines)


async def _run_sandbox_enrichment(
    records: list[RecordDTO],
    args: dict,
    *,
    provider: str | None,
    model: str | None,
) -> list[RecordDTO]:
    enricher = get_enricher(
        args.get("enricher_key", "custom"),
        provider=provider,
        model=model,
        custom_prompt=args.get("custom_prompt"),
        column_name=args.get("column_name") or args.get("label") or "custom_field",
    )
    recs = [dto_to_record(r) for r in records]
    targets = recs[:3]
    for rec in targets:
        try:
            result = await enricher.enrich(rec)
            rec.set_enriched(enricher.output_column(), result.value)
        except Exception as e:
            rec.set_enriched(enricher.output_column(), None)
            rec.set_enriched(f"{enricher.output_column()}_error", str(e))
    return [record_to_dto(r) for r in recs]


async def _handle_tool(
    name: str,
    args: dict,
    *,
    records: list[RecordDTO],
    columns: list[dict],
    provider: str | None,
    model: str | None,
) -> AsyncIterator[dict]:
    if name == "propose_column":
        yield {"type": "proposal", "proposal": args}
    elif name == "recommend_columns":
        yield {"type": "recommendations", "recommendations": args.get("recommendations", [])}
        for rec in args.get("recommendations", []):
            yield {"type": "proposal", "proposal": {
                "column_name": rec.get("column_name") or rec.get("enricher_key"),
                "label": rec.get("label"),
                "enricher_key": rec.get("enricher_key"),
                "custom_prompt": rec.get("custom_prompt"),
                "reasoning": rec.get("reason"),
            }}
    elif name == "propose_workflow":
        yield {"type": "workflow", "workflow": args}
    elif name == "analyze_table":
        stats = analyze_table(records, columns)
        yield {"type": "analysis", "stats": stats, "insights": args}
    elif name == "draft_outreach":
        yield {"type": "drafts", "drafts": args.get("drafts", [])}
    elif name == "execute_sandbox":
        updated = await _run_sandbox_enrichment(records, args, provider=provider, model=model)
        yield {"type": "records", "records": [r.model_dump() for r in updated]}
        yield {"type": "sandbox_complete", "label": args.get("label") or args.get("enricher_key")}
    elif name == "diagnose_table":
        stats = analyze_table(records, columns)
        yield {"type": "diagnosis", "stats": stats, "issues": args.get("issues", [])}
    elif name == "estimate_cost":
        est = estimate_credits(records, args.get("column_count", 1))
        yield {"type": "cost_estimate", "estimate": est, "summary": args.get("summary", "")}
    elif name == "edit_column_prompt":
        yield {"type": "edit_prompt", "edit": args}


async def stream_sculptor(
    messages: list[ChatMessage],
    records: list[RecordDTO],
    columns: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    business_context: str | None = None,
) -> AsyncIterator[str]:
    context = _table_context(records, columns, business_context)
    llm_messages = [LLMMessage(role="system", content=SCULPTOR_SYSTEM + "\n\n" + context)]
    for m in messages:
        llm_messages.append(LLMMessage(role=m.role, content=m.content))

    use_tools = (provider or "openai") == "openai"

    if not use_tools:
        async for event in _stream_without_tools(
            llm_messages, records, columns, provider=provider, model=model, business_context=business_context
        ):
            yield event
        return

    for _ in range(6):
        try:
            result = await llm_complete(
                llm_messages,
                provider=provider,
                model=model,
                temperature=0.5,
                tools=SCULPTOR_TOOLS,
            )
        except Exception as e:
            yield _sse({"type": "token", "content": format_llm_error(e, provider=provider)})
            yield _sse({"type": "done"})
            return

        if result.tool_calls:
            executed: list[str] = []
            for call in result.tool_calls:
                executed.append(call.name)
                async for payload in _handle_tool(
                    call.name, call.arguments,
                    records=records, columns=columns, provider=provider, model=model,
                ):
                    yield _sse(payload)
                    if payload.get("type") == "records":
                        records = [RecordDTO.model_validate(r) for r in payload["records"]]
            llm_messages.append(LLMMessage(
                role="user",
                content=f"(Tools executed: {', '.join(executed)}. Summarize results for the user in 2-3 sentences.)",
            ))
            continue

        if result.content:
            yield _sse({"type": "token", "content": result.content})
        break

    yield _sse({"type": "done"})


async def _stream_without_tools(
    llm_messages: list[LLMMessage],
    records: list[RecordDTO],
    columns: list[dict],
    *,
    provider: str | None,
    model: str | None,
    business_context: str | None,
) -> AsyncIterator[str]:
    extra = "\n\nWhen you want to propose columns, include JSON in a fenced block:\n```sculptor\n{\"action\":\"propose_column\",...}\n```"
    llm_messages[0] = LLMMessage(role="system", content=llm_messages[0].content + extra)

    content = ""
    try:
        async for token in llm_stream(llm_messages, provider=provider, model=model, temperature=0.5):
            content += token
            yield _sse({"type": "token", "content": token})
    except Exception as e:
        yield _sse({"type": "token", "content": format_llm_error(e, provider=provider)})
        yield _sse({"type": "done"})
        return

    # Parse embedded sculptor actions from non-OpenAI providers
    if "```sculptor" in content:
        try:
            block = content.split("```sculptor")[1].split("```")[0].strip()
            action = json.loads(block)
            act = action.get("action")
            if act:
                async for payload in _handle_tool(
                    act, action,
                    records=records, columns=columns, provider=provider, model=model,
                ):
                    yield _sse(payload)
        except json.JSONDecodeError:
            pass

    yield _sse({"type": "done"})


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
