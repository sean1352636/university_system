"""Data Export CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def data_export_menu(auth):
    """Data Export menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.data_export.services.data_export_service import DataExportService

    svc = DataExportService(get_db_path())

    while True:
        print_header("Data Export")
        print_menu([("1", "Export pupils"), ("2", "Export staff"), ("3", "Export attendance"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice in ("1", "2", "3"):
            t = {"1": "pupils", "2": "staff", "3": "attendance"}[choice]
            try:
                result = svc.export_data(t)
                print(f"\n  Done: {result}")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
