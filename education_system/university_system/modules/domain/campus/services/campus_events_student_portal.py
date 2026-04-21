"""Campus Events — Student portal.

Browse upcoming campus events, register (writes to
`unified_event_registrations`), see "My registrations", and unregister.
Admins retain the full `CampusEventsGUI`.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CampusEventsStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.user_id = str(user.get('username') or user.get('user_id')
                           or user.get('id') or '')

        self.window = tk.Toplevel(parent)
        self.window.title("Campus Events — My Portal")
        self.window.geometry("1050x680")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.search_var = tk.StringVar()
        self.info_var = tk.StringVar(value="")
        self._registered_ids = set()

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#e67e22', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Campus Events — {display}",
                 font=('Arial', 14, 'bold'), bg='#e67e22', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#a04000', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#a04000', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_browse_tab(nb)
        self._build_mine_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_browse_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Browse Events")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_events())
        ttk.Button(bar, text="Search",
                   command=self._load_events).pack(side='left')
        ttk.Button(bar, text="Register",
                   command=self._register).pack(side='right')

        cols = ('date', 'title', 'type', 'location', 'capacity', 'mine')
        self.events_tree = ttk.Treeview(frame, columns=cols,
                                        show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'When', 140), ('title', 'Title', 280),
            ('type', 'Type', 120), ('location', 'Location', 160),
            ('capacity', 'Reg/Cap', 110), ('mine', 'Registered', 100),
        ]:
            self.events_tree.heading(key, text=title)
            self.events_tree.column(key, width=width,
                                    anchor='w' if key in ('title', 'location')
                                                  else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=vsb.set)
        self.events_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.events_tree.tag_configure('registered', background='#d5f5e3')

    def _build_mine_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Registrations")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="My upcoming and past event registrations",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Unregister",
                   command=self._unregister).pack(side='right')

        cols = ('date', 'title', 'location', 'status')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'When', 150), ('title', 'Title', 320),
            ('location', 'Location', 200), ('status', 'Status', 130),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width,
                                  anchor='w' if key in ('title', 'location')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_mine()
        self._load_events()

    def _load_events(self):
        for i in self.events_tree.get_children():
            self.events_tree.delete(i)
        today = datetime.now().date().isoformat()
        query = self.search_var.get().strip()

        sql = (
            "SELECT event_id, start_datetime, title, event_type, location, "
            "       max_capacity, "
            "       (SELECT COUNT(*) FROM unified_event_registrations r "
            "        WHERE r.event_id = e.event_id) AS reg_count "
            "FROM unified_events e "
            "WHERE date(start_datetime) >= ? "
            "  AND COALESCE(status, 'scheduled') = 'scheduled' "
            "  AND COALESCE(is_public, 1) = 1"
        )
        params = [today]
        if query:
            like = f"%{query}%"
            sql += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([like, like])
        sql += " ORDER BY start_datetime LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return

        for eid, start, title, etype, loc, cap, reg_cnt in rows:
            mine = eid in self._registered_ids
            tag = ('registered',) if mine else ()
            cap_str = f"{reg_cnt}/{cap or '∞'}"
            self.events_tree.insert('', 'end', iid=str(eid), values=(
                (start or '')[:16], title or '', etype or '',
                loc or '', cap_str, 'Yes' if mine else ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} upcoming event(s).")

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        self._registered_ids.clear()
        if not self.user_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT e.event_id, e.start_datetime, e.title, "
                    "       e.location, r.attendance_status "
                    "FROM unified_event_registrations r "
                    "JOIN unified_events e ON e.event_id = r.event_id "
                    "WHERE r.user_id = ? "
                    "ORDER BY e.start_datetime DESC LIMIT 500",
                    (self.user_id,)
                )
                for row in cur.fetchall():
                    self._registered_ids.add(row[0])
                    self.mine_tree.insert('', 'end', iid=str(row[0]), values=(
                        (row[1] or '')[:16], row[2] or '',
                        row[3] or '', row[4] or 'registered'
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _register(self):
        if not self.user_id:
            messagebox.showerror("Not Signed In",
                                 "Your account has no user ID.",
                                 parent=self.window)
            return
        sel = self.events_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an event to register for.",
                                parent=self.window)
            return
        eid = int(sel[0])
        if eid in self._registered_ids:
            messagebox.showinfo("Already Registered",
                                "You're already registered for this event.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO unified_event_registrations "
                    "(event_id, user_id, user_type, registration_date, "
                    " attendance_status) "
                    "VALUES (?, ?, 'student', ?, 'registered')",
                    (eid, self.user_id,
                     datetime.now().isoformat(timespec='seconds'))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Registration Failed", str(e),
                                 parent=self.window)
            return
        messagebox.showinfo("Registered",
                            "You're registered. See the 'My Registrations' tab.",
                            parent=self.window)
        self._refresh_all()

    def _unregister(self):
        sel = self.mine_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a registration to cancel.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Unregister",
                                   "Cancel your registration for this event?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM unified_event_registrations "
                    "WHERE event_id = ? AND user_id = ?",
                    (int(sel[0]), self.user_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Unregister Failed", str(e),
                                 parent=self.window)
            return
        self._refresh_all()


def launch_campus_events_student_portal(parent, auth):
    return CampusEventsStudentPortal(parent, auth)
