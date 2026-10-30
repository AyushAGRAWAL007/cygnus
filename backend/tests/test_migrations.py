"""Migration integration tests: only disposable copies, never application startup."""
import contextlib
import io
from pathlib import Path
import runpy
import sqlite3
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/migrations/001_customer_ownership.py"
LEGACY_SCHEMA = """
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
CONNECT = sqlite3.connect


def snapshot(path):
    with contextlib.closing(CONNECT(path.as_uri() + "?mode=ro", uri=True)) as conn:
        schema = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        data = {name: conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
                for kind, name, _, _ in schema if kind == "table"}
        return schema, data


def run_migration(path, fail_after=None):
    class FaultConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            cursor = super().execute(sql, parameters)
            if fail_after and fail_after in sql:
                raise RuntimeError("injected failure")
            return cursor

        def executescript(self, sql):
            cursor = super().executescript(sql)
            if fail_after and fail_after in sql:
                raise RuntimeError("injected failure")
            return cursor

    def connect(*args, **kwargs):
        return CONNECT(*args, **kwargs, factory=FaultConnection)

    with patch.object(sys, "argv", [str(SCRIPT), str(path)]), patch("sqlite3.connect", connect), contextlib.redirect_stdout(io.StringIO()):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cygnus-migration-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "copy.db"
        with contextlib.closing(CONNECT(self.path)) as conn:
            conn.executescript(LEGACY_SCHEMA)
            for i in range(4):
                conn.execute("INSERT INTO orders VALUES (?, 'Fictional Demo', '2026-10-01', 1)", (f"order-{i}",))
                conn.execute("INSERT INTO order_items VALUES (?, ?, 'Demo item', ?, 1, 25.0, 30, 0)", (f"item-{i}", f"order-{i}", f"sku-{i}"))
            for i in range(2):
                conn.execute("INSERT INTO return_cases VALUES (?, ?, ?, 'wrong_size', 'resolved', NULL, 1, '2026-10-02', '2026-10-03', 1)", (f"case-{i}", f"order-{i}", f"item-{i}"))
                for j in range(6):
                    conn.execute("INSERT INTO case_events(case_id,event_type,message,evidence,created_at,simulated) VALUES (?, 'demo', 'Simulated event', '{}', '2026-10-03', 1)", (f"case-{i}",))
            conn.commit()

    def test_success_preserves_records_and_repeat_is_noop(self):
        _, original = snapshot(self.path)
        run_migration(self.path)
        migrated = snapshot(self.path)
        for name, rows in original.items():
            actual = migrated[1][name]
            self.assertEqual([row[:len(rows[0])] for row in actual], rows)
        with contextlib.closing(CONNECT(self.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(conn.execute("SELECT version FROM schema_migrations").fetchall(), [("001_customer_ownership",)])
            self.assertEqual(conn.execute("SELECT user_id, source, external_order_id FROM orders").fetchall(), [(None, "demo", None)] * 4)
        run_migration(self.path)
        self.assertEqual(snapshot(self.path), migrated)

    def test_failure_rolls_back_all_schema_and_data(self):
        original = snapshot(self.path)
        for stage in ("CREATE TABLE IF NOT EXISTS users", "ALTER TABLE orders ADD COLUMN user_id", "CREATE INDEX IF NOT EXISTS idx_orders_user_date", "INSERT INTO schema_migrations"):
            with self.subTest(stage=stage):
                path = self.path.parent / (str(len(stage)) + "-failure.db")
                with contextlib.closing(CONNECT(self.path.as_uri() + "?mode=ro", uri=True)) as source:
                    with contextlib.closing(CONNECT(path)) as target:
                        source.backup(target)
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    run_migration(path, stage)
                self.assertEqual(snapshot(path), original)

    def test_repeat_rejects_schema_drift(self):
        run_migration(self.path)
        with contextlib.closing(CONNECT(self.path)) as conn:
            conn.execute("DROP INDEX idx_orders_user_date")
            conn.commit()
        before = snapshot(self.path)
        with self.assertRaisesRegex(RuntimeError, "schema"):
            run_migration(self.path)
        self.assertEqual(snapshot(self.path), before)

    def test_concurrent_cli_runs_apply_one_version(self):
        command = [sys.executable, "-B", str(SCRIPT), str(self.path)]
        first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for process in (first, second):
            output, errors = process.communicate(timeout=40)
            self.assertEqual(process.returncode, 0, output + errors)
        with contextlib.closing(CONNECT(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_existing_foreign_key_violation_rolls_back(self):
        with contextlib.closing(CONNECT(self.path)) as conn:
            conn.execute("UPDATE case_events SET case_id = 'missing' WHERE id = 1")
            conn.commit()
        original = snapshot(self.path)
        with self.assertRaisesRegex(RuntimeError, "Foreign key"):
            run_migration(self.path)
        self.assertEqual(snapshot(self.path), original)

    def test_wrong_existing_column_is_rejected_atomically(self):
        with contextlib.closing(CONNECT(self.path)) as conn:
            conn.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")
            conn.commit()
        original = snapshot(self.path)
        with self.assertRaisesRegex(RuntimeError, "schema"):
            run_migration(self.path)
        self.assertEqual(snapshot(self.path), original)

    def test_ownership_foreign_key_and_import_uniqueness(self):
        run_migration(self.path)
        with contextlib.closing(CONNECT(self.path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE orders SET user_id='missing' WHERE id='order-0'")
            conn.execute("INSERT INTO users(id,email,display_name,created_at) VALUES ('u1','one@example.test','One','2026-10-30')")
            conn.execute("INSERT INTO users(id,email,display_name,created_at) VALUES ('u2','two@example.test','Two','2026-10-30')")
            conn.execute("UPDATE orders SET user_id='u1',source='amazon_file',external_order_id='external-1' WHERE id='order-0'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE orders SET user_id='u1',source='amazon_file',external_order_id='external-1' WHERE id='order-1'")
            conn.execute("UPDATE orders SET user_id='u2',source='amazon_file',external_order_id='external-1' WHERE id='order-1'")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orders WHERE external_order_id='external-1'").fetchone()[0], 2)

    def test_missing_path_does_not_create_database(self):
        missing = self.path.parent / "missing.db"
        with self.assertRaises((SystemExit, sqlite3.OperationalError)):
            run_migration(missing)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
