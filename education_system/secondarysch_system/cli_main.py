"""CLI main menu for the Secondary School System.

Mirrors the categorized structure of `gui_main.py`.
"""

from __future__ import annotations

from education_system.secondarysch_system import SYSTEM_NAME

CATEGORIES: list[tuple[str, list[str]]] = [
    ("Pupil Management", [
        "Pupil Directory", "Add Pupil", "Search Pupils",
        "Pupil Profile", "Admissions", "Year Group Management",
    ]),
    ("Academic Management", [
        "Subjects", "Classes / Sets", "Timetable",
        "KS3 Curriculum", "KS4 / GCSE Options", "Homework",
        "Cover & Substitution",
    ]),
    ("Attendance & Registers", [
        "Daily Register", "Lesson Attendance", "Lateness Log",
        "Absence Reasons", "Attendance Report",
    ]),
    ("Assessment & GCSEs", [
        "Gradebook", "Assessment Cycles", "Predicted Grades",
        "Mock Exams", "GCSE Entries", "Results & Certificates",
    ]),
    ("Pastoral & Behaviour", [
        "Tutor / Form Groups", "Behaviour Points", "Detentions",
        "Exclusions", "Rewards & Merits", "House System",
    ]),
    ("Safeguarding & Welfare", [
        "Safeguarding Log", "CPOMS-style Incidents", "Looked-After Children",
        "Pupil Premium", "Free School Meals", "Medical & First Aid",
    ]),
    ("SEND & Inclusion", [
        "SEND Register", "EHCPs", "Provision Map",
        "Intervention Tracking", "EAL Support",
    ]),
    ("Staff & Communication", [
        "Staff Directory", "Cover Allocations", "Parent Contacts",
        "Parents' Evenings", "Letters & Bulletins", "Email / Messaging",
    ]),
    ("Finance & Trips", [
        "Trips & Visits", "Trip Payments", "Dinner Money", "Uniform & Shop",
    ]),
    ("Reports & Analytics", [
        "Attendance Report", "Behaviour Report", "Progress Tracking",
        "Census / DfE Returns", "Custom Export",
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
            _switch.request_switch("school", "gui")
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
    """Launch the CLI for an already-authenticated session."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        raise RuntimeError(
            "secondarysch_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Secondary School)")
    raise SystemExit(2)
