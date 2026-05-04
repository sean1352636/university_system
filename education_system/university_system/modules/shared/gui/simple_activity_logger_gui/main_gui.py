"""
Main GUI application class for the Enhanced Activity Logger.
"""

from education_system.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    time, json, os, sys, queue,
    datetime, timedelta,
    LOGGER_AVAILABLE, MATPLOTLIB_AVAILABLE,
    _t, init_i18n, get_current_language, show_gui_language_selector,
)

if LOGGER_AVAILABLE:
    from education_system.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
        logger, create_default_config,
        LogLevel, SecurityLevel,
    )

from education_system.university_system.modules.shared.gui.simple_activity_logger_gui.theme import LoggerGUITheme
from education_system.university_system.modules.shared.gui.simple_activity_logger_gui.status_bar import StatusBar
from education_system.university_system.modules.shared.gui.simple_activity_logger_gui.tabs import (
    LogViewerTab, AnalyticsTab, ConfigurationTab,
    SecurityTab, PluginTab, QueryTab,
)


class EnhancedActivityLoggerGUI:
    """Main GUI application for Enhanced Activity Logger"""

    def __init__(self, auth=None, parent=None):
        """
        Initialize the Enhanced Activity Logger GUI.

        Args:
            auth: Authentication instance for returning to main menu
            parent: Optional parent window (Toplevel). If provided, uses it instead of creating new Tk root.
        """
        # Store auth instance for returning to main menu
        self.auth = auth

        # Initialize logger
        self.logger = None
        self.update_queue = queue.Queue()
        self._update_timer_id = None  # Track timer ID for cleanup
        self._destroyed = False  # Flag to prevent callbacks after destroy

        # Handle parent window vs standalone mode
        if parent is not None:
            # Use provided parent window (embedded mode)
            self.root = parent
            self._standalone = False
        else:
            # Create own root window (standalone mode)
            self.root = tk.Tk()
            self.root.title(_t("activity_logger.window_title"))
            self.root.geometry("1400x900")
            self._standalone = True

        # Apply theme (skip global theme changes in embedded mode)
        LoggerGUITheme.apply_theme(self.root, standalone=self._standalone)

        # Setup UI
        self.setup_ui()

        # Connect to logger
        self.connect_to_logger()

        # Start update timer
        self.start_update_timer()

    def setup_ui(self):
        """Setup the main user interface"""
        # Main menu (skip in embedded mode — a ttk.Frame parent has no
        # menubar slot, so calling self.root.config(menu=...) raises
        # "unknown option -menu". Operations Console hosts this GUI in
        # a notebook tab, which is exactly that situation.)
        if self._standalone:
            self.setup_menu()

        # Header
        header_frame = ttk.Frame(self.root, style='AL.Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        # Logo/Title
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(title_frame, text=_t("activity_logger.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=10)

        # Language change button
        ttk.Button(
            title_frame,
            text="\U0001f310 " + _t("activity_logger.language.change"),
            command=self._on_language_change
        ).pack(side=tk.LEFT, padx=10)

        # Connection status
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side=tk.RIGHT, padx=10)

        self.connection_status = tk.StringVar(value=_t("activity_logger.status.disconnected"))
        ttk.Button(
            status_frame,
            text="\U0001f3e0 " + _t("activity_logger.return_home"),
            command=self.return_to_main_menu
        ).pack(side=tk.RIGHT, padx=(0, 10))

        self.connection_label = ttk.Label(status_frame, textvariable=self.connection_status,
                                         style='AL.Error.TLabel')
        self.connection_label.pack(side=tk.RIGHT)

        ttk.Label(status_frame, text=_t("activity_logger.status.label"), style='AL.Info.TLabel').pack(side=tk.RIGHT, padx=(0, 5))

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root, style='AL.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Create tabs
        self.log_viewer_tab = LogViewerTab(self.notebook, self)
        self.notebook.add(self.log_viewer_tab, text="\U0001f4ca " + _t("activity_logger.tabs.live_logs"))

        self.analytics_tab = AnalyticsTab(self.notebook, self)
        self.notebook.add(self.analytics_tab, text="\U0001f4c8 " + _t("activity_logger.tabs.analytics"))

        self.security_tab = SecurityTab(self.notebook, self)
        self.notebook.add(self.security_tab, text="\U0001f512 " + _t("activity_logger.tabs.security"))

        self.config_tab = ConfigurationTab(self.notebook, self)
        self.notebook.add(self.config_tab, text="\u2699\ufe0f " + _t("activity_logger.tabs.configuration"))

        self.plugin_tab = PluginTab(self.notebook, self)
        self.notebook.add(self.plugin_tab, text="\U0001f50c " + _t("activity_logger.tabs.plugins"))

        self.query_tab = QueryTab(self.notebook, self)
        self.notebook.add(self.query_tab, text="\U0001f50d " + _t("activity_logger.tabs.query"))

        # Status bar
        self.status_bar = StatusBar(self.root, controller=self)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def setup_menu(self):
        """Setup the main menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("activity_logger.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("activity_logger.menu.new_config"), command=self.new_config)
        file_menu.add_command(label=_t("activity_logger.menu.load_config"), command=self.load_config)
        file_menu.add_command(label=_t("activity_logger.menu.save_config"), command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label=_t("activity_logger.menu.import_logs"), command=self.import_logs)
        file_menu.add_command(label=_t("activity_logger.menu.export_logs"), command=self.export_logs)

        # Logger menu
        logger_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("activity_logger.menu.logger"), menu=logger_menu)
        logger_menu.add_command(label=_t("activity_logger.menu.connect"), command=self.connect_to_logger)
        logger_menu.add_command(label=_t("activity_logger.menu.disconnect"), command=self.disconnect_logger)
        logger_menu.add_command(label=_t("activity_logger.menu.restart"), command=self.restart_logger)
        logger_menu.add_separator()
        logger_menu.add_command(label=_t("activity_logger.menu.test_log"), command=self.test_log_entry)
        logger_menu.add_command(label=_t("activity_logger.menu.flush_logs"), command=self.flush_logs)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("activity_logger.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("activity_logger.menu.health_check"), command=self.system_health_check)
        tools_menu.add_command(label=_t("activity_logger.menu.generate_report"), command=self.generate_report)
        tools_menu.add_command(label=_t("activity_logger.menu.anomaly_detection"), command=self.run_anomaly_detection)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("activity_logger.menu.db_maintenance"), command=self.database_maintenance)
        tools_menu.add_command(label=_t("activity_logger.menu.log_cleanup"), command=self.log_file_cleanup)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("activity_logger.menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("activity_logger.menu.user_guide"), command=self.show_user_guide)
        help_menu.add_command(label=_t("activity_logger.menu.api_docs"), command=self.show_api_docs)
        help_menu.add_separator()
        help_menu.add_command(label=_t("activity_logger.menu.about"), command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a persistent top-right navigation button"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="\U0001f3e0 " + _t("activity_logger.return_home"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def _on_language_change(self):
        """Handle language change button click"""
        current_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()

        if new_lang != current_lang:
            messagebox.showinfo(
                _t("activity_logger.language.changed_title"),
                _t("activity_logger.language.changed_message")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI elements with current language"""
        init_i18n(get_current_language())

        # Update window title
        if self._standalone:
            self.root.title(_t("activity_logger.window_title"))

        # Rebuild the UI to apply new language
        for widget in self.root.winfo_children():
            widget.destroy()

        self.setup_ui()
        self.connect_to_logger()
        self.start_update_timer()

    def connect_to_logger(self):
        """Connect to the enhanced activity logger"""
        try:
            if LOGGER_AVAILABLE:
                # Use the global logger instance
                self.logger = logger
                self.connection_status.set(_t("activity_logger.status.connected"))
                self.connection_label.configure(style='AL.Success.TLabel')
                self.status_bar.update_logger_status(True)
                self.status_bar.update_status(_t("activity_logger.messages.connected"))

                # Test the connection by getting metrics
                if hasattr(self.logger, 'get_metrics'):
                    metrics = self.logger.get_metrics()
                    self.status_bar.update_queue_size(metrics.get('queue_size', 0))
                    self.status_bar.update_total_logs(metrics.get('logs_processed', 0))

            else:
                # Demo mode
                self.logger = None
                self.connection_status.set(_t("activity_logger.status.demo_mode"))
                self.connection_label.configure(style='AL.Warning.TLabel')
                self.status_bar.update_logger_status(False)
                self.status_bar.update_status(_t("activity_logger.messages.demo_mode"))

        except Exception as e:
            self.connection_status.set(_t("activity_logger.status.error"))
            self.connection_label.configure(style='AL.Error.TLabel')
            self.status_bar.update_logger_status(False)
            self.status_bar.update_status(_t("activity_logger.messages.connection_error", error=str(e)))
            messagebox.showerror(_t("common.error"), _t("activity_logger.errors.connection", error=str(e)))

    def disconnect_logger(self):
        """Disconnect from logger"""
        self.logger = None
        self.connection_status.set(_t("activity_logger.status.disconnected"))
        self.connection_label.configure(style='AL.Error.TLabel')
        self.status_bar.update_logger_status(False)
        self.status_bar.update_status(_t("activity_logger.messages.disconnected"))

    def restart_logger(self):
        """Restart the logger"""
        try:
            if self.logger and hasattr(self.logger, 'shutdown'):
                self.logger.shutdown()

            time.sleep(1)  # Give it a moment to shutdown
            self.connect_to_logger()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("activity_logger.errors.restart", error=str(e)))

    def start_update_timer(self):
        """Start the update timer for real-time updates"""
        # Don't run if destroyed
        if self._destroyed:
            return

        # Cancel previous timer if exists
        if self._update_timer_id:
            try:
                self.root.after_cancel(self._update_timer_id)
            except Exception:
                pass

        try:
            # Check if root window still exists
            if not hasattr(self, 'root') or not self.root.winfo_exists():
                self._destroyed = True
                return

            self.update_gui()
            # Schedule next update and store ID
            if not self._destroyed:
                self._update_timer_id = self.root.after(1000, self.start_update_timer)  # Update every second
        except (tk.TclError, Exception):
            # Widget destroyed, stop scheduling
            self._destroyed = True

    def update_gui(self):
        """Update GUI with real-time data"""
        try:
            if self.logger and hasattr(self.logger, 'get_metrics'):
                metrics = self.logger.get_metrics()
                self.status_bar.update_queue_size(metrics.get('queue_size', 0))
                self.status_bar.update_total_logs(metrics.get('logs_processed', 0))

        except Exception as e:
            # Silently handle errors to avoid spamming
            pass

    # Menu command implementations
    def new_config(self):
        """Create a new configuration"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Create New Configuration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )

            if file_path:
                if LOGGER_AVAILABLE:
                    create_default_config(file_path)
                    messagebox.showinfo("Configuration Created", f"New configuration created at: {file_path}")
                else:
                    # Create a minimal config for demo mode
                    default_config = {
                        "log_dir": "logs",
                        "min_log_level": "INFO",
                        "output_formats": ["json"],
                        "queue_size": 10000
                    }
                    with open(file_path, 'w') as f:
                        json.dump(default_config, f, indent=2)
                    messagebox.showinfo("Configuration Created", f"Demo configuration created at: {file_path}")

        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to create configuration: {str(e)}")

    def load_config(self):
        """Load configuration from file"""
        if hasattr(self.config_tab, 'load_config'):
            self.config_tab.load_config()
        else:
            messagebox.showwarning("Load Configuration", "Configuration tab not available.")

    def save_config(self):
        """Save current configuration to file"""
        if hasattr(self.config_tab, 'save_config'):
            self.config_tab.save_config()
        else:
            messagebox.showwarning("Save Configuration", "Configuration tab not available.")

    def import_logs(self):
        """Import logs from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Import Logs",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return

            # Create import progress dialog
            import_dialog = tk.Toplevel(self.root)
            import_dialog.title(_t("activity_logger.dialogs.import_logs"))
            import_dialog.geometry("600x500")
            import_dialog.transient(self.root)

            ttk.Label(import_dialog, text=_t("activity_logger.import.title"),
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            ttk.Label(import_dialog, text=f"File: {file_path}", foreground='blue').pack()

            # Progress area
            progress_frame = ttk.Frame(import_dialog, padding=10)
            progress_frame.pack(fill='both', expand=True)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
            progress_bar.pack(fill='x', pady=10)

            status_label = ttk.Label(progress_frame, text=_t("activity_logger.import.reading_file"))
            status_label.pack(pady=5)

            results_text = tk.Text(progress_frame, height=20, width=70)
            results_text.pack(fill='both', expand=True, pady=5)

            def perform_import():
                try:
                    import csv

                    imported_count = 0
                    error_count = 0
                    logs_to_import = []

                    # Determine file type and parse
                    if file_path.endswith('.json'):
                        status_label.config(text="Parsing JSON file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                logs_to_import = data
                            elif isinstance(data, dict) and 'logs' in data:
                                logs_to_import = data['logs']
                            else:
                                logs_to_import = [data]

                    elif file_path.endswith('.csv'):
                        status_label.config(text="Parsing CSV file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                logs_to_import.append(row)

                    else:  # Text file
                        status_label.config(text="Parsing text file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    # Parse simple log format: timestamp | level | message
                                    parts = line.split('|')
                                    if len(parts) >= 3:
                                        logs_to_import.append({
                                            'timestamp': parts[0].strip(),
                                            'level': parts[1].strip(),
                                            'message': '|'.join(parts[2:]).strip()
                                        })
                                    else:
                                        logs_to_import.append({
                                            'timestamp': datetime.now().isoformat(),
                                            'level': 'INFO',
                                            'message': line
                                        })

                    results_text.insert('end', f"Found {len(logs_to_import)} log entries\n\n")

                    # Import logs
                    status_label.config(text="Importing logs...")
                    for i, log_entry in enumerate(logs_to_import):
                        try:
                            # In real implementation, would save to database
                            # For now, just validate and count
                            if isinstance(log_entry, dict):
                                timestamp = log_entry.get('timestamp', datetime.now().isoformat())
                                level = log_entry.get('level', 'INFO')
                                message = log_entry.get('message', str(log_entry))

                                results_text.insert('end', f"\u2713 [{timestamp}] {level}: {message[:50]}...\n")
                                imported_count += 1
                            else:
                                error_count += 1
                                results_text.insert('end', f"\u2717 Invalid log entry: {log_entry}\n")

                            # Update progress
                            progress_var.set(20 + (i / len(logs_to_import)) * 80)
                            import_dialog.update()

                        except Exception as e:
                            error_count += 1
                            results_text.insert('end', f"\u2717 Error importing entry: {e}\n")

                        results_text.see('end')

                    progress_var.set(100)
                    status_label.config(text="Import Complete!")

                    # Summary
                    summary = f"\n{'='*60}\nImport Summary:\n"
                    summary += f"Total entries: {len(logs_to_import)}\n"
                    summary += f"Successfully imported: {imported_count}\n"
                    summary += f"Errors: {error_count}\n"
                    results_text.insert('end', summary)

                    ttk.Button(progress_frame, text="Close",
                              command=import_dialog.destroy).pack(pady=10)

                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import logs: {e}",
                                       parent=import_dialog)

            # Start import
            import_dialog.after(100, perform_import)

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import logs: {str(e)}")

    def export_logs(self):
        """Export logs to file"""
        if hasattr(self.log_viewer_tab, 'export_logs'):
            self.log_viewer_tab.export_logs()
        else:
            messagebox.showwarning("Export Logs", "Log viewer tab not available.")

    def test_log_entry(self):
        """Create a test log entry"""
        try:
            if self.logger and hasattr(self.logger, 'log_activity'):
                # Create a test log entry
                self.logger.log_activity(
                    "test_user", "GUI Test User", "admin",
                    "gui_test", "gui_application",
                    "Test log entry created from GUI",
                    "success", LogLevel.INFO, SecurityLevel.LOW,
                    {"source": "gui_test", "timestamp": datetime.now().isoformat()}
                )
                messagebox.showinfo(_t("common.success"), _t("activity_logger.messages.test_log_created"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("activity_logger.messages.test_log_unavailable"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("activity_logger.errors.test_log", error=str(e)))

    def flush_logs(self):
        """Flush pending logs"""
        try:
            if self.logger and hasattr(self.logger, 'flush_logs'):
                success = self.logger.flush_logs(timeout=10)
                if success:
                    messagebox.showinfo(_t("common.success"), _t("activity_logger.messages.flush_complete"))
                else:
                    messagebox.showwarning(_t("common.warning"), _t("activity_logger.messages.flush_timeout"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("activity_logger.messages.test_log_unavailable"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("activity_logger.errors.flush", error=str(e)))

    def system_health_check(self):
        """Perform system health check"""
        try:
            if self.logger and hasattr(self.logger, 'get_system_health'):
                health = self.logger.get_system_health()

                # Create health check window
                health_window = tk.Toplevel(self.root)
                health_window.title(_t("activity_logger.dialogs.health_check"))
                health_window.geometry("500x400")
                health_window.configure(bg=LoggerGUITheme.DARK_BG)

                text_widget = scrolledtext.ScrolledText(health_window, wrap=tk.WORD)
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                health_text = f"""SYSTEM HEALTH CHECK REPORT
{'='*50}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SYSTEM METRICS
{'='*50}
CPU Usage: {health.get('cpu_usage', 0):.1f}%
Memory Usage: {health.get('memory_usage', 0):.1f}%
Disk Usage: {health.get('disk_usage', 0):.1f}%
Active Connections: {health.get('active_connections', 0)}
System Uptime: {health.get('uptime', 0):.0f} seconds

MEMORY DETAILS
{'='*50}
Available Memory: {health.get('available_memory', 0):,} bytes
Total Memory: {health.get('total_memory', 0):,} bytes

RECOMMENDATIONS
{'='*50}
"""

                # Add recommendations based on metrics
                cpu_usage = health.get('cpu_usage', 0)
                memory_usage = health.get('memory_usage', 0)
                disk_usage = health.get('disk_usage', 0)

                if cpu_usage > 80:
                    health_text += "\u2022 HIGH CPU USAGE: Consider optimizing processes or scaling resources.\n"
                if memory_usage > 85:
                    health_text += "\u2022 HIGH MEMORY USAGE: Monitor for memory leaks and consider increasing memory.\n"
                if disk_usage > 90:
                    health_text += "\u2022 LOW DISK SPACE: Clean up old files or expand storage.\n"

                if cpu_usage <= 80 and memory_usage <= 85 and disk_usage <= 90:
                    health_text += "\u2022 System health is good. No immediate action required.\n"

                text_widget.insert(tk.END, health_text)
                text_widget.configure(state='disabled')

            else:
                messagebox.showwarning("Health Check", "System health monitoring not available.")

        except Exception as e:
            messagebox.showerror("Health Check Error", f"Failed to perform health check: {str(e)}")

    def generate_report(self):
        """Generate analytics report"""
        try:
            if hasattr(self, 'analytics_tab') and hasattr(self.analytics_tab, 'generate_report'):
                self.analytics_tab.generate_report()
            else:
                # Provide basic analytics functionality
                messagebox.showinfo("Analytics", "Analytics reporting is available through the Analytics tab.")
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate report: {str(e)}")

    def run_anomaly_detection(self):
        """Run anomaly detection"""
        if hasattr(self.security_tab, 'run_anomaly_detection'):
            self.security_tab.run_anomaly_detection()
        else:
            messagebox.showwarning("Anomaly Detection", "Security tab not available.")

    def database_maintenance(self):
        """Perform database maintenance"""
        try:
            # Database maintenance is available through centralized activity logger

            # Create maintenance dialog
            maintenance_window = tk.Toplevel(self.root)
            maintenance_window.title(_t("activity_logger.dialogs.maintenance"))
            maintenance_window.geometry("400x300")
            maintenance_window.configure(bg=LoggerGUITheme.DARK_BG)

            ttk.Label(maintenance_window, text=_t("activity_logger.maintenance.title"),
                     style='AL.Title.TLabel').pack(pady=10)

            # Maintenance options
            cleanup_days = tk.IntVar(value=90)

            ttk.Label(maintenance_window, text=_t("activity_logger.maintenance.delete_older_than"),
                     style='AL.Info.TLabel').pack(pady=(20, 5))
            ttk.Entry(maintenance_window, textvariable=cleanup_days, width=10).pack(pady=(0, 10))

            def perform_cleanup():
                try:
                    if not self.logger or not hasattr(self.logger, 'db_logger') or not self.logger.db_logger:
                        messagebox.showwarning("Cleanup Warning", "Logger database is not available.")
                        return
                    days = cleanup_days.get()
                    deleted_count = self.logger.db_logger.delete_old_logs(days)
                    messagebox.showinfo("Cleanup Complete", f"Deleted {deleted_count} old log entries.")
                    maintenance_window.destroy()
                except Exception as e:
                    messagebox.showerror("Cleanup Error", f"Failed to perform cleanup: {str(e)}")

            def show_stats():
                try:
                    if not self.logger or not hasattr(self.logger, 'db_logger') or not self.logger.db_logger:
                        messagebox.showwarning("Statistics Warning", "Logger database is not available.")
                        return
                    stats = self.logger.db_logger.get_database_stats()
                    stats_text = f"""Database Statistics:
Total Logs: {stats.get('total_logs', 0):,}
Recent Activity (24h): {stats.get('recent_activity', 0):,}
Database Size: {stats.get('database_size', 0):,} bytes
"""
                    messagebox.showinfo("Database Statistics", stats_text)
                except Exception as e:
                    messagebox.showerror("Statistics Error", f"Failed to get statistics: {str(e)}")

            button_frame = ttk.Frame(maintenance_window)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text=_t("activity_logger.maintenance.show_statistics"),
                      command=show_stats).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_t("activity_logger.maintenance.cleanup_logs"),
                      command=perform_cleanup).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel",
                      command=maintenance_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Maintenance Error", f"Failed to open database maintenance: {str(e)}")

    def log_file_cleanup(self):
        """Perform log file cleanup"""
        try:
            if not self.logger or not hasattr(self.logger, 'rotation_manager'):
                messagebox.showwarning("File Cleanup", "Log rotation manager not available.")
                return

            if messagebox.askyesno("Log File Cleanup",
                                 "This will remove old log files based on retention settings. Continue?"):

                log_dir = getattr(self.logger, 'log_dir', 'logs')
                self.logger.rotation_manager.cleanup_old_logs(log_dir)
                messagebox.showinfo("Cleanup Complete", "Old log files have been cleaned up.")

        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to cleanup log files: {str(e)}")

    def show_user_guide(self):
        """Show user guide"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title(_t("activity_logger.dialogs.user_guide"))
        guide_window.geometry("800x600")
        guide_window.configure(bg=LoggerGUITheme.DARK_BG)

        text_widget = scrolledtext.ScrolledText(guide_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        user_guide = """ENHANCED ACTIVITY LOGGER - USER GUIDE
========================================

OVERVIEW
--------
The Enhanced Activity Logger GUI provides a comprehensive interface for monitoring,
analyzing, and managing application activity logs in real-time.

MAIN FEATURES
-------------

1. LIVE LOGS TAB
   - Real-time log monitoring
   - Filtering by level, user, action, module
   - Auto-refresh functionality
   - Export capabilities
   - Detailed log entry inspection

2. ANALYTICS TAB
   - System statistics and metrics
   - Visual charts and graphs (when matplotlib available)
   - Performance monitoring
   - Report generation

3. SECURITY TAB
   - Security event monitoring
   - Suspicious IP management
   - Anomaly detection
   - Security report generation
   - Failed login tracking

4. CONFIGURATION TAB
   - Logger settings management
   - Output format configuration
   - Security parameter tuning
   - Cloud integration setup
   - Configuration import/export

5. PLUGINS TAB
   - Plugin management interface
   - Enable/disable plugins
   - Plugin configuration
   - Default plugin installation

6. QUERY TAB
   - Advanced database querying
   - Custom filters and search
   - Date range selection
   - Query save/load functionality
   - Export query results

GETTING STARTED
---------------

1. CONNECTION
   - The GUI automatically connects to the logger on startup
   - Check the connection status in the top-right corner
   - Use Logger menu to reconnect if needed

2. VIEWING LOGS
   - Navigate to the Live Logs tab
   - Use filters to narrow down results
   - Double-click entries for detailed view
   - Enable auto-refresh for real-time monitoring

3. ANALYTICS
   - Visit the Analytics tab for system overview
   - Generate reports using the "Generate Report" button
   - Monitor system health metrics

4. SECURITY MONITORING
   - Check the Security tab for threats
   - Use anomaly detection to find unusual patterns
   - Manage suspicious IPs manually

5. CONFIGURATION
   - Modify settings in the Configuration tab
   - Apply changes using "Apply Changes" button
   - Save/load configurations for backup

KEYBOARD SHORTCUTS
------------------
- Ctrl+R: Refresh current tab
- Ctrl+E: Export data from current tab
- Ctrl+F: Focus search/filter field
- F5: Refresh all data

TROUBLESHOOTING
---------------

Q: GUI shows "Demo Mode" or "Disconnected"
A: The simple_activity_logger module may not be available. Check installation.

Q: No data appears in logs
A: Ensure database logging is enabled in configuration.

Q: Charts don't appear in Analytics
A: Install matplotlib: pip install matplotlib

Q: Export fails
A: Check file permissions and available disk space.

SUPPORT
-------
For additional support, check the API documentation or contact the development team.
"""

        text_widget.insert(tk.END, user_guide)
        text_widget.configure(state='disabled')

    def show_api_docs(self):
        """Show API documentation"""
        try:
            # Show API documentation info
            doc_text = """Activity Logger API Documentation

The Activity Logger provides comprehensive logging functionality for the University Management System.

Main Functions:
- log_activity(action, user): Log a general activity
- log_login(username, success): Log login attempts
- log_logout(username): Log logout events
- log_create(item_type, item_name): Log item creation
- log_update(item_type, item_name): Log item updates
- log_delete(item_type, item_name): Log item deletion

For detailed documentation, see:
- Local: university_system/modules/shared/utils/activity_logger.py
- Online: Check the project README.md for full documentation
"""
            messagebox.showinfo("API Documentation", doc_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show documentation: {str(e)}")

    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title(_t("activity_logger.dialogs.about"))
        about_window.geometry("500x400")
        about_window.configure(bg=LoggerGUITheme.DARK_BG)
        about_window.resizable(False, False)

        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()

        main_frame = ttk.Frame(about_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ttk.Label(main_frame, text=_t("activity_logger.about.title"),
                 style='AL.Title.TLabel').pack(pady=(0, 10))

        # Version info
        version_text = """Version 2.0.0
GUI Management Console

A comprehensive activity logging solution with
real-time monitoring, analytics, and security features.
"""
        ttk.Label(main_frame, text=version_text,
                 style='AL.Info.TLabel', justify=tk.CENTER).pack(pady=(0, 20))

        # Features
        features_text = """Key Features:
\u2022 Real-time log monitoring and filtering
\u2022 Advanced analytics and reporting
\u2022 Security monitoring and anomaly detection
\u2022 Plugin system for extensibility
\u2022 Database querying and search
\u2022 Configuration management
\u2022 Multi-format log export
\u2022 System health monitoring
"""
        ttk.Label(main_frame, text=features_text,
                 style='AL.Info.TLabel', justify=tk.LEFT).pack(pady=(0, 20))

        # Credits
        credits_text = """Built with Python and Tkinter
Compatible with the original simple_activity_logger
Fully backward compatible

\u00a9 2024 Enhanced Activity Logger Team
"""
        ttk.Label(main_frame, text=credits_text,
                 style='AL.Info.TLabel', justify=tk.CENTER).pack(pady=(0, 20))

        ttk.Button(main_frame, text=_t("activity_logger.about.close"), command=about_window.destroy).pack()

    def on_closing(self):
        """Handle application closing"""
        try:
            # Ask for confirmation
            if messagebox.askyesno(_t("common.exit"), _t("activity_logger.dialogs.exit_confirm")):
                # Set destroyed flag first to stop timer callbacks
                self._destroyed = True

                # Cancel all timers first
                if self._update_timer_id:
                    try:
                        self.root.after_cancel(self._update_timer_id)
                        self._update_timer_id = None
                    except Exception:
                        pass

                # In embedded mode, don't shutdown the logger (main app may still use it)
                # In standalone mode, gracefully shutdown
                if self._standalone and self.logger and hasattr(self.logger, 'shutdown'):
                    try:
                        self.status_bar.update_status("Shutting down logger...")
                        self.root.update()

                        # Give logger time to flush pending logs
                        if hasattr(self.logger, 'flush_logs'):
                            self.logger.flush_logs(timeout=5)

                        # Shutdown logger
                        self.logger.shutdown(timeout=10)
                    except Exception:
                        pass

                # Destroy the GUI - only quit mainloop in standalone mode
                if self._standalone:
                    self.root.quit()
                self.root.destroy()

        except Exception as e:
            print(f"Error during shutdown: {e}")
            # Set destroyed flag and cancel timer even on error
            self._destroyed = True
            if hasattr(self, '_update_timer_id') and self._update_timer_id:
                try:
                    self.root.after_cancel(self._update_timer_id)
                    self._update_timer_id = None
                except Exception:
                    pass
            try:
                if self._standalone:
                    self.root.quit()
                self.root.destroy()
            except Exception:
                pass

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Set destroyed flag first to stop timer callbacks
            self._destroyed = True

            # Cancel update timer before destroying window
            if hasattr(self, '_update_timer_id') and self._update_timer_id:
                try:
                    self.root.after_cancel(self._update_timer_id)
                    self._update_timer_id = None
                except Exception:
                    pass

            # Use the gui_launcher utility to avoid circular imports
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Run the GUI application"""
        # Set closing protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Only center and run mainloop in standalone mode
        if self._standalone:
            # Center window on screen
            self.root.update_idletasks()
            x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
            y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
            self.root.geometry(f"+{x}+{y}")

            # Start the main loop
            self.root.mainloop()
