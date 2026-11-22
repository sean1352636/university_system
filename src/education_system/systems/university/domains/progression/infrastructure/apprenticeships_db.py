"""Read-only access to the apprenticeships system's database.

The progression domain's gateway reads apprenticeship data without changing
it; opening the SQLite file lives here so the domain layer does not import
the SQL driver (slice rule). Plain :mod:`sqlite3`, not the university
database wrapper, because that applies write-side pragmas a read-only
connection can't take.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: The driver's errors, for callers that catch them.
Error = sqlite3.Error


def open_readonly(db_path) -> sqlite3.Connection:
    """A read-only connection to ``db_path`` returning rows by name."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
