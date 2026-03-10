"""Database connection helper for the shared auth database."""

import sqlite3
from pathlib import Path

_AUTH_DB_DIR = Path(__file__).resolve().parent.parent / "data" / "db_files"
AUTH_DB_FILE = _AUTH_DB_DIR / "auth.db"


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection to the auth database."""
    path = db_path or str(AUTH_DB_FILE)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
