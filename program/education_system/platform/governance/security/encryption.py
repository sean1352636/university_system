"""Field-level encryption for sensitive data using Fernet (AES-128-CBC + HMAC-SHA256)."""

import os
import logging
import base64

logger = logging.getLogger(__name__)

_PREFIX = "ENC:"

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
    """Generate and save a new key to a file."""
    key = generate_key()
    with open(filepath, "w") as f:
        f.write(key)
    return key


class FieldEncryptor:
    """Encrypts/decrypts individual field values."""

    def __init__(self, key: str | None = None):
        self._key = key or load_key()
        self._fernet = None
        if self._key and HAS_CRYPTO:
            try:
                self._fernet = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
            except Exception:
                logger.error("Invalid encryption key")
        if self._fernet is None:
            logger.warning(
                "SECURITY WARNING: ENCRYPTION_KEY not set — sensitive fields will be "
                "stored in plaintext. Set the ENCRYPTION_KEY environment variable for "
                "production deployments."
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
