"""Explicit atomic import migration. Never called by application startup.

Rebuild only order_items to represent absent prices/policies as SQL NULL.
Foreign keys are disabled before BEGIN for SQLite's documented table rebuild
procedure and checked before COMMIT. All existing IDs and relationships survive.
"""
from pathlib import Path
import sqlite3
import sys
import re

VERSION = "002_order_imports"
ORDER_COLUMNS = (
    "marketplace TEXT", "currency TEXT", "order_status TEXT", "imported_at TEXT",
    "review_status TEXT NOT NULL DEFAULT 'unreviewed'",
)
INTEGRATION_COLUMNS = (
    "account_email TEXT", "history_cursor TEXT", "page_cursor TEXT", "sync_anchor TEXT",
    "last_sync_at TEXT", "error_code TEXT", "sync_lease_until TEXT", "generation TEXT",
)
ITEM_SCHEMA = """CREATE TABLE order_items_new (
    id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
    name TEXT NOT NULL, sku TEXT, quantity INTEGER CHECK(quantity IS NULL OR quantity>0),
    price REAL, return_window_days INTEGER, final_sale INTEGER DEFAULT 0,
    external_item_id TEXT, product_identifier TEXT, unit_price TEXT,
    currency TEXT, details_json TEXT NOT NULL DEFAULT '{}'
)"""
TABLES = (
    """CREATE TABLE import_previews (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), source TEXT NOT NULL,
        digest TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL, result_json TEXT
    )""",
    """CREATE TABLE order_source_references (
        id TEXT PRIMARY KEY, order_id TEXT NOT NULL, user_id TEXT NOT NULL,
        source TEXT NOT NULL, source_reference TEXT NOT NULL, observation_json TEXT NOT NULL,
        source_timestamp TEXT, imported_at TEXT NOT NULL,
        FOREIGN KEY(order_id,user_id) REFERENCES orders(id,user_id),
        UNIQUE(user_id,order_id,source,source_reference)
    )""",
    """CREATE TABLE oauth_attempts (
        state_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        session_hash TEXT NOT NULL, verifier_encrypted TEXT NOT NULL,
        integration_generation TEXT NOT NULL,
        expires_at TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE gmail_messages (
        integration_id TEXT NOT NULL REFERENCES integrations(id),
        message_id TEXT NOT NULL, processed_at TEXT NOT NULL, outcome TEXT NOT NULL,
        observation_json TEXT,
        PRIMARY KEY(integration_id,message_id)
    )""",
)
INDEXES = (
    "CREATE UNIQUE INDEX idx_orders_id_owner ON orders(id,user_id)",
    "CREATE UNIQUE INDEX idx_import_order_identity ON orders(user_id,retailer,marketplace,external_order_id) WHERE simulated=0 AND external_order_id IS NOT NULL AND marketplace IS NOT NULL",
    "CREATE INDEX idx_order_items_order ON order_items(order_id)",
    "CREATE INDEX idx_previews_owner ON import_previews(user_id,created_at)",
    "CREATE INDEX idx_sources_owner ON order_source_references(user_id,order_id)",
    "CREATE UNIQUE INDEX idx_credentials_integration ON integration_credentials(integration_id)",
)


def _check(conn):
    def sql_key(sql):
        return re.sub(r"\s+", "", sql).lower().rstrip(';')
    for statement in (*TABLES, *INDEXES):
        tokens = statement.split()
        if tokens[1] == 'UNIQUE':
            kind, name = 'index', tokens[3]
        else:
            kind, name = tokens[1].lower(), tokens[2]
        row = conn.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?', (kind,name)).fetchone()
        if row is None or sql_key(row[0]) != sql_key(statement):
            raise RuntimeError(f'Import schema drift detected: {name}')
    item_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_items'").fetchone()
    if not item_sql or sql_key(item_sql[0].replace('"order_items"', 'order_items')) != sql_key(ITEM_SCHEMA.replace('order_items_new', 'order_items')):
        raise RuntimeError('Import item schema drift detected')
    required = {"import_previews", "order_source_references", "oauth_attempts", "gmail_messages"}
    if not required.issubset({r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}):
        raise RuntimeError("Import schema drift detected")
    for table, columns in (("orders", ORDER_COLUMNS), ("integrations", INTEGRATION_COLUMNS)):
        actual = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not {c.split()[0] for c in columns}.issubset(actual):
            raise RuntimeError("Import column drift detected")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign key violations; rolled back")
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise RuntimeError("Database integrity check failed")


def migrate(database_path):
    path = Path(database_path).resolve()
    conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE version='001_customer_ownership'").fetchone():
            raise RuntimeError("Migration 001 is required")
        applied = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone()
        if not applied:
            old_columns = [r[1] for r in conn.execute('PRAGMA table_info(order_items)')]
            if old_columns != ['id','order_id','name','sku','quantity','price','return_window_days','final_sale']:
                raise RuntimeError('Unexpected legacy item schema; inspect before migrating')
            extra_objects = conn.execute("SELECT name,sql FROM sqlite_master WHERE tbl_name='order_items' AND type IN ('index','trigger') AND sql IS NOT NULL AND name!='idx_order_items_order'").fetchall()
            for definition in ORDER_COLUMNS:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {definition}")
            conn.execute("UPDATE orders SET currency='USD' WHERE simulated=1")
            for definition in INTEGRATION_COLUMNS:
                conn.execute(f"ALTER TABLE integrations ADD COLUMN {definition}")
            conn.execute("ALTER TABLE import_history ADD COLUMN summary_json TEXT NOT NULL DEFAULT '{}'")
            conn.execute(ITEM_SCHEMA)
            conn.execute("""INSERT INTO order_items_new(id,order_id,name,sku,quantity,price,return_window_days,final_sale,unit_price,currency)
                SELECT id,order_id,name,sku,quantity,price,return_window_days,final_sale,CAST(price AS TEXT),
                CASE WHEN (SELECT simulated FROM orders WHERE orders.id=order_items.order_id)=1 THEN 'USD' ELSE NULL END FROM order_items""")
            conn.execute("DROP TABLE order_items")
            conn.execute("ALTER TABLE order_items_new RENAME TO order_items")
            for statement in TABLES:
                conn.execute(statement)
            for statement in INDEXES:
                conn.execute(statement)
            for _, statement in extra_objects:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,datetime('now'))", (VERSION,))
        _check(conn)
        conn.execute("COMMIT")
        return not bool(applied)
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python 002_order_imports.py <DISPOSABLE_database_path>")
    print("Migration applied." if migrate(sys.argv[1]) else "Already applied; verified.")
