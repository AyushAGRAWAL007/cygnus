"""Cygnus API entry point (FastAPI).

FastAPI = the server. The browser sends it a request ("is the backend alive?"),
a Python function runs, and the result goes back as JSON.
"""
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ai import nebius
from .config import get_settings
from .db import check_database

VERSION = "0.1.0"
settings = get_settings()

app = FastAPI(title="Cygnus API", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Is the server up, is the database reachable, is AI configured?
    Never returns the API key itself, only whether one exists."""
    db_ok = check_database()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "version": VERSION,
        "environment": settings.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": "ok" if db_ok else "error",
        "ai": {
            "provider": "Nebius Token Factory",
            "configured": settings.ai_configured,
            "model": settings.nebius_model_id,
        },
        # Cygnus has no real retailer integration yet. Say so explicitly.
        "retailer_mode": "simulated",
    }


@app.get("/api/ai/models")
def ai_models() -> dict:
    """Lists NVIDIA models your Nebius key can call (use it to confirm the model id)."""
    try:
        return {"nvidia_models": nebius.list_nvidia_model_ids()}
    except nebius.AINotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # network/auth errors from the provider
        raise HTTPException(status_code=502, detail=f"Nebius request failed: {type(e).__name__}: {e}")


@app.post("/api/ai/ping")
def ai_ping() -> dict:
    """One real inference call to prove the NVIDIA-model-via-Nebius path works."""
    try:
        return nebius.ping()
    except nebius.AINotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Nebius request failed: {type(e).__name__}: {e}")
