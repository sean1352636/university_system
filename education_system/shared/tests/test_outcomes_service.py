"""Tests for OutcomesService."""

import sqlite3

import pytest

from education_system.shared.outcomes.outcomes_service import OutcomesService


@pytest.fixture
def system_dbs(tmp_path):
    """Create minimal system databases for outcomes tests."""
    dbs = {}

    # Primary uses 'pupils'
    primary_db = str(tmp_path / "primary.db")
    conn = sqlite3.connect(primary_db)
    conn.execute(
        "CREATE TABLE pupils (id INTEGER PRIMARY KEY, pupil_id TEXT, "
        "first_name TEXT, last_name TEXT, year_group TEXT, "
        "status TEXT DEFAULT 'active')"
    )
    conn.execute(
        "CREATE TABLE academic_transfer_history "
        "(id INTEGER PRIMARY KEY, student_id TEXT, source_system TEXT, "
        "student_name TEXT, transfer_date TEXT, status TEXT)"
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
            "CREATE TABLE grades (id INTEGER PRIMARY KEY, student_id INTEGER, "
            "subject TEXT, score REAL)"
        )
        conn.execute(
            "CREATE TABLE academic_transfer_history "
            "(id INTEGER PRIMARY KEY, student_id TEXT, source_system TEXT, "
            "student_name TEXT, transfer_date TEXT, status TEXT)"
        )
        conn.commit()
        conn.close()
        dbs[sys_name] = db

    return dbs


@pytest.fixture
def svc(system_dbs):
    return OutcomesService(
        primary_db=system_dbs["primary"],
        secondary_db=system_dbs["secondary"],
        college_db=system_dbs["college"],
        university_db=system_dbs["university"],
    )


# ── get_outcomes_for_system ──────────────────────────────────────────

class TestGetOutcomesForSystem:
    def test_empty_dbs_return_empty(self, svc):
        assert svc.get_outcomes_for_system("primary") == []

    def test_invalid_system_returns_empty(self, svc):
        assert svc.get_outcomes_for_system("nonexistent") == []

    def test_transfer_history_outcomes(self, svc, system_dbs):
        """Students in transfer history of destination show up as outcomes."""
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO academic_transfer_history "
            "(student_id, source_system, student_name, transfer_date, status) "
            "VALUES ('PRI0001', 'primary', 'Alice Smith', '2025-09-01', 'transferred')"
        )
        conn.commit()
        conn.close()

        results = svc.get_outcomes_for_system("primary")
        assert len(results) >= 1
        assert results[0]["student_name"] == "Alice Smith"
        assert results[0]["destination_system"] == "secondary"

    def test_previous_system_id_outcomes(self, svc, system_dbs):
        """Students with previous_system_id in destination appear as outcomes."""
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status, previous_system_id) "
            "VALUES ('SEC0001', 'Bob', 'Jones', 'active', 'PRI0001')"
        )
        conn.commit()
        conn.close()

        results = svc.get_outcomes_for_system("primary")
        assert len(results) >= 1
        found = [r for r in results if r["student_id"] == "PRI0001"]
        assert len(found) == 1
        assert found[0]["destination_system"] == "secondary"


# ── get_progression_stats ────────────────────────────────────────────

class TestGetProgressionStats:
    def test_empty_stats(self, svc):
        stats = svc.get_progression_stats("primary")
        assert stats["total_left"] == 0
        assert stats["progression_rate"] == 0.0
        assert stats["source_system"] == "primary"

    def test_stats_with_data(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status, previous_system_id) "
            "VALUES ('SEC0001', 'Charlie', 'Brown', 'active', 'PRI0001')"
        )
        conn.commit()
        conn.close()

        stats = svc.get_progression_stats("primary")
        assert stats["total_left"] >= 1
        assert stats["progressed_count"] >= 1


# ── search_student_outcome ───────────────────────────────────────────

class TestSearchStudentOutcome:
    def test_empty_query_returns_empty(self, svc):
        assert svc.search_student_outcome("") == []
        assert svc.search_student_outcome("   ") == []

    def test_empty_dbs_return_empty(self, svc):
        assert svc.search_student_outcome("Nobody") == []

    def test_finds_student_outcome(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0010', 'Dana', 'Lee', 'active')"
        )
        conn.commit()
        conn.close()

        results = svc.search_student_outcome("Dana")
        assert len(results) >= 1
        assert results[0]["student_name"] == "Dana Lee"
        assert results[0]["source_system"] == "primary"

    def test_university_graduated_outcomes(self, svc, system_dbs):
        """University is the terminal system; graduated students are outcomes."""
        conn = sqlite3.connect(system_dbs["university"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status) "
            "VALUES ('UNI0001', 'Eve', 'Park', 'graduated')"
        )
        conn.commit()
        conn.close()

        results = svc.get_outcomes_for_system("university")
        assert len(results) == 1
        assert results[0]["destination_system"] == "graduated"
        assert results[0]["destination_status"] == "graduated"
