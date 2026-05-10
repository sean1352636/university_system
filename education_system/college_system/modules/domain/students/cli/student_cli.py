"""CLI interface for student management."""

import logging

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.core.exceptions import StudentError, ValidationError
from education_system.college_system.infrastructure.auth.core import UserAuth

logger = logging.getLogger(__name__)


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


def _prompt_choice(label: str, choices: list[str], default: str = "") -> str | None:
    """Prompt for a value restricted to a choice list. Empty input returns ``default``."""
    raw = input(f"  {label} ({'/'.join(c for c in choices if c)}, optional): ").strip()
    if not raw:
        return default or None
    if raw not in choices:
        print(f"  Invalid value '{raw}'; ignoring.")
        return default or None
    return raw


def _add_student(service: StudentService):
    print_header("Add New Student")
    title = _prompt_choice("Title", ["", "Mr", "Ms", "Mrs", "Miss", "Mx", "Dr"])
    first_name = input("  First Name *: ").strip()
    middle_name = input("  Middle Name (optional): ").strip() or None
    last_name = input("  Last Name *: ").strip()
    gender = _prompt_choice(
        "Gender", ["", "male", "female", "other", "prefer_not_to_say"])
    phone = input("  Phone (optional): ").strip() or None
    dob = input("  Date of Birth (YYYY-MM-DD, optional): ").strip() or None
    address = input("  Address (optional): ").strip() or None
    year_group = input("  Year Group (12/13) [12]: ").strip() or "12"
    form_group = input("  Form Group (optional): ").strip() or None
    form_tutor = input("  Form Tutor (optional): ").strip() or None

    if not first_name or not last_name:
        print("\n  Error: First and last name are required.")
        return

    try:
        student = service.create_student(
            first_name=first_name, last_name=last_name,
            phone=phone, date_of_birth=dob, address=address,
            year_group=year_group, form_group=form_group, form_tutor=form_tutor,
            title=title, middle_name=middle_name, gender=gender,
        )
    except (StudentError, ValidationError) as e:
        logger.warning("CLI student add rejected: %s", e)
        print(f"\n  Error: {e}")
        return
    except Exception as e:
        logger.exception("CLI student add failed unexpectedly")
        print(f"\n  Unexpected error: {e}")
        return

    print(
        f"\n  Student created: {student['student_id']} - "
        f"{student['first_name']} {student['last_name']}"
    )
    print(f"  Email (auto-generated): {student['email']}")


def _view_student(service: StudentService):
    student_id = input("  Enter Student ID (e.g., SFC0001): ").strip()
    try:
        student = service.get_student_by_student_id(student_id)
    except Exception as e:
        logger.exception("CLI view-student failed")
        print(f"\n  Error: {e}")
        return
    if not student:
        print("\n  Student not found.")
        return
    print(f"\n  ID: {student['student_id']}")
    full_name = " ".join(p for p in (
        student.get("title"), student.get("first_name"),
        student.get("middle_name"), student.get("last_name"),
    ) if p)
    print(f"  Name: {full_name}")
    print(f"  Gender: {student.get('gender') or 'N/A'}")
    print(f"  Email: {student['email'] or 'N/A'}")
    print(f"  Phone: {student['phone'] or 'N/A'}")
    print(f"  Year Group: {student['year_group'] or 'N/A'}")
    print(f"  Form Group: {student['form_group'] or 'N/A'}")
    print(f"  Form Tutor: {student['form_tutor'] or 'N/A'}")
    print(f"  Status: {student['status']}")
    print(f"  Enrolled: {student['enrollment_date']}")


def _list_students(service: StudentService):
    try:
        students = service.list_students()
    except Exception as e:
        logger.exception("CLI list-students failed")
        print(f"\n  Error: {e}")
        return
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
    try:
        student = service.get_student_by_student_id(student_id)
    except Exception as e:
        logger.exception("CLI update-student lookup failed")
        print(f"\n  Error: {e}")
        return
    if not student:
        print("\n  Student not found.")
        return

    print(f"\n  Updating {student['first_name']} {student['last_name']} (press Enter to skip)")
    title = input(f"  Title [{student.get('title') or ''}]: ").strip() or None
    first_name = input(f"  First Name [{student['first_name']}]: ").strip() or None
    middle_name = input(f"  Middle Name [{student.get('middle_name') or ''}]: ").strip() or None
    last_name = input(f"  Last Name [{student['last_name']}]: ").strip() or None
    gender = input(f"  Gender [{student.get('gender') or ''}]: ").strip() or None
    year_group = input(f"  Year Group [{student['year_group'] or ''}]: ").strip() or None
    form_group = input(f"  Form Group [{student['form_group'] or ''}]: ").strip() or None
    form_tutor = input(f"  Form Tutor [{student['form_tutor'] or ''}]: ").strip() or None

    kwargs = {k: v for k, v in {
        "title": title, "first_name": first_name, "middle_name": middle_name,
        "last_name": last_name, "gender": gender, "year_group": year_group,
        "form_group": form_group, "form_tutor": form_tutor,
    }.items() if v}

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        updated = service.update_student(student["id"], **kwargs)
        print(f"\n  Student {updated['student_id']} updated successfully.")
    except (StudentError, ValidationError) as e:
        logger.warning("CLI update-student rejected: %s", e)
        print(f"\n  Error: {e}")
    except Exception as e:
        logger.exception("CLI update-student failed unexpectedly")
        print(f"\n  Unexpected error: {e}")


def _search_students(service: StudentService):
    term = input("  Search term: ").strip()
    try:
        results = service.list_students(search=term)
    except Exception as e:
        logger.exception("CLI student search failed")
        print(f"\n  Error: {e}")
        return
    if not results:
        print("\n  No matching students found.")
        return

    for s in results:
        print(f"  {s['student_id']} - {s['first_name']} {s['last_name']} (Year {s['year_group'] or 'N/A'})")


def _delete_student(service: StudentService):
    student_id = input("  Enter Student ID to deactivate: ").strip()
    try:
        student = service.get_student_by_student_id(student_id)
    except Exception as e:
        logger.exception("CLI delete-student lookup failed")
        print(f"\n  Error: {e}")
        return
    if not student:
        print("\n  Student not found.")
        return

    confirm = input(f"  Deactivate {student['first_name']} {student['last_name']}? (y/n): ").strip().lower()
    if confirm != "y":
        print("\n  Cancelled.")
        return

    try:
        service.delete_student(student["id"])
        print(f"\n  Student {student_id} deactivated.")
    except (StudentError, ValidationError) as e:
        logger.warning("CLI delete-student rejected: %s", e)
        print(f"\n  Error: {e}")
    except Exception as e:
        logger.exception("CLI delete-student failed unexpectedly")
        print(f"\n  Unexpected error: {e}")
