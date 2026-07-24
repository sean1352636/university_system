"""Super Admin Dashboard for the Education System.

A comprehensive top-level tkinter window that provides superadmins with
a unified management console across all 5 education systems (Nursery,
Primary, Secondary, College, University).
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_COLORS = {
    "university": "#2980b9",
    "sixth_form": "#27ae60",
    "secondary": "#8e44ad",
    "primary": "#e67e22",
    "nursery": "#16a085",
}

SYSTEM_LABELS = {
    "nursery": "Nursery",
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "university": "University",
}

SYSTEM_ORDER = ["nursery", "primary", "secondary", "sixth_form", "university"]

# ---------------------------------------------------------------------------
# i18n helper (Feature 12)
# ---------------------------------------------------------------------------

_TRANSLATIONS = {}  # populated by load_translations()


def load_translations(locale="en"):
    """Load translation strings from shared locale JSON if available.

    Falls back to empty dict so _t() returns the English default key.
    """
    global _TRANSLATIONS
    locales_dir = Path(__file__).resolve().parent.parent / "data" / "locales" / locale
    json_path = locales_dir / "superadmin_dashboard.json"
    if json_path.exists():
        try:
            import json
            with open(json_path, encoding="utf-8") as f:
                _TRANSLATIONS = json.load(f)
        except Exception:
            _TRANSLATIONS = {}
    else:
        _TRANSLATIONS = {}


def _t(key, default=None):
    """Return translated string for *key*, falling back to *default* or the key itself."""
    return _TRANSLATIONS.get(key, default or key)


SIDEBAR_BG = "#2c3e50"
SIDEBAR_BTN = "#34495e"
SIDEBAR_BTN_ACTIVE = "#1abc9c"
HEADER_BG = "#2c3e50"
CONTENT_BG = "#ecf0f1"
CARD_BG = "#ffffff"
TEXT_DARK = "#2c3e50"
TEXT_LIGHT = "#ffffff"
TEXT_MUTED = "#7f8c8d"

# Severity styling for the "Needs Attention" panel
ALERT_COLORS = {
    "critical": "#e74c3c",
    "warning": "#f39c12",
    "info": "#3498db",
}
ALERT_OK = "#2ecc71"


def _fmt_backup_age(days):
    """Human label for a last-backup age in whole days (None = never)."""
    if days is None:
        return "never"
    if days == 0:
        return "today"
    return f"{days} day" if days == 1 else f"{days} days"


# Comparison table columns: (id, heading, width, anchor, sort_key, format)
# sort_key maps None backups to a large sentinel so "never" sorts as worst.
COMPARISON_COLUMNS = [
    ("label", "System", 150, "w",
     lambda r: r["label"], lambda r: r["label"]),
    ("status", "Status", 80, "w",
     lambda r: r["status"], lambda r: r["status"].upper()),
    ("students", "Students", 80, "e",
     lambda r: r["student_count"], lambda r: str(r["student_count"])),
    ("staff", "Staff", 70, "e",
     lambda r: r["staff_count"], lambda r: str(r["staff_count"])),
    ("users", "Users", 70, "e",
     lambda r: r["user_count"], lambda r: str(r["user_count"])),
    ("db", "DB (MB)", 80, "e",
     lambda r: r["db_size_mb"], lambda r: f"{r['db_size_mb']:.1f}"),
    ("backup", "Last Backup", 100, "e",
     lambda r: r["last_backup_days"] if r["last_backup_days"] is not None else 10 ** 9,
     lambda r: _fmt_backup_age(r["last_backup_days"])),
    ("issues", "Issues", 60, "e",
     lambda r: r["open_issues"], lambda r: str(r["open_issues"])),
]


# ---------------------------------------------------------------------------
# SuperAdminDashboard
# ---------------------------------------------------------------------------

class SuperAdminDashboard(tk.Tk):
    """Standalone top-level window for superadmin management."""

    def __init__(self, user_info, auth, auth_db_path=None):
        super().__init__()

        # Public attributes read by run.py after the window closes
        self.user_info = user_info
        self.auth = auth
        self.launch_system = None
        self.launch_role = None
        self.logged_out = False
        self.switch_to_cli = False
        self.shutdown = False

        self._auth_db_path = auth_db_path
        self._current_section = None
        self._sidebar_buttons = {}
        self._content_frame = None

        # Cached service instances (lazy)
        self._admin_service = None
        self._analytics_service = None
        self._notification_service = None
        self._journey_service = None

        # Auto-refresh
        self._refresh_timer_id = None
        self._refresh_interval_ms = 60_000  # 60 seconds

        # Window setup
        self.title("Education System \u2014 Super Admin Dashboard")
        self.geometry("1200x800")
        self.minsize(1000, 600)
        self.configure(bg=CONTENT_BG)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._show_section("dashboard")
        self._start_auto_refresh()

    # ------------------------------------------------------------------
    # Service accessors (lazy imports)
    # ------------------------------------------------------------------

    def _get_admin_service(self):
        if self._admin_service is None:
            try:
                from education_system.shared.admin_portal.admin_service import AdminService
                self._admin_service = AdminService(
                    auth_db=self._auth_db_path
                )
            except Exception:
                return None
        return self._admin_service

    def _get_analytics_service(self):
        if self._analytics_service is None:
            try:
                from education_system.shared.analytics.analytics_service import AnalyticsService
                self._analytics_service = AnalyticsService()
            except Exception:
                return None
        return self._analytics_service

    def _get_notification_service(self):
        if self._notification_service is None:
            try:
                from education_system.shared.notifications.service import (
                    CrossSystemNotificationService,
                )
                self._notification_service = CrossSystemNotificationService(
                    db_path=self._auth_db_path
                )
            except Exception:
                return None
        return self._notification_service

    def _get_journey_service(self):
        if self._journey_service is None:
            try:
                from education_system.shared.cross_system.journey_service import JourneyService
                self._journey_service = JourneyService()
            except Exception:
                return None
        return self._journey_service

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=HEADER_BG, height=56)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=_t("header.title", "Education System \u2014 Super Admin Dashboard"),
            font=("Segoe UI", 16, "bold"),
            bg=HEADER_BG,
            fg=TEXT_LIGHT,
        ).pack(side=tk.LEFT, padx=20)

        # Right side of header: user info + logout
        right_header = tk.Frame(header, bg=HEADER_BG)
        right_header.pack(side=tk.RIGHT, padx=20)

        display_name = self.user_info.get("display_name") or self.user_info.get("username", "Admin")
        tk.Label(
            right_header,
            text=f"Logged in as: {display_name}",
            font=("Segoe UI", 10),
            bg=HEADER_BG,
            fg="#bdc3c7",
        ).pack(side=tk.LEFT, padx=(0, 15))

        # About button
        about_btn = tk.Button(
            right_header,
            text="About",
            font=("Segoe UI", 9),
            bg=SIDEBAR_BTN,
            fg=TEXT_LIGHT,
            activebackground=SIDEBAR_BTN_ACTIVE,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._show_about,
        )
        about_btn.pack(side=tk.LEFT, padx=(0, 8))

        switch_cli_btn = tk.Button(
            right_header,
            text="Switch to CLI",
            font=("Segoe UI", 10),
            bg="#34495e",
            fg=TEXT_LIGHT,
            activebackground="#2c3e50",
            activeforeground=TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._on_switch_to_cli,
        )
        switch_cli_btn.pack(side=tk.LEFT, padx=(0, 8))

        logout_btn = tk.Button(
            right_header,
            text="Logout",
            font=("Segoe UI", 10),
            bg="#e74c3c",
            fg=TEXT_LIGHT,
            activebackground="#c0392b",
            activeforeground=TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=2,
            command=self._on_logout,
        )
        logout_btn.pack(side=tk.LEFT, padx=(0, 8))

        shutdown_btn = tk.Button(
            right_header,
            text="Shutdown",
            font=("Segoe UI", 10),
            bg="#7f1d1d",
            fg=TEXT_LIGHT,
            activebackground="#5c1414",
            activeforeground=TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=2,
            command=self._on_shutdown,
        )
        shutdown_btn.pack(side=tk.LEFT)

        # Body container
        body = tk.Frame(self, bg=CONTENT_BG)
        body.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=SIDEBAR_BG, width=210)
        sidebar.pack(fill=tk.Y, side=tk.LEFT)
        sidebar.pack_propagate(False)

        # Navigation header (fixed at top)
        tk.Label(
            sidebar,
            text=_t("sidebar.navigation", "NAVIGATION"),
            font=("Segoe UI", 9, "bold"),
            bg=SIDEBAR_BG,
            fg="#7f8c8d",
        ).pack(pady=(18, 8), padx=15, anchor=tk.W)

        # Version label at bottom (pack first so it stays at bottom)
        tk.Label(
            sidebar,
            text="v8.1.0",
            font=("Segoe UI", 8),
            bg=SIDEBAR_BG,
            fg="#7f8c8d",
        ).pack(side=tk.BOTTOM, pady=10)

        # Scrollable nav area between header and version label
        nav_canvas = tk.Canvas(sidebar, bg=SIDEBAR_BG, highlightthickness=0, width=194)
        nav_scrollbar = ttk.Scrollbar(sidebar, orient=tk.VERTICAL, command=nav_canvas.yview)
        nav_inner = tk.Frame(nav_canvas, bg=SIDEBAR_BG)

        nav_inner.bind(
            "<Configure>",
            lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all")),
        )
        nav_canvas.create_window((0, 0), window=nav_inner, anchor="nw", width=194)
        nav_canvas.configure(yscrollcommand=nav_scrollbar.set)

        # Mouse wheel scrolling on the sidebar
        def _on_sidebar_mousewheel(event):
            nav_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_sidebar_button4(event):
            nav_canvas.yview_scroll(-1, "units")

        def _on_sidebar_button5(event):
            nav_canvas.yview_scroll(1, "units")

        for widget in (nav_canvas, nav_inner):
            widget.bind("<MouseWheel>", _on_sidebar_mousewheel)
            widget.bind("<Button-4>", _on_sidebar_button4)
            widget.bind("<Button-5>", _on_sidebar_button5)

        nav_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sections = [
            ("dashboard", _t("nav.dashboard", "Dashboard")),
            ("health", _t("nav.health", "System Health")),
            ("users", _t("nav.users", "User Management")),
            ("analytics", _t("nav.analytics", "Student Analytics")),
            ("misconduct", _t("nav.misconduct", "Misconduct")),
            ("notifications", _t("nav.notifications", "Notifications")),
            ("search", _t("nav.search", "Student Search")),
            ("journey", _t("nav.journey", "Student Journey")),
            ("permissions", _t("nav.permissions", "Permission Matrix")),
            ("password_policy", _t("nav.password_policy", "Password Policy")),
            ("audit", _t("nav.audit", "Audit Log")),
            ("backup", _t("nav.backup", "Backup / Restore")),
            ("dbreport", _t("nav.dbreport", "Database Report")),
            ("batch", _t("nav.batch", "Batch Operations")),
            ("sessions", _t("nav.sessions", "Active Sessions")),
            ("launch", _t("nav.launch", "Quick Launch")),
        ]

        for key, label in sections:
            btn = tk.Button(
                nav_inner,
                text=f"  {label}",
                font=("Segoe UI", 11),
                bg=SIDEBAR_BTN,
                fg=TEXT_LIGHT,
                activebackground=SIDEBAR_BTN_ACTIVE,
                activeforeground=TEXT_LIGHT,
                relief=tk.FLAT,
                anchor=tk.W,
                padx=15,
                pady=8,
                cursor="hand2",
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(fill=tk.X, padx=8, pady=2)
            self._sidebar_buttons[key] = btn

            # Bind mousewheel on each button too so scrolling works when hovering over them
            btn.bind("<MouseWheel>", _on_sidebar_mousewheel)
            btn.bind("<Button-4>", _on_sidebar_button4)
            btn.bind("<Button-5>", _on_sidebar_button5)

        # Content area
        self._content_frame = tk.Frame(body, bg=CONTENT_BG)
        self._content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    # ------------------------------------------------------------------
    # Section switching
    # ------------------------------------------------------------------

    def _show_section(self, section_key):
        # Update sidebar button highlighting
        for key, btn in self._sidebar_buttons.items():
            if key == section_key:
                btn.configure(bg=SIDEBAR_BTN_ACTIVE)
            else:
                btn.configure(bg=SIDEBAR_BTN)

        self._current_section = section_key

        # Clear content area
        for child in self._content_frame.winfo_children():
            child.destroy()

        builders = {
            "dashboard": self._build_dashboard,
            "health": self._build_health,
            "users": self._build_users,
            "analytics": self._build_analytics,
            "misconduct": self._build_misconduct,
            "notifications": self._build_notifications,
            "search": self._build_search,
            "journey": self._build_journey,
            "permissions": self._build_permissions,
            "password_policy": self._build_password_policy,
            "audit": self._build_audit,
            "backup": self._build_backup,
            "dbreport": self._build_db_report,
            "batch": self._build_batch,
            "sessions": self._build_sessions,
            "launch": self._build_launch,
        }

        builder = builders.get(section_key)
        if builder:
            try:
                builder()
            except Exception as exc:
                self._show_error(f"Error loading section: {exc}")

    def _show_error(self, message):
        tk.Label(
            self._content_frame,
            text=message,
            font=("Segoe UI", 12),
            bg=CONTENT_BG,
            fg="#e74c3c",
            wraplength=600,
        ).pack(pady=40)

    # ------------------------------------------------------------------
    # Helper: scrollable frame
    # ------------------------------------------------------------------

    def _make_scrollable(self, parent):
        """Return a (canvas, scrollable_frame) tuple inside *parent*."""
        canvas = tk.Canvas(parent, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=CONTENT_BG)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        return canvas, inner

    # ------------------------------------------------------------------
    # Helper: stat card
    # ------------------------------------------------------------------

    def _make_stat_card(self, parent, title, value, color=None, subtitle=None, width=160):
        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        if color:
            accent = tk.Frame(card, bg=color, height=4)
            accent.pack(fill=tk.X, side=tk.TOP)
        tk.Label(
            card,
            text=str(title),
            font=("Segoe UI", 9),
            bg=CARD_BG,
            fg=TEXT_MUTED,
        ).pack(padx=12, pady=(10, 0), anchor=tk.W)
        tk.Label(
            card,
            text=str(value),
            font=("Segoe UI", 22, "bold"),
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(padx=12, anchor=tk.W)
        if subtitle:
            tk.Label(
                card,
                text=str(subtitle),
                font=("Segoe UI", 8),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(padx=12, pady=(0, 8), anchor=tk.W)
        else:
            tk.Frame(card, bg=CARD_BG, height=8).pack()
        return card

    # ------------------------------------------------------------------
    # Helper: system card with status
    # ------------------------------------------------------------------

    def _make_system_card(self, parent, info):
        """Build a card for a system using a health info dict."""
        sys_key = info.get("system", "")
        color = SYSTEM_COLORS.get(sys_key, "#95a5a6")
        label = info.get("label", sys_key.title())

        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)

        # Color accent bar
        accent = tk.Frame(card, bg=color, height=6)
        accent.pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        # Title row with status dot
        title_row = tk.Frame(body, bg=CARD_BG)
        title_row.pack(fill=tk.X)

        tk.Label(
            title_row,
            text=label,
            font=("Segoe UI", 12, "bold"),
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(side=tk.LEFT)

        status = info.get("status", "offline")
        dot_color = "#2ecc71" if status == "online" else (
            "#e74c3c" if status == "error" else "#95a5a6"
        )
        dot = tk.Canvas(title_row, width=14, height=14, bg=CARD_BG, highlightthickness=0)
        dot.create_oval(2, 2, 12, 12, fill=dot_color, outline="")
        dot.pack(side=tk.RIGHT)

        # Stats
        stats = [
            ("Students", info.get("student_count", 0)),
            ("Staff", info.get("staff_count", 0)),
            ("DB Size", f"{info.get('db_size_mb', 0)} MB"),
        ]
        for stat_label, stat_val in stats:
            row = tk.Frame(body, bg=CARD_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=stat_label,
                font=("Segoe UI", 9),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=str(stat_val),
                font=("Segoe UI", 9, "bold"),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.RIGHT)

        # Hint that the card is openable
        tk.Label(
            body,
            text="Double-click to open  →",
            font=("Segoe UI", 8),
            bg=CARD_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, pady=(6, 0))

        # Double-click anywhere on the card launches that system (same as the
        # Quick Launch section). Bind recursively because the card has nested
        # child widgets that would otherwise swallow the event.
        if sys_key:
            def _open(_e=None, sk=sys_key):
                self._launch_system(sk)

            def _bind_recursive(widget):
                widget.bind("<Double-Button-1>", _open)
                try:
                    widget.configure(cursor="hand2")
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    _bind_recursive(child)

            _bind_recursive(card)

        return card

    # ------------------------------------------------------------------
    # "Needs Attention" panel
    # ------------------------------------------------------------------

    def _build_alerts_panel(self, parent):
        """Render a triage panel of cross-system operational alerts.

        Empty state shows an "all clear" row so the panel is reassuring rather
        than blank. Each alert is clickable and jumps to the relevant section.
        """
        alerts = []
        svc = self._get_admin_service()
        if svc:
            try:
                alerts = svc.get_alerts()
            except Exception:
                alerts = []

        critical = sum(1 for a in alerts if a.get("severity") == "critical")
        header_text = "Needs Attention"
        if alerts:
            header_text += f"  ({len(alerts)})"

        header_row = tk.Frame(parent, bg=CONTENT_BG)
        header_row.pack(fill=tk.X, padx=24, pady=(0, 6))

        tk.Label(
            header_row,
            text=header_text,
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg="#c0392b" if critical else TEXT_DARK,
        ).pack(side=tk.LEFT)

        panel = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        panel.pack(fill=tk.X, padx=24, pady=(0, 16))

        if not alerts:
            ok_row = tk.Frame(panel, bg=CARD_BG)
            ok_row.pack(fill=tk.X, padx=14, pady=12)
            dot = tk.Canvas(ok_row, width=12, height=12, bg=CARD_BG, highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=ALERT_OK, outline="")
            dot.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(
                ok_row,
                text="All systems healthy — no alerts.",
                font=("Segoe UI", 10),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.LEFT)
            return

        for i, alert in enumerate(alerts):
            self._build_alert_row(panel, alert, last=(i == len(alerts) - 1))

    def _build_alert_row(self, parent, alert, last=False):
        severity = alert.get("severity", "info")
        color = ALERT_COLORS.get(severity, ALERT_COLORS["info"])
        action = alert.get("action")

        row = tk.Frame(parent, bg=CARD_BG, cursor="hand2" if action else "arrow")
        row.pack(fill=tk.X, padx=14, pady=(8, 8 if last else 0))

        # Severity dot
        dot = tk.Canvas(row, width=12, height=12, bg=CARD_BG, highlightthickness=0)
        dot.create_oval(1, 1, 11, 11, fill=color, outline="")
        dot.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        # Severity pill
        tk.Label(
            row,
            text=severity.upper(),
            font=("Segoe UI", 7, "bold"),
            bg=color,
            fg=TEXT_LIGHT,
            padx=6,
            pady=1,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            row,
            text=alert.get("message", ""),
            font=("Segoe UI", 10),
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        if action:
            tk.Label(
                row,
                text="Resolve  →",
                font=("Segoe UI", 9, "bold"),
                bg=CARD_BG,
                fg=color,
            ).pack(side=tk.RIGHT)

            def _go(_e=None, target=action):
                self._show_section(target)

            for widget in (row, *row.winfo_children()):
                widget.bind("<Button-1>", _go)

        # Thin divider between rows
        if not last:
            tk.Frame(parent, bg="#ecf0f1", height=1).pack(fill=tk.X, padx=14)

    # ------------------------------------------------------------------
    # Trends (sparklines)
    # ------------------------------------------------------------------

    _TREND_COLORS = {
        "students": "#2980b9",
        "staff": "#27ae60",
        "users": "#e67e22",
        "storage_mb": "#8e44ad",
    }

    def _build_trends_panel(self, parent):
        """Render 30-day sparklines for the headline aggregate metrics."""
        svc = self._get_admin_service()
        if not svc:
            return
        try:
            svc.record_metrics_snapshot()  # capture today's point (daily-deduped)
            trends = svc.get_trends()
        except Exception:
            return
        if not trends:
            return

        tk.Label(
            parent, text="Trends (last 30 days)",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(8, 6))

        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(0, 16))
        row = tk.Frame(card, bg=CARD_BG)
        row.pack(fill=tk.X, padx=12, pady=12)

        for i, t in enumerate(trends):
            color = self._TREND_COLORS.get(t["metric"], "#3498db")
            cell = tk.Frame(row, bg=CARD_BG)
            cell.grid(row=0, column=i, padx=12, sticky=tk.NSEW)
            row.columnconfigure(i, weight=1)

            tk.Label(
                cell, text=t["label"], font=("Segoe UI", 9),
                bg=CARD_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W)

            cur = t["current"]
            cur_text = f"{cur:.1f}" if t["metric"] == "storage_mb" else f"{int(cur)}"
            tk.Label(
                cell, text=cur_text, font=("Segoe UI", 18, "bold"),
                bg=CARD_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W)

            if t["count"] >= 2:
                change = t["change"]
                if change > 0:
                    sign, ch_color = "▲", "#27ae60"
                elif change < 0:
                    sign, ch_color = "▼", "#e74c3c"
                else:
                    sign, ch_color = "—", TEXT_MUTED
                mag = f"{abs(change):.1f}" if t["metric"] == "storage_mb" else f"{int(abs(change))}"
                tk.Label(
                    cell, text=f"{sign} {mag}  ({t['change_pct']:+}%)",
                    font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=ch_color,
                ).pack(anchor=tk.W)
                self._draw_sparkline(cell, t["values"], color)
            else:
                tk.Label(
                    cell, text="collecting data…", font=("Segoe UI", 8),
                    bg=CARD_BG, fg=TEXT_MUTED,
                ).pack(anchor=tk.W, pady=(6, 0))

    def _draw_sparkline(self, parent, values, color, width=150, height=36):
        """Draw a small line chart of *values* onto a canvas and return it."""
        canvas = tk.Canvas(
            parent, width=width, height=height, bg=CARD_BG, highlightthickness=0,
        )
        canvas.pack(anchor=tk.W, pady=(4, 0))
        if len(values) < 2:
            return canvas

        vmin, vmax = min(values), max(values)
        span = (vmax - vmin) or 1
        n = len(values)
        pad = 4

        def point(i, v):
            x = pad + (width - 2 * pad) * i / (n - 1)
            y = (height - pad) - (height - 2 * pad) * (v - vmin) / span
            return x, y

        coords = []
        for i, v in enumerate(values):
            coords.extend(point(i, v))
        canvas.create_line(*coords, fill=color, width=2, smooth=True)

        lx, ly = point(n - 1, values[-1])
        canvas.create_oval(lx - 2.5, ly - 2.5, lx + 2.5, ly + 2.5,
                           fill=color, outline=color)
        return canvas

    # ------------------------------------------------------------------
    # Section: Dashboard (Overview)
    # ------------------------------------------------------------------

    def _build_dashboard(self):
        _, frame = self._make_scrollable(self._content_frame)

        # Section title
        tk.Label(
            frame,
            text="Dashboard Overview",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text=f"Welcome back. Today is {datetime.now().strftime('%A, %d %B %Y')}.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # "Needs Attention" panel — operational exceptions across all systems
        self._build_alerts_panel(frame)

        # System cards row
        health_data = []
        svc = self._get_admin_service()
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        cards_row = tk.Frame(frame, bg=CONTENT_BG)
        cards_row.pack(fill=tk.X, padx=20, pady=(0, 12))

        if health_data:
            for i, info in enumerate(health_data):
                card = self._make_system_card(cards_row, info)
                card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
                cards_row.columnconfigure(i, weight=1)
        else:
            # Fallback: show placeholder cards for all 5 systems
            for i, sys_key in enumerate(SYSTEM_ORDER):
                placeholder = {
                    "system": sys_key,
                    "label": SYSTEM_LABELS[sys_key],
                    "status": "unknown",
                    "student_count": "N/A",
                    "staff_count": "N/A",
                    "db_size_mb": "N/A",
                }
                card = self._make_system_card(cards_row, placeholder)
                card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
                cards_row.columnconfigure(i, weight=1)

        # Summary stats row
        total_students = sum(h.get("student_count", 0) for h in health_data)
        total_staff = sum(h.get("staff_count", 0) for h in health_data)

        # Get additional summary data
        total_transfers = 0
        active_sessions = 0
        analytics_svc = self._get_analytics_service()
        if analytics_svc:
            try:
                summary = analytics_svc.get_summary()
                total_transfers = summary.get("total_transferred", 0)
            except Exception:
                pass

        user_summary = {}
        if svc:
            try:
                user_summary = svc.get_user_summary()
                active_sessions = user_summary.get("total_users", 0)
            except Exception:
                pass

        stats_row = tk.Frame(frame, bg=CONTENT_BG)
        stats_row.pack(fill=tk.X, padx=20, pady=(0, 16))

        stat_items = [
            ("Total Students", total_students, "#2980b9"),
            ("Total Staff", total_staff, "#27ae60"),
            ("Total Transfers", total_transfers, "#8e44ad"),
            ("Registered Users", active_sessions, "#e67e22"),
        ]
        for i, (label, val, color) in enumerate(stat_items):
            card = self._make_stat_card(stats_row, label, val, color=color)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            stats_row.columnconfigure(i, weight=1)

        # Trends (30-day sparklines)
        self._build_trends_panel(frame)

        # Recent activity
        tk.Label(
            frame,
            text="Recent Activity",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(8, 6))

        activity_frame = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        activity_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

        audit_entries = []
        if svc:
            try:
                audit_entries = svc.get_audit_summary(limit=10)
            except Exception:
                pass

        if audit_entries:
            for entry in audit_entries[:10]:
                row = tk.Frame(activity_frame, bg=CARD_BG)
                row.pack(fill=tk.X, padx=12, pady=4)

                etype = entry.get("type", "")
                dot_color = "#3498db" if etype == "notification" else "#9b59b6"
                dot = tk.Canvas(row, width=10, height=10, bg=CARD_BG, highlightthickness=0)
                dot.create_oval(1, 1, 9, 9, fill=dot_color, outline="")
                dot.pack(side=tk.LEFT, padx=(0, 8), pady=4)

                tk.Label(
                    row,
                    text=entry.get("description", ""),
                    font=("Segoe UI", 9),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                    anchor=tk.W,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)

                ts = entry.get("timestamp", "")
                if ts:
                    tk.Label(
                        row,
                        text=ts[:16],
                        font=("Segoe UI", 8),
                        bg=CARD_BG,
                        fg=TEXT_MUTED,
                    ).pack(side=tk.RIGHT)
        else:
            tk.Label(
                activity_frame,
                text="No recent activity found.",
                font=("Segoe UI", 10),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(padx=12, pady=16)

    # ------------------------------------------------------------------
    # Comparative table (system x metrics, sortable)
    # ------------------------------------------------------------------

    def _build_comparison_table(self, parent, rows):
        """Render all systems as one sortable table so outliers stand out."""
        tk.Label(
            parent,
            text="Systems at a Glance",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 2))
        tk.Label(
            parent,
            text="Click a column header to sort. Red = offline/error, orange = open issues.",
            font=("Segoe UI", 8),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        wrapper = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        wrapper.pack(fill=tk.X, padx=24, pady=(0, 4))

        col_ids = [c[0] for c in COMPARISON_COLUMNS]
        tree = ttk.Treeview(
            wrapper, columns=col_ids, show="headings",
            height=len(rows), selectmode="none",
        )
        for col_id, heading, width, anchor, _key, _fmt in COMPARISON_COLUMNS:
            tree.heading(
                col_id, text=heading,
                command=lambda c=col_id: self._sort_comparison(c),
            )
            tree.column(col_id, width=width, anchor=anchor, stretch=True)

        tree.tag_configure("down", foreground="#e74c3c")
        tree.tag_configure("issue", foreground="#e67e22")
        tree.tag_configure("ok", foreground=TEXT_DARK)

        tree.pack(fill=tk.X, padx=2, pady=2)

        # State for sorting; default order is the configured system order.
        self._cmp_tree = tree
        self._cmp_rows = list(rows)
        self._cmp_sort_col = None
        self._cmp_sort_desc = False
        self._populate_comparison()

    def _populate_comparison(self):
        tree = self._cmp_tree
        tree.delete(*tree.get_children())
        fmts = {c[0]: c[5] for c in COMPARISON_COLUMNS}
        for r in self._cmp_rows:
            values = [fmts[c[0]](r) for c in COMPARISON_COLUMNS]
            if r["status"] != "online":
                tag = "down"
            elif r["open_issues"] > 0:
                tag = "issue"
            else:
                tag = "ok"
            tree.insert("", tk.END, values=values, tags=(tag,))

    def _sort_comparison(self, col_id):
        key_fn = next(c[4] for c in COMPARISON_COLUMNS if c[0] == col_id)
        if self._cmp_sort_col == col_id:
            self._cmp_sort_desc = not self._cmp_sort_desc
        else:
            self._cmp_sort_col = col_id
            self._cmp_sort_desc = False
        self._cmp_rows.sort(key=key_fn, reverse=self._cmp_sort_desc)
        self._populate_comparison()

        # Reflect sort direction in the heading text.
        arrow = " ▼" if self._cmp_sort_desc else " ▲"
        for c in COMPARISON_COLUMNS:
            heading = c[1] + (arrow if c[0] == col_id else "")
            self._cmp_tree.heading(c[0], text=heading)

    # ------------------------------------------------------------------
    # Section: System Health
    # ------------------------------------------------------------------

    def _build_health(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="System Health",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Database status and resource usage for each education system.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        svc = self._get_admin_service()

        # Comparative table — all systems side by side, sortable.
        comparison = []
        if svc:
            try:
                comparison = svc.get_comparison()
            except Exception:
                comparison = []
        if comparison:
            self._build_comparison_table(frame, comparison)

        health_data = []
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        if not health_data:
            if not comparison:
                tk.Label(
                    frame,
                    text="Unable to retrieve system health data.",
                    font=("Segoe UI", 11),
                    bg=CONTENT_BG,
                    fg="#e74c3c",
                ).pack(pady=30)
            return

        tk.Label(
            frame,
            text="Per-System Detail",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(16, 6))

        for info in health_data:
            sys_key = info.get("system", "")
            color = SYSTEM_COLORS.get(sys_key, "#95a5a6")

            card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.pack(fill=tk.X, padx=24, pady=6)

            accent = tk.Frame(card, bg=color, width=6)
            accent.pack(side=tk.LEFT, fill=tk.Y)

            body = tk.Frame(card, bg=CARD_BG)
            body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

            # Title + status
            title_row = tk.Frame(body, bg=CARD_BG)
            title_row.pack(fill=tk.X)

            tk.Label(
                title_row,
                text=info.get("label", sys_key),
                font=("Segoe UI", 13, "bold"),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.LEFT)

            status = info.get("status", "offline")
            status_text = status.upper()
            status_fg = "#2ecc71" if status == "online" else (
                "#e74c3c" if status == "error" else "#95a5a6"
            )
            tk.Label(
                title_row,
                text=status_text,
                font=("Segoe UI", 10, "bold"),
                bg=CARD_BG,
                fg=status_fg,
            ).pack(side=tk.RIGHT)

            # Details grid
            details_frame = tk.Frame(body, bg=CARD_BG)
            details_frame.pack(fill=tk.X, pady=(8, 0))

            detail_items = [
                ("Database Exists", "Yes" if info.get("db_exists") else "No"),
                ("DB Size", f"{info.get('db_size_mb', 0)} MB"),
                ("Students", str(info.get("student_count", 0))),
                ("Staff", str(info.get("staff_count", 0))),
                ("Last Activity", info.get("last_activity", "N/A") or "N/A"),
            ]

            for i, (dlabel, dval) in enumerate(detail_items):
                col = i % 5
                tk.Label(
                    details_frame,
                    text=dlabel,
                    font=("Segoe UI", 8),
                    bg=CARD_BG,
                    fg=TEXT_MUTED,
                ).grid(row=0, column=col, padx=(0, 20), sticky=tk.W)
                tk.Label(
                    details_frame,
                    text=dval,
                    font=("Segoe UI", 10, "bold"),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                ).grid(row=1, column=col, padx=(0, 20), sticky=tk.W)

            # DB path
            svc2 = self._get_admin_service()
            db_path_text = ""
            if svc2:
                try:
                    cfg = svc2.get_system_config(sys_key)
                    db_path_text = cfg.get("db_path", "")
                except Exception:
                    pass

            if db_path_text:
                tk.Label(
                    body,
                    text=f"Path: {db_path_text}",
                    font=("Segoe UI", 8),
                    bg=CARD_BG,
                    fg=TEXT_MUTED,
                ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Section: User Management
    # ------------------------------------------------------------------

    def _build_users(self):
        tk.Label(
            self._content_frame,
            text="User Management",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="View and filter all users across every education system.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Filter bar
        filter_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        filter_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        tk.Label(filter_bar, text="System:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        system_var = tk.StringVar(value="All")
        system_combo = ttk.Combobox(
            filter_bar,
            textvariable=system_var,
            values=["All", *SYSTEM_ORDER],
            state="readonly",
            width=14,
        )
        system_combo.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(filter_bar, text="Role:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        role_var = tk.StringVar(value="All")
        role_combo = ttk.Combobox(
            filter_bar,
            textvariable=role_var,
            values=["All", "superadmin", "admin", "staff", "student", "parent"],
            state="readonly",
            width=14,
        )
        role_combo.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(filter_bar, text="Search:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.Entry(filter_bar, textvariable=search_var, width=22, font=("Segoe UI", 10))
        search_entry.pack(side=tk.LEFT, padx=(0, 8))

        # Treeview
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("username", "display_name", "email", "systems", "roles", "active", "last_login")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=22)

        headings = {
            "username": ("Username", 120),
            "display_name": ("Display Name", 150),
            "email": ("Email", 180),
            "systems": ("System(s)", 160),
            "roles": ("Role(s)", 130),
            "active": ("Active", 60),
            "last_login": ("Last Login", 140),
        }
        for col, (heading, width) in headings.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        all_users = []
        svc = self._get_admin_service()
        if svc:
            try:
                all_users = svc.get_all_users()
            except Exception:
                pass

        def _populate(users_list):
            tree.delete(*tree.get_children())
            for u in users_list:
                sys_list = [s["system_key"] for s in u.get("systems", [])]
                role_list = list({s["role"] for s in u.get("systems", [])})
                tree.insert("", tk.END, values=(
                    u.get("username", ""),
                    u.get("display_name", ""),
                    u.get("email", ""),
                    ", ".join(sys_list),
                    ", ".join(role_list),
                    "Yes" if u.get("is_active") else "No",
                    u.get("last_login", "")[:19] if u.get("last_login") else "",
                ))

        def _apply_filter(*_args):
            sys_filter = system_var.get()
            role_filter = role_var.get()
            search_text = search_var.get().strip().lower()

            filtered = all_users
            if sys_filter and sys_filter != "All":
                filtered = [
                    u for u in filtered
                    if any(s["system_key"] == sys_filter for s in u.get("systems", []))
                ]
            if role_filter and role_filter != "All":
                filtered = [
                    u for u in filtered
                    if any(s["role"] == role_filter for s in u.get("systems", []))
                ]
            if search_text:
                filtered = [
                    u for u in filtered
                    if search_text in (u.get("username", "").lower())
                    or search_text in (u.get("display_name", "").lower())
                    or search_text in (u.get("email", "").lower())
                ]
            _populate(filtered)

        system_combo.bind("<<ComboboxSelected>>", _apply_filter)
        role_combo.bind("<<ComboboxSelected>>", _apply_filter)
        search_entry.bind("<KeyRelease>", _apply_filter)

        filter_btn = tk.Button(
            filter_bar,
            text="Apply",
            font=("Segoe UI", 10),
            bg="#3498db",
            fg=TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            command=_apply_filter,
        )
        filter_btn.pack(side=tk.LEFT)

        # Action buttons row
        action_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        action_bar.pack(fill=tk.X, padx=24, pady=(0, 4))

        def _get_selected_user():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a user first.")
                return None
            vals = tree.item(sel[0], "values")
            username = vals[0]
            for u in all_users:
                if u.get("username") == username:
                    return u
            return None

        def _on_create_user():
            self._show_create_user_dialog()

        def _on_edit_user():
            user = _get_selected_user()
            if user:
                self._show_edit_user_dialog(user)

        def _on_reset_password():
            user = _get_selected_user()
            if not user:
                return
            new_pw = simpledialog.askstring(
                "Reset Password",
                f"Enter new password for '{user['username']}':",
                show="*",
                parent=self,
            )
            if not new_pw:
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.reset_password(user["id"], new_pw)
                    messagebox.showinfo("Success", f"Password reset for '{user['username']}'.")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        def _on_deactivate():
            user = _get_selected_user()
            if not user:
                return
            if not messagebox.askyesno(
                "Confirm Deactivation",
                f"Deactivate user '{user['username']}'?",
            ):
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.deactivate_user(user["id"])
                    messagebox.showinfo("Success", f"User '{user['username']}' deactivated.")
                    self._show_section("users")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        for btn_text, btn_cmd, btn_color in [
            ("Create User", _on_create_user, "#27ae60"),
            ("Edit User", _on_edit_user, "#2980b9"),
            ("Reset Password", _on_reset_password, "#e67e22"),
            ("Deactivate", _on_deactivate, "#e74c3c"),
        ]:
            tk.Button(
                action_bar,
                text=btn_text,
                font=("Segoe UI", 9),
                bg=btn_color,
                fg=TEXT_LIGHT,
                relief=tk.FLAT,
                cursor="hand2",
                padx=10,
                pady=2,
                command=btn_cmd,
            ).pack(side=tk.LEFT, padx=(0, 6))

        _populate(all_users)

    # ------------------------------------------------------------------
    # User dialogs
    # ------------------------------------------------------------------

    def _show_create_user_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create User")
        dlg.geometry("420x440")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Create New User", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        fields_frame = tk.Frame(dlg)
        fields_frame.pack(padx=20, fill=tk.X)

        entries = {}
        for label_text in ("Username", "Display Name", "Email", "Password"):
            row = tk.Frame(fields_frame)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label_text + ":", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar()
            ent = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=28)
            if label_text == "Password":
                ent.configure(show="*")
            ent.pack(side=tk.LEFT)
            entries[label_text.lower().replace(" ", "_")] = var

        # System / role assignments
        tk.Label(dlg, text="System / Role Assignments:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, padx=20, pady=(10, 4)
        )
        sr_frame = tk.Frame(dlg)
        sr_frame.pack(padx=20, fill=tk.X)

        sys_role_vars = []
        for sys_key in SYSTEM_ORDER:
            row = tk.Frame(sr_frame)
            row.pack(fill=tk.X, pady=1)
            enabled_var = tk.BooleanVar(value=False)
            tk.Checkbutton(row, text=SYSTEM_LABELS[sys_key], variable=enabled_var, width=18, anchor=tk.W).pack(
                side=tk.LEFT
            )
            role_var = tk.StringVar(value="student")
            ttk.Combobox(
                row, textvariable=role_var,
                values=["superadmin", "admin", "staff", "student", "parent"],
                state="readonly", width=12,
            ).pack(side=tk.LEFT, padx=4)
            sys_role_vars.append((sys_key, enabled_var, role_var))

        def _save():
            username = entries["username"].get().strip()
            display_name = entries["display_name"].get().strip()
            email = entries["email"].get().strip()
            password = entries["password"].get()
            if not username or not password:
                messagebox.showwarning("Validation", "Username and password are required.", parent=dlg)
                return
            systems_roles = [
                {"system_key": sk, "role": rv.get()}
                for sk, ev, rv in sys_role_vars if ev.get()
            ]
            svc = self._get_admin_service()
            if svc:
                try:
                    svc.create_user(username, display_name, email, password, systems_roles)
                    messagebox.showinfo("Success", f"User '{username}' created.", parent=dlg)
                    dlg.destroy()
                    self._show_section("users")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Create", font=("Segoe UI", 11), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_save,
        ).pack(pady=16)

    def _show_edit_user_dialog(self, user):
        dlg = tk.Toplevel(self)
        dlg.title("Edit User")
        dlg.geometry("420x400")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=f"Edit User: {user['username']}", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        fields_frame = tk.Frame(dlg)
        fields_frame.pack(padx=20, fill=tk.X)

        dn_var = tk.StringVar(value=user.get("display_name", ""))
        email_var = tk.StringVar(value=user.get("email", ""))
        active_var = tk.BooleanVar(value=user.get("is_active", True))

        for label_text, var in [("Display Name", dn_var), ("Email", email_var)]:
            row = tk.Frame(fields_frame)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label_text + ":", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=28).pack(side=tk.LEFT)

        row = tk.Frame(fields_frame)
        row.pack(fill=tk.X, pady=3)
        tk.Checkbutton(row, text="Active", variable=active_var, font=("Segoe UI", 10)).pack(side=tk.LEFT)

        # System / role editing
        tk.Label(dlg, text="System / Role Assignments:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, padx=20, pady=(10, 4)
        )
        sr_frame = tk.Frame(dlg)
        sr_frame.pack(padx=20, fill=tk.X)

        current_systems = {s["system_key"]: s["role"] for s in user.get("systems", [])}
        sr_vars = []
        for sys_key in SYSTEM_ORDER:
            row = tk.Frame(sr_frame)
            row.pack(fill=tk.X, pady=1)
            enabled_var = tk.BooleanVar(value=sys_key in current_systems)
            tk.Checkbutton(row, text=SYSTEM_LABELS[sys_key], variable=enabled_var, width=18, anchor=tk.W).pack(
                side=tk.LEFT
            )
            role_var = tk.StringVar(value=current_systems.get(sys_key, "student"))
            ttk.Combobox(
                row, textvariable=role_var,
                values=["superadmin", "admin", "staff", "student", "parent"],
                state="readonly", width=12,
            ).pack(side=tk.LEFT, padx=4)
            sr_vars.append((sys_key, enabled_var, role_var))

        def _save():
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                svc.update_user(
                    user["id"],
                    display_name=dn_var.get().strip() or None,
                    email=email_var.get().strip() or None,
                    is_active=active_var.get(),
                )
                new_sr = [
                    {"system_key": sk, "role": rv.get()}
                    for sk, ev, rv in sr_vars if ev.get()
                ]
                svc.update_user_systems(user["id"], new_sr)
                messagebox.showinfo("Success", "User updated.", parent=dlg)
                dlg.destroy()
                self._show_section("users")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Save Changes", font=("Segoe UI", 11), bg="#2980b9", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_save,
        ).pack(pady=16)

    # ------------------------------------------------------------------
    # Section: Student Analytics
    # ------------------------------------------------------------------

    def _build_analytics(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Student Analytics",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Cross-system student statistics, transfer rates, and retention data.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Export button
        export_bar = tk.Frame(frame, bg=CONTENT_BG)
        export_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        def _export_csv():
            svc = self._get_analytics_service()
            if not svc:
                messagebox.showerror("Error", "Analytics service unavailable.")
                return
            try:
                csv_data = svc.export_summary_csv()
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(
                    title="Export Analytics CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                    initialfile=f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    parent=self,
                )
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(csv_data)
                    messagebox.showinfo("Exported", f"Analytics exported to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc))

        tk.Button(
            export_bar, text="Export CSV", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, pady=2, command=_export_csv,
        ).pack(side=tk.LEFT)

        analytics_svc = self._get_analytics_service()

        # Summary cards
        summary = {}
        if analytics_svc:
            try:
                summary = analytics_svc.get_summary()
            except Exception:
                pass

        cards_row = tk.Frame(frame, bg=CONTENT_BG)
        cards_row.pack(fill=tk.X, padx=20, pady=(0, 12))

        summary_items = [
            ("Total Students", summary.get("total_students", 0), "#2980b9"),
            ("Active", summary.get("total_active", 0), "#27ae60"),
            ("Transferred", summary.get("total_transferred", 0), "#8e44ad"),
            ("Graduated", summary.get("total_graduated", 0), "#e67e22"),
        ]
        for i, (label, val, color) in enumerate(summary_items):
            card = self._make_stat_card(cards_row, label, val, color=color)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            cards_row.columnconfigure(i, weight=1)

        # Per-system breakdown
        tk.Label(
            frame,
            text="Per-System Breakdown",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        per_system = summary.get("systems", [])
        if per_system:
            ps_frame = tk.Frame(frame, bg=CONTENT_BG)
            ps_frame.pack(fill=tk.X, padx=20, pady=(0, 12))

            # 3 columns → a 3×3 grid across the nine systems.
            _ANALYTICS_COLS = 3
            for c in range(_ANALYTICS_COLS):
                ps_frame.columnconfigure(c, weight=1, uniform="sysgrid")

            for i, sys_info in enumerate(per_system):
                sys_key = sys_info.get("system", "")
                color = SYSTEM_COLORS.get(sys_key, "#95a5a6")
                grid_row, grid_col = divmod(i, _ANALYTICS_COLS)
                card = tk.Frame(ps_frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
                card.grid(row=grid_row, column=grid_col, padx=6, pady=6, sticky=tk.NSEW)

                accent = tk.Frame(card, bg=color, height=4)
                accent.pack(fill=tk.X, side=tk.TOP)

                tk.Label(
                    card,
                    text=sys_info.get("label", sys_key),
                    font=("Segoe UI", 11, "bold"),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                ).pack(padx=10, pady=(8, 2), anchor=tk.W)

                for stat_name in ("total", "active", "transferred", "graduated", "dropped_out"):
                    val = sys_info.get(stat_name, 0)
                    row = tk.Frame(card, bg=CARD_BG)
                    row.pack(fill=tk.X, padx=10, pady=1)
                    tk.Label(
                        row,
                        text=stat_name.replace("_", " ").title(),
                        font=("Segoe UI", 9),
                        bg=CARD_BG,
                        fg=TEXT_MUTED,
                    ).pack(side=tk.LEFT)
                    tk.Label(
                        row,
                        text=str(val),
                        font=("Segoe UI", 9, "bold"),
                        bg=CARD_BG,
                        fg=TEXT_DARK,
                    ).pack(side=tk.RIGHT)

                tk.Frame(card, bg=CARD_BG, height=8).pack()

        # Retention stats
        tk.Label(
            frame,
            text="Retention Statistics",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        retention = []
        if analytics_svc:
            try:
                retention = analytics_svc.get_retention_stats()
            except Exception:
                pass

        if retention:
            ret_tree_frame = tk.Frame(frame, bg=CONTENT_BG)
            ret_tree_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

            ret_cols = ("system", "total", "active", "retained_pct", "dropped_out", "dropout_pct")
            ret_tree = ttk.Treeview(ret_tree_frame, columns=ret_cols, show="headings", height=5)
            for col, heading, w in [
                ("system", "System", 160),
                ("total", "Total", 80),
                ("active", "Active", 80),
                ("retained_pct", "Retained %", 100),
                ("dropped_out", "Dropped Out", 100),
                ("dropout_pct", "Dropout %", 100),
            ]:
                ret_tree.heading(col, text=heading)
                ret_tree.column(col, width=w, minwidth=60)

            for r in retention:
                ret_tree.insert("", tk.END, values=(
                    r.get("label", ""),
                    r.get("total", 0),
                    r.get("active", 0),
                    f"{r.get('retained_pct', 0)}%",
                    r.get("dropped_out", 0),
                    f"{r.get('dropout_pct', 0)}%",
                ))
            ret_tree.pack(fill=tk.X)

        # Transfer rates
        tk.Label(
            frame,
            text="Transfer Rates",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        transfers = []
        if analytics_svc:
            try:
                transfers = analytics_svc.get_transfer_rates()
            except Exception:
                pass

        if transfers:
            tr_frame = tk.Frame(frame, bg=CONTENT_BG)
            tr_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

            tr_cols = ("source", "destination", "count", "rate")
            tr_tree = ttk.Treeview(tr_frame, columns=tr_cols, show="headings", height=min(8, len(transfers)))
            for col, heading, w in [
                ("source", "Source", 160),
                ("destination", "Destination", 160),
                ("count", "Count", 80),
                ("rate", "Rate %", 80),
            ]:
                tr_tree.heading(col, text=heading)
                tr_tree.column(col, width=w, minwidth=60)

            for t in transfers:
                src = SYSTEM_LABELS.get(t.get("source_system", ""), t.get("source_system", ""))
                dst = SYSTEM_LABELS.get(t.get("destination_system", ""), t.get("destination_system", ""))
                tr_tree.insert("", tk.END, values=(
                    src, dst, t.get("count", 0), f"{t.get('rate_pct', 0)}%",
                ))
            tr_tree.pack(fill=tk.X)
        else:
            tk.Label(
                frame,
                text="No transfer data available.",
                font=("Segoe UI", 10),
                bg=CONTENT_BG,
                fg=TEXT_MUTED,
            ).pack(padx=24, pady=8, anchor=tk.W)

        # Year-over-year trends (drill-down analytics, Feature 10)
        tk.Label(
            frame, text="Year-over-Year Trends",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        trends = []
        if analytics_svc:
            try:
                trends = analytics_svc.get_year_trends()
            except Exception:
                pass

        if trends:
            trend_frame = tk.Frame(frame, bg=CONTENT_BG)
            trend_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

            trend_cols = ("system", "year", "count")
            trend_tree = ttk.Treeview(
                trend_frame, columns=trend_cols, show="headings",
                height=min(10, len(trends)),
            )
            for col, heading, w in [
                ("system", "System", 160),
                ("year", "Year", 80),
                ("count", "Student Count", 120),
            ]:
                trend_tree.heading(col, text=heading)
                trend_tree.column(col, width=w, minwidth=60)

            for t in trends:
                trend_tree.insert("", tk.END, values=(
                    t.get("label", ""), t.get("year", ""), t.get("student_count", 0),
                ))
            trend_tree.pack(fill=tk.X)
        else:
            tk.Label(
                frame, text="No trend data available.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(padx=24, pady=8, anchor=tk.W)

        # Comparative summary (drill-down analytics, Feature 10)
        tk.Label(
            frame, text="Cross-System Comparison",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        comp_frame = tk.Frame(frame, bg=CONTENT_BG)
        comp_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        health_data = []
        svc = self._get_admin_service()
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        retention = []
        if analytics_svc:
            try:
                retention = analytics_svc.get_retention_stats()
            except Exception:
                pass

        ret_map = {r["system"]: r for r in retention}

        for i, sys_key in enumerate(SYSTEM_ORDER):
            color = SYSTEM_COLORS[sys_key]
            card = tk.Frame(comp_frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            comp_frame.columnconfigure(i, weight=1)

            accent = tk.Frame(card, bg=color, height=4)
            accent.pack(fill=tk.X, side=tk.TOP)

            tk.Label(
                card, text=SYSTEM_LABELS[sys_key],
                font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(padx=8, pady=(6, 2), anchor=tk.W)

            # Find matching health and retention data
            h = next((x for x in health_data if x.get("system") == sys_key), {})
            r = ret_map.get(sys_key, {})

            stats = [
                ("Students", h.get("student_count", 0)),
                ("Staff", h.get("staff_count", 0)),
                ("DB Size", f"{h.get('db_size_mb', 0)} MB"),
                ("Retained", f"{r.get('retained_pct', 0)}%"),
                ("Dropout", f"{r.get('dropout_pct', 0)}%"),
            ]
            for stat_label, stat_val in stats:
                row = tk.Frame(card, bg=CARD_BG)
                row.pack(fill=tk.X, padx=8, pady=1)
                tk.Label(row, text=stat_label, font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED).pack(side=tk.LEFT)
                tk.Label(row, text=str(stat_val), font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(
                    side=tk.RIGHT
                )

            tk.Frame(card, bg=CARD_BG, height=6).pack()

    # ------------------------------------------------------------------
    # Section: Academic Misconduct (Cross-System)
    # ------------------------------------------------------------------

    def _build_misconduct(self):
        """Build the cross-system academic misconduct overview and launch panel."""
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Academic Misconduct - Cross-System Overview",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="View misconduct cases across all education systems or launch the full misconduct panel.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 20))

        # Stats cards across systems
        try:
            import sqlite3
            from education_system.shared.academic_misconduct._imports import DEFAULT_DB_PATH
            from education_system.shared.academic_misconduct.database import init_misconduct_tables

            init_misconduct_tables()
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Global stats
            stats_frame = tk.Frame(frame, bg=CONTENT_BG)
            stats_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE severity = 'Critical'")
            critical = cursor.fetchone()[0]

            global_stats = [
                ("Total Cases", total, "#3498db"),
                ("Active", active, "#f39c12"),
                ("Resolved", resolved, "#27ae60"),
                ("Critical", critical, "#e74c3c"),
            ]

            for i, (label, value, color) in enumerate(global_stats):
                card = tk.Frame(stats_frame, bg=color, width=160, height=80)
                card.pack(side=tk.LEFT, padx=6, fill=tk.BOTH, expand=True)
                card.pack_propagate(False)
                tk.Label(card, text=str(value), font=("Segoe UI", 24, "bold"),
                         fg="white", bg=color).pack(pady=(10, 0))
                tk.Label(card, text=label, font=("Segoe UI", 9),
                         fg="white", bg=color).pack(pady=(0, 8))

            # Per-system breakdown
            tk.Label(
                frame,
                text="Per-System Breakdown",
                font=("Segoe UI", 14, "bold"),
                bg=CONTENT_BG,
                fg=TEXT_DARK,
            ).pack(anchor=tk.W, padx=24, pady=(10, 10))

            sys_row = tk.Frame(frame, bg=CONTENT_BG)
            sys_row.pack(fill=tk.X, padx=24, pady=(0, 20))

            for sys_key in SYSTEM_ORDER:
                sys_color = SYSTEM_COLORS[sys_key]
                sys_label = SYSTEM_LABELS[sys_key]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ?", (sys_key,))
                sys_total = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND status != 'Resolved'",
                    (sys_key,))
                sys_active = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND severity = 'Critical'",
                    (sys_key,))
                sys_critical = cursor.fetchone()[0]

                card = tk.Frame(sys_row, bg=CARD_BG, relief="solid", bd=1)
                card.pack(side=tk.LEFT, padx=6, fill=tk.BOTH, expand=True)

                # Colored header
                ch = tk.Frame(card, bg=sys_color, height=35)
                ch.pack(fill=tk.X)
                ch.pack_propagate(False)
                tk.Label(ch, text=sys_label, font=("Segoe UI", 10, "bold"),
                         fg="white", bg=sys_color).pack(expand=True)

                body = tk.Frame(card, bg=CARD_BG)
                body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

                for sl, sv in [("Total", sys_total), ("Active", sys_active), ("Critical", sys_critical)]:
                    r = tk.Frame(body, bg=CARD_BG)
                    r.pack(fill=tk.X, pady=2)
                    tk.Label(r, text=sl, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG).pack(side=tk.LEFT)
                    val_fg = "#e74c3c" if sl == "Critical" and sv > 0 else TEXT_DARK
                    tk.Label(r, text=str(sv), font=("Segoe UI", 10, "bold"),
                             fg=val_fg, bg=CARD_BG).pack(side=tk.RIGHT)

            conn.close()

        except Exception as e:
            tk.Label(
                frame,
                text=f"Could not load misconduct data: {e}",
                font=("Segoe UI", 10),
                fg="#e74c3c",
                bg=CONTENT_BG,
            ).pack(padx=24, pady=10)

        # Launch buttons
        tk.Label(
            frame,
            text="Launch Misconduct Panel",
            font=("Segoe UI", 14, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 10))

        btn_row = tk.Frame(frame, bg=CONTENT_BG)
        btn_row.pack(fill=tk.X, padx=24, pady=(0, 10))

        # All Systems (superadmin) button
        sa_btn = tk.Button(
            btn_row,
            text="Open All Systems View (Super Admin)",
            font=("Segoe UI", 11, "bold"),
            bg="#2c3e50",
            fg="white",
            activebackground="#34495e",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
            command=lambda: self._open_misconduct_panel(None),
        )
        sa_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Per-system launch buttons
        for sys_key in SYSTEM_ORDER:
            sys_color = SYSTEM_COLORS[sys_key]
            sys_label = SYSTEM_LABELS[sys_key]
            btn = tk.Button(
                btn_row,
                text=sys_label,
                font=("Segoe UI", 10),
                bg=sys_color,
                fg="white",
                activebackground=sys_color,
                activeforeground="white",
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=8,
                command=lambda sk=sys_key: self._open_misconduct_panel(sk),
            )
            btn.pack(side=tk.LEFT, padx=4)

    def _open_misconduct_panel(self, system_key):
        """Open the Academic Misconduct Panel from superadmin dashboard."""
        try:
            from education_system.shared.academic_misconduct.database import init_misconduct_tables
            from education_system.shared.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel

            init_misconduct_tables()
            window = tk.Toplevel(self)
            window.geometry("1400x900")

            # Build a minimal auth-like object so the panel doesn't reject us
            class _SuperAdminAuth:
                def __init__(self, user_info):
                    self.current_user = {
                        'username': user_info.get('username', 'superadmin'),
                        'role': 'admin',
                        'display_name': user_info.get('display_name', 'Super Admin'),
                    }

            auth = _SuperAdminAuth(self.user_info)
            AcademicMisconductPanel(window, auth=auth, system_key=system_key)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open misconduct panel:\n{e}")

    # ------------------------------------------------------------------
    # Section: Cross-System Notifications
    # ------------------------------------------------------------------

    def _build_notifications(self):
        tk.Label(
            self._content_frame,
            text="Cross-System Notifications",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        notif_svc = self._get_notification_service()
        user_id = self.user_info.get("id") or self.user_info.get("user_id")

        # Unread count badge
        unread_count = 0
        if notif_svc and user_id:
            try:
                unread_count = notif_svc.get_unread_count(user_id)
            except Exception:
                pass

        badge_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        badge_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

        badge_color = "#e74c3c" if unread_count > 0 else "#27ae60"
        tk.Label(
            badge_frame,
            text=f"  {unread_count} unread  ",
            font=("Segoe UI", 10, "bold"),
            bg=badge_color,
            fg=TEXT_LIGHT,
        ).pack(side=tk.LEFT)

        if unread_count > 0 and notif_svc and user_id:
            mark_btn = tk.Button(
                badge_frame,
                text="Mark All Read",
                font=("Segoe UI", 9),
                bg="#27ae60",
                fg=TEXT_LIGHT,
                relief=tk.FLAT,
                cursor="hand2",
                padx=10,
                command=lambda: self._mark_all_read_and_refresh(notif_svc, user_id),
            )
            mark_btn.pack(side=tk.LEFT, padx=10)

        # Send notification / broadcast buttons
        tk.Button(
            badge_frame, text="Send Notification", font=("Segoe UI", 9),
            bg="#2980b9", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=lambda: self._show_send_notification_dialog(notif_svc, user_id),
        ).pack(side=tk.LEFT, padx=(10, 4))

        tk.Button(
            badge_frame, text="Broadcast to Role", font=("Segoe UI", 9),
            bg="#8e44ad", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=lambda: self._show_broadcast_dialog(notif_svc, user_id),
        ).pack(side=tk.LEFT, padx=4)

        # Notifications list
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("id", "from_system", "title", "message", "priority", "read", "date")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)

        headings_map = {
            "id": ("ID", 40),
            "from_system": ("From System", 120),
            "title": ("Title", 200),
            "message": ("Message", 250),
            "priority": ("Priority", 80),
            "read": ("Read", 50),
            "date": ("Date", 140),
        }
        for col, (heading, width) in headings_map.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        notifications = []
        if notif_svc and user_id:
            try:
                notifications = notif_svc.get_all(user_id, limit=100)
            except Exception:
                pass

        for n in notifications:
            tree.insert("", tk.END, values=(
                n.get("id", ""),
                n.get("sender_system", ""),
                n.get("title", ""),
                (n.get("message", "") or "")[:80],
                n.get("priority", "normal"),
                "No" if not n.get("is_read") else "Yes",
                str(n.get("created_at", ""))[:16],
            ))

        if not notifications:
            tk.Label(
                self._content_frame,
                text="No notifications found.",
                font=("Segoe UI", 10),
                bg=CONTENT_BG,
                fg=TEXT_MUTED,
            ).pack(pady=8)

    def _mark_all_read_and_refresh(self, notif_svc, user_id):
        try:
            notif_svc.mark_all_read(user_id)
        except Exception:
            pass
        self._show_section("notifications")

    def _show_send_notification_dialog(self, notif_svc, sender_user_id):
        dlg = tk.Toplevel(self)
        dlg.title("Send Notification")
        dlg.geometry("440x360")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Send Notification", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))
        form = tk.Frame(dlg)
        form.pack(padx=20, fill=tk.X)

        # Recipient user ID
        row = tk.Frame(form); row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Recipient User ID:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        recip_var = tk.StringVar()
        tk.Entry(row, textvariable=recip_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Target system
        row2 = tk.Frame(form); row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Target System:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            row2, textvariable=sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Title
        row3 = tk.Frame(form); row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Title:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        tk.Entry(row3, textvariable=title_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Priority
        row4 = tk.Frame(form); row4.pack(fill=tk.X, pady=3)
        tk.Label(row4, text="Priority:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        prio_var = tk.StringVar(value="normal")
        ttk.Combobox(
            row4, textvariable=prio_var, values=["low", "normal", "high", "urgent"], state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Message
        tk.Label(form, text="Message:", font=("Segoe UI", 10), anchor=tk.W).pack(fill=tk.X, pady=(6, 2))
        msg_text = tk.Text(form, font=("Segoe UI", 10), height=4, width=40)
        msg_text.pack(fill=tk.X)

        def _send():
            if not title_var.get().strip():
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            if not notif_svc or not sender_user_id:
                messagebox.showerror("Error", "Notification service unavailable.", parent=dlg)
                return
            try:
                recip = int(recip_var.get().strip())
                notif_svc.send(
                    sender_user_id=sender_user_id,
                    sender_system="superadmin",
                    recipient_user_id=recip,
                    recipient_system=sys_var.get(),
                    title=title_var.get().strip(),
                    message=msg_text.get("1.0", tk.END).strip() or None,
                    priority=prio_var.get(),
                )
                messagebox.showinfo("Sent", "Notification sent.", parent=dlg)
                dlg.destroy()
                self._show_section("notifications")
            except ValueError:
                messagebox.showwarning("Validation", "Recipient User ID must be a number.", parent=dlg)
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Send", font=("Segoe UI", 11), bg="#2980b9", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_send,
        ).pack(pady=12)

    def _show_broadcast_dialog(self, notif_svc, sender_user_id):
        dlg = tk.Toplevel(self)
        dlg.title("Broadcast to Role")
        dlg.geometry("440x360")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Broadcast Announcement", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))
        form = tk.Frame(dlg)
        form.pack(padx=20, fill=tk.X)

        # Target system
        row = tk.Frame(form); row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Target System:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            row, textvariable=sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Target role
        row2 = tk.Frame(form); row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Target Role:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        role_var = tk.StringVar(value="student")
        ttk.Combobox(
            row2, textvariable=role_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Title
        row3 = tk.Frame(form); row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Title:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        tk.Entry(row3, textvariable=title_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Priority
        row4 = tk.Frame(form); row4.pack(fill=tk.X, pady=3)
        tk.Label(row4, text="Priority:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        prio_var = tk.StringVar(value="normal")
        ttk.Combobox(
            row4, textvariable=prio_var, values=["low", "normal", "high", "urgent"], state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Message
        tk.Label(form, text="Message:", font=("Segoe UI", 10), anchor=tk.W).pack(fill=tk.X, pady=(6, 2))
        msg_text = tk.Text(form, font=("Segoe UI", 10), height=4, width=40)
        msg_text.pack(fill=tk.X)

        def _broadcast():
            if not title_var.get().strip():
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            if not notif_svc or not sender_user_id:
                messagebox.showerror("Error", "Notification service unavailable.", parent=dlg)
                return
            try:
                count = notif_svc.send_to_role(
                    sender_user_id=sender_user_id,
                    sender_system="superadmin",
                    target_system=sys_var.get(),
                    target_role=role_var.get(),
                    title=title_var.get().strip(),
                    message=msg_text.get("1.0", tk.END).strip() or None,
                    priority=prio_var.get(),
                )
                messagebox.showinfo("Broadcast Sent", f"Notification sent to {count} user(s).", parent=dlg)
                dlg.destroy()
                self._show_section("notifications")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Broadcast", font=("Segoe UI", 11), bg="#8e44ad", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_broadcast,
        ).pack(pady=12)

    # ------------------------------------------------------------------
    # Section: Student Search
    # ------------------------------------------------------------------

    @staticmethod
    def _roles_summary(systems):
        """Render a user's system/role assignments as 'University:admin, ...'."""
        if not systems:
            return "—"
        return ", ".join(
            f"{SYSTEM_LABELS.get(s.get('system_key', ''), s.get('system_key', ''))}"
            f":{s.get('role', '')}"
            for s in systems
        )

    def _build_search(self):
        tk.Label(
            self._content_frame,
            text="Find a Person",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="One box for everyone — staff/admin accounts and students across "
                 "all systems. Shows system(s), role, account status, and last login.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Search bar
        search_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        search_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_bar, textvariable=search_var, font=("Segoe UI", 12), width=35,
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        search_entry.focus_set()

        count_label = tk.Label(
            self._content_frame,
            text="Type a name, username, email, or student ID and press Enter.",
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        count_label.pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Unified results treeview
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("kind", "name", "ident", "where", "status", "extra")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
        for col, heading, w in [
            ("kind", "Type", 70),
            ("name", "Name", 200),
            ("ident", "Username / ID", 140),
            ("where", "System(s) & Role", 260),
            ("status", "Status", 90),
            ("extra", "Last Login / Year", 150),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=50)

        tree.tag_configure("locked", foreground="#e74c3c")
        tree.tag_configure("inactive", foreground="#95a5a6")
        tree.tag_configure("student", foreground="#2c3e50")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _do_search(*_args):
            query = search_var.get().strip()
            if not query or len(query) < 2:
                return
            tree.delete(*tree.get_children())
            count_label.config(text="Searching…")

            svc = self._get_admin_service()
            if not svc:
                count_label.config(text="Admin service unavailable.")
                return
            try:
                res = svc.search(query)
            except Exception as exc:
                count_label.config(text=f"Search error: {exc}")
                return

            users = res.get("users", [])
            students = res.get("students", [])

            for u in users:
                status = u.get("status", "")
                last = (u.get("last_login", "") or "")[:16] or "never"
                tag = status if status in ("locked", "inactive") else ""
                tree.insert("", tk.END, tags=(tag,), values=(
                    "User",
                    u.get("display_name") or u.get("username", ""),
                    u.get("username", ""),
                    self._roles_summary(u.get("systems", [])),
                    status,
                    last,
                ))

            for s in students:
                sys_label = SYSTEM_LABELS.get(s.get("system", ""), s.get("system", ""))
                tree.insert("", tk.END, tags=("student",), values=(
                    "Student",
                    s.get("name", ""),
                    s.get("student_id", s.get("id", "")),
                    sys_label,
                    s.get("status", ""),
                    s.get("year_group", ""),
                ))

            total = len(users) + len(students)
            if not total:
                count_label.config(text=f"No matches for “{query}”.")
            else:
                count_label.config(
                    text=f"{total} match(es): {len(users)} account(s), "
                         f"{len(students)} student record(s).")

        tk.Button(
            search_bar, text="Search", font=("Segoe UI", 11), bg="#3498db",
            fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=16, command=_do_search,
        ).pack(side=tk.LEFT)

        search_entry.bind("<Return>", _do_search)

    # ------------------------------------------------------------------
    # Section: Audit Log
    # ------------------------------------------------------------------

    def _build_audit(self):
        tk.Label(
            self._content_frame,
            text="Audit Log",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="Recent cross-system transfers, notifications, and administrative activity.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Filter bar
        filter_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        filter_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        tk.Label(filter_bar, text="Type:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        type_var = tk.StringVar(value="All")
        ttk.Combobox(
            filter_bar, textvariable=type_var,
            values=["All", "notification", "transfer"], state="readonly", width=12,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filter_bar, text="From:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        tk.Entry(filter_bar, textvariable=from_var, font=("Segoe UI", 10), width=11).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="To:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        to_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(filter_bar, textvariable=to_var, font=("Segoe UI", 10), width=11).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="Search:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar()
        tk.Entry(filter_bar, textvariable=search_var, font=("Segoe UI", 10), width=16).pack(side=tk.LEFT, padx=(0, 8))

        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))

        columns = ("type", "timestamp", "description", "details")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        for col, heading, w in [
            ("type", "Type", 100),
            ("timestamp", "Timestamp", 160),
            ("description", "Description", 300),
            ("details", "Details", 300),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        no_data_label = tk.Label(
            self._content_frame, text="", font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        no_data_label.pack(pady=4)

        def _load_entries():
            tree.delete(*tree.get_children())
            no_data_label.config(text="")
            svc = self._get_admin_service()
            if not svc:
                no_data_label.config(text="Admin service unavailable.")
                return
            tf = type_var.get() if type_var.get() != "All" else None
            st = search_var.get().strip() or None
            df = from_var.get().strip() or None
            dt = to_var.get().strip() or None
            try:
                entries = svc.get_audit_summary(
                    limit=200, type_filter=tf, search_text=st,
                    date_from=df, date_to=dt,
                )
            except Exception:
                entries = []
            for e in entries:
                tree.insert("", tk.END, values=(
                    e.get("type", "").title(),
                    e.get("timestamp", "")[:19],
                    e.get("description", ""),
                    e.get("details", ""),
                ))
            if not entries:
                no_data_label.config(text="No audit entries match the current filters.")

        tk.Button(
            filter_bar, text="Apply", font=("Segoe UI", 10), bg="#3498db", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_load_entries,
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Export audit log
        def _export_audit():
            svc = self._get_admin_service()
            if not svc:
                return
            tf = type_var.get() if type_var.get() != "All" else None
            st = search_var.get().strip() or None
            df = from_var.get().strip() or None
            dt = to_var.get().strip() or None
            try:
                entries = svc.get_audit_summary(
                    limit=5000, type_filter=tf, search_text=st,
                    date_from=df, date_to=dt,
                )
                import csv
                import io
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(
                    title="Export Audit Log",
                    defaultextension=".csv",
                    filetypes=[("CSV Files", "*.csv")],
                    initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    parent=self,
                )
                if path:
                    with open(path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Type", "Timestamp", "Description", "Details"])
                        for e in entries:
                            writer.writerow([
                                e.get("type", ""), e.get("timestamp", ""),
                                e.get("description", ""), e.get("details", ""),
                            ])
                    messagebox.showinfo("Exported", f"Audit log exported to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc))

        tk.Button(
            filter_bar, text="Export CSV", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_export_audit,
        ).pack(side=tk.LEFT)

        _load_entries()

    # ------------------------------------------------------------------
    # Section: Student Journey (Feature 9)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Cohort flow (aggregate progression funnel)
    # ------------------------------------------------------------------

    def _build_cohort_flow(self, parent):
        """Render the cross-system progression funnel and drop-off analysis."""
        tk.Label(
            parent, text="Cohort Flow",
            font=("Segoe UI", 15, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(4, 2))
        tk.Label(
            parent,
            text="Progression funnel and drop-off: Primary → Secondary → "
                 "College → University.",
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        svc = self._get_journey_service()
        data = None
        if svc:
            try:
                data = svc.get_cohort_flow()
            except Exception:
                data = None

        if not data or not data.get("total_journeys"):
            tk.Label(
                parent, text="No cross-system journey records yet.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W, padx=24, pady=(0, 6))
            return

        # Year filter + summary line.
        controls = tk.Frame(parent, bg=CONTENT_BG)
        controls.pack(fill=tk.X, padx=24, pady=(0, 6))
        tk.Label(
            controls, text="Cohort year:", font=("Segoe UI", 9),
            bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT, padx=(0, 6))

        year_var = tk.StringVar(value="All")
        years = ["All"] + list(data.get("available_years", []))
        body = tk.Frame(parent, bg=CONTENT_BG)

        def _on_year(*_args):
            sel = year_var.get()
            current = data
            try:
                current = svc.get_cohort_flow(year=None if sel == "All" else sel)
            except Exception:
                pass
            for w in body.winfo_children():
                w.destroy()
            self._render_cohort_body(body, current)

        option = tk.OptionMenu(controls, year_var, *years, command=_on_year)
        option.configure(font=("Segoe UI", 9), bg=CARD_BG, relief=tk.FLAT, cursor="hand2")
        option.pack(side=tk.LEFT)

        body.pack(fill=tk.X)
        self._render_cohort_body(body, data)

    def _render_cohort_body(self, body, data):
        # --- Stage funnel (proportional bars) ---
        card = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(2, 8))
        tk.Label(
            card, text=f"Stage Funnel  ({data.get('total_journeys', 0)} journeys)",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 4))

        stages = data.get("stage_presence", [])
        max_count = max([s["count"] for s in stages] + [1])
        for s in stages:
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(
                row, text=s["label"], font=("Segoe UI", 9), bg=CARD_BG,
                fg=TEXT_DARK, width=18, anchor=tk.W,
            ).pack(side=tk.LEFT)
            bar_wrap = tk.Frame(row, bg="#ecf0f1", width=360, height=18)
            bar_wrap.pack(side=tk.LEFT, padx=(0, 8))
            bar_wrap.pack_propagate(False)
            width = max(2, int(360 * s["count"] / max_count))
            tk.Frame(
                bar_wrap, bg=SYSTEM_COLORS.get(s["system"], "#3498db"),
                width=width, height=18,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=str(s["count"]), font=("Segoe UI", 9, "bold"),
                bg=CARD_BG, fg=TEXT_DARK,
            ).pack(side=tk.LEFT)
        tk.Frame(card, bg=CARD_BG, height=6).pack()

        # --- Continuation & drop-off between adjacent stages ---
        card2 = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card2.pack(fill=tk.X, padx=24, pady=(0, 8))
        tk.Label(
            card2, text="Continuation & Drop-off",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 4))

        for c in data.get("continuation", []):
            row = tk.Frame(card2, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(
                row, text=f"{c['from_label']} → {c['to_label']}",
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_DARK,
                width=32, anchor=tk.W,
            ).pack(side=tk.LEFT)
            rate = c["rate"]
            rate_color = "#27ae60" if rate >= 75 else (
                "#e67e22" if rate >= 50 else "#e74c3c")
            tk.Label(
                row,
                text=f"{c['continued']}/{c['from_count']} continued ({rate}%)",
                font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=rate_color,
            ).pack(side=tk.LEFT)
            if c["dropped"]:
                tk.Label(
                    row, text=f"   {c['dropped']} dropped",
                    font=("Segoe UI", 9), bg=CARD_BG, fg="#e74c3c",
                ).pack(side=tk.LEFT)
        tk.Frame(card2, bg=CARD_BG, height=6).pack()

        # --- Recorded transitions (explicit moves logged in the registry) ---
        trans = data.get("transitions", [])
        if trans:
            card3 = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card3.pack(fill=tk.X, padx=24, pady=(0, 8))
            tk.Label(
                card3, text="Recorded Transitions  (click a row to see who moved)",
                font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, padx=12, pady=(8, 4))
            year = data.get("year")
            for t in trans:
                self._build_transition_row(card3, t, year)
            tk.Frame(card3, bg=CARD_BG, height=6).pack()

    def _build_transition_row(self, parent, t, year):
        """One clickable transition edge that expands to list the students."""
        row = tk.Frame(parent, bg=CARD_BG, cursor="hand2")
        row.pack(fill=tk.X, padx=12, pady=1)
        caret = tk.Label(
            row, text="▶", font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED, width=2,
        )
        caret.pack(side=tk.LEFT)
        tk.Label(
            row, text=f"{t['from_label']} → {t['to_label']}",
            font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_DARK, width=30, anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=str(t["count"]), font=("Segoe UI", 9, "bold"),
            bg=CARD_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT)

        detail = tk.Frame(parent, bg="#f7f9f9")

        def _toggle(_e=None):
            if detail.winfo_ismapped():
                detail.pack_forget()
                caret.config(text="▶")
                return
            for w in detail.winfo_children():
                w.destroy()
            self._populate_transition_students(detail, t, year)
            detail.pack(fill=tk.X, padx=12, pady=(0, 4), after=row)
            caret.config(text="▼")

        for widget in (row, caret, *row.winfo_children()):
            widget.bind("<Button-1>", _toggle)

    def _populate_transition_students(self, container, t, year):
        svc = self._get_journey_service()
        students = []
        if svc:
            try:
                students = svc.get_transition_students(
                    from_system=t.get("from_system"),
                    to_system=t.get("to_system"),
                    year=year,
                )
            except Exception:
                students = []

        if not students:
            tk.Label(
                container, text="No student detail recorded for this move.",
                font=("Segoe UI", 8), bg="#f7f9f9", fg=TEXT_MUTED,
            ).pack(anchor=tk.W, padx=24, pady=2)
            return

        for s in students:
            parts = [s["name"]]
            if s.get("occurred_at"):
                parts.append(str(s["occurred_at"])[:10])
            if s.get("reason"):
                parts.append(s["reason"])
            tk.Label(
                container, text="• " + "  —  ".join(parts),
                font=("Segoe UI", 9), bg="#f7f9f9", fg=TEXT_DARK, anchor=tk.W,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=24, pady=1)

    def _build_journey(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Student Journey Timeline",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Visualise a student's path across every system — Playgroup, "
                 "Nursery, Primary, Secondary, Sixth Form, College (FE), "
                 "Apprenticeships, Higher Apprenticeships and University.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Cohort-level progression funnel (aggregate across all students).
        self._build_cohort_flow(frame)

        # Divider before the single-student lookup.
        tk.Frame(frame, bg="#d5dbdb", height=1).pack(fill=tk.X, padx=24, pady=(8, 12))
        tk.Label(
            frame, text="Look Up an Individual Student",
            font=("Segoe UI", 15, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Search bar
        search_bar = tk.Frame(frame, bg=CONTENT_BG)
        search_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        search_var = tk.StringVar()
        tk.Entry(
            search_bar, textvariable=search_var, font=("Segoe UI", 12), width=30,
        ).pack(side=tk.LEFT, padx=(0, 8), ipady=4)

        timeline_frame = tk.Frame(frame, bg=CONTENT_BG)
        timeline_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))

        status_label = tk.Label(
            timeline_frame, text="Enter a student name or ID and click Search.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        status_label.pack(pady=8, anchor=tk.W)

        def _search_journey(*_args):
            query = search_var.get().strip()
            if not query or len(query) < 2:
                return
            # Clear previous timeline
            for w in timeline_frame.winfo_children():
                if w is not status_label:
                    w.destroy()
            status_label.config(text="Searching...")

            journey_svc = self._get_journey_service()
            if not journey_svc:
                status_label.config(text="Journey service unavailable.")
                return

            try:
                results = journey_svc.search_student(query)
            except Exception as exc:
                status_label.config(text=f"Search error: {exc}")
                return

            if not results:
                status_label.config(text="No students found.")
                return

            # Use first result to get full journey
            first = results[0]
            student_id = first.get("student_id", first.get("id", ""))
            system = first.get("system", "")

            try:
                journey = journey_svc.get_journey(student_id, system)
            except Exception:
                journey = None

            if not journey or not journey.get("stages"):
                status_label.config(
                    text=f"Found {first.get('name', '')} in {SYSTEM_LABELS.get(system, system)}, "
                         f"but no cross-system journey data available."
                )
                # Show a single stage card anyway
                self._draw_journey_card(
                    timeline_frame, system,
                    {"name": first.get("name", ""), "status": first.get("status", ""), "id": student_id},
                    is_last=True,
                )
                return

            stages = journey.get("stages", [])
            moves = journey.get("transitions", [])
            status_label.config(
                text=f"Journey for: {journey.get('name', first.get('name', ''))}  —  "
                     f"appears in {len(stages)} system(s) (by name); "
                     f"{len(moves)} recorded move(s)"
            )

            tk.Label(
                timeline_frame, text="Appears In (matched by name)",
                font=("Segoe UI", 11, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, pady=(4, 4))
            for i, stage in enumerate(stages):
                sys_key = stage.get("system", "")
                self._draw_journey_card(timeline_frame, sys_key, stage, is_last=(i == len(stages) - 1))

            # Authoritative recorded moves from the cross-system registry.
            # Distinct from the name-matched stages above, which is why the
            # counts can differ.
            tk.Label(
                timeline_frame, text=f"Recorded Moves ({len(moves)})",
                font=("Segoe UI", 11, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, pady=(12, 4))
            if moves:
                for m in moves:
                    line = f"  • {m['from_label']} → {m['to_label']}"
                    if m.get("occurred_at"):
                        line += f"   ({str(m['occurred_at'])[:10]})"
                    tk.Label(
                        timeline_frame, text=line, font=("Segoe UI", 9),
                        bg=CONTENT_BG, fg=TEXT_DARK, anchor=tk.W, justify=tk.LEFT,
                    ).pack(anchor=tk.W)
            else:
                tk.Label(
                    timeline_frame,
                    text="  No moves recorded in the registry for this student.",
                    font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
                ).pack(anchor=tk.W)

        tk.Button(
            search_bar, text="Search", font=("Segoe UI", 11), bg="#3498db", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=16, command=_search_journey,
        ).pack(side=tk.LEFT)

        search_bar.winfo_children()[0].bind("<Return>", _search_journey)

    def _draw_journey_card(self, parent, sys_key, stage, is_last=False):
        """Draw a single journey stage card with a connecting line."""
        color = SYSTEM_COLORS.get(sys_key, "#95a5a6")
        label = SYSTEM_LABELS.get(sys_key, sys_key.title())

        wrapper = tk.Frame(parent, bg=CONTENT_BG)
        wrapper.pack(fill=tk.X, pady=(0, 0))

        # Timeline dot and connector
        dot_frame = tk.Frame(wrapper, bg=CONTENT_BG, width=40)
        dot_frame.pack(side=tk.LEFT, fill=tk.Y)
        dot_frame.pack_propagate(False)

        dot_canvas = tk.Canvas(dot_frame, width=40, height=80, bg=CONTENT_BG, highlightthickness=0)
        dot_canvas.pack(fill=tk.BOTH, expand=True)
        dot_canvas.create_oval(12, 8, 28, 24, fill=color, outline=color)
        if not is_last:
            dot_canvas.create_line(20, 24, 20, 80, fill="#bdc3c7", width=2)

        # Card content
        card = tk.Frame(wrapper, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), pady=4)

        accent = tk.Frame(card, bg=color, height=4)
        accent.pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.X, padx=12, pady=8)

        tk.Label(
            body, text=label, font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W)

        info_parts = []
        if stage.get("name"):
            info_parts.append(f"Name: {stage['name']}")
        if stage.get("id") or stage.get("student_id"):
            info_parts.append(f"ID: {stage.get('student_id', stage.get('id', ''))}")
        if stage.get("status"):
            info_parts.append(f"Status: {stage['status']}")
        if stage.get("enrollment_date") or stage.get("enrolled_date"):
            dt = stage.get("enrollment_date") or stage.get("enrolled_date", "")
            info_parts.append(f"Enrolled: {str(dt)[:10]}")
        if stage.get("year_group"):
            info_parts.append(f"Year: {stage['year_group']}")

        if info_parts:
            tk.Label(
                body, text="  |  ".join(info_parts),
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED, wraplength=600, justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(2, 0))

        # Academic history
        for hist in stage.get("academic_history", []):
            tk.Label(
                body, text=f"  - {hist}",
                font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W)

    # ------------------------------------------------------------------
    # Section: Permission Matrix (Feature 8)
    # ------------------------------------------------------------------

    def _build_permissions(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Permission Matrix",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="View user roles across all education systems at a glance.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        tree_frame = tk.Frame(frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

        columns = ("username", "display_name", "nursery", "primary", "secondary", "sixth_form", "university")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=22)

        for col, heading, w in [
            ("username", "Username", 95),
            ("display_name", "Display Name", 120),
            ("nursery", "Nursery", 80),
            ("primary", "Primary", 80),
            ("secondary", "Secondary", 80),
            ("sixth_form", "Sixth Form", 80),
            ("university", "University", 80),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        all_users = []
        svc = self._get_admin_service()
        if svc:
            try:
                all_users = svc.get_all_users()
            except Exception:
                pass

        for u in all_users:
            sys_map = {}
            for s in u.get("systems", []):
                sys_map[s["system_key"]] = s["role"]
            tree.insert("", tk.END, values=(
                u.get("username", ""),
                u.get("display_name", ""),
                sys_map.get("nursery", "\u2014"),
                sys_map.get("primary", "\u2014"),
                sys_map.get("secondary", "\u2014"),
                sys_map.get("sixth_form", "\u2014"),
                sys_map.get("university", "\u2014"),
            ))

        if not all_users:
            tk.Label(
                frame, text="No user data available.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(padx=24, pady=8)

    # ------------------------------------------------------------------
    # Section: Backup / Restore (Feature 6)
    # ------------------------------------------------------------------

    def _build_backup(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Backup / Restore",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Create timestamped backups of system databases.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # Alert thresholds (Feature 7)
        tk.Label(
            frame, text="Health Alert Thresholds",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        threshold_frame = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        threshold_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

        self._alert_thresholds = getattr(self, "_alert_thresholds", {
            "max_db_size_mb": 500,
            "min_active_students": 1,
        })

        for i, (key, label, default) in enumerate([
            ("max_db_size_mb", "Max DB Size (MB)", 500),
            ("min_active_students", "Min Active Students", 1),
        ]):
            row = tk.Frame(threshold_frame, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(
                row, text=label + ":", font=("Segoe UI", 10), bg=CARD_BG, fg=TEXT_DARK, width=22, anchor=tk.W,
            ).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self._alert_thresholds.get(key, default)))
            ent = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=10)
            ent.pack(side=tk.LEFT, padx=4)
            ent._threshold_key = key
            ent._threshold_var = var

        def _save_thresholds():
            for child in threshold_frame.winfo_children():
                for ent in child.winfo_children():
                    if hasattr(ent, "_threshold_key"):
                        try:
                            self._alert_thresholds[ent._threshold_key] = int(ent._threshold_var.get())
                        except ValueError:
                            pass
            messagebox.showinfo("Saved", "Alert thresholds updated.")
            self._check_health_alerts(frame)

        tk.Button(
            threshold_frame, text="Save Thresholds", font=("Segoe UI", 9),
            bg="#2980b9", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=_save_thresholds,
        ).pack(padx=12, pady=8, anchor=tk.W)

        # Alert display area
        self._alerts_frame = tk.Frame(frame, bg=CONTENT_BG)
        self._alerts_frame.pack(fill=tk.X, padx=24, pady=(0, 12))
        self._check_health_alerts(frame)

        # Backup buttons per system
        tk.Label(
            frame, text="Database Backups",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(4, 6))

        for sys_key in SYSTEM_ORDER:
            sys_label = SYSTEM_LABELS[sys_key]
            color = SYSTEM_COLORS[sys_key]

            card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.pack(fill=tk.X, padx=24, pady=4)

            accent = tk.Frame(card, bg=color, width=6)
            accent.pack(side=tk.LEFT, fill=tk.Y)

            body = tk.Frame(card, bg=CARD_BG)
            body.pack(fill=tk.X, padx=12, pady=8)

            tk.Label(
                body, text=sys_label, font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(side=tk.LEFT)

            # Get DB info
            svc = self._get_admin_service()
            db_info = ""
            if svc:
                try:
                    cfg = svc.get_system_config(sys_key)
                    db_info = f"({cfg.get('db_size_mb', 0)} MB)"
                except Exception:
                    pass

            if db_info:
                tk.Label(
                    body, text=db_info, font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED,
                ).pack(side=tk.LEFT, padx=8)

            status_label = tk.Label(body, text="", font=("Segoe UI", 9), bg=CARD_BG, fg="#27ae60")
            status_label.pack(side=tk.RIGHT)

            def _make_backup(sk=sys_key, sl=status_label):
                svc2 = self._get_admin_service()
                if not svc2:
                    return
                try:
                    backup_path = svc2.backup_database(sk)
                    sl.config(text=f"Backed up: {backup_path.split('/')[-1]}", fg="#27ae60")
                except Exception as exc:
                    sl.config(text=f"Error: {exc}", fg="#e74c3c")

            tk.Button(
                body, text="Backup Now", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
                relief=tk.FLAT, cursor="hand2", padx=10, command=_make_backup,
            ).pack(side=tk.RIGHT, padx=(0, 8))

        # Auth DB backup
        card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=4)
        accent = tk.Frame(card, bg="#e74c3c", width=6)
        accent.pack(side=tk.LEFT, fill=tk.Y)
        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(body, text="Shared Auth Database", font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(
            side=tk.LEFT
        )
        auth_status = tk.Label(body, text="", font=("Segoe UI", 9), bg=CARD_BG, fg="#27ae60")
        auth_status.pack(side=tk.RIGHT)

        def _backup_auth():
            import shutil
            from pathlib import Path
            auth_path = Path(self._auth_db_path) if self._auth_db_path else None
            if not auth_path:
                try:
                    from education_system.shared.admin_portal.admin_service import _auth_db_path
                    auth_path = _auth_db_path()
                except Exception:
                    auth_status.config(text="Auth DB path unknown", fg="#e74c3c")
                    return
            if not auth_path.exists():
                auth_status.config(text="Auth DB not found", fg="#e74c3c")
                return
            backup = str(auth_path) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(str(auth_path), backup)
            auth_status.config(text=f"Backed up: {backup.split('/')[-1]}", fg="#27ae60")

        tk.Button(
            body, text="Backup Now", font=("Segoe UI", 9), bg="#e74c3c", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_backup_auth,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _check_health_alerts(self, parent_frame=None):
        """Check current health data against thresholds and show alerts."""
        alerts_frame = getattr(self, "_alerts_frame", None)
        if not alerts_frame:
            return
        for w in alerts_frame.winfo_children():
            w.destroy()

        thresholds = getattr(self, "_alert_thresholds", {})
        max_db = thresholds.get("max_db_size_mb", 500)
        min_students = thresholds.get("min_active_students", 1)

        svc = self._get_admin_service()
        if not svc:
            return

        alerts = []
        try:
            health = svc.get_system_health()
            for h in health:
                if h.get("db_size_mb", 0) > max_db:
                    alerts.append(
                        f"WARNING: {h['label']} DB size ({h['db_size_mb']} MB) exceeds threshold ({max_db} MB)"
                    )
                if h.get("student_count", 0) < min_students and h.get("db_exists"):
                    alerts.append(
                        f"WARNING: {h['label']} has only {h['student_count']} student(s) "
                        f"(threshold: {min_students})"
                    )
                if h.get("status") == "error":
                    alerts.append(f"ERROR: {h['label']} database has errors")
        except Exception:
            pass

        if alerts:
            for alert in alerts:
                color = "#e74c3c" if "ERROR" in alert else "#e67e22"
                tk.Label(
                    alerts_frame, text=alert, font=("Segoe UI", 9, "bold"),
                    bg=CONTENT_BG, fg=color, anchor=tk.W,
                ).pack(fill=tk.X, pady=1)
        else:
            tk.Label(
                alerts_frame, text="All systems within normal thresholds.",
                font=("Segoe UI", 9), bg=CONTENT_BG, fg="#27ae60",
            ).pack(anchor=tk.W)

    # ------------------------------------------------------------------
    # Section: Database Report (full PDF extract of every DB file)
    # ------------------------------------------------------------------

    def _open_path(self, path):
        """Open a file with the OS default application.

        Returns True if a handler launched successfully, False otherwise (e.g.
        no PDF viewer is registered on a headless Linux box — xdg-open then
        prints "No applications found for mimetype").
        """
        import sys
        import subprocess
        try:
            if sys.platform.startswith("darwin"):
                return subprocess.call(["open", path]) == 0
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
                return True
            # Linux: xdg-open exits non-zero when no handler is registered.
            return subprocess.call(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        except Exception:
            return False

    def _build_db_report(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Database Report",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Extract every database in the education system into a single PDF "
                 "report with summary charts, table inventories and sample data.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 14))

        # Discover databases and show what will be included.
        try:
            from education_system.shared.gui.db_report import (
                discover_databases, generate_database_report,
            )
            db_paths = discover_databases()
        except Exception as exc:
            tk.Label(
                frame, text=f"Report module unavailable: {exc}",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg="#c0392b",
            ).pack(anchor=tk.W, padx=24)
            return

        card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(0, 14))
        tk.Label(
            card, text=f"{len(db_paths)} database file(s) found:",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 2))
        for p in db_paths:
            try:
                size_kb = os.path.getsize(p) / 1024
            except OSError:
                size_kb = 0
            tk.Label(
                card, text=f"   •  {p.name}  ({size_kb:,.0f} KB)",
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED, anchor=tk.W,
            ).pack(anchor=tk.W, padx=12)
        tk.Frame(card, bg=CARD_BG, height=8).pack()

        # Options row.
        opts = tk.Frame(frame, bg=CONTENT_BG)
        opts.pack(fill=tk.X, padx=24, pady=(0, 8))
        tk.Label(
            opts, text="Max sample rows per table:",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT)
        rows_var = tk.StringVar(value="50")
        tk.Entry(opts, textvariable=rows_var, font=("Segoe UI", 10), width=6).pack(side=tk.LEFT, padx=6)

        # Progress + status.
        progress_var = tk.DoubleVar(value=0)
        status_var = tk.StringVar(value="Ready.")
        bar = ttk.Progressbar(frame, variable=progress_var, maximum=100, length=420)
        bar.pack(anchor=tk.W, padx=24, pady=(8, 2))
        tk.Label(
            frame, textvariable=status_var,
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24)

        state = {"running": False}

        def _on_progress(frac, msg):
            # Called from the worker thread — marshal onto the Tk main loop.
            self.after(0, lambda: (progress_var.set(frac * 100), status_var.set(msg)))

        def _done(result, err):
            state["running"] = False
            gen_btn.config(state=tk.NORMAL)
            if err is not None:
                status_var.set("Failed.")
                messagebox.showerror("Report failed", str(err))
                return
            progress_var.set(100)
            score = result.get("data_quality_score")
            issues = result.get("issues")
            extra = f" · quality {score}% · {issues} issue(s)" if score is not None else ""
            status_var.set(
                f"Done — {result['databases']} databases, {result['rows']:,} rows{extra}.")
            saved_at = result["output_path"]
            summary = (f"{result['databases']} databases · {result['rows']:,} rows · "
                       f"data-quality score {score}% ({issues} issues found)\n\n"
                       if score is not None else "\n")
            if messagebox.askyesno(
                "Report ready",
                f"Report saved to:\n{saved_at}\n\n{summary}Open it now?",
            ):
                if not self._open_path(saved_at):
                    # No PDF handler available (common on headless Linux).
                    messagebox.showinfo(
                        "Report saved",
                        "Couldn't find an application to open PDFs on this system.\n\n"
                        f"The report is saved here:\n{saved_at}")

        def _worker(path, max_rows):
            try:
                result = generate_database_report(
                    path, max_rows_per_table=max_rows, progress_cb=_on_progress)
                self.after(0, lambda: _done(result, None))
            except Exception as exc:  # noqa: BLE001 — surface any failure to the user
                self.after(0, lambda exc=exc: _done(None, exc))

        def _generate():
            if state["running"]:
                return
            from tkinter import filedialog
            default_name = f"edu_db_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            path = filedialog.asksaveasfilename(
                title="Save Database Report",
                defaultextension=".pdf",
                initialfile=default_name,
                filetypes=[("PDF document", "*.pdf")],
            )
            if not path:
                return
            try:
                max_rows = max(1, int(rows_var.get()))
            except (ValueError, TypeError):
                max_rows = 50
            state["running"] = True
            gen_btn.config(state=tk.DISABLED)
            progress_var.set(0)
            status_var.set("Starting…")
            import threading
            threading.Thread(target=_worker, args=(path, max_rows), daemon=True).start()

        gen_btn = tk.Button(
            frame, text="Generate PDF Report", font=("Segoe UI", 11, "bold"),
            bg="#1abc9c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2",
            padx=16, pady=8, command=_generate,
        )
        gen_btn.pack(anchor=tk.W, padx=24, pady=(12, 20))

    # ------------------------------------------------------------------
    # Section: Batch Operations (Feature 11)
    # ------------------------------------------------------------------

    def _build_batch(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Batch Operations",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Perform bulk changes across users and systems.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # Batch role change
        tk.Label(
            frame, text="Bulk Role Change",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        role_card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        role_card.pack(fill=tk.X, padx=24, pady=(0, 16))

        r1 = tk.Frame(role_card, bg=CARD_BG)
        r1.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(r1, text="System:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        batch_sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            r1, textvariable=batch_sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        r2 = tk.Frame(role_card, bg=CARD_BG)
        r2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(r2, text="Current Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(
            side=tk.LEFT
        )
        batch_from_var = tk.StringVar(value="student")
        ttk.Combobox(
            r2, textvariable=batch_from_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        r3 = tk.Frame(role_card, bg=CARD_BG)
        r3.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(r3, text="New Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        batch_to_var = tk.StringVar(value="staff")
        ttk.Combobox(
            r3, textvariable=batch_to_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        batch_result = tk.Label(role_card, text="", font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED)
        batch_result.pack(padx=12, pady=4, anchor=tk.W)

        def _do_batch_role():
            sys_key = batch_sys_var.get()
            from_role = batch_from_var.get()
            to_role = batch_to_var.get()
            if from_role == to_role:
                messagebox.showwarning("Validation", "Current and new roles must differ.")
                return
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                all_users = svc.get_all_users(system=sys_key, role=from_role)
                if not all_users:
                    batch_result.config(text=f"No users found with role '{from_role}' in {sys_key}.", fg="#e67e22")
                    return
                if not messagebox.askyesno(
                    "Confirm Batch Role Change",
                    f"Change {len(all_users)} user(s) from '{from_role}' to '{to_role}' in {sys_key}?",
                ):
                    return
                count = 0
                for u in all_users:
                    new_sr = []
                    for s in u.get("systems", []):
                        if s["system_key"] == sys_key and s["role"] == from_role:
                            new_sr.append({"system_key": sys_key, "role": to_role})
                        else:
                            new_sr.append(s)
                    svc.update_user_systems(u["id"], new_sr)
                    count += 1
                batch_result.config(text=f"Updated {count} user(s) to role '{to_role}'.", fg="#27ae60")
            except Exception as exc:
                batch_result.config(text=f"Error: {exc}", fg="#e74c3c")

        tk.Button(
            role_card, text="Apply Batch Role Change", font=("Segoe UI", 10),
            bg="#e67e22", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_do_batch_role,
        ).pack(padx=12, pady=(0, 12), anchor=tk.W)

        # Batch deactivation
        tk.Label(
            frame, text="Bulk Deactivation",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        deact_card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        deact_card.pack(fill=tk.X, padx=24, pady=(0, 16))

        d1 = tk.Frame(deact_card, bg=CARD_BG)
        d1.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(d1, text="System:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        deact_sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            d1, textvariable=deact_sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        d2 = tk.Frame(deact_card, bg=CARD_BG)
        d2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(d2, text="Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        deact_role_var = tk.StringVar(value="student")
        ttk.Combobox(
            d2, textvariable=deact_role_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        deact_result = tk.Label(deact_card, text="", font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED)
        deact_result.pack(padx=12, pady=4, anchor=tk.W)

        def _do_batch_deactivate():
            sys_key = deact_sys_var.get()
            role = deact_role_var.get()
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                users = svc.get_all_users(system=sys_key, role=role)
                active_users = [u for u in users if u.get("is_active")]
                if not active_users:
                    deact_result.config(text="No active users match this filter.", fg="#e67e22")
                    return
                if not messagebox.askyesno(
                    "Confirm Bulk Deactivation",
                    f"Deactivate {len(active_users)} active user(s) with role '{role}' in {sys_key}?",
                ):
                    return
                for u in active_users:
                    svc.deactivate_user(u["id"])
                deact_result.config(text=f"Deactivated {len(active_users)} user(s).", fg="#27ae60")
            except Exception as exc:
                deact_result.config(text=f"Error: {exc}", fg="#e74c3c")

        tk.Button(
            deact_card, text="Deactivate All Matching", font=("Segoe UI", 10),
            bg="#e74c3c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_do_batch_deactivate,
        ).pack(padx=12, pady=(0, 12), anchor=tk.W)

    # ------------------------------------------------------------------
    # Section: Active Sessions
    # ------------------------------------------------------------------

    def _build_sessions(self):
        tk.Label(
            self._content_frame, text="Active Sessions",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="View and manage active user sessions across all systems.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))

        columns = ("username", "user_id", "token_preview", "created_at", "expires_at")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        for col, heading, w in [
            ("username", "Username", 140),
            ("user_id", "User ID", 80),
            ("token_preview", "Token", 120),
            ("created_at", "Created", 160),
            ("expires_at", "Expires", 160),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        sessions = []
        svc = self._get_admin_service()
        if svc:
            try:
                sessions = svc.get_active_sessions()
            except Exception:
                pass

        for s in sessions:
            tree.insert("", tk.END, values=(
                s.get("username", ""),
                s.get("user_id", ""),
                s.get("token_preview", ""),
                str(s.get("created_at", ""))[:19],
                str(s.get("expires_at", ""))[:19],
            ))

        if not sessions:
            tk.Label(
                self._content_frame, text="No active sessions found.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(pady=8)

        # Action buttons
        action_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        action_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        def _force_logout():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a session first.")
                return
            vals = tree.item(sel[0], "values")
            user_id = vals[1]
            username = vals[0]
            if not messagebox.askyesno(
                "Confirm Force Logout",
                f"Force logout all sessions for '{username}' (user_id={user_id})?",
            ):
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.force_logout_user(int(user_id))
                    messagebox.showinfo("Done", f"All sessions for '{username}' have been terminated.")
                    self._show_section("sessions")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        tk.Button(
            action_bar, text="Force Logout Selected User", font=("Segoe UI", 10),
            bg="#e74c3c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_force_logout,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            action_bar, text="Refresh", font=("Segoe UI", 10),
            bg="#3498db", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=lambda: self._show_section("sessions"),
        ).pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Section: Quick Launch
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Section: Password Policy
    # ------------------------------------------------------------------

    def _build_password_policy(self):
        """Embed the standalone Password Reset Dashboard, bound to this
        session's shared auth object."""
        if self.auth is None or not hasattr(self.auth, "get_password_policy_overview"):
            self._show_error(
                "Password policy controls are unavailable (auth service missing)."
            )
            return
        try:
            from education_system.shared.gui.password_reset_dashboard import (
                PasswordResetDashboardFrame,
            )
            dash = PasswordResetDashboardFrame(self._content_frame, self.auth)
            dash.pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            self._show_error(f"Could not load the Password Reset Dashboard: {exc}")

    def _build_launch(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Quick Launch",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Launch an individual education system. You will enter as superadmin.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 24))

        # Grid of large launch buttons (3 columns → a 3×3 grid for the 9 systems)
        grid = tk.Frame(frame, bg=CONTENT_BG)
        grid.pack(padx=40, pady=(0, 30))
        _LAUNCH_COLS = 3

        launch_configs = [
            ("nursery", "Nursery", SYSTEM_COLORS["nursery"], "Birth - 5 years\nEYFS / Early Years"),
            ("primary", "Primary School", "#e67e22", "Reception - Year 6\nEYFS / KS1 / KS2"),
            ("secondary", "Secondary School", "#8e44ad", "Years 7 - 11\nKS3 / KS4 / GCSE"),
            ("sixth_form", "Sixth Form College", "#27ae60", "Years 12 - 13\nA-Levels / BTEC / T-Levels"),
            ("university", "University", "#2980b9", "Undergraduate & Postgraduate\nDegrees / Research"),
        ]

        for i, (sys_key, label, color, desc) in enumerate(launch_configs):
            row, col = divmod(i, _LAUNCH_COLS)

            btn_frame = tk.Frame(grid, bg=color, cursor="hand2")
            btn_frame.grid(row=row, column=col, padx=14, pady=14, sticky=tk.NSEW)
            grid.columnconfigure(col, weight=1)
            grid.rowconfigure(row, weight=1)

            inner = tk.Frame(btn_frame, bg=color)
            inner.pack(padx=3, pady=3, fill=tk.BOTH, expand=True)

            name_lbl = tk.Label(
                inner,
                text=label,
                font=("Segoe UI", 18, "bold"),
                bg=color,
                fg=TEXT_LIGHT,
            )
            name_lbl.pack(padx=30, pady=(30, 4))

            desc_lbl = tk.Label(
                inner,
                text=desc,
                font=("Segoe UI", 10),
                bg=color,
                fg="#e0e0e0",
                justify=tk.CENTER,
            )
            desc_lbl.pack(padx=30, pady=(0, 6))

            launch_lbl = tk.Label(
                inner,
                text="Click to Launch  \u2192",
                font=("Segoe UI", 10, "bold"),
                bg=color,
                fg=TEXT_LIGHT,
            )
            launch_lbl.pack(padx=30, pady=(4, 30))

            # Bind click to all widgets in the button frame
            def _make_handler(sk=sys_key):
                return lambda e: self._launch_system(sk)

            handler = _make_handler()
            for widget in (btn_frame, inner, name_lbl, desc_lbl, launch_lbl):
                widget.bind("<Button-1>", handler)

            # Hover effect
            def _on_enter(e, frm=btn_frame, c=color):
                try:
                    # Lighten the colour slightly
                    r = int(c[1:3], 16)
                    g = int(c[3:5], 16)
                    b = int(c[5:7], 16)
                    r = min(255, r + 20)
                    g = min(255, g + 20)
                    b = min(255, b + 20)
                    lighter = f"#{r:02x}{g:02x}{b:02x}"
                    frm.configure(bg=lighter)
                    for child in frm.winfo_children():
                        child.configure(bg=lighter)
                        for grandchild in child.winfo_children():
                            grandchild.configure(bg=lighter)
                except Exception:
                    pass

            def _on_leave(e, frm=btn_frame, c=color):
                try:
                    frm.configure(bg=c)
                    for child in frm.winfo_children():
                        child.configure(bg=c)
                        for grandchild in child.winfo_children():
                            grandchild.configure(bg=c)
                except Exception:
                    pass

            btn_frame.bind("<Enter>", _on_enter)
            btn_frame.bind("<Leave>", _on_leave)

    def _launch_system(self, system_key):
        """Set launch attributes and close the dashboard."""
        self._stop_auto_refresh()
        self.launch_system = system_key
        self.launch_role = "admin"
        self.destroy()

    # ------------------------------------------------------------------
    # About dialog
    # ------------------------------------------------------------------

    def _show_about(self):
        dlg = tk.Toplevel(self)
        dlg.title("About")
        dlg.geometry("380x220")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(
            dlg, text="Education System", font=("Segoe UI", 16, "bold"),
        ).pack(pady=(20, 4))
        tk.Label(
            dlg, text="Super Admin Dashboard v7.23.0", font=("Segoe UI", 11),
        ).pack(pady=(0, 8))
        tk.Label(
            dlg,
            text=(
                "Unified management console for Nursery, Primary School,\n"
                "Secondary School, Sixth Form College, and University.\n\n"
                "Python / tkinter / SQLite"
            ),
            font=("Segoe UI", 9), fg=TEXT_MUTED, justify=tk.CENTER,
        ).pack(pady=(0, 12))
        tk.Button(
            dlg, text="Close", font=("Segoe UI", 10), bg="#3498db", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, cursor="hand2", command=dlg.destroy,
        ).pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Auto-refresh (Feature 5)
    # ------------------------------------------------------------------

    def _start_auto_refresh(self):
        """Start periodic refresh of the current section."""
        self._do_auto_refresh()

    def _do_auto_refresh(self):
        """Refresh the current dashboard/health section and schedule next tick."""
        # Guard against callback firing after widget destruction
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        # Skip refresh if a modal dialog is open
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel) and child.winfo_exists():
                self._refresh_timer_id = self.after(5_000, self._do_auto_refresh)
                return
        if self._current_section in ("dashboard", "health"):
            try:
                self._show_section(self._current_section)
            except Exception:
                pass
        # Schedule next refresh
        self._refresh_timer_id = self.after(self._refresh_interval_ms, self._do_auto_refresh)

    def _stop_auto_refresh(self):
        """Cancel the auto-refresh timer."""
        if self._refresh_timer_id is not None:
            self.after_cancel(self._refresh_timer_id)
            self._refresh_timer_id = None

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def _on_logout(self):
        self._stop_auto_refresh()
        self.logged_out = True
        self.launch_system = None
        self.launch_role = None
        # Try to end the session
        if self.auth and self.user_info:
            try:
                token = self.user_info.get("session_token") or self.user_info.get("token")
                if token and hasattr(self.auth, "logout"):
                    self.auth.logout(token)
            except Exception:
                pass
        self.destroy()

    def _on_close(self):
        self._stop_auto_refresh()
        self.launch_system = None
        self.launch_role = None
        self.destroy()

    def _on_switch_to_cli(self):
        """Close the dashboard and signal dispatch to re-enter as CLI superadmin."""
        self._stop_auto_refresh()
        self.switch_to_cli = True
        self.launch_system = None
        self.launch_role = None
        self.destroy()

    def _on_shutdown(self):
        """Confirm, then signal dispatch to exit the whole application."""
        if not messagebox.askyesno(
            "Shut down",
            "Shut down the Education System entirely?\n\n"
            "This closes the application for all interfaces, not just logout.",
            icon="warning",
            default="no",
            parent=self,
        ):
            return
        self._stop_auto_refresh()
        self.shutdown = True
        self.launch_system = None
        self.launch_role = None
        # End the session on the way out, like logout does.
        if self.auth and self.user_info:
            try:
                token = self.user_info.get("session_token") or self.user_info.get("token")
                if token and hasattr(self.auth, "logout"):
                    self.auth.logout(token)
            except Exception:
                pass
        self.destroy()

    def destroy(self):
        """Override destroy to ensure auto-refresh is always cancelled."""
        self._stop_auto_refresh()
        super().destroy()
