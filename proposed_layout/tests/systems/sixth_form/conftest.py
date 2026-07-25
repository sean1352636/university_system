"""Shared fixtures for Sixth Form tests."""

from __future__ import annotations

import datetime as _dt
import importlib
import sqlite3
from types import SimpleNamespace

import pytest

# Data modules whose DB_PATH must be redirected at the temp file so no
# test ever touches the real sixthform.db. These cover the new feature
# modules plus the dependency tables their init_db chains create.
_FEATURE_MODULES = (
    "education_system.systems.sixth_form.domain.learners.students.students",
    "education_system.systems.sixth_form.domain.academics.courses.courses",
    "education_system.systems.sixth_form.domain.academics.class_groups.class_groups",
    "education_system.systems.sixth_form.domain.academics.timetable_optimiser.timetable_optimiser",
    "education_system.systems.sixth_form.domain.assessment.risk_analytics.risk_analytics",
    "education_system.systems.sixth_form.domain.progression.ucas_workflow.ucas_workflow",
    "education_system.systems.sixth_form.domain.governance.automation_rules.automation_rules",
    "education_system.systems.sixth_form.domain.operations.communications.parent_portal.parent_portal",
)

# Input tables the feature modules READ but don't own. We create them
# directly (matching the live schema) so the readers find them, rather
# than importing every producing module. FK enforcement is left off on
# the seeding connection so rows can be inserted without full graphs.
_INPUT_DDL = """
CREATE TABLE IF NOT EXISTS predicted_grades (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL, subject TEXT NOT NULL, grade TEXT NOT NULL,
    confidence TEXT DEFAULT 'Medium', notes TEXT, predicted_by TEXT,
    predicted_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, subject));
CREATE TABLE IF NOT EXISTS targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    subject_name TEXT NOT NULL, year_group TEXT, mte_grade TEXT NOT NULL,
    aspirational_grade TEXT, current_grade TEXT, baseline_record_id INTEGER,
    set_on TEXT, set_by TEXT, last_reviewed TEXT, next_review_due TEXT,
    status TEXT DEFAULT 'Not Started', rationale TEXT, notes TEXT,
    UNIQUE(student_id, subject_name));
CREATE TABLE IF NOT EXISTS baseline_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    subject_name TEXT, assessment_type TEXT DEFAULT 'Initial Test', assessment_date TEXT,
    raw_score REAL, max_score REAL, percentage REAL, baseline_grade TEXT,
    standardised_score REAL, confidence TEXT DEFAULT 'Medium', is_primary INTEGER DEFAULT 0,
    assessor TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS mock_exams (
    mock_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, subject TEXT NOT NULL,
    exam_board TEXT, paper_number INTEGER, date_sat TEXT NOT NULL, duration_minutes INTEGER,
    max_marks INTEGER NOT NULL, notes TEXT);
CREATE TABLE IF NOT EXISTS mock_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT, mock_id INTEGER NOT NULL,
    student_id TEXT NOT NULL, marks INTEGER, grade TEXT, notes TEXT,
    recorded_at TEXT DEFAULT (datetime('now')), UNIQUE(mock_id, student_id));
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT, slot_id INTEGER NOT NULL,
    student_id TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL,
    minutes_late INTEGER, notes TEXT, recorded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(slot_id, student_id, date));
CREATE TABLE IF NOT EXISTS behaviour_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    entry_date TEXT NOT NULL, entry_type TEXT NOT NULL, category TEXT NOT NULL,
    severity TEXT, points INTEGER DEFAULT 0, location TEXT, description TEXT NOT NULL,
    recorded_by TEXT, action_taken TEXT, follow_up_required INTEGER DEFAULT 0,
    follow_up_date TEXT, parent_contacted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ucas_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    cycle_year INTEGER NOT NULL, ucas_id TEXT, status TEXT DEFAULT 'Draft',
    personal_statement TEXT, submitted_at TEXT, notes TEXT,
    UNIQUE(student_id, cycle_year));
CREATE TABLE IF NOT EXISTS personal_statements (
    statement_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    title TEXT, body TEXT NOT NULL, word_count INTEGER DEFAULT 0, char_count INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0, status TEXT DEFAULT 'Draft', feedback TEXT, reviewer TEXT,
    reviewed_at TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS academic_references (
    reference_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
    referee TEXT NOT NULL, referee_role TEXT, title TEXT, body TEXT,
    word_count INTEGER DEFAULT 0, char_count INTEGER DEFAULT 0, line_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Requested', requested_at TEXT, submitted_at TEXT, notes TEXT,
    updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS timetable_slots (
    slot_id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL,
    day INTEGER NOT NULL, period INTEGER NOT NULL, start_time TEXT, end_time TEXT,
    room TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(group_id, day, period));
"""


def _iso_days_ago(n: int) -> str:
    return (_dt.date.today() - _dt.timedelta(days=n)).isoformat()


@pytest.fixture
def feature_db(tmp_path, monkeypatch):
    """Isolated DB seeded for the six new feature modules.

    Redirects every relevant data module's ``DB_PATH`` at one temp
    SQLite file, builds the schemas, and seeds two students:

    * ``S1`` — poor attendance, negative behaviour, grades below target,
      a trailing mock → should score as at-risk.
    * ``S2`` — clean record, predictions at/above target → low risk.

    Returns a namespace with the imported modules and seeded ids.
    """
    db = str(tmp_path / "sixthform.db")
    mods = {}
    for dotted in _FEATURE_MODULES:
        m = importlib.import_module(dotted)
        monkeypatch.setattr(m, "DB_PATH", db, raising=False)
        if hasattr(m, "_DB_READY"):
            monkeypatch.setattr(m, "_DB_READY", False, raising=False)
        mods[dotted.rsplit(".", 1)[-1]] = m

    # Build schemas via the real init_db chains (students, courses,
    # class_groups, and each feature module's own tables).
    mods["students"].init_db()
    mods["class_groups"].init_db()
    for key in ("timetable_optimiser", "risk_analytics", "ucas_workflow",
                "automation_rules", "parent_portal"):
        mods[key].init_db()

    conn = sqlite3.connect(db)
    conn.executescript(_INPUT_DDL)

    # ── Students ─────────────────────────────────────────────────────
    conn.executemany(
        "INSERT INTO students (student_id, first_name, last_name, email, "
        "subject_1, subject_2, subject_3, status) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("S1", "Alex", "Atrisk", "s1@example.test",
             "Mathematics", "Physics", "Chemistry", "Active"),
            ("S2", "Sam", "Steady", "s2@example.test",
             "Mathematics", None, None, "Active"),
        ])

    # ── Predicted grades / targets (S1 below target, S2 above) ───────
    conn.executemany(
        "INSERT INTO predicted_grades (student_id, subject, grade) VALUES (?,?,?)",
        [("S1", "Mathematics", "D"), ("S1", "Physics", "C"), ("S1", "Chemistry", "E"),
         ("S2", "Mathematics", "A")])
    conn.executemany(
        "INSERT INTO targets (student_id, subject_name, mte_grade) VALUES (?,?,?)",
        [("S1", "Mathematics", "B"), ("S1", "Physics", "C"), ("S1", "Chemistry", "C"),
         ("S2", "Mathematics", "B")])

    # ── Mock below prediction for S1 Maths ───────────────────────────
    conn.execute(
        "INSERT INTO mock_exams (mock_id, title, subject, date_sat, max_marks) "
        "VALUES (1, 'Maths Mock 1', 'Mathematics', ?, 100)", (_iso_days_ago(10),))
    conn.execute(
        "INSERT INTO mock_results (mock_id, student_id, grade) VALUES (1, 'S1', 'E')")

    # ── Attendance: S1 poor, S2 perfect (recent dates) ───────────────
    att = []
    for i in range(20):
        att.append((100 + i, "S1", _iso_days_ago(i + 1), "Absent" if i % 2 == 0 else "Present"))
    for i in range(20):
        att.append((100 + i, "S2", _iso_days_ago(i + 1), "Present"))
    conn.executemany(
        "INSERT INTO attendance_records (slot_id, student_id, date, status) VALUES (?,?,?,?)", att)

    # ── Behaviour: S1 net negative ───────────────────────────────────
    conn.executemany(
        "INSERT INTO behaviour_entries (student_id, entry_date, entry_type, category, "
        "points, description) VALUES (?,?,?,?,?,?)",
        [("S1", _iso_days_ago(5), "Negative", "Disruption", 8, "Repeated lateness"),
         ("S1", _iso_days_ago(3), "Positive", "Effort", 2, "Good homework")])

    conn.commit()
    conn.close()
    return SimpleNamespace(db=db, mods=mods, s1="S1", s2="S2")


@pytest.fixture
def fresh_ay_db(tmp_path, monkeypatch):
    """Point the Academic Year data module at a brand-new SQLite file.

    Returns the data module so tests can call its API directly.
    """
    db_path = tmp_path / "ay.db"
    from education_system.systems.sixth_form.domain.academics.academic_year import (
        academic_year as data,
    )
    monkeypatch.setattr(data, "DB_PATH", str(db_path))
    monkeypatch.setattr(data, "_DB_READY", False)
    # Reset RBAC defaults so a previous test can't leak.
    monkeypatch.setattr(data, "ENFORCE_RBAC", False)
    monkeypatch.setattr(data, "CURRENT_ACTOR_ROLE", None)
    monkeypatch.setattr(data, "CURRENT_ACTOR", None)
    data.init_db()
    return data
