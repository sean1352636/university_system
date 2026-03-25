"""Backward compatibility shim for university i18n.

New code should import from:
    from education_system.university_system.core.i18n import get_text, set_language, ...
"""

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
