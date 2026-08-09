"""
Security GUI components.

This package contains GUI components for security features that were
previously located in infrastructure/security/. They have been moved
here to respect the 4-layer architecture (GUI belongs in the interface layer).
"""

try:
    from education_system.systems.university.interfaces.gui.shell.security.security_dashboard_gui import SecurityDashboard
except ImportError:
    SecurityDashboard = None

try:
    from education_system.systems.university.interfaces.gui.shell.security.audit_log_viewer_gui import (
        AuditLogViewerGUI,
        AnomalyDetector,
        show_audit_log_viewer,
    )
except ImportError:
    AuditLogViewerGUI = None
    AnomalyDetector = None
    show_audit_log_viewer = None

__all__ = [
    'SecurityDashboard',
    'AuditLogViewerGUI',
    'AnomalyDetector',
    'show_audit_log_viewer',
]
