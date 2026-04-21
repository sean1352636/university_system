"""Academic Calendar — Student portal.

A read-only, student-facing calendar: upcoming events (default filter) and
past events (toggle), filter by event type, and a description preview for
the selected event. Rows are tinted to show what's today, this week, or
already passed.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CalendarStudentPortal:
    """Read-only academic calendar viewer for students."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_label = self._resolve_user_label()

        self.window = tk.Toplevel(parent)
        self.window.title("Academic Calendar — My Portal")
        self.window.geometry("1050x660")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.filter_type_var = tk.StringVar(value='All')
        self.filter_scope_var = tk.StringVar(value='Upcoming')
        self.status_var = tk.StringVar(value="Loading events…")

        self._build_ui()
        self._load_events()

    def _resolve_user_label(self):
        user = (self.auth.current_user if self.auth else None) or {}
        return (user.get('display_name') or user.get('username', ''))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#2980b9', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"My Academic Calendar — {self.user_label}",
                 font=('Arial', 14, 'bold'), bg='#2980b9', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._load_events).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Label(bar, text="Show:").pack(side='left', padx=(0, 4))
        scope_combo = ttk.Combobox(
            bar, textvariable=self.filter_scope_var, state='readonly',
            values=['Upcoming', 'This week', 'This month', 'Past', 'All'],
            width=14,
        )
        scope_combo.pack(side='left', padx=(0, 12))
        scope_combo.bind('<<ComboboxSelected>>',
                         lambda _e: self._load_events())

        ttk.Label(bar, text="Type:").pack(side='left', padx=(0, 4))
        self.type_combo = ttk.Combobox(
            bar, textvariable=self.filter_type_var, state='readonly',
            width=14,
        )
        self.type_combo.pack(side='left')
        self.type_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._load_events())
        self._load_event_types()

        # Events table
        table = ttk.Frame(self.window, padding=(10, 4, 10, 4))
        table.pack(fill='both', expand=True)

        cols = ('date', 'name', 'type', 'range')
        self.tree = ttk.Treeview(table, columns=cols,
                                 show='headings', selectmode='browse')
        headings = [
            ('date', 'Date', 120),
            ('name', 'Event', 360),
            ('type', 'Type', 140),
            ('range', 'Range', 220),
        ]
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key == 'name' else 'center')
        vsb = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.tag_configure('today', background='#fef9e7')
        self.tree.tag_configure('this_week', background='#eafaf1')
        self.tree.tag_configure('past', foreground='#888')
        self.tree.bind('<<TreeviewSelect>>', self._on_event_selected)

        # Description preview
        preview = ttk.LabelFrame(self.window, text="Description", padding=6)
        preview.pack(fill='x', padx=10, pady=(0, 4))
        self.desc_var = tk.StringVar(
            value="Select an event to see its description."
        )
        ttk.Label(preview, textvariable=self.desc_var,
                  wraplength=1000, justify='left').pack(anchor='w')

        # Status bar
        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_event_types(self):
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT DISTINCT event_type FROM academic_calendar_events "
                    "WHERE event_type IS NOT NULL AND event_type != '' "
                    "ORDER BY event_type"
                )
                types = [r[0] for r in cur.fetchall()]
        except Exception:
            types = []
        self.type_combo['values'] = ['All'] + types

    def _load_events(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.desc_var.set("Select an event to see its description.")

        today = datetime.now().date()
        today_str = today.isoformat()

        clauses = []
        params = []

        etype = self.filter_type_var.get()
        if etype and etype != 'All':
            clauses.append("event_type = ?")
            params.append(etype)

        scope = self.filter_scope_var.get()
        if scope == 'Upcoming':
            clauses.append("COALESCE(date, date_start) >= ?")
            params.append(today_str)
        elif scope == 'Past':
            clauses.append("COALESCE(date, date_start) < ?")
            params.append(today_str)
        elif scope == 'This week':
            week_end = today + timedelta(days=7)
            clauses.append(
                "COALESCE(date, date_start) BETWEEN ? AND ?"
            )
            params.extend([today_str, week_end.isoformat()])
        elif scope == 'This month':
            if today.month == 12:
                month_end = today.replace(year=today.year + 1, month=1, day=1)
            else:
                month_end = today.replace(month=today.month + 1, day=1)
            month_end = month_end - timedelta(days=1)
            month_start = today.replace(day=1)
            clauses.append(
                "COALESCE(date, date_start) BETWEEN ? AND ?"
            )
            params.extend([month_start.isoformat(), month_end.isoformat()])

        sql = (
            "SELECT id, name, event_type, "
            "       COALESCE(date, date_start) AS event_date, "
            "       date_start, date_end, description "
            "FROM academic_calendar_events"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if scope == 'Past':
            sql += " ORDER BY COALESCE(date, date_start) DESC"
        else:
            sql += " ORDER BY COALESCE(date, date_start) ASC"
        sql += " LIMIT 500"

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

        week_end = today + timedelta(days=7)
        self._event_descriptions = {}
        for eid, name, etype_val, ed, ds, de, desc in rows:
            rng = ''
            if ds and de:
                rng = f"{ds[:10]} → {de[:10]}"
            elif ds:
                rng = f"from {ds[:10]}"
            elif de:
                rng = f"until {de[:10]}"
            tag = ()
            try:
                d = datetime.strptime((ed or '')[:10], '%Y-%m-%d').date()
                if d == today:
                    tag = ('today',)
                elif today < d <= week_end:
                    tag = ('this_week',)
                elif d < today:
                    tag = ('past',)
            except Exception:
                pass
            self.tree.insert('', 'end', iid=eid, values=(
                (ed or '')[:10], name, etype_val or '', rng
            ), tags=tag)
            self._event_descriptions[eid] = desc or ''

        self.status_var.set(f"{len(rows)} event(s).")

    def _on_event_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.desc_var.set(
            self._event_descriptions.get(sel[0]) or "(no description)"
        )


def launch_calendar_student_portal(parent, auth):
    """Module-level entry point."""
    return CalendarStudentPortal(parent, auth)
