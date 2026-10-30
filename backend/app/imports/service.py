"""One customer-owned import engine for file and Gmail observations."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import sqlite3
import uuid

from ..db import connect
from .models import ImportProblem, Order, ParseResult


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database():
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_previews'").fetchone():
                raise ImportProblem("Imports need database migration 002. Ask the administrator to configure a migrated database.", 503)
            yield conn
    except sqlite3.OperationalError:
        raise ImportProblem("Import storage is temporarily unavailable", 503) from None


def key(order):
    return hashlib.sha256(f"{order.retailer}|{order.marketplace}|{order.external_order_id}".encode()).hexdigest()[:32]


def existing(conn, user_id, order):
    if not order.marketplace:
        return None
    return conn.execute("SELECT * FROM orders WHERE user_id=? AND retailer=? AND marketplace=? AND external_order_id=? AND simulated=0", (user_id, order.retailer, order.marketplace, order.external_order_id)).fetchone()


def conflict(conn, row, order):
    if not row:
        return False
    if any(getattr(order, name) is not None and row[name] is not None and str(getattr(order, name)) != row[name] for name in ("currency", "order_date")):
        return True
    if any(name in row.keys() and getattr(order, name) is not None and row[name] is not None and str(getattr(order, name)) != row[name] for name in ("total_amount", "payment_status")):
        return True
    stored = conn.execute("SELECT name,quantity,unit_price,currency FROM order_items WHERE order_id=?", (row["id"],)).fetchall()
    # A later incomplete observation must not replace a reviewed product list.
    incoming = {(i.product_name, i.quantity, str(i.unit_price) if i.unit_price is not None else None, i.currency) for i in order.items}
    return bool(incoming and incoming != {tuple(i) for i in stored})


def _missing_fields(conn, row, order):
    """Find safe fill-only additions; product identity must be unambiguous."""
    if not row:
        return {}, []
    additions = {}
    for name in ("total_amount", "payment_status"):
        value = getattr(order, name)
        if name in row.keys() and row[name] is None and value is not None:
            if name != "total_amount" or (order.currency and order.currency == row["currency"]):
                additions[name] = str(value)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(order_items)")}
    categories = []
    if "category" in columns:
        stored = conn.execute("SELECT * FROM order_items WHERE order_id=?", (row["id"],)).fetchall()
        def identity(item):
            return (item.product_name, item.quantity, str(item.unit_price) if item.unit_price is not None else None, item.currency)
        for item in order.items:
            if item.category is None or sum(identity(i) == identity(item) for i in order.items) != 1:
                continue
            matches = [r for r in stored if (r["name"], r["quantity"], r["unit_price"], r["currency"]) == identity(item)
                       and (not item.external_item_id or item.external_item_id == r["external_item_id"])
                       and (not item.product_identifier or item.product_identifier == r["product_identifier"])]
            if len(matches) == 1 and matches[0]["category"] is None:
                categories.append((item.category, matches[0]["id"]))
    return additions, categories


def _validate_enrichment_refunds(conn, user_id, row, additions):
    if "total_amount" not in additions or not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='refunds'").fetchone():
        return
    # Use the same bounded money parser as the refund ledger. Both pending and
    # received refunds reserve the charged amount; damaged money blocks writes.
    from ..shopping.service import amount
    total = Decimal(0)
    for refund in conn.execute("SELECT amount,currency FROM refunds WHERE user_id=? AND order_id=?", (user_id, row["id"])):
        value = amount(refund["amount"])
        if value is None or refund["currency"] != row["currency"]:
            raise ImportProblem("Stored refunds require reconciliation before filling the charged total", 409)
        total += value
    if total > Decimal(additions["total_amount"]):
        raise ImportProblem("Recorded refunds exceed this charged total; reconcile refunds before confirming", 409)


def _groups(parsed):
    groups = {}
    for order in parsed.orders:
        groups.setdefault(key(order), []).append(order)
    return groups


def _preferred(observations):
    return max(observations, key=lambda o: (bool(o.order_date), bool(o.marketplace), len(o.items), sum(i.unit_price is not None for i in o.items)))


def _view(conn, preview):
    parsed = ParseResult.model_validate_json(preview["payload_json"])
    orders = []
    for observations in _groups(parsed).values():
        order = _preferred(observations)
        row = existing(conn, preview["user_id"], order)
        has_conflict = conflict(conn, row, order) or any(o.model_dump(exclude={"source_reference", "source_timestamp", "review_reasons"}) != order.model_dump(exclude={"source_reference", "source_timestamp", "review_reasons"}) for o in observations)
        order_view = order.model_dump(mode="json")
        additions, categories = _missing_fields(conn, row, order)
        if additions or categories:
            order_view["review_reasons"] = [*order_view["review_reasons"], "This observation can fill missing financial or category fields; review before confirming"]
        orders.append({"key": key(order), "order": order_view, "duplicate": bool(row), "conflict": has_conflict})
    return {"id": preview["id"], "source": preview["source"], "expires_at": preview["expires_at"], "orders": orders, "issues": parsed.issues, "unsupported": parsed.unsupported,
            "counts": {"orders": len(orders), "items": sum(len(o["order"]["items"]) for o in orders), "valid": len(orders), "invalid": len(parsed.issues), "duplicates": sum(o["duplicate"] for o in orders), "review": sum(bool(o["order"]["review_reasons"]) or o["conflict"] for o in orders), "unsupported": len(parsed.unsupported), "repeated_records": parsed.duplicate_records},
            "result": json.loads(preview["result_json"]) if preview["result_json"] else None}


def create_preview(user_id, source, digest, parsed, conn=None):
    if conn is None:
        with database() as owned:
            owned.execute("BEGIN IMMEDIATE")
            return create_preview(user_id, source, digest, parsed, owned)
    # Expired structured preview payloads are disposable; history remains.
    conn.execute("DELETE FROM import_previews WHERE user_id=? AND expires_at<?", (user_id, now()))
    if conn.execute("SELECT COUNT(*) FROM import_previews WHERE user_id=?", (user_id,)).fetchone()[0] >= 20:
        raise ImportProblem("Too many pending previews; wait for older previews to expire", 429)
    preview_id = uuid.uuid4().hex
    timestamp = now()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    conn.execute("INSERT INTO import_previews(id,user_id,source,digest,payload_json,created_at,expires_at) VALUES (?,?,?,?,?,?,?)", (preview_id, user_id, source, digest, parsed.model_dump_json(), timestamp, expires))
    return _view(conn, conn.execute("SELECT * FROM import_previews WHERE id=?", (preview_id,)).fetchone())


def _owned(conn, preview_id, user_id):
    preview = conn.execute("SELECT * FROM import_previews WHERE id=? AND user_id=?", (preview_id, user_id)).fetchone()
    if not preview:
        raise ImportProblem("Import preview not found", 404)
    if preview["expires_at"] < now():
        raise ImportProblem("Preview expired; upload or synchronize again", 410)
    return preview


def get_preview(user_id, preview_id):
    with database() as conn:
        return _view(conn, _owned(conn, preview_id, user_id))


def confirm_preview(user_id, preview_id, order_keys, acknowledge_review=False):
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        preview = _owned(conn, preview_id, user_id)
        if preview["result_json"]:
            return json.loads(preview["result_json"])
        parsed = ParseResult.model_validate_json(preview["payload_json"])
        keys = set(order_keys)
        if not keys or not keys.issubset({key(o) for o in parsed.orders}):
            raise ImportProblem("Choose valid orders from this preview")
        groups = _groups(parsed)
        selected = [_preferred(observations) for k, observations in groups.items() if k in keys]
        if any(not o.marketplace or not o.order_date or not o.items for o in selected):
            raise ImportProblem("Orders missing marketplace, order date or product lines cannot be confirmed. A verified adapter is needed.", 409)
        view = _view(conn, preview)
        if not acknowledge_review and any((o["order"]["review_reasons"] or o["conflict"]) for o in view["orders"] if o["key"] in keys):
            raise ImportProblem("Review unknown or conflicting fields and acknowledge them before confirming", 409)
        imported = skipped = 0
        for order in selected:
            row = existing(conn, user_id, order)
            if row:
                order_id = row["id"]
                if acknowledge_review:
                    additions, categories = _missing_fields(conn, row, order)
                    _validate_enrichment_refunds(conn, user_id, row, additions)
                    for name, value in additions.items():
                        # Names come exclusively from the fixed allowlist above.
                        conn.execute(f"UPDATE orders SET {name}=? WHERE id=? AND user_id=? AND {name} IS NULL", (value, order_id, user_id))
                    for category, item_id in categories:
                        conn.execute("UPDATE order_items SET category=? WHERE id=? AND order_id=? AND category IS NULL", (category, item_id, order_id))
                skipped += 1
            else:
                order_id = "order-" + uuid.uuid4().hex
                conn.execute("""INSERT INTO orders(id,user_id,retailer,order_date,simulated,source,external_order_id,marketplace,currency,order_status,imported_at,review_status)
                    VALUES (?,?,?,?,0,?,?,?,?,?,?,?)""", (order_id, user_id, order.retailer, order.order_date.isoformat(), order.source, order.external_order_id, order.marketplace, order.currency, order.order_status, now(), "reviewed_with_unknowns" if order.review_reasons else "reviewed"))
                order_columns = {r[1] for r in conn.execute("PRAGMA table_info(orders)")}
                if {"total_amount", "payment_status"}.issubset(order_columns):
                    conn.execute("UPDATE orders SET total_amount=?,payment_status=? WHERE id=?", (str(order.total_amount) if order.total_amount is not None else None, order.payment_status, order_id))
                item_columns = {r[1] for r in conn.execute("PRAGMA table_info(order_items)")}
                for item in order.items:
                    amount = str(item.unit_price) if item.unit_price is not None else None
                    item_id = "item-" + uuid.uuid4().hex
                    conn.execute("""INSERT INTO order_items(id,order_id,name,sku,quantity,price,return_window_days,final_sale,external_item_id,product_identifier,unit_price,currency,details_json)
                        VALUES (?,?,?,?,?,?,NULL,NULL,?,?,?,?,?)""", (item_id, order_id, item.product_name, item.product_identifier, item.quantity, float(item.unit_price) if amount is not None else None, item.external_item_id, item.product_identifier, amount, item.currency, json.dumps(item.details)))
                    if "category" in item_columns:
                        conn.execute("UPDATE order_items SET category=? WHERE id=?", (item.category, item_id))
                imported += 1
            for observation in groups[key(order)]:
                reference = f"{preview['digest']}:{observation.source_reference}" if observation.source == "amazon_file" else observation.source_reference
                conn.execute("""INSERT INTO order_source_references(id,order_id,user_id,source,source_reference,observation_json,source_timestamp,imported_at)
                    VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id,order_id,source,source_reference) DO NOTHING""", (uuid.uuid4().hex, order_id, user_id, observation.source, reference, observation.model_dump_json(), observation.source_timestamp, now()))
                if observation.source == "gmail":
                    conn.execute("UPDATE gmail_messages SET outcome='confirmed',observation_json=NULL WHERE message_id=? AND integration_id IN (SELECT id FROM integrations WHERE user_id=? AND provider='gmail')", (observation.source_reference, user_id))
        result = {"imported": imported, "skipped": skipped, "failed": len(parsed.issues), "unselected": len(groups) - len(selected), "status": "completed_with_issues" if parsed.issues or parsed.unsupported else "completed"}
        conn.execute("INSERT INTO import_history(id,user_id,source,status,imported_count,skipped_count,error_count,created_at,completed_at,summary_json) VALUES (?,?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, user_id, preview["source"], result["status"], imported, skipped, len(parsed.issues), preview["created_at"], now(), json.dumps(result)))
        conn.execute("UPDATE import_previews SET result_json=? WHERE id=?", (json.dumps(result), preview_id))
        return result


def history(user_id):
    with database() as conn:
        return {"items": [dict(row) for row in conn.execute("SELECT id,source,status,imported_count,skipped_count,error_count,created_at,completed_at FROM import_history WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (user_id,))]}
