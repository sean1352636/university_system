"""Budget manager utility methods"""
from education_system.systems.university.shell.gui import report_view as _rv

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class BudgetUtilsMixin:
    """Utility methods for budget manager"""

    def show_text_window(self, title, content):
        """Show content in a separate text window"""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("800x600")
        window.transient(self.root)

        text_widget = _rv.TextReportView(window, font=('Courier', 10))
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        text_widget.insert('1.0', content)

        ttk.Button(window, text=_t('gui.finance.finance.budget_manager.utils.buttons.close', default="Close"), command=window.destroy).pack(pady=10)

    def gui_manage_budgets(self):
        """Switch to budget tab"""
        self.show_tab('budget')

    def refresh_all_budget_data(self):
        """Refresh all budget-related data"""
        self.refresh_dashboard()
        self.refresh_my_budgets()
        self.refresh_savings_goals()
        self.load_meal_plan_status()
        self.load_my_textbooks()
        self.refresh_budget()  # Institutional budgets
