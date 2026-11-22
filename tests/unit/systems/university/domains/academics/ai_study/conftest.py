"""Shared fixtures for the AI Study Companion tests.

Every test runs against the autouse isolated university DB (the template DB
copied per test, ``DEFAULT_DB_PATH`` patched). The template has ``users``,
``students``, ``modules``, ``student_modules`` and ``module_grades``; the
tables the companion reads from other areas (exams, assignments, messages,
early warning, module specifications) are created here with the columns it
uses. ``log_activity`` and outbound email are stubbed, and the AI path is
off so nothing leaves the machine.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

PLANNING = ("education_system.systems.university.domains.student_life."
            "domain.study_hub.services.planning")

EXTRA_TABLES = (
    """CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL, module_name TEXT,
        date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, room TEXT,
        enrolled_student_ids TEXT, exam_name TEXT, status TEXT DEFAULT 'published')""",
    """CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL, title TEXT NOT NULL,
        due_date TEXT NOT NULL, max_marks INTEGER DEFAULT 100, is_active INTEGER DEFAULT 1,
        archived INTEGER DEFAULT 0, status TEXT DEFAULT 'active')""",
    """CREATE TABLE IF NOT EXISTS assignment_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL, grade REAL, is_final_submission INTEGER DEFAULT 1,
        grade_released_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER DEFAULT 0, sent_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS early_warning_indicators (
        indicator_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
        indicator_type TEXT NOT NULL, indicator_value TEXT NOT NULL, severity TEXT NOT NULL,
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP, is_resolved INTEGER DEFAULT 0,
        resolved_at TEXT, notes TEXT)""",
    """CREATE TABLE IF NOT EXISTS module_specifications (
        module_code TEXT PRIMARY KEY, aims TEXT, indicative_content TEXT, reading_list TEXT)""",
    """CREATE TABLE IF NOT EXISTS module_staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL, username TEXT NOT NULL,
        role TEXT NOT NULL, hours REAL DEFAULT 0, academic_year TEXT DEFAULT '')""",
)


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.fixture(autouse=True)
def _ai_off(monkeypatch):
    monkeypatch.setenv("STUDY_COMPANION_AI", "off")


@pytest.fixture()
def db():
    """``(get_connection, transaction)`` on the isolated DB, extra tables made."""
    from education_system.systems.university.infrastructure.database.db import (
        get_connection, transaction,
    )
    with transaction() as conn:
        for ddl in EXTRA_TABLES:
            conn.execute(ddl)
    return get_connection, transaction


@pytest.fixture()
def service(db):
    with patch(f"{PLANNING}.log_activity"), \
            patch("education_system.systems.university.application.teaching."
                  "occurrences.send_emails", side_effect=lambda e: len(e)):
        from education_system.systems.university.domains.student_life.domain.study_hub.services.planning import (
            AIStudyService,
        )
        yield AIStudyService()


@pytest.fixture()
def student(db):
    """Student S1 (login s1) enrolled on CS101 and CS102, with topics for CS101."""
    _, transaction = db
    with transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO students (student_id, first_name, last_name, "
                     "email_address) VALUES ('S1', 'Ada', 'Lovelace', 's1@example.ac.uk')")
        conn.execute("INSERT OR IGNORE INTO users (username, role, student_id, email) "
                     "VALUES ('s1', 'student', 'S1', 's1@example.ac.uk')")
        for code, name in (("CS101", "Programming"), ("CS102", "Algorithms")):
            conn.execute("INSERT OR IGNORE INTO modules (module_code, module_name) VALUES (?, ?)",
                         (code, name))
            conn.execute("INSERT OR IGNORE INTO student_modules (student_id, module_code) "
                         "VALUES ('S1', ?)", (code,))
        conn.execute("INSERT OR REPLACE INTO module_specifications (module_code, "
                     "indicative_content) VALUES ('CS101', 'Recursion; Loops; Hash tables')")
    return "S1"
