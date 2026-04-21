"""Course Management — Instructor portal.

Read-only view of the modules this instructor teaches plus the student
roster and enrolment counts for each. "Modules I teach" is resolved via
the union of:

- ``modules.instructor LIKE '%<username>%'`` — the classic linkage, if
  the column has been populated at all.
- ``DISTINCT assignments.module_code WHERE assignments.created_by = me``
  — because in live data the instructor column is usually NULL but the
  same person is the one posting assignments to the module.

No create / delete / reassignment here — those remain admin-only.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.university_system.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    sqlite3,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CourseManagementInstructorPortal:
    """Modules I teach, with per-module student rosters."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_id = self._resolve_user_id()
        user = (self.auth.current_user if self.auth else None) or {}
        self.username = user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Course Management — My Teaching")
        self.window.geometry("1180x720")
        self.window.minsize(980, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.summary_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Loading your modules…")

        self._modules_by_code: dict = {}
        self._current_module = None

        self._build_ui()
        if self.user_id is None:
            self.status_var.set(
                "Your user account is not linked to the assignments database.")
        else:
            self._load_modules()

    def _resolve_user_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        uid = user.get('id') or user.get('user_id')
        if uid:
            return uid
        username = user.get('username')
        if not username:
            return None
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = ?",
                            (username,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#6f42c1', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"My Teaching — {display}",
                 font=('Arial', 14, 'bold'), bg='#6f42c1', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#5a3697', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._load_modules).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#5a3697', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        summary = ttk.LabelFrame(self.window, text="Teaching summary",
                                 padding=10)
        summary.pack(fill='x', padx=12, pady=(10, 6))
        ttk.Label(summary, textvariable=self.summary_var,
                  font=('Arial', 11)).pack(anchor='w')

        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=12, pady=6)

        # Left: list of my modules ----------------------------------------
        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)
        ttk.Label(left, text="Modules",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 4))
        cols = ('code', 'name', 'enrolled', 'assignments')
        self.module_tree = ttk.Treeview(left, columns=cols, show='headings',
                                         selectmode='browse')
        for key, title, width, anchor in [
            ('code', 'Code', 100, 'center'),
            ('name', 'Module', 220, 'w'),
            ('enrolled', 'Students', 80, 'center'),
            ('assignments', 'Assignments', 100, 'center'),
        ]:
            self.module_tree.heading(key, text=title)
            self.module_tree.column(key, width=width, anchor=anchor)
        mscroll = ttk.Scrollbar(left, orient='vertical',
                                 command=self.module_tree.yview)
        self.module_tree.configure(yscrollcommand=mscroll.set)
        self.module_tree.pack(side='left', fill='both', expand=True)
        mscroll.pack(side='right', fill='y')
        self.module_tree.bind('<<TreeviewSelect>>', self._on_module_selected)

        # Right: module details + roster ----------------------------------
        right = ttk.Frame(paned, padding=6)
        paned.add(right, weight=2)

        self.detail_var = tk.StringVar(
            value="Select a module on the left to see its roster and details.")
        ttk.Label(right, textvariable=self.detail_var,
                  font=('Arial', 11), wraplength=700, justify='left'
                  ).pack(anchor='w', pady=(0, 8))

        roster_frame = ttk.LabelFrame(right, text="Student roster", padding=6)
        roster_frame.pack(fill='both', expand=True)
        r_cols = ('student_id', 'name', 'email', 'status', 'grade')
        self.roster_tree = ttk.Treeview(roster_frame, columns=r_cols,
                                         show='headings', selectmode='browse')
        for key, title, width, anchor in [
            ('student_id', 'Student ID', 110, 'center'),
            ('name', 'Name', 200, 'w'),
            ('email', 'Email', 220, 'w'),
            ('status', 'Status', 110, 'center'),
            ('grade', 'Final Grade', 100, 'center'),
        ]:
            self.roster_tree.heading(key, text=title)
            self.roster_tree.column(key, width=width, anchor=anchor)
        rscroll = ttk.Scrollbar(roster_frame, orient='vertical',
                                 command=self.roster_tree.yview)
        self.roster_tree.configure(yscrollcommand=rscroll.set)
        self.roster_tree.pack(side='left', fill='both', expand=True)
        rscroll.pack(side='right', fill='y')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_modules(self):
        for i in self.module_tree.get_children():
            self.module_tree.delete(i)
        for i in self.roster_tree.get_children():
            self.roster_tree.delete(i)
        self.detail_var.set(
            "Select a module on the left to see its roster and details.")
        self._modules_by_code = {}
        self._current_module = None

        if self.user_id is None:
            return

        try:
            with _connect() as conn:
                cur = conn.cursor()
                # Union: modules flagged as mine (classic) or modules where
                # I've posted assignments (the useful signal in live data).
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits,
                           m.description, m.department, m.instructor,
                           (SELECT COUNT(*) FROM student_modules sm
                            WHERE sm.module_code = m.module_code)
                              AS enrolled_count,
                           (SELECT COUNT(*) FROM assignments a
                            WHERE a.module_code = m.module_code
                              AND COALESCE(a.is_active, 1) = 1
                              AND a.created_by = ?)
                              AS my_assignment_count,
                           (SELECT COUNT(*) FROM assignments a
                            WHERE a.module_code = m.module_code
                              AND COALESCE(a.is_active, 1) = 1)
                              AS total_assignment_count
                    FROM modules m
                    WHERE COALESCE(m.is_active, 1) = 1
                      AND (
                          (m.instructor IS NOT NULL AND m.instructor LIKE ?)
                          OR m.module_code IN (
                              SELECT DISTINCT module_code
                              FROM assignments
                              WHERE created_by = ?
                                AND COALESCE(is_active, 1) = 1
                          )
                      )
                    ORDER BY m.module_code
                    """,
                    (self.user_id, f"%{self.username}%", self.user_id)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load your modules: {e}",
                                 parent=self.window)
            return

        total_students = 0
        total_assignments = 0
        for (code, name, credits, desc, dept, instr, enrolled_count,
             my_assignments, total_assgn) in rows:
            total_students += enrolled_count
            total_assignments += my_assignments
            self.module_tree.insert('', 'end', iid=code, values=(
                code, name, enrolled_count, my_assignments,
            ))
            self._modules_by_code[code] = {
                'code': code, 'name': name, 'credits': credits,
                'description': desc, 'department': dept,
                'instructor': instr, 'enrolled_count': enrolled_count,
                'my_assignment_count': my_assignments,
                'total_assignment_count': total_assgn,
            }

        self.summary_var.set(
            f"Teaching {len(rows)} module(s)   |   "
            f"Total students (across modules): {total_students}   |   "
            f"My active assignments: {total_assignments}"
        )
        self.status_var.set(
            "Click a module to see its student roster."
            if rows else
            "You don't have any modules on record. If you create an "
            "assignment in the Assignments portal, its module will appear here."
        )

    def _on_module_selected(self, _event=None):
        sel = self.module_tree.selection()
        if not sel:
            return
        code = sel[0]
        data = self._modules_by_code.get(code)
        if not data:
            return
        self._current_module = data

        lines = [
            f"{data['code']} — {data['name']}",
            "",
            f"Credits: {data.get('credits') or 'not set'}",
            f"Department: {data.get('department') or 'not set'}",
            f"Enrolled: {data.get('enrolled_count', 0)} student(s)",
            f"Assignments: {data.get('my_assignment_count', 0)} created by "
            f"you (of {data.get('total_assignment_count', 0)} in this module)",
        ]
        description = (data.get('description') or '').strip()
        if description:
            lines += ["", "Description:", description]
        self.detail_var.set('\n'.join(lines))

        self._load_roster(code)

    def _load_roster(self, module_code):
        for i in self.roster_tree.get_children():
            self.roster_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT sm.student_id,
                           COALESCE(
                               NULLIF(TRIM(COALESCE(st.first_name, '') || ' '
                                           || COALESCE(st.last_name, '')), ''),
                               sm.student_id
                           ) AS name,
                           COALESCE(u.email, st.email_address) AS email,
                           sm.status, sm.grade
                    FROM student_modules sm
                    LEFT JOIN students st ON st.student_id = sm.student_id
                    LEFT JOIN users u ON u.student_id = sm.student_id
                    WHERE sm.module_code = ?
                    ORDER BY name
                    """,
                    (module_code,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load roster: {e}",
                                 parent=self.window)
            return

        for student_id, name, email, status, grade in rows:
            self.roster_tree.insert('', 'end', values=(
                student_id, name, email or '—',
                (status or 'enrolled').capitalize(),
                grade or '—',
            ))
        self.status_var.set(
            f"Module {module_code}: {len(rows)} student(s) on roster.")


def launch_course_management_instructor_portal(parent, auth):
    """Module-level entry point."""
    return CourseManagementInstructorPortal(parent, auth)
