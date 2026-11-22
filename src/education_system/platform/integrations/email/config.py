"""Shared email configuration loader for all Education System subsystems.

Loads SMTP settings from the platform-wide config
(:data:`education_system.paths.PLATFORM_EMAIL_CONFIG_PATH`, currently
``var/data/platform/config/email_config.json``), falling back to the
per-university location for installs that predate the move to a shared file.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Shared config directory
# Runtime state lives under var/, not inside the package (ADR 0018).
from education_system.paths import (
    PLATFORM_CONFIG_DIR as SHARED_CONFIG_DIR,
    PLATFORM_DATA_DIR as SHARED_DATA_DIR,
    PLATFORM_EMAIL_CONFIG_PATH as SHARED_EMAIL_CONFIG_PATH,
    PLATFORM_SMTP_PASSWORD_FILE,
    UNIVERSITY_CONFIG_DIR,
)

# Legacy per-university location, for installs predating the shared config.
# This previously pointed at ``platform/post_18/university_system/data/config/``,
# which has not existed since the ADR 0018 move, so the fallback could never
# resolve. Kept in step with the same candidate in ``education_system.paths``.
_LEGACY_EMAIL_CONFIG: Path = UNIVERSITY_CONFIG_DIR / "email_config.json"

# Check for optional keyring support
try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False
    keyring = None

_KEYRING_SERVICE = "education_system_email"


def read_secret_file() -> str:
    """The SMTP password from the owner-only secrets file, or ``""``."""
    try:
        return PLATFORM_SMTP_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_secret_file(password: str) -> Path:
    """Write the SMTP password to the secrets file, readable by its owner only."""
    PLATFORM_SMTP_PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(PLATFORM_SMTP_PASSWORD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(password)
    os.chmod(PLATFORM_SMTP_PASSWORD_FILE, 0o600)
    return PLATFORM_SMTP_PASSWORD_FILE


def get_smtp_password(username: str | None = None) -> str:
    """The SMTP password from the SMTP_PASSWORD env var, the keyring or the
    owner-only secrets file — never from the config file."""
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
    return read_secret_file()


def set_smtp_password(username: str, password: str) -> bool:
    """Store SMTP password in the system keyring."""
    if not _KEYRING_AVAILABLE:
        raise RuntimeError("keyring not available")
    try:
        keyring.set_password(_KEYRING_SERVICE, username, password)
        return True
    except Exception:
        return False


def password_in_config_file(path: str | Path | None = None) -> bool:
    """Whether a plain-text ``smtp_password`` is still in the config file."""
    target = Path(path) if path else SHARED_EMAIL_CONFIG_PATH
    try:
        return bool(json.loads(target.read_text(encoding="utf-8")).get("smtp_password"))
    except (OSError, ValueError):
        return False


def move_password_out_of_config(path: str | Path | None = None) -> str:
    """Move a plain-text ``smtp_password`` from the config file into the
    keyring (when installed) or the owner-only secrets file, then remove it
    from the config file. Every other key is kept as it was. Returns where
    the password went, or ``""`` when there was nothing to move."""
    target = Path(path) if path else SHARED_EMAIL_CONFIG_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    password = data.get("smtp_password") or ""
    if not password:
        return ""
    username = data.get("smtp_username") or data.get("username") or ""
    where = ""
    if _KEYRING_AVAILABLE and username:
        try:
            keyring.set_password(_KEYRING_SERVICE, username, password)
            where = "keyring"
        except Exception:
            where = ""
    if not where:
        where = str(write_secret_file(password))
    data.pop("smtp_password", None)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, target)
    logger.info("SMTP password moved out of %s", target)
    return where


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
                pw = get_smtp_password(username)
                if not pw and data.get("smtp_password"):
                    logger.warning("SMTP password is stored in plain text in %s; move it "
                                   "out with move_password_out_of_config()", p)
                    pw = data["smtp_password"]
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
