"""Shared email configuration loader for all Education System subsystems.

Loads SMTP settings from ``education_system/shared/data/config/email_config.json``.
Falls back to the legacy university-system location if the shared file is missing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Shared config directory
SHARED_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
SHARED_CONFIG_DIR: Path = SHARED_DATA_DIR / "config"
SHARED_EMAIL_CONFIG_PATH: Path = SHARED_CONFIG_DIR / "email_config.json"

# Legacy university location (fallback)
_LEGACY_EMAIL_CONFIG: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "post_18" / "university_system" / "data" / "config" / "email_config.json"
)

# Check for optional keyring support
try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False
    keyring = None

_KEYRING_SERVICE = "education_system_email"


def get_smtp_password(username: str | None = None) -> str:
    """Retrieve the SMTP password from env var or keyring (never from file)."""
    env_pw = os.environ.get("SMTP_PASSWORD", "")
    if env_pw:
        return env_pw
    if username and _KEYRING_AVAILABLE:
        try:
            pw = keyring.get_password(_KEYRING_SERVICE, username)
            if pw:
                return pw
        except Exception:
            pass
    return ""


def set_smtp_password(username: str, password: str) -> bool:
    """Store SMTP password in the system keyring."""
    if not _KEYRING_AVAILABLE:
        raise RuntimeError("keyring not available")
    try:
        keyring.set_password(_KEYRING_SERVICE, username, password)
        return True
    except Exception:
        return False


def load_email_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load email configuration from a JSON file.

    Resolution order:
      1. Explicit *path* argument
      2. ``shared/data/config/email_config.json``
      3. ``university_system/data/config/email_config.json`` (legacy)
      4. Built-in defaults
    """
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    candidates.append(SHARED_EMAIL_CONFIG_PATH)
    candidates.append(_LEGACY_EMAIL_CONFIG)

    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # Resolve password: file value → env var / keyring → legacy file
                username = data.get("smtp_username", "")
                pw = data.get("smtp_password", "") or get_smtp_password(username)
                if not pw:
                    # Check other config files for the password
                    for fallback in candidates:
                        if fallback == p or not fallback.exists():
                            continue
                        try:
                            with open(fallback, "r", encoding="utf-8") as fb:
                                fb_data = json.load(fb)
                            pw = fb_data.get("smtp_password", "")
                            if pw:
                                break
                        except Exception:
                            pass
                data["smtp_password"] = pw
                logger.debug("Email config loaded from %s", p)
                return data
            except Exception as exc:
                logger.warning("Failed to load email config from %s: %s", p, exc)

    logger.info("No email config file found; using defaults")
    return {
        "database_only_mode": True,
        "smtp_server": "",
        "smtp_port": 587,
        "use_tls": True,
        "smtp_username": "",
        "smtp_password": "",
        "sender_email": "",
        "sender_name": "Education System",
    }


def save_email_config(data: Dict[str, Any], path: str | Path | None = None) -> None:
    """Save email configuration (passwords are stripped)."""
    target = Path(path) if path else SHARED_EMAIL_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    sensitive = {"password", "smtp_password", "secret", "api_key"}
    safe = {k: v for k, v in data.items() if k not in sensitive}

    with open(target, "w", encoding="utf-8") as fh:
        json.dump(safe, fh, indent=2)
    logger.info("Email config saved to %s (passwords excluded)", target)
