"""Main CLI entry point for the Secondary School Management System."""

import getpass
import sys
import logging

from education_system.secondary_school.infrastructure.auth.core import UserAuth
from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.secondary_school.core.paths import ensure_directories

logger = logging.getLogger(__name__)


def clear_screen():
    print("\n" * 2)


def print_header(title: str):
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")


def print_menu(options: list[tuple[str, str]]):
    """Print a numbered menu. Options are (key, label) tuples."""
    for key, label in options:
        print(f"  [{key}] {label}")
    print()


def get_choice(prompt: str = "Select option: ") -> str:
    return input(prompt).strip()


def login_prompt(auth: UserAuth) -> bool:
    """Show login prompt. Returns True if login succeeds."""
    from education_system.shared.cli.login_cli import cli_login_prompt
    result = cli_login_prompt(auth)
    if result is None:
        return False
    user_info, _ = result
    display = user_info.get("display_name", user_info.get("username", "User"))
    print(f"\n  Welcome, {display}!")
    logger.info("CLI login: user '%s'", user_info["username"])
    return True


# ================================================================
# Sub-menu helper
# ================================================================

def _run_submenu(auth, title, items):
    """Generic sub-menu runner. items: list of (key, label, callable)."""
    while True:
        print_header(title)
        options = [(k, lbl) for k, lbl, _ in items]
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        matched = False
        for k, _, func in items:
            if choice == k:
                func(auth)
                matched = True
                break
        if not matched:
            print("\n  Invalid option. Please try again.")


# ================================================================
# Student management CLI functions
# ================================================================

def _students_menu(auth):
    from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
    svc = StudentService(auth._db_path)

    def list_students(_):
        students = svc.list_students(limit=50)
        if not students:
            print("\n  No students found.")
            return
        print(f"\n  {'ID':<10} {'Name':<25} {'Year':<5} {'Form':<8} {'Status':<10}")
        print(f"  {'-'*58}")
        for s in students:
            print(f"  {s['student_id']:<10} {s['first_name'] + ' ' + s['last_name']:<25} {s['year_group']:<5} {s.get('form_group') or '':<8} {s['status']:<10}")

    def add_student(_):
        print_header("Add New Student")
        first = input("  First name: ").strip()
        last = input("  Last name: ").strip()
        email = input("  Email (optional): ").strip() or None
        year = input("  Year group (7-11) [7]: ").strip() or "7"
        form = input("  Form group (optional): ").strip() or None
        try:
            student = svc.create_student(first_name=first, last_name=last, email=email,
                                         year_group=year, form_group=form)
            print(f"\n  Student created: {student['student_id']} - {student['first_name']} {student['last_name']}")
        except Exception as e:
            print(f"\n  Error: {e}")

    def search_students(_):
        term = input("  Search: ").strip()
        students = svc.list_students(search=term)
        if not students:
            print("\n  No matching students.")
            return
        for s in students:
            print(f"  {s['student_id']} - {s['first_name']} {s['last_name']} (Year {s['year_group']})")

    def view_student(_):
        sid = input("  Student ID (e.g., SEC0001): ").strip()
        student = svc.get_student_by_student_id(sid.upper())
        if not student:
            print("\n  Student not found.")
            return
        print(f"\n  ID: {student['student_id']}")
        print(f"  Name: {student['first_name']} {student['last_name']}")
        print(f"  Year Group: {student['year_group']}  Key Stage: {student['key_stage']}")
        print(f"  Form Group: {student.get('form_group', 'N/A')}")
        print(f"  Email: {student.get('email', 'N/A')}")
        print(f"  SEN Status: {student.get('sen_status', 'none')}")
        print(f"  Pupil Premium: {'Yes' if student.get('pupil_premium') else 'No'}")
        print(f"  Status: {student['status']}")

    _run_submenu(auth, "Students", [
        ("1", "List All Students", list_students),
        ("2", "Add New Student", add_student),
        ("3", "Search Students", search_students),
        ("4", "View Student Details", view_student),
    ])


# ================================================================
# Subjects management CLI functions
# ================================================================

def _subjects_menu(auth):
    from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
    svc = SubjectService(auth._db_path)

    def list_subjects(_):
        subjects = svc.list_subjects()
        if not subjects:
            print("\n  No subjects found.")
            return
        print(f"\n  {'Code':<10} {'Title':<25} {'Dept':<15} {'KS':<5} {'Core':<5}")
        print(f"  {'-'*60}")
        for s in subjects:
            core = "Yes" if s.get("is_core") else "No"
            print(f"  {s['subject_code']:<10} {s['title']:<25} {s.get('department') or '':<15} {s['key_stage']:<5} {core:<5}")

    def add_subject(_):
        print_header("Add New Subject")
        code = input("  Subject code: ").strip()
        title = input("  Title: ").strip()
        dept = input("  Department (optional): ").strip() or None
        ks = input("  Key stage (KS3/KS4) [KS3]: ").strip() or "KS3"
        core = input("  Core subject? (y/n) [n]: ").strip().lower() == "y"
        try:
            subject = svc.create_subject(subject_code=code, title=title, department=dept,
                                          key_stage=ks, is_core=core)
            print(f"\n  Subject created: {subject['subject_code']} - {subject['title']}")
        except Exception as e:
            print(f"\n  Error: {e}")

    _run_submenu(auth, "Subjects", [
        ("1", "List All Subjects", list_subjects),
        ("2", "Add New Subject", add_subject),
    ])


# ================================================================
# Enrollment CLI
# ================================================================

def _enrollment_menu(auth):
    from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService
    from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
    svc = EnrollmentService(auth._db_path)
    stu_svc = StudentService(auth._db_path)

    def enroll(_):
        sid = input("  Student PK (numeric): ").strip()
        subj = input("  Subject PK (numeric): ").strip()
        try:
            e = svc.enroll_student(int(sid), int(subj))
            print(f"\n  Enrolled successfully (enrollment #{e['id']}).")
        except Exception as e:
            print(f"\n  Error: {e}")

    def view_enrollments(_):
        sid = input("  Student PK (numeric): ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        enrollments = svc.get_student_enrollments(student_id)
        if not enrollments:
            print("\n  No enrollments found.")
            return
        for e in enrollments:
            print(f"  {e['subject_code']} - {e['title']} (Teacher: {e.get('teacher', 'TBC')})")

    def drop(_):
        sid = input("  Student PK: ").strip()
        subj = input("  Subject PK: ").strip()
        try:
            svc.drop_enrollment(int(sid), int(subj))
            print("\n  Enrollment dropped.")
        except Exception as e:
            print(f"\n  Error: {e}")

    _run_submenu(auth, "Enrollment", [
        ("1", "Enroll Student in Subject", enroll),
        ("2", "View Student Enrollments", view_enrollments),
        ("3", "Drop Enrollment", drop),
    ])


# ================================================================
# Grades CLI
# ================================================================

def _grades_menu(auth):
    from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService
    svc = GradeService(auth._db_path)

    def add_grade(_):
        sid = input("  Student PK: ").strip()
        subj = input("  Subject PK: ").strip()
        atype = input("  Assessment type (classwork/test/homework/mock_exam/coursework/end_of_term) [classwork]: ").strip() or "classwork"
        aname = input("  Assessment name (optional): ").strip() or None
        score = input("  Score (numeric, optional): ").strip()
        grade = input("  Grade (9-1 or U, optional): ").strip() or None
        term = input("  Term (Autumn/Spring/Summer, optional): ").strip() or None
        try:
            g = svc.add_grade(
                student_id=int(sid), subject_id=int(subj),
                assessment_type=atype, assessment_name=aname,
                score=float(score) if score else None, grade=grade, term=term,
            )
            print(f"\n  Grade recorded (#{g['id']}): score={g.get('score')}, grade={g.get('grade')}")
        except Exception as e:
            print(f"\n  Error: {e}")

    def view_grades(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        grades = svc.get_student_grades(student_id)
        if not grades:
            print("\n  No grades found.")
            return
        print(f"\n  {'Subject':<10} {'Assessment':<20} {'Score':<8} {'Grade':<6} {'Term':<8}")
        print(f"  {'-'*52}")
        for g in grades:
            print(f"  {g.get('subject_code', ''):<10} {g.get('assessment_name') or g.get('assessment_type', ''):<20} {str(g.get('score', '')):<8} {g.get('grade') or '':<6} {g.get('term') or '':<8}")

    def view_average(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        avg = svc.get_student_average(student_id)
        if avg is None:
            print("\n  No scored grades yet.")
        else:
            print(f"\n  Average score: {avg:.1f}")

    _run_submenu(auth, "Grades", [
        ("1", "Add Grade", add_grade),
        ("2", "View Student Grades", view_grades),
        ("3", "View Student Average", view_average),
    ])


# ================================================================
# Attendance CLI
# ================================================================

def _attendance_menu(auth):
    from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService
    svc = AttendanceService(auth._db_path)

    def record(_):
        sid = input("  Student PK: ").strip()
        date_str = input("  Date (YYYY-MM-DD): ").strip()
        status = input("  Status (present/absent/late/authorised_absent/unauthorised_absent) [present]: ").strip() or "present"
        period = input("  Period (e.g., AM/PM/1-6) [AM]: ").strip() or "AM"
        try:
            r = svc.record_attendance(int(sid), date_str, status, period=period)
            print(f"\n  Attendance recorded: {r['status']} on {r['date']}")
        except Exception as e:
            print(f"\n  Error: {e}")

    def view_student(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        records = svc.get_student_attendance(student_id)
        if not records:
            print("\n  No attendance records.")
            return
        for r in records[:20]:
            print(f"  {r['date']}  {r.get('period', ''):<5}  {r['status']}")

    def view_summary(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        s = svc.get_attendance_summary(student_id)
        print(f"\n  Total: {s['total']}  Present: {s['present']}  Absent: {s['absent']}  Late: {s['late']}")
        print(f"  Attendance Rate: {s['percentage']}%")

    def year_comparison(_):
        comparison = svc.compare_year_groups()
        if not comparison:
            print("\n  No attendance data.")
            return
        print(f"\n  {'Year':<8} {'Total':<10} {'Attended':<10} {'Rate':<8}")
        print(f"  {'-'*36}")
        for c in comparison:
            print(f"  {c['year_group']:<8} {c['total']:<10} {c['attended']:<10} {c['percentage']}%")

    def below_threshold(_):
        year = input("  Year group: ").strip()
        threshold_str = input("  Threshold % [90]: ").strip()
        try:
            threshold = float(threshold_str) if threshold_str else 90.0
        except ValueError:
            print("\n  Invalid threshold. Please enter a number.")
            return
        students = svc.get_students_below_threshold(year, threshold)
        if not students:
            print(f"\n  All students above {threshold}%.")
            return
        for s in students:
            print(f"  {s['student_id']} {s['first_name']} {s['last_name']} - {s['percentage']}%")

    _run_submenu(auth, "Attendance", [
        ("1", "Record Attendance", record),
        ("2", "View Student Attendance", view_student),
        ("3", "View Student Summary", view_summary),
        ("4", "Year Group Comparison", year_comparison),
        ("5", "Students Below Threshold", below_threshold),
    ])


# ================================================================
# Behaviour CLI
# ================================================================

def _behaviour_menu(auth):
    from education_system.secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService
    svc = BehaviourService(auth._db_path)

    def add_record(_):
        sid = input("  Student PK: ").strip()
        rtype = input("  Type (positive/negative) [negative]: ").strip() or "negative"
        category = input("  Category (e.g., disruption, effort, homework): ").strip()
        desc = input("  Description (optional): ").strip() or None
        points = input("  Points [0]: ").strip()
        try:
            r = svc.add_record(int(sid), rtype, category, desc, int(points) if points else 0)
            print(f"\n  Behaviour recorded (#{r['id']}): {rtype} - {category}")
        except Exception as e:
            print(f"\n  Error: {e}")

    def view_records(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        records = svc.get_student_records(student_id)
        if not records:
            print("\n  No behaviour records.")
            return
        for r in records[:20]:
            print(f"  {r.get('incident_date', '')}  [{r['type']}]  {r['category']}  pts={r.get('points', 0)}")

    def view_points(_):
        sid = input("  Student PK: ").strip()
        try:
            student_id = int(sid)
        except ValueError:
            print("\n  Invalid student PK. Please enter a number.")
            return
        pts = svc.get_student_points(student_id)
        print(f"\n  Positive: {pts.get('positive', 0)}  Negative: {pts.get('negative', 0)}  Net: {pts.get('net', 0)}")

    _run_submenu(auth, "Behaviour", [
        ("1", "Add Behaviour Record", add_record),
        ("2", "View Student Records", view_records),
        ("3", "View Student Points", view_points),
    ])


# ================================================================
# Pastoral sub-menu stubs (link to existing services where available)
# ================================================================

def _pastoral_menu(auth):
    _run_submenu(auth, "Pastoral Care", [
        ("1", "Behaviour", lambda a: _behaviour_menu(a)),
        ("2", "Detentions", lambda a: print("\n  [Detentions module — use GUI for full features]")),
        ("3", "Exclusions", lambda a: print("\n  [Exclusions module — use GUI for full features]")),
        ("4", "Rewards", lambda a: print("\n  [Rewards module — use GUI for full features]")),
        ("5", "Safeguarding", lambda a: print("\n  [Safeguarding module — use GUI for full features]")),
        ("6", "SEND", lambda a: print("\n  [SEND module — use GUI for full features]")),
    ])


# ================================================================
# Admin sub-menus
# ================================================================

def _admin_academics(auth):
    _run_submenu(auth, "Academics", [
        ("1", "Students", lambda a: _students_menu(a)),
        ("2", "Subjects", lambda a: _subjects_menu(a)),
        ("3", "Enrollment", lambda a: _enrollment_menu(a)),
        ("4", "Grades", lambda a: _grades_menu(a)),
        ("5", "Attendance", lambda a: _attendance_menu(a)),
        ("6", "Timetable", lambda a: print("\n  [Timetable module — use GUI for full features]")),
        ("7", "Homework", lambda a: print("\n  [Homework module — use GUI for full features]")),
        ("8", "Exams", lambda a: print("\n  [Exams module — use GUI for full features]")),
        ("9", "Progress Tracking", lambda a: print("\n  [Progress module — use GUI for full features]")),
        ("A", "Reports", lambda a: print("\n  [Reports module — use GUI for full features]")),
    ])


def _admin_staff(auth):
    _run_submenu(auth, "Staff", [
        ("1", "Staff HR", lambda a: print("\n  [HR module — use GUI for full features]")),
        ("2", "CPD Records", lambda a: print("\n  [CPD module — use GUI for full features]")),
        ("3", "Cover/Supply", lambda a: print("\n  [Cover module — use GUI for full features]")),
        ("4", "Staff Directory", lambda a: print("\n  [Directory — use GUI for full features]")),
    ])


def _admin_administration(auth):
    _run_submenu(auth, "Administration", [
        ("1", "User Management", lambda a: print("\n  [Users module — use GUI for full features]")),
        ("2", "Settings", lambda a: print("\n  [Settings module — use GUI for full features]")),
        ("3", "Admissions", lambda a: print("\n  [Admissions module — use GUI for full features]")),
        ("4", "Finance", lambda a: print("\n  [Finance module — use GUI for full features]")),
        ("5", "Data Export", lambda a: print("\n  [Data Export module — use GUI for full features]")),
        ("6", "Audit Log", lambda a: print("\n  [Audit module — use GUI for full features]")),
        ("7", "Policies", lambda a: print("\n  [Policies module — use GUI for full features]")),
        ("8", "Documents", lambda a: print("\n  [Documents module — use GUI for full features]")),
    ])


def _admin_student_life(auth):
    _run_submenu(auth, "Student Life", [
        ("1", "Clubs", lambda a: print("\n  [Clubs module — use GUI for full features]")),
        ("2", "Meals", lambda a: print("\n  [Meals module — use GUI for full features]")),
        ("3", "Transport", lambda a: print("\n  [Transport module — use GUI for full features]")),
        ("4", "Trips & Visits", lambda a: print("\n  [Trips module — use GUI for full features]")),
        ("5", "Careers", lambda a: print("\n  [Careers module — use GUI for full features]")),
        ("6", "Library", lambda a: print("\n  [Library module — use GUI for full features]")),
        ("7", "Medical/First Aid", lambda a: print("\n  [Medical module — use GUI for full features]")),
    ])


def _admin_facilities(auth):
    _run_submenu(auth, "Facilities", [
        ("1", "Room Booking", lambda a: print("\n  [Room Booking module — use GUI for full features]")),
        ("2", "Assets", lambda a: print("\n  [Assets module — use GUI for full features]")),
        ("3", "Seating Plans", lambda a: print("\n  [Seating Plans — use GUI for full features]")),
        ("4", "Visitors", lambda a: print("\n  [Visitors module — use GUI for full features]")),
        ("5", "Incidents", lambda a: print("\n  [Incidents module — use GUI for full features]")),
    ])


def _admin_communication(auth):
    _run_submenu(auth, "Communication", [
        ("1", "Email/Messages", lambda a: print("\n  [Email module — use GUI for full features]")),
        ("2", "Notifications", lambda a: print("\n  [Notifications module — use GUI for full features]")),
        ("3", "Announcements", lambda a: print("\n  [Announcements module — use GUI for full features]")),
        ("4", "Calendar", lambda a: print("\n  [Calendar module — use GUI for full features]")),
        ("5", "Communication Log", lambda a: print("\n  [Comms Log — use GUI for full features]")),
        ("6", "Parents Evening", lambda a: print("\n  [Parents Evening — use GUI for full features]")),
    ])


# ================================================================
# Role-based menus
# ================================================================

def _switch_system_menu():
    """Show switch system sub-menu. Returns (system, mode) or None."""
    print_header("Switch System")
    options = [
        ("1", "Sixth Form College System"),
        ("2", "University Management System"),
        ("3", "Primary School System"),
        ("0", "Back"),
    ]
    print_menu(options)
    choice = get_choice()
    mapping = {"1": "college", "2": "university", "3": "primary"}
    if choice in mapping:
        return mapping[choice]
    return None


def admin_menu(auth: UserAuth):
    """Admin/SLT menu with categorized sub-menus."""
    while True:
        print_header("Secondary School - Admin")
        options = [
            ("1", "Academics"),
            ("2", "Pastoral Care"),
            ("3", "Staff"),
            ("4", "Administration"),
            ("5", "Student Life"),
            ("6", "Facilities"),
            ("7", "Communication"),
            ("P", "Change Password"),
            ("G", "Switch to GUI"),
            ("S", "Switch System"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _admin_academics(auth)
        elif choice == "2":
            _pastoral_menu(auth)
        elif choice == "3":
            _admin_staff(auth)
        elif choice == "4":
            _admin_administration(auth)
        elif choice == "5":
            _admin_student_life(auth)
        elif choice == "6":
            _admin_facilities(auth)
        elif choice == "7":
            _admin_communication(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice == "S":
            target = _switch_system_menu()
            if target:
                from education_system.switch import request_switch
                request_switch(target, "cli")
                return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def teacher_menu(auth: UserAuth):
    """Teacher-specific menu."""
    while True:
        print_header("Secondary School - Teacher")
        options = [
            ("1", "Academics"),
            ("2", "Pastoral Care"),
            ("3", "Communication"),
            ("P", "Change Password"),
            ("G", "Switch to GUI"),
            ("S", "Switch System"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _admin_academics(auth)
        elif choice == "2":
            _pastoral_menu(auth)
        elif choice == "3":
            _admin_communication(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice == "S":
            target = _switch_system_menu()
            if target:
                from education_system.switch import request_switch
                request_switch(target, "cli")
                return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def student_menu_main(auth: UserAuth):
    """Student-specific menu (read-only views)."""
    from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService
    from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService

    while True:
        print_header("Secondary School - Student")
        options = [
            ("1", "View My Grades"),
            ("2", "View My Attendance"),
            ("P", "Change Password"),
            ("G", "Switch to GUI"),
            ("S", "Switch System"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            print("\n  [Grade viewing via student portal — use GUI for full features]")
        elif choice == "2":
            print("\n  [Attendance viewing via student portal — use GUI for full features]")
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice == "S":
            target = _switch_system_menu()
            if target:
                from education_system.switch import request_switch
                request_switch(target, "cli")
                return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def change_password_prompt(auth: UserAuth):
    """Prompt user to change their password."""
    print_header("Change Password")
    old_pw = getpass.getpass("Current password: ")
    new_pw = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_pw != confirm:
        print("\n  Passwords do not match.")
        return

    try:
        auth.change_password(auth.current_user["id"], old_pw, new_pw)
        print("\n  Password changed successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")


def main(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Main CLI entry point.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    ensure_directories()

    from education_system.secondary_school.core.logs import setup_logging
    setup_logging()

    # Initialize database
    initialise_database(db_path)
    seed_default_users(db_path)

    auth = UserAuth()

    if user_info and role and shared_auth:
        # Pre-authenticated via universal CLI login
        auth = shared_auth
        display = user_info.get("display_name", user_info.get("username", "User"))
        auth._current_user = {
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "display_name": display,
            "email": user_info.get("email"),
            "role": role,
            "systems": user_info.get("systems", []),
        }
        print(f"\n  Welcome, {display}! (Role: {role})")
    else:
        if not login_prompt(auth):
            sys.exit(1)

        # Determine role for the school system
        role = "student"
        for s in auth.current_user.get("systems", []):
            if s["system_key"] == "school":
                role = s["role"]
                break
        auth._current_user["role"] = role

    while True:
        result = None
        try:
            if role == "admin":
                result = admin_menu(auth)
            elif role == "teacher":
                result = teacher_menu(auth)
            else:
                result = student_menu_main(auth)
        except Exception:
            logger.exception("Menu error")

        if result == "switch":
            break
        elif result == "logout":
            # Signal back to run.py for universal login (system selection)
            auth.logout()
            from education_system.switch import request_logout
            request_logout(mode="cli")
            break
        else:
            # Normal exit (choice "0")
            auth.logout()
            logger.info("CLI session ended")
            print("\n  Goodbye!")
            break
