# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import os

# Alias for translation function
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_system_admin(self):
    """Show system administration interface"""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("system_admin_gui.errors.access_denied_title"), _t("system_admin_gui.errors.admin_access_required"))
        return

    self.clear_content()

    ttk.Label(self.content_frame, text=_t("system_admin_gui.title"),
             font=('Arial', 14, 'bold')).grid(row=0, column=0, pady=(0, 20))

    # Admin tools interface
    admin_frame = ttk.LabelFrame(self.content_frame, text=_t("system_admin_gui.frames.administration_tools"), padding="15")
    admin_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
def show_system_administration_gui(self):
    """Launch comprehensive system administration GUI"""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("system_admin_gui.errors.access_denied_title"), _t("system_admin_gui.errors.administrator_access_required"))
        return

    try:
        admin_window = tk.Toplevel(self.root)
        admin_window.title(_t("system_admin_gui.window.title"))
        admin_window.geometry("1400x900")
        admin_window.minsize(1200, 700)

        try:
            admin_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set admin_window as transient: {e}")

        # Create notebook for different admin sections
        notebook = ttk.Notebook(admin_window, padding="10")
        notebook.pack(fill=tk.BOTH, expand=True)

        # Database Management Tab
        db_frame = ttk.Frame(notebook)
        notebook.add(db_frame, text=_t("system_admin_gui.tabs.database_management"))
        self.create_database_admin_tab(db_frame)

        # User Management Tab
        user_frame = ttk.Frame(notebook)
        notebook.add(user_frame, text=_t("system_admin_gui.tabs.user_management"))
        self.create_user_admin_tab(user_frame)

        # System Monitoring Tab
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text=_t("system_admin_gui.tabs.system_monitoring"))
        self.create_monitoring_tab(monitor_frame)

        # Configuration Tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text=_t("system_admin_gui.tabs.configuration"))
        self.create_config_tab(config_frame)

        # Operations Tab (moved from main navigation)
        ops_frame = ttk.Frame(notebook)
        notebook.add(ops_frame, text="Operations")
        self.create_operations_tab(ops_frame)

        # Add close button at the bottom
        button_frame = ttk.Frame(admin_window, padding="10")
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(button_frame, text=_t("system_admin_gui.buttons.close"), command=admin_window.destroy).pack(side=tk.RIGHT)

        print(_t("system_admin_gui.messages.gui_opened_successfully"))

    except Exception as e:
        messagebox.showerror(_t("system_admin_gui.errors.error_title"), _t("system_admin_gui.errors.failed_to_open_admin").format(error=str(e)))
def create_database_admin_tab(self, parent):
    """Create database administration interface"""
    main_frame = ttk.Frame(parent, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Database tools
    tools_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.database_tools"), padding="15")
    tools_frame.pack(fill=tk.X, pady=(0, 20))

    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.database_integrity_check"),
              command=self.run_integrity_check).grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.fix_duplicate_records"),
              command=self.fix_duplicates).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.optimize_database"),
              command=self.optimize_database).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.view_database_statistics"),
              command=self.show_db_statistics).grid(row=1, column=0, padx=5, pady=5)
    ttk.Button(tools_frame, text="Wipe Database",
              command=self.wipe_database).grid(row=1, column=1, padx=5, pady=5)

def create_user_admin_tab(self, parent):
    """Create user administration interface"""
    main_frame = ttk.Frame(parent, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # User management tools
    tools_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.user_management"), padding="15")
    tools_frame.pack(fill=tk.X, pady=(0, 20))

    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.view_all_users"),
              command=self.view_all_users).grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.add_new_user"),
              command=self.add_new_user).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.manage_permissions"),
              command=self.manage_permissions).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.view_active_sessions"),
              command=self.view_active_sessions).grid(row=1, column=0, padx=5, pady=5)

    # User statistics
    stats_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.user_statistics"), padding="15")
    stats_frame.pack(fill=tk.BOTH, expand=True)

    stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=15,
                                           fg="#000000", bg="#FFFFFF")
    stats_text.pack(fill=tk.BOTH, expand=True)

    try:
        # Get user statistics from database
        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor = conn.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            users_by_role = cursor.fetchall()

        stats_info = f"""{_t("system_admin_gui.user_stats.title")}
{'='*50}

{_t("system_admin_gui.user_stats.total_users")}: {total_users}

{_t("system_admin_gui.user_stats.users_by_role")}:
"""
        for role, count in users_by_role:
            stats_info += f"  {role}: {count}\n"

        stats_text.insert("1.0", stats_info)
    except Exception as e:
        stats_text.insert("1.0", _t("system_admin_gui.errors.error_loading_user_statistics").format(error=e))

    stats_text.config(state=tk.DISABLED)

def create_monitoring_tab(self, parent):
    """Create system monitoring interface"""
    main_frame = ttk.Frame(parent, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Monitoring tools
    tools_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.system_monitoring_tools"), padding="15")
    tools_frame.pack(fill=tk.X, pady=(0, 20))

    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.view_system_logs"),
              command=self.view_system_logs).grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.database_performance"),
              command=self.show_db_performance).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.active_connections"),
              command=self.show_active_connections).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.error_logs"),
              command=self.view_error_logs).grid(row=1, column=0, padx=5, pady=5)

    # System status display
    status_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.system_status"), padding="15")
    status_frame.pack(fill=tk.BOTH, expand=True)

    status_text = scrolledtext.ScrolledText(status_frame, wrap=tk.WORD, height=15,
                                           fg="#000000", bg="#FFFFFF")
    status_text.pack(fill=tk.BOTH, expand=True)

    try:
        import psutil
        import platform
        from datetime import datetime

        # Get system information
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Get database stats
        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM activity_log")
            result = cursor.fetchone()
            log_count = result[0] if result else 0

        status_info = f"""{_t("system_admin_gui.system_status.report_title")}
{'='*50}

{_t("system_admin_gui.system_status.system_information")}:
  {_t("system_admin_gui.system_status.platform")}: {platform.system()} {platform.release()}
  {_t("system_admin_gui.system_status.python")}: {platform.python_version()}
  {_t("system_admin_gui.system_status.generated")}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{_t("system_admin_gui.system_status.performance_metrics")}:
  {_t("system_admin_gui.system_status.cpu_usage")}: {cpu_percent}%
  {_t("system_admin_gui.system_status.memory_usage")}: {memory.percent}% ({memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB)
  {_t("system_admin_gui.system_status.disk_usage")}: {disk.percent}% ({disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB)

{_t("system_admin_gui.system_status.database_status")}:
  {_t("system_admin_gui.system_status.activity_logs")}: {log_count} {_t("system_admin_gui.system_status.entries")}
  {_t("system_admin_gui.system_status.status")}: {_t("system_admin_gui.system_status.connected")}

{_t("system_admin_gui.system_status.system_health")}: {_t("system_admin_gui.system_status.healthy") if cpu_percent < 80 and memory.percent < 80 else _t("system_admin_gui.system_status.warning")}
"""
        status_text.insert("1.0", status_info)
    except Exception as e:
        status_text.insert("1.0", f"{_t('system_admin_gui.system_status.title')}\n{'='*50}\n\n{_t('system_admin_gui.errors.error_loading_system_info').format(error=e)}\n\n{_t('system_admin_gui.system_status.basic_monitoring_available')}")

    status_text.config(state=tk.DISABLED)

def create_config_tab(self, parent):
    """Create configuration interface"""
    main_frame = ttk.Frame(parent, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Configuration tools
    tools_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.configuration_management"), padding="15")
    tools_frame.pack(fill=tk.X, pady=(0, 20))

    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.system_settings"),
              command=self.edit_system_settings).grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.email_configuration"),
              command=self.configure_email).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.backup_settings"),
              command=self.configure_backup).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(tools_frame, text=_t("system_admin_gui.buttons.security_settings"),
              command=self.configure_security).grid(row=1, column=0, padx=5, pady=5)

    # Current configuration display
    config_frame = ttk.LabelFrame(main_frame, text=_t("system_admin_gui.frames.current_configuration"), padding="15")
    config_frame.pack(fill=tk.BOTH, expand=True)

    config_text = scrolledtext.ScrolledText(config_frame, wrap=tk.WORD, height=15,
                                           fg="#000000", bg="#FFFFFF")
    config_text.pack(fill=tk.BOTH, expand=True)

    try:
        from education_system.university_system.modules.shared.constants import paths
        import os

        config_info = f"""{_t("system_admin_gui.config.title")}
{'='*50}

{_t("system_admin_gui.config.file_paths")}:
  {_t("system_admin_gui.config.database")}: {paths.DEFAULT_DB_PATH}
  {_t("system_admin_gui.config.logs")}: {paths.LOG_DIR}
  {_t("system_admin_gui.config.backups")}: {paths.BACKUP_DIR}
    Database backups: {paths.BACKUP_DATABASE_DIR}
    File backups: {paths.BACKUP_FILES_DIR}
    Attendance: {paths.BACKUP_ATTENDANCE_DIR}
    Finance: {paths.BACKUP_FINANCE_DIR}
    Library: {paths.BACKUP_LIBRARY_DIR}
    Health: {paths.BACKUP_HEALTH_DIR}
    Settings: {paths.BACKUP_SETTINGS_DIR}
    Calendar: {paths.BACKUP_CALENDAR_DIR}
  {_t("system_admin_gui.config.uploads")}: {paths.UPLOAD_DIR}

{_t("system_admin_gui.config.system_settings")}:
  {_t("system_admin_gui.config.project_root")}: {paths.PROJECT_ROOT}
  {_t("system_admin_gui.config.data_directory")}: {paths.DATA_DIR}

{_t("system_admin_gui.config.database_configuration")}:
  {_t("system_admin_gui.config.type")}: SQLite
  {_t("system_admin_gui.config.connection_pooling")}: {_t("system_admin_gui.config.enabled")}
  {_t("system_admin_gui.config.wal_mode")}: {_t("system_admin_gui.config.enabled")}

{_t("system_admin_gui.config.authentication")}:
  {_t("system_admin_gui.config.password_hashing")}: PBKDF2 (1,000,000 {_t("system_admin_gui.config.iterations")})
  {_t("system_admin_gui.config.multi_factor_auth")}: {_t("system_admin_gui.config.available")}
  {_t("system_admin_gui.config.session_management")}: {_t("system_admin_gui.config.token_based")}

{_t("system_admin_gui.config.email_service")}:
  {_t("system_admin_gui.system_status.status")}: {_t("system_admin_gui.config.configured") if os.path.exists(paths.PROJECT_ROOT / '.env') else _t("system_admin_gui.config.not_configured")}
  {_t("system_admin_gui.config.queue_system")}: {_t("system_admin_gui.config.asynchronous")}

{_t("system_admin_gui.config.logging")}:
  {_t("system_admin_gui.config.activity_logging")}: {_t("system_admin_gui.config.enabled")}
  {_t("system_admin_gui.config.log_rotation")}: {_t("system_admin_gui.config.daily")}
  {_t("system_admin_gui.config.retention")}: 90 {_t("system_admin_gui.config.days")}

{_t("system_admin_gui.config.note")}
"""
        config_text.insert("1.0", config_info)
    except Exception as e:
        config_text.insert("1.0", f"{_t('system_admin_gui.config.overview_title')}\n{'='*50}\n\n{_t('system_admin_gui.errors.error_loading_configuration').format(error=e)}\n\n{_t('system_admin_gui.config.use_tools_message')}")

    config_text.config(state=tk.DISABLED)

def create_operations_tab(self, parent):
    """Create operations tools tab with moved admin features"""
    import tkinter as tk
    from tkinter import ttk, messagebox

    main_frame = ttk.Frame(parent, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Monitoring & Logs
    logs_frame = ttk.LabelFrame(main_frame, text="Monitoring & Logs", padding="15")
    logs_frame.pack(fill=tk.X, pady=(0, 15))

    def launch_feature(title, method_name):
        try:
            method = getattr(self, method_name, None)
            if method:
                method()
            else:
                messagebox.showinfo("Info", f"{title} is accessible via the main menu.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {title}: {e}")

    row, col = 0, 0
    monitoring_buttons = [
        ("Audit Log Viewer", 'show_audit_log_viewer'),
        ("Activity Logger", 'show_activity_logger'),
        ("Activity Log", 'show_activity_log'),
        ("System Monitoring", 'show_system_monitoring_dashboard'),
    ]
    for label, method in monitoring_buttons:
        ttk.Button(logs_frame, text=label,
                  command=lambda m=method, l=label: launch_feature(l, m)).grid(
            row=row, column=col, padx=5, pady=5, sticky='ew')
        col += 1
        if col >= 3:
            col = 0
            row += 1

    # System Configuration
    config_frame = ttk.LabelFrame(main_frame, text="System Configuration", padding="15")
    config_frame.pack(fill=tk.X, pady=(0, 15))

    row, col = 0, 0
    config_buttons = [
        ("Configuration Editor", 'show_configuration_editor'),
        ("Query Analyser", 'show_query_analyser'),
        ("Capacity Planning", 'show_capacity_planning'),
        ("API Documentation", 'show_api_documentation'),
        ("Notification Templates", 'show_notification_template_manager'),
    ]
    for label, method in config_buttons:
        ttk.Button(config_frame, text=label,
                  command=lambda m=method, l=label: launch_feature(l, m)).grid(
            row=row, column=col, padx=5, pady=5, sticky='ew')
        col += 1
        if col >= 3:
            col = 0
            row += 1

    # Data & Compliance
    data_frame = ttk.LabelFrame(main_frame, text="Data & Compliance", padding="15")
    data_frame.pack(fill=tk.X, pady=(0, 15))

    row, col = 0, 0
    data_buttons = [
        ("Data Retention Manager", 'show_data_retention_manager'),
        ("System Changelog", 'show_system_changelog'),
        ("Department Isolation", 'show_department_isolation'),
        ("Integration Status", 'show_integration_status_dashboard'),
        ("License Management", 'show_license_management'),
        ("Disaster Recovery", 'show_disaster_recovery_plan'),
    ]
    for label, method in data_buttons:
        ttk.Button(data_frame, text=label,
                  command=lambda m=method, l=label: launch_feature(l, m)).grid(
            row=row, column=col, padx=5, pady=5, sticky='ew')
        col += 1
        if col >= 3:
            col = 0
            row += 1

def view_active_sessions(self):
    """View active user sessions"""
    try:
        sessions_window = tk.Toplevel(self.root)
        sessions_window.title(_t("system_admin_gui.sessions.window_title"))
        sessions_window.geometry("700x400")

        ttk.Label(sessions_window, text=_t("system_admin_gui.sessions.title"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Create treeview
        tree_frame = ttk.Frame(sessions_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("Username", "Role", "Login Time", "Status")
        column_headers = [
            _t("system_admin_gui.sessions.columns.username"),
            _t("system_admin_gui.sessions.columns.role"),
            _t("system_admin_gui.sessions.columns.login_time"),
            _t("system_admin_gui.sessions.columns.status")
        ]
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        for col, header in zip(columns, column_headers):
            tree.heading(col, text=header)
            tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Get active sessions from auth system
        if self.auth.current_user:
            from datetime import datetime
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            tree.insert("", tk.END, values=(
                self.auth.current_user.get('username'),
                self.auth.current_user.get('role'),
                current_time,
                _t("system_admin_gui.sessions.status_active")
            ))

        ttk.Button(sessions_window, text=_t("system_admin_gui.buttons.close"), command=sessions_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("system_admin_gui.errors.error_title"), _t("system_admin_gui.errors.failed_to_view_sessions").format(error=e))
def view_system_logs(self):
    """View system logs"""
    try:
        logs_window = tk.Toplevel(self.root)
        logs_window.title(_t("system_admin_gui.logs.window_title"))
        logs_window.geometry("900x600")

        ttk.Label(logs_window, text=_t("system_admin_gui.logs.title"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        log_text = scrolledtext.ScrolledText(logs_window, wrap=tk.WORD,
                                             fg="#000000", bg="#FFFFFF")
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load recent logs from database
        from education_system.university_system.infrastructure.database.db import get_connection
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT timestamp, user_id, action, details
                    FROM activity_log
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)
                logs = cursor.fetchall()

            log_content = _t("system_admin_gui.logs.recent_activity") + "\n" + "="*80 + "\n\n"
            for log in logs:
                log_content += f"[{log[0]}] {_t('system_admin_gui.logs.user')}: {log[1]} - {_t('system_admin_gui.logs.action')}: {log[2]}\n"
                if log[3]:
                    log_content += f"  {_t('system_admin_gui.logs.details')}: {log[3]}\n"
                log_content += "-"*80 + "\n"

            log_text.insert("1.0", log_content)
        except Exception as e:
            log_text.insert("1.0", _t("system_admin_gui.errors.error_loading_logs").format(error=e) + "\n\n" + _t("system_admin_gui.logs.activity_logger_available"))

        log_text.config(state=tk.DISABLED)
        ttk.Button(logs_window, text=_t("system_admin_gui.buttons.close"), command=logs_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("system_admin_gui.errors.error_title"), _t("system_admin_gui.errors.failed_to_view_logs").format(error=e))
def view_error_logs(self):
    """View error logs"""
    try:
        error_window = tk.Toplevel(self.root)
        error_window.title(_t("system_admin_gui.error_logs.window_title"))
        error_window.geometry("900x600")

        ttk.Label(error_window, text=_t("system_admin_gui.error_logs.title"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        error_text = scrolledtext.ScrolledText(error_window, wrap=tk.WORD,
                                               fg="#000000", bg="#FFFFFF")
        error_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Try to load error logs from log file
        from education_system.university_system.modules.shared.constants import paths
        import os

        try:
            log_file = paths.LOG_DIR / "error.log"
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines
                    error_content = _t("system_admin_gui.error_logs.recent_errors") + "\n" + "="*80 + "\n\n"
                    error_content += "".join(lines)
                    error_text.insert("1.0", error_content)
            else:
                error_text.insert("1.0", _t("system_admin_gui.error_logs.no_errors_found") + "\n\n" + _t("system_admin_gui.error_logs.system_running_without_errors"))
        except Exception as e:
            error_text.insert("1.0", _t("system_admin_gui.errors.error_reading_log_file").format(error=e) + "\n\n" + _t("system_admin_gui.error_logs.logs_available_in_directory"))

        error_text.config(state=tk.DISABLED)
        ttk.Button(error_window, text=_t("system_admin_gui.buttons.close"), command=error_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("system_admin_gui.errors.error_title"), _t("system_admin_gui.errors.failed_to_view_error_logs").format(error=e))
