"""Tests for the unified instructor-creation service.

Each test gets an isolated SQLite file by monkeypatching
``db_module.DEFAULT_DB_PATH`` (the same convention used by the admissions and
campus service tests) and creating the minimal ``instructors`` / ``users`` /
``user_accounts`` schema the service writes to.

The optional ``create_login`` (shared auth.db) and ``send_welcome_email``
stores are turned off so the tests stay hermetic — they assert the core
promise of the service: creating an instructor populates the instructors table
*and* the local staff-directory tables in one call.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domains.curriculum.domain.course_management.instructor_service import (
    create_instructor,
)


def _create_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE instructors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT DEFAULT '',
            specialization TEXT DEFAULT '',
            max_courses_per_semester INTEGER DEFAULT 4,
            max_hours_per_week INTEGER DEFAULT 40,
            preferred_days TEXT,
            preferred_times TEXT,
            status TEXT DEFAULT 'Active',
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            role TEXT,
            student_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            service_account INTEGER DEFAULT 0
        );
        CREATE TABLE user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password_hash TEXT,
            salt TEXT,
            user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def instructor_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "instructor_service_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    _create_schema(db_path)
    yield db_path


def _fetchall(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


class TestCreateInstructor:
    # Turn off the external-side-effect stores for hermetic tests.
    _LOCAL_ONLY = dict(create_login=False, send_welcome_email=False)

    def test_populates_instructors_and_staff_tables(self, instructor_db):
        result = create_instructor(
            first_name="Ada",
            last_name="Lovelace",
            email="ada.lovelace@university.edu",
            department="Computer Science",
            specialization="Analytical Engines",
            **self._LOCAL_ONLY,
        )

        assert result.ok
        assert result.error is None
        assert result.instructor_id is not None
        assert result.user_id is not None
        assert result.staff_registered is True
        assert result.username == "ada.lovelace"

        instructors = _fetchall(instructor_db, "SELECT * FROM instructors")
        assert len(instructors) == 1
        assert instructors[0]["email"] == "ada.lovelace@university.edu"
        assert instructors[0]["department"] == "Computer Science"

        # The whole point of the unification: a local users row exists so the
        # instructor shows up in the staff table, with role 'instructor'.
        users = _fetchall(instructor_db, "SELECT * FROM users WHERE username = ?", ("ada.lovelace",))
        assert len(users) == 1
        assert users[0]["role"] == "instructor"
        assert users[0]["first_name"] == "Ada"

        accounts = _fetchall(instructor_db, "SELECT * FROM user_accounts WHERE username = ?", ("ada.lovelace",))
        assert len(accounts) == 1
        assert accounts[0]["user_id"] == users[0]["id"]

    def test_auto_generates_email_when_none(self, instructor_db):
        result = create_instructor(
            first_name="Grace", last_name="Hopper", **self._LOCAL_ONLY
        )
        assert result.ok
        assert result.email == "grace.hopper@university.edu"

    def test_auto_generated_email_dedups_with_counter(self, instructor_db):
        first = create_instructor(first_name="John", last_name="Smith", **self._LOCAL_ONLY)
        second = create_instructor(first_name="John", last_name="Smith", **self._LOCAL_ONLY)

        assert first.email == "john.smith@university.edu"
        # Second collides on the generated address -> counter appended.
        assert second.email == "john.smith1@university.edu"
        assert second.ok

    def test_user_supplied_duplicate_email_is_an_error(self, instructor_db):
        create_instructor(
            first_name="Alan", last_name="Turing",
            email="alan.turing@university.edu", **self._LOCAL_ONLY,
        )
        dup = create_instructor(
            first_name="Alan", last_name="Turing",
            email="alan.turing@university.edu", **self._LOCAL_ONLY,
        )

        assert dup.ok is False
        assert dup.error is not None
        assert "already exists" in dup.error
        # No second instructors row was created.
        assert len(_fetchall(instructor_db, "SELECT id FROM instructors")) == 1

    def test_missing_name_is_rejected(self, instructor_db):
        result = create_instructor(first_name="", last_name="Nobody", **self._LOCAL_ONLY)
        assert result.ok is False
        assert result.error is not None
        assert len(_fetchall(instructor_db, "SELECT id FROM instructors")) == 0

    def test_invalid_email_is_rejected(self, instructor_db):
        result = create_instructor(
            first_name="Bad", last_name="Email", email="not-an-email", **self._LOCAL_ONLY
        )
        assert result.ok is False
        assert result.error is not None
        assert len(_fetchall(instructor_db, "SELECT id FROM instructors")) == 0

    def test_can_skip_staff_registration(self, instructor_db):
        result = create_instructor(
            first_name="Solo", last_name="Scheduler",
            register_as_staff=False, **self._LOCAL_ONLY,
        )
        assert result.ok
        assert result.staff_registered is False
        assert result.user_id is None
        # instructors row exists, but no users row was written.
        assert len(_fetchall(instructor_db, "SELECT id FROM instructors")) == 1
        assert len(_fetchall(instructor_db, "SELECT id FROM users")) == 0

    def test_staff_crud_backfill_only_touches_instructors(self, instructor_db):
        """Mirrors the call staff creation makes for a role='instructor' member:
        the users/user_accounts rows already exist, so all optional stores are
        off and only the instructors scheduling record should be created."""
        result = create_instructor(
            first_name="Katherine", last_name="Johnson",
            email="katherine.johnson@university.edu",
            register_as_staff=False,
            create_login=False,
            send_welcome_email=False,
        )
        assert result.ok
        assert result.instructor_id is not None
        assert result.account_created is False
        assert result.staff_registered is False
        instructors = _fetchall(instructor_db, "SELECT * FROM instructors")
        assert len(instructors) == 1
        assert instructors[0]["email"] == "katherine.johnson@university.edu"
        # staff CRUD owns these rows; the backfill must not add its own.
        assert len(_fetchall(instructor_db, "SELECT id FROM users")) == 0
        assert len(_fetchall(instructor_db, "SELECT id FROM user_accounts")) == 0


# ---------------------------------------------------------------------------
# Form choices, suitability, editing and deleting
# ---------------------------------------------------------------------------

from education_system.systems.university.domains.curriculum.domain.course_management import (  # noqa: E402
    instructor_service as svc,
)


@pytest.fixture
def catalogue_db(instructor_db):
    conn = sqlite3.connect(instructor_db)
    conn.executescript(
        """
        CREATE TABLE courses (
            id TEXT PRIMARY KEY, code TEXT, name TEXT, course_code TEXT, course_name TEXT,
            department TEXT, status TEXT DEFAULT 'active');
        INSERT INTO courses (id, course_code, course_name, department, status) VALUES
            ('AI', 'AI', 'Artificial Intelligence', 'School of Computing', 'active'),
            ('DS', 'DS', 'Data Science', 'School of Computing', 'active'),
            ('SE', 'SE', 'Software Engineering', 'School of Computing', 'inactive'),
            ('DSB', 'DSB', 'Business Data Science', 'Business School', 'active'),
            ('MKT', 'MKT', 'Marketing', 'Business School', 'active');
        CREATE TABLE course_schedule (
            id INTEGER PRIMARY KEY, course_id TEXT, semester TEXT, year INTEGER,
            instructor_id INTEGER REFERENCES instructors(id));
        CREATE TABLE exams (id INTEGER PRIMARY KEY, instructor_id INTEGER REFERENCES instructors(id));
        INSERT INTO instructors (id, first_name, last_name, email, department, specialization,
                                 status, is_active, created_at, updated_at)
        VALUES (1, 'Ada', 'Byron', 'ada@university.edu', 'School of Computing', 'Data Science',
                'Active', 1, 'x', 'x');
        INSERT INTO users (id, username, first_name, last_name, email, role)
        VALUES (5, 'ada', 'Ada', 'Byron', 'ada@university.edu', 'instructor');
        INSERT INTO user_accounts (username, user_id, is_active) VALUES ('ada', 5, 1);
        """
    )
    conn.commit()
    conn.close()
    return instructor_db


@pytest.fixture
def sent(monkeypatch):
    """Record update e-mails rather than reach the outbox."""
    calls = []

    def fake(name, email, changes, updated_by):
        calls.append((name, email, list(changes), updated_by))
        return True

    monkeypatch.setattr(svc, "_send_update_email", fake)
    return calls


class TestChoices:
    def test_specialisms_come_from_each_departments_courses(self, catalogue_db):
        catalogue = svc.department_specialisms()
        assert sorted(catalogue) == ["Business School", "School of Computing"]
        assert "Data Science" in catalogue["School of Computing"]
        assert "Data Science" not in catalogue["Business School"]

    def test_days_are_known_unique_and_capped(self):
        assert svc.parse_preferred_days("mon, Monday;tue,Sunday") == ["Monday", "Tuesday"]
        assert len(svc.parse_preferred_days("Mon,Tue,Wed,Thu,Fri")) == svc.MAX_PREFERRED_DAYS

    def test_time_windows_round_trip_and_older_text_survives(self):
        assert svc.time_value("9am-5pm") == "09:00-17:00"
        assert svc.time_label("09:00-17:00") == "9am-5pm"
        assert svc.time_value(svc.time_label("mornings")) == "mornings"


class TestSuitableCourses:
    def test_specialism_first_then_department_and_active_only(self, catalogue_db):
        codes = [c["code"] for c in svc.suitable_courses("School of Computing", "Data Science")]
        assert codes == ["DS", "DSB", "AI"]

    def test_department_alone_lists_that_department(self, catalogue_db):
        codes = {c["code"] for c in svc.suitable_courses("Business School", "")}
        assert codes == {"DSB", "MKT"}

    def test_nothing_set_offers_nothing(self, catalogue_db):
        assert svc.suitable_courses("", "") == []


class TestUpdateInstructor:
    def test_reports_and_emails_only_what_changed(self, catalogue_db, sent):
        result = svc.update_instructor(1, updated_by="admin", sync_login=False,
                                       first_name="Ada", department="Business School",
                                       preferred_days="Monday,Friday", preferred_times="09:00-17:00")
        assert result.ok and result.email_sent is True
        assert len(result.changes) == 3
        assert "Department: School of Computing → Business School" in result.changes
        assert "Preferred times: Not set → 9am-5pm" in result.changes
        assert sent[0][:2] == ("Ada Byron", "ada@university.edu")
        row = _fetchall(catalogue_db, "SELECT * FROM instructors WHERE id = 1")[0]
        assert row["department"] == "Business School"
        assert row["preferred_times"] == "09:00-17:00"

    def test_no_change_sends_nothing(self, catalogue_db, sent):
        result = svc.update_instructor(1, sync_login=False, department="School of Computing")
        assert result.ok and result.changes == [] and result.email_sent is None
        assert sent == []

    @pytest.mark.parametrize("days", ["Monday,Monday", "Mon,Tue,Wed,Thu,Fri", "Sunday"])
    def test_refuses_repeated_excess_or_unknown_days(self, catalogue_db, sent, days):
        result = svc.update_instructor(1, sync_login=False, preferred_days=days)
        assert not result.ok and sent == []

    def test_leaving_active_also_clears_is_active(self, catalogue_db, sent):
        svc.update_instructor(1, sync_login=False, status="On Leave")
        row = _fetchall(catalogue_db, "SELECT status, is_active FROM instructors WHERE id = 1")[0]
        assert row == {"status": "On Leave", "is_active": 0}

    def test_failed_email_keeps_the_change_and_warns(self, catalogue_db, monkeypatch):
        def boom(*_a):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(svc, "_send_update_email", boom)
        result = svc.update_instructor(1, sync_login=False, department="Business School")
        assert result.ok and result.email_sent is False and result.warnings


class TestDeleteInstructor:
    def test_releases_assignments_and_closes_the_local_login(self, catalogue_db, monkeypatch):
        from education_system.platform.identity.auth import core as auth_core

        closed = []
        monkeypatch.setattr(auth_core.UserAuth, "__init__", lambda self, *a, **k: None)
        monkeypatch.setattr(auth_core.UserAuth, "revoke_system_access",
                            lambda self, *a: closed.append(a) or True)
        conn = sqlite3.connect(catalogue_db)
        conn.execute("INSERT INTO course_schedule (course_id, semester, year, instructor_id) "
                     "VALUES ('DS', 'Fall', 2026, 1)")
        conn.commit()
        conn.close()

        result = svc.delete_instructor(1)

        assert result.ok and result.released_assignments == 1 and result.login_disabled
        assert closed == [("ada", "ada@university.edu", "university", "instructor")]
        assert _fetchall(catalogue_db, "SELECT id FROM instructors") == []
        assert _fetchall(catalogue_db, "SELECT instructor_id FROM course_schedule") == [{"instructor_id": None}]
        assert _fetchall(catalogue_db, "SELECT is_active FROM user_accounts") == [{"is_active": 0}]

    def test_teaching_records_refuse_the_delete(self, catalogue_db):
        conn = sqlite3.connect(catalogue_db)
        conn.execute("INSERT INTO exams (instructor_id) VALUES (1)")
        conn.commit()
        conn.close()

        result = svc.delete_instructor(1, disable_login=False)

        assert not result.ok and result.blockers == {"exams": 1}
        assert len(_fetchall(catalogue_db, "SELECT id FROM instructors")) == 1
