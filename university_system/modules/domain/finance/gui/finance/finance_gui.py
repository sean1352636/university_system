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

# Import your existing modules - keep backward compatibility
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
    from university_system.infrastructure.database.db import get_connection
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility
    def send_email(*args, **kwargs):
        return True
    
    class UserAuth:
        def __init__(self):
            self.current_user = {"username": "admin"}
        def check_permission(self, p):
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


class FinanceGUI:
    """Main Finance GUI class that coordinates all managers"""

    def __init__(self, root):
        self.root = root
        self.conn = None
        self.finance_system = None
        self.auth = None  # Initialize auth attribute

        # Try to get global auth instance
        try:
            self.auth = get_global_auth()
        except:
            # Fallback: create a basic auth instance
            try:
                self.auth = UserAuth()
            except:
                pass

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

        tk.Button(toolbar, text="➕ Add Student", command=self.show_student_dialog,
                 bg=colors['success'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="✏️ Edit Student", command=self.edit_selected_student,
                 bg=colors['warning'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="🗑️ Delete Student", command=self.delete_selected_student,
                 bg=colors['danger'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
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
        
        # Double-click to edit
        self.students_tree.bind('<Double-1>', self.edit_selected_student)
    

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
    

    def show_student_management_message(self):
        """Display message directing users to main GUI for student management"""
        messagebox.showinfo(
            "Student Management",
            "Student creation, editing, and deletion have been centralized in the main GUI.\n\n"
            "Please use the main student management interface to:\n"
            "• Create new students\n"
            "• Edit student information\n"
            "• Delete student records\n\n"
            "This ensures consistent student data across all modules."
        )
    

    def show_student_dialog(self):
        """Redirect to main GUI student management"""
        self.show_student_management_message()
        return  # Early return to skip the rest
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Student")
        dialog.geometry("700x800")
        dialog.transient(self.root)
    
        # Make dialog visible before grabbing
        dialog.update_idletasks()
        dialog.deiconify()
    
        try:
            dialog.grab_set()
        except tk.TclError:
            print("Warning: Could not grab dialog focus")
    
        # Main scrollable frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
    
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
    
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
    
        # Title
        title_label = ttk.Label(scrollable_frame, text="Create New Student",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
    
        # Form fields
        fields = {}
    
        # Personal Information Section
        personal_frame = ttk.LabelFrame(scrollable_frame, text="Personal Information", padding=15)
        personal_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
        # Title/Prefix
        ttk.Label(personal_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        fields['title'] = ttk.Combobox(personal_frame, values=['Mr', 'Ms', 'Mrs', 'Dr', 'Prof'],
                                      state='readonly', width=27)
        fields['title'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)
    
        # First Name
        ttk.Label(personal_frame, text="First Name: *").grid(row=1, column=0, sticky=tk.W, pady=5)
        fields['first_name'] = ttk.Entry(personal_frame, width=30)
        fields['first_name'].grid(row=1, column=1, pady=5, padx=(10, 0))
    
        # Middle Name
        ttk.Label(personal_frame, text="Middle Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        fields['middle_name'] = ttk.Entry(personal_frame, width=30)
        fields['middle_name'].grid(row=2, column=1, pady=5, padx=(10, 0))
    
        # Last Name
        ttk.Label(personal_frame, text="Last Name: *").grid(row=3, column=0, sticky=tk.W, pady=5)
        fields['last_name'] = ttk.Entry(personal_frame, width=30)
        fields['last_name'].grid(row=3, column=1, pady=5, padx=(10, 0))
    
        # Gender
        ttk.Label(personal_frame, text="Gender: *").grid(row=4, column=0, sticky=tk.W, pady=5)
        fields['gender'] = ttk.Combobox(personal_frame, values=['male', 'female', 'other'],
                                       state='readonly', width=27)
        fields['gender'].grid(row=4, column=1, pady=5, padx=(10, 0), sticky=tk.W)
    
        # Date of Birth
        ttk.Label(personal_frame, text="Date of Birth (YYYY-MM-DD): *").grid(row=5, column=0, sticky=tk.W, pady=5)
        fields['dob'] = ttk.Entry(personal_frame, width=30)
        fields['dob'].grid(row=5, column=1, pady=5, padx=(10, 0))
    
        # Academic Information Section
        academic_frame = ttk.LabelFrame(scrollable_frame, text="Academic Information", padding=15)
        academic_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
        # Course - Show as read-only with random assignment info
        ttk.Label(academic_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_label = ttk.Label(academic_frame, text="Will be randomly assigned (CS or DS)",
                                foreground="blue")
        course_label.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)
    
        # Status information
        status_label = ttk.Label(scrollable_frame,
                                text="Note: Student ID, email, course, and modules will be auto-generated",
                                foreground="blue")
        status_label.grid(row=3, column=0, columnspan=2, pady=10)
    
        # Validation feedback
        validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
        validation_label.grid(row=4, column=0, columnspan=2, pady=5)
    
        def validate_form():
            """Validate form inputs"""
            errors = []
    
            if not fields['first_name'].get().strip():
                errors.append("First name is required")
    
            if not fields['last_name'].get().strip():
                errors.append("Last name is required")
    
            if not fields['gender'].get():
                errors.append("Gender is required")
    
            dob_text = fields['dob'].get().strip()
            if not dob_text:
                errors.append("Date of birth is required")
            else:
                try:
                    dob = datetime.strptime(dob_text, "%Y-%m-%d")
                    age = datetime.now().year - dob.year
                    if age < 16 or age > 80:
                        errors.append("Age must be between 16 and 80")
                except ValueError:
                    errors.append("Invalid date format (use YYYY-MM-DD)")
    
            return errors
    
        def create_student():
            """Create student with comprehensive data processing and random course assignment"""
            import random
            try:
                # Validate form
                errors = validate_form()
                if errors:
                    validation_label.config(text="; ".join(errors))
                    return
    
                validation_label.config(text="")
    
                # Get form data
                first_name = fields['first_name'].get().strip()
                middle_name = fields['middle_name'].get().strip()
                last_name = fields['last_name'].get().strip()
                gender = fields['gender'].get()
                dob_text = fields['dob'].get().strip()
    
                # RANDOMLY ASSIGN COURSE FROM AVAILABLE COURSES IN DATABASE
                # Get available courses from courses table
                course_conn = get_connection()
                if not course_conn:
                    raise Exception("Database connection failed for course selection")
    
                course_cursor = course_conn.cursor()
                course_cursor.execute('''
                    SELECT course_code FROM courses
                    WHERE status = 'active' AND course_code IS NOT NULL
                    AND course_code != '' AND max_enrollment > current_enrollment
                ''')
                available_courses = [row[0] for row in course_cursor.fetchall()]
                course_conn.close()
    
                if not available_courses:
                    # Fallback to default courses if none available
                    available_courses = ['CS', 'DS']
    
                course = random.choice(available_courses)
    
                title = fields['title'].get() or ('Mr' if gender == 'male' else 'Ms')
    
                # Parse date and calculate age
                dob = datetime.strptime(dob_text, "%Y-%m-%d")
                now_dt = datetime.now()
                age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))
    
                # Generate student ID and email
                student_id = str(random.randint(1000000, 9999999)).zfill(7)
                email_address = f"C{student_id}@tees.ac.uk"
                registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    
                # Create student record in database
                conn = get_connection()
                if not conn:
                    raise Exception("Database connection failed")
    
                cursor = conn.cursor()
    
                # Temporarily disable foreign key checks to avoid module_code issues
                cursor.execute("PRAGMA foreign_keys = OFF")
    
                # Insert student record
                cursor.execute('''
                    INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, email_address, title, first_name, middle_name,
                    last_name, gender, dob.strftime('%Y-%m-%d'), age, course, registration_time, 'Active', registration_time
                ))
    
                # Add modules based on the assigned course from database
                current_date = datetime.now().strftime('%Y-%m-%d')
    
                # Get available modules for the assigned course
                cursor.execute('''
                    SELECT module_code FROM modules
                    WHERE department = ? AND is_active = 1
                    ORDER BY module_code
                ''', (course,))
                course_modules = [row[0] for row in cursor.fetchall()]
    
                # If no course-specific modules found, try to find general modules
                if not course_modules:
                    cursor.execute('''
                        SELECT module_code FROM modules
                        WHERE module_code LIKE ? AND is_active = 1
                        ORDER BY module_code
                        LIMIT 6
                    ''', (f"{course}%",))
                    course_modules = [row[0] for row in cursor.fetchall()]
    
                # If still no modules, fall back to any available modules
                if not course_modules:
                    cursor.execute('''
                        SELECT module_code FROM modules
                        WHERE is_active = 1
                        ORDER BY module_code
                        LIMIT 6
                    ''')
                    course_modules = [row[0] for row in cursor.fetchall()]
    
                # Select 3-6 random modules for the student
                selected_modules = []
                if course_modules:
                    num_modules = min(random.randint(3, 6), len(course_modules))
                    selected_modules = random.sample(course_modules, num_modules)
    
                    module_data = [
                        (student_id, module_code, current_date, 'enrolled')
                        for module_code in selected_modules
                    ]
    
                    cursor.executemany('''
                        INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                        VALUES (?, ?, ?, ?)
                    ''', module_data)
    
                    print(f"Assigned {len(selected_modules)} modules to student {student_id} for course {course}")
                else:
                    print(f"Warning: No modules found for course {course}, student {student_id} not enrolled in any modules")
    
                # Update course enrollment count
                cursor.execute('''
                    UPDATE courses
                    SET current_enrollment = current_enrollment + 1
                    WHERE course_code = ? AND status = 'active'
                ''', (course,))
    
                # Re-enable foreign key checks
                cursor.execute("PRAGMA foreign_keys = ON")
    
                conn.commit()
                conn.close()
    
                # Create user account
                temp_password = f"{first_name.lower()}123456"
                try:
                    self.auth.create_user(
                        username=student_id,
                        password=temp_password,
                        email=email_address,
                        first_name=first_name,
                        last_name=last_name,
                        role='student',
                        student_id=student_id
                    )
                except Exception as e:
                    logging.warning(f"User account creation failed: {e}")
    
                # Success message with details
                modules_text = ""
                if course_modules and selected_modules:
                    modules_text = "\n\n    Modules assigned:\n"
                    for mod_code in selected_modules:
                        modules_text += f"    - {mod_code}\n"
    
                success_msg = f"""Student created successfully!
    
    Student Details:
    - Student ID: {student_id}
    - Name: {title} {first_name} {middle_name} {last_name}
    - Email: {email_address}
    - Course: {course} (randomly assigned)
    - Age: {age}
    - Login Password: {temp_password}{modules_text}"""
    
                messagebox.showinfo("Success", success_msg)
    
                dialog.destroy()
                self.refresh_students()
                self.refresh_dashboard()
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create student: {e}")
    
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
    
        ttk.Button(button_frame, text="Create Student", command=create_student).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    

    def edit_selected_student(self, event=None):
        """Redirect to main GUI student management"""
        self.show_student_management_message()
    

    def update_student_dialog(self, student_id):
        """Redirect to main GUI student management"""
        self.show_student_management_message()
        return  # Early return to skip the rest
        import random
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Student - {student_id}")
        dialog.geometry("800x900")
        dialog.transient(self.root)
    
        # Make dialog visible before grabbing
        dialog.update_idletasks()
        dialog.deiconify()
    
        try:
            dialog.grab_set()
        except tk.TclError:
            print("Warning: Could not grab dialog focus")
    
        try:
            # Get current student data
            conn = get_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                dialog.destroy()
                return
    
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
    
            if not student:
                messagebox.showerror("Error", "Student not found")
                dialog.destroy()
                return
    
            # Main scrollable frame
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
    
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
    
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
    
            # Title
            title_label = ttk.Label(scrollable_frame, text=f"Update Student: {student_id}",
                                   font=('Arial', 16, 'bold'))
            title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
    
            # Current info display
            current_frame = ttk.LabelFrame(scrollable_frame, text="Current Information", padding=10)
            current_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
            current_text = tk.Text(current_frame, height=4, width=70, wrap=tk.WORD)
            current_text.pack(fill=tk.X)
            current_info = f"Name: {student[2]} {student[3]} {student[4]} {student[5]} | Gender: {student[6]} | Course: {student[9]} | Age: {student[8]}"
            current_text.insert(tk.END, current_info)
            current_text.config(state=tk.DISABLED)
    
            # Form fields with current values
            fields = {}
    
            # Personal Information Section
            personal_frame = ttk.LabelFrame(scrollable_frame, text="Personal Information", padding=15)
            personal_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
            # Title
            ttk.Label(personal_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
            fields['title'] = ttk.Combobox(personal_frame, values=['Mr', 'Ms', 'Mrs', 'Dr', 'Prof'],
                                          state='readonly', width=27)
            fields['title'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)
            fields['title'].set(student[2])
    
            # First Name
            ttk.Label(personal_frame, text="First Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
            fields['first_name'] = ttk.Entry(personal_frame, width=30)
            fields['first_name'].grid(row=1, column=1, pady=5, padx=(10, 0))
            fields['first_name'].insert(0, student[3])
    
            # Middle Name
            ttk.Label(personal_frame, text="Middle Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
            fields['middle_name'] = ttk.Entry(personal_frame, width=30)
            fields['middle_name'].grid(row=2, column=1, pady=5, padx=(10, 0))
            fields['middle_name'].insert(0, student[4] or '')
    
            # Last Name
            ttk.Label(personal_frame, text="Last Name:").grid(row=3, column=0, sticky=tk.W, pady=5)
            fields['last_name'] = ttk.Entry(personal_frame, width=30)
            fields['last_name'].grid(row=3, column=1, pady=5, padx=(10, 0))
            fields['last_name'].insert(0, student[5])
    
            # Gender
            ttk.Label(personal_frame, text="Gender:").grid(row=4, column=0, sticky=tk.W, pady=5)
            fields['gender'] = ttk.Combobox(personal_frame, values=['male', 'female', 'other'],
                                           state='readonly', width=27)
            fields['gender'].grid(row=4, column=1, pady=5, padx=(10, 0), sticky=tk.W)
            fields['gender'].set(student[6])
    
            # Date of Birth
            ttk.Label(personal_frame, text="Date of Birth (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, pady=5)
            fields['dob'] = ttk.Entry(personal_frame, width=30)
            fields['dob'].grid(row=5, column=1, pady=5, padx=(10, 0))
            fields['dob'].insert(0, student[7])
    
            # Academic Information
            academic_frame = ttk.LabelFrame(scrollable_frame, text="Academic Information", padding=15)
            academic_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
            # Course - Add random assignment option
            ttk.Label(academic_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
            course_frame = ttk.Frame(academic_frame)
            course_frame.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)
    
            current_course_label = ttk.Label(course_frame, text=f"Current: {student[9]}", foreground="blue")
            current_course_label.pack(side=tk.LEFT)
    
            # Random course reassignment option
            reassign_course_var = tk.BooleanVar()
            ttk.Checkbutton(course_frame, text="Randomly reassign course and modules",
                           variable=reassign_course_var).pack(side=tk.LEFT, padx=(20, 0))
    
            # Email (read-only display)
            ttk.Label(academic_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
            email_label = ttk.Label(academic_frame, text=student[1], foreground="blue")
            email_label.grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.W)
    
            # Module Management Section
            modules_frame = ttk.LabelFrame(scrollable_frame, text="Module Management", padding=15)
            modules_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
            # Get current modules
            try:
                cursor.execute('''
                    SELECT sm.module_id, sm.enrollment_date, sm.status
                    FROM student_modules sm
                    WHERE sm.student_id = ?
                ''', (student_id,))
                current_modules = cursor.fetchall()
            except:
                current_modules = []
    
            modules_text = ScrolledText(modules_frame, height=6, width=70)
            modules_text.pack(fill=tk.X)
    
            modules_info = "Current Modules:\n" + "-"*40 + "\n"
            for module in current_modules:
                modules_info += f"Module: {module[0]} - Status: {module[2]} - Enrolled: {module[1]}\n"
            modules_text.insert(tk.END, modules_info)
            modules_text.config(state=tk.DISABLED)
    
            # Validation feedback
            validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
            validation_label.grid(row=5, column=0, columnspan=2, pady=10)
    
            def validate_update_form():
                """Validate update form inputs"""
                errors = []
    
                if not fields['first_name'].get().strip():
                    errors.append("First name cannot be empty")
    
                if not fields['last_name'].get().strip():
                    errors.append("Last name cannot be empty")
    
                dob_text = fields['dob'].get().strip()
                if dob_text:
                    try:
                        dob = datetime.strptime(dob_text, "%Y-%m-%d")
                        age = datetime.now().year - dob.year
                        if age < 16 or age > 80:
                            errors.append("Age must be between 16 and 80")
                    except ValueError:
                        errors.append("Invalid date format (use YYYY-MM-DD)")
    
                return errors
    
            def update_student():
                """Update student with form data and random course assignment if selected"""
                try:
                    # Validate form
                    errors = validate_update_form()
                    if errors:
                        validation_label.config(text="; ".join(errors))
                        return
    
                    validation_label.config(text="")
    
                    # Get updated data
                    new_title = fields['title'].get()
                    new_first_name = fields['first_name'].get().strip()
                    new_middle_name = fields['middle_name'].get().strip()
                    new_last_name = fields['last_name'].get().strip()
                    new_gender = fields['gender'].get()
                    new_dob = fields['dob'].get().strip()
    
                    # Determine new course
                    if reassign_course_var.get():
                        new_course = random.choice(['CS', 'DS'])
                        course_changed = True
                    else:
                        new_course = student[9]  # Keep current course
                        course_changed = False
    
                    # Calculate new age if DOB changed
                    if new_dob != student[7]:
                        dob_date = datetime.strptime(new_dob, "%Y-%m-%d")
                        new_age = datetime.now().year - dob_date.year - (
                            (datetime.now().month, datetime.now().day) < (dob_date.month, dob_date.day)
                        )
                    else:
                        new_age = student[8]
    
                    # Update database
                    cursor.execute('''
                        UPDATE students
                        SET title = ?, first_name = ?, middle_name = ?, last_name = ?,
                            gender = ?, dob = ?, age = ?, course = ?
                        WHERE student_id = ?
                    ''', (new_title, new_first_name, new_middle_name, new_last_name,
                          new_gender, new_dob, new_age, new_course, student_id))
    
                    conn.commit()
    
                    success_msg = f"Student {student_id} updated successfully!"
                    if course_changed:
                        success_msg += f"\nCourse randomly changed from {student[9]} to {new_course}"
    
                    messagebox.showinfo("Success", success_msg)
    
                    # Refresh views and close dialog
                    self.refresh_students()
                    self.refresh_dashboard()
                    dialog.destroy()
    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update student: {str(e)}")
    
            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.grid(row=6, column=0, columnspan=2, pady=20)
    
            ttk.Button(button_frame, text="Update Student", command=update_student).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student data: {str(e)}")
            dialog.destroy()
    

    def search_students(self):
        """Search students dialog"""
        search_term = simpledialog.askstring("Search Students", "Enter student name or ID:")
        if search_term:
            self.student_search_var.set(search_term)
            self.on_student_search(None)
    

    def delete_student_dialog(self, student_id=None):
        """Redirect to main GUI student management"""
        self.show_student_management_message()
        return  # Early return to skip the rest
        if not student_id:
            # Show selection dialog first
            student_id = self.select_student_for_deletion()
            if not student_id:
                return
    
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Delete Student - {student_id}")
        dialog.geometry("600x500")
        dialog.transient(self.root)
    
        # Make dialog visible BEFORE grabbing
        dialog.update_idletasks()  # Force geometry calculation
        dialog.deiconify()         # Ensure window is visible
    
        # Center the dialog on parent
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
    
        # Now it's safe to grab focus
        try:
            dialog.grab_set()
        except tk.TclError:
            # If grab still fails, continue without it
            print("Warning: Could not grab dialog focus")
    
        # Make dialog modal and non-resizable
        dialog.resizable(False, False)
    
        try:
            # Get student data for confirmation
            conn = get_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                dialog.destroy()
                return
    
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
    
            if not student:
                messagebox.showerror("Error", "Student not found")
                dialog.destroy()
                return
    
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
    
            # Warning header
            warning_frame = ttk.Frame(main_frame)
            warning_frame.pack(fill=tk.X, pady=(0, 20))
    
            warning_label = ttk.Label(warning_frame, text="⚠️ DELETE STUDENT RECORD",
                                     font=('Arial', 16, 'bold'), foreground="red")
            warning_label.pack()
    
            # Student information display
            info_frame = ttk.LabelFrame(main_frame, text="Student Information", padding=15)
            info_frame.pack(fill=tk.X, pady=(0, 20))
    
            student_info = f"""Student ID: {student[0]}
    Name: {student[2]} {student[3]} {student[4]} {student[5]}
    Email: {student[1]}
    Course: {student[9]}
    Registration Date: {student[10]}"""
    
            ttk.Label(info_frame, text=student_info, font=('Courier', 10)).pack(anchor=tk.W)
    
            # Get related records count
            try:
                cursor.execute('SELECT COUNT(*) FROM student_modules WHERE student_id = ?', (student_id,))
                modules_count = cursor.fetchone()[0]
            except:
                modules_count = 0
    
            try:
                cursor.execute('SELECT COUNT(*) FROM student_grades WHERE student_id = ?', (student_id,))
                grades_count = cursor.fetchone()[0]
            except:
                grades_count = 0
    
            try:
                cursor.execute('SELECT COUNT(*) FROM attendance WHERE student_id = ?', (student_id,))
                attendance_count = cursor.fetchone()[0]
            except:
                attendance_count = 0
    
            # Related records information
            related_frame = ttk.LabelFrame(main_frame, text="Related Records (Will be Deleted)", padding=15)
            related_frame.pack(fill=tk.X, pady=(0, 20))
    
            related_info = f"""Module Enrollments: {modules_count}
    Grade Records: {grades_count}
    Attendance Records: {attendance_count}
    User Account: Will be removed
    All associated data will be permanently deleted"""
    
            ttk.Label(related_frame, text=related_info, font=('Courier', 10), foreground="dark red").pack(anchor=tk.W)
    
            # Confirmation section
            confirm_frame = ttk.LabelFrame(main_frame, text="Confirmation Required", padding=15)
            confirm_frame.pack(fill=tk.X, pady=(0, 20))
    
            ttk.Label(confirm_frame, text="This action cannot be undone!",
                     font=('Arial', 12, 'bold'), foreground="red").pack(pady=(0, 10))
    
            ttk.Label(confirm_frame, text=f"Type '{student_id}' to confirm deletion:").pack(anchor=tk.W)
            confirm_entry = ttk.Entry(confirm_frame, width=30, font=('Arial', 11))
            confirm_entry.pack(pady=(5, 10), fill=tk.X)
    
            # Additional confirmation checkbox
            additional_confirm = tk.BooleanVar()
            ttk.Checkbutton(confirm_frame, text="I understand this will permanently delete all student data",
                           variable=additional_confirm).pack(anchor=tk.W)
    
            # Status label
            status_label = ttk.Label(confirm_frame, text="", foreground="red")
            status_label.pack(pady=(10, 0))
    
            def perform_deletion():
                """Perform the actual deletion with comprehensive cleanup"""
                # Validate confirmations
                if confirm_entry.get().strip() != student_id:
                    status_label.config(text="Student ID confirmation does not match")
                    return
    
                if not additional_confirm.get():
                    status_label.config(text="Please check the confirmation checkbox")
                    return
    
                # Final confirmation dialog
                if not messagebox.askyesno("Final Confirmation",
                                         f"Are you absolutely sure you want to delete student {student_id}?\n\n"
                                         "This action is IRREVERSIBLE and will delete:\n"
                                         "• Student record\n"
                                         "• All module enrollments\n"
                                         "• All grades and assessments\n"
                                         "• All attendance records\n"
                                         "• User account and login access\n"
                                         "• All related data",
                                         icon='warning'):
                    return
    
                try:
                    # Start deletion process
                    status_label.config(text="Deleting student record...", foreground="blue")
                    dialog.update()
    
                    # Disable foreign key constraints temporarily
                    cursor.execute("PRAGMA foreign_keys = OFF")
    
                    deletion_log = []
    
                    # Delete from related tables first
                    tables_to_clean = [
                        ('student_grades', 'student_id'),
                        ('attendance', 'student_id'),
                        ('student_modules', 'student_id'),
                        ('assignment_submissions', 'student_id'),
                        ('accommodation_requests', 'student_id'),
                        ('housing_requests', 'student_id'),
                        ('health_records', 'student_id'),
                        ('internship_applications', 'student_id'),
                        ('trip_participants', 'student_id'),
                        ('loans', 'borrower_id'),
                        ('student_fees', 'student_id'),
                        ('support_tickets', 'student_id'),
                        ('parent_student_relationships', 'student_id')
                    ]
    
                    for table_name, column_name in tables_to_clean:
                        try:
                            cursor.execute(f'DELETE FROM {table_name} WHERE {column_name} = ?', (student_id,))
                            deleted_count = cursor.rowcount
                            if deleted_count > 0:
                                deletion_log.append(f"Deleted {deleted_count} records from {table_name}")
                        except:
                            # Table might not exist
                            pass
    
                    # Delete user accounts
                    try:
                        cursor.execute('SELECT id FROM users WHERE student_id = ?', (student_id,))
                        user_record = cursor.fetchone()
    
                        if user_record:
                            user_id = user_record[0]
    
                            # Delete from user_accounts
                            cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                            if cursor.rowcount > 0:
                                deletion_log.append("Deleted user account")
    
                            # Delete from users
                            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                            if cursor.rowcount > 0:
                                deletion_log.append("Deleted user profile")
                    except:
                        pass
    
                    # Finally delete the main student record
                    cursor.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
                    if cursor.rowcount > 0:
                        deletion_log.append("Deleted main student record")
    
                    # Re-enable foreign key constraints
                    cursor.execute("PRAGMA foreign_keys = ON")
    
                    conn.commit()
                    conn.close()
    
                    # Show deletion summary
                    summary = f"Student {student_id} deleted successfully!\n\nDeletion Summary:\n" + "\n".join(deletion_log)
                    messagebox.showinfo("Deletion Complete", summary)
    
                    # Refresh student list and close dialog
                    self.refresh_students()
                    self.refresh_dashboard()
                    dialog.destroy()
    
                except Exception as e:
                    # Re-enable foreign keys on error
                    cursor.execute("PRAGMA foreign_keys = ON")
                    conn.rollback()
                    messagebox.showerror("Deletion Failed", f"Failed to delete student: {str(e)}")
                    status_label.config(text="Deletion failed", foreground="red")
    
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))
    
            ttk.Button(button_frame, text="DELETE STUDENT", command=perform_deletion).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
    
            # Focus on confirmation entry
            confirm_entry.focus()
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student data: {str(e)}")
            dialog.destroy()
    

    def select_student_for_deletion(self):
        """Show dialog to select student for deletion"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students ORDER BY student_id')
            students = cursor.fetchall()
            conn.close()
    
            if not students:
                messagebox.showinfo("No Students", "No students found in database")
                return None
    
            # Create selection dialog
            selection_dialog = tk.Toplevel(self.root)
            selection_dialog.title("Select Student to Delete")
            selection_dialog.geometry("400x300")
            selection_dialog.transient(self.root)
            selection_dialog.grab_set()
    
            selected_student = None
    
            ttk.Label(selection_dialog, text="Select student to delete:", font=('Arial', 12, 'bold')).pack(pady=10)
    
            # Create listbox
            listbox_frame = ttk.Frame(selection_dialog)
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
            listbox = tk.Listbox(listbox_frame)
            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
    
            for student in students:
                listbox.insert(tk.END, f"{student[0]} - {student[1]} {student[2]}")
    
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
    
            def on_select():
                nonlocal selected_student
                selection = listbox.curselection()
                if selection:
                    selected_student = students[selection[0]][0]
                    selection_dialog.destroy()
    
            def on_cancel():
                nonlocal selected_student
                selected_student = None
                selection_dialog.destroy()
    
            # Buttons
            button_frame = ttk.Frame(selection_dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
    
            selection_dialog.wait_window()
            return selected_student
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load students: {str(e)}")
            return None
    

    def delete_selected_student(self):
        """Delete selected student from tree"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to delete.")
            return
    
        student_id = self.students_tree.item(selection[0])['values'][0]
        self.delete_student_dialog(student_id)
    

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
    
