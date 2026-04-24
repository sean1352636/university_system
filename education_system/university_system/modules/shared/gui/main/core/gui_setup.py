# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging

# GUI managers — imported lazily via _lazy_import() to speed up startup
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import _lazy_import

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t, get_current_language_name, init_i18n

# Import GUI availability flags
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    ADVANCED_SEARCH_GUI_AVAILABLE,
    VIRTUAL_CLASSROOM_AVAILABLE,
)

logger = logging.getLogger(__name__)

def create_fallback_interface(self):
    """Create minimal fallback interface"""
    self.root = tk.Tk()
    self.root.title(_t("gui.error_mode_title"))
    self.root.geometry("400x300")

    error_frame = ttk.Frame(self.root, padding="20")
    error_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(error_frame, text=_t("gui.error_initializing"), font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(error_frame, text=_t("gui.system_minimal_mode"), foreground="red", wraplength=350).pack(pady=10)
    ttk.Button(error_frame, text=_t("common.close"), command=self.root.quit).pack(pady=10)
def init_gui_managers(self):
    """Initialize modular GUI managers"""
    # Initialize each GUI manager individually to prevent cascade failures
    for attr, cls_name in [
        ("finance_gui", "FinanceManagementGUI"),
        ("student_union_gui", "StudentUnionManagementGUI"),
        ("health_portal_gui", "HealthPortalManagementGUI"),
        ("grade_tracking_gui", "GradeTrackingManagementGUI"),
        ("email_manager_gui", "EmailManagerManagementGUI"),
    ]:
        try:
            cls = _lazy_import(cls_name)
            if cls:
                setattr(self, attr, cls(self.root, self.auth))
            else:
                setattr(self, attr, None)
        except Exception as e:
            print(f"Warning: Error initializing {cls_name}: {e}")
            setattr(self, attr, None)
def create_themed_toplevel(self, title="", geometry=""):
    """Create a Toplevel window"""
    window = tk.Toplevel(self.root)
    if title:
        window.title(title)
    if geometry:
        window.geometry(geometry)
    window.transient(self.root)
    return window
def setup_gui(self):
    """Setup the unified GUI interface using AuthenticationGUI layout"""
    # Main frame
    main_frame = ttk.Frame(self.root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Configure grid weights
    self.root.columnconfigure(0, weight=1)
    self.root.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=0)  # Navigation column - fixed width
    main_frame.columnconfigure(1, weight=1)  # Content column - expands
    main_frame.rowconfigure(1, weight=1)     # Row 1 (nav + content) - expands vertically

    # Header with system status
    self.create_header(main_frame)

    # Left panel - Navigation buttons (like AuthenticationGUI)
    self.create_navigation_panel(main_frame)

    # Right panel - Content area
    self.create_content_area(main_frame)

    # Show welcome message initially
    self.show_welcome()
def create_header(self, parent):
    """Create header with system status and control buttons"""
    header_frame = ttk.LabelFrame(parent, text=_t("gui.system_control"), padding="10")
    header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    # Top row - Control buttons
    button_frame = ttk.Frame(header_frame)
    button_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 10))

    # Shutdown button - using lambda to ensure proper method binding
    ttk.Button(button_frame, text=_t("gui.shutdown"), command=lambda: self.shutdown_system(),
              style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))

    # Login/Logout button (dynamic text based on auth status)
    self.login_logout_btn = ttk.Button(button_frame, text=_t("common.logout"), command=lambda: self.toggle_login_logout())
    self.login_logout_btn.pack(side=tk.LEFT, padx=(0, 10))

    # Switch to CLI button
    ttk.Button(button_frame, text=_t("gui.switch_to_cli"), command=lambda: self.switch_to_cli()).pack(side=tk.LEFT, padx=(0, 10))

    # Switch System button (superadmin only)
    from education_system.university_system.modules.shared.gui.main.auth_gui import _is_superadmin_user
    if _is_superadmin_user(self):
        ttk.Button(button_frame, text=_t("gui.switch_system.title"), command=lambda: self.switch_system()).pack(side=tk.LEFT, padx=(0, 10))

    # Language button removed — language is now selected at startup via shared i18n

    # Status information
    ttk.Label(header_frame, text=_t("gui.status") + ":").grid(row=1, column=0, sticky=tk.W)
    ttk.Label(header_frame, textvariable=self.status_var).grid(row=1, column=1, sticky=tk.W, padx=(10, 0))

    ttk.Label(header_frame, text=_t("gui.current_user") + ":").grid(row=2, column=0, sticky=tk.W)
    ttk.Label(header_frame, textvariable=self.current_user_var).grid(row=2, column=1, sticky=tk.W, padx=(10, 0))

    header_frame.columnconfigure(1, weight=1)
def create_navigation_panel(self, parent):
    """Create navigation panel with categorized buttons and scrollbar"""
    # Destroy old navigation frame if it exists
    if hasattr(self, 'nav_frame') and self.nav_frame:
        try:
            self.nav_frame.destroy()
        except Exception as e:
            logger.debug(f"Could not destroy nav_frame: {e}")

    # Main navigation frame
    nav_frame = ttk.LabelFrame(parent, text=_t("gui.navigation"), padding="5")
    nav_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
    self.nav_frame = nav_frame
    self.nav_parent = parent

    # Ensure navigation frame has proper internal configuration
    nav_frame.rowconfigure(0, weight=1)
    nav_frame.columnconfigure(0, weight=1)

    # Canvas + scrollbar for long menus
    canvas = tk.Canvas(nav_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(nav_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    def configure_scroll_region(_):
        canvas.configure(scrollregion=canvas.bbox("all"))
    scrollable_frame.bind("<Configure>", configure_scroll_region)

    canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Mousewheel
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))

    # Keep inner frame width = canvas width
    def configure_canvas_width(_):
        canvas.itemconfig(canvas_window, width=canvas.winfo_width())
    canvas.bind('<Configure>', configure_canvas_width)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    self.nav_buttons = {}

    # Get current user role and determine visible buttons
    current_role = None
    if self.auth and self.auth.current_user:
        current_role = self.auth.current_user.get('role')
    visible_buttons = self.get_visible_buttons_for_role(current_role)

    # Helper for logout (returns to universal login)
    def do_logout():
        self.logout_user()

    # Helper to conditionally create button
    def create_button_if_visible(parent_frame, button_name, text, command):
        if button_name in visible_buttons:
            self.nav_buttons[button_name] = ttk.Button(parent_frame, text=text, command=command)
            self.nav_buttons[button_name].pack(fill=tk.X, pady=2)
            return True
        return False

    # Helper to create category window with buttons
    def open_category_window(category_title, buttons_data):
        """Open a window showing all buttons for a category

        Args:
            category_title: Title for the window
            buttons_data: List of tuples (button_name, button_text, command)
        """
        # Filter only visible buttons
        visible_category_buttons = [
            (name, text, cmd) for name, text, cmd in buttons_data
            if name in visible_buttons
        ]

        if not visible_category_buttons:
            messagebox.showinfo(_t("common.info"), _t("gui.nav.no_features_available").format(category=category_title))
            return

        # Create category window — sized for 4-column grid
        cols = 4
        cat_window = tk.Toplevel(self.root)
        cat_window.title(category_title)
        cat_window.geometry("820x500")
        cat_window.transient(self.root)

        # Header
        header = tk.Frame(cat_window, bg='#2c3e50', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)

        tk.Label(header, text=category_title, font=('Arial', 16, 'bold'),
                bg='#2c3e50', fg='white').pack(expand=True)

        # Scrollable button area
        canvas = tk.Canvas(cat_window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(cat_window, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Keep inner frame width matched to canvas
        def _resize_inner(event):
            canvas.itemconfig(canvas_win, width=event.width)
        canvas.bind('<Configure>', _resize_inner)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Configure grid columns to expand equally
        for c in range(cols):
            scrollable.columnconfigure(c, weight=1)

        # Add buttons in a 4-column grid
        for idx, (name, text, cmd) in enumerate(visible_category_buttons):
            def make_command(command, window):
                def wrapped_cmd():
                    window.destroy()
                    command()
                return wrapped_cmd

            row = idx // cols
            col = idx % cols
            btn = ttk.Button(scrollable, text=text,
                           command=make_command(cmd, cat_window),
                           style='Large.TButton')
            btn.grid(row=row, column=col, padx=4, pady=4, sticky='nsew')

        # Close button
        close_btn = ttk.Button(cat_window, text=_t("common.close"),
                              command=cat_window.destroy)
        close_btn.pack(pady=10)

    # ---------- Authentication ----------
    authentication_buttons_data = [
        ('login', _t("common.logout"), self.logout_user),
        ('change_password', _t("nav.buttons.change_password"), self.show_change_password),
        ('mfa_setup', _t("nav.buttons.mfa_setup"), self.show_mfa_setup),
        ('security_questions', "Security Questions", self.show_security_questions),
        ('toggle_verification', _t("nav.buttons.toggle_verification"), self.toggle_login_verification),
    ]

    if any(name in visible_buttons for name, _, _ in authentication_buttons_data):
        authentication_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.authentication") + " ▶",
                                   command=lambda: open_category_window(_t("nav.categories.authentication"), authentication_buttons_data),
                                   style='Large.TButton')
        authentication_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Student Management ----------
    student_mgmt_buttons_data = [
        ('student_records', _t("nav.buttons.student_records"), self.show_student_records),
        ('create_student', _t("nav.buttons.create_student"), self.create_student_dialog),
        ('search_students', _t("nav.buttons.search_students"), self.search_students_dialog),
    ]
    if ADVANCED_SEARCH_GUI_AVAILABLE:
        student_mgmt_buttons_data.append(('advanced_search_gui', _t("nav.buttons.advanced_search"), self.show_advanced_search_gui))
    student_mgmt_buttons_data.extend([
        ('delete_student', _t("nav.buttons.delete_student"), self.delete_student_dialog),
        ('batch_operations', _t("nav.buttons.batch_operations"), self.show_batch_operations_gui),
    ])

    if any(name in visible_buttons for name, _, _ in student_mgmt_buttons_data):
        student_mgmt_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.student_management") + " ▶",
                                      command=lambda: open_category_window(_t("nav.categories.student_management"), student_mgmt_buttons_data),
                                      style='Large.TButton')
        student_mgmt_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Academic Management ----------
    academic_buttons_data = [
        ('course_management', _t("nav.buttons.course_management"), self.show_course_management),
        ('module_management', _t("nav.buttons.module_management"), self.show_module_management),
        ('assignments', _t("nav.buttons.assignments"), self.show_assignments),
        ('grade_tracking_gui', _t("nav.buttons.grade_tracking"), self.show_grade_tracking_gui),
        ('student_registration', _t("nav.buttons.student_registration"), self.show_student_registration_gui),
        ('library', _t("nav.buttons.library"), self.show_library_management),
        ('ai_study', _t("nav.buttons.ai_study"), self.show_ai_study_gui),
        ('study_matching_gui', _t("nav.buttons.study_matching"), self.show_study_matching_gui),
        ('office_hours', _t("nav.buttons.office_hours"), self.show_office_hours_gui),
        ('study_recommendations', 'Study Recommendations', self.show_study_recommendations_gui),
    ]
    if VIRTUAL_CLASSROOM_AVAILABLE:
        academic_buttons_data.append(('virtual_classroom', _t("nav.buttons.virtual_classroom"), self.show_virtual_classroom_gui))

    if any(name in visible_buttons for name, _, _ in academic_buttons_data):
        academic_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.academic") + " ▶",
                                  command=lambda: open_category_window(_t("nav.categories.academic"), academic_buttons_data),
                                  style='Large.TButton')
        academic_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Scheduling & Attendance ----------
    sched_buttons_data = [
        ('academic_calendar', _t("nav.buttons.academic_calendar"), self.show_academic_calendar),
        ('scheduling', _t("nav.buttons.scheduling"), self.show_module_scheduling),
        ('my_timetable', _t("nav.buttons.my_timetable"), self.show_student_timetable_gui),
        ('attendance', _t("nav.buttons.attendance"), self.open_attendance_gui),
        ('absence_tracker', "Absence Tracker", self.open_absence_tracker_gui),
        ('exam_portal', "Exam Management", self.show_exam_portal),
    ]

    if any(name in visible_buttons for name, _, _ in sched_buttons_data):
        sched_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.scheduling") + " ▶",
                              command=lambda: open_category_window(_t("nav.categories.scheduling"), sched_buttons_data),
                              style='Large.TButton')
        sched_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Finance ----------
    finance_buttons_data = [
        ('finance_management', _t("nav.buttons.finance_management"), self.show_finance_management),
        ('my_finance', _t("nav.buttons.my_finance"), self.show_student_finance_account),
    ]

    if any(name in visible_buttons for name, _, _ in finance_buttons_data):
        finance_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.finance") + " ▶",
                                command=lambda: open_category_window(_t("nav.categories.finance"), finance_buttons_data),
                                style='Large.TButton')
        finance_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Health & Wellness ----------
    health_buttons_data = [
        ('health_portal', _t("nav.buttons.health_portal"), self.open_health_portal_gui),
        ('gym', "Gym", self.show_gym_gui),
    ]

    if any(name in visible_buttons for name, _, _ in health_buttons_data):
        health_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.health") + " ▶",
                               command=lambda: open_category_window(_t("nav.categories.health"), health_buttons_data),
                               style='Large.TButton')
        health_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Accommodation ----------
    accommodation_buttons_data = [
        ('housing_accommodations', _t("nav.buttons.housing_accommodation"), self.show_housing_accommodations),
    ]

    if any(name in visible_buttons for name, _, _ in accommodation_buttons_data):
        accommodation_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.accommodation") + " ▶",
                                      command=lambda: open_category_window(_t("nav.categories.accommodation"), accommodation_buttons_data),
                                      style='Large.TButton')
        accommodation_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Campus Life ----------
    campus_buttons_data = [
        ('student_union_portal', _t("nav.buttons.student_union"), self.open_student_union_portal_gui),
        ('campus_events', _t("nav.buttons.campus_events"), self.show_campus_events_gui),
        ('events_discovery', _t("nav.buttons.events_discovery"), self.show_events_discovery_gui),
        ('facilities_management', _t("nav.buttons.facilities"), self.show_facilities_management_gui),
        ('equipment', _t("nav.buttons.equipment"), self.show_equipment_gui),
    ]

    if any(name in visible_buttons for name, _, _ in campus_buttons_data):
        campus_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.campus") + " ▶",
                                command=lambda: open_category_window(_t("nav.categories.campus"), campus_buttons_data),
                                style='Large.TButton')
        campus_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Dining & Food ----------
    dining_buttons_data = [
        ('restaurant_management', _t("nav.buttons.dining_services"), self.show_restaurant_management),
        ('cafe_system', _t("nav.buttons.cafe_system"), self.show_cafe_system),
        ('takeaway_system', _t("nav.buttons.takeaway"), self.show_takeaway_system),
        ('bar', _t("nav.buttons.bar"), self.show_bar),
        ('butcher', _t("nav.buttons.butcher"), self.show_butcher_gui),
    ]

    if any(name in visible_buttons for name, _, _ in dining_buttons_data):
        dining_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.dining") + " ▶",
                               command=lambda: open_category_window(_t("nav.categories.dining"), dining_buttons_data),
                               style='Large.TButton')
        dining_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Shops & Retail ----------
    shops_buttons_data = [
        ('university_shop', _t("nav.buttons.university_shop"), self.show_university_shop),
        ('charity_shop', _t("nav.buttons.charity_shop"), self.show_charity_shop),
        ('phoneshop', _t("nav.buttons.phoneshop"), self.show_phoneshop_gui),
        ('musicshop', _t("nav.buttons.musicshop"), self.show_musicshop_gui),
        ('grocery_shop', _t("nav.buttons.grocery_shop"), self.show_grocery_shop),
    ]

    if any(name in visible_buttons for name, _, _ in shops_buttons_data):
        shops_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.shops") + " ▶",
                              command=lambda: open_category_window(_t("nav.categories.shops"), shops_buttons_data),
                              style='Large.TButton')
        shops_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Personal Services ----------
    personal_buttons_data = [
        ('barber', _t("nav.buttons.barber"), self.show_barber_gui),
        ('nailbar', _t("nav.buttons.nailbar"), self.show_nailbar_gui),
    ]

    if any(name in visible_buttons for name, _, _ in personal_buttons_data):
        personal_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.personal_services") + " ▶",
                                 command=lambda: open_category_window(_t("nav.categories.personal_services"), personal_buttons_data),
                                 style='Large.TButton')
        personal_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Transportation ----------
    transport_buttons_data = [
        ('taxi_booking', _t("nav.buttons.taxi_booking"), self.show_taxi_booking_gui),
        ('train_station', _t("nav.buttons.train_station"), self.show_train_station_gui),
        ('carrental', _t("nav.buttons.carrental"), self.show_carrental_gui),
        ('parking_management', _t("nav.buttons.parking"), self.show_parking_management),
        ('trip_management', _t("nav.buttons.trip_management"), self.show_trip_management_gui),
    ]

    if any(name in visible_buttons for name, _, _ in transport_buttons_data):
        transport_btn = ttk.Button(scrollable_frame, text=_t("nav.categories.transportation") + " ▶",
                                   command=lambda: open_category_window(_t("nav.categories.transportation"), transport_buttons_data),
                                   style='Large.TButton')
        transport_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Student Services ----------
    student_services_buttons_data = [
        ('student_dashboard', _t('nav.buttons.student_dashboard'), self.show_student_dashboard_gui),
        ('student_support', _t('nav.buttons.student_support'), self.open_student_support_portal_gui),
        ('helpdesk', _t('nav.buttons.helpdesk'), self.open_helpdesk_gui),
        ('early_warning_system', _t('nav.buttons.early_warning'), self.show_early_warning_gui),
        ('accessibility', _t('nav.buttons.accessibility'), self.show_accessibility_portal_gui),
        ('portfolio', _t('nav.buttons.portfolio'), self.show_portfolio_system_gui),
        ('advising_portal', _t('nav.buttons.advising_portal'), self.show_advising_portal_gui),
    ]

    if any(name in visible_buttons for name, _, _ in student_services_buttons_data):
        student_services_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.services') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.services'), student_services_buttons_data),
                                   style='Large.TButton')
        student_services_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Career & Alumni ----------
    career_and_alumni_buttons_data = [
        ('career_services', _t('nav.buttons.career_services'), self.show_career_services_gui),
        ('internship_portal', _t('nav.buttons.internship_portal'), self.open_internship_portal_gui),
        ('student_jobs', _t('nav.buttons.student_jobs'), self.show_student_jobs_gui),
        ('alumni_management', _t('nav.buttons.alumni'), self.open_alumni_portal_gui),
    ]

    if any(name in visible_buttons for name, _, _ in career_and_alumni_buttons_data):
        career_and_alumni_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.career_alumni') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.career_alumni'), career_and_alumni_buttons_data),
                                   style='Large.TButton')
        career_and_alumni_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Family & Legal ----------
    family_and_legal_buttons_data = [
        ('parent_portal', _t('nav.buttons.family_portal'), self.open_parent_portal_gui),
        ('legal_services', _t('nav.buttons.legal_services'), self.show_legal_services_gui),
    ]

    if any(name in visible_buttons for name, _, _ in family_and_legal_buttons_data):
        family_and_legal_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.family_legal') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.family_legal'), family_and_legal_buttons_data),
                                   style='Large.TButton')
        family_and_legal_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Entertainment ----------
    entertainment_buttons_data = [
        ('cinema', _t('nav.buttons.cinema'), self.show_cinema_gui),
        ('betting_shop', _t('nav.buttons.betting_shop'), self.show_betting_shop_gui),
    ]

    if any(name in visible_buttons for name, _, _ in entertainment_buttons_data):
        entertainment_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.entertainment') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.entertainment'), entertainment_buttons_data),
                                   style='Large.TButton')
        entertainment_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Communication ----------
    communication_buttons_data = [
        ('communication_hub', _t('nav.buttons.communication_hub'), self.show_email_sms_gui),
        ('feedback_system', _t('nav.buttons.feedback_system'), self.show_feedback_system_gui),
    ]

    if any(name in visible_buttons for name, _, _ in communication_buttons_data):
        communication_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.communication') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.communication'), communication_buttons_data),
                                   style='Large.TButton')
        communication_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Analytics & Reporting ----------
    analytics_and_reporting_buttons_data = [
        ('integrated_dashboard', _t('nav.buttons.dashboard'), self.show_integrated_dashboard),
        ('analytics', _t('nav.buttons.analytics'), self.show_analytics),
    ]

    if any(name in visible_buttons for name, _, _ in analytics_and_reporting_buttons_data):
        analytics_and_reporting_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.analytics') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.analytics'), analytics_and_reporting_buttons_data),
                                   style='Large.TButton')
        analytics_and_reporting_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Documents & Export ----------
    documents_and_export_buttons_data = [
        ('document_manager', _t('nav.buttons.document_manager'), self.show_document_manager),
        ('export', _t('nav.buttons.export_options'), self.export_data_dialog),
        ('backup_gui', _t('nav.buttons.data_backup'), self.show_data_backup_gui),
        ('pdf_export', _t('nav.buttons.pdf_export'), self.show_pdf_export_gui),
    ]

    if any(name in visible_buttons for name, _, _ in documents_and_export_buttons_data):
        documents_and_export_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.documents') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.documents'), documents_and_export_buttons_data),
                                   style='Large.TButton')
        documents_and_export_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- AI & Advanced Tools ----------
    ai_and_advanced_tools_buttons_data = [
        ('ai_features', _t('nav.buttons.ai_features'), self.show_ai_features_gui),
        ('mobile_app_pwa', _t('nav.buttons.mobile_app'), self.show_mobile_app_pwa_gui),
        ('blockchain_credentials', _t('nav.buttons.blockchain'), self.show_blockchain_credentials_gui),
        ('extras_launcher', _t('nav.buttons.extras'), self.show_extras_launcher),
        ('todo_app', _t('nav.buttons.todo_app'), self.show_todo_app_gui),
    ]

    if any(name in visible_buttons for name, _, _ in ai_and_advanced_tools_buttons_data):
        ai_and_advanced_tools_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.tools') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.tools'), ai_and_advanced_tools_buttons_data),
                                   style='Large.TButton')
        ai_and_advanced_tools_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Security & Safety ----------
    security_and_safety_buttons_data = [
        ('security_desk', _t('nav.buttons.security_desk'), self.show_security_desk_gui),
        ('police_station', _t('nav.buttons.police_station'), self.show_police_station_gui),
    ]

    if any(name in visible_buttons for name, _, _ in security_and_safety_buttons_data):
        security_and_safety_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.security_safety') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.security_safety'), security_and_safety_buttons_data),
                                   style='Large.TButton')
        security_and_safety_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Community Services ----------
    community_services_buttons_data = [
        ('church_management', _t('nav.buttons.church_management'), self.show_church_management_gui),
    ]

    if any(name in visible_buttons for name, _, _ in community_services_buttons_data):
        community_services_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.community') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.community'), community_services_buttons_data),
                                   style='Large.TButton')
        community_services_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Human Resources ----------
    human_resources_buttons_data = [
        ('view_staff', _t('nav.buttons.view_staff'), self.view_staff),
        ('create_staff', _t('nav.buttons.create_staff'), self.create_staff_dialog),
        ('search_staff', _t('nav.buttons.search_staff'), self.search_staff_dialog),
        ('delete_staff', _t('nav.buttons.delete_staff'), self.delete_staff_dialog),
        ('staff_hr', _t('nav.buttons.staff_hr'), self.show_staff_hr_gui),
    ]

    if any(name in visible_buttons for name, _, _ in human_resources_buttons_data):
        human_resources_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.human_resources') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.human_resources'), human_resources_buttons_data),
                                   style='Large.TButton')
        human_resources_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Administration ----------
    administration_buttons_data = [
        ('user_management', _t('nav.buttons.user_management'), self.show_user_management),
        ('system_admin_gui', _t('nav.buttons.system_admin'), self.show_system_administration_gui),
        ('security_dashboard', _t('nav.buttons.security'), self.show_security_dashboard),
        ('integration_marketplace', _t('nav.buttons.integration_marketplace'), self.show_integration_marketplace_gui),
        ('admissions_crm', _t('nav.buttons.admissions_crm'), self.show_admissions_crm_gui),
        ('usage_adoption_reports', _t('nav.buttons.usage_reports'), self.show_usage_adoption_reports),
        ('custom_report_builder', _t('nav.buttons.custom_report_builder'), self.show_custom_report_builder),
        ('hesa_export', 'HESA Data Export', self.show_hesa_export_gui),
        ('clearing_adjustment', 'Clearing & Adjustment', self.show_clearing_adjustment_gui),
    ]

    if any(name in visible_buttons for name, _, _ in administration_buttons_data):
        administration_btn = ttk.Button(scrollable_frame, text=_t('nav.categories.administration') + " ▶",
                                   command=lambda: open_category_window(_t('nav.categories.administration'), administration_buttons_data),
                                   style='Large.TButton')
        administration_btn.pack(fill=tk.X, pady=2, padx=5)

    # ---------- Cross-System ----------
    cross_system_buttons_data = [
        ('student_journey', 'Student Journey', self.show_student_journey_gui),
        ('analytics_dashboard', 'Analytics Dashboard', self.show_analytics_dashboard_gui),
        ('outcome_tracking', 'Outcome Tracking', self.show_outcome_tracking_gui),
        ('predictive_alerts', 'Predictive Alerts', self.show_predictive_alerts_gui),
        ('bulk_transfer', 'Bulk Transfer', self.show_bulk_transfer_gui),
        ('transfer_documents', 'Transfer Documents', self.show_transfer_documents_gui),
        ('reverse_lookup', 'Reverse Lookup', self.show_reverse_lookup_gui),
        ('parent_continuity', 'Parent Continuity', self.show_parent_continuity_gui),
        ('cross_system_calendar', 'Cross-System Calendar', self.show_cross_system_calendar_gui),
        ('central_admin_portal', 'Central Admin Portal', self.show_central_admin_gui),
        ('gdpr_compliance', 'GDPR Compliance', self.show_gdpr_compliance_gui),
        ('shared_documents', 'Shared Documents', self.show_shared_documents_gui),
        ('student_self_service', 'Student Self-Service', self.show_student_self_service_gui),
        ('certificates', 'Certificates', self.show_certificates_gui),
    ]

    if any(name in visible_buttons for name, _, _ in cross_system_buttons_data):
        cross_system_btn = ttk.Button(scrollable_frame, text="Cross-System" + " \u25b6",
                                   command=lambda: open_category_window("Cross-System", cross_system_buttons_data),
                                   style='Large.TButton')
        cross_system_btn.pack(fill=tk.X, pady=2, padx=5)

    # Finalize scroll region
    scrollable_frame.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))
def rebuild_navigation_panel(self):
    """Rebuild the navigation panel based on current user role"""
    if hasattr(self, 'nav_parent') and self.nav_parent:
        try:
            # Force GUI update before starting rebuild
            self.root.update_idletasks()

            self.create_navigation_panel(self.nav_parent)

            # Force another GUI update after rebuild completes
            self.root.update_idletasks()

            logger.debug(f"Navigation panel rebuilt for role: {self.auth.current_user.get('role') if self.auth and self.auth.current_user else 'Not logged in'}")
        except Exception as e:
            logger.error(f"Failed to rebuild navigation panel: {e}")
def create_content_area(self, parent):
    """Create the main content area with scrollbar"""
    # Outer frame to hold canvas and scrollbar
    outer_frame = ttk.LabelFrame(parent, text=_t("gui.content"), padding="5")
    outer_frame.grid(row=1, column=1, sticky="nsew")
    outer_frame.columnconfigure(0, weight=1)
    outer_frame.rowconfigure(0, weight=1)

    # Canvas for scrolling
    self.content_canvas = tk.Canvas(outer_frame, highlightthickness=0)
    self.content_canvas.grid(row=0, column=0, sticky="nsew")

    # Vertical scrollbar
    v_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=self.content_canvas.yview)
    v_scrollbar.grid(row=0, column=1, sticky="ns")

    # Horizontal scrollbar
    h_scrollbar = ttk.Scrollbar(outer_frame, orient="horizontal", command=self.content_canvas.xview)
    h_scrollbar.grid(row=1, column=0, sticky="ew")

    self.content_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Inner frame for actual content
    self.content_frame = ttk.Frame(self.content_canvas, padding="10")
    self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

    # Configure scroll region when content changes
    def configure_scroll_region(event):
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    self.content_frame.bind("<Configure>", configure_scroll_region)

    # Make canvas resize with window
    def configure_canvas_width(event):
        self.content_canvas.itemconfig(self.content_window, width=event.width)

    self.content_canvas.bind("<Configure>", configure_canvas_width)

    # Enable mousewheel scrolling
    def on_mousewheel(event):
        self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    self.content_canvas.bind("<Enter>", lambda e: self.content_canvas.bind_all("<MouseWheel>", on_mousewheel))
    self.content_canvas.bind("<Leave>", lambda e: self.content_canvas.unbind_all("<MouseWheel>"))

    self.content_frame.columnconfigure(0, weight=1)
    self.content_frame.rowconfigure(0, weight=1)

    # Ensure parent properly configures this cell
    parent.rowconfigure(1, weight=1)
    parent.columnconfigure(1, weight=1)
def get_visible_buttons_for_role(self, role=None):
    """
    Return a set of button names that should be visible for the given role.
    If role is None (not logged in), only login button is visible.
    """
    if role is None:
        return {'login'}

    # Get user object for detailed permission checking
    user = self.auth.current_user if self.auth else None
    permissions = user.get('permissions', []) if user else []

    # Helper flags
    is_admin = role == 'admin'
    is_staff = role in ('admin', 'staff')
    is_instructor = role in ('admin', 'staff', 'instructor')
    is_student = role == 'student'

    # Base buttons for all logged-in users
    visible = {
        'change_password', 'mfa_setup', 'security_questions',
        # Student services available to all
        'assignments', 'academic_calendar', 'health_portal', 'student_union_portal',
        'campus_events', 'university_shop', 'cafe_system', 'takeaway_system', 'grocery_shop', 'bar', 'student_support', 'internship_portal',
        'career_services', 'helpdesk', 'financial_aid', 'integrated_dashboard',
        'ai_features', 'mobile_app_pwa', 'parent_portal', 'extras_launcher',
        'legal_services', 'betting_shop', 'cinema', 'mail_post', 'gym', 'dentist',
        'butcher', 'barber', 'nailbar', 'carrental', 'equipment', 'phoneshop', 'musicshop',
        # Transportation services
        'taxi_booking', 'train_station',
        # New apps - available to all logged-in users
        'todo_app', 'security_desk', 'church_management',
        # Additional services
        'bank_app', 'exam_portal',
        # Student Success & Engagement (v5.5.0) - available to all
        'academic_progress', 'ai_study', 'study_matching_gui',
        'student_jobs', 'roommate_finder',
        'campus_navigation', 'lost_found', 'marketplace', 'wellness_hub',
        'accessibility', 'social_matching', 'portfolio', 'events_discovery',
        'feedback_system',
        # Student features (v5.40+)
        'advising_portal', 'student_id_card', 'study_room_booking',
        'printing_services',
        # Note: budget_tracker, scholarship_finder moved to Finance GUI
        # Note: notifications_hub moved to Email GUI
        # Shared modules available to all (including parents)
        'cross_system_calendar', 'digital_transcript', 'certificates',
        # LMS
        'lms',
        # Absence tracker — available to all roles
        'absence_tracker',
        # New features (modules 21-30) - student-accessible
        'student_app', 'achievement_badges', 'study_recommendations',
    }

    # Student-specific additions
    if is_student:
        visible.update({
            'student_records', 'grade_tracking_gui', 'library',
            'scheduling', 'trip_management', 'communication_hub',
            'office_hours',
            # Student-facing features
            'student_analytics', 'learning_outcomes',
            'my_timetable', 'student_registration', 'student_dashboard',
            # Shared cross-system modules for students
            'student_self_service', 'digital_transcript', 'cross_system_calendar',
        })

    # Instructor additions (includes students' features)
    if is_instructor:
        visible.update({
            'student_records', 'course_management', 'module_management',
            'grade_tracking_gui', 'library', 'virtual_classroom',
            'scheduling', 'attendance', 'analytics',
            'export', 'early_warning_system', 'communication_hub',
            'office_hours',
            'my_timetable', 'student_registration', 'student_dashboard',
        })

    # Staff additions (includes instructors' features)
    if is_staff:
        visible.update({
            'create_student', 'search_students', 'advanced_search_gui',
            'batch_operations', 'housing_accommodations',
            'restaurant_management', 'cafe_system', 'takeaway_system', 'grocery_shop', 'parking_management', 'facilities_management',
            'alumni_management', 'communication_hub',
            'admissions_crm', 'blockchain_credentials',
            'document_manager', 'pdf_export', 'charity_shop',
            # Staff-only security tools
            'police_station',
            # Staff HR management
            'staff_hr',
            # Staff CRUD management
            'view_staff', 'create_staff', 'search_staff',
            # Office hours
            'office_hours',
            # New features - staff level
            # Cross-system modules
            'student_journey',
            'analytics_dashboard', 'outcome_tracking', 'predictive_alerts',
            'bulk_transfer', 'transfer_documents', 'reverse_lookup',
            'parent_continuity', 'cross_system_calendar',
            'shared_documents',
            'student_self_service', 'digital_transcript',
        })

    # Admin-only additions (full access)
    if is_admin:
        visible.update({
            'delete_student', 'finance_management', 'finance_reporting',
            'user_management', 'system_admin_gui', 'security_dashboard',
            'integration_marketplace', 'backup_gui',
            # Admin-only staff management
            'delete_staff',
            # Admin tools
            'usage_adoption_reports',
            'custom_report_builder',
            # Admin-only shared modules
            'central_admin_portal', 'gdpr_compliance',
            # New features - admin level
            'hesa_export', 'clearing_adjustment',
        })

    # Additional permission-based checks for edge cases
    if 'view_any_student' in permissions or 'view_own_record' in permissions:
        visible.add('student_records')
    if 'manage_courses' in permissions or 'view_courses' in permissions:
        visible.add('course_management')
    if any(p in permissions for p in ['view_books', 'manage_books', 'manage_loans', 'checkout_books']):
        visible.add('library')
    if 'view_trips' in permissions or 'register_for_trips' in permissions or 'manage_trips' in permissions:
        visible.add('trip_management')

    return visible
def clear_content(self):
    """Clear the content area"""
    # Check if content_frame exists before trying to clear it
    if hasattr(self, 'content_frame') and self.content_frame:
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    else:
        # If content_frame doesn't exist yet, just return
        return
def show_welcome(self):
    """Show welcome message"""
    self.clear_content()

    welcome_text = _t("gui.welcome_text")

    welcome_label = ttk.Label(self.content_frame, text=welcome_text, justify=tk.LEFT, font=('Arial', 11))
    welcome_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=20, pady=20)

    # System status
    if self.auth.current_user:
        status_frame = ttk.LabelFrame(self.content_frame, text=_t("gui.quick_actions"), padding="15")
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=20, pady=10)

        user = self.auth.current_user
        permissions = user.get('permissions', [])

        quick_actions = []

        if 'view_any_student' in permissions or 'view_own_record' in permissions:
            quick_actions.append((_t("gui.view_student_records"), self.show_student_records))

        if 'create_student' in permissions:
            quick_actions.append((_t("gui.create_new_student"), self.create_student_dialog))

        if 'access_chatbot' in permissions:
            quick_actions.append((_t("gui.launch_chatbot"), self.show_chatbot))

        if 'view_analytics' in permissions:
            quick_actions.append((_t("gui.view_analytics"), self.show_analytics))

        if any(p in permissions for p in ['view_trips', 'register_for_trips', 'manage_trips']):
            quick_actions.append((_t("gui.trip_management"), self.show_trip_management_gui))

        if ADVANCED_SEARCH_GUI_AVAILABLE and 'view_any_student' in permissions:
            quick_actions.append((_t("gui.advanced_search"), self.show_advanced_search_gui))

        if ('manage_schedules' in permissions) or ('view_own_timetable' in permissions):
            quick_actions.append((_t("gui.module_scheduling"), self.show_module_scheduling))

        # Create buttons for quick actions
        for i, (text, command) in enumerate(quick_actions[:4]):  # Show up to 4 quick actions
            row = i // 2
            col = i % 2
            ttk.Button(status_frame, text=text, command=command, width=20).grid(
                row=row, column=col, padx=10, pady=5, sticky=tk.W)
def show_main_interface(self):
    """Show main interface when authenticated"""
    # Update status variables immediately
    if self.auth.current_user:
        user = self.auth.current_user
        self.current_user_var.set(f"{user['username']} ({user['role']})")
        self.status_var.set(_t("gui.loading_menu"))  # Show loading message
    else:
        self.current_user_var.set(_t("gui.not_logged_in"))
        self.status_var.set(_t("gui.not_logged_in"))

    self.update_login_logout_button()

    # Show role-based dashboard immediately on login
    self.show_integrated_dashboard()

    # Defer navigation panel rebuild to allow GUI to respond
    # This prevents the freeze during login
    self.root.after(50, self._deferred_navigation_rebuild)

def _deferred_navigation_rebuild(self):
    """Rebuild navigation panel after GUI has rendered (non-blocking)"""
    try:
        self.rebuild_navigation_panel()

        # Update status to "Logged in" after navigation is ready
        if self.auth.current_user:
            self.status_var.set(_t("gui.logged_in"))
    except Exception as e:
        logger.error(f"Error rebuilding navigation panel: {e}")
        if self.auth.current_user:
            self.status_var.set(_t("gui.logged_in"))

def update_status(self):
    """Update the status display and rebuild navigation for role-based UI"""
    if self.auth.current_user:
        user = self.auth.current_user
        self.current_user_var.set(f"{user['username']} ({user['role']})")
        self.status_var.set(_t("gui.logged_in"))
    else:
        self.current_user_var.set(_t("gui.not_logged_in"))
        self.status_var.set(_t("gui.not_logged_in"))

    # Rebuild navigation panel to show role-specific buttons
    self.rebuild_navigation_panel()
    self.update_login_logout_button()
def restart_gui(self):
    """Restart the GUI to apply language changes"""
    try:
        # Cancel any pending timers before destroying window
        self._cancel_timers()
        self.root.destroy()
        # Re-initialize
        init_i18n()  # Reload translations
        # Import locally to avoid circular import
        from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
        app = UnifiedManagementGUI(self.auth)
        app.run()
    except Exception as e:
        logger.error(f"Error restarting GUI: {e}")
def _cancel_timers(self):
    """Cancel all scheduled timers to prevent errors on window destroy"""
    try:
        if self._session_timer_id is not None:
            self.root.after_cancel(self._session_timer_id)
            self._session_timer_id = None
    except Exception:
        pass  # Ignore errors if timer already cancelled or window destroyed
