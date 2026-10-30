"""Explicit atomic dashboard migration; never run during application startup."""
import importlib.util
from pathlib import Path
import re
import sqlite3
import sys

VERSION = '003_shopping_dashboard'
COLUMNS = {'orders': ('total_amount TEXT', 'payment_status TEXT'),
           'order_items': ('category TEXT', 'image_url TEXT', 'return_deadline TEXT')}
TABLES = (
    """CREATE TABLE refunds (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        order_id TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','received')),
        effective_date TEXT NOT NULL, reference TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
        confirmed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY(order_id,user_id) REFERENCES orders(id,user_id),
        UNIQUE(user_id,order_id,reference), UNIQUE(id,user_id),
        CHECK((status='received' AND confirmed_at IS NOT NULL) OR (status='pending' AND confirmed_at IS NULL))
    )""",
    """CREATE TABLE refund_revisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, refund_id TEXT NOT NULL,
        user_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY(refund_id,user_id) REFERENCES refunds(id,user_id)
    )""",
    """CREATE TABLE retailer_accounts (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        retailer TEXT NOT NULL, provider TEXT NOT NULL, account_reference TEXT NOT NULL,
        display_name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(user_id,retailer,provider,account_reference)
    )""",
)
TRIGGERS = (
    """CREATE TRIGGER shopping_order_owner_insert BEFORE INSERT ON orders
       WHEN NEW.user_id IS NULL BEGIN SELECT RAISE(ABORT,'Order owner required'); END""",
    """CREATE TRIGGER shopping_order_owner_update BEFORE UPDATE OF user_id ON orders
       WHEN NEW.user_id IS NULL BEGIN SELECT RAISE(ABORT,'Order owner required'); END""",
)


def _check(conn):
    key = lambda sql: re.sub(r'\s+', '', sql).lower().rstrip(';')
    spec = importlib.util.spec_from_file_location('imports_migration', Path(__file__).with_name('002_order_imports.py'))
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    for sql in (*previous.TABLES, *previous.INDEXES, *TABLES, *TRIGGERS):
        tokens = sql.split()
        kind, name = ('index', tokens[3]) if tokens[1] == 'UNIQUE' else tokens[1:3]
        actual = conn.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?', (kind.lower(), name)).fetchone()
        if actual is None or key(actual[0]) != key(sql):
            raise RuntimeError(f'Shopping schema drift: {name}')
    item_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_items'").fetchone()
    expected = previous.ITEM_SCHEMA.replace('order_items_new', 'order_items').rstrip().removesuffix(')') + ', category TEXT, image_url TEXT, return_deadline TEXT)'
    if item_sql is None or key(item_sql[0].replace('"order_items"', 'order_items')) != key(expected):
        raise RuntimeError('Shopping item schema drift')
    for table, columns in (('orders', previous.ORDER_COLUMNS), ('integrations', previous.INTEGRATION_COLUMNS)):
        actual = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
        if not {column.split()[0] for column in columns}.issubset(actual):
            raise RuntimeError(f'Shopping predecessor column drift: {table}')
    for table, definitions in COLUMNS.items():
        actual = {row[1]: row for row in conn.execute(f'PRAGMA table_info({table})')}
        for definition in definitions:
            name = definition.split()[0]
            if name not in actual or actual[name][2:5] != ('TEXT', 0, None):
                raise RuntimeError(f'Shopping column drift: {table}.{name}')
    if conn.execute('PRAGMA foreign_key_check').fetchall() or conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise RuntimeError('Shopping database integrity check failed')


def migrate(database_path):
    path = Path(database_path).resolve()
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None, timeout=30)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE version='002_order_imports'").fetchone():
            raise RuntimeError('Migration 002 is required')
        applied = conn.execute('SELECT 1 FROM schema_migrations WHERE version=?', (VERSION,)).fetchone()
        if not applied:
            # Migration 002's validator expects the pre-003 item schema.
            spec = importlib.util.spec_from_file_location('imports_migration', Path(__file__).with_name('002_order_imports.py'))
            previous = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(previous)
            previous._check(conn)
            for table, definitions in COLUMNS.items():
                for definition in definitions:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')
            for statement in (*TABLES, *TRIGGERS):
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations VALUES (?,datetime('now'))", (VERSION,))
        _check(conn)
        conn.execute('COMMIT')
        return not bool(applied)
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python 003_shopping_dashboard.py <DISPOSABLE_database_path>')
    print('Migration applied.' if migrate(sys.argv[1]) else 'Already applied; verified.')
