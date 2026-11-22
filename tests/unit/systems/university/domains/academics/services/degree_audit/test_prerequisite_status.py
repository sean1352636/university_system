"""Prerequisites added through the form count in the check, at the minimum grade."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.university.domains.progression.domain.degree_audit import progress


@pytest.fixture
def conn(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE modules (module_code TEXT, module_name TEXT, prerequisites TEXT);
        CREATE TABLE degree_course_prerequisites (
            module_code TEXT, prerequisite_module_code TEXT, min_grade TEXT,
            is_corequisite INTEGER DEFAULT 0);
        INSERT INTO modules VALUES ('M2', 'Second', 'M0'), ('M1', 'First module', NULL),
                                   ('M0', 'Foundation', NULL);
        INSERT INTO degree_course_prerequisites VALUES ('M2', 'M1', '2:1', 0), ('M2', 'CO', NULL, 1);
        """
    )
    yield db
    db.close()


def _taken(monkeypatch, **grades):
    rows = [{"module_code": code, "status": "Enrolled", "grade": grade, "earned": grade not in ("", "F")}
            for code, grade in grades.items()]
    monkeypatch.setattr(progress, "module_progress", lambda _c, _s: rows)


def test_both_stores_count_and_corequisites_do_not(conn):
    assert progress.declared_prerequisites(conn, "M2") == {"M0": "", "M1": "2:1"}


def test_met_at_or_above_the_minimum(conn, monkeypatch):
    _taken(monkeypatch, M0="Third", M1="First")
    assert all(p["met"] for p in progress.prerequisite_status(conn, "S1", "M2"))


def test_passed_below_the_minimum_is_not_met(conn, monkeypatch):
    _taken(monkeypatch, M0="Third", M1="2:2")
    by_code = {p["code"]: p for p in progress.prerequisite_status(conn, "S1", "M2")}
    assert by_code["M0"]["met"] and not by_code["M1"]["met"]


def test_not_taken_is_not_met(conn, monkeypatch):
    _taken(monkeypatch)
    rows = progress.prerequisite_status(conn, "S1", "M2")
    assert {p["status"] for p in rows} == {"Not taken"} and not any(p["met"] for p in rows)


@pytest.mark.parametrize("grade,minimum,expected", [
    ("First", "2:1", True), ("2:1", "2:1", True), ("2:2", "2:1", False), ("A", "2:1", True),
    ("B-", "2:1", True), ("C+", "2:1", False), ("Distinction", "Third", False), ("", "Third", False),
    ("anything", "", True),
])
def test_grade_meets_minimum(grade, minimum, expected):
    assert progress.grade_meets_minimum(grade, minimum) is expected
