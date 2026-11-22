"""Sealing confidential health fields at rest.

One Fernet key for the whole university, kept owner-only in
``var/secrets/health_field_key`` (``paths.UNIVERSITY_HEALTH_FIELD_KEY_FILE``)
— never beside the database, never regenerated per process. A sealed value
is stored as ``enc1:<token>``; :func:`unseal` returns plaintext for values
written before sealing existed, so old rows keep reading. There is no
fallback cipher: if the key is missing it is created once; if it cannot be
read, sealing fails loudly rather than storing something that only looks
encrypted.
"""

from __future__ import annotations

import os
import threading

PREFIX = "enc1:"
_LOCK = threading.Lock()
_FERNET = None   # cryptography.fernet.Fernet, created on first use


def _key_file():
    from education_system import paths
    return paths.UNIVERSITY_HEALTH_FIELD_KEY_FILE


def key_bytes() -> bytes:
    """The managed key, created once (owner-only) when missing. For the
    few callers that need the key itself (encrypting an export file); never
    log or store it."""
    path = _key_file()
    if path.exists():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:           # another process created it first
        return path.read_bytes().strip()
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def _fernet():
    """The cipher. ``cryptography`` is imported here, on first use, so that
    importing this module (every health screen does) stays cheap."""
    global _FERNET
    if _FERNET is not None:
        return _FERNET
    with _LOCK:
        if _FERNET is None:
            from cryptography.fernet import Fernet
            _FERNET = Fernet(key_bytes())
    return _FERNET


def reset() -> None:
    """Forget the cached key (tests that point the key file elsewhere)."""
    global _FERNET
    _FERNET = None


def is_sealed(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def seal(value):
    """``value`` encrypted for storage (``None`` and ``''`` stay as they are;
    an already sealed value is not sealed twice)."""
    if value is None or value == "" or is_sealed(value):
        return value
    return PREFIX + _fernet().encrypt(str(value).encode("utf-8")).decode("ascii")


def unseal(value):
    """The plaintext of a stored value; unsealed (older) values pass through.
    A sealed value that can't be decrypted raises ``ValueError``."""
    if not is_sealed(value):
        return value
    from cryptography.fernet import InvalidToken
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise ValueError("A sealed health field could not be decrypted with this key") from None


class FieldCipher:
    """``encrypt(bytes) -> bytes`` / ``decrypt(bytes) -> bytes`` over
    :func:`seal` / :func:`unseal`, for code written against a Fernet-like
    cipher object. Tokens carry the ``enc1:`` prefix."""

    def encrypt(self, data) -> bytes:
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)
        return seal(text).encode("ascii")

    def decrypt(self, token) -> bytes:
        text = token.decode("ascii") if isinstance(token, (bytes, bytearray)) else str(token)
        if not is_sealed(text):
            raise ValueError("Not a sealed health field")
        return unseal(text).encode("utf-8")


def cipher() -> FieldCipher:
    return FieldCipher()
