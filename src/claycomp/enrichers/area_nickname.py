from __future__ import annotations

import json

from claycomp.enrichers.base import Enricher
from claycomp.llm import LLMMessage, llm_complete
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

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider
        self.model = model

    async def enrich(self, record: Record) -> EnrichmentResult:
        location = record.display_location()
        if not location:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no location")

        try:
            result = await llm_complete(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=f"Location: {location}"),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0.3,
                json_mode=True,
            )
            data = json.loads(result.content or "{}")
            return EnrichmentResult(column=self.name, value=data, source=result.provider, confidence=0.85)
        except Exception as e:
            return EnrichmentResult(
                column=self.name,
                value={"nickname": location, "how_to_reference": f"in {location}"},
                source="fallback",
                notes=str(e),
            )
