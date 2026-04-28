import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ClubFinancialReportsDialog:
    """Dialog for viewing club financial reports"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Financial Reports")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Club Financial Reports", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Club selection
        club_frame = ttk.LabelFrame(main_frame, text="Select Club and Period")
        club_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(club_frame, text="Club:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=40, state="readonly")
        self.club_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(club_frame, text="Period:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.period_var = tk.StringVar(value="current_month")
        ttk.Combobox(club_frame, textvariable=self.period_var,
                    values=["current_month", "last_month", "current_year", "last_year", "all_time"],
                    state="readonly", width=38).grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(club_frame, text="Generate Report", command=self.generate_report).grid(row=0, column=2, padx=5, pady=5)

        # Report display
        report_frame = ttk.LabelFrame(main_frame, text="Financial Report")
        report_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.report_text = scrolledtext.ScrolledText(report_frame, height=20, width=80)
        self.report_text.pack(fill='both', expand=True, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export PDF", command=self.export_pdf).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def generate_report(self):
        """Generate comprehensive financial report"""
        self.report_text.delete("1.0", tk.END)

        club_selection = self.club_var.get()
        if not club_selection:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Extract club_id from selection (format: "Club Name (ID: X)")
            club_id = club_selection.split("(ID: ")[1].rstrip(")")

            # Get period dates
            period = self.period_var.get()
            if period == "current_month":
                date_filter = "AND strftime('%Y-%m', expense_date) = strftime('%Y-%m', 'now')"
                period_name = "Current Month"
            elif period == "last_month":
                date_filter = "AND strftime('%Y-%m', expense_date) = strftime('%Y-%m', 'now', '-1 month')"
                period_name = "Last Month"
            elif period == "current_year":
                date_filter = "AND strftime('%Y', expense_date) = strftime('%Y', 'now')"
                period_name = "Current Year"
            elif period == "last_year":
                date_filter = "AND strftime('%Y', expense_date) = strftime('%Y', 'now', '-1 year')"
                period_name = "Last Year"
            else:
                date_filter = ""
                period_name = "All Time"

            # Get club name
            cursor.execute('SELECT club_name FROM student_clubs WHERE club_id = ?', (club_id,))
            club_name = cursor.fetchone()[0]

            # Generate report header
            report = f"FINANCIAL REPORT: {club_name}\n"
            report += f"Period: {period_name}\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report += "=" * 80 + "\n\n"

            # Get budget information
            cursor.execute('''
            SELECT SUM(amount), category
            FROM club_budgets
            WHERE club_id = ?
            GROUP BY category
            ''', (club_id,))

            budgets = cursor.fetchall()
            total_budget = sum([b[0] or 0 for b in budgets])

            report += "BUDGET ALLOCATION:\n"
            report += "-" * 80 + "\n"
            if budgets:
                for budget in budgets:
                    report += f"  {budget[1]}: £{budget[0]:,.2f}\n"
                report += f"\nTotal Budget: £{total_budget:,.2f}\n\n"
            else:
                report += "  No budget set for this club.\n\n"

            # Get expenses
            cursor.execute('''
            SELECT SUM(amount), category
            FROM club_expenses
            WHERE club_id = ? ''' + date_filter + '''
            GROUP BY category
            ''', (club_id,))

            expenses = cursor.fetchall()
            total_expenses = sum([e[0] or 0 for e in expenses])

            report += "EXPENSES:\n"
            report += "-" * 80 + "\n"
            if expenses:
                for expense in expenses:
                    report += f"  {expense[1]}: £{expense[0]:,.2f}\n"
                report += f"\nTotal Expenses: £{total_expenses:,.2f}\n\n"
            else:
                report += "  No expenses recorded for this period.\n\n"

            # Get income
            cursor.execute('''
            SELECT SUM(amount), source
            FROM club_income
            WHERE club_id = ? ''' + date_filter + '''
            GROUP BY source
            ''', (club_id,))

            income = cursor.fetchall()
            total_income = sum([i[0] or 0 for i in income])

            report += "INCOME:\n"
            report += "-" * 80 + "\n"
            if income:
                for inc in income:
                    report += f"  {inc[1]}: £{inc[0]:,.2f}\n"
                report += f"\nTotal Income: £{total_income:,.2f}\n\n"
            else:
                report += "  No income recorded for this period.\n\n"

            # Summary
            report += "FINANCIAL SUMMARY:\n"
            report += "=" * 80 + "\n"
            report += f"Total Income:    £{total_income:,.2f}\n"
            report += f"Total Expenses:  £{total_expenses:,.2f}\n"
            report += f"Net Position:    £{(total_income - total_expenses):,.2f}\n"

            if total_budget > 0:
                budget_used_pct = (total_expenses / total_budget) * 100
                report += f"\nBudget Utilization: {budget_used_pct:.1f}%\n"
                report += f"Remaining Budget: £{(total_budget - total_expenses):,.2f}\n"

                if budget_used_pct > 90:
                    report += "\n⚠️ WARNING: Budget utilization is high!\n"
                elif budget_used_pct > 100:
                    report += "\n⛔ ALERT: Budget exceeded!\n"

            # Recent transactions
            report += "\n\nRECENT TRANSACTIONS:\n"
            report += "-" * 80 + "\n"

            cursor.execute('''
            SELECT expense_date, category, description, amount
            FROM club_expenses
            WHERE club_id = ? ''' + date_filter + '''
            ORDER BY expense_date DESC
            LIMIT 10
            ''', (club_id,))

            recent = cursor.fetchall()
            if recent:
                for trans in recent:
                    report += f"{trans[0][:10]:<12} {trans[1]:<15} {trans[2]:<30} £{trans[3]:>10,.2f}\n"
            else:
                report += "No recent transactions.\n"

            self.report_text.insert("1.0", report)
            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
            import traceback
            traceback.print_exc()

    def export_pdf(self):
        """Export report to PDF (simplified - saves as text file)"""
        try:
            from tkinter import filedialog
            import os

            report_content = self.report_text.get("1.0", tk.END)
            if not report_content.strip() or "coming soon" in report_content.lower():
                messagebox.showwarning("Warning", "Please generate a report first.")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Financial Report"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(report_content)
                messagebox.showinfo("Success", f"Report saved to {filename}")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to export report: {str(e)}")



class ClubBudgetDialog:
    """Dialog for managing club budgets"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Club Budgets")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Club Budget Management", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Club selection
        club_frame = ttk.LabelFrame(main_frame, text="Select Club")
        club_frame.pack(fill='x', pady=(0, 10))

        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=50, state="readonly")
        self.club_combo.pack(side='left', padx=5, pady=5)

        ttk.Button(club_frame, text="View Budget", command=self.view_budget).pack(side='left', padx=5)
        ttk.Button(club_frame, text="Set Budget", command=self.set_budget).pack(side='left', padx=5)

        # Budget details
        details_frame = ttk.LabelFrame(main_frame, text="Budget Overview")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.budget_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
        self.budget_text.pack(fill='both', expand=True, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def view_budget(self):
        """View comprehensive budget for selected club"""
        self.budget_text.delete("1.0", tk.END)

        club_selection = self.club_var.get()
        if not club_selection:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Extract club_id
            club_id = club_selection.split("(ID: ")[1].rstrip(")")

            # Get club name
            cursor.execute('SELECT club_name FROM student_clubs WHERE club_id = ?', (club_id,))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Club not found.")
                return

            club_name = result[0]

            budget_display = f"BUDGET OVERVIEW: {club_name}\n"
            budget_display += "=" * 80 + "\n\n"

            # Get budget allocations
            cursor.execute('''
            SELECT category, amount, fiscal_year, status
            FROM club_budgets
            WHERE club_id = ?
            ORDER BY fiscal_year DESC, category
            ''', (club_id,))

            budgets = cursor.fetchall()

            if not budgets:
                budget_display += "No budget has been set for this club.\n\n"
                budget_display += "Click 'Set Budget' to create a budget allocation."
            else:
                current_year = datetime.now().year
                budget_display += f"BUDGET CATEGORIES (Fiscal Year: {current_year}):\n"
                budget_display += "-" * 80 + "\n"
                budget_display += f"{'Category':<20} {'Allocated':<15} {'Spent':<15} {'Remaining':<15} {'Status':<10}\n"
                budget_display += "-" * 80 + "\n"

                total_allocated = 0
                total_spent = 0

                for budget in budgets:
                    category = budget[0]
                    amount = budget[1] or 0
                    fiscal_year = budget[2]
                    status = budget[3]

                    # Get spent amount for this category
                    cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0)
                    FROM club_expenses
                    WHERE club_id = ? AND category = ?
                    AND strftime('%Y', expense_date) = ?
                    ''', (club_id, category, str(fiscal_year)))

                    spent = cursor.fetchone()[0] or 0
                    remaining = amount - spent

                    total_allocated += amount
                    total_spent += spent

                    budget_display += f"{category:<20} £{amount:<14,.2f} £{spent:<14,.2f} £{remaining:<14,.2f} {status:<10}\n"

                budget_display += "-" * 80 + "\n"
                budget_display += f"{'TOTAL':<20} £{total_allocated:<14,.2f} £{total_spent:<14,.2f} £{(total_allocated - total_spent):<14,.2f}\n\n"

                # Calculate utilization percentage
                if total_allocated > 0:
                    utilization = (total_spent / total_allocated) * 100
                    budget_display += f"Budget Utilization: {utilization:.1f}%\n\n"

                    if utilization > 100:
                        budget_display += "⛔ ALERT: Budget exceeded! Immediate action required.\n"
                    elif utilization > 90:
                        budget_display += "⚠️ WARNING: Budget utilization is high. Monitor spending carefully.\n"
                    elif utilization > 75:
                        budget_display += "⚡ NOTICE: Over 75% of budget used.\n"

                # Show budget trends
                budget_display += "\nSPENDING BY CATEGORY:\n"
                budget_display += "-" * 80 + "\n"

                for budget in budgets:
                    category = budget[0]
                    amount = budget[1] or 0

                    cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0)
                    FROM club_expenses
                    WHERE club_id = ? AND category = ?
                    AND strftime('%Y', expense_date) = ?
                    ''', (club_id, category, str(current_year)))

                    spent = cursor.fetchone()[0] or 0

                    if amount > 0:
                        pct = (spent / amount) * 100
                        bar_length = int(pct / 2)  # Scale to 50 chars max
                        bar = "█" * min(bar_length, 50)
                        budget_display += f"{category:<20} [{bar:<50}] {pct:>5.1f}%\n"

            self.budget_text.insert("1.0", budget_display)
            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to view budget: {str(e)}")
            import traceback
            traceback.print_exc()

    def set_budget(self):
        """Set or modify budget for selected club"""
        club_selection = self.club_var.get()
        if not club_selection:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        # Create budget setting dialog
        budget_dialog = tk.Toplevel(self.dialog)
        budget_dialog.title("Set Club Budget")
        budget_dialog.geometry("600x500")
        budget_dialog.transient(self.dialog)
        budget_dialog.grab_set()

        frame = ttk.Frame(budget_dialog)
        frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(frame, text="Set Budget Allocation", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Fiscal year
        year_frame = ttk.Frame(frame)
        year_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(year_frame, text="Fiscal Year:").pack(side='left', padx=(0, 10))
        year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(year_frame, textvariable=year_var, width=10).pack(side='left')

        # Budget categories
        ttk.Label(frame, text="Budget Categories:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))

        categories_frame = ttk.Frame(frame)
        categories_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Scrollable frame for categories
        canvas = tk.Canvas(categories_frame, height=250)
        scrollbar = ttk.Scrollbar(categories_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        # Default budget categories
        default_categories = [
            "Events", "Marketing", "Equipment", "Travel", "Supplies",
            "Food & Beverages", "Venue Rental", "Membership", "Training", "Other"
        ]

        budget_entries = {}

        for i, category in enumerate(default_categories):
            cat_frame = ttk.Frame(scrollable_frame)
            cat_frame.grid(row=i, column=0, sticky='ew', padx=5, pady=2)

            ttk.Label(cat_frame, text=category, width=20).pack(side='left')
            ttk.Label(cat_frame, text="$").pack(side='left', padx=(10, 2))
            entry = ttk.Entry(cat_frame, width=15)
            entry.pack(side='left')
            entry.insert(0, "0.00")
            budget_entries[category] = entry

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Total display
        total_frame = ttk.Frame(frame)
        total_frame.pack(fill='x', pady=(10, 10))
        ttk.Label(total_frame, text="Total Budget:", font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
        total_label = ttk.Label(total_frame, text="£0.00", font=('Arial', 10))
        total_label.pack(side='left')

        def calculate_total(*args):
            total = 0
            for entry in budget_entries.values():
                try:
                    amount = float(entry.get() or 0)
                    total += amount
                except ValueError:
                    pass
            total_label.config(text=f"£{total:,.2f}")

        # Bind calculation to all entries
        for entry in budget_entries.values():
            entry.bind('<KeyRelease>', calculate_total)

        def save_budget():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                club_id = club_selection.split("(ID: ")[1].rstrip(")")
                fiscal_year = int(year_var.get())

                # Delete existing budget for this year
                cursor.execute('DELETE FROM club_budgets WHERE club_id = ? AND fiscal_year = ?',
                             (club_id, fiscal_year))

                # Insert new budget allocations
                for category, entry in budget_entries.items():
                    try:
                        amount = float(entry.get() or 0)
                        if amount > 0:
                            cursor.execute('''
                            INSERT INTO club_budgets (club_id, category, amount, fiscal_year, status)
                            VALUES (?, ?, ?, ?, 'active')
                            ''', (club_id, category, amount, fiscal_year))
                    except ValueError:
                        continue

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Budget saved successfully!")
                budget_dialog.destroy()
                self.view_budget()  # Refresh the budget view

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to save budget: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Save Budget", command=save_budget).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=budget_dialog.destroy).pack(side='left')



def view_club_financial_reports_gui(self):
    """View club financial reports with GUI dialog"""
    try:
        dialog = ClubFinancialReportsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def manage_club_budgets_gui(self):
    """Manage club budgets with GUI dialog"""
    try:
        dialog = ClubBudgetDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


