"""The superadmin dashboard window: shell, navigation and lifecycle.

Each sidebar section lives in its own mixin under ``sections/``.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.i18n import _t
from education_system.platform.delivery.gui.superadmin_dashboard.linked_sections import (
    LINKED_SECTIONS,
)
from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    HEADER_BG,
    SIDEBAR_BG,
    SIDEBAR_BTN,
    SIDEBAR_BTN_ACTIVE,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_LIGHT,
    TEXT_MUTED,
)
from education_system.platform.delivery.gui.superadmin_dashboard.linked_sections import LinkedPlatformSectionsMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.analytics import AnalyticsMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.audit import AuditMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.backup import BackupMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.batch import BatchMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.database_report import DatabaseReportMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.health import HealthMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.journey import JourneyMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.launch import LaunchMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.misconduct import MisconductMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.notifications import NotificationsMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.overview import OverviewMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.search import SearchMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.security import SecurityMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.sessions import SessionsMixin
from education_system.platform.delivery.gui.superadmin_dashboard.sections.users import UsersMixin
from education_system.platform.delivery.gui.superadmin_dashboard.widgets import WidgetsMixin


class SuperAdminDashboard(
    LinkedPlatformSectionsMixin,
    OverviewMixin,
    HealthMixin,
    UsersMixin,
    AnalyticsMixin,
    MisconductMixin,
    SecurityMixin,
    NotificationsMixin,
    SearchMixin,
    AuditMixin,
    JourneyMixin,
    BackupMixin,
    DatabaseReportMixin,
    BatchMixin,
    SessionsMixin,
    LaunchMixin,
    WidgetsMixin,
    tk.Tk,
):
    """Standalone top-level window for superadmin management.

    The cross-system sections (tasks, Learner 360, transfer and event
    monitors, registry, identity, reports, boards) come from
    :class:`LinkedPlatformSectionsMixin`.
    """

    def __init__(self, user_info, auth, auth_db_path=None):
        super().__init__()

        # Public attributes read by python -m education_system after the window closes
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
        # Run the shared bus consumers (notifications, webhooks, calendar)
        # for every system while the console is open, so a transfer into a
        # system nobody has launched still reaches its staff.
        try:
            from education_system.platform.integrations.external.bus_drainer import (
                start_platform_drainer,
            )
            start_platform_drainer(db_path=auth_db_path)
        except Exception:
            pass
        # Wait until the root window is visible before presenting a modal.
        self.after(350, self._show_locked_account_alert)

    # ------------------------------------------------------------------
    # Service accessors (lazy imports)
    # ------------------------------------------------------------------

    def _get_admin_service(self):
        if self._admin_service is None:
            try:
                from education_system.platform.delivery.portals.admin.admin_service import AdminService
                self._admin_service = AdminService(
                    auth_db=self._auth_db_path
                )
            except Exception:
                return None
        return self._admin_service

    def _get_analytics_service(self):
        if self._analytics_service is None:
            try:
                from education_system.platform.features.analytics.analytics_service import AnalyticsService
                self._analytics_service = AnalyticsService()
            except Exception:
                return None
        return self._analytics_service

    def _get_notification_service(self):
        if self._notification_service is None:
            try:
                from education_system.platform.features.notifications.service import (
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
                from education_system.platform.cross_system.journey_service import JourneyService
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
            *((key, _t(f"nav.{key}", label)) for key, label in LINKED_SECTIONS),
            ("permissions", _t("nav.permissions", "Permission Matrix")),
            ("password_policy", _t("nav.password_policy", "Password Policy")),
            ("security_training", _t("nav.security_training", "ICT Security Training")),
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
            "security_training": self._build_security_training,
            "audit": self._build_audit,
            "backup": self._build_backup,
            "dbreport": self._build_db_report,
            "batch": self._build_batch,
            "sessions": self._build_sessions,
            "launch": self._build_launch,
        }
        builders.update(self._linked_builders())

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
                "Unified management console for all "
                f"{len(SYSTEM_ORDER)} education systems:\n"
                + ", ".join(SYSTEM_LABELS.get(k, k) for k in SYSTEM_ORDER)
                + ".\n\n"
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
