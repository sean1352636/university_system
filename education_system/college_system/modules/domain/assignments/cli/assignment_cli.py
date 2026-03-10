"""Assignment CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def assignment_menu(auth: UserAuth):
    """Assignment management menu."""
    svc = AssignmentService(auth._db_path)

    while True:
        print_header("Assignment Management")
        options = [
            ("1", "Create Assignment"),
            ("2", "List Assignments"),
            ("3", "Submit Assignment"),
            ("4", "Grade Submission"),
            ("5", "My Submissions"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _create_assignment(svc, auth)
        elif choice == "2":
            _list_assignments(svc)
        elif choice == "3":
            _submit_assignment(svc, auth)
        elif choice == "4":
            _grade_submission(svc, auth)
        elif choice == "5":
            _my_submissions(svc, auth)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _create_assignment(svc: AssignmentService, auth: UserAuth):
    print_header("Create Assignment")
    try:
        course_id = int(input("Course ID: ").strip())
        title = input("Title: ").strip()
        desc = input("Description (optional): ").strip() or None
        due_date = input("Due date (YYYY-MM-DD): ").strip()
        max_score_str = input("Max score [100]: ").strip()
        max_score = float(max_score_str) if max_score_str else 100
        allow_late = input("Allow late submissions? (y/n) [n]: ").strip().lower() == "y"

        assignment = svc.create_assignment(
            course_id, title, desc, due_date, max_score, allow_late,
            created_by=auth.current_user["user_id"],
        )
        print(f"\n  Assignment created (ID: {assignment['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_assignments(svc: AssignmentService):
    print_header("List Assignments")
    try:
        course_id_str = input("Course ID (blank for all): ").strip()
        course_id = int(course_id_str) if course_id_str else None

        assignments = svc.list_assignments(course_id)
        if not assignments:
            print("\n  No assignments found.")
            return
        print(f"\n  {'ID':<5} {'Course':<10} {'Title':<25} {'Due Date':<12} {'Max':<6}")
        print(f"  {'-'*58}")
        for a in assignments:
            print(f"  {a['id']:<5} {a['course_code']:<10} {a['title'][:24]:<25} "
                  f"{a['due_date']:<12} {a['max_score']:<6.0f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _submit_assignment(svc: AssignmentService, auth: UserAuth):
    print_header("Submit Assignment")
    try:
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(auth._db_path)
        try:
            student = conn.execute(
                "SELECT id FROM students WHERE user_id = ?",
                (auth.current_user["user_id"],),
            ).fetchone()
        finally:
            conn.close()

        if not student:
            print("\n  No student record linked to your account.")
            return

        assignment_id = int(input("Assignment ID: ").strip())
        content = input("Content: ").strip()

        sub = svc.submit(assignment_id, student["id"], content)
        late_str = " (LATE)" if sub["is_late"] else ""
        print(f"\n  Submission recorded (ID: {sub['id']}){late_str}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _grade_submission(svc: AssignmentService, auth: UserAuth):
    print_header("Grade Submission")
    try:
        submission_id = int(input("Submission ID: ").strip())
        score = float(input("Score: ").strip())
        feedback = input("Feedback (optional): ").strip() or None

        result = svc.grade_submission(
            submission_id, score, feedback,
            graded_by=auth.current_user["user_id"],
        )
        print(f"\n  Submission {result['id']} graded: {result['score']}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _my_submissions(svc: AssignmentService, auth: UserAuth):
    print_header("My Submissions")
    try:
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(auth._db_path)
        try:
            student = conn.execute(
                "SELECT id FROM students WHERE user_id = ?",
                (auth.current_user["user_id"],),
            ).fetchone()
        finally:
            conn.close()

        if not student:
            print("\n  No student record linked to your account.")
            return

        subs = svc.get_student_submissions(student["id"])
        if not subs:
            print("\n  No submissions found.")
            return
        print(f"\n  {'ID':<5} {'Course':<10} {'Assignment':<22} {'Score':<8} {'Late':<5}")
        print(f"  {'-'*50}")
        for s in subs:
            score_str = str(s['score']) if s['score'] is not None else "-"
            late_str = "Yes" if s['is_late'] else "No"
            print(f"  {s['id']:<5} {s['course_code']:<10} "
                  f"{s['assignment_title'][:21]:<22} {score_str:<8} {late_str:<5}")
    except Exception as e:
        print(f"\n  Error: {e}")
