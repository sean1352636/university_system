# _common.py
# Shared imports and module-level configuration for the medical accommodation GUI package.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
import os
import sys
import threading
from datetime import datetime, timedelta
import json
import csv
from education_system.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging

# Import i18n for language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Email service imports
try:
    from education_system.university_system.infrastructure.email.template_utils import render_template
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

# Import database utilities
try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    # Fallback to creating our own get_connection
    from education_system.university_system.core import paths
    def get_connection():
        """Get database connection"""
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

# Import authentication utilities
try:
    from education_system.university_system.infrastructure.auth import get_current_user
except ImportError:
    def get_current_user():
        """Fallback function when auth is not available"""
        return None

# Import the original accommodation module to maintain compatibility
try:
    from education_system.university_system.modules.domain.campus.housing.services.accommodation import (
        auth, apply_template, bulk_import_from_csv, check_conflict as cli_check_conflict,
        check_expiry_notifications, display_accommodation_menu,
        fix_accommodation_db_schema, generate_statistics_report,
        get_accommodation_types, init_accommodation_db, log_action,
        migrate_audit_log_schema, notify_student as cli_notify_student,
        save_template, validate_student_id, validate_date,
        verify_database_schema, TEMPLATES_TABLE, set_auth
    )
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False
    TEMPLATES_TABLE = 'accommodation_templates'
    print("Warning: Original accommodation module not found. GUI-only mode.")
    # Fallback validate_date function
    def validate_date(date_str):
        """Validate date format"""
        if not date_str:
            return True, None
        try:
            datetime.fromisoformat(date_str)
            return True, None
        except ValueError:
            return False, "Invalid date format. Please use YYYY-MM-DD format."

# Import backup functionality
try:
    from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
    BACKUP_AVAILABLE = True
except ImportError:
    BACKUP_AVAILABLE = False
    def backup_before_operation(operation_type):
        """Fallback when backup module not available"""
        logging.info(f"Backup requested for {operation_type} but backup module not available")

# Import secure file upload handler
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

# Configure logger for this module
logger = logging.getLogger(__name__)
