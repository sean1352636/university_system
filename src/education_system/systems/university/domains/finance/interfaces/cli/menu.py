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


def _lazy(module: str, func: str) -> Callable[[Any], None]:
    """Resolve ``func`` from ``module`` on first use so one broken area cannot
    take the whole finance menu down (same reason the areas above import
    inside their wrappers)."""
    def _run(auth: Any) -> None:
        import importlib

        getattr(importlib.import_module(module), func)(auth)

    _run.__name__ = func
    return _run


_CLI = "education_system.systems.university.domains.finance.interfaces.cli."

FINANCE_AREAS: tuple[tuple[str, str, Callable[[Any], None]], ...] = (
    ("1", "Core Finance Operations (29 options)", _core_finance),
    ("2", "General Ledger", _ledger),
    ("3", "Bank Reconciliation", _bank_reconciliation),
    ("4", "Student Statements", _statements),
    ("5", "Budget Management", _budgets),
    ("6", "Bursary Management", _bursaries),
    ("7", "Scholarship Finder", _scholarships),
    ("8", "Blockchain Credentials", _blockchain_credentials),
    # Parity with the Finance GUI (added 2026-10-14): every GUI section
    # below was previously GUI-only or far thinner on the command line.
    ("9", "Finance Operations (AP, purchasing, suppliers, cash, VAT, assets, approvals, fraud, close)",
     _lazy(_CLI + "operations", "run_operations_menu")),
    ("10", "Collections Management", _lazy(_CLI + "collections", "run_collections_menu")),
    ("11", "Payment Plans", _lazy(_CLI + "payment_plans", "run_payment_plans_menu")),
    ("12", "Late Fees", _lazy(_CLI + "late_fees", "run_late_fees_menu")),
    ("13", "Refunds", _lazy(_CLI + "refunds", "run_refunds_menu")),
    ("14", "Multi-Currency Rates", _lazy(_CLI + "currency", "run_currency_menu")),
    ("15", "Revenue Sources", _lazy(_CLI + "revenue", "run_revenue_menu")),
    ("16", "Forecasting & Analytics", _lazy(_CLI + "forecasting", "run_forecasting_menu")),
    ("17", "Finance Administration (admin)", _lazy(_CLI + "admin", "run_finance_admin_menu")),
    ("18", "Club Payments", _lazy(_CLI + "club_payments", "run_club_payments_menu")),
    ("19", "Library Finance", _lazy(_CLI + "library_finance", "run_library_finance_menu")),
    # Student-facing (any logged-in user, own account only).
    ("20", "Student Bank App", _lazy(_CLI + "bank_app", "run_bank_app_menu")),
    ("21", "My Finances", _lazy(_CLI + "my_finances", "run_my_finances_menu")),
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
