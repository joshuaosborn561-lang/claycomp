from __future__ import annotations

from claycomp.enrichers.base import Enricher
from claycomp.llm import LLMMessage, llm_complete
from claycomp.models import EnrichmentResult, Record


class CustomPromptEnricher(Enricher):
    """AI column with a user- or Sculptor-defined prompt."""

    def __init__(
        self,
        column_name: str,
        prompt: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        description: str = "Custom AI enrichment",
    ):
        self.name = column_name
        self.description = description
        self.prompt = prompt
        self.provider = provider
        self.model = model
        self.requires_api_key = None

    def output_column(self) -> str:
        return self.name

    async def enrich(self, record: Record) -> EnrichmentResult:
        context = {
            "name": record.display_name(),
            "email": record.email,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "title": record.title,
            "company": record.company,
            "city": record.city,
            "state": record.state,
            "country": record.country,
            "location": record.display_location(),
            "enriched": record.enriched,
        }

        user_content = f"Lead data:\n{context}\n\nTask: {self.prompt}\n\nReturn only the enrichment result."

        try:
            result = await llm_complete(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "You enrich lead data for cold outreach. "
                            "Return a concise, useful value. JSON only if the task asks for structured data."
                        ),
                    ),
                    LLMMessage(role="user", content=user_content),
                ],
                provider=self.provider,
                model=self.model,
                temperature=0.3,
                max_tokens=300,
            )
            value = (result.content or "").strip()
            return EnrichmentResult(
                column=self.name,
                value=value,
                source=result.provider,
                confidence=0.8,
            )
        except Exception as e:
            return EnrichmentResult(column=self.name, value=None, source="error", notes=str(e))
