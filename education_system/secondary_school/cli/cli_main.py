"""Main CLI entry point for the Secondary School Management System."""

import getpass
import sys
import logging

from education_system.secondary_school.infrastructure.auth.core import UserAuth
from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users, seed_default_staff
from education_system.secondary_school.core.paths import ensure_directories
from education_system.shared.cli.cli_helpers import (
    print_header, print_menu, get_choice, run_submenu as _run_submenu, login_prompt,
)

logger = logging.getLogger(__name__)


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


def _email_menu(auth):
    """Email sub-menu with cross-system messaging."""
    from education_system.shared.messaging import cross_system_cli
    db_path = getattr(auth, '_db_path', None)
    _run_submenu(auth, "Email", [
        ("1", "Local Email (use GUI for compose/inbox)",
         lambda a: print("\n  [Local email — use GUI for full features]")),
        ("2", "Cross-System Messages",
         lambda a: cross_system_cli.run(db_path=db_path, auth=a)),
    ])


def _admin_communication(auth):
    _run_submenu(auth, "Communication", [
        ("1", "Email", lambda a: _email_menu(a)),
        ("2", "Notifications", lambda a: print("\n  [Notifications module — use GUI for full features]")),
        ("3", "Announcements", lambda a: print("\n  [Announcements module — use GUI for full features]")),
        ("4", "Calendar", lambda a: print("\n  [Calendar module — use GUI for full features]")),
        ("5", "Communication Log", lambda a: print("\n  [Comms Log — use GUI for full features]")),
        ("6", "Parents Evening", lambda a: print("\n  [Parents Evening — use GUI for full features]")),
    ])


def _cross_system_tools(auth):
    """Cross-system shared tools available across all education systems."""
    db_path = getattr(auth, '_db_path', None)

    def _run_shared(module_path, label):
        """Lazily import and run a shared CLI module."""
        def handler(a):
            try:
                import importlib
                mod = importlib.import_module(module_path)
                mod.run(db_path=db_path, auth=a)
            except ImportError:
                print(f"\n  {label} module is not available.")
            except Exception as e:
                print(f"\n  Error running {label}: {e}")
        return handler

    _run_submenu(auth, "Cross-System Tools", [
        ("1", "Analytics Dashboard", _run_shared("education_system.shared.analytics.analytics_cli", "Analytics Dashboard")),
        ("2", "Outcome Tracking", _run_shared("education_system.shared.outcomes.outcomes_cli", "Outcome Tracking")),
        ("3", "Predictive Alerts", _run_shared("education_system.shared.predictive.predictive_cli", "Predictive Alerts")),
        ("4", "Bulk Transfer", _run_shared("education_system.shared.bulk_transfer.bulk_transfer_cli", "Bulk Transfer")),
        ("5", "Transfer Documents", _run_shared("education_system.shared.transfer_docs.transfer_docs_cli", "Transfer Documents")),
        ("6", "Reverse Lookup", _run_shared("education_system.shared.reverse_lookup.reverse_lookup_cli", "Reverse Lookup")),
        ("7", "Parent Continuity", _run_shared("education_system.shared.parent_continuity.parent_cli", "Parent Continuity")),
        ("8", "Cross-System Calendar", _run_shared("education_system.shared.calendar.calendar_cli", "Cross-System Calendar")),
        ("9", "Inter-System Messaging", _run_shared("education_system.shared.messaging.cross_system_cli", "Inter-System Messaging")),
        ("A", "Central Admin Portal", _run_shared("education_system.shared.admin_portal.admin_cli", "Central Admin Portal")),
        ("B", "GDPR Compliance", _run_shared("education_system.shared.gdpr.gdpr_cli", "GDPR Compliance")),
        ("C", "Shared Documents", _run_shared("education_system.shared.documents.document_cli", "Shared Documents")),
        ("D", "Student Self-Service", _run_shared("education_system.shared.student_portal.portal_cli", "Student Self-Service")),
        ("E", "Digital Transcript", _run_shared("education_system.shared.transcript.transcript_cli", "Digital Transcript")),
    ])


# ================================================================
# Role-based menus
# ================================================================

def _is_superadmin(auth):
    """Check if user is superadmin (admin in all 4 systems)."""
    cu = getattr(auth, 'current_user', None) or {}
    systems = cu.get('systems', []) if isinstance(cu, dict) else []
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    return admin_keys >= {"university", "college", "school", "primary"}


def _superadmin_switch_options(auth, this_system):
    """Return switch menu options and handler for superadmin users."""
    if not _is_superadmin(auth):
        return [], {}

    targets = [
        ("primary", "Primary School"),
        ("school", "Secondary School"),
        ("college", "Sixth Form College"),
        ("university", "University System"),
        ("__superadmin__", "Super Admin Dashboard"),
    ]
    options = []
    handler = {}
    idx = 1
    for key, label in targets:
        if key == this_system:
            continue
        opt_key = f"SW{idx}"
        options.append((opt_key, label))
        handler[opt_key] = key
        idx += 1
    return options, handler


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
            ("8", "Cross-System Tools"),
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        switch_opts, switch_map = _superadmin_switch_options(auth, "school")
        if switch_opts:
            options[-2:-2] = [("", "── Switch System ──")] + switch_opts
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
        elif choice == "8":
            _cross_system_tools(auth)
        elif choice == "M":
            from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice in switch_map:
            from education_system.switch import request_switch
            request_switch(switch_map[choice], "cli")
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
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        switch_opts, switch_map = _superadmin_switch_options(auth, "school")
        if switch_opts:
            options[-2:-2] = [("", "── Switch System ──")] + switch_opts
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _admin_academics(auth)
        elif choice == "2":
            _pastoral_menu(auth)
        elif choice == "3":
            _admin_communication(auth)
        elif choice == "M":
            from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice in switch_map:
            from education_system.switch import request_switch
            request_switch(switch_map[choice], "cli")
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
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        switch_opts, switch_map = _superadmin_switch_options(auth, "school")
        if switch_opts:
            options[-2:-2] = [("", "── Switch System ──")] + switch_opts
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            print("\n  [Grade viewing via student portal — use GUI for full features]")
        elif choice == "2":
            print("\n  [Attendance viewing via student portal — use GUI for full features]")
        elif choice == "M":
            from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("school", "gui")
            return "switch"
        elif choice in switch_map:
            from education_system.switch import request_switch
            request_switch(switch_map[choice], "cli")
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
        auth.change_password(auth.current_user["user_id"], old_pw, new_pw)
        print("\n  Password changed successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _show_dashboard_summary(role):
    """Print a brief role-specific dashboard summary."""
    print(f"\n  \u2500\u2500\u2500 Your Dashboard ({role.title()}) \u2500\u2500\u2500")
    if role in ("admin", "staff"):
        print("  Sections: Academics, Pastoral Care, Staff, Administration,")
        print("            Student Life, Facilities, Communication, Cross-System Tools")
    elif role in ("teacher", "instructor", "parent"):
        print("  Sections: Academics, Pastoral Care, Communication")
    else:
        print("  Sections: View My Grades, View My Attendance")


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
    seed_default_staff(db_path)

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

    _show_dashboard_summary(role)

    while True:
        result = None
        try:
            if role in ("admin", "staff"):
                result = admin_menu(auth)
            elif role in ("teacher", "instructor"):
                result = teacher_menu(auth)
            elif role == "parent":
                result = teacher_menu(auth)  # parent sees teacher-level
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
