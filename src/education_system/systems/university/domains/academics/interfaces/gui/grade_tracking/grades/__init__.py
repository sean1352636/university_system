"""Shared grade-tracking dependencies."""

import tkinter as tk

from tkinter import ttk, filedialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking._dialogs import messagebox

import tkinter.scrolledtext as scrolledtext

from education_system.systems.university.infrastructure.database.db import sqlite3

import os

from pathlib import Path

import csv


import math


from datetime import datetime, timedelta

import json
import logging

from education_system import paths

DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
logger = logging.getLogger(__name__)
MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 10_000
MAX_FIELD_LENGTH = 5_000

from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.utils import ensure_column_exists

try:
    from education_system.systems.university.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

try:
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

def require_grade_audit(conn=None, **kwargs):
    """Persist an immutable audit event or abort the grade transaction.

    Pass *conn* — the connection the grade was written on — so the audit
    entry joins that transaction. Without it the audit opens a second
    connection and blocks on the write lock the caller is still holding,
    which fails every save with "database is locked".
    """
    if not IMMUTABLE_AUDIT_AVAILABLE or not safe_log_security_event(conn=conn, **kwargs):
        raise RuntimeError("Grade audit could not be persisted")


try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    def get_connection():
        """Fallback database connection function"""
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        return sqlite3.connect(str(DEFAULT_DB_PATH))
