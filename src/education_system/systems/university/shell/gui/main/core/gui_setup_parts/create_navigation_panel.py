"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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

    # ── Mousewheel scrolling, scoped to the navigation canvas ──
    # Pre-8.117.19 used ``bind_all('<MouseWheel>')`` on Enter +
    # ``unbind_all`` on Leave. Two failure modes that fix:
    #   (a) If the mouse left the canvas via a popup steal / focus
    #       grab without firing Leave (e.g. a Toplevel appears under
    #       the cursor), the global binding stayed pointed at this
    #       canvas. After the canvas was destroyed (logout rebuild,
    #       window close, etc.) the next wheel event raised
    #       ``TclError: invalid command name ".!frame.!labelframe.!canvas"``.
    #       Same bug class as the student-records academic-tab leak
    #       fixed in 8.117.15.
    #   (b) Even when working correctly, the global unbind *removed*
    #       wheel handling from any other widget in the app that had
    #       legitimately bound it. Detail-window canvases, tree
    #       scrollers, etc. would silently lose mousewheel until the
    #       user moved the cursor through the navigation canvas
    #       again.
    # Replaced with widget-local bind on the canvas + a <Map>-driven
    # recursive walk over the scrollable inner frame so newly-packed
    # children (e.g. category sub-frames opened by the 8.117.17
    # accordion) inherit the binding. Bindings die naturally with
    # the canvas; no global state. ``_on_mousewheel`` swallows
    # ``tk.TclError`` to handle the destroy race cleanly.
    def _on_mousewheel(event):
        try:
            delta = -1 if (getattr(event, 'num', None) == 5
                           or getattr(event, 'delta', 0) < 0) else 1
            canvas.yview_scroll(-delta, "units")
        except tk.TclError:
            pass
        return "break"

    def _bind_wheel_recursive(widget):
        # Idempotent: the marker attribute prevents add="+" from
        # stacking duplicate handlers on widgets we've already
        # touched — important because <Configure> fires repeatedly
        # as the accordion expands.
        try:
            if getattr(widget, '_nav_wheel_bound', False):
                pass  # already bound; still recurse for new children
            else:
                for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                    widget.bind(seq, _on_mousewheel, add="+")
                widget._nav_wheel_bound = True
            for child in widget.winfo_children():
                _bind_wheel_recursive(child)
        except tk.TclError:
            pass

    for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        canvas.bind(seq, _on_mousewheel, add="+")
    canvas._nav_wheel_bound = True
    # Add a second <Configure> handler on the scrollable inner frame
    # (the first one already updates the scroll region). This fires
    # whenever children are packed/repacked — including accordion
    # expand, pin/unpin rebuild, and the inline-search results frame
    # rebuilding on every keystroke. The recursive walk is idempotent
    # via the ``_nav_wheel_bound`` marker so repeat calls are cheap.
    scrollable_frame.bind(
        '<Configure>',
        lambda _e: _bind_wheel_recursive(scrollable_frame),
        add="+",
    )
    # Initial pass — at panel-build time the children list is empty
    # but the binding will be picked up on the first <Configure>
    # after content is packed. Bind now anyway so the canvas itself
    # responds even before any children exist.
    _bind_wheel_recursive(scrollable_frame)

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
        ('new_feature_identity_management', 'Identity Management', self.show_new_feature_identity_management),
    ])

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
        ('absence_tracker', 'Absence Tracker', self.open_absence_tracker_gui),
        # "Graduation System" removed: it opened the Degree Audit GUI, which
        # is already a Course Management tab, and four of its five tabs are
        # advising rather than graduation. The graduation half now lives in
        # the Graduation entry below.
        ('graduation_ceremony', '🎓 Graduation', self.show_graduation_ceremony_gui),
        ('new_feature_course_evaluation_system', 'Course Evaluation', self.show_new_feature_course_evaluation_system),
        ('new_feature_module_evaluation_portal', 'Module Evaluation', self.show_new_feature_module_evaluation_portal),
        ('new_feature_lecturer_evaluation', 'Lecturer Evaluation', self.show_new_feature_lecturer_evaluation),
        ('new_feature_university_research', 'Research Portal', self.show_new_feature_university_research),
        ('study_recommendations', 'Study Recommendations', self.show_study_recommendations_gui),
        ('new_feature_programme_governance', 'Programme Governance', self.show_new_feature_programme_governance),
        ('new_feature_pgr_admin', 'PGR Administration', self.show_new_feature_pgr_admin),
        ('new_feature_assessment_boards', 'Assessment Boards', self.show_new_feature_assessment_boards),
    ]
    if VIRTUAL_CLASSROOM_AVAILABLE:
        academic_buttons_data.append(('virtual_classroom', _t("nav.buttons.virtual_classroom"), self.show_virtual_classroom_gui))

    # ---------- Scheduling & Attendance ----------
    sched_buttons_data = [
        ('academic_calendar', _t("nav.buttons.academic_calendar"), self.show_academic_calendar),
        ('scheduling', _t("nav.buttons.scheduling"), self.show_module_scheduling),
        # One timetable button. This was two — 'Timetable Manager' and
        # 'My Timetable' — which after the timetable merge opened the same
        # window. The surviving id is 'my_timetable' because it is the one
        # every role can already see: the student block grants it directly and
        # the instructor block (which covers admin and staff) grants it too,
        # whereas 'timetable_manager' reached only admin/staff/instructor.
        ('my_timetable', _t("nav.buttons.timetable", default="Timetable"),
         self.show_timetable_management),
        ('attendance', _t("nav.buttons.attendance"), self.open_attendance_gui),
        # One exam button. "Exam Scheduler" was removed because Exam
        # Management already contains it: ExamPortalGUI's Scheduling tab
        # embeds the whole ExamSchedulerApp, so the two buttons opened the
        # same nine scheduler tabs, one of them nested a level deeper.
        ('exam_portal', "Exam Management", self.show_exam_portal),
        ('new_feature_timetabling', 'Timetabling', self.show_new_feature_timetabling),
    ]

    # ---------- Finance ----------
    finance_buttons_data = [
        ('finance_management', _t("nav.buttons.finance_management"), self.show_finance_management),
        ('my_finance', _t("nav.buttons.my_finance"), self.show_student_finance_account),
        ('bank_app', _t("nav.buttons.bank_app", default="Student Bank"), self.show_bank_app_gui),
        ('finance_reporting', 'Finance Reporting', self.show_finance_reporting_dashboard),
        ('club_payment', 'Club Payments', self.show_club_payment_management),
        ('new_feature_bursary', 'Bursaries', self.show_new_feature_bursary),
    ]

    # ---------- Health & Wellness ----------
    health_buttons_data = [
        ('health_portal', _t("nav.buttons.health_portal"), self.open_health_portal_gui),
        ('new_feature_first_aid_portal', 'First Aid Portal', self.show_new_feature_first_aid_portal),
        ('medical_accommodations', 'Medical Accommodations', self.show_medical_accommodations),
        ('dentist', _t("nav.buttons.dentist", default="Dental Service"), self.show_dentist_gui),
    ]

    # ---------- Accommodation ----------
    accommodation_buttons_data = [
        ('housing_accommodations', _t("nav.buttons.housing_accommodation"), self.show_housing_accommodations),
    ]

    # ---------- Campus Life ----------
    campus_buttons_data = [
        ('student_union_portal', _t("nav.buttons.student_union"), self.open_student_union_portal_gui),
        ('campus_events', _t("nav.buttons.campus_events"), self.show_campus_events_gui),
        ('mail_post', 'Mail / Post', self.show_mail_post_gui),
        ('new_feature_room_booking', 'Room Booking', self.show_new_feature_room_booking),
        ('events_discovery', _t("nav.buttons.events_discovery"), self.show_events_discovery_gui),
        # Single consolidated entry — opens the unified app with tabs for
        # Buildings / Rooms / Bookings / Utilities / Cleaning / Maintenance /
        # Work Orders / Occupancy / Access Cards / Inspections / Assets /
        # Reports. Replaces the previously-separate Room Booking +
        # Building Management buttons.
        ('facilities_management', _t("nav.buttons.facilities"), self.show_facilities_management_gui),
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

    # ---------- Transportation (university) ----------
    # taxi_booking / train_station / carrental are non-university town
    # services and now live in the 'Other' group (other_transport_buttons_data).
    transport_buttons_data = [
        ('parking_management', _t("nav.buttons.parking"), self.show_parking_management),
        ('trip_management', _t("nav.buttons.trip_management"), self.show_trip_management_gui),
    ]

    # ---------- Student Services ----------
    student_services_buttons_data = [
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
        ('visa_compliance', 'Visa Sponsorship (Tier-4)', self.show_visa_compliance_gui),
        ('enrolment_letters', 'Status Letters', self.show_enrolment_letters_gui),
        ('student_app', 'Student App', self.show_student_app_gui),
        ('mental_health', 'Mental Health & Wellness', self.show_mental_health_gui),
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
        ('new_feature_fitness_to_practise', 'Fitness to Practise', self.show_new_feature_fitness_to_practise),
        ('new_feature_risk_management', 'Risk Management', self.show_new_feature_risk_management),
        ('information_rights', 'SAR / FOI Requests', self.show_information_rights_gui),
        ('new_feature_case_management', 'Case Management', self.show_new_feature_case_management),
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
        ('new_feature_institutional_analytics', 'Institutional Analytics', self.show_new_feature_institutional_analytics),
        ('business_intelligence', 'Business Intelligence', self.show_business_intelligence_gui),
        ('predictive_analytics', 'Predictive Analytics', self.show_predictive_analytics_gui),
        ('student_analytics', 'Student Analytics', self.show_student_analytics_gui),
        ('student_outcomes', 'Student Outcomes', self.show_student_outcomes_gui),
        ('qa_dashboard', 'External QA (OfS / TEF / REF)', self.show_qa_dashboard_gui),
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
        ('ai_detector', 'AI Detector', self.open_ai_detector_window),
    ]

    # ---------- Security & Safety ----------
    # police_station is a non-university town service and now lives in the
    # 'Other' group (other_leisure_civic_buttons_data).
    security_and_safety_buttons_data = [
        ('security_desk', _t('nav.buttons.security_desk'), self.show_security_desk_gui),
    ]

    # ---------- Community Services ----------
    community_services_buttons_data = [
        ('church_management', _t('nav.buttons.church_management'), self.show_church_management_gui),
    ]

    # ---------- 'Other' — non-university town / lifestyle services ----------
    # Split out of the mixed Transport / Health / Security categories so the
    # genuine university functions (parking, trips, health portal, security
    # desk) stay in the main groups while their town-service siblings move
    # into the 'Other' window below.
    other_transport_buttons_data = [
        ('taxi_booking', _t("nav.buttons.taxi_booking"), self.show_taxi_booking_gui),
        ('train_station', _t("nav.buttons.train_station"), self.show_train_station_gui),
        ('carrental', _t("nav.buttons.carrental"), self.show_carrental_gui),
    ]
    other_leisure_civic_buttons_data = [
        ('gym', "Gym", self.show_gym_gui),
        ('police_station', _t('nav.buttons.police_station'), self.show_police_station_gui),
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
        ('ucas_management', 'UCAS Management', self.show_ucas_management_gui),
        ('university_progression', 'University Progression', self.show_university_progression_gui),
        ('usage_adoption_reports', _t('nav.buttons.usage_reports'), self.show_usage_adoption_reports),
        ('custom_report_builder', _t('nav.buttons.custom_report_builder'), self.show_custom_report_builder),
        ('hesa_export', 'HESA Data Export', self.show_hesa_export_gui),
        ('clearing_adjustment', 'Clearing & Adjustment', self.show_clearing_adjustment_gui),
        ('prior_learning', 'Prior Learning (APL/RPL)', self.show_prior_learning_gui),
        ('mitigating_circumstances', 'Mitigating Circumstances', self.show_mitigating_circumstances_gui),
        ('collaborative_provision', 'Partner Provision', self.show_collaborative_provision_gui),
        ('student_mobility', 'Study Abroad & Exchange', self.show_student_mobility_gui),
        ('curriculum_specification', 'Curriculum Spec.', self.show_curriculum_specification_gui),
        ('new_feature_sso_providers', 'SSO Providers', self.show_new_feature_sso_providers),
    ]

    # ---------- Cross-System ----------
    cross_system_buttons_data = [
        ('analytics_dashboard', 'Analytics Dashboard', self.show_analytics_dashboard_gui),
        ('student_journey', 'Student Journey', self.show_student_journey_gui),
        ('apprenticeship_progression', 'Apprenticeship Progression',
         self.show_apprenticeship_progression_gui),
        ('reporting_warehouse', 'Reporting Warehouse', self.show_reporting_warehouse_gui),
        ('cross_system_calendar', 'Cross-System Calendar', self.show_cross_system_calendar_gui),
        ('central_admin_portal', 'Central Admin Portal', self.show_central_admin_gui),
        ('gdpr_compliance', 'GDPR Compliance', self.show_gdpr_compliance_gui),
        ('shared_documents', 'Shared Documents', self.show_shared_documents_gui),
        ('student_self_service', 'Student Self-Service', self.show_student_self_service_gui),
        ('certificates', 'Certificates', self.show_certificates_gui),
    ]

    # ── Split the three oversized sections into scannable sub-sections ──
    # The source lists above remain the single source of truth (and keep the
    # conditional virtual_classroom append working); we partition them by
    # button-name into labelled sub-sections for display. Any name not listed
    # falls through to the trailing catch-all group so nothing is ever dropped.
    def _partition(buttons, *named_groups):
        by_name = {b[0]: b for b in buttons}
        listed = {n for names in named_groups for n in names}
        result = [[by_name[n] for n in names if n in by_name]
                  for names in named_groups]
        leftovers = [b for b in buttons if b[0] not in listed]
        if leftovers:
            result[-1].extend(leftovers)
        return result

    academic_courses, academic_assessment, academic_study = _partition(
        academic_buttons_data,
        ['course_management', 'module_management', 'assignments', 'library',
         'office_hours', 'virtual_classroom', 'new_feature_programme_governance'],
        ['grade_tracking_gui', 'student_registration',
         'new_feature_course_evaluation_system',
         'new_feature_module_evaluation_portal',
         'new_feature_lecturer_evaluation', 'new_feature_assessment_boards'],
        ['study_hub', 'new_feature_university_research', 'new_feature_pgr_admin',
         'graduation_ceremony'],
    )

    support_wellbeing, inclusion_records = _partition(
        student_services_buttons_data,
        ['student_support', 'helpdesk',
         'early_warning_system', 'new_feature_intervention_support',
         'new_feature_intervention_outcomes', 'new_feature_mentoring_matching'],
        ['new_feature_safeguarding_system', 'accessibility',
         'equality_diversity', 'portfolio', 'advising_portal',
         'visa_compliance', 'enrolment_letters'],
    )

    admin_system, admin_admissions, admin_reporting = _partition(
        administration_buttons_data,
        ['user_management', 'system_admin_gui', 'security_dashboard',
         'new_feature_health_safety_portal', 'new_feature_background_checker',
         'integration_marketplace', 'new_feature_sso_providers'],
        ['admissions_crm', 'university_progression', 'ucas_management',
         'clearing_adjustment', 'prior_learning',
         'mitigating_circumstances', 'curriculum_specification',
         'collaborative_provision', 'student_mobility'],
        ['usage_adoption_reports', 'custom_report_builder', 'hesa_export'],
    )

    # 9 top-level groups (re-balanced for even size; the 2-button Finance group
    # is folded into People, and the three giant sections are split above).
    # Each entry is (group_label, sections, layout). Layout 'notebook' renders
    # sections as Notebook tabs in the popup (used for the wide Campus Life
    # group); 'sections' (default) renders them as stacked headers in one scroll.
    top_level_groups = [
        ("🎓 Academics", [
            (_t("nav.categories.courses_teaching", default="Courses & Teaching"), academic_courses),
            (_t("nav.categories.assessment_evaluation", default="Assessment & Evaluation"), academic_assessment),
            (_t("nav.categories.study_research", default="Study, Research & Graduation"), academic_study),
            (_t("nav.categories.scheduling"), sched_buttons_data),
        ], 'sections'),
        ("👥 People & Finance", [
            (_t("nav.categories.student_management"), student_mgmt_buttons_data),
            (_t("nav.categories.human_resources"), human_resources_buttons_data),
            (_t("nav.categories.finance"), finance_buttons_data),
        ], 'sections'),
        ("🛟 Student Support", [
            (_t("nav.categories.support_wellbeing", default="Support & Wellbeing"), support_wellbeing),
            (_t("nav.categories.inclusion_records", default="Inclusion & Records"), inclusion_records),
            (_t("nav.categories.family_legal"), family_and_legal_buttons_data),
            (_t("nav.categories.communication"), communication_buttons_data),
        ], 'sections'),
        ("🏠 Campus Life", [
            (_t("nav.categories.health"), health_buttons_data),
            (_t("nav.categories.accommodation"), accommodation_buttons_data),
            (_t("nav.categories.campus"), campus_buttons_data),
            ("Parking & Trips", transport_buttons_data),
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
            (_t("nav.categories.admin_system", default="System & Users"), admin_system),
            (_t("nav.categories.admin_admissions", default="Admissions & Records"), admin_admissions),
            (_t("nav.categories.admin_reporting", default="Statutory Reporting"), admin_reporting),
            (_t("nav.categories.security_safety"), security_and_safety_buttons_data),
        ], 'sections'),
        ("🔐 Account", [
            (_t("nav.categories.authentication"), authentication_buttons_data),
        ], 'sections'),
        # 'Other' — non-university town / lifestyle services, kept out of the
        # main university navigation. Pinned to the very bottom of the sidebar,
        # and given the 'window' layout so its toggle button opens a separate
        # pop-out window (see the rendering loop) rather than expanding inline
        # like every other group.
        ("🛒 Other", [
            (_t("nav.categories.dining"), dining_buttons_data),
            (_t("nav.categories.shops"), shops_buttons_data),
            (_t("nav.categories.personal_services"), personal_buttons_data),
            ("Transport", other_transport_buttons_data),
            (_t("nav.categories.entertainment"), entertainment_buttons_data),
            (_t("nav.categories.community"), community_services_buttons_data),
            ("Leisure & Civic", other_leisure_civic_buttons_data),
        ], 'window'),
    ]

    # ---------- Search bar (filters across all visible actions) ----------
    # Stash on self so a global Ctrl+K binding can focus this entry
    # from anywhere in the app (closes "search hidden in sidebar" gap
    # from the 8.117.16 layout review).
    search_var = tk.StringVar()
    search_entry = ttk.Entry(scrollable_frame, textvariable=search_var)
    search_entry.pack(fill=tk.X, padx=5, pady=(2, 4))
    self.nav_search_entry = search_entry
    try:
        # Ctrl+K (and Ctrl+Shift+K) → focus the search box. Bind on
        # the root so the shortcut works no matter which child has
        # keyboard focus. ``add="+"`` so we don't clobber any other
        # binding the app already attached.
        self.root.bind('<Control-k>',
                       lambda _e: _focus_nav_search(self), add="+")
        self.root.bind('<Control-K>',
                       lambda _e: _focus_nav_search(self), add="+")
    except Exception:
        logger.debug("Ctrl+K binding failed", exc_info=True)

    _SEARCH_PLACEHOLDER = "🔍 Search features..."

    def _set_placeholder():
        search_entry.delete(0, tk.END)
        search_entry.insert(0, _SEARCH_PLACEHOLDER)
        try:
            search_entry.config(foreground='gray')
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _on_search_focus_in(_e):
        if search_var.get() == _SEARCH_PLACEHOLDER:
            search_entry.delete(0, tk.END)
            try:
                search_entry.config(foreground='black')
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    def _on_search_focus_out(_e):
        if not search_var.get().strip():
            _set_placeholder()

    search_entry.bind('<FocusIn>', _on_search_focus_in)
    search_entry.bind('<FocusOut>', _on_search_focus_out)
    _set_placeholder()

    # Results frame is created unpacked — only takes a slot in the layout
    # while there are matches to show. Without this the empty frame keeps
    # its padx/padding slot after the user clears the search box, leaving
    # a visible gap where the result buttons were.
    search_results_frame = ttk.Frame(scrollable_frame)

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
            try:
                search_results_frame.pack_forget()
            except tk.TclError:
                pass
            return
        seen_names = set()
        matches = []
        for txt, name, cmd in all_actions:
            if name in seen_names:
                continue
            if q in txt.lower():
                matches.append((txt, name, cmd))
                seen_names.add(name)
        if not matches:
            try:
                search_results_frame.pack_forget()
            except tk.TclError:
                pass
            return
        # Re-attach directly under the search entry. `after=` keeps it in
        # the right slot if it was previously forgotten.
        try:
            search_results_frame.pack(fill=tk.X, padx=5, pady=(0, 4),
                                      after=search_entry)
        except tk.TclError:
            search_results_frame.pack(fill=tk.X, padx=5, pady=(0, 4))
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
            pin_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.shell.main.core.gui_setup_parts.create_navigation_panel.labels.pinned', default="★ Pinned"),
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
    def _open_group_window(label, sects):
        """Open a group's sections in a separate pop-out window instead of
        expanding them inline. Used by groups whose layout is 'window'
        (currently just 'Other'). Re-opening focuses the existing window."""
        existing = getattr(self, '_group_windows', {}).get(label)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_set()
                    return
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        # Multi-column layout: pick a column count from the number of
        # sections (up to 3), then greedily pack each section into the
        # currently-shortest column so the columns stay balanced by height.
        ncols = max(1, min(3, len(sects)))
        col_w = 230
        win = self.create_themed_toplevel(
            title=label.strip(), geometry=f"{col_w * ncols + 40}x560")
        if not hasattr(self, '_group_windows'):
            self._group_windows = {}
        self._group_windows[label] = win

        # Scrollable body so tall content stays reachable if a column
        # overflows the window height.
        outer = ttk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)
        wcanvas = tk.Canvas(outer, highlightthickness=0)
        wscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=wcanvas.yview)
        body = ttk.Frame(wcanvas)
        body.bind(
            "<Configure>",
            lambda _e: wcanvas.configure(scrollregion=wcanvas.bbox("all")),
        )
        wcanvas.create_window((0, 0), window=body, anchor="nw",
                              width=col_w * ncols)
        wcanvas.configure(yscrollcommand=wscroll.set)
        wcanvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wscroll.pack(side=tk.RIGHT, fill=tk.Y)

        # One frame per column, laid side by side.
        col_frames = []
        col_weights = []  # running height estimate (rows) per column
        for c in range(ncols):
            cf = ttk.Frame(body)
            cf.grid(row=0, column=c, sticky="nw", padx=4)
            col_frames.append(cf)
            col_weights.append(0)

        # Distribute sections into the shortest column (balanced by the
        # section's button count + 1 for its header).
        for section_label, btns in sects:
            target = col_weights.index(min(col_weights))
            cf = col_frames[target]
            col_weights[target] += len(btns) + 1
            ttk.Label(
                cf, text=section_label, font=('Arial', 9, 'bold'),
                foreground='#555555', anchor='w',
            ).pack(fill=tk.X, padx=(6, 4), pady=(8, 2))
            for name, text, cmd in btns:
                b = ttk.Button(cf, text=text, command=cmd)
                b.pack(fill=tk.X, padx=(6, 4), pady=1)
                _bind_pin_menu_inline(b, name)

    for group_label, sections, _layout in top_level_groups:
        visible_sections = _filter_visible_sections(sections)
        if not visible_sections:
            continue

        # 'window' layout: a single button that pops the group out into its
        # own window rather than the inline expand/collapse used by the rest.
        if _layout == 'window':
            cat_container = ttk.Frame(scrollable_frame)
            cat_container.pack(fill=tk.X, pady=2, padx=5)
            open_btn = ttk.Button(
                cat_container,
                text=group_label + "  ⧉",
                style='Large.TButton',
                command=lambda lbl=group_label, s=visible_sections:
                    _open_group_window(lbl, s),
            )
            open_btn.pack(fill=tk.X)
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
                        logger.debug("Suppressed exception", exc_info=True)
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
