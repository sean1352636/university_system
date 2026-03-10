"""Cinema CLI admin panel main menu."""

import logging

from ..utils import print_header, get_current_user, is_staff_or_admin
from .movies import admin_add_movie, admin_update_movie, admin_view_all_movies
from .screenings import (
    admin_add_screening, admin_update_screening,
    admin_view_all_screenings, admin_create_exclusive_screening,
)
from .reports import (
    admin_booking_reports, admin_revenue_analytics,
    admin_occupancy_report, admin_member_statistics,
)

logger = logging.getLogger(__name__)


def admin_panel():
    """Admin panel for cinema management"""
    user = get_current_user()
    if not user or not is_staff_or_admin(user):
        print("❌ Access denied. Staff/Admin privileges required.")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("CINEMA ADMIN PANEL")
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n🎬 MOVIE MANAGEMENT:")
            print("1. Add New Movie")
            print("2. Update Movie")
            print("3. View All Movies")

            print("\n📅 SCREENING MANAGEMENT:")
            print("4. Add Screening")
            print("5. Update Screening")
            print("6. View All Screenings")

            print("\n📊 REPORTS & ANALYTICS:")
            print("7. Booking Reports")
            print("8. Revenue Analytics")
            print("9. Occupancy Report")
            print("10. Member Statistics")

            print("\n👑 EXCLUSIVE SCREENINGS:")
            print("11. Create Exclusive Screening")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                admin_add_movie()
            elif choice == "2":
                admin_update_movie()
            elif choice == "3":
                admin_view_all_movies()
            elif choice == "4":
                admin_add_screening()
            elif choice == "5":
                admin_update_screening()
            elif choice == "6":
                admin_view_all_screenings()
            elif choice == "7":
                admin_booking_reports()
            elif choice == "8":
                admin_revenue_analytics()
            elif choice == "9":
                admin_occupancy_report()
            elif choice == "10":
                admin_member_statistics()
            elif choice == "11":
                admin_create_exclusive_screening()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in admin panel: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")
