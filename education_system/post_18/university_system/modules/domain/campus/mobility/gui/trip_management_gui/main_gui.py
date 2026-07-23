from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import (
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
    from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import CalendarConfig, AcademicCalendarManager

from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.trip_dialogs import TripDetailsDialog, CreateTripDialog, UpdateTripDialog, TripSelectionDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.registration_dialogs import CancelRegistrationDialog, RegisterForTripDialog, PaymentStatusDialog, ParticipantStatusDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.itinerary_dialogs import ViewItineraryDialog, ItineraryDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.expense_dialogs import AddExpenseDialog, EditExpenseDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.staff_dialogs import AssignStaffDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.report_dialogs import ReportGeneratorDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.calendar_dialogs import CreateCalendarEventDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.export_dialog import ExportDataDialog
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.about_dialog import AboutDialog

# Import all original functions and classes
# Note: In a real implementation, you would import these from the original file
# For this example, I'll include the essential ones

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
        self.calendar_manager = None
        self.setup_gui()

        # Calendar integration
        if CALENDAR_AVAILABLE and self.auth:
            try:
                config = CalendarConfig()
                self.calendar_manager = AcademicCalendarManager(config=config, auth_manager=self.auth)
            except Exception as e:
                logging.warning(f"Could not initialize calendar system: {e}")

    def setup_gui(self):
        """Initialize the main GUI window"""
        if self.root is None:
            self.root = tk.Tk()
        # It's fine to set title/geometry on a Toplevel as well
        self.root.title(_t("trip.title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)

        # Create main menu
        self.create_menu()

        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Provide a top-corner button for returning to the main menu
        self.create_main_menu_button()

        # Create status bar
        self.status_bar = ttk.Label(self.root, text=_t("common.ready"), relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Check authentication - user must log in through main GUI
        if self.auth and self.auth.current_user:
            self.show_main_interface()
        else:
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI before accessing Trip Management."
            )
            self.root.destroy()

    def create_menu(self):
        """Create the application menu bar with role-based filtering"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Get user role for filtering
        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)

        # Admin/Staff can export data
        if is_admin or is_staff:
            file_menu.add_command(label=_t("trip.menu.export_data"), command=self.export_data)
            file_menu.add_separator()

        file_menu.add_command(label=_t("common.exit"), command=self.root.quit)

        # Trip menu
        trip_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("trip.menu.trips"), menu=trip_menu)
        trip_menu.add_command(label=_t("trip.menu.view_all_trips"), command=self.show_trips_view)

        # Admin/Staff can create trips
        if is_admin or is_staff:
            trip_menu.add_command(label=_t("trip.menu.create_new_trip"), command=self.show_create_trip)

        trip_menu.add_separator()
        trip_menu.add_command(label=_t("trip.menu.my_registrations"), command=self.show_my_registrations)

        # Cross-domain: surface risk-register entries linked to a
        # trip via risk_bus.list_risks_for("trip:N").
        def _show_trip_risks():
            from tkinter import simpledialog
            from education_system.post_18.university_system.modules.services.risks_panel import (
                show_risks_for,
            )
            tid = simpledialog.askstring(
                "Trip risks",
                "Trip ID (numeric):", parent=self.root,
            )
            if not tid:
                return
            show_risks_for(self.root, f"trip:{tid.strip()}",
                           title=f"Risks for trip {tid}")
        trip_menu.add_separator()
        trip_menu.add_command(label="View trip risks",
                              command=_show_trip_risks)

        if self.auth.check_permission('cancel_trip_registration'):
            trip_menu.add_command(label=_t("trip.menu.cancel_registration"), command=self.cancel_selected_registration)

        # Itinerary submenu
        if self.auth.check_permission('view_trips'):
            itinerary_menu = tk.Menu(trip_menu, tearoff=0)
            trip_menu.add_cascade(label=_t("trip.menu.itinerary"), menu=itinerary_menu)
            itinerary_menu.add_command(label=_t("trip.menu.view_trip_itinerary"), command=self.view_trip_itinerary)

            # Admin/Staff can manage itinerary
            if (is_admin or is_staff) and (self.auth.check_permission('manage_trips') or self.auth.check_permission('create_trips')):
                itinerary_menu.add_command(label=_t("trip.menu.manage_itinerary"), command=self.add_trip_itinerary)

        # Reports menu (Admin/Staff only)
        if is_admin or is_staff:
            reports_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.reports"), menu=reports_menu)
            reports_menu.add_command(label=_t("trip.menu.trip_summary"), command=self.generate_trip_summary_report)
            reports_menu.add_command(label=_t("trip.menu.participant_list"), command=self.generate_participant_report)
            reports_menu.add_command(label=_t("trip.menu.financial_report"), command=self.generate_financial_report)

        # Admin menu (Admin only)
        if is_admin and self.auth and self.auth.current_user and self.auth.check_permission('manage_trips'):
            admin_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.admin"), menu=admin_menu)
            admin_menu.add_command(label=_t("trip.menu.manage_participants"), command=self.show_manage_participants)
            admin_menu.add_command(label=_t("trip.menu.assign_staff"), command=self.show_assign_staff)
            admin_menu.add_command(label=_t("trip.menu.manage_expenses"), command=self.show_manage_expenses)
            admin_menu.add_separator()
            admin_menu.add_command(label=_t("trip.menu.assign_trip_staff"), command=self.assign_trip_staff)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("trip.menu.about"), command=self.show_about)

    def create_main_menu_button(self):
        """Place a persistent main-menu button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Error checking main_menu_button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def show_main_interface(self):
        """Show the main trip management interface"""
        self.clear_main_frame()

        # Header
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text=_t("trip.header_title"),
                 font=('Arial', 18, 'bold')).pack(side=tk.LEFT)

        if self.auth and self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
            ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main content notebook
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Add tabs based on permissions
        self.add_trips_tab()

        if self.auth.check_permission('register_for_trips'):
            self.add_registration_tab()

        if self.auth.check_permission('view_own_trip_registrations'):
            self.add_my_trips_tab()

        if self.auth.check_permission('manage_trips'):
            self.add_admin_tab()

        if self.auth.check_permission('view_trip_reports'):
            self.add_reports_tab()

        # Calendar integration tab
        if CALENDAR_AVAILABLE and self.calendar_manager:
            self.add_calendar_tab()

    def add_trips_tab(self):
        """Add the trips overview tab"""
        trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(trips_frame, text=_t("trip.tabs.all_trips"))

        # Toolbar
        toolbar = ttk.Frame(trips_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_trips).pack(side=tk.LEFT, padx=(0, 5))

        if self.auth.check_permission('create_trips'):
            ttk.Button(toolbar, text=_t("trip.btn.create_trip"), command=self.show_create_trip).pack(side=tk.LEFT, padx=5)

        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_trips)
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT)

        # Trips treeview
        self.trips_tree = ttk.Treeview(trips_frame, columns=('name', 'destination', 'start_date', 'participants', 'cost', 'status'), show='tree headings')

        # Configure columns
        self.trips_tree.heading('#0', text='ID')
        self.trips_tree.heading('name', text='Trip Name')
        self.trips_tree.heading('destination', text='Destination')
        self.trips_tree.heading('start_date', text='Start Date')
        self.trips_tree.heading('participants', text='Participants')
        self.trips_tree.heading('cost', text='Cost')
        self.trips_tree.heading('status', text='Status')

        self.trips_tree.column('#0', width=50)
        self.trips_tree.column('name', width=200)
        self.trips_tree.column('destination', width=150)
        self.trips_tree.column('start_date', width=100)
        self.trips_tree.column('participants', width=100)
        self.trips_tree.column('cost', width=80)
        self.trips_tree.column('status', width=100)

        # Scrollbars
        trips_scrollbar_v = ttk.Scrollbar(trips_frame, orient=tk.VERTICAL, command=self.trips_tree.yview)
        trips_scrollbar_h = ttk.Scrollbar(trips_frame, orient=tk.HORIZONTAL, command=self.trips_tree.xview)
        self.trips_tree.configure(yscrollcommand=trips_scrollbar_v.set, xscrollcommand=trips_scrollbar_h.set)

        # Pack treeview and scrollbars
        self.trips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trips_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        trips_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind double-click to view details
        self.trips_tree.bind('<Double-1>', self.on_trip_double_click)

        # Context menu
        self.create_trips_context_menu()

        # Load trips data
        self.refresh_trips()

    def add_registration_tab(self):
        """Add the trip registration tab"""
        reg_frame = ttk.Frame(self.notebook)
        self.notebook.add(reg_frame, text="Register for Trip")

        # Available trips for registration
        ttk.Label(reg_frame, text="Available Trips for Registration",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Registration treeview
        self.reg_tree = ttk.Treeview(reg_frame, columns=('name', 'destination', 'start_date', 'cost', 'spaces'), show='tree headings')

        self.reg_tree.heading('#0', text='ID')
        self.reg_tree.heading('name', text='Trip Name')
        self.reg_tree.heading('destination', text='Destination')
        self.reg_tree.heading('start_date', text='Start Date')
        self.reg_tree.heading('cost', text='Cost')
        self.reg_tree.heading('spaces', text='Spaces Left')

        self.reg_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Registration button
        ttk.Button(reg_frame, text="Register for Selected Trip",
                  command=self.register_for_trip).pack(pady=10)

        self.load_available_trips()

    def add_my_trips_tab(self):
        """Add the my trips tab"""
        my_trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(my_trips_frame, text="My Trips")

        ttk.Label(my_trips_frame, text="My Trip Registrations",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # My trips treeview
        self.my_trips_tree = ttk.Treeview(my_trips_frame, columns=('name', 'destination', 'start_date', 'cost', 'payment', 'status'), show='tree headings')

        self.my_trips_tree.heading('#0', text='ID')
        self.my_trips_tree.heading('name', text='Trip Name')
        self.my_trips_tree.heading('destination', text='Destination')
        self.my_trips_tree.heading('start_date', text='Start Date')
        self.my_trips_tree.heading('cost', text='Cost')
        self.my_trips_tree.heading('payment', text='Payment')
        self.my_trips_tree.heading('status', text='Status')

        self.my_trips_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Cancel registration button
        ttk.Button(my_trips_frame, text="Cancel Selected Registration",
                  command=self.cancel_registration).pack(pady=10)

        self.load_my_trips()

    def add_admin_tab(self):
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="Administration")

        # store notebook so menu actions can select subtabs later
        self.admin_notebook = ttk.Notebook(admin_frame)
        self.admin_notebook.pack(fill=tk.BOTH, expand=True)

        participants_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(participants_frame, text="Manage Participants")
        self.setup_participants_management(participants_frame)

        staff_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(staff_frame, text="Assign Staff")
        self.setup_staff_assignment(staff_frame)

        expenses_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(expenses_frame, text="Manage Expenses")
        self.setup_expenses_management(expenses_frame)

        trip_mgmt_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(trip_mgmt_frame, text="Trip Management")
        self.setup_trip_management(trip_mgmt_frame)

    def add_reports_tab(self):
        """Add the reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")

        ttk.Label(reports_frame, text="Trip Reports",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Report buttons
        reports_buttons_frame = ttk.Frame(reports_frame)
        reports_buttons_frame.pack(pady=20)

        ttk.Button(reports_buttons_frame, text="Trip Summary Report",
                  command=self.generate_trip_summary_report).pack(pady=5, fill=tk.X)

        ttk.Button(reports_buttons_frame, text="Participant List Report",
                  command=self.generate_participant_report).pack(pady=5, fill=tk.X)

        if self.auth.check_permission('view_financial_reports'):
            ttk.Button(reports_buttons_frame, text="Financial Report",
                      command=self.generate_financial_report).pack(pady=5, fill=tk.X)

        # Report output area
        ttk.Label(reports_frame, text="Report Generation Log").pack(anchor=tk.W, pady=(20, 5))
        self.report_log = scrolledtext.ScrolledText(reports_frame, height=15, width=80)
        self.report_log.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    def add_calendar_tab(self):
        """Add the calendar integration tab"""
        calendar_frame = ttk.Frame(self.notebook)
        self.notebook.add(calendar_frame, text="Calendar")

        ttk.Label(calendar_frame, text="Calendar Integration",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Calendar buttons
        cal_buttons_frame = ttk.Frame(calendar_frame)
        cal_buttons_frame.pack(pady=20)

        ttk.Button(cal_buttons_frame, text="View Trips with Calendar Events",
                  command=self.show_trips_with_calendar).pack(pady=5, fill=tk.X)

        ttk.Button(cal_buttons_frame, text="View Trip Events in Calendar",
                  command=self.view_trip_events_in_calendar).pack(pady=5, fill=tk.X)

        if self.auth.check_permission('manage_schedules'):
            ttk.Button(cal_buttons_frame, text="Create Calendar Event for Trip",
                      command=self.create_trip_calendar_event).pack(pady=5, fill=tk.X)

        # Calendar view area
        self.calendar_tree = ttk.Treeview(calendar_frame, columns=('trip', 'event', 'start_date', 'status'), show='tree headings')

        self.calendar_tree.heading('#0', text='ID')
        self.calendar_tree.heading('trip', text='Trip Name')
        self.calendar_tree.heading('event', text='Calendar Event')
        self.calendar_tree.heading('start_date', text='Start Date')
        self.calendar_tree.heading('status', text='Status')

        self.calendar_tree.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

    def clear_main_frame(self):
        """Clear the main frame"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def update_status(self, message):
        """Update the status bar"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            return None
        except Exception as e:
            logging.error(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff"""
        role = self.get_user_role()
        return role in ['staff', 'trip_coordinator', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def _show_admin_subtab(self, subtab_label):
        self._ensure_main_ui()
        # ensure Admin tab exists / allowed
        if not any(self.notebook.tab(i, 'text') == 'Administration'
                   for i in range(self.notebook.index('end'))):
            if self.auth and self.auth.check_permission('manage_trips'):
                self.add_admin_tab()
            else:
                messagebox.showerror("Permission Denied", "You don't have access to Administration.")
                return
        # select Admin
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Administration':
                self.notebook.select(i)
                break
        # select inner subtab
        if hasattr(self, 'admin_notebook'):
            for j in range(self.admin_notebook.index('end')):
                if self.admin_notebook.tab(j, 'text') == subtab_label:
                    self.admin_notebook.select(j)
                    break

    def cancel_trip_registration(self):
        """Cancel selected registration - enhanced version"""
        selection = self.my_trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a registration to cancel.")
            return

        trip_id = self.my_trips_tree.item(selection[0])['text']
        trip_name = self.my_trips_tree.item(selection[0])['values'][0]
        payment_status = self.my_trips_tree.item(selection[0])['values'][4]

        # Enhanced cancellation dialog
        CancelRegistrationDialog(self.root, self.auth, trip_id, trip_name, payment_status, self.load_my_trips)

    def view_trip_itinerary(self):
        """View itinerary for selected trip"""
        selection = self.trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to view itinerary.")
            return

        trip_id = self.trips_tree.item(selection[0])['text']
        ViewItineraryDialog(self.root, trip_id)

    def add_trip_itinerary(self):
        """Add itinerary to selected trip"""
        selection = self.trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to add itinerary.")
            return

        trip_id = self.trips_tree.item(selection[0])['text']
        ItineraryDialog(self.root, self.auth, trip_id)

    def assign_trip_staff(self):
        """Assign staff to trip - calls existing dialog"""
        self._show_admin_subtab('Assign Staff')

    def show_manage_participants(self):
        self._show_admin_subtab('Manage Participants')

    def show_assign_staff(self):
        self._show_admin_subtab('Assign Staff')

    def show_manage_expenses(self):
        self._show_admin_subtab('Manage Expenses')

    def cancel_selected_registration(self):
        """Menu action to cancel registration from My Trips"""
        if self._select_tab('My Trips'):
            # Wait a moment for tab to load, then check selection
            self.root.after(100, self._check_and_cancel_registration)

    def _check_and_cancel_registration(self):
        """Helper to cancel registration after tab loads"""
        if hasattr(self, 'my_trips_tree'):
            selection = self.my_trips_tree.selection()
            if selection:
                self.cancel_trip_registration()
            else:
                messagebox.showinfo("No Selection", "Please select a registration from the My Trips tab first.")
        else:
            messagebox.showinfo("Tab Not Available", "Please go to the My Trips tab and select a registration to cancel.")

    def refresh_trips(self):
        """Refresh the trips display"""
        self.update_status("Loading trips...")

        # Clear existing items
        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)

        # Load trips from database
        def load_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            LEFT JOIN users u ON t.created_by = u.id
            GROUP BY t.id
            ORDER BY t.start_date ASC
            ''')

            trips = cursor.fetchall()
            return trips

        trips = self.safe_db_operation(load_trips_operation)

        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"

                cost_str = f"\u00a3{cost:.2f}" if cost is not None else "\u00a30.00"
                status_str = status.title() if status else "Unknown"
                self.trips_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, participants_info, cost_str, status_str
                ))

        self.update_status(f"Loaded {len(trips) if trips else 0} trips")

    def filter_trips(self, *args):
        """Filter trips based on search criteria"""
        search_raw = (self.search_var.get() or "").strip()
        if not search_raw:
            self.refresh_trips()
            return

        search_term = search_raw.lower()
        like_term = f"%{escape_like(search_term)}%"

        def filter_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                       t.max_participants, t.cost, t.status,
                       COUNT(tp.id) as current_participants,
                       u.first_name || ' ' || u.last_name as created_by_name
                FROM trips t
                LEFT JOIN trip_participants tp
                       ON t.id = tp.trip_id AND tp.status = 'registered'
                LEFT JOIN users u ON t.created_by = u.id
                WHERE (
                    LOWER(t.trip_name) LIKE ?
                    OR LOWER(t.destination) LIKE ?
                    OR LOWER(COALESCE(t.status, '')) LIKE ?
                    OR LOWER(COALESCE(u.first_name || ' ' || u.last_name, '')) LIKE ?
                    OR t.start_date LIKE ?
                    OR t.end_date LIKE ?
                    OR CAST(t.cost AS TEXT) LIKE ?
                )
                GROUP BY t.id
                ORDER BY t.start_date ASC
                ''',
                (
                    like_term,
                    like_term,
                    like_term,
                    like_term,
                    f"%{escape_like(search_raw)}%",
                    f"%{escape_like(search_raw)}%",
                    f"%{escape_like(search_raw)}%",
                ),
            )
            return cursor.fetchall()

        trips = self.safe_db_operation(filter_trips_operation) or []

        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)

        for trip in trips:
            (trip_id, name, destination, start_date, end_date, max_parts,
             cost, status, current_parts, created_by) = trip
            participants_info = f"{current_parts}/{max_parts}"
            cost_str = f"\u00a3{cost:.2f}" if cost is not None else "\u00a30.00"
            status_str = status.title() if status else "Unknown"
            self.trips_tree.insert(
                '',
                'end',
                text=str(trip_id),
                values=(name, destination, start_date, participants_info, cost_str, status_str)
            )

        match_count = len(trips)
        self.update_status(f"Found {match_count} trip(s) matching '{search_raw}'")

    def on_trip_double_click(self, event):
        """Handle double-click on trip item"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            self.show_trip_details(trip_id)

    def show_trip_details(self, trip_id):
        """Show detailed trip information"""
        def get_trip_details_operation(conn):
            cursor = conn.cursor()

            # Get trip details
            cursor.execute('''
            SELECT t.*, u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN users u ON t.created_by = u.id
            WHERE t.id = ?
            ''', (trip_id,))

            trip = cursor.fetchone()

            if not trip:
                return None

            # Get participants
            cursor.execute('''
            SELECT tp.*, s.first_name || ' ' || s.last_name as student_name, s.email_address
            FROM trip_participants tp
            LEFT JOIN students s ON tp.student_id = s.student_id
            WHERE tp.trip_id = ? AND tp.status = 'registered'
            ORDER BY tp.registration_date
            ''', (trip_id,))

            participants = cursor.fetchall()

            return {'trip': trip, 'participants': participants}

        result = self.safe_db_operation(get_trip_details_operation)

        if result:
            TripDetailsDialog(self.root, result['trip'], result['participants'])

    def show_create_trip(self):
        """Show create trip dialog"""
        if not self.auth.check_permission('create_trips'):
            messagebox.showerror("Permission Denied", "You don't have permission to create trips.")
            return

        CreateTripDialog(self.root, self.auth, self.refresh_trips)

    def register_for_trip(self):
        """Register for selected trip"""
        selection = self.reg_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to register for.")
            return

        trip_id = self.reg_tree.item(selection[0])['text']
        RegisterForTripDialog(self.root, self.auth, trip_id, self.load_available_trips, self.load_my_trips)

    def cancel_registration(self):
        """Cancel selected registration"""
        selection = self.my_trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a registration to cancel.")
            return

        trip_id = self.my_trips_tree.item(selection[0])['text']
        values = self.my_trips_tree.item(selection[0])['values']
        trip_name = values[0] if values else f"Trip {trip_id}"
        payment_status = values[4] if len(values) > 4 else "unknown"

        CancelRegistrationDialog(
            self.root,
            self.auth,
            trip_id,
            trip_name,
            payment_status,
            self.load_my_trips
        )

    def load_available_trips(self):
        """Load available trips for registration"""
        # Clear existing items
        for item in self.reg_tree.get_children():
            self.reg_tree.delete(item)

        def load_available_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            WHERE t.status IN ('open', 'planning')
            GROUP BY t.id
            HAVING current_participants < t.max_participants
            ORDER BY t.start_date ASC
            ''')

            return cursor.fetchall()

        trips = self.safe_db_operation(load_available_trips_operation)

        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts = trip
                spaces_left = max_parts - current_parts

                cost_str = f"\u00a3{cost:.2f}" if cost is not None else "\u00a30.00"
                self.reg_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, cost_str, str(spaces_left)
                ))

    def load_my_trips(self):
        """Load user's trip registrations"""
        if not self.auth.current_user:
            return

        # Clear existing items
        for item in self.my_trips_tree.get_children():
            self.my_trips_tree.delete(item)

        def load_my_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.cost, tp.registration_date, tp.payment_status, tp.status
            FROM trip_participants tp
            JOIN trips t ON tp.trip_id = t.id
            WHERE tp.user_id = ?
            ORDER BY t.start_date ASC
            ''', (self.auth.current_user['id'],))

            return cursor.fetchall()

        registrations = self.safe_db_operation(load_my_trips_operation)

        if registrations:
            for reg in registrations:
                trip_id, name, destination, start_date, end_date, cost, reg_date, payment_status, status = reg

                cost_str = f"\u00a3{cost:.2f}" if cost is not None else "\u00a30.00"
                payment_str = payment_status.title() if payment_status else "Unknown"
                status_str = status.title() if status else "Unknown"
                self.my_trips_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, cost_str, payment_str, status_str
                ))

    def setup_participants_management(self, parent):
        """Setup participants management interface"""
        # Trip selection
        trip_select_frame = ttk.Frame(parent)
        trip_select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(trip_select_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.participant_trip_var = tk.StringVar()
        self.participant_trip_combo = ttk.Combobox(trip_select_frame, textvariable=self.participant_trip_var)
        self.participant_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(trip_select_frame, text="Load Participants",
                  command=self.load_trip_participants).pack(side=tk.LEFT)

        # Participants list
        self.participants_tree = ttk.Treeview(parent, columns=('name', 'email', 'registration', 'payment', 'status'), show='tree headings')

        self.participants_tree.heading('#0', text='ID')
        self.participants_tree.heading('name', text='Name')
        self.participants_tree.heading('email', text='Email')
        self.participants_tree.heading('registration', text='Registration Date')
        self.participants_tree.heading('payment', text='Payment Status')
        self.participants_tree.heading('status', text='Status')

        self.participants_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Management buttons
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="Update Payment",
                  command=self.update_payment_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Update Status",
                  command=self.update_participant_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Remove Participant",
                  command=self.remove_participant).pack(side=tk.LEFT, padx=5)

        # Load trips for selection
        self.load_trips_for_management()

    def setup_staff_assignment(self, parent):
        """Setup staff assignment interface"""
        ttk.Label(parent, text="Staff Assignment", font=('Arial', 12, 'bold')).pack(pady=10)

        # Trip selection for staff assignment
        staff_trip_frame = ttk.Frame(parent)
        staff_trip_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(staff_trip_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.staff_trip_var = tk.StringVar()
        self.staff_trip_combo = ttk.Combobox(
            staff_trip_frame,
            textvariable=self.staff_trip_var,
            state='readonly'
        )
        self.staff_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.staff_trip_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_trip_staff())

        # Staff assignment tree
        self.staff_tree = ttk.Treeview(parent, columns=('staff_name', 'role', 'assigned_date'), show='tree headings')

        self.staff_tree.heading('#0', text='ID')
        self.staff_tree.heading('staff_name', text='Staff Name')
        self.staff_tree.heading('role', text='Role')
        self.staff_tree.heading('assigned_date', text='Assigned Date')

        self.staff_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Assignment buttons
        staff_buttons_frame = ttk.Frame(parent)
        staff_buttons_frame.pack(fill=tk.X)

        ttk.Button(staff_buttons_frame, text="Assign Staff",
                  command=self.assign_staff).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(staff_buttons_frame, text="Remove Staff",
                  command=self.remove_staff).pack(side=tk.LEFT)

        self.load_staff_trip_options()

    def setup_expenses_management(self, parent):
        """Setup expenses management interface"""
        ttk.Label(parent, text="Expense Management", font=('Arial', 12, 'bold')).pack(pady=10)

        # Trip selection for expenses
        expense_trip_frame = ttk.Frame(parent)
        expense_trip_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(expense_trip_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.expense_trip_var = tk.StringVar()
        self.expense_trip_combo = ttk.Combobox(expense_trip_frame, textvariable=self.expense_trip_var)
        self.expense_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(expense_trip_frame, text="Load Expenses",
                  command=self.load_trip_expenses).pack(side=tk.LEFT)

        # Expenses tree
        self.expenses_tree = ttk.Treeview(parent, columns=('category', 'description', 'amount', 'date', 'recorded_by'), show='tree headings')

        self.expenses_tree.heading('#0', text='ID')
        self.expenses_tree.heading('category', text='Category')
        self.expenses_tree.heading('description', text='Description')
        self.expenses_tree.heading('amount', text='Amount')
        self.expenses_tree.heading('date', text='Date')
        self.expenses_tree.heading('recorded_by', text='Recorded By')

        self.expenses_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Expense buttons
        expense_buttons_frame = ttk.Frame(parent)
        expense_buttons_frame.pack(fill=tk.X)

        ttk.Button(expense_buttons_frame, text="Add Expense",
                  command=self.add_expense).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(expense_buttons_frame, text="Edit Expense",
                  command=self.edit_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(expense_buttons_frame, text="Delete Expense",
                  command=self.delete_expense).pack(side=tk.LEFT, padx=5)

    def setup_trip_management(self, parent):
        """Setup trip management interface"""
        ttk.Label(parent, text="Trip Management", font=('Arial', 12, 'bold')).pack(pady=10)

        # Trip actions
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=10)

        ttk.Button(actions_frame, text="Update Trip",
                  command=self.update_trip).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(actions_frame, text="Delete Trip",
                  command=self.delete_trip).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Manage Itinerary",
                  command=self.manage_itinerary).pack(side=tk.LEFT, padx=5)

        # Trip status summary
        summary_frame = ttk.LabelFrame(parent, text="Trip Summary", padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.trip_summary_text = scrolledtext.ScrolledText(summary_frame, height=15)
        self.trip_summary_text.pack(fill=tk.BOTH, expand=True)

        self.load_trip_summary()

    def create_trips_context_menu(self):
        """Create context menu for trips treeview - enhanced"""
        self.trips_context_menu = tk.Menu(self.root, tearoff=0)
        self.trips_context_menu.add_command(label="View Details", command=self.view_selected_trip_details)
        self.trips_context_menu.add_command(label="View Itinerary", command=self.view_trip_itinerary)

        if self.auth.check_permission('register_for_trips'):
            self.trips_context_menu.add_command(label="Register for Trip", command=self.register_for_selected_trip)

        if self.auth.check_permission('manage_trips') or self.auth.check_permission('create_trips'):
            self.trips_context_menu.add_separator()
            self.trips_context_menu.add_command(label="Add/Edit Itinerary", command=self.add_trip_itinerary)
            self.trips_context_menu.add_command(label="Edit Trip", command=self.edit_selected_trip)

        if self.auth.check_permission('manage_trips'):
            self.trips_context_menu.add_command(label="Assign Staff", command=self.assign_trip_staff)
            self.trips_context_menu.add_command(label="Delete Trip", command=self.delete_selected_trip)

        self.trips_tree.bind("<Button-3>", self.show_trips_context_menu)

    def show_trips_context_menu(self, event):
        """Show context menu for trips"""
        selection = self.trips_tree.selection()
        if selection:
            self.trips_context_menu.post(event.x_root, event.y_root)

    def view_selected_trip_details(self):
        """View details of selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            self.show_trip_details(trip_id)

    def register_for_selected_trip(self):
        """Register for selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            RegisterForTripDialog(self.root, self.auth, trip_id, self.refresh_trips, self.load_my_trips)

    def edit_selected_trip(self):
        """Edit selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            UpdateTripDialog(self.root, self.auth, trip_id, self.refresh_trips)

    def delete_selected_trip(self):
        """Delete selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            trip_name = self.trips_tree.item(selection[0])['values'][0]

            if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete trip '{trip_name}'?"):
                def delete_trip_operation(conn):
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
                    return True

                if self.safe_db_operation(delete_trip_operation):
                    messagebox.showinfo("Success", "Trip deleted successfully")
                    self.refresh_trips()
                else:
                    messagebox.showerror("Error", "Failed to delete trip")

    def load_trips_for_management(self):
        """Load trips for management dropdowns"""
        def load_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT id, trip_name FROM trips ORDER BY trip_name')
            return cursor.fetchall()

        trips = self.safe_db_operation(load_trips_operation)

        if trips:
            trip_list = [f"{trip[0]} - {trip[1]}" for trip in trips]

            # Update all trip selection comboboxes
            if hasattr(self, 'participant_trip_combo'):
                self.participant_trip_combo['values'] = trip_list
            if hasattr(self, 'staff_trip_combo'):
                self.staff_trip_combo['values'] = trip_list
            if hasattr(self, 'expense_trip_combo'):
                self.expense_trip_combo['values'] = trip_list

    # --- Add this helper anywhere in the class ---
    def _ensure_main_ui(self):
        """Ensure the main notebook exists."""
        if not hasattr(self, 'notebook'):
            self.show_main_interface()

    def _select_tab(self, label_text):
        """Select a top-level tab by its text label."""
        self._ensure_main_ui()
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == label_text:
                self.notebook.select(i)
                return True
        return False

    # --- ADD: implement the missing menu target ---
    def show_trips_view(self):
        """Menu action: go to the All Trips tab and refresh."""
        if self._select_tab('All Trips'):
            try:
                self.refresh_trips()
            except Exception as e:
                logger.warning(f"Failed to refresh trips view: {e}")

    def show_my_registrations(self):
        """Menu action: go to My Trips; create it if permissions allow."""
        self._ensure_main_ui()
        # If the tab isn't present yet but user can view their regs, add it.
        if not any(self.notebook.tab(i, 'text') == 'My Trips'
                   for i in range(self.notebook.index('end'))):
            if self.auth and self.auth.check_permission('view_own_trip_registrations'):
                self.add_my_trips_tab()
        self._select_tab('My Trips')

    def load_trip_participants(self):
        """Load participants for selected trip"""
        trip_selection = self.participant_trip_var.get()
        if not trip_selection:
            return

        trip_id = trip_selection.split(' - ')[0]

        # Clear existing items
        for item in self.participants_tree.get_children():
            self.participants_tree.delete(item)

        def load_participants_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT tp.id, tp.student_id,
                   s.first_name || ' ' || s.last_name as student_name,
                   s.email_address, tp.registration_date, tp.payment_status, tp.status
            FROM trip_participants tp
            LEFT JOIN students s ON tp.student_id = s.student_id
            WHERE tp.trip_id = ?
            ORDER BY tp.registration_date
            ''', (trip_id,))

            return cursor.fetchall()

        participants = self.safe_db_operation(load_participants_operation)

        if participants:
            for participant in participants:
                p_id, student_id, student_name, email, reg_date, payment_status, status = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"

                self.participants_tree.insert('', 'end', text=str(p_id), values=(
                    name, email, reg_date, payment_status.title(), status.title()
                ))

    def load_trip_expenses(self):
        """Load expenses for selected trip"""
        trip_selection = self.expense_trip_var.get()
        if not trip_selection:
            return

        trip_id = trip_selection.split(' - ')[0]

        # Clear existing items
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)

        def load_expenses_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT te.id, te.category, te.description, te.amount, te.date,
                   u.first_name || ' ' || u.last_name as recorded_by
            FROM trip_expenses te
            LEFT JOIN users u ON te.recorded_by = u.id
            WHERE te.trip_id = ?
            ORDER BY te.date DESC
            ''', (trip_id,))

            return cursor.fetchall()

        expenses = self.safe_db_operation(load_expenses_operation)

        if expenses:
            for expense in expenses:
                exp_id, category, description, amount, date, recorded_by = expense
                recorded_by = recorded_by if recorded_by else "Unknown"

                amount_str = f"\u00a3{amount:.2f}" if amount is not None else "\u00a30.00"
                self.expenses_tree.insert('', 'end', text=str(exp_id), values=(
                    category, description, amount_str, date, recorded_by
                ))

    def load_trip_summary(self):
        """Load trip summary statistics"""
        def get_summary_operation(conn):
            cursor = conn.cursor()

            # Get basic trip statistics
            cursor.execute('''
            SELECT
                COUNT(*) as total_trips,
                COUNT(CASE WHEN status = 'planning' THEN 1 END) as planning_trips,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trips,
                COUNT(CASE WHEN status = 'full' THEN 1 END) as full_trips,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_trips,
                SUM(cost) as total_revenue_potential,
                AVG(cost) as average_cost
            FROM trips
            ''')

            summary_stats = cursor.fetchone()

            # Get participant statistics
            cursor.execute('''
            SELECT
                COUNT(*) as total_registrations,
                COUNT(CASE WHEN status = 'registered' THEN 1 END) as active_registrations,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_registrations,
                COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_registrations,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_payments
            FROM trip_participants
            ''')

            participant_stats = cursor.fetchone()

            return {'summary': summary_stats, 'participants': participant_stats}

        data = self.safe_db_operation(get_summary_operation)

        if data:
            summary_text = "TRIP MANAGEMENT SUMMARY\n"
            summary_text += "=" * 50 + "\n\n"

            summary_text += "TRIP STATISTICS:\n"
            summary_text += f"Total Trips: {data['summary'][0]}\n"
            summary_text += f"Planning: {data['summary'][1]}\n"
            summary_text += f"Open for Registration: {data['summary'][2]}\n"
            summary_text += f"Full: {data['summary'][3]}\n"
            summary_text += f"Completed: {data['summary'][4]}\n"
            summary_text += f"Cancelled: {data['summary'][5]}\n"
            revenue = data['summary'][6] if data['summary'][6] is not None else 0
            avg_cost = data['summary'][7] if data['summary'][7] is not None else 0
            summary_text += f"Total Revenue Potential: \u00a3{revenue:.2f}\n"
            summary_text += f"Average Trip Cost: \u00a3{avg_cost:.2f}\n\n"

            summary_text += "PARTICIPANT STATISTICS:\n"
            summary_text += f"Total Registrations: {data['participants'][0]}\n"
            summary_text += f"Active Registrations: {data['participants'][1]}\n"
            summary_text += f"Cancelled Registrations: {data['participants'][2]}\n"
            summary_text += f"Paid Registrations: {data['participants'][3]}\n"
            summary_text += f"Pending Payments: {data['participants'][4]}\n"

            self.trip_summary_text.delete(1.0, tk.END)
            self.trip_summary_text.insert(1.0, summary_text)

    def generate_trip_summary_report(self):
        """Generate trip summary report"""
        if not self.auth.check_permission('view_trip_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
            return

        ReportGeneratorDialog(self.root, self.auth, 'TRIP_SUMMARY', self.report_log)

    def generate_participant_report(self):
        """Generate participant report"""
        if not self.auth.check_permission('view_trip_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
            return

        ReportGeneratorDialog(self.root, self.auth, 'PARTICIPANT_LIST', self.report_log)

    def generate_financial_report(self):
        """Generate financial report"""
        if not self.auth.check_permission('view_financial_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to view financial reports.")
            return

        ReportGeneratorDialog(self.root, self.auth, 'FINANCIAL_REPORT', self.report_log)

    def update_payment_status(self):
        """Update payment status for selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return

        participant_id = self.participants_tree.item(selection[0])['text']
        PaymentStatusDialog(self.root, participant_id, self.load_trip_participants)

    def update_participant_status(self):
        """Update status for selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return

        participant_id = self.participants_tree.item(selection[0])['text']
        ParticipantStatusDialog(self.root, participant_id, self.load_trip_participants)

    def remove_participant(self):
        """Remove selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return

        participant_id = self.participants_tree.item(selection[0])['text']
        participant_name = self.participants_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove '{participant_name}' from this trip?"):
            def remove_participant_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_participants WHERE id = ?', (participant_id,))
                return True

            if self.safe_db_operation(remove_participant_operation):
                messagebox.showinfo("Success", "Participant removed successfully")
                self.load_trip_participants()
            else:
                messagebox.showerror("Error", "Failed to remove participant")

    def assign_staff(self):
        """Assign staff to trip"""
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            messagebox.showwarning("No Trip Selected", "Please select a trip first.")
            return

        try:
            trip_id = int(trip_selection.split(' - ')[0].strip())
        except (ValueError, IndexError):
            messagebox.showerror("Invalid Selection", "Could not determine the selected trip.")
            return

        AssignStaffDialog(self.root, self.auth, trip_id, self.load_trip_staff)

    def remove_staff(self):
        """Remove staff from trip"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member.")
            return

        staff_assignment_id = self.staff_tree.item(selection[0])['text']
        staff_name = self.staff_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove '{staff_name}' from this trip?"):
            def remove_staff_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_staff WHERE id = ?', (staff_assignment_id,))
                return True

            if self.safe_db_operation(remove_staff_operation):
                messagebox.showinfo("Success", "Staff member removed successfully")
                self.load_trip_staff()
            else:
                messagebox.showerror("Error", "Failed to remove staff member")

    def load_trip_staff(self):
        """Load staff for selected trip"""
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            return

        try:
            trip_id = int(trip_selection.split(' - ')[0].strip())
        except (ValueError, IndexError):
            return

        # Clear existing items
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        def load_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, ts.role, u.first_name || ' ' || u.last_name as staff_name, ts.assigned_date
            FROM trip_staff ts
            JOIN users u ON ts.staff_user_id = u.id
            WHERE ts.trip_id = ?
            ORDER BY ts.role, staff_name
            ''', (trip_id,))

            return cursor.fetchall()

        staff = self.safe_db_operation(load_staff_operation) or []

        for staff_member in staff:
            staff_id, role, name, assigned_date = staff_member

            self.staff_tree.insert('', 'end', text=str(staff_id), values=(
                name, role.title(), assigned_date
            ))

    def load_staff_trip_options(self):
        """Populate trip selector for staff assignment"""
        def fetch_trips(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, trip_name, destination, start_date
            FROM trips
            ORDER BY start_date DESC
            ''')
            return cursor.fetchall()

        trips = self.safe_db_operation(fetch_trips) or []
        display_values = [
            f"{trip_id} - {name} ({destination}) [{start_date}]"
            for trip_id, name, destination, start_date in trips
        ]
        self.staff_trip_combo['values'] = display_values
        if display_values:
            self.staff_trip_combo.set(display_values[0])
            self.load_trip_staff()
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            return

        trip_id = trip_selection.split(' - ')[0]

        # Clear existing items
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        def load_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, ts.role, u.first_name || ' ' || u.last_name as staff_name, ts.assigned_date
            FROM trip_staff ts
            JOIN users u ON ts.staff_user_id = u.id
            WHERE ts.trip_id = ?
            ORDER BY ts.role
            ''', (trip_id,))

            return cursor.fetchall()

        staff = self.safe_db_operation(load_staff_operation)

        if staff:
            for staff_member in staff:
                staff_id, role, name, assigned_date = staff_member

                self.staff_tree.insert('', 'end', text=str(staff_id), values=(
                    name, role.title(), assigned_date
                ))

    def add_expense(self):
        """Add new expense"""
        trip_selection = self.expense_trip_var.get()
        if not trip_selection:
            messagebox.showwarning("No Trip Selected", "Please select a trip first.")
            return

        trip_id = trip_selection.split(' - ')[0]
        AddExpenseDialog(self.root, self.auth, trip_id, self.load_trip_expenses)

    def edit_expense(self):
        """Edit selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an expense.")
            return

        expense_id = self.expenses_tree.item(selection[0])['text']
        EditExpenseDialog(self.root, expense_id, self.load_trip_expenses)

    def delete_expense(self):
        """Delete selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an expense.")
            return

        expense_id = self.expenses_tree.item(selection[0])['text']
        expense_desc = self.expenses_tree.item(selection[0])['values'][1]

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete expense '{expense_desc}'?"):
            def delete_expense_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_expenses WHERE id = ?', (expense_id,))
                return True

            if self.safe_db_operation(delete_expense_operation):
                messagebox.showinfo("Success", "Expense deleted successfully")
                self.load_trip_expenses()
            else:
                messagebox.showerror("Error", "Failed to delete expense")

    def update_trip(self):
        """Update trip information"""
        # Show trip selection dialog first
        TripSelectionDialog(self.root, self.auth, self.open_update_trip_dialog)

    def open_update_trip_dialog(self, trip_id):
        """Open update trip dialog for specific trip"""
        UpdateTripDialog(self.root, self.auth, trip_id, self.refresh_trips)

    def delete_trip(self):
        """Delete trip"""
        TripSelectionDialog(self.root, self.auth, self.confirm_delete_trip)

    def confirm_delete_trip(self, trip_id):
        """Confirm and delete trip"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
            result = cursor.fetchone()
            return result[0] if result else None

        trip_name = self.safe_db_operation(get_trip_info_operation)

        if trip_name and messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete trip '{trip_name}'?"):
            def delete_trip_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
                return True

            if self.safe_db_operation(delete_trip_operation):
                messagebox.showinfo("Success", "Trip deleted successfully")
                self.refresh_trips()
                self.load_trip_summary()
            else:
                messagebox.showerror("Error", "Failed to delete trip")

    def manage_itinerary(self):
        """Manage trip itinerary"""
        TripSelectionDialog(self.root, self.auth, self.open_itinerary_dialog)

    def open_itinerary_dialog(self, trip_id):
        """Open itinerary management dialog"""
        ItineraryDialog(self.root, self.auth, trip_id)

    def show_trips_with_calendar(self):
        """Show trips with calendar integration"""
        if not self.calendar_manager:
            messagebox.showerror("Calendar Unavailable", "Calendar integration is not available.")
            return

        # Clear existing items
        for item in self.calendar_tree.get_children():
            self.calendar_tree.delete(item)

        def load_calendar_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status,
                   e.name as calendar_event_name,
                   e.id as calendar_event_id
            FROM trips t
            LEFT JOIN academic_calendar_events e ON t.id = e.trip_id
            ORDER BY t.start_date ASC
            ''')

            return cursor.fetchall()

        trips = self.safe_db_operation(load_calendar_trips_operation)

        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, status, cal_event_name, cal_event_id = trip
                calendar_info = cal_event_name if cal_event_name else "No Event"

                self.calendar_tree.insert('', 'end', text=str(trip_id), values=(
                    name, calendar_info, start_date, status.title()
                ))

    def view_trip_events_in_calendar(self):
        """View trip events in the calendar (calendar-centric view)"""
        if not CALENDAR_AVAILABLE or not self.calendar_manager:
            messagebox.showwarning("Calendar Not Available",
                                 "Calendar system is not available.")
            return

        try:
            # Get trip events from calendar for next 365 days
            current_date = datetime.now().strftime('%Y-%m-%d')
            future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

            events = self.calendar_manager.get_events_by_date_range(
                current_date, future_date, 'Trip'
            )

            if not events:
                messagebox.showinfo("No Events", "No trip events found in calendar for the next year.")
                return

            # Create dialog to display events
            dialog = tk.Toplevel(self.root)
            dialog.title("Trip Events in Calendar")
            dialog.geometry("900x600")
            dialog.transient(self.root)

            # Title
            ttk.Label(dialog, text="Trip Events in Calendar",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            ttk.Label(dialog, text=f"Showing trip events for next 365 days ({len(events)} events found)",
                     font=('Arial', 9)).pack(pady=(0, 10))

            # Create treeview for events
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            columns = ('event_name', 'start_date', 'end_date', 'description')
            tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

            tree.heading('event_name', text='Event Name')
            tree.heading('start_date', text='Start Date')
            tree.heading('end_date', text='End Date')
            tree.heading('description', text='Description')

            tree.column('event_name', width=250)
            tree.column('start_date', width=120)
            tree.column('end_date', width=120)
            tree.column('description', width=350)

            # Add scrollbar
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Populate with events
            for event in events:
                start_date = event.get('date_start') or event.get('date', 'TBD')
                end_date = event.get('date_end') or event.get('date', 'TBD')
                description = (event.get('description') or 'No description')[:80]

                tree.insert('', tk.END, values=(
                    event.get('name', 'Unnamed Event'),
                    start_date,
                    end_date,
                    description
                ))

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

            # Log activity
            log_read('trip_calendar_events', f"Viewed {len(events)} trip events in calendar")
            self.update_status(f"Showing {len(events)} trip events from calendar")

        except Exception as e:
            logging.error(f"Error viewing trip events in calendar: {e}")
            messagebox.showerror("Error", f"Failed to view trip events: {str(e)}")

    def create_trip_calendar_event(self):
        """Create calendar event for trip"""
        if not self.calendar_manager:
            messagebox.showerror("Calendar Unavailable", "Calendar integration is not available.")
            return

        CreateCalendarEventDialog(self.root, self.auth, self.calendar_manager, self.show_trips_with_calendar)

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from education_system.post_18.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def export_data(self):
        """Export trip data"""
        ExportDataDialog(self.root, self.auth)

    def show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)

    def safe_db_operation(self, operation_func, *args, max_retries=3, **kwargs):
        """Safely execute a database operation with retry logic - integrated from original"""
        retry_delay = 0.1
        last_error = None

        for attempt in range(max_retries):
            conn = None
            try:
                conn = self.get_db_connection(timeout=30.0)
                if not conn:
                    last_error = "Failed to establish database connection"
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    return False

                result = operation_func(conn, *args, **kwargs)
                conn.commit()
                return result

            except sqlite3.OperationalError as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception as rollback_err:
                        logger.debug(f"Failed to rollback after database locked error: {rollback_err}")

                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    return False

            except Exception as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception as rollback_err:
                        logger.debug(f"Failed to rollback transaction: {rollback_err}")
                return False

            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception as close_err:
                        logger.debug(f"Failed to close database connection: {close_err}")

        return False

    def get_db_connection(self, timeout=30.0, max_retries=3):
        """Get a database connection - uses centralized thread-safe connection.

        Uses the centralized get_connection() function which maintains thread safety
        by keeping check_same_thread=True (SQLite default). Each thread gets its own
        connection to prevent cross-thread data corruption.
        """
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Use centralized get_connection which is thread-safe
                # check_same_thread=True is maintained (the safe default)
                conn = get_connection(db_path=DEFAULT_DB_PATH, timeout=timeout)

                # Additional PRAGMA settings for this module's needs
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
                conn.execute("PRAGMA cache_size = 10000")
                return conn

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    return None
            except sqlite3.Error:
                return None

    def run(self):
        if getattr(self, "_owns_root", False):
            self.root.mainloop()
