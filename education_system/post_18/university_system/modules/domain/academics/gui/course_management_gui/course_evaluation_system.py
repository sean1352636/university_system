"""
University Course Evaluation System

Students rate courses across 5 fixed criteria
(teaching quality, course content, workload, communication, overall).

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The Student ID is auto-filled from that
identity; there is no in-app login screen.

Persistence: rows live in the central university `student_records.db`.
The course catalog is read from the existing `modules` table; individual
responses are stored in the existing `evaluations` table — its column
set (teaching_quality / course_content / workload / communication /
overall / comments / submitted_at) matches the criteria here exactly.

Note on `evaluations.course_id` — the column is declared INTEGER for a
legacy `courses` table that has since been replaced by `modules`. We
store the textual `module_code` in that column; SQLite's flexible
typing keeps the value as TEXT and equality comparisons against the
same string still match. This file is the only reader/writer of the
table, so the convention is local to this module.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''

    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }

    try:
        from education_system.post_18.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_admin_user(user):
    if not user:
        return False
    return (user.get('role') or '').lower() in ('admin', 'administrator', 'superadmin')


def _resolve_student_identity(user):
    """Return (display_name, student_id) for the logged-in user."""
    if not user:
        return '', ''
    env_user_id = (user.get('user_id') or user.get('id') or '') or ''
    username = user.get('username') or ''
    full_name = ''
    resolved_sid = ''
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        row = None
        if env_user_id:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name "
                "FROM users u LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.id = ?", (env_user_id,)).fetchone()
        if not row and username:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name "
                "FROM users u LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.username = ?", (username,)).fetchone()
        if not row and env_user_id:
            row = cur.execute(
                "SELECT student_id, first_name, last_name FROM students WHERE student_id = ?",
                (env_user_id,)).fetchone()
        conn.close()
        if row:
            sid, first, last = row
            resolved_sid = str(sid or '')
            full_name = ' '.join(p for p in (first or '', last or '') if p).strip()
    except Exception:
        logger.debug("Student identity lookup failed", exc_info=True)

    if not full_name:
        full_name = username or env_user_id or 'Unknown User'
    return full_name, resolved_sid or env_user_id or username or ''


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
class Database:
    """Thin wrapper around the central student_records.db.

    Reuses the existing `modules` table for the catalog and the existing
    `evaluations` table for response storage — no schema changes.
    """

    def __init__(self):
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            self._connect = get_connection
        except Exception:
            logger.exception("Could not import shared get_connection")
            raise

    def get_courses(self):
        """Return [(course_code, course_code, course_name, instructor_or_blank,
        department_or_blank)] from the central ``courses`` table.

        Pre-8.117.91 this read from ``modules`` instead — the dropdown
        was populated with every individual module the catalog seeded
        rather than the actual courses students are enrolled in.
        Now matches the Course Management list / Course Details
        dropdown's shape (any row with non-NULL code and name).
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT COALESCE(course_code, code) AS code, "
                "       COALESCE(course_name, name) AS name, "
                "       COALESCE(department, '')   AS dept "
                "FROM courses "
                "WHERE COALESCE(course_code, code) IS NOT NULL "
                "AND   COALESCE(course_name, name) IS NOT NULL "
                "ORDER BY code"
            ).fetchall()
        finally:
            conn.close()
        # Instructor field stays blank — courses don't carry a single
        # instructor (modules do, but we deliberately moved off the
        # modules catalog). UI tolerates an empty instructor; it just
        # omits the "(<name>)" suffix in the dropdown label.
        return [(code, code, name, "", dept)
                for code, name, dept in rows]

    def submit_evaluation(self, data):
        """Insert an evaluation row.

        `data` is the 9-tuple expected by the existing `evaluations`
        schema: (course_id, student_id, teaching_quality, course_content,
        workload, communication, overall, comments, submitted_at).

        `evaluations.course_id` has a FK to `courses.id`, so before
        inserting we mirror the module into `courses` (idempotent —
        `courses.id` is the PK, INSERT OR IGNORE handles the dedup).
        We also fill the NOT NULL columns (`code`, `name`, `date_added`).

        After the legacy write, we also mirror the response into the
        Evaluation Admin tables (8.117.89) so admin's results dashboard
        sees student submissions.
        """
        conn = self._connect()
        try:
            module_code = data[0]
            row = conn.execute(
                "SELECT module_name FROM modules WHERE module_code = ?",
                (module_code,)).fetchone()
            module_name = (row[0] if row else module_code) or module_code
            conn.execute(
                "INSERT OR IGNORE INTO courses (id, code, name, date_added) "
                "VALUES (?, ?, ?, ?)",
                (module_code, module_code, module_name,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.execute("""
                INSERT INTO evaluations
                (course_id, student_id, teaching_quality, course_content,
                 workload, communication, overall, comments, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()
            logger.info("Submitted course evaluation course=%s student=%s",
                        data[0], data[1])
        finally:
            conn.close()

        # Bridge into Evaluation Admin tables. Failure here mustn't
        # block the legacy write, so anything that goes wrong is
        # logged and swallowed — the user-visible submission still
        # succeeded against the legacy schema.
        try:
            _mirror_to_admin_system(
                module_code=data[0], module_name=module_name,
                student_id=data[1],
                ratings={
                    'teaching_quality': data[2],
                    'course_content':   data[3],
                    'workload':         data[4],
                    'communication':    data[5],
                    'overall':          data[6],
                },
                comments=data[7],
            )
        except Exception:
            logger.exception("Evaluation Admin mirror failed (non-fatal)")

    def get_evaluation_stats(self, course_id):
        conn = self._connect()
        try:
            return conn.execute("""
                SELECT COUNT(*),
                       AVG(teaching_quality), AVG(course_content),
                       AVG(workload), AVG(communication), AVG(overall)
                FROM evaluations WHERE course_id=?
            """, (course_id,)).fetchone()
        finally:
            conn.close()

    def get_evaluations(self, course_id):
        conn = self._connect()
        try:
            return conn.execute("""
                SELECT student_id, teaching_quality, course_content, workload,
                       communication, overall, comments, submitted_at
                FROM evaluations WHERE course_id=? ORDER BY submitted_at DESC
            """, (course_id,)).fetchall()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Bridge to the Evaluation Admin tables (8.117.89)
# ---------------------------------------------------------------------------
#
# This file's legacy ``evaluations`` table is the historical home of
# student responses; the admin GUI in
# ``course_management_gui/course_evaluation_gui.py`` reads from a
# different schema (``course_evaluations`` / ``evaluation_responses`` /
# ``evaluation_answers``). Without a bridge, admin's results dashboard
# would never see a student's submission. The helper below mirrors
# each legacy submission into the admin tables. It bootstraps a
# default 5-criterion template + per-module evaluation lazily; once
# created, subsequent calls are O(few) lookups.

_DEFAULT_TEMPLATE_NAME = "Student Form (auto)"
_CRITERION_TO_QUESTION = [
    # (key in ratings dict, question text, display order)
    ("teaching_quality", "Teaching quality", 0),
    ("course_content",   "Course content",   1),
    ("workload",         "Workload",         2),
    ("communication",    "Communication",    3),
    ("overall",          "Overall",          4),
]


def _ensure_default_template(cursor):
    """Return the template_id of the auto-managed Student Form
    template, creating it (and its 5 questions) on first use."""
    cursor.execute(
        "SELECT template_id FROM evaluation_templates WHERE template_name = ?",
        (_DEFAULT_TEMPLATE_NAME,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO evaluation_templates "
        "(template_name, template_type, description, created_by) "
        "VALUES (?, ?, ?, ?)",
        (_DEFAULT_TEMPLATE_NAME, 'student',
         '5-criterion student form, auto-generated by the main GUI',
         'system'))
    template_id = cursor.lastrowid
    for _key, text, order in _CRITERION_TO_QUESTION:
        cursor.execute(
            "INSERT INTO evaluation_questions "
            "(template_id, question_text, question_type, "
            " scale_min, scale_max, display_order, is_required) "
            "VALUES (?, ?, 'rating', 1, 5, ?, 1)",
            (template_id, text, order))
    return template_id


def _question_id_map(cursor, template_id):
    """Return {criterion_key: question_id} for the default template."""
    out = {}
    cursor.execute(
        "SELECT question_text, question_id FROM evaluation_questions "
        "WHERE template_id = ?", (template_id,))
    text_to_id = {t: qid for t, qid in cursor.fetchall()}
    for key, text, _order in _CRITERION_TO_QUESTION:
        if text in text_to_id:
            out[key] = text_to_id[text]
    return out


def _ensure_module_evaluation(cursor, module_code, template_id):
    """Return the evaluation_id for ``module_code`` under the default
    template, creating it on first use. Date columns are filled with
    sensible defaults — admins can edit later via the admin GUI."""
    cursor.execute(
        "SELECT evaluation_id FROM course_evaluations "
        "WHERE module_code = ? AND template_id = ?",
        (module_code, template_id))
    row = cursor.fetchone()
    if row:
        return row[0]
    today = datetime.now().date()
    start = today.replace(year=today.year)
    cursor.execute(
        "INSERT INTO course_evaluations "
        "(module_code, academic_year, semester, instructor_id, "
        " template_id, start_date, end_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (module_code, str(today.year), 'auto', 'auto',
         template_id, str(start), str(today.replace(year=today.year + 1))))
    return cursor.lastrowid


def _mirror_to_admin_system(module_code, module_name, student_id, ratings, comments):
    """Mirror a legacy-table evaluation into the admin tables. Called
    after Database.submit_evaluation; raises only on programmer errors,
    never blocks the user."""
    from education_system.post_18.university_system.modules.domain.academics.services.evaluation.db_schema import (
        initialize_evaluation_database,
    )
    from education_system.post_18.university_system.infrastructure.database.db import (
        get_connection,
    )
    initialize_evaluation_database()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        template_id = _ensure_default_template(cursor)
        question_ids = _question_id_map(cursor, template_id)
        eval_id = _ensure_module_evaluation(cursor, module_code, template_id)

        cursor.execute(
            "INSERT INTO evaluation_responses "
            "(evaluation_id, student_id, is_complete, is_anonymous, "
            " time_taken_minutes) VALUES (?, ?, 1, 0, ?)",
            (eval_id, student_id, 5))
        response_id = cursor.lastrowid
        for key, qid in question_ids.items():
            value = ratings.get(key)
            if value is None:
                continue
            cursor.execute(
                "INSERT INTO evaluation_answers "
                "(response_id, question_id, answer_value, numeric_value) "
                "VALUES (?, ?, ?, ?)",
                (response_id, qid, str(value), float(value)))
        cursor.execute(
            "UPDATE course_evaluations SET response_count = response_count + 1 "
            "WHERE evaluation_id = ?", (eval_id,))
        conn.commit()
        logger.info(
            "Mirrored evaluation to admin tables: module=%s eval_id=%s "
            "response_id=%s", module_code, eval_id, response_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
class CourseEvaluationApp:
    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip
        # window-chrome. Same shape as Library (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title("University Course Evaluation System")
            # Don't force a small geometry when the host is already sized
            # (the launcher now opens us in a maximised Toplevel).
            try:
                already_sized = (self.root.winfo_width() > 1000
                                 and self.root.winfo_height() > 700)
            except tk.TclError:
                already_sized = False
            if not already_sized:
                self.root.geometry("900x650")
        try:
            self.root.configure(bg="#f0f0f0")
        except tk.TclError:
            pass

        self.user = _get_current_user()
        self.is_admin = _is_admin_user(self.user)
        self.full_name, self.student_id = _resolve_student_identity(self.user)
        self.db = Database()

        self.setup_styles()
        self.create_header()

        if not self.user:
            self._show_no_auth()
            return

        logger.info("Course Evaluation starting user=%s admin=%s",
                    self.full_name, self.is_admin)
        self.create_notebook()

    def _show_no_auth(self):
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=40, pady=60)
        ttk.Label(body, text="🔒 Authentication Required",
                  style="Header.TLabel",
                  font=("Arial", 16, "bold")).pack(pady=(40, 10))
        ttk.Label(body,
                  text="Please launch this module from the main\n"
                       "University System after signing in.",
                  justify="center").pack(pady=10)
        ttk.Button(body, text="Close",
                   command=self.root.destroy).pack(pady=20)

    def setup_styles(self):
        # ttk.Style is process-global. When this app embeds inside the
        # main GUI workspace (admin path: Dashboard → Course Evaluation),
        # configuring base style names (TNotebook, TFrame, TLabel, etc.)
        # bleeds out and recolours every widget in the host. Only named
        # styles are safe here.
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Arial", 11, "bold"),
                        foreground="#000000")

    def create_header(self):
        # 8.117.69 — flattened to clam-default neutrals to match
        # the main GUI. Pre-8.117.69 the header was navy (#1a365d)
        # with white text on a pale-blue (#f0f4f8) body.
        header = tk.Frame(self.root, bg="#f0f0f0", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🎓 University Course Evaluation System",
                 font=("Arial", 18, "bold"), bg="#f0f0f0", fg="#000000"
                 ).pack(side="left", padx=20, pady=18)
        if self.user:
            tk.Label(header,
                     text=f"👤 {self.full_name}  ({self.student_id})",
                     font=("Arial", 10), bg="#f0f0f0", fg="#555555"
                     ).pack(side="right", padx=20, pady=22)
        if self.is_admin:
            tk.Button(header, text="Operations…", bg="#f0f0f0",
                      command=self._launch_operations
                      ).pack(side="right", padx=4, pady=20)
            tk.Button(header, text="Survey Designer…", bg="#f0f0f0",
                      command=self._launch_designer
                      ).pack(side="right", padx=4, pady=20)

    def _launch_designer(self):
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_designer import (
                launch_survey_designer,
            )
        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror("Survey Designer", str(e))
            return
        launch_survey_designer(self.root, getattr(self, "auth", None))

    def _launch_operations(self):
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_operations import (
                launch_operations_gui,
            )
        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror("Operations", str(e))
            return
        launch_operations_gui(self.root, getattr(self, "auth", None))

    def create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        self.eval_frame = ttk.Frame(self.notebook)
        self.results_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.eval_frame, text="  Submit Evaluation  ")
        self.notebook.add(self.results_frame, text="  View Results  ")

        self.build_eval_tab()
        self.build_results_tab()

    # ---------- Evaluation Tab ----------
    def build_eval_tab(self):
        container = ttk.Frame(self.eval_frame)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Identity row — read-only, sourced from the logged-in user.
        ttk.Label(container, text="Submitting as:",
                  style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(container,
                  text=f"{self.full_name}  ({self.student_id})"
                       if self.student_id
                       else self.full_name,
                  font=("Arial", 10)).grid(row=0, column=1, sticky="w",
                                            pady=5, padx=10)

        # Course selection
        ttk.Label(container, text="Select Course:",
                  style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        self.course_combo = ttk.Combobox(container, width=50,
                                          font=("Arial", 10), state="readonly")
        self.course_combo.grid(row=1, column=1, sticky="w", pady=5, padx=10)
        self.refresh_course_combo()

        # Rating section
        ratings_frame = ttk.LabelFrame(
            container, text=" Rate the Course (1 = Poor, 5 = Excellent) ",
            padding=15)
        ratings_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=15)

        self.rating_vars = {}
        categories = [
            ("teaching_quality", "Teaching Quality"),
            ("course_content", "Course Content"),
            ("workload", "Workload Balance"),
            ("communication", "Instructor Communication"),
            ("overall", "Overall Satisfaction"),
        ]
        for i, (key, label) in enumerate(categories):
            ttk.Label(ratings_frame, text=label + ":").grid(
                row=i, column=0, sticky="w", pady=6)
            var = tk.IntVar(value=3)
            self.rating_vars[key] = var
            scale_frame = ttk.Frame(ratings_frame)
            scale_frame.grid(row=i, column=1, sticky="w", padx=20)
            for val in range(1, 6):
                ttk.Radiobutton(scale_frame, text=str(val), variable=var,
                                value=val).pack(side="left", padx=5)

        ttk.Label(container, text="Comments (optional):",
                  style="Header.TLabel").grid(row=3, column=0, sticky="nw",
                                                pady=5)
        self.comments_text = tk.Text(container, width=55, height=5,
                                     font=("Arial", 10), wrap="word")
        self.comments_text.grid(row=3, column=1, sticky="w", pady=5, padx=10)

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit Evaluation",
                   command=self.submit_evaluation
                   ).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Clear Form", command=self.clear_form
                   ).pack(side="left", padx=10)

    def refresh_course_combo(self):
        courses = self.db.get_courses()
        self.course_map = {f"{c[1]} - {c[2]}"
                            + (f" ({c[3]})" if c[3] else ""): c[0]
                           for c in courses}
        self.course_combo["values"] = list(self.course_map.keys())
        if courses:
            self.course_combo.current(0)

    def submit_evaluation(self):
        course_selection = self.course_combo.get()
        if not course_selection:
            messagebox.showwarning("Missing Info", "Please select a course.")
            return
        if not self.student_id:
            messagebox.showerror(
                "Identity Error",
                "Could not determine your student ID from the logged-in user. "
                "Please relaunch from the main system.")
            return

        course_id = self.course_map[course_selection]
        comments = self.comments_text.get("1.0", "end-1c").strip()

        data = (
            course_id, self.student_id,
            self.rating_vars["teaching_quality"].get(),
            self.rating_vars["course_content"].get(),
            self.rating_vars["workload"].get(),
            self.rating_vars["communication"].get(),
            self.rating_vars["overall"].get(),
            comments,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        try:
            self.db.submit_evaluation(data)
        except sqlite3.Error as e:
            messagebox.showerror("Save Error", f"Could not save evaluation: {e}")
            return
        messagebox.showinfo("Success",
                            "Thank you! Your evaluation has been submitted.")
        self.clear_form()
        self.refresh_results()

    def clear_form(self):
        self.comments_text.delete("1.0", "end")
        for var in self.rating_vars.values():
            var.set(3)

    # ---------- Results Tab ----------
    def build_results_tab(self):
        container = ttk.Frame(self.results_frame)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        top = ttk.Frame(container)
        top.pack(fill="x", pady=5)
        ttk.Label(top, text="Select Course:",
                  style="Header.TLabel").pack(side="left")
        self.results_combo = ttk.Combobox(top, width=50,
                                           font=("Arial", 10), state="readonly")
        self.results_combo.pack(side="left", padx=10)
        self.results_combo.bind("<<ComboboxSelected>>",
                                lambda e: self.show_course_results())
        ttk.Button(top, text="Refresh",
                   command=self.refresh_results).pack(side="left", padx=5)

        self.stats_frame = ttk.LabelFrame(container, text=" Statistics ",
                                          padding=15)
        self.stats_frame.pack(fill="x", pady=10)
        self.stats_label = ttk.Label(self.stats_frame,
                                     text="Select a course to view statistics.",
                                     font=("Arial", 10))
        self.stats_label.pack(anchor="w")

        list_frame = ttk.LabelFrame(container,
                                    text=" Individual Evaluations ", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)

        columns = ("student", "teaching", "content", "workload", "comm",
                   "overall", "date")
        self.tree = ttk.Treeview(list_frame, columns=columns,
                                 show="headings", height=10)
        headings = [
            ("student", "Student ID", 100),
            ("teaching", "Teaching", 80),
            ("content", "Content", 80),
            ("workload", "Workload", 80),
            ("comm", "Communication", 110),
            ("overall", "Overall", 70),
            ("date", "Date", 140),
        ]
        for col, label, width in headings:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")

        scroll = ttk.Scrollbar(list_frame, orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.show_comment)

        self.comment_label = ttk.Label(container,
                                       text="Click a row to view comments.",
                                       font=("Arial", 9, "italic"),
                                       wraplength=800)
        self.comment_label.pack(fill="x", pady=5)

        self.refresh_results()

    def refresh_results(self):
        courses = self.db.get_courses()
        self.results_map = {f"{c[1]} - {c[2]}": c[0] for c in courses}
        self.results_combo["values"] = list(self.results_map.keys())
        if courses and not self.results_combo.get():
            self.results_combo.current(0)
        if self.results_combo.get():
            self.show_course_results()

    def show_course_results(self):
        selection = self.results_combo.get()
        if not selection:
            return
        course_id = self.results_map[selection]

        stats = self.db.get_evaluation_stats(course_id)
        count = stats[0]
        if count == 0:
            self.stats_label.config(
                text="No evaluations submitted yet for this course.")
        else:
            text = (
                f"Total Evaluations: {count}\n"
                f"Teaching Quality: {stats[1]:.2f} / 5.0\n"
                f"Course Content: {stats[2]:.2f} / 5.0\n"
                f"Workload Balance: {stats[3]:.2f} / 5.0\n"
                f"Communication: {stats[4]:.2f} / 5.0\n"
                f"Overall Satisfaction: {stats[5]:.2f} / 5.0"
            )
            self.stats_label.config(text=text)

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.evaluations_cache = self.db.get_evaluations(course_id)
        for ev in self.evaluations_cache:
            self.tree.insert("", "end",
                             values=(ev[0], ev[1], ev[2], ev[3],
                                     ev[4], ev[5], ev[7]))

    def show_comment(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        index = self.tree.index(selection[0])
        if index < len(self.evaluations_cache):
            comment = self.evaluations_cache[index][6]
            if comment:
                self.comment_label.config(text=f"💬 Comment: {comment}")
            else:
                self.comment_label.config(text="💬 No comment provided.")


if __name__ == "__main__":
    root = tk.Tk()
    app = CourseEvaluationApp(root)
    root.mainloop()
