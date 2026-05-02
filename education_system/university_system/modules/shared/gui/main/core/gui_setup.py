# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import json
from pathlib import Path

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

_PIN_FILE = Path.home() / ".config" / "edu_system" / "university_pinned.json"


def _load_pinned():
    try:
        if _PIN_FILE.exists():
            data = json.loads(_PIN_FILE.read_text())
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.debug(f"Could not load pinned: {e}")
    return []


def _save_pinned(pins):
    try:
        _PIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PIN_FILE.write_text(json.dumps(list(pins)))
    except Exception as e:
        logger.warning(f"Could not save pinned: {e}")

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

    # ── Inline category renderer (replaces the popup-per-category) ──
    # Pre-8.117.17 each category button (e.g. "Academic Management ▶")
    # opened a 900×600 modal Toplevel containing the actual feature
    # buttons. Two clicks to launch anything, plus a window-creation
    # latency hit, plus losing the sidebar context while the popup was
    # open. The sub-frame is built lazily on first expand and packed
    # inline below the category's toggle button — same right-click
    # pin/unpin affordance, but feature-launching is now immediate
    # and subsequent launches in the same category stay 1-click as
    # long as the section is left open.
    def _filter_visible_sections(sections):
        """Drop sections whose buttons aren't visible to the current
        user, then drop empty sections. Returns the list of
        ``(section_label, [(name, text, cmd), ...])`` tuples that
        actually need rendering."""
        visible_sections = []
        for section_label, buttons_data in sections:
            visible_btns = [
                (name, text, cmd) for name, text, cmd in buttons_data
                if name in visible_buttons
            ]
            if visible_btns:
                visible_sections.append((section_label, visible_btns))
        return visible_sections

    def _toggle_pin_inline(name):
        pins = _load_pinned()
        if name in pins:
            pins.remove(name)
        else:
            pins.append(name)
        _save_pinned(pins)
        # Rebuild so the Pinned section reflects the change. The
        # currently-expanded category collapses on rebuild, which is
        # the same behaviour as the previous popup (which closed on
        # pin) so muscle memory is preserved.
        self.rebuild_navigation_panel()

    def _bind_pin_menu_inline(widget, name):
        def _show_menu(event):
            m = tk.Menu(widget, tearoff=0)
            pins = _load_pinned()
            label = "Unpin from sidebar" if name in pins else "Pin to sidebar"
            m.add_command(label=label,
                          command=lambda n=name: _toggle_pin_inline(n))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
        widget.bind('<Button-3>', _show_menu)

    def _populate_category_subframe(sub_frame, visible_sections):
        """Render the category's section labels + feature buttons
        inside *sub_frame*. Single-column packing — the sidebar is
        narrow, so the previous 4-column grid doesn't fit. Section
        labels are only rendered when there's more than one
        section."""
        show_headers = len(visible_sections) > 1
        for section_label, btns in visible_sections:
            if show_headers:
                ttk.Label(
                    sub_frame, text=section_label,
                    font=('Arial', 9, 'bold'), foreground='#555555',
                    anchor='w',
                ).pack(fill=tk.X, padx=(14, 4), pady=(6, 2))
            for name, text, cmd in btns:
                btn = ttk.Button(sub_frame, text=text, command=cmd)
                btn.pack(fill=tk.X, padx=(14, 4), pady=1)
                _bind_pin_menu_inline(btn, name)

    # ---------- Authentication ----------
    authentication_buttons_data = [
        ('login', _t("common.logout"), self.logout_user),
        ('change_password', _t("nav.buttons.change_password"), self.show_change_password),
        ('mfa_setup', _t("nav.buttons.mfa_setup"), self.show_mfa_setup),
        ('security_questions', "Security Questions", self.show_security_questions),
        ('toggle_verification', _t("nav.buttons.toggle_verification"), self.toggle_login_verification),
    ]

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

    # ---------- Academic Management ----------
    academic_buttons_data = [
        ('academic_hub', '🏛 Academic Hub', self.show_academic_hub),
        ('course_management', _t("nav.buttons.course_management"), self.show_course_management),
        ('module_management', _t("nav.buttons.module_management"), self.show_module_management),
        ('assignments', _t("nav.buttons.assignments"), self.show_assignments),
        ('grade_tracking_gui', _t("nav.buttons.grade_tracking"), self.show_grade_tracking_gui),
        ('student_registration', _t("nav.buttons.student_registration"), self.show_student_registration_gui),
        ('library', _t("nav.buttons.library"), self.show_library_management),
        ('ai_study', _t("nav.buttons.ai_study"), self.show_ai_study_gui),
        ('study_matching_gui', _t("nav.buttons.study_matching"), self.show_study_matching_gui),
        ('office_hours', _t("nav.buttons.office_hours"), self.show_office_hours_gui),
        ('new_feature_course_evaluation_system', 'Course Evaluation', self.show_new_feature_course_evaluation_system),
        ('new_feature_module_evaluation_portal', 'Module Evaluation', self.show_new_feature_module_evaluation_portal),
        ('new_feature_lecturer_evaluation', 'Lecturer Evaluation', self.show_new_feature_lecturer_evaluation),
        ('new_feature_lesson_planner', 'Lesson Planner', self.show_new_feature_lesson_planner),
        ('new_feature_tutor_groups', 'Tutor Groups', self.show_new_feature_tutor_groups),
        ('new_feature_university_research', 'Research Portal', self.show_new_feature_university_research),
        ('study_recommendations', 'Study Recommendations', self.show_study_recommendations_gui),
    ]
    if VIRTUAL_CLASSROOM_AVAILABLE:
        academic_buttons_data.append(('virtual_classroom', _t("nav.buttons.virtual_classroom"), self.show_virtual_classroom_gui))

    # ---------- Scheduling & Attendance ----------
    sched_buttons_data = [
        ('academic_calendar', _t("nav.buttons.academic_calendar"), self.show_academic_calendar),
        ('scheduling', _t("nav.buttons.scheduling"), self.show_module_scheduling),
        ('my_timetable', _t("nav.buttons.my_timetable"), self.show_student_timetable_gui),
        ('attendance', _t("nav.buttons.attendance"), self.open_attendance_gui),
        ('exam_portal', "Exam Management", self.show_exam_portal),
    ]

    # ---------- Finance ----------
    finance_buttons_data = [
        ('finance_management', _t("nav.buttons.finance_management"), self.show_finance_management),
        ('my_finance', _t("nav.buttons.my_finance"), self.show_student_finance_account),
    ]

    # ---------- Health & Wellness ----------
    health_buttons_data = [
        ('health_portal', _t("nav.buttons.health_portal"), self.open_health_portal_gui),
        ('new_feature_first_aid_portal', 'First Aid Portal', self.show_new_feature_first_aid_portal),
        ('gym', "Gym", self.show_gym_gui),
    ]

    # ---------- Accommodation ----------
    accommodation_buttons_data = [
        ('housing_accommodations', _t("nav.buttons.housing_accommodation"), self.show_housing_accommodations),
    ]

    # ---------- Campus Life ----------
    campus_buttons_data = [
        ('student_union_portal', _t("nav.buttons.student_union"), self.open_student_union_portal_gui),
        ('campus_events', _t("nav.buttons.campus_events"), self.show_campus_events_gui),
        ('events_discovery', _t("nav.buttons.events_discovery"), self.show_events_discovery_gui),
        ('facilities_management', _t("nav.buttons.facilities"), self.show_facilities_management_gui),
        ('new_feature_room_booking', 'Room Booking', self.show_new_feature_room_booking),
        ('new_feature_building_management', 'Building Management', self.show_new_feature_building_management),
        ('equipment', _t("nav.buttons.equipment"), self.show_equipment_gui),
    ]

    # ---------- Dining & Food ----------
    dining_buttons_data = [
        ('restaurant_management', _t("nav.buttons.dining_services"), self.show_restaurant_management),
        ('cafe_system', _t("nav.buttons.cafe_system"), self.show_cafe_system),
        ('takeaway_system', _t("nav.buttons.takeaway"), self.show_takeaway_system),
        ('bar', _t("nav.buttons.bar"), self.show_bar),
        ('butcher', _t("nav.buttons.butcher"), self.show_butcher_gui),
        ('new_feature_bakery_shop', 'Bakery Shop', self.show_new_feature_bakery_shop),
    ]

    # ---------- Shops & Retail ----------
    shops_buttons_data = [
        ('university_shop', _t("nav.buttons.university_shop"), self.show_university_shop),
        ('charity_shop', _t("nav.buttons.charity_shop"), self.show_charity_shop),
        ('phoneshop', _t("nav.buttons.phoneshop"), self.show_phoneshop_gui),
        ('musicshop', _t("nav.buttons.musicshop"), self.show_musicshop_gui),
        ('grocery_shop', _t("nav.buttons.grocery_shop"), self.show_grocery_shop),
    ]

    # ---------- Personal Services ----------
    personal_buttons_data = [
        ('barber', _t("nav.buttons.barber"), self.show_barber_gui),
        ('nailbar', _t("nav.buttons.nailbar"), self.show_nailbar_gui),
    ]

    # ---------- Transportation ----------
    transport_buttons_data = [
        ('taxi_booking', _t("nav.buttons.taxi_booking"), self.show_taxi_booking_gui),
        ('train_station', _t("nav.buttons.train_station"), self.show_train_station_gui),
        ('carrental', _t("nav.buttons.carrental"), self.show_carrental_gui),
        ('parking_management', _t("nav.buttons.parking"), self.show_parking_management),
        ('trip_management', _t("nav.buttons.trip_management"), self.show_trip_management_gui),
    ]

    # ---------- Student Services ----------
    student_services_buttons_data = [
        ('student_dashboard', _t('nav.buttons.student_dashboard'), self.show_student_dashboard_gui),
        ('student_support', _t('nav.buttons.student_support'), self.open_student_support_portal_gui),
        ('helpdesk', _t('nav.buttons.helpdesk'), self.open_helpdesk_gui),
        ('early_warning_system', _t('nav.buttons.early_warning'), self.show_early_warning_gui),
        ('new_feature_intervention_support', 'Intervention Support', self.show_new_feature_intervention_support),
        ('new_feature_intervention_outcomes', 'Intervention Outcomes', self.show_new_feature_intervention_outcomes),
        ('new_feature_safeguarding_system', 'Safeguarding', self.show_new_feature_safeguarding_system),
        ('new_feature_mentoring_matching', 'Peer Mentoring Matching', self.show_new_feature_mentoring_matching),
        ('accessibility', _t('nav.buttons.accessibility'), self.show_accessibility_portal_gui),
        ('equality_diversity', 'Equality & Diversity', self.show_equality_diversity_gui),
        ('portfolio', _t('nav.buttons.portfolio'), self.show_portfolio_system_gui),
        ('advising_portal', _t('nav.buttons.advising_portal'), self.show_advising_portal_gui),
    ]

    # ---------- Career & Alumni ----------
    career_and_alumni_buttons_data = [
        ('career_services', _t('nav.buttons.career_services'), self.show_career_services_gui),
        ('internship_portal', _t('nav.buttons.internship_portal'), self.open_internship_portal_gui),
        ('new_feature_apprenticeship_system', 'Apprenticeships', self.show_new_feature_apprenticeship_system),
        ('new_feature_placement_tracker', 'Placement Hours', self.show_new_feature_placement_tracker),
        ('new_feature_employer_portal', 'Employer Portal', self.show_new_feature_employer_portal),
        ('student_jobs', _t('nav.buttons.student_jobs'), self.show_student_jobs_gui),
        ('alumni_management', _t('nav.buttons.alumni'), self.open_alumni_portal_gui),
    ]

    # ---------- Family & Legal ----------
    family_and_legal_buttons_data = [
        ('parent_portal', _t('nav.buttons.family_portal'), self.open_parent_portal_gui),
        ('legal_services', _t('nav.buttons.legal_services'), self.show_legal_services_gui),
        ('new_feature_disciplinary_portal', 'Disciplinary Portal', self.show_new_feature_disciplinary_portal),
        ('new_feature_risk_management', 'Risk Management', self.show_new_feature_risk_management),
    ]

    # ---------- Entertainment ----------
    entertainment_buttons_data = [
        ('cinema', _t('nav.buttons.cinema'), self.show_cinema_gui),
        ('betting_shop', _t('nav.buttons.betting_shop'), self.show_betting_shop_gui),
    ]

    # ---------- Communication ----------
    communication_buttons_data = [
        ('communication_hub', _t('nav.buttons.communication_hub'), self.show_email_sms_gui),
        ('feedback_system', _t('nav.buttons.feedback_system'), self.show_feedback_system_gui),
        ('new_feature_complaints_portal', 'Complaints Portal', self.show_new_feature_complaints_portal),
    ]

    # ---------- Analytics & Reporting ----------
    analytics_and_reporting_buttons_data = [
        ('integrated_dashboard', _t('nav.buttons.dashboard'), self.show_integrated_dashboard),
        ('analytics', _t('nav.buttons.analytics'), self.show_analytics),
        ('new_feature_kpi_dashboard', 'KPI Dashboard', self.show_new_feature_kpi_dashboard),
    ]

    # ---------- Documents & Export ----------
    documents_and_export_buttons_data = [
        ('document_manager', _t('nav.buttons.document_manager'), self.show_document_manager),
        ('export', _t('nav.buttons.export_options'), self.export_data_dialog),
        ('backup_gui', _t('nav.buttons.data_backup'), self.show_data_backup_gui),
        ('pdf_export', _t('nav.buttons.pdf_export'), self.show_pdf_export_gui),
    ]

    # ---------- AI & Advanced Tools ----------
    ai_and_advanced_tools_buttons_data = [
        ('ai_features', _t('nav.buttons.ai_features'), self.show_ai_features_gui),
        ('mobile_app_pwa', _t('nav.buttons.mobile_app'), self.show_mobile_app_pwa_gui),
        ('blockchain_credentials', _t('nav.buttons.blockchain'), self.show_blockchain_credentials_gui),
        ('extras_launcher', _t('nav.buttons.extras'), self.show_extras_launcher),
        ('todo_app', _t('nav.buttons.todo_app'), self.show_todo_app_gui),
    ]

    # ---------- Security & Safety ----------
    security_and_safety_buttons_data = [
        ('security_desk', _t('nav.buttons.security_desk'), self.show_security_desk_gui),
        ('police_station', _t('nav.buttons.police_station'), self.show_police_station_gui),
    ]

    # ---------- Community Services ----------
    community_services_buttons_data = [
        ('church_management', _t('nav.buttons.church_management'), self.show_church_management_gui),
    ]

    # ---------- Human Resources ----------
    human_resources_buttons_data = [
        ('view_staff', _t('nav.buttons.view_staff'), self.view_staff),
        ('create_staff', _t('nav.buttons.create_staff'), self.create_staff_dialog),
        ('search_staff', _t('nav.buttons.search_staff'), self.search_staff_dialog),
        ('delete_staff', _t('nav.buttons.delete_staff'), self.delete_staff_dialog),
        ('staff_hr', _t('nav.buttons.staff_hr'), self.show_staff_hr_gui),
    ]

    # ---------- Administration ----------
    administration_buttons_data = [
        ('user_management', _t('nav.buttons.user_management'), self.show_user_management),
        ('system_admin_gui', _t('nav.buttons.system_admin'), self.show_system_administration_gui),
        ('security_dashboard', _t('nav.buttons.security'), self.show_security_dashboard),
        ('new_feature_health_safety_portal', 'Health & Safety', self.show_new_feature_health_safety_portal),
        ('new_feature_background_checker', 'Background Checker', self.show_new_feature_background_checker),
        ('integration_marketplace', _t('nav.buttons.integration_marketplace'), self.show_integration_marketplace_gui),
        ('admissions_crm', _t('nav.buttons.admissions_crm'), self.show_admissions_crm_gui),
        ('usage_adoption_reports', _t('nav.buttons.usage_reports'), self.show_usage_adoption_reports),
        ('custom_report_builder', _t('nav.buttons.custom_report_builder'), self.show_custom_report_builder),
        ('hesa_export', 'HESA Data Export', self.show_hesa_export_gui),
        ('clearing_adjustment', 'Clearing & Adjustment', self.show_clearing_adjustment_gui),
    ]

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

    # 10 top-level groups (re-balanced). Each entry is
    # (group_label, sections, layout). Layout 'notebook' renders sections
    # as Notebook tabs in the popup (used for the wide Campus Life group);
    # 'sections' (default) renders them as stacked headers in one scroll.
    top_level_groups = [
        ("🎓 Academics", [
            (_t("nav.categories.academic"), academic_buttons_data),
            (_t("nav.categories.scheduling"), sched_buttons_data),
        ], 'sections'),
        ("👥 People", [
            (_t("nav.categories.student_management"), student_mgmt_buttons_data),
            (_t("nav.categories.human_resources"), human_resources_buttons_data),
        ], 'sections'),
        ("💰 Finance", [
            (_t("nav.categories.finance"), finance_buttons_data),
        ], 'sections'),
        ("🛟 Student Support", [
            (_t("nav.categories.services"), student_services_buttons_data),
            (_t("nav.categories.family_legal"), family_and_legal_buttons_data),
            (_t("nav.categories.communication"), communication_buttons_data),
        ], 'sections'),
        ("🏠 Campus Life", [
            (_t("nav.categories.health"), health_buttons_data),
            (_t("nav.categories.accommodation"), accommodation_buttons_data),
            (_t("nav.categories.campus"), campus_buttons_data),
            (_t("nav.categories.dining"), dining_buttons_data),
            (_t("nav.categories.shops"), shops_buttons_data),
            (_t("nav.categories.personal_services"), personal_buttons_data),
            (_t("nav.categories.transportation"), transport_buttons_data),
            (_t("nav.categories.entertainment"), entertainment_buttons_data),
            (_t("nav.categories.community"), community_services_buttons_data),
        ], 'notebook'),
        ("💼 Career", [
            (_t("nav.categories.career_alumni"), career_and_alumni_buttons_data),
        ], 'sections'),
        ("📊 Analytics & Reports", [
            (_t("nav.categories.analytics"), analytics_and_reporting_buttons_data),
            (_t("nav.categories.documents"), documents_and_export_buttons_data),
            (_t("nav.categories.tools"), ai_and_advanced_tools_buttons_data),
        ], 'sections'),
        ("🏛 Cross-System", [
            ("Cross-System", cross_system_buttons_data),
        ], 'sections'),
        ("⚙ Administration", [
            (_t("nav.categories.administration"), administration_buttons_data),
            (_t("nav.categories.security_safety"), security_and_safety_buttons_data),
        ], 'sections'),
        ("🔐 Account", [
            (_t("nav.categories.authentication"), authentication_buttons_data),
        ], 'sections'),
    ]

    # ---------- Search bar (filters across all visible actions) ----------
    search_var = tk.StringVar()
    search_entry = ttk.Entry(scrollable_frame, textvariable=search_var)
    search_entry.pack(fill=tk.X, padx=5, pady=(2, 4))

    _SEARCH_PLACEHOLDER = "🔍 Search features..."

    def _set_placeholder():
        search_entry.delete(0, tk.END)
        search_entry.insert(0, _SEARCH_PLACEHOLDER)
        try:
            search_entry.config(foreground='gray')
        except Exception:
            pass

    def _on_search_focus_in(_e):
        if search_var.get() == _SEARCH_PLACEHOLDER:
            search_entry.delete(0, tk.END)
            try:
                search_entry.config(foreground='black')
            except Exception:
                pass

    def _on_search_focus_out(_e):
        if not search_var.get().strip():
            _set_placeholder()

    search_entry.bind('<FocusIn>', _on_search_focus_in)
    search_entry.bind('<FocusOut>', _on_search_focus_out)
    _set_placeholder()

    search_results_frame = ttk.Frame(scrollable_frame)
    search_results_frame.pack(fill=tk.X, padx=5)

    # Flat index of every visible action across all groups.
    all_actions = []
    for _gl, _secs, _lay in top_level_groups:
        for _sl, _btns in _secs:
            for _nm, _txt, _cmd in _btns:
                if _nm in visible_buttons:
                    all_actions.append((_txt, _nm, _cmd))

    def _on_search_change(*_):
        for w in search_results_frame.winfo_children():
            w.destroy()
        q = search_var.get().strip().lower()
        if not q or q == _SEARCH_PLACEHOLDER.lower():
            return
        seen_names = set()
        matches = []
        for txt, name, cmd in all_actions:
            if name in seen_names:
                continue
            if q in txt.lower():
                matches.append((txt, name, cmd))
                seen_names.add(name)
        for txt, name, cmd in matches[:25]:
            ttk.Button(search_results_frame, text=txt,
                       command=cmd).pack(fill=tk.X, pady=1)

    search_var.trace_add('write', _on_search_change)

    # ---------- Pinned shortcuts ----------
    pinned_names = _load_pinned()
    if pinned_names:
        actions_by_name = {n: (t, c) for (t, n, c) in all_actions}
        pinned_visible = [(actions_by_name[n][0], n, actions_by_name[n][1])
                          for n in pinned_names if n in actions_by_name]
        if pinned_visible:
            pin_frame = ttk.LabelFrame(scrollable_frame, text="★ Pinned",
                                       padding=3)
            pin_frame.pack(fill=tk.X, padx=5, pady=(4, 6))

            def _make_unpin(n):
                def _do():
                    pins = _load_pinned()
                    if n in pins:
                        pins.remove(n)
                        _save_pinned(pins)
                    self.rebuild_navigation_panel()
                return _do

            for txt, name, cmd in pinned_visible:
                row = ttk.Frame(pin_frame)
                row.pack(fill=tk.X, pady=1)
                ttk.Button(row, text=txt, command=cmd).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)
                ttk.Button(row, text="✕", width=2,
                           command=_make_unpin(name)).pack(side=tk.RIGHT,
                                                            padx=(2, 0))

    # ---------- Group buttons (inline accordion) ----------
    # Each top-level category renders as a toggle button + an
    # initially-hidden sub-frame, both inside a per-category container
    # frame. Click toggles the sub-frame's pack state and flips the
    # ▶/▼ marker. Sub-frame contents are populated lazily on first
    # expand so we don't pay the layout cost for every category up
    # front (~15 categories × ~10 buttons = 150 widgets we don't need
    # until the user looks at them).
    for group_label, sections, _layout in top_level_groups:
        visible_sections = _filter_visible_sections(sections)
        if not visible_sections:
            continue

        cat_container = ttk.Frame(scrollable_frame)
        cat_container.pack(fill=tk.X, pady=2, padx=5)

        # State held on the container itself so the toggle closure
        # can mutate it without a nonlocal dance.
        cat_container._expanded = False
        cat_container._sub = None

        toggle_btn = ttk.Button(
            cat_container,
            text=group_label + "  ▶",
            style='Large.TButton',
        )
        toggle_btn.pack(fill=tk.X)

        def _make_toggle(container, btn, label, sects):
            def _toggle():
                if container._expanded:
                    if container._sub is not None:
                        container._sub.pack_forget()
                    btn.configure(text=label + "  ▶")
                    container._expanded = False
                else:
                    if container._sub is None:
                        sub = ttk.Frame(container)
                        _populate_category_subframe(sub, sects)
                        container._sub = sub
                    container._sub.pack(fill=tk.X, pady=(2, 4))
                    btn.configure(text=label + "  ▼")
                    container._expanded = True
                    # The newly-expanded section may extend past the
                    # canvas's current view; re-measure scroll region
                    # so the sidebar's scrollbar updates immediately.
                    try:
                        scrollable_frame.update_idletasks()
                        canvas.configure(scrollregion=canvas.bbox("all"))
                    except Exception:
                        pass
            return _toggle

        toggle_btn.configure(
            command=_make_toggle(cat_container, toggle_btn,
                                 group_label, visible_sections)
        )

    # The "New Features" sidebar bucket has been retired. Every
    # standalone Tk app it used to host has been redistributed into
    # the appropriate topical category \u2014 see the move comments
    # scattered through this file for the audit trail. Buttons are
    # still launched as subprocesses via the same
    # `UnifiedManagementGUI._launch_new_feature_module` plumbing.

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
        # New features (modules 21-30) - student-accessible
        'student_app', 'achievement_badges', 'study_recommendations',
        # New Features sidebar category (13 standalone Tk apps under
        # modules/domain/, launched as subprocesses by main_gui.py).
        'new_feature_complaints_portal',
        'new_feature_course_evaluation_system',
        'new_feature_lecturer_evaluation',
        'new_feature_module_evaluation_portal',
        'new_feature_disciplinary_portal',
        'new_feature_risk_management',
        'new_feature_first_aid_portal',
        'new_feature_health_safety_portal',
        'new_feature_intervention_support',
        'new_feature_safeguarding_system',
        'new_feature_lesson_planner',
        'new_feature_background_checker',
        'new_feature_university_research',
        # Cross-system ports added 2026-04
        'new_feature_employer_portal',
        'new_feature_intervention_outcomes',
        'new_feature_kpi_dashboard',
        'new_feature_mentoring_matching',
        'new_feature_room_booking',
        'new_feature_building_management',
        'new_feature_tutor_groups',
        # Academic Operations Hub — visible to all logged-in users
        'academic_hub',
        # Standalone Tk apps moved from /add 2026-04
        'new_feature_apprenticeship_system',
        'new_feature_placement_tracker',
        'new_feature_bakery_shop',
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
            'central_admin_portal', 'gdpr_compliance', 'equality_diversity',
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
        # Clearing the content area always destroys the workspace
        # notebook (it lives inside content_frame). Drop the
        # references so ``open_in_workspace`` doesn't try to add tabs
        # to a destroyed widget.
        self.workspace_notebook = None
        if hasattr(self, 'workspace_tabs') and self.workspace_tabs is not None:
            self.workspace_tabs.clear()
    else:
        # If content_frame doesn't exist yet, just return
        return


def open_in_workspace(self, title, builder, *, focus=True):
    """Render a feature inside the dashboard's notebook as a tab,
    instead of opening it as a Toplevel.

    Closes the "right content panel is decorative" gap from the
    8.117.16 layout review: any launcher that calls this method gets
    its UI hosted inside the main window's existing dashboard
    notebook (created by ``show_integrated_dashboard``) rather than
    spinning up a Toplevel that leaves the panel inert.

    Falls back gracefully when the workspace isn't available
    (e.g. user hasn't logged in yet, or the dashboard hasn't been
    rendered for this session). The caller's ``builder`` is invoked
    with the tab's frame regardless — but if there's no workspace
    notebook, the builder gets a freshly-created Toplevel's inner
    frame instead, preserving the old behaviour for the legacy path.

    Parameters
    ----------
    title : str
        Tab label. If a tab with this exact title already exists,
        the existing tab is raised rather than duplicated. Match is
        exact (case-sensitive) so a launcher that appends contextual
        info (e.g. ``"Library — S12345"``) will get a new tab while
        the same launcher with no context lands on the existing one.
    builder : callable(parent_frame) -> Any
        Populates the tab's frame. Return value is discarded; the
        builder is expected to ``pack``/``grid`` widgets onto the
        supplied frame.
    focus : bool
        If True (default), select the tab after construction so the
        user lands on what they just opened. Set to False for tabs
        that should open in the background.

    Returns
    -------
    Frame | None
        The frame the builder rendered into, or ``None`` if neither
        the workspace notebook nor a fallback Toplevel could be
        created.
    """
    import tkinter as tk
    from tkinter import ttk

    # Lazy-init the tracking dict — first launcher to opt in won't
    # have seen show_integrated_dashboard yet on a fresh session.
    if not hasattr(self, 'workspace_tabs') or self.workspace_tabs is None:
        self.workspace_tabs = {}

    nb = getattr(self, 'workspace_notebook', None)
    nb_alive = False
    if nb is not None:
        try:
            nb_alive = bool(nb.winfo_exists())
        except Exception:
            nb_alive = False

    if nb_alive:
        # Existing tab? Raise it.
        existing = self.workspace_tabs.get(title)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    if focus:
                        nb.select(existing)
                    return existing
            except Exception:
                # Stale entry — fall through and rebuild.
                self.workspace_tabs.pop(title, None)

        tab = ttk.Frame(nb)
        nb.add(tab, text=title)
        self.workspace_tabs[title] = tab

        # Add a small "✕" close affordance via right-click on the
        # tab's title cell. Cheap; no need for a custom tab
        # implementation.
        def _close_tab(_e=None, t=title, fr=tab):
            try:
                nb.forget(fr)
            except Exception:
                pass
            self.workspace_tabs.pop(t, None)
        try:
            # Tk doesn't expose per-tab right-click directly; bind
            # globally on the notebook and only act if the click
            # landed on this title's tab index.
            def _maybe_close(event, fr=tab, closer=_close_tab):
                try:
                    idx = nb.index(f"@{event.x},{event.y}")
                    if nb.tabs()[idx] == str(fr):
                        closer()
                except (tk.TclError, IndexError):
                    pass
            nb.bind("<Button-3>", _maybe_close, add="+")
        except Exception:
            pass

        try:
            builder(tab)
        except Exception:
            logger.exception("workspace tab builder failed for %s", title)
        if focus:
            try:
                nb.select(tab)
            except Exception:
                pass
        return tab

    # Fallback: no workspace notebook (pre-login, or content area
    # was cleared and not rebuilt). Spin up a Toplevel and hand the
    # builder its inner frame — preserves the pre-8.117.18 launcher
    # behaviour so callers that haven't migrated still work.
    try:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("1400x900")
        try:
            win.transient(self.root)
        except Exception:
            pass
        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True)
        try:
            builder(outer)
        except Exception:
            logger.exception("Toplevel-fallback builder failed for %s", title)
        return outer
    except Exception:
        logger.exception("open_in_workspace fallback Toplevel failed")
        return None
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
