"""
CLI System Package

This package provides the command-line interface for the University Management System.
It has been refactored into a modular structure for better maintainability.

Main Modules:
- cli_main: Main entry point and orchestrator
- imports: Centralized imports and availability flags
- database_manager: Database operations and schema management
- auth_manager: Authentication and user management
- student_operations: Student CRUD operations
- student_search: Student search functionality
- module_operations: Course/module management
- export_manager: Data export to various formats
- integration_manager: External system integrations
- chatbot_integration: Chatbot functionality
- ai_tools_integration: AI detector and plagiarism checker
- menu_builder: Menu construction utilities
- menu_router: Menu navigation and routing
- system_monitoring: System health and monitoring
- admin_tools: Administrative utilities
- utils: Helper functions and utilities

Usage:
    # From other parts of the system
    from university_system.modules.shared.cli import main
    main()

    # Or use individual functions (backward compatible)
    from university_system.modules.shared.cli import create_student_record
"""

# Import main entry point
from .cli_main import main, initialize_system, auth

# Import DB_PATH from imports
from .imports import DB_PATH

# Import finance menu (for backward compatibility)
try:
    from university_system.modules.domain.finance.core.financial_core import (
        display_enhanced_finance_menu as display_finance_menu
    )
except ImportError:
    display_finance_menu = None

# Import from database_manager
from .database_manager import (
    get_db_connection,
    safe_db_operation_with_retry,
    enhanced_db_operation,
    handle_database_error,
    fix_accommodation_schema,
    fix_parent_portal_database,
    fix_ai_detector_database_schema,
    fix_support_database_schema,
    fix_duplicate_emails,
    silent_integrity_check,
    validate_database_integrity,
    validate_database_integrity_with_admin_context,
    emergency_fix_database,
    cleanup_database_on_startup,
    cleanup_database_connections,
    init_db,
    init_integration_tables,
    init_all_databases,
    init_auth_for_modules,
)

# Import from auth_manager
from .auth_manager import (
    ensure_default_users_exist_once,
    create_default_user_if_needed,
    ensure_user_in_communication_system,
    initialize_security_modules,
)

# Import from student_operations
from .student_operations import (
    create_student_record,
    view_student_record,
    update_student_record,
    delete_student_record,
    display_student_record,
    display_student_records_menu,
    fetch_student_data,
    example_create_student_operation,
    create_student_with_retry,
)

# Import from student_search
from .student_search import (
    search_student_by_first_name,
    search_student_by_last_name,
    search_student_by_student_id,
    search_student_by_registration_date,
)

# Import from module_operations
from .module_operations import (
    create_module,
    edit_module,
    delete_module,
    search_module_by_module_name,
    search_module_by_module_code,
    display_module_management_menu,
)

# Import from export_manager
from .export_manager import (
    get_file_path,
    export_to_csv,
    export_to_excel,
    export_to_pdf,
    export_to_txt,
    display_export_menu,
    display_pdf_export_menu,
)

# Import from integration_manager
from .integration_manager import (
    link_attendance_to_calendar_events,
    create_integrated_dashboard_data,
    display_integrated_system_dashboard,
    ensure_communication_integration_on_startup,
    add_communication_dashboard_to_main_menu,
    create_trip_calendar_event,
    view_integrated_dashboard,
    sync_trips_with_calendar,
    link_trip_to_event_manually,
    view_trip_calendar_links,
    display_integrated_academic_menu,
)

# Import from chatbot_integration
from .chatbot_integration import (
    initialize_chatbot_integration,
    display_chatbot_menu,
    start_chat_session,
    log_chatbot_conversation,
    view_conversation_history,
    view_all_conversations,
    chatbot_administration,
    show_chatbot_statistics,
    clear_conversation_history,
    restart_chatbot,
    setup_chatbot_permissions,
    launch_chatbot,
)

# Import from ai_tools_integration
from .ai_tools_integration import (
    integrate_ai_detector_with_main,
    create_minimal_ai_detector,
    display_ai_detector_menu_from_main,
    analyze_text_interface_safe,
    display_analysis_results_safe,
    fix_ai_detector_database_schema,
    view_submission_history_safe,
    display_detailed_submission,
    view_ai_detector_statistics_safe,
    run_ai_detector_demo_safe,
    integrate_plagiarism_checker_with_main,
    display_plagiarism_checker_menu,
)

# Import from menu_router
from .menu_router import (
    display_menu,
    display_virtual_classroom_menu,
    display_financial_aid_menu,
    display_communication_hub_menu,
    display_accessibility_tools_menu,
    display_transportation_parking_menu,
    display_administrative_tools_menu,
    display_data_document_management_menu,
    switch_to_gui,
)

# Import from system_monitoring
from .system_monitoring import (
    view_system_health,
    view_application_metrics,
    view_recent_alerts,
    manage_backups,
    view_cache_statistics,
    view_performance_monitoring,
    create_manual_backup,
    clear_cache,
    display_system_monitoring_menu,
)

# Import from admin_tools
from .admin_tools import (
    display_admin_tools_menu,
    display_database_statistics,
    display_analytics_menu,
    display_batch_menu,
)

# Import from utils
from .utils import (
    safe_auth_check,
    suppress_duplicate_messages,
    cleanup_connections,
)

# Import availability flags from imports module
from .imports import (
    HAS_PANDAS,
    HAS_REPORTLAB,
    ACADEMIC_MISCONDUCT_AVAILABLE,
    SECURITY_DESK_AVAILABLE,
    TODO_AVAILABLE,
    CHURCH_AVAILABLE,
    POLICE_STATION_AVAILABLE,
    TAXI_BOOKING_AVAILABLE,
    TRAIN_STATION_AVAILABLE,
    LEGAL_SERVICES_AVAILABLE,
    CARRENTAL_AVAILABLE,
    EQUIPMENT_RENTAL_AVAILABLE,
    PHONE_SHOP_AVAILABLE,
    MUSIC_SHOP_AVAILABLE,
    BAR_AVAILABLE,
    BETTING_SHOP_AVAILABLE,
    BUTCHER_SHOP_AVAILABLE,
    BARBER_SHOP_AVAILABLE,
    NAILBAR_AVAILABLE,
    CINEMA_AVAILABLE,
    MEDICAL_ACCOMMODATION_AVAILABLE,
    DEGREE_AUDIT_CLI_AVAILABLE,
    MAIL_POST_AVAILABLE,
    GYM_AVAILABLE,
    DENTIST_AVAILABLE,
    MFA_AVAILABLE,
    MFA_INTEGRATION_AVAILABLE,
    EMAIL_OTP_AVAILABLE,
    SMS_PROVIDER_AVAILABLE,
    SESSION_MANAGEMENT_AVAILABLE,
    COMPREHENSIVE_SECURITY_AVAILABLE,
    DATA_ENCRYPTION_AVAILABLE,
    SECURITY_DASHBOARD_CLI_AVAILABLE,
    CHARITY_SHOP_CLI_AVAILABLE,
    CAFE_CLI_AVAILABLE,
    TAKEAWAY_CLI_AVAILABLE,
    GROCERY_CLI_AVAILABLE,
    STAFF_HR_CLI_AVAILABLE,
)


__all__ = [
    # Main entry point
    'main',
    'initialize_system',
    'auth',
    'DB_PATH',
    'display_finance_menu',

    # Database operations
    'get_db_connection',
    'safe_db_operation_with_retry',
    'enhanced_db_operation',
    'handle_database_error',
    'fix_accommodation_schema',
    'fix_parent_portal_database',
    'fix_ai_detector_database_schema',
    'fix_support_database_schema',
    'fix_duplicate_emails',
    'silent_integrity_check',
    'validate_database_integrity',
    'validate_database_integrity_with_admin_context',
    'emergency_fix_database',
    'cleanup_database_on_startup',
    'cleanup_database_connections',
    'init_db',
    'init_integration_tables',
    'init_all_databases',
    'init_auth_for_modules',

    # Authentication
    'set_auth',
    'ensure_default_users_exist_once',
    'create_default_user_if_needed',
    'ensure_user_in_communication_system',
    'initialize_security_modules',

    # Student operations
    'create_student_record',
    'view_student_record',
    'update_student_record',
    'delete_student_record',
    'display_student_record',
    'display_student_records_menu',
    'fetch_student_data',
    'example_create_student_operation',
    'create_student_with_retry',

    # Student search
    'search_student_by_first_name',
    'search_student_by_last_name',
    'search_student_by_student_id',
    'search_student_by_registration_date',

    # Module operations
    'create_module',
    'edit_module',
    'delete_module',
    'search_module_by_module_name',
    'search_module_by_module_code',
    'display_module_management_menu',

    # Export
    'get_file_path',
    'export_to_csv',
    'export_to_excel',
    'export_to_pdf',
    'export_to_txt',
    'display_export_menu',
    'display_pdf_export_menu',

    # Integration
    'link_attendance_to_calendar_events',
    'create_integrated_dashboard_data',
    'display_integrated_system_dashboard',
    'ensure_communication_integration_on_startup',
    'add_communication_dashboard_to_main_menu',
    'create_trip_calendar_event',
    'view_integrated_dashboard',
    'sync_trips_with_calendar',
    'link_trip_to_event_manually',
    'view_trip_calendar_links',
    'display_integrated_academic_menu',

    # Chatbot
    'initialize_chatbot_integration',
    'display_chatbot_menu',
    'start_chat_session',
    'log_chatbot_conversation',
    'view_conversation_history',
    'view_all_conversations',
    'chatbot_administration',
    'show_chatbot_statistics',
    'clear_conversation_history',
    'restart_chatbot',
    'setup_chatbot_permissions',
    'launch_chatbot',

    # AI Tools
    'integrate_ai_detector_with_main',
    'create_minimal_ai_detector',
    'display_ai_detector_menu_from_main',
    'analyze_text_interface_safe',
    'display_analysis_results_safe',
    'fix_ai_detector_database_schema',
    'view_submission_history_safe',
    'display_detailed_submission',
    'view_ai_detector_statistics_safe',
    'run_ai_detector_demo_safe',
    'integrate_plagiarism_checker_with_main',
    'display_plagiarism_checker_menu',

    # Menus
    'display_menu',
    'display_virtual_classroom_menu',
    'display_financial_aid_menu',
    'display_communication_hub_menu',
    'display_accessibility_tools_menu',
    'display_transportation_parking_menu',
    'display_administrative_tools_menu',
    'display_data_document_management_menu',
    'switch_to_gui',

    # System monitoring
    'view_system_health',
    'view_application_metrics',
    'view_recent_alerts',
    'manage_backups',
    'view_cache_statistics',
    'view_performance_monitoring',
    'create_manual_backup',
    'clear_cache',
    'display_system_monitoring_menu',

    # Admin tools
    'display_admin_tools_menu',
    'display_database_statistics',
    'display_analytics_menu',
    'display_batch_menu',

    # Utilities
    'safe_auth_check',
    'suppress_duplicate_messages',
    'cleanup_connections',

    # Availability flags
    'HAS_PANDAS',
    'HAS_REPORTLAB',
    'ACADEMIC_MISCONDUCT_AVAILABLE',
    'SECURITY_DESK_AVAILABLE',
    'TODO_AVAILABLE',
    'CHURCH_AVAILABLE',
    'POLICE_STATION_AVAILABLE',
    'TAXI_BOOKING_AVAILABLE',
    'TRAIN_STATION_AVAILABLE',
    'LEGAL_SERVICES_AVAILABLE',
    'CARRENTAL_AVAILABLE',
    'EQUIPMENT_RENTAL_AVAILABLE',
    'PHONE_SHOP_AVAILABLE',
    'MUSIC_SHOP_AVAILABLE',
    'BAR_AVAILABLE',
    'BETTING_SHOP_AVAILABLE',
    'BUTCHER_SHOP_AVAILABLE',
    'BARBER_SHOP_AVAILABLE',
    'NAILBAR_AVAILABLE',
    'CINEMA_AVAILABLE',
    'MEDICAL_ACCOMMODATION_AVAILABLE',
    'DEGREE_AUDIT_CLI_AVAILABLE',
    'MAIL_POST_AVAILABLE',
    'GYM_AVAILABLE',
    'DENTIST_AVAILABLE',
    'MFA_AVAILABLE',
    'MFA_INTEGRATION_AVAILABLE',
    'EMAIL_OTP_AVAILABLE',
    'SMS_PROVIDER_AVAILABLE',
    'SESSION_MANAGEMENT_AVAILABLE',
    'COMPREHENSIVE_SECURITY_AVAILABLE',
    'DATA_ENCRYPTION_AVAILABLE',
    'SECURITY_DASHBOARD_CLI_AVAILABLE',
    'CHARITY_SHOP_CLI_AVAILABLE',
    'CAFE_CLI_AVAILABLE',
    'TAKEAWAY_CLI_AVAILABLE',
    'GROCERY_CLI_AVAILABLE',
    'STAFF_HR_CLI_AVAILABLE',
]


# Version info
__version__ = '5.0.0'
__author__ = 'University Management System Team'
__description__ = 'Modular CLI system for university management'
