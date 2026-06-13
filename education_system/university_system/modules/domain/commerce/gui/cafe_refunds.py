"""
Cafe System - Refunds tab mixin
Handles refund processing, student account refunds, and refund receipts
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.commerce.gui.cafe_common import get_db_connection, EMAIL_SERVICE_AVAILABLE


class CafeRefundsMixin:
    """Mixin for refund management tab functionality"""

    def create_refunds_tab(self):
        """Create payment refunds management tab"""
        refunds_frame = ttk.Frame(self.notebook)
        self.notebook.add(refunds_frame, text=_t("cafe.tab_refunds"))

        # Header
        header_frame = ttk.Frame(refunds_frame)
        header_frame.pack(fill=tk.X, pady=(10, 10))
        ttk.Label(header_frame, text=_t("cafe.refunds.header"),
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, padx=10)

        # Search frame
        search_frame = ttk.LabelFrame(refunds_frame, text=_t("cafe.refunds.search_orders"), padding="10")
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(search_frame, text=_t("cafe.refunds.search_label")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.refund_search_var, width=30).grid(row=0, column=1, padx=5)

        # Payments list frame
        list_frame = ttk.LabelFrame(refunds_frame, text=_t("cafe.refunds.all_orders"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('order_id', 'date', 'customer', 'student_id', 'total', 'method', 'status')
        self.refunds_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.refunds_tree.heading('order_id', text=_t('cafe.columns.order_id'))
        self.refunds_tree.heading('date', text=_t('cafe.columns.date_time'))
        self.refunds_tree.heading('customer', text=_t('cafe.columns.customer'))
        self.refunds_tree.heading('student_id', text=_t('cafe.columns.student_id'))
        self.refunds_tree.heading('total', text=_t('cafe.columns.total_gbp'))
        self.refunds_tree.heading('method', text=_t('cafe.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('cafe.columns.status'))

        self.refunds_tree.column('order_id', width=80)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=120)
        self.refunds_tree.column('student_id', width=100)
        self.refunds_tree.column('total', width=100)
        self.refunds_tree.column('method', width=120)
        self.refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)
        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(refunds_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_t("cafe.refunds.button_search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("cafe.refunds.button_show_all"),
                  command=lambda: [self.refund_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("cafe.refunds.button_process"), command=self.process_cafe_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("cafe.refunds.button_view_details"), command=self.view_refund_payment_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("cafe.refunds.button_export_csv"), command=self.export_refunds_csv).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list from database."""
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.db_connection_failed"))
                return

            cursor = conn.cursor()
            search_term = self.refund_search_var.get().strip()

            if search_term:
                cursor.execute('''
                    SELECT
                        id,
                        order_date,
                        COALESCE(customer_name, 'N/A') as customer_name,
                        COALESCE(student_id, 'N/A') as student_id,
                        total_amount,
                        COALESCE(payment_method, 'Cash') as payment_method,
                        COALESCE(order_status, 'completed') as order_status
                    FROM orders
                    WHERE source_type = 'cafe' AND (CAST(id AS TEXT) LIKE ? OR customer_name LIKE ? OR student_id LIKE ?)
                    ORDER BY order_date DESC
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT
                        id,
                        order_date,
                        COALESCE(customer_name, 'N/A') as customer_name,
                        COALESCE(student_id, 'N/A') as student_id,
                        total_amount,
                        COALESCE(payment_method, 'Cash') as payment_method,
                        COALESCE(order_status, 'completed') as order_status
                    FROM orders
                    WHERE source_type = 'cafe'
                    ORDER BY order_date DESC
                    LIMIT 100
                ''')

            for row in cursor.fetchall():
                values = list(row)
                # Ensure all 7 columns
                while len(values) < 7:
                    values.append('N/A')
                # Format amount
                if values[4] and values[4] != 'N/A':
                    try:
                        values[4] = f"{float(values[4]):.2f}"
                    except (ValueError, TypeError):
                        pass
                self.refunds_tree.insert('', tk.END, values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_orders", error=str(e)))

    def view_refund_payment_details(self):
        """View detailed payment information."""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_selection"))
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 7:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.data_incomplete"))
                return

            details = f"""ORDER DETAILS
==================
Order ID: {values[0]}
Date/Time: {values[1]}
Customer: {values[2]}
Student ID: {values[3]}
Total Amount: GBP {values[4]}
Payment Method: {values[5]}
Status: {values[6]}
"""
            messagebox.showinfo(_t("cafe.refunds.order_details_title"), details)
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.view_details_failed", error=str(e)))

    def export_refunds_csv(self):
        """Export orders to CSV file."""
        try:
            import csv
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"cafe_orders_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Order ID', 'Date/Time', 'Customer', 'Student ID',
                                   'Total', 'Payment Method', 'Status'])

                    for item in self.refunds_tree.get_children():
                        values = self.refunds_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo(_t("common.success"), f"Orders exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to export orders: {e}")

    def process_cafe_refund(self):
        """Process a refund with cash/card/student account options."""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_selection_refund"))
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 7:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.data_incomplete"))
                return

            order_id = values[0]
            order_date = values[1]
            customer_name = values[2]
            student_id = values[3] if values[3] != 'N/A' else None
            amount = float(values[4])
            payment_method = values[5]
            status = values[6]
        except (IndexError, ValueError) as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.reading_order_data", error=str(e)))
            return

        if status == 'refunded':
            messagebox.showinfo(_t("common.info"), _t("cafe.messages.already_refunded"))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("common.confirm"),
                                   _t("cafe.messages.confirm_refund",
                                      amount=f"{amount:.2f}",
                                      id=order_id,
                                      customer=customer_name,
                                      date=order_date,
                                      method=payment_method)):
            return

        # Show refund method selection dialog
        refund_method = self.show_cafe_refund_method_dialog(amount, order_id, student_id)
        if not refund_method:
            return

        # Process based on method
        success = False

        if refund_method == 'Student Account':
            if not student_id:
                # Prompt for student ID
                student_id = simpledialog.askstring(_t("cafe.refunds.student_id_label"), _t("cafe.messages.student_id_prompt"))
                if not student_id:
                    return

            success = self.add_cafe_refund_to_student_account(student_id, amount, order_id)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update order status to refunded
            try:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror(_t("common.error"), _t("cafe.errors.db_connection_failed"))
                    return

                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE orders
                    SET order_status = 'refunded'
                    WHERE order_id = ? AND source_type = 'cafe'
                ''', (order_id,))

                # Generate refund reference
                import uuid
                refund_ref = f"CAFE-REFUND-{uuid.uuid4().hex[:12].upper()}"

                # Record refund in unified_refunds table
                cursor.execute('''
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, amount, refund_method, refund_reference, student_id, refund_date, status)
                    VALUES ('cafe', ?, 'order', ?, ?, ?, ?, CURRENT_TIMESTAMP, 'processed')
                ''', (str(order_id), amount, refund_method, refund_ref, student_id))
                refund_row_id = cursor.lastrowid

                conn.commit()
                conn.close()

                # Auto-post to GL (cash has moved). Never raises.
                try:
                    from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                    notify_ledger('refund', refund_row_id, posted_by='cafe')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                # Send refund receipt email
                self.send_cafe_refund_receipt(order_id, customer_name, amount, refund_method, refund_ref, student_id)

                # Notify finance GUI
                self.notify_cafe_finance_gui(order_id, amount, refund_method, refund_ref, student_id)

                messagebox.showinfo(_t("common.success"),
                                  _t("cafe.messages.refund_processed",
                                     amount=f"{amount:.2f}",
                                     method=refund_method,
                                     ref=refund_ref))

                self.refresh_refunds_list()
            except Exception as e:
                messagebox.showerror(_t("common.error"), f"Failed to process refund: {e}")
        else:
            messagebox.showerror(_t("common.error"), _t("cafe.messages.refund_failed"))

    def show_cafe_refund_method_dialog(self, amount: float, order_id: int, student_id=None):
        """Show refund method selection dialog."""
        dialog = tk.Toplevel(self.cafe_window)
        dialog.title(_t("cafe.refunds.select_method_title"))
        dialog.geometry("450x400")
        dialog.transient(self.cafe_window)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("cafe.refunds.details_title"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=_t("cafe.refunds.order_id_label") + f" {order_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=_t("cafe.refunds.refund_amount_label") + f" GBP {amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance if available
        if student_id:
            balance = self.get_cafe_student_account_balance(student_id)
            if balance is not None:
                ttk.Label(info_frame, text=_t("cafe.refunds.student_id_label") + f" {student_id}").pack(anchor=tk.W, pady=(5, 0))
                ttk.Label(info_frame, text=_t("cafe.refunds.current_balance_label") + f" GBP {balance:.2f}").pack(
                    anchor=tk.W, pady=(5, 0))
                ttk.Label(info_frame, text=_t("cafe.refunds.balance_after_label") + f" GBP {balance + amount:.2f}",
                         foreground='green').pack(anchor=tk.W)

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("cafe.refunds.method_frame"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text=_t("cafe.refunds.method_cash"), width=30,
                  command=lambda: select_method('Cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text=_t("cafe.refunds.method_card"), width=30,
                  command=lambda: select_method('Card')).pack(pady=5)

        # Student Account button
        ttk.Button(method_frame, text=_t("cafe.refunds.method_student_account"), width=30,
                  command=lambda: select_method('Student Account')).pack(pady=5)

        # Cancel button
        ttk.Button(dialog, text=_t("cafe.refunds.button_cancel"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def get_cafe_student_account_balance(self, student_id: str):
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

    def add_cafe_refund_to_student_account(self, student_id: str, amount: float, order_id: int):
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
                  f'Cafe Refund - Order: {order_id}'))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding to student account: {e}")
            return False

    def send_cafe_refund_receipt(self, order_id: int, customer_name: str, amount: float,
                                 method: str, refund_ref: str, student_id=None):
        """Send refund receipt email."""
        try:
            # Get customer email
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get email from student or user records
            email = None

            if student_id:
                cursor.execute("SELECT email FROM students WHERE student_id = ?", (student_id,))
                row = cursor.fetchone()
                if row:
                    email = row[0]

                # Fallback to users table
                if not email:
                    cursor.execute("SELECT email FROM users WHERE username = ?", (student_id,))
                    row = cursor.fetchone()
                    if row:
                        email = row[0]

            conn.close()

            if email and EMAIL_SERVICE_AVAILABLE:
                from education_system.university_system.infrastructure.email.email_service import send_email

                # Prepare account balance info (conditional)
                account_balance_info = ""
                if method == 'Student Account' and student_id:
                    balance = self.get_cafe_student_account_balance(student_id)
                    if balance is not None:
                        account_balance_info = f"Your new Student Finance Account balance: GBP {balance:.2f}"

                # Prepare template variables
                from education_system.university_system.infrastructure.email.template_utils import render_template

                template_vars = {
                    'customer_name': customer_name,
                    'refund_ref': refund_ref,
                    'order_id': order_id,
                    'amount': f"{amount:.2f}",
                    'method': method,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'account_balance_info': account_balance_info
                }

                subject, body = render_template('commerce/cafe_payment_refund_receipt', template_vars)
                if not subject or not body:
                    print("Failed to render email template")
                    return

                send_email(email, subject, body)
                print(f"[Cafe] Refund receipt sent to {email}")
            else:
                print(f"[Cafe] No email found for order {order_id}")
        except Exception as e:
            print(f"Error sending refund receipt: {e}")

    def notify_cafe_finance_gui(self, order_id: int, amount: float, method: str,
                                refund_ref: str, student_id=None):
        """Record refund in finance system for integration."""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Refund already recorded in unified_refunds table
            print(f"[Cafe] Refund recorded in finance system: {refund_ref}")

            conn.close()
        except Exception as e:
            print(f"Error notifying finance system: {e}")
