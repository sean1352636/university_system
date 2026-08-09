"""CLI handlers for KS2 SATs results."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.assessment.ks2_sats import (
    ks2_sats as data,
)
from education_system.systems.primary.domain.assessment.ks2_sats.ks2_sats import (
    OUTCOMES, OUTCOME_LABELS, SUBJECTS,
    SCALED_SCORE_MAX, SCALED_SCORE_MIN,
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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no results)")
        return
    print(f"  {'#':<5} {'Pupil':<10} {'Name':<22} {'Yr':<3} "
          f"{'AcYr':<9} {'Subject':<10} {'Score':<6} {'Outcome':<8}")
    print(f"  {'-'*5} {'-'*10} {'-'*22} {'-'*3} {'-'*9} {'-'*10} "
          f"{'-'*6} {'-'*8}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        score = "-" if rec.scaled_score is None else str(rec.scaled_score)
        print(f"  {rec.result_id:<5} {rec.pupil_id:<10} {name[:22]:<22} "
              f"{yr:<3} {rec.academic_year:<9} {rec.subject:<10} "
              f"{score:<6} {rec.outcome:<8}")


@_safe
def open_ks2_sats() -> None:
    logger.debug("CLI: open_ks2_sats")
    while True:
        print("\n  -- KS2 SATs --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print(f"  Subjects: {', '.join(SUBJECTS)}")
        print(f"  Outcomes: {', '.join(OUTCOMES)}")
        print("\n   1) List all results")
        print("   2) Filter results")
        print("   3) View pupil's results")
        print("   4) Summary (by outcome)")
        print("   5) RWM combined summary (year)")
        print("   6) Record result")
        print("   7) Update result")
        print("   8) Delete result")
        print("   9) Show outcome meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view_pupil,
            "4": _summary,
            "5": _rwm_summary,
            "6": _record,
            "7": _update,
            "8": _delete,
            "9": _show_outcomes,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_results()
    print(f"\n  {len(rows)} result(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    print(f"  Subjects: {', '.join(SUBJECTS)} (blank for any)")
    subj = _prompt("  Subject: ").strip() or None
    print(f"  Outcomes: {', '.join(OUTCOMES)} (blank for any)")
    oc = _prompt("  Outcome: ").strip().upper() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    rows = data.list_results(academic_year=ay, subject=subj,
                             outcome=oc, year_group=yg)
    print(f"\n  {len(rows)} result(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_for_pupil(pid)
    print(f"\n  {len(rows)} result(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for r in rows:
            score = "-" if r.scaled_score is None else str(r.scaled_score)
            print(f"    #{r.result_id} {r.academic_year} {r.subject}: "
                  f"{r.outcome} (score={score})  "
                  f"{r.assessed_on or '-'}   {r.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    subj = _prompt("  Subject (blank for any): ").strip() or None
    s = data.summary(academic_year=ay, subject=subj)
    print("\n  -- Summary --")
    print(f"  Total: {s['total']}")
    for o in OUTCOMES:
        print(f"  {o}: {s['by_outcome'].get(o, 0)}")
    print(f"  At or above EXS: {s['at_or_above_exs']} "
          f"({s['at_or_above_exs_pct']:.1f}%)")
    if s['average_scaled'] is not None:
        print(f"  Avg scaled score (n={s['scaled_count']}): "
              f"{s['average_scaled']:.1f}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _rwm_summary() -> None:
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    s = data.cohort_combined_summary(ay)
    print(f"\n  -- RWM combined ({s['academic_year']}) --")
    print(f"  Pupils with any KS2 record: {s['pupils_recorded']}")
    print(f"  Achieved >=EXS in Reading, Maths, EGPS: "
          f"{s['exs_in_RWM']} ({s['exs_in_RWM_pct']:.1f}%)")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Subjects: {', '.join(SUBJECTS)})")
    print(f"  (Outcomes: {', '.join(OUTCOMES)})")
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    out["subject"]       = _prompt(f"  Subject [{d.get('subject','')}]: ") or d.get("subject", "")
    score_default = "" if d.get("scaled_score") in (None, "") else str(d["scaled_score"])
    out["scaled_score"]  = _prompt(f"  Scaled score {SCALED_SCORE_MIN}-{SCALED_SCORE_MAX} (optional) [{score_default}]: ") or score_default
    out["outcome"]       = _prompt(f"  Outcome [{d.get('outcome','')}]: ") or d.get("outcome", "")
    out["assessed_on"]   = _prompt(f"  Assessed on YYYY-MM-DD [{d.get('assessed_on','')}]: ") or d.get("assessed_on", "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _record() -> None:
    print("\n  -- Record KS2 SATs Result --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created #{rec.result_id}: pupil {rec.pupil_id} "
          f"{rec.academic_year} {rec.subject} -> {rec.outcome}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Result ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No result #{raw}")
        return
    defaults = {
        "pupil_id": existing.pupil_id,
        "academic_year": existing.academic_year,
        "subject": existing.subject,
        "scaled_score": existing.scaled_score,
        "outcome": existing.outcome,
        "assessed_on": existing.assessed_on or "",
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated #{rec.result_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Result ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete result #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such result'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_outcomes() -> None:
    print("\n  -- KS2 SATs outcomes --")
    for o in OUTCOMES:
        print(f"   {o}  — {OUTCOME_LABELS[o]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"KS2 SATs": open_ks2_sats}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching ks2_sats CLI label: %s", label)
    handler()
    return True
