"""Progress reporting
(systems.primary.domain.operations.reporting.progress_report.progress_report)."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.primary.domain.assessment import assessment as AS
from education_system.systems.primary.domain.assessment.eyfs_profile import eyfs_profile as EY
from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats as K2
from education_system.systems.primary.domain.assessment.mtc import mtc as MTC
from education_system.systems.primary.domain.assessment.phonics import phonics as PH
from education_system.systems.primary.domain.assessment.phonics_screening import (
    phonics_screening as PS,
)
from education_system.systems.primary.domain.assessment.reading_levels import (
    reading_levels as RL,
)
from education_system.systems.primary.domain.assessment.target_setting import (
    target_setting as TS,
)
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.progress_report import (
    progress_report as PR,
)

AY, PREV = "2025-26", "2024-25"


def _pupil(first="Ada", last="Lovelace", year="4"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2017-01-01"})


def _grade(pupil, subject, grade, *, term="Autumn", year=AY, score=None):
    return AS.create({"pupil_id": pupil.pupil_id, "academic_year": year, "term": term,
                      "subject": subject, "grade": grade, "score": score})


# ── pupil_progress ──

def test_pupil_progress_collects_every_source():
    p = _pupil()
    _grade(p, "Maths", "EXS")
    _grade(p, "Reading", "GDS", term="Spring")
    MTC.create({"pupil_id": p.pupil_id, "academic_year": AY, "score": 22})
    PS.create({"pupil_id": p.pupil_id, "academic_year": PREV, "score": 30})
    PS.create({"pupil_id": p.pupil_id, "academic_year": PREV, "attempt": 2, "score": 35})
    PH.record_assessment(p.pupil_id, {"phase": "5", "status": "working"})
    RL.record_assessment(p.pupil_id, {"band": "Gold", "status": "secure"})
    TS.create({"pupil_id": p.pupil_id, "academic_year": AY, "subject": "Maths",
               "target_grade": "GDS"})
    EY.set_elg(p.pupil_id, "2021-22", "CL01", "Expected")
    pp = PR.pupil_progress(f" {p.pupil_id} ")
    assert pp.pupil.pupil_id == p.pupil_id
    assert len(pp.assessments) == 2 and len(pp.mtc_results) == 1
    assert [r.attempt for r in pp.phonics_screening] == [1, 2]
    assert (pp.phonics_record.phase, pp.reading_record.band) == ("5", "Gold")
    assert [t.subject for t in pp.targets] == ["Maths"]
    assert [ay for ay, _ in pp.eyfs_profiles] == ["2021-22"]
    assert pp.ks1_results == [] and pp.ks2_results == []
    # 2 + 1 + 2 + 1 target + 1 eyfs + phonics record + reading record
    assert pp.total_data_points == 9


def test_pupil_progress_empty_pupil():
    pp = PR.pupil_progress(_pupil().pupil_id)
    assert pp.total_data_points == 0
    assert pp.phonics_record is None and pp.reading_record is None


def test_pupil_progress_refusals():
    with pytest.raises(PR.ValidationError, match="Pupil ID is required"):
        PR.pupil_progress("  ")
    with pytest.raises(PR.ValidationError, match="No pupil with id GHOST"):
        PR.pupil_progress("GHOST")


# ── cohort_subject_summary ──

def test_cohort_subject_summary_figures():
    a, b, c = _pupil("A", "A", "4"), _pupil("B", "B", "4"), _pupil("C", "C", "5")
    _grade(a, "Maths", "EXS")
    _grade(b, "Maths", "WTS")
    _grade(c, "Maths", "GDS")
    _grade(a, "Reading", "BLW")
    _grade(a, "Maths", "GDS", term="Spring")
    out = PR.cohort_subject_summary(term="Autumn")
    assert out["Maths"] == {"BLW": 0, "WTS": 1, "EXS": 1, "GDS": 1, "total": 3,
                            "exs_plus": 2, "exs_plus_pct": 66.67}
    assert out["Reading"]["exs_plus_pct"] == 0.0
    y4 = PR.cohort_subject_summary(year_group="4", subject="Maths")
    assert (y4["Maths"]["total"], y4["Maths"]["exs_plus"], y4["Maths"]["exs_plus_pct"]) == \
        (3, 2, 66.67)
    assert PR.cohort_subject_summary(academic_year=PREV) == {}


def test_cohort_subject_summary_year_filter_validated():
    with pytest.raises(PR.ValidationError, match="Year filter must be one of"):
        PR.cohort_subject_summary(year_group="9")


# ── cohort_overview ──

def test_cohort_overview_with_year():
    a, b = _pupil("A", "A", "6"), _pupil("B", "B", "6")
    _grade(a, "Maths", "EXS", score=80)
    _grade(b, "Maths", "WTS", score=60)
    for subj in ("Reading", "Maths", "EGPS"):
        K2.create({"pupil_id": a.pupil_id, "academic_year": AY, "subject": subj,
                   "outcome": "EXS", "scaled_score": 104})
    K2.create({"pupil_id": b.pupil_id, "academic_year": AY, "subject": "Reading",
               "outcome": "WTS", "scaled_score": 95})
    MTC.create({"pupil_id": a.pupil_id, "academic_year": AY, "score": 25})
    MTC.create({"pupil_id": b.pupil_id, "academic_year": AY, "score": 15})
    PS.create({"pupil_id": a.pupil_id, "academic_year": AY, "score": 32})
    out = PR.cohort_overview(academic_year=AY)
    assert out["academic_year"] == AY
    assert (out["assessment"]["total"], out["assessment"]["at_or_above_exs"],
            out["assessment"]["average_score"]) == (2, 1, 70.0)
    assert (out["ks2"]["total"], out["ks2"]["at_or_above_exs"]) == (4, 3)
    assert (out["ks2_rwm"]["pupils_recorded"], out["ks2_rwm"]["exs_in_RWM"],
            out["ks2_rwm"]["exs_in_RWM_pct"]) == (2, 1, 50.0)
    assert (out["mtc"]["total"], out["mtc"]["met_expected"], out["mtc"]["full_marks"],
            out["mtc"]["average_score"]) == (2, 1, 1, 20.0)
    assert (out["phonics_screening"]["passed"], out["phonics_screening"]["pass_rate"]) == \
        (1, 100.0)
    assert out["eyfs_gld"]["pupils"] == 0
    assert out["ks1"]["total"] == 0


def test_cohort_overview_without_year_skips_year_only_measures():
    out = PR.cohort_overview()
    assert out["academic_year"] is None
    assert out["ks2_rwm"] == out["mtc"] == out["phonics_screening"] == out["eyfs_gld"] == {}
    assert out["assessment"]["total"] == 0


# ── trajectory ──

def test_pupil_trajectory_is_chronological():
    p = _pupil()
    _grade(p, "Maths", "GDS", term="Summer", score=90)
    _grade(p, "Maths", "WTS", term="Autumn", year=PREV)
    _grade(p, "Reading", "EXS", term="Spring")
    _grade(p, "English", "EXS", term="Spring")
    _grade(p, "Maths", "EXS", term="Autumn")
    steps = PR.pupil_trajectory(p.pupil_id)
    assert [(s["academic_year"], s["term"], s["subject"]) for s in steps] == [
        (PREV, "Autumn", "Maths"), (AY, "Autumn", "Maths"), (AY, "Spring", "English"),
        (AY, "Spring", "Reading"), (AY, "Summer", "Maths")]
    assert [s["grade_rank"] for s in steps] == [2, 3, 3, 3, 4]
    assert steps[-1]["score"] == 90.0


def test_pupil_trajectory_unknown_pupil_is_empty():
    assert PR.pupil_trajectory("NOBODY") == []


# ── find_pupils_with_data ──

def test_find_pupils_with_data_sorted_and_filtered():
    a, b, c = _pupil("A", "A", "4"), _pupil("B", "B", "4"), _pupil("C", "C", "5")
    _grade(a, "Maths", "EXS")
    _grade(b, "Maths", "EXS")
    _grade(b, "Reading", "EXS", year=PREV)
    MTC.create({"pupil_id": b.pupil_id, "academic_year": AY, "score": 20})
    _grade(c, "Maths", "WTS", year=PREV)
    _pupil("D", "D", "4")  # no data: left out
    assert [(p.pupil_id, n) for p, n in PR.find_pupils_with_data()] == \
        [(b.pupil_id, 3), (a.pupil_id, 1), (c.pupil_id, 1)]
    assert [(p.pupil_id, n) for p, n in PR.find_pupils_with_data(year_group="5")] == \
        [(c.pupil_id, 1)]
    assert [(p.pupil_id, n) for p, n in PR.find_pupils_with_data(academic_year=AY)] == \
        [(b.pupil_id, 2), (a.pupil_id, 1)]
    with pytest.raises(PR.ValidationError, match="Year filter must be one of"):
        PR.find_pupils_with_data(year_group="Y4")


# ── export ──

def _read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_export_cohort_csv_values(tmp_path):
    a, b = _pupil("Amy", "Ash", "4"), _pupil("Ben", "Birch", "5")
    _grade(a, "Maths", "EXS")
    MTC.create({"pupil_id": a.pupil_id, "academic_year": AY, "score": 23})
    PS.create({"pupil_id": a.pupil_id, "academic_year": PREV, "score": 20})
    PS.create({"pupil_id": a.pupil_id, "academic_year": PREV, "attempt": 2, "score": 33})
    PH.record_assessment(a.pupil_id, {"phase": "6", "status": "secure"})
    RL.record_assessment(a.pupil_id, {"band": "Lime", "status": "working"})
    TS.create({"pupil_id": a.pupil_id, "academic_year": AY, "subject": "Maths",
               "target_grade": "GDS"})
    TS.create({"pupil_id": a.pupil_id, "academic_year": AY, "subject": "Reading",
               "target_grade": "EXS", "status": "met"})
    for subj in ("Reading", "Maths"):
        K2.create({"pupil_id": b.pupil_id, "academic_year": AY, "subject": subj,
                   "outcome": "EXS"})
    out = tmp_path / "sub" / "cohort.csv"
    assert PR.export_cohort_csv(out) == 2
    rows = {r["pupil_id"]: r for r in _read(out)}
    ra = rows[a.pupil_id]
    assert (ra["full_name"], ra["year_group"], ra["assessments_recorded"],
            ra["latest_assessment_grade"], ra["latest_assessment_subject"],
            ra["latest_assessment_term"], ra["latest_assessment_year"]) == \
        ("Amy Ash", "4", "1", "EXS", "Maths", "Autumn", AY)
    assert (ra["mtc_score"], ra["phonics_screen_passed"], ra["phonics_current_phase"],
            ra["reading_band"], ra["open_targets"]) == ("23", "yes", "6", "Lime", "1")
    rb = rows[b.pupil_id]
    assert (rb["ks2_subjects"], rb["ks1_subjects"], rb["mtc_score"],
            rb["phonics_screen_passed"], rb["latest_assessment_grade"]) == \
        ("2", "0", "", "", "")


def test_export_cohort_csv_year_filters(tmp_path):
    a = _pupil("Amy", "Ash", "4")
    _pupil("Ben", "Birch", "5")
    _grade(a, "Maths", "EXS", year=PREV)
    PS.create({"pupil_id": a.pupil_id, "academic_year": PREV, "score": 10})
    out = tmp_path / "y4.csv"
    assert PR.export_cohort_csv(out, academic_year=AY, year_group="4") == 1
    (row,) = _read(out)
    assert (row["assessments_recorded"], row["latest_assessment_grade"],
            row["phonics_screen_passed"]) == ("0", "", "")
    assert PR.export_cohort_csv(tmp_path / "prev.csv", academic_year=PREV) == 2
    prev = {r["pupil_id"]: r for r in _read(tmp_path / "prev.csv")}
    assert prev[a.pupil_id]["phonics_screen_passed"] == "no"
    with pytest.raises(PR.ValidationError, match="Year filter must be one of"):
        PR.export_cohort_csv(tmp_path / "bad.csv", year_group="7")


def test_export_latest_assessment_is_the_latest_term(tmp_path):
    a = _pupil()
    _grade(a, "Maths", "WTS", term="Autumn")
    _grade(a, "Maths", "GDS", term="Summer")
    out = tmp_path / "latest.csv"
    PR.export_cohort_csv(out)
    (row,) = _read(out)
    assert (row["latest_assessment_term"], row["latest_assessment_grade"]) == ("Summer", "GDS")


def test_export_empty_school_writes_header(tmp_path):
    out = tmp_path / "empty.csv"
    assert PR.export_cohort_csv(out) == 0
    assert out.read_text(encoding="utf-8").startswith("pupil_id,full_name,year_group,")
