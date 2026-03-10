"""Library CLI for managing library items and loans."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.library.services.library_service import LibraryService


def library_menu(auth: UserAuth):
    svc = LibraryService(auth._db_path)

    while True:
        print_header("Library")
        options = [
            ("1", "Search Catalogue"),
            ("2", "Add Item"),
            ("3", "Checkout"),
            ("4", "Return Item"),
            ("5", "Renew Loan"),
            ("6", "View Overdue"),
            ("7", "My Loans"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            search = input("  Search (title/author/ISBN): ").strip()
            items = svc.list_items(search=search if search else None)
            for i in items:
                print(f"  [{i['id']}] {i.get('title', '')} by {i.get('author', '')} - Available: {i.get('available_copies', 0)}/{i.get('total_copies', 0)}")
            if not items:
                print("  No items found.")
        elif choice == "2":
            try:
                title = input("  Title: ").strip()
                author = input("  Author: ").strip() or None
                isbn = input("  ISBN: ").strip() or None
                copies = input("  Copies (1): ").strip()
                i = svc.add_item(title, author=author, isbn=isbn, total_copies=int(copies) if copies else 1)
                print(f"\n  Item #{i['id']} added.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                iid = int(input("  Item ID: ").strip())
                bid = int(input("  Borrower ID: ").strip())
                l = svc.checkout(iid, bid)
                print(f"\n  Loan #{l['id']} - Due: {l.get('due_date', '')}")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                lid = int(input("  Loan ID: ").strip())
                svc.return_item(lid)
                print("  Item returned.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                lid = int(input("  Loan ID: ").strip())
                l = svc.renew_loan(lid)
                print(f"  Renewed. New due date: {l.get('due_date', '')}")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "6":
            overdue = svc.get_overdue()
            for o in overdue:
                print(f"  [{o['id']}] {o.get('title', '')} - Borrower: {o.get('borrower_id', '')} Due: {o.get('due_date', '')}")
            if not overdue:
                print("  No overdue items.")
        elif choice == "7":
            try:
                user_id = auth.current_user["user_id"]
                loans = svc.list_loans(borrower_id=user_id)
                for l in loans:
                    print(f"  [{l['id']}] {l.get('title', '')} Due: {l.get('due_date', '')} [{l.get('status', '')}]")
                if not loans:
                    print("  No loans found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
