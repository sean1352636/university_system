"""Health Portal — Student portal.

A student-facing window: see my upcoming and past appointments, request a
new appointment, and view my vaccinations, allergies, and emergency
contacts. All panels apart from the appointment request form are
read-only. Full medical records / prescriptions / vitals remain admin-only
(the full `HealthPortalGUI`).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_APPT_TYPES = [
    'General', 'Physical', 'Vaccination', 'Mental Health',
    'Follow-up', 'Lab', 'Screening', 'Other',
]


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class HealthStudentPortal:
    """Read-only health viewer + appointment request for students."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.student = self._resolve_student()

        self.window = tk.Toplevel(parent)
        self.window.title("Health Portal — My Portal")
        self.window.geometry("1050x700")
        self.window.minsize(920, 580)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="")
        self._build_ui()

        if self.student is None:
            self._show_not_found()
        else:
            self._refresh_all()

    def _resolve_student(self):
        user = (self.auth.current_user if self.auth else None) or {}
        candidates = [
            ('student_id', user.get('student_id')),
            ('student_id', user.get('username')),
            ('email_address', user.get('email')),
        ]
        try:
            with _connect() as conn:
                cur = conn.cursor()
                for column, value in candidates:
                    if not value:
                        continue
                    cur.execute(
                        f"SELECT student_id, first_name, last_name, "
                        f"       email_address "
                        f"FROM students WHERE {column} = ?",
                        (value,)
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            'student_id': row[0],
                            'first_name': row[1] or '',
                            'last_name': row[2] or '',
                            'email': row[3] or '',
                        }
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#1abc9c', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)

        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"My Health — {display}",
                 font=('Arial', 14, 'bold'), bg='#1abc9c', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#148f77', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#148f77', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self._build_appointments_tab(nb)
        self._build_vaccinations_tab(nb)
        self._build_allergies_tab(nb)
        self._build_contacts_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    # -- Appointments tab ---------------------------------------------

    def _build_appointments_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Appointments")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="My upcoming and past appointments",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Request New Appointment",
                   command=self._request_appointment).pack(side='right')

        cols = ('date', 'time', 'type', 'provider', 'status', 'reason')
        self.appt_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        headings = [
            ('date', 'Date', 110),
            ('time', 'Time', 80),
            ('type', 'Type', 140),
            ('provider', 'Provider', 180),
            ('status', 'Status', 110),
            ('reason', 'Reason', 360),
        ]
        for key, title, width in headings:
            self.appt_tree.heading(key, text=title)
            self.appt_tree.column(key, width=width,
                                  anchor='w' if key in ('provider', 'reason')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.appt_tree.yview)
        self.appt_tree.configure(yscrollcommand=vsb.set)
        self.appt_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.appt_tree.tag_configure('upcoming', background='#fef9e7')
        self.appt_tree.tag_configure('today', background='#eafaf1')
        self.appt_tree.tag_configure('past', foreground='#888')

    def _load_appointments(self):
        for i in self.appt_tree.get_children():
            self.appt_tree.delete(i)
        if not self.student:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT appointment_date, appointment_time, "
                    "       appointment_type, provider, status, reason "
                    "FROM health_appointments "
                    "WHERE student_id = ? "
                    "ORDER BY appointment_date DESC, appointment_time DESC",
                    (self.student['student_id'],)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        today = datetime.now().date().isoformat()
        upcoming = 0
        for date, time_, atype, provider, status, reason in rows:
            tag = ()
            if date == today:
                tag = ('today',)
            elif date and date > today:
                tag = ('upcoming',)
                upcoming += 1
            elif date and date < today:
                tag = ('past',)
            self.appt_tree.insert('', 'end', values=(
                date or '', (time_ or '')[:5],
                atype or '', provider or '',
                status or '', reason or ''
            ), tags=tag)
        self.status_var.set(
            f"{len(rows)} appointment(s); {upcoming} upcoming."
        )

    def _request_appointment(self):
        if not self.student:
            return
        RequestAppointmentDialog(
            self.window, self.student['student_id'],
            on_save=self._load_appointments)

    # -- Vaccinations tab ---------------------------------------------

    def _build_vaccinations_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Vaccinations")

        ttk.Label(frame, text="My vaccination record",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('vaccine', 'administered', 'expiry', 'manufacturer',
                'verified')
        self.vacc_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('vaccine', 'Vaccine', 240),
            ('administered', 'Administered', 120),
            ('expiry', 'Expires', 120),
            ('manufacturer', 'Manufacturer', 200),
            ('verified', 'Verified', 90),
        ]:
            self.vacc_tree.heading(key, text=title)
            self.vacc_tree.column(key, width=width,
                                  anchor='w' if key in ('vaccine',
                                                        'manufacturer')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.vacc_tree.yview)
        self.vacc_tree.configure(yscrollcommand=vsb.set)
        self.vacc_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.vacc_tree.tag_configure('expired', foreground='#c0392b')

    def _load_vaccinations(self):
        for i in self.vacc_tree.get_children():
            self.vacc_tree.delete(i)
        if not self.student:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT vaccine_name, administered_date, expiry_date, "
                    "       manufacturer, verified "
                    "FROM vaccination_records "
                    "WHERE student_id = ? "
                    "ORDER BY administered_date DESC",
                    (self.student['student_id'],)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        today = datetime.now().date().isoformat()
        for name, admin, expiry, mfr, verified in rows:
            tag = ()
            if expiry and expiry < today:
                tag = ('expired',)
            self.vacc_tree.insert('', 'end', values=(
                name or '', (admin or '')[:10], (expiry or '')[:10],
                mfr or '', 'Yes' if verified else 'No'
            ), tags=tag)

    # -- Allergies tab -------------------------------------------------

    def _build_allergies_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Allergies")

        ttk.Label(frame, text="My recorded allergies",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('allergen', 'severity', 'reaction', 'diagnosed')
        self.allergy_tree = ttk.Treeview(frame, columns=cols,
                                         show='headings', selectmode='browse')
        for key, title, width in [
            ('allergen', 'Allergen', 220),
            ('severity', 'Severity', 110),
            ('reaction', 'Reaction', 380),
            ('diagnosed', 'Diagnosed', 120),
        ]:
            self.allergy_tree.heading(key, text=title)
            self.allergy_tree.column(key, width=width,
                                     anchor='w' if key in ('allergen',
                                                           'reaction')
                                                   else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.allergy_tree.yview)
        self.allergy_tree.configure(yscrollcommand=vsb.set)
        self.allergy_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _load_allergies(self):
        for i in self.allergy_tree.get_children():
            self.allergy_tree.delete(i)
        if not self.student:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT allergen, severity, reaction_description, "
                    "       diagnosed_date "
                    "FROM allergies WHERE student_id = ? "
                    "ORDER BY severity DESC",
                    (self.student['student_id'],)
                )
                for row in cur.fetchall():
                    self.allergy_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '', row[2] or '',
                        (row[3] or '')[:10]
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)

    # -- Contacts tab --------------------------------------------------

    def _build_contacts_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Emergency Contacts")

        ttk.Label(frame, text="My emergency contacts",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('name', 'relationship', 'phone', 'email', 'decision_maker')
        self.contacts_tree = ttk.Treeview(frame, columns=cols,
                                          show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Name', 220),
            ('relationship', 'Relation', 140),
            ('phone', 'Phone', 160),
            ('email', 'Email', 240),
            ('decision_maker', 'Decision maker', 130),
        ]:
            self.contacts_tree.heading(key, text=title)
            self.contacts_tree.column(key, width=width,
                                      anchor='w' if key in ('name', 'email')
                                                    else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.contacts_tree.yview)
        self.contacts_tree.configure(yscrollcommand=vsb.set)
        self.contacts_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _load_contacts(self):
        for i in self.contacts_tree.get_children():
            self.contacts_tree.delete(i)
        if not self.student:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT contact_name, relationship, phone_primary, email, "
                    "       medical_decision_maker "
                    "FROM emergency_contacts WHERE student_id = ? "
                    "ORDER BY priority_order",
                    (self.student['student_id'],)
                )
                for row in cur.fetchall():
                    self.contacts_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '', row[2] or '',
                        row[3] or '',
                        'Yes' if row[4] else 'No'
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)

    # ------------------------------------------------------------------

    def _show_not_found(self):
        self.status_var.set(
            "No student record matched your account. "
            "Contact an administrator."
        )

    def _refresh_all(self):
        self._load_appointments()
        self._load_vaccinations()
        self._load_allergies()
        self._load_contacts()


class RequestAppointmentDialog:
    """Let a student request a new health appointment.

    Writes to health_appointments with status = 'scheduled'. Staff can then
    review and reschedule / complete / cancel via the staff portal.
    """

    def __init__(self, parent, student_id, on_save):
        self.student_id = student_id
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Request Appointment")
        self.dialog.geometry("480x440")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame,
                  text="Request an appointment. A staff member will "
                       "confirm or reschedule.",
                  wraplength=420, justify='left').pack(anchor='w', pady=(0, 8))

        grid = ttk.Frame(frame)
        grid.pack(fill='x', pady=4)

        ttk.Label(grid, text="Type:").grid(row=0, column=0, sticky='w', pady=4)
        self.type_var = tk.StringVar(value='General')
        ttk.Combobox(grid, textvariable=self.type_var,
                     values=_APPT_TYPES, state='readonly', width=28).grid(
            row=0, column=1, sticky='w', pady=4)

        default_date = (datetime.now() + timedelta(days=3)
                        ).date().isoformat()
        ttk.Label(grid, text="Preferred date (YYYY-MM-DD):").grid(
            row=1, column=0, sticky='w', pady=4)
        self.date_var = tk.StringVar(value=default_date)
        ttk.Entry(grid, textvariable=self.date_var, width=30).grid(
            row=1, column=1, sticky='w', pady=4)

        ttk.Label(grid, text="Preferred time (HH:MM):").grid(
            row=2, column=0, sticky='w', pady=4)
        self.time_var = tk.StringVar(value='10:00')
        ttk.Entry(grid, textvariable=self.time_var, width=30).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Reason (briefly):").pack(anchor='w',
                                                         pady=(8, 2))
        self.reason_text = tk.Text(frame, width=54, height=8, wrap='word')
        self.reason_text.pack(fill='x')

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(12, 0))
        ttk.Button(btns, text="Submit Request",
                   command=self._save).pack(side='right', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='right', padx=4)

    def _save(self):
        atype = self.type_var.get().strip() or 'General'
        date_val = self.date_var.get().strip()
        time_val = self.time_var.get().strip()
        reason = self.reason_text.get('1.0', 'end').strip()

        if not (date_val and time_val):
            messagebox.showerror("Missing",
                                 "Preferred date and time are required.",
                                 parent=self.dialog)
            return
        today = datetime.now().date()
        try:
            chosen = datetime.strptime(date_val, '%Y-%m-%d').date()
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 f"'{date_val}' is not YYYY-MM-DD.",
                                 parent=self.dialog)
            return
        if chosen < today:
            messagebox.showerror("Invalid Date",
                                 "Preferred date cannot be in the past.",
                                 parent=self.dialog)
            return
        try:
            datetime.strptime(time_val, '%H:%M')
        except ValueError:
            messagebox.showerror("Invalid Time",
                                 f"'{time_val}' is not HH:MM.",
                                 parent=self.dialog)
            return

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO health_appointments "
                    "(student_id, appointment_type, appointment_date, "
                    " appointment_time, provider, reason, status, notes, "
                    " scheduled_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)",
                    (self.student_id, atype, date_val, time_val,
                     '', reason, 'Requested by student', now)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Request Failed",
                                 f"Could not submit request: {e}",
                                 parent=self.dialog)
            return
        messagebox.showinfo(
            "Request Submitted",
            f"Your {atype.lower()} appointment on {date_val} at {time_val} "
            "has been requested. A staff member will confirm shortly.",
            parent=self.dialog)
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_health_student_portal(parent, auth):
    """Module-level entry point."""
    return HealthStudentPortal(parent, auth)
