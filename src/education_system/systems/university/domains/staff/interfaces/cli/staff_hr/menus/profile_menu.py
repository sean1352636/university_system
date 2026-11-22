"""
Profile Menu - Staff profile management CLI.

Keyed by the signed-in username; EmployeeManager checks who may see or
change what (personal details: the person and HR; line managers: HR).
"""

from typing import Any

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services import EmployeeManager


def session_actor(user_id: Any) -> Any:
    """The signed-in session for ``user_id`` (the shared auth when it is the
    same person), else a bare ``{'username': ...}``."""
    key = access.staff_key(user_id) or (str(user_id) if user_id is not None else None)
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    except Exception:
        auth = None
    if auth is not None and access.username_of(auth) and access.username_of(auth) == key:
        return auth
    return {'username': key}


def _run(action) -> None:
    try:
        action()
    except (PermissionError, ValueError) as e:
        print(f"\n{e}")
        input("Press Enter to continue...")


def display_profile_menu(user_id: str) -> None:
    """Display profile management menu."""
    actor = session_actor(user_id)
    user_id = access.username_of(actor)
    if not user_id:
        print("\nPlease sign in to use My Profile.")
        return
    is_manager = access.can(actor, 'manager')
    is_hr = access.can(actor, 'hr')
    while True:
        print("\n" + "=" * 60)
        print("MY PROFILE")
        print("=" * 60)

        profile = EmployeeManager.get_profile(user_id, actor=actor)

        if profile:
            print(f"\nEmployee ID: {profile.get('employee_id', 'N/A')}")
            print(f"Department: {profile.get('department', 'N/A')}")
            print(f"Job Title: {profile.get('job_title', 'N/A')}")
            print(f"Employment Type: {profile.get('employment_type', 'N/A')}")
            print(f"Office: {profile.get('office_location', 'N/A')}")
        else:
            print("\nNo profile found. Please contact HR to set up your profile.")

        print("\n  1. View Full Profile")
        print("  2. Update Contact Info")
        print("  3. Update Emergency Contact")
        print("  4. View My Documents")
        print("  5. Upload Document")
        print("  6. View Workload")
        print("  7. View Schedule")
        if is_manager:
            print("  8. My Team")
        if is_hr:
            print("  9. Set a Line Manager")
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _run(lambda: _view_full_profile(user_id, actor))
        elif choice == '2':
            _run(lambda: _update_contact_info(user_id, actor))
        elif choice == '3':
            _run(lambda: _update_emergency_contact(user_id, actor))
        elif choice == '4':
            _run(lambda: _view_documents(user_id, actor))
        elif choice == '5':
            _run(lambda: _upload_document(user_id, actor))
        elif choice == '6':
            _run(lambda: _view_workload(user_id, actor))
        elif choice == '7':
            _run(lambda: _view_schedule(user_id, actor))
        elif choice == '8' and is_manager:
            _run(lambda: _view_team(actor))
        elif choice == '9' and is_hr:
            _run(lambda: _set_line_manager(actor))
        else:
            print("Invalid choice.")


def _view_full_profile(user_id: str, actor: Any = None) -> None:
    """View full profile details."""
    profile = EmployeeManager.get_profile(user_id, actor=actor)
    if not profile:
        print("\nNo profile found.")
        input("Press Enter to continue...")
        return

    print("\n" + "-" * 50)
    print("FULL PROFILE")
    print("-" * 50)
    for key, value in profile.items():
        if key not in ('created_at', 'updated_at', 'profile_id'):
            print(f"{key.replace('_', ' ').title()}: {value or 'N/A'}")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _update_contact_info(user_id: str, actor: Any = None) -> None:
    """Update contact information."""
    print("\n--- Update Contact Info ---")
    phone = input("Phone Extension (leave blank to skip): ").strip()
    office = input("Office Location (leave blank to skip): ").strip()

    updates = {}
    if phone:
        updates['phone_extension'] = phone
    if office:
        updates['office_location'] = office

    if updates:
        EmployeeManager.save_profile(actor, user_id, **updates)
        print("\nContact info updated successfully.")
    else:
        print("\nNo changes made.")
    input("Press Enter to continue...")


def _update_emergency_contact(user_id: str, actor: Any = None) -> None:
    """Update emergency contact."""
    print("\n--- Update Emergency Contact ---")
    name = input("Contact Name: ").strip()
    phone = input("Contact Phone: ").strip()
    relationship = input("Relationship: ").strip()

    if name and phone:
        EmployeeManager.save_profile(actor, user_id, emergency_contact_name=name,
                                     emergency_contact_phone=phone,
                                     emergency_contact_relationship=relationship)
        print("\nEmergency contact updated successfully.")
    else:
        print("\nName and phone are required.")
    input("Press Enter to continue...")


def _view_documents(user_id: str, actor: Any = None) -> None:
    """View user's documents."""
    docs = EmployeeManager.get_documents(user_id, actor=actor)
    print("\n" + "-" * 50)
    print("MY DOCUMENTS")
    print("-" * 50)
    if docs:
        for doc in docs:
            status = doc.get('status', 'active')
            expiry = doc.get('expiry_date', '')
            print(f"  - {doc.get('document_name')} ({doc.get('document_type')})")
            print(f"    Status: {status}, Expiry: {expiry or 'N/A'}")
    else:
        print("  No documents found.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _upload_document(user_id: str, actor: Any = None) -> None:
    """Upload a new document."""
    print("\n--- Upload Document ---")
    doc_types = ['contract', 'id_document', 'qualification', 'certification',
                 'visa', 'right_to_work', 'dbs_check', 'reference', 'other']
    print("Document Types:", ', '.join(doc_types))

    doc_type = input("Document Type: ").strip().lower()
    if doc_type not in doc_types:
        print("Invalid document type.")
        input("Press Enter to continue...")
        return

    doc_name = input("Document Name: ").strip()
    file_path = input("File Path: ").strip()
    expiry = input("Expiry Date (YYYY-MM-DD, or leave blank): ").strip()

    if doc_name:
        EmployeeManager.add_document(
            user_id, doc_type, doc_name, file_path or None, actor=actor,
            expiry_date=expiry if expiry else None
        )
        print("\nDocument uploaded successfully.")
    else:
        print("\nDocument name is required.")
    input("Press Enter to continue...")


def _view_workload(user_id: str, actor: Any = None) -> None:
    """View workload allocation."""
    workload = EmployeeManager.get_workload(user_id, actor=actor)
    print("\n" + "-" * 50)
    print("WORKLOAD ALLOCATION")
    print("-" * 50)
    if workload:
        for w in workload:
            print(f"\n{w.get('academic_year')} - {w.get('semester') or 'Full year'}")
            print(f"  Teaching: {w.get('teaching_hours', 0)} hours")
            print(f"  Research: {w.get('research_hours', 0)} hours")
            print(f"  Admin: {w.get('admin_hours', 0)} hours")
            print(f"  Service: {w.get('service_hours', 0)} hours")
            print(f"  Total FTE: {w.get('total_fte', 1.0)}")
    else:
        print("  No workload data found.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _view_schedule(user_id: str, actor: Any = None) -> None:
    """View schedule."""
    schedules = EmployeeManager.get_schedules(user_id, actor=actor)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    print("\n" + "-" * 50)
    print("MY SCHEDULE")
    print("-" * 50)
    if schedules:
        for s in schedules:
            day = days[s['day_of_week']] if isinstance(s.get('day_of_week'), int) and 0 <= s['day_of_week'] < 7 else 'N/A'
            print(f"  {day}: {s.get('start_time')} - {s.get('end_time')}")
            print(f"      Type: {s.get('schedule_type')}, Location: {s.get('location', 'N/A')}")
    else:
        print("  No schedule entries found.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _view_team(actor: Any) -> None:
    """A line manager's reports (directory details only)."""
    deep = input("Include indirect reports? (y/N): ").strip().lower() == 'y'
    team = EmployeeManager.team_of(actor, deep=deep)
    print("\n" + "-" * 70)
    print("MY TEAM")
    print("-" * 70)
    if team:
        for t in team:
            name = ' '.join(p for p in (t.get('first_name'), t.get('last_name')) if p)
            print(f"  {t['username']:<16} {name or '':<24} {t.get('job_title') or 'N/A'}")
            print(f"      {t.get('department') or 'N/A'} | {t.get('email') or 'N/A'} | "
                  f"manager: {t.get('manager_id') or 'N/A'}")
    else:
        print("  Nobody reports to you.")
    print("-" * 70)
    input("\nPress Enter to continue...")


def _set_line_manager(actor: Any) -> None:
    """HR: set or clear someone's line manager."""
    print("\n--- Set a Line Manager ---")
    staff = input("Staff member (username or employee number): ").strip()
    if not staff:
        return
    current = (EmployeeManager.get_profile(staff, actor=actor) or {}).get('manager_id')
    print(f"Current line manager: {current or 'none'}")
    manager = input("New line manager (blank for none): ").strip()
    boss = EmployeeManager.set_line_manager(actor, staff, manager or None)
    print(f"\nLine manager is now {boss or 'nobody'}.")
    input("Press Enter to continue...")
