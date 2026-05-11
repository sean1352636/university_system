"""CLI flows for Sixth Form Attendance.

Submenu: take register / records / per-student summary / per-group
summary / edit record / delete record.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.sixthform_system import (
    attendance as data,
    class_groups as cg_data,
    courses as course_data,
    students as student_data,
    timetable as tt_data,
)
from education_system.sixthform_system.attendance import (
    DEFAULT_STATUS,
    STATUSES,
    AttendanceSummary,
    ValidationError,
)
from education_system.sixthform_system.timetable import day_name

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C / EOF or types ``cancel``."""


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_slot() -> int:
    slots = tt_data.list_slots()
    if not slots:
        print("    No timetable slots exist. Create one first.")
        raise _UserAbort
    groups = {g.group_id: g for g in cg_data.list_groups()}
    courses = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Slots:")
    for i, s in enumerate(slots, 1):
        g = groups.get(s.group_id)
        course = courses.get(g.course_id) if g else None
        code = course.course_code if course else f"#{s.group_id}"
        print(f"    {i:>3}) #{s.slot_id:<3}  {day_name(s.day):<4} P{s.period}  "
              f"{code:<14}  {(g.group_name if g else '?')}")
    while True:
        raw = _input(f"  Pick #1..{len(slots)} (or slot ID)", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(slots):
                return slots[n - 1].slot_id
            target = next((s for s in slots if s.slot_id == n), None)
            if target:
                return target.slot_id
            print(f"    Out of range (1..{len(slots)}).")


def _pick_group() -> int:
    groups = cg_data.list_groups()
    if not groups:
        print("    No class groups exist. Create one first.")
        raise _UserAbort
    courses = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        course = courses.get(g.course_id)
        code = course.course_code if course else f"#{g.course_id}"
        print(f"    {i:>3}) #{g.group_id:<3}  {code:<14}  {g.group_name}")
    while True:
        raw = _input(f"  Pick #1..{len(groups)} (or group ID)", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(groups):
                return groups[n - 1].group_id
            target = next((g for g in groups if g.group_id == n), None)
            if target:
                return target.group_id
            print(f"    Out of range (1..{len(groups)}).")


# ── Take register ──────────────────────────────────────────────────

def take_register() -> None:
    print("\n═══ Take Register ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        slot_id = _pick_slot()
        date_s = _input("Date (YYYY-MM-DD)", default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        entries = data.register_view(slot_id, date_s)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("register_view failed")
        print(f"  ✗ Unexpected error: {e}")
        _pause()
        return

    if not entries:
        print("  ✗ This slot's class group has no members.")
        _pause()
        return

    print(f"\n  Roster ({len(entries)} student(s)):")
    print(f"  Statuses: 1=Present  2=Late  3=Absent  4=Authorised  S=Skip")
    print(f"  Default for blank input is 'Present'. Type 'cancel' to abort.\n")

    payload: dict[str, dict[str, Any]] = {}
    for e in entries:
        existing = (f"  [current: {e.record.status}"
                    + (f", mins_late={e.record.minutes_late}"
                       if e.record and e.record.minutes_late else "")
                    + "]") if e.record else ""
        print(f"\n  {e.student_id}  {e.full_name}{existing}")
        try:
            raw = _input("  Status (1-4 / S)",
                         default=(e.record.status if e.record
                                  else DEFAULT_STATUS))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        # Accept either number or full status name
        mapping = {"1": "Present", "2": "Late", "3": "Absent", "4": "Authorised"}
        status = mapping.get(raw, raw)
        if status not in STATUSES:
            # Treat as a typed status — let validation catch errors at save
            pass

        late: str = ""
        if status == "Late":
            try:
                late = _input(
                    "    Minutes late",
                    default=(str(e.record.minutes_late)
                             if e.record and e.record.minutes_late else "0"),
                )
            except _UserAbort:
                print("\n  Cancelled.")
                return

        notes: str = ""
        if status in ("Absent", "Authorised", "Late"):
            try:
                notes = _input(
                    "    Notes (optional)",
                    default=(e.record.notes if e.record and e.record.notes else ""),
                )
            except _UserAbort:
                print("\n  Cancelled.")
                return

        payload[e.student_id] = {
            "status": status, "minutes_late": late, "notes": notes,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_register(slot_id, date_s, payload)
        print(f"\n  ✓ Saved {n} row(s) for slot #{slot_id} on {date_s}.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_register crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Records ────────────────────────────────────────────────────────

def _print_records(rows: list) -> None:
    if not rows:
        print("\n  (no records)")
        return
    print()
    print(f"  {'#':>5}  {'Date':<10}  {'Slot':>4}  {'Student':<10}  "
          f"{'Status':<10}  {'Mins':>4}  Notes")
    print("  " + "-" * 78)
    for r in rows:
        print(
            f"  {r.record_id:>5}  {r.date:<10}  {r.slot_id:>4}  "
            f"{r.student_id:<10}  {r.status:<10}  "
            f"{(str(r.minutes_late) if r.minutes_late is not None else '—'):>4}  "
            f"{r.notes or ''}"
        )
    print(f"\n  {len(rows)} record(s).")


def list_records() -> None:
    print("\n═══ Attendance Records ═══")
    print("  (leave any filter blank to skip)\n")
    try:
        sid = _input("Student ID") or None
        slot_raw = _input("Slot ID")
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To   (YYYY-MM-DD)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    kwargs: dict[str, Any] = {
        "student_id": sid, "date_from": date_from, "date_to": date_to,
    }
    if slot_raw:
        try:
            kwargs["slot_id"] = int(slot_raw)
        except ValueError:
            print("  ✗ Slot ID must be a number.")
            _pause()
            return
    if status:
        if status not in STATUSES:
            print(f"  ✗ Status must be one of: {', '.join(STATUSES)}.")
            _pause()
            return
        kwargs["status"] = status

    try:
        rows = data.list_records(**kwargs)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("list_records failed")
        print(f"  ✗ Unexpected error: {e}")
        _pause()
        return

    _print_records(rows)
    _row_action_loop(rows)


def edit_record(record_id: int | None = None) -> None:
    print("\n═══ Edit Record ═══")
    try:
        rid = record_id if record_id is not None else int(
            _input("Record ID", allow_empty=False))
    except ValueError:
        print("  ✗ Record ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print(f"  ✗ No record #{rid}")
        _pause()
        return

    print(f"\n  {existing.student_id} · slot #{existing.slot_id} · {existing.date}")
    print(f"  Current: status={existing.status}, "
          f"mins_late={existing.minutes_late or '—'}, "
          f"notes={existing.notes or ''}")
    try:
        new_status = _pick_from(
            "Status", list(STATUSES), default=existing.status)
        new_late = _input(
            "Minutes late",
            default=(str(existing.minutes_late)
                     if existing.minutes_late is not None else ""))
        new_notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_record(rid, {
            "status": new_status, "minutes_late": new_late, "notes": new_notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_record crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated record #{updated.record_id} ({updated.status})")
    _pause()


def delete_record_flow(record_id: int | None = None) -> None:
    print("\n═══ Delete Record ═══")
    try:
        rid = record_id if record_id is not None else int(
            _input("Record ID", allow_empty=False))
    except ValueError:
        print("  ✗ Record ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print(f"  ✗ No record #{rid}")
        _pause()
        return
    confirm = _input(
        f"Delete record #{rid} ({existing.student_id}, {existing.date})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_record(rid):
            print(f"\n  ✓ Deleted #{rid}")
    except Exception as e:
        logger.exception("delete_record crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Summaries ──────────────────────────────────────────────────────

def _print_summary(summary: AttendanceSummary, indent: str = "  ") -> None:
    pct = f"{summary.percentage}%" if summary.percentage is not None else "—"
    print(f"{indent}Total sessions : {summary.total}")
    print(f"{indent}Present        : {summary.present}")
    print(f"{indent}Late           : {summary.late}")
    print(f"{indent}Absent         : {summary.absent}")
    print(f"{indent}Authorised     : {summary.authorised}")
    print(f"{indent}Attending %    : {pct}")


def student_summary() -> None:
    print("\n═══ Per-Student Summary ═══")
    try:
        sid = _input("Student ID", allow_empty=False)
        date_from = _input("From (YYYY-MM-DD, optional)") or None
        date_to = _input("To   (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    if student is None:
        print(f"  ✗ No student with id {sid}")
        _pause()
        return
    try:
        s = data.summary_for_student(
            sid, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_summary(s)
    _pause()


def group_summary() -> None:
    print("\n═══ Per-Group Summary ═══")
    try:
        gid = _pick_group()
        date_from = _input("From (YYYY-MM-DD, optional)") or None
        date_to = _input("To   (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        per = data.per_student_summary_for_group(
            gid, date_from=date_from, date_to=date_to)
        overall = data.summary_for_group(
            gid, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return

    students_index = {s.student_id: s for s in student_data.list_students()}
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Sess.':>5}  "
          f"{'Pres.':>5}  {'Late':>4}  {'Abs.':>4}  "
          f"{'Auth.':>5}  {'%':>5}")
    print("  " + "-" * 70)
    for sid, s in sorted(per.items()):
        student = students_index.get(sid)
        name = (student.full_name if student else "(deleted)")[:24]
        pct = f"{s.percentage}%" if s.percentage is not None else "—"
        print(f"  {sid:<10}  {name:<24}  {s.total:>5}  "
              f"{s.present:>5}  {s.late:>4}  {s.absent:>4}  "
              f"{s.authorised:>5}  {pct:>5}")
    print(f"\n  Group overall: total={overall.total} attending="
          f"{overall.attending}/{overall.total} "
          f"({overall.percentage}%" +
          (")" if overall.percentage is not None else " — no sessions)"))
    _pause()


# ── Row-action loop ────────────────────────────────────────────────

def _row_action_loop(rows: list) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("e", "d"):
            print("    Pick E, D, or Enter.")
            continue
        try:
            raw = _input("Record ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Record ID must be a whole number.")
            continue
        if choice == "e":
            edit_record(rid)
        elif choice == "d":
            delete_record_flow(rid)
        return


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Take Register",       take_register),
    ("List / Filter Records", list_records),
    ("Per-Student Summary", student_summary),
    ("Per-Group Summary",   group_summary),
    ("Edit Record",         edit_record),
    ("Delete Record",       delete_record_flow),
]


def run() -> None:
    while True:
        print("\n── Attendance ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
            logger.exception("Attendance CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Attendance":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Attendance CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
