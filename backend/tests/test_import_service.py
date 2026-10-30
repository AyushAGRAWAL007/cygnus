import json
from pathlib import Path
import runpy
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main, returns
from app.config import get_settings
from app.db import connect
from .test_amazon_import import payload, record

HEADERS = {"Origin": "http://localhost:5173", "X-Cygnus-CSRF": "1"}
MIGRATION = Path(__file__).resolve().parents[1] / "migrations/002_order_imports.py"


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "imports.db"
    monkeypatch.setattr(get_settings(), "database_path", str(path))
    returns.initialize()
    runpy.run_path(str(MIGRATION.with_name("001_customer_ownership.py")))["migrate"](path)
    runpy.run_path(str(MIGRATION))["migrate"](path)
    main.auth.limiter.reset()
    with TestClient(main.app) as c:
        register(c)
        yield c


def register(c, email="importer@example.com"):
    response = c.post("/api/auth/register", headers=HEADERS, json={"email": email, "password": "a very long test passphrase", "display_name": "Importer"})
    assert response.status_code == 201, response.text
    return response.json()


def upload(c, data=None):
    return c.post("/api/imports/amazon/preview", headers={**HEADERS, "Content-Type": "application/octet-stream"}, content=data or payload(record()))


def confirm(c, preview, **extra):
    return c.post(f"/api/imports/{preview['id']}/confirm", headers=HEADERS, json={"order_keys": [o["key"] for o in preview["orders"]], **extra})


def test_migration_preserves_relationships_and_is_repeatable(client):
    with connect() as c:
        before = c.execute("SELECT * FROM order_items ORDER BY id").fetchall()
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
    assert runpy.run_path(str(MIGRATION))["migrate"](get_settings().database_path) is False
    with connect() as c:
        assert [tuple(r) for r in c.execute("SELECT * FROM order_items ORDER BY id")] == [tuple(r) for r in before]
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_preview_confirm_and_repeated_upload_are_idempotent(client):
    response = upload(client)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["counts"]["orders"] == 1 and preview["counts"]["items"] == 1
    with connect() as c:
        assert c.execute("SELECT COUNT(*) FROM orders WHERE simulated=0").fetchone()[0] == 0
    result = confirm(client, preview)
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 1
    assert confirm(client, preview).json() == result.json()
    again = upload(client).json()
    assert again["counts"]["duplicates"] == 1
    assert confirm(client, again).json()["skipped"] == 1
    orders = client.get("/api/orders").json()["items"]
    imported = next(o for o in orders if not o["simulated"])
    assert imported["currency"] == "INR" and imported["source"] == "amazon_file"
    assert imported["items"][0]["return_window_days"] is None
    eligibility = client.post("/api/returns/eligibility", headers=HEADERS, json={"order_id": imported["id"], "item_id": imported["items"][0]["id"], "reason": "damaged"}).json()
    assert eligibility["eligible"] is False and eligibility["simulated"] is False
    assert "not verified" in " ".join(eligibility["reasons"])
    assert len(client.get("/api/imports/history").json()["items"]) == 2


def test_unknown_values_require_explicit_review_and_remain_null(client):
    preview = upload(client, payload(record(items=[{"product_name": "Mystery"}]))).json()
    assert preview["counts"]["review"] == 1
    assert confirm(client, preview).status_code == 409
    assert confirm(client, preview, acknowledge_review=True).status_code == 200
    item = next(o for o in client.get("/api/orders").json()["items"] if not o["simulated"])["items"][0]
    assert item["price"] is None and item["quantity"] is None


def test_customer_isolation_auth_csrf_and_invalid_key(client):
    preview = upload(client).json()
    assert confirm(client, preview, order_keys=["bad"]).status_code == 422
    assert client.post("/api/imports/amazon/preview", content=payload(record()), headers={"Content-Type": "application/octet-stream"}).status_code == 403
    register(client, "second@example.com")
    assert client.get(f"/api/imports/{preview['id']}").status_code == 404
    assert confirm(client, preview).status_code == 404
    assert client.get("/api/imports/history").json()["items"] == []
    client.cookies.clear()
    assert upload(client).status_code == 401


def test_conflict_does_not_overwrite_existing_order(client):
    first = upload(client).json()
    confirm(client, first)
    other = upload(client, payload(record(currency="USD"))).json()
    assert other["orders"][0]["conflict"] is True
    assert confirm(client, other).status_code == 409
    assert confirm(client, other, acknowledge_review=True).json()["skipped"] == 1
    assert next(o for o in client.get("/api/orders").json()["items"] if not o["simulated"])["currency"] == "INR"


def test_expired_preview_and_atomic_ownership_constraints(client):
    preview = upload(client).json()
    with connect() as c:
        c.execute("UPDATE import_previews SET expires_at='2000-01-01' WHERE id=?", (preview["id"],))
    assert confirm(client, preview).status_code == 410


def test_cross_source_duplicate_adds_provenance_without_new_order(client):
    from app.imports.models import Order, ParseResult
    from app.imports.service import create_preview
    preview = upload(client).json()
    confirm(client, preview)
    user = client.get("/api/auth/me").json()
    order = Order.model_validate({**preview["orders"][0]["order"], "source": "gmail", "source_reference": "message-1"})
    mail = create_preview(user["id"], "gmail", "mail-digest", ParseResult(orders=[order]))
    assert confirm(client, mail).json()["skipped"] == 1
    with connect() as c:
        assert c.execute("SELECT COUNT(*) FROM orders WHERE simulated=0").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM order_source_references").fetchone()[0] == 2


def test_sql_injection_product_name_is_data(client):
    preview = upload(client, payload(record(items=[{"product_name": "'; DROP TABLE users; --", "quantity": 1, "unit_price": "1"}]))).json()
    assert confirm(client, preview).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_imported_ai_facts_are_owned_and_do_not_invent_demo_policy(client):
    from app.ai.nvidia import build_context
    preview = upload(client).json()
    confirm(client, preview)
    order = next(o for o in client.get('/api/orders').json()['items'] if not o['simulated'])
    owner = client.get('/api/auth/me').json()['id']
    context = build_context(order_id=order['id'], user_id=owner)
    facts = ' '.join(context.facts)
    assert 'seeded demo' not in facts
    assert 'not verified' in facts
    assert '1299.50' in facts and 'INR' in facts
    assert '30 days' not in facts
    other = register(client, 'ai-other@example.com')['id']
    from app.ai.nvidia import AssistantError
    with pytest.raises(AssistantError):
        build_context(order_id=order['id'], user_id=other)


def test_same_order_in_multiple_gmail_messages_is_one_preview_entry(client):
    from app.imports.models import Order, ParseResult
    from app.imports.service import create_preview
    owner = client.get('/api/auth/me').json()['id']
    orders = [Order.model_validate({"external_order_id": '123-1234567-1234567', 'marketplace': 'amazon.in', 'order_date': '2026-10-01', 'currency': 'INR', 'source': 'gmail', 'source_reference': ref, 'items': [{'product_name': 'Cup', 'quantity': 1, 'unit_price': '10', 'currency': 'INR'}]}) for ref in ('m1','m2')]
    preview = create_preview(owner, 'gmail', 'digest', ParseResult(orders=orders))
    assert len(preview['orders']) == 1
    assert confirm(client, preview).json()['imported'] == 1
    with connect() as c:
        assert c.execute('SELECT COUNT(*) FROM order_source_references').fetchone()[0] == 2
