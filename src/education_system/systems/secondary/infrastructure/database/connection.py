"""SQLite connection for the Secondary School System.

One database file (``paths.SECONDARY_PUPILS_DB``, i.e.
``var/data/secondary/secondary.db``). Each domain module registers its own
schema with :func:`register_schema`; :func:`connect` applies every registered
schema once per database file, so a fresh install builds itself on first use.

Foreign keys are ON for every connection, and every foreign key must point at
a real table in this file (the old system referenced a ``students`` table
that never existed, which made ten features unable to save anything).

Tests point the module at a temporary file with :func:`use_database`.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from education_system import paths

#: A UNIQUE / FOREIGN KEY rule refused a write. Domain code catches this
#: rather than importing sqlite3 itself (SQL stays in infrastructure).
IntegrityError = sqlite3.IntegrityError

_override: Path | None = None
_schemas: list[tuple[str, str]] = []
#: One-off changes to tables that already exist (a CREATE ... IF NOT EXISTS
#: script can't alter them). Each takes a connection, must be idempotent and
#: does its own commit; they run after the schemas, once per database file.
_upgrades: list[tuple[str, Callable[[sqlite3.Connection], None]]] = []
_initialised: set[Path] = set()
_lock = threading.Lock()


def db_path() -> Path:
    """The database file in use."""
    return _override or paths.SECONDARY_PUPILS_DB


def use_database(path: str | Path | None) -> None:
    """Point every connection at *path* (``None`` restores the default)."""
    global _override
    _override = Path(path) if path is not None else None


def register_schema(name: str, ddl: str) -> None:
    """Add a module's ``CREATE ... IF NOT EXISTS`` script. Idempotent."""
    if not any(existing == name for existing, _ in _schemas):
        _schemas.append((name, ddl))
        _initialised.clear()


def register_upgrade(name: str, fn: Callable[[sqlite3.Connection], None]) -> None:
    """Add an idempotent upgrade for an existing table. Idempotent."""
    if not any(existing == name for existing, _ in _upgrades):
        _upgrades.append((name, fn))
        _initialised.clear()


def _open(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def _ensure_schema(conn: sqlite3.Connection, path: Path) -> None:
    if path in _initialised:
        return
    with _lock:
        if path in _initialised:
            return
        conn.execute("PRAGMA journal_mode = WAL")
        for _name, ddl in _schemas:
            conn.executescript(ddl)
        conn.commit()
        for _name, upgrade in _upgrades:
            upgrade(conn)
            conn.commit()
        _initialised.add(path)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection with the schema in place. Commits on success, rolls
    back on any exception, always closes."""
    path = db_path()
    conn = _open(path)
    try:
        _ensure_schema(conn, path)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
