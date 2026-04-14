"""Savings goals tracking"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.modules.domain.finance.gui.finance.budget_manager.constants import logger


class SavingsGoalsMixin:
    """Savings goals management methods"""

    def create_savings_goals_tab(self, notebook):
        """Create savings goals tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Savings Goals")

        # Create goal frame
        create_frame = ttk.LabelFrame(tab, text="Create New Savings Goal", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(create_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Goal Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_name_entry = ttk.Entry(fields, width=30)
        self.goal_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Target Amount (\u00a3):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.goal_amount_entry = ttk.Entry(fields, width=15)
        self.goal_amount_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Priority:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_priority_combo = ttk.Combobox(fields,
            values=['Low', 'Medium', 'High'], state='readonly', width=28)
        self.goal_priority_combo.current(1)
        self.goal_priority_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields, text="Create Goal", command=self.create_savings_goal).grid(
            row=1, column=3, padx=5, pady=5)

        # Goals list
        list_frame = ttk.LabelFrame(tab, text="My Savings Goals", padding="10")
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
        ttk.Button(btn_frame, text="Add Funds", command=self.update_goal_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_savings_goals).pack(side=tk.LEFT, padx=5)

    def create_savings_goal(self):
        """Create a new savings goal"""
        try:
            name = self.goal_name_entry.get().strip()
            amount = float(self.goal_amount_entry.get().strip())
            priority = self.goal_priority_combo.get().lower()

            if not name or amount <= 0:
                messagebox.showerror("Error", "Please enter valid goal name and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import savings goal manager
            from education_system.university_system.modules.domain.finance.budget.services.budget_service import SavingsGoalManager

            goal_id = SavingsGoalManager.create_goal(
                student_id=student_id,
                goal_name=name,
                target_amount=amount,
                target_date=None,
                priority=priority
            )

            messagebox.showinfo("Success", f"Savings goal '{name}' created successfully!")
            self.goal_name_entry.delete(0, tk.END)
            self.goal_amount_entry.delete(0, tk.END)
            self.refresh_savings_goals()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create savings goal: {e}")

    def update_goal_progress(self):
        """Update progress on selected savings goal"""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a goal.")
            return

        try:
            item = self.goals_tree.item(selection[0])
            goal_id = item['values'][0]

            amount = simpledialog.askfloat("Add Funds", "Amount to add (\u00a3):", minvalue=0.01, parent=self.root)
            if amount:
                from education_system.university_system.modules.domain.finance.budget.services.budget_service import SavingsGoalManager
                SavingsGoalManager.update_goal_progress(goal_id, amount)
                messagebox.showinfo("Success", f"Added \u00a3{amount:.2f} to goal!")
                self.refresh_savings_goals()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update goal: {e}")

    def refresh_savings_goals(self):
        """Refresh savings goals list"""
        if not hasattr(self, 'goals_tree'):
            return

        self.goals_tree.delete(*self.goals_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.finance.budget.services.budget_service import SavingsGoalManager
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=False)

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
