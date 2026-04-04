"""Tests for cross-system JourneyService."""

import sqlite3

import pytest

from education_system.shared.cross_system.journey_service import JourneyService


@pytest.fixture
def system_dbs(tmp_path):
    """Create minimal system databases for journey tests."""
    dbs = {}

    # Primary uses 'pupils' with 'pupil_id'
    primary_db = str(tmp_path / "primary.db")
    conn = sqlite3.connect(primary_db)
    conn.execute(
        "CREATE TABLE pupils (id INTEGER PRIMARY KEY, pupil_id TEXT, "
        "first_name TEXT, last_name TEXT, year_group TEXT, "
        "status TEXT DEFAULT 'active', date_of_birth TEXT)"
    )
    conn.execute(
        "CREATE TABLE academic_transfer_history "
        "(id INTEGER PRIMARY KEY, student_id TEXT, source_system TEXT, "
        "dest_system TEXT, student_name TEXT, transfer_date TEXT)"
    )
    conn.commit()
    conn.close()
    dbs["primary"] = primary_db

    # Secondary, college, university use 'students' with 'student_id'
    for sys_name in ("secondary", "college", "university"):
        db = str(tmp_path / f"{sys_name}.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE students (id INTEGER PRIMARY KEY, student_id TEXT, "
            "first_name TEXT, last_name TEXT, year_group TEXT, "
            "status TEXT DEFAULT 'active', date_of_birth TEXT, "
            "previous_system_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE academic_transfer_history "
            "(id INTEGER PRIMARY KEY, student_id TEXT, source_system TEXT, "
            "dest_system TEXT, student_name TEXT, transfer_date TEXT)"
        )
        conn.commit()
        conn.close()
        dbs[sys_name] = db

    return dbs


@pytest.fixture
def svc(system_dbs):
    return JourneyService(
        primary_db=system_dbs["primary"],
        secondary_db=system_dbs["secondary"],
        college_db=system_dbs["college"],
        university_db=system_dbs["university"],
    )


# ── search_student ───────────────────────────────────────────────────

class TestSearchStudent:
    def test_empty_dbs_return_empty(self, svc):
        assert svc.search_student("Alice") == []

    def test_empty_query_returns_empty(self, svc):
        assert svc.search_student("") == []
        assert svc.search_student("   ") == []

    def test_finds_primary_pupil(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, year_group, status) "
            "VALUES ('PRI0001', 'Alice', 'Smith', 'Year 3', 'active')"
        )
        conn.commit()
        conn.close()

        results = svc.search_student("Alice")
        assert len(results) == 1
        assert results[0]["system"] == "primary"
        assert results[0]["name"] == "Alice Smith"
        assert results[0]["student_id"] == "PRI0001"

    def test_finds_student_in_secondary(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, year_group, status) "
            "VALUES ('SEC0001', 'Bob', 'Jones', 'Year 8', 'active')"
        )
        conn.commit()
        conn.close()

        results = svc.search_student("Bob")
        assert len(results) == 1
        assert results[0]["system"] == "secondary"
        assert results[0]["name"] == "Bob Jones"

    def test_finds_across_multiple_systems(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0002', 'Charlie', 'Brown', 'transferred')"
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status) "
            "VALUES ('SEC0002', 'Charlie', 'Brown', 'active')"
        )
        conn.commit()
        conn.close()

        results = svc.search_student("Charlie Brown")
        assert len(results) == 2
        systems = {r["system"] for r in results}
        assert systems == {"primary", "secondary"}


# ── get_journey ──────────────────────────────────────────────────────

class TestGetJourney:
    def test_empty_dbs_return_empty(self, svc):
        assert svc.get_journey(student_name="Nobody") == []

    def test_journey_by_name_single_system(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["college"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "year_group, status) VALUES ('COL0001', 'Dana', 'Lee', 'Year 12', 'active')"
        )
        conn.commit()
        conn.close()

        stages = svc.get_journey(student_name="Dana Lee")
        assert len(stages) == 1
        assert stages[0]["system"] == "college"
        assert stages[0]["name"] == "Dana Lee"

    def test_journey_by_id_and_system(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["university"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "year_group, status) VALUES ('UNI0001', 'Eve', 'Park', 'Year 1', 'active')"
        )
        conn.commit()
        conn.close()

        stages = svc.get_journey(student_id="UNI0001", system="university")
        assert len(stages) >= 1
        assert stages[-1]["system"] == "university"
        assert stages[-1]["student_id"] == "UNI0001"

    def test_journey_ordered_primary_to_university(self, svc, system_dbs):
        """Stages are returned in chronological order primary -> university."""
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0003', 'Faye', 'Kim', 'transferred')"
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(system_dbs["college"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status) "
            "VALUES ('COL0003', 'Faye', 'Kim', 'active')"
        )
        conn.commit()
        conn.close()

        stages = svc.get_journey(student_name="Faye Kim")
        systems = [s["system"] for s in stages]
        assert systems == sorted(systems, key=lambda s: ["primary", "secondary", "college", "university"].index(s))
