"""CLI main menu for the Nursery System.

Mirrors the categorized structure of `main_gui.py`: a top-level list of
categories; selecting one opens a sub-menu of feature actions. The menu
structure is shared via `nursery_system/menu.py`, so the CLI and GUI
always present the same options. Every action is a placeholder — Early
Years domain wiring goes in later.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery import SYSTEM_NAME, SYSTEM_SLUG
from education_system.systems.nursery.menu import NAV_CATEGORIES

logger = logging.getLogger(__name__)


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
        logger.debug("Nursery CLI dispatch: %s / %s", category, label)
        if label == "Multi-Language":
            try:
                from education_system.platform.features.i18n.selector_cli import (
                    show_language_selector_cli,
                )
                show_language_selector_cli()
                continue
            except Exception as e:
                logger.exception("Language selector failed")
                print(f"  Error opening {label}: {e}")
                _prompt("Press Enter to continue...")
                continue
        try:
            from education_system.platform.cross_system import journey_cli
            if journey_cli.dispatch(label, "nursery", auth=auth):
                continue
            from education_system.systems.nursery.domain.learners.children import (
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
    "Registration & Enrolment":         "enrolment.enrolment_cli",
    "Rooms & Age Groups":               "rooms.rooms_cli",
    "Key Person Assignment":            "key_persons.key_persons_cli",
    "Funded Hours (15/30 & 2-Year-Old)": "funded_hours.funded_hours_cli",
    "Sessions & Bookings":              "sessions.sessions_cli",
    "Settling-In":                      "settling_in.settling_in_cli",
    "Transition to School":             "transitions.transitions_cli",
    "Leavers":                          "leavers.leavers_cli",
    "Staff : Child Ratios":             "ratios.ratios_cli",
    "Live Ratio Alerts":                "ratio_alerts.ratio_alerts_cli",
    "Staff Rota":                       "rota.rota_cli",
    "Qualifications & Training":         "qualifications.qualifications_cli",
    "Paediatric First Aid":             "first_aid.first_aid_cli",
    "Invoices & Fees":                  "invoices.invoices_cli",
    "Funded Hours Claims":              "funding_claims.funding_claims_cli",
    "Payments":                         "payments.payments_cli",
    "Tax-Free Childcare / Vouchers":    "childcare_vouchers.childcare_vouchers_cli",
    "Sibling Discounts":                "discounts.discounts_cli",
    "Occupancy & Income":               "occupancy.occupancy_cli",
    "Parent Contacts":                  "parent_contacts.parent_contacts_cli",
    "Emergency Contacts":               "emergency_contacts.emergency_contacts_cli",
    "Permissions & Consents":           "consents.consents_cli",
    "Parent Messaging":                 "messaging.messaging_cli",
    "Daily Updates":                    "daily_updates.daily_updates_cli",
    "Newsletters":                      "newsletters.newsletters_cli",
    "Parent Meetings":                  "parent_meetings.parent_meetings_cli",
    "Safeguarding / Child Protection":  "safeguarding.safeguarding_cli",
    "Designated Safeguarding Lead":     "dsl.dsl_cli",
    "Welfare Requirements":             "welfare.welfare_cli",
    "SEND & Additional Needs":          "send.send_cli",
    "EHC Plans":                        "ehc_plans.ehc_plans_cli",
    "Looked-After Children":            "looked_after.looked_after_cli",
    "Risk Assessments":                 "risk_assessments.risk_assessments_cli",
    "Prevent Duty":                     "prevent_duty.prevent_duty_cli",
    "Concerns & Referrals":             "concerns.concerns_cli",
    "Wellbeing":                        "wellbeing.wellbeing_cli",
    "EYFS Profile":                     "eyfs_profile.eyfs_profile_cli",
    "Development Tracking (Prime & Specific Areas)": "development_tracking.development_tracking_cli",
    "Observations":                     "observations.observations_cli",
    "Learning Journeys":                "learning_journeys.learning_journeys_cli",
    "Next Steps Planning":              "next_steps.next_steps_cli",
    "2-Year-Old Progress Check":        "progress_check_2yr.progress_check_2yr_cli",
    "Characteristics of Effective Learning": "effective_learning.effective_learning_cli",
    "Activity & Curriculum Planning":   "curriculum_planning.curriculum_planning_cli",
    "Cohort Tracking":                  "cohort_tracking.cohort_tracking_cli",
    "Photos & Evidence":                "evidence.evidence_cli",
    # Daily Care & Routines
    "Daily Register":                   "daily_register.daily_register_cli",
    "Sign In / Sign Out":               "sign_in_out.sign_in_out_cli",
    "Collections & Late Pickup":        "collections.collections_cli",
    "Daily Diary":                      "daily_diary.daily_diary_cli",
    "Sleep Log":                        "sleep_log.sleep_log_cli",
    "Nappy / Toileting Log":            "toileting_log.toileting_log_cli",
    "Meals & Menus":                    "meals.meals_cli",
    "Bottle Feeds":                     "bottle_feeds.bottle_feeds_cli",
    "Allergies & Dietary Requirements": "allergies.allergies_cli",
    "Accident & Incident Log":          "accident_log.accident_log_cli",
    "Existing Injuries Log":            "existing_injuries.existing_injuries_cli",
    "Medication Log":                   "medication_log.medication_log_cli",
}


def _dispatch_local_cli(label: str) -> bool:
    """Run a local domain module's CLI for ``label``; return True if handled."""
    module_path = _LOCAL_CLI.get(label)
    if module_path is None:
        return False
    import importlib
    mod = importlib.import_module(
        f"education_system.systems.nursery.domain.{module_path}")
    logger.debug("Nursery CLI dispatch (local): %s -> %s", label, module_path)
    return bool(mod.dispatch(label))


# Nursery menu label -> dotted module path for the "System" category features
# (account/auth/settings/about). The four shared ones live under
# ``modules.shared.cli``; MFA and User Management are domain modules. Each
# exposes ``dispatch(label, auth=...)`` and is imported lazily.
_SYSTEM_CLI: dict[str, str] = {
    # Email / Messaging lives here (not in _LOCAL_CLI) because it needs the
    # signed-in ``auth`` to drive its Cross-System Email option.
    "Email / Messaging":          "domain.email_centre.email_centre_cli",
    "Change Password":            "shared.cli.change_password_cli",
    "Multi-Factor Authentication": "domain.mfa.mfa_cli",
    "User Accounts":              "shared.cli.user_accounts_cli",
    "User Management":            "domain.user_management.user_management_cli",
    "Settings":                   "shared.cli.settings_cli",
    "About":                      "shared.cli.about_cli",
}


def _dispatch_system_cli(label: str, auth=None) -> bool:
    """Run a System-category CLI for ``label``; return True if handled."""
    module_path = _SYSTEM_CLI.get(label)
    if module_path is None:
        return False
    import importlib
    mod = importlib.import_module(
        f"education_system.systems.nursery.__init__.{module_path}")
    logger.debug("Nursery CLI dispatch (system): %s -> %s", label, module_path)
    return bool(mod.dispatch(label, auth=auth))


# Nursery menu label -> (module dotted path, run-callable name) for the
# cross-cutting modules ported from the Primary School System. Imported lazily
# so a single broken module can't stop the launcher from starting.
_PORTED_CLI: dict[str, tuple[str, str]] = {
    "Policies & Procedures":     ("policies.policies_cli", "run"),
    "GDPR":                      ("gdpr.gdpr_cli", "run"),
    "Recruitment":               ("recruitment.recruitment_cli", "run"),
    "Complaints":                ("complaints.complaints_cli", "run"),
    "Feedback & Surveys":        ("feedback.feedback_cli", "run"),
    "Expense Claims":            ("expense_claims.expense_claims_cli", "run"),
    "Audit Reports":             ("audit_reports.audit_reports_cli", "run"),
    "Staff Absence":             ("staff_absence.staff_absence_cli", "run"),
    "Staff Directory":           ("staff.staff_cli", "run"),
    "Visitors":                  ("visitors.visitors_cli", "run"),
    "DBS Checks":                ("dbs_checks.dbs_checks_cli", "run"),
    "Supervisions & Appraisals": ("appraisals.appraisals_cli", "run"),
    # Compliance & Reports
    "Ofsted Readiness":          ("ofsted.ofsted_cli", "run"),
    "EYFS Compliance":           ("eyfs_compliance.eyfs_compliance_cli", "run"),
    "Attendance Report":         ("attendance_report.attendance_report_cli", "run"),
    "Occupancy Report":          ("occupancy_report.occupancy_report_cli", "run"),
    "Funding Report":            ("funding_report.funding_report_cli", "run"),
    "Accident / Incident Report": (
        "accident_report.accident_report_cli", "run"),
    "Data Export":               ("data_export.data_export_cli", "run"),
}


def _dispatch_ported_cli(label: str) -> bool:
    """Run a ported module's CLI for ``label``; return True if handled."""
    entry = _PORTED_CLI.get(label)
    if entry is None:
        return False
    module_path, func_name = entry
    import importlib
    mod = importlib.import_module(
        f"education_system.systems.nursery.domain.{module_path}")
    logger.debug("Nursery CLI dispatch (ported): %s -> %s", label, module_path)
    getattr(mod, func_name)()
    return True


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

    user = auth.current_user or {}
    show_system_switch = is_superadmin(user)
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {user.get('username', '?')}")
        for i, (cat, _items) in enumerate(NAV_CATEGORIES, 1):
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(NAV_CATEGORIES)):
            print("Invalid selection.")
            continue
        cat, items = NAV_CATEGORIES[int(choice) - 1]
        _submenu(cat, items, auth=auth)


def run_authenticated(auth) -> int:
    _main_menu(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("nursery CLI invoked without a shared_auth session")
        raise RuntimeError(
            "nursery_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Nursery CLI starting for user=%s role=%s",
                cu.get("username"), role)
    from education_system.systems.nursery.infrastructure.database import init_db
    init_db()
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Nursery)")
    raise SystemExit(2)
