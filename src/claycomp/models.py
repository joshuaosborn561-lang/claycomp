from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Record(BaseModel):
    """A single lead row from Apollo or similar."""

    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    company: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    enriched: dict[str, Any] = Field(default_factory=dict)

    def display_name(self) -> str:
        if self.full_name:
            return self.full_name
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else self.email or self.id

    def display_location(self) -> str | None:
        if self.location:
            return self.location
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts) if parts else None

    def get_enriched(self, key: str, default: Any = None) -> Any:
        return self.enriched.get(key, default)

    def set_enriched(self, key: str, value: Any) -> None:
        self.enriched[key] = value


class EnrichmentResult(BaseModel):
    column: str
    value: Any
    source: str = "unknown"
    confidence: float | None = None
    notes: str | None = None
