"""The ``students`` table has one definition, and it does not drift.

Before this, ``students`` was created by 48 disagreeing ``CREATE TABLE``
statements across 31 files and widened afterwards by scattered
``ALTER TABLE ... ADD COLUMN`` calls. These tests pin the three things that
made that expensive to live with:

* the canonical column list and the Alembic migration agree
* the bootstrap is idempotent and repairs a narrow table
* no module writes a column name the table does not have
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.infrastructure.database.schemas.students_table import (
    COLUMN_ALIASES,
    STUDENT_COLUMN_NAMES,
    STUDENT_COLUMNS,
    UnknownStudentColumnError,
    create_students_sql,
    ensure_students_table,
    missing_columns,
    resolve_column,
)

REPO_ROOT = Path(__file__).resolve().parents[6]
UNIVERSITY_ROOT = (REPO_ROOT / "src" / "education_system" / "systems"
                   / "university")
MIGRATION = (REPO_ROOT / "src" / "education_system" / "migrations" / "versions"
             / "e4a17c9d3b52_canonical_students_table.py")


@pytest.fixture()
def db(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "students.db")
    yield conn
    conn.close()


def _migration_constant(path: Path, name: str):
    """Read a module-level constant out of a migration without importing it.

    The migrations annotate their constants (``X: tuple[...] = (...)``), so
    this has to handle ``AnnAssign`` as well as ``Assign`` — matching only
    the latter silently returns None and the comparison passes vacuously.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if getattr(node.target, "id", None) == name and node.value:
                return ast.literal_eval(node.value)
        elif isinstance(node, ast.Assign):
            if any(getattr(t, "id", "") == name for t in node.targets):
                return ast.literal_eval(node.value)
    return None


# --------------------------------------------------------------- definition

def test_migration_and_module_agree():
    """The migration snapshots the shape; the module bootstraps it. If they
    diverge, a fresh database and an upgraded one stop matching — which is
    the whole class of bug this replaced."""
    migration_columns = _migration_constant(MIGRATION, "STUDENT_COLUMNS")
    assert migration_columns is not None, "migration lost STUDENT_COLUMNS"
    assert tuple(migration_columns) == tuple(STUDENT_COLUMNS)


def test_student_id_is_the_primary_key():
    first_name, first_decl = STUDENT_COLUMNS[0]
    assert first_name == "student_id"
    assert "PRIMARY KEY" in first_decl.upper()
    others = [n for n, d in STUDENT_COLUMNS[1:] if "PRIMARY KEY" in d.upper()]
    assert not others, f"second primary key declared on {others}"


def test_no_alias_is_also_a_real_column():
    """An alias that is also a column would mean two homes for one fact —
    exactly the ``dob``/``date_of_birth`` split that started this."""
    overlap = set(COLUMN_ALIASES) & STUDENT_COLUMN_NAMES
    assert not overlap, f"aliases shadow real columns: {sorted(overlap)}"


def test_alias_targets_exist():
    unknown = {a: t for a, t in COLUMN_ALIASES.items()
               if t not in STUDENT_COLUMN_NAMES}
    assert not unknown, f"aliases point at nonexistent columns: {unknown}"


# ---------------------------------------------------------------- bootstrap

def test_bootstrap_creates_every_column(db):
    ensure_students_table(db)
    assert missing_columns(db) == []


def test_bootstrap_is_idempotent(db):
    ensure_students_table(db)
    before = db.execute("SELECT sql FROM sqlite_master "
                        "WHERE name='students'").fetchone()[0]
    ensure_students_table(db)
    after = db.execute("SELECT sql FROM sqlite_master "
                       "WHERE name='students'").fetchone()[0]
    assert before == after


def test_bootstrap_widens_a_narrow_table(db):
    """The 7-column definition that used to win the race on some databases."""
    db.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY, "
               "first_name TEXT, last_name TEXT)")
    db.execute("INSERT INTO students VALUES ('S1', 'Ada', 'Lovelace')")
    ensure_students_table(db)
    assert missing_columns(db) == []
    row = db.execute("SELECT first_name, last_name FROM students "
                     "WHERE student_id='S1'").fetchone()
    assert row == ("Ada", "Lovelace"), "widening lost the existing rows"


def test_bootstrap_survives_a_table_without_the_key(db):
    """A table missing student_id cannot be repaired by ALTER; the bootstrap
    should log and move on rather than raise into a GUI callback."""
    db.execute("CREATE TABLE students (first_name TEXT)")
    ensure_students_table(db)  # must not raise
    assert "student_id" in missing_columns(db)


def test_create_sql_matches_the_column_list(db):
    db.executescript(create_students_sql())
    columns = {row[1] for row in db.execute("PRAGMA table_info(students)")}
    assert columns == STUDENT_COLUMN_NAMES


# ----------------------------------------------------------------- aliases

@pytest.mark.parametrize(("given", "expected"), [
    ("email", "email_address"),
    ("phone_number", "phone"),
    ("date_of_birth", "dob"),
    ("created_at", "created_date"),
    ("EMAIL", "email_address"),
    ("dob", "dob"),
])
def test_resolve_column(given, expected):
    assert resolve_column(given) == expected


def test_resolve_column_rejects_a_typo():
    with pytest.raises(UnknownStudentColumnError):
        resolve_column("emial_adress")


# --------------------------------------------------------- no ghost writes

def _student_write_columns(text: str) -> set[str]:
    """Column names used in INSERT INTO students / UPDATE students."""
    names: set[str] = set()
    for match in re.finditer(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+students\s*\(([^)]*)\)",
                             text, re.IGNORECASE | re.DOTALL):
        names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", match.group(1)))
    for match in re.finditer(r"UPDATE\s+students\s+SET\s+(.{0,400}?)\s+WHERE",
                             text, re.IGNORECASE | re.DOTALL):
        body = match.group(1)
        names |= {m.group(1) for m in
                  re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", body)}
    return names


# The grade-tracking package used to be exempt here on the grounds that it
# owned a separate student_grading_system.db. It does not: its
# ``analytics_manager/constants.py`` reassigns ``sqlite3.connect`` on the
# shared module object so that filename resolves to the university default
# database, and the file exists nowhere on disk. Its definitions land on
# this table like everyone else's, so it is no longer exempt.
_EXEMPT = (
    # Exists to keep dob and the legacy date_of_birth column in step.
    "domain/health/records/db/schema.py",
)

_SQL_NOISE = {
    "excluded", "values", "set", "where", "select", "null", "coalesce",
    "case", "when", "then", "end", "students",
}


def test_no_module_writes_a_column_students_does_not_have():
    offenders: dict[str, set[str]] = {}
    for path in UNIVERSITY_ROOT.rglob("*.py"):
        rel = path.relative_to(UNIVERSITY_ROOT).as_posix()
        if any(part in rel for part in _EXEMPT):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "students" not in text:
            continue
        used = {c.lower() for c in _student_write_columns(text)}
        unknown = {c for c in used - STUDENT_COLUMN_NAMES - _SQL_NOISE
                   if c in COLUMN_ALIASES}
        if unknown:
            offenders[rel] = unknown
    assert not offenders, (
        "these modules write student columns that do not exist "
        f"(use the canonical name or resolve_column): {offenders}"
    )
