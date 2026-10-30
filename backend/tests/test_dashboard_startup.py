"""A migrated empty customer store must stay empty on application startup."""
from contextlib import closing
from pathlib import Path
import runpy
import sqlite3

from app import returns
from app.config import get_settings
from .test_migrations import LEGACY_SCHEMA


def test_empty_migrated_database_starts_without_inventing_demo_orders(tmp_path, monkeypatch):
    path = tmp_path / 'empty-shopping.db'
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(LEGACY_SCHEMA)
    root = Path(__file__).resolve().parents[1]
    for name in ('001_customer_ownership.py', '002_order_imports.py', '003_shopping_dashboard.py'):
        runpy.run_path(str(root / 'migrations' / name))['migrate'](path)
    monkeypatch.setattr(get_settings(), 'database_path', str(path))
    returns.initialize()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM return_cases').fetchone()[0] == 0
