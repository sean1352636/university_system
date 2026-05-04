"""
University Portal Safeguarding System
--------------------------------------
A GUI application that screens messages/posts submitted through a
university portal for safeguarding concerns (self-harm, bullying,
harassment, exploitation, academic distress, etc.) and routes flagged
content to the appropriate support team.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. There is no in-app login screen. Users
with role=='student' see the submission form; everyone else (staff,
instructor, admin, dsl, ...) gets the staff review console.

Persistence: rows live in the central `student_records.db` table
`safeguarding_submissions`. The legacy local `safeguarding.db` file
is removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.

NOTE: This is an educational/demonstration tool. A real safeguarding
system requires trained professionals, robust NLP (not keyword matching),
compliance with GDPR/Data Protection law, and integration with
institutional safeguarding policy.
"""

import json
import logging
import os
import re
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext


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


logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "safeguarding.db")


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    full_name = os.environ.get('EDU_AUTH_FULL_NAME') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or username,
            'user_id': user_id or username,
            'username': username or user_id,
            'role': role or 'student',
            'email': email,
            'full_name': full_name or username or user_id or 'Unknown User',
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            u = dict(ga.current_user)
            u.setdefault('full_name', u.get('username', 'Unknown User'))
            u.setdefault('role', 'student')
            return u
        return None
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_staff_role(role: str) -> bool:
    """Anyone who isn't a student sees the staff review console."""
    return (role or '').lower() not in ('student', '', 'guest')


# ---------------------------------------------------------------------------
# Risk classification engine
# ---------------------------------------------------------------------------

class RiskCategory:
    SELF_HARM       = "Self-harm / Suicide"
    MENTAL_HEALTH   = "Mental Health"
    BULLYING        = "Bullying / Harassment"
    EXPLOITATION    = "Exploitation / Abuse"
    SUBSTANCE       = "Substance Misuse"
    ACADEMIC        = "Academic Distress"
    DISCRIMINATION  = "Discrimination / Hate"
    EXTREMISM       = "Radicalisation Concern"


# Keyword patterns grouped by concern category. Using word-boundary
# regexes to reduce false positives (e.g. "kill" matching "skill").
RISK_PATTERNS = {
    RiskCategory.SELF_HARM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bkill\s+myself\b", r"\bend\s+(it|my\s+life)\b",
            r"\bsuicid\w*\b", r"\bself[\s-]?harm\b", r"\bcut\s+myself\b",
            r"\bdon't\s+want\s+to\s+(live|be\s+here)\b",
            r"\bwant\s+to\s+die\b", r"\bno\s+reason\s+to\s+live\b",
            r"\boverdos\w*\b",
        ],
    },
    RiskCategory.MENTAL_HEALTH: {
        "severity": "HIGH",
        "patterns": [
            r"\bdepress\w*\b", r"\banxiety\b", r"\bpanic\s+attack\b",
            r"\bcan't\s+cope\b", r"\bhopeless\b", r"\bworthless\b",
            r"\bbreakdown\b", r"\bmental\s+health\b", r"\bisolat\w+\b",
            r"\bcrying\s+(all|every)\b",
        ],
    },
    RiskCategory.BULLYING: {
        "severity": "HIGH",
        "patterns": [
            r"\bbull(y|ied|ying)\b", r"\bharass\w*\b", r"\bthreaten\w*\b",
            r"\bstalk\w*\b", r"\bintimidat\w*\b", r"\bhate\s+me\b",
            r"\bmaking\s+fun\s+of\s+me\b", r"\bpicking\s+on\s+me\b",
        ],
    },
    RiskCategory.EXPLOITATION: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bassault\w*\b", r"\brape\w*\b", r"\bgroom\w*\b",
            r"\bcoerc\w*\b", r"\bforc\w+\s+(me|to)\b",
            r"\binappropriate\s+touch\w*\b", r"\bsexual\s+abuse\b",
            r"\bdomestic\s+(abuse|violence)\b",
        ],
    },
    RiskCategory.SUBSTANCE: {
        "severity": "MEDIUM",
        "patterns": [
            r"\bdrunk\s+every\b", r"\baddict\w*\b", r"\boverdose\b",
            r"\bdrug\s+problem\b", r"\balcohol\s+problem\b",
            r"\bcan't\s+stop\s+drinking\b",
        ],
    },
    RiskCategory.ACADEMIC: {
        "severity": "LOW",
        "patterns": [
            r"\bfail\w+\s+(everything|all)\b", r"\bdrop\s+out\b",
            r"\bquit\s+uni\w*\b", r"\bcan't\s+keep\s+up\b",
            r"\boverwhelmed\b", r"\btoo\s+much\s+pressure\b",
            r"\bburn\s?out\b",
        ],
    },
    RiskCategory.DISCRIMINATION: {
        "severity": "HIGH",
        "patterns": [
            r"\bracis\w*\b", r"\bsexis\w*\b", r"\bhomophob\w*\b",
            r"\btransphob\w*\b", r"\bdiscriminat\w*\b",
            r"\bhate\s+crime\b", r"\bslur\w*\b",
        ],
    },
    RiskCategory.EXTREMISM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bradicali[sz]\w*\b", r"\bextremis\w*\b",
            r"\bterroris\w*\b", r"\bjoin\s+a\s+cause\b",
        ],
    },
}

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SEVERITY_COLOUR = {
    "LOW":      "#f5c518",
    "MEDIUM":   "#f38b00",
    "HIGH":     "#d9480f",
    "CRITICAL": "#b00020",
    "NONE":     "#2e7d32",
}


def analyse_text(text: str):
    """Return a dict of {category: [matched_snippets]} and overall severity."""
    text_lower = text.lower()
    matches = {}

    for category, cfg in RISK_PATTERNS.items():
        hits = []
        for pattern in cfg["patterns"]:
            for m in re.finditer(pattern, text_lower):
                # Capture a little surrounding context for the reviewer
                start = max(0, m.start() - 25)
                end   = min(len(text_lower), m.end() + 25)
                hits.append("…" + text_lower[start:end].strip() + "…")
        if hits:
            matches[category] = {
                "severity": cfg["severity"],
                "snippets": hits,
            }

    # Overall severity = highest across all categories
    if not matches:
        overall = "NONE"
    else:
        overall = max(
            (m["severity"] for m in matches.values()),
            key=lambda s: SEVERITY_ORDER[s],
        )

    return matches, overall


# ---------------------------------------------------------------------------
# Persistence layer — central student_records.db
# ---------------------------------------------------------------------------


def _connect():
    from education_system.university_system.infrastructure.database.db import get_connection
    return get_connection()


def init_db():
    """Create the safeguarding_submissions table if missing.

    The previous schema split data across `users` and `submissions`
    tables in a per-module DB. Auth now comes from EDU_AUTH_* env vars
    so there's no need for a local users table — we record the
    submitter's username / full_name / role inline with each row.
    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_submissions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            full_name    TEXT,
            role         TEXT,
            content      TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            severity     TEXT NOT NULL,
            categories   TEXT NOT NULL,      -- JSON
            status       TEXT NOT NULL DEFAULT 'Pending',
            reviewer     TEXT,
            review_note  TEXT,
            reviewed_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_submission(user, content, severity, categories):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_submissions"
        "(username, full_name, role, content, submitted_at, severity, categories) "
        "VALUES (?,?,?,?,?,?,?)",
        (user.get('username') or '', user.get('full_name') or '',
         user.get('role') or '', content,
         datetime.now().isoformat(), severity, json.dumps(categories)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def fetch_submissions(status_filter=None, severity_filter=None):
    """Return rows shaped like the previous version expected:
    (id, full_name, username, submitted_at, severity, categories,
     status, content, reviewer, review_note, reviewed_at)."""
    conn = _connect()
    cur = conn.cursor()
    q = """SELECT id, full_name, username, submitted_at,
                  severity, categories, status, content,
                  reviewer, review_note, reviewed_at
           FROM safeguarding_submissions WHERE 1=1"""
    params = []
    if status_filter and status_filter != "All":
        q += " AND status = ?"
        params.append(status_filter)
    if severity_filter and severity_filter != "All":
        q += " AND severity = ?"
        params.append(severity_filter)
    q += " ORDER BY CASE severity " \
         "WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 " \
         "WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END, " \
         "submitted_at DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_submission_status(sub_id, status, reviewer, note):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET status=?, reviewer=?, review_note=?, reviewed_at=? "
        "WHERE id=?",
        (status, reviewer, note, datetime.now().isoformat(), sub_id),
    )
    conn.commit()
    conn.close()


def fetch_user_submissions(username):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status FROM safeguarding_submissions "
        "WHERE username=? ORDER BY submitted_at DESC",
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _remove_legacy_db():
    """Delete the old per-module safeguarding.db (and WAL/SHM siblings)
    — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy safeguarding DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

SUPPORT_RESOURCES = """If you are struggling right now, please reach out:

  • Samaritans (UK)   116 123  — free, 24/7
  • Nightline (student peer support)  — nightline.ac.uk
  • University Wellbeing Service      — contact via portal
  • Emergency services                — 999 / 112

You are not alone. Speaking to someone can help."""


class SafeguardingApp(tk.Tk):
    def __init__(self, host=None):
        """Build the Safeguarding portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess) — initialise as a ``tk.Tk``
            root and own the window/mainloop.
          * a workspace tab ``Frame`` (passed by ``open_in_workspace``)
            — skip Tk init and build widgets onto the host frame.
            ``mainloop()`` becomes a no-op (caller owns it).

        Same shape as ComplaintsPortal (8.117.49).
        """
        if host is None:
            super().__init__()
            self.title("University Portal — Safeguarding System")
            self.geometry("1000x680")
            self.configure(bg="#f4f6fa")
            self._host = self
            self._owns_root = True
        else:
            self._host = host
            self._owns_root = False
            try:
                host.configure(bg="#f4f6fa")
            except tk.TclError:
                pass

        self.user = _get_current_user()

        # ttk theming — process-global style; only configure named styles
        # to avoid leaking into the host main GUI when embedded.
        style = ttk.Style(self._host)
        style.configure("Header.TLabel",
                        font=("Segoe UI", 16, "bold"),
                        background="#f4f6fa")
        style.configure("Sub.TLabel",
                        font=("Segoe UI", 10),
                        background="#f4f6fa", foreground="#555")

        self.container = tk.Frame(self._host, bg="#f4f6fa")
        self.container.pack(fill="both", expand=True)

        if not self.user:
            self.show_no_auth()
        elif _is_staff_role(self.user.get('role')):
            logger.info("Safeguarding starting console=staff user=%s role=%s",
                        self.user.get('username'), self.user.get('role'))
            self.show_staff_dashboard()
        else:
            logger.info("Safeguarding starting console=student user=%s role=%s",
                        self.user.get('username'), self.user.get('role'))
            self.show_student_dashboard()

    # ---------- embedded-mode shims ----------
    # When ``host`` was supplied, ``super().__init__()`` was skipped,
    # so any inherited ``tk.Misc`` method that touches ``self.tk``
    # (mainloop / destroy / bind / unbind) crashes. Redirect those
    # calls to the host frame.
    def mainloop(self, n: int = 0):
        if not self._owns_root:
            return
        super().mainloop(n)

    def destroy(self):
        if self._owns_root:
            super().destroy()
        else:
            try:
                self._host.destroy()
            except tk.TclError:
                pass

    def unbind(self, sequence, funcid=None):
        try:
            return self._host.unbind(sequence, funcid)
        except tk.TclError:
            pass

    def bind(self, sequence=None, func=None, add=None):
        return self._host.bind(sequence, func, add)

    # ---------- helpers ----------
    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    # ---------- no-auth fallback ----------
    def show_no_auth(self):
        self._clear()
        frame = tk.Frame(self.container, bg="#f4f6fa")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(frame, text="🔒 Authentication Required",
                  style="Header.TLabel").pack(pady=(0, 8))
        ttk.Label(frame,
                  text="Please launch this portal from the main\n"
                       "University System after signing in.",
                  style="Sub.TLabel", justify="center").pack(pady=(0, 14))
        ttk.Button(frame, text="Close",
                   command=self.destroy).pack()

    # ---------- student dashboard ----------
    def show_student_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        self._build_topbar(f"Welcome, {self.user['full_name']}")

        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        left  = tk.Frame(body, bg="#f4f6fa")
        right = tk.Frame(body, bg="#f4f6fa", width=300)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y", padx=(15, 0))

        # --- Submission form ---
        ttk.Label(left, text="Share a concern or message",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(left,
                  text="Your submission will be reviewed by the wellbeing team.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 10))

        box = tk.Frame(left, bg="white", bd=1, relief="solid")
        box.pack(fill="both", expand=True)

        self.txt_input = scrolledtext.ScrolledText(
            box, wrap="word", font=("Segoe UI", 11),
            relief="flat", padx=10, pady=10, height=15,
        )
        self.txt_input.pack(fill="both", expand=True)

        btn_row = tk.Frame(left, bg="#f4f6fa")
        btn_row.pack(fill="x", pady=10)
        ttk.Button(btn_row, text="Submit",
                   command=self._student_submit).pack(side="left")
        ttk.Button(btn_row, text="Clear",
                   command=lambda: self.txt_input.delete("1.0", "end")
                   ).pack(side="left", padx=6)

        # --- Right column: history + support ---
        ttk.Label(right, text="Your recent submissions",
                  style="Sub.TLabel").pack(anchor="w")
        self.history_list = tk.Listbox(right, width=40, height=10,
                                       font=("Segoe UI", 9))
        self.history_list.pack(fill="x", pady=(2, 15))
        self._refresh_student_history()

        support = tk.Frame(right, bg="#eaf4ec", bd=1, relief="solid")
        support.pack(fill="x")
        tk.Label(support, text="Need help now?", bg="#eaf4ec",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                    padx=10, pady=(8, 4))
        tk.Label(support, text=SUPPORT_RESOURCES, bg="#eaf4ec",
                 justify="left", font=("Segoe UI", 9),
                 wraplength=280).pack(anchor="w", padx=10, pady=(0, 10))

    def _refresh_student_history(self):
        self.history_list.delete(0, "end")
        for sid, ts, sev, status in fetch_user_submissions(
                self.user.get("username") or ""):
            date = ts.split("T")[0]
            self.history_list.insert(
                "end", f"#{sid}  {date}   {sev:<8}  {status}")

    def _student_submit(self):
        text = self.txt_input.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Empty", "Please write something before submitting.")
            return

        matches, overall = analyse_text(text)
        categories = {cat: info["snippets"] for cat, info in matches.items()}
        sid = save_submission(self.user, text, overall, categories)
        logger.info("Safeguarding submission saved id=%s severity=%s user=%s categories=%s",
                    sid, overall, self.user.get('username'),
                    list(categories.keys()))

        # If severity is critical, strongly surface support info to the user
        if overall == "CRITICAL":
            messagebox.showwarning(
                "We're here for you",
                "Thank you for reaching out. A member of the safeguarding "
                "team has been alerted and will contact you as soon as "
                "possible.\n\n" + SUPPORT_RESOURCES,
            )
        elif overall in ("HIGH", "MEDIUM"):
            messagebox.showinfo(
                "Submitted",
                "Your submission has been received and flagged for review "
                "by the wellbeing team. They may be in touch.\n\n"
                + SUPPORT_RESOURCES,
            )
        else:
            messagebox.showinfo(
                "Submitted",
                f"Thank you. Your submission #{sid} has been received.",
            )

        self.txt_input.delete("1.0", "end")
        self._refresh_student_history()

    # ---------- staff dashboard ----------
    def show_staff_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        self._build_topbar(f"Staff console — {self.user['full_name']}")

        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        # Filters
        filt = tk.Frame(body, bg="#f4f6fa")
        filt.pack(fill="x", pady=(0, 8))

        tk.Label(filt, text="Status:", bg="#f4f6fa").pack(side="left")
        self.status_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.status_var,
                     values=["All", "Pending", "In progress", "Closed"],
                     state="readonly", width=12
                     ).pack(side="left", padx=(4, 15))

        tk.Label(filt, text="Severity:", bg="#f4f6fa").pack(side="left")
        self.sev_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.sev_var,
                     values=["All", "CRITICAL", "HIGH",
                             "MEDIUM", "LOW", "NONE"],
                     state="readonly", width=12
                     ).pack(side="left", padx=(4, 15))

        ttk.Button(filt, text="Refresh",
                   command=self._refresh_staff_list).pack(side="left")

        # Split: list on left, detail on right
        split = tk.Frame(body, bg="#f4f6fa")
        split.pack(fill="both", expand=True)

        list_frame = tk.Frame(split, bg="#f4f6fa")
        list_frame.pack(side="left", fill="both", expand=True)

        columns = ("id", "student", "submitted", "severity", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns,
                                 show="headings", height=20)
        for col, w in zip(columns, (50, 180, 140, 100, 100)):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # Severity row colours
        for sev, col in SEVERITY_COLOUR.items():
            self.tree.tag_configure(sev, background=col,
                                    foreground="white" if sev != "LOW" else "black")

        self.tree.bind("<<TreeviewSelect>>", self._on_select_submission)

        # Detail panel
        self.detail = tk.Frame(split, bg="white", bd=1, relief="solid",
                               width=420)
        self.detail.pack(side="right", fill="both", padx=(12, 0))
        self.detail.pack_propagate(False)
        self._render_empty_detail()

        self._refresh_staff_list()

    def _refresh_staff_list(self):
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = fetch_submissions(self.status_var.get(), self.sev_var.get())
        self._rows_cache = {r[0]: r for r in rows}
        for r in rows:
            sid, name, username, ts, sev, _cats, status, *_ = r
            self.tree.insert(
                "", "end", iid=str(sid),
                values=(sid, f"{name} ({username})",
                        ts.replace("T", " ")[:16], sev, status),
                tags=(sev,),
            )

    def _render_empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        tk.Label(self.detail, text="Select a submission to review.",
                 bg="white", fg="#888",
                 font=("Segoe UI", 10)).pack(expand=True)

    def _on_select_submission(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        sid = int(sel[0])
        row = self._rows_cache[sid]
        (sid, name, username, ts, sev, cats_json,
         status, content, reviewer, note, reviewed_at) = row

        for w in self.detail.winfo_children():
            w.destroy()

        pad = dict(padx=12, pady=4)

        tk.Label(self.detail, text=f"Submission #{sid}",
                 bg="white", font=("Segoe UI", 13, "bold")
                 ).pack(anchor="w", padx=12, pady=(12, 0))

        # Severity badge
        badge = tk.Label(self.detail, text=f" {sev} ",
                         bg=SEVERITY_COLOUR.get(sev, "#666"), fg="white",
                         font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        badge.pack(anchor="w", padx=12, pady=(4, 8))

        meta = (f"Student: {name} ({username})\n"
                f"Submitted: {ts.replace('T', ' ')[:19]}\n"
                f"Status: {status}")
        if reviewer:
            meta += f"\nLast reviewed by: {reviewer} at {reviewed_at[:19]}"
        tk.Label(self.detail, text=meta, bg="white", justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", **pad)

        # Flagged categories
        cats = json.loads(cats_json)
        if cats:
            tk.Label(self.detail, text="Flagged categories:",
                     bg="white", font=("Segoe UI", 9, "bold")
                     ).pack(anchor="w", **pad)
            for cat, snippets in cats.items():
                tk.Label(self.detail, text=f"• {cat}",
                         bg="white", font=("Segoe UI", 9),
                         fg="#b00020").pack(anchor="w", padx=24)
                for snip in snippets[:3]:
                    tk.Label(self.detail, text=f"   “{snip}”",
                             bg="white", font=("Segoe UI", 8),
                             fg="#555", wraplength=380, justify="left"
                             ).pack(anchor="w", padx=24)
        else:
            tk.Label(self.detail, text="No automated flags.",
                     bg="white", fg="#2e7d32",
                     font=("Segoe UI", 9)).pack(anchor="w", **pad)

        # Original content
        tk.Label(self.detail, text="Content:", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        content_box = scrolledtext.ScrolledText(
            self.detail, wrap="word", height=6,
            font=("Segoe UI", 9), bg="#fafafa")
        content_box.insert("1.0", content)
        content_box.config(state="disabled")
        content_box.pack(fill="x", padx=12, pady=4)

        # Review actions
        tk.Label(self.detail, text="Review note:", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        note_box = tk.Text(self.detail, height=3, font=("Segoe UI", 9))
        if note:
            note_box.insert("1.0", note)
        note_box.pack(fill="x", padx=12)

        actions = tk.Frame(self.detail, bg="white")
        actions.pack(fill="x", padx=12, pady=10)

        def set_status(new_status):
            update_submission_status(
                sid, new_status, self.user["full_name"],
                note_box.get("1.0", "end").strip(),
            )
            logger.info("Safeguarding submission %s status->%s by %s",
                        sid, new_status, self.user.get('username'))
            messagebox.showinfo("Updated",
                                f"Submission #{sid} marked as '{new_status}'.")
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(actions, text="Mark In progress",
                   command=lambda: set_status("In progress")
                   ).pack(side="left", padx=2)
        ttk.Button(actions, text="Close case",
                   command=lambda: set_status("Closed")
                   ).pack(side="left", padx=2)
        ttk.Button(actions, text="Escalate (Critical)",
                   command=lambda: [
                       update_submission_status(
                           sid, "In progress", self.user["full_name"],
                           (note_box.get("1.0", "end").strip()
                            + "\n[ESCALATED]").strip()),
                       logger.warning("Safeguarding submission %s ESCALATED by %s",
                                      sid, self.user.get('username')),
                       messagebox.showwarning(
                           "Escalated",
                           "Case escalated to senior safeguarding lead. "
                           "In a real deployment this would page the "
                           "duty officer and notify Designated Safeguarding "
                           "Lead (DSL)."),
                       self._refresh_staff_list(),
                       self._render_empty_detail(),
                   ]).pack(side="left", padx=2)

    # ---------- top bar ----------
    def _build_topbar(self, title):
        bar = tk.Frame(self.container, bg="#1f3a5f", height=55)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text=title, bg="#1f3a5f", fg="white",
                 font=("Segoe UI", 12, "bold")).pack(side="left",
                                                    padx=20)
        role = (self.user or {}).get('role') or '—'
        tk.Label(bar,
                 text=f"Signed in: {(self.user or {}).get('username') or 'Guest'}  ({role})",
                 bg="#1f3a5f", fg="#cfe0ff",
                 font=("Segoe UI", 9)).pack(side="right", padx=20)


# ---------------------------------------------------------------------------

def main():
    _remove_legacy_db()
    init_db()
    app = SafeguardingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
