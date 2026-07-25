"""Student Self-Service Portal — CLI module.

Text-based menu that mirrors the GUI functionality:
  1) View my journey
  2) View my records
  3) Submit record request
  4) View my requests
  5) [Admin] View pending requests
  6) [Admin] Resolve request
  0) Back
"""

from education_system.platform.delivery.portals.student.portal_service import (
    PortalService,
    REQUEST_TYPES,
)

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "university": "University",
}


def run(db_path=None, auth=None):
    """Entry point for the CLI portal menu."""
    auth = auth or {}
    username = auth.get("username", "")
    role = auth.get("role", "").lower()
    is_admin = role in ("admin", "superadmin", "staff")
    service = PortalService()

    while True:
        print("\n===== Student Self-Service Portal =====")
        print("1) View my journey")
        print("2) View my records")
        print("3) Submit record request")
        print("4) View my requests")
        if is_admin:
            print("5) [Admin] View pending requests")
            print("6) [Admin] Resolve request")
        print("0) Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            _view_journey(service, username)
        elif choice == "2":
            _view_records(service, username)
        elif choice == "3":
            _submit_request(service, username)
        elif choice == "4":
            _view_my_requests(service, username)
        elif choice == "5" and is_admin:
            _view_pending(service)
        elif choice == "6" and is_admin:
            _resolve_request(service, username)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def _view_journey(service, username):
    if not username:
        print("No user logged in.")
        return
    try:
        stages = service.get_my_journey(username)
    except Exception as exc:
        print(f"Error: {exc}")
        return

    if not stages:
        print("No journey data found for your account.")
        return

    for stage in stages:
        label = SYSTEM_LABELS.get(stage.get("system", ""), stage.get("system", ""))
        print(f"\n--- {label} ---")
        for key in ("student_id", "name", "year_group", "status", "enrolled_date"):
            val = stage.get(key, "")
            if val:
                print(f"  {key.replace('_', ' ').title()}: {val}")


def _view_records(service, username):
    if not username:
        print("No user logged in.")
        return

    print("\nSelect system:")
    systems = ["primary", "secondary", "sixth_form", "university"]
    for i, s in enumerate(systems, 1):
        print(f"  {i}) {SYSTEM_LABELS[s]}")
    sel = input("Choice: ").strip()
    try:
        system = systems[int(sel) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    try:
        records = service.get_my_records(username, system)
    except Exception as exc:
        print(f"Error: {exc}")
        return

    grades = records.get("grades", [])
    if grades:
        print(f"\n  Grades/Assessments ({len(grades)} record(s)):")
        for g in grades[:20]:
            parts = [f"{k}={v}" for k, v in g.items() if v is not None and str(v).strip()]
            print(f"    {', '.join(parts)}")
        if len(grades) > 20:
            print(f"    ... and {len(grades) - 20} more")
    else:
        print("\n  No grade records found.")

    att = records.get("attendance", {})
    if att:
        print("\n  Attendance Summary:")
        for k, v in att.items():
            print(f"    {k.replace('_', ' ').title()}: {v}")
    else:
        print("\n  No attendance data.")


def _submit_request(service, username):
    if not username:
        print("No user logged in.")
        return

    print("\nRequest types:")
    for i, rt in enumerate(REQUEST_TYPES, 1):
        print(f"  {i}) {rt}")
    sel = input("Type: ").strip()
    try:
        rtype = REQUEST_TYPES[int(sel) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    details = input("Details: ").strip()
    if not details:
        print("Details cannot be empty.")
        return

    try:
        rid = service.submit_record_request(username, rtype, details)
        print(f"Request #{rid} submitted successfully.")
    except Exception as exc:
        print(f"Error: {exc}")


def _view_my_requests(service, username):
    if not username:
        print("No user logged in.")
        return
    try:
        reqs = service.get_my_requests(username)
    except Exception as exc:
        print(f"Error: {exc}")
        return

    if not reqs:
        print("No requests found.")
        return

    print(f"\n{'ID':<5} {'Type':<14} {'Status':<10} {'Created':<20} {'Details'}")
    print("-" * 80)
    for r in reqs:
        print(
            f"{r.get('id',''):<5} {r.get('request_type',''):<14} "
            f"{r.get('status',''):<10} {r.get('created_at',''):<20} "
            f"{(r.get('details','') or '')[:40]}"
        )


def _view_pending(service):
    try:
        reqs = service.get_pending_requests()
    except Exception as exc:
        print(f"Error: {exc}")
        return

    if not reqs:
        print("No pending requests.")
        return

    print(f"\n{'ID':<5} {'User':<15} {'Type':<14} {'Created':<20} {'Details'}")
    print("-" * 80)
    for r in reqs:
        print(
            f"{r.get('id',''):<5} {r.get('username',''):<15} "
            f"{r.get('request_type',''):<14} {r.get('created_at',''):<20} "
            f"{(r.get('details','') or '')[:30]}"
        )


def _resolve_request(service, admin_username):
    rid = input("Request ID to resolve: ").strip()
    if not rid.isdigit():
        print("Invalid ID.")
        return
    try:
        service.resolve_request(int(rid), admin_username, status="resolved")
        print(f"Request #{rid} resolved.")
    except Exception as exc:
        print(f"Error: {exc}")
