from __future__ import annotations

import json
import os

from openai import AsyncOpenAI

from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record

SYSTEM_PROMPT = """You find the conversational/local nickname for a geographic area.

Examples:
- San Francisco, CA → "the Bay Area" or "SF"
- Brooklyn, NY → "Brooklyn" (locals say Brooklyn, not "New York City")
- Austin, TX → "Austin" or "ATX"
- Greater Boston area → "Boston" or "the Boston area"

Return JSON: {"nickname": "...", "how_to_reference": "how you'd mention it in an email opener"}

The how_to_reference should be natural, e.g. "out in the Bay Area" or "based in Austin"."""


class AreaNicknameEnricher(Enricher):
    name = "area_nickname"
    description = "Conversational name for someone's location"
    requires_api_key = "OPENAI_API_KEY"

    async def enrich(self, record: Record) -> EnrichmentResult:
        location = record.display_location()
        if not location:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no location")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return EnrichmentResult(
                column=self.name,
                value={"nickname": location, "how_to_reference": f"in {location}"},
                source="fallback",
            )

        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Location: {location}"},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return EnrichmentResult(column=self.name, value=data, source="openai", confidence=0.85)
