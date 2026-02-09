"""Shared imports and setup for data backup GUI modules."""
from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import datetime
import tempfile
import xml.etree.ElementTree as ET
import shutil
import os
import json
import hashlib
import posixpath
import re
from pathlib import Path
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"

# Import centralized paths
try:
    from university_system.modules.shared.constants.paths import (
        BACKUP_DIR, LOG_DIR, BACKUP_TEMPLATES_DIR, DATA_DIR, DEFAULT_DB_PATH as DB_PATH, PROJECT_ROOT
    )
except ImportError:
    # Fallback if paths module not available - use PROJECT_ROOT relative paths
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    BACKUP_DIR = PROJECT_ROOT / "backups"
    LOG_DIR = PROJECT_ROOT / "logs"
    BACKUP_TEMPLATES_DIR = PROJECT_ROOT / "templates" / "backup_templates"
    DATA_DIR = PROJECT_ROOT / "data"
    DB_PATH = DEFAULT_DB_PATH

try:
    from university_system.infrastructure.database.db import get_db_connection, sqlite3
    from university_system.infrastructure.database.database_utils import cleanup_database_connections
    from university_system.modules.shared.utils.sql_safety import (
        validate_table_name,
        SQLIdentifierError,
    )
    print("Database modules imported successfully")
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")
    # Create minimal fallbacks
    def get_db_connection():
        return None

    def cleanup_database_connections():
        """
        Cleanup database connections (fallback implementation)

        This is a fallback implementation used when the database_utils module
        is not available. In a production environment, this should close all
        open database connections and clear connection pools to prevent
        database lock issues during backup operations.
        """
        # Basic cleanup - close any global connection references
        try:
            import gc
            # Force garbage collection to close any lingering connections
            gc.collect()
            print("Database connections cleanup attempted (fallback mode)")
        except Exception as e:
            print(f"Warning: Could not cleanup database connections: {e}")

# Logging setup
try:
    from university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="backup_gui")
except Exception:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
