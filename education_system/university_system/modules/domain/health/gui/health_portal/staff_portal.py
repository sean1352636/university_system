"""Health Portal — Staff/Instructor portal.

A focused clinical-operations window for health staff and instructors:
view today's and upcoming appointments, schedule / update / complete /
cancel appointments, and look up a student's allergies and emergency
contacts. Admins retain the full `HealthPortalGUI` (records, vaccinations,
vitals, prescriptions, lab results, surveillance, reports, maintenance).
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

_STATUS_VALUES = ['scheduled', 'completed', 'cancelled', 'no_show']


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class HealthStaffPortal:
    """Appointment management + student look-up for health staff."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_label = self._resolve_user_label()

        self.window = tk.Toplevel(parent)
        self.window.title("Health Portal — Staff")
        self.window.geometry("1200x760")
        self.window.minsize(1000, 640)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Loading…")
        self.scope_var = tk.StringVar(value='Upcoming')
        self.status_filter_var = tk.StringVar(value='All')
        self.lookup_var = tk.StringVar()

        self._build_ui()
        self._load_appointments()

    def _resolve_user_label(self):
        user = (self.auth.current_user if self.auth else None) or {}
        return (user.get('display_name') or user.get('username')
                or str(user.get('id') or 'staff'))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#16a085', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Health — Staff Clinic View ({self.user_label})",
                 font=('Arial', 14, 'bold'), bg='#16a085', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self._build_appointments_tab(nb)
        self._build_student_lookup_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    # -- Appointments tab ---------------------------------------------

    def _build_appointments_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Appointments")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))

        ttk.Label(bar, text="Scope:").pack(side='left', padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.scope_var,
                     state='readonly', width=14,
                     values=['Today', 'Upcoming', 'Past', 'All']
                     ).pack(side='left', padx=(0, 12))

        ttk.Label(bar, text="Status:").pack(side='left', padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.status_filter_var,
                     state='readonly', width=14,
                     values=['All'] + _STATUS_VALUES
                     ).pack(side='left', padx=(0, 12))

        ttk.Button(bar, text="Apply",
                   command=self._load_appointments).pack(side='left')
        ttk.Button(bar, text="+ New",
                   command=self._new_appointment).pack(side='right')
        ttk.Button(bar, text="Edit",
                   command=self._edit_appointment).pack(side='right', padx=4)
        ttk.Button(bar, text="Complete",
                   command=lambda: self._set_status('completed')
                   ).pack(side='right', padx=4)
        ttk.Button(bar, text="Cancel",
                   command=lambda: self._set_status('cancelled')
                   ).pack(side='right', padx=4)
        ttk.Button(bar, text="No-show",
                   command=lambda: self._set_status('no_show')
                   ).pack(side='right', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_appointments
                   ).pack(side='right', padx=4)

        cols = ('date', 'time', 'student', 'type', 'provider', 'status')
        self.appt_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        headings = [
            ('date', 'Date', 110),
            ('time', 'Time', 80),
            ('student', 'Student', 220),
            ('type', 'Type', 120),
            ('provider', 'Provider', 150),
            ('status', 'Status', 110),
        ]
        for key, title, width in headings:
            self.appt_tree.heading(key, text=title)
            self.appt_tree.column(key, width=width,
                                  anchor='w' if key in ('student', 'provider')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.appt_tree.yview)
        self.appt_tree.configure(yscrollcommand=vsb.set)
        self.appt_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.appt_tree.bind('<Double-1>', lambda _e: self._edit_appointment())
        self.appt_tree.tag_configure('today', background='#fef9e7')
        self.appt_tree.tag_configure('past', foreground='#888')
        self.appt_tree.tag_configure('done', background='#eafaf1')

    def _load_appointments(self):
        for i in self.appt_tree.get_children():
            self.appt_tree.delete(i)

        today_str = datetime.now().date().isoformat()
        clauses = []
        params = []

        scope = self.scope_var.get()
        if scope == 'Today':
            clauses.append("appointment_date = ?")
            params.append(today_str)
        elif scope == 'Upcoming':
            clauses.append("appointment_date >= ?")
            params.append(today_str)
        elif scope == 'Past':
            clauses.append("appointment_date < ?")
            params.append(today_str)

        status_filter = self.status_filter_var.get()
        if status_filter and status_filter != 'All':
            clauses.append("a.status = ?")
            params.append(status_filter)

        sql = (
            "SELECT a.id, a.appointment_date, a.appointment_time, "
            "       a.student_id, "
            "       COALESCE(s.first_name || ' ' || s.last_name, a.student_id), "
            "       a.appointment_type, a.provider, a.status "
            "FROM health_appointments a "
            "LEFT JOIN students s ON s.student_id = a.student_id"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if scope == 'Past':
            sql += " ORDER BY appointment_date DESC, appointment_time DESC"
        else:
            sql += " ORDER BY appointment_date ASC, appointment_time ASC"
        sql += " LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load appointments: {e}",
                                 parent=self.window)
            return

        for aid, date, time_, sid, name, atype, provider, status in rows:
            tag = ()
            if status in ('completed',):
                tag = ('done',)
            elif date == today_str and status == 'scheduled':
                tag = ('today',)
            elif date and date < today_str and status == 'scheduled':
                tag = ('past',)
            self.appt_tree.insert('', 'end', iid=str(aid), values=(
                date or '',
                (time_ or '')[:5],
                f"{sid} — {name}",
                atype or '',
                provider or '',
                status or ''
            ), tags=tag)

        self.status_var.set(f"{len(rows)} appointment(s).")

    def _new_appointment(self):
        AppointmentDialog(self.window, appointment=None,
                          default_provider=self.user_label,
                          on_save=self._load_appointments)

    def _edit_appointment(self):
        sel = self.appt_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an appointment to edit.",
                                parent=self.window)
            return
        aid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, student_id, appointment_type, "
                    "       appointment_date, appointment_time, provider, "
                    "       reason, status, notes "
                    "FROM health_appointments WHERE id = ?",
                    (aid,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if row:
            AppointmentDialog(self.window, appointment=row,
                              default_provider=self.user_label,
                              on_save=self._load_appointments)

    def _set_status(self, new_status):
        sel = self.appt_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an appointment first.",
                                parent=self.window)
            return
        aid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE health_appointments SET status = ? WHERE id = ?",
                    (new_status, aid)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self.status_var.set(f"Appointment {aid} → {new_status}.")
        self._load_appointments()

    # -- Student look-up tab ------------------------------------------

    def _build_student_lookup_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Student Lookup")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Student ID or name:").pack(side='left', padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.lookup_var, width=30)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._do_lookup())
        ttk.Button(bar, text="Search",
                   command=self._do_lookup).pack(side='left')

        self.lookup_info_var = tk.StringVar(
            value="Search a student to see their allergies and emergency contacts."
        )
        ttk.Label(frame, textvariable=self.lookup_info_var,
                  font=('Arial', 10, 'bold'),
                  wraplength=1000, justify='left').pack(anchor='w', pady=(6, 8))

        # Allergies panel
        allergies = ttk.LabelFrame(frame, text="Allergies", padding=6)
        allergies.pack(fill='both', expand=False, pady=(0, 6))
        a_cols = ('allergen', 'severity', 'reaction', 'diagnosed')
        self.allergy_tree = ttk.Treeview(allergies, columns=a_cols,
                                         show='headings', height=5)
        for key, title, width in [
            ('allergen', 'Allergen', 200),
            ('severity', 'Severity', 100),
            ('reaction', 'Reaction', 360),
            ('diagnosed', 'Diagnosed', 110),
        ]:
            self.allergy_tree.heading(key, text=title)
            self.allergy_tree.column(key, width=width,
                                     anchor='w' if key in ('allergen',
                                                           'reaction')
                                                   else 'center')
        self.allergy_tree.pack(fill='both', expand=True)

        # Emergency contacts panel
        contacts = ttk.LabelFrame(frame, text="Emergency contacts", padding=6)
        contacts.pack(fill='both', expand=True)
        c_cols = ('name', 'relationship', 'phone', 'email', 'decision_maker')
        self.contacts_tree = ttk.Treeview(contacts, columns=c_cols,
                                          show='headings', height=6)
        for key, title, width in [
            ('name', 'Name', 200),
            ('relationship', 'Relation', 120),
            ('phone', 'Phone', 160),
            ('email', 'Email', 220),
            ('decision_maker', 'Decision maker', 120),
        ]:
            self.contacts_tree.heading(key, text=title)
            self.contacts_tree.column(key, width=width,
                                      anchor='w' if key in ('name', 'email')
                                                    else 'center')
        self.contacts_tree.pack(fill='both', expand=True)

    def _do_lookup(self):
        query = self.lookup_var.get().strip()
        if not query:
            return
        for tree in (self.allergy_tree, self.contacts_tree):
            for i in tree.get_children():
                tree.delete(i)

        try:
            with _connect() as conn:
                cur = conn.cursor()
                like = f"%{query}%"
                cur.execute(
                    "SELECT student_id, first_name, last_name "
                    "FROM students "
                    "WHERE student_id = ? OR first_name LIKE ? "
                    "   OR last_name LIKE ? "
                    "ORDER BY last_name LIMIT 1",
                    (query, like, like)
                )
                student = cur.fetchone()
                if not student:
                    self.lookup_info_var.set(
                        f"No student found matching '{query}'."
                    )
                    return
                sid, fn, ln = student
                self.lookup_info_var.set(
                    f"Student: {sid} — {fn or ''} {ln or ''}"
                )

                cur.execute(
                    "SELECT allergen, severity, reaction_description, "
                    "       diagnosed_date "
                    "FROM allergies WHERE student_id = ? "
                    "ORDER BY severity DESC",
                    (sid,)
                )
                for row in cur.fetchall():
                    self.allergy_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        row[2] or '', (row[3] or '')[:10]
                    ))

                cur.execute(
                    "SELECT contact_name, relationship, phone_primary, email, "
                    "       medical_decision_maker "
                    "FROM emergency_contacts WHERE student_id = ? "
                    "ORDER BY priority_order",
                    (sid,)
                )
                for row in cur.fetchall():
                    self.contacts_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '', row[2] or '',
                        row[3] or '',
                        'Yes' if row[4] else 'No'
                    ))
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Lookup failed: {e}",
                                 parent=self.window)


# ----------------------------------------------------------------------
# Appointment dialog
# ----------------------------------------------------------------------


class AppointmentDialog:
    """Create or edit a health appointment."""

    def __init__(self, parent, appointment, default_provider, on_save):
        self.appointment = appointment  # tuple or None
        self.default_provider = default_provider
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Appointment" if appointment else "New Appointment")
        self.dialog.geometry("500x520")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=4)
        self.sid_var = tk.StringVar(
            value=appointment[1] if appointment else ''
        )
        sid_entry = ttk.Entry(frame, textvariable=self.sid_var, width=40)
        sid_entry.grid(row=0, column=1, sticky='w', pady=4)
        if appointment:
            sid_entry.configure(state='readonly')

        ttk.Label(frame, text="Type:").grid(row=1, column=0, sticky='w', pady=4)
        self.type_var = tk.StringVar(
            value=(appointment[2] if appointment else 'General')
        )
        ttk.Combobox(frame, textvariable=self.type_var,
                     values=_APPT_TYPES, width=38).grid(
            row=1, column=1, sticky='w', pady=4)

        default_date = (datetime.now() + timedelta(days=1)
                        ).date().isoformat()
        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0,
                                                          sticky='w', pady=4)
        self.date_var = tk.StringVar(
            value=(appointment[3] if appointment else default_date)
        )
        ttk.Entry(frame, textvariable=self.date_var, width=40).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Time (HH:MM):").grid(row=3, column=0,
                                                     sticky='w', pady=4)
        self.time_var = tk.StringVar(
            value=(appointment[4] if appointment else '09:00')
        )
        ttk.Entry(frame, textvariable=self.time_var, width=40).grid(
            row=3, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Provider:").grid(row=4, column=0,
                                                 sticky='w', pady=4)
        self.provider_var = tk.StringVar(
            value=(appointment[5] if appointment else default_provider)
        )
        ttk.Entry(frame, textvariable=self.provider_var, width=40).grid(
            row=4, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Status:").grid(row=5, column=0,
                                               sticky='w', pady=4)
        self.status_var = tk.StringVar(
            value=(appointment[7] if appointment else 'scheduled')
        )
        ttk.Combobox(frame, textvariable=self.status_var,
                     values=_STATUS_VALUES, state='readonly', width=38).grid(
            row=5, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Reason:").grid(row=6, column=0,
                                               sticky='nw', pady=4)
        self.reason_text = tk.Text(frame, width=40, height=3, wrap='word')
        self.reason_text.grid(row=6, column=1, sticky='w', pady=4)
        if appointment and appointment[6]:
            self.reason_text.insert('1.0', appointment[6])

        ttk.Label(frame, text="Notes:").grid(row=7, column=0,
                                              sticky='nw', pady=4)
        self.notes_text = tk.Text(frame, width=40, height=5, wrap='word')
        self.notes_text.grid(row=7, column=1, sticky='w', pady=4)
        if appointment and appointment[8]:
            self.notes_text.insert('1.0', appointment[8])

        btns = ttk.Frame(frame)
        btns.grid(row=8, column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        sid = self.sid_var.get().strip()
        atype = self.type_var.get().strip() or 'General'
        date_val = self.date_var.get().strip()
        time_val = self.time_var.get().strip()
        provider = self.provider_var.get().strip()
        status = self.status_var.get().strip() or 'scheduled'
        reason = self.reason_text.get('1.0', 'end').strip()
        notes = self.notes_text.get('1.0', 'end').strip()

        if not (sid and date_val and time_val):
            messagebox.showerror("Missing Fields",
                                 "Student ID, date, and time are required.",
                                 parent=self.dialog)
            return
        try:
            datetime.strptime(date_val, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 f"'{date_val}' is not YYYY-MM-DD.",
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
                if self.appointment:
                    cur.execute(
                        "UPDATE health_appointments "
                        "SET appointment_type = ?, appointment_date = ?, "
                        "    appointment_time = ?, provider = ?, "
                        "    reason = ?, status = ?, notes = ? "
                        "WHERE id = ?",
                        (atype, date_val, time_val, provider, reason,
                         status, notes, self.appointment[0])
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM students WHERE student_id = ?",
                        (sid,)
                    )
                    if not cur.fetchone():
                        messagebox.showerror(
                            "Unknown Student",
                            f"No student with ID '{sid}'.",
                            parent=self.dialog)
                        return
                    cur.execute(
                        "INSERT INTO health_appointments "
                        "(student_id, appointment_type, appointment_date, "
                        " appointment_time, provider, reason, status, notes, "
                        " scheduled_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (sid, atype, date_val, time_val, provider, reason,
                         status, notes, now)
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed",
                                 f"Could not save appointment: {e}",
                                 parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_health_staff_portal(parent, auth):
    """Module-level entry point."""
    return HealthStaffPortal(parent, auth)
