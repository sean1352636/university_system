"""
Authentication GUI components.

This module contains GUI components for MFA setup and administration that were moved from
infrastructure/auth/ to maintain proper architectural layering.
"""

from education_system.university_system.modules.shared.gui.auth.mfa_gui import (
    MFASetupWizard,
    MFAVerificationDialog,
    show_mfa_setup,
    show_mfa_verification,
)
from education_system.university_system.modules.shared.gui.auth.mfa_admin_gui import (
    MFAAdminPanel,
    show_mfa_admin,
)

__all__ = [
    'MFASetupWizard',
    'MFAVerificationDialog',
    'show_mfa_setup',
    'show_mfa_verification',
    'MFAAdminPanel',
    'show_mfa_admin',
]
