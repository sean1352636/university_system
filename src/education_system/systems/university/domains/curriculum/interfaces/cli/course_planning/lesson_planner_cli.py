"""
Lesson Planner — interactive CLI, over the merged scheduling model.

The planner used to keep its own timetable (``lesson_plans``) and its own
course list (``lesson_courses``), neither visible to Module Scheduling, the
conflict detector or Timetable Management. Both are retired. The timetable is
``module_schedule``; a lesson is now *content* — title, delivery type, notes —
attached to one of its slots. The GUI equivalent is Module Scheduling →
Lesson Plans.

So the flow here is slot-first: list the scheduled slots, pick one, and write
the lesson for it. Day, time, room and instructor are not editable here —
they belong to the slot, and are changed in Module Scheduling (CLI: the
scheduling menu; GUI: the Schedules tab).

The separate DEGREE planner (semester plans / prerequisites) lives in
``planning_cli.PlanningCLI`` and is unrelated.
"""

from __future__ import annotations

from typing import Optional

from education_system.systems.university.domains.curriculum.domain.course_planning.services import (
    lesson_service,
)

_LESSON_TYPES = list(lesson_service.LESSON_TYPES)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{text}{suffix}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = _prompt(text)
        if not raw:
            if allow_blank:
                return None
            print("A number is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Enter a whole number.")


def _pause() -> None:
    try:
        input("\nPress Enter to continue...")
    except (KeyboardInterrupt, EOFError):
        print()


def _header(title: str) -> None:
    print("\n" + "=" * 50)
    print(f"    {title.upper()}")
    print("=" * 50)


def _current_username(auth) -> str:
    user = getattr(auth, "current_user", None) or {}
    if isinstance(user, dict):
        return user.get("username") or ""
    return getattr(user, "username", "") or ""


# --------------------------------------------------------------------------- #
# 1. Slots and their lessons
# --------------------------------------------------------------------------- #
def _list_slots() -> None:
    search = _prompt("Search text (optional)")
    slots = lesson_service.list_slots(search or None)
    if not slots:
        print("\nNo scheduled slots found. Create one in Module Scheduling first.")
        return
    print(f"\n{'Slot':<6}{'Module':<12}{'Day':<11}{'Time':<14}{'Room':<14}"
          f"{'Status':<11}Lesson")
    print("-" * 96)
    for slot in slots:
        time = f"{slot.get('start_time') or '?'}-{slot.get('end_time') or '?'}"
        print(f"{slot['schedule_id']:<6}"
              f"{(slot.get('module_code') or '')[:11]:<12}"
              f"{(slot.get('day_of_week') or '')[:10]:<11}"
              f"{time[:13]:<14}"
              f"{(slot.get('room') or '-')[:13]:<14}"
              f"{(slot.get('status') or '')[:10]:<11}"
              f"{slot.get('title') or '(no lesson)'}")

    orphans = lesson_service.unscheduled()
    if orphans:
        print(f"\n{len(orphans)} lesson(s) with no slot:")
        for lesson in orphans:
            print(f"   lesson {lesson['lesson_id']}: {lesson.get('title') or ''} "
                  f"({lesson.get('module_code') or '?'}, "
                  f"was {lesson.get('legacy_slot') or 'unknown'})")


def _set_lesson(auth) -> None:
    slot_id = _prompt_int("Slot id to write the lesson for", allow_blank=False)
    slot = lesson_service.get_slot(slot_id)
    if slot is None:
        print(f"\nNo scheduled slot with id {slot_id}.")
        return
    print(f"\n{slot.get('module_code')} — {slot.get('day_of_week')} "
          f"{slot.get('start_time')}-{slot.get('end_time')} "
          f"in {slot.get('room') or 'no room'}")
    if slot.get("title"):
        print(f"Current lesson: {slot['title']}")

    title = _prompt("Lesson title", default=slot.get("title") or "")
    if not title:
        print("A title is required.")
        return
    ltype = _prompt(f"Type ({'/'.join(_LESSON_TYPES)})",
                    default=slot.get("lesson_type") or slot.get("session_type") or "")
    notes = _prompt("Notes (optional)", default=slot.get("notes") or "")
    try:
        lesson_id = lesson_service.set_lesson(
            slot_id, title, lesson_type=ltype, notes=notes,
            updated_by=_current_username(auth))
        print(f"\n✓ Lesson saved for slot {slot_id} (id={lesson_id}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _clear_lesson() -> None:
    lesson_id = _prompt_int("Lesson id to delete", allow_blank=False)
    print("This removes the lesson plan only — the scheduled slot stays.")
    if _prompt("Type 'yes' to confirm").lower() != "yes":
        print("Cancelled.")
        return
    if lesson_service.clear_lesson(lesson_id):
        print(f"\n✓ Deleted lesson {lesson_id}.")
    else:
        print(f"\nNo lesson with id {lesson_id}.")


def _attach_lesson() -> None:
    orphans = lesson_service.unscheduled()
    if not orphans:
        print("\nEvery lesson already has a slot.")
        return
    for lesson in orphans:
        print(f"   lesson {lesson['lesson_id']}: {lesson.get('title') or ''} "
              f"({lesson.get('module_code') or '?'})")
    lesson_id = _prompt_int("Lesson id to place", allow_blank=False)
    slot_id = _prompt_int("Slot id to attach it to", allow_blank=False)
    if lesson_service.get_slot(slot_id) is None:
        print(f"\nNo scheduled slot with id {slot_id}.")
        return
    if lesson_service.attach_lesson(lesson_id, slot_id):
        print(f"\n✓ Lesson {lesson_id} now belongs to slot {slot_id}.")
    else:
        print("\n✗ Could not attach that lesson.")


def _hours_summary() -> None:
    rows = lesson_service.weekly_hours()
    if not rows:
        print("\nNothing scheduled to summarise.")
        return
    print(f"\n{'Module':<24}Weekly hours")
    print("-" * 40)
    for row in rows:
        print(f"{(row.get('module_code') or '')[:23]:<24}{row.get('hours')}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_lesson_planner_menu(auth) -> None:
    """Run the Lesson Planner CLI loop."""
    while True:
        _header("Lesson Planner")
        print("1. List scheduled slots and lessons")
        print("2. Write / update the lesson for a slot")
        print("3. Delete a lesson plan")
        print("4. Place an unscheduled lesson on a slot")
        print("5. Planned contact-hours summary")
        print("6. Return to Main Menu")
        print("=" * 50)
        print("Times, rooms and instructors are set in Module Scheduling.")

        try:
            choice = input("\nEnter your choice (1-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _list_slots()
                _pause()
            elif choice == "2":
                _set_lesson(auth)
                _pause()
            elif choice == "3":
                _clear_lesson()
                _pause()
            elif choice == "4":
                _attach_lesson()
                _pause()
            elif choice == "5":
                _hours_summary()
                _pause()
            elif choice == "6":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
