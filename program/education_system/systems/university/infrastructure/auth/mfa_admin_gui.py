"""
DEPRECATED: MFA Admin GUI components have been moved to modules/shared/gui/auth/

This module provides backward compatibility for existing imports.
New code should import from education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.systems.university.infrastructure.auth.mfa_admin_gui is deprecated. "
    "Please import from education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui import (
    MFAAdminPanel,
    show_mfa_admin,
)

__all__ = [
    'MFAAdminPanel',
    'show_mfa_admin',
]
