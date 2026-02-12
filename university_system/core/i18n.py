"""
Internationalization (i18n) module for the University Management System.

This module provides multi-language support throughout the application.
It loads translations from JSON files within locale directories
(e.g., locales/en/*.json, locales/es/*.json) and provides a simple API
for retrieving translated strings.

This module is in the core package and has no dependencies on infrastructure
or modules, preventing circular imports.

Usage:
    from university_system.core.i18n import get_text, set_language

    # Get translated text
    message = get_text("welcome_message")

    # Change language
    set_language("es")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Global state for current language
_current_language: str = "en"
_translations: Dict[str, Dict[str, Any]] = {}
_loaded: bool = False

# Supported languages with their display names
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "zh": "中文 (Chinese)",
    "ar": "العربية (Arabic)",
    "pt": "Português (Portuguese)",
    "ru": "Русский (Russian)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
}


def _get_locales_dir() -> Path:
    """Get the locales directory path."""
    from university_system.core import paths
    return paths.DATA_DIR / "locales"


def _get_config_path() -> Path:
    """Get the language config file path."""
    from university_system.core import paths
    return paths.CONFIG_DIR / "language_config.json"


def _ensure_locales_dir() -> Path:
    """Ensure the locales directory exists and return the path."""
    locales_dir = _get_locales_dir()
    locales_dir.mkdir(parents=True, exist_ok=True)
    return locales_dir


def _deep_merge_dicts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, combining nested dictionaries recursively.

    Args:
        base: The base dictionary
        update: The dictionary to merge into base

    Returns:
        Merged dictionary with deep merge of nested dicts
    """
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            # Overwrite or add new key
            result[key] = value
    return result


def _load_split_translations(lang_dir: Path) -> Dict[str, Any]:
    """
    Load and merge all JSON files from a language directory.

    Recursively searches for JSON files in the language directory and all subdirectories
    (e.g., locales/en/*.json, locales/en/academics/*.json, etc.)

    Uses deep merge to properly combine nested dictionaries from multiple files.

    Args:
        lang_dir: Path to the language directory (e.g., locales/en/)

    Returns:
        Merged dictionary of all translations
    """
    translations = {}

    # Use rglob to recursively find all JSON files in subdirectories
    for json_file in sorted(lang_dir.rglob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Use deep merge instead of shallow update
                translations = _deep_merge_dicts(translations, data)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {json_file}: {e}")
        except IOError as e:
            logger.error(f"Error reading {json_file}: {e}")

    return translations


def _load_translation_file(language_code: str) -> Dict[str, Any]:
    """
    Load translations for the specified language from the locale directory.

    Loads all JSON files from the language directory (e.g., locales/en/*.json)

    Args:
        language_code: The language code (e.g., 'en', 'es', 'fr')

    Returns:
        Dictionary of translations, empty dict if not found
    """
    locales_dir = _ensure_locales_dir()

    # Load from directory structure (e.g., locales/en/*.json)
    lang_dir = locales_dir / language_code
    if lang_dir.is_dir():
        translations = _load_split_translations(lang_dir)
        if translations:
            logger.debug(f"Loaded {len(translations)} sections from {lang_dir}")
            return translations

    logger.warning(f"Translation directory not found: {lang_dir}")
    return {}


def _load_all_translations() -> None:
    """Load all available translation files from locale directories."""
    global _translations, _loaded

    locales_dir = _ensure_locales_dir()

    # Load each supported language from its directory
    for lang_code in SUPPORTED_LANGUAGES:
        lang_dir = locales_dir / lang_code
        if lang_dir.is_dir():
            _translations[lang_code] = _load_translation_file(lang_code)
        else:
            _translations[lang_code] = {}

    _loaded = True
    logger.info(f"Loaded translations for {len(_translations)} languages")


def load_saved_language() -> str:
    """
    Load the saved language preference from config file.

    Returns:
        The saved language code, or 'en' if not found
    """
    config_path = _get_config_path()

    if not config_path.exists():
        return "en"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("language", "en")
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load language config: {e}")
        return "en"


def save_language_preference(language_code: str) -> bool:
    """
    Save the language preference to config file.

    Args:
        language_code: The language code to save

    Returns:
        True if saved successfully, False otherwise
    """
    config_path = _get_config_path()

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        config = {"language": language_code}
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Saved language preference: {language_code}")
        return True
    except IOError as e:
        logger.error(f"Could not save language config: {e}")
        return False


def init_i18n(language_code: Optional[str] = None) -> str:
    """
    Initialize the i18n system.

    Args:
        language_code: Optional language code to set. If None, loads saved preference.

    Returns:
        The current language code after initialization
    """
    global _current_language, _loaded

    # Load all translation files
    if not _loaded:
        _load_all_translations()

    # Set language from parameter or saved preference
    if language_code:
        _current_language = language_code
    else:
        _current_language = load_saved_language()

    # Validate language
    if _current_language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language '{_current_language}', defaulting to English")
        _current_language = "en"

    logger.info(f"i18n initialized with language: {_current_language}")
    return _current_language


def get_text(key: str, default: Optional[str] = None, **kwargs) -> str:
    """
    Get translated text for a given key.

    Args:
        key: The translation key (can use dot notation for nested keys)
        default: Optional default value if translation is not found
        **kwargs: Format arguments to interpolate into the string

    Returns:
        The translated string, or the default/key if not found
    """
    global _current_language, _translations, _loaded

    # Ensure translations are loaded
    if not _loaded:
        _load_all_translations()

    # Get translation for current language
    translations = _translations.get(_current_language, {})

    # Handle dot notation for nested keys (e.g., "menu.welcome")
    value = translations
    for part in key.split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    # Fall back to English if not found in current language
    if value is None and _current_language != "en":
        translations = _translations.get("en", {})
        value = translations
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

    # Use default if provided and value not found
    if value is None:
        if default is not None:
            value = default
        else:
            logger.debug(f"Translation not found for key: {key}")
            return key

    # Format string with kwargs if provided
    if kwargs and isinstance(value, str):
        try:
            return value.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format key {e} for translation: {key}")
            return value

    return value if isinstance(value, str) else key


def set_language(language_code: str, save: bool = True) -> bool:
    """
    Set the current language.

    Args:
        language_code: The language code to set
        save: Whether to save the preference to config

    Returns:
        True if language was set successfully, False otherwise
    """
    global _current_language

    if language_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {language_code}")
        return False

    _current_language = language_code
    logger.info(f"Language set to: {language_code}")

    if save:
        save_language_preference(language_code)

    return True


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


def get_current_language_name() -> str:
    """Get the display name of the current language."""
    return SUPPORTED_LANGUAGES.get(_current_language, "Unknown")


def get_available_languages() -> Dict[str, str]:
    """
    Get all available languages.

    Returns:
        Dictionary mapping language codes to display names
    """
    return SUPPORTED_LANGUAGES.copy()


def get_available_language_list() -> List[tuple]:
    """
    Get available languages as a list of tuples.

    Returns:
        List of (code, name) tuples
    """
    return list(SUPPORTED_LANGUAGES.items())


def reload_translations() -> None:
    """Reload all translation files from disk."""
    global _loaded
    _loaded = False
    _load_all_translations()


# Shorthand function for convenience
_ = get_text


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
]
