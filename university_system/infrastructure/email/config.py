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
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from university_system.modules.shared.constants import paths as sys_paths

# Default configuration settings for the email subsystem.  These
# values can be adjusted by calling ``configure_email_settings`` or
# ``load_config`` / ``save_config`` as appropriate.
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
    'smtp_username': '',
    # Optional password for SMTP authentication.
    'smtp_password': '',
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

    Args:
        path: Path where the configuration should be saved. If None, uses default location.
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    if path is None:
        # Use centralized config directory
        path = sys_paths.CONFIG_DIR / 'email_config.json'
    else:
        path = Path(path)

    try:
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save config to JSON file
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Configuration saved to {path}")

    except Exception as e:
        logger.error(f"Failed to save config to {path}: {e}")

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

__all__ = ['config', 'load_config', 'save_config', 'configure_email_settings', 'ensure_email_config_for_database_mode']
