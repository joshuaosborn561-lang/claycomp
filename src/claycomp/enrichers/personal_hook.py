from __future__ import annotations

import json

from claycomp.enrichers.base import Enricher
from claycomp.enrichers.research_util import enriched_field, lead_context, parse_json_object
from claycomp.llm import LLMMessage, llm_complete
from claycomp.models import EnrichmentResult, Record

SYSTEM_PROMPT = """You research high-touch personalization hooks for B2B outreach.

Inspiration: Mars CEO casually mentioned loving the smell of flowers at his Dutch college.
Someone mailed that exact flower — and booked a $10M meeting. Find THAT kind of hook.

Find 1–3 personal/professional hooks that are:
- Specific and emotional (not "likes golf")
- Actionable for a physical or digital gesture
- Plausible from public signals (alumni, hometown, hobbies, podcasts, boards, sports, philanthropy)
- Prefer verified-looking public facts; mark uncertain ones clearly

Skip generic fluff. Prefer obscure, high-signal details.

Return JSON only:
{
  "hooks": [
    {
      "hook": "short specific fact",
      "emotion": "why it matters to them",
      "confidence": "high" | "medium" | "low",
      "source_hint": "where to verify (LinkedIn About, podcast, alumni page, etc.)",
      "gift_angle": "gesture category under a normal CAC (not luxury forever-gifts)"
    }
  ],
  "best_hook": "the strongest hook text",
  "research_needed": ["follow-ups if confidence is low"],
  "skip_reason": null or why not worth researching further
}

If the lead looks junior / not a buyer, set hooks=[] and skip_reason.
"""


class PersonalHookEnricher(Enricher):
    name = "personal_hook"
    description = "Find unique personal hooks for high-touch outreach (Mars flower style)"
    requires_api_key = "OPENAI_API_KEY"

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        *,
        min_tier_score: int = 40,
    ):
        self.provider = provider
        self.model = model
        self.min_tier_score = min_tier_score

    async def enrich(self, record: Record) -> EnrichmentResult:
        tier = enriched_field(record, "research_tier", "Research Tier")
        if isinstance(tier, dict):
            score = int(tier.get("score") or 0)
            if score < self.min_tier_score or tier.get("tier") == "skip":
                return EnrichmentResult(
                    column=self.name,
                    value={
                        "hooks": [],
                        "best_hook": None,
                        "skip_reason": f"Below research threshold (score {score})",
                        "talking_point": "Skipped — not high-touch worth",
                    },
                    source="gate",
                    notes="tier_gate",
                )

        context = lead_context(record)
        try:
            result = await llm_complete(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=json.dumps(context, default=str)),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0.5,
                max_tokens=700,
                json_mode=True,
            )
            data = parse_json_object(result.content)
            hooks = data.get("hooks") or []
            best = data.get("best_hook") or (hooks[0].get("hook") if hooks else None)
            value = {
                "hooks": hooks,
                "best_hook": best,
                "research_needed": data.get("research_needed") or [],
                "skip_reason": data.get("skip_reason"),
                "talking_point": best or data.get("skip_reason") or "No hook found",
            }
            return EnrichmentResult(column=self.name, value=value, source=result.provider, confidence=0.7)
        except Exception as e:
            return EnrichmentResult(column=self.name, value=None, source="error", notes=str(e))
