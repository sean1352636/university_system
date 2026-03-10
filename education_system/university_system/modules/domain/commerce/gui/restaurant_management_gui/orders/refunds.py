"""
Restaurant Payment Refunds Module

Provides comprehensive refund functionality for restaurant payments including:
- Payment list display from restaurant_orders table
- Refund processing with Cash/Card/Student Account options
- Student finance account integration
- Email receipt system
- Finance GUI integration
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from datetime import datetime
from typing import Optional
import csv
import uuid

# Import database connection
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def create_refunds_tab(self, parent):
    """Create comprehensive refunds management tab for restaurant payments."""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(header_frame, text="Restaurant Payment Refunds",
             font=('Arial', 12, 'bold')).pack(anchor=tk.W)

    # Search frame
    search_frame = ttk.LabelFrame(parent, text="Search Payments", padding="10")
    search_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(search_frame, text="Order ID or Customer ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
    search_var = tk.StringVar()
    ttk.Entry(search_frame, textvariable=search_var, width=30).grid(row=0, column=1, padx=5)

    # Payments list frame
    list_frame = ttk.LabelFrame(parent, text="All Restaurant Payments", padding="5")
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    columns = ('order_id', 'customer', 'date', 'total', 'method', 'status')
    payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

    payments_tree.heading('order_id', text='Order ID')
    payments_tree.heading('customer', text='Customer ID')
    payments_tree.heading('date', text='Date/Time')
    payments_tree.heading('total', text='Total (GBP)')
    payments_tree.heading('method', text='Payment Method')
    payments_tree.heading('status', text='Status')

    payments_tree.column('order_id', width=80)
    payments_tree.column('customer', width=100)
    payments_tree.column('date', width=150)
    payments_tree.column('total', width=100)
    payments_tree.column('method', width=120)
    payments_tree.column('status', width=120)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=payments_tree.yview)
    payments_tree.configure(yscrollcommand=scrollbar.set)
    payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_payments_list():
        """Refresh the payments list from database."""
        for item in payments_tree.get_children():
            payments_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()
            search_term = search_var.get().strip()

            if search_term:
                cursor.execute('''
                    SELECT
                        order_id,
                        COALESCE(customer_id, 'N/A') as customer_id,
                        order_time,
                        total_price,
                        COALESCE(payment_method, 'Pending') as payment_method,
                        COALESCE(status, 'Pending') as status
                    FROM restaurant_orders
                    WHERE CAST(order_id AS TEXT) LIKE ? OR CAST(customer_id AS TEXT) LIKE ?
                    ORDER BY order_time DESC
                ''', (f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT
                        order_id,
                        COALESCE(customer_id, 'N/A') as customer_id,
                        order_time,
                        total_price,
                        COALESCE(payment_method, 'Pending') as payment_method,
                        COALESCE(status, 'Pending') as status
                    FROM restaurant_orders
                    ORDER BY order_time DESC
                    LIMIT 100
                ''')

            for row in cursor.fetchall():
                values = list(row)
                # Ensure all 6 columns
                while len(values) < 6:
                    values.append('N/A')
                # Format amount
                if values[3] and values[3] != 'N/A':
                    try:
                        values[3] = f"{float(values[3]):.2f}"
                    except (ValueError, TypeError):
                        pass
                payments_tree.insert('', tk.END, values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load payments: {e}")

    def view_payment_details():
        """View detailed payment information."""
        selection = payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view details")
            return

        try:
            values = payments_tree.item(selection[0])['values']
            if len(values) < 6:
                messagebox.showerror("Data Error", "Payment record is incomplete")
                return

            details = f"""PAYMENT DETAILS
==================
Order ID: {values[0]}
Customer ID: {values[1]}
Date/Time: {values[2]}
Total Amount: GBP {values[3]}
Payment Method: {values[4]}
Status: {values[5]}
"""
            messagebox.showinfo("Payment Details", details)
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing payment details: {e}")

    def export_payments_csv():
        """Export payments to CSV file."""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"restaurant_payments_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Order ID', 'Customer ID', 'Date/Time', 'Total',
                                   'Payment Method', 'Status'])

                    for item in payments_tree.get_children():
                        values = payments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Payments exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export payments: {e}")

    def process_refund():
        """Process a refund with cash/card/student account options."""
        selection = payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund")
            return

        try:
            values = payments_tree.item(selection[0])['values']
            if len(values) < 6:
                messagebox.showerror("Data Error", "Payment record is incomplete")
                return

            order_id = values[0]
            customer_id = values[1]
            order_date = values[2]
            amount = float(values[3])
            payment_method = values[4]
            status = values[5]
        except (IndexError, ValueError) as e:
            messagebox.showerror("Error", f"Error reading payment data: {e}")
            return

        if status in ('Refunded', 'Partially Refunded'):
            messagebox.showinfo("Already Refunded", "This payment has already been refunded")
            return

        if status not in ('Paid', 'Completed'):
            messagebox.showwarning("Cannot Refund", "Only paid/completed orders can be refunded")
            return

        # Confirm refund
        if not messagebox.askyesno("Confirm Refund",
                                   f"Refund GBP {amount:.2f} for Order #{order_id}?\n\n"
                                   f"Customer ID: {customer_id}\n"
                                   f"Date: {order_date}\n"
                                   f"Payment Method: {payment_method}"):
            return

        # Show refund method selection dialog
        refund_method = show_refund_method_dialog(amount, order_id, self.root)
        if not refund_method:
            return

        # Process based on method
        success = False
        student_id = None

        if refund_method == 'Student Account':
            # Get student ID from order
            student_id = get_student_id_from_order(order_id)
            if not student_id:
                # Prompt for student ID
                student_id = simpledialog.askstring("Student ID", "Enter Student ID for refund:")
                if not student_id:
                    return

            success = add_refund_to_student_account(student_id, amount, order_id)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update order status to refunded
            try:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection failed")
                    return

                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE restaurant_orders
                    SET status = 'Refunded'
                    WHERE order_id = ?
                ''', (order_id,))

                # Generate refund reference
                refund_ref = f"REST-REFUND-{uuid.uuid4().hex[:12].upper()}"

                # Record refund in order_refunds table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS order_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER,
                        refund_amount REAL,
                        refund_type TEXT,
                        refund_method TEXT,
                        refund_reference TEXT,
                        reason TEXT,
                        notes TEXT,
                        refund_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                    )
                ''')

                cursor.execute('''
                    INSERT INTO order_refunds
                    (order_id, refund_amount, refund_type, refund_method, refund_reference, reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (order_id, amount, 'Full', refund_method, refund_ref, 'Customer Request'))

                conn.commit()
                conn.close()

                # Send refund receipt email
                send_refund_receipt(order_id, amount, refund_method, refund_ref, student_id)

                # Notify finance GUI
                notify_finance_gui(order_id, amount, refund_method, refund_ref, student_id)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                  f"Method: {refund_method}\n"
                                  f"Refund Reference: {refund_ref}")

                refresh_payments_list()
            except Exception as e:
                messagebox.showerror("Refund Error", f"Failed to process refund: {e}")
        else:
            messagebox.showerror("Refund Failed", "Failed to process student account refund")

    # Button frame
    button_frame = ttk.Frame(parent)
    button_frame.pack(fill=tk.X, padx=10)

    ttk.Button(button_frame, text="Search", command=refresh_payments_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Show All",
              command=lambda: [search_var.set(''), refresh_payments_list()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="View Details", command=view_payment_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=export_payments_csv).pack(side=tk.LEFT, padx=5)

    # Initial load
    refresh_payments_list()


def show_refund_method_dialog(amount: float, order_id: int, parent_window) -> Optional[str]:
    """Show refund method selection dialog."""
    dialog = tk.Toplevel(parent_window)
    dialog.title("Select Refund Method")
    dialog.geometry("450x350")
    dialog.transient(parent_window)
    dialog.grab_set()

    result = {'method': None}

    # Refund info frame
    info_frame = ttk.LabelFrame(dialog, text="Refund Details", padding="10")
    info_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(info_frame, text=f"Order ID: {order_id}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
             font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

    # Refund method selection
    method_frame = ttk.LabelFrame(dialog, text="Select Refund Method", padding="10")
    method_frame.pack(fill=tk.X, padx=10, pady=10)

    def select_method(method):
        result['method'] = method
        dialog.destroy()

    # Cash button
    ttk.Button(method_frame, text="Cash", width=30,
              command=lambda: select_method('Cash')).pack(pady=5)

    # Card button
    ttk.Button(method_frame, text="Card (Original Payment Method)", width=30,
              command=lambda: select_method('Card')).pack(pady=5)

    # Student Account button
    ttk.Button(method_frame, text="Student Finance Account", width=30,
              command=lambda: select_method('Student Account')).pack(pady=5)

    # Cancel button
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=10)

    dialog.wait_window()
    return result['method']


def get_student_id_from_order(order_id: int) -> Optional[str]:
    """Try to get student ID associated with an order.

    Since restaurant_orders has customer_id instead of student_id,
    we'll return the customer_id which may represent a student.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        # Get customer_id from order (may be a student_id)
        cursor.execute('''
            SELECT customer_id FROM restaurant_orders
            WHERE order_id = ? AND customer_id IS NOT NULL
        ''', (order_id,))
        row = cursor.fetchone()
        conn.close()
        # Return as string for consistency with student_id usage
        return str(row[0]) if row and row[0] else None
    except Exception as e:
        print(f"Error getting customer/student ID from order: {e}")
        return None


def get_student_account_balance(student_id: str) -> Optional[float]:
    """Get student's finance account balance."""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        cursor.execute('''
            SELECT balance FROM student_finance_accounts
            WHERE student_id = ? AND account_status = 'active'
        ''', (student_id,))
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row else None
    except Exception as e:
        print(f"Error getting student balance: {e}")
        return None


def add_refund_to_student_account(student_id: str, amount: float, order_id: int) -> bool:
    """Add refund amount to student's finance account."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Get account_id and balance
        cursor.execute('''
            SELECT account_id, balance FROM student_finance_accounts
            WHERE student_id = ? AND account_status = 'active'
        ''', (student_id,))
        row = cursor.fetchone()

        if not row:
            # Try to create account if it doesn't exist
            cursor.execute('''
                INSERT INTO student_finance_accounts
                (student_id, account_type, balance, account_status, created_at)
                VALUES (?, 'standard', ?, 'active', CURRENT_TIMESTAMP)
            ''', (student_id, amount))
            account_id = cursor.lastrowid
            balance_before = 0
            balance_after = amount
        else:
            account_id = row[0]
            balance_before = float(row[1])
            balance_after = balance_before + amount

            # Add to balance
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ?
            ''', (balance_after, account_id))

        # Record transaction
        cursor.execute('''
            INSERT INTO student_finance_transactions
            (account_id, student_id, transaction_type, amount, balance_before,
             balance_after, description, created_at)
            VALUES (?, ?, 'credit', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (account_id, student_id, amount, balance_before, balance_after,
              f'Restaurant Refund - Order: {order_id}'))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to student account: {e}")
        return False


def send_refund_receipt(order_id: int, amount: float, method: str,
                       refund_ref: str, student_id: Optional[str]):
    """Send refund receipt email."""
    try:
        # Get order and customer details
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Get customer email from order or student
        email = None
        customer_name = "Customer"

        if student_id:
            cursor.execute("SELECT email, first_name, last_name FROM students WHERE student_id = ?",
                         (student_id,))
            row = cursor.fetchone()
            if row:
                email = row[0]
                customer_name = f"{row[1]} {row[2]}"

        # Fallback: try to get from users table
        if not email and student_id:
            cursor.execute("SELECT email FROM users WHERE username = ?", (student_id,))
            row = cursor.fetchone()
            if row:
                email = row[0]

        conn.close()

        if email:
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email
                from education_system.university_system.infrastructure.email.template_utils import render_template

                # Build account balance info if applicable
                account_balance_info = ""
                if method == 'Student Account' and student_id:
                    balance = get_student_account_balance(student_id)
                    if balance is not None:
                        account_balance_info = f"Your new Student Finance Account balance: GBP {balance:.2f}\n"

                # Render email from template
                subject, body = render_template('commerce/restaurant_payment_refund_receipt',
                    customer_name=customer_name,
                    refund_ref=refund_ref,
                    order_id=order_id,
                    amount=f"{amount:.2f}",
                    method=method,
                    refund_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    account_balance_info=account_balance_info
                )

                send_email(email, subject, body)
                print(f"[Restaurant] Refund receipt sent to {email}")
            except Exception as e:
                print(f"Error sending email: {e}")
        else:
            print(f"[Restaurant] No email found for order {order_id}")
    except Exception as e:
        print(f"Error sending refund receipt: {e}")


def notify_finance_gui(order_id: int, amount: float, method: str,
                       refund_ref: str, student_id: Optional[str]):
    """Record refund in finance system for integration."""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Try to insert into finance refunds table if it exists
        try:
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    refund_reference TEXT UNIQUE,
                    department TEXT,
                    amount REAL,
                    refund_method TEXT,
                    refund_date TEXT,
                    refund_time TEXT,
                    transaction_reference TEXT,
                    processed_by TEXT,
                    notes TEXT
                )
            ''')

            # Migrate finance_refunds table to ensure all columns exist
            cursor.execute("PRAGMA table_info(finance_refunds)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add missing columns if needed
            if 'transaction_reference' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN transaction_reference TEXT')
                print("Migration: Added transaction_reference column to finance_refunds table")

            if 'refund_time' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN refund_time TEXT')
                print("Migration: Added refund_time column to finance_refunds table")

            if 'notes' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN notes TEXT')
                print("Migration: Added notes column to finance_refunds table")

            # Insert into finance_refunds table
            cursor.execute('''
                INSERT INTO finance_refunds
                (refund_reference, department, amount, refund_method,
                 refund_date, refund_time, transaction_reference, processed_by, notes)
                VALUES (?, ?, ?, ?, date('now'), time('now'), ?, ?, ?)
            ''', (refund_ref, 'Restaurant', amount, method,
                  f'order_{order_id}', 'restaurant',
                  f'Restaurant Order #{order_id} Refund - Student: {student_id or "N/A"}'))
            conn.commit()
            print(f"[Restaurant] Refund recorded in finance system: {refund_ref}")
        except Exception as e:
            # Log error but don't fail the refund
            print(f"Warning: Could not notify finance system: {e}")

        conn.close()
    except Exception as e:
        print(f"Error notifying finance system: {e}")
