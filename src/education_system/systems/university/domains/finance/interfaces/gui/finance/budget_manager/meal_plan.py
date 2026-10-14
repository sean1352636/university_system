"""Meal plan tracking"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.finance.interfaces.gui.finance.budget_manager.constants import logger

MEAL_PLAN_TYPES = ['unlimited', 'block', 'declining-balance', 'hybrid']


class MealPlanMixin:
    """Meal plan tracking methods"""

    def create_meal_plan_tab(self, notebook):
        """Create meal plan tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text=_t('gui.finance.finance.budget_manager.meal_plan.tabs.meal_plan', default="Meal Plan"))

        # Status frame
        status_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.current_meal_plan_status', default="Current Meal Plan Status"), padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.meal_plan_labels = {}
        labels = ['Plan Name', 'Type', 'Meals Remaining', 'Dollars Remaining', 'Usage %', 'Days Remaining']
        for i, label in enumerate(labels):
            ttk.Label(status_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.meal_plan_labels[label] = ttk.Label(status_frame, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.n_a', default="N/A"))
            self.meal_plan_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        status_buttons = ttk.Frame(status_frame)
        status_buttons.grid(row=(len(labels)//2)+1, column=0, columnspan=4, pady=10)
        ttk.Button(status_buttons, text=_t('gui.finance.finance.budget_manager.meal_plan.buttons.refresh_status', default="Refresh Status"),
                  command=self.load_meal_plan_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(status_buttons, text=_t('gui.finance.finance.budget_manager.meal_plan.buttons.setup_meal_plan', default="Setup Meal Plan"),
                  command=self.setup_meal_plan).pack(side=tk.LEFT, padx=5)

        # Log transaction frame
        log_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.log_meal_transaction', default="Log Meal Transaction"), padding="10")
        log_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(log_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.location', default="Location:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_location_entry = ttk.Entry(fields, width=25)
        self.meal_location_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.meal_type', default="Meal Type:")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_type_combo = ttk.Combobox(fields,
            values=['breakfast', 'lunch', 'dinner', 'snack'],
            state='readonly', width=15)
        self.meal_type_combo.current(1)
        self.meal_type_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.meals_used', default="Meals Used:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_swipes_entry = ttk.Entry(fields, width=10)
        self.meal_swipes_entry.insert(0, "1")
        self.meal_swipes_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.dollars_used', default="Dollars Used:")).grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_dollars_entry = ttk.Entry(fields, width=10)
        self.meal_dollars_entry.insert(0, "0.00")
        self.meal_dollars_entry.grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(fields, text=_t('gui.finance.finance.budget_manager.meal_plan.buttons.log_transaction', default="Log Transaction"),
                  command=self.log_meal_transaction).grid(row=2, column=0, columnspan=4, pady=10)

        # Transaction history
        history_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.recent_meal_transactions', default="Recent Meal Transactions"), padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True)

        history_bar = ttk.Frame(history_frame)
        history_bar.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(history_bar, text=_t('gui.finance.finance.budget_manager.meal_plan.labels.history_days', default="Show last (days):")).pack(side=tk.LEFT, padx=5)
        self.meal_history_days_entry = ttk.Entry(history_bar, width=6)
        self.meal_history_days_entry.insert(0, "14")
        self.meal_history_days_entry.pack(side=tk.LEFT)
        ttk.Button(history_bar, text=_t('gui.finance.finance.budget_manager.meal_plan.buttons.load_history', default="Load History"),
                  command=self.load_meal_history).pack(side=tk.LEFT, padx=5)

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

    def _meal_student_id(self):
        current_user = self.gui.auth.get_current_user() if self.gui.auth else None
        return current_user.get('username') if current_user else 'guest'

    def setup_meal_plan(self):
        """Create meal plan tracking (CLI: Setup Meal Plan Tracking)."""
        today = datetime.now().strftime('%Y-%m-%d')
        values = ask_form(self.root, _t('gui.finance.finance.budget_manager.meal_plan.windows.setup_meal_plan', default="Setup Meal Plan Tracking"), [
            Field('plan_name', 'Plan name'),
            Field('plan_type', 'Plan type', kind='choice', options=MEAL_PLAN_TYPES, default='block'),
            Field('academic_term', 'Academic term', optional=True),
            Field('start_date', 'Start date (YYYY-MM-DD)', default=today),
            Field('end_date', 'End date (YYYY-MM-DD)'),
            Field('total_meals', 'Total meals (0 if unlimited)', kind='int', default='0', optional=True),
            Field('total_dollars', 'Total dollars', kind='float', default='0', optional=True),
        ])
        if values is None:
            return
        try:
            for key in ('start_date', 'end_date'):
                datetime.strptime(values[key], '%Y-%m-%d')
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import MealPlanManager
            tracking_id = MealPlanManager.create_meal_plan_tracking(
                student_id=self._meal_student_id(),
                plan_name=values['plan_name'],
                plan_type=values['plan_type'],
                academic_term=values.get('academic_term') or '',
                start_date=values['start_date'],
                end_date=values['end_date'],
                total_meals=values.get('total_meals') or 0,
                total_dollars=values.get('total_dollars') or 0.0,
            )
            messagebox.showinfo(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.success', default="Success"),
                                f"Meal plan tracking created (ID {tracking_id}).")
            self.load_meal_plan_status()
        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"),
                                 _t('gui.finance.finance.budget_manager.meal_plan.dialogs.dates_format', default="Dates must be YYYY-MM-DD."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"), f"Failed to set up meal plan: {e}")

    def load_meal_history(self):
        """Load meal transactions for the last N days (CLI: View Meal History)."""
        try:
            days = int(self.meal_history_days_entry.get().strip() or 14)
        except (ValueError, AttributeError):
            days = 14
        try:
            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import MealPlanManager
            history = MealPlanManager.get_meal_history(self._meal_student_id(), days=days)
            self.meal_history_tree.delete(*self.meal_history_tree.get_children())
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
            logger.error(f"Error loading meal history: {e}")

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
                messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.meal_plan.dialogs.no_active_meal_plan_found', default="No active meal plan found."))
                return

            location = self.meal_location_entry.get().strip()
            meal_type = self.meal_type_combo.get()
            meals_used = int(self.meal_swipes_entry.get().strip())
            dollars_used = float(self.meal_dollars_entry.get().strip())

            if not location:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.meal_plan.dialogs.location_is_required', default="Location is required."))
                return

            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import MealPlanManager
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

            messagebox.showinfo(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.meal_plan.dialogs.meal_transaction_logged', default="Meal transaction logged!"))
            self.meal_location_entry.delete(0, tk.END)
            self.meal_swipes_entry.delete(0, tk.END)
            self.meal_swipes_entry.insert(0, "1")
            self.meal_dollars_entry.delete(0, tk.END)
            self.meal_dollars_entry.insert(0, "0.00")
            self.load_meal_plan_status()

        except ValueError:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.meal_plan.dialogs.invalid_values', default="Invalid values."))
        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.meal_plan.dialogs.error', default="Error"), f"Failed to log meal transaction: {e}")

    def load_meal_plan_status(self):
        """Load meal plan status"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import MealPlanManager
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

            else:
                for label in self.meal_plan_labels.values():
                    label.config(text=_t('gui.finance.finance.budget_manager.meal_plan.labels.n_a', default="N/A"))
            self.load_meal_history()
        except Exception as e:
            logger.error(f"Error loading meal plan status: {e}")
