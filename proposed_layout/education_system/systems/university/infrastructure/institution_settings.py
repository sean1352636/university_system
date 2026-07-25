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

from education_system.systems.university.infrastructure.paths import CONFIG_DIR


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
}

# Module-level settings cache
_settings: Dict[str, Any] = {}
_settings_loaded: bool = False


def _get_config_path() -> Path:
    """Get the path to the institution settings configuration file."""
    return CONFIG_DIR / "institution_settings.json"


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
    global _settings, _settings_loaded
    _settings = {}
    _settings_loaded = False


# Convenience functions for common settings
def get_elections_phone() -> str:
    """Get the elections office phone number."""
    return get_setting("elections_phone", DEFAULT_INSTITUTION_SETTINGS["elections_phone"])


def get_events_support_phone() -> str:
    """Get the events/technical support phone number."""
    return get_setting("events_support_phone", DEFAULT_INSTITUTION_SETTINGS["events_support_phone"])


def get_mfa_recovery_format_hint() -> str:
    """Get the MFA recovery code format hint for display."""
    return get_setting("mfa_recovery_code_hint", DEFAULT_INSTITUTION_SETTINGS["mfa_recovery_code_hint"])


__all__ = [
    "DEFAULT_INSTITUTION_SETTINGS",
    "load_settings",
    "get_setting",
    "save_settings",
    "reset_settings",
    "get_elections_phone",
    "get_events_support_phone",
    "get_mfa_recovery_format_hint",
]
