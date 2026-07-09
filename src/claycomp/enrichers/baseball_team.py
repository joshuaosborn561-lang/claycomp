from __future__ import annotations

from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record
from claycomp.utils.geo import geocode, nearest_mlb_team


class BaseballTeamEnricher(Enricher):
    name = "nearest_baseball_team"
    description = "Nearest MLB team based on location"

    async def enrich(self, record: Record) -> EnrichmentResult:
        location = record.display_location()
        if not location:
            return EnrichmentResult(column=self.name, value=None, source="skip", notes="no location")

        coords = geocode(location)
        if not coords:
            return EnrichmentResult(
                column=self.name,
                value=None,
                source="geocode_failed",
                notes=f"could not geocode: {location}",
            )

        team = nearest_mlb_team(coords[0], coords[1])
        return EnrichmentResult(
            column=self.name,
            value={
                "team": team["team"],
                "city": team["city"],
                "distance_miles": team["distance_miles"],
                "talking_point": f"the {team['team'].split()[-1]}",  # e.g. "the Giants"
            },
            source="mlb_dataset",
            confidence=0.95,
        )
