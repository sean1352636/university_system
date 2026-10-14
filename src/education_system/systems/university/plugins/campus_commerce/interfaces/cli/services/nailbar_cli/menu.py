"""Nail bar menu loops and CLI entry point."""

import logging

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg
from .appointments import book_appointment, cancel_appointment, view_my_appointments
from .helpers import get_current_user, is_staff, print_header, print_subheader
from .payments import complete_appointment, view_payment_history
from .reports import (
    customer_retention_stats, daily_schedule_report,
    popular_treatments_analysis, revenue_report,
)
from .technicians import (
    manage_technician_schedule, technician_performance, view_technicians,
)
from .treatments import (
    add_treatment, update_treatment, view_treatments,
    view_treatments_by_category,
)

logger = logging.getLogger(__name__)


def staff_menu():
    """Staff management menu"""
    while True:
        try:
            print_subheader("STAFF MANAGEMENT")

            print("\n📋 TREATMENTS:")
            print("1. Add Treatment")
            print("2. Update Treatment")

            print("\n👩‍💼 TECHNICIANS:")
            print("3. Technician Performance")
            print("4. Manage Schedules")

            print("\n💰 PAYMENTS:")
            print("5. Complete Appointment")
            print("6. Payment History")

            print("\n📊 REPORTS:")
            print("7. Daily Schedule")
            print("8. Revenue Report")
            print("9. Popular Treatments")
            print("10. Customer Retention")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                add_treatment()
            elif choice == "2":
                update_treatment()
            elif choice == "3":
                technician_performance()
            elif choice == "4":
                manage_technician_schedule()
            elif choice == "5":
                complete_appointment()
            elif choice == "6":
                view_payment_history()
            elif choice == "7":
                daily_schedule_report()
            elif choice == "8":
                revenue_report()
            elif choice == "9":
                popular_treatments_analysis()
            elif choice == "10":
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
            logger.error(f"Error in staff menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def nailbar_menu():
    """Main nail bar menu"""
    try:
        # Initialize database
        _pkg.init_nailbar_db()
    except Exception as e:
        logger.error(f"Failed to initialize nail bar database: {e}")
        print(f"❌ Failed to initialize nail bar system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Nail Bar")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY NAIL BAR")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n💅 TREATMENTS:")
            print("1. View All Treatments")
            print("2. Browse by Category")
            print("3. View Technicians")

            print("\n📅 APPOINTMENTS:")
            print("4. Book Appointment")
            print("5. View My Appointments")
            print("6. Cancel Appointment")

            if is_staff():
                print("\n👩‍💼 STAFF MENU:")
                print("7. Staff Management")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_treatments()
            elif choice == "2":
                view_treatments_by_category()
            elif choice == "3":
                view_technicians()
            elif choice == "4":
                book_appointment()
            elif choice == "5":
                view_my_appointments()
            elif choice == "6":
                cancel_appointment()
            elif choice == "7" and is_staff():
                staff_menu()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in nail bar menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def launch_nailbar_cli(auth=None):
    """Launch nail bar CLI (called from main menu)"""
    nailbar_menu()


__all__ = ['staff_menu', 'nailbar_menu', 'launch_nailbar_cli']


if __name__ == "__main__":
    nailbar_menu()
