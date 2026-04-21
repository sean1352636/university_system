"""Student Union — Student portal.

Read-only browse of upcoming union events, active elections, and clubs.
Election voting and event RSVPs remain in the full StudentUnionGUI for now
(this is a lightweight viewer). Admins retain the full GUI.
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


class StudentUnionStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        self.window = tk.Toplevel(parent)
        self.window.title("Student Union — My Portal")
        self.window.geometry("1050x680")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#8e44ad', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Student Union — {display}",
                 font=('Arial', 14, 'bold'), bg='#8e44ad', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#5b2c6f', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#5b2c6f', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_events_tab(nb)
        self._build_elections_tab(nb)
        self._build_clubs_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_events_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Upcoming Events")
        ttk.Label(frame, text="Upcoming union events",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        cols = ('date', 'time', 'name', 'location', 'attendees', 'category')
        self.events_tree = ttk.Treeview(frame, columns=cols,
                                        show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'Date', 110), ('time', 'Time', 80),
            ('name', 'Event', 280), ('location', 'Location', 180),
            ('attendees', 'Attendees', 110), ('category', 'Category', 130),
        ]:
            self.events_tree.heading(key, text=title)
            self.events_tree.column(key, width=width,
                                    anchor='w' if key in ('name', 'location',
                                                          'category')
                                                  else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=vsb.set)
        self.events_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _build_elections_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Elections")
        ttk.Label(frame, text="Active and upcoming elections",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        cols = ('position', 'department', 'voting_start', 'voting_end', 'status')
        self.elect_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        for key, title, width in [
            ('position', 'Position', 260),
            ('department', 'Department', 140),
            ('voting_start', 'Voting Start', 140),
            ('voting_end', 'Voting End', 140),
            ('status', 'Status', 110),
        ]:
            self.elect_tree.heading(key, text=title)
            self.elect_tree.column(key, width=width,
                                   anchor='w' if key == 'position'
                                                 else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.elect_tree.yview)
        self.elect_tree.configure(yscrollcommand=vsb.set)
        self.elect_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.elect_tree.tag_configure('voting', background='#d5f5e3')

    def _build_clubs_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Clubs")
        ttk.Label(frame, text="Student union clubs",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        cols = ('name', 'category', 'members', 'status')
        self.clubs_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Club', 300), ('category', 'Category', 180),
            ('members', 'Members', 110), ('status', 'Status', 120),
        ]:
            self.clubs_tree.heading(key, text=title)
            self.clubs_tree.column(key, width=width,
                                   anchor='w' if key in ('name', 'category')
                                                 else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.clubs_tree.yview)
        self.clubs_tree.configure(yscrollcommand=vsb.set)
        self.clubs_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_events()
        self._load_elections()
        self._load_clubs()

    def _load_events(self):
        for i in self.events_tree.get_children():
            self.events_tree.delete(i)
        today = datetime.now().date().isoformat()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT event_date, start_time, event_name, location, "
                    "       current_attendees, max_attendees, category "
                    "FROM union_events "
                    "WHERE event_date >= ? AND COALESCE(status, 'scheduled') "
                    "                           != 'cancelled' "
                    "ORDER BY event_date ASC, start_time ASC LIMIT 500",
                    (today,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for date, start, name, loc, cur_att, max_att, cat in rows:
            att = f"{cur_att or 0}/{max_att or '∞'}"
            self.events_tree.insert('', 'end', values=(
                (date or '')[:10], (start or '')[:5],
                name or '', loc or '', att, cat or ''
            ))
        self.status_var.set(f"{len(rows)} upcoming event(s).")

    def _load_elections(self):
        for i in self.elect_tree.get_children():
            self.elect_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT position, department, voting_start, voting_end, "
                    "       status "
                    "FROM union_elections "
                    "WHERE COALESCE(status, '') NOT IN ('closed', 'cancelled') "
                    "ORDER BY voting_start ASC LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for pos, dept, vs, ve, status in rows:
            tag = ('voting',) if status == 'voting' else ()
            self.elect_tree.insert('', 'end', values=(
                pos or '', dept or '',
                (vs or '')[:16], (ve or '')[:16], status or ''
            ), tags=tag)

    def _load_clubs(self):
        for i in self.clubs_tree.get_children():
            self.clubs_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT club_name, category, member_count, status "
                    "FROM student_clubs "
                    "WHERE COALESCE(status, 'active') = 'active' "
                    "ORDER BY club_name LIMIT 500"
                )
                for row in cur.fetchall():
                    self.clubs_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        row[2] or 0, row[3] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)


def launch_student_union_student_portal(parent, auth):
    return StudentUnionStudentPortal(parent, auth)
