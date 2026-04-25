"""
University Portal Safeguarding System
--------------------------------------
A demonstration GUI application that screens messages/posts submitted
through a university portal for safeguarding concerns (self-harm,
bullying, harassment, exploitation, academic distress, etc.) and
routes flagged content to the appropriate support team.

Built with tkinter (standard library - no external dependencies).

NOTE: This is an educational/demonstration tool. A real safeguarding
system requires trained professionals, robust NLP (not keyword matching),
compliance with GDPR/Data Protection law, and integration with
institutional safeguarding policy.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
import hashlib
import re
import json
from datetime import datetime
from pathlib import Path


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
# Persistence layer (SQLite)
# ---------------------------------------------------------------------------

DB_PATH = Path("safeguarding.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            pw_hash    TEXT NOT NULL,
            role       TEXT NOT NULL,       -- 'student' or 'staff'
            full_name  TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            content     TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            severity    TEXT NOT NULL,
            categories  TEXT NOT NULL,      -- JSON
            status      TEXT NOT NULL DEFAULT 'Pending',
            reviewer    TEXT,
            review_note TEXT,
            reviewed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()

    # Seed demo accounts on first run
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        demo = [
            ("student1", "password", "student", "Alex Morgan"),
            ("student2", "password", "student", "Sam Taylor"),
            ("staff1",   "password", "staff",   "Dr. Jordan Reed"),
        ]
        for username, pw, role, name in demo:
            cur.execute(
                "INSERT INTO users(username, pw_hash, role, full_name, created_at) "
                "VALUES (?,?,?,?,?)",
                (username, hash_pw(pw), role, name, datetime.now().isoformat()),
            )
        conn.commit()
    conn.close()


def hash_pw(password: str) -> str:
    # NOTE: demonstration only — real systems must use bcrypt/argon2 with a salt.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, full_name FROM users "
        "WHERE username=? AND pw_hash=?",
        (username, hash_pw(password)),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "role": row[2], "full_name": row[3]}
    return None


def save_submission(user_id, content, severity, categories):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO submissions(user_id, content, submitted_at, severity, categories) "
        "VALUES (?,?,?,?,?)",
        (user_id, content, datetime.now().isoformat(),
         severity, json.dumps(categories)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def fetch_submissions(status_filter=None, severity_filter=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    q = """SELECT s.id, u.full_name, u.username, s.submitted_at,
                  s.severity, s.categories, s.status, s.content,
                  s.reviewer, s.review_note, s.reviewed_at
           FROM submissions s
           JOIN users u ON s.user_id = u.id
           WHERE 1=1"""
    params = []
    if status_filter and status_filter != "All":
        q += " AND s.status = ?"
        params.append(status_filter)
    if severity_filter and severity_filter != "All":
        q += " AND s.severity = ?"
        params.append(severity_filter)
    q += " ORDER BY CASE s.severity " \
         "WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 " \
         "WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END, " \
         "s.submitted_at DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_submission_status(sub_id, status, reviewer, note):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE submissions SET status=?, reviewer=?, review_note=?, reviewed_at=? "
        "WHERE id=?",
        (status, reviewer, note, datetime.now().isoformat(), sub_id),
    )
    conn.commit()
    conn.close()


def fetch_user_submissions(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status FROM submissions "
        "WHERE user_id=? ORDER BY submitted_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


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
    def __init__(self):
        super().__init__()
        self.title("University Portal — Safeguarding System")
        self.geometry("1000x680")
        self.configure(bg="#f4f6fa")

        self.user = None

        # ttk theming
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=6)
        style.configure("Header.TLabel",
                        font=("Segoe UI", 16, "bold"),
                        background="#f4f6fa")
        style.configure("Sub.TLabel",
                        font=("Segoe UI", 10),
                        background="#f4f6fa", foreground="#555")

        self.container = tk.Frame(self, bg="#f4f6fa")
        self.container.pack(fill="both", expand=True)

        self.show_login()

    # ---------- helpers ----------
    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    # ---------- login ----------
    def show_login(self):
        self._clear()
        frame = tk.Frame(self.container, bg="#f4f6fa")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(frame, text="University Portal",
                  style="Header.TLabel").pack(pady=(0, 4))
        ttk.Label(frame, text="Safeguarding & Wellbeing System",
                  style="Sub.TLabel").pack(pady=(0, 20))

        form = tk.Frame(frame, bg="white", bd=1, relief="solid",
                        padx=30, pady=25)
        form.pack()

        tk.Label(form, text="Username", bg="white",
                 anchor="w").grid(row=0, column=0, sticky="w")
        user_entry = ttk.Entry(form, width=32)
        user_entry.grid(row=1, column=0, pady=(2, 10))

        tk.Label(form, text="Password", bg="white",
                 anchor="w").grid(row=2, column=0, sticky="w")
        pw_entry = ttk.Entry(form, width=32, show="•")
        pw_entry.grid(row=3, column=0, pady=(2, 15))

        msg_lbl = tk.Label(form, text="", bg="white", fg="#b00020")
        msg_lbl.grid(row=5, column=0)

        def try_login():
            u = user_entry.get().strip()
            p = pw_entry.get()
            if not u or not p:
                msg_lbl.config(text="Please enter username and password.")
                return
            user = authenticate(u, p)
            if user:
                self.user = user
                if user["role"] == "staff":
                    self.show_staff_dashboard()
                else:
                    self.show_student_dashboard()
            else:
                msg_lbl.config(text="Invalid credentials.")

        ttk.Button(form, text="Sign in",
                   command=try_login).grid(row=4, column=0, sticky="ew")

        # Demo credentials hint
        hint = tk.Label(
            frame, bg="#f4f6fa", fg="#555",
            font=("Segoe UI", 9),
            text=("Demo accounts:\n"
                  "  student1 / password    (student)\n"
                  "  staff1   / password    (safeguarding staff)"),
            justify="left",
        )
        hint.pack(pady=(15, 0))

        user_entry.focus_set()
        self.bind("<Return>", lambda e: try_login())

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
        for sid, ts, sev, status in fetch_user_submissions(self.user["id"]):
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
        sid = save_submission(self.user["id"], text, overall, categories)

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
        ttk.Button(bar, text="Sign out",
                   command=self._logout).pack(side="right", padx=20)

    def _logout(self):
        self.user = None
        self.show_login()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app = SafeguardingApp()
    app.mainloop()
