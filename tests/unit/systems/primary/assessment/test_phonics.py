"""Phonics phase tracking (domain.assessment.phonics.phonics)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.assessment.phonics import phonics as PH
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="1", last=None, **kw):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2019-03-01"}, **kw)


def _assess(pupil, phase, status="working", on="2025-10-01", **extra):
    return PH.record_assessment(pupil.pupil_id, {"phase": phase, "status": status,
                                                 "assessed_on": on, **extra})


# ── framework ────────────────────────────────────────────────────────

def test_six_phases_each_labelled():
    assert PH.PHASES == ("1", "2", "3", "4", "5", "6")
    assert set(PH.PHASE_LABELS) == set(PH.PHASES)
    assert PH.STATUSES == ("working", "secure")


# ── recording ────────────────────────────────────────────────────────

def test_no_record_until_first_assessment():
    p = _pupil()
    assert PH.get_record(p.pupil_id) is None
    assert PH.list_history(p.pupil_id) == []


def test_record_assessment_sets_current_state_and_history():
    p = _pupil()
    rec = _assess(p, "3", "WORKING", notes="  ai/ee confusion ")
    assert (rec.pupil_id, rec.phase, rec.status, rec.last_assessed, rec.notes) == (
        p.pupil_id, "3", "working", "2025-10-01", "ai/ee confusion")
    (h,) = PH.list_history(p.pupil_id)
    assert (h.phase, h.status, h.assessed_on, h.notes) == (
        "3", "working", "2025-10-01", "ai/ee confusion")


def test_later_assessment_moves_pupil_on_and_keeps_history():
    p = _pupil()
    _assess(p, "3", "working", on="2025-10-01")
    _assess(p, "3", "secure", on="2025-12-01")
    rec = _assess(p, "4", "working", on="2026-01-10")
    assert (rec.phase, rec.status, rec.last_assessed) == ("4", "working", "2026-01-10")
    assert rec.notes is None
    assert [(h.phase, h.status) for h in PH.list_history(p.pupil_id)] == [
        ("4", "working"), ("3", "secure"), ("3", "working")]
    assert PH.get_record(p.pupil_id) == rec


def test_missing_date_uses_today():
    p = _pupil()
    rec = PH.record_assessment(p.pupil_id, {"phase": "2", "status": "secure"})
    today = dt.date.today().isoformat()
    # SQLite's date('now') is UTC; allow the day either side of midnight.
    assert rec.last_assessed in {today, (dt.date.today() - dt.timedelta(days=1)).isoformat(),
                                 (dt.date.today() + dt.timedelta(days=1)).isoformat()}
    assert PH.list_history(p.pupil_id)[0].assessed_on == rec.last_assessed


@pytest.mark.parametrize("data, message", [
    ({"status": "working"}, "Phase is required"),
    ({"phase": "7", "status": "working"}, "Phase must be one of 1, 2, 3, 4, 5, 6"),
    ({"phase": "Phase 3", "status": "working"}, "Phase must be one of"),
    ({"phase": "3"}, "Status is required"),
    ({"phase": "3", "status": "mastered"}, "Status must be one of working, secure"),
    ({"phase": "3", "status": "secure", "assessed_on": "1/10/2025"},
     "Assessed-on date must be YYYY-MM-DD"),
])
def test_record_assessment_refuses_invalid(data, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        PH.record_assessment(p.pupil_id, data)
    assert PH.get_record(p.pupil_id) is None
    assert PH.list_history(p.pupil_id) == []


def test_unknown_pupil_is_refused_everywhere():
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        PH.record_assessment("P0000000", {"phase": "2", "status": "secure"})
    with pytest.raises(P.ValidationError, match="No pupil"):
        PH.get_record("P0000000")
    with pytest.raises(P.ValidationError, match="No pupil"):
        PH.list_history("P0000000")


# ── deleting ─────────────────────────────────────────────────────────

def test_delete_assessment_removes_history_row_only():
    p = _pupil()
    _assess(p, "2", on="2025-09-10")
    _assess(p, "3", on="2025-11-10")
    newest = PH.list_history(p.pupil_id)[0]
    assert PH.delete_assessment(newest.assessment_id) is True
    assert PH.delete_assessment(newest.assessment_id) is False
    assert [h.phase for h in PH.list_history(p.pupil_id)] == ["2"]
    assert PH.get_record(p.pupil_id).phase == "3"


def test_clear_pupil_keeps_history():
    p = _pupil()
    _assess(p, "5", "secure")
    assert PH.clear_pupil(p.pupil_id) is True
    assert PH.get_record(p.pupil_id) is None
    assert len(PH.list_history(p.pupil_id)) == 1
    assert PH.clear_pupil(p.pupil_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    r_a = _pupil("R", last="Adams")
    y1_b = _pupil("1", last="Brown")
    y1_c = _pupil("1", last="Clark")
    y2_d = _pupil("2", last="Drew")
    _assess(r_a, "2", "working")
    _assess(y1_b, "4", "secure")
    _assess(y1_c, "4", "working")
    return r_a, y1_b, y1_c, y2_d


def test_list_records_includes_pupils_without_a_record():
    r_a, y1_b, y1_c, y2_d = _seed()
    rows = PH.list_records()
    assert [p.pupil_id for p, _ in rows] == [y1_b.pupil_id, y1_c.pupil_id,
                                             y2_d.pupil_id, r_a.pupil_id]
    by_id = {p.pupil_id: rec for p, rec in rows}
    assert by_id[y2_d.pupil_id] is None
    assert by_id[y1_b.pupil_id].status == "secure"


def test_list_records_filters():
    r_a, y1_b, y1_c, y2_d = _seed()
    assert [p.pupil_id for p, _ in PH.list_records(year_group="1")] == [
        y1_b.pupil_id, y1_c.pupil_id]
    assert [p.pupil_id for p, _ in PH.list_records(phase="4")] == [
        y1_b.pupil_id, y1_c.pupil_id]
    assert [p.pupil_id for p, _ in PH.list_records(status="working")] == [
        y1_c.pupil_id, r_a.pupil_id]
    assert [p.pupil_id for p, _ in PH.list_records(phase="4", status="secure")] == [
        y1_b.pupil_id]
    assert PH.list_records(year_group="2", phase="4") == []


def test_list_records_leaves_out_pupils_off_roll():
    _seed()
    gone = _pupil("1", roll_status="left")
    _assess(gone, "6", "secure")
    assert gone.pupil_id not in {p.pupil_id for p, _ in PH.list_records()}


@pytest.mark.parametrize("kwargs, message", [
    ({"phase": "0"}, "Phase filter"),
    ({"status": "Secure"}, "Status filter"),
    ({"year_group": "Nursery"}, "Year filter"),
])
def test_list_records_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        PH.list_records(**kwargs)


def test_phase_summary_counts_current_phase_only():
    assert PH.phase_summary() == {ph: 0 for ph in PH.PHASES}
    r_a, y1_b, _c, _d = _seed()
    _assess(r_a, "3", "working", on="2025-12-01")     # moved from 2 to 3
    assert PH.phase_summary() == {"1": 0, "2": 0, "3": 1, "4": 2, "5": 0, "6": 0}
