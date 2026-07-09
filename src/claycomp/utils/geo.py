from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path

import httpx
from geopy.geocoders import Nominatim

DATA_DIR = Path(__file__).parent.parent / "data"


@lru_cache(maxsize=256)
def geocode(location: str) -> tuple[float, float] | None:
    """Resolve a location string to (lat, lng). Cached."""
    if not location or not location.strip():
        return None
    geolocator = Nominatim(user_agent="claycomp/0.1")
    try:
        result = geolocator.geocode(location, timeout=10)
        if result:
            return (result.latitude, result.longitude)
    except Exception:
        pass
    return None


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3959  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def load_mlb_teams() -> list[dict]:
    path = DATA_DIR / "mlb_teams.json"
    return json.loads(path.read_text())


def nearest_mlb_team(lat: float, lng: float) -> dict:
    teams = load_mlb_teams()
    best = min(teams, key=lambda t: haversine_miles(lat, lng, t["lat"], t["lng"]))
    dist = haversine_miles(lat, lng, best["lat"], best["lng"])
    return {**best, "distance_miles": round(dist, 1)}


async def google_places_search(
    query: str,
    *,
    location: str | None = None,
    place_type: str | None = None,
) -> list[dict]:
    """Search Google Places (New) API. Returns [] if no API key."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return []

    body: dict = {"textQuery": query, "maxResultCount": 5}
    if location:
        coords = geocode(location)
        if coords:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": coords[0], "longitude": coords[1]},
                    "radius": 25000.0,
                }
            }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.id,places.types",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])

    results = []
    for p in places:
        if place_type and place_type not in p.get("types", []):
            continue
        results.append(
            {
                "name": p.get("displayName", {}).get("text"),
                "address": p.get("formattedAddress"),
                "rating": p.get("rating"),
                "review_count": p.get("userRatingCount"),
                "place_id": p.get("id"),
            }
        )
    return results
