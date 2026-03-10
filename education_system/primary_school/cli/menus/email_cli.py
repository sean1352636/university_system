"""Email CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def email_menu(auth):
    """Email menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.email.services.email_service import EmailService

    svc = EmailService(get_db_path())

    while True:
        print_header("Email")
        print_menu([("1", "List emails"), ("2", "Send email"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.list_emails() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            recipient = input("  Recipient: ").strip()
            subject = input("  Subject: ").strip()
            body = input("  Body: ").strip()
            try:
                svc.send_email(recipient=recipient, subject=subject, body=body)
                print("\n  Sent.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
