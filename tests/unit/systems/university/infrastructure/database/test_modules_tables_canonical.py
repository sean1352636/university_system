"""``modules`` and ``student_modules`` have one definition each.

Two of the fourteen disagreeing definitions had teeth, and both are pinned
here: the ``'Enrolled'`` / ``'enrolled'`` default split that hid six live
enrolments from all 42 filters that read them, and the missing
``modules.instructor_id`` that two live endpoints query.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.infrastructure.database.schemas.modules_table import (
    ENROLLED,
    ENROLMENT_STATUSES,
    MODULE_ALIASES,
    MODULE_COLUMN_NAMES,
    MODULE_COLUMNS,
    STUDENT_MODULE_ALIASES,
    STUDENT_MODULE_COLUMN_NAMES,
    STUDENT_MODULE_COLUMNS,
    UnknownModuleColumnError,
    create_modules_sql,
    create_student_modules_sql,
    ensure_module_tables,
    missing_columns,
    mixed_case_statuses,
    normalise_status,
    normalise_stored_statuses,
    resolve_module_column,
    resolve_student_module_column,
)

REPO_ROOT = Path(__file__).resolve().parents[6]
UNIVERSITY_ROOT = (REPO_ROOT / "src" / "education_system" / "systems"
                   / "university")
MIGRATION = (REPO_ROOT / "src" / "education_system" / "migrations" / "versions"
             / "c3e58a7b91f4_canonical_module_tables.py")


@pytest.fixture()
def db(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "modules.db")
    yield conn
    conn.close()


# ------------------------------------------------------------- definition

def test_module_id_is_the_key_not_module_code():
    """Every ad-hoc definition made module_code the primary key; the live
    table uses module_id, with a unique index holding module_code."""
    first_name, first_decl = MODULE_COLUMNS[0]
    assert first_name == "module_id"
    assert "PRIMARY KEY" in first_decl.upper()
    assert "module_code" in MODULE_COLUMN_NAMES


def test_instructor_id_is_declared():
    """Read by dashboard_routes and the parent portal's grade view; declared
    by no definition that ever ran, so both failed with no such column."""
    assert "instructor_id" in MODULE_COLUMN_NAMES


def test_enrolment_status_default_is_canonical():
    status_decl = dict(STUDENT_MODULE_COLUMNS)["status"]
    assert "'Enrolled'" in status_decl, (
        "the lowercase default is what hid six live enrolments"
    )


def test_no_alias_shadows_a_real_column():
    assert not set(MODULE_ALIASES) & MODULE_COLUMN_NAMES
    assert not set(STUDENT_MODULE_ALIASES) & STUDENT_MODULE_COLUMN_NAMES


def test_alias_targets_exist():
    assert set(MODULE_ALIASES.values()) <= MODULE_COLUMN_NAMES
    assert set(STUDENT_MODULE_ALIASES.values()) <= STUDENT_MODULE_COLUMN_NAMES


# -------------------------------------------------------------- bootstrap

def test_bootstrap_creates_both_tables(db):
    ensure_module_tables(db)
    assert missing_columns(db) == {"modules": [], "student_modules": []}


def test_bootstrap_is_idempotent(db):
    ensure_module_tables(db)
    before = sorted(r[0] for r in db.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    ensure_module_tables(db)
    after = sorted(r[0] for r in db.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    assert before == after


def test_bootstrap_widens_a_narrow_populated_table(db):
    db.execute("CREATE TABLE modules (module_id TEXT PRIMARY KEY, "
               "module_name TEXT NOT NULL)")
    db.execute("INSERT INTO modules VALUES ('M1', 'Algorithms')")
    ensure_module_tables(db)
    assert missing_columns(db)["modules"] == []
    assert db.execute("SELECT module_name FROM modules").fetchone() == \
        ("Algorithms",)


def test_module_code_uniqueness_is_enforced(db):
    ensure_module_tables(db)
    db.execute("INSERT INTO modules (module_id, module_name, module_code) "
               "VALUES ('M1', 'Algorithms', 'CS101')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO modules (module_id, module_name, module_code) "
                   "VALUES ('M2', 'Algorithms II', 'CS101')")


def test_create_sql_matches_the_column_lists(db):
    db.executescript(create_modules_sql())
    db.executescript(create_student_modules_sql())
    assert {r[1] for r in db.execute("PRAGMA table_info(modules)")} == \
        MODULE_COLUMN_NAMES
    assert {r[1] for r in db.execute("PRAGMA table_info(student_modules)")} == \
        STUDENT_MODULE_COLUMN_NAMES


def test_default_status_is_applied_on_insert(db):
    ensure_module_tables(db)
    db.execute("INSERT INTO student_modules (student_id, module_code) "
               "VALUES ('S1', 'CS101')")
    assert db.execute("SELECT status FROM student_modules").fetchone() == \
        (ENROLLED,)


# ----------------------------------------------------------- status repair

@pytest.mark.parametrize(("given", "expected"), [
    ("enrolled", "Enrolled"),
    ("ENROLLED", "Enrolled"),
    ("  Enrolled  ", "Enrolled"),
    ("paused", "Paused"),
    ("Enrolled", "Enrolled"),
])
def test_normalise_status(given, expected):
    assert normalise_status(given) == expected


def test_normalise_status_passes_through_the_unknown():
    """A normaliser, not a validator — the column is free text."""
    assert normalise_status("Deferred Externally") == "Deferred Externally"
    assert normalise_status(None) is None


def test_mixed_case_statuses_are_detected_and_repaired(db):
    ensure_module_tables(db)
    db.execute("INSERT INTO student_modules (student_id, module_code, status) "
               "VALUES ('S1', 'CS101', 'enrolled')")
    db.execute("INSERT INTO student_modules (student_id, module_code, status) "
               "VALUES ('S2', 'CS102', 'Enrolled')")
    assert mixed_case_statuses(db) == [("enrolled", 1)]

    assert normalise_stored_statuses(db) == 1
    assert mixed_case_statuses(db) == []
    assert db.execute(
        "SELECT COUNT(*) FROM student_modules WHERE status = 'Enrolled'"
    ).fetchone()[0] == 2


def test_repair_leaves_unrecognised_statuses_alone(db):
    ensure_module_tables(db)
    db.execute("INSERT INTO student_modules (student_id, module_code, status) "
               "VALUES ('S1', 'CS101', 'Deferred Externally')")
    assert normalise_stored_statuses(db) == 0
    assert db.execute("SELECT status FROM student_modules").fetchone() == \
        ("Deferred Externally",)


def test_migration_normalises_status(db):
    """The migration is where the live repair happens, so its statement has
    to survive editing."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "UPDATE student_modules SET status" in source
    assert "LOWER(status) = LOWER(:canonical)" in source


def test_migration_revision_chain():
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            name = getattr(node.target, "id", None)
            if name in ("revision", "down_revision") and node.value:
                values[name] = ast.literal_eval(node.value)
    assert values["revision"] == "c3e58a7b91f4"
    assert values["down_revision"] == "a91c47e2f8d3"


# ----------------------------------------------------------------- aliases

@pytest.mark.parametrize(("given", "expected"), [
    ("code", "module_code"),
    ("name", "module_name"),
    ("MODULE_CODE", "module_code"),
])
def test_resolve_module_column(given, expected):
    assert resolve_module_column(given) == expected


@pytest.mark.parametrize(("given", "expected"), [
    ("enrolment_date", "enrollment_date"),
    ("enrolment_id", "enrollment_id"),
    ("status", "status"),
])
def test_resolve_student_module_column(given, expected):
    assert resolve_student_module_column(given) == expected


def test_resolve_rejects_a_typo():
    with pytest.raises(UnknownModuleColumnError):
        resolve_module_column("modul_code")


# ------------------------------------------------- no lowercase comparisons

_STATUS_LITERAL_RE = re.compile(
    r"status\s*=\s*'(enrolled|paused|withdrawn|completed|closed|failed)'")
_LOWER_GUARD_RE = re.compile(
    r"LOWER\s*\(\s*[a-z_.]*status\s*\)\s*(?:=|IN)", re.IGNORECASE)


def test_no_module_compares_status_against_lowercase():
    """A lowercase literal comparison matches nothing now the stored values
    are canonical — the same defect, from the other side.

    Scoped to SQL string literals that mention ``student_modules``: a
    file-wide regex would flag ``status = 'completed'`` on the half-dozen
    unrelated tables that also have a status column.
    """
    offenders: dict[str, list[str]] = {}
    for path in UNIVERSITY_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "student_modules" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            statement = node.value
            if "student_modules" not in statement:
                continue
            # LOWER(status) = 'enrolled' is fine; a bare comparison is not.
            guarded = _LOWER_GUARD_RE.sub("", statement)
            found = _STATUS_LITERAL_RE.findall(guarded)
            if found:
                offenders.setdefault(
                    path.relative_to(UNIVERSITY_ROOT).as_posix(),
                    []).extend(found)
    assert not offenders, (
        f"compare against the canonical capitalisation: {offenders}")


def test_every_canonical_status_is_distinct_when_lowercased():
    lowered = [s.lower() for s in ENROLMENT_STATUSES]
    assert len(set(lowered)) == len(lowered)
