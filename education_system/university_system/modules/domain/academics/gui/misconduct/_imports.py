"""Shared imports for the Academic Misconduct Panel modules."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import json
from education_system.university_system.infrastructure.database.db import sqlite3

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None, **kwargs):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

# Database and email imports
try:
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    from pathlib import Path
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[6] / "data" / "db_files" / "student_records.db"

try:
    from education_system.university_system.infrastructure.email.email_service import queue_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    queue_email = None

# Authentication imports
try:
    from education_system.university_system.infrastructure.shared_context import get_auth, is_auth_initialized
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    is_auth_initialized = lambda: False
    get_auth = None

# Secure file upload imports
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    secure_filename = lambda x: x

# Define a dummy auth class for type checking when auth is not available
if not AUTH_AVAILABLE:
    class _DummyAuth:
        """Dummy auth class used when auth is not available"""
        pass
else:
    _DummyAuth = None
