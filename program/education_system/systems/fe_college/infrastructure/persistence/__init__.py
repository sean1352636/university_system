"""SQLite persistence for the FE College system.

One connection helper, used by every repository. It applies the same PRAGMAs
the rest of the platform uses (WAL, foreign keys on, a busy timeout) — foreign
keys in particular are off by default in SQLite, and the schema relies on
``ON DELETE CASCADE`` to keep a deleted learner from leaving orphaned
attendance and fee rows behind.

Opening a connection is not free: SQLite re-parses the schema each time, which
costs tens of milliseconds against a database this wide. Repository calls are
individually cheap, but a screen that makes a few hundred of them pays for
every one. :func:`session` therefore lets a caller hold one connection open for
a batch of work — the dashboards and the demo seeder both use it — while every
repository method continues to work unchanged outside a session.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from pathlib import Path

from education_system.paths import FE_COLLEGE_DB, ensure_fe_college_directories

# Module-level override so tests can point every repository at a temp file
# without monkey-patching each one. ``None`` means "use FE_COLLEGE_DB".
_db_path_override: Path | None = None

# The connection an open session is sharing. Thread-local because a SQLite
# connection must not be used from a thread other than the one that made it —
# a background worker gets its own connection rather than borrowing this one.
_state = threading.local()


def set_db_path(path: str | Path | None) -> None:
    """Redirect every connection to ``path`` (or back to the default)."""
    global _db_path_override
    _db_path_override = Path(path) if path is not None else None


def db_path() -> Path:
    """The database file this process is talking to."""
    return _db_path_override or FE_COLLEGE_DB


def _shared() -> sqlite3.Connection | None:
    return getattr(_state, "conn", None)


def _open() -> sqlite3.Connection:
    """Open a new connection with the platform's standard PRAGMAs."""
    target = db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect() -> sqlite3.Connection:
    """Open a connection the caller is responsible for closing.

    Ignores any open session — callers of this function close what they get,
    and closing a session's connection out from under it would break the rest
    of the batch.
    """
    return _open()


@contextlib.contextmanager
def session():
    """Hold one connection open for everything inside the block.

    All work in the block commits together at the end, or rolls back together
    on an exception — so a batch can never be left half-applied. Nesting is
    allowed and joins the outer session rather than starting a second one.
    """
    if _shared() is not None:
        yield _state.conn          # already in a session — join it
        return
    conn = _open()
    _state.conn = conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _state.conn = None
        conn.close()


@contextlib.contextmanager
def transaction():
    """Connection scope that commits on success and rolls back on error.

    Inside a :func:`session` this joins the batch instead: committing here
    would defeat the session's all-or-nothing guarantee.
    """
    shared = _shared()
    if shared is not None:
        yield shared
        return
    conn = _open()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextlib.contextmanager
def read_only():
    """Connection scope for queries — no commit, always closed."""
    shared = _shared()
    if shared is not None:
        yield shared
        return
    conn = _open()
    try:
        yield conn
    finally:
        conn.close()


def ensure_directories() -> None:
    """Create the FE College runtime tree. Safe to call repeatedly."""
    ensure_fe_college_directories()


__all__ = [
    "connect",
    "db_path",
    "ensure_directories",
    "read_only",
    "session",
    "set_db_path",
    "transaction",
]
