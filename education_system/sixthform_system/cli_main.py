"""CLI main menu for the Sixth Form System.

Mirrors the categorized structure of `gui_main.py`: a top-level list of
categories; selecting a category opens a sub-menu of feature actions.
Stubs print a placeholder; real domain wiring goes in later.
"""

from __future__ import annotations

from education_system.sixthform_system import SYSTEM_NAME

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


def _submenu(category: str, items: list[str]) -> None:
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
        print(f"\n[stub] {label} — not yet implemented.")
        _prompt("Press Enter to continue...")


def _main_menu(auth) -> None:
    from education_system import switch as _switch
    user = auth.current_user or {}
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {user.get('username', '?')}")
        for i, (cat, _items) in enumerate(CATEGORIES, 1):
            print(f"  {i:2d}) {cat}")
        print("   G) Switch to GUI")
        print("   L) Logout (return to login)")
        choice = _prompt("Select: ").lower()
        if choice == "g":
            _switch.request_switch("college", "gui")
            return
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
        _submenu(cat, items)


def run_authenticated(auth) -> int:
    """Entry point when the caller has already logged in (e.g. GUI → CLI switch)."""
    try:
        _main_menu(auth)
    finally:
        try:
            auth.logout()
        except Exception:
            pass
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the CLI for an already-authenticated session.

    Called by `run.py` after the universal login succeeds. No per-system
    login is shown — `shared_auth.current_user` must already be set.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        raise RuntimeError(
            "sixthform_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Sixth Form)")
    raise SystemExit(2)
