"""CLI handlers for phonics screening results."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.assessment.phonics_screening import (
    phonics_screening as data,
)
from education_system.systems.primary.domain.assessment.phonics_screening.phonics_screening import (
    ATTEMPTS, MAX_SCORE, PASS_MARK, ScreeningResult,
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
    print(f"  {'#':<5} {'Pupil ID':<10} {'Name':<24} {'Year':<5} "
          f"{'Ac.Year':<10} {'Att':<4} {'Score':<6} {'Result':<6}")
    print(f"  {'-'*5} {'-'*10} {'-'*24} {'-'*5} {'-'*10} {'-'*4} {'-'*6} {'-'*6}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        print(f"  {rec.result_id:<5} {rec.pupil_id:<10} {name[:24]:<24} "
              f"{yr:<5} {rec.academic_year:<10} {rec.attempt:<4} "
              f"{f'{rec.score}/{MAX_SCORE}':<6} "
              f"{'pass' if rec.passed else 'fail':<6}")


@_safe
def open_phonics_screening() -> None:
    logger.debug("CLI: open_phonics_screening")
    while True:
        print("\n  -- Phonics Screening Check --")
        print(f"  Pass mark: {PASS_MARK}/{MAX_SCORE}")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("\n   1) List all results")
        print("   2) Filter results")
        print("   3) View pupil's results")
        print("   4) Year summary (pass rate)")
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
    att_raw = _prompt(
        f"  Attempt {ATTEMPTS} (blank for any): ").strip()
    attempt = None
    if att_raw:
        if not att_raw.isdigit():
            print("  Attempt must be an integer.")
            return
        attempt = int(att_raw)
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    p_raw = _prompt("  Pass filter [pass / fail / blank]: ").strip().lower()
    passed: bool | None = None
    if p_raw == "pass":
        passed = True
    elif p_raw == "fail":
        passed = False
    rows = data.list_results(academic_year=ay, attempt=attempt,
                             year_group=yg, passed=passed)
    print(f"\n  {len(rows)} result(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    results = data.list_for_pupil(pid)
    print(f"\n  {len(results)} result(s) for pupil {pid}:")
    if not results:
        print("    (none)")
    else:
        for r in results:
            print(f"    #{r.result_id} {r.academic_year} attempt {r.attempt}: "
                  f"{r.score}/{MAX_SCORE} "
                  f"{'pass' if r.passed else 'fail'}   "
                  f"{r.assessed_on or '-'}   {r.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _year_summary() -> None:
    ay = _prompt("  Academic year (e.g. 2025-26): ")
    if not ay:
        return
    s = data.year_summary(ay)
    print(f"\n  -- Year {s['academic_year']} --")
    print(f"  Total:        {s['total']}")
    print(f"  Passed:       {s['passed']}")
    print(f"  Failed:       {s['failed']}")
    print(f"  Pass rate:    {s['pass_rate']:.1f}%")
    print(f"  Avg score:    {s['average_score']:.1f}/{MAX_SCORE}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    attempt_default = str(d.get("attempt", "1"))
    out["attempt"]       = _prompt(f"  Attempt 1/2 [{attempt_default}]: ") or attempt_default
    score_default = "" if d.get("score") in (None, "") else str(d["score"])
    out["score"]         = _prompt(f"  Score 0-{MAX_SCORE} [{score_default}]: ") or score_default
    out["assessed_on"]   = _prompt(f"  Assessed on YYYY-MM-DD [{d.get('assessed_on','')}]: ") or d.get("assessed_on", "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _record() -> None:
    print("\n  -- Record Phonics Screening Result --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created result #{rec.result_id}: "
          f"pupil {rec.pupil_id} {rec.academic_year} attempt {rec.attempt} "
          f"-> {rec.score}/{MAX_SCORE} ({'pass' if rec.passed else 'fail'})")
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
        "attempt": existing.attempt,
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


_DISPATCH = {"Phonics Screening": open_phonics_screening}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching phonics_screening CLI label: %s", label)
    handler()
    return True
