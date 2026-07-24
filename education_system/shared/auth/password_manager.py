"""Password hashing and validation using bcrypt.

Includes legacy PBKDF2-SHA256 verification for migrated university accounts.
"""

import hashlib
import hmac
import re
import bcrypt

from education_system.shared.auth.defaults import MIN_PASSWORD_LENGTH

# Top 100 common passwords (lowercase) - reject these regardless of complexity
_COMMON_PASSWORDS = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "michael", "shadow", "123123", "654321", "superman", "qazwsx",
    "football", "password1", "password123", "batman", "login",
    "admin123", "admin1234", "staff123", "staff1234", "student123", "student1234",
    "welcome", "welcome1", "changeme", "p@ssw0rd", "passw0rd", "p@ssword",
    "p@ssword1", "qwerty123", "1q2w3e4r", "1qaz2wsx", "zaq1xsw2",
    "password1!", "abcdef", "abcd1234", "121212", "flower", "hello", "charlie",
    "donald", "loveme", "jordan", "access", "ranger", "buster", "thomas",
    "robert", "soccer", "hockey", "killer", "george", "andrew", "pepper",
    "ginger", "hunter", "dallas", "matrix", "yankees", "thunder", "starwars",
    "princess", "mustang", "cheese", "corvette", "merlin", "cookie",
    "summer", "winter", "spring", "autumn", "january", "february", "march",
    "education", "teacher", "student", "secondary", "sixth_form", "university",
    "parent123", "parent1234", "superadmin", "superadmin@123",
})

# Dummy hash for timing-attack prevention when no valid hash exists
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def constant_time_dummy_verify(password: str) -> None:
    """Run a dummy bcrypt comparison so timing matches a real verify.

    Call this from auth code paths that fail before reaching the real
    :func:`verify_password` (e.g. unknown user, deactivated account) so an
    attacker can't tell from response time whether a username exists.
    """
    try:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
    except (ValueError, AttributeError):
        pass


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
        # Run dummy comparison to prevent timing oracle
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
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
        return hmac.compare_digest(key.hex(), stored_hash)
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

    if password.lower() in _COMMON_PASSWORDS:
        return False, "Password is too common. Please choose a more unique password."

    return True, "Password meets requirements."
