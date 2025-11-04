"""
University System Shared Utilities

This module provides common utilities used across the university system.
"""

from university_system.modules.shared.utils import state
from university_system.modules.shared.utils import templates
from university_system.modules.shared.utils.config import (
    CONFIG_SCHEMA,
    DEFAULT_CONFIG,
    config,
    validate_email_config,
    load_config,
    save_config,
    validate_config,
    configure_email_settings,
    test_email_configuration,
    ensure_email_config_for_database_mode
)
from university_system.modules.shared.utils.logs import (
    get_log_file,
    configure_logging,
    log_event,
    handle_exception,
    display_communication_logs_menu,
    display_activity_logs,
    export_communication_logs,
    display_communication_analytics_menu,
    logger
)
from university_system.modules.shared.utils.activity_logger import (
    set_user,
    get_user,
    log_activity,
    log_login,
    log_logout,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_import,
    log_error,
    log_access,
    log_permission_denied,
    logger as activity_logger
)

__all__ = [
    'state',
    'templates',
    'CONFIG_SCHEMA',
    'DEFAULT_CONFIG',
    'config',
    'validate_email_config',
    'load_config',
    'save_config',
    'validate_config',
    'configure_email_settings',
    'test_email_configuration',
    'ensure_email_config_for_database_mode',
    'get_log_file',
    'configure_logging',
    'log_event',
    'handle_exception',
    'display_communication_logs_menu',
    'display_activity_logs',
    'export_communication_logs',
    'display_communication_analytics_menu',
    'logger',
    # Activity logging
    'set_user',
    'get_user',
    'log_activity',
    'log_login',
    'log_logout',
    'log_create',
    'log_read',
    'log_update',
    'log_delete',
    'log_search',
    'log_export',
    'log_import',
    'log_error',
    'log_access',
    'log_permission_denied',
    'activity_logger'
]