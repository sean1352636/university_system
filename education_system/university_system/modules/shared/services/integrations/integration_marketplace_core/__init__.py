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

# Database helper re-exported for convenience
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import get_connection

# Core manager classes
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.catalog import IntegrationCatalogManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.installation import InstallationManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.credentials import CredentialManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.sync import SyncManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.data_mapping import DataMappingManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.webhooks import WebhookManager

# Feature manager classes
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.search_discovery import SearchDiscoveryManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.bulk_operations import BulkOperationsManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.import_export import ImportExportManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.reports import ReportsDashboardManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.security import SecurityCredentialsManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.scheduling import SchedulingManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.validation import ValidationTestingManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.mapping_tools import DataMappingToolsManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.notifications import NotificationsAlertManager

# CLI Functions - Search & Discovery
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.search_discovery import (
    search_catalog, filter_by_rating, filter_by_compatibility,
    find_similar_integrations, search_sync_logs, advanced_filter_dialog,
)

# CLI Functions - Bulk Operations
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.bulk_operations import (
    bulk_install_integrations, bulk_uninstall_integrations,
    bulk_enable_integrations, bulk_disable_integrations,
    bulk_sync_integrations, bulk_update_credentials,
)

# CLI Functions - Import/Export
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.import_export import (
    export_catalog_to_json, import_integrations_from_json,
    export_configuration_bundle, import_configuration_bundle,
    export_sync_report_pdf, export_mappings_to_excel,
)

# CLI Functions - Reports & Dashboards
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.reports import (
    show_dashboard_overview, generate_health_report, show_error_analysis,
    generate_usage_trend_chart, show_api_call_statistics,
    compare_integration_performance, generate_compliance_report,
)

# CLI Functions - Security & Credentials
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.security import (
    rotate_api_credentials, check_credential_expiry, validate_credentials,
    encrypt_export_credentials, audit_credential_access, revoke_all_tokens,
)

# CLI Functions - Scheduling & Automation
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.scheduling import (
    schedule_sync, view_scheduled_tasks, pause_scheduled_syncs,
    set_maintenance_window, configure_retry_policy,
)

# CLI Functions - Validation & Testing
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.validation import (
    test_integration_connection, validate_mapping_rules, dry_run_sync,
    test_webhook_delivery, validate_json_configuration, run_integration_diagnostics,
)

# CLI Functions - Data Mapping Tools
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.mapping_tools import (
    auto_detect_mappings, preview_transformation,
    duplicate_mapping_set, import_mappings_from_template,
)

# CLI Functions - Notifications & Alerts
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.notifications import (
    configure_alert_rules, subscribe_to_notifications,
    view_notification_history, test_notification_channel,
)

# Menu & GUI
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.menu import display_integration_marketplace_menu, launch_integration_marketplace_gui


__all__ = [
    # Database helper
    'get_connection',

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
