"""Tests for the cross-system journey-id backfill (Step 2).

The backfill module accepts a per-system DB path and the shared auth DB
path, so tests can exercise it against tiny synthetic DBs without
needing the full schema of any subsystem.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import identity_service as ids
from education_system.shared.cross_system import journey_backfill as bf


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def auth_db_path(tmp_path):
    p = str(tmp_path / "auth.db")
    initialise_auth_db(p)
    return p


def _make_int_pk_db(tmp_path, name: str, table: str, sid_col: str,
                    rows: list[dict]) -> str:
    """Create a minimal SQLite DB with a (id, sid, dob, first, last,
    journey_id) shape — matches the primary/school/college layout."""
    p = str(tmp_path / f"{name}.db")
    conn = sqlite3.connect(p)
    conn.execute(
        f"""CREATE TABLE {table} (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            {sid_col}     TEXT UNIQUE,
            date_of_birth TEXT,
            first_name    TEXT,
            last_name     TEXT,
            journey_id    TEXT
        )"""
    )
    for r in rows:
        conn.execute(
            f"INSERT INTO {table} ({sid_col}, date_of_birth, first_name, last_name) "
            "VALUES (?, ?, ?, ?)",
            (r[sid_col], r["date_of_birth"], r["first_name"], r["last_name"]),
        )
    conn.commit()
    conn.close()
    return p


def _make_uni_db(tmp_path, rows: list[dict]) -> str:
    """University layout: TEXT primary key (student_id), no integer pk,
    DOB column called ``dob`` not ``date_of_birth``."""
    p = str(tmp_path / "university.db")
    conn = sqlite3.connect(p)
    conn.execute(
        """CREATE TABLE students (
            student_id    TEXT PRIMARY KEY,
            dob           TEXT,
            first_name    TEXT,
            last_name     TEXT,
            journey_id    TEXT
        )"""
    )
    for r in rows:
        conn.execute(
            "INSERT INTO students (student_id, dob, first_name, last_name) "
            "VALUES (?, ?, ?, ?)",
            (r["student_id"], r["dob"], r["first_name"], r["last_name"]),
        )
    conn.commit()
    conn.close()
    return p


def _read_journey_ids(db_path: str, table: str, sid_col: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {r[sid_col]: r["journey_id"] for r in conn.execute(
            f"SELECT {sid_col}, journey_id FROM {table}").fetchall()}
    finally:
        conn.close()


# ── attach_system_record signature change (pk now optional) ──────────────

class TestAttachSystemRecordOptionalPk:
    def test_student_id_only_attaches(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="Una", last_name="Persson", date_of_birth="2002-02-02",
            current_system="university", db_path=auth_db_path,
        )
        ids.attach_system_record(
            jid, "university", student_id="C1234567", db_path=auth_db_path,
        )
        row = ids.get_journey(jid, db_path=auth_db_path)
        assert row["university_pk"] is None
        assert row["university_student_id"] == "C1234567"

    def test_neither_pk_nor_student_id_rejected(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="V", last_name="W", date_of_birth="2000-01-01",
            current_system="college", db_path=auth_db_path,
        )
        with pytest.raises(ids.IdentityError):
            ids.attach_system_record(jid, "college", db_path=auth_db_path)

    def test_conflicting_student_id_raises(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="Wally", last_name="West", date_of_birth="2001-01-01",
            current_system="university", db_path=auth_db_path,
        )
        ids.attach_system_record(jid, "university", student_id="C0000001",
                                 db_path=auth_db_path)
        with pytest.raises(ids.IdentityError):
            ids.attach_system_record(jid, "university", student_id="C0000002",
                                      db_path=auth_db_path)


# ── Single-system backfill ───────────────────────────────────────────────

class TestBackfillSystem:
    def test_college_rows_get_linked_with_new_journeys(self, tmp_path, auth_db_path):
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {"student_id": "SFC0001", "date_of_birth": "2007-01-01",
             "first_name": "Alice",   "last_name": "Anderson"},
            {"student_id": "SFC0002", "date_of_birth": "2007-02-02",
             "first_name": "Bob",     "last_name": "Brown"},
        ])
        report = bf.backfill_system(
            "college", college_db, auth_db_path=auth_db_path)
        assert report.examined == 2
        assert report.linked_new_journey == 2
        assert report.linked_existing_journey == 0
        assert report.skipped_no_match_keys == 0
        assert report.errors == []

        ids_map = _read_journey_ids(college_db, "students", "student_id")
        assert all(v for v in ids_map.values())

        # Both journeys exist and are attached to the right college pks.
        for sid in ("SFC0001", "SFC0002"):
            j = ids.find_journey_by_student_id("college", sid,
                                                 db_path=auth_db_path)
            assert j is not None
            assert j["journey_id"] == ids_map[sid]
            assert j["college_student_id"] == sid

    def test_skips_rows_already_linked(self, tmp_path, auth_db_path):
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {"student_id": "SFC0010", "date_of_birth": "2007-03-03",
             "first_name": "Carol",   "last_name": "Chen"},
        ])
        first = bf.backfill_system("college", college_db,
                                    auth_db_path=auth_db_path)
        assert first.linked_new_journey == 1
        # Re-running should be a no-op.
        second = bf.backfill_system("college", college_db,
                                     auth_db_path=auth_db_path)
        assert second.examined == 0
        assert second.linked_new_journey == 0
        assert second.linked_existing_journey == 0

    def test_missing_keys_are_skipped_not_failed(self, tmp_path, auth_db_path):
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {"student_id": "SFC0020", "date_of_birth": "",
             "first_name": "Empty",   "last_name": "DOB"},
            {"student_id": "SFC0021", "date_of_birth": "2007-04-04",
             "first_name": "",        "last_name": "NoFirst"},
            {"student_id": "SFC0022", "date_of_birth": "2007-05-05",
             "first_name": "Ok",      "last_name": "Row"},
        ])
        report = bf.backfill_system("college", college_db,
                                     auth_db_path=auth_db_path)
        assert report.examined == 3
        assert report.skipped_no_match_keys == 2
        assert report.linked_new_journey == 1
        assert report.errors == []

    def test_dry_run_writes_nothing(self, tmp_path, auth_db_path):
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {"student_id": "SFC0030", "date_of_birth": "2007-06-06",
             "first_name": "Dry",     "last_name": "Run"},
        ])
        report = bf.backfill_system(
            "college", college_db, auth_db_path=auth_db_path, dry_run=True)
        assert report.linked_new_journey == 1
        # Nothing was written to the system DB...
        ids_map = _read_journey_ids(college_db, "students", "student_id")
        assert ids_map["SFC0030"] is None
        # ...nor to the shared journey table.
        assert ids.find_journey_by_student_id(
            "college", "SFC0030", db_path=auth_db_path) is None

    def test_university_uses_student_id_only(self, tmp_path, auth_db_path):
        uni_db = _make_uni_db(tmp_path, [
            {"student_id": "C1000001", "dob": "2003-09-09",
             "first_name": "Ed", "last_name": "Ellsberg"},
        ])
        report = bf.backfill_system("university", uni_db,
                                     auth_db_path=auth_db_path)
        assert report.linked_new_journey == 1
        j = ids.find_journey_by_student_id("university", "C1000001",
                                            db_path=auth_db_path)
        assert j is not None
        assert j["university_pk"] is None     # uni doesn't store pk
        assert j["university_student_id"] == "C1000001"

    def test_missing_journey_id_column_errors(self, tmp_path, auth_db_path):
        # Build a college-shaped DB without the journey_id column.
        p = str(tmp_path / "college.db")
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE students (id INTEGER PRIMARY KEY, "
            "student_id TEXT, date_of_birth TEXT, first_name TEXT, "
            "last_name TEXT)"
        )
        conn.commit()
        conn.close()
        with pytest.raises(RuntimeError, match="journey_id column missing"):
            bf.backfill_system("college", p, auth_db_path=auth_db_path)


# ── Cross-system journey reuse ───────────────────────────────────────────

class TestBackfillReusesExistingJourney:
    def test_same_student_in_school_and_college_shares_one_journey(
        self, tmp_path, auth_db_path,
    ):
        # Same identity in two systems.
        person = dict(date_of_birth="2007-07-07",
                      first_name="Gina", last_name="Greene")
        school_db = _make_int_pk_db(tmp_path, "school", "students", "student_id", [
            {**person, "student_id": "SCH0010"},
        ])
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {**person, "student_id": "SFC0050"},
        ])
        rs = bf.backfill_system("school", school_db, auth_db_path=auth_db_path)
        rc = bf.backfill_system("college", college_db, auth_db_path=auth_db_path)

        assert rs.linked_new_journey == 1
        assert rc.linked_existing_journey == 1   # shared the school journey
        assert rc.linked_new_journey == 0

        s_jid = _read_journey_ids(school_db, "students", "student_id")["SCH0010"]
        c_jid = _read_journey_ids(college_db, "students", "student_id")["SFC0050"]
        assert s_jid == c_jid  # same journey
        j = ids.get_journey(s_jid, db_path=auth_db_path)
        assert j["school_student_id"] == "SCH0010"
        assert j["college_student_id"] == "SFC0050"


# ── backfill_all wrapper ─────────────────────────────────────────────────

class TestBackfillAll:
    def test_runs_only_for_given_paths(self, tmp_path, auth_db_path):
        college_db = _make_int_pk_db(tmp_path, "college", "students", "student_id", [
            {"student_id": "SFC0099", "date_of_birth": "2007-08-08",
             "first_name": "Hal", "last_name": "Hill"},
        ])
        out = bf.backfill_all(college_db=college_db, auth_db_path=auth_db_path)
        assert set(out.keys()) == {"college"}
        assert out["college"].linked_new_journey == 1
