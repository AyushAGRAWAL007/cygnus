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
        # Demo seeding belongs only to the original pre-account bootstrap.
        # An empty migrated customer store is legitimate and must remain empty.
        has_accounts = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if not has_accounts and conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
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


def _get_case(conn: sqlite3.Connection, case_id: str, user_id: str | None = None) -> sqlite3.Row:
    if user_id is None:
        row = conn.execute("SELECT * FROM return_cases WHERE id = ?", (case_id,)).fetchone()
    else:
        row = conn.execute("""SELECT return_cases.* FROM return_cases
            JOIN orders ON orders.id=return_cases.order_id
            JOIN order_items ON order_items.id=return_cases.item_id AND order_items.order_id=orders.id
            WHERE return_cases.id=? AND orders.user_id=?""", (case_id, user_id)).fetchone()
    if row is None:
        raise WorkflowError(404, "Return case not found")
    return row


def list_orders(user_id: str | None = None, order_id: str | None = None) -> dict:
    with connect() as conn:
        filters, parameters = [], []
        if user_id is not None:
            filters.append("user_id=?"); parameters.append(user_id)
        if order_id is not None:
            filters.append("id=?"); parameters.append(order_id)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        rows = conn.execute("SELECT * FROM orders" + where + " ORDER BY order_date DESC, id", parameters).fetchall()
        # Fetch items once instead of once per order.
        item_rows = conn.execute("SELECT order_items.* FROM order_items JOIN orders ON orders.id=order_items.order_id" + (" WHERE orders.user_id=?" if user_id is not None else "") + " ORDER BY order_items.id", (user_id,) if user_id is not None else ()).fetchall()
        by_order = {}
        for item in item_rows:
            by_order.setdefault(item["order_id"], []).append(item)
        items = []
        source_map = {}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='order_source_references'").fetchone():
            source_rows = conn.execute("SELECT DISTINCT order_id,source FROM order_source_references" + (" WHERE user_id=?" if user_id is not None else ""), (user_id,) if user_id is not None else ()).fetchall()
            for source_row in source_rows:
                source_map.setdefault(source_row["order_id"], []).append(source_row["source"])
        for order in rows:
            order_items = by_order.get(order["id"], [])
            items.append(
                {
                    "id": order["id"],
                    "retailer": order["retailer"],
                    "order_date": order["order_date"],
                    "simulated": bool(order["simulated"]),
                    "source": order["source"] if "source" in order.keys() else "demo",
                    "external_order_id": order["external_order_id"] if "external_order_id" in order.keys() else None,
                    "currency": order["currency"] if "currency" in order.keys() else "USD",
                    "order_status": order["order_status"] if "order_status" in order.keys() else None,
                    "marketplace": order["marketplace"] if "marketplace" in order.keys() else None,
                    "sources": source_map.get(order["id"], []),
                    "items": [
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "sku": item["sku"],
                            "quantity": item["quantity"],
                            "price": item["price"],
                            "return_window_days": item["return_window_days"],
                            "final_sale": bool(item["final_sale"]),
                            "unit_price": item["unit_price"] if "unit_price" in item.keys() else str(item["price"]),
                            "currency": item["currency"] if "currency" in item.keys() else "USD",
                        }
                        for item in order_items
                    ],
                }
            )
        return {"items": items, "simulated": all(o["simulated"] for o in items)}


def get_order(order_id: str, user_id: str | None = None) -> dict:
    result = next((order for order in list_orders(user_id, order_id)["items"] if order["id"] == order_id), None)
    if result is None:
        raise WorkflowError(404, "Order not found")
    return result


def _eligibility(conn, order_id: str, item_id: str, user_id: str | None = None) -> dict:
    reasons = []
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    item = conn.execute(
        "SELECT * FROM order_items WHERE id = ? AND order_id = ?", (item_id, order_id)
    ).fetchone()
    if user_id is not None:
        owned = conn.execute("SELECT 1 FROM orders WHERE id=? AND user_id=?", (order_id, user_id)).fetchone()
        if owned is None or item is None:
            raise WorkflowError(404, "Order item not found")
    if order is None:
        reasons.append("order not found")
    if item is None:
        reasons.append("item not found on this order")
    if order is not None and item is not None:
        if not order["simulated"]:
            return {"eligible": False, "reasons": ["Retailer return eligibility is not verified. Check the order in Amazon; Cygnus cannot arrange a real pickup or refund."], "simulated": False, "verification": "unknown"}
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


def eligibility(order_id: str, item_id: str, user_id: str | None = None) -> dict:
    with connect() as conn:
        return _eligibility(conn, order_id, item_id, user_id)


def create_case(order_id: str, item_id: str, reason: str, user_id: str | None = None) -> dict:
    case_id = f"case-{uuid.uuid4().hex[:12]}"
    timestamp = _now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        check = _eligibility(conn, order_id, item_id, user_id)
        if not check["eligible"]:
            raise WorkflowError(409, {"message": "Return is not eligible", "reasons": check["reasons"]})
        conn.execute(
            """INSERT INTO return_cases
               (id, order_id, item_id, reason, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'requested', ?, ?)""",
            (case_id, order_id, item_id, reason, timestamp, timestamp),
        )
        _event(conn, case_id, "return_requested", "Simulated return case created.", {"order_id": order_id, "item_id": item_id})
        return _case(conn, _get_case(conn, case_id))


def list_cases(order_id: str | None = None, user_id: str | None = None) -> dict:
    if order_id and user_id is not None:
        get_order(order_id, user_id)
    with connect() as conn:
        filters, parameters = [], []
        if order_id:
            filters.append("return_cases.order_id=?"); parameters.append(order_id)
        if user_id is not None:
            filters.append("orders.user_id=?"); parameters.append(user_id)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        rows = conn.execute("SELECT return_cases.* FROM return_cases JOIN orders ON orders.id=return_cases.order_id" + where + " ORDER BY return_cases.created_at DESC", parameters).fetchall()
        return {"items": [_case(conn, row) for row in rows], "simulated": True}


def get_case(case_id: str, user_id: str | None = None) -> dict:
    with connect() as conn:
        return _case(conn, _get_case(conn, case_id, user_id))


def _set_status(conn: sqlite3.Connection, case_id: str, status: str, event_type: str, message: str, evidence: dict, resolved: bool = False) -> dict:
    timestamp = _now()
    conn.execute(
        "UPDATE return_cases SET status = ?, resolved = ?, updated_at = ? WHERE id = ?",
        (status, int(resolved), timestamp, case_id),
    )
    _event(conn, case_id, event_type, message, evidence)
    return _case(conn, _get_case(conn, case_id))


def schedule_pickup(case_id: str, pickup_date: date, user_id: str | None = None) -> dict:
    if pickup_date < date.today():
        raise WorkflowError(422, "Pickup date cannot be in the past")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get_case(conn, case_id, user_id)
        if row["status"] != "requested":
            raise WorkflowError(409, "Pickup can only be scheduled for a requested return")
        return _set_status(conn, case_id, "pickup_scheduled", "pickup_scheduled", "Simulated pickup scheduled.", {"pickup_date": pickup_date.isoformat()})


def mark_pickup_missed(case_id: str, user_id: str | None = None) -> dict:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get_case(conn, case_id, user_id)
        if row["status"] != "pickup_scheduled":
            raise WorkflowError(409, "Only a scheduled pickup can be marked missed")
        return _set_status(conn, case_id, "missed_pickup", "pickup_missed", "Simulated pickup was marked as missed.", {"source": "demo action"})


def collect_availability(case_id: str, availability: str, user_id: str | None = None) -> dict:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get_case(conn, case_id, user_id)
        if row["status"] != "missed_pickup":
            raise WorkflowError(409, "Customer availability can only be collected after a missed pickup")
        conn.execute(
            "UPDATE return_cases SET availability = ?, updated_at = ? WHERE id = ?",
            (availability, _now(), case_id),
        )
        _event(conn, case_id, "availability_collected", "Customer availability recorded for simulated rescheduling.", {"availability": availability})
        conn.execute("UPDATE return_cases SET status = 'availability_collected' WHERE id = ?", (case_id,))
        return _case(conn, _get_case(conn, case_id))


def reschedule_pickup(case_id: str, pickup_date: date, user_id: str | None = None) -> dict:
    if pickup_date < date.today():
        raise WorkflowError(422, "Pickup date cannot be in the past")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get_case(conn, case_id, user_id)
        if row["status"] != "availability_collected" or not row["availability"]:
            raise WorkflowError(409, "Customer availability is required before rescheduling")
        return _set_status(conn, case_id, "pickup_scheduled", "pickup_rescheduled", "Simulated pickup rescheduled using customer availability.", {"pickup_date": pickup_date.isoformat(), "availability": row["availability"]})


def advance_simulation(case_id: str, to_status: str, user_id: str | None = None) -> dict:
    transitions = {
        "pickup_scheduled": ("picked_up", "pickup_completed", "Simulated pickup completed."),
        "picked_up": ("in_transit", "shipment_in_transit", "Simulated shipment is in transit."),
        "in_transit": ("delivered", "shipment_delivered", "Simulated shipment delivery recorded."),
        "delivered": ("resolved", "refund_issued", "Simulated refund issued; return case resolved."),
    }
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get_case(conn, case_id, user_id)
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


def activity(user_id: str | None = None) -> dict:
    with connect() as conn:
        rows = conn.execute(
            """SELECT case_events.*, return_cases.order_id
               FROM case_events JOIN return_cases ON return_cases.id = case_events.case_id
               JOIN orders ON orders.id=return_cases.order_id"""
            + (" WHERE orders.user_id=?" if user_id is not None else "")
            + " ORDER BY case_events.id DESC", (user_id,) if user_id is not None else ()
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
