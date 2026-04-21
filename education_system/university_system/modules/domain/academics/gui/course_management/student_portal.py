"""Course Management — Student portal.

Read-only view of the student's enrolled modules plus a browsable
catalogue of every other active module in the system. No enrolment /
drop actions — those belong to the registration workflow (or an
admin), not to a read-only course viewer.
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


class CourseManagementStudentPortal:
    """What am I enrolled in, and what else is on offer."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.student_id = self._resolve_student_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Course Management — My Courses")
        self.window.geometry("1040x680")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Loading your courses…")
        self.summary_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(
            value="Select a module on the left to see its details.")

        self._build_ui()
        if self.student_id is None:
            self.status_var.set(
                "No student record matched your account — contact an "
                "administrator to have your student_id linked.")
        else:
            self._load_my_modules()
            self._load_catalogue()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def _resolve_student_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        sid = user.get('student_id')
        if sid:
            return sid
        uid = user.get('id') or user.get('user_id')
        if uid:
            try:
                with _connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT student_id FROM users WHERE id = ?", (uid,))
                    row = cur.fetchone()
                    if row and row[0]:
                        return row[0]
            except Exception:
                pass
        username = user.get('username')
        if username:
            try:
                with _connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT student_id FROM students WHERE student_id = ?",
                        (username,))
                    row = cur.fetchone()
                    if row:
                        return row[0]
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#2980b9', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"My Courses — {display}",
                 font=('Arial', 14, 'bold'), bg='#2980b9', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        summary = ttk.LabelFrame(self.window, text="Enrolment summary",
                                 padding=10)
        summary.pack(fill='x', padx=12, pady=(10, 6))
        ttk.Label(summary, textvariable=self.summary_var,
                  font=('Arial', 11)).pack(anchor='w')

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=12, pady=6)

        # My modules tab ---------------------------------------------------
        my_tab = ttk.Frame(notebook, padding=8)
        notebook.add(my_tab, text="My Modules")

        paned = ttk.PanedWindow(my_tab, orient='horizontal')
        paned.pack(fill='both', expand=True)

        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)
        ttk.Label(left, text="Enrolled modules",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 4))

        cols = ('code', 'name', 'credits', 'status')
        self.my_tree = ttk.Treeview(left, columns=cols, show='headings',
                                     selectmode='browse')
        for key, title, width, anchor in [
            ('code', 'Code', 100, 'center'),
            ('name', 'Module', 220, 'w'),
            ('credits', 'Credits', 70, 'center'),
            ('status', 'Status', 110, 'center'),
        ]:
            self.my_tree.heading(key, text=title)
            self.my_tree.column(key, width=width, anchor=anchor)
        scroll = ttk.Scrollbar(left, orient='vertical',
                               command=self.my_tree.yview)
        self.my_tree.configure(yscrollcommand=scroll.set)
        self.my_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.my_tree.bind('<<TreeviewSelect>>',
                          lambda _e: self._show_detail('my'))

        right = ttk.Frame(paned, padding=6)
        paned.add(right, weight=2)
        ttk.Label(right, text="Module details",
                  font=('Arial', 11, 'bold')).pack(anchor='w')
        ttk.Label(right, textvariable=self.detail_var, wraplength=520,
                  justify='left').pack(anchor='w', pady=(4, 0), fill='both',
                                        expand=True)

        # Catalogue tab ----------------------------------------------------
        cat_tab = ttk.Frame(notebook, padding=8)
        notebook.add(cat_tab, text="Course Catalogue")

        ttk.Label(cat_tab,
                  text="Every active module in the system — read-only.",
                  foreground='#555').pack(anchor='w', pady=(0, 6))

        cat_cols = ('code', 'name', 'credits', 'department', 'enrolled')
        self.cat_tree = ttk.Treeview(cat_tab, columns=cat_cols,
                                      show='headings', selectmode='browse')
        for key, title, width, anchor in [
            ('code', 'Code', 100, 'center'),
            ('name', 'Module', 300, 'w'),
            ('credits', 'Credits', 70, 'center'),
            ('department', 'Department', 160, 'w'),
            ('enrolled', 'Enrolled', 90, 'center'),
        ]:
            self.cat_tree.heading(key, text=title)
            self.cat_tree.column(key, width=width, anchor=anchor)
        cat_scroll = ttk.Scrollbar(cat_tab, orient='vertical',
                                    command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.pack(side='left', fill='both', expand=True)
        cat_scroll.pack(side='right', fill='y')
        self.cat_tree.bind('<<TreeviewSelect>>',
                           lambda _e: self._show_detail('catalogue'))

        # Status bar
        status_bar = ttk.Frame(self.window, relief='sunken')
        status_bar.pack(fill='x', side='bottom')
        ttk.Label(status_bar, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

        self._my_modules_by_code = {}
        self._cat_modules_by_code = {}

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self):
        if self.student_id is None:
            return
        self._load_my_modules()
        self._load_catalogue()

    def _load_my_modules(self):
        for i in self.my_tree.get_children():
            self.my_tree.delete(i)
        self._my_modules_by_code = {}

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits,
                           m.description, m.department, m.instructor,
                           sm.status, sm.enrollment_date,
                           sm.grade, sm.completion_date
                    FROM student_modules sm
                    JOIN modules m ON m.module_code = sm.module_code
                    WHERE sm.student_id = ?
                    ORDER BY m.module_code
                    """,
                    (self.student_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load your modules: {e}",
                                 parent=self.window)
            return

        total_credits = 0
        graded = 0
        for code, name, credits, desc, dept, instr, status, enrolled, grade, completed in rows:
            credits_val = credits or 0
            total_credits += credits_val
            if grade:
                graded += 1
            self.my_tree.insert('', 'end', iid=code, values=(
                code, name, credits_val if credits_val else '—',
                (status or 'enrolled').capitalize(),
            ))
            self._my_modules_by_code[code] = {
                'code': code, 'name': name, 'credits': credits_val,
                'description': desc, 'department': dept, 'instructor': instr,
                'status': status, 'enrolled': enrolled,
                'grade': grade, 'completed': completed,
            }

        self.summary_var.set(
            f"Enrolled in {len(rows)} module(s)   |   "
            f"Total credits: {total_credits}   |   "
            f"Graded: {graded}"
        )
        self.status_var.set(
            "Click a module to see details, or open the Course Catalogue tab."
            if rows else
            "You are not enrolled in any modules yet."
        )

    def _load_catalogue(self):
        for i in self.cat_tree.get_children():
            self.cat_tree.delete(i)
        self._cat_modules_by_code = {}
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits,
                           m.description, m.department, m.instructor,
                           (SELECT COUNT(*) FROM student_modules sm
                            WHERE sm.module_code = m.module_code)
                           AS enrolled_count
                    FROM modules m
                    WHERE COALESCE(m.is_active, 1) = 1
                    ORDER BY m.module_code
                    """
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load catalogue: {e}",
                                 parent=self.window)
            return

        for code, name, credits, desc, dept, instr, enrolled in rows:
            self.cat_tree.insert('', 'end', iid=code, values=(
                code, name, credits or '—',
                dept or '—', enrolled,
            ))
            self._cat_modules_by_code[code] = {
                'code': code, 'name': name, 'credits': credits,
                'description': desc, 'department': dept, 'instructor': instr,
                'enrolled_count': enrolled,
            }

    # ------------------------------------------------------------------
    # Detail rendering
    # ------------------------------------------------------------------

    def _show_detail(self, source):
        tree = self.my_tree if source == 'my' else self.cat_tree
        lookup = (self._my_modules_by_code if source == 'my'
                  else self._cat_modules_by_code)
        sel = tree.selection()
        if not sel:
            return
        data = lookup.get(sel[0])
        if not data:
            return

        lines = [
            f"{data['code']} — {data['name']}",
            "",
            f"Credits: {data.get('credits') or 'not set'}",
            f"Department: {data.get('department') or 'not set'}",
            f"Instructor: {data.get('instructor') or 'not assigned'}",
        ]
        if source == 'my':
            lines.append(
                f"Enrolment status: {(data.get('status') or 'enrolled').capitalize()}"
            )
            if data.get('enrolled'):
                lines.append(f"Enrolled since: {data['enrolled']}")
            if data.get('grade'):
                lines.append(f"Final grade on record: {data['grade']}")
            if data.get('completed'):
                lines.append(f"Completed: {data['completed']}")
        else:
            lines.append(
                f"Total enrolled: {data.get('enrolled_count', 0)} student(s)"
            )

        description = (data.get('description') or '').strip()
        lines += ["", "Description:", description or '(no description on file)']
        self.detail_var.set('\n'.join(lines))


def launch_course_management_student_portal(parent, auth):
    """Module-level entry point."""
    return CourseManagementStudentPortal(parent, auth)
