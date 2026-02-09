"""
Budget Tracker CLI Package

Exports the CLI interface for the budget tracker module.
"""

from university_system.modules.domain.budget.cli.budget_cli import (
    BudgetTrackerCLI,
    display_budget_tracker_menu,
    run
)

__all__ = [
    'BudgetTrackerCLI',
    'display_budget_tracker_menu',
    'run'
]
