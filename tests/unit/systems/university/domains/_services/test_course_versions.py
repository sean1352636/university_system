"""Unit tests for effective-dated course catalogue versions.

``course_history`` logs which field changed; it cannot answer "what were this
course's credits and outcomes in 2024/25?". These tests pin that question's
answer, the supersession that keeps exactly one version in force per date, and
the no-op behaviour when nothing has actually changed.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import course_versions as cv

_SCHEMA = """
CREATE TABLE courses (
    id TEXT PRIMARY KEY, code TEXT, course_code TEXT, name TEXT, course_name TEXT,
    description TEXT, department TEXT, level TEXT,
    credits INTEGER, credit_hours INTEGER, max_enrollment INTEGER,
    course_fee REAL, status TEXT DEFAULT 'active',
    current_enrollment INTEGER DEFAULT 0, updated_at TEXT
);
CREATE TABLE course_learning_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT, outcome_code TEXT, description TEXT
);
CREATE TABLE course_assessment_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT, name TEXT, weight REAL, notes TEXT
);
CREATE TABLE course_curriculum (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT, year INTEGER, module_code TEXT, module_name TEXT
);

INSERT INTO courses (id, code, course_code, name, course_name, description,
                     department, credit_hours, credits, max_enrollment)
VALUES ('CS','CS','CS','Computer Science','Computer Science','Three-year BSc',
        'Computing', 360, 360, 120);
INSERT INTO course_learning_outcomes (course_code, outcome_code, description)
VALUES ('CS','LO1','Design software'), ('CS','LO2','Reason about algorithms');
INSERT INTO course_assessment_components (course_code, name, weight)
VALUES ('CS','Coursework', 60.0), ('CS','Examination', 40.0);
INSERT INTO course_curriculum (course_code, year, module_code, module_name)
VALUES ('CS', 1, 'CS-Y1-1', 'Programming');
"""


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "versions.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        path,
    )
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return path


def _edit(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


@pytest.fixture()
def two_versions(db):
    cv.snapshot_course("CS", effective_from="2024-09-01", academic_year="2024/25",
                       change_reason="Baseline", created_by="registry")
    _edit(db, "UPDATE courses SET credit_hours = 480, course_name = 'Computer Science (rev)' "
              "WHERE id = 'CS'")
    cv.snapshot_course("CS", effective_from="2025-09-01", academic_year="2025/26",
                       change_reason="Credit uplift", created_by="registry")
    return db


class TestSnapshot:

    def test_first_snapshot_is_version_one(self, db):
        assert cv.snapshot_course("CS", effective_from="2024-09-01") == 1

    def test_unknown_course_records_nothing(self, db):
        assert cv.snapshot_course("NOPE") is None

    def test_identical_entry_does_not_create_a_version(self, db):
        cv.snapshot_course("CS", effective_from="2024-09-01")
        assert cv.snapshot_course("CS") is None

    def test_changed_entry_creates_the_next_version(self, db):
        cv.snapshot_course("CS", effective_from="2024-09-01")
        _edit(db, "UPDATE courses SET credit_hours = 480 WHERE id = 'CS'")
        assert cv.snapshot_course("CS", effective_from="2025-09-01") == 2

    def test_enrolment_counters_are_not_versioned(self, db):
        """A new enrolment must not look like a catalogue change."""
        cv.snapshot_course("CS", effective_from="2024-09-01")
        _edit(db, "UPDATE courses SET current_enrollment = 47 WHERE id = 'CS'")
        assert cv.snapshot_course("CS") is None

    def test_snapshot_captures_outcomes_and_components(self, db):
        cv.snapshot_course("CS", effective_from="2024-09-01")
        snapshot = cv.course_as_of("CS", when="2024-10-01")["snapshot"]
        assert [o["outcome_code"] for o in snapshot["learning_outcomes_detail"]] == \
            ["LO1", "LO2"]
        assert {c["name"] for c in snapshot["assessment_components"]} == \
            {"Coursework", "Examination"}
        assert snapshot["modules"] == ["CS-Y1-1"]

    def test_outcome_changes_alone_create_a_version(self, db):
        cv.snapshot_course("CS", effective_from="2024-09-01")
        _edit(db, "INSERT INTO course_learning_outcomes (course_code, outcome_code, "
                  "description) VALUES ('CS','LO3','Evaluate systems')")
        assert cv.snapshot_course("CS", effective_from="2025-09-01") == 2


class TestAsOf:

    def test_historic_date_returns_the_old_entry(self, two_versions):
        version = cv.course_as_of("CS", when="2024-11-01")
        assert version["version_no"] == 1
        assert version["snapshot"]["credit_hours"] == 360
        assert version["snapshot"]["course_name"] == "Computer Science"

    def test_current_date_returns_the_new_entry(self, two_versions):
        version = cv.course_as_of("CS", when="2026-01-01")
        assert version["version_no"] == 2
        assert version["snapshot"]["credit_hours"] == 480

    def test_lookup_by_academic_year(self, two_versions):
        assert cv.course_as_of("CS", academic_year="2024/25")["version_no"] == 1
        assert cv.course_as_of("CS", academic_year="2025/26")["version_no"] == 2

    def test_before_the_first_version_there_is_nothing(self, two_versions):
        assert cv.course_as_of("CS", when="2020-01-01") is None

    def test_unknown_course(self, db):
        assert cv.course_as_of("NOPE") is None

    def test_boundary_dates_belong_to_one_version_each(self, two_versions):
        assert cv.course_as_of("CS", when="2025-08-31")["version_no"] == 1
        assert cv.course_as_of("CS", when="2025-09-01")["version_no"] == 2


class TestSupersession:

    def test_previous_version_is_closed_the_day_before(self, two_versions):
        versions = {v["version_no"]: v for v in cv.list_versions("CS")}
        assert versions[1]["effective_to"] == "2025-08-31"
        assert versions[2]["effective_to"] is None

    def test_versions_are_listed_newest_first(self, two_versions):
        assert [v["version_no"] for v in cv.list_versions("CS")] == [2, 1]

    def test_metadata_is_kept(self, two_versions):
        latest = cv.list_versions("CS")[0]
        assert latest["change_reason"] == "Credit uplift"
        assert latest["created_by"] == "registry"


class TestDiff:

    def test_reports_only_what_changed(self, two_versions):
        changed = cv.diff_versions("CS", 1, 2)
        assert set(changed) == {"credit_hours", "course_name"}
        assert changed["credit_hours"] == {"from": 360, "to": 480}

    def test_unknown_version_yields_nothing(self, two_versions):
        assert cv.diff_versions("CS", 1, 99) == {}
