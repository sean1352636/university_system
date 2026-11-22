"""The one definition of the ``modules`` and ``student_modules`` tables.

The two are defined together because they are only meaningful together:
``student_modules.module_code`` points at ``modules.module_code``, which is
not the modules primary key, and getting that relationship wrong is how
the enrolment table ends up with rows nothing can join.

Between them they had 14 disagreeing definitions across 12 files on
``student_records.db``. What that cost:

* ``student_modules.status`` was declared ``DEFAULT 'Enrolled'`` in some
  definitions and ``DEFAULT 'enrolled'`` in others. 42 places in the tree
  filter on the exact string ``'Enrolled'``, so every row created under
  the lowercase default is invisible to all of them — including
  ``student_lifecycle``, which pauses a student's modules on interruption
  with ``WHERE status = 'Enrolled'``. Six live rows are affected, all
  belonging to the same student.
* ``modules.instructor_id`` is read by ``dashboard_routes`` and the parent
  portal's grade view, and was declared by no definition that ever ran, so
  both queries fail outright with ``no such column``.
* ``modules.module_id`` is the primary key, but every ad-hoc definition
  made ``module_code`` the key instead. The live table has both, with a
  unique index on ``module_code`` holding the relationship together.

Canonical status values live in :data:`ENROLMENT_STATUSES`; use
:func:`normalise_status` rather than comparing raw strings.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Iterable
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608 - identifier validation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# modules
# ---------------------------------------------------------------------------

MODULE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("module_id", "TEXT PRIMARY KEY"),
    ("module_name", "TEXT NOT NULL"),
    ("description", "TEXT"),
    ("credits", "INTEGER DEFAULT 0"),
    ("semester", "TEXT"),
    ("year", "TEXT"),
    ("instructor", "TEXT"),
    # Read by dashboard_routes and the parent portal's grade view, and
    # declared by nothing that ever ran. Nullable: the 388 live rows have
    # no instructor recorded either way.
    ("instructor_id", "INTEGER"),
    ("department", "TEXT"),
    ("prerequisites", "TEXT"),
    ("is_active", "BOOLEAN DEFAULT 1"),
    ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ("updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ("module_code", "TEXT"),
    ("module_type", "TEXT DEFAULT 'Standard'"),
    ("course", "TEXT"),
    ("academic_year", "TEXT"),
)

MODULE_COLUMN_NAMES: frozenset[str] = frozenset(n for n, _d in MODULE_COLUMNS)

MODULE_ALIASES: dict[str, str] = {
    "name": "module_name",
    "code": "module_code",
    "title": "module_name",
    "credit": "credits",
    "active": "is_active",
}

_MODULE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_modules_course ON modules(course)",
    "CREATE INDEX IF NOT EXISTS idx_modules_active ON modules(is_active)",
)

# module_code is not the primary key but every join in the tree treats it
# as one. The unique index is what makes that safe.
_MODULE_UNIQUE_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_modules_code_unique "
    "ON modules(module_code)",
)


# ---------------------------------------------------------------------------
# student_modules
# ---------------------------------------------------------------------------

# The canonical enrolment statuses, in the capitalisation the 42 filters in
# the tree expect. student_lifecycle writes 'Paused', 'Withdrawn',
# 'Completed' and 'Closed'; the enrolment screens write 'Enrolled'.
ENROLLED = "Enrolled"
PAUSED = "Paused"
WITHDRAWN = "Withdrawn"
COMPLETED = "Completed"
CLOSED = "Closed"
FAILED = "Failed"

ENROLMENT_STATUSES: tuple[str, ...] = (
    ENROLLED, PAUSED, WITHDRAWN, COMPLETED, CLOSED, FAILED,
)

_STATUS_BY_LOWER = {s.lower(): s for s in ENROLMENT_STATUSES}

STUDENT_MODULE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("student_id", "TEXT"),
    ("module_code", "TEXT"),
    ("enrollment_date", "TEXT DEFAULT (date('now'))"),
    ("status", "TEXT DEFAULT 'Enrolled'"),
    ("module_type", "TEXT DEFAULT 'Standard'"),
    ("module_name", "TEXT"),
    ("grade", "TEXT"),
    ("completion_date", "TEXT"),
    ("credits_earned", "INTEGER DEFAULT 0"),
    ("enrollment_id", "INTEGER"),
    ("module_id", "TEXT"),
    ("semester", "TEXT"),
    ("year", "TEXT"),
    ("created_at", "TIMESTAMP DEFAULT NULL"),
)

STUDENT_MODULE_COLUMN_NAMES: frozenset[str] = frozenset(
    n for n, _d in STUDENT_MODULE_COLUMNS)

STUDENT_MODULE_ALIASES: dict[str, str] = {
    "enrolment_date": "enrollment_date",
    "enrolment_id": "enrollment_id",
    "date_enrolled": "enrollment_date",
    "code": "module_code",
    "grade_awarded": "grade",
}

_STUDENT_MODULE_CONSTRAINTS = (
    "FOREIGN KEY (student_id) REFERENCES students (student_id)",
    "FOREIGN KEY (module_code) REFERENCES modules (module_code)",
    "UNIQUE(student_id, module_code)",
)

_STUDENT_MODULE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_student_modules_student_id "
    "ON student_modules(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_student_modules_module_code "
    "ON student_modules(module_code)",
    "CREATE INDEX IF NOT EXISTS idx_student_modules_status "
    "ON student_modules(status)",
    # (student_id, module_code) is UNIQUE, so its autoindex already serves it.
)


class UnknownModuleColumnError(KeyError):
    """A caller used a column name these tables do not have."""


def _resolve(name: str, canonical: frozenset[str],
             aliases: dict[str, str], table: str) -> str:
    key = name.strip().strip('"`[]').lower()
    if key in canonical:
        return key
    if key in aliases:
        return aliases[key]
    raise UnknownModuleColumnError(
        f"{table} has no column {name!r}; known aliases: "
        f"{', '.join(sorted(aliases))}")


def resolve_module_column(name: str) -> str:
    return _resolve(name, MODULE_COLUMN_NAMES, MODULE_ALIASES, "modules")


def resolve_student_module_column(name: str) -> str:
    return _resolve(name, STUDENT_MODULE_COLUMN_NAMES,
                    STUDENT_MODULE_ALIASES, "student_modules")


def resolve_module_columns(names: Iterable[str]) -> list[str]:
    return [resolve_module_column(n) for n in names]


def normalise_status(status: str | None) -> str | None:
    """Map any capitalisation of an enrolment status onto the canonical one.

    ``'enrolled'`` and ``'ENROLLED'`` both become ``'Enrolled'``. An
    unrecognised value is returned unchanged rather than rejected — the
    column is free text on the live table and this is a normaliser, not a
    validator.
    """
    if status is None:
        return None
    return _STATUS_BY_LOWER.get(status.strip().lower(), status)


def create_modules_sql() -> str:
    body = ",\n    ".join(f'"{n}" {d}' for n, d in MODULE_COLUMNS)
    return f"CREATE TABLE IF NOT EXISTS modules (\n    {body}\n)"


def create_student_modules_sql() -> str:
    body = ",\n    ".join(f'"{n}" {d}' for n, d in STUDENT_MODULE_COLUMNS)
    constraints = ",\n    ".join(_STUDENT_MODULE_CONSTRAINTS)
    return ("CREATE TABLE IF NOT EXISTS student_modules (\n    "
            f"{body},\n    {constraints}\n)")


def _addable(decl: str) -> str:
    """Strip what SQLite refuses on ``ALTER TABLE ADD COLUMN``."""
    cleaned = re.sub(r"\bUNIQUE\b", "", decl, flags=re.IGNORECASE)
    if "NOT NULL" in cleaned.upper() and "DEFAULT" not in cleaned.upper():
        cleaned = re.sub(r"\bNOT\s+NULL\b", "", cleaned, flags=re.IGNORECASE)
    # A non-constant default (date('now')) cannot be added either.
    if re.search(r"DEFAULT\s*\(", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(r"DEFAULT\s*\([^)]*\)", "", cleaned,
                         flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip() or "TEXT"


def _ensure(conn: sqlite3.Connection, table: str, create_sql: str,
            columns: tuple[tuple[str, str], ...], indexes: tuple[str, ...],
            unique_indexes: tuple[str, ...] = ()) -> None:
    # Identifiers cannot be parameterised, so they are validated instead.
    table = validate_identifier(table)
    try:
        conn.execute(create_sql)
        existing = {row[1] for row in conn.execute(
            f'PRAGMA table_info("{table}")')}
        for name, decl in columns:
            if name in existing:
                continue
            if "PRIMARY KEY" in decl.upper():
                logger.error("%s exists without its key column %s; refusing "
                             "to patch it", table, name)
                continue
            try:
                conn.execute(
                    f'ALTER TABLE "{table}" ADD COLUMN "{name}" {_addable(decl)}')
                logger.info("Added %s.%s", table, name)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Could not add %s.%s: %s", table, name, exc)
        for statement in indexes:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                logger.debug("%s index skipped: %s", table, statement)
        for statement in unique_indexes:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as exc:
                logger.warning("%s uniqueness not enforced: %s", table, exc)
    except sqlite3.Error:
        logger.exception("%s bootstrap failed", table)


def ensure_modules_table(conn: sqlite3.Connection) -> None:
    """Create ``modules`` if absent and backfill any missing column."""
    _ensure(conn, "modules", create_modules_sql(), MODULE_COLUMNS,
            _MODULE_INDEXES, _MODULE_UNIQUE_INDEXES)


def ensure_student_modules_table(conn: sqlite3.Connection) -> None:
    """Create ``student_modules`` if absent and backfill any missing column."""
    _ensure(conn, "student_modules", create_student_modules_sql(),
            STUDENT_MODULE_COLUMNS, _STUDENT_MODULE_INDEXES)


def ensure_module_tables(conn: sqlite3.Connection) -> None:
    """Both, parent first — student_modules references modules."""
    ensure_modules_table(conn)
    ensure_student_modules_table(conn)


def ensure_module_tables_at(db_path: str | None = None) -> None:
    if db_path is None:
        from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
        db_path = str(UNIVERSITY_DEFAULT_DB_PATH)
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_module_tables(conn)
        conn.commit()
    finally:
        conn.close()


def missing_columns(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Canonical columns absent from this database, per table."""
    out: dict[str, list[str]] = {}
    for table, names in (("modules", MODULE_COLUMN_NAMES),
                         ("student_modules", STUDENT_MODULE_COLUMN_NAMES)):
        try:
            existing = {row[1] for row in conn.execute(
                f'PRAGMA table_info("{table}")')}
        except sqlite3.Error:
            existing = set()
        out[table] = sorted(names - existing) if existing else sorted(names)
    return out


def mixed_case_statuses(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Enrolment rows whose status is not in canonical capitalisation.

    Should be empty. Anything here is invisible to the 42 filters that
    compare against the exact string.
    """
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM student_modules "
            "WHERE status IS NOT NULL GROUP BY status").fetchall()
    except sqlite3.Error:
        return []
    return [(str(s), int(n)) for s, n in rows
            if s and s not in ENROLMENT_STATUSES
            and s.lower() in _STATUS_BY_LOWER]


def normalise_stored_statuses(conn: sqlite3.Connection) -> int:
    """Rewrite mis-cased enrolment statuses in place. Returns rows changed."""
    changed = 0
    for stored, _count in mixed_case_statuses(conn):
        canonical = _STATUS_BY_LOWER[stored.lower()]
        cursor = conn.execute(
            "UPDATE student_modules SET status = ? WHERE status = ?",
            (canonical, stored))
        changed += cursor.rowcount or 0
        logger.info("Normalised student_modules.status %r -> %r (%d rows)",
                    stored, canonical, cursor.rowcount or 0)
    return changed


__all__ = [
    "MODULE_COLUMNS", "MODULE_COLUMN_NAMES", "MODULE_ALIASES",
    "STUDENT_MODULE_COLUMNS", "STUDENT_MODULE_COLUMN_NAMES",
    "STUDENT_MODULE_ALIASES", "ENROLMENT_STATUSES", "ENROLLED", "PAUSED",
    "WITHDRAWN", "COMPLETED", "CLOSED", "FAILED",
    "UnknownModuleColumnError", "resolve_module_column",
    "resolve_student_module_column", "resolve_module_columns",
    "normalise_status", "create_modules_sql", "create_student_modules_sql",
    "ensure_modules_table", "ensure_student_modules_table",
    "ensure_module_tables", "ensure_module_tables_at", "missing_columns",
    "mixed_case_statuses", "normalise_stored_statuses",
]
