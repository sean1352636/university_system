"""Student-side Office Hours booking GUI.

Provides a Treeview-based interface for students to browse available
office hours, create bookings, and manage (cancel) existing bookings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


class BookingManager:
    """Manages the student booking view for office hours."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self._setup_ui()
        self._refresh_available()

    # ------------------------------------------------------------------ #
    #  UI setup
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        """Build the booking interface."""
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- Available office hours ---- #
        avail_frame = ttk.LabelFrame(
            main_frame, text="Available Office Hours", padding="5",
        )
        avail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'instructor', 'day', 'start', 'end', 'location', 'capacity')
        self.avail_tree = ttk.Treeview(
            avail_frame, columns=columns, show='headings', height=8,
        )
        for col in columns:
            self.avail_tree.heading(col, text=col.title())
            self.avail_tree.column(col, width=100)
        self.avail_tree.column('id', width=50)

        avail_scrollbar = ttk.Scrollbar(
            avail_frame, orient=tk.VERTICAL, command=self.avail_tree.yview,
        )
        self.avail_tree.configure(yscrollcommand=avail_scrollbar.set)
        self.avail_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        avail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons for available hours
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(
            btn_frame, text="Book Selected", command=self._book_selected,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Refresh", command=self._refresh_available,
        ).pack(side=tk.LEFT, padx=5)

        # ---- My bookings ---- #
        my_frame = ttk.LabelFrame(
            main_frame, text="My Bookings", padding="5",
        )
        my_frame.pack(fill=tk.BOTH, expand=True)

        booking_cols = (
            'id', 'instructor', 'day', 'time', 'location', 'date', 'status',
        )
        self.bookings_tree = ttk.Treeview(
            my_frame, columns=booking_cols, show='headings', height=6,
        )
        for col in booking_cols:
            self.bookings_tree.heading(col, text=col.title())
            self.bookings_tree.column(col, width=100)
        self.bookings_tree.column('id', width=50)

        bookings_scrollbar = ttk.Scrollbar(
            my_frame, orient=tk.VERTICAL, command=self.bookings_tree.yview,
        )
        self.bookings_tree.configure(yscrollcommand=bookings_scrollbar.set)
        self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bookings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame2 = ttk.Frame(my_frame)
        btn_frame2.pack(fill=tk.X, pady=5)
        ttk.Button(
            btn_frame2, text="Cancel Selected", command=self._cancel_selected,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame2, text="Refresh Bookings", command=self._refresh_bookings,
        ).pack(side=tk.LEFT, padx=5)

        self._refresh_bookings()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _get_student_id(self):
        """Return the current student's user ID."""
        if self.auth and self.auth.current_user:
            return self.auth.current_user.get('username', '')
        return ''

    # ------------------------------------------------------------------ #
    #  Data operations
    # ------------------------------------------------------------------ #

    def _refresh_available(self):
        """Reload available office hours into the Treeview."""
        for item in self.avail_tree.get_children():
            self.avail_tree.delete(item)

        try:
            hours = self.service.get_available_office_hours()
            for h in hours:
                self.avail_tree.insert('', tk.END, values=(
                    h['id'],
                    h['instructor_id'],
                    h['day_of_week'],
                    h['start_time'],
                    h['end_time'],
                    h['location'],
                    h['capacity'],
                ))
        except Exception as e:
            logger.error("Error refreshing available office hours: %s", e)
            messagebox.showerror(
                "Error", f"Failed to load available office hours:\n{e}",
            )

    def _refresh_bookings(self):
        """Reload the student's bookings into the Treeview."""
        for item in self.bookings_tree.get_children():
            self.bookings_tree.delete(item)

        student_id = self._get_student_id()
        if not student_id:
            return

        try:
            bookings = self.service.get_student_bookings(student_id)
            for b in bookings:
                time_str = f"{b['start_time']}-{b['end_time']}"
                self.bookings_tree.insert('', tk.END, values=(
                    b['id'],
                    b['instructor_id'],
                    b['day_of_week'],
                    time_str,
                    b['location'],
                    b['booking_date'],
                    b['status'],
                ))
        except Exception as e:
            logger.error("Error refreshing student bookings: %s", e)
            messagebox.showerror(
                "Error", f"Failed to load your bookings:\n{e}",
            )

    # ------------------------------------------------------------------ #
    #  Book selected
    # ------------------------------------------------------------------ #

    def _book_selected(self):
        """Book the office hours entry selected in the available hours tree."""
        selected = self.avail_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select an office hours entry to book.",
            )
            return

        values = self.avail_tree.item(selected[0], 'values')
        oh_id = int(values[0])
        instructor = values[1]
        day = values[2]
        start = values[3]
        end = values[4]
        location = values[5]

        student_id = self._get_student_id()
        if not student_id:
            messagebox.showwarning(
                "Not Logged In",
                "You must be logged in to book an appointment.",
            )
            return

        # Show booking dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title("Book Appointment")
        dialog.geometry("400x250")
        dialog.transient(self.parent)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        # Display summary
        ttk.Label(
            frame,
            text=f"Instructor: {instructor}",
            font=('Arial', 10),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(
            frame,
            text=f"Schedule: {day} {start}-{end}",
            font=('Arial', 10),
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(
            frame,
            text=f"Location: {location}",
            font=('Arial', 10),
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=2, sticky=tk.EW, pady=10,
        )

        # Booking date
        ttk.Label(frame, text="Booking Date (YYYY-MM-DD):").grid(
            row=4, column=0, sticky=tk.W, pady=5,
        )
        date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=date_var, width=22).grid(
            row=4, column=1, sticky=tk.W, pady=5,
        )

        # Notes
        ttk.Label(frame, text="Notes (optional):").grid(
            row=5, column=0, sticky=tk.W, pady=5,
        )
        notes_var = tk.StringVar()
        ttk.Entry(frame, textvariable=notes_var, width=22).grid(
            row=5, column=1, sticky=tk.W, pady=5,
        )

        def _on_book():
            booking_date = date_var.get().strip()
            notes = notes_var.get().strip()

            if not booking_date:
                messagebox.showwarning(
                    "Missing Date",
                    "Please enter a booking date in YYYY-MM-DD format.",
                    parent=dialog,
                )
                return

            # Basic date format validation
            parts = booking_date.split('-')
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                messagebox.showwarning(
                    "Invalid Date",
                    "Date must be in YYYY-MM-DD format (e.g. 2026-03-15).",
                    parent=dialog,
                )
                return

            try:
                booking_id = self.service.book_office_hour(
                    office_hour_id=oh_id,
                    student_id=student_id,
                    booking_date=booking_date,
                    notes=notes,
                )
                messagebox.showinfo(
                    "Success",
                    f"Appointment booked successfully (Booking ID: {booking_id}).",
                    parent=dialog,
                )
                dialog.destroy()
                self._refresh_bookings()

                # Email both student and instructor
                self._send_booking_emails(
                    student_id=student_id,
                    instructor_id=instructor,
                    day=day,
                    start_time=start,
                    end_time=end,
                    location=location,
                    booking_date=booking_date,
                )
            except ValueError as e:
                messagebox.showwarning("Booking Error", str(e), parent=dialog)
            except Exception as e:
                logger.error("Error booking appointment: %s", e)
                messagebox.showerror(
                    "Error",
                    f"Failed to book appointment:\n{e}",
                    parent=dialog,
                )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Book", command=_on_book).pack(
            side=tk.LEFT, padx=10,
        )
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.LEFT, padx=10,
        )

    # ------------------------------------------------------------------ #
    #  Cancel selected
    # ------------------------------------------------------------------ #

    def _cancel_selected(self):
        """Cancel the booking selected in the bookings tree."""
        selected = self.bookings_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select a booking to cancel.",
            )
            return

        values = self.bookings_tree.item(selected[0], 'values')
        booking_id = int(values[0])
        status = values[6]

        if status != 'confirmed':
            messagebox.showinfo(
                "Cannot Cancel",
                f"This booking has status '{status}' and cannot be cancelled.",
            )
            return

        student_id = self._get_student_id()
        if not student_id:
            messagebox.showwarning(
                "Not Logged In",
                "You must be logged in to cancel a booking.",
            )
            return

        instructor = values[1]
        day = values[2]
        time_str = values[3]
        date = values[5]

        confirm = messagebox.askyesno(
            "Confirm Cancellation",
            f"Cancel booking {booking_id}?\n\n"
            f"Instructor: {instructor}\n"
            f"Schedule: {day} {time_str}\n"
            f"Date: {date}",
        )
        if not confirm:
            return

        try:
            success = self.service.cancel_booking(booking_id, student_id)
            if success:
                messagebox.showinfo("Success", "Booking cancelled successfully.")
                self._refresh_bookings()

                # Email both parties about cancellation
                self._send_cancellation_emails(
                    student_id=student_id,
                    instructor_id=instructor,
                    day=day,
                    time_str=time_str,
                    booking_date=date,
                )
            else:
                messagebox.showwarning(
                    "Not Cancelled",
                    "Booking not found or could not be cancelled.\n"
                    "It may have already been cancelled.",
                )
        except Exception as e:
            logger.error("Error cancelling booking %s: %s", booking_id, e)
            messagebox.showerror(
                "Error", f"Failed to cancel booking:\n{e}",
            )

    # ------------------------------------------------------------------ #
    #  Email notifications
    # ------------------------------------------------------------------ #

    def _send_booking_emails(self, student_id, instructor_id, day, start_time,
                             end_time, location, booking_date):
        """Email both the student and the instructor about the booking."""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            from education_system.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Get student info
                student_row = conn.execute(
                    "SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                    (student_id,)
                ).fetchone()

                if not student_row:
                    student_row = conn.execute(
                        "SELECT first_name, last_name, email FROM users WHERE username = ? OR id = ?",
                        (student_id, student_id)
                    ).fetchone()

                # Get instructor info
                instructor_row = conn.execute(
                    "SELECT first_name, last_name, email FROM users WHERE username = ? OR id = ?",
                    (instructor_id, instructor_id)
                ).fetchone()

            student_name = f"{student_row[0]} {student_row[1]}" if student_row else student_id
            student_email = student_row[2] if student_row else None

            instructor_name = f"{instructor_row[0]} {instructor_row[1]}" if instructor_row else instructor_id
            instructor_email = instructor_row[2] if instructor_row else None

            meeting_details = (
                f"Date: {booking_date}\n"
                f"Day: {day}\n"
                f"Time: {start_time} - {end_time}\n"
                f"Location: {location}\n"
            )

            # Email student
            if student_email:
                send_email(
                    recipient_email=student_email,
                    subject=f"Office Hours Booking Confirmed - {booking_date}",
                    body=(
                        f"Dear {student_name},\n\n"
                        f"Your office hours appointment has been confirmed:\n\n"
                        f"Instructor: {instructor_name}\n"
                        f"{meeting_details}\n"
                        f"Please arrive on time. If you need to cancel, please do so "
                        f"through the Office Hours Management system.\n\n"
                        f"Best regards,\nAcademic Administration"
                    )
                )

            # Email instructor
            if instructor_email:
                send_email(
                    recipient_email=instructor_email,
                    subject=f"Office Hours Booking - {student_name} on {booking_date}",
                    body=(
                        f"Dear {instructor_name},\n\n"
                        f"A student has booked an office hours appointment with you:\n\n"
                        f"Student: {student_name} ({student_id})\n"
                        f"{meeting_details}\n"
                        f"Best regards,\nAcademic Administration"
                    )
                )

        except Exception as e:
            logger.warning("Failed to send booking emails: %s", e)

    def _send_cancellation_emails(self, student_id, instructor_id, day, time_str,
                                   booking_date):
        """Email both the student and the instructor about a cancelled booking."""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            from education_system.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                student_row = conn.execute(
                    "SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                    (student_id,)
                ).fetchone()
                if not student_row:
                    student_row = conn.execute(
                        "SELECT first_name, last_name, email FROM users WHERE username = ? OR id = ?",
                        (student_id, student_id)
                    ).fetchone()

                instructor_row = conn.execute(
                    "SELECT first_name, last_name, email FROM users WHERE username = ? OR id = ?",
                    (instructor_id, instructor_id)
                ).fetchone()

            student_name = f"{student_row[0]} {student_row[1]}" if student_row else student_id
            student_email = student_row[2] if student_row else None
            instructor_name = f"{instructor_row[0]} {instructor_row[1]}" if instructor_row else instructor_id
            instructor_email = instructor_row[2] if instructor_row else None

            details = (
                f"Date: {booking_date}\n"
                f"Day: {day}\n"
                f"Time: {time_str}\n"
            )

            if student_email:
                send_email(
                    recipient_email=student_email,
                    subject=f"Office Hours Booking Cancelled - {booking_date}",
                    body=(
                        f"Dear {student_name},\n\n"
                        f"Your office hours appointment has been cancelled:\n\n"
                        f"Instructor: {instructor_name}\n"
                        f"{details}\n"
                        f"If you need to rebook, please visit the Office Hours Management system.\n\n"
                        f"Best regards,\nAcademic Administration"
                    )
                )

            if instructor_email:
                send_email(
                    recipient_email=instructor_email,
                    subject=f"Office Hours Booking Cancelled - {student_name} on {booking_date}",
                    body=(
                        f"Dear {instructor_name},\n\n"
                        f"A student has cancelled their office hours appointment:\n\n"
                        f"Student: {student_name} ({student_id})\n"
                        f"{details}\n"
                        f"Best regards,\nAcademic Administration"
                    )
                )

        except Exception as e:
            logger.warning("Failed to send cancellation emails: %s", e)
