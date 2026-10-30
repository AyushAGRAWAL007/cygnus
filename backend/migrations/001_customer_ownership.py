"""Explicit, atomic ownership migration; never invoked by application startup."""
import re
import sqlite3
import sys
from pathlib import Path

VERSION = "001_customer_ownership"
LEDGER = "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"

TABLE_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT,
            email_verified INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS auth_identities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            provider TEXT NOT NULL,
            provider_subject TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(provider, provider_subject)
        )""",
    """CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            revoked_at TEXT
        )""",
    """CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS integrations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'disconnected',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, provider)
        )""",
    """CREATE TABLE IF NOT EXISTS integration_credentials (
            id TEXT PRIMARY KEY,
            integration_id TEXT NOT NULL REFERENCES integrations(id),
            encrypted_access_token TEXT,
            encrypted_refresh_token TEXT,
            expires_at TEXT,
            updated_at TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS import_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            imported_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )""",
    """CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
)

INDEX_STATEMENTS = (
    """CREATE INDEX IF NOT EXISTS idx_orders_user_date
            ON orders(user_id, order_date)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS
            idx_orders_user_source_external
            ON orders(user_id, source, external_order_id)
            WHERE external_order_id IS NOT NULL""",
    """CREATE INDEX IF NOT EXISTS idx_order_items_order
            ON order_items(order_id)""",
    """CREATE INDEX IF NOT EXISTS idx_return_cases_order
            ON return_cases(order_id)""",
    """CREATE INDEX IF NOT EXISTS idx_return_cases_item
            ON return_cases(item_id)""",
    """CREATE INDEX IF NOT EXISTS idx_case_events_case
            ON case_events(case_id)""",
    """CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id)""",
    """CREATE INDEX IF NOT EXISTS idx_import_history_user
            ON import_history(user_id, created_at)""",
)

ORDER_COLUMNS = (
    "user_id TEXT REFERENCES users(id)",
    "source TEXT NOT NULL DEFAULT 'demo'",
    "external_order_id TEXT",
)


def _sql_key(sql):
    return re.sub(r"\s+", "", sql.replace("IF NOT EXISTS", "")).lower().rstrip(";")


def _validate_schema(conn):
    for statement in (LEDGER, *TABLE_STATEMENTS, *INDEX_STATEMENTS):
        parts = statement.split()
        kind, name = parts[1].lower(), parts[5]
        if kind == "unique":
            kind, name = "index", parts[6]
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = ? AND name = ?", (kind, name)
        ).fetchone()
        if row is None or _sql_key(row[0]) != _sql_key(statement):
            raise RuntimeError(f"Unexpected schema for {name}; inspect before retrying")
    columns = {row[1]: row for row in conn.execute("PRAGMA table_info(orders)")}
    expected = {
        "user_id": ("TEXT", 0, None),
        "source": ("TEXT", 1, "'demo'"),
        "external_order_id": ("TEXT", 0, None),
    }
    for name, definition in expected.items():
        row = columns.get(name)
        if row is None or tuple(row[2:5]) != definition or row[5] != 0:
            raise RuntimeError(f"Unexpected schema for orders.{name}")
    if not any(row[2:5] == ("users", "user_id", "id") for row in conn.execute("PRAGMA foreign_key_list(orders)")):
        raise RuntimeError("Unexpected schema: orders.user_id must reference users.id")


def migrate(database_path):
    path = Path(database_path).resolve()
    # Explicit transaction control; mode=rw refuses nonexistent database paths.
    conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Foreign key enforcement unavailable")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(LEDGER)
        applied = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
        if not applied:
            for statement in TABLE_STATEMENTS:
                conn.execute(statement)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
            for definition in ORDER_COLUMNS:
                if definition.split()[0] not in columns:
                    conn.execute(f"ALTER TABLE orders ADD COLUMN {definition}")
            for statement in INDEX_STATEMENTS:
                conn.execute(statement)
        _validate_schema(conn)
        if list(conn.execute("PRAGMA foreign_key_check")):
            raise RuntimeError("Foreign key violations; migration rolled back")
        if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("Database integrity check failed")
        if not applied:
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (VERSION,),
            )
        conn.execute("COMMIT")
        return not bool(applied)
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python 001_customer_ownership.py <database_path>")
    changed = migrate(sys.argv[1])
    print("Migration applied successfully." if changed else "Migration already applied; schema verified.")


if __name__ == "__main__":
    main()
