"""
Centralized Activity Logger for University System.

DEPRECATED: This module has been moved to university_system.core.activity_logger
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from university_system.core.activity_logger import log_activity, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.activity_logger for backward compatibility
from university_system.core.activity_logger import (
    ActivityLogger,
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
    logger,
)

__all__ = [
    "ActivityLogger",
    "set_user",
    "get_user",
    "log_activity",
    "log_login",
    "log_logout",
    "log_create",
    "log_read",
    "log_update",
    "log_delete",
    "log_search",
    "log_export",
    "log_import",
    "log_error",
    "log_access",
    "log_permission_denied",
    "logger",
]
