"""Assignment System — Staff/Instructor portal.

A focused window for staff and instructors: list the assignments they've
created, create new ones, view submissions, and grade them inline. No
admin-only features (peer review config, rubric authoring, analytics,
maintenance). For those, admins use the full AssignmentGUI.
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)

logger = logging.getLogger(__name__)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class AssignmentStaffPortal:
    """Simplified assignment management for staff/instructors."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_id = self._resolve_user_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Assignments — Staff Portal")
        self.window.geometry("1200x760")
        self.window.minsize(1000, 640)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Loading your assignments…")
        self._current_assignment_id = None
        self._current_max_marks = 100.0

        self._build_ui()
        self._load_assignments()

    # ------------------------------------------------------------------
    # User identity
    # ------------------------------------------------------------------

    def _resolve_user_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        uid = user.get('id') or user.get('user_id')
        if uid:
            return uid
        # Fallback: look up by username
        username = user.get('username')
        if not username:
            return None
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#34495e', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)

        display = ''
        if self.auth and self.auth.current_user:
            display = self.auth.current_user.get('display_name') or \
                      self.auth.current_user.get('username', '')
        tk.Label(header, text=f"Assignment Management — {display}",
                 font=('Arial', 14, 'bold'), bg='#34495e', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        # Main paned area
        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=(8, 6))

        # Left: assignment list + action buttons
        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)

        list_header = ttk.Frame(left)
        list_header.pack(fill='x', pady=(0, 4))
        ttk.Label(list_header, text="My Assignments",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(list_header, text="+ New",
                   command=self._create_assignment).pack(side='right')
        ttk.Button(list_header, text="Refresh",
                   command=self._load_assignments).pack(side='right', padx=4)

        cols = ('title', 'module', 'due', 'max', 'subs')
        self.tree = ttk.Treeview(left, columns=cols, show='headings',
                                 selectmode='browse')
        self.tree.heading('title', text='Title')
        self.tree.heading('module', text='Module')
        self.tree.heading('due', text='Due')
        self.tree.heading('max', text='Max')
        self.tree.heading('subs', text='Subs')
        self.tree.column('title', width=260, anchor='w')
        self.tree.column('module', width=80, anchor='center')
        self.tree.column('due', width=110, anchor='center')
        self.tree.column('max', width=60, anchor='center')
        self.tree.column('subs', width=60, anchor='center')
        vsb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_assignment_selected)

        actions = ttk.Frame(left)
        actions.pack(fill='x', pady=(6, 0))
        ttk.Button(actions, text="Edit…",
                   command=self._edit_assignment).pack(side='left', padx=2)
        ttk.Button(actions, text="Delete",
                   command=self._delete_assignment).pack(side='left', padx=2)

        # Right: detail panel with submissions
        right = ttk.Frame(paned, padding=6)
        paned.add(right, weight=2)

        self.detail_var = tk.StringVar(value="Select an assignment on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                  font=('Arial', 11), wraplength=680, justify='left'
                  ).pack(anchor='w', pady=(0, 8))

        sub_frame = ttk.LabelFrame(right, text="Submissions", padding=6)
        sub_frame.pack(fill='both', expand=True)

        s_cols = ('id', 'student', 'submitted', 'file', 'grade', 'status')
        self.sub_tree = ttk.Treeview(sub_frame, columns=s_cols,
                                     show='headings', selectmode='browse')
        s_headings = [
            ('id', 'ID', 50),
            ('student', 'Student', 120),
            ('submitted', 'Submitted', 140),
            ('file', 'File', 220),
            ('grade', 'Grade', 80),
            ('status', 'Status', 120),
        ]
        for key, title, width in s_headings:
            self.sub_tree.heading(key, text=title)
            self.sub_tree.column(key, width=width,
                                 anchor='w' if key in ('file', 'student') else 'center')
        svsb = ttk.Scrollbar(sub_frame, orient='vertical',
                             command=self.sub_tree.yview)
        self.sub_tree.configure(yscrollcommand=svsb.set)
        self.sub_tree.pack(side='left', fill='both', expand=True)
        svsb.pack(side='right', fill='y')
        self.sub_tree.bind('<Double-1>', self._grade_submission)

        sub_actions = ttk.Frame(right)
        sub_actions.pack(fill='x', pady=(6, 0))
        ttk.Button(sub_actions, text="Grade / Feedback…",
                   command=self._grade_submission).pack(side='left', padx=2)

        # Status bar
        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Assignment list
    # ------------------------------------------------------------------

    def _load_assignments(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._clear_submissions()
        self.detail_var.set("Select an assignment on the left.")
        self._current_assignment_id = None

        if self.user_id is None:
            self.status_var.set(
                "Your user account is not linked to the assignments database."
            )
            return

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT a.id, a.title, a.module_code, a.due_date, a.max_marks,
                           (SELECT COUNT(*) FROM assignment_submissions s
                            WHERE s.assignment_id = a.id) AS sub_count
                    FROM assignments a
                    WHERE a.created_by = ? AND a.is_active = 1
                    ORDER BY a.due_date DESC, a.id DESC
                    """,
                    (self.user_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assignments: {e}",
                                 parent=self.window)
            return

        for aid, title, module, due, max_marks, sub_count in rows:
            self.tree.insert('', 'end', iid=str(aid), values=(
                title, module or '',
                (due or '')[:10],
                max_marks,
                sub_count,
            ))
        self.status_var.set(f"{len(rows)} assignment(s) created by you.")

    def _on_assignment_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self._current_assignment_id = int(sel[0])
        self._load_detail()
        self._load_submissions()

    def _load_detail(self):
        if self._current_assignment_id is None:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT title, module_code, due_date, max_marks,
                           description, allow_late_submission,
                           late_penalty_per_day, assignment_type
                    FROM assignments WHERE id = ?
                    """,
                    (self._current_assignment_id,)
                )
                row = cur.fetchone()
        except Exception:
            row = None
        if not row:
            self.detail_var.set("Assignment details unavailable.")
            return
        title, module, due, max_marks, desc, late_ok, late_pen, atype = row
        self._current_max_marks = float(max_marks) if max_marks else 100.0
        lines = [
            f"Title: {title}",
            f"Module: {module}   |   Due: {due}   |   Max marks: {max_marks}",
            f"Type: {atype or 'individual'}   |   "
            f"Late submissions: {'yes' if late_ok else 'no'}"
            + (f"   |   Penalty/day: {late_pen:g}" if late_ok and late_pen else ''),
            "",
            f"Description:\n{(desc or '').strip() or '(none)'}",
        ]
        self.detail_var.set('\n'.join(lines))

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    def _clear_submissions(self):
        for i in self.sub_tree.get_children():
            self.sub_tree.delete(i)

    def _load_submissions(self):
        self._clear_submissions()
        if self._current_assignment_id is None:
            self.status_var.set("Select an assignment to view its submissions.")
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.id, s.student_id,
                           COALESCE(NULLIF(TRIM(COALESCE(st.first_name, '') || ' '
                                                || COALESCE(st.last_name, '')), ''),
                                    s.student_id),
                           s.submission_date, s.file_name, s.grade, s.status,
                           s.late_submission
                    FROM assignment_submissions s
                    LEFT JOIN students st ON st.student_id = s.student_id
                    WHERE s.assignment_id = ?
                      AND COALESCE(s.is_final_submission, 1) = 1
                    ORDER BY s.submission_date DESC
                    """,
                    (self._current_assignment_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load submissions: {e}",
                                 parent=self.window)
            return

        if not rows:
            self.status_var.set("No submissions yet for this assignment.")
            return

        for sid, student_id, name, submitted, file_name, grade, status, late in rows:
            status_label = status or 'submitted'
            if late:
                status_label = f"{status_label} (late)"
            self.sub_tree.insert('', 'end', iid=str(sid), values=(
                sid,
                f"{student_id} — {name}",
                (submitted or '')[:16],
                file_name or '',
                '—' if grade is None else f"{grade:g}",
                status_label,
            ))
        self.status_var.set(f"{len(rows)} submission(s) for this assignment.")

    def _grade_submission(self, _event=None):
        sel = self.sub_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a submission to grade.",
                                parent=self.window)
            return
        submission_id = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.id, s.student_id, s.file_name, s.grade, s.feedback,
                           a.title, a.max_marks
                    FROM assignment_submissions s
                    JOIN assignments a ON a.id = s.assignment_id
                    WHERE s.id = ?
                    """,
                    (submission_id,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load submission: {e}",
                                 parent=self.window)
            return
        if not row:
            return

        GradeSubmissionDialog(self.window, row, self.user_id,
                              on_save=self._load_submissions)

    # ------------------------------------------------------------------
    # Create / edit / delete
    # ------------------------------------------------------------------

    def _create_assignment(self):
        AssignmentEditorDialog(self.window, assignment=None,
                               created_by=self.user_id,
                               on_save=self._load_assignments)

    def _edit_assignment(self):
        if self._current_assignment_id is None:
            messagebox.showinfo("No Selection",
                                "Select an assignment to edit.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, title, module_code, description, due_date,
                           max_marks, allow_late_submission, late_penalty_per_day,
                           assignment_type
                    FROM assignments WHERE id = ?
                    """,
                    (self._current_assignment_id,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if not row:
            return
        AssignmentEditorDialog(self.window, assignment=row,
                               created_by=self.user_id,
                               on_save=self._load_assignments)

    def _delete_assignment(self):
        if self._current_assignment_id is None:
            messagebox.showinfo("No Selection",
                                "Select an assignment to delete.",
                                parent=self.window)
            return
        if not messagebox.askyesno(
                "Delete Assignment",
                "Soft-delete this assignment (is_active = 0)?\n"
                "Existing submissions are kept.",
                parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE assignments SET is_active = 0, "
                    "updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(timespec='seconds'),
                     self._current_assignment_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Delete failed: {e}", parent=self.window)
            return
        self._load_assignments()


# ----------------------------------------------------------------------
# Dialogs
# ----------------------------------------------------------------------


class AssignmentEditorDialog:
    """Create or edit an assignment."""

    def __init__(self, parent, assignment, created_by, on_save):
        self.assignment = assignment  # tuple or None
        self.created_by = created_by
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Assignment" if assignment else "New Assignment")
        self.dialog.geometry("560x540")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self._modules = self._load_modules()

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky='w', pady=4)
        self.title_var = tk.StringVar(value=assignment[1] if assignment else '')
        ttk.Entry(frame, textvariable=self.title_var, width=44).grid(
            row=0, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Module:").grid(row=1, column=0, sticky='w', pady=4)
        self.module_var = tk.StringVar(
            value=assignment[2] if assignment else (self._modules[0] if self._modules else '')
        )
        self.module_combo = ttk.Combobox(frame, textvariable=self.module_var,
                                         values=self._modules, width=42,
                                         state='readonly' if self._modules else 'normal')
        self.module_combo.grid(row=1, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Due date (YYYY-MM-DD):").grid(row=2, column=0, sticky='w', pady=4)
        default_due = (assignment[4] if assignment else '')
        self.due_var = tk.StringVar(value=(default_due or '')[:10])
        ttk.Entry(frame, textvariable=self.due_var, width=44).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Max marks:").grid(row=3, column=0, sticky='w', pady=4)
        self.marks_var = tk.StringVar(value=str(assignment[5]) if assignment else '100')
        ttk.Entry(frame, textvariable=self.marks_var, width=44).grid(
            row=3, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Type:").grid(row=4, column=0, sticky='w', pady=4)
        self.type_var = tk.StringVar(
            value=(assignment[8] if assignment else 'individual')
        )
        ttk.Combobox(frame, textvariable=self.type_var,
                     values=['individual', 'group'], state='readonly',
                     width=42).grid(row=4, column=1, sticky='w', pady=4)

        self.late_ok_var = tk.BooleanVar(
            value=bool(assignment[6]) if assignment else True
        )
        ttk.Checkbutton(frame, text="Allow late submissions",
                        variable=self.late_ok_var).grid(
            row=5, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Late penalty / day:").grid(row=6, column=0, sticky='w', pady=4)
        self.penalty_var = tk.StringVar(
            value=str(assignment[7]) if assignment else '0'
        )
        ttk.Entry(frame, textvariable=self.penalty_var, width=44).grid(
            row=6, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=7, column=0, sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=44, height=8, wrap='word')
        self.desc_text.grid(row=7, column=1, sticky='w', pady=4)
        if assignment and assignment[3]:
            self.desc_text.insert('1.0', assignment[3])

        btns = ttk.Frame(frame)
        btns.grid(row=8, column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text="Save", command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _load_modules(self):
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT module_code FROM modules ORDER BY module_code")
                return [r[0] for r in cur.fetchall()]
        except Exception:
            return []

    def _save(self):
        title = self.title_var.get().strip()
        module = self.module_var.get().strip()
        due = self.due_var.get().strip()
        try:
            max_marks = int(float(self.marks_var.get()))
        except ValueError:
            messagebox.showerror("Invalid", "Max marks must be a number.",
                                 parent=self.dialog)
            return
        try:
            penalty = float(self.penalty_var.get() or 0)
        except ValueError:
            penalty = 0.0
        atype = self.type_var.get().strip() or 'individual'
        desc = self.desc_text.get('1.0', 'end').strip()

        if not title or not module or not due:
            messagebox.showerror("Missing Fields",
                                 "Title, module, and due date are required.",
                                 parent=self.dialog)
            return

        try:
            datetime.strptime(due, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 "Due date must be YYYY-MM-DD.",
                                 parent=self.dialog)
            return

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                if self.assignment:
                    cur.execute(
                        """
                        UPDATE assignments
                        SET title = ?, module_code = ?, description = ?,
                            due_date = ?, max_marks = ?,
                            allow_late_submission = ?, late_penalty_per_day = ?,
                            assignment_type = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (title, module, desc, due, max_marks,
                         1 if self.late_ok_var.get() else 0, penalty,
                         atype, now, self.assignment[0])
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO assignments
                            (module_code, title, description, due_date,
                             max_marks, assignment_type,
                             allow_late_submission, late_penalty_per_day,
                             is_active, created_by, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                        """,
                        (module, title, desc, due, max_marks, atype,
                         1 if self.late_ok_var.get() else 0, penalty,
                         self.created_by, now, now)
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Save failed: {e}", parent=self.dialog)
            return

        self.dialog.destroy()
        if self.on_save:
            self.on_save()


class GradeSubmissionDialog:
    """Enter grade + feedback for a submission."""

    def __init__(self, parent, submission_row, grader_user_id, on_save):
        # submission_row: (id, student_id, file_name, grade, feedback, a_title, max_marks)
        self.submission_id = submission_row[0]
        self.grader_user_id = grader_user_id
        self.on_save = on_save
        self.max_marks = submission_row[6] or 100

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Grade Submission")
        self.dialog.geometry("500x440")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame,
                  text=f"Assignment: {submission_row[5]}",
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 2))
        ttk.Label(frame,
                  text=f"Student: {submission_row[1]}   |   "
                       f"File: {submission_row[2] or '(none)'}   |   "
                       f"Max: {self.max_marks}"
                  ).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Grade:").pack(anchor='w')
        self.grade_var = tk.StringVar(
            value='' if submission_row[3] is None else str(submission_row[3])
        )
        ttk.Entry(frame, textvariable=self.grade_var, width=18).pack(anchor='w')

        ttk.Label(frame, text="Feedback:").pack(anchor='w', pady=(10, 2))
        self.fb_text = tk.Text(frame, width=54, height=9, wrap='word')
        self.fb_text.pack(fill='both', expand=True)
        if submission_row[4]:
            self.fb_text.insert('1.0', submission_row[4])

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(10, 0))
        ttk.Button(btns, text="Save Grade",
                   command=self._save).pack(side='right', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='right', padx=4)

    def _save(self):
        raw = self.grade_var.get().strip()
        try:
            grade = float(raw)
        except ValueError:
            messagebox.showerror("Invalid Grade",
                                 "Grade must be a number.",
                                 parent=self.dialog)
            return
        if grade < 0 or grade > self.max_marks:
            if not messagebox.askyesno(
                    "Out of Range",
                    f"Grade {grade:g} is outside 0–{self.max_marks:g}. "
                    "Save anyway?", parent=self.dialog):
                return

        feedback = self.fb_text.get('1.0', 'end').strip()
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
                    (grade, feedback, self.grader_user_id, now,
                     self.submission_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Grade save failed: {e}",
                                 parent=self.dialog)
            return

        threading.Thread(
            target=_send_grade_release_emails,
            args=(self.submission_id, grade, feedback, self.max_marks,
                  self.grader_user_id),
            daemon=True,
        ).start()

        messagebox.showinfo(
            "Grade Saved",
            f"Grade saved for submission #{self.submission_id}.\n\n"
            "The student will be notified by email that their result is "
            "available, and a confirmation will be sent to your inbox.",
            parent=self.dialog,
        )
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def _send_grade_release_emails(submission_id, grade, feedback, max_marks,
                               grader_user_id):
    """Background: email student with grade + staff with confirmation.

    Runs off the UI thread. Failures are logged; the grade is already saved.
    """
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.student_id,
                       st.email, st.first_name,
                       a.title, a.module_code,
                       u.email, u.username
                FROM assignment_submissions s
                JOIN assignments a ON a.id = s.assignment_id
                LEFT JOIN students st ON st.student_id = s.student_id
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
        from education_system.university_system.infrastructure.email import (
            queue_template_email,
            send_email,
        )
    except Exception as e:
        logger.warning("Grade email: email service unavailable: %s", e)
        return

    if student_email:
        try:
            queue_template_email(
                template_name='academics/assignment_grade_released',
                recipient=student_email,
                template_vars={
                    'student_name': student_display,
                    'assignment_title': assignment_title,
                    'module_code': module_code or '',
                    'grade': f"{grade:g} / {max_marks:g}",
                    'feedback': feedback or '(no written feedback)',
                    'signature': 'Academic Administration Team',
                },
            )
        except Exception as e:
            logger.warning("Grade email to student failed: %s", e)
    else:
        logger.info("Grade email: no email on file for student %s", student_id)

    if staff_email:
        body = (
            f"Hi {staff_username or 'there'},\n\n"
            f"You have successfully released a grade for:\n\n"
            f"  Student: {student_id} ({student_display})\n"
            f"  Assignment: {assignment_title} ({module_code or 'n/a'})\n"
            f"  Grade: {grade:g} / {max_marks:g}\n\n"
            f"The student has been notified by email.\n\n"
            f"Regards,\nAcademic Administration Team"
        )
        try:
            send_email(
                recipient_email=staff_email,
                subject=f"Grade Sent: {assignment_title} — {student_id}",
                body=body,
            )
        except Exception as e:
            logger.warning("Grade confirmation to staff failed: %s", e)


def launch_assignment_staff_portal(parent, auth):
    """Module-level entry point."""
    return AssignmentStaffPortal(parent, auth)
