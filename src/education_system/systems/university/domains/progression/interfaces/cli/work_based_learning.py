"""Work-Based Learning — one CLI over apprenticeships and industry placements.

These were two adjacent menus doing overlapping jobs: both tracked a
work-based route, both carried their own student CRUD, and both ended in
"Submit as APL evidence". Splitting them by qualification type made the
learner's route the *first* thing you had to know, when in practice you
arrive wanting employers, hours, or an application.

They are merged at the **menu** layer only. The two services keep their own
data and their own rules, because they are genuinely different things:

* **Apprenticeships** — employer-sponsored programmes owned by the
  apprenticeships system, read here through a read-only gateway. This side
  shows what is on offer and routes applications.
* **Industry placements** — the T-Level style hours requirement
  (``REQUIRED_HOURS``), owned by the university and logged here.

Merging their *data* would be wrong; merging their front door is what the
person using it actually wanted.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _pause() -> None:
    input("\nPress Enter to continue...")


def _apprenticeship_bits():
    from education_system.systems.university.domains.progression.interfaces.cli.apprenticeships import (  # noqa: E501
        apprenticeships_cli as mod,
    )
    return mod


def _placement_bits():
    from education_system.systems.university.domains.progression.interfaces.cli.placements import (  # noqa: E501
        placements_cli as mod,
    )
    return mod


def _submit_apl_evidence(appr_svc, placement_db) -> None:
    """One APL route, asking which experience is being claimed.

    Both halves fed the same APL/RPL claim through different functions, so
    the split was invisible to the user but duplicated in the menus.
    """
    print("\nWhich experience is being submitted as APL evidence?")
    print("  [1] Apprenticeship experience")
    print("  [2] Industry placement hours")
    choice = input("Choice (blank to cancel): ").strip()

    if choice == "1":
        _apprenticeship_bits()._submit_student_apl(appr_svc)
    elif choice == "2":
        _placement_bits()._submit_apl(placement_db)
    elif choice:
        print("Invalid choice.")


def run_work_based_learning_menu(auth) -> None:
    """Run the combined Work-Based Learning CLI loop."""
    appr_mod = _apprenticeship_bits()
    plac_mod = _placement_bits()

    from education_system.systems.university.domains.progression.domain.apprenticeships.apprenticeship_service import (  # noqa: E501
        ApprenticeshipService,
    )
    from education_system.systems.university.domains.progression.domain.placements.placement_service import (  # noqa: E501
        REQUIRED_HOURS,
        Database,
    )

    appr_svc = placement_db = None
    try:
        appr_svc = ApprenticeshipService()
    except Exception as e:
        print(f"⚠ Apprenticeship data unavailable: {e}")
    try:
        placement_db = Database()
    except Exception as e:
        print(f"⚠ Placement data unavailable: {e}")

    if appr_svc is None and placement_db is None:
        print("❌ Neither apprenticeships nor placements could be opened.")
        return

    try:
        while True:
            print("\n" + "=" * 58)
            print("    WORK-BASED LEARNING")
            print("=" * 58)
            print("  APPRENTICESHIPS")
            print("   1. Employers")
            print("   2. Apprenticeship programmes")
            print("   3. Applications")
            print(f"\n  INDUSTRY PLACEMENTS  (requirement: {REQUIRED_HOURS} hours)")
            print("   4. Placement hours")
            print("   5. Export placement summary")
            print("\n  SHARED")
            print("   6. Submit experience as APL evidence")
            print("\n   0. Return to Main Menu")
            print("=" * 58)

            try:
                choice = input("\nEnter your choice: ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            try:
                if choice in ("1", "2", "3") and appr_svc is None:
                    print("❌ Apprenticeship data is unavailable.")
                elif choice in ("4", "5") and placement_db is None:
                    print("❌ Placement data is unavailable.")
                elif choice == "1":
                    appr_mod._employers_menu(appr_svc, auth)
                elif choice == "2":
                    appr_mod._apprenticeships_menu(appr_svc, auth)
                elif choice == "3":
                    appr_mod._applications_menu(appr_svc, auth)
                elif choice == "4":
                    plac_mod._hours_menu(placement_db, auth)
                elif choice == "5":
                    plac_mod._export_summary(placement_db)
                    _pause()
                elif choice == "6":
                    _submit_apl_evidence(appr_svc, placement_db)
                    _pause()
                elif choice == "0":
                    print("Returning to main menu...")
                    return
                else:
                    print("❌ Invalid choice.")
            except KeyboardInterrupt:
                print("\nCancelled.")
            except Exception as e:  # keep the menu resilient
                logger.warning("work-based learning menu error", exc_info=True)
                print(f"❌ Error: {e}")
    finally:
        for closeable in (appr_svc, placement_db):
            try:
                if closeable is not None:
                    closeable.close()
            except Exception:
                logger.debug("close failed", exc_info=True)
