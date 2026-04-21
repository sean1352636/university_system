"""Assignment System — Student portal.

A student-facing window: list assignments for their enrolled modules,
see submission status, submit a file, and view grade/feedback once
graded. No admin controls.
"""

import hashlib
import logging
import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)

logger = logging.getLogger(__name__)

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
                        "SELECT student_id FROM users WHERE id = ?",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0]:
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
        (aid, title, module_code, due, _max, _desc, _instr,
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

        try:
            with open(file_path, 'rb') as fh:
                file_hash = hashlib.sha256(fh.read()).hexdigest()
        except Exception as e:
            messagebox.showerror("Read Failed",
                                 f"Could not read file: {e}",
                                 parent=self.window)
            return

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.assignment_id, s.file_name, s.submission_date,
                           a.title
                    FROM assignment_submissions s
                    LEFT JOIN assignments a ON a.id = s.assignment_id
                    WHERE s.student_id = ? AND s.file_hash = ?
                    ORDER BY s.submission_date DESC
                    LIMIT 1
                    """,
                    (self.student_id, file_hash)
                )
                duplicate = cur.fetchone()
        except Exception:
            duplicate = None

        if duplicate:
            prev_aid, prev_name, prev_date, prev_title = duplicate
            if prev_aid == aid:
                where = "for this assignment"
            else:
                where = f"for '{prev_title or f'assignment #{prev_aid}'}'"
            messagebox.showwarning(
                "Already Submitted",
                f"You've already submitted this exact file {where}.\n\n"
                f"Previous submission: {prev_name} at {(prev_date or '')[:16]}\n\n"
                f"Each submission must be a distinct file. Edit the file "
                f"(or submit a different one) and try again.",
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
        submission_id = None
        version_number = 1
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
                         file_path, file_name, file_size, file_hash, status,
                         late_submission, late_days, version_number,
                         is_final_submission)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?,
                            COALESCE((SELECT MAX(version_number) + 1
                                      FROM assignment_submissions
                                      WHERE assignment_id = ? AND student_id = ?), 1),
                            1)
                    """,
                    (aid, self.student_id, now, str(dest), orig_name,
                     file_size, file_hash, 1 if is_late else 0, late_days,
                     aid, self.student_id)
                )
                submission_id = cur.lastrowid
                cur.execute(
                    "SELECT version_number FROM assignment_submissions WHERE id = ?",
                    (submission_id,)
                )
                row = cur.fetchone()
                if row:
                    version_number = row[0]
                conn.commit()
        except Exception as e:
            messagebox.showerror("Submission Failed",
                                 f"Database save failed: {e}",
                                 parent=self.window)
            return

        threading.Thread(
            target=self._post_submit_tasks,
            args=(submission_id, aid, str(dest), orig_name, title,
                  module_code, version_number, is_late, late_days, now,
                  file_hash),
            daemon=True,
        ).start()

        messagebox.showinfo(
            "Submitted",
            f"Submitted '{orig_name}' for {title}."
            + (f"\n(Late by {late_days} day(s).)" if is_late else '')
            + "\n\nA confirmation email and plagiarism report will be sent to"
              " your registered email address shortly.",
            parent=self.window)
        self._load_assignments()
        # Re-select the same assignment if still in the list
        iid = str(aid)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self._on_selected()

    def _post_submit_tasks(self, submission_id, aid, file_path, orig_name,
                           assignment_title, module_code, version_number,
                           is_late, late_days, submission_time, file_hash):
        """Background: plagiarism check + confirmation/report emails.

        Runs off the UI thread. Any failure here is logged but does not
        roll back the submission — the student's file is already stored.
        """
        student_email, first_name, module_name = self._lookup_student_and_module(module_code)
        if not student_email:
            logger.warning("Submission %s: no email on file for student %s",
                           submission_id, self.student_id)
            return

        self._send_submission_confirmation(
            student_email, first_name, assignment_title, module_code,
            module_name, version_number, is_late, late_days, submission_time,
        )

        plagiarism_summary = self._run_plagiarism_check(
            aid, file_path, orig_name, assignment_title, module_code,
            submission_id,
        )
        if plagiarism_summary:
            self._send_plagiarism_email(
                student_email, first_name, assignment_title,
                module_code, plagiarism_summary,
            )

    def _lookup_student_and_module(self, module_code):
        email = first_name = module_name = None
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COALESCE(u.email, st.email_address) AS email,
                           st.first_name
                    FROM students st
                    LEFT JOIN users u ON u.student_id = st.student_id
                    WHERE st.student_id = ?
                    """,
                    (self.student_id,)
                )
                row = cur.fetchone()
                if row:
                    email, first_name = row
                if module_code:
                    cur.execute(
                        "SELECT module_name FROM modules WHERE module_code = ?",
                        (module_code,)
                    )
                    row = cur.fetchone()
                    if row:
                        module_name = row[0]
        except Exception as e:
            logger.warning("Could not resolve student/module for submission: %s", e)
        user = (self.auth.current_user if self.auth else None) or {}
        email = email or user.get('email')
        first_name = first_name or user.get('first_name') or user.get('display_name') or 'Student'
        module_name = module_name or module_code or ''
        return email, first_name, module_name

    def _send_submission_confirmation(self, email, first_name, assignment_title,
                                      module_code, module_name, version_number,
                                      is_late, late_days, submission_time):
        try:
            from education_system.university_system.infrastructure.email import queue_template_email
            late_text = f" (late by {late_days} day(s))" if is_late else ""
            queue_template_email(
                template_name='academics/assignment_submission_student',
                recipient=email,
                template_vars={
                    'first_name': first_name,
                    'module_code': module_code or '',
                    'module_name': module_name,
                    'assignment_title': assignment_title,
                    'version_number': str(version_number),
                    'submission_status': 'Late Submission' if is_late else 'On Time',
                    'late_text': late_text,
                    'submission_time': submission_time,
                },
            )
        except Exception as e:
            logger.warning("Submission confirmation email failed: %s", e)

    def _run_plagiarism_check(self, aid, file_path, orig_name,
                              assignment_title, module_code, submission_id):
        """Scan the new submission against every prior submission for the
        same assignment and return a summary dict, or None on failure.

        Before running the scan we ingest any existing submission that
        isn't yet in the plagiarism repository, so every submission is a
        comparison target even if it predates the plagiarism wiring.
        """
        try:
            from education_system.university_system.modules.domain.academics.services.plagiarism.checker import (
                PlagiarismChecker,
            )
        except Exception as e:
            logger.info("Plagiarism checker unavailable: %s", e)
            return None

        try:
            checker = PlagiarismChecker()
        except Exception as e:
            logger.warning("Could not initialise plagiarism checker: %s", e)
            return None

        try:
            content, file_type = checker.extract_text_from_file(file_path)
        except Exception as e:
            logger.info("Plagiarism: text extraction failed for %s: %s", orig_name, e)
            return {'status': 'SKIPPED', 'reason': str(e),
                    'highest_similarity': 0.0, 'compared_count': 0,
                    'matches': []}

        author_id = self._resolve_numeric_user_id()
        if not author_id:
            logger.info("Plagiarism: could not resolve numeric user id for %s",
                        self.student_id)
            return None

        compared_count = self._seed_repo_with_assignment_submissions(
            checker, aid, exclude_submission_id=submission_id,
        )

        try:
            doc_id = checker.add_document_to_repository(
                title=f"{assignment_title} — {orig_name}",
                content=content,
                author_id=author_id,
                module_code=module_code or '',
                file_type=file_type,
            )
        except Exception as e:
            logger.warning("Plagiarism: add_document_to_repository failed: %s", e)
            return None

        try:
            result = checker.check_plagiarism(
                document_id=doc_id,
                checker_id=author_id,
                threshold=0.3,
            )
        except Exception as e:
            logger.warning("Plagiarism: check_plagiarism failed: %s", e)
            return None

        if isinstance(result, dict):
            result['compared_count'] = compared_count
        return result

    def _seed_repo_with_assignment_submissions(self, checker, aid,
                                                exclude_submission_id):
        """Ingest every other final submission for this assignment into
        the plagiarism repository, so the subsequent scan has something
        to compare against.

        Returns the number of other submissions that were considered
        (including ones already in the repo). Silently skips files that
        can't be read or whose author has no users.id.
        """
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.id, s.file_path, s.file_name, s.student_id,
                           a.title, a.module_code, u.id AS author_user_id
                    FROM assignment_submissions s
                    JOIN assignments a ON a.id = s.assignment_id
                    LEFT JOIN users u ON u.student_id = s.student_id
                    WHERE s.assignment_id = ?
                      AND s.id != ?
                      AND COALESCE(s.is_final_submission, 1) = 1
                    """,
                    (aid, exclude_submission_id)
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.warning("Plagiarism: could not list prior submissions: %s", e)
            return 0

        seeded = 0
        for (_sid, fpath, fname, _student_id, title, mod_code,
             author_uid) in rows:
            if not fpath or not author_uid:
                continue
            try:
                text, ftype = checker.extract_text_from_file(fpath)
            except Exception as e:
                logger.debug("Plagiarism seed: skipping %s (%s)", fname, e)
                continue
            try:
                checker.add_document_to_repository(
                    title=f"{title} — {fname}",
                    content=text,
                    author_id=author_uid,
                    module_code=mod_code or '',
                    file_type=ftype,
                )
                seeded += 1
            except Exception as e:
                logger.debug("Plagiarism seed: add failed for %s: %s", fname, e)
        return len(rows)

    def _resolve_numeric_user_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        uid = user.get('id') or user.get('user_id')
        if isinstance(uid, int) and uid > 0:
            return uid
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM users WHERE student_id = ?",
                    (self.student_id,)
                )
                row = cur.fetchone()
                if row and isinstance(row[0], int) and row[0] > 0:
                    return row[0]
        except Exception:
            pass
        return None

    def _send_plagiarism_email(self, email, first_name, assignment_title,
                                module_code, summary):
        try:
            from education_system.university_system.infrastructure.email import queue_template_email
        except Exception as e:
            logger.warning("queue_template_email unavailable for plagiarism report: %s", e)
            return

        status = summary.get('status', 'UNKNOWN')
        score = summary.get('highest_similarity') or 0.0
        compared_count = summary.get('compared_count', 0)
        matches = summary.get('matches') or []

        verdicts = {
            'SKIPPED': "The file you submitted could not be scanned "
                       "automatically ({reason}). Your instructor may still "
                       "run a manual check — no action is required from you.",
            'EXACT_MATCH': "An exact match was found: your submission is "
                           "byte-for-byte identical to existing material in "
                           "the repository.",
            'HIGH_SIMILARITY': "A high similarity score was detected against "
                               "existing submissions.",
            'MODERATE_SIMILARITY': "A moderate similarity score was detected "
                                   "against existing submissions.",
            'LOW_SIMILARITY': "A low similarity score was detected against "
                              "existing submissions.",
            'NO_MATCH': "No significant matches were found against existing "
                        "submissions.",
        }
        verdict = verdicts.get(status, f"Scan completed with status: {status}.")
        if status == 'SKIPPED':
            verdict = verdict.format(reason=summary.get('reason',
                                                         'unsupported file type'))

        matches_info = ''
        matches_info_html = ''
        if matches:
            n = len(matches)
            matches_info = f"- {n} matching document(s) identified in the repository."
            matches_info_html = (
                f"<li><strong>Matches:</strong> {n} matching document(s) "
                "identified in the repository.</li>"
            )

        try:
            queue_template_email(
                template_name='academics/plagiarism_report_student',
                recipient=email,
                template_vars={
                    'first_name': first_name,
                    'assignment_title': assignment_title,
                    'module_code': module_code or 'n/a',
                    'status': status,
                    'similarity_pct': f"{score * 100:.1f}%",
                    'compared_count': str(compared_count),
                    'verdict': verdict,
                    'matches_info': matches_info,
                    'matches_info_html': matches_info_html,
                },
            )
        except Exception as e:
            logger.warning("Plagiarism email send failed: %s", e)


def launch_assignment_student_portal(parent, auth):
    """Module-level entry point."""
    return AssignmentStudentPortal(parent, auth)
