"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_ical_export_menu(scheduler):
    """Display iCal export menu"""
    print("\n📅 Export to iCal:")
    print("1. Export Student Schedule")
    print("2. Export Instructor Schedule")

    choice = input("Enter your choice (1-2): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        filename = scheduler.export_to_ical('student', student_id)
        if filename:
            print(f"iCal file created: {filename}")
            print("You can import this file into Google Calendar, Outlook, or any calendar app.")

    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            filename = scheduler.export_to_ical('instructor', instructor_id)
            if filename:
                print(f"iCal file created: {filename}")
                print("You can import this file into Google Calendar, Outlook, or any calendar app.")
        except ValueError:
            print("Invalid instructor ID.")

    else:
        print("Invalid choice.")
