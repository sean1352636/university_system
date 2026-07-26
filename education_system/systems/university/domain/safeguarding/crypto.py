import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.config import (
    _DRAFT_DIR,
    _KEY_FILE,
    _SECURE_DIR,
)

FIELD_ENCRYPTION_ENABLED = True


def _encrypt_field(text):
    """Return (blob, encrypted_flag). If encryption is disabled or unavailable,
    returns (None, False) and the caller stores the plaintext column instead."""
    if not text or not FIELD_ENCRYPTION_ENABLED:
        return None, False
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_or_create_key())
        return f.encrypt(text.encode("utf-8")), True
    except Exception:
        logger.warning("Field encryption unavailable; storing plaintext", exc_info=True)
        return None, False


def _decrypt_field(blob):
    if not blob:
        return ""
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_or_create_key())
        return f.decrypt(blob).decode("utf-8")
    except Exception:
        logger.warning("Could not decrypt field", exc_info=True)
        return ""


def _ensure_dirs():
    for d in (_SECURE_DIR, _DRAFT_DIR):
        os.makedirs(d, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass


def _get_or_create_key() -> bytes:
    """Return the Fernet key for at-rest attachment encryption. Generated once."""
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read().strip()
    try:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
    except Exception:
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass
    return key


def encrypt_and_store(src_path: str) -> str | None:
    """Encrypt the file at src_path with Fernet and store it under secure_uploads/.
    Returns the stored filename (not full path) or None on failure. Falls back to
    plain copy with a .plain suffix if cryptography is unavailable."""
    if not src_path or not os.path.isfile(src_path):
        return None
    _ensure_dirs()
    base = os.path.basename(src_path)
    safe_base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:80]
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    token = secrets.token_hex(4)
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_or_create_key())
        with open(src_path, "rb") as r:
            blob = f.encrypt(r.read())
        out_name = f"{stamp}_{token}_{safe_base}.enc"
        with open(os.path.join(_SECURE_DIR, out_name), "wb") as w:
            w.write(blob)
        return out_name
    except Exception:
        logger.warning("Encryption unavailable; storing attachment in plain form", exc_info=True)
        out_name = f"{stamp}_{token}_{safe_base}.plain"
        shutil.copy2(src_path, os.path.join(_SECURE_DIR, out_name))
        return out_name


def decrypt_to_temp(stored_name: str) -> str | None:
    """Decrypt a stored attachment to a temp file and return that path."""
    if not stored_name:
        return None
    path = os.path.join(_SECURE_DIR, stored_name)
    if not os.path.isfile(path):
        return None
    if stored_name.endswith(".plain"):
        return path
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_or_create_key())
        with open(path, "rb") as r:
            data = f.decrypt(r.read())
        import tempfile

        out = tempfile.NamedTemporaryFile(
            delete=False,
            suffix="_" + re.sub(r"\.enc$", "", stored_name.split("_", 3)[-1]),
        )
        out.write(data)
        out.close()
        return out.name
    except Exception:
        logger.warning("Could not decrypt attachment %s", stored_name, exc_info=True)
        return None


__all__ = [
    "FIELD_ENCRYPTION_ENABLED",
    "_encrypt_field",
    "_decrypt_field",
    "_ensure_dirs",
    "_get_or_create_key",
    "encrypt_and_store",
    "decrypt_to_temp",
]
