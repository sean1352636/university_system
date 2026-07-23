# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import logging
from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Alias for translation function
from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608

# Import GUI availability flags and classes
from education_system.post_18.university_system.modules.shared.gui.main.imports.gui_imports import (
    DATA_BACKUP_GUI_AVAILABLE,
    BackupGUI,
    BATCH_OPS_GUI_AVAILABLE,
    BatchOperationsGUI,
)

logger = logging.getLogger(__name__)

def show_backup(self):
    """Launch the full Data Backup GUI"""
    try:
        # Import the backup GUI
        from education_system.post_18.university_system.modules.shared.gui.database.entry_points import start_backup_gui

        # Launch the backup GUI in a new window
        start_backup_gui()
        print(_t("database_admin_gui.messages.backup_launched"))

    except ImportError as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_not_available", error=str(e)))
        print(f"Import error: {e}")
    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_launch_failed", error=str(e)))
        print(f"Backup GUI error: {e}")
def show_data_backup_gui(self):
    """Launch Data Backup inside the main GUI's content notebook
    when a workspace is available, falling back to a Toplevel
    otherwise — same pattern as Student Records (8.117.38)."""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_backup"))
        return

    if not self.auth.check_permission('backup_restore'):
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.no_permission_backup"))
        return

    if not DATA_BACKUP_GUI_AVAILABLE:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_gui_not_available"))
        return

    title = _t("database_admin_gui.titles.backup_restore_system")
    auth = self.auth

    def _build(host):
        gui = BackupGUI(host, auth)
        if hasattr(gui, 'set_auth'):
            gui.set_auth(auth)
        return gui

    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, _build)
        print(_t("database_admin_gui.messages.backup_gui_opened"))
        return

    try:
        backup_window = tk.Toplevel(self.root)
        _install_clean_close(backup_window)
        backup_window.title(title)
        backup_window.geometry("800x600")
        backup_window.minsize(600, 500)
        try:
            backup_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set backup_window as transient: {e}")
        _build(backup_window)
        print(_t("database_admin_gui.messages.backup_gui_opened"))
    except ImportError:
        # Fallback to CLI menu
        try:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_backup_menu
            display_backup_menu()
        except ImportError:
            messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_system_not_available"))
    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_gui_open_failed", error=str(e)))
def show_batch_operations_gui(self):
    """Launch Batch Operations inside the main GUI's content notebook
    when a workspace is available, falling back to a Toplevel
    otherwise — same pattern as Student Records (8.117.38)."""
    # Auth gate (best-effort; don't block on unexpected auth errors)
    try:
        if hasattr(self, "auth") and not getattr(self.auth, "current_user", None):
            messagebox.showerror(_t("database_admin_gui.titles.batch_operations"), _t("database_admin_gui.errors.login_required"))
            return
    except Exception as e:
        logger.error(f"Error in batch operations: {e}")

    if not BATCH_OPS_GUI_AVAILABLE:
        messagebox.showerror(_t("database_admin_gui.titles.batch_operations"), _t("database_admin_gui.errors.batch_ops_not_available"))
        return

    title = _t("database_admin_gui.titles.batch_operations")
    auth = getattr(self, "auth", None)

    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: BatchOperationsGUI(host, auth))
        print(_t("database_admin_gui.messages.batch_ops_opened"))
        return

    try:
        batch_window = tk.Toplevel(self.root)
        _install_clean_close(batch_window)
        batch_window.title(title)
        batch_window.geometry("1000x700")
        BatchOperationsGUI(batch_window, auth)
        print(_t("database_admin_gui.messages.batch_ops_opened"))
    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.batch_ops_open_failed", error=str(e)))
        print(f"Batch Operations error: {e}")
def fix_duplicates(self):
    """Fix duplicate records in the database"""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_db_ops"))
        return

    user_role = self.auth.current_user.get('role', '')
    if user_role != 'admin':
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.admin_required"))
        return

    try:
        result = messagebox.askyesno(_t("database_admin_gui.titles.confirm"),
            _t("database_admin_gui.dialogs.fix_duplicates_confirm"))

        if not result:
            return

        # Deduplicate on natural keys, keeping the earliest row (lowest rowid).
        # Rows with an empty/NULL key are never treated as duplicates.
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        dedup_targets = [
            ("students", ["email_address"]),
            ("payments", ["transaction_id"]),
            ("scholarships", ["scholarship_name", "academic_year"]),
        ]

        db_path = getattr(self.auth, "db_path", None)
        removed = {}
        conn = get_connection(db_path, row_factory=False)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            for table, key_cols in dedup_targets:
                # Only touch tables/columns that actually exist in this schema.
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if cursor.fetchone() is None:
                    continue
                existing_cols = {row[1] for row in cursor.execute(
                    "PRAGMA table_info([" + validate_table_name(table, conn=conn) + "])")}
                if not all(col in existing_cols for col in key_cols):
                    continue

                safe_table = validate_table_name(table, conn=conn)
                safe_keys = [validate_identifier(col, "column") for col in key_cols]
                partition = ", ".join("[" + c + "]" for c in safe_keys)
                not_null = " AND ".join(
                    "[" + c + "] IS NOT NULL AND TRIM([" + c + "]) <> ''" for c in safe_keys)

                dupe_rowids_sql = (  # nosec B608 - identifiers validated above
                    "SELECT rowid FROM ("
                    "  SELECT rowid, ROW_NUMBER() OVER "
                    "    (PARTITION BY " + partition + " ORDER BY rowid) AS rn"
                    "  FROM [" + safe_table + "]"
                    "  WHERE " + not_null +
                    ") WHERE rn > 1"
                )
                count = cursor.execute(
                    "SELECT COUNT(*) FROM (" + dupe_rowids_sql + ")").fetchone()[0]
                if count:
                    cursor.execute(
                        "DELETE FROM [" + safe_table + "] WHERE rowid IN (" + dupe_rowids_sql + ")")
                    removed[table] = count
            conn.commit()
        finally:
            conn.close()

        total = sum(removed.values())
        if total:
            detail = "\n".join(f"• {table}: {n} removed" for table, n in removed.items())
            messagebox.showinfo(_t("database_admin_gui.titles.database_maintenance"),
                f"{_t('database_admin_gui.dialogs.fix_duplicates_complete')}\n\n"
                f"Removed {total} duplicate record(s):\n{detail}")
        else:
            messagebox.showinfo(_t("database_admin_gui.titles.database_maintenance"),
                "No duplicate records were found.")

        self.log_activity(
            f"{_t('database_admin_gui.activity.duplicate_fix')} ({total} removed)",
            "info", "database_maintenance")

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.fix_duplicates_failed", error=str(e)))
def optimize_database(self):
    """Optimize database performance"""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_db_ops"))
        return

    user_role = self.auth.current_user.get('role', '')
    if user_role != 'admin':
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.admin_required"))
        return

    try:
        result = messagebox.askyesno(_t("database_admin_gui.titles.confirm"),
            _t("database_admin_gui.dialogs.optimize_db_confirm"))

        if not result:
            return

        # Real optimization: rebuild indexes, refresh the query planner's
        # statistics, reclaim free pages, and truncate the WAL.
        import os
        from education_system.post_18.university_system.infrastructure.database.db import (
            get_connection, DEFAULT_DB_PATH,
        )

        db_path = getattr(self.auth, "db_path", None) or DEFAULT_DB_PATH
        size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        conn = get_connection(db_path, row_factory=False)
        try:
            # VACUUM cannot run inside a transaction.
            conn.isolation_level = None
            conn.execute("REINDEX")
            conn.execute("ANALYZE")
            conn.execute("PRAGMA optimize")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        finally:
            conn.close()

        size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        reclaimed = max(0, size_before - size_after)

        def _mb(n):
            return f"{n / (1024 * 1024):.2f} MB"

        messagebox.showinfo(_t("database_admin_gui.titles.database_maintenance"),
            f"{_t('database_admin_gui.dialogs.optimize_db_complete')}\n\n"
            f"Operations run: REINDEX, ANALYZE, PRAGMA optimize, "
            f"WAL checkpoint, VACUUM.\n\n"
            f"Size before: {_mb(size_before)}\n"
            f"Size after:  {_mb(size_after)}\n"
            f"Reclaimed:   {_mb(reclaimed)}")

        self.log_activity(
            f"{_t('database_admin_gui.activity.optimization')} "
            f"(reclaimed {_mb(reclaimed)})",
            "info", "database_maintenance")

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.optimize_db_failed", error=str(e)))

def run_integrity_check(self):
    """Run database integrity check"""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_db_ops"))
        return

    user_role = self.auth.current_user.get('role', '')
    if user_role != 'admin':
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.admin_required"))
        return

    try:
        # Run SQLite's built-in integrity diagnostics against the live DB.
        from education_system.post_18.university_system.infrastructure.database.db import (
            get_connection, DEFAULT_DB_PATH,
        )
        from datetime import datetime

        db_path = getattr(self.auth, "db_path", None) or DEFAULT_DB_PATH
        conn = get_connection(db_path, row_factory=False)
        try:
            integrity = [row[0] for row in conn.execute("PRAGMA integrity_check")]
            quick = [row[0] for row in conn.execute("PRAGMA quick_check")]
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            table_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        finally:
            conn.close()

        integrity_ok = integrity == ["ok"]
        quick_ok = quick == ["ok"]
        fk_ok = not fk_violations

        lines = [
            "DATABASE INTEGRITY CHECK",
            "=" * 50,
            f"Database: {db_path}",
            f"Run at:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Tables:   {table_count}",
            "",
            f"integrity_check ...... {'✓ OK' if integrity_ok else '✗ FAILED'}",
            f"quick_check .......... {'✓ OK' if quick_ok else '✗ FAILED'}",
            f"foreign_key_check .... {'✓ OK' if fk_ok else '✗ ' + str(len(fk_violations)) + ' violation(s)'}",
            "",
        ]
        if not integrity_ok:
            lines.append("Integrity problems:")
            lines.extend(f"  • {msg}" for msg in integrity)
            lines.append("")
        if not fk_ok:
            lines.append("Foreign-key violations (table, rowid, referenced, fk_index):")
            lines.extend(f"  • {tuple(v)}" for v in fk_violations[:100])
            if len(fk_violations) > 100:
                lines.append(f"  ... and {len(fk_violations) - 100} more")
            lines.append("")
        lines.append(
            "Overall: ✓ Database is healthy" if (integrity_ok and quick_ok and fk_ok)
            else "Overall: ✗ Issues detected — review the details above")
        integrity_results = "\n".join(lines)

        result_window = tk.Toplevel(self.root)
        _install_clean_close(result_window)
        result_window.title(_t("database_admin_gui.titles.integrity_check_results"))
        result_window.geometry("600x400")

        text_frame = ttk.Frame(result_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_area = tk.Text(text_frame, wrap=tk.WORD, height=20, width=70)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)

        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_area.insert(tk.END, integrity_results)
        text_area.config(state=tk.DISABLED)

        ttk.Button(result_window, text=_t("database_admin_gui.buttons.close"),
                  command=result_window.destroy).pack(pady=10)

        self.log_activity(_t("database_admin_gui.activity.integrity_check"), "info", "database_maintenance")

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.integrity_check_failed", error=str(e)))

def show_db_statistics(self):
    """Show database statistics"""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_stats"))
        return

    user_role = self.auth.current_user.get('role', '')
    if user_role not in ['admin', 'staff']:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.admin_staff_required"))
        return

    try:
        stats_window = tk.Toplevel(self.root)
        _install_clean_close(stats_window)
        stats_window.title(_t("database_admin_gui.titles.database_statistics"))
        stats_window.geometry("700x500")

        # Create notebook for different stat categories
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # General Stats Tab
        general_frame = ttk.Frame(notebook, padding="10")
        notebook.add(general_frame, text=_t("database_admin_gui.tabs.general"))

        general_text = tk.Text(general_frame, wrap=tk.WORD, height=20, width=70)
        general_scroll = ttk.Scrollbar(general_frame, orient=tk.VERTICAL, command=general_text.yview)
        general_text.configure(yscrollcommand=general_scroll.set)

        general_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        general_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        general_stats = _t("database_admin_gui.reports.general_statistics")

        general_text.insert(tk.END, general_stats)
        general_text.config(state=tk.DISABLED)

        # Performance Stats Tab
        perf_frame = ttk.Frame(notebook, padding="10")
        notebook.add(perf_frame, text=_t("database_admin_gui.tabs.performance"))

        perf_text = tk.Text(perf_frame, wrap=tk.WORD, height=20, width=70)
        perf_scroll = ttk.Scrollbar(perf_frame, orient=tk.VERTICAL, command=perf_text.yview)
        perf_text.configure(yscrollcommand=perf_scroll.set)

        perf_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        perf_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        perf_stats = _t("database_admin_gui.reports.performance_statistics")

        perf_text.insert(tk.END, perf_stats)
        perf_text.config(state=tk.DISABLED)

        self.log_activity(_t("database_admin_gui.activity.statistics_viewed"), "info", "database_view")

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.show_statistics_failed", error=str(e)))

def show_db_performance(self):
    """Show database performance metrics"""
    try:
        perf_window = tk.Toplevel(self.root)
        _install_clean_close(perf_window)
        perf_window.title(_t("database_admin_gui.titles.database_performance"))
        perf_window.geometry("700x500")

        ttk.Label(perf_window, text=_t("database_admin_gui.labels.performance_metrics"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        perf_text = scrolledtext.ScrolledText(perf_window, wrap=tk.WORD, height=20,
                                              fg="#000000", bg="#FFFFFF")
        perf_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        import time

        # Test query performance
        start_time = time.time()
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM activity_log")
            log_count = cursor.fetchone()[0]
        query_time = (time.time() - start_time) * 1000

        perf_info = _t("database_admin_gui.reports.performance_report", query_time=f"{query_time:.2f}", log_count=log_count)
        perf_text.insert("1.0", perf_info)
        perf_text.config(state=tk.DISABLED)

        ttk.Button(perf_window, text=_t("database_admin_gui.buttons.close"), command=perf_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.show_performance_failed", error=str(e)))

def wipe_database(self):
    """Wipe all data from the database, preserving only default accounts and module definitions"""
    if not self.auth.current_user:
        messagebox.showerror("Error", "You must be logged in to perform database operations.")
        return

    user_role = self.auth.current_user.get('role', '')
    if user_role != 'admin':
        messagebox.showerror("Error", "Only administrators can wipe the database.")
        return

    try:
        # First confirmation
        result = messagebox.askyesno(
            "Confirm Database Wipe",
            "WARNING: This will permanently delete ALL data from the database.\n\n"
            "Only the 3 default accounts (admin, staff, student) and module definitions "
            "will be preserved.\n\n"
            "This action CANNOT be undone. Are you sure you want to continue?"
        )
        if not result:
            return

        # Second confirmation - require typing "WIPE"
        confirmation = simpledialog.askstring(
            "Final Confirmation",
            'Type "WIPE" to confirm database wipe:',
            parent=self.root
        )
        if confirmation != "WIPE":
            messagebox.showinfo("Cancelled", "Database wipe cancelled.")
            return

        from education_system.post_18.university_system.infrastructure.auth.core import UserAuth
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        from education_system.post_18.university_system.modules.scripts.setup_database_complete import sync_modules_to_database

        # Use the project's get_connection to ensure proper PRAGMAs (WAL, busy_timeout, etc.)
        conn = get_connection(self.auth.db_path, row_factory=False)
        try:
            cursor = conn.cursor()

            # Save CS and DS course records before wiping
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
            has_courses = cursor.fetchone() is not None
            preserved_courses = []
            if has_courses:
                cursor.execute("SELECT * FROM courses WHERE code IN ('CS', 'DS')")
                preserved_courses = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]

            cursor.execute("PRAGMA foreign_keys = OFF")
            for table in tables:
                safe_table = validate_table_name(table, conn=conn)
                cursor.execute("DELETE FROM [" + safe_table + "]")

            # Restore CS and DS courses
            if preserved_courses:
                safe_col_names = [validate_identifier(col, "column") for col in col_names]
                placeholders = ', '.join('?' * len(col_names))
                for row in preserved_courses:
                    cursor.execute("INSERT INTO courses (" + ", ".join("[" + c + "]" for c in safe_col_names) + ") VALUES (" + placeholders + ")", row)

            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        finally:
            conn.close()

        # Re-populate default accounts (opens its own connection internally)
        UserAuth._db_initialized = False
        self.auth._do_init_db()

        # Sync modules with a fresh connection so it sees _do_init_db's writes
        conn = get_connection(self.auth.db_path, row_factory=False)
        try:
            sync_modules_to_database(conn)
        finally:
            conn.close()

        self.log_activity("Database wiped and reset to defaults", "warning", "database_maintenance")

        messagebox.showinfo(
            "Database Wiped",
            "Database has been wiped successfully.\n\n"
            "Default accounts and module definitions have been restored.\n"
            "The system will now restart."
        )

        self.restart_gui()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to wipe database: {e}")

def show_active_connections(self):
    """Show active database connections"""
    try:
        conn_window = tk.Toplevel(self.root)
        _install_clean_close(conn_window)
        conn_window.title(_t("database_admin_gui.titles.active_connections"))
        conn_window.geometry("600x400")

        ttk.Label(conn_window, text=_t("database_admin_gui.labels.active_connections"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        conn_text = scrolledtext.ScrolledText(conn_window, wrap=tk.WORD, height=15,
                                              fg="#000000", bg="#FFFFFF")
        conn_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        conn_info = _t("database_admin_gui.reports.connection_status")
        conn_text.insert("1.0", conn_info)
        conn_text.config(state=tk.DISABLED)

        ttk.Button(conn_window, text=_t("database_admin_gui.buttons.close"), command=conn_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.show_connections_failed", error=str(e)))
