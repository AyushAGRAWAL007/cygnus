"""SQLite connection helper.

SQLite = a whole database stored in one file. For Cygnus it will hold orders,
return requests and a timeline of every event. In Part 1 we only prove the
file can be created and queried; tables arrive in Part 2.
"""
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
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
