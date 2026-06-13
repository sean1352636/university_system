"""CLI handlers for assessment records."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.assessment import (
    assessment as data,
)
from education_system.primarysch_system.modules.domain.assessment.assessment import (
    GRADES, GRADE_LABELS, TERMS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'#':<5} {'Pupil':<10} {'Name':<22} {'Yr':<3} "
          f"{'AcYr':<9} {'Term':<7} {'Subject':<18} {'Gr':<4} {'Score':<6}")
    print(f"  {'-'*5} {'-'*10} {'-'*22} {'-'*3} {'-'*9} {'-'*7} {'-'*18} "
          f"{'-'*4} {'-'*6}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        score = "-" if rec.score is None else f"{rec.score:g}"
        print(f"  {rec.assessment_id:<5} {rec.pupil_id:<10} "
              f"{name[:22]:<22} {yr:<3} {rec.academic_year:<9} "
              f"{rec.term:<7} {rec.subject[:18]:<18} {rec.grade:<4} "
              f"{score:<6}")


@_safe
def open_assessment() -> None:
    logger.debug("CLI: open_assessment")
    while True:
        print("\n  -- Assessment Records --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("\n   1) List all records")
        print("   2) Filter records")
        print("   3) View pupil's record list")
        print("   4) Grade summary")
        print("   5) Record assessment")
        print("   6) Update assessment")
        print("   7) Delete assessment")
        print("   8) Show grade meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view_pupil,
            "4": _summary,
            "5": _record,
            "6": _update,
            "7": _delete,
            "8": _show_grades,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_records()
    print(f"\n  {len(rows)} record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    print(f"  Terms: {', '.join(TERMS)} (blank for any)")
    term = _prompt("  Term: ").strip().title() or None
    subj = _prompt("  Subject (blank for any): ").strip() or None
    print(f"  Grades: {', '.join(GRADES)} (blank for any)")
    grade = _prompt("  Grade: ").strip().upper() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    pid = _prompt("  Pupil ID (blank for any): ").strip() or None
    rows = data.list_records(academic_year=ay, term=term, subject=subj,
                             grade=grade, year_group=yg, pupil_id=pid)
    print(f"\n  {len(rows)} record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_for_pupil(pid)
    print(f"\n  {len(rows)} record(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for r in rows:
            score = "-" if r.score is None else f"{r.score:g}"
            print(f"    #{r.assessment_id} {r.academic_year} {r.term} "
                  f"{r.subject}: {r.grade}  score={score}  "
                  f"{r.assessed_on or '-'}  {r.comment or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    print(f"  Terms: {', '.join(TERMS)} (blank for any)")
    term = _prompt("  Term: ").strip().title() or None
    subj = _prompt("  Subject (blank for any): ").strip() or None
    s = data.grade_summary(academic_year=ay, term=term, subject=subj)
    print(f"\n  -- Summary --")
    print(f"  Total records: {s['total']}")
    for g in GRADES:
        print(f"  {g}: {s['by_grade'].get(g, 0)}")
    print(f"  At or above EXS: {s['at_or_above_exs']} "
          f"({s['at_or_above_exs_pct']:.1f}%)")
    if s['average_score'] is not None:
        print(f"  Average score: {s['average_score']:.1f}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Terms: {', '.join(TERMS)})")
    print(f"  (Grades: {', '.join(GRADES)})")
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    out["term"]          = _prompt(f"  Term [{d.get('term','')}]: ") or d.get("term", "")
    out["subject"]       = _prompt(f"  Subject [{d.get('subject','')}]: ") or d.get("subject", "")
    out["grade"]         = _prompt(f"  Grade [{d.get('grade','')}]: ") or d.get("grade", "")
    score_default = "" if d.get("score") in (None, "") else f"{d['score']:g}"
    out["score"]         = _prompt(f"  Score 0-100 (optional) [{score_default}]: ") or score_default
    out["assessed_on"]   = _prompt(f"  Assessed on YYYY-MM-DD [{d.get('assessed_on','')}]: ") or d.get("assessed_on", "")
    out["comment"]       = _prompt(f"  Comment [{d.get('comment','')}]: ") or d.get("comment", "")
    return out


@_safe
def _record() -> None:
    print("\n  -- Record Assessment --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created #{rec.assessment_id}: pupil {rec.pupil_id} "
          f"{rec.academic_year} {rec.term} {rec.subject} -> {rec.grade}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Assessment ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No assessment #{raw}")
        return
    defaults = {
        "pupil_id": existing.pupil_id,
        "academic_year": existing.academic_year,
        "term": existing.term,
        "subject": existing.subject,
        "grade": existing.grade,
        "score": existing.score,
        "assessed_on": existing.assessed_on or "",
        "comment": existing.comment or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated #{rec.assessment_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Assessment ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete assessment #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such assessment'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_grades() -> None:
    print("\n  -- Attainment grades --")
    for g in GRADES:
        print(f"   {g}  — {GRADE_LABELS[g]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Assessment Records": open_assessment}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching assessment CLI label: %s", label)
    handler()
    return True
