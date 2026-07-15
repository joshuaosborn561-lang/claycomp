from claycomp.enrichers.area_nickname import AreaNicknameEnricher
from claycomp.enrichers.base import Enricher
from claycomp.enrichers.baseball_team import BaseballTeamEnricher
from claycomp.enrichers.custom_prompt import CustomPromptEnricher
from claycomp.enrichers.email_waterfall import EmailWaterfallEnricher
from claycomp.enrichers.google_review import GoogleReviewEnricher
from claycomp.enrichers.name_normalizer import NameNormalizerEnricher
from claycomp.enrichers.restaurant import RestaurantEnricher

ENRICHERS: dict[str, type[Enricher]] = {
    "name": NameNormalizerEnricher,
    "area": AreaNicknameEnricher,
    "baseball": BaseballTeamEnricher,
    "restaurant": RestaurantEnricher,
    "review": GoogleReviewEnricher,
    "email_waterfall": EmailWaterfallEnricher,
}

DEFAULT_PIPELINE = ["name", "area", "baseball", "restaurant", "review"]


def get_enricher(
    name: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    custom_prompt: str | None = None,
    column_name: str | None = None,
    business_context: str | None = None,
    cac_limit_usd: float | None = None,
    email_providers: list[str] | None = None,
) -> Enricher:
    _ = (business_context, cac_limit_usd)

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
    if name in ("name", "area"):
        return cls(provider=provider, model=model)
    if name == "email_waterfall":
        return EmailWaterfallEnricher(providers=email_providers)
    return cls()


def get_enrichers(names: list[str], **kwargs) -> list[Enricher]:
    return [get_enricher(n, **kwargs) for n in names]
