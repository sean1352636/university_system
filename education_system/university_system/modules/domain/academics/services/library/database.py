from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def get_db_connection() -> Optional[sqlite3.Connection]:
    """Get database connection using the consolidated database file."""
    try:
        return get_db_conn(db_path=DATABASE_FILE, row_factory=False)
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        return None


def init_library_db():
    """Initialize the enhanced library database with all new features"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # First, check if library_settings table exists and get its structure
        cursor.execute("PRAGMA table_info(library_settings)")
        existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        # Drop and recreate library_settings table if it doesn't have the right structure
        expected_columns = {
            'setting_name': 'TEXT',
            'setting_value': 'TEXT',
            'description': 'TEXT',
            'setting_type': 'TEXT',
            'min_value': 'REAL',
            'max_value': 'REAL',
            'allowed_values': 'TEXT'
        }
        
        if not all(col in existing_columns for col in expected_columns.keys()):
            print(get_text("library.updating_settings_table"))
            
            # Backup existing settings if table exists
            existing_settings = []
            try:
                cursor.execute("SELECT setting_name, setting_value FROM library_settings")
                existing_settings = cursor.fetchall()
            except sqlite3.Error:
                pass  # Table doesn't exist yet
            
            # Drop the old table
            cursor.execute("DROP TABLE IF EXISTS library_settings")
            
            # Create new table with correct structure
            cursor.execute('''
            CREATE TABLE library_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                description TEXT,
                setting_type TEXT DEFAULT 'string',
                min_value REAL,
                max_value REAL,
                allowed_values TEXT
            )
            ''')
            
            # Restore existing settings with default values for new columns
            for setting_name, setting_value in existing_settings:
                cursor.execute('''
                INSERT INTO library_settings 
                (setting_name, setting_value, description, setting_type)
                VALUES (?, ?, ?, ?)
                ''', (setting_name, setting_value, 'Existing setting', 'string'))
        
        # Enhanced books table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            publisher TEXT,
            category TEXT,
            year_published INTEGER,
            description TEXT,
            location TEXT,
            status TEXT DEFAULT 'available',
            added_date TEXT,
            last_updated TEXT,
            reading_level TEXT,
            tags TEXT,
            cover_image_path TEXT,
            digital_copy_path TEXT,
            acquisition_cost REAL DEFAULT 0.0,
            barcode TEXT UNIQUE,
            qr_code_path TEXT,
            total_pages INTEGER,
            language TEXT DEFAULT 'English',
            edition TEXT,
            condition_notes TEXT
        )
        ''')
        
        # Enhanced book_loans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            checkout_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT DEFAULT 'active',
            fine_amount REAL DEFAULT 0.0,
            renewal_count INTEGER DEFAULT 0,
            reading_progress INTEGER DEFAULT 0,
            checkout_method TEXT DEFAULT 'manual',
            staff_id TEXT,
            notes TEXT
        )
        ''')
        
        # Enhanced book_reservations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reservation_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority_order INTEGER DEFAULT 1,
            notification_sent BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Book reviews and ratings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            review_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            helpful_votes INTEGER DEFAULT 0,
            moderated_by TEXT,
            moderation_date TEXT
        )
        ''')
        
        # Reading lists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_lists (
            list_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            creator_id TEXT NOT NULL,
            created_date TEXT NOT NULL,
            is_public BOOLEAN DEFAULT FALSE,
            is_collaborative BOOLEAN DEFAULT FALSE,
            category TEXT,
            target_reading_level TEXT
        )
        ''')
        
        # Reading list items
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_list_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            book_id TEXT NOT NULL,
            added_date TEXT NOT NULL,
            added_by TEXT NOT NULL,
            notes TEXT,
            order_index INTEGER DEFAULT 0
        )
        ''')
        
        # User preferences and profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            preferred_categories TEXT,
            preferred_authors TEXT,
            reading_level TEXT,
            notification_preferences TEXT,
            privacy_settings TEXT,
            reading_goals TEXT,
            language_preference TEXT DEFAULT 'English'
        )
        ''')
        
        # Reading goals and achievements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_goals (
            goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            target_value INTEGER NOT NULL,
            current_value INTEGER DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_date TEXT NOT NULL
        )
        ''')
        
        # User achievements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_name TEXT NOT NULL,
            description TEXT,
            earned_date TEXT NOT NULL,
            points INTEGER DEFAULT 0
        )
        ''')
        
        # Book recommendations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            generated_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            clicked BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Notification queue
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_queue (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_date TEXT NOT NULL,
            send_date TEXT,
            sent BOOLEAN DEFAULT FALSE,
            delivery_method TEXT DEFAULT 'email',
            priority INTEGER DEFAULT 1
        )
        ''')
        
        # Digital library items
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS digital_library (
            digital_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            category TEXT,
            description TEXT,
            access_level TEXT DEFAULT 'public',
            download_count INTEGER DEFAULT 0,
            added_date TEXT NOT NULL
        )
        ''')
        
        # System audit log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            table_affected TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            success BOOLEAN DEFAULT TRUE
        )
        ''')
        
        # Book suggestions/requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            requested_date TEXT NOT NULL,
            processed_date TEXT,
            processed_by TEXT,
            notes TEXT
        )
        ''')
        
        # Inter-library loans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interlibrary_loans (
            ill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            source_library TEXT,
            request_date TEXT NOT NULL,
            expected_arrival TEXT,
            actual_arrival TEXT,
            due_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'requested',
            cost REAL DEFAULT 0.0
        )
        ''')
        
        # Usage analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            category TEXT,
            additional_data TEXT
        )
        ''')

        # Note: Library fine payments are now stored in the unified 'payments' table
        # with source_type='library'. Refunds are tracked in 'unified_refunds'.
        # Ensure payments table has required columns for library tracking
        try:
            cursor.execute("PRAGMA table_info(payments)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col_name, col_type, col_default in [
                ('source_type', 'TEXT', None),
                ('reference_id', 'TEXT', None),
                ('reference_type', 'TEXT', None),
                ('payment_reference', 'TEXT', None),
            ]:
                if col_name not in existing_cols:
                    cursor.execute(f'ALTER TABLE payments ADD COLUMN {col_name} {col_type}')
        except Exception as e:
            logging.warning(f"Could not ensure payments table columns: {e}")

        # Insert enhanced default settings
        enhanced_settings = [
            ('loan_period_days', '14', 'Default loan period in days', 'integer', 1, 365, None),
            ('max_loans', '5', 'Maximum number of books a user can borrow', 'integer', 1, 50, None),
            ('fine_per_day', '0.50', 'Fine amount per day for overdue books', 'decimal', 0.0, 10.0, None),
            ('reservation_period_days', '3', 'Number of days a reservation is valid', 'integer', 1, 30, None),
            ('max_renewals', '2', 'Maximum number of times a book can be renewed', 'integer', 0, 10, None),
            ('sms_notifications', 'false', 'Enable SMS notifications', 'boolean', None, None, 'true,false'),
            ('email_notifications', 'true', 'Enable email notifications', 'boolean', None, None, 'true,false'),
            ('auto_backup', 'true', 'Enable automatic backups', 'boolean', None, None, 'true,false'),
            ('backup_frequency_hours', '24', 'Backup frequency in hours', 'integer', 1, 168, None),
            ('reading_level_tracking', 'true', 'Enable reading level tracking', 'boolean', None, None, 'true,false'),
            ('recommendation_engine', 'true', 'Enable book recommendations', 'boolean', None, None, 'true,false'),
            ('social_features', 'true', 'Enable social features', 'boolean', None, None, 'true,false'),
            ('review_moderation', 'true', 'Require review moderation', 'boolean', None, None, 'true,false'),
            ('barcode_scanning', 'false', 'Enable barcode scanning support', 'boolean', None, None, 'true,false'),
            ('multi_location_support', 'false', 'Enable multi-location support', 'boolean', None, None, 'true,false')
        ]
        
        for setting in enhanced_settings:
            cursor.execute('''
            INSERT OR IGNORE INTO library_settings 
            (setting_name, setting_value, description, setting_type, min_value, max_value, allowed_values)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', setting)
        
        # Create indexes for better performance
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)',
            'CREATE INDEX IF NOT EXISTS idx_books_category ON books(category)',
            'CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)',
            'CREATE INDEX IF NOT EXISTS idx_loans_user ON book_loans(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_loans_status ON book_loans(status)',
            'CREATE INDEX IF NOT EXISTS idx_loans_due_date ON book_loans(due_date)',
            'CREATE INDEX IF NOT EXISTS idx_reservations_user ON book_reservations(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_reviews_book ON book_reviews(book_id)',
            'CREATE INDEX IF NOT EXISTS idx_reviews_user ON book_reviews(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_payments_source_type ON payments(source_type)',
            'CREATE INDEX IF NOT EXISTS idx_payments_reference_id ON payments(reference_id)'
        ]
        
        for index in indexes:
            cursor.execute(index)
        
        conn.commit()
        conn.close()
        print("✅ " + get_text("library.db_init_success"))
        logging.info("Enhanced library database initialized successfully!")
        return True
        
    except sqlite3.Error as e:
        print("❌ " + get_text("library.db_init_error", error=str(e)))
        logging.error(f"An error occurred while initializing the enhanced library database: {e}")
        return False


def verify_database_structure():
    """Verify that all required tables and columns exist"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Check library_settings table structure
        cursor.execute("PRAGMA table_info(library_settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        required_columns = ['setting_name', 'setting_value', 'description', 'setting_type', 'min_value', 'max_value', 'allowed_values']
        
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            print(get_text("library.db_structure_error", columns=str(missing_columns)))
            return False
        
        print("✅ " + get_text("library.db_structure_verified"))
        return True
        
    except sqlite3.Error as e:
        print(get_text("common.error") + f": {e}")
        return False
    finally:
        conn.close()


def repair_database():
    """Repair database structure if needed"""
    print("🔧 " + get_text("library.db_repair_checking"))
    
    if not verify_database_structure():
        print("🔄 " + get_text("library.db_repair_needed"))
        return init_library_db()
    else:
        print("✅ " + get_text("library.db_structure_correct"))
        return True


def log_audit_event(user_id: str, action: str, table_affected: str = None, 
                   record_id: str = None, old_values: str = None, 
                   new_values: str = None, ip_address: str = None, success: bool = True):
    """Log audit events for security and compliance"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO audit_log (user_id, action, table_name, record_id,
                              old_values, new_values, timestamp, ip_address, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, action, table_affected, record_id,
            old_values, new_values, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ip_address, str(success) if success is not True else None
        ))
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Error logging audit event: {e}")


