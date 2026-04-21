"""Course Management — Staff portal.

Read-only staff view of every active module in the system, with search,
department filter, enrolment counts, and a per-module student roster.
No create/edit/delete or instructor reassignment — staff coordinators
who need those actions go through the full ``CourseManagementGUI``.
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


class CourseManagementStaffPortal:
    """Browse every active module with search + roster drill-down."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.window = tk.Toplevel(parent)
        self.window.title("Course Management — Staff Portal")
        self.window.geometry("1200x720")
        self.window.minsize(1000, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._apply_filter())
        self.dept_var = tk.StringVar(value='All')
        self.summary_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Loading modules…")
        self.detail_var = tk.StringVar(
            value="Select a module on the left to see its details and roster.")

        self._all_modules: list = []
        self._modules_by_code: dict = {}
        self._current_module = None

        self._build_ui()
        self._load_modules()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#34495e', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        display = ''
        if self.auth and self.auth.current_user:
            display = (self.auth.current_user.get('display_name')
                       or self.auth.current_user.get('username', ''))
        tk.Label(header, text=f"Course Management — {display}",
                 font=('Arial', 14, 'bold'), bg='#34495e', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Refresh", bg='#2c3e50', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._load_modules).pack(side='right', padx=8, pady=10)
        tk.Button(header, text="Close", bg='#2c3e50', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=10)

        summary = ttk.LabelFrame(self.window, text="Overview", padding=10)
        summary.pack(fill='x', padx=12, pady=(10, 6))
        ttk.Label(summary, textvariable=self.summary_var,
                  font=('Arial', 11)).pack(anchor='w')

        bar = ttk.Frame(self.window, padding=(12, 0, 12, 4))
        bar.pack(fill='x')
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        ttk.Entry(bar, textvariable=self.search_var, width=28
                  ).pack(side='left', padx=(0, 12))
        ttk.Label(bar, text="Department:").pack(side='left', padx=(0, 4))
        self.dept_combo = ttk.Combobox(bar, textvariable=self.dept_var,
                                        state='readonly', width=22,
                                        values=['All'])
        self.dept_combo.pack(side='left')
        self.dept_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._apply_filter())

        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=12, pady=6)

        # Left: module list --------------------------------------------
        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=2)

        cols = ('code', 'name', 'credits', 'department', 'instructor',
                'enrolled')
        self.module_tree = ttk.Treeview(left, columns=cols, show='headings',
                                         selectmode='browse')
        for key, title, width, anchor in [
            ('code', 'Code', 100, 'center'),
            ('name', 'Module', 240, 'w'),
            ('credits', 'Credits', 70, 'center'),
            ('department', 'Department', 140, 'w'),
            ('instructor', 'Instructor', 140, 'w'),
            ('enrolled', 'Enrolled', 80, 'center'),
        ]:
            self.module_tree.heading(key, text=title)
            self.module_tree.column(key, width=width, anchor=anchor)
        mscroll = ttk.Scrollbar(left, orient='vertical',
                                 command=self.module_tree.yview)
        self.module_tree.configure(yscrollcommand=mscroll.set)
        self.module_tree.pack(side='left', fill='both', expand=True)
        mscroll.pack(side='right', fill='y')
        self.module_tree.bind('<<TreeviewSelect>>', self._on_module_selected)

        # Right: detail + roster ---------------------------------------
        right = ttk.Frame(paned, padding=6)
        paned.add(right, weight=2)

        ttk.Label(right, textvariable=self.detail_var,
                  font=('Arial', 11), wraplength=560, justify='left'
                  ).pack(anchor='w', pady=(0, 8))

        roster_frame = ttk.LabelFrame(right, text="Student roster", padding=6)
        roster_frame.pack(fill='both', expand=True)
        r_cols = ('student_id', 'name', 'email', 'course', 'status')
        self.roster_tree = ttk.Treeview(roster_frame, columns=r_cols,
                                         show='headings', selectmode='browse')
        for key, title, width, anchor in [
            ('student_id', 'Student ID', 110, 'center'),
            ('name', 'Name', 180, 'w'),
            ('email', 'Email', 200, 'w'),
            ('course', 'Course', 120, 'w'),
            ('status', 'Status', 110, 'center'),
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
            "Select a module on the left to see its details and roster.")
        self._modules_by_code = {}

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits,
                           m.description, m.department, m.instructor,
                           (SELECT COUNT(*) FROM student_modules sm
                            WHERE sm.module_code = m.module_code)
                              AS enrolled_count,
                           (SELECT COUNT(*) FROM assignments a
                            WHERE a.module_code = m.module_code
                              AND COALESCE(a.is_active, 1) = 1)
                              AS assignment_count
                    FROM modules m
                    WHERE COALESCE(m.is_active, 1) = 1
                    ORDER BY m.module_code
                    """
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load modules: {e}",
                                 parent=self.window)
            return

        self._all_modules = []
        depts = set()
        total_enrolled = 0
        for (code, name, credits, desc, dept, instr, enrolled_count,
             assignment_count) in rows:
            total_enrolled += enrolled_count
            if dept:
                depts.add(dept)
            self._all_modules.append({
                'code': code, 'name': name, 'credits': credits,
                'description': desc, 'department': dept,
                'instructor': instr, 'enrolled_count': enrolled_count,
                'assignment_count': assignment_count,
            })

        self.dept_combo['values'] = ['All'] + sorted(depts)
        if self.dept_var.get() not in self.dept_combo['values']:
            self.dept_var.set('All')

        self.summary_var.set(
            f"Active modules: {len(rows)}   |   "
            f"Departments: {len(depts)}   |   "
            f"Total enrolments (sum across modules): {total_enrolled}"
        )
        self._apply_filter()

    def _apply_filter(self):
        search = self.search_var.get().strip().lower()
        dept = self.dept_var.get()

        for i in self.module_tree.get_children():
            self.module_tree.delete(i)
        self._modules_by_code = {}

        matched = 0
        for m in self._all_modules:
            if dept != 'All' and (m.get('department') or '') != dept:
                continue
            if search:
                haystack = f"{m['code']} {m['name']}".lower()
                if search not in haystack:
                    continue
            self.module_tree.insert('', 'end', iid=m['code'], values=(
                m['code'], m['name'],
                m.get('credits') or '—',
                m.get('department') or '—',
                m.get('instructor') or '—',
                m.get('enrolled_count', 0),
            ))
            self._modules_by_code[m['code']] = m
            matched += 1
        self.status_var.set(
            f"Showing {matched} module(s). "
            "Click a module to see its details and roster."
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
            f"Instructor: {data.get('instructor') or 'not assigned'}",
            f"Enrolled: {data.get('enrolled_count', 0)} student(s)",
            f"Active assignments: {data.get('assignment_count', 0)}",
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
                           st.course, sm.status
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

        for student_id, name, email, course, status in rows:
            self.roster_tree.insert('', 'end', values=(
                student_id, name, email or '—', course or '—',
                (status or 'enrolled').capitalize(),
            ))


def launch_course_management_staff_portal(parent, auth):
    """Module-level entry point."""
    return CourseManagementStaffPortal(parent, auth)
