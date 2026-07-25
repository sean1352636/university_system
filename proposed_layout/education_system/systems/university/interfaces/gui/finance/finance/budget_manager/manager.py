"""Budget manager - main class composing all mixins"""

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.constants import logger
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.plans import BudgetPlansMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.categories import BudgetCategoriesMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.personal import PersonalBudgetMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.expenses_income import ExpensesIncomeMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.savings import SavingsGoalsMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.meal_plan import MealPlanMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.textbooks import TextbooksMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.reports import BudgetReportsMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.institutional import InstitutionalBudgetMixin
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.utils import BudgetUtilsMixin


class BudgetManager(
    BudgetPlansMixin,
    BudgetCategoriesMixin,
    PersonalBudgetMixin,
    ExpensesIncomeMixin,
    SavingsGoalsMixin,
    MealPlanMixin,
    TextbooksMixin,
    BudgetReportsMixin,
    InstitutionalBudgetMixin,
    BudgetUtilsMixin,
):
    """Budget planning and analysis"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        self.finance_system = vars(gui).get('finance_system')

    def create_budget_tab(self):
        """Create comprehensive budget management tab with Budget Tracker integration"""
        budget_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['budget'] = budget_frame

        # Initialize Budget Tracker database tables
        try:
            from education_system.systems.university.domain.finance.budget.services.budget_service import BudgetManager
            BudgetManager.create_tables()
        except Exception as e:
            logger.warning(f"Could not initialize budget tables: {e}")

        # Check user role to determine which view to show
        user_role = self.gui.get_user_role() if hasattr(self.gui, 'get_user_role') else None

        # Budget toolbar
        toolbar = tk.Frame(budget_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        # Common buttons for all users - Quick navigation
        tk.Button(toolbar, text="\U0001f4b0 My Expenses", command=self.open_expense_tracker,
                 bg=self.gui.layout.colors['info'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="\U0001f4b5 My Income", command=self.open_income_tracker,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="\U0001f3af Savings Goals", command=self.open_savings_goals,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="\U0001f37d\ufe0f Meal Plan", command=self.open_meal_plan,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="\U0001f4da Textbooks", command=self.open_textbooks,
                 bg=self.gui.layout.colors['primary'], fg='white').pack(side='left', padx=5)

        # Admin/Staff only buttons
        if user_role in ['admin', 'staff', 'instructor']:
            toolbar2 = tk.Frame(budget_frame, bg='white')
            toolbar2.pack(fill='x', padx=10, pady=5)

            tk.Button(toolbar2, text="\U0001f4ca New Budget Plan", command=self.create_budget_plan,
                     bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="\u270f\ufe0f Edit Budget", command=self.edit_budget_plan,
                     bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="\U0001f5d1\ufe0f Delete Budget", command=self.delete_budget_plan,
                     bg=self.gui.layout.colors['danger'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="\U0001f4c8 Budget Analysis", command=self.budget_analysis,
                     bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="\U0001f4c2 Manage Categories", command=self.gui_manage_budget_categories,
                     bg=self.gui.layout.colors['info'], fg='white').pack(side='left', padx=5)

        # Main content with notebook
        budget_notebook = ttk.Notebook(budget_frame)
        budget_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.budget_notebook = budget_notebook

        # Tab 1: Personal Budget Dashboard
        self.create_personal_budget_dashboard(budget_notebook)

        # Tab 2: My Budgets
        self.create_my_budgets_tab(budget_notebook)

        # Tab 3: Expenses & Income
        self.create_expenses_income_tab(budget_notebook)

        # Tab 4: Savings & Goals
        self.create_savings_goals_tab(budget_notebook)

        # Tab 5: Meal Plan Tracking
        self.create_meal_plan_tab(budget_notebook)

        # Tab 6: Textbooks
        self.create_textbooks_tab(budget_notebook)

        # Tab 7: Budget Reports (for all users)
        self.create_budget_reports_tab(budget_notebook)

        # Tab 8: Institutional Budgets (admin/staff only)
        if user_role in ['admin', 'staff', 'instructor']:
            self.create_institutional_budget_tab(budget_notebook)

        # Load initial data
        self.refresh_all_budget_data()
