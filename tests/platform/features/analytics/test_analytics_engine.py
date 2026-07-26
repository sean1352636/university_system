"""Tests for AnalyticsEngine."""

import sqlite3
import pytest

from education_system.platform.features.analytics.engine import AnalyticsEngine


def _create_schema(db_path):
    """Create minimal students/attendance/grades/courses/enrollments tables."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name  TEXT,
            year_group TEXT,
            form_group TEXT,
            status     TEXT DEFAULT 'active'
        );
        CREATE TABLE attendance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date       TEXT NOT NULL,
            status     TEXT NOT NULL
        );
        CREATE TABLE grades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT NOT NULL,
            course_code TEXT,
            grade       TEXT NOT NULL
        );
        CREATE TABLE courses (
            course_code TEXT PRIMARY KEY,
            title       TEXT
        );
        CREATE TABLE enrollments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT,
            course_code TEXT
        );
    """)
    conn.commit()
    conn.close()


def _seed_data(db_path):
    """Insert sample rows for testing."""
    conn = sqlite3.connect(str(db_path))
    conn.executemany(
        "INSERT INTO students VALUES (?,?,?,?,?,?)",
        [
            ("S01", "Alice", "Smith", "12", "12A", "active"),
            ("S02", "Bob", "Jones", "12", "12B", "active"),
            ("S03", "Carol", "Lee", "13", "13A", "active"),
        ],
    )
    conn.executemany(
        "INSERT INTO attendance (student_id, date, status) VALUES (?,?,?)",
        [
            ("S01", "2026-03-01", "present"),
            ("S01", "2026-03-02", "present"),
            ("S01", "2026-03-03", "absent"),
            ("S02", "2026-03-01", "present"),
            ("S02", "2026-03-02", "late"),
            ("S03", "2026-03-01", "absent"),
            ("S03", "2026-03-02", "absent"),
        ],
    )
    conn.executemany(
        "INSERT INTO grades (student_id, course_code, grade) VALUES (?,?,?)",
        [
            ("S01", "MATH101", "A"),
            ("S01", "ENG101", "B"),
            ("S02", "MATH101", "C"),
            ("S02", "ENG101", "A"),
            ("S03", "MATH101", "B"),
        ],
    )
    conn.executemany(
        "INSERT INTO courses VALUES (?,?)",
        [("MATH101", "Mathematics"), ("ENG101", "English")],
    )
    conn.executemany(
        "INSERT INTO enrollments (student_id, course_code) VALUES (?,?)",
        [("S01", "MATH101"), ("S01", "ENG101"), ("S02", "MATH101"), ("S03", "MATH101")],
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def engine_empty(tmp_path):
    db = str(tmp_path / "analytics.db")
    _create_schema(db)
    return AnalyticsEngine(db_path=db, system_key="sixth_form")


@pytest.fixture()
def engine(tmp_path):
    db = str(tmp_path / "analytics.db")
    _create_schema(db)
    _seed_data(db)
    return AnalyticsEngine(db_path=db, system_key="sixth_form")


# ── empty DB ─────────────────────────────────────────────────────────

def test_attendance_summary_empty(engine_empty):
    summary = engine_empty.attendance_summary()
    assert summary["total_records"] == 0
    assert summary["attendance_rate"] == 0.0


def test_grade_distribution_empty(engine_empty):
    result = engine_empty.grade_distribution()
    assert result["total_grades"] == 0
    assert result["distribution"] == {}


def test_system_overview_empty(engine_empty):
    overview = engine_empty.system_overview()
    assert overview["system_key"] == "sixth_form"
    assert overview["total_students"] == 0
    assert overview["total_grades"] == 0


# ── with data ────────────────────────────────────────────────────────

def test_attendance_summary(engine):
    summary = engine.attendance_summary()
    assert summary["total_records"] == 7
    assert summary["present"] == 3
    assert summary["late"] == 1
    assert summary["absent"] == 3
    # rate = (3+1)/7*100 ≈ 57.1
    assert 57.0 <= summary["attendance_rate"] <= 57.2


def test_attendance_summary_by_year(engine):
    summary = engine.attendance_summary()
    by_year = summary["by_year_group"]
    assert "12" in by_year
    assert "13" in by_year


def test_grade_distribution(engine):
    result = engine.grade_distribution()
    assert result["total_grades"] == 5
    assert result["distribution"]["A"] == 2
    assert result["distribution"]["B"] == 2
    assert result["distribution"]["C"] == 1


def test_grade_distribution_by_course(engine):
    result = engine.grade_distribution(course_code="MATH101")
    assert result["total_grades"] == 3


def test_at_risk_students(engine):
    # All data is recent, threshold 100% means everyone with any absence is at risk
    at_risk = engine.at_risk_students(threshold_attendance=100.0, days=365)
    # S01: 2/3 present+late = 66.7%, S02: 2/2 = 100%, S03: 0/2 = 0%
    ids = {s["student_id"] for s in at_risk}
    assert "S03" in ids
    assert "S01" in ids


def test_at_risk_students_empty(engine_empty):
    result = engine_empty.at_risk_students()
    assert result == []


def test_system_overview(engine):
    overview = engine.system_overview()
    assert overview["total_students"] == 3
    assert overview["total_courses"] == 2
    assert overview["total_enrollments"] == 4
    assert overview["total_grades"] == 5
    assert overview["total_attendance"] == 7
