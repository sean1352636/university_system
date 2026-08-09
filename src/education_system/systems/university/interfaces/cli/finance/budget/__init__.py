"""
Budget Tracker CLI Package

Exports the CLI interface for the budget tracker module.
"""

from education_system.systems.university.interfaces.cli.finance.budget.budget_cli import (
    BudgetTrackerCLI,
    display_budget_tracker_menu,
    run
)

__all__ = [
    'BudgetTrackerCLI',
    'display_budget_tracker_menu',
    'run'
]
