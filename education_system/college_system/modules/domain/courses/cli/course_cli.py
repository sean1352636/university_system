"""CLI interface for course management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.infrastructure.auth.core import UserAuth


def course_menu(auth: UserAuth):
    """Course management menu."""
    service = CourseService(auth._db_path)
    role = auth.current_user.get("role", "student")
    is_admin = role in ("admin", "staff")

    while True:
        print_header("Course Management")
        options = []
        if is_admin:
            options.append(("1", "Add Course"))
        options.extend([
            ("2", "View Course"),
            ("3", "List Courses"),
            ("4", "Update Course"),
            ("5", "View Roster"),
        ])
        if is_admin:
            options.extend([
                ("6", "Manage Prerequisites"),
                ("7", "Delete Course"),
            ])
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "1" and is_admin:
            _add_course(service)
        elif choice == "2":
            _view_course(service)
        elif choice == "3":
            _list_courses(service)
        elif choice == "4":
            _update_course(service)
        elif choice == "5":
            _view_roster(service)
        elif choice == "6" and is_admin:
            _manage_prerequisites(service)
        elif choice == "7" and is_admin:
            _delete_course(service)
        elif choice == "0":
            break


def _add_course(service: CourseService):
    print_header("Add New Course")
    code = input("  Course Code (e.g., CS101): ").strip()
    title = input("  Title: ").strip()
    qual_type = input("  Qualification Type (A-Level/BTEC/T-Level/GCSE/Core Maths/EPQ) [A-Level]: ").strip() or "A-Level"
    glh = input("  Guided Learning Hours [3]: ").strip() or "3"
    capacity = input("  Capacity [30]: ").strip() or "30"
    subject_area = input("  Subject Area (optional): ").strip() or None
    teacher = input("  Teacher (optional): ").strip() or None
    term = input("  Term (Autumn/Spring/Summer, optional): ").strip() or None

    try:
        course = service.create_course(
            course_code=code, title=title, guided_learning_hours=int(glh),
            capacity=int(capacity), subject_area=subject_area,
            teacher=teacher, term=term, qualification_type=qual_type,
        )
        print(f"\n  Course created: {course['course_code']} - {course['title']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_course(service: CourseService):
    code = input("  Enter Course Code: ").strip()
    course = service.get_course_by_code(code)
    if course:
        enrolled = service.get_enrollment_count(course["id"])
        print(f"\n  Code: {course['course_code']}")
        print(f"  Title: {course['title']}")
        print(f"  Qualification: {course['qualification_type'] or 'N/A'}")
        print(f"  Guided Learning Hours: {course['credits']}")
        print(f"  Capacity: {enrolled}/{course['capacity']}")
        print(f"  Subject Area: {course['subject_area'] or 'N/A'}")
        print(f"  Teacher: {course['teacher'] or 'N/A'}")
        print(f"  Term: {course['term'] or 'N/A'}")
        print(f"  Status: {course['status']}")

        prereqs = service.get_prerequisites(course["id"])
        if prereqs:
            prereq_codes = ", ".join(p["course_code"] for p in prereqs)
            print(f"  Prerequisites: {prereq_codes}")
    else:
        print("\n  Course not found.")


def _list_courses(service: CourseService):
    courses = service.list_courses()
    if not courses:
        print("\n  No courses found.")
        return

    print(f"\n  {'Code':<10} {'Title':<30} {'Qualification':<14} {'Status':<10}")
    print(f"  {'-'*64}")
    for c in courses:
        print(f"  {c['course_code']:<10} {c['title']:<30} {c['qualification_type'] or 'N/A':<14} {c['status']:<10}")
    print(f"\n  Total: {len(courses)} courses")


def _update_course(service: CourseService):
    code = input("  Enter Course Code: ").strip()
    course = service.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    print(f"\n  Updating {course['course_code']} (press Enter to skip)")
    title = input(f"  Title [{course['title']}]: ").strip() or None
    capacity = input(f"  Capacity [{course['capacity']}]: ").strip()
    teacher = input(f"  Teacher [{course['teacher'] or ''}]: ").strip() or None

    kwargs = {}
    if title:
        kwargs["title"] = title
    if capacity:
        kwargs["capacity"] = int(capacity)
    if teacher:
        kwargs["teacher"] = teacher

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        updated = service.update_course(course["id"], **kwargs)
        print(f"\n  Course {updated['course_code']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_roster(service: CourseService):
    code = input("  Enter Course Code: ").strip()
    course = service.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    roster = service.get_roster(course["id"])
    if not roster:
        print(f"\n  No students enrolled in {code}.")
        return

    print(f"\n  Roster for {code} - {course['title']}:")
    for s in roster:
        print(f"  {s['student_id']} - {s['first_name']} {s['last_name']}")
    print(f"\n  Total: {len(roster)} students")


def _manage_prerequisites(service: CourseService):
    code = input("  Enter Course Code: ").strip()
    course = service.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    prereqs = service.get_prerequisites(course["id"])
    if prereqs:
        print(f"\n  Current prerequisites for {code}:")
        for p in prereqs:
            print(f"    - {p['course_code']} ({p['title']})")
    else:
        print(f"\n  No prerequisites for {code}.")

    action = input("\n  [1] Add prerequisite  [2] Remove prerequisite  [0] Back: ").strip()
    if action == "1":
        prereq_code = input("  Prerequisite Course Code: ").strip()
        prereq = service.get_course_by_code(prereq_code)
        if not prereq:
            print("\n  Prerequisite course not found.")
            return
        try:
            service.add_prerequisite(course["id"], prereq["id"])
            print(f"\n  {prereq_code} added as prerequisite for {code}.")
        except Exception as e:
            print(f"\n  Error: {e}")
    elif action == "2":
        prereq_code = input("  Prerequisite Course Code to remove: ").strip()
        prereq = service.get_course_by_code(prereq_code)
        if prereq:
            service.remove_prerequisite(course["id"], prereq["id"])
            print(f"\n  Prerequisite removed.")


def _delete_course(service: CourseService):
    code = input("  Enter Course Code to deactivate: ").strip()
    course = service.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    confirm = input(f"  Deactivate {code} - {course['title']}? (y/n): ").strip().lower()
    if confirm == "y":
        service.delete_course(course["id"])
        print(f"\n  Course {code} deactivated.")
