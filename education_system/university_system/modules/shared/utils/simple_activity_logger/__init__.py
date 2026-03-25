# simple_activity_logger package
# Re-exports everything for backward compatibility with the old single-file module.

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogLevel, OutputFormat, SecurityLevel, LogEntry
from education_system.university_system.modules.shared.utils.simple_activity_logger.security import PIIDetector, SecurityMonitor
from education_system.university_system.modules.shared.utils.simple_activity_logger.storage import LogRotationManager, DatabaseManager, DatabaseLogger
from education_system.university_system.modules.shared.utils.simple_activity_logger.cloud import CloudIntegration
from education_system.university_system.modules.shared.utils.simple_activity_logger.analytics import AnalyticsEngine, _log_detail
from education_system.university_system.modules.shared.utils.simple_activity_logger.logger import EnhancedActivityLogger
from education_system.university_system.modules.shared.utils.simple_activity_logger.decorators import (
    enhanced_log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_admin_action,
    log_menu_navigation,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger.plugins import (
    LoggerPlugin,
    PluginManager,
    SlackNotificationPlugin,
    MetricsCollectionPlugin,
    EmailNotificationPlugin,
    AuditTrailPlugin,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger.module_api import (
    logger,
    plugin_manager,
    log_activity,
    log_login,
    log_logout,
    log_dynamic_activity,
    load_logger_config,
    get_logger_instance,
    register_plugin,
    unregister_plugin,
    get_plugin_status,
    create_default_config,
)

__all__ = [
    # Models
    'LogLevel', 'OutputFormat', 'SecurityLevel', 'LogEntry',
    # Security
    'PIIDetector', 'SecurityMonitor',
    # Storage
    'LogRotationManager', 'DatabaseManager', 'DatabaseLogger',
    # Cloud
    'CloudIntegration',
    # Analytics
    'AnalyticsEngine', '_log_detail',
    # Logger
    'EnhancedActivityLogger',
    # Decorators
    'enhanced_log_activity',
    'log_create', 'log_read', 'log_update', 'log_delete',
    'log_search', 'log_export', 'log_admin_action', 'log_menu_navigation',
    # Plugins
    'LoggerPlugin', 'PluginManager',
    'SlackNotificationPlugin', 'MetricsCollectionPlugin',
    'EmailNotificationPlugin', 'AuditTrailPlugin',
    # Module API
    'logger', 'plugin_manager',
    'log_activity', 'log_login', 'log_logout', 'log_dynamic_activity',
    'load_logger_config', 'get_logger_instance',
    'register_plugin', 'unregister_plugin', 'get_plugin_status',
    'create_default_config',
]
