from education_system.systems.university.infrastructure.utils.activity_logger.plugins.base import LoggerPlugin, PluginManager
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.slack import SlackNotificationPlugin
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.metrics import MetricsCollectionPlugin
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.email import EmailNotificationPlugin
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.audit import AuditTrailPlugin

__all__ = [
    'LoggerPlugin',
    'PluginManager',
    'SlackNotificationPlugin',
    'MetricsCollectionPlugin',
    'EmailNotificationPlugin',
    'AuditTrailPlugin',
]
