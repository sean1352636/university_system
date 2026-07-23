"""
DEPRECATED: MFA GUI components have been moved to modules/shared/gui/auth/

This module provides backward compatibility for existing imports.
New code should import from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.post_18.university_system.infrastructure.auth.mfa_gui is deprecated. "
    "Please import from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import (
    MFASetupWizard,
    MFAVerificationDialog,
    show_mfa_setup,
    show_mfa_verification,
)

__all__ = [
    'MFASetupWizard',
    'MFAVerificationDialog',
    'show_mfa_setup',
    'show_mfa_verification',
]
