"""
University Risk Management System
A GUI-based application for identifying, assessing, tracking, and mitigating
risks across university operations (academic, financial, IT, safety, compliance).

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. New/edited risks are stamped with the
current user; the header shows who is signed in.

Persistence: rows live in the central `student_records.db` `risks` table
(reached via `infrastructure.database.db.get_connection`). The legacy
local `university_risks.db` file alongside this module is removed on
startup if it still exists.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import csv
import logging
import os
import sqlite3
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, falling
    back to the in-process global auth singleton."""
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


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown User')


def _user_can_write(user):
    """Risk register edits are restricted to admin/staff roles. Read-only
    otherwise."""
    if not user:
        return False
    role = (user.get('role') or '').lower()
    return role in ('admin', 'administrator', 'superadmin', 'staff',
                    'lecturer', 'manager')


# ---------------------------------------------------------------------------
# Configuration & constants
# ---------------------------------------------------------------------------

# Legacy local DB file — we now use the central student_records.db.
# The file is deleted on startup if it still exists alongside this module.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "university_risks.db")

CATEGORIES = [
    "Academic",
    "Financial",
    "IT / Cybersecurity",
    "Health & Safety",
    "Compliance / Legal",
    "Reputational",
    "Operational",
    "Research",
    "Student Affairs",
    "Facilities",
]

DEPARTMENTS = [
    "Administration",
    "Registrar",
    "Finance",
    "IT Services",
    "Human Resources",
    "Facilities Management",
    "Library",
    "Research Office",
    "Student Services",
    "Faculty of Arts",
    "Faculty of Science",
    "Faculty of Engineering",
    "Faculty of Medicine",
    "Faculty of Business",
]

STATUSES = ["Open", "In Progress", "Mitigated", "Accepted", "Closed"]

LIKELIHOOD_LEVELS = {
    1: "Rare",
    2: "Unlikely",
    3: "Possible",
    4: "Likely",
    5: "Almost Certain",
}

IMPACT_LEVELS = {
    1: "Insignificant",
    2: "Minor",
    3: "Moderate",
    4: "Major",
    5: "Catastrophic",
}


# ---------------------------------------------------------------------------
# Data / persistence layer
# ---------------------------------------------------------------------------


@dataclass
class Risk:
    id: Optional[int]
    title: str
    category: str
    department: str
    description: str
    likelihood: int
    impact: int
    status: str
    owner: str
    mitigation: str
    created: str
    updated: str

    @property
    def score(self) -> int:
        return self.likelihood * self.impact

    @property
    def rating(self) -> str:
        s = self.score
        if s >= 20:
            return "Critical"
        if s >= 12:
            return "High"
        if s >= 6:
            return "Medium"
        return "Low"


class RiskDB:
    """Thin wrapper around the central `student_records.db`.

    The `risks` table is part of the canonical schema; this class assumes
    it exists and only ever inserts/reads from it. A short-lived
    connection is opened per call to play nicely with the shared WAL
    pool used elsewhere in the app.
    """

    def __init__(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            self._connect = get_connection
        except Exception:
            logger.exception("Could not import central get_connection")
            raise
        self._ensure_schema()

    def _connection(self):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        # `risks` is in the canonical schema; CREATE IF NOT EXISTS is a
        # belt-and-braces guard for fresh dev DBs that haven't run the
        # full migration set.
        conn = self._connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    department  TEXT NOT NULL,
                    description TEXT,
                    likelihood  INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
                    impact      INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5),
                    status      TEXT NOT NULL,
                    owner       TEXT,
                    mitigation  TEXT,
                    created     TEXT NOT NULL,
                    updated     TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    # -- CRUD ---------------------------------------------------------------

    def add(self, r: Risk) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO risks
                   (title, category, department, description, likelihood, impact,
                    status, owner, mitigation, created, updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (r.title, r.category, r.department, r.description, r.likelihood,
                 r.impact, r.status, r.owner, r.mitigation, now, now),
            )
            conn.commit()
            new_id = cur.lastrowid
            logger.info("Risk added id=%s title=%r owner=%r score=%s",
                        new_id, r.title, r.owner, r.likelihood * r.impact)
        finally:
            conn.close()

        # Cross-domain: publish a 'risk.raised' bus event so other
        # subscribers (calendar, dashboards) see the new entry. If
        # the Risk model has a next_review_date attribute set, also
        # publish a calendar row for that review.
        try:
            from education_system.university_system.modules.services import (
                risk_bus,
            )
            from education_system.university_system.modules.domain.academics.gui._event_bus import publish
            publish("risk.raised",
                    risk_id=new_id, category=r.category,
                    likelihood=r.likelihood, impact=r.impact)
            review_date = getattr(r, 'next_review_date', None)
            if review_date:
                risk_bus.set_review_date(new_id, review_date)
        except Exception:
            pass

        return new_id

    def update(self, r: Risk):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            conn.execute(
                """UPDATE risks SET
                     title=?, category=?, department=?, description=?,
                     likelihood=?, impact=?, status=?, owner=?, mitigation=?,
                     updated=?
                   WHERE id=?""",
                (r.title, r.category, r.department, r.description, r.likelihood,
                 r.impact, r.status, r.owner, r.mitigation, now, r.id),
            )
            conn.commit()
            logger.info("Risk updated id=%s title=%r status=%s", r.id, r.title, r.status)
        finally:
            conn.close()

    def delete(self, risk_id: int):
        conn = self._connection()
        try:
            conn.execute("DELETE FROM risks WHERE id=?", (risk_id,))
            conn.commit()
            logger.info("Risk deleted id=%s", risk_id)
        finally:
            conn.close()

    def fetch_all(self, search: str = "", category: str = "All",
                  status: str = "All") -> list[Risk]:
        query = "SELECT * FROM risks WHERE 1=1"
        params: list = []
        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR owner LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        if category != "All":
            query += " AND category=?"
            params.append(category)
        if status != "All":
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY (likelihood*impact) DESC, id DESC"
        conn = self._connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_risk(row) for row in rows]

    def fetch(self, risk_id: int) -> Optional[Risk]:
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT * FROM risks WHERE id=?", (risk_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_risk(row) if row else None

    def stats(self) -> dict:
        by_rating = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        by_status = {s: 0 for s in STATUSES}
        by_category = {cat: 0 for cat in CATEGORIES}
        conn = self._connection()
        try:
            c = conn.cursor()
            total = c.execute("SELECT COUNT(*) FROM risks").fetchone()[0]
            rows = c.execute("SELECT likelihood, impact, status, category FROM risks").fetchall()
        finally:
            conn.close()
        for row in rows:
            score = row[0] * row[1]
            if score >= 20:
                by_rating["Critical"] += 1
            elif score >= 12:
                by_rating["High"] += 1
            elif score >= 6:
                by_rating["Medium"] += 1
            else:
                by_rating["Low"] += 1
            by_status[row[2]] = by_status.get(row[2], 0) + 1
            by_category[row[3]] = by_category.get(row[3], 0) + 1
        return {
            "total": total,
            "by_rating": by_rating,
            "by_status": by_status,
            "by_category": by_category,
        }

    @staticmethod
    def _row_to_risk(row: sqlite3.Row) -> Risk:
        return Risk(
            id=row["id"],
            title=row["title"],
            category=row["category"],
            department=row["department"],
            description=row["description"] or "",
            likelihood=row["likelihood"],
            impact=row["impact"],
            status=row["status"],
            owner=row["owner"] or "",
            mitigation=row["mitigation"] or "",
            created=row["created"],
            updated=row["updated"],
        )


# ---------------------------------------------------------------------------
# GUI — Risk entry / edit dialog
# ---------------------------------------------------------------------------


class RiskDialog(tk.Toplevel):
    """Modal dialog for creating or editing a single risk."""

    def __init__(self, parent, db: RiskDB, risk: Optional[Risk] = None,
                 default_owner: str = ""):
        super().__init__(parent)
        self.db = db
        self.risk = risk
        self.result: Optional[Risk] = None

        self.title("Edit Risk" if risk else "New Risk")
        self.geometry("560x620")
        self.transient(parent)
        self.configure(padx=16, pady=16)
        # Defer grab_set until the window is mapped — calling it earlier
        # raises "grab failed: window not viewable" on some WMs.
        self.after(50, self._safe_grab)

        self._build_form()
        if risk:
            self._populate(risk)
        elif default_owner:
            self.owner_var.set(default_owner)

    def _safe_grab(self):
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            logger.debug("grab_set deferred — window not yet viewable", exc_info=True)

    # -- UI construction ----------------------------------------------------

    def _build_form(self):
        row = 0

        ttk.Label(self, text="Title *").grid(row=row, column=0, sticky="w")
        self.title_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.title_var, width=50).grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(self, text="Category *").grid(row=row, column=0, sticky="w")
        self.category_var = tk.StringVar(value=CATEGORIES[0])
        ttk.Combobox(self, textvariable=self.category_var,
                     values=CATEGORIES, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(self, text="Department *").grid(row=row, column=0, sticky="w")
        self.department_var = tk.StringVar(value=DEPARTMENTS[0])
        ttk.Combobox(self, textvariable=self.department_var,
                     values=DEPARTMENTS, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(self, text="Owner").grid(row=row, column=0, sticky="w")
        self.owner_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.owner_var).grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(self, text="Description").grid(row=row, column=0, sticky="nw")
        self.description_text = tk.Text(self, height=5, width=45, wrap="word")
        self.description_text.grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(self, text="Likelihood *").grid(row=row, column=0, sticky="w")
        self.likelihood_var = tk.StringVar(value=f"3 - {LIKELIHOOD_LEVELS[3]}")
        ttk.Combobox(
            self, textvariable=self.likelihood_var,
            values=[f"{k} - {v}" for k, v in LIKELIHOOD_LEVELS.items()],
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(self, text="Impact *").grid(row=row, column=0, sticky="w")
        self.impact_var = tk.StringVar(value=f"3 - {IMPACT_LEVELS[3]}")
        ttk.Combobox(
            self, textvariable=self.impact_var,
            values=[f"{k} - {v}" for k, v in IMPACT_LEVELS.items()],
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(self, text="Status *").grid(row=row, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Open")
        ttk.Combobox(self, textvariable=self.status_var,
                     values=STATUSES, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(self, text="Mitigation Plan").grid(row=row, column=0, sticky="nw")
        self.mitigation_text = tk.Text(self, height=6, width=45, wrap="word")
        self.mitigation_text.grid(row=row, column=1, sticky="ew", pady=4)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(16, 0), sticky="e")
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right")

        self.columnconfigure(1, weight=1)

    def _populate(self, r: Risk):
        self.title_var.set(r.title)
        self.category_var.set(r.category)
        self.department_var.set(r.department)
        self.owner_var.set(r.owner)
        self.description_text.insert("1.0", r.description)
        # Combobox displays "N - Label" but holds IntVar; set the text directly
        for cb in self.winfo_children():
            pass
        # Set likelihood / impact via matching string
        self._set_combo_int(self.likelihood_var, r.likelihood, LIKELIHOOD_LEVELS)
        self._set_combo_int(self.impact_var, r.impact, IMPACT_LEVELS)
        self.status_var.set(r.status)
        self.mitigation_text.insert("1.0", r.mitigation)

    @staticmethod
    def _set_combo_int(var, value, mapping):
        # Display "value - label" but keep numeric on read via parsing
        var.set(f"{value} - {mapping[value]}")

    # -- Save logic ---------------------------------------------------------

    def _parse_level(self, raw) -> int:
        """Accepts 3, '3', or '3 - Possible' and returns the integer 3."""
        if isinstance(raw, int):
            return raw
        s = str(raw).strip()
        if " - " in s:
            s = s.split(" - ", 1)[0]
        return int(s)

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Validation", "Title is required.", parent=self)
            return
        try:
            likelihood = self._parse_level(self.likelihood_var.get())
            impact = self._parse_level(self.impact_var.get())
            if not (1 <= likelihood <= 5 and 1 <= impact <= 5):
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showerror(
                "Validation",
                "Likelihood and Impact must be values 1–5.",
                parent=self,
            )
            return

        r = Risk(
            id=self.risk.id if self.risk else None,
            title=title,
            category=self.category_var.get(),
            department=self.department_var.get(),
            description=self.description_text.get("1.0", "end").strip(),
            likelihood=likelihood,
            impact=impact,
            status=self.status_var.get(),
            owner=self.owner_var.get().strip(),
            mitigation=self.mitigation_text.get("1.0", "end").strip(),
            created=self.risk.created if self.risk else "",
            updated="",
        )

        if self.risk:
            self.db.update(r)
        else:
            new_id = self.db.add(r)
            r.id = new_id

        self.result = r
        self.destroy()


# ---------------------------------------------------------------------------
# GUI — main application window
# ---------------------------------------------------------------------------


class RiskApp(tk.Tk):
    """Main application: dashboard + risk register + filters + actions."""

    RATING_COLORS = {
        "Critical": "#c62828",  # red
        "High":     "#ef6c00",  # orange
        "Medium":   "#f9a825",  # amber
        "Low":      "#2e7d32",  # green
    }

    def __init__(self):
        super().__init__()
        self.db = RiskDB()

        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        self.can_write = _user_can_write(self.user)
        logger.info("Risk Management starting user=%s role=%s write=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none',
                    self.can_write)

        self.title("University Risk Management System")
        self.geometry("1180x720")
        self.minsize(960, 600)

        self._configure_style()
        self._build_layout()
        self.refresh()

    # -- Styling ------------------------------------------------------------

    def _configure_style(self):
        style = ttk.Style(self)
        # Use a theme that respects custom background colours on Treeview rows
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Dashboard.TLabel", font=("Segoe UI", 11))
        style.configure("DashboardValue.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))

    # -- Layout -------------------------------------------------------------

    def _build_layout(self):
        # --- Header --------------------------------------------------------
        header = ttk.Frame(self, padding=(14, 12))
        header.pack(fill="x")
        ttk.Label(header, text="University Risk Management System",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(header,
                  text="Identify • Assess • Mitigate • Monitor",
                  foreground="#555").pack(side="left", padx=(14, 0))
        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        ttk.Label(header,
                  text=f"Signed in: {self.user_display}  ({role})",
                  foreground="#1565c0").pack(side="right")

        # --- Dashboard cards ----------------------------------------------
        self.dashboard = ttk.Frame(self, padding=(14, 0, 14, 10))
        self.dashboard.pack(fill="x")

        # --- Toolbar -------------------------------------------------------
        toolbar = ttk.Frame(self, padding=(14, 6))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="+ New Risk", command=self.new_risk).pack(side="left")
        ttk.Button(toolbar, text="Edit", command=self.edit_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self.delete_risk).pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Matrix", command=self.show_matrix).pack(side="left", padx=4)

        # Filters on the right
        ttk.Label(toolbar, text="Status:").pack(side="left", padx=(16, 2))
        self.status_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self.status_filter,
                     values=["All"] + STATUSES, state="readonly", width=14
                     ).pack(side="left")

        ttk.Label(toolbar, text="Category:").pack(side="left", padx=(10, 2))
        self.category_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self.category_filter,
                     values=["All"] + CATEGORIES, state="readonly", width=20
                     ).pack(side="left")

        ttk.Label(toolbar, text="Search:").pack(side="left", padx=(10, 2))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side="left")
        ttk.Button(toolbar, text="Apply", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Reset", command=self._reset_filters).pack(side="left")

        # Bind filter changes
        self.status_filter.trace_add("write", lambda *a: self.refresh())
        self.category_filter.trace_add("write", lambda *a: self.refresh())
        search_entry.bind("<Return>", lambda e: self.refresh())

        # --- Treeview (risk register) -------------------------------------
        tree_frame = ttk.Frame(self, padding=(14, 0, 14, 14))
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "title", "category", "department",
                   "likelihood", "impact", "score", "rating",
                   "status", "owner", "updated")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="browse")
        headings = {
            "id": ("ID", 50),
            "title": ("Title", 240),
            "category": ("Category", 130),
            "department": ("Department", 150),
            "likelihood": ("Lklhd", 60),
            "impact": ("Impact", 60),
            "score": ("Score", 60),
            "rating": ("Rating", 90),
            "status": ("Status", 100),
            "owner": ("Owner", 120),
            "updated": ("Updated", 140),
        }
        for col, (label, width) in headings.items():
            anchor = "center" if col in {"id", "likelihood", "impact", "score"} else "w"
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._sort_by(c, False))
            self.tree.column(col, width=width, anchor=anchor,
                             stretch=(col == "title"))

        # Row color tags per rating
        for rating, color in self.RATING_COLORS.items():
            self.tree.tag_configure(rating, background=color, foreground="white")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self.edit_risk())

        # --- Status bar ----------------------------------------------------
        self.status_bar = ttk.Label(self, text="", anchor="w",
                                    padding=(10, 4), relief="sunken")
        self.status_bar.pack(fill="x", side="bottom")

    # -- Dashboard rendering -----------------------------------------------

    def _render_dashboard(self):
        for child in self.dashboard.winfo_children():
            child.destroy()

        stats = self.db.stats()
        cards = [
            ("Total Risks", stats["total"], "#1565c0"),
            ("Critical",    stats["by_rating"]["Critical"], self.RATING_COLORS["Critical"]),
            ("High",        stats["by_rating"]["High"],     self.RATING_COLORS["High"]),
            ("Medium",      stats["by_rating"]["Medium"],   self.RATING_COLORS["Medium"]),
            ("Low",         stats["by_rating"]["Low"],      self.RATING_COLORS["Low"]),
            ("Open",        stats["by_status"].get("Open", 0), "#37474f"),
        ]

        for i, (label, value, color) in enumerate(cards):
            card = tk.Frame(self.dashboard, bg=color, padx=14, pady=10,
                            highlightthickness=0, bd=0)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            tk.Label(card, text=str(value), bg=color, fg="white",
                     font=("Segoe UI", 20, "bold")).pack(anchor="w")
            tk.Label(card, text=label, bg=color, fg="white",
                     font=("Segoe UI", 10)).pack(anchor="w")
            self.dashboard.columnconfigure(i, weight=1)

    # -- Data refresh -------------------------------------------------------

    def refresh(self):
        self._render_dashboard()

        for item in self.tree.get_children():
            self.tree.delete(item)

        risks = self.db.fetch_all(
            search=self.search_var.get().strip(),
            category=self.category_filter.get(),
            status=self.status_filter.get(),
        )
        for r in risks:
            self.tree.insert(
                "", "end",
                values=(r.id, r.title, r.category, r.department,
                        r.likelihood, r.impact, r.score, r.rating,
                        r.status, r.owner, r.updated),
                tags=(r.rating,),
            )
        self.status_bar.config(text=f"Showing {len(risks)} risk(s)")

    def _reset_filters(self):
        self.status_filter.set("All")
        self.category_filter.set("All")
        self.search_var.set("")
        self.refresh()

    def _sort_by(self, col, reverse):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        # Try numeric sort where appropriate
        def key(v):
            try:
                return float(v[0])
            except ValueError:
                return v[0].lower()
        items.sort(key=key, reverse=reverse)
        for i, (_, k) in enumerate(items):
            self.tree.move(k, "", i)
        self.tree.heading(col, command=lambda: self._sort_by(col, not reverse))

    # -- Selection helpers -------------------------------------------------

    def _selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0], "values")[0])

    # -- Actions ------------------------------------------------------------

    def _require_write(self, action: str) -> bool:
        if self.can_write:
            return True
        logger.warning("Blocked %s by user=%s — read-only role", action, self.user_display)
        messagebox.showwarning(
            "Read-only",
            "Your account is read-only for the risk register.\n"
            "Sign in with an admin/staff role to make changes.")
        return False

    def new_risk(self):
        if not self._require_write("new_risk"):
            return
        dlg = RiskDialog(self, self.db, default_owner=self.user_display)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def edit_risk(self):
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a risk to edit.")
            return
        if not self._require_write("edit_risk"):
            return
        risk = self.db.fetch(rid)
        if not risk:
            return
        dlg = RiskDialog(self, self.db, risk)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def delete_risk(self):
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Select a risk to delete.")
            return
        if not self._require_write("delete_risk"):
            return
        if messagebox.askyesno("Confirm", f"Delete risk #{rid}? This cannot be undone."):
            self.db.delete(rid)
            self.refresh()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="university_risks.csv",
        )
        if not path:
            return
        risks = self.db.fetch_all()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Title", "Category", "Department", "Description",
                "Likelihood", "Impact", "Score", "Rating",
                "Status", "Owner", "Mitigation", "Created", "Updated",
            ])
            for r in risks:
                writer.writerow([
                    r.id, r.title, r.category, r.department, r.description,
                    r.likelihood, r.impact, r.score, r.rating,
                    r.status, r.owner, r.mitigation, r.created, r.updated,
                ])
        logger.info("Exported %s risk(s) to %s by user=%s",
                    len(risks), path, self.user_display)
        messagebox.showinfo("Export", f"Exported {len(risks)} risk(s) to:\n{path}")

    def show_matrix(self):
        MatrixWindow(self, self.db)


# ---------------------------------------------------------------------------
# 5x5 Risk-matrix heat-map window
# ---------------------------------------------------------------------------


class MatrixWindow(tk.Toplevel):
    """Displays a 5x5 likelihood-vs-impact heat-map with live counts."""

    def __init__(self, parent, db: RiskDB):
        super().__init__(parent)
        self.db = db
        self.title("Risk Matrix (Likelihood × Impact)")
        self.geometry("640x560")
        self.transient(parent)
        self.configure(padx=14, pady=14)

        ttk.Label(self,
                  text="Risk Matrix — cells show count of risks",
                  font=("Segoe UI", 13, "bold")).pack(pady=(0, 8))

        self._build_matrix()

    def _build_matrix(self):
        # Count risks per (likelihood, impact) cell
        counts = {(l, i): 0 for l in range(1, 6) for i in range(1, 6)}
        for r in self.db.fetch_all():
            counts[(r.likelihood, r.impact)] += 1

        grid = ttk.Frame(self)
        grid.pack(expand=True, fill="both")

        # Top-left corner / axis labels
        tk.Label(grid, text="Likelihood ↓ / Impact →",
                 font=("Segoe UI", 9, "italic")).grid(row=0, column=0, padx=4, pady=4)

        # Column headers (Impact 1..5)
        for i in range(1, 6):
            tk.Label(grid, text=f"{i}\n{IMPACT_LEVELS[i]}",
                     font=("Segoe UI", 9, "bold")
                     ).grid(row=0, column=i, padx=2, pady=2, sticky="nsew")

        # Rows — likelihood 5 at top, 1 at bottom (standard risk-matrix orientation)
        for display_row, likelihood in enumerate(range(5, 0, -1), start=1):
            tk.Label(grid, text=f"{likelihood}\n{LIKELIHOOD_LEVELS[likelihood]}",
                     font=("Segoe UI", 9, "bold")
                     ).grid(row=display_row, column=0, padx=2, pady=2, sticky="nsew")
            for impact in range(1, 6):
                score = likelihood * impact
                color = self._cell_color(score)
                count = counts[(likelihood, impact)]
                cell = tk.Label(
                    grid,
                    text=f"{count}\nscore {score}",
                    bg=color, fg="white",
                    font=("Segoe UI", 10, "bold"),
                    width=10, height=3, relief="ridge",
                )
                cell.grid(row=display_row, column=impact, padx=1, pady=1, sticky="nsew")

        for c in range(6):
            grid.columnconfigure(c, weight=1)
        for r in range(6):
            grid.rowconfigure(r, weight=1)

        # Legend
        legend = ttk.Frame(self)
        legend.pack(fill="x", pady=(14, 0))
        for label, color in [("Low (1-5)", "#2e7d32"),
                             ("Medium (6-11)", "#f9a825"),
                             ("High (12-19)", "#ef6c00"),
                             ("Critical (20-25)", "#c62828")]:
            tk.Label(legend, text=f"  {label}  ", bg=color, fg="white",
                     font=("Segoe UI", 9, "bold"), padx=6, pady=4
                     ).pack(side="left", padx=4)

    @staticmethod
    def _cell_color(score: int) -> str:
        if score >= 20:
            return "#c62828"
        if score >= 12:
            return "#ef6c00"
        if score >= 6:
            return "#f9a825"
        return "#2e7d32"


# ---------------------------------------------------------------------------
# Sample-data seeding (only when database is empty)
# ---------------------------------------------------------------------------


def seed_sample_data(db: RiskDB):
    if db.fetch_all():
        return
    samples = [
        Risk(None, "Ransomware attack on student records", "IT / Cybersecurity",
             "IT Services",
             "A successful ransomware attack could encrypt the Student Information System, "
             "blocking access to enrolment and grading data.",
             3, 5, "In Progress", "CISO",
             "Immutable off-site backups, endpoint detection, phishing-awareness training, "
             "quarterly tabletop exercises.", "", ""),
        Risk(None, "Loss of research grant funding", "Financial", "Research Office",
             "Major grant non-renewal could affect staffing and ongoing studies across several "
             "research groups.",
             2, 4, "Open", "Head of Research",
             "Diversify funding sources; maintain 6-month operating reserve; "
             "pursue industry-partnership co-funding.", "", ""),
        Risk(None, "Laboratory chemical spill", "Health & Safety",
             "Faculty of Science",
             "Spill of hazardous reagents in undergraduate chemistry lab with potential injury "
             "and environmental exposure.",
             2, 4, "Mitigated", "Safety Officer",
             "Spill kits in every lab, mandatory safety induction, annual refresher, "
             "fume-hood compliance checks.", "", ""),
        Risk(None, "GDPR / data-protection breach", "Compliance / Legal",
             "Administration",
             "Unauthorised disclosure of student personal data could trigger regulatory fines "
             "and reputational harm.",
             3, 4, "Open", "DPO",
             "DPIA for new systems, role-based access control, annual staff training, "
             "encrypted data-at-rest.", "", ""),
        Risk(None, "Plagiarism / academic misconduct rise", "Academic",
             "Registrar",
             "Increased use of generative AI may erode assessment integrity in written "
             "coursework.",
             4, 3, "In Progress", "Academic Registrar",
             "Revise assessment design toward viva and in-person components; deploy "
             "AI-awareness training for staff; update academic-integrity policy.", "", ""),
        Risk(None, "Campus fire-safety non-compliance", "Facilities",
             "Facilities Management",
             "Older residential blocks may not meet updated fire-safety regulations.",
             2, 5, "Open", "Estates Director",
             "Commission third-party fire-risk assessment; schedule remediation within FY;"
             " install additional detectors and signage.", "", ""),
        Risk(None, "Student mental-health crisis capacity", "Student Affairs",
             "Student Services",
             "Counselling demand exceeds service capacity, leading to long wait times.",
             4, 4, "In Progress", "Head of Wellbeing",
             "Hire two additional counsellors; introduce online CBT self-help; partner with "
             "local NHS trust for urgent referrals.", "", ""),
        Risk(None, "Reputational damage from social-media incident", "Reputational",
             "Administration",
             "Viral negative coverage could damage applications and donor relationships.",
             3, 3, "Open", "Communications Director",
             "Crisis-communications playbook, social-media monitoring tool, media-training "
             "for senior leaders.", "", ""),
        Risk(None, "Exam-system outage during assessment week", "Operational",
             "IT Services",
             "Failure of online proctoring/LMS during exam period could disrupt thousands of "
             "candidates.",
             2, 5, "Mitigated", "IT Operations Manager",
             "HA architecture, annual load-test at 150% capacity, paper-based fallback "
             "process documented.", "", ""),
        Risk(None, "International student visa-policy change", "Compliance / Legal",
             "Registrar",
             "Government visa policy shift could sharply reduce international enrolment.",
             3, 4, "Open", "International Office Director",
             "Diversify source countries, strengthen domestic recruitment pipeline, "
             "scenario-plan for 20% / 40% reductions.", "", ""),
    ]
    for r in samples:
        db.add(r)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _remove_legacy_db():
    """Drop the old per-module university_risks.db file (and WAL/SHM
    siblings) — data now lives in the central student_records.db.
    """
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy risk DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path, exc_info=True)


def main():
    _remove_legacy_db()
    app = RiskApp()
    # Seed only if the central risks table is empty (first run on a fresh DB)
    if not app.db.fetch_all():
        logger.info("Risks table empty — seeding sample data")
        seed_sample_data(app.db)
        app.refresh()
    app.mainloop()


if __name__ == "__main__":
    main()
