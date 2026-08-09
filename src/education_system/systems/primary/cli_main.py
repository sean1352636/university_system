"""CLI main menu for the Primary School System.

Mirrors the categorized structure of `gui_main.py`: a top-level list
of categories; selecting a category opens a sub-menu of feature
actions. Every action is a placeholder — real domain wiring goes in
later.
"""

from __future__ import annotations

import logging

from education_system.systems.primary import SYSTEM_NAME

logger = logging.getLogger(__name__)

CATEGORIES: list[tuple[str, list[str]]] = [
    ("Pupil Management", [
        "Pupil Directory", "Add Pupil", "Search Pupils",
        "Pupil Profile", "Admissions", "Year Group Enrolment",
        "Onboarding", "Bulk Operations", "Leavers",
    ]),
    ("Academic Management", [
        "Academic Year", "Calendar", "Year Groups (R–6)", "Classes",
        "Subjects", "Timetable", "Attendance Register",
        "Lesson Plans", "Cover", "Homework / Reading Log",
        "Phonics Tracking", "Reading Levels", "Library",
        "Clubs & Activities",
    ]),
    ("Assessment & Progress", [
        "Assessment Records", "Phonics Screening", "Multiplication Check",
        "KS1 SATs", "KS2 SATs", "EYFS Profile", "Target Setting",
        "Intervention Tracking", "Early Warning", "Observations",
        "Pupil Reports",
    ]),
    ("Pastoral & Wellbeing", [
        "Class Teachers", "Behaviour Log", "House Points",
        "Safeguarding", "SEND", "Pupil Premium", "Accessibility",
        "Wellbeing", "Pupil Support", "Attendance Concerns",
        "Absence Requests", "First Aid", "Medical Records",
        "Emergency Contacts", "Prevent Duty", "Equality & Diversity",
        "Complaints", "Feedback", "Surveys", "School Council",
        "Breakfast / After-School Club", "Transport",
    ]),
    ("Staff & Communication", [
        "Staff Directory", "Teaching Assistants", "Staff HR",
        "Staff Absence", "Staff Wellbeing", "Recruitment",
        "Appraisals", "CPD", "DBS Checks", "Visitors",
        "Parent Contacts", "Parents' Evenings", "Newsletters",
        "Announcements", "Notifications", "Activity Feed",
        "Email / Messaging", "Letter Templates", "Document Hub",
        "Attachments",
    ]),
    ("Finance", [
        "Dinner Money", "Trips & Payments", "Receipts",
        "Expense Claims", "Funding", "School Census",
    ]),
    ("Reports & Analytics", [
        "Attendance Report", "Progress Report", "KPI Dashboard",
        "Data Dashboard", "Mobile Dashboard", "Audit Reports",
        "Data Export", "Custom Export",
    ]),
    ("Cross-System", [
        "Student Journey", "Promote to Next System",
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
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return "0"


def _submenu(category: str, items: list[str], *, auth=None) -> None:
    while True:
        print(f"\n── {category} ──")
        for i, label in enumerate(items, 1):
            print(f"  {i:2d}) {label}")
        print("   0) Back")
        choice = _prompt("Select: ")
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("Invalid selection.")
            continue
        label = items[int(choice) - 1]
        logger.debug("Primary CLI dispatch: %s / %s", category, label)
        try:
            from education_system.systems.primary.domain.learners.pupils import pupil_cli
            from education_system.systems.primary.domain.learners.pupils.onboarding import onboarding_cli
            from education_system.systems.primary.domain.learners.pupils.bulk_operations import bulk_operations_cli
            from education_system.systems.primary.domain.learners.pupils.leavers import leavers_cli
            from education_system.systems.primary.domain.admissions import admissions_cli
            from education_system.systems.primary.domain.admissions.enrolment import enrolment_cli
            from education_system.systems.primary.domain.governance.mfa import mfa_cli
            # Pastoral
            from education_system.systems.primary.domain.pastoral.behaviour import behaviour_cli
            from education_system.systems.primary.domain.safeguarding import safeguarding_cli
            from education_system.systems.primary.domain.pastoral.send import send_cli
            from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium_cli
            from education_system.systems.primary.domain.pastoral.accessibility import accessibility_cli
            from education_system.systems.primary.domain.pastoral.wellbeing import wellbeing_cli
            from education_system.systems.primary.domain.pastoral.pupil_support import pupil_support_cli
            from education_system.systems.primary.domain.pastoral.attendance_concerns import attendance_concerns_cli
            from education_system.systems.primary.domain.pastoral.absence_requests import absence_requests_cli
            from education_system.systems.primary.domain.pastoral.health.first_aid import first_aid_cli
            from education_system.systems.primary.domain.pastoral.emergency import emergency_cli
            from education_system.systems.primary.domain.safeguarding.prevent_duty import prevent_duty_cli
            from education_system.systems.primary.domain.pastoral.equality_diversity import equality_diversity_cli
            from education_system.systems.primary.domain.pastoral.complaints import complaints_cli
            from education_system.systems.primary.domain.pastoral.feedback import feedback_cli
            from education_system.systems.primary.domain.pastoral.surveys import surveys_cli
            from education_system.systems.primary.domain.pastoral.school_council import school_council_cli
            from education_system.systems.primary.domain.pastoral.transport import transport_cli
            # Academics
            from education_system.systems.primary.domain.academics.academic_year import academic_year_cli
            from education_system.systems.primary.domain.academics.calendar import calendar_cli
            from education_system.systems.primary.domain.academics.subjects import subjects_cli
            from education_system.systems.primary.domain.academics.classes import classes_cli
            from education_system.systems.primary.domain.assessment.phonics import phonics_cli
            from education_system.systems.primary.domain.assessment.reading_levels import reading_levels_cli
            from education_system.systems.primary.domain.academics.enrichment.clubs import clubs_cli
            from education_system.systems.primary.domain.assessment.phonics_screening import phonics_screening_cli
            from education_system.systems.primary.domain.assessment import assessment_cli
            from education_system.systems.primary.domain.assessment.mtc import mtc_cli
            from education_system.systems.primary.domain.assessment.ks1_sats import ks1_sats_cli
            from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats_cli
            from education_system.systems.primary.domain.assessment.eyfs_profile import eyfs_profile_cli
            from education_system.systems.primary.domain.assessment.target_setting import target_setting_cli
            from education_system.systems.primary.domain.operations.reporting.pupil_reports import pupil_reports_cli
            from education_system.systems.primary.domain.staff.class_teachers import class_teachers_cli
            from education_system.systems.primary.domain.pastoral.house_points import house_points_cli
            from education_system.systems.primary.domain.pastoral.health.medical_records import medical_records_cli
            from education_system.systems.primary.domain.operations.daily_care.wraparound import wraparound_cli
            from education_system.systems.primary.domain.staff.teaching_assistants import teaching_assistants_cli
            from education_system.systems.primary.domain.operations.communications.newsletters import newsletters_cli
            from education_system.systems.primary.domain.finance.dinner_money import dinner_money_cli
            from education_system.systems.primary.domain.operations.reporting.attendance_report import attendance_report_cli
            from education_system.systems.primary.domain.operations.reporting.progress_report import progress_report_cli
            from education_system.systems.primary.domain.academics.timetable import timetable_cli
            from education_system.systems.primary.domain.academics.attendance import attendance_cli
            from education_system.systems.primary.domain.academics.lesson_plans import lesson_plans_cli
            from education_system.systems.primary.domain.staff.cover import cover_cli
            from education_system.systems.primary.domain.academics.homework import homework_cli
            from education_system.systems.primary.domain.academics.library import library_cli
            from education_system.systems.primary.domain.academics.year_groups import year_groups_cli
            # Assessment
            from education_system.systems.primary.domain.assessment.intervention_tracking import intervention_tracking_cli
            from education_system.systems.primary.domain.assessment.early_warning import early_warning_cli
            from education_system.systems.primary.domain.assessment.observations import observations_cli
            # Staff comms
            from education_system.systems.primary.domain.staff import staff_cli
            from education_system.systems.primary.domain.staff.staff_hr import staff_hr_cli
            from education_system.systems.primary.domain.staff.departments import departments_cli
            from education_system.systems.primary.domain.staff.staff_absence import staff_absence_cli
            from education_system.systems.primary.domain.staff.staff_wellbeing import staff_wellbeing_cli
            from education_system.systems.primary.domain.staff.recruitment import recruitment_cli
            from education_system.systems.primary.domain.staff.appraisals import appraisals_cli
            from education_system.systems.primary.domain.staff.cpd import cpd_cli
            from education_system.systems.primary.domain.staff.dbs_checks import dbs_checks_cli
            from education_system.systems.primary.domain.operations.visitors import visitors_cli
            from education_system.systems.primary.domain.operations.communications.parent_contacts import parent_contacts_cli
            from education_system.systems.primary.domain.operations.communications.parents_evenings import parents_evenings_cli
            from education_system.systems.primary.domain.operations.communications.announcements import announcements_cli
            from education_system.systems.primary.domain.operations.communications.notifications import notifications_cli
            from education_system.systems.primary.domain.operations.communications.activity_feed import activity_feed_cli
            from education_system.systems.primary.domain.operations.communications.messages import messages_cli
            from education_system.systems.primary.domain.operations.communications.letter_templates import letter_templates_cli
            from education_system.systems.primary.domain.operations.document_hub import document_hub_cli
            from education_system.systems.primary.domain.operations.attachments import attachments_cli
            # Finance
            from education_system.systems.primary.domain.finance.trips import trips_cli
            from education_system.systems.primary.domain.finance.receipts import receipts_cli
            from education_system.systems.primary.domain.finance.expense_claims import expense_claims_cli
            from education_system.systems.primary.domain.finance.funding import funding_cli
            from education_system.systems.primary.domain.governance.compliance.census import census_cli
            # Reports
            from education_system.systems.primary.domain.assessment.progress import progress_cli
            from education_system.systems.primary.domain.operations.reporting.kpi_dashboard import kpi_dashboard_cli
            from education_system.systems.primary.domain.operations.reporting.data_dashboard import data_dashboard_cli
            from education_system.systems.primary.domain.operations.reporting.mobile_dashboard import mobile_dashboard_cli
            from education_system.systems.primary.domain.governance.audit.audit_reports import audit_reports_cli
            from education_system.systems.primary.domain.operations.reporting.data_export import data_export_cli
            from education_system.systems.primary.domain.operations.reporting.custom_export import custom_export_cli
            # Governance
            from education_system.systems.primary.domain.governance.compliance import compliance_cli
            from education_system.systems.primary.domain.governance import governance_cli
            from education_system.systems.primary.domain.governance.policies import policies_cli
            from education_system.systems.primary.domain.governance.gdpr import gdpr_cli
            from education_system.systems.primary.domain.governance.risk_management import risk_management_cli
            from education_system.systems.primary.domain.governance.health_safety import health_safety_cli
            from education_system.systems.primary.domain.operations.assets import assets_cli
            from education_system.systems.primary.domain.operations.todo import todo_cli
            from education_system.systems.primary.domain.governance.user_management import user_management_cli
            # Shared
            from education_system.systems.primary.interfaces.cli import (
                change_password_cli, user_accounts_cli, settings_cli, about_cli,
            )
            if label == "Multi-Language":
                from education_system.platform.features.i18n.selector_cli import show_language_selector_cli
                show_language_selector_cli()
                continue
            from education_system.platform.cross_system import journey_cli
            if journey_cli.dispatch(label, "primary", auth=auth):
                continue
            if (pupil_cli.dispatch(label)
                    or onboarding_cli.dispatch(label)
                    or bulk_operations_cli.dispatch(label)
                    or leavers_cli.dispatch(label)
                    or admissions_cli.dispatch(label)
                    or enrolment_cli.dispatch(label)
                    or behaviour_cli.dispatch(label)
                    or safeguarding_cli.dispatch(label)
                    or send_cli.dispatch(label)
                    or pupil_premium_cli.dispatch(label)
                    or accessibility_cli.dispatch(label)
                    or wellbeing_cli.dispatch(label)
                    or pupil_support_cli.dispatch(label)
                    or attendance_concerns_cli.dispatch(label)
                    or absence_requests_cli.dispatch(label)
                    or first_aid_cli.dispatch(label)
                    or emergency_cli.dispatch(label)
                    or prevent_duty_cli.dispatch(label)
                    or equality_diversity_cli.dispatch(label)
                    or complaints_cli.dispatch(label)
                    or feedback_cli.dispatch(label)
                    or surveys_cli.dispatch(label)
                    or school_council_cli.dispatch(label)
                    or transport_cli.dispatch(label)
                    or academic_year_cli.dispatch(label)
                    or calendar_cli.dispatch(label)
                    or subjects_cli.dispatch(label)
                    or classes_cli.dispatch(label)
                    or phonics_cli.dispatch(label)
                    or reading_levels_cli.dispatch(label)
                    or clubs_cli.dispatch(label)
                    or phonics_screening_cli.dispatch(label)
                    or assessment_cli.dispatch(label)
                    or mtc_cli.dispatch(label)
                    or ks1_sats_cli.dispatch(label)
                    or ks2_sats_cli.dispatch(label)
                    or eyfs_profile_cli.dispatch(label)
                    or target_setting_cli.dispatch(label)
                    or pupil_reports_cli.dispatch(label)
                    or class_teachers_cli.dispatch(label)
                    or house_points_cli.dispatch(label)
                    or medical_records_cli.dispatch(label)
                    or wraparound_cli.dispatch(label)
                    or teaching_assistants_cli.dispatch(label)
                    or newsletters_cli.dispatch(label)
                    or dinner_money_cli.dispatch(label)
                    or attendance_report_cli.dispatch(label)
                    or progress_report_cli.dispatch(label)
                    or timetable_cli.dispatch(label)
                    or attendance_cli.dispatch(label)
                    or lesson_plans_cli.dispatch(label)
                    or cover_cli.dispatch(label)
                    or homework_cli.dispatch(label)
                    or library_cli.dispatch(label)
                    or year_groups_cli.dispatch(label)
                    or intervention_tracking_cli.dispatch(label)
                    or early_warning_cli.dispatch(label)
                    or observations_cli.dispatch(label)
                    or staff_cli.dispatch(label)
                    or staff_hr_cli.dispatch(label)
                    or departments_cli.dispatch(label)
                    or staff_absence_cli.dispatch(label)
                    or staff_wellbeing_cli.dispatch(label)
                    or recruitment_cli.dispatch(label)
                    or appraisals_cli.dispatch(label)
                    or cpd_cli.dispatch(label)
                    or dbs_checks_cli.dispatch(label)
                    or visitors_cli.dispatch(label)
                    or parent_contacts_cli.dispatch(label)
                    or parents_evenings_cli.dispatch(label)
                    or announcements_cli.dispatch(label)
                    or notifications_cli.dispatch(label)
                    or activity_feed_cli.dispatch(label)
                    or messages_cli.dispatch(label)
                    or letter_templates_cli.dispatch(label)
                    or document_hub_cli.dispatch(label)
                    or attachments_cli.dispatch(label)
                    or trips_cli.dispatch(label)
                    or receipts_cli.dispatch(label)
                    or expense_claims_cli.dispatch(label)
                    or funding_cli.dispatch(label)
                    or census_cli.dispatch(label)
                    or progress_cli.dispatch(label)
                    or kpi_dashboard_cli.dispatch(label)
                    or data_dashboard_cli.dispatch(label)
                    or mobile_dashboard_cli.dispatch(label)
                    or audit_reports_cli.dispatch(label)
                    or data_export_cli.dispatch(label)
                    or custom_export_cli.dispatch(label)
                    or compliance_cli.dispatch(label)
                    or governance_cli.dispatch(label)
                    or policies_cli.dispatch(label)
                    or gdpr_cli.dispatch(label)
                    or risk_management_cli.dispatch(label)
                    or health_safety_cli.dispatch(label)
                    or assets_cli.dispatch(label)
                    or todo_cli.dispatch(label)
                    or user_management_cli.dispatch(label, auth=auth)
                    or change_password_cli.dispatch(label, auth=auth)
                    or user_accounts_cli.dispatch(label, auth=auth)
                    or settings_cli.dispatch(label, auth=auth)
                    or about_cli.dispatch(label, auth=auth)
                    or mfa_cli.dispatch(label, auth=auth)):
                continue
        except Exception as e:
            logger.exception("Pupil CLI dispatch failed for label=%s", label)
            print(f"  Error opening {label}: {e}")
            print("  See logs for details.")
            _prompt("Press Enter to continue...")
            continue
        print(f"\n[stub] {label} — not yet implemented.")
        _prompt("Press Enter to continue...")


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

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
        print("   Q) Shut down")
        choice = _prompt("Select: ").lower()
        if choice == "g":
            _switch.request_switch("primary", "gui")
            return
        if choice == "s" and show_system_switch:
            target = pick_system_cli(user, "primary")
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
        if choice == "q":
            confirm = _prompt(f"Shut down the {SYSTEM_NAME}? (y/N): ").lower()
            if confirm != "y":
                continue
            try:
                auth.logout()
            except Exception:
                pass
            _switch.request_exit()
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(CATEGORIES)):
            print("Invalid selection.")
            continue
        cat, items = CATEGORIES[int(choice) - 1]
        _submenu(cat, items, auth=auth)


def run_authenticated(auth) -> int:
    _main_menu(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("primarysch CLI invoked without a shared_auth session")
        raise RuntimeError(
            "primarysch_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Primary-school CLI starting for user=%s role=%s",
                cu.get("username"), role)
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Primary School)")
    raise SystemExit(2)
