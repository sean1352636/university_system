"""Cinema CLI main menu and entry point."""

import logging

from education_system.university_system.modules.services.cli.cinema_cli.db import init_cinema_db
from education_system.university_system.modules.services.cli.cinema_cli.utils import print_header, get_current_user, is_staff_or_admin
from education_system.university_system.modules.services.cli.cinema_cli.movies import view_movies, search_movies, view_movie_details
from education_system.university_system.modules.services.cli.cinema_cli.screenings import view_screenings
from education_system.university_system.modules.services.cli.cinema_cli.booking import book_tickets, view_my_bookings
from education_system.university_system.modules.services.cli.cinema_cli.membership import membership_menu, get_user_membership
from education_system.university_system.modules.services.cli.cinema_cli.admin import admin_panel

logger = logging.getLogger(__name__)


def cinema_menu():
    """Main cinema menu"""
    try:
        # Initialize database
        init_cinema_db()
    except Exception as e:
        logger.error(f"Failed to initialize cinema database: {e}", exc_info=True)
        print(f"❌ Failed to initialize cinema system: {e}")
        input("\n📌 Press Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Cinema")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY CINEMA")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

                # Show membership status
                membership = get_user_membership(user.get('username'))
                if membership:
                    print(f"💳 Member Status: ACTIVE | Points: {membership['points_balance']}")

            print("\n🎬 MOVIE BROWSING:")
            print("1. View Movies (Now Showing & Coming Soon)")
            print("2. Search Movies")
            print("3. View Movie Details")

            print("\n🎟️  TICKET BOOKING:")
            print("4. View Screenings")
            print("5. Book Tickets")
            print("6. View My Bookings")

            print("\n💳 MEMBERSHIP PROGRAM:")
            print("7. Membership Menu")

            # Show admin options for staff/admin
            if is_staff_or_admin(user):
                print("\n👑 ADMIN PANEL:")
                print("8. Cinema Administration")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_movies()
            elif choice == "2":
                search_movies()
            elif choice == "3":
                view_movie_details()
            elif choice == "4":
                view_screenings()
            elif choice == "5":
                book_tickets()
            elif choice == "6":
                view_my_bookings()
            elif choice == "7":
                membership_menu()
            elif choice == "8" and is_staff_or_admin(user):
                admin_panel()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in cinema menu: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")


def launch_cinema_cli(auth=None):
    """Launch cinema CLI (called from main menu)"""
    cinema_menu()
