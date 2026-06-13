"""Main Finance GUI - coordinates all manager classes"""

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
import io
import os

from education_system.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
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
from education_system.university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.infrastructure.logging.log_config import configure_logging, get_log_file
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
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def configure_logging(name=None):
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        from education_system.university_system.core import paths
        return str(paths.LOG_DIR / name)

try:
    from education_system.university_system.modules.domain.finance.core.financial_core import (
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
try:
    from education_system.university_system.modules.domain.finance.core.financial_core import (
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
        agency_performance_report, export_forecast_report, complete_database_fix,
        quick_fix_database, initialize_finance, detect_payment_fraud,
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

# Configure logging
log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')



# Import all manager classes
from education_system.university_system.modules.domain.finance.gui.finance.db_manager import DatabaseManager
from education_system.university_system.modules.domain.finance.gui.finance.layout import LayoutManager
from education_system.university_system.modules.domain.finance.gui.finance.dashboard import DashboardManager
from education_system.university_system.modules.domain.finance.gui.finance.budget_manager import BudgetManager
from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager import TransactionManager
from education_system.university_system.modules.domain.finance.gui.finance.invoice_manager import InvoiceManager
from education_system.university_system.modules.domain.finance.gui.finance.expense_manager import ExpenseManager
from education_system.university_system.modules.domain.finance.gui.finance.report_manager import ReportManager
from education_system.university_system.modules.domain.finance.gui.finance.analytics import AnalyticsManager
from education_system.university_system.modules.domain.finance.gui.finance.compliance import CollectionsManager
from education_system.university_system.modules.domain.finance.gui.finance.settings import SettingsManager
from education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager import RevenueSourceManager


class FinanceGUI:
    """Main Finance GUI class that coordinates all managers"""

    def __init__(self, root, auth=None):
        """
        Initialize Finance GUI.

        Args:
            root: Tkinter root window
            auth: Authentication instance (if None, will use get_auth())

        Raises:
            RuntimeError: If authentication system is not available
        """
        self.root = root
        self.conn = None
        self.finance_system = None

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            raise RuntimeError(
                _("finance.errors.auth_not_available")
            )

        # Initialize all manager classes
        self.db = DatabaseManager(self)
        self.layout = LayoutManager(self)
        self.dashboard = DashboardManager(self)
        self.budgets = BudgetManager(self)
        self.transactions = TransactionManager(self)
        self.invoices = InvoiceManager(self)
        self.expenses = ExpenseManager(self)
        self.reports = ReportManager(self)
        self.analytics = AnalyticsManager(self)
        self.collections = CollectionsManager(self)
        self.settings = SettingsManager(self)
        self.revenue_source = RevenueSourceManager(self)

        # Initialize system
        self.initialize_system()
        self.layout.setup_styles()
        self.layout.create_main_interface()
        self.dashboard.refresh_dashboard()

    def set_auth(self, auth):
        """Set the authentication manager"""
        self.auth = auth

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth:
                if hasattr(self.auth, 'current_user') and self.auth.current_user:
                    role = self.auth.current_user.get('role', '').lower()
                    return role
                elif hasattr(self.auth, 'user_role'):
                    return self.auth.user_role.lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def initialize_system(self):
        """Initialize the finance system"""
        def init_thread():
            try:
                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status(_("finance.status.initializing"))

                # Initialize database connection
                try:
                    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
                    # Just ensure we can connect to the database
                    self.conn = get_connection()

                    # Try to initialize enhanced finance tables if available
                    try:
                        from education_system.university_system.modules.domain.finance.core.financial_core import init_enhanced_finance_db
                        init_enhanced_finance_db()
                    except ImportError:
                        # Finance core module not available, just ensure basic connection works
                        pass
                    except Exception as e:
                        print(f"Warning: Could not initialize enhanced finance tables: {e}")

                    # Ensure student finance account tables exist
                    try:
                        from education_system.university_system.modules.shared.utils.finance_integration import _ensure_finance_tables_exist
                        _ensure_finance_tables_exist()
                    except ImportError:
                        pass
                    except Exception as e:
                        print(f"Warning: Could not initialize student finance tables: {e}")

                except Exception as e:
                    print(f"Warning: Database initialization issue: {e}")

                # Initialize auth if needed
                global auth
                auth = self.auth

                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status(_("finance.status.initialized_success"))
                if hasattr(self, 'layout') and hasattr(self.layout, 'connection_label'):
                    self.layout.connection_label.config(text=_("finance.status.connected"))

                # Load initial data
                if hasattr(self, 'load_initial_data'):
                    self.root.after(1000, self.load_initial_data)

            except Exception as e:
                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status(_("finance.status.init_failed").format(error=str(e)))
                if hasattr(self, 'layout') and hasattr(self.layout, 'connection_label'):
                    self.layout.connection_label.config(text=_("finance.status.error"))
                messagebox.showerror(_("finance.errors.init_error_title"), _("finance.errors.init_failed").format(error=str(e)))

        threading.Thread(target=init_thread, daemon=True).start()


    def run(self):
        """Run the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Application terminated by user")
            self.root.quit()
        except Exception as e:
            messagebox.showerror(_("finance.errors.app_error_title"), _("finance.errors.unexpected_error").format(error=e))


    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()


    def create_students_tab(self):
        """Create students management tab"""
        # Access content_frame through layout manager
        content_frame = self.layout.content_frame if hasattr(self.layout, 'content_frame') else self.root
        students_frame = tk.Frame(content_frame, bg='white')

        # Store in layout's tab_frames
        if hasattr(self.layout, 'tab_frames'):
            self.layout.tab_frames['students'] = students_frame
        else:
            if not hasattr(self, 'tab_frames'):
                self.tab_frames = {}
            self.tab_frames['students'] = students_frame

        # Students toolbar
        toolbar = tk.Frame(students_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        # Access colors through layout manager
        colors = self.layout.colors if hasattr(self.layout, 'colors') else {
            'success': '#27ae60', 'warning': '#f39c12', 'danger': '#e74c3c',
            'secondary': '#3498db', 'dark': '#2c3e50'
        }

        tk.Button(toolbar, text=_("finance.buttons.search"), command=self.search_students,
                 bg=colors['secondary'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance.buttons.view_finances"), command=self.view_student_finances,
                 bg=colors['dark'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="Status Letters", command=self._open_status_letters,
                 bg=colors.get('warning', '#f39c12'), fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)

        # Search frame
        search_frame = tk.Frame(students_frame, bg='white')
        search_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(search_frame, text=_("finance.labels.search"), bg='white').pack(side='left')
        self.student_search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.student_search_var, width=30)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<KeyRelease>', self.on_student_search)

        # Students table
        self.create_students_table(students_frame)

        # Load students data
        self.refresh_students()


    def create_students_table(self, parent):
        """Create students table"""
        table_frame = tk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('student_id', 'name', 'email', 'course', 'status', 'balance')
        self.students_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        self.students_tree.heading('student_id', text=_("finance.columns.student_id"))
        self.students_tree.heading('name', text=_("finance.columns.name"))
        self.students_tree.heading('email', text=_("finance.columns.email"))
        self.students_tree.heading('course', text=_("finance.columns.course"))
        self.students_tree.heading('status', text=_("finance.columns.status"))
        self.students_tree.heading('balance', text=_("finance.columns.balance"))

        for col in columns:
            self.students_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=v_scroll.set)

        self.students_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')


    def refresh_students(self):
        """Refresh students data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT s.student_id, s.first_name || ' ' || s.last_name as name,
                       s.email_address, s.course, s.status,
                       COALESCE(SUM(sf.amount) - SUM(COALESCE(pa.amount, 0)), 0) as balance
                FROM students s
                LEFT JOIN student_fees sf ON s.student_id = sf.student_id
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                GROUP BY s.student_id
                ORDER BY s.last_name, s.first_name
                ''')

                students = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_students_table(students))

            except Exception as e:
                print(f"Error refreshing students: {e}")

        refresh_thread()


    def update_students_table(self, students):
        """Update students table"""
        for item in self.students_tree.get_children():
            self.students_tree.delete(item)

        for student in students:
            # Format balance
            balance = f"£{student[5]:.2f}" if student[5] else "£0.00"
            display_data = student[:5] + (balance,)
            self.students_tree.insert('', 'end', values=display_data)


    def on_student_search(self, event):
        """Handle student search"""
        search_term = self.student_search_var.get().lower()
        if len(search_term) < 2:
            self.refresh_students()
            return

        def search_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT s.student_id, s.first_name || ' ' || s.last_name as name,
                       s.email_address, s.course, s.status,
                       COALESCE(SUM(sf.amount) - SUM(COALESCE(pa.amount, 0)), 0) as balance
                FROM students s
                LEFT JOIN student_fees sf ON s.student_id = sf.student_id
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                WHERE LOWER(s.first_name || ' ' || s.last_name) LIKE ?
                   OR LOWER(s.student_id) LIKE ?
                   OR LOWER(s.email_address) LIKE ?
                GROUP BY s.student_id
                ORDER BY s.last_name, s.first_name
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

                students = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_students_table(students))

            except Exception as e:
                print(f"Error searching students: {e}")

        threading.Thread(target=search_thread, daemon=True).start()


    def search_students(self):
        """Search students dialog"""
        search_term = simpledialog.askstring(_("finance.dialogs.search_students_title"), _("finance.dialogs.search_students_prompt"))
        if search_term:
            self.student_search_var.set(search_term)
            self.on_student_search(None)


    def _open_status_letters(self):
        """Launch the Enrolment Verification / Status Letters GUI.

        Council-tax exemption, mortgage / lender, and bank-account
        opening letters all hang off tuition standing — natural fit
        for the Bursar's toolbar."""
        try:
            from education_system.university_system.modules.domain.student_affairs.student_app.documentation.gui.documentation_gui import DocumentationGUI
            DocumentationGUI(parent=self.root, auth=self.auth)
        except Exception as exc:
            messagebox.showerror(_("common.error"), f"Status Letters not available: {exc}")


    def view_student_finances(self):
        """View financial details for selected student with access control"""
        # Check if user is logged in
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("finance.errors.must_be_logged_in"))
            return

        current_user = self.auth.current_user
        user_role = current_user.get('role', '').lower()
        current_user_id = current_user.get('student_id') or current_user.get('user_id')

        # Determine which student to view
        student_id = None
        student_name = None

        if user_role == 'student':
            # Students can only view their own finances
            student_id = current_user_id
            student_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            if not student_name:
                student_name = current_user.get('username', 'Student')
        elif user_role in ['admin', 'staff', 'instructor']:
            # Admin/staff can select from list or view any student
            if hasattr(self, 'students_tree'):
                selection = self.students_tree.selection()
                if selection:
                    student_id = self.students_tree.item(selection[0])['values'][0]
                    student_name = self.students_tree.item(selection[0])['values'][1]
                else:
                    # Allow admin to enter student ID directly
                    student_id = simpledialog.askstring(_("finance.dialogs.view_finances_title"),
                                                        _("finance.dialogs.enter_student_id"),
                                                        parent=self.root)
                    if not student_id:
                        return
            else:
                student_id = simpledialog.askstring(_("finance.dialogs.view_finances_title"),
                                                    _("finance.dialogs.enter_student_id"),
                                                    parent=self.root)
                if not student_id:
                    return
        else:
            messagebox.showerror(_("finance.errors.access_denied_title"), _("finance.errors.no_permission_view"))
            return

        if not student_id:
            messagebox.showwarning(_("common.error"), _("finance.errors.cannot_determine_student_id"))
            return

        # Get student name if not already set
        if not student_name:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                result = cursor.fetchone()
                if result:
                    student_name = f"{result[0]} {result[1]}"
                else:
                    student_name = f"Student {student_id}"
                conn.close()
            except Exception:
                student_name = f"Student {student_id}"

        # Open the finance details dialog
        self._show_student_finance_dialog(student_id, student_name, user_role)

    def _show_student_finance_dialog(self, student_id, student_name, user_role):
        """Show detailed finance dialog for a student"""
        finance_dialog = tk.Toplevel(self.root)
        finance_dialog.title(_("finance.dialogs.financial_details_title").format(name=student_name))
        finance_dialog.geometry("900x700")
        finance_dialog.transient(self.root)

        ttk.Label(finance_dialog, text=_("finance.dialogs.student_financial_details").format(name=student_name, id=student_id),
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Create notebook for different financial sections
        notebook = ttk.Notebook(finance_dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Overview
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text=_("finance.tabs.overview"))
        self._create_finance_overview_tab(overview_frame, student_id)

        # Tab 2: Finance Account (for top-up, use, withdraw)
        account_frame = ttk.Frame(notebook)
        notebook.add(account_frame, text=_("finance.tabs.finance_account"))
        self._create_finance_account_tab(account_frame, student_id, student_name, user_role, finance_dialog)

        # Tab 3: Fees
        fees_frame = ttk.Frame(notebook)
        notebook.add(fees_frame, text=_("finance.tabs.fees"))
        self._create_fees_tab(fees_frame, student_id)

        # Tab 4: Payments
        payments_frame = ttk.Frame(notebook)
        notebook.add(payments_frame, text=_("finance.tabs.payments"))
        self._create_payments_tab(payments_frame, student_id)

        # Tab 5: Transaction History
        transactions_frame = ttk.Frame(notebook)
        notebook.add(transactions_frame, text=_("finance.tabs.account_history"))
        self._create_account_transactions_tab(transactions_frame, student_id)

        # Tab 6: Refunds
        refunds_frame = ttk.Frame(notebook)
        notebook.add(refunds_frame, text=_("finance.tabs.refunds", default="Refunds"))
        self._create_refunds_tab(refunds_frame, student_id)

        # Close button
        ttk.Button(finance_dialog, text=_("common.close"), command=finance_dialog.destroy).pack(pady=10)

    def _create_finance_overview_tab(self, parent, student_id):
        """Create overview tab showing financial summary"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get fee summary
            cursor.execute('''
                SELECT
                    COALESCE(SUM(sf.amount), 0) as total_fees,
                    COALESCE(SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END), 0) as paid_amount,
                    COALESCE(SUM(CASE WHEN sf.status != 'paid' THEN sf.amount ELSE 0 END), 0) as outstanding
                FROM student_fees sf
                WHERE sf.student_id = ?
            ''', (student_id,))
            fee_summary = cursor.fetchone()

            # Get account balance
            cursor.execute('''
                SELECT COALESCE(balance, 0) FROM student_finance_accounts WHERE student_id = ?
            ''', (student_id,))
            account_result = cursor.fetchone()
            account_balance = account_result[0] if account_result else 0.0

            # Display summary
            summary_frame = ttk.LabelFrame(parent, text=_("finance.labels.financial_summary"), padding=20)
            summary_frame.pack(fill='x', padx=10, pady=10)

            summary_text = f"""
{_("finance.labels.total_fees")}           £{fee_summary[0]:,.2f}
{_("finance.labels.paid")}                 £{fee_summary[1]:,.2f}
{_("finance.labels.outstanding")}          £{fee_summary[2]:,.2f}

{_("finance.labels.account_balance")}      £{account_balance:,.2f}
"""
            ttk.Label(summary_frame, text=summary_text, font=('Courier', 11)).pack(anchor='w')

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=_("finance.errors.error_loading_data").format(error=e), foreground='red').pack(pady=20)

    def _create_finance_account_tab(self, parent, student_id, student_name, user_role, dialog):
        """Create enhanced finance account tab with comprehensive features"""
        # Ensure account exists
        self._ensure_student_account_exists(student_id)

        # Create main scrollable container
        main_canvas = tk.Canvas(parent, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        main_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Variables for dynamic updates
        balance_var = tk.StringVar(value="Loading...")
        total_deposited_var = tk.StringVar(value="£0.00")
        total_spent_var = tk.StringVar(value="£0.00")
        transaction_count_var = tk.StringVar(value="0")

        def refresh_all_data():
            """Refresh balance and statistics"""
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get balance
                cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                result = cursor.fetchone()
                balance = result[0] if result else 0.0
                balance_var.set(f"£{balance:,.2f}")

                # Get statistics
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_transactions,
                        COALESCE(SUM(CASE WHEN transaction_type IN ('top_up', 'deposit', 'refund') THEN amount ELSE 0 END), 0) as total_deposited,
                        COALESCE(SUM(CASE WHEN transaction_type IN ('use', 'withdrawal', 'payment') THEN amount ELSE 0 END), 0) as total_spent
                    FROM transactions
                    WHERE source_type = 'student_finance' AND student_id = ?
                ''', (student_id,))
                stats = cursor.fetchone()

                if stats:
                    transaction_count_var.set(str(stats[0]))
                    total_deposited_var.set(f"£{stats[1]:,.2f}")
                    total_spent_var.set(f"£{stats[2]:,.2f}")

                # Refresh transaction list
                load_transactions()

                conn.close()
            except Exception as e:
                balance_var.set(f"Error: {e}")

        # ==== HEADER SECTION ====
        header_frame = tk.Frame(scrollable_frame, bg='#2c3e50')
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame, text=f"💳 {student_name}'s Finance Account",
                font=('Arial', 16, 'bold'), bg='#2c3e50', fg='white', pady=15).pack()

        # ==== BALANCE CARD ====
        balance_card = tk.Frame(scrollable_frame, bg='#27ae60', relief='raised', bd=2)
        balance_card.pack(fill='x', padx=20, pady=10)

        tk.Label(balance_card, text=_("student_dashboard.labels.current_balance"),
                font=('Arial', 12, 'bold'), bg='#27ae60', fg='white').pack(pady=(15, 5))
        tk.Label(balance_card, textvariable=balance_var,
                font=('Arial', 32, 'bold'), bg='#27ae60', fg='white').pack(pady=5)

        refresh_btn = tk.Button(balance_card, text=_("student_dashboard.buttons.refresh"), command=refresh_all_data,
                               bg='#229954', fg='white', font=('Arial', 10, 'bold'),
                               relief='flat', padx=20, pady=5, cursor='hand2')
        refresh_btn.pack(pady=(5, 15))

        # ==== STATISTICS CARDS ====
        stats_container = tk.Frame(scrollable_frame, bg='white')
        stats_container.pack(fill='x', padx=20, pady=10)

        # Total Deposited Card
        deposit_card = tk.Frame(stats_container, bg='#3498db', relief='raised', bd=2)
        deposit_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(deposit_card, text=_("student_dashboard.labels.total_deposited"), font=('Arial', 10, 'bold'),
                bg='#3498db', fg='white').pack(pady=(10, 5))
        tk.Label(deposit_card, textvariable=total_deposited_var, font=('Arial', 18, 'bold'),
                bg='#3498db', fg='white').pack(pady=(0, 10))

        # Total Spent Card
        spent_card = tk.Frame(stats_container, bg='#e74c3c', relief='raised', bd=2)
        spent_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(spent_card, text=_("student_dashboard.labels.total_spent"), font=('Arial', 10, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(10, 5))
        tk.Label(spent_card, textvariable=total_spent_var, font=('Arial', 18, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(0, 10))

        # Transactions Count Card
        count_card = tk.Frame(stats_container, bg='#f39c12', relief='raised', bd=2)
        count_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(count_card, text=_("student_dashboard.labels.transactions"), font=('Arial', 10, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(10, 5))
        tk.Label(count_card, textvariable=transaction_count_var, font=('Arial', 18, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(0, 10))

        # ==== QUICK ACTIONS ====
        actions_frame = ttk.LabelFrame(scrollable_frame, text=_("student_dashboard.labels.quick_actions"), padding=15)
        actions_frame.pack(fill='x', padx=20, pady=15)

        # Main action buttons
        main_actions = tk.Frame(actions_frame, bg='white')
        main_actions.pack(fill='x', pady=(0, 10))

        def top_up_account():
            self._top_up_account(student_id, student_name, refresh_all_data)

        def use_balance():
            self._use_account_balance(student_id, student_name, refresh_all_data)

        def withdraw_balance():
            self._withdraw_from_account(student_id, student_name, refresh_all_data, user_role)

        tk.Button(main_actions, text=_("student_dashboard.buttons.top_up"), command=top_up_account,
                 bg='#27ae60', fg='white', font=('Arial', 11, 'bold'),
                 relief='flat', padx=20, pady=10, cursor='hand2').pack(side='left', padx=5, expand=True, fill='x')
        tk.Button(main_actions, text=_("student_dashboard.buttons.use_balance"), command=use_balance,
                 bg='#3498db', fg='white', font=('Arial', 11, 'bold'),
                 relief='flat', padx=20, pady=10, cursor='hand2').pack(side='left', padx=5, expand=True, fill='x')
        tk.Button(main_actions, text=_("student_dashboard.buttons.withdraw"), command=withdraw_balance,
                 bg='#e74c3c', fg='white', font=('Arial', 11, 'bold'),
                 relief='flat', padx=20, pady=10, cursor='hand2').pack(side='left', padx=5, expand=True, fill='x')

        # Quick amount buttons
        tk.Label(actions_frame, text=_("student_dashboard.labels.quick_topup_amounts"), font=('Arial', 9, 'bold')).pack(anchor='w', pady=(10, 5))
        quick_amounts = tk.Frame(actions_frame, bg='white')
        quick_amounts.pack(fill='x')

        def quick_top_up(amount):
            """Quick top-up with preset amount"""
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import top_up_student_finance_account
                processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'

                result = top_up_student_finance_account(
                    student_id=student_id,
                    amount=amount,
                    payment_method='quick_topup',
                    processed_by=processed_by
                )

                if result['success']:
                    messagebox.showinfo("Success", f"✓ Added £{amount:.2f} to account\nNew balance: £{result['new_balance']:.2f}")
                    refresh_all_data()
                else:
                    messagebox.showerror("Error", result['message'])
            except Exception as e:
                messagebox.showerror("Error", _("student_dashboard.messages.quick_topup_failed").format(e=e))

        for amount in [10, 20, 50, 100]:
            tk.Button(quick_amounts, text=f"£{amount}", command=lambda amt=amount: quick_top_up(amt),
                     bg='#ecf0f1', fg='#2c3e50', font=('Arial', 10, 'bold'),
                     relief='flat', padx=15, pady=5, cursor='hand2').pack(side='left', padx=3)

        # ==== RECENT TRANSACTIONS ====
        trans_frame = ttk.LabelFrame(scrollable_frame, text=_("student_dashboard.labels.recent_transactions"), padding=10)
        trans_frame.pack(fill='both', expand=True, padx=20, pady=15)

        # Filter buttons
        filter_frame = tk.Frame(trans_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        filter_var = tk.StringVar(value='all')

        def apply_filter():
            load_transactions(filter_var.get())

        tk.Radiobutton(filter_frame, text=_("student_dashboard.filters.all"), variable=filter_var, value='all',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text=_("student_dashboard.filters.deposits"), variable=filter_var, value='deposit',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text=_("student_dashboard.filters.spending"), variable=filter_var, value='spend',
                      command=apply_filter).pack(side='left', padx=5)

        # Export button
        def export_transactions():
            try:
                import csv
                from tkinter import filedialog

                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"finance_account_{student_id}.csv"
                )

                if not filename:
                    return

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT created_at, transaction_type, amount, balance_after, description
                    FROM transactions
                    WHERE source_type = 'student_finance' AND student_id = ?
                    ORDER BY created_at DESC
                ''', (student_id,))

                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Date/Time', 'Type', 'Amount', 'Balance After', 'Description'])
                    writer.writerows(cursor.fetchall())

                conn.close()
                messagebox.showinfo("Success", _("student_dashboard.messages.transactions_exported").format(filename=filename))
            except Exception as e:
                messagebox.showerror("Error", _("student_dashboard.messages.export_failed").format(e=e))

        tk.Button(filter_frame, text=_("student_dashboard.buttons.export_csv"), command=export_transactions,
                 bg='#34495e', fg='white', font=('Arial', 9, 'bold'),
                 relief='flat', padx=10, pady=3, cursor='hand2').pack(side='right', padx=5)

        # Transaction table
        trans_table_frame = tk.Frame(trans_frame)
        trans_table_frame.pack(fill='both', expand=True)

        columns = ('Date', 'Type', 'Amount', 'Balance', 'Description')
        trans_tree = ttk.Treeview(trans_table_frame, columns=columns, show='headings', height=10)

        trans_tree.heading('Date', text='Date/Time')
        trans_tree.heading('Type', text='Type')
        trans_tree.heading('Amount', text='Amount')
        trans_tree.heading('Balance', text='Balance After')
        trans_tree.heading('Description', text='Description')

        trans_tree.column('Date', width=150, anchor='center')
        trans_tree.column('Type', width=100, anchor='center')
        trans_tree.column('Amount', width=100, anchor='e')
        trans_tree.column('Balance', width=100, anchor='e')
        trans_tree.column('Description', width=250, anchor='w')

        trans_scrollbar = ttk.Scrollbar(trans_table_frame, orient='vertical', command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_scrollbar.set)

        trans_tree.pack(side='left', fill='both', expand=True)
        trans_scrollbar.pack(side='right', fill='y')

        def load_transactions(filter_type='all'):
            """Load and display transactions"""
            for item in trans_tree.get_children():
                trans_tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                if filter_type == 'deposit':
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ? AND transaction_type IN ('top_up', 'deposit', 'refund')
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))
                elif filter_type == 'spend':
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ? AND transaction_type IN ('use', 'withdrawal', 'payment')
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))
                else:
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ?
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))

                for row in cursor.fetchall():
                    trans_type = (row[1] or '').replace('_', ' ').title()
                    amount = float(row[2]) if row[2] is not None else 0.0
                    balance = float(row[3]) if row[3] is not None else 0.0

                    # Format amount with +/- indicator
                    if row[1] in ['use', 'withdrawal', 'payment']:
                        amount_str = f"-\u00a3{amount:.2f}"
                        tag = 'negative'
                    else:
                        amount_str = f"+\u00a3{amount:.2f}"
                        tag = 'positive'

                    trans_tree.insert('', 'end', values=(
                        row[0] or '', trans_type, amount_str, f"\u00a3{balance:.2f}", row[4] or ''
                    ), tags=(tag,))

                # Configure tag colors
                trans_tree.tag_configure('positive', foreground='#27ae60')
                trans_tree.tag_configure('negative', foreground='#e74c3c')

                conn.close()
            except Exception as e:
                print(f"Error loading transactions: {e}")

        # Initial data load
        refresh_all_data()

    def _ensure_student_account_exists(self, student_id):
        """Ensure a finance account exists for the student"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO student_finance_accounts (student_id, balance)
                VALUES (?, 0.00)
            ''', (student_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error creating student account: {e}")

    def _top_up_account(self, student_id, student_name, refresh_callback):
        """Top up student finance account"""
        top_up_dialog = tk.Toplevel(self.root)
        top_up_dialog.title(_("finance.dialogs.top_up_title").format(name=student_name))
        top_up_dialog.geometry("400x300")
        top_up_dialog.transient(self.root)
        top_up_dialog.grab_set()

        ttk.Label(top_up_dialog, text=_("finance.labels.top_up_amount"),
                 font=('Arial', 12)).pack(pady=20)

        amount_entry = ttk.Entry(top_up_dialog, width=20, font=('Arial', 14))
        amount_entry.pack(pady=10)
        amount_entry.focus()

        ttk.Label(top_up_dialog, text=_("finance.labels.payment_method")).pack(pady=5)
        method_var = tk.StringVar(value='card')
        method_combo = ttk.Combobox(top_up_dialog, textvariable=method_var,
                                    values=['card', 'bank_transfer', 'cash', 'online'],
                                    state='readonly', width=18)
        method_combo.pack(pady=5)

        def process_top_up():
            raw_amount = amount_entry.get().strip()
            if not raw_amount:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=top_up_dialog)
                return
            try:
                amount = float(raw_amount)
                if amount <= 0:
                    messagebox.showerror(_("common.error"), _("finance.errors.amount_must_be_positive"), parent=top_up_dialog)
                    return

                # Use centralized top-up function which handles email notifications
                try:
                    from education_system.university_system.modules.shared.utils.finance_integration import top_up_student_finance_account
                    processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'

                    result = top_up_student_finance_account(
                        student_id=student_id,
                        amount=amount,
                        payment_method=method_var.get(),
                        processed_by=processed_by
                    )

                    if result['success']:
                        email_status = _("finance.messages.confirmation_email_sent") if result.get('email_sent') else ""
                        messagebox.showinfo(_("common.success"),
                            _("finance.messages.top_up_success").format(amount=amount, balance=result['new_balance'], email_status=email_status),
                            parent=top_up_dialog)
                        top_up_dialog.destroy()
                        refresh_callback()
                    else:
                        messagebox.showerror(_("common.error"), result['message'], parent=top_up_dialog)

                except ImportError:
                    # Fallback to direct database update if integration not available
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                                 (student_id,))
                    db_result = cursor.fetchone()
                    if not db_result:
                        messagebox.showerror(_("common.error"), _("finance.errors.account_not_found"), parent=top_up_dialog)
                        conn.close()
                        return

                    account_id, current_balance = db_result
                    new_balance = current_balance + amount

                    cursor.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = datetime('now')
                        WHERE student_id = ?
                    ''', (new_balance, student_id))

                    processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'
                    cursor.execute('''
                        INSERT INTO transactions
                        (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                         description, processed_by)
                        VALUES ('student_finance', ?, ?, 'top_up', ?, ?, ?, ?, ?)
                    ''', (account_id, student_id, amount, current_balance, new_balance,
                         f'Top up via {method_var.get()}', processed_by))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("common.success"), _("finance.messages.top_up_success_simple").format(amount=amount, balance=new_balance),
                                       parent=top_up_dialog)
                    top_up_dialog.destroy()
                    refresh_callback()

            except ValueError:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=top_up_dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance.errors.top_up_failed").format(error=e), parent=top_up_dialog)

        ttk.Button(top_up_dialog, text=_("finance.buttons.process_top_up"), command=process_top_up).pack(pady=20)
        ttk.Button(top_up_dialog, text=_("common.cancel"), command=top_up_dialog.destroy).pack()

    def _use_account_balance(self, student_id, student_name, refresh_callback):
        """Use balance from student finance account (for services, fees, etc.)"""
        use_dialog = tk.Toplevel(self.root)
        use_dialog.title(_("finance.dialogs.use_balance_title").format(name=student_name))
        use_dialog.geometry("400x350")
        use_dialog.transient(self.root)
        use_dialog.grab_set()

        # Get current balance
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            result = cursor.fetchone()
            current_balance = result[0] if result else 0.0
            conn.close()
        except Exception:
            current_balance = 0.0

        ttk.Label(use_dialog, text=_("finance.labels.current_balance").format(balance=current_balance),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(use_dialog, text=_("finance.labels.amount_to_use")).pack(pady=5)
        amount_entry = ttk.Entry(use_dialog, width=20, font=('Arial', 14))
        amount_entry.pack(pady=5)
        amount_entry.focus()

        ttk.Label(use_dialog, text=_("finance.labels.purpose")).pack(pady=5)
        purpose_var = tk.StringVar(value='fee_payment')
        purpose_combo = ttk.Combobox(use_dialog, textvariable=purpose_var,
                                     values=['fee_payment', 'library_fine', 'meal_purchase',
                                            'printing', 'club_fee', 'other'],
                                     state='readonly', width=18)
        purpose_combo.pack(pady=5)

        ttk.Label(use_dialog, text=_("finance.labels.description_optional")).pack(pady=5)
        desc_entry = ttk.Entry(use_dialog, width=30)
        desc_entry.pack(pady=5)

        def process_use():
            raw_amount = amount_entry.get().strip()
            if not raw_amount:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=use_dialog)
                return
            try:
                amount = float(raw_amount)
                if amount <= 0:
                    messagebox.showerror(_("common.error"), _("finance.errors.amount_must_be_positive"), parent=use_dialog)
                    return
                if amount > current_balance:
                    messagebox.showerror(_("common.error"), _("finance.errors.insufficient_balance"), parent=use_dialog)
                    return

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                             (student_id,))
                result = cursor.fetchone()
                account_id, balance = result
                new_balance = balance - amount

                # Update balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = datetime('now')
                    WHERE student_id = ?
                ''', (new_balance, student_id))

                # Record transaction
                processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'
                description = desc_entry.get() or f'{purpose_var.get().replace("_", " ").title()}'
                cursor.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                     description, processed_by)
                    VALUES ('student_finance', ?, ?, 'use', ?, ?, ?, ?, ?)
                ''', (account_id, student_id, amount, balance, new_balance, description, processed_by))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("finance.messages.use_balance_success").format(amount=amount, balance=new_balance),
                                   parent=use_dialog)
                use_dialog.destroy()
                refresh_callback()

            except ValueError:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=use_dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance.errors.transaction_failed").format(error=e), parent=use_dialog)

        ttk.Button(use_dialog, text=_("finance.buttons.confirm_use"), command=process_use).pack(pady=20)
        ttk.Button(use_dialog, text=_("common.cancel"), command=use_dialog.destroy).pack()

    def _withdraw_from_account(self, student_id, student_name, refresh_callback, user_role):
        """Withdraw funds from student finance account"""
        withdraw_dialog = tk.Toplevel(self.root)
        withdraw_dialog.title(_("finance.dialogs.withdraw_title").format(name=student_name))
        withdraw_dialog.geometry("400x350")
        withdraw_dialog.transient(self.root)
        withdraw_dialog.grab_set()

        # Get current balance
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            result = cursor.fetchone()
            current_balance = result[0] if result else 0.0
            conn.close()
        except Exception:
            current_balance = 0.0

        ttk.Label(withdraw_dialog, text=_("finance.labels.current_balance").format(balance=current_balance),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(withdraw_dialog, text=_("finance.labels.withdrawal_amount")).pack(pady=5)
        amount_entry = ttk.Entry(withdraw_dialog, width=20, font=('Arial', 14))
        amount_entry.pack(pady=5)
        amount_entry.focus()

        ttk.Label(withdraw_dialog, text=_("finance.labels.withdrawal_method")).pack(pady=5)
        method_var = tk.StringVar(value='bank_transfer')
        method_combo = ttk.Combobox(withdraw_dialog, textvariable=method_var,
                                    values=['bank_transfer', 'cash', 'cheque'],
                                    state='readonly', width=18)
        method_combo.pack(pady=5)

        ttk.Label(withdraw_dialog, text=_("finance.labels.reason_optional")).pack(pady=5)
        reason_entry = ttk.Entry(withdraw_dialog, width=30)
        reason_entry.pack(pady=5)

        def process_withdrawal():
            raw_amount = amount_entry.get().strip()
            if not raw_amount:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=withdraw_dialog)
                return
            try:
                amount = float(raw_amount)
                if amount <= 0:
                    messagebox.showerror(_("common.error"), _("finance.errors.amount_must_be_positive"), parent=withdraw_dialog)
                    return
                if amount > current_balance:
                    messagebox.showerror(_("common.error"), _("finance.errors.insufficient_balance"), parent=withdraw_dialog)
                    return

                # Confirm withdrawal
                if not messagebox.askyesno(_("finance.dialogs.confirm_withdrawal_title"),
                                          _("finance.dialogs.confirm_withdrawal_message").format(amount=amount, method=method_var.get()),
                                          parent=withdraw_dialog):
                    return

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                             (student_id,))
                result = cursor.fetchone()
                account_id, balance = result
                new_balance = balance - amount

                # Update balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = datetime('now')
                    WHERE student_id = ?
                ''', (new_balance, student_id))

                # Record transaction
                processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'
                description = reason_entry.get() or f'Withdrawal via {method_var.get()}'
                cursor.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                     description, processed_by)
                    VALUES ('student_finance', ?, ?, 'withdrawal', ?, ?, ?, ?, ?)
                ''', (account_id, student_id, amount, balance, new_balance, description, processed_by))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("finance.messages.withdrawal_success").format(amount=amount, balance=new_balance),
                                   parent=withdraw_dialog)
                withdraw_dialog.destroy()
                refresh_callback()

            except ValueError:
                messagebox.showerror(_("common.error"), _("finance.errors.enter_valid_amount"), parent=withdraw_dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance.errors.withdrawal_failed").format(error=e), parent=withdraw_dialog)

        ttk.Button(withdraw_dialog, text=_("finance.buttons.process_withdrawal"), command=process_withdrawal).pack(pady=20)
        ttk.Button(withdraw_dialog, text=_("common.cancel"), command=withdraw_dialog.destroy).pack()

    def _create_fees_tab(self, parent, student_id):
        """Create fees tab"""
        fees_tree = ttk.Treeview(parent, columns=('ID', 'Description', 'Amount', 'Due Date', 'Status'),
                                show='headings', height=15)
        fees_tree.heading('ID', text=_("finance.columns.fee_id"))
        fees_tree.heading('Description', text=_("finance.columns.description"))
        fees_tree.heading('Amount', text=_("finance.columns.amount"))
        fees_tree.heading('Due Date', text=_("finance.columns.due_date"))
        fees_tree.heading('Status', text=_("finance.columns.status"))

        for col in ('ID', 'Description', 'Amount', 'Due Date', 'Status'):
            fees_tree.column(col, width=140)

        fees_tree.pack(fill='both', expand=True, padx=5, pady=5)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.due_date, sf.status
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ?
                ORDER BY sf.due_date DESC
            ''', (student_id,))

            for row in cursor.fetchall():
                status = _("finance.status.paid") if row[4] == 'paid' else _("finance.status.outstanding")
                fees_tree.insert('', 'end', values=(row[0], row[1], f"£{row[2]:.2f}", row[3], status))

            conn.close()
        except Exception as e:
            ttk.Label(parent, text=_("finance.errors.error_loading_fees").format(error=e), foreground='red').pack()

    def _create_payments_tab(self, parent, student_id):
        """Create payments tab"""
        payments_tree = ttk.Treeview(parent, columns=('ID', 'Amount', 'Date', 'Method', 'Reference'),
                                    show='headings', height=15)
        payments_tree.heading('ID', text=_("finance.columns.payment_id"))
        payments_tree.heading('Amount', text=_("finance.columns.amount"))
        payments_tree.heading('Date', text=_("finance.columns.date"))
        payments_tree.heading('Method', text=_("finance.columns.method"))
        payments_tree.heading('Reference', text=_("finance.columns.reference"))

        for col in ('ID', 'Amount', 'Date', 'Method', 'Reference'):
            payments_tree.column(col, width=140)

        payments_tree.pack(fill='both', expand=True, padx=5, pady=5)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT payment_id, amount, payment_date, payment_method, transaction_id
                FROM payments
                WHERE student_id = ?
                ORDER BY payment_date DESC
            ''', (student_id,))

            for row in cursor.fetchall():
                payments_tree.insert('', 'end', values=(row[0], f"£{row[1]:.2f}", row[2], row[3] or 'N/A', row[4] or 'N/A'))

            conn.close()
        except Exception as e:
            ttk.Label(parent, text=_("finance.errors.error_loading_payments").format(error=e), foreground='red').pack()

    def _create_account_transactions_tab(self, parent, student_id):
        """Create account transaction history tab"""
        trans_tree = ttk.Treeview(parent,
                                  columns=('Date', 'Type', 'Amount', 'Balance After', 'Description'),
                                  show='headings', height=15)
        trans_tree.heading('Date', text=_("finance.columns.date"))
        trans_tree.heading('Type', text=_("finance.columns.type"))
        trans_tree.heading('Amount', text=_("finance.columns.amount"))
        trans_tree.heading('Balance After', text=_("finance.columns.balance_after"))
        trans_tree.heading('Description', text=_("finance.columns.description"))

        trans_tree.column('Date', width=150)
        trans_tree.column('Type', width=100)
        trans_tree.column('Amount', width=100)
        trans_tree.column('Balance After', width=120)
        trans_tree.column('Description', width=200)

        trans_tree.pack(fill='both', expand=True, padx=5, pady=5)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT created_at, transaction_type, amount, balance_after, description
                FROM transactions
                WHERE source_type = 'student_finance' AND student_id = ?
                ORDER BY created_at DESC
                LIMIT 100
            ''', (student_id,))

            for row in cursor.fetchall():
                trans_type = row[1].replace('_', ' ').title()
                amount_str = f"£{row[2]:.2f}"
                if row[1] in ['use', 'withdrawal', 'payment']:
                    amount_str = f"-£{row[2]:.2f}"
                elif row[1] in ['top_up', 'deposit', 'refund']:
                    amount_str = f"+£{row[2]:.2f}"
                trans_tree.insert('', 'end', values=(row[0], trans_type, amount_str,
                                                    f"£{row[3]:.2f}", row[4] or ''))

            conn.close()
        except Exception as e:
            ttk.Label(parent, text=_("finance.errors.error_loading_transactions").format(error=e), foreground='red').pack()

    def _create_refunds_tab(self, parent, student_id):
        """Create refunds tab showing all refunds made by the department"""
        # Header with info
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(header_frame, text=_("finance.labels.all_refunds", default="All Refunds"),
                 font=('TkDefaultFont', 12, 'bold')).pack(side='left')

        # Refresh button
        refresh_btn = ttk.Button(header_frame, text=_("common.refresh", default="Refresh"),
                                command=lambda: self._refresh_refunds_list(refunds_tree))
        refresh_btn.pack(side='right', padx=5)

        # Search frame
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(search_frame, text=_("common.search", default="Search") + ":").pack(side='left', padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side='left', padx=5)

        # Table frame with scrollbar
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Create Treeview with scrollbar
        refunds_tree = ttk.Treeview(table_frame,
                                    columns=('ID', 'Reference', 'Department', 'Amount', 'Method', 'Date', 'Time', 'Transaction ID', 'Processed By', 'Notes'),
                                    show='headings', height=20)

        # Define column headings
        refunds_tree.heading('ID', text=_("finance.columns.id", default="ID"))
        refunds_tree.heading('Reference', text=_("finance.columns.refund_reference", default="Refund Reference"))
        refunds_tree.heading('Department', text=_("finance.columns.department", default="Department"))
        refunds_tree.heading('Amount', text=_("finance.columns.amount", default="Amount"))
        refunds_tree.heading('Method', text=_("finance.columns.refund_method", default="Method"))
        refunds_tree.heading('Date', text=_("finance.columns.date", default="Date"))
        refunds_tree.heading('Time', text=_("finance.columns.time", default="Time"))
        refunds_tree.heading('Transaction ID', text=_("finance.columns.transaction_id", default="Transaction ID"))
        refunds_tree.heading('Processed By', text=_("finance.columns.processed_by", default="Processed By"))
        refunds_tree.heading('Notes', text=_("finance.columns.notes", default="Notes"))

        # Define column widths
        refunds_tree.column('ID', width=50, anchor='center')
        refunds_tree.column('Reference', width=180, anchor='w')
        refunds_tree.column('Department', width=120, anchor='w')
        refunds_tree.column('Amount', width=100, anchor='e')
        refunds_tree.column('Method', width=120, anchor='w')
        refunds_tree.column('Date', width=100, anchor='center')
        refunds_tree.column('Time', width=80, anchor='center')
        refunds_tree.column('Transaction ID', width=150, anchor='w')
        refunds_tree.column('Processed By', width=120, anchor='w')
        refunds_tree.column('Notes', width=200, anchor='w')

        # Add scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=refunds_tree.xview)
        refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Pack the treeview and scrollbars
        refunds_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load refunds data
        self._load_refunds_data(refunds_tree)

        # Search functionality
        def search_refunds(*args):
            search_term = search_var.get().lower()
            # Clear and reload with filter
            for item in refunds_tree.get_children():
                refunds_tree.delete(item)
            self._load_refunds_data(refunds_tree, search_term)

        search_var.trace('w', search_refunds)

        # Summary frame at bottom
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill='x', padx=10, pady=5)

        # Calculate and display summary
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_refunds,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COUNT(DISTINCT COALESCE(department, source_type)) as departments_count
                FROM unified_refunds
            ''')

            summary = cursor.fetchone()
            conn.close()

            if summary:
                summary_text = f"Total Refunds: {summary[0]} | Total Amount: £{summary[1]:,.2f} | Departments: {summary[2]}"
                ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 10, 'bold'),
                         foreground='blue').pack()

        except Exception as e:
            ttk.Label(summary_frame, text=f"Error loading summary: {e}", foreground='red').pack()

    def _load_refunds_data(self, tree, search_term=None):
        """Load refunds data into the treeview"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Build query from unified_refunds table
            if search_term:
                cursor.execute('''
                    SELECT refund_id, refund_reference,
                           COALESCE(department, source_type) as department,
                           amount, refund_method, refund_date, '' as refund_time,
                           reference_id,
                           COALESCE(processed_by, approved_by, requested_by) as processed_by,
                           notes
                    FROM unified_refunds
                    WHERE LOWER(COALESCE(refund_reference, '')) LIKE ?
                       OR LOWER(COALESCE(department, source_type, '')) LIKE ?
                       OR LOWER(COALESCE(reference_id, '')) LIKE ?
                       OR LOWER(COALESCE(processed_by, '')) LIKE ?
                       OR LOWER(COALESCE(notes, '')) LIKE ?
                    ORDER BY refund_date DESC
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                      f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT refund_id, refund_reference,
                           COALESCE(department, source_type) as department,
                           amount, refund_method, refund_date, '' as refund_time,
                           reference_id,
                           COALESCE(processed_by, approved_by, requested_by) as processed_by,
                           notes
                    FROM unified_refunds
                    ORDER BY refund_date DESC
                ''')

            refunds = cursor.fetchall()

            # Insert data into tree
            for refund in refunds:
                refund_id, ref, dept, amount, method, date, time, trans_id, processed_by, notes = refund

                # Format amount
                amount_str = f"£{amount:.2f}" if amount else "£0.00"

                # Add row with color coding based on method
                tag = 'student_account' if method == 'Student Account' else 'other'

                tree.insert('', 'end', values=(
                    refund_id,
                    ref or '',
                    dept or '',
                    amount_str,
                    method or '',
                    date or '',
                    time or '',
                    trans_id or '',
                    processed_by or '',
                    notes or ''
                ), tags=(tag,))

            # Configure tags for color coding
            tree.tag_configure('student_account', background='#e3f2fd')
            tree.tag_configure('other', background='#f5f5f5')

            conn.close()

        except Exception as e:
            print(f"Error loading refunds data: {e}")
            # Show error in tree
            tree.insert('', 'end', values=('Error', str(e), '', '', '', '', '', '', '', ''))

    def _refresh_refunds_list(self, tree):
        """Refresh the refunds list"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        # Reload data
        self._load_refunds_data(tree)

        messagebox.showinfo(_("common.success", default="Success"),
                          _("finance.messages.refunds_refreshed", default="Refunds list refreshed successfully"))

    def view_my_finances(self):
        """Shortcut for students to view their own finances"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("finance.errors.must_be_logged_in"))
            return

        user_role = self.auth.current_user.get('role', '').lower()
        if user_role != 'student':
            messagebox.showinfo(_("common.info"), _("finance.messages.option_for_students"))
            return

        self.view_student_finances()

    # ==================== REPORT METHODS ====================


    def log_activity(self, message):
        """Log activity to the activity list"""
        try:
            # Activity listbox is created in dashboard manager
            if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'activity_listbox'):
                timestamp = datetime.now().strftime('%H:%M:%S')
                activity_text = f"{timestamp} - {message}"

                # Insert at the beginning of the list
                self.dashboard.activity_listbox.insert(0, activity_text)

                # Keep only the last 20 activities
                while self.dashboard.activity_listbox.size() > 20:
                    self.dashboard.activity_listbox.delete(tk.END)

        except Exception as e:
            print(f"Error logging activity: {e}")

    # Additional helper methods that might be missing

