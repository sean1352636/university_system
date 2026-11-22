"""CLI main menu for the Primary School System.

Mirrors the categorized structure of `gui_main.py`: a top-level list
of categories; selecting a category opens a sub-menu of feature
actions. Each label is routed in ``_submenu`` to its module's
``dispatch``; Cross-System entries go to the shared platform menus.
"""

from __future__ import annotations

import logging

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.primary import SYSTEM_NAME
from education_system.systems.primary.domain import access

logger = logging.getLogger(__name__)

CATEGORIES: list[tuple[str, list[str]]] = [
    ("Pupil Management", [
        "Pupil Directory", "Add Pupil", "Search Pupils",
        "Pupil Profile", "Admissions", "Year Group Enrolment",
        "Onboarding", "Bulk Operations", "Leavers", "Year 6 Transition",
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
        "Student Journey", "Promote to Next System", "Referrals to Alternative Provision",
        "SEND Service Requests", "Local Authority",
        "Analytics Dashboard", "Cross-System Calendar", "Central Admin Portal",
        "GDPR Compliance", "Shared Documents", "Pupil Self-Service", "Certificates",
    ]),
    ("System", [
        "Change Password", "Multi-Factor Authentication",
        "User Accounts", "User Management",
        "Settings", "Compliance", "Governance", "Policies",
        "GDPR", "Risk Management", "Health & Safety", "Assets",
        "Multi-Language", "To-Do", "About",
    ]),
]


#: Cross-System entries handled by the shared platform terminal menus — the
#: same screens the GUI's Cross-System category opens.
_PLATFORM_MENUS: dict[str, tuple[str, str]] = {
    "Analytics Dashboard": ("education_system.platform.features.analytics.analytics_cli", "run"),
    "Cross-System Calendar": ("education_system.platform.features.calendar.calendar_cli", "run"),
    "Central Admin Portal": ("education_system.platform.delivery.portals.admin.admin_cli", "run"),
    "GDPR Compliance": ("education_system.platform.governance.gdpr.gdpr_cli", "run"),
    "Shared Documents": ("education_system.platform.features.documents.document_cli", "run"),
    "Pupil Self-Service": ("education_system.platform.delivery.portals.student.portal_cli", "run"),
    "Certificates": ("education_system.platform.features.certificates.certificates_cli", "run"),
}


def _platform_menu_kwargs(label: str) -> dict:
    """Certificates keep their register in the primary database; without a
    ``db_path`` the service falls back to a throwaway in-memory database."""
    if label == "Certificates":
        from education_system import paths
        return {"db_path": str(paths.PRIMARY_PUPILS_DB)}
    return {}


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return "0"


def _logout(auth) -> None:
    """Sign out and return to login: the L key and the idle timeout both end here."""
    from education_system import switch as _switch
    try:
        auth.logout()
    except Exception:
        pass
    _switch.request_logout("cli")


def _submenu(category: str, items: list[str], *, auth=None) -> None:
    principal = access.current_for(auth)
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
        if not principal.can_open(label):
            logger.warning("Refused %s to user=%s role=%s", label,
                           principal.username, principal.role)
            print(f"  {principal.denied_message(label)}")
            continue
        if label in access.POLICY.own_labels:
            from education_system.systems.primary.interfaces.cli.learners.own_records import (
                own_records_cli,
            )
            own_records_cli.dispatch(label, auth=auth)
            continue
        if principal.opens_raise_only(label):
            from education_system.systems.primary.interfaces.cli.safeguarding import safeguarding_cli
            safeguarding_cli.raise_concern()
            continue
        try:
            from education_system.systems.primary.interfaces.cli.learners.pupils import pupil_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.onboarding import onboarding_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.bulk_operations import bulk_operations_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.leavers import leavers_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.year6_transition import year6_transition_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.ap_referrals import ap_referrals_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.send_requests import send_requests_cli
            from education_system.systems.primary.interfaces.cli.learners.pupils.local_authority import local_authority_cli
            from education_system.systems.primary.interfaces.cli.admissions import admissions_cli
            from education_system.systems.primary.interfaces.cli.admissions.enrolment import enrolment_cli
            from education_system.platform.delivery.cli import mfa_setup_cli as mfa_cli
            # Pastoral
            from education_system.systems.primary.interfaces.cli.pastoral.behaviour import behaviour_cli
            from education_system.systems.primary.interfaces.cli.safeguarding import safeguarding_cli
            from education_system.systems.primary.interfaces.cli.pastoral.send import send_cli
            from education_system.systems.primary.interfaces.cli.finance.pupil_premium import pupil_premium_cli
            from education_system.systems.primary.interfaces.cli.pastoral.accessibility import accessibility_cli
            from education_system.systems.primary.interfaces.cli.pastoral.wellbeing import wellbeing_cli
            from education_system.systems.primary.interfaces.cli.pastoral.pupil_support import pupil_support_cli
            from education_system.systems.primary.interfaces.cli.pastoral.attendance_concerns import attendance_concerns_cli
            from education_system.systems.primary.interfaces.cli.pastoral.absence_requests import absence_requests_cli
            from education_system.systems.primary.interfaces.cli.pastoral.health.first_aid import first_aid_cli
            from education_system.systems.primary.interfaces.cli.pastoral.emergency import emergency_cli
            from education_system.systems.primary.interfaces.cli.safeguarding.prevent_duty import prevent_duty_cli
            from education_system.systems.primary.interfaces.cli.pastoral.equality_diversity import equality_diversity_cli
            from education_system.systems.primary.interfaces.cli.pastoral.complaints import complaints_cli
            from education_system.systems.primary.interfaces.cli.pastoral.feedback import feedback_cli
            from education_system.systems.primary.interfaces.cli.pastoral.surveys import surveys_cli
            from education_system.systems.primary.interfaces.cli.pastoral.school_council import school_council_cli
            from education_system.systems.primary.interfaces.cli.pastoral.transport import transport_cli
            # Academics
            from education_system.systems.primary.interfaces.cli.academics.academic_year import academic_year_cli
            from education_system.systems.primary.interfaces.cli.academics.calendar import calendar_cli
            from education_system.systems.primary.interfaces.cli.academics.subjects import subjects_cli
            from education_system.systems.primary.interfaces.cli.academics.classes import classes_cli
            from education_system.systems.primary.interfaces.cli.assessment.phonics import phonics_cli
            from education_system.systems.primary.interfaces.cli.assessment.reading_levels import reading_levels_cli
            from education_system.systems.primary.interfaces.cli.academics.enrichment.clubs import clubs_cli
            from education_system.systems.primary.interfaces.cli.assessment.phonics_screening import phonics_screening_cli
            from education_system.systems.primary.interfaces.cli.assessment import assessment_cli
            from education_system.systems.primary.interfaces.cli.assessment.mtc import mtc_cli
            from education_system.systems.primary.interfaces.cli.assessment.ks1_sats import ks1_sats_cli
            from education_system.systems.primary.interfaces.cli.assessment.ks2_sats import ks2_sats_cli
            from education_system.systems.primary.interfaces.cli.assessment.eyfs_profile import eyfs_profile_cli
            from education_system.systems.primary.interfaces.cli.assessment.target_setting import target_setting_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.pupil_reports import pupil_reports_cli
            from education_system.systems.primary.interfaces.cli.staff.class_teachers import class_teachers_cli
            from education_system.systems.primary.interfaces.cli.pastoral.house_points import house_points_cli
            from education_system.systems.primary.interfaces.cli.pastoral.health.medical_records import medical_records_cli
            from education_system.systems.primary.interfaces.cli.operations.daily_care.wraparound import wraparound_cli
            from education_system.systems.primary.interfaces.cli.staff.teaching_assistants import teaching_assistants_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.newsletters import newsletters_cli
            from education_system.systems.primary.interfaces.cli.finance.dinner_money import dinner_money_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.attendance_report import attendance_report_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.progress_report import progress_report_cli
            from education_system.systems.primary.interfaces.cli.academics.timetable import timetable_cli
            from education_system.systems.primary.interfaces.cli.academics.attendance import attendance_cli
            from education_system.systems.primary.interfaces.cli.academics.lesson_plans import lesson_plans_cli
            from education_system.systems.primary.interfaces.cli.staff.cover import cover_cli
            from education_system.systems.primary.interfaces.cli.academics.homework import homework_cli
            from education_system.systems.primary.interfaces.cli.academics.library import library_cli
            from education_system.systems.primary.interfaces.cli.academics.year_groups import year_groups_cli
            # Assessment
            from education_system.systems.primary.interfaces.cli.assessment.intervention_tracking import intervention_tracking_cli
            from education_system.systems.primary.interfaces.cli.assessment.early_warning import early_warning_cli
            from education_system.systems.primary.interfaces.cli.assessment.observations import observations_cli
            # Staff comms
            from education_system.systems.primary.interfaces.cli.staff import staff_cli
            from education_system.systems.primary.interfaces.cli.staff.staff_hr import staff_hr_cli
            from education_system.systems.primary.interfaces.cli.staff.departments import departments_cli
            from education_system.systems.primary.interfaces.cli.staff.staff_absence import staff_absence_cli
            from education_system.systems.primary.interfaces.cli.staff.staff_wellbeing import staff_wellbeing_cli
            from education_system.systems.primary.interfaces.cli.staff.recruitment import recruitment_cli
            from education_system.systems.primary.interfaces.cli.staff.appraisals import appraisals_cli
            from education_system.systems.primary.interfaces.cli.staff.cpd import cpd_cli
            from education_system.systems.primary.interfaces.cli.staff.dbs_checks import dbs_checks_cli
            from education_system.systems.primary.interfaces.cli.operations.visitors import visitors_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.parent_contacts import parent_contacts_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.parents_evenings import parents_evenings_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.announcements import announcements_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.notifications import notifications_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.activity_feed import activity_feed_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.messages import messages_cli
            from education_system.systems.primary.interfaces.cli.operations.communications.letter_templates import letter_templates_cli
            from education_system.systems.primary.interfaces.cli.operations.document_hub import document_hub_cli
            from education_system.systems.primary.interfaces.cli.operations.attachments import attachments_cli
            # Finance
            from education_system.systems.primary.interfaces.cli.finance.trips import trips_cli
            from education_system.systems.primary.interfaces.cli.finance.receipts import receipts_cli
            from education_system.systems.primary.interfaces.cli.finance.expense_claims import expense_claims_cli
            from education_system.systems.primary.interfaces.cli.finance.funding import funding_cli
            from education_system.systems.primary.interfaces.cli.governance.compliance.census import census_cli
            # Reports
            from education_system.systems.primary.interfaces.cli.assessment.progress import progress_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.kpi_dashboard import kpi_dashboard_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.data_dashboard import data_dashboard_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.mobile_dashboard import mobile_dashboard_cli
            from education_system.systems.primary.interfaces.cli.governance.audit.audit_reports import audit_reports_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.data_export import data_export_cli
            from education_system.systems.primary.interfaces.cli.operations.reporting.custom_export import custom_export_cli
            # Governance
            from education_system.systems.primary.interfaces.cli.governance.compliance import compliance_cli
            from education_system.systems.primary.interfaces.cli.governance import governance_cli
            from education_system.systems.primary.interfaces.cli.governance.policies import policies_cli
            from education_system.systems.primary.interfaces.cli.governance.gdpr import gdpr_cli
            from education_system.systems.primary.interfaces.cli.governance.risk_management import risk_management_cli
            from education_system.systems.primary.interfaces.cli.governance.health_safety import health_safety_cli
            from education_system.systems.primary.interfaces.cli.operations.assets import assets_cli
            from education_system.systems.primary.interfaces.cli.operations.todo import todo_cli
            from education_system.systems.primary.interfaces.cli.governance.user_management import user_management_cli
            # Shared
            from education_system.platform.delivery.cli import change_password_cli
            from education_system.systems.primary.interfaces.cli import (
                user_accounts_cli,
                settings_cli,
                about_cli,
            )
            if label == "Multi-Language":
                from education_system.platform.features.i18n.selector_cli import show_language_selector_cli
                show_language_selector_cli()
                continue
            from education_system.platform.cross_system import journey_cli
            if journey_cli.dispatch(label, "primary", auth=auth):
                continue
            platform_menu = _PLATFORM_MENUS.get(label)
            if platform_menu is not None:
                module_name, func = platform_menu
                import importlib
                getattr(importlib.import_module(module_name), func)(
                    auth=auth, **_platform_menu_kwargs(label))
                continue
            if (pupil_cli.dispatch(label)
                    or onboarding_cli.dispatch(label)
                    or bulk_operations_cli.dispatch(label)
                    or leavers_cli.dispatch(label)
                    or year6_transition_cli.dispatch(label)
                    or ap_referrals_cli.dispatch(label)
                    or send_requests_cli.dispatch(label)
                    or local_authority_cli.dispatch(label)
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
                    or parent_contacts_cli.dispatch(label, auth=auth)
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
    principal = access.current_for(auth)
    categories = principal.visible_menu(CATEGORIES, labels_only=True)
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {user.get('username', '?')}")
        if principal.notice():
            print(f"\n{principal.notice()}\n")
        for i, (cat, _items) in enumerate(categories, 1):
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
            _logout(auth)
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(categories)):
            print("Invalid selection.")
            continue
        cat, items = categories[int(choice) - 1]
        _submenu(cat, items, auth=auth)


def run_authenticated(auth) -> int:
    with idle_session(lambda: _logout(auth)):
        _main_menu(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("primarysch CLI invoked without a shared_auth session")
        raise RuntimeError(
            "primarysch_system CLI must be launched via python -m education_system — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Primary-school CLI starting for user=%s role=%s",
                cu.get("username"), role)
    access.set_current(access.from_auth(shared_auth, role))
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python -m education_system --cli  (then choose Primary School)")
    raise SystemExit(2)
