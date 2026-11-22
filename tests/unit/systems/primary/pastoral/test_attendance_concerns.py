"""Attendance-concern cases (domain.pastoral.attendance_concerns.attendance_concerns)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.attendance_concerns import (
    attendance_concerns as AC,
)

TODAY = dt.date.today().isoformat()


def _pupil(first="Ada", last="Lovelace", year="2"):
    return P.create_pupil({"first_name": first, "last_name": last,
                           "year_group": year, "date_of_birth": "2019-02-01"})


def _concern(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": "2025/26",
            "opened_date": "2025-10-01", "attendance_pct": 87.5}
    data.update(extra)
    return AC.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values_and_defaults():
    p = _pupil()
    c = _concern(p, key_worker="Mrs Brown", intervention=" Breakfast club ",
                 parent_contact="Phoned mum", notes="", next_review_date="2025-11-01")
    assert c.concern_id > 0
    assert c.pupil_id == p.pupil_id
    assert c.academic_year == "2025/26"
    assert c.concern_type == "Persistent absence"
    assert c.level == "PA threshold (<90%)"
    assert c.attendance_pct == 87.5
    assert c.threshold_pct == 90.0
    assert c.opened_date == "2025-10-01"
    assert c.next_review_date == "2025-11-01"
    assert c.closed_date is None
    assert c.status == "Open"
    assert c.key_worker == "Mrs Brown"
    assert c.intervention == "Breakfast club"
    assert c.parent_contact == "Phoned mum"
    assert c.notes is None
    assert c.pupil_name == "Ada Lovelace" and c.pupil_year == "2"


def test_percentages_rounded_and_optional():
    p = _pupil()
    c = _concern(p, attendance_pct="88.456", threshold_pct="92.5")
    assert c.attendance_pct == 88.46
    assert c.threshold_pct == 92.5
    blank = _concern(p, attendance_pct="", threshold_pct="")
    assert blank.attendance_pct is None and blank.threshold_pct == 90.0


def test_opened_date_defaults_to_today():
    assert _concern(_pupil(), opened_date=None).opened_date == TODAY


def test_get_missing_is_none():
    P.init_db()  # the pupils table always exists in a real install
    assert AC.get(404) is None


# ── validation ───────────────────────────────────────────────────────

def test_pupil_required_and_must_exist():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Pupil ID is required"):
        _concern(p, pupil_id=None)
    with pytest.raises(AC.ValidationError, match="No pupil with id"):
        _concern(p, pupil_id="GHOST")


def test_academic_year_rules():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Academic year is required"):
        _concern(p, academic_year="")
    with pytest.raises(AC.ValidationError, match="YYYY/YY"):
        _concern(p, academic_year="2025-26")


def test_type_level_status_lists():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Concern type must be one of"):
        _concern(p, concern_type="Boredom")
    with pytest.raises(AC.ValidationError, match="Level must be one of"):
        _concern(p, level="Extreme")
    with pytest.raises(AC.ValidationError, match="Status must be one of"):
        _concern(p, status="Paused")


def test_percentage_rules():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Attendance % must be a number"):
        _concern(p, attendance_pct="ninety")
    with pytest.raises(AC.ValidationError, match="Attendance % must be between 0 and 100"):
        _concern(p, attendance_pct=100.1)
    with pytest.raises(AC.ValidationError, match="Threshold % must be between 0 and 100"):
        _concern(p, threshold_pct=-1)
    assert _concern(p, attendance_pct=0).attendance_pct == 0
    assert _concern(p, attendance_pct=100).attendance_pct == 100


def test_date_rules():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="Opened date must be YYYY-MM-DD"):
        _concern(p, opened_date="1 Oct")
    with pytest.raises(AC.ValidationError, match="Next review date is not a real date"):
        _concern(p, next_review_date="2025-02-29")
    with pytest.raises(AC.ValidationError, match="Next review date cannot be before opened"):
        _concern(p, next_review_date="2025-09-30")
    with pytest.raises(AC.ValidationError, match="Closed date cannot be before opened"):
        _concern(p, status="Closed", closed_date="2025-09-30")


def test_closed_date_only_with_closed_status():
    p = _pupil()
    with pytest.raises(AC.ValidationError, match="only be set when status is Closed"):
        _concern(p, closed_date="2025-12-01")
    closed = _concern(p, status="Closed")
    assert closed.closed_date == TODAY
    explicit = _concern(p, status="Closed", closed_date="2025-12-01")
    assert explicit.closed_date == "2025-12-01"


# ── list ─────────────────────────────────────────────────────────────

def test_list_empty():
    P.init_db()
    assert AC.list_concerns() == []


def test_list_sorted_newest_opened_first():
    p = _pupil()
    a = _concern(p, opened_date="2025-09-10")
    b = _concern(p, opened_date="2026-01-10")
    c = _concern(p, opened_date="2025-09-10")
    assert [r.concern_id for r in AC.list_concerns()] == [b.concern_id, c.concern_id,
                                                         a.concern_id]


def test_list_filters():
    p1, p2 = _pupil("Ada", "A"), _pupil("Ben", "B")
    a = _concern(p1, key_worker="Mr Green")
    b = _concern(p2, academic_year="2024/25", concern_type="Medical",
                 level="Severe (<80%)", status="Closed", opened_date="2024-10-01",
                 closed_date="2025-01-10")
    c = _concern(p2, status="Escalated", key_worker="Mrs Brown")
    ids = lambda rows: sorted(r.concern_id for r in rows)  # noqa: E731
    assert ids(AC.list_concerns(pupil_id=p1.pupil_id)) == [a.concern_id]
    assert ids(AC.list_concerns(academic_year="2024/25")) == [b.concern_id]
    assert ids(AC.list_concerns(status="Escalated")) == [c.concern_id]
    assert ids(AC.list_concerns(concern_type="Medical")) == [b.concern_id]
    assert ids(AC.list_concerns(level="Severe (<80%)")) == [b.concern_id]
    assert ids(AC.list_concerns(key_worker="Mr Green")) == [a.concern_id]
    assert ids(AC.list_concerns(open_only=True)) == [a.concern_id, c.concern_id]


def test_list_filter_validation():
    with pytest.raises(AC.ValidationError, match="Status filter"):
        AC.list_concerns(status="x")
    with pytest.raises(AC.ValidationError, match="Concern type filter"):
        AC.list_concerns(concern_type="x")
    with pytest.raises(AC.ValidationError, match="Level filter"):
        AC.list_concerns(level="x")


# ── update / status / close / delete ────────────────────────────────

def test_update_merges_fields():
    c = _concern(_pupil(), key_worker="Mrs Brown")
    u = AC.update(c.concern_id, {"attendance_pct": 91, "status": "Improving"})
    assert u.attendance_pct == 91.0
    assert u.status == "Improving"
    assert u.key_worker == "Mrs Brown"
    assert u.academic_year == "2025/26"


def test_update_missing_and_invalid():
    P.init_db()
    with pytest.raises(AC.ValidationError, match="No attendance concern #9"):
        AC.update(9, {"notes": "x"})
    c = _concern(_pupil())
    with pytest.raises(AC.ValidationError, match="between 0 and 100"):
        AC.update(c.concern_id, {"attendance_pct": 150})
    assert AC.get(c.concern_id).attendance_pct == 87.5


def test_close_and_reopen():
    c = _concern(_pupil())
    closed = AC.close(c.concern_id, "2026-02-01")
    assert closed.status == "Closed" and closed.closed_date == "2026-02-01"
    reopened = AC.set_status(c.concern_id, "Monitoring")
    assert reopened.status == "Monitoring"
    assert reopened.closed_date is None


def test_close_defaults_to_today_and_keeps_date_on_other_edits():
    c = _concern(_pupil())
    closed = AC.close(c.concern_id)
    assert closed.closed_date == TODAY
    edited = AC.update(c.concern_id, {"notes": "Final letter sent"})
    assert edited.status == "Closed" and edited.closed_date == TODAY


def test_set_status_refuses_unknown():
    c = _concern(_pupil())
    with pytest.raises(AC.ValidationError, match="Status must be one of"):
        AC.set_status(c.concern_id, "Done")


def test_delete():
    c = _concern(_pupil())
    assert AC.delete(c.concern_id) is True
    assert AC.get(c.concern_id) is None
    assert AC.delete(c.concern_id) is False


# ── cohort_summary ───────────────────────────────────────────────────

def test_cohort_summary_empty():
    P.init_db()
    assert AC.cohort_summary() == {"total": 0, "open": 0, "by_status": {}, "by_level": {},
                                   "by_type": {}, "pupils": 0, "avg_attendance": None}


def test_cohort_summary_counts_and_average():
    p1, p2 = _pupil("Ada", "A"), _pupil("Ben", "B")
    _concern(p1, attendance_pct=85)
    _concern(p1, attendance_pct=88, concern_type="Medical", status="Closed")
    _concern(p2, attendance_pct=None, level="Severe (<80%)")
    _concern(p2, attendance_pct=78.3, status="Escalated", level="Severe (<80%)")
    _concern(p2, academic_year="2024/25", attendance_pct=50, opened_date="2024-10-01")
    s = AC.cohort_summary(academic_year="2025/26")
    assert s["total"] == 4
    assert s["open"] == 3
    assert s["by_status"] == {"Open": 2, "Closed": 1, "Escalated": 1}
    assert s["by_level"] == {"PA threshold (<90%)": 2, "Severe (<80%)": 2}
    assert s["by_type"] == {"Persistent absence": 3, "Medical": 1}
    assert s["pupils"] == 2
    # (85 + 88 + 78.3) / 3 = 83.7666… → 83.77; the blank % is not counted
    assert s["avg_attendance"] == 83.77
    assert AC.cohort_summary()["total"] == 5
