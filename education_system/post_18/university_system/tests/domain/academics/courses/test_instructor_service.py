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

from education_system.post_18.university_system.infrastructure.database import db as db_module
from education_system.post_18.university_system.modules.domain.academics.services.course_management.instructor_service import (
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
