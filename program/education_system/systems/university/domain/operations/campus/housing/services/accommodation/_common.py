# Standard library imports
import csv
import os
import logging
import re
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging first using centralized configuration
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Setup logger using centralized configuration
logger = configure_logging(name=__name__)

# Application imports
from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Optional dependencies for export and dashboards
try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("pandas not available. Some export features will be disabled.")

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph  # Fixed typo
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    canvas = None
    logger.warning("reportlab not available. PDF generation will be disabled.")

# Integration imports with fallbacks
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, UserAuth
except ImportError:
    logger.warning("Authentication module not available. Using fallback.")
    def get_current_user():  # type: ignore
        return 'system'
    UserAuth = None  # type: ignore

try:
    from education_system.systems.university.infrastructure import email as email_manager
except ImportError:
    email_manager = None
    logger.warning("Email manager not available. Email features will be disabled.")

try:
    from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
except ImportError:
    logger.warning("Data backup module not available. Using fallback.")
    def backup_before_operation(operation_type):  # type: ignore
        logger.info(f"Backup requested before {operation_type} operation, but data_backup module not available")

# Shared path constants keep runtime artefacts inside program/data
from education_system.systems.university.infrastructure import paths

# Configuration constants
DB_PATH = os.fspath(paths.DEFAULT_DB_PATH)
NOTIFICATION_THRESHOLD_DAYS = 7
TEMPLATES_TABLE = 'accommodation_templates'
ACCOMMODATION_LOG_PATH = os.fspath(paths.LOG_DIR / 'accommodation')
UPLOADS_DIR = os.fspath(paths.DATA_DIR / 'uploads' / 'accommodation')

# Ensure required directories exist
for directory in [ACCOMMODATION_LOG_PATH, UPLOADS_DIR]:
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Could not create directory {directory}: {e}")

# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Import centralized auth management
from education_system.systems.university.infrastructure.shared_context import get_auth, set_auth as set_shared_auth

# Import internationalization support
from education_system.systems.university.infrastructure.i18n import get_text

# Import secure file upload handler
try:
    from education_system.systems.university.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None

# Import immutable audit logging for compliance
try:
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_current_user_id,
    )
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def secure_filename(x):
        return x
