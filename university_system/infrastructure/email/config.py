"""
Basic configuration module for the email subsystem.

The original project referenced a ``config`` submodule within
``university_system.infrastructure.email`` that was not present in
this repository.  Various email components import symbols from
``university_system.infrastructure.email.config``, including a
configuration dictionary and several helper functions.  This module
provides a minimal implementation of those symbols to prevent
``ModuleNotFoundError`` exceptions and allow the system to load.  The
implementation focuses on sensible defaults rather than full
functionality.

Security Note:
    SMTP passwords should NEVER be stored in plaintext config files.
    Use one of these secure methods instead:
    1. Environment variables: SMTP_PASSWORD, SMTP_USERNAME
    2. System keyring: keyring.set_password('university_email', username, password)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from university_system.modules.shared.constants import paths as sys_paths

_logger = logging.getLogger(__name__)

# Check for optional keyring support
try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False
    keyring = None

# Service name for keyring storage
_KEYRING_SERVICE = 'university_system_email'


def _get_env_password() -> str:
    """Get SMTP password from environment variable.

    Returns:
        Password string or empty string if not set.
    """
    return os.environ.get('SMTP_PASSWORD', '')


def _get_keyring_password(username: str) -> str:
    """Get SMTP password from system keyring.

    Args:
        username: The SMTP username to look up.

    Returns:
        Password string or empty string if not available.
    """
    if not _KEYRING_AVAILABLE or not username:
        return ''
    try:
        password = keyring.get_password(_KEYRING_SERVICE, username)
        return password or ''
    except Exception as e:
        _logger.debug("Could not retrieve password from keyring: %s", e)
        return ''


def get_smtp_password(username: Optional[str] = None) -> str:
    """Get SMTP password using secure methods.

    Attempts to retrieve the password in order of preference:
    1. Environment variable (SMTP_PASSWORD)
    2. System keyring (if available)
    3. Returns empty string if no secure source available

    Args:
        username: Optional SMTP username for keyring lookup.

    Returns:
        The SMTP password or empty string.

    Note:
        Passwords are NEVER read from config files for security.
    """
    # Priority 1: Environment variable (most common in production)
    env_password = _get_env_password()
    if env_password:
        return env_password

    # Priority 2: System keyring (secure local storage)
    if username:
        keyring_password = _get_keyring_password(username)
        if keyring_password:
            return keyring_password

    return ''


def set_smtp_password(username: str, password: str) -> bool:
    """Store SMTP password in the system keyring.

    Args:
        username: The SMTP username.
        password: The password to store.

    Returns:
        True if successfully stored, False otherwise.

    Raises:
        RuntimeError: If keyring is not available.

    Note:
        This is the ONLY supported method for password storage.
        Passwords are never written to config files.
    """
    if not _KEYRING_AVAILABLE:
        raise RuntimeError(
            "Keyring not available. Install with: pip install keyring\n"
            "Alternatively, set the SMTP_PASSWORD environment variable."
        )

    try:
        keyring.set_password(_KEYRING_SERVICE, username, password)
        _logger.info("SMTP password stored securely in system keyring")
        return True
    except Exception as e:
        _logger.error("Failed to store password in keyring: %s", e)
        return False


def delete_smtp_password(username: str) -> bool:
    """Remove SMTP password from the system keyring.

    Args:
        username: The SMTP username.

    Returns:
        True if successfully deleted, False otherwise.
    """
    if not _KEYRING_AVAILABLE:
        return False

    try:
        keyring.delete_password(_KEYRING_SERVICE, username)
        _logger.info("SMTP password removed from system keyring")
        return True
    except Exception as e:
        _logger.debug("Could not delete password from keyring: %s", e)
        return False


# Default configuration settings for the email subsystem.  These
# values can be adjusted by calling ``configure_email_settings`` or
# ``load_config`` / ``save_config`` as appropriate.
#
# SECURITY: Note that 'password' and 'smtp_password' are NOT included
# in this config. Use get_smtp_password() to retrieve credentials.
config: Dict[str, Any] = {
    # When ``database_only_mode`` is True, outbound emails are queued
    # instead of being sent via SMTP.
    'database_only_mode': True,
    # Path to the directory where email templates are stored.  This
    # will be resolved relative to the project root at runtime.
    'templates_dir': 'templates/email',
    # Default sender address for outgoing emails.
    'sender_email': '',
    # Display name for the sender
    'sender_name': '',
    # SMTP server hostname or IP address.  Empty by default.
    'smtp_server': '',
    # SMTP server port.  Standard ports are 25 or 587 for TLS.
    'smtp_port': 25,
    # Whether to use TLS when connecting to the SMTP server.
    'use_tls': True,
    # Whether to use authentication
    'use_authentication': True,
    # Optional username for SMTP authentication.
    'username': os.environ.get('SMTP_USERNAME', ''),
    # Email signature appended to all emails
    'email_signature': '',
    # Delay between sending emails (prevents rate limiting)
    'send_delay': 1.0,
    # Maximum concurrent email sending threads
    'max_threads': 3,
    # Maximum retry attempts for failed emails
    'max_retries': 3,
    # Delay between retry attempts
    'retry_delay': 5,
    # Maximum attachment size in bytes
    'attachment_size_limit': 10485760,
    # Enable email subsystem logging
    'enable_logging': True,
    # Logging level
    'log_level': 'INFO',
}

# Property-like access for password (never stored, always retrieved securely)
# This provides backward compatibility for code that reads config['password']


class _SecureConfig(dict):
    """Config dict that retrieves passwords securely on access."""

    # Keys that should never be stored and must be retrieved securely
    _SENSITIVE_KEYS = {'password', 'smtp_password'}

    def __getitem__(self, key: str) -> Any:
        if key in self._SENSITIVE_KEYS:
            # Always retrieve password securely
            username = super().get('username', '')
            return get_smtp_password(username)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._SENSITIVE_KEYS:
            username = super().get('username', '')
            password = get_smtp_password(username)
            return password if password else default
        return super().get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._SENSITIVE_KEYS:
            _logger.warning(
                "Attempted to store '%s' in config. "
                "Use set_smtp_password() or SMTP_PASSWORD env var instead.",
                key
            )
            # Don't store the password in the dict - silently ignore
            return
        super().__setitem__(key, value)


# Replace the plain dict with our secure version
config = _SecureConfig(config)

def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        path: Path to the JSON configuration file. If None, tries default location.

    Returns:
        The loaded configuration dictionary
    """
    import json
    import logging
    import os

    logger = logging.getLogger(__name__)

    if path is None:
        # Use centralized config directory
        path = sys_paths.CONFIG_DIR / 'email_config.json'
    else:
        path = Path(path)

    if not path.exists():
        logger.warning(f"Config file not found at {path}, using defaults")
        return config

    try:
        with open(path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)

        # Update global config with loaded values
        for key, value in loaded_config.items():
            if key in config:
                config[key] = value

        logger.info(f"Configuration loaded from {path}")
        return config

    except Exception as e:
        logger.error(f"Failed to load config from {path}: {e}")
        return config

def save_config(path: str | Path | None = None) -> None:
    """Save the current configuration to a file.

    SECURITY: Passwords are NEVER saved to config files. They must be
    stored using environment variables or the system keyring.

    Args:
        path: Path where the configuration should be saved. If None, uses default location.
    """
    import json

    if path is None:
        # Use centralized config directory
        path = sys_paths.CONFIG_DIR / 'email_config.json'
    else:
        path = Path(path)

    try:
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # SECURITY: Create a sanitized copy without sensitive data
        # Never save passwords to config files
        sensitive_keys = {'password', 'smtp_password', 'secret', 'api_key'}
        safe_config = {
            key: value for key, value in dict(config).items()
            if key not in sensitive_keys
        }

        # Save sanitized config to JSON file
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(safe_config, f, indent=2)

        _logger.info("Configuration saved to %s (passwords excluded)", path)

    except Exception as e:
        _logger.error("Failed to save config to %s: %s", path, e)

def configure_email_settings(**kwargs: Any) -> None:
    """Update configuration values from keyword arguments.

    Only keys present in the default ``config`` dictionary will be
    updated.  Extra keys are ignored.
    """
    for key, value in kwargs.items():
        if key in config:
            config[key] = value

def ensure_email_config_for_database_mode() -> None:
    """Ensure that the configuration is valid when operating in database-only mode.

    Validates that the necessary configuration settings are present for
    database-only mode to function correctly.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Ensure database_only_mode is set
    if not config.get('database_only_mode'):
        logger.warning("database_only_mode is not enabled, enabling it now")
        config['database_only_mode'] = True

    # Validate templates directory exists or can be created
    templates_dir = config.get('templates_dir')
    if templates_dir:
        templates_path = Path(templates_dir)
        if not templates_path.exists():
            logger.info(f"Templates directory does not exist: {templates_path}")
            # Don't create it automatically, just log
        else:
            logger.debug(f"Templates directory found: {templates_path}")

    # In database-only mode, SMTP settings are optional but should be noted
    if not config.get('smtp_server'):
        logger.debug("No SMTP server configured (expected in database-only mode)")

    logger.info("Email configuration validated for database-only mode")

__all__ = [
    'config',
    'load_config',
    'save_config',
    'configure_email_settings',
    'ensure_email_config_for_database_mode',
    # Secure password management functions
    'get_smtp_password',
    'set_smtp_password',
    'delete_smtp_password',
]
