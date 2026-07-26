import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter.font as tkFont
from tkinter import scrolledtext
from datetime import datetime, timedelta
import threading
import queue
import json
import os
from typing import Dict, Any, Optional, List, Tuple, Callable
import logging
import platform
import re
import uuid
import hashlib
import secrets
from functools import wraps
from urllib.parse import urlparse

from education_system.systems.university.infrastructure.i18n import (
    get_text as _, init_i18n, get_current_language, get_current_language_name
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector
init_i18n()

# Import the calendar functionality from modular package
from education_system.systems.university.infrastructure.database.db import get_connection as get_db_connection
from education_system.systems.university.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
from education_system.systems.university.domain.academics.services.academic_calendar.config import CalendarConfig
from education_system.systems.university.domain.academics.services.academic_calendar.exceptions import (
    CalendarError, ValidationError, DatabaseError, PermissionError,
)
from education_system.systems.university.domain.academics.services.academic_calendar.cli import (
    display_academic_calendar_menu, handle_add_event, handle_update_event,
    handle_delete_event, handle_view_calendar, handle_export_calendar,
    auth, set_auth,
)

# Import central auth system
try:
    from education_system.systems.university.infrastructure.auth import get_global_auth
    CENTRAL_AUTH_AVAILABLE = True
except ImportError:
    get_global_auth = None  # type: ignore
    CENTRAL_AUTH_AVAILABLE = False

# Import trip management GUI
try:
    from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui import TripManagementGUI
    from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui.trip_dialogs import (
        TripDetailsDialog, CreateTripDialog, TripSelectionDialog
    )
    from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui.registration_dialogs import (
        RegisterForTripDialog
    )
    from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui.calendar_dialogs import (
        CreateCalendarEventDialog
    )
    TRIP_GUI_AVAILABLE = True
except ImportError:
    TRIP_GUI_AVAILABLE = False

# Import trip management service for trip-calendar links
try:
    from education_system.systems.university.domain.operations.campus.mobility.services import trip_management
    TRIP_MANAGEMENT_AVAILABLE = True
except ImportError:
    TRIP_MANAGEMENT_AVAILABLE = False

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Configure logging for GUI
gui_logger = logging.getLogger(__name__)

# Import mixin classes for modular functionality
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dashboard import DashboardMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.calendar_view import CalendarViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.events_view import EventsViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.academic_view import AcademicViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.menu_actions import MenuActionsMixin

# Import dialog classes
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_event import (
    AddEventDialog, EditEventDialog, EventDetailsDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_academic import (
    AddAcademicYearDialog, AddSemesterDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_admin import (
    SystemMaintenanceDialog, AuditLogsDialog, SettingsDialog,
    TimezoneSettingsDialog, NotificationSettingsDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_resources import (
    ResourceManagementDialog, CourseManagementDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_categories import (
    EventCategoriesDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_recurring import (
    RecurringEventDialog, RecurringEventsDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_reports import (
    ReportsDialog, DataVisualizationDialog, ProjectMilestonesDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_search import (
    AdvancedSearchDialog
)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_misc import (
    ExportDialog, ImportCalendarDialog, CalendarSyncDialog,
    ImportHolidaysDialog, BulkOperationsDialog, HelpDialog, AboutDialog
)

# ============================================================================
# MAIN CALENDAR GUI CLASS
# ============================================================================


class CalendarGUI(DashboardMixin, CalendarViewMixin, EventsViewMixin, AcademicViewMixin, MenuActionsMixin):
    def __init__(self, auth_manager=None, parent_window=None):
        self.auth_manager = auth_manager
        self.calendar_manager = None
        self.parent_window = parent_window
        self.style = None

        # GUI components
        self.main_frame = None
        self.sidebar = None
        self.content_area = None
        self.status_bar = None

        # Data storage
        self.current_events = []
        self.current_view = "calendar"

        # Threading for long operations
        self.task_queue = queue.Queue()
        self._task_after_id = None
        # Authoritative stop signal for the after() poll loop. Using a plain
        # flag (rather than after_cancel) avoids Tkinter deleting the callback
        # command out from under an already-queued timer, which surfaces as a
        # Tcl "invalid command name ...process_tasks" background error.
        self._closing = False

        # Initialize GUI
        self._setup_gui()
        self._setup_calendar_manager()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth_manager:
                if hasattr(self.auth_manager, 'current_user') and self.auth_manager.current_user:
                    role = self.auth_manager.current_user.get('role', '').lower()
                    return role
                elif hasattr(self.auth_manager, 'user_role'):
                    return self.auth_manager.user_role.lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def navigate_to_date(self, iso_date):
        """Switch to the events list and select event(s) on the given date.

        Matches single-day events (Date == iso_date) and multi-day events
        whose range covers iso_date. Returns True if any rows matched. If
        nothing matches, falls back to seeding the search box with the
        date so the user can see they're in the right place.
        """
        if not iso_date:
            return False
        try:
            self._show_manage_events()
        except Exception:
            return False
        tree = getattr(self, 'events_tree', None)
        if tree is None:
            return False
        matches = []
        for item in tree.get_children():
            try:
                vals = tree.item(item, 'values')
                start = str(vals[1]) if len(vals) > 1 else ''
                end = str(vals[2]) if len(vals) > 2 else ''
                if start == iso_date:
                    matches.append(item)
                elif start and end and start <= iso_date <= end:
                    matches.append(item)
            except Exception:
                continue
        if not matches:
            if hasattr(self, 'search_var'):
                try:
                    self.search_var.set(iso_date)
                    if hasattr(self, '_search_events'):
                        self._search_events()
                except Exception:
                    pass
            return False
        try:
            tree.selection_set(matches)
            tree.see(matches[0])
            tree.focus(matches[0])
        except Exception:
            pass
        # When exactly one event matches, jump straight to its details
        # dialog — the user clearly meant that one. For multi-match days
        # leave selection alone so they can pick.
        if len(matches) == 1 and hasattr(self, '_view_event_details'):
            try:
                self._view_event_details()
            except Exception:
                pass
        return True

    def init_calendar_database():
        """Initialize the academic calendar database tables"""
        try:
            conn = get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()

            print("🗓️ Initializing academic calendar database...")

            # Create academic_years table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_years (
                id TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                date_added TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0
            )
            ''')

            # Create semesters table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                academic_year_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                date_added TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                FOREIGN KEY (academic_year_id) REFERENCES academic_years (id)
            )
            ''')

            # Create event_categories table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#2196F3',
                icon TEXT DEFAULT '📅',
                created_at TEXT NOT NULL,
                is_system BOOLEAN DEFAULT 0
            )
            ''')

            # Create events table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                event_type TEXT DEFAULT 'Academic',
                category_id INTEGER,
                date TEXT,
                date_start TEXT,
                date_end TEXT,
                all_day BOOLEAN DEFAULT 1,
                location TEXT,
                academic_year_id TEXT,
                semester_id INTEGER,
                created_by TEXT,
                date_added TEXT NOT NULL,
                last_modified TEXT,
                is_recurring BOOLEAN DEFAULT 0,
                recurrence_rule TEXT,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES event_categories (id),
                FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                FOREIGN KEY (semester_id) REFERENCES semesters (id)
            )
            ''')

            # Create event_notifications table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                user_id TEXT,
                notification_type TEXT NOT NULL,
                send_at TEXT NOT NULL,
                sent BOOLEAN DEFAULT 0,
                sent_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
            ''')

            # Create calendar_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_type TEXT NOT NULL,
                resource_id TEXT,
                granted_by TEXT,
                granted_at TEXT NOT NULL,
                expires_at TEXT
            )
            ''')

            # Create calendar_audit_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                old_values TEXT,
                new_values TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT
            )
            ''')

            # Insert default event categories
            default_categories = [
                ('Academic', 'Academic events and deadlines', '#2196F3', '📚', 1),
                ('Holiday', 'Holidays and breaks', '#4CAF50', '🎉', 1),
                ('Administrative', 'Administrative events', '#FF9800', '📋', 1),
                ('Social', 'Social events and activities', '#E91E63', '🎊', 1),
                ('Sports', 'Sports and athletic events', '#9C27B0', '⚽', 1),
                ('Trip', 'Educational trips and excursions', '#00BCD4', '🎒', 1),
                ('Deadline', 'Important deadlines', '#F44336', '⏰', 1),
                ('Meeting', 'Meetings and conferences', '#795548', '🤝', 1)
            ]

            for name, desc, color, icon, is_system in default_categories:
                cursor.execute('''
                INSERT OR IGNORE INTO event_categories
                (name, description, color, icon, created_at, is_system)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, desc, color, icon, datetime.now().isoformat(), is_system))

            conn.commit()
            conn.close()

            print("✅ Academic calendar database initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize calendar database: {e}")
            logging.error(f"Calendar database initialization failed: {e}")
            return False

    def _setup_gui(self):
        """Initialize the main GUI"""
        if self.parent_window:
            self.root = self.parent_window
        else:
            self.root = tk.Tk()
            self.root.title(_("academic_calendar.title"))
            self.root.geometry("1400x900")
            self.root.minsize(1000, 600)

        # Set icon (if available)
        try:
            self.root.iconname("📅")
        except Exception as e:
            gui_logger.debug(f"Failed to set window icon: {e}")

        # Configure style. ttk.Style is process-global; only switch
        # themes when this window owns the Tk root, otherwise inherit
        # the parent's theme so it isn't restyled.
        self.style = ttk.Style()
        self._previous_theme = self.style.theme_use()
        if self.parent_window is None:
            try:
                self.style.theme_use('clam')
            except tk.TclError:
                pass
            self.root.bind(
                "<Destroy>",
                lambda _e, p=self._previous_theme, s=self.style: (
                    s.theme_use(p) if _e.widget is self.root else None
                ),
                add="+",
            )

        # Configure colors and fonts
        self._configure_styles()

        # Create main layout
        self._create_layout()

        # Setup menu bar
        self._create_menu_bar()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        # Start task processor
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_task_processor()

    def _configure_styles(self):
        """Configure custom styles for the GUI"""
        # Colors
        bg_color = '#f0f0f0'
        accent_color = '#2E86C1'
        success_color = '#27AE60'
        warning_color = '#F39C12'
        error_color = '#E74C3C'

        # Configure styles
        self.style.configure('Sidebar.TFrame', background='#34495E')
        self.style.configure('SidebarButton.TButton',
                           background='#34495E',
                           foreground='white',
                           borderwidth=0,
                           # Match the button background so the focus ring is
                           # invisible. "none" is not a valid Tk color and
                           # raised: Tk background error: unknown color name "none".
                           focuscolor='#34495E')
        self.style.map('SidebarButton.TButton',
                      background=[('active', '#5D6D7E')])

        self.style.configure('Header.TLabel',
                           font=('Arial', 16, 'bold'),
                           background=bg_color)

        self.style.configure('Success.TLabel', foreground=success_color)
        self.style.configure('Warning.TLabel', foreground=warning_color)
        self.style.configure('Error.TLabel', foreground=error_color)

    def _create_layout(self):
        """Create the main layout structure"""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar = ttk.Frame(self.main_frame, style='Sidebar.TFrame', width=250)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Content area
        self.content_area = ttk.Frame(self.main_frame)
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create sidebar content
        self._create_sidebar()

        # Create status bar
        self._create_status_bar()

        # Don't show dashboard here - it will be shown after calendar_manager is initialized

    def _create_sidebar(self):
        """Create the sidebar navigation with scrollable content"""
        # Logo/Title
        title_frame = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = ttk.Label(title_frame, text=_("academic_calendar.sidebar.title"),
                               font=('Arial', 18, 'bold'),
                               background='#34495E', foreground='white')
        title_label.pack()

        # Create scrollable frame for navigation
        # Main container for scrollable area
        scroll_container = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        scroll_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for scrolling
        canvas = tk.Canvas(scroll_container, bg='#34495E', highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Sidebar.TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Navigation buttons in scrollable frame
        nav_frame = ttk.Frame(scrollable_frame, style='Sidebar.TFrame')
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Updated button definitions with new features
        nav_buttons = [
            (_("academic_calendar.nav.dashboard"), self._show_dashboard),
            (_("academic_calendar.nav.view_calendar"), self._show_calendar_view),
            (_("academic_calendar.nav.add_event"), self._show_add_event),
            (_("academic_calendar.nav.manage_events"), self._show_manage_events),
            (_("academic_calendar.nav.recurring_events"), self._show_create_recurring_event),
            (_("academic_calendar.nav.advanced_search"), self._show_advanced_search),
            (_("academic_calendar.nav.academic_years"), self._show_academic_years),
            (_("academic_calendar.nav.semesters"), self._show_semesters),
            (_("academic_calendar.nav.resources"), self._show_resource_management),
            (_("academic_calendar.nav.courses"), self._show_course_management),
            (_("academic_calendar.nav.categories_tags"), self._show_event_categories),
            (_("academic_calendar.nav.reports"), self._show_reports),
            (_("academic_calendar.nav.visualizations"), self._show_data_visualization),
            (_("academic_calendar.nav.milestones"), self._show_project_milestones),
            (_("academic_calendar.nav.notifications"), self._show_notification_settings),
            (_("academic_calendar.nav.timezone"), self._show_timezone_settings),
            (_("academic_calendar.nav.export"), self._show_export),
            (_("academic_calendar.nav.system"), self._show_system_backup),
            (_("academic_calendar.nav.audit_logs"), self._show_audit_logs),
            (_("academic_calendar.nav.settings"), self._show_settings),
        ]

        # Add trip management buttons if available
        if TRIP_GUI_AVAILABLE:
            nav_buttons.append(
                (_("academic_calendar.nav.trip_manager", default="\U0001f3d5 Trip Manager"), self._open_trip_manager))
            nav_buttons.append(
                (_("academic_calendar.nav.trip_calendar_event", default="\U0001f517 Trip Calendar Event"), self._create_trip_calendar_event))
            nav_buttons.append(
                (_("academic_calendar.nav.trip_links", default="\U0001f4cb Trip-Calendar Links"), self._view_trip_calendar_links))

        # Add buttons if user has permissions
        if self.auth_manager and self.auth_manager.current_user:
            for text, command in nav_buttons:
                if self._has_permission_for_button(text):
                    btn = ttk.Button(nav_frame, text=text,
                                   command=command,
                                   style='SidebarButton.TButton')
                    btn.pack(fill=tk.X, pady=2)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # Bind mouse wheel events
        canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        canvas.bind("<Button-4>", _on_mousewheel_linux)  # Linux
        canvas.bind("<Button-5>", _on_mousewheel_linux)  # Linux

        # User info at bottom (fixed position)
        user_frame = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        user_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        if self.auth_manager and self.auth_manager.current_user:
            user_text = f"👤 {self.auth_manager.current_user.get('username', 'User')}\n({self.auth_manager.current_user.get('role', 'user')})"
            user_label = ttk.Label(user_frame, text=user_text,
                                 background='#34495E', foreground='white',
                                 font=('Arial', 9))
            user_label.pack()

        # Backward compatibility button (fixed position)
        compat_btn = ttk.Button(user_frame, text=_("academic_calendar.nav.cli_mode"),
                              command=self._launch_cli_mode,
                              style='SidebarButton.TButton')
        compat_btn.pack(fill=tk.X, pady=(10, 0))

    def _create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text=_("academic_calendar.status.ready"))
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)

        # Progress bar for long operations
        self.progress_bar = ttk.Progressbar(self.status_bar, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)

    def _create_menu_bar(self):
        """Create menu bar with role-based access"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("academic_calendar.menu.file"), menu=file_menu)

        # Admin and Staff can export/import
        if is_admin or is_staff:
            file_menu.add_command(label=_("academic_calendar.menu.export_calendar"), command=self._show_export)
            file_menu.add_command(label=_("academic_calendar.menu.import_calendar"), command=self._import_calendar)
            file_menu.add_separator()

        # Admin only - Database backup/restore
        if is_admin:
            file_menu.add_command(label=_("academic_calendar.menu.backup_database"), command=self._backup_database)
            file_menu.add_command(label=_("academic_calendar.menu.restore_database"), command=self._restore_database)
            file_menu.add_separator()

        file_menu.add_command(label=_("academic_calendar.menu.exit"), command=self.root.quit)

        # Events menu
        events_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("academic_calendar.menu.events"), menu=events_menu)

        # Admin and Staff can add/manage events
        if is_admin or is_staff:
            events_menu.add_command(label=_("academic_calendar.menu.add_event"), command=self._show_add_event)
            events_menu.add_command(label=_("academic_calendar.menu.recurring_event"), command=self._show_create_recurring_event)

        # Everyone can search
        events_menu.add_command(label=_("academic_calendar.menu.advanced_search"), command=self._show_advanced_search)

        # Admin and Staff can manage categories
        if is_admin or is_staff:
            events_menu.add_separator()
            events_menu.add_command(label=_("academic_calendar.menu.categories_tags"), command=self._show_event_categories)

        # Resources menu - Admin and Staff only
        if is_admin or is_staff:
            resources_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("academic_calendar.menu.resources"), menu=resources_menu)
            resources_menu.add_command(label=_("academic_calendar.menu.manage_resources"), command=self._show_resource_management)
            resources_menu.add_command(label=_("academic_calendar.menu.manage_courses"), command=self._show_course_management)
            resources_menu.add_command(label=_("academic_calendar.menu.project_milestones"), command=self._show_project_milestones)

        # Trips menu (if trip management GUI is available)
        if TRIP_GUI_AVAILABLE:
            trips_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("academic_calendar.menu.trips", default="Trips"), menu=trips_menu)
            trips_menu.add_command(
                label=_("academic_calendar.menu.open_trip_manager", default="Open Trip Manager"),
                command=self._open_trip_manager)
            trips_menu.add_separator()
            if is_admin or is_staff:
                trips_menu.add_command(
                    label=_("academic_calendar.menu.create_trip_event", default="Create Calendar Event for Trip"),
                    command=self._create_trip_calendar_event)
            trips_menu.add_command(
                label=_("academic_calendar.menu.view_trip_links", default="View Trip-Calendar Links"),
                command=self._view_trip_calendar_links)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("academic_calendar.menu.view"), menu=view_menu)
        view_menu.add_command(label=_("academic_calendar.menu.dashboard"), command=self._show_dashboard)
        view_menu.add_command(label=_("academic_calendar.menu.calendar"), command=self._show_calendar_view)
        view_menu.add_command(label=_("academic_calendar.menu.events_list"), command=self._show_manage_events)
        view_menu.add_separator()

        # Admin and Staff can view analytics
        if is_admin or is_staff:
            view_menu.add_command(label=_("academic_calendar.menu.data_visualization"), command=self._show_data_visualization)
            view_menu.add_command(label=_("academic_calendar.menu.reports"), command=self._show_reports)
            view_menu.add_separator()

        view_menu.add_command(label=_("academic_calendar.menu.refresh"), command=self._refresh_current_view)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("academic_calendar.menu.tools"), menu=tools_menu)

        # Admin and Staff only
        if is_admin or is_staff:
            tools_menu.add_command(label=_("academic_calendar.menu.calendar_sync"), command=self._calendar_sync)
            tools_menu.add_command(label=_("academic_calendar.menu.import_holidays"), command=self._import_holidays)

        # Admin only - Bulk operations
        if is_admin:
            tools_menu.add_command(label=_("academic_calendar.menu.bulk_operations"), command=self._bulk_operations)

        # Admin only - System maintenance
        if is_admin:
            tools_menu.add_separator()
            tools_menu.add_command(label=_("academic_calendar.menu.system_maintenance"), command=self._show_system_backup)
            tools_menu.add_command(label=_("academic_calendar.menu.audit_logs"), command=self._show_audit_logs)

        if is_admin or is_staff:
            tools_menu.add_separator()
            tools_menu.add_command(label=_("academic_calendar.menu.cli_mode"), command=self._launch_cli_mode)

        # Settings menu - Admin and Staff only
        if is_admin or is_staff:
            settings_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("academic_calendar.menu.settings"), menu=settings_menu)
            settings_menu.add_command(label=_("academic_calendar.menu.notification_settings"), command=self._show_notification_settings)
            settings_menu.add_command(label=_("academic_calendar.menu.timezone_settings"), command=self._show_timezone_settings)
            settings_menu.add_command(label=_("academic_calendar.menu.general_settings"), command=self._show_settings)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("academic_calendar.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("academic_calendar.menu.user_guide"), command=self._show_help)
        help_menu.add_command(label=_("academic_calendar.menu.about"), command=self._show_about)
        help_menu.add_separator()
        help_menu.add_command(
            label=f"{_('academic_calendar.menu.change_language')} [{get_current_language_name()}]",
            command=self._on_language_change
        )

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Place a reusable main-menu button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            gui_logger.debug(f"Error checking main_menu_button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=_("academic_calendar.buttons.return_to_main_menu"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=55)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-n>', lambda e: self._show_add_event())
        self.root.bind('<Control-e>', lambda e: self._show_export())
        self.root.bind('<Control-r>', lambda e: self._refresh_current_view())
        self.root.bind('<F5>', lambda e: self._refresh_current_view())
        self.root.bind('<Control-f>', lambda e: self._show_advanced_search())
        # Fix: Use proper key binding syntax for Shift combinations
        self.root.bind('<Control-Shift-R>', lambda e: self._show_create_recurring_event())
        self.root.bind('<Control-Shift-N>', lambda e: self._show_notification_settings())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    def _setup_calendar_manager(self):
        """Setup the calendar manager"""
        try:
            config = CalendarConfig()
            self.calendar_manager = AcademicCalendarManager(
                config=config,
                auth_manager=self.auth_manager
            )
            gui_logger.info("Calendar manager initialized successfully")
            self._update_status(_("academic_calendar.messages.calendar_initialized"))
        except Exception as e:
            import traceback
            gui_logger.error(f"Calendar initialization failed: {e}")
            gui_logger.error(f"Traceback: {traceback.format_exc()}")
            # Show error to user
            messagebox.showerror(
                "Calendar Initialization Error",
                f"Failed to initialize calendar manager:\n\n{str(e)}\n\nCheck logs for details."
            )
            # Keep calendar_manager as None so the GUI can show appropriate message

        # Now show the dashboard after calendar_manager is set up
        self._show_dashboard()

    def _has_permission_for_button(self, button_text: str) -> bool:
        """Check if user has permission for a specific button"""
        if not self.auth_manager or not self.auth_manager.current_user:
            return False

        permission_map = {
            "➕ Add Event": "manage_schedules",
            "📝 Manage Events": "manage_schedules",
            "🔄 Recurring Events": "manage_schedules",
            "📚 Academic Years": "manage_schedules",
            "📖 Semesters": "manage_schedules",
            "🏢 Resources": "manage_schedules",
            "📚 Courses": "manage_schedules",
            "🏷️ Categories & Tags": "manage_schedules",
            "🎯 Milestones": "manage_schedules",
            "🔔 Notifications": "view_own_timetable",
            "🌐 Timezone": "view_own_timetable",
            "📊 Reports": "view_reports",
            "📈 Visualizations": "export_data",
            "📤 Export": "export_data",
            "🛠️ System": "system_config",
            "📋 Audit Logs": "system_config",
            "⚙️ Settings": "system_config",
        }

        required_permission = permission_map.get(button_text)
        if not required_permission:
            return True  # No specific permission required

        return self.auth_manager.check_permission(required_permission)

    def _stop_task_processor(self):
        """Signal the after() poll loop to stop. Uses a flag rather than
        after_cancel to avoid a Tcl 'invalid command name' race on teardown."""
        self._closing = True
        self._task_after_id = None

    def _on_close(self):
        """Stop the task poll loop and destroy the window."""
        self._stop_task_processor()
        self.root.destroy()

    def _start_task_processor(self):
        """Start background task processor"""
        def process_tasks():
            if self._closing:
                return
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return

            try:
                while True:
                    task = self.task_queue.get(timeout=0.1)
                    if task is None:
                        break
                    try:
                        task()
                    except Exception as e:
                        gui_logger.error(f"Task failed: {e}")
                        self.root.after(0, lambda _e=e: self._show_error(f"Operation failed: {_e}"))
                    finally:
                        self.task_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                gui_logger.error(f"Task processor error: {e}")

            # Schedule next check (unless we're tearing down)
            if self._closing:
                return
            try:
                self._task_after_id = self.root.after(100, process_tasks)
            except tk.TclError:
                pass

        self._task_after_id = self.root.after(100, process_tasks)

    def _clear_content_area(self):
        """Clear the content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def _update_status(self, message: str, status_type: str = "info"):
        """Update status bar message"""
        self.status_label.config(text=message)
        if status_type == "error":
            self.status_label.config(foreground='red')
        elif status_type == "success":
            self.status_label.config(foreground='green')
        elif status_type == "warning":
            self.status_label.config(foreground='orange')
        else:
            self.status_label.config(foreground='black')

    def _show_progress(self, show: bool = True):
        """Show/hide progress bar"""
        if show:
            self.progress_bar.start()
        else:
            self.progress_bar.stop()

    def _show_error(self, message: str):
        """Show error message"""
        messagebox.showerror(_("common.error"), message)
        self._update_status(f"{_('common.error')}: {message}", "error")

    def _show_success(self, message: str):
        """Show success message"""
        messagebox.showinfo(_("common.success"), message)
        self._update_status(message, "success")

    def _show_warning(self, message: str):
        """Show warning message"""
        messagebox.showwarning(_("common.warning"), message)
        self._update_status(f"{_('common.warning')}: {message}", "warning")

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._update_status(_("academic_calendar.messages.email_template_copied"), "success")
        except Exception as e:
            self._show_error(_("academic_calendar.messages.failed_to_copy_clipboard").format(error=e))

    def _refresh_current_view(self):
        """Refresh the current view"""
        if self.current_view == "dashboard":
            self._show_dashboard()
        elif self.current_view == "calendar":
            self._load_calendar_data()
        elif self.current_view == "manage_events":
            self._load_events_data()
        elif self.current_view == "academic_years":
            self._show_academic_years()
        elif self.current_view == "semesters":
            self._show_semesters()

    def _on_language_change(self):
        """Handle language change request"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()

        if old_lang != new_lang:
            messagebox.showinfo(
                _("academic_calendar.language.changed_title"),
                _("academic_calendar.language.restart_for_full_effect")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI text elements with current language translations"""
        try:
            # Update window title
            if not self.parent_window:
                self.root.title(_("academic_calendar.title"))

            # Update status bar
            if hasattr(self, 'status_label'):
                self.status_label.config(text=_("academic_calendar.status.ready"))

            # Rebuild menu bar with new language
            self._create_menu_bar()

            # Rebuild sidebar with new language
            if hasattr(self, 'sidebar'):
                for widget in self.sidebar.winfo_children():
                    widget.destroy()
                self._create_sidebar()

            # Refresh current view to apply new translations
            self._refresh_current_view()

            gui_logger.info(f"UI language refreshed to: {get_current_language()}")
        except Exception as e:
            gui_logger.error(f"Error refreshing UI language: {e}")

    def return_to_main_menu(self):
        """Return to main menu"""
        try:
            # Stop the task poll loop before destroying
            self._stop_task_processor()

            # Determine which window to close
            window_to_close = self.parent_window if self.parent_window else self.root

            # Check if it's a child window (Toplevel) or standalone (Tk)
            if isinstance(window_to_close, tk.Toplevel):
                # Just close the child window
                window_to_close.destroy()
            else:
                # Running standalone, need to create main GUI if auth available
                if self.auth_manager:
                    window_to_close.destroy()
                    from education_system.systems.university.interfaces.gui.shell.main import UnifiedManagementGUI
                    app = UnifiedManagementGUI(self.auth_manager)
                    app.run()
                else:
                    from tkinter import messagebox
                    messagebox.showinfo(_("common.info"), _("academic_calendar.messages.no_main_menu_standalone"))
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Run the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.quit()
        except Exception as e:
            gui_logger.error(f"GUI runtime error: {e}")
            messagebox.showerror(_("academic_calendar.messages.runtime_error"), _("academic_calendar.messages.an_error_occurred").format(error=e))



def launch_calendar_gui(auth_manager=None):
    """
    Launch the Calendar GUI application

    Args:
        auth_manager: Authentication manager instance (optional)

    Returns:
        CalendarGUI instance
    """
    try:
        # Ensure calendar permissions exist
        from education_system.systems.university.domain.academics.services.academic_calendar.cli import ensure_calendar_permissions
        ensure_calendar_permissions()

        # Create and run GUI
        gui = CalendarGUI(auth_manager)
        return gui

    except ImportError as e:
        # Handle missing dependencies gracefully
        root = tk.Tk()
        root.withdraw()  # Hide main window

        error_msg = _("academic_calendar.messages.import_error").format(error=e)

        messagebox.showerror(_("academic_calendar.messages.import_error_title"), error_msg)
        root.destroy()
        return None

    except Exception as e:
        # Handle other initialization errors
        root = tk.Tk()
        root.withdraw()

        error_msg = _("academic_calendar.messages.initialization_error").format(error=e)

        messagebox.showerror(_("academic_calendar.messages.initialization_error_title"), error_msg)
        root.destroy()
        return None


def run_gui_calendar(auth_manager=None):
    """
    Convenience function to launch and run the calendar GUI

    Args:
        auth_manager: Authentication manager instance (optional)
    """
    gui = launch_calendar_gui(auth_manager)
    if gui:
        gui.run()


def display_academic_calendar_gui(auth_manager=None):
    """
    Backward compatibility function for GUI launch
    Maintains same signature as CLI function
    """
    return run_gui_calendar(auth_manager)


def integrate_with_main_system():
    """
    Integration function to be called from main system
    Provides seamless integration with existing authentication
    """
    try:
        # Import the main authentication system
        from education_system.systems.university.infrastructure.auth import get_global_auth
        global_auth = get_global_auth()

        if global_auth and global_auth.current_user:
            # User is authenticated, launch GUI
            return run_gui_calendar(global_auth)
        else:
            # No authentication, show error
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(_("academic_calendar.messages.auth_required"),
                               _("academic_calendar.messages.please_login"))
            root.destroy()
            return None

    except ImportError:
        # Fallback to basic GUI without authentication
        messagebox.showwarning(_("academic_calendar.messages.auth_unavailable"),
                             _("academic_calendar.messages.limited_mode"))
        return run_gui_calendar()


