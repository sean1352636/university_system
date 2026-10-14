"""Learners who are already students here must not be offered "Admit from UCAS".

A sending system can open a fresh transition for a learner who has already
arrived — the sixth form's KS5 destination capture re-opened one for a learner
transferred weeks earlier. The ``completed``/``cancelled`` status filter cannot
see that, so the learner was listed as an applicant, and Admit could only fail
with "has no sixth-form record" because their sixth-form record was gone.

``list_all_applicants`` now leaves out anyone whose journey names a university
student that exists.
"""

import sqlite3

import pytest

from education_system.systems.university.domains.admissions.domain.ucas import (
    applicants as ap,
)


def _applicant(student_id, journey_id=None, *, source="sixth_form", route=None, ucas_id=None):
    return ap.Applicant(source_system=source, student_id=student_id,
                        student_name=f"Learner {student_id}",
                        route=route or ap.ROUTE_TRANSITION,
                        journey_id=journey_id, ucas_id=ucas_id)


@pytest.fixture()
def sources(monkeypatch):
    """Fixed transition and UCAS rows."""
    state = {"transitions": [], "ucas": []}
    monkeypatch.setattr(ap, "_from_transitions", lambda: list(state["transitions"]))
    monkeypatch.setattr(ap, "_from_ucas", lambda university_name=None: list(state["ucas"]))
    return state


def _names(rows):
    return sorted(a.student_id for a in rows)


def test_learner_already_enrolled_is_left_out(sources, monkeypatch):
    sources["transitions"] = [_applicant("C1", "journey-enrolled"),
                              _applicant("C2", "journey-applying")]
    monkeypatch.setattr(ap, "_journeys_with_university_students",
                        lambda ids: {"journey-enrolled"})
    assert _names(ap.list_all_applicants()) == ["C2"]


def test_ucas_row_that_inherits_the_journey_is_left_out_too(sources, monkeypatch):
    """The UCAS row wins the merge but takes the transition's journey id."""
    sources["transitions"] = [_applicant("C1", "journey-enrolled", ucas_id="123")]
    sources["ucas"] = [_applicant("C1", None, route="UCAS", ucas_id="123")]
    monkeypatch.setattr(ap, "_journeys_with_university_students",
                        lambda ids: {"journey-enrolled"})
    assert ap.list_all_applicants() == []


def test_applicants_without_a_journey_are_kept(sources, monkeypatch):
    sources["ucas"] = [_applicant("C3", None, route="UCAS")]
    called = []
    monkeypatch.setattr(ap, "_journeys_with_university_students",
                        lambda ids: called.append(ids) or set())
    assert _names(ap.list_all_applicants()) == ["C3"]
    assert called == []        # nothing to look up, no database opened


def test_an_outage_never_hides_applicants(sources, monkeypatch):
    sources["transitions"] = [_applicant("C1", "journey-1"), _applicant("C2", "journey-2")]

    def _boom(ids):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ap, "_journeys_with_university_students", _boom)
    assert _names(ap.list_all_applicants()) == ["C1", "C2"]


# ---------------------------------------------------------------------------
# the lookup itself, against temporary databases
# ---------------------------------------------------------------------------

@pytest.fixture()
def databases(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.db"
    uni_path = tmp_path / "student_records.db"
    with sqlite3.connect(auth_path) as conn:
        conn.execute("CREATE TABLE student_journey (journey_id TEXT PRIMARY KEY, "
                     "university_student_id TEXT)")
        conn.executemany("INSERT INTO student_journey VALUES (?, ?)", [
            ("journey-enrolled", "1635679"),
            ("journey-dangling", "9999999"),     # links a student that is gone
            ("journey-blank", "  "),
            ("journey-none", None),
        ])
    with sqlite3.connect(uni_path) as conn:
        conn.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO students VALUES ('1635679')")

    import education_system.platform.identity.auth.db as auth_db
    import education_system.systems.university.infrastructure.database.db as uni_db
    monkeypatch.setattr(auth_db, "connect", lambda db_path=None: sqlite3.connect(auth_path))
    monkeypatch.setattr(uni_db, "get_connection", lambda *a, **k: sqlite3.connect(uni_path))
    return auth_path, uni_path


def test_lookup_needs_a_link_and_an_existing_student(databases):
    found = ap._journeys_with_university_students(
        ["journey-enrolled", "journey-dangling", "journey-blank", "journey-none", "journey-unknown"])
    assert found == {"journey-enrolled"}


def test_lookup_with_no_linked_students_skips_the_university_database(databases, monkeypatch):
    import education_system.systems.university.infrastructure.database.db as uni_db

    def _must_not_open(*a, **k):
        raise AssertionError("the university database should not be opened")

    monkeypatch.setattr(uni_db, "get_connection", _must_not_open)
    assert ap._journeys_with_university_students(["journey-none", "journey-blank"]) == set()
