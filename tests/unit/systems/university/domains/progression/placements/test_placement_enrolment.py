"""Placements may enrol a student, never create or overwrite one.

``students`` is the canonical person record shared across the whole system.
The placement tracker used to write it: ``add_student`` upserted names,
course and email (so saving over an existing id silently rewrote a real
student), and ``update_student`` cascade-renamed ``student_id`` across
``students``, ``placement_profiles`` and ``placement_hours_log``.

``save_placement`` replaces both and touches ``placement_profiles`` only.
These tests pin that boundary — the failure mode is silent data loss in a
table this module doesn't own, so it needs holding down.
"""

from __future__ import annotations

import pytest

from education_system.systems.university.domains.progression.domain.placements.placement_service import (  # noqa: E501
    REQUIRED_HOURS,
    Database,
)

_DB_PATH_ATTR = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Placement Database over an empty temp DB it bootstraps itself."""
    monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "placements.db"))
    database = Database()
    yield database
    database.close()


def _seed_student(db, student_id="S1", first="Ann", last="Smith",
                  course="CS", email="ann@x.test"):
    db.cursor.execute(
        "INSERT INTO students (student_id, first_name, last_name, course, "
        " email_address) VALUES (?, ?, ?, ?, ?)",
        (student_id, first, last, course, email),
    )
    db.conn.commit()


def _student_row(db, student_id="S1"):
    return db.cursor.execute(
        "SELECT student_id, first_name, last_name, course, email_address "
        "FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Enrolment
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_save_placement_creates_the_profile_only(db):
    _seed_student(db)
    before = tuple(_student_row(db))

    db.save_placement("S1", cohort="2026/27", employer="Acme",
                      supervisor="Pat", start_date="2026-09-01",
                      end_date="2027-06-30")

    profile = db.cursor.execute(
        "SELECT student_id, cohort, employer, supervisor, start_date, end_date "
        "FROM placement_profiles WHERE student_id = 'S1'").fetchone()
    assert tuple(profile) == ("S1", "2026/27", "Acme", "Pat",
                              "2026-09-01", "2027-06-30")
    # The person is untouched — this is the regression that matters.
    assert tuple(_student_row(db)) == before


@pytest.mark.unit
def test_save_placement_updates_in_place(db):
    _seed_student(db)
    db.save_placement("S1", employer="Acme")
    db.save_placement("S1", employer="Globex", cohort="2027/28")

    rows = db.cursor.execute(
        "SELECT employer, cohort FROM placement_profiles WHERE student_id='S1'"
    ).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == ("Globex", "2027/28")


@pytest.mark.unit
def test_a_placement_cannot_invent_a_person(db):
    with pytest.raises(ValueError) as excinfo:
        db.save_placement("GHOST-1", employer="Nowhere Ltd")

    assert "does not exist" in str(excinfo.value).lower() or "no student" in str(excinfo.value).lower()
    assert db.cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
    assert db.cursor.execute(
        "SELECT COUNT(*) FROM placement_profiles").fetchone()[0] == 0


@pytest.mark.unit
def test_save_placement_requires_a_student(db):
    with pytest.raises(ValueError):
        db.save_placement("")


@pytest.mark.unit
@pytest.mark.parametrize("method", ["add_student", "update_student"])
def test_person_mutators_are_gone(db, method):
    """``add_student`` upserted the canonical row; ``update_student`` renamed
    student_id across three tables. Neither belongs to placements."""
    assert not hasattr(db, method)


# ---------------------------------------------------------------------------
# Choosing who to enrol
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_enrollable_excludes_students_already_on_placement(db):
    _seed_student(db, "S1", "Ann", "Smith")
    _seed_student(db, "S2", "Bob", "Jones")
    db.save_placement("S1", employer="Acme")

    ids = {row[0] for row in db.list_enrollable_students()}
    assert ids == {"S2"}


@pytest.mark.unit
def test_enrollable_search_matches_id_name_and_course(db):
    _seed_student(db, "S1", "Ann", "Smith", course="Computer Science")
    _seed_student(db, "S2", "Bob", "Jones", course="Mathematics")

    assert {r[0] for r in db.list_enrollable_students("Smith")} == {"S1"}
    assert {r[0] for r in db.list_enrollable_students("Mathematics")} == {"S2"}
    assert {r[0] for r in db.list_enrollable_students("S2")} == {"S2"}
    assert db.list_enrollable_students("nomatch") == []


@pytest.mark.unit
def test_student_exists(db):
    _seed_student(db)
    assert db.student_exists("S1") is True
    assert db.student_exists("nope") is False


# ---------------------------------------------------------------------------
# Removal keeps the person
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_delete_removes_the_enrolment_not_the_student(db):
    _seed_student(db)
    db.save_placement("S1", employer="Acme")
    db.add_hours("S1", "2026-09-02", 7.5, "Induction", 1, None)

    db.delete_student("S1")

    assert db.cursor.execute(
        "SELECT COUNT(*) FROM placement_profiles").fetchone()[0] == 0
    assert db.cursor.execute(
        "SELECT COUNT(*) FROM placement_hours_log").fetchone()[0] == 0
    # The person survives — they are shared with the rest of the system.
    assert _student_row(db) is not None


@pytest.mark.unit
def test_required_hours_is_the_t_level_figure():
    assert REQUIRED_HOURS == 315
