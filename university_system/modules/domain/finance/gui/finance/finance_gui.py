"""Main Finance GUI - coordinates all manager classes"""

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



# Import all manager classes
from university_system.modules.domain.finance.gui.finance.db_manager import DatabaseManager
from university_system.modules.domain.finance.gui.finance.layout_manager import LayoutManager
from university_system.modules.domain.finance.gui.finance.dashboard import DashboardManager
from university_system.modules.domain.finance.gui.finance.budget_manager import BudgetManager
from university_system.modules.domain.finance.gui.finance.transaction_manager import TransactionManager
from university_system.modules.domain.finance.gui.finance.invoice_manager import InvoiceManager
from university_system.modules.domain.finance.gui.finance.expense_manager import ExpenseManager
from university_system.modules.domain.finance.gui.finance.report_manager import ReportManager
from university_system.modules.domain.finance.gui.finance.analytics import AnalyticsManager
from university_system.modules.domain.finance.gui.finance.compliance import ComplianceManager
from university_system.modules.domain.finance.gui.finance.settings import SettingsManager
from university_system.modules.domain.finance.gui.finance.revenue_source_manager import RevenueSourceManager


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
                "Authentication system not available. "
                "Finance GUI cannot start without proper authentication."
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
        self.compliance = ComplianceManager(self)
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

    def initialize_system(self):
        """Initialize the finance system"""
        def init_thread():
            try:
                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status("Initializing system...")

                # Initialize database connection
                try:
                    from university_system.infrastructure.database.db import DEFAULT_DB_PATH
                    # Just ensure we can connect to the database
                    self.conn = get_connection()

                    # Try to initialize enhanced finance tables if available
                    try:
                        from university_system.modules.finance.core.financial_core import init_enhanced_finance_db
                        init_enhanced_finance_db()
                    except ImportError:
                        # Finance core module not available, just ensure basic connection works
                        pass
                    except Exception as e:
                        print(f"Warning: Could not initialize enhanced finance tables: {e}")

                except Exception as e:
                    print(f"Warning: Database initialization issue: {e}")

                # Initialize auth if needed
                global auth
                auth = self.auth

                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status("System initialized successfully")
                if hasattr(self, 'layout') and hasattr(self.layout, 'connection_label'):
                    self.layout.connection_label.config(text="🟢 Connected")

                # Load initial data
                if hasattr(self, 'load_initial_data'):
                    self.root.after(1000, self.load_initial_data)

            except Exception as e:
                if hasattr(self, 'layout') and hasattr(self.layout, 'update_status'):
                    self.layout.update_status(f"Initialization failed: {str(e)}")
                if hasattr(self, 'layout') and hasattr(self.layout, 'connection_label'):
                    self.layout.connection_label.config(text="🔴 Error")
                messagebox.showerror("Initialization Error", f"Failed to initialize system: {str(e)}")

        threading.Thread(target=init_thread, daemon=True).start()
    

    def run(self):
        """Run the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Application terminated by user")
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
    

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
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
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

        tk.Button(toolbar, text="🔍 Search", command=self.search_students,
                 bg=colors['secondary'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="💰 View Finances", command=self.view_student_finances,
                 bg=colors['dark'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        
        # Search frame
        search_frame = tk.Frame(students_frame, bg='white')
        search_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(search_frame, text="Search:", bg='white').pack(side='left')
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
        
        self.students_tree.heading('student_id', text='Student ID')
        self.students_tree.heading('name', text='Name')
        self.students_tree.heading('email', text='Email')
        self.students_tree.heading('course', text='Course')
        self.students_tree.heading('status', text='Status')
        self.students_tree.heading('balance', text='Balance')
        
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
        search_term = simpledialog.askstring("Search Students", "Enter student name or ID:")
        if search_term:
            self.student_search_var.set(search_term)
            self.on_student_search(None)
    

    def view_student_finances(self):
        """View financial details for selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to view finances.")
            return
    
        student_id = self.students_tree.item(selection[0])['values'][0]
        student_name = self.students_tree.item(selection[0])['values'][1]
    
        # Create detailed finance view dialog
        finance_dialog = tk.Toplevel(self.root)
        finance_dialog.title(f"Financial Details - {student_name}")
        finance_dialog.geometry("800x600")
        finance_dialog.transient(self.root)
    
        ttk.Label(finance_dialog, text=f"Student Financial Details - {student_name} ({student_id})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
    
        # Create notebook for different financial sections
        notebook = ttk.Notebook(finance_dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)
    
        # Tab 1: Overview
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
    
        try:
            conn = get_connection()
            cursor = conn.cursor()
    
            # Get financial summary
            cursor.execute('''
                SELECT
                    COALESCE(SUM(f.amount), 0) as total_fees,
                    COALESCE(SUM(CASE WHEN f.paid = 1 THEN f.amount ELSE 0 END), 0) as paid_amount,
                    COALESCE(SUM(CASE WHEN f.paid = 0 THEN f.amount ELSE 0 END), 0) as outstanding
                FROM fees f
                WHERE f.student_id = ?
            ''', (student_id,))
            fee_summary = cursor.fetchone()
    
            # Display overview
            summary_frame = ttk.LabelFrame(overview_frame, text="Financial Summary", padding=20)
            summary_frame.pack(fill='x', padx=10, pady=10)
    
            summary_text = f"""
    Total Fees:        £{fee_summary[0]:,.2f}
    Paid:              £{fee_summary[1]:,.2f}
    Outstanding:       £{fee_summary[2]:,.2f}
    """
            ttk.Label(summary_frame, text=summary_text, font=('Courier', 10)).pack(anchor='w')
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load financial data: {e}", parent=finance_dialog)
    
        # Tab 2: Fees
        fees_frame = ttk.Frame(notebook)
        notebook.add(fees_frame, text="Fees")
    
        fees_tree = ttk.Treeview(fees_frame, columns=('ID', 'Description', 'Amount', 'Due Date', 'Status'),
                                show='headings', height=15)
        fees_tree.heading('ID', text='Fee ID')
        fees_tree.heading('Description', text='Description')
        fees_tree.heading('Amount', text='Amount')
        fees_tree.heading('Due Date', text='Due Date')
        fees_tree.heading('Status', text='Status')
    
        for col in ('ID', 'Description', 'Amount', 'Due Date', 'Status'):
            fees_tree.column(col, width=140)
    
        fees_tree.pack(fill='both', expand=True, padx=5, pady=5)
    
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, description, amount, due_date, paid
                FROM fees
                WHERE student_id = ?
                ORDER BY due_date DESC
            ''', (student_id,))
    
            for row in cursor.fetchall():
                status = 'Paid' if row[4] == 1 else 'Outstanding'
                fees_tree.insert('', 'end', values=(row[0], row[1], f"£{row[2]:.2f}", row[3], status))
    
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load fees: {e}", parent=finance_dialog)
    
        # Tab 3: Payments
        payments_frame = ttk.Frame(notebook)
        notebook.add(payments_frame, text="Payments")
    
        payments_tree = ttk.Treeview(payments_frame, columns=('ID', 'Amount', 'Date', 'Method', 'Reference'),
                                    show='headings', height=15)
        payments_tree.heading('ID', text='Payment ID')
        payments_tree.heading('Amount', text='Amount')
        payments_tree.heading('Date', text='Date')
        payments_tree.heading('Method', text='Method')
        payments_tree.heading('Reference', text='Reference')
    
        for col in ('ID', 'Amount', 'Date', 'Method', 'Reference'):
            payments_tree.column(col, width=140)
    
        payments_tree.pack(fill='both', expand=True, padx=5, pady=5)
    
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, amount, payment_date, payment_method, transaction_id
                FROM payments
                WHERE student_id = ?
                ORDER BY payment_date DESC
            ''', (student_id,))
    
            for row in cursor.fetchall():
                payments_tree.insert('', 'end', values=(row[0], f"£{row[1]:.2f}", row[2], row[3] or 'N/A', row[4] or 'N/A'))
    
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load payments: {e}", parent=finance_dialog)
    
        # Close button
        ttk.Button(finance_dialog, text="Close", command=finance_dialog.destroy).pack(pady=10)
    
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
    
