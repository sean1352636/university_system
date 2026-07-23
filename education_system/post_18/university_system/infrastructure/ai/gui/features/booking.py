import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")

logger = logging.getLogger(__name__)

# Bookable facilities offered in the chatbot dialog. Mirrors the "Available
# spaces" list the assistant describes in text responses.
FACILITIES = [
    "Study room (library)",
    "Meeting room",
    "Seminar room",
    "Sports facility",
]


class BookingMixin:
    """Mixin providing a 'Book a Room' dialog that records a facility booking
    and emails the user a confirmation."""

    def show_book_room_dialog(self):
        """Open the room-booking dialog."""
        if not getattr(self, 'current_user', None):
            messagebox.showwarning(
                _t("chatbot.booking", default="Book a Room"),
                _t("chatbot.booking_login", default="Please log in to book a room."),
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("chatbot.booking_title", default="Book a Room"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        frm = ttk.Frame(dialog, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=_t("chatbot.booking_heading", default="Book a Room / Facility"),
                  style='CB.Title.TLabel').grid(row=0, column=0, columnspan=2,
                                                sticky='w', pady=(0, 12))

        # Facility
        ttk.Label(frm, text=_t("chatbot.facility", default="Facility:")).grid(
            row=1, column=0, sticky='w', pady=4)
        facility_var = tk.StringVar(value=FACILITIES[0])
        facility_box = ttk.Combobox(frm, textvariable=facility_var, values=FACILITIES,
                                    state='readonly', width=28)
        facility_box.grid(row=1, column=1, sticky='ew', pady=4)

        # Date
        ttk.Label(frm, text=_t("chatbot.date", default="Date (YYYY-MM-DD):")).grid(
            row=2, column=0, sticky='w', pady=4)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frm, textvariable=date_var, width=30).grid(row=2, column=1, sticky='ew', pady=4)

        # Start / end time
        ttk.Label(frm, text=_t("chatbot.start_time", default="Start time (HH:MM):")).grid(
            row=3, column=0, sticky='w', pady=4)
        start_var = tk.StringVar(value="09:00")
        ttk.Entry(frm, textvariable=start_var, width=30).grid(row=3, column=1, sticky='ew', pady=4)

        ttk.Label(frm, text=_t("chatbot.end_time", default="End time (HH:MM):")).grid(
            row=4, column=0, sticky='w', pady=4)
        end_var = tk.StringVar(value="10:00")
        ttk.Entry(frm, textvariable=end_var, width=30).grid(row=4, column=1, sticky='ew', pady=4)

        # Purpose (optional)
        ttk.Label(frm, text=_t("chatbot.purpose", default="Purpose (optional):")).grid(
            row=5, column=0, sticky='w', pady=4)
        purpose_var = tk.StringVar()
        ttk.Entry(frm, textvariable=purpose_var, width=30).grid(row=5, column=1, sticky='ew', pady=4)

        frm.columnconfigure(1, weight=1)

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky='e', pady=(14, 0))

        def submit():
            self._submit_room_booking(
                dialog,
                facility=facility_var.get(),
                date=date_var.get(),
                start=start_var.get(),
                end=end_var.get(),
                purpose=purpose_var.get(),
            )

        ttk.Button(btns, text=_t("chatbot.book_btn", default="Book"),
                   style='CB.Primary.TButton', command=submit).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text=_t("chatbot.cancel_btn", default="Cancel"),
                   style='CB.Secondary.TButton', command=dialog.destroy).pack(side=tk.RIGHT)

        facility_box.focus()

    def _submit_room_booking(self, dialog, facility, date, start, end, purpose):
        """Validate + persist the booking, then email a confirmation."""
        username = self.current_user.get("username")
        result = self.chatbot.create_facility_booking(
            username, facility, date, start, end, purpose)

        if not result.get("ok"):
            messagebox.showerror(
                _t("chatbot.booking_failed", default="Booking Failed"),
                result.get("error", "Could not create the booking."),
                parent=dialog,
            )
            return

        booking = result["booking"]
        email = result.get("email")
        name = result.get("name") or username

        # Send the confirmation email (best-effort — the booking itself is saved).
        email_note = self._send_booking_confirmation(email, name, booking)

        # Reflect it in the chat transcript.
        if hasattr(self, "add_chat_message"):
            self.add_chat_message(
                _t("chatbot.system", default="System"),
                f"Room booked: {booking['room']} on {booking['date']} "
                f"{booking['start']}–{booking['end']}. {email_note}",
                "system",
            )

        messagebox.showinfo(
            _t("chatbot.booking_confirmed", default="Booking Confirmed"),
            f"{booking['room']} booked for {booking['date']} "
            f"{booking['start']}–{booking['end']}.\n\n{email_note}",
            parent=dialog,
        )
        dialog.destroy()

    def _send_booking_confirmation(self, email, name, booking):
        """Send the confirmation email. Returns a short status note for the UI."""
        if not email:
            return "No email address on file, so no confirmation was sent."
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service.core import (
                send_email_as_system,
            )
            subject = f"Room booking confirmed: {booking['room']} on {booking['date']}"
            body = (
                f"Hi {name},\n\n"
                f"Your room booking is confirmed:\n\n"
                f"  Facility : {booking['room']}\n"
                f"  Date     : {booking['date']}\n"
                f"  Time     : {booking['start']} - {booking['end']}\n"
                f"  Reference: #{booking['id']}\n"
                + (f"  Purpose  : {booking['purpose']}\n" if booking.get('purpose') else "")
                + "\nIf you need to cancel, please use the student portal or "
                "contact facilities@university.ac.uk.\n\n"
                "University Facilities Team"
            )
            ok = send_email_as_system(email, subject, body, system_name="University Facilities")
            if ok:
                return f"A confirmation email was sent to {email}."
            return f"Booking saved, but the confirmation email to {email} could not be sent."
        except Exception as e:
            logger.debug(f"Booking confirmation email failed: {e}")
            return f"Booking saved, but the confirmation email to {email} could not be sent."
