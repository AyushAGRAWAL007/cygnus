"""Validate the AI path end to end from the terminal.

Run from the backend/ folder:   python scripts/check_llm.py
Success looks like: a list of nvidia/* models, then "Cygnus online" and a latency.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import nebius  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    print(f"Base URL : {s.nebius_base_url}")
    print(f"Model id : {s.nebius_model_id}")
    if not s.ai_configured:
        print("\nNEBIUS_API_KEY is not set -> cannot test a real call.")
        print("Fix: copy .env.example to .env (repo root) and paste your Token Factory key.")
        return 2
    try:
        nvidia = nebius.list_nvidia_model_ids()
        print(f"\nNVIDIA models on your account ({len(nvidia)}):")
        for m in nvidia:
            print("  -", m)
        if s.nebius_model_id not in nvidia:
            print(f"\nWARNING: {s.nebius_model_id!r} is not in that list. Copy an id exactly into .env.")
        result = nebius.ping()
        print(f"\nReply   : {result['text']}")
        print(f"Model   : {result['model']}")
        print(f"Latency : {result['latency_ms']} ms")
        return 0
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
