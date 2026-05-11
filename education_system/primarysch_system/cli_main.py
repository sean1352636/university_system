"""CLI main menu for the Primary School System.

Mirrors the categorized structure of `gui_main.py`.
"""

from __future__ import annotations

from education_system.primarysch_system import SYSTEM_NAME

CATEGORIES: list[tuple[str, list[str]]] = [
    ("Pupil Management", [
        "Pupil Directory", "Add Pupil", "Search Pupils",
        "Pupil Profile", "Admissions", "Year Group Management",
    ]),
    ("EYFS & Early Years", [
        "Nursery Register", "Reception Class", "Learning Journeys",
        "Observations", "EYFS Profile", "Tapestry-style Posts",
    ]),
    ("Curriculum & Lessons", [
        "Class Lists", "Subjects", "Phonics", "Reading Levels",
        "Timetable", "Lesson Planning", "Homework", "Cover & Supply",
    ]),
    ("Attendance & Registers", [
        "Morning Register", "Afternoon Register", "Lateness Log",
        "Absence Reasons", "Attendance Report",
    ]),
    ("Assessment & SATs", [
        "Phonics Screening", "KS1 Assessments", "KS2 SATs",
        "Multiplication Check (Y4)", "Progress Tracker",
        "Reports to Parents",
    ]),
    ("Behaviour & Rewards", [
        "Behaviour Log", "Reward Charts", "House Points",
        "Star of the Week", "Playtime Incidents",
    ]),
    ("Safeguarding & Welfare", [
        "Safeguarding Log", "Concerns & Incidents", "Looked-After Children",
        "Pupil Premium", "Free School Meals", "Medical & First Aid",
        "Allergies & Care Plans",
    ]),
    ("SEND & Inclusion", [
        "SEND Register", "EHCPs", "Provision Map",
        "Interventions", "EAL Support",
    ]),
    ("Parents & Communication", [
        "Parent Contacts", "Parents' Evenings", "Newsletters",
        "Letters Home", "Messaging", "Permission Slips",
    ]),
    ("Staff", [
        "Staff Directory", "Teaching Assistants",
        "Cover Allocations", "PPA Cover",
    ]),
    ("Clubs, Trips & Dinners", [
        "After-School Clubs", "Breakfast Club", "School Trips",
        "Trip Payments", "Dinner Money", "Dinner Choices", "Uniform",
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
            _switch.request_switch("primary", "gui")
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
    """Entry point when the caller has already logged in (e.g. GUI → CLI switch).

    The shared session is owned by the unified launcher — we never log it
    out unconditionally here. The explicit "Logout" menu item handles that;
    the "Switch to GUI" menu item leaves the session intact so dispatch
    can hand it straight to the GUI.
    """
    _main_menu(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the CLI for an already-authenticated session."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        raise RuntimeError(
            "primarysch_system CLI must be launched via run.py — "
            "no standalone login is available."
        )
    return run_authenticated(shared_auth)


if __name__ == "__main__":
    print("Launch via: python run.py --cli  (then choose Primary School)")
    raise SystemExit(2)
