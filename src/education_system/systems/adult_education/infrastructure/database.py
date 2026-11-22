"""SQLite connection for the Adult Education System.

One database file (``paths.ADULT_EDUCATION_DB``). Each domain module
registers its ``CREATE ... IF NOT EXISTS`` script with :func:`register_schema`;
:func:`connect` applies them once per file, so a fresh install builds itself.

Foreign keys are ON and every foreign key points at a real table here.
Tests and probes point it at a temporary file with :func:`use_database`.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from education_system import paths

#: A UNIQUE / FOREIGN KEY rule refused a write.
IntegrityError = sqlite3.IntegrityError

_override: Path | None = None
_schemas: list[tuple[str, Callable[[sqlite3.Connection], None]]] = []
_initialised: set[Path] = set()
_lock = threading.Lock()


def db_path() -> Path:
    return _override or paths.ADULT_EDUCATION_DB


def use_database(path: str | Path | None) -> None:
    """Point every connection at *path* (``None`` restores the default)."""
    global _override
    _override = Path(path) if path is not None else None


def register_schema(name: str, ddl: str) -> None:
    """Add a ``CREATE ... IF NOT EXISTS`` script. Idempotent per *name*."""
    register_setup(name, lambda conn: conn.executescript(ddl))


def register_setup(name: str, fn: Callable[[sqlite3.Connection], None]) -> None:
    """Add an idempotent set-up step (run in registration order, once per file)."""
    if not any(existing == name for existing, _ in _schemas):
        _schemas.append((name, fn))
        _initialised.clear()


def _open(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection that commits on success and rolls back on error."""
    path = db_path()
    conn = _open(path)
    try:
        if path not in _initialised:
            with _lock:
                if path not in _initialised:
                    conn.execute("PRAGMA journal_mode = WAL")
                    for _name, setup in _schemas:
                        setup(conn)
                        conn.commit()
                    _initialised.add(path)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
