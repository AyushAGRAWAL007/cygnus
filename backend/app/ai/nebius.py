"""Thin wrapper around Nebius Token Factory.

Token Factory speaks the *OpenAI-compatible* protocol, so we use the official
`openai` Python SDK and simply point `base_url` at Nebius. The API key lives
only here on the server. This module is how Cygnus satisfies the hackathon rule
"makes a runtime call to the Token Factory inference API".
"""
import time

from openai import OpenAI

from ..config import get_settings


class AINotConfigured(RuntimeError):
    """Raised when NEBIUS_API_KEY is missing."""


def get_client() -> OpenAI:
    s = get_settings()
    if not s.ai_configured:
        raise AINotConfigured("NEBIUS_API_KEY is not set. Copy .env.example to .env and add it.")
    return OpenAI(api_key=s.nebius_api_key.get_secret_value(), base_url=s.nebius_base_url, timeout=20.0, max_retries=0)


def list_model_ids() -> list[str]:
    """Every model id this account can call (the source of truth for exact ids)."""
    with get_client() as client:
        return sorted(m.id for m in client.models.list().data)


def list_nvidia_model_ids() -> list[str]:
    return [m for m in list_model_ids() if m.lower().startswith("nvidia/")]


def ping(prompt: str = "Reply with exactly: Cygnus online") -> dict:
    """One tiny real inference call. Returns text, model and latency."""
    s = get_settings()
    start = time.perf_counter()
    with get_client() as client:
        resp = client.chat.completions.create(
            model=s.nebius_model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
            temperature=0.2,
        )
    return {
        "model": resp.model,
        "text": (resp.choices[0].message.content or "").strip(),
        "latency_ms": round((time.perf_counter() - start) * 1000),
    }
