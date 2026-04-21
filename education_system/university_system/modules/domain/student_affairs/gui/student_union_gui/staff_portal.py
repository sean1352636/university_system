"""Student Union — Staff/Instructor portal.

A compact operational view: upcoming union events, active elections, and a
club roster with member counts. Staff can create / cancel union events
and open/close elections. Admins retain the full `StudentUnionGUI`
(events, elections, clubs, campaigns, analytics, competitions, volunteer
management, financial processing, book clubs, etc.).
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


class StudentUnionStaffPortal:
    """Events + elections + club roster for union staff."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_id = self._resolve_user_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Student Union — Staff Portal")
        self.window.geometry("1120x720")
        self.window.minsize(980, 620)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _resolve_user_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        return user.get('id') or user.get('user_id') or user.get('username')

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#8e44ad', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="Student Union — Staff",
                 font=('Arial', 14, 'bold'), bg='#8e44ad', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

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
        nb.add(frame, text="Events")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="+ New Event",
                   command=self._new_event).pack(side='left')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel_event).pack(side='left', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_events).pack(side='right')

        cols = ('date', 'time', 'name', 'location', 'attendees', 'status')
        self.events_tree = ttk.Treeview(frame, columns=cols,
                                        show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'Date', 110), ('time', 'Time', 90),
            ('name', 'Event', 300), ('location', 'Location', 180),
            ('attendees', 'Attendees', 110), ('status', 'Status', 100),
        ]:
            self.events_tree.heading(key, text=title)
            self.events_tree.column(key, width=width,
                                    anchor='w' if key in ('name', 'location')
                                                  else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=vsb.set)
        self.events_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _build_elections_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Elections")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Open Voting",
                   command=lambda: self._set_election_status('voting')
                   ).pack(side='left')
        ttk.Button(bar, text="Close Voting",
                   command=lambda: self._set_election_status('closed')
                   ).pack(side='left', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_elections).pack(side='right')

        cols = ('position', 'department', 'voting_start', 'voting_end', 'status')
        self.elect_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        for key, title, width in [
            ('position', 'Position', 240), ('department', 'Dept', 140),
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

    def _build_clubs_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Clubs")

        ttk.Label(frame, text="Active union clubs",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('name', 'category', 'members', 'president', 'status')
        self.clubs_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Club', 280), ('category', 'Category', 160),
            ('members', 'Members', 100), ('president', 'President ID', 130),
            ('status', 'Status', 110),
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

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh_all(self):
        self._load_events()
        self._load_elections()
        self._load_clubs()

    def _load_events(self):
        for i in self.events_tree.get_children():
            self.events_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT event_id, event_date, start_time, event_name, "
                    "       location, current_attendees, max_attendees, status "
                    "FROM union_events ORDER BY event_date DESC LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for eid, date, start, name, loc, cur_att, max_att, status in rows:
            att = f"{cur_att or 0}/{max_att or '?'}"
            self.events_tree.insert('', 'end', iid=str(eid), values=(
                (date or '')[:10], (start or '')[:5],
                name or '', loc or '', att, status or ''
            ))
        self.status_var.set(f"{len(rows)} event(s) loaded.")

    def _load_elections(self):
        for i in self.elect_tree.get_children():
            self.elect_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT election_id, position, department, "
                    "       voting_start, voting_end, status "
                    "FROM union_elections ORDER BY voting_start DESC LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for eid, pos, dept, vs, ve, status in rows:
            self.elect_tree.insert('', 'end', iid=str(eid), values=(
                pos or '', dept or '',
                (vs or '')[:16], (ve or '')[:16], status or ''
            ))

    def _load_clubs(self):
        for i in self.clubs_tree.get_children():
            self.clubs_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT club_id, club_name, category, member_count, "
                    "       president_id, status "
                    "FROM student_clubs ORDER BY club_name LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for cid, name, cat, members, pres, status in rows:
            self.clubs_tree.insert('', 'end', iid=str(cid), values=(
                name or '', cat or '', members or 0,
                pres or '', status or ''
            ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_event(self):
        UnionEventDialog(self.window, organizer_id=self.user_id,
                         on_save=self._load_events)

    def _cancel_event(self):
        sel = self.events_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an event to cancel.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Cancel Event",
                                   "Mark this event as cancelled?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE union_events SET status = 'cancelled' "
                    "WHERE event_id = ?", (int(sel[0]),)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self._load_events()

    def _set_election_status(self, new_status):
        sel = self.elect_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an election first.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE union_elections SET status = ? "
                    "WHERE election_id = ?",
                    (new_status, int(sel[0]))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self._load_elections()
        self.status_var.set(f"Election → {new_status}.")


class UnionEventDialog:
    def __init__(self, parent, organizer_id, on_save):
        self.organizer_id = organizer_id
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Union Event")
        self.dialog.geometry("440x420")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        self.name_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.now().date().isoformat())
        self.start_var = tk.StringVar(value='18:00')
        self.end_var = tk.StringVar(value='20:00')
        self.location_var = tk.StringVar()
        self.category_var = tk.StringVar(value='Social')
        self.max_var = tk.StringVar(value='100')

        for i, (label, var) in enumerate([
            ("Name:", self.name_var), ("Date (YYYY-MM-DD):", self.date_var),
            ("Start (HH:MM):", self.start_var), ("End (HH:MM):", self.end_var),
            ("Location:", self.location_var),
            ("Category:", self.category_var), ("Max attendees:", self.max_var),
        ]):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', pady=4)
            ttk.Entry(frame, textvariable=var, width=30).grid(
                row=i, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=7, column=0,
                                                    sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=30, height=4, wrap='word')
        self.desc_text.grid(row=7, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=8, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        name = self.name_var.get().strip()
        date = self.date_var.get().strip()
        if not (name and date):
            messagebox.showerror("Missing", "Name and date are required.",
                                 parent=self.dialog)
            return
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 f"'{date}' is not YYYY-MM-DD.",
                                 parent=self.dialog)
            return
        try:
            max_att = int(self.max_var.get() or 0)
        except ValueError:
            max_att = 0

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO union_events "
                    "(event_name, description, organizer_id, event_date, "
                    " start_time, end_time, location, category, "
                    " max_attendees, current_attendees, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'scheduled', ?)",
                    (name, self.desc_text.get('1.0', 'end').strip(),
                     self.organizer_id, date,
                     self.start_var.get().strip(),
                     self.end_var.get().strip(),
                     self.location_var.get().strip(),
                     self.category_var.get().strip(),
                     max_att, datetime.now().isoformat(timespec='seconds'))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed", str(e), parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_student_union_staff_portal(parent, auth):
    return StudentUnionStaffPortal(parent, auth)
