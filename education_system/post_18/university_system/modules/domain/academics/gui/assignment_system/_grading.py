"""Shared grading machinery used by both the Assignment staff portal
(grade-one-submission flow) and the Grade Tracking staff portal
(batch-grade-a-whole-module flow).

There is one dialog (``GradeSubmissionDialog``), one DB writer
(``save_submission_grade``), and one email pipeline
(``send_grade_release_emails_async`` → ``_send_grade_release_emails``).
The portal decides the surrounding UX (whether to save immediately or
batch), but the grading action itself goes through this module.

The dialog captures a score + feedback and hands them back to the
caller via an ``on_save(score, feedback)`` callback — it never touches
the database itself, so callers that want batch behaviour can just
accumulate the values without hitting the DB yet.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable, Optional

from education_system.post_18.university_system.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    sqlite3,
)

logger = logging.getLogger(__name__)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class GradeSubmissionDialog:
    """Modal: capture a score + feedback for a single submission.

    Parameters
    ----------
    parent:
        Parent window — the dialog is transient to it.
    student_label:
        Human-readable identifier shown in the dialog header
        (e.g. ``"S12345 — Alice Jones"``).
    assignment_label:
        Assignment/assessment title, shown alongside student_label.
        Empty string omits that line.
    file_label:
        Optional filename shown in the header (the assignment staff
        portal uses this; grade tracking doesn't).
    max_marks:
        Maximum score. Used for the out-of-range confirmation and
        displayed in the header.
    current_score / current_feedback:
        Pre-fill values. ``current_score=None`` yields an empty input.
    on_save:
        Callback invoked with ``(score: float, feedback: str)`` when
        the user confirms the dialog. The dialog closes itself after
        invoking the callback — it does NOT save to the database.
    """

    def __init__(
        self,
        parent,
        *,
        student_label: str,
        max_marks: float,
        on_save: Callable[[float, str], None],
        assignment_label: str = '',
        file_label: str = '',
        current_score: Optional[float] = None,
        current_feedback: str = '',
        title: str = 'Grade Submission',
    ):
        self.on_save = on_save
        self.max_marks = float(max_marks) if max_marks else 100.0

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x440")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        if assignment_label:
            ttk.Label(frame, text=f"Assignment: {assignment_label}",
                      font=('Arial', 10, 'bold')
                      ).pack(anchor='w', pady=(0, 2))

        header_bits = [f"Student: {student_label}"]
        if file_label:
            header_bits.append(f"File: {file_label}")
        header_bits.append(f"Max: {self.max_marks:g}")
        ttk.Label(frame, text='   |   '.join(header_bits)
                  ).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Grade:").pack(anchor='w')
        seed = '' if current_score is None else f"{float(current_score):g}"
        self.grade_var = tk.StringVar(value=seed)
        ttk.Entry(frame, textvariable=self.grade_var, width=18
                  ).pack(anchor='w')

        ttk.Label(frame, text="Feedback:").pack(anchor='w', pady=(10, 2))
        self.fb_text = tk.Text(frame, width=54, height=9, wrap='word')
        self.fb_text.pack(fill='both', expand=True)
        if current_feedback:
            self.fb_text.insert('1.0', current_feedback)

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(10, 0))
        ttk.Button(btns, text="Save Grade", command=self._save
                   ).pack(side='right', padx=4)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy
                   ).pack(side='right', padx=4)

    def _save(self):
        raw = self.grade_var.get().strip()
        try:
            score = float(raw)
        except ValueError:
            messagebox.showerror("Invalid Grade",
                                 "Grade must be a number.",
                                 parent=self.dialog)
            return
        if score < 0 or score > self.max_marks:
            if not messagebox.askyesno(
                    "Out of Range",
                    f"Grade {score:g} is outside 0–{self.max_marks:g}. "
                    "Save anyway?", parent=self.dialog):
                return

        feedback = self.fb_text.get('1.0', 'end').strip()
        self.dialog.destroy()
        if self.on_save:
            self.on_save(score, feedback)


def save_submission_grade(
    submission_id: int,
    score: float,
    feedback: str,
    grader_user_id: Optional[int],
) -> bool:
    """UPDATE assignment_submissions with the new grade info.

    Returns True on success, False on failure (and logs the error).
    """
    now = datetime.now().isoformat(timespec='seconds')
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE assignment_submissions
                SET grade = ?, feedback = ?, graded_by = ?, graded_date = ?,
                    status = 'graded'
                WHERE id = ?
                """,
                (score, feedback, grader_user_id, now, submission_id)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.warning("save_submission_grade failed for %s: %s",
                       submission_id, e)
        return False


def send_grade_release_emails_async(
    submission_id: int,
    score: float,
    feedback: str,
    max_marks: float,
    grader_user_id: Optional[int],
) -> None:
    """Fire the grade-release email pipeline in a daemon thread."""
    threading.Thread(
        target=_send_grade_release_emails,
        args=(submission_id, score, feedback, max_marks, grader_user_id),
        daemon=True,
    ).start()


def _send_grade_release_emails(submission_id, grade, feedback, max_marks,
                               grader_user_id):
    """Email the student with their grade and the grader with a confirmation.

    Runs off the UI thread. Failures are logged; the grade is already
    committed to the DB before this is called.
    """
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.student_id,
                       COALESCE(us.email, st.email_address) AS student_email,
                       st.first_name,
                       a.title, a.module_code,
                       u.email, u.username
                FROM assignment_submissions s
                JOIN assignments a ON a.id = s.assignment_id
                LEFT JOIN students st ON st.student_id = s.student_id
                LEFT JOIN users us ON us.student_id = s.student_id
                LEFT JOIN users u ON u.id = ?
                WHERE s.id = ?
                """,
                (grader_user_id, submission_id)
            )
            row = cur.fetchone()
    except Exception as e:
        logger.warning("Grade email: lookup failed: %s", e)
        return
    if not row:
        logger.warning("Grade email: submission %s not found", submission_id)
        return

    (student_id, student_email, first_name, assignment_title, module_code,
     staff_email, staff_username) = row
    student_display = first_name or student_id or 'Student'

    try:
        from education_system.post_18.university_system.infrastructure.email import queue_template_email
    except Exception as e:
        logger.warning("Grade email: email service unavailable: %s", e)
        return

    grade_display = f"{grade:g} / {max_marks:g}"

    if student_email:
        try:
            queue_template_email(
                template_name='academics/assignment_grade_released',
                recipient=student_email,
                template_vars={
                    'student_name': student_display,
                    'assignment_title': assignment_title,
                    'module_code': module_code or 'n/a',
                    'grade': grade_display,
                    'feedback': feedback or '(no written feedback)',
                },
            )
        except Exception as e:
            logger.warning("Grade email to student failed: %s", e)
    else:
        logger.info("Grade email: no email on file for student %s", student_id)

    if staff_email:
        try:
            queue_template_email(
                template_name='academics/grade_release_confirmation_staff',
                recipient=staff_email,
                template_vars={
                    'staff_name': staff_username or 'there',
                    'student_id': student_id or '',
                    'student_name': student_display,
                    'student_email': student_email or '(not on file)',
                    'assignment_title': assignment_title,
                    'module_code': module_code or 'n/a',
                    'grade_display': grade_display,
                },
            )
        except Exception as e:
            logger.warning("Grade confirmation to staff failed: %s", e)
