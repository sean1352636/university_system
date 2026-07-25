"""Payments & Refunds tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging
import csv

from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import get_connection, _t, TEMPLATE_AVAILABLE, render_template
from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management.dialogs.payment_dialog import PaymentDialog
from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management.dialogs.refund_dialog import RefundDialog


class PaymentsMixin:
    """Mixin providing payments and refunds tab functionality."""

    def setup_payments_tab(self):
        """Setup the payments and refunds management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.payments_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="Refund Payment", command=self.refund_selected_payment).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="View Details", command=self.view_payment_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_payments).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export to CSV", command=self.export_payments_csv).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.payments_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.payment_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.payment_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_payments)

        # Create treeview for payments
        columns = ("Pay ID", "Violation ID", "Amount", "Method", "Reference", "Date", "Status")
        self.payments_tree = ttk.Treeview(self.payments_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.payments_tree.heading(col, text=col)
            self.payments_tree.column(col, width=120)

        # Add scrollbars
        payments_scrolly = ttk.Scrollbar(self.payments_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
        payments_scrollx = ttk.Scrollbar(self.payments_frame, orient=tk.HORIZONTAL, command=self.payments_tree.xview)
        self.payments_tree.configure(yscrollcommand=payments_scrolly.set, xscrollcommand=payments_scrollx.set)

        # Pack treeview and scrollbars
        self.payments_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        payments_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        payments_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load payments data
        self.refresh_payments()

    def refresh_payments(self):
        """Refresh payments list"""
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    p.payment_id,
                    p.reference_id,
                    p.amount,
                    p.payment_method,
                    p.payment_reference,
                    p.payment_date,
                    CASE
                        WHEN r.refund_id IS NOT NULL THEN 'Refunded'
                        ELSE 'Paid'
                    END as status
                FROM payments p
                LEFT JOIN unified_refunds r ON CAST(p.payment_id AS TEXT) = r.reference_id
                    AND r.reference_type = 'payment'
                    AND r.source_type = 'parking'
                WHERE p.source_type = 'parking'
                ORDER BY p.payment_date DESC
            """)
            payments = cursor.fetchall()
            conn.close()

            for payment in payments:
                values = (
                    payment[0],
                    payment[1],
                    f"£{float(payment[2]):.2f}",
                    payment[3].replace('_', ' ').title(),
                    payment[4],
                    payment[5],
                    payment[6]
                )
                self.payments_tree.insert("", tk.END, values=values)

        except Exception as e:
            logging.error(f"Error refreshing payments: {e}")
            messagebox.showerror("Error", f"Failed to load payments: {str(e)}")

    def filter_payments(self, event=None):
        """Filter payments by search term"""
        search_term = self.payment_search_var.get().lower()

        all_items = self.payments_tree.get_children()

        for item in all_items:
            values = self.payments_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.payments_tree.item(item, tags=())
            else:
                self.payments_tree.item(item, tags=('hidden',))

        self.payments_tree.tag_configure('hidden', foreground='gray')

    def refund_selected_payment(self):
        """Refund selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund.")
            return

        values = self.payments_tree.item(selection[0])['values']

        # Check if already refunded
        if values[6] == 'Refunded':
            messagebox.showwarning("Already Refunded", "This payment has already been refunded.")
            return

        # Get full payment data
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payment_id, reference_id, amount, payment_method, payment_reference, payment_date, student_id
            FROM payments WHERE payment_id = ? AND source_type = 'parking'
        """, (values[0],))
        payment_data = cursor.fetchone()
        conn.close()

        if payment_data:
            self.process_refund(payment_data)

    def view_payment_details(self):
        """View payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view.")
            return

        values = self.payments_tree.item(selection[0])['values']

        # Get full details
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, v.license_plate, v.violation_type, v.fine_amount
            FROM payments p
            LEFT JOIN parking_violations v ON p.reference_id = v.violation_id
                AND p.reference_type = 'violation'
            WHERE p.payment_id = ? AND p.source_type = 'parking'
        """, (values[0],))
        payment = cursor.fetchone()
        conn.close()

        if payment:
            details = f"""Payment ID: {payment[0]}
Violation ID: {payment[1]}
License Plate: {payment[10]}
Violation Type: {payment[11]}
Amount: £{float(payment[2]):.2f}
Payment Method: {payment[3].replace('_', ' ').title()}
Payment Reference: {payment[4]}
Payment Date: {payment[5]}
Student ID: {payment[6] or 'N/A'}
Processed By: {payment[7] or 'N/A'}
Notes: {payment[8] or 'None'}
"""
            messagebox.showinfo("Payment Details", details)

    def export_payments_csv(self):
        """Export payments to CSV"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parking_payments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.payment_id, p.reference_id, p.amount, p.payment_method,
                       p.payment_reference, p.payment_date, p.student_id, p.processed_by
                FROM payments p
                WHERE p.source_type = 'parking'
                ORDER BY p.payment_date DESC
            """)
            payments = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Payment ID", "Violation ID", "Amount", "Method", "Reference",
                               "Date", "Student ID", "Processed By"])
                writer.writerows(payments)

            messagebox.showinfo("Export Successful", f"Payments exported to:\n{filename}")

        except Exception as e:
            logging.error(f"Error exporting payments: {e}")
            messagebox.showerror("Export Error", f"Failed to export payments: {str(e)}")

    def process_payment(self, violation_data):
        """Show payment dialog and process payment"""
        dialog = PaymentDialog(self.root, violation_data, self.current_user)
        self.root.wait_window(dialog.dialog)

        if not dialog.result:
            return

        try:
            from education_system.systems.university.infrastructure.database.db import transaction

            payment_ref = f"PARKING-PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            processed_by = self.current_user.get('username') if self.current_user else 'system'

            with transaction() as conn:
                cursor = conn.cursor()

                # Record payment
                cursor.execute("""
                    INSERT INTO payments
                    (source_type, reference_id, reference_type, amount, payment_method, payment_reference, student_id, processed_by, notes)
                    VALUES ('parking', ?, 'violation', ?, ?, ?, ?, ?, ?)
                """, (dialog.result['violation_id'], dialog.result['amount'], dialog.result['payment_method'],
                      payment_ref, dialog.result['student_id'], processed_by, 'Parking fine payment'))
                payment_row_id = cursor.lastrowid

                # Update violation status
                cursor.execute("""
                    UPDATE parking_violations
                    SET payment_status = 'Paid'
                    WHERE violation_id = ?
                """, (dialog.result['violation_id'],))

                # If student account, deduct amount
                if dialog.result['payment_method'] == 'student_account' and dialog.result['student_id']:
                    cursor.execute("""
                        UPDATE student_finance_accounts
                        SET balance = balance - ?
                        WHERE student_id = ?
                    """, (dialog.result['amount'], dialog.result['student_id']))

                    # Log in student finance transactions
                    cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                                 (dialog.result['student_id'],))
                    account_result = cursor.fetchone()
                    if account_result:
                        account_id, new_balance = account_result
                        cursor.execute("""
                            INSERT INTO transactions
                            (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                             reference_id, processed_by, created_at)
                            VALUES ('student_finance', ?, ?, 'debit', ?, ?, ?, ?, ?, ?)
                        """, (account_id, dialog.result['student_id'], dialog.result['amount'], new_balance,
                              f"Parking fine payment - {payment_ref}", payment_ref, processed_by,
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Add to finance system for central tracking
                try:
                    cursor.execute("""
                        INSERT INTO payments
                        (source_type, payment_reference, department, transaction_id, amount, payment_method, processed_by, notes)
                        VALUES ('finance', ?, ?, ?, ?, ?, ?, ?)
                    """, (payment_ref, 'Parking Services', dialog.result['violation_id'], dialog.result['amount'],
                          dialog.result['payment_method'], processed_by, 'Parking fine payment'))
                except Exception as e:
                    logging.warning(f"Could not log to payments (finance): {e}")

            # Auto-post the parking payment to GL (never raises). The second
            # INSERT above with source_type='finance' is a redundant log entry
            # and is intentionally NOT hooked to avoid double-posting.
            try:
                from education_system.systems.university.domain.finance.ledger import notify_ledger
                notify_ledger('payment', payment_row_id, posted_by=processed_by)
            except Exception as _e:
                logging.warning("ledger hook failed: %s", _e)

            # Send confirmation email
            self.send_payment_confirmation_email(dialog.result['violation_id'], dialog.result['amount'],
                                                dialog.result['payment_method'], payment_ref,
                                                dialog.result['student_id'], violation_data)

            # Refresh violations list
            self.refresh_violations()

            messagebox.showinfo("Payment Successful",
                              f"Payment processed successfully!\nReference: {payment_ref}")

        except Exception as e:
            logging.error(f"Error processing payment: {e}")
            messagebox.showerror("Payment Error", f"Failed to process payment: {str(e)}")

    def send_payment_confirmation_email(self, violation_id, amount, payment_method, payment_ref, student_id, violation_data):
        """Send payment confirmation email"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            # Get student/owner details
            if not student_id:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Try students table first
            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()

            if result and result[2]:
                student_name = f"{result[0]} {result[1]}"
                student_email = result[2]
            else:
                # Fall back to users table
                cursor.execute("SELECT first_name, last_name, email, username FROM users WHERE username = ? OR id = ?",
                             (student_id, student_id))
                result = cursor.fetchone()
                if result and result[2]:
                    student_name = f"{result[0] or ''} {result[1] or ''}".strip() or result[3]
                    student_email = result[2]
                else:
                    logging.warning(f"No email found for student {student_id}")
                    conn.close()
                    return

            conn.close()

            # Build email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('parking_fine_payment_confirmation', {
                        'student_name': student_name,
                        'fine_id': str(violation_id),
                        'amount': f"{amount:.2f}",
                        'payment_method': payment_method.replace('_', ' ').title(),
                        'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'payment_id': payment_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                subject = f"Parking Fine Payment Confirmation - {payment_ref}"
                body = f"""Dear {student_name},

This confirms your parking fine payment has been processed successfully.

Payment Details:
- Violation ID: {violation_id}
- Amount Paid: £{amount:.2f}
- Payment Method: {payment_method.replace('_', ' ').title()}
- Payment Reference: {payment_ref}
- Payment Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Violation Details:
- Type: {violation_data[2]}
- License Plate: {violation_data[1]}
- Date: {violation_data[3]}
- Location: {violation_data[6]}

Your violation status is now: PAID

Thank you for your prompt payment.

Parking Services
University Parking Management
"""

            send_email(recipient_email=student_email, subject=subject, body=body)
            logging.info(f"Payment confirmation email sent to {student_email}")

        except Exception as e:
            logging.error(f"Error sending payment confirmation email: {e}")

    def process_refund(self, payment_data):
        """Show refund dialog and process refund"""
        dialog = RefundDialog(self.root, payment_data, self.current_user)
        self.root.wait_window(dialog.dialog)

        if not dialog.result:
            return

        try:
            from education_system.systems.university.infrastructure.database.db import transaction

            refund_ref = f"PARKING-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            processed_by = self.current_user.get('username') if self.current_user else 'system'

            with transaction() as conn:
                cursor = conn.cursor()

                # Record refund in unified_refunds
                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, amount, refund_method, refund_reference,
                     student_id, processed_by, reason, refund_date, status)
                    VALUES ('parking', ?, 'payment', ?, ?, ?, ?, ?, ?, ?, 'processed')
                """, (str(dialog.result['payment_id']), dialog.result['amount'],
                      dialog.result['refund_method'], refund_ref, dialog.result['student_id'], processed_by,
                      f"Parking fine refund (violation: {dialog.result['violation_id']})",
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                refund_row_id = cursor.lastrowid

                # Update violation status
                cursor.execute("""
                    UPDATE parking_violations
                    SET payment_status = 'Refunded'
                    WHERE violation_id = ?
                """, (dialog.result['violation_id'],))

                # Update payment notes
                try:
                    cursor.execute("""
                        UPDATE payments
                        SET notes = notes || ' [REFUNDED: ' || ? || ']'
                        WHERE payment_id = ? AND source_type = 'parking'
                    """, (refund_ref, dialog.result['payment_id']))
                except Exception:
                    pass

                # If student account, add refund amount
                if dialog.result['refund_method'] == 'student_account' and dialog.result['student_id']:
                    cursor.execute("""
                        UPDATE student_finance_accounts
                        SET balance = balance + ?
                        WHERE student_id = ?
                    """, (dialog.result['amount'], dialog.result['student_id']))

                    # Log in student finance transactions
                    cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                                 (dialog.result['student_id'],))
                    account_result = cursor.fetchone()
                    if account_result:
                        account_id, new_balance = account_result
                        cursor.execute("""
                            INSERT INTO transactions
                            (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                             reference_id, processed_by, created_at)
                            VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                        """, (account_id, dialog.result['student_id'], dialog.result['amount'], new_balance,
                              f"Parking fine refund - {refund_ref}", refund_ref, processed_by,
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Auto-post refund to GL (cash has moved). Never raises.
            try:
                from education_system.systems.university.domain.finance.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by)
            except Exception as _e:
                logging.warning("ledger hook failed: %s", _e)

            # Send confirmation email
            self.send_refund_confirmation_email(dialog.result['violation_id'], dialog.result['amount'],
                                              dialog.result['refund_method'], refund_ref,
                                              dialog.result['student_id'], payment_data)

            # Refresh payments list
            if hasattr(self, 'refresh_payments'):
                self.refresh_payments()

            messagebox.showinfo("Refund Successful",
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logging.error(f"Error processing refund: {e}")
            messagebox.showerror("Refund Error", f"Failed to process refund: {str(e)}")

    def send_refund_confirmation_email(self, violation_id, amount, refund_method, refund_ref, student_id, payment_data):
        """Send refund confirmation email"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            if not student_id:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Try students table first
            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()

            if result and result[2]:
                student_name = f"{result[0]} {result[1]}"
                student_email = result[2]
            else:
                # Fall back to users table
                cursor.execute("SELECT first_name, last_name, email, username FROM users WHERE username = ? OR id = ?",
                             (student_id, student_id))
                result = cursor.fetchone()
                if result and result[2]:
                    student_name = f"{result[0] or ''} {result[1] or ''}".strip() or result[3]
                    student_email = result[2]
                else:
                    logging.warning(f"No email found for student {student_id}")
                    conn.close()
                    return

            # Get new balance if student account refund
            balance_text = ""
            if refund_method == 'student_account':
                cursor.execute("SELECT balance FROM student_finance_accounts WHERE student_id = ?", (student_id,))
                balance_result = cursor.fetchone()
                if balance_result:
                    balance_text = f"\nYour new student account balance is: £{balance_result[0]:.2f}\n"

            conn.close()

            # Build email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('parking_fine_refund_confirmation', {
                        'student_name': student_name,
                        'fine_id': str(violation_id),
                        'amount': f"{amount:.2f}",
                        'payment_method': refund_method.replace('_', ' ').title(),
                        'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                subject = f"Parking Fine Refund Confirmation - {refund_ref}"
                body = f"""Dear {student_name},

This confirms your parking fine refund has been processed successfully.

Refund Details:
- Violation ID: {violation_id}
- Refund Amount: £{amount:.2f}
- Refund Method: {refund_method.replace('_', ' ').title()}
- Refund Reference: {refund_ref}
- Refund Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Original Payment:
- Payment Reference: {payment_data[4]}
- Payment Date: {payment_data[5]}
{balance_text}
If you have any questions about this refund, please contact Parking Services.

Parking Services
University Parking Management
"""

            send_email(recipient_email=student_email, subject=subject, body=body)
            logging.info(f"Refund confirmation email sent to {student_email}")

        except Exception as e:
            logging.error(f"Error sending refund confirmation email: {e}")
