"""
Student Budget Tracker Module

Personal finance management system with expense tracking, meal plan monitoring,
textbook cost comparison, and savings goals.
"""

from education_system.university_system.modules.domain.budget.services.budget_service import (
    BudgetManager,
    ExpenseManager,
    IncomeManager,
    MealPlanManager,
    TextbookComparisonManager,
    SavingsGoalManager
)

# Import CLI interface
from education_system.university_system.modules.domain.budget.cli.budget_cli import (
    BudgetTrackerCLI,
    display_budget_tracker_menu
)

__all__ = [
    # Service layer
    'BudgetManager',
    'ExpenseManager',
    'IncomeManager',
    'MealPlanManager',
    'TextbookComparisonManager',
    'SavingsGoalManager',
    # CLI interface
    'BudgetTrackerCLI',
    'display_budget_tracker_menu'
]
