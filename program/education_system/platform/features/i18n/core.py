"""Unified i18n engine for all education systems.

Supports 13 languages, multiple locale directories (for shared + system-specific
translations), deep-merged JSON files, dot-notation key lookups with English
fallback, and persistent language preferences.

Thread-safe for single-threaded tkinter use (module-level state).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported languages (13 total)
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "es": "Espa\u00f1ol",
    "fr": "Fran\u00e7ais",
    "de": "Deutsch",
    "zh": "\u4e2d\u6587",
    "ar": "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
    "pt": "Portugu\u00eas",
    "ru": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    "ja": "\u65e5\u672c\u8a9e",
    "ko": "\ud55c\uad6d\uc5b4",
    "cy": "Cymraeg",
    "pl": "Polski",
    "ur": "\u0627\u0631\u062f\u0648",
}

# English-name suffixes for display in selectors
_ENGLISH_NAMES: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ar": "Arabic",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "cy": "Welsh",
    "pl": "Polish",
    "ur": "Urdu",
}

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_current_language: str = "en"
_translations: Dict[str, Dict[str, Any]] = {}
_locale_dirs: List[Path] = []
_loaded: bool = False

# Default paths.  Runtime data lives in the gitignored var/ tree at the
# repository root, never inside the package (ADR 0018).
# core.py -> i18n -> features -> platform -> education_system -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PLATFORM_DATA_DIR = _REPO_ROOT / "var" / "data" / "platform"
_DEFAULT_LOCALE_DIR = _PLATFORM_DATA_DIR / "locales"
_CONFIG_DIR = _PLATFORM_DATA_DIR / "config"
_LANGUAGE_CONFIG_PATH = _CONFIG_DIR / "language_config.json"


# ---------------------------------------------------------------------------
# Deep merge utility
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into a copy of *base*.

    Nested dicts are merged; all other values are replaced.
    """
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


# ---------------------------------------------------------------------------
# Translation loading helpers
# ---------------------------------------------------------------------------

def _load_json_files_from_dir(lang_dir: Path) -> Dict[str, Any]:
    """Recursively load and deep-merge all ``*.json`` files under *lang_dir*."""
    translations: Dict[str, Any] = {}
    if not lang_dir.is_dir():
        return translations

    for json_file in sorted(lang_dir.rglob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            translations = _deep_merge(translations, data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load locale file %s: %s", json_file, exc)

    return translations


def _load_language(lang_code: str) -> Dict[str, Any]:
    """Load translations for *lang_code* from all registered locale dirs.

    Later directories override earlier ones (system-specific wins over shared).
    """
    merged: Dict[str, Any] = {}
    for locale_dir in _locale_dirs:
        lang_dir = locale_dir / lang_code
        if lang_dir.is_dir():
            data = _load_json_files_from_dir(lang_dir)
            merged = _deep_merge(merged, data)
    return merged


def _load_all_translations() -> None:
    """Load translations for every supported language from all locale dirs."""
    global _translations, _loaded

    for lang_code in SUPPORTED_LANGUAGES:
        _translations[lang_code] = _load_language(lang_code)

    _loaded = True
    loaded_count = sum(1 for v in _translations.values() if v)
    logger.debug("Loaded translations for %d/%d languages from %d locale dir(s)",
                 loaded_count, len(SUPPORTED_LANGUAGES), len(_locale_dirs))


def _ensure_loaded() -> None:
    """Lazy-load translations on first access."""
    if not _loaded:
        init_i18n()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_language_preference(language: str) -> bool:
    """Persist the language choice to a JSON config file.

    Returns ``True`` on success, ``False`` on failure.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_LANGUAGE_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump({"language": language}, fh, indent=2)
        logger.debug("Saved language preference: %s", language)
        return True
    except OSError as exc:
        logger.warning("Could not save language preference: %s", exc)
        return False


def load_saved_language() -> str:
    """Load the previously saved language preference, defaulting to ``'en'``."""
    try:
        with open(_LANGUAGE_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        lang = data.get("language", "en")
        return lang if lang in SUPPORTED_LANGUAGES else "en"
    except (OSError, json.JSONDecodeError):
        return "en"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_i18n(
    language: Optional[str] = None,
    locale_dirs: Optional[List[str]] = None,
) -> str:
    """Initialise the shared i18n system.

    Parameters
    ----------
    language:
        Language code to activate.  If ``None``, the saved preference is
        loaded (falling back to ``"en"``).
    locale_dirs:
        One or more filesystem paths to locale directories.  Each directory
        is expected to contain sub-directories named by language code (e.g.
        ``en/``, ``es/``) holding ``.json`` translation files.  If ``None``,
        the default ``shared/data/locales/`` is used.  Directories are
        searched in order; later entries override earlier ones.

    Returns
    -------
    str
        The active language code after initialisation.
    """
    global _current_language, _locale_dirs, _loaded, _translations

    # Set up locale directories
    if locale_dirs is not None:
        _locale_dirs = [Path(d) for d in locale_dirs]
    elif not _locale_dirs:
        # First init with no explicit dirs -> use default
        _locale_dirs = [_DEFAULT_LOCALE_DIR]

    # Determine language
    if language is not None:
        lang = language
    else:
        lang = load_saved_language()

    _current_language = lang if lang in SUPPORTED_LANGUAGES else "en"

    # (Re)load translations
    _translations = {}
    _load_all_translations()

    logger.debug("i18n initialised: language=%s, locale_dirs=%s",
                 _current_language, [str(d) for d in _locale_dirs])
    return _current_language


def add_locale_dir(path: str) -> None:
    """Register an additional locale directory (e.g. for system-specific translations).

    The new directory takes precedence over previously registered directories.
    If translations have already been loaded, they are reloaded automatically
    so that the new directory's files are merged in.
    """
    global _loaded
    p = Path(path)
    if p not in _locale_dirs:
        _locale_dirs.append(p)
        if _loaded:
            # Reload to incorporate the new directory
            _loaded = False
            _load_all_translations()


def t(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """Get a translated string by dot-notation key.

    Fallback chain: current language -> English -> *default* -> *key* itself.

    Supports ``str.format`` placeholders::

        t("greeting", name="Alice")  # "Hello, {name}!" -> "Hello, Alice!"
    """
    _ensure_loaded()

    # Try current language, then English fallback
    for lang in (_current_language, "en"):
        value: Any = _translations.get(lang, {})
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
            if value is None:
                break

        if isinstance(value, str):
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, IndexError):
                    return value
            return value

    # Nothing found in any language
    return default if default is not None else key


# Convenience aliases
get_text = t
_ = t


def set_language(code: str, save: bool = True) -> bool:
    """Switch the active language and optionally persist the choice.

    Returns ``True`` if the language was set, ``False`` if the code is
    unsupported.
    """
    global _current_language

    if code not in SUPPORTED_LANGUAGES:
        logger.warning("Unsupported language code: %s", code)
        return False

    _current_language = code

    # Ensure translations for this language are loaded
    if code not in _translations or not _translations[code]:
        _translations[code] = _load_language(code)

    if save:
        save_language_preference(code)

    logger.info("Language switched to %s", code)
    return True


def get_current_language() -> str:
    """Return the current language code (e.g. ``'en'``)."""
    _ensure_loaded()
    return _current_language


def get_current_language_name() -> str:
    """Return the native display name of the current language."""
    _ensure_loaded()
    return SUPPORTED_LANGUAGES.get(_current_language, _current_language)


def get_available_languages() -> Dict[str, str]:
    """Return ``{code: native_name}`` for every supported language."""
    return dict(SUPPORTED_LANGUAGES)


def get_available_language_list() -> List[Tuple[str, str]]:
    """Return a list of ``(code, native_name)`` tuples."""
    return list(SUPPORTED_LANGUAGES.items())


def get_english_name(code: str) -> str:
    """Return the English name for a language code."""
    return _ENGLISH_NAMES.get(code, code)


def reload_translations() -> None:
    """Force a full reload of all translation files from disk."""
    global _translations, _loaded
    _translations = {}
    _loaded = False
    _load_all_translations()


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "init_i18n",
    "t",
    "get_text",
    "set_language",
    "get_current_language",
    "get_current_language_name",
    "get_available_languages",
    "get_available_language_list",
    "get_english_name",
    "reload_translations",
    "add_locale_dir",
    "load_saved_language",
    "save_language_preference",
    "SUPPORTED_LANGUAGES",
    "_",
]
