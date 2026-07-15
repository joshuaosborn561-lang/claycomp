from __future__ import annotations

from claycomp.email_finder.waterfall import DEFAULT_PROVIDERS, run_email_waterfall
from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record


class EmailWaterfallEnricher(Enricher):
    name = "email_waterfall"
    description = "Email finder waterfall (AI Ark → Prospeo by default)"
    requires_api_key = "AI_ARK_API_KEY"

    def __init__(self, providers: list[str] | None = None):
        self.providers = providers or list(DEFAULT_PROVIDERS)

    async def enrich(self, record: Record) -> EnrichmentResult:
        try:
            value = await run_email_waterfall(record, self.providers)
            return EnrichmentResult(
                column=self.name,
                value=value,
                source=value.get("provider") or "waterfall",
                confidence=0.9 if value.get("email") else 0.2,
                notes=None if value.get("email") else value.get("skip_reason"),
            )
        except Exception as e:
            return EnrichmentResult(column=self.name, value=None, source="error", notes=str(e))
