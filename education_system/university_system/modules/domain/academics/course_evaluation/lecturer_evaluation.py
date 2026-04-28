"""
University Lecturer/Instructor Evaluation System

Students evaluate lecturers; admins view aggregated reports.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The app dispatches straight to the student
or admin dashboard based on that role; there is no in-app login screen.

Persistence: rows live in the central university `student_records.db`.
The app reuses the existing `lecturers` and `modules` tables for the
directory data, and adds a single `lecturer_evaluations` table (none of
the existing evaluation tables match the 7-criterion lecturer schema).
"""

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
    """Resolve the logged-in user dict from EDU_AUTH_* env vars.

    Mirrors the pattern used by complaints_portal.py — the main GUI sets
    these env vars on subprocess launch, so we read them directly to
    avoid silent failures inside the auth-infra import chain.
    """
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
    """Return (display_name, student_id) for the logged-in user.

    Looks up the student row in `students` joined to `users` so we get
    the student-facing student_id (e.g. S12345) rather than the auth PK.
    Falls back to env values when the DB lookup misses.
    """
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


# ---------------------------------------------------------------------------
# DATABASE LAYER
# ---------------------------------------------------------------------------
_LECTURER_EVALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lecturer_evaluations (
    evaluation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT    NOT NULL,
    module_code     TEXT    NOT NULL,
    lecturer_id     INTEGER NOT NULL,
    knowledge       INTEGER NOT NULL,
    communication   INTEGER NOT NULL,
    preparation     INTEGER NOT NULL,
    engagement      INTEGER NOT NULL,
    fairness        INTEGER NOT NULL,
    availability    INTEGER NOT NULL,
    overall         INTEGER NOT NULL,
    comments        TEXT,
    submitted_at    TEXT    NOT NULL,
    FOREIGN KEY (lecturer_id) REFERENCES lecturers(lecturer_id),
    UNIQUE(student_id, module_code, lecturer_id)
)
"""


class Database:
    """Wraps queries against the central student_records.db.

    The app no longer owns its own SQLite file — it uses the shared
    `get_connection()` from the university infrastructure, so it sees
    the same `lecturers`, `modules`, `users`, and `students` data as
    every other module. The only table this app introduces is
    `lecturer_evaluations` (idempotently created on init).
    """

    def __init__(self):
        self._connect = self._build_connector()
        self._ensure_schema()

    def _build_connector(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            return get_connection
        except Exception:
            logger.exception("Could not import shared get_connection")
            raise

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(_LECTURER_EVALS_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # -- lecturers ----------------------------------------------------------
    def get_lecturers(self):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT lecturer_id, full_name, department, email, title "
                "FROM lecturers ORDER BY full_name"
            ).fetchall()
        finally:
            conn.close()

    def add_lecturer(self, name, dept, email, title):
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO lecturers (full_name, department, email, title) "
                "VALUES (?,?,?,?)", (name, dept, email, title))
            conn.commit()
            logger.info("Added lecturer %s", name)
        finally:
            conn.close()

    # -- modules (acting as "courses") --------------------------------------
    def get_modules(self):
        """Return modules from the central catalog.

        Tuple shape mirrors what the UI used to receive for courses:
        (module_code, module_code_display, module_name, department, semester).
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT module_code, module_name, "
                "       COALESCE(department, ''), "
                "       COALESCE(semester, '') || "
                "         CASE WHEN year IS NOT NULL AND year <> '' "
                "              THEN ' ' || year ELSE '' END "
                "FROM modules "
                "WHERE COALESCE(is_active, 1) = 1 "
                "ORDER BY module_code"
            ).fetchall()
        finally:
            conn.close()
        return rows

    # -- evaluations --------------------------------------------------------
    def has_evaluated(self, student_id, module_code, lecturer_id):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT 1 FROM lecturer_evaluations "
                "WHERE student_id=? AND module_code=? AND lecturer_id=?",
                (student_id, module_code, lecturer_id)).fetchone() is not None
        finally:
            conn.close()

    def evaluated_module_codes(self, student_id):
        """Set of module_codes the student has submitted at least one
        evaluation for. Used to mark the dashboard as 'Evaluated'.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT module_code FROM lecturer_evaluations WHERE student_id=?",
                (student_id,)).fetchall()
        finally:
            conn.close()
        return {r[0] for r in rows}

    def submit_evaluation(self, data):
        try:
            conn = self._connect()
            try:
                conn.execute("""
                    INSERT INTO lecturer_evaluations
                        (student_id, module_code, lecturer_id,
                         knowledge, communication, preparation, engagement,
                         fairness, availability, overall, comments, submitted_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, data)
                conn.commit()
            finally:
                conn.close()
            logger.info("Submitted evaluation student=%s module=%s lecturer=%s",
                        data[0], data[1], data[2])
            return True, "Evaluation submitted successfully."
        except sqlite3.IntegrityError:
            return False, "You have already evaluated this lecturer for this module."

    # -- reports ------------------------------------------------------------
    def get_lecturer_report(self, lecturer_id):
        conn = self._connect()
        try:
            return conn.execute("""
                SELECT COUNT(*),
                       AVG(knowledge), AVG(communication), AVG(preparation),
                       AVG(engagement), AVG(fairness),     AVG(availability),
                       AVG(overall)
                FROM lecturer_evaluations
                WHERE lecturer_id = ?
            """, (lecturer_id,)).fetchone()
        finally:
            conn.close()

    def get_lecturer_comments(self, lecturer_id):
        conn = self._connect()
        try:
            return conn.execute("""
                SELECT module_code, comments, submitted_at
                FROM lecturer_evaluations
                WHERE lecturer_id = ?
                  AND comments IS NOT NULL AND TRIM(comments) <> ''
                ORDER BY submitted_at DESC
            """, (lecturer_id,)).fetchall()
        finally:
            conn.close()

    def get_all_lecturer_summaries(self):
        conn = self._connect()
        try:
            return conn.execute("""
                SELECT l.lecturer_id, l.full_name, l.department, l.title,
                       COUNT(e.evaluation_id), AVG(e.overall)
                FROM lecturers l
                LEFT JOIN lecturer_evaluations e ON l.lecturer_id = e.lecturer_id
                GROUP BY l.lecturer_id
                ORDER BY l.full_name
            """).fetchall()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# UI THEME
# ---------------------------------------------------------------------------
class Theme:
    PRIMARY     = "#1e3a5f"
    SECONDARY   = "#2d6a9f"
    ACCENT      = "#c9a961"
    SUCCESS     = "#2d8659"
    DANGER      = "#b84242"
    BG          = "#f4f1ea"
    CARD        = "#ffffff"
    TEXT        = "#1a1a1a"
    TEXT_MUTED  = "#666666"
    BORDER      = "#d0cabf"

    FONT_TITLE   = ("Georgia", 22, "bold")
    FONT_HEADING = ("Georgia", 14, "bold")
    FONT_BODY    = ("Segoe UI", 10)
    FONT_BOLD    = ("Segoe UI", 10, "bold")
    FONT_SMALL   = ("Segoe UI", 9)


# ---------------------------------------------------------------------------
# STUDENT DASHBOARD
# ---------------------------------------------------------------------------
class StudentDashboard:
    def __init__(self, root, db, full_name, student_id):
        self.root = root
        self.db = db
        self.full_name = full_name
        self.student_id = student_id

        for w in root.winfo_children():
            w.destroy()

        root.title(f"Student Portal - {self.full_name}")
        root.geometry("1000x680")
        root.configure(bg=Theme.BG)
        root.resizable(True, True)

        self.build_ui()
        self.load_modules()

    def build_ui(self):
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎓  Lecturer Evaluation",
                 bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(side="left", padx=25, pady=18)
        tk.Label(header, text=f"👤  {self.full_name}  ({self.student_id})",
                 bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_BODY).pack(side="right", padx=25, pady=22)

        body = tk.Frame(self.root, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(body, text="Your Modules — Evaluate Your Lecturers",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w")
        tk.Label(body,
                 text="Select a module below and choose the lecturer you wish to evaluate. "
                      "Your feedback helps improve teaching quality.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w", pady=(2, 15))

        table_frame = tk.Frame(body, bg=Theme.CARD,
                               highlightbackground=Theme.BORDER, highlightthickness=1)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=Theme.CARD, fieldbackground=Theme.CARD,
                        foreground=Theme.TEXT, rowheight=32,
                        font=Theme.FONT_BODY, borderwidth=0)
        style.configure("Treeview.Heading",
                        background=Theme.PRIMARY, foreground="white",
                        font=Theme.FONT_BOLD, relief="flat", padding=8)
        style.map("Treeview", background=[("selected", Theme.SECONDARY)])

        cols = ("code", "name", "department", "semester", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)

        widths = {"code": 110, "name": 320, "department": 200,
                  "semester": 160, "status": 130}
        headings = {"code": "Code", "name": "Module", "department": "Department",
                    "semester": "Semester", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.open_evaluation())

        self.tree.tag_configure("done", foreground=Theme.SUCCESS)
        self.tree.tag_configure("pending", foreground=Theme.TEXT)

        actions = tk.Frame(body, bg=Theme.BG)
        actions.pack(fill="x", pady=(15, 0))
        tk.Button(actions, text="📝  Evaluate Selected Module",
                  bg=Theme.PRIMARY, fg="white", font=Theme.FONT_BOLD,
                  relief="flat", cursor="hand2", padx=20, pady=10,
                  command=self.open_evaluation).pack(side="left")
        tk.Button(actions, text="🔄  Refresh", bg=Theme.SECONDARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=20, pady=10, command=self.load_modules).pack(side="left", padx=10)

    def load_modules(self):
        self.tree.delete(*self.tree.get_children())
        evaluated = self.db.evaluated_module_codes(self.student_id)
        for code, name, dept, sem in self.db.get_modules():
            done = code in evaluated
            status = "✓ Evaluated" if done else "Pending"
            tag = "done" if done else "pending"
            self.tree.insert("", "end", iid=code,
                             values=(code, name, dept, sem, status), tags=(tag,))

    def open_evaluation(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a module to evaluate.")
            return
        module_code = sel[0]
        module_name = self.tree.item(module_code)["values"][1]
        lecturers = self.db.get_lecturers()
        if not lecturers:
            messagebox.showwarning(
                "No Lecturers",
                "No lecturers are listed in the directory yet. Please contact an administrator.")
            return
        EvaluationForm(self.root, self.db, self.student_id,
                       module_code, module_name, lecturers, self.load_modules)


# ---------------------------------------------------------------------------
# EVALUATION FORM
# ---------------------------------------------------------------------------
class EvaluationForm:
    CRITERIA = [
        ("knowledge",     "Subject Knowledge",        "Demonstrates deep understanding of the subject matter"),
        ("communication", "Communication Skills",     "Explains concepts clearly and effectively"),
        ("preparation",   "Lecture Preparation",      "Classes are well-prepared and organized"),
        ("engagement",    "Student Engagement",       "Keeps students engaged and encourages participation"),
        ("fairness",      "Fairness in Assessment",   "Grades and assessments are fair and transparent"),
        ("availability",  "Availability for Help",    "Accessible outside class for questions and support"),
        ("overall",       "Overall Rating",           "Your overall impression of this lecturer"),
    ]

    def __init__(self, parent, db, student_id, module_code, module_name,
                 lecturers, on_submit):
        self.db = db
        self.student_id = student_id
        self.module_code = module_code
        self.module_name = module_name
        self.lecturers = lecturers
        self.on_submit = on_submit

        self.win = tk.Toplevel(parent)
        self.win.title("Lecturer Evaluation Form")
        self.win.geometry("760x820")
        self.win.configure(bg=Theme.BG)
        self.win.transient(parent)

        self.ratings = {}
        self.build_ui()
        self.win.wait_visibility()
        self.win.grab_set()

    def build_ui(self):
        header = tk.Frame(self.win, bg=Theme.PRIMARY, height=100)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Lecturer Evaluation Form", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(anchor="w", padx=25, pady=(18, 0))
        tk.Label(header, text=f"{self.module_code} — {self.module_name}",
                 bg=Theme.PRIMARY, fg=Theme.ACCENT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=25)

        container = tk.Frame(self.win, bg=Theme.BG)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=Theme.BG, highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=Theme.BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=740)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=15)
        scroll.pack(side="right", fill="y", pady=15)

        # Lecturer picker
        picker = tk.Frame(inner, bg=Theme.CARD,
                          highlightbackground=Theme.BORDER, highlightthickness=1)
        picker.pack(fill="x", padx=10, pady=(0, 12))
        tk.Label(picker, text="Lecturer", bg=Theme.CARD, fg=Theme.PRIMARY,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(picker, text="Select the lecturer you wish to evaluate for this module.",
                 bg=Theme.CARD, fg=Theme.TEXT_MUTED,
                 font=Theme.FONT_SMALL).pack(anchor="w", padx=12)
        self._lecturer_map = {f"{l[1]} — {l[2]}": l[0] for l in self.lecturers}
        self.lecturer_combo = ttk.Combobox(picker, state="readonly",
                                           values=list(self._lecturer_map.keys()),
                                           font=Theme.FONT_BODY)
        self.lecturer_combo.pack(fill="x", padx=12, pady=(6, 12))

        info = tk.Frame(inner, bg="#f7f3e8",
                        highlightbackground=Theme.ACCENT, highlightthickness=1)
        info.pack(fill="x", padx=10, pady=(0, 15))
        tk.Label(info, text="📋  Rating Scale",
                 bg="#f7f3e8", fg=Theme.PRIMARY, font=Theme.FONT_BOLD).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(info,
                 text="1 = Poor   •   2 = Below Average   •   3 = Average   •   4 = Good   •   5 = Excellent",
                 bg="#f7f3e8", fg=Theme.TEXT, font=Theme.FONT_SMALL).pack(anchor="w", padx=12, pady=(0, 8))

        for key, label, desc in self.CRITERIA:
            self.build_criterion(inner, key, label, desc)

        tk.Label(inner, text="Additional Comments (Optional)",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_BOLD).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(inner, text="Share any specific feedback, suggestions, or praise.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", padx=10)
        self.comments = scrolledtext.ScrolledText(inner, height=5, font=Theme.FONT_BODY,
                                                  relief="solid", bd=1, wrap="word")
        self.comments.pack(fill="x", padx=10, pady=(6, 15))

        btns = tk.Frame(inner, bg=Theme.BG)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btns, text="Submit Evaluation", bg=Theme.SUCCESS, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=25, pady=10, command=self.submit).pack(side="left")
        tk.Button(btns, text="Cancel", bg=Theme.BG, fg=Theme.TEXT_MUTED,
                  font=Theme.FONT_BODY, relief="flat", cursor="hand2",
                  padx=25, pady=10, command=self.win.destroy).pack(side="left", padx=10)

    def build_criterion(self, parent, key, label, desc):
        frame = tk.Frame(parent, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="x", padx=10, pady=5)

        tk.Label(frame, text=label, bg=Theme.CARD, fg=Theme.TEXT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(frame, text=desc, bg=Theme.CARD, fg=Theme.TEXT_MUTED,
                 font=Theme.FONT_SMALL).pack(anchor="w", padx=12)

        radio = tk.Frame(frame, bg=Theme.CARD)
        radio.pack(anchor="w", padx=12, pady=(6, 10))
        var = tk.IntVar(value=0)
        self.ratings[key] = var
        labels = {1: "Poor", 2: "Below Avg", 3: "Average", 4: "Good", 5: "Excellent"}
        for i in range(1, 6):
            rb = tk.Radiobutton(radio, text=f"{i} — {labels[i]}", variable=var, value=i,
                                bg=Theme.CARD, fg=Theme.TEXT, font=Theme.FONT_SMALL,
                                activebackground=Theme.CARD,
                                selectcolor="white", cursor="hand2")
            rb.pack(side="left", padx=(0, 15))

    def submit(self):
        lecturer_label = self.lecturer_combo.get()
        lecturer_id = self._lecturer_map.get(lecturer_label)
        if not lecturer_id:
            messagebox.showwarning("Lecturer Required", "Please select a lecturer.")
            return

        missing = [label for key, label, _ in self.CRITERIA if self.ratings[key].get() == 0]
        if missing:
            messagebox.showwarning("Incomplete",
                                   "Please rate all criteria:\n\n• " + "\n• ".join(missing))
            return

        if self.db.has_evaluated(self.student_id, self.module_code, lecturer_id):
            messagebox.showinfo("Already Evaluated",
                                "You have already evaluated this lecturer for this module.")
            return

        comments = self.comments.get("1.0", "end").strip()
        data = (
            self.student_id, self.module_code, lecturer_id,
            self.ratings["knowledge"].get(),
            self.ratings["communication"].get(),
            self.ratings["preparation"].get(),
            self.ratings["engagement"].get(),
            self.ratings["fairness"].get(),
            self.ratings["availability"].get(),
            self.ratings["overall"].get(),
            comments,
            datetime.now().isoformat(timespec="seconds"),
        )
        ok, msg = self.db.submit_evaluation(data)
        if ok:
            messagebox.showinfo("Thank You",
                                "Your evaluation has been submitted.\nThank you for your feedback!")
            self.on_submit()
            self.win.destroy()
        else:
            messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------
class AdminDashboard:
    def __init__(self, root, db, full_name):
        self.root = root
        self.db = db
        self.full_name = full_name

        for w in root.winfo_children():
            w.destroy()

        root.title(f"Administrator Portal - {self.full_name}")
        root.geometry("1100x720")
        root.configure(bg=Theme.BG)
        root.resizable(True, True)

        self.build_ui()

    def build_ui(self):
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏛  Lecturer Evaluation — Administrator",
                 bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(side="left", padx=25, pady=18)
        tk.Label(header, text=f"👤  {self.full_name}",
                 bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_BODY).pack(side="right", padx=25, pady=22)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=Theme.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10),
                        font=Theme.FONT_BOLD, background=Theme.BORDER,
                        foreground=Theme.TEXT)
        style.map("TNotebook.Tab",
                  background=[("selected", Theme.CARD)],
                  foreground=[("selected", Theme.PRIMARY)])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_reports   = tk.Frame(self.nb, bg=Theme.BG)
        self.tab_lecturers = tk.Frame(self.nb, bg=Theme.BG)

        self.nb.add(self.tab_reports,   text="  📊  Evaluation Reports  ")
        self.nb.add(self.tab_lecturers, text="  👨‍🏫  Manage Lecturers  ")

        self.build_reports_tab()
        self.build_lecturers_tab()

    # -- Reports ------------------------------------------------------------
    def build_reports_tab(self):
        tab = self.tab_reports
        tk.Label(tab, text="Lecturer Performance Summary",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(tab, text="Double-click a lecturer to view their detailed evaluation report.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", padx=10, pady=(0, 10))

        frame = tk.Frame(tab, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("name", "title", "department", "count", "rating")
        self.lecturer_tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)
        widths = {"name": 240, "title": 180, "department": 200, "count": 140, "rating": 180}
        headings = {"name": "Lecturer", "title": "Title", "department": "Department",
                    "count": "# Evaluations", "rating": "Overall Rating"}
        for c in cols:
            self.lecturer_tree.heading(c, text=headings[c])
            self.lecturer_tree.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.lecturer_tree.yview)
        self.lecturer_tree.configure(yscrollcommand=vsb.set)
        self.lecturer_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.lecturer_tree.bind("<Double-1>", lambda e: self.view_report())

        actions = tk.Frame(tab, bg=Theme.BG)
        actions.pack(fill="x", padx=10, pady=5)
        tk.Button(actions, text="📄  View Detailed Report",
                  bg=Theme.PRIMARY, fg="white", font=Theme.FONT_BOLD,
                  relief="flat", cursor="hand2", padx=18, pady=8,
                  command=self.view_report).pack(side="left")
        tk.Button(actions, text="🔄  Refresh", bg=Theme.SECONDARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=18, pady=8, command=self.load_summaries).pack(side="left", padx=10)

        self.load_summaries()

    def load_summaries(self):
        self.lecturer_tree.delete(*self.lecturer_tree.get_children())
        for lid, name, dept, title, count, avg in self.db.get_all_lecturer_summaries():
            rating = f"{avg:.2f} / 5.00  {self.stars(avg)}" if avg else "— No evaluations —"
            self.lecturer_tree.insert("", "end", iid=str(lid),
                                       values=(name, title or "", dept, count, rating))

    @staticmethod
    def stars(avg):
        if not avg:
            return ""
        filled = round(avg)
        return "★" * filled + "☆" * (5 - filled)

    def view_report(self):
        sel = self.lecturer_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a lecturer.")
            return
        LecturerReportWindow(self.root, self.db, int(sel[0]))

    # -- Lecturers ----------------------------------------------------------
    def build_lecturers_tab(self):
        tab = self.tab_lecturers
        tk.Label(tab, text="Lecturer Directory",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w", padx=10, pady=(10, 10))

        frame = tk.Frame(tab, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("name", "title", "department", "email")
        self.lect_tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        for c, w, h in [("name", 220, "Full Name"), ("title", 180, "Title"),
                        ("department", 200, "Department"), ("email", 260, "Email")]:
            self.lect_tree.heading(c, text=h)
            self.lect_tree.column(c, width=w, anchor="w")
        self.lect_tree.pack(fill="both", expand=True)

        form = tk.Frame(tab, bg=Theme.CARD,
                        highlightbackground=Theme.BORDER, highlightthickness=1)
        form.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(form, text="Add New Lecturer", bg=Theme.CARD, fg=Theme.PRIMARY,
                 font=Theme.FONT_BOLD).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 5))

        labels = ["Full Name", "Title", "Department", "Email"]
        self.lect_entries = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl, bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BODY).grid(row=1, column=i, sticky="w", padx=10)
            ent = tk.Entry(form, font=Theme.FONT_BODY, bg="white", relief="solid", bd=1)
            ent.grid(row=2, column=i, sticky="we", padx=10, pady=(2, 10), ipady=4)
            self.lect_entries[lbl] = ent
        for i in range(4):
            form.grid_columnconfigure(i, weight=1)

        tk.Button(form, text="➕  Add Lecturer", bg=Theme.SUCCESS, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=15, pady=6, command=self.add_lecturer
                  ).grid(row=3, column=0, columnspan=4, pady=(0, 10))

        self.load_lecturers()

    def load_lecturers(self):
        self.lect_tree.delete(*self.lect_tree.get_children())
        for lid, name, dept, email, title in self.db.get_lecturers():
            self.lect_tree.insert("", "end", values=(name, title or "", dept, email or ""))

    def add_lecturer(self):
        name  = self.lect_entries["Full Name"].get().strip()
        title = self.lect_entries["Title"].get().strip()
        dept  = self.lect_entries["Department"].get().strip()
        email = self.lect_entries["Email"].get().strip()
        if not name or not dept:
            messagebox.showwarning("Missing", "Full Name and Department are required.")
            return
        self.db.add_lecturer(name, dept, email, title)
        for e in self.lect_entries.values():
            e.delete(0, "end")
        self.load_lecturers()
        self.load_summaries()
        messagebox.showinfo("Success", f"Lecturer '{name}' has been added.")


# ---------------------------------------------------------------------------
# LECTURER REPORT WINDOW
# ---------------------------------------------------------------------------
class LecturerReportWindow:
    CRITERIA_LABELS = [
        ("Subject Knowledge",      1),
        ("Communication Skills",   2),
        ("Lecture Preparation",    3),
        ("Student Engagement",     4),
        ("Fairness in Assessment", 5),
        ("Availability for Help",  6),
        ("Overall Rating",         7),
    ]

    def __init__(self, parent, db, lecturer_id):
        self.db = db
        self.lecturer_id = lecturer_id

        lecturer = next((l for l in db.get_lecturers() if l[0] == lecturer_id), None)
        if not lecturer:
            return
        _, self.name, self.dept, self.email, self.title = lecturer

        self.win = tk.Toplevel(parent)
        self.win.title(f"Evaluation Report - {self.name}")
        self.win.geometry("780x700")
        self.win.configure(bg=Theme.BG)
        self.win.transient(parent)

        self.build_ui()

    def build_ui(self):
        header = tk.Frame(self.win, bg=Theme.PRIMARY, height=110)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=self.name, bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_TITLE).pack(anchor="w", padx=25, pady=(15, 0))
        tk.Label(header, text=f"{self.title or 'Lecturer'} • {self.dept}",
                 bg=Theme.PRIMARY, fg=Theme.ACCENT, font=Theme.FONT_BOLD).pack(anchor="w", padx=25)
        if self.email:
            tk.Label(header, text=self.email, bg=Theme.PRIMARY, fg="white",
                     font=Theme.FONT_SMALL).pack(anchor="w", padx=25)

        body = tk.Frame(self.win, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=20, pady=15)

        stats = self.db.get_lecturer_report(self.lecturer_id)
        count = stats[0] if stats else 0

        if count == 0:
            tk.Label(body, text="No evaluations have been submitted yet.",
                     bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_HEADING).pack(pady=60)
            tk.Button(body, text="Close", bg=Theme.PRIMARY, fg="white",
                      font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                      padx=20, pady=8, command=self.win.destroy).pack()
            return

        summary = tk.Frame(body, bg=Theme.BG)
        summary.pack(fill="x")

        def card(parent, label, value, color):
            f = tk.Frame(parent, bg=color,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
            f.pack(side="left", expand=True, fill="both", padx=5)
            tk.Label(f, text=label, bg=color, fg="white", font=Theme.FONT_SMALL).pack(pady=(10, 0))
            tk.Label(f, text=value, bg=color, fg="white",
                     font=("Georgia", 20, "bold")).pack(pady=(2, 10))

        card(summary, "Total Evaluations", str(count), Theme.PRIMARY)
        card(summary, "Overall Rating", f"{stats[7]:.2f} / 5", Theme.SECONDARY)

        stars_filled = round(stats[7])
        star_str = "★" * stars_filled + "☆" * (5 - stars_filled)
        card(summary, "Stars", star_str, Theme.ACCENT)

        tk.Label(body, text="Rating Breakdown", bg=Theme.BG, fg=Theme.TEXT,
                 font=Theme.FONT_HEADING).pack(anchor="w", pady=(20, 8))

        breakdown = tk.Frame(body, bg=Theme.CARD,
                             highlightbackground=Theme.BORDER, highlightthickness=1)
        breakdown.pack(fill="x")

        for label, idx in self.CRITERIA_LABELS:
            avg = stats[idx]
            row = tk.Frame(breakdown, bg=Theme.CARD)
            row.pack(fill="x", padx=15, pady=6)
            tk.Label(row, text=label, bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BODY, width=25, anchor="w").pack(side="left")
            bar_bg = tk.Frame(row, bg="#e8e4d8", height=18, width=300)
            bar_bg.pack(side="left", padx=(0, 10))
            bar_bg.pack_propagate(False)
            fill_w = int(300 * (avg / 5))
            fill_color = self.rating_color(avg)
            tk.Frame(bar_bg, bg=fill_color, height=18, width=fill_w).pack(side="left")
            tk.Label(row, text=f"{avg:.2f}", bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BOLD, width=6).pack(side="left")

        tk.Label(body, text="Student Comments", bg=Theme.BG, fg=Theme.TEXT,
                 font=Theme.FONT_HEADING).pack(anchor="w", pady=(20, 8))

        comments_frame = tk.Frame(body, bg=Theme.CARD,
                                   highlightbackground=Theme.BORDER, highlightthickness=1)
        comments_frame.pack(fill="both", expand=True)

        text = scrolledtext.ScrolledText(comments_frame, font=Theme.FONT_BODY,
                                         bg=Theme.CARD, relief="flat", bd=0,
                                         wrap="word", padx=12, pady=10)
        text.pack(fill="both", expand=True)

        comments = self.db.get_lecturer_comments(self.lecturer_id)
        if not comments:
            text.insert("end", "No written comments have been submitted.", "muted")
            text.tag_config("muted", foreground=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        else:
            for i, (code, comment, date) in enumerate(comments):
                if i > 0:
                    text.insert("end", "\n" + "─" * 70 + "\n\n")
                text.insert("end", f"[{code}]  ", "course")
                text.insert("end", f"{date[:10]}\n", "date")
                text.insert("end", f"{comment}\n", "body")
        text.tag_config("course", foreground=Theme.PRIMARY, font=Theme.FONT_BOLD)
        text.tag_config("date",   foreground=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        text.tag_config("body",   foreground=Theme.TEXT, font=Theme.FONT_BODY)
        text.config(state="disabled")

        tk.Button(body, text="Close", bg=Theme.PRIMARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=25, pady=8, command=self.win.destroy).pack(pady=(15, 0))

    @staticmethod
    def rating_color(avg):
        if avg >= 4.5: return Theme.SUCCESS
        if avg >= 3.5: return Theme.SECONDARY
        if avg >= 2.5: return Theme.ACCENT
        return Theme.DANGER


# ---------------------------------------------------------------------------
# APPLICATION CONTROLLER
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.user = _get_current_user()
        self.db = Database()
        self.root = tk.Tk()

        if not self.user:
            self._show_no_auth_screen()
            return

        full_name, student_id = _resolve_student_identity(self.user)
        logger.info("Lecturer Evaluation starting user=%s role=%s",
                    full_name, (self.user or {}).get('role') or '<none>')

        if _is_admin_user(self.user):
            AdminDashboard(self.root, self.db, full_name)
        else:
            if not student_id:
                # No student record — let them in but warn; submissions
                # need a non-empty student_id key for the UNIQUE index.
                logger.warning("No student_id resolved for user %s", full_name)
                student_id = (self.user.get('username') or
                              self.user.get('user_id') or 'UNKNOWN')
            StudentDashboard(self.root, self.db, full_name, student_id)

    def _show_no_auth_screen(self):
        self.root.title("Lecturer Evaluation")
        self.root.geometry("520x260")
        self.root.configure(bg=Theme.BG)
        tk.Label(self.root, text="🔒  Authentication Required",
                 bg=Theme.BG, fg=Theme.PRIMARY,
                 font=Theme.FONT_HEADING).pack(pady=(40, 10))
        tk.Label(self.root,
                 text=("Please launch this module from the main\n"
                       "University System after signing in."),
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_BODY,
                 justify="center").pack(pady=10)
        tk.Button(self.root, text="Close", bg=Theme.PRIMARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self.root.destroy).pack(pady=20)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
