"""School census returns (domain.governance.compliance.census.census)."""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from education_system.systems.primary.domain.governance.compliance.census import census as CN
from education_system.systems.primary.domain.learners.pupils import pupils as P

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _ret(return_type="School Census - Autumn", year="2026/27", **extra):
    return CN.create_return({"return_type": return_type, "academic_year": year, **extra})


_n = 0


def _pupil(roll_status="on_roll"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Kid{_n}", "last_name": "Test",
                           "year_group": "3", "date_of_birth": "2018-03-01"},
                          roll_status=roll_status)


# ── no learner aims ──

def test_learner_aims_api_is_gone():
    names = set(dir(CN))
    assert not [n for n in names if "aim" in n.lower()]
    assert not [n for n in CN.__all__ if "aim" in n.lower()]
    fields = {f.name for f in dataclasses.fields(CN.CensusSummary)}
    assert "pupils_on_roll" in fields
    assert not [f for f in fields if "aim" in f or "learner" in f]


def test_init_db_creates_only_returns_table(primary_sandbox):
    import sqlite3
    CN.init_db()
    conn = sqlite3.connect(primary_sandbox.PRIMARY_CENSUS_DB)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "census_returns" in tables
    assert "learner_aims" not in tables


# ── pupils on roll ──

def test_pupils_on_roll_counts_only_on_roll():
    assert CN._pupils_on_roll() == 0
    _pupil()
    _pupil()
    _pupil(roll_status="applicant")
    left = _pupil()
    P.set_roll_status(left.pupil_id, "left")
    assert CN._pupils_on_roll() == 2


def test_submit_return_sets_learner_count_from_pupils_on_roll():
    for _ in range(3):
        _pupil()
    _pupil(roll_status="applicant")
    r = _ret(learner_count=99)
    out = CN.submit_return(r.return_id, submitted_by=" Office ", file_ref="CEN-1")
    assert out.status == "Submitted"
    assert out.learner_count == 3
    assert out.submitted_on == TODAY.isoformat()
    assert out.submitted_by == "Office" and out.file_ref == "CEN-1"


def test_submit_return_with_empty_roll_records_zero():
    r = _ret(learner_count=5)
    assert CN.submit_return(r.return_id).learner_count == 0


# ── create / read ──

def test_create_return_defaults():
    r = CN.create_return({"academic_year": " 2026/27 "})
    assert r.return_type == CN.DEFAULT_RETURN_TYPE
    assert r.status == CN.DEFAULT_RETURN_STATUS == "Planned"
    assert r.academic_year == "2026/27"
    assert (r.learner_count, r.error_count, r.warning_count) == (0, 0, 0)
    assert r.submitted_on is None and r.notes is None
    assert CN.get_return(r.return_id) == r


def test_create_return_stores_fields():
    r = _ret("Workforce Census", reference_date="2026-11-05", window_opens="2026-11-01",
             window_closes="2026-12-01", submission_deadline="2026-12-01",
             error_count="2", warning_count=4, file_ref=" f.xml ", notes=" n ")
    assert r.return_type == "Workforce Census"
    assert (r.window_opens, r.window_closes) == ("2026-11-01", "2026-12-01")
    assert (r.error_count, r.warning_count) == (2, 4)
    assert (r.file_ref, r.notes) == ("f.xml", "n")


def test_get_missing_return_is_none():
    assert CN.get_return(404) is None


# ── validation ──

def test_return_type_must_be_known():
    with pytest.raises(CN.ValidationError, match="Return type must be one of"):
        _ret("ILR")


def test_academic_year_required():
    with pytest.raises(CN.ValidationError, match="Academic year is required"):
        CN.create_return({"academic_year": "  "})


def test_status_must_be_known():
    with pytest.raises(CN.ValidationError, match="Status must be one of"):
        _ret(status="Sent")


@pytest.mark.parametrize("field, label", [
    ("reference_date", "Reference date"), ("window_opens", "Window opens"),
    ("window_closes", "Window closes"), ("submission_deadline", "Submission deadline"),
    ("submitted_on", "Submitted on"), ("accepted_on", "Accepted on"),
])
def test_dates_must_be_iso(field, label):
    with pytest.raises(CN.ValidationError, match=f"{label} must be YYYY-MM-DD"):
        _ret(**{field: "05/11/2026"})


def test_window_closes_not_before_opens():
    with pytest.raises(CN.ValidationError, match="Window closes cannot be before window opens"):
        _ret(window_opens="2026-11-10", window_closes="2026-11-09")


@pytest.mark.parametrize("field, label", [
    ("learner_count", "Learner count"), ("error_count", "Error count"),
    ("warning_count", "Warning count"),
])
def test_counts_must_be_non_negative_integers(field, label):
    with pytest.raises(CN.ValidationError, match=f"{label} must be an integer"):
        _ret(**{field: "many"})
    with pytest.raises(CN.ValidationError, match=f"{label} must be >= 0"):
        _ret(**{field: -1})


def test_one_return_per_type_and_year():
    _ret()
    with pytest.raises(CN.ValidationError, match="already exists"):
        _ret()
    assert _ret(year="2027/28").academic_year == "2027/28"
    assert _ret("School Census - Spring").return_type == "School Census - Spring"


# ── update / delete ──

def test_update_return_full_replace():
    r = _ret(notes="old")
    out = CN.update_return(r.return_id, {"return_type": r.return_type,
                                         "academic_year": "2026/27", "status": "Draft"})
    assert out.status == "Draft"
    assert out.notes is None      # update is a full replace, not a merge


def test_update_return_may_keep_its_own_type_and_year():
    r = _ret()
    out = CN.update_return(r.return_id, {"academic_year": "2026/27", "notes": "same key"})
    assert out.notes == "same key"


def test_update_return_cannot_collide_with_another():
    _ret()
    other = _ret(year="2027/28")
    with pytest.raises(CN.ValidationError, match="already exists"):
        CN.update_return(other.return_id, {"academic_year": "2026/27"})


def test_update_missing_return_refused():
    with pytest.raises(CN.ValidationError, match="No return with id 8"):
        CN.update_return(8, {"academic_year": "2026/27"})


def test_delete_return():
    r = _ret()
    assert CN.delete_return(r.return_id) is True
    assert CN.get_return(r.return_id) is None
    assert CN.delete_return(r.return_id) is False


# ── list / filter ──

def test_list_returns_empty():
    assert CN.list_returns() == []


def test_list_returns_order_and_filters():
    a = _ret("School Census - Spring", "2025/26", submission_deadline="2026-02-01")
    b = _ret("School Census - Autumn", "2026/27", submission_deadline="2026-10-15")
    c = _ret("School Census - Spring", "2026/27", submission_deadline="2027-02-01",
             status="Draft")
    assert [r.return_id for r in CN.list_returns()] == [b.return_id, c.return_id, a.return_id]
    assert [r.return_id for r in CN.list_returns(academic_year="2025/26")] == [a.return_id]
    assert [r.return_id for r in CN.list_returns(return_type="School Census - Spring")] == \
        [c.return_id, a.return_id]
    assert [r.return_id for r in CN.list_returns(status="Draft")] == [c.return_id]


def test_list_returns_overdue_only():
    late = _ret("Workforce Census", submission_deadline=_iso(-1))
    _ret("Other", submission_deadline=_iso(-1), status="Submitted")
    _ret("Pupil Premium Return", submission_deadline=_iso(3))
    _ret("School Census - Summer")
    assert [r.return_id for r in CN.list_returns(overdue_only=True)] == [late.return_id]


def test_list_returns_open_window_only():
    open_ = _ret("Workforce Census", window_opens=_iso(-2), window_closes=_iso(2))
    _ret("Other", window_opens=_iso(1), window_closes=_iso(5))
    _ret("School Census - Spring", window_opens=_iso(-5), window_closes=_iso(-1))
    assert [r.return_id for r in CN.list_returns(open_window_only=True)] == [open_.return_id]


# ── derived properties ──

def test_is_overdue_property():
    assert _ret("Other", submission_deadline=_iso(-1)).is_overdue is True
    assert _ret("Workforce Census", submission_deadline=_iso(0)).is_overdue is False
    assert _ret("School Census - Spring").is_overdue is False
    for i, st in enumerate(("Submitted", "Accepted", "Resubmitted", "Archived")):
        r = _ret(year=f"y{i}", status=st, submission_deadline=_iso(-9))
        assert r.is_overdue is False


def test_is_open_window_property():
    assert _ret(window_opens=_iso(0), window_closes=_iso(0)).is_open_window is True
    assert _ret("Other", window_opens=_iso(-3)).is_open_window is False


# ── workflow ──

def test_workflow_transitions_keep_other_fields():
    r = _ret(notes="keep", file_ref="a.xml")
    assert CN.validate_return(r.return_id).status == "Validated"
    rej = CN.reject_return(r.return_id)
    assert rej.status == "Rejected" and rej.notes == "keep"
    rs = CN.resubmit_return(r.return_id, submitted_by="Bursar", file_ref="b.xml")
    assert rs.status == "Resubmitted" and rs.submitted_on == TODAY.isoformat()
    assert rs.submitted_by == "Bursar" and rs.file_ref == "b.xml"
    acc = CN.accept_return(r.return_id, accepted_on="2026-12-02")
    assert acc.status == "Accepted" and acc.accepted_on == "2026-12-02"
    assert CN.archive_return(r.return_id).status == "Archived"
    assert CN.get_return(r.return_id).notes == "keep"


def test_accept_defaults_to_today_and_resubmit_keeps_file_ref():
    r = _ret(file_ref="orig.xml")
    assert CN.resubmit_return(r.return_id).file_ref == "orig.xml"
    assert CN.accept_return(r.return_id).accepted_on == TODAY.isoformat()


def test_set_return_status():
    r = _ret()
    assert CN.set_return_status(r.return_id, "Under Review").status == "Under Review"
    with pytest.raises(CN.ValidationError, match="Status must be one of"):
        CN.set_return_status(r.return_id, "Lost")


def test_record_validation_counts_clamps_negative():
    r = _ret()
    out = CN.record_validation_counts(r.return_id, errors=3, warnings=-2)
    assert (out.error_count, out.warning_count) == (3, 0)


def test_workflow_missing_return_refused():
    for fn in (CN.validate_return, CN.submit_return, CN.accept_return, CN.reject_return,
               CN.resubmit_return, CN.archive_return, CN.record_validation_counts):
        with pytest.raises(CN.ValidationError, match="No return with id 31"):
            fn(31)
    with pytest.raises(CN.ValidationError, match="No return with id 31"):
        CN.set_return_status(31, "Draft")


# ── summary ──

def test_summary_empty():
    s = CN.summary()
    assert s == CN.CensusSummary()
    assert s.pupils_on_roll == 0


def test_summary_counts_and_pupils_on_roll():
    _pupil()
    _pupil()
    _pupil(roll_status="applicant")
    _ret("School Census - Autumn", status="Planned", submission_deadline=_iso(-1))
    _ret("School Census - Spring", status="Draft", window_opens=_iso(-1),
         window_closes=_iso(1))
    _ret("School Census - Summer", status="Validated")
    _ret("Workforce Census", status="Submitted", submission_deadline=_iso(-5))
    _ret("Other", status="Resubmitted")
    _ret("Pupil Premium Return", status="Accepted")
    _ret("Alternative Provision Census", status="Rejected", submission_deadline=_iso(-2))
    s = CN.summary()
    assert s.total_returns == 7
    assert s.pupils_on_roll == 2
    assert (s.planned, s.in_progress, s.submitted, s.accepted, s.rejected) == (1, 2, 2, 1, 1)
    assert s.overdue == 2           # planned + rejected past deadline; submitted is not
    assert s.open_windows == 1
    assert s.by_return_status == {"Planned": 1, "Draft": 1, "Validated": 1, "Submitted": 1,
                                  "Resubmitted": 1, "Accepted": 1, "Rejected": 1}
    assert sum(s.by_return_type.values()) == 7 and len(s.by_return_type) == 7
