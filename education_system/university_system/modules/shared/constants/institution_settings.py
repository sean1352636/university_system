"""Centralized institution contact settings.

DEPRECATED: This module has been moved to university_system.core.institution_settings
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from education_system.university_system.core.institution_settings import get_setting, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.institution_settings for backward compatibility
from education_system.university_system.core.institution_settings import (
    DEFAULT_INSTITUTION_SETTINGS,
    load_settings,
    get_setting,
    save_settings,
    reset_settings,
    get_elections_phone,
    get_events_support_phone,
    get_mfa_recovery_format_hint,
)

__all__ = [
    "DEFAULT_INSTITUTION_SETTINGS",
    "load_settings",
    "get_setting",
    "save_settings",
    "reset_settings",
    "get_elections_phone",
    "get_events_support_phone",
    "get_mfa_recovery_format_hint",
]
