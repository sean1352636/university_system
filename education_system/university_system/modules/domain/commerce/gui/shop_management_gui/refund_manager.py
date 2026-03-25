import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.university_system.modules.domain.commerce.services.shop_management import (
        auth, add_to_shopping_cart, browse_products, checkout_process,
        display_product_management_menu, display_shop_menu,
        get_customer_analytics, get_inventory_valuation, init_shop_db,
        print_product_labels, search_products, set_auth,
        toggle_discount_status, toggle_product_status, view_purchase_history
    )
except Exception:
    try:
        from shop_management import (
            auth, add_to_shopping_cart, browse_products, checkout_process,
            display_product_management_menu, display_shop_menu,
            get_customer_analytics, get_inventory_valuation, init_shop_db,
            print_product_labels, search_products, set_auth,
            toggle_discount_status, toggle_product_status, view_purchase_history
        )
    except Exception:
        # If running standalone, we'll define the essential fallback functions
        def get_customer_analytics():
            return None

        def get_inventory_valuation():
            return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

        def print_product_labels(product_ids=None):
            print("Label printing functionality not available")

        # Note: get_low_stock_items is implemented as a class method in UniversityShopGUI

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Initialize logger
logger = logging.getLogger(__name__)


def show_refunds(self):
    """Display refunds management interface"""
    self.clear_content()
    self.update_status("Loading refunds...")

    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
        return

    # Title
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)

    ttk.Label(title_frame, text="Shop Transaction Refunds", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)

    # Search frame
    search_frame = ttk.LabelFrame(self.content_frame, text="Search Transactions", padding="10")
    search_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(search_frame, text="Search by Transaction ID, Customer:").grid(row=0, column=0, padx=5)
    self.refunds_search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
    search_entry.grid(row=0, column=1, padx=5)

    ttk.Button(search_frame, text="Search", command=self.refresh_refunds_list).grid(row=0, column=2, padx=2)
    ttk.Button(search_frame, text="Show All", command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).grid(row=0, column=3, padx=2)

    # Transactions table
    trans_frame = ttk.LabelFrame(self.content_frame, text="Transactions", padding="10")
    trans_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    trans_frame.columnconfigure(0, weight=1)
    trans_frame.rowconfigure(0, weight=1)

    # Create treeview
    columns = ('transaction_id', 'date', 'customer', 'amount', 'payment_method', 'status')
    self.refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

    self.refunds_tree.heading('transaction_id', text='Transaction ID')
    self.refunds_tree.heading('date', text='Date')
    self.refunds_tree.heading('customer', text='Customer')
    self.refunds_tree.heading('amount', text='Amount')
    self.refunds_tree.heading('payment_method', text='Payment Method')
    self.refunds_tree.heading('status', text='Status')

    self.refunds_tree.column('transaction_id', width=150)
    self.refunds_tree.column('date', width=150)
    self.refunds_tree.column('customer', width=120)
    self.refunds_tree.column('amount', width=100)
    self.refunds_tree.column('payment_method', width=120)
    self.refunds_tree.column('status', width=100)

    # Scrollbars
    scrollbar = ttk.Scrollbar(trans_frame, orient='vertical', command=self.refunds_tree.yview)
    self.refunds_tree.configure(yscrollcommand=scrollbar.set)

    self.refunds_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    # Buttons
    button_frame = ttk.Frame(self.content_frame)
    button_frame.grid(row=3, column=0, pady=10, sticky='ew')

    ttk.Button(button_frame, text="Process Refund", command=self.process_shop_refund).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="View Details", command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Refresh", command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

    # Initial load
    self.refresh_refunds_list()
    self.update_status("Refunds loaded")


def refresh_refunds_list(self):
    """Refresh the refunds list with all transactions"""
    # Clear existing items
    for item in self.refunds_tree.get_children():
        self.refunds_tree.delete(item)

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        search_term = self.refunds_search_var.get().strip()

        if search_term:
            # Search by transaction_id or username
            query = '''
                SELECT t.source_transaction_id as transaction_id, t.created_at as transaction_date, u.username, u.student_id,
                       t.total_amount, t.payment_method, t.status
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND (t.source_transaction_id LIKE ? OR u.username LIKE ? OR u.student_id LIKE ?)
                ORDER BY t.created_at DESC
                LIMIT 500
            '''
            search_pattern = f'%{search_term}%'
            cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        else:
            # Get all transactions
            query = '''
                SELECT t.source_transaction_id as transaction_id, t.created_at as transaction_date, u.username, u.student_id,
                       t.total_amount, t.payment_method, t.status
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop'
                ORDER BY t.created_at DESC
                LIMIT 500
            '''
            cursor.execute(query)

        transactions = cursor.fetchall()

        for trans in transactions:
            # Format customer identifier
            customer_display = trans['student_id'] if trans['student_id'] else trans['username'] or 'Unknown'

            # Format payment method
            payment_display = trans['payment_method'].replace('_', ' ').title() if trans['payment_method'] else 'N/A'

            # Format status
            status_display = trans['status'].upper() if trans['status'] else 'PENDING'

            self.refunds_tree.insert('', tk.END, values=(
                trans['transaction_id'],
                trans['transaction_date'],
                customer_display,
                f"£{trans['total_amount']:.2f}",
                payment_display,
                status_display
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Database Error", f"Error loading transactions: {e}")


def process_shop_refund(self):
    """Process a refund for selected shop transaction"""
    selection = self.refunds_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a transaction to refund.")
        return

    item = self.refunds_tree.item(selection[0])
    values = item['values']

    if len(values) < 6:
        messagebox.showerror("Error", "Invalid transaction data.")
        return

    transaction_id = values[0]
    amount_str = values[3].replace('£', '').strip()
    try:
        amount = float(amount_str)
    except ValueError:
        messagebox.showerror("Error", "Invalid amount format.")
        return

    status = values[5]

    # Check if already refunded
    if status == 'REFUNDED':
        messagebox.showinfo("Already Refunded", "This transaction has already been refunded.")
        return

    # Confirm refund
    if not messagebox.askyesno("Confirm Refund", f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
        return

    # Get transaction details to find student_id or user identifier
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT t.customer_id as user_id, t.student_id as trans_student_id, u.student_id as user_student_id,
                       u.username, t.payment_method
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND t.source_transaction_id = ?
            ''', (transaction_id,))

            trans_data = cursor.fetchone()

            if not trans_data:
                messagebox.showerror("Error", "Transaction not found in database.")
                return

            user_id = trans_data['user_id']
            # Try multiple sources for user identifier (for finance account lookup)
            student_id = trans_data['trans_student_id'] or trans_data['user_student_id'] or trans_data['username']
            payment_method = trans_data['payment_method']

            # Check if user has a finance account
            user_has_finance_account = False
            if student_id:
                cursor.execute('SELECT account_id FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                if cursor.fetchone():
                    user_has_finance_account = True

    except Exception as e:
        messagebox.showerror("Database Error", f"Error fetching transaction details: {e}")
        return

    # Show refund method dialog
    refund_method = self.show_shop_refund_method_dialog(amount, transaction_id, student_id, user_has_finance_account)

    if not refund_method:
        return

    # Process based on method
    try:
        # Generate unique refund reference
        refund_ref = f"SHOP-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Use transaction context manager for atomic operations
        from education_system.university_system.infrastructure.database.db import transaction

        with transaction() as conn:
            cursor = conn.cursor()

            # Update transaction status to refunded
            cursor.execute('''
                UPDATE transactions
                SET status = 'refunded'
                WHERE source_type = 'shop' AND source_transaction_id = ?
            ''', (transaction_id,))

            # Insert refund record into unified_refunds table
            cursor.execute('''
                INSERT INTO unified_refunds
                (source_type, reference_id, reference_type, refund_date, amount,
                 refund_method, refund_reference, student_id, processed_by)
                VALUES ('shop', ?, 'transaction', ?, ?, ?, ?, ?, ?)
            ''', (transaction_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                  refund_ref, student_id, self.current_user.get('username', 'System')))

            # Transaction auto-commits on successful exit from context

        # If student account refund, add to their account
        if refund_method == 'Student Account':
            success = self.add_shop_refund_to_student_account(student_id, amount, refund_ref)
            if not success:
                if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                    messagebox.showwarning("Partial Success",
                                         "Refund recorded but failed to credit student account. Please credit manually.")

        # Send refund receipt email
        self.send_shop_refund_receipt(transaction_id, student_id or user_id, amount, refund_method, refund_ref)

        # Notify finance GUI
        self.notify_shop_finance_gui(transaction_id, amount, refund_method, refund_ref, student_id)

        # Show success message only if window still exists
        if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
            messagebox.showinfo("Refund Processed",
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

            # Refresh the list
            self.refresh_refunds_list()

    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        # Only show error dialog if window still exists
        if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
            messagebox.showerror("Database Error", f"Error processing refund: {e}")


def show_shop_refund_method_dialog(self, amount, transaction_id, student_id, user_has_finance_account=False):
    """Show dialog to select refund method"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Select Refund Method")
    dialog.geometry("400x400")
    dialog.transient(self.root)
    dialog.update_idletasks()
    dialog.grab_set()

    result = {'method': None}

    ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

    # Show user account balance if finance account available
    if student_id and (FINANCE_ACCOUNT_AVAILABLE or user_has_finance_account):
        try:
            current_balance = get_student_finance_account_balance(student_id)
            if current_balance is not None:
                new_balance = current_balance + amount
                balance_frame = ttk.LabelFrame(dialog, text="Finance Account", padding=10)
                balance_frame.pack(pady=10, padx=20, fill=tk.X)

                ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                        font=('Arial', 10, 'bold'), foreground='green').pack(anchor='w')

                # Show helpful note
                ttk.Label(balance_frame, text="(Available for all users with finance accounts)",
                        font=('Arial', 8), foreground='gray').pack(anchor='w', pady=(5,0))
        except Exception as e:
            logger.error(f"Error getting balance: {e}")

    ttk.Label(dialog, text="Select refund method:", font=('Arial', 10)).pack(pady=10)

    button_frame = ttk.Frame(dialog)
    button_frame.pack(pady=20)

    def select_cash():
        result['method'] = 'Cash'
        dialog.destroy()

    def select_card():
        result['method'] = 'Card'
        dialog.destroy()

    def select_student_account():
        if not student_id:
            messagebox.showerror("Error", "No user account identifier found for this transaction.")
            return
        result['method'] = 'Student Account'
        dialog.destroy()

    ttk.Button(button_frame, text="Cash Refund", command=select_cash, width=25).pack(pady=5)
    ttk.Button(button_frame, text="Card Refund", command=select_card, width=25).pack(pady=5)

    # Show Student Account option if user has a finance account
    if student_id and (FINANCE_ACCOUNT_AVAILABLE or user_has_finance_account):
        ttk.Button(button_frame, text="Refund to Finance Account",
                  command=select_student_account, width=25,
                  style='Accent.TButton').pack(pady=5)

    ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=25).pack(pady=10)

    dialog.wait_window()
    return result['method']


def send_shop_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
    """Send refund receipt email to customer"""
    try:
        # Get customer email
        if FINANCE_ACCOUNT_AVAILABLE:
            customer_info = get_student_info(customer_id)
            if not customer_info or not customer_info.get('email'):
                logger.warning(f"No email found for customer {customer_id}")
                return

            customer_email = customer_info['email']
            customer_name = customer_info.get('full_name', 'Valued Customer')
        else:
            # Fallback: get email from users table
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT username, email FROM users WHERE id = ? OR student_id = ?', (customer_id, customer_id))
            user = cursor.fetchone()
            conn.close()

            if not user or not user['email']:
                logger.warning(f"No email found for customer {customer_id}")
                return

            customer_email = user['email']
            customer_name = user['username']

        # Get updated balance if student account refund
        balance_text = ""
        if method == 'Student Account' and FINANCE_ACCOUNT_AVAILABLE:
            try:
                new_balance = get_student_finance_account_balance(customer_id)
                if new_balance is not None:
                    balance_text = f"\n\nYour updated account balance is: £{new_balance:.2f}"
            except Exception:
                pass

        # Prepare template variables
        from education_system.university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'customer_name': customer_name,
            'transaction_id': transaction_id,
            'amount': f"{amount:.2f}",
            'method': method,
            'refund_ref': refund_ref,
            'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance_text': balance_text
        }

        subject, body = render_template('commerce/shop_payment_refund_receipt', template_vars)
        if not subject or not body:
            logger.error("Failed to render email template")
            return

        from education_system.university_system.infrastructure.email.email_service import send_email
        result = send_email(customer_email, subject, body)
        if result:
            logger.info(f"Refund receipt sent to {customer_email}")
        else:
            logger.warning(f"Failed to send refund receipt to {customer_email}")

    except Exception as e:
        logger.error(f"Error sending refund receipt: {e}")


def export_refunds_to_csv(self):
    """Export refunds list to CSV file"""
    try:
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"shop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(['Transaction ID', 'Date', 'Customer', 'Amount',
                           'Payment Method', 'Status'])

            # Write data
            for item in self.refunds_tree.get_children():
                values = self.refunds_tree.item(item)['values']
                writer.writerow(values)

        messagebox.showinfo("Export Successful", f"Data exported to:\n{filename}")

    except Exception as e:
        messagebox.showerror("Export Error", f"Error exporting data: {e}")

# Backward compatibility functions

