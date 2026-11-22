
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import access_ui
import tkinter as tk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import make_toplevel
from tkinter import ttk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox, simpledialog
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.sql_safety import escape_like
# Every appointment read and booking check goes through the clinic diary
# (application/health/diary): clashes across all clinics, provider hours and
# capacity, time off, the waiting list and post-appointment feedback.
from education_system.systems.university.domains.health.application.health import diary

CLINIC_LABELS = {
    "health_appointments": "Health",
    "dentist_appointments": "Dental",
    "counseling_appointments": "Counselling",
    "mental_health_appointments": "Mental health",
}


class AppointmentsMixin:
    """Mixin for appointment management operations."""

    def create_schedule_appointment(self):
        """Create appointment scheduling interface"""
        title = ttk.Label(self.content_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.appointment_management', default="Appointment Management"), style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text=_t('gui.pastoral.health.health_portal.appointments.tabs.schedule_appointment', default="Schedule Appointment"))
        self.create_schedule_appointment_form(schedule_tab)

        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text=_t('gui.pastoral.health.health_portal.appointments.tabs.view_appointments', default="View Appointments"))
        self.create_view_appointments_form(view_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_schedule_appointment_form(self, parent):
        """Create form for scheduling appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.apt_student_id = tk.StringVar()
        student_entry = ttk.Entry(main_frame, textvariable=self.apt_student_id, width=20)
        student_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        # A student books for themselves only (their student number, locked).
        access_ui.lock_to_own(self.auth, self.apt_student_id, student_entry)

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.appointment_type', default="Appointment Type:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.apt_type = tk.StringVar()
        apt_type_combo = ttk.Combobox(main_frame, textvariable=self.apt_type,
                                     values=['General Check-up', 'Follow-up Visit', 'Vaccination',
                                            'Mental Health Consultation', 'Injury Assessment',
                                            'Chronic Care Management', 'Preventive Screening',
                                            'Emergency Consultation'])
        apt_type_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.apt_date = tk.StringVar()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        ttk.Entry(main_frame, textvariable=self.apt_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.time_hh_mm', default="Time (HH:MM):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.apt_time = tk.StringVar(value="09:00")
        ttk.Entry(main_frame, textvariable=self.apt_time, width=20).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.provider', default="Provider:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.apt_provider = tk.StringVar(value=_t('gui.pastoral.health.health_portal.appointments.values.dr_health_services', default="Dr. Health Services"))
        ttk.Entry(main_frame, textvariable=self.apt_provider, width=30).grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.reason', default="Reason:")).grid(row=5, column=0, sticky=(tk.W, tk.N), pady=5)
        self.apt_reason = tk.Text(main_frame, width=40, height=4)
        self.apt_reason.grid(row=5, column=1, pady=5, padx=(5, 0))

        ttk.Button(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.schedule_appointment', default="Schedule Appointment"), command=self.save_appointment).grid(row=6, column=0, columnspan=2, pady=20)
        extra = ttk.Frame(main_frame)
        extra.grid(row=7, column=0, columnspan=2)
        ttk.Button(extra, text="Free Slots", command=self.show_free_slots).pack(side=tk.LEFT, padx=4)
        ttk.Button(extra, text="Join Waiting List", command=self.join_waiting_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(extra, text="Waiting List", command=self.show_waiting_list).pack(side=tk.LEFT, padx=4)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def save_appointment(self):
        """Save appointment to database"""
        own = access_ui.own_student_id(self.auth)
        if own is not None:
            self.apt_student_id.set(own)
        elif not access_ui.require_clinician(self.root, self.auth,
                                             "book appointments for other people"):
            return
        try:
            if not all([self.apt_student_id.get().strip(), self.apt_type.get().strip(),
                       self.apt_date.get().strip(), self.apt_time.get().strip(),
                       self.apt_provider.get().strip()]):
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.appointments.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields"))
                return

            try:
                datetime.strptime(self.apt_date.get(), '%Y-%m-%d')
                datetime.strptime(self.apt_time.get(), '%H:%M')
            except ValueError:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.appointments.dialogs.invalid_date_or_time_format', default="Invalid date or time format"))
                return

            if datetime.strptime(self.apt_date.get(), '%Y-%m-%d') < datetime.now():
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.appointments.dialogs.cannot_schedule_appointments_in_the_past', default="Cannot schedule appointments in the past"))
                return

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.apt_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.appointments.dialogs.student_id_not_found', default="Student ID not found"))
                conn.close()
                return

            reason = self.apt_reason.get(1.0, tk.END).strip()
            student_id = self.apt_student_id.get().strip()
            provider = self.apt_provider.get().strip()

            # Time off blocks; a clash (provider or student, any clinic) or a
            # schedule problem (outside hours / day full) needs a clinician's
            # override with a reason. Otherwise the waiting list is offered.
            diary.ensure_schema(conn)
            check = diary.check_booking(conn, student_id=student_id, provider=provider,
                                        date=self.apt_date.get(), time=self.apt_time.get())
            override_reason = None
            if not check.ok:
                may_override = not check.blocked and access_ui.is_clinician(self.auth)
                if may_override:
                    override_reason = simpledialog.askstring(
                        access_ui.TITLE, check.summary()
                        + "\n\nTo book anyway, enter the reason (recorded in the audit):",
                        parent=self.root)
                    if not override_reason or len(override_reason.strip()) < 5:
                        override_reason = None
                if not override_reason:
                    if messagebox.askyesno(access_ui.TITLE, check.summary()
                                           + "\n\nThis slot cannot be booked. Join the waiting "
                                             "list for a " + self.apt_type.get()
                                           + " appointment instead?"):
                        diary.join_waitlist(conn, student_id=student_id,
                                            appointment_type=self.apt_type.get(),
                                            provider=provider or None,
                                            preferred_from=self.apt_date.get(),
                                            notes=reason, by=self._wl_user())
                        conn.commit()
                        messagebox.showinfo(access_ui.TITLE, "Added to the waiting list. A freed "
                                            "slot will be offered by e-mail.")
                    conn.close()
                    return

            apt_id = diary.book(conn, student_id=student_id, appointment_type=self.apt_type.get(),
                                date=self.apt_date.get(), time=self.apt_time.get(),
                                provider=provider, reason=reason,
                                has_conflict=bool(override_reason))
            if override_reason:
                diary.record_booking_override(conn, self._wl_user(), apt_id, check,
                                              override_reason)
            conn.commit()
            diary.publish_booking(apt_id, student_id=student_id, date=self.apt_date.get(),
                                  time=self.apt_time.get(), provider=provider,
                                  appointment_type=self.apt_type.get())

            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                          (self.apt_student_id.get().strip(),))
            patient_info = cursor.fetchone()

            conn.close()

            emailed = False
            if patient_info:
                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                appointment_details = {
                    'date': self.apt_date.get(),
                    'time': self.apt_time.get(),
                    'practitioner': self.apt_provider.get().strip(),
                    'department': self.apt_type.get(),
                    'type': self.apt_type.get(),
                    'preparation_notes': f"Reason for visit: {reason}" if reason else "No special preparation required."
                }

                emailed = self.send_appointment_confirmation(patient_email, patient_name, appointment_details)

            self.log_audit_event('schedule_appointment', 'appointment', apt_id)
            messagebox.showinfo(_t('gui.pastoral.health.health_portal.appointments.dialogs.success', default="Success"),
                                f"Appointment scheduled successfully!\nAppointment ID: {apt_id}\n"
                                + ("Confirmation email sent." if emailed
                                   else "The confirmation e-mail could not be sent."))

            self.clear_appointment_form()

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), f"An error occurred: {str(e)}")

    def clear_appointment_form(self):
        """Clear the appointment form"""
        if self.auth.current_user['role'] != 'student':
            self.apt_student_id.set("")
        self.apt_type.set("")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        self.apt_time.set("09:00")
        self.apt_provider.set("Dr. Health Services")
        self.apt_reason.delete(1.0, tk.END)

    def create_view_appointments_form(self, parent):
        """Create interface for viewing appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        search_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.search', default="Search"), padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.apt_search_student = tk.StringVar()
        self.apt_search_entry = ttk.Entry(search_frame, textvariable=self.apt_search_student,
                                          width=20)
        self.apt_search_entry.grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))
        access_ui.lock_to_own(self.auth, self.apt_search_student, self.apt_search_entry)

        ttk.Button(search_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.search', default="Search"), command=self.search_appointments).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.show_all', default="Show All"), command=self.load_all_appointments).grid(row=0, column=3, padx=5)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        columns = ('ID', 'Student', 'Type', 'Date', 'Time', 'Provider', 'Status', 'Clinic')
        self.apt_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.apt_tree.heading(col, text=col)
            if col == 'ID':
                self.apt_tree.column(col, width=50)
            else:
                self.apt_tree.column(col, width=120)

        self.apt_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        apt_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.apt_tree.yview)
        apt_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.apt_tree.configure(yscrollcommand=apt_scroll.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)

        ttk.Button(buttons_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.view_details', default="View Details"), command=self.view_appointment_details).pack(side=tk.LEFT, padx=5)
        if access_ui.is_clinician(self.auth):
            ttk.Button(buttons_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.update_status', default="Update Status"), command=self.update_appointment_status).pack(side=tk.LEFT, padx=5)
        if access_ui.is_clinician(self.auth) or access_ui.own_student_id(self.auth):
            ttk.Button(buttons_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.cancel', default="Cancel"), command=self.cancel_appointment).pack(side=tk.LEFT, padx=5)
            ttk.Button(buttons_frame, text="Give Feedback", command=self.give_appointment_feedback).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.load_all_appointments()

    def search_appointments(self):
        """Search appointments"""
        self.load_appointments(self.apt_search_student.get().strip())

    def load_all_appointments(self):
        """Load all appointments"""
        self.load_appointments()

    def load_appointments(self, student_filter=""):
        """Load appointments with optional student filter"""
        for item in self.apt_tree.get_children():
            self.apt_tree.delete(item)

        student_filter = access_ui.scoped_student(self.root, self.auth, student_filter,
                                                  var=getattr(self, "apt_search_student", None),
                                                  widget=getattr(self, "apt_search_entry", None))
        if student_filter is None:
            return
        if not access_ui.record_view(self.root, self.auth, "appointments",
                                     student_id=student_filter):
            return

        try:
            conn = self.get_connection()
            # Every clinic's appointments (diary); a clinician's partial
            # student number still matches as before.
            rows = diary.appointments(conn, student_id=student_filter or None)
            if student_filter and access_ui.is_clinician(self.auth) and not rows:
                rows = [a for a in diary.appointments(conn)
                        if student_filter.lower() in str(a["student_id"]).lower()]
            rows.sort(key=lambda a: (str(a["date"] or ""), str(a["time"] or "")), reverse=True)
            for apt in rows[:100]:
                self.apt_tree.insert('', tk.END, values=(
                    apt["id"], "anonymous" if apt["anonymous"] else apt["student_id"], apt["type"], apt["date"], apt["time"],
                    apt["provider"], apt["status"], CLINIC_LABELS.get(apt["source"], apt["source"])))

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), f"Failed to load appointments: {str(e)}")

    def view_appointment_details(self):
        """View details of selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.health.health_portal.appointments.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.health.health_portal.appointments.dialogs.please_select_an_appointment_to_view', default="Please select an appointment to view."))
            return
        if not self._is_health_row(selection[0], "view"):
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT apt.student_id, s.first_name, s.last_name, s.email_address,
                       apt.appointment_type, apt.appointment_date, apt.appointment_time,
                       apt.provider, apt.reason, apt.status, apt.notes, apt.scheduled_at
                FROM health_appointments apt
                JOIN students s ON apt.student_id = s.student_id
                WHERE apt.id = ?
            ''', (apt_id,))
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.appointments.dialogs.appointment_not_found', default="Appointment not found"))
                return
            if not access_ui.may_view(self.auth, record[0]):
                messagebox.showerror(access_ui.TITLE, "You cannot see this appointment.")
                return
            if not access_ui.record_view(self.root, self.auth, "appointment",
                                         student_id=record[0], record_id=apt_id):
                return

            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.pastoral.health.health_portal.appointments.windows.appointment_details', default="Appointment Details"))
            dialog.geometry("600x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.appointment_details', default="Appointment Details"), font=('Arial', 14, 'bold')).pack(pady=10)

            details_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.labels.appointment_information', default="Appointment Information"), padding=15)
            details_frame.pack(fill='both', expand=True, pady=10)

            info_text = tk.Text(details_frame, height=20, width=60, wrap='word', font=('Courier', 10))
            info_text.pack(fill='both', expand=True)

            status_display = record[9].upper() if record[9] else 'SCHEDULED'
            details = f"""
PATIENT INFORMATION
{'='*50}
Student ID:      {record[0]}
Name:            {record[1]} {record[2]}
Email:           {record[3]}

APPOINTMENT DETAILS
{'='*50}
Type:            {record[4]}
Date:            {record[5]}
Time:            {record[6]}
Provider:        {record[7] or 'Not assigned'}
Status:          {status_display}

REASON FOR VISIT
{'='*50}
{record[8] if record[8] else 'No reason provided'}

NOTES
{'='*50}
{record[10] if record[10] else 'No notes'}

SCHEDULING INFORMATION
{'='*50}
Scheduled At:    {record[11] if record[11] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text=_t('gui.pastoral.health.health_portal.appointments.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), f"Failed to load appointment details: {e}")

    def update_appointment_status(self):
        """Update appointment status"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.health.health_portal.appointments.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.health.health_portal.appointments.dialogs.please_select_an_appointment_to_update', default="Please select an appointment to update."))
            return
        if not self._is_health_row(selection[0], "update"):
            return

        if not access_ui.require_clinician(self.root, self.auth, "change an appointment's status"):
            return
        apt_id = self.apt_tree.item(selection[0])['values'][0]
        current_status = self.apt_tree.item(selection[0])['values'][6]

        status_dialog = make_toplevel(self.root)
        status_dialog.title(_t('gui.pastoral.health.health_portal.appointments.windows.update_appointment_status', default="Update Appointment Status"))
        status_dialog.geometry("300x200")
        status_dialog.transient(self.root)
        status_dialog.grab_set()

        ttk.Label(status_dialog, text=f"Current Status: {current_status}").pack(pady=10)
        ttk.Label(status_dialog, text=_t('gui.pastoral.health.health_portal.appointments.labels.new_status', default="New Status:")).pack()

        new_status = tk.StringVar()
        status_combo = ttk.Combobox(status_dialog, textvariable=new_status,
                                   values=['scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled'])
        status_combo.pack(pady=5)

        def update_status():
            if new_status.get():
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()

                    cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                                  (new_status.get(), apt_id))
                    offers = []
                    if new_status.get() in ('cancelled', 'no-show', 'rescheduled'):
                        row = cursor.execute(
                            'SELECT appointment_date, appointment_time, provider, appointment_type '
                            'FROM health_appointments WHERE id = ?', (apt_id,)).fetchone()
                        if row and new_status.get() != 'no-show':
                            offers = diary.offer_freed_slot(conn, date=row[0], time=row[1],
                                                            provider=row[2], appointment_type=row[3])
                    conn.commit()
                    conn.close()
                    diary.send_emails(offers)
                    if new_status.get() == 'completed':
                        # The patient is asked for feedback by e-mail (hourly
                        # job); if they are here, their rating can be taken now.
                        self._ask_feedback_now(apt_id)

                    self.log_audit_event('update_appointment_status', 'appointment', apt_id,
                                       f"Status changed from {current_status} to {new_status.get()}")

                    messagebox.showinfo(_t('gui.pastoral.health.health_portal.appointments.dialogs.success', default="Success"), _t('gui.pastoral.health.health_portal.appointments.dialogs.appointment_status_updated_successfully', default="Appointment status updated successfully!"))
                    status_dialog.destroy()
                    self.load_appointments(self.apt_search_student.get().strip())
                except Exception as e:
                    messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), f"Failed to update status: {str(e)}")
            else:
                messagebox.showwarning(_t('gui.pastoral.health.health_portal.appointments.dialogs.warning', default="Warning"), _t('gui.pastoral.health.health_portal.appointments.dialogs.please_select_a_status', default="Please select a status"))

        ttk.Button(status_dialog, text=_t('gui.pastoral.health.health_portal.appointments.buttons.update', default="Update"), command=update_status).pack(pady=10)
        ttk.Button(status_dialog, text=_t('gui.pastoral.health.health_portal.appointments.buttons.cancel', default="Cancel"), command=status_dialog.destroy).pack()

    def cancel_appointment(self):
        """Cancel selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.health.health_portal.appointments.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.health.health_portal.appointments.dialogs.please_select_an_appointment_to_cancel', default="Please select an appointment to cancel."))
            return
        if not self._is_health_row(selection[0], "cancel"):
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]
        owner = str(self.apt_tree.item(selection[0])['values'][1])
        if not access_ui.is_clinician(self.auth) and owner != access_ui.own_student_id(self.auth):
            messagebox.showerror(access_ui.TITLE, "You can only cancel your own appointments.")
            return

        cancellation_reason = simpledialog.askstring(
            _t('gui.pastoral.health.health_portal.appointments.dialogs.cancellation_reason', default="Cancellation Reason"),
            _t('gui.pastoral.health.health_portal.appointments.dialogs.please_provide_a_reason_for_cancelling_this_appointment', default="Please provide a reason for cancelling this appointment:"),
            initialvalue="Patient request"
        )

        if not cancellation_reason:
            return

        if messagebox.askyesno(_t('gui.pastoral.health.health_portal.appointments.dialogs.confirm_cancellation', default="Confirm Cancellation"), _t('gui.pastoral.health.health_portal.appointments.dialogs.are_you_sure_you_want_to_cancel_this_appointment', default="Are you sure you want to cancel this appointment?")):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT ha.student_id, ha.appointment_date, ha.appointment_time,
                           ha.provider, ha.appointment_type, s.first_name, s.last_name, s.email_address
                    FROM health_appointments ha
                    JOIN students s ON ha.student_id = s.student_id
                    WHERE ha.id = ?
                ''', (apt_id,))

                appointment_info = cursor.fetchone()

                cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                              ('cancelled', apt_id))
                # The freed slot goes to the first matching waiting-list entry.
                offers = diary.offer_freed_slot(
                    conn, date=appointment_info[1], time=appointment_info[2],
                    provider=appointment_info[3],
                    appointment_type=appointment_info[4]) if appointment_info else []
                conn.commit()
                conn.close()
                diary.send_emails(offers)

                emailed = False
                if appointment_info:
                    patient_name = f"{appointment_info[5]} {appointment_info[6]}"
                    patient_email = appointment_info[7]

                    appointment_details = {
                        'date': appointment_info[1],
                        'time': appointment_info[2],
                        'practitioner': appointment_info[3],
                        'department': appointment_info[4]
                    }

                    emailed = self.send_appointment_cancellation(patient_email, patient_name, appointment_details, cancellation_reason)

                self.log_audit_event('cancel_appointment', 'appointment', apt_id, f"Reason: {cancellation_reason}")
                messagebox.showinfo(_t('gui.pastoral.health.health_portal.appointments.dialogs.success', default="Success"),
                                    (_t('gui.pastoral.health.health_portal.appointments.dialogs.appointment_cancelled_successfully_cancellation_email_sent', default="Appointment cancelled successfully!\nCancellation email sent.")
                                     if emailed else "Appointment cancelled.\nThe cancellation e-mail could not be sent.")
                                    + ("\nThe slot was offered to the waiting list." if offers else ""))
                self.load_appointments(self.apt_search_student.get().strip())

            except Exception as e:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.appointments.dialogs.error', default="Error"), f"Failed to cancel appointment: {str(e)}")

    # ------------------------------------------------------------------
    # Diary helpers: waiting list, free slots, feedback
    # ------------------------------------------------------------------
    def _wl_user(self):
        user = access_ui.current_user(self.auth) or {}
        return str(user.get('username') or user.get('id') or 'unknown')

    def _is_health_row(self, item, verb):
        values = self.apt_tree.item(item)['values']
        clinic = values[7] if len(values) > 7 else CLINIC_LABELS["health_appointments"]
        if clinic != CLINIC_LABELS["health_appointments"]:
            messagebox.showinfo(access_ui.TITLE, f"This is a {clinic} appointment; {verb} it "
                                f"from the {clinic} screen.")
            return False
        return True

    def show_free_slots(self):
        provider = self.apt_provider.get().strip()
        date = self.apt_date.get().strip()
        if not provider or not date:
            messagebox.showwarning(access_ui.TITLE, "Enter a provider and a date first.")
            return
        conn = self.get_connection()
        try:
            diary.ensure_schema(conn)
            slots = diary.free_slots(conn, provider, date)
            away = diary.time_off_for(conn, provider, date)
        except ValueError:
            messagebox.showerror(access_ui.TITLE, "Use the date format YYYY-MM-DD.")
            return
        finally:
            conn.close()
        if away:
            text = f"{provider} is away on {date} ({away[0]['reason'] or 'time off'})."
        elif slots:
            text = f"Free times for {provider} on {date}:\n" + ", ".join(slots)
        else:
            text = (f"No free times for {provider} on {date} (no clinic that day, or fully "
                    "booked). You can join the waiting list.")
        messagebox.showinfo(access_ui.TITLE, text)

    def join_waiting_list(self):
        own = access_ui.own_student_id(self.auth)
        student_id = own or self.apt_student_id.get().strip()
        if not student_id or not self.apt_type.get().strip():
            messagebox.showwarning(access_ui.TITLE, "Enter the student ID and appointment type.")
            return
        if own is None and not access_ui.require_clinician(self.root, self.auth,
                                                           "add other people to the waiting list"):
            return
        conn = self.get_connection()
        try:
            wid = diary.join_waitlist(conn, student_id=student_id,
                                      appointment_type=self.apt_type.get().strip(),
                                      provider=self.apt_provider.get().strip() or None,
                                      preferred_from=self.apt_date.get().strip() or None,
                                      notes=self.apt_reason.get(1.0, tk.END).strip(),
                                      by=self._wl_user())
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(access_ui.TITLE, f"Added to the waiting list (entry {wid}). A freed "
                            "slot will be offered by e-mail.")

    def show_waiting_list(self):
        own = access_ui.own_student_id(self.auth)
        if own is None and not access_ui.is_clinician(self.auth):
            messagebox.showerror(access_ui.TITLE, "The waiting list is for the health team and "
                                 "the student themselves.")
            return
        win = make_toplevel(self.root)
        win.title("Appointment Waiting List")
        win.geometry("900x420")
        win.transient(self.root)
        cols = ("ID", "Student", "Type", "Provider", "From", "Status", "Offer")
        tree = ttk.Treeview(win, columns=cols, show='headings', height=14)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=60 if c == "ID" else 130)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def refresh():
            tree.delete(*tree.get_children())
            conn = self.get_connection()
            try:
                rows = diary.list_waitlist(conn, student_id=own)
            finally:
                conn.close()
            for r in rows:
                if r["status"] not in ("waiting", "offered"):
                    continue
                offer = (f"{r['offered_date']} {r['offered_time']} until {r['offer_expires_at']}"
                         if r["status"] == "offered" else "")
                tree.insert('', tk.END, values=(r["id"], r["student_id"], r["appointment_type"],
                                                r["provider"] or "any", r["preferred_from"] or "",
                                                r["status"], offer))

        def selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(access_ui.TITLE, "Select an entry.", parent=win)
                return None
            return tree.item(sel[0])['values']

        def accept():
            values = selected()
            if not values:
                return
            conn = self.get_connection()
            try:
                appt = diary.accept_offer(conn, values[0], by=self._wl_user())
                conn.commit()
                row = conn.execute("SELECT student_id, appointment_date, appointment_time, provider, "
                                   "appointment_type FROM health_appointments WHERE id = ?",
                                   (appt,)).fetchone()
            except ValueError as exc:
                conn.rollback()
                messagebox.showerror(access_ui.TITLE, str(exc), parent=win)
                return
            finally:
                conn.close()
            diary.publish_booking(appt, student_id=row[0], date=row[1], time=row[2],
                                  provider=row[3], appointment_type=row[4])
            messagebox.showinfo(access_ui.TITLE, f"Booked: appointment {appt}.", parent=win)
            refresh()
            self.load_appointments(getattr(self, "apt_search_student", tk.StringVar()).get().strip())

        def remove():
            values = selected()
            if not values:
                return
            conn = self.get_connection()
            try:
                diary.withdraw(conn, values[0])
                conn.commit()
            finally:
                conn.close()
            refresh()

        bar = ttk.Frame(win)
        bar.pack(pady=(0, 10))
        ttk.Button(bar, text="Accept Offer", command=accept).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Withdraw", command=remove).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=4)
        refresh()

    def _record_feedback(self, source, appt_id, student_id, parent=None):
        rating = simpledialog.askinteger(access_ui.TITLE, "How was the appointment? (1 = poor, "
                                         "5 = excellent)", minvalue=1, maxvalue=5,
                                         parent=parent or self.root)
        if not rating:
            return False
        comments = simpledialog.askstring(access_ui.TITLE, "Any comments? (optional)",
                                          parent=parent or self.root) or None
        conn = self.get_connection()
        try:
            diary.submit_feedback(conn, source=source, appointment_id=appt_id,
                                  student_id=student_id, rating=rating, comments=comments)
            conn.commit()
        except (ValueError, LookupError) as exc:
            conn.rollback()
            messagebox.showerror(access_ui.TITLE, str(exc))
            return False
        finally:
            conn.close()
        messagebox.showinfo(access_ui.TITLE, "Thank you — feedback recorded.")
        return True

    def _ask_feedback_now(self, apt_id):
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT student_id FROM health_appointments WHERE id = ?",
                               (apt_id,)).fetchone()
        finally:
            conn.close()
        if row and messagebox.askyesno(access_ui.TITLE, "Appointment completed. Is the patient "
                                       "here to rate it now? (Otherwise they are asked by "
                                       "e-mail.)"):
            self._record_feedback("health_appointments", apt_id, row[0])

    def give_appointment_feedback(self):
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning(access_ui.TITLE, "Select a completed appointment.")
            return
        values = self.apt_tree.item(selection[0])['values']
        owner = str(values[1])
        own = access_ui.own_student_id(self.auth)
        if own is not None and owner != own:
            messagebox.showerror(access_ui.TITLE, "You can only rate your own appointments.")
            return
        if own is None and not access_ui.is_clinician(self.auth):
            return
        clinic = values[7] if len(values) > 7 else "Health"
        source = {v: k for k, v in CLINIC_LABELS.items()}.get(clinic, "health_appointments")
        self._record_feedback(source, values[0], owner)
