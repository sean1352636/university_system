"""
Menu router for CLI system.

Routes user choices to appropriate handlers and manages menu navigation.
"""

from .imports import (
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
from .database_manager import cleanup_database_on_startup, init_all_databases, init_auth_for_modules, cleanup_database_connections

# Import menu functions
from .student_operations import display_student_records_menu, set_auth as set_student_ops_auth
from .integration_manager import display_integrated_academic_menu, set_auth as set_integration_auth
from university_system.modules.domain.academics.services.lms.lms_core import display_lms_menu
from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import display_course_evaluation_menu
from university_system.modules.domain.health.services.health_portal import display_health_portal_menu
from university_system.modules.domain.career.services.career_services_core import display_career_services_menu
from university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import display_early_warning_menu
from university_system.modules.domain.student_affairs.services.student_support.features.dashboard import display_support_menu
from university_system.modules.domain.student_affairs.services.student_support.auth import set_auth as set_support_auth
from university_system.modules.domain.academics.services.library.menu import display_library_menu
from university_system.modules.domain.facilities.services.facilities_management_core import display_facilities_management_menu
from university_system.modules.domain.admissions.services.admissions_crm_core import display_admissions_crm_menu
from university_system.modules.domain.research.services.research_grants_core import display_research_grants_menu
from university_system.modules.domain.campus.services.campus_events_core import display_campus_events_menu
from university_system.modules.domain.finance.gui.finance_reporting.misc import display_finance_menu, set_auth as set_finance_auth

# Import menu functions that may not exist - with fallbacks
try:
    from university_system.modules.domain.academics.gui.grade_tracking_management_gui import display_enhanced_grade_menu, predictive_analytics_menu
except ImportError:
    display_enhanced_grade_menu = None
    predictive_analytics_menu = None

try:
    from university_system.modules.domain.student_affairs.gui.student_union_management_gui import display_student_union_menu
except ImportError:
    display_student_union_menu = None

# Placeholder functions for not-yet-implemented features
def display_advanced_attendance_menu():
    print("\n❌ Advanced Attendance menu is not yet implemented")
    input("Press Enter to continue...")

def display_timetable_optimizer_menu():
    print("\n❌ Timetable Optimizer menu is not yet implemented")
    input("Press Enter to continue...")

def display_alumni_relations_menu():
    print("\n❌ Alumni Relations menu is not yet implemented")
    input("Press Enter to continue...")

# Import utility functions
from .utils import safe_auth_check

# Import exceptions
from university_system.infrastructure.exceptions import (
    ValidationError, AuthenticationError, PermissionDeniedError
)

# Import auth-related functions
from university_system.infrastructure.auth import set_auth_instance

# Import permission setup functions
from university_system.modules.domain.student_affairs.services.alumni_management import setup_alumni_permissions
from university_system.modules.domain.student_affairs.services.internship_management import setup_internship_permissions
from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import setup_student_union_permissions
from university_system.infrastructure.auth import add_finance_permissions
from university_system.modules.domain.commerce.services.shop_management import setup_shop_permissions
from university_system.modules.domain.mobility.services.trip_management import setup_trip_permissions
from university_system.modules.services.cli.charity_shop_cli import setup_charity_shop_permissions
from university_system.modules.services.cli.cafe_system_cli import setup_cafe_permissions
from university_system.modules.domain.commerce.services.takeaway.takeaway_service import setup_takeaway_permissions
from university_system.modules.domain.commerce.services.grocery.grocery_service import setup_grocery_permissions
from university_system.modules.domain.staff_hr.cli.staff_hr_cli import setup_staff_hr_permissions

# Import plagiarism checker integration
from university_system.modules.domain.academics.gui.plagiarism_main_gui import integrate_plagiarism_checker_with_main

# Import auth linking
from .auth_manager import _link_auth_to_student_union

# Import admin tools menus
from .admin_tools import display_analytics_menu, display_batch_menu, display_admin_tools_menu

# Import export menu
from .export_manager import display_export_menu, display_pdf_export_menu

# Import system monitoring
from .system_monitoring import display_system_monitoring_menu

# Import service menus
from university_system.modules.shared.services.analytics.analytics_dashboard_core import display_predictive_analytics_menu
from university_system.modules.shared.services.business_intelligence.bi_reports_core import display_business_intelligence_menu
from university_system.modules.shared.services.analytics.advanced_search import display_enhanced_menu
from university_system.modules.shared.services.ai_features.ai_features_core import display_ai_features_menu
from university_system.modules.shared.services.integrations.integration_marketplace_core import display_integration_marketplace_menu

# Import domain-specific menus
from university_system.modules.domain.blockchain.services.blockchain_credentials_core import display_blockchain_credentials_menu
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import display_mobile_app_pwa_menu
from university_system.modules.domain.academics.services.virtual_classroom.classroom_manager import VirtualClassroomManager
from university_system.modules.domain.finance.services.financial_aid.aid_manager import FinancialAidManager

auth = None


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
    
    # Initialize authentication system if not already done
    if auth is None:
        try:
            auth = get_auth()
            if auth is None:
                # Create if doesn't exist
                auth = UserAuth()
                set_auth(auth)
            # Ensure auth object has all required attributes
            safe_auth_check(auth)
            # Set the global auth instance for other modules
            set_auth_instance(auth)
        except (ValueError, TypeError, ValidationError) as e:
            logger.error(f"Error initializing authentication: {e}")
            logger.info("Creating minimal auth object...")
            # Create minimal auth object
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
        
        init_auth_for_modules()  # Initialize auth for other modules

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

            # Add plagiarism permissions AFTER UserAuth is fully initialized
            try:
                from university_system.infrastructure.auth import add_plagiarism_permissions
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
        # Check if user is logged in - FIXED VERSION
        if not safe_auth_check(auth) or not auth.current_user:
            # User is not logged in, show authentication menu first
            print(f"\n{get_text('cli.please_login', default='Please log in to access the system.')}")
            try:
                auth = display_auth_menu()
                if auth is None:
                    # Get or create auth object if none was returned
                    auth = get_auth()
                    if auth is None:
                        auth = UserAuth()
                        set_auth(auth)
                    safe_auth_check(auth)
                # Set the global auth instance after login
                set_auth_instance(auth)
                set_auth(auth)  # Update shared_context so get_auth() returns this instance
                init_auth_for_modules()  # Reinitialize auth for other modules
                # Loop back to check if login was successful
                continue
            except (AuthenticationError, PermissionDeniedError) as e:
                print(f"{get_text('cli.auth_menu_error', default='Error in authentication menu')}: {e}")
                print(get_text('cli.try_again_or_contact_admin', default='Please try again or contact an administrator.'))
                break
        
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
        ]
        if DEGREE_AUDIT_CLI_AVAILABLE:
            items.append(add_option(get_text('cli.menu.degree_audit', default='Degree Audit'), "degree_audit"))
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
        print_row(items)
        items = []
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

        # 📱 INFRASTRUCTURE & ⚙️ SYSTEM
        print(f"\n📱 {get_text('cli.menu.infrastructure_system', default='INFRASTRUCTURE & SYSTEM')}")
        items = [
            add_option(get_text('cli.menu.mobile_app', default='Mobile App (PWA)'), "mobile_app_pwa"),
            add_option(get_text('cli.menu.switch_to_gui', default='Switch to GUI'), "switch_to_gui"),
            add_option(get_text('cli.menu.language', default='Language'), "change_language"),
        ]
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
            elif option == "degree_audit":
                if DEGREE_AUDIT_CLI_AVAILABLE:
                    launch_degree_audit_cli(auth)
                else:
                    print("\n❌ Degree Audit CLI is not available")
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
            elif option == "mobile_app_pwa":
                display_mobile_app_pwa_menu(auth)
            elif option == "system_monitoring":
                display_system_monitoring_menu(auth)
            elif option == "switch_to_gui":
                switch_to_gui(auth)
            elif option == "change_language":
                display_language_menu_option()
            elif option == "logout":
                cleanup_database_connections()
                auth.logout()
            elif option == "exit":
                cleanup_database_connections()
                if auth and auth.current_user:
                    auth.logout()
                print(f"\n{get_text('cli.goodbye', default='Thank you for using the University Management System. Goodbye!')}")
                return
            else:
                print(get_text('cli.invalid_choice', default='Invalid choice. Please try again.'))
        else:
            print(get_text('cli.invalid_choice', default='Invalid choice. Please try again.'))


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
                print(f"\n{get_text('virtual.feature.schedule', default='Schedule Virtual Session - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '3':
                print(f"\n{get_text('virtual.feature.participants', default='Manage Participants - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '4':
                print(f"\n{get_text('virtual.feature.recordings', default='View Recordings - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '5':
                print(f"\n{get_text('virtual.feature.polls', default='Create Polls/Quizzes - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '6':
                print(f"\n{get_text('virtual.feature.breakout', default='Manage Breakout Rooms - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '7':
                print(f"\n{get_text('virtual.feature.chat', default='View Chat Messages - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '8':
                print(f"\n{get_text('virtual.feature.analytics', default='Session Analytics - Feature available via GUI')}")
                print(get_text('virtual.use_gui', default='Please use the GUI version for full functionality.'))
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
                print(f"\n{get_text('finaid.feature.applications', default='View Financial Aid Applications - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
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
                print(f"\n{get_text('finaid.feature.package', default='Create Aid Package - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '4':
                print(f"\n{get_text('finaid.feature.scholarships', default='Manage Scholarships - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '5':
                print(f"\n{get_text('finaid.feature.review', default='Review Scholarship Applications - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '6':
                print(f"\n{get_text('finaid.feature.award', default='Award Scholarship - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '7':
                print(f"\n{get_text('finaid.feature.disbursement', default='Disbursement Management - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
            elif choice == '8':
                print(f"\n{get_text('finaid.feature.compliance', default='Compliance Reports - Feature available via GUI')}")
                print(get_text('finaid.use_gui', default='Please use the GUI version for full functionality.'))
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
    from university_system.infrastructure.email.config import config
    from university_system.infrastructure.email.admin import CommunicationDashboard
    from university_system.modules.shared.services.communication.communication_manager import CommunicationManager
    from university_system.modules.shared.utils.logs import LOG_MANAGEMENT_AVAILABLE

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
                print("\n📱 Send Push Notification - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '4':
                # Messages Management
                from university_system.infrastructure.email.admin import display_messages_menu
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
                from university_system.infrastructure.email.admin import display_announcements_menu
                display_announcements_menu(dashboard)
            elif choice == '7':
                # Send Batch Announcement
                from university_system.infrastructure.email.email_service import send_batch_email_form
                send_batch_email_form()
            elif choice == '8':
                # Chat Rooms
                from university_system.infrastructure.email.admin import display_chat_rooms_menu
                display_chat_rooms_menu(dashboard)
            elif choice == '9':
                # Notification Preferences
                from university_system.infrastructure.email.admin import display_preferences_menu
                display_preferences_menu(dashboard)
            elif choice == '10':
                # Configure Email Settings
                from university_system.infrastructure.email.config import configure_email_settings
                configure_email_settings()
            elif choice == '11':
                # Test Email Configuration
                from university_system.infrastructure.email.email_service import send_email
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
                from university_system.infrastructure.email.templates import template_management_menu
                template_management_menu()
            elif choice == '13':
                # Schedule Emails
                from university_system.infrastructure.email.email_service import schedule_email_form
                schedule_email_form()
            elif choice == '14':
                # View Email Queue Status
                from university_system.infrastructure.email.email_service import email_queue, get_stored_emails
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
                from university_system.infrastructure.email.email_service import display_stored_emails_menu
                display_stored_emails_menu()
            elif choice == '16':
                # Generate Email Reports
                from university_system.infrastructure.email.reports import generate_report_form
                generate_report_form()
            elif choice == '17':
                if LOG_MANAGEMENT_AVAILABLE:
                    # Communication Activity Logs
                    from university_system.modules.shared.utils.logs import display_communication_logs_menu
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
                    from university_system.modules.shared.utils.logs import display_communication_analytics_menu
                    display_communication_analytics_menu(dashboard)
                else:
                    print("❌ Invalid choice.")
            elif choice == '19':
                if is_admin and not LOG_MANAGEMENT_AVAILABLE:
                    # Admin Message Management (admin without log management)
                    from university_system.infrastructure.email.admin import display_admin_message_management_menu
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
                print(f"\n♿ Accessibility feature - Database tables available")
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
    from university_system.modules.domain.mobility.services.parking_management import display_parking_menu
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
            from university_system.modules.shared.services.enhanced_reporting import display_enhanced_reporting_menu
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
            from university_system.modules.shared.utils.document_manager import display_document_management_menu
            display_document_management_menu()
        elif choice == '2':
            # Export Options
            display_export_menu()
        elif choice == '3':
            # Data Backup and Restore
            from university_system.infrastructure.database.data_backup import display_backup_menu
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
        gui_module = importlib.import_module('university_system.modules.shared.gui.main')

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
