"""Logging utilities and reporting helpers for the email infrastructure package.

DEPRECATED: This module has been moved to university_system.core.logs
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from education_system.university_system.core.logs import log_event, handle_exception, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.logs for backward compatibility
from education_system.university_system.core.logs import (
    log_event,
    handle_exception,
    logger,
    configure_logging,
    get_log_file,
    display_communication_logs_menu,
    display_activity_logs,
    export_communication_logs,
    display_communication_analytics_menu,
)

__all__ = [
    "log_event",
    "handle_exception",
    "logger",
    "configure_logging",
    "get_log_file",
    "display_communication_logs_menu",
    "display_activity_logs",
    "export_communication_logs",
    "display_communication_analytics_menu",
]
