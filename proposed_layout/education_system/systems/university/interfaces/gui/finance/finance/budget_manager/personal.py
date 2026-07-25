"""Personal budget dashboard and operations"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta

from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.constants import logger


class PersonalBudgetMixin:
    """Personal budget dashboard and management methods"""

    def create_personal_budget_dashboard(self, notebook):
        """Create personal budget dashboard tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Dashboard")

        # Get current user
        current_user = self.gui.auth.get_current_user() if self.gui.auth else None
        student_id = current_user.get('username') if current_user else 'guest'

        # Summary cards frame
        cards_frame = ttk.Frame(tab)
        cards_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Left column - Current Budget Summary
        left_frame = ttk.LabelFrame(cards_frame, text="Current Budget Summary", padding="15")
        left_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        self.dashboard_labels = {}
        labels = ['Budget Name', 'Total Budget', 'Spent', 'Remaining', 'Utilization %']
        for i, label in enumerate(labels):
            ttk.Label(left_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky=tk.W, padx=5, pady=5)
            self.dashboard_labels[label] = ttk.Label(left_frame, text="N/A")
            self.dashboard_labels[label].grid(row=i, column=1, sticky=tk.W, padx=5, pady=5)

        # Right column - Quick Stats
        right_frame = ttk.LabelFrame(cards_frame, text="This Month Summary", padding="15")
        right_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        self.stats_labels = {}
        stats = ['Total Spending', 'Total Income', 'Net Balance', 'Transactions']
        for i, stat in enumerate(stats):
            frame = ttk.Frame(right_frame)
            frame.grid(row=i//2, column=(i%2)*2, columnspan=2, padx=10, pady=10, sticky='w')
            ttk.Label(frame, text=f"{stat}:", font=('Arial', 9)).pack(side='left')
            self.stats_labels[stat] = ttk.Label(frame, text="\u00a30.00", font=('Arial', 11, 'bold'))
            self.stats_labels[stat].pack(side='left', padx=10)

        # Recent expenses
        expenses_frame = ttk.LabelFrame(tab, text="Recent Expenses (Last 7 Days)", padding="10")
        expenses_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.recent_expenses_tree = ttk.Treeview(expenses_frame,
            columns=('Date', 'Description', 'Amount'), show='headings', height=8)
        self.recent_expenses_tree.heading('Date', text='Date')
        self.recent_expenses_tree.heading('Description', text='Description')
        self.recent_expenses_tree.heading('Amount', text='Amount')
        self.recent_expenses_tree.column('Date', width=100)
        self.recent_expenses_tree.column('Description', width=300)
        self.recent_expenses_tree.column('Amount', width=100)
        self.recent_expenses_tree.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(tab, text="Refresh Dashboard", command=self.refresh_dashboard).pack(pady=10)

        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)

    def create_my_budgets_tab(self, notebook):
        """Create my budgets management tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="My Budgets")

        # Create budget frame
        create_frame = ttk.LabelFrame(tab, text="Create New Budget", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        fields_frame = ttk.Frame(create_frame)
        fields_frame.pack(fill=tk.X)

        ttk.Label(fields_frame, text="Budget Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.my_budget_name_entry = ttk.Entry(fields_frame, width=30)
        self.my_budget_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.my_budget_type_combo = ttk.Combobox(fields_frame,
            values=['monthly', 'weekly', 'semester', 'annual', 'custom'],
            state='readonly', width=15)
        self.my_budget_type_combo.current(0)
        self.my_budget_type_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields_frame, text="Total Budget (\u00a3):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.my_budget_amount_entry = ttk.Entry(fields_frame, width=30)
        self.my_budget_amount_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields_frame, text="Create Budget",
                  command=self.create_personal_budget).grid(row=1, column=3, padx=5, pady=5)

        # Budget list
        list_frame = ttk.LabelFrame(tab, text="My Budgets", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.my_budgets_tree = ttk.Treeview(list_frame,
            columns=('ID', 'Name', 'Type', 'Total', 'Spent', 'Remaining', 'Status'),
            show='headings', height=12)

        for col in self.my_budgets_tree['columns']:
            self.my_budgets_tree.heading(col, text=col)
            width = 60 if col == 'ID' else 100 if col in ('Type', 'Status') else 120
            self.my_budgets_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.my_budgets_tree.yview)
        self.my_budgets_tree.configure(yscrollcommand=scrollbar.set)

        self.my_budgets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="View Details", command=self.view_budget_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_my_budgets).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.root.after(100, self.refresh_my_budgets)

    def open_expense_tracker(self):
        """Switch to expenses tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(2)  # Expenses & Income tab

    def open_income_tracker(self):
        """Switch to income tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(2)  # Expenses & Income tab

    def open_savings_goals(self):
        """Switch to savings goals tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(3)  # Savings Goals tab

    def open_meal_plan(self):
        """Switch to meal plan tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(4)  # Meal Plan tab

    def open_textbooks(self):
        """Switch to textbooks tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(5)  # Textbooks tab

    def create_personal_budget(self):
        """Create a new personal budget"""
        try:
            name = self.my_budget_name_entry.get().strip()
            budget_type = self.my_budget_type_combo.get()
            amount = float(self.my_budget_amount_entry.get().strip())

            if not name or amount <= 0:
                messagebox.showerror("Error", "Please enter valid budget name and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import budget manager from budget tracker
            from education_system.systems.university.domain.finance.budget.services.budget_service import BudgetManager

            # Calculate dates based on budget type
            start_date = datetime.now().strftime('%Y-%m-%d')
            if budget_type == 'monthly':
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            elif budget_type == 'weekly':
                end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            elif budget_type == 'semester':
                end_date = (datetime.now() + timedelta(days=120)).strftime('%Y-%m-%d')
            elif budget_type == 'annual':
                end_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            else:
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            budget_id = BudgetManager.create_budget(
                student_id=student_id,
                budget_name=name,
                budget_type=budget_type,
                start_date=start_date,
                end_date=end_date,
                total_budget=amount
            )

            messagebox.showinfo("Success", f"Budget '{name}' created successfully!")
            self.my_budget_name_entry.delete(0, tk.END)
            self.my_budget_amount_entry.delete(0, tk.END)
            self.refresh_my_budgets()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create budget: {e}")

    def view_budget_details(self):
        """View details of selected budget"""
        selection = self.my_budgets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a budget to view.")
            return

        try:
            item = self.my_budgets_tree.item(selection[0])
            budget_id = item['values'][0]

            from education_system.systems.university.domain.finance.budget.services.budget_service import BudgetManager
            summary = BudgetManager.get_budget_summary(budget_id)

            # Create detail window
            window = tk.Toplevel(self.root)
            window.title(f"Budget Details: {summary['budget_name']}")
            window.geometry("600x500")

            text = ScrolledText(window, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            output = f"""
{'='*60}
BUDGET DETAILS: {summary['budget_name']}
{'='*60}

Type: {summary['budget_type'].capitalize()}
Period: {summary['start_date']} to {summary['end_date']}

Financial Summary:
  Total Budget:     \u00a3{summary['total_budget']:.2f}
  Spent:            \u00a3{summary['spent_amount']:.2f}
  Remaining:        \u00a3{summary['remaining_budget']:.2f}
  Utilization:      {summary['budget_utilization_pct']:.1f}%

Time Analysis:
  Total Days:       {summary['total_days']}
  Days Elapsed:     {summary['elapsed_days']}
  Days Remaining:   {summary['remaining_days']}
  Daily Budget:     \u00a3{summary['recommended_daily_spending']:.2f}
"""
            text.insert(tk.END, output)
            text.config(state=tk.DISABLED)

            ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load budget details: {e}")

    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import (
                BudgetManager, ExpenseManager, IncomeManager
            )

            # Load current budget
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets and len(budgets) > 0:
                budget = budgets[0]
                summary = BudgetManager.get_budget_summary(budget['budget_id'])

                self.dashboard_labels['Budget Name'].config(text=summary['budget_name'])
                self.dashboard_labels['Total Budget'].config(text=f"\u00a3{summary['total_budget']:.2f}")
                self.dashboard_labels['Spent'].config(text=f"\u00a3{summary['spent_amount']:.2f}")
                self.dashboard_labels['Remaining'].config(text=f"\u00a3{summary['remaining_budget']:.2f}")
                self.dashboard_labels['Utilization %'].config(text=f"{summary['budget_utilization_pct']:.1f}%")

            # Load recent expenses
            if hasattr(self, 'recent_expenses_tree'):
                self.recent_expenses_tree.delete(*self.recent_expenses_tree.get_children())
                expenses = ExpenseManager.get_student_expenses(student_id,
                    start_date=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
                for expense in expenses[:10]:
                    self.recent_expenses_tree.insert('', 'end', values=(
                        expense['expense_date'],
                        expense['description'][:40],
                        f"\u00a3{expense['amount']:.2f}"
                    ))

            # Quick stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            month_expenses = ExpenseManager.get_student_expenses(student_id, start_date=month_start)
            month_income = IncomeManager.get_student_income(student_id, start_date=month_start)

            total_expenses = sum(e['amount'] for e in month_expenses)
            total_income = sum(i['amount'] for i in month_income)
            net = total_income - total_expenses

            self.stats_labels['Total Spending'].config(text=f"\u00a3{total_expenses:.2f}")
            self.stats_labels['Total Income'].config(text=f"\u00a3{total_income:.2f}")
            self.stats_labels['Net Balance'].config(text=f"\u00a3{net:.2f}",
                foreground='green' if net >= 0 else 'red')
            self.stats_labels['Transactions'].config(text=str(len(month_expenses) + len(month_income)))

        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")

    def refresh_my_budgets(self):
        """Refresh my budgets list"""
        if not hasattr(self, 'my_budgets_tree'):
            return

        self.my_budgets_tree.delete(*self.my_budgets_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domain.finance.budget.services.budget_service import BudgetManager
            budgets = BudgetManager.get_student_budgets(student_id, active_only=False)

            for budget in budgets:
                remaining = budget['total_budget'] - budget['spent_amount']
                status = "Active" if budget['is_active'] else "Inactive"
                self.my_budgets_tree.insert('', 'end', values=(
                    budget['budget_id'],
                    budget['budget_name'],
                    budget['budget_type'],
                    f"\u00a3{budget['total_budget']:.2f}",
                    f"\u00a3{budget['spent_amount']:.2f}",
                    f"\u00a3{remaining:.2f}",
                    status
                ))
        except Exception as e:
            logger.error(f"Error loading budgets: {e}")
