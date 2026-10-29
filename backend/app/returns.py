"""SQLite-backed simulated orders, returns, and evidence events."""
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .db import connect


class WorkflowError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                retailer TEXT NOT NULL,
                order_date TEXT NOT NULL,
                simulated INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL REFERENCES orders(id),
                name TEXT NOT NULL,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                return_window_days INTEGER NOT NULL,
                final_sale INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS return_cases (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL REFERENCES orders(id),
                item_id TEXT NOT NULL REFERENCES order_items(id),
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                availability TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                simulated INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS case_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES return_cases(id),
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL,
                simulated INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    today = date.today()
    conn.executemany(
        "INSERT INTO orders (id, retailer, order_date) VALUES (?, ?, ?)",
        [
            ("demo-order-001", "Cygnus Demo Store (simulated)", (today - timedelta(days=8)).isoformat()),
            ("demo-order-002", "Cygnus Demo Store (simulated)", (today - timedelta(days=5)).isoformat()),
            ("demo-order-003", "Cygnus Demo Store (simulated)", (today - timedelta(days=50)).isoformat()),
            ("demo-order-004", "Cygnus Demo Store (simulated)", (today - timedelta(days=6)).isoformat()),
        ],
    )
    conn.executemany(
        """INSERT INTO order_items
           (id, order_id, name, sku, quantity, price, return_window_days, final_sale)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("item-shoes-001", "demo-order-001", "Everyday running shoes", "SHOE-001", 1, 84.00, 30, 0),
            ("item-coat-002", "demo-order-002", "Packable rain jacket", "COAT-002", 1, 112.00, 30, 0),
            ("item-old-003", "demo-order-003", "Ceramic pour-over set", "HOME-003", 1, 46.00, 30, 0),
            ("item-final-004", "demo-order-004", "Clearance headphones", "AUDIO-004", 1, 39.00, 30, 1),
        ],
    )
    timestamp = _now()
    conn.execute(
        """INSERT INTO return_cases
           (id, order_id, item_id, reason, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("case-demo-001", "demo-order-001", "item-shoes-001", "wrong_size", "pickup_scheduled", timestamp, timestamp),
    )
    conn.executemany(
        """INSERT INTO case_events
           (case_id, event_type, message, evidence, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        [
            ("case-demo-001", "return_requested", "Simulated return case created.", json.dumps({"order_id": "demo-order-001", "item_id": "item-shoes-001"}), timestamp),
            ("case-demo-001", "pickup_scheduled", "Simulated pickup scheduled.", json.dumps({"pickup_date": today.isoformat()}), timestamp),
        ],
    )


def _event(conn: sqlite3.Connection, case_id: str, event_type: str, message: str, evidence: dict) -> None:
    conn.execute(
        """INSERT INTO case_events
           (case_id, event_type, message, evidence, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (case_id, event_type, message, json.dumps(evidence), _now()),
    )


def _events(conn: sqlite3.Connection, case_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM case_events WHERE case_id = ? ORDER BY id", (case_id,)
    ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["event_type"],
            "message": row["message"],
            "evidence": json.loads(row["evidence"]),
            "occurred_at": row["created_at"],
            "simulated": bool(row["simulated"]),
        }
        for row in rows
    ]


def _case(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "order_id": row["order_id"],
        "item_id": row["item_id"],
        "reason": row["reason"],
        "status": row["status"],
        "availability": row["availability"],
        "resolved": bool(row["resolved"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "simulated": bool(row["simulated"]),
        "events": _events(conn, row["id"]),
    }


def _get_case(conn: sqlite3.Connection, case_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM return_cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise WorkflowError(404, "Return case not found")
    return row


def list_orders() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY order_date DESC, id").fetchall()
        items = []
        for order in rows:
            order_items = conn.execute(
                "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order["id"],)
            ).fetchall()
            items.append(
                {
                    "id": order["id"],
                    "retailer": order["retailer"],
                    "order_date": order["order_date"],
                    "simulated": bool(order["simulated"]),
                    "items": [
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "sku": item["sku"],
                            "quantity": item["quantity"],
                            "price": item["price"],
                            "return_window_days": item["return_window_days"],
                            "final_sale": bool(item["final_sale"]),
                        }
                        for item in order_items
                    ],
                }
            )
        return {"items": items, "simulated": True}


def get_order(order_id: str) -> dict:
    result = next((order for order in list_orders()["items"] if order["id"] == order_id), None)
    if result is None:
        raise WorkflowError(404, "Order not found")
    return result


def eligibility(order_id: str, item_id: str) -> dict:
    reasons = []
    with connect() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        item = conn.execute(
            "SELECT * FROM order_items WHERE id = ? AND order_id = ?", (item_id, order_id)
        ).fetchone()
        if order is None:
            reasons.append("order not found")
        if item is None:
            reasons.append("item not found on this order")
        if order is not None and item is not None:
            age_days = (date.today() - date.fromisoformat(order["order_date"])).days
            if age_days > item["return_window_days"]:
                reasons.append("return window has expired")
            if item["final_sale"]:
                reasons.append("item is final sale")
            active = conn.execute(
                "SELECT 1 FROM return_cases WHERE order_id = ? AND item_id = ? AND resolved = 0",
                (order_id, item_id),
            ).fetchone()
            if active:
                reasons.append("return case already exists")
    return {"eligible": not reasons, "reasons": reasons, "simulated": True}


def create_case(order_id: str, item_id: str, reason: str) -> dict:
    check = eligibility(order_id, item_id)
    if not check["eligible"]:
        raise WorkflowError(409, {"message": "Return is not eligible", "reasons": check["reasons"]})
    case_id = f"case-{uuid.uuid4().hex[:12]}"
    timestamp = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO return_cases
               (id, order_id, item_id, reason, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'requested', ?, ?)""",
            (case_id, order_id, item_id, reason, timestamp, timestamp),
        )
        _event(conn, case_id, "return_requested", "Simulated return case created.", {"order_id": order_id, "item_id": item_id})
        return _case(conn, _get_case(conn, case_id))


def list_cases(order_id: str | None = None) -> dict:
    with connect() as conn:
        if order_id:
            rows = conn.execute(
                "SELECT * FROM return_cases WHERE order_id = ? ORDER BY created_at DESC", (order_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM return_cases ORDER BY created_at DESC").fetchall()
        return {"items": [_case(conn, row) for row in rows], "simulated": True}


def get_case(case_id: str) -> dict:
    with connect() as conn:
        return _case(conn, _get_case(conn, case_id))


def _set_status(conn: sqlite3.Connection, case_id: str, status: str, event_type: str, message: str, evidence: dict, resolved: bool = False) -> dict:
    timestamp = _now()
    conn.execute(
        "UPDATE return_cases SET status = ?, resolved = ?, updated_at = ? WHERE id = ?",
        (status, int(resolved), timestamp, case_id),
    )
    _event(conn, case_id, event_type, message, evidence)
    return _case(conn, _get_case(conn, case_id))


def schedule_pickup(case_id: str, pickup_date: date) -> dict:
    if pickup_date < date.today():
        raise WorkflowError(422, "Pickup date cannot be in the past")
    with connect() as conn:
        row = _get_case(conn, case_id)
        if row["status"] != "requested":
            raise WorkflowError(409, "Pickup can only be scheduled for a requested return")
        return _set_status(conn, case_id, "pickup_scheduled", "pickup_scheduled", "Simulated pickup scheduled.", {"pickup_date": pickup_date.isoformat()})


def mark_pickup_missed(case_id: str) -> dict:
    with connect() as conn:
        row = _get_case(conn, case_id)
        if row["status"] != "pickup_scheduled":
            raise WorkflowError(409, "Only a scheduled pickup can be marked missed")
        return _set_status(conn, case_id, "missed_pickup", "pickup_missed", "Simulated pickup was marked as missed.", {"source": "demo action"})


def collect_availability(case_id: str, availability: str) -> dict:
    with connect() as conn:
        row = _get_case(conn, case_id)
        if row["status"] != "missed_pickup":
            raise WorkflowError(409, "Customer availability can only be collected after a missed pickup")
        conn.execute(
            "UPDATE return_cases SET availability = ?, updated_at = ? WHERE id = ?",
            (availability, _now(), case_id),
        )
        _event(conn, case_id, "availability_collected", "Customer availability recorded for simulated rescheduling.", {"availability": availability})
        conn.execute("UPDATE return_cases SET status = 'availability_collected' WHERE id = ?", (case_id,))
        return _case(conn, _get_case(conn, case_id))


def reschedule_pickup(case_id: str, pickup_date: date) -> dict:
    if pickup_date < date.today():
        raise WorkflowError(422, "Pickup date cannot be in the past")
    with connect() as conn:
        row = _get_case(conn, case_id)
        if row["status"] != "availability_collected" or not row["availability"]:
            raise WorkflowError(409, "Customer availability is required before rescheduling")
        return _set_status(conn, case_id, "pickup_scheduled", "pickup_rescheduled", "Simulated pickup rescheduled using customer availability.", {"pickup_date": pickup_date.isoformat(), "availability": row["availability"]})


def advance_simulation(case_id: str, to_status: str) -> dict:
    transitions = {
        "pickup_scheduled": ("picked_up", "pickup_completed", "Simulated pickup completed."),
        "picked_up": ("in_transit", "shipment_in_transit", "Simulated shipment is in transit."),
        "in_transit": ("delivered", "shipment_delivered", "Simulated shipment delivery recorded."),
        "delivered": ("resolved", "refund_issued", "Simulated refund issued; return case resolved."),
    }
    with connect() as conn:
        row = _get_case(conn, case_id)
        transition = transitions.get(row["status"])
        accepted_target = "refund_issued" if row["status"] == "delivered" else (transition[0] if transition else None)
        if transition is None or accepted_target != to_status:
            expected = transition[0] if transition else "no further transition"
            raise WorkflowError(409, f"Cannot advance from {row['status']} to {to_status}; expected {expected}")
        evidence = {"status": to_status, "simulated": True}
        event_type = transition[1]
        resolved = event_type == "refund_issued"
        if event_type == "refund_issued":
            item = conn.execute("SELECT price FROM order_items WHERE id = ?", (row["item_id"],)).fetchone()
            evidence.update({"refund_status": "issued", "amount": item["price"], "currency": "USD"})
        return _set_status(conn, case_id, transition[0], event_type, transition[2], evidence, resolved)


def activity() -> dict:
    with connect() as conn:
        rows = conn.execute(
            """SELECT case_events.*, return_cases.order_id
               FROM case_events JOIN return_cases ON return_cases.id = case_events.case_id
               ORDER BY case_events.id DESC"""
        ).fetchall()
        return {
            "items": [
                {
                    "id": row["id"],
                    "case_id": row["case_id"],
                    "order_id": row["order_id"],
                    "type": row["event_type"],
                    "message": row["message"],
                    "evidence": json.loads(row["evidence"]),
                    "occurred_at": row["created_at"],
                    "simulated": bool(row["simulated"]),
                }
                for row in rows
            ],
            "simulated": True,
        }