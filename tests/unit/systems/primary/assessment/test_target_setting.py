"""Pupil targets (domain.assessment.target_setting.target_setting)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.target_setting import (
    target_setting as TS,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P

YEAR = "2025-26"
_n = 0


def _pupil(year="5"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2015-03-01"})


def _target(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": YEAR, "subject": "Maths",
            "target_grade": "EXS"}
    data.update(extra)
    return TS.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_defaults_to_open():
    t = _target(_pupil())
    assert t.status == "open" and t.is_open
    assert t.target_score is None and t.set_on is None and t.review_date is None
    assert TS.get(t.target_id) == t


def test_create_stores_every_field_and_normalises():
    p = _pupil()
    t = _target(p, subject=" Reading ", target_grade="gds", target_score="105.5",
                set_on="2025-09-10", review_date="2026-02-10", status=" MET ",
                notes="  stretch ")
    got = TS.get(t.target_id)
    assert (got.subject, got.target_grade, got.target_score) == ("Reading", "GDS", 105.5)
    assert (got.set_on, got.review_date, got.status, got.notes) == (
        "2025-09-10", "2026-02-10", "met", "stretch")
    assert not got.is_open


def test_review_date_may_equal_set_on():
    t = _target(_pupil(), set_on="2025-09-10", review_date="2025-09-10")
    assert t.review_date == "2025-09-10"


def test_target_score_limits_inclusive():
    p = _pupil()
    assert _target(p, subject="A", target_score=0).target_score == 0.0
    assert _target(p, subject="B", target_score=130).target_score == 130.0


def test_get_unknown_is_none():
    assert TS.get(31) is None


@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", "", "Pupil ID is required"),
    ("academic_year", "", "Academic year is required"),
    ("academic_year", "2025-266", "Academic year must look like"),
    ("subject", "", "Subject is required"),
    ("subject", "s" * 65, "64 characters or fewer"),
    ("target_grade", "", "Target grade is required"),
    ("target_grade", "A", "Target grade must be one of BLW, WTS, EXS, GDS"),
    ("target_score", "lots", "Target score must be a number"),
    ("target_score", -1, "between 0 and 130"),
    ("target_score", 130.5, "between 0 and 130"),
    ("set_on", "10/09/2025", "Set-on date must be YYYY-MM-DD"),
    ("review_date", "Feb", "Review date must be YYYY-MM-DD"),
    ("status", "achieved", "Status must be one of"),
])
def test_create_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _target(p, **{field: value})
    assert TS.list_targets() == []


def test_review_date_before_set_on_is_refused():
    with pytest.raises(P.ValidationError, match="Review date cannot be before the set-on date"):
        _target(_pupil(), set_on="2025-10-01", review_date="2025-09-30")


def test_create_refuses_unknown_pupil_and_duplicates():
    with pytest.raises(P.ValidationError, match="No pupil with id"):
        TS.create({"pupil_id": "P0000000", "academic_year": YEAR, "subject": "Maths",
                   "target_grade": "EXS"})
    p = _pupil()
    first = _target(p)
    with pytest.raises(P.ValidationError, match=f"#{first.target_id}"):
        _target(p, target_grade="GDS")
    _target(p, subject="Writing")
    _target(p, academic_year="2026-27")
    assert len(TS.list_for_pupil(p.pupil_id)) == 3


# ── update / status / delete ─────────────────────────────────────────

def test_update_merges_fields():
    t = _target(_pupil(), notes="keep", set_on="2025-09-01")
    up = TS.update(t.target_id, {"target_grade": "GDS", "review_date": "2026-01-15"})
    assert (up.target_grade, up.review_date, up.notes, up.set_on) == (
        "GDS", "2026-01-15", "keep", "2025-09-01")


def test_update_refusals():
    p = _pupil()
    _target(p, subject="Maths")
    reading = _target(p, subject="Reading", set_on="2025-09-01")
    with pytest.raises(P.ValidationError, match="No target #808"):
        TS.update(808, {})
    with pytest.raises(P.ValidationError, match="Another target"):
        TS.update(reading.target_id, {"subject": "Maths"})
    with pytest.raises(P.ValidationError, match="Review date cannot be before"):
        TS.update(reading.target_id, {"review_date": "2025-08-01"})
    with pytest.raises(P.ValidationError, match="No pupil"):
        TS.update(reading.target_id, {"pupil_id": "P0000000"})
    assert TS.get(reading.target_id).subject == "Reading"


@pytest.mark.parametrize("status", ["met", "not_met", "exceeded", "withdrawn", "open"])
def test_set_status_each_status(status):
    t = _target(_pupil())
    assert TS.set_status(t.target_id, status).status == status
    assert TS.get(t.target_id).is_open is (status == "open")


def test_set_status_refusals():
    t = _target(_pupil())
    with pytest.raises(P.ValidationError, match="Status must be one of"):
        TS.set_status(t.target_id, "done")
    with pytest.raises(P.ValidationError, match="No target #999"):
        TS.set_status(999, "met")
    assert TS.get(t.target_id).status == "open"


def test_delete():
    t = _target(_pupil())
    assert TS.delete(t.target_id) is True
    assert TS.get(t.target_id) is None
    assert TS.delete(t.target_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    a, b = _pupil("5"), _pupil("6")
    _target(a, subject="Maths", target_grade="EXS", status="met")
    _target(a, subject="Reading", target_grade="GDS", status="exceeded")
    _target(b, subject="Maths", target_grade="WTS", status="not_met")
    _target(b, subject="Writing", target_grade="EXS")
    _target(a, academic_year="2024-25", subject="Maths", target_grade="BLW", status="withdrawn")
    return a, b


def test_list_targets_filters_and_order():
    a, b = _seed()
    rows = TS.list_targets()
    assert [t.academic_year for t, _ in rows] == [YEAR] * 4 + ["2024-25"]
    assert [t.subject for t, _ in rows][:4] == ["Maths", "Maths", "Reading", "Writing"]
    assert len(TS.list_targets(academic_year=YEAR)) == 4
    assert len(TS.list_targets(subject="Maths")) == 3
    assert [t.subject for t, _ in TS.list_targets(status="open")] == ["Writing"]
    assert len(TS.list_targets(pupil_id=a.pupil_id)) == 3
    assert {p.pupil_id for _, p in TS.list_targets(year_group="6")} == {b.pupil_id}


def test_list_targets_bad_filters():
    with pytest.raises(P.ValidationError, match="Status filter"):
        TS.list_targets(status="Open")
    with pytest.raises(P.ValidationError, match="Year filter"):
        TS.list_targets(year_group="7")


def test_list_for_pupil():
    a, _ = _seed()
    assert [(t.academic_year, t.subject) for t in TS.list_for_pupil(a.pupil_id)] == [
        (YEAR, "Maths"), (YEAR, "Reading"), ("2024-25", "Maths")]
    with pytest.raises(P.ValidationError, match="No pupil"):
        TS.list_for_pupil("P0000000")


def test_summary():
    _seed()
    s = TS.summary(academic_year=YEAR)
    assert s["total"] == 4
    assert s["by_status"] == {"open": 1, "met": 1, "not_met": 1, "exceeded": 1, "withdrawn": 0}
    assert s["by_grade"] == {"BLW": 0, "WTS": 1, "EXS": 2, "GDS": 1}
    assert s["met_or_exceeded"] == 2 and s["met_or_exceeded_pct"] == 50.0
    maths = TS.summary(subject="Maths")
    assert maths["total"] == 3 and maths["met_or_exceeded"] == 1
    assert maths["met_or_exceeded_pct"] == pytest.approx(100 / 3)


def test_empty_database():
    assert TS.list_targets() == [] and TS.known_years() == [] and TS.known_subjects() == []
    s = TS.summary()
    assert s["total"] == 0 and s["met_or_exceeded_pct"] == 0.0
    assert set(s["by_status"].values()) == {0}


def test_known_years_and_subjects():
    _seed()
    p = _pupil()
    _target(p, subject="art")
    assert TS.known_years() == [YEAR, "2024-25"]
    assert TS.known_subjects() == ["art", "Maths", "Reading", "Writing"]
