"""CLI flows for the Sixth Form Timetable Optimiser.

Submenu: generate a draft plan / list plans / view a plan / commit a
plan to the live timetable / delete a plan.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.timetable.timetable import DAYS
from education_system.systems.sixth_form.domain.academics.timetable_optimiser import (
    timetable_optimiser as data,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _generate() -> None:
    name = _input("Plan name", default="Auto plan")
    raw = _input("Lessons per group per week", default=str(data.DEFAULT_LESSONS_PER_WEEK))
    try:
        lpw = int(raw)
    except ValueError:
        print("  Invalid number.")
        return _pause()
    try:
        result = data.generate(lessons_per_week=lpw, name=name)
    except ValueError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"\n  Generated: {result.placed} slots placed across "
          f"{result.group_count} groups / {result.teacher_count} teachers.")
    if result.unplaced:
        print(f"  ⚠ {len(result.unplaced)} lesson(s) could not be placed:")
        for u in result.unplaced[:10]:
            print(f"      - {u}")
    if result.student_clashes:
        print(f"  ⚠ {len(result.student_clashes)} soft student clash(es).")
    if _input("Save this plan? (y/N)").lower() == "y":
        pid = data.save_plan(result)
        print(f"  ✓ Saved as plan #{pid} (Draft). Commit it to go live.")
    _pause()


def _list() -> None:
    plans = data.list_plans()
    if not plans:
        print("\n  No plans yet.")
        return _pause()
    print(f"\n  {'ID':>4}  {'Name':<22}{'Status':<11}{'Placed':>7}{'Unpl':>6}  Created")
    print("  " + "-" * 64)
    for p in plans:
        st = p["stats"]
        print(f"  {p['plan_id']:>4}  {p['name'][:20]:<22}{p['status']:<11}"
              f"{st.get('placed', 0):>7}{st.get('unplaced', 0):>6}  {p['created_at']}")
    _pause()


def _view() -> None:
    pid = _input("Plan ID")
    if not pid.isdigit():
        return
    slots = data.plan_slots(int(pid))
    if not slots:
        print("  No slots for that plan.")
        return _pause()
    # Render a simple day-grouped list.
    by_day: dict[int, list] = {}
    for s in slots:
        by_day.setdefault(s.day, []).append(s)
    print()
    for day in sorted(by_day):
        print(f"  {DAYS[day-1]}:")
        for s in sorted(by_day[day], key=lambda x: x.period):
            room = f" @ {s.room}" if s.room else ""
            print(f"      P{s.period}  {s.group_label}{room}")
    _pause()


def _commit() -> None:
    pid = _input("Plan ID to commit")
    if not pid.isdigit():
        return
    if _input("This overwrites live timetable slots for the plan's groups. Continue? (y/N)").lower() != "y":
        print("  Cancelled.")
        return _pause()
    try:
        n = data.commit_plan(int(pid))
    except ValueError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"  ✓ Wrote {n} live timetable slots.")
    _pause()


def _delete() -> None:
    pid = _input("Plan ID to delete")
    if not pid.isdigit():
        return
    data.delete_plan(int(pid))
    print("  ✓ Deleted.")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Generate draft plan", _generate),
    ("List plans", _list),
    ("View plan", _view),
    ("Commit plan to live timetable", _commit),
    ("Delete plan", _delete),
]


def run() -> None:
    while True:
        print("\n── Timetable Optimiser ──")
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
            logger.exception("Timetable-optimiser CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Timetable Optimiser":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Timetable-optimiser CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
