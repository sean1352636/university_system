"""CLI handlers for Multiplication Tables Check results."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.mtc import mtc as data
from education_system.primarysch_system.modules.domain.mtc.mtc import (
    EXPECTED_THRESHOLD, MAX_SCORE,
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
        print("  (no results)")
        return
    print(f"  {'#':<5} {'Pupil ID':<10} {'Name':<24} {'Yr':<3} "
          f"{'AcYr':<9} {'Score':<7} {'Met':<5} {'Assessed':<11}")
    print(f"  {'-'*5} {'-'*10} {'-'*24} {'-'*3} {'-'*9} {'-'*7} "
          f"{'-'*5} {'-'*11}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        met = "yes" if rec.met_expected else "no"
        if rec.full_marks:
            met = "FULL"
        print(f"  {rec.result_id:<5} {rec.pupil_id:<10} {name[:24]:<24} "
              f"{yr:<3} {rec.academic_year:<9} "
              f"{rec.score}/{MAX_SCORE:<3} {met:<5} "
              f"{(rec.assessed_on or '-'):<11}")


@_safe
def open_mtc() -> None:
    logger.debug("CLI: open_mtc")
    while True:
        print("\n  -- Multiplication Tables Check --")
        print(f"  Max score: {MAX_SCORE}   "
              f"Internal 'expected' threshold: {EXPECTED_THRESHOLD}")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("\n   1) List all results")
        print("   2) Filter results")
        print("   3) View pupil's results")
        print("   4) Year summary")
        print("   5) Record result")
        print("   6) Update result")
        print("   7) Delete result")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view_pupil,
            "4": _year_summary,
            "5": _record,
            "6": _update,
            "7": _delete,
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
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    m_raw = _prompt("  Expected? [met / below / blank]: ").strip().lower()
    met: bool | None = None
    if m_raw == "met":
        met = True
    elif m_raw == "below":
        met = False
    rows = data.list_results(academic_year=ay, year_group=yg, met_expected=met)
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
            tag = "FULL" if r.full_marks else ("met" if r.met_expected else "below")
            print(f"    #{r.result_id} {r.academic_year} "
                  f"{r.score}/{MAX_SCORE} ({tag})  "
                  f"{r.assessed_on or '-'}   {r.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _year_summary() -> None:
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    s = data.year_summary(ay)
    print(f"\n  -- Year {s['academic_year']} --")
    print(f"  Total:         {s['total']}")
    print(f"  Met expected:  {s['met_expected']} ({s['met_pct']:.1f}%)")
    print(f"  Below:         {s['below_expected']}")
    print(f"  Full marks:    {s['full_marks']} ({s['full_marks_pct']:.1f}%)")
    print(f"  Average score: {s['average_score']:.1f}/{MAX_SCORE}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    score_default = "" if d.get("score") in (None, "") else str(d["score"])
    out["score"]         = _prompt(f"  Score 0-{MAX_SCORE} [{score_default}]: ") or score_default
    out["assessed_on"]   = _prompt(f"  Assessed on YYYY-MM-DD [{d.get('assessed_on','')}]: ") or d.get("assessed_on", "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _record() -> None:
    print("\n  -- Record MTC Result --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created result #{rec.result_id}: "
          f"pupil {rec.pupil_id} {rec.academic_year} -> "
          f"{rec.score}/{MAX_SCORE}")
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
        "score": existing.score,
        "assessed_on": existing.assessed_on or "",
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated result #{rec.result_id}")
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


_DISPATCH = {"Multiplication Check": open_mtc}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching MTC CLI label: %s", label)
    handler()
    return True
