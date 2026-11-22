"""Homework assignments and submissions (domain.academics.homework.homework)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.homework import homework as HW
from education_system.systems.primary.domain.academics.subjects import subjects as S
from education_system.systems.primary.domain.learners.pupils import pupils as P

SET = "2025-09-08"
DUE = "2025-09-15"


def _subject(code="MATH", name="Maths"):
    return S.create({"code": code, "name": name, "key_stage": "All"})


def _assignment(subject=None, **extra):
    subject = subject or _subject()
    data = {"title": "Times tables", "subject_id": subject.subject_id, "year_group": "3",
            "set_date": SET, "due_date": DUE, **extra}
    return HW.create_assignment(data)


def _pupil(first="Ada", year="3", class_name="3 Maple"):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": year,
                           "class_name": class_name, "date_of_birth": "2018-01-01"})


# ── empty database ──

def test_empty_db():
    assert HW.list_assignments() == []
    assert HW.get_assignment(1) is None
    assert HW.get_submission(1) is None
    assert HW.list_submissions(1) == []
    assert HW.list_for_pupil("P0000001") == []
    assert HW.delete_assignment(1) is False
    assert HW.delete_submission(1) is False
    assert HW.assignment_status_counts() == {"Draft": 0, "Set": 0, "Closed": 0}


# ── assignments ──

def test_create_assignment_with_subject_join():
    a = _assignment(form_group=" 3 Maple ", set_by=" Mrs Oak ", points="10",
                    instructions=" pages 4-5 ", notes="")
    assert (a.title, a.year_group, a.form_group, a.set_by, a.set_date, a.due_date,
            a.points, a.status, a.instructions, a.notes) == (
        "Times tables", "3", "3 Maple", "Mrs Oak", SET, DUE, 10, "Draft", "pages 4-5", None)
    assert (a.subject_code, a.subject_name) == ("MATH", "Maths")
    assert HW.get_assignment(a.assignment_id) == a


def test_set_date_defaults_to_today():
    today = dt.date.today()
    a = _assignment(set_date=None, due_date=(today + dt.timedelta(days=7)).isoformat())
    assert a.set_date == today.isoformat()


def test_assignment_validation():
    sub = _subject()
    with pytest.raises(HW.ValidationError, match="Title is required"):
        _assignment(sub, title=" ")
    with pytest.raises(HW.ValidationError, match="120 characters"):
        _assignment(sub, title="x" * 121)
    with pytest.raises(HW.ValidationError, match="Subject is required"):
        _assignment(sub, subject_id=None)
    with pytest.raises(HW.ValidationError, match="Subject ID must be a number"):
        _assignment(sub, subject_id="maths")
    with pytest.raises(HW.ValidationError, match="No subject #999"):
        _assignment(sub, subject_id=999)
    with pytest.raises(HW.ValidationError, match="Year group is required"):
        _assignment(sub, year_group="")
    with pytest.raises(HW.ValidationError, match="Year group must be one of"):
        _assignment(sub, year_group="Y3")
    with pytest.raises(HW.ValidationError, match="Due date is required"):
        _assignment(sub, due_date="")
    with pytest.raises(HW.ValidationError, match="Due date is not a real date"):
        _assignment(sub, due_date="2025-09-31")
    with pytest.raises(HW.ValidationError, match="Due date cannot be before set date"):
        _assignment(sub, due_date="2025-09-07")
    with pytest.raises(HW.ValidationError, match="Points must be a whole number"):
        _assignment(sub, points="ten")
    with pytest.raises(HW.ValidationError, match="between 0 and 1000"):
        _assignment(sub, points=1001)
    with pytest.raises(HW.ValidationError, match="Status must be one of"):
        _assignment(sub, status="Open")
    assert HW.list_assignments() == []


def test_due_same_day_as_set_allowed():
    assert _assignment(due_date=SET).due_date == SET


def test_list_assignments_filters_and_order():
    maths, eng = _subject(), _subject("ENGL", "English")
    a = _assignment(maths, due_date="2025-09-10", set_by="Mrs Oak", status="Set")
    b = _assignment(eng, due_date="2025-09-20", year_group="4")
    c = _assignment(maths, due_date="2025-09-20", status="Closed")
    ids = lambda xs: [x.assignment_id for x in xs]  # noqa: E731
    assert ids(HW.list_assignments()) == [c.assignment_id, b.assignment_id,
                                          a.assignment_id]
    assert ids(HW.list_assignments(year_group="4")) == [b.assignment_id]
    assert ids(HW.list_assignments(subject_id=maths.subject_id)) == [c.assignment_id,
                                                                     a.assignment_id]
    assert ids(HW.list_assignments(status="Set")) == [a.assignment_id]
    assert ids(HW.list_assignments(teacher=" Mrs Oak ")) == [a.assignment_id]
    assert ids(HW.list_assignments(due_from="2025-09-15")) == [c.assignment_id,
                                                               b.assignment_id]
    assert ids(HW.list_assignments(due_to="2025-09-15")) == [a.assignment_id]
    with pytest.raises(HW.ValidationError, match="Year filter"):
        HW.list_assignments(year_group="7")
    with pytest.raises(HW.ValidationError, match="Status filter"):
        HW.list_assignments(status="Open")
    with pytest.raises(HW.ValidationError, match="From due date must be"):
        HW.list_assignments(due_from="next week")


def test_update_and_status():
    a = _assignment()
    out = HW.update_assignment(a.assignment_id, {"title": "Fractions", "points": 5})
    assert (out.title, out.points, out.due_date) == ("Fractions", 5, DUE)
    assert HW.set_assignment_status(a.assignment_id, "Set").status == "Set"
    assert HW.set_assignment_status(a.assignment_id, "Closed").status == "Closed"
    with pytest.raises(HW.ValidationError, match="Status must be one of"):
        HW.set_assignment_status(a.assignment_id, "Done")
    with pytest.raises(HW.ValidationError, match="cannot be before set date"):
        HW.update_assignment(a.assignment_id, {"set_date": "2025-09-20"})
    with pytest.raises(HW.ValidationError, match="No homework assignment #77"):
        HW.update_assignment(77, {})


def test_status_counts():
    sub = _subject()
    _assignment(sub)
    _assignment(sub, status="Set")
    _assignment(sub, status="Set")
    assert HW.assignment_status_counts() == {"Draft": 1, "Set": 2, "Closed": 0}


def test_delete_assignment_cascades_submissions():
    a = _assignment()
    pid = _pupil().pupil_id
    s = HW.upsert_submission(a.assignment_id, {"pupil_id": pid})
    assert HW.delete_assignment(a.assignment_id) is True
    assert HW.get_assignment(a.assignment_id) is None
    assert HW.get_submission(s.submission_id) is None


# ── submissions ──

def test_seed_submissions_for_year_group_is_idempotent():
    a = _assignment()
    p1, p2 = _pupil("Ada"), _pupil("Bea", class_name="3 Oak")
    _pupil("Cy", year="4", class_name="4 Elm")
    assert HW.seed_submissions(a.assignment_id) == 2
    subs = HW.list_submissions(a.assignment_id)
    assert sorted(s.pupil_id for s in subs) == sorted([p1.pupil_id, p2.pupil_id])
    assert {s.status for s in subs} == {"Pending"}
    assert HW.seed_submissions(a.assignment_id) == 0


def test_seed_submissions_skips_pupils_off_roll():
    a = _assignment()
    _pupil()
    P.create_pupil({"first_name": "Leaver", "last_name": "Test", "year_group": "3",
                    "date_of_birth": "2018-01-01"}, roll_status="left")
    assert HW.seed_submissions(a.assignment_id) == 1


def test_seed_submissions_for_one_class():
    """An assignment with a form group goes only to pupils in that class."""
    a = _assignment(form_group="3 Maple")
    maple = _pupil("Ada", class_name="3 Maple")
    _pupil("Bea", class_name="3 Oak")
    assert HW.seed_submissions(a.assignment_id) == 1
    assert [s.pupil_id for s in HW.list_submissions(a.assignment_id)] == [maple.pupil_id]


def test_seed_submissions_unknown_assignment():
    with pytest.raises(HW.ValidationError, match="No homework assignment #5"):
        HW.seed_submissions(5)


def test_upsert_submission_insert_then_update():
    a = _assignment()
    pid = _pupil().pupil_id
    s = HW.upsert_submission(a.assignment_id, {"pupil_id": pid,
                                               "submitted_date": "2025-09-14",
                                               "status": "Submitted"})
    assert (s.pupil_id, s.submitted_date, s.status, s.mark_pct) == (
        pid, "2025-09-14", "Submitted", None)
    g = HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "status": "Graded",
                                               "grade": " A ", "mark_pct": "85.5",
                                               "feedback": " Well done "})
    assert g.submission_id == s.submission_id
    assert (g.status, g.grade, g.mark_pct, g.feedback, g.submitted_date) == (
        "Graded", "A", 85.5, "Well done", None)
    assert len(HW.list_submissions(a.assignment_id)) == 1


def test_submission_validation():
    a = _assignment()
    pid = _pupil().pupil_id
    with pytest.raises(HW.ValidationError, match="No homework assignment #9"):
        HW.upsert_submission(9, {"pupil_id": pid})
    with pytest.raises(HW.ValidationError, match="Pupil ID is required"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": " "})
    with pytest.raises(HW.ValidationError, match="Submitted date must be YYYY-MM-DD"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "submitted_date": "x"})
    with pytest.raises(HW.ValidationError, match="Status must be one of"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "status": "Done"})
    with pytest.raises(HW.ValidationError, match="must be a number between 0 and 100"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "mark_pct": "high"})
    with pytest.raises(HW.ValidationError, match="Mark % must be between 0 and 100"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "mark_pct": 100.5})


def test_submission_for_unknown_pupil_refused():
    """Homework can only be recorded against a pupil who exists."""
    a = _assignment()
    with pytest.raises(HW.ValidationError, match="NOBODY"):
        HW.upsert_submission(a.assignment_id, {"pupil_id": "NOBODY"})


def test_list_for_pupil_and_status_filter():
    sub = _subject()
    a, b = _assignment(sub), _assignment(sub, title="Spellings")
    pid = _pupil().pupil_id
    HW.upsert_submission(a.assignment_id, {"pupil_id": pid, "status": "Missing"})
    HW.upsert_submission(b.assignment_id, {"pupil_id": pid, "status": "Submitted"})
    assert {s.assignment_id for s in HW.list_for_pupil(f" {pid} ")} == {
        a.assignment_id, b.assignment_id}
    assert [s.assignment_id for s in HW.list_for_pupil(pid, status="Missing")] == [
        a.assignment_id]
    with pytest.raises(HW.ValidationError, match="Pupil ID is required"):
        HW.list_for_pupil("")
    with pytest.raises(HW.ValidationError, match="Status filter"):
        HW.list_for_pupil(pid, status="Lost")


def test_delete_submission():
    a = _assignment()
    s = HW.upsert_submission(a.assignment_id, {"pupil_id": _pupil().pupil_id})
    assert HW.delete_submission(s.submission_id) is True
    assert HW.list_submissions(a.assignment_id) == []


def test_submission_summary():
    a = _assignment()
    pids = [_pupil(n).pupil_id for n in ("Ada", "Bea", "Cy", "Di")]
    HW.upsert_submission(a.assignment_id, {"pupil_id": pids[0], "status": "Graded",
                                           "mark_pct": 80})
    HW.upsert_submission(a.assignment_id, {"pupil_id": pids[1], "status": "Graded",
                                           "mark_pct": 65})
    HW.upsert_submission(a.assignment_id, {"pupil_id": pids[2], "status": "Late",
                                           "mark_pct": 50})
    HW.upsert_submission(a.assignment_id, {"pupil_id": pids[3], "status": "Missing"})
    s = HW.submission_summary(a.assignment_id)
    assert s["assignment"].assignment_id == a.assignment_id
    assert s["total"] == 4
    assert s["by_status"] == {"Pending": 0, "Submitted": 0, "Late": 1, "Missing": 1,
                              "Graded": 2, "Excused": 0}
    assert s["marked"] == 3
    assert s["avg_mark_pct"] == round((80 + 65 + 50) / 3, 2)    # 65.0


def test_submission_summary_no_marks():
    a = _assignment()
    s = HW.submission_summary(a.assignment_id)
    assert (s["total"], s["marked"], s["avg_mark_pct"]) == (0, 0, None)
    with pytest.raises(HW.ValidationError, match="No homework assignment #3"):
        HW.submission_summary(3)
