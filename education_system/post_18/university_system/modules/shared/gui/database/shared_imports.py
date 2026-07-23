"""Shared imports and setup for data backup GUI modules."""
from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import datetime
import tempfile
import defusedxml.ElementTree as ET
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
    from education_system.post_18.university_system.core.i18n import (
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
    from education_system.post_18.university_system.core.paths import (
        BACKUP_DIR, BACKUP_DATABASE_DIR, LOG_DIR, BACKUP_TEMPLATES_DIR, USER_BACKUP_TEMPLATES_DIR, DATA_DIR, DEFAULT_DB_PATH as DB_PATH, PROJECT_ROOT
    )
except ImportError as exc:
    raise ImportError(
        "Unable to load centralized path constants from "
        "education_system.post_18.university_system.core.paths"
    ) from exc

try:
    from education_system.post_18.university_system.infrastructure.database.db import get_db_connection, sqlite3
    from education_system.post_18.university_system.infrastructure.database.database_utils import cleanup_database_connections
    from education_system.post_18.university_system.core.sql_safety import (
        validate_table_name,
        SQLIdentifierError,
    )
    logging.getLogger(__name__).debug("Database modules imported successfully")
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
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="backup_gui")
except Exception:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
