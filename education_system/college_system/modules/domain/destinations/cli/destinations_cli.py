"""Destinations & NEET CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService
from education_system.college_system.infrastructure.auth.core import UserAuth


def destinations_menu(auth: UserAuth):
    """Destinations & NEET management menu."""
    svc = DestinationService(auth._db_path)

    while True:
        print_header("Destinations & NEET")
        options = [
            ("1", "All Destinations"),
            ("2", "New Destination"),
            ("3", "Update Destination"),
            ("4", "Confirm Destination"),
            ("5", "NEET Risk Students"),
            ("6", "Calculate NEET Risk"),
            ("7", "Record Contact"),
            ("8", "Pending Follow-ups"),
            ("9", "Destination Stats"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_destinations(svc)
        elif choice == "2":
            _new_destination(svc)
        elif choice == "3":
            _update_destination(svc)
        elif choice == "4":
            _confirm_destination(svc)
        elif choice == "5":
            _neet_risk(svc)
        elif choice == "6":
            _calculate_risk(svc)
        elif choice == "7":
            _record_contact(svc)
        elif choice == "8":
            _pending_followups(svc)
        elif choice == "9":
            _stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_destinations(svc):
    print_header("All Destinations")
    try:
        dests = svc.list_destinations()
        if not dests:
            print("\n  No destinations found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Type':<18} {'Confirmed':<20} {'NEET':<5} {'Contact'}")
        print(f"  {'-'*62}")
        for d in dests:
            neet = "Yes" if d["neet_risk"] else "-"
            contact = "Yes" if d["contact_made"] else "No"
            print(f"  {d['id']:<5} {d['student_id']:<8} {d['destination_type']:<18} "
                  f"{(d.get('confirmed_destination') or '-'):<20} {neet:<5} {contact}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_destination(svc):
    print_header("New Destination")
    try:
        student_id = int(input("  Student PK: ").strip())
        academic_year = input("  Academic Year: ").strip() or None
        intended = input("  Intended Destination: ").strip() or None
        dtype = input("  Type (university/apprenticeship/employment/further_education/gap_year/neet/unknown) [unknown]: ").strip() or "unknown"
        institution = input("  Institution Name: ").strip() or None
        course = input("  Course Title: ").strip() or None

        dest = svc.create_destination(student_id, academic_year, intended, dtype,
                                       institution, course)
        print(f"\n  Destination created (ID: {dest['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_destination(svc):
    print_header("Update Destination")
    try:
        dest_id = int(input("  Destination ID: ").strip())
        print("  (Leave blank to keep current)")
        dtype = input("  Type: ").strip() or None
        institution = input("  Institution: ").strip() or None
        notes = input("  Notes: ").strip() or None

        updates = {}
        if dtype:
            updates["destination_type"] = dtype
        if institution:
            updates["institution_name"] = institution
        if notes:
            updates["notes"] = notes

        dest = svc.update_destination(dest_id, **updates)
        print(f"\n  Destination {dest['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _confirm_destination(svc):
    try:
        dest_id = int(input("  Destination ID: ").strip())
        confirmed = input("  Confirmed Destination: ").strip()
        dtype = input("  Type (optional): ").strip() or None
        svc.confirm_destination(dest_id, confirmed, dtype)
        print("\n  Destination confirmed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _neet_risk(svc):
    print_header("NEET Risk Students")
    try:
        students = svc.get_neet_risk_students()
        if not students:
            print("\n  No students flagged as NEET risk.")
            return
        for s in students:
            print(f"  [{s['id']}] {s.get('sid', '-')} {s.get('first_name', '')} "
                  f"{s.get('last_name', '')} - {s['destination_type']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _calculate_risk(svc):
    try:
        student_id = int(input("  Student PK: ").strip())
        result = svc.calculate_neet_risk(student_id)
        print(f"\n  Risk Score: {result['risk_score']}/{result['max_score']}")
        print(f"  Risk Level: {result['risk_level']}")
        if result["reasons"]:
            print("  Reasons:")
            for r in result["reasons"]:
                print(f"    - {r}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_contact(svc):
    try:
        dest_id = int(input("  Destination ID: ").strip())
        svc.record_contact(dest_id)
        print("\n  Contact recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _pending_followups(svc):
    print_header("Pending Follow-ups")
    try:
        followups = svc.get_pending_followups()
        if not followups:
            print("\n  No pending follow-ups.")
            return
        for f in followups:
            print(f"  [{f['id']}] {f.get('sid', '-')} {f.get('first_name', '')} "
                  f"{f.get('last_name', '')} - {f['destination_type']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _stats(svc):
    print_header("Destination Statistics")
    try:
        stats = svc.get_destination_stats()
        print(f"\n  Total: {stats['total']}")
        print(f"  Confirmed: {stats['confirmed']}")
        print(f"  Unconfirmed: {stats['unconfirmed']}")
        print(f"  NEET Risk: {stats['neet_risk']}")
        if stats["by_type"]:
            print("\n  By Type:")
            for t in stats["by_type"]:
                print(f"    {t['destination_type']}: {t['count']}")
    except Exception as e:
        print(f"\n  Error: {e}")
