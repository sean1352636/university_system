"""Password hashing and validation using bcrypt.

Includes legacy PBKDF2-SHA256 verification for migrated university accounts.
"""

import hashlib
import re
import bcrypt

from education_system.shared.auth.defaults import MIN_PASSWORD_LENGTH


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str, legacy_salt: str | None = None) -> bool:
    """Verify a password against its hash.

    Supports bcrypt (default) and legacy PBKDF2-SHA256 hashes for migrated
    university accounts.  When *legacy_salt* is provided the hash is treated
    as a PBKDF2 hex digest; otherwise bcrypt verification is used.

    Returns True if the password matches, False otherwise.
    """
    if legacy_salt:
        return _verify_pbkdf2_legacy(password, legacy_salt, password_hash)
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def _verify_pbkdf2_legacy(password: str, salt: str, stored_hash: str) -> bool:
    """Verify a password against a legacy PBKDF2-SHA256 hash.

    The university system used PBKDF2-SHA256 with 1,000,000 iterations and a
    hex-encoded 16-byte salt.
    """
    try:
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            1_000_000,
            dklen=64,
        )
        return key.hex() == stored_hash
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Check password meets minimum strength requirements.

    Returns (is_valid, message).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."

    return True, "Password meets requirements."
