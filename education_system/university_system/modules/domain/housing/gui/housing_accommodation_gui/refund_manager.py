"""
Refund management functions - handling payment refunds.
Manages refund processing, student account credits, and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import json
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import email service if available
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
def send_email(*args, **kwargs):
        return False

# Dynamic activity logger
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_dynamic_activity
except ImportError:
    def log_dynamic_activity(*args, **kwargs):
        pass

def create_payments_refunds_tab(self, parent):
        """Create payments and refunds management tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="Housing Payments & Refunds",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text="(Housing rent and deposit payments only)",
                 font=('Arial', 9, 'italic'), foreground='gray').pack(anchor=tk.W)

        # Search/Filter frame
        search_frame = ttk.LabelFrame(parent, text="Search Payments", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.refund_search_var, width=20).grid(row=0, column=1, padx=5)

        ttk.Button(search_frame, text="Search", command=lambda: _refresh_refund_payments_list(self)).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="Show All", command=lambda: [self.refund_search_var.set(''), _refresh_refund_payments_list(self)]).grid(row=0, column=3, padx=5)

        # Payments list frame
        list_frame = ttk.LabelFrame(parent, text="Housing Payments", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('payment_id', 'student_id', 'amount', 'method', 'date', 'period_start', 'period_end', 'status')
        self.refund_payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.refund_payments_tree.heading('payment_id', text='Payment ID')
        self.refund_payments_tree.heading('student_id', text='Student ID')
        self.refund_payments_tree.heading('amount', text='Amount (£)')
        self.refund_payments_tree.heading('method', text='Method')
        self.refund_payments_tree.heading('date', text='Date')
        self.refund_payments_tree.heading('period_start', text='Period Start')
        self.refund_payments_tree.heading('period_end', text='Period End')
        self.refund_payments_tree.heading('status', text='Status')

        self.refund_payments_tree.column('payment_id', width=120)
        self.refund_payments_tree.column('student_id', width=100)
        self.refund_payments_tree.column('amount', width=80)
        self.refund_payments_tree.column('method', width=120)
        self.refund_payments_tree.column('date', width=100)
        self.refund_payments_tree.column('period_start', width=100)
        self.refund_payments_tree.column('period_end', width=100)
        self.refund_payments_tree.column('status', width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.refund_payments_tree.yview)
        self.refund_payments_tree.configure(yscrollcommand=scrollbar.set)

        self.refund_payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons frame
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X)

        ttk.Button(action_frame, text="Process Refund", command=lambda: process_housing_refund(self)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="View Details", command=lambda: view_housing_payment_details(self)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Export to CSV", command=lambda: export_housing_payments_csv(self)).pack(side=tk.LEFT, padx=5)

        _refresh_refund_payments_list(self)

def _refresh_refund_payments_list(self):
        """Refresh the payments list for refunds tab"""
        for item in self.refund_payments_tree.get_children():
            self.refund_payments_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            search_term = self.refund_search_var.get().strip()

            # Only show completed housing payments
            if search_term:
                cursor.execute('''
                    SELECT source_payment_id, student_id, amount, payment_method,
                           payment_date, payment_period_start, payment_period_end, status
                    FROM payments
                    WHERE source_type = 'housing' AND student_id LIKE ? AND status = 'Completed'
                    ORDER BY payment_date DESC
                ''', (f'%{search_term}%',))
            else:
                cursor.execute('''
                    SELECT source_payment_id, student_id, amount, payment_method,
                           payment_date, payment_period_start, payment_period_end, status
                    FROM payments
                    WHERE source_type = 'housing' AND status = 'Completed'
                    ORDER BY payment_date DESC
                    LIMIT 100
                ''')

            for row in cursor.fetchall():
                values = list(row)
                # Format amount
                if values[2]:
                    try:
                        values[2] = f"{float(values[2]):.2f}"
                    except (ValueError, TypeError):
                        pass
                self.refund_payments_tree.insert('', tk.END, values=values)

            conn.close()
        except Exception as e:
            print(f"Error loading payments for refunds: {e}")
            messagebox.showerror("Error", f"Failed to load payments: {e}")

def view_housing_payment_details(self):
        """View detailed payment information"""
        selection = self.refund_payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view details")
            return

        try:
            values = self.refund_payments_tree.item(selection[0])['values']

            if len(values) < 8:
                messagebox.showerror("Data Error", "Payment record is incomplete.")
                return

            details = f"""PAYMENT DETAILS
================
Payment ID: {values[0]}
Student ID: {values[1]}
Amount: £{values[2]}
Payment Method: {values[3]}
Payment Date: {values[4]}
Period Start: {values[5]}
Period End: {values[6]}
Status: {values[7]}
"""
            messagebox.showinfo("Payment Details", details)
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing payment details: {e}")

def export_housing_payments_csv(self):
        """Export housing payments to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"housing_payments_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Payment ID', 'Student ID', 'Amount', 'Method',
                                   'Date', 'Period Start', 'Period End', 'Status'])

                    for item in self.refund_payments_tree.get_children():
                        values = self.refund_payments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Payments exported to:\n{filepath}")
                log_dynamic_activity('export', 'housing_payments', details=json.dumps({'file': filepath}))
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export payments: {e}")

def process_housing_refund(self):
        """Process a housing payment refund"""
        selection = self.refund_payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund")
            return

        try:
            values = self.refund_payments_tree.item(selection[0])['values']

            if len(values) < 8:
                messagebox.showerror("Data Error", "Payment record is incomplete.")
                return

            payment_id = values[0]
            student_id = values[1]
            amount = float(values[2])
            status = values[7]

            # Check if already refunded
            if status == 'Refunded':
                messagebox.showinfo("Refund Already Made", "Refund already made")
                return

        except (IndexError, ValueError) as e:
            messagebox.showerror("Error", f"Error reading payment data: {e}")
            return

        # Confirm refund
        if not messagebox.askyesno("Confirm Refund",
                                   f"Refund £{amount:.2f} to {student_id}?\n\n"
                                   f"Payment ID: {payment_id}"):
            return

        # Show refund method selection dialog
        refund_method = _show_housing_refund_method_dialog(self, amount, student_id)
        if not refund_method:
            return

        # Process based on method
        success = False
        if refund_method == 'Student Account':
            success = _add_to_student_account(self, student_id, amount, payment_id)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update payment status to refunded
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE payments
                    SET status = 'Refunded'
                    WHERE source_type = 'housing' AND source_payment_id = ?
                ''', (payment_id,))

                conn.commit()
                conn.close()

                # Notify finance system
                _notify_finance_for_housing_refund(self, student_id, amount, refund_method, payment_id)

                # Send refund receipt email
                _send_housing_refund_receipt(self, student_id, amount, refund_method, payment_id)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of £{amount:.2f} processed successfully\n\n"
                                  f"Method: {refund_method}\n"
                                  f"Payment ID: {payment_id}")

                log_dynamic_activity('refund', 'housing_payment', details=json.dumps({
                    'payment_id': payment_id,
                    'amount': amount,
                    'method': refund_method,
                    'student_id': student_id
                }))

                _refresh_refund_payments_list(self)
            except Exception as e:
                messagebox.showerror("Refund Error", f"Failed to process refund: {e}")
        else:
            messagebox.showerror("Refund Failed", "Failed to process student account refund")

def _show_housing_refund_method_dialog(self, amount: float, student_id: str):
        """Show refund method selection dialog for housing payments"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text="Refund Details", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Student ID: {student_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Refund Amount: £{amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance
        balance = _get_student_account_balance(self, student_id)
        if balance is not None:
            ttk.Label(info_frame, text=f"Current Account Balance: £{balance:.2f}").pack(
                anchor=tk.W, pady=(5, 0))
            ttk.Label(info_frame, text=f"Balance After Refund: £{balance + amount:.2f}",
                     foreground='green').pack(anchor=tk.W)

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text="Select Refund Method", padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text="Cash", width=20,
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

def _get_student_account_balance(self, student_id: str):
        """Get student's finance account balance"""
        try:
            conn = get_connection()
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

def _add_to_student_account(self, student_id: str, amount: float, original_ref: str) -> bool:
        """Add refund amount to student's finance account"""
        try:
            conn = get_connection()
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
                    (student_id, balance, account_status, created_at)
                    VALUES (?, ?, 'active', CURRENT_TIMESTAMP)
                ''', (student_id, amount))
                account_id = cursor.lastrowid
            else:
                account_id = row[0]
                balance_before = float(row[1])
                balance_after = balance_before + amount

                # Update balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?
                    WHERE account_id = ?
                ''', (balance_after, account_id))

            # Record transaction
            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, description,
                 reference_id, processed_by)
                VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?)
            ''', (account_id, student_id, amount,
                  f'Housing Payment Refund - Ref: {original_ref}',
                  original_ref,
                  self.auth.current_user.get('username', 'System') if self.auth and self.auth.current_user else 'System'))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding refund to student account: {e}")
            return False

def _notify_finance_for_housing_refund(self, student_id: str, amount: float, method: str, refund_ref: str):
        """Record refund in unified refunds table for finance integration"""
        refund_row_id = None
        processed_by = (self.auth.current_user.get('username', 'System')
                        if self.auth and self.auth.current_user else 'System')
        try:
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
            from datetime import datetime
            with db_transaction() as conn:
                # Insert into unified refunds table with source_type='housing'
                try:
                    cur = conn.execute('''
                        INSERT INTO unified_refunds
                        (student_id, refund_reference, department, reference_id,
                         amount, refund_method, refund_date, processed_by, notes,
                         source_type, reference_type, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'housing', 'payment', 'processed')
                    ''', (
                        student_id,
                        refund_ref,
                        'Housing',
                        None,
                        amount,
                        method.lower().replace(' ', '_'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        processed_by,
                        'Housing Payment Refund',
                    ))
                    refund_row_id = cur.lastrowid
                    print(f"[Housing] Refund recorded in unified_refunds: {refund_ref}")
                except Exception as e:
                    print(f"[Housing] Error recording refund in unified_refunds: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error notifying finance system: {e}")

        # Auto-post to GL (cash has moved). Never raises.
        if refund_row_id is not None:
            try:
                from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

def _send_housing_refund_receipt(self, student_id: str, amount: float, method: str, payment_id: str):
        """Send refund receipt email to student"""
        if not EMAIL_SERVICE_AVAILABLE:
            return

        try:
            # Get student email
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (student_id,))
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                email = row[0]
                # Use email template
                try:
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    subject, body = render_template("housing_payment_refund_receipt", {
                        "payment_id": payment_id,
                        "student_id": student_id,
                        "amount": f"{amount:.2f}",
                        "method": method,
                        "refund_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                except Exception as template_error:
                    # Fallback to hardcoded email
                    subject = "Housing Payment Refund Receipt"
                    body = f"""Dear Student,

Your housing payment refund has been processed successfully.

REFUND RECEIPT
==============
Payment ID: {payment_id}
Student ID: {student_id}
Refund Amount: £{amount:.2f}
Refund Method: {method}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you have any questions about this refund, please contact the Housing Office.

Best regards,
University Housing Department
"""
                if send_email(email, subject, body):
                    print(f"[Housing] Refund receipt sent to {email}")
            else:
                print(f"[Housing] No email address on file for student {student_id}")
        except Exception as e:
            print(f"Error sending refund receipt: {e}")
