"""CLI interface for first aid management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.first_aid.services.first_aid_service import FirstAidService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def first_aid_menu(auth: UserAuth):
    """First aid management menu."""
    svc = FirstAidService(auth._db_path)

    while True:
        print_header("First Aid")
        options = [
            ("1", "Report Incident"),
            ("2", "View Incidents"),
            ("3", "View Incident Details"),
            ("4", "Update Incident"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _report_incident(svc, auth)
        elif choice == "2":
            _list_incidents(svc)
        elif choice == "3":
            _view_incident(svc)
        elif choice == "4":
            _update_incident(svc, auth)
        elif choice == "0":
            break


def _report_incident(svc, auth):
    print_header("Report Incident")
    student_svc = StudentService(auth._db_path)

    sid = input("  Student ID (optional): ").strip()
    student_id = None
    if sid:
        student = student_svc.get_student_by_student_id(sid)
        if not student:
            print(f"\n  Student '{sid}' not found.")
            return
        student_id = student["id"]

    description = input("  Description: ").strip()
    if not description:
        print("\n  Description is required.")
        return

    location = input("  Location (optional): ").strip() or None
    severity = input("  Severity (minor/moderate/severe/emergency) [minor]: ").strip() or "minor"
    incident_time = input("  Time (HH:MM, optional): ").strip() or None

    try:
        incident = svc.report_incident(
            reported_by=auth.current_user["user_id"],
            student_id=student_id,
            description=description,
            location=location,
            severity=severity,
            incident_time=incident_time,
        )
        print(f"\n  Incident reported (ID: {incident['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_incidents(svc):
    status = input("  Filter by status (open/treated/referred/closed, or Enter for all): ").strip() or None
    incidents = svc.list_incidents(status=status)
    if not incidents:
        print("\n  No incidents found.")
        return

    print(f"\n  {'ID':<5} {'Date':<12} {'Student':<20} {'Severity':<10} {'Status'}")
    print(f"  {'-' * 55}")
    for inc in incidents:
        student_name = ""
        if inc.get("first_name"):
            student_name = f"{inc['first_name']} {inc.get('last_name', '')}"
        print(f"  {inc['id']:<5} {inc['incident_date']:<12} {student_name[:18]:<20} "
              f"{inc['severity']:<10} {inc['status']}")


def _view_incident(svc):
    incident_id = input("  Incident ID: ").strip()
    try:
        inc = svc.get_incident(int(incident_id))
    except Exception as e:
        print(f"\n  Error: {e}")
        return

    student_name = "N/A"
    if inc.get("first_name"):
        student_name = f"{inc['first_name']} {inc.get('last_name', '')}"

    print(f"\n  Incident #{inc['id']}")
    print(f"  Date: {inc['incident_date']}  Time: {inc.get('incident_time') or 'N/A'}")
    print(f"  Student: {student_name}")
    print(f"  Location: {inc.get('location') or 'N/A'}")
    print(f"  Severity: {inc['severity']}  Status: {inc['status']}")
    print(f"  Description: {inc['description']}")
    print(f"  Treatment: {inc.get('treatment') or 'None'}")
    print(f"  Treated by: {inc.get('treated_by') or 'N/A'}")
    print(f"  Parent notified: {'Yes' if inc.get('parent_notified') else 'No'}")
    print(f"  Notes: {inc.get('notes') or 'None'}")


def _update_incident(svc, auth):
    incident_id = input("  Incident ID: ").strip()
    try:
        int(incident_id)
    except ValueError:
        print("\n  Invalid ID.")
        return

    print("  Leave blank to skip a field.")
    status = input("  New status (open/treated/referred/closed): ").strip() or None
    treatment = input("  Treatment: ").strip() or None
    notes = input("  Notes: ").strip() or None

    kwargs = {}
    if status:
        kwargs["status"] = status
    if treatment:
        kwargs["treatment"] = treatment
        kwargs["treated_by"] = auth.current_user.get("username", "")
    if notes:
        kwargs["notes"] = notes

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        svc.update_incident(int(incident_id), **kwargs)
        print("\n  Incident updated.")
    except Exception as e:
        print(f"\n  Error: {e}")
