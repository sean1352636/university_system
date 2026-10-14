"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def staff_menu():
    """Staff management menu"""
    while True:
        try:
            print_header("STAFF MANAGEMENT")

            print("\n1. View All Staff")
            print("2. View Staff Schedules (Staff)")
            print("3. Staff Performance Metrics (Staff)")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_staff()
            elif choice == "2":
                view_staff_schedules()
            elif choice == "3":
                staff_performance_metrics()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in staff menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
