"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def appointments_menu():
    """Appointments management menu"""
    while True:
        try:
            print_header("APPOINTMENTS")

            print("\n📅 CUSTOMER:")
            print("1. Book Appointment")
            print("2. View My Appointments")
            print("3. Cancel Appointment")
            print("4. Reschedule Appointment")

            if is_staff_or_admin():
                print("\n👨‍💼 STAFF:")
                print("5. Check-In Customer")
                print("6. Complete Appointment")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                book_appointment()
            elif choice == "2":
                view_my_appointments()
            elif choice == "3":
                cancel_appointment()
            elif choice == "4":
                reschedule_appointment()
            elif choice == "5" and is_staff_or_admin():
                check_in_appointment()
            elif choice == "6" and is_staff_or_admin():
                complete_appointment()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in appointments menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
