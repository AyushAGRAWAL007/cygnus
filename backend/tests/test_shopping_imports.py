"""Isolated synthetic interchange and metadata-only retailer discovery checks."""
import json
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from app.db import connect
from app.imports.amazon import parse_upload
from app.imports.models import Order
from app.integrations.mail_parser import detected_retailer, parse_message
from app.integrations.retailers import catalogue
from .test_amazon_import import payload, record
from .test_import_service import client, HEADERS, confirm, register, upload
from .test_gmail import google, connect_gmail, message
from .test_shopping import client as shopping_client


def test_authoritative_optional_amounts_and_categories():
    parsed = parse_upload(payload(record(total_amount="2900.25", payment_status="paid", items=[{"product_name": "Kettle", "quantity": 2, "unit_price": "100", "category": "Kitchen"}])))
    order = parsed.orders[0]
    assert order.total_amount == Decimal("2900.25")
    assert order.payment_status == "paid" and order.items[0].category == "Kitchen"
    assert parse_upload(payload(record())).orders[0].total_amount is None
    for invalid in ["NaN", "-1", "1.12345"]:
        assert parse_upload(payload(record(total_amount=invalid))).issues
    csv = b"Order ID,Order Date,Product Name,Marketplace,Currency,Total Amount,Payment Status,Category\n123-1234567-1234567,2026-10-01,Kettle,amazon.in,INR,12.25,paid,Kitchen\n"
    order = parse_upload(csv).orders[0]
    assert order.total_amount == Decimal("12.25") and order.items[0].category == "Kitchen"


def test_registry_is_honest_and_normalized_contract_extensible():
    assert [r["id"] for r in catalogue()] == ["amazon", "flipkart", "myntra", "meesho", "ajio", "other"]
    assert [r["id"] for r in catalogue() if r["extraction_supported"]] == ["amazon"]
    assert Order(retailer="Flipkart", external_order_id="OD-123", marketplace="flipkart.com").external_order_id == "OD-123"
    with pytest.raises(ValidationError):
        Order(external_order_id="OD-123")
    with pytest.raises(ValidationError):
        Order(retailer="Flipkart", external_order_id="unsafe\nID")
    for domain, retailer in [("flipkart.com", "flipkart"), ("myntra.com", "myntra"), ("meesho.com", "meesho"), ("ajio.com", "ajio")]:
        synthetic = message(sender="orders@" + domain)
        assert detected_retailer(synthetic) == retailer
        assert parse_message(synthetic) is None
        assert detected_retailer(message(sender="orders@" + domain + ".evil.example")) is None


def test_schema_002_preserves_import_compatibility(client):
    preview = upload(client, payload(record(total_amount="500", payment_status="paid"))).json()
    assert confirm(client, preview).json()["imported"] == 1


def test_schema_003_persists_authoritative_fields_and_leaves_unknowns(client):
    # Schema capability detection is independent of migration orchestration.
    with connect() as conn:
        conn.execute("ALTER TABLE orders ADD COLUMN total_amount TEXT")
        conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT")
        conn.execute("ALTER TABLE order_items ADD COLUMN category TEXT")
    preview = upload(client, payload(record(total_amount="12.25", payment_status="paid", items=[{"product_name":"Kettle", "quantity": 2, "unit_price":"100", "category":"Kitchen"}]))).json()
    assert confirm(client, preview).json()["imported"] == 1
    preview = upload(client, payload(record(order_id="124-1234567-1234567"))).json()
    assert confirm(client, preview).json()["imported"] == 1
    with connect() as conn:
        rows = conn.execute("SELECT total_amount,payment_status FROM orders WHERE simulated=0 ORDER BY external_order_id").fetchall()
        assert [tuple(r) for r in rows] == [("12.25", "paid"), (None, None)]
        assert conn.execute("SELECT category FROM order_items WHERE category IS NOT NULL").fetchone()[0] == "Kitchen"


def test_unsupported_retailer_sync_fetches_metadata_only(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    formats = []
    def call(method, url, **kwargs):
        if url.endswith("/messages/m1"):
            formats.append(kwargs["params"]["format"])
            return httpx.Response(200, json=message(sender="orders@flipkart.com"))
        return original(method, url, **kwargs)
    monkeypatch.setattr(gmail, "call", call)
    result = client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).json()
    assert formats == ["metadata"]
    assert result["unsupported"] == 1 and result["extracted"] == 0
    assert result["preview"]["orders"] == []
    with connect() as conn:
        row = conn.execute("SELECT outcome,observation_json FROM gmail_messages").fetchone()
        assert row["outcome"] == "unsupported"
        assert json.loads(row["observation_json"]) == {"retailer":"flipkart"}
    # Recovery must never try parsing unsupported metadata as an Order.
    assert client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).status_code == 200


def test_sync_preview_confirmation_ownership_and_file_dedup_no_returns(client, google):
    connect_gmail(client)
    preview = client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).json()["preview"]
    assert client.get(f"/api/imports/{preview['id']}").status_code == 200
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders WHERE simulated=0").fetchone()[0] == 0
        before_returns = conn.execute("SELECT COUNT(*) FROM return_cases").fetchone()[0]
    assert confirm(client, preview, acknowledge_review=True).json()["imported"] == 1
    duplicate = upload(client, payload(record(items=[{"product_name":"Test kettle", "quantity":1,"unit_price":"1299.50"}]))).json()
    assert duplicate["counts"]["duplicates"] == 1
    assert confirm(client, duplicate, acknowledge_review=True).json()["skipped"] == 1
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders WHERE simulated=0").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM return_cases").fetchone()[0] == before_returns
        assert conn.execute("SELECT COUNT(DISTINCT source) FROM order_source_references").fetchone()[0] == 2
    register(client, "different-owner@example.com")
    assert client.get(f"/api/imports/{preview['id']}").status_code == 404
    assert confirm(client, preview, acknowledge_review=True).status_code == 404


def test_refresh_denial_keeps_diagnostic_until_explicit_disconnect(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    with connect() as conn:
        conn.execute("UPDATE integration_credentials SET expires_at='2000-01-01'")
    monkeypatch.setattr(gmail, "call", lambda method, url, **kwargs: httpx.Response(400, json={"error":"invalid_grant"}) if url.endswith("/token") else original(method, url, **kwargs))
    assert client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).status_code == 409
    status = client.get("/api/integrations/gmail").json()
    assert status["status"] == "reauthorization_required"
    assert status["error_code"] == "authorization_expired"
    assert client.post("/api/integrations/gmail/disconnect", headers=HEADERS, json={}).status_code == 200
    assert client.get("/api/integrations/gmail").json()["status"] == "disconnected"


def test_duplicate_review_enriches_only_unknown_finance_and_categories(client, google):
    with connect() as conn:
        conn.execute("ALTER TABLE orders ADD COLUMN total_amount TEXT")
        conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT")
        conn.execute("ALTER TABLE order_items ADD COLUMN category TEXT")
    connect_gmail(client)
    preview = client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).json()["preview"]
    assert confirm(client, preview, acknowledge_review=True).json()["imported"] == 1
    data = payload(record(total_amount="1375.25", payment_status="paid", items=[{"product_name":"Test kettle", "quantity":1, "unit_price":"1299.50", "category":"Kitchen"}]))
    preview = upload(client, data).json()
    assert preview["counts"]["duplicates"] == 1 and preview["counts"]["review"] == 1
    assert confirm(client, preview).status_code == 409
    with connect() as conn:
        before = conn.execute("SELECT id,total_amount FROM orders WHERE simulated=0").fetchone()
        assert before["total_amount"] is None
        item_ids = [r[0] for r in conn.execute("SELECT id FROM order_items WHERE order_id=?", (before["id"],))]
    assert confirm(client, preview, acknowledge_review=True).json()["skipped"] == 1
    contradiction = upload(client, payload(record(total_amount="999", payment_status="unpaid", items=[{"product_name":"Test kettle", "quantity":1, "unit_price":"1299.50", "category":"Other"}]))).json()
    assert contradiction["orders"][0]["conflict"] is True
    assert confirm(client, contradiction).status_code == 409
    assert confirm(client, contradiction, acknowledge_review=True).json()["skipped"] == 1
    with connect() as conn:
        row = conn.execute("SELECT total_amount,payment_status FROM orders WHERE id=?", (before["id"],)).fetchone()
        assert tuple(row) == ("1375.25", "paid")
        items = conn.execute("SELECT id,category FROM order_items WHERE order_id=?", (before["id"],)).fetchall()
        assert [r["id"] for r in items] == item_ids and items[0]["category"] == "Kitchen"
        assert conn.execute("SELECT COUNT(*) FROM order_source_references WHERE order_id=?", (before["id"],)).fetchone()[0] == 3


@pytest.mark.parametrize("damaged", [None, "amount", "currency"])
def test_duplicate_total_enrichment_preserves_refund_invariant(shopping_client, damaged):
    client = shopping_client
    preview = upload(client).json()
    assert confirm(client, preview).json()["imported"] == 1
    with connect() as conn:
        order_id = conn.execute("SELECT id FROM orders WHERE simulated=0").fetchone()[0]
    endpoint = f"/api/shopping/orders/{order_id}/refunds"
    for index, (value, status) in enumerate([("60", "pending"), ("40", "received")]):
        response = client.post(endpoint, headers=HEADERS, json={"amount":value, "currency":"INR", "status":status, "effective_date":"2026-10-02", "reference":f"refund-{index}", "confirm_received":status == "received"})
        assert response.status_code == 200, response.text
    with connect() as conn:
        if damaged == "amount":
            conn.execute("UPDATE refunds SET amount='NaN' WHERE reference='refund-0'")
        elif damaged == "currency":
            conn.execute("UPDATE refunds SET currency='USD' WHERE reference='refund-0'")
        before_refunds = [tuple(r) for r in conn.execute("SELECT * FROM refunds ORDER BY id")]
        before_sources = [tuple(r) for r in conn.execute("SELECT * FROM order_source_references ORDER BY id")]
    preview = upload(client, payload(record(total_amount="50", payment_status="paid"))).json()
    response = confirm(client, preview, acknowledge_review=True)
    assert response.status_code == 409, response.text
    with connect() as conn:
        order = conn.execute("SELECT total_amount,payment_status FROM orders WHERE id=?", (order_id,)).fetchone()
        assert tuple(order) == (None, None)
        assert [tuple(r) for r in conn.execute("SELECT * FROM refunds ORDER BY id")] == before_refunds
        assert [tuple(r) for r in conn.execute("SELECT * FROM order_source_references ORDER BY id")] == before_sources
