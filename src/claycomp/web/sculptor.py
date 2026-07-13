from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.llm import LLMMessage, llm_complete, llm_stream
from claycomp.llm.errors import format_llm_error
from claycomp.web.sculptor_analytics import analyze_table, estimate_credits
from claycomp.web.schemas import ChatMessage, RecordDTO, dto_to_record, record_to_dto

TEST_ROWS = 10

ENRICHERS_DOC = "\n".join(
    f"- {k}: {cls().description}" for k, cls in ENRICHERS.items()
) + "\n- custom: your own AI prompt per row"

SCULPTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_column",
            "description": "Propose exactly ONE enrichment column. Use this when the user asks to fill/add/find a specific field.",
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
            "description": "ONLY for open-ended questions like 'what enrichments should I add?'. Max 2 recommendations. Never use when the user asked for one specific field.",
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
            "description": f"Run an enrichment test on the first {TEST_ROWS} rows (safe preview)",
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
- execute_sandbox to preview on 10 rows before going live (always prefer test first)
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
- Prefer test runs before full runs
- Use tools proactively — don't just describe what to do, DO it via tools
- Be concise and actionable like Clay Sculptor
- If business context is provided, tailor all recommendations to it
- For column proposals: call propose_column OR recommend_columns ONCE per user message — never propose the same column twice
- After proposing columns, stop — do not call proposal tools again in follow-up turns
- When the user asks to fill/find/add ONE field (e.g. location), call propose_column exactly ONCE — do NOT use recommend_columns and do NOT suggest other fields
- recommend_columns is only for broad "what should I add?" questions — maximum 1 item, never duplicate topics
- Never create multiple columns for the same purpose (e.g. one "Location" column, not "Location" + "Full Location" + "Filled Location")"""


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
    targets = recs[:TEST_ROWS]
    for rec in targets:
        try:
            result = await enricher.enrich(rec)
            rec.set_enriched(enricher.output_column(), result.value)
        except Exception as e:
            rec.set_enriched(enricher.output_column(), None)
            rec.set_enriched(f"{enricher.output_column()}_error", str(e))
    return [record_to_dto(r) for r in recs]


PROPOSAL_TOOL_NAMES = frozenset({"propose_column", "recommend_columns"})

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "location": ("location", "city", "state", "address", "where", "lives", "geograph", "region"),
    "title": ("job title", "title", "role", "position"),
    "name": ("normalize name", "name normalizer", "normalize"),
    "restaurant": ("restaurant", "dining", "food", "nearby"),
    "review": ("google review", "review", "rating"),
    "area": ("area nickname", "neighborhood", "nickname"),
    "baseball": ("baseball", "mlb", "team"),
    "company": ("company", "employer", "organization"),
    "email": ("email",),
}

TOPIC_MATCH_ORDER = (
    "location", "title", "restaurant", "review", "baseball", "area", "name", "company", "email",
)

FALLBACK_PROPOSALS: dict[str, dict[str, str]] = {
    "location": {
        "column_name": "location",
        "label": "Location",
        "enricher_key": "custom",
        "custom_prompt": (
            "Find where this person is located. Use their first name, last name, and company. "
            "Return city and state."
        ),
        "reasoning": "Fill in missing location data using name and company.",
    },
    "title": {
        "column_name": "title",
        "label": "Title",
        "enricher_key": "custom",
        "custom_prompt": "Find the job title for this person at their company.",
        "reasoning": "Fill in missing title data.",
    },
}


def _topic_from_text(text: str) -> str | None:
    text_l = text.lower()
    for topic in TOPIC_MATCH_ORDER:
        for kw in sorted(TOPIC_KEYWORDS[topic], key=len, reverse=True):
            if kw in text_l:
                return topic
    return None


def _proposal_topic(args: dict) -> str:
    enricher = (args.get("enricher_key") or "").lower()
    if enricher and enricher != "custom":
        return enricher

    label_blob = f"{args.get('label', '')} {args.get('column_name', '')}".lower()
    label_topic = _topic_from_text(label_blob)
    if label_topic:
        return label_topic

    prompt_blob = " ".join(
        str(args.get(k) or "") for k in ("custom_prompt", "reasoning", "reason")
    ).lower()
    prompt_topic = _topic_from_text(prompt_blob)
    if prompt_topic:
        return prompt_topic

    return f"custom:{label_blob.strip()[:48] or 'misc'}"


def _topic_matches_primary(primary: str, topic: str, args: dict) -> bool:
    if topic == primary:
        return True
    label_blob = f"{args.get('label', '')} {args.get('column_name', '')}".lower()
    return any(kw in label_blob for kw in TOPIC_KEYWORDS.get(primary, ()))


def _column_config_topic(col: dict) -> str:
    return _proposal_topic({
        "enricher_key": col.get("enricherKey") or col.get("enricher_key") or "",
        "label": col.get("label") or "",
        "column_name": col.get("columnName") or col.get("column_name") or "",
        "custom_prompt": col.get("customPrompt") or col.get("custom_prompt") or "",
    })


def _extract_primary_topic(text: str) -> str | None:
    text_l = text.lower()
    for pattern in (
        r"(?:try to )?(?:fill in|populate|enrich|complete|add)\s+(?:the\s+)?([\w\s]+?)(?:\s+for|\s+using|$|\.|,)",
        r"(?:find|get|look up|lookup|search for)\s+(?:the\s+)?([\w\s]+?)(?:\s+for|\s+using|$|\.|,)",
    ):
        match = re.search(pattern, text_l)
        if not match:
            continue
        phrase = match.group(1).strip()
        topic = _topic_from_text(phrase)
        if topic:
            return topic
    return None


def _user_intent(messages: list[ChatMessage]) -> dict[str, Any]:
    last = next((m.content for m in reversed(messages) if m.role == "user"), "")
    text = last.lower()
    specific_verbs = (
        "fill in", "look up", "lookup", "find", "get", "add", "figure out",
        "populate", "enrich", "search for", "try to fill",
    )
    primary_topic = _extract_primary_topic(last)
    contextual_topics = {"name", "company"}
    salient_topics = [
        t for t, kws in TOPIC_KEYWORDS.items()
        if t not in contextual_topics and any(kw in text for kw in kws)
    ]
    if not primary_topic and any(v in text for v in specific_verbs) and len(salient_topics) == 1:
        primary_topic = salient_topics[0]
    is_specific = primary_topic is not None
    is_workflow = any(w in text for w in ("workflow", "full enrichment", "build a", "all enrichments"))
    cap = 1
    return {
        "cap": cap,
        "primary_topic": primary_topic,
        "topics": salient_topics,
        "is_specific": is_specific,
        "hint": (
            f"USER INTENT: They asked specifically to enrich **{primary_topic}** only. "
            f"Call propose_column exactly once for {primary_topic}. "
            "Do not use recommend_columns. Do not suggest other fields."
        )
        if is_specific and primary_topic
        else None,
    }


class _ProposalGate:
    def __init__(self, *, cap: int, primary_topic: str | None, columns: list[dict]) -> None:
        self.cap = cap
        self.primary_topic = primary_topic
        self.columns = columns
        self.seen_topics: set[str] = set()
        self.emitted = 0
        self.configured_topics = {_column_config_topic(c) for c in columns}

    def allow(self, args: dict, *, force: bool = False) -> bool:
        if self.emitted >= self.cap:
            return False
        topic = _proposal_topic(args)
        if not force:
            if self.primary_topic and not _topic_matches_primary(self.primary_topic, topic, args):
                return False
            if topic in self.seen_topics or topic in self.configured_topics:
                return False
        elif topic in self.seen_topics:
            return False
        self.seen_topics.add(topic)
        self.emitted += 1
        return True


def _existing_column_label(columns: list[dict], topic: str) -> str | None:
    for col in columns:
        if _column_config_topic(col) == topic:
            return col.get("label") or topic.title()
    return None


def _finalize_proposals(
    proposal_gate: _ProposalGate,
    intent: dict[str, Any],
    columns: list[dict],
) -> list[dict[str, Any]]:
    if proposal_gate.emitted > 0:
        return []

    primary = intent.get("primary_topic")
    if primary:
        existing = _existing_column_label(columns, primary)
        if existing:
            return [{
                "type": "token",
                "content": (
                    f"\n\nYou already have a **{existing}** column — scroll right in the table "
                    "and click the play button to run it."
                ),
            }]

        fallback = FALLBACK_PROPOSALS.get(primary)
        if fallback and proposal_gate.allow(fallback, force=True):
            return [{"type": "proposal", "proposal": fallback}]

    return [{
        "type": "token",
        "content": "\n\nI couldn't build a column proposal. Use the **+** button to add a Custom AI column.",
    }]


def _proposal_key(args: dict) -> str:
    return _proposal_topic(args)


async def _handle_tool(
    name: str,
    args: dict,
    *,
    records: list[RecordDTO],
    columns: list[dict],
    provider: str | None,
    model: str | None,
    proposal_gate: _ProposalGate | None = None,
) -> AsyncIterator[dict]:
    if name == "propose_column":
        if proposal_gate is not None and not proposal_gate.allow(args):
            return
        yield {"type": "proposal", "proposal": args}
    elif name == "recommend_columns":
        recommendations = args.get("recommendations", [])
        emitted: list[dict] = []
        for rec in recommendations:
            proposal = {
                "column_name": rec.get("column_name") or rec.get("enricher_key"),
                "label": rec.get("label"),
                "enricher_key": rec.get("enricher_key"),
                "custom_prompt": rec.get("custom_prompt"),
                "reasoning": rec.get("reason"),
            }
            if proposal_gate is not None and not proposal_gate.allow(proposal):
                continue
            emitted.append(proposal)
            yield {"type": "proposal", "proposal": proposal}
        if emitted:
            yield {"type": "recommendations", "recommendations": emitted}
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
    intent = _user_intent(messages)
    if intent.get("hint"):
        context += "\n\n" + intent["hint"]
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

    proposal_gate = _ProposalGate(
        cap=intent["cap"],
        primary_topic=intent.get("primary_topic"),
        columns=columns,
    )
    for _ in range(3):
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
                    proposal_gate=proposal_gate,
                ):
                    yield _sse(payload)
                    if payload.get("type") == "records":
                        records = [RecordDTO.model_validate(r) for r in payload["records"]]

            if all(call.name in PROPOSAL_TOOL_NAMES for call in result.tool_calls):
                for payload in _finalize_proposals(proposal_gate, intent, columns):
                    yield _sse(payload)
                if result.content:
                    yield _sse({"type": "token", "content": result.content})
                elif proposal_gate.emitted > 0:
                    yield _sse({
                        "type": "token",
                        "content": "\n\nClick **Apply** to add the column to your table, or **Test** to try it on 10 rows first.",
                    })
                break

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
