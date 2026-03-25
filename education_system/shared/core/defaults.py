"""Shared default configuration utilities used by all subsystems.

Provides common password generation, JWT secret management, and auth
constants so each subsystem's ``core/defaults.py`` only needs to define
system-specific values (ID prefixes, credentials, year groups, etc.).
"""

import os
import secrets
import string
from pathlib import Path

# ── Auth defaults (shared baseline) ─────────────────────────────────────
SESSION_TIMEOUT_MINUTES = 30
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Staff ID prefix is the same across all school systems
STAFF_ID_PREFIX = "STF"


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.

    Guarantees at least one lowercase, uppercase, digit, and special char.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password


def load_or_create_jwt_secret(
    env_var: str,
    secret_file: Path,
) -> str:
    """Load JWT secret from env var or persistent file. Generate once if missing.

    Args:
        env_var: Environment variable name to check first.
        secret_file: Path to the persistent secret file.
    """
    env_val = os.getenv(env_var)
    if env_val:
        return env_val
    try:
        if secret_file.exists():
            return secret_file.read_text().strip()
    except OSError:
        pass
    # Generate and persist
    new_secret = secrets.token_hex(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(new_secret)
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return new_secret
