"""CLI handlers for wraparound care (breakfast / after-school club)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.operations.daily_care.wraparound import (
    wraparound as data,
)
from education_system.systems.primary.domain.operations.daily_care.wraparound.wraparound import (
    ATTENDANCE_LABELS, ATTENDANCE_STATUSES, DAYS_OF_WEEK,
    SESSION_TYPE_LABELS, SESSION_TYPES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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


def _print_sessions(rows: list) -> None:
    if not rows:
        print("  (no sessions)")
        return
    print(f"  {'ID':<4} {'Name':<22} {'Type':<14} {'Days':<28} "
          f"{'Time':<13} {'Cap':<4} {'Fee':<8} {'Active':<6}")
    print(f"  {'-'*4} {'-'*22} {'-'*14} {'-'*28} {'-'*13} {'-'*4} "
          f"{'-'*8} {'-'*6}")
    for s in rows:
        time = ""
        if s.start_time or s.end_time:
            time = f"{s.start_time or '?'}–{s.end_time or '?'}"
        print(f"  {s.session_id:<4} {s.name[:22]:<22} "
              f"{SESSION_TYPE_LABELS.get(s.session_type, s.session_type)[:14]:<14} "
              f"{(s.days_of_week or '-')[:28]:<28} {time[:13]:<13} "
              f"{(str(s.capacity) if s.capacity else '-'):<4} "
              f"{s.fee_display:<8} {'yes' if s.is_active else 'no':<6}")


def _print_attendance(rows: list[tuple]) -> None:
    if not rows:
        print("  (none)")
        return
    print(f"  {'#':<6} {'Date':<11} {'Session':<22} {'Pupil':<10} "
          f"{'Name':<22} {'Status':<10}")
    print(f"  {'-'*6} {'-'*11} {'-'*22} {'-'*10} {'-'*22} {'-'*10}")
    for a, sess, pupil in rows:
        sname = sess.name if sess else f"#{a.session_id}"
        pname = pupil.full_name if pupil else "(unknown)"
        print(f"  {a.attendance_id:<6} {a.date:<11} {sname[:22]:<22} "
              f"{a.pupil_id:<10} {pname[:22]:<22} {a.status:<10}")


@_safe
def open_wraparound() -> None:
    logger.debug("CLI: open_wraparound")
    while True:
        print("\n  -- Breakfast / After-School Club --")
        c = data.counts()
        print(f"  Sessions: {c['sessions']} ({c['active_sessions']} active)   "
              f"Attendance rows: {c['attendance_rows']}")
        print("\n  -- Sessions --")
        print("   1) List sessions")
        print("   2) Create session")
        print("   3) Update session")
        print("   4) Toggle session active")
        print("   5) Delete session")
        print("  -- Attendance --")
        print("   6) Book / update attendance")
        print("   7) Today's register for a session")
        print("   8) Register for a session on a date")
        print("   9) Recent attendance for a pupil")
        print("  10) Filter attendance")
        print("  11) Change attendance status")
        print("  12) Delete attendance row")
        print("  13) Session summary (counts)")
        print("  14) Show day / status meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_sessions,
            "2": _create_session,
            "3": _update_session,
            "4": _toggle_session,
            "5": _delete_session,
            "6": _book,
            "7": _register_today,
            "8": _register_date,
            "9": _pupil_recent,
            "10": _filter_att,
            "11": _change_status,
            "12": _delete_att,
            "13": _session_summary,
            "14": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_sessions() -> None:
    print(f"  Types: {', '.join(SESSION_TYPES)} (blank for any)")
    st = _prompt("  Type: ").strip().lower() or None
    active_only = _prompt("  Active only? (y/N): ").lower() == "y"
    rows = data.list_sessions(session_type=st, active_only=active_only)
    print(f"\n  {len(rows)} session(s):")
    _print_sessions(rows)
    _prompt("\n  Press Enter to continue...")


def _collect_session(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Types: {', '.join(SESSION_TYPES)})")
    print(f"  (Days: {', '.join(DAYS_OF_WEEK)} — comma-separated)")
    out: dict = {}
    out["name"]         = _prompt(f"  Name [{d.get('name','')}]: ") or d.get("name", "")
    out["session_type"] = _prompt(f"  Type [{d.get('session_type','')}]: ") or d.get("session_type", "")
    out["days_of_week"] = _prompt(f"  Days [{d.get('days_of_week','')}]: ") or d.get("days_of_week", "")
    out["start_time"]   = _prompt(f"  Start time HH:MM [{d.get('start_time','')}]: ") or d.get("start_time", "")
    out["end_time"]     = _prompt(f"  End time HH:MM [{d.get('end_time','')}]: ") or d.get("end_time", "")
    cap_def = "" if d.get("capacity") in (None, "") else str(d["capacity"])
    out["capacity"]     = _prompt(f"  Capacity [{cap_def}]: ") or cap_def
    fee_def = ""
    if d.get("fee_pence") not in (None, "", 0):
        fee_def = f"{d['fee_pence']/100:.2f}"
    out["fee_pounds"]   = _prompt(f"  Fee £ (0 = free) [{fee_def}]: ") or fee_def
    out["notes"]        = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create_session() -> None:
    print("\n  -- Create Session --")
    payload = _collect_session()
    rec = data.create_session(payload)
    print(f"  Created session #{rec.session_id} {rec.name} ({rec.session_type})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update_session() -> None:
    raw = _prompt("  Session ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get_session(int(raw))
    if existing is None:
        print(f"  No session #{raw}")
        return
    defaults = {
        "name": existing.name,
        "session_type": existing.session_type,
        "days_of_week": existing.days_of_week or "",
        "start_time": existing.start_time or "",
        "end_time": existing.end_time or "",
        "capacity": existing.capacity,
        "fee_pence": existing.fee_pence,
        "notes": existing.notes or "",
    }
    payload = _collect_session(defaults)
    rec = data.update_session(int(raw), payload)
    print(f"  Updated session #{rec.session_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle_session() -> None:
    raw = _prompt("  Session ID to toggle: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_session_active(int(raw))
    print(f"  Session #{rec.session_id} {rec.name} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_session() -> None:
    raw = _prompt("  Session ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete session #{raw}? "
                     f"All attendance rows cascade. Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete_session(int(raw))
    print(f"  {'Deleted' if ok else 'No such session'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _book() -> None:
    sid = _prompt("  Session ID: ")
    if not sid or not sid.isdigit():
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    date = _prompt("  Date YYYY-MM-DD: ")
    if not date:
        return
    print(f"  Statuses: {', '.join(ATTENDANCE_STATUSES)}")
    status = _prompt("  Status [booked]: ").strip().lower() or "booked"
    notes = _prompt("  Notes (optional): ")
    rec = data.book({
        "session_id": int(sid), "pupil_id": pid, "date": date,
        "status": status, "notes": notes,
    })
    print(f"  Attendance #{rec.attendance_id}: pupil {rec.pupil_id} "
          f"session #{rec.session_id} on {rec.date} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _register_today() -> None:
    sid = _prompt("  Session ID: ")
    if not sid or not sid.isdigit():
        return
    import datetime as _dt
    today = _dt.date.today().isoformat()
    rows = data.day_register(int(sid), today)
    print(f"\n  Register for session #{sid} on {today} ({len(rows)} pupil(s)):")
    _print_register(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _register_date() -> None:
    sid = _prompt("  Session ID: ")
    if not sid or not sid.isdigit():
        return
    date = _prompt("  Date YYYY-MM-DD: ")
    if not date:
        return
    rows = data.day_register(int(sid), date)
    print(f"\n  Register for session #{sid} on {date} ({len(rows)} pupil(s)):")
    _print_register(rows)
    _prompt("\n  Press Enter to continue...")


def _print_register(rows: list[tuple]) -> None:
    if not rows:
        print("    (no bookings)")
        return
    print(f"    {'#':<6} {'Pupil':<10} {'Name':<26} {'Year':<5} {'Status':<10}")
    print(f"    {'-'*6} {'-'*10} {'-'*26} {'-'*5} {'-'*10}")
    for a, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        print(f"    {a.attendance_id:<6} {a.pupil_id:<10} "
              f"{name[:26]:<26} {yr:<5} {a.status:<10}")


@_safe
def _pupil_recent() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_attendance(pupil_id=pid)
    print(f"\n  {len(rows)} attendance row(s) for pupil {pid}:")
    _print_attendance(rows[:50])
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter_att() -> None:
    sid_raw = _prompt("  Session ID (blank for any): ").strip()
    sid: int | None = None
    if sid_raw:
        if not sid_raw.isdigit():
            print("  Session ID must be an integer.")
            return
        sid = int(sid_raw)
    pid = _prompt("  Pupil ID (blank for any): ").strip() or None
    fr = _prompt("  From date YYYY-MM-DD (blank): ").strip() or None
    to = _prompt("  To date YYYY-MM-DD (blank): ").strip() or None
    print(f"  Statuses: {', '.join(ATTENDANCE_STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    rows = data.list_attendance(session_id=sid, pupil_id=pid,
                                from_date=fr, to_date=to, status=st)
    print(f"\n  {len(rows)} row(s):")
    _print_attendance(rows[:200])
    if len(rows) > 200:
        print(f"  (truncated; {len(rows) - 200} more)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _change_status() -> None:
    raw = _prompt("  Attendance ID: ")
    if not raw or not raw.isdigit():
        return
    print(f"  Statuses: {', '.join(ATTENDANCE_STATUSES)}")
    new = _prompt("  New status: ").strip().lower()
    if not new:
        return
    rec = data.set_attendance_status(int(raw), new)
    print(f"  Attendance #{rec.attendance_id} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_att() -> None:
    raw = _prompt("  Attendance ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete attendance #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete_attendance(int(raw))
    print(f"  {'Deleted' if ok else 'No such attendance'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _session_summary() -> None:
    raw = _prompt("  Session ID: ")
    if not raw or not raw.isdigit():
        return
    fr = _prompt("  From date YYYY-MM-DD (blank): ").strip() or None
    to = _prompt("  To date YYYY-MM-DD (blank): ").strip() or None
    s = data.session_summary(int(raw), from_date=fr, to_date=to)
    print(f"\n  -- Session #{s['session_id']} summary --")
    print(f"  Total rows:    {s['total_rows']}")
    print(f"  Unique pupils: {s['unique_pupils']}")
    for k in ATTENDANCE_STATUSES:
        print(f"  {k:<10} {s['by_status'].get(k, 0)}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- Session types --")
    for t in SESSION_TYPES:
        print(f"   {t:<14} {SESSION_TYPE_LABELS[t]}")
    print("\n  -- Attendance statuses --")
    for s in ATTENDANCE_STATUSES:
        print(f"   {s:<10} {ATTENDANCE_LABELS[s]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Breakfast / After-School Club": open_wraparound}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching wraparound CLI label: %s", label)
    handler()
    return True
