"""Unit tests for the enrolment eligibility gate (``services.bus.enrolment_bus``).

The gate is the single place the three registration paths — the student
registration GUI, the course catalogue GUI and the REST route — consult before
writing to ``student_modules``. Before it existed, ``course_prerequisites`` was
advisory and the capacity check on the GUI path was dead code.

The fixture repoints ``DEFAULT_DB_PATH`` at a temp file and seeds only the
tables the gate reads, following the ``test_commerce_bus`` pattern; no test
here touches the live database.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import enrolment_bus
from education_system.systems.university.services.bus.enrolment_bus import (
    BLOCK_CAPACITY,
    BLOCK_COREQUISITE,
    BLOCK_PREREQUISITE,
    check_enrolment_eligibility,
)

_SCHEMA = """
CREATE TABLE modules (
    module_code TEXT PRIMARY KEY, module_name TEXT, capacity INTEGER
);
CREATE TABLE student_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT, module_code TEXT, status TEXT, enrollment_date TEXT
);
CREATE TABLE course_prerequisites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_code TEXT, prerequisite_module_code TEXT,
    is_required INTEGER DEFAULT 1, is_corequisite INTEGER DEFAULT 0,
    can_be_concurrent INTEGER DEFAULT 0, min_grade TEXT
);
CREATE TABLE module_grades (
    student_id TEXT, module_code TEXT, final_grade TEXT
);
CREATE TABLE student_grades (
    student_id TEXT, module_code TEXT, grade TEXT, is_final INTEGER DEFAULT 1
);
INSERT INTO modules (module_code, module_name) VALUES
    ('CS201', 'Algorithms'), ('CS101', 'Intro'), ('CS150', 'Discrete Maths');
"""

STUDENT = "S1"
TARGET = "CS201"
PREREQ = "CS101"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "enrolment.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        path,
    )
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return path


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _add_rule(db_path, module, prereq, **cols):
    fields = {"module_code": module, "prerequisite_module_code": prereq, **cols}
    names = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    _exec(db_path, f"INSERT INTO course_prerequisites ({names}) VALUES ({marks})",
          tuple(fields.values()))


def _enrol(db_path, student, module, status="Enrolled"):
    _exec(db_path, "INSERT INTO student_modules (student_id, module_code, status, "
                   "enrollment_date) VALUES (?,?,?, '2026-01-01')",
          (student, module, status))


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

class TestPrerequisites:

    def test_no_rules_is_eligible(self, db):
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert result.ok
        assert result.blocks == []

    def test_unmet_prerequisite_blocks(self, db):
        _add_rule(db, TARGET, PREREQ)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert not result.ok
        assert result.blocks[0].kind == BLOCK_PREREQUISITE
        assert PREREQ in result.reason()
        # Not a waitlist case: a queue would not fix a missing prerequisite.
        assert not result.only_capacity

    def test_passing_grade_satisfies(self, db):
        _add_rule(db, TARGET, PREREQ)
        _exec(db, "INSERT INTO module_grades (student_id, module_code, final_grade) "
                  "VALUES (?,?,'B')", (STUDENT, PREREQ))
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_fail_grade_does_not_satisfy(self, db):
        _add_rule(db, TARGET, PREREQ)
        _exec(db, "INSERT INTO module_grades (student_id, module_code, final_grade) "
                  "VALUES (?,?,'F')", (STUDENT, PREREQ))
        assert not check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_student_grades_table_also_counts(self, db):
        _add_rule(db, TARGET, PREREQ)
        _exec(db, "INSERT INTO student_grades (student_id, module_code, grade, is_final) "
                  "VALUES (?,?,'A',1)", (STUDENT, PREREQ))
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_optional_rule_never_blocks(self, db):
        _add_rule(db, TARGET, PREREQ, is_required=0)
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_being_enrolled_does_not_satisfy_a_prerequisite(self, db):
        """A prerequisite needs a *pass*, not concurrent attendance."""
        _add_rule(db, TARGET, PREREQ)
        _enrol(db, STUDENT, PREREQ)
        assert not check_enrolment_eligibility(STUDENT, TARGET).ok


# ---------------------------------------------------------------------------
# Co-requisites
# ---------------------------------------------------------------------------

class TestCorequisites:

    def test_missing_corequisite_blocks(self, db):
        _add_rule(db, TARGET, PREREQ, is_corequisite=1)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert not result.ok
        assert result.blocks[0].kind == BLOCK_COREQUISITE

    def test_concurrent_enrolment_satisfies(self, db):
        _add_rule(db, TARGET, PREREQ, is_corequisite=1)
        _enrol(db, STUDENT, PREREQ)
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_can_be_concurrent_flag_behaves_the_same(self, db):
        _add_rule(db, TARGET, PREREQ, can_be_concurrent=1)
        _enrol(db, STUDENT, PREREQ)
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_dropped_module_does_not_satisfy(self, db):
        _add_rule(db, TARGET, PREREQ, is_corequisite=1)
        _enrol(db, STUDENT, PREREQ, status="Dropped")
        assert not check_enrolment_eligibility(STUDENT, TARGET).ok


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------

class TestCapacity:

    def test_null_capacity_is_uncapped(self, db):
        for i in range(5):
            _enrol(db, f"S{i + 10}", TARGET)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert result.ok
        assert result.capacity is None

    def test_zero_capacity_is_uncapped(self, db):
        """0 means "no limit set", matching the seeded data's intent."""
        _exec(db, "UPDATE modules SET capacity = 0 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET)
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_seat_available(self, db):
        _exec(db, "UPDATE modules SET capacity = 2 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert result.ok
        assert (result.capacity, result.enrolled) == (2, 1)

    def test_full_module_blocks(self, db):
        _exec(db, "UPDATE modules SET capacity = 1 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert not result.ok
        assert result.blocks[0].kind == BLOCK_CAPACITY
        assert result.is_full
        # Capacity alone -> the caller may offer the waitlist.
        assert result.only_capacity

    def test_dropped_rows_free_their_seat(self, db):
        _exec(db, "UPDATE modules SET capacity = 1 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET, status="Dropped")
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_own_seat_does_not_block_re_enrolment(self, db):
        """A returning student must not be refused against their own place."""
        _exec(db, "UPDATE modules SET capacity = 2 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET)
        _enrol(db, STUDENT, TARGET)
        assert check_enrolment_eligibility(STUDENT, TARGET).ok


# ---------------------------------------------------------------------------
# Combined verdicts and failure behaviour
# ---------------------------------------------------------------------------

class TestVerdict:

    def test_prerequisite_and_capacity_both_reported(self, db):
        _exec(db, "UPDATE modules SET capacity = 1 WHERE module_code = ?", (TARGET,))
        _enrol(db, "S99", TARGET)
        _add_rule(db, TARGET, PREREQ)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        kinds = {b.kind for b in result.blocks}
        assert kinds == {BLOCK_PREREQUISITE, BLOCK_CAPACITY}
        # A waitlist would not help while a prerequisite is outstanding.
        assert not result.only_capacity
        assert PREREQ in result.reason() and "full" in result.reason()

    def test_to_dict_round_trip(self, db):
        _add_rule(db, TARGET, PREREQ)
        payload = check_enrolment_eligibility(STUDENT, TARGET).to_dict()
        assert payload["ok"] is False
        assert payload["blocks"][0]["kind"] == BLOCK_PREREQUISITE
        assert payload["blocks"][0]["details"]["missing"][0]["code"] == PREREQ

    def test_blank_arguments_are_eligible(self, db):
        assert check_enrolment_eligibility("", TARGET).ok
        assert check_enrolment_eligibility(STUDENT, "").ok

    def test_missing_prerequisites_table_does_not_block(self, db):
        """A schema outage must not lock every student out of registration."""
        _exec(db, "DROP TABLE course_prerequisites")
        assert check_enrolment_eligibility(STUDENT, TARGET).ok

    def test_broken_connection_degrades_open(self, db, monkeypatch):
        def boom(*_a, **_kw):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(enrolment_bus, "get_connection", boom)
        result = check_enrolment_eligibility(STUDENT, TARGET)
        assert result.ok
        assert result.degraded
        assert result.blocks == []

    def test_caller_supplied_connection_is_not_closed(self, db):
        """The route runs the gate inside its own open read connection."""
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        check_enrolment_eligibility(STUDENT, TARGET, conn=conn)
        conn.execute("SELECT 1").fetchone()  # would raise if the gate closed it
        conn.close()
