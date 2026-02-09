"""
Localization Module

Provides translation support for the University System.
Loads translations from JSON files in data/locales/{locale}/ directory.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Default locale
DEFAULT_LOCALE = 'en'

# Cache for loaded translations
_translation_cache: Dict[str, Dict[str, Any]] = {}

# Current locale
_current_locale = DEFAULT_LOCALE


def get_locales_dir() -> Path:
    """Get the locales directory path."""
    # Get the project root (3 levels up from infrastructure/)
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    locales_dir = project_root / 'data' / 'locales' / _current_locale
    return locales_dir


def load_translation_file(file_path: Path) -> Dict[str, Any]:
    """Load a single translation JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load translation file {file_path}: {e}")
        return {}


def get_translation_data(domain: str = None) -> Dict[str, Any]:
    """
    Get translation data for a specific domain or all translations.

    Args:
        domain: Optional domain name (e.g., 'staff_hr', 'academics', etc.)

    Returns:
        Dictionary containing translation data
    """
    global _translation_cache

    # If we haven't loaded translations yet
    if not _translation_cache:
        locales_dir = get_locales_dir()

        if not locales_dir.exists():
            return {}

        # Load all JSON files from the locales directory and subdirectories
        for json_file in locales_dir.rglob('*.json'):
            try:
                data = load_translation_file(json_file)
                # Merge into cache
                _merge_dicts(_translation_cache, data)
            except Exception as e:
                print(f"Warning: Error loading {json_file}: {e}")

    if domain:
        return _translation_cache.get(domain, {})

    return _translation_cache


def _merge_dicts(dest: Dict, src: Dict) -> None:
    """Recursively merge source dict into destination dict."""
    for key, value in src.items():
        if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
            _merge_dicts(dest[key], value)
        else:
            dest[key] = value


def _get_nested_value(data: Dict[str, Any], key_path: str) -> Optional[Any]:
    """
    Get a value from nested dictionary using dot notation.

    Args:
        data: Dictionary to search
        key_path: Key path in dot notation (e.g., 'staff_profile.tabs.my_profile')

    Returns:
        Value if found, None otherwise
    """
    keys = key_path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current


def get_translation(key: str, default: str = None, **kwargs) -> str:
    """
    Get a translated string.

    Args:
        key: Translation key in dot notation (e.g., 'staff_profile.tabs.my_profile')
        default: Default value if translation not found
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string with format arguments applied

    Example:
        _t("staff_profile.messages.save_success", default="Profile saved successfully")
        _t("staff_profile.labels.employee_id", default="Employee ID: {id}", id="12345")
    """
    # Get all translation data
    translations = get_translation_data()

    # Try to find the translation
    value = _get_nested_value(translations, key)

    # Fall back to default if not found
    if value is None:
        value = default if default is not None else key

    # Apply format arguments if provided
    if kwargs:
        try:
            value = value.format(**kwargs)
        except (KeyError, ValueError) as e:
            print(f"Warning: Translation formatting error for key '{key}': {e}")

    return value


def set_locale(locale: str) -> None:
    """
    Set the current locale.

    Args:
        locale: Locale code (e.g., 'en', 'es', 'fr')
    """
    global _current_locale, _translation_cache
    _current_locale = locale
    _translation_cache = {}  # Clear cache to reload with new locale


def get_current_locale() -> str:
    """Get the current locale."""
    return _current_locale


def reload_translations() -> None:
    """Reload all translations from disk."""
    global _translation_cache
    _translation_cache = {}
    get_translation_data()


# Convenience alias
_t = get_translation
