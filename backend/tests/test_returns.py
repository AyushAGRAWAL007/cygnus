from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "database_path", str(tmp_path / "cygnus.db"))
    with TestClient(app) as test_client:
        yield test_client


def eligibility_payload(order_id="demo-order-002", item_id="item-coat-002"):
    return {"order_id": order_id, "item_id": item_id, "reason": "wrong_size"}


def test_seeded_orders_and_return_cases_are_labelled_simulated(client):
    orders = client.get("/api/orders")
    cases = client.get("/api/returns")

    assert orders.status_code == 200
    assert orders.json()["simulated"] is True
    assert {order["id"] for order in orders.json()["items"]} >= {"demo-order-001"}
    assert cases.status_code == 200
    assert cases.json()["simulated"] is True
    assert any(case["id"] == "case-demo-001" for case in cases.json()["items"])


def test_eligibility_returns_clear_reasons(client):
    eligible = client.post("/api/returns/eligibility", json=eligibility_payload())
    expired = client.post(
        "/api/returns/eligibility",
        json=eligibility_payload("demo-order-003", "item-old-003"),
    )
    final_sale = client.post(
        "/api/returns/eligibility",
        json=eligibility_payload("demo-order-004", "item-final-004"),
    )

    assert eligible.status_code == 200
    assert eligible.json() == {"eligible": True, "reasons": [], "simulated": True}
    assert expired.status_code == 200
    assert expired.json()["eligible"] is False
    assert "return window has expired" in expired.json()["reasons"]
    assert final_sale.status_code == 200
    assert "item is final sale" in final_sale.json()["reasons"]


def test_return_creation_and_case_detail_follow_contract(client):
    created = client.post("/api/returns", json=eligibility_payload())

    assert created.status_code == 201
    case = created.json()
    assert case["status"] == "requested"
    assert case["resolved"] is False
    assert case["simulated"] is True
    assert case["events"][0]["type"] == "return_requested"
    assert case["events"][0]["simulated"] is True
    assert client.get(f"/api/returns/{case['id']}").json() == case


def test_ineligible_return_cannot_be_created(client):
    response = client.post(
        "/api/returns",
        json=eligibility_payload("demo-order-004", "item-final-004"),
    )

    assert response.status_code == 409
    assert "item is final sale" in response.json()["detail"]["reasons"]


def test_full_missed_pickup_reschedule_and_refund_journey(client):
    case = client.post("/api/returns", json=eligibility_payload()).json()
    case_id = case["id"]
    pickup_date = date.today().isoformat()

    assert client.post(
        f"/api/returns/{case_id}/pickup/schedule", json={"pickup_date": pickup_date}
    ).status_code == 200
    missed = client.post(f"/api/returns/{case_id}/pickup/missed")
    assert missed.status_code == 200
    assert missed.json()["status"] == "missed_pickup"

    blocked = client.post(
        f"/api/returns/{case_id}/pickup/reschedule",
        json={"pickup_date": pickup_date},
    )
    assert blocked.status_code == 409
    assert "availability" in blocked.json()["detail"].lower()

    collected = client.post(
        f"/api/returns/{case_id}/availability",
        json={"availability": "Weekdays after 5 PM"},
    )
    assert collected.status_code == 200
    assert collected.json()["status"] == "availability_collected"
    rescheduled = client.post(
        f"/api/returns/{case_id}/pickup/reschedule",
        json={"pickup_date": pickup_date},
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["status"] == "pickup_scheduled"
    assert any(event["type"] == "pickup_rescheduled" for event in rescheduled.json()["events"])

    for next_status in ("picked_up", "in_transit", "delivered", "refund_issued"):
        advanced = client.post(
            f"/api/returns/{case_id}/simulate/advance",
            json={"to_status": next_status},
        )
        assert advanced.status_code == 200
    assert advanced.json()["status"] == "resolved"
    assert advanced.json()["resolved"] is True
    assert [event["type"] for event in advanced.json()["events"]][-6:] == [
        "availability_collected",
        "pickup_rescheduled",
        "pickup_completed",
        "shipment_in_transit",
        "shipment_delivered",
        "refund_issued",
    ]


def test_resolution_requires_ordered_simulated_evidence(client):
    case = client.post("/api/returns", json=eligibility_payload()).json()
    case_id = case["id"]
    pickup_date = date.today().isoformat()

    assert client.post(
        f"/api/returns/{case_id}/pickup/schedule", json={"pickup_date": pickup_date}
    ).status_code == 200
    premature = client.post(
        f"/api/returns/{case_id}/simulate/advance", json={"to_status": "refund_issued"}
    )
    assert premature.status_code == 409
    assert client.get(f"/api/returns/{case_id}").json()["resolved"] is False

    for next_status in ("picked_up", "in_transit", "delivered", "refund_issued"):
        advanced = client.post(
            f"/api/returns/{case_id}/simulate/advance",
            json={"to_status": next_status},
        )
        assert advanced.status_code == 200
        assert advanced.json()["simulated"] is True

    resolved = advanced.json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved"] is True
    event_types = [event["type"] for event in resolved["events"]]
    assert event_types[-4:] == [
        "pickup_completed",
        "shipment_in_transit",
        "shipment_delivered",
        "refund_issued",
    ]
    refund_event = resolved["events"][-1]
    assert refund_event["evidence"]["refund_status"] == "issued"
    assert refund_event["evidence"]["amount"] == 112.0
    assert refund_event["simulated"] is True


def test_required_simulated_evidence_cannot_be_skipped(client):
    case = client.post("/api/returns", json=eligibility_payload()).json()
    case_id = case["id"]
    advance_url = f"/api/returns/{case_id}/simulate/advance"

    before_pickup = client.post(advance_url, json={"to_status": "picked_up"})
    assert before_pickup.status_code == 409

    pickup_date = date.today().isoformat()
    assert client.post(
        f"/api/returns/{case_id}/pickup/schedule", json={"pickup_date": pickup_date}
    ).status_code == 200
    for skipped_status in ("in_transit", "delivered", "refund_issued"):
        skipped = client.post(advance_url, json={"to_status": skipped_status})
        assert skipped.status_code == 409
        current = client.get(f"/api/returns/{case_id}").json()
        assert current["status"] == "pickup_scheduled"
        assert current["resolved"] is False

    activity = client.get("/api/activity").json()["items"]
    case_events = [event for event in activity if event["case_id"] == case_id]
    assert not any(event["type"] in {"shipment_delivered", "refund_issued"} for event in case_events)