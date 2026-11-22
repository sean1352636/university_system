"""Pupils bridge (domain._pupils_bridge): pupils seen as ``student_id`` rows."""

from __future__ import annotations

from education_system.systems.primary.domain import _pupils_bridge as B
from education_system.systems.primary.domain.learners.pupils import pupils as P


def _pupil(first="Ada", last="Lovelace", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year})


def test_empty_roll_lists_no_students():
    B.init_db()
    assert B.list_students() == []


def test_get_student_wraps_the_pupil():
    made = _pupil()
    got = B.get_student(made.pupil_id)
    assert got == B.StudentLike(student_id=made.pupil_id, first_name="Ada",
                                last_name="Lovelace")
    assert got.full_name == "Ada Lovelace"


def test_get_unknown_student_is_none():
    assert B.get_student("P0000000") is None


def test_list_students_follows_the_roll_order_and_hides_off_roll():
    b = _pupil("Bea", "Brown", "2")
    a = _pupil("Al", "Adams", "1")
    gone = _pupil("Gus", "Gone", "1")
    P.set_roll_status(gone.pupil_id, "left")
    P.create_pupil({"first_name": "App", "last_name": "Licant", "year_group": "R"},
                   roll_status="applicant")
    assert [s.student_id for s in B.list_students()] == [a.pupil_id, b.pupil_id]


def test_full_name_trims_a_missing_part():
    assert B.StudentLike("P1", "Ada", "").full_name == "Ada"
