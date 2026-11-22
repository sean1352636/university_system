
import os

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import (
    tk, ttk, messagebox, scrolledtext,
    sqlite3, logging, time, datetime, timedelta,
    init_i18n, _t,
    log_read,
    CALENDAR_AVAILABLE,
    DEFAULT_DB_PATH,
    logger,
    safe_db_operation as module_safe_db_operation,
)

if CALENDAR_AVAILABLE:
    from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import CalendarConfig, AcademicCalendarManager

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, show_error, money, title_case, trip_label, parse_trip_id,
    has_any, APPROVER_PERMISSIONS, WORKSPACE_PERMISSIONS, list_trip_staff, calendar_links,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.trip_dialogs import TripDetailsDialog, CreateTripDialog, UpdateTripDialog, TripSelectionDialog, notify_trip_participants, email_people
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.registration_dialogs import CancelRegistrationDialog, RegisterForTripDialog, PaymentStatusDialog, ParticipantStatusDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.itinerary_dialogs import ViewItineraryDialog, ItineraryDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.expense_dialogs import AddExpenseDialog, EditExpenseDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.staff_dialogs import AssignStaffDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.report_dialogs import ReportGeneratorDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.export_dialog import ExportDataDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.about_dialog import AboutDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.workspace import TripWorkspace
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.ws_planning import ApprovalsPanel, RiskPanel, MyApprovalsTab
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.ws_safety import IncidentsPanel, SafeguardingPanel, OverseasPanel, AcademicPanel, ReportIncidentDialog, DocumentsDialog
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.ws_people import ParticipantsPanel, PayDialog, HealthDetailsDialog, show_medical_sheet
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.ws_running import CommsPanel, OnTheDayPanel, MoneyPanel, EvaluationPanel, HistoryPanel, EvaluateDialog

_M = 'gui.operations.campus.mobility.trip_management_gui.main'

# The Trip Workspace sub-tabs, in the order a trip goes through them.
WORKSPACE_PANELS = (ApprovalsPanel, RiskPanel, SafeguardingPanel, OverseasPanel, AcademicPanel,
                    ParticipantsPanel, CommsPanel, OnTheDayPanel, IncidentsPanel, MoneyPanel,
                    EvaluationPanel, HistoryPanel)

# Tabs are found by these stable keys, never by their (translated) text.
# The English labels map to the keys for callers that still pass a label.
TAB_KEYS = {'All Trips': 'all_trips', 'Register for Trip': 'register', 'My Trips': 'my_trips',
            'Administration': 'admin', 'Reports': 'reports', 'Calendar': 'calendar',
            'Trip Workspace': 'workspace', 'My Approvals': 'approvals'}
ADMIN_TAB_KEYS = {'Manage Participants': 'participants', 'Assign Staff': 'staff',
                  'Manage Expenses': 'expenses', 'Trip Management': 'trip_management'}

ALL_CURRENT = 'all_current'
ALL_INCL_ARCHIVED = 'all'


class TripManagementGUI:
    def __init__(self, auth_instance=None, root=None):
        # Initialize i18n for language support
        init_i18n()

        # Support both (root, auth) and (auth, root) calling conventions.
        # Detect by checking if the first argument is a tkinter widget.
        if auth_instance is not None and isinstance(auth_instance, (tk.Tk, tk.Toplevel, tk.Frame)):
            auth_instance, root = root, auth_instance

        self.auth = auth_instance
        self.root = root          # may be provided by caller
        self._owns_root = self.root is None  # track if we created the root
        self.main_frame = None
        self.notebook = None
        self.status_bar = None
        self.workspace = None
        self._tabs = {}
        self._admin_tabs = {}
        self._all_trips = []
        self._my_regs = {}

        # The calendar manager must exist before the tabs are built: the
        # Calendar tab is only added when it is there.
        self.calendar_manager = None
        if CALENDAR_AVAILABLE and self.auth and getattr(self.auth, 'current_user', None):
            try:
                from education_system.systems.university.infrastructure.database import db as _db
                # CalendarConfig's default path is fixed when its module is
                # imported; pass the current one so it follows the trip data.
                config = CalendarConfig(db_file=os.fspath(_db.DEFAULT_DB_PATH))
                self.calendar_manager = AcademicCalendarManager(config=config, auth_manager=self.auth)
            except Exception as e:
                logging.warning(f"Could not initialize calendar system: {e}")

        self.setup_gui()

    def setup_gui(self):
        """Initialize the main GUI window"""
        if self.root is None:
            from education_system.platform.delivery.gui import window_sizing
            window_sizing.install()
            self.root = tk.Tk()
        self.root.title(_t("trip.title", default="Trip Management"))
        self.root.geometry("1400x900+%d+%d" % (max((self.root.winfo_screenwidth() - 1400) // 2, 0),
                                               max((self.root.winfo_screenheight() - 900) // 2, 0)))
        self.root.minsize(1200, 800)

        self.create_menu()

        # Status bar first so the notebook cannot squeeze it out.
        self.status_bar = ttk.Label(self.root, text=_t("common.ready", default="Ready"), relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.create_main_menu_button()

        # Check authentication - user must log in through main GUI
        if self.auth and self.auth.current_user:
            self.show_main_interface()
        else:
            messagebox.showerror(
                _t(f'{_M}.dialogs.authentication_required', default="Authentication Required"),
                _t(f'{_M}.dialogs.please_log_in_through_the_main_university_system_gui_before_acce', default="Please log in through the main University System GUI before accessing Trip Management.")
            )
            self.root.destroy()

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def can(self, *permissions):
        return bool(self.auth) and has_any(self.auth, *permissions)

    def create_menu(self):
        """Create the application menu bar; entries follow the user's permissions."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        can_create = self.can('create_trips', 'manage_trips')
        can_export = self.can('view_trip_reports', 'manage_trips', 'export_participant_data')

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file", default="File"), menu=file_menu)
        if can_export:
            file_menu.add_command(label=_t("trip.menu.export_data", default="Export Data"), command=self.export_data)
            file_menu.add_separator()
        # No Exit item: the window has a "Return to Main Menu" button, and
        # root.quit() tore down the whole application when Trip Management
        # was opened as a Toplevel from the main GUI.

        trip_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("trip.menu.trips", default="Trips"), menu=trip_menu)
        trip_menu.add_command(label=_t("trip.menu.view_all_trips", default="View All Trips"), command=self.show_trips_view)
        if can_create:
            trip_menu.add_command(label=_t("trip.menu.create_new_trip", default="Create New Trip"), command=self.show_create_trip)
        trip_menu.add_command(label=_t("trip.menu.view_trip_details", default="View Trip Details"), command=self.view_trip)
        if can_create:
            trip_menu.add_command(label=_t("trip.menu.update_trip", default="Update Trip"), command=self.update_trip)
            trip_menu.add_command(label=_t("trip.menu.delete_trip", default="Delete Trip"), command=self.delete_trip)

        trip_menu.add_separator()
        trip_menu.add_command(label=_t("trip.menu.my_registrations", default="My Registrations"), command=self.show_my_registrations)

        # Cross-domain: surface risk-register entries linked to a
        # trip via risk_bus.list_risks_for("trip:N").
        def _show_trip_risks():
            def _open(trip_id):
                from education_system.systems.university.services.bus.risks_panel import (
                    show_risks_for,
                )
                name = self._trip_name(trip_id) or trip_id
                show_risks_for(self.root, f"trip:{trip_id}", title=f"Risks for trip {name}")

            TripSelectionDialog(self.root, self.auth, _open)
        trip_menu.add_separator()
        trip_menu.add_command(label=_t(f'{_M}.menus.view_trip_risks', default="View trip risks"), command=_show_trip_risks)
        trip_menu.add_command(label=_t(f'{_M}.menus.report_incident', default="Report an Incident..."),
                              command=self.report_incident)

        if self.can('cancel_trip_registration'):
            trip_menu.add_command(label=_t("trip.menu.cancel_registration", default="Cancel Registration"), command=self.cancel_selected_registration)

        if self.can('view_trips'):
            itinerary_menu = tk.Menu(trip_menu, tearoff=0)
            trip_menu.add_cascade(label=_t("trip.menu.itinerary", default="Itinerary"), menu=itinerary_menu)
            itinerary_menu.add_command(label=_t("trip.menu.view_trip_itinerary", default="View Trip Itinerary"), command=self.view_trip_itinerary)
            if can_create:
                itinerary_menu.add_command(label=_t("trip.menu.manage_itinerary", default="Manage Itinerary"), command=self.add_trip_itinerary)

        if self.can('view_trip_reports'):
            reports_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.reports", default="Reports"), menu=reports_menu)
            reports_menu.add_command(label=_t("trip.menu.trip_summary", default="Trip Summary"), command=self.generate_trip_summary_report)
            reports_menu.add_command(label=_t("trip.menu.participant_list", default="Participant List"), command=self.generate_participant_report)
            reports_menu.add_command(label=_t("trip.menu.financial_report", default="Financial Report"), command=self.generate_financial_report)

        if self.can(*WORKSPACE_PERMISSIONS):
            ws_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t(f'{_M}.menus.workspace', default="Workspace"), menu=ws_menu)
            for panel in WORKSPACE_PANELS:
                ws_menu.add_command(label=panel.title, command=lambda k=panel.key: self.open_workspace(k))
            if self.can(*APPROVER_PERMISSIONS):
                ws_menu.add_separator()
                ws_menu.add_command(label=_t(f'{_M}.menus.my_approvals', default="My Approvals"),
                                    command=lambda: self._select_tab('approvals'))

        if self.can('manage_trips'):
            admin_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.admin", default="Admin"), menu=admin_menu)
            admin_menu.add_command(label=_t("trip.menu.manage_participants", default="Manage Participants"), command=self.show_manage_participants)
            # "Assign Staff" opens the staff tab (every trip's staff list);
            # "Assign Trip Staff" picks one trip and assigns to it directly.
            admin_menu.add_command(label=_t("trip.menu.assign_staff", default="Assign Staff"), command=self.show_assign_staff)
            admin_menu.add_command(label=_t("trip.menu.manage_expenses", default="Manage Expenses"), command=self.show_manage_expenses)
            admin_menu.add_separator()
            admin_menu.add_command(label=_t("trip.menu.assign_trip_staff", default="Assign Trip Staff"), command=self.assign_trip_staff)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help", default="Help"), menu=help_menu)
        help_menu.add_command(label=_t("trip.menu.about", default="About"), command=self.show_about)

    # Role helpers kept for callers outside this class; menus and tabs use
    # permissions (``can``), not role names.
    def get_user_role(self):
        try:
            if self.auth and getattr(self.auth, 'current_user', None):
                return str(self.auth.current_user.get('role', '')).lower()
        except Exception as e:
            logging.error(f"Error getting user role: {e}")
        return None

    def is_admin(self):
        return self.can('manage_trips')

    def is_staff(self):
        return self.can('create_trips', 'manage_trip_participants') and not self.can('manage_trips')

    def is_student(self):
        return self.can('register_for_trips') and not self.can('create_trips', 'manage_trips')

    def create_main_menu_button(self):
        """Place a persistent main-menu button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Error checking main_menu_button existence: {e}")
        self.main_menu_button = ttk.Button(self.root, text=_t("common.return_to_main_menu", default="Return to Main Menu"),
                                           command=self.return_to_main_menu)
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def show_main_interface(self):
        """Show the main trip management interface"""
        self.clear_main_frame()
        self._tabs = {}

        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text=_t("trip.header_title", default="Trip Management"),
                  font=('Arial', 18, 'bold')).pack(side=tk.LEFT)
        if self.auth and self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
            ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT, padx=(0, 180))

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.add_trips_tab()
        if self.can('register_for_trips'):
            self.add_registration_tab()
        if self.can('view_own_trip_registrations'):
            self.add_my_trips_tab()
        if self.can('manage_trips'):
            self.add_admin_tab()
        if self.can('view_trip_reports'):
            self.add_reports_tab()
        if self.can(*WORKSPACE_PERMISSIONS):
            self.add_workspace_tab()
        if self.can(*APPROVER_PERMISSIONS):
            self.add_approvals_tab()
        if CALENDAR_AVAILABLE and self.calendar_manager:
            self.add_calendar_tab()

    def _add_tab(self, key, frame, text):
        self.notebook.add(frame, text=text)
        self._tabs[key] = frame
        return frame

    def add_trips_tab(self):
        """Add the trips overview tab"""
        trips_frame = self._add_tab('all_trips', ttk.Frame(self.notebook), _t("trip.tabs.all_trips", default="All Trips"))

        toolbar = ttk.Frame(trips_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text=_t("common.refresh", default="Refresh"), command=self.refresh_trips).pack(side=tk.LEFT, padx=(0, 5))
        if self.can('create_trips', 'manage_trips'):
            ttk.Button(toolbar, text=_t("trip.btn.create_trip", default="Create Trip"), command=self.show_create_trip).pack(side=tk.LEFT, padx=5)
        if self.can(*WORKSPACE_PERMISSIONS):
            ttk.Button(toolbar, text=_t(f'{_M}.buttons.open_workspace', default="Open in Workspace"),
                       command=self.open_selected_in_workspace).pack(side=tk.LEFT, padx=5)

        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT)
        ttk.Label(search_frame, text=_t(f'{_M}.labels.status_filter', default="Status:")).pack(side=tk.LEFT, padx=(0, 3))
        statuses = [s for s in tm('database').TRIP_STATUSES if s != 'planning']
        self._status_filters = {_t(f'{_M}.labels.all_current', default="All current"): ALL_CURRENT}
        self._status_filters.update({title_case(s): s for s in statuses})
        self._status_filters[_t(f'{_M}.labels.all_incl_archived', default="All incl. archived")] = ALL_INCL_ARCHIVED
        self.status_filter_var = tk.StringVar(value=next(iter(self._status_filters)))
        status_combo = ttk.Combobox(search_frame, textvariable=self.status_filter_var, state='readonly',
                                    values=list(self._status_filters), width=16)
        status_combo.pack(side=tk.LEFT, padx=(0, 8))
        status_combo.bind('<<ComboboxSelected>>', self.filter_trips)
        ttk.Label(search_frame, text=_t(f'{_M}.labels.from', default="From:")).pack(side=tk.LEFT)
        self.date_from_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.date_from_var, width=11).pack(side=tk.LEFT, padx=(2, 5))
        ttk.Label(search_frame, text=_t(f'{_M}.labels.to', default="To:")).pack(side=tk.LEFT)
        self.date_to_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.date_to_var, width=11).pack(side=tk.LEFT, padx=(2, 8))
        for var in (self.date_from_var, self.date_to_var):
            var.trace_add('write', self.filter_trips)
        ttk.Label(search_frame, text=_t(f'{_M}.labels.search', default="Search:")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_trips)
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT)

        table = ttk.Frame(trips_frame)
        table.pack(fill=tk.BOTH, expand=True)
        self.trips_tree = ttk.Treeview(table, columns=('name', 'destination', 'start_date', 'participants', 'cost', 'status'), show='tree headings')
        self.trips_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.trips_tree.heading('name', text=_t(f'{_M}.headings.trip_name', default='Trip Name'))
        self.trips_tree.heading('destination', text=_t(f'{_M}.headings.destination', default='Destination'))
        self.trips_tree.heading('start_date', text=_t(f'{_M}.headings.start_date', default='Start Date'))
        self.trips_tree.heading('participants', text=_t(f'{_M}.headings.participants', default='Participants'))
        self.trips_tree.heading('cost', text=_t(f'{_M}.headings.cost', default='Cost'))
        self.trips_tree.heading('status', text=_t(f'{_M}.headings.status', default='Status'))
        self.trips_tree.column('#0', width=50)
        self.trips_tree.column('name', width=200)
        self.trips_tree.column('destination', width=150)
        self.trips_tree.column('start_date', width=100)
        self.trips_tree.column('participants', width=100)
        self.trips_tree.column('cost', width=80)
        self.trips_tree.column('status', width=100)

        trips_scrollbar_v = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.trips_tree.yview)
        trips_scrollbar_h = ttk.Scrollbar(table, orient=tk.HORIZONTAL, command=self.trips_tree.xview)
        self.trips_tree.configure(yscrollcommand=trips_scrollbar_v.set, xscrollcommand=trips_scrollbar_h.set)
        trips_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        trips_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        self.trips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.trips_tree.bind('<Double-1>', self.on_trip_double_click)
        self.create_trips_context_menu()
        self.refresh_trips()

    def add_registration_tab(self):
        """Add the trip registration tab"""
        reg_frame = self._add_tab('register', ttk.Frame(self.notebook),
                                  _t(f'{_M}.tabs.register_for_trip', default="Register for Trip"))
        ttk.Label(reg_frame, text=_t(f'{_M}.labels.available_trips_for_registration', default="Available Trips for Registration"),
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        ttk.Button(reg_frame, text=_t(f'{_M}.buttons.register_for_selected_trip', default="Register for Selected Trip"),
                   command=self.register_for_trip).pack(side=tk.BOTTOM, pady=10)
        search = ttk.Frame(reg_frame)
        search.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search, text=_t(f'{_M}.labels.search', default="Search:")).pack(side=tk.LEFT)
        self.reg_search_var = tk.StringVar()
        self.reg_search_var.trace_add('write', lambda *_: self.load_available_trips())
        ttk.Entry(search, textvariable=self.reg_search_var, width=30).pack(side=tk.LEFT, padx=5)

        self.reg_tree = ttk.Treeview(reg_frame, columns=('name', 'destination', 'start_date', 'cost', 'spaces'), show='tree headings')
        self.reg_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.reg_tree.heading('name', text=_t(f'{_M}.headings.trip_name', default='Trip Name'))
        self.reg_tree.heading('destination', text=_t(f'{_M}.headings.destination', default='Destination'))
        self.reg_tree.heading('start_date', text=_t(f'{_M}.headings.start_date', default='Start Date'))
        self.reg_tree.heading('cost', text=_t(f'{_M}.headings.cost', default='Cost'))
        self.reg_tree.heading('spaces', text=_t(f'{_M}.headings.spaces_left', default='Spaces Left'))
        self.reg_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.reg_tree.bind('<Double-1>', lambda _e: self.register_for_trip())
        self.load_available_trips()

    def add_my_trips_tab(self):
        """Add the my trips tab"""
        my_trips_frame = self._add_tab('my_trips', ttk.Frame(self.notebook),
                                       _t(f'{_M}.tabs.my_trips', default="My Trips"))
        ttk.Label(my_trips_frame, text=_t(f'{_M}.labels.my_trip_registrations', default="My Trip Registrations"),
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Action bars before the table, so they are never squeezed out.
        actions = ttk.Frame(my_trips_frame)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        row1 = ttk.Frame(actions)
        row1.pack(fill=tk.X)
        row2 = ttk.Frame(actions)
        row2.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(row1, text=_t(f'{_M}.buttons.cancel_selected_registration', default="Cancel Selected Registration"),
                   command=self.cancel_registration).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text=_t(f'{_M}.buttons.accept_offer', default="Accept Offered Place"),
                   command=self.accept_offer).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text=_t(f'{_M}.buttons.decline_offer', default="Decline Offer"),
                   command=self.decline_offer).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text=_t(f'{_M}.buttons.pay', default="Pay..."),
                   command=self.pay_for_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text=_t(f'{_M}.buttons.view_details', default="View Trip Details"),
                   command=lambda: self._with_my_reg(lambda r: self.open_trip_details(r['trip_id']))).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text=_t(f'{_M}.buttons.health_details', default="My Medical & Dietary Details..."),
                   command=self.my_health_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text=_t(f'{_M}.buttons.documents', default="Travel Documents..."),
                   command=self.my_travel_documents).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text=_t(f'{_M}.buttons.conduct', default="Accept Code of Conduct"),
                   command=self.accept_code_of_conduct).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text=_t(f'{_M}.buttons.report_incident', default="Report an Incident..."),
                   command=self.report_incident_on_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text=_t(f'{_M}.buttons.evaluate', default="Evaluate Trip..."),
                   command=self.evaluate_selected).pack(side=tk.LEFT, padx=5)

        search = ttk.Frame(my_trips_frame)
        search.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search, text=_t(f'{_M}.labels.search', default="Search:")).pack(side=tk.LEFT)
        self.my_search_var = tk.StringVar()
        self.my_search_var.trace_add('write', lambda *_: self._fill_my_trips())
        ttk.Entry(search, textvariable=self.my_search_var, width=30).pack(side=tk.LEFT, padx=5)

        self.my_trips_tree = ttk.Treeview(my_trips_frame, columns=('name', 'destination', 'start_date', 'cost', 'payment', 'status', 'place', 'owed'), show='tree headings')
        self.my_trips_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.my_trips_tree.heading('name', text=_t(f'{_M}.headings.trip_name', default='Trip Name'))
        self.my_trips_tree.heading('destination', text=_t(f'{_M}.headings.destination', default='Destination'))
        self.my_trips_tree.heading('start_date', text=_t(f'{_M}.headings.start_date', default='Start Date'))
        self.my_trips_tree.heading('cost', text=_t(f'{_M}.headings.cost', default='Cost'))
        self.my_trips_tree.heading('payment', text=_t(f'{_M}.headings.payment', default='Payment'))
        self.my_trips_tree.heading('status', text=_t(f'{_M}.headings.status', default='Status'))
        self.my_trips_tree.heading('place', text=_t(f'{_M}.headings.waitlist_offer', default='Waiting List / Offer'))
        self.my_trips_tree.heading('owed', text=_t(f'{_M}.headings.owed', default='Owed'))
        self.my_trips_tree.column('#0', width=50)
        self.my_trips_tree.column('place', width=170)
        self.my_trips_tree.column('owed', width=80)
        self.my_trips_tree.tag_configure('offered', background='#e6f0ff')
        self.my_trips_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.load_my_trips()

    def add_admin_tab(self):
        admin_frame = self._add_tab('admin', ttk.Frame(self.notebook),
                                    _t(f'{_M}.tabs.administration', default="Administration"))
        self.admin_notebook = ttk.Notebook(admin_frame)
        self.admin_notebook.pack(fill=tk.BOTH, expand=True)
        self._admin_tabs = {}
        for key, text, setup in (
                ('participants', _t(f'{_M}.tabs.manage_participants', default="Manage Participants"), self.setup_participants_management),
                ('staff', _t(f'{_M}.tabs.assign_staff', default="Assign Staff"), self.setup_staff_assignment),
                ('expenses', _t(f'{_M}.tabs.manage_expenses', default="Manage Expenses"), self.setup_expenses_management),
                ('trip_management', _t(f'{_M}.tabs.trip_management', default="Trip Management"), self.setup_trip_management)):
            frame = ttk.Frame(self.admin_notebook)
            self.admin_notebook.add(frame, text=text)
            self._admin_tabs[key] = frame
            setup(frame)
        self.load_trips_for_management()

    def add_reports_tab(self):
        """Add the reports tab"""
        reports_frame = self._add_tab('reports', ttk.Frame(self.notebook), _t(f'{_M}.tabs.reports', default="Reports"))
        ttk.Label(reports_frame, text=_t(f'{_M}.labels.trip_reports', default="Trip Reports"),
                  font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        reports_buttons_frame = ttk.Frame(reports_frame)
        reports_buttons_frame.pack(pady=20)
        ttk.Button(reports_buttons_frame, text=_t(f'{_M}.buttons.trip_summary_report', default="Trip Summary Report"),
                   command=self.generate_trip_summary_report).pack(pady=5, fill=tk.X)
        ttk.Button(reports_buttons_frame, text=_t(f'{_M}.buttons.participant_list_report', default="Participant List Report"),
                   command=self.generate_participant_report).pack(pady=5, fill=tk.X)
        if self.can('view_financial_reports'):
            ttk.Button(reports_buttons_frame, text=_t(f'{_M}.buttons.financial_report', default="Financial Report"),
                       command=self.generate_financial_report).pack(pady=5, fill=tk.X)
        ttk.Label(reports_frame, text=_t(f'{_M}.labels.report_generation_log', default="Report Generation Log")).pack(anchor=tk.W, pady=(20, 5))
        self.report_log = scrolledtext.ScrolledText(reports_frame, height=15, width=80)
        self.report_log.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    def add_workspace_tab(self):
        """The Trip Workspace: approvals, risk, safety, people, comms, money, evaluation."""
        self.workspace = TripWorkspace(self.notebook, self, WORKSPACE_PANELS)
        self._add_tab('workspace', self.workspace, _t(f'{_M}.tabs.workspace', default="Trip Workspace"))

    def add_approvals_tab(self):
        """Approval decisions waiting on the signed-in user."""
        self.approvals_tab = MyApprovalsTab(self.notebook, self)
        self._add_tab('approvals', self.approvals_tab, _t(f'{_M}.tabs.my_approvals', default="My Approvals"))

    def add_calendar_tab(self):
        """Add the calendar integration tab"""
        calendar_frame = self._add_tab('calendar', ttk.Frame(self.notebook), _t(f'{_M}.tabs.calendar', default="Calendar"))
        ttk.Label(calendar_frame, text=_t(f'{_M}.labels.calendar_integration', default="Calendar Integration"),
                  font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        cal_buttons_frame = ttk.Frame(calendar_frame)
        cal_buttons_frame.pack(pady=20)
        ttk.Button(cal_buttons_frame, text=_t(f'{_M}.buttons.view_trips_with_calendar_events', default="View Trips with Calendar Events"),
                   command=self.show_trips_with_calendar).pack(pady=5, fill=tk.X)
        ttk.Button(cal_buttons_frame, text=_t(f'{_M}.buttons.view_trip_events_in_calendar', default="View Trip Events in Calendar"),
                   command=self.view_trip_events_in_calendar).pack(pady=5, fill=tk.X)
        # Calendar events for trips are no longer created from here. A trip
        # now starts life as a Trip-typed event in the Academic Calendar,
        # which registers the trip itself — one direction, not two.
        self.calendar_tree = ttk.Treeview(calendar_frame, columns=('trip', 'event', 'start_date', 'status'), show='tree headings')
        self.calendar_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.calendar_tree.heading('trip', text=_t(f'{_M}.headings.trip_name', default='Trip Name'))
        self.calendar_tree.heading('event', text=_t(f'{_M}.headings.calendar_event', default='Calendar Event'))
        self.calendar_tree.heading('start_date', text=_t(f'{_M}.headings.start_date', default='Start Date'))
        self.calendar_tree.heading('status', text=_t(f'{_M}.headings.status', default='Status'))
        self.calendar_tree.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

    def clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def update_status(self, message):
        """Update the status bar"""
        try:
            self.status_bar.config(text=message)
            self.root.update_idletasks()
        except tk.TclError:
            pass

    def _ensure_main_ui(self):
        """Ensure the main notebook exists."""
        if self.notebook is None:
            self.show_main_interface()

    def _select_tab(self, key_or_label):
        """Select a top-level tab by its stable key (or its English label)."""
        self._ensure_main_ui()
        frame = self._tabs.get(TAB_KEYS.get(key_or_label, key_or_label))
        if frame is None:
            return False
        self.notebook.select(frame)
        return True

    def _show_admin_subtab(self, key_or_label):
        self._ensure_main_ui()
        if 'admin' not in self._tabs:
            if self.can('manage_trips'):
                self.add_admin_tab()
            else:
                messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"), _t(f'{_M}.dialogs.you_don_t_have_access_to_administration', default="You don't have access to Administration."))
                return
        self._select_tab('admin')
        frame = self._admin_tabs.get(ADMIN_TAB_KEYS.get(key_or_label, key_or_label))
        if frame is not None:
            self.admin_notebook.select(frame)

    def open_workspace(self, key='approvals', trip_id=None):
        """Show the Trip Workspace sub-tab ``key`` (for ``trip_id`` when given)."""
        self._ensure_main_ui()
        if self.workspace is None:
            if not self.can(*WORKSPACE_PERMISSIONS):
                messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"),
                                     _t(f'{_M}.dialogs.no_workspace', default="You don't have access to the Trip Workspace."))
                return
            self.add_workspace_tab()
        self._select_tab('workspace')
        self.workspace.select(key, trip_id)

    def open_selected_in_workspace(self):
        trip_id = self._selected_trip_id()
        self.open_workspace('approvals', trip_id)

    # ------------------------------------------------------------------
    # All Trips
    # ------------------------------------------------------------------
    def refresh_trips(self):
        """Reload every trip (one read) and show those passing the filters."""
        self.update_status(_t(f'{_M}.status.loading', default="Loading trips..."))
        try:
            self._all_trips = tm('trips').list_trips(include_archived=True)
        except Exception as exc:
            show_error(self.root, exc)
            self._all_trips = []
        self.filter_trips()

    def filter_trips(self, *args):
        """Filter the loaded trips by status, start date range and search text."""
        if not hasattr(self, 'trips_tree'):
            return
        status = self._status_filters.get(self.status_filter_var.get(), ALL_CURRENT)
        date_from = (self.date_from_var.get() or '').strip()
        date_to = (self.date_to_var.get() or '').strip()
        term = (self.search_var.get() or '').strip().lower()
        shown = []
        for trip in self._all_trips:
            if status == ALL_CURRENT and trip['status'] == 'archived':
                continue
            if status not in (ALL_CURRENT, ALL_INCL_ARCHIVED):
                legacy = 'planning' if status == 'proposed' else None
                if trip['status'] not in (status, legacy):
                    continue
            start = str(trip.get('start_date') or '')
            if len(date_from) == 10 and start < date_from:
                continue
            if len(date_to) == 10 and start > date_to:
                continue
            if term and term not in " ".join(str(trip.get(k) or '') for k in (
                    'trip_name', 'destination', 'status', 'start_date', 'end_date', 'cost',
                    'organising_club', 'country')).lower():
                continue
            shown.append(trip)
        self.trips_tree.delete(*self.trips_tree.get_children())
        for trip in shown:
            self.trips_tree.insert('', 'end', text=str(trip['id']), values=(
                trip['trip_name'], trip.get('destination') or '', trip.get('start_date') or '',
                f"{trip.get('current_participants') or 0}/{trip.get('max_participants') or 0}",
                money(trip.get('cost')), title_case(trip.get('status'), "Unknown")))
        if term or date_from or date_to or status != ALL_CURRENT:
            self.update_status(tf(f'{_M}.status.found', "Found {n} trip(s)", n=len(shown)))
        else:
            self.update_status(tf(f'{_M}.status.loaded', "Loaded {n} trips", n=len(shown)))

    def _selected_trip_id(self):
        selection = self.trips_tree.selection() if hasattr(self, 'trips_tree') else ()
        return parse_trip_id(self.trips_tree.item(selection[0])['text']) if selection else None

    def on_trip_double_click(self, event):
        trip_id = self._selected_trip_id()
        if trip_id:
            self.show_trip_details(trip_id)

    def show_trip_details(self, trip_id):
        """Show detailed trip information"""
        self.open_trip_details(trip_id)

    def create_trips_context_menu(self):
        """Context menu for the trips list (entries follow permissions)."""
        self.trips_context_menu = tk.Menu(self.root, tearoff=0)
        self.trips_context_menu.add_command(label=_t(f'{_M}.menus.view_details', default="View Details"), command=self.view_selected_trip_details)
        self.trips_context_menu.add_command(label=_t(f'{_M}.menus.view_itinerary', default="View Itinerary"), command=self.view_trip_itinerary)
        if self.can('register_for_trips'):
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.register_for_trip', default="Register for Trip"), command=self.register_for_selected_trip)
        if self.can('manage_trips', 'create_trips'):
            self.trips_context_menu.add_separator()
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.add_edit_itinerary', default="Add/Edit Itinerary"), command=self.add_trip_itinerary)
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.edit_trip', default="Edit Trip"), command=self.edit_selected_trip)
        if self.can(*WORKSPACE_PERMISSIONS):
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.open_workspace', default="Open in Workspace"), command=self.open_selected_in_workspace)
        if self.can('manage_trips'):
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.assign_staff', default="Assign Staff"), command=self.assign_staff_to_selected_trip)
        if self.can('manage_trips', 'create_trips'):
            self.trips_context_menu.add_command(label=_t(f'{_M}.menus.delete_trip', default="Delete Trip"), command=self.delete_selected_trip)
        self.trips_tree.bind("<Button-3>", self.show_trips_context_menu)

    def show_trips_context_menu(self, event):
        row = self.trips_tree.identify_row(event.y)
        if row:
            self.trips_tree.selection_set(row)
        if self.trips_tree.selection():
            self.trips_context_menu.post(event.x_root, event.y_root)

    def view_selected_trip_details(self):
        trip_id = self._selected_trip_id()
        if trip_id:
            self.show_trip_details(trip_id)

    def register_for_selected_trip(self):
        """Register through the domain (capacity, status and duplicates are checked there)."""
        trip_id = self._selected_trip_id()
        if trip_id:
            RegisterForTripDialog(self.root, self.auth, trip_id, self.after_change, None)

    def edit_selected_trip(self):
        trip_id = self._selected_trip_id()
        if trip_id:
            UpdateTripDialog(self.root, self.auth, trip_id, self.after_change)

    def delete_selected_trip(self):
        """Archive the selected trip (records are kept)."""
        trip_id = self._selected_trip_id()
        if trip_id:
            self.confirm_delete_trip(trip_id)

    def assign_staff_to_selected_trip(self):
        trip_id = self._selected_trip_id()
        if trip_id:
            AssignStaffDialog(self.root, self.auth, trip_id, self.after_change)

    # ------------------------------------------------------------------
    # Registration and My Trips
    # ------------------------------------------------------------------
    def load_available_trips(self):
        """Trips taking registrations (open, or full with a waiting list)."""
        if not hasattr(self, 'reg_tree'):
            return
        self.reg_tree.delete(*self.reg_tree.get_children())
        term = (self.reg_search_var.get() if hasattr(self, 'reg_search_var') else '').strip().lower()
        try:
            trips = [t for t in tm('trips').list_trips() if t['status'] in ('open', 'full')]
        except Exception as exc:
            show_error(self.root, exc)
            return
        for trip in trips:
            if term and term not in f"{trip['trip_name']} {trip.get('destination')} {trip.get('start_date')}".lower():
                continue
            left = (trip.get('max_participants') or 0) - (trip.get('current_participants') or 0)
            spaces = str(left) if left > 0 else _t(f'{_M}.labels.full_waitlist', default="Full - waiting list")
            self.reg_tree.insert('', 'end', text=str(trip['id']), values=(
                trip['trip_name'], trip.get('destination') or '', trip['start_date'], money(trip.get('cost')), spaces))

    def show_create_trip(self):
        if not self.can('create_trips', 'manage_trips'):
            messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"), _t(f'{_M}.dialogs.you_don_t_have_permission_to_create_trips', default="You don't have permission to create trips."))
            return
        CreateTripDialog(self.root, self.auth, self.after_change)

    def register_for_trip(self):
        selection = self.reg_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_a_trip_to_register_for', default="Please select a trip to register for."))
            return
        trip_id = self.reg_tree.item(selection[0])['text']
        RegisterForTripDialog(self.root, self.auth, trip_id, self.after_change, None)

    def load_my_trips(self):
        """The user's registrations, with waiting-list place, offer and amount owed."""
        if not hasattr(self, 'my_trips_tree') or not self.auth.current_user:
            return
        try:
            regs = tm('registrations').list_my_registrations(self.auth)
            places, positions = {}, {}
            with tm('database').read_connection() as c:
                for r in regs:
                    places[r['participant_id']] = tm('registrations').get_participant(r['participant_id'], conn=c) or {}
            for trip_id in {r['trip_id'] for r in regs if r['status'] == 'waitlisted'}:
                for w in tm('waitlist').positions(trip_id):
                    positions[w['participant_id']] = w['place']
        except Exception as exc:
            show_error(self.root, exc)
            return
        money_mod = tm('money')
        self._my_regs = {}
        for r in regs:
            place = places.get(r['participant_id']) or {}
            owed = (money_mod.amount_owed(place, {'cost': r['cost']})
                    if r['status'] in ('registered', 'offered', 'confirmed', 'attended') else 0.0)
            if r['status'] == 'waitlisted':
                note = tf(f'{_M}.labels.waitlist_place', "Waiting list #{n}", n=positions.get(r['participant_id'], '?'))
            elif r['status'] == 'offered':
                note = tf(f'{_M}.labels.offer_until', "Place offered — accept by {when}",
                          when=(place.get('offer_expires_at') or '')[:16])
            else:
                note = ''
            self._my_regs[str(r['participant_id'])] = dict(r, owed=owed, note=note)
        self._fill_my_trips()

    def _fill_my_trips(self):
        if not hasattr(self, 'my_trips_tree'):
            return
        self.my_trips_tree.delete(*self.my_trips_tree.get_children())
        term = (self.my_search_var.get() if hasattr(self, 'my_search_var') else '').strip().lower()
        for iid, r in self._my_regs.items():
            if term and term not in f"{r['trip_name']} {r.get('destination')} {r['status']} {r.get('start_date')}".lower():
                continue
            self.my_trips_tree.insert('', 'end', iid=iid, text=str(r['trip_id']),
                                      tags=('offered',) if r['status'] == 'offered' else (), values=(
                r['trip_name'], r.get('destination') or '', r.get('start_date') or '', money(r.get('cost')),
                title_case(r.get('payment_status'), "Unknown"), title_case(r.get('status'), "Unknown"),
                r['note'], money(r['owed']) if r['owed'] else ''))

    def _selected_my_reg(self, warn=True):
        selection = self.my_trips_tree.selection() if hasattr(self, 'my_trips_tree') else ()
        reg = self._my_regs.get(selection[0]) if selection else None
        if reg is None and warn:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"),
                                   _t(f'{_M}.dialogs.please_select_a_registration', default="Please select a registration in My Trips."))
        return reg

    def _with_my_reg(self, action):
        reg = self._selected_my_reg()
        if reg:
            action(reg)

    def cancel_trip_registration(self):
        """Cancel selected registration (shows the refund due)."""
        reg = self._selected_my_reg(warn=False)
        if not reg:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_a_registration_to_cancel', default="Please select a registration to cancel."))
            return
        CancelRegistrationDialog(self.root, self.auth, reg['trip_id'], reg['trip_name'],
                                 reg.get('payment_status') or '', self.after_change,
                                 participant_id=reg['participant_id'])

    def cancel_registration(self):
        """Cancel selected registration"""
        self.cancel_trip_registration()

    def cancel_selected_registration(self):
        """Menu action to cancel registration from My Trips"""
        if self._select_tab('my_trips'):
            self.root.after(100, self._check_and_cancel_registration)
        else:
            messagebox.showinfo(_t(f'{_M}.dialogs.tab_not_available', default="Tab Not Available"), _t(f'{_M}.dialogs.please_go_to_the_my_trips_tab_and_select_a_registration_to_cance', default="Please go to the My Trips tab and select a registration to cancel."))

    def _check_and_cancel_registration(self):
        if self._selected_my_reg(warn=False):
            self.cancel_trip_registration()
        else:
            messagebox.showinfo(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_a_registration_from_the_my_trips_tab_first', default="Please select a registration from the My Trips tab first."))

    def accept_offer(self):
        reg = self._selected_my_reg()
        if not reg:
            return
        ok, place = call(self.root, tm('waitlist').accept_offer, self.auth, reg['participant_id'])
        if not ok:
            return
        self.after_change()
        if float(reg.get('cost') or 0) > 0 and messagebox.askyesno(
                _t(f'{_M}.dialogs.place_accepted', default="Place Accepted"),
                tf(f'{_M}.dialogs.pay_now', "The place on {trip} is yours. Pay {amount} now?",
                   trip=reg['trip_name'], amount=money(reg.get('cost')))):
            PayDialog(self.root, self.auth, reg['participant_id'], self.after_change)

    def decline_offer(self):
        reg = self._selected_my_reg()
        if reg and messagebox.askyesno(_t(f'{_M}.dialogs.decline', default="Decline Offer"),
                                       tf(f'{_M}.dialogs.decline_confirm', "Turn down the place on {trip}? It goes to the next person waiting.",
                                          trip=reg['trip_name'])):
            auth, pid = self.auth, reg['participant_id']
            run_async(self.root, lambda: tm('waitlist').decline_offer(auth, pid), lambda _r: self.after_change())

    def pay_for_selected(self):
        self._with_my_reg(lambda r: PayDialog(self.root, self.auth, r['participant_id'], self.after_change))

    def my_health_details(self):
        self._with_my_reg(lambda r: HealthDetailsDialog(self.root, self.auth, r['participant_id'], own=True))

    def my_travel_documents(self):
        self._with_my_reg(lambda r: DocumentsDialog(self.root, self.auth, r['participant_id'], r['trip_name']))

    def accept_code_of_conduct(self):
        reg = self._selected_my_reg()
        if reg and messagebox.askyesno(
                _t(f'{_M}.dialogs.conduct', default="Code of Conduct"),
                tf(f'{_M}.dialogs.conduct_text',
                   "I have read the trip code of conduct for {trip} and agree to follow it, and to follow the "
                   "instructions of the trip leaders.", trip=reg['trip_name'])):
            ok, _ = call(self.root, tm('safeguarding').record_conduct_acceptance, self.auth, reg['participant_id'])
            if ok:
                messagebox.showinfo(_t(f'{_M}.dialogs.conduct', default="Code of Conduct"),
                                    _t(f'{_M}.dialogs.conduct_recorded', default="Thank you — recorded."))

    def report_incident_on_selected(self):
        self._with_my_reg(lambda r: ReportIncidentDialog(self.root, self.auth, r['trip_id']))

    def report_incident(self):
        """Menu: pick a trip (yours, or any for staff) and report an incident on it."""
        TripSelectionDialog(self.root, self.auth, lambda trip_id: ReportIncidentDialog(
            self.root, self.auth, trip_id, staff=tm('trips').can_manage_trip(self.auth, trip_id)))

    def evaluate_selected(self):
        self._with_my_reg(lambda r: EvaluateDialog(self.root, self.auth, r['trip_id'], r['trip_name']))

    # ------------------------------------------------------------------
    # Administration
    # ------------------------------------------------------------------
    def _trip_options(self):
        try:
            return [f"{t['id']} - {t['trip_name']} ({t.get('destination') or ''}) [{t['start_date']}]"
                    for t in tm('trips').list_trips(include_archived=True)]
        except Exception as exc:
            show_error(self.root, exc)
            return []

    def setup_participants_management(self, parent):
        trip_select_frame = ttk.Frame(parent)
        trip_select_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(trip_select_frame, text=_t(f'{_M}.labels.select_trip', default="Select Trip:")).pack(side=tk.LEFT, padx=(0, 5))
        self.participant_trip_var = tk.StringVar()
        self.participant_trip_combo = ttk.Combobox(trip_select_frame, textvariable=self.participant_trip_var, state='readonly')
        self.participant_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.participant_trip_combo.bind('<<ComboboxSelected>>', lambda _e: self.load_trip_participants())
        ttk.Button(trip_select_frame, text=_t(f'{_M}.buttons.load_participants', default="Load Participants"),
                   command=self.load_trip_participants).pack(side=tk.LEFT)
        ttk.Label(trip_select_frame, text=_t(f'{_M}.labels.search', default="Search:")).pack(side=tk.LEFT, padx=(10, 3))
        self.participant_search_var = tk.StringVar()
        self.participant_search_var.trace_add('write', lambda *_: self._fill_participants())
        ttk.Entry(trip_select_frame, textvariable=self.participant_search_var, width=18).pack(side=tk.LEFT)

        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(buttons_frame, text=_t(f'{_M}.buttons.update_payment', default="Update Payment"),
                   command=self.update_payment_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_t(f'{_M}.buttons.update_status', default="Update Status"),
                   command=self.update_participant_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t(f'{_M}.buttons.remove_participant', default="Remove Participant"),
                   command=self.remove_participant).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t(f'{_M}.buttons.medical_sheet', default="Medical & Dietary (restricted)"),
                   command=self.show_participant_medical).pack(side=tk.LEFT, padx=5)

        self.participants_tree = ttk.Treeview(parent, columns=('name', 'email', 'registration', 'payment', 'status'), show='tree headings')
        self.participants_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.participants_tree.heading('name', text=_t(f'{_M}.headings.name', default='Name'))
        self.participants_tree.heading('email', text=_t(f'{_M}.headings.email', default='Email'))
        self.participants_tree.heading('registration', text=_t(f'{_M}.headings.registration_date', default='Registration Date'))
        self.participants_tree.heading('payment', text=_t(f'{_M}.headings.payment_status', default='Payment Status'))
        self.participants_tree.heading('status', text=_t(f'{_M}.headings.status', default='Status'))
        self.participants_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._participants = []
        self.load_trips_for_management()

    def setup_staff_assignment(self, parent):
        ttk.Label(parent, text=_t(f'{_M}.labels.staff_assignment', default="Staff Assignment"), font=('Arial', 12, 'bold')).pack(pady=10)
        staff_trip_frame = ttk.Frame(parent)
        staff_trip_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(staff_trip_frame, text=_t(f'{_M}.labels.select_trip', default="Select Trip:")).pack(side=tk.LEFT, padx=(0, 5))
        self.staff_trip_var = tk.StringVar()
        self.staff_trip_combo = ttk.Combobox(staff_trip_frame, textvariable=self.staff_trip_var, state='readonly')
        self.staff_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.staff_trip_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_trip_staff())

        staff_buttons_frame = ttk.Frame(parent)
        staff_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(staff_buttons_frame, text=_t(f'{_M}.buttons.assign_staff', default="Assign Staff"),
                   command=self.assign_staff).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(staff_buttons_frame, text=_t(f'{_M}.buttons.remove_staff', default="Remove Staff"),
                   command=self.remove_staff).pack(side=tk.LEFT)

        self.staff_tree = ttk.Treeview(parent, columns=('staff_name', 'role', 'assigned_date', 'first_aider', 'dbs'), show='tree headings')
        self.staff_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.staff_tree.heading('staff_name', text=_t(f'{_M}.headings.staff_name', default='Staff Name'))
        self.staff_tree.heading('role', text=_t(f'{_M}.headings.role', default='Role'))
        self.staff_tree.heading('assigned_date', text=_t(f'{_M}.headings.assigned_date', default='Assigned Date'))
        self.staff_tree.heading('first_aider', text=_t(f'{_M}.headings.first_aider', default='First Aider'))
        self.staff_tree.heading('dbs', text=_t(f'{_M}.headings.dbs', default='DBS'))
        self.staff_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.load_staff_trip_options()

    def setup_expenses_management(self, parent):
        ttk.Label(parent, text=_t(f'{_M}.labels.expense_management', default="Expense Management"), font=('Arial', 12, 'bold')).pack(pady=10)
        expense_trip_frame = ttk.Frame(parent)
        expense_trip_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(expense_trip_frame, text=_t(f'{_M}.labels.select_trip', default="Select Trip:")).pack(side=tk.LEFT, padx=(0, 5))
        self.expense_trip_var = tk.StringVar()
        self.expense_trip_combo = ttk.Combobox(expense_trip_frame, textvariable=self.expense_trip_var, state='readonly')
        self.expense_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.expense_trip_combo.bind('<<ComboboxSelected>>', lambda _e: self.load_trip_expenses())
        ttk.Button(expense_trip_frame, text=_t(f'{_M}.buttons.load_expenses', default="Load Expenses"),
                   command=self.load_trip_expenses).pack(side=tk.LEFT)
        ttk.Label(expense_trip_frame, text=_t(f'{_M}.labels.search', default="Search:")).pack(side=tk.LEFT, padx=(10, 3))
        self.expense_search_var = tk.StringVar()
        self.expense_search_var.trace_add('write', lambda *_: self._fill_expenses())
        ttk.Entry(expense_trip_frame, textvariable=self.expense_search_var, width=18).pack(side=tk.LEFT)

        expense_buttons_frame = ttk.Frame(parent)
        expense_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(expense_buttons_frame, text=_t(f'{_M}.buttons.add_expense', default="Add Expense"),
                   command=self.add_expense).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(expense_buttons_frame, text=_t(f'{_M}.buttons.edit_expense', default="Edit Expense"),
                   command=self.edit_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(expense_buttons_frame, text=_t(f'{_M}.buttons.delete_expense', default="Delete Expense"),
                   command=self.delete_expense).pack(side=tk.LEFT, padx=5)
        self.expense_total_var = tk.StringVar()
        ttk.Label(expense_buttons_frame, textvariable=self.expense_total_var).pack(side=tk.LEFT, padx=10)

        self.expenses_tree = ttk.Treeview(parent, columns=('category', 'description', 'amount', 'date', 'recorded_by'), show='tree headings')
        self.expenses_tree.heading('#0', text=_t(f'{_M}.headings.id', default='ID'))
        self.expenses_tree.heading('category', text=_t(f'{_M}.headings.category', default='Category'))
        self.expenses_tree.heading('description', text=_t(f'{_M}.headings.description', default='Description'))
        self.expenses_tree.heading('amount', text=_t(f'{_M}.headings.amount', default='Amount'))
        self.expenses_tree.heading('date', text=_t(f'{_M}.headings.date', default='Date'))
        self.expenses_tree.heading('recorded_by', text=_t(f'{_M}.headings.recorded_by', default='Recorded By'))
        self.expenses_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._expenses = []

    def setup_trip_management(self, parent):
        ttk.Label(parent, text=_t(f'{_M}.labels.trip_management', default="Trip Management"), font=('Arial', 12, 'bold')).pack(pady=10)
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=10)
        ttk.Button(actions_frame, text=_t(f'{_M}.buttons.update_trip', default="Update Trip"),
                   command=self.update_trip).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(actions_frame, text=_t(f'{_M}.buttons.delete_trip', default="Delete Trip"),
                   command=self.delete_trip).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text=_t(f'{_M}.buttons.manage_itinerary', default="Manage Itinerary"),
                   command=self.manage_itinerary).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text=_t(f'{_M}.buttons.change_status', default="Approvals && Status..."),
                   command=lambda: TripSelectionDialog(self.root, self.auth, lambda tid: self.open_workspace('approvals', tid),
                                                       purpose='manage')).pack(side=tk.LEFT, padx=5)
        summary_frame = ttk.LabelFrame(parent, text=_t(f'{_M}.labels.trip_summary', default="Trip Summary"), padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.trip_summary_text = scrolledtext.ScrolledText(summary_frame, height=15)
        self.trip_summary_text.pack(fill=tk.BOTH, expand=True)
        self.load_trip_summary()

    def load_trips_for_management(self):
        """Refresh the trip pickers on the Administration tabs (keeping each selection)."""
        trip_list = self._trip_options()
        for name in ('participant_trip_combo', 'expense_trip_combo', 'staff_trip_combo'):
            combo = getattr(self, name, None)
            if combo is not None:
                try:
                    combo['values'] = trip_list
                except tk.TclError:
                    pass

    def show_trips_view(self):
        """Menu action: go to the All Trips tab and refresh."""
        if self._select_tab('all_trips'):
            try:
                self.refresh_trips()
            except Exception as e:
                logger.warning(f"Failed to refresh trips view: {e}")

    def show_my_registrations(self):
        """Menu action: go to My Trips; create it if permissions allow."""
        self._ensure_main_ui()
        if 'my_trips' not in self._tabs and self.can('view_own_trip_registrations'):
            self.add_my_trips_tab()
        self._select_tab('my_trips')

    def _combo_trip_id(self, var):
        return parse_trip_id(var.get()) if var.get() else None

    def load_trip_participants(self):
        """Participants of the selected trip (``registrations.list_participants``)."""
        trip_id = self._combo_trip_id(self.participant_trip_var)
        if trip_id is None:
            return
        ok, people = call(self.root, tm('registrations').list_participants, self.auth, trip_id, include_ended=True)
        self._participants = people if ok else []
        self._fill_participants()

    def _fill_participants(self):
        self.participants_tree.delete(*self.participants_tree.get_children())
        term = self.participant_search_var.get().strip().lower()
        for p in self._participants:
            if term and term not in f"{p.get('name')} {p.get('email')} {p.get('student_id')} {p.get('status')}".lower():
                continue
            # Staff registrations have no student number: their user name is shown.
            name = p.get('name') or p.get('student_id') or f"Participant {p['id']}"
            self.participants_tree.insert('', 'end', text=str(p['id']), values=(
                name, p.get('email') or "N/A", p.get('registration_date') or '',
                title_case(p.get('payment_status')), title_case(p.get('status'))))

    def load_trip_expenses(self):
        trip_id = self._combo_trip_id(self.expense_trip_var)
        if trip_id is None:
            return
        ok, rows = call(self.root, tm('expenses').list_expenses, self.auth, trip_id)
        self._expenses = rows if ok else []
        self._fill_expenses()

    def _fill_expenses(self):
        self.expenses_tree.delete(*self.expenses_tree.get_children())
        term = self.expense_search_var.get().strip().lower()
        total = 0.0
        for e in self._expenses:
            if term and term not in f"{e['category']} {e['description']} {e['date']} {e.get('recorded_by')}".lower():
                continue
            total += float(e['amount'] or 0)
            self.expenses_tree.insert('', 'end', text=str(e['id']), values=(
                e['category'], e['description'], money(e['amount']), e['date'], e.get('recorded_by') or "Unknown"))
        self.expense_total_var.set(tf(f'{_M}.labels.expense_total', "Total shown: {total}", total=money(total)))

    def load_trip_summary(self):
        """Trip and participant statistics (domain reads)."""
        if not hasattr(self, 'trip_summary_text'):
            return
        try:
            trips = tm('trips').list_trips(include_archived=True)
            from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import TripReportGenerator
            with tm('database').read_connection() as conn:
                stats = TripReportGenerator(self.auth).get_trip_summary_data(conn)['participant_stats']
            pending = len(tm('approvals').pending_for(self.auth)) if self.can(*APPROVER_PERMISSIONS) else None
        except Exception as exc:
            logger.warning("trip summary failed: %s", exc)
            return
        by_status = {}
        for t in trips:
            status = 'proposed' if t['status'] == 'planning' else t['status']
            by_status[status] = by_status.get(status, 0) + 1
        live = [t for t in trips if t['status'] not in ('cancelled', 'archived')]
        income_due = sum(float(t.get('cost') or 0) * (t.get('current_participants') or 0) for t in live)
        avg_cost = (sum(float(t.get('cost') or 0) for t in live) / len(live)) if live else 0.0
        lines = ["TRIP MANAGEMENT SUMMARY", "=" * 50, "", "TRIP STATISTICS:",
                 f"Total Trips: {len(trips)}"]
        lines += [f"{title_case(s)}: {by_status.get(s, 0)}" for s in
                  ('proposed', 'approved', 'open', 'full', 'closed', 'in_progress', 'completed', 'cancelled', 'archived')]
        lines += [f"Fees from places taken (current trips): {money(income_due)}",
                  f"Average Trip Cost: {money(avg_cost)}", ""]
        if pending is not None:
            lines += [f"Approval decisions waiting for you: {pending}", ""]
        if stats:
            lines += ["PARTICIPANT STATISTICS:", f"Total Registrations: {stats[0]}",
                      f"Active Registrations: {stats[1]}", f"Cancelled Registrations: {stats[2]}",
                      f"Paid Registrations: {stats[3]}", f"Pending Payments: {stats[4]}"]
        self.trip_summary_text.delete(1.0, tk.END)
        self.trip_summary_text.insert(1.0, "\n".join(lines) + "\n")

    def generate_trip_summary_report(self):
        if not self.can('view_trip_reports'):
            messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"), _t(f'{_M}.dialogs.you_don_t_have_permission_to_generate_reports', default="You don't have permission to generate reports."))
            return
        ReportGeneratorDialog(self.root, self.auth, 'TRIP_SUMMARY', getattr(self, 'report_log', None))

    def generate_participant_report(self):
        if not self.can('view_trip_reports'):
            messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"), _t(f'{_M}.dialogs.you_don_t_have_permission_to_generate_reports', default="You don't have permission to generate reports."))
            return
        ReportGeneratorDialog(self.root, self.auth, 'PARTICIPANT_LIST', getattr(self, 'report_log', None))

    def generate_financial_report(self):
        if not self.can('view_financial_reports'):
            messagebox.showerror(_t(f'{_M}.dialogs.permission_denied', default="Permission Denied"), _t(f'{_M}.dialogs.you_don_t_have_permission_to_view_financial_reports', default="You don't have permission to view financial reports."))
            return
        ReportGeneratorDialog(self.root, self.auth, 'FINANCIAL_REPORT', getattr(self, 'report_log', None))

    def _selected_participant_id(self):
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_a_participant', default="Please select a participant."))
            return None
        return int(self.participants_tree.item(selection[0])['text'])

    def update_payment_status(self):
        pid = self._selected_participant_id()
        if pid:
            PaymentStatusDialog(self.root, self.auth, pid, self.after_change)

    def update_participant_status(self):
        pid = self._selected_participant_id()
        if pid:
            ParticipantStatusDialog(self.root, self.auth, pid, self.after_change)

    def remove_participant(self):
        """Take someone off a trip (status 'removed'; the row and any refund are kept)."""
        pid = self._selected_participant_id()
        if not pid:
            return
        name = self.participants_tree.item(self.participants_tree.selection()[0])['values'][0]
        if not messagebox.askyesno(_t(f'{_M}.dialogs.confirm_removal', default="Confirm Removal"),
                                   tf(f'{_M}.dialogs.remove_confirm',
                                      "Remove '{name}' from this trip? Their registration is kept as 'removed' "
                                      "and anything they paid is refunded.", name=name)):
            return
        auth = self.auth

        def done(outcome):
            refund = (outcome or {}).get('refund') or {}
            extra = (f"\n\nRefund: {money(refund.get('amount'))} "
                     f"({'raised' if refund.get('success') else refund.get('message') or 'not needed'})"
                     if refund else "")
            messagebox.showinfo(_t(f'{_M}.dialogs.success', default="Success"),
                                _t(f'{_M}.dialogs.participant_removed_successfully', default="Participant removed successfully") + extra)
            self.after_change()

        run_async(self.root, lambda: tm('registrations').remove_participant_record(auth, pid), done)

    def show_participant_medical(self):
        trip_id = self._combo_trip_id(self.participant_trip_var)
        if trip_id is None:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_trip_selected', default="No Trip Selected"), _t(f'{_M}.dialogs.please_select_a_trip_first', default="Please select a trip first."))
            return
        show_medical_sheet(self.root, self.auth, trip_id)

    def assign_staff(self):
        trip_id = self._combo_trip_id(self.staff_trip_var)
        if trip_id is None:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_trip_selected', default="No Trip Selected"), _t(f'{_M}.dialogs.please_select_a_trip_first', default="Please select a trip first."))
            return
        AssignStaffDialog(self.root, self.auth, trip_id, self.after_change)

    def remove_staff(self):
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return
        trip_id = self._combo_trip_id(self.staff_trip_var)
        assignment_id = int(self.staff_tree.item(selection[0])['text'])
        staff_name = self.staff_tree.item(selection[0])['values'][0]
        if messagebox.askyesno(_t(f'{_M}.dialogs.confirm_removal', default="Confirm Removal"), f"Are you sure you want to remove '{staff_name}' from this trip?"):
            ok, _ = call(self.root, tm('staff').unassign_staff_member, self.auth, trip_id, assignment_id)
            if ok:
                messagebox.showinfo(_t(f'{_M}.dialogs.success', default="Success"), _t(f'{_M}.dialogs.staff_member_removed_successfully', default="Staff member removed successfully"))
                self.after_change()

    def load_trip_staff(self):
        """Staff on the selected trip."""
        trip_id = self._combo_trip_id(self.staff_trip_var)
        if trip_id is None:
            return
        self.staff_tree.delete(*self.staff_tree.get_children())
        try:
            staff = list_trip_staff(trip_id)
        except Exception as exc:
            show_error(self.root, exc)
            return
        for s in staff:
            self.staff_tree.insert('', 'end', text=str(s['id']), values=(
                s['name'], title_case(s['role']), s.get('assigned_date') or '',
                'yes' if s.get('first_aider') else '', title_case(s.get('dbs_status'), 'not checked')))

    def load_staff_trip_options(self):
        """Populate the staff tab's trip picker (keeping the selection)."""
        display_values = self._trip_options()
        self.staff_trip_combo['values'] = display_values
        current = self._combo_trip_id(self.staff_trip_var)
        keep = next((v for v in display_values if parse_trip_id(v) == current), None)
        if keep:
            self.staff_trip_combo.set(keep)
        elif display_values:
            self.staff_trip_combo.set(display_values[0])
        self.load_trip_staff()

    def add_expense(self):
        trip_id = self._combo_trip_id(self.expense_trip_var)
        if trip_id is None:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_trip_selected', default="No Trip Selected"), _t(f'{_M}.dialogs.please_select_a_trip_first', default="Please select a trip first."))
            return
        AddExpenseDialog(self.root, self.auth, trip_id, self.after_change)

    def _selected_expense(self):
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f'{_M}.dialogs.no_selection', default="No Selection"), _t(f'{_M}.dialogs.please_select_an_expense', default="Please select an expense."))
            return None
        expense_id = int(self.expenses_tree.item(selection[0])['text'])
        return next((e for e in self._expenses if e['id'] == expense_id), None)

    def edit_expense(self):
        expense = self._selected_expense()
        if expense:
            EditExpenseDialog(self.root, self.auth, self._combo_trip_id(self.expense_trip_var), expense, self.after_change)

    def delete_expense(self):
        expense = self._selected_expense()
        if expense and messagebox.askyesno(_t(f'{_M}.dialogs.confirm_deletion', default="Confirm Deletion"), f"Are you sure you want to delete expense '{expense['description']}'?"):
            ok, _ = call(self.root, tm('expenses').remove_expense, self.auth,
                         self._combo_trip_id(self.expense_trip_var), expense['id'])
            if ok:
                messagebox.showinfo(_t(f'{_M}.dialogs.success', default="Success"), _t(f'{_M}.dialogs.expense_deleted_successfully', default="Expense deleted successfully"))
                self.after_change()

    # ------------------------------------------------------------------
    # Trip actions
    # ------------------------------------------------------------------
    def _trip_name(self, trip_id):
        """Trip name for an id, or None if it has gone."""
        try:
            trip = tm('trips').get_trip(trip_id)
        except Exception:
            return None
        return trip['trip_name'] if trip else None

    def view_trip(self):
        """Pick a trip and show its details (students: the trips they are on)."""
        TripSelectionDialog(self.root, self.auth, self.open_trip_details)

    def open_trip_details(self, trip_id):
        """Read-only details: the trip, its approvals and — for its organisers —
        participants and counts of the health details recorded."""
        try:
            trip = tm('trips').get_trip(trip_id)
        except Exception as exc:
            show_error(self.root, exc)
            return
        if not trip:
            messagebox.showerror(_t(f'{_M}.dialogs.error', default="Error"),
                                 _t(f'{_M}.dialogs.trip_not_found', default="That trip no longer exists."))
            return
        participants, details = None, {}
        try:
            participants = tm('registrations').list_participants(self.auth, trip_id)
            details['health_counts'] = tm('medical').counts(trip_id)
        except PermissionError:
            participants = None
        except Exception as exc:
            logger.warning("participants for trip %s: %s", trip_id, exc)
        try:
            details['approval'] = tm('approvals').approval_state(trip_id)
            if participants is not None and trip['status'] in ('proposed', 'planning', 'approved', 'full', 'closed'):
                details['problems'] = tm('approvals').gate_problems(trip_id, 'open')
        except Exception as exc:
            logger.warning("approval state for trip %s: %s", trip_id, exc)
        TripDetailsDialog(self.root, trip, participants, details)

    def update_trip(self):
        TripSelectionDialog(self.root, self.auth, self.open_update_trip_dialog, purpose='manage')

    def open_update_trip_dialog(self, trip_id):
        UpdateTripDialog(self.root, self.auth, trip_id, self.after_change)

    def delete_trip(self):
        """Menu: pick a trip and archive it (the trip and its records are kept)."""
        TripSelectionDialog(self.root, self.auth, self.confirm_delete_trip, purpose='manage')

    def confirm_delete_trip(self, trip_id):
        """Archive a trip through ``trips.archive_trip`` — nothing is deleted.

        Places still held are released, paid participants refunded and the
        people who held a place e-mailed — all by the domain.
        """
        try:
            trip = tm('trips').get_trip(trip_id)
        except Exception as exc:
            show_error(self.root, exc)
            return
        if not trip:
            return
        if not messagebox.askyesno(
                _t(f'{_M}.dialogs.confirm_deletion', default="Confirm Deletion"),
                tf(f'{_M}.dialogs.archive_confirm',
                   "Delete trip '{name}'?\n\nThe trip is archived, not erased: its participants, payments, "
                   "expenses and history are kept. Any places still held are released and paid "
                   "participants are refunded.", name=trip['trip_name'])):
            return
        auth = self.auth

        def work():
            # archive_trip e-mails everyone whose place it releases.
            result = tm('trips').archive_trip(auth, trip_id)
            return result, result.get('emailed') or 0

        def done(outcome):
            result, sent = outcome
            refunds = result.get('refunds') or []
            text = _t(f'{_M}.dialogs.trip_archived', default="Trip archived; its records are kept.")
            if refunds:
                failed = [r for r in refunds if not r.get('success')]
                text += "\n\n" + tf(f'{_M}.dialogs.refunds', "{n} refund(s) processed, {failed} failed.",
                                    n=len(refunds), failed=len(failed))
            if sent:
                text += "\n\n" + tf(f'{_M}.dialogs.emailed', "{n} participant(s) emailed.", n=sent)
            messagebox.showinfo(_t(f'{_M}.dialogs.success', default="Success"), text)
            self.after_change()

        run_async(self.root, work, done, status=self.update_status)

    def view_trip_itinerary(self):
        """Itinerary of the selected trip (or pick one)."""
        trip_id = self._selected_trip_id()
        if trip_id:
            ViewItineraryDialog(self.root, trip_id)
        else:
            TripSelectionDialog(self.root, self.auth, lambda tid: ViewItineraryDialog(self.root, tid))

    def add_trip_itinerary(self):
        trip_id = self._selected_trip_id()
        if trip_id:
            ItineraryDialog(self.root, self.auth, trip_id)
        else:
            self.manage_itinerary()

    def assign_trip_staff(self):
        """Admin > Assign Trip Staff: pick one trip and assign staff to it."""
        TripSelectionDialog(self.root, self.auth,
                            lambda trip_id: AssignStaffDialog(self.root, self.auth, trip_id, self.after_change),
                            purpose='manage')

    def show_manage_participants(self):
        self._show_admin_subtab('participants')

    def show_assign_staff(self):
        """Admin > Assign Staff: the staff tab (every trip's staff list)."""
        self._show_admin_subtab('staff')

    def show_manage_expenses(self):
        self._show_admin_subtab('expenses')

    def manage_itinerary(self):
        TripSelectionDialog(self.root, self.auth, self.open_itinerary_dialog, purpose='manage')

    def open_itinerary_dialog(self, trip_id):
        ItineraryDialog(self.root, self.auth, trip_id)

    # ------------------------------------------------------------------
    # Refresh after a change
    # ------------------------------------------------------------------
    def after_change(self, source=None):
        """Something was written: refresh every list, picker and summary."""
        for step in (self.refresh_trips, self.load_available_trips, self.load_my_trips,
                     self.load_trips_for_management, self.load_trip_summary):
            try:
                step()
            except Exception:
                logger.debug("refresh step %s failed", getattr(step, '__name__', step), exc_info=True)
        for refresh in (lambda: self._fill_after('participant_trip_var', self.load_trip_participants),
                        lambda: self._fill_after('expense_trip_var', self.load_trip_expenses),
                        lambda: self._fill_after('staff_trip_var', self.load_trip_staff)):
            try:
                refresh()
            except Exception:
                logger.debug("admin list refresh failed", exc_info=True)
        if self.workspace is not None and source is not self.workspace:
            try:
                self.workspace.refresh_all()
            except Exception:
                logger.debug("workspace refresh failed", exc_info=True)
        tab = getattr(self, 'approvals_tab', None)
        if tab is not None and source is not tab:
            try:
                tab.refresh()
            except Exception:
                logger.debug("approvals refresh failed", exc_info=True)

    def _fill_after(self, var_name, loader):
        var = getattr(self, var_name, None)
        if var is not None and var.get():
            loader()

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------
    def show_trips_with_calendar(self):
        if not self.calendar_manager:
            messagebox.showerror(_t(f'{_M}.dialogs.calendar_unavailable', default="Calendar Unavailable"), _t(f'{_M}.dialogs.calendar_integration_is_not_available', default="Calendar integration is not available."))
            return
        self.calendar_tree.delete(*self.calendar_tree.get_children())
        try:
            trips = tm('trips').list_trips()
        except Exception as exc:
            show_error(self.root, exc)
            return
        links = calendar_links()
        for trip in trips:
            event = links.get(trip['id'])
            self.calendar_tree.insert('', 'end', text=str(trip['id']), values=(
                trip['trip_name'], event[1] if event else "No Event", trip['start_date'],
                title_case(trip['status'])))

    def view_trip_events_in_calendar(self):
        """View trip events in the calendar (calendar-centric view)"""
        if not CALENDAR_AVAILABLE or not self.calendar_manager:
            messagebox.showwarning(_t(f'{_M}.dialogs.calendar_not_available', default="Calendar Not Available"),
                                   _t(f'{_M}.dialogs.calendar_system_is_not_available', default="Calendar system is not available."))
            return
        try:
            current_date = datetime.now().strftime('%Y-%m-%d')
            future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            events = self.calendar_manager.get_events_by_date_range(current_date, future_date, 'Trip')
            if not events:
                messagebox.showinfo(_t(f'{_M}.dialogs.no_events', default="No Events"), _t(f'{_M}.dialogs.no_trip_events_found_in_calendar_for_the_next_year', default="No trip events found in calendar for the next year."))
                return
            dialog = tk.Toplevel(self.root)
            dialog.title(_t(f'{_M}.windows.trip_events_in_calendar', default="Trip Events in Calendar"))
            dialog.geometry("900x600")
            dialog.transient(self.root)
            ttk.Label(dialog, text=_t(f'{_M}.labels.trip_events_in_calendar', default="Trip Events in Calendar"),
                      font=('Arial', 14, 'bold')).pack(pady=10)
            ttk.Label(dialog, text=f"Showing trip events for next 365 days ({len(events)} events found)",
                      font=('Arial', 9)).pack(pady=(0, 10))
            ttk.Button(dialog, text=_t(f'{_M}.buttons.close', default="Close"), command=dialog.destroy).pack(side=tk.BOTTOM, pady=10)
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            columns = ('event_name', 'start_date', 'end_date', 'description')
            tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)
            tree.heading('event_name', text=_t(f'{_M}.headings.event_name', default='Event Name'))
            tree.heading('start_date', text=_t(f'{_M}.headings.start_date', default='Start Date'))
            tree.heading('end_date', text=_t(f'{_M}.headings.end_date', default='End Date'))
            tree.heading('description', text=_t(f'{_M}.headings.description', default='Description'))
            tree.column('event_name', width=250)
            tree.column('start_date', width=120)
            tree.column('end_date', width=120)
            tree.column('description', width=350)
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            for event in events:
                start_date = event.get('date_start') or event.get('date', 'TBD')
                end_date = event.get('date_end') or event.get('date', 'TBD')
                description = (event.get('description') or 'No description')[:80]
                tree.insert('', tk.END, values=(event.get('name', 'Unnamed Event'), start_date, end_date, description))
            log_read('trip_calendar_events', f"Viewed {len(events)} trip events in calendar")
            self.update_status(f"Showing {len(events)} trip events from calendar")
        except Exception as e:
            logging.error(f"Error viewing trip events in calendar: {e}")
            messagebox.showerror(_t(f'{_M}.dialogs.error', default="Error"), f"Failed to view trip events: {str(e)}")

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------
    def return_to_main_menu(self):
        try:
            if isinstance(self.root, tk.Toplevel):
                self.root.destroy()
            else:
                self.root.destroy()
                from education_system.systems.university.shell.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            logger.error("Error returning to main menu: %s", e, exc_info=True)

    def export_data(self):
        ExportDataDialog(self.root, self.auth)

    def show_about(self):
        AboutDialog(self.root)

    def safe_db_operation(self, operation_func, *args, max_retries=3, **kwargs):
        """Run a read through the package helper (kept for older callers;
        the screens themselves go through the trip domain API)."""
        return module_safe_db_operation(operation_func, *args, **kwargs)

    def get_db_connection(self, timeout=30.0, max_retries=3):
        """A university database connection (kept for older callers)."""
        from education_system.systems.university.infrastructure.database.db import get_connection
        for attempt in range(max_retries):
            try:
                return get_connection(db_path=DEFAULT_DB_PATH, timeout=timeout)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                return None
            except sqlite3.Error:
                return None
        return None

    def run(self):
        if getattr(self, "_owns_root", False):
            self.root.mainloop()
