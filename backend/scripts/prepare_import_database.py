"""Copy an existing database, then migrate only that new disposable copy.

No application imports: importing/starting the app can seed the configured DB.
The source is opened mode=ro, and an existing target is always refused.
"""
import argparse
from contextlib import closing
from pathlib import Path
import runpy
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
LIVE = BACKEND / 'cygnus.db'
MIGRATIONS = ('001_customer_ownership.py', '002_order_imports.py', '003_shopping_dashboard.py')


def verify(database_path):
    """Verify the ledger and current schema without changing data."""
    modules = [runpy.run_path(str(BACKEND / 'migrations' / name)) for name in MIGRATIONS]
    with closing(sqlite3.connect(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        applied = {row[0] for row in conn.execute('SELECT version FROM schema_migrations')}
        if not {module['VERSION'] for module in modules}.issubset(applied):
            raise RuntimeError('Required migrations are missing from the prepared database')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'users', 'sessions', 'app_metadata'}.issubset(tables):
            raise RuntimeError('Required authentication tables are missing')
        # Later migrations extend schemas checked exactly by their predecessors.
        # Validate the final schema, rather than rerunning an obsolete validator.
        modules[-1]['_check'](conn)
    return tuple(module['VERSION'] for module in modules)


def prepare(output, source=LIVE):
    target, source = Path(output).resolve(), Path(source).resolve()
    if target == LIVE.resolve() or target == source or target.exists() or target.suffix != '.db':
        raise ValueError('Choose a new disposable .db path; existing files and the live path are refused')
    if not source.is_file():
        raise ValueError('Source database does not exist')
    # Reserve exclusively so another preparation cannot overwrite this target.
    with target.open('xb'):
        pass
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(target)) as copy:
            original.backup(copy)
    with closing(sqlite3.connect(target)) as conn:
        ledger_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
        applied = {row[0] for row in conn.execute('SELECT version FROM schema_migrations')} if ledger_exists else set()
    for name in MIGRATIONS:
        module = runpy.run_path(str(BACKEND / 'migrations' / name))
        if module['VERSION'] not in applied:
            module['migrate'](target)
    verify(target)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source', default=str(LIVE))
    arguments = parser.parse_args()
    target = prepare(arguments.output, arguments.source)
    print('Prepared disposable database:', target)
    print('Verified migrations:', ', '.join(verify(target)))
    print('Start the backend with DATABASE_PATH set to this exact path; restart any running backend.')
