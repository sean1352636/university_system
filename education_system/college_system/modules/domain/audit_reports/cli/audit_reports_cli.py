"""CLI interface for audit & compliance reports management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.audit_reports.services.audit_reports_service import AuditReportService
from education_system.college_system.infrastructure.auth.core import UserAuth


def audit_reports_menu(auth: UserAuth):
    """Audit & Compliance Reports management menu."""
    service = AuditReportService(auth._db_path)

    while True:
        print_header("Audit & Compliance Reports")
        options = [
            ("1", "List Reports"),
            ("2", "Add Report"),
            ("3", "View Report"),
            ("4", "Update Report"),
            ("5", "Delete Report"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_reports(service)
        elif choice == "2":
            _add_report(service)
        elif choice == "3":
            _view_report(service)
        elif choice == "4":
            _update_report(service)
        elif choice == "5":
            _delete_report(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_reports(service):
    print_header("List Reports")
    try:
        items = service.list_reports()
        if not items:
            print("\n  No reports found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Type':<15}" + f"{'Title':<25}" + f"{'By':<10}" + f"{'Summary':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('report_type', '') or '')[:20].ljust(15) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('generated_by', '') or '')[:20].ljust(10) + str(item.get('result_summary', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} reports")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_report(service):
    print_header("Add Report")
    try:
        data = {}
        for field in ['report_type', 'title', 'generated_by', 'result_summary', 'findings']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_report(**data)
        print(f"\n  Report created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_report(service):
    print_header("View Report")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_report(pk)
        if not item:
            print("\n  Report not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_report(service):
    print_header("Update Report")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_report(pk)
        if not item:
            print("\n  Report not found.")
            return
        data = {}
        for field in ['report_type', 'title', 'generated_by', 'result_summary', 'findings']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_report(pk, **data)
            print(f"\n  Report updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_report(service):
    print_header("Delete Report")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete report {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_report(pk)
            print(f"\n  Report deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
