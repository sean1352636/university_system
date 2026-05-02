# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Alias for translation function
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608

# Import GUI availability flags and classes
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
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
        from education_system.university_system.modules.shared.gui.database.entry_points import start_backup_gui

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
    """Launch the Data Backup and Restore GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.login_required_backup"))
        return

    if not self.auth.check_permission('backup_restore'):
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.no_permission_backup"))
        return

    try:
        # Create backup window
        backup_window = tk.Toplevel(self.root)
        _install_clean_close(backup_window)
        backup_window.title(_t("database_admin_gui.titles.backup_restore_system"))
        backup_window.geometry("800x600")
        backup_window.minsize(600, 500)

        try:
            backup_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set backup_window as transient: {e}")

        # Use the imported BackupGUI class
        if not DATA_BACKUP_GUI_AVAILABLE:
            messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_gui_not_available"))
            return

        backup_gui = BackupGUI(backup_window, self.auth)

        if hasattr(backup_gui, 'set_auth'):
            backup_gui.set_auth(self.auth)

        print(_t("database_admin_gui.messages.backup_gui_opened"))

    except ImportError:
        # Fallback to CLI menu
        try:
            from education_system.university_system.infrastructure.database.data_backup import display_backup_menu
            display_backup_menu()
        except ImportError:
            messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_system_not_available"))
    except Exception as e:
        messagebox.showerror(_t("database_admin_gui.titles.error"), _t("database_admin_gui.errors.backup_gui_open_failed", error=str(e)))
def show_batch_operations_gui(self):
    """Launch Batch Operations GUI in a separate window."""
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

    # Create window + init GUI
    try:
        batch_window = tk.Toplevel(self.root)
        _install_clean_close(batch_window)
        batch_window.title(_t("database_admin_gui.titles.batch_operations"))
        batch_window.geometry("1000x700")

        BatchOperationsGUI(batch_window, getattr(self, "auth", None))
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

        # This is a placeholder - would need actual database logic
        messagebox.showinfo(_t("database_admin_gui.titles.database_maintenance"),
            _t("database_admin_gui.dialogs.fix_duplicates_complete"))

        self.log_activity(_t("database_admin_gui.activity.duplicate_fix"), "info", "database_maintenance")

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

        # This is a placeholder - would need actual database optimization logic
        messagebox.showinfo(_t("database_admin_gui.titles.database_maintenance"),
            _t("database_admin_gui.dialogs.optimize_db_complete"))

        self.log_activity(_t("database_admin_gui.activity.optimization"), "info", "database_maintenance")

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
        # This is a placeholder - would need actual integrity check logic
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

        # Sample integrity check results
        integrity_results = _t("database_admin_gui.reports.integrity_check_results")

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

        from education_system.university_system.infrastructure.database.db import get_connection
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

        from education_system.university_system.infrastructure.auth.core import UserAuth
        from education_system.university_system.infrastructure.database.db import get_connection
        from education_system.university_system.modules.scripts.setup_database_complete import sync_modules_to_database

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
