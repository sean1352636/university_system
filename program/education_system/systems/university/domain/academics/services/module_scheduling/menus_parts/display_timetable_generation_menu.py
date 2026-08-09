"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_timetable_generation_menu(scheduler):
    """Display the timetable generation menu"""
    while True:
        print("\nTimetable Generation Menu:")
        print("=========================")
        print("1. Generate Student Timetable")
        print("2. Generate Instructor Timetable")
        print("3. Generate Room Schedule")
        print("4. Generate Department Schedule")
        print("5. Export to Various Formats")
        print("6. Return to Previous Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            display_student_timetable_menu(scheduler)
        elif choice == '2':
            display_instructor_timetable_menu(scheduler)
        elif choice == '3':
            room_id = input("Enter room ID (or leave empty to list all): ")
            if room_id:
                try:
                    scheduler.view_room_schedule(int(room_id))
                except ValueError:
                    print("Invalid room ID.")
            else:
                scheduler.view_room_schedule()
        elif choice == '4':
            department = input("Enter department name: ")
            if department:
                display_department_schedule(scheduler, department)
        elif choice == '5':
            display_export_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")
