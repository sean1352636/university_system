"""
Internationalization (i18n) module for the University Management System.

DEPRECATED: This module has been moved to university_system.core.i18n
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from education_system.university_system.core.i18n import get_text, set_language, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.i18n for backward compatibility
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
    get_available_language_list,
    load_saved_language,
    save_language_preference,
    reload_translations,
    SUPPORTED_LANGUAGES,
    _,
    _get_config_path,
)

__all__ = [
    "init_i18n",
    "get_text",
    "set_language",
    "get_current_language",
    "get_current_language_name",
    "get_available_languages",
    "get_available_language_list",
    "load_saved_language",
    "save_language_preference",
    "reload_translations",
    "SUPPORTED_LANGUAGES",
    "_",
    "_get_config_path",
]
