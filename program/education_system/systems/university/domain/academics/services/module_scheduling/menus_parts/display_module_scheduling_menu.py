"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_module_scheduling_menu():
    """Display the module scheduling menu and handle user choices"""
    scheduler = ModuleScheduler()

    while True:
        print("\nModule Scheduling and Timetable Menu:")
        print("=====================================")
        print("1. Manage Rooms")
        print("2. Manage Instructors")
        print("3. Manage Module Schedules")
        print("4. View Module Schedules")
        print("5. View Room Schedules")
        print("6. View Instructor Schedules")
        print("7. Generate Student Timetable")
        print("8. Generate Instructor Timetable")
        print("9. Check for Scheduling Conflicts")
        print("10. Return to Main Menu")

        choice = input("\nEnter your choice (1-10): ")

        if choice == '1':
            display_room_menu(scheduler)
        elif choice == '2':
            display_instructor_menu(scheduler)
        elif choice == '3':
            display_schedule_menu(scheduler)
        elif choice == '4':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '5':
            scheduler.view_room_schedule()
        elif choice == '6':
            scheduler.view_instructor_schedule()
        elif choice == '7':
            display_student_timetable_menu(scheduler)
        elif choice == '8':
            display_instructor_timetable_menu(scheduler)
        elif choice == '9':
            student_id = input("Enter student ID: ")
            scheduler.display_student_conflicts(student_id)
        elif choice == '10':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")
