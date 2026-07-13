from __future__ import annotations

import os

STORAGE_SETUP_MESSAGE = (
    "Supabase storage is not ready. In your Supabase project open SQL Editor and run "
    "supabase/migrations/20260713000000_claycomp_schema.sql from the Claycomp repo. "
    "Ensure Vercel has SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, then redeploy."
)


def supabase_credentials() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if url and key:
        return url.rstrip("/"), key
    return None


def redis_credentials() -> tuple[str, str] | None:
    url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    if url and token:
        return url, token
    return None


def supabase_configured() -> bool:
    return supabase_credentials() is not None


def redis_configured() -> bool:
    return redis_credentials() is not None


def storage_backend() -> str:
    if supabase_configured():
        return "supabase"
    if redis_configured():
        return "upstash"
    if os.getenv("VERCEL"):
        return "unconfigured"
    return "file"
