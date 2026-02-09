"""Payment and transaction processing"""

from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from university_system.modules.shared.utils.i18n import get_text as _
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
from university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import database utilities - use centralized connection management
from university_system.infrastructure.database.db import get_connection

# Import optional modules with fallbacks for non-critical functionality
try:
    from university_system.infrastructure.email.email_service import send_email
except ImportError:
    def send_email(*args, **kwargs):
        """Fallback stub when email service is unavailable."""
        return True

try:
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    def configure_logging(name=None):
        """Fallback logging configuration."""
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        """Fallback log file path resolution."""
        from university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

# Import finance functions from common_imports module (explicit imports)
from university_system.modules.domain.finance.gui.finance.common_imports import (
    # Student credits
    add_student_credit,
    apply_credit_to_fees,
    view_credit_history,
    view_student_credits,
    # Payment plans
    create_payment_plan,
    # Payment processing
    generate_qr_payment_code,
    process_stripe_payment,
)

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




class TransactionManager:
    """Payment and transaction processing"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def create_payments_tab(self):
        """Create payments management tab"""
        payments_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['payments'] = payments_frame

        # Payments toolbar
        toolbar = tk.Frame(payments_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_record_payment"), command=self.show_payment_dialog,
                 bg=self.gui.layout.colors['success'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_search_payments"), command=self.search_payments,
                 bg=self.gui.layout.colors['secondary'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_payment_analytics"), command=self.show_payment_analytics,
                 bg=self.gui.layout.colors['warning'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_email_reminders"), command=self.send_payment_email_reminders,
                 bg=self.gui.layout.colors['info'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_refresh"), command=self.refresh_payments,
                 bg=self.gui.layout.colors['dark'], fg='white', font=('Arial', 9, 'bold')).pack(side='right', padx=5)
        
        # Payments table
        self.create_payments_table(payments_frame)
        
        # Load payments data
        self.refresh_payments()
    

    def create_payments_table(self, parent):
        """Create payments table with treeview"""
        table_frame = tk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('payment_id', 'student_id', 'amount', 'method', 'date', 'status')
        self.payments_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.payments_tree.heading('payment_id', text=_("finance_gui.transaction_manager.column_payment_id"))
        self.payments_tree.heading('student_id', text=_("finance_gui.transaction_manager.column_student_id"))
        self.payments_tree.heading('amount', text=_("finance_gui.transaction_manager.column_amount"))
        self.payments_tree.heading('method', text=_("finance_gui.transaction_manager.column_method"))
        self.payments_tree.heading('date', text=_("finance_gui.transaction_manager.column_date"))
        self.payments_tree.heading('status', text=_("finance_gui.transaction_manager.column_status"))
        
        self.payments_tree.column('payment_id', width=100)
        self.payments_tree.column('student_id', width=100)
        self.payments_tree.column('amount', width=100)
        self.payments_tree.column('method', width=120)
        self.payments_tree.column('date', width=100)
        self.payments_tree.column('status', width=80)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.payments_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.payments_tree.xview)
        self.payments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Pack table and scrollbars
        self.payments_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Context menu
        self.create_payments_context_menu()
    

    def create_payments_context_menu(self):
        """Create context menu for payments table"""
        self.payments_menu = tk.Menu(self.root, tearoff=0)
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_view_details"), command=self.view_payment_details)
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_process_refund"), command=self.process_refund)
        self.payments_menu.add_separator()
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_export_csv"), command=self.export_payments)
        
        self.payments_tree.bind("<Button-3>", self.show_payments_menu)
    

    def show_payment_dialog(self):
        """Show payment recording dialog"""
        # Simple payment dialog using built-in dialogs
        student_id = simpledialog.askstring(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.enter_student_id"))
        if student_id:
            amount = simpledialog.askfloat(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.enter_payment_amount"))
            if amount:
                method = simpledialog.askstring(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.payment_method_prompt"), initialvalue="card")
                if method:
                    try:
                        # Get authentication for audit trail
                        from university_system.infrastructure.shared_context import get_auth
                        auth = get_auth()
                        username = 'system'
                        if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                            user = auth.get_current_user()
                            username = user.get('username', 'system') if user else 'system'

                        # Save payment to database
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Verify student exists
                        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                        if cursor.fetchone()[0] == 0:
                            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                            conn.close()
                            return

                        # Insert payment record
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        payment_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute('''
                            INSERT INTO payments
                            (student_id, amount, payment_method, payment_date, status, created_by, created_at)
                            VALUES (?, ?, ?, ?, 'completed', ?, ?)
                        ''', (student_id, amount, method, payment_date, username, now))

                        payment_id = cursor.lastrowid

                        # Auto-allocate to outstanding fees
                        cursor.execute('''
                            SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                                   COALESCE(SUM(pa.amount), 0) as paid_amount,
                                   (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
                            FROM student_fees sf
                            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                            WHERE sf.student_id = ? AND sf.status != 'paid'
                            GROUP BY sf.student_fee_id
                            HAVING outstanding > 0
                            ORDER BY sf.due_date
                        ''', (student_id,))

                        fees = cursor.fetchall()
                        remaining = amount
                        allocations = []

                        for fee in fees:
                            if remaining <= 0:
                                break
                            fee_id, fee_name, total_amount, paid, outstanding = fee
                            allocation = min(remaining, outstanding)

                            # Create allocation
                            cursor.execute('''
                                INSERT INTO payment_allocations (payment_id, student_fee_id, amount, created_at)
                                VALUES (?, ?, ?, ?)
                            ''', (payment_id, fee_id, allocation, now))

                            # Update fee status
                            new_paid = paid + allocation
                            new_status = 'paid' if new_paid >= total_amount else 'partial'
                            cursor.execute('''
                                UPDATE student_fees SET status = ?, updated_at = ?
                                WHERE student_fee_id = ?
                            ''', (new_status, now, fee_id))

                            remaining -= allocation
                            allocations.append(f"£{allocation:.2f} → {fee_name}")

                        # Handle overpayment as credit
                        if remaining > 0:
                            cursor.execute('''
                                INSERT INTO student_credits
                                (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
                                VALUES (?, ?, ?, 'overpayment', ?, ?, ?, ?)
                            ''', (student_id, remaining, remaining, f'Overpayment from payment ID {payment_id}', username, now, now))
                            allocations.append(f"£{remaining:.2f} → Student Credit")

                        conn.commit()
                        conn.close()

                        # Success message with allocations
                        msg = _("finance_gui.transaction_manager.payment_recorded", amount=amount, student_id=student_id) + "\n"
                        if allocations:
                            msg += "\n" + _("finance_gui.transaction_manager.allocated_label") + "\n" + "\n".join(allocations)
                        messagebox.showinfo(_("finance_gui.messages.success"), msg)

                        self.refresh_payments()
                    except Exception as e:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_record_payment", error=str(e)))
                        import traceback
                        traceback.print_exc()
            self.refresh_dashboard()
    

    def gui_record_payment(self):
        """GUI wrapper for record_payment - Enhanced with auto-fill and service selection"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.record_payment_title"))
        dialog.geometry("900x750")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Create notebook for tabs inside scrollable frame
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Basic payment tab
        basic_tab = ttk.Frame(notebook, padding="15")
        notebook.add(basic_tab, text=_("finance_gui.transaction_manager.basic_payment_tab"))

        # Auto-fill with current user details
        auth = get_auth()
        current_user_id = ""
        current_user_name = ""
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            current_user_id = auth.current_user.get('student_id') or auth.current_user.get('user_id', '')
            first_name = auth.current_user.get('first_name', '')
            last_name = auth.current_user.get('last_name', '')
            current_user_name = f"{first_name} {last_name}".strip()

        # Current user info display
        if current_user_id:
            user_info_frame = ttk.LabelFrame(basic_tab, text="Current User", padding="10")
            user_info_frame.pack(fill='x', pady=(0, 10))
            ttk.Label(user_info_frame, text=f"ID: {current_user_id}  |  Name: {current_user_name}",
                     font=('Arial', 10, 'bold')).pack()

        # Student ID with auto-fill button
        student_id_frame = ttk.Frame(basic_tab)
        student_id_frame.pack(fill='x', pady=5)
        ttk.Label(student_id_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(side='left')
        student_id_var = tk.StringVar(value=current_user_id if current_user_id else "")
        student_entry = ttk.Entry(student_id_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(side='left', padx=5)
        if current_user_id:
            ttk.Button(student_id_frame, text="Use My ID",
                      command=lambda: student_id_var.set(current_user_id)).pack(side='left', padx=5)

        # Payment Purpose Dropdown - All Services
        ttk.Label(basic_tab, text="Payment For:", font=('Arial', 12, 'bold')).pack(pady=(15, 5))
        purpose_var = tk.StringVar(value="General Fee Payment")

        # Comprehensive list of all services/purposes in the system
        payment_purposes = [
            "=== Academic Services ===",
            "Tuition Fees",
            "Course Materials",
            "Lab Fees",
            "Exam Fees",
            "Library Fines",
            "Late Submission Penalty",
            "Academic Transcript",
            "Certificate Fee",
            "=== Food & Dining ===",
            "Restaurant - Meal",
            "Cafe - Coffee/Snacks",
            "Takeaway - Food Order",
            "Bar - Beverages",
            "Grocery - Shopping",
            "=== Health & Wellness ===",
            "Dentist - Dental Treatment",
            "Doctor - Medical Consultation",
            "Gym - Membership",
            "Pharmacy - Medication",
            "=== Personal Services ===",
            "Barber - Haircut",
            "Nail Bar - Manicure/Pedicure",
            "=== Retail & Shopping ===",
            "Butcher - Meat Products",
            "Music Shop - Instruments/Equipment",
            "Phone Shop - Mobile/Accessories",
            "Charity Shop - Donations/Purchases",
            "Shop Management - General Store",
            "=== Entertainment ===",
            "Cinema - Movie Tickets",
            "Betting Shop - Wagers",
            "=== Transportation ===",
            "Taxi - Ride Fare",
            "Car Rental - Vehicle Hire",
            "Train Station - Train Tickets",
            "=== Accommodation ===",
            "Housing - Rent Payment",
            "Accommodation Deposit",
            "=== Other Services ===",
            "Legal Services",
            "Student Union - Membership/Events",
            "Club/Society Fee",
            "Printing Services",
            "General Fee Payment",
            "Other"
        ]

        purpose_combo = ttk.Combobox(basic_tab, textvariable=purpose_var,
                                     values=payment_purposes,
                                     font=('Arial', 11), width=35)
        purpose_combo.pack(pady=5)

        # Amount
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_amount_label"), font=('Arial', 12)).pack(pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=amount_var, font=('Arial', 12), width=20).pack(pady=5)

        # Payment method with Student Finance Account option
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_method_label"), font=('Arial', 12)).pack(pady=5)
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(basic_tab, textvariable=method_var,
                                   values=["Student Finance Account", "Card", "Cash", "Bank Transfer", "Cheque", "Online"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(pady=5)

        # Show balance when Student Finance Account is selected
        balance_label_var = tk.StringVar(value="")
        balance_label = ttk.Label(basic_tab, textvariable=balance_label_var, font=('Arial', 10), foreground='blue')
        balance_label.pack(pady=2)

        def update_balance_display(*args):
            if method_var.get() == "Student Finance Account" and student_id_var.get():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?',
                                 (student_id_var.get(),))
                    result = cursor.fetchone()
                    balance = result[0] if result else 0.0
                    balance_label_var.set(f"Account Balance: £{balance:,.2f}")
                    conn.close()
                except Exception as e:
                    balance_label_var.set(f"Error checking balance: {e}")
            else:
                balance_label_var.set("")

        method_var.trace('w', update_balance_display)
        student_id_var.trace('w', update_balance_display)

        # Payment date
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_date_label"), font=('Arial', 12)).pack(pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(basic_tab, textvariable=date_var, font=('Arial', 12), width=20).pack(pady=5)

        # Transaction ID
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.transaction_id_label"), font=('Arial', 12)).pack(pady=5)
        trans_id_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=trans_id_var, font=('Arial', 12), width=30).pack(pady=5)

        # Notes
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.notes_label"), font=('Arial', 12)).pack(pady=5)
        notes_text = tk.Text(basic_tab, height=3, width=50, font=('Arial', 10))
        notes_text.pack(pady=5)
        # Auto-fill notes with payment purpose
        if purpose_var.get() and purpose_var.get() != "General Fee Payment":
            notes_text.insert("1.0", f"Payment for: {purpose_var.get()}")
        
        def record_payment():
            try:
                # Validate inputs
                if not all([student_id_var.get(), amount_var.get(), method_var.get(), date_var.get()]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.required_fields_missing"))
                    return

                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method = method_var.get()
                payment_date = date_var.get().strip()
                transaction_id = trans_id_var.get().strip()
                purpose = purpose_var.get()
                notes_input = notes_text.get("1.0", tk.END).strip()

                # Combine purpose and notes
                notes = f"Payment for: {purpose}"
                if notes_input and notes_input != notes:
                    notes += f"\n{notes_input}"

                if amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.amount_greater_zero"))
                    return

                # Get authentication
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Call original function logic
                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                    conn.close()
                    return

                # Handle Student Finance Account payment
                if payment_method == "Student Finance Account":
                    # Check balance
                    cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                                 (student_id,))
                    result = cursor.fetchone()

                    if not result:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           "Student finance account not found. Please create an account first.")
                        conn.close()
                        return

                    account_id, balance = result

                    if balance < amount:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           f"Insufficient balance. Available: £{balance:.2f}, Required: £{amount:.2f}")
                        conn.close()
                        return

                    # Deduct from student finance account
                    new_balance = balance - amount
                    cursor.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = datetime('now')
                        WHERE student_id = ?
                    ''', (new_balance, student_id))

                    # Record transaction in finance account history
                    cursor.execute('''
                        INSERT INTO student_finance_transactions
                        (account_id, student_id, transaction_type, amount, balance_before, balance_after,
                         description, processed_by)
                        VALUES (?, ?, 'payment', ?, ?, ?, ?, ?)
                    ''', (account_id, student_id, amount, balance, new_balance, notes, username))

                # Record payment
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, transaction_id, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, amount, payment_method, payment_date, transaction_id, notes,
                      username, now))
                
                payment_id = cursor.lastrowid
                
                # Auto-allocate to outstanding fees
                cursor.execute('''
                SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                       COALESCE(SUM(pa.amount), 0) as paid_amount,
                       (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                WHERE sf.student_id = ? AND sf.status != 'paid'
                GROUP BY sf.student_fee_id
                HAVING outstanding > 0
                ORDER BY sf.due_date
                ''', (student_id,))
                
                outstanding_fees = cursor.fetchall()
                remaining_payment = amount
                allocated_fees = []
                
                for fee in outstanding_fees:
                    if remaining_payment <= 0:
                        break
                    
                    fee_id, fee_name, total_amount, paid_amount, outstanding = fee
                    allocation_amount = min(remaining_payment, outstanding)
                    
                    # Create payment allocation
                    cursor.execute('''
                    INSERT INTO payment_allocations 
                    (payment_id, student_fee_id, amount, created_at)
                    VALUES (?, ?, ?, ?)
                    ''', (payment_id, fee_id, allocation_amount, now))
                    
                    # Update fee status
                    new_paid_amount = paid_amount + allocation_amount
                    new_status = 'paid' if new_paid_amount >= total_amount else 'partial'
                    
                    cursor.execute('''
                    UPDATE student_fees 
                    SET status = ?, updated_at = ?
                    WHERE student_fee_id = ?
                    ''', (new_status, now, fee_id))
                    
                    remaining_payment -= allocation_amount
                    allocated_fees.append(f"£{allocation_amount:.2f} to {fee_name}")
                
                # Handle overpayment as credit
                if remaining_payment > 0:
                    cursor.execute('''
                    INSERT INTO student_credits
                    (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, remaining_payment, remaining_payment, 'overpayment',
                          f'Overpayment from payment ID {payment_id}', username, now, now))
                
                conn.commit()
                conn.close()
                
                # Show success message with allocation details
                allocation_msg = "\n".join(allocated_fees) if allocated_fees else _("finance_gui.transaction_manager.no_outstanding_fees")
                if remaining_payment > 0:
                    allocation_msg += "\n\n" + _("finance_gui.transaction_manager.overpayment_credit", amount=remaining_payment)
                
                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.payment_success") + "\n" +
                                   _("finance_gui.transaction_manager.payment_id_label") + f" {payment_id}\n" +
                                   _("finance_gui.transaction_manager.amount_label_display") + f" £{amount:.2f}\n\n" +
                                   _("finance_gui.transaction_manager.allocations_label") + f"\n{allocation_msg}")
                
                dialog.destroy()
                self.update_status(f"Payment of £{amount:.2f} recorded for student {student_id}")
                
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_record_payment", error=str(e)))
        
        # Buttons
        button_frame = ttk.Frame(basic_tab)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_record"), command=record_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
    

    def refresh_payments(self):
        """Refresh payments data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT payment_id, student_id, amount, payment_method, payment_date, status
                FROM payments
                ORDER BY payment_date DESC
                LIMIT 100
                ''')
                
                payments = cursor.fetchall()
                conn.close()
                
                # Update UI in main thread using after() method
                self.root.after(0, lambda: self.update_payments_table(payments))
                
            except Exception as e:
                error_msg = f"Error refreshing payments: {e}"
                print(error_msg)
                # Update status in main thread
                self.root.after(0, lambda msg=error_msg: self.update_status(msg))
        
        # Only start thread if we have a main loop running
        if self.root.tk.call('winfo', 'exists', self.root._w):
            refresh_thread()
        else:
            # If no main loop, run directly
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT payment_id, student_id, amount, payment_method, payment_date, status
                FROM payments ORDER BY payment_date DESC LIMIT 100
                ''')
                payments = cursor.fetchall()
                conn.close()
                self.update_payments_table(payments)
            except Exception as e:
                print(f"Error refreshing payments: {e}")
            

    def update_payments_table(self, payments):
        """Update payments table"""
        # Clear existing data
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)

        # Insert new data (convert sqlite3.Row to tuple)
        for payment in payments:
            self.payments_tree.insert('', 'end', values=tuple(payment))
    

    def show_payments_menu(self, event):
        """Show payments context menu"""
        item = self.payments_tree.selection()
        if item:
            self.payments_menu.post(event.x_root, event.y_root)
    

    def search_payments(self):
        """Search payments with comprehensive search functionality"""
        # Create search dialog
        search_dialog = tk.Toplevel(self.root)
        search_dialog.title(_("finance_gui.transaction_manager.search_payments_title"))
        search_dialog.geometry("950x750")
        search_dialog.transient(self.root)
        search_dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(search_dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Search criteria frame
        criteria_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.search_criteria_frame"), padding=15)
        criteria_frame.pack(fill='x', padx=10, pady=10)

        # Student ID
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.student_id_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, sticky='w', padx=5, pady=5)

        # Payment method
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.payment_method_filter")).grid(row=0, column=2, sticky='w', padx=5, pady=5)
        method_var = tk.StringVar()
        method_combo = ttk.Combobox(criteria_frame, textvariable=method_var,
                                    values=["", "Card", "Cash", "Bank Transfer", "Cheque", "Online"],
                                    width=18)
        method_combo.grid(row=0, column=3, sticky='w', padx=5, pady=5)

        # Date range
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.from_date")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        from_date_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=from_date_var, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.to_date")).grid(row=1, column=2, sticky='w', padx=5, pady=5)
        to_date_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=to_date_var, width=18).grid(row=1, column=3, sticky='w', padx=5, pady=5)

        # Amount range
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.min_amount")).grid(row=2, column=0, sticky='w', padx=5, pady=5)
        min_amount_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=min_amount_var, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.max_amount")).grid(row=2, column=2, sticky='w', padx=5, pady=5)
        max_amount_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=max_amount_var, width=18).grid(row=2, column=3, sticky='w', padx=5, pady=5)

        # Transaction ID
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.transaction_id_filter")).grid(row=3, column=0, sticky='w', padx=5, pady=5)
        transaction_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=transaction_id_var, width=20).grid(row=3, column=1, sticky='w', padx=5, pady=5)

        # Status
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.status_filter")).grid(row=3, column=2, sticky='w', padx=5, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(criteria_frame, textvariable=status_var,
                                    values=["", "completed", "pending", "failed", "refunded"],
                                    width=18)
        status_combo.grid(row=3, column=3, sticky='w', padx=5, pady=5)

        # Results frame
        results_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.search_results_frame"), padding=15)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Results treeview
        columns = ('Payment ID', 'Student ID', 'Student Name', 'Amount', 'Method', 'Date', 'Transaction ID', 'Status')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100, anchor='center')

        results_tree.pack(side='left', fill='both', expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
        scrollbar.pack(side='right', fill='y')
        results_tree.configure(yscrollcommand=scrollbar.set)

        # Results label
        results_label = ttk.Label(scrollable_frame, text=_("finance_gui.transaction_manager.results_label", count=0))
        results_label.pack(pady=5)

        def perform_search():
            """Execute the search with given criteria"""
            try:
                # Clear previous results
                for item in results_tree.get_children():
                    results_tree.delete(item)

                # Build SQL query
                query = '''
                SELECT p.payment_id, p.student_id,
                       COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') as student_name,
                       p.amount, p.payment_method, p.payment_date, p.transaction_id, p.status
                FROM payments p
                LEFT JOIN students s ON p.student_id = s.student_id
                WHERE 1=1
                '''
                params = []

                # Add criteria
                if student_id_var.get().strip():
                    query += " AND p.student_id LIKE ?"
                    params.append(f"%{student_id_var.get().strip()}%")

                if method_var.get():
                    query += " AND p.payment_method = ?"
                    params.append(method_var.get())

                if from_date_var.get().strip():
                    query += " AND p.payment_date >= ?"
                    params.append(from_date_var.get().strip())

                if to_date_var.get().strip():
                    query += " AND p.payment_date <= ?"
                    params.append(to_date_var.get().strip())

                if min_amount_var.get().strip():
                    query += " AND p.amount >= ?"
                    params.append(float(min_amount_var.get().strip()))

                if max_amount_var.get().strip():
                    query += " AND p.amount <= ?"
                    params.append(float(max_amount_var.get().strip()))

                if transaction_id_var.get().strip():
                    query += " AND p.transaction_id LIKE ?"
                    params.append(f"%{transaction_id_var.get().strip()}%")

                if status_var.get():
                    query += " AND p.status = ?"
                    params.append(status_var.get())

                query += " ORDER BY p.payment_date DESC LIMIT 1000"

                # Execute query
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()

                # Display results
                for row in results:
                    payment_id, student_id, student_name, amount, method, date, trans_id, status = row
                    results_tree.insert('', 'end', values=(
                        payment_id,
                        student_id,
                        student_name,
                        f"£{amount:.2f}",
                        method,
                        date,
                        trans_id or 'N/A',
                        status
                    ))

                results_label.config(text=_("finance_gui.transaction_manager.results_label", count=len(results)))
                self.update_status(_("finance_gui.transaction_manager.search_completed", count=len(results)))

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount_format"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.search_failed", error=str(e)))

        def export_results():
            """Export search results to CSV"""
            try:
                if not results_tree.get_children():
                    messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_results_export"))
                    return

                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title=_("finance_gui.transaction_manager.export_search_results")
                )

                if filename:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Payment ID', 'Student ID', 'Student Name', 'Amount', 'Method', 'Date', 'Transaction ID', 'Status'])

                        for item in results_tree.get_children():
                            values = results_tree.item(item)['values']
                            writer.writerow(values)

                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.results_exported", filename=filename))

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_failed", error=str(e)))

        def clear_filters():
            """Clear all search filters"""
            student_id_var.set("")
            method_var.set("")
            from_date_var.set("")
            to_date_var.set("")
            min_amount_var.set("")
            max_amount_var.set("")
            transaction_id_var.set("")
            status_var.set("")

            # Clear results
            for item in results_tree.get_children():
                results_tree.delete(item)
            results_label.config(text=_("finance_gui.transaction_manager.results_label", count=0))

        # Buttons frame
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_search"), command=perform_search).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_export_results"), command=export_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_clear_filters"), command=clear_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=search_dialog.destroy).pack(side='left', padx=5)
    

    def view_payment_details(self):
        """View selected payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_view"))
            return
        
        payment_id = self.payments_tree.item(selection[0])['values'][0]
        
        # Create details dialog
        dialog = PaymentDetailsDialog(self.root, payment_id)
        self.root.wait_window(dialog.dialog)
    

    def process_refund(self):
        """Process refund for selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_refund"))
            return
        
        payment_data = self.payments_tree.item(selection[0])['values']
        payment_id = payment_data[0]
        student_id = payment_data[1]
        amount = float(payment_data[2])
        
        # Show refund dialog
        dialog = RefundDialog(self.root, payment_id, student_id, amount)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.refresh_payments()
            self.refresh_dashboard()
    

    def export_payments(self):
        """Export payments to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=_("finance_gui.transaction_manager.export_title")
            )
            
            if filename:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_method, p.payment_date, p.status
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                ORDER BY p.payment_date DESC
                ''')
                
                payments = cursor.fetchall()
                conn.close()
                
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Payment ID', 'Student ID', 'First Name', 'Last Name', 
                                   'Amount', 'Method', 'Date', 'Status'])
                    writer.writerows(payments)
                
                self.update_status(_("finance_gui.transaction_manager.export_complete", filename=filename))
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.export_complete", filename=filename))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_error", error=str(e)))
    

    def gui_process_refund(self):
        """GUI wrapper for process_refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.process_refund_title"))
        dialog.geometry("900x750")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Student selection
        student_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.student_info_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(anchor='w', pady=5)

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.load_payment_history"),
                  command=lambda: self.load_payment_history(student_id_var.get(), payments_tree)).pack(anchor='w', pady=5)

        # Payment history display
        history_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.payment_history_frame"), padding=15)
        history_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Payment ID', 'Amount', 'Method', 'Date', 'Transaction ID')
        payments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            payments_tree.heading(col, text=col)
            payments_tree.column(col, width=120, anchor='center')
        
        payments_tree.pack(fill='both', expand=True)

        # Refund details
        refund_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.refund_details_frame"), padding=15)
        refund_frame.pack(fill='x', padx=20, pady=10)

        # Refund type
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_type_label"), font=('Arial', 12)).pack(anchor='w')
        refund_type_var = tk.StringVar(value="partial")
        refund_type_combo = ttk.Combobox(refund_frame, textvariable=refund_type_var,
                                        values=["full", "partial", "withdrawal", "overpayment"],
                                        state='readonly', font=('Arial', 12))
        refund_type_combo.pack(anchor='w', pady=5)

        # Refund amount
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_amount_label"), font=('Arial', 12)).pack(anchor='w')
        refund_amount_var = tk.StringVar()
        ttk.Entry(refund_frame, textvariable=refund_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)

        # Refund reason
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_reason_label"), font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(refund_frame, height=3, width=60, font=('Arial', 10))
        reason_text.pack(anchor='w', pady=5)

        # Refund method
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_method_label"), font=('Arial', 12)).pack(anchor='w')
        refund_method_var = tk.StringVar(value="bank_transfer")
        method_combo = ttk.Combobox(refund_frame, textvariable=refund_method_var,
                                   values=["bank_transfer", "original_payment_method", "check", "cash"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(anchor='w', pady=5)
        
        def process_refund():
            try:
                student_id = student_id_var.get().strip()
                refund_amount = float(refund_amount_var.get())
                refund_type = refund_type_var.get()
                refund_method = refund_method_var.get()
                reason = reason_text.get("1.0", tk.END).strip()

                if not all([student_id, refund_amount > 0, refund_type, refund_method, reason]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                # Get authentication
                auth = get_auth()
                username = 'system'
                has_approve_permission = False

                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'
                    has_approve_permission = auth.has_permission('approve_refunds') if hasattr(auth, 'has_permission') else False

                # Get selected payment
                selected_item = payments_tree.selection()
                original_payment_id = None

                if selected_item:
                    payment_data = payments_tree.item(selected_item[0])['values']
                    original_payment_id = payment_data[0]
                    original_amount = float(payment_data[1].replace('£', ''))

                    if refund_amount > original_amount:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.refund_exceeds_original", amount=original_amount))
                        return

                # Create refund request
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                request_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO refunds
                (student_id, original_payment_id, refund_amount, refund_reason, refund_type,
                 refund_method, status, requested_by, request_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, original_payment_id, refund_amount, reason, refund_type,
                      refund_method, 'pending', username, request_date, now))

                refund_id = cursor.lastrowid

                # Auto-approve if user has permissions (simplified)
                if has_approve_permission:
                    cursor.execute('''
                    UPDATE refunds
                    SET status = 'approved', approved_by = ?, approval_date = ?
                    WHERE refund_id = ?
                    ''', (username, request_date, refund_id))
                    status_msg = _("finance_gui.transaction_manager.refund_approved")
                else:
                    status_msg = _("finance_gui.transaction_manager.refund_pending_approval")
                
                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.refund_success") + "\n" +
                                   _("finance_gui.transaction_manager.refund_id_label") + f" {refund_id}\n" +
                                   _("finance_gui.transaction_manager.amount_label_display") + f" £{refund_amount:.2f}\n" +
                                   _("finance_gui.transaction_manager.status_label") + f" {status_msg}")
                
                dialog.destroy()
                self.update_status(f"Refund request created for £{refund_amount:.2f}")
                
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_refund_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_process_refund", error=str(e)))


        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_process_refund"), command=process_refund).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
    

    def load_payment_history(self, student_id, tree_widget):
        """Load payment history for a student"""
        if not student_id:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT p.payment_id, p.amount, p.payment_method, p.payment_date, p.transaction_id
            FROM payments p
            WHERE p.student_id = ? AND p.status = 'completed'
            ORDER BY p.payment_date DESC
            ''', (student_id,))
            
            payments = cursor.fetchall()
            
            # Clear existing items
            for item in tree_widget.get_children():
                tree_widget.delete(item)
            
            # Add payment data
            for payment in payments:
                payment_id, amount, method, date, transaction_id = payment
                trans_id = transaction_id if transaction_id else "N/A"
                tree_widget.insert('', 'end', values=(payment_id, f"£{amount:.2f}", method, date, trans_id))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_load_payment_history", error=str(e)))
    

    def show_payment_analytics(self):
        """Show payment analytics"""
        try:
            # Call the original function
            self.analyze_payment_patterns()
            self.update_status(_("finance_gui.transaction_manager.payment_analytics_generated"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_payment_analytics", error=str(e)))
    

    def send_payment_email_reminders(self):
        """Send email reminders for payments and financial matters"""
        # Create email reminder dialog
        email_window = tk.Toplevel(self.root)
        email_window.title(_("finance_gui.transaction_manager.email_reminders_title"))
        email_window.geometry("750x680")
        email_window.transient(self.root)
        email_window.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(email_window)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Email type selection frame
        type_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.email_type_frame"), padding=10)
        type_frame.pack(fill='x', padx=10, pady=10)

        email_type_var = tk.StringVar(value="overdue_payment")
        email_types = [
            ("overdue_payment", _("finance_gui.transaction_manager.email_type_overdue")),
            ("upcoming_payment", _("finance_gui.transaction_manager.email_type_upcoming")),
            ("payment_confirmation", _("finance_gui.transaction_manager.email_type_confirmation")),
            ("fee_notification", _("finance_gui.transaction_manager.email_type_fee_notification")),
            ("scholarship_update", _("finance_gui.transaction_manager.email_type_scholarship")),
            ("financial_hold", _("finance_gui.transaction_manager.email_type_financial_hold")),
            ("custom", _("finance_gui.transaction_manager.email_type_custom"))
        ]
    
        for i, (value, text) in enumerate(email_types):
            ttk.Radiobutton(type_frame, text=text, variable=email_type_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)

        # Recipient selection frame
        recipient_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.recipients_frame"), padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=10)

        recipient_var = tk.StringVar(value="overdue_students")
        recipient_options = [
            ("overdue_students", _("finance_gui.transaction_manager.recipient_overdue")),
            ("upcoming_due", _("finance_gui.transaction_manager.recipient_upcoming")),
            ("all_students", _("finance_gui.transaction_manager.recipient_all")),
            ("financial_aid", _("finance_gui.transaction_manager.recipient_financial_aid")),
            ("scholarship_recipients", _("finance_gui.transaction_manager.recipient_scholarship")),
            ("custom", _("finance_gui.transaction_manager.recipient_custom"))
        ]
    
        for i, (value, text) in enumerate(recipient_options):
            ttk.Radiobutton(recipient_frame, text=text, variable=recipient_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)

        # Message composition frame
        message_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.message_frame"), padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Subject line
        ttk.Label(message_frame, text=_("finance_gui.transaction_manager.subject_label")).pack(anchor='w')
        subject_var = tk.StringVar(value=_("finance_gui.transaction_manager.subject_default"))
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, width=80)
        subject_entry.pack(fill='x', pady=(0, 10))

        # Message body
        ttk.Label(message_frame, text=_("finance_gui.transaction_manager.message_label")).pack(anchor='w')
        message_text = ScrolledText(message_frame, height=12, width=80)
        message_text.pack(fill='both', expand=True)
    
        # Default message templates
        def update_default_message(*args):
            email_type = email_type_var.get()
            template_map = {
                "overdue_payment": "overdue_payment_notice",
                "upcoming_payment": "upcoming_payment_reminder",
                "payment_confirmation": "payment_confirmation_notice",
                "fee_notification": "fee_notification",
                "scholarship_update": "scholarship_update_notification",
                "financial_hold": "financial_hold_notice"
            }
    
            if email_type in template_map:
                try:
                    from university_system.infrastructure.email.template_utils import render_template
                    _, default_message = render_template(template_map[email_type], {})
                except Exception:
                    default_message = ""
            else:
                default_message = _("finance_gui.transaction_manager.default_custom_message")
    
            message_text.delete('1.0', tk.END)
            message_text.insert('1.0', default_message)
    
        email_type_var.trace('w', update_default_message)
        update_default_message()  # Set initial message

        # Buttons frame
        buttons_frame = ttk.Frame(scrollable_frame)
        buttons_frame.pack(fill='x', padx=10, pady=10)
    
        def preview_recipients():
            """Preview the list of recipients"""
            try:
                recipient_type = recipient_var.get()
                recipients = self._get_finance_email_recipients(recipient_type)

                preview_window = tk.Toplevel(email_window)
                preview_window.title(_("finance_gui.transaction_manager.recipients_preview_title"))
                preview_window.geometry("500x400")
                preview_window.transient(email_window)

                ttk.Label(preview_window, text=_("finance_gui.transaction_manager.recipients_count", count=len(recipients))).pack(anchor='w', padx=10, pady=10)
    
                recipients_list = tk.Listbox(preview_window, height=20)
                recipients_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))
    
                for recipient in recipients:
                    display_text = f"{recipient['name']} ({recipient['email']})"
                    if 'balance' in recipient:
                        display_text += f" - Balance: ${recipient['balance']:.2f}"
                    recipients_list.insert(tk.END, display_text)
    
                ttk.Button(preview_window, text=_("finance_gui.transaction_manager.btn_close"),
                          command=preview_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_preview_recipients", error=str(e)))
    
        def send_emails():
            """Send the email reminders"""
            try:
                email_type = email_type_var.get()
                recipient_type = recipient_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()
    
                if not subject or not message:
                    messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.enter_subject_message"))
                    return
    
                # Get recipient list
                recipients = self._get_finance_email_recipients(recipient_type)
    
                if not recipients:
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.no_recipients_found"))
                    return
    
                # Try to send emails via email GUI
                success = self._send_finance_emails_via_gui(recipients, subject, message, email_type)
    
                if success:
                    email_window.destroy()
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.emails_sent_success", count=len(recipients)))
                else:
                    # Fallback: show email details for manual sending
                    self._show_finance_email_fallback_dialog(recipients, subject, message)
    
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_send_emails", error=str(e)))
    
        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.preview_recipients"),
                  command=preview_recipients).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.send_emails"),
                  command=send_emails).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.btn_cancel"),
                  command=email_window.destroy).pack(side='right')
    

    def _get_finance_email_recipients(self, recipient_type):
        """Get email recipients based on financial criteria"""
        recipients = []
        try:
            conn = get_connection()
            cursor = conn.cursor()

            if recipient_type == "overdue_students":
                # Students with overdue payments (more than 30 days past due)
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date < date('now', '-30 days') AND f.status != 'paid'
                  AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "upcoming_due":
                # Students with payments due in the next 7 days
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date BETWEEN date('now') AND date('now', '+7 days')
                  AND f.status != 'paid' AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "all_students":
                # All students with outstanding balances
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.status != 'paid' AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "financial_aid":
                # Financial aid recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                JOIN financial_aid fa ON s.student_id = fa.student_id
                WHERE fa.status = 'Approved' AND s.email_address IS NOT NULL AND s.email_address != ''
                ''')

            elif recipient_type == "scholarship_recipients":
                # Scholarship recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                JOIN scholarships sch ON s.student_id = sch.student_id
                WHERE sch.status = 'Active' AND s.email_address IS NOT NULL AND s.email_address != ''
                ''')
    
            for row in cursor.fetchall():
                recipient_data = {
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'email': row[3]
                }
                if len(row) > 4:  # Balance information available
                    recipient_data['balance'] = row[4]
                recipients.append(recipient_data)
    
            conn.close()
    
        except Exception as e:
            print(f"Error getting finance email recipients: {e}")
    
        return recipients
    

    def _send_finance_emails_via_gui(self, recipients, subject, message, email_type):
        """Try to send emails via email service"""
        try:
            # Try to import and use email service directly
            from university_system.infrastructure.email.email_service import send_email

            # Send emails through email service
            for recipient in recipients:
                personalized_message = message.replace("[Student Name]", recipient['name'])
                if 'balance' in recipient:
                    personalized_message = personalized_message.replace("[Balance]", f"${recipient['balance']:.2f}")

                send_email(
                    recipient_email=recipient['email'],
                    subject=subject,
                    body=personalized_message
                )

            return True

        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending finance emails: {e}")
            return False
    

    def _show_finance_email_fallback_dialog(self, recipients, subject, message):
        """Show fallback dialog with email details for manual sending"""
        fallback_window = tk.Toplevel(self.root)
        fallback_window.title(_("finance_gui.transaction_manager.email_fallback_title"))
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)

        ttk.Label(fallback_window, text=_("finance_gui.transaction_manager.email_gui_unavailable"),
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text=_("finance_gui.transaction_manager.email_details_frame"), padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        details_text = ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)
    
        email_details = f"Subject: {subject}\n\n"
        email_details += f"Recipients ({len(recipients)}):\n"
        for recipient in recipients:
            email_details += f"  - {recipient['name']} ({recipient['email']})"
            if 'balance' in recipient:
                email_details += f" - Balance: ${recipient['balance']:.2f}"
            email_details += "\n"
        email_details += f"\nMessage:\n{message}"
    
        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')
    
        ttk.Button(fallback_window, text=_("finance_gui.transaction_manager.btn_close"),
                  command=fallback_window.destroy).pack(pady=10)
    

    def analyze_payment_patterns(self):
        """Analyze payment patterns and display insights"""
        try:
            # Create analysis dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_("finance_gui.transaction_manager.payment_analysis_title"))
            dialog.geometry("700x600")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_("finance_gui.transaction_manager.payment_analysis_title"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Create text widget for results
            results_text = ScrolledText(main_frame, width=80, height=30,
                                       font=('Courier', 10), wrap=tk.WORD)
            results_text.pack(fill=tk.BOTH, expand=True)

            # Analyze payment data
            conn = get_connection()
            cursor = conn.cursor()

            # CTE to combine all transaction sources
            all_transactions_cte = '''
                WITH all_transactions AS (
                    SELECT payment_method, amount, payment_date as trans_date, 'Central' as source
                    FROM payments WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Gym' as source
                    FROM gym_transactions
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Dentist' as source
                    FROM dentist_transactions
                    UNION ALL
                    SELECT payment_method, total_amount as amount, transaction_date as trans_date, 'Grocery' as source
                    FROM grocery_transactions
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Betting' as source
                    FROM betting_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, total_amount as amount, transaction_date as trans_date, 'Shop' as source
                    FROM shop_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Butcher' as source
                    FROM butcher_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Barber' as source
                    FROM barber_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'NailBar' as source
                    FROM nailbar_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'CarRental' as source
                    FROM carrental_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'PhoneShop' as source
                    FROM phoneshop_transactions WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'MusicShop' as source
                    FROM musicshop_transactions WHERE status = 'completed'
                )
            '''

            analysis = "PAYMENT PATTERN ANALYSIS REPORT\n"
            analysis += "=" * 70 + "\n\n"

            # 1. Payment Method Distribution
            analysis += "1. PAYMENT METHOD DISTRIBUTION\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT payment_method, COUNT(*) as count, SUM(amount) as total
                FROM all_transactions
                GROUP BY payment_method
                ORDER BY total DESC
            ''')
            methods = cursor.fetchall()
            if methods:
                for method in methods:
                    analysis += f"   {method[0]}: {method[1]} payments, £{method[2]:,.2f} total\n"
            else:
                analysis += "   No payment data available\n"
            analysis += "\n"

            # 2. Payment Timing Trends (by day of week)
            analysis += "2. PAYMENT TIMING (BY DAY OF WEEK)\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT CASE CAST(strftime('%w', trans_date) AS INTEGER)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END as day_name,
                COUNT(*) as count,
                AVG(amount) as avg_amount
                FROM all_transactions
                WHERE trans_date IS NOT NULL
                GROUP BY strftime('%w', trans_date)
                ORDER BY count DESC
            ''')
            days = cursor.fetchall()
            if days:
                for day in days:
                    analysis += f"   {day[0]}: {day[1]} payments, £{day[2]:.2f} avg\n"
            else:
                analysis += "   No payment timing data available\n"
            analysis += "\n"

            # 3. Monthly Payment Trends
            analysis += "3. MONTHLY PAYMENT TRENDS\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT strftime('%Y-%m', trans_date) as month,
                       COUNT(*) as count,
                       SUM(amount) as total
                FROM all_transactions
                WHERE trans_date IS NOT NULL
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            ''')
            months = cursor.fetchall()
            if months:
                for month in months:
                    analysis += f"   {month[0]}: {month[1]} payments, £{month[2]:,.2f}\n"
            else:
                analysis += "   No monthly data available\n"
            analysis += "\n"

            # 4. Average Payment Amount by Status
            analysis += "4. PAYMENT STATISTICS\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT
                    COUNT(*) as total_payments,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount,
                    MIN(amount) as min_amount,
                    MAX(amount) as max_amount
                FROM all_transactions
            ''')
            stats = cursor.fetchone()
            if stats and stats[0] > 0:
                analysis += f"   Total Payments: {stats[0]}\n"
                analysis += f"   Total Amount: £{stats[1]:,.2f}\n"
                analysis += f"   Average Payment: £{stats[2]:.2f}\n"
                analysis += f"   Smallest Payment: £{stats[3]:.2f}\n"
                analysis += f"   Largest Payment: £{stats[4]:.2f}\n"
            else:
                analysis += "   No payment statistics available\n"
            analysis += "\n"

            # 5. Recent Payment Activity (last 30 days)
            analysis += "5. RECENT ACTIVITY (LAST 30 DAYS)\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT COUNT(*) as count, SUM(amount) as total
                FROM all_transactions
                WHERE trans_date >= date('now', '-30 days')
            ''')
            recent = cursor.fetchone()
            if recent and recent[0] > 0:
                analysis += f"   Payments: {recent[0]}\n"
                analysis += f"   Total Amount: £{recent[1]:,.2f}\n"
            else:
                analysis += "   No recent payment activity\n"

            conn.close()

            # Display results
            results_text.insert('1.0', analysis)
            results_text.config(state='disabled')

            # Store analysis for email
            self.current_analytics_report = analysis

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))

            def send_to_admin():
                """Send analytics report to admin via email"""
                try:
                    # Get admin email from database
                    admin_conn = get_connection()
                    admin_cursor = admin_conn.cursor()

                    # Try to find admin user email from users table
                    admin_cursor.execute('''
                        SELECT email FROM users
                        WHERE role = 'admin'
                        LIMIT 1
                    ''')
                    admin_result = admin_cursor.fetchone()

                    if not admin_result:
                        # Fallback: look for admin in students table
                        admin_cursor.execute('''
                            SELECT email_address FROM students
                            WHERE LOWER(student_id) LIKE '%admin%'
                            OR LOWER(email_address) LIKE '%admin%'
                            LIMIT 1
                        ''')
                        admin_result = admin_cursor.fetchone()

                    admin_conn.close()

                    if not admin_result or not admin_result[0]:
                        # Ask user for admin email
                        admin_email = simpledialog.askstring(
                            _("finance_gui.transaction_manager.admin_email_title"),
                            _("finance_gui.transaction_manager.admin_email_prompt"),
                            parent=dialog
                        )
                        if not admin_email:
                            return
                    else:
                        admin_email = admin_result[0]

                    # Validate email format
                    if '@' not in admin_email or '.' not in admin_email:
                        messagebox.showerror(_("finance_gui.transaction_manager.invalid_email_title"),
                                           _("finance_gui.transaction_manager.invalid_email_message", email=admin_email),
                                           parent=dialog)
                        return

                    # Send email using email service with template
                    from university_system.infrastructure.email.email_service import send_email
                    from university_system.infrastructure.email.template_utils import render_template

                    report_date = datetime.now().strftime('%Y-%m-%d')
                    generated_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Render email from template
                    subject, message = render_template('reports/payment_analytics_report', {
                        'report_date': report_date,
                        'generated_timestamp': generated_timestamp,
                        'report_content': analysis
                    })

                    # Fallback if template not found
                    if not subject or not message:
                        subject = f"Payment Analytics Report - {report_date}"
                        message = f"Payment Pattern Analysis Report\nGenerated: {generated_timestamp}\n\n{analysis}"

                    # Send email
                    success = send_email(
                        admin_email,
                        subject,
                        message
                    )

                    if success:
                        messagebox.showinfo(
                            _("finance_gui.transaction_manager.email_sent_title"),
                            _("finance_gui.transaction_manager.email_sent_message", email=admin_email),
                            parent=dialog
                        )
                        print(f"Analytics report emailed to {admin_email}")
                    else:
                        messagebox.showwarning(
                            _("finance_gui.transaction_manager.email_failed_title"),
                            _("finance_gui.transaction_manager.email_failed_message", email=admin_email),
                            parent=dialog
                        )

                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_send_email", error=str(e)), parent=dialog)
                    import traceback
                    traceback.print_exc()

            ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_send_to_admin"), command=send_to_admin).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=5)

            print("✅ Payment pattern analysis completed")

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_analyze_patterns", error=str(e)))
            print(f"Error in analyze_payment_patterns: {e}")
    

    def gui_process_stripe_payment(self):
        """GUI wrapper for process_stripe_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.stripe_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.stripe_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Payment method ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.payment_method_id_label")).pack(anchor='w', pady=5)
        payment_method_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=payment_method_var).pack(anchor='w', fill='x', pady=5)
        
        def process_payment():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method_id = payment_method_var.get().strip()
                
                if not all([student_id, amount > 0, payment_method_id]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                result = process_stripe_payment(student_id, amount, payment_method_id)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.stripe_payment_success", transaction_id=result.get('id', 'N/A')))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.stripe_payment_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_process_payment"), command=process_payment).pack(pady=20)
    

    def gui_generate_qr_payment_code(self):
        """GUI wrapper for generate_qr_payment_code"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.qr_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_details_frame"), padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.description_label")).pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)
        
        # QR Code display
        qr_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.qr_code_frame"), padding=20)
        qr_frame.pack(fill='both', expand=True, padx=20, pady=10)

        qr_label = ttk.Label(qr_frame, text=_("finance_gui.transaction_manager.qr_placeholder"))
        qr_label.pack(pady=20)
        
        def generate_qr():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                description = desc_var.get().strip()
                
                if not all([student_id, amount > 0]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_amount_required"))
                    return

                qr_code_data = generate_qr_payment_code(student_id, amount, description)
                qr_label.config(text=_("finance_gui.transaction_manager.qr_generated", student_id=student_id, amount=amount))
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.qr_success"))

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.qr_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_generate_qr"), command=generate_qr).pack(pady=20)
    

    def gui_apply_credit_to_fees(self):
        """GUI wrapper for apply_credit_to_fees"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.apply_credit_title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.credit_application_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Credit ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_id_label")).pack(anchor='w', pady=5)
        credit_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=credit_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount to apply
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_to_apply_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        def apply_credit():
            try:
                student_id = student_id_var.get().strip()
                credit_id = int(credit_id_var.get())
                amount = float(amount_var.get())
                
                if not all([student_id, credit_id, amount > 0]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                apply_credit_to_fees(student_id, credit_id, amount)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_applied_success"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_credit_id_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.apply_credit_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_apply_credit"), command=apply_credit).pack(pady=20)
    

    def gui_view_credit_history(self):
        """GUI wrapper for view_credit_history"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.view_credit_history_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)
        
        def show_history():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
                return
            
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                view_credit_history(student_id)
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                history_text.delete('1.0', tk.END)
                history_text.insert('1.0', output)
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.view_credit_history_failed", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_view_history"), command=show_history).pack(side='left', padx=10)
        
        # History display
        history_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
        history_text.pack(fill='both', expand=True, padx=10, pady=10)
    

    def gui_view_student_credits(self):
        """GUI wrapper for view_student_credits"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.view_credits_title"))
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)
        
        def show_credits():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
                return
            
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                view_student_credits(student_id)
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                credits_text.delete('1.0', tk.END)
                credits_text.insert('1.0', output)
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.view_credits_failed", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_view_credits"), command=show_credits).pack(side='left', padx=10)
        
        # Credits display
        credits_text = ScrolledText(dialog, height=20, width=70, font=('Courier', 10))
        credits_text.pack(fill='both', expand=True, padx=10, pady=10)
    

    def gui_add_student_credit(self):
        """GUI wrapper for add_student_credit"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.add_credit_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.credit_details_frame"), padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Credit amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Credit source
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_source_label")).pack(anchor='w', pady=5)
        source_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=source_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.description_label")).pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)
        
        def add_credit():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                source = source_var.get().strip()
                description = desc_var.get().strip()
                
                if not all([student_id, amount > 0, source]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                add_student_credit(student_id, amount, source, description)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_added_success"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.add_credit_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_add_credit"), command=add_credit).pack(pady=20)
    

    def gui_manage_student_credits(self):
        """GUI wrapper for student credits management"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.manage_credits_title"))
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create notebook for different credit operations
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # View credits tab
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text=_("finance_gui.transaction_manager.tab_view_credits"))

        # Student selection for viewing
        search_frame = ttk.LabelFrame(view_tab, text=_("finance_gui.transaction_manager.student_search_frame"), padding=10)
        search_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(search_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        view_student_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=view_student_var, width=15).pack(side='left', padx=5)
        ttk.Button(search_frame, text=_("finance_gui.transaction_manager.btn_load_credits"),
                  command=lambda: self.load_student_credits(view_student_var.get(), credits_tree)).pack(side='left', padx=10)

        # Credits display
        credits_frame = ttk.LabelFrame(view_tab, text=_("finance_gui.transaction_manager.active_credits_frame"), padding=10)
        credits_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('Credit ID', 'Amount', 'Remaining', 'Source', 'Description', 'Expires', 'Created')
        credits_tree = ttk.Treeview(credits_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            credits_tree.heading(col, text=col)
            width = 150 if col in ['Description'] else 100
            credits_tree.column(col, width=width, anchor='center')
        
        credits_scroll = ttk.Scrollbar(credits_frame, orient='vertical', command=credits_tree.yview)
        credits_tree.configure(yscrollcommand=credits_scroll.set)
        
        credits_tree.pack(side='left', fill='both', expand=True)
        credits_scroll.pack(side='right', fill='y')
        
        # Add credit tab
        add_tab = ttk.Frame(notebook)
        notebook.add(add_tab, text=_("finance_gui.transaction_manager.tab_add_credit"))

        add_frame = ttk.LabelFrame(add_tab, text=_("finance_gui.transaction_manager.add_new_credit_frame"), padding=20)
        add_frame.pack(fill='x', padx=20, pady=20)

        # Student ID for adding credit
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        add_student_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=add_student_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Credit amount
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.credit_amount_pound_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        credit_amount_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=credit_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)

        # Credit source
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.credit_source_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        source_var = tk.StringVar(value="adjustment")
        source_combo = ttk.Combobox(add_frame, textvariable=source_var,
                                   values=["overpayment", "refund", "scholarship", "adjustment", "goodwill", "other"],
                                   state='readonly', font=('Arial', 12))
        source_combo.pack(anchor='w', pady=5)

        # Description
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.description_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        desc_entry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=desc_entry_var, font=('Arial', 12), width=50).pack(anchor='w', pady=5)

        # Expiry date
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.expiry_date_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        expiry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=expiry_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)
        
        def add_credit():
            try:
                student_id = add_student_var.get().strip()
                credit_amount = float(credit_amount_var.get())
                credit_source = source_var.get()
                description = desc_entry_var.get().strip()
                expiry_date = expiry_var.get().strip()
                
                if not all([student_id, credit_amount > 0, credit_source]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_amount_source_required"))
                    return
                
                # Validate expiry date if provided
                if expiry_date:
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_date_format"))
                        return
                else:
                    expiry_date = None
                
                # Check if student exists
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                    conn.close()
                    return
                
                # Create the credit
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO student_credits 
                (student_id, credit_amount, remaining_amount, credit_source, description, 
                 expiry_date, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, credit_amount, credit_amount, credit_source, description,
                      expiry_date, auth.current_user['username'], now, now))
                
                credit_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_added_with_id", credit_id=credit_id))
                
                # Clear form
                add_student_var.set("")
                credit_amount_var.set("")
                desc_entry_var.set("")
                expiry_var.set("")
                
                self.update_status(f"Credit of £{credit_amount:.2f} added for student {student_id}")
                
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_credit_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.add_credit_failed", error=str(e)))

        ttk.Button(add_frame, text=_("finance_gui.transaction_manager.btn_add_credit"), command=add_credit).pack(anchor='w', pady=20)
    

    def load_student_credits(self, student_id, tree_widget):
        """Load student credits into tree widget"""
        if not student_id:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT credit_id, credit_amount, remaining_amount, credit_source, description, 
                   expiry_date, created_at, status
            FROM student_credits
            WHERE student_id = ? AND status = 'active'
            ORDER BY created_at DESC
            ''', (student_id,))
            
            credits = cursor.fetchall()
            
            # Clear existing items
            for item in tree_widget.get_children():
                tree_widget.delete(item)
            
            total_credits = 0
            for credit in credits:
                credit_id, amount, remaining, source, description, expiry, created, status = credit
                expiry_str = expiry if expiry else "No expiry"
                desc_str = description if description else "N/A"
                
                tree_widget.insert('', 'end', values=(
                    credit_id, f"£{amount:.2f}", f"£{remaining:.2f}", 
                    source, desc_str, expiry_str, created
                ))
                total_credits += remaining
            
            # Update status with total
            if credits:
                self.update_status(f"Student {student_id} has £{total_credits:.2f} in active credits")
            else:
                self.update_status(f"No active credits found for student {student_id}")
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_credits_failed", error=str(e)))
    

    def create_core_finance_tab(self):
        """Create core finance operations tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['core_finance'] = tab

        # Create scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Button frame
        button_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.core_finance_frame"), padding=20)
        button_frame.pack(fill='x', padx=20, pady=10)

        buttons = [
            (_("finance_gui.transaction_manager.btn_assign_fees"), self.gui_assign_fees_to_student, "#3498db"),
            (_("finance_gui.transaction_manager.btn_record_payment"), self.gui_record_payment, "#27ae60"),
            (_("finance_gui.transaction_manager.btn_generate_invoice"), self.gui_generate_invoice, "#e74c3c"),
            (_("finance_gui.transaction_manager.btn_process_refund_full"), self.gui_process_refund, "#f39c12"),
            (_("finance_gui.transaction_manager.btn_manage_credits"), self.gui_manage_student_credits, "#9b59b6"),
            (_("finance_gui.transaction_manager.btn_view_statement"), self.gui_view_student_financial_statement, "#34495e")
        ]
        
        for i, (text, command, color) in enumerate(buttons):
            btn = tk.Button(button_frame, text=text, command=command,
                          font=('Arial', 12, 'bold'), bg=color, fg='white',
                          width=35, height=2, relief='raised', bd=3)
            btn.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='ew')
        
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        # Quick stats frame
        stats_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.quick_stats_frame"), padding=20)
        stats_frame.pack(fill='x', padx=20, pady=10)
        
        self.stats_labels = {}
        self.update_quick_stats(stats_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    

    def create_payment_plans_tab(self):
        """Create payment plans management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['payment_plans'] = tab
        
        # Main frame
        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Buttons frame
        button_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.transaction_manager.payment_plan_management_frame"), padding=15)
        button_frame.pack(fill='x', pady=(0, 20))

        buttons = [
            (_("finance_gui.transaction_manager.btn_create_plan"), self.gui_create_payment_plan),
            (_("finance_gui.transaction_manager.btn_view_active_plans"), self.gui_view_active_payment_plans),
            (_("finance_gui.transaction_manager.btn_modify_plan"), self.gui_modify_payment_plan),
            (_("finance_gui.transaction_manager.btn_process_plan_payment"), self.gui_process_payment_plan_payment),
            (_("finance_gui.transaction_manager.btn_cancel_plan"), self.gui_cancel_payment_plan)
        ]
        
        for i, (text, command) in enumerate(buttons):
            btn = ttk.Button(button_frame, text=text, command=command, width=25)
            btn.grid(row=i//3, column=i%3, padx=10, pady=5, sticky='ew')
        
        # Plans display frame
        display_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        display_frame.pack(fill='both', expand=True)
        
        # Treeview for plans
        columns = ('Plan ID', 'Student', 'Template', 'Total', 'Remaining', 'Next Due')
        self.plans_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.plans_tree.heading(col, text=col)
            self.plans_tree.column(col, width=120, anchor='center')
        
        # Scrollbars for treeview
        plans_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.plans_tree.yview)
        plans_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.plans_tree.xview)
        self.plans_tree.configure(yscrollcommand=plans_v_scroll.set, xscrollcommand=plans_h_scroll.set)
        
        self.plans_tree.pack(side='left', fill='both', expand=True)
        plans_v_scroll.pack(side='right', fill='y')
        plans_h_scroll.pack(side='bottom', fill='x')
        
        # Load initial data
        self.refresh_payment_plans()
    

    def gui_create_payment_plan(self):
        """GUI for creating payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.create_plan_title"))
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_info_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12))
        student_entry.pack(anchor='w', pady=5, fill='x')
        
        # Outstanding fees display
        fees_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.outstanding_fees_frame"), padding=15)
        fees_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        fees_text = ScrolledText(fees_frame, height=6, font=('Courier', 10))
        fees_text.pack(fill='both', expand=True)
        
        def load_outstanding_fees():
            student_id = student_id_var.get().strip()
            if not student_id:
                return
                
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.status, sf.due_date
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ? AND sf.status != 'paid'
                ORDER BY sf.due_date
                ''', (student_id,))
                
                outstanding_fees = cursor.fetchall()
                
                fees_text.delete('1.0', tk.END)
                
                if not outstanding_fees:
                    fees_text.insert('1.0', f"No outstanding fees found for student {student_id}")
                    total_outstanding_var.set("0.00")
                    conn.close()
                    return
                
                total_outstanding = sum(fee[2] for fee in outstanding_fees)
                total_outstanding_var.set(f"{total_outstanding:.2f}")
                
                fees_content = f"Outstanding Fees for Student {student_id}:\n"
                fees_content += "=" * 60 + "\n"
                
                for fee_id, fee_name, amount, status, due_date in outstanding_fees:
                    fees_content += f"{fee_name:<30} £{amount:>8.2f}  Due: {due_date}\n"
                
                fees_content += "=" * 60 + "\n"
                fees_content += f"Total Outstanding: £{total_outstanding:.2f}"
                
                fees_text.insert('1.0', fees_content)
                conn.close()
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_fees_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_load_outstanding_fees"),
                  command=load_outstanding_fees).pack(anchor='w', pady=5)
        
        # Plan configuration
        plan_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.plan_config_frame"), padding=15)
        plan_frame.pack(fill='x', padx=20, pady=10)
        
        # Load payment plan templates
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT template_id, template_name, description, number_of_installments, 
                   installment_frequency, setup_fee, interest_rate
            FROM payment_plan_templates
            WHERE is_active = 1
            ORDER BY number_of_installments
            ''')
            templates = cursor.fetchall()
            conn.close()
        except Exception:
            templates = []
        
        ttk.Label(plan_frame, text=_("finance_gui.transaction_manager.plan_template_label"), font=('Arial', 12)).pack(anchor='w')
        template_var = tk.StringVar()
        template_combo = ttk.Combobox(plan_frame, textvariable=template_var, state='readonly', width=50)
        
        template_values = []
        self.template_data = {}
        
        for template in templates:
            template_id, name, desc, installments, frequency, setup_fee, interest_rate = template
            display_text = f"{name} - {installments} {frequency} payments (Setup: £{setup_fee:.2f}, Interest: {interest_rate}%)"
            template_values.append(display_text)
            self.template_data[display_text] = template
        
        template_combo['values'] = template_values
        template_combo.pack(anchor='w', pady=5, fill='x')
        
        # Plan summary
        summary_frame = ttk.LabelFrame(plan_frame, text=_("finance_gui.transaction_manager.plan_summary_frame"), padding=10)
        summary_frame.pack(fill='x', pady=10)

        total_outstanding_var = tk.StringVar(value="0.00")
        ttk.Label(summary_frame, text=_("finance_gui.transaction_manager.outstanding_amount_label")).pack(side='left')
        ttk.Label(summary_frame, textvariable=total_outstanding_var, font=('Arial', 12, 'bold')).pack(side='left')
        
        def calculate_plan_summary():
            selected_template = template_var.get()
            if not selected_template or selected_template not in self.template_data:
                return
                
            try:
                outstanding = float(total_outstanding_var.get())
                if outstanding <= 0:
                    return
                
                template_info = self.template_data[selected_template]
                _, _, _, num_installments, frequency, setup_fee, interest_rate = template_info
                
                principal_amount = outstanding
                interest_amount = principal_amount * (interest_rate / 100)
                total_with_interest = principal_amount + interest_amount + setup_fee
                installment_amount = total_with_interest / num_installments
                
                summary_text = f"""
    Plan Details:
    - Principal: £{principal_amount:.2f}
    - Setup Fee: £{setup_fee:.2f}
    - Interest ({interest_rate}%): £{interest_amount:.2f}
    - Total Amount: £{total_with_interest:.2f}
    - Installments: {num_installments}
    - Amount per installment: £{installment_amount:.2f}
    """
                plan_summary_text.delete('1.0', tk.END)
                plan_summary_text.insert('1.0', summary_text)

            except ValueError as e:
                # Invalid input for calculation, silently ignore
                print(f"Debug: Plan summary calculation failed: {e}")
        
        template_combo.bind('<<ComboboxSelected>>', lambda e: calculate_plan_summary())
        
        plan_summary_text = tk.Text(summary_frame, height=8, width=50, font=('Courier', 9))
        plan_summary_text.pack(fill='x', pady=5)
        
        def create_payment_plan():
            try:
                student_id = student_id_var.get().strip()
                selected_template = template_var.get()
                
                if not all([student_id, selected_template]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_template_required"))
                    return

                if selected_template not in self.template_data:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_template"))
                    return
                
                outstanding = float(total_outstanding_var.get())
                if outstanding <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_outstanding_for_plan"))
                    return
                
                # Get template details
                template_info = self.template_data[selected_template]
                template_id, template_name, _, num_installments, frequency, setup_fee, interest_rate = template_info
                
                # Calculate plan details
                principal_amount = outstanding
                interest_amount = principal_amount * (interest_rate / 100)
                total_with_interest = principal_amount + interest_amount + setup_fee
                installment_amount = total_with_interest / num_installments
                
                # Create the payment plan
                conn = get_connection()
                cursor = conn.cursor()
                
                now = datetime.now()
                start_date = now.strftime('%Y-%m-%d')
                
                # Calculate next due date based on frequency
                if frequency == 'weekly':
                    next_due = now + timedelta(weeks=1)
                elif frequency == 'monthly':
                    next_due = now + timedelta(days=30)
                elif frequency == 'quarterly':
                    next_due = now + timedelta(days=90)
                else:
                    next_due = now + timedelta(days=30)
                
                next_due_date = next_due.strftime('%Y-%m-%d')
                
                cursor.execute('''
                INSERT INTO student_payment_plans 
                (student_id, template_id, total_amount, remaining_amount, start_date, 
                 next_due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, template_id, total_with_interest, total_with_interest, 
                      start_date, next_due_date, now.strftime('%Y-%m-%d %H:%M:%S'), 
                      now.strftime('%Y-%m-%d %H:%M:%S')))
                
                payment_plan_id = cursor.lastrowid
                
                # Create installments
                current_due_date = next_due
                for i in range(num_installments):
                    cursor.execute('''
                    INSERT INTO payment_plan_installments 
                    (payment_plan_id, installment_number, amount, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (payment_plan_id, i + 1, installment_amount, current_due_date.strftime('%Y-%m-%d'),
                          now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))
                    
                    # Calculate next due date
                    if frequency == 'weekly':
                        current_due_date += timedelta(weeks=1)
                    elif frequency == 'monthly':
                        current_due_date += timedelta(days=30)
                    elif frequency == 'quarterly':
                        current_due_date += timedelta(days=90)
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.plan_created_success") + "\n" +
                                   _("finance_gui.transaction_manager.plan_id_label") + f" {payment_plan_id}\n" +
                                   _("finance_gui.transaction_manager.template_label") + f" {template_name}\n" +
                                   _("finance_gui.transaction_manager.total_amount_label") + f" £{total_with_interest:.2f}\n" +
                                   _("finance_gui.transaction_manager.first_installment_label", amount=installment_amount, date=next_due_date))
                
                dialog.destroy()
                self.refresh_payment_plans()
                self.update_status(f"Payment plan created for student {student_id}")
                
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_numerical_values"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.create_plan_failed", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_create_payment_plan"), command=create_payment_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
    

    def gui_view_active_payment_plans(self):
        """Refresh and display active payment plans"""
        self.refresh_payment_plans()
        self.show_tab('payment_plans')  # Switch to Payment Plans tab
        messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plans_refreshed"))
    

    def refresh_payment_plans(self):
        """Refresh payment plans display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT spp.payment_plan_id, spp.student_id, s.first_name, s.last_name,
                   spp.total_amount, spp.remaining_amount, spp.status, spp.next_due_date,
                   ppt.template_name, ppt.number_of_installments
            FROM student_payment_plans spp
            JOIN students s ON spp.student_id = s.student_id
            JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
            WHERE spp.status = 'active'
            ORDER BY spp.next_due_date
            ''')
            
            plans = cursor.fetchall()
            
            # Clear existing items
            for item in self.plans_tree.get_children():
                self.plans_tree.delete(item)
            
            # Add plan data
            for plan in plans:
                plan_id, student_id, first_name, last_name, total, remaining, status, next_due, template, installments = plan
                student_name = f"{first_name} {last_name}"
                
                self.plans_tree.insert('', 'end', values=(
                    plan_id, student_name, template, 
                    f"£{total:.2f}", f"£{remaining:.2f}", next_due
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.refresh_plans_failed", error=str(e)))
    
    # Continue with more GUI wrapper functions...
    

    def gui_process_payment_plan_payment(self):
        """GUI for processing payment plan payments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.process_plan_payment_title"))
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_selection_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)
        
        def load_payment_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return
                
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT spp.payment_plan_id, ppt.template_name, spp.remaining_amount,
                       spp.next_due_date, spp.status
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status = 'active'
                ORDER BY spp.next_due_date
                ''', (student_id,))
                
                plans = cursor.fetchall()
                
                # Clear existing items
                for item in plan_tree.get_children():
                    plan_tree.delete(item)
                
                for plan in plans:
                    plan_id, template, remaining, next_due, status = plan
                    plan_tree.insert('', 'end', values=(
                        plan_id, template, f"£{remaining:.2f}", next_due, status
                    ))
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_load_plans"), command=load_payment_plans).pack(anchor='w', pady=5)

        # Payment plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Remaining', 'Next Due', 'Status')
        plan_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            plan_tree.heading(col, text=col)
            plan_tree.column(col, width=120, anchor='center')
        
        plan_tree.pack(fill='both', expand=True)
        
        # Payment details
        payment_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_details_frame"), padding=15)
        payment_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(payment_frame, text=_("finance_gui.transaction_manager.payment_amount_pound_label"), font=('Arial', 12)).pack(anchor='w')
        amount_var = tk.StringVar()
        ttk.Entry(payment_frame, textvariable=amount_var, font=('Arial', 12)).pack(anchor='w', pady=5)

        ttk.Label(payment_frame, text=_("finance_gui.transaction_manager.payment_method_select_label"), font=('Arial', 12)).pack(anchor='w')
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(payment_frame, textvariable=method_var,
                                   values=["Card", "Cash", "Bank Transfer", "Cheque"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(anchor='w', pady=5)
        
        def process_payment():
            selection = plan_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_prompt"))
                return
            
            try:
                plan_id = plan_tree.item(selection[0])['values'][0]
                payment_amount = float(amount_var.get())
                payment_method = method_var.get()
                
                if payment_amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.amount_greater_zero"))
                    return
                
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get plan details
                cursor.execute('''
                SELECT student_id, remaining_amount, template_id
                FROM student_payment_plans
                WHERE payment_plan_id = ?
                ''', (plan_id,))
                
                plan_data = cursor.fetchone()
                if not plan_data:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.plan_not_found"))
                    conn.close()
                    return
                
                student_id, remaining_amount, template_id = plan_data
                
                if payment_amount > remaining_amount:
                    if not messagebox.askyesno(_("finance_gui.transaction_manager.overpayment_title"),
                                              _("finance_gui.transaction_manager.overpayment_confirm", payment=payment_amount, remaining=remaining_amount)):
                        conn.close()
                        return
                
                # Record the payment
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO payments 
                (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                ''', (student_id, payment_amount, payment_method, 
                      datetime.now().strftime('%Y-%m-%d'), 
                      f'Payment plan installment for plan {plan_id}',
                      auth.current_user['username'], now))
                
                payment_id = cursor.lastrowid
                
                # Update payment plan
                new_remaining = max(0, remaining_amount - payment_amount)
                new_status = 'completed' if new_remaining == 0 else 'active'
                
                # Calculate next due date (simplified - monthly)
                if new_remaining > 0:
                    next_due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                else:
                    next_due = None
                
                cursor.execute('''
                UPDATE student_payment_plans 
                SET remaining_amount = ?, status = ?, next_due_date = ?, updated_at = ?
                WHERE payment_plan_id = ?
                ''', (new_remaining, new_status, next_due, now, plan_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.plan_payment_success") + "\n" +
                                   _("finance_gui.transaction_manager.payment_id_label") + f" {payment_id}\n" +
                                   _("finance_gui.transaction_manager.remaining_balance_label", amount=new_remaining))
                
                dialog.destroy()
                self.refresh_payment_plans()
                
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_payment_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.process_payment_failed", error=str(e)))

        ttk.Button(payment_frame, text=_("finance_gui.transaction_manager.btn_process_payment"), command=process_payment).pack(pady=20)
    
    
    

    def gui_modify_payment_plan(self):
        """GUI for modifying payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.modify_plan_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Plan selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.select_plan_frame"), padding=15)
        selection_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(selection_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)
        
        def load_student_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return
                
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT spp.payment_plan_id, spp.total_amount, spp.remaining_amount, 
                       spp.status, ppt.template_name
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status = 'active'
                ''', (student_id,))
                
                plans = cursor.fetchall()
                
                # Clear existing items
                for item in plans_tree.get_children():
                    plans_tree.delete(item)
                
                for plan in plans:
                    plan_id, total, remaining, status, template = plan
                    plans_tree.insert('', 'end', values=(
                        plan_id, template, f"£{total:.2f}", f"£{remaining:.2f}", status
                    ))
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.transaction_manager.btn_load_plans"), command=load_student_plans).pack(anchor='w', pady=5)

        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Status')
        plans_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=6)
        
        for col in columns:
            plans_tree.heading(col, text=col)
            plans_tree.column(col, width=100, anchor='center')
        
        plans_tree.pack(fill='both', expand=True)
        
        # Modification options
        modify_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.modifications_frame"), padding=15)
        modify_frame.pack(fill='x', padx=20, pady=10)

        def suspend_plan():
            selection = plans_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_suspend"))
                return

            plan_id = plans_tree.item(selection[0])['values'][0]
            if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_title"), _("finance_gui.transaction_manager.suspend_confirm", plan_id=plan_id)):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    UPDATE student_payment_plans 
                    SET status = 'suspended', updated_at = ?
                    WHERE payment_plan_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), plan_id))
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plan_suspended_success"))
                    load_student_plans()

                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.suspend_plan_failed", error=str(e)))

        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_suspend_plan"), command=suspend_plan).pack(side='left', padx=10)
        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_cancel_plan_action"),
                  command=lambda: self.cancel_selected_plan(plans_tree)).pack(side='left', padx=10)
        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='right', padx=10)
    

    def cancel_selected_plan(self, tree_widget):
        """Cancel selected payment plan"""
        selection = tree_widget.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_cancel"))
            return

        plan_id = tree_widget.item(selection[0])['values'][0]

        if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_cancel_title"),
                              _("finance_gui.transaction_manager.cancel_confirm", plan_id=plan_id)):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                UPDATE student_payment_plans 
                SET status = 'cancelled', updated_at = ?
                WHERE payment_plan_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), plan_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plan_cancelled_success"))
                self.refresh_payment_plans()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.cancel_plan_failed", error=str(e)))
    

    def gui_cancel_payment_plan(self):
        """GUI for cancelling payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.cancel_plan_dialog_title"))
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.find_plan_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)
        
        def load_cancellable_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return
                
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT spp.payment_plan_id, ppt.template_name, spp.total_amount,
                       spp.remaining_amount, spp.start_date, spp.status
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status IN ('active', 'suspended')
                ORDER BY spp.start_date DESC
                ''', (student_id,))
                
                plans = cursor.fetchall()
                
                # Clear existing items
                for item in cancel_tree.get_children():
                    cancel_tree.delete(item)
                
                for plan in plans:
                    plan_id, template, total, remaining, start_date, status = plan
                    cancel_tree.insert('', 'end', values=(
                        plan_id, template, f"£{total:.2f}", 
                        f"£{remaining:.2f}", start_date, status
                    ))
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_find_plans"), command=load_cancellable_plans).pack(anchor='w', pady=5)

        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Start Date', 'Status')
        cancel_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            cancel_tree.heading(col, text=col)
            cancel_tree.column(col, width=100, anchor='center')
        
        cancel_tree.pack(fill='both', expand=True)
        
        # Cancellation reason
        reason_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.cancellation_details_frame"), padding=15)
        reason_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(reason_frame, text=_("finance_gui.transaction_manager.cancellation_reason_label"), font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(reason_frame, height=3, width=50, font=('Arial', 10))
        reason_text.pack(fill='x', pady=5)
        
        def cancel_plan():
            selection = cancel_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_cancel"))
                return

            reason = reason_text.get("1.0", tk.END).strip()
            if not reason:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.reason_required"))
                return

            plan_data = cancel_tree.item(selection[0])['values']
            plan_id = plan_data[0]
            remaining_amount = float(plan_data[3].replace('£', ''))

            if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_cancel_title"),
                                  _("finance_gui.transaction_manager.cancel_confirm_detailed", plan_id=plan_id, remaining=remaining_amount)):
                try:
                    self.cancel_selected_plan(cancel_tree)
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.cancel_plan_failed", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel_plan_action"), command=cancel_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=10)
    
    # Additional GUI functions for other features

    def gui_view_student_financial_statement(self):
        """GUI wrapper for viewing student financial statement"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.financial_statement_title"))
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        input_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_selection_frame"), padding=15)
        input_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(input_frame, textvariable=student_id_var, font=('Arial', 12), width=15)
        student_entry.pack(side='left', padx=5)
        
        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_generate_statement"),
                  command=lambda: self.generate_financial_statement(student_id_var.get(), statement_text)).pack(side='left', padx=10)

        # Statement display
        statement_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.financial_statement_frame"), padding=15)
        statement_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        statement_text = ScrolledText(statement_frame, height=25, width=100, font=('Courier', 10))
        statement_text.pack(fill='both', expand=True)
        
        # Export buttons
        export_frame = ttk.Frame(dialog)
        export_frame.pack(pady=10)
        
        def export_statement():
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_statement_to_export"))
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"financial_statement_{student_id_var.get()}_{datetime.now().strftime('%Y%m%d')}.txt"
            )
            
            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(statement_text.get("1.0", tk.END))
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.statement_exported", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_statement_failed", error=str(e)))
        
        def print_statement():
            """Print the financial statement"""
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_statement_to_print"))
                return
    
            try:
                import tempfile
                import platform
    
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                    temp_file.write(statement_text.get("1.0", tk.END))
                    temp_path = temp_file.name
    
                # Print based on OS
                if platform.system() == 'Windows':
                    os.startfile(temp_path, "print")
                elif platform.system() == 'Darwin':  # macOS
                    os.system(f'lpr "{temp_path}"')
                else:  # Linux
                    os.system(f'lpr "{temp_path}"')
    
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.statement_sent_to_printer"))

            except Exception as e:
                # Fallback: offer to save as PDF
                if messagebox.askyesno(_("finance_gui.transaction_manager.print_failed_title"),
                                      _("finance_gui.transaction_manager.print_failed_save_pdf", error=str(e))):
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".pdf",
                        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                        initialfile=f"financial_statement_{student_id_var.get()}.pdf"
                    )
                    if filename:
                        try:
                            # Simple text to PDF (fallback to text file if no PDF library)
                            filename = filename.replace('.pdf', '.txt')
                            with open(filename, 'w') as f:
                                f.write(statement_text.get("1.0", tk.END))
                            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.saved_as_text", filename=filename))
                        except Exception as save_error:
                            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.save_failed", error=str(save_error)))
    
        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_export_statement"), command=export_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_print_statement"), command=print_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=10)
    

    def generate_financial_statement(self, student_id, text_widget):
        """Generate and display financial statement"""
        if not student_id:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student details
            cursor.execute('''
            SELECT first_name, last_name, email_address, course, enrollment_date, status
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            if not student:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found_statement"))
                return
            
            first_name, last_name, email, course, enrollment_date, status = student
            
            # Build statement content
            statement = f"""
    {'=' * 80}
    FINANCIAL STATEMENT
    {'=' * 80}
    Student: {first_name} {last_name}
    Student ID: {student_id}
    Course: {course}
    Enrollment Date: {enrollment_date}
    Status: {status}
    Statement Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    {'=' * 80}
    
    """
            
            # Get all fees
            cursor.execute('''
            SELECT ft.fee_name, sf.amount, sf.due_date, sf.status, sf.created_at
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE sf.student_id = ?
            ORDER BY sf.created_at
            ''', (student_id,))
            
            fees = cursor.fetchall()
            
            statement += "FEES CHARGED:\n"
            statement += "-" * 80 + "\n"
            total_fees = 0
            for fee_name, amount, due_date, fee_status, created_at in fees:
                status_indicator = "✓" if fee_status == 'paid' else "○" if fee_status == 'partial' else "×"
                statement += f"{status_indicator} {fee_name:<30} £{amount:>10.2f}  Due: {due_date}\n"
                total_fees += amount
            
            statement += "-" * 80 + "\n"
            statement += f"Total Fees Charged: £{total_fees:>10.2f}\n\n"
            
            # Get all payments
            cursor.execute('''
            SELECT amount, payment_method, payment_date, transaction_id
            FROM payments
            WHERE student_id = ? AND status = 'completed'
            ORDER BY payment_date
            ''', (student_id,))
            
            payments = cursor.fetchall()
            
            statement += "PAYMENTS RECEIVED:\n"
            statement += "-" * 80 + "\n"
            total_payments = 0
            for amount, method, date, trans_id in payments:
                trans_display = trans_id if trans_id else "N/A"
                statement += f"{date} {method:<15} £{amount:>10.2f}  Ref: {trans_display}\n"
                total_payments += amount
            
            statement += "-" * 80 + "\n"
            statement += f"Total Payments: £{total_payments:>10.2f}\n\n"
            
            # Get credits
            cursor.execute('''
            SELECT credit_amount, remaining_amount, credit_source, created_at, status
            FROM student_credits
            WHERE student_id = ?
            ORDER BY created_at
            ''', (student_id,))
            
            credits = cursor.fetchall()
            
            if credits:
                statement += "CREDITS:\n"
                statement += "-" * 80 + "\n"
                total_credits = 0
                active_credits = 0
                for credit_amount, remaining, source, created_at, credit_status in credits:
                    status_display = credit_status.upper()
                    statement += f"{created_at} {source:<15} £{credit_amount:>10.2f}  Remaining: £{remaining:.2f} ({status_display})\n"
                    total_credits += credit_amount
                    if credit_status == 'active':
                        active_credits += remaining
                
                statement += "-" * 80 + "\n"
                statement += f"Total Credits Issued: £{total_credits:>10.2f}\n"
                statement += f"Active Credits Available: £{active_credits:>10.2f}\n\n"
            
            # Calculate balance
            balance = total_fees - total_payments
            
            statement += "=" * 80 + "\n"
            statement += "ACCOUNT SUMMARY:\n"
            statement += f"Total Fees: £{total_fees:>10.2f}\n"
            statement += f"Total Payments: £{total_payments:>10.2f}\n"
            if credits:
                active_credits = sum(c[1] for c in credits if c[4] == 'active')
                statement += f"Available Credits: £{active_credits:>10.2f}\n"
            statement += "-" * 30 + "\n"
            if balance > 0:
                statement += f"BALANCE DUE: £{balance:>10.2f}\n"
            elif balance < 0:
                statement += f"CREDIT BALANCE: £{abs(balance):>10.2f}\n"
            else:
                statement += f"ACCOUNT BALANCE: £0.00\n"
            statement += "=" * 80 + "\n"
            
            # Display in text widget
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', statement)
            
            conn.close()
            self.update_status(f"Financial statement generated for {student_id}")
            
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.generate_statement_failed", error=str(e)))

    # Helper methods
    def update_status(self, message):
        """Update status bar message"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(message)
            elif hasattr(self.gui, 'update_status'):
                self.gui.update_status(message)
            else:
                print(f"Status: {message}")
        except Exception as e:
            print(f"Status update failed: {message} (Error: {e})")

    def refresh_dashboard(self):
        """Refresh the dashboard if it exists"""
        try:
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'refresh_dashboard'):
                self.gui.dashboard.refresh_dashboard()
            elif hasattr(self.gui, 'refresh_dashboard'):
                self.gui.refresh_dashboard()
            else:
                # Dashboard not available, skip silently
                pass
        except Exception as e:
            print(f"Dashboard refresh failed: {e}")

    # Payment Plans GUI Functions
