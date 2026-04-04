"""Tests for PredictiveService."""

import sqlite3

import pytest

from education_system.shared.predictive.predictive_service import (
    PredictiveService,
)


@pytest.fixture
def system_dbs(tmp_path):
    """Create minimal system databases for predictive tests."""
    dbs = {}

    # Primary
    primary_db = str(tmp_path / "primary.db")
    conn = sqlite3.connect(primary_db)
    conn.execute(
        "CREATE TABLE pupils (id INTEGER PRIMARY KEY, pupil_id TEXT, "
        "first_name TEXT, last_name TEXT, year_group TEXT, "
        "status TEXT DEFAULT 'active')"
    )
    conn.execute(
        "CREATE TABLE attendance_records (id INTEGER PRIMARY KEY, "
        "pupil_id TEXT, date TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE grades (id INTEGER PRIMARY KEY, pupil_id TEXT, "
        "subject TEXT, score REAL)"
    )
    conn.commit()
    conn.close()
    dbs["primary"] = primary_db

    for sys_name in ("secondary", "college", "university"):
        db = str(tmp_path / f"{sys_name}.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE students (id INTEGER PRIMARY KEY, student_id TEXT, "
            "first_name TEXT, last_name TEXT, year_group TEXT, "
            "status TEXT DEFAULT 'active', previous_system_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE attendance_records (id INTEGER PRIMARY KEY, "
            "student_id TEXT, date TEXT, status TEXT)"
        )
        conn.execute(
            "CREATE TABLE grades (id INTEGER PRIMARY KEY, student_id TEXT, "
            "subject TEXT, score REAL)"
        )
        conn.execute(
            "CREATE TABLE academic_transfer_history "
            "(id INTEGER PRIMARY KEY, student_id TEXT, source_system TEXT, "
            "student_name TEXT, transfer_date TEXT, attendance REAL, grade REAL)"
        )
        conn.commit()
        conn.close()
        dbs[sys_name] = db

    return dbs


@pytest.fixture
def svc(system_dbs):
    return PredictiveService(
        primary_db=system_dbs["primary"],
        secondary_db=system_dbs["secondary"],
        college_db=system_dbs["college"],
        university_db=system_dbs["university"],
    )


# ── get_at_risk_students ─────────────────────────────────────────────

class TestGetAtRiskStudents:
    def test_empty_db_returns_empty(self, svc):
        assert svc.get_at_risk_students("secondary") == []

    def test_no_previous_system_id_column_returns_empty(self, svc, system_dbs):
        """Primary table has no previous_system_id, so returns empty."""
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0001', 'Alice', 'Smith', 'active')"
        )
        conn.commit()
        conn.close()
        assert svc.get_at_risk_students("primary") == []

    def test_student_with_previous_system_flagged(self, svc, system_dbs):
        """A student with previous_system_id is included (at least Low risk)."""
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('SEC0001', 'Bob', 'Jones', 'active', 'PRI0001')"
        )
        conn.commit()
        conn.close()

        results = svc.get_at_risk_students("secondary")
        assert len(results) == 1
        assert results[0]["student_id"] == "SEC0001"
        assert results[0]["risk_level"] in ("High", "Medium", "Low")
        assert isinstance(results[0]["risk_score"], (int, float))
        assert isinstance(results[0]["risk_factors"], list)

    def test_low_attendance_raises_risk(self, svc, system_dbs):
        """Low current attendance should produce a higher risk score."""
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('SEC0002', 'Cara', 'Diaz', 'active', 'PRI0002')"
        )
        # 10 attendance records: 5 present, 5 absent -> 50%
        for i in range(5):
            conn.execute(
                "INSERT INTO attendance_records (student_id, date, status) "
                "VALUES ('SEC0002', ?, 'present')",
                (f"2026-01-{i+1:02d}",),
            )
        for i in range(5):
            conn.execute(
                "INSERT INTO attendance_records (student_id, date, status) "
                "VALUES ('SEC0002', ?, 'absent')",
                (f"2026-01-{i+6:02d}",),
            )
        conn.commit()
        conn.close()

        results = svc.get_at_risk_students("secondary")
        student = next(r for r in results if r["student_id"] == "SEC0002")
        assert student["attendance_pct"] == 50.0
        assert student["risk_score"] >= 30  # at least Medium
        risk_text = " ".join(student["risk_factors"])
        assert "attendance" in risk_text.lower()

    def test_sorted_by_risk_score_descending(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["college"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('COL0001', 'Dana', 'Lee', 'active', 'SEC0001')"
        )
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('COL0002', 'Eve', 'Park', 'active', 'SEC0002')"
        )
        # Give Eve terrible attendance to push her risk higher
        for i in range(10):
            conn.execute(
                "INSERT INTO attendance_records (student_id, date, status) "
                "VALUES ('COL0002', ?, 'absent')",
                (f"2026-02-{i+1:02d}",),
            )
        conn.commit()
        conn.close()

        results = svc.get_at_risk_students("college")
        assert len(results) == 2
        assert results[0]["risk_score"] >= results[1]["risk_score"]


# ── get_risk_factors ─────────────────────────────────────────────────

class TestGetRiskFactors:
    def test_missing_student_returns_error(self, svc):
        result = svc.get_risk_factors("NOBODY", "secondary")
        assert result.get("error") or result.get("risk_level") == "Unknown"

    def test_existing_student_returns_detail(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('SEC0005', 'Faye', 'Kim', 'active', 'PRI0005')"
        )
        conn.commit()
        conn.close()

        result = svc.get_risk_factors("SEC0005", "secondary")
        assert result["student_id"] == "SEC0005"
        assert result["student_name"] == "Faye Kim"
        assert "risk_level" in result
        assert isinstance(result["attendance_history"], list)
        assert isinstance(result["grade_history"], list)
        assert isinstance(result["transfer_history"], list)
