from __future__ import annotations

import json
import os
from typing import Any

from openai import AsyncOpenAI

from claycomp.models import Record

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_enrichment",
            "description": "Save an enrichment result for this lead",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "Column name for the result"},
                    "value": {"description": "The enrichment value (string, number, or object)"},
                    "reasoning": {"type": "string", "description": "Brief note on how you found this"},
                },
                "required": ["column", "value"],
            },
        },
    }
]

SYSTEM_PROMPT = """You are a lead enrichment agent for cold outreach personalization.

Given a lead record, research and infer useful personalization data.
You have general knowledge about geography, sports, culture, and business.

Common tasks:
- Find local sports teams, landmarks, neighborhoods
- Suggest conversation starters based on location/role
- Infer company industry or size signals
- Find colloquial area names

Use save_enrichment to store each piece of data. You can call it multiple times.
Be practical — only save things genuinely useful in a 1-line email opener.
If you can't determine something confidently, skip it."""


class EnrichmentAgent:
    """Flexible AI agent for custom enrichment prompts."""

    def __init__(self, prompt: str, output_column: str = "agent_result"):
        self.prompt = prompt
        self.output_column = output_column
        self.requires_api_key = "OPENAI_API_KEY"

    async def enrich(self, record: Record) -> dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY not set"}

        client = AsyncOpenAI(api_key=api_key)
        context = {
            "name": record.display_name(),
            "email": record.email,
            "title": record.title,
            "company": record.company,
            "location": record.display_location(),
            "existing_enrichments": record.enriched,
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Lead:\n{json.dumps(context, indent=2)}\n\nTask: {self.prompt}",
            },
        ]

        enrichments: dict[str, Any] = {}

        for _ in range(3):  # allow multiple tool calls
            resp = await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                tools=AGENT_TOOLS,
                temperature=0.4,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                if msg.content:
                    enrichments[self.output_column] = msg.content
                break

            messages.append(msg)
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments)
                col = args.get("column", self.output_column)
                enrichments[col] = {
                    "value": args.get("value"),
                    "reasoning": args.get("reasoning"),
                }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps({"saved": True, "column": col}),
                    }
                )

        return enrichments
