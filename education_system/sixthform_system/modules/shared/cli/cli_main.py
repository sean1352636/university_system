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
        "Student Profile", "Enrolment",
    ]),
    ("Academic Management", [
        "Courses", "Subjects & A-Levels", "Class Groups",
        "Timetable", "Attendance", "Homework & Coursework",
    ]),
    ("Assessment & Grades", [
        "Gradebook", "Predicted Grades", "Mock Exams",
        "Exam Entries", "Results Day",
    ]),
    ("UCAS & Careers", [
        "UCAS Applications", "Personal Statements", "References",
        "University Offers", "Apprenticeships", "Careers Guidance",
    ]),
    ("Pastoral & Wellbeing", [
        "Tutor Groups", "Behaviour Log", "Safeguarding",
        "Wellbeing", "Attendance Concerns",
    ]),
    ("Staff & Communication", [
        "Staff Directory", "Parent Contacts", "Parents' Evenings",
        "Notices & Bulletins", "Email / Messaging",
    ]),
    ("Finance & Bursaries", [
        "Fees", "Bursary Applications", "Trips & Payments", "Receipts",
    ]),
    ("Reports & Analytics", [
        "Attendance Report", "Grades Report",
        "Progress Tracking", "Custom Export",
    ]),
    ("System", [
        "Change Password", "User Accounts", "Settings", "About",
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
            print(f"  {i}) {label}")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("Invalid selection.")
            continue
        label = items[int(choice) - 1]
        logger.debug("Sixth-form CLI dispatch: %s / %s", category, label)
        from education_system.sixthform_system.modules.domain.students import student_cli
        from education_system.sixthform_system.modules.domain.enrolments import enrolment_cli
        from education_system.sixthform_system.modules.domain.courses import course_cli
        from education_system.sixthform_system.modules.domain.subjects import subject_cli
        from education_system.sixthform_system.modules.domain.class_groups import class_group_cli
        from education_system.sixthform_system.modules.domain.timetable import timetable_cli
        from education_system.sixthform_system.modules.domain.attendance import attendance_cli
        from education_system.sixthform_system.modules.domain.homework import homework_cli
        from education_system.sixthform_system.modules.domain.gradebook import gradebook_cli
        from education_system.sixthform_system.modules.domain.predicted_grades import predicted_grades_cli
        from education_system.sixthform_system.modules.domain.mock_exams import mock_exam_cli
        from education_system.sixthform_system.modules.domain.exam_entries import exam_entry_cli
        from education_system.sixthform_system.modules.domain.exam_results import exam_result_cli
        from education_system.sixthform_system.modules.domain.ucas import ucas_cli
        from education_system.sixthform_system.modules.domain.personal_statements import personal_statement_cli
        from education_system.sixthform_system.modules.domain.references import reference_cli
        from education_system.sixthform_system.modules.domain.offers import offer_cli
        from education_system.sixthform_system.modules.domain.apprenticeships import apprenticeship_cli
        from education_system.sixthform_system.modules.domain.careers import careers_cli
        from education_system.sixthform_system.modules.domain.tutor_groups import tutor_group_cli
        from education_system.sixthform_system.modules.domain.behaviour import behaviour_cli
        from education_system.sixthform_system.modules.domain.safeguarding import safeguarding_cli
        from education_system.sixthform_system.modules.domain.wellbeing import wellbeing_cli
        from education_system.sixthform_system.modules.domain.attendance_concerns import attendance_concerns_cli
        from education_system.sixthform_system.modules.domain.staff import staff_cli
        from education_system.sixthform_system.modules.domain.parent_contacts import parent_contacts_cli
        from education_system.sixthform_system.modules.domain.parents_evenings import parents_evenings_cli
        from education_system.sixthform_system.modules.domain.notices import notices_cli
        from education_system.sixthform_system.modules.domain.messages import messages_cli
        from education_system.sixthform_system.modules.domain.fees import fees_cli
        from education_system.sixthform_system.modules.domain.bursaries import bursaries_cli
        from education_system.sixthform_system.modules.domain.trips import trips_cli
        from education_system.sixthform_system.modules.domain.receipts import receipts_cli
        from education_system.sixthform_system.modules.domain.attendance_report import attendance_report_cli
        from education_system.sixthform_system.modules.domain.grades_report import grades_report_cli
        from education_system.sixthform_system.modules.domain.progress import progress_cli
        from education_system.sixthform_system.modules.domain.custom_export import custom_export_cli
        from education_system.sixthform_system.modules.shared.cli import change_password_cli, user_accounts_cli, settings_cli, about_cli
        if change_password_cli.dispatch(label, auth=auth):
            continue
        if user_accounts_cli.dispatch(label, auth=auth):
            continue
        if settings_cli.dispatch(label, auth=auth):
            continue
        if about_cli.dispatch(label, auth=auth):
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
                or attendance_concerns_cli.dispatch(label)
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
                or custom_export_cli.dispatch(label)):
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
        choice = _prompt("Select: ").lower()
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
