from education_system.university_system.modules.domain.academics.services.plagiarism.checker import PlagiarismChecker
from education_system.university_system.modules.domain.academics.services.plagiarism.cli.submission import submit_document, view_my_documents
from education_system.university_system.modules.domain.academics.services.plagiarism.cli.checking import check_document, view_results
from education_system.university_system.modules.domain.academics.services.plagiarism.cli.search import search_repository
from education_system.university_system.modules.domain.academics.services.plagiarism.cli.reporting import view_statistics
from education_system.university_system.modules.domain.academics.services.plagiarism.cli.admin import manage_repository


def safe_input(prompt, default=None, validator=None):
    """Safe input function with validation"""
    while True:
        try:
            value = input(prompt).strip()
            if not value and default is not None:
                return default
            if validator:
                if validator(value):
                    return value
                else:
                    print("Invalid input. Please try again.")
                    continue
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"Input error: {e}")
            continue


def display_plagiarism_checker_menu(auth):
    """Display the plagiarism checker menu and handle user choices"""
    if not auth or not auth.current_user:
        print("You must be logged in to access the Plagiarism Checker.")
        return

    # Check for appropriate permissions
    has_check_permission = auth.check_permission('check_plagiarism')
    has_manage_permission = auth.check_permission('manage_plagiarism_system')
    has_submit_permission = auth.check_permission('submit_document')

    if not (has_check_permission or has_manage_permission or has_submit_permission):
        print("You don't have permission to access the Plagiarism Checker.")
        return

    # Initialize the plagiarism checker
    try:
        checker = PlagiarismChecker()
    except Exception as e:
        print(f"Error initializing plagiarism checker: {e}")
        print("Please ensure the database is properly set up.")
        return

    while True:
        try:
            print("\nPlagiarism Checker Menu:")
            print("=========================")

            # Options based on permissions
            options = []
            option_num = 1

            if has_submit_permission:
                print(f"{option_num}. Submit Document")
                options.append("submit_document")
                option_num += 1

                print(f"{option_num}. View My Documents")
                options.append("view_my_documents")
                option_num += 1

            if has_check_permission:
                print(f"{option_num}. Check Document for Plagiarism")
                options.append("check_document")
                option_num += 1

                print(f"{option_num}. View Plagiarism Check Results")
                options.append("view_results")
                option_num += 1

                print(f"{option_num}. Search Document Repository")
                options.append("search_repository")
                option_num += 1

            if has_manage_permission:
                print(f"{option_num}. System Statistics")
                options.append("view_statistics")
                option_num += 1

                print(f"{option_num}. Manage Document Repository")
                options.append("manage_repository")
                option_num += 1

            print(f"{option_num}. Return to Main Menu")

            choice = safe_input("\nEnter your choice: ")
            if choice is None:  # User cancelled
                return

            try:
                choice_num = int(choice)

                if choice_num > 0 and choice_num <= len(options):
                    action = options[choice_num - 1]

                    if action == "submit_document":
                        submit_document(checker, auth)
                    elif action == "view_my_documents":
                        view_my_documents(checker, auth)
                    elif action == "check_document":
                        check_document(checker, auth)
                    elif action == "view_results":
                        view_results(checker, auth)
                    elif action == "search_repository":
                        search_repository(checker, auth)
                    elif action == "view_statistics":
                        view_statistics(checker, auth)
                    elif action == "manage_repository":
                        manage_repository(checker, auth)
                elif choice_num == option_num:
                    return
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled. Returning to main menu.")
            return
        except Exception as e:
            print(f"Unexpected error in menu: {e}")
