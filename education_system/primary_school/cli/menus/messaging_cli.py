"""Messaging CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def messaging_menu(auth):
    """Messaging management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.messaging.services.messaging_service import MessagingService

    svc = MessagingService(get_db_path())

    while True:
        print_header("Messaging")
        print_menu([
            ("1", "List records"),
            ("2", "View details"),
            ("3", "Add record"),
            ("4", "Update record"),
            ("5", "Delete record"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_all()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            sender_type = input("  Sender Type: ").strip()
            recipient_type = input("  Recipient Type: ").strip()
            subject = input("  Subject: ").strip()
            body = input("  Body: ").strip()
            try:
                svc.create(sender_type=sender_type, recipient_type=recipient_type, subject=subject, body=body)
                print("\n  Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            sender_type = input("  Sender Type: ").strip()
            recipient_type = input("  Recipient Type: ").strip()
            subject = input("  Subject: ").strip()
            body = input("  Body: ").strip()
            try:
                svc.update(int(pk), sender_type=sender_type, recipient_type=recipient_type, subject=subject, body=body)
                print("\n  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete(int(pk))
                print("\n  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
