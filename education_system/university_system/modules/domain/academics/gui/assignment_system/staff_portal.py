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
from education_system.university_system.modules.domain.academics.gui.assignment_system._grading import (
    GradeSubmissionDialog,
    save_submission_grade,
    send_grade_release_emails_async,
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
        ttk.Button(sub_actions, text="View File",
                   command=self._view_submission_file).pack(side='left', padx=2)

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

    def _view_submission_file(self):
        sel = self.sub_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a submission to view.",
                                parent=self.window)
            return
        submission_id = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT file_path, file_name, student_id "
                    "FROM assignment_submissions WHERE id = ?",
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
        file_path, file_name, student_id = row
        from education_system.university_system.modules.domain.academics.gui.assignment_system._file_viewer import (
            preview_file,
        )
        preview_file(self.window, file_path or '',
                     title=f"Submission #{submission_id} — {student_id}")

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

        (sub_id, student_id, file_name, current_grade, current_feedback,
         assignment_title, max_marks) = row
        max_marks = max_marks or 100.0

        def _on_save(score, feedback):
            if not save_submission_grade(sub_id, score, feedback, self.user_id):
                messagebox.showerror(
                    "Database Error",
                    "Grade save failed. See application log for details.",
                    parent=self.window)
                return
            send_grade_release_emails_async(
                sub_id, score, feedback, max_marks, self.user_id)
            messagebox.showinfo(
                "Grade Saved",
                f"Grade saved for submission #{sub_id}.\n\n"
                "The student will be notified by email that their result is "
                "available, and a confirmation will be sent to your inbox.",
                parent=self.window,
            )
            self._load_submissions()

        GradeSubmissionDialog(
            self.window,
            student_label=str(student_id),
            assignment_label=assignment_title,
            file_label=file_name or '(none)',
            max_marks=max_marks,
            current_score=current_grade,
            current_feedback=current_feedback or '',
            on_save=_on_save,
        )

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
        is_new = self.assignment is None
        new_assignment_id = None
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
                    new_assignment_id = cur.lastrowid
                conn.commit()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Save failed: {e}", parent=self.dialog)
            return

        if is_new and new_assignment_id:
            threading.Thread(
                target=_notify_enrolled_students_of_new_assignment,
                args=(new_assignment_id, module, title, due, max_marks,
                      atype, self.late_ok_var.get(), penalty, desc),
                daemon=True,
            ).start()

        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def _notify_enrolled_students_of_new_assignment(assignment_id, module_code,
                                                 title, due, max_marks,
                                                 assignment_type, late_ok,
                                                 penalty, description):
    """Background: email every student enrolled in *module_code* about the
    new assignment. Failures are logged; the assignment is already
    committed so we never roll back on a mail problem.
    """
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT m.module_name FROM modules WHERE module_code = ?
                """,
                (module_code,)
            )
            row = cur.fetchone()
            module_name = (row[0] if row else module_code) or module_code
            cur.execute(
                """
                SELECT sm.student_id,
                       COALESCE(u.email, st.email_address) AS email,
                       st.first_name
                FROM student_modules sm
                LEFT JOIN students st ON st.student_id = sm.student_id
                LEFT JOIN users u ON u.student_id = sm.student_id
                WHERE sm.module_code = ?
                  AND LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled'
                """,
                (module_code,)
            )
            students = cur.fetchall()
    except Exception as e:
        logger.warning("Assignment-notify: student lookup failed: %s", e)
        return

    if not students:
        logger.info("Assignment-notify: no enrolled students for %s",
                    module_code)
        return

    try:
        from education_system.university_system.infrastructure.email import queue_template_email
    except Exception as e:
        logger.warning("Assignment-notify: email service unavailable: %s", e)
        return

    if late_ok:
        late_policy = f"allowed (penalty {float(penalty or 0):g} / day)"
    else:
        late_policy = "not allowed"

    due_str = (due or '')[:10]
    description_text = (description or '(no description)').strip()
    sent = 0
    skipped = 0
    for student_id, email, first_name in students:
        if not email:
            skipped += 1
            continue
        try:
            queue_template_email(
                template_name='academics/assignment_created_student',
                recipient=email,
                template_vars={
                    'first_name': first_name or student_id or 'Student',
                    'module_code': module_code,
                    'module_name': module_name,
                    'assignment_title': title,
                    'due_date': due_str,
                    'max_marks': f"{float(max_marks):g}",
                    'assignment_type': assignment_type or 'individual',
                    'late_submission_policy': late_policy,
                    'description': description_text,
                },
            )
            sent += 1
        except Exception as e:
            logger.warning("Assignment-notify: send failed for %s: %s",
                           student_id, e)
    logger.info("Assignment-notify: assignment %s (%s) — queued %d, "
                "skipped %d (no email on file)",
                assignment_id, module_code, sent, skipped)


def launch_assignment_staff_portal(parent, auth):
    """Module-level entry point."""
    return AssignmentStaffPortal(parent, auth)
