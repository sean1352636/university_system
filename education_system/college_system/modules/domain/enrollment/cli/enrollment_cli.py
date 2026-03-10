"""CLI interface for enrollment management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.infrastructure.auth.core import UserAuth


def enrollment_menu(auth: UserAuth):
    """Enrollment management menu."""
    enroll_svc = EnrollmentService(auth._db_path)
    student_svc = StudentService(auth._db_path)
    course_svc = CourseService(auth._db_path)

    while True:
        print_header("Enrollment Management")
        options = [
            ("1", "Enroll Student"),
            ("2", "Drop Student"),
            ("3", "View Enrollments"),
            ("4", "View Waitlist"),
            ("5", "Student Enrollments"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _enroll_student(enroll_svc, student_svc, course_svc)
        elif choice == "2":
            _drop_student(enroll_svc, student_svc, course_svc)
        elif choice == "3":
            _view_enrollments(enroll_svc, course_svc)
        elif choice == "4":
            _view_waitlist(enroll_svc, course_svc)
        elif choice == "5":
            _student_enrollments(enroll_svc, student_svc)
        elif choice == "0":
            break


def _enroll_student(enroll_svc, student_svc, course_svc):
    print_header("Enroll Student")
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    try:
        result = enroll_svc.enroll_student(student["id"], course["id"])
        if result["status"] == "enrolled":
            print(f"\n  {sid} enrolled in {code} successfully.")
        else:
            print(f"\n  Course full. {sid} added to waitlist (position {result['position']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _drop_student(enroll_svc, student_svc, course_svc):
    print_header("Drop Student")
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    try:
        result = enroll_svc.drop_student(student["id"], course["id"])
        print(f"\n  {sid} dropped from {code}.")
        if result.get("promoted_student_pk"):
            print(f"  Next waitlisted student has been auto-promoted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_enrollments(enroll_svc, course_svc):
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    enrollments = enroll_svc.list_enrollments(course_pk=course["id"], status="enrolled")
    if not enrollments:
        print(f"\n  No students enrolled in {code}.")
        return

    print(f"\n  Enrolled students in {code}:")
    for e in enrollments:
        print(f"  {e['sid']} - {e['first_name']} {e['last_name']} (enrolled: {e['enrolled_at']})")
    print(f"\n  Total: {len(enrollments)}")


def _view_waitlist(enroll_svc, course_svc):
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    waitlist = enroll_svc.get_waitlist(course["id"])
    if not waitlist:
        print(f"\n  No students on waitlist for {code}.")
        return

    print(f"\n  Waitlist for {code}:")
    for w in waitlist:
        print(f"  #{w['position']} - {w['sid']} {w['first_name']} {w['last_name']}")


def _student_enrollments(enroll_svc, student_svc):
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    enrollments = enroll_svc.get_student_enrollments(student["id"])
    if not enrollments:
        print(f"\n  {sid} is not enrolled in any courses.")
        return

    print(f"\n  Enrollments for {sid}:")
    for e in enrollments:
        print(f"  {e['course_code']} - {e['title']} (enrolled: {e['enrolled_at']})")
