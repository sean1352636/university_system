"""Budget reports and analytics"""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta

from .constants import (
    budget_vs_actual_analysis,
    variance_analysis_report,
    budget_performance_trends,
    category_performance_report,
)


class BudgetReportsMixin:
    """Budget reports and analytics methods"""

    def create_budget_reports_tab(self, notebook):
        """Create budget reports and analytics tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Reports")

        # Report selection
        select_frame = ttk.LabelFrame(tab, text="Select Report", padding="10")
        select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(select_frame, text="Financial Summary", command=self.show_financial_summary,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Budget vs Actual", command=self.show_budget_performance,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Spending by Category", command=self.show_spending_analysis,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Spending Trends", command=self.show_spending_trends,
                  width=22).pack(side=tk.LEFT, padx=5)

        # Report display
        report_frame = ttk.LabelFrame(tab, text="Report Output", padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True)

        self.budget_report_text = ScrolledText(report_frame, wrap=tk.WORD,
                                              width=100, height=25, font=('Courier', 10))
        self.budget_report_text.pack(fill=tk.BOTH, expand=True)

    def gui_budget_vs_actual_analysis(self):
        """GUI wrapper for budget_vs_actual_analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_vs_actual_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Budget vs actual analysis generated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate budget vs actual analysis: {e}")

    def gui_variance_analysis_report(self):
        """GUI wrapper for variance_analysis_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            variance_analysis_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Variance analysis report generated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate variance analysis report: {e}")

    def gui_budget_performance_trends(self):
        """GUI wrapper for budget_performance_trends"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_performance_trends()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Budget performance trends report generated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate budget performance trends: {e}")

    def gui_category_performance_report(self):
        """GUI wrapper for category_performance_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            category_performance_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Category performance report generated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate category performance report: {e}")

    def gui_apply_credit_to_fees(self):
        """Wrapper to call transaction manager's apply credit function"""
        if hasattr(self.gui, 'transactions'):
            self.gui.transactions.gui_apply_credit_to_fees()
        else:
            messagebox.showwarning("Not Available", "Transaction manager not initialized")

    def show_financial_summary(self):
        """Show financial summary report"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.budget.services.budget_service import (
                BudgetManager, ExpenseManager, IncomeManager
            )

            output = f"""
{'='*70}
PERSONAL FINANCIAL SUMMARY
{'='*70}

Student: {student_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            self.budget_report_text.insert(tk.END, output)

            # Get active budgets
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                output = "\nACTIVE BUDGETS:\n"
                for budget in budgets:
                    summary = BudgetManager.get_budget_summary(budget['budget_id'])
                    output += f"""
  {summary['budget_name']}
    Total:      \u00a3{summary['total_budget']:.2f}
    Spent:      \u00a3{summary['spent_amount']:.2f}
    Remaining:  \u00a3{summary['remaining_budget']:.2f}
"""
                self.budget_report_text.insert(tk.END, output)

            # This month stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            expenses = ExpenseManager.get_student_expenses(student_id, start_date=month_start)
            income = IncomeManager.get_student_income(student_id, start_date=month_start)

            total_expenses = sum(e['amount'] for e in expenses)
            total_income = sum(i['amount'] for i in income)

            output = f"""
THIS MONTH ({month_start} to now):
  Total Income:    \u00a3{total_income:.2f}
  Total Expenses:  \u00a3{total_expenses:.2f}
  Net Balance:     \u00a3{total_income - total_expenses:.2f}
"""
            self.budget_report_text.insert(tk.END, output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_spending_analysis(self):
        """Show spending by category breakdown"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.budget.services.budget_service import ExpenseManager

            # Get last 30 days
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')

            breakdown = ExpenseManager.get_spending_by_category(student_id, start_date, end_date)

            total = sum(cat['total_amount'] for cat in breakdown)
            output = f"""
{'='*70}
SPENDING BY CATEGORY
{'='*70}
Period: {start_date} to {end_date}
Total Spending: \u00a3{total:.2f}
{'='*70}

"""
            self.budget_report_text.insert(tk.END, output)

            for cat in breakdown:
                pct = (cat['total_amount'] / total * 100) if total > 0 else 0
                cat_output = f"""
{cat['category_name']} ({cat['category_type'] or 'N/A'})
  Total: \u00a3{cat['total_amount']:.2f} ({pct:.1f}%)
  Transactions: {cat['transaction_count']}
  Average: \u00a3{cat['average_amount']:.2f}
  Range: \u00a3{cat['min_amount']:.2f} - \u00a3{cat['max_amount']:.2f}

"""
                self.budget_report_text.insert(tk.END, cat_output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_budget_performance(self):
        """Show budget vs actual performance report"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.budget.services.budget_service import BudgetManager

            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                self.budget_report_text.insert(tk.END, "No active budgets found.")
                return

            budget_id = budgets[0]['budget_id']
            summary = BudgetManager.get_budget_summary(budget_id)

            output = f"""
{'='*70}
BUDGET VS ACTUAL ANALYSIS
{'='*70}

Budget: {summary['budget_name']}
Type: {summary['budget_type'].capitalize()}
Period: {summary['start_date']} to {summary['end_date']}

Overall Performance:
  Budgeted: \u00a3{summary['total_budget']:.2f}
  Spent: \u00a3{summary['spent_amount']:.2f}
  Variance: \u00a3{summary['remaining_budget']:.2f}
  Utilization: {summary['budget_utilization_pct']:.1f}%

Time Progress: {summary['days_progress_pct']:.1f}%
Spending Progress: {summary['budget_utilization_pct']:.1f}%

"""
            self.budget_report_text.insert(tk.END, output)

            if summary['budget_utilization_pct'] > summary['days_progress_pct'] + 10:
                self.budget_report_text.insert(tk.END, "\u26a0 WARNING: Spending ahead of schedule!\n\n")
            elif summary['budget_utilization_pct'] < summary['days_progress_pct'] - 10:
                self.budget_report_text.insert(tk.END, "\u2713 Good: Spending below pace\n\n")
            else:
                self.budget_report_text.insert(tk.END, "\u2713 On track\n\n")

            if summary.get('categories'):
                self.budget_report_text.insert(tk.END, f"{'='*70}\nCATEGORY BREAKDOWN\n{'='*70}\n\n")
                for cat in summary['categories']:
                    spent_pct = (cat['spent_amount'] / cat['allocated_amount'] * 100) if cat['allocated_amount'] > 0 else 0
                    variance = cat['allocated_amount'] - cat['spent_amount']
                    status = "OK" if spent_pct <= 100 else "OVER"

                    cat_output = f"""{cat['category_name']} [{status}]
  Budgeted: \u00a3{cat['allocated_amount']:.2f}
  Spent: \u00a3{cat['spent_amount']:.2f} ({spent_pct:.1f}%)
  Variance: \u00a3{variance:.2f}

"""
                    self.budget_report_text.insert(tk.END, cat_output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_spending_trends(self):
        """Show spending trends analysis"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.budget.services.budget_service import ExpenseManager

            trends = ExpenseManager.get_spending_trends(student_id, days=30)
            stats = trends['statistics']

            output = f"""
{'='*70}
SPENDING TRENDS (30 Days)
{'='*70}

Period: {trends['start_date']} to {trends['end_date']}

Overall Statistics:
  Total Spent: \u00a3{stats['total_spent']:.2f}
  Total Transactions: {stats['total_transactions']}
  Average Transaction: \u00a3{stats['average_transaction']:.2f}
  Average Daily Spending: \u00a3{stats['average_daily_spending']:.2f}
  Transaction Range: \u00a3{stats['min_transaction']:.2f} - \u00a3{stats['max_transaction']:.2f}

{'='*70}
DAILY SPENDING (Last 14 Days)
{'='*70}

"""
            self.budget_report_text.insert(tk.END, output)

            if trends['daily_spending']:
                for day in trends['daily_spending'][-14:]:
                    self.budget_report_text.insert(tk.END, f"{day['expense_date']}: \u00a3{day['daily_total']:.2f}\n")

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")
