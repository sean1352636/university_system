"""Database management and maintenance"""

from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
import sys
import io
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import threading
import warnings
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
import qrcode
from io import BytesIO
import base64
from university_system.modules.domain.finance.gui.finance_reporting_gui import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.database.db import get_connection
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility (non-security critical)
    def send_email(*args, **kwargs):
        return True

    from pathlib import Path
    def get_connection():
        """
        Fallback database connection for standalone mode.
        Use the central student_records.db located in the refactored/db_files
        directory rather than creating an enhanced_student_finance.db in the
        current working directory. This ensures the application operates on
        a single database file when the main refactored modules are not
        available.
        """
        # Determine the project root (refactored directory) one level above finance
        base_dir = Path(__file__).resolve().parents[1]
        db_path = base_dir / "db_files" / str(DEFAULT_DB_PATH)
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def configure_logging(name=None):
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        from university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

try:
    from university_system.modules.finance.core.financial_core import (
        assign_to_collection_agency, track_collection_progress,
        update_collection_case_status, create_payment_arrangement,
        send_arrangement_confirmation, setup_collection_workflows,
        check_required_packages, ensure_database_exists, verify_fix
    )
except ImportError:
    # Stub implementations for missing functions
    def assign_to_collection_agency(*args, **kwargs):
        print("assign_to_collection_agency function not implemented")
    
    def track_collection_progress(*args, **kwargs):
        print("track_collection_progress function not implemented")
    
    def update_collection_case_status(*args, **kwargs):
        print("update_collection_case_status function not implemented")
    
    def create_payment_arrangement(*args, **kwargs):
        print("create_payment_arrangement function not implemented")
    
    def send_arrangement_confirmation(*args, **kwargs):
        print("send_arrangement_confirmation function not implemented")
    
    def setup_collection_workflows(*args, **kwargs):
        print("setup_collection_workflows function not implemented")
    
    def check_required_packages(*args, **kwargs):
        print("check_required_packages function not implemented")
    
    def ensure_database_exists(*args, **kwargs):
        print("ensure_database_exists function not implemented")
    
    def verify_fix(*args, **kwargs):
        print("verify_fix function not implemented")

# Add these import stubs for the missing functions if they don't exist
# Try to import from the actual location first
try:
    from university_system.modules.domain.finance.finance_misc.finance_db_operations import (
        complete_database_fix, quick_fix_database
    )
except ImportError:
    complete_database_fix = None
    quick_fix_database = None

try:
    from university_system.modules.finance.core.financial_core import (
        modify_payment_plan, view_student_credits, add_student_credit,
        manage_financial_aid, create_budget_plan, view_overdue_accounts,
        create_collection_case, aging_analysis_report, collection_case_status_report,
        view_student_collection_detail, manage_collection_agencies,
        budget_vs_actual_analysis, generate_aid_reports, aid_distribution_summary,
        aid_by_academic_year, loan_repayment_status_report, aid_effectiveness_analysis,
        track_loan_repayments, view_aid_types, create_aid_type, edit_aid_type,
        deactivate_aid_type, review_pending_aid_applications, process_loan_payment,
        view_aid_application_detail, manage_budget_categories, view_budget_categories,
        create_budget_category, edit_budget_category, deactivate_budget_category,
        variance_analysis_report, budget_performance_trends, category_performance_report,
        collection_performance_summary, monthly_revenue_trend_report,
        enhanced_notification_system, manage_aid_types, recovery_rate_analysis,
        agency_performance_report, export_forecast_report,
        initialize_finance, detect_payment_fraud,
        setup_email_config, setup_sms_config, generate_qr_payment_code,
        process_stripe_payment, create_approval_workflow, apply_credit_to_fees,
        update_actual_amounts, view_credit_history, send_collection_notice,
        add_collection_agency, edit_collection_agency, deactivate_collection_agency,
        view_collection_agencies, test_email_service, test_sms_service,
        generate_audit_report
    )
except ImportError:
    # Create stub functions for missing finance core features so the GUI can still load
    def _make_stub(name):
        def _stub(*args, **kwargs):
            print(f"{name} function not implemented")
        return _stub

    _missing_functions = [
        'modify_payment_plan', 'view_student_credits', 'add_student_credit',
        'manage_financial_aid', 'create_budget_plan', 'view_overdue_accounts',
        'create_collection_case', 'aging_analysis_report', 'collection_case_status_report',
        'view_student_collection_detail', 'manage_collection_agencies',
        'budget_vs_actual_analysis', 'generate_aid_reports', 'aid_distribution_summary',
        'aid_by_academic_year', 'loan_repayment_status_report', 'aid_effectiveness_analysis',
        'track_loan_repayments', 'view_aid_types', 'create_aid_type', 'edit_aid_type',
        'deactivate_aid_type', 'review_pending_aid_applications', 'process_loan_payment',
        'view_aid_application_detail', 'manage_budget_categories', 'view_budget_categories',
        'create_budget_category', 'edit_budget_category', 'deactivate_budget_category',
        'variance_analysis_report', 'budget_performance_trends', 'category_performance_report',
        'collection_performance_summary', 'monthly_revenue_trend_report',
        'enhanced_notification_system', 'manage_aid_types', 'recovery_rate_analysis',
        'agency_performance_report', 'export_forecast_report', 'complete_database_fix',
        'quick_fix_database', 'initialize_finance', 'detect_payment_fraud',
        'setup_email_config', 'setup_sms_config', 'generate_qr_payment_code',
        'process_stripe_payment', 'create_approval_workflow', 'apply_credit_to_fees',
        'update_actual_amounts', 'view_credit_history', 'send_collection_notice',
        'add_collection_agency', 'edit_collection_agency', 'deactivate_collection_agency',
        'view_collection_agencies', 'test_email_service', 'test_sms_service',
        'generate_audit_report'
    ]

    globals().update({name: _make_stub(name) for name in _missing_functions})

    # Also create stubs for complete_database_fix and quick_fix_database if they weren't imported
    if complete_database_fix is None:
        complete_database_fix = _make_stub('complete_database_fix')
    if quick_fix_database is None:
        quick_fix_database = _make_stub('quick_fix_database')

# Configure logging
log_path = get_log_file("analytics.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')




class DatabaseManager:
    """Database management and maintenance"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None


    def initialize_database(self):
        """Initialize database (wrapper for initialize_database_schema)"""
        try:
            self.initialize_database_schema()
            messagebox.showinfo("Success", "Database initialized successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Database initialization failed: {e}")
    


    def initialize_database_schema(self):
        """Initialize database schema with all required columns"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create fee_types table with is_active if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT,
            amount REAL,
            late_fee_calculation TEXT DEFAULT 'fixed',
            late_fee_amount REAL DEFAULT 0,
            grace_period_days INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Create other essential tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER,
            amount REAL NOT NULL,
            due_date DATE,
            status TEXT DEFAULT 'unpaid',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fee_type_id) REFERENCES fee_types(fee_type_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT,
            payment_date DATE,
            transaction_id TEXT,
            status TEXT DEFAULT 'completed',
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Add some default fee types if table is empty
            cursor.execute('SELECT COUNT(*) FROM fee_types')
            if cursor.fetchone()[0] == 0:
                default_fees = [
                    ('Tuition Fee', 'Annual tuition fee', 5000.00, 'fixed', 50.00, 7, 1),
                    ('Registration Fee', 'Course registration fee', 100.00, 'fixed', 10.00, 3, 1),
                    ('Lab Fee', 'Laboratory usage fee', 200.00, 'fixed', 20.00, 7, 1),
                    ('Library Fee', 'Library access fee', 50.00, 'fixed', 5.00, 14, 1)
                ]

                cursor.executemany('''
                INSERT INTO fee_types (fee_name, description, amount, late_fee_calculation,
                late_fee_amount, grace_period_days, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', default_fees)

                print("Default fee types created")

            conn.commit()
            conn.close()
            print("Database schema initialized successfully")

        except Exception as e:
            print(f"Failed to initialize database schema: {e}")


    def ensure_db_compatibility(self):
        """Ensure required columns exist to avoid OperationalError on older databases."""
        try:
            conn = get_connection()
            cur = conn.cursor()

            def ensure_col(tbl, col, decl):
                try:
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = [r[1] for r in cur.fetchall()]
                    if col not in cols:
                        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {decl}")
                        print(f"Added column {col} to table {tbl}")
                except Exception as e:
                    print(f"Error adding column {col} to {tbl}: {e}")

            # Ensure required columns exist
            ensure_col('students', 'status', 'TEXT DEFAULT "active"')
            ensure_col('payments', 'status', 'TEXT DEFAULT "completed"')
            ensure_col('fee_types', 'is_active', 'INTEGER DEFAULT 1')
            ensure_col('scholarships', 'is_active', 'INTEGER DEFAULT 1')
            ensure_col('financial_aid_types', 'is_active', 'INTEGER DEFAULT 1')
            ensure_col('student_fees', 'status', 'TEXT DEFAULT "unpaid"')
            ensure_col('budget_categories', 'is_active', 'INTEGER DEFAULT 1')
            ensure_col('payment_plan_templates', 'is_active', 'INTEGER DEFAULT 1')

            conn.commit()
            conn.close()
            print("Database compatibility check completed")

        except Exception as e:
            print(f"Database compatibility check failed: {e}")


    def clean_database(self):
        """Clean database - remove old records and optimize"""
        try:
            if not messagebox.askyesno("Confirm Database Cleaning",
                "This will:\n• Delete records older than 5 years\n• Remove orphaned records\n• Vacuum and optimize database\n\nContinue?"):
                return

            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cleaned_count = 0

            # Delete old payment records (>5 years)
            cursor.execute('''
            DELETE FROM payments
            WHERE date(payment_date) < date('now', '-5 years')
            ''')
            cleaned_count += cursor.rowcount

            # Delete old transaction records (>5 years)
            cursor.execute('''
            DELETE FROM financial_transactions
            WHERE date(transaction_date) < date('now', '-5 years')
            ''')
            cleaned_count += cursor.rowcount

            # Delete orphaned fee records (no associated student)
            cursor.execute('''
            DELETE FROM student_fees
            WHERE student_id NOT IN (SELECT student_id FROM students)
            ''')
            cleaned_count += cursor.rowcount

            # Optimize database
            cursor.execute('VACUUM')
            cursor.execute('ANALYZE')

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Database cleaned successfully!\n\n• Removed {cleaned_count} old records\n• Database optimized")

        except Exception as e:
            messagebox.showerror("Error", f"Database cleaning failed: {e}")


    def backup_database(self):
        """Backup finance database"""
        try:
            import shutil
            from datetime import datetime
            from tkinter import filedialog
            from pathlib import Path
            from university_system.modules.shared.constants import paths

            # Get database path
            db_path = str(paths.DEFAULT_DB_PATH)
            if not os.path.exists(db_path):
                messagebox.showerror("Error", "Database file not found")
                return

            # Determine backup directory
            # Find university_system root directory
            current_file = Path(__file__).resolve()
            university_system_root = None
            for parent in current_file.parents:
                if parent.name == 'university_system':
                    university_system_root = parent.parent
                    break

            if university_system_root:
                backup_dir = university_system_root / 'university_system' / 'backups'
            else:
                # Fallback to current directory if can't find university_system
                backup_dir = Path.cwd() / 'backups'

            # Create backup directory if it doesn't exist
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create default backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"finance_backup_{timestamp}.db"

            # Ask user where to save backup
            backup_path = filedialog.asksaveasfilename(
                title="Save Database Backup",
                defaultextension=".db",
                initialfile=default_filename,
                initialdir=str(backup_dir),
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )

            if not backup_path:
                return  # User cancelled

            # Copy database file
            shutil.copy2(db_path, backup_path)

            # Get file size
            file_size = os.path.getsize(backup_path) / (1024 * 1024)  # Convert to MB

            messagebox.showinfo("Success",
                f"Database backed up successfully!\n\n"
                f"Backup location: {backup_path}\n"
                f"Size: {file_size:.2f} MB\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            messagebox.showerror("Error", f"Database backup failed: {e}")


    def show_database_stats(self):
        """Show database statistics in a dialog"""
        try:
            from university_system.infrastructure.database.db import get_connection

            stats_window = tk.Toplevel(self.root)
            stats_window.title("Database Statistics")
            stats_window.geometry("600x400")
            stats_window.transient(self.root)
            stats_window.grab_set()

            # Create text widget to display stats
            text_frame = tk.Frame(stats_window)
            text_frame.pack(fill='both', expand=True, padx=20, pady=20)

            text_widget = tk.Text(text_frame, font=('Courier', 10))
            scrollbar = tk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            text_widget.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Get database statistics
            conn = get_connection()
            cursor = conn.cursor()

            stats_text = "DATABASE STATISTICS\n"
            stats_text += "=" * 50 + "\n\n"

            # Get table counts
            tables_to_check = ['students', 'payments', 'student_fees', 'fee_types',
                'scholarships', 'financial_aid', 'late_fees']

            for table in tables_to_check:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats_text += f"{table.replace('_', ' ').title()}: {count:,}\n"
                except Exception:
                    stats_text += f"{table.replace('_', ' ').title()}: Table not found\n"

            stats_text += "\n" + "=" * 50 + "\n"
            stats_text += "DATABASE FILE INFORMATION\n"
            stats_text += "=" * 50 + "\n\n"

            # Get database file path and info
            from university_system.modules.shared.constants import paths
            db_path = str(paths.DEFAULT_DB_PATH)

            if os.path.exists(db_path):
                file_size = os.path.getsize(db_path)
                file_size_mb = file_size / (1024 * 1024)
                stats_text += f"Database Path: {db_path}\n"
                stats_text += f"File Size: {file_size:,} bytes ({file_size_mb:.2f} MB)\n"

                # Get last modified time
                import time
                mod_time = os.path.getmtime(db_path)
                mod_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                stats_text += f"Last Modified: {mod_time_str}\n"

                # Get total records across all tables
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                stats_text += f"\nTotal Tables: {table_count}\n"
            else:
                stats_text += f"Database Path: {db_path}\n"
                stats_text += "Status: File not found!\n"

            conn.close()

            text_widget.insert('1.0', stats_text)
            text_widget.config(state='disabled')

            # Close button
            tk.Button(stats_window, text="Close", command=stats_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show database stats: {e}")


    def gui_complete_database_fix(self):
        """GUI wrapper for complete_database_fix"""
        if messagebox.askyesno("Confirm", "This will perform a complete database repair and initialization. Continue?"):
            try:
                self.update_status("Performing complete database fix...")

                def fix_database():
                    complete_database_fix()
                    messagebox.showinfo("Success", "Database fix completed successfully!")
                    self.update_system_status()
                    self.update_status("Database fix completed")

                thread = threading.Thread(target=fix_database)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror("Error", f"Database fix failed: {e}")


    def gui_quick_fix_database(self):
        """GUI wrapper for quick_fix_database"""
        if messagebox.askyesno("Confirm", "This will perform a quick database repair. Continue?"):
            try:
                self.update_status("Performing quick database fix...")

                def quick_fix():
                    quick_fix_database()
                    messagebox.showinfo("Success", "Quick database fix completed successfully!")
                    self.update_system_status()
                    self.update_status("Quick database fix completed")

                thread = threading.Thread(target=quick_fix)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror("Error", f"Quick database fix failed: {e}")


    def gui_ensure_database_exists(self):
        """GUI wrapper for ensure_database_exists"""
        try:
            ensure_database_exists()
            messagebox.showinfo("Success", "Database existence verified!")
            self.update_status("Database existence verified")

        except Exception as e:
            messagebox.showerror("Error", f"Database verification failed: {e}")


    def gui_verify_fix(self):
        """GUI wrapper for verify_fix"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            verify_fix()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window("Database Fix Verification", output)
            self.update_status("Database fix verification completed")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to verify fix: {e}")

    def update_status(self, message):
        """Update status bar"""
        if hasattr(self.gui, 'update_status'):
            self.gui.update_status(message)
        else:
            print(f"Status: {message}")

    def update_system_status(self):
        """Update system status"""
        if hasattr(self.gui, 'update_system_status'):
            self.gui.update_system_status()

    def show_text_window(self, title, content):
        """Show text content in a window"""
        try:
            text_window = tk.Toplevel(self.root)
            text_window.title(title)
            text_window.geometry("800x600")
            text_window.transient(self.root)

            # Create text widget with scrollbar
            text_frame = tk.Frame(text_window)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)

            text_widget = ScrolledText(text_frame, font=('Courier', 10), wrap='word')
            text_widget.pack(fill='both', expand=True)

            text_widget.insert('1.0', content)
            text_widget.config(state='disabled')

            # Close button
            tk.Button(text_window, text="Close", command=text_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show text window: {e}")
        
