"""User Management CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def user_management_menu(auth):
    """User Management management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.users.services.user_service import UserService

    svc = UserService(get_db_path())

    while True:
        print_header("User Management")
        print_menu([
            ("1", "List users"),
            ("2", "View details"),
            ("3", "Add User"),
            ("4", "Update User"),
            ("5", "Delete User"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_users()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_user(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            username = input("  Username: ").strip()
            password = input("  Password: ").strip()
            role = input("  Role: ").strip()
            try:
                svc.create_user(username=username, password=password, role=role)
                print("\n  User created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            username = input("  Username: ").strip()
            password = input("  Password: ").strip()
            role = input("  Role: ").strip()
            try:
                svc.update_user(int(pk), username=username, password=password, role=role)
                print("\n  User updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_user(int(pk))
                print("\n  User deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
