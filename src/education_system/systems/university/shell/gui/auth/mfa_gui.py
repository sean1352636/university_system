"""University MFA GUI — moved to the platform.

The implementation now lives at
``education_system.platform.delivery.gui.mfa_setup_gui``. This module stays
as a re-export so the university's existing imports keep resolving, and is
where the university registers its own recovery-code format hint with the
shared MFA integrations layer.
"""

from __future__ import annotations

import logging

from education_system.platform.delivery.gui.mfa_setup_gui import (  # noqa: F401
    MFASetupWizard,
    MFAVerificationDialog,
    show_mfa_setup,
    show_mfa_verification,
)
from education_system.platform.identity.auth.mfa import register_recovery_format_hint
from education_system.systems.university.infrastructure.i18n import init_i18n

logger = logging.getLogger(__name__)

__all__ = [
    "MFASetupWizard",
    "MFAVerificationDialog",
    "show_mfa_setup",
    "show_mfa_verification",
]

# The university adds its own locale directory, so keep initialising i18n
# here — the shared module deliberately does not do it at import time.
init_i18n()

try:
    from education_system.systems.university.infrastructure.institution_settings import (
        get_mfa_recovery_format_hint,
    )
except ImportError:
    logger.debug("Institution settings unavailable; using default recovery hint")
else:
    register_recovery_format_hint(get_mfa_recovery_format_hint)
