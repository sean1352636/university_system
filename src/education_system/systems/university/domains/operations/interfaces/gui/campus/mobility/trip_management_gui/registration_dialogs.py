
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import safe_db_operation


class CancelRegistrationDialog(Dialog):
    def __init__(self, parent, auth, trip_id, trip_name, payment_status, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.trip_name = trip_name
        self.payment_status = payment_status
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Cancel Trip Registration")

    def body(self, master):
        """Create the dialog body"""
        # Trip information
        info_frame = ttk.LabelFrame(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.registration_details', default="Registration Details"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Trip: {self.trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Payment Status: {self.payment_status.title()}").pack(anchor=tk.W)

        if self.payment_status.lower() in ['paid', 'partial']:
            ttk.Label(info_frame, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.warning_you_have_made_payment_s_for_this_trip', default="\u26a0\ufe0f Warning: You have made payment(s) for this trip."),
                     foreground="orange", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=5)
            ttk.Label(info_frame, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.cancellation_may_involve_refund_processing', default="Cancellation may involve refund processing.")).pack(anchor=tk.W)

        # Cancellation reason
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.reason_for_cancellation_optional', default="Reason for cancellation (optional):")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.reason_text = tk.Text(master, width=50, height=3)
        self.reason_text.pack(fill=tk.X, padx=10, pady=(0, 10))

        return self.reason_text

    def apply(self):
        """Apply the cancellation"""
        def cancel_operation(conn):
            cursor = conn.cursor()

            # Check if registration exists and belongs to user
            cursor.execute('''
            SELECT id FROM trip_participants
            WHERE trip_id = ? AND user_id = ? AND status = 'registered'
            ''', (self.trip_id, self.auth.current_user['id']))

            if not cursor.fetchone():
                return "not_found"

            # Update registration status to cancelled
            reason = self.reason_text.get(1.0, tk.END).strip()
            cursor.execute('''
            UPDATE trip_participants
            SET status = 'cancelled',
                cancellation_reason = ?,
                cancellation_date = ?
            WHERE trip_id = ? AND user_id = ?
            ''', (reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  self.trip_id, self.auth.current_user['id']))

            return "success"

        result = self.safe_db_operation(cancel_operation)

        if result == "not_found":
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.registration_not_found_or_already_cancelled', default="Registration not found or already cancelled."))
        elif result == "success":
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.success', default="Success"), f"Registration for '{self.trip_name}' has been cancelled.")
            if self.payment_status.lower() in ['paid', 'partial']:
                messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.refund_information', default="Refund Information"),
                                   _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.please_contact_administration_regarding_refund_processing', default="Please contact administration regarding refund processing."))
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.failed_to_cancel_registration', default="Failed to cancel registration."))

    def safe_db_operation(self, operation_func):
        """Use the same safe_db_operation as the main GUI"""
        return safe_db_operation(operation_func)


class RegisterForTripDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback1, refresh_callback2):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback1 = refresh_callback1
        self.refresh_callback2 = refresh_callback2
        self.trip_info = None

        # Get trip information first
        self.load_trip_info()

        super().__init__(parent, "Register for Trip")

    def load_trip_info(self):
        """Load trip information"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT trip_name, destination, start_date, cost, max_participants,
                   (SELECT COUNT(*) FROM trip_participants WHERE trip_id = ? AND status = 'registered') as current_participants
            FROM trips WHERE id = ?
            ''', (self.trip_id, self.trip_id))

            return cursor.fetchone()

        self.trip_info = safe_db_operation(get_trip_info_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.trip_info:
            ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.trip_not_found', default="Trip not found.")).pack(pady=20)
            return None

        trip_name, destination, start_date, cost, max_participants, current_participants = self.trip_info

        # Trip information
        info_frame = ttk.LabelFrame(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.trip_information', default="Trip Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {destination}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Start Date: {start_date}").pack(anchor=tk.W)
        cost_str = f"\u00a3{cost:.2f}" if cost is not None else "\u00a30.00"
        ttk.Label(info_frame, text=f"Cost: {cost_str}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Participants: {current_participants}/{max_participants}").pack(anchor=tk.W)

        # Registration form
        reg_frame = ttk.LabelFrame(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.registration_details', default="Registration Details"), padding=10)
        reg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Emergency contact
        ttk.Label(reg_frame, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.emergency_contact_name_and_phone', default="Emergency Contact (Name and Phone):")).pack(anchor=tk.W)
        self.emergency_var = tk.StringVar()
        self.emergency_entry = ttk.Entry(reg_frame, textvariable=self.emergency_var, width=50)
        self.emergency_entry.pack(fill=tk.X, pady=(0, 10))

        # Medical information
        ttk.Label(reg_frame, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.medical_information_optional', default="Medical Information (optional):")).pack(anchor=tk.W)
        self.medical_text = tk.Text(reg_frame, width=50, height=3)
        self.medical_text.pack(fill=tk.X, pady=(0, 10))

        # Dietary requirements
        ttk.Label(reg_frame, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.dietary_requirements_optional', default="Dietary Requirements (optional):")).pack(anchor=tk.W)
        self.dietary_text = tk.Text(reg_frame, width=50, height=2)
        self.dietary_text.pack(fill=tk.X)

        return self.emergency_entry  # Initial focus - return widget, not StringVar

    def validate(self):
        """Validate registration data"""
        if not self.emergency_var.get().strip():
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.emergency_contact_information_is_required', default="Emergency contact information is required."))
            return False
        return True

    def apply(self):
        """Apply the registration"""
        def register_operation(conn):
            cursor = conn.cursor()

            # Check if already registered
            cursor.execute('''
            SELECT id FROM trip_participants
            WHERE trip_id = ? AND user_id = ?
            ''', (self.trip_id, self.auth.current_user['id']))

            if cursor.fetchone():
                return "already_registered"

            # Get student ID if user is a student
            student_id = None
            if self.auth.current_user['role'] == 'student':
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()
                if result:
                    student_id = result[0]

            # Register for trip
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO trip_participants (
                trip_id, student_id, user_id, registration_date,
                emergency_contact, medical_info, dietary_requirements
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id, student_id, self.auth.current_user['id'], timestamp,
                self.emergency_var.get().strip(),
                self.medical_text.get(1.0, tk.END).strip(),
                self.dietary_text.get(1.0, tk.END).strip()
            ))

            return "success"

        result = safe_db_operation(register_operation)

        if result == "already_registered":
            messagebox.showwarning(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.already_registered', default="Already Registered"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.you_are_already_registered_for_this_trip', default="You are already registered for this trip."))
        elif result == "success":
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.success', default="Success"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.successfully_registered_for_the_trip', default="Successfully registered for the trip!"))
            if self.refresh_callback1:
                self.refresh_callback1()
            if self.refresh_callback2:
                self.refresh_callback2()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.failed_to_register_for_trip', default="Failed to register for trip."))


class PaymentStatusDialog(Dialog):
    def __init__(self, parent, participant_id, refresh_callback):
        self.participant_id = participant_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Update Payment Status")

    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.select_new_payment_status', default="Select new payment status:")).pack(pady=10)

        self.payment_var = tk.StringVar(value=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.values.pending', default="pending"))

        payment_options = ['pending', 'partial', 'paid', 'refunded']
        for option in payment_options:
            ttk.Radiobutton(master, text=option.title(), variable=self.payment_var,
                           value=option).pack(anchor=tk.W, padx=20)

        return None

    def apply(self):
        """Apply the payment status update"""
        def update_payment_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET payment_status = ? WHERE id = ?',
                (self.payment_var.get(), self.participant_id)
            )
            return True


        if safe_db_operation(update_payment_operation):
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.success', default="Success"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.payment_status_updated_successfully', default="Payment status updated successfully!"))
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.failed_to_update_payment_status', default="Failed to update payment status."))


class ParticipantStatusDialog(Dialog):
    def __init__(self, parent, participant_id, refresh_callback):
        self.participant_id = participant_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Update Participant Status")

    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.labels.select_new_participant_status', default="Select new participant status:")).pack(pady=10)

        self.status_var = tk.StringVar(value=_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.values.registered', default="registered"))

        status_options = ['registered', 'waitlist', 'cancelled', 'attended']
        for option in status_options:
            ttk.Radiobutton(master, text=option.title(), variable=self.status_var,
                           value=option).pack(anchor=tk.W, padx=20)

        return None

    def apply(self):
        """Apply the status update"""
        def update_status_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET status = ? WHERE id = ?',
                (self.status_var.get(), self.participant_id)
            )
            return True


        if safe_db_operation(update_status_operation):
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.success', default="Success"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.participant_status_updated_successfully', default="Participant status updated successfully!"))
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.registration_dialogs.dialogs.failed_to_update_participant_status', default="Failed to update participant status."))
