"""Campus Events — Staff/Instructor portal.

Manage campus events in `unified_events`: create, cancel, filter by
scope/status, and review registrations per event. Admins retain the full
`CampusEventsGUI` for advanced features (sponsors, announcements, QR
codes, waitlists, feedback moderation).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_EVENT_TYPES = [
    'Social', 'Academic', 'Cultural', 'Sports', 'Workshop',
    'Career', 'Orientation', 'Other',
]


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CampusEventsStaffPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.user_id = user.get('id') or user.get('user_id')
        self.user_label = (user.get('display_name')
                           or user.get('username', 'staff'))

        self.window = tk.Toplevel(parent)
        self.window.title("Campus Events — Staff Portal")
        self.window.geometry("1150x720")
        self.window.minsize(960, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.scope_var = tk.StringVar(value='Upcoming')
        self.status_var = tk.StringVar(value='All')
        self.info_var = tk.StringVar(value="")

        self._build_ui()
        self._load_events()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#d35400', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Campus Events — Staff ({self.user_label})",
                 font=('Arial', 14, 'bold'), bg='#d35400', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Label(bar, text="Scope:").pack(side='left')
        ttk.Combobox(bar, textvariable=self.scope_var, state='readonly', width=12,
                     values=['Upcoming', 'Today', 'Past', 'All']
                     ).pack(side='left', padx=(4, 12))
        ttk.Label(bar, text="Status:").pack(side='left')
        ttk.Combobox(bar, textvariable=self.status_var, state='readonly', width=14,
                     values=['All', 'scheduled', 'cancelled', 'completed']
                     ).pack(side='left', padx=(4, 12))
        ttk.Button(bar, text="Apply",
                   command=self._load_events).pack(side='left')
        ttk.Button(bar, text="+ New",
                   command=self._new_event).pack(side='right')
        ttk.Button(bar, text="View Registrations",
                   command=self._view_registrations).pack(side='right', padx=4)
        ttk.Button(bar, text="Cancel",
                   command=lambda: self._set_status('cancelled')
                   ).pack(side='right', padx=4)

        paned = ttk.PanedWindow(self.window, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=(4, 4))

        events_frame = ttk.Frame(paned)
        paned.add(events_frame, weight=2)
        cols = ('date', 'title', 'type', 'location', 'capacity', 'status')
        self.tree = ttk.Treeview(events_frame, columns=cols,
                                 show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'When', 150), ('title', 'Title', 280),
            ('type', 'Type', 120), ('location', 'Location', 180),
            ('capacity', 'Reg/Cap', 110), ('status', 'Status', 110),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('title', 'location')
                                           else 'center')
        vsb = ttk.Scrollbar(events_frame, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.tag_configure('cancelled', foreground='#c0392b')

        reg_frame = ttk.LabelFrame(paned, text="Registrations", padding=6)
        paned.add(reg_frame, weight=1)
        r_cols = ('user_id', 'user_type', 'registered', 'status', 'guests')
        self.reg_tree = ttk.Treeview(reg_frame, columns=r_cols,
                                     show='headings', height=6)
        for key, title, width in [
            ('user_id', 'User', 130), ('user_type', 'Type', 100),
            ('registered', 'Registered', 150),
            ('status', 'Attendance', 110), ('guests', 'Guests', 70),
        ]:
            self.reg_tree.heading(key, text=title)
            self.reg_tree.column(key, width=width, anchor='center')
        r_vsb = ttk.Scrollbar(reg_frame, orient='vertical',
                              command=self.reg_tree.yview)
        self.reg_tree.configure(yscrollcommand=r_vsb.set)
        self.reg_tree.pack(side='left', fill='both', expand=True)
        r_vsb.pack(side='right', fill='y')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _load_events(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in self.reg_tree.get_children():
            self.reg_tree.delete(i)

        today = datetime.now().date().isoformat()
        clauses = []
        params = []
        scope = self.scope_var.get()
        if scope == 'Upcoming':
            clauses.append("date(start_datetime) >= ?")
            params.append(today)
        elif scope == 'Today':
            clauses.append("date(start_datetime) = ?")
            params.append(today)
        elif scope == 'Past':
            clauses.append("date(start_datetime) < ?")
            params.append(today)
        status = self.status_var.get()
        if status and status != 'All':
            clauses.append("status = ?")
            params.append(status)

        sql = (
            "SELECT event_id, start_datetime, title, event_type, location, "
            "       max_capacity, status, "
            "       (SELECT COUNT(*) FROM unified_event_registrations r "
            "        WHERE r.event_id = e.event_id) AS reg_count "
            "FROM unified_events e"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY start_datetime " + (
            "DESC" if scope == 'Past' else "ASC") + " LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return

        for eid, start, title, etype, loc, cap, st, reg_cnt in rows:
            cap_str = f"{reg_cnt}/{cap or '∞'}"
            tag = ('cancelled',) if st == 'cancelled' else ()
            self.tree.insert('', 'end', iid=str(eid), values=(
                (start or '')[:16], title or '', etype or '',
                loc or '', cap_str, st or ''
            ), tags=tag)

        self.info_var.set(f"{len(rows)} event(s).")

    def _on_select(self, _event=None):
        for i in self.reg_tree.get_children():
            self.reg_tree.delete(i)
        sel = self.tree.selection()
        if not sel:
            return
        eid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT user_id, user_type, registration_date, "
                    "       attendance_status, num_guests "
                    "FROM unified_event_registrations "
                    "WHERE event_id = ? "
                    "ORDER BY registration_date DESC LIMIT 500",
                    (eid,)
                )
                for row in cur.fetchall():
                    self.reg_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        (row[2] or '')[:16], row[3] or '', row[4] or 0
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)

    def _new_event(self):
        CampusEventDialog(self.window, user_id=self.user_id,
                          user_label=self.user_label,
                          on_save=self._load_events)

    def _set_status(self, new_status):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select an event first.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE unified_events SET status = ?, "
                    "       updated_at = ? WHERE event_id = ?",
                    (new_status, datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e), parent=self.window)
            return
        self._load_events()

    def _view_registrations(self):
        self._on_select()


class CampusEventDialog:
    def __init__(self, parent, user_id, user_label, on_save):
        self.user_id = user_id
        self.user_label = user_label
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Campus Event")
        self.dialog.geometry("480x460")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        self.title_var = tk.StringVar()
        self.type_var = tk.StringVar(value='Social')
        default_date = (datetime.now() + timedelta(days=7)
                        ).strftime('%Y-%m-%d %H:%M')
        self.start_var = tk.StringVar(value=default_date)
        self.end_var = tk.StringVar(value=default_date)
        self.location_var = tk.StringVar()
        self.cap_var = tk.StringVar(value='50')
        self.public_var = tk.BooleanVar(value=True)

        for i, (label, widget_factory) in enumerate([
            ("Title:", lambda f: ttk.Entry(f, textvariable=self.title_var, width=32)),
            ("Type:", lambda f: ttk.Combobox(f, textvariable=self.type_var,
                                              values=_EVENT_TYPES, width=30)),
            ("Start (YYYY-MM-DD HH:MM):",
                lambda f: ttk.Entry(f, textvariable=self.start_var, width=32)),
            ("End (YYYY-MM-DD HH:MM):",
                lambda f: ttk.Entry(f, textvariable=self.end_var, width=32)),
            ("Location:", lambda f: ttk.Entry(f, textvariable=self.location_var, width=32)),
            ("Max capacity:", lambda f: ttk.Entry(f, textvariable=self.cap_var, width=32)),
        ]):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', pady=4)
            widget_factory(frame).grid(row=i, column=1, sticky='w', pady=4)

        ttk.Checkbutton(frame, text="Public (visible to all students)",
                        variable=self.public_var).grid(
            row=6, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=7, column=0,
                                                    sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=32, height=5, wrap='word')
        self.desc_text.grid(row=7, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=8, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        title = self.title_var.get().strip()
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        if not (title and start):
            messagebox.showerror("Missing",
                                 "Title and start datetime required.",
                                 parent=self.dialog)
            return
        for raw in (start, end):
            if not raw:
                continue
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
            except ValueError:
                messagebox.showerror("Invalid Datetime",
                                     f"'{raw}' is not YYYY-MM-DD HH:MM.",
                                     parent=self.dialog)
                return
        try:
            cap = int(self.cap_var.get() or 0)
        except ValueError:
            cap = 0

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO unified_events "
                    "(source_type, title, description, event_type, "
                    " start_datetime, end_datetime, location, "
                    " organizer_id, organizer_name, max_capacity, "
                    " registration_required, is_public, status, "
                    " created_by, created_at, updated_at) "
                    "VALUES ('campus_events', ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "        1, ?, 'scheduled', ?, ?, ?)",
                    (title, self.desc_text.get('1.0', 'end').strip(),
                     self.type_var.get().strip() or 'Social',
                     start, end or None,
                     self.location_var.get().strip(),
                     self.user_id, self.user_label, cap,
                     1 if self.public_var.get() else 0,
                     self.user_id, now, now)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed", str(e), parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_campus_events_staff_portal(parent, auth):
    return CampusEventsStaffPortal(parent, auth)
