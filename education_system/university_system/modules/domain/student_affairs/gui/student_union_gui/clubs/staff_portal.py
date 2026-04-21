"""Clubs & Societies — Staff/Instructor portal.

Lists all student clubs, lets staff create/edit/archive a club, and shows
the current membership roster. Uses the existing `student_clubs` table
and creates `club_memberships` on first open if it doesn't exist yet.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_CLUB_CATEGORIES = [
    'Academic', 'Athletic', 'Cultural', 'Hobby',
    'Service', 'Political', 'Religious', 'Professional', 'Other',
]


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


def ensure_club_memberships_table():
    """Create club_memberships if missing. Idempotent — safe to call on
    every portal open."""
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS club_memberships ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  club_id INTEGER NOT NULL,"
                "  student_id TEXT NOT NULL,"
                "  join_date TEXT DEFAULT (date('now')),"
                "  status TEXT DEFAULT 'active',"
                "  role TEXT,"
                "  UNIQUE(club_id, student_id)"
                ")"
            )
            conn.commit()
    except Exception:
        pass


class ClubsStaffPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        ensure_club_memberships_table()

        self.window = tk.Toplevel(parent)
        self.window.title("Clubs & Societies — Staff Portal")
        self.window.geometry("1050x680")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.info_var = tk.StringVar(value="")
        self._build_ui()
        self._load_clubs()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#6c3483', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="Clubs & Societies — Staff",
                 font=('Arial', 14, 'bold'), bg='#6c3483', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Button(bar, text="+ New Club",
                   command=self._new_club).pack(side='left')
        ttk.Button(bar, text="Edit",
                   command=self._edit_club).pack(side='left', padx=4)
        ttk.Button(bar, text="Archive",
                   command=self._archive_club).pack(side='left', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_clubs).pack(side='right')

        paned = ttk.PanedWindow(self.window, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=(4, 4))

        clubs_frame = ttk.LabelFrame(paned, text="Clubs", padding=4)
        paned.add(clubs_frame, weight=2)
        cols = ('name', 'category', 'members', 'president', 'status')
        self.tree = ttk.Treeview(clubs_frame, columns=cols,
                                 show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Club', 280), ('category', 'Category', 150),
            ('members', 'Members', 100),
            ('president', 'President ID', 150),
            ('status', 'Status', 110),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('name', 'category')
                                           else 'center')
        vsb = ttk.Scrollbar(clubs_frame, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._load_members)

        mem_frame = ttk.LabelFrame(paned, text="Members", padding=4)
        paned.add(mem_frame, weight=1)
        m_cols = ('student_id', 'name', 'role', 'joined', 'status')
        self.mem_tree = ttk.Treeview(mem_frame, columns=m_cols,
                                     show='headings', selectmode='browse')
        for key, title, width in [
            ('student_id', 'Student ID', 120),
            ('name', 'Name', 240),
            ('role', 'Role', 120),
            ('joined', 'Joined', 120),
            ('status', 'Status', 110),
        ]:
            self.mem_tree.heading(key, text=title)
            self.mem_tree.column(key, width=width,
                                 anchor='w' if key == 'name' else 'center')
        m_vsb = ttk.Scrollbar(mem_frame, orient='vertical',
                              command=self.mem_tree.yview)
        self.mem_tree.configure(yscrollcommand=m_vsb.set)
        self.mem_tree.pack(side='left', fill='both', expand=True)
        m_vsb.pack(side='right', fill='y')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _load_clubs(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in self.mem_tree.get_children():
            self.mem_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT c.club_id, c.club_name, c.category, "
                    "       COALESCE((SELECT COUNT(*) FROM club_memberships m "
                    "                 WHERE m.club_id = c.club_id "
                    "                   AND m.status = 'active'), "
                    "                c.member_count, 0), "
                    "       c.president_id, c.status "
                    "FROM student_clubs c "
                    "ORDER BY c.club_name LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for cid, name, cat, members, pres, status in rows:
            self.tree.insert('', 'end', iid=str(cid), values=(
                name or '', cat or '', members or 0,
                pres or '', status or ''
            ))
        self.info_var.set(f"{len(rows)} club(s).")

    def _load_members(self, _event=None):
        for i in self.mem_tree.get_children():
            self.mem_tree.delete(i)
        sel = self.tree.selection()
        if not sel:
            return
        cid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT m.student_id, "
                    "       COALESCE(s.first_name || ' ' || s.last_name, "
                    "                m.student_id), "
                    "       m.role, m.join_date, m.status "
                    "FROM club_memberships m "
                    "LEFT JOIN students s ON s.student_id = m.student_id "
                    "WHERE m.club_id = ? "
                    "ORDER BY m.join_date DESC LIMIT 500",
                    (cid,)
                )
                for row in cur.fetchall():
                    self.mem_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        row[2] or '', (row[3] or '')[:10],
                        row[4] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)

    def _new_club(self):
        ClubEditorDialog(self.window, club=None,
                         on_save=self._load_clubs)

    def _edit_club(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a club to edit.",
                                parent=self.window)
            return
        cid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT club_id, club_name, description, category, "
                    "       president_id, treasurer_id, secretary_id, status "
                    "FROM student_clubs WHERE club_id = ?", (cid,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if row:
            ClubEditorDialog(self.window, club=row,
                             on_save=self._load_clubs)

    def _archive_club(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a club.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Archive",
                                   "Archive this club? (status = archived)",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE student_clubs SET status = 'archived' "
                    "WHERE club_id = ?", (int(sel[0]),)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self._load_clubs()


class ClubEditorDialog:
    def __init__(self, parent, club, on_save):
        self.club = club
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Club" if club else "New Club")
        self.dialog.geometry("460x460")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        self.name_var = tk.StringVar(value=club[1] if club else '')
        self.category_var = tk.StringVar(
            value=(club[3] if club else 'Academic')
        )
        self.pres_var = tk.StringVar(value=(club[4] if club else '') or '')
        self.treas_var = tk.StringVar(value=(club[5] if club else '') or '')
        self.sec_var = tk.StringVar(value=(club[6] if club else '') or '')
        self.status_var = tk.StringVar(
            value=(club[7] if club else 'active')
        )

        for i, (label, var, widget_kwargs) in enumerate([
            ("Name:", self.name_var, {'width': 34}),
            ("Category:", self.category_var, None),
            ("President ID:", self.pres_var, {'width': 34}),
            ("Treasurer ID:", self.treas_var, {'width': 34}),
            ("Secretary ID:", self.sec_var, {'width': 34}),
            ("Status:", self.status_var, None),
        ]):
            ttk.Label(frame, text=label).grid(row=i, column=0,
                                                sticky='w', pady=4)
            if label == 'Category:':
                ttk.Combobox(frame, textvariable=var,
                             values=_CLUB_CATEGORIES, width=32).grid(
                    row=i, column=1, sticky='w', pady=4)
            elif label == 'Status:':
                ttk.Combobox(frame, textvariable=var,
                             values=['active', 'inactive', 'archived'],
                             state='readonly', width=32).grid(
                    row=i, column=1, sticky='w', pady=4)
            else:
                ttk.Entry(frame, textvariable=var, **widget_kwargs).grid(
                    row=i, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=6, column=0,
                                                    sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=32, height=6, wrap='word')
        self.desc_text.grid(row=6, column=1, sticky='w', pady=4)
        if club and club[2]:
            self.desc_text.insert('1.0', club[2])

        btns = ttk.Frame(frame)
        btns.grid(row=7, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Missing", "Club name is required.",
                                 parent=self.dialog)
            return
        desc = self.desc_text.get('1.0', 'end').strip()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                if self.club:
                    cur.execute(
                        "UPDATE student_clubs SET club_name = ?, "
                        "description = ?, category = ?, president_id = ?, "
                        "treasurer_id = ?, secretary_id = ?, status = ? "
                        "WHERE club_id = ?",
                        (name, desc,
                         self.category_var.get().strip(),
                         self.pres_var.get().strip() or None,
                         self.treas_var.get().strip() or None,
                         self.sec_var.get().strip() or None,
                         self.status_var.get().strip() or 'active',
                         self.club[0])
                    )
                else:
                    cur.execute(
                        "INSERT INTO student_clubs "
                        "(club_name, description, category, member_count, "
                        " president_id, treasurer_id, secretary_id, status, "
                        " created_date) "
                        "VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)",
                        (name, desc,
                         self.category_var.get().strip(),
                         self.pres_var.get().strip() or None,
                         self.treas_var.get().strip() or None,
                         self.sec_var.get().strip() or None,
                         self.status_var.get().strip() or 'active',
                         datetime.now().date().isoformat())
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed", str(e), parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_clubs_staff_portal(parent, auth):
    return ClubsStaffPortal(parent, auth)
