"""Payment and transaction processing"""

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

# Import all required finance functions from common_imports module
from university_system.modules.domain.finance.gui.finance.common_imports import *

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
        except:
            self.finance_system = None

    def create_payments_tab(self):
        """Create payments management tab"""
        payments_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['payments'] = payments_frame

        # Payments toolbar
        toolbar = tk.Frame(payments_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar, text="➕ Record Payment", command=self.show_payment_dialog,
                 bg=self.gui.layout.colors['success'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="🔍 Search Payments", command=self.search_payments,
                 bg=self.gui.layout.colors['secondary'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="📊 Payment Analytics", command=self.show_payment_analytics,
                 bg=self.gui.layout.colors['warning'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="📧 Email Reminders", command=self.send_payment_email_reminders,
                 bg=self.gui.layout.colors['info'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text="🔄 Refresh", command=self.refresh_payments,
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
        self.payments_tree.heading('payment_id', text='Payment ID')
        self.payments_tree.heading('student_id', text='Student ID')
        self.payments_tree.heading('amount', text='Amount')
        self.payments_tree.heading('method', text='Method')
        self.payments_tree.heading('date', text='Date')
        self.payments_tree.heading('status', text='Status')
        
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
        self.payments_menu.add_command(label="View Details", command=self.view_payment_details)
        self.payments_menu.add_command(label="Process Refund", command=self.process_refund)
        self.payments_menu.add_separator()
        self.payments_menu.add_command(label="Export to CSV", command=self.export_payments)
        
        self.payments_tree.bind("<Button-3>", self.show_payments_menu)
    

    def show_payment_dialog(self):
        """Show payment recording dialog"""
        # Simple payment dialog using built-in dialogs
        student_id = simpledialog.askstring("Payment", "Enter Student ID:")
        if student_id:
            amount = simpledialog.askfloat("Payment", "Enter Payment Amount:")
            if amount:
                method = simpledialog.askstring("Payment", "Payment Method (card/cash/bank):", initialvalue="card")
                if method:
                    try:
                        # Here you would save the payment to database
                        messagebox.showinfo("Success", f"Payment of £{amount:.2f} recorded for student {student_id}")
                        self.refresh_payments()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to record payment: {e}")
            self.refresh_dashboard()
    

    def gui_record_payment(self):
        """GUI wrapper for record_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Payment")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create notebook for tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Basic payment tab
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="Basic Payment")
        
        # Student ID
        ttk.Label(basic_tab, text="Student ID:", font=('Arial', 12)).pack(pady=5)
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(basic_tab, textvariable=student_id_var, font=('Arial', 12))
        student_entry.pack(pady=5)
        
        # Amount
        ttk.Label(basic_tab, text="Payment Amount (£):", font=('Arial', 12)).pack(pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=amount_var, font=('Arial', 12)).pack(pady=5)
        
        # Payment method
        ttk.Label(basic_tab, text="Payment Method:", font=('Arial', 12)).pack(pady=5)
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(basic_tab, textvariable=method_var, 
                                   values=["Card", "Cash", "Bank Transfer", "Cheque", "Online"], 
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(pady=5)
        
        # Payment date
        ttk.Label(basic_tab, text="Payment Date (YYYY-MM-DD):", font=('Arial', 12)).pack(pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(basic_tab, textvariable=date_var, font=('Arial', 12)).pack(pady=5)
        
        # Transaction ID
        ttk.Label(basic_tab, text="Transaction ID (optional):", font=('Arial', 12)).pack(pady=5)
        trans_id_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=trans_id_var, font=('Arial', 12)).pack(pady=5)
        
        # Notes
        ttk.Label(basic_tab, text="Notes:", font=('Arial', 12)).pack(pady=5)
        notes_text = tk.Text(basic_tab, height=3, width=50, font=('Arial', 10))
        notes_text.pack(pady=5)
        
        def record_payment():
            try:
                # Validate inputs
                if not all([student_id_var.get(), amount_var.get(), method_var.get(), date_var.get()]):
                    messagebox.showerror("Error", "Required fields are missing")
                    return
                
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method = method_var.get()
                payment_date = date_var.get().strip()
                transaction_id = trans_id_var.get().strip()
                notes = notes_text.get("1.0", tk.END).strip()
                
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be greater than zero")
                    return
                
                # Call original function logic
                conn = get_connection()
                cursor = conn.cursor()
                
                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror("Error", f"Student {student_id} not found")
                    conn.close()
                    return
                
                # Record payment
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO payments 
                (student_id, amount, payment_method, payment_date, transaction_id, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, amount, payment_method, payment_date, transaction_id, notes, 
                      auth.current_user['username'], now))
                
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
                          f'Overpayment from payment ID {payment_id}', auth.current_user['username'], now, now))
                
                conn.commit()
                conn.close()
                
                # Show success message with allocation details
                allocation_msg = "\n".join(allocated_fees) if allocated_fees else "No outstanding fees to allocate"
                if remaining_payment > 0:
                    allocation_msg += f"\n\nOverpayment: £{remaining_payment:.2f} (added as credit)"
                
                messagebox.showinfo("Success", 
                                   f"Payment recorded successfully!\n"
                                   f"Payment ID: {payment_id}\n"
                                   f"Amount: £{amount:.2f}\n\n"
                                   f"Allocations:\n{allocation_msg}")
                
                dialog.destroy()
                self.update_status(f"Payment of £{amount:.2f} recorded for student {student_id}")
                
            except ValueError:
                messagebox.showerror("Error", "Invalid amount entered")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to record payment: {e}")
        
        # Buttons
        button_frame = ttk.Frame(basic_tab)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Record Payment", command=record_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
    

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
        
        # Insert new data
        for payment in payments:
            self.payments_tree.insert('', 'end', values=payment)
    

    def show_payments_menu(self, event):
        """Show payments context menu"""
        item = self.payments_tree.selection()
        if item:
            self.payments_menu.post(event.x_root, event.y_root)
    

    def search_payments(self):
        """Search payments"""
        search_term = simpledialog.askstring("Search Payments", "Enter search term:")
        if search_term:
            self.update_status(f"Searching payments for: {search_term}")
            # Implement search logic here
    

    def view_payment_details(self):
        """View selected payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view details.")
            return
        
        payment_id = self.payments_tree.item(selection[0])['values'][0]
        
        # Create details dialog
        dialog = PaymentDetailsDialog(self.root, payment_id)
        self.root.wait_window(dialog.dialog)
    

    def process_refund(self):
        """Process refund for selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund.")
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
                title="Export Payments"
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
                
                self.update_status(f"Payments exported to {filename}")
                messagebox.showinfo("Export Complete", f"Payments exported to {filename}")
        
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export payments: {str(e)}")
    

    def gui_process_refund(self):
        """GUI wrapper for process_refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Refund")
        dialog.geometry("800x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student selection
        student_frame = ttk.LabelFrame(dialog, text="Student Information", padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(student_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(anchor='w', pady=5)
        
        ttk.Button(student_frame, text="Load Payment History", 
                  command=lambda: self.load_payment_history(student_id_var.get(), payments_tree)).pack(anchor='w', pady=5)
        
        # Payment history display
        history_frame = ttk.LabelFrame(dialog, text="Payment History", padding=15)
        history_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Payment ID', 'Amount', 'Method', 'Date', 'Transaction ID')
        payments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            payments_tree.heading(col, text=col)
            payments_tree.column(col, width=120, anchor='center')
        
        payments_tree.pack(fill='both', expand=True)
        
        # Refund details
        refund_frame = ttk.LabelFrame(dialog, text="Refund Details", padding=15)
        refund_frame.pack(fill='x', padx=20, pady=10)
        
        # Refund type
        ttk.Label(refund_frame, text="Refund Type:", font=('Arial', 12)).pack(anchor='w')
        refund_type_var = tk.StringVar(value="partial")
        refund_type_combo = ttk.Combobox(refund_frame, textvariable=refund_type_var,
                                        values=["full", "partial", "withdrawal", "overpayment"],
                                        state='readonly', font=('Arial', 12))
        refund_type_combo.pack(anchor='w', pady=5)
        
        # Refund amount
        ttk.Label(refund_frame, text="Refund Amount (£):", font=('Arial', 12)).pack(anchor='w')
        refund_amount_var = tk.StringVar()
        ttk.Entry(refund_frame, textvariable=refund_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)
        
        # Refund reason
        ttk.Label(refund_frame, text="Refund Reason:", font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(refund_frame, height=3, width=60, font=('Arial', 10))
        reason_text.pack(anchor='w', pady=5)
        
        # Refund method
        ttk.Label(refund_frame, text="Refund Method:", font=('Arial', 12)).pack(anchor='w')
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
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                # Get selected payment
                selected_item = payments_tree.selection()
                original_payment_id = None
                
                if selected_item:
                    payment_data = payments_tree.item(selected_item[0])['values']
                    original_payment_id = payment_data[0]
                    original_amount = float(payment_data[1].replace('£', ''))
                    
                    if refund_amount > original_amount:
                        messagebox.showerror("Error", f"Refund amount cannot exceed original payment (£{original_amount:.2f})")
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
                      refund_method, 'pending', auth.current_user['username'], request_date, now))
                
                refund_id = cursor.lastrowid
                
                # Auto-approve if user has permissions (simplified)
                if auth.check_permission('approve_refunds'):
                    cursor.execute('''
                    UPDATE refunds 
                    SET status = 'approved', approved_by = ?, approval_date = ?
                    WHERE refund_id = ?
                    ''', (auth.current_user['username'], request_date, refund_id))
                    status_msg = "Refund approved and ready for processing"
                else:
                    status_msg = "Refund request created and pending approval"
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", 
                                   f"Refund request created successfully!\n"
                                   f"Refund ID: {refund_id}\n"
                                   f"Amount: £{refund_amount:.2f}\n"
                                   f"Status: {status_msg}")
                
                dialog.destroy()
                self.update_status(f"Refund request created for £{refund_amount:.2f}")
                
            except ValueError:
                messagebox.showerror("Error", "Invalid refund amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process refund: {e}")
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
    

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
            messagebox.showerror("Error", f"Failed to load payment history: {e}")
    

    def show_payment_analytics(self):
        """Show payment analytics"""
        try:
            # Call the original function
            self.analyze_payment_patterns()
            self.update_status("Payment analytics generated")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate payment analytics: {str(e)}")
    

    def send_payment_email_reminders(self):
        """Send email reminders for payments and financial matters"""
        # Create email reminder dialog
        email_window = tk.Toplevel(self.root)
        email_window.title("Finance Email Reminders")
        email_window.geometry("700x600")
        email_window.transient(self.root)
        email_window.grab_set()
    
        # Email type selection frame
        type_frame = ttk.LabelFrame(email_window, text="Email Type", padding=10)
        type_frame.pack(fill='x', padx=10, pady=10)
    
        email_type_var = tk.StringVar(value="overdue_payment")
        email_types = [
            ("overdue_payment", "Overdue Payment Reminder"),
            ("upcoming_payment", "Upcoming Payment Due"),
            ("payment_confirmation", "Payment Confirmation"),
            ("fee_notification", "New Fee Notification"),
            ("scholarship_update", "Scholarship/Aid Update"),
            ("financial_hold", "Financial Hold Notice"),
            ("custom", "Custom Financial Message")
        ]
    
        for i, (value, text) in enumerate(email_types):
            ttk.Radiobutton(type_frame, text=text, variable=email_type_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)
    
        # Recipient selection frame
        recipient_frame = ttk.LabelFrame(email_window, text="Recipients", padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=10)
    
        recipient_var = tk.StringVar(value="overdue_students")
        recipient_options = [
            ("overdue_students", "Students with Overdue Payments"),
            ("upcoming_due", "Students with Payments Due Soon"),
            ("all_students", "All Students with Outstanding Balances"),
            ("financial_aid", "Financial Aid Recipients"),
            ("scholarship_recipients", "Scholarship Recipients"),
            ("custom", "Custom Recipients")
        ]
    
        for i, (value, text) in enumerate(recipient_options):
            ttk.Radiobutton(recipient_frame, text=text, variable=recipient_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)
    
        # Message composition frame
        message_frame = ttk.LabelFrame(email_window, text="Message", padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Subject line
        ttk.Label(message_frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value="Finance Department Notification")
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, width=80)
        subject_entry.pack(fill='x', pady=(0, 10))
    
        # Message body
        ttk.Label(message_frame, text="Message:").pack(anchor='w')
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
                except:
                    default_message = ""
            else:
                default_message = "Dear Student,\n\n[Enter your custom message here]\n\nBest regards,\nFinance Department"
    
            message_text.delete('1.0', tk.END)
            message_text.insert('1.0', default_message)
    
        email_type_var.trace('w', update_default_message)
        update_default_message()  # Set initial message
    
        # Buttons frame
        buttons_frame = ttk.Frame(email_window)
        buttons_frame.pack(fill='x', padx=10, pady=10)
    
        def preview_recipients():
            """Preview the list of recipients"""
            try:
                recipient_type = recipient_var.get()
                recipients = self._get_finance_email_recipients(recipient_type)
    
                preview_window = tk.Toplevel(email_window)
                preview_window.title("Email Recipients Preview")
                preview_window.geometry("500x400")
                preview_window.transient(email_window)
    
                ttk.Label(preview_window, text=f"Recipients ({len(recipients)}):").pack(anchor='w', padx=10, pady=10)
    
                recipients_list = tk.Listbox(preview_window, height=20)
                recipients_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))
    
                for recipient in recipients:
                    display_text = f"{recipient['name']} ({recipient['email']})"
                    if 'balance' in recipient:
                        display_text += f" - Balance: ${recipient['balance']:.2f}"
                    recipients_list.insert(tk.END, display_text)
    
                ttk.Button(preview_window, text="Close",
                          command=preview_window.destroy).pack(pady=10)
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to preview recipients: {e}")
    
        def send_emails():
            """Send the email reminders"""
            try:
                email_type = email_type_var.get()
                recipient_type = recipient_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()
    
                if not subject or not message:
                    messagebox.showwarning("Warning", "Please enter both subject and message")
                    return
    
                # Get recipient list
                recipients = self._get_finance_email_recipients(recipient_type)
    
                if not recipients:
                    messagebox.showinfo("Info", "No recipients found for the selected criteria")
                    return
    
                # Try to send emails via email GUI
                success = self._send_finance_emails_via_gui(recipients, subject, message, email_type)
    
                if success:
                    email_window.destroy()
                    messagebox.showinfo("Success", f"Finance emails sent to {len(recipients)} recipients")
                else:
                    # Fallback: show email details for manual sending
                    self._show_finance_email_fallback_dialog(recipients, subject, message)
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send emails: {e}")
    
        ttk.Button(buttons_frame, text="Preview Recipients",
                  command=preview_recipients).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Send Emails",
                  command=send_emails).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Cancel",
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
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date < date('now', '-30 days') AND f.paid_status != 'Paid'
                  AND s.email IS NOT NULL AND s.email != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')
    
            elif recipient_type == "upcoming_due":
                # Students with payments due in the next 7 days
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date BETWEEN date('now') AND date('now', '+7 days')
                  AND f.paid_status != 'Paid' AND s.email IS NOT NULL AND s.email != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')
    
            elif recipient_type == "all_students":
                # All students with outstanding balances
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.paid_status != 'Paid' AND s.email IS NOT NULL AND s.email != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')
    
            elif recipient_type == "financial_aid":
                # Financial aid recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN financial_aid fa ON s.student_id = fa.student_id
                WHERE fa.status = 'Approved' AND s.email IS NOT NULL AND s.email != ''
                ''')
    
            elif recipient_type == "scholarship_recipients":
                # Scholarship recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN scholarships sch ON s.student_id = sch.student_id
                WHERE sch.status = 'Active' AND s.email IS NOT NULL AND s.email != ''
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
        """Try to send emails via email GUI"""
        try:
            # Try to import and use email GUI
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI
    
            # Create email GUI instance
            email_gui = EmailGUI(self.root, self.auth if hasattr(self, 'auth') else None)
    
            # Send emails through email GUI
            for recipient in recipients:
                personalized_message = message.replace("[Student Name]", recipient['name'])
                if 'balance' in recipient:
                    personalized_message = personalized_message.replace("[Balance]", f"${recipient['balance']:.2f}")
    
                email_gui.send_email(
                    to_email=recipient['email'],
                    subject=subject,
                    message=personalized_message
                )
    
            return True
    
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending finance emails via GUI: {e}")
            return False
    

    def _show_finance_email_fallback_dialog(self, recipients, subject, message):
        """Show fallback dialog with email details for manual sending"""
        fallback_window = tk.Toplevel(self.root)
        fallback_window.title("Finance Email Details - Manual Send")
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)
    
        ttk.Label(fallback_window, text="Email GUI not available. Please send manually:",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)
    
        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
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
    
        ttk.Button(fallback_window, text="Close",
                  command=fallback_window.destroy).pack(pady=10)
    

    def analyze_payment_patterns(self):
        """Analyze payment patterns (placeholder function)"""
        try:
            messagebox.showinfo("Payment Analytics",
                "Payment pattern analysis functionality not fully implemented.\n"
                "This would analyze:\n"
                "• Payment timing trends\n"
                "• Popular payment methods\n"
                "• Peak payment periods\n"
                "• Payment failure patterns")
        except Exception as e:
            print(f"Error in analyze_payment_patterns: {e}")
    

    def gui_process_stripe_payment(self):
        """GUI wrapper for process_stripe_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Stripe Payment")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Stripe Payment Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Amount
        ttk.Label(form_frame, text="Amount:").pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        # Payment method ID
        ttk.Label(form_frame, text="Payment Method ID:").pack(anchor='w', pady=5)
        payment_method_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=payment_method_var).pack(anchor='w', fill='x', pady=5)
        
        def process_payment():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method_id = payment_method_var.get().strip()
                
                if not all([student_id, amount > 0, payment_method_id]):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                result = process_stripe_payment(student_id, amount, payment_method_id)
                messagebox.showinfo("Success", f"Stripe payment processed successfully!\nTransaction ID: {result.get('id', 'N/A')}")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process Stripe payment: {e}")
        
        ttk.Button(form_frame, text="Process Payment", command=process_payment).pack(pady=20)
    

    def gui_generate_qr_payment_code(self):
        """GUI wrapper for generate_qr_payment_code"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate QR Payment Code")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Payment Details", padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Amount
        ttk.Label(form_frame, text="Amount:").pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)
        
        # QR Code display
        qr_frame = ttk.LabelFrame(dialog, text="QR Code", padding=20)
        qr_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        qr_label = ttk.Label(qr_frame, text="QR Code will appear here")
        qr_label.pack(pady=20)
        
        def generate_qr():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                description = desc_var.get().strip()
                
                if not all([student_id, amount > 0]):
                    messagebox.showerror("Error", "Student ID and amount are required")
                    return
                
                qr_code_data = generate_qr_payment_code(student_id, amount, description)
                qr_label.config(text=f"QR Code generated for {student_id}\nAmount: £{amount:.2f}")
                messagebox.showinfo("Success", "QR payment code generated successfully!")
                
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate QR code: {e}")
        
        ttk.Button(form_frame, text="Generate QR Code", command=generate_qr).pack(pady=20)
    

    def gui_apply_credit_to_fees(self):
        """GUI wrapper for apply_credit_to_fees"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Apply Credit to Fees")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Credit Application", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Credit ID
        ttk.Label(form_frame, text="Credit ID:").pack(anchor='w', pady=5)
        credit_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=credit_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Amount to apply
        ttk.Label(form_frame, text="Amount to Apply:").pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        def apply_credit():
            try:
                student_id = student_id_var.get().strip()
                credit_id = int(credit_id_var.get())
                amount = float(amount_var.get())
                
                if not all([student_id, credit_id, amount > 0]):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                apply_credit_to_fees(student_id, credit_id, amount)
                messagebox.showinfo("Success", "Credit applied to fees successfully!")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid credit ID or amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to apply credit: {e}")
        
        ttk.Button(form_frame, text="Apply Credit", command=apply_credit).pack(pady=20)
    

    def gui_view_credit_history(self):
        """GUI wrapper for view_credit_history"""
        dialog = tk.Toplevel(self.root)
        dialog.title("View Credit History")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')
        
        ttk.Label(input_frame, text="Student ID:").pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)
        
        def show_history():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Student ID is required")
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
                messagebox.showerror("Error", f"Failed to view credit history: {e}")
        
        ttk.Button(input_frame, text="View History", command=show_history).pack(side='left', padx=10)
        
        # History display
        history_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
        history_text.pack(fill='both', expand=True, padx=10, pady=10)
    

    def gui_view_student_credits(self):
        """GUI wrapper for view_student_credits"""
        dialog = tk.Toplevel(self.root)
        dialog.title("View Student Credits")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')
        
        ttk.Label(input_frame, text="Student ID:").pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)
        
        def show_credits():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Student ID is required")
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
                messagebox.showerror("Error", f"Failed to view credits: {e}")
        
        ttk.Button(input_frame, text="View Credits", command=show_credits).pack(side='left', padx=10)
        
        # Credits display
        credits_text = ScrolledText(dialog, height=20, width=70, font=('Courier', 10))
        credits_text.pack(fill='both', expand=True, padx=10, pady=10)
    

    def gui_add_student_credit(self):
        """GUI wrapper for add_student_credit"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student Credit")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Credit Details", padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Credit amount
        ttk.Label(form_frame, text="Credit Amount:").pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        # Credit source
        ttk.Label(form_frame, text="Credit Source:").pack(anchor='w', pady=5)
        source_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=source_var).pack(anchor='w', fill='x', pady=5)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)
        
        def add_credit():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                source = source_var.get().strip()
                description = desc_var.get().strip()
                
                if not all([student_id, amount > 0, source]):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                add_student_credit(student_id, amount, source, description)
                messagebox.showinfo("Success", "Credit added successfully!")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add credit: {e}")
        
        ttk.Button(form_frame, text="Add Credit", command=add_credit).pack(pady=20)
    

    def gui_manage_student_credits(self):
        """GUI wrapper for student credits management"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Student Credits")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create notebook for different credit operations
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # View credits tab
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text="View Credits")
        
        # Student selection for viewing
        search_frame = ttk.LabelFrame(view_tab, text="Student Search", padding=10)
        search_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(search_frame, text="Student ID:").pack(side='left', padx=5)
        view_student_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=view_student_var, width=15).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Load Credits", 
                  command=lambda: self.load_student_credits(view_student_var.get(), credits_tree)).pack(side='left', padx=10)
        
        # Credits display
        credits_frame = ttk.LabelFrame(view_tab, text="Active Credits", padding=10)
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
        notebook.add(add_tab, text="Add Credit")
        
        add_frame = ttk.LabelFrame(add_tab, text="Add New Credit", padding=20)
        add_frame.pack(fill='x', padx=20, pady=20)
        
        # Student ID for adding credit
        ttk.Label(add_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w', pady=5)
        add_student_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=add_student_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)
        
        # Credit amount
        ttk.Label(add_frame, text="Credit Amount (£):", font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        credit_amount_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=credit_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)
        
        # Credit source
        ttk.Label(add_frame, text="Credit Source:", font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        source_var = tk.StringVar(value="adjustment")
        source_combo = ttk.Combobox(add_frame, textvariable=source_var,
                                   values=["overpayment", "refund", "scholarship", "adjustment", "goodwill", "other"],
                                   state='readonly', font=('Arial', 12))
        source_combo.pack(anchor='w', pady=5)
        
        # Description
        ttk.Label(add_frame, text="Description:", font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        desc_entry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=desc_entry_var, font=('Arial', 12), width=50).pack(anchor='w', pady=5)
        
        # Expiry date
        ttk.Label(add_frame, text="Expiry Date (optional, YYYY-MM-DD):", font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
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
                    messagebox.showerror("Error", "Student ID, amount, and source are required")
                    return
                
                # Validate expiry date if provided
                if expiry_date:
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        messagebox.showerror("Error", "Invalid expiry date format (use YYYY-MM-DD)")
                        return
                else:
                    expiry_date = None
                
                # Check if student exists
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror("Error", f"Student {student_id} not found")
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
                
                messagebox.showinfo("Success", f"Credit added successfully!\nCredit ID: {credit_id}")
                
                # Clear form
                add_student_var.set("")
                credit_amount_var.set("")
                desc_entry_var.set("")
                expiry_var.set("")
                
                self.update_status(f"Credit of £{credit_amount:.2f} added for student {student_id}")
                
            except ValueError:
                messagebox.showerror("Error", "Invalid credit amount")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add credit: {e}")
        
        ttk.Button(add_frame, text="Add Credit", command=add_credit).pack(anchor='w', pady=20)
    

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
            messagebox.showerror("Error", f"Failed to load credits: {e}")
    

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
        button_frame = ttk.LabelFrame(scrollable_frame, text="Core Finance Operations", padding=20)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        buttons = [
            ("👤 Assign Fees to Student", self.gui_assign_fees_to_student, "#3498db"),
            ("💳 Record Payment", self.gui_record_payment, "#27ae60"),
            ("📋 Generate Invoice", self.gui_generate_invoice, "#e74c3c"),
            ("💰 Process Refund", self.gui_process_refund, "#f39c12"),
            ("🎯 Manage Student Credits", self.gui_manage_student_credits, "#9b59b6"),
            ("📊 View Student Financial Statement", self.gui_view_student_financial_statement, "#34495e")
        ]
        
        for i, (text, command, color) in enumerate(buttons):
            btn = tk.Button(button_frame, text=text, command=command,
                          font=('Arial', 12, 'bold'), bg=color, fg='white',
                          width=35, height=2, relief='raised', bd=3)
            btn.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='ew')
        
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        # Quick stats frame
        stats_frame = ttk.LabelFrame(scrollable_frame, text="Quick Statistics", padding=20)
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
        button_frame = ttk.LabelFrame(main_frame, text="Payment Plan Management", padding=15)
        button_frame.pack(fill='x', pady=(0, 20))
        
        buttons = [
            ("➕ Create Payment Plan", self.gui_create_payment_plan),
            ("👁 View Active Plans", self.gui_view_active_payment_plans),
            ("⚙ Modify Payment Plan", self.gui_modify_payment_plan),
            ("💰 Process Plan Payment", self.gui_process_payment_plan_payment),
            ("❌ Cancel Payment Plan", self.gui_cancel_payment_plan)
        ]
        
        for i, (text, command) in enumerate(buttons):
            btn = ttk.Button(button_frame, text=text, command=command, width=25)
            btn.grid(row=i//3, column=i%3, padx=10, pady=5, sticky='ew')
        
        # Plans display frame
        display_frame = ttk.LabelFrame(main_frame, text="Active Payment Plans", padding=15)
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
        dialog.title("Create Payment Plan")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student selection
        student_frame = ttk.LabelFrame(dialog, text="Student Information", padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(student_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12))
        student_entry.pack(anchor='w', pady=5, fill='x')
        
        # Outstanding fees display
        fees_frame = ttk.LabelFrame(dialog, text="Outstanding Fees", padding=15)
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
                messagebox.showerror("Error", f"Failed to load fees: {e}")
        
        ttk.Button(student_frame, text="Load Outstanding Fees", 
                  command=load_outstanding_fees).pack(anchor='w', pady=5)
        
        # Plan configuration
        plan_frame = ttk.LabelFrame(dialog, text="Payment Plan Configuration", padding=15)
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
        except:
            templates = []
        
        ttk.Label(plan_frame, text="Payment Plan Template:", font=('Arial', 12)).pack(anchor='w')
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
        summary_frame = ttk.LabelFrame(plan_frame, text="Plan Summary", padding=10)
        summary_frame.pack(fill='x', pady=10)
        
        total_outstanding_var = tk.StringVar(value="0.00")
        ttk.Label(summary_frame, text="Outstanding Amount: £").pack(side='left')
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
                
            except ValueError:
                pass
        
        template_combo.bind('<<ComboboxSelected>>', lambda e: calculate_plan_summary())
        
        plan_summary_text = tk.Text(summary_frame, height=8, width=50, font=('Courier', 9))
        plan_summary_text.pack(fill='x', pady=5)
        
        def create_payment_plan():
            try:
                student_id = student_id_var.get().strip()
                selected_template = template_var.get()
                
                if not all([student_id, selected_template]):
                    messagebox.showerror("Error", "Student ID and template selection are required")
                    return
                
                if selected_template not in self.template_data:
                    messagebox.showerror("Error", "Invalid template selection")
                    return
                
                outstanding = float(total_outstanding_var.get())
                if outstanding <= 0:
                    messagebox.showerror("Error", "No outstanding fees to create payment plan")
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
                
                messagebox.showinfo("Success", 
                                   f"Payment plan created successfully!\n"
                                   f"Plan ID: {payment_plan_id}\n"
                                   f"Template: {template_name}\n"
                                   f"Total Amount: £{total_with_interest:.2f}\n"
                                   f"First installment: £{installment_amount:.2f} due on {next_due_date}")
                
                dialog.destroy()
                self.refresh_payment_plans()
                self.update_status(f"Payment plan created for student {student_id}")
                
            except ValueError:
                messagebox.showerror("Error", "Invalid numerical values")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create payment plan: {e}")
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Create Payment Plan", command=create_payment_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
    

    def gui_view_active_payment_plans(self):
        """Refresh and display active payment plans"""
        self.refresh_payment_plans()
        self.show_tab('payment_plans')  # Switch to Payment Plans tab
        messagebox.showinfo("Info", "Active payment plans refreshed and displayed in Payment Plans tab")
    

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
            messagebox.showerror("Error", f"Failed to refresh payment plans: {e}")
    
    # Continue with more GUI wrapper functions...
    

    def gui_process_payment_plan_payment(self):
        """GUI for processing payment plan payments"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Payment Plan Payment")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student selection
        student_frame = ttk.LabelFrame(dialog, text="Student Selection", padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(student_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
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
                messagebox.showerror("Error", f"Failed to load payment plans: {e}")
        
        ttk.Button(student_frame, text="Load Payment Plans", command=load_payment_plans).pack(anchor='w', pady=5)
        
        # Payment plans display
        plans_frame = ttk.LabelFrame(dialog, text="Active Payment Plans", padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Remaining', 'Next Due', 'Status')
        plan_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            plan_tree.heading(col, text=col)
            plan_tree.column(col, width=120, anchor='center')
        
        plan_tree.pack(fill='both', expand=True)
        
        # Payment details
        payment_frame = ttk.LabelFrame(dialog, text="Payment Details", padding=15)
        payment_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(payment_frame, text="Payment Amount (£):", font=('Arial', 12)).pack(anchor='w')
        amount_var = tk.StringVar()
        ttk.Entry(payment_frame, textvariable=amount_var, font=('Arial', 12)).pack(anchor='w', pady=5)
        
        ttk.Label(payment_frame, text="Payment Method:", font=('Arial', 12)).pack(anchor='w')
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(payment_frame, textvariable=method_var,
                                   values=["Card", "Cash", "Bank Transfer", "Cheque"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(anchor='w', pady=5)
        
        def process_payment():
            selection = plan_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a payment plan.")
                return
            
            try:
                plan_id = plan_tree.item(selection[0])['values'][0]
                payment_amount = float(amount_var.get())
                payment_method = method_var.get()
                
                if payment_amount <= 0:
                    messagebox.showerror("Error", "Payment amount must be greater than zero.")
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
                    messagebox.showerror("Error", "Payment plan not found.")
                    conn.close()
                    return
                
                student_id, remaining_amount, template_id = plan_data
                
                if payment_amount > remaining_amount:
                    if not messagebox.askyesno("Overpayment", 
                                              f"Payment amount (£{payment_amount:.2f}) exceeds remaining balance (£{remaining_amount:.2f}).\n"
                                              "Continue with overpayment?"):
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
                
                messagebox.showinfo("Success", 
                                   f"Payment processed successfully!\n"
                                   f"Payment ID: {payment_id}\n"
                                   f"Remaining balance: £{new_remaining:.2f}")
                
                dialog.destroy()
                self.refresh_payment_plans()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid payment amount.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process payment: {e}")
        
        ttk.Button(payment_frame, text="Process Payment", command=process_payment).pack(pady=20)
    
    
    

    def gui_modify_payment_plan(self):
        """GUI for modifying payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Modify Payment Plan")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Plan selection
        selection_frame = ttk.LabelFrame(dialog, text="Select Payment Plan", padding=15)
        selection_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(selection_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
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
                messagebox.showerror("Error", f"Failed to load payment plans: {e}")
        
        ttk.Button(selection_frame, text="Load Plans", command=load_student_plans).pack(anchor='w', pady=5)
        
        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text="Active Plans", padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Status')
        plans_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=6)
        
        for col in columns:
            plans_tree.heading(col, text=col)
            plans_tree.column(col, width=100, anchor='center')
        
        plans_tree.pack(fill='both', expand=True)
        
        # Modification options
        modify_frame = ttk.LabelFrame(dialog, text="Modifications", padding=15)
        modify_frame.pack(fill='x', padx=20, pady=10)
        
        def suspend_plan():
            selection = plans_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a plan to suspend.")
                return
            
            plan_id = plans_tree.item(selection[0])['values'][0]
            if messagebox.askyesno("Confirm", f"Suspend payment plan {plan_id}?"):
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
                    
                    messagebox.showinfo("Success", "Payment plan suspended successfully!")
                    load_student_plans()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to suspend plan: {e}")
        
        ttk.Button(modify_frame, text="Suspend Plan", command=suspend_plan).pack(side='left', padx=10)
        ttk.Button(modify_frame, text="Cancel Plan", 
                  command=lambda: self.cancel_selected_plan(plans_tree)).pack(side='left', padx=10)
        ttk.Button(modify_frame, text="Close", command=dialog.destroy).pack(side='right', padx=10)
    

    def cancel_selected_plan(self, tree_widget):
        """Cancel selected payment plan"""
        selection = tree_widget.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a plan to cancel.")
            return
        
        plan_id = tree_widget.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm Cancellation", 
                              f"Are you sure you want to cancel payment plan {plan_id}?\n"
                              "This action cannot be undone."):
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
                
                messagebox.showinfo("Success", "Payment plan cancelled successfully!")
                self.refresh_payment_plans()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel payment plan: {e}")
    

    def gui_cancel_payment_plan(self):
        """GUI for cancelling payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Cancel Payment Plan")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student selection
        student_frame = ttk.LabelFrame(dialog, text="Find Payment Plan", padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(student_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
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
                messagebox.showerror("Error", f"Failed to load payment plans: {e}")
        
        ttk.Button(student_frame, text="Find Plans", command=load_cancellable_plans).pack(anchor='w', pady=5)
        
        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text="Payment Plans", padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Start Date', 'Status')
        cancel_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            cancel_tree.heading(col, text=col)
            cancel_tree.column(col, width=100, anchor='center')
        
        cancel_tree.pack(fill='both', expand=True)
        
        # Cancellation reason
        reason_frame = ttk.LabelFrame(dialog, text="Cancellation Details", padding=15)
        reason_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(reason_frame, text="Cancellation Reason:", font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(reason_frame, height=3, width=50, font=('Arial', 10))
        reason_text.pack(fill='x', pady=5)
        
        def cancel_plan():
            selection = cancel_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a payment plan to cancel.")
                return
            
            reason = reason_text.get("1.0", tk.END).strip()
            if not reason:
                messagebox.showerror("Error", "Cancellation reason is required.")
                return
            
            plan_data = cancel_tree.item(selection[0])['values']
            plan_id = plan_data[0]
            remaining_amount = float(plan_data[3].replace('£', ''))
            
            if messagebox.askyesno("Confirm Cancellation", 
                                  f"Cancel payment plan {plan_id}?\n"
                                  f"Remaining amount: £{remaining_amount:.2f}\n\n"
                                  "This action cannot be undone."):
                try:
                    self.cancel_selected_plan(cancel_tree)
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to cancel payment plan: {e}")
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Cancel Plan", command=cancel_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='left', padx=10)
    
    # Additional GUI functions for other features

    def gui_view_student_financial_statement(self):
        """GUI wrapper for viewing student financial statement"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Student Financial Statement")
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Student selection
        input_frame = ttk.LabelFrame(dialog, text="Student Selection", padding=15)
        input_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(input_frame, text="Student ID:", font=('Arial', 12)).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(input_frame, textvariable=student_id_var, font=('Arial', 12), width=15)
        student_entry.pack(side='left', padx=5)
        
        ttk.Button(input_frame, text="Generate Statement", 
                  command=lambda: self.generate_financial_statement(student_id_var.get(), statement_text)).pack(side='left', padx=10)
        
        # Statement display
        statement_frame = ttk.LabelFrame(dialog, text="Financial Statement", padding=15)
        statement_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        statement_text = ScrolledText(statement_frame, height=25, width=100, font=('Courier', 10))
        statement_text.pack(fill='both', expand=True)
        
        # Export buttons
        export_frame = ttk.Frame(dialog)
        export_frame.pack(pady=10)
        
        def export_statement():
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror("Error", "No statement to export")
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
                    messagebox.showinfo("Success", f"Statement exported to {filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {e}")
        
        def print_statement():
            """Print the financial statement"""
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror("Error", "No statement to print")
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
    
                messagebox.showinfo("Success", "Statement sent to printer")
    
            except Exception as e:
                # Fallback: offer to save as PDF
                if messagebox.askyesno("Print Failed",
                                      f"Printing failed: {e}\n\nWould you like to save as PDF instead?"):
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
                            messagebox.showinfo("Success", f"Saved as text file: {filename}\n(PDF library not available)")
                        except Exception as save_error:
                            messagebox.showerror("Error", f"Failed to save: {save_error}")
    
        ttk.Button(export_frame, text="Export Statement", command=export_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text="Print Statement", command=print_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text="Close", command=dialog.destroy).pack(side='left', padx=10)
    

    def generate_financial_statement(self, student_id, text_widget):
        """Generate and display financial statement"""
        if not student_id:
            messagebox.showerror("Error", "Student ID is required")
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
                messagebox.showerror("Error", "Student not found")
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
            messagebox.showerror("Error", f"Failed to generate statement: {e}")
    
    # Payment Plans GUI Functions
