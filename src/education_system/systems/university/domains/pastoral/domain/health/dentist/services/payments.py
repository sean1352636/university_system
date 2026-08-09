import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from typing import Optional
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.pastoral.domain.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class PaymentServiceMixin:
        def _get_student_account_balance(self) -> Optional[float]:
            """Get student's finance account balance."""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (self.user_id,))
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
                    ''', (self.user_id,))
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
                    ''', (account_id, self.user_id, amount, balance_before, balance_after))
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
                result = TransactionManager.record_payment(
                    user_id=self.user_id,
                    patient_id=self.patient['patient_id'] if self.patient else 0,
                    amount=amount,
                    payment_method=payment_method,
                    transaction_type=transaction_type,
                    processed_by=self.user_id
                )
                if result:
                    # Record payment in central payments table for finance integration
                    payment_row_id = None
                    try:
                        from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                        with db_transaction() as conn:
                            # Insert into payments table for finance tracking
                            cur = conn.execute('''
                                INSERT INTO payments
                                (student_id, amount, payment_method, payment_date, status, notes, created_by)
                                VALUES (?, ?, ?, date("now"), ?, ?, ?)
                            ''', (self.user_id, amount, f'dentist_{payment_method}', 'completed',
                                  f"Dental: {description} (Ref: {result['reference']})", self.user_id))
                            payment_row_id = cur.lastrowid

                            # Auto-post to GL (never raises)
                            if payment_row_id is not None:
                                try:
                                    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                                    notify_ledger('payment', payment_row_id, posted_by=self.user_id or 'dentist')
                                except Exception as _e:
                                    import logging
                                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                            # Try to record revenue for finance reporting
                            try:
                                conn.execute('''
                                    INSERT INTO service_payments
                                    (service_type, user_id, amount, reference, description, payment_date)
                                    VALUES (?, ?, ?, ?, ?, date("now"))
                                ''', ('dental_clinic', self.user_id, amount, result['reference'], description))
                            except Exception:
                                pass  # Table may not exist
                    except Exception as e:
                        print(f"Finance integration error: {e}")

                    # Show payment success message
                    payment_method_display = {'cash': 'Cash', 'card': 'Card', 'student_account': 'Student Account'}.get(payment_method, payment_method)
                    messagebox.showinfo(_t("dentist.window_title"),
                                       f"Payment successful!\n\nAmount: GBP {amount:.2f}\nMethod: {payment_method_display}\nReference: {result['reference']}")

                    # Auto-send receipt email
                    if self.user_email:
                        patient_name = self.patient.get('user_name', self.user_id) if self.patient else self.user_id
                        patient_number = self.patient.get('patient_number', 'N/A') if self.patient else 'N/A'

                        # Render email from template
                        receipt_subject, receipt_body = render_template('commerce/dentist/payment_receipt', {
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
                print(f"Payment error: {e}")
            return None
