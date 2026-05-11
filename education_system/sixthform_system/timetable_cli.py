"""CLI flows for Sixth Form Timetable.

Submenu: list / weekly-grid / new / view / edit / delete. The grid view
is a text-based 5×6 table that filters by group / student / teacher /
room.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.sixthform_system import (
    class_groups as cg_data,
    courses as course_data,
    students as student_data,
    timetable as data,
)
from education_system.sixthform_system.timetable import (
    DAYS,
    DAY_NUMBERS,
    DEFAULT_PERIOD_TIMES,
    PERIODS,
    SaveResult,
    TimetableSlot,
    ValidationError,
    day_name,
    day_number,
)

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


def _pick_group() -> int:
    try:
        groups = cg_data.list_groups()
    except Exception as e:
        logger.exception("Could not load class groups")
        print(f"    Error: {e}")
        raise _UserAbort
    if not groups:
        print("    No class groups exist. Create one first.")
        raise _UserAbort
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        course = courses_by_id.get(g.course_id)
        code = course.course_code if course else f"#{g.course_id}"
        print(f"    {i:>3}) #{g.group_id:<4}  {code:<12}  {g.group_name}")
    while True:
        raw = _input(f"  Pick #1..{len(groups)} (or type group_id)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(groups):
                return groups[n - 1].group_id
            try:
                target = next((g for g in groups if g.group_id == int(raw)), None)
                if target:
                    return target.group_id
            except ValueError:
                pass
            print(f"    Out of range (1..{len(groups)}).")
            continue
        print("    Enter a number.")


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


# ── Form ───────────────────────────────────────────────────────────

def _collect_form(existing: TimetableSlot | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing slot #{existing.slot_id} "
              f"(group #{existing.group_id})")
        payload["group_id"] = existing.group_id
    else:
        print("\n  ── Class group ──")
        payload["group_id"] = _pick_group()

    print("\n  ── Slot ──")
    payload["day"] = _pick_from(
        "Day", list(DAYS),
        default=(DAYS[existing.day - 1] if is_edit else DAYS[0]),
    )
    payload["period"] = _pick_from(
        "Period", [str(p) for p in PERIODS],
        default=(str(existing.period) if is_edit else str(PERIODS[0])),
    )
    # Pre-fill times if blank
    p = int(payload["period"])
    default_st, default_et = DEFAULT_PERIOD_TIMES.get(p, ("", ""))
    payload["start_time"] = _input(
        "Start time (HH:MM, blank = default)",
        default=(existing.start_time if is_edit and existing.start_time
                 else default_st),
    )
    payload["end_time"] = _input(
        "End time (HH:MM, blank = default)",
        default=(existing.end_time if is_edit and existing.end_time
                 else default_et),
    )
    payload["room"] = _input(
        "Room (blank = inherit course/group room)",
        default=(existing.room or "") if is_edit else "",
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def _surface_clashes(save: SaveResult) -> None:
    if save.student_clashes:
        print("\n  ⚠ Student clashes (in another class at the same time):")
        for sid in sorted(save.student_clashes):
            print(f"      · {sid}")
    if save.teacher_clashes:
        print("\n  ⚠ Teacher clashes:")
        for t in sorted(set(save.teacher_clashes)):
            print(f"      · {t}")


# ── CRUD entry points ──────────────────────────────────────────────

def _print_table(rows: list[TimetableSlot]) -> None:
    if not rows:
        print("\n  (no slots)")
        return
    try:
        groups = {g.group_id: g for g in cg_data.list_groups()}
        courses = {c.course_id: c for c in course_data.list_courses()}
    except Exception:
        logger.exception("Could not load groups/courses")
        groups, courses = {}, {}

    print()
    print(f"  {'#':>4}  {'Day':<4}  {'P':>2}  {'Group':<24}  "
          f"{'Code':<10}  {'Room':<8}  Time")
    print("  " + "-" * 80)
    for s in rows:
        g = groups.get(s.group_id)
        course = courses.get(g.course_id) if g else None
        gname = g.group_name if g else f"#{s.group_id}"
        code = course.course_code if course else "—"
        room = s.room or (g.room if g else None) or \
               (course.room if course else None) or "—"
        time = f"{s.start_time}–{s.end_time}" if s.start_time and s.end_time else ""
        print(f"  {s.slot_id:>4}  {day_name(s.day):<4}  {s.period:>2}  "
              f"{gname[:24]:<24}  {code[:10]:<10}  {room[:8]:<8}  {time}")
    print(f"\n  {len(rows)} slot(s).")


def list_all() -> None:
    print("\n═══ Timetable Slots ═══")
    try:
        rows = data.list_slots()
    except Exception as e:
        logger.exception("CLI list_slots failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_slots() -> None:
    print("\n═══ Filter Slots ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        gid_raw = _input("Group ID")
        day_raw = _input(f"Day ({'/'.join(DAYS)})")
        per_raw = _input(f"Period ({'/'.join(str(p) for p in PERIODS)})")
        room = _input("Room") or None
        teacher = _input("Teacher (exact)") or None
        student = _input("Student ID") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    kwargs: dict[str, Any] = {}
    if gid_raw:
        try:
            kwargs["group_id"] = int(gid_raw)
        except ValueError:
            print("  ✗ Group ID must be a number.")
            _pause()
            return
    if day_raw:
        d = day_number(day_raw) or (int(day_raw) if day_raw.isdigit() else 0)
        if d not in DAY_NUMBERS:
            print(f"  ✗ Day must be one of: {', '.join(DAYS)}.")
            _pause()
            return
        kwargs["day"] = d
    if per_raw:
        try:
            p = int(per_raw)
        except ValueError:
            print("  ✗ Period must be a number.")
            _pause()
            return
        if p not in PERIODS:
            print(f"  ✗ Period must be one of {list(PERIODS)}.")
            _pause()
            return
        kwargs["period"] = p
    kwargs["room"] = room
    kwargs["teacher"] = teacher
    kwargs["student_id"] = student

    try:
        rows = data.list_slots(**kwargs)
    except Exception as e:
        logger.exception("CLI filter_slots failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_slot() -> None:
    print("\n═══ New Slot ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        save = data.create_slot(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_slot failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    s = save.slot
    print(f"  ✓ Created slot #{s.slot_id}")
    print(f"      Group   : #{s.group_id}")
    print(f"      When    : {day_name(s.day)} P{s.period} "
          f"({s.start_time or '?'}–{s.end_time or '?'})")
    print(f"      Room    : {s.room or '—'}")
    _surface_clashes(save)
    _pause()


def view_slot(slot_id: int | None = None) -> None:
    print("\n═══ View Slot ═══")
    try:
        sid = slot_id if slot_id is not None else int(
            _input("Slot ID", allow_empty=False))
    except ValueError:
        print("  ✗ Slot ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = data.get_slot(sid)
    if s is None:
        print(f"  ✗ No slot #{sid}")
        _pause()
        return

    g = cg_data.get_group(s.group_id)
    course = course_data.get_course(g.course_id) if g else None
    teacher = (g.teacher if g else None) or (course.teacher if course else None) or "—"
    room = s.room or (g.room if g else None) or (course.room if course else None) or "—"

    print()
    print(f"    Slot ID  : #{s.slot_id}")
    print(f"    Group    : #{s.group_id} "
          f"({g.group_name if g else '(deleted)'})")
    print(f"    Course   : {course.course_code if course else '—'}")
    print(f"    Teacher  : {teacher}")
    print(f"    When     : {day_name(s.day)} P{s.period}")
    print(f"    Time     : {s.start_time or '—'} – {s.end_time or '—'}")
    print(f"    Room     : {room}")
    if s.notes:
        print(f"    Notes    : {s.notes}")
    print(f"    Created  : {s.created_at}")
    _pause()


def edit_slot(slot_id: int | None = None) -> None:
    print("\n═══ Edit Slot ═══")
    try:
        sid = slot_id if slot_id is not None else int(
            _input("Slot ID", allow_empty=False))
    except ValueError:
        print("  ✗ Slot ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_slot(sid)
    if existing is None:
        print(f"  ✗ No slot #{sid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        save = data.update_slot(sid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_slot(%d) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated slot #{save.slot.slot_id}")
    _surface_clashes(save)
    _pause()


def delete_slot_flow(slot_id: int | None = None) -> None:
    print("\n═══ Delete Slot ═══")
    try:
        sid = slot_id if slot_id is not None else int(
            _input("Slot ID", allow_empty=False))
    except ValueError:
        print("  ✗ Slot ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_slot(sid)
    if existing is None:
        print(f"  ✗ No slot #{sid}")
        _pause()
        return
    confirm = _input(
        f"Delete slot #{sid} ({day_name(existing.day)} P{existing.period})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_slot(sid):
            print(f"\n  ✓ Deleted slot #{sid}")
    except Exception as e:
        logger.exception("CLI delete_slot(%d) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Weekly grid view ──────────────────────────────────────────────

_GRID_COL_WIDTH = 22  # characters per day column


def _cell_str(slot: TimetableSlot, groups: dict, courses: dict) -> list[str]:
    g = groups.get(slot.group_id)
    course = courses.get(g.course_id) if g else None
    line1 = (f"{course.course_code} {g.group_name}"
             if g and course else
             (g.group_name if g else f"#{slot.group_id}"))
    room = slot.room or (g.room if g else None) or \
           (course.room if course else None) or "—"
    line2 = f"  {room}"
    return [line1[:_GRID_COL_WIDTH], line2[:_GRID_COL_WIDTH]]


def show_grid() -> None:
    print("\n═══ Weekly Grid ═══")
    try:
        v = _pick_from("View by",
                       ["All", "Group", "Student", "Teacher", "Room"],
                       default="All")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    kwargs: dict[str, Any] = {}
    try:
        if v == "Group":
            kwargs["group_id"] = _pick_group()
        elif v == "Student":
            sid = _input("Student ID", allow_empty=False)
            kwargs["student_id"] = sid
        elif v == "Teacher":
            kwargs["teacher"] = _input("Teacher", allow_empty=False)
        elif v == "Room":
            kwargs["room"] = _input("Room", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        grid = data.weekly_grid(**kwargs)
        groups = {g.group_id: g for g in cg_data.list_groups()}
        courses = {c.course_id: c for c in course_data.list_courses()}
    except Exception as e:
        logger.exception("CLI weekly_grid failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return

    # Header
    print()
    print(" " * 6 + "".join(f"{d:^{_GRID_COL_WIDTH}}" for d in DAYS))
    sep = "      " + ("-" * (_GRID_COL_WIDTH * len(DAYS)))
    print(sep)
    for p in PERIODS:
        # Two lines per row: group code + room
        line1 = f"  P{p}  "
        line2 = " " * 6
        for d in DAY_NUMBERS:
            cell = grid.get((d, p), [])
            if not cell:
                line1 += " " * _GRID_COL_WIDTH
                line2 += " " * _GRID_COL_WIDTH
                continue
            if len(cell) > 1:
                # Show the first; flag the clash inline
                first = cell[0]
                marker = f"⚠×{len(cell)} "
                rendered = _cell_str(first, groups, courses)
                line1 += (marker + rendered[0])[:_GRID_COL_WIDTH].ljust(_GRID_COL_WIDTH)
                line2 += rendered[1].ljust(_GRID_COL_WIDTH)
            else:
                rendered = _cell_str(cell[0], groups, courses)
                line1 += rendered[0].ljust(_GRID_COL_WIDTH)
                line2 += rendered[1].ljust(_GRID_COL_WIDTH)
        print(line1.rstrip())
        print(line2.rstrip())
        print(sep)

    clash_cells = sum(1 for v in grid.values() if len(v) > 1)
    if clash_cells:
        print(f"\n  ⚠ {clash_cells} period(s) have multiple slots.")
    _pause()


# ── Row-action loop ────────────────────────────────────────────────

def _row_action_loop(rows: list[TimetableSlot]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d"):
            print("    Pick V, E, D, or Enter.")
            continue
        try:
            raw = _input("Slot ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        try:
            sid = int(raw)
        except ValueError:
            print("    Slot ID must be a whole number.")
            continue
        if choice == "v":
            view_slot(sid)
        elif choice == "e":
            edit_slot(sid)
        elif choice == "d":
            delete_slot_flow(sid)
        return


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Slots",  list_all),
    ("Filter Slots",    filter_slots),
    ("Weekly Grid",     show_grid),
    ("New Slot",        new_slot),
    ("View Slot",       view_slot),
    ("Edit Slot",       edit_slot),
    ("Delete Slot",     delete_slot_flow),
]


def run() -> None:
    while True:
        print("\n── Timetable ──")
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
            logger.exception("Timetable CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Timetable":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Timetable CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
