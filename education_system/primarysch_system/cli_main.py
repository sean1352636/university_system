"""CLI main menu for the Primary School System.

Mirrors the categorized structure of `gui_main.py`: a top-level list
of categories; selecting a category opens a sub-menu of feature
actions. Every action is a placeholder — real domain wiring goes in
later.
"""

from __future__ import annotations

import logging

from education_system.primarysch_system import SYSTEM_NAME

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
            from education_system.primarysch_system.modules.domain.pupils import pupil_cli
            from education_system.primarysch_system.modules.domain.pupils.onboarding import onboarding_cli
            from education_system.primarysch_system.modules.domain.pupils.bulk_operations import bulk_operations_cli
            from education_system.primarysch_system.modules.domain.pupils.leavers import leavers_cli
            from education_system.primarysch_system.modules.domain.admissions import admissions_cli
            from education_system.primarysch_system.modules.domain.enrolment import enrolment_cli
            from education_system.primarysch_system.modules.domain.mfa import mfa_cli
            # Pastoral
            from education_system.primarysch_system.modules.domain.behaviour import behaviour_cli
            from education_system.primarysch_system.modules.domain.safeguarding import safeguarding_cli
            from education_system.primarysch_system.modules.domain.send import send_cli
            from education_system.primarysch_system.modules.domain.pupil_premium import pupil_premium_cli
            from education_system.primarysch_system.modules.domain.accessibility import accessibility_cli
            from education_system.primarysch_system.modules.domain.wellbeing import wellbeing_cli
            from education_system.primarysch_system.modules.domain.pupil_support import pupil_support_cli
            from education_system.primarysch_system.modules.domain.attendance_concerns import attendance_concerns_cli
            from education_system.primarysch_system.modules.domain.absence_requests import absence_requests_cli
            from education_system.primarysch_system.modules.domain.first_aid import first_aid_cli
            from education_system.primarysch_system.modules.domain.emergency import emergency_cli
            from education_system.primarysch_system.modules.domain.prevent_duty import prevent_duty_cli
            from education_system.primarysch_system.modules.domain.equality_diversity import equality_diversity_cli
            from education_system.primarysch_system.modules.domain.complaints import complaints_cli
            from education_system.primarysch_system.modules.domain.feedback import feedback_cli
            from education_system.primarysch_system.modules.domain.surveys import surveys_cli
            from education_system.primarysch_system.modules.domain.school_council import school_council_cli
            from education_system.primarysch_system.modules.domain.transport import transport_cli
            # Academics
            from education_system.primarysch_system.modules.domain.academic_year import academic_year_cli
            from education_system.primarysch_system.modules.domain.calendar import calendar_cli
            from education_system.primarysch_system.modules.domain.subjects import subjects_cli
            from education_system.primarysch_system.modules.domain.classes import classes_cli
            from education_system.primarysch_system.modules.domain.phonics import phonics_cli
            from education_system.primarysch_system.modules.domain.reading_levels import reading_levels_cli
            from education_system.primarysch_system.modules.domain.clubs import clubs_cli
            from education_system.primarysch_system.modules.domain.phonics_screening import phonics_screening_cli
            from education_system.primarysch_system.modules.domain.assessment import assessment_cli
            from education_system.primarysch_system.modules.domain.mtc import mtc_cli
            from education_system.primarysch_system.modules.domain.ks1_sats import ks1_sats_cli
            from education_system.primarysch_system.modules.domain.ks2_sats import ks2_sats_cli
            from education_system.primarysch_system.modules.domain.eyfs_profile import eyfs_profile_cli
            from education_system.primarysch_system.modules.domain.target_setting import target_setting_cli
            from education_system.primarysch_system.modules.domain.pupil_reports import pupil_reports_cli
            from education_system.primarysch_system.modules.domain.class_teachers import class_teachers_cli
            from education_system.primarysch_system.modules.domain.house_points import house_points_cli
            from education_system.primarysch_system.modules.domain.medical_records import medical_records_cli
            from education_system.primarysch_system.modules.domain.wraparound import wraparound_cli
            from education_system.primarysch_system.modules.domain.teaching_assistants import teaching_assistants_cli
            from education_system.primarysch_system.modules.domain.newsletters import newsletters_cli
            from education_system.primarysch_system.modules.domain.dinner_money import dinner_money_cli
            from education_system.primarysch_system.modules.domain.attendance_report import attendance_report_cli
            from education_system.primarysch_system.modules.domain.progress_report import progress_report_cli
            from education_system.primarysch_system.modules.domain.timetable import timetable_cli
            from education_system.primarysch_system.modules.domain.attendance import attendance_cli
            from education_system.primarysch_system.modules.domain.lesson_plans import lesson_plans_cli
            from education_system.primarysch_system.modules.domain.cover import cover_cli
            from education_system.primarysch_system.modules.domain.homework import homework_cli
            from education_system.primarysch_system.modules.domain.library import library_cli
            from education_system.primarysch_system.modules.domain.year_groups import year_groups_cli
            # Assessment
            from education_system.primarysch_system.modules.domain.intervention_tracking import intervention_tracking_cli
            from education_system.primarysch_system.modules.domain.early_warning import early_warning_cli
            from education_system.primarysch_system.modules.domain.observations import observations_cli
            # Staff comms
            from education_system.primarysch_system.modules.domain.staff import staff_cli
            from education_system.primarysch_system.modules.domain.operations.staff_hr import staff_hr_cli
            from education_system.primarysch_system.modules.domain.departments import departments_cli
            from education_system.primarysch_system.modules.domain.staff_absence import staff_absence_cli
            from education_system.primarysch_system.modules.domain.staff_wellbeing import staff_wellbeing_cli
            from education_system.primarysch_system.modules.domain.recruitment import recruitment_cli
            from education_system.primarysch_system.modules.domain.appraisals import appraisals_cli
            from education_system.primarysch_system.modules.domain.cpd import cpd_cli
            from education_system.primarysch_system.modules.domain.dbs_checks import dbs_checks_cli
            from education_system.primarysch_system.modules.domain.visitors import visitors_cli
            from education_system.primarysch_system.modules.domain.parent_contacts import parent_contacts_cli
            from education_system.primarysch_system.modules.domain.parents_evenings import parents_evenings_cli
            from education_system.primarysch_system.modules.domain.announcements import announcements_cli
            from education_system.primarysch_system.modules.domain.notifications import notifications_cli
            from education_system.primarysch_system.modules.domain.activity_feed import activity_feed_cli
            from education_system.primarysch_system.modules.domain.messages import messages_cli
            from education_system.primarysch_system.modules.domain.letter_templates import letter_templates_cli
            from education_system.primarysch_system.modules.domain.document_hub import document_hub_cli
            from education_system.primarysch_system.modules.domain.attachments import attachments_cli
            # Finance
            from education_system.primarysch_system.modules.domain.trips import trips_cli
            from education_system.primarysch_system.modules.domain.receipts import receipts_cli
            from education_system.primarysch_system.modules.domain.expense_claims import expense_claims_cli
            from education_system.primarysch_system.modules.domain.funding import funding_cli
            from education_system.primarysch_system.modules.domain.census import census_cli
            # Reports
            from education_system.primarysch_system.modules.domain.progress import progress_cli
            from education_system.primarysch_system.modules.domain.kpi_dashboard import kpi_dashboard_cli
            from education_system.primarysch_system.modules.domain.data_dashboard import data_dashboard_cli
            from education_system.primarysch_system.modules.domain.mobile_dashboard import mobile_dashboard_cli
            from education_system.primarysch_system.modules.domain.audit_reports import audit_reports_cli
            from education_system.primarysch_system.modules.domain.data_export import data_export_cli
            from education_system.primarysch_system.modules.domain.custom_export import custom_export_cli
            # Governance
            from education_system.primarysch_system.modules.domain.compliance import compliance_cli
            from education_system.primarysch_system.modules.domain.governance import governance_cli
            from education_system.primarysch_system.modules.domain.policies import policies_cli
            from education_system.primarysch_system.modules.domain.gdpr import gdpr_cli
            from education_system.primarysch_system.modules.domain.risk_management import risk_management_cli
            from education_system.primarysch_system.modules.domain.health_safety import health_safety_cli
            from education_system.primarysch_system.modules.domain.assets import assets_cli
            from education_system.primarysch_system.modules.domain.todo import todo_cli
            from education_system.primarysch_system.modules.domain.user_management import user_management_cli
            # Shared
            from education_system.primarysch_system.modules.shared.cli import (
                change_password_cli, user_accounts_cli, settings_cli, about_cli,
            )
            if label == "Multi-Language":
                from education_system.shared.i18n.selector_cli import show_language_selector_cli
                show_language_selector_cli()
                continue
            from education_system.shared.cross_system import journey_cli
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
