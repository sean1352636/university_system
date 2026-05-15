"""Progress reporting — read-only roll-ups across the assessment modules.

This module pulls data from several existing modules and presents it
back as a coherent picture of a pupil's progress:

* ``assessment``        — termly attainment grades (BLW/WTS/EXS/GDS)
* ``mtc``               — Year 4 Multiplication Tables Check
* ``ks1_sats``          — End of KS1 SATs
* ``ks2_sats``          — End of KS2 SATs
* ``phonics``           — Letters & Sounds phase tracker
* ``phonics_screening`` — Year 1 phonics screening check
* ``reading_levels``    — Book band tracker
* ``eyfs_profile``      — End-of-Reception ELG profile (GLD)
* ``target_setting``    — Pupil targets

Nothing here writes data; it reads existing tables and shapes the
results for the CLI/GUI views.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.primarysch_system.modules.domain.assessment import (
    assessment as assessment_data,
)
from education_system.primarysch_system.modules.domain.assessment.assessment import (
    GRADES, GRADE_RANK,
)
from education_system.primarysch_system.modules.domain.eyfs_profile import (
    eyfs_profile as eyfs_data,
)
from education_system.primarysch_system.modules.domain.ks1_sats import (
    ks1_sats as ks1_data,
)
from education_system.primarysch_system.modules.domain.ks2_sats import (
    ks2_sats as ks2_data,
)
from education_system.primarysch_system.modules.domain.mtc import (
    mtc as mtc_data,
)
from education_system.primarysch_system.modules.domain.phonics import (
    phonics as phonics_data,
)
from education_system.primarysch_system.modules.domain.phonics_screening import (
    phonics_screening as phonics_screen_data,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
)
from education_system.primarysch_system.modules.domain.reading_levels import (
    reading_levels as reading_data,
)
from education_system.primarysch_system.modules.domain.target_setting import (
    target_setting as targets_data,
)

logger = logging.getLogger(__name__)


@dataclass
class PupilProgress:
    pupil: Pupil
    assessments: list = field(default_factory=list)        # AssessmentRecord
    mtc_results: list = field(default_factory=list)        # MTCResult
    ks1_results: list = field(default_factory=list)        # KS1Result
    ks2_results: list = field(default_factory=list)        # KS2Result
    phonics_screening: list = field(default_factory=list)  # ScreeningResult
    phonics_record: Any = None                              # PhonicsRecord|None
    reading_record: Any = None                              # ReadingLevelRecord|None
    eyfs_profiles: list = field(default_factory=list)      # [(year, PupilProfile)]
    targets: list = field(default_factory=list)            # Target

    @property
    def total_data_points(self) -> int:
        n = (len(self.assessments) + len(self.mtc_results)
             + len(self.ks1_results) + len(self.ks2_results)
             + len(self.phonics_screening) + len(self.targets)
             + len(self.eyfs_profiles))
        if self.phonics_record is not None:
            n += 1
        if self.reading_record is not None:
            n += 1
        return n


def _safe_call(label: str, fn, *args, **kwargs):
    """Call ``fn`` and return its result, but turn data-layer failures
    into a logged warning + an empty fallback. Used so a single broken
    module doesn't take down the whole report."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("progress_report: %s failed", label)
        return None


def pupil_progress(pupil_id: str) -> PupilProgress:
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    p = pupils_data.get_pupil(pid)
    if p is None:
        raise ValidationError(f"No pupil with id {pid}")

    pp = PupilProgress(pupil=p)
    pp.assessments = _safe_call(
        "assessment.list_for_pupil",
        assessment_data.list_for_pupil, pid) or []
    pp.mtc_results = _safe_call(
        "mtc.list_for_pupil",
        mtc_data.list_for_pupil, pid) or []
    pp.ks1_results = _safe_call(
        "ks1.list_for_pupil",
        ks1_data.list_for_pupil, pid) or []
    pp.ks2_results = _safe_call(
        "ks2.list_for_pupil",
        ks2_data.list_for_pupil, pid) or []
    pp.phonics_screening = _safe_call(
        "phonics_screening.list_for_pupil",
        phonics_screen_data.list_for_pupil, pid) or []
    pp.phonics_record = _safe_call(
        "phonics.get_record",
        phonics_data.get_record, pid)
    pp.reading_record = _safe_call(
        "reading.get_record",
        reading_data.get_record, pid)
    pp.targets = _safe_call(
        "targets.list_for_pupil",
        targets_data.list_for_pupil, pid) or []

    # EYFS profiles are stored per year — pull every year on record and
    # surface the ones with at least one ELG entry.
    eyfs_years = _safe_call("eyfs.known_years",
                            eyfs_data.known_years) or []
    profiles: list[tuple[str, Any]] = []
    for ay in eyfs_years:
        prof = _safe_call("eyfs.get_profile",
                          eyfs_data.get_profile, pid, ay)
        if prof and prof.elgs_recorded:
            profiles.append((ay, prof))
    pp.eyfs_profiles = profiles
    return pp


def cohort_subject_summary(
    *, academic_year: str | None = None,
    term: str | None = None,
    subject: str | None = None,
    year_group: str | None = None,
) -> dict[str, Any]:
    """Per-subject attainment roll-up from ``assessment_records``.

    Returns ``{ subject: {grade: count, ..., total, exs_plus, exs_plus_pct} }``.
    """
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    rows = _safe_call(
        "assessment.list_records",
        assessment_data.list_records,
        academic_year=academic_year, term=term, subject=subject,
        year_group=year_group,
    ) or []
    by_subject: dict[str, dict[str, Any]] = {}
    for rec, _p in rows:
        bucket = by_subject.setdefault(
            rec.subject,
            {g: 0 for g in GRADES} | {
                "total": 0, "exs_plus": 0, "exs_plus_pct": 0.0,
            },
        )
        bucket[rec.grade] = bucket.get(rec.grade, 0) + 1
        bucket["total"] = bucket["total"] + 1
        if rec.grade in ("EXS", "GDS"):
            bucket["exs_plus"] = bucket["exs_plus"] + 1
    for subj, bucket in by_subject.items():
        total = bucket["total"]
        bucket["exs_plus_pct"] = (
            round(bucket["exs_plus"] / total * 100.0, 2) if total else 0.0)
    return by_subject


def cohort_overview(
    *, academic_year: str | None = None,
) -> dict[str, Any]:
    """A top-line view across modules.

    Currently surfaces:
      * assessment totals (by grade)
      * MTC year summary
      * KS1 SATs summary
      * KS2 SATs summary + RWM combined %
      * Phonics screening pass rate
    """
    out: dict[str, Any] = {"academic_year": academic_year}

    a_summary = _safe_call("assessment.grade_summary",
                           assessment_data.grade_summary,
                           academic_year=academic_year) or {}
    out["assessment"] = a_summary

    ks1 = _safe_call("ks1.summary", ks1_data.summary,
                     academic_year=academic_year) or {}
    out["ks1"] = ks1

    ks2 = _safe_call("ks2.summary", ks2_data.summary,
                     academic_year=academic_year) or {}
    out["ks2"] = ks2

    if academic_year:
        out["ks2_rwm"] = _safe_call(
            "ks2.cohort_combined_summary",
            ks2_data.cohort_combined_summary, academic_year) or {}
        out["mtc"] = _safe_call(
            "mtc.year_summary",
            mtc_data.year_summary, academic_year) or {}
        out["phonics_screening"] = _safe_call(
            "phonics_screening.year_summary",
            phonics_screen_data.year_summary, academic_year) or {}
        out["eyfs_gld"] = _safe_call(
            "eyfs.cohort_summary",
            eyfs_data.cohort_summary, academic_year) or {}
    else:
        out["ks2_rwm"] = {}
        out["mtc"] = {}
        out["phonics_screening"] = {}
        out["eyfs_gld"] = {}

    return out


def pupil_trajectory(pupil_id: str) -> list[dict[str, Any]]:
    """Return a chronological list of assessment grades for a pupil,
    one entry per (year, term, subject), sorted oldest first.
    """
    rows = _safe_call("assessment.list_for_pupil",
                      assessment_data.list_for_pupil, pupil_id) or []
    out: list[dict[str, Any]] = []
    for rec in rows:
        out.append({
            "academic_year": rec.academic_year,
            "term": rec.term,
            "subject": rec.subject,
            "grade": rec.grade,
            "grade_rank": GRADE_RANK.get(rec.grade, 0),
            "score": rec.score,
            "assessed_on": rec.assessed_on,
            "comment": rec.comment,
        })
    # Order by year then term sequence (Autumn -> Spring -> Summer) then subject.
    term_order = {"Autumn": 0, "Spring": 1, "Summer": 2}
    out.sort(key=lambda e: (
        e["academic_year"], term_order.get(e["term"], 9), e["subject"]))
    return out


def find_pupils_with_data(
    *, year_group: str | None = None,
    academic_year: str | None = None,
) -> list[tuple[Pupil, int]]:
    """List pupils with at least one progress data-point, sorted by
    total data-points descending. ``academic_year`` filters the
    assessment data scan only.
    """
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    pupils = pupils_data.list_pupils()
    if year_group:
        pupils = [p for p in pupils if p.year_group == year_group]
    out: list[tuple[Pupil, int]] = []
    for p in pupils:
        try:
            pp = pupil_progress(p.pupil_id)
        except Exception:
            logger.exception("pupil_progress(%s) failed", p.pupil_id)
            continue
        n = pp.total_data_points
        if academic_year:
            n = sum(1 for r in pp.assessments
                    if r.academic_year == academic_year)
            n += sum(1 for r in pp.mtc_results
                     if r.academic_year == academic_year)
            n += sum(1 for r in pp.ks1_results
                     if r.academic_year == academic_year)
            n += sum(1 for r in pp.ks2_results
                     if r.academic_year == academic_year)
            n += sum(1 for r in pp.phonics_screening
                     if r.academic_year == academic_year)
            n += sum(1 for r in pp.targets
                     if r.academic_year == academic_year)
            n += sum(1 for ay, _prof in pp.eyfs_profiles
                     if ay == academic_year)
        if n > 0:
            out.append((p, n))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def export_cohort_csv(path: str | Path,
                      *, academic_year: str | None = None,
                      year_group: str | None = None) -> int:
    """Export a one-row-per-pupil cohort snapshot."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pupils = pupils_data.list_pupils()
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        pupils = [pp for pp in pupils if pp.year_group == year_group]
    headers = [
        "pupil_id", "full_name", "year_group",
        "assessments_recorded", "latest_assessment_grade",
        "latest_assessment_subject", "latest_assessment_term",
        "latest_assessment_year",
        "mtc_score", "ks1_subjects", "ks2_subjects",
        "phonics_screen_passed", "phonics_current_phase",
        "reading_band", "open_targets",
    ]
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for pupil in pupils:
                try:
                    pp = pupil_progress(pupil.pupil_id)
                except Exception:
                    logger.exception("pupil_progress(%s) failed",
                                     pupil.pupil_id)
                    continue
                a_in_year = [r for r in pp.assessments
                             if academic_year is None
                             or r.academic_year == academic_year]
                latest = a_in_year[0] if a_in_year else None
                mtc_in_year = [r for r in pp.mtc_results
                               if academic_year is None
                               or r.academic_year == academic_year]
                ks1_in_year = [r for r in pp.ks1_results
                               if academic_year is None
                               or r.academic_year == academic_year]
                ks2_in_year = [r for r in pp.ks2_results
                               if academic_year is None
                               or r.academic_year == academic_year]
                ps_in_year = [r for r in pp.phonics_screening
                              if academic_year is None
                              or r.academic_year == academic_year]
                ps_passed = ""
                if ps_in_year:
                    ps_passed = "yes" if any(r.passed for r in ps_in_year) else "no"
                open_targets = sum(1 for t in pp.targets if t.is_open)
                writer.writerow([
                    pupil.pupil_id, pupil.full_name, pupil.year_group,
                    len(a_in_year),
                    latest.grade if latest else "",
                    latest.subject if latest else "",
                    latest.term if latest else "",
                    latest.academic_year if latest else "",
                    mtc_in_year[0].score if mtc_in_year else "",
                    len({r.subject for r in ks1_in_year}),
                    len({r.subject for r in ks2_in_year}),
                    ps_passed,
                    pp.phonics_record.phase if pp.phonics_record else "",
                    pp.reading_record.band if pp.reading_record else "",
                    open_targets,
                ])
    except OSError as e:
        logger.exception("export_cohort_csv failed writing %s", p)
        raise ValidationError(f"Could not write CSV: {e}") from e
    logger.info("Progress export wrote %d row(s) to %s", len(pupils), p)
    return len(pupils)
