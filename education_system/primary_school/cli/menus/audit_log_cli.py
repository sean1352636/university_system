"""Audit Log CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def audit_log_menu(auth):
    """Audit Log menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.audit_log.services.audit_service import AuditService

    svc = AuditService(get_db_path())

    while True:
        print_header("Audit Log")
        print_menu([("1", "View recent entries"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.get_logs(limit=20) or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        else:
            print("\n  Invalid option.")
