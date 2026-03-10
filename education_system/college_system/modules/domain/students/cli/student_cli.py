"""CLI interface for student management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def student_menu(auth: UserAuth):
    """Student management menu."""
    service = StudentService(auth._db_path)

    while True:
        print_header("Student Management")
        options = [
            ("1", "Add Student"),
            ("2", "View Student"),
            ("3", "List Students"),
            ("4", "Update Student"),
            ("5", "Search Students"),
            ("6", "Delete Student"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _add_student(service)
        elif choice == "2":
            _view_student(service)
        elif choice == "3":
            _list_students(service)
        elif choice == "4":
            _update_student(service)
        elif choice == "5":
            _search_students(service)
        elif choice == "6":
            _delete_student(service)
        elif choice == "0":
            break


def _add_student(service: StudentService):
    print_header("Add New Student")
    first_name = input("  First Name: ").strip()
    last_name = input("  Last Name: ").strip()
    email = input("  Email (optional): ").strip() or None
    phone = input("  Phone (optional): ").strip() or None
    dob = input("  Date of Birth (YYYY-MM-DD, optional): ").strip() or None
    year_group = input("  Year Group (12/13) [12]: ").strip() or "12"
    form_group = input("  Form Group (optional): ").strip() or None
    form_tutor = input("  Form Tutor (optional): ").strip() or None

    try:
        student = service.create_student(
            first_name=first_name, last_name=last_name,
            email=email, phone=phone, date_of_birth=dob,
            year_group=year_group, form_group=form_group, form_tutor=form_tutor,
        )
        print(f"\n  Student created: {student['student_id']} - {student['first_name']} {student['last_name']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_student(service: StudentService):
    student_id = input("  Enter Student ID (e.g., SFC0001): ").strip()
    student = service.get_student_by_student_id(student_id)
    if student:
        print(f"\n  ID: {student['student_id']}")
        print(f"  Name: {student['first_name']} {student['last_name']}")
        print(f"  Email: {student['email'] or 'N/A'}")
        print(f"  Phone: {student['phone'] or 'N/A'}")
        print(f"  Year Group: {student['year_group'] or 'N/A'}")
        print(f"  Form Group: {student['form_group'] or 'N/A'}")
        print(f"  Form Tutor: {student['form_tutor'] or 'N/A'}")
        print(f"  Status: {student['status']}")
        print(f"  Enrolled: {student['enrollment_date']}")
    else:
        print("\n  Student not found.")


def _list_students(service: StudentService):
    students = service.list_students()
    if not students:
        print("\n  No students found.")
        return

    print(f"\n  {'ID':<10} {'Name':<25} {'Year':<6} {'Form':<10} {'Status':<10}")
    print(f"  {'-'*61}")
    for s in students:
        name = f"{s['first_name']} {s['last_name']}"
        print(f"  {s['student_id']:<10} {name:<25} {s['year_group'] or 'N/A':<6} {s['form_group'] or 'N/A':<10} {s['status']:<10}")
    print(f"\n  Total: {len(students)} students")


def _update_student(service: StudentService):
    student_id = input("  Enter Student ID: ").strip()
    student = service.get_student_by_student_id(student_id)
    if not student:
        print("\n  Student not found.")
        return

    print(f"\n  Updating {student['first_name']} {student['last_name']} (press Enter to skip)")
    first_name = input(f"  First Name [{student['first_name']}]: ").strip() or None
    last_name = input(f"  Last Name [{student['last_name']}]: ").strip() or None
    email = input(f"  Email [{student['email'] or ''}]: ").strip() or None
    year_group = input(f"  Year Group [{student['year_group'] or ''}]: ").strip() or None
    form_group = input(f"  Form Group [{student['form_group'] or ''}]: ").strip() or None
    form_tutor = input(f"  Form Tutor [{student['form_tutor'] or ''}]: ").strip() or None

    kwargs = {}
    if first_name:
        kwargs["first_name"] = first_name
    if last_name:
        kwargs["last_name"] = last_name
    if email:
        kwargs["email"] = email
    if year_group:
        kwargs["year_group"] = year_group
    if form_group:
        kwargs["form_group"] = form_group
    if form_tutor:
        kwargs["form_tutor"] = form_tutor

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        updated = service.update_student(student["id"], **kwargs)
        print(f"\n  Student {updated['student_id']} updated successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _search_students(service: StudentService):
    term = input("  Search term: ").strip()
    results = service.list_students(search=term)
    if not results:
        print("\n  No matching students found.")
        return

    for s in results:
        print(f"  {s['student_id']} - {s['first_name']} {s['last_name']} (Year {s['year_group'] or 'N/A'})")


def _delete_student(service: StudentService):
    student_id = input("  Enter Student ID to deactivate: ").strip()
    student = service.get_student_by_student_id(student_id)
    if not student:
        print("\n  Student not found.")
        return

    confirm = input(f"  Deactivate {student['first_name']} {student['last_name']}? (y/n): ").strip().lower()
    if confirm == "y":
        service.delete_student(student["id"])
        print(f"\n  Student {student_id} deactivated.")
    else:
        print("\n  Cancelled.")
