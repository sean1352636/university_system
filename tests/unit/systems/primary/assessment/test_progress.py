"""Progress reviews and targets (domain.assessment.progress.progress)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.assessment.ks1_sats import ks1_sats as K1
from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats as K2
from education_system.systems.primary.domain.assessment.mtc import mtc as MTC
from education_system.systems.primary.domain.assessment.phonics_screening import (
    phonics_screening as PS,
)
from education_system.systems.primary.domain.assessment.progress import progress as PR
from education_system.systems.primary.domain.assessment.reading_levels import (
    reading_levels as RL,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.staff import staff as ST

YEAR = "2025-26"
TODAY = dt.date.today().isoformat()
_n = 0


def _pupil(year="4", first=None, last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": first or f"Pupil{_n}",
                           "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2016-03-01"})


def _staff():
    return ST.create_staff({"first_name": "Rita", "last_name": "Reviewer"})


def _review(pupil, **extra):
    data = {"student_id": pupil.pupil_id, "review_date": "2025-10-20",
            "period": "Autumn Half-Term 1", "academic_year": YEAR}
    data.update(extra)
    return PR.create_review(data)


def _target(review, **extra):
    data = {"description": "Learn 7x table"}
    data.update(extra)
    return PR.add_target(review.review_id, data)


# ── reviews: create / get ────────────────────────────────────────────

def test_create_review_defaults():
    p = _pupil()
    r = _review(p)
    assert (r.overall, r.attitude, r.homework) == ("2 — Good",) * 3
    assert (r.risk_level, r.status) == ("Low", "Draft")
    assert r.is_active and r.overall_score == 2
    assert r.shared_at is None and r.attendance_pct is None
    assert PR.get_review(r.review_id) == r


def test_create_review_stores_every_field():
    p = _pupil()
    s = _staff()
    r = _review(p, reviewer_staff_id=s.staff_id.lower(), overall="1 — Outstanding",
                attitude="3 — Requires Improvement", homework="4 — Inadequate",
                attendance_pct="96.47", risk_level="Medium", status="Published",
                academic_summary=" Strong ", behaviour_summary="Kind",
                next_steps="Fluency", notes="n")
    got = PR.get_review(r.review_id)
    assert got.reviewer_staff_id == s.staff_id
    assert (got.overall, got.attitude, got.homework) == (
        "1 — Outstanding", "3 — Requires Improvement", "4 — Inadequate")
    assert got.overall_score == 1
    assert got.attendance_pct == 96.5                    # rounded to 1 dp
    assert (got.risk_level, got.status) == ("Medium", "Published")
    assert (got.academic_summary, got.behaviour_summary, got.next_steps, got.notes) == (
        "Strong", "Kind", "Fluency", "n")


def test_review_date_and_period_default():
    p = _pupil()
    r = PR.create_review({"student_id": p.pupil_id})
    assert r.review_date == TODAY
    assert r.period == "Mid-Cycle Check" and r.academic_year is None


def test_get_review_unknown_is_none():
    assert PR.get_review(5) is None


@pytest.mark.parametrize("field, value, message", [
    ("student_id", "", "Student ID is required"),
    ("student_id", "P9999999", "No student with id P9999999"),
    ("review_date", "20/10/2025", "Review date must be YYYY-MM-DD"),
    ("period", "Half-Term 1", "Period must be one of"),
    ("reviewer_staff_id", "S9999", "No staff with id S9999"),
    ("overall", "Good", "Overall must be one of"),
    ("attitude", "5 — Awful", "Attitude must be one of"),
    ("homework", "x", "Homework must be one of"),
    ("attendance_pct", "lots", "Attendance % must be a number"),
    ("attendance_pct", 100.1, "Attendance % must be between 0 and 100"),
    ("attendance_pct", -1, "Attendance % must be between 0 and 100"),
    ("risk_level", "Severe", "Risk level must be one of"),
    ("status", "Final", "Status must be one of"),
])
def test_create_review_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(PR.ValidationError, match=message):
        _review(p, **{field: value})
    assert PR.list_reviews() == []


def test_one_review_per_pupil_period_and_year():
    p = _pupil()
    _review(p)
    with pytest.raises(PR.ValidationError, match="already has a review for Autumn Half-Term 1"):
        _review(p, review_date="2025-10-21")
    _review(p, academic_year="2026-27")
    _review(p, period="Autumn Half-Term 2")
    assert len(PR.reviews_for_student(p.pupil_id)) == 3


# ── reviews: update and lifecycle ────────────────────────────────────

def test_update_review_merges_fields_and_keeps_student():
    p, other = _pupil(), _pupil()
    r = _review(p, notes="keep")
    up = PR.update_review(r.review_id, {"overall": "3 — Requires Improvement",
                                        "risk_level": "High", "student_id": other.pupil_id})
    assert (up.overall, up.risk_level, up.notes) == ("3 — Requires Improvement", "High", "keep")
    assert up.student_id == p.pupil_id      # the pupil of a review never changes
    assert up.overall_score == 3


def test_update_review_refusals():
    p = _pupil()
    _review(p, period="Autumn Half-Term 1")
    r2 = _review(p, period="Autumn Half-Term 2")
    with pytest.raises(PR.ValidationError, match="No review #404"):
        PR.update_review(404, {})
    with pytest.raises(PR.ValidationError, match="Another review already exists"):
        PR.update_review(r2.review_id, {"period": "Autumn Half-Term 1"})
    with pytest.raises(PR.ValidationError, match="Risk level must be one of"):
        PR.update_review(r2.review_id, {"risk_level": "x"})
    assert PR.get_review(r2.review_id).period == "Autumn Half-Term 2"


def test_publish_then_share_stamps_shared_at_once():
    r = _review(_pupil())
    assert PR.publish(r.review_id).status == "Published"
    shared = PR.share(r.review_id)
    assert shared.status == "Shared" and shared.shared_at == TODAY
    # Sharing again (or editing) keeps the first stamp.
    again = PR.update_review(r.review_id, {"notes": "later"})
    assert again.shared_at == TODAY and again.status == "Shared"


def test_set_review_status_refuses_unknown():
    r = _review(_pupil())
    with pytest.raises(PR.ValidationError, match="Status must be one of"):
        PR.set_review_status(r.review_id, "Closed")


def test_archive_locks_the_review():
    r = _review(_pupil())
    a = PR.archive(r.review_id)
    assert a.status == "Archived" and not a.is_active
    with pytest.raises(PR.ValidationError, match="Cannot edit an Archived review"):
        PR.update_review(r.review_id, {"notes": "x"})
    with pytest.raises(PR.ValidationError, match="No review #999"):
        PR.archive(999)


def test_archived_review_can_be_unarchived():
    # update_review refuses edits with "un-archive first", so changing the
    # status back out of Archived must be possible.
    r = _review(_pupil())
    PR.archive(r.review_id)
    back = PR.set_review_status(r.review_id, "Published")
    assert back.status == "Published" and back.is_active


def test_only_drafts_can_be_deleted():
    p = _pupil()
    draft = _review(p)
    pub = _review(p, period="Spring Half-Term 1", status="Published")
    t = _target(draft)
    assert PR.delete_review(draft.review_id) is True
    assert PR.get_review(draft.review_id) is None
    assert PR.get_target(t.target_id) is None            # targets cascade
    assert PR.delete_review(draft.review_id) is False
    with pytest.raises(PR.ValidationError, match="Only Draft reviews can be deleted"):
        PR.delete_review(pub.review_id)


# ── reviews: listing and view ────────────────────────────────────────

def _seed_reviews():
    s = _staff()
    a, b = _pupil(), _pupil()
    r1 = _review(a, review_date="2025-10-01", period="Autumn Half-Term 1",
                 risk_level="High", reviewer_staff_id=s.staff_id)
    r2 = _review(a, review_date="2025-12-01", period="Autumn Half-Term 2", status="Published")
    r3 = _review(b, review_date="2025-12-01", period="Autumn Half-Term 2",
                 risk_level="Critical", academic_year="2026-27")
    r4 = _review(b, review_date="2025-09-01", period="End of Year", risk_level="High")
    PR.archive(r4.review_id)
    return s, a, b, (r1, r2, r3, r4)


def test_list_reviews_order_and_filters():
    s, a, b, (r1, r2, r3, r4) = _seed_reviews()

    def ids(**kw):
        return [r.review_id for r in PR.list_reviews(**kw)]

    assert ids() == [r3.review_id, r2.review_id, r1.review_id, r4.review_id]
    assert ids(student_id=a.pupil_id) == [r2.review_id, r1.review_id]
    assert ids(period="Autumn Half-Term 2") == [r3.review_id, r2.review_id]
    assert ids(academic_year="2026-27") == [r3.review_id]
    assert ids(status="Archived") == [r4.review_id]
    assert ids(risk_level="High") == [r1.review_id, r4.review_id]
    assert ids(reviewer_staff_id=s.staff_id.lower()) == [r1.review_id]
    assert ids(active_only=True) == [r3.review_id, r2.review_id, r1.review_id]


@pytest.mark.parametrize("kwargs, message", [
    ({"period": "Term 1"}, "Period must be one of"),
    ({"status": "Final"}, "Status must be one of"),
    ({"risk_level": "Huge"}, "Risk must be one of"),
])
def test_list_reviews_bad_filters(kwargs, message):
    with pytest.raises(PR.ValidationError, match=message):
        PR.list_reviews(**kwargs)


def test_view_review_joins_names_and_counts_targets():
    s = _staff()
    p = _pupil(first="Ada", last="Lovelace")
    r = _review(p, reviewer_staff_id=s.staff_id)
    _target(r)
    _target(r, status="At Risk")
    _target(r, status="Met", closed_on="2025-11-01")
    _target(r, status="Missed", closed_on="2025-11-01")
    v = PR.view_review(r.review_id)
    assert v.review == PR.get_review(r.review_id)
    assert v.student_name == "Ada Lovelace" and v.reviewer_name == s.full_name
    assert len(v.targets) == 4
    assert (v.open_targets, v.met_targets) == (2, 1)
    assert PR.view_review(999) is None


def test_view_review_without_reviewer():
    r = _review(_pupil())
    assert PR.view_review(r.review_id).reviewer_name is None


# ── targets ──────────────────────────────────────────────────────────

def test_add_target_defaults_and_fields():
    r = _review(_pupil())
    t = _target(r, area="Times Tables", measure=" 25/25 on MTC ", due_date="2026-01-31",
                progress_note="started")
    assert (t.review_id, t.area, t.description, t.measure) == (
        r.review_id, "Times Tables", "Learn 7x table", "25/25 on MTC")
    assert (t.due_date, t.status, t.progress_note, t.closed_on) == (
        "2026-01-31", "Open", "started", None)
    assert t.is_open
    assert PR.get_target(t.target_id) == t
    assert _target(r, description="x").area == "Academic"


@pytest.mark.parametrize("data, message", [
    ({"description": ""}, "Description is required"),
    ({"area": "Maths"}, "Area must be one of"),
    ({"due_date": "31/01/2026"}, "Due date must be YYYY-MM-DD"),
    ({"status": "Done"}, "Status must be one of"),
    ({"closed_on": "soon"}, "Closed on must be YYYY-MM-DD"),
])
def test_add_target_refuses_invalid(data, message):
    r = _review(_pupil())
    with pytest.raises(PR.ValidationError, match=message):
        _target(r, **data)
    assert PR.list_targets(review_id=r.review_id) == []


def test_add_target_to_unknown_review():
    with pytest.raises(PR.ValidationError, match="No review #321"):
        PR.add_target(321, {"description": "x"})


def test_closing_a_target_stamps_closed_on_and_reopening_clears_it():
    r = _review(_pupil())
    t = _target(r)
    met = PR.set_target_status(t.target_id, "Met")
    assert met.closed_on == TODAY and not met.is_open
    reopened = PR.set_target_status(t.target_id, "On Track")
    assert reopened.closed_on is None and reopened.is_open
    missed = PR.update_target(t.target_id, {"status": "Missed", "closed_on": "2025-12-20"})
    assert missed.closed_on == "2025-12-20"


def test_open_target_ignores_a_closed_on_date():
    t = _target(_review(_pupil()), status="Open", closed_on="2025-12-01")
    assert t.closed_on is None


def test_update_target_merges_and_refuses():
    t = _target(_review(_pupil()), measure="m")
    up = PR.update_target(t.target_id, {"progress_note": "halfway"})
    assert (up.progress_note, up.measure, up.description) == ("halfway", "m", "Learn 7x table")
    with pytest.raises(PR.ValidationError, match="No target #55"):
        PR.update_target(55, {})
    with pytest.raises(PR.ValidationError, match="Status must be one of"):
        PR.set_target_status(t.target_id, "Gone")


def test_delete_target():
    t = _target(_review(_pupil()))
    assert PR.delete_target(t.target_id) is True
    assert PR.delete_target(t.target_id) is False


def test_list_targets_filters_and_order():
    a, b = _pupil(), _pupil()
    ra, rb = _review(a), _review(b)
    t1 = _target(ra, due_date="2026-02-01", area="Reading")
    t2 = _target(ra, due_date="2025-11-01", status="Met")
    t3 = _target(rb, due_date="2025-12-01", status="At Risk")
    t4 = _target(rb)                                     # no due date

    def ids(**kw):
        return [t.target_id for t in PR.list_targets(**kw)]

    assert ids()[:3] == [t2.target_id, t3.target_id, t1.target_id]
    assert ids(review_id=ra.review_id) == [t2.target_id, t1.target_id]
    assert set(ids(student_id=b.pupil_id)) == {t3.target_id, t4.target_id}
    assert ids(status="Met") == [t2.target_id]
    assert ids(area="Reading") == [t1.target_id]
    assert set(ids(open_only=True)) == {t1.target_id, t3.target_id, t4.target_id}
    assert ids(due_before="2025-12-01") == [t2.target_id, t3.target_id]
    with pytest.raises(PR.ValidationError, match="Status must be one of"):
        PR.list_targets(status="x")
    with pytest.raises(PR.ValidationError, match="Area must be one of"):
        PR.list_targets(area="x")
    with pytest.raises(PR.ValidationError, match="due_before must be YYYY-MM-DD"):
        PR.list_targets(due_before="Dec")


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    s = PR.summary()
    assert (s.total_reviews, s.total_targets, s.students_at_high_risk) == (0, 0, 0)
    assert set(s.by_period.values()) == {0} and set(s.by_target_area.values()) == {0}


def test_summary_counts():
    _s, _a, _b, (r1, r2, r3, _r4) = _seed_reviews()
    _target(r1, due_date="2025-11-01")                         # open, overdue
    _target(r1, due_date="2026-03-01", area="Attendance")      # open, not yet due
    _target(r2, status="Met", due_date="2025-10-01")           # closed: never overdue
    _target(r3, status="Missed")
    _target(r3, status="At Risk")                              # open, no due date
    s = PR.summary(overdue_window_today="2025-12-15")
    assert s.total_reviews == 4
    assert (s.drafts, s.published, s.shared, s.archived) == (2, 1, 0, 1)
    assert s.by_period["Autumn Half-Term 2"] == 2 and s.by_period["End of Year"] == 1
    assert s.by_risk == {"Low": 1, "Medium": 0, "High": 2, "Critical": 1}
    assert s.by_overall["2 — Good"] == 4
    # Active (non-archived) reviews at High/Critical: r1 and r3, not the archived r4.
    assert s.students_at_high_risk == 2
    assert s.total_targets == 5
    assert (s.open_targets, s.met_targets, s.missed_targets) == (3, 1, 1)
    assert s.overdue_open_targets == 1
    assert s.by_target_area["Academic"] == 4 and s.by_target_area["Attendance"] == 1


# ── populate_from_data ───────────────────────────────────────────────

def test_populate_from_data_with_no_data():
    p = _pupil()
    out = PR.populate_from_data(p.pupil_id)
    assert out == {"attendance_pct": None}


def test_populate_from_data_builds_attainment_line():
    p = _pupil("6")
    RL.record_assessment(p.pupil_id, {"band": "Lime", "status": "secure",
                                      "assessed_on": "2025-10-01"})
    PS.create({"pupil_id": p.pupil_id, "academic_year": "2020-21", "attempt": 1, "score": 28})
    PS.create({"pupil_id": p.pupil_id, "academic_year": "2021-22", "attempt": 2, "score": 35})
    MTC.create({"pupil_id": p.pupil_id, "academic_year": "2023-24", "score": 22})
    K1.create({"pupil_id": p.pupil_id, "academic_year": "2021-22", "subject": "Reading",
               "outcome": "EXS"})
    K2.create({"pupil_id": p.pupil_id, "academic_year": "2024-25", "subject": "Reading",
               "outcome": "WTS"})
    K2.create({"pupil_id": p.pupil_id, "academic_year": YEAR, "subject": "Maths",
               "outcome": "GDS"})
    K2.create({"pupil_id": p.pupil_id, "academic_year": YEAR, "subject": "Reading",
               "outcome": "EXS"})
    out = PR.populate_from_data(p.pupil_id)
    assert out["attendance_pct"] is None
    assert out["academic_summary"] == " | ".join([
        "Reading: Lime (secure)",
        "Phonics check 2021-22: 35/40 (passed)",
        "MTC 2023-24: 22/25",
        "KS1 2021-22: Reading EXS",
        f"KS2 {YEAR}: Maths GDS, Reading EXS",
    ])
