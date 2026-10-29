from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "Cygnus"
    assert body["status"] in {"ok", "degraded"}
    assert body["retailer_mode"] == "simulated"


def test_health_never_leaks_key():
    assert "api_key" not in client.get("/api/health").text.lower()


def test_ai_ping_without_key_is_clear_503(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "nebius_api_key", None)
    r = client.post("/api/ai/ping")
    assert r.status_code == 503
    assert "NEBIUS_API_KEY" in r.json()["detail"]
