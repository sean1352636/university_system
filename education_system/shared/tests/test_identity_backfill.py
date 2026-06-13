"""Tests for the cross-system identity registry backfill."""

import sqlite3

import pytest

from education_system.shared.cross_system import identity_service
from education_system.shared.cross_system.identity_backfill import (
    backfill_identity_registry,
)


def _make_pupils_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT)"
    )
    conn.executemany("INSERT INTO pupils VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


def _make_students_db(path, rows, dob_col="date_of_birth"):
    conn = sqlite3.connect(str(path))
    conn.execute(
        f"CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, "
        f"last_name TEXT, {dob_col} TEXT)"
    )
    conn.executemany("INSERT INTO students VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


@pytest.fixture()
def world(tmp_path):
    """5 system DBs + auth DB. Noah appears in nursery, primary and university."""
    auth = tmp_path / "auth.db"
    identity_service.initialise_auth_db  # ensure import side-effects ok
    from education_system.shared.auth.schema import initialise_auth_db
    initialise_auth_db(str(auth))

    nursery = tmp_path / "nursery.db"
    primary = tmp_path / "primary.db"
    school = tmp_path / "school.db"
    college = tmp_path / "college.db"
    university = tmp_path / "university.db"

    _make_pupils_db(nursery, [
        ("NCH003", "Noah", "Campbell", "2019-06-21"),
        ("NCH004", "Mia", "Jones", ""),            # no DOB -> skipped
    ])
    _make_pupils_db(primary, [
        ("P100", "Noah", "Campbell", "2019-06-21"),  # same person as nursery
        ("P101", "Ada", "Lovelace", "2018-01-02"),
    ])
    _make_pupils_db(school, [])                      # empty
    _make_students_db(college, [
        ("C500", "Ada", "Lovelace", "2018-01-02"),   # same person as primary
    ])
    _make_students_db(university, [
        ("U900", "Noah", "Campbell", "2019-06-21"),  # same Noah, university slot
        ("U901", "", "Nameless", "2000-01-01"),      # no first name -> skipped
    ], dob_col="dob")

    db_paths = {
        "nursery": nursery, "primary": primary, "school": school,
        "college": college, "university": university,
    }
    return str(auth), db_paths


class TestBackfill:
    def test_links_and_dedups(self, world):
        auth, db_paths = world
        res = backfill_identity_registry(db_paths=db_paths, auth_db=auth)

        # Noah: nursery + primary + university = 1 journey, 3 slots.
        noah = identity_service.find_by_identity(
            "Noah", "Campbell", "2019-06-21", db_path=auth)
        assert noah is not None
        assert noah["nursery_student_id"] == "NCH003"
        assert noah["primary_student_id"] == "P100"
        assert noah["university_student_id"] == "U900"

        # Ada: primary + college.
        ada = identity_service.find_by_identity(
            "Ada", "Lovelace", "2018-01-02", db_path=auth)
        assert ada["primary_student_id"] == "P101"
        assert ada["college_student_id"] == "C500"

        # current_system reflects the last system linked (university order last).
        assert noah["current_system"] in ("nursery", "primary", "school",
                                          "college", "university")

    def test_counts(self, world):
        auth, db_paths = world
        res = backfill_identity_registry(db_paths=db_paths, auth_db=auth)
        assert res["nursery"]["skipped_no_dob"] == 1   # Mia
        assert res["university"]["skipped_no_name"] == 1  # Nameless
        # 5 linkable slot-links: Noah x3 (nursery/primary/university), Ada x2.
        assert res["_total"]["linked"] == 5
        assert res["school"]["total"] == 0

    def test_idempotent(self, world):
        auth, db_paths = world
        backfill_identity_registry(db_paths=db_paths, auth_db=auth)
        # second pass creates no new journeys
        before = sqlite3.connect(auth).execute(
            "SELECT COUNT(*) FROM student_journey").fetchone()[0]
        backfill_identity_registry(db_paths=db_paths, auth_db=auth)
        after = sqlite3.connect(auth).execute(
            "SELECT COUNT(*) FROM student_journey").fetchone()[0]
        assert before == after == 2   # Noah + Ada

    def test_dry_run_writes_nothing(self, world):
        auth, db_paths = world
        res = backfill_identity_registry(db_paths=db_paths, auth_db=auth, dry_run=True)
        assert res["_total"]["linked"] == 5
        count = sqlite3.connect(auth).execute(
            "SELECT COUNT(*) FROM student_journey").fetchone()[0]
        assert count == 0

    def test_missing_db_reported(self, tmp_path, world):
        auth, db_paths = world
        db_paths["nursery"] = tmp_path / "does_not_exist.db"
        res = backfill_identity_registry(db_paths=db_paths, auth_db=auth)
        assert res["nursery"]["db_missing"] == 1
