"""Phonics screening check (domain.assessment.phonics_screening.phonics_screening)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.phonics_screening import (
    phonics_screening as PS,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P

Y1 = "2025-26"
Y2 = "2026-27"
_n = 0


def _pupil(year="1"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2019-03-01"})


def _res(pupil, score, year=Y1, attempt=1, **extra):
    return PS.create({"pupil_id": pupil.pupil_id, "academic_year": year,
                      "attempt": attempt, "score": score, **extra})


# ── pass mark ────────────────────────────────────────────────────────

def test_check_is_out_of_40_with_32_to_pass():
    assert (PS.MAX_SCORE, PS.PASS_MARK, PS.ATTEMPTS) == (40, 32, (1, 2))


@pytest.mark.parametrize("score, passed", [(0, False), (31, False), (32, True), (40, True)])
def test_passed_flag(score, passed):
    assert _res(_pupil(), score).passed is passed


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_and_reads_back():
    p = _pupil()
    r = _res(p, "28", assessed_on="2026-06-08", notes="  tired ")
    got = PS.get(r.result_id)
    assert got == r
    assert (got.attempt, got.score, got.assessed_on, got.notes) == (1, 28, "2026-06-08", "tired")


def test_attempt_defaults_to_one():
    p = _pupil()
    r = PS.create({"pupil_id": p.pupil_id, "academic_year": Y1, "score": 35})
    assert r.attempt == 1


def test_get_unknown_is_none():
    assert PS.get(77) is None


@pytest.mark.parametrize("data, message", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"academic_year": ""}, "Academic year is required"),
    ({"academic_year": "Y1"}, "Academic year must look like"),
    ({"attempt": "first"}, "Attempt must be 1 or 2"),
    ({"attempt": 3}, "Attempt must be one of 1, 2"),
    ({"attempt": 0}, "Attempt must be one of 1, 2"),
    ({"score": None}, "Score is required"),
    ({"score": "high"}, "Score must be an integer"),
    ({"score": -1}, "Score must be between 0 and 40"),
    ({"score": 41}, "Score must be between 0 and 40"),
    ({"assessed_on": "June 2026"}, "Assessed-on date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid(data, message):
    p = _pupil()
    payload = {"pupil_id": p.pupil_id, "academic_year": Y1, "attempt": 1, "score": 30, **data}
    with pytest.raises(P.ValidationError, match=message):
        PS.create(payload)
    assert PS.list_results() == []


def test_create_refuses_unknown_pupil():
    with pytest.raises(P.ValidationError, match="No pupil with id P2222222"):
        PS.create({"pupil_id": "P2222222", "academic_year": Y1, "score": 30})


def test_same_attempt_in_same_year_is_a_duplicate():
    p = _pupil()
    first = _res(p, 20)
    with pytest.raises(P.ValidationError, match=f"attempt 1 already exists \\(#{first.result_id}\\)"):
        _res(p, 33)


# ── retake rule ──────────────────────────────────────────────────────

def test_pupil_who_failed_retakes_next_year():
    p = _pupil()
    _res(p, 25, year=Y1, attempt=1)
    retake = _res(p, 34, year=Y2, attempt=2)
    assert retake.passed
    assert [(r.academic_year, r.attempt, r.passed) for r in PS.list_for_pupil(p.pupil_id)] == [
        (Y2, 2, True), (Y1, 1, False)]


def test_pupil_who_passed_first_time_cannot_record_a_retake():
    # Module docstring: "any pupil who did not pass first time retakes in
    # Year 2 (attempt 2)" - a pupil who passed attempt 1 does not retake.
    p = _pupil()
    _res(p, 36, year=Y1, attempt=1)
    with pytest.raises(P.ValidationError):
        _res(p, 38, year=Y2, attempt=2)
    assert [r.attempt for r in PS.list_for_pupil(p.pupil_id)] == [1]


# ── update / delete ──────────────────────────────────────────────────

def test_update_merges_fields():
    r = _res(_pupil(), 30, notes="keep")
    up = PS.update(r.result_id, {"score": 32})
    assert (up.score, up.passed, up.notes) == (32, True, "keep")


def test_update_refusals():
    p = _pupil()
    a = _res(p, 20, year=Y1, attempt=1)
    b = _res(p, 25, year=Y1, attempt=2)
    with pytest.raises(P.ValidationError, match="No phonics-screening result #900"):
        PS.update(900, {"score": 1})
    with pytest.raises(P.ValidationError, match="attempt 1 already exists"):
        PS.update(b.result_id, {"attempt": 1})
    with pytest.raises(P.ValidationError, match="between 0 and 40"):
        PS.update(a.result_id, {"score": 50})
    with pytest.raises(P.ValidationError, match="No pupil"):
        PS.update(a.result_id, {"pupil_id": "P0000000"})
    assert PS.get(a.result_id).score == 20


def test_delete():
    r = _res(_pupil(), 10)
    assert PS.delete(r.result_id) is True
    assert PS.get(r.result_id) is None
    assert PS.delete(r.result_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    a, b, c = _pupil("1"), _pupil("1"), _pupil("2")
    _res(a, 38)
    _res(b, 22)
    _res(c, 30, year="2024-25")
    _res(c, 33, year=Y1, attempt=2)
    return a, b, c


def test_list_results_filters():
    a, b, c = _seed()
    assert len(PS.list_results()) == 4
    assert {r.pupil_id for r, _ in PS.list_results(academic_year=Y1)} == {
        a.pupil_id, b.pupil_id, c.pupil_id}
    assert [r.pupil_id for r, _ in PS.list_results(attempt=2)] == [c.pupil_id]
    assert {r.score for r, _ in PS.list_results(passed=True)} == {38, 33}
    assert {r.score for r, _ in PS.list_results(passed=False)} == {22, 30}
    assert [r.score for r, _ in PS.list_results(pupil_id=c.pupil_id)] == [33, 30]
    assert {p.pupil_id for _, p in PS.list_results(year_group="2")} == {c.pupil_id}
    assert [r.score for r, _ in PS.list_results(academic_year=Y1, passed=False)] == [22]


def test_list_results_orders_year_then_attempt():
    _seed()
    keys = [(r.academic_year, r.attempt) for r, _ in PS.list_results()]
    assert keys == [(Y1, 1), (Y1, 1), (Y1, 2), ("2024-25", 1)]


def test_list_results_refuses_bad_filters():
    with pytest.raises(P.ValidationError, match="Attempt filter"):
        PS.list_results(attempt=3)
    with pytest.raises(P.ValidationError, match="Year filter"):
        PS.list_results(year_group="Y1")


def test_list_for_pupil_unknown():
    with pytest.raises(P.ValidationError, match="No pupil"):
        PS.list_for_pupil("P0000000")


def test_year_summary():
    _seed()
    s = PS.year_summary(Y1)
    assert (s["academic_year"], s["total"], s["passed"], s["failed"]) == (Y1, 3, 2, 1)
    assert s["pass_rate"] == pytest.approx(200 / 3)
    assert s["average_score"] == pytest.approx((38 + 22 + 33) / 3)
    old = PS.year_summary("2024-25")
    assert (old["total"], old["passed"], old["pass_rate"], old["average_score"]) == (
        1, 0, 0.0, 30.0)


def test_year_summary_empty_and_required():
    assert PS.year_summary("2030-31") == {"academic_year": "2030-31", "total": 0,
                                          "passed": 0, "failed": 0, "pass_rate": 0.0,
                                          "average_score": 0.0}
    with pytest.raises(P.ValidationError, match="Academic year is required"):
        PS.year_summary(" ")


def test_known_years():
    assert PS.known_years() == []
    _seed()
    assert PS.known_years() == [Y1, "2024-25"]
