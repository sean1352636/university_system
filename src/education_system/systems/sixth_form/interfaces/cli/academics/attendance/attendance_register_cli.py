"""CLI flows for the Sixth Form register lifecycle.

Submenu hung off Attendance: bulk marking, submit / reopen, the
unsubmitted-register chase list, copy-forward, arrival and departure
stamps, range marking and undo.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    lazy_domain,
    _input,
    _pause,
    _pick_group,
    _pick_slot,
    _UserAbort,
)

# Domain modules load on first use (see attendance_cli.lazy_domain).
data = lazy_domain("attendance")
reg = lazy_domain("attendance_register")
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _pick_status(default: str = "Present") -> str:
    print("\n  Statuses: " + "  ".join(
        f"{key.upper()}={value}" for key, value in reg.STATUS_KEYS.items()))
    raw = _input("Status (key or name)", default=default)
    if raw in STATUSES:
        return raw
    return reg.status_for_key(raw)


def _pick_roster_student(slot_id: int, date_s: str) -> str:
    entries = data.register_view(slot_id, date_s)
    if not entries:
        print("    This slot's class group has no members.")
        raise _UserAbort
    print("\n  Roster:")
    for i, e in enumerate(entries, 1):
        mark = e.record.status if e.record else "—"
        print(f"    {i:>3}) {e.student_id:<10} {e.full_name:<28} {mark}")
    while True:
        raw = _input(f"  Pick #1..{len(entries)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit() and 1 <= int(raw) <= len(entries):
            return entries[int(raw) - 1].student_id
        match = next((e for e in entries if e.student_id == raw), None)
        if match:
            return match.student_id
        print("    Not on this roster.")


def _slot_and_date(prompt: str = "Date (YYYY-MM-DD)") -> tuple[int, str]:
    slot_id = _pick_slot()
    return slot_id, _input(prompt, default=_today())


def _show_session(slot_id: int, date_s: str) -> None:
    session = reg.get_session(slot_id, date_s)
    if session is None:
        print(f"\n  Slot #{slot_id} on {date_s}: not started.")
        return
    line = f"\n  Slot #{slot_id} on {date_s}: {session.state}"
    if session.is_submitted:
        line += (f" — submitted {session.submitted_at}"
                 f" by {session.submitted_by or '?'}")
    if session.reopen_reason:
        line += f"\n    Reopened by {session.reopened_by or '?'}: {session.reopen_reason}"
    print(line)


# ── Bulk marking ───────────────────────────────────────────────────

def mark_all() -> None:
    print("\n═══ Mark Whole Register ═══")
    slot_id, date_s = _slot_and_date()
    status = _pick_status()
    scope = _input("Apply to (A)ll or (S)elected students", default="A").lower()
    student_ids = None
    if scope.startswith("s"):
        picked: list[str] = []
        while True:
            picked.append(_pick_roster_student(slot_id, date_s))
            if not _input("Add another? (y/N)", default="n").lower().startswith("y"):
                break
        student_ids = picked
    try:
        n = reg.mark_all(slot_id, date_s, status, student_ids=student_ids)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Marked {n} student(s) as {status}.")
    print("    (undo with 'Undo Last Save' if that was the wrong button)")
    _pause()


# ── Submit / reopen ────────────────────────────────────────────────

def submit_register() -> None:
    print("\n═══ Submit Register ═══")
    slot_id, date_s = _slot_and_date()
    _show_session(slot_id, date_s)
    who = _input("Submitted by (username)")
    try:
        reg.submit_register(slot_id, date_s, submitted_by=who or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        if "unmarked" in str(e):
            if _input("Submit anyway? (y/N)", default="n").lower().startswith("y"):
                try:
                    reg.submit_register(slot_id, date_s,
                                        submitted_by=who or None,
                                        allow_incomplete=True)
                except ValidationError as e2:
                    print(f"  ✗ {e2}")
                    _pause()
                    return
                print(f"\n  ✓ Submitted (incomplete) and locked.")
                _pause()
                return
        _pause()
        return
    print(f"\n  ✓ Register submitted and locked.")
    _pause()


def reopen_register() -> None:
    print("\n═══ Reopen Register ═══")
    slot_id, date_s = _slot_and_date()
    _show_session(slot_id, date_s)
    reason = _input("Reason for reopening", allow_empty=False)
    who = _input("Reopened by (username)")
    try:
        reg.reopen_register(slot_id, date_s, reason=reason,
                            reopened_by=who or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print("\n  ✓ Register reopened — edits are allowed again.")
    _pause()


def session_log() -> None:
    print("\n═══ Register Sessions ═══")
    date_from = _input("From (YYYY-MM-DD, optional)") or None
    date_to = _input("To   (YYYY-MM-DD, optional)") or None
    try:
        sessions = reg.list_sessions(date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not sessions:
        print("\n  (no register sessions)")
        _pause()
        return
    print()
    print(f"  {'Date':<12}  {'Slot':>5}  {'State':<10}  {'By':<12}  Reopen reason")
    print("  " + "-" * 74)
    for s in sessions:
        print(f"  {s.date:<12}  {s.slot_id:>5}  {s.state:<10}  "
              f"{(s.submitted_by or '—'):<12}  {s.reopen_reason or ''}")
    print(f"\n  {len(sessions)} session(s).")
    _pause()


# ── Chase list ─────────────────────────────────────────────────────

def chase_list() -> None:
    print("\n═══ Registers Not Yet Submitted ═══")
    date_from = _input("From (YYYY-MM-DD)", default=_today())
    date_to = _input("To   (YYYY-MM-DD)", default=date_from)
    try:
        missing = reg.unsubmitted_registers(date_from=date_from,
                                            date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not missing:
        print("\n  ✓ Every timetabled register in that window is submitted.")
        _pause()
        return
    print()
    print(f"  {'Date':<12}  {'Slot':>5}  {'Day':<4}  {'Per':>3}  "
          f"{'Room':<8}  {'State':<12}  Marked")
    print("  " + "-" * 70)
    for m in missing:
        print(f"  {m.date:<12}  {m.slot_id:>5}  {day_name(m.day):<4}  "
              f"{m.period:>3}  {(m.room or '—'):<8}  {m.state:<12}  "
              f"{m.marked}/{m.expected}")
    print(f"\n  {len(missing)} register(s) outstanding.")
    _pause()


# ── Copy forward ───────────────────────────────────────────────────

def copy_previous() -> None:
    print("\n═══ Copy Previous Session ═══")
    slot_id, date_s = _slot_and_date()
    source = reg.previous_register_date(slot_id, date_s)
    if source is None:
        print("\n  ✗ This slot has never been marked before that date.")
        _pause()
        return
    print(f"\n  Last marked on {source}.")
    overwrite = _input("Overwrite marks already taken? (y/N)",
                       default="n").lower().startswith("y")
    try:
        result = reg.copy_previous_register(slot_id, date_s,
                                            overwrite=overwrite)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Copied {result.copied} mark(s) from {result.source_date}"
          + (f", left {result.skipped} already-marked student(s) alone."
             if result.skipped else "."))
    _pause()


# ── Clock stamps ───────────────────────────────────────────────────

def record_arrival() -> None:
    print("\n═══ Record Arrival ═══")
    slot_id, date_s = _slot_and_date()
    start, end = reg.slot_window(slot_id)
    print(f"\n  Lesson runs {start}–{end}.")
    student_id = _pick_roster_student(slot_id, date_s)
    arrival = _input("Arrived at (HH:MM)", allow_empty=False)
    try:
        record = reg.record_arrival(slot_id, date_s, student_id, arrival)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if record.status == "Late":
        print(f"\n  ✓ {student_id} marked Late — {record.minutes_late} minute(s).")
    else:
        print(f"\n  ✓ {student_id} marked Present (on time).")
    _pause()


def record_departure() -> None:
    print("\n═══ Record Early Leave ═══")
    slot_id, date_s = _slot_and_date()
    start, end = reg.slot_window(slot_id)
    print(f"\n  Lesson runs {start}–{end}.")
    student_id = _pick_roster_student(slot_id, date_s)
    departure = _input("Left at (HH:MM)", allow_empty=False)
    reason = _input("Reason (optional)")
    try:
        record = reg.record_departure(slot_id, date_s, student_id, departure,
                                      reason=reason or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {student_id} left at {record.departure_time} — "
          f"{reg.minutes_missed(record)} minute(s) of the lesson missed.")
    _pause()


def early_leavers() -> None:
    print("\n═══ Early Leavers ═══")
    date_from = _input("From (YYYY-MM-DD, optional)") or None
    date_to = _input("To   (YYYY-MM-DD, optional)") or None
    try:
        rows = reg.list_early_leavers(date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (none)")
        _pause()
        return
    names = {s.student_id: s.full_name for s in student_data.list_students()}
    print()
    print(f"  {'Date':<12}  {'Slot':>5}  {'Student':<10}  {'Name':<24}  "
          f"{'Left':<6}  Missed")
    print("  " + "-" * 74)
    for r in rows:
        print(f"  {r.date:<12}  {r.slot_id:>5}  {r.student_id:<10}  "
              f"{names.get(r.student_id, '(deleted)')[:24]:<24}  "
              f"{r.departure_time:<6}  {reg.minutes_missed(r)} min")
    print(f"\n  {len(rows)} early leave(s).")
    _pause()


# ── Range marking ──────────────────────────────────────────────────

def mark_range() -> None:
    print("\n═══ Mark a Date Range ═══")
    print("  For known absence across several days — study leave, hospital,")
    print("  a trip. Only days the students actually had lessons are marked.")
    date_from = _input("From (YYYY-MM-DD)", default=_today())
    date_to = _input("To   (YYYY-MM-DD)", default=date_from)
    status = _pick_status(default="Authorised")
    scope = _input("Whole (G)roup or named (S)tudents", default="S").lower()
    group_id = _pick_group()
    student_ids = None
    if not scope.startswith("g"):
        picked: list[str] = []
        while True:
            raw = _input("Student ID", allow_empty=False)
            if student_data.get_student(raw) is None:
                print(f"    ✗ No student with id {raw}")
                continue
            picked.append(raw)
            if not _input("Add another? (y/N)", default="n").lower().startswith("y"):
                break
        student_ids = picked
    notes = _input("Notes (optional)") or None

    try:
        result = reg.mark_range(date_from=date_from, date_to=date_to,
                                status=status, group_id=group_id,
                                student_ids=student_ids, notes=notes)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {result.written} row(s) across "
          f"{len(result.dates)} teaching day(s).")
    if result.skipped_no_slot:
        print(f"    {result.skipped_no_slot} day(s) had no lessons — skipped.")
    if result.skipped_locked:
        print(f"    {result.skipped_locked} row(s) skipped: register already "
              "submitted. Reopen those registers to include them.")
    _pause()


# ── Undo ───────────────────────────────────────────────────────────

def undo_last_save() -> None:
    print("\n═══ Undo Last Save ═══")
    slot_id, date_s = _slot_and_date()
    steps = reg.snapshot_count(slot_id, date_s)
    if not steps:
        print("\n  ✗ Nothing to undo for that register.")
        _pause()
        return
    print(f"\n  {steps} undo step(s) available.")
    if not _input("Roll back the last save? (y/N)",
                  default="n").lower().startswith("y"):
        print("  Cancelled.")
        return
    try:
        result = reg.undo_last_save(slot_id, date_s)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Restored {result.restored} row(s); removed "
          f"{result.deleted} row(s) the save had created.")
    _pause()


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Mark Whole Register",        mark_all),
    ("Submit Register (lock)",     submit_register),
    ("Reopen Register",            reopen_register),
    ("Registers Not Yet Submitted", chase_list),
    ("Copy Previous Session",      copy_previous),
    ("Record Arrival",             record_arrival),
    ("Record Early Leave",         record_departure),
    ("Early Leavers",              early_leavers),
    ("Mark a Date Range",          mark_range),
    ("Undo Last Save",             undo_last_save),
    ("Register Session Log",       session_log),
]


def run() -> None:
    while True:
        print("\n── Register Tools ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Register tools CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
