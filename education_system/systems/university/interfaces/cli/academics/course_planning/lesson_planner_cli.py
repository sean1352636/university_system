"""
Lesson / Timetable Planner — interactive CLI.

Wired to the plain CRUD helpers in
``course_planning.services.lesson_service``, which read/write the shared
``student_records.db`` tables ``lesson_plans`` and ``lesson_courses`` — the
same tables the Lesson Planner GUI (``lesson_planner.py``) persists to.
Anything created here is visible in the GUI and vice-versa.

This is the pedagogical LESSON/timetable side. The separate DEGREE planner
(semester plans / prerequisites) lives in ``planning_cli.PlanningCLI`` and is
unrelated.

Covers: Lessons (list/add/update/delete), Courses (list/add/update/delete),
and a read-only planned contact-hours summary.
"""

from __future__ import annotations

from typing import Optional

from education_system.systems.university.domain.academics.course_planning.services import (
    lesson_service,
)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_LESSON_TYPES = ["Lecture", "Seminar", "Lab", "Tutorial", "Workshop", "Exam"]


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


# --------------------------------------------------------------------------- #
# 1. Lessons
# --------------------------------------------------------------------------- #
def _list_lessons() -> None:
    search = _prompt("Search text (optional)")
    lessons = lesson_service.list_lessons(search=search or None)
    if not lessons:
        print("\nNo lessons found.")
        return
    print(f"\n{'ID':<5}{'Course':<18}{'Title':<22}{'Type':<10}"
          f"{'Day':<11}{'Time':<14}Room")
    print("-" * 92)
    for row in lessons:
        time = f"{row.get('start') or '?'}-{row.get('end') or '?'}"
        print(f"{row['id']:<5}{(row.get('course') or '')[:17]:<18}"
              f"{(row.get('title') or '')[:21]:<22}"
              f"{(row.get('type') or '')[:9]:<10}"
              f"{(row.get('day') or '')[:10]:<11}"
              f"{time[:13]:<14}{row.get('room') or '-'}")


def _add_lesson(auth) -> None:
    course = _prompt("Course (e.g. 'CS101 - Intro')")
    title = _prompt("Lesson title")
    if not course or not title:
        print("Course and title are required.")
        return
    instructor = _prompt("Instructor (optional)")
    ltype = _prompt(f"Type ({'/'.join(_LESSON_TYPES)})", default="Lecture")
    day = _prompt(f"Day ({'/'.join(_DAYS)})", default="Monday")
    start = _prompt("Start time (HH:MM)")
    end = _prompt("End time (HH:MM)")
    if start and end and start >= end:
        print("End time must be after start time.")
        return
    room = _prompt("Room (optional)")
    notes = _prompt("Notes (optional)")
    try:
        lid = lesson_service.add_lesson(
            course, title, instructor=instructor, type=ltype, day=day,
            start=start, end=end, room=room, notes=notes,
            updated_by=_current_username(auth))
        print(f"\n✓ Added lesson '{title}' (id={lid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_lesson(auth) -> None:
    lid = _prompt_int("Lesson id", allow_blank=False)
    current = lesson_service.get_lesson(lid)
    if not current:
        print(f"\nNo lesson with id {lid}.")
        return
    print("Leave a field blank to keep its current value.")
    fields = {}
    for key, label in (("course", "Course"), ("title", "Title"),
                       ("instructor", "Instructor"), ("type", "Type"),
                       ("day", "Day"), ("start", "Start (HH:MM)"),
                       ("end", "End (HH:MM)"), ("room", "Room"),
                       ("notes", "Notes")):
        val = _prompt(f"{label} [{current.get(key) or '-'}]")
        if val:
            fields[key] = val
    if not fields:
        print("Nothing to update.")
        return
    try:
        if lesson_service.update_lesson(
                lid, updated_by=_current_username(auth), **fields):
            print(f"\n✓ Updated lesson {lid}.")
        else:
            print(f"\nNo change made to lesson {lid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_lesson() -> None:
    lid = _prompt_int("Lesson id to delete", allow_blank=False)
    try:
        if lesson_service.delete_lesson(lid):
            print(f"\n✓ Deleted lesson {lid}.")
        else:
            print(f"\nNo lesson with id {lid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _lessons_menu(auth) -> None:
    while True:
        _header("Lessons")
        print("[1] List lessons")
        print("[2] Add lesson")
        print("[3] Update lesson")
        print("[4] Delete lesson")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_lessons()
        elif choice == "2":
            _add_lesson(auth)
        elif choice == "3":
            _update_lesson(auth)
        elif choice == "4":
            _delete_lesson()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Courses
# --------------------------------------------------------------------------- #
def _list_courses() -> None:
    courses = lesson_service.list_courses()
    if not courses:
        print("\nNo planner-local courses found.")
        return
    print(f"\n{'Code':<12}{'Name':<26}{'Department':<18}{'Credits':<9}Semester")
    print("-" * 78)
    for c in courses:
        print(f"{(c.get('code') or '')[:11]:<12}"
              f"{(c.get('name') or '')[:25]:<26}"
              f"{(c.get('dept') or '')[:17]:<18}"
              f"{(str(c.get('credits') or ''))[:8]:<9}"
              f"{c.get('semester') or '-'}")


def _add_course(auth) -> None:
    code = _prompt("Course code")
    name = _prompt("Course name")
    if not code or not name:
        print("Course code and name are required.")
        return
    dept = _prompt("Department (optional)")
    credits = _prompt("Credits (optional)")
    semester = _prompt("Semester (optional)")
    description = _prompt("Description (optional)")
    try:
        lesson_service.add_course(
            code, name, dept=dept, credits=credits, semester=semester,
            description=description, updated_by=_current_username(auth))
        print(f"\n✓ Added course '{code}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_course(auth) -> None:
    code = _prompt("Course code to update")
    current = lesson_service.get_course(code)
    if not current:
        print(f"\nNo planner-local course with code '{code}'.")
        return
    print("Leave a field blank to keep its current value.")
    fields = {}
    for key, label in (("name", "Name"), ("dept", "Department"),
                       ("credits", "Credits"), ("semester", "Semester"),
                       ("description", "Description")):
        val = _prompt(f"{label} [{current.get(key) or '-'}]")
        if val:
            fields[key] = val
    if not fields:
        print("Nothing to update.")
        return
    try:
        if lesson_service.update_course(
                code, updated_by=_current_username(auth), **fields):
            print(f"\n✓ Updated course '{code}'.")
        else:
            print(f"\nNo change made to course '{code}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_course() -> None:
    code = _prompt("Course code to delete")
    if not code:
        print("Course code is required.")
        return
    try:
        if lesson_service.delete_course(code):
            print(f"\n✓ Deleted course '{code}'.")
        else:
            print(f"\nNo planner-local course with code '{code}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _courses_menu(auth) -> None:
    while True:
        _header("Courses (planner-local)")
        print("[1] List courses")
        print("[2] Add course")
        print("[3] Update course")
        print("[4] Delete course")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_courses()
        elif choice == "2":
            _add_course(auth)
        elif choice == "3":
            _update_course(auth)
        elif choice == "4":
            _delete_course()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Contact-hours summary
# --------------------------------------------------------------------------- #
def _hours_summary() -> None:
    rows = lesson_service.contact_hours_by_course()
    if not rows:
        print("\nNo lessons to summarise.")
        return
    print(f"\n{'Course':<24}{'Lessons':<10}Weekly hours")
    print("-" * 46)
    for r in rows:
        print(f"{(r.get('course') or '')[:23]:<24}"
              f"{r.get('lessons'):<10}{r.get('hours')}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_lesson_planner_menu(auth) -> None:
    """Run the Lesson / Timetable Planner CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("    LESSON / TIMETABLE PLANNER")
        print("=" * 50)
        print("1. Lessons")
        print("2. Courses")
        print("3. Planned contact-hours summary")
        print("4. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _lessons_menu(auth)
            elif choice == "2":
                _courses_menu(auth)
            elif choice == "3":
                _hours_summary()
                _pause()
            elif choice == "4":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
