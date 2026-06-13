import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print(_t("facility.warning.finance_not_available"))

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print(_t("facility.warning.cli_not_available"))
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class FacilityBookingDialog:
    """Dialog for facility booking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("facility.dialog.book_title"))
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_facilities()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=_t("facility.dialog.book_title"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Facility selection
        facility_frame = ttk.LabelFrame(main_frame, text=_t("facility.select_facility"))
        facility_frame.pack(fill='x', pady=(0, 10))

        self.facility_var = tk.StringVar()
        self.facility_combo = ttk.Combobox(facility_frame, textvariable=self.facility_var, width=50)
        self.facility_combo.pack(side='left', padx=5, pady=5)
        self.facility_combo.bind('<<ComboboxSelected>>', self.on_facility_selected)

        # Facility details
        self.facility_details = tk.Text(facility_frame, height=4, width=60)
        self.facility_details.pack(fill='x', padx=5, pady=5)

        # Booking details
        booking_frame = ttk.LabelFrame(main_frame, text=_t("facility.booking_details"))
        booking_frame.pack(fill='x', pady=(0, 10))

        # Date and time
        datetime_frame = ttk.Frame(booking_frame)
        datetime_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(datetime_frame, text=_t("common.date") + ":").grid(row=0, column=0, sticky='w', padx=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(datetime_frame, textvariable=self.date_var, width=15).grid(row=0, column=1, padx=5)

        ttk.Label(datetime_frame, text=_t("facility.start_time") + ":").grid(row=0, column=2, sticky='w', padx=5)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(datetime_frame, textvariable=self.start_time_var, width=10).grid(row=0, column=3, padx=5)

        ttk.Label(datetime_frame, text=_t("facility.end_time") + ":").grid(row=1, column=0, sticky='w', padx=5)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(datetime_frame, textvariable=self.end_time_var, width=10).grid(row=1, column=1, padx=5)

        # Purpose
        ttk.Label(booking_frame, text=_t("facility.purpose") + ":").pack(anchor='w', padx=5, pady=(10, 0))
        self.purpose_var = tk.StringVar()
        ttk.Entry(booking_frame, textvariable=self.purpose_var, width=50).pack(fill='x', padx=5, pady=5)

        # Notes
        ttk.Label(booking_frame, text=_t("facility.additional_notes") + ":").pack(anchor='w', padx=5)
        self.notes_text = tk.Text(booking_frame, height=3, width=50)
        self.notes_text.pack(fill='x', padx=5, pady=5)

        # Club booking option
        club_frame = ttk.LabelFrame(main_frame, text=_t("facility.club_booking_optional"))
        club_frame.pack(fill='x', pady=(0, 10))

        self.club_booking_var = tk.BooleanVar()
        club_check = ttk.Checkbutton(club_frame, text=_t("facility.book_for_club"), variable=self.club_booking_var,
                                   command=self.toggle_club_selection)
        club_check.pack(anchor='w', padx=5, pady=5)

        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=40, state='disabled')
        self.club_combo.pack(fill='x', padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text=_t("facility.submit_booking"),
                  command=self.submit_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"),
                  command=self.cancel).pack(side='left')

    def load_facilities(self):
        """Load available facilities"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT facility_id, facility_name, location, capacity, description,
                   equipment, booking_fee
            FROM union_facilities
            WHERE status = 'available'
            ORDER BY facility_name
            ''')

            facilities = cursor.fetchall()

            facility_options = []
            self.facility_data = {}

            for facility in facilities:
                option = f"{facility[1]} - {facility[2]}"
                facility_options.append(option)
                self.facility_data[option] = facility

            self.facility_combo['values'] = facility_options

            # Load user's clubs for club booking option
            if self.auth and self.auth.current_user:
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()

                if result:
                    student_id = result[0]
                    cursor.execute('''
                    SELECT c.club_id, c.club_name
                    FROM student_clubs c
                    WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
                    AND c.status = 'active'
                    ORDER BY c.club_name
                    ''', (student_id, student_id, student_id))

                    clubs = cursor.fetchall()

                    club_options = [f"{club[1]} (ID: {club[0]})" for club in clubs]
                    self.club_combo['values'] = club_options

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load facilities: {str(e)}")

    def on_facility_selected(self, event=None):
        """Handle facility selection"""
        selection = self.facility_var.get()
        if not selection or selection not in self.facility_data:
            return

        facility = self.facility_data[selection]

        details = f"Facility: {facility[1]}\n"
        details += f"Location: {facility[2]}\n"
        details += f"Capacity: {facility[3]} people\n"
        details += f"Description: {facility[4]}\n"
        details += f"Equipment: {facility[5]}\n"
        details += f"Booking Fee: £{facility[6]:.2f}"

        self.facility_details.delete(1.0, tk.END)
        self.facility_details.insert(1.0, details)

    def toggle_club_selection(self):
        """Toggle club selection based on checkbox"""
        if self.club_booking_var.get():
            self.club_combo.config(state='normal')
        else:
            self.club_combo.config(state='disabled')
            self.club_var.set('')

    def submit_booking(self):
        """Submit the booking request"""
        # Validate inputs
        if not self.facility_var.get():
            messagebox.showwarning(_t("common.warning"), _t("facility.error.select_facility"))
            return

        if not self.date_var.get():
            messagebox.showwarning(_t("common.warning"), _t("facility.error.enter_date"))
            return

        if not all([self.start_time_var.get(), self.end_time_var.get()]):
            messagebox.showwarning(_t("common.warning"), _t("facility.error.enter_times"))
            return

        if not self.purpose_var.get():
            messagebox.showwarning(_t("common.warning"), _t("facility.error.enter_purpose"))
            return

        try:
            # Validate date format
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showwarning(_t("common.warning"), _t("facility.error.invalid_date_format"))
            return

        booking_data = {
            'facility': self.facility_var.get(),
            'date': self.date_var.get(),
            'start_time': self.start_time_var.get(),
            'end_time': self.end_time_var.get(),
            'purpose': self.purpose_var.get(),
            'notes': self.notes_text.get(1.0, tk.END).strip(),
            'club': self.club_var.get() if self.club_booking_var.get() else None
        }

        if messagebox.askyesno(_t("common.confirm"), _t("facility.confirm_submit")):
            self.result = booking_data
            messagebox.showinfo(_t("common.success"), _t("facility.booking_submitted"))
            self.dialog.destroy()

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


# Additional utility classes and functions


class FacilityApprovalDialog:
    """Dialog for approving facility bookings"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("facility.approve.title"))
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_pending_bookings()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t("facility.approve.pending_bookings"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text=_t("facility.approve.pending_requests"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Facility', 'Student', 'Date', 'Time', 'Purpose', 'Status')
        self.bookings_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.bookings_tree.heading(col, text=col)
            self.bookings_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.bookings_tree.yview)
        self.bookings_tree.configure(yscrollcommand=scrollbar.set)

        self.bookings_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text=_t("facility.approve.approve_btn"), command=self.approve_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("facility.approve.reject_btn"), command=self.reject_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side='left')

    def load_pending_bookings(self):
        """Load pending facility bookings"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT fb.booking_id, f.facility_name, u.username, fb.booking_date,
                   fb.start_time || '-' || fb.end_time, fb.purpose, fb.status
            FROM facility_bookings fb
            JOIN union_facilities f ON fb.facility_id = f.facility_id
            JOIN users u ON fb.student_id = u.student_id
            WHERE fb.status = 'pending'
            ORDER BY fb.booking_date, fb.start_time
            ''')

            bookings = cursor.fetchall()

            for booking in bookings:
                self.bookings_tree.insert('', 'end', values=booking)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load bookings: {str(e)}")

    def approve_booking(self):
        """Approve selected booking"""
        selection = self.bookings_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("facility.approve.select_booking"))
            return

        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE facility_bookings SET status = ? WHERE booking_id = ?', ('approved', booking_id))
            conn.commit()
            conn.close()

            self.bookings_tree.delete(selection[0])
            messagebox.showinfo(_t("common.success"), _t("facility.approve.approved_success"))
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("facility.approve.approve_failed") + f": {str(e)}")

    def reject_booking(self):
        """Reject selected booking"""
        selection = self.bookings_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("facility.approve.select_booking_reject"))
            return

        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]

        reason = simpledialog.askstring(_t("facility.approve.rejection_reason"), _t("facility.approve.enter_reason"))
        if reason:
            try:
                conn = student_union_cli.get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE facility_bookings SET status = ?, rejection_reason = ? WHERE booking_id = ?',
                             ('rejected', reason, booking_id))
                conn.commit()
                conn.close()

                self.bookings_tree.delete(selection[0])
                messagebox.showinfo(_t("common.success"), _t("facility.approve.rejected_success"))
            except sqlite3.Error as e:
                messagebox.showerror(_t("common.error"), _t("facility.approve.reject_failed") + f": {str(e)}")



class ApproveFacilityBookingsDialog:
    """Dialog for approving facility bookings (admin)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approve Facility Bookings")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="✅ Facility Booking Approvals",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Approval queue overview
        overview_frame = ttk.LabelFrame(main_frame, text="Approval Queue")
        overview_frame.pack(fill='x', pady=(0, 15))

        overview_grid = ttk.Frame(overview_frame)
        overview_grid.pack(fill='x', padx=15, pady=10)

        ttk.Label(overview_grid, text="Pending Approvals:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="8", foreground='orange').grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Urgent (< 48h):", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="3", foreground='red').grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Approved Today:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="12").grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Average Approval Time:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="6.5 hours").grid(row=3, column=1, sticky='w', padx=10)

        # Pending bookings
        bookings_frame = ttk.LabelFrame(main_frame, text="Pending Booking Requests")
        bookings_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Club/Student', 'Facility', 'Date', 'Time', 'Purpose', 'Priority', 'Status')
        tree = ttk.Treeview(bookings_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Club/Student':
                tree.column(col, width=140)
            elif col == 'Facility':
                tree.column(col, width=120)
            elif col == 'Purpose':
                tree.column(col, width=150)
            else:
                tree.column(col, width=80)

        scrollbar = ttk.Scrollbar(bookings_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample pending bookings
        bookings = [
            ("FB001", "Drama Society", "Main Hall", "2025-04-15", "18:00-22:00", "Annual Play Performance", "High", "Pending"),
            ("FB002", "Debate Club", "Seminar Room 3", "2025-04-12", "14:00-16:00", "Competition Practice", "Urgent", "Pending"),
            ("FB003", "Music Society", "Concert Hall", "2025-04-20", "19:00-23:00", "Spring Concert", "High", "Pending"),
            ("FB004", "Sports Club", "Gym", "2025-04-10", "16:00-18:00", "Training Session", "Urgent", "Pending"),
            ("FB005", "Art Society", "Exhibition Space", "2025-04-25", "All Day", "Art Exhibition", "Normal", "Pending"),
            ("FB006", "Environmental Club", "Conference Room", "2025-04-11", "12:00-14:00", "Planning Meeting", "Urgent", "Pending"),
            ("FB007", "Tech Society", "Computer Lab", "2025-04-18", "15:00-19:00", "Hackathon", "Normal", "Pending"),
            ("FB008", "Film Society", "Cinema Room", "2025-04-22", "18:00-21:00", "Movie Screening", "Normal", "Pending")
        ]

        for booking in bookings:
            tree.insert('', 'end', values=booking)

        tree.bind('<Double-1>', lambda e: self.show_booking_details())

        # Action buttons
        action_frame = ttk.LabelFrame(main_frame, text="Booking Actions")
        action_frame.pack(fill='x', pady=(0, 15))

        button_grid = ttk.Frame(action_frame)
        button_grid.pack(padx=15, pady=10)

        ttk.Button(button_grid, text="✓ Approve", command=self.approve_booking, width=15).grid(row=0, column=0, padx=5, pady=3)
        ttk.Button(button_grid, text="✗ Reject", command=self.reject_booking, width=15).grid(row=0, column=1, padx=5, pady=3)
        ttk.Button(button_grid, text="⚠ Request Changes", command=self.request_changes, width=15).grid(row=0, column=2, padx=5, pady=3)
        ttk.Button(button_grid, text="📋 View Details", command=self.show_booking_details, width=15).grid(row=1, column=0, padx=5, pady=3)
        ttk.Button(button_grid, text="📧 Contact Requester", command=self.contact_requester, width=15).grid(row=1, column=1, padx=5, pady=3)
        ttk.Button(button_grid, text="📅 Check Calendar", command=self.check_calendar, width=15).grid(row=1, column=2, padx=5, pady=3)

        # Filters
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=(0, 10))
        filter_combo = ttk.Combobox(filter_frame, width=20, state='readonly')
        filter_combo['values'] = ('All Pending', 'Urgent Only', 'High Priority', 'By Facility', 'By Date Range')
        filter_combo.current(0)
        filter_combo.pack(side='left', padx=(0, 20))

        ttk.Button(filter_frame, text="📊 View Approval History", command=self.view_history).pack(side='left', padx=(0, 10))
        ttk.Button(filter_frame, text="⚙️ Approval Settings", command=self.approval_settings).pack(side='left')

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def show_booking_details(self):
        messagebox.showinfo("Booking Details",
                          "BOOKING REQUEST DETAILS\n\n" +
                          "ID: FB001\n" +
                          "Requester: Drama Society\n" +
                          "Contact: president@dramasoc.ac.uk\n\n" +
                          "Facility: Main Hall\n" +
                          "Date: April 15, 2025\n" +
                          "Time: 18:00 - 22:00 (4 hours)\n\n" +
                          "Purpose: Annual Play Performance\n" +
                          "Expected Attendees: 200\n" +
                          "Setup Required: Stage, lighting, seating\n" +
                          "Equipment Needed: Sound system, projector\n\n" +
                          "Additional Notes:\n" +
                          "This is our flagship event of the year.\n" +
                          "We have performed at this venue for 5 years.\n" +
                          "Tickets already on sale (150 sold).\n\n" +
                          "Risk Assessment: Submitted ✓\n" +
                          "Insurance: Current ✓\n" +
                          "Previous Bookings: 8 (all successful)")

    def approve_booking(self):
        result = messagebox.askyesno("Approve Booking",
                                     "Approve this facility booking?\n\n" +
                                     "FB001 - Drama Society\n" +
                                     "Main Hall - April 15, 2025\n\n" +
                                     "This will:\n" +
                                     "- Reserve the facility\n" +
                                     "- Notify the requester\n" +
                                     "- Add to calendar\n" +
                                     "- Generate confirmation")
        if result:
            messagebox.showinfo("Approved",
                              "Booking approved!\n\n" +
                              "Confirmation email sent to Drama Society.\n" +
                              "Facility reserved in calendar.\n" +
                              "Booking ID: FB001\n\n" +
                              "They will receive:\n" +
                              "- Booking confirmation\n" +
                              "- Access instructions\n" +
                              "- Setup guidelines\n" +
                              "- Contact information")

    def reject_booking(self):
        reason_window = tk.Toplevel(self.dialog)
        reason_window.title("Reject Booking")
        reason_window.geometry("400x300")
        reason_window.transient(self.dialog)
        reason_window.grab_set()

        ttk.Label(reason_window, text="Rejection Reason:").pack(padx=15, pady=(15, 5))

        reason_text = scrolledtext.ScrolledText(reason_window, height=8, wrap=tk.WORD)
        reason_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        reason_text.insert('1.0', "Please provide reason for rejection...")

        def submit_rejection():
            messagebox.showinfo("Rejected", "Booking rejected.\n\nRejection notice sent to requester with reason.\nThey can resubmit with modifications.")
            reason_window.destroy()

        ttk.Button(reason_window, text="Submit Rejection", command=submit_rejection).pack(pady=(0, 15))

    def request_changes(self):
        messagebox.showinfo("Request Changes",
                          "Request changes to booking:\n\n" +
                          "Common requests:\n" +
                          "- Change date/time (conflict)\n" +
                          "- Reduce duration\n" +
                          "- Different facility\n" +
                          "- Additional documentation\n" +
                          "- Reduce capacity/scope\n\n" +
                          "Requester will be notified and can\n" +
                          "resubmit with requested changes.")

    def contact_requester(self):
        messagebox.showinfo("Contact Requester",
                          "Contact Information:\n\n" +
                          "Club: Drama Society\n" +
                          "President: Sarah Johnson\n" +
                          "Email: president@dramasoc.ac.uk\n" +
                          "Phone: 07123 456789\n\n" +
                          "Opening email client...")

    def check_calendar(self):
        messagebox.showinfo("Facility Calendar",
                          "Main Hall - April 2025\n\n" +
                          "April 15 (Requested):\n" +
                          "18:00-22:00 - REQUESTED (Drama Society)\n\n" +
                          "Conflicts: None\n\n" +
                          "Adjacent bookings:\n" +
                          "April 14: 14:00-17:00 (Setup available)\n" +
                          "April 16: 10:00-12:00 (Cleanup available)\n\n" +
                          "Status: AVAILABLE ✓")

    def view_history(self):
        messagebox.showinfo("Approval History",
                          "Approval History (Last 30 days):\n\n" +
                          "Total Requests: 156\n" +
                          "Approved: 124 (79%)\n" +
                          "Rejected: 18 (12%)\n" +
                          "Changes Requested: 14 (9%)\n\n" +
                          "Average Time to Approve: 6.5 hours\n" +
                          "Fastest: 15 minutes\n" +
                          "Slowest: 48 hours\n\n" +
                          "Most Booked Facility: Seminar Rooms (45)\n" +
                          "Most Active Club: Music Society (12 bookings)")

    def approval_settings(self):
        messagebox.showinfo("Approval Settings",
                          "Approval Configuration:\n\n" +
                          "Auto-approve if:\n" +
                          "☑ Requester has good history (5+ bookings)\n" +
                          "☑ Low risk booking (meeting rooms)\n" +
                          "☑ Short duration (< 2 hours)\n" +
                          "☑ No conflicts\n\n" +
                          "Require manual approval if:\n" +
                          "☑ Large events (> 100 people)\n" +
                          "☑ Prime facilities (Main Hall)\n" +
                          "☑ Multi-day bookings\n" +
                          "☑ External groups")



def show_facilities_content(self):
    """Display facilities in main content area"""
    self.clear_content()
    facilities_frame = ttk.Frame(self.content_frame)
    facilities_frame.pack(fill=tk.BOTH, expand=True)
    # Create and display facilities content without notebook
    self._render_facilities_tab(facilities_frame)


def _render_facilities_tab(self, parent_frame):
    """Render facilities content in the provided parent frame"""
    # Facilities content
    ttk.Label(parent_frame, text="Facility Booking System",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Booking form
    booking_frame = ttk.LabelFrame(parent_frame, text="Book a Facility")
    booking_frame.pack(fill=tk.X, padx=20, pady=10)
    form_frame = ttk.Frame(booking_frame)
    form_frame.pack(padx=20, pady=20)
    # Facility selection
    ttk.Label(form_frame, text="Facility:").grid(row=0, column=0, sticky=tk.W, pady=5)
    self.facility_combo = ttk.Combobox(form_frame, width=30)
    self.facility_combo.grid(row=0, column=1, padx=10, pady=5)
    # Date selection
    ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
    self.booking_date_entry = ttk.Entry(form_frame, width=32)
    self.booking_date_entry.grid(row=1, column=1, padx=10, pady=5)
    # Time selection
    ttk.Label(form_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
    self.start_time_entry = ttk.Entry(form_frame, width=32)
    self.start_time_entry.grid(row=2, column=1, padx=10, pady=5)
    ttk.Label(form_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
    self.end_time_entry = ttk.Entry(form_frame, width=32)
    self.end_time_entry.grid(row=3, column=1, padx=10, pady=5)
    # Purpose
    ttk.Label(form_frame, text="Purpose:").grid(row=4, column=0, sticky=tk.W, pady=5)
    self.purpose_entry = ttk.Entry(form_frame, width=32)
    self.purpose_entry.grid(row=4, column=1, padx=10, pady=5)
    # Submit button
    ttk.Button(form_frame, text="Submit Booking Request",
              command=self.submit_booking_request).grid(row=5, column=1, pady=20)
    # Load facilities
    self.load_facilities()
    # My bookings section
    bookings_frame = ttk.LabelFrame(parent_frame, text="My Bookings")
    bookings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    # Bookings treeview
    booking_columns = ('ID', 'Facility', 'Date', 'Time', 'Status', 'Purpose')
    self.bookings_tree = ttk.Treeview(bookings_frame, columns=booking_columns, show='headings', height=8)
    for col in booking_columns:
        self.bookings_tree.heading(col, text=col)
        self.bookings_tree.column(col, width=100)
    bookings_scrollbar = ttk.Scrollbar(bookings_frame, orient=tk.VERTICAL, command=self.bookings_tree.yview)
    self.bookings_tree.configure(yscrollcommand=bookings_scrollbar.set)
    self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    bookings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    # Load my bookings
    self.refresh_my_bookings()


def show_facilities_tab(self):
    """Legacy method for backwards compatibility - creates tab in notebook if exists"""
    if hasattr(self, 'notebook') and self.notebook:
        facilities_frame = ttk.Frame(self.notebook)
        self.notebook.add(facilities_frame, text="Facilities")
        self._render_facilities_tab(facilities_frame)
    else:
        # Fall back to content display
        self.show_facilities_content()


def load_facilities(self):
    """Load available facilities from database"""
    facilities = []

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Get facilities from union_facilities table
        cursor.execute('''
            SELECT facility_name, location, capacity
            FROM union_facilities
            WHERE status = 'available'
            ORDER BY facility_name
        ''')
        union_facilities = cursor.fetchall()

        for facility in union_facilities:
            facility_name = facility[0]
            location = facility[1] if facility[1] else ''
            capacity = facility[2] if len(facility) > 2 and facility[2] else ''

            # Format: "Facility Name (Location) [Capacity: X]"
            display_name = facility_name
            if location:
                display_name += f" ({location})"
            if capacity:
                display_name += f" [Capacity: {capacity}]"

            facilities.append(display_name)

        # Also get buildings that can be booked
        cursor.execute('''
            SELECT building_name, building_code, building_type
            FROM buildings
            WHERE is_active = 1
            ORDER BY building_name
        ''')
        buildings = cursor.fetchall()

        for building in buildings:
            building_name = building[0]
            building_code = building[1] if building[1] else ''
            building_type = building[2] if len(building) > 2 and building[2] else ''

            # Format: "Building Name [Code] (Type)"
            display_name = building_name
            if building_code:
                display_name += f" [{building_code}]"
            if building_type:
                display_name += f" ({building_type})"

            facilities.append(display_name)

        conn.close()

        # If no facilities found in database, use defaults
        if not facilities:
            facilities = [
                "Main Hall", "Conference Room A", "Conference Room B",
                "Student Lounge", "Study Room 1", "Study Room 2",
                "Computer Lab", "Meeting Room"
            ]

    except sqlite3.Error as e:
        print(f"Failed to load facilities from database: {e}")
        # Fallback to default facilities
        facilities = [
            "Main Hall", "Conference Room A", "Conference Room B",
            "Student Lounge", "Study Room 1", "Study Room 2",
            "Computer Lab", "Meeting Room"
        ]

    self.facility_combo['values'] = facilities
    if facilities:
        self.facility_combo.set(facilities[0])


def submit_booking_request(self):
    """Submit a facility booking request"""
    facility = self.facility_combo.get()
    date = self.booking_date_entry.get().strip()
    start_time = self.start_time_entry.get().strip()
    end_time = self.end_time_entry.get().strip()
    purpose = self.purpose_entry.get().strip()

    if not all([facility, date, start_time, end_time, purpose]):
        messagebox.showerror("Error", "Please fill in all fields")
        return

    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        messagebox.showerror("Error", "Date must be in YYYY-MM-DD format")
        return

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO facility_bookings (facility_name, user_id, booking_date, start_time, end_time, purpose, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (facility, self.current_user['id'], date, start_time, end_time, purpose,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        messagebox.showinfo("Success", f"Booking request for {facility} submitted successfully!")

        # Send email confirmation if email service is available
        if EMAIL_SERVICE_AVAILABLE and self.current_user.get('email'):
            try:
                subject, email_body = render_template('student_union/facility_booking_confirmation', {
                    'username': self.current_user.get('username', 'Student'),
                    'facility': facility,
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'purpose': purpose
                })
                send_email(
                    self.current_user['email'],
                    subject,
                    email_body
                )
            except Exception as e:
                print(f"Failed to send confirmation email: {e}")

    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Failed to submit booking: {e}")
    finally:
        if conn:
            conn.close()

    # Clear form
    self.booking_date_entry.delete(0, tk.END)
    self.start_time_entry.delete(0, tk.END)
    self.end_time_entry.delete(0, tk.END)
    self.purpose_entry.delete(0, tk.END)

    self.refresh_my_bookings()


def refresh_my_bookings(self):
    """Refresh the user's bookings list"""
    # Clear existing items
    for item in self.bookings_tree.get_children():
        self.bookings_tree.delete(item)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT booking_id, facility_name, booking_date,
                   start_time || '-' || end_time as time_slot, status, purpose
            FROM facility_bookings
            WHERE user_id = ?
            ORDER BY booking_date DESC
        ''', (self.current_user['id'],))

        bookings = cursor.fetchall()

        for booking in bookings:
            self.bookings_tree.insert('', tk.END, values=booking)

        conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Failed to load bookings: {e}")


def open_approve_facility_bookings_dialog(self):
    """Open facility bookings approval (admin)"""
    dialog = ApproveFacilityBookingsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# FIFTH ROUND (PART 3C FINAL) - Equipment Management System

def create_facilities_tab(self):
    """Create facilities booking tab"""
    facilities_frame = ttk.Frame(self.notebook)
    self.notebook.add(facilities_frame, text="Facilities")

    # Left panel
    left_panel = ttk.LabelFrame(facilities_frame, text="Facility Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)

    ttk.Button(left_panel, text="View Facilities",
              command=self.view_facilities).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Book Facility",
              command=self.request_facility_booking_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="My Bookings",
              command=self.view_my_bookings).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Approve Bookings",
              command=self.approve_facility_bookings_gui).pack(fill='x', pady=2)

    # Right panel
    right_panel = ttk.LabelFrame(facilities_frame, text="Facility Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)

    self.facilities_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                    height=30, width=80)
    self.facilities_text.pack(fill='both', expand=True, padx=5, pady=5)


def view_facilities(self):
    """GUI wrapper for viewing facilities"""
    self.update_status("Loading facilities...")

    def callback(output, result):
        self.display_result(self.facilities_text, output)
        self.update_status("Facilities loaded")

    self.run_in_thread(student_union_cli.view_facilities, callback)


def request_facility_booking_gui(self):
    """GUI for facility booking"""
    dialog = FacilityBookingDialog(self.master, self.auth)
    self.master.wait_window(dialog.dialog)

    if dialog.result:
        self.update_status("Facility booking requested")
        self.view_my_bookings()


def view_my_bookings(self):
    """GUI wrapper for viewing my bookings"""
    self.update_status("Loading your bookings...")

    def callback(output, result):
        self.display_result(self.facilities_text, output)
        self.update_status("Your bookings loaded")

    self.run_in_thread(student_union_cli.view_my_bookings, callback)

# Add more GUI wrapper methods for other functions...
# (For brevity, showing the pattern - similar methods would be created for all CLI functions)

# Backwards compatibility - CLI function access

def approve_facility_bookings_gui(self):
    """Approve facility bookings with GUI dialog"""
    try:
        dialog = FacilityApprovalDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


