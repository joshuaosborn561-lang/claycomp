from __future__ import annotations

from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record
from claycomp.utils.geo import google_places_search


class GoogleReviewEnricher(Enricher):
    name = "company_google_review"
    description = "Pull Google rating/review summary for their company"
    requires_api_key = "GOOGLE_PLACES_API_KEY"

    async def enrich(self, record: Record) -> EnrichmentResult:
        company = record.company
        location = record.display_location()
        if not company:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no company")

        query = f"{company} {location}" if location else company
        places = await google_places_search(query, location=location)

        if not places:
            return EnrichmentResult(
                column=self.name,
                value=None,
                source="no_results",
                notes="set GOOGLE_PLACES_API_KEY for live results",
            )

        best = places[0]
        rating = best.get("rating")
        count = best.get("review_count") or 0

        snippet = None
        if rating and count:
            if rating >= 4.5:
                snippet = f"impressive {rating}★ rating with {count:,} reviews"
            elif rating >= 4.0:
                snippet = f"solid {rating}★ on Google ({count:,} reviews)"
            else:
                snippet = f"{rating}★ on Google"

        return EnrichmentResult(
            column=self.name,
            value={
                "name": best["name"],
                "rating": rating,
                "review_count": count,
                "snippet": snippet,
            },
            source="google_places",
            confidence=0.75,
        )
