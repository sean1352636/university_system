"""Regression tests for the default student's module enrolments on first run.

``init_db()`` seeds the demo student ``S12345`` and enrols it on six starting
modules.  Two defects stopped that happening on a fresh database:

* the student INSERT was positional (``INSERT INTO students VALUES (...)``
  with 13 placeholders), so it raised ``table students has 35 columns but 13
  values were supplied`` the moment the table grew past its original shape —
  and the enrolments, which sat inside the same ``if`` block, died with it;
* the enrolments were only written when *this* code created the student, so
  when the auth bootstrap created the record first the student ended up with
  no modules at all.
"""

import hashlib
import sqlite3

import pytest

# ``database_manager`` writes an audit_trail row at import time, so every
# import in this module is deliberately done inside a test or fixture — by
# then the autouse ``_isolate_db`` fixture has redirected DEFAULT_DB_PATH.
# The guard below turns any leak into a failure instead of a silent write.


@pytest.fixture(autouse=True)
def _live_db_untouched():
    """Fail loudly if anything in this module reaches the real database."""
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

    live = UNIVERSITY_DEFAULT_DB_PATH
    before = hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None
    yield
    after = hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None
    assert before == after, f"test wrote to the live database at {live}"


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Run ``init_db()`` against a throwaway database and hand back its path."""
    from education_system.systems.university.shell.cli import database_manager as dm

    db_path = tmp_path / "student_records.db"
    monkeypatch.setattr(dm, "DB_PATH", str(db_path))
    # The user bootstrap writes through to the shared auth.db; keep it out of
    # a unit test.
    monkeypatch.setattr(dm.auth_manager, "ensure_default_users_exist_once",
                        lambda *a, **k: None)

    assert dm.init_db() is True, "init_db() reported failure on a fresh database"
    return db_path


def _enrolments(db_path, student_id):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ? "
            "ORDER BY module_code", (student_id,))]
    finally:
        conn.close()


def test_default_student_is_created(seeded_db):
    from education_system.systems.university.infrastructure import defaults

    conn = sqlite3.connect(f"file:{seeded_db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT course, status FROM students WHERE student_id = ?",
            (defaults.DEFAULT_STUDENT_ID,)).fetchone()
    finally:
        conn.close()

    assert row is not None, "default student record was not created"
    assert row[0] == "CS"


def test_default_student_gets_six_modules(seeded_db):
    from education_system.systems.university.infrastructure import defaults

    codes = _enrolments(seeded_db, defaults.DEFAULT_STUDENT_ID)
    assert len(codes) == 6, f"expected 6 module enrolments, got {len(codes)}: {codes}"


def test_enrolled_modules_exist_in_the_modules_table(seeded_db):
    """Every enrolment must point at a module row, not a dangling code."""
    from education_system.systems.university.infrastructure import defaults

    codes = _enrolments(seeded_db, defaults.DEFAULT_STUDENT_ID)
    conn = sqlite3.connect(f"file:{seeded_db}?mode=ro", uri=True)
    try:
        known = {r[0] for r in conn.execute("SELECT module_code FROM modules")}
    finally:
        conn.close()

    assert set(codes) <= known, f"enrolled on unknown modules: {set(codes) - known}"


def test_enrolment_survives_the_student_being_created_first(tmp_path, monkeypatch):
    """The auth bootstrap creating the student must not cost it its modules."""
    from education_system.systems.university.shell.cli import database_manager as dm
    from education_system.systems.university.infrastructure import defaults
    from education_system.systems.university.infrastructure.database.schemas.students_table import (
        ensure_students_table,
    )

    db_path = tmp_path / "student_records.db"
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_students_table(conn)
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "email_address, status, registration_datetime) "
            "VALUES (?, ?, ?, ?, 'Active', '2026-01-01 00:00:00')",
            (defaults.DEFAULT_STUDENT_ID, defaults.DEFAULT_STUDENT_FIRST_NAME,
             defaults.DEFAULT_STUDENT_LAST_NAME, defaults.DEFAULT_STUDENT_EMAIL))
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(dm, "DB_PATH", str(db_path))
    monkeypatch.setattr(dm.auth_manager, "ensure_default_users_exist_once",
                        lambda *a, **k: None)
    assert dm.init_db() is True

    codes = _enrolments(db_path, defaults.DEFAULT_STUDENT_ID)
    assert len(codes) == 6, f"expected 6 module enrolments, got {len(codes)}: {codes}"


def test_init_db_is_idempotent(seeded_db, monkeypatch):
    """A second run must not double-enrol the default student."""
    from education_system.systems.university.shell.cli import database_manager as dm
    from education_system.systems.university.infrastructure import defaults

    monkeypatch.setattr(dm, "DB_PATH", str(seeded_db))
    monkeypatch.setattr(dm.auth_manager, "ensure_default_users_exist_once",
                        lambda *a, **k: None)
    assert dm.init_db() is True

    codes = _enrolments(seeded_db, defaults.DEFAULT_STUDENT_ID)
    assert len(codes) == 6, f"re-running init_db() changed enrolments: {codes}"
