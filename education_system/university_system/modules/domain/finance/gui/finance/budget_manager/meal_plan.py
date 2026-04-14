"""Meal plan tracking"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.domain.finance.gui.finance.budget_manager.constants import logger


class MealPlanMixin:
    """Meal plan tracking methods"""

    def create_meal_plan_tab(self, notebook):
        """Create meal plan tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Meal Plan")

        # Status frame
        status_frame = ttk.LabelFrame(tab, text="Current Meal Plan Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.meal_plan_labels = {}
        labels = ['Plan Name', 'Type', 'Meals Remaining', 'Dollars Remaining', 'Usage %', 'Days Remaining']
        for i, label in enumerate(labels):
            ttk.Label(status_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.meal_plan_labels[label] = ttk.Label(status_frame, text="N/A")
            self.meal_plan_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        ttk.Button(status_frame, text="Refresh Status",
                  command=self.load_meal_plan_status).grid(
            row=(len(labels)//2)+1, column=0, columnspan=4, pady=10)

        # Log transaction frame
        log_frame = ttk.LabelFrame(tab, text="Log Meal Transaction", padding="10")
        log_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(log_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Location:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_location_entry = ttk.Entry(fields, width=25)
        self.meal_location_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Meal Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_type_combo = ttk.Combobox(fields,
            values=['breakfast', 'lunch', 'dinner', 'snack'],
            state='readonly', width=15)
        self.meal_type_combo.current(1)
        self.meal_type_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Meals Used:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_swipes_entry = ttk.Entry(fields, width=10)
        self.meal_swipes_entry.insert(0, "1")
        self.meal_swipes_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Dollars Used:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_dollars_entry = ttk.Entry(fields, width=10)
        self.meal_dollars_entry.insert(0, "0.00")
        self.meal_dollars_entry.grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(fields, text="Log Transaction",
                  command=self.log_meal_transaction).grid(row=2, column=0, columnspan=4, pady=10)

        # Transaction history
        history_frame = ttk.LabelFrame(tab, text="Recent Meal Transactions", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True)

        self.meal_history_tree = ttk.Treeview(history_frame,
            columns=('Date', 'Time', 'Location', 'Type', 'Meals', 'Dollars'),
            show='headings', height=10)

        for col in self.meal_history_tree['columns']:
            self.meal_history_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Time', 'Type') else 80 if col in ('Meals', 'Dollars') else 150
            self.meal_history_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL,
                                 command=self.meal_history_tree.yview)
        self.meal_history_tree.configure(yscrollcommand=scrollbar.set)

        self.meal_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def log_meal_transaction(self):
        """Log a meal plan transaction"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Get active meal plan
            with get_connection() as conn:
                tracking = conn.execute('''
                    SELECT * FROM meal_plan_tracking
                    WHERE student_id = ? AND is_active = 1
                    ORDER BY start_date DESC LIMIT 1
                ''', (student_id,)).fetchone()

            if not tracking:
                messagebox.showerror("Error", "No active meal plan found.")
                return

            location = self.meal_location_entry.get().strip()
            meal_type = self.meal_type_combo.get()
            meals_used = int(self.meal_swipes_entry.get().strip())
            dollars_used = float(self.meal_dollars_entry.get().strip())

            if not location:
                messagebox.showerror("Error", "Location is required.")
                return

            from education_system.university_system.modules.domain.finance.budget.services.budget_service import MealPlanManager
            transaction_id = MealPlanManager.log_meal_transaction(
                tracking_id=tracking['tracking_id'],
                student_id=student_id,
                transaction_date=datetime.now().strftime('%Y-%m-%d'),
                transaction_time=datetime.now().strftime('%H:%M'),
                location=location,
                meal_type=meal_type,
                meals_used=meals_used,
                dollars_used=dollars_used
            )

            messagebox.showinfo("Success", f"Meal transaction logged!")
            self.meal_location_entry.delete(0, tk.END)
            self.meal_swipes_entry.delete(0, tk.END)
            self.meal_swipes_entry.insert(0, "1")
            self.meal_dollars_entry.delete(0, tk.END)
            self.meal_dollars_entry.insert(0, "0.00")
            self.load_meal_plan_status()

        except ValueError:
            messagebox.showerror("Error", "Invalid values.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to log meal transaction: {e}")

    def load_meal_plan_status(self):
        """Load meal plan status"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.university_system.modules.domain.finance.budget.services.budget_service import MealPlanManager
            status = MealPlanManager.get_meal_plan_status(student_id, active_only=True)

            if status:
                self.meal_plan_labels['Plan Name'].config(text=status['plan_name'])
                self.meal_plan_labels['Type'].config(text=status['plan_type'])
                self.meal_plan_labels['Meals Remaining'].config(
                    text=str(status.get('remaining_meals', 'N/A')))
                self.meal_plan_labels['Dollars Remaining'].config(
                    text=f"\u00a3{status.get('remaining_dollars', 0):.2f}")
                self.meal_plan_labels['Usage %'].config(
                    text=f"{max(status.get('meals_used_pct', 0), status.get('dollars_used_pct', 0)):.1f}%")
                self.meal_plan_labels['Days Remaining'].config(
                    text=str(status.get('days_remaining', 'N/A')))

                # Load recent transactions
                self.meal_history_tree.delete(*self.meal_history_tree.get_children())
                history = MealPlanManager.get_meal_history(student_id, days=14)
                for txn in history:
                    self.meal_history_tree.insert('', 'end', values=(
                        txn['transaction_date'],
                        txn['transaction_time'],
                        txn['location'],
                        txn['meal_type'],
                        txn['meals_used'],
                        f"\u00a3{txn['dollars_used']:.2f}"
                    ))
        except Exception as e:
            logger.error(f"Error loading meal plan status: {e}")
