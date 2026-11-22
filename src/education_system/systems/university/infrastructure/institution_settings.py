"""Centralized institution contact settings.

This module provides configurable institution contact information that can
be used throughout the application instead of hardcoded placeholder values.

Settings can be loaded from environment variables or a configuration file.

This module is in the core package and has no dependencies on infrastructure
or modules, preventing circular imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any

from education_system.paths import UNIVERSITY_CONFIG_DIR


# Default institution settings
DEFAULT_INSTITUTION_SETTINGS: Dict[str, Any] = {
    # General contact information
    "institution_name": "Teesside University",
    "main_phone": "+44 1642 218121",
    "main_email": "info@tees.ac.uk",
    "website": "https://www.tees.ac.uk",

    # Student Union contact
    "student_union_phone": "+44 1642 342256",
    "student_union_email": "studentsunion@tees.ac.uk",

    # Elections office contact
    "elections_email": "elections@studentunion.ac.uk",
    "elections_phone": "+44 1642 342257",

    # Events/technical support contact
    "events_support_phone": "+44 1642 342258",
    "events_support_email": "techsupport@studentunion.ac.uk",

    # Physical address
    "address_line1": "Middlesbrough",
    "address_line2": "Tees Valley",
    "postcode": "TS1 3BX",
    "country": "United Kingdom",

    # MFA recovery code format (display only, not actual format)
    "mfa_recovery_code_format": "NNNN-NNNN",
    "mfa_recovery_code_hint": "8 digits with hyphen in middle",

    # Statutory identifiers (HESA / OfS / UCAS / SLC / UKVI returns). Blank
    # until an administrator enters them; the returns refuse to build while
    # they are blank rather than inventing a number.
    "ukprn": "",
    "hesa_provider_id": "",
    "ucas_institution_code": "",
    "sponsor_licence_number": "",
}

# Module-level settings cache
_settings: Dict[str, Any] = {}
_settings_loaded: bool = False

# Cache for the branding-table lookup in get_institution_name(). Opening a
# fresh connection to student_records.db costs ~100 ms, and bulk email renders
# the institution name once per recipient.
_branding_name: str | None = None
_branding_name_loaded: bool = False


def _get_config_path() -> Path:
    """Get the path to the institution settings configuration file."""
    return UNIVERSITY_CONFIG_DIR / "institution_settings.json"


def load_settings() -> Dict[str, Any]:
    """
    Load institution settings from configuration file and environment variables.

    Priority order (highest to lowest):
    1. Environment variables (prefixed with UNIVERSITY_)
    2. Configuration file (institution_settings.json)
    3. Default values

    Returns:
        Dict containing all institution settings.
    """
    global _settings, _settings_loaded

    if _settings_loaded:
        return _settings.copy()

    # Start with defaults
    _settings = DEFAULT_INSTITUTION_SETTINGS.copy()

    # Load from config file if exists
    config_path = _get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_settings = json.load(f)
                _settings.update(file_settings)
        except (json.JSONDecodeError, IOError) as e:
            # Log error but continue with defaults
            import logging
            logging.getLogger(__name__).warning(
                f"Could not load institution settings from {config_path}: {e}"
            )

    # Override with environment variables
    env_prefix = "UNIVERSITY_"
    for key in DEFAULT_INSTITUTION_SETTINGS.keys():
        env_key = env_prefix + key.upper()
        env_value = os.environ.get(env_key)
        if env_value is not None:
            _settings[key] = env_value

    _settings_loaded = True
    return _settings.copy()


def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a specific institution setting.

    Args:
        key: The setting key to retrieve.
        default: Default value if setting not found.

    Returns:
        The setting value or default.
    """
    settings = load_settings()
    return settings.get(key, default)


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    Save institution settings to configuration file.

    Args:
        settings: Dictionary of settings to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    global _settings, _settings_loaded

    config_path = _get_config_path()
    try:
        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Merge with existing settings
        current = load_settings()
        current.update(settings)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=4)

        # Update cache
        _settings = current
        _settings_loaded = True
        return True

    except IOError as e:
        import logging
        logging.getLogger(__name__).error(
            f"Could not save institution settings to {config_path}: {e}"
        )
        return False


def reset_settings() -> None:
    """Reset settings cache to force reload on next access."""
    global _settings, _settings_loaded, _branding_name, _branding_name_loaded
    _settings = {}
    _settings_loaded = False
    _branding_name = None
    _branding_name_loaded = False


# Convenience functions for common settings
def get_institution_name() -> str:
    """Return the institution's display name for user-facing text.

    Resolution order, first hit wins:

    1. ``UNIVERSITY_INSTITUTION_NAME`` in the environment — a deployment-level
       override, so it beats anything stored in the instance.
    2. ``branding_institution_name`` in the ``security_settings`` table, which
       is what the admin Branding & Customization GUI writes.
    3. ``institution_settings.json``, then the built-in default.

    The database is consulted lazily and failures are non-fatal: a missing
    table or an unreachable database just falls through to the file/default.
    """
    global _branding_name, _branding_name_loaded

    env_value = os.environ.get("UNIVERSITY_INSTITUTION_NAME")
    if env_value:
        return env_value

    if not _branding_name_loaded:
        _branding_name_loaded = True
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection

            with get_connection() as conn:
                row = conn.execute(
                    "SELECT setting_value FROM security_settings WHERE setting_name = ?",
                    ("branding_institution_name",),
                ).fetchone()
            if row and row[0]:
                _branding_name = row[0]
        except Exception as e:  # missing table, locked db, no db yet — all fine
            import logging
            logging.getLogger(__name__).debug(
                f"Could not read branding institution name: {e}"
            )

    if _branding_name:
        return _branding_name

    return get_setting("institution_name", DEFAULT_INSTITUTION_SETTINGS["institution_name"])


def get_elections_phone() -> str:
    """Get the elections office phone number."""
    return get_setting("elections_phone", DEFAULT_INSTITUTION_SETTINGS["elections_phone"])


def get_events_support_phone() -> str:
    """Get the events/technical support phone number."""
    return get_setting("events_support_phone", DEFAULT_INSTITUTION_SETTINGS["events_support_phone"])


def get_mfa_recovery_format_hint() -> str:
    """Get the MFA recovery code format hint for display."""
    return get_setting("mfa_recovery_code_hint", DEFAULT_INSTITUTION_SETTINGS["mfa_recovery_code_hint"])


STATUTORY_IDENTIFIERS = {
    "ukprn": ("UKPRN", r"^1\d{7}$", "8 digits starting with 1 (UK Register of Learning Providers)"),
    "hesa_provider_id": ("HESA provider identifier", r"^\d{4}$", "4 digits (HESA INSTID)"),
    "ucas_institution_code": ("UCAS institution code", r"^[A-Z0-9]{3,5}$",
                              "letters/digits as shown on UCAS (e.g. T20)"),
    "sponsor_licence_number": ("Home Office sponsor licence number", r"^[A-Z0-9]{6,12}$",
                               "as shown in the Sponsor Management System"),
}


def statutory_identifiers() -> Dict[str, str]:
    """The institution's statutory identifiers ('' where not set)."""
    settings = load_settings()
    return {key: str(settings.get(key) or "").strip() for key in STATUTORY_IDENTIFIERS}


def set_statutory_identifier(key: str, value: str) -> str:
    """Validate and save one statutory identifier; returns the stored value."""
    import re

    if key not in STATUTORY_IDENTIFIERS:
        raise ValueError(f"Unknown identifier {key!r}")
    label, pattern, hint = STATUTORY_IDENTIFIERS[key]
    value = str(value or "").strip().upper()
    if value and not re.match(pattern, value):
        raise ValueError(f"{label} must be {hint}")
    if not save_settings({key: value}):
        raise OSError(f"Could not save the {label}")
    return value


def require_statutory_identifier(key: str) -> str:
    """The identifier, or ValueError naming what to set first."""
    value = statutory_identifiers().get(key, "")
    if not value:
        label = STATUTORY_IDENTIFIERS[key][0]
        raise ValueError(f"Set the institution's {label} first (Statutory Returns → "
                         "Institution identifiers)")
    return value


__all__ = [
    "DEFAULT_INSTITUTION_SETTINGS",
    "STATUTORY_IDENTIFIERS",
    "statutory_identifiers",
    "set_statutory_identifier",
    "require_statutory_identifier",
    "load_settings",
    "get_setting",
    "save_settings",
    "reset_settings",
    "get_institution_name",
    "get_elections_phone",
    "get_events_support_phone",
    "get_mfa_recovery_format_hint",
]
