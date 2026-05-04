"""
University Module Evaluation Survey Portal

Students rate modules against a fixed Likert-scale questionnaire.
Admins can view aggregate response data.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The app dispatches straight to the survey
flow; there is no in-app login screen.

Persistence: rows live in the central university `student_records.db`.
The portal uses the existing `evaluation_forms`, `eval_form_questions`,
`eval_form_responses`, and `eval_form_answers` tables — exactly the
shape the survey needs — and reads the module catalog from `modules`.
On first use of a module within an academic year, an `evaluation_forms`
row is lazily created and seeded with the standard question set.
"""

import hashlib
import json
import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext

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
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
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
        from education_system.university_system.infrastructure.auth import get_global_auth
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
        from education_system.university_system.infrastructure.database.db import get_connection
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


def _student_hash(student_id):
    """SHA-256 of the student_id — matches the `eval_form_responses.
    student_hash` column's anonymization intent.
    """
    return hashlib.sha256((student_id or '').encode('utf-8')).hexdigest()


def _current_academic_year():
    """UK-style academic year string for today, e.g. '2025/2026'.

    Sept onwards rolls into the next year; before Sept stays in the
    previous year's intake.
    """
    now = datetime.now()
    if now.month >= 9:
        return f"{now.year}/{now.year + 1}"
    return f"{now.year - 1}/{now.year}"


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
LIKERT_OPTIONS = [
    "Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree",
]
LIKERT_VALUES = {label: i + 1 for i, label in enumerate(LIKERT_OPTIONS)}

LIKERT_QUESTIONS = [
    "The module learning objectives were clearly explained.",
    "The content was well-structured and organised.",
    "The lecturer was knowledgeable and engaging.",
    "Assessment methods were fair and appropriate.",
    "Feedback on assignments was timely and helpful.",
    "The workload was reasonable for the credits awarded.",
    "Learning resources (materials, readings) were useful.",
    "I would recommend this module to other students.",
]

OVERALL_QUESTION = "Overall Module Rating (1 = Poor, 5 = Excellent)"
COMMENTS_QUESTION = "Additional Comments"


class Database:
    """Thin wrapper around the central student_records.db.

    All schema is reused as-is — this class assumes the canonical
    education_system tables exist and only ever inserts/reads from them.
    """

    def __init__(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            self._connect = get_connection
        except Exception:
            logger.exception("Could not import shared get_connection")
            raise

    def get_modules(self):
        """Return [(module_code, module_name)] for all active modules."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT module_code, module_name FROM modules "
                "WHERE COALESCE(is_active, 1) = 1 "
                "ORDER BY module_code"
            ).fetchall()
        finally:
            conn.close()
        return rows

    def get_or_create_form(self, module_code, module_name, created_by):
        """Return the evaluation_forms.id for (module, current academic year),
        creating the form + the standard question set on first use.
        """
        academic_year = _current_academic_year()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id FROM evaluation_forms "
                "WHERE module_code = ? AND academic_year = ?",
                (module_code, academic_year)).fetchone()
            if row:
                return row[0]

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = conn.execute(
                "INSERT INTO evaluation_forms "
                "(module_code, module_name, academic_year, semester, status, "
                " created_by, created_at, is_anonymous) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (module_code, module_name, academic_year, '', 'open',
                 created_by or '', now, 1))
            form_id = cur.lastrowid

            order = 1
            for text in LIKERT_QUESTIONS:
                conn.execute(
                    "INSERT INTO eval_form_questions "
                    "(form_id, question_text, question_type, options, "
                    " display_order, is_required) VALUES (?,?,?,?,?,?)",
                    (form_id, text, 'likert', json.dumps(LIKERT_OPTIONS),
                     order, 1))
                order += 1
            conn.execute(
                "INSERT INTO eval_form_questions "
                "(form_id, question_text, question_type, options, "
                " display_order, is_required) VALUES (?,?,?,?,?,?)",
                (form_id, OVERALL_QUESTION, 'rating',
                 json.dumps([1, 2, 3, 4, 5]), order, 1))
            order += 1
            conn.execute(
                "INSERT INTO eval_form_questions "
                "(form_id, question_text, question_type, options, "
                " display_order, is_required) VALUES (?,?,?,?,?,?)",
                (form_id, COMMENTS_QUESTION, 'text', None, order, 0))

            conn.commit()
            logger.info("Created evaluation form id=%s for %s (%s)",
                        form_id, module_code, academic_year)
            return form_id
        finally:
            conn.close()

    def get_form_questions(self, form_id):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT id, question_text, question_type, options, is_required "
                "FROM eval_form_questions WHERE form_id = ? "
                "ORDER BY display_order", (form_id,)).fetchall()
        finally:
            conn.close()

    def has_responded(self, form_id, student_id):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT 1 FROM eval_form_responses "
                "WHERE form_id = ? AND student_hash = ?",
                (form_id, _student_hash(student_id))).fetchone() is not None
        finally:
            conn.close()

    def submit_response(self, form_id, student_id, answers):
        """Insert a response row plus one answer row per question.

        `answers` is {question_id: (rating_value or None, text_value or None)}.
        Wrapped in a single transaction so a partial submit can't land.
        """
        conn = self._connect()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = conn.execute(
                "INSERT INTO eval_form_responses "
                "(form_id, student_hash, submitted_at) VALUES (?,?,?)",
                (form_id, _student_hash(student_id), now))
            response_id = cur.lastrowid
            for qid, (rating, text) in answers.items():
                conn.execute(
                    "INSERT INTO eval_form_answers "
                    "(response_id, question_id, rating_value, text_value) "
                    "VALUES (?,?,?,?)",
                    (response_id, qid, rating, text))
            conn.commit()
            logger.info("Submitted response id=%s form=%s", response_id, form_id)
            return response_id
        except sqlite3.Error:
            conn.rollback()
            logger.exception("Failed to submit response form=%s", form_id)
            raise
        finally:
            conn.close()

    def get_all_submissions(self):
        """For admin viewing — returns rows joined across forms/responses/
        answers/questions. Comments and answer text live alongside
        rating_value so the admin display can present them coherently.
        """
        conn = self._connect()
        try:
            forms = conn.execute(
                "SELECT f.id, f.module_code, f.module_name, f.academic_year, "
                "       COUNT(r.id), AVG(CASE WHEN q.question_type = 'rating' "
                "                              THEN a.rating_value END) "
                "FROM evaluation_forms f "
                "LEFT JOIN eval_form_responses r ON r.form_id = f.id "
                "LEFT JOIN eval_form_answers a   ON a.response_id = r.id "
                "LEFT JOIN eval_form_questions q ON q.id = a.question_id "
                "GROUP BY f.id ORDER BY f.module_code"
            ).fetchall()
        finally:
            conn.close()
        return forms

    def get_responses_for_form(self, form_id):
        conn = self._connect()
        try:
            responses = conn.execute(
                "SELECT id, student_hash, submitted_at "
                "FROM eval_form_responses WHERE form_id = ? "
                "ORDER BY submitted_at DESC", (form_id,)).fetchall()
            answers = conn.execute(
                "SELECT a.response_id, q.question_text, q.question_type, "
                "       a.rating_value, a.text_value "
                "FROM eval_form_answers a "
                "JOIN eval_form_questions q ON q.id = a.question_id "
                "WHERE q.form_id = ? "
                "ORDER BY a.response_id, q.display_order", (form_id,)).fetchall()
        finally:
            conn.close()
        return responses, answers


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
class ModuleEvaluationPortal:
    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip
        # window-chrome. Same shape Library uses (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title("University Module Evaluation Portal")
            self.root.geometry("800x700")
        try:
            self.root.configure(bg="#f0f0f0")
        except tk.TclError:
            pass

        self.user = _get_current_user()
        self.is_admin = _is_admin_user(self.user)
        full_name, student_id = _resolve_student_identity(self.user)
        self.full_name = full_name
        self.student_id = student_id

        self.db = Database()
        self.current_module = None
        self.current_form_id = None
        self.question_widgets = []

        self.setup_styles()

        if not self.user:
            self.show_no_auth_screen()
        else:
            logger.info("Module Evaluation starting user=%s admin=%s",
                        full_name, self.is_admin)
            self.show_module_selection()

    def setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 20, "bold"),
                        background="#f0f0f0", foreground="#000000")
        style.configure("Heading.TLabel", font=("Helvetica", 14, "bold"),
                        background="#f0f0f0", foreground="#000000")
        style.configure("Body.TLabel", font=("Helvetica", 11),
                        background="#f0f0f0", foreground="#000000")
        style.configure("Primary.TButton", font=("Helvetica", 11, "bold"),
                        padding=10)

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ---------- NO AUTH FALLBACK ----------
    def show_no_auth_screen(self):
        self.clear_window()
        container = tk.Frame(self.root, bg="#f0f0f0")
        container.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(container, text="🔒 Authentication Required",
                  style="Title.TLabel").pack(pady=(0, 10))
        ttk.Label(container,
                  text="Please launch this module from the\n"
                       "main University System after signing in.",
                  style="Body.TLabel", justify="center").pack(pady=10)
        ttk.Button(container, text="Close", style="Primary.TButton",
                   command=self.root.destroy).pack(pady=20)

    # ---------- MODULE SELECTION ----------
    def show_module_selection(self):
        self.clear_window()

        header = tk.Frame(self.root, bg="#f0f0f0", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=f"Welcome, {self.full_name}",
                 font=("Helvetica", 14, "bold"),
                 bg="#f0f0f0", fg="#000000").pack(side="left", padx=20, pady=20)

        if self.is_admin:
            ttk.Button(header, text="View Submissions",
                       command=self.view_submissions).pack(
                           side="right", padx=20, pady=20)

        body = tk.Frame(self.root, bg="#f0f0f0")
        body.pack(fill="both", expand=True, padx=40, pady=30)

        ttk.Label(body, text="Select a Module to Evaluate",
                  style="Title.TLabel").pack(pady=(0, 20))
        ttk.Label(body,
                  text="Choose the module you wish to provide feedback for:",
                  style="Body.TLabel").pack(pady=(0, 15))

        modules = self.db.get_modules()
        if not modules:
            ttk.Label(body,
                      text="No modules are listed in the catalog yet.\n"
                           "Please contact an administrator.",
                      style="Body.TLabel", justify="center").pack(pady=40)
            return

        self._modules = modules
        module_options = [f"{code} — {name}" for code, name in modules]
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(body, textvariable=self.module_var,
                                    values=module_options, state="readonly",
                                    width=60, font=("Helvetica", 11))
        module_combo.pack(pady=10)
        module_combo.current(0)

        ttk.Button(body, text="Start Evaluation →",
                   style="Primary.TButton",
                   command=self.start_evaluation).pack(pady=30)

    def start_evaluation(self):
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module.")
            return
        code = selected.split(" — ", 1)[0]
        name = next((n for c, n in self._modules if c == code), code)
        self.current_module = {"code": code, "name": name}

        try:
            form_id = self.db.get_or_create_form(
                code, name, created_by=self.user.get('username', ''))
        except Exception as e:
            logger.exception("Could not load/create form for %s", code)
            messagebox.showerror("Database Error",
                                 f"Could not prepare the evaluation form: {e}")
            return

        if self.db.has_responded(form_id, self.student_id):
            messagebox.showinfo(
                "Already Submitted",
                "You have already submitted an evaluation for this module "
                "this academic year. Each student may submit once per module.")
            return

        self.current_form_id = form_id
        self.show_evaluation_form()

    # ---------- EVALUATION FORM ----------
    def show_evaluation_form(self):
        self.clear_window()

        header = tk.Frame(self.root, bg="#f0f0f0", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header,
                 text=f"Evaluating: {self.current_module['code']} — "
                      f"{self.current_module['name']}",
                 font=("Helvetica", 13, "bold"),
                 bg="#f0f0f0", fg="#000000", wraplength=700
                 ).pack(side="left", padx=20, pady=20)

        canvas = tk.Canvas(self.root, bg="#f0f0f0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical",
                                  command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#f0f0f0")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True,
                    padx=(30, 0), pady=20)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        ttk.Label(scroll_frame, text="Please rate the following statements:",
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 15))

        questions = self.db.get_form_questions(self.current_form_id)
        self.question_widgets = []  # list of (qid, qtype, var_or_widget)

        for qid, qtext, qtype, options_json, _required in questions:
            if qtype == 'likert':
                var = self._build_likert(scroll_frame, qtext)
                self.question_widgets.append((qid, qtype, var))
            elif qtype == 'rating':
                var = self._build_rating(scroll_frame, qtext)
                self.question_widgets.append((qid, qtype, var))
            elif qtype == 'text':
                widget = self._build_text(scroll_frame, qtext)
                self.question_widgets.append((qid, qtype, widget))
            else:
                logger.warning("Unknown question_type %r — skipping", qtype)

        btn_frame = tk.Frame(scroll_frame, bg="#f0f0f0")
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="← Back", style="Primary.TButton",
                   command=self.show_module_selection
                   ).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Submit Evaluation",
                   style="Primary.TButton",
                   command=self.submit_evaluation
                   ).pack(side="left", padx=5)

    def _build_likert(self, parent, qtext):
        q_frame = tk.Frame(parent, bg="white", relief="flat", bd=1)
        q_frame.pack(fill="x", pady=8, padx=5)
        tk.Label(q_frame, text=qtext, font=("Helvetica", 11, "bold"),
                 bg="white", fg="#000000", wraplength=650, justify="left"
                 ).pack(anchor="w", padx=15, pady=(12, 8))
        var = tk.StringVar(value="")
        options_frame = tk.Frame(q_frame, bg="white")
        options_frame.pack(anchor="w", padx=15, pady=(0, 12))
        for option in LIKERT_OPTIONS:
            tk.Radiobutton(options_frame, text=option, variable=var,
                           value=option, bg="white", font=("Helvetica", 10),
                           activebackground="white", selectcolor="#e6f0ff"
                           ).pack(side="left", padx=4)
        return var

    def _build_rating(self, parent, qtext):
        rating_frame = tk.Frame(parent, bg="white", bd=1)
        rating_frame.pack(fill="x", pady=15, padx=5)
        tk.Label(rating_frame, text=qtext + ":",
                 font=("Helvetica", 11, "bold"),
                 bg="white", fg="#000000"
                 ).pack(anchor="w", padx=15, pady=(12, 8))
        var = tk.IntVar(value=0)
        buttons = tk.Frame(rating_frame, bg="white")
        buttons.pack(anchor="w", padx=15, pady=(0, 12))
        for i in range(1, 6):
            tk.Radiobutton(buttons, text=f"★ {i}", variable=var, value=i,
                           bg="white", font=("Helvetica", 11),
                           activebackground="white", selectcolor="#fff9db"
                           ).pack(side="left", padx=8)
        return var

    def _build_text(self, parent, qtext):
        comments_frame = tk.Frame(parent, bg="white", bd=1)
        comments_frame.pack(fill="x", pady=15, padx=5)
        tk.Label(comments_frame, text=f"{qtext} (optional):",
                 font=("Helvetica", 11, "bold"),
                 bg="white", fg="#000000"
                 ).pack(anchor="w", padx=15, pady=(12, 8))
        widget = scrolledtext.ScrolledText(comments_frame, height=5,
                                           font=("Helvetica", 10), wrap="word")
        widget.pack(fill="x", padx=15, pady=(0, 12))
        return widget

    def submit_evaluation(self):
        answers = {}
        for qid, qtype, holder in self.question_widgets:
            if qtype == 'likert':
                value = holder.get()
                if not value:
                    messagebox.showwarning(
                        "Incomplete Form",
                        "Please answer all rating questions before submitting.")
                    return
                answers[qid] = (LIKERT_VALUES[value], value)
            elif qtype == 'rating':
                value = holder.get()
                if value == 0:
                    messagebox.showwarning("Incomplete Form",
                                           "Please provide an overall rating.")
                    return
                answers[qid] = (value, str(value))
            elif qtype == 'text':
                text = holder.get("1.0", "end").strip()
                answers[qid] = (None, text or None)

        if not messagebox.askyesno(
                "Confirm Submission",
                "Are you sure you want to submit? You cannot edit after submission."):
            return

        try:
            self.db.submit_response(self.current_form_id, self.student_id, answers)
        except sqlite3.Error as e:
            messagebox.showerror("Save Error", f"Could not save response: {e}")
            return

        self.show_thank_you()

    # ---------- THANK YOU ----------
    def show_thank_you(self):
        self.clear_window()
        container = tk.Frame(self.root, bg="#f0f0f0")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(container, text="✓",
                 font=("Helvetica", 60, "bold"),
                 bg="#f0f0f0", fg="#38a169").pack()
        ttk.Label(container, text="Thank You!",
                  style="Title.TLabel").pack(pady=10)
        ttk.Label(container,
                  text="Your evaluation has been submitted successfully.",
                  style="Body.TLabel").pack(pady=5)
        ttk.Label(container,
                  text="Your feedback helps us improve teaching and learning.",
                  style="Body.TLabel").pack(pady=5)

        btn_frame = tk.Frame(container, bg="#f0f0f0")
        btn_frame.pack(pady=30)
        ttk.Button(btn_frame, text="Evaluate Another Module",
                   style="Primary.TButton",
                   command=self.show_module_selection
                   ).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close",
                   style="Primary.TButton",
                   command=self.root.destroy
                   ).pack(side="left", padx=5)

    # ---------- VIEW SUBMISSIONS (Admin) ----------
    def view_submissions(self):
        if not self.is_admin:
            return  # button isn't shown for non-admins, but guard anyway

        forms = self.db.get_all_submissions()
        forms = [f for f in forms if f[4]]  # drop forms with zero responses
        if not forms:
            messagebox.showinfo("No Data",
                                "No submissions have been recorded yet.")
            return

        win = tk.Toplevel(self.root)
        win.title("Submitted Evaluations")
        win.geometry("820x600")
        win.configure(bg="#f0f0f0")

        tk.Label(win,
                 text=f"Module Evaluations — {len(forms)} module(s) with responses",
                 font=("Helvetica", 16, "bold"),
                 bg="#f0f0f0", fg="#000000").pack(pady=15)

        text_area = scrolledtext.ScrolledText(win, font=("Courier", 10),
                                              wrap="word", bg="white")
        text_area.pack(fill="both", expand=True, padx=20, pady=10)

        for fid, code, name, year, count, avg in forms:
            text_area.insert("end", "=" * 70 + "\n")
            text_area.insert("end", f"{code} — {name}\n")
            text_area.insert("end", f"Academic Year: {year}\n")
            text_area.insert("end", f"Responses: {count}   "
                                    f"Avg overall: {avg:.2f}/5\n\n"
                             if avg is not None
                             else f"Responses: {count}   Avg overall: —\n\n")

            responses, answers = self.db.get_responses_for_form(fid)
            by_response = {}
            for resp_id, qtext, qtype, rating, text in answers:
                by_response.setdefault(resp_id, []).append(
                    (qtext, qtype, rating, text))

            for i, (resp_id, _hash, submitted_at) in enumerate(responses, 1):
                text_area.insert("end", f"  Response #{i}  |  {submitted_at}\n")
                for qtext, qtype, rating, text in by_response.get(resp_id, []):
                    if qtype == 'likert':
                        text_area.insert("end",
                                         f"    {qtext}\n      → {text} ({rating}/5)\n")
                    elif qtype == 'rating':
                        text_area.insert("end",
                                         f"    {qtext}\n      → {rating}/5\n")
                    elif qtype == 'text' and text:
                        text_area.insert("end",
                                         f"    {qtext}\n      → {text}\n")
                text_area.insert("end", "\n")
            text_area.insert("end", "\n")

        text_area.configure(state="disabled")


def main():
    root = tk.Tk()
    ModuleEvaluationPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
