"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def services_menu():
    """Services management menu"""
    while True:
        try:
            print_header("SERVICES MANAGEMENT")

            print("\n1. View All Services")
            print("2. Add New Service (Staff)")
            print("3. Update Service (Staff)")
            print("4. Enable/Disable Service (Staff)")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_services()
            elif choice == "2":
                add_service()
            elif choice == "3":
                update_service()
            elif choice == "4":
                toggle_service_availability()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in services menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
