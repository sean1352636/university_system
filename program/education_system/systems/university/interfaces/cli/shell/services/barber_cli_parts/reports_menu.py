"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def reports_menu():
    """Reports and analytics menu (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("REPORTS & ANALYTICS")

            print("\n1. Daily Schedule")
            print("2. Revenue Report")
            print("3. Service Popularity Analysis")
            print("4. Customer Retention Statistics")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                daily_schedule()
            elif choice == "2":
                revenue_report()
            elif choice == "3":
                service_popularity_report()
            elif choice == "4":
                customer_retention_stats()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in reports menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
