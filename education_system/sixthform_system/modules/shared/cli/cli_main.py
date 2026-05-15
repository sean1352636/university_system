"""CLI main menu for the Sixth Form System.

Mirrors the categorized structure of `gui_main.py`: a top-level list of
categories; selecting a category opens a sub-menu of feature actions.
Stubs print a placeholder; real domain wiring goes in later.
"""

from __future__ import annotations

import logging
from education_system.sixthform_system import SYSTEM_NAME

logger = logging.getLogger(__name__)

# Same catalogue as the GUI — keep them in sync.
CATEGORIES: list[tuple[str, list[str]]] = [
    ("Student Management", [
        "Student Directory", "Add Student", "Search Students",
        "Advanced Search", "Student Profile", "Admissions",
        "Enrolment", "Onboarding", "Bulk Operations", "Alumni",
    ]),
    ("Academic Management", [
        "Academic Year", "Calendar", "Courses", "Subjects & A-Levels",
        "Class Groups", "Timetable", "Attendance",
        "Lesson Plans", "Cover", "Cover Agency",
        "Homework & Coursework", "Assignments",
        "Enrichment", "Library", "Study Planner",
    ]),
    ("Assessment & Grades", [
        "Gradebook", "Predicted Grades", "Baseline Assessment",
        "Target Setting", "ILP", "Intervention Tracking",
        "Early Warning", "Value Added",
        "Mock Exams", "Exam Entries", "Results Day",
        "Observations", "Self Assessment",
        "Quality Assurance", "SEF Builder",
    ]),
    ("UCAS & Careers", [
        "UCAS Applications", "Personal Statements", "References",
        "University Offers", "Apprenticeships", "Careers Guidance",
    ]),
    ("Pastoral & Wellbeing", [
        "Tutor Groups", "Behaviour Log", "Disciplinary",
        "Safeguarding", "SEND", "Accessibility",
        "Wellbeing", "Student Wellbeing", "Student Support",
        "Peer Mentoring", "Attendance Concerns", "Absence Requests",
        "First Aid", "Emergency", "Prevent Duty",
        "Equality & Diversity", "Complaints", "Feedback",
        "Surveys", "Student Council", "Transport",
    ]),
    ("Staff & Communication", [
        "Staff Directory", "Departments", "Staff HR",
        "Staff Absence", "Staff Wellbeing", "Recruitment",
        "Appraisals", "CPD", "DBS Checks", "Visitors",
        "Parent Contacts", "Parents' Evenings",
        "Notices & Bulletins", "Announcements", "Notifications",
        "Activity Feed", "Email / Messaging",
        "Letter Templates", "Document Hub", "Attachments",
    ]),
    ("Finance & Bursaries", [
        "Fees", "Bursary Applications", "Trips & Payments",
        "Receipts", "Expense Claims", "Funding", "Census ILR",
    ]),
    ("Reports & Analytics", [
        "Attendance Report", "Grades Report", "Progress Tracking",
        "KPI Dashboard", "Data Dashboard", "Progress Dashboard",
        "Mobile Dashboard", "Audit Reports", "Data Export",
        "Custom Export",
    ]),
    ("System", [
        "Change Password", "Multi-Factor Authentication",
        "User Accounts", "User Management",
        "Settings", "Compliance", "Governance", "Policies",
        "GDPR", "Risk Management", "Health & Safety", "Assets",
        "Multi-Language", "To-Do", "About",
    ]),
]


def _prompt(msg: str) -> str:
    """Prompt the user. May raise ``SessionTimeoutError`` if they've
    been idle past the configured threshold — callers in the menu
    loops catch that and bail back to the login screen."""
    from education_system.sixthform_system.modules.shared.cli.idle_timeout import (
        timed_input,
    )
    try:
        return timed_input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return "0"


def _submenu(category: str, items: list[str], *, auth=None) -> None:
    while True:
        print(f"\n── {category} ──")
        for i, label in enumerate(items, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        # SessionTimeoutError isn't caught here — we let it bubble up
        # to ``_main_menu`` so the user lands at the login screen
        # instead of stuck in this submenu after timing out.
        choice = _prompt("Select: ")
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("Invalid selection.")
            continue
        label = items[int(choice) - 1]
        logger.debug("Sixth-form CLI dispatch: %s / %s", category, label)
        from education_system.sixthform_system.modules.domain.students.students import student_cli
        from education_system.sixthform_system.modules.domain.students.enrolments import enrolment_cli
        from education_system.sixthform_system.modules.domain.academics.courses import course_cli
        from education_system.sixthform_system.modules.domain.academics.subjects import subject_cli
        from education_system.sixthform_system.modules.domain.academics.class_groups import class_group_cli
        from education_system.sixthform_system.modules.domain.academics.timetable import timetable_cli
        from education_system.sixthform_system.modules.domain.academics.attendance import attendance_cli
        from education_system.sixthform_system.modules.domain.academics.homework import homework_cli
        from education_system.sixthform_system.modules.domain.assessment.gradebook import gradebook_cli
        from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades_cli
        from education_system.sixthform_system.modules.domain.assessment.mock_exams import mock_exam_cli
        from education_system.sixthform_system.modules.domain.assessment.exam_entries import exam_entry_cli
        from education_system.sixthform_system.modules.domain.assessment.exam_results import exam_result_cli
        from education_system.sixthform_system.modules.domain.progression.ucas import ucas_cli
        from education_system.sixthform_system.modules.domain.progression.personal_statements import personal_statement_cli
        from education_system.sixthform_system.modules.domain.progression.references import reference_cli
        from education_system.sixthform_system.modules.domain.progression.offers import offer_cli
        from education_system.sixthform_system.modules.domain.progression.apprenticeships import apprenticeship_cli
        from education_system.sixthform_system.modules.domain.progression.careers import careers_cli
        from education_system.sixthform_system.modules.domain.pastoral.tutor_groups import tutor_group_cli
        from education_system.sixthform_system.modules.domain.pastoral.behaviour import behaviour_cli
        from education_system.sixthform_system.modules.domain.pastoral.safeguarding import safeguarding_cli
        from education_system.sixthform_system.modules.domain.pastoral.wellbeing import wellbeing_cli
        from education_system.sixthform_system.modules.domain.pastoral.student_wellbeing import student_wellbeing_cli
        from education_system.sixthform_system.modules.domain.pastoral.prevent_duty import prevent_duty_cli
        from education_system.sixthform_system.modules.domain.pastoral.attendance_concerns import attendance_concerns_cli
        from education_system.sixthform_system.modules.domain.pastoral.absence_requests import absence_requests_cli
        from education_system.sixthform_system.modules.domain.academics.academic_year import academic_year_cli
        from education_system.sixthform_system.modules.domain.pastoral.accessibility import accessibility_cli
        from education_system.sixthform_system.modules.domain.staff_comms.activity_feed import activity_feed_cli
        from education_system.sixthform_system.modules.domain.students.advanced_search import advanced_search_cli
        from education_system.sixthform_system.modules.domain.students.admissions import admissions_cli
        from education_system.sixthform_system.modules.domain.students.onboarding import onboarding_cli
        from education_system.sixthform_system.modules.domain.students.bulk_operations import bulk_operations_cli
        from education_system.sixthform_system.modules.domain.students.alumni import alumni_cli
        from education_system.sixthform_system.modules.domain.academics.calendar import calendar_cli
        from education_system.sixthform_system.modules.domain.academics.lesson_plans import lesson_plans_cli
        from education_system.sixthform_system.modules.domain.academics.cover import cover_cli
        from education_system.sixthform_system.modules.domain.academics.cover_agency import cover_agency_cli
        from education_system.sixthform_system.modules.domain.academics.assignments import assignments_cli
        from education_system.sixthform_system.modules.domain.academics.enrichment import enrichment_cli
        from education_system.sixthform_system.modules.domain.academics.library import library_cli
        from education_system.sixthform_system.modules.domain.academics.study_planner import study_planner_cli
        from education_system.sixthform_system.modules.domain.assessment.baseline_assessment import baseline_assessment_cli
        from education_system.sixthform_system.modules.domain.assessment.target_setting import target_setting_cli
        from education_system.sixthform_system.modules.domain.assessment.ilp import ilp_cli
        from education_system.sixthform_system.modules.domain.assessment.intervention_tracking import intervention_tracking_cli
        from education_system.sixthform_system.modules.domain.assessment.value_added import value_added_cli
        from education_system.sixthform_system.modules.domain.assessment.early_warning import early_warning_cli
        from education_system.sixthform_system.modules.domain.assessment.observations import observations_cli
        from education_system.sixthform_system.modules.domain.assessment.self_assessment import self_assessment_cli
        from education_system.sixthform_system.modules.domain.assessment.quality_assurance import quality_assurance_cli
        from education_system.sixthform_system.modules.domain.assessment.sef_builder import sef_builder_cli
        from education_system.sixthform_system.modules.domain.pastoral.send import send_cli
        from education_system.sixthform_system.modules.domain.pastoral.disciplinary import disciplinary_cli
        from education_system.sixthform_system.modules.domain.pastoral.student_support import student_support_cli
        from education_system.sixthform_system.modules.domain.pastoral.peer_mentoring import peer_mentoring_cli
        from education_system.sixthform_system.modules.domain.pastoral.first_aid import first_aid_cli
        from education_system.sixthform_system.modules.domain.pastoral.emergency import emergency_cli
        from education_system.sixthform_system.modules.domain.pastoral.equality_diversity import equality_diversity_cli
        from education_system.sixthform_system.modules.domain.pastoral.complaints import complaints_cli
        from education_system.sixthform_system.modules.domain.pastoral.feedback import feedback_cli
        from education_system.sixthform_system.modules.domain.pastoral.surveys import surveys_cli
        from education_system.sixthform_system.modules.domain.pastoral.student_council import student_council_cli
        from education_system.sixthform_system.modules.domain.pastoral.transport import transport_cli
        from education_system.sixthform_system.modules.domain.staff_comms.staff_hr import staff_hr_cli
        from education_system.sixthform_system.modules.domain.staff_comms.departments import departments_cli
        from education_system.sixthform_system.modules.domain.staff_comms.staff_absence import staff_absence_cli
        from education_system.sixthform_system.modules.domain.staff_comms.staff_wellbeing import staff_wellbeing_cli
        from education_system.sixthform_system.modules.domain.staff_comms.recruitment import recruitment_cli
        from education_system.sixthform_system.modules.domain.staff_comms.appraisals import appraisals_cli
        from education_system.sixthform_system.modules.domain.staff_comms.cpd import cpd_cli
        from education_system.sixthform_system.modules.domain.staff_comms.dbs_checks import dbs_checks_cli
        from education_system.sixthform_system.modules.domain.staff_comms.visitors import visitors_cli
        from education_system.sixthform_system.modules.domain.staff_comms.announcements import announcements_cli
        from education_system.sixthform_system.modules.domain.staff_comms.notifications import notifications_cli
        from education_system.sixthform_system.modules.domain.staff_comms.letter_templates import letter_templates_cli
        from education_system.sixthform_system.modules.domain.staff_comms.document_hub import document_hub_cli
        from education_system.sixthform_system.modules.domain.staff_comms.attachments import attachments_cli
        from education_system.sixthform_system.modules.domain.finance.census_ilr import census_ilr_cli
        from education_system.sixthform_system.modules.domain.finance.expense_claims import expense_claims_cli
        from education_system.sixthform_system.modules.domain.finance.funding import funding_cli
        from education_system.sixthform_system.modules.domain.staff_comms.staff import staff_cli
        from education_system.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts_cli
        from education_system.sixthform_system.modules.domain.staff_comms.parents_evenings import parents_evenings_cli
        from education_system.sixthform_system.modules.domain.staff_comms.notices import notices_cli
        from education_system.sixthform_system.modules.domain.staff_comms.messages import messages_cli
        from education_system.sixthform_system.modules.domain.finance.fees import fees_cli
        from education_system.sixthform_system.modules.domain.finance.bursaries import bursaries_cli
        from education_system.sixthform_system.modules.domain.finance.trips import trips_cli
        from education_system.sixthform_system.modules.domain.finance.receipts import receipts_cli
        from education_system.sixthform_system.modules.domain.reports.attendance_report import attendance_report_cli
        from education_system.sixthform_system.modules.domain.reports.grades_report import grades_report_cli
        from education_system.sixthform_system.modules.domain.reports.progress import progress_cli
        from education_system.sixthform_system.modules.domain.reports.custom_export import custom_export_cli
        from education_system.sixthform_system.modules.domain.reports.kpi_dashboard import kpi_dashboard_cli
        from education_system.sixthform_system.modules.domain.reports.data_dashboard import data_dashboard_cli
        from education_system.sixthform_system.modules.domain.reports.progress_dashboard import progress_dashboard_cli
        from education_system.sixthform_system.modules.domain.reports.mobile_dashboard import mobile_dashboard_cli
        from education_system.sixthform_system.modules.domain.reports.audit_reports import audit_reports_cli
        from education_system.sixthform_system.modules.domain.reports.data_export import data_export_cli
        from education_system.sixthform_system.modules.domain.governance.compliance import compliance_cli
        from education_system.sixthform_system.modules.domain.governance.governance import governance_cli
        from education_system.sixthform_system.modules.domain.governance.policies import policies_cli
        from education_system.sixthform_system.modules.domain.governance.health_safety import health_safety_cli
        from education_system.sixthform_system.modules.domain.governance.assets import assets_cli
        from education_system.shared.i18n.selector_cli import show_language_selector_cli
        from education_system.sixthform_system.modules.domain.governance.todo import todo_cli
        from education_system.sixthform_system.modules.domain.governance.user_management import user_management_cli
        from education_system.sixthform_system.modules.domain.governance.gdpr import gdpr_cli
        from education_system.sixthform_system.modules.domain.governance.risk_management import risk_management_cli
        from education_system.sixthform_system.modules.shared.cli import (
            change_password_cli, mfa_cli, user_accounts_cli, settings_cli, about_cli,
        )
        if change_password_cli.dispatch(label, auth=auth):
            continue
        if mfa_cli.dispatch(label, auth=auth):
            continue
        if user_accounts_cli.dispatch(label, auth=auth):
            continue
        if settings_cli.dispatch(label, auth=auth):
            continue
        if about_cli.dispatch(label, auth=auth):
            continue
        if user_management_cli.dispatch(label, auth=auth):
            continue
        if (student_cli.dispatch(label)
                or enrolment_cli.dispatch(label)
                or course_cli.dispatch(label)
                or subject_cli.dispatch(label)
                or class_group_cli.dispatch(label)
                or timetable_cli.dispatch(label)
                or attendance_cli.dispatch(label)
                or homework_cli.dispatch(label)
                or gradebook_cli.dispatch(label)
                or predicted_grades_cli.dispatch(label)
                or mock_exam_cli.dispatch(label)
                or exam_entry_cli.dispatch(label)
                or exam_result_cli.dispatch(label)
                or ucas_cli.dispatch(label)
                or personal_statement_cli.dispatch(label)
                or reference_cli.dispatch(label)
                or offer_cli.dispatch(label)
                or apprenticeship_cli.dispatch(label)
                or careers_cli.dispatch(label)
                or tutor_group_cli.dispatch(label)
                or behaviour_cli.dispatch(label)
                or safeguarding_cli.dispatch(label)
                or wellbeing_cli.dispatch(label)
                or student_wellbeing_cli.dispatch(label)
                or prevent_duty_cli.dispatch(label)
                or attendance_concerns_cli.dispatch(label)
                or absence_requests_cli.dispatch(label)
                or academic_year_cli.dispatch(label)
                or accessibility_cli.dispatch(label)
                or activity_feed_cli.dispatch(label)
                or advanced_search_cli.dispatch(label)
                or admissions_cli.dispatch(label)
                or onboarding_cli.dispatch(label)
                or bulk_operations_cli.dispatch(label)
                or alumni_cli.dispatch(label)
                or calendar_cli.dispatch(label)
                or lesson_plans_cli.dispatch(label)
                or cover_cli.dispatch(label)
                or cover_agency_cli.dispatch(label)
                or assignments_cli.dispatch(label)
                or enrichment_cli.dispatch(label)
                or library_cli.dispatch(label)
                or study_planner_cli.dispatch(label)
                or baseline_assessment_cli.dispatch(label)
                or target_setting_cli.dispatch(label)
                or ilp_cli.dispatch(label)
                or intervention_tracking_cli.dispatch(label)
                or value_added_cli.dispatch(label)
                or early_warning_cli.dispatch(label)
                or observations_cli.dispatch(label)
                or self_assessment_cli.dispatch(label)
                or quality_assurance_cli.dispatch(label)
                or sef_builder_cli.dispatch(label)
                or send_cli.dispatch(label)
                or disciplinary_cli.dispatch(label)
                or student_support_cli.dispatch(label)
                or peer_mentoring_cli.dispatch(label)
                or first_aid_cli.dispatch(label)
                or emergency_cli.dispatch(label)
                or equality_diversity_cli.dispatch(label)
                or complaints_cli.dispatch(label)
                or feedback_cli.dispatch(label)
                or surveys_cli.dispatch(label)
                or student_council_cli.dispatch(label)
                or transport_cli.dispatch(label)
                or staff_hr_cli.dispatch(label)
                or departments_cli.dispatch(label)
                or staff_absence_cli.dispatch(label)
                or staff_wellbeing_cli.dispatch(label)
                or recruitment_cli.dispatch(label)
                or appraisals_cli.dispatch(label)
                or cpd_cli.dispatch(label)
                or dbs_checks_cli.dispatch(label)
                or visitors_cli.dispatch(label)
                or announcements_cli.dispatch(label)
                or notifications_cli.dispatch(label)
                or letter_templates_cli.dispatch(label)
                or document_hub_cli.dispatch(label)
                or attachments_cli.dispatch(label)
                or census_ilr_cli.dispatch(label)
                or expense_claims_cli.dispatch(label)
                or funding_cli.dispatch(label)
                or staff_cli.dispatch(label)
                or parent_contacts_cli.dispatch(label)
                or parents_evenings_cli.dispatch(label)
                or notices_cli.dispatch(label)
                or messages_cli.dispatch(label)
                or fees_cli.dispatch(label)
                or bursaries_cli.dispatch(label)
                or trips_cli.dispatch(label)
                or receipts_cli.dispatch(label)
                or attendance_report_cli.dispatch(label)
                or grades_report_cli.dispatch(label)
                or progress_cli.dispatch(label)
                or custom_export_cli.dispatch(label)
                or kpi_dashboard_cli.dispatch(label)
                or data_dashboard_cli.dispatch(label)
                or progress_dashboard_cli.dispatch(label)
                or mobile_dashboard_cli.dispatch(label)
                or audit_reports_cli.dispatch(label)
                or data_export_cli.dispatch(label)
                or compliance_cli.dispatch(label)
                or governance_cli.dispatch(label)
                or policies_cli.dispatch(label)
                or health_safety_cli.dispatch(label)
                or assets_cli.dispatch(label)
                or (label == "Multi-Language" and (show_language_selector_cli() or True))
                or todo_cli.dispatch(label)
                or gdpr_cli.dispatch(label)
                or risk_management_cli.dispatch(label)):
            continue
        print(f"\n[stub] {label} — not yet implemented.")
        _prompt("Press Enter to continue...")


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli
    from education_system.sixthform_system.modules.shared.cli.idle_timeout import (
        SessionTimeoutError, timeout_minutes,
    )
    user = auth.current_user or {}
    show_system_switch = is_superadmin(user)
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {user.get('username', '?')}")
        for i, (cat, _items) in enumerate(CATEGORIES, 1):
            print(f"  {i:2d}) {cat}")
        print("   G) Switch to GUI")
        if show_system_switch:
            print("   S) Switch System")
        print("   L) Logout (return to login)")
        try:
            choice = _prompt("Select: ").lower()
        except SessionTimeoutError:
            mins = timeout_minutes()
            print(f"\n[!] Signed out after {mins} minute(s) of inactivity. "
                  "Please sign in again to continue.")
            logger.info(
                "Idle logout for user=%s after %d minute(s)",
                user.get("username", "?"), mins)
            try:
                auth.logout()
            except Exception:
                pass
            _switch.request_logout("cli")
            return
        if choice == "g":
            _switch.request_switch("college", "gui")
            return
        if choice == "s" and show_system_switch:
            target = pick_system_cli(user, "college")
            if target:
                _switch.request_switch(target, "cli")
                return
            continue
        if choice == "l":
            try:
                auth.logout()
            except Exception:
                pass
            _switch.request_logout("cli")
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(CATEGORIES)):
            print("Invalid selection.")
            continue
        cat, items = CATEGORIES[int(choice) - 1]
        _submenu(cat, items, auth=auth)


def run_authenticated(auth) -> int:
    """Entry point when the caller has already logged in (e.g. GUI → CLI switch).

    The shared session is owned by the unified launcher — we never log it
    out unconditionally here. The explicit "Logout" menu item handles that;
    the "Switch to GUI" menu item leaves the session intact so dispatch
    can hand it straight to the GUI.
    """
    _main_menu(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the CLI for an already-authenticated session.

    Called by `run.py` after the universal login succeeds. No per-system
    login is shown — `shared_auth.current_user` must already be set.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("sixthform CLI invoked without a shared_auth session")
        raise RuntimeError(
            "sixthform_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Sixth-form CLI starting for user=%s role=%s",
                cu.get("username"), role)
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Sixth Form)")
    raise SystemExit(2)
