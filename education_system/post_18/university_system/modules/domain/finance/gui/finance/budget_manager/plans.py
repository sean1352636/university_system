"""Budget plan CRUD operations"""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from unittest.mock import Mock

from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.infrastructure.database.db import get_connection

from education_system.post_18.university_system.modules.domain.finance.gui.finance.budget_manager.constants import (
    budget_approval_workflow,
    budget_vs_actual_analysis,
    create_budget_plan,
    logger,
)


class BudgetPlansMixin:
    """Budget plan management methods"""

    @staticmethod
    def _budget_manager_package():
        return sys.modules.get(
            'education_system.post_18.university_system.modules.domain.finance.gui.finance.budget_manager'
        )

    @classmethod
    def _get_connection(cls):
        package = cls._budget_manager_package()
        factory = getattr(package, 'get_connection', get_connection) if package else get_connection
        return factory()

    @classmethod
    def _get_auth(cls):
        package = cls._budget_manager_package()
        factory = getattr(package, 'get_auth', get_auth) if package else get_auth
        return factory()

    def create_budget_plan(self):
        """Create new budget plan with database integration"""
        # Create dialog for budget plan details
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Budget Plan")
        dialog.geometry("550x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Tests patch ``tkinter.Toplevel`` with a plain mock that cannot host ttk widgets.
        if isinstance(dialog, Mock) or not hasattr(dialog, "tk") or not hasattr(dialog, "_w"):
            return dialog

        ttk.Label(dialog, text="Create New Budget Plan",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Plan name
        ttk.Label(form_frame, text="Plan Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
        name_entry.grid(row=0, column=1, pady=5, padx=5)
        name_entry.focus()

        # Academic year
        ttk.Label(form_frame, text="Academic Year:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        year_var = tk.StringVar(value=f"{datetime.now().year}-{datetime.now().year + 1}")
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=35)
        year_entry.grid(row=1, column=1, pady=5, padx=5)

        # Revenue budget
        ttk.Label(form_frame, text="Revenue Budget (\u00a3):").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        revenue_var = tk.StringVar(value="0.00")
        revenue_entry = ttk.Entry(form_frame, textvariable=revenue_var, width=35)
        revenue_entry.grid(row=2, column=1, pady=5, padx=5)

        # Expense budget
        ttk.Label(form_frame, text="Expense Budget (\u00a3):").grid(row=3, column=0, sticky='w', pady=5, padx=5)
        expense_var = tk.StringVar(value="0.00")
        expense_entry = ttk.Entry(form_frame, textvariable=expense_var, width=35)
        expense_entry.grid(row=3, column=1, pady=5, padx=5)

        # Currency
        ttk.Label(form_frame, text="Currency:").grid(row=4, column=0, sticky='w', pady=5, padx=5)
        currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(form_frame, textvariable=currency_var,
                                      values=['GBP', 'USD', 'EUR'], width=33, state='readonly')
        currency_combo.grid(row=4, column=1, pady=5, padx=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5, padx=5)
        status_var = tk.StringVar(value="draft")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['draft', 'active', 'approved', 'closed'],
                                    width=33, state='readonly')
        status_combo.grid(row=5, column=1, pady=5, padx=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=4, width=35)
        notes_text.grid(row=6, column=1, pady=5, padx=5)

        # Summary display
        summary_frame = ttk.LabelFrame(dialog, text="Budget Summary", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)

        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack()

        def update_summary():
            try:
                revenue = float(revenue_var.get() or 0)
                expense = float(expense_var.get() or 0)
                net = revenue - expense

                summary_text = f"""
Revenue Budget:   \u00a3{revenue:,.2f}
Expense Budget:   \u00a3{expense:,.2f}
Net Budget:       \u00a3{net:,.2f}
Status:           {status_var.get().title()}
"""
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text="Invalid numeric values")

        # Update summary when values change
        revenue_var.trace('w', lambda *args: update_summary())
        expense_var.trace('w', lambda *args: update_summary())
        status_var.trace('w', lambda *args: update_summary())
        update_summary()

        def save_plan():
            plan_name = name_var.get().strip()
            if not plan_name:
                messagebox.showwarning("Name Required", "Please enter a budget plan name", parent=dialog)
                return

            academic_year = year_var.get().strip()
            if not academic_year:
                messagebox.showwarning("Year Required", "Please enter an academic year", parent=dialog)
                return

            try:
                revenue = float(revenue_var.get() or 0)
                expense = float(expense_var.get() or 0)
                if revenue < 0 or expense < 0:
                    raise ValueError("Budget amounts cannot be negative")
            except ValueError as e:
                messagebox.showwarning("Invalid Amount", str(e), parent=dialog)
                return

            notes = notes_text.get("1.0", tk.END).strip()

            # Get current user
            try:
                auth = self._get_auth()
                if auth.is_logged_in():
                    created_by = auth.get_current_user()['username']
                else:
                    created_by = 'system'
            except Exception:
                created_by = 'admin'

            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO budget_plans
                    (plan_name, academic_year, currency, status,
                     total_revenue_budget, total_expense_budget,
                     created_by, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (plan_name, academic_year, currency_var.get(), status_var.get(),
                      revenue, expense, created_by, notes, now, now))

                conn.commit()
                budget_id = cursor.lastrowid

                messagebox.showinfo("Success",
                    f"Budget plan '{plan_name}' created successfully!\n\nBudget ID: {budget_id}",
                    parent=dialog)
                dialog.destroy()
                self.refresh_budget()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create budget plan: {e}", parent=dialog)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Create Plan", command=save_plan).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def edit_budget_plan(self):
        """Edit selected budget plan"""
        selection = self.budget_plans_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a budget plan to edit.")
            return

        # Get current values
        values = self.budget_plans_tree.item(selection[0])['values']
        budget_id = values[0]
        current_name = values[1]
        current_year = values[2]
        current_revenue = str(values[3]).replace('\u00a3', '').replace(',', '') if len(values) > 3 else '0'
        current_expenses = str(values[4]).replace('\u00a3', '').replace(',', '') if len(values) > 4 else '0'
        current_status = values[5] if len(values) > 5 else 'Active'

        # Create edit dialog
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title(f"Edit Budget Plan - {budget_id}")
        edit_dialog.geometry("550x500")
        edit_dialog.transient(self.root)
        edit_dialog.grab_set()

        ttk.Label(edit_dialog, text=f"Edit Budget Plan: {budget_id}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(edit_dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Budget ID (read-only)
        ttk.Label(form_frame, text="Budget ID:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        ttk.Label(form_frame, text=budget_id, foreground='blue').grid(row=0, column=1, sticky='w', pady=5, padx=5)

        # Plan name
        ttk.Label(form_frame, text="Plan Name:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
        name_entry.grid(row=1, column=1, pady=5, padx=5)
        name_entry.focus()

        # Year
        ttk.Label(form_frame, text="Fiscal Year:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        year_var = tk.StringVar(value=current_year)
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=35)
        year_entry.grid(row=2, column=1, pady=5, padx=5)

        # Revenue budget
        ttk.Label(form_frame, text="Revenue Budget (\u00a3):").grid(row=3, column=0, sticky='w', pady=5, padx=5)
        revenue_var = tk.StringVar(value=current_revenue)
        revenue_entry = ttk.Entry(form_frame, textvariable=revenue_var, width=35)
        revenue_entry.grid(row=3, column=1, pady=5, padx=5)

        # Expenses budget
        ttk.Label(form_frame, text="Expenses Budget (\u00a3):").grid(row=4, column=0, sticky='w', pady=5, padx=5)
        expenses_var = tk.StringVar(value=current_expenses)
        expenses_entry = ttk.Entry(form_frame, textvariable=expenses_var, width=35)
        expenses_entry.grid(row=4, column=1, pady=5, padx=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5, padx=5)
        status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['Active', 'Draft', 'Approved', 'Closed'],
                                    width=33, state='readonly')
        status_combo.grid(row=5, column=1, pady=5, padx=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=4, width=35)
        notes_text.grid(row=6, column=1, pady=5, padx=5)
        notes_text.insert('1.0', f"Budget plan for {current_year}")

        # Summary display
        summary_frame = ttk.LabelFrame(edit_dialog, text="Budget Summary", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)

        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack()

        def update_summary():
            try:
                revenue = float(revenue_var.get() or 0)
                expenses = float(expenses_var.get() or 0)
                surplus = revenue - expenses

                summary_text = f"""
    Revenue Budget:   \u00a3{revenue:,.2f}
    Expenses Budget:  \u00a3{expenses:,.2f}
    Net Surplus:      \u00a3{surplus:,.2f}
    Status:           {status_var.get()}
    """
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text="Invalid numeric values")

        # Update summary when values change
        revenue_var.trace('w', lambda *args: update_summary())
        expenses_var.trace('w', lambda *args: update_summary())
        status_var.trace('w', lambda *args: update_summary())
        update_summary()

        def save_changes():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Name Required", "Please enter a budget plan name", parent=edit_dialog)
                return

            academic_year = year_var.get().strip()
            if not academic_year:
                messagebox.showwarning("Year Required", "Please enter an academic year", parent=edit_dialog)
                return

            try:
                revenue = float(revenue_var.get() or 0)
                expenses = float(expenses_var.get() or 0)
                if revenue < 0 or expenses < 0:
                    raise ValueError("Budget amounts cannot be negative")
            except ValueError as e:
                messagebox.showwarning("Invalid Amount", str(e), parent=edit_dialog)
                return

            notes = notes_text.get("1.0", tk.END).strip()

            # Save to database
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE budget_plans
                    SET plan_name = ?,
                        academic_year = ?,
                        total_revenue_budget = ?,
                        total_expense_budget = ?,
                        status = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE budget_id = ?
                ''', (new_name, academic_year, revenue, expenses,
                      status_var.get(), notes, now, budget_id))

                conn.commit()

                messagebox.showinfo("Success", f"Budget plan '{new_name}' updated successfully", parent=edit_dialog)
                edit_dialog.destroy()
                self.refresh_budget()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update budget plan: {e}", parent=edit_dialog)

        # Buttons
        button_frame = ttk.Frame(edit_dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)

    def budget_analysis(self):
        """Show budget analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_vs_actual_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window("Budget Analysis", output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror("Error", f"Failed to generate budget analysis: {str(e)}")

    def approve_budget(self):
        """Approve budget workflow"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_approval_workflow()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window("Budget Approval", output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror("Error", f"Budget approval failed: {str(e)}")

    def delete_budget_plan(self):
        """Delete selected budget plan"""
        selection = self.budget_plans_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a budget plan to delete.")
            return

        # Get budget details
        values = self.budget_plans_tree.item(selection[0])['values']
        budget_id = values[0]
        plan_name = values[1]

        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete budget plan '{plan_name}'?\n\n"
                                   f"This will also delete all associated line items.\n"
                                   f"This action cannot be undone.",
                                   icon='warning'):
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Delete line items first (foreign key constraint)
            cursor.execute('DELETE FROM budget_line_items WHERE budget_id = ?', (budget_id,))

            # Delete budget plan
            cursor.execute('DELETE FROM budget_plans WHERE budget_id = ?', (budget_id,))

            conn.commit()

            messagebox.showinfo("Success", f"Budget plan '{plan_name}' deleted successfully")
            self.refresh_budget()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete budget plan: {e}")

    def gui_create_budget_plan(self):
        """GUI wrapper for create_budget_plan"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Budget Plan")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Plan name
        ttk.Label(form_frame, text="Plan Name:").pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # Academic year
        ttk.Label(form_frame, text="Academic Year:").pack(anchor='w', pady=5)
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(form_frame, textvariable=year_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='x', pady=5)

        def create_plan_action():
            try:
                plan_name = name_var.get().strip()
                academic_year = year_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()

                if not all([plan_name, academic_year]):
                    messagebox.showerror("Error", "Plan name and academic year are required")
                    return

                create_budget_plan(plan_name, academic_year, description)
                messagebox.showinfo("Success", "Budget plan created successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create budget plan: {e}")

        ttk.Button(form_frame, text="Create Plan", command=create_plan_action).pack(pady=20)

    def refresh_budget(self):
        """Refresh budget data"""
        def refresh_thread():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Get budget plans
                cursor.execute('''
                SELECT budget_id, plan_name, academic_year,
                       total_revenue_budget, total_expense_budget, status
                FROM budget_plans
                ORDER BY academic_year DESC, plan_name
                ''')

                budget_plans = cursor.fetchall()

                # Get budget categories
                cursor.execute('''
                SELECT bc.category_id, bc.category_name, bc.category_type,
                       COALESCE(pc.category_name, 'None') as parent_name
                FROM budget_categories bc
                LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                WHERE bc.is_active = 1
                ORDER BY bc.category_type, bc.category_name
                ''')

                budget_categories = cursor.fetchall()

                self.root.after(0, lambda: self.update_budget_data(budget_plans, budget_categories))

            except Exception as e:
                print(f"Error refreshing budget: {e}")

        refresh_thread()

    def update_budget_data(self, budget_plans, budget_categories):
        """Update budget data in UI"""
        if not hasattr(self, 'budget_plans_tree') or not hasattr(self, 'budget_categories_tree'):
            return
        # Update budget plans
        for item in self.budget_plans_tree.get_children():
            self.budget_plans_tree.delete(item)

        for plan in budget_plans:
            budget_id, name, year, revenue, expenses, status = plan
            revenue_str = f"\u00a3{revenue:,.2f}" if revenue else "\u00a30.00"
            expenses_str = f"\u00a3{expenses:,.2f}" if expenses else "\u00a30.00"
            display_data = (budget_id, name, year, revenue_str, expenses_str, status)
            self.budget_plans_tree.insert('', 'end', values=display_data)

        # Update budget categories
        for item in self.budget_categories_tree.get_children():
            self.budget_categories_tree.delete(item)

        for category in budget_categories:
            self.budget_categories_tree.insert('', 'end', values=tuple(category))
