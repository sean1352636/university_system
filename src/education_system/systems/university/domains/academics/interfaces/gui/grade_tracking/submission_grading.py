"""Marking assignment submissions, inside Grade Tracking.

These two screens — Grade Submissions and Grade with Rubrics — used to live
in the Assignment GUI and write to ``assignment_submissions`` directly. Grade
Tracking already wrote to that same table from three other places
(``grades/repository.py``, ``grades/ui/add_dialog.py``,
``grades/ui/edit_dialog.py``) and already had a read adapter for it in
``integrations/submissions.py``, so the same rows were being marked by two
GUIs through two different code paths.

That divergence had teeth: the Assignment GUI's copy read its query by column
position against an ``s.*`` it assumed had 11 columns, so it showed the wrong
student, the wrong file and a max-mark of 0 — while Grade Tracking's path was
fine.

Everything here goes through :meth:`SubmissionGradingMixin._record_submission_grade`,
which is the one write, with the FERPA audit entry attached the same way the
existing dialogs do it.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking._dialogs import (
    messagebox,
)
from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    sqlite3,
)

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        AuditAction,
    )
    from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.grades import (
        get_gui_context,
        require_grade_audit,
        IMMUTABLE_AUDIT_AVAILABLE,
    )
except Exception:  # pragma: no cover - audit is optional in some installs
    AuditAction = None
    get_gui_context = None
    require_grade_audit = None
    IMMUTABLE_AUDIT_AVAILABLE = False


UNGRADED_COLUMNS = ("ID", "Student", "Assignment", "Module", "Submitted")


class SubmissionGradingMixin:
    """Grade Submissions and Grade with Rubrics, as Grade Tracking views."""

    # ------------------------------------------------------------------
    # Shared data access
    # ------------------------------------------------------------------
    def _submission_connection(self):
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _grader_id(self):
        auth = getattr(self, "auth", None)
        current = getattr(auth, "current_user", None) if auth else None
        if isinstance(current, dict):
            return current.get("id") or current.get("username")
        return None

    def _load_ungraded(self, tree):
        """Fill *tree* with submissions that have no grade yet."""
        tree.delete(*tree.get_children())
        try:
            with self._submission_connection() as conn:
                rows = conn.execute(
                    """SELECT s.id, s.student_id, s.submission_date, s.submitted_at,
                              a.title AS assignment_title,
                              a.module_code AS module_code,
                              st.first_name, st.last_name
                         FROM assignment_submissions s
                         JOIN assignments a ON a.id = s.assignment_id
                         LEFT JOIN students st ON st.student_id = s.student_id
                        WHERE s.grade IS NULL
                        ORDER BY COALESCE(s.submission_date, s.submitted_at) DESC"""
                ).fetchall()
        except Exception as exc:
            messagebox.showerror("Grade Submissions",
                                 f"Could not load submissions: {exc}")
            return []

        for row in rows:
            name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            tree.insert("", tk.END, values=(
                row["id"], name or row["student_id"],
                row["assignment_title"], row["module_code"] or "—",
                row["submission_date"] or row["submitted_at"] or "—"))
        if not rows:
            tree.insert("", tk.END, values=("", "Nothing awaiting marking", "", "", ""))
        return rows

    def _submission_detail(self, submission_id):
        """One submission, read by column name."""
        with self._submission_connection() as conn:
            return conn.execute(
                """SELECT s.*, a.title AS assignment_title,
                          a.max_marks AS assignment_max_marks,
                          a.module_code AS assignment_module_code,
                          a.rubric_id AS assignment_rubric_id,
                          st.first_name AS student_first_name,
                          st.last_name AS student_last_name
                     FROM assignment_submissions s
                     JOIN assignments a ON a.id = s.assignment_id
                     LEFT JOIN students st ON st.student_id = s.student_id
                    WHERE s.id = ?""", (submission_id,)).fetchone()

    @staticmethod
    def _max_marks(row):
        """(total, was_set) — falls back to 100 so the form stays usable."""
        try:
            total = float(row["assignment_max_marks"] or 0)
        except (TypeError, ValueError):
            total = 0.0
        return (total, True) if total > 0 else (100.0, False)

    # ------------------------------------------------------------------
    # The single write
    # ------------------------------------------------------------------
    def _record_submission_grade(self, submission_id, percentage, feedback):
        """Store a mark against a submission, with the FERPA audit entry.

        The one place a submission grade is written by these screens. Returns
        True when the row was updated.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        grader = self._grader_id()
        conn = self._submission_connection()
        try:
            row = conn.execute(
                "SELECT student_id, assignment_id FROM assignment_submissions "
                " WHERE id = ?", (submission_id,)).fetchone()
            if row is None:
                messagebox.showerror("Grade Submissions",
                                     "That submission no longer exists.")
                return False
            conn.execute(
                """UPDATE assignment_submissions
                      SET grade = ?, feedback = ?, graded_date = ?,
                          graded_by = ?, status = 'graded'
                    WHERE id = ?""",
                (percentage, feedback, now, grader, submission_id))

            # The audit entry is written before the grade is committed, and a
            # failure aborts the whole thing. That is the convention the other
            # grade writers here already follow (``grades/ui/add_dialog.py``
            # raises "Grade audit service unavailable"): for a student record,
            # a mark nobody can account for is worse than a mark not taken.
            if require_grade_audit and AuditAction and get_gui_context:
                user_id, session_id = get_gui_context()
                require_grade_audit(
                    conn=conn,
                    action=AuditAction.RECORD_UPDATE,
                    user_id=user_id,
                    resource_type="grade",
                    resource_id=str(row["student_id"]),
                    session_id=session_id,
                    details={
                        "student_id": row["student_id"],
                        "assignment_id": row["assignment_id"],
                        "submission_id": submission_id,
                        "score": percentage,
                    },
                )
            else:
                raise RuntimeError("Grade audit service unavailable")

            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.exception("could not record grade for submission %s", submission_id)
            messagebox.showerror(
                "Grade Submissions",
                f"The grade was not saved: {exc}\n\n"
                f"Grades are only recorded once the audit entry is written.")
            return False
        finally:
            conn.close()
        return True

    # ------------------------------------------------------------------
    # Screen: Grade Submissions
    # ------------------------------------------------------------------
    def create_grade_submissions_content(self):
        parent = self.layout.content_frame
        for child in parent.winfo_children():
            child.destroy()

        ttk.Label(parent, text="Grade Submissions",
                  font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(parent, text="Submissions still awaiting a mark.",
                  foreground="#7f8c8d").pack(anchor="w", padx=10, pady=(0, 8))

        panes = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.LabelFrame(panes, text="Ungraded", padding=8)
        panes.add(left, weight=1)
        tree = ttk.Treeview(left, columns=UNGRADED_COLUMNS, show="headings", height=16)
        for column, width in (("ID", 60), ("Student", 150), ("Assignment", 180),
                              ("Module", 100), ("Submitted", 140)):
            tree.heading(column, text=column)
            tree.column(column, width=width)
        scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._ungraded_tree = tree

        right = ttk.LabelFrame(panes, text="Marking", padding=10)
        panes.add(right, weight=1)
        self._marking_frame = right

        ttk.Button(left, text="Refresh",
                   command=lambda: self._load_ungraded(tree)).pack(anchor="w", pady=(6, 0))
        tree.bind("<<TreeviewSelect>>", lambda _e: self._on_ungraded_selected())

        self._load_ungraded(tree)
        self._marking_placeholder()

    def _marking_placeholder(self, message="Select a submission to mark it."):
        for child in self._marking_frame.winfo_children():
            child.destroy()
        ttk.Label(self._marking_frame, text=message,
                  foreground="#7f8c8d", wraplength=380,
                  justify=tk.LEFT).pack(anchor="w")

    def _selected_submission_id(self, tree):
        selection = tree.selection()
        if not selection:
            return None
        values = tree.item(selection[0])["values"]
        if not values or not values[0]:
            return None
        return values[0]

    def _on_ungraded_selected(self):
        submission_id = self._selected_submission_id(self._ungraded_tree)
        if submission_id is None:
            return
        row = self._submission_detail(submission_id)
        if row is None:
            self._marking_placeholder("That submission could not be loaded.")
            return

        total, was_set = self._max_marks(row)
        frame = self._marking_frame
        for child in frame.winfo_children():
            child.destroy()

        student = (f"{row['student_first_name'] or ''} "
                   f"{row['student_last_name'] or ''}").strip() or row["student_id"]
        detail = (f"Student: {student}\n"
                  f"Assignment: {row['assignment_title']}\n"
                  f"Module: {row['assignment_module_code'] or '—'}\n"
                  f"File: {row['file_name'] or '—'}\n"
                  f"Submitted: {row['submission_date'] or row['submitted_at'] or '—'}\n"
                  f"Max marks: {total:g}"
                  + ("" if was_set else "  (not set — assuming 100)"))
        ttk.Label(frame, text=detail, justify=tk.LEFT).pack(anchor="w", pady=(0, 10))

        entry_row = ttk.Frame(frame)
        entry_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(entry_row, text=f"Grade (0–{total:g}):").pack(side=tk.LEFT)
        grade_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=grade_var, width=10).pack(side=tk.LEFT, padx=6)
        percent_var = tk.StringVar(value="(0.0%)")
        ttk.Label(entry_row, textvariable=percent_var).pack(side=tk.LEFT)

        def _update_percent(*_a):
            try:
                value = float(grade_var.get()) if grade_var.get() else 0
            except ValueError:
                percent_var.set("(0.0%)")
                return
            percent_var.set(f"({value / total * 100:.1f}%)" if total > 0 else "(n/a)")
        grade_var.trace_add("write", _update_percent)

        ttk.Label(frame, text="Feedback:").pack(anchor="w")
        feedback = tk.Text(frame, height=8, wrap="word")
        feedback.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        def _submit():
            try:
                value = float(grade_var.get())
            except ValueError:
                messagebox.showerror("Grade Submissions", "Enter a valid grade.")
                return
            if not (0 <= value <= total):
                messagebox.showerror("Grade Submissions",
                                     f"Grade must be between 0 and {total:g}.")
                return
            if self._record_submission_grade(
                    submission_id, (value / total) * 100,
                    feedback.get("1.0", tk.END).strip()):
                messagebox.showinfo("Grade Submissions", "Grade recorded.")
                self._load_ungraded(self._ungraded_tree)
                self._marking_placeholder()

        ttk.Button(frame, text="Save Grade", command=_submit).pack(anchor="w")

    # ------------------------------------------------------------------
    # Screen: Grade with Rubrics
    # ------------------------------------------------------------------
    def create_rubric_grading_content(self):
        parent = self.layout.content_frame
        for child in parent.winfo_children():
            child.destroy()

        ttk.Label(parent, text="Grade with Rubrics",
                  font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(parent,
                  text="Submissions whose assignment has a rubric attached. "
                       "The mark is the weighted total of the criteria.",
                  foreground="#7f8c8d", wraplength=700,
                  justify=tk.LEFT).pack(anchor="w", padx=10, pady=(0, 8))

        panes = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.LabelFrame(panes, text="Awaiting a rubric mark", padding=8)
        panes.add(left, weight=1)
        tree = ttk.Treeview(left, columns=UNGRADED_COLUMNS, show="headings", height=16)
        for column, width in (("ID", 60), ("Student", 150), ("Assignment", 180),
                              ("Module", 100), ("Submitted", 140)):
            tree.heading(column, text=column)
            tree.column(column, width=width)
        tree.pack(fill=tk.BOTH, expand=True)
        self._rubric_tree = tree

        right = ttk.LabelFrame(panes, text="Criteria", padding=10)
        panes.add(right, weight=1)
        self._rubric_frame = right

        tree.bind("<<TreeviewSelect>>", lambda _e: self._on_rubric_selected())
        self._load_rubric_submissions()
        self._rubric_placeholder()

    def _rubric_placeholder(self, message="Select a submission to mark against its rubric."):
        for child in self._rubric_frame.winfo_children():
            child.destroy()
        ttk.Label(self._rubric_frame, text=message, foreground="#7f8c8d",
                  wraplength=380, justify=tk.LEFT).pack(anchor="w")

    def _load_rubric_submissions(self):
        tree = self._rubric_tree
        tree.delete(*tree.get_children())
        try:
            with self._submission_connection() as conn:
                rows = conn.execute(
                    """SELECT s.id, s.student_id, s.submission_date, s.submitted_at,
                              a.title AS assignment_title, a.module_code,
                              st.first_name, st.last_name
                         FROM assignment_submissions s
                         JOIN assignments a ON a.id = s.assignment_id
                         LEFT JOIN students st ON st.student_id = s.student_id
                        WHERE s.grade IS NULL
                          AND a.rubric_id IS NOT NULL
                        ORDER BY COALESCE(s.submission_date, s.submitted_at) DESC"""
                ).fetchall()
        except Exception as exc:
            messagebox.showerror("Grade with Rubrics",
                                 f"Could not load submissions: {exc}")
            return

        for row in rows:
            name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            tree.insert("", tk.END, values=(
                row["id"], name or row["student_id"], row["assignment_title"],
                row["module_code"] or "—",
                row["submission_date"] or row["submitted_at"] or "—"))
        if not rows:
            tree.insert("", tk.END,
                        values=("", "No submissions with a rubric await marking",
                                "", "", ""))

    def _on_rubric_selected(self):
        submission_id = self._selected_submission_id(self._rubric_tree)
        if submission_id is None:
            return
        row = self._submission_detail(submission_id)
        if row is None:
            self._rubric_placeholder("That submission could not be loaded.")
            return

        rubric_id = row["assignment_rubric_id"]
        try:
            with self._submission_connection() as conn:
                criteria = conn.execute(
                    """SELECT id,
                              COALESCE(criterion_name, criteria_name) AS name,
                              COALESCE(criteria_description, description) AS detail,
                              COALESCE(max_points, 0) AS max_points,
                              COALESCE(weight, 1) AS weight
                         FROM rubric_criteria
                        WHERE rubric_id = ?
                        ORDER BY COALESCE(criterion_order, order_index, display_order, id)""",
                    (rubric_id,)).fetchall()
        except Exception as exc:
            self._rubric_placeholder(f"Could not load the rubric: {exc}")
            return

        frame = self._rubric_frame
        for child in frame.winfo_children():
            child.destroy()

        if not criteria:
            self._rubric_placeholder(
                "This assignment's rubric has no criteria defined, so there is "
                "nothing to mark against. Add criteria to the rubric first.")
            return

        student = (f"{row['student_first_name'] or ''} "
                   f"{row['student_last_name'] or ''}").strip() or row["student_id"]
        ttk.Label(frame, text=f"{student} — {row['assignment_title']}",
                  font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 8))

        score_vars = []
        for criterion in criteria:
            block = ttk.Frame(frame)
            block.pack(fill=tk.X, pady=3)
            ttk.Label(block, text=f"{criterion['name']} (max {criterion['max_points']:g})"
                      ).pack(side=tk.LEFT)
            var = tk.StringVar(value="0")
            ttk.Entry(block, textvariable=var, width=8).pack(side=tk.RIGHT)
            score_vars.append((criterion, var))

        ttk.Label(frame, text="Feedback:").pack(anchor="w", pady=(8, 0))
        feedback = tk.Text(frame, height=6, wrap="word")
        feedback.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        def _submit():
            earned = weighted_total = 0.0
            for criterion, var in score_vars:
                try:
                    value = float(var.get() or 0)
                except ValueError:
                    messagebox.showerror("Grade with Rubrics",
                                         f"'{criterion['name']}' must be a number.")
                    return
                maximum = float(criterion["max_points"] or 0)
                if maximum <= 0:
                    continue
                if not (0 <= value <= maximum):
                    messagebox.showerror(
                        "Grade with Rubrics",
                        f"'{criterion['name']}' must be between 0 and {maximum:g}.")
                    return
                weight = float(criterion["weight"] or 1)
                earned += value * weight
                weighted_total += maximum * weight

            if weighted_total <= 0:
                messagebox.showerror("Grade with Rubrics",
                                     "This rubric's criteria carry no marks, so a "
                                     "grade cannot be calculated.")
                return
            percentage = (earned / weighted_total) * 100
            if self._record_submission_grade(
                    submission_id, percentage,
                    feedback.get("1.0", tk.END).strip()):
                messagebox.showinfo("Grade with Rubrics",
                                    f"Grade recorded: {percentage:.1f}%")
                self._load_rubric_submissions()
                self._rubric_placeholder()

        ttk.Button(frame, text="Save Rubric Grade", command=_submit).pack(anchor="w")


__all__ = ["SubmissionGradingMixin"]
