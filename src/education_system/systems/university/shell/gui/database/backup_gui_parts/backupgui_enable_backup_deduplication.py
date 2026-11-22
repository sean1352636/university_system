"""Methods enable_backup_deduplication through run_backup_operation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from education_system.platform.delivery.gui.tk_threads import start_thread, ui


class BackupGUI:
    def enable_backup_deduplication():
        """Enable backup deduplication - missing from GUI"""
        try:
            logger.info("Enabling backup deduplication")
            config["enable_deduplication"] = True
            save_config()

            removed = deduplicate_backups()
            if removed:
                logger.info(f"Deduplication removed {removed} duplicate backup(s).")
            else:
                logger.info("No duplicate backups detected during deduplication.")
            return True
        except Exception as e:
            logger.error(f"Error enabling deduplication: {e}")
            return False

    def deduplicate_backups():
        """Remove duplicate backup files - missing from GUI"""
        try:
            if not config.get("enable_deduplication", False):
                return 0

            backups = list_available_backups()
            duplicates_removed = 0

            # Group backups by hash
            hash_groups = {}
            for backup in backups:
                file_hash = backup.get("file_hash")
                if file_hash:
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(backup)

            # Remove duplicates (keep the newest)
            for file_hash, backup_group in hash_groups.items():
                if len(backup_group) > 1:
                    # Sort by timestamp, keep the newest
                    backup_group.sort(key=lambda x: x["timestamp"], reverse=True)
                    for duplicate in backup_group[1:]:  # Skip the first (newest)
                        try:
                            # Use centralized delete_backup function
                            try:
                                from education_system.systems.university.infrastructure.database.data_backup import delete_backup as delete_backup_func
                                if delete_backup_func(duplicate["path"]):
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")
                            except ImportError:
                                # Fallback implementation
                                if os.path.exists(duplicate["path"]):
                                    os.remove(duplicate["path"])
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")

                                # Remove from metadata
                                metadata_manager.metadata["backups"] = [
                                    b for b in metadata_manager.metadata["backups"]
                                    if b["path"] != duplicate["path"]
                                ]
                                metadata_manager.save_metadata()
                        except Exception as e:
                            logger.error(f"Error removing duplicate {duplicate['filename']}: {e}")

            return duplicates_removed

        except Exception as e:
            logger.error(f"Error during deduplication: {e}")
            return 0

    def check_storage_quota():
        """Check if storage quota is exceeded - missing from GUI"""
        try:
            quota_gb = config.get("storage_quota_gb", 10)
            quota_bytes = quota_gb * 1024 * 1024 * 1024

            # Calculate total backup size
            total_size = 0
            backup_dir = Path(config["backup_directory"])

            if backup_dir.exists():
                for file_path in backup_dir.glob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size

            usage_percentage = (total_size / quota_bytes) * 100 if quota_bytes > 0 else 0

            return {
                "total_size_bytes": total_size,
                "total_size_gb": total_size / (1024**3),
                "quota_gb": quota_gb,
                "quota_bytes": quota_bytes,
                "usage_percentage": usage_percentage,
                "quota_exceeded": total_size > quota_bytes
            }

        except Exception as e:
            logger.error(f"Error checking storage quota: {e}")
            return {"quota_exceeded": False, "usage_percentage": 0}

    def show_storage_usage(self):
        """Show storage usage dialog - missing method"""
        StorageUsageDialog(self.root)

    def export_logs(self):
        """Export logs to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.success', default="Success"), f"Logs exported to {filename}")
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.error', default="Error"), f"Failed to export logs: {e}")

    def filter_logs(self, event=None):
        """Filter logs by level"""
        try:
            log_file = get_log_file('backup.log')
            if not os.path.exists(log_file):
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
                return

            with open(log_file, 'r') as f:
                lines = f.readlines()

            selected_level = self.log_level_var.get()
            if selected_level == "All":
                filtered_lines = lines
            else:
                pattern = re.compile(rf'\\b{selected_level}\\b', re.IGNORECASE)
                filtered_lines = [line for line in lines if pattern.search(line)]

            self.log_text.delete(1.0, tk.END)
            if filtered_lines:
                self.log_text.insert(1.0, "".join(filtered_lines))
            else:
                self.log_text.insert(1.0, f"No log entries found for level {selected_level}.")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error filtering logs: {e}")

    def list_available_backups(filter_type=None, search_term=None):
        """List all available backup files with enhanced filtering - missing from GUI"""
        try:
            backups = metadata_manager.get_backups()

            # Apply filters
            if filter_type:
                backups = [b for b in backups if b.get("backup_type") == filter_type]

            if search_term:
                backups = [b for b in backups if search_term.lower() in b["filename"].lower()]

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)

            # Add calculated fields
            for i, backup in enumerate(backups):
                backup["id"] = i + 1

                # Format size
                size_bytes = backup.get("size", 0)
                if size_bytes > 1024*1024*1024:
                    backup["size_formatted"] = f"{size_bytes/(1024*1024*1024):.2f} GB"
                elif size_bytes > 1024*1024:
                    backup["size_formatted"] = f"{size_bytes/(1024*1024):.2f} MB"
                else:
                    backup["size_formatted"] = f"{size_bytes/1024:.2f} KB"

                # Format date
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    backup["date_formatted"] = backup_date.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, KeyError):
                    backup["date_formatted"] = "Unknown"

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    def run_backup_operation(self, operation, status_message):
        """Run backup operation in separate thread"""
        def run_operation():
            try:
                ui(self.root, self.status_var.set, status_message)
                ui(self.root, self.progress_var.set, 0)

                result = operation()

                if result:
                    def _done(result=result):
                        self.status_var.set("Backup completed successfully")
                        self.refresh_backup_list()
                        messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.success', default="Success"), f"Backup created: {os.path.basename(result)}")
                    ui(self.root, _done)
                else:
                    def _failed():
                        self.status_var.set("Backup failed")
                        messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.error', default="Error"), _t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.backup_operation_failed', default="Backup operation failed"))
                    ui(self.root, _failed)

            except Exception as e:
                def _error(e=e):
                    self.status_var.set("Backup failed")
                    messagebox.showerror(_t('gui.shell.database.backup_gui_parts.backupgui_enable_backup_deduplication.dialogs.error', default="Error"), f"Backup operation failed: {e}")
                ui(self.root, _error)
            finally:
                ui(self.root, self.progress_var.set, 0)

        # Run in separate thread to prevent GUI freezing
        start_thread(self.root, run_operation)
