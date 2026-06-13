# Auto-generated module
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import database connection
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core import paths as _paths


# --- Lightweight tooltip helper (#11) ---------------------------------
class _Tooltip:
    """Minimal hover tooltip. One per widget; auto-cleans on destroy."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _e=None):
        if self.tip or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0",
                 relief=tk.SOLID, borderwidth=1, font=("Arial", 9),
                 padx=6, pady=2).pack()

    def _hide(self, _e=None):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


# --- Pinned-actions storage (#6) --------------------------------------
def _pins_path():
    return _paths.CONFIG_DIR / "overview_pins.json"


def _load_pins(username):
    try:
        with open(_pins_path(), 'r') as f:
            return list(json.load(f).get(username, []))
    except (OSError, ValueError):
        return []


def _save_pins(username, pin_keys):
    try:
        _paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(_pins_path(), 'r') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data[username] = list(pin_keys)
        with open(_pins_path(), 'w') as f:
            json.dump(data, f)
    except OSError as e:
        logging.warning(f"Could not persist overview pins: {e}")

# Import i18n for language support
from education_system.university_system.core.i18n import get_text as _

# Import GUI availability flags and classes
from education_system.university_system.modules.shared.gui.main.imports import gui_imports
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    STUDENT_ANALYTICS_GUI_AVAILABLE,
    ANALYTICS_GUI_AVAILABLE,
    CHATBOT_GUI_AVAILABLE,
    GUIStudentAnalytics,
    UniversityChatbotGUI,
)

def show_integrated_dashboard(self):
    """Show integrated dashboard with system overview and quick stats"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.login_required"))
        return

    self.clear_content()

    # Create dashboard layout
    dashboard_frame = ttk.Frame(self.content_frame)
    dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Title row — title plus a "Close extra tabs" affordance that
    # tears down anything launchers added via ``open_in_workspace``,
    # leaving only the dashboard's own tabs (My Dashboard, Overview,
    # Statistics, Activity, Health, and admin extensions).
    title_row = ttk.Frame(dashboard_frame)
    title_row.pack(fill=tk.X, pady=(0, 20))
    ttk.Label(title_row, text=_("dashboard.title"),
              font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

    def _close_extra_tabs():
        nb = getattr(self, 'workspace_notebook', None)
        tabs = getattr(self, 'workspace_tabs', None) or {}
        if nb is None or not tabs:
            return
        for title, frame in list(tabs.items()):
            try:
                nb.forget(frame)
            except Exception:
                pass
            tabs.pop(title, None)

    ttk.Button(title_row, text="Close extra tabs",
               command=_close_extra_tabs).pack(side=tk.RIGHT)

    # Create notebook for different dashboard sections.
    # ``self.workspace_notebook`` is exposed so feature launchers can
    # opt into rendering inside this notebook as tabs (see
    # ``open_in_workspace`` on UnifiedManagementGUI) — addresses the
    # "right content panel is decorative" gap from the 8.117.16 layout
    # review. The dashboard tabs below stay as the home view; any
    # opted-in launcher appends new tabs to the right of them.
    notebook = ttk.Notebook(dashboard_frame)
    notebook.pack(fill=tk.BOTH, expand=True)
    self.workspace_notebook = notebook
    # Track tabs added by ``open_in_workspace`` so re-opens raise the
    # existing tab instead of stacking duplicates. Keyed by title.
    if not hasattr(self, 'workspace_tabs') or self.workspace_tabs is None:
        self.workspace_tabs = {}
    else:
        # Wipe stale references — the previous notebook's tab ids are
        # invalid against this freshly-built notebook.
        self.workspace_tabs.clear()

    # Role-specific "My Dashboard" tab (inserted first)
    role = self.auth.current_user.get('role', '')
    try:
        from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService
        dash_service = DashboardService()
        my_dash_frame = ttk.Frame(notebook)

        if role == 'student':
            from education_system.university_system.modules.shared.gui.main.dashboard.student_dashboard import create_student_dashboard
            create_student_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
        elif role in ('instructor', 'staff'):
            from education_system.university_system.modules.shared.gui.main.dashboard.instructor_dashboard import create_instructor_dashboard
            create_instructor_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
        elif role == 'admin':
            from education_system.university_system.modules.shared.gui.main.dashboard.admin_dashboard import create_admin_dashboard
            create_admin_dashboard(my_dash_frame, self.auth, dash_service)
            notebook.add(my_dash_frame, text="My Dashboard")
    except Exception as e:
        logging.warning(f"Could not load role-specific dashboard: {e}")

    # System Overview Tab
    overview_frame = ttk.Frame(notebook)
    notebook.add(overview_frame, text=_("dashboard.tabs.overview"))
    self.create_overview_tab(overview_frame)

    # Quick Stats Tab
    stats_frame = ttk.Frame(notebook)
    notebook.add(stats_frame, text=_("dashboard.tabs.statistics"))
    self.create_stats_tab(stats_frame)

    # Recent Activity Tab
    activity_frame = ttk.Frame(notebook)
    notebook.add(activity_frame, text=_("dashboard.tabs.activity"))
    self.create_activity_tab(activity_frame)

    # System Health Tab
    health_frame = ttk.Frame(notebook)
    notebook.add(health_frame, text=_("dashboard.tabs.health"))
    self.create_health_tab(health_frame)

    # Admin-only tabs
    if role == 'admin':
        try:
            from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService as _DS
            _admin_svc = _DS()

            # Login Analytics tab (Feature 13)
            login_analytics_frame = ttk.Frame(notebook)
            notebook.add(login_analytics_frame, text="Login Analytics")
            from education_system.university_system.modules.shared.gui.main.dashboard.login_analytics_dashboard import create_login_analytics_tab
            create_login_analytics_tab(login_analytics_frame, _admin_svc)

            # Operational Dashboards tab (Feature 14)
            operations_frame = ttk.Frame(notebook)
            notebook.add(operations_frame, text="Operations")
            from education_system.university_system.modules.shared.gui.main.dashboard.operations_dashboard import create_operations_tab
            create_operations_tab(operations_frame, _admin_svc)

            # System Health (enhanced) tab (Feature 15)
            sys_health_frame = ttk.Frame(notebook)
            # Renamed in 8.117.86 from "System Health (Live)". Despite
            # the old label, this tab doesn't auto-refresh, and its
            # actual focus is DB-performance forensics (connection-pool
            # wait times, slow queries, per-table drill-down) — not
            # general health, which is what the regular "Health" tab
            # already covers.
            notebook.add(sys_health_frame, text="DB Performance")
            from education_system.university_system.modules.shared.gui.main.dashboard.system_health_dashboard import create_system_health_tab
            create_system_health_tab(sys_health_frame, _admin_svc)
        except Exception as e:
            logging.warning(f"Could not load admin dashboard extensions: {e}")

    # Select the role-specific tab if it was added
    if role in ('student', 'instructor', 'staff', 'admin'):
        try:
            notebook.select(0)
        except Exception:
            pass

    print(_("dashboard.messages.opened_successfully"))
def create_overview_tab(self, parent):
    """Create the system overview tab.

    Reworked in 8.117.78 to be a real landing page rather than a static
    welcome card. Sections, top to bottom:
      - Header: full name + role badge, last-login, live clock, DB indicator
      - Search bar (jumps to the relevant launcher)
      - Announcements strip (active rows from ``announcements`` table)
      - KPI tiles (Students / Active Courses / Logins 24h / Pending Assignments)
      - Quick actions (role-aware, pinnable via right-click, tooltipped)
      - Recent activity preview (last 5) + "See all" link
    """
    user = self.auth.current_user or {}
    username = user.get('username', _("common.user"))
    role = user.get('role', _("common.unknown"))

    # Master container with a vertical scroll so smaller screens still
    # see the activity strip at the bottom.
    canvas = tk.Canvas(parent, highlightthickness=0)
    vbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    overview_container = ttk.Frame(canvas, padding="20")
    canvas.create_window((0, 0), window=overview_container, anchor="nw")
    overview_container.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    # ---------------------- HEADER (#9, #2, #3) -----------------------
    header = ttk.Frame(overview_container)
    header.pack(fill=tk.X, pady=(0, 15))

    full_name = (
        user.get('full_name')
        or " ".join(filter(None, [user.get('first_name'), user.get('last_name')]))
        or username
    )
    ttk.Label(header, text=full_name,
              font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
    role_badge = ttk.Label(header, text=f"  {role.upper()}  ",
                           font=('Arial', 9, 'bold'),
                           background="#d0e4ff", foreground="#003366",
                           padding=4)
    role_badge.pack(side=tk.LEFT, padx=10)

    # Last-login lookup from login_attempts.
    last_login_text = "Last login: —"
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT attempt_time FROM login_attempts "
                "WHERE username = ? AND success = 1 "
                "ORDER BY id DESC LIMIT 1, 1",
                (username,),
            ).fetchone()
            if row and row['attempt_time']:
                last_login_text = f"Last login: {row['attempt_time']}"
    except Exception:
        pass
    ttk.Label(header, text=last_login_text,
              foreground="#555").pack(side=tk.LEFT, padx=15)

    # Live clock + DB indicator on the right.
    right = ttk.Frame(header)
    right.pack(side=tk.RIGHT)
    clock_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ttk.Label(right, textvariable=clock_var,
              font=('Consolas', 11)).pack(side=tk.LEFT, padx=10)
    db_dot = tk.Label(right, text="●", font=('Arial', 14), foreground="gray")
    db_dot.pack(side=tk.LEFT)
    db_label = ttk.Label(right, text="DB: checking…")
    db_label.pack(side=tk.LEFT, padx=4)

    def _tick():
        if not overview_container.winfo_exists():
            return
        clock_var.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        # Re-check DB every 30 ticks (~30s) so the dot reflects reality
        # without hammering the pool.
        _tick.counter = getattr(_tick, 'counter', 0) + 1
        if _tick.counter % 30 == 1:
            try:
                with get_connection() as conn:
                    conn.execute("SELECT 1").fetchone()
                db_dot.config(foreground="#2ca02c")
                db_label.config(text="DB: connected")
            except Exception as e:
                db_dot.config(foreground="#d62728")
                db_label.config(text=f"DB: {type(e).__name__}")
        overview_container.after(1000, _tick)

    overview_container.after(0, _tick)

    # ---------------------- SEARCH BAR (#8) ---------------------------
    search_row = ttk.Frame(overview_container)
    search_row.pack(fill=tk.X, pady=(0, 15))
    ttk.Label(search_row, text="🔎").pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
    search_entry.insert(0, "")

    def _do_search(_e=None):
        q = search_var.get().strip()
        if not q:
            return
        # Pick the most likely destination from the query shape and
        # hand off to the existing launcher; the user can then refine.
        ql = q.lower()
        try:
            if ql.startswith('s') and q[1:].isdigit():
                self.show_student_records()
            elif any(c.isalpha() for c in q) and any(c.isdigit() for c in q):
                # Looks like a course/module code (CS101).
                self.show_course_management()
            else:
                self.show_student_records()
        except Exception as e:
            messagebox.showerror(_("common.error"), str(e))

    ttk.Button(search_row, text="Go",
               command=_do_search).pack(side=tk.LEFT)
    search_entry.bind("<Return>", _do_search)

    # ---------------------- ANNOUNCEMENTS (#7) ------------------------
    ann_frame = ttk.LabelFrame(overview_container, text="Announcements",
                               padding="10")
    ann_frame.pack(fill=tk.X, pady=(0, 15))
    announcements = []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT title, content, priority FROM announcements "
                "WHERE is_active = 1 "
                "AND (start_date IS NULL OR start_date <= date('now')) "
                "AND (end_date   IS NULL OR end_date   >= date('now')) "
                "ORDER BY CASE priority "
                "  WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
                "  WHEN 'normal' THEN 2 ELSE 3 END, "
                "announcement_id DESC LIMIT 3"
            ).fetchall()
            announcements = list(rows)
    except Exception:
        pass

    if announcements:
        priority_color = {
            'urgent': '#b00020', 'high': '#cc6600',
            'normal': '#003366', 'low': '#555',
        }
        for r in announcements:
            colour = priority_color.get(
                (r['priority'] or 'normal').lower(), '#003366')
            line = ttk.Frame(ann_frame)
            line.pack(fill=tk.X, anchor='w', pady=2)
            tk.Label(line, text=f"● {r['title']}",
                     foreground=colour, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(line, text=f" — {r['content']}").pack(side=tk.LEFT)
    else:
        ttk.Label(ann_frame, text="No active announcements.",
                  foreground="#777").pack(anchor='w')

    # ---------------------- KPI TILES (#4) ----------------------------
    kpi_frame = ttk.Frame(overview_container)
    kpi_frame.pack(fill=tk.X, pady=(0, 15))
    for i in range(4):
        kpi_frame.columnconfigure(i, weight=1, uniform='kpi')

    def _query_one(sql):
        try:
            with get_connection() as conn:
                row = conn.execute(sql).fetchone()
                return row[0] if row else 0
        except Exception:
            return "—"

    kpis = [
        ("Total Students",  "SELECT COUNT(*) FROM students"),
        ("Active Courses",  "SELECT COUNT(*) FROM modules WHERE is_active = 1"),
        ("Logins (24h)",    "SELECT COUNT(*) FROM login_attempts "
                            "WHERE success = 1 "
                            "AND attempt_time >= datetime('now','-24 hours')"),
        ("Pending Assignments",
                            "SELECT COUNT(*) FROM assignments "
                            "WHERE due_date >= date('now') AND status = 'active'"),
    ]
    for col, (label, sql) in enumerate(kpis):
        tile = ttk.LabelFrame(kpi_frame, text=label, padding=10)
        tile.grid(row=0, column=col, padx=5, sticky="ew")
        value = _query_one(sql)
        value_str = f"{value:,}" if isinstance(value, int) else str(value)
        ttk.Label(tile, text=value_str,
                  font=('Arial', 22, 'bold')).pack()

    # ---------------------- QUICK ACTIONS (#1, #6, #10, #11) ----------
    # (key, label, command, tooltip, [permissions...])
    # An empty permissions list means "always show".
    actions = [
        ('student_records',
         _("dashboard.overview.buttons.student_records"),
         self.show_student_records,
         "Browse, edit and manage student records.",
         ['view_any_student', 'view_own_student']),
        ('grade_tracking',
         _("dashboard.overview.buttons.grade_tracking"),
         self.show_grade_tracking_gui,
         "View and record grades and assessment results.",
         ['view_grades', 'manage_grades']),
        ('attendance',
         _("dashboard.overview.buttons.attendance"),
         self.open_attendance_gui,
         "Mark attendance, run reports, view trends.",
         ['view_attendance', 'manage_attendance']),
        ('course_management',
         _("dashboard.overview.buttons.course_management"),
         self.show_course_management,
         "Create, edit and schedule courses and modules.",
         ['view_courses', 'manage_courses']),
        ('finance_management',
         _("dashboard.overview.buttons.finance_management"),
         self.show_finance_management,
         "Fees, invoices, scholarships and ledgers.",
         ['view_finance', 'manage_finance']),
        ('reports',
         _("dashboard.overview.buttons.reports"),
         self.show_enhanced_reporting_dashboard,
         "Open the enhanced reporting dashboard.",
         ['view_reports', 'export_data']),
    ]

    perms = set(user.get('permissions') or [])
    is_admin = role == 'admin'

    def _allowed(required):
        if not required:
            return True
        if is_admin:
            return True
        return any(p in perms for p in required)

    visible = [a for a in actions if _allowed(a[4])]

    pins = set(_load_pins(username))
    visible.sort(key=lambda a: (0 if a[0] in pins else 1, a[1]))

    qa_frame = ttk.LabelFrame(
        overview_container, text=_("dashboard.overview.quick_access"),
        padding="15")
    qa_frame.pack(fill=tk.X, pady=(0, 15))

    if not visible:
        ttk.Label(qa_frame,
                  text="No quick actions available for your role.",
                  foreground="#777").pack(anchor='w')
    else:
        cols = 3
        for i in range(cols):
            qa_frame.columnconfigure(i, weight=1)

        def _toggle_pin(key, btn):
            current = set(_load_pins(username))
            if key in current:
                current.discard(key)
            else:
                current.add(key)
            _save_pins(username, current)
            # Update label inline so the user sees the pin without a rebuild.
            label = btn.cget('text').lstrip('★ ').rstrip()
            btn.config(text=f"★ {label}" if key in current else label)

        for idx, (key, label, cmd, tip, _req) in enumerate(visible):
            display = f"★ {label}" if key in pins else label
            btn = ttk.Button(qa_frame, text=display, command=cmd,
                             style='Action.TButton')
            btn.grid(row=idx // cols, column=idx % cols,
                     padx=5, pady=5, sticky="ew")
            _Tooltip(btn,
                     f"{tip}\n(Right-click to {'unpin' if key in pins else 'pin'})")
            btn.bind("<Button-3>",
                     lambda _e, k=key, b=btn: _toggle_pin(k, b))

    # ---------------------- RECENT ACTIVITY (#5) ----------------------
    ra_frame = ttk.LabelFrame(overview_container,
                              text="Recent activity", padding="10")
    ra_frame.pack(fill=tk.X, pady=(0, 10))

    ra_cols = ('timestamp', 'username', 'action')
    ra_tree = ttk.Treeview(ra_frame, columns=ra_cols, show='headings',
                           height=5)
    ra_tree.heading('timestamp', text='Time')
    ra_tree.heading('username', text='User')
    ra_tree.heading('action', text='Action')
    ra_tree.column('timestamp', width=160)
    ra_tree.column('username', width=120)
    ra_tree.column('action', width=300)
    ra_tree.pack(fill=tk.X)

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT timestamp, username, action FROM activity_log "
                "ORDER BY id DESC LIMIT 5"
            ).fetchall()
            for r in rows:
                ra_tree.insert('', tk.END, values=(
                    r['timestamp'] or '', r['username'] or '',
                    r['action'] or ''))
    except Exception as e:
        ra_tree.insert('', tk.END,
                       values=('', '', f'Error: {e}'))

    def _see_all_activity():
        nb = getattr(self, 'workspace_notebook', None)
        if nb is None:
            return
        for tab_id in nb.tabs():
            if 'activity' in nb.tab(tab_id, 'text').lower():
                nb.select(tab_id)
                return

    see_all = ttk.Label(ra_frame, text="See all activity →",
                        foreground="#1a73e8", cursor="hand2")
    see_all.pack(anchor='e', pady=(5, 0))
    see_all.bind("<Button-1>", lambda _e: _see_all_activity())

def create_stats_tab(self, parent):
    """Create quick statistics tab.

    Replaced the original ``tk.Text`` blob with a grid of stat cards in
    8.117.87. Each card has a coloured top accent (so the eye can
    triage by domain), a big number, a sub-label, and (where relevant)
    a context line such as "last 24h" or "of N total".
    """
    container = ttk.Frame(parent, padding=20)
    container.pack(fill=tk.BOTH, expand=True)

    # Header row: title + as-of timestamp + Refresh button
    header = ttk.Frame(container)
    header.pack(fill=tk.X, pady=(0, 15))
    ttk.Label(header, text=_("dashboard.statistics.title"),
              font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
    asof_var = tk.StringVar()
    ttk.Label(header, textvariable=asof_var,
              foreground="#666").pack(side=tk.LEFT, padx=15)

    # Stats grid (3 columns × 2 rows)
    grid = ttk.Frame(container)
    grid.pack(fill=tk.BOTH, expand=True)
    for c in range(3):
        grid.columnconfigure(c, weight=1, uniform='stats')

    # Per-card state — populated by the renderer below
    cards = {}

    def _make_card(row, col, label, accent, sub=""):
        outer = tk.Frame(grid, bg=accent, bd=0)
        outer.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        # Coloured accent strip at the top
        tk.Frame(outer, bg=accent, height=4).pack(fill=tk.X)
        # Card body
        body = tk.Frame(outer, bg="#ffffff", padx=18, pady=14)
        body.pack(fill=tk.BOTH, expand=True)
        value_var = tk.StringVar(value="…")
        tk.Label(body, textvariable=value_var, bg="#ffffff",
                 fg="#1a1a1a",
                 font=('Arial', 26, 'bold')).pack(anchor='w')
        tk.Label(body, text=label, bg="#ffffff",
                 fg="#444", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(4, 0))
        sub_var = tk.StringVar(value=sub)
        tk.Label(body, textvariable=sub_var, bg="#ffffff",
                 fg="#888", font=('Arial', 9)).pack(anchor='w')
        cards[label] = {'value': value_var, 'sub': sub_var}

    # Define cards: (label, accent_colour)
    _make_card(0, 0, "Total Students",       "#1a73e8")
    _make_card(0, 1, "Active Courses",       "#0f9d58")
    _make_card(0, 2, "Pending Assignments",  "#f4b400")
    _make_card(1, 0, "Logins (24h)",         "#9334e6")
    _make_card(1, 1, "Total Users",          "#1a73e8")
    _make_card(1, 2, "Active Enrollments",   "#0f9d58")

    # Spacer so the cards stay tight at the top instead of stretching.
    grid.rowconfigure(0, weight=0)
    grid.rowconfigure(1, weight=0)
    grid.rowconfigure(2, weight=1)

    def _refresh_stats():
        try:
            with get_connection() as conn:
                def _q(sql, default=0):
                    try:
                        row = conn.execute(sql).fetchone()
                        return row[0] if row and row[0] is not None else default
                    except Exception:
                        return None  # signals "table missing / query failed"

                total_students = _q("SELECT COUNT(*) FROM students")
                active_courses = _q("SELECT COUNT(*) FROM modules WHERE is_active = 1")
                pending = _q("SELECT COUNT(*) FROM assignments "
                             "WHERE due_date >= date('now') AND status = 'active'")
                logins = _q("SELECT COUNT(*) FROM login_attempts "
                            "WHERE success = 1 AND attempt_time >= datetime('now','-24 hours')")
                total_users = _q("SELECT COUNT(*) FROM users")
                active_enrol = _q("SELECT COUNT(*) FROM student_modules "
                                  "WHERE status IN ('Enrolled', 'enrolled')")

            def _set(card_label, value, sub=""):
                if value is None:
                    cards[card_label]['value'].set("—")
                    cards[card_label]['sub'].set("unavailable")
                else:
                    cards[card_label]['value'].set(f"{value:,}")
                    cards[card_label]['sub'].set(sub)

            _set("Total Students",       total_students)
            _set("Active Courses",       active_courses,
                 sub="active modules")
            _set("Pending Assignments",  pending,
                 sub="due today or later")
            _set("Logins (24h)",         logins, sub="successful")
            _set("Total Users",          total_users)
            # If we know totals, show Active Enrollments as ratio.
            if active_enrol is not None and total_students:
                pct = (active_enrol / total_students) * 100 if total_students else 0
                _set("Active Enrollments", active_enrol,
                     sub=f"{pct:.0f}% of students")
            else:
                _set("Active Enrollments", active_enrol)

            asof_var.set(f"as of {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            asof_var.set(f"load error: {e}")

    ttk.Button(header, text="Refresh",
               command=_refresh_stats).pack(side=tk.RIGHT)
    _refresh_stats()

def create_activity_tab(self, parent):
    """Create recent activity tab with live data from activity_log table."""
    activity_container = ttk.Frame(parent, padding="20")
    activity_container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(activity_container, text=_("dashboard.activity.title"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 10))

    # Controls row
    controls = ttk.Frame(activity_container)
    controls.pack(fill=tk.X, pady=(0, 5))

    filter_var = tk.StringVar(value="All")
    ttk.Label(controls, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
    filter_combo = ttk.Combobox(controls, textvariable=filter_var, state='readonly',
                                 values=['All', 'login', 'logout', 'create', 'update', 'delete', 'view', 'export'],
                                 width=12)
    filter_combo.pack(side=tk.LEFT, padx=(0, 10))

    # Treeview for activity log
    cols = ('timestamp', 'username', 'action', 'details')
    tree_frame = ttk.Frame(activity_container)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
    tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=18,
                        yscrollcommand=tree_scroll.set)
    tree_scroll.config(command=tree.yview)

    tree.heading('timestamp', text='Timestamp')
    tree.heading('username', text='User')
    tree.heading('action', text='Action')
    tree.heading('details', text='Details')
    tree.column('timestamp', width=160)
    tree.column('username', width=100)
    tree.column('action', width=150)
    tree.column('details', width=400)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def load_activity(action_filter='All'):
        for item in tree.get_children():
            tree.delete(item)
        try:
            with get_connection() as conn:
                if action_filter == 'All':
                    rows = conn.execute(
                        "SELECT timestamp, username, action, details FROM activity_log "
                        "ORDER BY id DESC LIMIT 100"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT timestamp, username, action, details FROM activity_log "
                        "WHERE LOWER(action) LIKE ? ORDER BY id DESC LIMIT 100",
                        (f'%{action_filter.lower()}%',)
                    ).fetchall()
                for r in rows:
                    ts = r['timestamp'] if r['timestamp'] else ''
                    user = r['username'] if r['username'] else ''
                    action = r['action'] if r['action'] else ''
                    details = r['details'] if r['details'] else ''
                    tree.insert('', tk.END, values=(ts, user, action, details))
        except Exception as e:
            tree.insert('', tk.END, values=('', '', 'Error loading activity', str(e)))

    filter_combo.bind('<<ComboboxSelected>>', lambda e: load_activity(filter_var.get()))

    ttk.Button(controls, text="Refresh", command=lambda: load_activity(filter_var.get())).pack(side=tk.RIGHT)

    load_activity()

def create_health_tab(self, parent):
    """Create system health monitoring tab.

    Renders rich live metrics (DB size, tables, users 24h, logins 24h,
    failed logins, activity-log size, uptime, connection pool, recent
    errors from app.log) plus a "Quick self-test" section that runs
    four boolean checks (DB connection, auth, filesystem, GUI).

    8.117.86: previously delegated to ``health_portal_gui.create_health_tab``
    whenever the Health Portal was registered — that path only showed
    the four self-test rows and hid the rich metrics. Inverted: the
    rich metrics always render; the four self-tests live below as a
    "Quick self-test" section so the visual of green ticks isn't lost.
    """
    import os
    import tempfile
    import threading

    health_container = ttk.Frame(parent, padding="20")
    health_container.pack(fill=tk.BOTH, expand=True)
    ttk.Label(health_container, text=_("dashboard.health.title"),
              font=('Arial', 14, 'bold')).pack(pady=(0, 10))

    metrics_frame = ttk.LabelFrame(health_container, text="System Metrics", padding="10")
    metrics_frame.pack(fill=tk.X, pady=(0, 10))

    info_labels = {}

    def _add_metric(parent_f, label, row):
        ttk.Label(parent_f, text=label, width=25, anchor='w').grid(row=row, column=0, padx=5, pady=3, sticky='w')
        val = ttk.Label(parent_f, text="...", anchor='w')
        val.grid(row=row, column=1, padx=5, pady=3, sticky='w')
        info_labels[label] = val

    _add_metric(metrics_frame, "Database Size", 0)
    _add_metric(metrics_frame, "Total Tables", 1)
    _add_metric(metrics_frame, "Total Rows (est.)", 2)
    _add_metric(metrics_frame, "Active Users (24h)", 3)
    _add_metric(metrics_frame, "Login Attempts (24h)", 4)
    _add_metric(metrics_frame, "Failed Logins (24h)", 5)
    _add_metric(metrics_frame, "Activity Log Entries", 6)
    _add_metric(metrics_frame, "Application Uptime", 7)

    # Connection Pool section
    pool_frame = ttk.LabelFrame(health_container, text="Connection Pool", padding="10")
    pool_frame.pack(fill=tk.X, pady=(0, 10))

    pool_labels = {}

    def _add_pool_metric(parent_f, label, row):
        ttk.Label(parent_f, text=label, width=25, anchor='w').grid(row=row, column=0, padx=5, pady=3, sticky='w')
        val = ttk.Label(parent_f, text="...", anchor='w')
        val.grid(row=row, column=1, padx=5, pady=3, sticky='w')
        pool_labels[label] = val

    _add_pool_metric(pool_frame, "Pool Status", 0)
    _add_pool_metric(pool_frame, "Total Connections", 1)
    _add_pool_metric(pool_frame, "Active Connections", 2)
    _add_pool_metric(pool_frame, "Idle Connections", 3)
    _add_pool_metric(pool_frame, "Connection Errors", 4)

    # Error counts section
    errors_frame = ttk.LabelFrame(health_container, text="Recent Errors", padding="10")
    errors_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    error_text = tk.Text(errors_frame, wrap=tk.WORD, height=6)
    error_text.pack(fill=tk.BOTH, expand=True)
    error_text.config(state=tk.DISABLED)

    # Quick self-test section — the four boolean checks the Health
    # Portal stub used to render. Each runs in a daemon thread so a
    # slow check doesn't block the tab from appearing.
    selftest_frame = ttk.LabelFrame(health_container, text="Quick self-test", padding="10")
    selftest_frame.pack(fill=tk.X, pady=(0, 10))
    selftest_vars = {}

    def _check_database():
        try:
            with get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def _check_auth():
        return self.auth is not None and hasattr(self.auth, 'current_user')

    def _check_filesystem():
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(b"test")
            return True
        except Exception:
            return False

    def _check_gui_components():
        # We're rendering inside Tk right now, so by definition GUI
        # components are available. Kept for parity with the old
        # Health Portal stub that surfaced this row.
        return True

    selftest_checks = [
        ("Database connection", _check_database),
        ("Authentication system", _check_auth),
        ("File system access", _check_filesystem),
        ("GUI components", _check_gui_components),
    ]
    for i, (label, _fn) in enumerate(selftest_checks):
        ttk.Label(selftest_frame, text=label, width=25,
                  anchor='w').grid(row=i, column=0, padx=5, pady=3, sticky='w')
        var = tk.StringVar(value="Checking…")
        ttk.Label(selftest_frame, textvariable=var,
                  anchor='w').grid(row=i, column=1, padx=5, pady=3, sticky='w')
        selftest_vars[label] = var

    def _run_self_tests():
        for lbl, fn in selftest_checks:
            v = selftest_vars[lbl]
            v.set("Checking…")
            def _runner(label=lbl, func=fn, var=v):
                try:
                    var.set("✅ OK" if func() else "❌ FAIL")
                except Exception as e:
                    var.set(f"❌ ERROR: {str(e)[:50]}")
            threading.Thread(target=_runner, daemon=True).start()

    _start_time = datetime.now()

    def refresh_health():
        try:
            from education_system.university_system.core import paths
            db_path = str(paths.DEFAULT_DB_PATH)

            # Database size
            try:
                db_size = os.path.getsize(db_path)
                if db_size >= 1_048_576:
                    size_str = f"{db_size / 1_048_576:.1f} MB"
                else:
                    size_str = f"{db_size / 1024:.1f} KB"
                info_labels["Database Size"].config(text=size_str)
            except Exception:
                info_labels["Database Size"].config(text="Unknown")

            with get_connection() as conn:
                # Table count
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'"
                ).fetchone()
                info_labels["Total Tables"].config(text=str(row['cnt'] if row else 0))

                # Estimated total rows from sqlite_stat1
                try:
                    row = conn.execute(
                        "SELECT SUM(stat) as total FROM (SELECT CAST(stat AS INTEGER) as stat FROM sqlite_stat1)"
                    ).fetchone()
                    total = row['total'] if row and row['total'] else 0
                    info_labels["Total Rows (est.)"].config(text=f"{total:,}")
                except Exception:
                    info_labels["Total Rows (est.)"].config(text="N/A")

                # Active users (24h)
                try:
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT username) as cnt FROM activity_log "
                        "WHERE timestamp >= datetime('now', '-24 hours')"
                    ).fetchone()
                    info_labels["Active Users (24h)"].config(text=str(row['cnt'] if row else 0))
                except Exception:
                    info_labels["Active Users (24h)"].config(text="N/A")

                # Login attempts (24h)
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM login_attempts "
                        "WHERE attempt_time >= datetime('now', '-24 hours')"
                    ).fetchone()
                    info_labels["Login Attempts (24h)"].config(text=str(row['cnt'] if row else 0))
                except Exception:
                    info_labels["Login Attempts (24h)"].config(text="N/A")

                # Failed logins (24h)
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM login_attempts "
                        "WHERE success = 0 AND attempt_time >= datetime('now', '-24 hours')"
                    ).fetchone()
                    info_labels["Failed Logins (24h)"].config(text=str(row['cnt'] if row else 0))
                except Exception:
                    info_labels["Failed Logins (24h)"].config(text="N/A")

                # Activity log count
                row = conn.execute("SELECT COUNT(*) as cnt FROM activity_log").fetchone()
                info_labels["Activity Log Entries"].config(text=f"{row['cnt']:,}" if row else "0")

            # Uptime
            delta = datetime.now() - _start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            info_labels["Application Uptime"].config(text=f"{hours}h {minutes}m {seconds}s")

            # Connection pool metrics
            try:
                from education_system.university_system.infrastructure.database.pool_metrics import get_pool_metrics
                metrics = get_pool_metrics()
                if metrics:
                    pool_labels["Pool Status"].config(text="Active")
                    pool_labels["Total Connections"].config(text=str(metrics.total_connections))
                    pool_labels["Active Connections"].config(text=str(metrics.active_connections))
                    pool_labels["Idle Connections"].config(text=str(metrics.idle_connections))
                    pool_labels["Connection Errors"].config(text=str(metrics.connection_errors))
                else:
                    pool_labels["Pool Status"].config(text="Active (no collector)")
                    pool_labels["Total Connections"].config(text="N/A")
                    pool_labels["Active Connections"].config(text="N/A")
                    pool_labels["Idle Connections"].config(text="N/A")
                    pool_labels["Connection Errors"].config(text="N/A")
            except Exception:
                pool_labels["Pool Status"].config(text="Active (metrics unavailable)")
                for k in ["Total Connections", "Active Connections", "Idle Connections", "Connection Errors"]:
                    pool_labels[k].config(text="N/A")

            # Recent errors from log file
            try:
                from education_system.university_system.core import paths as _paths
                log_file = os.path.join(str(_paths.LOG_DIR), 'app.log')
                error_lines = []
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        for line in f:
                            if 'ERROR' in line:
                                error_lines.append(line.strip())
                    error_lines = error_lines[-10:]  # last 10 errors
                error_text.config(state=tk.NORMAL)
                error_text.delete('1.0', tk.END)
                if error_lines:
                    error_text.insert(tk.END, '\n'.join(error_lines))
                else:
                    error_text.insert(tk.END, 'No recent errors.')
                error_text.config(state=tk.DISABLED)
            except Exception:
                error_text.config(state=tk.NORMAL)
                error_text.delete('1.0', tk.END)
                error_text.insert(tk.END, 'Could not read log file.')
                error_text.config(state=tk.DISABLED)

            # Re-run the four self-tests so the Refresh button updates them too
            _run_self_tests()

        except Exception as e:
            logging.warning(f"Health tab refresh error: {e}")

    ttk.Button(health_container, text="Refresh", command=refresh_health).pack(anchor='e', pady=(5, 0))
    refresh_health()
def show_analytics(self):
    """Launch the standalone Student Analytics GUI from student_analytics_gui.py"""
    if not self.auth.current_user or 'view_analytics' not in self.auth.current_user.get('permissions', []):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_analytics_permission"))
        return

    try:
        if STUDENT_ANALYTICS_GUI_AVAILABLE:
            # Create a child window for the analytics GUI
            analytics_window = tk.Toplevel(self.root)
            _install_clean_close(analytics_window)
            analytics_window.transient(self.root)

            # Launch the GUI in the child window
            analytics_app = GUIStudentAnalytics(root=analytics_window, auth_manager=self.auth)
        else:
            messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_not_available"))
    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_launch_failed", error=str(e)))
def show_chatbot(self):
    """Launch the full Chatbot GUI using the existing ChatbotGUI class"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_login_required"))
        return

    if not self.auth.check_permission('access_chatbot'):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_chatbot_permission"))
        return

    try:
        # Initialize the chatbot instance if not already done
        if not gui_imports.chatbot_instance:
            if not gui_imports.initialize_chatbot_integration():
                messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_init_failed"))
                return

        # Set authentication system for chatbot
        if gui_imports.chatbot_instance and self.auth:
            gui_imports.chatbot_instance.set_auth_system(self.auth)

        # Use imported UniversityChatbotGUI if available
        if CHATBOT_GUI_AVAILABLE and UniversityChatbotGUI:
            chatbot_window = tk.Toplevel(self.root)
            _install_clean_close(chatbot_window)
            chatbot_window.title(_("dashboard.chatbot.title"))
            chatbot_window.geometry("1000x700")

            chatbot_gui = UniversityChatbotGUI(gui_imports.chatbot_instance, chatbot_window, auth_system=self.auth)
            print(_("dashboard.messages.chatbot_opened"))
        else:
            messagebox.showerror(
                _("common.error"),
                "Chatbot GUI is not available. Please ensure the chatbot module is installed."
            )

        print(_("dashboard.messages.chatbot_launched"))

    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_open_failed", error=str(e)))
        print(f"Chatbot GUI error: {e}")
def log_activity(self, message, level="info", action=None):
    """Log activity with comprehensive error handling"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f"[{timestamp}] {_('dashboard.log.gui_prefix')}: {message}"

        print(formatted_message)

        if level.lower() == "error":
            logging.error(formatted_message)
        elif level.lower() == "warning":
            logging.warning(formatted_message)
        else:
            logging.info(formatted_message)

    except Exception as e:
        print(f"{_('dashboard.log.gui_activity')}: {message}")
        logging.error(f"{_('dashboard.log.logging_error')}: {e}")
def launch_analytics_gui_standalone():
    """Launch analytics GUI as standalone window"""
    try:
        if ANALYTICS_GUI_AVAILABLE:
            analytics_app = GUIStudentAnalytics()
            if auth:
                analytics_app.auth = auth
            analytics_app.run()
        else:
            print(_("dashboard.messages.analytics_not_available_cli"))
            display_analytics_menu()
    except Exception as e:
        print(_("dashboard.errors.analytics_error", error=str(e)))
        display_analytics_menu()
