"""Reading book bands (domain.assessment.reading_levels.reading_levels)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.reading_levels import (
    reading_levels as RL,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="2", last=None, **kw):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-03-01"}, **kw)


def _assess(pupil, band, status="working", on="2025-10-01", **extra):
    return RL.record_assessment(pupil.pupil_id, {"band": band, "status": status,
                                                 "assessed_on": on, **extra})


# ── bands ────────────────────────────────────────────────────────────

def test_band_order_runs_pink_to_free_reader():
    assert RL.BANDS[0] == "Pink" and RL.BANDS[-1] == "Free Reader"
    assert len(RL.BANDS) == 15
    assert RL.BAND_ORDER["Pink"] < RL.BAND_ORDER["Turquoise"] < RL.BAND_ORDER["Dark Blue"]
    assert [RL.BAND_ORDER[b] for b in RL.BANDS] == list(range(15))


# ── recording ────────────────────────────────────────────────────────

def test_first_assessment_creates_current_level():
    p = _pupil()
    assert RL.get_record(p.pupil_id) is None
    rec = _assess(p, "Blue", "SECURE", book_title=" The Big Egg ", notes=" fluent ")
    assert (rec.band, rec.status, rec.last_assessed, rec.book_title, rec.notes) == (
        "Blue", "secure", "2025-10-01", "The Big Egg", "fluent")
    (h,) = RL.list_history(p.pupil_id)
    assert (h.band, h.status, h.assessed_on, h.book_title, h.notes) == (
        "Blue", "secure", "2025-10-01", "The Big Egg", "fluent")


def test_moving_up_a_band_updates_current_and_appends_history():
    p = _pupil()
    _assess(p, "Yellow", on="2025-09-15", book_title="Book A")
    rec = _assess(p, "Blue", on="2025-11-15")
    assert (rec.band, rec.last_assessed, rec.book_title) == ("Blue", "2025-11-15", None)
    assert [h.band for h in RL.list_history(p.pupil_id)] == ["Blue", "Yellow"]


def test_history_same_day_newest_first():
    p = _pupil()
    _assess(p, "Red", on="2025-10-01")
    _assess(p, "Yellow", on="2025-10-01")
    assert [h.band for h in RL.list_history(p.pupil_id)] == ["Yellow", "Red"]


@pytest.mark.parametrize("data, message", [
    ({"status": "working"}, "Band is required"),
    ({"band": "pink", "status": "working"}, "Band must be one of"),
    ({"band": "Silver", "status": "working"}, "Band must be one of"),
    ({"band": "Pink"}, "Status is required"),
    ({"band": "Pink", "status": "done"}, "Status must be one of working, secure"),
    ({"band": "Pink", "status": "secure", "assessed_on": "2025.10.01"},
     "Assessed-on date must be YYYY-MM-DD"),
])
def test_record_assessment_refuses_invalid(data, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        RL.record_assessment(p.pupil_id, data)
    assert RL.get_record(p.pupil_id) is None and RL.list_history(p.pupil_id) == []


def test_unknown_pupil_refused():
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        RL.record_assessment("P0000000", {"band": "Pink", "status": "working"})
    with pytest.raises(P.ValidationError, match="No pupil"):
        RL.get_record("P0000000")
    with pytest.raises(P.ValidationError, match="No pupil"):
        RL.list_history("P0000000")


# ── deleting ─────────────────────────────────────────────────────────

def test_delete_assessment_and_clear_pupil():
    p = _pupil()
    _assess(p, "Green", on="2025-09-01")
    _assess(p, "Orange", on="2025-12-01")
    newest = RL.list_history(p.pupil_id)[0]
    assert RL.delete_assessment(newest.assessment_id) is True
    assert RL.delete_assessment(newest.assessment_id) is False
    assert [h.band for h in RL.list_history(p.pupil_id)] == ["Green"]
    assert RL.get_record(p.pupil_id).band == "Orange"     # current level untouched
    assert RL.clear_pupil(p.pupil_id) is True
    assert RL.get_record(p.pupil_id) is None
    assert len(RL.list_history(p.pupil_id)) == 1           # history kept
    assert RL.clear_pupil(p.pupil_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    r = _pupil("R", last="Ash")
    a = _pupil("2", last="Bell")
    b = _pupil("2", last="Cole")
    none = _pupil("3", last="Dunn")
    _assess(r, "Pink", "working")
    _assess(a, "Gold", "secure")
    _assess(b, "Gold", "working")
    return r, a, b, none


def test_list_records_all_on_roll_pupils():
    r, a, b, none = _seed()
    rows = RL.list_records()
    assert [p.pupil_id for p, _ in rows] == [a.pupil_id, b.pupil_id, none.pupil_id, r.pupil_id]
    assert dict((p.pupil_id, rec) for p, rec in rows)[none.pupil_id] is None


def test_list_records_filters():
    r, a, b, none = _seed()
    assert [p.pupil_id for p, _ in RL.list_records(year_group="2")] == [a.pupil_id, b.pupil_id]
    assert [p.pupil_id for p, _ in RL.list_records(band="Gold")] == [a.pupil_id, b.pupil_id]
    assert [p.pupil_id for p, _ in RL.list_records(status="working")] == [
        b.pupil_id, r.pupil_id]
    assert [p.pupil_id for p, _ in RL.list_records(band="Gold", status="secure")] == [
        a.pupil_id]
    assert RL.list_records(year_group="3", band="Pink") == []


def test_list_records_excludes_leavers():
    _seed()
    left = _pupil("2", roll_status="left")
    _assess(left, "White")
    assert left.pupil_id not in {p.pupil_id for p, _ in RL.list_records()}


@pytest.mark.parametrize("kwargs, message", [
    ({"band": "Silver"}, "Band filter"),
    ({"status": "x"}, "Status filter"),
    ({"year_group": "0"}, "Year filter"),
])
def test_list_records_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        RL.list_records(**kwargs)


def test_band_summary():
    empty = RL.band_summary()
    assert list(empty) == list(RL.BANDS) and set(empty.values()) == {0}
    r, _a, _b, _none = _seed()
    _assess(r, "Red", on="2025-11-01")
    s = RL.band_summary()
    assert s["Gold"] == 2 and s["Red"] == 1 and s["Pink"] == 0
    assert sum(s.values()) == 3
