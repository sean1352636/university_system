"""
Enhanced Library Management System - GUI Version
Modular package that composes LibraryGUI class from multiple modules
"""

from education_system.university_system.modules.domain.academics.gui.library.base import LibraryGUI

# Import all functions from submodules and bind them to LibraryGUI class
import sys

# Debug: Track binding execution
_BINDING_DEBUG = False  # Set to True to enable debug output
if _BINDING_DEBUG:
    print("library/__init__.py: Starting method bindings...", file=sys.stderr)

# Dashboard functions
from education_system.university_system.modules.domain.academics.gui.library.dashboard import (
    show_dashboard, create_statistics_display, get_library_statistics,
    create_activity_display, get_recent_activity, _get_audit_log_columns,
    _get_student_columns, show_statistics_dashboard
)
LibraryGUI.show_dashboard = show_dashboard
if _BINDING_DEBUG:
    print(f"  ✓ Bound show_dashboard: {hasattr(LibraryGUI, 'show_dashboard')}", file=sys.stderr)
LibraryGUI.create_statistics_display = create_statistics_display
LibraryGUI.get_library_statistics = get_library_statistics
LibraryGUI.create_activity_display = create_activity_display
LibraryGUI.get_recent_activity = get_recent_activity
LibraryGUI._get_audit_log_columns = _get_audit_log_columns
LibraryGUI._get_student_columns = _get_student_columns
LibraryGUI.show_statistics_dashboard = show_statistics_dashboard

# Books functions
from education_system.university_system.modules.domain.academics.gui.library.books import (
    show_all_books, create_books_context_menu, show_books_context_menu,
    load_books_data, search_books_table, refresh_books_table,
    on_book_double_click, view_selected_book, show_book_details,
    get_book_details, generate_book_barcode, create_loan_history_table,
    show_add_book, add_book_dialog, lookup_isbn_data,
    _fetch_from_openlibrary, _fetch_from_google_books, _populate_book_data,
    _handle_lookup_error, save_new_book, add_book_to_database,
    edit_selected_book, delete_selected_book, view_book_loan_history,
    checkout_book_dialog, reserve_book_dialog, edit_book_dialog,
    show_book_reviews
)
LibraryGUI.show_all_books = show_all_books
LibraryGUI.create_books_context_menu = create_books_context_menu
LibraryGUI.show_books_context_menu = show_books_context_menu
LibraryGUI.load_books_data = load_books_data
LibraryGUI.search_books_table = search_books_table
LibraryGUI.refresh_books_table = refresh_books_table
LibraryGUI.on_book_double_click = on_book_double_click
LibraryGUI.view_selected_book = view_selected_book
LibraryGUI.show_book_details = show_book_details
LibraryGUI.get_book_details = get_book_details
LibraryGUI.generate_book_barcode = generate_book_barcode
LibraryGUI.create_loan_history_table = create_loan_history_table
LibraryGUI.show_add_book = show_add_book
LibraryGUI.add_book_dialog = add_book_dialog
LibraryGUI.lookup_isbn_data = lookup_isbn_data
LibraryGUI._fetch_from_openlibrary = _fetch_from_openlibrary
LibraryGUI._fetch_from_google_books = _fetch_from_google_books
LibraryGUI._populate_book_data = _populate_book_data
LibraryGUI._handle_lookup_error = _handle_lookup_error
LibraryGUI.save_new_book = save_new_book
LibraryGUI.add_book_to_database = add_book_to_database
LibraryGUI.edit_selected_book = edit_selected_book
LibraryGUI.delete_selected_book = delete_selected_book
LibraryGUI.view_book_loan_history = view_book_loan_history
LibraryGUI.checkout_book_dialog = checkout_book_dialog
LibraryGUI.reserve_book_dialog = reserve_book_dialog
LibraryGUI.edit_book_dialog = edit_book_dialog
LibraryGUI.show_book_reviews = show_book_reviews

# Search functions
from education_system.university_system.modules.domain.academics.gui.library.search import (
    show_search_books, execute_search, clear_search, save_search,
    on_search_result_double_click, show_advanced_search, show_advanced_search_gui
)
LibraryGUI.show_search_books = show_search_books
LibraryGUI.execute_search = execute_search
LibraryGUI.clear_search = clear_search
LibraryGUI.save_search = save_search
LibraryGUI.on_search_result_double_click = on_search_result_double_click
LibraryGUI.show_advanced_search = show_advanced_search
LibraryGUI.show_advanced_search_gui = show_advanced_search_gui

# Checkout/Return functions
from education_system.university_system.modules.domain.academics.gui.library.checkout_return import (
    show_checkout, checkout_dialog, lookup_checkout_book, verify_checkout_user,
    check_checkout_ready, process_checkout, checkout_book_database,
    checkout_selected_book, show_return, return_dialog, lookup_return_book,
    process_return, return_book_database, enhanced_checkout_book_gui,
    enhanced_return_book_gui, renew_book_gui, view_loan_history_gui,
    _send_checkout_emails, _send_return_emails,
)
LibraryGUI.show_checkout = show_checkout
LibraryGUI.checkout_dialog = checkout_dialog
LibraryGUI.lookup_checkout_book = lookup_checkout_book
LibraryGUI.verify_checkout_user = verify_checkout_user
LibraryGUI.check_checkout_ready = check_checkout_ready
LibraryGUI.process_checkout = process_checkout
LibraryGUI.checkout_book_database = checkout_book_database
LibraryGUI.checkout_selected_book = checkout_selected_book
LibraryGUI.show_return = show_return
LibraryGUI.return_dialog = return_dialog
LibraryGUI.lookup_return_book = lookup_return_book
LibraryGUI.process_return = process_return
LibraryGUI.return_book_database = return_book_database
LibraryGUI.enhanced_checkout_book_gui = enhanced_checkout_book_gui
LibraryGUI.enhanced_return_book_gui = enhanced_return_book_gui
LibraryGUI.renew_book_gui = renew_book_gui
LibraryGUI.view_loan_history_gui = view_loan_history_gui
LibraryGUI._send_checkout_emails = _send_checkout_emails
LibraryGUI._send_return_emails = _send_return_emails

# Reservations functions
from education_system.university_system.modules.domain.academics.gui.library.reservations import (
    show_reservations, load_reservations, refresh_reservations,
    new_reservation_dialog, create_reservation_database, cancel_reservation,
    reserve_selected_book, reserve_book_gui, manage_reservations_gui,
    _send_reservation_email, notify_reserved_users_on_return
)
LibraryGUI.show_reservations = show_reservations
LibraryGUI.load_reservations = load_reservations
LibraryGUI.refresh_reservations = refresh_reservations
LibraryGUI.new_reservation_dialog = new_reservation_dialog
LibraryGUI.create_reservation_database = create_reservation_database
LibraryGUI.cancel_reservation = cancel_reservation
LibraryGUI._send_reservation_email = _send_reservation_email
LibraryGUI.notify_reserved_users_on_return = notify_reserved_users_on_return
LibraryGUI.reserve_selected_book = reserve_selected_book
LibraryGUI.reserve_book_gui = reserve_book_gui
LibraryGUI.manage_reservations_gui = manage_reservations_gui

# Reports functions
from education_system.university_system.modules.domain.academics.gui.library.reports import (
    show_reports, generate_collection_report, _show_report_message,
    _show_report_not_available, get_collection_report_data,
    generate_circulation_report, get_circulation_report_data,
    generate_overdue_report, get_overdue_report_data,
    generate_user_activity_report, generate_popular_books_report,
    generate_fine_report, generate_card_usage_report, generate_health_report,
    generate_maintenance_report, email_report_to_admin, save_report_to_file,
    show_report_in_window, open_current_report_window
)
LibraryGUI.show_reports = show_reports
LibraryGUI.generate_collection_report = generate_collection_report
LibraryGUI._show_report_message = _show_report_message
LibraryGUI._show_report_not_available = _show_report_not_available
LibraryGUI.get_collection_report_data = get_collection_report_data
LibraryGUI.generate_circulation_report = generate_circulation_report
LibraryGUI.get_circulation_report_data = get_circulation_report_data
LibraryGUI.generate_overdue_report = generate_overdue_report
LibraryGUI.get_overdue_report_data = get_overdue_report_data
LibraryGUI.generate_user_activity_report = generate_user_activity_report
LibraryGUI.generate_popular_books_report = generate_popular_books_report
LibraryGUI.generate_fine_report = generate_fine_report
LibraryGUI.generate_card_usage_report = generate_card_usage_report
LibraryGUI.generate_health_report = generate_health_report
LibraryGUI.generate_maintenance_report = generate_maintenance_report
LibraryGUI.email_report_to_admin = email_report_to_admin
LibraryGUI.save_report_to_file = save_report_to_file
LibraryGUI.show_report_in_window = show_report_in_window
LibraryGUI.open_current_report_window = open_current_report_window

# Also add generate_circulation_report_gui from reports
from education_system.university_system.modules.domain.academics.gui.library.reports import generate_circulation_report_gui
LibraryGUI.generate_circulation_report_gui = generate_circulation_report_gui

# Settings functions
from education_system.university_system.modules.domain.academics.gui.library.settings import (
    show_settings, create_library_settings_tab, create_system_settings_tab,
    create_user_settings_tab, save_library_settings, save_system_settings,
    save_user_settings, show_user_preferences, save_user_preferences,
    reset_user_preferences, enhanced_settings_management_gui,
    export_settings_gui, import_settings_gui, reset_settings_to_default_gui,
    backup_settings_only_gui
)
LibraryGUI.show_settings = show_settings
LibraryGUI.create_library_settings_tab = create_library_settings_tab
LibraryGUI.create_system_settings_tab = create_system_settings_tab
LibraryGUI.create_user_settings_tab = create_user_settings_tab
LibraryGUI.save_library_settings = save_library_settings
LibraryGUI.save_system_settings = save_system_settings
LibraryGUI.save_user_settings = save_user_settings
LibraryGUI.show_user_preferences = show_user_preferences
LibraryGUI.save_user_preferences = save_user_preferences
LibraryGUI.reset_user_preferences = reset_user_preferences
LibraryGUI.enhanced_settings_management_gui = enhanced_settings_management_gui
LibraryGUI.export_settings_gui = export_settings_gui
LibraryGUI.import_settings_gui = import_settings_gui
LibraryGUI.reset_settings_to_default_gui = reset_settings_to_default_gui
LibraryGUI.backup_settings_only_gui = backup_settings_only_gui

# Reading lists functions
from education_system.university_system.modules.domain.academics.gui.library.reading_lists import (
    show_reading_lists, create_reading_lists_context_menu,
    show_reading_lists_context_menu, load_reading_lists, refresh_reading_lists,
    import_reading_list_dialog, create_reading_list_dialog, create_reading_list_database,
    view_reading_list_details, get_reading_list_details, load_reading_list_items,
    manage_reading_lists_gui, create_reading_list_gui, view_reading_list_details_gui
)
LibraryGUI.show_reading_lists = show_reading_lists
LibraryGUI.create_reading_lists_context_menu = create_reading_lists_context_menu
LibraryGUI.show_reading_lists_context_menu = show_reading_lists_context_menu
LibraryGUI.load_reading_lists = load_reading_lists
LibraryGUI.refresh_reading_lists = refresh_reading_lists
LibraryGUI.import_reading_list_dialog = import_reading_list_dialog
LibraryGUI.create_reading_list_dialog = create_reading_list_dialog
LibraryGUI.create_reading_list_database = create_reading_list_database
LibraryGUI.view_reading_list_details = view_reading_list_details
LibraryGUI.get_reading_list_details = get_reading_list_details
LibraryGUI.load_reading_list_items = load_reading_list_items
LibraryGUI.manage_reading_lists_gui = manage_reading_lists_gui
LibraryGUI.create_reading_list_gui = create_reading_list_gui
LibraryGUI.view_reading_list_details_gui = view_reading_list_details_gui

# Reviews functions
from education_system.university_system.modules.domain.academics.gui.library.reviews import (
    show_reviews, load_reviews, show_my_reviews, show_all_reviews,
    refresh_reviews, write_review_dialog, submit_review_database,
    view_review_details, publish_all_reviews, rate_and_review_book_gui
)
LibraryGUI.show_reviews = show_reviews
LibraryGUI.load_reviews = load_reviews
LibraryGUI.show_my_reviews = show_my_reviews
LibraryGUI.show_all_reviews = show_all_reviews
LibraryGUI.refresh_reviews = refresh_reviews
LibraryGUI.write_review_dialog = write_review_dialog
LibraryGUI.submit_review_database = submit_review_database
LibraryGUI.view_review_details = view_review_details
LibraryGUI.publish_all_reviews = publish_all_reviews
LibraryGUI.rate_and_review_book_gui = rate_and_review_book_gui

# Overdue functions
from education_system.university_system.modules.domain.academics.gui.library.overdue import (
    show_overdue_books, create_overdue_context_menu, show_overdue_context_menu,
    load_overdue_books, refresh_overdue_books, send_overdue_reminders,
    send_overdue_notifications, process_overdue_fines, calculate_overdue_fines,
    export_overdue_report, create_overdue_export, check_and_display_late_fees
)
LibraryGUI.show_overdue_books = show_overdue_books
LibraryGUI.create_overdue_context_menu = create_overdue_context_menu
LibraryGUI.show_overdue_context_menu = show_overdue_context_menu
LibraryGUI.load_overdue_books = load_overdue_books
LibraryGUI.refresh_overdue_books = refresh_overdue_books
LibraryGUI.send_overdue_reminders = send_overdue_reminders
LibraryGUI.send_overdue_notifications = send_overdue_notifications
LibraryGUI.process_overdue_fines = process_overdue_fines
LibraryGUI.calculate_overdue_fines = calculate_overdue_fines
LibraryGUI.export_overdue_report = export_overdue_report
LibraryGUI.create_overdue_export = create_overdue_export
LibraryGUI.check_and_display_late_fees = check_and_display_late_fees

# Fines functions
from education_system.university_system.modules.domain.academics.gui.library.fines import (
    show_fine_management, load_user_fines, process_fine_payment,
    pay_fine_from_finance_account, _show_topup_dialog, waive_all_fines,
    view_fine_history, generate_fine_statistics_report, adjust_fine_amount,
    export_fines_to_csv, _save_text_report, _record_fine_payment,
    _record_library_payment_in_finance,
    pay_fine_via_finance, _process_library_fine_payment,
    open_finance_payment_for_user, process_fine_payment_gui, generate_fine_receipt_gui,
    refund_fine_dialog, _show_user_refund_details, _process_library_fine_refund,
    _send_refund_receipt_email
)
LibraryGUI.show_fine_management = show_fine_management
LibraryGUI.load_user_fines = load_user_fines
LibraryGUI.process_fine_payment = process_fine_payment
LibraryGUI.pay_fine_from_finance_account = pay_fine_from_finance_account
LibraryGUI._show_topup_dialog = _show_topup_dialog
LibraryGUI.waive_all_fines = waive_all_fines
LibraryGUI.view_fine_history = view_fine_history
LibraryGUI.generate_fine_statistics_report = generate_fine_statistics_report
LibraryGUI.adjust_fine_amount = adjust_fine_amount
LibraryGUI.export_fines_to_csv = export_fines_to_csv
LibraryGUI._save_text_report = _save_text_report
LibraryGUI._record_fine_payment = _record_fine_payment
LibraryGUI._record_library_payment_in_finance = _record_library_payment_in_finance
LibraryGUI.pay_fine_via_finance = pay_fine_via_finance
LibraryGUI._process_library_fine_payment = _process_library_fine_payment
LibraryGUI.open_finance_payment_for_user = open_finance_payment_for_user
LibraryGUI.process_fine_payment_gui = process_fine_payment_gui
LibraryGUI.generate_fine_receipt_gui = generate_fine_receipt_gui
LibraryGUI.refund_fine_dialog = refund_fine_dialog
LibraryGUI._show_user_refund_details = _show_user_refund_details
LibraryGUI._process_library_fine_refund = _process_library_fine_refund
LibraryGUI._send_refund_receipt_email = _send_refund_receipt_email

# Maintenance functions
from education_system.university_system.modules.domain.academics.gui.library.maintenance import (
    optimize_database, check_database_integrity, show_audit_log,
    audit_log_dialog, load_audit_log, library_maintenance_gui,
    cleanup_expired_reservations, update_overdue_status, calculate_fines,
    archive_old_records, check_data_integrity, quick_system_health_check,
    system_health_check_gui, view_audit_log_gui, database_optimization_gui,
    clear_cache_gui, manage_library_events_gui
)
LibraryGUI.optimize_database = optimize_database
LibraryGUI.check_database_integrity = check_database_integrity
LibraryGUI.show_audit_log = show_audit_log
LibraryGUI.audit_log_dialog = audit_log_dialog
LibraryGUI.load_audit_log = load_audit_log
LibraryGUI.library_maintenance_gui = library_maintenance_gui
LibraryGUI.cleanup_expired_reservations = cleanup_expired_reservations
LibraryGUI.update_overdue_status = update_overdue_status
LibraryGUI.calculate_fines = calculate_fines
LibraryGUI.archive_old_records = archive_old_records
LibraryGUI.check_data_integrity = check_data_integrity
LibraryGUI.quick_system_health_check = quick_system_health_check
LibraryGUI.system_health_check_gui = system_health_check_gui
LibraryGUI.view_audit_log_gui = view_audit_log_gui
LibraryGUI.database_optimization_gui = database_optimization_gui
LibraryGUI.clear_cache_gui = clear_cache_gui
LibraryGUI.manage_library_events_gui = manage_library_events_gui

# Barcode and cards functions
from education_system.university_system.modules.domain.academics.gui.library.barcode_cards import (
    show_barcode_generator, generate_barcodes, show_barcode_scanner,
    process_barcode_scan, clear_barcode_scan, show_library_cards_generator,
    bulk_generate_library_cards_gui, generate_library_card_gui, print_library_card_gui
)
LibraryGUI.show_barcode_generator = show_barcode_generator
LibraryGUI.generate_barcodes = generate_barcodes
LibraryGUI.show_barcode_scanner = show_barcode_scanner
LibraryGUI.process_barcode_scan = process_barcode_scan
LibraryGUI.clear_barcode_scan = clear_barcode_scan
LibraryGUI.show_library_cards_generator = show_library_cards_generator
LibraryGUI.bulk_generate_library_cards_gui = bulk_generate_library_cards_gui
LibraryGUI.generate_library_card_gui = generate_library_card_gui
LibraryGUI.print_library_card_gui = print_library_card_gui

# Import/Export functions
from education_system.university_system.modules.domain.academics.gui.library.import_export import (
    import_books_gui, export_books_gui, backup_system_gui, restore_system_gui,
    restore_from_backup, bulk_import_books_gui, _perform_import,
    bulk_export_books_gui, _perform_export, system_backup_gui,
    generate_library_statistics_export
)
LibraryGUI.import_books_gui = import_books_gui
LibraryGUI.export_books_gui = export_books_gui
LibraryGUI.backup_system_gui = backup_system_gui
LibraryGUI.restore_system_gui = restore_system_gui
LibraryGUI.restore_from_backup = restore_from_backup
LibraryGUI.bulk_import_books_gui = bulk_import_books_gui
LibraryGUI._perform_import = _perform_import
LibraryGUI.bulk_export_books_gui = bulk_export_books_gui
LibraryGUI._perform_export = _perform_export
LibraryGUI.system_backup_gui = system_backup_gui
LibraryGUI.generate_library_statistics_export = generate_library_statistics_export

# Digital library functions
from education_system.university_system.modules.domain.academics.gui.library.digital_library import (
    show_digital_library, load_digital_resources, refresh_digital_library,
    add_digital_resource_dialog, browse_digital_file, save_digital_resource,
    add_digital_resource_database, show_digital_library_gui, load_digital_library,
    upload_digital_resource, download_digital_resource_gui,
    manage_digital_access_permissions_gui
)
LibraryGUI.show_digital_library = show_digital_library
LibraryGUI.load_digital_resources = load_digital_resources
LibraryGUI.refresh_digital_library = refresh_digital_library
LibraryGUI.add_digital_resource_dialog = add_digital_resource_dialog
LibraryGUI.browse_digital_file = browse_digital_file
LibraryGUI.save_digital_resource = save_digital_resource
LibraryGUI.add_digital_resource_database = add_digital_resource_database
LibraryGUI.show_digital_library_gui = show_digital_library_gui
LibraryGUI.load_digital_library = load_digital_library
LibraryGUI.upload_digital_resource = upload_digital_resource
LibraryGUI.download_digital_resource_gui = download_digital_resource_gui
LibraryGUI.manage_digital_access_permissions_gui = manage_digital_access_permissions_gui

# Analytics functions
from education_system.university_system.modules.domain.academics.gui.library.analytics import (
    show_advanced_analytics_gui, _create_collection_overview,
    _refresh_collection_overview, _load_collection_overview_data,
    _create_circulation_stats, _create_user_activity, _create_category_analysis,
    export_analytics_report
)
LibraryGUI.show_advanced_analytics_gui = show_advanced_analytics_gui
LibraryGUI._create_collection_overview = _create_collection_overview
LibraryGUI._refresh_collection_overview = _refresh_collection_overview
LibraryGUI._load_collection_overview_data = _load_collection_overview_data
LibraryGUI._create_circulation_stats = _create_circulation_stats
LibraryGUI._create_user_activity = _create_user_activity
LibraryGUI._create_category_analysis = _create_category_analysis
LibraryGUI.export_analytics_report = export_analytics_report

# Notifications functions
from education_system.university_system.modules.domain.academics.gui.library.notifications import (
    _send_library_payment_confirmation_email, _send_email_via_gui,
    _show_library_email_fallback, _send_checkout_confirmation_email,
    _send_return_confirmation_email, send_automated_notifications_gui,
    open_calendar_with_due_dates, add_calendar_button_to_interface
)
LibraryGUI._send_library_payment_confirmation_email = _send_library_payment_confirmation_email
LibraryGUI._send_email_via_gui = _send_email_via_gui
LibraryGUI._show_library_email_fallback = _show_library_email_fallback
LibraryGUI._send_checkout_confirmation_email = _send_checkout_confirmation_email
LibraryGUI._send_return_confirmation_email = _send_return_confirmation_email
LibraryGUI.send_automated_notifications_gui = send_automated_notifications_gui
LibraryGUI.open_calendar_with_due_dates = open_calendar_with_due_dates
LibraryGUI.add_calendar_button_to_interface = add_calendar_button_to_interface

# Help functions
from education_system.university_system.modules.domain.academics.gui.library.help import show_help, show_shortcuts, show_about
LibraryGUI.show_help = show_help
LibraryGUI.show_shortcuts = show_shortcuts
LibraryGUI.show_about = show_about

# Finance functions
from education_system.university_system.modules.domain.academics.gui.library.finance import open_library_finance, LibraryFinanceManager
LibraryGUI.open_library_finance = open_library_finance

# Misc functions
from education_system.university_system.modules.domain.academics.gui.library.misc import load_loan_history
LibraryGUI.load_loan_history = load_loan_history

__all__ = ["LibraryGUI", "LibraryFinanceManager"]
