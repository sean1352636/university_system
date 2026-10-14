"""CLI handlers for progress reporting."""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Callable

from education_system.systems.primary.domain.operations.reporting.progress_report import (
    progress_report as data,
)
from education_system.systems.primary.domain.assessment.assessment import (
    GRADES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


@_safe
def open_progress_report() -> None:
    logger.debug("CLI: open_progress_report")
    while True:
        print("\n  -- Progress Report --")
        print("\n   1) Pupil progress profile")
        print("   2) Cohort overview (top-line)")
        print("   3) Subject summary (assessment grades)")
        print("   4) Pupils with most data points")
        print("   5) Pupil trajectory (term-by-term)")
        print("   6) Export cohort CSV")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _pupil_profile,
            "2": _cohort_overview,
            "3": _subject_summary,
            "4": _pupils_with_data,
            "5": _trajectory,
            "6": _export,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _pupil_profile() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    pp = data.pupil_progress(pid)
    p = pp.pupil
    print(f"\n  -- Progress: {p.full_name} ({p.pupil_id}, year {p.year_group}) --")
    print(f"  Data points across modules: {pp.total_data_points}")

    if pp.assessments:
        print(f"\n  Assessment records ({len(pp.assessments)}):")
        for r in pp.assessments[:10]:
            score = "-" if r.score is None else f"{r.score:g}"
            print(f"    {r.academic_year} {r.term} {r.subject}: "
                  f"{r.grade}  score={score}")
        if len(pp.assessments) > 10:
            print(f"    (+{len(pp.assessments) - 10} more)")

    if pp.mtc_results:
        print(f"\n  Multiplication Tables Check ({len(pp.mtc_results)}):")
        for r in pp.mtc_results:
            tag = ("FULL" if r.full_marks
                   else "met" if r.met_expected else "below")
            print(f"    {r.academic_year}: {r.score}/25 ({tag})")

    if pp.phonics_screening:
        print(f"\n  Phonics screening ({len(pp.phonics_screening)}):")
        for r in pp.phonics_screening:
            print(f"    {r.academic_year} attempt {r.attempt}: "
                  f"{r.score}/40 "
                  f"({'pass' if r.passed else 'fail'})")

    if pp.phonics_record:
        rec = pp.phonics_record
        print(f"\n  Phonics phase (current): {rec.phase} ({rec.status})  "
              f"last {rec.last_assessed or '-'}")

    if pp.reading_record:
        rec = pp.reading_record
        print(f"\n  Reading band (current): {rec.band} ({rec.status})  "
              f"last {rec.last_assessed or '-'}")

    if pp.eyfs_profiles:
        print(f"\n  EYFS profiles ({len(pp.eyfs_profiles)}):")
        for ay, prof in pp.eyfs_profiles:
            print(f"    {ay}: ELGs {prof.elgs_recorded}/{prof.elgs_total}, "
                  f"Expected: {prof.expected_count}, "
                  f"GLD: {'YES' if prof.has_gld else 'no'}")

    if pp.ks1_results:
        print(f"\n  KS1 SATs ({len(pp.ks1_results)}):")
        for r in pp.ks1_results:
            score = r.scaled_score if r.scaled_score is not None else "-"
            print(f"    {r.academic_year} {r.subject}: "
                  f"{r.outcome} (score={score})")

    if pp.ks2_results:
        print(f"\n  KS2 SATs ({len(pp.ks2_results)}):")
        for r in pp.ks2_results:
            score = r.scaled_score if r.scaled_score is not None else "-"
            print(f"    {r.academic_year} {r.subject}: "
                  f"{r.outcome} (score={score})")

    if pp.targets:
        print(f"\n  Targets ({len(pp.targets)}):")
        for t in pp.targets:
            print(f"    {t.academic_year} {t.subject}: {t.target_grade} "
                  f"(status: {t.status})")

    if pp.total_data_points == 0:
        print("  (no data on record)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _cohort_overview() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    s = data.cohort_overview(academic_year=ay)
    print(f"\n  -- Cohort overview "
          f"({s['academic_year'] or 'all years'}) --")
    a = s.get("assessment", {})
    print(f"\n  Assessment records: total {a.get('total', 0)}")
    if a.get("by_grade"):
        for g in GRADES:
            print(f"    {g}: {a['by_grade'].get(g, 0)}")
        print(f"    At or above EXS: {a.get('at_or_above_exs', 0)} "
              f"({a.get('at_or_above_exs_pct', 0.0):.1f}%)")

    ks1 = s.get("ks1", {})
    if ks1:
        print(f"\n  KS1: total {ks1.get('total', 0)}, "
              f">=EXS {ks1.get('at_or_above_exs', 0)} "
              f"({ks1.get('at_or_above_exs_pct', 0.0):.1f}%)")
    ks2 = s.get("ks2", {})
    if ks2:
        print(f"  KS2: total {ks2.get('total', 0)}, "
              f">=EXS {ks2.get('at_or_above_exs', 0)} "
              f"({ks2.get('at_or_above_exs_pct', 0.0):.1f}%)")
    rwm = s.get("ks2_rwm", {})
    if rwm:
        print(f"  KS2 RWM combined: {rwm.get('exs_in_RWM', 0)} of "
              f"{rwm.get('pupils_recorded', 0)} "
              f"({rwm.get('exs_in_RWM_pct', 0.0):.1f}%)")
    mtc = s.get("mtc", {})
    if mtc:
        print(f"  MTC ({mtc.get('academic_year', '-')}): "
              f"total {mtc.get('total', 0)}, "
              f"avg {mtc.get('average_score', 0.0):.1f}/25, "
              f"met {mtc.get('met_pct', 0.0):.1f}%")
    ps = s.get("phonics_screening", {})
    if ps:
        print(f"  Phonics screening ({ps.get('academic_year', '-')}): "
              f"pass rate {ps.get('pass_rate', 0.0):.1f}%")
    eyfs = s.get("eyfs_gld", {})
    if eyfs:
        print(f"  EYFS GLD: {eyfs.get('gld_count', 0)} of "
              f"{eyfs.get('pupils', 0)} "
              f"({eyfs.get('gld_pct', 0.0):.1f}%)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _subject_summary() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    term = _prompt("  Term (Autumn/Spring/Summer, blank): ").strip() or None
    subj = _prompt("  Subject (blank for all): ").strip() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Year group: ").strip() or None
    by_subject = data.cohort_subject_summary(
        academic_year=ay, term=term, subject=subj, year_group=yg)
    if not by_subject:
        print("  (no assessment data)")
        _prompt("\n  Press Enter to continue...")
        return
    print(f"\n  {'Subject':<22} {'Total':<6} "
          + " ".join(f"{g:<5}" for g in GRADES)
          + f" {'>=EXS':<6} {'%':<6}")
    print(f"  {'-'*22} {'-'*6} " + " ".join("-"*5 for _ in GRADES)
          + " " + "-"*6 + " " + "-"*6)
    for subject in sorted(by_subject):
        bucket = by_subject[subject]
        grades_str = " ".join(f"{bucket.get(g, 0):<5}" for g in GRADES)
        print(f"  {subject[:22]:<22} {bucket['total']:<6} "
              f"{grades_str} {bucket['exs_plus']:<6} "
              f"{bucket['exs_plus_pct']:<6.1f}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupils_with_data() -> None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Year group: ").strip() or None
    ay = _prompt("  Limit to academic year (blank): ").strip() or None
    rows = data.find_pupils_with_data(year_group=yg, academic_year=ay)
    print(f"\n  {len(rows)} pupil(s) with data:")
    if not rows:
        print("    (none)")
    else:
        print(f"  {'Pupil ID':<10} {'Name':<26} {'Year':<5} "
              f"{'Data points':<11}")
        print(f"  {'-'*10} {'-'*26} {'-'*5} {'-'*11}")
        for p, n in rows[:50]:
            print(f"  {p.pupil_id:<10} {p.full_name[:26]:<26} "
                  f"{p.year_group:<5} {n:<11}")
        if len(rows) > 50:
            print(f"    (+{len(rows) - 50} more)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _trajectory() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    entries = data.pupil_trajectory(pid)
    print(f"\n  {len(entries)} assessment entry/entries (oldest first):")
    if not entries:
        print("    (none)")
    else:
        print(f"  {'AcYr':<10} {'Term':<7} {'Subject':<22} {'Grade':<6} "
              f"{'Score':<6} {'Assessed':<11}")
        print(f"  {'-'*10} {'-'*7} {'-'*22} {'-'*6} {'-'*6} {'-'*11}")
        for e in entries:
            score = "-" if e["score"] is None else f"{e['score']:g}"
            print(f"  {e['academic_year']:<10} {e['term']:<7} "
                  f"{e['subject'][:22]:<22} {e['grade']:<6} "
                  f"{score:<6} {(e['assessed_on'] or '-'):<11}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _export() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    yg = _prompt("  Year group (blank for all): ").strip() or None
    path = _prompt("  Output CSV path: ").strip()
    if not path:
        return
    n = data.export_cohort_csv(Path(path).expanduser(),
                               academic_year=ay, year_group=yg)
    print(f"  Wrote {n} pupil row(s) to {path}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Progress Report": open_progress_report}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching progress_report CLI label: %s", label)
    handler()
    return True
