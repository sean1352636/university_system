"""CLI handlers for self-assessment."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.self_assessment import (
    self_assessment as data,
)
from education_system.secondarysch_system.modules.domain.assessment.self_assessment.self_assessment import (
    TERMS, STATUSES,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_table(rows: list[data.SelfAssessment]) -> None:
    if not rows:
        print("  (no assessments)")
        return
    print(f"  {'ID':<4} {'Pupil':<10} {'Yr':<3} {'Subj':<6} "
          f"{'AYear':<8} {'Term':<7} {'Date':<10} "
          f"{'Conf':<4} {'Eff':<3} {'Enj':<3} {'Avg':<5} {'Status':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*6} {'-'*8} {'-'*7} {'-'*10} "
          f"{'-'*4} {'-'*3} {'-'*3} {'-'*5} {'-'*10}")
    for a in rows:
        avg = (f"{a.average_rating:.2f}"
               if a.average_rating is not None else "-")
        print(f"  {a.assessment_id:<4} {a.pupil_id:<10} "
              f"{(a.pupil_year or '-'):<3} "
              f"{(a.subject_code or '?'):<6} "
              f"{a.academic_year:<8} {a.term:<7} {a.assessment_date:<10} "
              f"{(a.confidence_level if a.confidence_level is not None else '-'):<4} "
              f"{(a.effort_level if a.effort_level is not None else '-'):<3} "
              f"{(a.enjoyment_level if a.enjoyment_level is not None else '-'):<3} "
              f"{avg:<5} {a.status:<10}")


@_safe
def open_self_assessment() -> None:
    logger.debug("CLI: open_self_assessment")
    while True:
        print("\n  ── Self Assessment ──")
        print("   1) Record / update assessment")
        print("   2) List assessments")
        print("   3) View assessment")
        print("   4) Submit (mark Submitted)")
        print("   5) Review (add reviewer comments)")
        print("   6) Pupil summary")
        print("   7) Cohort summary")
        print("   8) Delete assessment")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _submit, "5": _review,
            "6": _pupil_summary, "7": _summary, "8": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.SelfAssessment | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                         existing.pupil_id if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"]    = ask("Subject ID",
                               existing.subject_id if existing else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                               existing.academic_year if existing
                               else None)
    f["term"]          = ask(f"Term ({'/'.join(TERMS)})",
                               existing.term if existing else "Autumn")
    f["assessment_date"] = ask(
        "Assessment date (YYYY-MM-DD, blank = today)",
        existing.assessment_date if existing else None)
    f["confidence_level"] = ask("Confidence (1-5, blank ok)",
                                  existing.confidence_level if existing
                                  else None)
    f["effort_level"]     = ask("Effort (1-5, blank ok)",
                                  existing.effort_level if existing
                                  else None)
    f["enjoyment_level"]  = ask("Enjoyment (1-5, blank ok)",
                                  existing.enjoyment_level if existing
                                  else None)
    f["strengths"]        = ask("Strengths",
                                  existing.strengths if existing
                                  else None)
    f["areas_to_improve"] = ask("Areas to improve",
                                  existing.areas_to_improve if existing
                                  else None)
    f["goals"]            = ask("Goals",
                                  existing.goals if existing else None)
    f["status"]           = ask(f"Status ({'/'.join(STATUSES)})",
                                  existing.status if existing
                                  else "Draft")
    f["reviewed_by"]      = ask("Reviewed by",
                                  existing.reviewed_by if existing
                                  else None)
    f["reviewer_comments"] = ask("Reviewer comments",
                                   existing.reviewer_comments if existing
                                   else None)
    f["reviewed_date"]    = ask("Reviewed date (YYYY-MM-DD, blank ok)",
                                  existing.reviewed_date if existing
                                  else None)
    f["notes"]            = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Record / Update Self-Assessment ──")
    fields = _collect()
    a = data.upsert(fields)
    print(f"  Saved #{a.assessment_id} for {a.pupil_id} / "
          f"{a.subject_code} ({a.academic_year} {a.term})")
    if a.average_rating is not None:
        print(f"  Avg rating: {a.average_rating}    "
              f"Status: {a.status}")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    sid_raw = _prompt("  Subject ID (blank): ")
    sid = None
    if sid_raw:
        try:
            sid = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    ay = _prompt("  Academic year (blank): ") or None
    term = _prompt(f"  Term ({'/'.join(TERMS)}, blank): ") or None
    status = _prompt(f"  Status ({'/'.join(STATUSES)}, blank): ") or None
    rows = data.list_assessments(year_group=yg, pupil_id=pid,
                                   subject_id=sid, academic_year=ay,
                                   term=term, status=status)
    print(f"\n  {len(rows)} assessment(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    aid = _ask_id("Assessment ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No assessment with that ID.")
        return
    print(f"\n  ── Self-Assessment #{a.assessment_id} ──")
    print(f"  Pupil:        {a.pupil_id} ({a.pupil_name or '-'}, "
          f"Yr {a.pupil_year or '-'})")
    print(f"  Subject:      {a.subject_code} — {a.subject_name}")
    print(f"  Year / term:  {a.academic_year} / {a.term}")
    print(f"  Date:         {a.assessment_date}    Status: {a.status}")
    print(f"  Confidence:   {a.confidence_level or '-'}")
    print(f"  Effort:       {a.effort_level or '-'}")
    print(f"  Enjoyment:    {a.enjoyment_level or '-'}")
    print(f"  Avg rating:   "
          f"{a.average_rating if a.average_rating is not None else '-'}")
    print(f"\n  Strengths:\n    {a.strengths or '-'}")
    print(f"\n  Areas to improve:\n    {a.areas_to_improve or '-'}")
    print(f"\n  Goals:\n    {a.goals or '-'}")
    print(f"\n  Reviewer:     {a.reviewed_by or '-'}")
    print(f"  Reviewed on:  {a.reviewed_date or '-'}")
    print(f"  Comments:     {a.reviewer_comments or '-'}")
    print(f"  Notes:        {a.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _submit() -> None:
    aid = _ask_id("Assessment ID")
    if aid is None:
        return
    a = data.set_status(aid, "Submitted")
    print(f"  Submitted #{a.assessment_id}.")


@_safe
def _review() -> None:
    aid = _ask_id("Assessment ID")
    if aid is None:
        return
    reviewer = _prompt("  Reviewer: ")
    if not reviewer:
        print("  Reviewer required.")
        return
    comments = _prompt("  Reviewer comments: ")
    a = data.set_status(aid, "Reviewed",
                         reviewer=reviewer,
                         reviewer_comments=comments or None)
    print(f"  Marked #{a.assessment_id} as Reviewed.")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ay = _prompt("  Academic year (blank for all): ") or None
    s = data.pupil_summary(pid, academic_year=ay)
    print(f"\n  ── {pid} ──")
    print(f"  Assessments: {s['count']}    "
          f"Avg confidence: "
          f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}    "
          f"Avg effort: "
          f"{s['avg_effort'] if s['avg_effort'] is not None else '-'}    "
          f"Avg enjoyment: "
          f"{s['avg_enjoyment'] if s['avg_enjoyment'] is not None else '-'}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _print_table(s["assessments"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    term = _prompt(f"  Term ({'/'.join(TERMS)}, blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay, term=term)
    print(f"\n  Records: {s['count']}")
    print(f"  Avg confidence: "
          f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}")
    print(f"  Avg effort:     "
          f"{s['avg_effort'] if s['avg_effort'] is not None else '-'}")
    print(f"  Avg enjoyment:  "
          f"{s['avg_enjoyment'] if s['avg_enjoyment'] is not None else '-'}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_term"]:
        print("  By term:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_term"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    aid = _ask_id("Assessment ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No assessment with that ID.")
        return
    confirm = _prompt(
        f"  Delete assessment #{aid} ({a.pupil_id} / "
        f"{a.subject_code}, {a.academic_year} {a.term})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(aid)
    print(f"  Deleted assessment #{aid}.")


_DISPATCH = {"Self Assessment": open_self_assessment}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching self_assessment CLI label: %s", label)
    handler()
    return True
