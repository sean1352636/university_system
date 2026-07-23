"""
University Research Management System
A GUI application for managing research ethics, REF submissions, IP/commercialisation,
and thesis/viva workflows at a university.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user.

Persistence: rows live in the central `student_records.db` under
module-prefixed tables (`research_people`, `research_ethics_applications`,
`research_outputs`, `research_ip_assets`, `research_theses`,
`research_thesis_milestones`) so they don't collide with generic
table names elsewhere in the system. The legacy local
`university_research.db` file is removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime, date
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, simpledialog


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
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
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


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "university_research.db")


def _remove_legacy_db():
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy research DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection`. All tables are prefixed `research_*` to avoid
    colliding with generic table names elsewhere in the system."""

    def __init__(self, db_path=None):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        self.conn = get_connection()
        self.conn.row_factory = sqlite3.Row
        # Foreign keys reference research_people / research_theses
        # which we own — enabling FK enforcement is safe here.
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_if_empty()

    def create_tables(self):
        cur = self.conn.cursor()

        # People (researchers, supervisors, students, examiners)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL,           -- 'staff', 'student', 'examiner', 'external'
                department TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Research Ethics / IRB
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_ethics_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                principal_investigator_id INTEGER,
                department TEXT,
                risk_level TEXT,              -- 'Low', 'Medium', 'High'
                category TEXT,                -- 'Human participants', 'Animal', 'Data-only', etc.
                submitted_date TEXT,
                decision_date TEXT,
                status TEXT NOT NULL,         -- 'Draft','Submitted','Under Review','Approved','Rejected','Revisions Required','Expired'
                approval_expiry TEXT,
                notes TEXT,
                FOREIGN KEY (principal_investigator_id) REFERENCES research_people(id)
            )
        """)

        # REF submissions / research outputs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                output_type TEXT NOT NULL,    -- 'Journal article','Conference paper','Book','Book chapter','Dataset','Software','Other'
                authors TEXT,                 -- comma separated
                lead_author_id INTEGER,
                venue TEXT,                   -- journal/conference/publisher
                publication_date TEXT,
                doi TEXT,
                uoa TEXT,                     -- Unit of Assessment
                ref_submitted INTEGER DEFAULT 0,  -- boolean 0/1
                open_access INTEGER DEFAULT 0,
                quality_rating TEXT,          -- '1*','2*','3*','4*', or ''
                abstract TEXT,
                FOREIGN KEY (lead_author_id) REFERENCES research_people(id)
            )
        """)

        # IP / Tech-transfer / Commercialisation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_ip_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                ip_type TEXT NOT NULL,        -- 'Patent','Copyright','Trademark','Know-how','Software','Design'
                inventor_id INTEGER,
                disclosure_date TEXT,
                filing_date TEXT,
                grant_date TEXT,
                jurisdiction TEXT,
                status TEXT NOT NULL,         -- 'Disclosed','Evaluating','Filed','Granted','Licensed','Abandoned'
                commercial_route TEXT,        -- 'License','Spin-out','Assignment','None yet'
                licensee TEXT,
                revenue_to_date REAL DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (inventor_id) REFERENCES research_people(id)
            )
        """)

        # Theses / dissertations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_theses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                degree TEXT NOT NULL,         -- 'PhD','MPhil','MRes','Masters'
                department TEXT,
                primary_supervisor_id INTEGER,
                secondary_supervisor_id INTEGER,
                start_date TEXT,
                expected_submission TEXT,
                submission_date TEXT,
                viva_date TEXT,
                internal_examiner_id INTEGER,
                external_examiner_id INTEGER,
                status TEXT NOT NULL,         -- 'Active','Submitted','Under Examination','Viva Scheduled','Passed','Minor Corrections','Major Corrections','Failed','Withdrawn'
                outcome TEXT,
                FOREIGN KEY (student_id) REFERENCES research_people(id),
                FOREIGN KEY (primary_supervisor_id) REFERENCES research_people(id),
                FOREIGN KEY (secondary_supervisor_id) REFERENCES research_people(id),
                FOREIGN KEY (internal_examiner_id) REFERENCES research_people(id),
                FOREIGN KEY (external_examiner_id) REFERENCES research_people(id)
            )
        """)

        # Thesis milestones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_thesis_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thesis_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                due_date TEXT,
                completed_date TEXT,
                status TEXT NOT NULL,         -- 'Pending','Completed','Overdue','Missed'
                notes TEXT,
                FOREIGN KEY (thesis_id) REFERENCES research_theses(id) ON DELETE CASCADE
            )
        """)

        self.conn.commit()

    def seed_if_empty(self):
        """Populate with sample data on first run so the UI is not empty."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM research_people")
        if cur.fetchone()[0] > 0:
            return

        now = datetime.now().isoformat()
        people = [
            ("Prof. Eleanor Ashworth", "e.ashworth@uni.ac.uk", "staff", "Computer Science"),
            ("Dr. Marcus Chen", "m.chen@uni.ac.uk", "staff", "Biological Sciences"),
            ("Dr. Priya Raman", "p.raman@uni.ac.uk", "staff", "Engineering"),
            ("Prof. James O'Sullivan", "j.osullivan@uni.ac.uk", "staff", "Physics"),
            ("Sarah Nakamura", "s.nakamura@student.uni.ac.uk", "student", "Computer Science"),
            ("Thomas Bergstrom", "t.bergstrom@student.uni.ac.uk", "student", "Engineering"),
            ("Aisha Patel", "a.patel@student.uni.ac.uk", "student", "Biological Sciences"),
            ("Prof. Helen Warburton", "h.warburton@external.ac.uk", "external", "External"),
            ("Prof. David Kowalski", "d.kowalski@oxbridge.ac.uk", "external", "External"),
        ]
        # The seed data below references people/theses by their 1-based
        # position in these lists. We must resolve those to the actual
        # auto-generated ids: research_people uses AUTOINCREMENT, so if the
        # table was seeded once and later cleared, sqlite_sequence has
        # advanced and re-seeded rows do NOT start at id 1 — hard-coding
        # 1,2,3 then trips the foreign keys.
        people_ids = []
        for p in people:
            cur.execute(
                "INSERT INTO research_people(name,email,role,department,created_at) VALUES(?,?,?,?,?)",
                (*p, now),
            )
            people_ids.append(cur.lastrowid)

        def _pid(ref):
            return people_ids[ref - 1] if ref else None

        # Ethics applications
        ethics = [
            ("ETH-2025-001", "Behavioural study of HCI interfaces for older adults", 1,
             "Computer Science", "Medium", "Human participants",
             "2025-01-12", "2025-02-08", "Approved", "2026-02-08",
             "Approved with standard conditions."),
            ("ETH-2025-014", "Gene expression in zebrafish larvae", 2,
             "Biological Sciences", "High", "Animal",
             "2025-02-20", None, "Under Review", None,
             "Awaiting AWERB panel feedback."),
            ("ETH-2025-022", "Retrospective analysis of anonymised clinical data", 2,
             "Biological Sciences", "Low", "Data-only",
             "2025-03-05", "2025-03-19", "Approved", "2028-03-19",
             ""),
            ("ETH-2026-003", "Survey on AI tool adoption in SMEs", 3,
             "Engineering", "Low", "Human participants",
             "2026-01-15", None, "Revisions Required", None,
             "Revise consent form language."),
        ]
        for e in ethics:
            row = list(e)
            row[2] = _pid(row[2])  # principal_investigator_id
            cur.execute("""INSERT INTO research_ethics_applications
                (reference,title,principal_investigator_id,department,risk_level,category,
                 submitted_date,decision_date,status,approval_expiry,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", row)

        # Research outputs
        outputs = [
            ("Accessible Interface Design Patterns for Cognitive Decline", "Journal article",
             "Ashworth, E.; Nakamura, S.", 1, "ACM Transactions on Accessible Computing",
             "2025-06-15", "10.1145/example.2025.001", "UoA 11 - Computer Science",
             1, 1, "4*", "A study of design patterns supporting users with mild cognitive impairment."),
            ("Quantum error correction via topological codes: a review", "Journal article",
             "O'Sullivan, J.", 4, "Reviews of Modern Physics",
             "2025-09-01", "10.1103/example.2025.002", "UoA 9 - Physics",
             1, 1, "4*", ""),
            ("CRISPR-based screening identifies novel regulators of neural crest migration",
             "Journal article", "Chen, M.; Patel, A.", 2, "Nature Cell Biology",
             "2025-11-04", "10.1038/example.2025.003", "UoA 5 - Biological Sciences",
             0, 1, "4*", ""),
            ("Edge AI for predictive maintenance in rotating machinery",
             "Conference paper", "Raman, P.; Bergstrom, T.", 3,
             "Proceedings of IEEE ICRA 2026", "2026-05-20", "10.1109/example.2026.004",
             "UoA 12 - Engineering", 0, 0, "3*", ""),
        ]
        for o in outputs:
            row = list(o)
            row[3] = _pid(row[3])  # lead_author_id
            cur.execute("""INSERT INTO research_outputs
                (title,output_type,authors,lead_author_id,venue,publication_date,doi,
                 uoa,ref_submitted,open_access,quality_rating,abstract)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", row)

        # IP assets
        ip = [
            ("IP-2024-007", "Adaptive UI framework for accessibility",
             "Software", 1, "2024-09-10", "2025-01-20", None, "UK/EU",
             "Filed", "License", None, 0, ""),
            ("IP-2025-002", "Novel catalyst composition for hydrogen production",
             "Patent", 3, "2025-02-14", "2025-06-30", None, "UK/US/EU",
             "Filed", "Spin-out", None, 0, "Evaluating spin-out company formation."),
            ("IP-2023-019", "Method for targeted gene delivery",
             "Patent", 2, "2023-05-01", "2023-11-12", "2025-08-04", "US",
             "Licensed", "License", "BioNova Therapeutics", 125000,
             "Exclusive license, 5% royalty."),
            ("IP-2026-001", "Vibration-analysis algorithm (know-how disclosure)",
             "Know-how", 3, "2026-01-08", None, None, "N/A",
             "Disclosed", "None yet", None, 0, ""),
        ]
        for item in ip:
            row = list(item)
            row[3] = _pid(row[3])  # inventor_id
            cur.execute("""INSERT INTO research_ip_assets
                (reference,title,ip_type,inventor_id,disclosure_date,filing_date,grant_date,
                 jurisdiction,status,commercial_route,licensee,revenue_to_date,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

        # Theses
        theses = [
            (5, "Human-computer interaction for ageing populations", "PhD",
             "Computer Science", 1, 4, "2023-09-25", "2026-09-25", None, None,
             None, None, "Active", None),
            (6, "Machine learning for industrial condition monitoring", "PhD",
             "Engineering", 3, 1, "2022-10-01", "2025-10-01", "2025-11-30",
             "2026-03-18", 1, 8, "Viva Scheduled", None),
            (7, "Transcriptional regulation in vertebrate development", "PhD",
             "Biological Sciences", 2, 4, "2021-09-20", "2024-09-20", "2024-12-15",
             "2025-04-10", 4, 9, "Minor Corrections",
             "Minor corrections to be submitted within 3 months."),
        ]
        thesis_ids = []
        for t in theses:
            row = list(t)
            for i in (0, 4, 5, 10, 11):  # student / supervisors / examiners
                row[i] = _pid(row[i])
            cur.execute("""INSERT INTO research_theses
                (student_id,title,degree,department,primary_supervisor_id,secondary_supervisor_id,
                 start_date,expected_submission,submission_date,viva_date,
                 internal_examiner_id,external_examiner_id,status,outcome)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)
            thesis_ids.append(cur.lastrowid)

        def _tid(ref):
            return thesis_ids[ref - 1] if ref else None

        # Milestones
        milestones = [
            # Sarah - active PhD
            (1, "Confirmation of Registration (Year 1 review)", "2024-09-25", "2024-09-18", "Completed", ""),
            (1, "Annual Progress Review Y2", "2025-09-25", "2025-09-22", "Completed", ""),
            (1, "Annual Progress Review Y3", "2026-09-25", None, "Pending", ""),
            (1, "Thesis submission", "2026-09-25", None, "Pending", ""),
            # Thomas - viva scheduled
            (2, "Confirmation of Registration", "2023-10-01", "2023-09-28", "Completed", ""),
            (2, "Annual Progress Review Y2", "2024-10-01", "2024-09-30", "Completed", ""),
            (2, "Thesis submission", "2025-10-01", "2025-11-30", "Completed", "Extension granted."),
            (2, "Viva voce examination", "2026-03-18", None, "Pending", ""),
            # Aisha - minor corrections
            (3, "Confirmation of Registration", "2022-09-20", "2022-09-15", "Completed", ""),
            (3, "Thesis submission", "2024-09-20", "2024-12-15", "Completed", "Extension granted."),
            (3, "Viva voce examination", "2025-04-10", "2025-04-10", "Completed", "Minor corrections."),
            (3, "Corrections submission", "2025-07-10", None, "Pending", ""),
        ]
        for m in milestones:
            row = list(m)
            row[0] = _tid(row[0])  # thesis_id
            cur.execute("""INSERT INTO research_thesis_milestones
                (thesis_id,name,due_date,completed_date,status,notes)
                VALUES(?,?,?,?,?,?)""", row)

        self.conn.commit()

    # ----- generic query helpers --------------------------------------------
    def query(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

PALETTE = {
    # 8.117.65 — flattened to the main GUI's neutral clam-default look.
    # Pre-8.117.65 the portal had a navy header bar (#1f3a68), white
    # panel cards, and a saturated blue accent button — visually
    # disconnected from every other workspace tab.
    "bg": "#f0f0f0",
    "panel": "#f0f0f0",
    "header": "#f0f0f0",
    "accent": "#3c5a99",
    "accent_soft": "#e1e1e1",
    "text": "#000000",
    "muted": "#555555",
    "success": "#1f7a3c",
    "warn": "#b0620a",
    "danger": "#b3261e",
    "border": "#cccccc",
}


def configure_styles():
    # 8.117.71 — only configure NAMED styles. Pre-8.117.71 this
    # reconfigured base styles (".", TFrame, TLabel, TButton,
    # TNotebook, TNotebook.Tab, Treeview, Treeview.Heading, TEntry,
    # TCombobox) on the global ttk.Style — and because the portal
    # is launched in-process via ``open_in_workspace`` (so it shares
    # the main GUI's Tk root), those overrides bled out and recoloured
    # the whole main window. Base styles now stay on clam defaults;
    # only the Research.* named styles are touched.
    style = ttk.Style()

    style.configure("Panel.TFrame", background=PALETTE["panel"])
    style.configure("Header.TFrame", background=PALETTE["header"])

    style.configure("Panel.TLabel", background=PALETTE["panel"])
    style.configure("Header.TLabel", background=PALETTE["header"],
                    foreground=PALETTE["text"], font=("Segoe UI", 14, "bold"))
    style.configure("Subheader.TLabel", background=PALETTE["header"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 10))
    style.configure("SectionTitle.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["text"], font=("Segoe UI", 13, "bold"))
    style.configure("Muted.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 9))
    style.configure("StatValue.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["text"], font=("Segoe UI", 20, "bold"))
    style.configure("StatLabel.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 9))

    style.configure("Accent.TButton", padding=(14, 7))
    style.configure("Danger.TButton", foreground=PALETTE["danger"])

    return style


def status_colour(status):
    s = (status or "").lower()
    if any(k in s for k in ["approved", "completed", "passed", "granted", "licensed"]):
        return PALETTE["success"]
    if any(k in s for k in ["submitted", "active", "filed", "under review",
                            "scheduled", "pending", "evaluating",
                            "minor corrections"]):
        return PALETTE["warn"]
    if any(k in s for k in ["rejected", "failed", "overdue", "missed",
                            "expired", "abandoned", "withdrawn",
                            "major corrections", "revisions required"]):
        return PALETTE["danger"]
    return PALETTE["muted"]


def fmt_date(s):
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {s!r}. Use YYYY-MM-DD.")


# ---------------------------------------------------------------------------
# Generic record dialog
# ---------------------------------------------------------------------------

class FieldSpec:
    """Describes one field shown in an edit dialog."""
    def __init__(self, key, label, kind="text", choices=None, required=False,
                 default=None, hint=None):
        self.key = key
        self.label = label
        self.kind = kind  # 'text','multiline','combo','date','int','float','bool','people'
        self.choices = choices or []
        self.required = required
        self.default = default
        self.hint = hint


class RecordDialog(tk.Toplevel):
    """Generic edit/create dialog driven by a list of FieldSpec."""

    def __init__(self, parent, title, fields, record=None, people_lookup=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PALETTE["bg"])
        self.transient(parent)
        # A transient Toplevel isn't mapped synchronously, so an immediate
        # grab_set() raises "grab failed: window not viewable". Defer the grab
        # until the window is actually viewable.
        self._grab_when_viewable()
        self.resizable(False, False)

        self.fields = fields
        self.record = record or {}
        self.people_lookup = people_lookup or {}
        self.vars = {}
        self.result = None

        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        header = ttk.Frame(frame, style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=title, style="Header.TLabel").pack(
            anchor="w", padx=18, pady=12)

        body = ttk.Frame(frame, style="Panel.TFrame")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        for i, f in enumerate(fields):
            ttk.Label(body, text=f.label + (" *" if f.required else ""),
                      style="Panel.TLabel", font=("Segoe UI", 10)).grid(
                row=i, column=0, sticky="nw", pady=6, padx=(0, 12))

            val = self.record.get(f.key, f.default)
            if val is None:
                val = ""

            if f.kind == "multiline":
                text = tk.Text(body, width=42, height=4, font=("Segoe UI", 10),
                               relief="solid", borderwidth=1)
                text.insert("1.0", str(val))
                text.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = text
            elif f.kind == "combo":
                var = tk.StringVar(value=str(val))
                cb = ttk.Combobox(body, textvariable=var, values=f.choices,
                                  width=40, state="readonly")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            elif f.kind == "people":
                # choices is a list of (id, display) tuples
                display_map = {d: i for i, d in f.choices}
                self.vars[f.key + "_map"] = display_map
                inverse = {i: d for i, d in f.choices}
                current = inverse.get(val, "")
                var = tk.StringVar(value=current)
                cb = ttk.Combobox(body, textvariable=var,
                                  values=[""] + [d for _, d in f.choices],
                                  width=40, state="readonly")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            elif f.kind == "bool":
                var = tk.BooleanVar(value=bool(val))
                cb = ttk.Checkbutton(body, variable=var, style="TCheckbutton")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            else:
                var = tk.StringVar(value=str(val))
                entry = ttk.Entry(body, textvariable=var, width=44)
                entry.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
                if f.hint:
                    ttk.Label(body, text=f.hint, style="Muted.TLabel").grid(
                        row=i, column=2, sticky="w", padx=8)

        btn_row = ttk.Frame(frame, style="Panel.TFrame")
        btn_row.pack(fill="x", padx=20, pady=(0, 18))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btn_row, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right", padx=(0, 8))

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    def _grab_when_viewable(self):
        """Set the modal grab once the window is viewable, retrying until then.

        grab_set() raises TclError if the window isn't yet mapped; a transient
        Toplevel maps asynchronously, so retry on the event loop.
        """
        try:
            if self.winfo_viewable():
                self.grab_set()
            else:
                self.after(10, self._grab_when_viewable)
        except tk.TclError:
            # Window was destroyed before it became viewable — nothing to grab.
            pass

    def _save(self):
        out = {}
        for f in self.fields:
            widget = self.vars[f.key]
            if f.kind == "multiline":
                v = widget.get("1.0", "end").strip()
            elif f.kind == "bool":
                v = 1 if widget.get() else 0
            elif f.kind == "people":
                display = widget.get()
                mapping = self.vars[f.key + "_map"]
                v = mapping.get(display)
            else:
                v = widget.get().strip()

            if f.required and (v is None or v == ""):
                messagebox.showerror("Missing field",
                                     f"Please provide: {f.label}", parent=self)
                return

            if f.kind == "date" and v:
                try:
                    v = parse_date(v)
                except ValueError as e:
                    messagebox.showerror("Invalid date", str(e), parent=self)
                    return
            elif f.kind == "int" and v != "":
                try:
                    v = int(v)
                except ValueError:
                    messagebox.showerror("Invalid number",
                                         f"{f.label} must be a whole number.",
                                         parent=self)
                    return
            elif f.kind == "float" and v != "":
                try:
                    v = float(v)
                except ValueError:
                    messagebox.showerror("Invalid number",
                                         f"{f.label} must be a number.",
                                         parent=self)
                    return

            out[f.key] = v if v != "" else None

        self.result = out
        self.destroy()


# ---------------------------------------------------------------------------
# Base module tab
# ---------------------------------------------------------------------------

class ModuleTab(ttk.Frame):
    """Base class for each feature tab."""
    def __init__(self, parent, db, app):
        super().__init__(parent, style="TFrame")
        self.db = db
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        raise NotImplementedError

    def refresh(self):
        raise NotImplementedError

    def people_choices(self, role=None):
        if role:
            rows = self.db.query(
                "SELECT id,name,department FROM research_people WHERE role=? ORDER BY name",
                (role,))
        else:
            rows = self.db.query(
                "SELECT id,name,department FROM research_people ORDER BY name")
        return [(r["id"], f"{r['name']} ({r['department'] or '—'})") for r in rows]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardTab(ModuleTab):

    def _build(self):
        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=24, pady=20)

        ttk.Label(container, text="Research Management Overview",
                  font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(anchor="w")
        ttk.Label(container,
                  text="A consolidated view across ethics, outputs, IP and research degrees.",
                  foreground=PALETTE["muted"]).pack(anchor="w", pady=(0, 18))

        # KPI cards
        self.cards_frame = ttk.Frame(container, style="TFrame")
        self.cards_frame.pack(fill="x")

        # Two-column lower region
        lower = ttk.Frame(container, style="TFrame")
        lower.pack(fill="both", expand=True, pady=(18, 0))
        lower.columnconfigure(0, weight=1, uniform="col")
        lower.columnconfigure(1, weight=1, uniform="col")
        lower.rowconfigure(0, weight=1)

        self.left_panel = self._panel(lower, "Upcoming & overdue milestones")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_list = self._listbox(self.left_panel)

        self.right_panel = self._panel(lower, "Attention needed")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.right_list = self._listbox(self.right_panel)

    def _panel(self, parent, title):
        p = ttk.Frame(parent, style="Panel.TFrame")
        inner = ttk.Frame(p, style="Panel.TFrame")
        inner.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(inner, text=title, style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(inner).pack(fill="x", pady=(6, 10))
        p.inner = inner
        return p

    def _listbox(self, panel):
        frame = ttk.Frame(panel.inner, style="Panel.TFrame")
        frame.pack(fill="both", expand=True)
        lb = tk.Listbox(frame, font=("Segoe UI", 10),
                        bg="white", fg=PALETTE["text"],
                        selectbackground=PALETTE["accent_soft"],
                        selectforeground=PALETTE["header"],
                        relief="solid", borderwidth=1, highlightthickness=0,
                        activestyle="none")
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)
        return lb

    def refresh(self):
        # clear cards
        for w in self.cards_frame.winfo_children():
            w.destroy()

        stats = [
            ("Active ethics apps",
             self.db.query("SELECT COUNT(*) c FROM research_ethics_applications "
                           "WHERE status IN ('Submitted','Under Review',"
                           "'Revisions Required')")[0]["c"],
             PALETTE["accent"]),
            ("Approved (current)",
             self.db.query("SELECT COUNT(*) c FROM research_ethics_applications "
                           "WHERE status='Approved'")[0]["c"],
             PALETTE["success"]),
            ("Outputs (REF-tagged)",
             self.db.query("SELECT COUNT(*) c FROM research_outputs "
                           "WHERE ref_submitted=1")[0]["c"],
             PALETTE["accent"]),
            ("IP assets",
             self.db.query("SELECT COUNT(*) c FROM research_ip_assets")[0]["c"],
             PALETTE["header"]),
            ("Active theses",
             self.db.query("SELECT COUNT(*) c FROM research_theses "
                           "WHERE status IN ('Active','Submitted',"
                           "'Under Examination','Viva Scheduled',"
                           "'Minor Corrections','Major Corrections')")[0]["c"],
             PALETTE["warn"]),
            ("IP revenue (total)",
             f"£{self.db.query('SELECT COALESCE(SUM(revenue_to_date),0) s FROM research_ip_assets')[0]['s']:,.0f}",
             PALETTE["success"]),
        ]

        for i, (lbl, val, colour) in enumerate(stats):
            card = tk.Frame(self.cards_frame, bg=PALETTE["panel"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            self.cards_frame.columnconfigure(i, weight=1, uniform="kpi")

            strip = tk.Frame(card, bg=colour, height=4)
            strip.pack(fill="x")

            inner = tk.Frame(card, bg=PALETTE["panel"])
            inner.pack(fill="both", expand=True, padx=16, pady=14)
            tk.Label(inner, text=str(val), bg=PALETTE["panel"],
                     fg=PALETTE["header"],
                     font=("Segoe UI", 20, "bold")).pack(anchor="w")
            tk.Label(inner, text=lbl, bg=PALETTE["panel"],
                     fg=PALETTE["muted"],
                     font=("Segoe UI", 9)).pack(anchor="w")

        # Upcoming & overdue milestones
        self.left_list.delete(0, "end")
        today = date.today().isoformat()
        rows = self.db.query("""
            SELECT m.name, m.due_date, m.status, p.name AS student, t.title
            FROM research_thesis_milestones m
            JOIN research_theses t ON t.id = m.thesis_id
            JOIN research_people p ON p.id = t.student_id
            WHERE m.status='Pending' OR (m.status='Pending' AND m.due_date < ?)
            ORDER BY COALESCE(m.due_date,'9999-12-31')
            LIMIT 12
        """, (today,))
        if not rows:
            self.left_list.insert("end", "  No pending milestones.")
        for r in rows:
            overdue = r["due_date"] and r["due_date"] < today
            tag = "  [OVERDUE] " if overdue else "  "
            self.left_list.insert(
                "end",
                f"{tag}{fmt_date(r['due_date'])} — {r['name']}  ·  {r['student']}")
            if overdue:
                self.left_list.itemconfig("end",
                                          foreground=PALETTE["danger"])

        # Attention needed
        self.right_list.delete(0, "end")
        attention = []
        rows = self.db.query(
            "SELECT reference,title,status FROM research_ethics_applications "
            "WHERE status IN ('Revisions Required','Expired')")
        for r in rows:
            attention.append(("Ethics", f"{r['reference']}: {r['status']}",
                              r["title"], PALETTE["danger"]))

        rows = self.db.query(
            "SELECT reference,title,status FROM research_ethics_applications "
            "WHERE status='Approved' AND approval_expiry IS NOT NULL "
            "AND approval_expiry < date('now','+90 days')")
        for r in rows:
            attention.append(("Ethics",
                              f"{r['reference']}: approval expiring",
                              r["title"], PALETTE["warn"]))

        rows = self.db.query(
            "SELECT t.title, p.name FROM research_theses t JOIN research_people p ON p.id=t.student_id "
            "WHERE t.status='Minor Corrections' OR t.status='Major Corrections'")
        for r in rows:
            attention.append(("Thesis", "Corrections outstanding",
                              f"{r['name']} — {r['title']}", PALETTE["warn"]))

        rows = self.db.query(
            "SELECT reference,title FROM research_ip_assets WHERE status='Disclosed'")
        for r in rows:
            attention.append(("IP", f"{r['reference']}: awaiting evaluation",
                              r["title"], PALETTE["accent"]))

        if not attention:
            self.right_list.insert("end", "  Nothing requires immediate attention.")
        for kind, head, body, colour in attention:
            self.right_list.insert("end", f"  [{kind}] {head}")
            self.right_list.itemconfig("end", foreground=colour)
            self.right_list.insert("end", f"         {body}")


# ---------------------------------------------------------------------------
# Generic "table + detail" module
# ---------------------------------------------------------------------------

class TableModule(ModuleTab):
    """
    Reusable module with:
      * title + New/Edit/Delete/Refresh buttons
      * search box
      * treeview listing
      * detail pane showing the selected record
    Subclasses define columns, query, field specs, and detail rendering.
    """

    title = ""
    subtitle = ""
    table_name = ""
    pk = "id"

    def _build(self):
        wrapper = ttk.Frame(self, style="TFrame")
        wrapper.pack(fill="both", expand=True, padx=24, pady=20)

        # Title row
        top = ttk.Frame(wrapper, style="TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=self.title, font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(anchor="w")
        ttk.Label(top, text=self.subtitle,
                  foreground=PALETTE["muted"]).pack(anchor="w")

        # Actions
        actions = ttk.Frame(wrapper, style="TFrame")
        actions.pack(fill="x", pady=(14, 8))

        ttk.Button(actions, text="+ New", style="Accent.TButton",
                   command=self.on_new).pack(side="left")
        ttk.Button(actions, text="Edit", command=self.on_edit).pack(side="left",
                                                                    padx=6)
        ttk.Button(actions, text="Delete", command=self.on_delete).pack(
            side="left")
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(
            side="left", padx=6)

        ttk.Label(actions, text="Search:",
                  foreground=PALETTE["muted"]).pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(actions, textvariable=self.search_var, width=30).pack(
            side="left")

        # Split area: table | detail
        split = ttk.Frame(wrapper, style="TFrame")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # Table area
        table_frame = ttk.Frame(split, style="Panel.TFrame")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        cols, heads, widths = self.get_columns()
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                 selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)

        sb = ttk.Scrollbar(table_frame, orient="vertical",
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=sb.set)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Double-1>", lambda e: self.on_edit())

        self.tree.tag_configure("alt", background="#fafbfd")

        # Detail panel
        detail_frame = ttk.Frame(split, style="Panel.TFrame")
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_inner = ttk.Frame(detail_frame, style="Panel.TFrame")
        detail_inner.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(detail_inner, text="Details",
                  style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(detail_inner).pack(fill="x", pady=(6, 10))

        self.detail_text = tk.Text(detail_inner, height=20, wrap="word",
                                   font=("Segoe UI", 10),
                                   relief="flat", bg=PALETTE["panel"],
                                   fg=PALETTE["text"])
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.configure(state="disabled")
        self.detail_text.tag_configure("label",
                                       font=("Segoe UI", 10, "bold"),
                                       foreground=PALETTE["header"])
        self.detail_text.tag_configure("value", foreground=PALETTE["text"])
        self.detail_text.tag_configure("muted", foreground=PALETTE["muted"])
        self.detail_text.tag_configure("section",
                                       font=("Segoe UI", 11, "bold"),
                                       foreground=PALETTE["header"])

    # ---- methods subclasses override ---------------------------------------
    def get_columns(self):
        raise NotImplementedError

    def fetch_rows(self, search):
        raise NotImplementedError

    def row_to_tree_values(self, row):
        raise NotImplementedError

    def get_field_specs(self, record=None):
        raise NotImplementedError

    def build_record_from_row(self, row):
        return dict(row)

    def render_detail(self, row):
        raise NotImplementedError

    def insert_sql(self, data):
        raise NotImplementedError

    def update_sql(self, data, pk):
        raise NotImplementedError

    # ---- common behaviour --------------------------------------------------
    def refresh(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = self.fetch_rows(self.search_var.get())
        for i, r in enumerate(rows):
            tag = ("alt",) if i % 2 else ()
            self.tree.insert("", "end", iid=str(r[self.pk]),
                             values=self.row_to_tree_values(r), tags=tag)
        self._clear_detail()

    def _clear_detail(self):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0",
                                "Select a row to view full details.",
                                ("muted",))
        self.detail_text.configure(state="disabled")

    def on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        pk_val = int(sel[0])
        row = self.db.query(
            f"SELECT * FROM {self.table_name} WHERE {self.pk}=?",
            (pk_val,))
        if not row:
            return
        row = self.build_record_from_row(row[0])
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.render_detail(row)
        self.detail_text.configure(state="disabled")

    def _write_detail(self, pairs):
        for label, value, *rest in pairs:
            tag = rest[0] if rest else "value"
            self.detail_text.insert("end", f"{label}\n", ("label",))
            self.detail_text.insert("end", f"{value or '—'}\n\n", (tag,))

    def on_new(self):
        fields = self.get_field_specs()
        dlg = RecordDialog(self.app.root, f"New — {self.title}", fields)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self.insert_sql(dlg.result)
                self.refresh()
                self.app.dashboard.refresh()
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=self)

    def on_edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select a record to edit.", parent=self)
            return
        pk_val = int(sel[0])
        row = self.db.query(
            f"SELECT * FROM {self.table_name} WHERE {self.pk}=?",
            (pk_val,))
        if not row:
            return
        record = self.build_record_from_row(row[0])
        fields = self.get_field_specs(record)
        dlg = RecordDialog(self.app.root, f"Edit — {self.title}",
                           fields, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self.update_sql(dlg.result, pk_val)
                self.refresh()
                self.tree.selection_set(str(pk_val))
                self.app.dashboard.refresh()
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=self)

    def on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select a record to delete.", parent=self)
            return
        pk_val = int(sel[0])
        if not messagebox.askyesno("Confirm delete",
                                   "Delete the selected record? This cannot be undone.",
                                   parent=self):
            return
        self.db.execute(
            f"DELETE FROM {self.table_name} WHERE {self.pk}=?", (pk_val,))
        self.refresh()
        self.app.dashboard.refresh()


# ---------------------------------------------------------------------------
# Ethics module
# ---------------------------------------------------------------------------

class EthicsTab(TableModule):
    title = "Research Ethics / IRB"
    subtitle = "Track applications, approvals and expiry across the institution."
    table_name = "ethics_applications"

    ETHICS_STATUSES = ["Draft", "Submitted", "Under Review",
                       "Revisions Required", "Approved", "Rejected",
                       "Expired"]
    RISK_LEVELS = ["Low", "Medium", "High"]
    CATEGORIES = ["Human participants", "Animal", "Data-only",
                  "Clinical", "Environmental", "Other"]

    def get_columns(self):
        cols = ("reference", "title", "pi", "category", "risk", "status",
                "decision")
        heads = ("Reference", "Title", "Principal Investigator",
                 "Category", "Risk", "Status", "Decision date")
        widths = (95, 280, 170, 130, 70, 140, 110)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            sql = """SELECT e.*, p.name AS pi_name FROM research_ethics_applications e
                     LEFT JOIN research_people p ON p.id=e.principal_investigator_id
                     WHERE LOWER(e.reference) LIKE ? OR LOWER(e.title) LIKE ?
                        OR LOWER(COALESCE(p.name,'')) LIKE ?
                        OR LOWER(COALESCE(e.status,'')) LIKE ?
                     ORDER BY e.submitted_date DESC NULLS LAST, e.id DESC"""
            return self.db.query(sql, (q, q, q, q))
        return self.db.query("""SELECT e.*, p.name AS pi_name
            FROM research_ethics_applications e
            LEFT JOIN research_people p ON p.id=e.principal_investigator_id
            ORDER BY e.submitted_date DESC, e.id DESC""")

    def row_to_tree_values(self, row):
        return (row["reference"], row["title"], row["pi_name"] or "—",
                row["category"] or "—", row["risk_level"] or "—",
                row["status"], fmt_date(row["decision_date"]))

    def get_field_specs(self, record=None):
        return [
            FieldSpec("reference", "Reference", required=True,
                      hint="e.g. ETH-2026-005"),
            FieldSpec("title", "Study title", required=True),
            FieldSpec("principal_investigator_id",
                      "Principal Investigator", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("department", "Department"),
            FieldSpec("category", "Category", kind="combo",
                      choices=self.CATEGORIES),
            FieldSpec("risk_level", "Risk level", kind="combo",
                      choices=self.RISK_LEVELS),
            FieldSpec("submitted_date", "Submitted date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("decision_date", "Decision date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.ETHICS_STATUSES, required=True),
            FieldSpec("approval_expiry", "Approval expiry", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]

    def render_detail(self, row):
        pi_name = "—"
        if row.get("principal_investigator_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["principal_investigator_id"],))
            if r:
                pi_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['reference']}\n", ("section",))
        self.detail_text.insert("end", f"{row['title']}\n\n", ("value",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Principal Investigator", pi_name),
            ("Department", row.get("department")),
            ("Category", row.get("category")),
            ("Risk level", row.get("risk_level")),
            ("Submitted", fmt_date(row.get("submitted_date"))),
            ("Decision", fmt_date(row.get("decision_date"))),
            ("Approval expiry", fmt_date(row.get("approval_expiry"))),
            ("Notes", row.get("notes")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_ethics_applications
            (reference,title,principal_investigator_id,department,risk_level,
             category,submitted_date,decision_date,status,approval_expiry,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submitted_date"), d.get("decision_date"),
             d.get("status"), d.get("approval_expiry"), d.get("notes")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_ethics_applications SET
            reference=?,title=?,principal_investigator_id=?,department=?,
            risk_level=?,category=?,submitted_date=?,decision_date=?,
            status=?,approval_expiry=?,notes=? WHERE id=?""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submitted_date"), d.get("decision_date"),
             d.get("status"), d.get("approval_expiry"),
             d.get("notes"), pk))


# ---------------------------------------------------------------------------
# REF / Outputs module
# ---------------------------------------------------------------------------

class OutputsTab(TableModule):
    title = "Research Outputs (REF)"
    subtitle = "Publications repository and REF submission tracking."
    table_name = "research_outputs"

    TYPES = ["Journal article", "Conference paper", "Book", "Book chapter",
             "Dataset", "Software", "Report", "Other"]
    RATINGS = ["", "1*", "2*", "3*", "4*"]
    UOAS = [f"UoA {n}" for n in range(1, 35)]

    def get_columns(self):
        cols = ("title", "type", "lead", "venue", "date", "ref", "rating")
        heads = ("Title", "Type", "Lead author", "Venue",
                 "Published", "REF?", "Rating")
        widths = (330, 120, 150, 180, 100, 55, 70)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT o.*, p.name AS lead_name
                FROM research_outputs o
                LEFT JOIN research_people p ON p.id=o.lead_author_id
                WHERE LOWER(o.title) LIKE ? OR LOWER(COALESCE(o.authors,'')) LIKE ?
                   OR LOWER(COALESCE(o.venue,'')) LIKE ?
                   OR LOWER(COALESCE(p.name,'')) LIKE ?
                ORDER BY o.publication_date DESC""", (q, q, q, q))
        return self.db.query("""SELECT o.*, p.name AS lead_name
            FROM research_outputs o
            LEFT JOIN research_people p ON p.id=o.lead_author_id
            ORDER BY o.publication_date DESC""")

    def row_to_tree_values(self, row):
        return (row["title"], row["output_type"],
                row["lead_name"] or "—", row["venue"] or "—",
                fmt_date(row["publication_date"]),
                "Yes" if row["ref_submitted"] else "No",
                row["quality_rating"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("title", "Title", required=True),
            FieldSpec("output_type", "Type", kind="combo",
                      choices=self.TYPES, required=True),
            FieldSpec("authors", "Authors (comma separated)"),
            FieldSpec("lead_author_id", "Lead author", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("venue", "Venue (journal/conf/publisher)"),
            FieldSpec("publication_date", "Publication date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("doi", "DOI / identifier"),
            FieldSpec("uoa", "Unit of Assessment", kind="combo",
                      choices=self.UOAS),
            FieldSpec("ref_submitted", "Submitted to REF?", kind="bool"),
            FieldSpec("open_access", "Open access compliant?", kind="bool"),
            FieldSpec("quality_rating", "Internal quality rating",
                      kind="combo", choices=self.RATINGS),
            FieldSpec("abstract", "Abstract / summary", kind="multiline"),
        ]

    def render_detail(self, row):
        lead_name = "—"
        if row.get("lead_author_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["lead_author_id"],))
            if r:
                lead_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['title']}\n", ("section",))
        self.detail_text.insert("end", f"{row['output_type']}\n\n",
                                ("muted",))
        self._write_detail([
            ("Authors", row.get("authors")),
            ("Lead author", lead_name),
            ("Venue", row.get("venue")),
            ("Published", fmt_date(row.get("publication_date"))),
            ("DOI", row.get("doi")),
            ("Unit of Assessment", row.get("uoa")),
            ("REF submitted", "Yes" if row.get("ref_submitted") else "No"),
            ("Open access", "Yes" if row.get("open_access") else "No"),
            ("Quality rating", row.get("quality_rating")),
            ("Abstract", row.get("abstract")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_outputs
            (title,output_type,authors,lead_author_id,venue,publication_date,
             doi,uoa,ref_submitted,open_access,quality_rating,abstract)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("title"), d.get("output_type"), d.get("authors"),
             d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_outputs SET
            title=?,output_type=?,authors=?,lead_author_id=?,venue=?,
            publication_date=?,doi=?,uoa=?,ref_submitted=?,open_access=?,
            quality_rating=?,abstract=? WHERE id=?""",
            (d.get("title"), d.get("output_type"), d.get("authors"),
             d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract"), pk))


# ---------------------------------------------------------------------------
# IP / Commercialisation module
# ---------------------------------------------------------------------------

class IPTab(TableModule):
    title = "IP & Commercialisation"
    subtitle = "Disclosures, filings, licences and tech-transfer revenue."
    table_name = "ip_assets"

    IP_TYPES = ["Patent", "Copyright", "Trademark", "Know-how",
                "Software", "Design"]
    IP_STATUSES = ["Disclosed", "Evaluating", "Filed", "Granted",
                   "Licensed", "Abandoned"]
    ROUTES = ["None yet", "License", "Spin-out", "Assignment", "Open release"]

    def get_columns(self):
        cols = ("reference", "title", "type", "inventor", "status", "route",
                "revenue")
        heads = ("Reference", "Title", "Type", "Inventor", "Status",
                 "Route", "Revenue (£)")
        widths = (95, 280, 95, 160, 110, 110, 100)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT i.*, p.name AS inv_name
                FROM research_ip_assets i
                LEFT JOIN research_people p ON p.id=i.inventor_id
                WHERE LOWER(i.reference) LIKE ? OR LOWER(i.title) LIKE ?
                   OR LOWER(COALESCE(p.name,'')) LIKE ?
                   OR LOWER(COALESCE(i.status,'')) LIKE ?
                ORDER BY i.disclosure_date DESC""", (q, q, q, q))
        return self.db.query("""SELECT i.*, p.name AS inv_name
            FROM research_ip_assets i
            LEFT JOIN research_people p ON p.id=i.inventor_id
            ORDER BY i.disclosure_date DESC""")

    def row_to_tree_values(self, row):
        return (row["reference"], row["title"], row["ip_type"],
                row["inv_name"] or "—", row["status"],
                row["commercial_route"] or "—",
                f"{(row['revenue_to_date'] or 0):,.0f}")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("reference", "Reference", required=True,
                      hint="e.g. IP-2026-003"),
            FieldSpec("title", "Title / short description", required=True),
            FieldSpec("ip_type", "IP type", kind="combo",
                      choices=self.IP_TYPES, required=True),
            FieldSpec("inventor_id", "Lead inventor", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("disclosure_date", "Disclosure date", kind="date"),
            FieldSpec("filing_date", "Filing date", kind="date"),
            FieldSpec("grant_date", "Grant date", kind="date"),
            FieldSpec("jurisdiction", "Jurisdiction(s)",
                      hint="e.g. UK/US/EU"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.IP_STATUSES, required=True),
            FieldSpec("commercial_route", "Commercial route",
                      kind="combo", choices=self.ROUTES),
            FieldSpec("licensee", "Licensee / partner"),
            FieldSpec("revenue_to_date", "Revenue to date (£)",
                      kind="float"),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]

    def render_detail(self, row):
        inv_name = "—"
        if row.get("inventor_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["inventor_id"],))
            if r:
                inv_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['reference']}\n", ("section",))
        self.detail_text.insert("end", f"{row['title']}\n\n", ("value",))
        rev = row.get("revenue_to_date") or 0
        self._write_detail([
            ("IP type", row.get("ip_type")),
            ("Status", row.get("status")),
            ("Lead inventor", inv_name),
            ("Disclosure date", fmt_date(row.get("disclosure_date"))),
            ("Filing date", fmt_date(row.get("filing_date"))),
            ("Grant date", fmt_date(row.get("grant_date"))),
            ("Jurisdiction", row.get("jurisdiction")),
            ("Commercial route", row.get("commercial_route")),
            ("Licensee", row.get("licensee")),
            ("Revenue to date", f"£{rev:,.2f}"),
            ("Notes", row.get("notes")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_ip_assets
            (reference,title,ip_type,inventor_id,disclosure_date,filing_date,
             grant_date,jurisdiction,status,commercial_route,licensee,
             revenue_to_date,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("filing_date"), d.get("grant_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("licensee"),
             d.get("revenue_to_date") or 0, d.get("notes")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_ip_assets SET
            reference=?,title=?,ip_type=?,inventor_id=?,disclosure_date=?,
            filing_date=?,grant_date=?,jurisdiction=?,status=?,
            commercial_route=?,licensee=?,revenue_to_date=?,notes=?
            WHERE id=?""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("filing_date"), d.get("grant_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("licensee"),
             d.get("revenue_to_date") or 0, d.get("notes"), pk))


# ---------------------------------------------------------------------------
# Thesis / Viva module (with milestones)
# ---------------------------------------------------------------------------

class ThesisTab(TableModule):
    title = "Theses, Vivas & Supervision"
    subtitle = "Supervisor allocation, milestones, submission and examination."
    table_name = "theses"

    DEGREES = ["PhD", "MPhil", "MRes", "Masters"]
    STATUSES = ["Active", "Submitted", "Under Examination",
                "Viva Scheduled", "Passed", "Minor Corrections",
                "Major Corrections", "Failed", "Withdrawn"]

    MILESTONE_STATUSES = ["Pending", "Completed", "Overdue", "Missed"]

    def get_columns(self):
        cols = ("student", "title", "degree", "supervisor",
                "viva", "status")
        heads = ("Student", "Thesis title", "Degree",
                 "Primary supervisor", "Viva date", "Status")
        widths = (150, 300, 70, 170, 110, 140)
        return cols, heads, widths

    def _build(self):
        super()._build()
        # Add milestone pane beneath the detail text
        ms_frame = ttk.Frame(self.detail_text.master, style="Panel.TFrame")
        ms_frame.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(ms_frame, text="Milestones",
                  style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(ms_frame).pack(fill="x", pady=(4, 8))

        ms_actions = ttk.Frame(ms_frame, style="Panel.TFrame")
        ms_actions.pack(fill="x", pady=(0, 6))
        ttk.Button(ms_actions, text="+ Add milestone",
                   command=self.add_milestone).pack(side="left")
        ttk.Button(ms_actions, text="Mark completed",
                   command=self.complete_milestone).pack(side="left", padx=6)
        ttk.Button(ms_actions, text="Delete",
                   command=self.delete_milestone).pack(side="left")

        cols = ("name", "due", "completed", "status")
        self.ms_tree = ttk.Treeview(ms_frame, columns=cols, show="headings",
                                    height=6, selectmode="browse")
        for c, h, w in zip(cols, ("Milestone", "Due", "Completed", "Status"),
                           (200, 100, 100, 100)):
            self.ms_tree.heading(c, text=h)
            self.ms_tree.column(c, width=w, anchor="w")
        self.ms_tree.pack(fill="both", expand=True)
        self.ms_tree.tag_configure("overdue", foreground=PALETTE["danger"])
        self.ms_tree.tag_configure("done", foreground=PALETTE["success"])

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        base = """SELECT t.*,
                  s.name AS student_name,
                  sup.name AS supervisor_name
                  FROM research_theses t
                  LEFT JOIN research_people s ON s.id=t.student_id
                  LEFT JOIN research_people sup ON sup.id=t.primary_supervisor_id"""
        if q:
            return self.db.query(base + """
                WHERE LOWER(COALESCE(s.name,'')) LIKE ?
                   OR LOWER(t.title) LIKE ?
                   OR LOWER(COALESCE(sup.name,'')) LIKE ?
                   OR LOWER(t.status) LIKE ?
                ORDER BY t.start_date DESC""", (q, q, q, q))
        return self.db.query(base + " ORDER BY t.start_date DESC")

    def row_to_tree_values(self, row):
        return (row["student_name"] or "—",
                row["title"],
                row["degree"],
                row["supervisor_name"] or "—",
                fmt_date(row["viva_date"]),
                row["status"])

    def get_field_specs(self, record=None):
        return [
            FieldSpec("student_id", "Student", kind="people",
                      choices=self.people_choices(role="student"),
                      required=True),
            FieldSpec("title", "Thesis title", required=True),
            FieldSpec("degree", "Degree", kind="combo",
                      choices=self.DEGREES, required=True),
            FieldSpec("department", "Department"),
            FieldSpec("primary_supervisor_id", "Primary supervisor",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("secondary_supervisor_id", "Secondary supervisor",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("start_date", "Start date", kind="date"),
            FieldSpec("expected_submission", "Expected submission",
                      kind="date"),
            FieldSpec("submission_date", "Actual submission", kind="date"),
            FieldSpec("viva_date", "Viva date", kind="date"),
            FieldSpec("internal_examiner_id", "Internal examiner",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("external_examiner_id", "External examiner",
                      kind="people",
                      choices=self.people_choices(role="external")),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.STATUSES, required=True),
            FieldSpec("outcome", "Outcome / notes", kind="multiline"),
        ]

    def render_detail(self, row):
        def person(pid):
            if not pid:
                return "—"
            r = self.db.query("SELECT name FROM research_people WHERE id=?", (pid,))
            return r[0]["name"] if r else "—"

        self.detail_text.insert("end", f"{row['title']}\n", ("section",))
        self.detail_text.insert("end",
                                f"{row.get('degree')} — {person(row.get('student_id'))}\n\n",
                                ("muted",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Department", row.get("department")),
            ("Primary supervisor", person(row.get("primary_supervisor_id"))),
            ("Secondary supervisor",
             person(row.get("secondary_supervisor_id"))),
            ("Start date", fmt_date(row.get("start_date"))),
            ("Expected submission",
             fmt_date(row.get("expected_submission"))),
            ("Actual submission", fmt_date(row.get("submission_date"))),
            ("Viva date", fmt_date(row.get("viva_date"))),
            ("Internal examiner", person(row.get("internal_examiner_id"))),
            ("External examiner", person(row.get("external_examiner_id"))),
            ("Outcome / notes", row.get("outcome")),
        ])
        self._refresh_milestones(row["id"])

    def _clear_detail(self):
        super()._clear_detail()
        if hasattr(self, "ms_tree"):
            for iid in self.ms_tree.get_children():
                self.ms_tree.delete(iid)

    def _refresh_milestones(self, thesis_id):
        for iid in self.ms_tree.get_children():
            self.ms_tree.delete(iid)
        rows = self.db.query(
            "SELECT * FROM research_thesis_milestones WHERE thesis_id=? "
            "ORDER BY COALESCE(due_date,'9999-12-31')", (thesis_id,))
        today = date.today().isoformat()
        for r in rows:
            tag = ()
            status = r["status"]
            if status == "Pending" and r["due_date"] and r["due_date"] < today:
                status = "Overdue"
                tag = ("overdue",)
            elif status == "Completed":
                tag = ("done",)
            self.ms_tree.insert("", "end", iid=str(r["id"]),
                                values=(r["name"],
                                        fmt_date(r["due_date"]),
                                        fmt_date(r["completed_date"]),
                                        status),
                                tags=tag)

    def _selected_thesis_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add_milestone(self):
        tid = self._selected_thesis_id()
        if not tid:
            messagebox.showinfo("No thesis selected",
                                "Select a thesis first.", parent=self)
            return
        fields = [
            FieldSpec("name", "Milestone", required=True),
            FieldSpec("due_date", "Due date", kind="date"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.MILESTONE_STATUSES, default="Pending",
                      required=True),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]
        dlg = RecordDialog(self.app.root, "New milestone", fields)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            self.db.execute("""INSERT INTO research_thesis_milestones
                (thesis_id,name,due_date,status,notes)
                VALUES(?,?,?,?,?)""",
                (tid, d.get("name"), d.get("due_date"),
                 d.get("status"), d.get("notes")))
            self._refresh_milestones(tid)
            self.app.dashboard.refresh()

    def complete_milestone(self):
        tid = self._selected_thesis_id()
        sel = self.ms_tree.selection()
        if not (tid and sel):
            messagebox.showinfo("No milestone selected",
                                "Select a milestone to complete.", parent=self)
            return
        mid = int(sel[0])
        self.db.execute(
            "UPDATE research_thesis_milestones SET status='Completed', "
            "completed_date=? WHERE id=?",
            (date.today().isoformat(), mid))
        self._refresh_milestones(tid)
        self.app.dashboard.refresh()

    def delete_milestone(self):
        tid = self._selected_thesis_id()
        sel = self.ms_tree.selection()
        if not (tid and sel):
            return
        if not messagebox.askyesno("Confirm",
                                   "Delete the selected milestone?",
                                   parent=self):
            return
        self.db.execute("DELETE FROM research_thesis_milestones WHERE id=?",
                        (int(sel[0]),))
        self._refresh_milestones(tid)
        self.app.dashboard.refresh()

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_theses
            (student_id,title,degree,department,primary_supervisor_id,
             secondary_supervisor_id,start_date,expected_submission,
             submission_date,viva_date,internal_examiner_id,
             external_examiner_id,status,outcome)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("student_id"), d.get("title"), d.get("degree"),
             d.get("department"), d.get("primary_supervisor_id"),
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_theses SET
            student_id=?,title=?,degree=?,department=?,
            primary_supervisor_id=?,secondary_supervisor_id=?,
            start_date=?,expected_submission=?,submission_date=?,
            viva_date=?,internal_examiner_id=?,external_examiner_id=?,
            status=?,outcome=? WHERE id=?""",
            (d.get("student_id"), d.get("title"), d.get("degree"),
             d.get("department"), d.get("primary_supervisor_id"),
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome"), pk))


# ---------------------------------------------------------------------------
# People module
# ---------------------------------------------------------------------------

class PeopleTab(TableModule):
    title = "People Directory"
    subtitle = "Staff, students and external examiners."
    table_name = "people"

    ROLES = ["staff", "student", "examiner", "external"]

    def get_columns(self):
        cols = ("name", "role", "department", "email")
        heads = ("Name", "Role", "Department", "Email")
        widths = (220, 110, 200, 260)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT * FROM research_people
                WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(email,'')) LIKE ?
                   OR LOWER(COALESCE(department,'')) LIKE ?
                   OR LOWER(role) LIKE ?
                ORDER BY name""", (q, q, q, q))
        return self.db.query("SELECT * FROM research_people ORDER BY name")

    def row_to_tree_values(self, row):
        return (row["name"], row["role"],
                row["department"] or "—", row["email"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("name", "Full name", required=True),
            FieldSpec("email", "Email"),
            FieldSpec("role", "Role", kind="combo",
                      choices=self.ROLES, required=True),
            FieldSpec("department", "Department"),
        ]

    def render_detail(self, row):
        self.detail_text.insert("end", f"{row['name']}\n", ("section",))
        self.detail_text.insert("end", f"{row['role']}\n\n", ("muted",))
        self._write_detail([
            ("Email", row.get("email")),
            ("Department", row.get("department")),
            ("Created", fmt_date(row.get("created_at"))),
        ])

        # Quick links — what this person is involved in
        pid = row["id"]
        ethics = self.db.query(
            "SELECT reference,title FROM research_ethics_applications "
            "WHERE principal_investigator_id=?", (pid,))
        outputs = self.db.query(
            "SELECT title FROM research_outputs WHERE lead_author_id=?",
            (pid,))
        ip = self.db.query(
            "SELECT reference,title FROM research_ip_assets WHERE inventor_id=?",
            (pid,))
        theses = self.db.query(
            "SELECT title FROM research_theses WHERE student_id=? "
            "OR primary_supervisor_id=? OR secondary_supervisor_id=? "
            "OR internal_examiner_id=? OR external_examiner_id=?",
            (pid, pid, pid, pid, pid))

        self.detail_text.insert("end", "Involvement\n", ("section",))
        for label, items in [
            ("Ethics (as PI)", [f"{r['reference']} — {r['title']}" for r in ethics]),
            ("Outputs (as lead)", [r["title"] for r in outputs]),
            ("IP (as inventor)",
             [f"{r['reference']} — {r['title']}" for r in ip]),
            ("Theses", [r["title"] for r in theses]),
        ]:
            self.detail_text.insert("end", f"\n{label}\n", ("label",))
            if not items:
                self.detail_text.insert("end", "  —\n", ("muted",))
            else:
                for it in items[:6]:
                    self.detail_text.insert("end", f"  • {it}\n", ("value",))
                if len(items) > 6:
                    self.detail_text.insert(
                        "end", f"  … and {len(items) - 6} more\n", ("muted",))

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_people(name,email,role,department,created_at)
            VALUES(?,?,?,?,?)""",
            (d.get("name"), d.get("email"), d.get("role"),
             d.get("department"), datetime.now().isoformat()))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_people SET name=?,email=?,role=?,department=?
            WHERE id=?""",
            (d.get("name"), d.get("email"), d.get("role"),
             d.get("department"), pk))


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class UniversityApp:
    def __init__(self, host=None):
        """Build the Research Portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess entry point) — create a new
            ``tk.Tk()`` root and own it; ``run()`` enters mainloop.
          * a workspace tab ``Frame`` (passed by the main GUI's
            ``open_in_workspace``) — embed inside it; the caller owns
            the window and its mainloop.
          * a ``Toplevel`` — embed inside it without owning the
            mainloop (uncommon, but supported for symmetry).
        """
        self.db = Database()
        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        logger.info("Research Portal starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        if host is None:
            self.root = tk.Tk()
            self.root.title("University Research Management System")
            self.root.geometry("1320x820")
            self.root.minsize(1100, 700)
            self.root.configure(bg=PALETTE["bg"])
            self._owns_root = True
        else:
            self.root = host
            self._owns_root = False
            try:
                self.root.configure(bg=PALETTE["bg"])
            except tk.TclError:
                pass

        configure_styles()
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self):
        header = tk.Frame(self.root, bg=PALETTE["header"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=PALETTE["header"])
        left.pack(side="left", padx=24, pady=10)
        tk.Label(left, text="🎓  University Research Office",
                 bg=PALETTE["header"], fg=PALETTE["text"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(left, text="Ethics · Outputs · IP · Research Degrees",
                 bg=PALETTE["header"], fg=PALETTE["muted"],
                 font=("Segoe UI", 10)).pack(anchor="w")

        right = tk.Frame(header, bg=PALETTE["header"])
        right.pack(side="right", padx=24)
        tk.Label(right, text=datetime.now().strftime("%A, %d %B %Y"),
                 bg=PALETTE["header"], fg=PALETTE["muted"],
                 font=("Segoe UI", 10)).pack(anchor="e", pady=(14, 0))
        role = (self.user or {}).get('role') or ('Research Administrator' if self.user else 'not signed in')
        tk.Label(right,
                 text=f"{self.user_display}  ({role})",
                 bg=PALETTE["header"], fg=PALETTE["text"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="e")

    def _build_body(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self.dashboard = DashboardTab(self.notebook, self.db, self)
        self.ethics = EthicsTab(self.notebook, self.db, self)
        self.outputs = OutputsTab(self.notebook, self.db, self)
        self.ip = IPTab(self.notebook, self.db, self)
        self.thesis = ThesisTab(self.notebook, self.db, self)
        self.people = PeopleTab(self.notebook, self.db, self)

        self.notebook.add(self.dashboard, text="  Dashboard  ")
        self.notebook.add(self.ethics, text="  Ethics  ")
        self.notebook.add(self.outputs, text="  Outputs (REF)  ")
        self.notebook.add(self.ip, text="  IP & Commercialisation  ")
        self.notebook.add(self.thesis, text="  Theses & Vivas  ")
        self.notebook.add(self.people, text="  People  ")

        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda e: self._on_tab_changed())

    def _on_tab_changed(self):
        current = self.notebook.select()
        if not current:
            return
        widget = self.notebook.nametowidget(current)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["border"], height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Label(bar, text="Data: central student_records.db",
                 bg=PALETTE["border"], fg=PALETTE["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=12)
        tk.Label(bar, text="Ready",
                 bg=PALETTE["border"], fg=PALETTE["muted"],
                 font=("Segoe UI", 9)).pack(side="right", padx=12)

    def run(self):
        if not self._owns_root:
            # Embedded mode: caller owns mainloop. Just hook DB close
            # to the host's destroy.
            try:
                self.root.bind("<Destroy>",
                               lambda e, r=self.root: self.db.close()
                               if e.widget is r else None,
                               add="+")
            except tk.TclError:
                pass
            return
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.db.close()
        if self._owns_root:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _remove_legacy_db()
    app = UniversityApp()
    app.run()


if __name__ == "__main__":
    main()
