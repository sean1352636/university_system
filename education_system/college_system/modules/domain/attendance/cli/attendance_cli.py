"""CLI interface for attendance management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.attendance.services.attendance_service import AttendanceService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def attendance_menu(auth: UserAuth):
    """Attendance management menu."""
    att_svc = AttendanceService(auth._db_path)
    course_svc = CourseService(auth._db_path)
    student_svc = StudentService(auth._db_path)

    while True:
        print_header("Attendance Management")
        options = [
            ("1", "Create Attendance Session"),
            ("2", "Record Attendance"),
            ("3", "Bulk Record Attendance"),
            ("4", "View Session Records"),
            ("5", "Student Attendance Summary"),
            ("6", "Course Attendance Report"),
            ("7", "Generate Registers for Date"),
            ("8", "Pre-populate Register"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _create_session(att_svc, course_svc, auth)
        elif choice == "2":
            _record_attendance(att_svc, student_svc)
        elif choice == "3":
            _bulk_record(att_svc, course_svc, student_svc)
        elif choice == "4":
            _view_session(att_svc)
        elif choice == "5":
            _student_summary(att_svc, student_svc, course_svc)
        elif choice == "6":
            _course_report(att_svc, course_svc)
        elif choice == "7":
            _generate_registers(att_svc, auth)
        elif choice == "8":
            _pre_populate(att_svc)
        elif choice == "0":
            break


def _create_session(att_svc, course_svc, auth):
    print_header("Create Attendance Session")
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    date = input("  Date (YYYY-MM-DD, or Enter for today): ").strip() or None
    topic = input("  Topic (optional): ").strip() or None

    try:
        session = att_svc.create_session(
            course["id"], session_date=date, topic=topic,
            created_by=auth.current_user["username"],
        )
        print(f"\n  Session created (ID: {session['id']}) for {code} on {session['session_date']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_attendance(att_svc, student_svc):
    session_id = input("  Session ID: ").strip()
    try:
        session_id = int(session_id)
    except ValueError:
        print("\n  Invalid session ID.")
        return

    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    status = input("  Status (present/absent/late/excused) [present]: ").strip() or "present"

    try:
        att_svc.record_attendance(session_id, student["id"], status)
        print(f"\n  Attendance recorded: {sid} = {status}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _bulk_record(att_svc, course_svc, student_svc):
    print_header("Bulk Record Attendance")
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    sessions = att_svc.get_course_sessions(course["id"])
    if not sessions:
        print(f"\n  No sessions for {code}. Create one first.")
        return

    print("\n  Recent sessions:")
    for s in sessions[:5]:
        print(f"  ID: {s['id']} - {s['session_date']} ({s['topic'] or 'no topic'})")

    session_id = input("\n  Session ID: ").strip()
    try:
        session_id = int(session_id)
    except ValueError:
        print("\n  Invalid session ID.")
        return

    roster = course_svc.get_roster(course["id"])
    if not roster:
        print(f"\n  No students enrolled in {code}.")
        return

    records = []
    print("\n  Mark attendance (p=present, a=absent, l=late, e=excused):")
    status_map = {"p": "present", "a": "absent", "l": "late", "e": "excused"}

    for s in roster:
        status_key = input(f"  {s['student_id']} {s['first_name']} {s['last_name']} [p]: ").strip().lower() or "p"
        status = status_map.get(status_key, "present")
        records.append({"student_pk": s["id"], "status": status})

    try:
        count = att_svc.bulk_record_attendance(session_id, records)
        print(f"\n  Attendance recorded for {count} students.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_session(att_svc):
    session_id = input("  Session ID: ").strip()
    try:
        session_id = int(session_id)
    except ValueError:
        print("\n  Invalid session ID.")
        return

    session = att_svc.get_session(session_id)
    if not session:
        print("\n  Session not found.")
        return

    records = att_svc.get_session_records(session_id)
    print(f"\n  Session: {session['course_code']} - {session['session_date']}")
    if session["topic"]:
        print(f"  Topic: {session['topic']}")

    if not records:
        print("  No attendance records yet.")
        return

    for r in records:
        print(f"  {r['sid']} {r['first_name']} {r['last_name']}: {r['status']}")


def _student_summary(att_svc, student_svc, course_svc):
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

    summary = att_svc.get_attendance_summary(student["id"], course["id"])
    print(f"\n  Attendance Summary for {sid} in {code}:")
    print(f"  Total Sessions: {summary['total_sessions']}")
    print(f"  Present: {summary['present']}")
    print(f"  Absent: {summary['absent']}")
    print(f"  Late: {summary['late']}")
    print(f"  Excused: {summary['excused']}")
    print(f"  Attendance Rate: {summary['attendance_rate']}%")


def _course_report(att_svc, course_svc):
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    report = att_svc.get_course_attendance_report(course["id"])
    if not report:
        print(f"\n  No attendance data for {code}.")
        return

    print(f"\n  Attendance Report for {code}:")
    print(f"  {'Student':<12} {'Name':<25} {'Rate':<10} {'Present':<8} {'Absent':<8}")
    print(f"  {'-'*63}")
    for r in report:
        print(f"  {r['student_id']:<12} {r['name']:<25} {r['attendance_rate']:<10.1f} {r['present']:<8} {r['absent']:<8}")


def _generate_registers(att_svc, auth):
    print_header("Generate Registers for Date")
    target = input("  Date (YYYY-MM-DD, or Enter for today): ").strip()
    if not target:
        from datetime import date
        target = date.today().isoformat()

    created_by = None
    if auth and auth.current_user:
        created_by = auth.current_user.get("username")

    try:
        sessions = att_svc.generate_registers_for_date(target, created_by=created_by)
        print(f"\n  Generated {len(sessions)} register(s) for {target}.")
        for s in sessions:
            print(f"  Session {s['id']}: {s.get('course_code', '?')} - {s.get('topic', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _pre_populate(att_svc):
    print_header("Pre-populate Register")
    try:
        session_id = int(input("  Session ID: ").strip())
        count = att_svc.pre_populate_register(session_id)
        print(f"\n  Pre-populated {count} absent record(s).")
    except Exception as e:
        print(f"\n  Error: {e}")


def view_my_attendance(auth: UserAuth):
    """View attendance for the currently logged-in student."""
    att_svc = AttendanceService(auth._db_path)

    conn = att_svc._conn()
    try:
        student = conn.execute(
            "SELECT * FROM students WHERE user_id = ?",
            (auth.current_user["user_id"],),
        ).fetchone()
    finally:
        conn.close()

    if not student:
        print("\n  No student record linked to your account.")
        return

    records = att_svc.get_student_attendance(student["id"])
    if not records:
        print("\n  No attendance records found.")
        return

    print("\n  Your Attendance:")
    for r in records:
        print(f"  {r['session_date']} - {r['course_code']}: {r['status']}")
