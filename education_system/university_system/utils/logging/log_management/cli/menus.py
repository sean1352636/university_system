"""Main menu display functions for log management CLI."""

from education_system.university_system.utils.logging.log_management.manager import get_log_manager

from education_system.university_system.utils.logging.log_management.cli.views import view_recent_logs, search_logs_basic, generate_basic_report, basic_config_menu
from education_system.university_system.utils.logging.log_management.cli.dashboard import (
    display_activity_dashboard, generate_activity_summary_menu,
    user_activity_report_menu, create_charts_menu
)
from education_system.university_system.utils.logging.log_management.cli.search import advanced_search_menu, saved_searches_menu
from education_system.university_system.utils.logging.log_management.cli.realtime import real_time_monitor_menu, view_alerts_menu
from education_system.university_system.utils.logging.log_management.cli.security_analysis import security_analysis_menu
from education_system.university_system.utils.logging.log_management.cli.retention_ops import retention_settings_menu, integrity_check_menu, anonymize_data_menu
from education_system.university_system.utils.logging.log_management.cli.export import enhanced_export_menu, bulk_operations_menu
from education_system.university_system.utils.logging.log_management.cli.api_mgmt import api_management_menu
from education_system.university_system.utils.logging.log_management.cli.db_maintenance import database_maintenance_menu
from education_system.university_system.utils.logging.log_management.cli.performance import performance_metrics_menu
from education_system.university_system.utils.logging.log_management.cli.scheduled_reports import scheduled_reports_menu


def display_log_management_menu(auth):
    """Display the basic log management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access log management.")
        return

    if not auth.check_permission('system_config') and not auth.check_permission('view_logs'):
        print("You don't have permission to access log management.")
        return

    # Initialize log manager if needed
    log_manager = get_log_manager()

    while True:
        print("\n" + "="*50)
        print("LOG MANAGEMENT SYSTEM")
        print("="*50)
        print("1. View Recent Activity Logs")
        print("2. Search Activity Logs")
        print("3. Generate Activity Report")
        print("4. System Configuration")
        print("5. Enhanced Log Management")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            view_recent_logs(log_manager, auth)
        elif choice == '2':
            search_logs_basic(log_manager, auth)
        elif choice == '3':
            generate_basic_report(log_manager, auth)
        elif choice == '4':
            basic_config_menu(log_manager, auth)
        elif choice == '5':
            display_enhanced_log_menu(log_manager, auth)
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")


def display_enhanced_log_menu(log_manager, auth):
    """Enhanced log management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access log management.")
        return

    if not auth.check_permission('system_config') and not auth.check_permission('view_logs'):
        print("You don't have permission to access log management.")
        return

    while True:
        print("\n" + "="*60)
        print("ENHANCED LOG MANAGEMENT SYSTEM")
        print("="*60)
        print("\U0001f4ca ANALYTICS & REPORTS")
        print("1.  Activity Dashboard")
        print("2.  Generate Activity Summary")
        print("3.  User Activity Report")
        print("4.  Create Activity Charts")
        print("5.  Scheduled Reports")

        print("\n\U0001f50d SEARCH & MONITORING")
        print("6.  Advanced Log Search")
        print("7.  Saved Searches")
        print("8.  Real-time Monitor")
        print("9.  View Alerts")

        print("\n\U0001f512 SECURITY & COMPLIANCE")
        print("10. Security Analysis")
        print("11. Data Retention Settings")
        print("12. Log Integrity Check")
        print("13. Anonymize Data")

        print("\n\U0001f4e4 EXPORT & INTEGRATION")
        print("14. Enhanced Export")
        print("15. Bulk Operations")
        print("16. API Management")

        print("\n\u2699\ufe0f  ADMINISTRATION")
        print("17. System Configuration")
        print("18. Database Maintenance")
        print("19. Performance Metrics")
        print("20. Return to Main Menu")

        choice = input("\nEnter your choice (1-20): ")

        try:
            if choice == '1':
                display_activity_dashboard(log_manager, auth)
            elif choice == '2':
                generate_activity_summary_menu(log_manager, auth)
            elif choice == '3':
                user_activity_report_menu(log_manager, auth)
            elif choice == '4':
                create_charts_menu(log_manager, auth)
            elif choice == '5':
                scheduled_reports_menu(log_manager, auth)
            elif choice == '6':
                advanced_search_menu(log_manager, auth)
            elif choice == '7':
                saved_searches_menu(log_manager, auth)
            elif choice == '8':
                real_time_monitor_menu(log_manager, auth)
            elif choice == '9':
                view_alerts_menu(log_manager, auth)
            elif choice == '10':
                security_analysis_menu(log_manager, auth)
            elif choice == '11':
                retention_settings_menu(log_manager, auth)
            elif choice == '12':
                integrity_check_menu(log_manager, auth)
            elif choice == '13':
                anonymize_data_menu(log_manager, auth)
            elif choice == '14':
                enhanced_export_menu(log_manager, auth)
            elif choice == '15':
                bulk_operations_menu(log_manager, auth)
            elif choice == '16':
                api_management_menu(log_manager, auth)
            elif choice == '17':
                system_config_menu(log_manager, auth)
            elif choice == '18':
                database_maintenance_menu(log_manager, auth)
            elif choice == '19':
                performance_metrics_menu(log_manager, auth)
            elif choice == '20':
                return
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")


def system_config_menu(log_manager, auth):
    """System configuration menu (delegates to basic_config_menu)"""
    basic_config_menu(log_manager, auth)
