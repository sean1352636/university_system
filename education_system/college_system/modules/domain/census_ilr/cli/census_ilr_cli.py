"""Census / ILR Returns CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.census_ilr.services.census_ilr_service import CensusILRService
from education_system.college_system.infrastructure.auth.core import UserAuth


def census_ilr_menu(auth: UserAuth):
    """Census / ILR Returns management menu."""
    svc = CensusILRService(auth._db_path)

    while True:
        print_header("Census / ILR Returns")
        options = [
            ("1", "List Returns"),
            ("2", "Create New Return"),
            ("3", "View Return Details"),
            ("4", "Generate Census Data"),
            ("5", "Generate ILR Data"),
            ("6", "Validate Return"),
            ("7", "Export Census XML"),
            ("8", "Export ILR XML"),
            ("9", "Submit Return"),
            ("10", "Return Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_returns(svc)
        elif choice == "2":
            _create_return(svc)
        elif choice == "3":
            _view_return(svc)
        elif choice == "4":
            _generate_census(svc)
        elif choice == "5":
            _generate_ilr(svc)
        elif choice == "6":
            _validate_return(svc)
        elif choice == "7":
            _export_census_xml(svc)
        elif choice == "8":
            _export_ilr_xml(svc)
        elif choice == "9":
            _submit_return(svc)
        elif choice == "10":
            _return_stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_returns(svc):
    print_header("All Returns")
    try:
        rt = input("  Filter by type (census/ilr/hesa, blank=all): ").strip() or None
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        returns = svc.list_returns(return_type=rt, academic_year=ay)
        if not returns:
            print("\n  No returns found.")
            return
        print(f"\n  {'ID':<5} {'Type':<8} {'Year':<12} {'Term':<10} {'Period':<12} {'Records':<8} {'Status':<12} {'Deadline'}")
        print(f"  {'-'*85}")
        for r in returns:
            print(f"  {r['id']:<5} {r['return_type']:<8} {(r.get('academic_year') or '-'):<12} "
                  f"{(r.get('term') or '-'):<10} {(r.get('collection_period') or '-'):<12} "
                  f"{r.get('record_count', 0):<8} {(r.get('status') or '-'):<12} "
                  f"{(r.get('submission_deadline') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_return(svc):
    print_header("Create New Return")
    try:
        rt = input("  Return type (census/ilr/hesa): ").strip()
        ay = input("  Academic year: ").strip()
        term = input("  Term: ").strip()
        cp = input("  Collection period: ").strip()
        dl = input("  Submission deadline (YYYY-MM-DD): ").strip()
        result = svc.create_return(rt, ay, term, cp, dl)
        print(f"\n  Return created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_return(svc):
    print_header("Return Details")
    try:
        rid = int(input("  Return ID: ").strip())
        r = svc.get_return(rid)
        print(f"\n  ID:                  {r['id']}")
        print(f"  Type:                {r['return_type']}")
        print(f"  Academic Year:       {r.get('academic_year', '-')}")
        print(f"  Term:                {r.get('term', '-')}")
        print(f"  Collection Period:   {r.get('collection_period', '-')}")
        print(f"  Deadline:            {r.get('submission_deadline', '-')}")
        print(f"  Status:              {r.get('status', '-')}")
        print(f"  Record Count:        {r.get('record_count', 0)}")
        print(f"  Submitted By:        {r.get('submitted_by') or '-'}")
        print(f"  Submitted At:        {r.get('submitted_at') or '-'}")
        print(f"  Created:             {r.get('created_at', '-')}")
        print(f"  Updated:             {r.get('updated_at', '-')}")
        if r.get('validation_errors'):
            print(f"\n  Validation Errors:")
            for line in r['validation_errors'].split('\n')[:10]:
                print(f"    - {line}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_census(svc):
    print_header("Generate Census Data")
    try:
        rid = int(input("  Return ID: ").strip())
        count = svc.generate_census_data(rid)
        print(f"\n  Generated {count} census student records.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_ilr(svc):
    print_header("Generate ILR Data")
    try:
        rid = int(input("  Return ID: ").strip())
        count = svc.generate_ilr_data(rid)
        print(f"\n  Generated {count} ILR learning aim records.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _validate_return(svc):
    print_header("Validate Return")
    try:
        rid = int(input("  Return ID: ").strip())
        errors = svc.validate_return(rid)
        print(f"\n  Validation complete: {len(errors)} error(s) found.")
        if errors:
            print(f"\n  First {min(len(errors), 10)} errors:")
            for e in errors[:10]:
                print(f"    - {e}")
            if len(errors) > 10:
                print(f"    ... and {len(errors) - 10} more.")
        else:
            print("  Return is valid.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _export_census_xml(svc):
    print_header("Export Census XML")
    try:
        rid = int(input("  Return ID: ").strip())
        xml = svc.export_census_xml(rid)
        print(f"\n  Census XML generated ({len(xml)} chars).")
        preview = xml[:200]
        print(f"\n  Preview:\n  {preview}...")
    except Exception as e:
        print(f"\n  Error: {e}")


def _export_ilr_xml(svc):
    print_header("Export ILR XML")
    try:
        rid = int(input("  Return ID: ").strip())
        xml = svc.export_ilr_xml(rid)
        print(f"\n  ILR XML generated ({len(xml)} chars).")
        preview = xml[:200]
        print(f"\n  Preview:\n  {preview}...")
    except Exception as e:
        print(f"\n  Error: {e}")


def _submit_return(svc):
    print_header("Submit Return")
    try:
        rid = int(input("  Return ID: ").strip())
        submitted_by = input("  Submitted by (user ID): ").strip()
        submitted_by = int(submitted_by) if submitted_by else None
        svc.submit_return(rid, submitted_by)
        print(f"\n  Return {rid} submitted successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _return_stats(svc):
    print_header("Return Statistics")
    try:
        rid = int(input("  Return ID: ").strip())
        stats = svc.get_return_stats(rid)
        print(f"\n  Return ID:       {stats['return_id']}")
        print(f"  Type:            {stats['return_type']}")
        print(f"  Status:          {stats['status']}")
        print(f"  Total Records:   {stats.get('total_records', 0)}")
        print(f"  Valid Records:   {stats.get('valid_records', 0)}")
        print(f"  Invalid Records: {stats.get('invalid_records', 0)}")
    except Exception as e:
        print(f"\n  Error: {e}")
