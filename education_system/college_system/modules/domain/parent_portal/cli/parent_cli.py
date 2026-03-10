"""CLI interface for parent portal."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.parent_portal.services.parent_service import ParentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def parent_menu(auth: UserAuth):
    """Parent portal menu - dispatches based on role."""
    role = auth.current_user.get("role", "student")
    if role == "parent":
        _parent_view_menu(auth)
    elif role == "admin":
        _admin_link_menu(auth)
    else:
        print("\n  Parent Portal is not available for your role.")


def _parent_view_menu(auth: UserAuth):
    """Parent view of their children's data."""
    svc = ParentService(auth._db_path)
    user_id = auth.current_user["user_id"]

    while True:
        print_header("Parent Portal")
        options = [
            ("1", "View My Children"),
            ("2", "View Child Grades"),
            ("3", "View Child Attendance"),
            ("4", "View Child Timetable"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_children(svc, user_id)
        elif choice == "2":
            _view_child_grades(svc, user_id)
        elif choice == "3":
            _view_child_attendance(svc, user_id)
        elif choice == "4":
            _view_child_timetable(svc, user_id)
        elif choice == "0":
            break


def _admin_link_menu(auth: UserAuth):
    """Admin management of parent-student links."""
    svc = ParentService(auth._db_path)

    while True:
        print_header("Parent Portal - Admin")
        options = [
            ("1", "List Parent Links"),
            ("2", "Link Parent to Student"),
            ("3", "Unlink Parent from Student"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_links(svc, auth)
        elif choice == "2":
            _link_parent(svc)
        elif choice == "3":
            _unlink_parent(svc)
        elif choice == "0":
            break


def _view_children(svc, user_id):
    children = svc.get_linked_students(user_id)
    if not children:
        print("\n  No children linked to your account.")
        return
    print("\n  Your Children:")
    for c in children:
        print(f"  {c['student_id']} - {c['first_name']} {c['last_name']} "
              f"(Year {c.get('year_group', '?')}, Form {c.get('form_group', '?')})")


def _select_child(svc, user_id):
    """Helper to select a child by student PK."""
    children = svc.get_linked_students(user_id)
    if not children:
        print("\n  No children linked to your account.")
        return None
    print("\n  Your Children:")
    for i, c in enumerate(children, 1):
        print(f"  [{i}] {c['student_id']} - {c['first_name']} {c['last_name']}")
    idx = input("  Select child number: ").strip()
    try:
        child = children[int(idx) - 1]
        return child["id"]
    except (ValueError, IndexError):
        print("\n  Invalid selection.")
        return None


def _view_child_grades(svc, user_id):
    child_pk = _select_child(svc, user_id)
    if child_pk is None:
        return
    try:
        grades = svc.get_child_grades(user_id, child_pk)
    except Exception as e:
        print(f"\n  Error: {e}")
        return
    if not grades:
        print("\n  No grades found.")
        return
    print(f"\n  {'Course':<10} {'Title':<25} {'Grade':<8} {'Score':<8} {'Type'}")
    print(f"  {'-' * 55}")
    for g in grades:
        print(f"  {g['course_code']:<10} {g['course_title'][:23]:<25} "
              f"{g.get('letter_grade') or '-':<8} {g.get('score') or '-':<8} "
              f"{g.get('grade_type') or '-'}")


def _view_child_attendance(svc, user_id):
    child_pk = _select_child(svc, user_id)
    if child_pk is None:
        return
    try:
        summaries = svc.get_child_attendance(user_id, child_pk)
    except Exception as e:
        print(f"\n  Error: {e}")
        return
    if not summaries:
        print("\n  No attendance data found.")
        return
    print(f"\n  {'Course':<10} {'Title':<20} {'Total':<7} {'Present':<8} "
          f"{'Absent':<8} {'Late':<6} {'Rate'}")
    print(f"  {'-' * 65}")
    for s in summaries:
        print(f"  {s['course_code']:<10} {s['course_title'][:18]:<20} "
              f"{s['total']:<7} {s['present']:<8} {s['absent']:<8} "
              f"{s['late']:<6} {s['rate']:.1f}%")


def _view_child_timetable(svc, user_id):
    child_pk = _select_child(svc, user_id)
    if child_pk is None:
        return
    try:
        slots = svc.get_child_timetable(user_id, child_pk)
    except Exception as e:
        print(f"\n  Error: {e}")
        return
    if not slots:
        print("\n  No timetable data found.")
        return
    print(f"\n  {'Day':<6} {'Time':<14} {'Course':<20} {'Room':<10} {'Instructor'}")
    print(f"  {'-' * 55}")
    for sl in slots:
        time_str = f"{sl['start_time']}-{sl['end_time']}"
        print(f"  {sl['day_of_week']:<6} {time_str:<14} "
              f"{sl['course_title'][:18]:<20} {sl.get('room') or '-':<10} "
              f"{sl.get('instructor_name') or '-'}")


def _list_links(svc, auth):
    from education_system.college_system.infrastructure.database.db import connect
    conn = connect(auth._db_path)
    try:
        rows = conn.execute(
            """SELECT pl.*, u.username, s.student_id as sid,
                      s.first_name, s.last_name
               FROM parent_links pl
               JOIN users u ON pl.parent_user_id = u.id
               JOIN students s ON pl.student_id = s.id
               ORDER BY u.username"""
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("\n  No parent links found.")
        return

    print(f"\n  {'Parent':<15} {'Student ID':<12} {'Student Name':<25} {'Relationship'}")
    print(f"  {'-' * 55}")
    for r in rows:
        print(f"  {r['username']:<15} {r['sid']:<12} "
              f"{r['first_name']} {r['last_name']:<20} "
              f"{r.get('relationship') or 'parent'}")


def _link_parent(svc):
    print_header("Link Parent to Student")
    parent_id = input("  Parent user ID: ").strip()
    student_id = input("  Student ID (PK): ").strip()
    relationship = input("  Relationship [parent]: ").strip() or "parent"
    try:
        svc.admin_link_parent(int(parent_id), int(student_id), relationship)
        print("\n  Parent linked to student.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _unlink_parent(svc):
    parent_id = input("  Parent user ID: ").strip()
    student_id = input("  Student ID (PK): ").strip()
    try:
        svc.unlink_parent(int(parent_id), int(student_id))
        print("\n  Link removed.")
    except Exception as e:
        print(f"\n  Error: {e}")
