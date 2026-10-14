"""Methods create_logs_tab through upload_backup_gui."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
import tkinter.simpledialog  # noqa: F401 - registers tk.simpledialog
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class BackupGUI:
    def create_logs_tab(self):
        """Create the logs and monitoring tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text=_t("backup.tab_logs", default="Logs"))

        # Log controls
        controls_frame = ttk.Frame(logs_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("backup.refresh_logs", default="Refresh Logs"),
                  command=self.refresh_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t("backup.clear_logs", default="Clear Logs"),
                  command=self.clear_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t("backup.export_logs", default="Export Logs"),
                  command=self.export_logs).pack(side="left", padx=5)

        # Log level filter
        ttk.Label(controls_frame, text=_t("backup.filter", default="Filter:")).pack(side="left", padx=(20, 5))
        self.log_level_var = tk.StringVar(value=_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.values.all', default="All"))
        level_combo = ttk.Combobox(controls_frame, textvariable=self.log_level_var,
                                 values=["All", "ERROR", "WARNING", "INFO", "DEBUG"],
                                 state="readonly", width=10)
        level_combo.pack(side="left", padx=5)
        level_combo.bind("<<ComboboxSelected>>", self.filter_logs)

        # Log display
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=25, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Load initial logs
        self.refresh_logs()

    def create_status_bar(self):
        """Create the status bar"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")

        # Status label
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief="sunken")
        status_label.pack(side="left", fill="x", expand=True)

        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var,
                                          length=200, mode="determinate")
        self.progress_bar.pack(side="right", padx=5, pady=2)

    def setup_logging(self):
        """
        Setup logging to capture log messages in GUI

        Configures a queue handler to capture log messages from the backup
        operations and display them in the GUI's log text widget.
        This allows real-time monitoring of backup activities in the interface.
        """
        try:
            # Create a custom handler that writes to the log queue
            class QueueHandler(logging.Handler):
                def __init__(self, log_queue):
                    super().__init__()
                    self.log_queue = log_queue

                def emit(self, record):
                    try:
                        # Format the log record
                        msg = self.format(record)
                        self.log_queue.put(msg)
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)

            # Create and configure the queue handler
            queue_handler = QueueHandler(self.log_queue)
            queue_handler.setLevel(logging.DEBUG)

            # Set formatter
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            queue_handler.setFormatter(formatter)

            # Add handler to logger
            logger.addHandler(queue_handler)

            # Start monitoring the log queue
            self.monitor_logs()

        except Exception as e:
            print(f"Warning: Could not setup GUI logging: {e}")

    def monitor_logs(self):
        """Monitor log queue for new messages"""
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        try:
            while True:
                record = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{record}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        except tk.TclError:
            # Widget torn down between get_nowait() and insert(); stop.
            return

        # Schedule next check
        try:
            self.root.after(1000, self.monitor_logs)
        except tk.TclError:
            return

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.systems.university.shell.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def create_manual_backup(self):
        """Create a manual backup with options"""
        dialog = BackupOptionsDialog(self.root)
        if dialog.result:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True,
                    backup_type=dialog.backup_type,
                    tables=dialog.selected_tables
                ),
                "Creating manual backup..."
            )

    def quick_backup(self):
        """Create a quick full backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True),
            "Creating quick backup..."
        )

    def view_backups(self):
        """Open backup viewer dialog"""
        BackupViewerDialog(self.root)

    def restore_backup(self):
        """Open restore dialog"""
        RestoreDialog(self.root, self.refresh_backup_list)

    def validate_backup_gui(self):
        """Open backup validation dialog"""
        ValidationDialog(self.root)

    def export_backup_gui(self):
        """Open backup export dialog"""
        ExportDialog(self.root)

    def create_incremental_backup(self):
        """Create incremental backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="incremental"),
            "Creating incremental backup..."
        )

    def create_selective_backup(self):
        """Create selective table backup"""
        tables = get_database_tables()
        dialog = TableSelectionDialog(self.root, tables)
        if dialog.selected_tables:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True,
                    backup_type="selective",
                    tables=dialog.selected_tables
                ),
                "Creating selective backup..."
            )

    def create_schema_backup(self):
        """Create schema-only backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="schema"),
            "Creating schema backup..."
        )

    def save_template_gui(self):
        """Save current configuration as template"""
        name = tk.simpledialog.askstring("Save Template", "Enter template name:")
        if name:
            # Get current configuration
            self.save_configuration()  # Save current GUI settings to config
            template_config = {k: v for k, v in config.items() if k != "backup_templates"}

            if save_backup_template(name, template_config):
                messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.success', default="Success"), f"Template '{name}' saved successfully!")
            else:
                messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.error', default="Error"), _t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.failed_to_save_template', default="Failed to save template"))

    def load_template_gui(self):
        """Load configuration from template"""
        # Use new list_backup_templates function to get all templates
        templates = list_backup_templates()
        if not templates:
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.no_templates', default="No Templates"), _t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.no_templates_available', default="No templates available"))
            return

        dialog = TemplateSelectionDialog(self.root, list(templates.keys()), templates)
        if dialog.selected_template:
            if load_backup_template(dialog.selected_template):
                self.refresh_config_gui()
                messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.success', default="Success"), f"Template '{dialog.selected_template}' loaded!")
            else:
                messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.error', default="Error"), _t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.failed_to_load_template', default="Failed to load template"))

    def manage_templates_gui(self):
        """Open template management dialog"""
        TemplateManagerDialog(self.root)

    def toggle_scheduling(self):
        """Toggle backup scheduling"""
        config["auto_backup_enabled"] = not config["auto_backup_enabled"]

        if config["auto_backup_enabled"]:
            start_scheduler()
            self.schedule_btn.config(text=_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.text.disable_scheduling', default="Disable Scheduling"))
        else:
            stop_scheduler()
            self.schedule_btn.config(text=_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.text.enable_scheduling', default="Enable Scheduling"))

        self.update_schedule_status()
        save_config()

    def configure_schedule_gui(self):
        """Open schedule configuration dialog"""
        ScheduleConfigDialog(self.root, self.update_schedule_status)

    def browse_backup_dir(self):
        """Browse for backup directory"""
        directory = filedialog.askdirectory(initialdir=self.backup_dir_var.get())
        if directory:
            self.backup_dir_var.set(directory)

    def toggle_encryption(self):
        """Toggle encryption settings"""
        if self.encryption_var.get() and not self.encryption_pass_var.get():
            password = tk.simpledialog.askstring("Encryption Password",
                                                "Enter encryption password:", show="*")
            if password:
                self.encryption_pass_var.set(password)
            else:
                self.encryption_var.set(False)

    def toggle_email_notifications(self):
        """Toggle email notifications"""
        if self.email_notify_var.get():
            self.configure_email_gui()

    def configure_email_gui(self):
        """Configure email settings"""
        EmailConfigDialog(self.root)

    def configure_webhooks_gui(self):
        """Configure webhook settings"""
        WebhookConfigDialog(self.root)

    def toggle_cloud_storage(self):
        """
        Toggle cloud storage

        Enables or disables cloud storage settings based on the cloud storage toggle.
        When enabled, activates AWS S3 configuration fields. When disabled, disables
        them to prevent accidental misconfiguration.
        """
        if self.cloud_enabled_var.get():
            # Enable AWS settings
            try:
                # Enable all AWS-related entry widgets
                if hasattr(self, 'aws_bucket_entry'):
                    self.aws_bucket_entry.config(state='normal')
                if hasattr(self, 'aws_access_entry'):
                    self.aws_access_entry.config(state='normal')
                if hasattr(self, 'aws_secret_entry'):
                    self.aws_secret_entry.config(state='normal')
                if hasattr(self, 'aws_region_combo'):
                    self.aws_region_combo.config(state='readonly')

                # Update status
                self.status_var.set("Cloud storage enabled - configure AWS S3 settings")

            except AttributeError:
                # Widgets not yet created, that's ok
                pass
        else:
            # Disable AWS settings
            try:
                # Disable all AWS-related entry widgets
                if hasattr(self, 'aws_bucket_entry'):
                    self.aws_bucket_entry.config(state='disabled')
                if hasattr(self, 'aws_access_entry'):
                    self.aws_access_entry.config(state='disabled')
                if hasattr(self, 'aws_secret_entry'):
                    self.aws_secret_entry.config(state='disabled')
                if hasattr(self, 'aws_region_combo'):
                    self.aws_region_combo.config(state='disabled')

                # Update status
                self.status_var.set("Cloud storage disabled - backups will be stored locally only")

            except AttributeError:
                # Widgets not yet created, that's ok
                pass

    def save_configuration(self):
        """Save all configuration settings"""
        try:
            # Update config from GUI
            config["backup_directory"] = self.backup_dir_var.get()
            config["max_backups"] = int(self.max_backups_var.get())
            config["auto_backup_enabled"] = self.auto_backup_var.get()
            config["encryption_enabled"] = self.encryption_var.get()
            config["encryption_password"] = self.encryption_pass_var.get()
            config["secure_deletion"] = self.secure_delete_var.get()
            config["verify_integrity"] = self.verify_integrity_var.get()
            config["compression_enabled"] = self.compression_var.get()
            config["compression_format"] = self.compression_format_var.get()
            config["compression_level"] = int(self.compression_level_var.get())
            config["email_notifications"] = self.email_notify_var.get()
            config["cloud_enabled"] = self.cloud_enabled_var.get()
            config["aws_bucket"] = self.aws_bucket_var.get()
            config["aws_access_key"] = self.aws_access_var.get()
            config["aws_secret_key"] = self.aws_secret_var.get()
            config["aws_region"] = self.aws_region_var.get()
            config["remote_enabled"] = self.remote_enabled_var.get()
            config["remote_type"] = self.remote_type_var.get()
            config["remote_host"] = self.remote_host_var.get()
            config["remote_username"] = self.remote_user_var.get()
            config["remote_password"] = self.remote_pass_var.get()

            save_config()

            # Restart scheduler if needed
            if config["auto_backup_enabled"]:
                stop_scheduler()
                start_scheduler()

            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.success', default="Success"), _t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.configuration_saved_successfully', default="Configuration saved successfully!"))

        except ValueError as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.error', default="Error"), f"Invalid configuration value: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.error', default="Error"), f"Failed to save configuration: {e}")

    def refresh_config_gui(self):
        """Refresh GUI with current configuration"""
        self.backup_dir_var.set(config["backup_directory"])
        self.max_backups_var.set(str(config["max_backups"]))
        self.auto_backup_var.set(config["auto_backup_enabled"])
        self.encryption_var.set(config["encryption_enabled"])
        self.encryption_pass_var.set(config["encryption_password"])
        self.secure_delete_var.set(config["secure_deletion"])
        self.verify_integrity_var.set(config["verify_integrity"])
        self.compression_var.set(config["compression_enabled"])
        self.compression_format_var.set(config["compression_format"])
        self.compression_level_var.set(str(config["compression_level"]))
        self.email_notify_var.set(config["email_notifications"])
        self.cloud_enabled_var.set(config["cloud_enabled"])
        self.aws_bucket_var.set(config["aws_bucket"])
        self.aws_access_var.set(config["aws_access_key"])
        self.aws_secret_var.set(config["aws_secret_key"])
        self.aws_region_var.set(config["aws_region"])
        self.remote_enabled_var.set(config["remote_enabled"])
        self.remote_type_var.set(config["remote_type"])
        self.remote_host_var.set(config["remote_host"])
        self.remote_user_var.set(config["remote_username"])
        self.remote_pass_var.set(config["remote_password"])

    def compare_backups_gui(self):
        """Open backup comparison dialog"""
        ComparisonDialog(self.root)

    def generate_statistics_gui(self):
        """Generate and display statistics"""
        self.refresh_statistics()

    def generate_report_gui(self):
        """Generate comprehensive backup report"""
        ReportDialog(self.root)

    def refresh_statistics(self):
        """Refresh statistics display"""
        try:
            stats = generate_backup_statistics()

            stats_text = "BACKUP STATISTICS REPORT\n"
            stats_text += "=" * 40 + "\n\n"
            stats_text += f"Total Backups: {stats['total_backups']}\n"
            stats_text += f"Total Size: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
            stats_text += f"Average Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
            stats_text += f"Recent Activity (30 days): {stats['recent_activity']} backups\n\n"

            if stats['backup_types']:
                stats_text += "Backup Types:\n"
                for backup_type, count in stats['backup_types'].items():
                    stats_text += f"  {backup_type}: {count}\n"
                stats_text += "\n"

            if stats['storage_usage']:
                stats_text += "Monthly Storage Usage:\n"
                for month, size in sorted(stats['storage_usage'].items()):
                    stats_text += f"  {month}: {size / (1024*1024):.2f} MB\n"

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_text)

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, f"Error generating statistics: {e}")

    def upload_backup_gui(self):
        """Upload backup to cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.cloud_storage', default="Cloud Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_create_logs_tab.dialogs.cloud_storage_is_not_configured', default="Cloud storage is not configured"))
            return

        UploadDialog(self.root)
