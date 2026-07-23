"""
Menu router for CLI system.

Routes user choices to appropriate handlers and manages menu navigation.
"""

from education_system.post_18.university_system.modules.shared.cli.imports import (
    logging, datetime, logger, _t, get_text, get_auth, UserAuth, set_auth,
    display_assignment_menu, display_course_management_menu,
    display_academic_calendar_menu, display_trip_management_menu,
    display_housing_accommodation_menu, display_shop_menu,
    display_log_management_menu, display_user_management_menu,
    display_auth_menu, display_parent_portal_menu,
    display_parent_portal_enhancement_menu,
    display_language_menu_option,
    # CLI availability flags
    ACADEMIC_MISCONDUCT_AVAILABLE, academic_misconduct_menu,
    SECURITY_DESK_AVAILABLE, security_desk_menu,
    TODO_AVAILABLE, todo_menu,
    CHURCH_AVAILABLE, church_menu,
    POLICE_STATION_AVAILABLE, police_station_menu,
    TAXI_BOOKING_AVAILABLE, taxi_booking_menu,
    TRAIN_STATION_AVAILABLE, train_station_menu,
    LEGAL_SERVICES_AVAILABLE, legal_services_menu,
    INFORMATION_RIGHTS_AVAILABLE, information_rights_menu,
    CARRENTAL_AVAILABLE, carrental_menu,
    EQUIPMENT_RENTAL_AVAILABLE, equipment_rental_menu,
    PHONE_SHOP_AVAILABLE, phone_shop_menu,
    MUSIC_SHOP_AVAILABLE, music_shop_menu,
    BAR_AVAILABLE, bar_menu,
    BETTING_SHOP_AVAILABLE, launch_betting_shop_cli,
    BUTCHER_SHOP_AVAILABLE, launch_butcher_cli,
    BARBER_SHOP_AVAILABLE, launch_barber_cli,
    NAILBAR_AVAILABLE, launch_nailbar_cli,
    CINEMA_AVAILABLE, launch_cinema_cli,
    MEDICAL_ACCOMMODATION_AVAILABLE, launch_medical_accommodation_cli,
    DEGREE_AUDIT_CLI_AVAILABLE, launch_degree_audit_cli,
    GRADUATION_CEREMONY_CLI_AVAILABLE, launch_graduation_ceremony_cli,
    MAIL_POST_AVAILABLE, mail_post_menu,
    GYM_AVAILABLE, gym_menu,
    DENTIST_AVAILABLE, dentist_menu,
    CHARITY_SHOP_CLI_AVAILABLE, display_charity_shop_menu,
    CAFE_CLI_AVAILABLE, display_cafe_menu,
    TAKEAWAY_CLI_AVAILABLE, display_takeaway_menu,
    GROCERY_CLI_AVAILABLE, display_grocery_menu,
    STAFF_HR_CLI_AVAILABLE, display_staff_hr_menu,
    SECURITY_DASHBOARD_CLI_AVAILABLE, display_security_dashboard_menu,
)

# Import additional functions from database_manager
from education_system.post_18.university_system.modules.shared.cli.database_manager import cleanup_database_on_startup, init_all_databases, init_auth_for_modules, cleanup_database_connections

# Import menu functions
from education_system.post_18.university_system.modules.shared.cli.student_operations import display_student_records_menu, set_auth as set_student_ops_auth
from education_system.post_18.university_system.modules.shared.cli.integration_manager import display_integrated_academic_menu, set_auth as set_integration_auth
from education_system.post_18.university_system.modules.domain.academics.services.lms.lms_core import display_lms_menu
from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import display_course_evaluation_menu
from education_system.post_18.university_system.modules.domain.health.services.health_portal import display_health_portal_menu
from education_system.post_18.university_system.modules.domain.student_affairs.services.career_services.career_services_core import display_career_services_menu
from education_system.post_18.university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import display_early_warning_menu
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.dashboard import display_support_menu
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.auth import set_auth as set_support_auth
from education_system.post_18.university_system.modules.domain.academics.services.library.menu import display_library_menu
from education_system.post_18.university_system.modules.domain.campus.facilities.services.facilities_management_core import display_facilities_management_menu
from education_system.post_18.university_system.modules.domain.admissions.services.admissions_crm_core import display_admissions_crm_menu
from education_system.post_18.university_system.modules.domain.admissions.ucas.ucas_cli import run as display_ucas_management_menu
from education_system.post_18.university_system.modules.domain.academics.research.services.research_grants_core import display_research_grants_menu
from education_system.post_18.university_system.modules.domain.campus.services.campus_events_core import display_campus_events_menu
from education_system.post_18.university_system.modules.domain.finance.gui.finance_reporting.misc import display_finance_menu, set_auth as set_finance_auth

# Import menu functions that may not exist - with fallbacks
try:
    from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking_management_gui import display_enhanced_grade_menu, predictive_analytics_menu
except ImportError:
    display_enhanced_grade_menu = None
    predictive_analytics_menu = None

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.gui.student_union_management_gui import display_student_union_menu
except ImportError:
    display_student_union_menu = None

# Import fully-implemented menu functions for previously-stubbed features
from education_system.post_18.university_system.modules.domain.academics.services.attendance import display_advanced_attendance_menu
from education_system.post_18.university_system.modules.domain.academics.services.timetable import display_timetable_optimizer_menu
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management import display_alumni_menu as display_alumni_relations_menu

# Import utility functions
from education_system.post_18.university_system.modules.shared.cli.utils import safe_auth_check

# Import exceptions
from education_system.post_18.university_system.core.exceptions import (
    ValidationError, AuthenticationError, PermissionDeniedError
)

# Import auth-related functions
from education_system.post_18.university_system.infrastructure.auth import set_auth_instance

# Import permission setup functions
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management import setup_alumni_permissions
from education_system.post_18.university_system.modules.domain.student_affairs.services.internship_management import setup_internship_permissions
from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import setup_student_union_permissions
from education_system.post_18.university_system.infrastructure.auth import add_finance_permissions
from education_system.post_18.university_system.modules.domain.commerce.services.shop_management import setup_shop_permissions
from education_system.post_18.university_system.modules.domain.campus.mobility.services.trip_management import setup_trip_permissions
from education_system.post_18.university_system.modules.services.cli.charity_shop_cli import setup_charity_shop_permissions
from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import setup_cafe_permissions
from education_system.post_18.university_system.modules.domain.commerce.services.takeaway.takeaway_service import setup_takeaway_permissions
from education_system.post_18.university_system.modules.domain.commerce.services.grocery.grocery_service import setup_grocery_permissions
from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.staff_hr_cli import setup_staff_hr_permissions
from education_system.post_18.university_system.modules.domain.academics.services.office_hours.office_hours_permissions import setup_office_hours_permissions
from education_system.post_18.university_system.modules.domain.academics.services.assignments.admin_tools.ta_permissions_setup import setup_ta_permissions

# Import Office Hours and TA Management CLI menus
try:
    from education_system.post_18.university_system.modules.domain.academics.cli.office_hours_cli import display_office_hours_menu
    OFFICE_HOURS_CLI_AVAILABLE = True
except ImportError:
    display_office_hours_menu = None
    OFFICE_HOURS_CLI_AVAILABLE = False

try:
    from education_system.post_18.university_system.modules.domain.academics.services.assignments.admin_tools.ta_management_cli import display_ta_management_menu
    TA_MANAGEMENT_CLI_AVAILABLE = True
except ImportError:
    display_ta_management_menu = None
    TA_MANAGEMENT_CLI_AVAILABLE = False

# Import plagiarism checker integration
from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui import integrate_plagiarism_checker_with_main

# Import auth linking
from education_system.post_18.university_system.modules.shared.cli.auth_manager import _link_auth_to_student_union

# Import admin tools menus
from education_system.post_18.university_system.modules.shared.cli.admin_tools import display_analytics_menu, display_batch_menu, display_admin_tools_menu

# Import export menu
from education_system.post_18.university_system.modules.shared.cli.export_manager import display_export_menu, display_pdf_export_menu

# Import system monitoring
from education_system.post_18.university_system.modules.shared.cli.system_monitoring import display_system_monitoring_menu

# Import service menus
from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import display_predictive_analytics_menu
from education_system.post_18.university_system.modules.shared.services.business_intelligence.bi_reports_core import display_business_intelligence_menu
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search import display_enhanced_menu
from education_system.post_18.university_system.modules.shared.services.ai_features.ai_features_core import display_ai_features_menu
from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core import display_integration_marketplace_menu

# Import domain-specific menus
from education_system.post_18.university_system.modules.domain.finance.blockchain.services.blockchain_credentials_core import display_blockchain_credentials_menu
from education_system.post_18.university_system.modules.domain.campus.mobility.services.mobile_app_pwa_core import display_mobile_app_pwa_menu
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.classroom_manager import VirtualClassroomManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.session_manager import SessionManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.participant_manager import ParticipantManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.recording_manager import RecordingManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.poll_manager import PollManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.breakout_room_manager import BreakoutRoomManager
from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.chat_manager import ChatManager
from education_system.post_18.university_system.modules.domain.finance.services.financial_aid.aid_manager import FinancialAidManager

auth = None


_CROSS_SYSTEM_MODULES = {
    "cross_analytics": ("education_system.shared.analytics.analytics_cli", "Analytics Dashboard"),
    "cross_outcomes": ("education_system.shared.outcomes.outcomes_cli", "Outcome Tracking"),
    "cross_predictive": ("education_system.shared.predictive.predictive_cli", "Predictive Alerts"),
    "cross_bulk_transfer": ("education_system.shared.bulk_transfer.bulk_transfer_cli", "Bulk Transfer"),
    "cross_transfer_docs": ("education_system.shared.transfer_docs.transfer_docs_cli", "Transfer Documents"),
    "cross_reverse_lookup": ("education_system.shared.reverse_lookup.reverse_lookup_cli", "Reverse Lookup"),
    "cross_parent_continuity": ("education_system.shared.parent_continuity.parent_cli", "Parent Continuity"),
    "cross_calendar": ("education_system.shared.calendar.calendar_cli", "Cross-System Calendar"),
    "cross_messaging": ("education_system.shared.messaging.cross_system_cli", "Inter-System Messaging"),
    "cross_admin_portal": ("education_system.shared.admin_portal.admin_cli", "Central Admin Portal"),
    "cross_gdpr": ("education_system.shared.gdpr.gdpr_cli", "GDPR Compliance"),
    "cross_documents": ("education_system.shared.documents.document_cli", "Shared Documents"),
    "cross_student_portal": ("education_system.shared.student_portal.portal_cli", "Student Self-Service"),
    "cross_transcript": ("education_system.shared.transcript.transcript_cli", "Digital Transcript"),
}


def _handle_cross_system_tool(option, auth):
    """Lazily import and run a cross-system shared CLI module."""
    if option not in _CROSS_SYSTEM_MODULES:
        print(f"\nUnknown cross-system tool: {option}")
        input("Press Enter to continue...")
        return

    module_path, label = _CROSS_SYSTEM_MODULES[option]
    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.run(db_path=None, auth=auth)
    except ImportError:
        print(f"\n  {label} module is not available.")
        input("Press Enter to continue...")
    except Exception as e:
        print(f"\n  Error running {label}: {e}")
        input("Press Enter to continue...")


def display_menu():
    global auth

    # Link auth to Student Union (only if auth exists)
    try:
        _link_auth_to_student_union(auth)
    except NameError as e:
        # auth not created yet; skip silently or initialize it before calling display_menu
        logger.debug(f"Auth not yet initialized during display_menu call: {e}")

    # One-time system initialization
    if not getattr(display_menu, "_system_init_complete", False):
        logger.info("Performing one-time system initialization...")

        # Clean up any hanging connections first
        cleanup_database_on_startup()

        # Initialize all databases
        if not init_all_databases():
            print("Failed to initialize databases. Exiting.")
            return

        display_menu._system_init_complete = True
        logger.info("System initialization completed successfully")

    # Sync authentication with shared context (always refresh to stay current
    # after system switches)
    try:
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
            set_auth(auth)
        safe_auth_check(auth)
        set_auth_instance(auth)
    except (ValueError, TypeError, ValidationError) as e:
        logger.error(f"Error initializing authentication: {e}")
        logger.info("Creating minimal auth object...")
        class MinimalAuth:
            def __init__(self):
                self.current_user = None
                self.last_activity = None
                self.session_timeout = 30
                self.login_attempts = {}
                self.max_attempts = 5
                self.lockout_time = 15

            def check_session(self):
                return False

            def check_permission(self, perm):
                return False

            def logout(self):
                self.current_user = None

        auth = MinimalAuth()

    if not getattr(display_menu, '_auth_modules_initialized', False):
        init_auth_for_modules()
        display_menu._auth_modules_initialized = True

    # Setup permissions for various modules (ONLY ONCE)
    if not hasattr(display_menu, '_permissions_setup'):
        try:
            setup_alumni_permissions()
            setup_internship_permissions()
            setup_student_union_permissions(auth)
            add_finance_permissions()
            setup_shop_permissions(auth)
            setup_trip_permissions()  # Add this line
            setup_charity_shop_permissions(auth)  # Charity shop permissions
            setup_cafe_permissions(auth)  # Cafe system permissions
            setup_takeaway_permissions(auth)  # Takeaway system permissions
            setup_grocery_permissions(auth)  # Grocery shop permissions
            setup_staff_hr_permissions(auth)  # Staff HR permissions
            setup_office_hours_permissions(auth)  # Office Hours permissions
            setup_ta_permissions(auth)  # TA Management permissions

            # Add plagiarism permissions AFTER UserAuth is fully initialized
            try:
                from education_system.post_18.university_system.infrastructure.auth import add_plagiarism_permissions
                created_permissions = add_plagiarism_permissions(auth)
                if created_permissions:
                    logger.info(f"Added plagiarism permissions: {', '.join(created_permissions)}")
                else:
                    logger.info("Plagiarism permissions already exist")
            except (AuthenticationError, PermissionDeniedError) as e:
                logging.warning(f"Could not add plagiarism permissions: {e}")

        except (AuthenticationError, PermissionDeniedError) as e:
            logging.warning(f"Error setting up permissions: {e}")

        # Mark permissions as setup
        display_menu._permissions_setup = True

    # Initialize plagiarism checker integration (ONLY ONCE)
    if not hasattr(display_menu, '_plagiarism_initialized'):
        try:
            integrate_plagiarism_checker_with_main()
            display_menu._plagiarism_initialized = True
            logger.info("Plagiarism checker integration completed")
        except (AuthenticationError, PermissionDeniedError) as e:
            logging.warning(f"Failed to initialize plagiarism checker: {e}")
            display_menu._plagiarism_initialized = True
            logger.warning("Plagiarism checker integration had issues")

    # Main application loop
    while True:
        # Check if user is logged in
        if not safe_auth_check(auth) or not auth.current_user:
            # User logged out — signal back to run.py for universal login
            # so multi-system users (e.g. superadmin) can pick a system
            from education_system.switch import request_logout
            request_logout(mode="cli")
            return

        # User is now logged in, show main menu
        try:
            print(f"\n{get_text('cli.logged_in_as', default='Logged in as')}: {auth.current_user['username']} ({auth.current_user['role']})")
        except (AttributeError, TypeError):
            print(f"\n{get_text('cli.logged_in_details_unavailable', default='Logged in (user details unavailable)')}")

        # NEW CONSOLIDATED MENU STRUCTURE
        print("\n" + "="*100)
        print(get_text('cli.main_title', default='UNIVERSITY MANAGEMENT SYSTEM').center(100))
        print("="*100)

        option_map = {}
        option_num = 1
        col_width = 24  # Width for each column

        def print_row(items):
            """Print items in a row of up to 4 columns"""
            row = ""
            for item in items:
                row += item.ljust(col_width)
            print(row)

        def add_option(label, key):
            """Add option and return formatted string"""
            nonlocal option_num
            option_map[str(option_num)] = key
            result = f"{option_num}. {label}"
            option_num += 1
            return result

        # 📚 ACADEMIC & LEARNING
        print(f"\n📚 {get_text('cli.menu.academic_learning', default='ACADEMIC & LEARNING')}")
        items = [
            add_option(get_text('cli.menu.student_records', default='Student Records'), "student_records"),
            add_option(get_text('cli.menu.course_management', default='Course Management'), "course_management"),
            add_option(get_text('cli.menu.academic_calendar', default='Academic Calendar'), "integrated_academic"),
            add_option(get_text('cli.menu.grade_tracking', default='Grade Tracking'), "grades"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.lms', default='LMS'), "lms_system"),
            add_option(get_text('cli.menu.attendance', default='Attendance'), "advanced_attendance"),
            add_option(get_text('cli.menu.timetable', default='Timetable'), "timetable_optimizer"),
            add_option(get_text('cli.menu.course_evaluation', default='Course Evaluation'), "course_evaluation"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.virtual_classroom', default='Virtual Classroom'), "virtual_classroom"),
            add_option(get_text('cli.menu.predictive_analytics', default='Predictive Analytics'), "predictive_analytics"),
            add_option("Exam Management", "exam_portal"),
            add_option("Course Planning", "course_planning"),
            add_option("Lesson Planner", "lesson_planner"),
        ]
        print_row(items)
        items = []
        if DEGREE_AUDIT_CLI_AVAILABLE:
            items.append(add_option(get_text('cli.menu.degree_audit', default='Degree Audit'), "degree_audit"))
        if GRADUATION_CEREMONY_CLI_AVAILABLE:
            items.append(add_option(get_text('cli.menu.graduation_ceremony', default='Graduation Ceremony'), "graduation_ceremony"))
        if OFFICE_HOURS_CLI_AVAILABLE:
            items.append(add_option("Office Hours", "office_hours"))
        if TA_MANAGEMENT_CLI_AVAILABLE:
            items.append(add_option("TA Management", "ta_management"))
        if items:
            print_row(items)
        items = [
            add_option("Apprenticeships", "apprenticeships"),
            add_option("Placements", "placements"),
        ]
        print_row(items)

        # 👥 STUDENT SERVICES
        print(f"\n👥 {get_text('cli.menu.student_services', default='STUDENT SERVICES')}")
        items = [
            add_option(get_text('cli.menu.housing', default='Housing'), "housing_accommodations"),
            add_option(get_text('cli.menu.health_portal', default='Health Portal'), "health_portal"),
            add_option(get_text('cli.menu.student_union', default='Student Union'), "student_union_portal"),
            add_option(get_text('cli.menu.career_services', default='Career Services'), "career_services"),
        ]
        if MEDICAL_ACCOMMODATION_AVAILABLE:
            items.append(add_option(get_text('cli.menu.medical_accommodation', default='Medical Accommodations'), "medical_accommodation"))
        print_row(items)
        items = [
            add_option(get_text('cli.menu.financial_aid', default='Financial Aid'), "financial_aid"),
            add_option(get_text('cli.menu.early_warning', default='Early Warning'), "early_warning_system"),
            add_option(get_text('cli.menu.support_helpdesk', default='Support/Helpdesk'), "student_support"),
        ]
        if LEGAL_SERVICES_AVAILABLE:
            items.append(add_option(get_text('cli.menu.legal_services', default='Legal Services'), "legal_services"))
        if INFORMATION_RIGHTS_AVAILABLE:
            items.append(add_option(get_text('cli.menu.information_rights', default='SAR / FOI Requests'), "information_rights"))
        print_row(items)
        items = []
        items.append(add_option("Advising", "advising"))
        items.append(add_option("Wellbeing", "student_wellbeing"))
        items.append(add_option("Student Finance", "student_finance"))
        print_row(items)
        items = [
            add_option("First Aid", "first_aid"),
            add_option("Health & Safety", "health_safety"),
        ]
        print_row(items)
        items = []
        items.append(add_option("Student ID", "student_id_card"))
        if GYM_AVAILABLE:
            items.append(add_option(get_text('cli.menu.gym', default='Gym/Fitness'), "gym"))
        if DENTIST_AVAILABLE:
            items.append(add_option(get_text('cli.menu.dentist', default='Dental Clinic'), "dentist"))
        if items:
            print_row(items)

        # 💼 BUSINESS OPERATIONS
        print(f"\n💼 {get_text('cli.menu.business_operations', default='BUSINESS OPERATIONS')}")
        items = [
            add_option(get_text('cli.menu.finance', default='Finance'), "finance_management"),
            add_option(get_text('cli.menu.library', default='Library'), "library"),
            add_option(get_text('cli.menu.facilities', default='Facilities'), "facilities_management"),
            add_option(get_text('cli.menu.transport_parking', default='Transport/Parking'), "transportation_parking"),
        ]
        print_row(items)
        items = [
            add_option("Bank Reconciliation", "bank_rec"),
            add_option("General Ledger", "ledger"),
            add_option("Statement Runs", "statements"),
            add_option("Bakery Shop", "bakery_shop"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.charity_shop', default='Charity Shop'), "charity_shop"),
            add_option(get_text('cli.menu.cafe_system', default='Cafe System'), "cafe_system"),
            add_option(get_text('cli.menu.takeaway', default='Takeaway'), "takeaway_system"),
            add_option(get_text('cli.menu.grocery_shop', default='Grocery Shop'), "grocery_shop"),
        ]
        print_row(items)
        items = []
        if BAR_AVAILABLE:
            items.append(add_option(get_text('cli.menu.bar', default='Bar/Pub'), "bar"))
        if EQUIPMENT_RENTAL_AVAILABLE:
            items.append(add_option(get_text('cli.menu.equipment_rental', default='Equipment Rental'), "equipment_rental"))
        if PHONE_SHOP_AVAILABLE:
            items.append(add_option(get_text('cli.menu.phone_shop', default='Phone Shop'), "phone_shop"))
        if MUSIC_SHOP_AVAILABLE:
            items.append(add_option(get_text('cli.menu.music_shop', default='Music Shop'), "music_shop"))
        if items:  # Only print if there are items
            print_row(items)
        items = []
        if BETTING_SHOP_AVAILABLE:
            items.append(add_option(get_text('cli.menu.betting_shop', default='Betting Shop'), "betting_shop"))
        if BUTCHER_SHOP_AVAILABLE:
            items.append(add_option(get_text('cli.menu.butcher_shop', default='Butcher Shop'), "butcher_shop"))
        if BARBER_SHOP_AVAILABLE:
            items.append(add_option(get_text('cli.menu.barber_shop', default='Barber Shop'), "barber_shop"))
        if NAILBAR_AVAILABLE:
            items.append(add_option(get_text('cli.menu.nailbar', default='Nail Bar/Salon'), "nailbar"))
        if items:  # Only print if there are items
            print_row(items)
        items = []
        if CINEMA_AVAILABLE:
            items.append(add_option(get_text('cli.menu.cinema', default='Cinema'), "cinema"))
        if items:  # Only print if there are items
            print_row(items)

        # 🚔 CAMPUS SERVICES & MOBILITY
        print(f"\n🚔 {get_text('cli.menu.campus_services_mobility', default='CAMPUS SERVICES & MOBILITY')}")
        items = []
        if POLICE_STATION_AVAILABLE:
            items.append(add_option(get_text('cli.menu.police_station', default='Campus Police'), "police_station"))
        if TAXI_BOOKING_AVAILABLE:
            items.append(add_option(get_text('cli.menu.taxi_booking', default='Taxi Booking'), "taxi_booking"))
        if TRAIN_STATION_AVAILABLE:
            items.append(add_option(get_text('cli.menu.train_station', default='Train Station'), "train_station"))
        if CARRENTAL_AVAILABLE:
            items.append(add_option(get_text('cli.menu.car_rental', default='Car Rental'), "car_rental"))
        if MAIL_POST_AVAILABLE:
            items.append(add_option(get_text('cli.menu.mail_post', default='Mail/Post Services'), "mail_post"))
        if items:  # Only print if there are items
            print_row(items)

        # 💬 COMMUNICATION & 🏛️ INSTITUTIONAL
        print(f"\n💬 {get_text('cli.menu.communication_institutional', default='COMMUNICATION & INSTITUTIONAL')}")
        items = [
            add_option(get_text('cli.menu.communication_hub', default='Communication Hub'), "communication_hub"),
            add_option(get_text('cli.menu.admissions_crm', default='Admissions CRM'), "admissions_crm"),
            add_option(get_text('cli.menu.ucas_management', default='UCAS Management'), "ucas_management"),
            add_option(get_text('cli.menu.alumni_relations', default='Alumni Relations'), "alumni_relations"),
            add_option(get_text('cli.menu.research_grants', default='Research/Grants'), "research_grants"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.campus_events', default='Campus Events'), "campus_events"),
            add_option(get_text('cli.menu.staff_hr', default='Staff/HR Management'), "staff_hr_management"),
        ]
        if CHURCH_AVAILABLE:
            items.append(add_option(get_text('cli.menu.church', default='Church Management'), "church"))
        if SECURITY_DESK_AVAILABLE:
            items.append(add_option(get_text('cli.menu.security_desk', default='Security Desk'), "security_desk"))
        print_row(items)

        # ⚖️ COMPLIANCE & CASE MANAGEMENT
        print(f"\n⚖️  {get_text('cli.menu.compliance_case', default='COMPLIANCE & CASE MANAGEMENT')}")
        items = [
            add_option(get_text('cli.menu.safeguarding', default='Safeguarding'), "safeguarding"),
            add_option(get_text('cli.menu.visa_compliance', default='Visa Compliance'), "visa_compliance"),
            add_option(get_text('cli.menu.equality_diversity', default='Equality & Diversity'), "equality_diversity"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.disciplinary', default='Disciplinary'), "disciplinary"),
            add_option(get_text('cli.menu.fitness_to_practise', default='Fitness to Practise'), "fitness_to_practise"),
            add_option(get_text('cli.menu.risk_management', default='Risk Management'), "risk_management"),
        ]
        print_row(items)

        # 🔧 TECHNOLOGY & ANALYTICS
        print(f"\n🔧 {get_text('cli.menu.technology_analytics', default='TECHNOLOGY & ANALYTICS')}")
        items = [
            add_option(get_text('cli.menu.admin_tools', default='Admin Tools'), "administrative_tools"),
            add_option(get_text('cli.menu.security_dashboard', default='Security Dashboard'), "security_dashboard"),
            add_option(get_text('cli.menu.data_documents', default='Data/Documents'), "data_document_management"),
            add_option(get_text('cli.menu.ai_features', default='AI Features'), "ai_features"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.business_intel', default='Business Intel'), "business_intelligence"),
            add_option(get_text('cli.menu.integrations', default='Integrations'), "integration_marketplace"),
            add_option(get_text('cli.menu.blockchain_creds', default='Blockchain Creds'), "blockchain_credentials"),
            add_option(get_text('cli.menu.pdf_export', default='PDF Export'), "pdf_database_export"),
        ]
        print_row(items)
        items = [
            add_option(get_text('cli.menu.authentication', default='Authentication'), "authentication"),
        ]
        print_row(items)

        # 🎓 NEW UNIVERSITY FEATURES
        print("\n🎓 NEW UNIVERSITY FEATURES")
        items = [
            add_option("HESA Export", "hesa_export"),
            add_option("External Examiners", "external_examiners"),
            add_option("External QA (OfS/TEF/REF)", "external_qa"),
            add_option("Mitigating Circumstances", "mitigating_circumstances"),
            add_option("Curriculum Spec.", "curriculum_specification"),
        ]
        print_row(items)
        items = [
            add_option("Student App", "student_app"),
            add_option("Status Letters", "enrolment_letters"),
            add_option("Achievement Badges", "achievement_badges"),
            add_option("Study Recommend.", "study_recommendations"),
            add_option("Clearing/Adjust.", "clearing_adjustment"),
            add_option("APL/RPL", "prior_learning"),
        ]
        print_row(items)
        items = [
            add_option("Printing", "printing"),
            add_option("Study Rooms", "study_rooms"),
            add_option("Textbooks", "textbooks"),
        ]
        print_row(items)

        # 🔗 CROSS-SYSTEM TOOLS (admin only)
        if auth.current_user and auth.current_user.get('role', '').lower() in ('admin', 'administrator'):
            print(f"\n🔗 {get_text('cli.menu.cross_system_tools', default='CROSS-SYSTEM TOOLS')}")
            items = [
                add_option("Analytics Dashboard", "cross_analytics"),
                add_option("Outcome Tracking", "cross_outcomes"),
                add_option("Predictive Alerts", "cross_predictive"),
                add_option("Bulk Transfer", "cross_bulk_transfer"),
            ]
            print_row(items)
            items = [
                add_option("Transfer Documents", "cross_transfer_docs"),
                add_option("Reverse Lookup", "cross_reverse_lookup"),
                add_option("Parent Continuity", "cross_parent_continuity"),
                add_option("Cross-System Calendar", "cross_calendar"),
            ]
            print_row(items)
            items = [
                add_option("Inter-System Messaging", "cross_messaging"),
                add_option("Central Admin Portal", "cross_admin_portal"),
                add_option("GDPR Compliance", "cross_gdpr"),
                add_option("Shared Documents", "cross_documents"),
            ]
            print_row(items)
            items = [
                add_option("Student Self-Service", "cross_student_portal"),
                add_option("Digital Transcript", "cross_transcript"),
            ]
            print_row(items)

        # ✨ NEW FEATURES
        print(f"\n✨ {get_text('cli.menu.new_features', default='NEW FEATURES')}")
        items = [
            add_option("Employer Portal", "nf_employer_portal"),
            add_option("Intervention Outcomes", "nf_intervention_outcomes"),
            add_option("KPI Dashboard", "nf_kpi_dashboard"),
            add_option("Institutional Analytics", "nf_institutional_analytics"),
            add_option("Bursary Management", "nf_bursary"),
        ]
        print_row(items)
        items = [
            add_option("Peer Mentoring Matching", "nf_mentoring_matching"),
            add_option("Room Booking", "nf_room_booking"),
            add_option("Tutor Groups", "nf_tutor_groups"),
        ]
        print_row(items)

        # 📱 INFRASTRUCTURE & ⚙️ SYSTEM
        print(f"\n📱 {get_text('cli.menu.infrastructure_system', default='INFRASTRUCTURE & SYSTEM')}")
        items = [
            add_option(get_text('cli.menu.mobile_app', default='Mobile App (PWA)'), "mobile_app_pwa"),
            add_option(get_text('cli.menu.switch_to_gui', default='Switch to GUI'), "switch_to_gui"),
            add_option(get_text('cli.menu.language', default='Language'), "change_language"),
        ]
        # Superadmins (admin role on the university system) can jump
        # straight to another system without going through the login.
        try:
            from education_system.launcher.roles import is_superadmin as _is_sa
            if _is_sa(auth.current_user if auth else None):
                items.append(add_option(
                    get_text('cli.menu.switch_system', default='Switch System'),
                    "switch_system",
                ))
        except Exception:
            pass
        # Add monitoring/backup options for admin users
        if auth.current_user and auth.current_user.get('role') == 'admin':
            items.append(add_option(get_text('cli.menu.system_monitoring', default='System Monitoring'), "system_monitoring"))
        print_row(items)
        items = [
            add_option(get_text('cli.menu.logout', default='Logout'), "logout"),
        ]
        if TODO_AVAILABLE:
            items.append(add_option(get_text('cli.menu.todo', default='To-Do List'), "todo"))
        print_row(items)
        items = [
            add_option(get_text('cli.menu.exit', default='Exit'), "exit"),
        ]
        print_row(items)
        max_option = option_num - 1

        print("="*100)

        # Get user choice
        choice = input(f"\n{get_text('cli.enter_choice', default='Enter your choice')}: ")

        # Route to appropriate menu
        if choice in option_map:
            option = option_map[choice]

            if option == "student_records":
                set_student_ops_auth(auth)
                display_student_records_menu()
            elif option == "course_management":
                display_course_management_menu(auth)
            elif option == "integrated_academic":
                set_integration_auth(auth)
                display_integrated_academic_menu()
            elif option == "grades":
                if display_enhanced_grade_menu:
                    display_enhanced_grade_menu()
                else:
                    print("\n❌ Enhanced Grade menu is not available")
                    input("Press Enter to continue...")
            elif option == "lms_system":
                display_lms_menu(auth)
            elif option == "advanced_attendance":
                display_advanced_attendance_menu()
            elif option == "timetable_optimizer":
                display_timetable_optimizer_menu()
            elif option == "course_evaluation":
                display_course_evaluation_menu(auth)
            elif option == "virtual_classroom":
                display_virtual_classroom_menu(auth)
            elif option == "predictive_analytics":
                if predictive_analytics_menu:
                    predictive_analytics_menu()
                else:
                    print("\n❌ Predictive Analytics menu is not available")
                    input("Press Enter to continue...")
            elif option == "exam_portal":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.cli.exam_management_cli import display_exam_portal_menu
                    display_exam_portal_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Exam Management CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "degree_audit":
                if DEGREE_AUDIT_CLI_AVAILABLE:
                    launch_degree_audit_cli(auth)
                else:
                    print("\n❌ Degree Audit CLI is not available")
                    input("Press Enter to continue...")
            elif option == "graduation_ceremony":
                if GRADUATION_CEREMONY_CLI_AVAILABLE:
                    launch_graduation_ceremony_cli(auth)
                else:
                    print("\n❌ Graduation Ceremony CLI is not available")
                    input("Press Enter to continue...")
            elif option == "office_hours":
                if OFFICE_HOURS_CLI_AVAILABLE:
                    display_office_hours_menu(auth)
                else:
                    print("\n❌ Office Hours menu is not available")
                    input("Press Enter to continue...")
            elif option == "ta_management":
                if TA_MANAGEMENT_CLI_AVAILABLE:
                    display_ta_management_menu(auth)
                else:
                    print("\n❌ TA Management menu is not available")
                    input("Press Enter to continue...")
            elif option == "housing_accommodations":
                display_housing_accommodation_menu()
            elif option == "health_portal":
                display_health_portal_menu(auth)
            elif option == "medical_accommodation":
                if MEDICAL_ACCOMMODATION_AVAILABLE:
                    launch_medical_accommodation_cli(auth)
                else:
                    print("\n❌ Medical Accommodation CLI is not available")
                    input("Press Enter to continue...")
            elif option == "student_union_portal":
                if display_student_union_menu:
                    try:
                        from education_system.post_18.university_system.modules.domain.student_affairs.student_union import set_auth as _su_set_auth
                        _su_set_auth(auth)
                    except ImportError:
                        pass
                    display_student_union_menu()
                else:
                    print("\n❌ Student Union menu is not available")
                    input("Press Enter to continue...")
            elif option == "career_services":
                display_career_services_menu(auth)
            elif option == "financial_aid":
                display_financial_aid_menu(auth)
            elif option == "early_warning_system":
                display_early_warning_menu(auth)
            elif option == "student_support":
                set_support_auth(auth)
                display_support_menu()
            elif option == "finance_management":
                set_finance_auth(auth)
                display_finance_menu(auth)
            elif option == "library":
                display_library_menu()
            elif option == "facilities_management":
                display_facilities_management_menu(auth)
            elif option == "transportation_parking":
                display_transportation_parking_menu(auth)
            elif option == "charity_shop":
                if CHARITY_SHOP_CLI_AVAILABLE and display_charity_shop_menu:
                    display_charity_shop_menu()
                else:
                    print("\n❌ Charity Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "cafe_system":
                if CAFE_CLI_AVAILABLE and display_cafe_menu:
                    display_cafe_menu()
                else:
                    print("\n❌ Cafe System CLI is not available")
                    input("Press Enter to continue...")
            elif option == "takeaway_system":
                if TAKEAWAY_CLI_AVAILABLE and display_takeaway_menu:
                    display_takeaway_menu()
                else:
                    print("\n❌ Takeaway System CLI is not available")
                    input("Press Enter to continue...")
            elif option == "grocery_shop":
                if GROCERY_CLI_AVAILABLE and display_grocery_menu:
                    display_grocery_menu()
                else:
                    print("\n❌ Grocery Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "communication_hub":
                display_communication_hub_menu(auth)
            elif option == "admissions_crm":
                display_admissions_crm_menu(auth)
            elif option == "ucas_management":
                display_ucas_management_menu()
            elif option == "alumni_relations":
                display_alumni_relations_menu()
            elif option == "research_grants":
                display_research_grants_menu(auth)
            elif option == "campus_events":
                display_campus_events_menu(auth)
            elif option == "staff_hr_management":
                if STAFF_HR_CLI_AVAILABLE and display_staff_hr_menu:
                    display_staff_hr_menu()
                else:
                    print("\n❌ Staff HR CLI is not available")
                    input("Press Enter to continue...")
            elif option == "church":
                if CHURCH_AVAILABLE:
                    church_menu()
                else:
                    print("\n❌ Church Management CLI is not available")
                    input("Press Enter to continue...")
            elif option == "security_desk":
                if SECURITY_DESK_AVAILABLE:
                    security_desk_menu()
                else:
                    print("\n❌ Security Desk CLI is not available")
                    input("Press Enter to continue...")
            elif option == "police_station":
                if POLICE_STATION_AVAILABLE:
                    police_station_menu()
                else:
                    print("\n❌ Police Station CLI is not available")
                    input("Press Enter to continue...")
            elif option == "taxi_booking":
                if TAXI_BOOKING_AVAILABLE:
                    taxi_booking_menu()
                else:
                    print("\n❌ Taxi Booking CLI is not available")
                    input("Press Enter to continue...")
            elif option == "train_station":
                if TRAIN_STATION_AVAILABLE:
                    train_station_menu()
                else:
                    print("\n❌ Train Station CLI is not available")
                    input("Press Enter to continue...")
            elif option == "legal_services":
                if LEGAL_SERVICES_AVAILABLE:
                    legal_services_menu()
                else:
                    print("\n❌ Legal Services CLI is not available")
                    input("Press Enter to continue...")
            elif option == "information_rights":
                if INFORMATION_RIGHTS_AVAILABLE:
                    information_rights_menu()
                else:
                    print("\n❌ Information Rights CLI is not available")
                    input("Press Enter to continue...")
            elif option == "safeguarding":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.cli import run_safeguarding_menu
                    run_safeguarding_menu(auth)
                except Exception as e:
                    print(f"\n❌ Safeguarding CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "visa_compliance":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.international_compliance.cli import run_visa_compliance_menu
                    run_visa_compliance_menu(auth)
                except Exception as e:
                    print(f"\n❌ Visa Compliance CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "equality_diversity":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.cli import run_equality_diversity_menu
                    run_equality_diversity_menu(auth)
                except Exception as e:
                    print(f"\n❌ Equality & Diversity CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "disciplinary":
                try:
                    from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.cli import run_disciplinary_menu
                    run_disciplinary_menu(auth)
                except Exception as e:
                    print(f"\n❌ Disciplinary CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "fitness_to_practise":
                try:
                    from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.fitness_to_practise.cli import run_ftp_menu
                    run_ftp_menu(auth)
                except Exception as e:
                    print(f"\n❌ Fitness to Practise CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "risk_management":
                try:
                    from education_system.post_18.university_system.modules.domain.operations.legal.risk_management.cli import run_risk_management_menu
                    run_risk_management_menu(auth)
                except Exception as e:
                    print(f"\n❌ Risk Management CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "car_rental":
                if CARRENTAL_AVAILABLE:
                    carrental_menu()
                else:
                    print("\n❌ Car Rental CLI is not available")
                    input("Press Enter to continue...")
            elif option == "equipment_rental":
                if EQUIPMENT_RENTAL_AVAILABLE:
                    equipment_rental_menu()
                else:
                    print("\n❌ Equipment Rental CLI is not available")
                    input("Press Enter to continue...")
            elif option == "phone_shop":
                if PHONE_SHOP_AVAILABLE:
                    phone_shop_menu()
                else:
                    print("\n❌ Phone Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "music_shop":
                if MUSIC_SHOP_AVAILABLE:
                    music_shop_menu()
                else:
                    print("\n❌ Music Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "bar":
                if BAR_AVAILABLE:
                    bar_menu()
                else:
                    print("\n❌ Bar CLI is not available")
                    input("Press Enter to continue...")
            elif option == "betting_shop":
                if BETTING_SHOP_AVAILABLE:
                    launch_betting_shop_cli(auth)
                else:
                    print("\n❌ Betting Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "butcher_shop":
                if BUTCHER_SHOP_AVAILABLE:
                    launch_butcher_cli(auth)
                else:
                    print("\n❌ Butcher Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "barber_shop":
                if BARBER_SHOP_AVAILABLE:
                    launch_barber_cli(auth)
                else:
                    print("\n❌ Barber Shop CLI is not available")
                    input("Press Enter to continue...")
            elif option == "nailbar":
                if NAILBAR_AVAILABLE:
                    launch_nailbar_cli(auth)
                else:
                    print("\n❌ Nail Bar CLI is not available")
                    input("Press Enter to continue...")
            elif option == "cinema":
                if CINEMA_AVAILABLE:
                    launch_cinema_cli(auth)
                else:
                    print("\n❌ Cinema CLI is not available")
                    input("Press Enter to continue...")
            elif option == "mail_post":
                if MAIL_POST_AVAILABLE:
                    mail_post_menu()
                else:
                    print("\n❌ Mail/Post CLI is not available")
                    input("Press Enter to continue...")
            elif option == "gym":
                if GYM_AVAILABLE:
                    gym_menu()
                else:
                    print("\n❌ Gym CLI is not available")
                    input("Press Enter to continue...")
            elif option == "dentist":
                if DENTIST_AVAILABLE:
                    dentist_menu()
                else:
                    print("\n❌ Dentist CLI is not available")
                    input("Press Enter to continue...")
            elif option == "todo":
                if TODO_AVAILABLE:
                    todo_menu()
                else:
                    print("\n❌ To-Do List CLI is not available")
                    input("Press Enter to continue...")
            elif option == "administrative_tools":
                display_administrative_tools_menu(auth)
            elif option == "security_dashboard":
                if SECURITY_DASHBOARD_CLI_AVAILABLE:
                    # Check if user is admin
                    if auth.current_user and auth.current_user.get('role') == 'admin':
                        user_id = auth.current_user.get('id', 1)
                        display_security_dashboard_menu(user_id)
                    else:
                        print("\n❌ Access Denied: Administrator access required for Security Dashboard")
                        input("Press Enter to continue...")
                else:
                    print("\n❌ Security Dashboard is not available")
                    input("Press Enter to continue...")
            elif option == "data_document_management":
                display_data_document_management_menu(auth)
            elif option == "ai_features":
                display_ai_features_menu(auth)
            elif option == "business_intelligence":
                display_business_intelligence_menu(auth)
            elif option == "integration_marketplace":
                display_integration_marketplace_menu(auth)
            elif option == "blockchain_credentials":
                display_blockchain_credentials_menu(auth)
            elif option == "pdf_database_export":
                display_pdf_export_menu(auth)
            elif option == "authentication":
                display_auth_menu(auth)
            elif option == "mobile_app_pwa":
                display_mobile_app_pwa_menu(auth)
            elif option == "system_monitoring":
                display_system_monitoring_menu(auth)
            elif option == "switch_to_gui":
                switch_to_gui(auth)
            elif option == "switch_system":
                try:
                    from education_system import switch as _switch
                    from education_system.launcher.system_switch import pick_system_cli
                    target = pick_system_cli(
                        auth.current_user if auth else None, "university")
                    if target:
                        _switch.request_switch(target, "cli")
                        return  # exits main menu loop; dispatcher takes over
                except Exception as e:
                    print(f"\n  ✗ Could not switch system: {e}")
                    input("Press Enter to continue...")
            elif option == "change_language":
                display_language_menu_option()
            elif option == "hesa_export":
                try:
                    from education_system.post_18.university_system.modules.domain.admissions.hesa_export.cli.hesa_export_cli import display_hesa_export_menu
                    display_hesa_export_menu(auth)
                except ImportError as e:
                    print(f"\n❌ HESA Export CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "external_examiners":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.external_examiners.cli.external_examiner_cli import display_external_examiner_menu
                    display_external_examiner_menu(auth)
                except ImportError as e:
                    print(f"\n❌ External Examiners CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "external_qa":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.research.external_quality_assurance.cli.eqa_cli import display_external_qa_menu
                    display_external_qa_menu(auth)
                except ImportError as e:
                    print(f"\n❌ External QA CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "mitigating_circumstances":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.mitigating_circumstances.cli.mitigating_circumstances_cli import display_mitigating_circumstances_menu
                    display_mitigating_circumstances_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Mitigating Circumstances CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "curriculum_specification":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.curriculum_specification.cli.curriculum_specification_cli import display_curriculum_specification_menu
                    display_curriculum_specification_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Curriculum Specification CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_app":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.student_app.cli.student_app_cli import display_student_app_menu
                    display_student_app_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Student App CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "enrolment_letters":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.student_app.documentation.cli.documentation_cli import display_documentation_menu
                    display_documentation_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Status Letters CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "achievement_badges":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.achievement_badges.cli.achievement_badge_cli import display_achievement_badge_menu
                    display_achievement_badge_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Achievement Badges CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "study_recommendations":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.study_recommendations.cli.study_recommendation_cli import display_study_recommendation_menu
                    display_study_recommendation_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Study Recommendations CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "clearing_adjustment":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.clearing_adjustment.cli.clearing_adjustment_cli import display_clearing_adjustment_menu
                    display_clearing_adjustment_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Clearing & Adjustment CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "prior_learning":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.prior_learning_recognition.cli.prior_learning_cli import display_prior_learning_menu
                    display_prior_learning_menu(auth)
                except ImportError as e:
                    print(f"\n❌ APL/RPL CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "course_planning":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.course_planning.cli.planning_cli import main as course_planning_main
                    course_planning_main()
                except ImportError as e:
                    print(f"\n  Course Planning CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "lesson_planner":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.course_planning.cli import run_lesson_planner_menu
                    run_lesson_planner_menu(auth)
                except Exception as e:
                    print(f"\n  Lesson Planner CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "apprenticeships":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.apprenticeships.cli import run_apprenticeships_menu
                    run_apprenticeships_menu(auth)
                except Exception as e:
                    print(f"\n  Apprenticeships CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "placements":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.placements.cli import run_placements_menu
                    run_placements_menu(auth)
                except Exception as e:
                    print(f"\n  Placements CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "bakery_shop":
                try:
                    from education_system.post_18.university_system.modules.domain.commerce.bakery_shop.cli import run_bakery_menu
                    run_bakery_menu(auth)
                except Exception as e:
                    print(f"\n  Bakery Shop CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "bank_rec":
                try:
                    from education_system.post_18.university_system.modules.domain.finance.bank_rec.cli import run_bank_rec_menu
                    run_bank_rec_menu(auth)
                except Exception as e:
                    print(f"\n  Bank Reconciliation CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "ledger":
                try:
                    from education_system.post_18.university_system.modules.domain.finance.ledger.cli import run_ledger_menu
                    run_ledger_menu(auth)
                except Exception as e:
                    print(f"\n  Ledger CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "statements":
                try:
                    from education_system.post_18.university_system.modules.domain.finance.statements.cli import run_statements_menu
                    run_statements_menu(auth)
                except Exception as e:
                    print(f"\n  Statements CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "first_aid":
                try:
                    from education_system.post_18.university_system.modules.domain.health.first_aid.cli import run_first_aid_menu
                    run_first_aid_menu(auth)
                except Exception as e:
                    print(f"\n  First Aid CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "health_safety":
                try:
                    from education_system.post_18.university_system.modules.domain.health.health_safety.cli import run_health_safety_menu
                    run_health_safety_menu(auth)
                except Exception as e:
                    print(f"\n  Health & Safety CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "advising":
                try:
                    from education_system.post_18.university_system.modules.domain.academics.advising.cli.advising_cli import main as advising_main
                    advising_main()
                except ImportError as e:
                    print(f"\n  Advising CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_wellbeing":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.student_wellbeing.cli.student_wellbeing_cli import main as wellbeing_main
                    wellbeing_main()
                except ImportError as e:
                    print(f"\n  Student Wellbeing CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_finance":
                # Student Finance merged into the main Finance CLI/GUI.
                try:
                    from education_system.post_18.university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI
                    import tkinter as tk
                    FinanceGUI(tk.Tk())
                except Exception as e:
                    print(f"\n  Finance GUI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_id_card":
                try:
                    from education_system.post_18.university_system.modules.domain.student_affairs.student_id.cli.student_id_cli import main as student_id_main
                    student_id_main()
                except ImportError as e:
                    print(f"\n  Student ID CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "printing":
                try:
                    from education_system.post_18.university_system.modules.domain.campus.printing.cli.printing_cli import main as printing_main
                    printing_main()
                except ImportError as e:
                    print(f"\n  Printing CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "study_rooms":
                try:
                    from education_system.post_18.university_system.modules.domain.campus.study_rooms.cli.study_rooms_cli import main as study_rooms_main
                    study_rooms_main()
                except ImportError as e:
                    print(f"\n  Study Rooms CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "textbooks":
                try:
                    from education_system.post_18.university_system.modules.domain.commerce.textbooks.cli.textbooks_cli import main as textbooks_main
                    textbooks_main()
                except ImportError as e:
                    print(f"\n  Textbooks CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option.startswith("cross_"):
                _handle_cross_system_tool(option, auth)
            elif option.startswith("nf_"):
                _dispatch_new_feature(option, auth)
            elif option == "logout":
                cleanup_database_connections()
                auth.logout()
            elif option == "exit":
                cleanup_database_connections()
                if auth and auth.current_user:
                    auth.logout()
                # Request a clean shutdown so even a superadmin is not bounced
                # back to the superadmin dashboard by the dispatcher.
                from education_system.switch import request_exit
                request_exit()
                print(f"\n{get_text('cli.goodbye', default='Thank you for using the University Management System. Goodbye!')}")
                return
            else:
                print(get_text('cli.invalid_choice', default='Invalid choice. Please try again.'))
        else:
            print(get_text('cli.invalid_choice', default='Invalid choice. Please try again.'))


_NEW_FEATURE_CLI_DISPATCH = {
    "nf_employer_portal": (
        "education_system.post_18.university_system.modules.domain.student_affairs."
        "employer_portal.cli.employer_portal_cli",
        "display_employer_portal_menu",
    ),
    "nf_intervention_outcomes": (
        "education_system.post_18.university_system.modules.domain.student_affairs."
        "services.early_warning.outcomes.intervention_outcomes_cli",
        "display_intervention_outcomes_menu",
    ),
    "nf_kpi_dashboard": (
        "education_system.post_18.university_system.modules.domain.analytics."
        "kpi_dashboard.cli.kpi_dashboard_cli",
        "display_kpi_dashboard_menu",
    ),
    "nf_institutional_analytics": (
        "education_system.post_18.university_system.modules.domain.analytics."
        "institutional_analytics.cli.institutional_analytics_cli",
        "display_institutional_analytics_menu",
    ),
    "nf_bursary": (
        "education_system.post_18.university_system.modules.domain.finance."
        "bursary.cli.bursary_cli",
        "display_bursary_menu",
    ),
    "nf_mentoring_matching": (
        "education_system.post_18.university_system.modules.domain.student_affairs."
        "student_union.services.mentoring_matching.cli.matching_cli",
        "display_mentoring_matching_menu",
    ),
    "nf_room_booking": (
        "education_system.post_18.university_system.modules.domain.campus."
        "room_booking.cli.room_booking_cli",
        "display_room_booking_menu",
    ),
    "nf_tutor_groups": (
        "education_system.post_18.university_system.modules.domain.academics."
        "tutor_groups.cli.tutor_group_cli",
        "display_tutor_group_menu",
    ),
}


def _dispatch_new_feature(option, auth):
    """Resolve a new-feature option key to its CLI menu and run it."""
    target = _NEW_FEATURE_CLI_DISPATCH.get(option)
    if not target:
        print(f"\n  Unknown new feature: {option}")
        input("Press Enter to continue...")
        return
    module_path, fn_name = target
    try:
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "set_auth"):
            mod.set_auth(auth)
        fn = getattr(mod, fn_name)
        fn()
    except Exception as e:
        print(f"\n  Failed to launch new feature ({option}): {e}")
        input("Press Enter to continue...")


def _vc_schedule_session(auth):
    """Schedule a virtual session sub-menu"""
    print("\n--- Schedule Virtual Session ---")
    print("1. Create new session")
    print("2. View upcoming sessions")
    print("3. List sessions by classroom")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        sm = SessionManager()
        if sub == '1':
            classroom_id = int(input("Enter classroom ID: ").strip())
            start_time_str = input("Enter start time (YYYY-MM-DD HH:MM): ").strip()
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            session_type = input("Session type (lecture/lab/office_hours) [lecture]: ").strip() or "lecture"
            duration = int(input("Duration in minutes [60]: ").strip() or "60")
            notes = input("Notes (optional): ").strip() or None
            session_id = sm.create_session(
                classroom_id=classroom_id, start_time=start_time,
                session_type=session_type, duration_minutes=duration, notes=notes
            )
            if session_id:
                print(f"✅ Session created! Session ID: {session_id}")
            else:
                print("❌ Failed to create session.")
        elif sub == '2':
            classroom_id_str = input("Classroom ID (or Enter for all): ").strip()
            classroom_id = int(classroom_id_str) if classroom_id_str else None
            sessions = sm.get_upcoming_sessions(classroom_id=classroom_id)
            if sessions:
                for s in sessions:
                    print(f"  ID: {s['id']}, Start: {s.get('start_time', 'N/A')}, Type: {s.get('session_type', 'N/A')}, Status: {s.get('status', 'N/A')}")
            else:
                print("No upcoming sessions found.")
        elif sub == '3':
            classroom_id = int(input("Enter classroom ID: ").strip())
            sessions = sm.get_sessions_by_classroom(classroom_id)
            if sessions:
                for s in sessions:
                    print(f"  ID: {s['id']}, Start: {s.get('start_time', 'N/A')}, Type: {s.get('session_type', 'N/A')}, Status: {s.get('status', 'N/A')}")
            else:
                print("No sessions found for this classroom.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_manage_participants(auth):
    """Manage participants sub-menu"""
    print("\n--- Manage Participants ---")
    print("1. Join a session")
    print("2. View session participants")
    print("3. View attendance history")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        pm = ParticipantManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            user_id = auth.current_user['user_id']
            user_type = auth.current_user.get('role', 'student')
            device = input("Device type (desktop/mobile/tablet) [desktop]: ").strip() or "desktop"
            pid = pm.add_participant(
                session_id=session_id, user_id=user_id,
                user_type=user_type, device_type=device
            )
            if pid:
                print(f"✅ Joined session! Participant ID: {pid}")
            else:
                print("❌ Failed to join session.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            participants = pm.get_session_participants(session_id)
            if participants:
                for p in participants:
                    print(f"  User ID: {p.get('user_id')}, Type: {p.get('user_type')}, Status: {p.get('attendance_status', 'N/A')}")
            else:
                print("No participants found.")
        elif sub == '3':
            user_id_str = input("Enter user ID (or Enter for yourself): ").strip()
            user_id = int(user_id_str) if user_id_str else auth.current_user['user_id']
            history = pm.get_user_attendance_history(user_id)
            if history:
                for h in history:
                    print(f"  Session: {h.get('session_id')}, Status: {h.get('attendance_status', 'N/A')}, Joined: {h.get('join_time', 'N/A')}")
            else:
                print("No attendance history found.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_view_recordings(auth):
    """View recordings sub-menu"""
    print("\n--- View Recordings ---")
    print("1. List recordings by classroom")
    print("2. View recording details")
    print("3. View storage usage")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        rm = RecordingManager()
        if sub == '1':
            classroom_id = int(input("Enter classroom ID: ").strip())
            recordings = rm.get_recordings_by_classroom(classroom_id)
            if recordings:
                for r in recordings:
                    print(f"  ID: {r['id']}, File: {r.get('file_name', 'N/A')}, Duration: {r.get('duration', 'N/A')}s, Views: {r.get('view_count', 0)}")
            else:
                print("No recordings found.")
        elif sub == '2':
            recording_id = int(input("Enter recording ID: ").strip())
            rec = rm.get_recording(recording_id)
            if rec:
                for k, v in rec.items():
                    print(f"  {k}: {v}")
            else:
                print("Recording not found.")
        elif sub == '3':
            classroom_id_str = input("Classroom ID (or Enter for all): ").strip()
            classroom_id = int(classroom_id_str) if classroom_id_str else None
            usage = rm.get_storage_usage(classroom_id=classroom_id)
            for k, v in usage.items():
                print(f"  {k}: {v}")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_create_polls(auth):
    """Create polls/quizzes sub-menu"""
    print("\n--- Polls & Quizzes ---")
    print("1. Create a poll")
    print("2. View session polls")
    print("3. View poll results")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        plm = PollManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            question = input("Enter poll question: ").strip()
            poll_type = input("Poll type (multiple_choice/true_false/open_ended) [multiple_choice]: ").strip() or "multiple_choice"
            options = None
            if poll_type in ('multiple_choice', 'true_false'):
                options_str = input("Enter options (comma-separated): ").strip()
                options = [o.strip() for o in options_str.split(',') if o.strip()]
            correct_answer = input("Correct answer (optional): ").strip() or None
            time_limit_str = input("Time limit in seconds (optional): ").strip()
            time_limit = int(time_limit_str) if time_limit_str else None
            poll_id = plm.create_poll(
                session_id=session_id, question=question,
                created_by=auth.current_user['user_id'],
                poll_type=poll_type, options=options,
                correct_answer=correct_answer, time_limit=time_limit
            )
            if poll_id:
                print(f"✅ Poll created! Poll ID: {poll_id}")
            else:
                print("❌ Failed to create poll.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            polls = plm.get_session_polls(session_id)
            if polls:
                for p in polls:
                    print(f"  ID: {p['id']}, Question: {p.get('question', 'N/A')}, Type: {p.get('poll_type', 'N/A')}, Status: {p.get('status', 'N/A')}")
            else:
                print("No polls found for this session.")
        elif sub == '3':
            poll_id = int(input("Enter poll ID: ").strip())
            results = plm.get_poll_results(poll_id)
            for k, v in results.items():
                print(f"  {k}: {v}")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_manage_breakout_rooms(auth):
    """Manage breakout rooms sub-menu"""
    print("\n--- Breakout Rooms ---")
    print("1. Create breakout room")
    print("2. View session rooms")
    print("3. Start a room")
    print("4. End a room")
    print("5. Return")
    sub = input("Choice: ").strip()
    try:
        brm = BreakoutRoomManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            room_name = input("Enter room name: ").strip()
            room_number = int(input("Enter room number: ").strip())
            participants_str = input("Enter participant user IDs (comma-separated): ").strip()
            participants = [int(p.strip()) for p in participants_str.split(',') if p.strip()]
            topic = input("Topic (optional): ").strip() or None
            duration = int(input("Duration in minutes [15]: ").strip() or "15")
            room_id = brm.create_breakout_room(
                session_id=session_id, room_name=room_name,
                room_number=room_number, participants=participants,
                topic=topic, duration_minutes=duration
            )
            if room_id:
                print(f"✅ Breakout room created! Room ID: {room_id}")
            else:
                print("❌ Failed to create breakout room.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            rooms = brm.get_session_breakout_rooms(session_id)
            if rooms:
                for r in rooms:
                    print(f"  ID: {r['id']}, Name: {r.get('room_name', 'N/A')}, Status: {r.get('status', 'N/A')}, Topic: {r.get('topic', 'N/A')}")
            else:
                print("No breakout rooms found.")
        elif sub == '3':
            room_id = int(input("Enter room ID to start: ").strip())
            if brm.start_breakout_room(room_id):
                print("✅ Breakout room started!")
            else:
                print("❌ Failed to start breakout room.")
        elif sub == '4':
            room_id = int(input("Enter room ID to end: ").strip())
            if brm.end_breakout_room(room_id):
                print("✅ Breakout room ended!")
            else:
                print("❌ Failed to end breakout room.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_view_chat(auth):
    """View chat messages sub-menu"""
    print("\n--- Chat Messages ---")
    print("1. View session messages")
    print("2. Search messages")
    print("3. Chat statistics")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        cm = ChatManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            limit = int(input("Number of messages to show [50]: ").strip() or "50")
            messages = cm.get_session_messages(session_id, limit=limit)
            if messages:
                for m in messages:
                    print(f"  [{m.get('timestamp', '')}] {m.get('user_name', 'Unknown')}: {m.get('message_text', '')}")
            else:
                print("No messages found.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            search_term = input("Search term: ").strip()
            results = cm.search_messages(session_id, search_term)
            if results:
                for m in results:
                    print(f"  [{m.get('timestamp', '')}] {m.get('user_name', 'Unknown')}: {m.get('message_text', '')}")
            else:
                print("No matching messages found.")
        elif sub == '3':
            session_id = int(input("Enter session ID: ").strip())
            stats = cm.get_chat_statistics(session_id)
            for k, v in stats.items():
                print(f"  {k}: {v}")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _vc_session_analytics(auth):
    """Session analytics sub-menu"""
    print("\n--- Session Analytics ---")
    print("1. View session statistics")
    print("2. Classroom overview")
    print("3. Return")
    sub = input("Choice: ").strip()
    try:
        if sub == '1':
            sm = SessionManager()
            session_id = int(input("Enter session ID: ").strip())
            stats = sm.get_session_statistics(session_id)
            if stats:
                for k, v in stats.items():
                    print(f"  {k}: {v}")
            else:
                print("No statistics available for this session.")
        elif sub == '2':
            vcm = VirtualClassroomManager()
            classroom_id = int(input("Enter classroom ID: ").strip())
            classroom = vcm.get_classroom(classroom_id)
            if classroom:
                for k, v in classroom.items():
                    print(f"  {k}: {v}")
            else:
                print("Classroom not found.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def display_virtual_classroom_menu(auth):
    """Display the virtual classroom management CLI menu"""
    print("\n" + "="*50)
    print(f"      {get_text('virtual.title', default='VIRTUAL CLASSROOM MANAGEMENT')}")
    print("="*50)
    print(f"1. {get_text('virtual.menu.create_classroom', default='Create Virtual Classroom')}")
    print(f"2. {get_text('virtual.menu.schedule_session', default='Schedule Virtual Session')}")
    print(f"3. {get_text('virtual.menu.manage_participants', default='Manage Participants')}")
    print(f"4. {get_text('virtual.menu.view_recordings', default='View Recordings')}")
    print(f"5. {get_text('virtual.menu.create_polls', default='Create Polls/Quizzes')}")
    print(f"6. {get_text('virtual.menu.breakout_rooms', default='Manage Breakout Rooms')}")
    print(f"7. {get_text('virtual.menu.view_chat', default='View Chat Messages')}")
    print(f"8. {get_text('virtual.menu.analytics', default='Session Analytics')}")
    print(f"9. {get_text('virtual.menu.language', default='Language')}")
    print(f"10. {get_text('virtual.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('virtual.prompt.choice', default='Enter your choice (1-10)')}: ").strip()

            if choice == '1':
                # Create Virtual Classroom
                try:
                    session_name = input(get_text('virtual.prompt.session_name', default='Enter session name: ')).strip()
                    platform = input(get_text('virtual.prompt.platform', default='Enter platform (zoom/teams/meet/webrtc): ')).strip()
                    meeting_link = input(get_text('virtual.prompt.meeting_link', default='Enter meeting link: ')).strip()

                    classroom_mgr = VirtualClassroomManager()
                    classroom_id = classroom_mgr.create_classroom(
                        session_name=session_name,
                        instructor_id=auth.current_user['user_id'],
                        platform=platform,
                        meeting_link=meeting_link
                    )
                    print(get_text('virtual.success.created', default='Virtual classroom created successfully! Classroom ID: {id}').format(id=classroom_id))
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(get_text('virtual.error.creating', default='Error creating classroom: {error}').format(error=e))
            elif choice == '2':
                _vc_schedule_session(auth)
            elif choice == '3':
                _vc_manage_participants(auth)
            elif choice == '4':
                _vc_view_recordings(auth)
            elif choice == '5':
                _vc_create_polls(auth)
            elif choice == '6':
                _vc_manage_breakout_rooms(auth)
            elif choice == '7':
                _vc_view_chat(auth)
            elif choice == '8':
                _vc_session_analytics(auth)
            elif choice == '9':
                display_language_menu_option()
            elif choice == '10':
                print(get_text('virtual.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('virtual.invalid_choice', default='Invalid choice. Please enter a number between 1 and 10.'))

        except KeyboardInterrupt:
            print(get_text('virtual.exiting', default='\n\nExiting virtual classroom menu...'))
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(get_text('virtual.error', default='Error: {error}').format(error=e))


def _finaid_manage_scholarships(auth):
    """Manage scholarships sub-menu"""
    from education_system.post_18.university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
    print("\n--- Manage Scholarships ---")
    print("1. Create scholarship")
    print("2. View available scholarships")
    print("3. Submit scholarship application")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        sm = ScholarshipManager()
        if sub == '1':
            name = input("Scholarship name: ").strip()
            amount = float(input("Amount: ").strip())
            scholarship_type = input("Type (merit/need/athletic/departmental) [merit]: ").strip() or "merit"
            description = input("Description (optional): ").strip() or None
            min_gpa_str = input("Minimum GPA (optional): ").strip()
            min_gpa = float(min_gpa_str) if min_gpa_str else None
            deadline_str = input("Deadline (YYYY-MM-DD, optional): ").strip()
            deadline = None
            if deadline_str:
                from datetime import date as _date
                deadline = _date.fromisoformat(deadline_str)
            sid = sm.create_scholarship(
                name=name, amount=amount, scholarship_type=scholarship_type,
                description=description, min_gpa=min_gpa, deadline=deadline
            )
            if sid:
                print(f"✅ Scholarship created! ID: {sid}")
            else:
                print("❌ Failed to create scholarship.")
        elif sub == '2':
            scholarships = sm.get_available_scholarships()
            if scholarships:
                for s in scholarships:
                    print(f"  ID: {s['id']}, Name: {s.get('name', 'N/A')}, Amount: £{s.get('amount', 0):.2f}, Type: {s.get('scholarship_type', 'N/A')}")
            else:
                print("No scholarships available.")
        elif sub == '3':
            scholarship_id = int(input("Scholarship ID: ").strip())
            student_id = int(input("Student ID: ").strip())
            essay = input("Essay text (optional): ").strip() or None
            gpa_str = input("GPA (optional): ").strip()
            gpa = float(gpa_str) if gpa_str else None
            app_id = sm.submit_application(
                scholarship_id=scholarship_id, student_id=student_id,
                essay_text=essay, gpa=gpa
            )
            if app_id:
                print(f"✅ Application submitted! Application ID: {app_id}")
            else:
                print("❌ Failed to submit application.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def _finaid_disbursement_management(auth):
    """Disbursement management sub-menu"""
    print("\n--- Disbursement Management ---")
    print("1. Create disbursement")
    print("2. View pending disbursements")
    print("3. Process disbursement")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        aid_mgr = FinancialAidManager()
        if sub == '1':
            student_id = int(input("Student ID: ").strip())
            amount = float(input("Amount: ").strip())
            from datetime import date as _date
            date_str = input("Disbursement date (YYYY-MM-DD): ").strip()
            disb_date = _date.fromisoformat(date_str)
            disb_type = input("Type (tuition/housing/books/stipend): ").strip()
            term = input("Academic term (e.g., Fall 2025): ").strip()
            did = aid_mgr.create_disbursement(
                student_id=student_id, amount=amount,
                disbursement_date=disb_date, disbursement_type=disb_type,
                academic_term=term
            )
            if did:
                print(f"✅ Disbursement created! ID: {did}")
            else:
                print("❌ Failed to create disbursement.")
        elif sub == '2':
            term = input("Academic term (or Enter for all): ").strip() or None
            pending = aid_mgr.get_pending_disbursements(academic_term=term)
            if pending:
                for d in pending:
                    print(f"  ID: {d['id']}, Student: {d.get('student_id')}, Amount: £{d.get('amount', 0):.2f}, Type: {d.get('disbursement_type', 'N/A')}")
            else:
                print("No pending disbursements.")
        elif sub == '3':
            disb_id = int(input("Disbursement ID: ").strip())
            processed_by = auth.current_user['user_id']
            txn_id = input("Transaction ID (optional): ").strip() or None
            if aid_mgr.process_disbursement(disb_id, processed_by=processed_by, transaction_id=txn_id):
                print("✅ Disbursement processed successfully!")
            else:
                print("❌ Failed to process disbursement.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")


def display_financial_aid_menu(auth):
    """Display the financial aid & scholarships CLI menu"""
    print("\n" + "="*50)
    print(f"    {get_text('finaid.title', default='FINANCIAL AID & SCHOLARSHIP MANAGEMENT')}")
    print("="*50)
    print(f"1. {get_text('finaid.menu.view_applications', default='View Financial Aid Applications')}")
    print(f"2. {get_text('finaid.menu.submit_fafsa', default='Submit FAFSA Data')}")
    print(f"3. {get_text('finaid.menu.create_package', default='Create Aid Package')}")
    print(f"4. {get_text('finaid.menu.manage_scholarships', default='Manage Scholarships')}")
    print(f"5. {get_text('finaid.menu.review_applications', default='Review Scholarship Applications')}")
    print(f"6. {get_text('finaid.menu.award_scholarship', default='Award Scholarship')}")
    print(f"7. {get_text('finaid.menu.disbursement', default='Disbursement Management')}")
    print(f"8. {get_text('finaid.menu.compliance', default='Compliance Reports')}")
    print(f"9. {get_text('finaid.menu.language', default='Language')}")
    print(f"10. {get_text('finaid.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('finaid.prompt.choice', default='Enter your choice (1-10)')}: ").strip()

            if choice == '1':
                # View Financial Aid Applications
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    aid_mgr = FinancialAidManager()
                    package = aid_mgr.get_aid_package(student_id, academic_year)
                    if package:
                        print(f"\n--- Aid Package for Student {student_id} ({academic_year}) ---")
                        for k, v in package.items():
                            print(f"  {k}: {v}")
                    else:
                        fafsa = aid_mgr.get_fafsa_data(student_id, academic_year)
                        if fafsa:
                            print(f"\n--- FAFSA Data for Student {student_id} ({academic_year}) ---")
                            for k, v in fafsa.items():
                                print(f"  {k}: {v}")
                        else:
                            print("No financial aid data found for this student and academic year.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.applications', default='Error viewing applications: {error}').format(error=e))
            elif choice == '2':
                # Submit FAFSA Data
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    efc = float(input(get_text('finaid.prompt.efc', default="Enter Expected Family Contribution (EFC): ")).strip())

                    aid_mgr = FinancialAidManager()
                    from datetime import date
                    aid_mgr.import_fafsa_data(
                        student_id=student_id,
                        academic_year=academic_year,
                        efc=efc,
                        submission_date=date.today()
                    )
                    print(get_text('finaid.success.fafsa', default='FAFSA data imported successfully!'))
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.fafsa', default='Error importing FAFSA data: {error}').format(error=e))
            elif choice == '3':
                # Create Aid Package
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    aid_mgr = FinancialAidManager()
                    pkg_id = aid_mgr.create_aid_package(
                        student_id=student_id, academic_year=academic_year,
                        created_by=auth.current_user['user_id']
                    )
                    if pkg_id:
                        print(f"✅ Aid package created! Package ID: {pkg_id}")
                        add_component = input("Add a component now? (y/n): ").strip().lower()
                        while add_component == 'y':
                            aid_type = input("Aid type (grant/loan/scholarship/work_study): ").strip()
                            name = input("Component name: ").strip()
                            amount = float(input("Amount: ").strip())
                            source = input("Source (federal/state/institutional) [institutional]: ").strip() or "institutional"
                            comp_id = aid_mgr.add_aid_component(
                                package_id=pkg_id, aid_type=aid_type,
                                name=name, amount=amount, source=source
                            )
                            if comp_id:
                                print(f"✅ Component added! Component ID: {comp_id}")
                            else:
                                print("❌ Failed to add component.")
                            add_component = input("Add another component? (y/n): ").strip().lower()
                    else:
                        print("❌ Failed to create aid package.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.package', default='Error creating aid package: {error}').format(error=e))
            elif choice == '4':
                _finaid_manage_scholarships(auth)
            elif choice == '5':
                # Review Scholarship Applications
                try:
                    from education_system.post_18.university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    app_id = int(input("Enter application ID: ").strip())
                    status = input("Decision (approved/denied/waitlisted): ").strip()
                    score_str = input("Review score (0-100, optional): ").strip()
                    score = float(score_str) if score_str else None
                    comments = input("Review comments (optional): ").strip() or None
                    sm = ScholarshipManager()
                    if sm.review_application(
                        app_id=app_id, reviewer_id=auth.current_user['user_id'],
                        status=status, review_score=score, review_comments=comments
                    ):
                        print("✅ Application reviewed successfully!")
                    else:
                        print("❌ Failed to review application.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.review', default='Error reviewing application: {error}').format(error=e))
            elif choice == '6':
                # Award Scholarship
                try:
                    from education_system.post_18.university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    scholarship_id = int(input("Enter scholarship ID: ").strip())
                    student_id = int(input("Enter student ID: ").strip())
                    academic_year = input("Academic year (e.g., 2024-2025): ").strip()
                    amount = float(input("Award amount: ").strip())
                    renewable_str = input("Is renewable? (y/n) [n]: ").strip().lower()
                    is_renewable = renewable_str == 'y'
                    sm = ScholarshipManager()
                    award_id = sm.award_scholarship(
                        scholarship_id=scholarship_id, student_id=student_id,
                        academic_year=academic_year, amount=amount,
                        is_renewable=is_renewable
                    )
                    if award_id:
                        print(f"✅ Scholarship awarded! Award ID: {award_id}")
                    else:
                        print("❌ Failed to award scholarship.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.award', default='Error awarding scholarship: {error}').format(error=e))
            elif choice == '7':
                _finaid_disbursement_management(auth)
            elif choice == '8':
                # Compliance Reports
                try:
                    from education_system.post_18.university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    student_id = int(input("Enter student ID: ").strip())
                    sm = ScholarshipManager()
                    awards = sm.get_student_awards(student_id)
                    if awards:
                        print(f"\n--- Scholarship Awards for Student {student_id} ---")
                        for a in awards:
                            print(f"  ID: {a.get('id', 'N/A')}, Name: {a.get('scholarship_name', a.get('name', 'N/A'))}, Amount: £{a.get('amount', 0):.2f}, Year: {a.get('academic_year', 'N/A')}")
                    else:
                        print("No scholarship awards found.")
                    aid_mgr = FinancialAidManager()
                    pending = aid_mgr.get_pending_disbursements()
                    if pending:
                        print("\n--- Pending Disbursements ---")
                        for d in pending:
                            print(f"  ID: {d['id']}, Student: {d.get('student_id')}, Amount: £{d.get('amount', 0):.2f}, Type: {d.get('disbursement_type', 'N/A')}")
                    else:
                        print("No pending disbursements.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.compliance', default='Error generating compliance report: {error}').format(error=e))
            elif choice == '9':
                display_language_menu_option()
            elif choice == '10':
                print(get_text('finaid.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('finaid.invalid_choice', default='Invalid choice. Please enter a number between 1 and 10.'))

        except KeyboardInterrupt:
            print(get_text('finaid.exiting', default='\n\nExiting financial aid menu...'))
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(get_text('finaid.error', default='Error: {error}').format(error=e))


def display_communication_hub_menu(auth):
    """Display the unified communication hub CLI menu with all options"""
    from education_system.post_18.university_system.infrastructure.email.config import config
    from education_system.post_18.university_system.infrastructure.email.admin import CommunicationDashboard
    from education_system.post_18.university_system.modules.shared.services.communication.communication_manager import CommunicationManager
    from education_system.post_18.university_system.core.logs import LOG_MANAGEMENT_AVAILABLE

    # Initialize dashboard for advanced features
    dashboard = CommunicationDashboard(auth=auth)
    is_admin = auth and auth.current_user and auth.current_user.get('role') == 'admin'

    print("\n" + "="*100)
    print("       UNIFIED COMMUNICATION HUB")
    print("="*100)

    print("\n📧 Quick Actions:")
    print(f"{'1.  Send Email':<25} {'2.  Send SMS':<25} {'3.  Push Notification':<25}")

    print("\n📢 Announcements & Messages:")
    print(f"{'4.  Messages Mgmt':<25} {'5.  Create Announcement':<25} {'6.  Manage Announcements':<25} {'7.  Batch Announcement':<25}")

    print("\n💬 Chat & Communication:")
    print(f"{'8.  Chat Rooms':<25} {'9.  Notification Prefs':<25}")

    print("\n⚙️ Email System Configuration:")
    print(f"{'10. Email Settings':<25} {'11. Test Configuration':<25} {'12. Email Templates':<25} {'13. Schedule Emails':<25}")
    print(f"{'14. Queue Status':<25} {'15. Stored Emails':<25}")

    print("\n🌐 Cross-System:")
    print(f"{'C.  Cross-System Messages':<25}")

    print("\n📊 Reports & Analytics:")
    print(f"{'16. Email Reports':<25}", end="")
    if LOG_MANAGEMENT_AVAILABLE:
        print(f" {'17. Activity Logs':<25}", end="")
        if is_admin:
            print(f" {'18. Analytics':<25}", end="")
    print()

    if is_admin:
        print("\n🔧 Administration:")
        print(f"{'19. Admin Messages':<25}")

    print("\n↩️ Navigation:")
    if is_admin and LOG_MANAGEMENT_AVAILABLE:
        print("20. Return to Main Menu")
        max_choice = 20
    elif is_admin or LOG_MANAGEMENT_AVAILABLE:
        print("19. Return to Main Menu")
        max_choice = 19
    else:
        print("17. Return to Main Menu")
        max_choice = 17
    print("="*100)

    while True:
        try:
            choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

            if choice == '1':
                # Send Email
                try:
                    to_address = input("Enter recipient email: ").strip()
                    subject = input("Enter subject: ").strip()
                    body = input("Enter message body: ").strip()

                    comm_mgr = CommunicationManager()
                    email_id = comm_mgr.queue_email(
                        to_address=to_address,
                        subject=subject,
                        body=body,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ Email queued successfully! Email ID: {email_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error queuing email: {e}")
            elif choice == '2':
                # Send SMS
                try:
                    phone_number = input("Enter phone number: ").strip()
                    message = input("Enter message: ").strip()

                    comm_mgr = CommunicationManager()
                    sms_id = comm_mgr.queue_sms(
                        phone_number=phone_number,
                        message=message,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ SMS queued successfully! SMS ID: {sms_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error queuing SMS: {e}")
            elif choice == '3':
                # Send Push Notification
                try:
                    user_id = int(input("Enter recipient user ID: ").strip())
                    title = input("Enter notification title: ").strip()
                    body = input("Enter notification body: ").strip()
                    click_action = input("Enter click action URL (or press Enter to skip): ").strip() or None
                    comm_mgr = CommunicationManager()
                    notif_id = comm_mgr.send_push_notification(
                        user_id=user_id, title=title, body=body, click_action=click_action
                    )
                    if notif_id:
                        print(f"✅ Push notification sent! Notification ID: {notif_id}")
                    else:
                        print("❌ Failed to send push notification.")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error sending push notification: {e}")
            elif choice == '4':
                # Messages Management
                from education_system.post_18.university_system.infrastructure.email.admin import display_messages_menu
                display_messages_menu(dashboard)
            elif choice == '5':
                # Create Announcement
                try:
                    title = input("Enter announcement title: ").strip()
                    content = input("Enter announcement content: ").strip()
                    target_audience = input("Enter target audience (all/students/faculty/staff): ").strip()

                    comm_mgr = CommunicationManager()
                    announcement_id = comm_mgr.create_announcement(
                        title=title,
                        content=content,
                        target_audience=target_audience,
                        created_by=auth.current_user['user_id']
                    )
                    print(f"✅ Announcement created successfully! Announcement ID: {announcement_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error creating announcement: {e}")
            elif choice == '6':
                # Manage Announcements
                from education_system.post_18.university_system.infrastructure.email.admin import display_announcements_menu
                display_announcements_menu(dashboard)
            elif choice == '7':
                # Send Batch Announcement
                from education_system.post_18.university_system.infrastructure.email.email_service import send_batch_email_form
                send_batch_email_form()
            elif choice == '8':
                # Chat Rooms
                from education_system.post_18.university_system.infrastructure.email.admin import display_chat_rooms_menu
                display_chat_rooms_menu(dashboard)
            elif choice == '9':
                # Notification Preferences
                from education_system.post_18.university_system.infrastructure.email.admin import display_preferences_menu
                display_preferences_menu(dashboard)
            elif choice == '10':
                # Configure Email Settings
                from education_system.post_18.university_system.infrastructure.email.config import configure_email_settings
                configure_email_settings()
            elif choice == '11':
                # Test Email Configuration
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                recipient = input("Enter test recipient email (or press Enter to use your email): ").strip()
                if not recipient and auth.current_user:
                    recipient = auth.current_user.get('email', '')
                if recipient:
                    test_subject = "Test Email from University System"
                    test_body = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    if send_email(recipient, test_subject, test_body):
                        print("✅ Test email sent successfully!")
                    else:
                        print("❌ Failed to send test email.")
                else:
                    print("❌ No recipient email provided.")
            elif choice == '12':
                # Manage Email Templates
                from education_system.post_18.university_system.infrastructure.email.templates import template_management_menu
                template_management_menu()
            elif choice == '13':
                # Schedule Emails
                from education_system.post_18.university_system.infrastructure.email.email_service import schedule_email_form
                schedule_email_form()
            elif choice == '14':
                # View Email Queue Status
                from education_system.post_18.university_system.infrastructure.email.email_service import email_queue, get_stored_emails
                if config.get('database_only_mode', True):
                    emails_data = get_stored_emails(limit=1)
                    print(f"\n📊 Stored emails in database: {emails_data['total_count']}")
                    if emails_data['total_count'] > 0:
                        print("Recent stored emails:")
                        recent_emails = get_stored_emails(limit=5)
                        for email in recent_emails['emails']:
                            print(f"  - To: {email['recipient_email']}, Subject: {email['subject'][:50]}...")
                else:
                    queue_size = email_queue.qsize()
                    print(f"\n📊 Current email queue size: {queue_size}")
                input("\nPress Enter to continue...")
            elif choice == '15':
                # View Stored Emails
                from education_system.post_18.university_system.infrastructure.email.email_service import display_stored_emails_menu
                display_stored_emails_menu()
            elif choice == '16':
                # Generate Email Reports
                from education_system.post_18.university_system.infrastructure.email.reports import generate_report_form
                generate_report_form()
            elif choice == '17':
                if LOG_MANAGEMENT_AVAILABLE:
                    # Communication Activity Logs
                    from education_system.post_18.university_system.core.logs import display_communication_logs_menu
                    display_communication_logs_menu(dashboard)
                elif not is_admin:
                    # Return to main menu (non-admin, no log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '18':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Communication Analytics
                    from education_system.post_18.university_system.core.logs import display_communication_analytics_menu
                    display_communication_analytics_menu(dashboard)
                else:
                    print("❌ Invalid choice.")
            elif choice == '19':
                if is_admin and not LOG_MANAGEMENT_AVAILABLE:
                    # Admin Message Management (admin without log management)
                    from education_system.post_18.university_system.infrastructure.email.admin import display_admin_message_management_menu
                    display_admin_message_management_menu(dashboard)
                elif is_admin or LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '20':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu (admin with log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice.upper() == 'C':
                # Cross-System Messages — links the per-system Email Manager
                # to the shared inter-system messaging CLI.
                from education_system.shared.messaging import cross_system_cli
                cross_system_cli.run(auth=auth)
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {max_choice}.")

        except KeyboardInterrupt:
            print("\n\nExiting communication hub menu...")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"❌ Error: {e}")


def display_accessibility_tools_menu(auth):
    """Display the Accessibility & Accommodation Tools CLI menu"""
    print("\n" + "="*50)
    print("  ACCESSIBILITY & ACCOMMODATION TOOLS")
    print("="*50)
    print("1. Manage Accommodation Requests")
    print("2. Accessibility Profiles")
    print("3. Assistive Technology Settings")
    print("4. Document Formats & Conversions")
    print("5. Captioning & Transcripts")
    print("6. Testing Accommodations")
    print("7. Compliance Audits")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print("\n♿ Accessibility feature - Database tables available")
                print("Database tables: accommodation_requests, accommodation_approvals,")
                print("accessibility_profiles, assistive_technology, document_formats,")
                print("captioning_requests, testing_accommodations, accessibility_audits,")
                print("accommodation_documentation")
                print("\nAccess via SQL or create manager following existing patterns.")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"❌ Error: {e}")


def display_transportation_parking_menu(auth):
    """Display the Transportation & Parking Management CLI menu"""
    # Redirect to parking management menu which now includes transportation
    from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import display_parking_menu
    display_parking_menu()


def display_administrative_tools_menu(auth):
    """Consolidated administrative tools and analytics menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access administrative tools.")
        return

    while True:
        print("\n" + "="*60)
        print("            ADMINISTRATIVE TOOLS & ANALYTICS")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n👥 User & Access Management:")
        print("1. User Management")

        print("\n📊 Reporting & Analytics:")
        print("2. Enhanced Reporting")
        print("3. Student Analytics Dashboard")
        print("4. Predictive Analytics Dashboard")
        print("5. Business Intelligence Reports")

        print("\n🔧 System Operations:")
        print("6. Batch Operations")
        print("7. Advanced Search and Filtering")

        if auth.current_user['role'] == 'admin':
            print("\n🛠️ Database Administration:")
            print("8. Admin Database Tools")

        print("\n↩️ Navigation:")
        if auth.current_user['role'] == 'admin':
            print("9. Return to Main Menu")
            max_choice = 9
        else:
            print("8. Return to Main Menu")
            max_choice = 8
        print("="*60)

        choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

        if choice == '1':
            # User Management
            display_user_management_menu(auth)
        elif choice == '2':
            # Enhanced Reporting
            from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting import display_enhanced_reporting_menu
            display_enhanced_reporting_menu()
        elif choice == '3':
            # Student Analytics Dashboard
            display_analytics_menu()
        elif choice == '4':
            # Predictive Analytics Dashboard
            display_predictive_analytics_menu(auth)
        elif choice == '5':
            # Business Intelligence Reports
            display_business_intelligence_menu(auth)
        elif choice == '6':
            # Batch Operations
            display_batch_menu()
        elif choice == '7':
            # Advanced Search
            display_enhanced_menu()
        elif choice == '8':
            if auth.current_user['role'] == 'admin':
                # Admin Database Tools
                display_admin_tools_menu()
            else:
                # Return to main menu (non-admin)
                break
        elif choice == '9' and auth.current_user['role'] == 'admin':
            # Return to main menu (admin)
            break
        else:
            print("Invalid choice. Please try again.")


def display_data_document_management_menu(auth):
    """Consolidated data and document management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access data management.")
        return

    while True:
        print("\n" + "="*60)
        print("        DATA & DOCUMENT MANAGEMENT SYSTEM")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n📄 Document Management:")
        print("1. Document Management System")

        print("\n💾 Data Operations:")
        print("2. Export Options")
        print("3. Data Backup and Restore")

        print("\n↩️ Navigation:")
        print("4. Return to Main Menu")
        print("="*60)

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            # Document Management
            from education_system.post_18.university_system.modules.shared.utils.document_manager import display_document_management_menu
            display_document_management_menu()
        elif choice == '2':
            # Export Options
            display_export_menu()
        elif choice == '3':
            # Data Backup and Restore
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_backup_menu
            display_backup_menu()
        elif choice == '4':
            # Return to main menu
            break
        else:
            print("Invalid choice. Please try again.")


def switch_to_gui(auth_instance):
    """Switch from CLI to GUI interface without circular imports"""
    try:
        print("\n🔄 Switching to GUI interface...")
        print("Please wait while the GUI loads...")

        # Dynamic import to avoid circular imports
        import importlib
        gui_module = importlib.import_module('education_system.post_18.university_system.modules.shared.gui.main')

        # Get the current user from the authenticated CLI session
        current_user = auth_instance.current_user if hasattr(auth_instance, 'current_user') else None

        # Use the centralized init_gui function with the logged-in user
        init_gui_func = getattr(gui_module, 'init_gui', None)
        if callable(init_gui_func):
            main_gui = init_gui_func(session_user=current_user)
        else:
            # Fallback to old method if init_gui is not available
            print("⚠️ Warning: Using legacy GUI initialization")
            if hasattr(gui_module, 'auth'):
                gui_module.auth = auth_instance
            safe_auth_check = getattr(gui_module, 'safe_auth_check', None)
            if callable(safe_auth_check):
                safe_auth_check(auth_instance)
            main_gui = gui_module.StudentManagementGUI(auth_instance)

        print("✅ GUI interface loaded successfully!")
        print("You can now close this CLI window if desired.")

        # Start the GUI application loop
        if hasattr(main_gui, 'run') and callable(main_gui.run):
            main_gui.run()
        elif hasattr(main_gui, 'root') and hasattr(main_gui.root, 'mainloop'):
            main_gui.root.mainloop()
        else:
            print("⚠️ Unable to determine GUI main loop entry point. Closing GUI instance.")
            return

    except ImportError as e:
        print(f"❌ Error: Could not import GUI module: {e}")
        print("Please ensure the GUI components are properly installed.")
        input("Press Enter to continue with CLI...")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error switching to GUI: {e}")
        print("Continuing with CLI interface...")
        input("Press Enter to continue...")


__all__ = [
    'display_menu',
    'display_virtual_classroom_menu',
    'display_financial_aid_menu',
    'display_communication_hub_menu',
    'display_accessibility_tools_menu',
    'display_transportation_parking_menu',
    'display_administrative_tools_menu',
    'display_data_document_management_menu',
    'switch_to_gui',
]
