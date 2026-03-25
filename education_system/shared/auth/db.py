"""Database connection helper for the shared auth database."""

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_AUTH_DB_DIR = Path(__file__).resolve().parent.parent / "data" / "db_files"
AUTH_DB_FILE = _AUTH_DB_DIR / "auth.db"


def _secure_db_permissions(path: str) -> None:
    """Set database file to owner-only read/write (chmod 600)."""
    try:
        p = Path(path)
        if p.exists():
            os.chmod(p, 0o600)
        # Also secure WAL and SHM files if they exist
        for suffix in ("-wal", "-shm"):
            wal = Path(str(path) + suffix)
            if wal.exists():
                os.chmod(wal, 0o600)
    except OSError:
        pass  # May fail on non-POSIX systems


def connect(db_path: str | None = None, max_retries: int = 3, retry_delay: float = 0.2) -> sqlite3.Connection:
    """Open a connection to the auth database with retry on lock."""
    path = db_path or str(AUTH_DB_FILE)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            _secure_db_permissions(path)
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(
                    "Auth database locked, retrying in %.1fs (attempt %d/%d)",
                    retry_delay, attempt + 1, max_retries,
                )
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise


@contextmanager
def get_connection(db_path: str | None = None, *, commit: bool = False):
    """Context manager for database connections.

    Usage:
        with get_connection(path) as conn:
            conn.execute(...)
        # auto-closes on exit

        with get_connection(path, commit=True) as conn:
            conn.execute("INSERT ...")
        # auto-commits on success, rolls back on error, always closes
    """
    conn = connect(db_path)
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()
