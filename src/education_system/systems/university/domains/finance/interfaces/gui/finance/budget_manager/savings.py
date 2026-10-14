"""Savings goals tracking"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.systems.university.domains.finance.interfaces.gui.finance.budget_manager.constants import logger


class SavingsGoalsMixin:
    """Savings goals management methods"""

    def create_savings_goals_tab(self, notebook):
        """Create savings goals tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text=_t('gui.finance.finance.budget_manager.savings.tabs.savings_goals', default="Savings Goals"))

        # Create goal frame
        create_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.savings.labels.create_new_savings_goal', default="Create New Savings Goal"), padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(create_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.goal_name', default="Goal Name:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_name_entry = ttk.Entry(fields, width=30)
        self.goal_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.target_amount', default="Target Amount (\u00a3):")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.goal_amount_entry = ttk.Entry(fields, width=15)
        self.goal_amount_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.priority', default="Priority:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_priority_combo = ttk.Combobox(fields,
            values=['Low', 'Medium', 'High'], state='readonly', width=28)
        self.goal_priority_combo.current(1)
        self.goal_priority_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.target_date', default="Target Date (YYYY-MM-DD):")).grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.goal_date_entry = ttk.Entry(fields, width=15)
        self.goal_date_entry.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.category', default="Category:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_category_entry = ttk.Entry(fields, width=30)
        self.goal_category_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.savings.labels.description', default="Description:")).grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.goal_description_entry = ttk.Entry(fields, width=30)
        self.goal_description_entry.grid(row=2, column=3, padx=5, pady=5)

        ttk.Button(fields, text=_t('gui.finance.finance.budget_manager.savings.buttons.create_goal', default="Create Goal"), command=self.create_savings_goal).grid(
            row=3, column=3, padx=5, pady=5, sticky=tk.E)

        # Goals list
        list_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.savings.labels.my_savings_goals', default="My Savings Goals"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.goals_tree = ttk.Treeview(list_frame,
            columns=('ID', 'Goal', 'Target', 'Saved', 'Remaining', 'Progress %', 'Priority'),
            show='headings', height=12)

        for col in self.goals_tree['columns']:
            self.goals_tree.heading(col, text=col)
            width = 50 if col == 'ID' else 80 if col in ('Priority', 'Progress %') else 100 if col in ('Target', 'Saved', 'Remaining') else 200
            self.goals_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.goals_tree.yview)
        self.goals_tree.configure(yscrollcommand=scrollbar.set)

        self.goals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text=_t('gui.finance.finance.budget_manager.savings.buttons.add_funds', default="Add Funds"), command=self.update_goal_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.finance.finance.budget_manager.savings.buttons.refresh', default="Refresh"), command=self.refresh_savings_goals).pack(side=tk.LEFT, padx=5)
        self.goals_show_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_frame, text=_t('gui.finance.finance.budget_manager.savings.labels.show_completed', default="Include completed/inactive goals"),
                        variable=self.goals_show_all_var, command=self.refresh_savings_goals).pack(side=tk.LEFT, padx=10)

    def create_savings_goal(self):
        """Create a new savings goal"""
        try:
            name = self.goal_name_entry.get().strip()
            amount = float(self.goal_amount_entry.get().strip())
            priority = self.goal_priority_combo.get().lower()

            if not name or amount <= 0:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.savings.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.savings.dialogs.please_enter_valid_goal_name_and_amount', default="Please enter valid goal name and amount."))
                return
            target_date = self.goal_date_entry.get().strip() or None
            if target_date:
                datetime.strptime(target_date, '%Y-%m-%d')

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import savings goal manager
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import SavingsGoalManager

            goal_id = SavingsGoalManager.create_goal(
                student_id=student_id,
                goal_name=name,
                target_amount=amount,
                target_date=target_date,
                priority=priority,
                category=self.goal_category_entry.get().strip(),
                description=self.goal_description_entry.get().strip(),
            )

            messagebox.showinfo(_t('gui.finance.finance.budget_manager.savings.dialogs.success', default="Success"), f"Savings goal '{name}' created successfully!")
            for entry in (self.goal_name_entry, self.goal_amount_entry, self.goal_date_entry,
                          self.goal_category_entry, self.goal_description_entry):
                entry.delete(0, tk.END)
            self.refresh_savings_goals()

        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.savings.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.savings.dialogs.invalid_amount_or_date', default="Amount must be a number and the target date YYYY-MM-DD."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.savings.dialogs.error', default="Error"), f"Failed to create savings goal: {e}")

    def update_goal_progress(self):
        """Update progress on selected savings goal"""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.finance.finance.budget_manager.savings.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.savings.dialogs.please_select_a_goal', default="Please select a goal."))
            return

        try:
            item = self.goals_tree.item(selection[0])
            goal_id = item['values'][0]

            amount = simpledialog.askfloat(_t('gui.finance.finance.budget_manager.savings.dialogs.add_funds', default="Add Funds"), _t('gui.finance.finance.budget_manager.savings.dialogs.amount_to_add', default="Amount to add (\u00a3):"), minvalue=0.01, parent=self.root)
            if amount:
                from education_system.systems.university.domains.finance.domain.budget.services.budget_service import SavingsGoalManager
                SavingsGoalManager.update_goal_progress(goal_id, amount)
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.savings.dialogs.success', default="Success"), f"Added \u00a3{amount:.2f} to goal!")
                self.refresh_savings_goals()
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.savings.dialogs.error', default="Error"), f"Failed to update goal: {e}")

    def refresh_savings_goals(self):
        """Refresh savings goals list"""
        if not hasattr(self, 'goals_tree'):
            return

        self.goals_tree.delete(*self.goals_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import SavingsGoalManager
            show_all = getattr(self, 'goals_show_all_var', None)
            active_only = not (show_all.get() if show_all is not None else True)
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=active_only)

            for goal in goals:
                self.goals_tree.insert('', 'end', values=(
                    goal['goal_id'],
                    goal['goal_name'],
                    f"\u00a3{goal['target_amount']:.2f}",
                    f"\u00a3{goal['current_amount']:.2f}",
                    f"\u00a3{goal['remaining_amount']:.2f}",
                    f"{goal['progress_pct']:.1f}%",
                    goal['priority'].capitalize()
                ))
        except Exception as e:
            logger.error(f"Error loading savings goals: {e}")
