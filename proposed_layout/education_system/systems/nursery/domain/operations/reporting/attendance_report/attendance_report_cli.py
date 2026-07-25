"""CLI flow for the Attendance Report + register (Nursery System).

Prints attendance rates by room and by child over a date range, lets you take
the daily register for the active children, and offers a CSV export.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.nursery.domain.operations.reporting.attendance_report import (
    attendance_report as data,
)

logger = logging.getLogger(__name__)

# Single-letter shortcuts accepted when taking the register.
_SHORTCUTS = {
    "p": "present", "a": "absent", "l": "late", "s": "sick", "h": "holiday",
}


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _ask(prompt: str, default: str = "") -> str | None:
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return raw or default


def _print_report(lo: str, hi: str) -> None:
    rep = data.report(lo, hi)
    print(f"\n═══ Attendance Report  {rep['date_from']} → {rep['date_to']} ═══")
    bs = rep["by_status"]
    rate = "-" if rep["attendance_rate"] is None else f"{rep['attendance_rate']}%"
    arate = "-" if rep["absence_rate"] is None else f"{rep['absence_rate']}%"
    print(f"  Records: {rep['total']}   Attended: {rep['attended']}   "
          f"Attendance: {rate}   Absence: {arate}")
    print("  " + "   ".join(f"{s}: {bs.get(s, 0)}" for s in data.STATUSES))

    print("\n  By room")
    print(f"  {'Room':<20} {'Pre':>4} {'Lat':>4} {'Abs':>4} {'Sic':>4} "
          f"{'Hol':>4} {'Tot':>4} {'Rate':>6}")
    print("  " + "-" * 60)
    for r in rep["per_room"]:
        rr = "-" if r["rate"] is None else f"{r['rate']}%"
        print(f"  {r['room'][:20]:<20} {r['present']:>4} {r['late']:>4} "
              f"{r['absent']:>4} {r['sick']:>4} {r['holiday']:>4} "
              f"{r['total']:>4} {rr:>6}")

    print("\n  By child")
    print(f"  {'Child':<24} {'Room':<16} {'Pre':>4} {'Lat':>4} {'Abs':>4} "
          f"{'Sic':>4} {'Hol':>4} {'Tot':>4} {'Rate':>6}")
    print("  " + "-" * 80)
    for c in rep["per_child"]:
        rr = "-" if c["rate"] is None else f"{c['rate']}%"
        print(f"  {c['name'][:24]:<24} {(c['room'] or '-')[:16]:<16} "
              f"{c['present']:>4} {c['late']:>4} {c['absent']:>4} "
              f"{c['sick']:>4} {c['holiday']:>4} {c['total']:>4} {rr:>6}")


def _view_report() -> None:
    lo_d, hi_d = data.default_range()
    lo = _ask(f"\n  From date [{lo_d}]: ", lo_d)
    if lo is None:
        return
    hi = _ask(f"  To date [{hi_d}]: ", hi_d)
    if hi is None:
        return
    try:
        _print_report(lo, hi)
    except data.ValidationError as e:
        print(f"  ✗ {e}")


def _take_register() -> None:
    today = _dt.date.today().isoformat()
    when = _ask(f"\n  Register date [{today}]: ", today)
    if when is None:
        return
    children = data.active_children()
    if not children:
        print("  No active children on roll.")
        return
    print("  Status per child (p=present a=absent l=late s=sick h=holiday).")
    saved = 0
    for pid, name, room in children:
        raw = _ask(f"   {name} ({pid}) [present]: ", "present")
        if raw is None:
            print("  Cancelled.")
            return
        status = _SHORTCUTS.get(raw.lower(), raw.lower())
        reason = None
        if status in ("absent", "sick"):
            reason = _ask("     Absence reason (optional): ", "") or None
        try:
            data.mark_attendance(pid, when, status, absence_reason=reason,
                                 room=room)
            saved += 1
        except data.ValidationError as e:
            print(f"     ✗ {e}")
    print(f"  ✓ Saved {saved} register row(s) for {when}.")


def _export() -> None:
    lo_d, hi_d = data.default_range()
    lo = _ask(f"\n  From date [{lo_d}]: ", lo_d)
    if lo is None:
        return
    hi = _ask(f"  To date [{hi_d}]: ", hi_d)
    if hi is None:
        return
    raw = _ask("  Export CSV to path (blank = data dir): ", "")
    if raw is None:
        return
    try:
        res = data.export_csv(lo, hi, path=raw or None)
        print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except data.ValidationError as e:
        print(f"  ✗ {e}")
    except OSError as e:
        print(f"  ✗ {e}")


def run(auth=None) -> None:
    """Entry point for the Attendance Report CLI screen."""
    while True:
        print("\n═══ Attendance Report ═══")
        print("   1) View report")
        print("   2) Take register")
        print("   3) Export report CSV")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "1":
            _view_report()
            _pause()
        elif choice == "2":
            try:
                _take_register()
            except Exception as e:  # noqa: BLE001
                logger.exception("Take register failed")
                print(f"  ✗ Could not take register: {e}")
            _pause()
        elif choice == "3":
            _export()
            _pause()
        elif choice == "0" or choice == "":
            return
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Attendance Report":
        return False
    run()
    return True
