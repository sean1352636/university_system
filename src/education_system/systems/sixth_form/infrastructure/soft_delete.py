"""Archive ("soft delete") for records UK retention rules expect to keep.

Disciplinary cases, the SEND register, first-aid incidents, staff HR
records and the visitor log must survive a slip of the Delete button:
their modules' ``delete_*`` functions archive the row instead of
removing it. An archived row carries who archived it, when and why,
drops out of the module's lists (unless the caller asks for archived
rows) and can be restored.

Columns (added lazily by each module's ``init_db`` via
:func:`ensure_columns`)::

    archived_at     TEXT   -- NULL = live
    archived_by     TEXT
    archive_reason  TEXT
"""

from __future__ import annotations

import sqlite3

ARCHIVE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("archived_at", "TEXT"),
    ("archived_by", "TEXT"),
    ("archive_reason", "TEXT"),
)

#: SQL condition for live (not archived) rows.
LIVE = "archived_at IS NULL"


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def ensure_columns(conn: sqlite3.Connection, table: str) -> None:
    """Add the archive columns to *table* when they are missing."""
    have = {r[1] for r in conn.execute(
        "SELECT * FROM pragma_table_info(?)", (table,))}
    for col, ddl in ARCHIVE_COLUMNS:
        if col not in have:
            # db-audit: ignore[DBW001] - table is a module constant, quoted; col/ddl are constants above
            conn.execute(f"ALTER TABLE {_q(table)} ADD COLUMN {col} {ddl}")


def archive(conn: sqlite3.Connection, table: str, pk_col: str, pk: object,
            *, by: str | None, reason: str | None) -> bool:
    """Archive one live row; False when it is unknown or already archived."""
    # db-audit: ignore[DBW001] - table/pk_col are module constants, quoted
    cur = conn.execute(
        f"UPDATE {_q(table)} SET archived_at = datetime('now'), "
        f"archived_by = ?, archive_reason = ? "
        f"WHERE {_q(pk_col)} = ? AND archived_at IS NULL",
        (by or None, (reason or "").strip() or None, pk))
    return cur.rowcount > 0


def restore(conn: sqlite3.Connection, table: str, pk_col: str,
            pk: object) -> bool:
    """Bring an archived row back; False when it was not archived."""
    # db-audit: ignore[DBW001] - table/pk_col are module constants, quoted
    cur = conn.execute(
        f"UPDATE {_q(table)} SET archived_at = NULL, archived_by = NULL, "
        f"archive_reason = NULL WHERE {_q(pk_col)} = ? "
        f"AND archived_at IS NOT NULL", (pk,))
    return cur.rowcount > 0
