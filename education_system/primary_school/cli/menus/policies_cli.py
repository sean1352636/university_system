"""Policies CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def policies_menu(auth):
    """Policies management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.policies.services.policy_service import PolicyService

    svc = PolicyService(get_db_path())

    while True:
        print_header("Policies")
        print_menu([
            ("1", "List policies"),
            ("2", "View details"),
            ("3", "Add Policy"),
            ("4", "Update Policy"),
            ("5", "Delete Policy"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_policies()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_policy(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            title = input("  Title: ").strip()
            content = input("  Content: ").strip()
            try:
                svc.create_policy(title=title, content=content)
                print("\n  Policy created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            title = input("  Title: ").strip()
            content = input("  Content: ").strip()
            try:
                svc.update_policy(int(pk), title=title, content=content)
                print("\n  Policy updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_policy(int(pk))
                print("\n  Policy deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
