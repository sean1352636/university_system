"""
Faculty Schedule Menu - Weekly faculty schedule building CLI.

Wired to FacultyScheduleManager (schedule blocks, conflict-checked
create/update/delete, templates, teaching import, and reporting).
"""

from education_system.systems.university.domain.staff.staff_hr.services.managers import (
    FacultyScheduleManager,
)

DAY_NAMES = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
    4: 'Friday', 5: 'Saturday', 6: 'Sunday',
}


def display_faculty_schedule_menu(user_id: str) -> None:
    """Display the faculty schedule menu."""
    while True:
        print("\n" + "=" * 60)
        print("FACULTY SCHEDULE")
        print("=" * 60)

        print("\n  1. View My Schedule")
        print("  2. Weekly Summary")
        print("  3. Add Schedule Block")
        print("  4. Update Block")
        print("  5. Delete Block")
        print("  6. Import Teaching Schedule")
        print("  7. My Templates")
        print("  8. Save Schedule as Template")
        print("  9. Load Template")
        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_schedule(user_id)
        elif choice == '2':
            _weekly_summary(user_id)
        elif choice == '3':
            _add_block(user_id)
        elif choice == '4':
            _update_block()
        elif choice == '5':
            _delete_block()
        elif choice == '6':
            _import_teaching(user_id)
        elif choice == '7':
            _list_templates(user_id)
        elif choice == '8':
            _save_template(user_id)
        elif choice == '9':
            _load_template(user_id)
        else:
            print("Invalid choice.")


def _prompt_int(label: str, default: int | None = None) -> int | None:
    """Prompt for an integer, returning default on empty input."""
    raw = input(label).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Invalid number.")
        return default


def _view_schedule(user_id: str) -> None:
    """View a user's schedule blocks."""
    blocks = FacultyScheduleManager.get_user_schedule(user_id)
    print("\n" + "-" * 60)
    print("MY SCHEDULE")
    print("-" * 60)
    if blocks:
        for b in blocks:
            day = DAY_NAMES.get(b.get('day_of_week'), f"Day {b.get('day_of_week')}")
            locked = ' [locked]' if b.get('is_locked') else ''
            print(f"  {b.get('block_id')}. {day} "
                  f"{b.get('start_time')}-{b.get('end_time')} "
                  f"({b.get('activity_type')}){locked}")
            if b.get('title'):
                print(f"      {b.get('title')}")
    else:
        print("  No schedule blocks found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _weekly_summary(user_id: str) -> None:
    """Display the weekly hours summary."""
    summary = FacultyScheduleManager.get_weekly_summary(user_id)
    print("\n" + "-" * 60)
    print("WEEKLY SUMMARY")
    print("-" * 60)
    print(f"  Total Hours: {summary.get('total_hours', 0)}")
    by_type = summary.get('by_type', {})
    if by_type:
        print("\n  By Activity:")
        for activity, hours in by_type.items():
            print(f"    - {activity}: {hours}h")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_block(user_id: str) -> None:
    """Add a schedule block."""
    print("\n--- Add Schedule Block ---")
    print("Days: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun")
    day_of_week = _prompt_int("Day of Week (0-6): ")
    if day_of_week is None:
        return
    start_time = input("Start Time (HH:MM): ").strip()
    end_time = input("End Time (HH:MM): ").strip()
    if not start_time or not end_time:
        print("Start and end times are required.")
        input("Press Enter to continue...")
        return
    activity_type = input("Activity Type [teaching]: ").strip() or 'teaching'
    title = input("Title (optional): ").strip() or None
    location = input("Location (optional): ").strip() or None
    course_code = input("Course Code (optional): ").strip() or None
    try:
        block_id = FacultyScheduleManager.create_block(
            user_id, day_of_week, start_time, end_time,
            activity_type=activity_type, title=title,
            location=location, course_code=course_code)
        print(f"\nBlock created. ID: {block_id}")
    except ValueError as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _update_block() -> None:
    """Update a schedule block."""
    print("\n--- Update Block ---")
    block_id = _prompt_int("Block ID: ")
    if block_id is None:
        return
    title = input("New Title (blank to skip): ").strip()
    location = input("New Location (blank to skip): ").strip()
    start_time = input("New Start Time HH:MM (blank to skip): ").strip()
    end_time = input("New End Time HH:MM (blank to skip): ").strip()
    data = {}
    if title:
        data['title'] = title
    if location:
        data['location'] = location
    if start_time:
        data['start_time'] = start_time
    if end_time:
        data['end_time'] = end_time
    if not data:
        print("Nothing to update.")
        input("Press Enter to continue...")
        return
    try:
        FacultyScheduleManager.update_block(block_id, **data)
        print("\nBlock updated.")
    except ValueError as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _delete_block() -> None:
    """Delete a schedule block."""
    block_id = _prompt_int("Block ID to delete: ")
    if block_id is None:
        return
    try:
        FacultyScheduleManager.delete_block(block_id)
        print("\nBlock deleted.")
    except ValueError as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _import_teaching(user_id: str) -> None:
    """Import teaching schedule from module data."""
    semester = input("Semester (optional): ").strip() or None
    academic_year = input("Academic Year (optional): ").strip() or None
    try:
        count = FacultyScheduleManager.import_teaching_schedule(
            user_id, semester=semester, academic_year=academic_year)
        print(f"\nImported {count} teaching block(s).")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_templates(user_id: str) -> None:
    """List available schedule templates."""
    templates = FacultyScheduleManager.get_templates(user_id=user_id)
    print("\n" + "-" * 60)
    print("SCHEDULE TEMPLATES")
    print("-" * 60)
    if templates:
        for t in templates:
            shared = ' [shared]' if t.get('is_shared') else ''
            print(f"  {t.get('template_id')}. {t.get('name')}{shared}")
            if t.get('description'):
                print(f"      {t.get('description')}")
    else:
        print("  No templates found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _save_template(user_id: str) -> None:
    """Save the current schedule as a template."""
    print("\n--- Save as Template ---")
    name = input("Template Name: ").strip()
    if not name:
        print("Name is required.")
        input("Press Enter to continue...")
        return
    description = input("Description (optional): ").strip() or None
    is_shared = input("Share with others? (y/N): ").strip().lower() == 'y'
    try:
        template_id = FacultyScheduleManager.save_as_template(
            user_id, name, description=description, is_shared=is_shared)
        print(f"\nTemplate saved. ID: {template_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _load_template(user_id: str) -> None:
    """Load a template into the user's schedule."""
    print("\n--- Load Template ---")
    template_id = _prompt_int("Template ID: ")
    if template_id is None:
        return
    clear_existing = input(
        "Clear existing unlocked blocks first? (y/N): ").strip().lower() == 'y'
    try:
        count = FacultyScheduleManager.load_template(
            template_id, user_id, clear_existing=clear_existing)
        print(f"\nLoaded {count} block(s) from template.")
    except ValueError as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")
