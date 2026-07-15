from claycomp.enrichers.area_nickname import AreaNicknameEnricher
from claycomp.enrichers.base import Enricher
from claycomp.enrichers.baseball_team import BaseballTeamEnricher
from claycomp.enrichers.custom_prompt import CustomPromptEnricher
from claycomp.enrichers.google_review import GoogleReviewEnricher
from claycomp.enrichers.name_normalizer import NameNormalizerEnricher
from claycomp.enrichers.personal_hook import PersonalHookEnricher
from claycomp.enrichers.research_tier import ResearchTierEnricher
from claycomp.enrichers.restaurant import RestaurantEnricher
from claycomp.enrichers.unique_offer import UniqueOfferEnricher

ENRICHERS: dict[str, type[Enricher]] = {
    "name": NameNormalizerEnricher,
    "area": AreaNicknameEnricher,
    "baseball": BaseballTeamEnricher,
    "restaurant": RestaurantEnricher,
    "review": GoogleReviewEnricher,
    "research_tier": ResearchTierEnricher,
    "personal_hook": PersonalHookEnricher,
    "unique_offer": UniqueOfferEnricher,
}

DEFAULT_PIPELINE = ["name", "area", "baseball", "restaurant", "review"]

HIGH_TOUCH_PIPELINE = ["research_tier", "personal_hook", "unique_offer"]


def get_enricher(
    name: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    custom_prompt: str | None = None,
    column_name: str | None = None,
    business_context: str | None = None,
    cac_limit_usd: float | None = None,
) -> Enricher:
    if name == "custom" and custom_prompt and column_name:
        return CustomPromptEnricher(
            column_name=column_name,
            prompt=custom_prompt,
            provider=provider,
            model=model,
        )

    if name not in ENRICHERS:
        available = ", ".join(ENRICHERS)
        raise ValueError(f"Unknown enricher '{name}'. Available: {available}")

    cls = ENRICHERS[name]
    if name in ("name", "area", "research_tier", "personal_hook"):
        return cls(provider=provider, model=model)
    if name == "unique_offer":
        return UniqueOfferEnricher(
            provider=provider,
            model=model,
            cac_limit_usd=float(cac_limit_usd or 200),
            business_context=business_context,
        )
    return cls()


def get_enrichers(names: list[str], **kwargs) -> list[Enricher]:
    return [get_enricher(n, **kwargs) for n in names]
