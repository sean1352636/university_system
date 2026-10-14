"""Canonical command-line entry point for University Finance.

The launcher previously entered the GUI/reporting compatibility menu, which
hid most of the command-line finance features behind an "enhanced console"
choice.  Keep the finance areas together here and import each implementation
lazily so a missing optional dependency cannot make the whole CLI disappear.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _core_finance(auth: Any) -> None:
    from education_system.systems.university.domains.finance.domain.core.finance_context import (
        set_auth,
    )
    from education_system.systems.university.domains.finance.domain.core.menu import (
        display_enhanced_finance_menu,
    )

    set_auth(auth)
    display_enhanced_finance_menu()


def _ledger(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.ledger import (
        run_ledger_menu,
    )

    run_ledger_menu(auth)


def _bank_reconciliation(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.bank_rec import (
        run_bank_rec_menu,
    )

    run_bank_rec_menu(auth)


def _statements(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.statements import (
        run_statements_menu,
    )

    run_statements_menu(auth)


def _budgets(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.budget.budget_cli import (
        display_budget_tracker_menu,
        set_auth,
    )

    set_auth(auth)
    display_budget_tracker_menu()


def _bursaries(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.bursary.bursary_cli import (
        display_bursary_menu,
        set_auth,
    )

    set_auth(auth)
    display_bursary_menu()


def _scholarships(_auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.scholarship_finder import (
        ScholarshipFinderCLI,
    )

    ScholarshipFinderCLI().run()


def _blockchain_credentials(auth: Any) -> None:
    from education_system.systems.university.domains.finance.interfaces.cli.blockchain import (
        display_blockchain_credentials_menu,
    )

    display_blockchain_credentials_menu(auth)


FINANCE_AREAS: tuple[tuple[str, str, Callable[[Any], None]], ...] = (
    ("1", "Core Finance Operations (29 options)", _core_finance),
    ("2", "General Ledger", _ledger),
    ("3", "Bank Reconciliation", _bank_reconciliation),
    ("4", "Student Statements", _statements),
    ("5", "Budget Management", _budgets),
    ("6", "Bursary Management", _bursaries),
    ("7", "Scholarship Finder", _scholarships),
    ("8", "Blockchain Credentials", _blockchain_credentials),
)


def display_finance_menu(auth: Any) -> None:
    """Display every command-line Finance area from one discoverable menu."""
    actions = {key: action for key, _label, action in FINANCE_AREAS}

    while True:
        print("\n" + "=" * 60)
        print("UNIVERSITY FINANCE")
        print("=" * 60)
        for key, label, _action in FINANCE_AREAS:
            print(f"{key}. {label}")
        print("0. Return to Main Menu")

        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return

        action = actions.get(choice)
        if action is None:
            print("Invalid choice.")
            continue

        try:
            action(auth)
        except KeyboardInterrupt:
            print("\nFinance action cancelled.")
        except Exception as exc:
            # One optional finance area must not eject the user from the
            # Finance hub or hide the other working areas.
            print(f"\nUnable to open this finance area: {exc}")


__all__ = ["FINANCE_AREAS", "display_finance_menu"]
