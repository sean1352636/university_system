"""
University Background Checker
=============================

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. There is no in-app login screen.

Persistence: rows live in the central `student_records.db` under
module-prefixed tables (`bgcheck_persons`, `bgcheck_audit_log`,
`bgcheck_watchlist`, `bgcheck_search_history`) so they don't collide
with the canonical `users` / `audit_log` tables already in the same
DB. The legacy `background_checker.db` and `background_checker.log`
files alongside this module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import csv
import datetime
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import tkinter as tk
import uuid
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Optional


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


logger = logging.getLogger("BGChecker")

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name="BGChecker")
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username or user_id,
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


def _bgcheck_role(role: str) -> str:
    """Map an EDU_AUTH role onto the three-tier permission model this
    module uses: admin / officer / viewer."""
    r = (role or '').lower()
    if r in ('admin', 'administrator', 'superadmin'):
        return 'admin'
    if r in ('hr', 'staff', 'manager', 'instructor', 'faculty'):
        return 'officer'
    return 'viewer'


# Legacy local files this module used to write — superseded by the
# central student_records.db and shared logs/app.log.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LEGACY_DB_FILE  = os.path.join(_HERE, "background_checker.db")
_LEGACY_LOG_FILE = os.path.join(_HERE, "background_checker.log")


def _remove_legacy_files():
    targets = [
        _LEGACY_DB_FILE,
        _LEGACY_DB_FILE + "-wal",
        _LEGACY_DB_FILE + "-shm",
        _LEGACY_DB_FILE + "-journal",
        _LEGACY_LOG_FILE,
    ]
    for path in targets:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy bg-checker file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy file %s", path,
                               exc_info=True)


# ============================================================
# DATABASE LAYER
# ============================================================
class Database:
    """Thin wrapper around the central `student_records.db`.

    Uses `bgcheck_*` prefixed tables (persons, audit_log, watchlist,
    search_history) so they don't collide with the canonical
    `users` / `audit_log` / etc. tables in the shared DB. There is no
    local `users` table — auth comes from the main system via
    EDU_AUTH_* env vars."""

    def __init__(self, db_path: Optional[str] = None):
        self.conn: Optional[sqlite3.Connection] = None
        self.connect()
        self.init_schema()

    def connect(self) -> None:
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            self.conn = get_connection()
            self.conn.row_factory = sqlite3.Row
            logger.info("Database connected (central student_records.db)")
        except Exception as e:
            logger.exception("Database connection failed")
            raise RuntimeError(f"Could not connect to DB: {e}") from e

    def init_schema(self) -> None:
        try:
            cur = self.conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS bgcheck_persons (
                    case_id TEXT PRIMARY KEY,
                    person_id TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('student','staff','faculty')),
                    email TEXT,
                    phone TEXT,
                    dob TEXT,
                    department TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','in-progress','cleared','flagged','inactive')),
                    gpa REAL,
                    criminal_flag INTEGER DEFAULT 0,
                    disciplinary_history TEXT,
                    employment_history TEXT,
                    references_text TEXT,
                    documents TEXT,
                    notes TEXT,
                    tags TEXT,
                    risk_score INTEGER DEFAULT 0,
                    id_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bgcheck_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    username TEXT,
                    action TEXT NOT NULL,
                    target TEXT,
                    details TEXT
                );

                CREATE TABLE IF NOT EXISTS bgcheck_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    reason TEXT,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bgcheck_search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    query TEXT,
                    timestamp TEXT NOT NULL
                );
                """
            )
            self.conn.commit()
            logger.info("Schema initialized")
        except sqlite3.Error:
            logger.exception("Schema init failed")
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            self.conn.commit()
            return cur
        except sqlite3.Error as e:
            logger.exception("SQL error: %s", sql)
            raise RuntimeError(f"Database error: {e}") from e

    def fetchall(self, sql: str, params: tuple = ()) -> list:
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()
        except sqlite3.Error as e:
            logger.exception("SQL fetch error: %s", sql)
            raise RuntimeError(f"Database error: {e}") from e

    def fetchone(self, sql: str, params: tuple = ()):
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchone()
        except sqlite3.Error as e:
            logger.exception("SQL fetchone error: %s", sql)
            raise RuntimeError(f"Database error: {e}") from e

    def backup(self, path: str) -> None:
        try:
            with sqlite3.connect(path) as bck:
                self.conn.backup(bck)
            logger.info("Backup saved to %s", path)
        except sqlite3.Error as e:
            logger.exception("Backup failed")
            raise RuntimeError(f"Backup error: {e}") from e

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            logger.info("Database closed")


# ============================================================
# UTILITIES
# ============================================================
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def valid_email(email: str) -> bool:
    if not email:
        return True  # optional
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def valid_phone(phone: str) -> bool:
    if not phone:
        return True
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15


def valid_dob(dob: str) -> bool:
    if not dob:
        return True
    try:
        d = datetime.date.fromisoformat(dob)
        age = (datetime.date.today() - d).days / 365.25
        return 0 < age < 120
    except ValueError:
        return False


def valid_id(person_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{4,20}", person_id))


# ============================================================
# AUDIT LOGGER
# ============================================================
class AuditLogger:
    def __init__(self, db: Database):
        self.db = db

    def log(self, username: str, action: str, target: str = "", details: str = "") -> None:
        try:
            self.db.execute(
                "INSERT INTO bgcheck_audit_log (timestamp, username, action, target, details) VALUES (?,?,?,?,?)",
                (now_iso(), username, action, target, details),
            )
            logger.info("AUDIT [%s] %s -> %s | %s", username, action, target, details)
        except RuntimeError:
            logger.exception("Audit log write failed")


# ============================================================
# RISK SCORING
# ============================================================
def calculate_risk_score(person: dict, watchlist_names: list) -> int:
    """0-100 risk score."""
    score = 0
    if person.get("criminal_flag"):
        score += 50
    gpa = person.get("gpa")
    if gpa is not None and gpa < 2.0:
        score += 15
    if person.get("disciplinary_history"):
        score += 20
    name = (person.get("full_name") or "").lower()
    for w in watchlist_names:
        if w.lower() in name:
            score += 30
            break
    if person.get("status") == "flagged":
        score += 10
    return min(score, 100)


# ============================================================
# LOGIN
# ============================================================
# In-app login removed — identity comes from EDU_AUTH_* env vars set
# by the main university GUI. See `_get_current_user` at the top of
# this module.


# ============================================================
# PERSON FORM DIALOG
# ============================================================
class PersonDialog(tk.Toplevel):
    FIELDS = [
        ("person_id", "ID Number*", "entry"),
        ("full_name", "Full Name*", "entry"),
        ("role", "Role*", "combo:student,staff,faculty"),
        ("email", "Email", "entry"),
        ("phone", "Phone", "entry"),
        ("dob", "DOB (YYYY-MM-DD)", "entry"),
        ("department", "Department", "entry"),
        ("status", "Status", "combo:pending,in-progress,cleared,flagged,inactive"),
        ("gpa", "GPA (0.0-4.0)", "entry"),
        ("criminal_flag", "Criminal Flag", "combo:0,1"),
        ("disciplinary_history", "Disciplinary History", "text"),
        ("employment_history", "Employment History", "text"),
        ("references_text", "References", "text"),
        ("documents", "Documents (paths)", "text"),
        ("notes", "Notes", "text"),
        ("tags", "Tags (comma-sep)", "entry"),
    ]

    def __init__(self, parent, title: str, initial: Optional[dict] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("560x720")
        self.transient(parent)
        self.grab_set()
        self.result: Optional[dict] = None
        self.vars: dict = {}

        canvas = tk.Canvas(self, borderwidth=0)
        frame = ttk.Frame(canvas)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        for i, (key, label, kind) in enumerate(self.FIELDS):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            if kind.startswith("combo:"):
                opts = kind.split(":", 1)[1].split(",")
                v = tk.StringVar()
                ttk.Combobox(frame, textvariable=v, values=opts, state="readonly", width=35).grid(
                    row=i, column=1, padx=8, pady=4
                )
                self.vars[key] = v
            elif kind == "text":
                t = tk.Text(frame, height=3, width=38)
                t.grid(row=i, column=1, padx=8, pady=4)
                self.vars[key] = t
            else:
                v = tk.StringVar()
                ttk.Entry(frame, textvariable=v, width=38).grid(row=i, column=1, padx=8, pady=4)
                self.vars[key] = v

        if initial:
            for k, v in initial.items():
                if k in self.vars:
                    widget = self.vars[k]
                    val = "" if v is None else str(v)
                    if isinstance(widget, tk.Text):
                        widget.delete("1.0", "end")
                        widget.insert("1.0", val)
                    else:
                        widget.set(val)

        btn = ttk.Frame(frame)
        btn.grid(row=len(self.FIELDS), column=0, columnspan=2, pady=16)
        ttk.Button(btn, text="Save", command=self._save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=6)

    def _save(self):
        data = {}
        for key, _label, _kind in self.FIELDS:
            w = self.vars[key]
            data[key] = w.get("1.0", "end-1c").strip() if isinstance(w, tk.Text) else w.get().strip()

        # Validation
        if not valid_id(data["person_id"]):
            messagebox.showerror("Validation", "ID must be 4-20 chars, A-Z and 0-9 only.", parent=self)
            return
        if not data["full_name"]:
            messagebox.showerror("Validation", "Full name required.", parent=self)
            return
        if not data["role"]:
            messagebox.showerror("Validation", "Role required.", parent=self)
            return
        if not valid_email(data["email"]):
            messagebox.showerror("Validation", "Invalid email format.", parent=self)
            return
        if not valid_phone(data["phone"]):
            messagebox.showerror("Validation", "Invalid phone (7-15 digits).", parent=self)
            return
        if not valid_dob(data["dob"]):
            messagebox.showerror("Validation", "Invalid DOB (use YYYY-MM-DD, age 0-120).", parent=self)
            return
        if data["gpa"]:
            try:
                gpa = float(data["gpa"])
                if not 0.0 <= gpa <= 4.0:
                    raise ValueError
                data["gpa"] = gpa
            except ValueError:
                messagebox.showerror("Validation", "GPA must be 0.0-4.0", parent=self)
                return
        else:
            data["gpa"] = None

        try:
            data["criminal_flag"] = int(data["criminal_flag"] or 0)
        except ValueError:
            data["criminal_flag"] = 0
        if not data["status"]:
            data["status"] = "pending"

        self.result = data
        self.destroy()


# ============================================================
# MAIN APPLICATION
# ============================================================
class BGCheckerApp(tk.Tk):
    SESSION_TIMEOUT_MIN = 30

    def __init__(self, host=None):
        """Build the BG Checker app.

        ``host`` may be:
          * ``None`` (legacy / subprocess) — initialise as a ``tk.Tk``
            root and own the window/mainloop.
          * a workspace tab ``Frame`` — skip Tk init and build widgets
            onto the host frame; ``mainloop()`` becomes a no-op.

        Same shape as ComplaintsPortal (8.117.49), SafeguardingApp
        (8.117.50), ApprenticeshipApp (8.117.53).
        """
        if host is None:
            super().__init__()
            self.title("University Background Checker")
            self.geometry("1180x720")
            self._host = self
            self._owns_root = True
        else:
            self._host = host
            self._owns_root = False
        self.db = Database()
        self.audit = AuditLogger(self.db)
        self.current_user: Optional[str] = None
        self.current_role: Optional[str] = None
        self.dark_mode = False
        self.font_size = 10
        self.last_activity = datetime.datetime.now()

        if not self._resolve_user():
            self.destroy()
            return

        self._build_menu()
        self._build_ui()
        self._apply_theme()
        self._refresh_table()
        self._refresh_stats()
        self._bind_shortcuts()
        self._start_session_timer()
        if self._owns_root:
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- AUTH ----------
    def _resolve_user(self) -> bool:
        """Pull identity from EDU_AUTH_* env vars instead of an in-app
        login. If the env vars aren't set (i.e. someone launched the
        module standalone), show a placeholder and bail."""
        user = _get_current_user()
        if not user:
            messagebox.showwarning(
                "Authentication Required",
                "Please launch this portal from the main University System "
                "after signing in.")
            return False
        self.current_user = user.get('username') or user.get('user_id') or 'Unknown'
        self.current_role = _bgcheck_role(user.get('role'))
        self.audit.log(self.current_user, "LOGIN", "", f"role={self.current_role}")
        logger.info("BG Checker starting user=%s mapped_role=%s",
                    self.current_user, self.current_role)
        return True

    # ---------- MENU ----------
    def _build_menu(self):
        # Frames don't accept ``config(menu=…)``; only Tk/Toplevel do.
        # Skip the menu when embedded; toolbar buttons in the body
        # cover the same operations.
        if not self._owns_root:
            return
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Import CSV", command=self.import_csv)
        filem.add_command(label="Export CSV", command=self.export_csv)
        filem.add_command(label="Export JSON", command=self.export_json)
        filem.add_command(label="Generate Report", command=self.generate_report)
        filem.add_separator()
        filem.add_command(label="Backup DB", command=self.backup_db)
        filem.add_command(label="Restore DB", command=self.restore_db)
        filem.add_separator()
        filem.add_command(label="Print Preview", command=self.print_preview)
        filem.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filem)

        editm = tk.Menu(menubar, tearoff=0)
        editm.add_command(label="Add Person  (Ctrl+N)", command=self.add_person)
        editm.add_command(label="Edit Selected  (Ctrl+E)", command=self.edit_person)
        editm.add_command(label="Delete Selected  (Del)", command=self.delete_person)
        editm.add_command(label="Add Note", command=self.add_note)
        menubar.add_cascade(label="Edit", menu=editm)

        viewm = tk.Menu(menubar, tearoff=0)
        viewm.add_command(label="Refresh  (F5)", command=self._refresh_table)
        viewm.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewm.add_command(label="Increase Font", command=lambda: self._adjust_font(1))
        viewm.add_command(label="Decrease Font", command=lambda: self._adjust_font(-1))
        viewm.add_separator()
        viewm.add_command(label="Statistics Dashboard", command=self.show_stats)
        viewm.add_command(label="Audit Log", command=self.show_audit_log)
        viewm.add_command(label="Search History", command=self.show_search_history)
        viewm.add_command(label="Recent Activity", command=self.show_recent_activity)
        menubar.add_cascade(label="View", menu=viewm)

        toolm = tk.Menu(menubar, tearoff=0)
        toolm.add_command(label="Run Background Check", command=self.run_check)
        toolm.add_command(label="Detect Duplicates", command=self.detect_duplicates)
        toolm.add_command(label="Manage Watchlist", command=self.manage_watchlist)
        toolm.add_command(label="Configure Risk Thresholds", command=self.configure_thresholds)
        menubar.add_cascade(label="Tools", menu=toolm)

        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        helpm.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpm)

    # ---------- UI ----------
    def _build_ui(self):
        top = ttk.Frame(self._host, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text=f"User: {self.current_user} ({self.current_role})").pack(side=tk.LEFT)
        ttk.Label(top, text="  |  Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.search_var, width=30)
        ent.pack(side=tk.LEFT, padx=4)
        ent.bind("<Return>", lambda _e: self.search())

        ttk.Label(top, text=" Field:").pack(side=tk.LEFT)
        self.search_field = tk.StringVar(value="full_name")
        ttk.Combobox(
            top,
            textvariable=self.search_field,
            values=["person_id", "full_name", "email"],
            state="readonly",
            width=12,
        ).pack(side=tk.LEFT)

        ttk.Label(top, text=" Role:").pack(side=tk.LEFT)
        self.filter_role = tk.StringVar(value="all")
        ttk.Combobox(
            top,
            textvariable=self.filter_role,
            values=["all", "student", "staff", "faculty"],
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT)

        ttk.Label(top, text=" Status:").pack(side=tk.LEFT)
        self.filter_status = tk.StringVar(value="all")
        ttk.Combobox(
            top,
            textvariable=self.filter_status,
            values=["all", "pending", "in-progress", "cleared", "flagged", "inactive"],
            state="readonly",
            width=12,
        ).pack(side=tk.LEFT)

        ttk.Label(top, text=" Dept:").pack(side=tk.LEFT)
        self.filter_dept = tk.StringVar()
        ttk.Entry(top, textvariable=self.filter_dept, width=12).pack(side=tk.LEFT)

        ttk.Button(top, text="Search", command=self.search).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Clear", command=self.clear_filters).pack(side=tk.LEFT)

        # Table
        cols = ("case_id", "person_id", "full_name", "role", "email", "department", "status", "risk_score")
        self.tree = ttk.Treeview(self._host, columns=cols, show="headings", selectmode="browse", style="BgChecker.Treeview")
        widths = {"case_id": 110, "person_id": 100, "full_name": 200, "role": 80,
                  "email": 200, "department": 140, "status": 100, "risk_score": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title(),
                              command=lambda col=c: self._sort_column(col))
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ysb = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.edit_person())
        self.tree.tag_configure("flagged", background="#ffd6d6")
        self.tree.tag_configure("cleared", background="#d6ffd6")

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self._host, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").pack(fill=tk.X, side=tk.BOTTOM)

    def _apply_theme(self):
        bg = "#222" if self.dark_mode else "#f0f0f0"
        fg = "#eee" if self.dark_mode else "black"
        # ttk.Frame doesn't accept ``bg=…`` (only ``tk.Frame`` /
        # ``tk.Tk`` / ``tk.Toplevel`` do), so a workspace tab Frame
        # rejects this. Try it but don't let failure abort the rest
        # of the theme.
        try:
            self._host.configure(bg=bg)
        except tk.TclError:
            pass
        try:
            style = ttk.Style(self._host)
            # Note: avoid base-style configures (TLabel / TFrame / "."
            # / Treeview) here — ttk.Style is process-global, so when
            # this app is embedded in the main GUI workspace those
            # mutations leak out and recolour every widget in the host.
            # Only the namespaced BgChecker.Treeview is touched; the
            # rest of the BG Checker chrome uses tk.Frame / tk.Label
            # with explicit bg=/fg= so dark mode still works.
            if self.dark_mode:
                style.configure("BgChecker.Treeview",
                                background="#333", foreground=fg, fieldbackground="#333")
            else:
                style.configure("BgChecker.Treeview",
                                background="white", foreground="black", fieldbackground="white")
        except tk.TclError:
            logger.exception("Theme apply failed")

    def _bind_shortcuts(self):
        self.bind("<Control-n>", lambda _e: self.add_person())
        self.bind("<Control-e>", lambda _e: self.edit_person())
        self.bind("<Delete>", lambda _e: self.delete_person())
        self.bind("<F5>", lambda _e: self._refresh_table())
        self.bind("<Control-f>", lambda _e: self.search())
        self.bind("<Control-q>", lambda _e: self._on_close())
        self.bind_all("<Any-KeyPress>", self._mark_activity)
        self.bind_all("<Any-Button>", self._mark_activity)

    # ---------- SESSION ----------
    def _mark_activity(self, _e=None):
        self.last_activity = datetime.datetime.now()

    def _start_session_timer(self):
        def check():
            elapsed = (datetime.datetime.now() - self.last_activity).total_seconds() / 60
            if elapsed > self.SESSION_TIMEOUT_MIN:
                logger.info("Session timed out for %s", self.current_user)
                messagebox.showinfo("Session", "Session timed out. Please log in again.")
                self._on_close()
                return
            self.after(60_000, check)
        self.after(60_000, check)

    # ---------- DATA OPS ----------
    def _refresh_table(self, rows: Optional[list] = None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        if rows is None:
            try:
                rows = self.db.fetchall("SELECT * FROM bgcheck_persons ORDER BY updated_at DESC")
            except RuntimeError as e:
                messagebox.showerror("Database error", str(e))
                return
        for r in rows:
            tag = r["status"] if r["status"] in ("flagged", "cleared") else ""
            self.tree.insert(
                "", "end",
                iid=r["case_id"],
                values=(r["case_id"], r["person_id"], r["full_name"], r["role"],
                        r["email"] or "", r["department"] or "", r["status"], r["risk_score"]),
                tags=(tag,),
            )
        self.status_var.set(f"{len(rows)} record(s)")

    def _refresh_stats(self):
        try:
            total = self.db.fetchone("SELECT COUNT(*) c FROM bgcheck_persons")["c"]
            flagged = self.db.fetchone("SELECT COUNT(*) c FROM bgcheck_persons WHERE status='flagged'")["c"]
            cleared = self.db.fetchone("SELECT COUNT(*) c FROM bgcheck_persons WHERE status='cleared'")["c"]
            # Dynamic title only meaningful on a Tk/Toplevel.
            if self._owns_root:
                self.title(f"University Background Checker — Total: {total} | Flagged: {flagged} | Cleared: {cleared}")
            else:
                self.status_var.set(f"Total: {total} | Flagged: {flagged} | Cleared: {cleared}")
        except RuntimeError:
            logger.exception("Stats refresh failed")

    def _selected_case_id(self) -> Optional[str]:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _require_role(self, *roles) -> bool:
        if self.current_role not in roles:
            messagebox.showwarning("Permission denied", f"Requires role: {', '.join(roles)}")
            return False
        return True

    # ---------- CRUD ----------
    def add_person(self):
        if not self._require_role("admin", "officer"):
            return
        dlg = PersonDialog(self, "Add Person")
        self.wait_window(dlg)
        if not dlg.result:
            return
        d = dlg.result
        try:
            existing = self.db.fetchone("SELECT 1 FROM bgcheck_persons WHERE person_id=?", (d["person_id"],))
            if existing:
                messagebox.showerror("Duplicate", "Person ID already exists.")
                return
            watch = [r["name"] for r in self.db.fetchall("SELECT name FROM bgcheck_watchlist")]
            risk = calculate_risk_score(d, watch)
            case_id = "CASE-" + uuid.uuid4().hex[:8].upper()
            self.db.execute(
                """INSERT INTO bgcheck_persons (case_id, person_id, full_name, role, email, phone, dob,
                   department, status, gpa, criminal_flag, disciplinary_history, employment_history,
                   references_text, documents, notes, tags, risk_score, id_hash, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (case_id, d["person_id"], d["full_name"], d["role"], d["email"], d["phone"], d["dob"],
                 d["department"], d["status"], d["gpa"], d["criminal_flag"], d["disciplinary_history"],
                 d["employment_history"], d["references_text"], d["documents"], d["notes"], d["tags"],
                 risk, sha256(d["person_id"]), now_iso(), now_iso()),
            )
            self.audit.log(self.current_user, "ADD_PERSON", case_id, d["full_name"])
            self._refresh_table()
            self._refresh_stats()
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    def edit_person(self):
        if not self._require_role("admin", "officer"):
            return
        cid = self._selected_case_id()
        if not cid:
            messagebox.showinfo("Edit", "Select a row first.")
            return
        try:
            row = self.db.fetchone("SELECT * FROM bgcheck_persons WHERE case_id=?", (cid,))
            if not row:
                return
            initial = dict(row)
            dlg = PersonDialog(self, "Edit Person", initial=initial)
            self.wait_window(dlg)
            if not dlg.result:
                return
            d = dlg.result
            watch = [r["name"] for r in self.db.fetchall("SELECT name FROM bgcheck_watchlist")]
            risk = calculate_risk_score(d, watch)
            self.db.execute(
                """UPDATE bgcheck_persons SET person_id=?, full_name=?, role=?, email=?, phone=?, dob=?,
                   department=?, status=?, gpa=?, criminal_flag=?, disciplinary_history=?,
                   employment_history=?, references_text=?, documents=?, notes=?, tags=?,
                   risk_score=?, updated_at=? WHERE case_id=?""",
                (d["person_id"], d["full_name"], d["role"], d["email"], d["phone"], d["dob"],
                 d["department"], d["status"], d["gpa"], d["criminal_flag"], d["disciplinary_history"],
                 d["employment_history"], d["references_text"], d["documents"], d["notes"], d["tags"],
                 risk, now_iso(), cid),
            )
            self.audit.log(self.current_user, "EDIT_PERSON", cid, d["full_name"])
            self._refresh_table()
            self._refresh_stats()
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    def delete_person(self):
        if not self._require_role("admin"):
            return
        cid = self._selected_case_id()
        if not cid:
            return
        if not messagebox.askyesno("Delete", f"Delete {cid}?"):
            return
        try:
            self.db.execute("DELETE FROM bgcheck_persons WHERE case_id=?", (cid,))
            self.audit.log(self.current_user, "DELETE_PERSON", cid)
            self._refresh_table()
            self._refresh_stats()
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    def add_note(self):
        cid = self._selected_case_id()
        if not cid:
            return
        note = simpledialog.askstring("Add Note", "Append note:")
        if not note:
            return
        try:
            row = self.db.fetchone("SELECT notes FROM bgcheck_persons WHERE case_id=?", (cid,))
            existing = row["notes"] or ""
            new = f"{existing}\n[{now_iso()} by {self.current_user}] {note}".strip()
            self.db.execute("UPDATE bgcheck_persons SET notes=?, updated_at=? WHERE case_id=?",
                            (new, now_iso(), cid))
            self.audit.log(self.current_user, "ADD_NOTE", cid, note[:80])
            messagebox.showinfo("Note", "Note added.")
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    # ---------- SEARCH ----------
    def search(self):
        q = self.search_var.get().strip()
        field = self.search_field.get()
        role = self.filter_role.get()
        status = self.filter_status.get()
        dept = self.filter_dept.get().strip()

        sql = "SELECT * FROM bgcheck_persons WHERE 1=1"
        params: list = []
        if q:
            if field not in ("person_id", "full_name", "email"):
                field = "full_name"
            sql += f" AND {field} LIKE ?"
            params.append(f"%{q}%")
        if role and role != "all":
            sql += " AND role=?"
            params.append(role)
        if status and status != "all":
            sql += " AND status=?"
            params.append(status)
        if dept:
            sql += " AND department LIKE ?"
            params.append(f"%{dept}%")
        sql += " ORDER BY updated_at DESC"

        try:
            rows = self.db.fetchall(sql, tuple(params))
            self._refresh_table(rows)
            self.db.execute(
                "INSERT INTO bgcheck_search_history (username, query, timestamp) VALUES (?,?,?)",
                (self.current_user, f"{field}:{q} role:{role} status:{status} dept:{dept}", now_iso()),
            )
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    def clear_filters(self):
        self.search_var.set("")
        self.filter_role.set("all")
        self.filter_status.set("all")
        self.filter_dept.set("")
        self._refresh_table()

    def _sort_column(self, col: str):
        try:
            rows = self.db.fetchall(f"SELECT * FROM bgcheck_persons ORDER BY {col}")
            self._refresh_table(rows)
        except RuntimeError as e:
            messagebox.showerror("Database error", str(e))

    # ---------- IMPORT/EXPORT ----------
    def import_csv(self):
        if not self._require_role("admin", "officer"):
            return
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        added = errors = 0
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        d = {k: (row.get(k) or "").strip() for k, _, _ in PersonDialog.FIELDS}
                        if not valid_id(d["person_id"]) or not d["full_name"] or not d["role"]:
                            errors += 1
                            continue
                        if self.db.fetchone("SELECT 1 FROM bgcheck_persons WHERE person_id=?", (d["person_id"],)):
                            errors += 1
                            continue
                        try:
                            d["gpa"] = float(d["gpa"]) if d["gpa"] else None
                        except ValueError:
                            d["gpa"] = None
                        try:
                            d["criminal_flag"] = int(d["criminal_flag"] or 0)
                        except ValueError:
                            d["criminal_flag"] = 0
                        if not d["status"]:
                            d["status"] = "pending"
                        watch = [r["name"] for r in self.db.fetchall("SELECT name FROM bgcheck_watchlist")]
                        risk = calculate_risk_score(d, watch)
                        case_id = "CASE-" + uuid.uuid4().hex[:8].upper()
                        self.db.execute(
                            """INSERT INTO bgcheck_persons (case_id, person_id, full_name, role, email, phone, dob,
                               department, status, gpa, criminal_flag, disciplinary_history, employment_history,
                               references_text, documents, notes, tags, risk_score, id_hash, created_at, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (case_id, d["person_id"], d["full_name"], d["role"], d["email"], d["phone"], d["dob"],
                             d["department"], d["status"], d["gpa"], d["criminal_flag"], d["disciplinary_history"],
                             d["employment_history"], d["references_text"], d["documents"], d["notes"], d["tags"],
                             risk, sha256(d["person_id"]), now_iso(), now_iso()),
                        )
                        added += 1
                    except (RuntimeError, KeyError):
                        logger.exception("Import row failed")
                        errors += 1
            self.audit.log(self.current_user, "IMPORT_CSV", path, f"added={added} errors={errors}")
            self._refresh_table()
            self._refresh_stats()
            messagebox.showinfo("Import", f"Added {added}, errors {errors}.")
        except OSError as e:
            messagebox.showerror("Import", f"File error: {e}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            rows = self.db.fetchall("SELECT * FROM bgcheck_persons")
            if not rows:
                messagebox.showinfo("Export", "Nothing to export.")
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                for r in rows:
                    writer.writerow(dict(r))
            self.audit.log(self.current_user, "EXPORT_CSV", path)
            messagebox.showinfo("Export", f"Exported {len(rows)} rows.")
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Export", str(e))

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            rows = [dict(r) for r in self.db.fetchall("SELECT * FROM bgcheck_persons")]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, default=str)
            self.audit.log(self.current_user, "EXPORT_JSON", path)
            messagebox.showinfo("Export", f"Exported {len(rows)} rows.")
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Export", str(e))

    def generate_report(self):
        cid = self._selected_case_id()
        if not cid:
            messagebox.showinfo("Report", "Select a row first.")
            return
        try:
            row = self.db.fetchone("SELECT * FROM bgcheck_persons WHERE case_id=?", (cid,))
            if not row:
                return
            lines = ["=" * 60, "BACKGROUND CHECK REPORT", "=" * 60,
                     f"Generated: {now_iso()} by {self.current_user}", ""]
            for k in row.keys():
                lines.append(f"{k:<22}: {row[k]}")
            lines += ["", "=" * 60, "End of report"]
            text = "\n".join(lines)
            path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Text", "*.txt")],
                                                initialfile=f"{cid}_report.txt")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.audit.log(self.current_user, "REPORT", cid, path)
                messagebox.showinfo("Report", "Report saved.")
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Report", str(e))

    def backup_db(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite", "*.db")])
        if not path:
            return
        try:
            self.db.backup(path)
            self.audit.log(self.current_user, "BACKUP", path)
            messagebox.showinfo("Backup", "Backup complete.")
        except RuntimeError as e:
            messagebox.showerror("Backup", str(e))

    def restore_db(self):
        if not self._require_role("admin"):
            return
        path = filedialog.askopenfilename(filetypes=[("SQLite", "*.db")])
        if not path or not os.path.exists(path):
            return
        if not messagebox.askyesno("Restore", "This overwrites current data. Continue?"):
            return
        try:
            self.db.close()
            os.replace(path, self.db.db_path) if False else None  # don't move user's file
            # Safer: copy contents
            import shutil
            shutil.copyfile(path, self.db.db_path)
            self.db = Database(self.db.db_path)
            self.audit = AuditLogger(self.db)
            self._refresh_table()
            self._refresh_stats()
            messagebox.showinfo("Restore", "Restored.")
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Restore", str(e))

    def print_preview(self):
        cid = self._selected_case_id()
        if not cid:
            messagebox.showinfo("Print", "Select a row first.")
            return
        try:
            row = self.db.fetchone("SELECT * FROM bgcheck_persons WHERE case_id=?", (cid,))
            win = tk.Toplevel(self._host)
            win.title("Print Preview")
            txt = tk.Text(win, width=80, height=30)
            txt.pack(fill=tk.BOTH, expand=True)
            for k in row.keys():
                txt.insert("end", f"{k}: {row[k]}\n")
            txt.configure(state="disabled")
        except RuntimeError as e:
            messagebox.showerror("Print", str(e))

    # ---------- TOOLS ----------
    def run_check(self):
        cid = self._selected_case_id()
        if not cid:
            messagebox.showinfo("Check", "Select a row first.")
            return
        try:
            row = dict(self.db.fetchone("SELECT * FROM bgcheck_persons WHERE case_id=?", (cid,)))
            watch = [r["name"] for r in self.db.fetchall("SELECT name FROM bgcheck_watchlist")]
            risk = calculate_risk_score(row, watch)
            new_status = "flagged" if risk >= 50 else "cleared"
            self.db.execute(
                "UPDATE bgcheck_persons SET risk_score=?, status=?, updated_at=? WHERE case_id=?",
                (risk, new_status, now_iso(), cid),
            )
            self.audit.log(self.current_user, "RUN_CHECK", cid, f"risk={risk} status={new_status}")
            self._refresh_table()
            self._refresh_stats()
            messagebox.showinfo("Check", f"Risk score: {risk}\nStatus: {new_status}")
        except RuntimeError as e:
            messagebox.showerror("Check", str(e))

    def detect_duplicates(self):
        try:
            rows = self.db.fetchall(
                "SELECT full_name, COUNT(*) c FROM bgcheck_persons GROUP BY full_name HAVING c > 1"
            )
            if not rows:
                messagebox.showinfo("Duplicates", "No duplicates found.")
                return
            msg = "\n".join(f"{r['full_name']}: {r['c']}" for r in rows)
            messagebox.showwarning("Duplicates", msg)
        except RuntimeError as e:
            messagebox.showerror("Duplicates", str(e))

    def manage_watchlist(self):
        win = tk.Toplevel(self._host)
        win.title("Watchlist")
        win.geometry("420x420")
        lb = tk.Listbox(win)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def reload():
            lb.delete(0, "end")
            try:
                for r in self.db.fetchall("SELECT id, name, reason FROM bgcheck_watchlist ORDER BY name"):
                    lb.insert("end", f"{r['id']}: {r['name']} ({r['reason'] or ''})")
            except RuntimeError as e:
                messagebox.showerror("Watchlist", str(e), parent=win)

        def add():
            name = simpledialog.askstring("Watchlist", "Name:", parent=win)
            if not name:
                return
            reason = simpledialog.askstring("Watchlist", "Reason:", parent=win) or ""
            try:
                self.db.execute(
                    "INSERT INTO bgcheck_watchlist (name, reason, added_at) VALUES (?,?,?)",
                    (name, reason, now_iso()),
                )
                self.audit.log(self.current_user, "WATCHLIST_ADD", name)
                reload()
            except RuntimeError as e:
                messagebox.showerror("Watchlist", str(e), parent=win)

        def remove():
            sel = lb.curselection()
            if not sel:
                return
            wid = int(lb.get(sel[0]).split(":", 1)[0])
            try:
                self.db.execute("DELETE FROM bgcheck_watchlist WHERE id=?", (wid,))
                self.audit.log(self.current_user, "WATCHLIST_DEL", str(wid))
                reload()
            except RuntimeError as e:
                messagebox.showerror("Watchlist", str(e), parent=win)

        bf = ttk.Frame(win)
        bf.pack(pady=6)
        ttk.Button(bf, text="Add", command=add).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Remove", command=remove).pack(side=tk.LEFT, padx=4)
        reload()

    def configure_thresholds(self):
        messagebox.showinfo(
            "Risk Thresholds",
            "Current thresholds:\n"
            "- Criminal flag: +50\n"
            "- GPA < 2.0: +15\n"
            "- Disciplinary history: +20\n"
            "- Watchlist match: +30\n"
            "- Status flagged: +10\n\n"
            "Threshold for auto-flag: 50",
        )

    # ---------- VIEW DIALOGS ----------
    def show_stats(self):
        try:
            total = self.db.fetchone("SELECT COUNT(*) c FROM bgcheck_persons")["c"]
            by_role = self.db.fetchall("SELECT role, COUNT(*) c FROM bgcheck_persons GROUP BY role")
            by_status = self.db.fetchall("SELECT status, COUNT(*) c FROM bgcheck_persons GROUP BY status")
            avg_risk = self.db.fetchone("SELECT AVG(risk_score) a FROM bgcheck_persons")["a"] or 0
            lines = [f"Total persons: {total}", f"Average risk: {avg_risk:.1f}", "", "By role:"]
            lines += [f"  {r['role']}: {r['c']}" for r in by_role]
            lines += ["", "By status:"]
            lines += [f"  {r['status']}: {r['c']}" for r in by_status]
            messagebox.showinfo("Statistics", "\n".join(lines))
        except RuntimeError as e:
            messagebox.showerror("Statistics", str(e))

    def show_audit_log(self):
        win = tk.Toplevel(self._host)
        win.title("Audit Log")
        win.geometry("800x500")
        txt = tk.Text(win)
        txt.pack(fill=tk.BOTH, expand=True)
        try:
            for r in self.db.fetchall("SELECT * FROM bgcheck_audit_log ORDER BY id DESC LIMIT 500"):
                txt.insert("end",
                           f"{r['timestamp']} | {r['username']} | {r['action']} | {r['target']} | {r['details']}\n")
        except RuntimeError as e:
            messagebox.showerror("Audit", str(e))
        txt.configure(state="disabled")

    def show_search_history(self):
        win = tk.Toplevel(self._host)
        win.title("Search History")
        win.geometry("700x400")
        txt = tk.Text(win)
        txt.pack(fill=tk.BOTH, expand=True)
        try:
            for r in self.db.fetchall("SELECT * FROM bgcheck_search_history ORDER BY id DESC LIMIT 200"):
                txt.insert("end", f"{r['timestamp']} | {r['username']} | {r['query']}\n")
        except RuntimeError as e:
            messagebox.showerror("History", str(e))
        txt.configure(state="disabled")

    def show_recent_activity(self):
        win = tk.Toplevel(self._host)
        win.title("Recent Activity")
        win.geometry("700x400")
        txt = tk.Text(win)
        txt.pack(fill=tk.BOTH, expand=True)
        try:
            for r in self.db.fetchall("SELECT * FROM bgcheck_persons ORDER BY updated_at DESC LIMIT 25"):
                txt.insert("end", f"{r['updated_at']} | {r['case_id']} | {r['full_name']} | {r['status']}\n")
        except RuntimeError as e:
            messagebox.showerror("Activity", str(e))
        txt.configure(state="disabled")

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _adjust_font(self, delta: int):
        self.font_size = max(8, min(20, self.font_size + delta))
        self._apply_theme()

    def show_shortcuts(self):
        messagebox.showinfo(
            "Shortcuts",
            "Ctrl+N - Add person\nCtrl+E - Edit\nDel - Delete\nF5 - Refresh\nCtrl+F - Search\nCtrl+Q - Quit",
        )

    def show_about(self):
        messagebox.showinfo(
            "About",
            "University Background Checker v1.0\n\n"
            "Tkinter + SQLite\n"
            "Audit log, risk scoring, import/export, watchlist, and more.\n\n"
            "Authentication: handled by the main university system "
            "(EDU_AUTH_*).",
        )

    # ---------- LIFECYCLE ----------
    def _on_close(self):
        try:
            if self.current_user:
                self.audit.log(self.current_user, "LOGOUT")
            self.db.close()
        except (RuntimeError, sqlite3.Error):
            logger.exception("Close error")
        self.destroy()

    # ---------- embedded-mode shims ----------
    # When ``host`` was supplied, ``super().__init__()`` was skipped,
    # so any inherited ``tk.Misc`` method that touches ``self.tk``
    # would crash. Forward to the host frame.
    def mainloop(self, n: int = 0):
        if self._owns_root:
            super().mainloop(n)

    def destroy(self):
        if self._owns_root:
            super().destroy()
        else:
            try:
                self._host.destroy()
            except tk.TclError:
                pass

    def bind(self, sequence=None, func=None, add=None):
        if self._owns_root:
            return super().bind(sequence, func, add)
        return self._host.bind(sequence, func, add)

    def bind_all(self, sequence=None, func=None, add=None):
        if self._owns_root:
            return super().bind_all(sequence, func, add)
        return self._host.bind_all(sequence, func, add)

    def after(self, ms, *args):
        if self._owns_root:
            return super().after(ms, *args)
        return self._host.after(ms, *args)


# ============================================================
# ENTRY POINT
# ============================================================
def main():
    _remove_legacy_files()
    try:
        app = BGCheckerApp()
        if app.winfo_exists():
            app.mainloop()
    except (RuntimeError, tk.TclError) as e:
        logger.exception("Fatal error")
        try:
            messagebox.showerror("Fatal error", str(e))
        except tk.TclError:
            print(f"Fatal: {e}")


if __name__ == "__main__":
    main()
