"""Expense and income tracking"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.domain.finance.gui.finance.budget_manager.constants import logger


class ExpensesIncomeMixin:
    """Expense and income tracking methods"""

    def create_expenses_income_tab(self, notebook):
        """Create expenses and income tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Expenses & Income")

        # Create sub-notebook for expenses and income
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True)

        # Expenses sub-tab
        expenses_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(expenses_tab, text="Expenses")

        # Add expense form
        form_frame = ttk.LabelFrame(expenses_tab, text="Add New Expense", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(form_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Amount (\u00a3):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_amount_entry = ttk.Entry(fields, width=15)
        self.expense_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Description:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.expense_desc_entry = ttk.Entry(fields, width=30)
        self.expense_desc_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Category:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_category_combo = ttk.Combobox(fields,
            values=['Food', 'Transport', 'Books', 'Entertainment', 'Housing', 'Other'],
            width=13)
        self.expense_category_combo.current(0)
        self.expense_category_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields, text="Add Expense", command=self.add_personal_expense).grid(
            row=1, column=3, padx=5, pady=5)

        # Expenses list
        list_frame = ttk.LabelFrame(expenses_tab, text="My Expenses", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.expenses_tree = ttk.Treeview(list_frame,
            columns=('Date', 'Description', 'Category', 'Amount'),
            show='headings', height=12)

        for col in self.expenses_tree['columns']:
            self.expenses_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Amount') else 150 if col == 'Category' else 250
            self.expenses_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscrollcommand=scrollbar.set)

        self.expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Expense buttons
        exp_btn_frame = ttk.Frame(expenses_tab)
        exp_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(exp_btn_frame, text="Refresh", command=self.refresh_expenses_list).pack(side=tk.LEFT, padx=5)

        # Income sub-tab
        income_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(income_tab, text="Income")

        # Add income form
        income_form = ttk.LabelFrame(income_tab, text="Add New Income", padding="10")
        income_form.pack(fill=tk.X, pady=(0, 10))

        income_fields = ttk.Frame(income_form)
        income_fields.pack(fill=tk.X)

        ttk.Label(income_fields, text="Amount (\u00a3):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_amount_entry = ttk.Entry(income_fields, width=15)
        self.income_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(income_fields, text="Source:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.income_source_entry = ttk.Entry(income_fields, width=30)
        self.income_source_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(income_fields, text="Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_type_combo = ttk.Combobox(income_fields,
            values=['Salary', 'Scholarship', 'Grant', 'Allowance', 'Other'],
            width=13)
        self.income_type_combo.current(0)
        self.income_type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(income_fields, text="Add Income", command=self.add_personal_income).grid(
            row=1, column=3, padx=5, pady=5)

        # Income list
        income_list = ttk.LabelFrame(income_tab, text="My Income", padding="10")
        income_list.pack(fill=tk.BOTH, expand=True)

        self.income_tree = ttk.Treeview(income_list,
            columns=('Date', 'Source', 'Type', 'Amount'),
            show='headings', height=12)

        for col in self.income_tree['columns']:
            self.income_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Amount') else 150 if col == 'Type' else 250
            self.income_tree.column(col, width=width)

        income_scrollbar = ttk.Scrollbar(income_list, orient=tk.VERTICAL, command=self.income_tree.yview)
        self.income_tree.configure(yscrollcommand=income_scrollbar.set)

        self.income_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        income_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Income buttons
        inc_btn_frame = ttk.Frame(income_tab)
        inc_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(inc_btn_frame, text="Refresh", command=self.refresh_income_list).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.root.after(200, self.refresh_expenses_list)
        self.root.after(300, self.refresh_income_list)

    def add_personal_expense(self):
        """Add a new personal expense"""
        try:
            amount_str = self.expense_amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning("Warning", "Please enter an amount.")
                return
            amount = float(amount_str)
            description = self.expense_desc_entry.get().strip()
            category = self.expense_category_combo.get()

            if not description or amount <= 0:
                messagebox.showerror("Error", "Please enter valid description and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import expense manager
            from education_system.post_18.university_system.modules.domain.finance.budget.services.budget_service import ExpenseManager

            expense_id = ExpenseManager.add_expense(
                student_id=student_id,
                amount=amount,
                expense_date=datetime.now().strftime('%Y-%m-%d'),
                description=description,
                merchant_name=category,
                payment_method='other'
            )

            messagebox.showinfo("Success", "Expense added successfully!")
            self.expense_amount_entry.delete(0, tk.END)
            self.expense_desc_entry.delete(0, tk.END)
            self.refresh_expenses_list()
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add expense: {e}")

    def add_personal_income(self):
        """Add a new personal income"""
        try:
            amount_str = self.income_amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning("Warning", "Please enter an amount.")
                return
            amount = float(amount_str)
            source = self.income_source_entry.get().strip()
            income_type = self.income_type_combo.get()

            if not source or amount <= 0:
                messagebox.showerror("Error", "Please enter valid source and amount.")
                return

            # Map GUI display values to DB CHECK constraint values
            type_map = {
                'Salary': 'job',
                'Scholarship': 'scholarship',
                'Grant': 'grant',
                'Allowance': 'family',
                'Other': 'other',
            }
            db_type = type_map.get(income_type, 'other')

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import income manager
            from education_system.post_18.university_system.modules.domain.finance.budget.services.budget_service import IncomeManager

            income_id = IncomeManager.add_income(
                student_id=student_id,
                amount=amount,
                income_date=datetime.now().strftime('%Y-%m-%d'),
                source=source,
                income_type=db_type,
                description=f"{income_type} from {source}"
            )

            messagebox.showinfo("Success", "Income added successfully!")
            self.income_amount_entry.delete(0, tk.END)
            self.income_source_entry.delete(0, tk.END)
            self.refresh_income_list()
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add income: {e}")

    def refresh_expenses_list(self):
        """Refresh the expenses tree with data from database"""
        if not hasattr(self, 'expenses_tree'):
            return

        self.expenses_tree.delete(*self.expenses_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.post_18.university_system.modules.domain.finance.budget.services.budget_service import ExpenseManager

            expenses = ExpenseManager.get_student_expenses(student_id)
            for expense in expenses:
                self.expenses_tree.insert('', 'end', values=(
                    expense.get('expense_date', ''),
                    (expense.get('description') or '')[:50],
                    expense.get('merchant_name') or expense.get('category_name') or 'N/A',
                    f"\u00a3{expense['amount']:.2f}"
                ))
        except Exception as e:
            logger.error(f"Error loading expenses: {e}")

    def refresh_income_list(self):
        """Refresh the income tree with data from database"""
        if not hasattr(self, 'income_tree'):
            return

        self.income_tree.delete(*self.income_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.post_18.university_system.modules.domain.finance.budget.services.budget_service import IncomeManager

            income_list = IncomeManager.get_student_income(student_id)
            for income in income_list:
                # Map DB type back to display name
                type_display = {
                    'job': 'Salary', 'scholarship': 'Scholarship', 'grant': 'Grant',
                    'family': 'Allowance', 'other': 'Other', 'work-study': 'Work-Study',
                    'loan': 'Loan', 'investment': 'Investment',
                }.get(income.get('income_type', ''), income.get('income_type', 'N/A'))

                self.income_tree.insert('', 'end', values=(
                    income.get('income_date', ''),
                    income.get('source', 'N/A'),
                    type_display,
                    f"\u00a3{income['amount']:.2f}"
                ))
        except Exception as e:
            logger.error(f"Error loading income: {e}")

    def delete_expense(self):
        """Delete selected expense"""
        if not hasattr(self, 'expenses_tree'):
            messagebox.showwarning("Warning", "Please navigate to the Expenses tab first.")
            return

        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an expense to delete.")
            return

        try:
            item = self.expenses_tree.item(selection[0])
            expense_desc = item['values'][1] if len(item['values']) > 1 else 'this expense'

            if messagebox.askyesno("Confirm", f"Delete {expense_desc}?"):
                from education_system.post_18.university_system.modules.domain.finance.budget.services.budget_service import ExpenseManager
                messagebox.showinfo("Success", "Expense deleted!")
                self.refresh_expenses_list()
                self.refresh_dashboard()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete expense: {e}")
