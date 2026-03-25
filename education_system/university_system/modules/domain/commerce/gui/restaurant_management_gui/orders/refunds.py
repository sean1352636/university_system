"""
Restaurant Payment Refunds Module

Provides comprehensive refund functionality for restaurant payments including:
- Payment list display from orders table (source_type='restaurant')
- Refund processing with Cash/Card/Finance Account options
- Student finance account integration
- Email receipt system
- Finance GUI integration
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
                        order_date,
                        total_amount,
                        COALESCE(payment_method, 'Pending') as payment_method,
                        COALESCE(order_status, 'Pending') as status
                    FROM orders
                    WHERE CAST(order_id AS TEXT) LIKE ? OR CAST(customer_id AS TEXT) LIKE ?
                    ORDER BY order_date DESC
                ''', (f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT
                        order_id,
                        COALESCE(customer_id, 'N/A') as customer_id,
                        order_date,
                        total_amount,
                        COALESCE(payment_method, 'Pending') as payment_method,
                        COALESCE(order_status, 'Pending') as status
                    FROM orders
                    ORDER BY order_date DESC
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

        # Resolve who paid for this order
        payer_info = get_payer_info_from_order(order_id)
        payer_id = payer_info.get('user_identifier') if payer_info else None
        payer_name = payer_info.get('name', 'Customer') if payer_info else 'Customer'
        payer_email = payer_info.get('email') if payer_info else None

        # Show refund method selection dialog with payer details
        refund_method = show_refund_method_dialog(
            amount, order_id, self.root,
            original_method=payment_method,
            payer_name=payer_name,
            payer_id=payer_id
        )
        if not refund_method:
            return

        # Process based on method
        success = False

        if refund_method == 'Finance Account':
            if not payer_id:
                messagebox.showerror("Refund Failed",
                                    "Cannot refund to Finance Account — no account linked to this order")
                return
            success = add_refund_to_student_account(payer_id, amount, order_id)
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
                    UPDATE orders
                    SET order_status = 'Refunded'
                    WHERE order_id = ?
                ''', (order_id,))

                # Generate refund reference
                refund_ref = f"REST-REFUND-{uuid.uuid4().hex[:12].upper()}"

                # Record refund in unified_refunds table
                cursor.execute('''
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, amount, refund_type,
                     refund_method, refund_reference, reason, refund_date)
                    VALUES ('order', ?, 'order', ?, 'Full', ?, ?, 'Customer Request', CURRENT_TIMESTAMP)
                ''', (str(order_id), amount, refund_method, refund_ref))

                conn.commit()
                conn.close()

                # Send refund receipt email to the payer
                email_sent = send_refund_receipt(order_id, amount, refund_method, refund_ref,
                                                payer_id, payer_name, payer_email)

                # Notify finance GUI
                notify_finance_gui(order_id, amount, refund_method, refund_ref, payer_id)

                success_msg = (f"Refund of GBP {amount:.2f} processed successfully\n\n"
                              f"Refunded to: {payer_name}\n"
                              f"Method: {refund_method}\n"
                              f"Refund Reference: {refund_ref}")

                if email_sent:
                    success_msg += f"\n\nReceipt emailed to {payer_email}"
                elif payer_email:
                    success_msg += f"\n\nCould not send email receipt"

                messagebox.showinfo("Refund Processed", success_msg)

                refresh_payments_list()
            except Exception as e:
                messagebox.showerror("Refund Error", f"Failed to process refund: {e}")
        else:
            messagebox.showerror("Refund Failed", "Failed to process finance account refund")

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


def show_refund_method_dialog(amount: float, order_id: int, parent_window,
                              original_method: str = None, payer_name: str = None,
                              payer_id: str = None) -> Optional[str]:
    """Show refund method selection dialog with payer details."""
    dialog = tk.Toplevel(parent_window)
    dialog.title("Select Refund Method")
    dialog.geometry("450x400")
    dialog.transient(parent_window)
    dialog.grab_set()

    result = {'method': None}

    # Refund info frame
    info_frame = ttk.LabelFrame(dialog, text="Refund Details", padding="10")
    info_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(info_frame, text=f"Order ID: {order_id}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
             font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

    if payer_name:
        ttk.Label(info_frame, text=f"Refund to: {payer_name}",
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(5, 0))
    if original_method:
        ttk.Label(info_frame, text=f"Original Payment: {original_method}",
                 font=('Arial', 10)).pack(anchor=tk.W)

    # Refund method selection
    method_frame = ttk.LabelFrame(dialog, text="Select Refund Method", padding="10")
    method_frame.pack(fill=tk.X, padx=10, pady=10)

    def select_method(method):
        result['method'] = method
        dialog.destroy()

    # Cash button
    cash_text = "Cash"
    if original_method == 'Cash':
        cash_text += " (Original Method)"
    ttk.Button(method_frame, text=cash_text, width=30,
              command=lambda: select_method('Cash')).pack(pady=5)

    # Card button
    card_text = "Card"
    if original_method == 'Card':
        card_text += " (Original Method)"
    ttk.Button(method_frame, text=card_text, width=30,
              command=lambda: select_method('Card')).pack(pady=5)

    # Finance Account button
    finance_text = "Finance Account"
    if original_method == 'Finance Account':
        finance_text += " (Original Method)"
    if payer_id:
        ttk.Button(method_frame, text=finance_text, width=30,
                  command=lambda: select_method('Finance Account')).pack(pady=5)
    else:
        btn = ttk.Button(method_frame, text="Finance Account (No account linked)", width=30)
        btn.pack(pady=5)
        btn.configure(state='disabled')

    # Cancel button
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=10)

    dialog.wait_window()
    return result['method']


def get_payer_info_from_order(order_id: int) -> Optional[dict]:
    """Get full payer details from an order.

    Resolves through restaurant_customers to find the user identifier
    (student_id or username) and email address.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        # Get customer_id from order
        cursor.execute('''
            SELECT customer_id, payment_method FROM orders
            WHERE order_id = ? AND customer_id IS NOT NULL
        ''', (order_id,))
        order_row = cursor.fetchone()

        if not order_row or not order_row[0]:
            conn.close()
            return None

        customer_id = order_row[0]

        # Look up restaurant_customers to get the name (which is the student_id/username)
        cursor.execute('''
            SELECT name, email FROM restaurant_customers
            WHERE customer_id = ?
        ''', (customer_id,))
        cust_row = cursor.fetchone()

        if not cust_row:
            conn.close()
            return None

        user_identifier = cust_row[0]  # student_id or username
        customer_email = cust_row[1]
        customer_name = user_identifier

        # Try to get full name and email from students table
        cursor.execute('''
            SELECT first_name, last_name, email FROM students
            WHERE student_id = ?
        ''', (user_identifier,))
        student_row = cursor.fetchone()

        if student_row:
            first = student_row[0] or ''
            last = student_row[1] or ''
            customer_name = f"{first} {last}".strip() or user_identifier
            if student_row[2]:
                customer_email = student_row[2]

        # Fallback: try users table (for admin/staff)
        if not customer_email:
            cursor.execute('SELECT email FROM users WHERE username = ?', (user_identifier,))
            user_row = cursor.fetchone()
            if user_row and user_row[0]:
                customer_email = user_row[0]

        conn.close()

        return {
            'user_identifier': user_identifier,
            'name': customer_name,
            'email': customer_email
        }

    except Exception as e:
        print(f"Error getting payer info from order: {e}")
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
            INSERT INTO transactions
            (source_type, account_id, student_id, transaction_type, amount, balance_before,
             balance_after, description, created_at)
            VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (account_id, student_id, amount, balance_before, balance_after,
              f'Restaurant Refund - Order: {order_id}'))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to student account: {e}")
        return False


def send_refund_receipt(order_id: int, amount: float, method: str,
                       refund_ref: str, payer_id: Optional[str] = None,
                       payer_name: str = "Customer",
                       payer_email: Optional[str] = None) -> bool:
    """Send refund receipt email to the payer.

    Returns True if email was sent successfully.
    """
    if not payer_email:
        print(f"[Restaurant] No email found for order {order_id}")
        return False

    try:
        from education_system.university_system.infrastructure.email.email_service import send_email
        from education_system.university_system.infrastructure.email.template_utils import render_template

        # Build account balance info if applicable
        account_balance_info = ""
        if method == 'Finance Account' and payer_id:
            balance = get_student_account_balance(payer_id)
            if balance is not None:
                account_balance_info = f"Your new Finance Account balance: GBP {balance:.2f}\n"

        # Render email from template
        result = render_template('commerce/restaurant_payment_refund_receipt', {
            'customer_name': payer_name,
            'refund_ref': refund_ref,
            'order_id': order_id,
            'amount': f"{amount:.2f}",
            'method': method,
            'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'account_balance_info': account_balance_info
        })
        if result and isinstance(result, tuple):
            subject, body = result
        else:
            subject = "Refund Receipt - University Restaurant"
            body = (f"Dear {payer_name},\n\n"
                    f"Your refund has been processed.\n\n"
                    f"Refund Reference: {refund_ref}\n"
                    f"Order ID: {order_id}\n"
                    f"Amount: GBP {amount:.2f}\n"
                    f"Refund Method: {method}\n"
                    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"{account_balance_info}\n"
                    f"Thank you.")

        success = send_email(payer_email, subject, body)
        if success:
            print(f"[Restaurant] Refund receipt sent to {payer_email}")
        return success
    except Exception as e:
        print(f"Error sending refund receipt email: {e}")
        return False


def notify_finance_gui(order_id: int, amount: float, method: str,
                       refund_ref: str, student_id: Optional[str]):
    """Record refund in finance system for integration."""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Refund already recorded in unified_refunds table
        print(f"[Restaurant] Refund recorded in finance system: {refund_ref}")
        conn.close()
    except Exception as e:
        print(f"Error notifying finance system: {e}")
