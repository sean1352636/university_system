"""Data Export & ILR CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.data_export.services.data_export_service import DataExportService
from education_system.college_system.infrastructure.auth.core import UserAuth


def data_export_menu(auth: UserAuth):
    """Data Export & ILR management menu."""
    svc = DataExportService(auth._db_path)

    while True:
        print_header("Data Export & ILR")
        options = [
            ("1", "List Jobs"),
            ("2", "View Job"),
            ("3", "New Job"),
            ("4", "Start Job"),
            ("5", "Complete Job"),
            ("6", "Delete Job"),
            ("7", "List Templates"),
            ("8", "New Template"),
            ("9", "Update Template"),
            ("10", "Toggle Active"),
            ("11", "Delete Template"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()

        if choice == "0":
            break

        elif choice == "1":
            # List Jobs
            etype = input("  Export type (or Enter for all): ").strip() or None
            status = input("  Status (pending/running/completed/failed or Enter for all): ").strip() or None
            year = input("  Academic year (or Enter for all): ").strip() or None
            try:
                jobs = svc.list_jobs(export_type=etype, status=status,
                                     academic_year=year)
                if not jobs:
                    print("\n  No export jobs found.")
                for j in jobs:
                    print(f"  [{j['id']}] {j.get('export_type', '')} | "
                          f"{j.get('academic_year', '') or ''} | "
                          f"{j.get('description', '') or ''} | "
                          f"Records: {j.get('record_count', 0)} | "
                          f"Errors: {j.get('validation_errors', 0)} | "
                          f"[{j.get('status', '')}]")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "2":
            # View Job
            try:
                jid = int(input("  Job ID: ").strip())
                j = svc.get_job(jid)
                if not j:
                    print("\n  Job not found.")
                    continue
                print(f"\n  ID:                {j['id']}")
                print(f"  Export Type:       {j.get('export_type', '')}")
                print(f"  Academic Year:     {j.get('academic_year', '') or ''}")
                print(f"  Description:       {j.get('description', '') or ''}")
                print(f"  Status:            {j.get('status', '')}")
                print(f"  Record Count:      {j.get('record_count', 0)}")
                print(f"  Errors:            {j.get('validation_errors', 0)}")
                print(f"  Warnings:          {j.get('validation_warnings', 0)}")
                print(f"  File Path:         {j.get('file_path', '') or ''}")
                print(f"  Started At:        {j.get('started_at', '') or ''}")
                print(f"  Completed At:      {j.get('completed_at', '') or ''}")
                print(f"  Created At:        {j.get('created_at', '') or ''}")
                if j.get("validation_log"):
                    print(f"  Validation Log:    {j['validation_log']}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            # New Job
            etype = input("  Export type (ILR/school_census/student_data/staff_data/finance/attendance/custom): ").strip()
            if not etype:
                print("\n  Export type is required.")
                continue
            year = input("  Academic year (or Enter to skip): ").strip() or None
            desc = input("  Description (or Enter to skip): ").strip() or None
            try:
                j = svc.create_job(export_type=etype, academic_year=year,
                                   description=desc)
                print(f"\n  Created export job #{j['id']}.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            # Start Job
            try:
                jid = int(input("  Job ID: ").strip())
                j = svc.start_job(jid)
                print(f"\n  Job #{j['id']} started at {j.get('started_at', '')}.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            # Complete Job
            try:
                jid = int(input("  Job ID: ").strip())
                record_count = int(input("  Record count: ").strip())
                file_path = input("  File path: ").strip()
                errors = int(input("  Validation errors (default 0): ").strip() or "0")
                warnings = int(input("  Validation warnings (default 0): ").strip() or "0")
                log = input("  Validation log (or Enter to skip): ").strip() or None
                j = svc.complete_job(jid, record_count=record_count,
                                     file_path=file_path, errors=errors,
                                     warnings=warnings, log=log)
                print(f"\n  Job #{j['id']} completed. "
                      f"Records: {j.get('record_count', 0)}, "
                      f"Errors: {j.get('validation_errors', 0)}.")
            except ValueError:
                print("\n  Invalid numeric input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            # Delete Job
            try:
                jid = int(input("  Job ID: ").strip())
                confirm = input(f"  Delete job #{jid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_job(jid)
                    print(f"\n  Job #{jid} deleted.")
                else:
                    print("\n  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            # List Templates
            etype = input("  Export type (or Enter for all): ").strip() or None
            try:
                templates = svc.list_templates(export_type=etype)
                if not templates:
                    print("\n  No templates found.")
                for t in templates:
                    active = "Active" if t.get("is_active") else "Inactive"
                    print(f"  [{t['id']}] {t.get('template_name', '')} | "
                          f"{t.get('export_type', '')} | [{active}]")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            # New Template
            name = input("  Template name: ").strip()
            if not name:
                print("\n  Name is required.")
                continue
            etype = input("  Export type: ").strip()
            if not etype:
                print("\n  Export type is required.")
                continue
            field_mapping = input("  Field mapping (JSON or Enter to skip): ").strip() or None
            filters = input("  Filters (JSON or Enter to skip): ").strip() or None
            try:
                t = svc.create_template(template_name=name, export_type=etype,
                                        field_mapping=field_mapping,
                                        filters=filters)
                print(f"\n  Created template #{t['id']}.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            # Update Template
            try:
                tid = int(input("  Template ID: ").strip())
                t = svc.get_template(tid)
                if not t:
                    print("\n  Template not found.")
                    continue
                name = input(f"  Name [{t.get('template_name', '')}]: ").strip() or None
                etype = input(f"  Export type [{t.get('export_type', '')}]: ").strip() or None
                field_mapping = input("  Field mapping (JSON or Enter to keep): ").strip() or None
                filters = input("  Filters (JSON or Enter to keep): ").strip() or None
                updates = {}
                if name:
                    updates["template_name"] = name
                if etype:
                    updates["export_type"] = etype
                if field_mapping:
                    updates["field_mapping"] = field_mapping
                if filters:
                    updates["filters"] = filters
                if not updates:
                    print("\n  No changes provided.")
                    continue
                t = svc.update_template(tid, **updates)
                print(f"\n  Template #{t['id']} updated.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            # Toggle Active
            try:
                tid = int(input("  Template ID: ").strip())
                t = svc.toggle_active(tid)
                state = "active" if t.get("is_active") else "inactive"
                print(f"\n  Template #{t['id']} is now {state}.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            # Delete Template
            try:
                tid = int(input("  Template ID: ").strip())
                confirm = input(f"  Delete template #{tid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_template(tid)
                    print(f"\n  Template #{tid} deleted.")
                else:
                    print("\n  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            # Statistics
            try:
                stats = svc.get_stats()
                print(f"\n  Total Export Jobs:     {stats['total_jobs']}")
                print("  Jobs by Status:")
                for s, c in stats.get("by_status", {}).items():
                    print(f"    {s:<16} {c}")
                print("  Jobs by Type:")
                for t, c in stats.get("by_type", {}).items():
                    print(f"    {t:<16} {c}")
                print(f"  Total Templates:      {stats['total_templates']}")
                print(f"  Active Templates:     {stats['active_templates']}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
