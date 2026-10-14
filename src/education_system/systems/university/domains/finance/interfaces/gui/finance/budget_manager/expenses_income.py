"""Expense and income tracking"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.systems.university.domains.finance.interfaces.gui.finance.budget_manager.constants import logger


def _date_range(from_entry, to_entry):
    """(start, end) from two optional YYYY-MM-DD entries; raises ValueError on bad input."""
    bounds = []
    for entry in (from_entry, to_entry):
        text = entry.get().strip() if entry is not None else ''
        if text:
            datetime.strptime(text, '%Y-%m-%d')
        bounds.append(text or None)
    return bounds[0], bounds[1]


class ExpensesIncomeMixin:
    """Expense and income tracking methods"""

    def create_expenses_income_tab(self, notebook):
        """Create expenses and income tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text=_t('gui.finance.finance.budget_manager.expenses_income.tabs.expenses_income', default="Expenses & Income"))

        # Create sub-notebook for expenses and income
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True)

        # Expenses sub-tab
        expenses_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(expenses_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.tabs.expenses', default="Expenses"))

        # Add expense form
        form_frame = ttk.LabelFrame(expenses_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.add_new_expense', default="Add New Expense"), padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(form_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.amount', default="Amount (\u00a3):")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_amount_entry = ttk.Entry(fields, width=15)
        self.expense_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.description', default="Description:")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.expense_desc_entry = ttk.Entry(fields, width=30)
        self.expense_desc_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.category', default="Category:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_category_combo = ttk.Combobox(fields,
            values=['Food', 'Transport', 'Books', 'Entertainment', 'Housing', 'Other'],
            width=13)
        self.expense_category_combo.current(0)
        self.expense_category_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.add_expense', default="Add Expense"), command=self.add_personal_expense).grid(
            row=1, column=3, padx=5, pady=5)

        # Expenses list
        list_frame = ttk.LabelFrame(expenses_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.my_expenses', default="My Expenses"), padding="10")
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
        ttk.Button(exp_btn_frame, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.refresh', default="Refresh"), command=self.refresh_expenses_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(exp_btn_frame, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.edit_expense', default="Edit Expense"), command=self.edit_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(exp_btn_frame, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.delete_expense', default="Delete Expense"), command=self.delete_expense).pack(side=tk.LEFT, padx=5)
        self.expense_from_entry, self.expense_to_entry = self._date_filter(exp_btn_frame, self.refresh_expenses_list)

        # Income sub-tab
        income_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(income_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.tabs.income', default="Income"))

        # Add income form
        income_form = ttk.LabelFrame(income_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.add_new_income', default="Add New Income"), padding="10")
        income_form.pack(fill=tk.X, pady=(0, 10))

        income_fields = ttk.Frame(income_form)
        income_fields.pack(fill=tk.X)

        ttk.Label(income_fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.amount', default="Amount (\u00a3):")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_amount_entry = ttk.Entry(income_fields, width=15)
        self.income_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(income_fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.source', default="Source:")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.income_source_entry = ttk.Entry(income_fields, width=30)
        self.income_source_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(income_fields, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.type', default="Type:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_type_combo = ttk.Combobox(income_fields,
            values=['Salary', 'Scholarship', 'Grant', 'Allowance', 'Other'],
            width=13)
        self.income_type_combo.current(0)
        self.income_type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(income_fields, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.add_income', default="Add Income"), command=self.add_personal_income).grid(
            row=1, column=3, padx=5, pady=5)

        # Income list
        income_list = ttk.LabelFrame(income_tab, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.my_income', default="My Income"), padding="10")
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
        ttk.Button(inc_btn_frame, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.refresh', default="Refresh"), command=self.refresh_income_list).pack(side=tk.LEFT, padx=5)
        self.income_from_entry, self.income_to_entry = self._date_filter(inc_btn_frame, self.refresh_income_list)

        # Initial load
        self.root.after(200, self.refresh_expenses_list)
        self.root.after(300, self.refresh_income_list)

    def _date_filter(self, bar, command):
        """From/To date entries plus a Filter button on an action bar (CLI: view by date range)."""
        ttk.Label(bar, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.from_date', default="From:")).pack(side=tk.LEFT, padx=(15, 2))
        from_entry = ttk.Entry(bar, width=11)
        from_entry.pack(side=tk.LEFT)
        ttk.Label(bar, text=_t('gui.finance.finance.budget_manager.expenses_income.labels.to_date', default="To:")).pack(side=tk.LEFT, padx=(8, 2))
        to_entry = ttk.Entry(bar, width=11)
        to_entry.pack(side=tk.LEFT)
        ttk.Button(bar, text=_t('gui.finance.finance.budget_manager.expenses_income.buttons.filter', default="Filter"), command=command).pack(side=tk.LEFT, padx=5)
        return from_entry, to_entry

    def _budget_student_id(self):
        current_user = self.gui.auth.get_current_user() if self.gui.auth else None
        return current_user.get('username') if current_user else 'guest'

    def _selected_expense(self):
        """The expense dict behind the selected row, or None after a warning."""
        selection = self.expenses_tree.selection() if hasattr(self, 'expenses_tree') else ()
        if not selection:
            messagebox.showwarning(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.please_select_an_expense', default="Please select an expense."))
            return None
        return getattr(self, '_expense_rows', {}).get(selection[0])

    def add_personal_expense(self):
        """Add a new personal expense"""
        try:
            amount_str = self.expense_amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.please_enter_an_amount', default="Please enter an amount."))
                return
            amount = float(amount_str)
            description = self.expense_desc_entry.get().strip()
            category = self.expense_category_combo.get()

            if not description or amount <= 0:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.please_enter_valid_description_and_amount', default="Please enter valid description and amount."))
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import expense manager
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import ExpenseManager

            expense_id = ExpenseManager.add_expense(
                student_id=student_id,
                amount=amount,
                expense_date=datetime.now().strftime('%Y-%m-%d'),
                description=description,
                merchant_name=category,
                payment_method='other'
            )

            messagebox.showinfo(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.expense_added_successfully', default="Expense added successfully!"))
            self.expense_amount_entry.delete(0, tk.END)
            self.expense_desc_entry.delete(0, tk.END)
            self.refresh_expenses_list()
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.invalid_amount_please_enter_a_number', default="Invalid amount. Please enter a number."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), f"Failed to add expense: {e}")

    def add_personal_income(self):
        """Add a new personal income"""
        try:
            amount_str = self.income_amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.please_enter_an_amount', default="Please enter an amount."))
                return
            amount = float(amount_str)
            source = self.income_source_entry.get().strip()
            income_type = self.income_type_combo.get()

            if not source or amount <= 0:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.please_enter_valid_source_and_amount', default="Please enter valid source and amount."))
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
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import IncomeManager

            income_id = IncomeManager.add_income(
                student_id=student_id,
                amount=amount,
                income_date=datetime.now().strftime('%Y-%m-%d'),
                source=source,
                income_type=db_type,
                description=f"{income_type} from {source}"
            )

            messagebox.showinfo(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.income_added_successfully', default="Income added successfully!"))
            self.income_amount_entry.delete(0, tk.END)
            self.income_source_entry.delete(0, tk.END)
            self.refresh_income_list()
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.invalid_amount_please_enter_a_number', default="Invalid amount. Please enter a number."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), f"Failed to add income: {e}")

    def refresh_expenses_list(self):
        """Refresh the expenses tree with data from database"""
        if not hasattr(self, 'expenses_tree'):
            return

        self.expenses_tree.delete(*self.expenses_tree.get_children())
        self._expense_rows = {}
        try:
            start_date, end_date = _date_range(getattr(self, 'expense_from_entry', None),
                                               getattr(self, 'expense_to_entry', None))
        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.date_format', default="Dates must be YYYY-MM-DD."))
            return
        try:
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import ExpenseManager

            expenses = ExpenseManager.get_student_expenses(self._budget_student_id(), start_date, end_date)
            for expense in expenses:
                iid = self.expenses_tree.insert('', 'end', values=(
                    expense.get('expense_date', ''),
                    (expense.get('description') or '')[:50],
                    expense.get('merchant_name') or expense.get('category_name') or 'N/A',
                    f"\u00a3{expense['amount']:.2f}"
                ))
                self._expense_rows[iid] = expense
        except Exception as e:
            logger.error(f"Error loading expenses: {e}")

    def refresh_income_list(self):
        """Refresh the income tree with data from database"""
        if not hasattr(self, 'income_tree'):
            return

        self.income_tree.delete(*self.income_tree.get_children())
        try:
            start_date, end_date = _date_range(getattr(self, 'income_from_entry', None),
                                               getattr(self, 'income_to_entry', None))
        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.date_format', default="Dates must be YYYY-MM-DD."))
            return
        try:
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import IncomeManager

            income_list = IncomeManager.get_student_income(self._budget_student_id(), start_date, end_date)
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
        """Delete the selected expense (CLI: Delete Expense)."""
        expense = self._selected_expense()
        if expense is None:
            return
        expense_desc = expense.get('description') or 'this expense'
        if not messagebox.askyesno(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.confirm', default="Confirm"), f"Delete {expense_desc}?"):
            return
        try:
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import ExpenseManager
            if ExpenseManager.delete_expense(expense['expense_id']):
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.expense_deleted', default="Expense deleted!"))
            else:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.expense_not_found', default="Expense not found."))
            self.refresh_expenses_list()
            self.refresh_dashboard()
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), f"Failed to delete expense: {e}")

    def edit_expense(self):
        """Update the selected expense (CLI: Update Expense)."""
        expense = self._selected_expense()
        if expense is None:
            return
        values = ask_form(self.root, _t('gui.finance.finance.budget_manager.expenses_income.windows.edit_expense', default="Edit Expense"), [
            Field('amount', 'Amount', kind='float', default=str(expense.get('amount') or '')),
            Field('description', 'Description', default=expense.get('description') or ''),
            Field('expense_date', 'Date (YYYY-MM-DD)', default=expense.get('expense_date') or ''),
            Field('merchant_name', 'Category / merchant', default=expense.get('merchant_name') or '', optional=True),
        ])
        if values is None:
            return
        try:
            datetime.strptime(values['expense_date'], '%Y-%m-%d')
            if values['amount'] <= 0:
                raise ValueError('amount')
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import ExpenseManager
            ExpenseManager.update_expense(expense['expense_id'], amount=values['amount'],
                                          description=values['description'],
                                          expense_date=values['expense_date'],
                                          merchant_name=values.get('merchant_name') or '')
            messagebox.showinfo(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.expense_updated', default="Expense updated!"))
            self.refresh_expenses_list()
            self.refresh_dashboard()
        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.expenses_income.dialogs.invalid_amount_or_date', default="Amount must be positive and the date YYYY-MM-DD."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.expenses_income.dialogs.error', default="Error"), f"Failed to update expense: {e}")
