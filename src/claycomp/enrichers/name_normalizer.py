from __future__ import annotations

import os

from openai import AsyncOpenAI

from claycomp.enrichers.base import Enricher
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

    async def enrich(self, record: Record) -> EnrichmentResult:
        first = record.first_name
        if not first:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no first name")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return EnrichmentResult(
                column=self.name,
                value=first,
                source="fallback",
                notes="OPENAI_API_KEY not set",
            )

        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"First name: {first}"},
            ],
            temperature=0,
            max_tokens=20,
        )
        normalized = (resp.choices[0].message.content or first).strip().strip('"')
        return EnrichmentResult(column=self.name, value=normalized, source="openai", confidence=0.9)
