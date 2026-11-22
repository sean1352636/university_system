"""Multiplication Tables Check (domain.assessment.mtc.mtc)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.mtc import mtc as MTC
from education_system.systems.primary.domain.learners.pupils import pupils as P

YEAR = "2025-26"
_n = 0


def _pupil(year="4"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2016-03-01"})


def _res(pupil, score, **extra):
    return MTC.create({"pupil_id": pupil.pupil_id, "academic_year": YEAR,
                       "score": score, **extra})


# ── thresholds ───────────────────────────────────────────────────────

def test_check_is_out_of_25_with_20_expected():
    assert (MTC.MAX_SCORE, MTC.EXPECTED_THRESHOLD) == (25, 20)


@pytest.mark.parametrize("score, met, full", [
    (0, False, False), (19, False, False), (20, True, False),
    (24, True, False), (25, True, True),
])
def test_met_expected_and_full_marks(score, met, full):
    r = _res(_pupil(), score)
    assert (r.met_expected, r.full_marks) == (met, full)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_and_reads_back():
    p = _pupil()
    r = _res(p, "22", assessed_on="2026-06-09", notes="  quick  ")
    got = MTC.get(r.result_id)
    assert got == r
    assert (got.score, got.assessed_on, got.notes, got.academic_year) == (
        22, "2026-06-09", "quick", YEAR)


def test_get_unknown_is_none():
    assert MTC.get(5) is None


@pytest.mark.parametrize("data, message", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"academic_year": ""}, "Academic year is required"),
    ({"academic_year": "2025_26"}, "Academic year must look like"),
    ({"score": None}, "Score is required"),
    ({"score": ""}, "Score is required"),
    ({"score": "twenty"}, "Score must be an integer"),
    ({"score": -1}, "Score must be between 0 and 25"),
    ({"score": 26}, "Score must be between 0 and 25"),
    ({"assessed_on": "9 June"}, "Assessed-on date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid(data, message):
    p = _pupil()
    payload = {"pupil_id": p.pupil_id, "academic_year": YEAR, "score": 20, **data}
    with pytest.raises(P.ValidationError, match=message):
        MTC.create(payload)
    assert MTC.list_results() == []


def test_create_refuses_unknown_pupil():
    with pytest.raises(P.ValidationError, match="No pupil with id P1111111"):
        MTC.create({"pupil_id": "P1111111", "academic_year": YEAR, "score": 20})


def test_one_result_per_pupil_per_year():
    p = _pupil()
    first = _res(p, 18)
    with pytest.raises(P.ValidationError, match=f"#{first.result_id}"):
        _res(p, 22)
    MTC.create({"pupil_id": p.pupil_id, "academic_year": "2026-27", "score": 22})
    assert [r.academic_year for r in MTC.list_for_pupil(p.pupil_id)] == ["2026-27", YEAR]


# ── update / delete ──────────────────────────────────────────────────

def test_update_merges_fields():
    r = _res(_pupil(), 18, notes="keep")
    up = MTC.update(r.result_id, {"score": 21})
    assert (up.score, up.notes, up.met_expected) == (21, "keep", True)


def test_update_refusals():
    p = _pupil()
    a = _res(p, 10)
    b = MTC.create({"pupil_id": p.pupil_id, "academic_year": "2026-27", "score": 15})
    with pytest.raises(P.ValidationError, match="No MTC result #321"):
        MTC.update(321, {"score": 1})
    with pytest.raises(P.ValidationError, match="Another result"):
        MTC.update(b.result_id, {"academic_year": YEAR})
    with pytest.raises(P.ValidationError, match="between 0 and 25"):
        MTC.update(a.result_id, {"score": 30})
    with pytest.raises(P.ValidationError, match="Score is required"):
        MTC.update(a.result_id, {"score": ""})
    assert MTC.get(a.result_id).score == 10


def test_delete():
    r = _res(_pupil(), 12)
    assert MTC.delete(r.result_id) is True
    assert MTC.get(r.result_id) is None
    assert MTC.delete(r.result_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    a, b, c = _pupil("4"), _pupil("4"), _pupil("5")
    _res(a, 25)
    _res(b, 12)
    _res(c, 20)
    MTC.create({"pupil_id": c.pupil_id, "academic_year": "2024-25", "score": 8})
    return a, b, c


def test_list_results_filters():
    a, b, c = _seed()
    assert len(MTC.list_results()) == 4
    assert {r.pupil_id for r, _ in MTC.list_results(academic_year=YEAR)} == {
        a.pupil_id, b.pupil_id, c.pupil_id}
    assert {r.score for r, _ in MTC.list_results(met_expected=True)} == {25, 20}
    assert {r.score for r, _ in MTC.list_results(met_expected=False)} == {12, 8}
    assert [r.score for r, _ in MTC.list_results(pupil_id=c.pupil_id)] == [20, 8]
    assert {p.pupil_id for _, p in MTC.list_results(year_group="4")} == {a.pupil_id, b.pupil_id}
    assert MTC.list_results(academic_year=YEAR, met_expected=False)[0][0].score == 12


def test_list_results_order_newest_year_first():
    _seed()
    years = [r.academic_year for r, _ in MTC.list_results()]
    assert years == [YEAR, YEAR, YEAR, "2024-25"]


def test_list_results_bad_year_group():
    with pytest.raises(P.ValidationError, match="Year filter"):
        MTC.list_results(year_group="Y4")


def test_list_for_pupil_unknown():
    with pytest.raises(P.ValidationError, match="No pupil"):
        MTC.list_for_pupil("P0000000")


def test_year_summary():
    _seed()
    s = MTC.year_summary(YEAR)
    assert s["academic_year"] == YEAR
    assert (s["total"], s["met_expected"], s["below_expected"], s["full_marks"]) == (3, 2, 1, 1)
    assert s["met_pct"] == pytest.approx(200 / 3)
    assert s["full_marks_pct"] == pytest.approx(100 / 3)
    assert s["average_score"] == pytest.approx(19.0)       # (25 + 12 + 20) / 3


def test_year_summary_empty_and_required():
    s = MTC.year_summary("2030-31")
    assert s == {"academic_year": "2030-31", "total": 0, "met_expected": 0,
                 "below_expected": 0, "met_pct": 0.0, "full_marks": 0,
                 "full_marks_pct": 0.0, "average_score": 0.0}
    with pytest.raises(P.ValidationError, match="Academic year is required"):
        MTC.year_summary("")


def test_known_years():
    assert MTC.known_years() == []
    _seed()
    assert MTC.known_years() == [YEAR, "2024-25"]
