"""
Integration Marketplace Core Service

Integration catalog, installation management, credentials,
sync logs, data mappings, webhooks, and usage analytics.

Extended with:
- Search & Discovery
- Bulk Operations
- Import/Export
- Reports & Dashboards
- Security & Credentials Management
- Scheduling & Automation
- Validation & Testing
- Data Mapping Tools
- Notifications & Alerts
"""

# Core manager classes
from .catalog import IntegrationCatalogManager
from .installation import InstallationManager
from .credentials import CredentialManager
from .sync import SyncManager
from .data_mapping import DataMappingManager
from .webhooks import WebhookManager

# Feature manager classes
from .search_discovery import SearchDiscoveryManager
from .bulk_operations import BulkOperationsManager
from .import_export import ImportExportManager
from .reports import ReportsDashboardManager
from .security import SecurityCredentialsManager
from .scheduling import SchedulingManager
from .validation import ValidationTestingManager
from .mapping_tools import DataMappingToolsManager
from .notifications import NotificationsAlertManager

# CLI Functions - Search & Discovery
from .search_discovery import (
    search_catalog, filter_by_rating, filter_by_compatibility,
    find_similar_integrations, search_sync_logs, advanced_filter_dialog,
)

# CLI Functions - Bulk Operations
from .bulk_operations import (
    bulk_install_integrations, bulk_uninstall_integrations,
    bulk_enable_integrations, bulk_disable_integrations,
    bulk_sync_integrations, bulk_update_credentials,
)

# CLI Functions - Import/Export
from .import_export import (
    export_catalog_to_json, import_integrations_from_json,
    export_configuration_bundle, import_configuration_bundle,
    export_sync_report_pdf, export_mappings_to_excel,
)

# CLI Functions - Reports & Dashboards
from .reports import (
    show_dashboard_overview, generate_health_report, show_error_analysis,
    generate_usage_trend_chart, show_api_call_statistics,
    compare_integration_performance, generate_compliance_report,
)

# CLI Functions - Security & Credentials
from .security import (
    rotate_api_credentials, check_credential_expiry, validate_credentials,
    encrypt_export_credentials, audit_credential_access, revoke_all_tokens,
)

# CLI Functions - Scheduling & Automation
from .scheduling import (
    schedule_sync, view_scheduled_tasks, pause_scheduled_syncs,
    set_maintenance_window, configure_retry_policy,
)

# CLI Functions - Validation & Testing
from .validation import (
    test_integration_connection, validate_mapping_rules, dry_run_sync,
    test_webhook_delivery, validate_json_configuration, run_integration_diagnostics,
)

# CLI Functions - Data Mapping Tools
from .mapping_tools import (
    auto_detect_mappings, preview_transformation,
    duplicate_mapping_set, import_mappings_from_template,
)

# CLI Functions - Notifications & Alerts
from .notifications import (
    configure_alert_rules, subscribe_to_notifications,
    view_notification_history, test_notification_channel,
)

# Menu & GUI
from .menu import display_integration_marketplace_menu, launch_integration_marketplace_gui


__all__ = [
    # Manager Classes
    'IntegrationCatalogManager', 'InstallationManager', 'CredentialManager',
    'SyncManager', 'DataMappingManager', 'WebhookManager',
    'SearchDiscoveryManager', 'BulkOperationsManager', 'ImportExportManager',
    'ReportsDashboardManager', 'SecurityCredentialsManager', 'SchedulingManager',
    'ValidationTestingManager', 'DataMappingToolsManager', 'NotificationsAlertManager',

    # CLI Functions - Search & Discovery (10-15)
    'search_catalog', 'filter_by_rating', 'filter_by_compatibility',
    'find_similar_integrations', 'search_sync_logs', 'advanced_filter_dialog',

    # CLI Functions - Bulk Operations (20-25)
    'bulk_install_integrations', 'bulk_uninstall_integrations',
    'bulk_enable_integrations', 'bulk_disable_integrations',
    'bulk_sync_integrations', 'bulk_update_credentials',

    # CLI Functions - Import/Export (30-35)
    'export_catalog_to_json', 'import_integrations_from_json',
    'export_configuration_bundle', 'import_configuration_bundle',
    'export_sync_report_pdf', 'export_mappings_to_excel',

    # CLI Functions - Reports & Dashboards (40-46)
    'show_dashboard_overview', 'generate_health_report', 'show_error_analysis',
    'generate_usage_trend_chart', 'show_api_call_statistics',
    'compare_integration_performance', 'generate_compliance_report',

    # CLI Functions - Security & Credentials (50-55)
    'rotate_api_credentials', 'check_credential_expiry', 'validate_credentials',
    'encrypt_export_credentials', 'audit_credential_access', 'revoke_all_tokens',

    # CLI Functions - Scheduling & Automation (60-64)
    'schedule_sync', 'view_scheduled_tasks', 'pause_scheduled_syncs',
    'set_maintenance_window', 'configure_retry_policy',

    # CLI Functions - Validation & Testing (70-75)
    'test_integration_connection', 'validate_mapping_rules', 'dry_run_sync',
    'test_webhook_delivery', 'validate_json_configuration', 'run_integration_diagnostics',

    # CLI Functions - Data Mapping Tools (80-83)
    'auto_detect_mappings', 'preview_transformation',
    'duplicate_mapping_set', 'import_mappings_from_template',

    # CLI Functions - Notifications & Alerts (90-93)
    'configure_alert_rules', 'subscribe_to_notifications',
    'view_notification_history', 'test_notification_channel',

    # Menu & GUI
    'display_integration_marketplace_menu',
    'launch_integration_marketplace_gui',
]
