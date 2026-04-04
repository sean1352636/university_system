"""Tests for ReverseLookupService."""

import sqlite3

import pytest

from education_system.shared.reverse_lookup.reverse_lookup_service import (
    ReverseLookupService,
)


@pytest.fixture
def system_dbs(tmp_path):
    """Create minimal system databases for reverse-lookup tests."""
    dbs = {}

    # Primary uses 'pupils'
    primary_db = str(tmp_path / "primary.db")
    conn = sqlite3.connect(primary_db)
    conn.execute(
        "CREATE TABLE pupils (id INTEGER PRIMARY KEY, pupil_id TEXT, "
        "first_name TEXT, last_name TEXT, year_group TEXT, "
        "status TEXT DEFAULT 'active')"
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
        conn.commit()
        conn.close()
        dbs[sys_name] = db

    return dbs


@pytest.fixture
def svc(system_dbs):
    return ReverseLookupService(
        primary_db=system_dbs["primary"],
        secondary_db=system_dbs["secondary"],
        college_db=system_dbs["college"],
        university_db=system_dbs["university"],
    )


# ── find_transferred_students ────────────────────────────────────────

class TestFindTransferredStudents:
    def test_empty_db_returns_empty(self, svc):
        assert svc.find_transferred_students("primary") == []

    def test_only_transferred_status_returned(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0001', 'Alice', 'Smith', 'transferred')"
        )
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0002', 'Bob', 'Jones', 'active')"
        )
        conn.commit()
        conn.close()

        results = svc.find_transferred_students("primary")
        assert len(results) == 1
        assert results[0]["name"] == "Alice Smith"
        assert results[0]["student_id"] == "PRI0001"
        assert results[0]["status"] == "transferred"

    def test_transferred_from_secondary(self, svc, system_dbs):
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status, year_group) "
            "VALUES ('SEC0001', 'Charlie', 'Brown', 'transferred', 'Year 11')"
        )
        conn.commit()
        conn.close()

        results = svc.find_transferred_students("secondary")
        assert len(results) == 1
        assert results[0]["name"] == "Charlie Brown"
        assert results[0]["year_group"] == "Year 11"


# ── find_destination ─────────────────────────────────────────────────

class TestFindDestination:
    def test_no_destination_returns_none(self, svc):
        assert svc.find_destination("Nobody Here", "primary") is None

    def test_finds_student_in_destination(self, svc, system_dbs):
        # Student transferred from primary, now in secondary
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "status, previous_system_id) "
            "VALUES ('SEC0010', 'Dana', 'Lee', 'active', 'PRI0010')"
        )
        conn.commit()
        conn.close()

        result = svc.find_destination("Dana Lee", "primary")
        assert result is not None
        assert result["dest_system"] == "secondary"
        assert result["name"] == "Dana Lee"
        assert result["status"] == "active"

    def test_finds_in_downstream_system(self, svc, system_dbs):
        """A primary student could skip secondary and appear at college."""
        conn = sqlite3.connect(system_dbs["college"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status) "
            "VALUES ('COL0010', 'Eve', 'Park', 'active')"
        )
        conn.commit()
        conn.close()

        result = svc.find_destination("Eve Park", "primary")
        assert result is not None
        assert result["dest_system"] == "college"


# ── get_destination_summary ──────────────────────────────────────────

class TestGetDestinationSummary:
    def test_empty_summary(self, svc):
        summary = svc.get_destination_summary("primary")
        assert summary["_total_transferred"] == 0
        assert summary["Unknown / Not Found"] == 0

    def test_summary_with_transferred_students(self, svc, system_dbs):
        # Mark two primary pupils as transferred
        conn = sqlite3.connect(system_dbs["primary"])
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0020', 'Faye', 'Kim', 'transferred')"
        )
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, status) "
            "VALUES ('PRI0021', 'Gary', 'Hill', 'transferred')"
        )
        conn.commit()
        conn.close()

        # Put Faye in secondary
        conn = sqlite3.connect(system_dbs["secondary"])
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, status) "
            "VALUES ('SEC0020', 'Faye', 'Kim', 'active')"
        )
        conn.commit()
        conn.close()

        summary = svc.get_destination_summary("primary")
        assert summary["_total_transferred"] == 2
        assert summary.get("Secondary School", 0) >= 1
        # Gary not found anywhere
        assert summary["Unknown / Not Found"] >= 1
