"""Shared internationalization (i18n) module for all education systems.

Provides a unified multi-language engine with JSON-based translations,
dot-notation key lookups, automatic English fallback, and persistent
language preferences.

Usage::

    from education_system.shared.i18n import init_i18n, t, set_language

    init_i18n(language="en", locale_dirs=["/path/to/locales"])
    print(t("greeting", name="Alice"))
    set_language("es")
"""

from education_system.shared.i18n.core import (
    init_i18n,
    t,
    get_text,
    set_language,
    get_current_language,
    get_available_languages,
    reload_translations,
    add_locale_dir,
    get_current_language_name,
    get_available_language_list,
    load_saved_language,
    save_language_preference,
    SUPPORTED_LANGUAGES,
)

__all__ = [
    "init_i18n",
    "t",
    "get_text",
    "set_language",
    "get_current_language",
    "get_available_languages",
    "reload_translations",
    "add_locale_dir",
    "get_current_language_name",
    "get_available_language_list",
    "load_saved_language",
    "save_language_preference",
    "SUPPORTED_LANGUAGES",
]
