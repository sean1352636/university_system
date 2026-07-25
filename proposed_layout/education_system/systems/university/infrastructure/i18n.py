"""Internationalization support for the University Management System.

Delegates to the shared i18n engine, adding the university-specific locale
directory so that system-specific translations are loaded alongside shared ones.
"""

from __future__ import annotations

from pathlib import Path

from education_system.platform.features.i18n import (
    init_i18n as _shared_init,
    add_locale_dir,
    t,
    get_text,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
    get_available_language_list,
    reload_translations,
    load_saved_language,
    save_language_preference,
    SUPPORTED_LANGUAGES,
)

# Convenience alias
_ = get_text

_initialised = False

# University locale directory (lives alongside the university data)
_UNIVERSITY_LOCALES = Path(__file__).resolve().parent.parent / "data" / "locales"


def _get_config_path() -> Path:
    """Get the language config file path (backward compat)."""
    from education_system.systems.university.infrastructure import paths
    return paths.CONFIG_DIR / "language_config.json"


def init_i18n(language_code: str | None = None) -> str:
    """Initialise the i18n system with university-specific locale directory.

    Parameters
    ----------
    language_code:
        Language code to activate.  If ``None``, the saved preference
        is loaded (falling back to ``"en"``).

    Returns
    -------
    str
        The active language code after initialisation.
    """
    global _initialised

    if not _initialised:
        _shared_init(language=language_code)
        add_locale_dir(str(_UNIVERSITY_LOCALES))
        _initialised = True
    elif language_code is not None:
        set_language(language_code)

    return get_current_language()


__all__ = [
    "init_i18n",
    "get_text",
    "t",
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
