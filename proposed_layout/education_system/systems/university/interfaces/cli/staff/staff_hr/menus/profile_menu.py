"""
Profile Menu - Staff profile management CLI.
"""

from education_system.systems.university.domain.staff.staff_hr.services import EmployeeManager


def display_profile_menu(user_id: str) -> None:
    """Display profile management menu."""
    while True:
        print("\n" + "=" * 60)
        print("MY PROFILE")
        print("=" * 60)

        profile = EmployeeManager.get_profile(user_id)

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
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_full_profile(user_id)
        elif choice == '2':
            _update_contact_info(user_id)
        elif choice == '3':
            _update_emergency_contact(user_id)
        elif choice == '4':
            _view_documents(user_id)
        elif choice == '5':
            _upload_document(user_id)
        elif choice == '6':
            _view_workload(user_id)
        elif choice == '7':
            _view_schedule(user_id)
        else:
            print("Invalid choice.")


def _view_full_profile(user_id: str) -> None:
    """View full profile details."""
    profile = EmployeeManager.get_profile(user_id)
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


def _update_contact_info(user_id: str) -> None:
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
        EmployeeManager.update_profile(user_id, **updates)
        print("\nContact info updated successfully.")
    else:
        print("\nNo changes made.")
    input("Press Enter to continue...")


def _update_emergency_contact(user_id: str) -> None:
    """Update emergency contact."""
    print("\n--- Update Emergency Contact ---")
    name = input("Contact Name: ").strip()
    phone = input("Contact Phone: ").strip()
    relationship = input("Relationship: ").strip()

    if name and phone:
        EmployeeManager.update_emergency_contact(user_id, name, phone, relationship)
        print("\nEmergency contact updated successfully.")
    else:
        print("\nName and phone are required.")
    input("Press Enter to continue...")


def _view_documents(user_id: str) -> None:
    """View user's documents."""
    docs = EmployeeManager.get_documents(user_id)
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


def _upload_document(user_id: str) -> None:
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
            user_id, doc_type, doc_name, file_path,
            expiry_date=expiry if expiry else None
        )
        print("\nDocument uploaded successfully.")
    else:
        print("\nDocument name is required.")
    input("Press Enter to continue...")


def _view_workload(user_id: str) -> None:
    """View workload allocation."""
    workload = EmployeeManager.get_workload(user_id)
    print("\n" + "-" * 50)
    print("WORKLOAD ALLOCATION")
    print("-" * 50)
    if workload:
        for w in workload:
            print(f"\n{w.get('academic_year')} - {w.get('semester', 'N/A')}")
            print(f"  Teaching: {w.get('teaching_hours', 0)} hours")
            print(f"  Research: {w.get('research_hours', 0)} hours")
            print(f"  Admin: {w.get('admin_hours', 0)} hours")
            print(f"  Service: {w.get('service_hours', 0)} hours")
            print(f"  Total FTE: {w.get('total_fte', 1.0)}")
    else:
        print("  No workload data found.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _view_schedule(user_id: str) -> None:
    """View schedule."""
    schedules = EmployeeManager.get_schedules(user_id)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    print("\n" + "-" * 50)
    print("MY SCHEDULE")
    print("-" * 50)
    if schedules:
        for s in schedules:
            day = days[s.get('day_of_week', 0)] if s.get('day_of_week') is not None else 'N/A'
            print(f"  {day}: {s.get('start_time')} - {s.get('end_time')}")
            print(f"      Type: {s.get('schedule_type')}, Location: {s.get('location', 'N/A')}")
    else:
        print("  No schedule entries found.")
    print("-" * 50)
    input("\nPress Enter to continue...")
