"""Enhanced Log Management System.

This package provides comprehensive log management capabilities including:
- Database-backed log storage and querying
- Real-time monitoring
- Analytics and reporting
- Security alerts
- Flask REST API
- CLI menus

All public names are re-exported here so existing imports continue to work:
    from education_system.post_18.university_system.infrastructure.logging.log_management import get_log_manager
"""

# Core classes
from education_system.post_18.university_system.infrastructure.logging.log_management.config import LogConfig, config
from education_system.post_18.university_system.infrastructure.logging.log_management.security import LogSecurity
from education_system.post_18.university_system.infrastructure.logging.log_management.database import LogDatabase
from education_system.post_18.university_system.infrastructure.logging.log_management.analytics import LogAnalytics
from education_system.post_18.university_system.infrastructure.logging.log_management.alerts import LogAlerts
from education_system.post_18.university_system.infrastructure.logging.log_management.monitoring import RealTimeMonitor
from education_system.post_18.university_system.infrastructure.logging.log_management.retention import LogRetention
from education_system.post_18.university_system.infrastructure.logging.log_management.manager import EnhancedLogManager, get_log_manager, log_manager

# Flask app and API
from education_system.post_18.university_system.infrastructure.logging.log_management.api import app, FLASK_AVAILABLE

# CLI menus
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.menus import display_log_management_menu, display_enhanced_log_menu

# CLI functions (re-exported for backwards compatibility)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.views import view_recent_logs, search_logs_basic, generate_basic_report, basic_config_menu
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.dashboard import (
    display_activity_dashboard, generate_activity_summary_menu,
    user_activity_report_menu, create_charts_menu
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.search import (
    advanced_search_menu, export_search_results, save_search,
    view_detailed_results, saved_searches_menu
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.realtime import real_time_monitor_menu, view_alerts_menu
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.security_analysis import (
    security_analysis_menu, analyze_failed_logins,
    detect_unusual_activity, audit_admin_actions, analyze_user_behavior
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.retention_ops import retention_settings_menu, integrity_check_menu, anonymize_data_menu
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.export import (
    enhanced_export_menu, export_with_filters, bulk_operations_menu,
    bulk_import_logs, bulk_cleanup_data
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.api_mgmt import api_management_menu, toggle_api, generate_api_key, show_api_docs
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.db_maintenance import (
    database_maintenance_menu, check_database_size, optimize_database,
    rebuild_indexes, vacuum_database, show_database_stats
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.performance import (
    performance_metrics_menu, test_query_performance, test_insert_performance,
    show_system_resources, test_database_response_times,
    test_simple_query, test_complex_query, test_insert_operation
)
from education_system.post_18.university_system.infrastructure.logging.log_management.cli.scheduled_reports import (
    scheduled_reports_menu, setup_daily_email_report, setup_weekly_report,
    setup_security_alerts, view_scheduled_tasks
)

__all__ = [
    # Core classes
    'LogConfig', 'config',
    'LogSecurity',
    'LogDatabase',
    'LogAnalytics',
    'LogAlerts',
    'RealTimeMonitor',
    'LogRetention',
    'EnhancedLogManager', 'get_log_manager', 'log_manager',
    # Flask
    'app', 'FLASK_AVAILABLE',
    # CLI
    'display_log_management_menu', 'display_enhanced_log_menu',
]
