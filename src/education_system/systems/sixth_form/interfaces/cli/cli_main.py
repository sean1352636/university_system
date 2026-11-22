"""CLI main menu for the Sixth Form System.

Mirrors the categorized structure of `gui_main.py`: a top-level list of
categories; selecting a category opens a sub-menu of feature actions.
Each user sees only the categories and entries their role allows
(see ``domain/governance/user_management/access.py``).
"""

from __future__ import annotations

import logging
from education_system.systems.sixth_form import SYSTEM_NAME

logger = logging.getLogger(__name__)

# Same catalogue as the GUI — keep them in sync.
CATEGORIES: list[tuple[str, list[str]]] = [
    ("Student Management", [
        "Student Directory", "Add Student", "Search Students",
        "Advanced Search", "Student Profile", "Admissions",
        "Enrolment", "Onboarding", "Bulk Operations", "Alumni", "Student Exit Interviews",
        "Parent Portal",
    ]),
    ("Academic Management", [
        # One entry, was two: "Calendar" is now a submenu of the
        # academic-year menu, which is where term dates live.
        "Academic Year & Calendar", "Courses", "Subjects & A-Levels",
        "Class Groups", "Timetable", "Timetable Optimiser", "Attendance",
        "Lesson Plans", "Cover", "Cover Agency",
        "Homework & Coursework", "Assignments",
        "Enrichment", "Library", "Study Planner",
        "EPQ", "Work Experience", "Room Booking", "Online Learning Space",
    ]),
    ("Assessment & Grades", [
        "Gradebook", "Predicted Grades", "Baseline Assessment",
        "Target Setting", "ILP", "Intervention Tracking",
        "Early Warning", "Risk Analytics", "Value Added",
        "Mock Exams", "Exam Entries", "Results Day",
        "Exams Office", "Report Cards", "Study Programme",
        "Observations", "Self Assessment",
        "Quality Assurance", "SEF Builder",
    ]),
    ("UCAS & Careers", [
        # One entry, was five: UCAS Applications, UCAS Workflow,
        # Personal Statements, References and University Offers all
        # describe one route and now share one menu.
        "University & UCAS", "University Visits",
        "Apprenticeships", "Careers Guidance",
        "Destinations",
    ]),
    ("Pastoral & Wellbeing", [
        "Tutor Groups", "Tutorial & PSHE Programme", "Contact Log", "Behaviour Log", "Disciplinary",
        "Safeguarding", "Looked-After & Care Leavers", "Young Carers", "Report a Safeguarding Concern", "LADO Allegations",
        "SEND", "Accessibility",
        "Wellbeing", "Student Wellbeing", "Student Support",
        "Peer Mentoring", "Attendance Concerns", "Absence Requests",
        "First Aid", "Medical Records", "Emergency", "Prevent Duty",
        "Equality & Diversity", "Complaints", "Feedback",
        "Surveys", "Student Council", "Transport",
    ]),
    ("Staff & Communication", [
        "Staff Directory", "My Area", "Departments", "Staff HR",
        "Staff Absence", "Staff Timetables & Directed Time", "Staff Wellbeing", "Recruitment", "Staff Exit Interviews",
        "Appraisals", "CPD", "Mandatory Training", "DBS Checks", "Single Central Record", "Visitors",
        "Parent Contacts", "Parents' Evenings",
        "Notices & Bulletins", "Announcements", "Notifications",
        "Activity Feed", "Email / Messaging",
        "Letter Templates", "Document Hub", "Attachments",
    ]),
    ("Finance & Bursaries", [
        "Fees", "Bursary Applications", "Trips & Payments",
        "Receipts", "Online Payments", "Expense Claims", "Funding", "Census ILR",
    ]),
    ("Operations", [
        "Lockers", "Parking Permits", "Catering", "Cashless Catering", "ID Cards", "Site & IT Helpdesk", "Device Loans", "Fire Drills & Premises Checks",
    ]),
    ("Reports & Analytics", [
        "Attendance Report", "Grades Report", "Progress Tracking",
        "KPI Dashboard", "Data Dashboard", "Progress Dashboard",
        "Mobile Dashboard", "Audit Reports", "Data Export",
        "Custom Export",
    ]),
    ("Cross-System", [
        "Student Journey", "Promote to Next System",
    ]),
    ("System", [
        "Change Password", "Multi-Factor Authentication",
        "User Accounts", "User Management",
        "Settings", "Integrations & Backups", "Compliance", "Governance", "Policies",
        "GDPR", "Risk Management", "Automation Rules", "Scheduled Jobs", "Health & Safety", "Assets",
        "Multi-Language", "To-Do", "About",
    ]),
]


def _prompt(msg: str) -> str:
    """Prompt the user. May raise ``SessionTimeoutError`` if they've
    been idle past the configured threshold — callers in the menu
    loops catch that and bail back to the login screen."""
    from education_system.systems.sixth_form.interfaces.cli.idle_timeout import (
        timed_input,
    )
    try:
        return timed_input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return "0"


# Each menu label is handled by the first dispatcher below whose
# ``dispatch(label)`` returns True. They are imported one at a time, on
# first use, so opening a menu no longer imports ~130 modules and one
# module that fails to import only breaks its own entries.
_JOURNEY_DISPATCHER = ("education_system.platform.cross_system", "journey_cli")

# Called as ``dispatch(label, auth=auth)``.
_AUTH_DISPATCHERS: tuple[tuple[str, str], ...] = (
    ("education_system.systems.sixth_form.interfaces.cli",
     "change_password_cli"),
    ("education_system.systems.sixth_form.interfaces.cli",
     "mfa_cli"),
    ("education_system.systems.sixth_form.interfaces.cli",
     "user_accounts_cli"),
    ("education_system.systems.sixth_form.interfaces.cli",
     "settings_cli"),
    ("education_system.systems.sixth_form.interfaces.cli",
     "about_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.user_management",
     "user_management_cli"),
)

# Called as ``dispatch(label)``, in this order.
_DISPATCHERS: tuple[tuple[str, str], ...] = (
    ("education_system.systems.sixth_form.interfaces.cli.staff.staff_hr",
     "single_central_record_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.integrations",
     "integrations_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.exams_office",
     "exams_office_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.report_cards",
     "report_cards_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.qualifications",
     "study_programme_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.learners.students",
     "student_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.admissions.enrolments",
     "enrolment_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.courses",
     "course_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.subjects",
     "subject_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.class_groups",
     "class_group_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.timetable",
     "timetable_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.timetable_optimiser",
     "timetable_optimiser_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.attendance",
     "attendance_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.homework",
     "homework_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.gradebook",
     "gradebook_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.predicted_grades",
     "predicted_grades_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.mock_exams",
     "mock_exam_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.exam_entries",
     "exam_entry_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.exam_results",
     "exam_result_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.university",
     "window"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.apprenticeships",
     "apprenticeship_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.careers",
     "careers_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.university_visits",
     "university_visits_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.destinations",
     "destinations_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.epq",
     "epq_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.progression.work_experience",
     "work_experience_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.room_booking",
     "room_booking_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.health.medical_records",
     "medical_records_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.tutor_groups",
     "tutor_group_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.behaviour",
     "behaviour_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.safeguarding",
     "safeguarding_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.wellbeing",
     "wellbeing_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.student_wellbeing",
     "student_wellbeing_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.safeguarding.prevent_duty",
     "prevent_duty_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.attendance_concerns",
     "attendance_concerns_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.absence_requests",
     "absence_requests_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.academic_year",
     "academic_year_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.accessibility",
     "accessibility_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.activity_feed",
     "activity_feed_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.learners.advanced_search",
     "advanced_search_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.admissions",
     "admissions_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.admissions.onboarding",
     "onboarding_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations",
     "bulk_operations_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.learners.alumni",
     "alumni_menu"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.communications.parent_portal",
     "parent_portal_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.calendar",
     "calendar_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.lesson_plans",
     "lesson_plans_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.cover",
     "cover_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.cover_agency",
     "cover_agency_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.assignments",
     "assignments_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.enrichment",
     "enrichment_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.library",
     "library_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.academics.study_planner",
     "study_planner_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.baseline_assessment",
     "baseline_assessment_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.target_setting",
     "target_setting_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.ilp",
     "ilp_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.intervention_tracking",
     "intervention_tracking_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.value_added",
     "value_added_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.early_warning",
     "early_warning_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.risk_analytics",
     "risk_analytics_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.observations",
     "observations_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.self_assessment",
     "self_assessment_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.quality_assurance",
     "quality_assurance_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.assessment.sef_builder",
     "sef_builder_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.send",
     "send_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.disciplinary",
     "disciplinary_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.student_support",
     "student_support_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.peer_mentoring",
     "peer_mentoring_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.health.first_aid",
     "first_aid_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.emergency",
     "emergency_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.equality_diversity",
     "equality_diversity_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.complaints",
     "complaints_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.feedback",
     "feedback_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.surveys",
     "surveys_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.pastoral.student_council",
     "student_council_cli"),
    ("education_system.systems.sixth_form.domains.operations.interfaces.cli.transport",
     "transport_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.staff_hr",
     "staff_hr_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.departments",
     "departments_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.staff_absence",
     "staff_absence_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.staff_wellbeing",
     "staff_wellbeing_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.recruitment",
     "recruitment_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.appraisals",
     "appraisals_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.cpd",
     "cpd_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff.dbs_checks",
     "dbs_checks_cli"),
    ("education_system.systems.sixth_form.domains.operations.interfaces.cli.visitors",
     "visitors_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.announcements",
     "announcements_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.notifications",
     "notifications_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.letter_templates",
     "letter_templates_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.document_hub",
     "document_hub_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.attachments",
     "attachments_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.census_ilr",
     "census_ilr_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.expense_claims",
     "expense_claims_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.funding",
     "funding_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.staff",
     "staff_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.parent_contacts",
     "parent_contacts_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.parents_evenings",
     "parents_evenings_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.notices",
     "notices_cli"),
    ("education_system.systems.sixth_form.domains.communications.interfaces.cli.messages",
     "messages_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.fees",
     "fees_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.bursaries",
     "bursaries_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.trips",
     "trips_cli"),
    ("education_system.systems.sixth_form.domains.finance.interfaces.cli.receipts",
     "receipts_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.attendance_report",
     "attendance_report_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.grades_report",
     "grades_report_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.progress",
     "progress_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.custom_export",
     "custom_export_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.kpi_dashboard",
     "kpi_dashboard_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.data_dashboard",
     "data_dashboard_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.progress_dashboard",
     "progress_dashboard_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.mobile_dashboard",
     "mobile_dashboard_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.audit.audit_reports",
     "audit_reports_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.operations.reporting.data_export",
     "data_export_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.compliance",
     "compliance_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance",
     "governance_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.policies",
     "policies_cli"),
    ("education_system.systems.sixth_form.domains.operations.interfaces.cli.health_safety",
     "health_safety_cli"),
    ("education_system.systems.sixth_form.domains.operations.interfaces.cli.assets",
     "assets_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.todo",
     "todo_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.gdpr",
     "gdpr_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.risk_management",
     "risk_management_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.automation_rules",
     "automation_rules_cli"),
    ("education_system.systems.sixth_form.interfaces.cli.governance.scheduler",
     "scheduler_cli"),
)

# Entries whose module offers a menu function rather than
# ``dispatch(label)``: label -> (module, function), called with no args.
_MENU_FUNCTIONS: dict[str, tuple[str, str]] = {
    "Student Exit Interviews": ("education_system.systems.sixth_form.interfaces.cli.learners.exit_interviews.exit_interviews_cli",
                              "exit_interviews_menu"),
    "Contact Log": ("education_system.systems.sixth_form.interfaces.cli.pastoral.contact_log.contact_log_cli",
                  "contact_log_menu"),
    "Tutorial & PSHE Programme": ("education_system.systems.sixth_form.interfaces.cli.pastoral.tutorial.tutorial_cli",
                                "tutorial_menu"),
    "Young Carers": ("education_system.systems.sixth_form.interfaces.cli.pastoral.young_carers.young_carers_cli",
                   "young_carers_menu"),
    "Looked-After & Care Leavers": ("education_system.systems.sixth_form.interfaces.cli.pastoral.looked_after.looked_after_cli",
                                  "looked_after_menu"),
    "Cashless Catering": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.catering.cashless_cli",
                        "cashless_catering_menu"),
    "Online Payments": ("education_system.systems.sixth_form.domains.finance.interfaces.cli.online_payments.online_payments_cli",
                      "online_payments_menu"),
    "Fire Drills & Premises Checks": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.health_safety.premises_checks_cli",
                                    "premises_checks_menu"),
    "Device Loans": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.device_loans.device_loans_cli",
                   "device_loans_menu"),
    "Site & IT Helpdesk": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.helpdesk.helpdesk_cli",
                         "helpdesk_menu"),
    "My Area": ("education_system.systems.sixth_form.interfaces.cli.staff.my_area.my_area_cli",
              "my_area_menu"),
    "Staff Exit Interviews": ("education_system.systems.sixth_form.interfaces.cli.staff.staff_hr.exit_interviews_cli",
                      "exit_interviews_menu"),
    "Mandatory Training": ("education_system.systems.sixth_form.interfaces.cli.staff.mandatory_training.mandatory_training_cli",
                         "mandatory_training_menu"),
    "Staff Timetables & Directed Time": ("education_system.systems.sixth_form.interfaces.cli.staff.directed_time.directed_time_cli",
                                       "directed_time_menu"),
    "Online Learning Space": ("education_system.systems.sixth_form.interfaces.cli.academics.class_resources.class_resources_cli",
                            "class_resources_menu"),
    "Lockers": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.lockers.lockers_cli",
                "lockers_menu"),
    "Parking Permits": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.parking.parking_cli",
                        "parking_menu"),
    "Catering": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.catering.catering_cli",
                 "catering_menu"),
    "ID Cards": ("education_system.systems.sixth_form.domains.operations.interfaces.cli.id_cards.id_cards_cli",
                 "id_cards_menu"),
}

_LANGUAGE_SELECTOR = ("education_system.platform.features.i18n.selector_cli", "show_language_selector_cli")

_loaded: dict[tuple[str, str], object] = {}
_broken: set[tuple[str, str]] = set()


def _load(spec: tuple[str, str]):
    """Import ``module.attr`` once; None (logged) if it fails to import."""
    if spec in _loaded:
        return _loaded[spec]
    if spec in _broken:
        return None
    import importlib
    try:
        # Most entries name a submodule; a few name a function.
        name = f"{spec[0]}.{spec[1]}"
        try:
            obj = importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name != name:
                raise
            obj = getattr(importlib.import_module(spec[0]), spec[1])
    except Exception:
        logger.exception("Sixth-form CLI module failed to load: %s.%s", *spec)
        _broken.add(spec)
        return None
    _loaded[spec] = obj
    return obj


def _dispatch(label: str, *, auth=None) -> bool:
    if label in _MENU_FUNCTIONS:
        menu = _load(_MENU_FUNCTIONS[label])
        if menu is None:
            return False
        menu()
        return True
    journey = _load(_JOURNEY_DISPATCHER)
    if journey is not None and journey.dispatch(label, "sixth_form", auth=auth):
        return True
    for spec in _AUTH_DISPATCHERS:
        mod = _load(spec)
        if mod is not None and mod.dispatch(label, auth=auth):
            return True
    if label == "Multi-Language":
        selector = _load(_LANGUAGE_SELECTOR)
        if selector is not None:
            selector()
            return True
    for spec in _DISPATCHERS:
        mod = _load(spec)
        if mod is not None and mod.dispatch(label):
            return True
    return False


def _visible_categories(principal) -> list[tuple[str, list[str]]]:
    out = []
    for cat, items in CATEGORIES:
        allowed = [lbl for lbl in items if principal.can_open(lbl)]
        if allowed:
            out.append((cat, allowed))
    return out


def _submenu(category: str, items: list[str], *, auth=None) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
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
        if not access.current().can_open(label):
            print(f"\n  Your account doesn't have access to {label}.")
            continue
        logger.debug("Sixth-form CLI dispatch: %s / %s", category, label)
        if _dispatch(label, auth=auth):
            continue
        print(f"\n  {label} could not be opened (see the log for details).")
        _prompt("Press Enter to continue...")


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli
    from education_system.systems.sixth_form.interfaces.cli.idle_timeout import (
        SessionTimeoutError, timeout_minutes,
    )
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    user = auth.current_user or {}
    show_system_switch = is_superadmin(user)
    principal = access.current()
    if principal.username != user.get("username"):
        principal = access.from_auth(auth)
        access.set_current(principal)
    if not principal.is_staff:
        # Reached by a GUI -> CLI switch; the entry point already
        # routed parents and students to their own menus.
        print(f"\n  The {SYSTEM_NAME} staff menu is only for college staff.\n")
        return
    categories = _visible_categories(principal)
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {user.get('username', '?')}")
        for i, (cat, _items) in enumerate(categories, 1):
            print(f"  {i:2d}) {cat}")
        print("   G) Switch to GUI")
        if show_system_switch:
            print("   S) Switch System")
        print("   L) Logout (return to login)")
        print("   Q) Shut down")
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
            _switch.request_switch("sixth_form", "gui")
            return
        if choice == "s" and show_system_switch:
            target = pick_system_cli(user, "sixth_form")
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(categories)):
            print("Invalid selection.")
            continue
        cat, items = categories[int(choice) - 1]
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

    Called by `python -m education_system` after the universal login succeeds. No per-system
    login is shown — `shared_auth.current_user` must already be set.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("sixthform CLI invoked without a shared_auth session")
        raise RuntimeError(
            "sixthform_system CLI must be launched via python -m education_system — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Sixth-form CLI starting for user=%s role=%s",
                cu.get("username"), role)

    # The staff menu reaches the whole college, so only staff get it,
    # filtered to the areas their job needs. Parents and students get
    # their own menus covering only their own records.
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    principal = access.from_auth(shared_auth, role)
    access.set_current(principal)
    if principal.is_parent:
        return _run_parent_portal(shared_auth, cu)
    if principal.is_student:
        return _run_student_portal(shared_auth, principal)
    if not principal.is_staff:
        logger.warning("Refusing sixth-form staff CLI for user=%s role=%s",
                       cu.get("username"), role)
        print(f"\n  The {SYSTEM_NAME} staff menu is only for college staff.")
        print(f"  Your account is signed in as '{role or 'no role'}'.\n")
        return 0

    return run_authenticated(shared_auth)


def _run_student_portal(shared_auth, principal) -> int:
    """Run the student's own menu — never the staff menu."""
    if not principal.student_id:
        logger.warning("No student record for signed-in student '%s'",
                       principal.username)
        print(f"\n  There is no sixth form student record for "
              f"'{principal.username}'.")
        print("  Please contact the college office.\n")
        return 0
    from education_system.systems.sixth_form.interfaces.cli.portals import (
        student_portal_cli,
    )
    logger.info("Student portal (CLI) starting for %s", principal.student_id)
    return student_portal_cli.run(shared_auth, principal)


def _run_parent_portal(shared_auth, current_user: dict) -> int:
    """Run the parent-facing menu, or explain why it can't run."""
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
        parent_portal,
    )
    from education_system.systems.sixth_form.interfaces.cli.operations.communications.parent_portal import (
        parent_home_cli,
    )

    username = current_user.get("username", "")
    account = parent_portal.account_for_username(username)
    if account is None:
        logger.warning("No parent-portal account for signed-in user '%s'", username)
        print(f"\n  There is no parent portal record for '{username}' yet.\n")
        print("  Please contact the college office so they can set up your")
        print("  account and link your child's record.\n")
        return 0

    logger.info("Parent portal (CLI) starting for %s (account %s)",
                username, account.account_id)
    return parent_home_cli.run(shared_auth, account)


if __name__ == "__main__":
    print("Launch via: python -m education_system --cli  (then choose Sixth Form)")
    raise SystemExit(2)
