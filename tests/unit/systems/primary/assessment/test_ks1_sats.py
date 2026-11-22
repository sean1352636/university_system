"""KS1 SATs results (domain.assessment.ks1_sats.ks1_sats)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.ks1_sats import ks1_sats as K1
from education_system.systems.primary.domain.learners.pupils import pupils as P

YEAR = "2025-26"
_n = 0


def _pupil(year="2"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-03-01"})


def _res(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": YEAR, "subject": "Reading",
            "outcome": "EXS"}
    data.update(extra)
    return K1.create(data)


# ── suggested outcome ────────────────────────────────────────────────

@pytest.mark.parametrize("score, outcome", [
    (None, None), (60, "WTS"), (84, "WTS"), (85, "WTS"), (99, "WTS"),
    (100, "EXS"), (109, "EXS"), (110, "GDS"), (130, "GDS"),
])
def test_suggest_outcome_bands(score, outcome):
    assert K1.suggest_outcome(score) == outcome


def test_at_or_above_expected_is_exs_or_gds_only():
    p = _pupil()
    flags = {}
    for subj, outcome in zip(K1.SUBJECTS, ("GDS", "WTS", "NS")):
        flags[outcome] = _res(p, subject=subj, outcome=outcome).at_or_above_expected
    assert flags == {"GDS": True, "WTS": False, "NS": False}


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_and_reads_back():
    p = _pupil()
    r = _res(p, subject="Maths", scaled_score="103", outcome=" exs ",
             assessed_on="2026-05-14", notes="  calm  ")
    got = K1.get(r.result_id)
    assert got == r
    assert (got.subject, got.scaled_score, got.outcome, got.assessed_on, got.notes) == (
        "Maths", 103, "EXS", "2026-05-14", "calm")


def test_teacher_assessment_without_score():
    r = _res(_pupil(), scaled_score="", outcome="PKS")
    assert r.scaled_score is None and r.outcome == "PKS"


def test_scaled_score_limits_are_inclusive():
    p = _pupil()
    assert _res(p, subject="Reading", scaled_score=60, outcome="BLW").scaled_score == 60
    assert _res(p, subject="Maths", scaled_score=130, outcome="GDS").scaled_score == 130


def test_get_unknown_is_none():
    assert K1.get(1234) is None


@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", "", "Pupil ID is required"),
    ("academic_year", "", "Academic year is required"),
    ("academic_year", "Y2025", "Academic year must look like"),
    ("subject", "", "Subject is required"),
    ("subject", "Writing", "Subject must be one of Reading, Maths, EGPS"),
    ("subject", "Science", "Subject must be one of"),
    ("scaled_score", "one hundred", "Scaled score must be an integer"),
    ("scaled_score", "100.5", "Scaled score must be an integer"),
    ("scaled_score", 59, "between 60 and 130"),
    ("scaled_score", 131, "between 60 and 130"),
    ("outcome", "", "Outcome is required"),
    ("outcome", "HNM", "Outcome must be one of"),
    ("assessed_on", "14-05-2026", "Assessed-on date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _res(p, **{field: value})
    assert K1.list_results() == []


def test_create_refuses_unknown_pupil():
    with pytest.raises(P.ValidationError, match="No pupil with id P0000001"):
        K1.create({"pupil_id": "P0000001", "academic_year": YEAR, "subject": "Reading",
                   "outcome": "EXS"})


def test_one_result_per_pupil_year_subject():
    p = _pupil()
    first = _res(p)
    with pytest.raises(P.ValidationError, match=f"already exists \\(#{first.result_id}\\)"):
        _res(p, outcome="GDS")
    _res(p, academic_year="2026-27")
    _res(p, subject="EGPS")
    assert len(K1.list_for_pupil(p.pupil_id)) == 3


# ── update / delete ──────────────────────────────────────────────────

def test_update_merges_fields():
    r = _res(_pupil(), scaled_score=98, outcome="WTS", notes="keep")
    up = K1.update(r.result_id, {"scaled_score": 104, "outcome": "exs"})
    assert (up.scaled_score, up.outcome, up.notes) == (104, "EXS", "keep")
    assert K1.get(r.result_id).outcome == "EXS"


def test_update_refusals():
    p = _pupil()
    _res(p, subject="Reading")
    maths = _res(p, subject="Maths")
    with pytest.raises(P.ValidationError, match="No KS1 SATs result #999"):
        K1.update(999, {"outcome": "EXS"})
    with pytest.raises(P.ValidationError, match="Another KS1 result"):
        K1.update(maths.result_id, {"subject": "Reading"})
    with pytest.raises(P.ValidationError, match="between 60 and 130"):
        K1.update(maths.result_id, {"scaled_score": 200})
    with pytest.raises(P.ValidationError, match="No pupil"):
        K1.update(maths.result_id, {"pupil_id": "P0000000"})
    assert K1.get(maths.result_id).subject == "Maths"


def test_delete():
    r = _res(_pupil())
    assert K1.delete(r.result_id) is True
    assert K1.get(r.result_id) is None
    assert K1.delete(r.result_id) is False


# ── listing and summary ──────────────────────────────────────────────

def _seed():
    a, b = _pupil("2"), _pupil("3")
    _res(a, subject="Reading", scaled_score=104, outcome="EXS")
    _res(a, subject="Maths", scaled_score=112, outcome="GDS")
    _res(b, subject="Reading", scaled_score=95, outcome="WTS")
    _res(b, subject="Maths", outcome="NS")
    _res(a, academic_year="2024-25", subject="EGPS", scaled_score=90, outcome="WTS")
    return a, b


def test_list_results_filters_and_order():
    a, b = _seed()
    rows = K1.list_results()
    assert [r.academic_year for r, _ in rows] == ["2025-26"] * 4 + ["2024-25"]
    assert [r.subject for r, _ in rows][:4] == ["Maths", "Maths", "Reading", "Reading"]
    assert len(K1.list_results(academic_year=YEAR)) == 4
    assert len(K1.list_results(subject="Maths")) == 2
    assert [r.pupil_id for r, _ in K1.list_results(outcome="GDS")] == [a.pupil_id]
    assert len(K1.list_results(pupil_id=b.pupil_id)) == 2
    assert {p.pupil_id for _, p in K1.list_results(year_group="3")} == {b.pupil_id}


@pytest.mark.parametrize("kwargs, message", [
    ({"subject": "Science"}, "Subject filter"),
    ({"outcome": "exs"}, "Outcome filter"),
    ({"year_group": "7"}, "Year filter"),
])
def test_list_results_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        K1.list_results(**kwargs)


def test_list_for_pupil():
    a, _ = _seed()
    assert [(r.academic_year, r.subject) for r in K1.list_for_pupil(a.pupil_id)] == [
        ("2025-26", "Maths"), ("2025-26", "Reading"), ("2024-25", "EGPS")]
    with pytest.raises(P.ValidationError, match="No pupil"):
        K1.list_for_pupil("P0000000")


def test_summary_for_a_year():
    _seed()
    s = K1.summary(academic_year=YEAR)
    assert s["total"] == 4
    assert s["by_outcome"] == {"BLW": 0, "PKS": 0, "WTS": 1, "EXS": 1, "GDS": 1, "NS": 1}
    assert s["at_or_above_exs"] == 2 and s["at_or_above_exs_pct"] == 50.0
    # Scores 104, 112, 95 (NS has none): 311 / 3.
    assert s["scaled_count"] == 3
    assert s["average_scaled"] == pytest.approx(311 / 3)


def test_summary_by_subject_and_all_years():
    _seed()
    s = K1.summary(subject="Reading")
    assert s["total"] == 2 and s["average_scaled"] == pytest.approx(99.5)
    assert K1.summary()["total"] == 5
    assert K1.summary()["at_or_above_exs_pct"] == pytest.approx(40.0)


def test_empty_database():
    assert K1.list_results() == []
    assert K1.known_years() == []
    s = K1.summary()
    assert s["total"] == 0 and s["at_or_above_exs_pct"] == 0.0
    assert s["average_scaled"] is None and s["scaled_count"] == 0


def test_known_years():
    _seed()
    assert K1.known_years() == ["2025-26", "2024-25"]
