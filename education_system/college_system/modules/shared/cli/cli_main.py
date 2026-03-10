"""Main CLI entry point with login and role-based menu."""

import getpass
import sys

from education_system.college_system.core.i18n import t, load_locale
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data
from education_system.college_system.core.paths import ensure_directories
import logging

logger = logging.getLogger(__name__)


def clear_screen():
    print("\n" * 2)


def print_header(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


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
# Sub-menu helper functions
# ================================================================

def _run_submenu(auth, title, items):
    """Generic sub-menu runner. items: list of (key, label, callable_or_func)."""
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
            print(f"\n  {t('menu.invalid_option')}")


# ================================================================
# Admin sub-menus
# ================================================================

def _admin_teaching_learning(auth):
    from education_system.college_system.modules.domain.courses.cli.course_cli import course_menu
    from education_system.college_system.modules.domain.assignments.cli.assignment_cli import assignment_menu
    from education_system.college_system.modules.domain.markbook.cli.markbook_cli import markbook_menu
    from education_system.college_system.modules.domain.lesson_plans.cli.lesson_plans_cli import lesson_plans_menu
    from education_system.college_system.modules.domain.intervention_tracking.cli.intervention_tracking_cli import intervention_tracking_menu
    from education_system.college_system.modules.domain.ilp.cli.ilp_cli import ilp_menu
    from education_system.college_system.modules.domain.value_added.cli.value_added_cli import value_added_menu
    from education_system.college_system.modules.domain.early_warning.cli.early_warning_cli import early_warning_menu
    from education_system.college_system.modules.domain.internal_verification.cli.internal_verification_cli import internal_verification_menu
    from education_system.college_system.modules.domain.baseline_assessment.cli.baseline_assessment_cli import baseline_assessment_menu
    _run_submenu(auth, "Teaching & Learning", [
        ("1", "Courses", lambda a: course_menu(a)),
        ("2", "Assignments", lambda a: assignment_menu(a)),
        ("3", "Markbook", lambda a: markbook_menu(a)),
        ("4", "Lesson Plans", lambda a: lesson_plans_menu(a)),
        ("5", "Interventions", lambda a: intervention_tracking_menu(a)),
        ("6", "ILP", lambda a: ilp_menu(a)),
        ("7", "Value-Added Analysis", lambda a: value_added_menu(a)),
        ("8", "Early Warning", lambda a: early_warning_menu(a)),
        ("9", "Internal Verification", lambda a: internal_verification_menu(a)),
        ("A", "Baseline Assessment", lambda a: baseline_assessment_menu(a)),
    ])


def _admin_students_pastoral(auth):
    from education_system.college_system.modules.domain.students.cli.student_cli import student_menu
    from education_system.college_system.modules.domain.enrollment.cli.enrollment_cli import enrollment_menu
    from education_system.college_system.modules.domain.behaviour.cli.behaviour_cli import behaviour_menu
    from education_system.college_system.modules.domain.pastoral.cli.pastoral_cli import pastoral_menu
    from education_system.college_system.modules.domain.send.cli.send_cli import send_menu
    from education_system.college_system.modules.domain.safeguarding.cli.safeguarding_cli import safeguarding_menu
    from education_system.college_system.modules.domain.student_support.cli.student_support_cli import student_support_menu
    from education_system.college_system.modules.domain.peer_mentoring.cli.peer_mentoring_cli import peer_mentoring_menu
    from education_system.college_system.modules.domain.tutorial.cli.tutorial_cli import tutorial_menu
    from education_system.college_system.modules.domain.student_wellbeing.cli.student_wellbeing_cli import student_wellbeing_menu
    _run_submenu(auth, "Students & Pastoral", [
        ("1", "Students", lambda a: student_menu(a)),
        ("2", "Enrollment", lambda a: enrollment_menu(a)),
        ("3", "Behaviour", lambda a: behaviour_menu(a)),
        ("4", "Pastoral", lambda a: pastoral_menu(a)),
        ("5", "SEND/ALS", lambda a: send_menu(a)),
        ("6", "Safeguarding", lambda a: safeguarding_menu(a)),
        ("7", "Student Support", lambda a: student_support_menu(a)),
        ("8", "Peer Mentoring", lambda a: peer_mentoring_menu(a)),
        ("9", "Tutorial System", lambda a: tutorial_menu(a)),
        ("A", "Student Wellbeing", lambda a: student_wellbeing_menu(a)),
    ])


def _admin_attendance_timetable(auth):
    from education_system.college_system.modules.domain.attendance.cli.attendance_cli import attendance_menu
    from education_system.college_system.modules.domain.timetable.cli.timetable_cli import timetable_menu
    from education_system.college_system.modules.domain.cover.cli.cover_cli import cover_menu
    from education_system.college_system.modules.domain.absence_requests.cli.absence_requests_cli import absence_requests_menu
    _run_submenu(auth, "Attendance & Timetable", [
        ("1", "Attendance", lambda a: attendance_menu(a)),
        ("2", "Timetable", lambda a: timetable_menu(a)),
        ("3", "Cover/Substitution", lambda a: cover_menu(a)),
        ("4", "Absence Requests", lambda a: absence_requests_menu(a)),
    ])


def _admin_exams_assessment(auth):
    from education_system.college_system.modules.domain.grades.cli.grade_cli import grade_menu
    from education_system.college_system.modules.domain.exams.cli.exams_cli import exams_menu
    from education_system.college_system.modules.domain.tlevel.cli.tlevel_cli import tlevel_menu
    from education_system.college_system.modules.domain.apprenticeships.cli.apprenticeships_cli import apprenticeship_menu
    from education_system.college_system.modules.domain.functional_skills.cli.functional_skills_cli import functional_skills_menu
    from education_system.college_system.modules.domain.study_programmes.cli.study_programmes_cli import study_programmes_menu
    _run_submenu(auth, "Exams & Assessment", [
        ("1", "Grades", lambda a: grade_menu(a)),
        ("2", "Exams", lambda a: exams_menu(a)),
        ("3", "T-Levels", lambda a: tlevel_menu(a)),
        ("4", "Apprenticeships", lambda a: apprenticeship_menu(a)),
        ("5", "Functional Skills & GCSE Resits", lambda a: functional_skills_menu(a)),
        ("6", "Study Programmes", lambda a: study_programmes_menu(a)),
    ])


def _admin_staff_hr(auth):
    from education_system.college_system.modules.domain.staff_hr.cli.staff_hr_cli import staff_hr_menu
    from education_system.college_system.modules.domain.cpd.cli.cpd_cli import cpd_menu
    from education_system.college_system.modules.domain.observations.cli.observations_cli import observations_menu
    from education_system.college_system.modules.domain.appraisals.cli.appraisals_cli import appraisals_menu
    from education_system.college_system.modules.domain.staff_wellbeing.cli.staff_wellbeing_cli import staff_wellbeing_menu
    from education_system.college_system.modules.domain.staff_absence.cli.staff_absence_cli import staff_absence_menu
    from education_system.college_system.modules.domain.recruitment.cli.recruitment_cli import recruitment_menu
    from education_system.college_system.modules.domain.dbs_checks.cli.dbs_checks_cli import dbs_checks_menu
    from education_system.college_system.modules.domain.onboarding.cli.onboarding_cli import onboarding_menu
    from education_system.college_system.modules.domain.expense_claims.cli.expense_claims_cli import expense_claims_menu
    _run_submenu(auth, "Staff & HR", [
        ("1", "Staff HR", lambda a: staff_hr_menu(a)),
        ("2", "CPD Records", lambda a: cpd_menu(a)),
        ("3", "Observations", lambda a: observations_menu(a)),
        ("4", "Appraisals", lambda a: appraisals_menu(a)),
        ("5", "Staff Wellbeing", lambda a: staff_wellbeing_menu(a)),
        ("6", "Staff Absence", lambda a: staff_absence_menu(a)),
        ("7", "Recruitment", lambda a: recruitment_menu(a)),
        ("8", "DBS Checks", lambda a: dbs_checks_menu(a)),
        ("9", "Onboarding & Probation", lambda a: onboarding_menu(a)),
        ("A", "Expense Claims", lambda a: expense_claims_menu(a)),
    ])


def _admin_administration(auth):
    from education_system.college_system.modules.domain.admissions.cli.admissions_cli import admissions_menu
    from education_system.college_system.modules.domain.visitors.cli.visitors_cli import visitors_menu
    from education_system.college_system.modules.domain.policies.cli.policies_cli import policies_menu
    from education_system.college_system.modules.domain.gdpr.cli.gdpr_cli import gdpr_menu
    from education_system.college_system.modules.domain.bulk_operations.cli.bulk_operations_cli import bulk_operations_menu
    from education_system.college_system.modules.domain.emergency.cli.emergency_cli import emergency_menu
    from education_system.college_system.modules.domain.academic_year.cli.academic_year_cli import academic_year_menu
    from education_system.college_system.modules.domain.user_management.cli.user_management_cli import user_management_menu
    from education_system.college_system.modules.domain.complaints.cli.complaints_cli import complaints_menu
    from education_system.college_system.modules.domain.equality_diversity.cli.equality_diversity_cli import equality_diversity_menu
    from education_system.college_system.modules.domain.prevent_duty.cli.prevent_duty_cli import prevent_duty_menu
    from education_system.college_system.modules.domain.risk_management.cli.risk_management_cli import risk_management_menu
    from education_system.college_system.modules.domain.marketing.cli.marketing_cli import marketing_menu
    from education_system.college_system.modules.domain.disciplinary.cli.disciplinary_cli import disciplinary_menu
    from education_system.college_system.modules.domain.letter_templates.cli.letter_templates_cli import letter_templates_menu
    from education_system.college_system.modules.domain.health_safety.cli.health_safety_cli import health_safety_menu
    from education_system.college_system.modules.domain.lettings.cli.lettings_cli import lettings_menu
    _run_submenu(auth, "Administration", [
        ("1", "Admissions", lambda a: admissions_menu(a)),
        ("2", "Visitors", lambda a: visitors_menu(a)),
        ("3", "Policies", lambda a: policies_menu(a)),
        ("4", "GDPR & Data Protection", lambda a: gdpr_menu(a)),
        ("5", "Bulk Operations", lambda a: bulk_operations_menu(a)),
        ("6", "Emergency Management", lambda a: emergency_menu(a)),
        ("7", "Academic Year", lambda a: academic_year_menu(a)),
        ("8", "User Management", lambda a: user_management_menu(a)),
        ("9", "Complaints", lambda a: complaints_menu(a)),
        ("A", "Equality & Diversity", lambda a: equality_diversity_menu(a)),
        ("B", "Prevent Duty", lambda a: prevent_duty_menu(a)),
        ("C", "Risk Management", lambda a: risk_management_menu(a)),
        ("D", "Marketing & Open Days", lambda a: marketing_menu(a)),
        ("E", "Disciplinary & Appeals", lambda a: disciplinary_menu(a)),
        ("F", "Letter Templates", lambda a: letter_templates_menu(a)),
        ("G", "Health & Safety", lambda a: health_safety_menu(a)),
        ("H", "Facility Lettings", lambda a: lettings_menu(a)),
    ])


def _admin_finance_funding(auth):
    from education_system.college_system.modules.domain.finance.cli.finance_cli import finance_menu
    from education_system.college_system.modules.domain.funding.cli.funding_cli import funding_menu
    from education_system.college_system.modules.domain.bursary.cli.bursary_cli import bursary_menu
    from education_system.college_system.modules.domain.meal_ordering.cli.meal_ordering_cli import meal_ordering_menu
    from education_system.college_system.modules.domain.print_credits.cli.print_credits_cli import print_credits_menu
    _run_submenu(auth, "Finance & Funding", [
        ("1", "Finance", lambda a: finance_menu(a)),
        ("2", "Funding & ILR", lambda a: funding_menu(a)),
        ("3", "Bursary", lambda a: bursary_menu(a)),
        ("4", "Meal Ordering", lambda a: meal_ordering_menu(a)),
        ("5", "Print Credits", lambda a: print_credits_menu(a)),
    ])


def _admin_communication(auth):
    from education_system.college_system.modules.domain.notifications.cli.notification_cli import notification_menu
    from education_system.college_system.modules.domain.messaging.cli.message_cli import messaging_menu
    from education_system.college_system.modules.domain.announcements.cli.announcements_cli import announcements_menu
    from education_system.college_system.modules.domain.surveys.cli.surveys_cli import surveys_menu
    from education_system.college_system.modules.domain.feedback.cli.feedback_cli import feedback_menu
    from education_system.college_system.modules.domain.activity_feed.cli.activity_feed_cli import activity_feed_menu
    from education_system.college_system.modules.domain.sms_email.cli.sms_email_cli import sms_email_menu
    _run_submenu(auth, "Communication", [
        ("1", "Notifications", lambda a: notification_menu(a)),
        ("2", "Messages", lambda a: messaging_menu(a)),
        ("3", "Announcements", lambda a: announcements_menu(a)),
        ("4", "Surveys", lambda a: surveys_menu(a)),
        ("5", "Feedback", lambda a: feedback_menu(a)),
        ("6", "Activity Feed", lambda a: activity_feed_menu(a)),
        ("7", "SMS & Email", lambda a: sms_email_menu(a)),
    ])


def _admin_facilities(auth):
    from education_system.college_system.modules.domain.assets.cli.assets_cli import assets_menu
    from education_system.college_system.modules.domain.transport.cli.transport_cli import transport_menu
    from education_system.college_system.modules.domain.resource_booking.cli.resource_booking_cli import resource_booking_menu
    from education_system.college_system.modules.domain.first_aid.cli.first_aid_cli import first_aid_menu
    _run_submenu(auth, "Facilities & Resources", [
        ("1", "Assets", lambda a: assets_menu(a)),
        ("2", "Transport", lambda a: transport_menu(a)),
        ("3", "Resource Booking", lambda a: resource_booking_menu(a)),
        ("4", "First Aid", lambda a: first_aid_menu(a)),
    ])


def _admin_analytics(auth):
    from education_system.college_system.modules.domain.reports.cli.reports_cli import reports_menu
    from education_system.college_system.modules.domain.compliance.cli.compliance_cli import compliance_menu
    from education_system.college_system.modules.domain.data_dashboard.cli.data_dashboard_cli import data_dashboard_menu
    from education_system.college_system.modules.domain.quality_assurance.cli.quality_assurance_cli import quality_assurance_menu
    from education_system.college_system.modules.domain.kpi_dashboard.cli.kpi_dashboard_cli import kpi_dashboard_menu
    from education_system.college_system.modules.domain.audit_reports.cli.audit_reports_cli import audit_reports_menu
    from education_system.college_system.modules.domain.self_assessment.cli.self_assessment_cli import self_assessment_menu
    from education_system.college_system.modules.domain.governance.cli.governance_cli import governance_menu
    from education_system.college_system.modules.domain.data_export.cli.data_export_cli import data_export_menu
    _run_submenu(auth, "Analytics & Reports", [
        ("1", "Reports", lambda a: reports_menu(a)),
        ("2", "Compliance", lambda a: compliance_menu(a)),
        ("3", "Data Dashboard", lambda a: data_dashboard_menu(a)),
        ("4", "Quality Assurance", lambda a: quality_assurance_menu(a)),
        ("5", "KPI Dashboard", lambda a: kpi_dashboard_menu(a)),
        ("6", "Audit Reports", lambda a: audit_reports_menu(a)),
        ("7", "Self-Assessment & Ofsted", lambda a: self_assessment_menu(a)),
        ("8", "Governance & Board", lambda a: governance_menu(a)),
        ("9", "Data Export & ILR", lambda a: data_export_menu(a)),
    ])


def _admin_parent_careers(auth):
    from education_system.college_system.modules.domain.parent_portal.cli.parent_cli import parent_menu
    from education_system.college_system.modules.domain.parents_evening.cli.parents_evening_cli import parents_evening_menu
    from education_system.college_system.modules.domain.careers.cli.careers_cli import careers_menu
    from education_system.college_system.modules.domain.destinations.cli.destinations_cli import destinations_menu
    from education_system.college_system.modules.domain.work_journal.cli.work_journal_cli import work_journal_menu
    from education_system.college_system.modules.domain.ucas.cli.ucas_cli import ucas_menu
    from education_system.college_system.modules.domain.alumni.cli.alumni_cli import alumni_menu
    _run_submenu(auth, "Parent & Careers", [
        ("1", "Parent Portal", lambda a: parent_menu(a)),
        ("2", "Parents Evening", lambda a: parents_evening_menu(a)),
        ("3", "Careers", lambda a: careers_menu(a)),
        ("4", "Destinations & NEET", lambda a: destinations_menu(a)),
        ("5", "Work Journal", lambda a: work_journal_menu(a)),
        ("6", "UCAS Applications", lambda a: ucas_menu(a)),
        ("7", "Alumni Network", lambda a: alumni_menu(a)),
    ])


def _admin_student_selfservice(auth):
    from education_system.college_system.modules.domain.helpdesk.cli.helpdesk_cli import helpdesk_menu
    from education_system.college_system.modules.domain.todo.cli.todo_cli import todo_menu
    from education_system.college_system.modules.domain.calendar.cli.calendar_cli import calendar_menu
    from education_system.college_system.modules.domain.library.cli.library_cli import library_menu
    from education_system.college_system.modules.domain.portfolio.cli.portfolio_cli import portfolio_menu
    from education_system.college_system.modules.domain.study_planner.cli.study_planner_cli import study_planner_menu
    from education_system.college_system.modules.domain.enrichment.cli.enrichment_cli import enrichment_menu
    from education_system.college_system.modules.domain.skills_passport.cli.skills_passport_cli import skills_passport_menu
    from education_system.college_system.modules.domain.progress_dashboard.cli.progress_dashboard_cli import progress_dashboard_menu
    from education_system.college_system.modules.domain.student_portal.cli.student_portal_cli import student_portal_menu
    from education_system.college_system.modules.domain.forums.cli.forums_cli import forums_menu
    from education_system.college_system.modules.domain.student_council.cli.student_council_cli import student_council_menu
    _run_submenu(auth, "Student Self-Service", [
        ("1", "Helpdesk", lambda a: helpdesk_menu(a)),
        ("2", "To-Do List", lambda a: todo_menu(a)),
        ("3", "Calendar", lambda a: calendar_menu(a)),
        ("4", "Library", lambda a: library_menu(a)),
        ("5", "Portfolio", lambda a: portfolio_menu(a)),
        ("6", "Study Planner", lambda a: study_planner_menu(a)),
        ("7", "Enrichment", lambda a: enrichment_menu(a)),
        ("8", "Skills Passport", lambda a: skills_passport_menu(a)),
        ("9", "Progress Dashboard", lambda a: progress_dashboard_menu(a)),
        ("A", "Student Portal", lambda a: student_portal_menu(a)),
        ("B", "Discussion Forums", lambda a: forums_menu(a)),
        ("C", "Student Council", lambda a: student_council_menu(a)),
    ])


def _admin_system_settings(auth):
    from education_system.college_system.modules.domain.settings.cli.settings_cli import settings_menu
    from education_system.college_system.modules.domain.departments.cli.departments_cli import departments_menu
    from education_system.college_system.modules.domain.document_hub.cli.document_hub_cli import document_hub_menu
    from education_system.college_system.modules.domain.advanced_search.cli.advanced_search_cli import advanced_search_menu
    from education_system.college_system.modules.domain.accessibility.cli.accessibility_cli import accessibility_menu
    from education_system.college_system.modules.domain.mobile_dashboard.cli.mobile_dashboard_cli import mobile_dashboard_menu
    from education_system.college_system.modules.domain.attachments.cli.attachments_cli import attachments_menu
    from education_system.college_system.modules.domain.multi_language.cli.multi_language_cli import multi_language_menu
    _run_submenu(auth, "System & Settings", [
        ("1", "Settings", lambda a: settings_menu(a)),
        ("2", "Departments & Groups", lambda a: departments_menu(a)),
        ("3", "Document Hub", lambda a: document_hub_menu(a)),
        ("4", "Advanced Search", lambda a: advanced_search_menu(a)),
        ("5", "Accessibility", lambda a: accessibility_menu(a)),
        ("6", "Mobile Dashboard", lambda a: mobile_dashboard_menu(a)),
        ("7", "Attachments", lambda a: attachments_menu(a)),
        ("8", "Multi-Language", lambda a: multi_language_menu(a)),
    ])


# ================================================================
# Role-based menus
# ================================================================

def admin_menu(auth: UserAuth):
    """Admin-specific menu with categorized sub-menus."""
    from education_system.college_system.modules.shared.cli.mfa_cli import mfa_settings_menu

    while True:
        print_header(f"{t('app.name')} - Admin")
        options = [
            ("1", "Teaching & Learning"),
            ("2", "Students & Pastoral"),
            ("3", "Attendance & Timetable"),
            ("4", "Exams & Assessment"),
            ("5", "Staff & HR"),
            ("6", "Administration"),
            ("7", "Finance & Funding"),
            ("8", "Communication"),
            ("9", "Facilities & Resources"),
            ("A", "Analytics & Reports"),
            ("B", "Parent & Careers"),
            ("C", "Student Self-Service"),
            ("D", "System & Settings"),
            ("M", t("menu.mfa_settings")),
            ("P", t("menu.change_password")),
            ("G", "Switch to GUI"),
            ("U", "Switch to University System"),
            ("W", "Switch to Secondary School"),
            ("R", "Switch to Primary School"),
            ("L", "Logout"),
            ("0", t("menu.exit")),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _admin_teaching_learning(auth)
        elif choice == "2":
            _admin_students_pastoral(auth)
        elif choice == "3":
            _admin_attendance_timetable(auth)
        elif choice == "4":
            _admin_exams_assessment(auth)
        elif choice == "5":
            _admin_staff_hr(auth)
        elif choice == "6":
            _admin_administration(auth)
        elif choice == "7":
            _admin_finance_funding(auth)
        elif choice == "8":
            _admin_communication(auth)
        elif choice == "9":
            _admin_facilities(auth)
        elif choice == "A":
            _admin_analytics(auth)
        elif choice == "B":
            _admin_parent_careers(auth)
        elif choice == "C":
            _admin_student_selfservice(auth)
        elif choice == "D":
            _admin_system_settings(auth)
        elif choice == "M":
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("college", "gui")
            return "switch"
        elif choice == "U":
            from education_system.switch import request_switch
            request_switch("university", "cli")
            return "switch"
        elif choice == "W":
            from education_system.switch import request_switch
            request_switch("school", "cli")
            return "switch"
        elif choice == "R":
            from education_system.switch import request_switch
            request_switch("primary", "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print(f"\n  {t('menu.invalid_option')}")


def instructor_menu(auth: UserAuth):
    """Instructor-specific menu with categorized sub-menus."""
    from education_system.college_system.modules.shared.cli.mfa_cli import mfa_settings_menu

    while True:
        print_header(f"{t('app.name')} - Teacher")
        options = [
            ("1", "Teaching & Learning"),
            ("2", "Students & Pastoral"),
            ("3", "Attendance & Timetable"),
            ("4", "Exams & Assessment"),
            ("5", "Staff & HR"),
            ("6", "Communication"),
            ("7", "Facilities & Resources"),
            ("8", "Analytics & Reports"),
            ("9", "Student Self-Service"),
            ("M", t("menu.mfa_settings")),
            ("P", t("menu.change_password")),
            ("G", "Switch to GUI"),
            ("U", "Switch to University System"),
            ("W", "Switch to Secondary School"),
            ("R", "Switch to Primary School"),
            ("L", "Logout"),
            ("0", t("menu.exit")),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _admin_teaching_learning(auth)
        elif choice == "2":
            _admin_students_pastoral(auth)
        elif choice == "3":
            _admin_attendance_timetable(auth)
        elif choice == "4":
            _admin_exams_assessment(auth)
        elif choice == "5":
            _admin_staff_hr(auth)
        elif choice == "6":
            _admin_communication(auth)
        elif choice == "7":
            _admin_facilities(auth)
        elif choice == "8":
            _admin_analytics(auth)
        elif choice == "9":
            _admin_student_selfservice(auth)
        elif choice == "M":
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("college", "gui")
            return "switch"
        elif choice == "U":
            from education_system.switch import request_switch
            request_switch("university", "cli")
            return "switch"
        elif choice == "W":
            from education_system.switch import request_switch
            request_switch("school", "cli")
            return "switch"
        elif choice == "R":
            from education_system.switch import request_switch
            request_switch("primary", "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print(f"\n  {t('menu.invalid_option')}")


def student_menu_main(auth: UserAuth):
    """Student-specific menu with categorized sub-menus."""
    from education_system.college_system.modules.domain.grades.cli.grade_cli import view_my_grades
    from education_system.college_system.modules.domain.attendance.cli.attendance_cli import view_my_attendance
    from education_system.college_system.modules.domain.timetable.cli.timetable_cli import _my_timetable
    from education_system.college_system.modules.domain.assignments.cli.assignment_cli import _my_submissions
    from education_system.college_system.modules.domain.notifications.cli.notification_cli import notification_menu
    from education_system.college_system.modules.domain.messaging.cli.message_cli import messaging_menu
    from education_system.college_system.modules.shared.cli.mfa_cli import mfa_settings_menu
    from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
    from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
    from education_system.college_system.modules.domain.todo.cli.todo_cli import todo_menu
    from education_system.college_system.modules.domain.calendar.cli.calendar_cli import calendar_menu
    from education_system.college_system.modules.domain.helpdesk.cli.helpdesk_cli import helpdesk_menu
    from education_system.college_system.modules.domain.settings.cli.settings_cli import settings_menu
    from education_system.college_system.modules.domain.parents_evening.cli.parents_evening_cli import parents_evening_menu
    from education_system.college_system.modules.domain.careers.cli.careers_cli import careers_menu
    from education_system.college_system.modules.domain.library.cli.library_cli import library_menu
    # New student modules
    from education_system.college_system.modules.domain.portfolio.cli.portfolio_cli import portfolio_menu
    from education_system.college_system.modules.domain.study_planner.cli.study_planner_cli import study_planner_menu
    from education_system.college_system.modules.domain.enrichment.cli.enrichment_cli import enrichment_menu
    from education_system.college_system.modules.domain.peer_mentoring.cli.peer_mentoring_cli import peer_mentoring_menu
    from education_system.college_system.modules.domain.surveys.cli.surveys_cli import surveys_menu
    from education_system.college_system.modules.domain.skills_passport.cli.skills_passport_cli import skills_passport_menu
    from education_system.college_system.modules.domain.progress_dashboard.cli.progress_dashboard_cli import progress_dashboard_menu
    from education_system.college_system.modules.domain.meal_ordering.cli.meal_ordering_cli import meal_ordering_menu
    from education_system.college_system.modules.domain.print_credits.cli.print_credits_cli import print_credits_menu
    from education_system.college_system.modules.domain.work_journal.cli.work_journal_cli import work_journal_menu
    # All-user modules
    from education_system.college_system.modules.domain.announcements.cli.announcements_cli import announcements_menu
    from education_system.college_system.modules.domain.feedback.cli.feedback_cli import feedback_menu
    from education_system.college_system.modules.domain.accessibility.cli.accessibility_cli import accessibility_menu
    from education_system.college_system.modules.domain.activity_feed.cli.activity_feed_cli import activity_feed_menu

    tt_svc = TimetableService(auth._db_path)
    assign_svc = AssignmentService(auth._db_path)

    while True:
        print_header(f"{t('app.name')} - Student")
        options = [
            ("1", "My Academics"),
            ("2", "Self-Service & Activities"),
            ("3", "Communication"),
            ("4", "Tools & Settings"),
            ("M", t("menu.mfa_settings")),
            ("P", t("menu.change_password")),
            ("G", "Switch to GUI"),
            ("U", "Switch to University System"),
            ("W", "Switch to Secondary School"),
            ("R", "Switch to Primary School"),
            ("L", "Logout"),
            ("0", t("menu.exit")),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _run_submenu(auth, "My Academics", [
                ("1", "View My Grades", lambda a: view_my_grades(a)),
                ("2", "View My Attendance", lambda a: view_my_attendance(a)),
                ("3", "My Timetable", lambda a: _my_timetable(tt_svc, a)),
                ("4", "My Submissions", lambda a: _my_submissions(assign_svc, a)),
                ("5", "Exams", lambda a: None),
                ("6", "Progress Dashboard", lambda a: progress_dashboard_menu(a)),
                ("7", "Parents Evening", lambda a: parents_evening_menu(a)),
            ])
        elif choice == "2":
            _run_submenu(auth, "Self-Service & Activities", [
                ("1", "Portfolio", lambda a: portfolio_menu(a)),
                ("2", "Study Planner", lambda a: study_planner_menu(a)),
                ("3", "Enrichment", lambda a: enrichment_menu(a)),
                ("4", "Peer Mentoring", lambda a: peer_mentoring_menu(a)),
                ("5", "Skills Passport", lambda a: skills_passport_menu(a)),
                ("6", "Careers", lambda a: careers_menu(a)),
                ("7", "Work Journal", lambda a: work_journal_menu(a)),
                ("8", "Meal Ordering", lambda a: meal_ordering_menu(a)),
                ("9", "Print Credits", lambda a: print_credits_menu(a)),
            ])
        elif choice == "3":
            _run_submenu(auth, "Communication", [
                ("1", "Notifications", lambda a: notification_menu(a)),
                ("2", "Messages", lambda a: messaging_menu(a)),
                ("3", "Announcements", lambda a: announcements_menu(a)),
                ("4", "Surveys", lambda a: surveys_menu(a)),
                ("5", "Feedback", lambda a: feedback_menu(a)),
                ("6", "Activity Feed", lambda a: activity_feed_menu(a)),
                ("7", "Helpdesk", lambda a: helpdesk_menu(a)),
            ])
        elif choice == "4":
            _run_submenu(auth, "Tools & Settings", [
                ("1", "To-Do List", lambda a: todo_menu(a)),
                ("2", "Calendar", lambda a: calendar_menu(a)),
                ("3", "Library", lambda a: library_menu(a)),
                ("4", "Settings", lambda a: settings_menu(a)),
                ("5", "Accessibility", lambda a: accessibility_menu(a)),
            ])
        elif choice == "M":
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("college", "gui")
            return "switch"
        elif choice == "U":
            from education_system.switch import request_switch
            request_switch("university", "cli")
            return "switch"
        elif choice == "W":
            from education_system.switch import request_switch
            request_switch("school", "cli")
            return "switch"
        elif choice == "R":
            from education_system.switch import request_switch
            request_switch("primary", "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print(f"\n  {t('menu.invalid_option')}")


def parent_menu_main(auth: UserAuth):
    """Parent-specific menu."""
    from education_system.college_system.modules.domain.parent_portal.cli.parent_cli import parent_menu as _parent_view
    from education_system.college_system.modules.domain.messaging.cli.message_cli import messaging_menu
    from education_system.college_system.modules.domain.settings.cli.settings_cli import settings_menu
    from education_system.college_system.modules.domain.todo.cli.todo_cli import todo_menu
    from education_system.college_system.modules.domain.calendar.cli.calendar_cli import calendar_menu
    from education_system.college_system.modules.shared.cli.mfa_cli import mfa_settings_menu
    from education_system.college_system.modules.domain.parents_evening.cli.parents_evening_cli import parents_evening_menu
    from education_system.college_system.modules.domain.announcements.cli.announcements_cli import announcements_menu
    from education_system.college_system.modules.domain.feedback.cli.feedback_cli import feedback_menu

    while True:
        print_header(f"{t('app.name')} - Parent")
        options = [
            ("1", "Parent Portal"),
            ("2", "Messages"),
            ("3", "To-Do List"),
            ("4", "Calendar"),
            ("5", "Settings"),
            ("6", "Parents Evening"),
            ("7", "Announcements"),
            ("8", "Feedback"),
            ("M", t("menu.mfa_settings")),
            ("P", t("menu.change_password")),
            ("G", "Switch to GUI"),
            ("U", "Switch to University System"),
            ("W", "Switch to Secondary School"),
            ("R", "Switch to Primary School"),
            ("L", "Logout"),
            ("0", t("menu.exit")),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _parent_view(auth)
        elif choice == "2":
            messaging_menu(auth)
        elif choice == "3":
            todo_menu(auth)
        elif choice == "4":
            calendar_menu(auth)
        elif choice == "5":
            settings_menu(auth)
        elif choice == "6":
            parents_evening_menu(auth)
        elif choice == "7":
            announcements_menu(auth)
        elif choice == "8":
            feedback_menu(auth)
        elif choice == "M":
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("college", "gui")
            return "switch"
        elif choice == "U":
            from education_system.switch import request_switch
            request_switch("university", "cli")
            return "switch"
        elif choice == "W":
            from education_system.switch import request_switch
            request_switch("school", "cli")
            return "switch"
        elif choice == "R":
            from education_system.switch import request_switch
            request_switch("primary", "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print(f"\n  {t('menu.invalid_option')}")


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
        print(f"\n  {t('auth.password_changed')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def main(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Main CLI entry point.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    ensure_directories()
    load_locale("en")
    from education_system.college_system.core.logs import configure_logging
    configure_logging()

    # Initialize database
    init_db(db_path)
    seed_default_data(db_path)

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

        # Determine role for the college system
        role = "student"
        for s in auth.current_user.get("systems", []):
            if s["system_key"] == "college":
                role = s["role"]
                break
        auth._current_user["role"] = role

    while True:
        result = None
        try:
            if role == "admin" or role == "staff":
                result = admin_menu(auth)
            elif role in ("instructor", "teacher"):
                result = instructor_menu(auth)
            elif role == "parent":
                result = parent_menu_main(auth)
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
