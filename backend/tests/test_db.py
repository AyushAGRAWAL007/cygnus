"""Connection integrity and workflow rollback checks on isolated databases."""
import sqlite3
from pathlib import Path
import runpy

import pytest

from app import db, returns
from app.config import get_settings


@pytest.fixture(params=["original", "migrated"])
def database(tmp_path, monkeypatch, request):
    path = tmp_path / "isolated.db"
    monkeypatch.setattr(get_settings(), "database_path", str(path))
    returns.initialize()
    if request.param == "migrated":
        script = Path(__file__).resolve().parents[1] / "migrations/001_customer_ownership.py"
        runpy.run_path(str(script))["migrate"](path)
    return path


def assert_closed(conn):
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_each_connection_enforces_foreign_keys_before_transaction(database):
    with db.connect() as first, db.connect() as second:
        assert first is not second
        for conn in (first, second):
            assert not conn.in_transaction
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert conn.execute("SELECT id FROM orders LIMIT 1").fetchone()["id"]
    assert_closed(first)
    assert_closed(second)
    with db.connect() as reopened:
        assert reopened.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.parametrize("sql", [
    "INSERT INTO order_items VALUES ('bad-item','missing','Demo','SKU',1,10,30,0)",
    "INSERT INTO return_cases(id,order_id,item_id,reason,status,created_at,updated_at) VALUES ('bad-case','missing','item-coat-002','damaged','requested','now','now')",
    "INSERT INTO return_cases(id,order_id,item_id,reason,status,created_at,updated_at) VALUES ('bad-case','demo-order-002','missing','damaged','requested','now','now')",
    "INSERT INTO case_events(case_id,event_type,message,evidence,created_at) VALUES ('missing','demo','demo','{}','now')",
    "UPDATE order_items SET order_id='missing' WHERE id='item-coat-002'",
    "DELETE FROM orders WHERE id='demo-order-001'",
])
def test_invalid_foreign_key_writes_fail(database, sql):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with db.connect() as conn:
            conn.execute(sql)
    assert_closed(conn)
    with db.connect() as check:
        assert check.execute("PRAGMA foreign_key_check").fetchall() == []
        assert check.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 4


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_failed_body_explicitly_rolls_back_before_close(database, monkeypatch, failure):
    original_connect = sqlite3.connect
    transactions_at_close = []

    class ObservedConnection(sqlite3.Connection):
        def close(self):
            transactions_at_close.append(self.in_transaction)
            super().close()

    monkeypatch.setattr(db.sqlite3, "connect", lambda *a, **kw: original_connect(*a, **kw, factory=ObservedConnection))
    with pytest.raises(failure):
        with db.connect() as conn:
            conn.execute("INSERT INTO orders(id,retailer,order_date,simulated) VALUES ('rollback-order','Demo','2026-10-30',1)")
            raise failure("operation failed")
    assert_closed(conn)
    assert transactions_at_close == [False]
    with db.connect() as check:
        assert check.execute("SELECT 1 FROM orders WHERE id='rollback-order'").fetchone() is None


def test_commit_failure_rolls_back_and_closes(database):
    with db.connect() as setup:
        setup.execute("CREATE TABLE deferred_child (order_id TEXT REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED)")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with db.connect() as conn:
            conn.execute("INSERT INTO deferred_child VALUES ('missing')")
    assert_closed(conn)
    with db.connect() as check:
        assert check.execute("SELECT * FROM deferred_child").fetchall() == []


@pytest.mark.parametrize("setup_failure", ["exception", "disabled"])
def test_foreign_key_setup_failure_closes_without_yield(database, monkeypatch, setup_failure):
    original_connect = sqlite3.connect
    opened = []

    class SetupFailureConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "PRAGMA foreign_keys = ON":
                if setup_failure == "exception":
                    raise sqlite3.OperationalError("setup failed")
                return super().execute("SELECT 0")
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs, factory=SetupFailureConnection)
        opened.append(conn)
        return conn

    monkeypatch.setattr(db.sqlite3, "connect", connect)
    with pytest.raises(sqlite3.OperationalError):
        with db.connect():
            pytest.fail("An unprotected connection must never reach application code")
    assert len(opened) == 1
    assert_closed(opened[0])


def test_successful_writes_commit_and_close(database):
    with db.connect() as conn:
        conn.execute("INSERT INTO orders(id,retailer,order_date,simulated) VALUES ('new-order','Demo','2026-10-30',1)")
    assert_closed(conn)
    with db.connect() as check:
        assert check.execute("SELECT retailer FROM orders WHERE id='new-order'").fetchone()[0] == "Demo"


@pytest.mark.parametrize("operation", ["create", "pickup", "availability"])
def test_event_failure_rolls_back_workflow_and_event(database, monkeypatch, operation):
    if operation == "availability":
        returns.mark_pickup_missed("case-demo-001")
    before_cases = returns.list_cases()
    before_activity = returns.activity()
    original_event = returns._event

    def fail_after_event(*args, **kwargs):
        original_event(*args, **kwargs)
        raise RuntimeError("event persistence failed")

    monkeypatch.setattr(returns, "_event", fail_after_event)
    with pytest.raises(RuntimeError, match="event persistence failed"):
        if operation == "create":
            returns.create_case("demo-order-002", "item-coat-002", "wrong_size")
        elif operation == "pickup":
            returns.advance_simulation("case-demo-001", "picked_up")
        else:
            returns.collect_availability("case-demo-001", "Weekdays after 5 PM")
    assert returns.list_cases() == before_cases
    assert returns.activity() == before_activity
    with db.connect() as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
