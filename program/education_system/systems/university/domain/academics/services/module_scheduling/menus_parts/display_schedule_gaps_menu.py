"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_schedule_gaps_menu(scheduler):
    """Display schedule gaps finder menu"""
    print("\n⏰ Find Schedule Gaps:")
    print("1. Student Schedule Gaps")
    print("2. Instructor Schedule Gaps")

    choice = input("Enter your choice (1-2): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        gaps = scheduler.find_schedule_gaps('student', student_id)

        if isinstance(gaps, str):
            print(gaps)
        else:
            print(f"\nSchedule Gaps for Student {student_id}:")
            print("=" * 60)

            for day, day_gaps in gaps.items():
                print(f"\n{day}:")
                if day_gaps:
                    for gap in day_gaps:
                        print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                else:
                    print("  No gaps (fully scheduled)")

    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            gaps = scheduler.find_schedule_gaps('instructor', instructor_id)

            if isinstance(gaps, str):
                print(gaps)
            else:
                print(f"\nSchedule Gaps for Instructor {instructor_id}:")
                print("=" * 60)

                for day, day_gaps in gaps.items():
                    print(f"\n{day}:")
                    if day_gaps:
                        for gap in day_gaps:
                            print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                    else:
                        print("  No gaps (fully scheduled)")
        except ValueError:
            print("Invalid instructor ID.")

    else:
        print("Invalid choice.")
