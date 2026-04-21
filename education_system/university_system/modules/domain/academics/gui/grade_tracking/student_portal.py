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

        module_rows = []
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.module_code, m.module_name, m.credits,
                           mg.final_score, mg.final_grade, sm.status
                    FROM student_modules sm
                    JOIN modules m ON m.module_code = sm.module_code
                    LEFT JOIN module_grades mg ON mg.student_id = sm.student_id
                                              AND mg.module_code = sm.module_code
                    WHERE sm.student_id = ?
                    ORDER BY m.module_code
                    """,
                    (student_id,)
                )
                module_rows = cur.fetchall()

                # For modules without a final grade in module_grades, compute
                # a running weighted score from graded assessments.
                computed = {}
                cur.execute(
                    """
                    SELECT a.module_code,
                           SUM(g.score / a.max_points * a.weight) AS weighted,
                           SUM(a.weight) AS total_weight
                    FROM grades g
                    JOIN assessments a ON a.assessment_id = g.assessment_id
                    WHERE g.student_id = ?
                    GROUP BY a.module_code
                    """,
                    (student_id,)
                )
                for code, weighted, total_weight in cur.fetchall():
                    if total_weight:
                        computed[code] = (weighted / total_weight) * 100.0
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load your grades: {e}",
                                 parent=self.window)
            return

        total_credits = 0
        weighted_gpa = 0.0
        gpa_credits = 0

        for code, name, credits, final_score, final_grade, status in module_rows:
            credits = credits or 0
            total_credits += credits

            letter = final_grade
            score_display = '—'
            pct_source = None
            if final_score is not None:
                pct_source = float(final_score)
            elif code in computed:
                pct_source = computed[code]

            if pct_source is not None:
                score_display = f"{pct_source:.1f}"
                if not letter:
                    letter = _percentage_to_letter(pct_source)

            if letter and letter in _GPA_MAP and credits:
                weighted_gpa += _GPA_MAP[letter] * credits
                gpa_credits += credits

            self.modules_tree.insert('', 'end', iid=code, values=(
                code, name, credits, score_display,
                letter or '—', status or 'Enrolled'
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
                    SELECT a.assessment_name, a.assessment_type, a.max_points,
                           g.score, g.letter_grade, g.submission_date
                    FROM assessments a
                    LEFT JOIN grades g ON g.assessment_id = a.assessment_id
                                      AND g.student_id = ?
                    WHERE a.module_code = ?
                    ORDER BY a.assessment_id
                    """,
                    (self.student['student_id'], module_code)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assessments: {e}",
                                 parent=self.window)
            return

        for name, atype, max_pts, score, letter, date in rows:
            if score is not None:
                pct = (score / max_pts * 100.0) if max_pts else 0
                self.assess_tree.insert('', 'end', values=(
                    name, atype or '',
                    f"{score:g}", f"{max_pts:g}",
                    f"{pct:.1f}%",
                    letter or _percentage_to_letter(pct),
                    date or ''
                ))
            else:
                self.assess_tree.insert('', 'end', values=(
                    name, atype or '', '—', f"{max_pts:g}",
                    '—', 'Pending', ''
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
