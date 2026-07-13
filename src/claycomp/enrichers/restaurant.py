from __future__ import annotations

from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record
from claycomp.utils.geo import google_places_search


class RestaurantEnricher(Enricher):
    name = "nearest_nice_restaurant"
    description = "Find a well-rated restaurant near their location"
    requires_api_key = "GOOGLE_PLACES_API_KEY"

    async def enrich(self, record: Record) -> EnrichmentResult:
        location = record.display_location()
        if not location:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no location")

        places = await google_places_search(
            "highly rated restaurant",
            location=location,
            place_type="restaurant",
        )

        if not places:
            return EnrichmentResult(
                column=self.name,
                value=None,
                source="no_results",
                notes="set GOOGLE_PLACES_API_KEY for live results",
            )

        # Pick highest rated with enough reviews
        rated = [p for p in places if p.get("rating") and (p.get("review_count") or 0) >= 50]
        best = max(rated or places, key=lambda p: p.get("rating") or 0)

        return EnrichmentResult(
            column=self.name,
            value={
                "name": best["name"],
                "rating": best["rating"],
                "review_count": best.get("review_count"),
                "address": best.get("address"),
                "talking_point": f"{best['name']} ({best['rating']}★)",
            },
            source="google_places",
            confidence=0.8,
        )
