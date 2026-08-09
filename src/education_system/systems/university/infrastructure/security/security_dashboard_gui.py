"""
DEPRECATED: Security Dashboard GUI has been moved to modules/shared/gui/security/

This module provides backward compatibility for existing imports.
New code should import from education_system.systems.university.interfaces.gui.shell.security.security_dashboard_gui instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.systems.university.infrastructure.security.security_dashboard_gui is deprecated. "
    "Please import from education_system.systems.university.interfaces.gui.shell.security.security_dashboard_gui instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.systems.university.interfaces.gui.shell.security.security_dashboard_gui import (
    SecurityDashboard,
    show_security_dashboard,
    MFA_ADMIN_AVAILABLE,
    MFA_SETUP_AVAILABLE,
)

from education_system.systems.university.infrastructure.security.init_security_tables import init_security_tables

__all__ = [
    'SecurityDashboard',
    'show_security_dashboard',
    'init_security_tables',
    'MFA_ADMIN_AVAILABLE',
    'MFA_SETUP_AVAILABLE',
]
