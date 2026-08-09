import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domain.pastoral.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.interfaces.gui.pastoral.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class AppointmentServiceMixin:
        def book_appointment(self):
            """Function 8: Book an appointment with payment."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return
            if not self.dentist_var.get() or not self.appt_date_var.get() or not self.appt_time_var.get() or not self.treatment_type_var.get():
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.fill_required"))
                return

            dentist = next((d for d in DENTIST_STAFF if d['name'] == self.dentist_var.get()), None)
            treatment_key = next((k for k, v in TREATMENT_TYPES.items() if v['name'] == self.treatment_type_var.get()), 'checkup')
            treatment_info = TREATMENT_TYPES[treatment_key]
            treatment_fee = treatment_info['fee']
            treatment_name = treatment_info['name']

            # Show confirmation with exact fee
            confirm_msg = f"""Confirm Appointment Booking

    Treatment: {treatment_name}
    Date: {self.appt_date_var.get()}
    Time: {self.appt_time_var.get()}
    Dentist: {self.dentist_var.get()}

    Fee: GBP {treatment_fee:.2f}

    Proceed to payment?"""

            if not messagebox.askyesno(_t("dentist.window_title"), confirm_msg):
                return

            # Show payment method selection
            payment_method = self._show_payment_dialog(treatment_fee, f"Appointment - {treatment_name}")
            if not payment_method:
                messagebox.showinfo(_t("dentist.window_title"), "Booking cancelled.")
                return

            # Handle student account payment
            if payment_method == 'student_account':
                if not self._deduct_from_student_account(treatment_fee):
                    messagebox.showerror(_t("dentist.window_title"), "Payment failed. Insufficient funds or account error.")
                    return

            # Book the appointment
            result = AppointmentManager.book_appointment(
                patient_id=self.patient['patient_id'],
                dentist_id=dentist['id'],
                dentist_name=dentist['name'],
                appointment_date=self.appt_date_var.get(),
                appointment_time=self.appt_time_var.get(),
                treatment_type=treatment_key,
                created_by=self.user_id
            )

            if result:
                # Record the payment
                payment_result = TransactionManager.record_payment(
                    user_id=self.user_id,
                    patient_id=self.patient['patient_id'],
                    amount=treatment_fee,
                    payment_method=payment_method,
                    transaction_type='appointment',
                    processed_by=self.user_id
                )

                # Record in central payments table
                payment_row_id = None
                try:
                    from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                    with db_transaction() as conn:
                        cur = conn.execute('''
                            INSERT INTO payments
                            (student_id, amount, payment_method, payment_date, status, notes, created_by)
                            VALUES (?, ?, ?, date("now"), ?, ?, ?)
                        ''', (self.user_id, treatment_fee, f'dentist_{payment_method}', 'completed',
                              f"Dental Appointment: {treatment_name} (Ref: {result['appointment_ref']})", self.user_id))
                        payment_row_id = cur.lastrowid
                except Exception as e:
                    print(f"Finance integration error: {e}")

                # Auto-post to GL (never raises)
                if payment_row_id is not None:
                    try:
                        from education_system.systems.university.domain.finance.ledger import notify_ledger
                        notify_ledger('payment', payment_row_id, posted_by=self.user_id or 'dentist')
                    except Exception as _e:
                        import logging
                        logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                payment_method_display = {'cash': 'Cash', 'card': 'Card', 'student_account': 'Student Account'}.get(payment_method, payment_method)

                # Show success message
                messagebox.showinfo(_t("dentist.window_title"),
                    f"Appointment booked successfully!\n\nReference: {result['appointment_ref']}\nPayment: GBP {treatment_fee:.2f} ({payment_method_display})")

                self._refresh_appointments_list()

                # Send confirmation email with receipt
                if self.user_email:
                    patient_name = self.patient.get('user_name', self.user_id)
                    # Render email from template
                    subject, body = render_template('commerce/dentist/appointment_confirmation', {
                        'patient_name': patient_name,
                        'appointment_ref': result['appointment_ref'],
                        'appointment_date': self.appt_date_var.get(),
                        'appointment_time': self.appt_time_var.get(),
                        'dentist_name': self.dentist_var.get(),
                        'treatment_name': treatment_name,
                        'amount': f"GBP {treatment_fee:.2f}",
                        'payment_method': payment_method_display
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = "Dental Appointment Confirmation & Receipt"
                        body = f"""Dear {patient_name},

    Your dental appointment has been confirmed and payment received.

    APPOINTMENT DETAILS
    ===================
    Reference: {result['appointment_ref']}
    Date: {self.appt_date_var.get()}
    Time: {self.appt_time_var.get()}
    Dentist: {self.dentist_var.get()}
    Treatment: {treatment_name}

    PAYMENT RECEIPT
    ===============
    Amount: GBP {treatment_fee:.2f}
    Payment Method: {payment_method_display}
    Status: Paid

    Please arrive 10 minutes early for your appointment.

    If you need to reschedule or cancel, please contact us or use the Dental Clinic portal.

    University Dental Clinic"""
                    if _send_dentist_email(self.user_email, subject, body):
                        messagebox.showinfo(_t("dentist.window_title"), f"Confirmation email sent to {self.user_email}")
                    else:
                        messagebox.showwarning(_t("dentist.window_title"), f"Could not send confirmation email to {self.user_email}")
                else:
                    messagebox.showinfo(_t("dentist.window_title"), "No email address on file - confirmation email not sent.")

                log_activity('appointment_booked', 'dentist',
                            details={'ref': result['appointment_ref'], 'treatment': treatment_name,
                                    'fee': treatment_fee, 'payment_method': payment_method})
            else:
                # Refund if booking failed but payment was made
                if payment_method == 'student_account':
                    try:
                        from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                        with db_transaction() as conn:
                            conn.execute('''
                                UPDATE student_finance_accounts
                                SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP
                                WHERE student_id = ? AND account_status = 'active'
                            ''', (treatment_fee, self.user_id))
                    except Exception:
                        pass
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.booking_failed"))

        def cancel_appointment(self):
            """Function 9: Cancel an appointment."""
            selected = self.appointments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_appointment"))
                return
            if messagebox.askyesno(_t("dentist.window_title"), _t("dentist.confirm.cancel_appointment")):
                ref = self.appointments_tree.item(selected[0])['values'][0]
                appt = AppointmentManager.get_appointment(appointment_ref=ref)
                if appt and AppointmentManager.cancel_appointment(appt['appointment_id']):
                    messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.appointment_cancelled"))
                    self._refresh_appointments_list()
                    # Send cancellation email
                    if self.user_email:
                        patient_name = self.patient.get('user_name', self.user_id) if self.patient else self.user_id
                        # Render email from template
                        subject, body = render_template('commerce/dentist/appointment_cancelled', {
                            'patient_name': patient_name,
                            'appointment_ref': ref,
                            'appointment_date': appt['appointment_date'],
                            'appointment_time': appt['appointment_time'],
                            'dentist_name': appt['dentist_name']
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = "Dental Appointment Cancelled"
                            body = f"""Dear {patient_name},

    Your dental appointment has been cancelled.

    Cancelled Appointment Details:
    - Reference: {ref}
    - Date: {appt['appointment_date']}
    - Time: {appt['appointment_time']}
    - Dentist: {appt['dentist_name']}

    If you did not request this cancellation or would like to book a new appointment, please visit the Dental Clinic portal or contact us.

    University Dental Clinic"""
                        if _send_dentist_email(self.user_email, subject, body):
                            print(f"Cancellation email sent to {self.user_email}")

        def reschedule_appointment(self):
            """Function 10: Reschedule an appointment."""
            selected = self.appointments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_appointment"))
                return
            ref = self.appointments_tree.item(selected[0])['values'][0]
            appt = AppointmentManager.get_appointment(appointment_ref=ref)
            if not appt:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.select_appointment"))
                return
            new_date = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.new_date"),
                                              initialvalue=appt['appointment_date'])
            if not new_date:
                return
            new_time = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.new_time"),
                                              initialvalue=appt['appointment_time'])
            if not new_time:
                return
            result = AppointmentManager.reschedule_appointment(appt['appointment_id'], new_date, new_time)
            if result:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.appointment_rescheduled"))
                self._refresh_appointments_list()
                # Send reschedule email
                if self.user_email:
                    patient_name = self.patient.get('user_name', self.user_id) if self.patient else self.user_id
                    # Render email from template
                    subject, body = render_template('commerce/dentist/appointment_rescheduled', {
                        'patient_name': patient_name,
                        'old_date': result['old_date'],
                        'old_time': result['old_time'],
                        'appointment_ref': ref,
                        'new_date': result['new_date'],
                        'new_time': result['new_time'],
                        'dentist_name': appt['dentist_name']
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = "Dental Appointment Rescheduled"
                        body = f"""Dear {patient_name},

    Your dental appointment has been rescheduled.

    Previous Appointment:
    - Date: {result['old_date']}
    - Time: {result['old_time']}

    New Appointment:
    - Reference: {ref}
    - Date: {result['new_date']}
    - Time: {result['new_time']}
    - Dentist: {appt['dentist_name']}

    Please arrive 10 minutes early for your appointment.

    If you have any questions, please contact us or use the Dental Clinic portal.

    University Dental Clinic"""
                    if _send_dentist_email(self.user_email, subject, body):
                        print(f"Reschedule email sent to {self.user_email}")
            else:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.booking_failed"))

        def send_appointment_reminder(self):
            """Function 20: Send appointment reminders."""
            if not EMAIL_AVAILABLE:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.email_unavailable"))
                return
            upcoming = ReportManager.get_upcoming_appointments(days=2)
            sent = 0
            for appt in upcoming:
                if appt.get('user_email'):
                    subject = "Dental Appointment Reminder"
                    body = f"Dear {appt['user_name']},\n\nThis is a reminder of your dental appointment:\nDate: {appt['appointment_date']}\nTime: {appt['appointment_time']}\nDentist: {appt['dentist_name']}\n\nPlease arrive 10 minutes early."
                    if send_email(appt['user_email'], subject, body):
                        sent += 1
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.reminders_sent").format(count=sent))

