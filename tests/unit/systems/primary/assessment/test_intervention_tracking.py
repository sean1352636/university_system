"""Intervention tracking (domain.assessment.intervention_tracking.intervention_tracking)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as SB
from education_system.systems.primary.domain.assessment.intervention_tracking import (
    intervention_tracking as IT,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="3", last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2017-03-01"})


def _subject(code="MATH", name="Mathematics"):
    return SB.create({"code": code, "name": name, "key_stage": "All"})


def _iv(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "start_date": "2025-09-15"}
    data.update(extra)
    return IT.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_applies_defaults_and_joins_names():
    p = _pupil("4")
    iv = _iv(p)
    assert (iv.intervention_type, iv.status, iv.frequency) == ("Catch-up", "Planned", "Weekly")
    assert iv.subject_id is None and iv.subject_code is None
    assert iv.pupil_name == p.full_name and iv.pupil_year == "4"
    assert iv.end_date is None and iv.outcome is None
    assert IT.get(iv.intervention_id) == iv


def test_create_with_subject_and_all_fields():
    p = _pupil()
    s = _subject()
    iv = _iv(p, subject_id=str(s.subject_id), intervention_type="Small group",
             goal=" Number bonds to 20 ", end_date="2025-12-12", status="Active",
             led_by="Mrs TA", location="Library", frequency="Twice weekly",
             baseline_grade="WTS", target_grade="EXS", current_grade="WTS", notes="n")
    got = IT.get(iv.intervention_id)
    assert got.subject_id == s.subject_id
    assert (got.subject_code, got.subject_name) == ("MATH", "Mathematics")
    assert (got.intervention_type, got.goal, got.status, got.frequency) == (
        "Small group", "Number bonds to 20", "Active", "Twice weekly")
    assert (got.baseline_grade, got.target_grade, got.current_grade) == ("WTS", "EXS", "WTS")
    assert (got.led_by, got.location, got.end_date, got.notes) == (
        "Mrs TA", "Library", "2025-12-12", "n")


def test_missing_start_date_defaults_to_today():
    iv = IT.create({"pupil_id": _pupil().pupil_id})
    assert iv.start_date == dt.date.today().isoformat()


def test_get_unknown_is_none():
    _iv(_pupil())
    assert IT.get(9999) is None


def test_end_date_may_equal_start_date():
    assert _iv(_pupil(), end_date="2025-09-15").end_date == "2025-09-15"


@pytest.mark.parametrize("grade", ["4", "A*", "9+", "EXS", "b-"])
def test_grades_accept_short_codes(grade):
    assert _iv(_pupil(), target_grade=grade).target_grade == grade


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", "", "Pupil ID is required"),
    ("pupil_id", "P9999999", "No pupil with id"),
    ("subject_id", "maths", "Subject ID must be a number"),
    ("subject_id", 999, "No subject #999"),
    ("intervention_type", "Therapy", "Type must be one of"),
    ("start_date", "15/09/2025", "Start date must be YYYY-MM-DD"),
    ("start_date", "2025-02-29", "Start date is not a real date"),
    ("end_date", "2025-09-14", "End date cannot be before start date"),
    ("status", "Done", "Status must be one of"),
    ("frequency", "Hourly", "Frequency must be one of"),
    ("baseline_grade", "EXSS", "Baseline grade must be 1"),
    ("target_grade", "A B", "Target grade must be 1"),
    ("current_grade", "?", "Current grade must be 1"),
    ("outcome", "Great", "Outcome must be one of"),
])
def test_create_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _iv(p, **{field: value})


@pytest.mark.parametrize("status", ["Complete", "Cancelled"])
def test_closing_status_needs_outcome(status):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=f"Outcome is required when status is {status}"):
        _iv(p, status=status)
    assert _iv(p, status=status, outcome="Partial").outcome == "Partial"


# ── update / status / delete ─────────────────────────────────────────

def test_update_merges_and_validates():
    iv = _iv(_pupil(), goal="g1", led_by="A")
    up = IT.update(iv.intervention_id, {"current_grade": "EXS", "led_by": "B"})
    assert (up.current_grade, up.led_by, up.goal) == ("EXS", "B", "g1")
    with pytest.raises(P.ValidationError, match="End date cannot be before"):
        IT.update(iv.intervention_id, {"end_date": "2025-01-01"})
    assert IT.get(iv.intervention_id).end_date is None


def test_update_can_clear_subject():
    s = _subject()
    iv = _iv(_pupil(), subject_id=s.subject_id)
    assert IT.update(iv.intervention_id, {"subject_id": ""}).subject_id is None


def test_update_unknown_is_refused():
    with pytest.raises(P.ValidationError, match="No intervention #77"):
        IT.update(77, {"status": "Active"})


def test_set_status_with_and_without_outcome():
    iv = _iv(_pupil())
    assert IT.set_status(iv.intervention_id, "Active").status == "Active"
    assert IT.set_status(iv.intervention_id, "Paused").status == "Paused"
    with pytest.raises(P.ValidationError, match="Outcome is required"):
        IT.set_status(iv.intervention_id, "Complete")
    done = IT.set_status(iv.intervention_id, "Complete", outcome="Successful")
    assert (done.status, done.outcome) == ("Complete", "Successful")


def test_delete_cascades_reviews():
    iv = _iv(_pupil())
    rv = IT.add_review({"intervention_id": iv.intervention_id, "review_date": "2025-10-01"})
    assert IT.delete(iv.intervention_id) is True
    assert IT.get(iv.intervention_id) is None
    assert IT.get_review(rv.review_id) is None
    assert IT.delete(iv.intervention_id) is False


# ── reviews ──────────────────────────────────────────────────────────

def test_add_review_stores_values():
    iv = _iv(_pupil())
    rv = IT.add_review({"intervention_id": str(iv.intervention_id),
                        "review_date": "2025-10-01", "reviewer": " SENCO ",
                        "attendance_pct": "87.5", "on_track": False,
                        "progress_notes": "Slow", "next_action": "Add a session"})
    assert rv.intervention_id == iv.intervention_id
    assert (rv.review_date, rv.reviewer, rv.attendance_pct, rv.on_track) == (
        "2025-10-01", "SENCO", 87.5, False)
    assert (rv.progress_notes, rv.next_action) == ("Slow", "Add a session")
    assert IT.get_review(rv.review_id) == rv


def test_review_defaults():
    iv = _iv(_pupil())
    rv = IT.add_review({"intervention_id": iv.intervention_id})
    assert rv.on_track is True and rv.attendance_pct is None
    assert rv.review_date == dt.date.today().isoformat()


@pytest.mark.parametrize("data, message", [
    ({}, "Intervention ID is required"),
    ({"intervention_id": "x"}, "Intervention ID must be a number"),
    ({"intervention_id": 999}, "No intervention #999"),
    ({"attendance_pct": "most"}, "Attendance % must be a number"),
    ({"attendance_pct": -1}, "between 0 and 100"),
    ({"attendance_pct": 100.5}, "between 0 and 100"),
    ({"review_date": "1/10/2025"}, "Review date must be YYYY-MM-DD"),
])
def test_add_review_refuses_invalid(data, message):
    iv = _iv(_pupil())
    payload = {"intervention_id": iv.intervention_id, **data}
    if not data:
        payload = {}
    with pytest.raises(P.ValidationError, match=message):
        IT.add_review(payload)
    assert IT.list_reviews(iv.intervention_id) == []


def test_list_reviews_newest_first_and_delete():
    iv = _iv(_pupil())
    a = IT.add_review({"intervention_id": iv.intervention_id, "review_date": "2025-10-01"})
    b = IT.add_review({"intervention_id": iv.intervention_id, "review_date": "2025-11-01"})
    c = IT.add_review({"intervention_id": iv.intervention_id, "review_date": "2025-11-01"})
    assert [r.review_id for r in IT.list_reviews(iv.intervention_id)] == [
        c.review_id, b.review_id, a.review_id]
    assert IT.delete_review(b.review_id) is True
    assert IT.delete_review(b.review_id) is False
    assert [r.review_id for r in IT.list_reviews(iv.intervention_id)] == [
        c.review_id, a.review_id]
    assert IT.list_reviews(9999) == []


def test_intervention_summary():
    iv = _iv(_pupil())
    for date, att, on in (("2025-10-01", 80, True), ("2025-10-15", 95, False),
                          ("2025-11-01", None, True), ("2025-11-15", 90.5, True)):
        IT.add_review({"intervention_id": iv.intervention_id, "review_date": date,
                       "attendance_pct": att, "on_track": on})
    s = IT.intervention_summary(iv.intervention_id)
    assert s["intervention"].intervention_id == iv.intervention_id
    assert s["review_count"] == 4
    # (80 + 95 + 90.5) / 3 = 88.5 — a review with no attendance is ignored.
    assert s["avg_attendance"] == 88.5
    assert (s["on_track"], s["off_track"]) == (3, 1)


def test_intervention_summary_without_reviews_and_unknown():
    iv = _iv(_pupil())
    s = IT.intervention_summary(iv.intervention_id)
    assert (s["review_count"], s["avg_attendance"], s["on_track"], s["off_track"]) == (
        0, None, 0, 0)
    with pytest.raises(P.ValidationError, match="No intervention #404"):
        IT.intervention_summary(404)


# ── listing / cohort ─────────────────────────────────────────────────

def _seed():
    maths = _subject()
    y3, y5 = _pupil("3", last="Aaron"), _pupil("5", last="Brown")
    a = _iv(y3, status="Active", start_date="2025-09-01", subject_id=maths.subject_id)
    b = _iv(y3, status="Active", start_date="2025-10-01", intervention_type="Tutoring")
    c = _iv(y5, status="Complete", outcome="Successful", intervention_type="Tutoring")
    d = _iv(y5, status="Cancelled", outcome="Unsuccessful", intervention_type="Pastoral")
    e = _iv(y5)
    return maths, y3, y5, (a, b, c, d, e)


def test_list_interventions_ordering_and_filters():
    maths, y3, y5, (a, b, c, d, e) = _seed()
    ids = [i.intervention_id for i in IT.list_interventions()]
    # Ordered by status name, then newest start first.
    assert ids == [b.intervention_id, a.intervention_id, d.intervention_id,
                   c.intervention_id, e.intervention_id]
    assert {i.intervention_id for i in IT.list_interventions(year_group="3")} == {
        a.intervention_id, b.intervention_id}
    assert [i.intervention_id for i in IT.list_interventions(status="Planned")] == [
        e.intervention_id]
    assert {i.intervention_id for i in IT.list_interventions(intervention_type="Tutoring")} == {
        b.intervention_id, c.intervention_id}
    assert len(IT.list_interventions(pupil_id=y5.pupil_id)) == 3
    assert [i.intervention_id for i in IT.list_interventions(subject_id=maths.subject_id)] == [
        a.intervention_id]


@pytest.mark.parametrize("kwargs, message", [
    ({"year_group": "Y3"}, "Year filter"),
    ({"status": "Open"}, "Status filter"),
    ({"intervention_type": "x"}, "Type filter"),
])
def test_list_interventions_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        IT.list_interventions(**kwargs)


def test_cohort_summary():
    _seed()
    s = IT.cohort_summary()
    assert s["total"] == 5
    assert s["by_status"] == {"Active": 2, "Complete": 1, "Cancelled": 1, "Planned": 1}
    assert s["by_type"] == {"Catch-up": 2, "Tutoring": 2, "Pastoral": 1}
    assert s["by_outcome"] == {"Successful": 1, "Unsuccessful": 1}
    assert IT.cohort_summary(year_group="5")["total"] == 3


def test_empty_database():
    assert IT.list_interventions() == []
    assert IT.cohort_summary() == {"total": 0, "by_status": {}, "by_type": {},
                                   "by_outcome": {}}
