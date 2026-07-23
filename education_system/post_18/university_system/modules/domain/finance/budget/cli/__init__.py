"""
Budget Tracker CLI Package

Exports the CLI interface for the budget tracker module.
"""

from education_system.post_18.university_system.modules.domain.finance.budget.cli.budget_cli import (
    BudgetTrackerCLI,
    display_budget_tracker_menu,
    run
)

__all__ = [
    'BudgetTrackerCLI',
    'display_budget_tracker_menu',
    'run'
]
