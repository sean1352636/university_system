# Auto-generated main entry
import tkinter as tk
from tkinter import ttk
import logging
from datetime import datetime

# Import authentication
from education_system.university_system.infrastructure.auth import UserAuth, set_auth_instance
from education_system.university_system.infrastructure.shared_context import set_auth as set_shared_auth, get_auth
from education_system.university_system.modules.shared.cli.utils import safe_auth_check
HAS_AUTH = True

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Patch messagebox so every showerror/showwarning is also logged to file + console
from education_system.university_system.infrastructure.logging.log_config import patch_messagebox_logging
patch_messagebox_logging()

logger = logging.getLogger(__name__)

# Initialize global auth variable
auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
    # Set in shared_context as well
    try:
        set_shared_auth(auth_instance)
    except Exception as e:
        logger.warning(f"Failed to set auth in shared_context: {e}")


def init_gui(session_user=None):
    """
    Centralized GUI initialization function.

    Args:
        session_user: Pre-authenticated user dict from the universal login.
                     Must be provided – login is handled by the universal login
                     in education_system/shared/gui/login_gui.py.

    Returns:
        UnifiedManagementGUI instance
    """
    global auth

    # Initialize auth manager if needed
    if auth is None:
        if UserAuth is None:
            raise ImportError(
                "UserAuth is not available. Please ensure the authentication module is properly installed.\n"
                "Path: university_system/infrastructure/auth/user_authentication.py"
            )

        # Get centralized auth or create new one
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
            set_auth(auth)
        safe_auth_check(auth)

    # If session_user is provided, set it as the current user
    if session_user is not None:
        auth.current_user = session_user
        if hasattr(auth, 'last_activity'):
            from datetime import datetime
            auth.last_activity = datetime.now()

    # Route each role to its dedicated portal; admin gets the full
    # UnifiedManagementGUI.
    role = (session_user or {}).get('role', '') if session_user else ''
    if role == 'student':
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI
        app = StudentPortalGUI(auth)
    elif role == 'staff':
        from education_system.university_system.modules.shared.gui.main.staff_portal import StaffPortalGUI
        app = StaffPortalGUI(auth)
    elif role in ('instructor', 'teacher'):
        from education_system.university_system.modules.shared.gui.main.instructor_portal import InstructorPortalGUI
        app = InstructorPortalGUI(auth)
    elif role == 'parent':
        from education_system.university_system.modules.shared.gui.main.parent_portal_wrapper import ParentPortalWrapper
        app = ParentPortalWrapper(auth)
    else:
        app = UnifiedManagementGUI(auth)
    return app


class UnifiedManagementGUI:
    def __init__(self, auth_manager):
        try:
            self.auth = auth_manager

            # Initialize content_frame to None first
            self.content_frame = None

            # Initialize modular GUI managers
            self.finance_gui = None
            self.student_union_gui = None
            self.health_portal_gui = None
            self.grade_tracking_gui = None
            self.restaurant_gui = None
            self.cafe_gui = None
            self.email_manager_gui = None

            # Initialize student management components
            self.student_tree = None

            # Initialize timer IDs for cleanup
            self._session_timer_id = None

            # Initialize Tkinter
            self.root = tk.Tk()
            self.root.title(_t("gui.window_title"))
            self.root.geometry("1200x800")
            self.root.minsize(1000, 700)

            # Configure style and theme
            self.style = ttk.Style()
            self.style.theme_use('clam')

            # Variables
            self.current_user_var = tk.StringVar()
            self.status_var = tk.StringVar(value=_t("gui.not_logged_in_status"))

            # Initialize GUI
            self.setup_gui()

            # Register window close handler to cancel timers
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

            # Initialize modular GUI managers after root is set up
            self.init_gui_managers()

            # Update status
            self.update_status()

            # Start periodic updates
            self.check_session_timer()

            # Always show main interface (login handled by universal login)
            self.show_main_interface()

        except Exception as e:
            print(f"Error initializing GUI: {e}")
            self.create_fallback_interface()

    def _on_closing(self):
        """Handle window close - cancel timers before destroying"""
        try:
            self._cancel_timers()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        """Start the Tkinter main loop."""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error running main loop: {e}")

from education_system.university_system.modules.shared.gui.main.core.gui_setup import (
    create_fallback_interface,
    init_gui_managers,
    create_themed_toplevel,
    setup_gui,
    create_header,
    create_navigation_panel,
    rebuild_navigation_panel,
    create_content_area,
    get_visible_buttons_for_role,
    clear_content,
    show_welcome,
    show_main_interface,
    _deferred_navigation_rebuild,
    update_status,
    restart_gui,
    _cancel_timers
)
from education_system.university_system.modules.shared.gui.main.auth_gui import (
    logout_user,
    toggle_login_logout,
    update_login_logout_button,
    show_change_password,
    check_session_timer,
    switch_to_cli,
    switch_system,
    shutdown_system,
    show_mfa_setup,
    _open_mfa_wizard,
    _reenable_mfa_with_confirmation,
    toggle_login_verification,
)
from education_system.university_system.modules.shared.gui.main.students.student_records_gui import (
    show_student_records,
    create_student_treeview,
    view_students,
    view_students_in_window,
    on_student_double_click,
    on_student_double_click_window,
    show_student_details,
    search_students_dialog,
    _load_academic_data
)
from education_system.university_system.modules.shared.gui.main.students.student_crud_gui import (
    create_student_dialog,
    update_student_dialog,
    delete_student_dialog,
    select_student_for_deletion,
    manage_student_grades,
    view_student_attendance,
    view_student_timetable,
    reassign_modules
)
from education_system.university_system.modules.shared.gui.main.students.student_export_gui import (
    export_student_data,
    export_individual_student_data,
    export_data_dialog,
    _export_to_csv,
    _export_to_excel,
    _export_to_pdf,
    _export_to_txt,
    _export_comprehensive_csv,
    _export_comprehensive_excel,
    _export_comprehensive_pdf,
    _export_comprehensive_txt
)
from education_system.university_system.modules.shared.gui.main.staff.staff_crud_gui import (
    create_staff_dialog,
    update_staff_dialog,
    view_staff,
    delete_staff_dialog,
    search_staff_dialog
)
from education_system.university_system.modules.shared.gui.main.admin.user_management_gui import (
    show_user_management,
    refresh_user_list,
    show_create_user,
    show_user_details,
    show_edit_user,
    reset_user_password,
    view_all_users,
    add_new_user,
    manage_permissions
)
from education_system.university_system.modules.shared.gui.main.admin.system_admin_gui import (
    show_system_admin,
    show_system_administration_gui,
    create_database_admin_tab,
    create_user_admin_tab,
    create_monitoring_tab,
    create_config_tab,
    create_operations_tab,
    view_active_sessions,
    view_system_logs,
    view_error_logs
)
from education_system.university_system.modules.shared.gui.main.admin.database_admin_gui import (
    show_backup,
    show_data_backup_gui,
    show_batch_operations_gui,
    fix_duplicates,
    optimize_database,
    run_integrity_check,
    show_db_statistics,
    show_db_performance,
    show_active_connections,
    wipe_database
)
from education_system.university_system.modules.shared.gui.main.admin.config_gui import (
    edit_system_settings,
    configure_email,
    configure_backup,
    configure_security,
    show_security_dashboard,
    show_audit_log_viewer,
    show_activity_logger,
    show_activity_log
)
from education_system.university_system.modules.shared.gui.main.admin.admin_tools_gui import (
    show_system_monitoring_dashboard,
    show_configuration_editor,
    show_query_analyser,
    show_capacity_planning,
    show_usage_adoption_reports,
    show_custom_report_builder,
    show_api_documentation,
    show_notification_template_manager,
    show_data_retention_manager,
    show_system_changelog,
    show_department_isolation,
    show_integration_status_dashboard,
    show_license_management,
    show_disaster_recovery_plan,
)
from education_system.university_system.modules.shared.gui.main.features.academic_launchers_gui import (
    show_library_management,
    show_academic_calendar,
    show_course_management,
    show_module_management,
    show_module_scheduling,
    show_grades,
    show_grade_tracking_gui,
    show_assignments,
    show_plagiarism_checker,
    show_ai_detector,
    open_ai_detector_window,
    open_attendance_gui,
    open_absence_tracker_gui,
    show_virtual_classroom_gui,
    show_office_hours_gui,
    show_student_outcomes_gui,
    show_student_timetable_gui,
    show_student_registration_gui,
    show_student_dashboard_gui,
    show_lms_gui,
)
from education_system.university_system.modules.shared.gui.main.features.student_affairs_gui import (
    show_student_union_portal,
    open_student_union_portal_gui,
    open_parent_portal_gui,
    open_alumni_portal_gui,
    open_student_support_portal_gui,
    open_health_portal_gui,
    open_helpdesk_gui,
    show_mental_health_gui,
    show_early_warning_gui,
    show_career_services_gui,
    open_internship_portal_gui,
    show_trip_management_gui,
    open_trip_management_gui,
    show_legal_services_gui,
    show_betting_shop_gui,
    show_mail_post_gui,
    show_staff_hr_gui
)
from education_system.university_system.modules.shared.gui.main.features.finance_gui import (
    show_finance_management,
    show_finance_reporting_dashboard,
    show_student_finance_account,
    show_financial_aid,
    show_club_payment_management,
    _create_payment_overview_tab_finance,
    _create_record_payment_tab_finance,
    _create_payment_history_tab_finance
)
from education_system.university_system.modules.shared.gui.main.features.commerce_facilities_gui import (
    show_university_shop,
    show_charity_shop,
    show_restaurant_management,
    show_cafe_system,
    show_takeaway_system,
    show_grocery_shop,
    show_bar,
    show_parking_management,
    show_housing_accommodations,
    show_medical_accommodations,
    show_campus_events_gui,
    show_facilities_management_gui,
    show_transportation_parking_gui,
    show_gym_gui,
    show_dentist_gui,
    show_butcher_gui,
    show_barber_gui,
    show_nailbar_gui,
    show_carrental_gui,
    show_equipment_gui,
    show_phoneshop_gui,
    show_musicshop_gui,
    show_taxi_booking_gui,
    show_train_station_gui,
    show_cinema_gui
)
# Functions merged from extras_gui.py into their domain files
from education_system.university_system.modules.shared.gui.main.features.academic_launchers_gui import (
    show_document_manager,
    show_enhanced_reporting_dashboard,
    show_pdf_export_gui,
    show_advanced_search_gui,
    refresh_advanced_search,
    show_integration_marketplace_gui,
    show_exam_scheduler_gui,
    show_exam_portal,
    show_student_analytics_gui,
    show_predictive_analytics_gui,
    show_business_intelligence_gui,
    show_hesa_export_gui,
    show_clearing_adjustment_gui,
)
from education_system.university_system.modules.shared.gui.main.features.student_affairs_gui import (
    show_communication_dashboard_gui,
    show_email_sms_gui,
    show_admissions_crm_gui,
    show_police_station_gui,
    show_security_desk_gui,
    show_church_management_gui,
)
from education_system.university_system.modules.shared.gui.main.features.student_success_gui import (
    show_ai_features_gui,
    show_mobile_app_pwa_gui,
    show_accessibility_tools_gui,
    show_blockchain_credentials_gui,
    show_extras_launcher,
    _show_feature_gui,
    show_todo_app_gui,
    show_student_app_gui,
    show_achievement_badge_gui,
    show_study_recommendations_gui,
)
from education_system.university_system.modules.shared.gui.main.features.finance_gui import (
    show_bank_app_gui,
)
from education_system.university_system.modules.shared.gui.main.features.student_success_gui import (
    show_academic_progress_gui,
    show_ai_study_gui,
    show_budget_tracker_gui,
    show_student_jobs_gui,
    show_scholarship_finder_gui,
    show_study_matching_gui,
    show_course_planning_gui,
    show_roommate_finder_gui,
    show_campus_navigation_gui,
    show_lost_found_gui,
    show_marketplace_gui,
    show_wellness_hub_gui,
    show_accessibility_portal_gui,
    show_events_discovery_gui,
    show_social_matching_gui,
    show_portfolio_system_gui,
    show_notifications_hub_gui,
    show_feedback_system_gui,
    show_advising_portal_gui,
    show_student_id_gui,
    show_study_room_booking_gui,
    show_printing_services_gui,
)
from education_system.university_system.modules.shared.gui.main.email.email_helpers_gui import (
    compose_email,
    send_email_to_student,
    show_email_manager,
    _send_welcome_email_to_student,
    _send_email_via_gui,
    _show_welcome_email_fallback,
    _send_student_update_email,
    _show_update_email_fallback
)
from education_system.university_system.modules.shared.gui.main.dashboard.dashboard_gui import (
    show_integrated_dashboard,
    create_overview_tab,
    create_stats_tab,
    create_activity_tab,
    create_health_tab,
    show_analytics,
    show_chatbot,
    log_activity,
    launch_analytics_gui_standalone
)

UnifiedManagementGUI.create_fallback_interface = create_fallback_interface
UnifiedManagementGUI.init_gui_managers = init_gui_managers
UnifiedManagementGUI.create_themed_toplevel = create_themed_toplevel
UnifiedManagementGUI.setup_gui = setup_gui
UnifiedManagementGUI.create_header = create_header
UnifiedManagementGUI.create_navigation_panel = create_navigation_panel
UnifiedManagementGUI.rebuild_navigation_panel = rebuild_navigation_panel
UnifiedManagementGUI.create_content_area = create_content_area
UnifiedManagementGUI.get_visible_buttons_for_role = get_visible_buttons_for_role
UnifiedManagementGUI.clear_content = clear_content
UnifiedManagementGUI.show_welcome = show_welcome
UnifiedManagementGUI.show_main_interface = show_main_interface
UnifiedManagementGUI._deferred_navigation_rebuild = _deferred_navigation_rebuild
UnifiedManagementGUI.update_status = update_status
UnifiedManagementGUI.restart_gui = restart_gui
UnifiedManagementGUI._cancel_timers = _cancel_timers
UnifiedManagementGUI.logout_user = logout_user
UnifiedManagementGUI.toggle_login_logout = toggle_login_logout
UnifiedManagementGUI.update_login_logout_button = update_login_logout_button
UnifiedManagementGUI.show_change_password = show_change_password
UnifiedManagementGUI.show_mfa_setup = show_mfa_setup
UnifiedManagementGUI._open_mfa_wizard = _open_mfa_wizard
UnifiedManagementGUI._reenable_mfa_with_confirmation = _reenable_mfa_with_confirmation


def show_security_questions(self):
    """Show the Security Questions management frame."""
    try:
        from education_system.shared.gui.security_questions_gui import SecurityQuestionsFrame
        if self.content_frame:
            for w in self.content_frame.winfo_children():
                w.destroy()
            frame = SecurityQuestionsFrame(
                self.content_frame,
                db_path=getattr(self.auth, '_db_path', None),
                auth=self.auth,
            )
            frame.pack(fill="both", expand=True)
        else:
            # Fallback: open in a new Toplevel window
            win = tk.Toplevel(self.root)
            win.title("Security Questions")
            win.geometry("500x520")
            frame = SecurityQuestionsFrame(win, auth=self.auth)
            frame.pack(fill="both", expand=True)
    except Exception as e:
        logger.error("Failed to show security questions: %s", e, exc_info=True)
        from tkinter import messagebox
        messagebox.showerror("Error", f"Could not open Security Questions: {e}")


UnifiedManagementGUI.show_security_questions = show_security_questions
UnifiedManagementGUI.toggle_login_verification = toggle_login_verification
UnifiedManagementGUI.check_session_timer = check_session_timer
UnifiedManagementGUI.switch_to_cli = switch_to_cli
UnifiedManagementGUI.switch_system = switch_system
UnifiedManagementGUI.shutdown_system = shutdown_system
UnifiedManagementGUI.show_student_records = show_student_records
UnifiedManagementGUI.create_student_treeview = create_student_treeview
UnifiedManagementGUI.view_students = view_students
UnifiedManagementGUI.view_students_in_window = view_students_in_window
UnifiedManagementGUI.on_student_double_click = on_student_double_click
UnifiedManagementGUI.on_student_double_click_window = on_student_double_click_window
UnifiedManagementGUI.show_student_details = show_student_details
UnifiedManagementGUI._load_academic_data = _load_academic_data
UnifiedManagementGUI.search_students_dialog = search_students_dialog
UnifiedManagementGUI.create_student_dialog = create_student_dialog
UnifiedManagementGUI.update_student_dialog = update_student_dialog
UnifiedManagementGUI.delete_student_dialog = delete_student_dialog
UnifiedManagementGUI.select_student_for_deletion = select_student_for_deletion
UnifiedManagementGUI.manage_student_grades = manage_student_grades
UnifiedManagementGUI.view_student_attendance = view_student_attendance
UnifiedManagementGUI.view_student_timetable = view_student_timetable
UnifiedManagementGUI.reassign_modules = reassign_modules
UnifiedManagementGUI.export_student_data = export_student_data
UnifiedManagementGUI.export_individual_student_data = export_individual_student_data
UnifiedManagementGUI.export_data_dialog = export_data_dialog
UnifiedManagementGUI._export_to_csv = _export_to_csv
UnifiedManagementGUI._export_to_excel = _export_to_excel
UnifiedManagementGUI._export_to_pdf = _export_to_pdf
UnifiedManagementGUI._export_to_txt = _export_to_txt
UnifiedManagementGUI._export_comprehensive_csv = _export_comprehensive_csv
UnifiedManagementGUI._export_comprehensive_excel = _export_comprehensive_excel
UnifiedManagementGUI._export_comprehensive_pdf = _export_comprehensive_pdf
UnifiedManagementGUI._export_comprehensive_txt = _export_comprehensive_txt
UnifiedManagementGUI.create_staff_dialog = create_staff_dialog
UnifiedManagementGUI.update_staff_dialog = update_staff_dialog
UnifiedManagementGUI.view_staff = view_staff
UnifiedManagementGUI.delete_staff_dialog = delete_staff_dialog
UnifiedManagementGUI.search_staff_dialog = search_staff_dialog
UnifiedManagementGUI.show_user_management = show_user_management
UnifiedManagementGUI.refresh_user_list = refresh_user_list
UnifiedManagementGUI.show_create_user = show_create_user
UnifiedManagementGUI.show_user_details = show_user_details
UnifiedManagementGUI.show_edit_user = show_edit_user
UnifiedManagementGUI.reset_user_password = reset_user_password
UnifiedManagementGUI.view_all_users = view_all_users
UnifiedManagementGUI.add_new_user = add_new_user
UnifiedManagementGUI.manage_permissions = manage_permissions
UnifiedManagementGUI.show_system_admin = show_system_admin
UnifiedManagementGUI.show_system_administration_gui = show_system_administration_gui
UnifiedManagementGUI.create_database_admin_tab = create_database_admin_tab
UnifiedManagementGUI.create_user_admin_tab = create_user_admin_tab
UnifiedManagementGUI.create_monitoring_tab = create_monitoring_tab
UnifiedManagementGUI.create_config_tab = create_config_tab
UnifiedManagementGUI.create_operations_tab = create_operations_tab
UnifiedManagementGUI.view_active_sessions = view_active_sessions
UnifiedManagementGUI.view_system_logs = view_system_logs
UnifiedManagementGUI.view_error_logs = view_error_logs
UnifiedManagementGUI.show_backup = show_backup
UnifiedManagementGUI.show_data_backup_gui = show_data_backup_gui
UnifiedManagementGUI.show_batch_operations_gui = show_batch_operations_gui
UnifiedManagementGUI.fix_duplicates = fix_duplicates
UnifiedManagementGUI.optimize_database = optimize_database
UnifiedManagementGUI.run_integrity_check = run_integrity_check
UnifiedManagementGUI.show_db_statistics = show_db_statistics
UnifiedManagementGUI.show_db_performance = show_db_performance
UnifiedManagementGUI.show_active_connections = show_active_connections
UnifiedManagementGUI.wipe_database = wipe_database
UnifiedManagementGUI.edit_system_settings = edit_system_settings
UnifiedManagementGUI.configure_email = configure_email
UnifiedManagementGUI.configure_backup = configure_backup
UnifiedManagementGUI.configure_security = configure_security
UnifiedManagementGUI.show_security_dashboard = show_security_dashboard
UnifiedManagementGUI.show_audit_log_viewer = show_audit_log_viewer
UnifiedManagementGUI.show_activity_logger = show_activity_logger
UnifiedManagementGUI.show_activity_log = show_activity_log
UnifiedManagementGUI.show_system_monitoring_dashboard = show_system_monitoring_dashboard
UnifiedManagementGUI.show_configuration_editor = show_configuration_editor
UnifiedManagementGUI.show_query_analyser = show_query_analyser
UnifiedManagementGUI.show_capacity_planning = show_capacity_planning
UnifiedManagementGUI.show_usage_adoption_reports = show_usage_adoption_reports
UnifiedManagementGUI.show_custom_report_builder = show_custom_report_builder
UnifiedManagementGUI.show_api_documentation = show_api_documentation
UnifiedManagementGUI.show_notification_template_manager = show_notification_template_manager
UnifiedManagementGUI.show_data_retention_manager = show_data_retention_manager
UnifiedManagementGUI.show_system_changelog = show_system_changelog
UnifiedManagementGUI.show_department_isolation = show_department_isolation
UnifiedManagementGUI.show_integration_status_dashboard = show_integration_status_dashboard
UnifiedManagementGUI.show_license_management = show_license_management
UnifiedManagementGUI.show_disaster_recovery_plan = show_disaster_recovery_plan
UnifiedManagementGUI.show_library_management = show_library_management
UnifiedManagementGUI.show_academic_calendar = show_academic_calendar
UnifiedManagementGUI.show_course_management = show_course_management
UnifiedManagementGUI.show_module_management = show_module_management
UnifiedManagementGUI.show_module_scheduling = show_module_scheduling
UnifiedManagementGUI.show_grades = show_grades
UnifiedManagementGUI.show_grade_tracking_gui = show_grade_tracking_gui
UnifiedManagementGUI.show_assignments = show_assignments
UnifiedManagementGUI.show_plagiarism_checker = show_plagiarism_checker
UnifiedManagementGUI.show_ai_detector = show_ai_detector
UnifiedManagementGUI.open_ai_detector_window = open_ai_detector_window
UnifiedManagementGUI.open_attendance_gui = open_attendance_gui
UnifiedManagementGUI.open_absence_tracker_gui = open_absence_tracker_gui
UnifiedManagementGUI.show_virtual_classroom_gui = show_virtual_classroom_gui
UnifiedManagementGUI.show_office_hours_gui = show_office_hours_gui
UnifiedManagementGUI.show_student_union_portal = show_student_union_portal
UnifiedManagementGUI.open_student_union_portal_gui = open_student_union_portal_gui
UnifiedManagementGUI.open_parent_portal_gui = open_parent_portal_gui
UnifiedManagementGUI.open_alumni_portal_gui = open_alumni_portal_gui
UnifiedManagementGUI.open_student_support_portal_gui = open_student_support_portal_gui
UnifiedManagementGUI.open_health_portal_gui = open_health_portal_gui
UnifiedManagementGUI.open_helpdesk_gui = open_helpdesk_gui
UnifiedManagementGUI.show_mental_health_gui = show_mental_health_gui
UnifiedManagementGUI.show_early_warning_gui = show_early_warning_gui
UnifiedManagementGUI.show_career_services_gui = show_career_services_gui
UnifiedManagementGUI.open_internship_portal_gui = open_internship_portal_gui
UnifiedManagementGUI.show_trip_management_gui = show_trip_management_gui
UnifiedManagementGUI.open_trip_management_gui = open_trip_management_gui
UnifiedManagementGUI.show_legal_services_gui = show_legal_services_gui
UnifiedManagementGUI.show_betting_shop_gui = show_betting_shop_gui
UnifiedManagementGUI.show_mail_post_gui = show_mail_post_gui
UnifiedManagementGUI.show_staff_hr_gui = show_staff_hr_gui
UnifiedManagementGUI.show_finance_management = show_finance_management
UnifiedManagementGUI.show_finance_reporting_dashboard = show_finance_reporting_dashboard
UnifiedManagementGUI.show_student_finance_account = show_student_finance_account
UnifiedManagementGUI.show_financial_aid = show_financial_aid
UnifiedManagementGUI.show_club_payment_management = show_club_payment_management
UnifiedManagementGUI._create_payment_overview_tab_finance = _create_payment_overview_tab_finance
UnifiedManagementGUI._create_record_payment_tab_finance = _create_record_payment_tab_finance
UnifiedManagementGUI._create_payment_history_tab_finance = _create_payment_history_tab_finance
UnifiedManagementGUI.show_university_shop = show_university_shop
UnifiedManagementGUI.show_charity_shop = show_charity_shop
UnifiedManagementGUI.show_restaurant_management = show_restaurant_management
UnifiedManagementGUI.show_cafe_system = show_cafe_system
UnifiedManagementGUI.show_takeaway_system = show_takeaway_system
UnifiedManagementGUI.show_grocery_shop = show_grocery_shop
UnifiedManagementGUI.show_bar = show_bar
UnifiedManagementGUI.show_parking_management = show_parking_management
UnifiedManagementGUI.show_housing_accommodations = show_housing_accommodations
UnifiedManagementGUI.show_medical_accommodations = show_medical_accommodations
UnifiedManagementGUI.show_campus_events_gui = show_campus_events_gui
UnifiedManagementGUI.show_facilities_management_gui = show_facilities_management_gui
UnifiedManagementGUI.show_transportation_parking_gui = show_transportation_parking_gui
UnifiedManagementGUI.show_gym_gui = show_gym_gui
UnifiedManagementGUI.show_dentist_gui = show_dentist_gui
UnifiedManagementGUI.show_butcher_gui = show_butcher_gui
UnifiedManagementGUI.show_barber_gui = show_barber_gui
UnifiedManagementGUI.show_nailbar_gui = show_nailbar_gui
UnifiedManagementGUI.show_carrental_gui = show_carrental_gui
UnifiedManagementGUI.show_equipment_gui = show_equipment_gui
UnifiedManagementGUI.show_phoneshop_gui = show_phoneshop_gui
UnifiedManagementGUI.show_musicshop_gui = show_musicshop_gui
UnifiedManagementGUI.show_taxi_booking_gui = show_taxi_booking_gui
UnifiedManagementGUI.show_train_station_gui = show_train_station_gui
UnifiedManagementGUI.show_cinema_gui = show_cinema_gui
UnifiedManagementGUI.show_document_manager = show_document_manager
UnifiedManagementGUI.show_enhanced_reporting_dashboard = show_enhanced_reporting_dashboard
UnifiedManagementGUI.show_pdf_export_gui = show_pdf_export_gui
UnifiedManagementGUI.show_advanced_search_gui = show_advanced_search_gui
UnifiedManagementGUI.refresh_advanced_search = refresh_advanced_search
UnifiedManagementGUI.show_communication_dashboard_gui = show_communication_dashboard_gui
UnifiedManagementGUI.show_email_sms_gui = show_email_sms_gui
UnifiedManagementGUI.show_admissions_crm_gui = show_admissions_crm_gui
UnifiedManagementGUI.show_predictive_analytics_gui = show_predictive_analytics_gui
UnifiedManagementGUI.show_business_intelligence_gui = show_business_intelligence_gui
UnifiedManagementGUI.show_ai_features_gui = show_ai_features_gui
UnifiedManagementGUI.show_integration_marketplace_gui = show_integration_marketplace_gui
UnifiedManagementGUI.show_mobile_app_pwa_gui = show_mobile_app_pwa_gui
UnifiedManagementGUI.show_accessibility_tools_gui = show_accessibility_tools_gui
UnifiedManagementGUI.show_blockchain_credentials_gui = show_blockchain_credentials_gui
UnifiedManagementGUI.show_extras_launcher = show_extras_launcher
UnifiedManagementGUI._show_feature_gui = _show_feature_gui
UnifiedManagementGUI.show_police_station_gui = show_police_station_gui
UnifiedManagementGUI.show_security_desk_gui = show_security_desk_gui
UnifiedManagementGUI.show_todo_app_gui = show_todo_app_gui
UnifiedManagementGUI.show_church_management_gui = show_church_management_gui
UnifiedManagementGUI.show_bank_app_gui = show_bank_app_gui
UnifiedManagementGUI.show_exam_scheduler_gui = show_exam_scheduler_gui
UnifiedManagementGUI.show_exam_portal = show_exam_portal
UnifiedManagementGUI.show_student_analytics_gui = show_student_analytics_gui
UnifiedManagementGUI.show_student_outcomes_gui = show_student_outcomes_gui
UnifiedManagementGUI.show_student_timetable_gui = show_student_timetable_gui
UnifiedManagementGUI.show_student_registration_gui = show_student_registration_gui
UnifiedManagementGUI.show_student_dashboard_gui = show_student_dashboard_gui
UnifiedManagementGUI.show_lms_gui = show_lms_gui
UnifiedManagementGUI.compose_email = compose_email
UnifiedManagementGUI.send_email_to_student = send_email_to_student
UnifiedManagementGUI.show_email_manager = show_email_manager
UnifiedManagementGUI._send_welcome_email_to_student = _send_welcome_email_to_student
UnifiedManagementGUI._send_email_via_gui = _send_email_via_gui
UnifiedManagementGUI._show_welcome_email_fallback = _show_welcome_email_fallback
UnifiedManagementGUI._send_student_update_email = _send_student_update_email
UnifiedManagementGUI._show_update_email_fallback = _show_update_email_fallback
UnifiedManagementGUI.show_integrated_dashboard = show_integrated_dashboard
UnifiedManagementGUI.create_overview_tab = create_overview_tab
UnifiedManagementGUI.create_stats_tab = create_stats_tab
UnifiedManagementGUI.create_activity_tab = create_activity_tab
UnifiedManagementGUI.create_health_tab = create_health_tab
UnifiedManagementGUI.show_analytics = show_analytics
UnifiedManagementGUI.show_chatbot = show_chatbot
UnifiedManagementGUI.log_activity = log_activity
UnifiedManagementGUI.launch_analytics_gui_standalone = launch_analytics_gui_standalone
UnifiedManagementGUI.show_academic_progress_gui = show_academic_progress_gui
UnifiedManagementGUI.show_ai_study_gui = show_ai_study_gui
UnifiedManagementGUI.show_budget_tracker_gui = show_budget_tracker_gui
UnifiedManagementGUI.show_student_jobs_gui = show_student_jobs_gui
UnifiedManagementGUI.show_scholarship_finder_gui = show_scholarship_finder_gui
UnifiedManagementGUI.show_study_matching_gui = show_study_matching_gui
UnifiedManagementGUI.show_course_planning_gui = show_course_planning_gui
UnifiedManagementGUI.show_roommate_finder_gui = show_roommate_finder_gui
UnifiedManagementGUI.show_campus_navigation_gui = show_campus_navigation_gui
UnifiedManagementGUI.show_lost_found_gui = show_lost_found_gui
UnifiedManagementGUI.show_marketplace_gui = show_marketplace_gui
UnifiedManagementGUI.show_wellness_hub_gui = show_wellness_hub_gui
UnifiedManagementGUI.show_accessibility_portal_gui = show_accessibility_portal_gui
UnifiedManagementGUI.show_events_discovery_gui = show_events_discovery_gui
UnifiedManagementGUI.show_social_matching_gui = show_social_matching_gui
UnifiedManagementGUI.show_portfolio_system_gui = show_portfolio_system_gui
UnifiedManagementGUI.show_notifications_hub_gui = show_notifications_hub_gui
UnifiedManagementGUI.show_feedback_system_gui = show_feedback_system_gui
UnifiedManagementGUI.show_advising_portal_gui = show_advising_portal_gui
UnifiedManagementGUI.show_student_id_gui = show_student_id_gui
UnifiedManagementGUI.show_study_room_booking_gui = show_study_room_booking_gui
UnifiedManagementGUI.show_printing_services_gui = show_printing_services_gui


def show_student_journey_gui(self):
    """Launch the Student Journey Dashboard in a top-level window."""
    from education_system.shared.cross_system.journey_dashboard import JourneyDashboardFrame
    win = self.create_themed_toplevel(title="Student Journey", geometry="900x600")
    frame = JourneyDashboardFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_analytics_dashboard_gui(self):
    """Launch the Analytics Dashboard in a top-level window."""
    from education_system.shared.analytics.analytics_gui import AnalyticsDashboardFrame
    win = self.create_themed_toplevel(title="Analytics Dashboard", geometry="900x600")
    frame = AnalyticsDashboardFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_outcome_tracking_gui(self):
    """Launch the Outcome Tracking frame in a top-level window."""
    from education_system.shared.outcomes.outcomes_gui import OutcomeTrackingFrame
    win = self.create_themed_toplevel(title="Outcome Tracking", geometry="900x600")
    frame = OutcomeTrackingFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_predictive_alerts_gui(self):
    """Launch the Predictive Alerts frame in a top-level window."""
    from education_system.shared.predictive.predictive_gui import PredictiveAlertsFrame
    win = self.create_themed_toplevel(title="Predictive Alerts", geometry="900x600")
    frame = PredictiveAlertsFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_bulk_transfer_gui(self):
    """Launch the Bulk Transfer frame in a top-level window."""
    from education_system.shared.bulk_transfer.bulk_transfer_gui import BulkTransferFrame
    win = self.create_themed_toplevel(title="Bulk Transfer", geometry="900x600")
    frame = BulkTransferFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_transfer_documents_gui(self):
    """Launch the Transfer Documents frame in a top-level window."""
    from education_system.shared.transfer_docs.transfer_docs_gui import TransferDocumentsFrame
    win = self.create_themed_toplevel(title="Transfer Documents", geometry="900x600")
    frame = TransferDocumentsFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_reverse_lookup_gui(self):
    """Launch the Reverse Lookup frame in a top-level window."""
    from education_system.shared.reverse_lookup.reverse_lookup_gui import ReverseLookupFrame
    win = self.create_themed_toplevel(title="Reverse Lookup", geometry="900x600")
    frame = ReverseLookupFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_parent_continuity_gui(self):
    """Launch the Parent Continuity frame in a top-level window."""
    from education_system.shared.parent_continuity.parent_gui import ParentContinuityFrame
    win = self.create_themed_toplevel(title="Parent Continuity", geometry="900x600")
    frame = ParentContinuityFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_cross_system_calendar_gui(self):
    """Launch the Cross-System Calendar frame in a top-level window."""
    from education_system.shared.calendar.calendar_gui import CrossSystemCalendarFrame
    win = self.create_themed_toplevel(title="Cross-System Calendar", geometry="900x600")
    frame = CrossSystemCalendarFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)




def show_central_admin_gui(self):
    """Launch the Central Admin Portal frame in a top-level window."""
    from education_system.shared.admin_portal.admin_gui import CentralAdminFrame
    win = self.create_themed_toplevel(title="Central Admin Portal", geometry="900x600")
    frame = CentralAdminFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_gdpr_compliance_gui(self):
    """Launch the GDPR Compliance frame in a top-level window."""
    from education_system.shared.gdpr.gdpr_gui import GDPRComplianceFrame
    win = self.create_themed_toplevel(title="GDPR Compliance", geometry="900x600")
    frame = GDPRComplianceFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_shared_documents_gui(self):
    """Launch the Shared Documents frame in a top-level window."""
    from education_system.shared.documents.document_gui import SharedDocumentsFrame
    win = self.create_themed_toplevel(title="Shared Documents", geometry="900x600")
    frame = SharedDocumentsFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


def show_student_self_service_gui(self):
    """Launch the Student Self-Service frame in a top-level window."""
    from education_system.shared.student_portal.portal_gui import StudentSelfServiceFrame
    win = self.create_themed_toplevel(title="Student Self-Service", geometry="900x600")
    frame = StudentSelfServiceFrame(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


UnifiedManagementGUI.show_student_journey_gui = show_student_journey_gui
UnifiedManagementGUI.show_analytics_dashboard_gui = show_analytics_dashboard_gui
UnifiedManagementGUI.show_outcome_tracking_gui = show_outcome_tracking_gui
UnifiedManagementGUI.show_predictive_alerts_gui = show_predictive_alerts_gui
UnifiedManagementGUI.show_bulk_transfer_gui = show_bulk_transfer_gui
UnifiedManagementGUI.show_transfer_documents_gui = show_transfer_documents_gui
UnifiedManagementGUI.show_reverse_lookup_gui = show_reverse_lookup_gui
UnifiedManagementGUI.show_parent_continuity_gui = show_parent_continuity_gui
UnifiedManagementGUI.show_cross_system_calendar_gui = show_cross_system_calendar_gui
UnifiedManagementGUI.show_central_admin_gui = show_central_admin_gui
UnifiedManagementGUI.show_gdpr_compliance_gui = show_gdpr_compliance_gui
UnifiedManagementGUI.show_shared_documents_gui = show_shared_documents_gui
UnifiedManagementGUI.show_student_self_service_gui = show_student_self_service_gui


def show_certificates_gui(self):
    """Launch the Certificates & Transcripts frame in a top-level window."""
    from education_system.shared.certificates.certificates_gui import CertificatesGUI
    win = self.create_themed_toplevel(title="Certificates & Transcripts", geometry="1000x650")
    frame = CertificatesGUI(win, db_path=None, auth=self.auth)
    frame.pack(fill='both', expand=True)


UnifiedManagementGUI.show_certificates_gui = show_certificates_gui

# New features (modules 21-30)
UnifiedManagementGUI.show_hesa_export_gui = show_hesa_export_gui
UnifiedManagementGUI.show_student_app_gui = show_student_app_gui
UnifiedManagementGUI.show_achievement_badge_gui = show_achievement_badge_gui
UnifiedManagementGUI.show_study_recommendations_gui = show_study_recommendations_gui
UnifiedManagementGUI.show_clearing_adjustment_gui = show_clearing_adjustment_gui

