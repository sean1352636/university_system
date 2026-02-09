"""
Staff HR Management GUI

Main launcher that integrates all staff HR features:
- Leave Management
- Time & Attendance
- Training & Certifications
- Performance Appraisals
- Onboarding & Offboarding
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.database.schemas.staff_hr_schemas import init_staff_hr_schemas
from university_system.modules.shared.utils.activity_logger import log_activity

from university_system.modules.domain.staff_hr.gui.leave_management_gui import LeaveManagementGUI
from university_system.modules.domain.staff_hr.gui.time_attendance_gui import TimeAttendanceGUI
from university_system.modules.domain.staff_hr.gui.training_gui import TrainingGUI
from university_system.modules.domain.staff_hr.gui.appraisal_gui import AppraisalGUI
from university_system.modules.domain.staff_hr.gui.onboarding_gui import OnboardingGUI
from university_system.modules.domain.staff_hr.gui.contract_gui import ContractGUI
from university_system.modules.domain.staff_hr.gui.expense_gui import ExpenseGUI
from university_system.modules.domain.staff_hr.gui.grievance_gui import GrievanceGUI
from university_system.modules.domain.staff_hr.gui.exit_gui import ExitGUI

# Import i18n for internationalization
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
)


class StaffHRGUI:
    """Main GUI launcher for Staff HR Management System."""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.window = None

        if not self.current_user:
            messagebox.showerror(_t("common.error"), _t("staff_hr.errors.login_required"))
            return

        # Initialize database schemas
        try:
            init_staff_hr_schemas()
        except Exception as e:
            print(f"Warning: Could not initialize Staff HR schemas: {e}")

        self.create_main_window()

    def create_main_window(self):
        """Create the main Staff HR window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t("staff_hr.window_title"))
        self.window.geometry("1300x800")
        self.window.minsize(1100, 700)

        # Configure styles
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Subheader.TLabel', font=('Arial', 12))

        # Bottom frame with close button
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t("staff_hr.close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = ttk.Label(self.window, text=_t("staff_hr.ready") + " - " + _t("staff_hr.version"),
                                    relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Header frame
        header_frame = ttk.Frame(self.window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.title"), style='Header.TLabel').pack(side=tk.LEFT)

        user_info = f"User: {self.current_user.get('username', 'Unknown')} | Role: {self.current_user.get('role', 'Unknown').capitalize()}"
        ttk.Label(header_frame, text=user_info, style='Subheader.TLabel').pack(side=tk.RIGHT)

        # Main notebook with all features
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create feature tabs
        self._create_dashboard_tab()
        self._load_leave_management()
        self._load_time_attendance()
        self._load_training()
        self._load_appraisals()
        self._load_onboarding()
        self._load_contracts()
        self._load_expenses()
        self._load_grievances()

        # Admin-only tabs
        if self.current_user.get('role') in ('admin', 'Admin', 'administrator'):
            self._load_exit_management()

        # Log activity
        log_activity('view', 'staff_hr_gui',
                     user_id=self.current_user.get('id') or self.current_user.get('username'),
                     details={'action': 'opened_staff_hr_gui'})

    def _create_dashboard_tab(self):
        """Create the dashboard overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.tabs.dashboard"))

        # Welcome message
        welcome_frame = ttk.Frame(tab)
        welcome_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(welcome_frame, text=_t("staff_hr.dashboard.welcome", username=self.current_user.get('username', 'User')),
                  font=('Arial', 18, 'bold')).pack(anchor=tk.W)
        ttk.Label(welcome_frame, text=_t("staff_hr.dashboard.welcome_message"),
                  font=('Arial', 11)).pack(anchor=tk.W, pady=5)

        # Quick stats frame
        stats_frame = ttk.LabelFrame(tab, text=_t("staff_hr.dashboard.quick_overview"), padding=15)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)

        # Create stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        self._create_stat_card(stats_grid, _t("staff_hr.dashboard.stats.leave_balance"), self._get_leave_balance(), 0, 0)
        self._create_stat_card(stats_grid, _t("staff_hr.dashboard.stats.pending_requests"), self._get_pending_requests(), 0, 1)
        self._create_stat_card(stats_grid, _t("staff_hr.dashboard.stats.training_due"), self._get_training_due(), 0, 2)
        self._create_stat_card(stats_grid, _t("staff_hr.dashboard.stats.goals_progress"), self._get_goals_progress(), 0, 3)

        # Quick actions frame
        actions_frame = ttk.LabelFrame(tab, text=_t("staff_hr.dashboard.quick_actions"), padding=15)
        actions_frame.pack(fill=tk.X, padx=20, pady=10)

        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack()

        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.request_leave"), width=18,
                   command=lambda: self.notebook.select(1)).grid(row=0, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.clock_in_out"), width=18,
                   command=lambda: self.notebook.select(2)).grid(row=0, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.view_training"), width=18,
                   command=lambda: self.notebook.select(3)).grid(row=0, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.my_goals"), width=18,
                   command=lambda: self.notebook.select(4)).grid(row=0, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.my_contract"), width=18,
                   command=lambda: self.notebook.select(6)).grid(row=1, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.submit_expense"), width=18,
                   command=lambda: self.notebook.select(7)).grid(row=1, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.file_grievance"), width=18,
                   command=lambda: self.notebook.select(8)).grid(row=1, column=2, padx=8, pady=5)

        # Notifications frame
        notif_frame = ttk.LabelFrame(tab, text=_t("staff_hr.dashboard.notifications"), padding=15)
        notif_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        notifications = self._get_notifications()
        if notifications:
            for notif in notifications[:5]:
                notif_row = ttk.Frame(notif_frame)
                notif_row.pack(fill=tk.X, pady=2)
                ttk.Label(notif_row, text=notif['icon'], font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
                ttk.Label(notif_row, text=notif['message'], wraplength=800).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Label(notif_frame, text=_t("staff_hr.dashboard.no_notifications"), foreground='gray').pack(pady=20)

    def _create_stat_card(self, parent, title, value, row, col):
        """Create a statistics card."""
        card = ttk.Frame(parent, relief=tk.RIDGE, borderwidth=1, padding=15)
        card.grid(row=row, column=col, padx=10, pady=5, sticky='nsew')

        ttk.Label(card, text=title, font=('Arial', 10)).pack()
        ttk.Label(card, text=str(value), font=('Arial', 18, 'bold')).pack(pady=5)

    def _load_tab_safe(self, gui_class, tab_name: str):
        """Safely load a GUI tab, avoiding duplicates on error."""
        tab_count_before = len(self.notebook.tabs())
        try:
            gui_class(self.root, self.auth, self.notebook)
        except Exception as e:
            # Only add error tab if the GUI didn't already add one
            if len(self.notebook.tabs()) == tab_count_before:
                tab = ttk.Frame(self.notebook)
                self.notebook.add(tab, text=tab_name)
                ttk.Label(tab, text=_t("staff_hr.errors.error_loading", module=tab_name, error=str(e))).pack(pady=20)

    def _load_leave_management(self):
        """Load leave management as a tab."""
        self._load_tab_safe(LeaveManagementGUI, _t("staff_hr.tabs.leave_management"))

    def _load_time_attendance(self):
        """Load time & attendance as a tab."""
        self._load_tab_safe(TimeAttendanceGUI, _t("staff_hr.tabs.time_attendance"))

    def _load_training(self):
        """Load training & certifications as a tab."""
        self._load_tab_safe(TrainingGUI, _t("staff_hr.tabs.training"))

    def _load_appraisals(self):
        """Load performance appraisals as a tab."""
        self._load_tab_safe(AppraisalGUI, _t("staff_hr.tabs.appraisals"))

    def _load_onboarding(self):
        """Load onboarding as a tab."""
        self._load_tab_safe(OnboardingGUI, _t("staff_hr.tabs.onboarding"))

    def _load_contracts(self):
        """Load contract management as a tab."""
        self._load_tab_safe(ContractGUI, _t("staff_hr.tabs.contracts"))

    def _load_expenses(self):
        """Load expense claims as a tab."""
        self._load_tab_safe(ExpenseGUI, _t("staff_hr.tabs.expenses"))

    def _load_grievances(self):
        """Load grievance management as a tab."""
        self._load_tab_safe(GrievanceGUI, _t("staff_hr.tabs.grievances"))

    def _load_exit_management(self):
        """Load exit management as a tab (admin only)."""
        self._load_tab_safe(ExitGUI, _t("staff_hr.tabs.exit_management"))

    def _get_leave_balance(self) -> str:
        """Get user's remaining leave balance."""
        try:
            user_id = self.current_user.get('id') or self.current_user.get('username')
            year = 2026  # Current year

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT SUM(COALESCE(b.allocated_days, t.max_days_per_year) - COALESCE(b.used_days, 0))
                    FROM leave_types t
                    LEFT JOIN leave_balances b ON t.leave_type_id = b.leave_type_id
                        AND b.user_id = ? AND b.year = ?
                    WHERE t.is_active = 1
                ''', (user_id, year))
                result = cursor.fetchone()[0]
                return f"{result:.0f} " + _t("staff_hr.dashboard.values.days") if result else _t("staff_hr.dashboard.values.na")
        except Exception:
            return _t("staff_hr.dashboard.values.na")

    def _get_pending_requests(self) -> int:
        """Get count of pending leave requests."""
        try:
            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM leave_requests
                    WHERE user_id = ? AND status = 'pending'
                ''', (user_id,))
                return cursor.fetchone()[0]
        except Exception:
            return 0

    def _get_training_due(self) -> int:
        """Get count of training courses due."""
        try:
            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM training_enrollments
                    WHERE user_id = ? AND status IN ('enrolled', 'in_progress')
                ''', (user_id,))
                return cursor.fetchone()[0]
        except Exception:
            return 0

    def _get_goals_progress(self) -> str:
        """Get average goals progress."""
        try:
            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT AVG(progress) FROM appraisal_goals
                    WHERE user_id = ? AND status = 'active'
                ''', (user_id,))
                result = cursor.fetchone()[0]
                return f"{result:.0f}%" if result else "0%"
        except Exception:
            return "0%"

    def _get_notifications(self) -> list:
        """Get user notifications and reminders."""
        notifications = []
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check for pending leave requests
                cursor.execute('''
                    SELECT COUNT(*) FROM leave_requests
                    WHERE user_id = ? AND status = 'pending'
                ''', (user_id,))
                pending = cursor.fetchone()[0]
                if pending > 0:
                    notifications.append({
                        'icon': '\u23f3',
                        'message': f"You have {pending} pending leave request(s) awaiting approval"
                    })

                # Check for overdue training
                cursor.execute('''
                    SELECT COUNT(*) FROM training_enrollments
                    WHERE user_id = ? AND status IN ('enrolled', 'in_progress')
                    AND due_date < date('now')
                ''', (user_id,))
                overdue = cursor.fetchone()[0]
                if overdue > 0:
                    notifications.append({
                        'icon': '\u26a0',
                        'message': f"You have {overdue} overdue training course(s)"
                    })

                # Check for expiring certifications
                cursor.execute('''
                    SELECT COUNT(*) FROM certifications
                    WHERE user_id = ? AND status = 'active'
                    AND expiry_date BETWEEN date('now') AND date('now', '+30 days')
                ''', (user_id,))
                expiring = cursor.fetchone()[0]
                if expiring > 0:
                    notifications.append({
                        'icon': '\u26a0',
                        'message': f"You have {expiring} certification(s) expiring within 30 days"
                    })

                # Check for active appraisal cycle
                cursor.execute('''
                    SELECT c.name FROM appraisal_cycles c
                    LEFT JOIN appraisal_records r ON c.cycle_id = r.cycle_id AND r.user_id = ?
                    WHERE c.status = 'active' AND (r.status IS NULL OR r.status = 'pending')
                ''', (user_id,))
                cycle = cursor.fetchone()
                if cycle:
                    notifications.append({
                        'icon': '\u2705',
                        'message': f"Self-review pending for appraisal cycle: {cycle[0]}"
                    })

                # Check for onboarding tasks
                cursor.execute('''
                    SELECT COUNT(*) FROM onboarding_task_progress p
                    JOIN onboarding_assignments a ON p.assignment_id = a.assignment_id
                    WHERE a.user_id = ? AND p.status = 'pending'
                ''', (user_id,))
                tasks = cursor.fetchone()[0]
                if tasks > 0:
                    notifications.append({
                        'icon': '\u2611',
                        'message': f"You have {tasks} onboarding task(s) to complete"
                    })

        except Exception:
            pass

        if not notifications:
            notifications.append({
                'icon': '\u2713',
                'message': "All caught up! No pending items."
            })

        return notifications


def launch_staff_hr_gui(root, auth):
    """Launch Staff HR Management GUI."""
    try:
        return StaffHRGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Staff HR GUI: {e}")
        return None
