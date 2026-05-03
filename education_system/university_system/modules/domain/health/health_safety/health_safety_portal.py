"""
University Health and Safety Portal
A comprehensive GUI application for managing health and safety at a university.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The portal has no in-app login screen.

Persistence: incidents, hazards, and training records live in the
central university `student_records.db` (tables `hs_incidents`,
`hs_hazards`, `hs_training`), reached via
`infrastructure.database.db.get_connection`. Legacy JSON sidecar files
(`incidents.json`, `hazards.json`, `training.json`) and any stray
SQLite files alongside this module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import logging
import os
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


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, with a
    fallback to the in-process global auth singleton."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    department = os.environ.get('EDU_AUTH_DEPARTMENT') or ''

    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role or 'Staff',
            'email': email,
            'department': department or 'University',
            'permissions': [p for p in perms_raw.split(',') if p],
        }

    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            u = dict(ga.current_user)
            u.setdefault('role', 'Staff')
            u.setdefault('department', 'University')
            return u
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
class HSDatabase:
    """Wraps the central `student_records.db` for incidents, hazards,
    and training records. Tables are created on demand."""

    def __init__(self):
        from education_system.university_system.infrastructure.database.db import get_connection
        self._connect = get_connection
        self._ensure_schema()

    def _connection(self):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS hs_incidents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref             TEXT,
                    incident_type   TEXT,
                    location        TEXT,
                    incident_date   TEXT,
                    severity        TEXT,
                    people_involved TEXT,
                    description     TEXT,
                    actions_taken   TEXT,
                    reported_by     TEXT,
                    department      TEXT,
                    status          TEXT DEFAULT 'Open',
                    reported_at     TEXT NOT NULL,
                    updated_at      TEXT
                );
                CREATE TABLE IF NOT EXISTS hs_hazards (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref             TEXT,
                    category        TEXT,
                    location        TEXT,
                    risk_level      TEXT,
                    description     TEXT,
                    mitigation      TEXT,
                    reported_by     TEXT,
                    department      TEXT,
                    status          TEXT DEFAULT 'Active',
                    reported_at     TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hs_training (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user            TEXT NOT NULL,
                    module          TEXT NOT NULL,
                    department      TEXT,
                    completed_at    TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    # --- incidents ------------------------------------------------------
    def list_incidents(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_incidents ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_incident(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO hs_incidents
                   (ref, incident_type, location, incident_date, severity,
                    people_involved, description, actions_taken,
                    reported_by, department, status, reported_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get('ref'), data.get('incident_type'), data.get('location'),
                 data.get('incident_date'), data.get('severity'),
                 data.get('people_involved'), data.get('description'),
                 data.get('actions_taken'), data.get('reported_by'),
                 data.get('department'), data.get('status', 'Open'), now),
            )
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        # Bus broadcast (#2): subscribers (First Aid, Finance, DM,
        # chatbot) link, charge, attach evidence, and notify managers.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_INCIDENT_LOGGED,
            )
            publish(
                EVENT_INCIDENT_LOGGED,
                incident_id=new_id, domain="hs",
                ref=data.get('ref'),
                incident_type=data.get('incident_type'),
                severity=data.get('severity'),
                location=data.get('location'),
                department=data.get('department'),
                reported_by=data.get('reported_by'),
                description=data.get('description'),
            )
        except Exception:
            pass

        # Finance link (#7) — if the incident carries an estimated cost,
        # post it as a charge against the responsible department.
        cost = data.get('estimated_cost') or data.get('cost')
        if cost:
            try:
                amount = float(cost)
                if amount > 0:
                    from education_system.university_system.modules.services.finance_bus import (
                        raise_charge,
                    )
                    raise_charge(
                        data.get('reported_by') or 'department',
                        amount,
                        source="hs_incident",
                        description=(
                            f"H&S incident #{new_id} ("
                            f"{data.get('incident_type') or 'incident'})"
                        ),
                        reference_id=f"incident:{new_id}",
                        processed_by="health_safety_portal",
                    )
            except Exception:
                pass

        return new_id

    def schedule_evacuation_drill(self, *, drill_date: str,
                                  location: str | None = None,
                                  description: str | None = None,
                                  scheduled_by: str | None = None) -> str | None:
        """Persist an evacuation drill as a Calendar event (#8).

        Single source for "what's happening on what day" — the drill
        shows up automatically in the Academic Calendar GUI; H&S
        doesn't run its own drill scheduler.
        """
        try:
            from education_system.university_system.infrastructure.database.db import (
                get_connection,
            )
            import uuid
            event_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO academic_calendar_events "
                    "(id, name, date, description, event_type, "
                    " date_added, last_modified, created_by) "
                    "VALUES (?, ?, ?, ?, 'evacuation_drill', ?, ?, ?)",
                    (event_id,
                     f"Evacuation drill — {location or 'campus'}",
                     drill_date,
                     description or "Scheduled evacuation drill",
                     now, now, scheduled_by),
                )
                conn.commit()
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                        event_type="evacuation_drill", action="created",
                        date=drill_date)
            except Exception:
                pass
            return event_id
        except Exception as exc:
            logger.warning("schedule_evacuation_drill failed: %s", exc)
            return None

    def update_incident_status(self, incident_id: int, status: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            conn.execute(
                "UPDATE hs_incidents SET status=?, updated_at=? WHERE id=?",
                (status, now, incident_id))
            conn.commit()
        finally:
            conn.close()

    # --- hazards --------------------------------------------------------
    def list_hazards(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_hazards ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_hazard(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO hs_hazards
                   (ref, category, location, risk_level, description,
                    mitigation, reported_by, department, status, reported_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (data.get('ref'), data.get('category'), data.get('location'),
                 data.get('risk_level'), data.get('description'),
                 data.get('mitigation'), data.get('reported_by'),
                 data.get('department'), data.get('status', 'Active'), now),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # --- training -------------------------------------------------------
    def list_training(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_training ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_training(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                "INSERT INTO hs_training (user, module, department, completed_at) "
                "VALUES (?,?,?,?)",
                (data['user'], data['module'], data.get('department', ''), now))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def _remove_legacy_files():
    """Delete sidecar JSON files and stray SQLite files left by earlier
    iterations of this module. Data now lives in the central
    `student_records.db`."""
    here = os.path.dirname(os.path.abspath(__file__))
    legacy = ['incidents.json', 'hazards.json', 'training.json']
    targets = [os.path.join(here, name) for name in legacy]
    if os.path.isdir(here):
        for fname in os.listdir(here):
            if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
                targets.append(os.path.join(here, fname))
    # CWD-relative paths are where the JSON files actually got written
    # in earlier runs, so sweep those too.
    for name in legacy:
        targets.append(os.path.abspath(name))
    for path in set(targets):
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy H&S data file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy file %s", path,
                               exc_info=True)


class HealthSafetyPortal:
    def __init__(self, root):
        self.root = root
        self.root.title("University Health & Safety Portal")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        self.root.configure(bg="#f0f4f8")

        # Auth — no in-app login; identity comes from EDU_AUTH_*
        self.current_user = _get_current_user()

        # Persistence
        try:
            self.db = HSDatabase()
        except Exception:
            self.db = None
            logger.exception("H&S Portal starting without DB persistence")

        # In-memory mirrors so existing GUI code can iterate them.
        # Refreshed from the DB before each list/dashboard render.
        self.incidents = []
        self.hazards = []
        self.training_records = []

        logger.info("H&S Portal starting user=%s role=%s db=%s",
                    (self.current_user or {}).get('username') or 'guest',
                    (self.current_user or {}).get('role') or 'none',
                    'on' if self.db else 'off')

        # Setup styling
        self.setup_styles()

        if not self.current_user:
            self.show_no_auth()
        else:
            self.show_dashboard()

    def setup_styles(self):
        """Configure ttk styles for a modern look."""
        style = ttk.Style()
        style.theme_use("clam")

        # Configure colors
        style.configure("TButton",
                       padding=10,
                       font=("Segoe UI", 10),
                       background="#2c5282",
                       foreground="white")
        style.map("TButton",
                 background=[("active", "#2b6cb0")])

        style.configure("Nav.TButton",
                       padding=15,
                       font=("Segoe UI", 11, "bold"),
                       background="#1a365d",
                       foreground="white")
        style.map("Nav.TButton",
                 background=[("active", "#2c5282")])

        style.configure("Danger.TButton",
                       background="#c53030",
                       foreground="white")
        style.map("Danger.TButton",
                 background=[("active", "#9b2c2c")])

        style.configure("Success.TButton",
                       background="#2f855a",
                       foreground="white")
        style.map("Success.TButton",
                 background=[("active", "#276749")])

        style.configure("TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 10))

        style.configure("Header.TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 18, "bold"),
                       foreground="#1a365d")

        style.configure("SubHeader.TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 12, "bold"),
                       foreground="#2c5282")

        style.configure("Treeview",
                       font=("Segoe UI", 10),
                       rowheight=28)
        style.configure("Treeview.Heading",
                       font=("Segoe UI", 10, "bold"),
                       background="#2c5282",
                       foreground="white")

    def _refresh_caches(self):
        """Pull fresh copies of the three datasets from the DB and
        attach the legacy-shaped keys (id/type/date/...) the existing
        GUI render code already uses."""
        if not self.db:
            return
        try:
            incidents = self.db.list_incidents()
            for r in incidents:
                r['id'] = r.get('ref') or f"INC-{r['id']:04d}"
                r['type'] = r.get('incident_type', '')
                r['date'] = r.get('incident_date', '')
            hazards = self.db.list_hazards()
            for r in hazards:
                r['id'] = r.get('ref') or f"HAZ-{r['id']:04d}"
            training = self.db.list_training()
            for r in training:
                # match legacy key name
                r['user'] = r.get('user', '')
            self.incidents = incidents
            self.hazards = hazards
            self.training_records = training
        except sqlite3.Error:
            logger.exception("Failed to refresh H&S caches")

    def clear_window(self):
        """Clear all widgets from the window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    # ==================== NO-AUTH FALLBACK ====================
    def show_no_auth(self):
        """Shown only if the portal was launched outside the main GUI
        and EDU_AUTH_* env vars aren't set."""
        self.clear_window()

        header_frame = tk.Frame(self.root, bg="#1a365d", height=120)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        tk.Label(header_frame,
                text="🏥 University Health & Safety Portal",
                font=("Segoe UI", 24, "bold"),
                bg="#1a365d", fg="white").pack(pady=30)

        body = tk.Frame(self.root, bg="#f0f4f8")
        body.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(body, text="🔒 Authentication Required",
                font=("Segoe UI", 18, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(pady=10)
        tk.Label(body,
                text="Please launch this portal from the main\n"
                     "University System after signing in.",
                font=("Segoe UI", 11),
                bg="#f0f4f8", fg="#2d3748",
                justify="center").pack(pady=10)
        ttk.Button(body, text="Close",
                  command=self.root.destroy).pack(pady=20)

    # ==================== DASHBOARD ====================
    def show_dashboard(self):
        """Display the main dashboard."""
        self.clear_window()

        # Top header
        header = tk.Frame(self.root, bg="#1a365d", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🏥 University Health & Safety Portal",
                font=("Segoe UI", 16, "bold"),
                bg="#1a365d", fg="white").pack(side="left", padx=20, pady=20)

        u = self.current_user or {}
        uname = u.get('username') or u.get('email') or u.get('user_id') or 'Guest'
        user_info = f"👤 {uname} ({u.get('role') or '—'}) | {u.get('department') or '—'}"
        tk.Label(header, text=user_info,
                font=("Segoe UI", 10),
                bg="#1a365d", fg="white").pack(side="right", padx=20, pady=25)

        # Main container with sidebar and content
        main_container = tk.Frame(self.root, bg="#f0f4f8")
        main_container.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(main_container, bg="#2d3748", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        nav_buttons = [
            ("🏠 Dashboard", self.show_dashboard_content),
            ("⚠️ Report Incident", self.show_report_incident),
            ("📋 View Incidents", self.show_incidents_list),
            ("🔍 Report Hazard", self.show_report_hazard),
            ("📊 View Hazards", self.show_hazards_list),
            ("🎓 Training", self.show_training),
            ("📚 Resources", self.show_resources),
            ("🚨 Emergency Info", self.show_emergency),
        ]

        for text, command in nav_buttons:
            btn = tk.Button(sidebar, text=text,
                          font=("Segoe UI", 11),
                          bg="#2d3748", fg="white",
                          bd=0, pady=15, padx=20,
                          anchor="w",
                          activebackground="#4a5568",
                          activeforeground="white",
                          cursor="hand2",
                          command=command)
            btn.pack(fill="x")

        # Content area
        self.content_frame = tk.Frame(main_container, bg="#f0f4f8")
        self.content_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        # Show default dashboard content
        self.show_dashboard_content()

    def clear_content(self):
        """Clear the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_dashboard_content(self):
        """Show dashboard overview with statistics."""
        self.clear_content()
        self._refresh_caches()

        tk.Label(self.content_frame, text="Dashboard Overview",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        # Stats cards
        stats_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        stats_frame.pack(fill="x", pady=10)

        total_incidents = len(self.incidents)
        open_incidents = sum(1 for i in self.incidents if i.get("status") == "Open")
        total_hazards = len(self.hazards)
        high_risk = sum(1 for h in self.hazards if h.get("risk_level") == "High")

        stats = [
            ("Total Incidents", total_incidents, "#3182ce", "📋"),
            ("Open Incidents", open_incidents, "#dd6b20", "⚠️"),
            ("Reported Hazards", total_hazards, "#805ad5", "🔍"),
            ("High Risk Items", high_risk, "#c53030", "🚨"),
        ]

        for i, (label, value, color, icon) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=color, width=200, height=120)
            card.grid(row=0, column=i, padx=10, pady=5, sticky="ew")
            card.pack_propagate(False)
            stats_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=("Segoe UI", 24),
                    bg=color, fg="white").pack(pady=(15, 0))
            tk.Label(card, text=str(value), font=("Segoe UI", 22, "bold"),
                    bg=color, fg="white").pack()
            tk.Label(card, text=label, font=("Segoe UI", 10),
                    bg=color, fg="white").pack()

        # Recent activity
        tk.Label(self.content_frame, text="Recent Incidents",
                font=("Segoe UI", 14, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(30, 10))

        recent_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        recent_frame.pack(fill="both", expand=True, pady=5)

        columns = ("ID", "Type", "Location", "Date", "Severity", "Status")
        tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140, anchor="w")

        # Show last 10 incidents
        for incident in self.incidents[-10:][::-1]:
            tree.insert("", "end", values=(
                incident.get("id", ""),
                incident.get("type", ""),
                incident.get("location", ""),
                incident.get("date", ""),
                incident.get("severity", ""),
                incident.get("status", "")
            ))

        tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Quick actions
        tk.Label(self.content_frame, text="Quick Actions",
                font=("Segoe UI", 14, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(20, 10))

        actions_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        actions_frame.pack(fill="x")

        ttk.Button(actions_frame, text="⚠️ Report New Incident",
                  style="Danger.TButton",
                  command=self.show_report_incident).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="🔍 Report Hazard",
                  command=self.show_report_hazard).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="🎓 View Training",
                  command=self.show_training).pack(side="left", padx=5)

    # ==================== REPORT INCIDENT ====================
    def show_report_incident(self):
        """Show incident reporting form."""
        self.clear_content()

        tk.Label(self.content_frame, text="⚠️ Report an Incident",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 10))

        tk.Label(self.content_frame,
                text="Report any accidents, injuries, or near-misses that occurred on campus.",
                font=("Segoe UI", 10, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 20))

        form = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1, padx=30, pady=20)
        form.pack(fill="both", expand=True)

        # Incident type
        tk.Label(form, text="Incident Type *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=0, column=0, sticky="w", pady=5)
        incident_type = ttk.Combobox(form, values=[
            "Slip/Trip/Fall", "Chemical Spill", "Fire/Smoke", "Equipment Failure",
            "Injury", "Near Miss", "Electrical", "Biological", "Other"
        ], state="readonly", font=("Segoe UI", 10), width=40)
        incident_type.grid(row=0, column=1, pady=5, padx=10, sticky="w")
        incident_type.set("Slip/Trip/Fall")

        # Location
        tk.Label(form, text="Location *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=1, column=0, sticky="w", pady=5)
        location_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        location_entry.grid(row=1, column=1, pady=5, padx=10, sticky="w")

        # Date
        tk.Label(form, text="Date *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=2, column=0, sticky="w", pady=5)
        date_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        date_entry.grid(row=2, column=1, pady=5, padx=10, sticky="w")
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))

        # Severity
        tk.Label(form, text="Severity *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=3, column=0, sticky="w", pady=5)
        severity = ttk.Combobox(form, values=["Low", "Medium", "High", "Critical"],
                                state="readonly", font=("Segoe UI", 10), width=40)
        severity.grid(row=3, column=1, pady=5, padx=10, sticky="w")
        severity.set("Low")

        # People involved
        tk.Label(form, text="People Involved", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=4, column=0, sticky="w", pady=5)
        people_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        people_entry.grid(row=4, column=1, pady=5, padx=10, sticky="w")

        # Description
        tk.Label(form, text="Description *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=5, column=0, sticky="nw", pady=5)
        description = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                                width=42, height=6)
        description.grid(row=5, column=1, pady=5, padx=10, sticky="w")

        # Actions taken
        tk.Label(form, text="Immediate Actions Taken", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=6, column=0, sticky="nw", pady=5)
        actions = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                            width=42, height=4)
        actions.grid(row=6, column=1, pady=5, padx=10, sticky="w")

        # Submit button
        def submit_incident():
            if not location_entry.get() or not description.get("1.0", "end-1c").strip():
                messagebox.showwarning("Validation Error",
                                     "Please fill in all required fields (marked with *).")
                return

            if not self.db:
                messagebox.showerror("Database Unavailable",
                                     "Cannot save — central database is not reachable.")
                logger.error("Incident submit failed — DB unavailable")
                return
            u = self.current_user or {}
            try:
                new_id = self.db.add_incident({
                    "incident_type": incident_type.get(),
                    "location": location_entry.get(),
                    "incident_date": date_entry.get(),
                    "severity": severity.get(),
                    "people_involved": people_entry.get(),
                    "description": description.get("1.0", "end-1c"),
                    "actions_taken": actions.get("1.0", "end-1c"),
                    "reported_by": u.get('username') or u.get('user_id') or '',
                    "department": u.get('department') or '',
                })
            except sqlite3.Error:
                logger.exception("Incident submit failed — DB error")
                messagebox.showerror("Save Error", "Could not save the incident.")
                return
            ref = f"INC-{new_id:04d}"
            self.db._connection_close = None  # no-op; ensure cache rebuilt below
            try:
                conn = self.db._connection()
                conn.execute("UPDATE hs_incidents SET ref=? WHERE id=?", (ref, new_id))
                conn.commit()
                conn.close()
            except sqlite3.Error:
                logger.debug("Could not stamp ref on incident", exc_info=True)
            logger.info("Incident submitted ref=%s severity=%s reporter=%s",
                        ref, severity.get(), u.get('username') or 'unknown')
            messagebox.showinfo("Success",
                              f"Incident {ref} has been reported successfully.\n"
                              f"The H&S team will review it shortly.")
            self.show_dashboard_content()

        btn_frame = tk.Frame(form, bg="white")
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Submit Report",
                  style="Success.TButton",
                  command=submit_incident).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=self.show_dashboard_content).pack(side="left", padx=5)

    # ==================== INCIDENTS LIST ====================
    def show_incidents_list(self):
        """Display all incidents."""
        self.clear_content()
        self._refresh_caches()

        tk.Label(self.content_frame, text="📋 All Incidents",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        # Filter frame
        filter_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="Filter by status:",
                bg="#f0f4f8", font=("Segoe UI", 10)).pack(side="left", padx=5)
        status_filter = ttk.Combobox(filter_frame, values=["All", "Open", "In Progress", "Resolved", "Closed"],
                                     state="readonly", width=15)
        status_filter.set("All")
        status_filter.pack(side="left", padx=5)

        # List frame
        list_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Type", "Location", "Date", "Severity", "Reporter", "Status")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="w")

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        def refresh_list():
            for item in tree.get_children():
                tree.delete(item)
            filter_val = status_filter.get()
            for incident in self.incidents[::-1]:
                if filter_val == "All" or incident.get("status") == filter_val:
                    tree.insert("", "end", values=(
                        incident.get("id", ""),
                        incident.get("type", ""),
                        incident.get("location", ""),
                        incident.get("date", ""),
                        incident.get("severity", ""),
                        incident.get("reported_by", ""),
                        incident.get("status", "")
                    ))

        refresh_list()
        status_filter.bind("<<ComboboxSelected>>", lambda e: refresh_list())

        # View details on double-click
        def view_details(event):
            selected = tree.selection()
            if not selected:
                return
            item = tree.item(selected[0])
            incident_id = item["values"][0]
            incident = next((i for i in self.incidents if i.get("id") == incident_id), None)
            if incident:
                self.show_incident_details(incident)

        tree.bind("<Double-1>", view_details)

        # Buttons
        btn_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        btn_frame.pack(fill="x", pady=10)

        def update_status():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select an incident first.")
                return
            item = tree.item(selected[0])
            incident_id = item["values"][0]
            self.update_incident_status(incident_id, refresh_list)

        ttk.Button(btn_frame, text="View Details",
                  command=lambda: view_details(None)).pack(side="left", padx=5)
        u = self.current_user or {}
        if (u.get('role') or '').lower() in ['h&s officer', 'administrator', 'admin', 'staff']:
            ttk.Button(btn_frame, text="Update Status",
                      command=update_status).pack(side="left", padx=5)

        tk.Label(self.content_frame,
                text="Double-click an incident to view full details.",
                font=("Segoe UI", 9, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w")

    def show_incident_details(self, incident):
        """Show detailed view of an incident."""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Incident Details - {incident.get('id')}")
        detail_window.geometry("600x500")
        detail_window.configure(bg="white")

        tk.Label(detail_window, text=f"Incident {incident.get('id')}",
                font=("Segoe UI", 16, "bold"),
                bg="white", fg="#1a365d").pack(pady=10)

        info_frame = tk.Frame(detail_window, bg="white", padx=20)
        info_frame.pack(fill="both", expand=True)

        details = [
            ("Type:", incident.get("type", "")),
            ("Location:", incident.get("location", "")),
            ("Date:", incident.get("date", "")),
            ("Severity:", incident.get("severity", "")),
            ("People Involved:", incident.get("people_involved", "None")),
            ("Reported By:", incident.get("reported_by", "")),
            ("Department:", incident.get("department", "")),
            ("Status:", incident.get("status", "")),
            ("Reported At:", incident.get("reported_at", "")),
        ]

        for i, (label, value) in enumerate(details):
            tk.Label(info_frame, text=label, font=("Segoe UI", 10, "bold"),
                    bg="white").grid(row=i, column=0, sticky="w", pady=3)
            tk.Label(info_frame, text=value, font=("Segoe UI", 10),
                    bg="white", wraplength=400, justify="left").grid(row=i, column=1, sticky="w", padx=10, pady=3)

        tk.Label(info_frame, text="Description:", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=len(details), column=0, sticky="nw", pady=5)
        desc_text = tk.Text(info_frame, height=4, width=50, font=("Segoe UI", 10), wrap="word")
        desc_text.insert("1.0", incident.get("description", ""))
        desc_text.config(state="disabled")
        desc_text.grid(row=len(details), column=1, sticky="w", padx=10, pady=5)

        tk.Label(info_frame, text="Actions Taken:", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=len(details)+1, column=0, sticky="nw", pady=5)
        actions_text = tk.Text(info_frame, height=3, width=50, font=("Segoe UI", 10), wrap="word")
        actions_text.insert("1.0", incident.get("actions_taken", "None"))
        actions_text.config(state="disabled")
        actions_text.grid(row=len(details)+1, column=1, sticky="w", padx=10, pady=5)

        ttk.Button(detail_window, text="Close",
                  command=detail_window.destroy).pack(pady=15)

    def update_incident_status(self, incident_id, refresh_callback):
        """Update the status of an incident."""
        update_window = tk.Toplevel(self.root)
        update_window.title("Update Incident Status")
        update_window.geometry("400x200")
        update_window.configure(bg="white")

        tk.Label(update_window, text=f"Update {incident_id}",
                font=("Segoe UI", 14, "bold"), bg="white").pack(pady=10)

        tk.Label(update_window, text="New Status:",
                font=("Segoe UI", 10), bg="white").pack(pady=5)
        status_var = tk.StringVar(value="In Progress")
        status_combo = ttk.Combobox(update_window, textvariable=status_var,
                                    values=["Open", "In Progress", "Resolved", "Closed"],
                                    state="readonly", width=25)
        status_combo.pack(pady=5)

        def save_status():
            if not self.db:
                messagebox.showerror("Database Unavailable",
                                     "Cannot update — central database is not reachable.")
                return
            # incident_id is the legacy ref string (e.g. "INC-0007"); map
            # back to the integer primary key.
            row = next((i for i in self.incidents if i.get("id") == incident_id), None)
            if not row:
                self._refresh_caches()
                row = next((i for i in self.incidents if i.get("id") == incident_id), None)
            if not row:
                messagebox.showerror("Error", "Incident not found.")
                return
            try:
                # `row` came from list_incidents() which keeps the
                # original integer id under a fresh dict — but we
                # overwrote 'id' in _refresh_caches. Re-fetch by ref.
                conn = self.db._connection()
                pk_row = conn.execute(
                    "SELECT id FROM hs_incidents WHERE ref=?",
                    (incident_id,)).fetchone()
                conn.close()
                if not pk_row:
                    messagebox.showerror("Error", "Incident not found in DB.")
                    return
                self.db.update_incident_status(pk_row['id'], status_var.get())
            except sqlite3.Error:
                logger.exception("Failed to update incident status")
                messagebox.showerror("Save Error", "Could not update status.")
                return
            logger.info("Incident %s status -> %s by %s",
                        incident_id, status_var.get(),
                        (self.current_user or {}).get('username') or 'unknown')
            messagebox.showinfo("Success", "Status updated successfully.")
            update_window.destroy()
            refresh_callback()

        ttk.Button(update_window, text="Save",
                  style="Success.TButton",
                  command=save_status).pack(pady=15)

    # ==================== HAZARDS ====================
    def show_report_hazard(self):
        """Show hazard reporting form."""
        self.clear_content()

        tk.Label(self.content_frame, text="🔍 Report a Hazard",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 10))

        tk.Label(self.content_frame,
                text="Report potential hazards before they cause incidents.",
                font=("Segoe UI", 10, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 20))

        form = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1, padx=30, pady=20)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Hazard Category *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=0, column=0, sticky="w", pady=5)
        category = ttk.Combobox(form, values=[
            "Physical", "Chemical", "Biological", "Ergonomic",
            "Electrical", "Fire", "Environmental", "Radiation", "Other"
        ], state="readonly", font=("Segoe UI", 10), width=40)
        category.grid(row=0, column=1, pady=5, padx=10, sticky="w")
        category.set("Physical")

        tk.Label(form, text="Location *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=1, column=0, sticky="w", pady=5)
        location_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        location_entry.grid(row=1, column=1, pady=5, padx=10, sticky="w")

        tk.Label(form, text="Risk Level *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=2, column=0, sticky="w", pady=5)
        risk_level = ttk.Combobox(form, values=["Low", "Medium", "High"],
                                  state="readonly", font=("Segoe UI", 10), width=40)
        risk_level.grid(row=2, column=1, pady=5, padx=10, sticky="w")
        risk_level.set("Low")

        tk.Label(form, text="Description *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=3, column=0, sticky="nw", pady=5)
        description = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                                width=42, height=5)
        description.grid(row=3, column=1, pady=5, padx=10, sticky="w")

        tk.Label(form, text="Suggested Mitigation", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=4, column=0, sticky="nw", pady=5)
        mitigation = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                               width=42, height=4)
        mitigation.grid(row=4, column=1, pady=5, padx=10, sticky="w")

        def submit_hazard():
            if not location_entry.get() or not description.get("1.0", "end-1c").strip():
                messagebox.showwarning("Validation Error",
                                     "Please fill in all required fields.")
                return

            if not self.db:
                messagebox.showerror("Database Unavailable",
                                     "Cannot save — central database is not reachable.")
                logger.error("Hazard submit failed — DB unavailable")
                return
            u = self.current_user or {}
            try:
                new_id = self.db.add_hazard({
                    "category": category.get(),
                    "location": location_entry.get(),
                    "risk_level": risk_level.get(),
                    "description": description.get("1.0", "end-1c"),
                    "mitigation": mitigation.get("1.0", "end-1c"),
                    "reported_by": u.get('username') or u.get('user_id') or '',
                    "department": u.get('department') or '',
                })
                ref = f"HAZ-{new_id:04d}"
                conn = self.db._connection()
                conn.execute("UPDATE hs_hazards SET ref=? WHERE id=?", (ref, new_id))
                conn.commit()
                conn.close()
            except sqlite3.Error:
                logger.exception("Hazard submit failed — DB error")
                messagebox.showerror("Save Error", "Could not save the hazard.")
                return
            logger.info("Hazard submitted ref=%s risk=%s reporter=%s",
                        ref, risk_level.get(), u.get('username') or 'unknown')
            messagebox.showinfo("Success",
                              f"Hazard {ref} has been reported successfully.")
            self.show_dashboard_content()

        btn_frame = tk.Frame(form, bg="white")
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Submit Report",
                  style="Success.TButton",
                  command=submit_hazard).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=self.show_dashboard_content).pack(side="left", padx=5)

    def show_hazards_list(self):
        """Display all hazards."""
        self.clear_content()
        self._refresh_caches()

        tk.Label(self.content_frame, text="📊 Reported Hazards",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        list_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Category", "Location", "Risk Level", "Reporter", "Status", "Date")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="w")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        for hazard in self.hazards[::-1]:
            tree.insert("", "end", values=(
                hazard.get("id", ""),
                hazard.get("category", ""),
                hazard.get("location", ""),
                hazard.get("risk_level", ""),
                hazard.get("reported_by", ""),
                hazard.get("status", ""),
                hazard.get("reported_at", "")[:10]
            ))

    # ==================== TRAINING ====================
    def show_training(self, *_):
        self._refresh_caches()
        return self._render_training()

    def _render_training(self):
        """Display training modules."""
        self.clear_content()

        tk.Label(self.content_frame, text="🎓 Health & Safety Training",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        training_modules = [
            ("Fire Safety Awareness", "30 min", "Required", "Covers evacuation procedures, fire extinguisher use, and prevention."),
            ("Manual Handling", "45 min", "Required", "Safe lifting techniques and preventing musculoskeletal injuries."),
            ("Laboratory Safety", "60 min", "Faculty/Staff", "Chemical handling, PPE, and lab emergency procedures."),
            ("First Aid Basics", "90 min", "Optional", "Basic first aid skills including CPR and wound care."),
            ("Mental Health Awareness", "40 min", "Recommended", "Recognizing mental health issues and support resources."),
            ("DSE Assessment", "20 min", "Staff", "Display Screen Equipment assessment for office workers."),
            ("COSHH Training", "50 min", "Lab Users", "Control of Substances Hazardous to Health regulations."),
            ("Electrical Safety", "35 min", "Technical Staff", "Safe use of electrical equipment and PAT testing basics."),
        ]

        # Container for training cards
        canvas = tk.Canvas(self.content_frame, bg="#f0f4f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, (title, duration, required, desc) in enumerate(training_modules):
            card = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            card.pack(fill="x", pady=5, padx=5)

            header = tk.Frame(card, bg="white")
            header.pack(fill="x", padx=15, pady=10)

            tk.Label(header, text=title, font=("Segoe UI", 12, "bold"),
                    bg="white", fg="#1a365d").pack(side="left")

            badge_color = "#c53030" if required == "Required" else "#3182ce" if required == "Recommended" else "#718096"
            tk.Label(header, text=f" {required} ", font=("Segoe UI", 9),
                    bg=badge_color, fg="white").pack(side="right", padx=5)
            tk.Label(header, text=f"⏱ {duration}", font=("Segoe UI", 9),
                    bg="white", fg="#4a5568").pack(side="right", padx=5)

            tk.Label(card, text=desc, font=("Segoe UI", 10),
                    bg="white", fg="#4a5568", wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 5))

            # Check if completed
            uname = (self.current_user or {}).get('username') or ''
            completed = any(t.get("user") == uname and
                          t.get("module") == title for t in self.training_records)

            btn_frame = tk.Frame(card, bg="white")
            btn_frame.pack(anchor="w", padx=15, pady=10)

            if completed:
                tk.Label(btn_frame, text="✓ Completed", font=("Segoe UI", 10, "bold"),
                        bg="white", fg="#2f855a").pack(side="left")
            else:
                ttk.Button(btn_frame, text="Mark as Completed",
                          command=lambda t=title: self.complete_training(t)).pack(side="left")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def complete_training(self, module):
        """Mark a training module as completed."""
        if not self.db:
            messagebox.showerror("Database Unavailable",
                                 "Cannot save — central database is not reachable.")
            return
        u = self.current_user or {}
        try:
            self.db.add_training({
                "user": u.get('username') or u.get('user_id') or '',
                "module": module,
                "department": u.get('department') or '',
            })
        except sqlite3.Error:
            logger.exception("Training record save failed")
            messagebox.showerror("Save Error", "Could not save the training record.")
            return
        logger.info("Training completed module=%r user=%s", module,
                    u.get('username') or 'unknown')
        messagebox.showinfo("Success", f"Training '{module}' marked as completed!")
        self.show_training()

    # ==================== RESOURCES ====================
    def show_resources(self):
        """Show safety resources and guidelines."""
        self.clear_content()

        tk.Label(self.content_frame, text="📚 Safety Resources & Guidelines",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        resources = [
            ("🔥 Fire Safety Policy",
             "Know your nearest fire exit. In case of fire: Raise alarm, evacuate via nearest safe route, "
             "assemble at designated point, do not use lifts, do not re-enter until cleared."),
            ("🧪 Laboratory Safety Rules",
             "Always wear appropriate PPE. No eating or drinking in labs. Know the location of safety "
             "showers, eyewash stations, and fire extinguishers. Report all spills immediately."),
            ("💼 Office Ergonomics",
             "Adjust your chair so feet are flat on the floor. Screen should be at arm's length, top at "
             "eye level. Take regular breaks every 30-60 minutes. Report any discomfort."),
            ("🧠 Mental Health Support",
             "The university offers counselling services available to all students and staff. "
             "Contact the Wellbeing Centre on extension 2500 or visit the Student Services building."),
            ("🚶 Manual Handling Guidelines",
             "Assess the load before lifting. Keep back straight, bend at knees. Hold load close to body. "
             "Avoid twisting. Use mechanical aids when available."),
            ("⚡ Electrical Safety",
             "Do not overload sockets. Report damaged cables or equipment immediately. All portable "
             "electrical equipment should be PAT tested. Never use electrical equipment in wet conditions."),
        ]

        canvas = tk.Canvas(self.content_frame, bg="#f0f4f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for title, content in resources:
            card = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            card.pack(fill="x", pady=5, padx=5)

            tk.Label(card, text=title, font=("Segoe UI", 13, "bold"),
                    bg="white", fg="#1a365d").pack(anchor="w", padx=15, pady=(10, 5))
            tk.Label(card, text=content, font=("Segoe UI", 10),
                    bg="white", fg="#2d3748", wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 15))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ==================== EMERGENCY INFO ====================
    def show_emergency(self):
        """Show emergency contact information."""
        self.clear_content()

        tk.Label(self.content_frame, text="🚨 Emergency Information",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#c53030").pack(anchor="w", pady=(0, 20))

        # Emergency banner
        banner = tk.Frame(self.content_frame, bg="#c53030", height=80)
        banner.pack(fill="x", pady=10)
        banner.pack_propagate(False)

        tk.Label(banner, text="⚠️ IN CASE OF LIFE-THREATENING EMERGENCY, DIAL 999",
                font=("Segoe UI", 16, "bold"),
                bg="#c53030", fg="white").pack(pady=25)

        # Contacts grid
        contacts_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        contacts_frame.pack(fill="both", expand=True, pady=10)

        contacts = [
            ("🚓 Emergency Services", "999", "Police, Fire, Ambulance"),
            ("🛡️ Campus Security", "01234-567890", "24/7 Available"),
            ("🏥 First Aid", "ext. 2222", "On-campus first aiders"),
            ("👨‍⚕️ Occupational Health", "ext. 2300", "Mon-Fri, 9am-5pm"),
            ("🧠 Mental Health Crisis", "0800-111-2222", "24/7 Samaritans"),
            ("🔥 Fire Officer", "ext. 3000", "Campus fire safety"),
            ("☣️ H&S Department", "ext. 2500", "Health & Safety office"),
            ("🔧 Estates (Urgent)", "ext. 4000", "Building/maintenance issues"),
        ]

        for i, (title, number, note) in enumerate(contacts):
            row = i // 2
            col = i % 2

            card = tk.Frame(contacts_frame, bg="white", relief="ridge", bd=2, padx=20, pady=15)
            card.grid(row=row, column=col, sticky="ew", padx=10, pady=8)
            contacts_frame.grid_columnconfigure(col, weight=1)

            tk.Label(card, text=title, font=("Segoe UI", 12, "bold"),
                    bg="white", fg="#1a365d").pack(anchor="w")
            tk.Label(card, text=number, font=("Segoe UI", 16, "bold"),
                    bg="white", fg="#c53030").pack(anchor="w", pady=5)
            tk.Label(card, text=note, font=("Segoe UI", 9, "italic"),
                    bg="white", fg="#4a5568").pack(anchor="w")

        # Evacuation info
        evac_frame = tk.Frame(self.content_frame, bg="#fef3c7", relief="ridge", bd=2, padx=20, pady=15)
        evac_frame.pack(fill="x", pady=20)

        tk.Label(evac_frame, text="🏃 Evacuation Procedure",
                font=("Segoe UI", 12, "bold"),
                bg="#fef3c7", fg="#92400e").pack(anchor="w")
        tk.Label(evac_frame,
                text="1. On hearing alarm, leave immediately via nearest fire exit\n"
                     "2. Do not use lifts - use stairs\n"
                     "3. Do not stop to collect belongings\n"
                     "4. Proceed to designated assembly point\n"
                     "5. Report to the Fire Warden\n"
                     "6. Do not re-enter building until the all-clear is given",
                font=("Segoe UI", 10),
                bg="#fef3c7", fg="#78350f", justify="left").pack(anchor="w", pady=5)


def main():
    _remove_legacy_files()
    root = tk.Tk()
    HealthSafetyPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
