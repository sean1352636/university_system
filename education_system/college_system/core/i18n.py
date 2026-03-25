"""Internationalization support for the College Management System.

Delegates to the shared i18n engine, adding the college-specific locale
directory so that system-specific translations are loaded alongside shared ones.
"""

from education_system.college_system.core.paths import LOCALES_DIR, CONFIG_DIR
from education_system.shared.i18n import (
    init_i18n as _shared_init,
    add_locale_dir,
    t,
    get_text,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
    reload_translations,
    load_saved_language,
    save_language_preference,
    SUPPORTED_LANGUAGES,
)

# Convenience aliases
_ = t
load_locale = set_language

_initialised = False

# Re-export the language config path for backward compatibility
LANGUAGE_CONFIG_PATH = CONFIG_DIR / "language_config.json"


def init_i18n(language: str | None = None):
    """Initialise the i18n system with college-specific locale directory."""
    global _initialised

    if not _initialised:
        _shared_init(language=language)
        add_locale_dir(str(LOCALES_DIR))
        _initialised = True
    elif language is not None:
        set_language(language)
