"""Shared imports for the Academic Misconduct Panel modules.

University-specific imports use graceful fallbacks.
"""

import sqlite3
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internationalisation — try each system's i18n, fall back to identity
# ---------------------------------------------------------------------------
_t = None
try:
    import importlib
    _m = importlib.import_module("education_system.university_system.core.i18n")
    _t = getattr(_m, "get_text", None) or getattr(_m, "t", None)
except ImportError:
    pass

if _t is None:
    def _t(key, default=None, **kwargs):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

# ---------------------------------------------------------------------------
# Database path — configurable, detected per-system, or fallback
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = None

# Try university
try:
    from education_system.university_system.core.paths import DEFAULT_DB_PATH as _p
    DEFAULT_DB_PATH = _p
except ImportError:
    pass

# Absolute fallback — use shared data dir
if DEFAULT_DB_PATH is None:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db_files" / "misconduct.db"

# ---------------------------------------------------------------------------
# Email — optional
# ---------------------------------------------------------------------------
EMAIL_AVAILABLE = False
queue_email = None
try:
    from education_system.university_system.infrastructure.email.email_service import queue_email
    EMAIL_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Authentication — optional
# ---------------------------------------------------------------------------
AUTH_AVAILABLE = False
get_auth = None
is_auth_initialized = lambda: False
try:
    from education_system.university_system.infrastructure.shared_context import get_auth, is_auth_initialized
    AUTH_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Secure file upload — optional (fallback: basic sanitisation)
# ---------------------------------------------------------------------------
SECURE_UPLOAD_AVAILABLE = False
validate_upload = None
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename as _sf,
    )
    secure_filename = _sf
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    import re as _re

    def secure_filename(filename: str) -> str:
        """Basic filename sanitisation when the security module is unavailable."""
        # Remove path separators and null bytes
        name = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
        # Keep only safe chars
        name = _re.sub(r'[^\w\s\-.]', '', name).strip()
        return name or "untitled"


# ---------------------------------------------------------------------------
# Hashing utility (from evidence organizer)
# ---------------------------------------------------------------------------
def compute_file_hash(filepath: str | Path) -> str:
    """Compute SHA-256 hash of a file for integrity verification."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


# Dummy auth class for type checking when auth is not available
if not AUTH_AVAILABLE:
    class _DummyAuth:
        """Dummy auth class used when auth is not available."""
        pass
else:
    _DummyAuth = None
