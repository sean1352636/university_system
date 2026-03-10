"""
Training Menu - Training and certifications CLI.
"""

from education_system.university_system.modules.domain.staff_hr.services import TrainingManager


def display_training_menu(user_id: str, is_admin: bool = False) -> None:
    """Display training and certifications menu."""
    while True:
        print("\n" + "=" * 60)
        print("TRAINING & CERTIFICATIONS")
        print("=" * 60)

        print("\n  1. Browse Available Courses")
        print("  2. My Enrolled Courses")
        print("  3. Enroll in Course")
        print("  4. Complete Course")
        print("  5. My Certifications")
        print("  6. Add Certification")
        print("  7. Expiring Certifications")
        print("  8. Mandatory Training Status")

        if is_admin:
            print("\n--- Admin ---")
            print("  9. Manage Courses")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _browse_courses()
        elif choice == '2':
            _view_enrollments(user_id)
        elif choice == '3':
            _enroll_course(user_id)
        elif choice == '4':
            _complete_course(user_id)
        elif choice == '5':
            _view_certifications(user_id)
        elif choice == '6':
            _add_certification(user_id)
        elif choice == '7':
            _expiring_certs()
        elif choice == '8':
            _mandatory_status(user_id)
        elif choice == '9' and is_admin:
            _manage_courses()
        else:
            print("Invalid choice.")


def _browse_courses() -> None:
    """Browse available courses."""
    courses = TrainingManager.get_courses()
    print("\n" + "-" * 60)
    print("AVAILABLE COURSES")
    print("-" * 60)

    categories = {}
    for c in courses:
        cat = c.get('category', 'Other')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)

    for cat, course_list in categories.items():
        print(f"\n[{cat}]")
        for c in course_list:
            mandatory = " [MANDATORY]" if c.get('is_mandatory') else ""
            print(f"  - {c.get('name')}{mandatory}")
            print(f"    Duration: {c.get('duration_hours', 'N/A')}h | Provider: {c.get('provider', 'N/A')}")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_enrollments(user_id: str) -> None:
    """View user's enrollments."""
    enrollments = TrainingManager.get_enrollments(user_id)
    print("\n" + "-" * 60)
    print("MY ENROLLED COURSES")
    print("-" * 60)
    if enrollments:
        for e in enrollments:
            status = e.get('status', 'enrolled').upper()
            print(f"\n  {e.get('course_name')}")
            print(f"    Status: {status} | Enrolled: {e.get('enrolled_date', 'N/A')[:10]}")
            if e.get('score'):
                print(f"    Score: {e.get('score')}")
            if e.get('due_date'):
                print(f"    Due: {e.get('due_date')}")
    else:
        print("No enrollments found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _enroll_course(user_id: str) -> None:
    """Enroll in a course."""
    courses = TrainingManager.get_courses()
    print("\nAvailable Courses:")
    for i, c in enumerate(courses, 1):
        mandatory = " *" if c.get('is_mandatory') else ""
        print(f"  {i}. {c.get('name')}{mandatory}")

    try:
        choice = int(input("\nSelect course (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(courses):
            course = courses[choice - 1]
            due_date = input("Due date (YYYY-MM-DD, or leave blank): ").strip()
            enrollment_id = TrainingManager.enroll(
                user_id, course['course_id'],
                due_date if due_date else None
            )
            print(f"\nEnrolled successfully. Enrollment ID: {enrollment_id}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _complete_course(user_id: str) -> None:
    """Mark a course as completed."""
    enrollments = TrainingManager.get_enrollments(user_id, status='in_progress')
    enrollments += TrainingManager.get_enrollments(user_id, status='enrolled')

    if not enrollments:
        print("\nNo courses in progress.")
        input("Press Enter to continue...")
        return

    print("\nCourses in Progress:")
    for i, e in enumerate(enrollments, 1):
        print(f"  {i}. {e.get('course_name')}")

    try:
        choice = int(input("\nSelect course (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(enrollments):
            enrollment = enrollments[choice - 1]
            score = float(input("Score achieved: ").strip())
            TrainingManager.complete_course(enrollment['enrollment_id'], score)
            print("\nCourse completed!")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_certifications(user_id: str) -> None:
    """View user's certifications."""
    certs = TrainingManager.get_certifications(user_id)
    print("\n" + "-" * 60)
    print("MY CERTIFICATIONS")
    print("-" * 60)
    if certs:
        for c in certs:
            status = c.get('status', 'active').upper()
            print(f"\n  {c.get('name')}")
            print(f"    Issuing Body: {c.get('issuing_body', 'N/A')}")
            print(f"    Issued: {c.get('issue_date', 'N/A')} | Expires: {c.get('expiry_date', 'N/A')}")
            print(f"    Status: {status}")
    else:
        print("No certifications found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_certification(user_id: str) -> None:
    """Add a certification."""
    print("\n--- Add Certification ---")
    name = input("Certification Name: ").strip()
    issuing_body = input("Issuing Body: ").strip()
    credential_id = input("Credential ID: ").strip()
    issue_date = input("Issue Date (YYYY-MM-DD): ").strip()
    expiry_date = input("Expiry Date (YYYY-MM-DD, or blank): ").strip()

    if name:
        try:
            cert_id = TrainingManager.add_certification(
                user_id, name,
                issuing_body=issuing_body,
                credential_id=credential_id,
                issue_date=issue_date,
                expiry_date=expiry_date if expiry_date else None
            )
            print(f"\nCertification added. ID: {cert_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nCertification name is required.")

    input("Press Enter to continue...")


def _expiring_certs() -> None:
    """View expiring certifications."""
    certs = TrainingManager.get_expiring_certs(days=60)
    print("\n" + "-" * 60)
    print("CERTIFICATIONS EXPIRING IN 60 DAYS")
    print("-" * 60)
    if certs:
        for c in certs:
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}"
            print(f"\n  {c.get('name')}")
            print(f"    Holder: {name.strip() or c.get('user_id')}")
            print(f"    Expires: {c.get('expiry_date')}")
    else:
        print("No certifications expiring soon.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _mandatory_status(user_id: str) -> None:
    """View mandatory training status."""
    incomplete = TrainingManager.get_mandatory_incomplete(user_id)
    print("\n" + "-" * 60)
    print("MANDATORY TRAINING STATUS")
    print("-" * 60)
    if incomplete:
        print("\nIncomplete Mandatory Training:")
        for c in incomplete:
            print(f"  - {c.get('name')}")
            print(f"    Duration: {c.get('duration_hours', 'N/A')}h")
    else:
        print("\nAll mandatory training complete!")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _manage_courses() -> None:
    """Admin: Manage courses."""
    print("\n--- Manage Courses ---")
    print("  1. Create New Course")
    print("  2. View All Courses")
    print("  0. Return")

    choice = input("\nChoice: ").strip()
    if choice == '1':
        name = input("Course Name: ").strip()
        category = input("Category: ").strip()
        duration = input("Duration (hours): ").strip()
        mandatory = input("Mandatory? (y/n): ").strip().lower() == 'y'

        if name:
            try:
                course_id = TrainingManager.create_course(
                    name, category=category,
                    duration_hours=float(duration) if duration else None,
                    is_mandatory=1 if mandatory else 0
                )
                print(f"\nCourse created. ID: {course_id}")
            except Exception as e:
                print(f"\nError: {e}")
        input("Press Enter to continue...")
