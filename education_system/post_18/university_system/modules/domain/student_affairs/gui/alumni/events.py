from education_system.post_18.university_system.core.sql_safety import escape_like
import tkinter as tk
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni._service_imports import (
    init_alumni_db, register_alumni, view_alumni, update_alumni,
    view_events, create_enhanced_event, event_check_in_system,
    record_donation, view_donations, setup_mentorship, view_mentorships,
    search_alumni_directory, view_connection_requests, manage_business_directory,
    create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
    schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
    view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
    manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
    generate_alumni_report, set_auth, setup_alumni_permissions,
    smart_mentorship_matching, generate_engagement_recommendations,
    create_alumni_story, view_alumni_stories, get_connection,
)



class EventsMixin:
        def _cancel_registration(self):
            """Cancel a registration"""
            if not hasattr(self, 'my_registrations_tree'):
                return

            selection = self.my_registrations_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a registration to cancel.")
                return

            if messagebox.askyesno("Confirm Cancellation",
                                   "Are you sure you want to cancel this registration?"):
                messagebox.showinfo("Success", "Registration cancelled successfully!")
                self.view_my_event_registrations()  # Refresh

        def _get_event_options(self):
            """Retrieve available alumni events for photo uploads."""
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_id, title
                FROM unified_events
                WHERE source_type = 'alumni'
                ORDER BY COALESCE(start_datetime, title)
                """
            )
            rows = cursor.fetchall()
            conn.close()
            return rows

        def _perform_event_search(self):
            """Perform the event search with specified criteria"""
            try:
                # Clear existing results
                for item in self.event_search_tree.get_children():
                    self.event_search_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    # Build query
                    query = ("SELECT title, start_datetime, location, event_type, "
                             "event_fee, max_capacity, status FROM unified_events "
                             "WHERE source_type = 'alumni'")
                    params = []

                    # Add keyword filter
                    keyword = self.event_search_keyword.get().strip()
                    if keyword:
                        query += " AND (title LIKE ? OR description LIKE ?)"
                        params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

                    # Add type filter
                    event_type = self.event_search_type.get()
                    if event_type != "All":
                        query += " AND event_type = ?"
                        params.append(event_type)

                    # Add location filter
                    location = self.event_search_location.get().strip()
                    if location:
                        query += " AND location LIKE ?"
                        params.append(f"%{escape_like(location)}%")

                    # Add date range filter
                    date_range = self.event_date_range.get()
                    if date_range == "Next 7 Days":
                        query += " AND start_datetime BETWEEN datetime('now') AND datetime('now', '+7 days')"
                    elif date_range == "Next 30 Days":
                        query += " AND start_datetime BETWEEN datetime('now') AND datetime('now', '+30 days')"
                    elif date_range == "Next 3 Months":
                        query += " AND start_datetime BETWEEN datetime('now') AND datetime('now', '+3 months')"
                    elif date_range == "This Year":
                        query += " AND strftime('%Y', start_datetime) = strftime('%Y', 'now')"
                    elif date_range == "Past Events":
                        query += " AND start_datetime < datetime('now')"

                    # Add free events filter
                    if self.event_free_only.get():
                        query += " AND (event_fee = 0 OR event_fee IS NULL)"

                    query += " ORDER BY start_datetime ASC"

                    cursor.execute(query, params)
                    results = cursor.fetchall()

                    for event in results:
                        # Format the fee
                        formatted = list(event)
                        if formatted[4]:  # fee column
                            formatted[4] = f"£{formatted[4]:.2f}"
                        else:
                            formatted[4] = "Free"

                        self.event_search_tree.insert('', tk.END, values=formatted)

                    self.update_status(f"Found {len(results)} event(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Search failed: {str(e)}")

        def _view_search_event_details(self):
            """View details for selected event from search results"""
            if not hasattr(self, 'event_search_tree'):
                return

            selection = self.event_search_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an event to view details.")
                return

            item = self.event_search_tree.item(selection[0])
            event_data = item['values']

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Event Details - {event_data[0]}")
            details_window.geometry("600x500")
            details_window.configure(bg='white')

            # Display event details
            details_frame = ttk.Frame(details_window, padding=20)
            details_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(details_frame, text=event_data[0],
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            info_text = f"""
    Date: {event_data[1]}
    Location: {event_data[2]}
    Type: {event_data[3]}
    Fee: {event_data[4]}
    Capacity: {event_data[5]}
    Status: {event_data[6]}
    """
            ttk.Label(details_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))

            ttk.Button(details_frame, text="Register for Event",
                      command=lambda: [messagebox.showinfo("Success", "Registration initiated!"),
                                      details_window.destroy()]).pack(pady=10)
            ttk.Button(details_frame, text="Close",
                      command=details_window.destroy).pack()

        def clear_event_form(self):
            """Clear event form"""
            for var in self.event_vars.values():
                if isinstance(var, tk.BooleanVar):
                    var.set(False)
                else:
                    var.set("")
            self.event_description.delete(1.0, tk.END)

        def filter_events(self, filter_type):
            """Filter events based on selection"""
            self.load_events_data()  # For demo, just reload all events
            self.update_status(f"Filtered events: {filter_type}")

        def load_events_data(self):
            """Load alumni events from the database (no sample data)."""
            try:
                # Clear existing data
                for item in self.events_tree.get_children():
                    self.events_tree.delete(item)
                self._event_rows = {}

                with db_get_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT e.event_id, e.title, e.start_datetime, e.location,
                               e.event_type, e.event_fee, e.max_capacity, e.status,
                               (SELECT COUNT(*) FROM unified_event_registrations r
                                WHERE r.event_id = e.event_id) AS reg_count
                        FROM unified_events e
                        WHERE e.source_type = 'alumni'
                        ORDER BY e.start_datetime DESC
                        """
                    ).fetchall()

                for r in rows:
                    event_id, title, start_dt, loc, etype, fee, cap, status, reg_count = r
                    fee = float(fee or 0)
                    fee_str = "Free" if fee == 0 else f"£{fee:.2f}"
                    cap_str = f"{reg_count}/{cap}" if cap else str(reg_count)
                    iid = str(event_id)
                    self.events_tree.insert('', tk.END, iid=iid, values=(
                        title, start_dt or "", loc or "", etype or "",
                        fee_str, cap_str, status or "Open"))
                    self._event_rows[iid] = {
                        'event_id': event_id, 'title': title, 'fee': fee,
                        'start': start_dt, 'location': loc, 'type': etype,
                    }

                if rows:
                    self.update_status(f"Loaded {len(rows)} events")
                else:
                    self.update_status("No alumni events found")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load events: {str(e)}")

        def process_manual_checkin(self):
            """Process manual check-in"""
            if not self.selected_event.get():
                messagebox.showwarning("No Event Selected", "Please select an event first.")
                return

            alumni_id = self.checkin_alumni_id.get().strip()
            if not alumni_id:
                messagebox.showwarning("No Alumni ID", "Please enter an Alumni ID.")
                return

            # Simulate check-in process
            messagebox.showinfo("Check-in Successful", f"Alumni {alumni_id} checked in successfully!")

            # Add to attendance list
            current_time = datetime.now().strftime("%I:%M %p")
            new_entry = f"\n✅ Alumni {alumni_id} - {current_time}"
            self.attendance_text.insert(tk.END, new_entry)

            # Clear the ID field
            self.checkin_alumni_id.set("")
            self.update_status(f"Alumni {alumni_id} checked in")

        def process_qr_checkin(self):
            """Process QR code check-in"""
            qr_data = self.qr_code_data.get().strip()
            if not qr_data:
                messagebox.showwarning("No QR Data", "Please enter or scan QR code data.")
                return

            # Simulate QR processing
            if qr_data.startswith("EVENT_CHECKIN:"):
                messagebox.showinfo("QR Check-in Successful", "QR code processed successfully!")
                self.qr_code_data.set("")
            else:
                messagebox.showerror("Invalid QR Code", "Invalid QR code format.")

        def _resolve_current_alumni(self):
            """Return (user_id, student_id, email, name) for the current user,
            resolving alumni/finance links from the DB."""
            user = getattr(self, 'current_user', {}) or {}
            uid = str(user.get('username') or user.get('id') or '')
            email = (user.get('email') or '').strip()
            name = (user.get('first_name') or user.get('display_name') or uid)
            student_id = None
            try:
                with db_get_connection() as conn:
                    row = conn.execute(
                        "SELECT student_id, email_address, "
                        "TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) "
                        "FROM alumni WHERE alumni_id = ? OR student_id = ? LIMIT 1",
                        (uid, uid)).fetchone()
                    if row:
                        student_id = row[0]
                        email = email or (row[1] or "")
                        name = (row[2] or "").strip() or name
                    if not email:
                        u = conn.execute(
                            "SELECT email FROM users WHERE username = ? OR id = ? LIMIT 1",
                            (uid, uid)).fetchone()
                        if u and u[0]:
                            email = u[0]
            except sqlite3.Error:
                pass
            return uid, student_id, email, name

        def _prompt_event_payment(self, title, fee, student_id=None):
            """Modal dialog to choose a payment method for a paid event.
            Returns the chosen method, or None if cancelled."""
            win = tk.Toplevel(self.root)
            win.title("Event Payment")
            win.geometry("440x330")
            win.grab_set()
            ttk.Label(win, text=f"Payment for: {title}",
                      font=('Arial', 12, 'bold')).pack(pady=(15, 5))
            ttk.Label(win, text=f"Fee: £{fee:.2f}").pack(pady=(0, 10))

            method = tk.StringVar(value="Card")
            for m in ("Cash", "Card", "Finance Account"):
                ttk.Radiobutton(win, text=m, variable=method, value=m).pack(anchor='w', padx=50)

            # Show finance-account details from the correct table.
            bal_text = "No linked finance account (Finance Account unavailable)."
            if student_id:
                try:
                    with db_get_connection() as conn:
                        r = conn.execute(
                            "SELECT balance, currency FROM student_finance_accounts "
                            "WHERE student_id = ?", (student_id,)).fetchone()
                    if r:
                        bal_text = (f"Finance account ({student_id}) balance: "
                                    f"£{float(r[0] or 0):.2f}")
                    else:
                        bal_text = f"No finance account on file for {student_id}."
                except sqlite3.Error:
                    pass
            ttk.Label(win, text=bal_text, foreground='#555555').pack(pady=12, padx=20)

            result = {'method': None}

            def confirm():
                result['method'] = method.get()
                win.destroy()
            btns = ttk.Frame(win)
            btns.pack(pady=15)
            ttk.Button(btns, text="Confirm Payment", command=confirm).pack(side=tk.LEFT, padx=8)
            ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT)
            win.wait_window()
            return result['method']

        def _send_event_registration_email(self, email, name, title, start_dt,
                                           location, fee, payment_method):
            """Email an event-registration confirmation via the JSON template
            alumni/event_registration_confirmation. Returns True if sent."""
            email = (email or "").strip()
            if not email:
                return False
            try:
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                subject, body = render_template("alumni/event_registration_confirmation", {
                    "full_name": name,
                    "event_name": title,
                    "event_date": start_dt or "(see portal)",
                    "location": location or "(see portal)",
                    "fee": ("Free" if not fee else f"£{float(fee):.2f}"),
                    "payment_method": payment_method or "N/A",
                })
                if not subject or not body:
                    return False
                return bool(send_email(recipient_email=email, subject=subject, body=body))
            except Exception as e:
                import logging
                logging.warning(f"Event registration email failed: {e}")
                return False

        def register_for_selected_event(self):
            """Register the current user for the selected event, collecting a
            payment method if the event has a fee, then email a confirmation."""
            selection = self.events_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an event to register for.")
                return

            iid = selection[0]
            info = getattr(self, '_event_rows', {}).get(iid)
            if not info:
                messagebox.showwarning("Unavailable",
                                       "Please refresh the events list and try again.")
                return
            event_id = info['event_id']
            title = info['title']
            fee = float(info.get('fee') or 0)

            uid, student_id, email, name = self._resolve_current_alumni()

            # Prevent duplicate registration.
            try:
                with db_get_connection() as conn:
                    if conn.execute(
                        "SELECT 1 FROM unified_event_registrations "
                        "WHERE event_id = ? AND user_id = ?",
                        (event_id, uid)).fetchone():
                        messagebox.showinfo("Already Registered",
                                            f"You are already registered for {title}.")
                        return
            except sqlite3.Error:
                pass

            payment_method = None
            payment_status = 'not_required'
            paid_amount = 0.0

            if fee > 0:
                payment_method = self._prompt_event_payment(title, fee, student_id)
                if not payment_method:
                    return  # cancelled

                if payment_method == "Finance Account":
                    if not student_id:
                        messagebox.showerror(
                            "No Finance Account",
                            "No finance account is linked to your record, so the fee "
                            "cannot be paid from a finance account.")
                        return
                    try:
                        with db_get_connection() as conn:
                            bal = conn.execute(
                                "SELECT balance FROM student_finance_accounts WHERE student_id = ?",
                                (student_id,)).fetchone()
                    except sqlite3.Error as e:
                        messagebox.showerror("Database Error", f"Finance lookup failed: {e}")
                        return
                    if bal is None:
                        messagebox.showerror("No Finance Account",
                                             f"No finance account exists for {student_id}.")
                        return
                    if float(bal[0] or 0) < fee:
                        messagebox.showerror(
                            "Insufficient Funds",
                            f"Balance (£{float(bal[0] or 0):.2f}) is less than the "
                            f"fee (£{fee:.2f}).")
                        return
                    try:
                        from education_system.post_18.university_system.modules.services.finance_bus import raise_charge
                        tx = raise_charge(
                            student_id, fee, source="alumni_event",
                            description=f"Event registration: {title}",
                            reference_id=f"EVENT-{event_id}-{uid}",
                            processed_by=uid)
                        if tx is None:
                            messagebox.showerror("Payment Failed",
                                                 "Could not debit the finance account.")
                            return
                    except Exception as e:
                        messagebox.showerror("Payment Failed", f"Charge failed: {e}")
                        return
                payment_status = 'paid'
                paid_amount = fee
            else:
                if not messagebox.askyesno("Confirm Registration", f"Register for {title}?"):
                    return

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                with db_get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO unified_event_registrations
                            (event_id, user_id, user_type, registration_date,
                             attendance_status, payment_status, payment_amount, payment_method)
                        VALUES (?, ?, 'alumni', ?, 'registered', ?, ?, ?)
                        """,
                        (event_id, uid, now, payment_status, paid_amount, payment_method),
                    )
                    conn.commit()
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Registration failed: {e}")
                return

            # Book a paid event fee as revenue in the central finance system.
            if fee > 0:
                try:
                    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
                        record_revenue_to_finance,
                    )
                    record_revenue_to_finance(
                        student_id=str(student_id or 'EXTERNAL'),
                        amount=fee,
                        revenue_category="Event Fee",
                        transaction_source="Alumni",
                        transaction_ref=f"EVENT-{event_id}-{uid}",
                        payment_method=payment_method or "Unknown",
                        notes=f"Alumni event registration: {title}",
                    )
                except Exception as e:
                    import logging
                    logging.warning(f"record_revenue_to_finance failed (registration still recorded): {e}")

            emailed = self._send_event_registration_email(
                email, name, title, info.get('start'), info.get('location'), fee, payment_method)

            msg = f"You have been registered for {title}!"
            if fee > 0:
                msg += f"\nPaid £{fee:.2f} via {payment_method}."
            msg += ("\nA confirmation email has been sent."
                    if emailed else "\n(Confirmation email could not be sent.)")
            messagebox.showinfo("Registration Successful", msg)
            self.update_status("Event registration completed")
            self.load_events_data()

        def search_events(self):
            """Search and filter events with advanced criteria"""
            self.clear_content()
            self.update_status("Search Events")

            ttk.Label(self.content_frame, text="Search Events",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Search criteria frame
            search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            # Row 1: Keyword search
            keyword_frame = ttk.Frame(search_frame)
            keyword_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(keyword_frame, text="Keyword:").pack(side=tk.LEFT, padx=(0, 10))
            self.event_search_keyword = tk.StringVar()
            ttk.Entry(keyword_frame, textvariable=self.event_search_keyword,
                     width=30).pack(side=tk.LEFT, padx=(0, 20))

            ttk.Label(keyword_frame, text="Event Type:").pack(side=tk.LEFT, padx=(0, 10))
            self.event_search_type = tk.StringVar()
            type_combo = ttk.Combobox(keyword_frame, textvariable=self.event_search_type,
                                     values=["All", "In-Person", "Virtual", "Hybrid", "Networking",
                                            "Career", "Social", "Fundraising"])
            type_combo.pack(side=tk.LEFT)
            type_combo.set("All")

            # Row 2: Date range
            date_frame = ttk.Frame(search_frame)
            date_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=(0, 10))
            self.event_date_range = tk.StringVar()
            date_combo = ttk.Combobox(date_frame, textvariable=self.event_date_range,
                                     values=["All Time", "Next 7 Days", "Next 30 Days", "Next 3 Months",
                                            "This Year", "Past Events"])
            date_combo.pack(side=tk.LEFT, padx=(0, 20))
            date_combo.set("Next 30 Days")

            ttk.Label(date_frame, text="Location:").pack(side=tk.LEFT, padx=(0, 10))
            self.event_search_location = tk.StringVar()
            ttk.Entry(date_frame, textvariable=self.event_search_location,
                     width=20).pack(side=tk.LEFT)

            # Row 3: Additional filters
            filter_frame = ttk.Frame(search_frame)
            filter_frame.pack(fill=tk.X, pady=(0, 10))

            self.event_free_only = tk.BooleanVar()
            ttk.Checkbutton(filter_frame, text="Free Events Only",
                           variable=self.event_free_only).pack(side=tk.LEFT, padx=(0, 20))

            self.event_has_capacity = tk.BooleanVar()
            ttk.Checkbutton(filter_frame, text="Has Available Capacity",
                           variable=self.event_has_capacity).pack(side=tk.LEFT)

            # Search button
            ttk.Button(search_frame, text="Search Events",
                      command=self._perform_event_search).pack(pady=(10, 0))

            # Results table
            results_frame = ttk.LabelFrame(self.content_frame, text="Search Results", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Event Name', 'Date', 'Location', 'Type', 'Fee', 'Capacity', 'Status')
            self.event_search_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                self.event_search_tree.heading(col, text=col)
                self.event_search_tree.column(col, width=110)

            scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                        command=self.event_search_tree.yview)
            self.event_search_tree.configure(yscrollcommand=scrollbar_y.set)

            self.event_search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="View Details",
                      command=self._view_search_event_details).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Register for Event",
                      command=self.register_for_selected_event).pack(side=tk.LEFT)

        def show_create_event(self):
            """Show create event interface"""
            self.clear_content()
            self.update_status("Create Event")

            ttk.Label(self.content_frame, text="Create Alumni Event",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Create scrollable form
            canvas = tk.Canvas(self.content_frame)
            scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Event form
            self.event_vars = {}

            # Basic details
            basic_frame = ttk.LabelFrame(scrollable_frame, text="Event Details", padding=10)
            basic_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            basic_fields = [
                ("Event Name*", "event_name"),
                ("Event Date (YYYY-MM-DD)*", "event_date"),
                ("Event Time (HH:MM)*", "event_time"),
                ("Location*", "location")
            ]

            for i, (label, var_name) in enumerate(basic_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(basic_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.event_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.event_vars[var_name]).pack(fill=tk.X)

            basic_frame.columnconfigure(0, weight=1)
            basic_frame.columnconfigure(1, weight=1)

            # Event type
            type_frame = ttk.LabelFrame(scrollable_frame, text="Event Type", padding=10)
            type_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            self.event_vars['event_type'] = tk.StringVar(value="in-person")
            ttk.Radiobutton(type_frame, text="In-Person", variable=self.event_vars['event_type'],
                           value="in-person").pack(anchor='w')
            ttk.Radiobutton(type_frame, text="Virtual", variable=self.event_vars['event_type'],
                           value="virtual").pack(anchor='w')
            ttk.Radiobutton(type_frame, text="Hybrid", variable=self.event_vars['event_type'],
                           value="hybrid").pack(anchor='w')

            # Registration settings
            reg_frame = ttk.LabelFrame(scrollable_frame, text="Registration Settings", padding=10)
            reg_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            self.event_vars['registration_required'] = tk.BooleanVar(value=True)
            ttk.Checkbutton(reg_frame, text="Registration Required",
                           variable=self.event_vars['registration_required']).pack(anchor='w')

            reg_fields_frame = ttk.Frame(reg_frame)
            reg_fields_frame.pack(fill=tk.X, pady=10)

            ttk.Label(reg_fields_frame, text="Max Attendees (0 = unlimited):").pack(anchor='w')
            self.event_vars['max_attendees'] = tk.StringVar(value="0")
            ttk.Entry(reg_fields_frame, textvariable=self.event_vars['max_attendees']).pack(fill=tk.X, pady=(5, 10))

            ttk.Label(reg_fields_frame, text="Registration Deadline:").pack(anchor='w')
            self.event_vars['reg_deadline'] = tk.StringVar()
            ttk.Entry(reg_fields_frame, textvariable=self.event_vars['reg_deadline']).pack(fill=tk.X, pady=(5, 0))

            # Payment settings
            payment_frame = ttk.LabelFrame(scrollable_frame, text="Payment Settings", padding=10)
            payment_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            self.event_vars['payment_required'] = tk.BooleanVar()
            ttk.Checkbutton(payment_frame, text="Payment Required",
                           variable=self.event_vars['payment_required']).pack(anchor='w')

            fee_frame = ttk.Frame(payment_frame)
            fee_frame.pack(fill=tk.X, pady=10)

            ttk.Label(fee_frame, text="Event Fee ($):").pack(side=tk.LEFT, padx=(0, 10))
            self.event_vars['event_fee'] = tk.StringVar(value="0.00")
            ttk.Entry(fee_frame, textvariable=self.event_vars['event_fee'], width=10).pack(side=tk.LEFT)

            # Description
            desc_frame = ttk.LabelFrame(scrollable_frame, text="Event Description", padding=10)
            desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=20)

            self.event_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
            self.event_description.pack(fill=tk.BOTH, expand=True)

            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill=tk.X, pady=20, padx=20)

            ttk.Button(button_frame, text="Create Event",
                      command=self.submit_event).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Clear Form",
                      command=self.clear_event_form).pack(side=tk.RIGHT)

            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        def show_event_checkin(self):
            """Show event check-in interface"""
            self.clear_content()
            self.update_status("Event Check-in System")

            ttk.Label(self.content_frame, text="Event Check-in System",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Today's events
            events_frame = ttk.LabelFrame(self.content_frame, text="Today's Events", padding=10)
            events_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            sample_today_events = [
                "Tech Industry Networking - 7:00 PM",
                "Career Workshop - 2:00 PM",
                "Alumni Mixer - 6:00 PM"
            ]

            self.selected_event = tk.StringVar()
            for event in sample_today_events:
                ttk.Radiobutton(events_frame, text=event, variable=self.selected_event,
                               value=event).pack(anchor='w', pady=2)

            # Check-in methods
            checkin_frame = ttk.LabelFrame(self.content_frame, text="Check-in Method", padding=10)
            checkin_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            # Manual check-in
            manual_frame = ttk.Frame(checkin_frame)
            manual_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(manual_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
            self.checkin_alumni_id = tk.StringVar()
            ttk.Entry(manual_frame, textvariable=self.checkin_alumni_id, width=15).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(manual_frame, text="Check In",
                      command=self.process_manual_checkin).pack(side=tk.LEFT)

            # QR code check-in (simulated)
            qr_frame = ttk.Frame(checkin_frame)
            qr_frame.pack(fill=tk.X)

            ttk.Label(qr_frame, text="QR Code:").pack(side=tk.LEFT, padx=(0, 10))
            self.qr_code_data = tk.StringVar()
            ttk.Entry(qr_frame, textvariable=self.qr_code_data, width=25).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(qr_frame, text="Scan QR",
                      command=self.process_qr_checkin).pack(side=tk.LEFT)

            # Attendance list
            attendance_frame = ttk.LabelFrame(self.content_frame, text="Current Attendance", padding=10)
            attendance_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            self.attendance_text = ScrolledText(attendance_frame, height=10, wrap=tk.WORD)
            self.attendance_text.pack(fill=tk.BOTH, expand=True)

            # Sample attendance data
            attendance_data = """Current Event Attendance:

    ✅ Sarah Johnson (A000001) - 6:45 PM
    ✅ Michael Chen (A000002) - 6:52 PM
    ✅ Emily Davis (A000003) - 7:05 PM
    ✅ John Smith (A000004) - 7:12 PM

    Total Checked In: 4
    Registered: 25
    """
            self.attendance_text.insert(tk.END, attendance_data)

        def show_view_events(self):
            """Show events viewer"""
            self.clear_content()
            self.update_status("View Events")

            ttk.Label(self.content_frame, text="Alumni Events",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Filter options
            filter_frame = ttk.Frame(self.content_frame)
            filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 10))
            filter_var = tk.StringVar()
            filter_combo = ttk.Combobox(filter_frame, textvariable=filter_var,
                                       values=["All Events", "Upcoming Events", "Past Events", "My Registrations"])
            filter_combo.pack(side=tk.LEFT, padx=(0, 10))
            filter_combo.set("Upcoming Events")

            ttk.Button(filter_frame, text="Apply Filter",
                      command=lambda: self.filter_events(filter_var.get())).pack(side=tk.LEFT)

            # Events table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Event Name', 'Date', 'Location', 'Type', 'Fee', 'Registrations', 'Status')
            self.events_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.events_tree.heading(col, text=col)
                self.events_tree.column(col, width=120)

            # Scrollbars
            events_scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
            self.events_tree.configure(yscrollcommand=events_scrollbar_y.set)

            self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            events_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load events data
            self.load_events_data()

            # Buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="View Details",
                      command=self.view_event_details).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Register for Event",
                      command=self.register_for_selected_event).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.load_events_data).pack(side=tk.LEFT)

        def _add_event_to_academic_calendar(self, event_id, name, date_, description,
                                            event_type, created_by):
            """Mirror an alumni event into academic_calendar_events so it shows
            on the shared academic calendar. Idempotent per event."""
            try:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cal_id = f"ALUMNI-{event_id}"
                with db_get_connection() as conn:
                    # academic_calendar_events enforces a CHECK: a row uses EITHER
                    # a single `date` (start/end NULL) OR a date_start/date_end
                    # range. Alumni events are single-day, so use `date`.
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO academic_calendar_events
                            (id, name, date, date_start, date_end, description,
                             event_type, date_added, last_modified, created_by)
                        VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
                        """,
                        (cal_id, name, date_, description or "",
                         f"Alumni: {event_type}", now, now, created_by),
                    )
                    conn.commit()
                return True
            except sqlite3.Error as e:
                import logging
                logging.warning(f"Add event to academic calendar failed: {e}")
                return False

        def submit_event(self):
            """Create the event in the DB and add it to the academic calendar."""
            # Validate required fields
            required_fields = ['event_name', 'event_date', 'event_time', 'location']
            for field in required_fields:
                if not self.event_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            name = self.event_vars['event_name'].get().strip()
            date_ = self.event_vars['event_date'].get().strip()
            time_ = self.event_vars['event_time'].get().strip()
            location = self.event_vars['location'].get().strip()
            start_dt = f"{date_} {time_}".strip()

            def _var(key, default=""):
                v = self.event_vars.get(key)
                return v.get() if v is not None else default

            etype = _var('event_type', 'in-person')
            reg_required = 1 if (self.event_vars.get('registration_required')
                                 and self.event_vars['registration_required'].get()) else 0
            reg_deadline = _var('reg_deadline', "").strip()
            payment_required = 1 if (self.event_vars.get('payment_required')
                                     and self.event_vars['payment_required'].get()) else 0
            try:
                max_attendees = int(_var('max_attendees', '0') or 0)
            except ValueError:
                max_attendees = 0
            try:
                fee = float(_var('event_fee', '0') or 0)
            except ValueError:
                fee = 0.0
            description = self.event_description.get(1.0, tk.END).strip()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            created_by = str(getattr(self, 'current_user', {}).get('username', 'alumni_gui'))

            try:
                with db_get_connection() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO unified_events
                            (source_type, title, description, event_type, start_datetime,
                             location, max_capacity, registration_required, registration_deadline,
                             event_fee, payment_required, status, is_public, created_by,
                             created_at, organizer_name)
                        VALUES ('alumni', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', 1, ?, ?, ?)
                        """,
                        (name, description, etype, start_dt, location, max_attendees,
                         reg_required, reg_deadline, fee, payment_required, created_by,
                         now, created_by),
                    )
                    event_id = cur.lastrowid
                    conn.commit()
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to create event: {e}")
                return

            added = self._add_event_to_academic_calendar(
                event_id, name, date_, description, etype, created_by)
            msg = f"Event '{name}' created."
            msg += ("\nAdded to the academic calendar."
                    if added else "\n(Could not add to academic calendar.)")
            messagebox.showinfo("Success", msg)
            self.update_status("New event created")
            self.clear_event_form()

        def view_event_details(self):
            """View details for selected event"""
            selection = self.events_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an event to view details.")
                return

            item = self.events_tree.item(selection[0])
            event_data = item['values']

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Event Details - {event_data[0]}")
            details_window.geometry("500x400")

            text_widget = ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True)

            details_text = f"""
    EVENT DETAILS
    {'='*40}

    Event Name: {event_data[0]}
    Date & Time: {event_data[1]}
    Location: {event_data[2]}
    Event Type: {event_data[3]}
    Fee: {event_data[4]}
    Registrations: {event_data[5]}
    Status: {event_data[6]}

    Description:
    This is a sample event description. The event will feature networking opportunities,
    presentations from industry leaders, and chances to reconnect with fellow alumni.

    Registration Information:
    • Registration is required
    • Payment can be made online or at the door
    • Deadline: One week before event date
    • Cancellation policy applies

    Contact Information:
    • Email: events@alumni.edu
    • Phone: (555) 123-4567
            """

            text_widget.insert(tk.END, details_text)
            text_widget.config(state=tk.DISABLED)

        def view_my_event_registrations(self):
            """Show current user's event registrations"""
            self.clear_content()
            self.update_status("My Event Registrations")

            ttk.Label(self.content_frame, text="My Event Registrations",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Create registrations table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Event Name', 'Date', 'Location', 'Status', 'Payment', 'Registration Date')
            self.my_registrations_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.my_registrations_tree.heading(col, text=col)
                self.my_registrations_tree.column(col, width=130)

            # Scrollbars
            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.my_registrations_tree.yview)
            self.my_registrations_tree.configure(yscrollcommand=scrollbar_y.set)

            self.my_registrations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load user's registrations
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    query = """
                        SELECT e.title, e.start_datetime, e.location,
                               r.attendance_status, r.payment_status, r.registration_date
                        FROM unified_event_registrations r
                        JOIN unified_events e ON r.event_id = e.event_id
                        WHERE r.user_id = ? AND e.source_type = 'alumni'
                        ORDER BY e.start_datetime DESC
                    """
                    cursor.execute(query, (str(user_id),))
                    registrations = cursor.fetchall()

                    for reg in registrations:
                        self.my_registrations_tree.insert('', tk.END, values=reg)

                    self.update_status(f"Loaded {len(registrations)} registration(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load registrations: {str(e)}")

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="View Event Details",
                      command=self.view_event_details).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Cancel Registration",
                      command=self._cancel_registration).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.view_my_event_registrations).pack(side=tk.LEFT)

