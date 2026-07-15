from __future__ import annotations

import json

from claycomp.enrichers.base import Enricher
from claycomp.enrichers.research_util import lead_context, parse_json_object
from claycomp.llm import LLMMessage, llm_complete
from claycomp.models import EnrichmentResult, Record

SYSTEM_PROMPT = """You are a GTM strategist deciding who deserves expensive high-touch research.

Rate each lead for deep personalization research (the Mars CEO flower story style — unique personal hooks that win big deals).

Score 0–100 based on:
- Decision-maker seniority (C-level / VP / Founder > manager)
- Company value / deal potential signals
- Data completeness (name, company, title, LinkedIn)
- Notability / researchability (public figure, known company, LinkedIn present)

Return JSON only:
{
  "score": 0-100,
  "tier": "skip" | "standard" | "high_touch",
  "reason": "1 sentence why",
  "research_budget_pct": 0-100,
  "priority": "low" | "medium" | "high"
}

Rules:
- tier=high_touch only if score >= 70
- tier=standard for 40–69
- tier=skip under 40
- research_budget_pct is what share of the user's CAC this person could justify (high-touch often 50–100%)
"""


class ResearchTierEnricher(Enricher):
    name = "research_tier"
    description = "Score who is worth expensive high-touch research"
    requires_api_key = "OPENAI_API_KEY"

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider
        self.model = model

    async def enrich(self, record: Record) -> EnrichmentResult:
        context = lead_context(record)
        try:
            result = await llm_complete(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=json.dumps(context, default=str)),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0.2,
                max_tokens=250,
                json_mode=True,
            )
            data = parse_json_object(result.content)
            score = int(data.get("score") or 0)
            if score >= 70:
                tier = "high_touch"
            elif score >= 40:
                tier = "standard"
            else:
                tier = "skip"
            value = {
                "score": score,
                "tier": data.get("tier") or tier,
                "reason": data.get("reason") or "",
                "research_budget_pct": data.get("research_budget_pct"),
                "priority": data.get("priority") or ("high" if score >= 70 else "medium" if score >= 40 else "low"),
                "talking_point": f"{tier.replace('_', ' ').title()} ({score}) — {data.get('reason') or 'n/a'}",
            }
            return EnrichmentResult(column=self.name, value=value, source=result.provider, confidence=0.8)
        except Exception as e:
            return EnrichmentResult(column=self.name, value=None, source="error", notes=str(e))
