from claycomp.enrichers.area_nickname import AreaNicknameEnricher
from claycomp.enrichers.base import Enricher
from claycomp.enrichers.baseball_team import BaseballTeamEnricher
from claycomp.enrichers.google_review import GoogleReviewEnricher
from claycomp.enrichers.name_normalizer import NameNormalizerEnricher
from claycomp.enrichers.restaurant import RestaurantEnricher

ENRICHERS: dict[str, type[Enricher]] = {
    "name": NameNormalizerEnricher,
    "area": AreaNicknameEnricher,
    "baseball": BaseballTeamEnricher,
    "restaurant": RestaurantEnricher,
    "review": GoogleReviewEnricher,
}

# Default pipeline — good starting point for outreach personalization
DEFAULT_PIPELINE = ["name", "area", "baseball", "restaurant", "review"]


def get_enricher(name: str) -> Enricher:
    if name not in ENRICHERS:
        available = ", ".join(ENRICHERS)
        raise ValueError(f"Unknown enricher '{name}'. Available: {available}")
    return ENRICHERS[name]()


def get_enrichers(names: list[str]) -> list[Enricher]:
    return [get_enricher(n) for n in names]
