"""Study Hub — one CLI menu for everything a student does to study.

Mirrors the Study Hub window: the same three areas, in the same order,
behind one main-menu entry. Each area is the original menu, unchanged.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["display_study_hub_menu"]


def _study_plan(auth):
    from education_system.systems.university.domains.student_life.interfaces.cli.ai_study.ai_study_cli import (
        display_ai_study_menu, set_auth,
    )
    set_auth(auth)
    display_ai_study_menu()


def _recommendations(auth):
    from education_system.systems.university.domains.student_life.interfaces.cli.study_hub.recommendations_cli import (
        display_study_recommendation_menu,
    )
    display_study_recommendation_menu(auth)


def _study_partners(auth):
    from education_system.systems.university.domains.student_life.interfaces.cli.study_hub.partners_cli import (
        StudyMatchingCLI,
    )
    StudyMatchingCLI(auth=auth).run()


#: (menu label, handler) — same order as the Study Hub window's tabs.
AREAS = (
    ("Study Plan (AI Study Companion)", _study_plan),
    ("Recommendations", _recommendations),
    ("Study Partners (groups, rooms, Q&A)", _study_partners),
)


def display_study_hub_menu(auth) -> None:
    """Show the Study Hub menu until the user goes back."""
    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("STUDY HUB".center(70))
        print("=" * 70)
        for number, (label, _) in enumerate(AREAS, start=1):
            print(f"  {number}. {label}")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(AREAS)):
            print("\nInvalid choice.")
            input("Press Enter to continue...")
            continue

        label, handler = AREAS[int(choice) - 1]
        try:
            handler(auth)
        except ImportError as exc:
            logger.exception("Study Hub area %r failed to import", label)
            print(f"\n❌ {label} is not available: {exc}")
            input("Press Enter to continue...")
