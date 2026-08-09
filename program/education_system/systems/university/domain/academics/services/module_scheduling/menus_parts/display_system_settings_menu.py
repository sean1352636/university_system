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
            current = scheduler.get_system_setting('institution_name', 'University')
            print(f"Current institution name: {current}")
            new_name = input("Enter new institution name: ").strip()
            if new_name:
                scheduler.update_system_setting('institution_name', new_name)

        elif choice == '3':
            start_date = input("Enter semester start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter semester end date (YYYY-MM-DD): ").strip()

            if start_date:
                scheduler.update_system_setting('semester_start', start_date)
            if end_date:
                scheduler.update_system_setting('semester_end', end_date)

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
