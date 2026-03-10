import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.clubs import (
    view_clubs, manage_club, create_club,
)
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.membership import (
    join_club, view_my_clubs,
)


def display_club_menu():
    """Display the club management menu"""
    auth = _state.auth

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
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")
