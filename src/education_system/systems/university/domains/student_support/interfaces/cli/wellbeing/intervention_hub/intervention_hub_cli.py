"""Early Warning & Interventions — one CLI menu for the Early Warning
System, support cases and their outcomes.

Mirrors the Early Warning & Interventions window: the same three areas,
in the same order, behind one main-menu entry.
"""
from __future__ import annotations

from typing import Any

auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _early_warning() -> None:
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.intervention_hub.early_warning_cli import (
        display_early_warning_menu,
    )
    display_early_warning_menu(auth)


def _support_cases() -> None:
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.intervention_hub.support_cli import (
        display_intervention_support_menu,
    )
    display_intervention_support_menu(auth)


def _outcomes() -> None:
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.intervention_hub import outcomes_cli
    outcomes_cli.set_auth(auth)
    outcomes_cli.display_intervention_outcomes_menu()


def _student_overview() -> None:
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.intervention_hub.overview_cli import (
        display_student_overview_menu,
    )
    display_student_overview_menu(auth)


#: (menu label, handler) — same order as the window's tabs.
AREAS = (
    ("Early Warning System", _early_warning),
    ("Support Cases", _support_cases),
    ("Outcomes (scores, sessions, value-added)", _outcomes),
    ("Student Overview (one student across all three)", _student_overview),
)


def display_intervention_hub_menu(auth_object: Any = None) -> None:
    if auth_object is not None:
        set_auth(auth_object)
    while True:
        print("\nEarly Warning & Interventions")
        print("=" * 30)
        for number, (label, _) in enumerate(AREAS, start=1):
            print(f"{number}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(AREAS)):
            print("Invalid choice.")
            continue
        AREAS[int(choice) - 1][1]()
