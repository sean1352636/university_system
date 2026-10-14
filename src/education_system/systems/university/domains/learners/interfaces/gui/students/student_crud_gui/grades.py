# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _safe_set_combobox, _safe_entry_insert

#: Display precedence when several sources describe the same piece of work.
#: Higher wins. An exam row beats the assessment that was generated from it,
#: which beats the assignment generated from *that*.
_TYPE_RANK = {"Exam": 3, "Online Exam": 2, "Assessment": 1, "Assignment": 0}

#: Names some syncs generate when they have nothing better — "ACC-Y1-1 exam".
#: A merged row prefers a real title over one of these.
def _is_placeholder_name(module_code, name):
    return str(name or "").strip().lower() in (
        f"{str(module_code or '').lower()} exam", "exam", "")


def _work_key(module_code, name, due):
    """Identity for a piece of work with no id linking it to anything.

    Module + title + the *date* part of the due timestamp. The time is
    dropped because the same item is stored as '2026-06-17 09:00' in one
    table and '2026-06-17' in another.
    """
    return ("work", str(module_code or "").strip().lower(),
            str(name or "").strip().lower(), str(due or "")[:10])


def _dedupe_rows(pairs):
    """Collapse rows describing the same work, keeping the best one.

    One exam currently reaches this table up to four times: the scheduled
    ``exams`` row, the ``exam_portal_exams`` row synced from it, the
    ``assessments`` row generated from the exam, and the ``assignments`` row
    generated from that assessment. None of that duplication is visible to a
    student looking at their own record — it is an artefact of four tables
    modelling one thing.

    *pairs* is ``(key, row)``. Rows sharing a key merge into the one that
    carries the most information: a grade first, then a submission, then the
    type precedence above. The merged row takes the most descriptive title of
    the group, so folding an exam into a placeholder-named row does not lose
    the real name.
    """
    def score(row):
        graded = 4 if str(row[5]).strip() not in ("Not Graded", "") else 0
        submitted = 2 if row[4] == "Yes" else 0
        return graded + submitted + _TYPE_RANK.get(row[0], 0)

    # A row that knows its exam id also tells us that *its own* module+title+
    # date describes that exam. Without this, an assessment linked by exam_id
    # jumps to the exam's key and the assignment generated from it — which has
    # only module+title+date to go on — is left stranded as a separate row.
    aliases = {}
    for key, row in pairs:
        if isinstance(key, tuple) and key[0] == "exam":
            own = _work_key(row[1], row[2], row[3])
            aliases.setdefault(own, key)

    def resolve(key):
        seen = set()
        while key in aliases and key not in seen:
            seen.add(key)
            key = aliases[key]
        return key

    pairs = [(resolve(key) if key is not None else None, row)
             for key, row in pairs]

    best = {}
    for key, row in pairs:
        if key is None:
            # Nothing to match on — always keep it.
            best[("unique", id(row))] = row
            continue
        current = best.get(key)
        if current is None or score(row) > score(current):
            best[key] = row

    # Second pass: give each surviving row the best title seen for its key.
    titles = {}
    for key, row in pairs:
        if key is None:
            continue
        name = row[2]
        if _is_placeholder_name(row[1], name):
            continue
        # Prefer the longest real title; ties keep the first seen.
        if len(str(name)) > len(str(titles.get(key, ""))):
            titles[key] = name

    out = []
    for key, row in best.items():
        better = titles.get(key)
        if better and better != row[2]:
            row = row[:2] + (better,) + row[3:]
        out.append(row)
    return out


def _load_exam_rows(cursor, student_id):
    """Exam rows for the grades table — scheduled sittings and online exams.

    Two separate stores, so two queries:

    * ``exams`` holds scheduled sittings. Its result lands in
      ``student_grades`` under the name ``apply_exam_results`` writes,
      ``"{module} Exam ({date})"``, so the join reproduces that name exactly
      rather than guessing at a match.
    * ``exam_portal_exams`` / ``exam_portal_attempts`` hold online exams,
      where the attempt itself carries the score.

    Either table may be absent — both are created lazily by their own GUI —
    so each query degrades to no rows instead of failing the whole window.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []

    try:
        cursor.execute("""
            SELECT 'Exam' AS type, e.module_code,
                   COALESCE(NULLIF(e.exam_name, ''), e.module_code || ' exam'),
                   COALESCE(e.date, '') AS due,
                   CASE WHEN sg.percentage IS NOT NULL THEN 'Yes' ELSE 'No' END,
                   COALESCE(sg.grade, 'Not Graded'),
                   100,
                   CASE
                       WHEN sg.percentage IS NOT NULL THEN 'Graded'
                       WHEN e.date > ? THEN 'Scheduled'
                       ELSE 'Awaiting result'
                   END,
                   e.id
            FROM exams e
            LEFT JOIN student_grades sg
                   ON sg.student_id = ?
                  AND sg.module_code = e.module_code
                  AND sg.assessment_name = e.module_code || ' Exam (' || e.date || ')'
            WHERE e.module_code IN (SELECT module_code FROM student_modules
                                    WHERE student_id = ?)
            ORDER BY e.date DESC
        """, (today, student_id, student_id))
        for r in cursor.fetchall():
            row = tuple(r)
            rows.append((("exam", row[8]), row[:8]))
    except Exception as exc:
        logger.debug("Could not load scheduled exams: %s", exc)

    try:
        # exam_portal_exams carries no link back to the exam it was synced
        # from, so it is matched the same way sync_from_scheduler matched it:
        # module_code plus the date part of the start time. Where that finds
        # the scheduled exam, both rows collapse into one.
        cursor.execute("""
            SELECT 'Online Exam' AS type, pe.module_code, pe.title,
                   COALESCE(pe.end_time, pe.start_time, '') AS due,
                   CASE WHEN pa.id IS NOT NULL THEN 'Yes' ELSE 'No' END,
                   COALESCE(CAST(ROUND(pa.percentage, 1) AS TEXT) || '%',
                            'Not Graded'),
                   COALESCE(pe.total_marks, 100),
                   CASE
                       WHEN pa.status = 'graded' THEN 'Graded'
                       WHEN pa.id IS NOT NULL THEN 'Submitted'
                       ELSE 'Not Submitted'
                   END,
                   se.id AS linked_exam_id
            FROM exam_portal_exams pe
            LEFT JOIN exam_portal_attempts pa
                   ON pa.exam_id = pe.id AND pa.student_id = ?
            LEFT JOIN exams se
                   ON se.module_code = pe.module_code
                  AND se.date = substr(COALESCE(pe.start_time, ''), 1, 10)
            WHERE pe.module_code IN (SELECT module_code FROM student_modules
                                     WHERE student_id = ?)
            ORDER BY pe.start_time DESC
        """, (student_id, student_id))
        for r in cursor.fetchall():
            row = tuple(r)
            linked = row[8]
            key = ("exam", linked) if linked else _work_key(row[1], row[2], row[3])
            rows.append((key, row[:8]))
    except Exception as exc:
        logger.debug("Could not load online exams: %s", exc)

    return rows


def _outstanding_items(tree):
    """Rows the student has not submitted, as ``(type, module, item, due)``."""
    out = []
    for item in tree.get_children(''):
        values = tree.item(item, 'values')
        if len(values) >= 8 and values[7] == 'Not Submitted':
            out.append((values[0], values[1], values[2], values[3]))
    return out


def send_outstanding_reminder(self, student_id, first_name, tree):
    """Email the student everything they have not submitted, with due dates."""
    outstanding = _outstanding_items(tree)
    if not outstanding:
        messagebox.showinfo(
            _t("common.info", default="Nothing outstanding"),
            f"{first_name} has submitted everything on this list.",
            parent=self.root)
        return

    recipient = None
    try:
        conn = get_db_connection()
        if conn:
            row = conn.cursor().execute(
                "SELECT email_address FROM students WHERE student_id = ?",
                (student_id,)).fetchone()
            recipient = tuple(row)[0] if row else None
            conn.close()
    except Exception as exc:
        logger.warning("Could not look up the student's email: %s", exc)

    if not recipient:
        messagebox.showerror(
            _t("common.error", default="Error"),
            f"No email address on file for {first_name}, so the reminder "
            f"cannot be sent.", parent=self.root)
        return

    lines = []
    for kind, module, item, due in outstanding:
        due_text = f"due {due}" if str(due).strip() else "no due date recorded"
        lines.append(f"  • [{kind}] {module} — {item}  ({due_text})")
    preview = "\n".join(lines)

    if not messagebox.askyesno(
            _t("common.confirm", default="Send reminder"),
            f"Email {recipient} about {len(outstanding)} outstanding item(s)?"
            f"\n\n{preview}", parent=self.root):
        return

    try:
        from education_system.systems.university.infrastructure.email import (
            send_template_email,
        )
        sender = "the Academic Office"
        try:
            user = self.auth.current_user if getattr(self, "auth", None) else None
            sender = (user or {}).get("username") or sender
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Full path — these templates sit two levels deep and the bare-name
        # lookup only searches one, so a bare name resolves to nothing.
        result = send_template_email(
            "academics/teaching/assignments/outstanding_work_reminder",
            recipient,
            {
                "first_name": first_name,
                "student_id": student_id,
                "item_count": len(outstanding),
                "outstanding_items": preview,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "sender_name": sender,
            },
        )
    except Exception as exc:
        logger.error("Outstanding-work reminder failed: %s", exc)
        messagebox.showerror(_t("common.error", default="Error"),
                             f"Could not send the reminder: {exc}",
                             parent=self.root)
        return

    if result is False:
        messagebox.showerror(
            _t("common.error", default="Error"),
            "The email system rejected the reminder. Check the mail "
            "configuration and the logs.", parent=self.root)
        return
    messagebox.showinfo(
        _t("common.success", default="Sent"),
        f"Reminder for {len(outstanding)} item(s) sent to {recipient}.",
        parent=self.root)


def manage_student_grades(self, student_id, first_name, last_name):
    """Display and manage student grades with assignments/assessments table"""
    try:
        grades_window = tk.Toplevel(self.root)
        _install_clean_close(grades_window)
        grades_window.title(f"View Grades - {first_name} {last_name} ({student_id})")
        grades_window.geometry("1150x620")
        grades_window.transient(self.root)

        main_frame = ttk.Frame(grades_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Grades for {first_name} {last_name}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview for grades
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # "Item" rather than "Assignment": this table now also lists
        # assessments and exams. "Due" was added because it is what makes an
        # unsubmitted row actionable — and it is what the reminder email
        # quotes back to the student.
        columns = ("Type", "Module", "Item", "Due", "Submitted",
                   "Grade", "Max Grade", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        widths = {"Type": 90, "Module": 100, "Item": 250, "Due": 110,
                  "Submitted": 90, "Grade": 90, "Max Grade": 90, "Status": 120}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 120))
        tree.tag_configure("missing", background="#fde4e4")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Fetch grades from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            grades_window.destroy()
            return

        cursor = conn.cursor()

        # Get assignments and grades
        cursor.execute("""
            SELECT 'Assignment' as type, a.module_code, a.title,
                   COALESCE(a.due_date, '') as due,
                   CASE WHEN s.submission_date IS NOT NULL THEN 'Yes' ELSE 'No' END as submitted,
                   COALESCE(s.grade, 'Not Graded') as grade,
                   COALESCE(a.max_marks, 100) as max_marks,
                   CASE
                       WHEN s.grade IS NOT NULL THEN 'Graded'
                       WHEN s.submission_date IS NOT NULL THEN 'Submitted'
                       ELSE 'Not Submitted'
                   END as status
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
            ORDER BY a.module_code, a.due_date DESC
        """, (student_id,))

        # Assignments have no id linking them to the assessment they were
        # generated from, so they are matched on module + title + due date.
        assignments = [(_work_key(r[1], r[2], r[3]), tuple(r))
                       for r in (tuple(x) for x in cursor.fetchall())]

        # Get assessments if table exists
        assessments = []
        try:
            cursor.execute("""
                SELECT 'Assessment' as type, a.module_code, a.assessment_name,
                       COALESCE(a.due_date, '') as due,
                       'N/A' as submitted,
                       COALESCE(g.score, 'Not Graded') as score,
                       COALESCE(a.max_points, 100) as max_points,
                       CASE WHEN g.score IS NOT NULL THEN 'Graded' ELSE 'Pending' END as status,
                       a.exam_id
                FROM assessments a
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = ?
                WHERE a.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
                ORDER BY a.module_code
            """, (student_id, student_id))
            for r in cursor.fetchall():
                row = tuple(r)
                # assessments.exam_id is the one real link in this pile: set
                # when the assessment was created from a scheduled exam.
                key = (("exam", row[8]) if row[8]
                       else _work_key(row[1], row[2], row[3]))
                assessments.append((key, row[:8]))
        except Exception as e:
            logger.debug("Could not load assessments: %s", e)

        exams = _load_exam_rows(cursor, student_id)

        conn.close()

        all_items = _dedupe_rows(assignments + assessments + exams)
        all_items.sort(key=lambda r: (str(r[1]), str(r[3])))

        for row in all_items:
            tree.insert('', tk.END, values=row,
                        tags=("missing",) if row[7] == 'Not Submitted' else ())

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        # Totals over the de-duplicated list, so the counts match the rows on
        # screen. The column positions moved when "Due" was inserted:
        # submitted is now index 4 and status index 7.
        total_items = len(all_items)
        submitted = sum(1 for item in all_items
                        if len(item) > 4 and item[4] == 'Yes')
        graded = sum(1 for item in all_items
                     if len(item) > 7 and 'Graded' in str(item[7]))
        outstanding = sum(1 for item in all_items
                          if len(item) > 7 and item[7] == 'Not Submitted')

        ttk.Label(summary_frame, text=f"Total items: {total_items}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Submitted: {submitted}").grid(row=0, column=1, padx=10)
        ttk.Label(summary_frame, text=f"Graded: {graded}").grid(row=0, column=2, padx=10)
        ttk.Label(summary_frame,
                  text=f"Not submitted: {outstanding}",
                  foreground="#c0392b" if outstanding else None).grid(
            row=0, column=3, padx=10)

        # Actions
        buttons = ttk.Frame(main_frame)
        buttons.pack(pady=(10, 0))
        ttk.Button(
            buttons,
            text=_t("student_details.btn_send_reminder",
                    default="Send reminder for outstanding work"),
            command=lambda: send_outstanding_reminder(
                self, student_id, first_name, tree)).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text=_t("common.close"),
                   command=grades_window.destroy).pack(side=tk.LEFT, padx=6)

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_grades", error=str(e)))
        if 'grades_window' in locals():
            grades_window.destroy()
