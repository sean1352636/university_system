"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_system_settings_menu(scheduler):
    """Display system settings menu"""
    while True:
        print("\n⚙️  System Settings:")
        print("1. View All Settings")
        print("2. Update Institution Name")
        print("3. Set Semester Dates")
        print("4. Configure Email Notifications")
        print("5. Set Default Session Duration")
        print("6. Custom Setting")
        print("7. Return to Main Menu")

        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            scheduler.list_system_settings()

        elif choice == '2':
            # Read-only here, same as the GUI: the institution name is
            # owned by Branding & Customization. Overriding it from the
            # scheduler put a second value in play that then disagreed
            # with every other screen.
            try:
                from education_system.systems.university.infrastructure.institution_settings import (
                    get_institution_name,
                )
                print(f"Institution name: {get_institution_name()}")
            except Exception:
                print("Institution name: (could not be resolved)")
            print("Change it in Branding & Customization.")

        elif choice == '3':
            # Term dates come from the academic calendar's academic_terms.
            print("Semester dates come from the academic calendar.")
            print("Add or edit the term there; the scheduler follows it.")

        elif choice == '4':
            current = scheduler.get_system_setting('email_notifications', 'False')
            print(f"Email notifications currently: {'Enabled' if current == 'True' else 'Disabled'}")

            enable = input("Enable email notifications? (y/n): ").lower() == 'y'
            scheduler.update_system_setting('email_notifications', str(enable))

        elif choice == '5':
            current = scheduler.get_system_setting('default_session_duration', '60')
            print(f"Current default session duration: {current} minutes")

            try:
                new_duration = int(input("Enter new default duration (minutes): "))
                scheduler.update_system_setting('default_session_duration', str(new_duration))
            except ValueError:
                print("Invalid duration.")

        elif choice == '6':
            key = input("Enter setting key: ").strip()
            value = input("Enter setting value: ").strip()
            if key and value:
                scheduler.update_system_setting(key, value)

        elif choice == '7':
            break

        else:
            print("Invalid choice. Please try again.")
