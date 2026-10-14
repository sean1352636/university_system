"""CLI handlers for daily attendance."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.systems.secondary.domain.academics.attendance import (
    attendance as data,
)
from education_system.systems.secondary.domain.academics.attendance.attendance import (
    MARK_CODES, SESSIONS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError,
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


def _today() -> str:
    return _dt.date.today().isoformat()


def _print_codes() -> None:
    print("  Mark codes:")
    for code, (label, category) in MARK_CODES.items():
        print(f"   {code:<3} {label:<22}  [{category}]")


@_safe
def open_attendance() -> None:
    logger.debug("CLI: open_attendance")
    while True:
        print("\n  ── Attendance ──")
        print("   1) Take register (bulk for a date/session)")
        print("   2) Record a single mark")
        print("   3) View pupil history")
        print("   4) View daily summary")
        print("   5) View pupil summary")
        print("   6) List records for a date")
        print("   7) Delete a record")
        print("   8) Mark codes reference")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _take_register,
            "2": _single_mark,
            "3": _pupil_history,
            "4": _daily_summary,
            "5": _pupil_summary,
            "6": _list_date,
            "7": _delete_record,
            "8": lambda: (_print_codes(), _prompt("\n  Press Enter to continue...")),
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


@_safe
def _take_register() -> None:
    print(f"\n  Date (YYYY-MM-DD) [{_today()}]:")
    date_s = _prompt("  Date: ") or _today()
    print(f"  Session ({'/'.join(SESSIONS)}):")
    sess = _prompt("  Session: ").upper()
    if not sess:
        return
    print("  Enter pupil ID and mark code per line, e.g.  S12345 /")
    print("  Type a blank line to finish.")
    _print_codes()
    marks: dict[str, str] = {}
    while True:
        line = _prompt("  > ")
        if not line:
            break
        parts = line.split()
        if len(parts) < 2:
            print("  Need pupil_id and mark — try again.")
            continue
        pid, code = parts[0], parts[1]
        marks[pid] = code
    if not marks:
        print("  No marks entered.")
        return
    results = data.bulk_record(date_s, sess, marks)
    ok = [k for k, v in results.items() if not isinstance(v, str)]
    bad = {k: v for k, v in results.items() if isinstance(v, str)}
    print(f"  Saved {len(ok)} mark(s).")
    for pid, msg in bad.items():
        print(f"  ✗ {pid}: {msg}")


@_safe
def _single_mark() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    date_s = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    sess = _prompt(f"  Session ({'/'.join(SESSIONS)}): ").upper()
    if not sess:
        return
    _print_codes()
    code = _prompt("  Mark: ")
    if not code:
        return
    notes = _prompt("  Notes (optional): ")
    rec = data.record_mark(pid, date_s, sess, code, notes or None)
    print(f"  Saved: pupil {rec.pupil_id} {rec.date}/{rec.session} "
          f"= {rec.mark} ({rec.label})")


@_safe
def _pupil_history() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    df = _prompt("  From date (YYYY-MM-DD, blank for any): ") or None
    dt = _prompt("  To date (YYYY-MM-DD, blank for any): ") or None
    rows = data.list_for_pupil(pid, date_from=df, date_to=dt)
    print(f"\n  {len(rows)} record(s) for {pid}:")
    if rows:
        print(f"  {'Date':<11} {'Sess':<4} {'Mark':<5} {'Label':<22} "
              f"{'Notes':<24}")
        print(f"  {'-'*11} {'-'*4} {'-'*5} {'-'*22} {'-'*24}")
        for r in rows:
            print(f"  {r.date:<11} {r.session:<4} {r.mark:<5} "
                  f"{r.label[:22]:<22} {(r.notes or '-')[:24]:<24}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _daily_summary() -> None:
    date_s = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    summary = data.daily_summary(date_s)
    print(f"\n  ── Daily summary: {summary['date']} ──")
    for sess, vals in summary["sessions"].items():
        print(f"\n  {sess}: total={vals['total']}  "
              f"present={vals['present']}  "
              f"auth absent={vals['authorised_absent']}  "
              f"unauth absent={vals['unauthorised_absent']}  "
              f"other={vals['other']}")
        if vals["marks"]:
            for code, n in sorted(vals["marks"].items()):
                label = MARK_CODES.get(code, (code, ""))[0]
                print(f"     {code:<3} {label:<22} {n}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    df = _prompt("  From date (YYYY-MM-DD, blank for any): ") or None
    dt = _prompt("  To date (YYYY-MM-DD, blank for any): ") or None
    s = data.pupil_summary(pid, date_from=df, date_to=dt)
    print(f"\n  ── Pupil summary: {s['pupil_id']} ──")
    print(f"  Total sessions:        {s['total_sessions']}")
    print(f"  Present:               {s['present']}")
    print(f"  Authorised absent:     {s['authorised_absent']}")
    print(f"  Unauthorised absent:   {s['unauthorised_absent']}")
    print(f"  Other:                 {s['other']}")
    print(f"  Attendance %:          {s['attendance_pct']}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_date() -> None:
    date_s = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    sess = _prompt(f"  Session ({'/'.join(SESSIONS)}) or blank: ").upper() or None
    rows = data.list_for_date(date_s, session=sess)
    print(f"\n  {len(rows)} record(s) on {date_s}"
          f"{(' (' + sess + ')') if sess else ''}:")
    if rows:
        print(f"  {'ID':<5} {'Pupil':<10} {'Sess':<4} "
              f"{'Mark':<5} {'Label':<22}")
        print(f"  {'-'*5} {'-'*10} {'-'*4} {'-'*5} {'-'*22}")
        for r in rows:
            print(f"  {r.record_id:<5} {r.pupil_id:<10} {r.session:<4} "
                  f"{r.mark:<5} {r.label[:22]:<22}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_record() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        return
    try:
        record_id = int(rid)
    except ValueError:
        print("  Record ID must be a number.")
        return
    rec = data.get_record(record_id)
    if rec is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete record #{rid} ({rec.pupil_id} {rec.date}/"
        f"{rec.session} = {rec.mark})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_record(record_id):
        print(f"  Deleted record #{rid}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Attendance": open_attendance}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching attendance CLI label: %s", label)
    handler()
    return True
