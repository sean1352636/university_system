"""Field-level encryption for sensitive data using Fernet (AES-128-CBC + HMAC-SHA256)."""

import os
import logging
import base64

from education_system.platform.governance.security.fail_closed import (
    SecurityControlError,
    alert_security_failure,
)
from education_system.platform.kernel.core.safe_paths import open_exclusive

logger = logging.getLogger(__name__)

_PREFIX = "ENC:"

#: ``APP_ENV`` values in which running without field encryption is tolerated.
_DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})


def _encryption_required() -> bool:
    """True unless ``APP_ENV`` names a development environment.

    Defaulting to required means an unset ``APP_ENV`` — the shape a
    misconfigured deployment takes — is treated as production.
    """
    return os.environ.get("APP_ENV", "production").strip().lower() not in _DEV_ENVIRONMENTS

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography package not installed; encryption disabled")


def generate_key() -> str:
    """Generate a new Fernet encryption key."""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package required")
    return Fernet.generate_key().decode()


def load_key() -> str | None:
    """Load encryption key from ENCRYPTION_KEY env var."""
    return os.environ.get("ENCRYPTION_KEY")


def save_key(filepath: str):
    """Generate and save a new key to a file, owner-readable only.

    Uses exclusive creation: refusing to overwrite prevents both clobbering a
    key that is already encrypting live data and following a symlink an
    attacker planted at the destination. The 0o600 mode is applied by
    ``open(2)``, so the key is never briefly world-readable — the previous
    plain ``open(filepath, "w")`` wrote it at the process umask, typically
    0o644.
    """
    key = generate_key()
    with open_exclusive(filepath) as handle:
        handle.write(key)
    return key


class EncryptionUnavailableError(SecurityControlError):
    """Field encryption was required but could not be initialised."""

    def __init__(self, message: str):
        super().__init__("encryption.field", message)


class FieldEncryptor:
    """Encrypts/decrypts individual field values.

    In production an unusable key is fatal. The previous behaviour — log a
    warning and pass values through in the clear — meant a typo'd or unset
    ``ENCRYPTION_KEY`` silently wrote every "encrypted" field as plaintext
    into the database, and nothing downstream could tell the difference,
    because :meth:`encrypt` returned the input unchanged.
    """

    def __init__(self, key: str | None = None, *, require: bool | None = None):
        """
        Args:
            key: Fernet key. Falls back to ``ENCRYPTION_KEY``.
            require: Whether an unusable key is fatal. Defaults to "yes unless
                ``APP_ENV`` names a development environment", so production
                fails closed without any per-call-site opt-in.

        Raises:
            EncryptionUnavailableError: when encryption is required and the key
                is missing, malformed, or the cryptography package is absent.
        """
        self._key = key or load_key()
        self._fernet = None
        self._required = _encryption_required() if require is None else require
        failure: str | None = None

        if not HAS_CRYPTO:
            failure = "the cryptography package is not installed"
        elif not self._key:
            failure = "ENCRYPTION_KEY is not set"
        else:
            try:
                self._fernet = Fernet(
                    self._key.encode() if isinstance(self._key, str) else self._key
                )
            except (ValueError, TypeError) as exc:
                # Fernet raises ValueError for a malformed/wrong-length key.
                failure = f"ENCRYPTION_KEY is not a valid Fernet key ({exc})"

        if self._fernet is None:
            if self._required:
                alert_security_failure("encryption.field", failure or "unavailable",
                                       severity="critical")
                raise EncryptionUnavailableError(
                    f"Field encryption is required but unavailable: {failure}. "
                    f"Set a valid ENCRYPTION_KEY (generate one with "
                    f"`python -c \"from cryptography.fernet import Fernet; "
                    f"print(Fernet.generate_key().decode())\"`)."
                )
            logger.warning(
                "SECURITY WARNING: field encryption is disabled (%s) — sensitive "
                "fields will be stored in PLAINTEXT. This is permitted only "
                "because APP_ENV is a development environment.",
                failure,
            )

    @property
    def is_available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode())
        return _PREFIX + base64.urlsafe_b64encode(token).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            return ciphertext
        if not is_encrypted(ciphertext):
            return ciphertext
        raw = ciphertext[len(_PREFIX):]
        token = base64.urlsafe_b64decode(raw.encode())
        return self._fernet.decrypt(token).decode()

    def encrypt_field(self, value):
        if value is None:
            return None
        return self.encrypt(str(value))

    def decrypt_field(self, value):
        if value is None:
            return None
        if not is_encrypted(str(value)):
            return value
        return self.decrypt(str(value))


def is_encrypted(value) -> bool:
    """Check if a value has the encryption prefix marker."""
    return isinstance(value, str) and value.startswith(_PREFIX)
