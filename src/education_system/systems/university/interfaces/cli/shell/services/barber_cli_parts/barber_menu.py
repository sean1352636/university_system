"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def barber_menu():
    """Main barber shop menu"""
    try:
        # Initialize database
        init_barber_db()
        if BARBER_CORE_AVAILABLE:
            init_extended_barber_db()
    except Exception as e:
        logger.error(f"Failed to initialize barber database: {e}")
        print(f"❌ Failed to initialize barber system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Barber Shop")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY BARBER SHOP")

            if user:
                role_display = user.get('role', 'User').title()
                print(f"\nLogged in as: {user.get('username')} ({role_display})")

            print("\n✂️  MAIN MENU:")
            print("1. Services Management")
            print("2. Staff Information")
            print("3. Appointments")

            if is_staff_or_admin():
                print("4. Reports & Analytics (Staff)")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                services_menu()
            elif choice == "2":
                staff_menu()
            elif choice == "3":
                appointments_menu()
            elif choice == "4" and is_staff_or_admin():
                reports_menu()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in barber menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
