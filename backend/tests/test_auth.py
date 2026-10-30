"""Auth integration tests; all schema and writes are isolated under tmp_path."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import runpy

import pytest
from fastapi.testclient import TestClient
from argon2 import PasswordHasher

from app import main, returns
from app.config import get_settings
from app.db import connect

HEADERS = {"Origin": "http://localhost:5173", "X-Cygnus-CSRF": "1"}
PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "database_path", str(tmp_path / "auth.db"))
    monkeypatch.setattr(get_settings(), "app_env", "development")
    returns.initialize()
    script = Path(__file__).resolve().parents[1] / "migrations/001_customer_ownership.py"
    runpy.run_path(str(script))["migrate"](tmp_path / "auth.db")
    if hasattr(main.app.state, "limiter"):
        main.app.state.limiter.reset()
    with TestClient(main.app) as test_client:
        yield test_client


def register(client, email="person@example.com", **extra):
    return client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Person", **extra}, headers=HEADERS)


@pytest.mark.parametrize("length,accepted", [(7, False), (8, True), (128, True), (129, False)])
def test_registration_password_length_limits(length, accepted):
    from pydantic import ValidationError
    from app.auth import Registration

    data = {"email": "length@example.com", "display_name": "Person", "password": "x" * length}
    if accepted:
        assert Registration(**data).password.get_secret_value() == data["password"]
    else:
        with pytest.raises(ValidationError):
            Registration(**data)


def test_registration_hashes_password_and_session_and_claims_demo_once(client):
    response = register(client)
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "email", "display_name", "email_verified"}
    assert user["email_verified"] is False
    token = client.cookies.get("cygnus_session")
    assert token and len(token) >= 43
    assert PASSWORD not in response.text and token not in response.text
    with connect() as conn:
        password_hash = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        assert password_hash.startswith("$argon2id$")
        assert PasswordHasher().verify(password_hash, PASSWORD)
        assert conn.execute("SELECT token_hash FROM sessions").fetchone()[0] == hashlib.sha256(token.encode()).hexdigest()
        assert conn.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (user["id"],)).fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM orders WHERE simulated=1").fetchone()[0] == 4
    assert register(client, "other@example.com").status_code == 201
    with connect() as conn:
        assert conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM app_metadata WHERE key='demo_data_owner'").fetchone()[0] == 1


def test_duplicate_email_is_case_insensitive(client):
    assert register(client).status_code == 201
    assert register(client, "PERSON@EXAMPLE.COM").status_code == 409
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("overrides", [{"email": "invalid"}, {"password": "short"}, {"password": "x" * 129}, {"display_name": "  "}, {"user_id": "injected"}])
def test_registration_validation_redacts_sensitive_input(client, overrides):
    response = register(client, **overrides)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    if "password" in overrides:
        assert overrides["password"] not in response.text
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_login_rotates_and_logout_revokes(client):
    assert register(client).status_code == 201
    old_token = client.cookies.get("cygnus_session")
    login = client.post("/api/auth/login", json={"email": "PERSON@example.com", "password": PASSWORD}, headers=HEADERS)
    assert login.status_code == 200
    new_token = client.cookies.get("cygnus_session")
    assert new_token != old_token
    assert client.get("/api/auth/me").json()["email"] == "person@example.com"
    with connect() as conn:
        assert conn.execute("SELECT revoked_at FROM sessions WHERE token_hash=?", (hashlib.sha256(old_token.encode()).hexdigest(),)).fetchone()[0]
    response = client.post("/api/auth/logout", json={}, headers=HEADERS)
    assert response.status_code == 200
    assert not client.cookies.get("cygnus_session")
    client.cookies.set("cygnus_session", new_token)
    assert client.get("/api/auth/me").status_code == 401


def test_login_errors_are_generic(client):
    register(client)
    responses = [client.post("/api/auth/login", json={"email": email, "password": "incorrect password"}, headers=HEADERS) for email in ["person@example.com", "unknown@example.com"]]
    assert [r.status_code for r in responses] == [401, 401]
    assert responses[0].json() == responses[1].json()
    assert "incorrect password" not in responses[0].text


@pytest.mark.parametrize("state", ["missing", "invalid", "expired", "inactive", "revoked"])
def test_session_identity_rejects_invalid_states(client, state):
    if state in {"expired", "inactive", "revoked"}:
        register(client)
        with connect() as conn:
            if state == "expired":
                conn.execute("UPDATE sessions SET expires_at=?", ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
            elif state == "inactive":
                conn.execute("UPDATE users SET is_active=0")
            else:
                conn.execute("UPDATE sessions SET revoked_at=?", (datetime.now(timezone.utc).isoformat(),))
    elif state == "invalid":
        client.cookies.set("cygnus_session", "invalid")
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("environment,secure", [("development", False), ("production", True)])
def test_cookie_security(client, monkeypatch, environment, secure):
    monkeypatch.setattr(get_settings(), "app_env", environment)
    response = register(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert ("secure" in cookie) == secure
    assert "domain=" not in cookie
    assert "max-age=28800" in cookie
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example", "X-Cygnus-CSRF": "1"}, {"Origin": "http://localhost:5173"}, {"Origin": "null", "X-Cygnus-CSRF": "1"}])
def test_auth_csrf_rejects_missing_header_or_untrusted_origin(client, headers):
    response = client.post("/api/auth/register", json={"email": "person@example.com", "password": PASSWORD, "display_name": "Person"}, headers=headers)
    assert response.status_code == 403


def test_cookie_authenticated_mutations_require_csrf(client):
    register(client)
    response = client.post("/api/returns/eligibility", json={"order_id": "demo-order-002", "item_id": "item-coat-002", "reason": "wrong_size"})
    assert response.status_code == 403
    assert client.post("/api/returns/eligibility", json={"order_id": "demo-order-002", "item_id": "item-coat-002", "reason": "wrong_size"}, headers=HEADERS).status_code == 200


def test_auth_schema_is_not_created_automatically(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "database_path", str(tmp_path / "unmigrated.db"))
    returns.initialize()
    assert register(client).status_code == 503
    with connect() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone() is None


def test_login_is_throttled(client):
    statuses = [client.post("/api/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}, headers=HEADERS).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[-1] == 429


def test_concurrent_registrations_claim_demo_once(client):
    def create(email):
        with TestClient(main.app) as separate:
            return register(separate, email)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, ["one@example.com", "two@example.com"]))
    assert sorted(r.status_code for r in responses) == [201, 201]
    with connect() as conn:
        assert conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("path", ["/api/orders", "/api/orders/demo-order-001", "/api/returns", "/api/returns/case-demo-001", "/api/activity", "/api/ai/models"])
def test_customer_routes_require_authentication(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path,payload", [
    ("/api/returns/eligibility", {"order_id": "demo-order-002", "item_id": "item-coat-002", "reason": "wrong_size"}),
    ("/api/returns", {"order_id": "demo-order-002", "item_id": "item-coat-002", "reason": "wrong_size"}),
    ("/api/returns/case-demo-001/pickup/schedule", {"pickup_date": "2099-01-01"}),
    ("/api/returns/case-demo-001/pickup/missed", {}),
    ("/api/returns/case-demo-001/availability", {"availability": "Weekdays after 5 PM"}),
    ("/api/returns/case-demo-001/pickup/reschedule", {"pickup_date": "2099-01-01"}),
    ("/api/returns/case-demo-001/simulate/advance", {"to_status": "picked_up"}),
    ("/api/ai/chat", {"message": "Explain this case", "case_id": "case-demo-001"}),
])
def test_other_customer_mutations_and_ai_are_hidden(client, path, payload):
    register(client)
    register(client, "other@example.com")
    response = client.post(path, json=payload, headers=HEADERS)
    assert response.status_code == 404


def test_other_customer_lists_and_details_are_isolated(client):
    register(client)
    register(client, "other@example.com")
    for path in ["/api/orders", "/api/returns", "/api/activity"]:
        assert client.get(path).json()["items"] == []
    for path in ["/api/orders/demo-order-001", "/api/returns/case-demo-001", "/api/returns?order_id=demo-order-001"]:
        assert client.get(path).status_code == 404


def test_concurrent_duplicate_returns_create_only_one_case(client):
    register(client)
    token = client.cookies.get("cygnus_session")
    def create(_):
        with TestClient(main.app) as separate:
            separate.cookies.set("cygnus_session", token)
            return separate.post("/api/returns", json={"order_id": "demo-order-002", "item_id": "item-coat-002", "reason": "wrong_size"}, headers=HEADERS)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, [1,2]))
    assert sorted(r.status_code for r in responses) == [201,409]


@pytest.mark.parametrize("path", ["/api/ai/models", "/api/ai/ping"])
def test_nebius_provider_errors_are_sanitized(client, monkeypatch, path):
    register(client)
    def fail():
        raise RuntimeError("private provider body fake-secret")
    name = "list_nvidia_model_ids" if path.endswith("models") else "ping"
    monkeypatch.setattr(main.nebius, name, fail)
    response = client.get(path) if path.endswith("models") else client.post(path, json={}, headers=HEADERS)
    assert response.status_code == 502
    assert "private provider" not in response.text and "fake-secret" not in response.text


def test_private_responses_are_not_cached(client):
    register(client)
    assert client.get("/api/orders").headers["cache-control"] == "no-store"


def test_logout_does_not_revoke_without_csrf(client):
    register(client)
    response = client.post("/api/auth/logout", json={})
    assert response.status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_wrong_content_type_rejected_even_with_origin_and_custom_header(client):
    response = client.post("/api/auth/login", content='{}', headers={**HEADERS, "Content-Type": "text/plain"})
    assert response.status_code == 403


def test_cors_allows_only_explicit_credentialed_origin(client):
    headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-cygnus-csrf"}
    allowed = client.options("/api/auth/login", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == headers["Origin"]
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert client.options("/api/auth/login", headers={**headers, "Origin": "https://evil.example"}).status_code == 400


def test_failed_registration_rolls_back_demo_claim(client, monkeypatch):
    from app import auth
    def fail(*args):
        raise RuntimeError("injected session failure")
    monkeypatch.setattr(auth, "new_session", fail)
    with pytest.raises(RuntimeError, match="injected session failure"):
        register(client)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM app_metadata").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM orders WHERE user_id IS NOT NULL").fetchone()[0] == 0


def test_google_only_identity_is_never_linked_by_email(client):
    with connect() as conn:
        conn.execute("INSERT INTO users(id,email,display_name,created_at) VALUES ('google-only','google@example.com','Google','2026-10-30')")
        conn.execute("INSERT INTO auth_identities(id,user_id,provider,provider_subject,created_at) VALUES ('identity','google-only','google','stable-subject','2026-10-30')")
    assert register(client, "google@example.com").status_code == 409
    response = client.post("/api/auth/login", json={"email": "google@example.com", "password": PASSWORD}, headers=HEADERS)
    assert response.status_code == 401
    with connect() as conn:
        assert conn.execute("SELECT password_hash FROM users WHERE id='google-only'").fetchone()[0] is None
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
