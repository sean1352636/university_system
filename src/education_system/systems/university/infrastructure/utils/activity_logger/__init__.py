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


def _resolve_actor():
    """Best-effort ``(user_id, username, role)`` for the logged-in user.

    Falls back to ``('system', 'system', 'system')`` — the same triple the
    logging decorators use when they cannot find a user — so logging never
    fails just because nobody is signed in.
    """
    try:
        from education_system.systems.university.infrastructure.auth import get_current_user
        user = get_current_user()
    except Exception:
        return 'system', 'system', 'system'

    if not user:
        return 'system', 'system', 'system'

    get = user.get if isinstance(user, dict) else lambda k, d=None: getattr(user, k, d)
    return (
        str(get('id', 'system') or 'system'),
        str(get('username', 'system') or 'system'),
        str(get('role', 'system') or 'system'),
    )


def log_activity(*args, **kwargs):
    """Log an activity, accepting the shapes callers actually use.

    ``EnhancedActivityLogger.log_activity`` requires
    ``(user_id, username, role, action, module, ...)``. Almost nothing in
    this codebase calls it that way — the ~1,200 call sites overwhelmingly
    use ``log_activity(action, module, ...)`` or a single free-text string
    — so forwarding straight through raised

        TypeError: log_activity() missing 4 required positional arguments

    for nearly every caller. Where the call sat inside a try/except the
    activity was silently dropped; where it did not (housing's guest passes
    and access cards, for instance) it aborted the menu action itself.

    So the shape is normalised here rather than at the call sites:

    * 5+ positional args, or the full strict keyword set -> passed through.
    * ``(action, module, ...)``                          -> actor resolved.
    * ``(action,)``                                      -> actor resolved,
      module inferred from the caller's own module name.

    ``user`` / ``user_id`` keywords, which many callers pass, override the
    resolved actor.
    """
    logger_instance = get_logger_instance()

    strict_keys = {'user_id', 'username', 'role', 'action', 'module'}
    if len(args) >= 5 or strict_keys.issubset(kwargs):
        return logger_instance.log_activity(*args, **kwargs)

    kwargs = dict(kwargs)
    user_id, username, role = _resolve_actor()

    # Callers commonly identify the actor with one of these instead.
    explicit_user = kwargs.pop('user', None)
    explicit_user_id = kwargs.pop('user_id', None)
    if explicit_user is not None:
        username = str(explicit_user)
    if explicit_user_id is not None:
        user_id = str(explicit_user_id)
    kwargs.pop('username', None)
    kwargs.pop('role', None)

    action = kwargs.pop('action', None)
    module = kwargs.pop('module', None)
    details = kwargs.pop('details', None)

    positional = list(args)
    if action is None and positional:
        action = positional.pop(0)
    if module is None and positional:
        module = positional.pop(0)
    if details is None and positional:
        details = positional.pop(0)

    if module is None:
        # Name the caller's module so a bare log_activity("...") is still
        # attributable to wherever it came from.
        try:
            import inspect
            frame = inspect.currentframe()
            caller = frame.f_back if frame else None
            module = (caller.f_globals.get('__name__') if caller else None) or 'general'
        except Exception:
            module = 'general'

    return logger_instance.log_activity(
        user_id, username, role, str(action) if action is not None else 'activity',
        str(module), details, *positional, **kwargs
    )


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
