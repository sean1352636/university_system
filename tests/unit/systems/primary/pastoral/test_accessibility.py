"""Accessibility arrangements (domain.pastoral.accessibility.accessibility)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.accessibility import accessibility as AC

TODAY = dt.date.today()
PAST = (TODAY - dt.timedelta(days=10)).isoformat()
LONG_AGO = (TODAY - dt.timedelta(days=100)).isoformat()
FUTURE = (TODAY + dt.timedelta(days=30)).isoformat()


def _pupil(first="Ada", last="Lovelace", year="4"):
    return P.create_pupil({"first_name": first, "last_name": last,
                           "year_group": year, "date_of_birth": "2017-05-01"})


def _arr(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "category": "Extra time (25%)",
            "start_date": "2026-01-05"}
    data.update(extra)
    return AC.create(data)


def _active(pupil, **extra):
    return _arr(pupil, status="Active", approved_by="SENCo", **extra)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values_and_defaults():
    p = _pupil()
    a = _arr(p, description="  25% extra in tests ", evidence_source="EHCP",
             evidence_reference="EHCP-1", review_date="2026-07-01", notes="")
    assert a.arrangement_id > 0
    assert a.pupil_id == p.pupil_id
    assert a.arrangement_type == "Reasonable adjustment"
    assert a.category == "Extra time (25%)"
    assert a.description == "25% extra in tests"
    assert a.exam_only is False
    assert a.start_date == "2026-01-05"
    assert a.end_date is None
    assert a.status == "Proposed"
    assert a.evidence_source == "EHCP" and a.evidence_reference == "EHCP-1"
    assert a.review_date == "2026-07-01"
    assert a.notes is None
    assert a.pupil_name == "Ada Lovelace" and a.pupil_year == "4"


def test_exam_only_flag_and_free_text_category():
    a = _arr(_pupil(), exam_only=1, category="Bespoke seating plan")
    assert a.exam_only is True
    assert a.category == "Bespoke seating plan"


def test_start_date_defaults_to_today():
    assert _arr(_pupil(), start_date="").start_date == TODAY.isoformat()


def test_get_missing_is_none():
    P.init_db()  # the pupils table always exists in a real install
    assert AC.get(12345) is None


# ── validation ───────────────────────────────────────────────────────

def test_pupil_required_and_must_exist():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Pupil ID is required"):
        _arr(p, pupil_id="")
    with pytest.raises(AC.ValidationError, match="No pupil with id"):
        _arr(p, pupil_id="ZZZ")


def test_type_and_category_rules():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Arrangement type must be one of"):
        _arr(p, arrangement_type="Magic")
    with pytest.raises(AC.ValidationError, match="Category is required"):
        _arr(p, category="  ")
    with pytest.raises(AC.ValidationError, match="64 chars or fewer"):
        _arr(p, category="x" * 65)
    assert _arr(p, category="x" * 64).category == "x" * 64


def test_date_rules():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Start date must be YYYY-MM-DD"):
        _arr(p, start_date="5 Jan")
    with pytest.raises(AC.ValidationError, match="End date is not a real date"):
        _arr(p, end_date="2026-13-01")
    with pytest.raises(AC.ValidationError, match="End date cannot be before start date"):
        _arr(p, end_date="2026-01-04")
    with pytest.raises(AC.ValidationError, match="Review date must be"):
        _arr(p, review_date="later")
    with pytest.raises(AC.ValidationError, match="Approval date cannot be before start date"):
        _arr(p, approval_date="2026-01-01")


def test_status_and_evidence_lists():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Status must be one of"):
        _arr(p, status="Live")
    with pytest.raises(AC.ValidationError, match="Evidence source must be one of"):
        _arr(p, evidence_source="Rumour")


def test_active_needs_approver():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Approved by is required when status is Active"):
        _arr(p, status="Active")
    a = _active(p, approval_date="2026-01-10")
    assert a.status == "Active" and a.approved_by == "SENCo"
    assert a.approval_date == "2026-01-10"


# ── list / filters ───────────────────────────────────────────────────

def test_list_empty():
    P.init_db()
    assert AC.list_arrangements() == []


def test_list_sorted_newest_start_first():
    p = _pupil()
    a = _arr(p, start_date="2026-01-05")
    b = _arr(p, start_date="2026-03-01")
    c = _arr(p, start_date="2026-01-05")
    assert [r.arrangement_id for r in AC.list_arrangements()] == [
        b.arrangement_id, c.arrangement_id, a.arrangement_id]


def test_list_filters():
    p4, p6 = _pupil("Ada", "A", "4"), _pupil("Ben", "B", "6")
    a = _arr(p4, exam_only=True)
    b = _active(p6, arrangement_type="Physical access", category="Wheelchair access / ramp")
    ids = lambda rows: [r.arrangement_id for r in rows]  # noqa: E731
    assert ids(AC.list_arrangements(pupil_id=p4.pupil_id)) == [a.arrangement_id]
    assert ids(AC.list_arrangements(year_group="6")) == [b.arrangement_id]
    assert ids(AC.list_arrangements(arrangement_type="Physical access")) == [b.arrangement_id]
    assert ids(AC.list_arrangements(status="Proposed")) == [a.arrangement_id]
    assert ids(AC.list_arrangements(exam_only=True)) == [a.arrangement_id]
    assert ids(AC.list_arrangements(exam_only=False)) == [b.arrangement_id]
    assert ids(AC.list_arrangements(category="Wheelchair access / ramp")) == [b.arrangement_id]


def test_list_filter_validation():
    with pytest.raises(AC.ValidationError, match="Year filter"):
        AC.list_arrangements(year_group="9")
    with pytest.raises(AC.ValidationError, match="Type filter"):
        AC.list_arrangements(arrangement_type="Nope")
    with pytest.raises(AC.ValidationError, match="Status filter"):
        AC.list_arrangements(status="Nope")


# ── update / set_status / delete ────────────────────────────────────

def test_update_merges_fields():
    a = _arr(_pupil(), description="Original", exam_only=True)
    u = AC.update(a.arrangement_id, {"description": "Changed", "end_date": "2026-07-20"})
    assert u.description == "Changed"
    assert u.end_date == "2026-07-20"
    assert u.exam_only is True
    assert u.category == "Extra time (25%)"
    u2 = AC.update(a.arrangement_id, {"exam_only": False})
    assert u2.exam_only is False


def test_update_missing_and_invalid():
    P.init_db()
    with pytest.raises(AC.ValidationError, match="No accessibility arrangement #77"):
        AC.update(77, {"notes": "x"})
    a = _arr(_pupil())
    with pytest.raises(AC.ValidationError, match="End date cannot be before"):
        AC.update(a.arrangement_id, {"end_date": "2025-01-01"})
    assert AC.get(a.arrangement_id).end_date is None


def test_set_status_workflow():
    a = _arr(_pupil())
    with pytest.raises(AC.ValidationError, match="Approved by is required"):
        AC.set_status(a.arrangement_id, "Active")
    AC.update(a.arrangement_id, {"approved_by": "Head"})
    assert AC.set_status(a.arrangement_id, "Active").status == "Active"
    assert AC.set_status(a.arrangement_id, "Withdrawn").status == "Withdrawn"
    with pytest.raises(AC.ValidationError, match="Status must be one of"):
        AC.set_status(a.arrangement_id, "Gone")


def test_delete():
    a = _arr(_pupil())
    assert AC.delete(a.arrangement_id) is True
    assert AC.get(a.arrangement_id) is None
    assert AC.delete(a.arrangement_id) is False


# ── pupil_arrangements / expiry ─────────────────────────────────────

def test_pupil_arrangements_active_only():
    p, other = _pupil(), _pupil("Ben", "B")
    act = _active(p)
    _arr(p)
    _active(other)
    assert len(AC.pupil_arrangements(p.pupil_id)) == 2
    assert [r.arrangement_id for r in AC.pupil_arrangements(p.pupil_id, active_only=True)] == [
        act.arrangement_id]


def test_expired_property():
    p = _pupil()
    gone = _active(p, start_date=LONG_AGO, end_date=PAST)
    ongoing = _active(p, start_date=LONG_AGO, end_date=FUTURE)
    open_ended = _active(p, start_date=LONG_AGO)
    proposed_past = _arr(p, start_date=LONG_AGO, end_date=PAST)
    assert gone.expired is True
    assert ongoing.expired is False
    assert open_ended.expired is False
    assert proposed_past.expired is False  # only Active arrangements expire


def test_expired_arrangements_lists_only_lapsed_active():
    p = _pupil()
    gone = _active(p, start_date=LONG_AGO, end_date=PAST)
    _active(p, start_date=LONG_AGO, end_date=FUTURE)
    _arr(p, start_date=LONG_AGO, end_date=PAST)
    assert [r.arrangement_id for r in AC.expired_arrangements()] == [gone.arrangement_id]


# ── cohort_summary ───────────────────────────────────────────────────

def test_cohort_summary_empty():
    P.init_db()
    s = AC.cohort_summary()
    assert s == {"total": 0, "by_type": {}, "by_status": {}, "by_category": {},
                 "exam_only": 0, "active": 0, "expired_active": 0}


def test_cohort_summary_counts():
    p4, p6 = _pupil("Ada", "A", "4"), _pupil("Ben", "B", "6")
    _arr(p4, exam_only=True)
    _active(p4, start_date=LONG_AGO, end_date=PAST)
    _active(p6, arrangement_type="Sensory access", category="Large print", exam_only=True)
    s = AC.cohort_summary()
    assert s["total"] == 3
    assert s["by_type"] == {"Reasonable adjustment": 2, "Sensory access": 1}
    assert s["by_status"] == {"Proposed": 1, "Active": 2}
    assert s["by_category"] == {"Extra time (25%)": 2, "Large print": 1}
    assert s["exam_only"] == 2
    assert s["active"] == 2
    assert s["expired_active"] == 1
    y6 = AC.cohort_summary(year_group="6")
    assert y6["total"] == 1 and y6["by_category"] == {"Large print": 1}
