"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    AuthenticationError,
    BARBER_SHOP_AVAILABLE,
    BAR_AVAILABLE,
    BETTING_SHOP_AVAILABLE,
    BUTCHER_SHOP_AVAILABLE,
    CAFE_CLI_AVAILABLE,
    CARRENTAL_AVAILABLE,
    CHARITY_SHOP_CLI_AVAILABLE,
    CHURCH_AVAILABLE,
    CINEMA_AVAILABLE,
    DEGREE_AUDIT_CLI_AVAILABLE,
    DENTIST_AVAILABLE,
    EQUIPMENT_RENTAL_AVAILABLE,
    GRADUATION_CEREMONY_CLI_AVAILABLE,
    GROCERY_CLI_AVAILABLE,
    GYM_AVAILABLE,
    INFORMATION_RIGHTS_AVAILABLE,
    LEGAL_SERVICES_AVAILABLE,
    MAIL_POST_AVAILABLE,
    MEDICAL_ACCOMMODATION_AVAILABLE,
    MUSIC_SHOP_AVAILABLE,
    NAILBAR_AVAILABLE,
    OFFICE_HOURS_CLI_AVAILABLE,
    PHONE_SHOP_AVAILABLE,
    POLICE_STATION_AVAILABLE,
    PermissionDeniedError,
    SECURITY_DASHBOARD_CLI_AVAILABLE,
    SECURITY_DESK_AVAILABLE,
    STAFF_HR_CLI_AVAILABLE,
    TAKEAWAY_CLI_AVAILABLE,
    TAXI_BOOKING_AVAILABLE,
    TA_MANAGEMENT_CLI_AVAILABLE,
    TODO_AVAILABLE,
    TRAIN_STATION_AVAILABLE,
    UserAuth,
    ValidationError,
    add_finance_permissions,
    bar_menu,
    carrental_menu,
    church_menu,
    cleanup_database_connections,
    cleanup_database_on_startup,
    dentist_menu,
    display_admissions_crm_menu,
    display_advanced_attendance_menu,
    display_ai_features_menu,
    display_alumni_relations_menu,
    display_auth_menu,
    display_blockchain_credentials_menu,
    display_business_intelligence_menu,
    display_cafe_menu,
    display_campus_events_menu,
    display_career_services_menu,
    display_charity_shop_menu,
    display_course_evaluation_menu,
    display_course_management_menu,
    display_early_warning_menu,
    display_enhanced_grade_menu,
    display_facilities_management_menu,
    display_finance_menu,
    display_grocery_menu,
    display_health_portal_menu,
    display_housing_accommodation_menu,
    display_integrated_academic_menu,
    display_integration_marketplace_menu,
    display_language_menu_option,
    display_library_menu,
    display_lms_menu,
    display_mobile_app_pwa_menu,
    display_office_hours_menu,
    display_pdf_export_menu,
    display_research_grants_menu,
    display_security_dashboard_menu,
    display_staff_hr_menu,
    display_student_records_menu,
    display_student_union_menu,
    display_support_menu,
    display_system_monitoring_menu,
    display_ta_management_menu,
    display_takeaway_menu,
    display_timetable_optimizer_menu,
    display_ucas_management_menu,
    equipment_rental_menu,
    get_auth,
    get_text,
    gym_menu,
    information_rights_menu,
    init_all_databases,
    init_auth_for_modules,
    integrate_plagiarism_checker_with_main,
    launch_barber_cli,
    launch_betting_shop_cli,
    launch_butcher_cli,
    launch_cinema_cli,
    launch_degree_audit_cli,
    launch_graduation_ceremony_cli,
    launch_medical_accommodation_cli,
    launch_nailbar_cli,
    legal_services_menu,
    logger,
    logging,
    mail_post_menu,
    music_shop_menu,
    phone_shop_menu,
    police_station_menu,
    predictive_analytics_menu,
    safe_auth_check,
    security_desk_menu,
    set_auth,
    set_auth_instance,
    set_finance_auth,
    set_integration_auth,
    set_student_ops_auth,
    set_support_auth,
    setup_alumni_permissions,
    setup_cafe_permissions,
    setup_charity_shop_permissions,
    setup_grocery_permissions,
    setup_internship_permissions,
    setup_office_hours_permissions,
    setup_shop_permissions,
    setup_staff_hr_permissions,
    setup_student_union_permissions,
    setup_ta_permissions,
    setup_takeaway_permissions,
    setup_trip_permissions,
    taxi_booking_menu,
    todo_menu,
    train_station_menu,
)
from ..bootstrap.integrations import _link_auth_to_student_union
from ..features.administrative_tools import display_administrative_tools_menu
from ..features.communication_hub import display_communication_hub_menu
from ..features.document_management import display_data_document_management_menu
from ..features.financial_aid import display_financial_aid_menu
from ..features.transportation import display_transportation_parking_menu
from ..features.virtual_classroom import display_virtual_classroom_menu
from ..menus.cross_system import _handle_cross_system_tool
from ..menus.optional_plugins import _dispatch_new_feature
from ..routing.lifecycle import switch_to_gui

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
                from education_system.systems.university.infrastructure.auth import add_plagiarism_permissions
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
        from education_system.systems.university.interfaces.cli.shell.utils import require_authenticated_user
        if not require_authenticated_user(auth):
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
                    from education_system.systems.university.interfaces.cli.academics.exam_management_cli import display_exam_portal_menu
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
                        from education_system.systems.university.domain.pastoral.student_life.student_union import set_auth as _su_set_auth
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
                    from education_system.systems.university.interfaces.cli.safeguarding import run_safeguarding_menu
                    run_safeguarding_menu(auth)
                except Exception as e:
                    print(f"\n❌ Safeguarding CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "visa_compliance":
                try:
                    from education_system.systems.university.interfaces.cli.governance.compliance.international_compliance import run_visa_compliance_menu
                    run_visa_compliance_menu(auth)
                except Exception as e:
                    print(f"\n❌ Visa Compliance CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "equality_diversity":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.equality_diversity import run_equality_diversity_menu
                    run_equality_diversity_menu(auth)
                except Exception as e:
                    print(f"\n❌ Equality & Diversity CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "disciplinary":
                try:
                    from education_system.systems.university.interfaces.cli.governance.legal.disciplinary import run_disciplinary_menu
                    run_disciplinary_menu(auth)
                except Exception as e:
                    print(f"\n❌ Disciplinary CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "fitness_to_practise":
                try:
                    from education_system.systems.university.interfaces.cli.governance.legal.disciplinary.fitness_to_practise import run_ftp_menu
                    run_ftp_menu(auth)
                except Exception as e:
                    print(f"\n❌ Fitness to Practise CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "risk_management":
                try:
                    from education_system.systems.university.interfaces.cli.governance.legal.risk_management import run_risk_management_menu
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
                    from education_system.systems.university.interfaces.cli.governance.compliance.hesa_export.hesa_export_cli import display_hesa_export_menu
                    display_hesa_export_menu(auth)
                except ImportError as e:
                    print(f"\n❌ HESA Export CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "external_examiners":
                try:
                    from education_system.systems.university.interfaces.cli.assessment.external_examiners.external_examiner_cli import display_external_examiner_menu
                    display_external_examiner_menu(auth)
                except ImportError as e:
                    print(f"\n❌ External Examiners CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "external_qa":
                try:
                    from education_system.systems.university.interfaces.cli.academics.research.external_quality_assurance.eqa_cli import display_external_qa_menu
                    display_external_qa_menu(auth)
                except ImportError as e:
                    print(f"\n❌ External QA CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "mitigating_circumstances":
                try:
                    from education_system.systems.university.interfaces.cli.assessment.mitigating_circumstances.mitigating_circumstances_cli import display_mitigating_circumstances_menu
                    display_mitigating_circumstances_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Mitigating Circumstances CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "curriculum_specification":
                try:
                    from education_system.systems.university.interfaces.cli.academics.curriculum_specification.curriculum_specification_cli import display_curriculum_specification_menu
                    display_curriculum_specification_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Curriculum Specification CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_app":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.student_app.student_app_cli import display_student_app_menu
                    display_student_app_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Student App CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "enrolment_letters":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.student_app.documentation.documentation_cli import display_documentation_menu
                    display_documentation_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Status Letters CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "achievement_badges":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.achievement_badges.achievement_badge_cli import display_achievement_badge_menu
                    display_achievement_badge_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Achievement Badges CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "study_recommendations":
                try:
                    from education_system.systems.university.interfaces.cli.academics.study_recommendations.study_recommendation_cli import display_study_recommendation_menu
                    display_study_recommendation_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Study Recommendations CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "clearing_adjustment":
                try:
                    from education_system.systems.university.interfaces.cli.admissions.clearing_adjustment.clearing_adjustment_cli import display_clearing_adjustment_menu
                    display_clearing_adjustment_menu(auth)
                except ImportError as e:
                    print(f"\n❌ Clearing & Adjustment CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "prior_learning":
                try:
                    from education_system.systems.university.interfaces.cli.admissions.prior_learning_recognition.prior_learning_cli import display_prior_learning_menu
                    display_prior_learning_menu(auth)
                except ImportError as e:
                    print(f"\n❌ APL/RPL CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "course_planning":
                try:
                    from education_system.systems.university.interfaces.cli.academics.course_planning.planning_cli import main as course_planning_main
                    course_planning_main()
                except ImportError as e:
                    print(f"\n  Course Planning CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "lesson_planner":
                try:
                    from education_system.systems.university.interfaces.cli.academics.course_planning import run_lesson_planner_menu
                    run_lesson_planner_menu(auth)
                except Exception as e:
                    print(f"\n  Lesson Planner CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "apprenticeships":
                try:
                    from education_system.systems.university.interfaces.cli.progression.apprenticeships import run_apprenticeships_menu
                    run_apprenticeships_menu(auth)
                except Exception as e:
                    print(f"\n  Apprenticeships CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "placements":
                try:
                    from education_system.systems.university.interfaces.cli.progression.placements import run_placements_menu
                    run_placements_menu(auth)
                except Exception as e:
                    print(f"\n  Placements CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "bakery_shop":
                try:
                    from education_system.systems.university.interfaces.cli.operations.commerce.bakery_shop import run_bakery_menu
                    run_bakery_menu(auth)
                except Exception as e:
                    print(f"\n  Bakery Shop CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "bank_rec":
                try:
                    from education_system.systems.university.interfaces.cli.finance.bank_rec import run_bank_rec_menu
                    run_bank_rec_menu(auth)
                except Exception as e:
                    print(f"\n  Bank Reconciliation CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "ledger":
                try:
                    from education_system.systems.university.interfaces.cli.finance.ledger import run_ledger_menu
                    run_ledger_menu(auth)
                except Exception as e:
                    print(f"\n  Ledger CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "statements":
                try:
                    from education_system.systems.university.interfaces.cli.finance.statements import run_statements_menu
                    run_statements_menu(auth)
                except Exception as e:
                    print(f"\n  Statements CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "first_aid":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.health.first_aid import run_first_aid_menu
                    run_first_aid_menu(auth)
                except Exception as e:
                    print(f"\n  First Aid CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "health_safety":
                try:
                    from education_system.systems.university.interfaces.cli.governance.health_safety import run_health_safety_menu
                    run_health_safety_menu(auth)
                except Exception as e:
                    print(f"\n  Health & Safety CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "advising":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.advising.advising_cli import main as advising_main
                    advising_main()
                except ImportError as e:
                    print(f"\n  Advising CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_wellbeing":
                try:
                    from education_system.systems.university.interfaces.cli.pastoral.wellbeing.student_wellbeing.student_wellbeing_cli import main as wellbeing_main
                    wellbeing_main()
                except ImportError as e:
                    print(f"\n  Student Wellbeing CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_finance":
                # Student Finance merged into the main Finance CLI/GUI.
                try:
                    from education_system.systems.university.interfaces.gui.finance.finance.finance_gui import FinanceGUI
                    import tkinter as tk
                    FinanceGUI(tk.Tk())
                except Exception as e:
                    print(f"\n  Finance GUI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "student_id_card":
                try:
                    from education_system.systems.university.interfaces.cli.learners.student_id.student_id_cli import main as student_id_main
                    student_id_main()
                except ImportError as e:
                    print(f"\n  Student ID CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "printing":
                try:
                    from education_system.systems.university.interfaces.cli.operations.campus.printing.printing_cli import main as printing_main
                    printing_main()
                except ImportError as e:
                    print(f"\n  Printing CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "study_rooms":
                try:
                    from education_system.systems.university.interfaces.cli.operations.campus.study_rooms.study_rooms_cli import main as study_rooms_main
                    study_rooms_main()
                except ImportError as e:
                    print(f"\n  Study Rooms CLI is not available: {e}")
                    input("Press Enter to continue...")
            elif option == "textbooks":
                try:
                    from education_system.systems.university.interfaces.cli.operations.commerce.textbooks.textbooks_cli import main as textbooks_main
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
