from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import PROJECT_ROOT, LOG_DIR
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Import i18n for internationalization
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        init_i18n,
        get_current_language,
        get_current_language_name
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    def _t(key, **kwargs):
        """Fallback translation function"""
        # Extract last part of key and convert to readable text
        text = key.split('.')[-1].replace('_', ' ').title()
        # Handle variable substitution
        for k, v in kwargs.items():
            text = text.replace('{' + k + '}', str(v))
        return text

    def init_i18n(lang=None):
        """Fallback init function"""
        pass

    def get_current_language():
        """Fallback language getter"""
        return 'en'

    def get_current_language_name():
        """Fallback language name getter"""
        return 'English'

    def show_gui_language_selector(parent):
        """Fallback language selector"""
        from tkinter import messagebox
        messagebox.showinfo("Info", "Language selection not available")

# Availability flags
STUDENT_SYSTEM_AVAILABLE = False  # define up front

# Import all original functionality
try:
    from education_system.university_system.infrastructure.logging.log_management import get_log_manager
    STUDENT_SYSTEM_AVAILABLE = True  # set True on successful import
except ImportError:
    print("Warning: Original log_management module not found. Using fallback implementation.")
    STUDENT_SYSTEM_AVAILABLE = False  # keep False on failure

    def get_log_manager():
        """Fallback get_log_manager function"""
        from education_system.university_system.infrastructure.logging.gui.fallbacks import FallbackLogManager
        return FallbackLogManager()

def get_student_db_connection():
    """Direct database connection without importing main.py"""
    if not STUDENT_SYSTEM_AVAILABLE:
        return None
    from education_system.university_system.infrastructure.database.db import sqlite3
    import os
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DB_PATH

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def initialize_database():
    """Initialize database with required tables for log management"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                username TEXT,
                action TEXT,
                status TEXT,
                module TEXT,
                message TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        ''')

        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                message TEXT,
                severity TEXT DEFAULT 'medium',
                triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT FALSE,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at DATETIME,
                user_id TEXT,
                metadata TEXT
            )
        ''')

        # Create saved_searches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                search_params TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create students table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                enrollment_date DATE,
                status TEXT DEFAULT 'active'
            )
        ''')

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
