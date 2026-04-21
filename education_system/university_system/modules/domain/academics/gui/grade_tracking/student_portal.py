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
        self.assess_tree.bind('<Double-1>', self._show_assessment_details)
        self.assess_tree.bind('<Return>', self._show_assessment_details)
        self._assess_details = {}

        hint = ttk.Label(
            assess_frame,
            text="Double-click an assessment to see feedback and details.",
            foreground='#666',
        )
        hint.pack(side='bottom', fill='x', pady=(4, 0))

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

        self._assess_details = {}
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT a.id, a.title, a.assignment_type, a.max_marks,
                           a.due_date, a.description,
                           s.id AS submission_id, s.grade, s.status,
                           s.submission_date, s.feedback, s.graded_date,
                           s.file_name, s.file_path, s.late_submission,
                           s.late_days
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

        for row in rows:
            (a_id, title, atype, max_pts, due_date, description,
             submission_id, score, sub_status, date, feedback,
             graded_date, file_name, file_path, late, late_days) = row
            max_pts = max_pts or 0
            max_display = f"{max_pts:g}" if max_pts else '—'
            iid = str(a_id)
            if score is not None:
                pct = (score / max_pts * 100.0) if max_pts else 0
                letter = _percentage_to_letter(pct)
                self.assess_tree.insert('', 'end', iid=iid, values=(
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
                self.assess_tree.insert('', 'end', iid=iid, values=(
                    title, atype or '', '—', max_display,
                    '—', status_label, (date or '')[:16],
                ))
            self._assess_details[iid] = {
                'assignment_id': a_id,
                'title': title,
                'type': atype,
                'max_pts': max_pts,
                'due_date': due_date,
                'description': description,
                'submission_id': submission_id,
                'score': score,
                'status': sub_status,
                'submitted': date,
                'feedback': feedback,
                'graded_date': graded_date,
                'file_name': file_name,
                'file_path': file_path,
                'late': bool(late),
                'late_days': late_days or 0,
            }

    def _show_assessment_details(self, _event=None):
        sel = self.assess_tree.selection()
        if not sel:
            return
        details = self._assess_details.get(sel[0])
        if not details:
            return
        AssessmentDetailsDialog(self.window, details)

    def _refresh(self):
        self.student = self._resolve_student()
        if self.student is None:
            self._show_not_found()
        else:
            self._load_summary()


class AssessmentDetailsDialog:
    """Read-only pop-up showing a student's grade + feedback for one assessment."""

    def __init__(self, parent, details):
        self.details = details
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Assessment — {details.get('title') or 'Details'}")
        self.dialog.geometry("640x560")
        self.dialog.minsize(480, 400)
        try:
            self.dialog.transient(parent)
        except Exception:
            pass

        pad = {'padx': 14, 'pady': 4}
        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        title = details.get('title') or 'Assessment'
        atype = details.get('type') or ''
        ttk.Label(frame, text=title, font=('Arial', 13, 'bold')
                  ).pack(anchor='w')
        subtitle_bits = []
        if atype:
            subtitle_bits.append(atype.capitalize())
        if details.get('due_date'):
            subtitle_bits.append(f"Due {str(details['due_date'])[:10]}")
        if subtitle_bits:
            ttk.Label(frame, text=' · '.join(subtitle_bits),
                      foreground='#555').pack(anchor='w', pady=(0, 8))

        score = details.get('score')
        max_pts = details.get('max_pts') or 0
        if score is not None and max_pts:
            pct = (score / max_pts * 100.0)
            letter = _percentage_to_letter(pct)
            grade_text = f"{score:g} / {max_pts:g}   —   {pct:.1f}%   ·   {letter}"
            grade_color = '#1e7e34'
        elif details.get('submission_id'):
            grade_text = f"Submitted — not yet graded"
            grade_color = '#7a5d00'
        else:
            grade_text = "Not submitted"
            grade_color = '#856404'

        grade_frame = ttk.LabelFrame(frame, text="Grade", padding=10)
        grade_frame.pack(fill='x', pady=(4, 8))
        ttk.Label(grade_frame, text=grade_text, font=('Arial', 12, 'bold'),
                  foreground=grade_color).pack(anchor='w')

        # Key/value rows
        meta_frame = ttk.Frame(frame)
        meta_frame.pack(fill='x', pady=(0, 6))
        row = 0
        meta_rows = []
        if details.get('submitted'):
            meta_rows.append(("Submitted:", str(details['submitted'])[:19]))
        if details.get('file_name'):
            meta_rows.append(("File:", details['file_name']))
        if details.get('late'):
            meta_rows.append(("Late:", f"yes ({details.get('late_days', 0)} day(s))"))
        if details.get('status'):
            meta_rows.append(("Status:", str(details['status']).capitalize()))
        if details.get('graded_date'):
            meta_rows.append(("Graded:", str(details['graded_date'])[:19]))
        for label_text, value in meta_rows:
            ttk.Label(meta_frame, text=label_text,
                      font=('Arial', 10, 'bold')).grid(
                row=row, column=0, sticky='w', padx=(0, 8), pady=2)
            ttk.Label(meta_frame, text=value).grid(
                row=row, column=1, sticky='w', pady=2)
            row += 1

        # Feedback pane
        fb_frame = ttk.LabelFrame(frame, text="Instructor feedback", padding=8)
        fb_frame.pack(fill='both', expand=True, pady=(6, 0))
        fb_text = tk.Text(fb_frame, wrap='word', height=8,
                          font=('Arial', 10), padx=4, pady=4)
        fb_scroll = ttk.Scrollbar(fb_frame, orient='vertical',
                                   command=fb_text.yview)
        fb_text.configure(yscrollcommand=fb_scroll.set)
        fb_text.pack(side='left', fill='both', expand=True)
        fb_scroll.pack(side='right', fill='y')

        feedback = details.get('feedback')
        if feedback:
            fb_text.insert('1.0', feedback)
        elif score is not None:
            fb_text.insert('1.0', "(your instructor did not leave written "
                                    "feedback for this assessment)")
        else:
            fb_text.insert('1.0', "(feedback will appear here once this "
                                    "assessment is graded)")
        fb_text.configure(state='disabled')

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(10, 0))
        if details.get('file_path'):
            ttk.Button(btns, text="View My Submission",
                       command=self._view_file).pack(side='left')
        ttk.Button(btns, text="Close",
                   command=self.dialog.destroy).pack(side='right')

    def _view_file(self):
        try:
            from education_system.university_system.modules.domain.academics.gui.assignment_system._file_viewer import (
                preview_file,
            )
        except Exception as e:
            messagebox.showerror("Unavailable",
                                 f"Could not open file viewer: {e}",
                                 parent=self.dialog)
            return
        preview_file(self.dialog, self.details.get('file_path') or '',
                     title=f"My submission — {self.details.get('title') or ''}")


def launch_grade_tracking_student_portal(parent, auth):
    """Module-level entry point."""
    return GradeTrackingStudentPortal(parent, auth)
