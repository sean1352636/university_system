"""Unit tests for the staff/HR bus (``modules.services.staff_hr_bus``).

The bus reads/writes through the shared ``get_connection`` helper, resolving its
target from the module-level ``DEFAULT_DB_PATH`` — repointing that constant at a
per-test temp file isolates every test. Unlike the schema-owning buses, staff_hr_bus
creates *no* tables: it soft-fails open when ``teaching_qualifications`` /
``leave_requests`` are absent, and only writes to a pre-existing ``instructors``
table. Fixtures seed exactly the tables a given behaviour needs.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services import staff_hr_bus as hr


@pytest.fixture()
def hr_db(tmp_path, monkeypatch):
    """Point the shared DB layer at an empty temp file (no tables seeded)."""
    db_path = str(tmp_path / "hr.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Touch the file so it exists as a valid empty sqlite db.
    sqlite3.connect(db_path).close()
    return db_path


def _seed_quals(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE teaching_qualifications ("
        " user_id TEXT, verified INTEGER, course_code TEXT, subject_area TEXT);"
        "CREATE TABLE modules (module_code TEXT, department TEXT);"
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# is_qualified_for
# ---------------------------------------------------------------------------

class TestIsQualifiedFor:
    def test_none_args_pass_open(self, hr_db):
        assert hr.is_qualified_for(None, "CS101") is True
        assert hr.is_qualified_for(1, "") is True

    def test_missing_table_allows(self, hr_db):
        # No teaching_qualifications table at all → soft pass.
        assert hr.is_qualified_for(1, "CS101") is True

    def test_no_rows_for_instructor_allows(self, hr_db):
        conn = _seed_quals(hr_db)
        conn.close()
        assert hr.is_qualified_for(1, "CS101") is True

    def test_matching_course_code_verified(self, hr_db):
        conn = _seed_quals(hr_db)
        conn.execute(
            "INSERT INTO teaching_qualifications VALUES (?, ?, ?, ?)",
            ("1", 1, "CS101", None),
        )
        conn.commit()
        conn.close()
        assert hr.is_qualified_for(1, "CS101") is True

    def test_matching_course_code_unverified_soft_pass(self, hr_db):
        conn = _seed_quals(hr_db)
        conn.execute(
            "INSERT INTO teaching_qualifications VALUES (?, ?, ?, ?)",
            ("1", 0, "cs101", None),  # case-insensitive match, unverified
        )
        conn.commit()
        conn.close()
        assert hr.is_qualified_for(1, "CS101") is True

    def test_subject_area_matches_module_department(self, hr_db):
        conn = _seed_quals(hr_db)
        conn.execute(
            "INSERT INTO teaching_qualifications VALUES (?, ?, ?, ?)",
            ("1", 1, None, "Computer Science"),
        )
        conn.execute("INSERT INTO modules VALUES (?, ?)",
                     ("CS101", "Computer Science"))
        conn.commit()
        conn.close()
        assert hr.is_qualified_for(1, "CS101") is True

    def test_no_match_returns_false(self, hr_db):
        conn = _seed_quals(hr_db)
        conn.execute(
            "INSERT INTO teaching_qualifications VALUES (?, ?, ?, ?)",
            ("1", 1, "MA200", "Mathematics"),
        )
        conn.execute("INSERT INTO modules VALUES (?, ?)",
                     ("CS101", "Computer Science"))
        conn.commit()
        conn.close()
        assert hr.is_qualified_for(1, "CS101") is False


# ---------------------------------------------------------------------------
# is_available_on
# ---------------------------------------------------------------------------

def _seed_leave(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE leave_requests ("
        " user_id TEXT, leave_type_id INTEGER, start_date TEXT, "
        " end_date TEXT, status TEXT)"
    )
    conn.commit()
    return conn


class TestIsAvailableOn:
    def test_none_args_available(self, hr_db):
        assert hr.is_available_on(None, "2026-01-01") is True
        assert hr.is_available_on(1, "") is True

    def test_missing_table_available(self, hr_db):
        assert hr.is_available_on(1, "2026-01-01") is True

    def test_on_approved_leave_unavailable(self, hr_db):
        conn = _seed_leave(hr_db)
        conn.execute(
            "INSERT INTO leave_requests VALUES (?, ?, ?, ?, ?)",
            ("1", 1, "2026-01-01", "2026-01-10", "Approved"),
        )
        conn.commit()
        conn.close()
        assert hr.is_available_on(1, "2026-01-05") is False

    def test_outside_leave_window_available(self, hr_db):
        conn = _seed_leave(hr_db)
        conn.execute(
            "INSERT INTO leave_requests VALUES (?, ?, ?, ?, ?)",
            ("1", 1, "2026-01-01", "2026-01-10", "approved"),
        )
        conn.commit()
        conn.close()
        assert hr.is_available_on(1, "2026-02-01") is True

    def test_unapproved_leave_ignored(self, hr_db):
        conn = _seed_leave(hr_db)
        conn.execute(
            "INSERT INTO leave_requests VALUES (?, ?, ?, ?, ?)",
            ("1", 1, "2026-01-01", "2026-01-10", "pending"),
        )
        conn.commit()
        conn.close()
        assert hr.is_available_on(1, "2026-01-05") is True


# ---------------------------------------------------------------------------
# list_unavailable_ranges
# ---------------------------------------------------------------------------

class TestListUnavailableRanges:
    def test_missing_table_empty(self, hr_db):
        assert hr.list_unavailable_ranges() == []

    def test_lists_approved_future_windows(self, hr_db):
        conn = _seed_leave(hr_db)
        conn.executemany(
            "INSERT INTO leave_requests VALUES (?, ?, ?, ?, ?)",
            [
                ("1", 1, "2099-01-01", "2099-01-10", "Approved"),
                ("2", 1, "2099-02-01", "2099-02-05", "approved"),
                # past window (ends before floor) → excluded
                ("1", 1, "2000-01-01", "2000-01-05", "approved"),
                # unapproved → excluded
                ("1", 1, "2099-03-01", "2099-03-05", "pending"),
            ],
        )
        conn.commit()
        conn.close()
        rows = hr.list_unavailable_ranges(since="2026-01-01")
        assert len(rows) == 2
        assert {r["user_id"] for r in rows} == {"1", "2"}

    def test_filter_by_instructor(self, hr_db):
        conn = _seed_leave(hr_db)
        conn.executemany(
            "INSERT INTO leave_requests VALUES (?, ?, ?, ?, ?)",
            [
                ("1", 1, "2099-01-01", "2099-01-10", "approved"),
                ("2", 1, "2099-02-01", "2099-02-05", "approved"),
            ],
        )
        conn.commit()
        conn.close()
        rows = hr.list_unavailable_ranges(1, since="2026-01-01")
        assert len(rows) == 1
        assert rows[0]["user_id"] == "1"


# ---------------------------------------------------------------------------
# publish_availability_change (best-effort, never raises)
# ---------------------------------------------------------------------------

class TestPublishAvailabilityChange:
    def test_never_raises(self, hr_db):
        # No subscribers wired in the test env; must swallow everything.
        assert hr.publish_availability_change("1", action="sick") is None


# ---------------------------------------------------------------------------
# update_instructor
# ---------------------------------------------------------------------------

def _seed_instructors(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE instructors ("
        " id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, "
        " email TEXT, department TEXT, status TEXT, is_active INTEGER, "
        " updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO instructors (id, first_name, department, is_active) "
        "VALUES (1, 'Ada', 'CS', 1)"
    )
    conn.commit()
    conn.close()


class TestUpdateInstructor:
    def test_none_id_returns_false(self, hr_db):
        assert hr.update_instructor(None, first_name="X") is False

    def test_no_writable_fields_returns_false(self, hr_db):
        _seed_instructors(hr_db)
        # Only unknown keys → nothing to persist.
        assert hr.update_instructor(1, nickname="Boss", secret="x") is False

    def test_persists_writable_fields(self, hr_db):
        _seed_instructors(hr_db)
        ok = hr.update_instructor(1, first_name="Grace", department="Maths",
                                  ignored_field="drop me")
        assert ok is True
        conn = sqlite3.connect(hr_db)
        row = conn.execute(
            "SELECT first_name, department, updated_at FROM instructors WHERE id = 1"
        ).fetchone()
        conn.close()
        assert row[0] == "Grace"
        assert row[1] == "Maths"
        assert row[2] is not None  # updated_at stamped

    def test_missing_table_returns_false(self, hr_db):
        # No instructors table → UPDATE errors → soft False.
        assert hr.update_instructor(1, first_name="Grace") is False
