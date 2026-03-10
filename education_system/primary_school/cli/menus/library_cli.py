"""Library CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def library_menu(auth):
    """Library menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pupil_life.library.services.library_service import LibraryService

    svc = LibraryService(get_db_path())

    while True:
        print_header("Library")
        print_menu([("1", "List books"), ("2", "Add book"), ("3", "List loans"), ("4", "Create loan"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.list_books() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            title = input("  Title: ").strip()
            author = input("  Author: ").strip()
            try:
                svc.add_book(title=title, author=author)
                print("\n  Added.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            for item in (svc.list_loans() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "4":
            book_id = input("  Book ID: ").strip()
            pupil_id = input("  Pupil ID: ").strip()
            try:
                svc.create_loan(book_id=int(book_id), pupil_id=pupil_id)
                print("\n  Created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
