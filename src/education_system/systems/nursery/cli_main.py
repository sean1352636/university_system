"""CLI main menu for the Nursery System.

Mirrors the categorized structure of `gui_main.py`: a top-level list of
categories; selecting one opens a sub-menu of feature actions. The menu
structure is shared via `nursery/menu.py`, so the CLI and GUI
always present the same options. Every action is a placeholder — Early
Years domain wiring goes in later.
"""

from __future__ import annotations

import logging

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.nursery import SYSTEM_NAME, SYSTEM_SLUG
from education_system.systems.nursery.domain import access
from education_system.systems.nursery.menu import NAV_CATEGORIES

logger = logging.getLogger(__name__)


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
        logger.debug("Nursery CLI dispatch: %s / %s", category, label)
        if not principal.can_open(label):
            logger.warning("Refused %s to user=%s role=%s", label,
                           principal.username, principal.role)
            print(f"  {principal.denied_message(label)}")
            continue
        try:
            from education_system.platform.cross_system import journey_cli
            if journey_cli.dispatch(label, "nursery", auth=auth):
                continue
            from education_system.systems.nursery.interfaces.cli.learners.children import (
                children_cli,
            )
            if children_cli.dispatch(label):
                continue
            if _dispatch_local_cli(label):
                continue
            if _dispatch_system_cli(label, auth):
                continue
            if _dispatch_ported_cli(label):
                continue
        except Exception as e:
            logger.exception("Nursery CLI handler failed for %s", label)
            print(f"  Error opening {label}: {e}")
            _prompt("Press Enter to continue...")
            continue
        print(f"\n[stub] {label} — not yet implemented.")
        _prompt("Press Enter to continue...")


# Nursery menu label -> (module dotted path, dispatch-callable name) for the
# Children & Admissions domain modules implemented for this system. Each module
# exposes a ``dispatch(label)`` that runs its manager for the matching label.
_LOCAL_CLI: dict[str, str] = {
    "Admissions & Waiting List":        "admissions.admissions_cli",
    "Registration & Enrolment":         "admissions.enrolment.enrolment_cli",
    "Rooms & Age Groups":               "operations.rooms.rooms_cli",
    "Key Person Assignment":            "staff.key_persons.key_persons_cli",
    "Funded Hours (15/30 & 2-Year-Old)": "finance.funded_hours.funded_hours_cli",
    "Sessions & Bookings":              "operations.sessions.sessions_cli",
    "Settling-In":                      "admissions.settling_in.settling_in_cli",
    "Transition to School":             "progression.transitions.transitions_cli",
    "Leavers":                          "learners.leavers.leavers_cli",
    "Staff : Child Ratios":             "operations.ratios.ratios_cli",
    "Live Ratio Alerts":                "operations.ratio_alerts.ratio_alerts_cli",
    "Staff Rota":                       "staff.rota.rota_cli",
    "Qualifications & Training":         "staff.qualifications.qualifications_cli",
    "Paediatric First Aid":             "pastoral.health.first_aid.first_aid_cli",
    "Invoices & Fees":                  "finance.invoices.invoices_cli",
    "Funded Hours Claims":              "finance.funding_claims.funding_claims_cli",
    "Payments":                         "finance.payments.payments_cli",
    "Tax-Free Childcare / Vouchers":    "finance.childcare_vouchers.childcare_vouchers_cli",
    "Sibling Discounts":                "finance.discounts.discounts_cli",
    "Occupancy & Income":               "operations.occupancy.occupancy_cli",
    "Parent Contacts":                  "operations.communications.parent_contacts.parent_contacts_cli",
    "Emergency Contacts":               "learners.emergency_contacts.emergency_contacts_cli",
    "Permissions & Consents":           "governance.consents.consents_cli",
    "Parent Messaging":                 "operations.communications.messaging.messaging_cli",
    "Daily Updates":                    "operations.communications.daily_updates.daily_updates_cli",
    "Newsletters":                      "operations.communications.newsletters.newsletters_cli",
    "Parent Meetings":                  "operations.communications.parent_meetings.parent_meetings_cli",
    "Safeguarding / Child Protection":  "safeguarding.safeguarding_cli",
    "Designated Safeguarding Lead":     "safeguarding.dsl.dsl_cli",
    "Welfare Requirements":             "pastoral.welfare.welfare_cli",
    "SEND & Additional Needs":          "pastoral.send.send_cli",
    "EHC Plans":                        "pastoral.send.ehc_plans.ehc_plans_cli",
    "Looked-After Children":            "safeguarding.looked_after.looked_after_cli",
    "Risk Assessments":                 "governance.risk_assessments.risk_assessments_cli",
    "Prevent Duty":                     "safeguarding.prevent_duty.prevent_duty_cli",
    "Concerns & Referrals":             "safeguarding.concerns.concerns_cli",
    "Wellbeing":                        "pastoral.wellbeing.wellbeing_cli",
    "EYFS Profile":                     "assessment.eyfs_profile.eyfs_profile_cli",
    "Development Tracking (Prime & Specific Areas)": "assessment.development_tracking.development_tracking_cli",
    "Observations":                     "assessment.observations.observations_cli",
    "Learning Journeys":                "academics.learning_journeys.learning_journeys_cli",
    "Next Steps Planning":              "academics.next_steps.next_steps_cli",
    "2-Year-Old Progress Check":        "assessment.progress_check_2yr.progress_check_2yr_cli",
    "Characteristics of Effective Learning": "academics.effective_learning.effective_learning_cli",
    "Activity & Curriculum Planning":   "academics.curriculum_planning.curriculum_planning_cli",
    "Cohort Tracking":                  "assessment.cohort_tracking.cohort_tracking_cli",
    "Photos & Evidence":                "assessment.evidence.evidence_cli",
    # Daily Care & Routines
    "Daily Register":                   "academics.attendance.daily_register.daily_register_cli",
    "Sign In / Sign Out":               "academics.attendance.sign_in_out.sign_in_out_cli",
    "Collections & Late Pickup":        "operations.daily_care.collections.collections_cli",
    "Daily Diary":                      "operations.daily_care.daily_diary.daily_diary_cli",
    "Sleep Log":                        "operations.daily_care.sleep_log.sleep_log_cli",
    "Nappy / Toileting Log":            "operations.daily_care.toileting_log.toileting_log_cli",
    "Meals & Menus":                    "operations.daily_care.meals.meals_cli",
    "Bottle Feeds":                     "operations.daily_care.bottle_feeds.bottle_feeds_cli",
    "Allergies & Dietary Requirements": "pastoral.health.allergies.allergies_cli",
    "Accident & Incident Log":          "pastoral.health.accident_log.accident_log_cli",
    "Existing Injuries Log":            "pastoral.health.existing_injuries.existing_injuries_cli",
    "Medication Log":                   "pastoral.health.medication_log.medication_log_cli",
}


def _dispatch_local_cli(label: str) -> bool:
    """Run a local domain module's CLI for ``label``; return True if handled."""
    module_path = _LOCAL_CLI.get(label)
    if module_path is None:
        return False
    import importlib
    mod = importlib.import_module(
        f"education_system.systems.nursery.interfaces.cli.{module_path}")
    logger.debug("Nursery CLI dispatch (local): %s -> %s", label, module_path)
    return bool(mod.dispatch(label))


# Nursery menu label -> fully-qualified module path for the "System" category
# features (account/auth/settings/about). Each exposes
# ``dispatch(label, auth=...)`` and is imported lazily.
#
# These were relative fragments interpolated into
# ``education_system.systems.nursery.__init__.<path>``, which is not an
# importable module path — every entry raised ModuleNotFoundError, so the
# whole System category was dead. Absolute paths, verified against the tree.
_SYSTEM_CLI: dict[str, str] = {
    # Email / Messaging lives here (not in _LOCAL_CLI) because it needs the
    # signed-in ``auth`` to drive its Cross-System Email option.
    "Email / Messaging":
        "education_system.systems.nursery.interfaces.cli.operations.communications"
        ".email_centre.email_centre_cli",
    # Change Password is now the shared platform flow, not a nursery copy.
    "Change Password":
        "education_system.platform.delivery.cli.change_password_cli",
    "Multi-Factor Authentication":
        "education_system.platform.delivery.cli.mfa_setup_cli",
    "User Accounts":
        "education_system.systems.nursery.interfaces.cli.user_accounts_cli",
    # User Management and Multi-Language run the shared features (auth.db
    # roles/access; the platform i18n selector) through the nursery's
    # System entry points in interfaces/.
    "User Management":
        "education_system.systems.nursery.interfaces.cli.user_management_cli",
    "Multi-Language":
        "education_system.systems.nursery.interfaces.cli.multi_language_cli",
    "Settings":
        "education_system.systems.nursery.interfaces.cli.settings_cli",
    "About":
        "education_system.systems.nursery.interfaces.cli.about_cli",
}


def _dispatch_system_cli(label: str, auth=None) -> bool:
    """Run a System-category CLI for ``label``; return True if handled."""
    module_path = _SYSTEM_CLI.get(label)
    if module_path is None:
        return False
    import importlib
    mod = importlib.import_module(module_path)
    logger.debug("Nursery CLI dispatch (system): %s -> %s", label, module_path)
    return bool(mod.dispatch(label, auth=auth))


# Nursery menu label -> (module dotted path, run-callable name) for the
# cross-cutting modules ported from the Primary School System. Imported lazily
# so a single broken module can't stop the launcher from starting.
_PORTED_CLI: dict[str, tuple[str, str]] = {
    "Policies & Procedures":     ("governance.policies.policies_cli", "run"),
    "GDPR":                      ("governance.gdpr.gdpr_cli", "run"),
    "Recruitment":               ("staff.recruitment.recruitment_cli", "run"),
    "Complaints":                ("pastoral.complaints.complaints_cli", "run"),
    "Feedback & Surveys":        ("pastoral.feedback.feedback_cli", "run"),
    "Expense Claims":            ("finance.expense_claims.expense_claims_cli", "run"),
    "Audit Reports":             ("governance.audit.audit_reports.audit_reports_cli", "run"),
    "Staff Absence":             ("staff.staff_absence.staff_absence_cli", "run"),
    "Staff Directory":           ("staff.staff_cli", "run"),
    "Visitors":                  ("operations.visitors.visitors_cli", "run"),
    "DBS Checks":                ("staff.dbs_checks.dbs_checks_cli", "run"),
    "Supervisions & Appraisals": ("staff.appraisals.appraisals_cli", "run"),
    # Compliance & Reports
    "Ofsted Readiness":          ("governance.compliance.ofsted.ofsted_cli", "run"),
    "EYFS Compliance":           ("governance.compliance.eyfs_compliance.eyfs_compliance_cli", "run"),
    "Attendance Report":         ("operations.reporting.attendance_report.attendance_report_cli", "run"),
    "Occupancy Report":          ("operations.reporting.occupancy_report.occupancy_report_cli", "run"),
    "Funding Report":            ("operations.reporting.funding_report.funding_report_cli", "run"),
    "Accident / Incident Report": (
        "pastoral.health.accident_report.accident_report_cli", "run"),
    "Data Export":               ("operations.reporting.data_export.data_export_cli", "run"),
}


def _dispatch_ported_cli(label: str) -> bool:
    """Run a ported module's CLI for ``label``; return True if handled."""
    entry = _PORTED_CLI.get(label)
    if entry is None:
        return False
    module_path, func_name = entry
    import importlib
    mod = importlib.import_module(
        f"education_system.systems.nursery.interfaces.cli.{module_path}")
    logger.debug("Nursery CLI dispatch (ported): %s -> %s", label, module_path)
    getattr(mod, func_name)()
    return True


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

    user = auth.current_user or {}
    show_system_switch = is_superadmin(user)
    principal = access.current_for(auth)
    categories = principal.filter_menu(NAV_CATEGORIES)
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
            _switch.request_switch(SYSTEM_SLUG, "gui")
            return
        if choice == "s" and show_system_switch:
            target = pick_system_cli(user, SYSTEM_SLUG)
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
        logger.error("nursery CLI invoked without a shared_auth session")
        raise RuntimeError(
            "nursery_system CLI must be launched via python -m education_system — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Nursery CLI starting for user=%s role=%s",
                cu.get("username"), role)
    from education_system.systems.nursery.infrastructure.database import init_db
    init_db()
    access.set_current(access.from_auth(shared_auth, role))
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python -m education_system --cli  (then choose Nursery)")
    raise SystemExit(2)
