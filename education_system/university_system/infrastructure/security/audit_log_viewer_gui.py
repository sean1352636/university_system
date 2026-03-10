"""
DEPRECATED: Audit Log Viewer GUI has been moved to modules/shared/gui/security/

This module provides backward compatibility for existing imports.
New code should import from education_system.university_system.modules.shared.gui.security.audit_log_viewer_gui instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.university_system.infrastructure.security.audit_log_viewer_gui is deprecated. "
    "Please import from education_system.university_system.modules.shared.gui.security.audit_log_viewer_gui instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.university_system.modules.shared.gui.security.audit_log_viewer_gui import (
    AuditLogViewerGUI,
    AnomalyDetector,
    show_audit_log_viewer,
)

__all__ = [
    'AuditLogViewerGUI',
    'AnomalyDetector',
    'show_audit_log_viewer',
]
