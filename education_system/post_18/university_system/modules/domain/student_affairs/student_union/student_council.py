"""University Student Council Management System.

GUI for managing council members, events, announcements and elections.
Integrates with central student_records.db, shared auth, the academic calendar
and the email template/queue system.
"""

import logging
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

try:
    from tkcalendar import DateEntry
    HAS_TKCAL = True
except ImportError:
    HAS_TKCAL = False

# NOTE: import send_email from the email package facade, NOT from
# `email_manager`. `email_manager.send_email` only appends to an
# in-process Python list (`_email_queue`) and never reaches the inbox.
# The package re-export resolves to `email_service.core.send_email`
# which inserts into `messages` / `stored_emails` / `email_log` and
# triggers SMTP delivery.
from education_system.post_18.university_system.infrastructure.email import send_email
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.shared_context import (
    get_auth,
    get_current_user,
)
from education_system.post_18.university_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = str(paths.DEFAULT_DB_PATH)


# ---------- Schema ----------------------------------------------------------

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS sc_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        name TEXT,
        email TEXT,
        department TEXT,
        position TEXT,
        joined_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sc_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        event_date TEXT,
        event_time TEXT,
        venue TEXT,
        organiser TEXT,
        description TEXT,
        calendar_event_id TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sc_announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        message TEXT,
        priority TEXT,
        posted_by TEXT,
        posted_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sc_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        name TEXT,
        position TEXT,
        platform TEXT,
        registered_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sc_votes (
        voter_id TEXT PRIMARY KEY,
        candidate_id INTEGER,
        cast_at TEXT,
        FOREIGN KEY (candidate_id) REFERENCES sc_candidates(id)
    )""",
]


def _init_schema(conn):
    for stmt in _SCHEMA:
        conn.execute(stmt)
    conn.commit()


# ---------- Main GUI --------------------------------------------------------

class StudentCouncilSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("University Student Council Management System")
        self.root.geometry("1180x740")
        self.root.configure(bg="#f0f4f8")

        # Auth + current user. Initialise the shared singleton if it
        # hasn't been already — the email infrastructure calls
        # `shared_context.get_auth()` for every send, and an uninit auth
        # logs a SECURITY error and breaks the send path.
        try:
            from education_system.post_18.university_system.infrastructure.shared_context import (
                is_auth_initialized, initialize_auth,
            )
            if not is_auth_initialized():
                initialize_auth()
        except Exception:
            logger.exception("could not initialise auth (continuing)")
        try:
            self.auth = get_auth()
        except Exception as e:
            logger.warning("Auth not initialised, running with limited access: %s", e)
            self.auth = None
        self.current_user = get_current_user() if self.auth else None
        self.is_privileged = self._check_privileged()

        # DB connection (central student_records.db)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        _init_schema(self.conn)

        # Cached lookups for dropdowns
        self.students_cache = self._load_students()
        self.buildings_cache = self._load_buildings()

        self.setup_styles()
        self.create_header()
        self.create_main_interface()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        logger.info(
            "Student Council GUI opened by user=%s role=%s privileged=%s",
            self._user_label(), self._user_role(), self.is_privileged,
        )

    # ---------- Auth helpers ----------

    def _user_role(self):
        if not self.current_user:
            return "guest"
        return self.current_user.get("role") or "unknown"

    def _user_label(self):
        if not self.current_user:
            return "anonymous"
        return (self.current_user.get("username")
                or self.current_user.get("name")
                or self.current_user.get("student_id")
                or "unknown")

    def _user_student_id(self):
        if not self.current_user:
            return ""
        return (self.current_user.get("student_id")
                or self.current_user.get("user_id")
                or "")

    def _check_privileged(self):
        role = (self.current_user or {}).get("role", "").lower()
        return role in {"admin", "staff", "superadmin"}

    def _require_privileged(self, action):
        if self.is_privileged:
            return True
        messagebox.showerror(
            "Permission Denied",
            f"Only admin or staff users can {action}.",
        )
        logger.warning(
            "Permission denied: user=%s tried to %s", self._user_label(), action,
        )
        return False

    # ---------- DB lookups ----------

    def _load_students(self):
        try:
            cur = self.conn.execute(
                "SELECT student_id, first_name, last_name, email_address, course "
                "FROM students WHERE COALESCE(status,'Active')='Active' "
                "ORDER BY last_name, first_name"
            )
            rows = cur.fetchall()
            students = []
            for r in rows:
                full_name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
                students.append({
                    "student_id": r["student_id"],
                    "name": full_name,
                    "email": r["email_address"] or "",
                    "department": r["course"] or "",
                    "label": f"{full_name} ({r['student_id']})",
                })
            return students
        except sqlite3.Error as e:
            logger.error("Failed to load students: %s", e)
            return []

    def _load_buildings(self):
        try:
            cur = self.conn.execute(
                "SELECT building_name FROM buildings "
                "WHERE COALESCE(is_active,1)=1 ORDER BY building_name"
            )
            return [r["building_name"] for r in cur.fetchall() if r["building_name"]]
        except sqlite3.Error:
            try:
                cur = self.conn.execute(
                    "SELECT building_name FROM campus_buildings ORDER BY building_name"
                )
                return [r["building_name"] for r in cur.fetchall() if r["building_name"]]
            except sqlite3.Error as e:
                logger.error("Failed to load buildings: %s", e)
                return []

    def _all_student_emails(self):
        try:
            cur = self.conn.execute(
                "SELECT email_address FROM students "
                "WHERE COALESCE(status,'Active')='Active' "
                "AND email_address IS NOT NULL AND email_address != ''"
            )
            return [r["email_address"] for r in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error("Failed to load student emails: %s", e)
            return []

    # ---------- Lifecycle ----------

    def on_close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        logger.info("Student Council GUI closed by %s", self._user_label())
        self.root.destroy()

    # ---------- Styling ----------

    def setup_styles(self):
        style = ttk.Style()
        style.configure("TNotebook", background="#f0f4f8", borderwidth=0)
        style.configure(
            "TNotebook.Tab", padding=[20, 10],
            font=("Segoe UI", 10, "bold"),
            background="#d1dce5", foreground="#1a365d",
        )
        style.map("TNotebook.Tab",
                  background=[("selected", "#2b6cb0")],
                  foreground=[("selected", "white")])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background="#2b6cb0", foreground="white")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"),
                        padding=8, background="#2b6cb0", foreground="white")
        style.map("Accent.TButton", background=[("active", "#2c5282")])
        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"),
                        padding=8, background="#c53030", foreground="white")
        style.map("Danger.TButton", background=[("active", "#9b2c2c")])

    # ---------- Header ----------

    def create_header(self):
        header = tk.Frame(self.root, bg="#1a365d", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎓  University Student Council",
                 font=("Segoe UI", 20, "bold"),
                 bg="#1a365d", fg="white").pack(side="left", padx=25, pady=15)
        tk.Label(header, text="Management System",
                 font=("Segoe UI", 11, "italic"),
                 bg="#1a365d", fg="#a0c4e2").pack(side="left", pady=25)

        # Right side: close button + user + date
        right = tk.Frame(header, bg="#1a365d")
        right.pack(side="right", padx=15, pady=15)

        ttk.Button(right, text="✕ Close", command=self.on_close).pack(
            side="right", padx=(15, 0))

        info = tk.Frame(right, bg="#1a365d")
        info.pack(side="right")
        tk.Label(info,
                 text=f"Signed in: {self._user_label()} ({self._user_role()})",
                 font=("Segoe UI", 9, "bold"),
                 bg="#1a365d", fg="#cbd5e0").pack(anchor="e")
        tk.Label(info, text=datetime.now().strftime("%A, %B %d, %Y"),
                 font=("Segoe UI", 9),
                 bg="#1a365d", fg="#cbd5e0").pack(anchor="e")

    # ---------- Tabs ----------

    def create_main_interface(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.create_dashboard_tab()
        self.create_members_tab()
        self.create_events_tab()
        self.create_announcements_tab()
        self.create_elections_tab()

    # =========================================================
    #                       DASHBOARD
    # =========================================================
    def create_dashboard_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(tab, text="📊  Dashboard")

        tk.Label(tab, text="Welcome to the Student Council Portal",
                 font=("Segoe UI", 18, "bold"),
                 bg="#f0f4f8", fg="#1a365d").pack(pady=(20, 10))

        stats_frame = tk.Frame(tab, bg="#f0f4f8")
        stats_frame.pack(pady=20)

        self.stat_cards = {}
        stats = [
            ("👥", "Members", "sc_members", "#3182ce"),
            ("📅", "Events", "sc_events", "#38a169"),
            ("📢", "Announcements", "sc_announcements", "#d69e2e"),
            ("🗳️", "Candidates", "sc_candidates", "#805ad5"),
        ]
        for i, (icon, label, table, color) in enumerate(stats):
            card = tk.Frame(stats_frame, bg="white",
                            highlightbackground=color, highlightthickness=2)
            card.grid(row=0, column=i, padx=15, pady=10, ipadx=30, ipady=20)
            tk.Label(card, text=icon, font=("Segoe UI", 28),
                     bg="white", fg=color).pack()
            count_lbl = tk.Label(card, text=str(self._table_count(table)),
                                 font=("Segoe UI", 24, "bold"),
                                 bg="white", fg="#1a365d")
            count_lbl.pack()
            tk.Label(card, text=label, font=("Segoe UI", 11),
                     bg="white", fg="#4a5568").pack()
            self.stat_cards[table] = count_lbl

        activity_frame = tk.LabelFrame(
            tab, text="  Recent Activity  ",
            font=("Segoe UI", 12, "bold"),
            bg="#f0f4f8", fg="#1a365d", padx=15, pady=15,
        )
        activity_frame.pack(fill="both", expand=True, padx=40, pady=20)
        self.activity_text = tk.Text(activity_frame, height=10,
                                     font=("Segoe UI", 10),
                                     bg="white", fg="#2d3748",
                                     relief="flat", wrap="word")
        self.activity_text.pack(fill="both", expand=True)
        self.refresh_activity()

    def _table_count(self, table):
        try:
            cur = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}")
            return cur.fetchone()["n"]
        except sqlite3.Error:
            return 0

    def refresh_activity(self):
        self.activity_text.config(state="normal")
        self.activity_text.delete("1.0", tk.END)
        lines = []
        try:
            cur = self.conn.execute(
                "SELECT title, posted_at FROM sc_announcements "
                "ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                lines.append(f"📢 Latest announcement: {row['title']} ({row['posted_at']})")

            cur = self.conn.execute(
                "SELECT name, event_date FROM sc_events "
                "ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                lines.append(f"📅 Upcoming event: {row['name']} on {row['event_date']}")

            n_members = self._table_count("sc_members")
            if n_members:
                lines.append(f"👥 Council has {n_members} active members")

            n_cand = self._table_count("sc_candidates")
            n_votes = self._table_count("sc_votes")
            if n_cand:
                lines.append(f"🗳️ Election: {n_cand} candidates, {n_votes} votes cast")
        except sqlite3.Error as e:
            logger.error("Failed to refresh activity: %s", e)

        if not lines:
            lines.append("No activity yet. Start by adding members, events, or announcements!")
        self.activity_text.insert("1.0", "\n\n".join(lines))
        self.activity_text.config(state="disabled")

    def update_stats(self):
        for table, lbl in self.stat_cards.items():
            lbl.config(text=str(self._table_count(table)))
        self.refresh_activity()

    # =========================================================
    #                        MEMBERS
    # =========================================================
    def create_members_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(tab, text="👥  Members")

        form = tk.LabelFrame(tab, text="  Add New Member  ",
                             font=("Segoe UI", 11, "bold"),
                             bg="#f0f4f8", fg="#1a365d", padx=15, pady=15)
        form.pack(fill="x", padx=20, pady=15)

        # Student selector (dropdown for admin/staff, locked to self for student)
        tk.Label(form, text="Student:", font=("Segoe UI", 10),
                 bg="#f0f4f8", fg="#2d3748").grid(row=0, column=0, sticky="e",
                                                  padx=5, pady=5)
        self.member_student_var = tk.StringVar()
        if self.is_privileged:
            labels = [s["label"] for s in self.students_cache]
            self.member_student_dropdown = ttk.Combobox(
                form, values=labels, textvariable=self.member_student_var,
                width=40, state="readonly")
            self.member_student_dropdown.grid(row=0, column=1, columnspan=3,
                                              padx=5, pady=5, sticky="w")
            self.member_student_dropdown.bind(
                "<<ComboboxSelected>>", self._on_member_student_selected)
        else:
            sid = self._user_student_id()
            match = next((s for s in self.students_cache
                          if s["student_id"] == sid), None)
            label = match["label"] if match else f"{self._user_label()} ({sid})"
            self.member_student_var.set(label)
            entry = ttk.Entry(form, textvariable=self.member_student_var,
                              width=42, state="readonly")
            entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        # Auto-filled fields (read-only)
        self._readonly_vars = {}
        labels = [("Name:", "name", 1, 0), ("Student ID:", "sid", 1, 2),
                  ("Email:", "email", 2, 0), ("Department:", "dept", 2, 2)]
        for label, key, row, col in labels:
            tk.Label(form, text=label, font=("Segoe UI", 10),
                     bg="#f0f4f8", fg="#2d3748").grid(
                row=row, column=col, sticky="e", padx=5, pady=5)
            var = tk.StringVar()
            ttk.Entry(form, textvariable=var, width=28,
                      state="readonly").grid(
                row=row, column=col + 1, padx=5, pady=5, sticky="w")
            self._readonly_vars[key] = var

        if not self.is_privileged:
            self._fill_member_fields(self.member_student_var.get())

        # Position - editable
        tk.Label(form, text="Position:", font=("Segoe UI", 10),
                 bg="#f0f4f8", fg="#2d3748").grid(
            row=3, column=0, sticky="e", padx=5, pady=5)
        self.member_position = ttk.Combobox(form, width=25, values=[
            "President", "Vice President", "Secretary", "Treasurer",
            "Public Relations Officer", "Event Coordinator", "General Member",
        ])
        self.member_position.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.member_position.set("General Member")

        btn_frame = tk.Frame(form, bg="#f0f4f8")
        btn_frame.grid(row=4, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="➕ Add Member", style="Accent.TButton",
                   command=self.add_member).pack(side="left", padx=5)
        if self.is_privileged:
            ttk.Button(btn_frame, text="🗑 Remove Selected",
                       style="Danger.TButton",
                       command=self.remove_member).pack(side="left", padx=5)

        # Table
        table_frame = tk.Frame(tab, bg="#f0f4f8")
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        cols = ("Name", "Student ID", "Department", "Position", "Email", "Joined")
        self.members_tree = ttk.Treeview(table_frame, columns=cols,
                                         show="headings", height=12)
        for c in cols:
            self.members_tree.heading(c, text=c)
            self.members_tree.column(c, width=160)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical",
                                  command=self.members_tree.yview)
        self.members_tree.configure(yscrollcommand=scrollbar.set)
        self.members_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.refresh_members()

    def _on_member_student_selected(self, _event=None):
        self._fill_member_fields(self.member_student_var.get())

    def _fill_member_fields(self, label):
        match = next((s for s in self.students_cache if s["label"] == label),
                     None)
        if not match:
            return
        self._readonly_vars["name"].set(match["name"])
        self._readonly_vars["sid"].set(match["student_id"])
        self._readonly_vars["email"].set(match["email"])
        self._readonly_vars["dept"].set(match["department"])

    def add_member(self):
        sid = self._readonly_vars["sid"].get().strip()
        name = self._readonly_vars["name"].get().strip()
        email = self._readonly_vars["email"].get().strip()
        dept = self._readonly_vars["dept"].get().strip()
        position = self.member_position.get().strip() or "General Member"

        if not sid or not name:
            messagebox.showwarning("Missing Info",
                                   "Please select a student first.")
            return

        # Students may only register themselves
        if not self.is_privileged and sid != self._user_student_id():
            messagebox.showerror("Permission Denied",
                                 "Students may only register themselves.")
            return

        joined_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            self.conn.execute(
                "INSERT INTO sc_members "
                "(student_id, name, email, department, position, joined_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, name, email, dept, position, joined_at),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Already a Member",
                                 f"{name} is already on the council.")
            return
        except sqlite3.Error as e:
            logger.error("Failed to add member %s: %s", sid, e)
            messagebox.showerror("Database Error", str(e))
            return

        logger.info("Council member added: %s (%s) as %s by %s",
                    name, sid, position, self._user_label())
        self._send_member_registration_email(sid, name, email, dept, position,
                                             joined_at)
        self.refresh_members()
        self.update_stats()
        messagebox.showinfo("Success",
                            f"Added {name} to the council as {position}.")

    def _send_member_registration_email(self, sid, name, email, dept,
                                        position, joined_at):
        if not email:
            logger.warning("No email on file for %s; skipping confirmation", sid)
            return
        subject, body = render_template(
            "student_council/member_registration",
            {
                "name": name,
                "student_id": sid,
                "department": dept,
                "position": position,
                "registered_at": joined_at,
            },
        )
        if not subject or not body:
            logger.error("Failed to render member_registration template for %s", sid)
            return
        try:
            send_email(recipient=email, subject=subject, body=body)
            logger.info("Council registration email queued for %s <%s>", name, email)
        except Exception as e:
            logger.error("Failed to send registration email to %s: %s", email, e)

    def remove_member(self):
        if not self._require_privileged("remove members"):
            return
        sel = self.members_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection",
                                   "Please select a member to remove.")
            return
        if not messagebox.askyesno("Confirm", "Remove the selected member?"):
            return
        member_id = self.members_tree.item(sel[0])["tags"][0]
        try:
            self.conn.execute("DELETE FROM sc_members WHERE id=?", (member_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to remove member id=%s: %s", member_id, e)
            messagebox.showerror("Database Error", str(e))
            return
        logger.info("Council member id=%s removed by %s",
                    member_id, self._user_label())
        self.refresh_members()
        self.update_stats()

    def refresh_members(self):
        for i in self.members_tree.get_children():
            self.members_tree.delete(i)
        try:
            cur = self.conn.execute(
                "SELECT id, name, student_id, department, position, email, "
                "joined_at FROM sc_members ORDER BY joined_at DESC")
            for r in cur.fetchall():
                self.members_tree.insert(
                    "", "end",
                    values=(r["name"], r["student_id"], r["department"],
                            r["position"], r["email"], r["joined_at"]),
                    tags=(r["id"],),
                )
        except sqlite3.Error as e:
            logger.error("Failed to refresh members: %s", e)

    # =========================================================
    #                         EVENTS
    # =========================================================
    def create_events_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(tab, text="📅  Events")

        form = tk.LabelFrame(tab, text="  Schedule New Event  ",
                             font=("Segoe UI", 11, "bold"),
                             bg="#f0f4f8", fg="#1a365d", padx=15, pady=15)
        form.pack(fill="x", padx=20, pady=15)

        tk.Label(form, text="Event Name:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.event_name = ttk.Entry(form, width=35, font=("Segoe UI", 10))
        self.event_name.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(form, text="Date:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        if HAS_TKCAL:
            self.event_date = DateEntry(form, width=15, date_pattern="yyyy-mm-dd",
                                        font=("Segoe UI", 10))
        else:
            self.event_date = ttk.Entry(form, width=18)
            self.event_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.event_date.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        tk.Label(form, text="Time:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.event_time = ttk.Entry(form, width=15, font=("Segoe UI", 10))
        self.event_time.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        tk.Label(form, text="Venue:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.event_venue = ttk.Combobox(form, values=self.buildings_cache,
                                        width=30)
        self.event_venue.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        tk.Label(form, text="Organiser:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.event_organiser = tk.StringVar(value=self._user_label())
        ttk.Entry(form, textvariable=self.event_organiser, width=35,
                  state="readonly").grid(row=2, column=1, padx=5, pady=5,
                                         sticky="w")

        tk.Label(form, text="Description:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=3, column=0, sticky="ne", padx=5, pady=5)
        self.event_desc = tk.Text(form, height=3, width=80, font=("Segoe UI", 10))
        self.event_desc.grid(row=3, column=1, columnspan=3, padx=5, pady=5,
                             sticky="w")

        btn_frame = tk.Frame(form, bg="#f0f4f8")
        btn_frame.grid(row=4, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="➕ Add Event", style="Accent.TButton",
                   command=self.add_event).pack(side="left", padx=5)
        if self.is_privileged:
            ttk.Button(btn_frame, text="🗑 Remove Selected",
                       style="Danger.TButton",
                       command=self.remove_event).pack(side="left", padx=5)

        # Table
        table_frame = tk.Frame(tab, bg="#f0f4f8")
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        cols = ("Event", "Date", "Time", "Venue", "Organiser", "Description")
        self.events_tree = ttk.Treeview(table_frame, columns=cols,
                                        show="headings", height=12)
        widths = [180, 110, 90, 160, 150, 280]
        for c, w in zip(cols, widths):
            self.events_tree.heading(c, text=c)
            self.events_tree.column(c, width=w)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical",
                                  command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)
        self.events_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.refresh_events()

    def _get_event_date(self):
        if HAS_TKCAL:
            return self.event_date.get_date().strftime("%Y-%m-%d")
        return self.event_date.get().strip()

    def add_event(self):
        if not self._require_privileged("schedule events"):
            return
        name = self.event_name.get().strip()
        date_str = self._get_event_date()
        time_str = self.event_time.get().strip()
        venue = self.event_venue.get().strip()
        organiser = self.event_organiser.get().strip()
        description = self.event_desc.get("1.0", tk.END).strip()

        if not name or not date_str:
            messagebox.showwarning("Missing Info",
                                   "Event name and date are required.")
            return

        # Push to academic calendar
        calendar_event_id = self._add_to_academic_calendar(name, date_str,
                                                           description)

        try:
            self.conn.execute(
                "INSERT INTO sc_events "
                "(name, event_date, event_time, venue, organiser, "
                "description, calendar_event_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, date_str, time_str, venue, organiser, description,
                 calendar_event_id, datetime.now().isoformat()),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to add event %s: %s", name, e)
            messagebox.showerror("Database Error", str(e))
            return

        logger.info("Council event added: %s on %s by %s (calendar_id=%s)",
                    name, date_str, self._user_label(), calendar_event_id)

        self.event_name.delete(0, tk.END)
        self.event_time.delete(0, tk.END)
        self.event_venue.set("")
        self.event_desc.delete("1.0", tk.END)
        self.refresh_events()
        self.update_stats()
        messagebox.showinfo("Success", f"Event '{name}' added!")

    def _add_to_academic_calendar(self, name, date_str, description):
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar import (
                AcademicCalendarManager,
            )
            mgr = AcademicCalendarManager(auth_manager=self.auth)
            result = mgr.add_event(
                name=f"Student Council: {name}",
                date=date_str,
                description=description or f"Student Council event on {date_str}",
                event_type="Student Council",
            )
            return result.get("event_id")
        except PermissionError:
            logger.warning("User %s lacks 'manage_schedules'; "
                           "event saved locally only", self._user_label())
            return None
        except Exception as e:
            logger.error("Academic calendar add failed: %s", e)
            return None

    def remove_event(self):
        if not self._require_privileged("remove events"):
            return
        sel = self.events_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection",
                                   "Please select an event to remove.")
            return
        if not messagebox.askyesno("Confirm", "Remove the selected event?"):
            return
        event_id = self.events_tree.item(sel[0])["tags"][0]
        try:
            self.conn.execute("DELETE FROM sc_events WHERE id=?", (event_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to remove event id=%s: %s", event_id, e)
            return
        logger.info("Council event id=%s removed by %s", event_id,
                    self._user_label())
        self.refresh_events()
        self.update_stats()

    def refresh_events(self):
        for i in self.events_tree.get_children():
            self.events_tree.delete(i)
        try:
            cur = self.conn.execute(
                "SELECT id, name, event_date, event_time, venue, organiser, "
                "description FROM sc_events ORDER BY event_date DESC")
            for r in cur.fetchall():
                desc = r["description"] or ""
                short = desc[:50] + ("..." if len(desc) > 50 else "")
                self.events_tree.insert(
                    "", "end",
                    values=(r["name"], r["event_date"], r["event_time"],
                            r["venue"], r["organiser"], short),
                    tags=(r["id"],),
                )
        except sqlite3.Error as e:
            logger.error("Failed to refresh events: %s", e)

    # =========================================================
    #                     ANNOUNCEMENTS
    # =========================================================
    def create_announcements_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(tab, text="📢  Announcements")

        form = tk.LabelFrame(tab, text="  Post Announcement  ",
                             font=("Segoe UI", 11, "bold"),
                             bg="#f0f4f8", fg="#1a365d", padx=15, pady=15)
        form.pack(fill="x", padx=20, pady=15)

        tk.Label(form, text="Title:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.ann_title = ttk.Entry(form, width=60, font=("Segoe UI", 10))
        self.ann_title.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(form, text="Priority:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.ann_priority = ttk.Combobox(form,
                                         values=["Low", "Normal", "High", "Urgent"],
                                         width=15)
        self.ann_priority.set("Normal")
        self.ann_priority.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(form, text="Message:", font=("Segoe UI", 10),
                 bg="#f0f4f8").grid(row=1, column=0, sticky="ne", padx=5, pady=5)
        self.ann_message = tk.Text(form, height=4, width=80, font=("Segoe UI", 10))
        self.ann_message.grid(row=1, column=1, columnspan=3, padx=5, pady=5,
                              sticky="w")

        self.ann_email_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form,
                       text="Email this announcement to all students",
                       variable=self.ann_email_var,
                       bg="#f0f4f8").grid(row=2, column=1, columnspan=3,
                                          sticky="w", padx=5)

        btn_frame = tk.Frame(form, bg="#f0f4f8")
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="📤 Post Announcement",
                   style="Accent.TButton",
                   command=self.post_announcement).pack(side="left", padx=5)
        if self.is_privileged:
            ttk.Button(btn_frame, text="🗑 Delete Most Recent",
                       style="Danger.TButton",
                       command=self.delete_announcement).pack(side="left", padx=5)

        display_frame = tk.LabelFrame(tab, text="  Posted Announcements  ",
                                      font=("Segoe UI", 11, "bold"),
                                      bg="#f0f4f8", fg="#1a365d")
        display_frame.pack(fill="both", expand=True, padx=20, pady=10)
        canvas = tk.Canvas(display_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(display_frame, orient="vertical",
                                  command=canvas.yview)
        self.ann_container = tk.Frame(canvas, bg="white")
        self.ann_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.ann_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.refresh_announcements()

    def post_announcement(self):
        if not self._require_privileged("post announcements"):
            return
        title = self.ann_title.get().strip()
        message = self.ann_message.get("1.0", tk.END).strip()
        priority = self.ann_priority.get() or "Normal"
        if not title or not message:
            messagebox.showwarning("Missing Info",
                                   "Title and message are required.")
            return

        posted_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            self.conn.execute(
                "INSERT INTO sc_announcements "
                "(title, message, priority, posted_by, posted_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, message, priority, self._user_label(), posted_at),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to post announcement %s: %s", title, e)
            messagebox.showerror("Database Error", str(e))
            return

        logger.info("Council announcement posted: %s [%s] by %s",
                    title, priority, self._user_label())

        sent = 0
        if self.ann_email_var.get():
            sent = self._email_announcement(title, message, priority)

        self.ann_title.delete(0, tk.END)
        self.ann_message.delete("1.0", tk.END)
        self.refresh_announcements()
        self.update_stats()
        suffix = f" Emailed to {sent} students." if sent else ""
        messagebox.showinfo("Posted", f"Announcement published!{suffix}")

    def _email_announcement(self, title, message, priority):
        recipients = self._all_student_emails()
        subject = f"[Student Council {priority}] {title}"
        body = (f"{message}\n\n"
                f"-- Student Council\nPosted: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        sent = 0
        for addr in recipients:
            try:
                send_email(recipient=addr, subject=subject, body=body)
                sent += 1
            except Exception as e:
                logger.error("Failed to email announcement to %s: %s", addr, e)
        logger.info("Announcement '%s' emailed to %d/%d students",
                    title, sent, len(recipients))
        return sent

    def delete_announcement(self):
        if not self._require_privileged("delete announcements"):
            return
        cur = self.conn.execute(
            "SELECT id FROM sc_announcements ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return
        if not messagebox.askyesno("Confirm",
                                   "Delete the most recent announcement?"):
            return
        self.conn.execute("DELETE FROM sc_announcements WHERE id=?", (row["id"],))
        self.conn.commit()
        logger.info("Council announcement id=%s deleted by %s",
                    row["id"], self._user_label())
        self.refresh_announcements()
        self.update_stats()

    def refresh_announcements(self):
        for w in self.ann_container.winfo_children():
            w.destroy()
        priority_colors = {"Low": "#48bb78", "Normal": "#3182ce",
                           "High": "#dd6b20", "Urgent": "#c53030"}
        try:
            cur = self.conn.execute(
                "SELECT title, message, priority, posted_at "
                "FROM sc_announcements ORDER BY id DESC")
            for ann in cur.fetchall():
                color = priority_colors.get(ann["priority"], "#3182ce")
                card = tk.Frame(self.ann_container, bg="white",
                                highlightbackground=color, highlightthickness=2)
                card.pack(fill="x", padx=10, pady=6)
                header = tk.Frame(card, bg=color)
                header.pack(fill="x")
                tk.Label(header, text=f"  {ann['title']}",
                         font=("Segoe UI", 11, "bold"),
                         bg=color, fg="white", anchor="w").pack(
                    side="left", fill="x", expand=True, pady=5)
                tk.Label(header,
                         text=f"{ann['priority']}  •  {ann['posted_at']}  ",
                         font=("Segoe UI", 9),
                         bg=color, fg="white").pack(side="right", pady=5)
                tk.Label(card, text=ann["message"], font=("Segoe UI", 10),
                         bg="white", fg="#2d3748", wraplength=950,
                         justify="left", anchor="w").pack(fill="x",
                                                          padx=10, pady=8)
        except sqlite3.Error as e:
            logger.error("Failed to refresh announcements: %s", e)

    # =========================================================
    #                       ELECTIONS
    # =========================================================
    def create_elections_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(tab, text="🗳️  Elections")

        left = tk.Frame(tab, bg="#f0f4f8")
        left.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        right = tk.Frame(tab, bg="#f0f4f8")
        right.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        # Register candidate
        cand_form = tk.LabelFrame(left, text="  Register Candidate  ",
                                  font=("Segoe UI", 11, "bold"),
                                  bg="#f0f4f8", fg="#1a365d", padx=15, pady=15)
        cand_form.pack(fill="x")

        tk.Label(cand_form, text="Student:", bg="#f0f4f8",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e",
                                             padx=5, pady=5)
        self.cand_student_var = tk.StringVar()
        labels = [s["label"] for s in self.students_cache]
        self.cand_student = ttk.Combobox(cand_form,
                                         values=labels,
                                         textvariable=self.cand_student_var,
                                         width=35, state="readonly")
        self.cand_student.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(cand_form, text="Running For:", bg="#f0f4f8",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e",
                                             padx=5, pady=5)
        self.cand_pos = ttk.Combobox(cand_form, values=[
            "President", "Vice President", "Secretary", "Treasurer",
        ], width=33)
        self.cand_pos.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(cand_form, text="Platform/Slogan:", bg="#f0f4f8",
                 font=("Segoe UI", 10)).grid(row=2, column=0, sticky="ne",
                                             padx=5, pady=5)
        self.cand_platform = tk.Text(cand_form, height=3, width=37,
                                     font=("Segoe UI", 10))
        self.cand_platform.grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(cand_form, text="📝 Register",
                   style="Accent.TButton",
                   command=self.register_candidate).grid(row=3, column=0,
                                                         columnspan=2, pady=10)

        # Voting
        vote_form = tk.LabelFrame(left, text="  Cast Your Vote  ",
                                  font=("Segoe UI", 11, "bold"),
                                  bg="#f0f4f8", fg="#1a365d", padx=15, pady=15)
        vote_form.pack(fill="x", pady=15)

        tk.Label(vote_form, text="Your Student ID:", bg="#f0f4f8",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e",
                                             padx=5, pady=5)
        self.voter_id_var = tk.StringVar(value=self._user_student_id())
        ttk.Entry(vote_form, textvariable=self.voter_id_var, width=30,
                  state="readonly", font=("Segoe UI", 10)).grid(
            row=0, column=1, padx=5, pady=5)

        tk.Label(vote_form, text="Vote For:", bg="#f0f4f8",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e",
                                             padx=5, pady=5)
        self.vote_choice = ttk.Combobox(vote_form, width=28, state="readonly")
        self.vote_choice.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(vote_form, text="🗳 Submit Vote",
                   style="Accent.TButton",
                   command=self.cast_vote).grid(row=2, column=0,
                                                columnspan=2, pady=10)

        if self.is_privileged:
            ttk.Button(vote_form, text="🔄 Reset Election",
                       style="Danger.TButton",
                       command=self.reset_election).grid(
                row=3, column=0, columnspan=2, pady=5)

        # Results
        results_frame = tk.LabelFrame(right, text="  Live Election Results  ",
                                      font=("Segoe UI", 11, "bold"),
                                      bg="#f0f4f8", fg="#1a365d",
                                      padx=15, pady=15)
        results_frame.pack(fill="both", expand=True)
        self.results_canvas = tk.Canvas(results_frame, bg="white",
                                        highlightthickness=0)
        self.results_canvas.pack(fill="both", expand=True)

        self.refresh_candidates_dropdown()
        self.refresh_results()

    def register_candidate(self):
        if not self._require_privileged("register candidates"):
            return
        label = self.cand_student_var.get().strip()
        match = next((s for s in self.students_cache if s["label"] == label),
                     None)
        position = self.cand_pos.get().strip()
        platform = self.cand_platform.get("1.0", tk.END).strip()
        if not match or not position:
            messagebox.showwarning("Missing Info",
                                   "Select a student and a position.")
            return
        try:
            self.conn.execute(
                "INSERT INTO sc_candidates "
                "(student_id, name, position, platform, registered_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (match["student_id"], match["name"], position, platform,
                 datetime.now().isoformat()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Already Registered",
                                 f"{match['name']} is already a candidate.")
            return
        except sqlite3.Error as e:
            logger.error("Failed to register candidate %s: %s",
                         match["student_id"], e)
            messagebox.showerror("Database Error", str(e))
            return

        logger.info("Candidate registered: %s for %s by %s",
                    match["name"], position, self._user_label())
        self.cand_student_var.set("")
        self.cand_pos.set("")
        self.cand_platform.delete("1.0", tk.END)
        self.refresh_candidates_dropdown()
        self.refresh_results()
        self.update_stats()
        messagebox.showinfo(
            "Registered",
            f"{match['name']} is now a candidate for {position}!")

    def refresh_candidates_dropdown(self):
        try:
            cur = self.conn.execute(
                "SELECT id, name, position FROM sc_candidates ORDER BY position, name")
            self._candidates = [(r["id"], r["name"], r["position"])
                                for r in cur.fetchall()]
        except sqlite3.Error:
            self._candidates = []
        self.vote_choice["values"] = [f"{n} ({p})"
                                      for _, n, p in self._candidates]

    def cast_vote(self):
        vid = self.voter_id_var.get().strip()
        choice = self.vote_choice.get().strip()
        if not vid:
            messagebox.showerror("Not Logged In",
                                 "You must be logged in as a student to vote.")
            return
        if not choice:
            messagebox.showwarning("Missing Info", "Please select a candidate.")
            return
        # Resolve candidate
        cand_id = None
        for cid, name, pos in self._candidates:
            if f"{name} ({pos})" == choice:
                cand_id = cid
                break
        if cand_id is None:
            messagebox.showerror("Invalid", "Candidate not found.")
            return
        try:
            self.conn.execute(
                "INSERT INTO sc_votes (voter_id, candidate_id, cast_at) "
                "VALUES (?, ?, ?)",
                (vid, cand_id, datetime.now().isoformat()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Already Voted",
                                 "You have already cast a vote.")
            return
        except sqlite3.Error as e:
            logger.error("Failed to cast vote for %s: %s", vid, e)
            return

        logger.info("Vote cast by %s for candidate_id=%s", vid, cand_id)
        self.vote_choice.set("")
        self.refresh_results()
        messagebox.showinfo("Vote Cast", "Thank you for voting! 🗳️")

    def reset_election(self):
        if not self._require_privileged("reset elections"):
            return
        if not messagebox.askyesno(
                "Confirm Reset",
                "This will remove all candidates and votes. Continue?"):
            return
        try:
            self.conn.execute("DELETE FROM sc_votes")
            self.conn.execute("DELETE FROM sc_candidates")
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to reset election: %s", e)
            return
        logger.warning("Election reset by %s", self._user_label())
        self.refresh_candidates_dropdown()
        self.refresh_results()
        self.update_stats()

    def refresh_results(self):
        self.results_canvas.delete("all")
        try:
            cur = self.conn.execute(
                "SELECT c.id, c.name, c.position, "
                "       COALESCE(COUNT(v.voter_id), 0) AS votes "
                "FROM sc_candidates c "
                "LEFT JOIN sc_votes v ON v.candidate_id = c.id "
                "GROUP BY c.id ORDER BY votes DESC")
            rows = cur.fetchall()
        except sqlite3.Error as e:
            logger.error("Failed to load results: %s", e)
            rows = []

        if not rows:
            self.results_canvas.create_text(
                200, 100, text="No candidates registered yet.",
                font=("Segoe UI", 11, "italic"), fill="#718096")
            return

        total = sum(r["votes"] for r in rows) or 1
        colors = ["#3182ce", "#38a169", "#d69e2e", "#805ad5",
                  "#e53e3e", "#319795", "#dd6b20"]

        y = 20
        for i, r in enumerate(rows):
            color = colors[i % len(colors)]
            votes = r["votes"]
            pct = (votes / total) * 100
            label = f"{r['name']} ({r['position']})"
            self.results_canvas.create_text(
                15, y, text=label, anchor="nw",
                font=("Segoe UI", 10, "bold"), fill="#1a365d")
            self.results_canvas.create_text(
                450, y,
                text=f"{votes} vote{'s' if votes != 1 else ''} ({pct:.1f}%)",
                anchor="ne", font=("Segoe UI", 10), fill="#2d3748")
            bar_y = y + 22
            self.results_canvas.create_rectangle(
                15, bar_y, 450, bar_y + 18, fill="#edf2f7", outline="")
            bar_width = max(2, (votes / total) * 435) if total > 0 else 2
            self.results_canvas.create_rectangle(
                15, bar_y, 15 + bar_width, bar_y + 18, fill=color, outline="")
            y += 60

        self.results_canvas.create_text(
            15, y + 10,
            text=f"Total votes cast: {sum(r['votes'] for r in rows)}",
            anchor="nw", font=("Segoe UI", 10, "italic"), fill="#4a5568")


def main():
    root = tk.Tk()
    StudentCouncilSystem(root)
    root.mainloop()


if __name__ == "__main__":
    main()
