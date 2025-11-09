"""Invoice generation and management"""

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




class InvoiceManager:
    """Invoice generation and management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None

        def gui_generate_invoice(self):
            """GUI wrapper for generate_invoice"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Generate Invoice")
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Student selection
            input_frame = ttk.LabelFrame(dialog, text="Student Information", padding=15)
            input_frame.pack(fill='x', padx=20, pady=10)
            
            ttk.Label(input_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
            student_id_var = tk.StringVar()
            student_entry = ttk.Entry(input_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
            student_entry.pack(anchor='w', pady=5)
            
            ttk.Button(input_frame, text="Load Student Info", 
                      command=lambda: self.load_student_info(student_id_var.get(), student_info_text)).pack(anchor='w', pady=5)
            
            # Student info display
            student_info_text = tk.Text(input_frame, height=4, width=70, font=('Arial', 10), state='disabled')
            student_info_text.pack(pady=5)
            
            # Outstanding fees display
            fees_frame = ttk.LabelFrame(dialog, text="Outstanding Fees", padding=15)
            fees_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            # Fees treeview
            columns = ('Fee Name', 'Amount', 'Due Date', 'Status')
            fees_tree = ttk.Treeview(fees_frame, columns=columns, show='headings', height=8)
            
            for col in columns:
                fees_tree.heading(col, text=col)
                fees_tree.column(col, width=150, anchor='center')
            
            fees_tree.pack(fill='both', expand=True)
            
            # Invoice preview
            preview_frame = ttk.LabelFrame(dialog, text="Invoice Preview", padding=15)
            preview_frame.pack(fill='x', padx=20, pady=10)
            
            invoice_text = ScrolledText(preview_frame, height=6, width=80, font=('Courier', 9))
            invoice_text.pack(fill='x')
    
        # ==================== DATA LOADING METHODS ====================
    

        def generate_invoice():
            try:
                student_id = student_id_var.get().strip()
                if not student_id:
                    messagebox.showerror("Error", "Student ID is required")
                    return
                    
                conn = get_connection()
                cursor = conn.cursor()
                    
                # Get student details
                cursor.execute('''
                SELECT first_name, last_name, email_address, course
                FROM students
                WHERE student_id = ?
                ''', (student_id,))
                    
                student = cursor.fetchone()
                if not student:
                    messagebox.showerror("Error", "Student not found")
                    conn.close()
                    return
                    
                first_name, last_name, email, course = student
                
                # Get outstanding fees
                cursor.execute('''
                SELECT ft.fee_name, sf.amount, sf.due_date, sf.status
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ? AND sf.status != 'paid'
                ORDER BY sf.due_date
                ''', (student_id,))
                
                fees = cursor.fetchall()
                
                # Update fees display
                for item in fees_tree.get_children():
                    fees_tree.delete(item)
                
                total_amount = 0
                for fee_name, amount, due_date, status in fees:
                    fees_tree.insert('', 'end', values=(fee_name, f"£{amount:.2f}", due_date, status))
                    total_amount += amount
                
                if not fees:
                    messagebox.showinfo("Info", "No outstanding fees for this student")
                    conn.close()
                    return
                
                # Generate invoice content
                invoice_date = datetime.now().strftime('%Y-%m-%d')
                invoice_number = f"INV-{student_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
                
                invoice_content = f"""
        INVOICE
        ===============================================
    
        Invoice Number: {invoice_number}
        Invoice Date: {invoice_date}
    
        BILL TO:
        {first_name} {last_name}
        Student ID: {student_id}
        Course: {course}
        Email: {email}
    
        ITEMIZED CHARGES:
        ===============================================
        """
                
                for fee_name, amount, due_date, status in fees:
                    invoice_content += f"{fee_name:<30} £{amount:>10.2f}  Due: {due_date}\n"
                
                invoice_content += f"""
        ===============================================
        TOTAL AMOUNT DUE:                £{total_amount:>10.2f}
        ===============================================
    
        PAYMENT INSTRUCTIONS:
        - Payment can be made online via student portal
        - Bank transfer details available on request
        - For payment plans, contact finance office
    
        Thank you for your prompt payment.
                """
                
                # Display in preview
                invoice_text.delete('1.0', tk.END)
                invoice_text.insert('1.0', invoice_content)
                
                conn.close()
                
                # Enable save/send buttons
                save_btn.config(state='normal')
                send_btn.config(state='normal')
                
                self.current_invoice = {
                    'number': invoice_number,
                    'content': invoice_content,
                    'student_email': email,
                    'student_name': f"{first_name} {last_name}"
                }
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate invoice: {e}")
    

        def save_invoice():
            if not hasattr(self, 'current_invoice'):
                messagebox.showerror("Error", "No invoice generated")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"invoice_{self.current_invoice['number']}.txt"
            )
            
            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(self.current_invoice['content'])
                    messagebox.showinfo("Success", f"Invoice saved as {filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save invoice: {e}")
    

        def send_invoice():
            if not hasattr(self, 'current_invoice'):
                messagebox.showerror("Error", "No invoice generated")
                return
    
            # Send invoice email using template system
            try:
                from university_system.infrastructure.email.template_utils import render_template
    
                subject, message = render_template("invoice_delivery", {
                    "invoice_number": self.current_invoice['number'],
                    "customer_name": self.current_invoice.get('customer_name', ''),
                    "student_name": self.current_invoice.get('customer_name', ''),
                    "invoice_date": self.current_invoice.get('date', ''),
                    "amount": self.current_invoice.get('total', 0),
                    "due_date": self.current_invoice.get('due_date', ''),
                    "items": self.current_invoice.get('items', [])
                })
    
                if not (subject and message):
                    # Fallback if template fails
                    subject = f"Invoice {self.current_invoice['number']}"
                    message = f"""Dear {self.current_invoice.get('customer_name', 'Customer')},
    
    Please find your invoice attached.
    
    Invoice Number: {self.current_invoice['number']}
    Invoice Date: {self.current_invoice.get('date', '')}
    Amount Due: £{self.current_invoice.get('total', 0):.2f}
    Due Date: {self.current_invoice.get('due_date', '')}
    
    Please process payment by the due date.
    
    Best regards,
    Finance Department
    """
    
                # Here you would integrate with your email system
                messagebox.showinfo("Success",
                                   f"Invoice sent to {self.current_invoice['student_email']}\n"
                                   f"(Email sending simulated)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send invoice: {e}")
    
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
    
            ttk.Button(button_frame, text="Generate Invoice", command=generate_invoice).pack(side='left', padx=5)
            save_btn = ttk.Button(button_frame, text="Save Invoice", command=save_invoice, state='disabled')
            save_btn.pack(side='left', padx=5)
            send_btn = ttk.Button(button_frame, text="Send Email", command=send_invoice, state='disabled')
            send_btn.pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)
    

        def load_student_info(self, student_id, text_widget):
            """Load and display student information"""
            if not student_id:
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Try to get phone_number if it exists, otherwise use NULL
                try:
                    cursor.execute('''
                    SELECT first_name, last_name, email_address, phone_number, course, enrollment_date, status
                    FROM students
                    WHERE student_id = ?
                    ''', (student_id,))
                except:
                    # Fallback if phone_number column doesn't exist
                    cursor.execute('''
                    SELECT first_name, last_name, email_address, NULL as phone_number, course, enrollment_date, status
                    FROM students
                    WHERE student_id = ?
                    ''', (student_id,))
                
                student = cursor.fetchone()
                
                text_widget.config(state='normal')
                text_widget.delete('1.0', tk.END)
                
                if student:
                    first_name, last_name, email, phone, course, enrollment_date, status = student
                    info = f"Name: {first_name} {last_name}\n"
                    info += f"Email: {email}\n"
                    info += f"Phone: {phone}\n"
                    info += f"Course: {course} | Enrolled: {enrollment_date} | Status: {status}"
                    text_widget.insert('1.0', info)
                else:
                    text_widget.insert('1.0', f"Student ID {student_id} not found")
                
                text_widget.config(state='disabled')
                conn.close()
                
            except Exception as e:
                text_widget.config(state='normal')
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', f"Error loading student info: {e}")
                text_widget.config(state='disabled')
    
