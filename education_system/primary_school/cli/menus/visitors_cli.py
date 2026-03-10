"""Visitors CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def visitors_menu(auth):
    """Visitors menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService

    svc = VisitorService(get_db_path())

    while True:
        print_header("Visitors")
        print_menu([("1", "List visitors"), ("2", "Sign in"), ("3", "Sign out"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.list_visitors() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            name = input("  Name: ").strip()
            purpose = input("  Purpose: ").strip()
            date = input("  Date: ").strip()
            try:
                svc.sign_in_visitor(name=name, purpose=purpose, date=date)
                print("\n  Signed in.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pk = input("  Visitor ID: ").strip()
            try:
                svc.sign_out_visitor(int(pk))
                print("\n  Signed out.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
