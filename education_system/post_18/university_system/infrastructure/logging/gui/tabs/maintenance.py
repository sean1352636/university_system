import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import time
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.paths import LOG_DIR
from education_system.post_18.university_system.infrastructure.logging.gui.helpers import _t
from education_system.post_18.university_system.infrastructure.logging.log_management.security import LogSecurity


class MaintenanceMixin:
    """Mixin providing maintenance tab functionality."""

    def setup_maintenance_tab(self):
        """Setup the maintenance tab"""
        self.maintenance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.maintenance_frame, text="🔧 " + _t("log_management.tabs.maintenance"))

        # Database section
        db_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.db_maintenance"))
        db_frame.pack(fill=tk.X, padx=10, pady=5)

        db_button_frame = ttk.Frame(db_frame)
        db_button_frame.pack(padx=10, pady=10)

        ttk.Button(db_button_frame, text="📊 " + _t("log_management.maintenance.buttons.db_info"),
                  command=self.show_database_info).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="⚡ " + _t("log_management.maintenance.buttons.optimize"),
                  command=self.optimize_database).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="🧹 " + _t("log_management.maintenance.buttons.vacuum"),
                  command=self.vacuum_database).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="🔍 " + _t("log_management.maintenance.buttons.integrity_check"),
                  command=self.run_integrity_check).pack(side=tk.LEFT)

        # Archive section
        archive_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.archive_management"))
        archive_frame.pack(fill=tk.X, padx=10, pady=5)

        archive_button_frame = ttk.Frame(archive_frame)
        archive_button_frame.pack(padx=10, pady=10)

        ttk.Button(archive_button_frame, text="📦 " + _t("log_management.maintenance.archive_buttons.archive_old"),
                  command=self.archive_old_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(archive_button_frame, text="🗑️ " + _t("log_management.maintenance.archive_buttons.cleanup_old"),
                  command=self.cleanup_old_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(archive_button_frame, text="📁 " + _t("log_management.maintenance.archive_buttons.view_archives"),
                  command=self.view_archives).pack(side=tk.LEFT)

        # Performance section
        perf_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.performance_testing"))
        perf_frame.pack(fill=tk.X, padx=10, pady=5)

        perf_button_frame = ttk.Frame(perf_frame)
        perf_button_frame.pack(padx=10, pady=10)

        ttk.Button(perf_button_frame, text="🏃 " + _t("log_management.maintenance.perf_buttons.query_perf"),
                  command=self.test_query_performance).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(perf_button_frame, text="💾 " + _t("log_management.maintenance.perf_buttons.insert_perf"),
                  command=self.test_insert_performance).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(perf_button_frame, text="📊 " + _t("log_management.maintenance.perf_buttons.system_resources"),
                  command=self.show_system_resources).pack(side=tk.LEFT)

        # Results display
        results_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.maintenance_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                         font=("Courier", 10),
                                                         fg="#000000", bg="#FFFFFF")
        self.maintenance_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def show_database_info(self):
        """Show database information"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return

        try:
            db_path = self.log_manager.db.db_path

            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                size_mb = size_bytes / (1024 * 1024)

                # Get record counts
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()

                    cursor.execute("SELECT COUNT(*) FROM activity_log")
                    log_count = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM alerts")
                    alert_count = cursor.fetchone()[0]

                finally:
                    conn.close()

                info_text = f"""Database Information
====================

File Path: {db_path}
Size: {size_bytes:,} bytes ({size_mb:.2f} MB)

Record Counts:
- Logs: {log_count:,}
- Alerts: {alert_count:,}

Average log size: {size_bytes / max(log_count, 1):.0f} bytes
"""
            else:
                info_text = "Database file not found."

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", info_text)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.db_info", error=str(e)))

    def optimize_database(self):
        """Optimize database"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_optimize")):
            self.update_status(_t("log_management.messages.optimizing_db"))

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                output = "Database Optimization Results\n"
                output += "="*35 + "\n\n"

                # Analyze tables
                cursor.execute("ANALYZE")
                output += "✅ Table analysis completed\n"

                # Update statistics
                cursor.execute("PRAGMA optimize")
                output += "✅ Statistics updated\n"

                conn.commit()
                conn.close()

                output += "\nDatabase optimization completed successfully!"

                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.optimize_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.messages.optimize_completed"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.optimize", error=str(e)))
                self.update_status(_t("log_management.messages.optimize_failed"))

    def vacuum_database(self):
        """Vacuum database to reclaim space"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_vacuum")):
            self.update_status(_t("log_management.messages.vacuuming_db"))

            try:
                # Get size before
                size_before = os.path.getsize(self.log_manager.db.db_path)

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()

                    cursor.execute("VACUUM")
                finally:
                    conn.close()

                # Get size after
                size_after = os.path.getsize(self.log_manager.db.db_path)
                space_saved = size_before - size_after

                output = f"""Database Vacuum Results
=======================

Size before: {size_before:,} bytes ({size_before/(1024*1024):.2f} MB)
Size after: {size_after:,} bytes ({size_after/(1024*1024):.2f} MB)
Space reclaimed: {space_saved:,} bytes ({space_saved/(1024*1024):.2f} MB)

VACUUM completed successfully!
"""

                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.vacuum_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.vacuum_success", mb=f"{space_saved/(1024*1024):.2f}"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.vacuum", error=str(e)))
                self.update_status(_t("log_management.messages.vacuum_failed"))

    def run_integrity_check(self):
        """Run log integrity check"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.integrity_check"))

        try:
            # Sample check of recent logs
            filters = {
                'date_from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            }

            recent_logs = self.log_manager.db.search_logs(filters, limit=1000)

            if not recent_logs:
                output = "No recent logs to check."
            else:
                corrupted_count = 0
                checked_count = 0

                for log in recent_logs:
                    if log.get('hash'):
                        # Verify hash
                        log_data = {k: v for k, v in log.items() if k != 'hash'}
                        calculated_hash = LogSecurity.generate_hash(log_data)

                        if calculated_hash != log['hash']:
                            corrupted_count += 1

                        checked_count += 1

                output = f"""Log Integrity Check Results
============================

Logs checked: {checked_count:,}
Corrupted logs: {corrupted_count:,}
Success rate: {((checked_count - corrupted_count) / max(checked_count, 1)) * 100:.2f}%

"""

                if corrupted_count > 0:
                    output += "⚠️ Warning: Some logs may have been tampered with!\n"
                else:
                    output += "✅ All checked logs passed integrity verification\n"

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.integrity_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.integrity", error=str(e)))
            self.update_status(_t("log_management.messages.integrity_failed"))

    def archive_old_logs(self):
        """Archive old logs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_archive")):
            self.update_status(_t("log_management.messages.archiving_logs"))

            try:
                self.log_manager.retention.archive_old_logs()

                output = "Archive operation completed!\nCheck the logs/archives directory for archived files."

                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.archive_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.archive_success"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.archive", error=str(e)))
                self.update_status(_t("log_management.messages.archive_failed"))

    def cleanup_old_logs(self):
        """Cleanup old logs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        retention_days = self.log_manager.config.get('retention_days', 90)

        if messagebox.askyesno(_t("log_management.messages.confirm"),
                              _t("log_management.maintenance.confirm_cleanup", days=retention_days)):

            if messagebox.askyesno(_t("log_management.maintenance.final_confirm"),
                                  _t("log_management.maintenance.cleanup_warning")):

                self.update_status(_t("log_management.messages.cleanup_logs"))

                try:
                    self.log_manager.retention.cleanup_old_logs()

                    output = f"Cleanup operation completed!\nLogs older than {retention_days} days have been deleted."

                    self.maintenance_text.delete("1.0", tk.END)
                    self.maintenance_text.insert("1.0", output)

                    self.update_status(_t("log_management.messages.cleanup_completed"))
                    messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.cleanup_success"))
                    self.update_dashboard()

                except Exception as e:
                    messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.cleanup", error=str(e)))
                    self.update_status(_t("log_management.messages.cleanup_failed"))

    def view_archives(self):
        """View archived log files"""
        archive_dir = str(LOG_DIR / "archives")

        if not os.path.exists(archive_dir):
            messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.maintenance.no_archive_dir"))
            return

        archives = [f for f in os.listdir(archive_dir) if f.endswith('.zip')]

        if not archives:
            messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.maintenance.no_archives"))
            return

        # Create archive viewer window
        archive_window = tk.Toplevel(self.root)
        archive_window.title(_t("log_management.dialogs.archive_files"))
        archive_window.geometry("600x400")

        ttk.Label(archive_window, text="Archive Files", font=("Arial", 14, "bold")).pack(pady=10)

        # Archive list
        archive_frame = ttk.LabelFrame(archive_window, text="Available Archives")
        archive_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("Filename", "Size", "Modified")
        archive_tree = ttk.Treeview(archive_frame, columns=columns, show="headings")

        for col in columns:
            archive_tree.heading(col, text=col)
            archive_tree.column(col, width=150)

        # Populate archive list
        for archive in sorted(archives, reverse=True):
            file_path = os.path.join(archive_dir, archive)
            file_size = os.path.getsize(file_path)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M')

            archive_tree.insert("", "end", values=(archive, f"{file_size:,} bytes", file_mtime))

        archive_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(archive_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        def open_archive_location():
            import subprocess
            import platform

            if platform.system() == "Windows":
                subprocess.Popen(["explorer", os.path.abspath(archive_dir)])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", archive_dir])
            else:  # Linux
                subprocess.Popen(["xdg-open", archive_dir])

        ttk.Button(button_frame, text="Open Archive Folder", command=open_archive_location).pack(side=tk.LEFT)

    def rebuild_indexes_gui(self):
        """GUI version of rebuild indexes"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if not messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_rebuild_indexes")):
            return

        self.update_status(_t("log_management.messages.rebuilding_indexes"))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            output = "Rebuilding Database Indexes\n"
            output += "="*30 + "\n\n"

            # Drop and recreate indexes
            indexes = [
                ("idx_logs_timestamp", "DROP INDEX IF EXISTS idx_logs_timestamp"),
                ("idx_logs_user_id", "DROP INDEX IF EXISTS idx_logs_user_id"),
                ("idx_logs_action", "DROP INDEX IF EXISTS idx_logs_action"),
                ("idx_logs_module", "DROP INDEX IF EXISTS idx_logs_module"),
                ("idx_logs_timestamp", "CREATE INDEX idx_logs_timestamp ON logs(timestamp)"),
                ("idx_logs_user_id", "CREATE INDEX idx_logs_user_id ON logs(user_id)"),
                ("idx_logs_action", "CREATE INDEX idx_logs_action ON logs(action)"),
                ("idx_logs_module", "CREATE INDEX idx_logs_module ON logs(module)")
            ]

            for index_name, index_sql in indexes:
                cursor.execute(index_sql)
                if "DROP" in index_sql:
                    output += f"Dropped index: {index_name}\n"
                else:
                    output += f"Created index: {index_name}\n"

            conn.commit()
            conn.close()

            output += "\nIndexes rebuilt successfully!"

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.index_rebuild_completed"))
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.indexes_rebuilt"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.rebuild_index", error=str(e)))
            self.update_status(_t("log_management.messages.index_rebuild_failed"))
