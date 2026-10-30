"""Real auth setup for existing API contract tests; no auth dependency bypass."""
from pathlib import Path
import runpy

from app.auth import limiter
from app.config import get_settings


def sign_in_demo(client):
    script = Path(__file__).resolve().parents[1] / "migrations/001_customer_ownership.py"
    runpy.run_path(str(script))["migrate"](get_settings().database_path)
    limiter.reset()
    client.headers.update({"Origin": "http://localhost:5173", "X-Cygnus-CSRF": "1", "Content-Type": "application/json"})
    response = client.post("/api/auth/register", json={"email": "demo@example.com", "password": "testing a long demo passphrase", "display_name": "Demo"})
    assert response.status_code == 201, response.text
