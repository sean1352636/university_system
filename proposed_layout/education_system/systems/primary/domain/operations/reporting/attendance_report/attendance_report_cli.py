"""CLI handlers for attendance reporting."""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Callable

from education_system.systems.primary.domain.operations.reporting.attendance_report import (
    attendance_report as data,
)
from education_system.systems.primary.domain.operations.reporting.attendance_report.attendance_report import (
    PERSISTENT_ABSENCE_THRESHOLD_PCT,
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


def _print_cohort(s: dict) -> None:
    label = "All pupils" if not s["year_group"] else f"Year {s['year_group']}"
    print(f"  -- {label}  ({s['from_date'] or 'all'} -> {s['to_date'] or 'now'}) --")
    print(f"  Sessions:              {s['sessions']}")
    print(f"  Unique pupils:         {s['unique_pupils']}")
    print(f"  Present:               {s['present']}")
    print(f"  Late:                  {s['late']}")
    print(f"  Authorised absent:     {s['auth_absent']}")
    print(f"  Unauthorised absent:   {s['unauth_absent']}")
    print(f"  Other:                 {s['other']}")
    print(f"  Attendance:            {s['attendance_pct']:.2f}%")


def _print_pupils(rows: list) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'Pupil ID':<10} {'Name':<26} {'Yr':<3} "
          f"{'Sess':<5} {'Pres':<5} {'Late':<5} {'Auth':<5} {'Unauth':<7} "
          f"{'Att%':<7} {'PA':<3}")
    print(f"  {'-'*10} {'-'*26} {'-'*3} {'-'*5} {'-'*5} {'-'*5} {'-'*5} "
          f"{'-'*7} {'-'*7} {'-'*3}")
    for r in rows:
        print(f"  {r.pupil_id:<10} {r.full_name[:26]:<26} "
              f"{r.year_group:<3} {r.total_sessions:<5} {r.present:<5} "
              f"{r.late:<5} {r.authorised_absent:<5} "
              f"{r.unauthorised_absent:<7} {r.attendance_pct:<7.2f} "
              f"{'YES' if r.is_persistent_absentee else 'no':<3}")


@_safe
def open_attendance_report() -> None:
    logger.debug("CLI: open_attendance_report")
    while True:
        print("\n  -- Attendance Report --")
        print(f"  Persistent-absentee threshold: "
              f"<{PERSISTENT_ABSENCE_THRESHOLD_PCT:g}%")
        print("\n   1) Cohort summary (whole school)")
        print("   2) Summary by year group")
        print("   3) Per-pupil rollup")
        print("   4) Persistent absentees")
        print("   5) Daily breakdown (range)")
        print("   6) Single pupil detail")
        print("   7) Export per-pupil rollup to CSV")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _cohort,
            "2": _by_year,
            "3": _per_pupil,
            "4": _pa,
            "5": _daily,
            "6": _single,
            "7": _export,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


def _range_prompt() -> tuple[str | None, str | None]:
    fr = _prompt("  From date YYYY-MM-DD (blank for all-time): ").strip() or None
    to = _prompt("  To date YYYY-MM-DD (blank for all-time): ").strip() or None
    return fr, to


def _year_prompt() -> str | None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    return _prompt("  Year group: ").strip() or None


@_safe
def _cohort() -> None:
    fr, to = _range_prompt()
    yg = _year_prompt()
    s = data.cohort_summary(from_date=fr, to_date=to, year_group=yg)
    print()
    _print_cohort(s)
    _prompt("\n  Press Enter to continue...")


@_safe
def _by_year() -> None:
    fr, to = _range_prompt()
    rows = data.by_year_group(from_date=fr, to_date=to)
    print(f"\n  Attendance by year ({fr or 'all'} -> {to or 'now'}):")
    print(f"  {'Year':<5} {'Sess':<6} {'Pres':<6} {'Late':<5} "
          f"{'Auth':<5} {'Unauth':<7} {'Att%':<7}")
    print(f"  {'-'*5} {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*7} {'-'*7}")
    for s in rows:
        print(f"  {(s['year_group'] or '-'):<5} {s['sessions']:<6} "
              f"{s['present']:<6} {s['late']:<5} {s['auth_absent']:<5} "
              f"{s['unauth_absent']:<7} {s['attendance_pct']:<7.2f}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _per_pupil() -> None:
    fr, to = _range_prompt()
    yg = _year_prompt()
    rows = data.pupil_attendance(from_date=fr, to_date=to, year_group=yg)
    print(f"\n  {len(rows)} pupil(s):")
    _print_pupils(rows[:200])
    if len(rows) > 200:
        print(f"  (truncated; {len(rows) - 200} more)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pa() -> None:
    fr, to = _range_prompt()
    yg = _year_prompt()
    thr_raw = _prompt(
        f"  Threshold % [{PERSISTENT_ABSENCE_THRESHOLD_PCT:g}]: ")
    try:
        thr = float(thr_raw) if thr_raw else PERSISTENT_ABSENCE_THRESHOLD_PCT
    except ValueError:
        print("  Threshold must be a number.")
        return
    rows = data.persistent_absentees(from_date=fr, to_date=to,
                                     year_group=yg, threshold_pct=thr)
    print(f"\n  {len(rows)} pupil(s) below {thr:g}%:")
    _print_pupils(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _daily() -> None:
    fr = _prompt("  From date YYYY-MM-DD: ").strip()
    to = _prompt("  To date YYYY-MM-DD: ").strip()
    if not fr or not to:
        print("  Both dates are required.")
        return
    yg = _year_prompt()
    rows = data.daily_breakdown(from_date=fr, to_date=to, year_group=yg)
    print(f"\n  {len(rows)} day(s) with marks:")
    print(f"  {'Date':<11} {'Sess':<5} {'Pres':<5} {'Late':<5} "
          f"{'Auth':<5} {'Unauth':<7} {'Att%':<7}")
    print(f"  {'-'*11} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*7} {'-'*7}")
    for d in rows:
        print(f"  {d['date']:<11} {d['sessions']:<5} {d['present']:<5} "
              f"{d['late']:<5} {d['auth_absent']:<5} "
              f"{d['unauth_absent']:<7} {d['attendance_pct']:<7.2f}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _single() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    fr, to = _range_prompt()
    rows = data.pupil_attendance(from_date=fr, to_date=to, pupil_id=pid)
    if not rows:
        print(f"  No attendance records for pupil {pid} in that range.")
        _prompt("\n  Press Enter to continue...")
        return
    r = rows[0]
    print(f"\n  -- {r.full_name} ({r.pupil_id}, year {r.year_group}) --")
    print(f"  Range:                 {fr or 'all'} -> {to or 'now'}")
    print(f"  Sessions:              {r.total_sessions}")
    print(f"  Present:               {r.present}")
    print(f"  Late:                  {r.late}")
    print(f"  Authorised absent:     {r.authorised_absent}")
    print(f"  Unauthorised absent:   {r.unauthorised_absent}")
    print(f"  Other:                 {r.other}")
    print(f"  Attendance:            {r.attendance_pct:.2f}%")
    if r.is_persistent_absentee:
        print(f"  PERSISTENT ABSENTEE (< "
              f"{PERSISTENT_ABSENCE_THRESHOLD_PCT:g}%)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _export() -> None:
    fr, to = _range_prompt()
    yg = _year_prompt()
    path_raw = _prompt("  Output CSV path: ").strip()
    if not path_raw:
        return
    rows = data.pupil_attendance(from_date=fr, to_date=to, year_group=yg)
    n = data.export_csv(Path(path_raw).expanduser(), rows)
    print(f"  Wrote {n} pupil row(s) to {path_raw}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Attendance Report": open_attendance_report}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching attendance_report CLI label: %s", label)
    handler()
    return True
