"""
Library package: reorganized modules from the original monolithic library.py file.

This package re-exports all public classes and functions from the submodules to
maintain backward compatibility with existing imports. Clients can continue
importing directly from ``library`` without needing to know the internal
module structure.
"""

# Re-export classes from models
from education_system.university_system.modules.domain.academics.services.library.models import Book, BookLoan, BookReservation, BookReview, ReadingList

# Re-export database helpers
from education_system.university_system.modules.domain.academics.services.library.database import (
    get_db_connection,
    init_library_db,
    verify_database_structure,
    repair_database,
    log_audit_event,
)

# Re-export CRUD operations for books
from education_system.university_system.modules.domain.academics.services.library.book_crud import (
    fetch_book_metadata,
    assess_reading_level,
    enhanced_add_book,
    add_book,
    enhanced_update_book,
    update_book,
    delete_book,
    enhanced_view_book_details,
    view_book_details,
    list_all_books,
)

# Re-export search utilities
from education_system.university_system.modules.domain.academics.services.library.search import (
    enhanced_search_books,
    search_books,
    advanced_search_interface,
    execute_advanced_search,
    display_search_results,
    save_search_query,
    load_saved_searches,
)

# Re-export circulation functions
from education_system.university_system.modules.domain.academics.services.library.circulation import (
    check_loan_eligibility,
    check_reading_level_compatibility,
    enhanced_checkout_book,
    checkout_book,
    enhanced_return_book,
    return_book,
    renew_book,
    reserve_book,
    manage_reservations,
    view_overdue_books,
    view_loan_history,
)

# Re-export reading list utilities
from education_system.university_system.modules.domain.academics.services.library.reading_lists import (
    manage_reading_lists,
    manage_reading_list_items,
    add_to_reading_list,
    view_reading_list_details,
    share_reading_list,
    import_reading_list,
)

# Re-export review functions
from education_system.university_system.modules.domain.academics.services.library.reviews import (
    rate_and_review_book,
    moderate_review_content,
)

# Re-export digital library functions
from education_system.university_system.modules.domain.academics.services.library.digital_library import (
    manage_digital_library,
    download_digital_resource,
    check_digital_access_permission,
    manage_digital_access_permissions,
)

# Re-export reporting utilities
from education_system.university_system.modules.domain.academics.services.library.reports import (
    generate_circulation_report,
    generate_inventory_report,
    generate_user_activity_report,
    generate_analytics_dashboard,
    generate_detailed_analytics_report,
    generate_html_analytics_report,
    generate_enhanced_reports,
    generate_library_statistics_export,
    library_statistics_dashboard,
    generate_reports,
)

# Re-export notification helpers
from education_system.university_system.modules.domain.academics.services.library.notifications import (
    automated_notifications,
    send_enhanced_checkout_notification,
    send_overdue_notification,
    send_due_date_reminder,
    send_reservation_confirmation,
    send_reservation_available_notification,
    send_generic_email_notification,
    send_email_notification,
    send_sms_notification,
    configure_notification_settings,
)

# Re-export barcode utilities
from education_system.university_system.modules.domain.academics.services.library.barcode import (
    generate_barcode,
    generate_qr_code,
    scan_barcode,
    process_scanned_barcode,
    print_barcode_labels,
    generate_library_cards,
    generate_library_card_data,
    create_library_card_image,
)

# Re-export recommendation utilities
from education_system.university_system.modules.domain.academics.services.library.recommendations import (
    get_similar_books,
    get_book_recommendations,
    train_recommendation_model,
    update_recommendation_scores,
)

# Re-export backup utilities
from education_system.university_system.modules.domain.academics.services.library.backup import (
    enhanced_system_backup,
    backup_system,
    auto_backup_scheduler,
    setup_scheduled_backups,
    restore_from_backup,
    library_maintenance,
    cleanup_old_logs,
    quick_system_health_check,
    view_audit_log,
)

# Re-export settings functions
from education_system.university_system.modules.domain.academics.services.library.settings import (
    auth,
    set_auth,
    get_current_user_id,
    enhanced_manage_settings,
    manage_settings,
    get_library_settings,
    update_library_setting,
    validate_setting_value,
    validate_library_configuration,
    manage_user_achievements,
    sync_user_data,
    validate_user_permissions,
    update_reading_goals,
    record_usage_analytics,
    process_fine_payment,
    generate_fine_receipt,
)

# Re-export menu operations
from education_system.university_system.modules.domain.academics.services.library.menu import (
    display_library_menu,
    show_help,
    exit_library_system,
    bulk_import_books,
    bulk_export_books,
    manage_library_events,
)

__all__ = [
    # Classes
    'Book',
    'BookLoan',
    'BookReservation',
    'BookReview',
    'ReadingList',
    # Database
    'get_db_connection',
    'init_library_db',
    'verify_database_structure',
    'repair_database',
    'log_audit_event',
    # Book CRUD
    'fetch_book_metadata',
    'assess_reading_level',
    'enhanced_add_book',
    'add_book',
    'enhanced_update_book',
    'update_book',
    'delete_book',
    'enhanced_view_book_details',
    'view_book_details',
    'list_all_books',
    # Search
    'enhanced_search_books',
    'search_books',
    'advanced_search_interface',
    'execute_advanced_search',
    'display_search_results',
    'save_search_query',
    'load_saved_searches',
    # Circulation
    'check_loan_eligibility',
    'check_reading_level_compatibility',
    'enhanced_checkout_book',
    'checkout_book',
    'enhanced_return_book',
    'return_book',
    'renew_book',
    'reserve_book',
    'manage_reservations',
    'view_overdue_books',
    'view_loan_history',
    # Reading Lists
    'manage_reading_lists',
    'manage_reading_list_items',
    'add_to_reading_list',
    'view_reading_list_details',
    'share_reading_list',
    'import_reading_list',
    # Reviews
    'rate_and_review_book',
    'moderate_review_content',
    # Digital Library
    'manage_digital_library',
    'download_digital_resource',
    'check_digital_access_permission',
    'manage_digital_access_permissions',
    # Reports
    'generate_circulation_report',
    'generate_inventory_report',
    'generate_user_activity_report',
    'generate_analytics_dashboard',
    'generate_detailed_analytics_report',
    'generate_html_analytics_report',
    'generate_enhanced_reports',
    'generate_library_statistics_export',
    'library_statistics_dashboard',
    'generate_reports',
    # Notifications
    'automated_notifications',
    'send_enhanced_checkout_notification',
    'send_overdue_notification',
    'send_due_date_reminder',
    'send_reservation_confirmation',
    'send_reservation_available_notification',
    'send_generic_email_notification',
    'send_email_notification',
    'send_sms_notification',
    'configure_notification_settings',
    # Barcode
    'generate_barcode',
    'generate_qr_code',
    'scan_barcode',
    'process_scanned_barcode',
    'print_barcode_labels',
    'generate_library_cards',
    'generate_library_card_data',
    'create_library_card_image',
    # Recommendations
    'get_similar_books',
    'get_book_recommendations',
    'train_recommendation_model',
    'update_recommendation_scores',
    # Backup
    'enhanced_system_backup',
    'backup_system',
    'auto_backup_scheduler',
    'setup_scheduled_backups',
    'restore_from_backup',
    'library_maintenance',
    'cleanup_old_logs',
    'quick_system_health_check',
    'view_audit_log',
    # Settings
    'auth',
    'set_auth',
    'get_current_user_id',
    'enhanced_manage_settings',
    'manage_settings',
    'get_library_settings',
    'update_library_setting',
    'validate_setting_value',
    'validate_library_configuration',
    'manage_user_achievements',
    'sync_user_data',
    'validate_user_permissions',
    'update_reading_goals',
    'record_usage_analytics',
    'process_fine_payment',
    'generate_fine_receipt',
    # Menu
    'display_library_menu',
    'show_help',
    'exit_library_system',
    'bulk_import_books',
    'bulk_export_books',
    'manage_library_events',
]