"""AI Auto-Grading — Staff portal.

Staff-facing window that surfaces each ungraded final submission for the
assignments the logged-in user created, runs a heuristic auto-grader
(no external API), and lets the grader review / accept / edit / skip
every suggestion. Accept routes through the shared ``_grading`` module
so the DB write and the grade-release emails are identical to grading
via the Assignment portal or Grade Tracking portal.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.post_18.university_system.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    sqlite3,
)
from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system._grading import (
    GradeSubmissionDialog,
    save_submission_grade,
    send_grade_release_emails_async,
)
from education_system.post_18.university_system.modules.domain.academics.services.ai_grading import (
    grade_submission_by_id,
)

logger = logging.getLogger(__name__)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class AutoGradingStaffPortal:
    """AI auto-grading review portal for staff/instructors."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_id = self._resolve_user_id()

        self.window = tk.Toplevel(parent)
        self.window.title("AI Auto-Grading — Staff Portal")
        self.window.geometry("1120x720")
        self.window.minsize(960, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.assignment_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Loading your assignments…")

        self._assignments: list = []   # (id, title, module_code, max_marks)
        self._current_assignment = None

        self._build_ui()
        if self.user_id is None:
            self.status_var.set(
                "Your user account is not linked to the assignments database.")
        else:
            self._load_assignments()

    # ------------------------------------------------------------------
    # User identity
    # ------------------------------------------------------------------

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

        display = ''
        if self.auth and self.auth.current_user:
            display = (self.auth.current_user.get('display_name')
                       or self.auth.current_user.get('username', ''))
        tk.Label(header, text=f"AI Auto-Grading — {display}",
                 font=('Arial', 14, 'bold'), bg='#6f42c1', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Close", bg='#5a3697', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        bar = ttk.Frame(self.window, padding=(12, 8))
        bar.pack(fill='x')
        ttk.Label(bar, text="Assignment:").pack(side='left', padx=(0, 6))
        self.assignment_combo = ttk.Combobox(bar,
                                              textvariable=self.assignment_var,
                                              state='readonly', width=60)
        self.assignment_combo.pack(side='left', padx=(0, 12), fill='x',
                                    expand=True)
        self.assignment_combo.bind('<<ComboboxSelected>>',
                                    self._on_assignment_selected)
        ttk.Button(bar, text="Refresh",
                   command=self._load_assignments).pack(side='left')

        info = ttk.Frame(self.window, padding=(14, 0, 14, 6))
        info.pack(fill='x')
        self.info_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.info_var,
                  foreground='#2c3e50').pack(side='left')

        body = ttk.LabelFrame(self.window, text="Ungraded submissions",
                              padding=8)
        body.pack(fill='both', expand=True, padx=12, pady=6)

        cols = ('submission_id', 'student_id', 'name', 'submitted', 'file')
        self.tree = ttk.Treeview(body, columns=cols, show='headings',
                                  selectmode='browse')
        headings = [
            ('submission_id', '#', 60),
            ('student_id', 'Student ID', 120),
            ('name', 'Name', 220),
            ('submitted', 'Submitted', 150),
            ('file', 'File', 340),
        ]
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('name', 'file') else 'center')
        vsb = ttk.Scrollbar(body, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', self._review_selected)

        actions = ttk.Frame(self.window, padding=(12, 6))
        actions.pack(fill='x')
        ttk.Button(actions, text="Review with AI…",
                   command=self._review_selected).pack(side='left', padx=(0, 6))
        ttk.Button(actions, text="Auto-Grade All (review each)",
                   command=self._review_all).pack(side='left', padx=(0, 6))
        ttk.Label(actions,
                  text="Grades always require your review before release.",
                  foreground='#666').pack(side='left', padx=12)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_assignments(self):
        self._assignments = []
        self.assignment_combo['values'] = []
        self.assignment_var.set('')
        self._current_assignment = None
        self._clear_tree()
        self.info_var.set('')

        if self.user_id is None:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, title, module_code, max_marks
                    FROM assignments
                    WHERE created_by = ?
                      AND COALESCE(is_active, 1) = 1
                    ORDER BY due_date IS NULL, due_date, id
                    """,
                    (self.user_id,)
                )
                self._assignments = [
                    (r[0], r[1], r[2], r[3] or 100.0) for r in cur.fetchall()
                ]
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assignments: {e}",
                                 parent=self.window)
            return

        values = [f"{title} ({module_code}) — max {float(max_marks):g}"
                  for _id, title, module_code, max_marks
                  in self._assignments]
        self.assignment_combo['values'] = values
        if values:
            self.status_var.set(f"{len(values)} assignment(s) you created.")
        else:
            self.status_var.set(
                "You haven't created any assignments yet. "
                "Create one in the Assignment portal first.")

    def _on_assignment_selected(self, _event=None):
        idx = self.assignment_combo.current()
        if idx < 0:
            return
        self._current_assignment = self._assignments[idx]
        self._load_ungraded()

    def _clear_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    def _load_ungraded(self):
        self._clear_tree()
        if self._current_assignment is None:
            return
        aid, title, module_code, max_marks = self._current_assignment

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.id, s.student_id,
                           COALESCE(
                               NULLIF(TRIM(COALESCE(st.first_name,'') || ' '
                                           || COALESCE(st.last_name,'')), ''),
                               s.student_id
                           ) AS name,
                           s.submission_date, s.file_name
                    FROM assignment_submissions s
                    LEFT JOIN students st ON st.student_id = s.student_id
                    WHERE s.assignment_id = ?
                      AND COALESCE(s.is_final_submission, 1) = 1
                      AND s.grade IS NULL
                    ORDER BY s.submission_date ASC
                    """,
                    (aid,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load submissions: {e}",
                                 parent=self.window)
            return

        for sid, student_id, name, submitted, file_name in rows:
            self.tree.insert('', 'end', iid=str(sid), values=(
                sid, student_id, name,
                (submitted or '')[:16],
                file_name or '',
            ))

        if rows:
            self.info_var.set(
                f"{title} ({module_code})  ·  max {float(max_marks):g}  "
                f"·  {len(rows)} ungraded submission(s)")
            self.status_var.set(
                "Double-click a row to run the AI auto-grader.")
        else:
            self.info_var.set(
                f"{title} ({module_code})  ·  max {float(max_marks):g}  "
                f"·  0 ungraded submissions")
            self.status_var.set("Nothing to grade here — all caught up.")

    # ------------------------------------------------------------------
    # Review flow
    # ------------------------------------------------------------------

    def _review_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Pick a submission first.",
                                parent=self.window)
            return
        self._run_grader(int(sel[0]))

    def _review_all(self):
        ids = [int(i) for i in self.tree.get_children()]
        if not ids:
            messagebox.showinfo("Nothing to grade",
                                "No ungraded submissions for this assignment.",
                                parent=self.window)
            return
        if not messagebox.askyesno(
                "Auto-Grade All",
                f"Run the auto-grader on {len(ids)} submission(s)? You'll "
                "review each suggestion one at a time before anything is "
                "committed.",
                parent=self.window):
            return
        self._queue = list(ids)
        self._run_next_in_queue()

    def _run_next_in_queue(self):
        if not getattr(self, '_queue', None):
            return
        next_id = self._queue.pop(0)
        if self.tree.exists(str(next_id)):
            self.tree.selection_set(str(next_id))
            self.tree.see(str(next_id))
        self._run_grader(next_id, chain=True)

    def _run_grader(self, submission_id: int, chain: bool = False):
        self.status_var.set(
            f"Running auto-grader for submission #{submission_id}…")
        self.window.update_idletasks()

        # Scoring includes a plagiarism scan, which does file I/O and
        # can be slow. Run it in a thread; re-enter the UI from the
        # main loop once we have the result.
        def _worker():
            result = grade_submission_by_id(submission_id,
                                             grader_user_id=self.user_id)
            self.window.after(0,
                               lambda: self._handle_result(submission_id,
                                                            result, chain))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_result(self, submission_id, result, chain: bool):
        if result.error:
            self.status_var.set(f"Auto-grader: {result.error}")
            messagebox.showerror(
                "Auto-Grader",
                f"Could not grade submission #{submission_id}:\n\n{result.error}",
                parent=self.window)
            if chain:
                self._run_next_in_queue()
            return

        self.status_var.set(
            f"Submission #{submission_id}: suggested "
            f"{result.total_score:g}/{result.max_marks:g} "
            f"(confidence {result.confidence})")

        # Load student info for the dialog header.
        student_label = str(submission_id)
        file_label = ''
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.student_id, s.file_name,
                           COALESCE(
                               NULLIF(TRIM(COALESCE(st.first_name,'') || ' '
                                           || COALESCE(st.last_name,'')), ''),
                               s.student_id
                           ) AS name
                    FROM assignment_submissions s
                    LEFT JOIN students st ON st.student_id = s.student_id
                    WHERE s.id = ?
                    """,
                    (submission_id,)
                )
                row = cur.fetchone()
            if row:
                student_id, file_name, name = row
                student_label = f"{student_id} — {name}"
                file_label = file_name or ''
        except Exception:
            pass

        assignment_title = self._current_assignment[1] if self._current_assignment else ''
        max_marks = result.max_marks or (
            self._current_assignment[3] if self._current_assignment else 100.0)

        def _on_accept(score, feedback):
            if not save_submission_grade(
                    submission_id, score, feedback, self.user_id):
                messagebox.showerror(
                    "Database Error",
                    "Grade save failed. See application log for details.",
                    parent=self.window)
                return
            send_grade_release_emails_async(
                submission_id, score, feedback, max_marks, self.user_id)
            messagebox.showinfo(
                "Grade Saved",
                f"Graded submission #{submission_id}.\n\nThe student will "
                "be notified by email, and a confirmation will be sent to "
                "your inbox.",
                parent=self.window)
            self._load_ungraded()
            if chain:
                self.window.after(150, self._run_next_in_queue)

        # Also notify the chain to continue if the user just cancels —
        # Tk's Toplevel close doesn't give us a clean cancel callback,
        # so we rely on the accept path. For batch mode we accept that
        # a cancelled dialog ends the run.

        GradeSubmissionDialog(
            self.window,
            student_label=student_label,
            assignment_label=assignment_title,
            file_label=file_label,
            max_marks=max_marks,
            current_score=result.total_score,
            current_feedback=result.feedback_text(),
            title=f"AI-Suggested Grade — submission #{submission_id}",
            on_save=_on_accept,
        )


def launch_auto_grading_staff_portal(parent, auth):
    """Module-level entry point."""
    return AutoGradingStaffPortal(parent, auth)
