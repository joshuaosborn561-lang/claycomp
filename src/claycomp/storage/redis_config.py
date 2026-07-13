from __future__ import annotations

import os


def redis_credentials() -> tuple[str, str] | None:
    url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    if url and token:
        return url, token
    return None


def redis_configured() -> bool:
    return redis_credentials() is not None


def storage_backend() -> str:
    if redis_configured():
        return "upstash"
    if os.getenv("VERCEL"):
        return "unconfigured"
    return "file"
