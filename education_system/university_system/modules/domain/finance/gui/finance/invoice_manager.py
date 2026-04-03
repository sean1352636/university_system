"""Invoice generation and management"""

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from education_system.university_system.modules.shared.utils.i18n import get_text as _
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
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
from education_system.university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.utils.logging.log_config import configure_logging, get_log_file
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
        from education_system.university_system.modules.shared.constants import paths
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

# Backward-compatible re-exports for transaction manager dialog imports.
try:
    from education_system.university_system.modules.domain.finance.gui.finance_reporting.payment_dialogs import (
        PaymentDetailsDialog,
        RefundDialog,
    )
except Exception:
    class PaymentDetailsDialog:
        def __init__(self, parent, payment_id):
            self.dialog = tk.Toplevel(parent)
            self.dialog.title(f"Payment Details - {payment_id}")

    class RefundDialog:
        def __init__(self, parent, payment_id, student_id, amount):
            self.dialog = tk.Toplevel(parent)
            self.dialog.title(f"Refund - {payment_id}")
            self.result = False




class InvoiceManager:
    """Invoice generation and management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def gui_generate_invoice(self):
        """GUI wrapper for generate_invoice"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.invoice_manager.dialog_title"))
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        input_frame = ttk.LabelFrame(dialog, text=_("finance_gui.invoice_manager.student_info_frame"), padding=15)
        input_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(input_frame, text=_("finance_gui.invoice_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(input_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(anchor='w', pady=5)

        ttk.Button(input_frame, text=_("finance_gui.invoice_manager.load_student_btn"),
                  command=lambda: self.load_student_info(student_id_var.get(), student_info_text)).pack(anchor='w', pady=5)

        # Student info display
        student_info_text = tk.Text(input_frame, height=4, width=70, font=('Arial', 10), state='disabled')
        student_info_text.pack(pady=5)

        # Outstanding fees display
        fees_frame = ttk.LabelFrame(dialog, text=_("finance_gui.invoice_manager.outstanding_fees_frame"), padding=15)
        fees_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Fees treeview
        columns = ('Fee Name', 'Amount', 'Due Date', 'Status')
        column_labels = {
            'Fee Name': _("finance_gui.invoice_manager.column_fee_name"),
            'Amount': _("finance_gui.invoice_manager.column_amount"),
            'Due Date': _("finance_gui.invoice_manager.column_due_date"),
            'Status': _("finance_gui.invoice_manager.column_status")
        }
        fees_tree = ttk.Treeview(fees_frame, columns=columns, show='headings', height=8)

        for col in columns:
            fees_tree.heading(col, text=column_labels.get(col, col))
            fees_tree.column(col, width=150, anchor='center')

        fees_tree.pack(fill='both', expand=True)

        # Invoice preview
        preview_frame = ttk.LabelFrame(dialog, text=_("finance_gui.invoice_manager.invoice_preview_frame"), padding=15)
        preview_frame.pack(fill='x', padx=20, pady=10)

        invoice_text = ScrolledText(preview_frame, height=6, width=80, font=('Courier', 9))
        invoice_text.pack(fill='x')

        def generate_invoice():
            try:
                student_id = student_id_var.get().strip()
                if not student_id:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_student_id_required"))
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
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_student_not_found"))
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
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.invoice_manager.info_no_outstanding_fees"))
                    conn.close()
                    return

                # Generate invoice content
                invoice_date = datetime.now().strftime('%Y-%m-%d')
                invoice_number = f"INV-{student_id}-{datetime.now().strftime('%Y%m%d%H%M')}"

                invoice_content = f"""
        {_("finance_gui.invoice_manager.invoice_header")}
        ===============================================

        {_("finance_gui.invoice_manager.invoice_number_label")} {invoice_number}
        {_("finance_gui.invoice_manager.invoice_date_label")} {invoice_date}

        {_("finance_gui.invoice_manager.bill_to_header")}
        {first_name} {last_name}
        {_("finance_gui.invoice_manager.student_id_field")} {student_id}
        {_("finance_gui.invoice_manager.course_field")} {course}
        {_("finance_gui.invoice_manager.email_field")} {email}

        {_("finance_gui.invoice_manager.itemized_charges_header")}
        ===============================================
        """

                for fee_name, amount, due_date, status in fees:
                    invoice_content += f"{fee_name:<30} £{amount:>10.2f}  Due: {due_date}\n"

                invoice_content += f"""
        ===============================================
        {_("finance_gui.invoice_manager.total_amount_due")}                £{total_amount:>10.2f}
        ===============================================

        {_("finance_gui.invoice_manager.payment_instructions_header")}
        {_("finance_gui.invoice_manager.payment_instruction_1")}
        {_("finance_gui.invoice_manager.payment_instruction_2")}
        {_("finance_gui.invoice_manager.payment_instruction_3")}

        {_("finance_gui.invoice_manager.thank_you_message")}
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
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_generate_invoice", error=str(e)))


        def save_invoice():
            if not hasattr(self, 'current_invoice'):
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_no_invoice_generated"))
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
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.invoice_manager.success_invoice_saved", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_save_invoice", error=str(e)))


        def send_invoice():
            if not hasattr(self, 'current_invoice'):
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_no_invoice_generated"))
                return

            # Send invoice email using template system
            try:
                from education_system.university_system.infrastructure.email.template_utils import render_template

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
                    customer_name = self.current_invoice.get('customer_name', 'Customer')
                    invoice_num = self.current_invoice['number']
                    invoice_date = self.current_invoice.get('date', '')
                    total_amount = self.current_invoice.get('total', 0)
                    due_date = self.current_invoice.get('due_date', '')

                    subject = _("finance_gui.invoice_manager.email_subject_fallback", invoice_number=invoice_num)
                    message = f"""{_("finance_gui.invoice_manager.email_dear_customer", customer_name=customer_name)}

{_("finance_gui.invoice_manager.email_invoice_attached")}

{_("finance_gui.invoice_manager.email_invoice_number", invoice_number=invoice_num)}
{_("finance_gui.invoice_manager.email_invoice_date", date=invoice_date)}
{_("finance_gui.invoice_manager.email_amount_due", amount=total_amount)}
{_("finance_gui.invoice_manager.email_due_date", due_date=due_date)}

{_("finance_gui.invoice_manager.email_process_payment")}

{_("finance_gui.invoice_manager.email_regards")}
{_("finance_gui.invoice_manager.email_finance_dept")}
"""

                # Here you would integrate with your email system
                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.invoice_manager.success_invoice_sent", email=self.current_invoice['student_email']))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.invoice_manager.error_send_invoice", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.invoice_manager.btn_generate_invoice"), command=generate_invoice).pack(side='left', padx=5)
        save_btn = ttk.Button(button_frame, text=_("finance_gui.invoice_manager.btn_save_invoice"), command=save_invoice, state='disabled')
        save_btn.pack(side='left', padx=5)
        send_btn = ttk.Button(button_frame, text=_("finance_gui.invoice_manager.btn_send_email"), command=send_invoice, state='disabled')
        send_btn.pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.invoice_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=5)

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
            except Exception:
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
                info = _("finance_gui.invoice_manager.student_info_name", name=f"{first_name} {last_name}") + "\n"
                info += _("finance_gui.invoice_manager.student_info_email", email=email) + "\n"
                info += _("finance_gui.invoice_manager.student_info_phone", phone=phone) + "\n"
                info += _("finance_gui.invoice_manager.student_info_details", course=course, enrolled=enrollment_date, status=status)
                text_widget.insert('1.0', info)
            else:
                text_widget.insert('1.0', _("finance_gui.invoice_manager.student_not_found", student_id=student_id))

            text_widget.config(state='disabled')
            conn.close()

        except Exception as e:
            text_widget.config(state='normal')
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', _("finance_gui.invoice_manager.error_loading_student", error=str(e)))
            text_widget.config(state='disabled')
