"""
Plagiarism detection system - backwards-compatible entry point.

This module re-exports all public symbols from the split submodules
so that existing imports continue to work unchanged.
"""
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.utils.logging.log_config import configure_logging

# Re-export the logger that external consumers import
logger = configure_logging(name=__name__)

# --- Core exports (used by tests, GUI, etc.) ---
from education_system.university_system.modules.domain.academics.services.plagiarism.exceptions import (
    PlagiarismCheckerError,
    DatabaseError,
    FileProcessingError,
    IntegrationError,
)
from education_system.university_system.modules.domain.academics.services.plagiarism.nlp import download_nltk_data, NLTK_AVAILABLE, TEXTRACT_AVAILABLE
from education_system.university_system.modules.domain.academics.services.plagiarism.db import get_safe_db_connection
from education_system.university_system.modules.domain.academics.services.plagiarism.checker import PlagiarismChecker

# --- CLI functions ---
from education_system.university_system.modules.domain.academics.services.plagiarism.cli import (
    safe_input,
    display_plagiarism_checker_menu,
    submit_document,
    view_my_documents,
    check_document,
    get_module_selection,
    view_results,
    search_repository,
    get_author_selection,
    get_module_selection_by_name,
    view_statistics,
    manage_repository,
    delete_document_interactive,
    check_repository_integrity,
    display_document_details,
    display_result_details,
    display_check_result,
)

# --- Setup & testing ---
from education_system.university_system.modules.domain.academics.services.plagiarism.setup import (
    check_requirements,
    check_database,
    create_directories,
    setup_plagiarism_system,
)
from education_system.university_system.modules.domain.academics.services.plagiarism.sample_data import (
    create_sample_documents,
    create_ai_education_content,
    create_similar_ai_content,
    create_different_content,
)
from education_system.university_system.modules.domain.academics.services.plagiarism.tests import (
    test_document_repository,
    test_document_submission,
    test_plagiarism_check,
    test_error_handling,
    test_edge_cases,
    test_plagiarism_checker,
)


def main():
    """Main function to demonstrate the plagiarism system"""
    print("Unified Plagiarism Detection System")
    print("==================================")
    print("1. Setup System")
    print("2. Test System")
    print("3. Run Interactive Demo")
    print("4. Exit")

    while True:
        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            try:
                if setup_plagiarism_system():
                    print("\nSetup completed successfully!")
                else:
                    print("\nSetup failed. Please check the errors above.")
            except KeyboardInterrupt:
                print("\nSetup cancelled by user.")
            except Exception as e:
                print(f"\nSetup failed with error: {e}")

        elif choice == '2':
            try:
                if test_plagiarism_checker():
                    print("\n\u2713 All tests completed successfully!")
                else:
                    print("\n\u2717 Some tests failed.")
            except KeyboardInterrupt:
                print("\nTesting cancelled by user.")
            except Exception as e:
                print(f"\nTesting failed with error: {e}")

        elif choice == '3':
            try:
                # Create UserAuth for demo
                auth = get_auth()
                if auth is None:
                    auth = UserAuth()
                with get_safe_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT username FROM users LIMIT 1')
                    user_data = cursor.fetchone()
                    if user_data:
                        auth.current_user = {'username': user_data[0]}
                        display_plagiarism_checker_menu(auth)
                    else:
                        print("Cannot run demo: No user accounts found in database.")
                        print("Please set up the main system first.")
            except KeyboardInterrupt:
                print("\nDemo cancelled by user.")
            except Exception as e:
                print(f"\nDemo failed with error: {e}")

        elif choice == '4':
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except Exception as e:
        print(f"\nProgram failed with error: {e}")
    finally:
        input("\nPress Enter to exit...")
