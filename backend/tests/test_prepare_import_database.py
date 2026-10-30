"""Preparation uses synthetic sources only; existing databases remain untouched."""
from contextlib import closing
from pathlib import Path
import runpy
import sqlite3

import pytest

from .test_migrations import LEGACY_SCHEMA

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = runpy.run_path(str(BACKEND / 'scripts/prepare_import_database.py'))


@pytest.mark.parametrize('migration_count', [0, 1, 2, 3])
def test_prepares_and_verifies_all_migrations_without_changing_source(tmp_path, migration_count, monkeypatch):
    source = tmp_path / 'source.db'
    target = tmp_path / 'prepared.db'
    with closing(sqlite3.connect(source)) as conn:
        conn.executescript(LEGACY_SCHEMA)
        conn.execute("INSERT INTO orders VALUES ('order-1','Demo','2026-10-01',1)")
        conn.execute("INSERT INTO order_items VALUES ('item-1','order-1','Item','sku',1,25,30,0)")
        conn.commit()
    for name in SCRIPT['MIGRATIONS'][:migration_count]:
        runpy.run_path(str(BACKEND / 'migrations' / name))['migrate'](source)
    original = source.read_bytes()
    assert SCRIPT['prepare'](target, source) == target
    assert source.read_bytes() == original
    assert SCRIPT['verify'](target) == ('001_customer_ownership', '002_order_imports', '003_shopping_dashboard')
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute('SELECT id,name,price FROM order_items').fetchall() == [('item-1','Item',25)]
    from app.config import get_settings
    from app.imports.service import database
    monkeypatch.setattr(get_settings(), 'database_path', str(target))
    with database() as conn:
        assert conn.execute('SELECT COUNT(*) FROM import_previews').fetchone()[0] == 0
    with closing(sqlite3.connect(target)) as conn:
        conn.execute('DROP TABLE import_previews')
        conn.commit()
    with pytest.raises(RuntimeError, match='schema drift'):
        SCRIPT['verify'](target)
    with closing(sqlite3.connect(target)) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version='002_order_imports'")
        conn.commit()
    with pytest.raises(RuntimeError, match='Required migrations are missing'):
        SCRIPT['verify'](target)


def test_existing_output_and_live_path_are_refused(tmp_path):
    source = tmp_path / 'source.db'
    source.write_bytes(b'source untouched')
    existing = tmp_path / 'backup.db'
    existing.write_bytes(b'backup untouched')
    for target in (existing, source, SCRIPT['LIVE']):
        with pytest.raises(ValueError):
            SCRIPT['prepare'](target, source)
    assert existing.read_bytes() == b'backup untouched'
    assert source.read_bytes() == b'source untouched'
