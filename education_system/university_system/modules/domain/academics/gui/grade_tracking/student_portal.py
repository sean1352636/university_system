"""Grade Tracking — Student portal.

A read-only, student-facing grade summary. Identifies the current student
from the auth session, then shows per-module grades, overall GPA, and
an assessment-level breakdown for any module the student picks.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection


_GPA_MAP = {
    'A+': 4.3, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D+': 1.3, 'D': 1.0, 'D-': 0.7,
    'F': 0.0,
}


_LETTER_CUTOFFS = [
    (93, 'A+'), (90, 'A'), (87, 'A-'),
    (83, 'B+'), (80, 'B'), (77, 'B-'),
    (73, 'C+'), (70, 'C'), (67, 'C-'),
    (63, 'D+'), (60, 'D'), (57, 'D-'),
]


def _percentage_to_letter(pct):
    for cutoff, letter in _LETTER_CUTOFFS:
        if pct >= cutoff:
            return letter
    return 'F'


class GradeTrackingStudentPortal:
    """Read-only grade viewer for the currently logged-in student."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.window = tk.Toplevel(parent)
        self.window.title("Grade Tracking — My Grades")
        self.window.geometry("1000x680")
        self.window.minsize(820, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.student = self._resolve_student()
        self._build_ui()

        if self.student is None:
            self._show_not_found()
        else:
            self._load_summary()

    # ------------------------------------------------------------------
    # Student identity
    # ------------------------------------------------------------------

    def _resolve_student(self):
        """Find this user's row in the students table.

        Tries explicit student_id, then username, then email.
        """
        user = (self.auth.current_user if self.auth else None) or {}
        candidates = [
            ('student_id', user.get('student_id')),
            ('student_id', user.get('username')),
            ('email_address', user.get('email')),
        ]
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                for column, value in candidates:
                    if not value:
                        continue
                    cur.execute(
                        f"SELECT student_id, first_name, middle_name, last_name, "
                        f"course, email_address FROM students WHERE {column} = ?",
                        (value,)
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            'student_id': row[0],
                            'first_name': row[1] or '',
                            'middle_name': row[2] or '',
                            'last_name': row[3] or '',
                            'course': row[4] or '',
                            'email': row[5] or '',
                        }
        except Exception:
            return None
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
        tk.Label(header, text=f"My Grades — {display}",
                 font=('Arial', 14, 'bold'), bg='#2980b9', fg='white'
                 ).pack(side='left', padx=18, pady=14)

        tk.Button(header, text="Refresh", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        # Summary card
        self.summary_frame = ttk.LabelFrame(self.window, text="Overall Summary",
                                            padding=12)
        self.summary_frame.pack(fill='x', padx=12, pady=(10, 6))
        self.summary_var = tk.StringVar(value="Loading…")
        ttk.Label(self.summary_frame, textvariable=self.summary_var,
                  font=('Arial', 11)).pack(anchor='w')

        # Modules table (top half)
        modules_frame = ttk.LabelFrame(self.window, text="My Modules",
                                       padding=8)
        modules_frame.pack(fill='both', expand=True, padx=12, pady=6)

        m_cols = ('module_code', 'module_name', 'credits', 'score',
                  'letter', 'status')
        self.modules_tree = ttk.Treeview(modules_frame, columns=m_cols,
                                         show='headings', selectmode='browse',
                                         height=7)
        headings = [
            ('module_code', 'Code', 100),
            ('module_name', 'Module', 280),
            ('credits', 'Credits', 80),
            ('score', 'Score %', 100),
            ('letter', 'Grade', 80),
            ('status', 'Status', 120),
        ]
        for key, title, width in headings:
            self.modules_tree.heading(key, text=title)
            self.modules_tree.column(key, width=width,
                                     anchor='w' if key == 'module_name' else 'center')

        m_scroll = ttk.Scrollbar(modules_frame, orient='vertical',
                                 command=self.modules_tree.yview)
        self.modules_tree.configure(yscrollcommand=m_scroll.set)
        self.modules_tree.pack(side='left', fill='both', expand=True)
        m_scroll.pack(side='right', fill='y')
        self.modules_tree.bind('<<TreeviewSelect>>', self._on_module_select)

        # Assessments breakdown (bottom half)
        assess_frame = ttk.LabelFrame(self.window,
                                      text="Assessments (select a module above)",
                                      padding=8)
        assess_frame.pack(fill='both', expand=True, padx=12, pady=(6, 12))
        self.assess_frame = assess_frame

        a_cols = ('name', 'type', 'score', 'max', 'percent', 'letter', 'date')
        self.assess_tree = ttk.Treeview(assess_frame, columns=a_cols,
                                        show='headings', height=7)
        a_headings = [
            ('name', 'Assessment', 240),
            ('type', 'Type', 110),
            ('score', 'Score', 80),
            ('max', 'Max', 80),
            ('percent', '%', 80),
            ('letter', 'Letter', 80),
            ('date', 'Submitted', 120),
        ]
        for key, title, width in a_headings:
            self.assess_tree.heading(key, text=title)
            self.assess_tree.column(key, width=width,
                                    anchor='w' if key in ('name',) else 'center')
        a_scroll = ttk.Scrollbar(assess_frame, orient='vertical',
                                 command=self.assess_tree.yview)
        self.assess_tree.configure(yscrollcommand=a_scroll.set)
        self.assess_tree.pack(side='left', fill='both', expand=True)
        a_scroll.pack(side='right', fill='y')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _show_not_found(self):
        self.summary_var.set(
            "No student record matched your account.\n"
            "Ask an administrator to link your user to a student_id."
        )

    def _load_summary(self):
        student_id = self.student['student_id']
        full_name = ' '.join(x for x in (
            self.student['first_name'],
            self.student['middle_name'],
            self.student['last_name'],
        ) if x)

        for t in (self.modules_tree, self.assess_tree):
            for i in t.get_children():
                t.delete(i)

        try:
            with get_connection() as conn:
                cur = conn.cursor()
                # Per-module summary: for each enrolled module, compute the
                # weighted percentage from the student's graded submissions
                # (assignment_submissions.grade / assignments.max_marks).
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits, sm.status,
                           SUM(CASE WHEN s.grade IS NOT NULL
                                    THEN s.grade END)     AS sum_score,
                           SUM(CASE WHEN s.grade IS NOT NULL
                                    THEN a.max_marks END) AS sum_max,
                           COUNT(DISTINCT a.id)           AS total_assignments,
                           SUM(CASE WHEN s.grade IS NOT NULL
                                    THEN 1 ELSE 0 END)    AS graded_count
                    FROM student_modules sm
                    JOIN modules m ON m.module_code = sm.module_code
                    LEFT JOIN assignments a
                           ON a.module_code = m.module_code
                          AND COALESCE(a.is_active, 1) = 1
                    LEFT JOIN assignment_submissions s
                           ON s.assignment_id = a.id
                          AND s.student_id = sm.student_id
                          AND COALESCE(s.is_final_submission, 1) = 1
                    WHERE sm.student_id = ?
                    GROUP BY m.module_code, m.module_name, m.credits, sm.status
                    ORDER BY m.module_code
                    """,
                    (student_id,)
                )
                module_rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load your grades: {e}",
                                 parent=self.window)
            return

        total_credits = 0
        weighted_gpa = 0.0
        gpa_credits = 0

        for (code, name, credits, status, sum_score, sum_max,
             total_assignments, graded_count) in module_rows:
            credits = credits or 0
            total_credits += credits

            if sum_max and sum_max > 0 and sum_score is not None:
                pct = (float(sum_score) / float(sum_max)) * 100.0
                score_display = f"{pct:.1f}"
                letter = _percentage_to_letter(pct)
            else:
                pct = None
                score_display = '—'
                letter = None

            if letter and letter in _GPA_MAP and credits:
                weighted_gpa += _GPA_MAP[letter] * credits
                gpa_credits += credits

            status_text = status or 'Enrolled'
            if total_assignments:
                status_text = f"{status_text} ({graded_count}/{total_assignments} graded)"

            self.modules_tree.insert('', 'end', iid=code, values=(
                code, name, credits, score_display,
                letter or '—', status_text,
            ))

        gpa = (weighted_gpa / gpa_credits) if gpa_credits else 0.0
        self.summary_var.set(
            f"Student: {student_id} — {full_name}   "
            f"({self.student['course'] or 'No course'})\n"
            f"Enrolled modules: {len(module_rows)}   |   "
            f"Credits: {total_credits}   |   "
            f"GPA (graded, credit-weighted): {gpa:.2f}"
        )

    def _on_module_select(self, _event=None):
        if self.student is None:
            return
        sel = self.modules_tree.selection()
        if not sel:
            return
        module_code = sel[0]
        module_name = self.modules_tree.item(module_code, 'values')[1]
        self.assess_frame.configure(
            text=f"Assessments — {module_code} · {module_name}")

        for i in self.assess_tree.get_children():
            self.assess_tree.delete(i)

        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT a.title, a.assignment_type, a.max_marks,
                           s.grade, s.status, s.submission_date
                    FROM assignments a
                    LEFT JOIN assignment_submissions s
                           ON s.assignment_id = a.id
                          AND s.student_id = ?
                          AND COALESCE(s.is_final_submission, 1) = 1
                    WHERE a.module_code = ?
                      AND COALESCE(a.is_active, 1) = 1
                    ORDER BY a.due_date IS NULL, a.due_date, a.id
                    """,
                    (self.student['student_id'], module_code)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assessments: {e}",
                                 parent=self.window)
            return

        for title, atype, max_pts, score, sub_status, date in rows:
            max_pts = max_pts or 0
            max_display = f"{max_pts:g}" if max_pts else '—'
            if score is not None:
                pct = (score / max_pts * 100.0) if max_pts else 0
                letter = _percentage_to_letter(pct)
                self.assess_tree.insert('', 'end', values=(
                    title, atype or '',
                    f"{score:g}", max_display,
                    f"{pct:.1f}%", letter,
                    (date or '')[:16],
                ))
            else:
                if sub_status:
                    status_label = 'Submitted' if sub_status.lower() == 'submitted' else sub_status.capitalize()
                else:
                    status_label = 'Not submitted'
                self.assess_tree.insert('', 'end', values=(
                    title, atype or '', '—', max_display,
                    '—', status_label, (date or '')[:16],
                ))

    def _refresh(self):
        self.student = self._resolve_student()
        if self.student is None:
            self._show_not_found()
        else:
            self._load_summary()


def launch_grade_tracking_student_portal(parent, auth):
    """Module-level entry point."""
    return GradeTrackingStudentPortal(parent, auth)
