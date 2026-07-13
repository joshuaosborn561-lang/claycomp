from __future__ import annotations

from abc import ABC, abstractmethod

from claycomp.models import EnrichmentResult, Record


class Enricher(ABC):
    """Base class for all enrichment columns."""

    name: str
    description: str
    requires_api_key: str | None = None  # e.g. "OPENAI_API_KEY"

    @abstractmethod
    async def enrich(self, record: Record) -> EnrichmentResult:
        ...

    def output_column(self) -> str:
        return self.name
