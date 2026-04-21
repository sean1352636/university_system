"""Assignment System — Student portal.

A student-facing window: list assignments for their enrolled modules,
see submission status, submit a file, and view grade/feedback once
graded. No admin controls.
"""

import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)

try:
    from education_system.university_system.modules.shared.constants import paths
    _SUBMISSIONS_DIR = Path(paths.SUBMISSIONS_DIR)
except Exception:
    _SUBMISSIONS_DIR = Path.cwd() / "submissions"


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class AssignmentStudentPortal:
    """Simplified assignment viewer / submitter for students."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.student_id = self._resolve_student_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Assignments — My Portal")
        self.window.geometry("1120x700")
        self.window.minsize(960, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Loading your assignments…")
        self._current_assignment_id = None
        self._current_assignment = None

        self._build_ui()
        if self.student_id is None:
            self._show_not_found()
        else:
            self._load_assignments()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def _resolve_student_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        explicit = user.get('student_id')
        if explicit:
            return explicit
        user_id = user.get('id') or user.get('user_id')
        if user_id:
            try:
                with _connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT student_id FROM students WHERE user_id = ?",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0]
            except Exception:
                pass
        # Fall back to username matching student_id
        username = user.get('username')
        if username:
            try:
                with _connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT student_id FROM students WHERE student_id = ?",
                        (username,)
                    )
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
        tk.Label(header, text=f"My Assignments — {display}",
                 font=('Arial', 14, 'bold'), bg='#2980b9', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._load_assignments).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=(8, 6))

        # Left: assignments list
        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)

        ttk.Label(left, text="Assignments for my enrolled modules",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 4))

        cols = ('title', 'module', 'due', 'status', 'grade')
        self.tree = ttk.Treeview(left, columns=cols, show='headings',
                                 selectmode='browse')
        self.tree.heading('title', text='Title')
        self.tree.heading('module', text='Module')
        self.tree.heading('due', text='Due')
        self.tree.heading('status', text='Status')
        self.tree.heading('grade', text='Grade')
        self.tree.column('title', width=240, anchor='w')
        self.tree.column('module', width=80, anchor='center')
        self.tree.column('due', width=100, anchor='center')
        self.tree.column('status', width=110, anchor='center')
        self.tree.column('grade', width=80, anchor='center')

        vsb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_selected)

        self.tree.tag_configure('overdue', background='#f9d6d5')
        self.tree.tag_configure('graded', background='#d5f5e3')
        self.tree.tag_configure('submitted', background='#fef9e7')

        # Right: detail + submit
        right = ttk.Frame(paned, padding=6)
        paned.add(right, weight=2)

        self.detail_var = tk.StringVar(value="Select an assignment on the left.")
        detail_label = ttk.Label(right, textvariable=self.detail_var,
                                 font=('Arial', 11), wraplength=640,
                                 justify='left')
        detail_label.pack(anchor='w', pady=(0, 8))

        self.grade_frame = ttk.LabelFrame(right, text="My Submission",
                                          padding=8)
        self.grade_frame.pack(fill='x', pady=(0, 8))
        self.grade_var = tk.StringVar(value="No submission yet.")
        ttk.Label(self.grade_frame, textvariable=self.grade_var,
                  wraplength=640, justify='left').pack(anchor='w')

        actions = ttk.Frame(right)
        actions.pack(fill='x', pady=(6, 0))
        self.submit_btn = ttk.Button(actions, text="Submit / Resubmit…",
                                     command=self._submit_file,
                                     state='disabled')
        self.submit_btn.pack(side='left')

        # Status bar
        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _show_not_found(self):
        self.status_var.set("No student record matched your account.")
        self.detail_var.set(
            "Your user account is not linked to a student record.\n"
            "Contact an administrator to have your student_id assigned."
        )

    def _load_assignments(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._current_assignment_id = None
        self._current_assignment = None
        self.detail_var.set("Select an assignment on the left.")
        self.grade_var.set("No submission yet.")
        self.submit_btn.configure(state='disabled')

        if self.student_id is None:
            return

        today = datetime.now().date().isoformat()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT a.id, a.title, a.module_code, a.due_date, a.max_marks,
                           s.status, s.grade, s.id AS submission_id,
                           a.allow_late_submission
                    FROM assignments a
                    JOIN student_modules sm ON sm.module_code = a.module_code
                    LEFT JOIN assignment_submissions s
                           ON s.assignment_id = a.id
                          AND s.student_id = sm.student_id
                          AND s.is_final_submission = 1
                    WHERE sm.student_id = ? AND a.is_active = 1
                    ORDER BY a.due_date ASC
                    """,
                    (self.student_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assignments: {e}",
                                 parent=self.window)
            return

        pending = 0
        for aid, title, module, due, max_marks, sub_status, grade, sub_id, late_ok in rows:
            due_str = (due or '')[:10]
            if sub_status == 'graded' or grade is not None:
                status = 'Graded'
                tag = 'graded'
            elif sub_status:
                status = sub_status.capitalize()
                tag = 'submitted'
            elif due_str and due_str < today:
                status = 'Overdue' if not late_ok else 'Late allowed'
                tag = 'overdue'
                pending += 1
            else:
                status = 'Pending'
                tag = ''
                pending += 1

            self.tree.insert('', 'end', iid=str(aid), values=(
                title, module or '', due_str, status,
                '—' if grade is None else f"{grade:g}"
            ), tags=(tag,) if tag else ())

        self.status_var.set(
            f"{len(rows)} assignment(s)  |  {pending} pending / overdue."
        )

    def _on_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self._current_assignment_id = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT a.id, a.title, a.module_code, a.due_date, a.max_marks,
                           a.description, a.instructions,
                           a.allow_late_submission, a.late_penalty_per_day,
                           a.max_file_size_mb, a.file_types_allowed
                    FROM assignments a WHERE a.id = ?
                    """,
                    (self._current_assignment_id,)
                )
                assignment = cur.fetchone()
                cur.execute(
                    """
                    SELECT id, submission_date, file_name, grade, feedback,
                           status, late_submission, late_days
                    FROM assignment_submissions
                    WHERE assignment_id = ? AND student_id = ?
                    ORDER BY submission_date DESC LIMIT 1
                    """,
                    (self._current_assignment_id, self.student_id)
                )
                submission = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if not assignment:
            return

        self._current_assignment = assignment
        _aid, title, module, due, max_marks, desc, instr, late_ok, _pen, _fs, types = assignment

        detail = [
            f"Title: {title}",
            f"Module: {module}   |   Due: {due}   |   Max marks: {max_marks}",
            f"Late submissions: {'allowed' if late_ok else 'not allowed'}"
            + (f"   |   Accepted types: {types}" if types else ''),
            "",
            f"Description:\n{(desc or '').strip() or '(none)'}",
        ]
        if instr:
            detail += ["", f"Instructions:\n{instr.strip()}"]
        self.detail_var.set('\n'.join(detail))

        if submission:
            sid, sdate, fname, grade, feedback, status, late, late_days = submission
            lines = [
                f"Submitted: {sdate}",
                f"File: {fname or '(none)'}",
                f"Status: {status or 'submitted'}"
                + (f"   (late by {late_days} day(s))" if late else ''),
            ]
            if grade is not None:
                lines.append(f"Grade: {grade:g} / {max_marks}")
            if feedback:
                lines += ["", f"Feedback:\n{feedback}"]
            self.grade_var.set('\n'.join(lines))
        else:
            self.grade_var.set("No submission yet.")

        today = datetime.now().date().isoformat()
        due_str = (due or '')[:10]
        is_overdue = due_str and due_str < today
        can_submit = True
        if is_overdue and not late_ok:
            can_submit = False
        self.submit_btn.configure(state='normal' if can_submit else 'disabled')

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def _submit_file(self):
        if not self._current_assignment or self.student_id is None:
            return
        (aid, title, _module, due, _max, _desc, _instr,
         late_ok, _penalty, _fs_mb, types_allowed) = self._current_assignment

        file_path = filedialog.askopenfilename(
            parent=self.window,
            title=f"Select file to submit for: {title}"
        )
        if not file_path:
            return

        if types_allowed:
            allowed = {t.strip().lower().lstrip('.')
                       for t in types_allowed.split(',') if t.strip()}
            ext = Path(file_path).suffix.lower().lstrip('.')
            if allowed and ext not in allowed:
                messagebox.showerror(
                    "File Type Not Allowed",
                    f"Accepted types: {types_allowed}\nYou chose: .{ext}",
                    parent=self.window)
                return

        dest_dir = _SUBMISSIONS_DIR / 'submitted' / str(self.student_id) / f"assignment_{aid}"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror(
                "Filesystem Error",
                f"Could not create submission folder: {e}",
                parent=self.window)
            return

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        orig_name = os.path.basename(file_path)
        stored_name = f"{ts}_{orig_name}"
        dest = dest_dir / stored_name
        try:
            shutil.copy2(file_path, dest)
        except Exception as e:
            messagebox.showerror("Copy Failed",
                                 f"Could not copy file: {e}",
                                 parent=self.window)
            return

        try:
            file_size = dest.stat().st_size
        except Exception:
            file_size = None

        today = datetime.now().date().isoformat()
        due_str = (due or '')[:10]
        is_late = bool(due_str and due_str < today)
        late_days = 0
        if is_late:
            try:
                d_due = datetime.strptime(due_str, '%Y-%m-%d').date()
                late_days = (datetime.now().date() - d_due).days
            except Exception:
                late_days = 0

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                # Mark prior submissions for this assignment as non-final
                cur.execute(
                    "UPDATE assignment_submissions "
                    "SET is_final_submission = 0 "
                    "WHERE assignment_id = ? AND student_id = ?",
                    (aid, self.student_id)
                )
                cur.execute(
                    """
                    INSERT INTO assignment_submissions
                        (assignment_id, student_id, submission_date,
                         file_path, file_name, file_size, status,
                         late_submission, late_days, version_number,
                         is_final_submission)
                    VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?,
                            COALESCE((SELECT MAX(version_number) + 1
                                      FROM assignment_submissions
                                      WHERE assignment_id = ? AND student_id = ?), 1),
                            1)
                    """,
                    (aid, self.student_id, now, str(dest), orig_name, file_size,
                     1 if is_late else 0, late_days, aid, self.student_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Submission Failed",
                                 f"Database save failed: {e}",
                                 parent=self.window)
            return

        messagebox.showinfo(
            "Submitted",
            f"Submitted '{orig_name}' for {title}."
            + (f"\n(Late by {late_days} day(s).)" if is_late else ''),
            parent=self.window)
        self._load_assignments()
        # Re-select the same assignment if still in the list
        iid = str(aid)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self._on_selected()


def launch_assignment_student_portal(parent, auth):
    """Module-level entry point."""
    return AssignmentStudentPortal(parent, auth)
