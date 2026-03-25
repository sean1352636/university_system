"""UCAS Data Export CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.ucas_export.services.ucas_export_service import UCASExportService
from education_system.college_system.infrastructure.auth.core import UserAuth


def ucas_export_menu(auth: UserAuth):
    """UCAS Data Export management menu."""
    svc = UCASExportService(auth._db_path)

    while True:
        print_header("UCAS Data Export")
        options = [
            ("1", "List Export Batches"),
            ("2", "Create New Batch"),
            ("3", "Generate Export Data"),
            ("4", "Validate Batch"),
            ("5", "Generate XML"),
            ("6", "Mark Batch as Exported"),
            ("7", "Batch Statistics"),
            ("8", "Student Export Status"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_batches(svc)
        elif choice == "2":
            _create_batch(svc)
        elif choice == "3":
            _generate_data(svc)
        elif choice == "4":
            _validate_batch(svc)
        elif choice == "5":
            _generate_xml(svc)
        elif choice == "6":
            _mark_exported(svc)
        elif choice == "7":
            _batch_stats(svc)
        elif choice == "8":
            _student_status(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_batches(svc):
    print_header("Export Batches")
    try:
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        batches = svc.list_batches(academic_year=ay)
        if not batches:
            print("\n  No export batches found.")
            return
        print(f"\n  {'ID':<5} {'Year':<12} {'Type':<16} {'Records':<8} {'Status':<12} {'Date'}")
        print(f"  {'-'*70}")
        for b in batches:
            print(f"  {b['id']:<5} {(b.get('academic_year') or '-'):<12} "
                  f"{(b.get('export_type') or '-'):<16} {b.get('record_count', 0):<8} "
                  f"{(b.get('status') or '-'):<12} {(b.get('export_date') or b.get('created_at', '-'))}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_batch(svc):
    print_header("Create New Batch")
    try:
        ay = input("  Academic year: ").strip()
        et = input("  Export type (applications/references/predictions): ").strip()
        result = svc.create_batch(ay, et)
        print(f"\n  Batch created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_data(svc):
    print_header("Generate Export Data")
    try:
        bid = int(input("  Batch ID: ").strip())
        count = svc.generate_export_data(bid)
        print(f"\n  Generated {count} export records.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _validate_batch(svc):
    print_header("Validate Batch")
    try:
        bid = int(input("  Batch ID: ").strip())
        errors = svc.validate_batch(bid)
        print(f"\n  Validation complete: {len(errors)} error(s) found.")
        if errors:
            print(f"\n  First {min(len(errors), 10)} errors:")
            for e in errors[:10]:
                print(f"    - {e}")
            if len(errors) > 10:
                print(f"    ... and {len(errors) - 10} more.")
        else:
            print("  Batch is valid.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_xml(svc):
    print_header("Generate XML")
    try:
        bid = int(input("  Batch ID: ").strip())
        xml = svc.generate_xml(bid)
        print(f"\n  XML generated ({len(xml)} chars).")
        preview = xml[:200]
        print(f"\n  Preview:\n  {preview}...")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_exported(svc):
    print_header("Mark Batch as Exported")
    try:
        bid = int(input("  Batch ID: ").strip())
        exported_by = input("  Exported by (user ID): ").strip()
        exported_by = int(exported_by) if exported_by else None
        svc.mark_exported(bid, exported_by)
        print(f"\n  Batch {bid} marked as exported.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _batch_stats(svc):
    print_header("Batch Statistics")
    try:
        bid = int(input("  Batch ID: ").strip())
        stats = svc.get_batch_stats(bid)
        print(f"\n  Batch ID:       {stats['batch_id']}")
        print(f"  Export Type:    {stats['export_type']}")
        print(f"  Status:         {stats['status']}")
        print(f"  Total Records:  {stats['total_records']}")
        print(f"  Pending:        {stats['pending']}")
        print(f"  Included:       {stats['included']}")
        print(f"  Excluded:       {stats['excluded']}")
        print(f"  Errors:         {stats['error']}")
        print(f"  Exported:       {stats['exported']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _student_status(svc):
    print_header("Student Export Status")
    try:
        sid = int(input("  Student ID: ").strip())
        records = svc.get_student_export_status(sid)
        if not records:
            print(f"\n  No export records found for student {sid}.")
            return
        print(f"\n  {'ID':<5} {'Year':<12} {'Type':<16} {'Status':<12} {'Batch':<8} {'Errors'}")
        print(f"  {'-'*70}")
        for r in records:
            print(f"  {r['id']:<5} {(r.get('academic_year') or '-'):<12} "
                  f"{(r.get('export_type') or '-'):<16} {(r.get('export_status') or '-'):<12} "
                  f"{(r.get('batch_status') or '-'):<8} {(r.get('error_notes') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")
