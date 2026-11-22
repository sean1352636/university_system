"""Methods download_backup_gui through test_schedule."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system import paths as _paths

from .. import backup_gui_shared as _shared
import tkinter.simpledialog  # noqa: F401 - registers tk.simpledialog
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

from education_system.platform.delivery.gui.tk_threads import start_thread, ui


class BackupGUI:
    def download_backup_gui(self):
        """Download backup from cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.cloud_storage', default="Cloud Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.cloud_storage_is_not_configured', default="Cloud storage is not configured"))
            return

        DownloadDialog(self.root)

    def sync_storage_gui(self):
        """Sync with remote storage"""
        if not config["remote_enabled"]:
            messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_storage', default="Remote Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_storage_is_not_configured', default="Remote storage is not configured"))
            return

        host = self.remote_host_var.get().strip()
        username = self.remote_user_var.get().strip()
        password = self.remote_pass_var.get().strip()
        remote_type = self.remote_type_var.get()
        remote_path = config.get("remote_path", _paths.UNIVERSITY_REMOTE_BACKUP_PATH)

        if not host or not username or not password:
            messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_storage', default="Remote Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.please_provide_host_username_and_password_for_remote_storage', default="Please provide host, username, and password for remote storage."))
            return

        backups = list_available_backups()
        if not backups:
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_storage', default="Remote Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.no_backups_available_to_sync', default="No backups available to sync."))
            return

        to_sync = [b for b in backups if not b.get("remote_uploaded", False)]
        if not to_sync:
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_storage', default="Remote Storage"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.all_backups_are_already_synced_with_the_remote_location', default="All backups are already synced with the remote location."))
            return

        # Persist the latest credentials in config
        config["remote_host"] = host
        config["remote_username"] = username
        config["remote_password"] = password

        def update_status(progress, status_text):
            self.progress_var.set(progress)
            self.status_var.set(status_text)

        def finish_sync(successes, failures):
            self.progress_var.set(0)
            self.status_var.set("Remote sync complete")

            if successes:
                message = f"Synchronized {len(successes)} backup(s) successfully."
            else:
                message = "No backups were synchronized."

            if failures:
                message += "\n\nFailed uploads:\n" + "\n".join(
                    f"- {item['filename']}: {reason}" for item, reason in failures
                )

            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.remote_sync', default="Remote Sync"), message)
            self.refresh_backup_list()

        def sync_worker():
            successes = []
            failures = []
            total = len(to_sync)

            for index, backup in enumerate(to_sync, start=1):
                progress = (index - 1) / total * 100
                ui(self.root, update_status, progress, f"Uploading {backup['filename']} ({index}/{total})")

                remote_target = posixpath.join(remote_path.rstrip('/'), backup['filename'])

                try:
                    if remote_type == "ftp":
                        result = upload_to_ftp(
                            backup["path"], host, username, password, remote_target
                        )
                    else:
                        result = upload_to_sftp(
                            backup["path"], host, username, password, remote_target
                        )
                except Exception as exc:
                    result = False
                    failures.append((backup, str(exc)))
                else:
                    if result:
                        successes.append(backup)
                        for record in metadata_manager.metadata["backups"]:
                            if record["path"] == backup["path"]:
                                record["remote_uploaded"] = True
                                break
                    else:
                        failures.append((backup, "Upload failed"))

                ui(self.root, update_status, index / total * 100, f"Processed {index}/{total} backups")

            metadata_manager.save_metadata()
            ui(self.root, finish_sync, successes, failures)

        start_thread(self.root, sync_worker)

    def refresh_logs(self):
        """Refresh log display"""
        try:
            log_file = get_log_file('backup.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = f.read()

                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, logs)
                self.log_text.see(tk.END)
            else:
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error loading logs: {e}")

    def clear_logs(self):
        """Clear log display and file"""
        if messagebox.askyesno(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.clear_logs', default="Clear Logs"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.are_you_sure_you_want_to_clear_all_logs', default="Are you sure you want to clear all logs?")):
            try:
                log_file = get_log_file('backup.log')
                if os.path.exists(log_file):
                    open(log_file, 'w').close()
                self.log_text.delete(1.0, tk.END)
                messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.success', default="Success"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.logs_cleared_successfully', default="Logs cleared successfully"))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.error', default="Error"), f"Failed to clear logs: {e}")

    def create_differential_backup(self):
        """Create differential backup - missing method"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="differential"),
            "Creating differential backup..."
        )

    def refresh_backup_list(self):
        """Refresh the backup list in main tab"""
        try:
            # Clear existing items
            for item in self.backup_tree.get_children():
                self.backup_tree.delete(item)

            # Get backup list
            backups = list_available_backups()

            # Populate tree
            for backup in backups[:20]:  # Show last 20 backups
                status = "\u2713" if os.path.exists(backup['path']) else "\u2717"
                encrypted = "\U0001f512" if backup.get('encrypted', False) else ""
                cloud = "\u2601" if backup.get('cloud_uploaded', False) else ""

                self.backup_tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    f"{status} {encrypted} {cloud}"
                ))

        except Exception as e:
            logger.error(f"Error refreshing backup list: {e}")

    def auto_refresh_backup_list(self):
        """Auto-refresh backup list every 30 seconds"""
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        self.refresh_backup_list()
        self.root.after(30000, self.auto_refresh_backup_list)

    def configure_advanced_settings(self):
        """Configure advanced backup settings - missing method"""
        AdvancedSettingsDialog(self.root)

    def backup_database_specific_settings(self):
        """Configure database-specific backup settings - missing method"""
        DatabaseSettingsDialog(self.root)

    def create_backup_report(self):
        """Create comprehensive backup report - missing method"""
        ReportGeneratorDialog(self.root)

    def backup_integrity_check(self):
        """Run integrity check on all backups - missing method"""
        IntegrityCheckDialog(self.root)

    def backup_migration_tools(self):
        """Tools for migrating backups between storage types - missing method"""
        MigrationToolsDialog(self.root)

    def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
        """Enhanced backup creation with all new features - missing from GUI"""
        try:
            # Check if database has changed (if change detection is enabled)
            if config.get("enable_change_detection", False) and not manual and not has_database_changed():
                logger.info("No changes detected since last backup. Skipping backup.")
                return None

            # Ensure backup directory exists
            backup_dir = ensure_backup_directory()

            # Generate backup filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            if operation_name:
                filename = f"student_records_before_{operation_name}_{timestamp}.db"
            elif manual:
                filename = f"student_records_manual_{backup_type}_{timestamp}.db"
            else:
                filename = f"student_records_scheduled_{backup_type}_{timestamp}.db"

            backup_path = backup_dir / filename

            # Check if source database exists (use DEFAULT_DB_PATH from db module)
            db_path = DEFAULT_DB_PATH
            if not os.path.exists(str(db_path)):
                logger.warning(f"Database file not found at {db_path}. Nothing to backup.")
                messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.backup_error', default="Backup Error"), f"Database file not found at:\n{db_path}\n\nPlease ensure the database exists before creating a backup.")
                return None

            logger.info(f"Creating backup from database: {db_path}")

            # Create backup based on type
            success = False
            if backup_type == "schema":
                success = create_schema_only_backup(str(backup_path))
            elif backup_type == "selective" and tables:
                success = create_selective_backup(tables, str(backup_path))
            elif backup_type == "incremental":
                success = create_incremental_backup(str(backup_path))
            elif backup_type == "differential":
                success = create_differential_backup(str(backup_path))
            else:  # full backup
                shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
                success = True

            if not success:
                logger.error("Backup creation failed")
                return None

            # Calculate file hash for integrity
            file_hash = calculate_file_hash(str(backup_path))

            # Compress if enabled
            if config.get("compression_enabled", False):
                compressed_path = compress_file(
                    str(backup_path),
                    config.get("compression_format", "gzip"),
                    config.get("compression_level", 6)
                )
                if compressed_path:
                    backup_path = Path(compressed_path)

            # Encrypt if enabled
            if config.get("encryption_enabled", False) and config.get("encryption_password"):
                encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
                if encrypted_path:
                    backup_path = Path(encrypted_path)

            # Upload to cloud/remote if enabled
            upload_success = True
            if config.get("cloud_enabled", False):
                if config.get("cloud_provider") == "aws":
                    upload_success = upload_to_aws_s3(
                        str(backup_path),
                        config.get("aws_bucket", ""),
                        f"backups/{backup_path.name}"
                    )

            if config.get("remote_enabled", False):
                if config.get("remote_type") == "ftp":
                    upload_success = upload_to_ftp(
                        str(backup_path),
                        config.get("remote_host", ""),
                        config.get("remote_username", ""),
                        config.get("remote_password", ""),
                        config.get("remote_path", _paths.UNIVERSITY_REMOTE_BACKUP_PATH)
                    )
                elif config.get("remote_type") == "sftp":
                    upload_success = upload_to_sftp(
                        str(backup_path),
                        config.get("remote_host", ""),
                        config.get("remote_username", ""),
                        config.get("remote_password", ""),
                        config.get("remote_path", _paths.UNIVERSITY_REMOTE_BACKUP_PATH)
                    )

            # Record backup metadata
            backup_info = {
                "path": str(backup_path),
                "filename": backup_path.name,
                "type": backup_type,
                "manual": manual,
                "operation": operation_name,
                "timestamp": timestamp,
                "size": os.path.getsize(backup_path),
                "file_hash": file_hash,
                "compressed": config.get("compression_enabled", False),
                "encrypted": config.get("encryption_enabled", False),
                "cloud_uploaded": config.get("cloud_enabled", False) and upload_success,
                "remote_uploaded": config.get("remote_enabled", False) and upload_success,
                "backup_type": backup_type
            }

            # Thread-safe read of backup context
            with cfg._backup_context_lock:
                if backup_type == "incremental" and cfg._last_incremental_context:
                    backup_info.update(cfg._last_incremental_context.copy())
                if backup_type == "differential" and cfg._last_differential_context:
                    backup_info.update(cfg._last_differential_context.copy())

            metadata_manager.add_backup(backup_info)

            logger.info(f"Backup created: {backup_path}")

            # Clean up old backups
            cleanup_old_backups()

            # Send notifications
            notify_backup_result(True, str(backup_path), f"{backup_type} backup")

            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            notify_backup_result(False, "", f"{backup_type} backup")
            return None

    def import_template_gui(self):
        """Import template from file - missing method"""
        file_path = filedialog.askopenfilename(
            title=_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.import_template', default="Import Template"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    template_data = json.load(f)

                name = tk.simpledialog.askstring("Template Name", "Enter name for imported template:")
                if name and save_backup_template(name, template_data):
                    messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.success', default="Success"), f"Template '{name}' imported successfully!")
                else:
                    messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.error', default="Error"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.failed_to_import_template', default="Failed to import template"))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.error', default="Error"), f"Failed to import template: {e}")

    def export_template_gui(self):
        """Export template to file - missing method"""
        templates = config.get("backup_templates", {})
        if not templates:
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.no_templates', default="No Templates"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.no_templates_available_to_export', default="No templates available to export"))
            return

        dialog = TemplateSelectionDialog(self.root, list(templates.keys()))
        if dialog.selected_template:
            file_path = filedialog.asksaveasfilename(
                title=_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.export_template', default="Export Template"),
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )

            if file_path:
                try:
                    template_data = templates[dialog.selected_template]
                    with open(file_path, 'w') as f:
                        json.dump(template_data, f, indent=4)
                    messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.success', default="Success"), f"Template exported to {file_path}")
                except Exception as e:
                    messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.error', default="Error"), f"Failed to export template: {e}")

    def show_schedule_history(self):
        """Show scheduling history - missing method"""
        ScheduleHistoryDialog(self.root)

    def test_schedule(self):
        """Test schedule configuration - missing method"""
        if not config["auto_backup_enabled"]:
            messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.schedule_disabled', default="Schedule Disabled"), _t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.automatic_backup_scheduling_is_currently_disabled', default="Automatic backup scheduling is currently disabled."))
            return

        # Calculate next scheduled run
        try:
            current_time = datetime.datetime.now()
            scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()

            today_scheduled = datetime.datetime.combine(current_time.date(), scheduled_time)
            if today_scheduled <= current_time:
                # If today's time has passed, show tomorrow's schedule
                tomorrow = current_time.date() + datetime.timedelta(days=1)
                next_run = datetime.datetime.combine(tomorrow, scheduled_time)
            else:
                next_run = today_scheduled

            frequency = config["backup_frequency"]
            message = "Schedule Configuration Test:\n\n"
            message += f"Frequency: {frequency.title()}\n"
            message += f"Time: {config['scheduled_backup_time']}\n"
            message += f"Next Run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Status: {'Active' if cfg.scheduler_running else 'Inactive'}\n"

            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.schedule_test', default="Schedule Test"), message)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_download_backup.dialogs.error', default="Error"), f"Schedule test failed: {e}")
