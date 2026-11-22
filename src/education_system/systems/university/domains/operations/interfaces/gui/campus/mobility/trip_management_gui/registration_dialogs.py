
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, show_error, money, title_case,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.registration_dialogs'


def _describe_refund(outcome):
    """One paragraph about the refund a cancellation produced (or will produce)."""
    if not outcome:
        return ""
    refund = outcome.get('refund')
    due = outcome.get('refund_due') or {}
    if refund:
        if refund.get('skipped'):
            return refund.get('message') or ""
        if refund.get('success'):
            return tf(f"{_K}.dialogs.refund_done", "A refund of {amount} has been raised.",
                      amount=money(refund.get('amount')))
        return tf(f"{_K}.dialogs.refund_failed",
                  "The refund of {amount} could not be raised: {message}\n"
                  "Please contact the finance office.",
                  amount=money(refund.get('amount')), message=refund.get('message') or '')
    if due and due.get('amount'):
        return tf(f"{_K}.dialogs.refund_due", "Refund due: {amount}.", amount=money(due['amount']))
    return ""


class CancelRegistrationDialog(Dialog):
    """Cancel a registration through ``registrations.cancel_registration``.

    Shows the refund the trip's refund tiers give before asking (the deposit
    is kept, per ``money.refund_due``). ``participant_id`` is the
    registration; when it is not given it is looked up among the signed-in
    user's own registrations on ``trip_id``.
    """

    def __init__(self, parent, auth, trip_id, trip_name, payment_status, refresh_callback,
                 participant_id=None):
        self.auth = auth
        self.trip_id = trip_id
        self.trip_name = trip_name
        self.payment_status = str(payment_status or '')
        self.refresh_callback = refresh_callback
        self.participant_id = participant_id or self._own_registration()
        self.refund_due = None
        if self.participant_id:
            try:
                self.refund_due = tm('money').refund_due(self.participant_id)
            except Exception:
                self.refund_due = None
        super().__init__(parent, _t(f"{_K}.windows.cancel", default="Cancel Trip Registration"))

    def _own_registration(self):
        try:
            current = tm('database').CURRENT_PARTICIPANT_STATUSES
            for reg in tm('registrations').list_my_registrations(self.auth):
                if str(reg['trip_id']) == str(self.trip_id) and reg['status'] in current:
                    return reg['participant_id']
        except Exception:
            return None
        return None

    def body(self, master):
        """Create the dialog body"""
        info_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.registration_details", default="Registration Details"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Trip: {self.trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Payment Status: {self.payment_status.title()}").pack(anchor=tk.W)

        due = self.refund_due
        if due and (due.get('paid') or 0) > 0:
            ttk.Label(info_frame, text=_t(f"{_K}.labels.warning_you_have_made_payment_s_for_this_trip", default="⚠️ Warning: You have made payment(s) for this trip."),
                      foreground="orange", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=5)
            ttk.Label(info_frame, text=tf(
                f"{_K}.labels.refund_breakdown",
                "Paid {paid}. Cancelling {days} day(s) before the trip refunds {percent:.0f}% "
                "after the deposit ({deposit}) is kept.\nRefund due: {amount}",
                paid=money(due['paid']), days=due['days_before'], percent=due['percent'],
                deposit=money(due['deposit_retained']), amount=money(due['amount'])),
                justify=tk.LEFT).pack(anchor=tk.W)
        elif not self.participant_id:
            ttk.Label(info_frame, text=_t(f"{_K}.labels.no_active_registration",
                                          default="You have no active registration on this trip."),
                      foreground="red").pack(anchor=tk.W, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.reason_for_cancellation_optional", default="Reason for cancellation (optional):")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.reason_text = tk.Text(master, width=50, height=3)
        self.reason_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        return self.reason_text

    def validate(self):
        if not self.participant_id:
            messagebox.showerror(_t(f"{_K}.dialogs.error", default="Error"),
                                 _t(f"{_K}.dialogs.registration_not_found_or_already_cancelled", default="Registration not found or already cancelled."),
                                 parent=self)
            return False
        return True

    def apply(self):
        """Cancel through the domain; the refund (Finance) runs off the Tk thread."""
        reason = self.reason_text.get(1.0, tk.END).strip()
        parent = self.parent
        pid, auth, name, refresh = self.participant_id, self.auth, self.trip_name, self.refresh_callback

        def done(outcome):
            text = tf(f"{_K}.dialogs.cancelled", "Registration for '{trip}' has been cancelled.", trip=name)
            extra = _describe_refund(outcome)
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"),
                                text + ("\n\n" + extra if extra else ""), parent=parent)
            if refresh:
                refresh()

        run_async(parent, lambda: tm('registrations').cancel_registration(auth, pid, reason), done)


class RegisterForTripDialog(Dialog):
    """Register the signed-in user through ``registrations.register``.

    The domain checks the trip is open, the person is not already on it,
    finance holds and capacity; a full trip offers the waiting list. Health
    details are sealed by the domain before they are written.
    """

    def __init__(self, parent, auth, trip_id, refresh_callback1, refresh_callback2):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.refresh_callback1 = refresh_callback1
        self.refresh_callback2 = refresh_callback2
        self.trip_info = None
        self.taken = 0
        self.load_trip_info()
        super().__init__(parent, _t(f"{_K}.windows.register", default="Register for Trip"))

    def load_trip_info(self):
        """Load trip information"""
        try:
            for trip in tm('trips').list_trips(include_archived=True):
                if trip['id'] == self.trip_id:
                    self.trip_info = trip
                    self.taken = trip.get('current_participants') or 0
                    break
        except Exception:
            self.trip_info = None

    def body(self, master):
        if not self.trip_info:
            ttk.Label(master, text=_t(f"{_K}.labels.trip_not_found", default="Trip not found.")).pack(pady=20)
            return None
        trip = self.trip_info

        info_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.trip_information", default="Trip Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(info_frame, text=f"Trip: {trip['trip_name']}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {trip.get('destination') or ''}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Start Date: {trip.get('start_date') or ''}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Cost: {money(trip.get('cost'))}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Participants: {self.taken}/{trip.get('max_participants')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Status: {title_case(trip.get('status'))}").pack(anchor=tk.W)

        reg_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.registration_details", default="Registration Details"), padding=10)
        reg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Label(reg_frame, text=_t(f"{_K}.labels.emergency_contact_name_and_phone", default="Emergency Contact (Name and Phone):")).pack(anchor=tk.W)
        self.emergency_var = tk.StringVar()
        self.emergency_entry = ttk.Entry(reg_frame, textvariable=self.emergency_var, width=50)
        self.emergency_entry.pack(fill=tk.X, pady=(0, 6))

        contact = ttk.Frame(reg_frame)
        contact.pack(fill=tk.X, pady=(0, 8))
        self.contact_name_var = tk.StringVar()
        self.contact_phone_var = tk.StringVar()
        self.contact_rel_var = tk.StringVar()
        for col, (label, var, width) in enumerate((
                (_t(f"{_K}.labels.contact_name", default="Name"), self.contact_name_var, 18),
                (_t(f"{_K}.labels.contact_phone", default="Phone"), self.contact_phone_var, 14),
                (_t(f"{_K}.labels.contact_relationship", default="Relationship"), self.contact_rel_var, 12))):
            ttk.Label(contact, text=label).grid(row=0, column=col * 2, sticky=tk.W, padx=(0, 3))
            ttk.Entry(contact, textvariable=var, width=width).grid(row=0, column=col * 2 + 1, padx=(0, 8))

        ttk.Label(reg_frame, text=_t(f"{_K}.labels.medical_information_optional", default="Medical Information (optional):")).pack(anchor=tk.W)
        self.medical_text = tk.Text(reg_frame, width=50, height=3)
        self.medical_text.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(reg_frame, text=_t(f"{_K}.labels.dietary_requirements_optional", default="Dietary Requirements (optional):")).pack(anchor=tk.W)
        self.dietary_text = tk.Text(reg_frame, width=50, height=2)
        self.dietary_text.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(reg_frame, text=_t(f"{_K}.labels.accessibility_optional", default="Accessibility Needs (optional):")).pack(anchor=tk.W)
        self.access_text = tk.Text(reg_frame, width=50, height=2)
        self.access_text.pack(fill=tk.X)

        ttk.Label(reg_frame, text=_t(f"{_K}.labels.sealed_note",
                                     default="Medical, dietary and accessibility details are stored encrypted "
                                             "and only the trip's leaders and the health team can read them."),
                  foreground="gray", wraplength=420, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))
        return self.emergency_entry

    def validate(self):
        if not self.trip_info:
            return False
        if not (self.emergency_var.get().strip() or self.contact_name_var.get().strip()
                or self.contact_phone_var.get().strip()):
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.emergency_contact_information_is_required", default="Emergency contact information is required."), parent=self)
            return False
        return True

    def _details(self):
        values = {
            'emergency_contact': self.emergency_var.get().strip(),
            'emergency_contact_name': self.contact_name_var.get().strip(),
            'emergency_contact_phone': self.contact_phone_var.get().strip(),
            'emergency_contact_relationship': self.contact_rel_var.get().strip(),
            'medical_info': self.medical_text.get(1.0, tk.END).strip(),
            'dietary_requirements': self.dietary_text.get(1.0, tk.END).strip(),
            'accessibility_needs': self.access_text.get(1.0, tk.END).strip(),
        }
        return {k: v for k, v in values.items() if v}

    def apply(self):
        details = self._details()
        parent = self.parent
        registrations = tm('registrations')
        ok, booking = call(parent, self._do_register, registrations, details, False,
                           title=_t(f"{_K}.dialogs.error", default="Error"))
        if ok and booking is None and getattr(self, '_full', False):
            if not messagebox.askyesno(
                    _t(f"{_K}.dialogs.trip_full", default="Trip Full"),
                    _t(f"{_K}.dialogs.join_waitlist",
                       default="This trip is full. Join the waiting list? You will be e-mailed "
                               "if a place comes up and have 48 hours to accept it."),
                    parent=parent):
                return
            ok, booking = call(parent, self._do_register, registrations, details, True)
        if not ok or not booking:
            return
        if booking['status'] == 'waitlisted':
            text = tf(f"{_K}.dialogs.waitlisted", "You are on the waiting list (position {position}).",
                      position=booking.get('position'))
        else:
            text = _t(f"{_K}.dialogs.successfully_registered_for_the_trip", default="Successfully registered for the trip!")
            if float(booking.get('amount') or 0) > 0:
                text += "\n\n" + tf(f"{_K}.dialogs.payment_due",
                                    "{amount} is due. Pay from My Trips > Pay.",
                                    amount=money(booking['amount']))
        text += "\n" + tf(f"{_K}.dialogs.reference", "Reference: {reference}", reference=booking['reference'])
        messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), text, parent=parent)
        for cb in (self.refresh_callback1, self.refresh_callback2):
            if cb:
                cb()

    def _do_register(self, registrations, details, waitlist):
        self._full = False
        try:
            return registrations.register(self.auth, self.trip_id, waitlist=waitlist, **details)
        except registrations.TripFullError:
            if waitlist:
                raise
            self._full = True
            return None


class PaymentStatusDialog(Dialog):
    """Organiser record of a payment taken outside the booking flow
    (``registrations.set_payment_status``)."""

    def __init__(self, parent, auth, participant_id, refresh_callback):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.payment", default="Update Payment Status"))

    def body(self, master):
        ttk.Label(master, text=_t(f"{_K}.labels.select_new_payment_status", default="Select new payment status:")).pack(pady=10)
        self.payment_var = tk.StringVar(value='pending')
        for option in tm('database').PAYMENT_STATUSES:
            ttk.Radiobutton(master, text=option.title(), variable=self.payment_var,
                            value=option).pack(anchor=tk.W, padx=20)
        row = ttk.Frame(master)
        row.pack(fill=tk.X, padx=20, pady=(10, 0))
        ttk.Label(row, text=_t(f"{_K}.labels.amount_paid_optional", default="Amount paid (optional, £):")).pack(side=tk.LEFT)
        self.amount_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.amount_var, width=10).pack(side=tk.LEFT, padx=5)
        return None

    def apply(self):
        amount = self.amount_var.get().strip()
        kwargs = {}
        if amount:
            try:
                kwargs['amount_paid'] = float(amount)
            except ValueError:
                show_error(self.parent, ValueError(_t(f"{_K}.dialogs.bad_amount", default="Please enter a valid amount.")))
                return
        ok, _ = call(self.parent, tm('registrations').set_payment_status, self.auth,
                     self.participant_id, self.payment_var.get(), **kwargs)
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.payment_status_updated_successfully", default="Payment status updated successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()


class ParticipantStatusDialog(Dialog):
    """Organiser change of a participant's status (``registrations.set_participant_status``)."""

    def __init__(self, parent, auth, participant_id, refresh_callback):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.status", default="Update Participant Status"))

    def body(self, master):
        ttk.Label(master, text=_t(f"{_K}.labels.select_new_participant_status", default="Select new participant status:")).pack(pady=10)
        self.status_var = tk.StringVar(value='registered')
        for option in tm('database').PARTICIPANT_STATUSES:
            ttk.Radiobutton(master, text=title_case(option), variable=self.status_var,
                            value=option).pack(anchor=tk.W, padx=20)
        ttk.Label(master, text=_t(f"{_K}.labels.reason_optional", default="Reason (optional):")).pack(anchor=tk.W, padx=20, pady=(10, 0))
        self.reason_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.reason_var, width=40).pack(padx=20, pady=(0, 5))
        return None

    def apply(self):
        parent, auth, pid = self.parent, self.auth, self.participant_id
        status, reason = self.status_var.get(), self.reason_var.get().strip()
        refresh = self.refresh_callback

        def done(outcome):
            text = _t(f"{_K}.dialogs.participant_status_updated_successfully", default="Participant status updated successfully!")
            extra = _describe_refund(outcome) if isinstance(outcome, dict) and 'refund' in outcome else ""
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"),
                                text + ("\n\n" + extra if extra else ""), parent=parent)
            if refresh:
                refresh()

        # Cancelling / removing may refund through Finance: off the Tk thread.
        run_async(parent, lambda: tm('registrations').set_participant_status(auth, pid, status, reason), done)
