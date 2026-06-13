"""CLI handlers for the weekly timetable."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.secondarysch_system.modules.domain.academics.timetable import (
    timetable as data,
)
from education_system.secondarysch_system.modules.domain.academics.timetable.timetable import (
    DAYS_OF_WEEK, MIN_PERIOD, MAX_PERIOD,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_table(rows: list[data.TimetableSlot]) -> None:
    if not rows:
        print("  (no slots)")
        return
    print(f"  {'ID':<5} {'Day':<4} {'P':<2} {'Yr':<3} {'Form':<6} "
          f"{'Subj':<8} {'Room':<8} {'Teacher':<18} "
          f"{'Time':<13}")
    print(f"  {'-'*5} {'-'*4} {'-'*2} {'-'*3} {'-'*6} {'-'*8} {'-'*8} "
          f"{'-'*18} {'-'*13}")
    for s in rows:
        timestr = ("-" if not s.start_time
                   else f"{s.start_time}-{s.end_time or '?'}")
        print(f"  {s.slot_id:<5} {s.day_of_week:<4} {s.period:<2} "
              f"{s.year_group:<3} {(s.form_group or '-'):<6} "
              f"{(s.subject_code or '?'):<8} {(s.room or '-'):<8} "
              f"{(s.teacher or '-')[:18]:<18} {timestr:<13}")


def _print_grid(rows: list[data.TimetableSlot]) -> None:
    if not rows:
        print("  (no slots)")
        return
    grid: dict[tuple[str, int], list[data.TimetableSlot]] = {}
    max_period = MIN_PERIOD
    for s in rows:
        grid.setdefault((s.day_of_week, s.period), []).append(s)
        max_period = max(max_period, s.period)
    print(f"  {'Day':<5} | " + " | ".join(
        f"{f'P{p}':<22}" for p in range(MIN_PERIOD, max_period + 1)))
    print("  " + "-" * (5 + (25 * (max_period - MIN_PERIOD + 1))))
    for day in DAYS_OF_WEEK:
        cells: list[str] = []
        for p in range(MIN_PERIOD, max_period + 1):
            slots = grid.get((day, p), [])
            if not slots:
                cells.append(f"{'-':<22}")
            else:
                # Show first slot inline; others appended with "+N"
                s = slots[0]
                txt = (f"{s.subject_code or '?'}"
                       f"{(' ' + s.form_group) if s.form_group else ''}"
                       f"{(' @' + s.room) if s.room else ''}")
                if len(slots) > 1:
                    txt += f" (+{len(slots)-1})"
                cells.append(f"{txt[:22]:<22}")
        print(f"  {day:<5} | " + " | ".join(cells))


@_safe
def open_timetable() -> None:
    logger.debug("CLI: open_timetable")
    while True:
        c = data.counts()
        print("\n  ── Timetable ──")
        print(f"  {c['total']} slot(s)   distinct teachers: {c['teachers']}")
        print("\n   1) New slot")
        print("   2) List slots")
        print("   3) Weekly grid (filtered)")
        print("   4) View slot")
        print("   5) Edit slot")
        print("   6) Delete slot")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new,
            "2": _list,
            "3": _grid,
            "4": _view,
            "5": _edit,
            "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.TimetableSlot | None = None) -> dict[str, str]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, str] = {}
    f["year_group"]  = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                           existing.year_group if existing else None)
    f["form_group"]  = ask("Form (blank = whole year)",
                           existing.form_group if existing else None)
    if existing:
        cur_subj = f"{existing.subject_id} ({existing.subject_code})"
    else:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True):
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
        cur_subj = None
    f["subject_id"]  = ask("Subject ID", cur_subj.split()[0] if cur_subj
                            else None)
    f["day_of_week"] = ask(f"Day ({'/'.join(DAYS_OF_WEEK)})",
                            existing.day_of_week if existing else None)
    f["period"]      = ask(f"Period ({MIN_PERIOD}-{MAX_PERIOD})",
                            existing.period if existing else None)
    f["start_time"]  = ask("Start time (HH:MM)",
                            existing.start_time if existing else None)
    f["end_time"]    = ask("End time (HH:MM)",
                            existing.end_time if existing else None)
    f["room"]        = ask("Room",
                            existing.room if existing else None)
    f["teacher"]     = ask("Teacher",
                            existing.teacher if existing else None)
    f["notes"]       = ask("Notes",
                            existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Slot ──")
    fields = _collect()
    s = data.create_slot(fields)
    print(f"  Created slot #{s.slot_id}  Yr{s.year_group}"
          f"{('/' + s.form_group) if s.form_group else ''}  "
          f"{s.day_of_week} P{s.period} {s.subject_code}")


@_safe
def _list() -> None:
    print(f"\n  Filter — year ({'/'.join(YEAR_GROUPS)}), blank for all.")
    yg = _prompt("  Year: ") or None
    print("  Filter — form (blank for all).")
    fg = _prompt("  Form: ") or None
    print(f"  Filter — day ({'/'.join(DAYS_OF_WEEK)}), blank for all.")
    day = _prompt("  Day: ") or None
    print("  Filter — teacher (blank for all).")
    teacher = _prompt("  Teacher: ") or None
    rows = data.list_slots(year_group=yg, form_group=fg,
                           day_of_week=day, teacher=teacher)
    print(f"\n  {len(rows)} slot(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _grid() -> None:
    print(f"\n  Year ({'/'.join(YEAR_GROUPS)}), blank for all.")
    yg = _prompt("  Year: ") or None
    fg = _prompt("  Form (blank for all): ") or None
    teacher = _prompt("  Teacher (blank for all): ") or None
    rows = data.list_slots(year_group=yg, form_group=fg, teacher=teacher)
    print("\n  Weekly grid:")
    _print_grid(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id() -> int | None:
    sid = _prompt("  Slot ID: ")
    if not sid:
        return None
    try:
        return int(sid)
    except ValueError:
        print("  Slot ID must be a number.")
        return None


@_safe
def _view() -> None:
    sid = _ask_id()
    if sid is None:
        return
    s = data.get_slot(sid)
    if s is None:
        print("  No slot with that ID.")
        return
    print(f"\n  ── Slot #{s.slot_id} ──")
    print(f"  Year/form:    {s.year_group}"
          f"{('/' + s.form_group) if s.form_group else ''}")
    print(f"  Day/period:   {s.day_of_week} P{s.period}")
    print(f"  Subject:      {s.subject_code} — {s.subject_name}")
    print(f"  Time:         {s.start_time or '-'} – {s.end_time or '-'}")
    print(f"  Room:         {s.room or '-'}")
    print(f"  Teacher:      {s.teacher or '-'}")
    print(f"  Notes:        {s.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    sid = _ask_id()
    if sid is None:
        return
    existing = data.get_slot(sid)
    if existing is None:
        print("  No slot with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    s = data.update_slot(sid, fields)
    print(f"  Updated slot #{s.slot_id}")


@_safe
def _delete() -> None:
    sid = _ask_id()
    if sid is None:
        return
    existing = data.get_slot(sid)
    if existing is None:
        print("  No slot with that ID.")
        return
    confirm = _prompt(
        f"  Delete slot #{sid} (Yr{existing.year_group} "
        f"{existing.day_of_week} P{existing.period} "
        f"{existing.subject_code})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_slot(sid):
        print(f"  Deleted slot #{sid}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Timetable": open_timetable}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching timetable CLI label: %s", label)
    handler()
    return True
