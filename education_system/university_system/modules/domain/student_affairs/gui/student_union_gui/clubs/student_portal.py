"""Clubs & Societies — Student portal.

Browse active clubs, join a club (creates a row in `club_memberships`),
see which clubs I belong to, and leave a club.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)

# Reuse the staff portal's helper so the table is guaranteed to exist.
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.staff_portal import (
    ensure_club_memberships_table,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class ClubsStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        ensure_club_memberships_table()

        user = (auth.current_user if auth else None) or {}
        self.student_id = str(user.get('student_id') or user.get('username')
                              or user.get('user_id') or '')

        self.window = tk.Toplevel(parent)
        self.window.title("Clubs & Societies — My Portal")
        self.window.geometry("1020x680")
        self.window.minsize(880, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.search_var = tk.StringVar()
        self.cat_var = tk.StringVar(value='All')
        self.info_var = tk.StringVar(value="")
        self._my_club_ids = set()

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#7d3c98', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Clubs & Societies — {display}",
                 font=('Arial', 14, 'bold'), bg='#7d3c98', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#5b2c6f', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#5b2c6f', fg='white',
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
        nb.add(frame, text="Browse Clubs")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.search_var, width=26)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_clubs())
        ttk.Label(bar, text="Category:").pack(side='left', padx=(10, 4))
        self.cat_combo = ttk.Combobox(bar, textvariable=self.cat_var,
                                      state='readonly', width=18)
        self.cat_combo.pack(side='left')
        self.cat_combo.bind('<<ComboboxSelected>>',
                            lambda _e: self._load_clubs())
        ttk.Button(bar, text="Search",
                   command=self._load_clubs).pack(side='left', padx=4)
        ttk.Button(bar, text="Join",
                   command=self._join).pack(side='right')

        cols = ('name', 'category', 'members', 'joined')
        self.tree = ttk.Treeview(frame, columns=cols,
                                 show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Club', 320), ('category', 'Category', 160),
            ('members', 'Members', 110), ('joined', 'I belong', 100),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('name', 'category')
                                           else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.tag_configure('mine', background='#d5f5e3')

    def _build_mine_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Clubs")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Clubs I've joined",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Leave Club",
                   command=self._leave).pack(side='right')

        cols = ('name', 'category', 'role', 'joined', 'status')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Club', 280), ('category', 'Category', 150),
            ('role', 'Role', 120), ('joined', 'Joined', 120),
            ('status', 'Status', 120),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width,
                                  anchor='w' if key in ('name', 'category')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_categories()
        self._load_mine()
        self._load_clubs()

    def _load_categories(self):
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT DISTINCT category FROM student_clubs "
                    "WHERE category IS NOT NULL AND category != '' "
                    "ORDER BY category"
                )
                cats = [r[0] for r in cur.fetchall()]
        except Exception:
            cats = []
        self.cat_combo['values'] = ['All'] + cats

    def _load_clubs(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        clauses = ["COALESCE(status, 'active') = 'active'"]
        params = []
        query = self.search_var.get().strip()
        if query:
            clauses.append("(club_name LIKE ? OR description LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like])
        cat = self.cat_var.get()
        if cat and cat != 'All':
            clauses.append("category = ?")
            params.append(cat)

        sql = (
            "SELECT club_id, club_name, category, member_count "
            "FROM student_clubs"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY club_name LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return

        for cid, name, cat_val, members in rows:
            mine = cid in self._my_club_ids
            tag = ('mine',) if mine else ()
            self.tree.insert('', 'end', iid=str(cid), values=(
                name or '', cat_val or '', members or 0,
                'Yes' if mine else ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} active club(s).")

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        self._my_club_ids.clear()
        if not self.student_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT m.id, c.club_id, c.club_name, c.category, "
                    "       m.role, m.join_date, m.status "
                    "FROM club_memberships m "
                    "JOIN student_clubs c ON c.club_id = m.club_id "
                    "WHERE m.student_id = ? "
                    "ORDER BY m.join_date DESC",
                    (self.student_id,)
                )
                for row in cur.fetchall():
                    self._my_club_ids.add(row[1])
                    self.mine_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[2] or '', row[3] or '',
                        row[4] or 'member', (row[5] or '')[:10],
                        row[6] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _join(self):
        if not self.student_id:
            messagebox.showerror("Not Signed In",
                                 "Your account is not linked to a student_id.",
                                 parent=self.window)
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a club to join.",
                                parent=self.window)
            return
        cid = int(sel[0])
        if cid in self._my_club_ids:
            messagebox.showinfo("Already a Member",
                                "You're already a member of this club.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO club_memberships "
                    "(club_id, student_id, join_date, status, role) "
                    "VALUES (?, ?, ?, 'active', 'member')",
                    (cid, self.student_id,
                     datetime.now().date().isoformat())
                )
                cur.execute(
                    "UPDATE student_clubs "
                    "SET member_count = COALESCE(member_count, 0) + 1 "
                    "WHERE club_id = ?", (cid,)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showinfo("Already a Member",
                                "You already have a membership row.",
                                parent=self.window)
            return
        except Exception as e:
            messagebox.showerror("Join Failed", str(e), parent=self.window)
            return
        messagebox.showinfo("Joined", "Welcome to the club.",
                            parent=self.window)
        self._refresh_all()

    def _leave(self):
        sel = self.mine_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a club to leave.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Leave Club",
                                   "Leave this club?",
                                   parent=self.window):
            return
        mid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT club_id FROM club_memberships WHERE id = ?",
                    (mid,)
                )
                row = cur.fetchone()
                if not row:
                    return
                cid = row[0]
                cur.execute(
                    "DELETE FROM club_memberships "
                    "WHERE id = ? AND student_id = ?",
                    (mid, self.student_id)
                )
                cur.execute(
                    "UPDATE student_clubs SET member_count = "
                    "    CASE WHEN COALESCE(member_count, 0) > 0 "
                    "         THEN member_count - 1 ELSE 0 END "
                    "WHERE club_id = ?", (cid,)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Leave Failed", str(e),
                                 parent=self.window)
            return
        self._refresh_all()


def launch_clubs_student_portal(parent, auth):
    return ClubsStudentPortal(parent, auth)
