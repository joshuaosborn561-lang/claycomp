from __future__ import annotations

import json

from claycomp.enrichers.base import Enricher
from claycomp.llm import LLMMessage, llm_complete
from claycomp.models import EnrichmentResult, Record

SYSTEM_PROMPT = """You normalize first names for cold outreach emails.

Rules:
- Return the conversational, friendly form people actually use
- "Robert" → "Rob", "William" → "Will", "Elizabeth" → "Liz"
- If already short/common, keep it: "Mike" stays "Mike"
- If unsure, return the original first name
- Return ONLY the normalized name, nothing else"""


class NameNormalizerEnricher(Enricher):
    name = "normalized_first_name"
    description = "Normalize first name to conversational form (Rob, Liz, etc.)"
    requires_api_key = "OPENAI_API_KEY"

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider
        self.model = model

    async def enrich(self, record: Record) -> EnrichmentResult:
        first = record.first_name
        if not first:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no first name")

        try:
            result = await llm_complete(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=f"First name: {first}"),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0,
                max_tokens=20,
            )
            normalized = (result.content or first).strip().strip('"')
            return EnrichmentResult(column=self.name, value=normalized, source=result.provider, confidence=0.9)
        except Exception as e:
            return EnrichmentResult(column=self.name, value=first, source="fallback", notes=str(e))
