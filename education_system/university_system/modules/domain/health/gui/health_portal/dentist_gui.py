"""
Dentist/Dental Clinic GUI

Provides a comprehensive GUI for university dental services including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from typing import Optional, Dict, List

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Authentication imports
try:
    from education_system.university_system.infrastructure.shared_context import get_auth, _DummyAuth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None
    _DummyAuth = None

from education_system.university_system.modules.domain.dentist.services.dentist_core import (
    PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager,
    TransactionManager, ReportManager, init_dentist_db,
    TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
)

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs): return False
    render_template = None


def _send_dentist_email(recipient: str, subject: str, body: str, show_success: bool = False) -> bool:
    """Helper function to send emails with proper error handling and logging."""
    if not EMAIL_AVAILABLE:
        print(f"[Dentist] Email service not available - would send to {recipient}: {subject}")
        return False
    if not recipient:
        print(f"[Dentist] No recipient email provided for: {subject}")
        return False
    try:
        result = send_email(recipient, subject, body)
        if result:
            log_activity('email_sent', 'dentist', details={'to': recipient, 'subject': subject})
            print(f"[Dentist] Email sent successfully to {recipient}: {subject}")
            return True
        else:
            print(f"[Dentist] Email send returned False for {recipient}: {subject}")
            return False
    except Exception as e:
        print(f"[Dentist] Email send error for {recipient}: {e}")
        log_activity('email_failed', 'dentist', details={'to': recipient, 'subject': subject, 'error': str(e)})
        return False


class DentistGUI:
    """Dentist/Dental Clinic GUI with 25 functions."""

    def __init__(self, root, auth=None):
        """Function 1: Initialize the Dentist GUI."""
        self.root = root
        self._is_embedded = not isinstance(root, (tk.Tk, tk.Toplevel))
        self.auth = auth

        # Try to get auth from shared context if not provided
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check authentication
        if not self._check_authentication():
            return
        self.user_id = self.current_user.get('username', 'unknown')
        self.user_role = self.current_user.get('role', 'student')
        self.user_email = self.current_user.get('email', '')

        # If email not in current_user, fetch from database
        if not self.user_email:
            self.user_email = self._get_user_email()

        self.current_report = None
        self.patient = None
        self._init_database()
        self._load_patient()
        self.create_widgets()

    def _get_user_email(self) -> str:
        """Fetch user email from the users table."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE username = ?",
                    (self.user_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception as e:
            print(f"Error fetching user email: {e}")
        return ''

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("dentist.window_title"),
                "You must be logged in to access the Dentist module.\n\n"
                "Please log in through the main GUI first."
            )
            self.root.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("dentist.window_title"),
                "You must be logged in to access the Dentist module.\n\n"
                "Please launch this module from the main GUI after logging in."
            )
            self.root.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("dentist.window_title"),
                "You are not currently logged in.\n\n"
                "Please log in through the main GUI to access this module."
            )
            self.root.destroy()
            return False

        # Store current user info
        self.current_user = self.auth.current_user
        return True

    def create_widgets(self):
        """Function 2: Create all GUI widgets."""
        if not self._is_embedded:
            self.root.title(_t("dentist.window_title"))
        header = ttk.Frame(self.root, padding="10")
        header.pack(fill=tk.X)
        ttk.Label(header, text=_t("dentist.title"), font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header, text=f"User: {self.user_id} | Role: {self.user_role}").pack(side=tk.RIGHT)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.create_appointments_tab()
        self.create_treatments_tab()
        self.create_records_tab()
        if self.user_role in ('admin', 'staff'):
            self.create_admin_tab()
            self.create_payments_refunds_tab()
        footer = ttk.Frame(self.root, padding="10")
        footer.pack(fill=tk.X)
        ttk.Button(footer, text=_t("common.refresh"), command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text=_t("common.close"), command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Function 3: Initialize database tables."""
        try:
            if not init_dentist_db():
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.db_init"))
        except Exception as e:
            messagebox.showwarning(_t("dentist.window_title"), f"DB init error: {e}")

    def return_to_homescreen(self):
        """Function 4: Close window."""
        self.root.destroy()

    def refresh_all_data(self):
        """Function 5: Refresh all data."""
        self._load_patient()
        self._refresh_appointments_list()
        self._refresh_treatments_list()
        messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.data_refreshed"))

    def _load_patient(self):
        self.patient = PatientManager.get_patient(user_id=self.user_id)

    def create_appointments_tab(self):
        """Function 6: Create appointments tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("dentist.tabs.appointments"))
        # Patient info
        patient_frame = ttk.LabelFrame(tab, text=_t("dentist.patient_info"), padding="10")
        patient_frame.pack(fill=tk.X, pady=(0, 10))
        self.patient_info_label = ttk.Label(patient_frame, text="")
        self.patient_info_label.pack(side=tk.LEFT)
        ttk.Button(patient_frame, text=_t("dentist.btn.register"), command=self.register_patient).pack(side=tk.RIGHT)
        # Booking frame
        booking_frame = ttk.LabelFrame(tab, text=_t("dentist.book_appointment"), padding="10")
        booking_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(booking_frame, text=_t("dentist.labels.dentist") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.dentist_var = tk.StringVar()
        dentist_names = [d['name'] for d in DENTIST_STAFF]
        ttk.Combobox(booking_frame, textvariable=self.dentist_var, values=dentist_names, width=30).grid(row=0, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("dentist.labels.date") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.appt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(booking_frame, textvariable=self.appt_date_var, width=33).grid(row=1, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("dentist.labels.time") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.appt_time_var = tk.StringVar()
        ttk.Combobox(booking_frame, textvariable=self.appt_time_var, values=APPOINTMENT_SLOTS, width=30).grid(row=2, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("dentist.labels.treatment_type") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.treatment_type_var = tk.StringVar()
        treatment_names = [t['name'] for t in TREATMENT_TYPES.values()]
        ttk.Combobox(booking_frame, textvariable=self.treatment_type_var, values=treatment_names, width=30).grid(row=3, column=1, pady=2)
        ttk.Button(booking_frame, text=_t("dentist.btn.book"), command=self.book_appointment).grid(row=4, column=1, pady=10)
        # Appointments list
        list_frame = ttk.LabelFrame(tab, text=_t("dentist.my_appointments"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('ref', 'date', 'time', 'dentist', 'treatment', 'status')
        self.appointments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.appointments_tree.heading(col, text=col.title())
            self.appointments_tree.column(col, width=90)
        self.appointments_tree.pack(fill=tk.BOTH, expand=True)
        action_frame = ttk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(action_frame, text=_t("dentist.btn.cancel"), command=self.cancel_appointment).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text=_t("dentist.btn.reschedule"), command=self.reschedule_appointment).pack(side=tk.LEFT, padx=2)
        self._refresh_patient_info()
        self._refresh_appointments_list()

    def register_patient(self):
        """Function 7: Register as a patient."""
        if self.patient:
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.already_registered"))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.btn.register"))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=_t("dentist.labels.phone") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=phone_var, width=30).grid(row=0, column=1, pady=2)
        ttk.Label(frame, text=_t("dentist.labels.dob") + " (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=2)
        dob_var = tk.StringVar()
        ttk.Entry(frame, textvariable=dob_var, width=30).grid(row=1, column=1, pady=2)
        ttk.Label(frame, text=_t("dentist.labels.emergency_contact") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        emergency_var = tk.StringVar()
        ttk.Entry(frame, textvariable=emergency_var, width=30).grid(row=2, column=1, pady=2)
        ttk.Label(frame, text=_t("dentist.labels.allergies") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        allergies_var = tk.StringVar()
        ttk.Entry(frame, textvariable=allergies_var, width=30).grid(row=3, column=1, pady=2)
        def save():
            result = PatientManager.register_patient(user_id=self.user_id, user_name=self.user_id, user_email=self.user_email, user_phone=phone_var.get(), date_of_birth=dob_var.get(), emergency_contact=emergency_var.get(), allergies=allergies_var.get())
            if result:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.registered").format(patient_number=result['patient_number']))
                self._load_patient()
                self._refresh_patient_info()
                dialog.destroy()
            else:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.registration_failed"))
        ttk.Button(frame, text=_t("common.save"), command=save).grid(row=4, column=1, pady=20)

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
            try:
                from education_system.university_system.infrastructure.database.db import transaction as db_transaction
                with db_transaction() as conn:
                    conn.execute('''
                        INSERT INTO payments
                        (student_id, amount, payment_method, payment_date, status, notes, created_by)
                        VALUES (?, ?, ?, date("now"), ?, ?, ?)
                    ''', (self.user_id, treatment_fee, f'dentist_{payment_method}', 'completed',
                          f"Dental Appointment: {treatment_name} (Ref: {result['appointment_ref']})", self.user_id))
            except Exception as e:
                print(f"Finance integration error: {e}")

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
                    from education_system.university_system.infrastructure.database.db import transaction as db_transaction
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

    def _refresh_patient_info(self):
        if self.patient:
            info = f"Patient #: {self.patient['patient_number']} | Last Visit: {self.patient.get('last_visit', 'Never')}"
        else:
            info = _t("dentist.messages.not_registered")
        self.patient_info_label.config(text=info)

    def _refresh_appointments_list(self):
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)
        if self.patient:
            for a in AppointmentManager.get_patient_appointments(self.patient['patient_id']):
                self.appointments_tree.insert('', tk.END, values=(a['appointment_ref'], a['appointment_date'], a['appointment_time'], a['dentist_name'], a['treatment_type'], a['status']))

    def create_treatments_tab(self):
        """Function 11: Create treatments tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("dentist.tabs.treatments"))

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text=_t("dentist.btn.filter_treatments"), padding="5")
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("dentist.labels.treatment_type_colon")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.treatment_filter_var = tk.StringVar(value="All")
        treatment_types = ["All"] + [t['name'] for t in TREATMENT_TYPES.values()]
        ttk.Combobox(filter_frame, textvariable=self.treatment_filter_var, values=treatment_types, width=25).grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text=_t("dentist.labels.payment_status")).grid(row=0, column=2, sticky=tk.W, padx=5)
        self.payment_filter_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self.payment_filter_var, values=["All", "paid", "pending"], width=15).grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text=_t("dentist.btn.apply_filter"), command=self._refresh_treatments_list).grid(row=0, column=4, padx=5)
        ttk.Button(filter_frame, text=_t("dentist.btn.clear"), command=self._clear_treatment_filters).grid(row=0, column=5, padx=5)

        # Treatment history
        history_frame = ttk.LabelFrame(tab, text=_t("dentist.treatment_history"), padding="5")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        columns = ('id', 'date', 'treatment', 'dentist', 'fee', 'status', 'follow_up')
        self.treatments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=10)
        self.treatments_tree.heading('id', text=_t('dentist.columns.id'))
        self.treatments_tree.heading('date', text=_t('dentist.columns.date'))
        self.treatments_tree.heading('treatment', text=_t('dentist.columns.treatment'))
        self.treatments_tree.heading('dentist', text=_t('dentist.columns.dentist'))
        self.treatments_tree.heading('fee', text=_t('dentist.columns.fee_gbp'))
        self.treatments_tree.heading('status', text=_t('dentist.columns.payment_status'))
        self.treatments_tree.heading('follow_up', text=_t('dentist.columns.follow_up'))

        self.treatments_tree.column('id', width=50)
        self.treatments_tree.column('date', width=100)
        self.treatments_tree.column('treatment', width=150)
        self.treatments_tree.column('dentist', width=120)
        self.treatments_tree.column('fee', width=80)
        self.treatments_tree.column('status', width=100)
        self.treatments_tree.column('follow_up', width=120)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.treatments_tree.yview)
        self.treatments_tree.configure(yscrollcommand=scrollbar.set)
        self.treatments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to view details
        self.treatments_tree.bind('<Double-1>', lambda e: self.view_treatment_details_advanced())

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text=_t("dentist.btn.view_full_details"), command=self.view_treatment_details_advanced).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.pay"), command=self.process_treatment_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.request_treatment"), command=self.request_treatment_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.schedule_follow_up"), command=self.schedule_followup_from_treatment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.export_csv"), command=self.export_treatments_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.view_prescriptions"), command=self.view_prescriptions).pack(side=tk.LEFT, padx=5)
        self._refresh_treatments_list()

    def view_treatment_details(self):
        """Function 12: View treatment details (simple)."""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
            return
        values = self.treatments_tree.item(selected[0])['values']
        details = f"Treatment ID: {values[0]}\nDate: {values[1]}\nTreatment: {values[2]}\nDentist: {values[3]}\nFee: GBP {values[4]}\nPayment Status: {values[5]}\nFollow-up: {values[6]}"
        messagebox.showinfo(_t("dentist.treatment_details"), details)

    def view_treatment_details_advanced(self):
        """View detailed treatment information with notes and prescriptions."""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
            return

        try:
            values = self.treatments_tree.item(selected[0])['values']
            treatment_id = values[0]

            # Fetch full treatment details from database
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM dentist_treatments WHERE treatment_id = ?
                ''', (treatment_id,))
                treatment = cursor.fetchone()

                if not treatment:
                    messagebox.showerror(_t("dentist.msg_titles.error"), "Treatment details not found")
                    return

            # Create details dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.labels.treatment_details"))
            dialog.geometry("600x500")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("dentist.labels.treatment_details"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

            # Details frame
            details_frame = ttk.LabelFrame(main_frame, text=_t("dentist.labels.treatment_information"), padding="10")
            details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            details_text = tk.Text(details_frame, height=20, wrap=tk.WORD, font=('Arial', 10))
            details_text.pack(fill=tk.BOTH, expand=True)

            # Format treatment details
            info = f"""Treatment ID: {treatment['treatment_id']}
Date: {treatment['treatment_date']}
Treatment Type: {treatment['treatment_type']}
Dentist: {treatment['dentist_name']}
Fee: GBP {treatment['fee']:.2f}
Payment Status: {treatment['payment_status']}

{'='*50}
TREATMENT DETAILS
{'='*50}
Tooth Number: {treatment['tooth_number'] if treatment['tooth_number'] else 'N/A'}
Description: {treatment['description'] if treatment['description'] else 'No description provided'}

Notes: {treatment['notes'] if treatment['notes'] else 'No notes recorded'}

{'='*50}
FOLLOW-UP INFORMATION
{'='*50}
Follow-up Required: {'Yes' if treatment['follow_up_required'] else 'No'}
Follow-up Date: {treatment['follow_up_date'] if treatment['follow_up_date'] else 'Not scheduled'}
"""
            details_text.insert('1.0', info)
            details_text.config(state='disabled')

            # Buttons frame
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=(10, 0))

            ttk.Button(btn_frame, text=_t("dentist.btn.close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

            if treatment['follow_up_required'] and not treatment['follow_up_date']:
                ttk.Button(btn_frame, text=_t("dentist.btn.schedule_follow_up"),
                          command=lambda: [dialog.destroy(), self.schedule_followup_from_treatment()]).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to load treatment details: {e}")

    def request_treatment_dialog(self):
        """Request a new treatment/appointment."""
        if not self.patient:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.msg_titles.treatment_request"))
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("dentist.btn.request_treatment_appt"), font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Treatment type
        ttk.Label(main_frame, text=_t("dentist.labels.treatment_type_colon")).pack(anchor=tk.W, pady=(5, 0))
        treatment_var = tk.StringVar()
        treatment_names = [t['name'] for t in TREATMENT_TYPES.values()]
        treatment_combo = ttk.Combobox(main_frame, textvariable=treatment_var, values=treatment_names, width=40)
        treatment_combo.pack(fill=tk.X, pady=(0, 10))

        # Preferred date
        ttk.Label(main_frame, text=_t("dentist.labels.preferred_date")).pack(anchor=tk.W, pady=(5, 0))
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=date_var, width=43).pack(fill=tk.X, pady=(0, 10))

        # Dentist preference
        ttk.Label(main_frame, text=_t("dentist.labels.preferred_dentist")).pack(anchor=tk.W, pady=(5, 0))
        dentist_var = tk.StringVar()
        dentist_names = ["Any"] + [d['name'] for d in DENTIST_STAFF]
        ttk.Combobox(main_frame, textvariable=dentist_var, values=dentist_names, width=40).pack(fill=tk.X, pady=(0, 10))

        # Notes
        ttk.Label(main_frame, text=_t("dentist.labels.additional_notes")).pack(anchor=tk.W, pady=(5, 0))
        notes_text = tk.Text(main_frame, height=5, wrap=tk.WORD)
        notes_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        def submit_request():
            if not treatment_var.get():
                messagebox.showerror(_t("dentist.msg_titles.error"), "Please select a treatment type")
                return

            # For now, redirect to appointment booking
            messagebox.showinfo(_t("dentist.msg_titles.treatment_request"),
                              f"Treatment request noted:\n\n"
                              f"Type: {treatment_var.get()}\n"
                              f"Preferred Date: {date_var.get()}\n"
                              f"Preferred Dentist: {dentist_var.get() or 'Any'}\n\n"
                              f"Please proceed to the Appointments tab to book your appointment.")
            dialog.destroy()

            # Switch to appointments tab
            self.notebook.select(0)  # Assuming appointments is first tab

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("dentist.btn.submit_request"), command=submit_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def schedule_followup_from_treatment(self):
        """Schedule a follow-up appointment from a treatment."""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("dentist.window_title"), "Please select a treatment that requires follow-up")
            return

        try:
            values = self.treatments_tree.item(selected[0])['values']
            treatment_id = values[0]
            treatment_type = values[2]

            # Check if follow-up is required
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT follow_up_required, follow_up_date FROM dentist_treatments
                    WHERE treatment_id = ?
                ''', (treatment_id,))
                result = cursor.fetchone()

                if not result or not result['follow_up_required']:
                    messagebox.showinfo(_t("dentist.msg_titles.follow_up"), "This treatment does not require a follow-up appointment")
                    return

                if result['follow_up_date']:
                    messagebox.showinfo(_t("dentist.msg_titles.follow_up"), f"Follow-up already scheduled for: {result['follow_up_date']}")
                    return

            # Show scheduling dialog
            messagebox.showinfo(_t("dentist.msg_titles.schedule_follow_up"),
                              f"Follow-up required for: {treatment_type}\n\n"
                              f"Please use the Appointments tab to schedule your follow-up appointment.")

            # Switch to appointments tab
            self.notebook.select(0)

        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to check follow-up status: {e}")

    def export_treatments_csv(self):
        """Export treatment history to CSV."""
        if not self.patient:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
            return

        try:
            from tkinter import filedialog
            import csv

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"treatments_{self.user_id}_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Treatment ID', 'Date', 'Treatment Type', 'Dentist',
                                   'Fee (GBP)', 'Payment Status', 'Follow-up Required'])

                    for item in self.treatments_tree.get_children():
                        values = self.treatments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo(_t("dentist.msg_titles.export_successful"), f"Treatments exported to:\n{filepath}")
                log_activity('export', 'dentist_treatments', user_id=self.user_id,
                           details={'file': filepath})

        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.export_error"), f"Failed to export treatments: {e}")

    def process_treatment_payment(self):
        """Function 13: Process payment for a treatment."""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
            return
        values = self.treatments_tree.item(selected[0])['values']
        # Updated: values are now (id, date, treatment_display_name, dentist, fee, status, follow_up)
        if values[5] == 'paid':
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.already_paid"))
            return
        try:
            amount = float(values[4])
        except (ValueError, TypeError):
            amount = 0
        treatment_id = values[0]

        if messagebox.askyesno(_t("dentist.window_title"), f"Process payment of GBP {amount:.2f}?"):
            # Process the payment
            result = self.process_payment('treatment', amount, f"Dental treatment - {values[2]}")

            if result:
                # Update treatment payment status in database
                try:
                    from education_system.university_system.infrastructure.database.db import transaction as db_transaction
                    with db_transaction() as conn:
                        conn.execute('''
                            UPDATE dentist_treatments
                            SET payment_status = 'paid'
                            WHERE treatment_id = ?
                        ''', (treatment_id,))
                except Exception as e:
                    print(f"Error updating treatment payment status: {e}")

                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.payment_processed"))
                self._refresh_treatments_list()

    def view_prescriptions(self):
        """Function 14: View prescriptions."""
        if not self.patient:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
            return
        prescriptions = PrescriptionManager.get_patient_prescriptions(self.patient['patient_id'])
        if not prescriptions:
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.no_prescriptions"))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.prescriptions"))
        dialog.geometry("600x400")
        text = tk.Text(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for p in prescriptions:
            text.insert(tk.END, f"\n=== {p['prescribed_date']} ===\n")
            text.insert(tk.END, f"Medication: {p['medication']}\nDosage: {p['dosage']}\nFrequency: {p['frequency']}\nDuration: {p['duration']}\nInstructions: {p.get('instructions', 'N/A')}\n")

    def _refresh_treatments_list(self):
        """Refresh treatments list with filtering."""
        for item in self.treatments_tree.get_children():
            self.treatments_tree.delete(item)
        if not self.patient:
            return

        treatments = TreatmentManager.get_patient_treatments(self.patient['patient_id'])

        if not treatments:
            # Show helpful message when no treatments
            self.treatments_tree.insert('', tk.END, values=(
                'N/A',
                '',
                'No treatment history yet',
                'Treatments are recorded after appointments are completed',
                '',
                '',
                'Check Appointments tab'
            ))
            return

        # Apply filters
        treatment_filter = self.treatment_filter_var.get()
        payment_filter = self.payment_filter_var.get()

        filtered_count = 0
        for t in treatments:
            # Get display name for treatment type
            treatment_key = t['treatment_type']
            treatment_display = TREATMENT_TYPES.get(treatment_key, {}).get('name', treatment_key)

            # Filter by treatment type (compare display names)
            if treatment_filter != "All" and treatment_display != treatment_filter:
                continue

            # Filter by payment status
            if payment_filter != "All" and t['payment_status'] != payment_filter:
                continue

            filtered_count += 1

            # Determine follow-up status
            follow_up = "Required" if t.get('follow_up_required') else "None"
            if t.get('follow_up_date'):
                follow_up = f"Due: {t['follow_up_date']}"

            self.treatments_tree.insert('', tk.END, values=(
                t.get('treatment_id', 'N/A'),
                t['treatment_date'],
                treatment_display,  # Show display name instead of key
                t['dentist_name'],
                f"{t['fee']:.2f}",
                t['payment_status'],
                follow_up
            ))

        # Show message if filters resulted in no results
        if filtered_count == 0 and (treatment_filter != "All" or payment_filter != "All"):
            self.treatments_tree.insert('', tk.END, values=(
                'N/A',
                '',
                'No treatments match current filters',
                'Try clearing filters or selecting different options',
                '',
                '',
                ''
            ))

    def _clear_treatment_filters(self):
        """Clear all treatment filters."""
        self.treatment_filter_var.set("All")
        self.payment_filter_var.set("All")
        self._refresh_treatments_list()

    def create_records_tab(self):
        """Function 15: Create records tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("dentist.tabs.records"))
        # Patient profile
        profile_frame = ttk.LabelFrame(tab, text=_t("dentist.my_profile"), padding="10")
        profile_frame.pack(fill=tk.X, pady=(0, 10))
        self.profile_text = tk.Text(profile_frame, height=8, wrap=tk.WORD)
        self.profile_text.pack(fill=tk.X)
        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(action_frame, text=_t("dentist.btn.update_profile"), command=self.update_patient_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("dentist.btn.view_history"), command=self.view_dental_history).pack(side=tk.LEFT, padx=5)
        # Available treatments
        treatments_frame = ttk.LabelFrame(tab, text=_t("dentist.available_treatments"), padding="5")
        treatments_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('treatment', 'duration', 'fee')
        tree = ttk.Treeview(treatments_frame, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col.title())
        for key, t in TREATMENT_TYPES.items():
            tree.insert('', tk.END, values=(t['name'], f"{t['duration']} min", f"GBP {t['fee']:.2f}"))
        tree.pack(fill=tk.BOTH, expand=True)
        self._refresh_profile()

    def update_patient_profile(self):
        """Function 16: Update patient profile."""
        if not self.patient:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
            return
        phone = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.new_phone"), initialvalue=self.patient.get('user_phone', ''))
        if phone:
            PatientManager.update_patient(self.patient['patient_id'], user_phone=phone)
            self._load_patient()
            self._refresh_profile()
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.profile_updated"))

    def view_dental_history(self):
        """Function 17: View complete dental history."""
        if not self.patient:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
            return
        treatments = TreatmentManager.get_patient_treatments(self.patient['patient_id'])
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.dental_history"))
        dialog.geometry("700x500")
        columns = ('date', 'treatment', 'dentist', 'notes')
        tree = ttk.Treeview(dialog, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col.title())
        for t in treatments:
            tree.insert('', tk.END, values=(t['treatment_date'], t['treatment_type'], t['dentist_name'], t.get('notes', '')))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _refresh_profile(self):
        self.profile_text.delete("1.0", tk.END)
        if self.patient:
            profile = f"""Patient Number: {self.patient['patient_number']}
Name: {self.patient['user_name']}
Email: {self.patient.get('user_email', 'N/A')}
Phone: {self.patient.get('user_phone', 'N/A')}
Date of Birth: {self.patient.get('date_of_birth', 'N/A')}
Allergies: {self.patient.get('allergies', 'None recorded')}
Last Visit: {self.patient.get('last_visit', 'Never')}"""
            self.profile_text.insert("1.0", profile)
        else:
            self.profile_text.insert("1.0", _t("dentist.messages.not_registered"))

    def create_admin_tab(self):
        """Function 18: Create admin tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("dentist.tabs.admin"))
        # Today's appointments
        today_frame = ttk.LabelFrame(tab, text=_t("dentist.todays_appointments"), padding="5")
        today_frame.pack(fill=tk.X, pady=(0, 10))
        columns = ('time', 'patient', 'dentist', 'treatment', 'status')
        self.today_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=6)
        for col in columns:
            self.today_tree.heading(col, text=col.title())
            self.today_tree.column(col, width=100)
        self.today_tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(today_frame, text=_t("dentist.btn.refresh_today"), command=self._refresh_today).pack(pady=5)
        # Reports
        report_frame = ttk.LabelFrame(tab, text=_t("dentist.reports.title"), padding="10")
        report_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(report_frame, text=_t("dentist.labels.report_type") + ":").grid(row=0, column=0, sticky=tk.W)
        self.report_type_var = tk.StringVar(value='daily')
        ttk.Combobox(report_frame, textvariable=self.report_type_var, values=['daily', 'monthly'], width=20).grid(row=0, column=1, padx=5)
        ttk.Button(report_frame, text=_t("dentist.btn.generate_report"), command=self.generate_admin_report).grid(row=0, column=2, padx=5)
        ttk.Button(report_frame, text=_t("dentist.btn.email_report"), command=self.email_admin_report).grid(row=0, column=3, padx=5)
        # Report output
        output_frame = ttk.LabelFrame(tab, text=_t("dentist.report_output"), padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.report_text = tk.Text(output_frame, height=10, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True)
        self._refresh_today()

    def search_patients(self):
        """Function 19: Search patients."""
        search_term = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.search_patient"))
        if not search_term:
            return
        patients = PatientManager.search_patients(search_term)
        if not patients:
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.no_patients_found"))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.search_results"))
        dialog.geometry("600x400")
        columns = ('number', 'name', 'email', 'last_visit')
        tree = ttk.Treeview(dialog, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col.replace('_', ' ').title())
        for p in patients:
            tree.insert('', tk.END, values=(p['patient_number'], p['user_name'], p.get('user_email', ''), p.get('last_visit', 'Never')))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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

    def _refresh_today(self):
        for item in self.today_tree.get_children():
            self.today_tree.delete(item)
        for a in AppointmentManager.get_todays_appointments():
            self.today_tree.insert('', tk.END, values=(a['appointment_time'], a.get('patient_name', 'N/A'), a['dentist_name'], a['treatment_type'], a['status']))

    def record_treatment(self):
        """Function 21: Record a treatment (staff)."""
        if self.user_role not in ('admin', 'staff'):
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.permission_denied"))
            return
        patient_number = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.patient_number"))
        if not patient_number:
            return
        patient = PatientManager.get_patient(patient_number=patient_number)
        if not patient:
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.patient_not_found"))
            return
        treatment_type = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.treatment_type"))
        if not treatment_type or treatment_type not in TREATMENT_TYPES:
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.invalid_treatment"))
            return
        result = TreatmentManager.record_treatment(patient_id=patient['patient_id'], dentist_id='STAFF', dentist_name=self.user_id, treatment_type=treatment_type, treatment_date=datetime.now().strftime('%Y-%m-%d'))
        if result:
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.treatment_recorded"))

    def create_prescription(self):
        """Function 22: Create a prescription (staff)."""
        if self.user_role not in ('admin', 'staff'):
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.permission_denied"))
            return
        patient_number = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.patient_number"))
        if not patient_number:
            return
        patient = PatientManager.get_patient(patient_number=patient_number)
        if not patient:
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.patient_not_found"))
            return
        medication = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.medication"))
        dosage = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.dosage"))
        frequency = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.frequency"))
        duration = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.duration"))
        if all([medication, dosage, frequency, duration]):
            result = PrescriptionManager.create_prescription(patient_id=patient['patient_id'], dentist_id='STAFF', dentist_name=self.user_id, medication=medication, dosage=dosage, frequency=frequency, duration=duration)
            if result:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.prescription_created"))

    def generate_admin_report(self):
        """Function 23: Generate admin report."""
        report_type = self.report_type_var.get()
        if report_type == 'daily':
            data = ReportManager.get_daily_report()
            report = f"=== Daily Report ===\nDate: {data.get('date', 'N/A')}\nTotal Appointments: {data.get('total_appointments', 0)}\nCompleted: {data.get('completed_appointments', 0)}\nTreatments: {data.get('treatments_performed', 0)}\nRevenue: GBP {data.get('revenue', 0):.2f}"
        else:
            data = ReportManager.get_monthly_summary()
            report = f"=== Monthly Summary ===\nPeriod: {data.get('month', '')}/{data.get('year', '')}\nTotal Appointments: {data.get('total_appointments', 0)}\nNew Patients: {data.get('new_patients', 0)}\nRevenue: GBP {data.get('total_revenue', 0):.2f}\n\nTreatments by Type:\n"
            for ttype, info in data.get('treatments_by_type', {}).items():
                report += f"  {ttype}: {info['count']} (GBP {info['revenue']:.2f})\n"
        self.current_report = report
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", report)
        messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.report_generated"))

    def _get_admin_emails(self) -> List[str]:
        """Get email addresses of all admin users."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                ''')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting admin emails: {e}")
            return []

    def email_admin_report(self):
        """Function 24: Email report to admin automatically."""
        if not self.current_report:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.generate_report_first"))
            return

        if not EMAIL_AVAILABLE:
            messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.email_unavailable"))
            return

        # Auto-detect admin emails
        admin_emails = self._get_admin_emails()

        if not admin_emails:
            # Fallback: prompt for email if no admins found
            admin_email = simpledialog.askstring(
                _t("dentist.window_title"),
                "No admin emails found. Enter admin email manually:"
            )
            if admin_email:
                admin_emails = [admin_email]
            else:
                return

        # Send report to all admins
        subject = f"Dental Clinic Report - {datetime.now().strftime('%Y-%m-%d')}"
        success_count = 0
        for email in admin_emails:
            if _send_dentist_email(email, subject, self.current_report):
                success_count += 1

        if success_count > 0:
            messagebox.showinfo(
                _t("dentist.window_title"),
                f"Report sent to {success_count} admin(s): {', '.join(admin_emails)}"
            )
            print(f"[Dentist] Admin report sent to {success_count} admin(s)")
        else:
            messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.email_failed"))

    def _get_student_account_balance(self) -> Optional[float]:
        """Get student's finance account balance."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
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
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
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

    def _show_payment_dialog(self, amount: float, description: str) -> Optional[str]:
        """Show payment method selection dialog. Returns payment method or None if cancelled."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.labels.select_payment_method"))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        result = {'method': None}

        # Payment info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("dentist.btn.payment_details"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Description: {description}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Amount Due: GBP {amount:.2f}", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance
        balance = self._get_student_account_balance()
        if balance is not None:
            ttk.Label(info_frame, text=f"Student Account Balance: GBP {balance:.2f}").pack(anchor=tk.W, pady=(5, 0))
            if balance < amount:
                ttk.Label(info_frame, text=_t("dentist.labels.insufficient_funds"), foreground='red').pack(anchor=tk.W)

        # Payment method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.select_payment_method"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        payment_var = tk.StringVar(value="")

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        cash_btn = ttk.Button(method_frame, text=_t("dentist.btn.cash"), width=20,
                             command=lambda: select_method('cash'))
        cash_btn.pack(pady=5)

        # Card button
        card_btn = ttk.Button(method_frame, text=_t("dentist.btn.card"), width=20,
                             command=lambda: select_method('card'))
        card_btn.pack(pady=5)

        # Student Account button
        account_btn = ttk.Button(method_frame, text=_t("dentist.btn.student_account"), width=20,
                                command=lambda: select_method('student_account'))
        account_btn.pack(pady=5)

        # Disable student account if insufficient funds
        if balance is None or balance < amount:
            account_btn.config(state='disabled')

        # Cancel button
        ttk.Button(dialog, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

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
                try:
                    from education_system.university_system.infrastructure.database.db import transaction as db_transaction
                    with db_transaction() as conn:
                        # Insert into payments table for finance tracking
                        conn.execute('''
                            INSERT INTO payments
                            (student_id, amount, payment_method, payment_date, status, notes, created_by)
                            VALUES (?, ?, ?, date("now"), ?, ?, ?)
                        ''', (self.user_id, amount, f'dentist_{payment_method}', 'completed',
                              f"Dental: {description} (Ref: {result['reference']})", self.user_id))

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

    def create_payments_refunds_tab(self):
        """Function 26: Create payments and refunds management tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("dentist.labels.payments_refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text=_t("dentist.labels.refunds_title"),
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text=_t("dentist.labels.only_appointment_payments"),
                 font=('Arial', 9, 'italic'), foreground='gray').pack(anchor=tk.W)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("dentist.labels.search_payments"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("dentist.labels.patient_id_name")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.payment_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.payment_search_var, width=30).grid(row=0, column=1, padx=5)
        ttk.Button(search_frame, text=_t("dentist.btn.search"), command=self._refresh_payments_list).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text=_t("dentist.btn.show_all"),
                  command=lambda: [self.payment_search_var.set(''), self._refresh_payments_list()]).grid(row=0, column=3, padx=5)

        # Payments list
        list_frame = ttk.LabelFrame(tab, text=_t("dentist.labels.appointment_payments_only"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'reference', 'date', 'user_id', 'patient', 'type', 'amount', 'method', 'status')
        self.payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.payments_tree.heading('transaction_id', text=_t('dentist.columns.id'))
        self.payments_tree.heading('reference', text=_t('dentist.columns.reference'))
        self.payments_tree.heading('date', text=_t('dentist.columns.date'))
        self.payments_tree.heading('user_id', text=_t('dentist.columns.user_id'))
        self.payments_tree.heading('patient', text=_t('dentist.columns.patient_num'))
        self.payments_tree.heading('type', text=_t('dentist.columns.type'))
        self.payments_tree.heading('amount', text=_t('dentist.columns.amount_gbp'))
        self.payments_tree.heading('method', text=_t('dentist.columns.payment_method'))
        self.payments_tree.heading('status', text=_t('dentist.columns.status'))

        self.payments_tree.column('transaction_id', width=50)
        self.payments_tree.column('reference', width=150)
        self.payments_tree.column('date', width=100)
        self.payments_tree.column('user_id', width=100)
        self.payments_tree.column('patient', width=80)
        self.payments_tree.column('type', width=100)
        self.payments_tree.column('amount', width=80)
        self.payments_tree.column('method', width=100)
        self.payments_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
        self.payments_tree.configure(yscrollcommand=scrollbar.set)
        self.payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("dentist.btn.process_refund"), command=self._process_payment_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("dentist.btn.view_details"), command=self._view_payment_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("dentist.btn.export_csv"), command=self._export_payments_csv).pack(side=tk.LEFT, padx=5)

        # Load payments
        self._refresh_payments_list()

    def _refresh_payments_list(self):
        """Refresh the payments list from database - ONLY APPOINTMENTS."""
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                search_term = self.payment_search_var.get().strip()

                # Only show appointments (transaction_type = 'appointment')
                if search_term:
                    cursor = conn.execute('''
                        SELECT
                            dt.transaction_id,
                            dt.reference_number,
                            dt.created_at,
                            dt.student_id,
                            COALESCE(dp.patient_number, 'N/A') as patient_number,
                            dt.transaction_type,
                            dt.amount,
                            dt.payment_method,
                            dt.status
                        FROM transactions dt
                        LEFT JOIN dentist_patients dp ON dt.customer_id = dp.patient_id
                        WHERE dt.source_type = 'dentist' AND dt.transaction_type = 'appointment'
                          AND (dt.student_id LIKE ? OR dp.patient_number LIKE ? OR dp.user_name LIKE ?)
                        ORDER BY dt.created_at DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor = conn.execute('''
                        SELECT
                            dt.transaction_id,
                            dt.reference_number,
                            dt.created_at,
                            dt.student_id,
                            COALESCE(dp.patient_number, 'N/A') as patient_number,
                            dt.transaction_type,
                            dt.amount,
                            dt.payment_method,
                            dt.status
                        FROM transactions dt
                        LEFT JOIN dentist_patients dp ON dt.customer_id = dp.patient_id
                        WHERE dt.source_type = 'dentist' AND dt.transaction_type = 'appointment'
                        ORDER BY dt.created_at DESC
                        LIMIT 100
                    ''')

                for row in cursor.fetchall():
                    values = list(row)
                    # Ensure all 9 columns
                    while len(values) < 9:
                        values.append('N/A')
                    # Format amount
                    if values[6] and values[6] != 'N/A':
                        try:
                            values[6] = f"{float(values[6]):.2f}"
                        except (ValueError, TypeError):
                            pass
                    self.payments_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to load payments: {e}")

    def _view_payment_details(self):
        """View detailed payment information."""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_t("dentist.msg_titles.no_selection"), "Please select a payment to view details")
            return

        try:
            values = self.payments_tree.item(selection[0])['values']
            if len(values) < 9:
                messagebox.showerror(_t("dentist.msg_titles.data_error"), "Payment record is incomplete")
                return

            details = f"""PAYMENT DETAILS
==================
Transaction ID: {values[0]}
Reference: {values[1]}
Date: {values[2]}
User ID: {values[3]}
Patient Number: {values[4]}
Transaction Type: {values[5]}
Amount: GBP {values[6]}
Payment Method: {values[7]}
Status: {values[8]}
"""
            messagebox.showinfo(_t("dentist.msg_titles.payment_details"), details)
        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.error"), f"Error viewing payment details: {e}")

    def _export_payments_csv(self):
        """Export payments to CSV file."""
        try:
            from tkinter import filedialog
            import csv

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"dentist_payments_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Transaction ID', 'Reference', 'Date', 'User ID', 'Patient #',
                                   'Type', 'Amount', 'Method', 'Status'])

                    for item in self.payments_tree.get_children():
                        values = self.payments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo(_t("dentist.msg_titles.export_successful"), f"Payments exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror(_t("dentist.msg_titles.export_error"), f"Failed to export payments: {e}")

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
                from education_system.university_system.infrastructure.database.db import transaction as db_transaction
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

    def _show_refund_method_dialog(self, amount: float, user_id: str) -> Optional[str]:
        """Show refund method selection dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("dentist.labels.select_refund_method"))
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.refund_details"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"User ID: {user_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance
        balance = self._get_student_account_balance_by_user(user_id)
        if balance is not None:
            ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
                anchor=tk.W, pady=(5, 0))
            ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                     foreground='green').pack(anchor=tk.W)

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.select_refund_method"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text=_t("dentist.btn.cash"), width=30,
                  command=lambda: select_method('Cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text=_t("dentist.labels.card_original"), width=30,
                  command=lambda: select_method('Card')).pack(pady=5)

        # Student Account button
        ttk.Button(method_frame, text=_t("dentist.btn.student_finance"), width=30,
                  command=lambda: select_method('Student Account')).pack(pady=5)

        # Cancel button
        ttk.Button(dialog, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def _get_student_account_balance_by_user(self, user_id: str) -> Optional[float]:
        """Get student's finance account balance by user ID."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
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
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
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
            from education_system.university_system.infrastructure.database.db import get_connection
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

    def _notify_finance_for_refund(self, user_id: str, amount: float, method: str, refund_ref: str):
        """Record refund in finance system for integration."""
        try:
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
            from datetime import datetime
            with db_transaction() as conn:
                # Record refund in unified_refunds table
                try:
                    conn.execute('''
                        INSERT INTO unified_refunds
                        (source_type, student_id, refund_reference, department,
                         amount, refund_method, refund_date, processed_by, notes, reference_type)
                        VALUES ('dentist', ?, ?, 'Dentist', ?, ?, ?, ?, 'Dental Clinic Payment Refund', 'payment')
                    ''', (
                        user_id,
                        refund_ref,
                        amount,
                        method.lower().replace(' ', '_'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        self.user_id,
                    ))
                    print(f"[Dentist] Refund recorded in finance system: {refund_ref}")
                except Exception as e:
                    print(f"[Dentist] Error recording refund in finance system: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error notifying finance system: {e}")


def launch_dentist_gui(root=None, auth=None):
    """Launch the Dentist GUI."""
    if root is None:
        root = tk.Tk()
    DentistGUI(root, auth)
    return root
