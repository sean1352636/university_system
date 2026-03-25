"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

# Import all original library functions
try:
    # Import from modular library package
    from education_system.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD,
        ensure_student_finance_account_exists,
        top_up_student_finance_account
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import matplotlib for library finance charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available for library finance charts")

# Import email service for library finance notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.university_system.modules.domain.academics.gui.library.base import LibraryGUI

def optimize_database(self):
    """Optimize database"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('VACUUM')
                cursor.execute('ANALYZE')
                conn.close()
                messagebox.showinfo(_("common.success"), "Database optimized successfully!")
        else:
            messagebox.showinfo(_("common.demo"), "Database optimization completed!")
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error optimizing database: {str(e)}")

def check_database_integrity(self):
    """Check database integrity"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('PRAGMA integrity_check')
                result = cursor.fetchone()[0]
                conn.close()

                if result == 'ok':
                    messagebox.showinfo(_("common.success"), "Database integrity check passed!")
                else:
                    messagebox.showwarning(_("common.warning"), f"Database integrity issues: {result}")
        else:
            messagebox.showinfo(_("common.demo"), "Database integrity check passed!")
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error checking database: {str(e)}")

def show_audit_log(self):
    """Show audit log viewer"""
    self.audit_log_dialog()

def audit_log_dialog(self):
    """Create audit log dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.audit_log_viewer"))
    dialog.geometry("800x600")
    dialog.transient(self.master)

    # Filter frame
    filter_frame = ttk.Frame(dialog)
    filter_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(filter_frame, text="User ID:").pack(side=tk.LEFT, padx=5)
    user_filter_var = tk.StringVar()
    ttk.Entry(filter_frame, textvariable=user_filter_var, width=15).pack(side=tk.LEFT, padx=5)

    ttk.Label(filter_frame, text="Action:").pack(side=tk.LEFT, padx=5)
    action_filter_var = tk.StringVar()
    ttk.Entry(filter_frame, textvariable=action_filter_var, width=20).pack(side=tk.LEFT, padx=5)

    ttk.Button(filter_frame, text="Filter", command=lambda: self.load_audit_log(audit_tree, user_filter_var.get(), action_filter_var.get())).pack(side=tk.LEFT, padx=5)
    ttk.Button(filter_frame, text=_("common.clear"), command=lambda: self.load_audit_log(audit_tree)).pack(side=tk.LEFT, padx=5)

    # Audit log table
    table_frame = ttk.Frame(dialog)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ('Timestamp', 'User ID', 'Action', 'Table', 'Success')
    audit_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

    for col in columns:
        audit_tree.heading(col, text=col)
        audit_tree.column(col, width=120)

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=audit_tree.yview)
    audit_tree.configure(yscrollcommand=v_scrollbar.set)

    audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load initial data
    self.load_audit_log(audit_tree)

    # Close button
    ttk.Button(dialog, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def load_audit_log(self, tree, user_filter="", action_filter=""):
    """Load audit log data"""
    # Clear existing data
    for item in tree.get_children():
        tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            query = '''
            SELECT timestamp, user_id, action, table_affected, success
            FROM audit_log
            WHERE 1=1
            '''
            params = []

            if user_filter:
                query += ' AND user_id LIKE ?'
                params.append(f'%{user_filter}%')

            if action_filter:
                query += ' AND action LIKE ?'
                params.append(f'%{action_filter}%')

            query += ' ORDER BY timestamp DESC LIMIT 100'

            cursor.execute(query, params)
            logs = cursor.fetchall()
            conn.close()

            for log in logs:
                timestamp, user_id, action, table_affected, success = log
                success_text = "✅" if success else "❌"

                tree.insert('', 'end', values=(
                    timestamp[:19],  # Format timestamp
                    user_id,
                    action,
                    table_affected or "N/A",
                    success_text
                ))
        else:
            # Demo data
            demo_logs = [
                ("2024-01-15 10:30:00", "admin", "GUI: Login", "system", "✅"),
                ("2024-01-15 10:31:00", "admin", "GUI: Added book B10001", "books", "✅"),
                ("2024-01-15 10:32:00", "admin", "GUI: Checked out book", "book_loans", "✅"),
            ]

            for log in demo_logs:
                tree.insert('', 'end', values=log)

    except tk.TclError as e:
        print(f"Error loading audit log: {e}")

def library_maintenance_gui(self):
    """GUI for library maintenance tasks"""
    if not self.check_permission('system_config'):
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.library_maintenance"))
    dialog.geometry("600x500")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="Library Maintenance Tasks", style='Title.TLabel')
    title_label.pack(pady=(0, 20))

    # Maintenance tasks
    tasks_frame = ttk.LabelFrame(main_frame, text="Available Tasks")
    tasks_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    tasks = [
        ("Clean up expired reservations", self.cleanup_expired_reservations),
        ("Update overdue status", self.update_overdue_status),
        ("Calculate fines", self.calculate_fines),
        ("Archive old loan records", self.archive_old_records),
        ("Optimize database", self.optimize_database),
        ("Check data integrity", self.check_data_integrity),
    ]

    for i, (task_name, task_func) in enumerate(tasks):
        task_frame = ttk.Frame(tasks_frame)
        task_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(task_frame, text=f"{i+1}. {task_name}").pack(side=tk.LEFT)
        ttk.Button(task_frame, text="Run", command=task_func).pack(side=tk.RIGHT)

    # Results area
    results_frame = ttk.LabelFrame(main_frame, text="Task Results")
    results_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    self.maintenance_results = ScrolledText(results_frame, height=8, wrap=tk.WORD)
    self.maintenance_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def cleanup_expired_reservations(self):
    """Clean up expired reservations"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE book_reservations 
                SET status = 'expired'
                WHERE status = 'active' AND expiry_date < datetime('now')
                ''')

                expired_count = cursor.rowcount
                conn.commit()
                conn.close()

                result = f"✅ Cleaned up {expired_count} expired reservations.\n"
        else:
            result = "✅ Demo: Would clean up expired reservations.\n"

        self.maintenance_results.insert(tk.END, result)
        self.maintenance_results.see(tk.END)
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

def update_overdue_status(self):
    """Update overdue loan status"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE book_loans 
                SET status = 'overdue'
                WHERE status = 'active' AND due_date < datetime('now')
                ''')

                overdue_count = cursor.rowcount
                conn.commit()
                conn.close()

                result = f"✅ Updated {overdue_count} loans to overdue status.\n"
        else:
            result = "✅ Demo: Would update overdue status.\n"

        self.maintenance_results.insert(tk.END, result)
        self.maintenance_results.see(tk.END)
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

def calculate_fines(self):
    """Calculate and update fines for overdue books"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get fine per day setting
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                setting = cursor.fetchone()
                fine_per_day = float(setting[0]) if setting else 0.50

                cursor.execute('''
                UPDATE book_loans 
                SET fine_amount = (julianday('now') - julianday(due_date)) * ?
                WHERE status = 'overdue' AND due_date < datetime('now')
                ''', (fine_per_day,))

                fine_count = cursor.rowcount
                conn.commit()
                conn.close()

                result = f"✅ Updated fines for {fine_count} overdue loans at ${fine_per_day:.2f} per day.\n"
        else:
            result = "✅ Demo: Would calculate and update fines.\n"

        self.maintenance_results.insert(tk.END, result)
        self.maintenance_results.see(tk.END)
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

def archive_old_records(self):
    """Archive old completed/returned loan records to an archive table"""
    try:
        if not ORIGINAL_LIBRARY_AVAILABLE:
            self.maintenance_results.insert(tk.END, "⚠️ Library module not available for archiving.\n")
            self.maintenance_results.see(tk.END)
            return

        conn = get_db_connection()
        if not conn:
            self.maintenance_results.insert(tk.END, "❌ Could not connect to database.\n")
            self.maintenance_results.see(tk.END)
            return

        cursor = conn.cursor()

        # Create the archive table if it doesn't exist (mirrors book_loans schema)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archived_book_loans (
                loan_id INTEGER PRIMARY KEY,
                book_id TEXT,
                user_id TEXT,
                checkout_date TEXT,
                due_date TEXT,
                return_date TEXT,
                status TEXT,
                fine_amount REAL DEFAULT 0,
                renewal_count INTEGER DEFAULT 0,
                reading_progress INTEGER DEFAULT 0,
                checkout_method TEXT,
                staff_id TEXT,
                notes TEXT,
                archived_at TEXT
            )
        ''')

        # Find completed loans older than 90 days
        cursor.execute('''
            SELECT COUNT(*) FROM book_loans
            WHERE status = 'returned'
            AND return_date IS NOT NULL
            AND return_date < datetime('now', '-90 days')
        ''')
        archivable_count = cursor.fetchone()[0]

        if archivable_count == 0:
            self.maintenance_results.insert(tk.END,
                "✅ No old loan records to archive (returned loans older than 90 days).\n")
            self.maintenance_results.see(tk.END)
            conn.close()
            return

        # Confirm with user
        if not messagebox.askyesno("Confirm Archive",
                f"Found {archivable_count} returned loan(s) older than 90 days.\n\n"
                "Move these to the archive table?\n"
                "This helps maintain performance for active queries."):
            self.maintenance_results.insert(tk.END, "⚠️ Archive cancelled by user.\n")
            self.maintenance_results.see(tk.END)
            conn.close()
            return

        self.maintenance_results.insert(tk.END, f"Archiving {archivable_count} old loan records...\n")
        self.maintenance_results.see(tk.END)

        # Copy records to archive table
        archived_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO archived_book_loans
            (loan_id, book_id, user_id, checkout_date, due_date, return_date,
             status, fine_amount, renewal_count, reading_progress,
             checkout_method, staff_id, notes, archived_at)
            SELECT loan_id, book_id, user_id, checkout_date, due_date, return_date,
                   status, fine_amount, renewal_count, reading_progress,
                   checkout_method, staff_id, notes, ?
            FROM book_loans
            WHERE status = 'returned'
            AND return_date IS NOT NULL
            AND return_date < datetime('now', '-90 days')
        ''', (archived_at,))

        archived_count = cursor.rowcount

        # Delete archived records from the active table
        cursor.execute('''
            DELETE FROM book_loans
            WHERE status = 'returned'
            AND return_date IS NOT NULL
            AND return_date < datetime('now', '-90 days')
        ''')

        deleted_count = cursor.rowcount

        conn.commit()

        # Get remaining active loan count
        cursor.execute('SELECT COUNT(*) FROM book_loans')
        remaining = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM archived_book_loans')
        total_archived = cursor.fetchone()[0]

        conn.close()

        result = (
            f"✅ Archive complete!\n"
            f"   Archived: {archived_count} loan records\n"
            f"   Removed from active table: {deleted_count}\n"
            f"   Active loans remaining: {remaining}\n"
            f"   Total archived records: {total_archived}\n"
        )
        self.maintenance_results.insert(tk.END, result)
        self.maintenance_results.see(tk.END)

        if ORIGINAL_LIBRARY_AVAILABLE:
            try:
                log_audit_event(
                    'system', f"Archived {archived_count} old loan records", "maintenance"
                )
            except Exception:
                pass

    except (sqlite3.Error, Exception) as e:
        self.maintenance_results.insert(tk.END, f"❌ Archive failed: {str(e)}\n")
        self.maintenance_results.see(tk.END)

def check_data_integrity(self):
    """Check database integrity"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('PRAGMA integrity_check')
                result = cursor.fetchone()[0]
                conn.close()

                if result == 'ok':
                    integrity_result = "✅ Database integrity check passed.\n"
                else:
                    integrity_result = f"❌ Database integrity issues: {result}\n"
        else:
            integrity_result = "✅ Demo: Database integrity check passed.\n"

        self.maintenance_results.insert(tk.END, integrity_result)
        self.maintenance_results.see(tk.END)
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        self.maintenance_results.insert(tk.END, f"❌ Error checking integrity: {str(e)}\n")

def quick_system_health_check(self):
    """Perform quick system health check"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.system_health_check"))
    dialog.geometry("500x400")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="System Health Check", style='Title.TLabel')
    title_label.pack(pady=(0, 10))

    # Results area
    results_text = ScrolledText(main_frame, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Run health check
    health_status = []

    try:
        # Database connectivity
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM books')
                health_status.append(("Database Connection", "✅ OK"))

                # Check integrity
                cursor.execute('PRAGMA integrity_check')
                integrity = cursor.fetchone()[0]

                if integrity == 'ok':
                    health_status.append(("Database Integrity", "✅ OK"))
                else:
                    health_status.append(("Database Integrity", f"❌ {integrity}"))

                # Check overdue items
                cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
                overdue_count = cursor.fetchone()[0]

                if overdue_count == 0:
                    health_status.append(("Overdue Items", "✅ None"))
                elif overdue_count < 10:
                    health_status.append(("Overdue Items", f"⚠️ {overdue_count} items"))
                else:
                    health_status.append(("Overdue Items", f"❌ {overdue_count} items"))

                conn.close()
            else:
                health_status.append(("Database Connection", "❌ Failed"))
        else:
            health_status.append(("Database Connection", "✅ Demo Mode"))

        # File system checks — resolve relative to the university system root
        # DB is at .../university_system/data/db_files/student_records.db
        uni_root = os.path.dirname(os.path.dirname(os.path.dirname(str(DEFAULT_DB_PATH))))
        dir_paths = {
            'backups': os.path.join(uni_root, 'data', 'backups'),
            'qr_codes': os.path.join(uni_root, 'qr_codes'),
            'digital_library': os.path.join(uni_root, 'digital_library'),
        }

        for directory, dir_path in dir_paths.items():
            if os.path.exists(dir_path):
                health_status.append((f"{directory.title()} Directory", "✅ Exists"))
            else:
                # Auto-create missing directories
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    health_status.append((f"{directory.title()} Directory", "✅ Created"))
                except OSError:
                    health_status.append((f"{directory.title()} Directory", "⚠️ Missing"))

        # Display results
        results_text.insert(tk.END, "Health Check Results:\n")
        results_text.insert(tk.END, "-" * 40 + "\n\n")

        for check, status in health_status:
            results_text.insert(tk.END, f"{check:<25} {status}\n")

        results_text.insert(tk.END, "\n" + "-" * 40 + "\n")

        # Overall assessment
        error_count = len([s for _, s in health_status if s.startswith("❌")])
        warning_count = len([s for _, s in health_status if s.startswith("⚠️")])

        if error_count == 0 and warning_count == 0:
            results_text.insert(tk.END, "Overall Status: ✅ HEALTHY")
        elif error_count == 0:
            results_text.insert(tk.END, "Overall Status: ⚠️ WARNINGS")
        else:
            results_text.insert(tk.END, "Overall Status: ❌ ISSUES DETECTED")

    except tk.TclError as e:
        results_text.insert(tk.END, f"Health check failed: {e}")

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def system_health_check_gui(self):
    """System health check interface"""
    health_window = tk.Toplevel(self.master)
    health_window.title("System Health Check")
    health_window.geometry("700x600")

    ttk.Label(health_window, text="System Health Check",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Results display
    results_frame = ttk.LabelFrame(health_window, text="Health Check Results", padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    results_text = ScrolledText(results_frame, height=30, width=80, font=('Courier', 10))
    results_text.pack(fill=tk.BOTH, expand=True)

    def run_health_check():
        results_text.delete('1.0', tk.END)

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║               LIBRARY SYSTEM HEALTH CHECK                    ║
╚══════════════════════════════════════════════════════════════╝

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DATABASE CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Test connection
            cursor.execute('SELECT 1')
            report += "✓ Database connection: OK\n"

            # Check table integrity
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            report += f"✓ Tables found: {len(tables)}\n"

            # Check data integrity
            report += "\nDATA INTEGRITY:\n"
            report += "━" * 60 + "\n"

            # Books
            cursor.execute('SELECT COUNT(*) FROM books')
            book_count = cursor.fetchone()[0]
            report += f"Books: {book_count:,}\n"

            # Loans
            cursor.execute('SELECT COUNT(*) FROM book_loans')
            loan_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "active"')
            active_loans = cursor.fetchone()[0]
            report += f"Total Loans: {loan_count:,} (Active: {active_loans:,})\n"

            # Reservations
            cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
            active_res = cursor.fetchone()[0]
            report += f"Active Reservations: {active_res:,}\n"

            # Check for orphaned records
            report += "\nORPHANED RECORDS CHECK:\n"
            report += "━" * 60 + "\n"

            cursor.execute('''
            SELECT COUNT(*) FROM book_loans l
            WHERE NOT EXISTS (SELECT 1 FROM books b WHERE b.book_id = l.book_id)
            ''')
            orphaned_loans = cursor.fetchone()[0]
            if orphaned_loans > 0:
                report += f"⚠ Orphaned loans: {orphaned_loans}\n"
            else:
                report += "✓ No orphaned loans\n"

            # Check overdue books
            report += "\nOVERDUE ITEMS:\n"
            report += "━" * 60 + "\n"
            cursor.execute('''
            SELECT COUNT(*) FROM book_loans
            WHERE status = 'active' AND due_date < datetime('now')
            ''')
            overdue_count = cursor.fetchone()[0]
            report += f"Overdue books: {overdue_count:,}\n"

            # Check database file size
            from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
            db_size = os.path.getsize(DEFAULT_DB_PATH) / (1024 * 1024)  # MB
            report += f"\nDATABASE SIZE: {db_size:.2f} MB\n"

            report += "\n" + "="* 60 + "\n"
            report += "HEALTH CHECK COMPLETE\n"
            report += "Overall Status: " + ("✓ HEALTHY" if orphaned_loans == 0 else "⚠ NEEDS ATTENTION")

            conn.close()

        except (sqlite3.Error, DatabaseError, OSError, IOError) as e:
            report += f"\n✗ Health check failed: {str(e)}"

        results_text.insert('1.0', report)

    def repair_database():
        if messagebox.askyesno("Confirm Repair",
            "This will attempt to repair database issues.\nContinue?"):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Vacuum database
                cursor.execute('VACUUM')

                # Update stale statuses
                cursor.execute('''
                UPDATE book_loans SET status = 'overdue'
                WHERE status = 'active' AND due_date < datetime('now')
                ''')

                # Expire old reservations
                cursor.execute('''
                UPDATE book_reservations SET status = 'expired'
                WHERE status = 'active' AND expiry_date < datetime('now')
                ''')

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Database repaired successfully!")
                run_health_check()  # Re-run check

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Repair failed: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(health_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Run Health Check", command=run_health_check).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Repair Database", command=repair_database).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=health_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Auto-run on open
    run_health_check()

def view_audit_log_gui(self):
    """View audit log interface"""
    audit_window = tk.Toplevel(self.master)
    audit_window.title("Audit Log Viewer")
    audit_window.geometry("1000x700")

    ttk.Label(audit_window, text="Audit Log Viewer",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Filter frame
    filter_frame = ttk.LabelFrame(audit_window, text="Filters", padding=10)
    filter_frame.pack(fill=tk.X, padx=10, pady=10)

    user_filter = tk.StringVar()
    action_filter = tk.StringVar()
    entity_filter = tk.StringVar()

    ttk.Label(filter_frame, text="User ID:").grid(row=0, column=0, padx=5, pady=5)
    ttk.Entry(filter_frame, textvariable=user_filter, width=20).grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(filter_frame, text="Action:").grid(row=0, column=2, padx=5, pady=5)
    ttk.Entry(filter_frame, textvariable=action_filter, width=20).grid(row=0, column=3, padx=5, pady=5)

    ttk.Label(filter_frame, text="Entity:").grid(row=0, column=4, padx=5, pady=5)
    ttk.Entry(filter_frame, textvariable=entity_filter, width=20).grid(row=0, column=5, padx=5, pady=5)

    # Audit log table
    table_frame = ttk.Frame(audit_window)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Timestamp', 'User', 'Action', 'Entity Type', 'Entity ID', 'Details')
    audit_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

    for col in columns:
        audit_tree.heading(col, text=col)
        audit_tree.column(col, width=150)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=audit_tree.yview)
    audit_tree.configure(yscrollcommand=scrollbar.set)

    audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_audit_log():
        for item in audit_tree.get_children():
            audit_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            query = 'SELECT timestamp, user_id, action, entity_type, entity_id, details FROM audit_log WHERE 1=1'
            params = []

            user = user_filter.get().strip()
            if user:
                query += ' AND user_id = ?'
                params.append(user)

            action = action_filter.get().strip()
            if action:
                query += ' AND action LIKE ?'
                params.append(f'%{action}%')

            entity = entity_filter.get().strip()
            if entity:
                query += ' AND entity_type = ?'
                params.append(entity)

            query += ' ORDER BY timestamp DESC LIMIT 500'

            cursor.execute(query, params)

            for row in cursor.fetchall():
                audit_tree.insert('', 'end', values=row)

            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError, ValueError, TypeError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load audit log: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(audit_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Load Log", command=load_audit_log).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Clear Filters",
              command=lambda: [user_filter.set(''), action_filter.set(''), entity_filter.set('')]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=audit_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Auto-load on open
    load_audit_log()

def database_optimization_gui(self):
    """Database optimization and maintenance"""
    opt_window = tk.Toplevel(self.master)
    opt_window.title("Database Optimization")
    opt_window.geometry("600x500")

    ttk.Label(opt_window, text="Database Optimization",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Results display
    results_frame = ttk.LabelFrame(opt_window, text="Optimization Results", padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    results_text = ScrolledText(results_frame, height=20, width=70, font=('Courier', 9))
    results_text.pack(fill=tk.BOTH, expand=True)

    def run_optimization():
        results_text.delete('1.0', tk.END)
        results_text.insert('1.0', "Starting database optimization...\n\n")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get database size before
            cursor.execute("PRAGMA page_count")
            page_count_before = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            size_before = (page_count_before * page_size) / (1024 * 1024)  # MB

            results_text.insert(tk.END, f"Database size before: {size_before:.2f} MB\n\n")

            # Run VACUUM
            results_text.insert(tk.END, "Running VACUUM command...\n")
            cursor.execute("VACUUM")
            results_text.insert(tk.END, "✓ VACUUM completed\n\n")

            # Analyze tables
            results_text.insert(tk.END, "Analyzing tables...\n")
            cursor.execute("ANALYZE")
            results_text.insert(tk.END, "✓ ANALYZE completed\n\n")

            # Reindex
            results_text.insert(tk.END, "Rebuilding indexes...\n")
            cursor.execute("REINDEX")
            results_text.insert(tk.END, "✓ REINDEX completed\n\n")

            # Get database size after
            cursor.execute("PRAGMA page_count")
            page_count_after = cursor.fetchone()[0]
            size_after = (page_count_after * page_size) / (1024 * 1024)  # MB

            saved = size_before - size_after
            results_text.insert(tk.END, f"Database size after: {size_after:.2f} MB\n")
            results_text.insert(tk.END, f"Space reclaimed: {saved:.2f} MB ({(saved/size_before*100):.1f}%)\n\n")

            results_text.insert(tk.END, "=" * 60 + "\n")
            results_text.insert(tk.END, "Optimization completed successfully!\n")

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), "Ran database optimization", "system")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            results_text.insert(tk.END, f"\n❌ Error: {str(e)}\n")

    # Button frame
    button_frame = ttk.Frame(opt_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Run Optimization", command=run_optimization).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=opt_window.destroy).pack(side=tk.RIGHT, padx=5)

def clear_cache_gui(self):
    """Clear temporary files and cache"""
    confirm = messagebox.askyesno(
        "Confirm Clear Cache",
        "This will clear temporary files and cached data.\n\nContinue?"
    )

    if not confirm:
        return

    try:
        items_cleared = 0

        # Clear temp directory if it exists
        temp_dir = os.path.join(os.path.dirname(DATABASE_FILE), 'temp')
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        items_cleared += 1
                except (OSError, IOError) as e:
                    print(f"Error deleting {file_path}: {e}")

        # Clear old backup files (keep last 10)
        backup_dir = os.path.join(os.path.dirname(DATABASE_FILE), 'backups')
        if os.path.exists(backup_dir):
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')],
                           key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
                           reverse=True)

            for old_backup in backups[10:]:  # Keep last 10
                try:
                    os.unlink(os.path.join(backup_dir, old_backup))
                    items_cleared += 1
                except (OSError, IOError, ValueError, TypeError) as e:
                    print(f"Error deleting backup {old_backup}: {e}")

        log_audit_event(get_current_user_id(), f"Cleared cache ({items_cleared} items)", "system")
        messagebox.showinfo(_("common.success"), f"Cache cleared successfully!\n{items_cleared} items removed")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to clear cache: {str(e)}")

def manage_library_events_gui(self):
    """Manage library events (create, view, edit, delete)"""
    events_window = tk.Toplevel(self.master)
    events_window.title("Library Events Management")
    events_window.geometry("900x600")

    ttk.Label(events_window, text="Library Events Management",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Events list
    list_frame = ttk.LabelFrame(events_window, text="Upcoming Events", padding=10)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('ID', 'Event Name', 'Date', 'Time', 'Location', 'Capacity', 'Registered')
    events_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

    for col in columns:
        events_tree.heading(col, text=col)
        events_tree.column(col, width=100 if col != 'Event Name' else 200)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=events_tree.yview)
    events_tree.configure(yscrollcommand=scrollbar.set)

    events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_events():
        for item in events_tree.get_children():
            events_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                location TEXT,
                description TEXT,
                max_capacity INTEGER DEFAULT 50,
                registered_count INTEGER DEFAULT 0,
                created_by TEXT,
                created_at TEXT
            )
            ''')

            cursor.execute('''
            SELECT event_id, event_name, event_date, event_time, location, max_capacity, registered_count
            FROM library_events
            WHERE event_date >= date('now')
            ORDER BY event_date, event_time
            ''')

            for row in cursor.fetchall():
                events_tree.insert('', 'end', values=row)

            conn.commit()
            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load events: {str(e)}")

    def add_event():
        add_window = tk.Toplevel(events_window)
        add_window.title("Add New Event")
        add_window.geometry("500x600")

        ttk.Label(add_window, text="Create New Event", font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(add_window)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ttk.Label(form_frame, text="Event Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(form_frame, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
        date_entry = ttk.Entry(form_frame, width=40)
        date_entry.grid(row=1, column=1, pady=5)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(form_frame, text="Time (HH:MM):").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_entry = ttk.Entry(form_frame, width=40)
        time_entry.grid(row=2, column=1, pady=5)

        ttk.Label(form_frame, text="Location:").grid(row=3, column=0, sticky=tk.W, pady=5)
        location_entry = ttk.Entry(form_frame, width=40)
        location_entry.grid(row=3, column=1, pady=5)

        ttk.Label(form_frame, text="Max Capacity:").grid(row=4, column=0, sticky=tk.W, pady=5)
        capacity_spinbox = ttk.Spinbox(form_frame, from_=5, to=500, width=38)
        capacity_spinbox.set(50)
        capacity_spinbox.grid(row=4, column=1, pady=5)

        ttk.Label(form_frame, text="Description:").grid(row=5, column=0, sticky=tk.W, pady=5)
        desc_text = tk.Text(form_frame, height=8, width=40)
        desc_text.grid(row=5, column=1, pady=5)

        def save_event():
            try:
                event_name = name_entry.get().strip()
                event_date = date_entry.get().strip()
                event_time = time_entry.get().strip()
                location = location_entry.get().strip()
                capacity = int(capacity_spinbox.get())
                description = desc_text.get('1.0', tk.END).strip()

                if not event_name or not event_date or not event_time:
                    messagebox.showwarning(_("common.warning"), "Please fill in all required fields")
                    return

                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO library_events (event_name, event_date, event_time, location, description,
                                           max_capacity, registered_count, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                ''', (event_name, event_date, event_time, location, description, capacity,
                     get_current_user_id(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Created event: {event_name}", "library_events")
                messagebox.showinfo(_("common.success"), "Event created successfully!")
                add_window.destroy()
                load_events()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Failed to create event: {str(e)}")

        ttk.Button(form_frame, text="Create Event", command=save_event).grid(row=6, column=0, columnspan=2, pady=20)

    def delete_event():
        selected = events_tree.selection()
        if not selected:
            messagebox.showwarning(_("common.warning"), "Please select an event to delete")
            return

        event_id = events_tree.item(selected[0])['values'][0]
        event_name = events_tree.item(selected[0])['values'][1]

        confirm = messagebox.askyesno("Confirm Delete", f"Delete event '{event_name}'?")
        if not confirm:
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM library_events WHERE event_id = ?', (event_id,))
            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), f"Deleted event: {event_name}", "library_events")
            messagebox.showinfo(_("common.success"), "Event deleted successfully")
            load_events()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to delete event: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(events_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Add Event", command=add_event).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Delete Event", command=delete_event).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.refresh"), command=load_events).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=events_window.destroy).pack(side=tk.RIGHT, padx=5)

    load_events()

