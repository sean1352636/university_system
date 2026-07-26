# simple_activity_logger package
# Re-exports everything for backward compatibility with the old single-file module.

from education_system.systems.university.infrastructure.utils.activity_logger.models import LogLevel, OutputFormat, SecurityLevel, LogEntry
from education_system.systems.university.infrastructure.utils.activity_logger.security import PIIDetector, SecurityMonitor
from education_system.systems.university.infrastructure.utils.activity_logger.storage import LogRotationManager, DatabaseManager, DatabaseLogger
from education_system.systems.university.infrastructure.utils.activity_logger.cloud import CloudIntegration
from education_system.systems.university.infrastructure.utils.activity_logger.analytics import AnalyticsEngine, _log_detail
from education_system.systems.university.infrastructure.utils.activity_logger.logger import EnhancedActivityLogger
from education_system.systems.university.infrastructure.utils.activity_logger.decorators import enhanced_log_activity as _decorator_enhanced_log_activity
from education_system.systems.university.infrastructure.utils.activity_logger.plugins import (
    LoggerPlugin,
    PluginManager,
    SlackNotificationPlugin,
    MetricsCollectionPlugin,
    EmailNotificationPlugin,
    AuditTrailPlugin,
)
from education_system.systems.university.infrastructure.utils.activity_logger.module_api import (
    logger,
    plugin_manager,
    load_logger_config,
    get_logger_instance,
    register_plugin,
    unregister_plugin,
    get_plugin_status,
    create_default_config,
)


def enhanced_log_activity(*args, **kwargs):
    return _decorator_enhanced_log_activity(*args, **kwargs)


def log_create(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_read(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_update(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_delete(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_search(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_export(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_admin_action(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_menu_navigation(*args, **kwargs):
    return enhanced_log_activity(*args, **kwargs)


def log_activity(*args, **kwargs):
    return get_logger_instance().log_activity(*args, **kwargs)


def log_login(user_id, username, role, status="success", details=None):
    return logger.log_activity(
        user_id, username, role, "login", "authentication",
        details, status, LogLevel.INFO, SecurityLevel.LOW
    )


def log_logout(user_id, username, role):
    return logger.log_activity(
        user_id, username, role, "logout", "authentication",
        status="success", log_level=LogLevel.INFO
    )


def log_dynamic_activity(action, module, details=None, **kwargs):
    return get_logger_instance().log_activity(
        "system", "system", "system", action, module, details, **kwargs
    )


__all__ = [
    "LogLevel", "OutputFormat", "SecurityLevel", "LogEntry",
    "PIIDetector", "SecurityMonitor",
    "LogRotationManager", "DatabaseManager", "DatabaseLogger",
    "CloudIntegration",
    "AnalyticsEngine", "_log_detail",
    "EnhancedActivityLogger",
    "enhanced_log_activity",
    "log_create", "log_read", "log_update", "log_delete",
    "log_search", "log_export", "log_admin_action", "log_menu_navigation",
    "LoggerPlugin", "PluginManager",
    "SlackNotificationPlugin", "MetricsCollectionPlugin",
    "EmailNotificationPlugin", "AuditTrailPlugin",
    "logger", "plugin_manager",
    "log_activity", "log_login", "log_logout", "log_dynamic_activity",
    "load_logger_config", "get_logger_instance",
    "register_plugin", "unregister_plugin", "get_plugin_status",
    "create_default_config",
]
