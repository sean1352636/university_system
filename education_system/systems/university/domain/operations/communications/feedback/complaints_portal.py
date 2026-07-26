"""
University Complaints Portal
A GUI application for students and staff to submit and track complaints.

Persistence: rows live in the central university `student_records.db` in a
`complaints` table (created on first launch). Replaces the previous local
`complaints.json` so admins can query complaints alongside the rest of the
domain data.

Auth: when launched as a subprocess by the unified main GUI, the
`EDU_AUTH_*` env vars carry the logged-in user's identity. The Submit tab
auto-fills full name, ID, and email from that user; standalone launches
fall back to manually-entered fields.

Email: on successful submission, a confirmation receipt is queued via the
shared email service using the `communications/complaint_received` JSON
template. Best-effort — never blocks the submit.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
import uuid

logger = logging.getLogger(__name__)

# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally (the package is
# already on the path). Without this, `from education_system... import
# get_connection` silently fails, the DB lookup never runs, and the
# autofill falls back to `username` (e.g. shows "S12345" as Full Name).
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


# ---------- Auth bootstrap ----------
def _bootstrap_auth_from_env():
    """Rebuild a global auth instance from EDU_AUTH_* env vars.

    No-op when the env vars aren't set (running standalone). Mirrors the
    pattern used by disciplinary_portal.py.
    """
    user_id = os.environ.get('EDU_AUTH_USER_ID')
    username = os.environ.get('EDU_AUTH_USERNAME')
    if not (user_id or username):
        return
    perms = [p for p in os.environ.get('EDU_AUTH_PERMISSIONS', '').split(',') if p]
    current_user = {
        'id': user_id or None,
        'user_id': user_id or None,
        'username': username or '',
        'role': os.environ.get('EDU_AUTH_ROLE', '') or '',
        'email': os.environ.get('EDU_AUTH_EMAIL', '') or '',
        'permissions': perms,
    }
    try:
        from types import SimpleNamespace

        def _check_permission(perm, _u=current_user):
            return perm in _u['permissions']

        shim = SimpleNamespace(
            current_user=current_user,
            user_role=current_user['role'],
            check_permission=_check_permission,
            is_authenticated=True,
        )
        from education_system.systems.university.infrastructure.auth import set_global_auth
        set_global_auth(shim)
        try:
            from education_system.systems.university.infrastructure.shared_context import set_auth as _shared_set_auth
            _shared_set_auth(shim)
        except Exception:
            logger.debug("shared_context.set_auth unavailable", exc_info=True)
        logger.info("Auth bootstrapped from env for user=%s role=%s",
                    username or user_id, current_user['role'])
    except Exception:
        logger.warning("Failed to bootstrap auth from env", exc_info=True)


_bootstrap_auth_from_env()


def _get_current_user():
    """Resolve the logged-in user dict.

    Reads the `EDU_AUTH_*` env vars directly first — those are set by the
    main GUI's `_launch_new_feature_module` and are the authoritative
    source for a subprocess-launched portal. Falls back to the global auth
    shim (set by `_bootstrap_auth_from_env`) and finally returns None if
    neither is populated.

    The previous implementation went env → bootstrap → set_global_auth →
    get_global_auth → .current_user, and any silent failure in that chain
    (e.g. an import error inside auth infra wrapped in try/except: pass)
    left the autofill blank. Reading the env directly removes those
    failure modes for the autofill code path.
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
        from education_system.systems.university.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_admin_user(user):
    """Return True if `user` has an admin/superadmin role."""
    if not user:
        return False
    role = (user.get('role') or '').lower()
    return role in ('admin', 'administrator', 'superadmin')


def _resolve_submitter_details(user):
    """Look up the submitter's full name, student/staff ID and email.

    The env-provided `EDU_AUTH_USER_ID` is the auth `users.id` PK (e.g.
    `2`), NOT the student-facing `students.student_id` (e.g. `S12345`),
    so we look up the correct ID by joining `users → students` on
    `student_id` and matching either by `users.id` or `users.username`.

    Email prefers `users.email` over `students.email_address` so
    confirmation emails land in the in-app inbox (same reasoning as
    `_student_contact` in election_gui.py).

    Falls back to env-only details when the DB lookup misses.

    Returns (full_name, student_or_staff_id, email).
    """
    if not user:
        return '', '', ''
    env_user_id = (user.get('user_id') or user.get('id') or '') or ''
    username = user.get('username') or ''
    env_email = user.get('email') or ''

    full_name = ''
    email = env_email
    resolved_id = ''
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        row = None
        # Match by users.id first when we have a numeric auth PK.
        if env_user_id:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name, "
                "       COALESCE(u.email, s.email_address, '') "
                "FROM users u "
                "LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.id = ?",
                (env_user_id,)).fetchone()
        # Fall back to username lookup.
        if not row and username:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name, "
                "       COALESCE(u.email, s.email_address, '') "
                "FROM users u "
                "LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.username = ?",
                (username,)).fetchone()
        # Also try matching the env value against students.student_id
        # directly — covers cases where the launcher passes the student
        # id as the user id.
        if not row and env_user_id:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name, "
                "       COALESCE(u.email, s.email_address, '') "
                "FROM students s "
                "LEFT JOIN users u ON u.student_id = s.student_id "
                "WHERE s.student_id = ?",
                (env_user_id,)).fetchone()
        conn.close()
        if row:
            sid, first, last, mail = row
            resolved_id = str(sid or '')
            full_name = ' '.join(p for p in (first or '', last or '') if p).strip()
            if mail:
                email = mail
    except Exception:
        # DB not reachable — fall back to env-only details.
        pass

    if not full_name:
        full_name = username or env_user_id or ''
    student_or_staff_id = resolved_id or env_user_id or username or ''
    return full_name, str(student_or_staff_id), email or ''


# ---------- Data Layer (SQLite) ----------
_COMPLAINTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    email       TEXT NOT NULL,
    category    TEXT NOT NULL,
    priority    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Pending',
    response    TEXT NOT NULL DEFAULT '',
    submitted   TEXT NOT NULL,
    updated     TEXT NOT NULL,
    submitted_by TEXT
)
"""


def _connect():
    """Return a connection to the central university DB.

    Returns None if the infrastructure isn't reachable (e.g. running this
    file outside the package context); the GUI degrades gracefully.
    """
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        return get_connection()
    except Exception:
        logger.error("Could not open DB connection for complaints portal", exc_info=True)
        return None


def _ensure_schema(conn):
    if conn is None:
        return
    try:
        conn.execute(_COMPLAINTS_SCHEMA)
        conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to ensure complaints schema")


def load_complaints():
    """Load all complaints from the DB, newest first."""
    conn = _connect()
    if conn is None:
        return []
    _ensure_schema(conn)
    try:
        rows = conn.execute(
            "SELECT id, name, user_id, email, category, priority, subject, "
            "       description, status, response, submitted, updated "
            "FROM complaints ORDER BY submitted DESC"
        ).fetchall()
    except sqlite3.Error:
        logger.exception("Failed to load complaints")
        rows = []
    conn.close()
    logger.debug("Loaded %d complaints", len(rows))
    return [
        {
            'id': r[0], 'name': r[1], 'user_id': r[2], 'email': r[3],
            'category': r[4], 'priority': r[5], 'subject': r[6],
            'description': r[7], 'status': r[8], 'response': r[9],
            'submitted': r[10], 'updated': r[11],
        }
        for r in rows
    ]


def insert_complaint(complaint, submitted_by=None):
    """Insert a complaint row. Returns True on success."""
    conn = _connect()
    if conn is None:
        return False
    _ensure_schema(conn)
    try:
        conn.execute(
            "INSERT INTO complaints "
            "(id, name, user_id, email, category, priority, subject, "
            " description, status, response, submitted, updated, submitted_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                complaint['id'], complaint['name'], complaint['user_id'],
                complaint['email'], complaint['category'], complaint['priority'],
                complaint['subject'], complaint['description'],
                complaint['status'], complaint['response'],
                complaint['submitted'], complaint['updated'],
                submitted_by,
            ),
        )
        conn.commit()
        logger.info("Inserted complaint id=%s category=%s priority=%s by=%s",
                    complaint['id'], complaint.get('category'),
                    complaint.get('priority'), submitted_by)
        try:
            from education_system.systems.university.services.bus.integration_bus import (
                publish_complaint_filed,
            )
            publish_complaint_filed(
                complaint_id=complaint['id'],
                user_id=complaint.get('user_id'),
                email=complaint.get('email'),
                category=complaint.get('category'),
                priority=complaint.get('priority'),
                subject=complaint.get('subject'),
            )
        except Exception:
            pass
        return True
    except sqlite3.Error:
        logger.exception("Failed to insert complaint id=%s", complaint.get('id'))
        return False
    finally:
        conn.close()


def update_complaint_row(complaint_id, status, response):
    conn = _connect()
    if conn is None:
        return False
    try:
        conn.execute(
            "UPDATE complaints SET status = ?, response = ?, updated = ? "
            "WHERE id = ?",
            (status, response, datetime.now().strftime('%Y-%m-%d %H:%M'),
             complaint_id))
        conn.commit()
        logger.info("Updated complaint id=%s status=%s", complaint_id, status)
        return True
    except sqlite3.Error:
        logger.exception("Failed to update complaint id=%s", complaint_id)
        return False
    finally:
        conn.close()


def delete_complaint_row(complaint_id):
    conn = _connect()
    if conn is None:
        return False
    try:
        conn.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
        conn.commit()
        logger.info("Deleted complaint id=%s", complaint_id)
        return True
    except sqlite3.Error:
        logger.exception("Failed to delete complaint id=%s", complaint_id)
        return False
    finally:
        conn.close()


# ---------- Email confirmation ----------
def _send_complaint_confirmation(email, full_vars):
    """Render `communications/complaint_received` and queue it.

    Best-effort; returns True on a successful queue, False otherwise.
    Never raises — the submit flow must not be blocked by email infra.
    """
    if not email:
        return False
    try:
        from education_system.systems.university.infrastructure.email.template_utils import render_template
        subject, body = render_template('communications/complaint_received', full_vars)
        if not (subject and body):
            logger.warning("Empty complaint_received template render for %s", email)
            return False
    except Exception:
        logger.exception("Failed to render complaint_received template")
        return False
    try:
        from education_system.systems.university.infrastructure.utils.email_service import queue_email
        ok = bool(queue_email(email, subject, body))
        if ok:
            logger.info("Queued complaint confirmation email to %s", email)
        else:
            logger.warning("queue_email returned falsy for %s", email)
        return ok
    except Exception:
        logger.exception("Failed to queue complaint confirmation email")
        return False


def _send_complaint_status_update(email, full_vars):
    """Render `communications/complaint_status_update` and queue it.

    Best-effort; sent to the original submitter when an admin changes the
    status of or posts a response to their complaint. Never raises.
    """
    if not email:
        return False
    try:
        from education_system.systems.university.infrastructure.email.template_utils import render_template
        subject, body = render_template('communications/complaint_status_update', full_vars)
        if not (subject and body):
            logger.warning("Empty complaint_status_update render for %s", email)
            return False
    except Exception:
        logger.exception("Failed to render complaint_status_update template")
        return False
    try:
        from education_system.systems.university.infrastructure.utils.email_service import queue_email
        ok = bool(queue_email(email, subject, body))
        if ok:
            logger.info("Queued complaint status update email to %s tracking_id=%s status=%s",
                        email, full_vars.get('tracking_id'), full_vars.get('status'))
        else:
            logger.warning("queue_email returned falsy for status update to %s", email)
        return ok
    except Exception:
        logger.exception("Failed to queue complaint status update email")
        return False


# ---------- Main Application ----------
class ComplaintsPortal(tk.Tk):
    def __init__(self, host=None):
        """Build the Complaints Portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess) — initialise as a ``tk.Tk``
            root and own the window/mainloop.
          * a workspace tab ``Frame`` (passed by ``open_in_workspace``)
            — skip Tk init and build all widgets onto the host frame.
            Caller owns the mainloop; ``mainloop()`` becomes a no-op.
        """
        if host is None:
            super().__init__()
            self.title("University Complaints Portal")
            self.geometry("900x650")
            self.configure(bg="#f0f4f8")
            self._host = self
            self._owns_root = True
        else:
            # Skip ``tk.Tk.__init__`` so we don't allocate a second
            # root window. Widgets parent to ``host`` instead of
            # ``self``.
            self._host = host
            self._owns_root = False
            try:
                host.configure(bg="#f0f4f8")
            except tk.TclError:
                pass

        self.current_user = _get_current_user()
        self.is_admin = _is_admin_user(self.current_user)
        logger.info("ComplaintsPortal starting user=%s role=%s admin=%s",
                    (self.current_user or {}).get('username') or
                    (self.current_user or {}).get('user_id') or '<anonymous>',
                    (self.current_user or {}).get('role') or '<none>',
                    self.is_admin)
        # Defer the initial DB read until after the window paints — the
        # Submit tab (the default) doesn't need it, so blocking the UI on
        # load_complaints() here just delays first paint.
        self.complaints = []

        self._configure_styles()
        self._build_header()
        self._build_notebook()

        self._host.after_idle(self._lazy_load_complaints)

    def mainloop(self, n: int = 0):
        """Embedded hosts own their own mainloop — no-op in that case."""
        if not self._owns_root:
            return
        super().mainloop(n)

    def _lazy_load_complaints(self):
        t0 = datetime.now()
        self.complaints = load_complaints()
        logger.debug("Lazy-loaded %d complaints in %.0fms",
                     len(self.complaints),
                     (datetime.now() - t0).total_seconds() * 1000)

    def _configure_styles(self):
        # ttk.Style is process-global even when given a master; embedded
        # in the main GUI workspace, base-style mutations (TNotebook,
        # TFrame, TLabel, TButton, Treeview) leak out. Use namespaced
        # styles for structural widgets and skip purely cosmetic
        # base-name overrides.
        style = ttk.Style(self._host)
        style.configure("Complaints.TNotebook", background="#f0f4f8", borderwidth=0)
        style.configure("Complaints.TNotebook.Tab", padding=[20, 10], font=("Segoe UI", 10, "bold"))
        style.map("Complaints.TNotebook.Tab",
                  background=[("selected", "#1e3a8a"), ("!selected", "#cbd5e1")],
                  foreground=[("selected", "white"), ("!selected", "#1e293b")])
        style.configure("Header.TLabel", background="#1e3a8a", foreground="white",
                        font=("Segoe UI", 18, "bold"), padding=15)
        style.configure("Submit.TButton", background="#1e3a8a", foreground="white")
        style.map("Submit.TButton", background=[("active", "#2563eb")])
        style.configure("Complaints.Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Complaints.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background="#1e3a8a", foreground="white")

    def _build_header(self):
        header = ttk.Label(self._host, text="🎓  University Complaints Portal",
                           style="Header.TLabel", anchor="center")
        header.pack(fill="x")

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self._host, style="Complaints.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        self.submit_tab = SubmitTab(self.notebook, self)
        self.view_tab = ViewTab(self.notebook, self)

        self.notebook.add(self.submit_tab, text="📝 Submit Complaint")
        self.notebook.add(self.view_tab, text="🔍 Track Complaint")

        if self.is_admin:
            self.admin_tab = AdminTab(self.notebook, self)
            self.notebook.add(self.admin_tab, text="⚙️ Admin Panel")
            self._admin_tab_index = self.notebook.index(self.admin_tab)
        else:
            self.admin_tab = None
            self._admin_tab_index = None
            logger.info("Admin tab hidden — current user is not an admin")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        selected = self.notebook.index("current")
        if self.admin_tab is not None and selected == self._admin_tab_index:
            self.admin_tab.refresh()

    def add_complaint(self, complaint):
        submitted_by = None
        if self.current_user:
            submitted_by = (str(self.current_user.get('id') or
                                self.current_user.get('user_id') or
                                self.current_user.get('username') or '') or None)
        if not insert_complaint(complaint, submitted_by=submitted_by):
            return False
        self.complaints = load_complaints()
        return True

    def update_complaint(self, complaint_id, status, response):
        if not update_complaint_row(complaint_id, status, response):
            return False
        self.complaints = load_complaints()
        return True

    def find_complaint(self, complaint_id):
        for c in self.complaints:
            if c["id"] == complaint_id:
                return c
        # Refresh once in case another process added it
        self.complaints = load_complaints()
        for c in self.complaints:
            if c["id"] == complaint_id:
                return c
        return None


# ---------- Submit Tab ----------
class SubmitTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build_form()
        self.after_idle(self._autofill_identity)

    def _autofill_identity(self):
        """Resolve and apply submitter identity after first paint.

        The lookup hits the DB; running it during `_build_form` blocks
        the window from appearing. Doing it via `after_idle` lets the
        form paint immediately, then fills the identity fields once the
        query returns (typically <200ms later).
        """
        try:
            full_name, student_id, email = _resolve_submitter_details(self.app.current_user)
        except Exception:
            logger.exception("Submitter identity autofill failed")
            return
        self._auto_filled = bool(full_name or student_id or email)
        if full_name:
            self.name_entry.insert(0, full_name)
        if student_id:
            self.id_entry.insert(0, student_id)
        if email:
            self.email_entry.insert(0, email)
        if self._auto_filled:
            for entry in (self.name_entry, self.id_entry, self.email_entry):
                entry.config(state="readonly")
            self._autofill_notice.config(
                text="(identity fields are filled from your account and cannot be changed)")

    def _build_form(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=40, pady=20)

        ttk.Label(container, text="Submit a New Complaint",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 20))

        # Identity fields are autofilled in the background — see
        # `_autofill_identity` — to keep first paint snappy. Until that
        # runs we leave them empty and start unlocked; once filled, they
        # get marked readonly.
        self._auto_filled = False

        # Name
        ttk.Label(container, text="Full Name *").grid(row=1, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Student ID
        ttk.Label(container, text="Student/Staff ID *").grid(row=2, column=0, sticky="w", pady=5)
        self.id_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.id_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Email
        ttk.Label(container, text="Email Address *").grid(row=3, column=0, sticky="w", pady=5)
        self.email_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.email_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Placeholder for the autofill notice; populated by _autofill_identity.
        self._autofill_notice = ttk.Label(
            container, text="", font=("Segoe UI", 8, "italic"),
            foreground="#64748b")
        self._autofill_notice.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Category
        ttk.Label(container, text="Category *").grid(row=5, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        categories = ["Academic", "Facilities", "Hostel/Accommodation", "Library",
                      "IT Services", "Food Services", "Transportation",
                      "Harassment/Discrimination", "Financial/Fees", "Other"]
        self.category_menu = ttk.Combobox(container, textvariable=self.category_var,
                                          values=categories, state="readonly",
                                          font=("Segoe UI", 10))
        self.category_menu.grid(row=5, column=1, sticky="ew", pady=5, padx=(10, 0))
        self.category_menu.current(0)

        # Priority
        ttk.Label(container, text="Priority *").grid(row=6, column=0, sticky="w", pady=5)
        self.priority_var = tk.StringVar(value="Medium")
        priority_frame = ttk.Frame(container)
        priority_frame.grid(row=6, column=1, sticky="w", pady=5, padx=(10, 0))
        for level in ["Low", "Medium", "High", "Urgent"]:
            ttk.Radiobutton(priority_frame, text=level, variable=self.priority_var,
                            value=level).pack(side="left", padx=5)

        # Subject
        ttk.Label(container, text="Subject *").grid(row=7, column=0, sticky="w", pady=5)
        self.subject_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.subject_entry.grid(row=7, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Description
        ttk.Label(container, text="Description *").grid(row=8, column=0, sticky="nw", pady=5)
        self.desc_text = scrolledtext.ScrolledText(container, width=50, height=8,
                                                    font=("Segoe UI", 10), wrap="word")
        self.desc_text.grid(row=8, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit Complaint", style="Submit.TButton",
                   command=self.submit).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear Form",
                   command=self.clear).pack(side="left", padx=5)

        container.columnconfigure(1, weight=1)

    def submit(self):
        name = self.name_entry.get().strip()
        user_id = self.id_entry.get().strip()
        email = self.email_entry.get().strip()
        category = self.category_var.get()
        priority = self.priority_var.get()
        subject = self.subject_entry.get().strip()
        description = self.desc_text.get("1.0", "end").strip()

        if not all([name, user_id, email, subject, description]):
            logger.warning("Complaint submit blocked — missing required field(s)")
            messagebox.showerror("Validation Error",
                                 "Please fill in all required fields (*)")
            return

        if "@" not in email or "." not in email:
            logger.warning("Complaint submit blocked — invalid email %r", email)
            messagebox.showerror("Validation Error", "Please enter a valid email address.")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        complaint = {
            "id": str(uuid.uuid4())[:8].upper(),
            "name": name,
            "user_id": user_id,
            "email": email,
            "category": category,
            "priority": priority,
            "subject": subject,
            "description": description,
            "status": "Pending",
            "response": "",
            "submitted": now,
            "updated": now,
        }

        if not self.app.add_complaint(complaint):
            logger.error("add_complaint failed for tracking_id=%s", complaint['id'])
            messagebox.showerror(
                "Save Failed",
                "Could not save complaint to the database. Please try again.")
            return

        # Queue confirmation receipt — best-effort.
        emailed = _send_complaint_confirmation(email, {
            'student_name': name,
            'student_id': str(user_id),
            'tracking_id': complaint['id'],
            'subject': subject,
            'category': category,
            'priority': priority,
            'submitted_at': now,
        })

        msg = (f"Complaint submitted successfully!\n\n"
               f"Your Tracking ID: {complaint['id']}\n\n"
               f"Please save this ID to track your complaint.")
        if emailed:
            msg += f"\n\nA confirmation email has been sent to {email}."
        messagebox.showinfo("Success", msg)
        self.clear()

    def clear(self):
        # Don't wipe locked identity fields — only the complaint content.
        if not self._auto_filled:
            self.name_entry.delete(0, "end")
            self.id_entry.delete(0, "end")
            self.email_entry.delete(0, "end")
        self.subject_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")
        self.category_menu.current(0)
        self.priority_var.set("Medium")


# ---------- View/Track Tab ----------
class ViewTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=40, pady=20)

        ttk.Label(container, text="Track Your Complaint",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 15))

        search_frame = ttk.Frame(container)
        search_frame.pack(fill="x", pady=10)
        ttk.Label(search_frame, text="Enter Tracking ID:").pack(side="left")
        self.track_entry = ttk.Entry(search_frame, width=20, font=("Segoe UI", 10))
        self.track_entry.pack(side="left", padx=10)
        ttk.Button(search_frame, text="Search", style="Submit.TButton",
                   command=self.search).pack(side="left")

        self.result_text = scrolledtext.ScrolledText(container, height=20,
                                                     font=("Consolas", 10),
                                                     wrap="word", bg="white")
        self.result_text.pack(fill="both", expand=True, pady=15)
        self.result_text.config(state="disabled")

    def search(self):
        cid = self.track_entry.get().strip().upper()
        if not cid:
            messagebox.showwarning("Input Error", "Please enter a tracking ID.")
            return

        complaint = self.app.find_complaint(cid)
        logger.info("Track lookup id=%s found=%s", cid, bool(complaint))
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")

        if complaint:
            status_color = {
                "Pending": "🟡",
                "In Progress": "🔵",
                "Resolved": "🟢",
                "Rejected": "🔴",
            }.get(complaint["status"], "⚪")

            info = f"""
╔══════════════════════════════════════════════════════════════╗
║                    COMPLAINT DETAILS                         ║
╚══════════════════════════════════════════════════════════════╝

Tracking ID    : {complaint['id']}
Status         : {status_color} {complaint['status']}
Priority       : {complaint['priority']}
Category       : {complaint['category']}

─────────────────── Submitter Information ───────────────────
Name           : {complaint['name']}
Student/Staff ID: {complaint['user_id']}
Email          : {complaint['email']}

─────────────────────── Complaint ────────────────────────────
Subject        : {complaint['subject']}

Description    :
{complaint['description']}

──────────────────── Admin Response ──────────────────────────
{complaint['response'] if complaint['response'] else '(No response yet)'}

─────────────────────── Timeline ─────────────────────────────
Submitted      : {complaint['submitted']}
Last Updated   : {complaint['updated']}
"""
            self.result_text.insert("1.0", info)
        else:
            self.result_text.insert("1.0",
                                    f"\n  No complaint found with ID: {cid}\n\n"
                                    f"  Please verify your tracking ID and try again.")

        self.result_text.config(state="disabled")


# ---------- Admin Tab ----------
class AdminTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        # Admin tab is only constructed for admin users (gated in
        # ComplaintsPortal._build_notebook), so the logged-in session is
        # already authenticated — no separate password prompt needed.
        self.authenticated = True
        logger.info("AdminTab opened by user=%s role=%s",
                    (app.current_user or {}).get('username') or
                    (app.current_user or {}).get('user_id') or '<unknown>',
                    (app.current_user or {}).get('role') or '<none>')
        self._build_dashboard()

    def _build_dashboard(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Stats bar
        self.stats_frame = ttk.Frame(container)
        self.stats_frame.pack(fill="x", pady=(0, 10))

        # Filter bar
        filter_frame = ttk.Frame(container)
        filter_frame.pack(fill="x", pady=5)
        ttk.Label(filter_frame, text="Filter by Status:").pack(side="left", padx=5)
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                     values=["All", "Pending", "In Progress", "Resolved", "Rejected"],
                                     state="readonly", width=15)
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(filter_frame, text="🔄 Refresh", command=self.refresh).pack(side="left", padx=5)

        # Treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Name", "Category", "Priority", "Subject", "Status", "Date")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12, style="Complaints.Treeview")

        widths = {"ID": 90, "Name": 140, "Category": 130, "Priority": 80,
                  "Subject": 200, "Status": 100, "Date": 130}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.open_complaint)

        # Action buttons
        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=10)
        ttk.Button(action_frame, text="View/Update Selected", style="Submit.TButton",
                   command=lambda: self.open_complaint(None)).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Delete Selected",
                   command=self.delete_complaint).pack(side="left", padx=5)

        # Configure row tags for status colors
        self.tree.tag_configure("Pending", background="#fef3c7")
        self.tree.tag_configure("In Progress", background="#dbeafe")
        self.tree.tag_configure("Resolved", background="#d1fae5")
        self.tree.tag_configure("Rejected", background="#fee2e2")

    def refresh(self):
        if not self.authenticated:
            return

        # Reload from DB so admin sees the live picture.
        self.app.complaints = load_complaints()

        # Update stats
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        complaints = self.app.complaints
        total = len(complaints)
        pending = sum(1 for c in complaints if c["status"] == "Pending")
        in_progress = sum(1 for c in complaints if c["status"] == "In Progress")
        resolved = sum(1 for c in complaints if c["status"] == "Resolved")
        rejected = sum(1 for c in complaints if c["status"] == "Rejected")

        stats = [
            ("Total", total, "#1e3a8a"),
            ("Pending", pending, "#d97706"),
            ("In Progress", in_progress, "#2563eb"),
            ("Resolved", resolved, "#059669"),
            ("Rejected", rejected, "#dc2626"),
        ]

        for label, value, color in stats:
            card = tk.Frame(self.stats_frame, bg=color, padx=15, pady=10)
            card.pack(side="left", padx=5, fill="x", expand=True)
            tk.Label(card, text=str(value), bg=color, fg="white",
                     font=("Segoe UI", 16, "bold")).pack()
            tk.Label(card, text=label, bg=color, fg="white",
                     font=("Segoe UI", 9)).pack()

        # Refresh tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_status = self.filter_var.get()
        for c in complaints:
            if filter_status != "All" and c["status"] != filter_status:
                continue
            self.tree.insert("", "end", values=(
                c["id"], c["name"], c["category"], c["priority"],
                c["subject"][:40] + ("..." if len(c["subject"]) > 40 else ""),
                c["status"], c["submitted"]
            ), tags=(c["status"],))

    def open_complaint(self, event):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a complaint first.")
            return

        cid = self.tree.item(selection[0])["values"][0]
        complaint = self.app.find_complaint(cid)
        if complaint:
            logger.info("Admin opening complaint id=%s", cid)
            ComplaintDetailWindow(self, self.app, complaint)
        else:
            logger.warning("Admin tried to open missing complaint id=%s", cid)

    def delete_complaint(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a complaint first.")
            return

        cid = self.tree.item(selection[0])["values"][0]
        if messagebox.askyesno("Confirm Delete",
                               f"Delete complaint {cid}? This cannot be undone."):
            actor = ((self.app.current_user or {}).get('username') or
                     (self.app.current_user or {}).get('user_id') or '<unknown>')
            logger.info("Admin %s deleting complaint id=%s", actor, cid)
            if not delete_complaint_row(cid):
                messagebox.showerror("Delete failed",
                                     "Could not delete complaint from the database.")
                return
            self.app.complaints = load_complaints()
            self.refresh()
            messagebox.showinfo("Deleted", "Complaint deleted successfully.")


# ---------- Complaint Detail Window ----------
class ComplaintDetailWindow(tk.Toplevel):
    def __init__(self, parent, app, complaint):
        super().__init__(parent)
        self.app = app
        self.complaint = complaint
        self.parent_tab = parent

        self.title(f"Complaint {complaint['id']}")
        self.geometry("600x600")
        self.configure(bg="#f0f4f8")
        self.transient(parent)

        self._build()

        self.wait_visibility()
        self.grab_set()

    def _build(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(container, text=f"Complaint #{self.complaint['id']}",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")

        info = f"""Submitter: {self.complaint['name']} ({self.complaint['user_id']})
Email: {self.complaint['email']}
Category: {self.complaint['category']}  |  Priority: {self.complaint['priority']}
Submitted: {self.complaint['submitted']}  |  Updated: {self.complaint['updated']}

Subject: {self.complaint['subject']}"""
        ttk.Label(container, text=info, justify="left",
                  font=("Segoe UI", 10)).pack(anchor="w", pady=10)

        ttk.Label(container, text="Description:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        desc_box = scrolledtext.ScrolledText(container, height=6, wrap="word",
                                              font=("Segoe UI", 10))
        desc_box.pack(fill="x", pady=5)
        desc_box.insert("1.0", self.complaint["description"])
        desc_box.config(state="disabled")

        ttk.Label(container, text="Status:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.status_var = tk.StringVar(value=self.complaint["status"])
        status_combo = ttk.Combobox(container, textvariable=self.status_var,
                                     values=["Pending", "In Progress", "Resolved", "Rejected"],
                                     state="readonly")
        status_combo.pack(fill="x", pady=5)

        ttk.Label(container, text="Admin Response:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.response_box = scrolledtext.ScrolledText(container, height=6, wrap="word",
                                                      font=("Segoe UI", 10))
        self.response_box.pack(fill="x", pady=5)
        self.response_box.insert("1.0", self.complaint["response"])

        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save Changes", style="Submit.TButton",
                   command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close",
                   command=self.destroy).pack(side="left", padx=5)

    def save(self):
        status = self.status_var.get()
        response = self.response_box.get("1.0", "end").strip()
        actor = ((self.app.current_user or {}).get('username') or
                 (self.app.current_user or {}).get('user_id') or '<unknown>')
        prev_status = self.complaint.get('status', '')
        prev_response = self.complaint.get('response', '') or ''
        logger.info("Admin %s saving complaint id=%s status=%s response_len=%d",
                    actor, self.complaint['id'], status, len(response))
        if not self.app.update_complaint(self.complaint["id"], status, response):
            messagebox.showerror("Save Failed",
                                 "Could not save changes to the database.")
            return

        # Notify the submitter if the status changed or a response was
        # added/edited. Best-effort — don't block the admin save flow.
        emailed = False
        if status != prev_status or response != prev_response:
            updated = self.app.find_complaint(self.complaint['id']) or self.complaint
            emailed = _send_complaint_status_update(updated.get('email', ''), {
                'student_name': updated.get('name', ''),
                'student_id': str(updated.get('user_id', '')),
                'tracking_id': updated.get('id', ''),
                'subject': updated.get('subject', ''),
                'category': updated.get('category', ''),
                'priority': updated.get('priority', ''),
                'status': status,
                'response': response or '(no admin response provided)',
                'updated_at': updated.get('updated', ''),
            })

        self.parent_tab.refresh()
        msg = "Complaint updated successfully."
        if emailed:
            msg += f"\n\nA status update email has been sent to {self.complaint.get('email', 'the submitter')}."
        messagebox.showinfo("Saved", msg)
        self.destroy()


# ---------- Entry Point ----------
if __name__ == "__main__":
    app = ComplaintsPortal()
    app.mainloop()
