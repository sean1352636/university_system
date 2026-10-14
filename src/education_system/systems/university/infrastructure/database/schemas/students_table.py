"""The one definition of the university ``students`` table.

Before this module existed, ``students`` was created by 48 separate
``CREATE TABLE IF NOT EXISTS`` statements across 31 files, none of which
agreed. The widest declared 15 columns, the narrowest 7, and the shape a
fresh database ended up with depended on which module happened to import
first. The 35-column table on an established installation is not any of
those definitions — it is the residue of a dozen scattered
``ALTER TABLE students ADD COLUMN`` calls patching whichever narrow table
won the race.

That is why ``SELECT nationality FROM students`` fails on a live database
(the column is declared in most of the old definitions and exists in none
of them), and why the duplicate-import path could not insert a student at
all: it wrote ``date_of_birth``, ``email`` and ``phone_number``, none of
which are real column names here.

So: one canonical column list, one bootstrap function, and a set of
recognised aliases so callers written against the old names get a clear
error instead of a mysterious one. The migration
``e4a17c9d3b52_canonical_students_table`` owns the same shape for a fresh
database; this module keeps the idempotent bootstrap for the many entry
points that reach the table before Alembic has ever run.

Adding a column: add it to :data:`STUDENT_COLUMNS` *and* to a new Alembic
migration. :func:`ensure_students_table` will backfill it on existing
databases; the migration makes it exist on new ones.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Iterable

logger = logging.getLogger(__name__)


# The canonical shape, in the order the live table carries it. The
# declarations match the established database exactly so that running the
# bootstrap against an existing installation is a no-op.
STUDENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("student_id", "TEXT PRIMARY KEY"),
    ("email_address", "TEXT"),
    ("title", "TEXT"),
    ("first_name", "TEXT"),
    ("middle_name", "TEXT"),
    ("last_name", "TEXT"),
    ("gender", "TEXT"),
    ("dob", "TEXT"),
    ("age", "INTEGER"),
    ("course", "TEXT"),
    ("registration_datetime", "TEXT"),
    ("status", "TEXT DEFAULT 'Active'"),
    ("enrollment_date", "TEXT"),
    ("emergency_contact", "TEXT DEFAULT ''"),
    ("pronouns", "TEXT DEFAULT ''"),
    ("previous_system", "TEXT"),
    ("previous_system_id", "TEXT"),
    ("year", "INTEGER"),
    ("program", "TEXT"),
    ("phone", "TEXT"),
    ("address", "TEXT"),
    ("is_active", "BOOLEAN DEFAULT 1"),
    ("grade_level", "TEXT"),
    ("created_date", "TIMESTAMP DEFAULT NULL"),
    ("year_of_study", "INTEGER"),
    ("gpa", "REAL"),
    ("journey_id", "TEXT"),
    ("entry_qualifications", "TEXT"),
    ("conditions_met", "INTEGER"),
    ("ucas_tariff", "INTEGER"),
    ("academic_year", "TEXT"),
    ("mode_of_study", "TEXT DEFAULT 'full-time'"),
    ("campus_code", "TEXT"),
    ("expected_return_date", "TEXT"),
    ("record_closed_at", "TEXT"),
)

STUDENT_COLUMN_NAMES: frozenset[str] = frozenset(
    name for name, _decl in STUDENT_COLUMNS)

# Names that older code writes but this table has never had. Mapped, not
# adopted: adding ``email`` alongside ``email_address`` would give the
# record two mailboxes and no rule about which one is right.
COLUMN_ALIASES: dict[str, str] = {
    "email": "email_address",
    "e_mail": "email_address",
    "phone_number": "phone",
    "telephone": "phone",
    "date_of_birth": "dob",
    "birth_date": "dob",
    "programme": "program",
    "active": "is_active",
    "created_at": "created_date",
}

# Declared in most of the superseded definitions, present in none of them,
# read by nothing — nationality lives on the visa and equality records.
# Listed so the audit tool's output can be explained rather than chased.
KNOWN_GHOST_COLUMNS: frozenset[str] = frozenset({
    "nationality", "user_id", "updated_at",
})

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_students_name "
    "ON students(first_name, last_name)",
    "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
    "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
    "CREATE INDEX IF NOT EXISTS idx_students_email ON students(email_address)",
    "CREATE INDEX IF NOT EXISTS idx_students_status ON students(status)",
    "CREATE INDEX IF NOT EXISTS idx_students_enrollment_date "
    "ON students(enrollment_date)",
    "CREATE INDEX IF NOT EXISTS idx_students_journey_id "
    "ON students(journey_id)",
)


def create_students_sql() -> str:
    """The canonical ``CREATE TABLE`` statement."""
    body = ",\n    ".join(f'"{name}" {decl}' for name, decl in STUDENT_COLUMNS)
    return f"CREATE TABLE IF NOT EXISTS students (\n    {body}\n)"


class UnknownStudentColumnError(KeyError):
    """A caller used a column name the ``students`` table does not have."""


def resolve_column(name: str) -> str:
    """Map a caller's column name onto the canonical one.

    Raises :class:`UnknownStudentColumnError` for a name that is neither
    canonical nor a known alias, so a typo fails where it is written
    rather than as ``no such column`` three layers down.
    """
    key = name.strip().strip('"`[]').lower()
    if key in STUDENT_COLUMN_NAMES:
        return key
    if key in COLUMN_ALIASES:
        return COLUMN_ALIASES[key]
    raise UnknownStudentColumnError(
        f"students has no column {name!r}; known aliases: "
        f"{', '.join(sorted(COLUMN_ALIASES))}")


def resolve_columns(names: Iterable[str]) -> list[str]:
    return [resolve_column(n) for n in names]


def ensure_students_table(conn: sqlite3.Connection) -> None:
    """Create ``students`` if absent and backfill any missing column.

    Idempotent and safe to call on every entry point. Takes an open
    connection rather than a path so it joins the caller's transaction
    instead of opening a competing one against a WAL database.
    """
    try:
        conn.execute(create_students_sql())
        existing = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
        for name, decl in STUDENT_COLUMNS:
            if name in existing:
                continue
            # SQLite cannot add a PRIMARY KEY column after the fact; if
            # student_id is missing the table is not ours to repair.
            if "PRIMARY KEY" in decl.upper():
                logger.error("students table exists without student_id; "
                             "refusing to patch it")
                continue
            try:
                conn.execute(f'ALTER TABLE students ADD COLUMN "{name}" {decl}')
                logger.info("Added students.%s", name)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Could not add students.%s: %s", name, exc)
        for statement in _INDEXES:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                logger.debug("students index skipped: %s", statement)
    except sqlite3.Error:
        logger.exception("students table bootstrap failed")


def ensure_students_table_at(db_path: str | None = None) -> None:
    """Path-taking wrapper for callers that have no connection to hand."""
    if db_path is None:
        from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
        db_path = str(UNIVERSITY_DEFAULT_DB_PATH)
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_students_table(conn)
        conn.commit()
    finally:
        conn.close()


def missing_columns(conn: sqlite3.Connection) -> list[str]:
    """Canonical columns absent from this database. Empty means healthy."""
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
    except sqlite3.Error:
        return sorted(STUDENT_COLUMN_NAMES)
    if not existing:
        return sorted(STUDENT_COLUMN_NAMES)
    return sorted(STUDENT_COLUMN_NAMES - existing)


__all__ = [
    "STUDENT_COLUMNS",
    "STUDENT_COLUMN_NAMES",
    "COLUMN_ALIASES",
    "KNOWN_GHOST_COLUMNS",
    "UnknownStudentColumnError",
    "create_students_sql",
    "resolve_column",
    "resolve_columns",
    "ensure_students_table",
    "ensure_students_table_at",
    "missing_columns",
]
