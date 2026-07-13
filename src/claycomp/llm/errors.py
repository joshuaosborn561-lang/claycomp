from __future__ import annotations

import re


def format_llm_error(exc: BaseException, *, provider: str | None = None) -> str:
    """Turn provider API errors into actionable user messages."""
    text = str(exc)
    lower = text.lower()

    if "insufficient_quota" in lower or "exceeded your current quota" in lower:
        name = _provider_label(provider)
        return (
            f"**{name} quota exceeded** — your API key is valid but the account has no "
            f"credits or billing set up. Add payment at the provider's billing page, or switch "
            f"to another provider in **Settings** (Perplexity, Anthropic)."
        )

    if "invalid_api_key" in lower or "incorrect api key" in lower:
        return (
            "**Invalid API key** — double-check the key in **Settings → API Keys**, "
            "or update it in your Vercel env vars."
        )

    if "rate_limit" in lower or "429" in text:
        return (
            "**Rate limited** — too many requests. Wait a minute and try again, "
            "or switch to a different provider in **Settings**."
        )

    if "not set" in lower and "api_key" in lower:
        return (
            "**API key missing** — add your key in **Settings → API Keys** "
            "or set it in Vercel environment variables."
        )

    # OpenAI-style embedded JSON: Error code: 429 - {'error': {...}}
    code = _extract_error_code(text)
    message = _extract_error_message(text)
    if code == "insufficient_quota":
        return format_llm_error(Exception(message or text), provider=provider)
    if message:
        return f"**API error:** {message}"

    return f"**Error:** {text}"


def _provider_label(provider: str | None) -> str:
    labels = {"openai": "OpenAI", "perplexity": "Perplexity", "anthropic": "Anthropic"}
    return labels.get(provider or "openai", "AI provider")


def _extract_error_code(text: str) -> str | None:
    m = re.search(r"'code':\s*'([^']+)'", text)
    return m.group(1) if m else None


def _extract_error_message(text: str) -> str | None:
    m = re.search(r"'message':\s*'([^']+)'", text)
    if m:
        return m.group(1)
    m = re.search(r'"message":\s*"([^"]+)"', text)
    return m.group(1) if m else None
