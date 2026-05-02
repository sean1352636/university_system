# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import database connection
from education_system.university_system.infrastructure.database.db import get_connection

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import get_text as _

# Import GUI availability flags and classes
from education_system.university_system.modules.shared.gui.main.imports import gui_imports
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    STUDENT_ANALYTICS_GUI_AVAILABLE,
    ANALYTICS_GUI_AVAILABLE,
    CHATBOT_GUI_AVAILABLE,
    GUIStudentAnalytics,
    UniversityChatbotGUI,
)

def show_integrated_dashboard(self):
    """Show integrated dashboard with system overview and quick stats"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.login_required"))
        return

    self.clear_content()

    # Create dashboard layout
    dashboard_frame = ttk.Frame(self.content_frame)
    dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Title
    title_label = ttk.Label(dashboard_frame, text=_("dashboard.title"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=(0, 20))

    # Create notebook for different dashboard sections.
    # ``self.workspace_notebook`` is exposed so feature launchers can
    # opt into rendering inside this notebook as tabs (see
    # ``open_in_workspace`` on UnifiedManagementGUI) — addresses the
    # "right content panel is decorative" gap from the 8.117.16 layout
    # review. The dashboard tabs below stay as the home view; any
    # opted-in launcher appends new tabs to the right of them.
    notebook = ttk.Notebook(dashboard_frame)
    notebook.pack(fill=tk.BOTH, expand=True)
    self.workspace_notebook = notebook
    # Track tabs added by ``open_in_workspace`` so re-opens raise the
    # existing tab instead of stacking duplicates. Keyed by title.
    if not hasattr(self, 'workspace_tabs') or self.workspace_tabs is None:
        self.workspace_tabs = {}
    else:
        # Wipe stale references — the previous notebook's tab ids are
        # invalid against this freshly-built notebook.
        self.workspace_tabs.clear()

    # Role-specific "My Dashboard" tab (inserted first)
    role = self.auth.current_user.get('role', '')
    try:
        from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService
        dash_service = DashboardService()
        my_dash_frame = ttk.Frame(notebook)

        if role == 'student':
            from education_system.university_system.modules.shared.gui.main.dashboard.student_dashboard import create_student_dashboard
            create_student_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
        elif role in ('instructor', 'staff'):
            from education_system.university_system.modules.shared.gui.main.dashboard.instructor_dashboard import create_instructor_dashboard
            create_instructor_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
        elif role == 'admin':
            from education_system.university_system.modules.shared.gui.main.dashboard.admin_dashboard import create_admin_dashboard
            create_admin_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
    except Exception as e:
        logging.warning(f"Could not load role-specific dashboard: {e}")

    # System Overview Tab
    overview_frame = ttk.Frame(notebook)
    notebook.add(overview_frame, text=_("dashboard.tabs.overview"))
    self.create_overview_tab(overview_frame)

    # Quick Stats Tab
    stats_frame = ttk.Frame(notebook)
    notebook.add(stats_frame, text=_("dashboard.tabs.statistics"))
    self.create_stats_tab(stats_frame)

    # Recent Activity Tab
    activity_frame = ttk.Frame(notebook)
    notebook.add(activity_frame, text=_("dashboard.tabs.activity"))
    self.create_activity_tab(activity_frame)

    # System Health Tab
    health_frame = ttk.Frame(notebook)
    notebook.add(health_frame, text=_("dashboard.tabs.health"))
    self.create_health_tab(health_frame)

    # Admin-only tabs
    if role == 'admin':
        try:
            from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService as _DS
            _admin_svc = _DS()

            # Login Analytics tab (Feature 13)
            login_analytics_frame = ttk.Frame(notebook)
            notebook.add(login_analytics_frame, text="Login Analytics")
            from education_system.university_system.modules.shared.gui.main.dashboard.login_analytics_dashboard import create_login_analytics_tab
            create_login_analytics_tab(login_analytics_frame, _admin_svc)

            # Operational Dashboards tab (Feature 14)
            operations_frame = ttk.Frame(notebook)
            notebook.add(operations_frame, text="Operations")
            from education_system.university_system.modules.shared.gui.main.dashboard.operations_dashboard import create_operations_tab
            create_operations_tab(operations_frame, _admin_svc)

            # System Health (enhanced) tab (Feature 15)
            sys_health_frame = ttk.Frame(notebook)
            notebook.add(sys_health_frame, text="System Health (Live)")
            from education_system.university_system.modules.shared.gui.main.dashboard.system_health_dashboard import create_system_health_tab
            create_system_health_tab(sys_health_frame, _admin_svc)
        except Exception as e:
            logging.warning(f"Could not load admin dashboard extensions: {e}")

    # Select the role-specific tab if it was added
    if role in ('student', 'instructor', 'staff', 'admin'):
        try:
            notebook.select(0)
        except Exception:
            pass

    print(_("dashboard.messages.opened_successfully"))
def create_overview_tab(self, parent):
    """Create system overview tab"""
    overview_container = ttk.Frame(parent, padding="20")
    overview_container.pack(fill=tk.BOTH, expand=True)

    # Welcome message
    welcome_text = _("dashboard.overview.welcome", username=self.auth.current_user.get('username', _("common.user")))
    ttk.Label(overview_container, text=welcome_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Quick access buttons in a grid
    buttons_frame = ttk.LabelFrame(overview_container, text=_("dashboard.overview.quick_access"), padding="15")
    buttons_frame.pack(fill=tk.X, pady=(0, 20))

    # Configure grid
    for i in range(3):
        buttons_frame.columnconfigure(i, weight=1)

    # Quick access buttons
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.student_records"),
              command=self.show_student_records).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.grade_tracking"),
              command=self.show_grade_tracking_gui).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.attendance"),
              command=self.open_attendance_gui).grid(row=0, column=2, padx=5, pady=5, sticky="ew")

    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.course_management"),
              command=self.show_course_management).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.finance_management"),
              command=self.show_finance_management).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.reports"),
              command=self.show_enhanced_reporting_dashboard).grid(row=1, column=2, padx=5, pady=5, sticky="ew")

    # System status
    status_frame = ttk.LabelFrame(overview_container, text=_("dashboard.overview.system_status"), padding="15")
    status_frame.pack(fill=tk.X, pady=(0, 20))

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ttk.Label(status_frame, text=_("dashboard.overview.current_time", time=current_time)).pack(anchor="w")
    ttk.Label(status_frame, text=_("dashboard.overview.user_role", role=self.auth.current_user.get('role', _("common.unknown")))).pack(anchor="w")
    ttk.Label(status_frame, text=_("dashboard.overview.database_connected")).pack(anchor="w")

def create_stats_tab(self, parent):
    """Create quick statistics tab"""
    stats_container = ttk.Frame(parent, padding="20")
    stats_container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(stats_container, text=_("dashboard.statistics.title"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Stats grid
    stats_frame = ttk.Frame(stats_container)
    stats_frame.pack(fill=tk.BOTH, expand=True)

    try:
        # Fetch live statistics from the database
        total_students = 0
        active_courses = 0
        pending_assignments = 0
        recent_logins = 0
        total_users = 0
        active_enrollments = 0

        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()
            total_students = row['cnt'] if row else 0

            row = conn.execute("SELECT COUNT(*) as cnt FROM modules WHERE is_active = 1").fetchone()
            active_courses = row['cnt'] if row else 0

            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM assignments WHERE due_date >= date('now') AND status = 'active'"
                ).fetchone()
                pending_assignments = row['cnt'] if row else 0
            except Exception:
                pass

            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM login_attempts WHERE success = 1 AND attempt_time >= datetime('now', '-24 hours')"
                ).fetchone()
                recent_logins = row['cnt'] if row else 0
            except Exception:
                pass

            row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
            total_users = row['cnt'] if row else 0

            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM student_modules WHERE status IN ('Enrolled', 'enrolled')"
                ).fetchone()
                active_enrollments = row['cnt'] if row else 0
            except Exception:
                pass

        stats_text = f"""{_("dashboard.statistics.database_stats")}
  {_("dashboard.statistics.total_students")} {total_students}
  {_("dashboard.statistics.active_courses")} {active_courses}
  {_("dashboard.statistics.pending_assignments")} {pending_assignments}
  {_("dashboard.statistics.system_uptime")} {_("common.active")}
  {_("dashboard.statistics.recent_logins")} {recent_logins} (last 24h)

  Total Users: {total_users}
  Active Enrollments: {active_enrollments}"""

        stats_display = tk.Text(stats_frame, wrap=tk.WORD, height=15, width=60)
        stats_display.pack(fill=tk.BOTH, expand=True)
        stats_display.insert(tk.END, stats_text)
        stats_display.config(state=tk.DISABLED)

    except Exception as e:
        ttk.Label(stats_frame, text=_("dashboard.statistics.load_error", error=str(e))).pack()

def create_activity_tab(self, parent):
    """Create recent activity tab with live data from activity_log table."""
    activity_container = ttk.Frame(parent, padding="20")
    activity_container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(activity_container, text=_("dashboard.activity.title"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 10))

    # Controls row
    controls = ttk.Frame(activity_container)
    controls.pack(fill=tk.X, pady=(0, 5))

    filter_var = tk.StringVar(value="All")
    ttk.Label(controls, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
    filter_combo = ttk.Combobox(controls, textvariable=filter_var, state='readonly',
                                 values=['All', 'login', 'logout', 'create', 'update', 'delete', 'view', 'export'],
                                 width=12)
    filter_combo.pack(side=tk.LEFT, padx=(0, 10))

    # Treeview for activity log
    cols = ('timestamp', 'username', 'action', 'details')
    tree_frame = ttk.Frame(activity_container)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
    tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=18,
                        yscrollcommand=tree_scroll.set)
    tree_scroll.config(command=tree.yview)

    tree.heading('timestamp', text='Timestamp')
    tree.heading('username', text='User')
    tree.heading('action', text='Action')
    tree.heading('details', text='Details')
    tree.column('timestamp', width=160)
    tree.column('username', width=100)
    tree.column('action', width=150)
    tree.column('details', width=400)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def load_activity(action_filter='All'):
        for item in tree.get_children():
            tree.delete(item)
        try:
            with get_connection() as conn:
                if action_filter == 'All':
                    rows = conn.execute(
                        "SELECT timestamp, username, action, details FROM activity_log "
                        "ORDER BY id DESC LIMIT 100"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT timestamp, username, action, details FROM activity_log "
                        "WHERE LOWER(action) LIKE ? ORDER BY id DESC LIMIT 100",
                        (f'%{action_filter.lower()}%',)
                    ).fetchall()
                for r in rows:
                    ts = r['timestamp'] if r['timestamp'] else ''
                    user = r['username'] if r['username'] else ''
                    action = r['action'] if r['action'] else ''
                    details = r['details'] if r['details'] else ''
                    tree.insert('', tk.END, values=(ts, user, action, details))
        except Exception as e:
            tree.insert('', tk.END, values=('', '', 'Error loading activity', str(e)))

    filter_combo.bind('<<ComboboxSelected>>', lambda e: load_activity(filter_var.get()))

    ttk.Button(controls, text="Refresh", command=lambda: load_activity(filter_var.get())).pack(side=tk.RIGHT)

    load_activity()

def create_health_tab(self, parent):
    """Create system health monitoring tab with live metrics."""
    if self.health_portal_gui:
        self.health_portal_gui.create_health_tab(parent)
    else:
        import os

        health_container = ttk.Frame(parent, padding="20")
        health_container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(health_container, text=_("dashboard.health.title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        metrics_frame = ttk.LabelFrame(health_container, text="System Metrics", padding="10")
        metrics_frame.pack(fill=tk.X, pady=(0, 10))

        info_labels = {}

        def _add_metric(parent_f, label, row):
            ttk.Label(parent_f, text=label, width=25, anchor='w').grid(row=row, column=0, padx=5, pady=3, sticky='w')
            val = ttk.Label(parent_f, text="...", anchor='w')
            val.grid(row=row, column=1, padx=5, pady=3, sticky='w')
            info_labels[label] = val

        _add_metric(metrics_frame, "Database Size", 0)
        _add_metric(metrics_frame, "Total Tables", 1)
        _add_metric(metrics_frame, "Total Rows (est.)", 2)
        _add_metric(metrics_frame, "Active Users (24h)", 3)
        _add_metric(metrics_frame, "Login Attempts (24h)", 4)
        _add_metric(metrics_frame, "Failed Logins (24h)", 5)
        _add_metric(metrics_frame, "Activity Log Entries", 6)
        _add_metric(metrics_frame, "Application Uptime", 7)

        # Connection Pool section
        pool_frame = ttk.LabelFrame(health_container, text="Connection Pool", padding="10")
        pool_frame.pack(fill=tk.X, pady=(0, 10))

        pool_labels = {}

        def _add_pool_metric(parent_f, label, row):
            ttk.Label(parent_f, text=label, width=25, anchor='w').grid(row=row, column=0, padx=5, pady=3, sticky='w')
            val = ttk.Label(parent_f, text="...", anchor='w')
            val.grid(row=row, column=1, padx=5, pady=3, sticky='w')
            pool_labels[label] = val

        _add_pool_metric(pool_frame, "Pool Status", 0)
        _add_pool_metric(pool_frame, "Total Connections", 1)
        _add_pool_metric(pool_frame, "Active Connections", 2)
        _add_pool_metric(pool_frame, "Idle Connections", 3)
        _add_pool_metric(pool_frame, "Connection Errors", 4)

        # Error counts section
        errors_frame = ttk.LabelFrame(health_container, text="Recent Errors", padding="10")
        errors_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        error_text = tk.Text(errors_frame, wrap=tk.WORD, height=6)
        error_text.pack(fill=tk.BOTH, expand=True)
        error_text.config(state=tk.DISABLED)

        _start_time = datetime.now()

        def refresh_health():
            try:
                from education_system.university_system.modules.shared.constants import paths
                db_path = str(paths.DEFAULT_DB_PATH)

                # Database size
                try:
                    db_size = os.path.getsize(db_path)
                    if db_size >= 1_048_576:
                        size_str = f"{db_size / 1_048_576:.1f} MB"
                    else:
                        size_str = f"{db_size / 1024:.1f} KB"
                    info_labels["Database Size"].config(text=size_str)
                except Exception:
                    info_labels["Database Size"].config(text="Unknown")

                with get_connection() as conn:
                    # Table count
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'"
                    ).fetchone()
                    info_labels["Total Tables"].config(text=str(row['cnt'] if row else 0))

                    # Estimated total rows from sqlite_stat1
                    try:
                        row = conn.execute(
                            "SELECT SUM(stat) as total FROM (SELECT CAST(stat AS INTEGER) as stat FROM sqlite_stat1)"
                        ).fetchone()
                        total = row['total'] if row and row['total'] else 0
                        info_labels["Total Rows (est.)"].config(text=f"{total:,}")
                    except Exception:
                        info_labels["Total Rows (est.)"].config(text="N/A")

                    # Active users (24h)
                    try:
                        row = conn.execute(
                            "SELECT COUNT(DISTINCT username) as cnt FROM activity_log "
                            "WHERE timestamp >= datetime('now', '-24 hours')"
                        ).fetchone()
                        info_labels["Active Users (24h)"].config(text=str(row['cnt'] if row else 0))
                    except Exception:
                        info_labels["Active Users (24h)"].config(text="N/A")

                    # Login attempts (24h)
                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM login_attempts "
                            "WHERE attempt_time >= datetime('now', '-24 hours')"
                        ).fetchone()
                        info_labels["Login Attempts (24h)"].config(text=str(row['cnt'] if row else 0))
                    except Exception:
                        info_labels["Login Attempts (24h)"].config(text="N/A")

                    # Failed logins (24h)
                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM login_attempts "
                            "WHERE success = 0 AND attempt_time >= datetime('now', '-24 hours')"
                        ).fetchone()
                        info_labels["Failed Logins (24h)"].config(text=str(row['cnt'] if row else 0))
                    except Exception:
                        info_labels["Failed Logins (24h)"].config(text="N/A")

                    # Activity log count
                    row = conn.execute("SELECT COUNT(*) as cnt FROM activity_log").fetchone()
                    info_labels["Activity Log Entries"].config(text=f"{row['cnt']:,}" if row else "0")

                # Uptime
                delta = datetime.now() - _start_time
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                info_labels["Application Uptime"].config(text=f"{hours}h {minutes}m {seconds}s")

                # Connection pool metrics
                try:
                    from education_system.university_system.infrastructure.database.pool_metrics import get_pool_metrics
                    metrics = get_pool_metrics()
                    if metrics:
                        pool_labels["Pool Status"].config(text="Active")
                        pool_labels["Total Connections"].config(text=str(metrics.total_connections))
                        pool_labels["Active Connections"].config(text=str(metrics.active_connections))
                        pool_labels["Idle Connections"].config(text=str(metrics.idle_connections))
                        pool_labels["Connection Errors"].config(text=str(metrics.connection_errors))
                    else:
                        pool_labels["Pool Status"].config(text="Active (no collector)")
                        pool_labels["Total Connections"].config(text="N/A")
                        pool_labels["Active Connections"].config(text="N/A")
                        pool_labels["Idle Connections"].config(text="N/A")
                        pool_labels["Connection Errors"].config(text="N/A")
                except Exception:
                    pool_labels["Pool Status"].config(text="Active (metrics unavailable)")
                    for k in ["Total Connections", "Active Connections", "Idle Connections", "Connection Errors"]:
                        pool_labels[k].config(text="N/A")

                # Recent errors from log file
                try:
                    from education_system.university_system.modules.shared.constants import paths as _paths
                    log_file = os.path.join(str(_paths.LOG_DIR), 'app.log')
                    error_lines = []
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            for line in f:
                                if 'ERROR' in line:
                                    error_lines.append(line.strip())
                        error_lines = error_lines[-10:]  # last 10 errors
                    error_text.config(state=tk.NORMAL)
                    error_text.delete('1.0', tk.END)
                    if error_lines:
                        error_text.insert(tk.END, '\n'.join(error_lines))
                    else:
                        error_text.insert(tk.END, 'No recent errors.')
                    error_text.config(state=tk.DISABLED)
                except Exception:
                    error_text.config(state=tk.NORMAL)
                    error_text.delete('1.0', tk.END)
                    error_text.insert(tk.END, 'Could not read log file.')
                    error_text.config(state=tk.DISABLED)

            except Exception as e:
                logging.warning(f"Health tab refresh error: {e}")

        ttk.Button(health_container, text="Refresh", command=refresh_health).pack(anchor='e', pady=(5, 0))
        refresh_health()
def show_analytics(self):
    """Launch the standalone Student Analytics GUI from student_analytics_gui.py"""
    if not self.auth.current_user or 'view_analytics' not in self.auth.current_user.get('permissions', []):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_analytics_permission"))
        return

    try:
        if STUDENT_ANALYTICS_GUI_AVAILABLE:
            # Create a child window for the analytics GUI
            analytics_window = tk.Toplevel(self.root)
            _install_clean_close(analytics_window)
            analytics_window.transient(self.root)

            # Launch the GUI in the child window
            analytics_app = GUIStudentAnalytics(root=analytics_window, auth_manager=self.auth)
        else:
            messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_not_available"))
    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_launch_failed", error=str(e)))
def show_chatbot(self):
    """Launch the full Chatbot GUI using the existing ChatbotGUI class"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_login_required"))
        return

    if not self.auth.check_permission('access_chatbot'):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_chatbot_permission"))
        return

    try:
        # Initialize the chatbot instance if not already done
        if not gui_imports.chatbot_instance:
            if not gui_imports.initialize_chatbot_integration():
                messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_init_failed"))
                return

        # Set authentication system for chatbot
        if gui_imports.chatbot_instance and self.auth:
            gui_imports.chatbot_instance.set_auth_system(self.auth)

        # Use imported UniversityChatbotGUI if available
        if CHATBOT_GUI_AVAILABLE and UniversityChatbotGUI:
            chatbot_window = tk.Toplevel(self.root)
            _install_clean_close(chatbot_window)
            chatbot_window.title(_("dashboard.chatbot.title"))
            chatbot_window.geometry("1000x700")

            chatbot_gui = UniversityChatbotGUI(gui_imports.chatbot_instance, chatbot_window, auth_system=self.auth)
            print(_("dashboard.messages.chatbot_opened"))
        else:
            messagebox.showerror(
                _("common.error"),
                "Chatbot GUI is not available. Please ensure the chatbot module is installed."
            )

        print(_("dashboard.messages.chatbot_launched"))

    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_open_failed", error=str(e)))
        print(f"Chatbot GUI error: {e}")
def log_activity(self, message, level="info", action=None):
    """Log activity with comprehensive error handling"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f"[{timestamp}] {_('dashboard.log.gui_prefix')}: {message}"

        print(formatted_message)

        if level.lower() == "error":
            logging.error(formatted_message)
        elif level.lower() == "warning":
            logging.warning(formatted_message)
        else:
            logging.info(formatted_message)

    except Exception as e:
        print(f"{_('dashboard.log.gui_activity')}: {message}")
        logging.error(f"{_('dashboard.log.logging_error')}: {e}")
def launch_analytics_gui_standalone():
    """Launch analytics GUI as standalone window"""
    try:
        if ANALYTICS_GUI_AVAILABLE:
            analytics_app = GUIStudentAnalytics()
            if auth:
                analytics_app.auth = auth
            analytics_app.run()
        else:
            print(_("dashboard.messages.analytics_not_available_cli"))
            display_analytics_menu()
    except Exception as e:
        print(_("dashboard.errors.analytics_error", error=str(e)))
        display_analytics_menu()
