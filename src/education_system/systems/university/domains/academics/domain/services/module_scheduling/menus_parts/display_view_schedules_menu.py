"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_view_schedules_menu(scheduler):
    """Display the view schedules menu"""
    while True:
        print("\nView Schedules Menu:")
        print("===================")
        print("1. View Module Schedules")
        print("2. View Room Schedules")
        print("3. View Instructor Schedules")
        print("4. View All Schedules")
        print("5. Search Schedules")
        print("6. Return to Previous Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '2':
            scheduler.view_room_schedule()
        elif choice == '3':
            scheduler.view_instructor_schedule()
        elif choice == '4':
            scheduler.view_module_schedule(None)
        elif choice == '5':
            display_advanced_search_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")
