"""Budget reports and analytics"""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta

from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.constants import (
    budget_vs_actual_analysis,
    variance_analysis_report,
    budget_performance_trends,
    category_performance_report,
    logger,
    get_connection,
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

        # Report display (kept for backward compat with toolbar wrappers)
        report_frame = ttk.LabelFrame(tab, text="Report Output", padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True)

        self.budget_report_text = ScrolledText(report_frame, wrap=tk.WORD,
                                              width=100, height=25, font=('Courier', 10))
        self.budget_report_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Helper: open report in a new window with Save / Email buttons
    # ------------------------------------------------------------------

    def _open_report_window(self, title, report_content):
        """Open a report in a new top-level window with Save and Email buttons."""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("800x600")
        window.minsize(600, 400)

        # Report text area
        text = ScrolledText(window, wrap=tk.WORD, font=('Courier', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        text.insert(tk.END, report_content)
        text.config(state=tk.DISABLED)

        # Button bar
        btn_frame = ttk.Frame(window)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Button(btn_frame, text="Save as TXT",
                  command=lambda: self._save_report_as_txt(title, report_content)
                  ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Email to Admin",
                  command=lambda: self._email_report_to_admin(title, report_content)
                  ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close",
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _save_report_as_txt(self, title, content):
        """Save report content to a .txt file."""
        default_name = title.replace(' ', '_').lower() + '.txt'
        file_path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=default_name,
            title="Save Report"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Saved", f"Report saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report: {e}")

    def _email_report_to_admin(self, subject, body):
        """Send the report to admin via the university email system."""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            # Look up admin email
            admin_email = None
            try:
                conn = get_connection()
                cursor = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' "
                    "AND email IS NOT NULL AND email != '' LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    admin_email = row['email'] if hasattr(row, 'keys') else row[0]
                conn.close()
            except Exception:
                pass

            if not admin_email:
                admin_email = 'admin@university.edu'

            # Get sender info
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            sender_name = 'Unknown'
            if current_user:
                first = current_user.get('first_name', '')
                last = current_user.get('last_name', '')
                sender_name = f"{first} {last}".strip() or current_user.get('username', 'Unknown')

            email_subject = f"Finance Report: {subject}"
            email_body = (
                f"Finance report generated by {sender_name}\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"{'='*70}\n\n"
                f"{body}"
            )

            result = send_email(admin_email, email_subject, email_body)
            if result is not False:
                messagebox.showinfo("Email Sent",
                    f"Report emailed to admin ({admin_email}).")
            else:
                messagebox.showwarning("Email",
                    "Email queued but delivery could not be confirmed.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}")

    # ------------------------------------------------------------------
    # Report generators
    # ------------------------------------------------------------------

    def show_financial_summary(self):
        """Show financial summary report in a new window"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import (
                BudgetManager, ExpenseManager, IncomeManager
            )

            output = (
                f"{'='*70}\n"
                f"PERSONAL FINANCIAL SUMMARY\n"
                f"{'='*70}\n\n"
                f"Student: {student_id}\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )

            # Get active budgets
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                output += "\nACTIVE BUDGETS:\n"
                for budget in budgets:
                    summary = BudgetManager.get_budget_summary(budget['budget_id'])
                    output += (
                        f"\n  {summary['budget_name']}\n"
                        f"    Total:      \u00a3{summary['total_budget']:.2f}\n"
                        f"    Spent:      \u00a3{summary['spent_amount']:.2f}\n"
                        f"    Remaining:  \u00a3{summary['remaining_budget']:.2f}\n"
                    )
            else:
                output += "\nNo active budgets found.\n"

            # This month stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            expenses = ExpenseManager.get_student_expenses(student_id, start_date=month_start)
            income = IncomeManager.get_student_income(student_id, start_date=month_start)

            total_expenses = sum(e['amount'] for e in expenses)
            total_income = sum(i['amount'] for i in income)

            output += (
                f"\nTHIS MONTH ({month_start} to now):\n"
                f"  Total Income:    \u00a3{total_income:.2f}\n"
                f"  Total Expenses:  \u00a3{total_expenses:.2f}\n"
                f"  Net Balance:     \u00a3{total_income - total_expenses:.2f}\n"
            )

            # Also update the inline text for backward compat
            self.budget_report_text.delete('1.0', tk.END)
            self.budget_report_text.insert(tk.END, output)

            self._open_report_window("Financial Summary", output)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def show_spending_analysis(self):
        """Show spending by category breakdown in a new window"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import ExpenseManager

            # Get last 30 days
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')

            breakdown = ExpenseManager.get_spending_by_category(student_id, start_date, end_date)

            total = sum(cat['total_amount'] for cat in breakdown)
            output = (
                f"{'='*70}\n"
                f"SPENDING BY CATEGORY\n"
                f"{'='*70}\n"
                f"Period: {start_date} to {end_date}\n"
                f"Total Spending: \u00a3{total:.2f}\n"
                f"{'='*70}\n"
            )

            if breakdown:
                for cat in breakdown:
                    pct = (cat['total_amount'] / total * 100) if total > 0 else 0
                    output += (
                        f"\n{cat['category_name']} ({cat['category_type'] or 'N/A'})\n"
                        f"  Total: \u00a3{cat['total_amount']:.2f} ({pct:.1f}%)\n"
                        f"  Transactions: {cat['transaction_count']}\n"
                        f"  Average: \u00a3{cat['average_amount']:.2f}\n"
                        f"  Range: \u00a3{cat['min_amount']:.2f} - \u00a3{cat['max_amount']:.2f}\n"
                    )
            else:
                output += "\nNo spending data found for this period.\n"

            self.budget_report_text.delete('1.0', tk.END)
            self.budget_report_text.insert(tk.END, output)

            self._open_report_window("Spending by Category", output)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def show_budget_performance(self):
        """Show budget vs actual performance report in a new window"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import BudgetManager

            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                messagebox.showinfo("No Data", "No active budgets found.")
                return

            budget_id = budgets[0]['budget_id']
            summary = BudgetManager.get_budget_summary(budget_id)

            # Status indicator
            if summary['budget_utilization_pct'] > summary['days_progress_pct'] + 10:
                status_line = "WARNING: Spending ahead of schedule!"
            elif summary['budget_utilization_pct'] < summary['days_progress_pct'] - 10:
                status_line = "Good: Spending below pace"
            else:
                status_line = "On track"

            output = (
                f"{'='*70}\n"
                f"BUDGET VS ACTUAL ANALYSIS\n"
                f"{'='*70}\n\n"
                f"Budget: {summary['budget_name']}\n"
                f"Type: {summary['budget_type'].capitalize()}\n"
                f"Period: {summary['start_date']} to {summary['end_date']}\n\n"
                f"Overall Performance:\n"
                f"  Budgeted: \u00a3{summary['total_budget']:.2f}\n"
                f"  Spent: \u00a3{summary['spent_amount']:.2f}\n"
                f"  Variance: \u00a3{summary['remaining_budget']:.2f}\n"
                f"  Utilization: {summary['budget_utilization_pct']:.1f}%\n\n"
                f"Time Progress: {summary['days_progress_pct']:.1f}%\n"
                f"Spending Progress: {summary['budget_utilization_pct']:.1f}%\n\n"
                f"Status: {status_line}\n"
            )

            if summary.get('categories'):
                output += f"\n{'='*70}\nCATEGORY BREAKDOWN\n{'='*70}\n"
                for cat in summary['categories']:
                    spent_pct = (cat['spent_amount'] / cat['allocated_amount'] * 100) if cat['allocated_amount'] > 0 else 0
                    variance = cat['allocated_amount'] - cat['spent_amount']
                    status = "OK" if spent_pct <= 100 else "OVER"

                    output += (
                        f"\n{cat['category_name']} [{status}]\n"
                        f"  Budgeted: \u00a3{cat['allocated_amount']:.2f}\n"
                        f"  Spent: \u00a3{cat['spent_amount']:.2f} ({spent_pct:.1f}%)\n"
                        f"  Variance: \u00a3{variance:.2f}\n"
                    )

            self.budget_report_text.delete('1.0', tk.END)
            self.budget_report_text.insert(tk.END, output)

            self._open_report_window("Budget vs Actual", output)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def show_spending_trends(self):
        """Show spending trends analysis in a new window"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import ExpenseManager

            trends = ExpenseManager.get_spending_trends(student_id, days=30)
            stats = trends['statistics']

            output = (
                f"{'='*70}\n"
                f"SPENDING TRENDS (30 Days)\n"
                f"{'='*70}\n\n"
                f"Period: {trends['start_date']} to {trends['end_date']}\n\n"
                f"Overall Statistics:\n"
                f"  Total Spent: \u00a3{stats['total_spent']:.2f}\n"
                f"  Total Transactions: {stats['total_transactions']}\n"
                f"  Average Transaction: \u00a3{stats['average_transaction']:.2f}\n"
                f"  Average Daily Spending: \u00a3{stats['average_daily_spending']:.2f}\n"
                f"  Transaction Range: \u00a3{stats['min_transaction']:.2f} - \u00a3{stats['max_transaction']:.2f}\n\n"
                f"{'='*70}\n"
                f"DAILY SPENDING (Last 14 Days)\n"
                f"{'='*70}\n\n"
            )

            if trends['daily_spending']:
                for day in trends['daily_spending'][-14:]:
                    output += f"{day['expense_date']}: \u00a3{day['daily_total']:.2f}\n"
            else:
                output += "No spending data found for this period.\n"

            self.budget_report_text.delete('1.0', tk.END)
            self.budget_report_text.insert(tk.END, output)

            self._open_report_window("Spending Trends", output)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    # ------------------------------------------------------------------
    # Toolbar wrapper methods (kept for backward compat with manager.py)
    # ------------------------------------------------------------------

    def gui_budget_vs_actual_analysis(self):
        """GUI wrapper for budget_vs_actual_analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_vs_actual_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')
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

            self.show_tab('reports')
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

            self.show_tab('reports')
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

            self.show_tab('reports')
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
