from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.llm import LLMMessage, llm_complete, llm_stream
from claycomp.llm.errors import format_llm_error
from claycomp.web.sculptor_analytics import analyze_table, estimate_credits
from claycomp.web.schemas import ChatMessage, RecordDTO, dto_to_record, record_to_dto
from claycomp.web.table_knowledge import (
    answer_table_query,
    build_table_knowledge,
    knowledge_to_prompt_block,
)

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
                    "skip_if_output_filled": {
                        "type": "boolean",
                        "description": "Skip rows that already have a value in this column",
                    },
                    "skip_if_source_filled": {
                        "type": "string",
                        "description": "Skip rows where this source field is already filled (e.g. 'email')",
                    },
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
            "description": "Suggest an improved prompt for an existing custom column",
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
    {
        "type": "function",
        "function": {
            "name": "query_table",
            "description": (
                "Look up hard facts from the loaded table knowledge base. "
                "ALWAYS call this before answering questions about the data "
                "(counts, missing emails, companies, titles, who to prioritize, what columns exist)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The user's question or the fact you need to verify",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "configure_column",
            "description": (
                "Update an existing enrichment column's settings — AI prompt and/or Clay-style run conditions "
                "(e.g. skip if email already filled). Use when the user wants to tweak how a column behaves."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "column_label": {"type": "string"},
                    "custom_prompt": {"type": "string"},
                    "skip_if_output_filled": {"type": "boolean"},
                    "skip_if_source_filled": {
                        "type": "string",
                        "description": "Source field to check, e.g. 'email'. Empty string clears the rule.",
                    },
                    "require_source_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reasoning": {"type": "string"},
                },
                "required": ["column_label", "reasoning"],
            },
        },
    },
]

SCULPTOR_SYSTEM = f"""You are Sculptor — the Claycomp table co-pilot. You act as BOTH:
1) a knowledgeable chatbot that answers questions about the loaded table using the TABLE KNOWLEDGE BASE, and
2) an architect that proposes/configures enrichment columns and workflows.

## Dual mode (pick the right one)
**CHAT / analyst mode** — when the user asks a question, wants an explanation, analysis, counts, diagnostics, drafts, or advice:
- Call query_table first (and analyze_table / diagnose_table when useful)
- Answer with concrete numbers, names, and companies from the knowledge base
- Do NOT propose new columns unless they clearly ask to add/build/enrich/find a field
- Write a solid, useful answer in natural language (2–8 short sentences or bullets)

**ARCHITECT mode** — when the user asks to add/build/fill/find a field, create a workflow, or change column settings:
- propose_column / recommend_columns / propose_workflow / configure_column / edit_column_prompt
- For email finder / waterfall: propose email_waterfall once, and set skip_if_source_filled to "email" when they want to avoid re-finding known emails
- Prefer configure_column when they want to tweak an EXISTING column (prompt or run conditions)
- After proposing, stop — do not spam more proposals

## Capabilities
Built-in enrichers:
{ENRICHERS_DOC}

Also: draft_outreach, estimate_cost, execute_sandbox (only if they explicitly ask to test).

## Hard rules
- Ground every data claim in the knowledge base / query_table results — never invent row counts or company names
- Prefer real names/companies/titles from the sample leads
- Never auto-run enrichments; the user clicks Test/Play in the UI
- One proposal max for a specific field request; recommend_columns only for open-ended "what should I add?"
- Never create duplicate columns for the same purpose
- If business context is provided, tailor recommendations and drafts to it
- Be concise, specific, and helpful — like a sharp Clay Sculptor"""


def _table_context(
    records: list[RecordDTO],
    columns: list[dict],
    business_context: str | None,
) -> str:
    kb = build_table_knowledge(records, columns, business_context)
    return knowledge_to_prompt_block(kb)


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
    "email": {
        "column_name": "email_waterfall",
        "label": "Work Email",
        "enricher_key": "email_waterfall",
        "skip_if_output_filled": True,
        "skip_if_source_filled": "email",
        "reasoning": (
            "Find work emails via the email waterfall (AI Ark + Prospeo). "
            "Skips rows that already have an email."
        ),
    },
}



TOPIC_FUZZY_PATTERNS: dict[str, re.Pattern[str]] = {
    "location": re.compile(r"loca?ti?on|locaiton|locaton|geograph|where\s+.+\s+lives", re.I),
    "title": re.compile(r"\btitle\b|\bjob\s+title\b|\brole\b|\bposition\b", re.I),
}


def _topic_from_text(text: str) -> str | None:
    text_l = text.lower()
    for topic, pattern in TOPIC_FUZZY_PATTERNS.items():
        if pattern.search(text_l):
            return topic
    for topic in TOPIC_MATCH_ORDER:
        for kw in sorted(TOPIC_KEYWORDS[topic], key=len, reverse=True):
            if kw in text_l:
                return topic
    return None


def _infer_topic_from_message(text: str) -> str | None:
    topic = _extract_primary_topic(text)
    if topic:
        return topic
    return _topic_from_text(text)


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
        r"(?:try to )?(?:fill in|populate|enrich|complete|add)\s+(?:the\s+)?(?:a\s+)?([\w\s]+?)(?:\s+for|\s+using|$|\.|,)",
        r"(?:try to )?(?:find|get|look up|lookup|search for)\s+(?:the\s+)?(?:a\s+)?([\w\s]+?)(?:\s+for|\s+using|$|\.|,)",
    ):
        match = re.search(pattern, text_l)
        if not match:
            continue
        phrase = match.group(1).strip()
        topic = _topic_from_text(phrase)
        if topic:
            return topic
    return _topic_from_text(text)


def _user_intent(messages: list[ChatMessage]) -> dict[str, Any]:
    last = next((m.content for m in reversed(messages) if m.role == "user"), "")
    text = last.lower().strip()
    specific_verbs = (
        "fill in", "look up", "lookup", "find", "get", "add", "figure out",
        "populate", "enrich", "search for", "try to fill", "try to find",
        "create column", "build column", "propose", "set up", "setup",
        "configure", "skip if", "don't run", "do not run", "dont run",
    )
    question_signals = (
        "?", "what ", "what's", "whats", "how ", "why ", "which ", "who ",
        "tell me", "explain", "analyze", "analyse", "look at", "show me",
        "how many", "how much", "summarize", "summary", "diagnose",
        "help me understand", "can you explain",
    )
    build_signals = (
        "add ", "propose", "build", "create", "fill in", "fill the",
        "enrich with", "enrich my", "find email", "email waterfall",
        "email finder", "workflow", "configure", "skip if", "change the prompt",
        "update the prompt", "edit the prompt",
    )
    wants_configure = any(
        w in text
        for w in (
            "skip if", "don't run", "do not run", "dont run",
            "configure", "change the prompt", "update the prompt",
            "edit the prompt", "column settings",
        )
    )
    primary_topic = _infer_topic_from_message(last)
    contextual_topics = {"name", "company", "email"}
    salient_topics = [
        t for t, kws in TOPIC_KEYWORDS.items()
        if t not in contextual_topics and any(kw in text for kw in kws)
    ]
    if not primary_topic and any(v in text for v in specific_verbs):
        non_context = [t for t in salient_topics if t not in contextual_topics]
        if len(non_context) == 1:
            primary_topic = non_context[0]
    is_question = any(s in text for s in question_signals)
    wants_build = any(s in text for s in build_signals) or wants_configure
    # Questions like "what enrichments should I add?" are architect+chat
    open_ended_recs = any(
        s in text
        for s in ("what enrichment", "what should i add", "recommend", "suggestions")
    )
    is_specific = primary_topic is not None and (wants_build or not is_question)
    is_workflow = any(w in text for w in ("workflow", "full enrichment", "build a", "all enrichments"))
    mode = "architect" if (wants_build or is_specific or is_workflow or open_ended_recs) else "chat"
    if is_question and not wants_build and not open_ended_recs:
        mode = "chat"
        is_specific = False
    cap = 1
    if mode == "chat":
        hint = (
            "USER INTENT: CHAT / analyst mode. Answer using query_table + the knowledge base. "
            "Do NOT call propose_column or recommend_columns unless they explicitly ask to add a column."
        )
    elif wants_configure:
        hint = (
            "USER INTENT: Configure an existing column. Prefer configure_column "
            "(e.g. skip_if_source_filled='email'). Do not add duplicate columns."
        )
    elif is_specific and primary_topic:
        hint = (
            f"USER INTENT: They asked specifically to enrich **{primary_topic}** only. "
            f"Call propose_column exactly once for {primary_topic}. "
            "Do not use recommend_columns. Do not suggest other fields."
        )
    elif open_ended_recs:
        hint = (
            "USER INTENT: Open-ended recommendations. Call query_table, then recommend_columns "
            "(max 1) grounded in table gaps."
        )
    else:
        hint = None
    return {
        "cap": cap,
        "primary_topic": primary_topic,
        "topics": salient_topics,
        "is_specific": is_specific,
        "is_workflow": is_workflow,
        "mode": mode,
        "hint": hint,
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
    messages: list[ChatMessage] | None = None,
    *,
    allow_failure_message: bool = True,
) -> list[dict[str, Any]]:
    if proposal_gate.emitted > 0:
        return []

    primary = intent.get("primary_topic")
    if not primary and messages:
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        primary = _infer_topic_from_message(last)

    if primary:
        existing = _existing_column_label(columns, primary)
        if existing:
            return [{
                "type": "token",
                "content": (
                    f"\n\nYou already have a **{existing}** column — scroll right in the table "
                    "and click the play button to run it, or delete the duplicate columns you don't need."
                ),
            }]

        fallback = FALLBACK_PROPOSALS.get(primary)
        if fallback and proposal_gate.allow(fallback, force=True):
            return [{"type": "proposal", "proposal": fallback}]

    if not allow_failure_message:
        return []

    return [{
        "type": "token",
        "content": (
            "\n\nI couldn't build a column proposal. Try rephrasing your request, "
            "or use the **+** button to add a Custom AI column."
        ),
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
        yield {"type": "column_config", "config": {
            "column_label": args.get("column_label"),
            "improved_prompt": args.get("improved_prompt"),
            "reasoning": args.get("reasoning"),
        }}
    elif name == "query_table":
        kb = build_table_knowledge(records, columns)
        result = answer_table_query(str(args.get("question") or ""), kb)
        yield {"type": "table_facts", "facts": result.get("facts", []), "snapshot": result.get("knowledge_snapshot")}
    elif name == "configure_column":
        skip_src = args.get("skip_if_source_filled")
        if skip_src == "":
            skip_src = None
        config = {
            "column_label": args.get("column_label"),
            "custom_prompt": args.get("custom_prompt"),
            "skip_if_output_filled": args.get("skip_if_output_filled"),
            "skip_if_source_filled": skip_src,
            "require_source_fields": args.get("require_source_fields"),
            "reasoning": args.get("reasoning"),
        }
        yield {"type": "column_config", "config": config}


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
    emitted_workflow = False
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
                    if payload.get("type") == "workflow":
                        emitted_workflow = True
                    yield _sse(payload)
                    if payload.get("type") == "records":
                        records = [RecordDTO.model_validate(r) for r in payload["records"]]

            if all(call.name in PROPOSAL_TOOL_NAMES for call in result.tool_calls):
                if intent.get("mode") == "architect":
                    for payload in _finalize_proposals(proposal_gate, intent, columns, messages):
                        yield _sse(payload)
                if result.content:
                    yield _sse({"type": "token", "content": result.content})
                elif proposal_gate.emitted > 0:
                    yield _sse({
                        "type": "token",
                        "content": "\n\nClick **Apply** to add the column to your table, or **Test** to try it on 10 rows first.",
                    })
                break

            # Feed tool results back so the model can write a solid answer
            tool_notes: list[str] = []
            for call in result.tool_calls:
                if call.name == "query_table":
                    kb = build_table_knowledge(records, columns)
                    facts = answer_table_query(str(call.arguments.get("question") or ""), kb).get("facts") or []
                    tool_notes.append("query_table facts:\n- " + "\n- ".join(facts))
                elif call.name == "configure_column":
                    tool_notes.append(
                        f"configure_column applied for '{call.arguments.get('column_label')}': "
                        f"{call.arguments.get('reasoning') or 'settings updated'}"
                    )
                elif call.name == "analyze_table":
                    tool_notes.append("analyze_table completed — cite the stats in your answer.")
            followup = (
                f"(Tools executed: {', '.join(executed)}. "
                "Write a clear, specific answer for the user using the tool results. "
                "Use real numbers and names. Do not invent data.)"
            )
            if tool_notes:
                followup += "\n\n" + "\n\n".join(tool_notes)
            llm_messages.append(LLMMessage(role="user", content=followup))
            continue

        if result.content:
            yield _sse({"type": "token", "content": result.content})
        break

    # Only force a proposal fallback in architect mode for specific field asks
    if (
        intent.get("mode") == "architect"
        and intent.get("is_specific")
        and proposal_gate.emitted == 0
        and not emitted_workflow
    ):
        for payload in _finalize_proposals(
            proposal_gate,
            intent,
            columns,
            messages,
            allow_failure_message=True,
        ):
            yield _sse(payload)

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
