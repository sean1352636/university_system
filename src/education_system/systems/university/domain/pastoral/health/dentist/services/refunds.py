import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from typing import Optional
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domain.pastoral.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.interfaces.gui.pastoral.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class RefundServiceMixin:
        def _process_payment_refund(self):
            """Process a refund with cash/card/student account options."""
            selection = self.payments_tree.selection()
            if not selection:
                messagebox.showwarning(_t("dentist.msg_titles.no_selection"), "Please select a payment to refund")
                return

            try:
                values = self.payments_tree.item(selection[0])['values']
                if len(values) < 9:
                    messagebox.showerror(_t("dentist.msg_titles.data_error"), "Payment record is incomplete")
                    return

                transaction_id = values[0]
                reference = values[1]
                payment_date = values[2]
                user_id = values[3]
                patient_number = values[4]
                transaction_type = values[5]
                amount = float(values[6])
                payment_method = values[7]
                status = values[8]
            except (IndexError, ValueError) as e:
                messagebox.showerror(_t("dentist.msg_titles.error"), f"Error reading payment data: {e}")
                return

            if status == 'refunded':
                messagebox.showinfo(_t("dentist.msg_titles.refund_already_made"), "Refund already made")
                return

            # Confirm refund
            if not messagebox.askyesno(_t("dentist.msg_titles.confirm_refund"),
                                       f"Refund GBP {amount:.2f} to {user_id}?\n\n"
                                       f"Transaction ID: {transaction_id}\n"
                                       f"Reference: {reference}\n"
                                       f"Type: {transaction_type}"):
                return

            # Show refund method selection dialog
            refund_method = self._show_refund_method_dialog(amount, user_id)
            if not refund_method:
                return

            # Process based on method
            success = False
            if refund_method == 'Student Account':
                success = self._add_refund_to_student_account(user_id, amount, reference)
            else:
                # For cash/card, just record the refund
                success = True

            if success:
                # Update transaction status to refunded
                try:
                    from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                    with db_transaction() as conn:
                        conn.execute('''
                            UPDATE transactions
                            SET status = 'refunded'
                            WHERE source_type = 'dentist' AND transaction_id = ?
                        ''', (transaction_id,))

                        # Generate refund reference
                        import uuid
                        refund_ref = f"DENTIST-REFUND-{uuid.uuid4().hex[:12].upper()}"

                        # Record refund transaction
                        conn.execute('''
                            INSERT INTO transactions
                            (source_type, reference_number, customer_id, user_id, transaction_type, amount,
                             payment_method, status, processed_by)
                            SELECT 'dentist', ?, customer_id, user_id, ?, ?, ?, 'completed', ?
                            FROM transactions WHERE source_type = 'dentist' AND transaction_id = ?
                        ''', (refund_ref, f'refund_{transaction_type}', amount,
                              refund_method.lower().replace(' ', '_'), self.user_id, transaction_id))

                    # Send refund receipt email
                    self._send_dentist_refund_receipt(user_id, amount, refund_method, reference, refund_ref, patient_number)

                    # Notify finance GUI
                    self._notify_finance_for_refund(user_id, amount, refund_method, refund_ref)

                    messagebox.showinfo(_t("dentist.msg_titles.refund_processed"),
                                      f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                      f"Method: {refund_method}\n"
                                      f"Refund Reference: {refund_ref}")

                    self._refresh_payments_list()
                    log_activity('refund_processed', 'dentist',
                               details={'ref': refund_ref, 'amount': amount, 'method': refund_method})
                except Exception as e:
                    messagebox.showerror(_t("dentist.msg_titles.refund_error"), f"Failed to process refund: {e}")
            else:
                messagebox.showerror(_t("dentist.msg_titles.refund_failed"), "Failed to process student account refund")

        def _get_student_account_balance_by_user(self, user_id: str) -> Optional[float]:
            """Get student's finance account balance by user ID."""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (user_id,))
                    row = cursor.fetchone()
                    return float(row[0]) if row else None
            except Exception as e:
                print(f"Error getting student balance: {e}")
                return None

        def _add_refund_to_student_account(self, user_id: str, amount: float, payment_ref: str) -> bool:
            """Add refund amount to student's finance account."""
            try:
                from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                with db_transaction() as conn:
                    # Get account_id and balance
                    cursor = conn.execute('''
                        SELECT account_id, balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (user_id,))
                    row = cursor.fetchone()

                    if not row:
                        # Try to create account if it doesn't exist
                        conn.execute('''
                            INSERT INTO student_finance_accounts
                            (student_id, account_type, balance, account_status, created_at)
                            VALUES (?, 'standard', ?, 'active', CURRENT_TIMESTAMP)
                        ''', (user_id, amount))
                        account_id = conn.lastrowid
                        balance_before = 0
                        balance_after = amount
                    else:
                        account_id = row[0]
                        balance_before = float(row[1])
                        balance_after = balance_before + amount

                        # Add to balance
                        conn.execute('''
                            UPDATE student_finance_accounts
                            SET balance = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE account_id = ?
                        ''', (balance_after, account_id))

                    # Record transaction
                    conn.execute('''
                        INSERT INTO transactions
                        (source_type, account_id, student_id, transaction_type, amount, balance_before,
                         balance_after, description, created_at)
                        VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (account_id, user_id, amount, balance_before, balance_after,
                          f'Dental Clinic Refund - Payment: {payment_ref}'))

                return True
            except Exception as e:
                print(f"Error adding to student account: {e}")
                return False

        def _send_dentist_refund_receipt(self, user_id: str, amount: float, method: str,
                                        original_ref: str, refund_ref: str, patient_number: str):
            """Send refund receipt email to user."""
            try:
                # Get user email
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute("SELECT email FROM users WHERE username = ?", (user_id,))
                    row = cursor.fetchone()
                    email = row[0] if row and row[0] else None

                if email:
                    # Get balance text for student account
                    balance_text = ""
                    if method == 'Student Account':
                        balance = self._get_student_account_balance_by_user(user_id)
                        if balance is not None:
                            balance_text = f"Your new Student Finance Account balance: GBP {balance:.2f}"

                    # Render email from template
                    subject, body = render_template('commerce/dentist/refund_receipt', {
                        'patient_name': user_id,
                        'refund_ref': refund_ref,
                        'original_ref': original_ref,
                        'patient_number': patient_number,
                        'refund_amount': f"GBP {amount:.2f}",
                        'refund_method': method,
                        'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'balance_text': balance_text
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = "Dental Clinic Payment Refund Receipt"
                        body = f"""Dear {user_id},

    Your Dental Clinic payment refund has been processed successfully.

    REFUND RECEIPT
    ==============
    Refund Reference: {refund_ref}
    Original Payment Reference: {original_ref}
    Patient Number: {patient_number}
    Refund Amount: GBP {amount:.2f}
    Refund Method: {method}
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

    """
                        if balance_text:
                            body += f"{balance_text}\n"

                        body += """\nIf you have any questions about this refund, please contact the Dental Clinic.

    University Dental Clinic"""

                    if _send_dentist_email(email, subject, body):
                        print(f"[Dentist] Refund receipt sent to {email}")
                else:
                    print(f"[Dentist] No email found for user {user_id}")
            except Exception as e:
                print(f"Error sending refund receipt: {e}")
