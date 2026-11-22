"""Appraisals (systems.primary.domain.staff.appraisals.appraisals)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.appraisals import appraisals as AP

TODAY = dt.date.today()
LONG_AGO = (TODAY - dt.timedelta(days=400)).isoformat()
RECENT = (TODAY - dt.timedelta(days=10)).isoformat()


def _staff(first="Amy", last="Adams", **extra):
    return S.create_staff({"first_name": first, "last_name": last, **extra})


def _appraisal(staff_id, cycle="2025-26", **extra):
    return AP.create_appraisal({"staff_id": staff_id, "cycle": cycle, **extra})


# ── Constants ────────────────────────────────────────────────────────

def test_grade_labels():
    assert [AP.grade_label(g) for g in AP.GRADES] == [
        "Outstanding", "Good", "Requires Improvement", "Unsatisfactory"]
    assert AP.grade_label(None) == "—"
    assert AP.grade_label(7) == "Unknown"


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    s = _staff()
    a = _appraisal(s.staff_id, job_role=" Teacher ", strengths=" planning ")
    assert (a.staff_id, a.cycle, a.status) == (s.staff_id, "2025-26", "Setting Objectives")
    assert (a.pay_progression, a.overall_grade) == ("Pending", None)
    assert (a.upholding_standards, a.self_review_completed) == (True, False)
    assert (a.job_role, a.strengths, a.appraiser_id) == ("Teacher", "planning", None)
    assert a.is_open is True and a.grade_label == "—"
    assert AP.get_appraisal(a.appraisal_id) == a
    assert AP.get_appraisal(999) is None


def test_create_with_appraiser_and_grade():
    head = _staff("Hana", "Head", role="Headteacher")
    s = _staff()
    a = _appraisal(s.staff_id, appraiser_id=head.staff_id, appraiser_name="Mrs Head",
                   overall_grade="2", pay_progression="Yes", upholding_standards=False,
                   self_review_completed=True)
    assert (a.appraiser_id, a.overall_grade, a.grade_label) == (head.staff_id, 2, "Good")
    assert (a.pay_progression, a.upholding_standards, a.self_review_completed) == \
        ("Yes", False, True)


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": " "}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"cycle": ""}, "Cycle is required"),
    ({"objectives_set_on": "01/09/2025"}, "Objectives set on must be YYYY-MM-DD"),
    ({"mid_year_review_on": "2026-02-30"}, "Mid-year review must be YYYY-MM-DD"),
    ({"end_year_review_on": "soon"}, "End-year review must be YYYY-MM-DD"),
    ({"status": "Done"}, "Status must be one of"),
    ({"overall_grade": 5}, "Grade must be 1-4"),
    ({"overall_grade": "good"}, "Grade must be 1-4"),
    ({"pay_progression": "Maybe"}, "Pay progression must be one of"),
    ({"appraiser_id": "T0000000"}, r"No staff with id T0000000 \(appraiser\)"),
])
def test_create_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, "cycle": "2025-26", **bad}
    with pytest.raises(AP.ValidationError, match=msg):
        AP.create_appraisal(data)
    assert AP.list_appraisals() == []


def test_one_appraisal_per_staff_per_cycle():
    s = _staff()
    _appraisal(s.staff_id)
    with pytest.raises(AP.ValidationError, match="already has an appraisal for cycle '2025-26'"):
        _appraisal(s.staff_id)
    assert _appraisal(s.staff_id, "2026-27").cycle == "2026-27"


# ── Update / delete ──────────────────────────────────────────────────

def test_update_and_uniqueness_excludes_self():
    s = _staff()
    a = _appraisal(s.staff_id)
    b = _appraisal(s.staff_id, "2026-27")
    data = {"staff_id": s.staff_id, "cycle": "2025-26", "notes": "fine"}
    assert AP.update_appraisal(a.appraisal_id, data).notes == "fine"
    with pytest.raises(AP.ValidationError, match="already has an appraisal"):
        AP.update_appraisal(b.appraisal_id, {"staff_id": s.staff_id, "cycle": "2025-26"})
    with pytest.raises(AP.ValidationError, match="No appraisal with id 999"):
        AP.update_appraisal(999, data)


def test_delete_cascades_objectives():
    s = _staff()
    a = _appraisal(s.staff_id)
    o = AP.add_objective(a.appraisal_id, {"title": "Phonics"})
    assert AP.delete_appraisal(a.appraisal_id) is True
    assert AP.get_appraisal(a.appraisal_id) is None
    assert AP.get_objective(o.objective_id) is None
    assert AP.delete_appraisal(a.appraisal_id) is False


def test_deleting_staff_cascades_appraisals():
    s = _staff()
    a = _appraisal(s.staff_id)
    S.delete_staff(s.staff_id)
    assert AP.get_appraisal(a.appraisal_id) is None


# ── Workflow ─────────────────────────────────────────────────────────

def test_set_objectives_moves_to_in_progress_once():
    s = _staff()
    a = _appraisal(s.staff_id)
    out = AP.set_objectives(a.appraisal_id, objectives_set_on="2025-09-15")
    assert (out.objectives_set_on, out.status) == ("2025-09-15", "In Progress")
    AP.set_appraisal_status(a.appraisal_id, "Mid-Year Review")
    again = AP.set_objectives(a.appraisal_id)
    assert (again.objectives_set_on, again.status) == (TODAY.isoformat(), "Mid-Year Review")


def test_mid_year_end_year_and_close():
    s = _staff()
    a = _appraisal(s.staff_id, objectives_set_on="2025-09-15")
    mid = AP.record_mid_year(a.appraisal_id, reviewed_on="2026-02-10")
    assert (mid.mid_year_review_on, mid.status) == ("2026-02-10", "Awaiting End Year")
    end = AP.record_end_year(a.appraisal_id, reviewed_on="2026-07-10", overall_grade=1,
                             pay_progression="Yes", upholding_standards=False,
                             strengths="Reading", areas_to_develop="Maths",
                             cpd_needs="Mastery", appraiser_comments="Great")
    assert (end.end_year_review_on, end.status, end.overall_grade) == \
        ("2026-07-10", "Completed", 1)
    assert (end.pay_progression, end.upholding_standards) == ("Yes", False)
    assert (end.strengths, end.areas_to_develop, end.cpd_needs, end.appraiser_comments) == \
        ("Reading", "Maths", "Mastery", "Great")
    assert end.is_open is True
    closed = AP.close_appraisal(a.appraisal_id)
    assert closed.status == "Closed" and closed.is_open is False
    assert closed.overall_grade == 1 and closed.mid_year_review_on == "2026-02-10"


def test_record_end_year_defaults_today_and_keeps_fields():
    s = _staff()
    a = _appraisal(s.staff_id, overall_grade=3, strengths="kept")
    end = AP.record_end_year(a.appraisal_id)
    assert (end.end_year_review_on, end.overall_grade, end.strengths) == \
        (TODAY.isoformat(), 3, "kept")
    with pytest.raises(AP.ValidationError, match="Grade must be 1-4"):
        AP.record_end_year(a.appraisal_id, overall_grade=0)


def test_workflow_refusals_for_missing_and_bad_status():
    for fn in (AP.set_objectives, AP.record_mid_year, AP.record_end_year, AP.close_appraisal):
        with pytest.raises(AP.ValidationError, match="No appraisal with id 404"):
            fn(404)
    with pytest.raises(AP.ValidationError, match="No appraisal with id 404"):
        AP.set_appraisal_status(404, "Closed")
    s = _staff()
    a = _appraisal(s.staff_id)
    with pytest.raises(AP.ValidationError, match="Status must be one of"):
        AP.set_appraisal_status(a.appraisal_id, "Finished")
    assert AP.set_appraisal_status(a.appraisal_id, "Archived").is_open is False


def test_mid_year_overdue_rule():
    s = _staff()
    old = _appraisal(s.staff_id, objectives_set_on=LONG_AGO)
    new = _appraisal(s.staff_id, "2026-27", objectives_set_on=RECENT)
    s2 = _staff("Ben", "Brown")
    done = _appraisal(s2.staff_id, objectives_set_on=LONG_AGO, mid_year_review_on=RECENT)
    closed = _appraisal(s2.staff_id, "2024-25", objectives_set_on=LONG_AGO, status="Closed")
    unset = _appraisal(s2.staff_id, "2023-24")
    assert old.mid_year_overdue is True
    assert new.mid_year_overdue is False
    assert done.mid_year_overdue is False
    assert closed.mid_year_overdue is False
    assert unset.mid_year_overdue is False
    assert [a.appraisal_id for a in AP.list_appraisals(mid_year_overdue=True)] == \
        [old.appraisal_id]


# ── Listing ──────────────────────────────────────────────────────────

def test_list_filters_order_and_cycles():
    assert AP.list_appraisals() == [] and AP.list_cycles() == []
    head = _staff("Hana", "Head", role="Headteacher")
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    a1 = _appraisal(a.staff_id, "2024-25", overall_grade=2, status="Closed")
    a2 = _appraisal(a.staff_id, "2025-26", appraiser_id=head.staff_id, pay_progression="Yes")
    b2 = _appraisal(b.staff_id, "2025-26", overall_grade=2)
    ids = lambda rows: {x.appraisal_id for x in rows}  # noqa: E731
    first = AP.list_appraisals()
    assert first[0].cycle == "2025-26" and first[-1].appraisal_id == a1.appraisal_id
    assert ids(AP.list_appraisals(staff_id=a.staff_id)) == {a1.appraisal_id, a2.appraisal_id}
    assert ids(AP.list_appraisals(cycle="2025-26")) == {a2.appraisal_id, b2.appraisal_id}
    assert ids(AP.list_appraisals(status="Closed")) == {a1.appraisal_id}
    assert ids(AP.list_appraisals(grade=2)) == {a1.appraisal_id, b2.appraisal_id}
    assert ids(AP.list_appraisals(pay_progression="Yes")) == {a2.appraisal_id}
    assert ids(AP.list_appraisals(open_only=True)) == {a2.appraisal_id, b2.appraisal_id}
    assert ids(AP.list_appraisals(appraiser_id=head.staff_id)) == {a2.appraisal_id}
    assert AP.list_cycles() == ["2025-26", "2024-25"]


# ── Objectives ───────────────────────────────────────────────────────

def test_objectives_numbered_in_order():
    s = _staff()
    a = _appraisal(s.staff_id)
    o1 = AP.add_objective(a.appraisal_id, {"title": " Phonics ", "weighting": "40",
                                           "reviewed_on": "2026-01-10"})
    o2 = AP.add_objective(a.appraisal_id, {"title": "Maths", "objective_type": "Leadership"})
    assert (o1.objective_number, o2.objective_number) == (1, 2)
    assert (o1.title, o1.objective_type, o1.status) == ("Phonics", "Pupil Outcomes",
                                                         "Not Started")
    assert (o1.weighting, o1.reviewed_on) == (40.0, "2026-01-10")
    assert o2.objective_type == "Leadership" and o2.weighting is None
    AP.delete_objective(o1.objective_id)
    o3 = AP.add_objective(a.appraisal_id, {"title": "Science"})
    assert o3.objective_number == 3
    assert [o.title for o in AP.list_objectives(a.appraisal_id)] == ["Maths", "Science"]
    assert AP.objective_count(a.appraisal_id) == 2
    assert AP.objective_count(999) == 0 and AP.list_objectives(999) == []


@pytest.mark.parametrize("bad, msg", [
    ({"title": " "}, "Objective title is required"),
    ({"objective_type": "Fun"}, "Objective type must be one of"),
    ({"status": "Done"}, "Objective status must be one of"),
    ({"reviewed_on": "10/01/2026"}, "Reviewed on must be YYYY-MM-DD"),
    ({"weighting": "lots"}, "Weighting must be a number"),
    ({"weighting": 101}, "Weighting must be 0-100"),
    ({"weighting": -1}, "Weighting must be 0-100"),
])
def test_objective_refusals(bad, msg):
    s = _staff()
    a = _appraisal(s.staff_id)
    with pytest.raises(AP.ValidationError, match=msg):
        AP.add_objective(a.appraisal_id, {"title": "Phonics", **bad})
    assert AP.objective_count(a.appraisal_id) == 0


def test_objective_needs_an_appraisal():
    with pytest.raises(AP.ValidationError, match="No appraisal with id 999"):
        AP.add_objective(999, {"title": "X"})


def test_update_objective_status_and_delete():
    s = _staff()
    a = _appraisal(s.staff_id)
    o = AP.add_objective(a.appraisal_id, {"title": "Phonics", "weighting": 50,
                                          "notes": "keep"})
    up = AP.update_objective(o.objective_id, {"title": "Phonics+", "status": "On Track"})
    assert (up.title, up.status, up.objective_number) == ("Phonics+", "On Track", 1)
    done = AP.set_objective_status(o.objective_id, "Achieved")
    assert done.status == "Achieved" and done.is_complete is True
    assert done.title == "Phonics+"
    assert AP.set_objective_status(o.objective_id, "At Risk").is_complete is False
    with pytest.raises(AP.ValidationError, match="Objective status must be one of"):
        AP.set_objective_status(o.objective_id, "Nope")
    with pytest.raises(AP.ValidationError, match="No objective with id 999"):
        AP.set_objective_status(999, "Achieved")
    with pytest.raises(AP.ValidationError, match="No objective with id 999"):
        AP.update_objective(999, {"title": "x"})
    assert AP.delete_objective(o.objective_id) is True
    assert AP.delete_objective(o.objective_id) is False


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = AP.summary()
    assert sm.total == 0 and sm.average_grade is None and sm.by_cycle == {}


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    x = _appraisal(a.staff_id, "2024-25", overall_grade=1, pay_progression="Yes",
                   status="Completed")
    _appraisal(a.staff_id, "2025-26", overall_grade=2, pay_progression="Deferred",
               objectives_set_on=LONG_AGO, upholding_standards=False)
    _appraisal(b.staff_id, "2025-26", status="Closed")
    AP.add_objective(x.appraisal_id, {"title": "1", "status": "Achieved"})
    AP.add_objective(x.appraisal_id, {"title": "2", "status": "Achieved"})
    AP.add_objective(x.appraisal_id, {"title": "3", "status": "At Risk"})
    sm = AP.summary()
    assert (sm.total, sm.open_count, sm.completed, sm.mid_year_overdue) == (3, 2, 1, 1)
    assert (sm.upholding_standards, sm.pay_progression_yes, sm.pay_progression_deferred) == \
        (2, 1, 1)
    assert (sm.total_objectives, sm.objectives_achieved, sm.distinct_cycles) == (3, 2, 2)
    assert sm.average_grade == 1.5                      # (1 + 2) / 2, ungraded ignored
    assert sm.by_cycle == {"2024-25": 1, "2025-26": 2}
    assert sm.by_status == {"Completed": 1, "Setting Objectives": 1, "Closed": 1}
    assert sm.by_grade == {1: 1, 2: 1}
    assert sm.by_pay_progression == {"Yes": 1, "Deferred": 1, "Pending": 1}
    assert sm.by_objective_status == {"Achieved": 2, "At Risk": 1}
