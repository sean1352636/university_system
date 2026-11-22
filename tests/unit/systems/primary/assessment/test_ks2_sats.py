"""KS2 SATs results (domain.assessment.ks2_sats.ks2_sats)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats as K2
from education_system.systems.primary.domain.learners.pupils import pupils as P

YEAR = "2025-26"
_n = 0


def _pupil(year="6"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2014-03-01"})


def _res(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": YEAR, "subject": "Reading",
            "outcome": "EXS"}
    data.update(extra)
    return K2.create(data)


def _rwm(pupil, reading, maths, egps, year=YEAR):
    for subj, outcome in (("Reading", reading), ("Maths", maths), ("EGPS", egps)):
        if outcome:
            _res(pupil, academic_year=year, subject=subj, outcome=outcome)


# ── suggested outcome ────────────────────────────────────────────────

@pytest.mark.parametrize("score, outcome", [
    (None, None), (60, "WTS"), (99, "WTS"), (100, "EXS"), (109, "EXS"),
    (110, "GDS"), (120, "GDS"),
])
def test_suggest_outcome_uses_100_and_110(score, outcome):
    assert K2.suggest_outcome(score) == outcome


def test_thresholds():
    assert (K2.EXPECTED_SCALED, K2.GREATER_DEPTH_SCALED) == (100, 110)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_and_reads_back():
    p = _pupil()
    r = _res(p, subject="EGPS", scaled_score="111", outcome="gds",
             assessed_on="2026-05-12", notes=" n ")
    got = K2.get(r.result_id)
    assert got == r
    assert (got.subject, got.scaled_score, got.outcome, got.assessed_on, got.notes) == (
        "EGPS", 111, "GDS", "2026-05-12", "n")
    assert got.at_or_above_expected


def test_science_is_a_ks2_subject_without_a_score():
    r = _res(_pupil(), subject="Science", outcome="EXS")
    assert r.subject == "Science" and r.scaled_score is None


def test_at_or_above_expected_flags():
    p = _pupil()
    assert not _res(p, subject="Reading", outcome="WTS").at_or_above_expected
    assert _res(p, subject="Maths", outcome="EXS").at_or_above_expected
    assert not _res(p, subject="EGPS", outcome="NS").at_or_above_expected


def test_get_unknown_is_none():
    assert K2.get(1) is None


@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", " ", "Pupil ID is required"),
    ("academic_year", "", "Academic year is required"),
    ("academic_year", "2025-6", "Academic year must look like"),
    ("subject", "", "Subject is required"),
    ("subject", "Writing", "Subject must be one of Reading, Maths, EGPS, Science"),
    ("scaled_score", "abc", "Scaled score must be an integer"),
    ("scaled_score", 59, "between 60 and 130"),
    ("scaled_score", 131, "between 60 and 130"),
    ("outcome", "", "Outcome is required"),
    ("outcome", "AS", "Outcome must be one of"),
    ("assessed_on", "2026/05/12", "Assessed-on date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _res(p, **{field: value})
    assert K2.list_results() == []


def test_create_refuses_unknown_pupil_and_duplicates():
    with pytest.raises(P.ValidationError, match="No pupil with id"):
        K2.create({"pupil_id": "P0000002", "academic_year": YEAR, "subject": "Maths",
                   "outcome": "EXS"})
    p = _pupil()
    first = _res(p, subject="Maths")
    with pytest.raises(P.ValidationError, match=f"#{first.result_id}"):
        _res(p, subject="Maths", outcome="GDS")
    assert len(K2.list_for_pupil(p.pupil_id)) == 1


# ── update / delete ──────────────────────────────────────────────────

def test_update_merges_and_refuses():
    p = _pupil()
    reading = _res(p, scaled_score=99, outcome="WTS", notes="keep")
    maths = _res(p, subject="Maths")
    up = K2.update(reading.result_id, {"scaled_score": 101, "outcome": "EXS"})
    assert (up.scaled_score, up.outcome, up.notes) == (101, "EXS", "keep")
    with pytest.raises(P.ValidationError, match="No KS2 SATs result #500"):
        K2.update(500, {})
    with pytest.raises(P.ValidationError, match="Another KS2 result"):
        K2.update(maths.result_id, {"subject": "Reading"})
    with pytest.raises(P.ValidationError, match="Outcome must be one of"):
        K2.update(maths.result_id, {"outcome": "X"})
    assert K2.get(maths.result_id).outcome == "EXS"


def test_update_can_clear_score():
    r = _res(_pupil(), scaled_score=100)
    assert K2.update(r.result_id, {"scaled_score": None}).scaled_score is None


def test_delete():
    r = _res(_pupil())
    assert K2.delete(r.result_id) is True
    assert K2.delete(r.result_id) is False


# ── listing and summaries ────────────────────────────────────────────

def test_list_results_filters():
    a, b = _pupil("6"), _pupil("5")
    _res(a, subject="Reading", outcome="EXS")
    _res(a, subject="Science", outcome="WTS")
    _res(b, subject="Reading", outcome="GDS", academic_year="2024-25")
    assert len(K2.list_results()) == 3
    assert [r.subject for r, _ in K2.list_results(pupil_id=a.pupil_id)] == [
        "Reading", "Science"]
    assert [r.pupil_id for r, _ in K2.list_results(academic_year="2024-25")] == [b.pupil_id]
    assert [r.outcome for r, _ in K2.list_results(subject="Science")] == ["WTS"]
    assert [r.outcome for r, _ in K2.list_results(outcome="GDS")] == ["GDS"]
    assert {p.pupil_id for _, p in K2.list_results(year_group="6")} == {a.pupil_id}
    with pytest.raises(P.ValidationError, match="Subject filter"):
        K2.list_results(subject="Writing")
    with pytest.raises(P.ValidationError, match="Outcome filter"):
        K2.list_results(outcome="x")
    with pytest.raises(P.ValidationError, match="Year filter"):
        K2.list_results(year_group="N")


def test_list_for_pupil_unknown():
    with pytest.raises(P.ValidationError, match="No pupil"):
        K2.list_for_pupil("P0000000")
    assert K2.list_for_pupil(_pupil().pupil_id) == []


def test_summary():
    a, b = _pupil(), _pupil()
    _res(a, subject="Reading", scaled_score=100, outcome="EXS")
    _res(a, subject="Maths", scaled_score=115, outcome="GDS")
    _res(b, subject="Reading", scaled_score=94, outcome="WTS")
    _res(b, subject="Science", outcome="EXS")
    s = K2.summary(academic_year=YEAR)
    assert s["total"] == 4
    assert s["by_outcome"]["EXS"] == 2 and s["by_outcome"]["GDS"] == 1
    assert s["by_outcome"]["WTS"] == 1 and s["by_outcome"]["NS"] == 0
    assert s["at_or_above_exs"] == 3 and s["at_or_above_exs_pct"] == 75.0
    assert s["scaled_count"] == 3
    assert s["average_scaled"] == pytest.approx((100 + 115 + 94) / 3)
    reading = K2.summary(subject="Reading")
    assert reading["total"] == 2 and reading["average_scaled"] == 97.0


def test_combined_summary_needs_exs_or_gds_in_all_three():
    met = _pupil()
    _rwm(met, "EXS", "GDS", "EXS")
    gds_all = _pupil()
    _rwm(gds_all, "GDS", "GDS", "GDS")
    one_short = _pupil()
    _rwm(one_short, "EXS", "WTS", "EXS")
    missing = _pupil()
    _rwm(missing, "EXS", "EXS", None)          # no EGPS row: not met
    absent = _pupil()
    _rwm(absent, "EXS", "EXS", "NS")
    s = K2.cohort_combined_summary(YEAR)
    assert s["academic_year"] == YEAR
    assert s["pupils_recorded"] == 5
    assert s["exs_in_RWM"] == 2
    assert s["exs_in_RWM_pct"] == 40.0


def test_combined_summary_ignores_science_and_other_years():
    only_science = _pupil()
    _res(only_science, subject="Science", outcome="GDS")
    other_year = _pupil()
    _rwm(other_year, "EXS", "EXS", "EXS", year="2024-25")
    s = K2.cohort_combined_summary(YEAR)
    assert (s["pupils_recorded"], s["exs_in_RWM"]) == (1, 0)
    assert K2.cohort_combined_summary("2024-25")["exs_in_RWM_pct"] == 100.0


def test_combined_summary_empty_and_required_year():
    assert K2.cohort_combined_summary(" 2030-31 ") == {
        "academic_year": "2030-31", "pupils_recorded": 0, "exs_in_RWM": 0,
        "exs_in_RWM_pct": 0.0}
    with pytest.raises(P.ValidationError, match="Academic year is required"):
        K2.cohort_combined_summary("  ")


def test_known_years_and_empty_summary():
    assert K2.known_years() == []
    assert K2.summary()["average_scaled"] is None
    p = _pupil()
    _res(p, academic_year="2023-24")
    _res(p, academic_year="2025-26")
    assert K2.known_years() == ["2025-26", "2023-24"]
