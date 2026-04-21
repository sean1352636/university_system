"""Course Management — Student portal.

Primary view: the student's degree course (e.g. Computer Science,
Data Science) resolved from ``students.course`` joined against the
``courses`` table. Below that, two tabs — the modules the student is
enrolled in, and a catalogue of every degree course the university
offers. No enrolment / drop actions; those belong to the registration
workflow, not to a read-only course viewer.
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
        self.course_title_var = tk.StringVar(value="")
        self.course_desc_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(
            value="Select a module on the left to see its details.")

        self._build_ui()
        if self.student_id is None:
            self.status_var.set(
                "No student record matched your account — contact an "
                "administrator to have your student_id linked.")
        else:
            self._load_my_course()
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

        degree = ttk.LabelFrame(self.window, text="My Degree Course",
                                 padding=12)
        degree.pack(fill='x', padx=12, pady=(10, 6))
        ttk.Label(degree, textvariable=self.course_title_var,
                  font=('Arial', 14, 'bold'),
                  foreground='#2c3e50').pack(anchor='w')
        ttk.Label(degree, textvariable=self.course_desc_var,
                  wraplength=960, justify='left',
                  foreground='#444').pack(anchor='w', pady=(4, 6))
        ttk.Label(degree, textvariable=self.summary_var,
                  font=('Arial', 10)).pack(anchor='w')

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

        # Course catalogue tab --------------------------------------------
        cat_tab = ttk.Frame(notebook, padding=8)
        notebook.add(cat_tab, text="Course Catalogue")

        ttk.Label(cat_tab,
                  text="Every degree course the university offers.",
                  foreground='#555').pack(anchor='w', pady=(0, 6))

        body = ttk.Frame(cat_tab)
        body.pack(fill='both', expand=True)

        cat_cols = ('code', 'name', 'department', 'credits', 'enrolled')
        self.cat_tree = ttk.Treeview(body, columns=cat_cols,
                                      show='headings', selectmode='browse',
                                      height=6)
        for key, title, width, anchor in [
            ('code', 'Code', 80, 'center'),
            ('name', 'Course', 240, 'w'),
            ('department', 'Department', 160, 'w'),
            ('credits', 'Credits', 80, 'center'),
            ('enrolled', 'Students', 90, 'center'),
        ]:
            self.cat_tree.heading(key, text=title)
            self.cat_tree.column(key, width=width, anchor=anchor)
        cat_scroll = ttk.Scrollbar(body, orient='vertical',
                                    command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.pack(side='left', fill='x', expand=True)
        cat_scroll.pack(side='right', fill='y')
        self.cat_tree.bind('<<TreeviewSelect>>',
                           lambda _e: self._show_course_detail())

        self.course_detail_var = tk.StringVar(
            value="Select a course above to see its description.")
        ttk.Label(cat_tab, textvariable=self.course_detail_var,
                  wraplength=980, justify='left',
                  foreground='#333').pack(anchor='w', pady=(10, 0),
                                           fill='both', expand=True)

        # Status bar
        status_bar = ttk.Frame(self.window, relief='sunken')
        status_bar.pack(fill='x', side='bottom')
        ttk.Label(status_bar, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

        self._my_modules_by_code = {}
        self._courses_by_code = {}
        self._my_course = None

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self):
        if self.student_id is None:
            return
        self._load_my_course()
        self._load_my_modules()
        self._load_catalogue()

    def _load_my_course(self):
        """Resolve the student's degree course and render the header card."""
        self._my_course = None
        self.course_title_var.set("")
        self.course_desc_var.set("")

        student_course = None
        first_name = last_name = ''
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT course, first_name, last_name "
                    "FROM students WHERE student_id = ?",
                    (self.student_id,)
                )
                row = cur.fetchone()
                if row:
                    student_course, first_name, last_name = row
                if student_course:
                    # students.course can hold the code ('CS') OR the full
                    # name ('Computer Science') — match either.
                    cur.execute(
                        """
                        SELECT id, COALESCE(course_code, code),
                               COALESCE(course_name, name),
                               description, credits, department
                        FROM courses
                        WHERE COALESCE(course_code, code) = ?
                           OR COALESCE(course_name, name) = ?
                        LIMIT 1
                        """,
                        (student_course, student_course)
                    )
                    self._my_course = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load your degree course: {e}",
                                 parent=self.window)
            return

        if self._my_course:
            _id, code, name, desc, credits, dept = self._my_course
            self.course_title_var.set(f"{code} — {name}")
            bits = []
            if dept:
                bits.append(f"Department: {dept}")
            if credits:
                bits.append(f"Standard credits: {credits}")
            desc_line = (desc or '').strip() or 'No description on file.'
            if bits:
                desc_line = ' · '.join(bits) + "\n\n" + desc_line
            self.course_desc_var.set(desc_line)
        elif student_course:
            self.course_title_var.set(f"{student_course}")
            self.course_desc_var.set(
                "(This course is on your record but doesn't match any entry "
                "in the courses catalogue — an administrator can fix this "
                "mapping.)"
            )
        else:
            self.course_title_var.set("Degree course not set")
            self.course_desc_var.set(
                "Your student record doesn't have a degree course assigned. "
                "Contact an administrator to be placed on a programme."
            )

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
        self._courses_by_code = {}
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COALESCE(course_code, code) AS code,
                           COALESCE(course_name, name) AS name,
                           department, credits, description,
                           (SELECT COUNT(*) FROM students st
                            WHERE st.course = COALESCE(c.course_code, c.code)
                               OR st.course = COALESCE(c.course_name, c.name))
                           AS enrolled_count
                    FROM courses c
                    WHERE COALESCE(status, 'active') != 'inactive'
                    ORDER BY code
                    """
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load course catalogue: {e}",
                                 parent=self.window)
            return

        for code, name, dept, credits, desc, enrolled in rows:
            self.cat_tree.insert('', 'end', iid=code or name, values=(
                code or '—', name, dept or '—', credits or '—', enrolled,
            ))
            self._courses_by_code[code or name] = {
                'code': code, 'name': name, 'department': dept,
                'credits': credits, 'description': desc,
                'enrolled_count': enrolled,
            }
        # Highlight the student's own course if it's in the catalogue.
        if self._my_course:
            my_code = self._my_course[1]
            if self.cat_tree.exists(my_code):
                self.cat_tree.selection_set(my_code)
                self.cat_tree.see(my_code)
                self._show_course_detail()

    def _show_course_detail(self):
        sel = self.cat_tree.selection()
        if not sel:
            return
        data = self._courses_by_code.get(sel[0])
        if not data:
            return
        lines = [
            f"{data.get('code') or ''} — {data['name']}",
            "",
            f"Department: {data.get('department') or 'not set'}",
            f"Credits: {data.get('credits') or 'not set'}",
            f"Students on this course: {data.get('enrolled_count', 0)}",
        ]
        desc = (data.get('description') or '').strip()
        if desc:
            lines += ["", desc]
        self.course_detail_var.set('\n'.join(lines))

    # ------------------------------------------------------------------
    # Detail rendering
    # ------------------------------------------------------------------

    def _show_detail(self, _source='my'):
        """Populate the right-hand detail pane for the selected module."""
        sel = self.my_tree.selection()
        if not sel:
            return
        data = self._my_modules_by_code.get(sel[0])
        if not data:
            return

        lines = [
            f"{data['code']} — {data['name']}",
            "",
            f"Credits: {data.get('credits') or 'not set'}",
            f"Department: {data.get('department') or 'not set'}",
            f"Instructor: {data.get('instructor') or 'not assigned'}",
            f"Enrolment status: {(data.get('status') or 'enrolled').capitalize()}",
        ]
        if data.get('enrolled'):
            lines.append(f"Enrolled since: {data['enrolled']}")
        if data.get('grade'):
            lines.append(f"Final grade on record: {data['grade']}")
        if data.get('completed'):
            lines.append(f"Completed: {data['completed']}")

        description = (data.get('description') or '').strip()
        lines += ["", "Description:", description or '(no description on file)']
        self.detail_var.set('\n'.join(lines))


def launch_course_management_student_portal(parent, auth):
    """Module-level entry point."""
    return CourseManagementStudentPortal(parent, auth)
