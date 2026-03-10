"""Internationalization support with JSON-based translations."""

import json
from pathlib import Path

from education_system.college_system.core.paths import LOCALES_DIR

_translations: dict = {}
_current_locale: str = "en"


def load_locale(locale: str = "en"):
    """Load translation strings for the given locale."""
    global _translations, _current_locale
    _current_locale = locale
    locale_dir = LOCALES_DIR / locale

    _translations = {}
    for json_file in locale_dir.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _translations.update(data)


def t(key: str, **kwargs) -> str:
    """Get a translated string by dot-notation key.

    Supports format placeholders: t("greeting", name="Alice")
    Falls back to the key itself if not found.
    """
    if not _translations:
        try:
            load_locale(_current_locale)
        except (FileNotFoundError, json.JSONDecodeError):
            return key

    parts = key.split(".")
    value = _translations
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return key
        if value is None:
            return key

    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value if isinstance(value, str) else key
