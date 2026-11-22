import logging

logger = logging.getLogger(__name__)

import csv
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog, filedialog
from datetime import datetime
from typing import Optional
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.health.domain.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS, billing_student_id
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class PaymentServiceMixin:
        def _billing_id(self) -> str:
            """The student number Finance bills for this login (the clinic
            keys patients on the username; finance accounts on the student number)."""
            if not getattr(self, '_billing_student_id', None):
                self._billing_student_id = billing_student_id(self.user_id)
            return self._billing_student_id

        def _get_student_account_balance(self) -> Optional[float]:
            """Get student's finance account balance."""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (self._billing_id(),))
                    row = cursor.fetchone()
                    return float(row[0]) if row else None
            except Exception as e:
                print(f"Error getting student balance: {e}")
                return None

        def _deduct_from_student_account(self, amount: float) -> bool:
            """Deduct amount from student's finance account."""
            try:
                from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                with db_transaction() as conn:
                    # Get account_id and balance
                    cursor = conn.execute('''
                        SELECT account_id, balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (self._billing_id(),))
                    row = cursor.fetchone()
                    if not row or float(row[1]) < amount:
                        return False

                    account_id = row[0]
                    balance_before = float(row[1])
                    balance_after = balance_before - amount

                    # Deduct from balance
                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = ?
                    ''', (balance_after, account_id))

                    # Record transaction with account_id
                    conn.execute('''
                        INSERT INTO transactions
                        (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after, description, created_at)
                        VALUES ('student_finance', ?, ?, 'debit', ?, ?, ?, 'Dental Clinic Payment', CURRENT_TIMESTAMP)
                    ''', (account_id, self._billing_id(), amount, balance_before, balance_after))
                return True
            except Exception as e:
                print(f"Error deducting from student account: {e}")
                return False

        def process_payment(self, transaction_type: str, amount: float, description: str):
            """Function 25: Process payment with payment method selection and finance integration."""
            # Show payment method selection dialog
            payment_method = self._show_payment_dialog(amount, description)
            if not payment_method:
                messagebox.showinfo(_t("dentist.window_title"), "Payment cancelled.")
                return None

            # Handle student account payment
            if payment_method == 'student_account':
                if not self._deduct_from_student_account(amount):
                    messagebox.showerror(_t("dentist.window_title"), "Failed to process student account payment. Insufficient funds or account error.")
                    return None

            try:
                # TransactionManager.record_payment writes the central payments
                # row and posts to the GL itself (shared with the dentist CLI).
                result = TransactionManager.record_payment(
                    user_id=self.user_id,
                    patient_id=self.patient['patient_id'] if self.patient else 0,
                    amount=amount,
                    payment_method=payment_method,
                    transaction_type=transaction_type,
                    processed_by=self.user_id,
                    description=description,
                )
                if not result:
                    # Nothing was recorded. A student-account debit already
                    # taken is put back, and the error is shown — never
                    # reported as a successful payment.
                    reversed_note = ""
                    if payment_method == 'student_account' and hasattr(self, '_add_refund_to_student_account'):
                        if self._add_refund_to_student_account(self.user_id, amount, 'payment not recorded'):
                            reversed_note = "\n\nThe student account debit has been reversed."
                        else:
                            reversed_note = ("\n\nThe student account was debited but the reversal "
                                             "failed — tell the Finance office.")
                    messagebox.showerror(_t("dentist.window_title"),
                                         "The payment could not be recorded with Finance." + reversed_note)
                    return None
                if result:
                    # TransactionManager.record_payment wrote the clinic
                    # transaction and the central payments row (payments.
                    # student_id = the student number) and posted the GL.
                    # (A service_payments insert here targeted a table that
                    # does not exist and swallowed the error; removed.)

                    # Show payment success message
                    payment_method_display = {'cash': 'Cash', 'card': 'Card', 'student_account': 'Student Account'}.get(payment_method, payment_method)
                    messagebox.showinfo(_t("dentist.window_title"),
                                       f"Payment successful!\n\nAmount: GBP {amount:.2f}\nMethod: {payment_method_display}\nReference: {result['reference']}")

                    # Auto-send receipt email
                    if self.user_email:
                        patient_name = self.patient.get('user_name', self.user_id) if self.patient else self.user_id
                        patient_number = self.patient.get('patient_number', 'N/A') if self.patient else 'N/A'

                        # Render email from template
                        receipt_subject, receipt_body = render_template('finance_commerce/commerce/dentist/payment_receipt', {
                            'patient_name': patient_name,
                            'reference': result['reference'],
                            'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                            'description': description,
                            'amount': f"GBP {amount:.2f}",
                            'payment_method': payment_method_display,
                            'patient_number': patient_number
                        })

                        # Fallback if template not found
                        if not receipt_subject or not receipt_body:
                            receipt_subject = "Dental Payment Receipt"
                            receipt_body = f"""Dear {patient_name},

    Thank you for your payment to the University Dental Clinic.

    PAYMENT RECEIPT
    ===============
    Reference: {result['reference']}
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

    Description: {description}
    Amount Paid: GBP {amount:.2f}
    Payment Method: {payment_method_display}
    Status: Completed

    Patient: {patient_name}
    Patient Number: {patient_number}

    If you have any questions about this payment, please contact the Dental Clinic.

    University Dental Clinic"""
                        if _send_dentist_email(self.user_email, receipt_subject, receipt_body):
                            print(f"Payment receipt automatically sent to {self.user_email}")

                    log_activity('payment', 'dentist_service',
                                amount=amount,
                                details={'type': transaction_type, 'ref': result['reference'],
                                        'user_id': self.user_id, 'payment_method': payment_method,
                                        'description': description})
                    return result
            except Exception as e:
                logger.exception("Dental payment failed")
                messagebox.showerror(_t("dentist.window_title"), f"Payment error: {e}")
            return None
