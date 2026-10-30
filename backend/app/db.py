"""SQLite connections with foreign-key enforcement and managed write cleanup.

Normal exit commits pending writes. Setup, operation, and commit failures roll
back pending work, and every successfully opened connection is closed.
"""
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().database_path)
    try:
        # SQLite ignores this setting inside a transaction: enable it before
        # handing the connection to callers, including startup initialization.
        conn.execute("PRAGMA foreign_keys = ON")
        enabled = conn.execute("PRAGMA foreign_keys").fetchone()
        if enabled is None or enabled[0] != 1:
            raise sqlite3.OperationalError("SQLite foreign-key enforcement could not be enabled")
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except BaseException:
        # Also covers commit-time constraint failures and interrupted requests.
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def check_database() -> bool:
    """True if we can open the DB file and run a trivial query."""
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
