"""Academic Calendar — Staff/Instructor portal.

A focused event-management window for staff and instructors: list calendar
events, filter by type and date range, create/edit/delete entries. Admins
still open the full `CalendarGUI` (with dashboard, academic views, bulk
import, workflows, recurring events, etc.) via the launcher.
"""

import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_DEFAULT_TYPES = [
    'Academic', 'Exam', 'Holiday', 'Deadline',
    'Orientation', 'Graduation', 'Social', 'Other',
]


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CalendarStaffPortal:
    """Event management for staff/instructors."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_label = self._resolve_user_label()

        self.window = tk.Toplevel(parent)
        self.window.title("Academic Calendar — Staff Portal")
        self.window.geometry("1150x720")
        self.window.minsize(980, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Loading events…")
        self.filter_type_var = tk.StringVar(value='All')
        self.filter_from_var = tk.StringVar(value='')
        self.filter_to_var = tk.StringVar(value='')

        self._build_ui()
        self._load_events()

    def _resolve_user_label(self):
        user = (self.auth.current_user if self.auth else None) or {}
        return (user.get('display_name') or user.get('username')
                or str(user.get('user_id') or user.get('id') or 'unknown'))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#34495e', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Academic Calendar — {self.user_label}",
                 font=('Arial', 14, 'bold'), bg='#34495e', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        # Filter bar
        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')

        ttk.Label(bar, text="Type:").pack(side='left', padx=(0, 4))
        self.type_combo = ttk.Combobox(bar, textvariable=self.filter_type_var,
                                       state='readonly', width=14,
                                       values=['All'] + _DEFAULT_TYPES)
        self.type_combo.pack(side='left', padx=(0, 12))
        self.type_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._load_events())

        ttk.Label(bar, text="From (YYYY-MM-DD):").pack(side='left', padx=(0, 4))
        ttk.Entry(bar, textvariable=self.filter_from_var, width=12
                  ).pack(side='left', padx=(0, 8))
        ttk.Label(bar, text="To:").pack(side='left', padx=(0, 4))
        ttk.Entry(bar, textvariable=self.filter_to_var, width=12
                  ).pack(side='left', padx=(0, 8))
        ttk.Button(bar, text="Apply",
                   command=self._load_events).pack(side='left')
        ttk.Button(bar, text="Clear",
                   command=self._clear_filters).pack(side='left', padx=4)

        ttk.Button(bar, text="+ New Event",
                   command=self._create_event).pack(side='right')
        ttk.Button(bar, text="Edit",
                   command=self._edit_event).pack(side='right', padx=4)
        ttk.Button(bar, text="Delete",
                   command=self._delete_event).pack(side='right', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_events).pack(side='right', padx=4)

        # Events table
        table = ttk.Frame(self.window, padding=(10, 4, 10, 4))
        table.pack(fill='both', expand=True)

        cols = ('date', 'name', 'type', 'range', 'created_by')
        self.tree = ttk.Treeview(table, columns=cols,
                                 show='headings', selectmode='browse')
        headings = [
            ('date', 'Date', 110),
            ('name', 'Event', 340),
            ('type', 'Type', 120),
            ('range', 'Range', 200),
            ('created_by', 'Created by', 150),
        ]
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('name', 'created_by')
                                         else 'center')
        vsb = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda _e: self._edit_event())

        # Description preview
        preview = ttk.LabelFrame(self.window, text="Description", padding=6)
        preview.pack(fill='x', padx=10, pady=(0, 4))
        self.desc_var = tk.StringVar(value="Select an event to see its description.")
        ttk.Label(preview, textvariable=self.desc_var,
                  wraplength=1000, justify='left').pack(anchor='w')
        self.tree.bind('<<TreeviewSelect>>', self._on_event_selected)

        # Status bar
        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _clear_filters(self):
        self.filter_type_var.set('All')
        self.filter_from_var.set('')
        self.filter_to_var.set('')
        self._load_events()

    def _load_events(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.desc_var.set("Select an event to see its description.")

        clauses = []
        params = []
        etype = self.filter_type_var.get()
        if etype and etype != 'All':
            clauses.append("event_type = ?")
            params.append(etype)

        date_from = self.filter_from_var.get().strip()
        date_to = self.filter_to_var.get().strip()
        for raw, op in ((date_from, '>='), (date_to, '<=')):
            if not raw:
                continue
            try:
                datetime.strptime(raw, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror(
                    "Invalid Date",
                    f"'{raw}' is not YYYY-MM-DD.", parent=self.window)
                return
            clauses.append(f"COALESCE(date, date_start) {op} ?")
            params.append(raw)

        sql = (
            "SELECT id, name, event_type, "
            "       COALESCE(date, date_start) AS event_date, "
            "       date_start, date_end, description, created_by "
            "FROM academic_calendar_events"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY COALESCE(date, date_start) DESC, name LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load events: {e}",
                                 parent=self.window)
            return

        self._event_descriptions = {}
        for eid, name, etype_val, ed, ds, de, desc, cb in rows:
            rng = ''
            if ds and de:
                rng = f"{ds[:10]} → {de[:10]}"
            elif ds:
                rng = f"from {ds[:10]}"
            elif de:
                rng = f"until {de[:10]}"
            self.tree.insert('', 'end', iid=eid, values=(
                (ed or '')[:10], name, etype_val or '', rng, cb or ''
            ))
            self._event_descriptions[eid] = desc or ''

        self.status_var.set(f"{len(rows)} event(s).")

    def _on_event_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        eid = sel[0]
        self.desc_var.set(
            self._event_descriptions.get(eid) or "(no description)"
        )

    # ------------------------------------------------------------------
    # Create / edit / delete
    # ------------------------------------------------------------------

    def _create_event(self):
        CalendarEventDialog(self.window, event=None,
                            creator_label=self.user_label,
                            on_save=self._load_events)

    def _edit_event(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an event to edit.",
                                parent=self.window)
            return
        eid = sel[0]
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, date, date_start, date_end, "
                    "       description, event_type, created_by "
                    "FROM academic_calendar_events WHERE id = ?",
                    (eid,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if row:
            CalendarEventDialog(self.window, event=row,
                                creator_label=self.user_label,
                                on_save=self._load_events)

    def _delete_event(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an event to delete.",
                                parent=self.window)
            return
        eid = sel[0]
        name = self.tree.item(eid, 'values')[1]
        if not messagebox.askyesno(
                "Delete Event",
                f"Permanently delete '{name}'?\n\n"
                "This cannot be undone.",
                parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM academic_calendar_events WHERE id = ?",
                    (eid,)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Delete Failed",
                                 f"Could not delete: {e}",
                                 parent=self.window)
            return
        self._load_events()


class CalendarEventDialog:
    """Create or edit an academic calendar event."""

    def __init__(self, parent, event, creator_label, on_save):
        self.event = event  # tuple or None
        self.creator_label = creator_label
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Event" if event else "New Event")
        self.dialog.geometry("500x520")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='w', pady=4)
        self.name_var = tk.StringVar(value=event[1] if event else '')
        ttk.Entry(frame, textvariable=self.name_var, width=42).grid(
            row=0, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Type:").grid(row=1, column=0, sticky='w', pady=4)
        self.type_var = tk.StringVar(
            value=(event[6] if event else 'Academic')
        )
        ttk.Combobox(frame, textvariable=self.type_var,
                     values=_DEFAULT_TYPES, width=40).grid(
            row=1, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0,
                                                          sticky='w', pady=4)
        self.date_var = tk.StringVar(
            value=((event[2] or '')[:10] if event else '')
        )
        ttk.Entry(frame, textvariable=self.date_var, width=42).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Start date (optional):").grid(
            row=3, column=0, sticky='w', pady=4)
        self.start_var = tk.StringVar(
            value=((event[3] or '')[:10] if event else '')
        )
        ttk.Entry(frame, textvariable=self.start_var, width=42).grid(
            row=3, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="End date (optional):").grid(
            row=4, column=0, sticky='w', pady=4)
        self.end_var = tk.StringVar(
            value=((event[4] or '')[:10] if event else '')
        )
        ttk.Entry(frame, textvariable=self.end_var, width=42).grid(
            row=4, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=5, column=0,
                                                    sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=42, height=10, wrap='word')
        self.desc_text.grid(row=5, column=1, sticky='w', pady=4)
        if event and event[5]:
            self.desc_text.insert('1.0', event[5])

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text="Save", command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        name = self.name_var.get().strip()
        etype = self.type_var.get().strip() or 'Academic'
        date_val = self.date_var.get().strip()
        start_val = self.start_var.get().strip()
        end_val = self.end_var.get().strip()
        desc = self.desc_text.get('1.0', 'end').strip()

        if not name:
            messagebox.showerror("Missing",
                                 "Event name is required.",
                                 parent=self.dialog)
            return
        if not (date_val or start_val):
            messagebox.showerror(
                "Missing Date",
                "Provide either a single date or a start date.",
                parent=self.dialog)
            return
        for raw in (date_val, start_val, end_val):
            if not raw:
                continue
            try:
                datetime.strptime(raw, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Invalid Date",
                                     f"'{raw}' is not YYYY-MM-DD.",
                                     parent=self.dialog)
                return
        if start_val and end_val and end_val < start_val:
            messagebox.showerror("Invalid Range",
                                 "End date cannot be before start date.",
                                 parent=self.dialog)
            return

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                if self.event:
                    cur.execute(
                        "UPDATE academic_calendar_events "
                        "SET name = ?, date = ?, date_start = ?, date_end = ?, "
                        "    description = ?, event_type = ?, "
                        "    last_modified = ? "
                        "WHERE id = ?",
                        (name, date_val or None,
                         start_val or None, end_val or None,
                         desc, etype, now, self.event[0])
                    )
                else:
                    eid = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO academic_calendar_events "
                        "(id, name, date, date_start, date_end, description, "
                        " event_type, date_added, last_modified, created_by) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (eid, name, date_val or None,
                         start_val or None, end_val or None,
                         desc, etype, now, now, self.creator_label)
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed",
                                 f"Could not save event: {e}",
                                 parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_calendar_staff_portal(parent, auth):
    """Module-level entry point."""
    return CalendarStaffPortal(parent, auth)
