"""Notifications CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def notifications_menu(auth):
    """Notifications management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.notifications.services.notification_service import NotificationService

    svc = NotificationService(get_db_path())

    while True:
        print_header("Notifications")
        print_menu([
            ("1", "List notifications"),
            ("2", "View details"),
            ("3", "Add Notification"),
            ("4", "Update Notification"),
            ("5", "Delete Notification"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_notifications()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_notification(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            user_id = input("  User Id: ").strip()
            title = input("  Title: ").strip()
            message = input("  Message: ").strip()
            try:
                svc.create_notification(user_id=user_id, title=title, message=message)
                print("\n  Notification created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            user_id = input("  User Id: ").strip()
            title = input("  Title: ").strip()
            message = input("  Message: ").strip()
            try:
                svc.update_notification(int(pk), user_id=user_id, title=title, message=message)
                print("\n  Notification updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_notification(int(pk))
                print("\n  Notification deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
