from __future__ import annotations

import json

from claycomp.enrichers.base import Enricher
from claycomp.enrichers.research_util import enriched_field, lead_context, parse_json_object
from claycomp.llm import LLMMessage, llm_complete
from claycomp.models import EnrichmentResult, Record

SYSTEM_PROMPT = """You design uniquely memorable outreach offers/gifts with a hard CAC budget.

Inspiration: someone mailed Mars' CEO the specific flowers that smelled like his Dutch college campus → $10M deal.
That works because it was personal, proportional, and surprising — not because it was expensive.

HARD RULES:
- You have a maximum budget (CAC limit) in USD. NEVER suggest anything that costs more.
- If the obvious gift exceeds CAC (e.g. Rolex, courtside tickets), REJECT it and invent a cheaper proxy that hits the same emotion.
- Prefer under 50% of CAC when possible; leave room for follow-up.
- Be specific and executable (vendor idea, note copy, logistics).
- Generate 2–3 options, then pick one winner under budget.

Return JSON only:
{
  "offers": [
    {
      "title": "short name",
      "idea": "what to do/send",
      "estimated_cost_usd": 0,
      "within_budget": true,
      "why_it_works": "emotion + specificity",
      "note_copy": "1-2 sentence card/email note",
      "risk": "creepy / too familiar / logistic risk if any"
    }
  ],
  "winner": { same shape as an offer },
  "rejected": [
    {"idea": "...", "estimated_cost_usd": 0, "reason": "over CAC / creepy / generic"}
  ],
  "budget_usd": 0,
  "talking_point": "one-line summary of the winning offer"
}

If no hooks exist, invent a respectful high-signal professional gesture under budget tied to company/alma mater/city — still unique, never generic swag.
"""


class UniqueOfferEnricher(Enricher):
    name = "unique_offer"
    description = "Design CAC-capped unique personalization offers from research hooks"
    requires_api_key = "OPENAI_API_KEY"

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        *,
        cac_limit_usd: float = 200,
        business_context: str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.cac_limit_usd = cac_limit_usd
        self.business_context = business_context or ""

    async def enrich(self, record: Record) -> EnrichmentResult:
        hook = enriched_field(record, "personal_hook", "Personal Hook")
        if isinstance(hook, dict) and hook.get("skip_reason") and not hook.get("best_hook"):
            return EnrichmentResult(
                column=self.name,
                value={
                    "offers": [],
                    "winner": None,
                    "rejected": [],
                    "budget_usd": self.cac_limit_usd,
                    "talking_point": f"Skipped — {hook.get('skip_reason')}",
                },
                source="gate",
            )

        payload = {
            "lead": lead_context(record),
            "personal_hook": hook,
            "cac_limit_usd": self.cac_limit_usd,
            "business_context": self.business_context,
        }
        try:
            result = await llm_complete(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(
                        role="user",
                        content=(
                            f"CAC limit: ${self.cac_limit_usd:.0f}. "
                            "Reject any idea over this and keep looking for alternatives.\n\n"
                            + json.dumps(payload, default=str)
                        ),
                    ),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0.6,
                max_tokens=900,
                json_mode=True,
            )
            data = parse_json_object(result.content)
            winner = data.get("winner") or {}
            # Enforce CAC server-side even if the model slips
            if winner and float(winner.get("estimated_cost_usd") or 0) > self.cac_limit_usd:
                rejected = list(data.get("rejected") or [])
                rejected.append({
                    "idea": winner.get("idea"),
                    "estimated_cost_usd": winner.get("estimated_cost_usd"),
                    "reason": "over CAC (server filter)",
                })
                within = [
                    o for o in (data.get("offers") or [])
                    if float(o.get("estimated_cost_usd") or 0) <= self.cac_limit_usd
                ]
                winner = within[0] if within else None
                data["rejected"] = rejected
                data["winner"] = winner

            if winner:
                winner["within_budget"] = float(winner.get("estimated_cost_usd") or 0) <= self.cac_limit_usd

            value = {
                "offers": data.get("offers") or [],
                "winner": winner,
                "rejected": data.get("rejected") or [],
                "budget_usd": self.cac_limit_usd,
                "talking_point": (
                    data.get("talking_point")
                    or (f"{winner.get('title')}: {winner.get('idea')}" if winner else "No in-budget offer found")
                ),
            }
            return EnrichmentResult(column=self.name, value=value, source=result.provider, confidence=0.75)
        except Exception as e:
            return EnrichmentResult(column=self.name, value=None, source="error", notes=str(e))
