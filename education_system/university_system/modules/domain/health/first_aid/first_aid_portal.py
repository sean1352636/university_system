"""
University First Aid Portal
A comprehensive GUI application for first aid information and emergency response.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The reporter name/ID fields on the incident
form are pre-filled from the signed-in user; submitted reports are
stamped with that identity.

Persistence: incident reports live in the `first_aid_incidents` table of
the central university `student_records.db` (reached via
`infrastructure.database.db.get_connection`). The legacy in-memory list
is gone, and any stray local *.db files alongside this module are
removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime


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
        return ''
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or '')


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
class IncidentDB:
    """Persists first-aid incident reports in the central
    `student_records.db`. Creates the `first_aid_incidents` table on
    demand."""

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
        conn = self._connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS first_aid_incidents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    submitted_at    TEXT NOT NULL,
                    reporter_user   TEXT,
                    reporter_name   TEXT NOT NULL,
                    reporter_id     TEXT,
                    phone           TEXT,
                    location        TEXT,
                    incident_type   TEXT,
                    severity        TEXT,
                    description     TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add(self, report: dict) -> int:
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO first_aid_incidents
                   (submitted_at, reporter_user, reporter_name, reporter_id,
                    phone, location, incident_type, severity, description)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (report['submitted_at'], report.get('reporter_user', ''),
                 report['reporter_name'], report.get('reporter_id', ''),
                 report.get('phone', ''), report.get('location', ''),
                 report.get('incident_type', ''), report.get('severity', ''),
                 report['description']),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def fetch_all(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM first_aid_incidents ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]


def _remove_legacy_db():
    """Sweep any stray local SQLite files that earlier iterations of
    this module may have written alongside it. Data lives in the
    central `student_records.db`."""
    here = os.path.dirname(os.path.abspath(__file__))
    for fname in os.listdir(here) if os.path.isdir(here) else []:
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy first-aid DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class FirstAidPortal:
    def __init__(self, root):
        self.root = root
        self.root.title("University First Aid Portal")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f4f8")

        # Color scheme
        self.colors = {
            "primary": "#c0392b",      # Medical red
            "secondary": "#2980b9",    # Medical blue
            "accent": "#27ae60",       # Green for safety
            "bg": "#f0f4f8",
            "card": "#ffffff",
            "text": "#2c3e50",
            "warning": "#e67e22",
        }

        # Auth + persistence
        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user) or 'Guest'
        try:
            self.db = IncidentDB()
        except Exception:
            self.db = None
            logger.exception("First Aid Portal starting without DB persistence")
        logger.info("First Aid Portal starting user=%s role=%s db=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none',
                    'on' if self.db else 'off')

        # First aid data
        self.first_aid_data = self._load_first_aid_data()
        self.emergency_contacts = self._load_emergency_contacts()

        self._setup_styles()
        self._create_header()
        self._create_main_content()
        self._create_footer()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=[20, 10],
            font=("Segoe UI", 10, "bold"),
            background="#d6dde5",
            foreground=self.colors["text"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["primary"])],
            foreground=[("selected", "white")],
        )

    def _create_header(self):
        header = tk.Frame(self.root, bg=self.colors["primary"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=self.colors["primary"])
        title_frame.pack(expand=True, fill="both", padx=20)

        tk.Label(
            title_frame,
            text="⚕  UNIVERSITY FIRST AID PORTAL",
            font=("Segoe UI", 20, "bold"),
            bg=self.colors["primary"],
            fg="white",
        ).pack(side="left", pady=20)

        tk.Label(
            title_frame,
            text="Emergency Response & Health Information System",
            font=("Segoe UI", 10, "italic"),
            bg=self.colors["primary"],
            fg="#ffe5e5",
        ).pack(side="right", pady=25)

        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        tk.Label(
            title_frame,
            text=f"Signed in: {self.user_display}  ({role})",
            font=("Segoe UI", 9),
            bg=self.colors["primary"],
            fg="#ffe5e5",
        ).pack(side="right", padx=15, pady=25)

    def _create_main_content(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_home_tab()
        self._create_first_aid_tab()
        self._create_emergency_tab()
        self._create_report_tab()
        self._create_resources_tab()

    def _create_home_tab(self):
        home = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(home, text="🏠 Home")

        welcome = tk.Label(
            home,
            text="Welcome to the First Aid Portal",
            font=("Segoe UI", 22, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        )
        welcome.pack(pady=20)

        msg = tk.Label(
            home,
            text="Quick access to first aid guidance, emergency contacts, and incident reporting.",
            font=("Segoe UI", 11),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        )
        msg.pack(pady=5)

        # Emergency banner
        emergency_frame = tk.Frame(home, bg=self.colors["primary"], relief="raised", bd=2)
        emergency_frame.pack(fill="x", padx=40, pady=20)

        tk.Label(
            emergency_frame,
            text="🚨  IN CASE OF EMERGENCY  🚨",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors["primary"],
            fg="white",
        ).pack(pady=5)

        tk.Label(
            emergency_frame,
            text="Campus Security: 911  |  Health Center: (555) 123-4567",
            font=("Segoe UI", 12),
            bg=self.colors["primary"],
            fg="white",
        ).pack(pady=5)

        # Quick action cards
        cards_frame = tk.Frame(home, bg=self.colors["bg"])
        cards_frame.pack(pady=30)

        cards = [
            ("🩹", "First Aid Guides", "Step-by-step instructions", 1),
            ("📞", "Emergency Contacts", "Quick dial numbers", 2),
            ("📝", "Report Incident", "Log health incidents", 3),
            ("📚", "Resources", "Training & downloads", 4),
        ]

        for i, (icon, title, desc, tab_idx) in enumerate(cards):
            card = tk.Frame(cards_frame, bg=self.colors["card"], relief="raised", bd=1, width=200, height=150)
            card.grid(row=0, column=i, padx=15, pady=10)
            card.grid_propagate(False)

            tk.Label(card, text=icon, font=("Segoe UI", 30), bg=self.colors["card"]).pack(pady=(15, 5))
            tk.Label(card, text=title, font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack()
            tk.Label(card, text=desc, font=("Segoe UI", 9), bg=self.colors["card"], fg="#7f8c8d").pack(pady=2)

            btn = tk.Button(
                card,
                text="Open",
                font=("Segoe UI", 9, "bold"),
                bg=self.colors["secondary"],
                fg="white",
                relief="flat",
                cursor="hand2",
                command=lambda idx=tab_idx: self.notebook.select(idx),
            )
            btn.pack(pady=8)

        # Date/time
        dt_label = tk.Label(
            home,
            text=f"Today: {datetime.now().strftime('%A, %B %d, %Y')}",
            font=("Segoe UI", 10, "italic"),
            bg=self.colors["bg"],
            fg="#7f8c8d",
        )
        dt_label.pack(pady=10)

    def _create_first_aid_tab(self):
        fa_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(fa_tab, text="🩹 First Aid Guides")

        # Left panel — list of conditions
        left = tk.Frame(fa_tab, bg=self.colors["card"], width=250)
        left.pack(side="left", fill="y", padx=(10, 5), pady=10)
        left.pack_propagate(False)

        tk.Label(
            left,
            text="Select Condition",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
        ).pack(pady=10)

        # Search box
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_conditions)
        search_entry = tk.Entry(left, textvariable=self.search_var, font=("Segoe UI", 10), relief="solid", bd=1)
        search_entry.pack(fill="x", padx=10, pady=5)
        search_entry.insert(0, "")

        tk.Label(left, text="🔍 Search conditions", font=("Segoe UI", 8), bg=self.colors["card"], fg="#95a5a6").pack()

        # Listbox
        list_frame = tk.Frame(left, bg=self.colors["card"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.condition_listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 10),
            bg="white",
            fg=self.colors["text"],
            selectbackground=self.colors["primary"],
            selectforeground="white",
            relief="flat",
            yscrollcommand=scrollbar.set,
            activestyle="none",
        )
        self.condition_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.condition_listbox.yview)

        for condition in self.first_aid_data.keys():
            self.condition_listbox.insert("end", condition)

        self.condition_listbox.bind("<<ListboxSelect>>", self._show_first_aid_instructions)

        # Right panel — instructions
        right = tk.Frame(fa_tab, bg=self.colors["card"])
        right.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        self.condition_title = tk.Label(
            right,
            text="Select a condition to view instructions",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["card"],
            fg=self.colors["primary"],
        )
        self.condition_title.pack(pady=15, padx=15, anchor="w")

        self.instructions_text = scrolledtext.ScrolledText(
            right,
            font=("Segoe UI", 11),
            bg="#fafafa",
            fg=self.colors["text"],
            relief="flat",
            wrap="word",
            padx=15,
            pady=10,
        )
        self.instructions_text.pack(fill="both", expand=True, padx=15, pady=10)
        self.instructions_text.insert(
            "1.0",
            "\n\n👈 Please select a first aid condition from the list on the left.\n\n"
            "You will find step-by-step instructions for handling common emergencies.",
        )
        self.instructions_text.config(state="disabled")

    def _create_emergency_tab(self):
        em_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(em_tab, text="📞 Emergency Contacts")

        tk.Label(
            em_tab,
            text="Emergency Contact Directory",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        container = tk.Frame(em_tab, bg=self.colors["bg"])
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # Create contact cards
        for i, contact in enumerate(self.emergency_contacts):
            row = i // 2
            col = i % 2

            card = tk.Frame(container, bg=self.colors["card"], relief="raised", bd=1)
            card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            container.grid_columnconfigure(col, weight=1)

            # Color strip
            strip = tk.Frame(card, bg=contact["color"], width=8)
            strip.pack(side="left", fill="y")

            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="both", expand=True, padx=15, pady=15)

            tk.Label(
                info,
                text=f"{contact['icon']}  {contact['name']}",
                font=("Segoe UI", 13, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
            ).pack(anchor="w")

            tk.Label(
                info,
                text=contact["number"],
                font=("Segoe UI", 16, "bold"),
                bg=self.colors["card"],
                fg=contact["color"],
            ).pack(anchor="w", pady=3)

            tk.Label(
                info,
                text=contact["description"],
                font=("Segoe UI", 9),
                bg=self.colors["card"],
                fg="#7f8c8d",
                wraplength=300,
                justify="left",
            ).pack(anchor="w")

            tk.Label(
                info,
                text=f"📍 {contact['location']}",
                font=("Segoe UI", 9, "italic"),
                bg=self.colors["card"],
                fg="#7f8c8d",
            ).pack(anchor="w", pady=(5, 0))

    def _create_report_tab(self):
        rep_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(rep_tab, text="📝 Report Incident")

        tk.Label(
            rep_tab,
            text="Incident Report Form",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        form_frame = tk.Frame(rep_tab, bg=self.colors["card"], relief="raised", bd=1)
        form_frame.pack(padx=40, pady=10, fill="both", expand=True)

        # Form fields
        fields = [
            ("Reporter Name:", "name"),
            ("Student/Staff ID:", "id"),
            ("Contact Number:", "phone"),
            ("Location of Incident:", "location"),
        ]

        self.form_vars = {}
        for label, key in fields:
            row = tk.Frame(form_frame, bg=self.colors["card"])
            row.pack(fill="x", padx=30, pady=8)

            tk.Label(
                row,
                text=label,
                font=("Segoe UI", 10, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
                width=20,
                anchor="w",
            ).pack(side="left")

            var = tk.StringVar()
            self.form_vars[key] = var
            tk.Entry(row, textvariable=var, font=("Segoe UI", 10), relief="solid", bd=1, width=40).pack(
                side="left", fill="x", expand=True
            )

        # Pre-fill reporter identity from the signed-in user.
        if self.user:
            self.form_vars["name"].set(self.user_display)
            uid = (self.user.get('user_id') or self.user.get('id') or '')
            if uid:
                self.form_vars["id"].set(str(uid))
            if self.user.get('email'):
                # Phone isn't in EDU_AUTH_*; leave blank rather than guess.
                pass

        # Incident type
        row = tk.Frame(form_frame, bg=self.colors["card"])
        row.pack(fill="x", padx=30, pady=8)
        tk.Label(
            row,
            text="Incident Type:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=20,
            anchor="w",
        ).pack(side="left")

        self.form_vars["type"] = tk.StringVar(value="Minor Injury")
        types = ["Minor Injury", "Major Injury", "Illness", "Allergic Reaction", "Mental Health", "Other"]
        ttk.Combobox(row, textvariable=self.form_vars["type"], values=types, state="readonly", width=38).pack(
            side="left", fill="x", expand=True
        )

        # Severity
        row = tk.Frame(form_frame, bg=self.colors["card"])
        row.pack(fill="x", padx=30, pady=8)
        tk.Label(
            row,
            text="Severity Level:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=20,
            anchor="w",
        ).pack(side="left")

        self.form_vars["severity"] = tk.StringVar(value="Low")
        for sev in ["Low", "Medium", "High", "Critical"]:
            tk.Radiobutton(
                row,
                text=sev,
                variable=self.form_vars["severity"],
                value=sev,
                bg=self.colors["card"],
                font=("Segoe UI", 9),
            ).pack(side="left", padx=5)

        # Description
        desc_row = tk.Frame(form_frame, bg=self.colors["card"])
        desc_row.pack(fill="both", expand=True, padx=30, pady=8)
        tk.Label(
            desc_row,
            text="Description:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            anchor="w",
        ).pack(anchor="w")

        self.description_text = tk.Text(desc_row, font=("Segoe UI", 10), relief="solid", bd=1, height=5)
        self.description_text.pack(fill="both", expand=True, pady=5)

        # Buttons
        btn_row = tk.Frame(form_frame, bg=self.colors["card"])
        btn_row.pack(pady=15)

        tk.Button(
            btn_row,
            text="📤  Submit Report",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._submit_report,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row,
            text="🗑  Clear Form",
            font=("Segoe UI", 11),
            bg="#95a5a6",
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._clear_form,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row,
            text="📋  View Log",
            font=("Segoe UI", 11),
            bg=self.colors["secondary"],
            fg="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._view_incident_log,
        ).pack(side="left", padx=10)

    def _create_resources_tab(self):
        res_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(res_tab, text="📚 Resources")

        tk.Label(
            res_tab,
            text="First Aid Resources & Training",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        resources_frame = tk.Frame(res_tab, bg=self.colors["bg"])
        resources_frame.pack(padx=30, pady=10, fill="both", expand=True)

        resources = [
            ("🎓", "CPR Certification", "Sign up for CPR/AED certification courses held every semester at the University Health Center.", "Register"),
            ("📖", "First Aid Handbook", "Download the official university first aid handbook (PDF) with detailed procedures.", "Download"),
            ("🎥", "Training Videos", "Watch training videos on common emergency procedures and response techniques.", "Watch"),
            ("🗓", "Workshop Schedule", "View upcoming first aid workshops, Red Cross events, and safety seminars on campus.", "View Schedule"),
            ("🧰", "First Aid Kit Locations", "Interactive campus map showing all first aid kit and AED locations.", "Open Map"),
            ("📱", "Mobile App", "Download the University Safety App for on-the-go emergency information.", "Get App"),
        ]

        for i, (icon, title, desc, btn_text) in enumerate(resources):
            row = i // 2
            col = i % 2

            card = tk.Frame(resources_frame, bg=self.colors["card"], relief="raised", bd=1)
            card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            resources_frame.grid_columnconfigure(col, weight=1, uniform="col")

            tk.Label(card, text=icon, font=("Segoe UI", 28), bg=self.colors["card"]).pack(pady=(15, 5))
            tk.Label(
                card,
                text=title,
                font=("Segoe UI", 12, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
            ).pack()
            tk.Label(
                card,
                text=desc,
                font=("Segoe UI", 9),
                bg=self.colors["card"],
                fg="#7f8c8d",
                wraplength=350,
                justify="center",
            ).pack(padx=15, pady=5)

            tk.Button(
                card,
                text=btn_text,
                font=("Segoe UI", 9, "bold"),
                bg=self.colors["accent"],
                fg="white",
                relief="flat",
                padx=15,
                pady=5,
                cursor="hand2",
                command=lambda t=title: messagebox.showinfo("Resource", f"Opening: {t}\n\n(This would link to the actual resource in a production system.)"),
            ).pack(pady=10)

    def _create_footer(self):
        footer = tk.Frame(self.root, bg=self.colors["text"], height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Label(
            footer,
            text="© 2025 University Health & Safety Department  |  For emergencies, always call 911",
            font=("Segoe UI", 9),
            bg=self.colors["text"],
            fg="white",
        ).pack(pady=6)

    # ---------- Helper methods ----------

    def _filter_conditions(self, *args):
        search = self.search_var.get().lower()
        self.condition_listbox.delete(0, "end")
        for condition in self.first_aid_data.keys():
            if search in condition.lower():
                self.condition_listbox.insert("end", condition)

    def _show_first_aid_instructions(self, event):
        selection = self.condition_listbox.curselection()
        if not selection:
            return
        condition = self.condition_listbox.get(selection[0])
        instructions = self.first_aid_data[condition]

        self.condition_title.config(text=f"🩹  {condition}")
        self.instructions_text.config(state="normal")
        self.instructions_text.delete("1.0", "end")
        self.instructions_text.insert("1.0", instructions)
        self.instructions_text.config(state="disabled")

    def _submit_report(self):
        name = self.form_vars["name"].get().strip()
        description = self.description_text.get("1.0", "end").strip()

        if not name or not description:
            messagebox.showwarning("Incomplete Form", "Please fill in at least your name and a description.")
            logger.warning("Incident submit blocked — missing name or description (user=%s)",
                           self.user_display)
            return

        report = {
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reporter_user": self.user_display if self.user else '',
            "reporter_name": name,
            "reporter_id": self.form_vars["id"].get().strip(),
            "phone": self.form_vars["phone"].get().strip(),
            "location": self.form_vars["location"].get().strip(),
            "incident_type": self.form_vars["type"].get(),
            "severity": self.form_vars["severity"].get(),
            "description": description,
        }

        if not self.db:
            messagebox.showerror(
                "Database Unavailable",
                "Cannot save the report — the central database is not "
                "reachable. Please contact IT support.")
            logger.error("Incident submit failed — DB unavailable (user=%s)",
                         self.user_display)
            return

        try:
            new_id = self.db.add(report)
        except sqlite3.Error:
            logger.exception("Incident submit failed — DB error (user=%s)",
                             self.user_display)
            messagebox.showerror("Save Error",
                                 "Could not save the incident report.")
            return

        logger.info("Incident submitted id=%s severity=%s type=%s reporter=%s",
                    new_id, report['severity'], report['incident_type'],
                    self.user_display)

        messagebox.showinfo(
            "Report Submitted",
            f"✓ Incident report submitted successfully.\n\n"
            f"Reference: INC-{new_id:04d}\n"
            f"Severity: {report['severity']}\n\n"
            f"A first aid officer will be notified.",
        )
        self._clear_form()

    def _clear_form(self):
        for var in self.form_vars.values():
            if isinstance(var, tk.StringVar):
                var.set("")
        self.form_vars["type"].set("Minor Injury")
        self.form_vars["severity"].set("Low")
        self.description_text.delete("1.0", "end")

    def _view_incident_log(self):
        log_window = tk.Toplevel(self.root)
        log_window.title("Incident Log")
        log_window.geometry("700x500")
        log_window.configure(bg=self.colors["bg"])

        tk.Label(
            log_window,
            text="📋 Incident Log",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=10)

        log_text = scrolledtext.ScrolledText(log_window, font=("Consolas", 10), wrap="word")
        log_text.pack(fill="both", expand=True, padx=15, pady=10)

        incidents = []
        if self.db:
            try:
                incidents = self.db.fetch_all()
            except sqlite3.Error:
                logger.exception("Could not load incident log")

        if not incidents:
            log_text.insert("1.0", "No incidents reported yet.\n")
        else:
            for rep in incidents:
                log_text.insert(
                    "end",
                    f"── Incident INC-{rep['id']:04d} ──\n"
                    f"Time:        {rep['submitted_at']}\n"
                    f"Reporter:    {rep['reporter_name']} (ID: {rep['reporter_id'] or '—'})\n"
                    f"Logged by:   {rep['reporter_user'] or '—'}\n"
                    f"Phone:       {rep['phone'] or '—'}\n"
                    f"Location:    {rep['location'] or '—'}\n"
                    f"Type:        {rep['incident_type'] or '—'}\n"
                    f"Severity:    {rep['severity'] or '—'}\n"
                    f"Description: {rep['description']}\n\n",
                )
        log_text.config(state="disabled")
        logger.info("Incident log viewed by user=%s entries=%s",
                    self.user_display, len(incidents))

    # ---------- Data ----------

    def _load_first_aid_data(self):
        return {
            "Bleeding / Cuts": (
                "STEPS TO CONTROL BLEEDING:\n\n"
                "1. Wash your hands and put on disposable gloves if available.\n"
                "2. Apply firm, direct pressure to the wound with a clean cloth or sterile gauze.\n"
                "3. Keep pressure applied for at least 10–15 minutes without peeking.\n"
                "4. If blood soaks through, add more cloth on top — do NOT remove the original dressing.\n"
                "5. Elevate the injured area above heart level if possible.\n"
                "6. Once bleeding stops, clean gently with water and apply a sterile bandage.\n\n"
                "⚠ SEEK EMERGENCY CARE IF:\n"
                "• Bleeding does not stop after 15 minutes of pressure\n"
                "• The wound is deep, gaping, or has embedded debris\n"
                "• There are signs of shock (pale skin, rapid pulse, confusion)"
            ),
            "Burns": (
                "TREATMENT FOR BURNS:\n\n"
                "1. Remove the person from the source of the burn safely.\n"
                "2. Cool the burn under cool (not cold) running water for 10–20 minutes.\n"
                "3. Remove jewellery or tight clothing near the burn before swelling begins.\n"
                "4. Do NOT apply ice, butter, toothpaste, or ointments.\n"
                "5. Cover loosely with a clean, non-stick dressing or cling film.\n"
                "6. Give paracetamol for pain relief if appropriate.\n\n"
                "⚠ SEEK EMERGENCY CARE IF:\n"
                "• Burn is larger than the person's palm\n"
                "• Burn is on the face, hands, feet, genitals, or a major joint\n"
                "• Burn is from chemicals or electricity\n"
                "• Skin appears white, charred, or leathery"
            ),
            "Choking": (
                "RESPONSE TO CHOKING (adult/child over 1 year):\n\n"
                "1. Ask 'Are you choking?' — if they can cough or speak, encourage coughing.\n"
                "2. If they cannot breathe, cough, or speak:\n\n"
                "BACK BLOWS:\n"
                "   • Lean them forward and support their chest with one hand.\n"
                "   • Give up to 5 sharp blows between the shoulder blades with the heel of your hand.\n\n"
                "ABDOMINAL THRUSTS (Heimlich):\n"
                "   • Stand behind them, place a fist above the navel.\n"
                "   • Grasp with the other hand and pull sharply inward and upward.\n"
                "   • Repeat up to 5 times.\n\n"
                "3. Alternate back blows and abdominal thrusts until the object clears.\n"
                "4. If the person becomes unconscious, begin CPR and call emergency services.\n\n"
                "⚠ Always seek medical attention after abdominal thrusts, even if successful."
            ),
            "CPR (Adult)": (
                "ADULT CPR PROCEDURE:\n\n"
                "1. Check the scene for safety, then check responsiveness (tap and shout).\n"
                "2. Call 911 (or have someone call) and get an AED if available.\n"
                "3. Place the person on their back on a firm surface.\n"
                "4. Kneel beside them and place the heel of one hand on the center of the chest.\n"
                "5. Place your other hand on top, interlocking fingers.\n\n"
                "COMPRESSIONS:\n"
                "   • Push down hard and fast — at least 2 inches (5 cm) deep.\n"
                "   • Rate: 100–120 compressions per minute.\n"
                "   • Allow full chest recoil between compressions.\n\n"
                "6. After 30 compressions, give 2 rescue breaths (if trained and willing).\n"
                "7. Continue cycles of 30:2 until help arrives or the person starts breathing.\n"
                "8. Use an AED as soon as one is available — follow its voice prompts."
            ),
            "Fainting": (
                "RESPONSE TO FAINTING:\n\n"
                "IF SOMEONE FEELS FAINT:\n"
                "1. Have them sit or lie down immediately.\n"
                "2. If sitting, ask them to put their head between their knees.\n"
                "3. If lying, raise their legs 8–12 inches above heart level.\n"
                "4. Loosen any tight clothing (collars, belts).\n"
                "5. Offer water once fully alert.\n\n"
                "IF SOMEONE HAS FAINTED:\n"
                "1. Lay them flat on their back.\n"
                "2. Elevate their legs about 12 inches.\n"
                "3. Check for breathing — if absent, begin CPR and call 911.\n"
                "4. Do NOT give food or water until they are fully conscious.\n\n"
                "⚠ SEEK MEDICAL ATTENTION IF:\n"
                "• Unconsciousness lasts more than a minute\n"
                "• The person has injuries from the fall\n"
                "• There are heart or seizure symptoms"
            ),
            "Fractures / Broken Bones": (
                "MANAGING A SUSPECTED FRACTURE:\n\n"
                "1. Do NOT move the person unless they are in immediate danger.\n"
                "2. Support the injured limb in the position found.\n"
                "3. Immobilize the area with a splint if trained — include the joints above and below.\n"
                "4. Apply ice wrapped in cloth to reduce swelling (no more than 20 minutes).\n"
                "5. Watch for signs of shock and keep the person warm.\n"
                "6. For open fractures, cover the wound with a sterile dressing — do NOT push bone back in.\n\n"
                "⚠ CALL 911 IMMEDIATELY IF:\n"
                "• The injury is to the head, neck, back, pelvis, or thigh\n"
                "• The bone is visible or has broken the skin\n"
                "• The limb is deformed, blue, or numb\n"
                "• There is heavy bleeding"
            ),
            "Heat Exhaustion / Heatstroke": (
                "HEAT-RELATED ILLNESS:\n\n"
                "HEAT EXHAUSTION SIGNS:\n"
                "• Heavy sweating, weakness, cold/pale/clammy skin, nausea, dizziness.\n\n"
                "TREATMENT:\n"
                "1. Move to a cool, shaded or air-conditioned area.\n"
                "2. Loosen clothing and apply cool, wet cloths.\n"
                "3. Sip cool water slowly.\n"
                "4. Rest and monitor closely.\n\n"
                "HEATSTROKE SIGNS (MEDICAL EMERGENCY):\n"
                "• High body temperature (above 103°F / 39.4°C)\n"
                "• Hot, red, dry skin — may have stopped sweating\n"
                "• Confusion, rapid pulse, possible loss of consciousness\n\n"
                "TREATMENT:\n"
                "1. CALL 911 IMMEDIATELY.\n"
                "2. Move person to a cool place.\n"
                "3. Cool rapidly — ice packs to armpits, groin, neck; cool water spray.\n"
                "4. Do NOT give fluids if confused or unconscious."
            ),
            "Seizures": (
                "RESPONSE TO A SEIZURE:\n\n"
                "DO:\n"
                "1. Stay calm and note the start time.\n"
                "2. Ease the person to the floor if standing.\n"
                "3. Clear the area of hard or sharp objects.\n"
                "4. Place something soft under their head.\n"
                "5. Turn them onto their side once convulsions stop (recovery position).\n"
                "6. Stay with them until fully alert — reassure them.\n\n"
                "DO NOT:\n"
                "• Put anything in their mouth\n"
                "• Try to hold them down or stop their movements\n"
                "• Offer water or food until fully recovered\n\n"
                "⚠ CALL 911 IF:\n"
                "• Seizure lasts longer than 5 minutes\n"
                "• Person doesn't wake up after the seizure\n"
                "• Another seizure follows immediately\n"
                "• It's their first-ever seizure\n"
                "• They are injured, pregnant, or have diabetes"
            ),
            "Allergic Reaction / Anaphylaxis": (
                "ALLERGIC REACTIONS:\n\n"
                "MILD REACTION (itching, hives, mild swelling):\n"
                "1. Remove the allergen if known.\n"
                "2. Give an antihistamine if available and appropriate.\n"
                "3. Monitor closely for worsening symptoms.\n\n"
                "ANAPHYLAXIS SIGNS (LIFE-THREATENING):\n"
                "• Difficulty breathing or swallowing\n"
                "• Swelling of face, lips, throat, or tongue\n"
                "• Rapid pulse, dizziness, or fainting\n"
                "• Widespread hives or flushing\n\n"
                "EMERGENCY ACTION:\n"
                "1. CALL 911 IMMEDIATELY.\n"
                "2. Help the person use their epinephrine auto-injector (EpiPen):\n"
                "   • Remove safety cap and press firmly into outer thigh.\n"
                "   • Hold for 3 seconds, then rub area for 10 seconds.\n"
                "3. Help them lie down with legs raised (unless breathing is difficult).\n"
                "4. A second dose may be given after 5–15 minutes if no improvement.\n"
                "5. Be prepared to start CPR if they become unresponsive."
            ),
            "Nosebleed": (
                "STOPPING A NOSEBLEED:\n\n"
                "1. Sit the person upright and lean them slightly forward.\n"
                "2. Ask them to breathe through their mouth.\n"
                "3. Pinch the soft part of the nose (just below the bony bridge) firmly.\n"
                "4. Maintain pressure for a full 10–15 minutes without releasing to check.\n"
                "5. Apply a cold compress to the bridge of the nose.\n"
                "6. Once stopped, avoid blowing the nose or strenuous activity for several hours.\n\n"
                "⚠ SEEK MEDICAL ATTENTION IF:\n"
                "• Bleeding lasts longer than 20 minutes\n"
                "• It follows a blow to the head\n"
                "• The person is on blood thinners\n"
                "• Bleeding is very heavy or they feel faint"
            ),
            "Sprains & Strains": (
                "R.I.C.E. METHOD:\n\n"
                "REST:\n"
                "• Stop the activity immediately.\n"
                "• Avoid putting weight on the injured area.\n\n"
                "ICE:\n"
                "• Apply ice wrapped in a towel for 15–20 minutes.\n"
                "• Repeat every 2–3 hours for the first 48 hours.\n"
                "• Never apply ice directly to skin.\n\n"
                "COMPRESSION:\n"
                "• Wrap the area with an elastic bandage.\n"
                "• Snug but not so tight it cuts off circulation.\n\n"
                "ELEVATION:\n"
                "• Raise the injured area above heart level when possible.\n"
                "• Use pillows for support.\n\n"
                "⚠ SEEK MEDICAL CARE IF:\n"
                "• Unable to bear weight or use the limb\n"
                "• Severe pain, swelling, or bruising\n"
                "• Numbness or deformity\n"
                "• No improvement after 2–3 days"
            ),
            "Poisoning": (
                "SUSPECTED POISONING:\n\n"
                "1. Stay calm and remove the person from the source.\n"
                "2. Call the Poison Control Center: 1-800-222-1222\n"
                "3. Check their breathing, pulse, and level of alertness.\n"
                "4. Gather information to share with responders:\n"
                "   • What was taken/inhaled/touched\n"
                "   • How much\n"
                "   • When\n"
                "   • The person's age and weight\n\n"
                "DO NOT:\n"
                "• Induce vomiting unless told to by a professional\n"
                "• Give food, water, or milk unless instructed\n"
                "• Follow label instructions without expert advice\n\n"
                "FOR INHALED POISONS:\n"
                "• Move to fresh air immediately.\n\n"
                "FOR SKIN CONTACT:\n"
                "• Remove contaminated clothing, rinse with water for 15–20 minutes.\n\n"
                "FOR EYES:\n"
                "• Flush with lukewarm water for 15–20 minutes."
            ),
        }

    def _load_emergency_contacts(self):
        return [
            {
                "name": "Emergency Services",
                "number": "911",
                "description": "Police, fire, and ambulance — call for any life-threatening emergency.",
                "location": "24/7 nationwide",
                "icon": "🚨",
                "color": "#c0392b",
            },
            {
                "name": "Campus Security",
                "number": "(555) 123-9999",
                "description": "24-hour campus security and first response team.",
                "location": "Security Office, Main Gate",
                "icon": "🛡",
                "color": "#2c3e50",
            },
            {
                "name": "University Health Center",
                "number": "(555) 123-4567",
                "description": "Medical care for students and staff. Walk-in and appointments available.",
                "location": "Building H, Ground Floor",
                "icon": "🏥",
                "color": "#27ae60",
            },
            {
                "name": "Mental Health Hotline",
                "number": "(555) 123-7777",
                "description": "24/7 confidential counselling and mental health support for students.",
                "location": "Student Services, Building C",
                "icon": "💙",
                "color": "#2980b9",
            },
            {
                "name": "Poison Control",
                "number": "1-800-222-1222",
                "description": "Immediate advice for poisoning and overdose emergencies.",
                "location": "National 24/7 hotline",
                "icon": "☠",
                "color": "#8e44ad",
            },
            {
                "name": "Campus First Aid Officer",
                "number": "(555) 123-4580",
                "description": "On-duty certified first aid responder for minor incidents.",
                "location": "Rotating locations — see app",
                "icon": "⚕",
                "color": "#e67e22",
            },
        ]


def main():
    _remove_legacy_db()
    root = tk.Tk()
    FirstAidPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
