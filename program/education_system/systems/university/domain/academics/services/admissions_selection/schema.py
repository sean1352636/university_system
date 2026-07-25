"""Idempotent schema + seed for the grades-gated student admissions flow.

Adds the small amount of structure the new student-create flow needs on
top of the existing ``courses`` / ``students`` / ``modules`` tables:

* ``courses.min_ucas_tariff``  – the entry requirement (UCAS tariff points)
* ``students.ucas_tariff``     – the tariff the applicant achieved
  (``students.entry_qualifications`` already exists for the raw grades)
* ``course_curriculum``        – the 18-module programme (6 per year) per course

Everything here is additive and safe to run repeatedly. Functions accept an
optional ``cursor`` so callers already inside a write transaction can run the
DDL on their own connection instead of opening a second one (SQLite only
allows a single writer at a time).
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)

# Default entry requirements (UCAS tariff points) for the seeded programmes.
# 112 ~= BBC at A-level, 104 ~= BCC. Applied only when a course has no
# requirement set yet, so admins can override via course management.
DEFAULT_ENTRY_TARIFFS: dict[str, int] = {
    "CS": 112,
    "DS": 104,
}

# Cache of database paths whose schema has already been ensured this process,
# so the common (no-cursor) path does not re-run DDL on every call. Keyed by
# resolved path so tests that point at a fresh temp DB still get initialised.
_ensured_paths: set[str] = set()


def _add_column(cursor, table: str, column: str, decl: str) -> None:
    """ALTER TABLE ... ADD COLUMN, ignoring 'duplicate column' errors."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    except sqlite3.OperationalError:
        pass  # column already exists


def _ensure_on_cursor(cursor) -> None:
    """Apply all DDL + seed using an existing cursor (no commit here)."""
    # 18-module-per-course programme definition.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_curriculum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            module_name TEXT NOT NULL,
            UNIQUE(course_code, module_code)
        )
        """
    )

    # Entry requirement on courses + achieved tariff on students.
    _add_column(cursor, "courses", "min_ucas_tariff", "INTEGER DEFAULT 0")
    _add_column(cursor, "students", "ucas_tariff", "INTEGER")
    # entry_qualifications already exists in the live schema, but add defensively
    # in case this runs against an older database.
    _add_column(cursor, "students", "entry_qualifications", "TEXT")

    # Seed default entry tariffs for the built-in programmes where unset.
    for code, tariff in DEFAULT_ENTRY_TARIFFS.items():
        cursor.execute(
            """
            UPDATE courses SET min_ucas_tariff = ?
            WHERE course_code = ?
              AND (min_ucas_tariff IS NULL OR min_ucas_tariff = 0)
            """,
            (tariff, code),
        )


def ensure_selection_schema(cursor=None) -> None:
    """Ensure the admissions-selection schema + seed exist.

    Parameters
    ----------
    cursor:
        If provided, run the DDL on this cursor (the caller owns the
        transaction and commit). If ``None``, open a dedicated connection,
        commit, and close.
    """
    if cursor is not None:
        _ensure_on_cursor(cursor)
        return

    conn = get_connection()
    try:
        path = getattr(conn, "_db_path", None) or ""
        cur = conn.cursor()
        _ensure_on_cursor(cur)
        conn.commit()
        if path:
            _ensured_paths.add(path)
    except sqlite3.Error:
        logger.exception("Failed to ensure admissions-selection schema")
        raise
    finally:
        conn.close()
