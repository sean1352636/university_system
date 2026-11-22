"""Student Union CLI menus (portal, clubs, events, facilities, elections, admin).

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""


from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import generate_advanced_analytics
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import manage_academic_support
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import manage_enhanced_voting
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import manage_green_initiatives
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import manage_learning_integration
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import manage_peer_support_system
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import view_facilities
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text

from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (
    logger,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.clubs import (
    create_club,
    delete_club,
    join_club,
    manage_club,
    update_club,
    view_clubs,
    view_my_clubs,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.events import (
    create_event,
    delete_event,
    register_for_event,
    update_event,
    view_events,
    view_my_events,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.elections import (
    create_election,
    delete_election,
    nominate_for_election,
    update_election,
    view_election_results,
    view_elections,
    vote_in_election,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.facility_bookings import (
    approve_facility_bookings,
    request_facility_booking,
    view_my_bookings,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.admin_tasks import (
    manage_union_reps,
    set_up_election,
)

# The menus read this module's ``auth``. student_union_core.set_auth reaches it
# through _AUTH_TARGET_MODULES, like every other Student Union submodule.
auth = None


def set_auth(auth_obj):
    """Set the auth object the Student Union menus check."""
    global auth
    auth = auth_obj


def display_student_union_menu():
    """Enhanced Student Union Portal.

    Anything created here (clubs, events, elections, bookings, …) is
    mirrored onto the university academic calendar as it is created —
    see ``calendar_bridge`` — so there is no manual calendar sync.
    """
    global auth
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.clubs.club_management.rewards import manage_engagement_rewards
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.clubs.club_management.competitions import manage_interclub_competitions
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.clubs.club_management.mentorship import manage_mentorship_system
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.facilities.facility_management import manage_equipment_system
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.clubs.club_management.community import manage_community_engagement
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.event_management import manage_virtual_events

    if not auth or not auth.current_user:
        print(get_text('union.login_required', default="You must be logged in to access the Student Union Portal."))
        return

    while True:
        print(f"\n🏛️ {get_text('union.title', default='Enhanced Student Union Portal')}")
        print("=" * 45)

        # Core features
        print(f"📋 {get_text('union.section.core', default='CORE FEATURES')}")
        print(f"1. {get_text('union.menu.clubs', default='Club Management')}")
        print(f"2. {get_text('union.menu.events', default='Events & Activities')}")
        print(f"3. {get_text('union.menu.facilities', default='Facilities & Bookings')}")
        print(f"4. {get_text('union.menu.elections', default='Elections & Democracy')}")

        # Enhanced features
        print(f"\n🌟 {get_text('union.section.enhanced', default='ENHANCED FEATURES')}")
        print(f"5. {get_text('union.menu.rewards', default='Engagement Rewards System')}")
        print(f"6. {get_text('union.menu.competitions', default='Inter-club Competitions')}")
        print(f"7. {get_text('union.menu.peer_support', default='Peer Support & Wellness')}")
        print(f"8. {get_text('union.menu.academic_support', default='Academic Support')}")
        print(f"9. {get_text('union.menu.mentorship', default='Mentorship Program')}")

        # Specialized systems
        print(f"\n🎯 {get_text('union.section.specialized', default='SPECIALIZED SYSTEMS')}")
        print(f"10. {get_text('union.menu.equipment', default='Equipment Management')}")
        print(f"11. {get_text('union.menu.green', default='Green Initiatives')}")
        print(f"12. {get_text('union.menu.community', default='Community Engagement')}")
        print(f"13. {get_text('union.menu.virtual', default='Virtual Events')}")
        print(f"14. {get_text('union.menu.learning', default='Learning Integration')}")

        # Analytics and admin
        print(f"\n📊 {get_text('union.section.analytics', default='ANALYTICS & ADMIN')}")
        if auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results'):
            print(f"15. {get_text('union.menu.analytics', default='Advanced Analytics')}")
            print(f"16. {get_text('union.menu.voting', default='Enhanced Voting System')}")
            print(f"17. {get_text('union.menu.admin', default='Admin Dashboard')}")

        # Navigation options
        print(f"\n18. {get_text('union.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('union.prompt.choice', default='Choose an option (1-18)')}: ").strip()

        # Core features
        if choice == '1':
            display_club_menu()
        elif choice == '2':
            display_event_menu()
        elif choice == '3':
            display_facility_menu()
        elif choice == '4':
            display_election_menu()

        # Enhanced features
        elif choice == '5':
            manage_engagement_rewards()
        elif choice == '6':
            manage_interclub_competitions()
        elif choice == '7':
            manage_peer_support_system()
        elif choice == '8':
            manage_academic_support()
        elif choice == '9':
            manage_mentorship_system()

        # Specialized systems
        elif choice == '10':
            manage_equipment_system()
        elif choice == '11':
            manage_green_initiatives()
        elif choice == '12':
            manage_community_engagement()
        elif choice == '13':
            manage_virtual_events()
        elif choice == '14':
            manage_learning_integration()

        # Analytics and admin
        elif choice == '15' and (auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results')):
            generate_advanced_analytics()
        elif choice == '16' and auth.check_permission('set_up_elections'):
            manage_enhanced_voting()
        elif choice == '17' and (auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results')):
            display_admin_menu()

        # Navigation
        elif choice == '18':
            print(get_text('union.returning', default='Returning to main menu...'))
            return
        else:
            print(get_text('union.invalid_choice', default="Invalid choice. Please try again."))

def display_club_menu():
    """Display the club management menu"""
    global auth

    while True:
        print("\nClub Management")
        print("===============")

        # Options based on permissions
        options = []
        option_num = 1

        # View Clubs
        print(f"{option_num}. View Available Clubs")
        options.append("view_clubs")
        option_num += 1

        # View My Clubs
        print(f"{option_num}. View My Club Memberships")
        options.append("view_my_clubs")
        option_num += 1

        # Join a Club
        if auth.check_permission('join_clubs'):
            print(f"{option_num}. Join a Club")
            options.append("join_club")
            option_num += 1

        # Manage Club
        if auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage Club")
            options.append("manage_club")
            option_num += 1

        # Create Club
        if auth.check_permission('create_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Create New Club")
            options.append("create_club")
            option_num += 1

        # Update / Delete Club — previously there was no way to change a
        # club's details or close one down at all.
        if auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Update Club")
            options.append("update_club")
            option_num += 1

        if auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Delete Club")
            options.append("delete_club")
            option_num += 1

        # Return to Student Union Menu
        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        # First check if user wants to return to main menu
        if choice == str(option_num):
            return

        # Then map the numeric choice to the actual option based on available permissions
        try:
            choice_index = int(choice) - 1  # Convert to 0-based index
            if 0 <= choice_index < len(options):
                selected_option = options[choice_index]

                if selected_option == "view_clubs":
                    view_clubs()
                elif selected_option == "view_my_clubs":
                    view_my_clubs()
                elif selected_option == "join_club":
                    join_club()
                elif selected_option == "manage_club":
                    manage_club()
                elif selected_option == "create_club":
                    create_club()
                elif selected_option == "update_club":
                    update_club()
                elif selected_option == "delete_club":
                    delete_club()
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")

def display_event_menu():
    """Display the event management menu"""
    global auth

    while True:
        print("\nEvents")
        print("======")

        # Options are built dynamically so the numbering stays correct when a
        # permission hides one. Create/Update/Delete previously did not exist.
        options = []
        option_num = 1

        print(f"{option_num}. View Upcoming Events")
        options.append("view_events")
        option_num += 1

        print(f"{option_num}. View My Registered Events")
        options.append("view_my_events")
        option_num += 1

        if auth.check_permission('register_for_events'):
            print(f"{option_num}. Register for an Event")
            options.append("register_for_event")
            option_num += 1

        if auth.check_permission('manage_events') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Create Event")
            options.append("create_event")
            option_num += 1

            print(f"{option_num}. Update Event")
            options.append("update_event")
            option_num += 1

            print(f"{option_num}. Delete Event")
            options.append("delete_event")
            option_num += 1

        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        if choice == str(option_num):
            return

        try:
            choice_index = int(choice) - 1
        except ValueError:
            print("Invalid choice. Please try again.")
            continue

        if not (0 <= choice_index < len(options)):
            print("Invalid choice. Please try again.")
            continue

        selected = options[choice_index]
        if selected == "view_events":
            view_events()
        elif selected == "view_my_events":
            view_my_events()
        elif selected == "register_for_event":
            register_for_event()
        elif selected == "create_event":
            create_event()
        elif selected == "update_event":
            update_event()
        elif selected == "delete_event":
            delete_event()

def display_facility_menu():
    """Display the facility management menu"""
    global auth

    while True:
        print("\nFacilities")
        print("==========")

        # Built as a list. The old version hard-coded the numbers and then tried
        # to patch them up, so with some permission combinations "Approve" sat on
        # the same number as another option.
        options = [("View Available Facilities", view_facilities)]

        if auth.check_permission('request_facility_booking'):
            options.append(("Request Facility Booking", request_facility_booking))
            options.append(("View My Bookings", view_my_bookings))

        if auth.check_permission('approve_facility_bookings') or auth.check_permission('manage_facilities'):
            options.append(("Approve Facility Bookings", approve_facility_bookings))

        for index, (label, _action) in enumerate(options, 1):
            print(f"{index}. {label}")
        back = len(options) + 1
        print(f"{back}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == str(back):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print("Invalid choice. Please try again.")

def display_election_menu():
    """Display the election menu"""
    global auth

    while True:
        print("\nElections")
        print("=========")

        # Built as a list so the numbering stays correct whatever the signed-in
        # user is allowed to do.
        options = [
            ("View Current & Upcoming Elections", view_elections),
            ("View Election Results", view_election_results),
        ]

        if auth.check_permission('vote_in_elections'):
            options.append(("Vote in Active Election", vote_in_election))
            options.append(("Submit Nomination for Election", nominate_for_election))

        if auth.check_permission('manage_elections') or auth.check_permission('manage_union'):
            options.append(("Create Election", create_election))
            options.append(("Update Election", update_election))
            options.append(("Delete Election", delete_election))

        for index, (label, _action) in enumerate(options, 1):
            print(f"{index}. {label}")
        back = len(options) + 1
        print(f"{back}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == str(back):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print("Invalid choice. Please try again.")

def display_admin_menu():
    """Display the admin menu for student union"""
    global auth

    if not auth.check_permission('manage_all_clubs') and not auth.check_permission('approve_facility_bookings') and \
       not auth.check_permission('set_up_elections') and not auth.check_permission('manage_union_reps'):
        print("You don't have permission to access the admin menu.")
        return

    while True:
        print("\nStudent Union Administration")
        print("===========================")

        option_num = 1
        options = []

        if auth.check_permission('set_up_elections'):
            print(f"{option_num}. Set Up New Election")
            options.append("setup_election")
            option_num += 1

        if auth.check_permission('manage_union_reps'):
            print(f"{option_num}. Manage Union Representatives")
            options.append("manage_reps")
            option_num += 1

        if auth.check_permission('approve_facility_bookings'):
            print(f"{option_num}. Manage Facility Bookings")
            options.append("manage_bookings")
            option_num += 1

        if auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage All Clubs")
            options.append("manage_all_clubs")
            option_num += 1

        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        try:
            choice_index = int(choice) - 1

            if choice == str(option_num):
                # Return to Student Union Menu
                return
            elif 0 <= choice_index < len(options):
                selected_option = options[choice_index]

                if selected_option == "setup_election":
                    # Call the imported function without cursor/conn arguments
                    conn = get_connection()
                    cursor = conn.cursor()
                    try:
                        set_up_election(cursor, conn)
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            logger.debug("Suppressed exception", exc_info=True)
                elif selected_option == "manage_reps":
                    # Manage Representatives
                    manage_union_reps()
                elif selected_option == "manage_bookings":
                    # Manage Bookings
                    approve_facility_bookings()
                elif selected_option == "manage_all_clubs":
                    # Manage All Clubs
                    manage_club()  # The manage_club function will show all clubs for admins
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")
        except TypeError as e:
            print(f"Error calling function: {e}")
            print("This function may need to be updated to work with the current system.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Please contact an administrator if this problem persists.")
