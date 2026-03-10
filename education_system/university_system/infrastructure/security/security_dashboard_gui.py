"""
DEPRECATED: Security Dashboard GUI has been moved to modules/shared/gui/security/

This module provides backward compatibility for existing imports.
New code should import from education_system.university_system.modules.shared.gui.security.security_dashboard_gui instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.university_system.infrastructure.security.security_dashboard_gui is deprecated. "
    "Please import from education_system.university_system.modules.shared.gui.security.security_dashboard_gui instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import (
    SecurityDashboard,
    show_security_dashboard,
)

__all__ = [
    'SecurityDashboard',
    'show_security_dashboard',
]
