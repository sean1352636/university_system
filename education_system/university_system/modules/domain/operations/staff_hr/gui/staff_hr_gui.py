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

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.schemas.staff_hr_schemas_all import init_staff_hr_schemas
from education_system.university_system.core.activity_logger import log_activity

# Sub-feature GUIs are imported lazily inside each `_load_*` method below.
# The 25 sibling modules together add ~11s to import of this file when loaded
# eagerly; paying each import on demand keeps Staff HR launch under a second.

# Import i18n for internationalization
from education_system.university_system.core.i18n import (
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
        self.window.geometry("1400x900+%d+%d" % ((self.window.winfo_screenwidth() - 1400) // 2, (self.window.winfo_screenheight() - 900) // 2))
        self.window.minsize(1200, 800)

        # Configure styles
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Subheader.TLabel', font=('Arial', 12))
        style.configure('Sidebar.TButton', font=('Arial', 11), anchor='w', padding=(12, 8))
        style.configure('SidebarActive.TButton', font=('Arial', 11, 'bold'), anchor='w', padding=(12, 8))

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

        # Main content area: sidebar + content
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # --- Scrollable sidebar ---
        sidebar_outer = ttk.Frame(main_frame, width=220)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        sidebar_outer.pack_propagate(False)

        sidebar_canvas = tk.Canvas(sidebar_outer, width=210, highlightthickness=0)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_outer, orient=tk.VERTICAL, command=sidebar_canvas.yview)
        self.sidebar_frame = ttk.Frame(sidebar_canvas)

        self.sidebar_frame.bind(
            '<Configure>',
            lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox('all'))
        )
        sidebar_canvas.create_window((0, 0), window=self.sidebar_frame, anchor='nw', width=210)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling on the sidebar
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def _on_mousewheel_linux(event):
            if event.num == 4:
                sidebar_canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                sidebar_canvas.yview_scroll(1, 'units')

        sidebar_canvas.bind('<MouseWheel>', _on_mousewheel)
        sidebar_canvas.bind('<Button-4>', _on_mousewheel_linux)
        sidebar_canvas.bind('<Button-5>', _on_mousewheel_linux)
        self.sidebar_frame.bind('<MouseWheel>', _on_mousewheel)
        self.sidebar_frame.bind('<Button-4>', _on_mousewheel_linux)
        self.sidebar_frame.bind('<Button-5>', _on_mousewheel_linux)

        # --- Content area with hidden notebook ---
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        # Hide the notebook tab bar by using a style that removes it
        style.layout('TNotebook.Tab', [])

        # Track sidebar buttons for highlighting
        self.sidebar_buttons = []
        self._tab_index = 0

        # Create feature sections
        self._create_dashboard_tab()
        self._load_leave_management()
        self._load_time_attendance()
        self._load_training()
        self._load_appraisals()
        self._load_onboarding()
        self._load_contracts()
        self._load_expenses()
        self._load_grievances()
        self._load_payroll()
        self._load_faculty_schedule()
        self._load_curriculum()
        self._load_travel()
        self._load_sabbatical()
        self._load_committees()
        self._load_ip()
        self._load_equipment()
        self._load_cover()
        self._load_workload()
        self._load_directory()
        self._load_mentoring()
        self._load_grant_budget()
        self._load_peer_review()
        self._load_comm_hub()
        self._load_teaching_load()

        # Admin-only tabs
        if self.current_user.get('role') in ('admin', 'Admin', 'administrator'):
            self._load_exit_management()

        # Select the first sidebar button by default
        if self.sidebar_buttons:
            self._select_sidebar(0)

        # Log activity
        log_activity('view', 'staff_hr_gui',
                     user_id=self.current_user.get('id') or self.current_user.get('username'),
                     details={'action': 'opened_staff_hr_gui'})

    def _add_sidebar_button(self, text: str):
        """Add a button to the sidebar for the current tab index."""
        index = self._tab_index
        btn = ttk.Button(
            self.sidebar_frame,
            text=text,
            style='Sidebar.TButton',
            command=lambda idx=index: self._select_sidebar(idx),
        )
        btn.pack(fill=tk.X, pady=1)
        # Bind mousewheel on each button so scrolling works over buttons too
        btn.bind('<MouseWheel>', lambda e: self.sidebar_frame.master.event_generate('<MouseWheel>', delta=e.delta))
        btn.bind('<Button-4>', lambda e: self.sidebar_frame.master.event_generate('<Button-4>'))
        btn.bind('<Button-5>', lambda e: self.sidebar_frame.master.event_generate('<Button-5>'))
        self.sidebar_buttons.append(btn)
        self._tab_index += 1

    def _select_sidebar(self, index: int):
        """Select a section from the sidebar."""
        # Update button styles
        for i, btn in enumerate(self.sidebar_buttons):
            btn.configure(style='SidebarActive.TButton' if i == index else 'Sidebar.TButton')
        # Show corresponding content
        self.notebook.select(index)

    def _create_dashboard_tab(self):
        """Create the dashboard overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.tabs.dashboard"))
        self._add_sidebar_button(_t("staff_hr.tabs.dashboard"))

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
                   command=lambda: self._select_sidebar(1)).grid(row=0, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.clock_in_out"), width=18,
                   command=lambda: self._select_sidebar(2)).grid(row=0, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.view_training"), width=18,
                   command=lambda: self._select_sidebar(3)).grid(row=0, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.my_goals"), width=18,
                   command=lambda: self._select_sidebar(4)).grid(row=0, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.my_contract"), width=18,
                   command=lambda: self._select_sidebar(6)).grid(row=1, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.submit_expense"), width=18,
                   command=lambda: self._select_sidebar(7)).grid(row=1, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text=_t("staff_hr.dashboard.actions.file_grievance"), width=18,
                   command=lambda: self._select_sidebar(8)).grid(row=1, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text="Payroll", width=18,
                   command=lambda: self._select_sidebar(9)).grid(row=1, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text="My Schedule", width=18,
                   command=lambda: self._select_sidebar(10)).grid(row=2, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text="Curriculum", width=18,
                   command=lambda: self._select_sidebar(11)).grid(row=2, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text="Travel", width=18,
                   command=lambda: self._select_sidebar(12)).grid(row=2, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text="Sabbatical", width=18,
                   command=lambda: self._select_sidebar(13)).grid(row=2, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text="Committees", width=18,
                   command=lambda: self._select_sidebar(14)).grid(row=3, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text="IP Management", width=18,
                   command=lambda: self._select_sidebar(15)).grid(row=3, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text="Equipment", width=18,
                   command=lambda: self._select_sidebar(16)).grid(row=3, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text="Cover", width=18,
                   command=lambda: self._select_sidebar(17)).grid(row=3, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text="Workload", width=18,
                   command=lambda: self._select_sidebar(18)).grid(row=4, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text="Directory", width=18,
                   command=lambda: self._select_sidebar(19)).grid(row=4, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text="Mentoring", width=18,
                   command=lambda: self._select_sidebar(20)).grid(row=4, column=2, padx=8, pady=5)
        ttk.Button(actions_grid, text="Grant Budget", width=18,
                   command=lambda: self._select_sidebar(21)).grid(row=4, column=3, padx=8, pady=5)
        ttk.Button(actions_grid, text="Peer Review", width=18,
                   command=lambda: self._select_sidebar(22)).grid(row=5, column=0, padx=8, pady=5)
        ttk.Button(actions_grid, text="Comm Hub", width=18,
                   command=lambda: self._select_sidebar(23)).grid(row=5, column=1, padx=8, pady=5)
        ttk.Button(actions_grid, text="Teaching Load", width=18,
                   command=lambda: self._select_sidebar(24)).grid(row=5, column=2, padx=8, pady=5)

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
        """Safely load a GUI section, avoiding duplicates on error."""
        tab_count_before = len(self.notebook.tabs())
        try:
            gui_class(self.root, self.auth, self.notebook)
        except Exception as e:
            # Only add error tab if the GUI didn't already add one
            if len(self.notebook.tabs()) == tab_count_before:
                tab = ttk.Frame(self.notebook)
                self.notebook.add(tab, text=tab_name)
                ttk.Label(tab, text=_t("staff_hr.errors.error_loading", module=tab_name, error=str(e))).pack(pady=20)
        self._add_sidebar_button(tab_name)

    def _load_leave_management(self):
        """Load leave management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.leave_management_gui import LeaveManagementGUI
        self._load_tab_safe(LeaveManagementGUI, _t("staff_hr.tabs.leave_management"))

    def _load_time_attendance(self):
        """Load time & attendance as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.time_attendance_gui import TimeAttendanceGUI
        self._load_tab_safe(TimeAttendanceGUI, _t("staff_hr.tabs.time_attendance"))

    def _load_training(self):
        """Load training & certifications as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.training_gui import TrainingGUI
        self._load_tab_safe(TrainingGUI, _t("staff_hr.tabs.training"))

    def _load_appraisals(self):
        """Load performance appraisals as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.appraisal_gui import AppraisalGUI
        self._load_tab_safe(AppraisalGUI, _t("staff_hr.tabs.appraisals"))

    def _load_onboarding(self):
        """Load onboarding as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.onboarding_gui import OnboardingGUI
        self._load_tab_safe(OnboardingGUI, _t("staff_hr.tabs.onboarding"))

    def _load_contracts(self):
        """Load contract management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.contract_gui import ContractGUI
        self._load_tab_safe(ContractGUI, _t("staff_hr.tabs.contracts"))

    def _load_expenses(self):
        """Load expense claims as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.expense_gui import ExpenseGUI
        self._load_tab_safe(ExpenseGUI, _t("staff_hr.tabs.expenses"))

    def _load_grievances(self):
        """Load grievance management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.grievance_gui import GrievanceGUI
        self._load_tab_safe(GrievanceGUI, _t("staff_hr.tabs.grievances"))

    def _load_payroll(self):
        """Load payroll management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.payroll_gui import PayrollGUI
        self._load_tab_safe(PayrollGUI, "Payroll")

    def _load_faculty_schedule(self):
        """Load faculty schedule builder as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.faculty_schedule_gui import FacultyScheduleGUI
        self._load_tab_safe(FacultyScheduleGUI, "Schedule")

    def _load_curriculum(self):
        """Load curriculum design tools as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.curriculum_gui import CurriculumGUI
        self._load_tab_safe(CurriculumGUI, "Curriculum")

    def _load_travel(self):
        """Load travel & conference management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.travel_gui import TravelGUI
        self._load_tab_safe(TravelGUI, "Travel")

    def _load_sabbatical(self):
        """Load sabbatical / study leave as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.sabbatical_gui import SabbaticalGUI
        self._load_tab_safe(SabbaticalGUI, "Sabbatical")

    def _load_committees(self):
        """Load committee management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.committee_gui import CommitteeGUI
        self._load_tab_safe(CommitteeGUI, "Committees")

    def _load_ip(self):
        """Load intellectual property management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.ip_gui import IPGUI
        self._load_tab_safe(IPGUI, "IP")

    def _load_equipment(self):
        """Load lab/equipment booking as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.equipment_gui import EquipmentGUI
        self._load_tab_safe(EquipmentGUI, "Equipment")

    def _load_cover(self):
        """Load substitute/cover arrangements as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.cover_gui import CoverGUI
        self._load_tab_safe(CoverGUI, "Cover")

    def _load_workload(self):
        """Load workload dashboard as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.workload_gui import WorkloadGUI
        self._load_tab_safe(WorkloadGUI, "Workload")

    def _load_directory(self):
        """Load staff directory as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.directory_gui import DirectoryGUI
        self._load_tab_safe(DirectoryGUI, "Directory")

    def _load_mentoring(self):
        """Load mentoring programme management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.mentoring_gui import MentoringGUI
        self._load_tab_safe(MentoringGUI, "Mentoring")

    def _load_grant_budget(self):
        """Load grant budget tracking as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.grant_budget_gui import GrantBudgetGUI
        self._load_tab_safe(GrantBudgetGUI, "Grant Budget")

    def _load_peer_review(self):
        """Load peer review / collaboration as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.peer_review_gui import PeerReviewGUI
        self._load_tab_safe(PeerReviewGUI, "Peer Review")

    def _load_comm_hub(self):
        """Load staff communication hub as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.comm_hub_gui import CommHubGUI
        self._load_tab_safe(CommHubGUI, "Comm Hub")

    def _load_teaching_load(self):
        """Load teaching load management as a tab."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.teaching_load_gui import TeachingLoadGUI
        self._load_tab_safe(TeachingLoadGUI, "Teaching Load")

    def _load_exit_management(self):
        """Load exit management as a tab (admin only)."""
        from education_system.university_system.modules.domain.operations.staff_hr.gui.exit_gui import ExitGUI
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

                # Check for pending travel approvals
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM travel_approvals ta
                        JOIN travel_requests tr ON ta.request_id = tr.request_id
                        WHERE ta.status = 'pending'
                    ''')
                    travel_pending = cursor.fetchone()[0]
                    if travel_pending > 0 and self.current_user.get('role') in ('admin', 'Admin', 'administrator', 'staff'):
                        notifications.append({
                            'icon': '\u2708',
                            'message': f"{travel_pending} travel request(s) awaiting approval"
                        })
                except Exception:
                    pass

                # Check for sabbatical progress reports due
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM sabbatical_applications
                        WHERE user_id = ? AND status = 'approved'
                    ''', (user_id,))
                    active_sabb = cursor.fetchone()[0]
                    if active_sabb > 0:
                        notifications.append({
                            'icon': '\u2709',
                            'message': f"You have {active_sabb} active sabbatical(s) - progress report may be due"
                        })
                except Exception:
                    pass

                # Check for upcoming committee meetings
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM committee_meetings
                        WHERE status = 'scheduled'
                        AND meeting_date BETWEEN date('now') AND date('now', '+7 days')
                    ''')
                    upcoming_meetings = cursor.fetchone()[0]
                    if upcoming_meetings > 0:
                        notifications.append({
                            'icon': '\U0001F4C5',
                            'message': f"{upcoming_meetings} committee meeting(s) scheduled this week"
                        })
                except Exception:
                    pass

                # Check for pending cover requests
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM cover_requests
                        WHERE status = 'open' AND cover_date >= date('now')
                    ''')
                    open_covers = cursor.fetchone()[0]
                    if open_covers > 0:
                        notifications.append({
                            'icon': '\U0001F465',
                            'message': f"{open_covers} open cover request(s) need volunteers"
                        })
                except Exception:
                    pass

                # Check for equipment bookings needing check-in
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM equipment_bookings
                        WHERE user_id = ? AND status = 'approved'
                        AND booking_date = date('now') AND checked_in_at IS NULL
                    ''', (user_id,))
                    checkins = cursor.fetchone()[0]
                    if checkins > 0:
                        notifications.append({
                            'icon': '\U0001F527',
                            'message': f"You have {checkins} equipment booking(s) to check in today"
                        })
                except Exception:
                    pass

                # Check for upcoming mentoring sessions
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM staff_mentoring_sessions s
                        JOIN staff_mentoring_matches m ON s.match_id = m.match_id
                        JOIN staff_mentors mt ON m.mentor_id = mt.mentor_id
                        WHERE s.status = 'scheduled'
                        AND s.session_date BETWEEN date('now') AND date('now', '+7 days')
                        AND (mt.user_id = ? OR m.mentee_user_id = ?)
                    ''', (user_id, user_id))
                    upcoming_sessions = cursor.fetchone()[0]
                    if upcoming_sessions > 0:
                        notifications.append({
                            'icon': '\U0001F91D',
                            'message': f"{upcoming_sessions} mentoring session(s) scheduled this week"
                        })
                except Exception:
                    pass

                # Check for unread grant funding alerts
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM grant_funding_alerts
                        WHERE is_read = 0 AND is_resolved = 0
                    ''')
                    unread_alerts = cursor.fetchone()[0]
                    if unread_alerts > 0:
                        notifications.append({
                            'icon': '\U0001F4B0',
                            'message': f"{unread_alerts} unread grant funding alert(s)"
                        })
                except Exception:
                    pass

                # Check for pending peer review assignments
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM peer_review_assignments
                        WHERE reviewer_id = ? AND status IN ('assigned', 'in_progress')
                    ''', (user_id,))
                    pending_reviews = cursor.fetchone()[0]
                    if pending_reviews > 0:
                        notifications.append({
                            'icon': '\U0001F4DD',
                            'message': f"You have {pending_reviews} pending peer review assignment(s)"
                        })
                except Exception:
                    pass

                # Check for open polls
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM comm_hub_polls
                        WHERE status = 'open'
                    ''')
                    open_polls = cursor.fetchone()[0]
                    if open_polls > 0:
                        notifications.append({
                            'icon': '\U0001F4CA',
                            'message': f"{open_polls} open poll(s) awaiting your vote"
                        })
                except Exception:
                    pass

                # Check for teaching load overload
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM teaching_load_history
                        WHERE user_id = ? AND is_overloaded = 1
                        AND academic_year = (SELECT MAX(academic_year) FROM teaching_load_history WHERE user_id = ?)
                    ''', (user_id, user_id))
                    overloaded = cursor.fetchone()[0]
                    if overloaded > 0:
                        notifications.append({
                            'icon': '\u26a0',
                            'message': "Teaching load overload detected for current period"
                        })
                except Exception:
                    pass

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
