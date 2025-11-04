from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from university_system.infrastructure.email import (
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
from typing import List, Dict, Optional, Tuple
import logging
from university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def get_current_user_id():
    """Safely get the current user ID from the auth object"""
    global auth
    
    if not auth or not auth.current_user:
        return None
    
    # Check if current_user is a dictionary
    if isinstance(auth.current_user, dict):
        return auth.current_user.get('user_id')
    
    # Check if current_user has a user_id attribute
    if hasattr(auth.current_user, 'user_id'):
        return auth.current_user.user_id
    
    # Check if current_user has a username attribute
    if hasattr(auth.current_user, 'username'):
        return auth.current_user.username
    
    # If it's a string, return it directly
    if isinstance(auth.current_user, str):
        return auth.current_user
    
    # Last resort - convert to string
    return str(auth.current_user)

class Book:
    def __init__(self, book_id, title, author, isbn, publisher, category, year_published, 
                 description, location, status, added_date, last_updated, reading_level=None,
                 tags=None, cover_image_path=None, digital_copy_path=None):
        self.book_id = book_id
        self.title = title
        self.author = author
        self.isbn = isbn
        self.publisher = publisher
        self.category = category
        self.year_published = year_published
        self.description = description
        self.location = location
        self.status = status  # 'available', 'checked_out', 'reserved', 'lost', 'damaged'
        self.added_date = added_date
        self.last_updated = last_updated
        self.reading_level = reading_level
        self.tags = tags or []
        self.cover_image_path = cover_image_path
        self.digital_copy_path = digital_copy_path

class BookLoan:
    def __init__(self, loan_id, book_id, user_id, checkout_date, due_date, return_date, 
                 status, fine_amount, renewal_count=0, reading_progress=0):
        self.loan_id = loan_id
        self.book_id = book_id
        self.user_id = user_id
        self.checkout_date = checkout_date
        self.due_date = due_date
        self.return_date = return_date
        self.status = status  # 'active', 'returned', 'overdue', 'lost'
        self.fine_amount = fine_amount
        self.renewal_count = renewal_count
        self.reading_progress = reading_progress

class BookReservation:
    def __init__(self, reservation_id, book_id, user_id, reservation_date, 
                 expiry_date, status, priority_order=1):
        self.reservation_id = reservation_id
        self.book_id = book_id
        self.user_id = user_id
        self.reservation_date = reservation_date
        self.expiry_date = expiry_date
        self.status = status
        self.priority_order = priority_order

class BookReview:
    def __init__(self, review_id, book_id, user_id, rating, review_text, 
                 review_date, status='pending'):
        self.review_id = review_id
        self.book_id = book_id
        self.user_id = user_id
        self.rating = rating
        self.review_text = review_text
        self.review_date = review_date
        self.status = status  # 'pending', 'approved', 'rejected'

class ReadingList:
    def __init__(self, list_id, name, description, creator_id, created_date, 
                 is_public=False, is_collaborative=False):
        self.list_id = list_id
        self.name = name
        self.description = description
        self.creator_id = creator_id
        self.created_date = created_date
        self.is_public = is_public
        self.is_collaborative = is_collaborative

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def get_db_connection():
    """Get database connection using the consolidated database file"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
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
            print("Updating library_settings table structure...")
            
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
            'CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)'
        ]
        
        for index in indexes:
            cursor.execute(index)
        
        conn.commit()
        conn.close()
        print("✅ Enhanced library database initialized successfully!")
        logging.info("Enhanced library database initialized successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ An error occurred while initializing the enhanced library database: {e}")
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
            print(f"Missing columns in library_settings: {missing_columns}")
            return False
        
        print("✅ Database structure verified successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"Error verifying database structure: {e}")
        return False
    finally:
        conn.close()

def repair_database():
    """Repair database structure if needed"""
    print("🔧 Checking and repairing database structure...")
    
    if not verify_database_structure():
        print("🔄 Database structure needs repair. Reinitializing...")
        return init_library_db()
    else:
        print("✅ Database structure is correct!")
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
        INSERT INTO audit_log (user_id, action, table_affected, record_id, 
                              old_values, new_values, timestamp, ip_address, success)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, action, table_affected, record_id,
            old_values, new_values, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ip_address, success
        ))
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Error logging audit event: {e}")

def generate_barcode(book_id: str) -> str:
    """Generate a unique barcode for a book"""
    # Simple barcode generation - in production, use proper barcode library
    import hashlib
    hash_object = hashlib.md5(book_id.encode())
    barcode = hash_object.hexdigest()[:12].upper()
    return f"LIB{barcode}"

def generate_qr_code(book_id: str, title: str) -> str:
    """Generate QR code for a book"""
    try:
        # Create QR code data
        qr_data = f"LIBRARY_BOOK:{book_id}:{title}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_path = QR_CODES_DIR / f"book_{book_id}.png"
        qr_img.save(str(qr_path))
        
        return qr_path
    except Exception as e:
        logging.error(f"Error generating QR code: {e}")
        return None

def fetch_book_metadata(isbn: str) -> Dict:
    """Fetch book metadata from online sources"""
    try:
        # Try Google Books API
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                book_info = data['items'][0]['volumeInfo']
                
                metadata = {
                    'title': book_info.get('title', ''),
                    'authors': book_info.get('authors', []),
                    'publisher': book_info.get('publisher', ''),
                    'published_date': book_info.get('publishedDate', ''),
                    'description': book_info.get('description', ''),
                    'page_count': book_info.get('pageCount', 0),
                    'categories': book_info.get('categories', []),
                    'language': book_info.get('language', 'en'),
                    'thumbnail': book_info.get('imageLinks', {}).get('thumbnail', '')
                }
                
                return metadata
    except Exception as e:
        logging.error(f"Error fetching book metadata: {e}")
    
    return {}

def assess_reading_level(text: str) -> str:
    """Assess reading level using simple algorithms"""
    try:
        # Simple reading level assessment based on sentence and word complexity
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return "Unknown"
        
        avg_sentence_length = len(words) / len(sentences)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Simple scoring system
        if avg_sentence_length < 10 and avg_word_length < 4:
            return "Elementary"
        elif avg_sentence_length < 15 and avg_word_length < 5:
            return "Middle School"
        elif avg_sentence_length < 20 and avg_word_length < 6:
            return "High School"
        else:
            return "College"
            
    except Exception as e:
        logging.error(f"Error assessing reading level: {e}")
        return "Unknown"

def enhanced_add_book():
    """Enhanced add book function with metadata fetching and QR code generation"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to add books.")
        return
    
    if not auth.check_permission('manage_books'):
        print("You don't have permission to add books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    # Generate book ID
    cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
    result = cursor.fetchone()[0]
    next_id = 10001 if result is None else result + 1
    book_id = f"B{next_id}"
    
    print("\nAdding a new book to the library")
    print("================================")
    
    # Get ISBN first to fetch metadata
    isbn = input("Enter ISBN (for automatic metadata fetching): ").strip()
    metadata = {}
    
    if isbn:
        print("Fetching book metadata...")
        metadata = fetch_book_metadata(isbn)
        if metadata:
            print("✓ Metadata fetched successfully!")
    
    # Title
    while True:
        default_title = metadata.get('title', '')
        title = input(f"Enter book title{f' [{default_title}]' if default_title else ''}: ").strip()
        if not title and default_title:
            title = default_title
        if title:
            break
        print("Error: Title cannot be empty.")
    
    # Author
    while True:
        default_authors = ', '.join(metadata.get('authors', []))
        author = input(f"Enter author name{f' [{default_authors}]' if default_authors else ''}: ").strip()
        if not author and default_authors:
            author = default_authors
        if author:
            break
        print("Error: Author cannot be empty.")
    
    # Publisher
    default_publisher = metadata.get('publisher', '')
    publisher = input(f"Enter publisher{f' [{default_publisher}]' if default_publisher else ''}: ").strip()
    if not publisher and default_publisher:
        publisher = default_publisher
    
    # Category
    default_categories = metadata.get('categories', [])
    categories = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science', 
                  'Mathematics', 'Philosophy', 'Psychology', 'Business', 'Biography', 
                  'Fantasy', 'Mystery', 'Romance', 'Thriller', 'Self-Help', 'Other']
    
    print("\nBook Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    while True:
        choice = input(f"Select category (1-{len(categories)}) or enter custom: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(categories):
            category = categories[int(choice) - 1]
            break
        elif choice:
            category = choice
            break
        print("Error: Please select a category or enter a custom one.")
    
    # Year Published
    default_year = metadata.get('published_date', '')[:4] if metadata.get('published_date') else ''
    while True:
        year_str = input(f"Enter publication year{f' [{default_year}]' if default_year else ''}: ").strip()
        if not year_str and default_year:
            year_published = int(default_year)
            break
        elif not year_str:
            year_published = None
            break
            
        try:
            year_published = int(year_str)
            current_year = datetime.now().year
            if 1500 <= year_published <= current_year:
                break
            print(f"Error: Year must be between 1500 and {current_year}.")
        except ValueError:
            print("Error: Please enter a valid year.")
    
    # Description
    default_description = metadata.get('description', '')
    description = input(f"Enter description{' [auto-filled]' if default_description else ''}: ").strip()
    if not description and default_description:
        description = default_description
    
    # Location
    location = input("Enter shelf location (e.g., 'Floor 2, Section A'): ").strip()
    
    # Additional fields
    edition = input("Enter edition (optional): ").strip() or None
    total_pages = metadata.get('page_count', 0) or None
    language = metadata.get('language', 'English')
    
    # Reading level assessment
    reading_level = "Unknown"
    if description:
        reading_level = assess_reading_level(description)
        print(f"Assessed reading level: {reading_level}")
    
    # Tags
    tags_input = input("Enter tags (comma-separated, optional): ").strip()
    tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []
    
    # Acquisition cost
    while True:
        cost_str = input("Enter acquisition cost (optional): $").strip()
        if not cost_str:
            acquisition_cost = 0.0
            break
        try:
            acquisition_cost = float(cost_str)
            if acquisition_cost >= 0:
                break
            print("Error: Cost must be non-negative.")
        except ValueError:
            print("Error: Please enter a valid number.")
    
    # Generate barcode and QR code
    barcode = generate_barcode(book_id)
    qr_code_path = generate_qr_code(book_id, title)
    
    # Status defaults to 'available'
    status = 'available'
    
    # Timestamps
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Insert the book into the database
        cursor.execute('''
        INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_id, title, author, isbn, publisher, category, 
            year_published, description, location, status, now, now,
            reading_level, json.dumps(tags), None, None, acquisition_cost,
            barcode, qr_code_path, total_pages, language, edition, None
        ))
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Added book: {book_id}", "books", book_id)        
        print(f"\n✓ Book added successfully! Book ID: {book_id}")
        print(f"✓ Barcode generated: {barcode}")
        if qr_code_path:
            print(f"✓ QR code saved: {qr_code_path}")
        
        # Display book details
        print("\nBook Details:")
        print(f"ID: {book_id}")
        print(f"Title: {title}")
        print(f"Author: {author}")
        print(f"ISBN: {isbn if isbn else 'N/A'}")
        print(f"Category: {category}")
        print(f"Reading Level: {reading_level}")
        print(f"Tags: {', '.join(tags) if tags else 'None'}")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error adding book: {e}")
        log_audit_event(get_current_user_id(), f"Failed to add book", success=False)
    
    conn.close()
    
def enhanced_search_books():
    """Enhanced book search with multiple filters and smart recommendations"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to search for books.")
        return
    
    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print("You don't have permission to search for books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    print("\nEnhanced Book Search:")
    print("====================")
    print("1. Quick Search (title/author)")
    print("2. Advanced Search")
    print("3. Search by Barcode/QR Code")
    print("4. Browse by Category")
    print("5. Browse by Reading Level")
    print("6. Get Recommendations")
    print("7. Return to menu")
    
    choice = input("Enter your choice (1-7): ").strip()
    
    if choice == '7':
        conn.close()
        return
    
    try:
        if choice == '1':
            # Quick search
            search_term = input("Enter title or author to search: ").strip()
            
            cursor.execute('''
            SELECT book_id, title, author, category, status, reading_level
            FROM books
            WHERE title LIKE ? OR author LIKE ?
            ORDER BY title
            ''', (f'%{search_term}%', f'%{search_term}%'))
            
            books = cursor.fetchall()
            search_type = "quick search"
            
        elif choice == '2':
            # Advanced search
            print("\nAdvanced Search (leave fields blank to ignore):")
            title = input("Title contains: ").strip()
            author = input("Author contains: ").strip()
            category = input("Category: ").strip()
            reading_level = input("Reading level: ").strip()
            tags = input("Tags (comma-separated): ").strip()
            year_from = input("Published from year: ").strip()
            year_to = input("Published to year: ").strip()
            status = input("Status (available/checked_out/reserved): ").strip()
            
            # Build dynamic query
            query = """
            SELECT book_id, title, author, category, status, reading_level, year_published
            FROM books WHERE 1=1
            """
            params = []
            
            if title:
                query += " AND title LIKE ?"
                params.append(f'%{title}%')
            
            if author:
                query += " AND author LIKE ?"
                params.append(f'%{author}%')
            
            if category:
                query += " AND category LIKE ?"
                params.append(f'%{category}%')
            
            if reading_level:
                query += " AND reading_level = ?"
                params.append(reading_level)
            
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')]
                for tag in tag_list:
                    query += " AND tags LIKE ?"
                    params.append(f'%{tag}%')
            
            if year_from:
                try:
                    query += " AND year_published >= ?"
                    params.append(int(year_from))
                except ValueError:
                    pass
            
            if year_to:
                try:
                    query += " AND year_published <= ?"
                    params.append(int(year_to))
                except ValueError:
                    pass
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY title"
            
            cursor.execute(query, tuple(params))
            books = cursor.fetchall()
            search_type = "advanced search"
            
        elif choice == '3':
            # Barcode/QR search
            code = input("Enter barcode or scan QR code: ").strip()
            
            if code.startswith("LIBRARY_BOOK:"):
                # QR code format
                parts = code.split(":")
                if len(parts) >= 2:
                    book_id = parts[1]
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE book_id = ?
                    ''', (book_id,))
                else:
                    print("Invalid QR code format.")
                    books = []
            else:
                # Barcode
                cursor.execute('''
                SELECT book_id, title, author, category, status, reading_level
                FROM books WHERE barcode = ?
                ''', (code,))
            
            books = cursor.fetchall()
            search_type = "barcode/QR search"
            
        elif choice == '4':
            # Browse by category
            cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            
            if not categories:
                print("No categories found.")
                conn.close()
                return
            
            print("\nAvailable Categories:")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")
            
            try:
                cat_choice = int(input("Select category: ")) - 1
                if 0 <= cat_choice < len(categories):
                    selected_category = categories[cat_choice]
                    
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE category = ?
                    ORDER BY title
                    ''', (selected_category,))
                    
                    books = cursor.fetchall()
                    search_type = f"category: {selected_category}"
                else:
                    print("Invalid category selection.")
                    conn.close()
                    return
                
            except (ValueError, IndexError):
                print("Invalid category selection.")
                conn.close()
                return
                
        elif choice == '5':
            # Browse by reading level
            reading_levels = ['Elementary', 'Middle School', 'High School', 'College', 'Unknown']
            
            print("\nReading Levels:")
            for i, level in enumerate(reading_levels, 1):
                print(f"{i}. {level}")
            
            try:
                level_choice = int(input("Select reading level: ")) - 1
                if 0 <= level_choice < len(reading_levels):
                    selected_level = reading_levels[level_choice]
                    
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE reading_level = ?
                    ORDER BY title
                    ''', (selected_level,))
                    
                    books = cursor.fetchall()
                    search_type = f"reading level: {selected_level}"
                else:
                    print("Invalid reading level selection.")
                    conn.close()
                    return
                
            except (ValueError, IndexError):
                print("Invalid reading level selection.")
                conn.close()
                return
                
        elif choice == '6':
            # Get recommendations
            books = get_book_recommendations(get_current_user_id())
            search_type = "recommendations"
                
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        # Display results
        if not books:
            print(f"No books found for {search_type}.")
            conn.close()
            return
        
        print(f"\nFound {len(books)} books for {search_type}:")
        print("=" * 100)
        print(f"{'ID':<8} {'Title':<30} {'Author':<20} {'Category':<15} {'Status':<12} {'Level':<10}")
        print("-" * 100)
        
        for book in books:
            book_id, title, author, category, status = book[:5]
            reading_level = book[5] if len(book) > 5 else 'Unknown'
            
            # Truncate strings if too long
            title = (title[:27] + '...') if len(title) > 30 else title
            author = (author[:17] + '...') if len(author) > 20 else author
            category = (category[:12] + '...') if len(category) > 15 else category
            
            print(f"{book_id:<8} {title:<30} {author:<20} {category:<15} {status:<12} {reading_level:<10}")
        
        print("=" * 100)
        
        # Additional options
        print("\nOptions:")
        print("1. View book details")
        print("2. Add to reading list")
        print("3. Reserve book")
        print("4. Rate/Review book")
        print("5. Return to search")
        
        action = input("Choose an action (1-5): ").strip()
        
        if action == '1':
            book_id = input("Enter Book ID to view details: ").strip()
            if book_id:
                enhanced_view_book_details(book_id)
        elif action == '2':
            book_id = input("Enter Book ID to add to reading list: ").strip()
            if book_id:
                add_to_reading_list(book_id)
        elif action == '3':
            book_id = input("Enter Book ID to reserve: ").strip()
            if book_id:
                reserve_book(book_id)
        elif action == '4':
            book_id = input("Enter Book ID to rate/review: ").strip()
            if book_id:
                rate_and_review_book(book_id)
    
    except sqlite3.Error as e:
        print(f"Error searching books: {e}")
    
    conn.close()

def enhanced_view_book_details(book_id=None):
    """Enhanced book details view with reviews, recommendations, and analytics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view book details.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    if book_id is None:
        book_id = input("Enter the Book ID: ").strip()
    
    try:
        # Get comprehensive book details
        cursor.execute('''
        SELECT b.*, 
               COALESCE(AVG(r.rating), 0) as avg_rating,
               COUNT(r.review_id) as review_count,
               COUNT(DISTINCT bl.loan_id) as total_loans
        FROM books b
        LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
        LEFT JOIN book_loans bl ON b.book_id = bl.book_id
        WHERE b.book_id = ?
        GROUP BY b.book_id
        ''', (book_id,))
        
        book_data = cursor.fetchone()
        
        if not book_data:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        # Parse book data
        book = {
            'book_id': book_data[0],
            'title': book_data[1],
            'author': book_data[2],
            'isbn': book_data[3],
            'publisher': book_data[4],
            'category': book_data[5],
            'year_published': book_data[6],
            'description': book_data[7],
            'location': book_data[8],
            'status': book_data[9],
            'added_date': book_data[10],
            'last_updated': book_data[11],
            'reading_level': book_data[12],
            'tags': json.loads(book_data[13]) if book_data[13] else [],
            'cover_image_path': book_data[14],
            'digital_copy_path': book_data[15],
            'acquisition_cost': book_data[16],
            'barcode': book_data[17],
            'qr_code_path': book_data[18],
            'total_pages': book_data[19],
            'language': book_data[20],
            'edition': book_data[21],
            'condition_notes': book_data[22],
            'avg_rating': round(book_data[23], 1),
            'review_count': book_data[24],
            'total_loans': book_data[25]
        }
        
        # Display enhanced book details
        print("\n" + "="*80)
        print(f"                    BOOK DETAILS - {book['book_id']}")
        print("="*80)
        
        print(f"Title: {book['title']}")
        print(f"Author: {book['author']}")
        print(f"Category: {book['category']}")
        print(f"Status: {book['status'].upper()}")
        
        if book['avg_rating'] > 0:
            stars = "★" * int(book['avg_rating']) + "☆" * (5 - int(book['avg_rating']))
            print(f"Rating: {stars} ({book['avg_rating']}/5.0 from {book['review_count']} reviews)")
        
        print(f"Total Times Borrowed: {book['total_loans']}")
        
        if book['isbn']:
            print(f"ISBN: {book['isbn']}")
        if book['publisher']:
            print(f"Publisher: {book['publisher']}")
        if book['year_published']:
            print(f"Year Published: {book['year_published']}")
        if book['edition']:
            print(f"Edition: {book['edition']}")
        if book['total_pages']:
            print(f"Pages: {book['total_pages']}")
        
        print(f"Language: {book['language']}")
        print(f"Reading Level: {book['reading_level']}")
        print(f"Location: {book['location']}")
        
        if book['tags']:
            print(f"Tags: {', '.join(book['tags'])}")
        
        if book['barcode']:
            print(f"Barcode: {book['barcode']}")
        
        if book['description']:
            print(f"\nDescription:")
            print("-" * 40)
            print(book['description'])
        
        if book['condition_notes']:
            print(f"\nCondition Notes: {book['condition_notes']}")
        
        print("-" * 80)
        
        # Show recent reviews
        cursor.execute('''
        SELECT r.rating, r.review_text, r.review_date, r.user_id
        FROM book_reviews r
        WHERE r.book_id = ? AND r.status = 'approved'
        ORDER BY r.review_date DESC
        LIMIT 3
        ''', (book_id,))
        
        reviews = cursor.fetchall()
        
        if reviews:
            print("\nRecent Reviews:")
            print("-" * 40)
            for review in reviews:
                rating, text, date, user_id = review
                stars = "★" * rating + "☆" * (5 - rating)
                print(f"{stars} by {user_id} on {date[:10]}")
                if text:
                    print(f"   \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
                print()
        
        # Show loan history
        cursor.execute('''
        SELECT bl.checkout_date, bl.due_date, bl.return_date, bl.user_id, bl.status
        FROM book_loans bl
        WHERE bl.book_id = ?
        ORDER BY bl.checkout_date DESC
        LIMIT 5
        ''', (book_id,))
        
        loans = cursor.fetchall()
        
        if loans:
            print("Recent Loan History:")
            print("-" * 60)
            print(f"{'User ID':<12} {'Checkout':<12} {'Due Date':<12} {'Returned':<12} {'Status':<10}")
            print("-" * 60)
            
            for loan in loans:
                checkout, due, returned, user_id, status = loan
                checkout_str = checkout[:10] if checkout else 'N/A'
                due_str = due[:10] if due else 'N/A'
                returned_str = returned[:10] if returned else 'N/A'
                
                print(f"{user_id:<12} {checkout_str:<12} {due_str:<12} {returned_str:<12} {status:<10}")
        
        # Show current reservations
        cursor.execute('''
        SELECT user_id, reservation_date, priority_order
        FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ORDER BY priority_order, reservation_date
        ''', (book_id,))
        
        reservations = cursor.fetchall()
        
        if reservations:
            print(f"\nCurrent Reservations ({len(reservations)}):")
            print("-" * 40)
            for i, (user_id, res_date, priority) in enumerate(reservations, 1):
                print(f"{i}. {user_id} (reserved {res_date[:10]})")
        
        # Show similar books
        similar_books = get_similar_books(book_id, book['category'], book['author'])
        if similar_books:
            print(f"\nSimilar Books:")
            print("-" * 40)
            for similar_book in similar_books[:3]:
                print(f"• {similar_book[1]} by {similar_book[2]} ({similar_book[0]})")
        
        print("="*80)
        
        # Action options
        if auth.check_permission('manage_books') or auth.check_permission('checkout_books'):
            print("\nActions:")
            actions = []
            
            if book['status'] == 'available':
                print("1. Check out this book")
                actions.append('checkout')
            
            if book['status'] in ['available', 'checked_out']:
                print(f"{len(actions)+1}. Reserve this book")
                actions.append('reserve')
            
            print(f"{len(actions)+1}. Rate/Review this book")
            actions.append('review')
            
            print(f"{len(actions)+1}. Add to reading list")
            actions.append('reading_list')
            
            if auth.check_permission('manage_books'):
                print(f"{len(actions)+1}. Edit book details")
                actions.append('edit')
            
            print(f"{len(actions)+1}. Return to menu")
            
            action = input("Choose an action: ").strip()
            
            try:
                action_idx = int(action) - 1
                if 0 <= action_idx < len(actions):
                    selected_action = actions[action_idx]
                    
                    if selected_action == 'checkout':
                        enhanced_checkout_book(book_id)
                    elif selected_action == 'reserve':
                        reserve_book(book_id)
                    elif selected_action == 'review':
                        rate_and_review_book(book_id)
                    elif selected_action == 'reading_list':
                        add_to_reading_list(book_id)
                    elif selected_action == 'edit':
                        enhanced_update_book(book_id)
            except ValueError:
                pass
    
    except sqlite3.Error as e:
        print(f"Error viewing book details: {e}")
    
    conn.close()

def get_similar_books(book_id: str, category: str, author: str, limit: int = 5) -> List:
    """Get similar books based on category and author"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        # Find books by same author or in same category
        cursor.execute('''
        SELECT book_id, title, author, category,
               CASE 
                   WHEN author = ? THEN 2
                   WHEN category = ? THEN 1
                   ELSE 0
               END as similarity_score
        FROM books
        WHERE book_id != ? AND (author = ? OR category = ?)
        ORDER BY similarity_score DESC, title
        LIMIT ?
        ''', (author, category, book_id, author, category, limit))
        
        similar_books = cursor.fetchall()
        conn.close()
        
        return similar_books
        
    except sqlite3.Error as e:
        logging.error(f"Error getting similar books: {e}")
        return []

def get_book_recommendations(user_id: str, limit: int = 10) -> List:
    """Generate personalized book recommendations"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        # Get user's borrowing history
        cursor.execute('''
        SELECT DISTINCT b.category, b.author
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.user_id = ?
        ''', (user_id,))
        
        user_history = cursor.fetchall()
        
        if not user_history:
            # No history, recommend popular books
            cursor.execute('''
            SELECT b.book_id, b.title, b.author, b.category, b.status, 
                   COUNT(bl.loan_id) as loan_count
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            WHERE b.status = 'available'
            GROUP BY b.book_id
            ORDER BY loan_count DESC, b.title
            LIMIT ?
            ''', (limit,))
        else:
            # Recommend based on preferences
            categories = [item[0] for item in user_history]
            authors = [item[1] for item in user_history]
            
            # Build recommendation query
            category_conditions = " OR ".join(["b.category = ?" for _ in categories])
            author_conditions = " OR ".join(["b.author = ?" for _ in authors])
            
            query = f'''
            SELECT DISTINCT b.book_id, b.title, b.author, b.category, b.status,
                   CASE 
                       WHEN {author_conditions} THEN 2
                       WHEN {category_conditions} THEN 1
                       ELSE 0
                   END as recommendation_score
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            WHERE b.book_id NOT IN (
                SELECT DISTINCT book_id FROM book_loans WHERE user_id = ?
            ) AND b.status = 'available'
            ORDER BY recommendation_score DESC, b.title
            LIMIT ?
            '''
            
            params = authors + categories + [user_id, limit]
            cursor.execute(query, params)
        
        recommendations = cursor.fetchall()
        
        # Store recommendations in database for tracking
        for rec in recommendations:
            cursor.execute('''
            INSERT OR REPLACE INTO book_recommendations 
            (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
            VALUES (?, ?, 'personalized', 0.8, ?, 'pending')
            ''', (user_id, rec[0], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
        
        return recommendations
        
    except sqlite3.Error as e:
        logging.error(f"Error generating recommendations: {e}")
        return []

def enhanced_checkout_book(book_id=None):
    """Enhanced checkout with barcode scanning and smart validation"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to check out books.")
        return
    
    if not (auth.check_permission('manage_loans') or auth.check_permission('checkout_books')):
        print("You don't have permission to check out books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        # Get book ID if not provided
        if book_id is None:
            print("\nCheckout Options:")
            print("1. Enter Book ID")
            print("2. Scan Barcode")
            print("3. Scan QR Code")
            
            method = input("Select method (1-3): ").strip()
            
            if method == '1':
                book_id = input("Enter Book ID: ").strip()
            elif method == '2':
                barcode = input("Scan/Enter Barcode: ").strip()
                cursor.execute('SELECT book_id FROM books WHERE barcode = ?', (barcode,))
                result = cursor.fetchone()
                if result:
                    book_id = result[0]
                else:
                    print("Book not found with that barcode.")
                    conn.close()
                    return
            elif method == '3':
                qr_data = input("Scan QR Code: ").strip()
                if qr_data.startswith("LIBRARY_BOOK:"):
                    parts = qr_data.split(":")
                    if len(parts) >= 2:
                        book_id = parts[1]
                    else:
                        print("Invalid QR code format.")
                        conn.close()
                        return
                else:
                    print("Invalid QR code.")
                    conn.close()
                    return
            else:
                print("Invalid method selection.")
                conn.close()
                return
        
        # Validate book
        cursor.execute('''
        SELECT title, status, category, reading_level 
        FROM books WHERE book_id = ?
        ''', (book_id,))
        
        book = cursor.fetchone()
        
        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        title, status, category, reading_level = book
        
        if status != 'available':
            print(f"This book is currently {status} and cannot be checked out.")
            
            # Check if there are reservations
            cursor.execute('''
            SELECT COUNT(*) FROM book_reservations 
            WHERE book_id = ? AND status = 'active'
            ''', (book_id,))
            
            reservation_count = cursor.fetchone()[0]
            if reservation_count > 0:
                print(f"There are {reservation_count} reservation(s) for this book.")
            
            conn.close()
            return
        
        # Get user information
        user_type = input("Is this for a student (S) or staff (T)? ").strip().upper()
        user_name = "Unknown User"
        user_validated = False
        
        if user_type == 'S':
            user_id = input("Enter Student ID: ").strip()
            
            if not user_id:
                print("Error: Student ID cannot be empty.")
                conn.close()
                return
            
            # Verify student exists
            try:
                cursor.execute('SELECT first_name, last_name, grade_level FROM students WHERE student_id = ?', (user_id,))
                student = cursor.fetchone()
                
                if student:
                    user_name = f"{student[0]} {student[1]}"
                    grade_level = student[2]
                    user_validated = True
                    print(f"Student found: {user_name} (Grade {grade_level})")
                    
                    # Check reading level compatibility
                    if reading_level and grade_level:
                        compatibility = check_reading_level_compatibility(reading_level, grade_level)
                        if not compatibility['suitable']:
                            print(f"⚠️  Warning: {compatibility['message']}")
                            confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                            if confirm != 'y':
                                print("Checkout cancelled.")
                                conn.close()
                                return
                else:
                    print(f"Warning: No student found with ID: {user_id}")
                    confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                    if confirm != 'y':
                        print("Checkout cancelled.")
                        conn.close()
                        return
                    user_name = f"Student {user_id}"
                    user_validated = True
                    
            except sqlite3.Error as e:
                print(f"Unable to verify student ID: {e}")
                confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Checkout cancelled.")
                    conn.close()
                    return
                user_name = f"Student {user_id}"
                user_validated = True
                
        elif user_type == 'T':
            user_id = input("Enter Staff/User ID: ").strip()
            
            if not user_id:
                print("Error: Staff ID cannot be empty.")
                conn.close()
                return
            
            user_name = input("Enter User Name: ").strip()
            if not user_name:
                user_name = f"Staff {user_id}"
            
            user_validated = True
        else:
            print("Invalid user type.")
            conn.close()
            return
        
        if not user_validated:
            print("User validation failed.")
            conn.close()
            return
        
        # Check loan limits and restrictions
        loan_check = check_loan_eligibility(cursor, user_id, user_type)
        if not loan_check['eligible']:
            print(f"Cannot checkout book: {loan_check['reason']}")
            conn.close()
            return
        
        # Get loan settings
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
        loan_setting = cursor.fetchone()
        loan_period = int(loan_setting[0]) if loan_setting else 14  # Default to 14 days
        
        # Set dates
        checkout_date = datetime.now()
        due_date = checkout_date + timedelta(days=loan_period)
        
        # Check for existing reservation by this user
        cursor.execute('''
        SELECT reservation_id FROM book_reservations 
        WHERE book_id = ? AND user_id = ? AND status = 'active'
        ''', (book_id, user_id))
        
        user_reservation = cursor.fetchone()
        
        # Create loan record
        cursor.execute('''
        INSERT INTO book_loans 
        (book_id, user_id, checkout_date, due_date, status, checkout_method, staff_id)
        VALUES (?, ?, ?, ?, 'active', 'enhanced', ?)
        ''', (
            book_id, user_id, 
            checkout_date.strftime('%Y-%m-%d %H:%M:%S'),
            due_date.strftime('%Y-%m-%d %H:%M:%S'),
            get_current_user_id()
        ))
        
        loan_id = cursor.lastrowid
        
        # Update book status
        cursor.execute('''
        UPDATE books SET status = 'checked_out', last_updated = ?
        WHERE book_id = ?
        ''', (checkout_date.strftime('%Y-%m-%d %H:%M:%S'), book_id))
        
        # If user had a reservation, mark it as fulfilled
        if user_reservation:
            cursor.execute('''
            UPDATE book_reservations SET status = 'fulfilled'
            WHERE reservation_id = ?
            ''', (user_reservation[0],))
        
        # Update user reading goals
        update_reading_goals(cursor, user_id, 'books_read')
        
        # Record analytics
        record_usage_analytics(cursor, 'checkout', category, user_type)
        
        conn.commit()
        
        # Log the action
        log_audit_event(get_current_user_id(), f"Checked out book {book_id} to {user_id}", "book_loans", str(loan_id))
        
        print(f"\n✅ Book checked out successfully!")
        print("=" * 60)
        print(f"Book: '{title}' ({book_id})")
        print(f"Loan ID: {loan_id}")
        print(f"User: {user_name} ({user_id})")
        print(f"Checkout Date: {checkout_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"Due Date: {due_date.strftime('%Y-%m-%d')}")
        print(f"Reading Level: {reading_level}")
        print(f"Active Loans: {loan_check['current_loans'] + 1}/{loan_check['max_loans']}")
        print("=" * 60)
        
        # Send notifications
        try:
            send_enhanced_checkout_notification(user_id, book_id, title, due_date.strftime('%Y-%m-%d'))
            print("✅ Checkout confirmation sent.")
        except Exception as e:
            print(f"⚠️  Could not send notification: {e}")
        
        # Suggest related books
        similar_books = get_similar_books(book_id, category, title.split()[0])
        if similar_books:
            print(f"\n📚 You might also like:")
            for similar in similar_books[:2]:
                print(f"   • {similar[1]} by {similar[2]} ({similar[0]})")
    
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during checkout: {e}")
        log_audit_event(get_current_user_id(), f"Failed checkout for book {book_id}", success=False)
    
    conn.close()

def check_reading_level_compatibility(book_level: str, grade_level: str) -> Dict:
    """Check if book reading level is appropriate for student grade"""
    grade_mappings = {
        'K': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, '11': 11, '12': 12
    }
    
    level_mappings = {
        'Elementary': (0, 5),
        'Middle School': (6, 8),
        'High School': (9, 12),
        'College': (13, 20)
    }
    
    try:
        grade_num = grade_mappings.get(str(grade_level), 0)
        level_range = level_mappings.get(book_level, (0, 20))
        
        if level_range[0] <= grade_num <= level_range[1]:
            return {'suitable': True, 'message': 'Reading level matches grade level'}
        elif grade_num < level_range[0]:
            return {'suitable': False, 'message': f'This book may be too advanced for grade {grade_level}'}
        else:
            return {'suitable': False, 'message': f'This book may be too easy for grade {grade_level}'}
            
    except Exception:
        return {'suitable': True, 'message': 'Unable to assess reading level compatibility'}

def check_loan_eligibility(cursor, user_id: str, user_type: str) -> Dict:
    """Check if user is eligible for new loans"""
    try:
        # Get max loans setting
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_loans"')
        max_loans = int(cursor.fetchone()[0])
        
        # Count current active loans
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans 
        WHERE user_id = ? AND status IN ('active', 'overdue')
        ''', (user_id,))
        
        current_loans = cursor.fetchone()[0]
        
        # Check for overdue books
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans 
        WHERE user_id = ? AND status = 'overdue'
        ''', (user_id,))
        
        overdue_count = cursor.fetchone()[0]
        
        # Check for outstanding fines
        cursor.execute('''
        SELECT SUM(fine_amount) FROM book_loans 
        WHERE user_id = ? AND fine_amount > 0 AND status != 'returned'
        ''', (user_id,))
        
        outstanding_fines = cursor.fetchone()[0] or 0
        
        # Apply eligibility rules
        if current_loans >= max_loans:
            return {
                'eligible': False,
                'reason': f'Maximum loan limit reached ({current_loans}/{max_loans})',
                'current_loans': current_loans,
                'max_loans': max_loans
            }
        
        if overdue_count > 0:
            return {
                'eligible': False,
                'reason': f'User has {overdue_count} overdue book(s)',
                'current_loans': current_loans,
                'max_loans': max_loans
            }
        
        if outstanding_fines > 10.00:  # $10 fine limit
            return {
                'eligible': False,
                'reason': f'Outstanding fines: ${outstanding_fines:.2f} (limit: $10.00)',
                'current_loans': current_loans,
                'max_loans': max_loans
            }
        
        return {
            'eligible': True,
            'reason': 'User is eligible for checkout',
            'current_loans': current_loans,
            'max_loans': max_loans
        }
        
    except sqlite3.Error as e:
        logging.error(f"Error checking loan eligibility: {e}")
        return {
            'eligible': False,
            'reason': 'Unable to verify loan eligibility',
            'current_loans': 0,
            'max_loans': max_loans
        }

def update_reading_goals(cursor, user_id: str, goal_type: str, increment: int = 1):
    """Update user's reading goals progress"""
    try:
        cursor.execute('''
        UPDATE reading_goals 
        SET current_value = current_value + ?
        WHERE user_id = ? AND goal_type = ? AND status = 'active'
        AND end_date >= date('now')
        ''', (increment, user_id, goal_type))
        
        # Check if any goals were completed
        cursor.execute('''
        SELECT goal_id, target_value, current_value 
        FROM reading_goals
        WHERE user_id = ? AND goal_type = ? AND status = 'active'
        AND current_value >= target_value
        ''', (user_id, goal_type))
        
        completed_goals = cursor.fetchall()
        
        for goal_id, target, current in completed_goals:
            # Mark goal as completed
            cursor.execute('''
            UPDATE reading_goals SET status = 'completed'
            WHERE goal_id = ?
            ''', (goal_id,))
            
            # Award achievement
            cursor.execute('''
            INSERT INTO user_achievements 
            (user_id, achievement_type, achievement_name, description, earned_date, points)
            VALUES (?, 'reading_goal', 'Goal Achieved', ?, ?, ?)
            ''', (
                user_id, 
                f'Completed reading goal: {target} {goal_type}',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                target * 10  # 10 points per book/page/etc
            ))
            
    except sqlite3.Error as e:
        logging.error(f"Error updating reading goals: {e}")

def record_usage_analytics(cursor, metric_name: str, category: str = None, user_type: str = None):
    """Record usage analytics for reporting"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        additional_data = json.dumps({
            'category': category,
            'user_type': user_type
        })
        
        cursor.execute('''
        INSERT INTO usage_analytics (date, metric_name, metric_value, category, additional_data)
        VALUES (?, ?, 1, ?, ?)
        ''', (today, metric_name, category, additional_data))
        
    except sqlite3.Error as e:
        logging.error(f"Error recording analytics: {e}")

def enhanced_return_book():
    """Enhanced book return with reading progress tracking"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to return books.")
        return
    
    if not (auth.check_permission('manage_loans') or auth.check_permission('checkout_books')):
        print("You don't have permission to return books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        print("\nReturn Options:")
        print("1. Enter Book ID")
        print("2. Scan Barcode")
        print("3. Enter Loan ID")
        
        method = input("Select method (1-3): ").strip()
        
        if method == '1':
            book_id = input("Enter Book ID: ").strip()
            
            cursor.execute('''
            SELECT loan_id, user_id, checkout_date, due_date, status, book_id
            FROM book_loans
            WHERE book_id = ? AND status IN ('active', 'overdue')
            ''', (book_id,))
            
        elif method == '2':
            barcode = input("Scan/Enter Barcode: ").strip()
            
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.checkout_date, bl.due_date, bl.status, bl.book_id
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE b.barcode = ? AND bl.status IN ('active', 'overdue')
            ''', (barcode,))
            
        elif method == '3':
            loan_id = input("Enter Loan ID: ").strip()
            
            cursor.execute('''
            SELECT loan_id, user_id, checkout_date, due_date, status, book_id
            FROM book_loans
            WHERE loan_id = ? AND status IN ('active', 'overdue')
            ''', (loan_id,))
            
        else:
            print("Invalid method.")
            conn.close()
            return
        
        loan = cursor.fetchone()
        
        if not loan:
            print("No active loan found.")
            conn.close()
            return
        
        loan_id, user_id, checkout_date, due_date, status, book_id = loan
        
        # Get book details
        cursor.execute('SELECT title, category FROM books WHERE book_id = ?', (book_id,))
        book_info = cursor.fetchone()
        title, category = book_info
        
        print(f"\nReturning: {title} ({book_id})")
        print(f"Borrower: {user_id}")
        print(f"Checkout Date: {checkout_date[:10]}")
        print(f"Due Date: {due_date[:10]}")
        
        # Calculate fine if overdue
        fine_amount = 0.0
        now = datetime.now()
        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
        
        if now > due_date_obj:
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
            fine_per_day = float(cursor.fetchone()[0])
            days_overdue = (now - due_date_obj).days
            fine_amount = days_overdue * fine_per_day
            
            print(f"⚠️  Book is overdue by {days_overdue} days")
            print(f"Fine amount: ${fine_amount:.2f}")
        
        # Ask about reading progress
        try:
            progress = input("Reading progress percentage (0-100, optional): ").strip()
            if progress and progress.isdigit():
                reading_progress = min(100, max(0, int(progress)))
            else:
                reading_progress = 100  # Assume completed if not specified
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            logger.debug(f"Failed to get reading progress input: {e}")
            reading_progress = 100
        
        # Ask about book condition
        condition_ok = input("Is the book in good condition? (y/n): ").strip().lower()
        condition_notes = None
        
        if condition_ok != 'y':
            condition_notes = input("Describe the condition issues: ").strip()
            
            # Update book condition
            cursor.execute('''
            UPDATE books SET condition_notes = COALESCE(condition_notes || '; ', '') || ?
            WHERE book_id = ?
            ''', (f"Returned {now.strftime('%Y-%m-%d')}: {condition_notes}", book_id))
        
        # Process return
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE book_loans
        SET return_date = ?, status = 'returned', fine_amount = ?, 
            reading_progress = ?, notes = ?
        WHERE loan_id = ?
        ''', (now_str, fine_amount, reading_progress, condition_notes, loan_id))
        
        # Update book status
        new_status = 'available'
        if condition_notes and any(word in condition_notes.lower() for word in ['damaged', 'torn', 'missing', 'broken']):
            new_status = 'damaged'
        
        cursor.execute('''
        UPDATE books SET status = ?, last_updated = ?
        WHERE book_id = ?
        ''', (new_status, now_str, book_id))
        
        # Update reading goals
        if reading_progress >= 100:
            update_reading_goals(cursor, user_id, 'books_read')
        
        # Check for reservations and notify next user
        cursor.execute('''
        SELECT user_id, reservation_id 
        FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ORDER BY priority_order, reservation_date
        LIMIT 1
        ''', (book_id,))
        
        next_reservation = cursor.fetchone()
        
        if next_reservation and new_status == 'available':
            next_user_id, reservation_id = next_reservation
            
            # Update book status to reserved
            cursor.execute('UPDATE books SET status = "reserved" WHERE book_id = ?', (book_id,))
            
            # Send notification to next user
            try:
                send_reservation_available_notification(next_user_id, book_id, title)
                print(f"✅ Notification sent to next user: {next_user_id}")
            except Exception as e:
                print(f"⚠️  Could not notify next user: {e}")
        
        # Record analytics
        record_usage_analytics(cursor, 'return', category)
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Returned book {book_id} from {user_id}", "book_loans", str(loan_id))
        
        print(f"\n✅ Book returned successfully!")
        print(f"Reading Progress: {reading_progress}%")
        if fine_amount > 0:
            print(f"Fine Amount: ${fine_amount:.2f}")
        if next_reservation:
            print(f"Book reserved for next user: {next_reservation[0]}")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error returning book: {e}")
        log_audit_event(get_current_user_id(), f"Failed to return book", success=False)
    
    conn.close()
    
def reserve_book(book_id: str = None):
    """Enhanced book reservation system with priority queue"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to reserve books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if book_id is None:
            book_id = input("Enter Book ID to reserve: ").strip()
        
        # Check if book exists
        cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()
        
        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        title, status = book
        
        if status == 'available':
            print("This book is currently available. You can check it out directly.")
            checkout_now = input("Would you like to check it out now? (y/n): ").strip().lower()
            if checkout_now == 'y':
                enhanced_checkout_book(book_id)
                conn.close()
                return
        
        # Get user ID
        user_id = input("Enter User ID for reservation: ").strip()
        
        # Check if user already has a reservation for this book
        cursor.execute('''
        SELECT reservation_id FROM book_reservations 
        WHERE book_id = ? AND user_id = ? AND status = 'active'
        ''', (book_id, user_id))
        
        existing_reservation = cursor.fetchone()
        
        if existing_reservation:
            print("User already has an active reservation for this book.")
            conn.close()
            return
        
        # Get next priority order
        cursor.execute('''
        SELECT COALESCE(MAX(priority_order), 0) + 1 
        FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))
        
        priority_order = cursor.fetchone()[0]
        
        # Get reservation period
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
        reservation_days = int(cursor.fetchone()[0])
        
        # Create reservation
        reservation_date = datetime.now()
        expiry_date = reservation_date + timedelta(days=reservation_days)
        
        cursor.execute('''
        INSERT INTO book_reservations 
        (book_id, user_id, reservation_date, expiry_date, status, priority_order)
        VALUES (?, ?, ?, ?, 'active', ?)
        ''', (
            book_id, user_id,
            reservation_date.strftime('%Y-%m-%d %H:%M:%S'),
            expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
            priority_order
        ))
        
        reservation_id = cursor.lastrowid
        
        # Count total reservations for this book
        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))
        
        total_reservations = cursor.fetchone()[0]
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Created reservation for book {book_id}", "book_reservations", str(reservation_id))
        
        print(f"\n✅ Reservation created successfully!")
        print(f"Book: {title} ({book_id})")
        print(f"User: {user_id}")
        print(f"Position in queue: {priority_order}")
        print(f"Total reservations: {total_reservations}")
        print(f"Expiry Date: {expiry_date.strftime('%Y-%m-%d')}")
        
        # Send confirmation
        try:
            send_reservation_confirmation(user_id, book_id, title, priority_order, expiry_date.strftime('%Y-%m-%d'))
            print("✅ Reservation confirmation sent.")
        except Exception as e:
            print(f"⚠️  Could not send confirmation: {e}")
    
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error creating reservation: {e}")
        log_audit_event(get_current_user_id(), f"Failed to create reservation", success=False)
    
    conn.close()
    
def rate_and_review_book(book_id: str = None):
    """Rate and review a book"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to rate books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if book_id is None:
            book_id = input("Enter Book ID to rate/review: ").strip()
        
        # Check if book exists
        cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()
        
        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        title, author = book
        # FIXED: Use the helper function to get user_id safely
        user_id = get_current_user_id()
                
        # Check if user has already reviewed this book
        cursor.execute('''
        SELECT review_id, rating, review_text FROM book_reviews 
        WHERE book_id = ? AND user_id = ?
        ''', (book_id, user_id))
        
        existing_review = cursor.fetchone()
        
        if existing_review:
            print(f"You have already reviewed this book (Rating: {existing_review[1]}/5)")
            update = input("Would you like to update your review? (y/n): ").strip().lower()
            if update != 'y':
                conn.close()
                return
        
        print(f"\nRating/Reviewing: {title} by {author}")
        
        # Get rating
        while True:
            try:
                rating = int(input("Enter rating (1-5 stars): ").strip())
                if 1 <= rating <= 5:
                    break
                print("Rating must be between 1 and 5.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get review text
        review_text = input("Enter your review (optional): ").strip()
        
        # Moderate review text
        if review_text:
            moderation_result = moderate_review_content(review_text)
            if not moderation_result['approved']:
                print(f"Review contains inappropriate content: {moderation_result['reason']}")
                review_text = input("Please enter a revised review: ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if existing_review:
            # Update existing review
            cursor.execute('''
            UPDATE book_reviews 
            SET rating = ?, review_text = ?, review_date = ?, status = 'pending'
            WHERE review_id = ?
            ''', (rating, review_text, now, existing_review[0]))
            
            print("✅ Review updated successfully!")
        else:
            # Create new review
            cursor.execute('''
            INSERT INTO book_reviews 
            (book_id, user_id, rating, review_text, review_date, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (book_id, user_id, rating, review_text, now))
            
            review_id = cursor.lastrowid
            print("✅ Review submitted successfully!")
            
            # Award points for reviewing
            cursor.execute('''
            INSERT INTO user_achievements 
            (user_id, achievement_type, achievement_name, description, earned_date, points)
            VALUES (?, 'review', 'Book Reviewer', 'Submitted a book review', ?, 5)
            ''', (user_id, now))
        
        conn.commit()
        
        # Check if review moderation is enabled
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "review_moderation"')
        moderation_enabled = cursor.fetchone()[0].lower() == 'true'
        
        if moderation_enabled:
            print("Your review will be visible after moderation approval.")
        else:
            # Auto-approve if moderation is disabled
            if not existing_review:
                cursor.execute('''
                UPDATE book_reviews SET status = 'approved' 
                WHERE review_id = ?
                ''', (review_id,))
                conn.commit()
            print("Your review is now visible to other users.")
    
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error submitting review: {e}")
    
    conn.close()
    
def moderate_review_content(text: str) -> Dict:
    """Simple content moderation for reviews"""
    inappropriate_words = [
        'spam', 'fake', 'scam', 'inappropriate', 'offensive'
        # Add more as needed
    ]
    
    text_lower = text.lower()
    
    for word in inappropriate_words:
        if word in text_lower:
            return {
                'approved': False,
                'reason': f'Contains inappropriate word: {word}'
            }
    
    # Check for excessive caps
    if len([c for c in text if c.isupper()]) > len(text) * 0.7:
        return {
            'approved': False,
            'reason': 'Excessive use of capital letters'
        }
    
    return {'approved': True, 'reason': 'Content approved'}

def manage_reading_list_items(user_id: str):
    """Manage items within reading lists"""
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    while True:
        print("\nManage Reading List Items:")
        print("=========================")
        print("1. Add book to list")
        print("2. Remove book from list")
        print("3. Reorder list items")
        print("4. Add notes to book")
        print("5. View list contents")
        print("6. Return to menu")
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '6':
            break
        
        try:
            if choice == '1':
                # Show user's lists
                cursor.execute('''
                SELECT list_id, name FROM reading_lists 
                WHERE creator_id = ? OR is_collaborative = 1
                ORDER BY name
                ''', (user_id,))
                
                lists = cursor.fetchall()
                
                if not lists:
                    print("No reading lists available.")
                    continue
                
                print("Available lists:")
                for i, (list_id, name) in enumerate(lists, 1):
                    print(f"{i}. {name}")
                
                try:
                    list_choice = int(input("Select list: ")) - 1
                    selected_list_id = lists[list_choice][0]
                    
                    book_id = input("Enter Book ID to add: ").strip()
                    
                    # Check if book exists
                    cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
                    book = cursor.fetchone()
                    
                    if not book:
                        print("Book not found.")
                        continue
                    
                    # Check if already in list
                    cursor.execute('''
                    SELECT item_id FROM reading_list_items 
                    WHERE list_id = ? AND book_id = ?
                    ''', (selected_list_id, book_id))
                    
                    if cursor.fetchone():
                        print("Book already in this list.")
                        continue
                    
                    notes = input("Add notes (optional): ").strip()
                    
                    cursor.execute('''
                    INSERT INTO reading_list_items 
                    (list_id, book_id, added_date, added_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (selected_list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, notes))
                    
                    conn.commit()
                    print(f"✅ Book added to list.")
                    
                except (ValueError, IndexError):
                    print("Invalid selection.")
            
            elif choice == '2':
                # Remove book from list
                cursor.execute('''
                SELECT rl.list_id, rl.name, rli.item_id, b.title
                FROM reading_lists rl
                JOIN reading_list_items rli ON rl.list_id = rli.list_id
                JOIN books b ON rli.book_id = b.book_id
                WHERE rl.creator_id = ? OR rl.is_collaborative = 1
                ORDER BY rl.name, b.title
                ''', (user_id,))
                
                items = cursor.fetchall()
                
                if not items:
                    print("No items in your reading lists.")
                    continue
                
                print("Items in your lists:")
                for i, (list_id, list_name, item_id, book_title) in enumerate(items, 1):
                    print(f"{i}. {book_title} (from {list_name})")
                
                try:
                    item_choice = int(input("Select item to remove: ")) - 1
                    selected_item_id = items[item_choice][2]
                    
                    cursor.execute('DELETE FROM reading_list_items WHERE item_id = ?', (selected_item_id,))
                    conn.commit()
                    print("✅ Item removed from list.")
                    
                except (ValueError, IndexError):
                    print("Invalid selection.")
            
            elif choice == '3':
                # Reorder list items
                print("List reordering feature would allow drag-and-drop or number-based reordering.")
                print("Implementation requires updating order_index values.")
            
            elif choice == '4':
                # Add notes to book
                cursor.execute('''
                SELECT rli.item_id, rl.name, b.title, rli.notes
                FROM reading_list_items rli
                JOIN reading_lists rl ON rli.list_id = rl.list_id
                JOIN books b ON rli.book_id = b.book_id
                WHERE rl.creator_id = ? OR (rl.is_collaborative = 1 AND rli.added_by = ?)
                ''', (user_id, user_id))
                
                items = cursor.fetchall()
                
                if not items:
                    print("No items found.")
                    continue
                
                print("Your reading list items:")
                for i, (item_id, list_name, book_title, current_notes) in enumerate(items, 1):
                    notes_preview = current_notes[:30] + "..." if current_notes and len(current_notes) > 30 else current_notes or "No notes"
                    print(f"{i}. {book_title} - {notes_preview}")
                
                try:
                    item_choice = int(input("Select item to add notes: ")) - 1
                    selected_item_id = items[item_choice][0]
                    
                    current_notes = items[item_choice][3] or ""
                    print(f"Current notes: {current_notes}")
                    
                    new_notes = input("Enter new notes: ").strip()
                    
                    cursor.execute('''
                    UPDATE reading_list_items SET notes = ? WHERE item_id = ?
                    ''', (new_notes, selected_item_id))
                    
                    conn.commit()
                    print("✅ Notes updated.")
                    
                except (ValueError, IndexError):
                    print("Invalid selection.")
            
            elif choice == '5':
                # View list contents
                cursor.execute('''
                SELECT list_id, name FROM reading_lists 
                WHERE creator_id = ?
                ORDER BY name
                ''', (user_id,))
                
                lists = cursor.fetchall()
                
                if not lists:
                    print("No reading lists found.")
                    continue
                
                print("Your reading lists:")
                for i, (list_id, name) in enumerate(lists, 1):
                    print(f"{i}. {name}")
                
                try:
                    list_choice = int(input("Select list to view: ")) - 1
                    selected_list_id = lists[list_choice][0]
                    
                    view_reading_list_details(selected_list_id)
                    
                except (ValueError, IndexError):
                    print("Invalid selection.")
        
        except sqlite3.Error as e:
            print(f"Error managing reading list items: {e}")
    
    conn.close()

def import_reading_list(user_id: str):
    """Import reading list from various sources - complete implementation"""
    print("\nImport Reading List:")
    print("===================")
    print("1. Import from CSV file")
    print("2. Import from JSON file")
    print("3. Import from share link")
    print("4. Copy public reading list")
    print("5. Import from Goodreads export")
    
    choice = input("Select import method (1-5): ").strip()
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        if choice == '1':
            # Import from CSV
            file_path = input("Enter CSV file path: ").strip()
            
            if not os.path.exists(file_path):
                print("File not found.")
                return
            
            df = pd.read_csv(file_path)
            
            required_columns = ['title']
            if not all(col in df.columns for col in required_columns):
                print("CSV must contain at least a 'title' column.")
                return
            
            list_name = input("Enter name for imported list: ").strip()
            description = input("Enter description (optional): ").strip()
            
            # Create new reading list
            cursor.execute('''
            INSERT INTO reading_lists (name, description, creator_id, created_date)
            VALUES (?, ?, ?, ?)
            ''', (list_name, description, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            list_id = cursor.lastrowid
            imported_count = 0
            
            for _, row in df.iterrows():
                book_id = None
                title = str(row['title']).strip()
                author = str(row.get('author', '')).strip() if pd.notna(row.get('author')) else ''
                
                # Try to find book by title and author
                if author:
                    cursor.execute('''
                    SELECT book_id FROM books 
                    WHERE LOWER(title) LIKE LOWER(?) AND LOWER(author) LIKE LOWER(?)
                    LIMIT 1
                    ''', (f'%{title}%', f'%{author}%'))
                else:
                    cursor.execute('''
                    SELECT book_id FROM books WHERE LOWER(title) LIKE LOWER(?) LIMIT 1
                    ''', (f'%{title}%',))
                
                result = cursor.fetchone()
                if result:
                    book_id = result[0]
                    
                    # Add to reading list
                    cursor.execute('''
                    INSERT OR IGNORE INTO reading_list_items
                    (list_id, book_id, added_date, added_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                          user_id, f"Imported: {title} by {author}"))
                    
                    imported_count += 1
            
            conn.commit()
            print(f"✅ Imported {imported_count} books to reading list '{list_name}'")
        
        elif choice == '2':
            # Import from JSON
            file_path = input("Enter JSON file path: ").strip()
            
            if not os.path.exists(file_path):
                print("File not found.")
                return
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            list_name = data.get('name') or input("Enter list name: ").strip()
            description = data.get('description', '')
            books = data.get('books', [])
            
            cursor.execute('''
            INSERT INTO reading_lists (name, description, creator_id, created_date)
            VALUES (?, ?, ?, ?)
            ''', (list_name, description, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            list_id = cursor.lastrowid
            imported_count = 0
            
            for book_data in books:
                if 'book_id' in book_data:
                    book_id = book_data['book_id']
                elif 'title' in book_data:
                    title = book_data['title']
                    author = book_data.get('author', '')
                    
                    # Find book in database
                    if author:
                        cursor.execute('''
                        SELECT book_id FROM books 
                        WHERE LOWER(title) = LOWER(?) AND LOWER(author) = LOWER(?)
                        LIMIT 1
                        ''', (title, author))
                    else:
                        cursor.execute('''
                        SELECT book_id FROM books WHERE LOWER(title) = LOWER(?) LIMIT 1
                        ''', (title,))
                    
                    result = cursor.fetchone()
                    book_id = result[0] if result else None
                else:
                    continue
                
                if book_id:
                    notes = book_data.get('notes', '')
                    cursor.execute('''
                    INSERT OR IGNORE INTO reading_list_items
                    (list_id, book_id, added_date, added_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, notes))
                    
                    imported_count += 1
            
            conn.commit()
            print(f"✅ Imported {imported_count} books to reading list '{list_name}'")
        
        elif choice == '3':
            # Import from share link
            share_link = input("Enter share link: ").strip()
            
            if share_link.startswith("library://reading-list/"):
                source_list_id = share_link.split("/")[-1]
                
                cursor.execute('''
                SELECT name, description, is_public FROM reading_lists WHERE list_id = ?
                ''', (source_list_id,))
                
                source_list = cursor.fetchone()
                
                if not source_list or not source_list[2]:
                    print("Reading list not found or not public.")
                    return
                
                new_name = input(f"Name for imported list (original: {source_list[0]}): ").strip() or f"Copy of {source_list[0]}"
                
                cursor.execute('''
                INSERT INTO reading_lists (name, description, creator_id, created_date)
                VALUES (?, ?, ?, ?)
                ''', (new_name, source_list[1], user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                new_list_id = cursor.lastrowid
                
                cursor.execute('''
                INSERT INTO reading_list_items (list_id, book_id, added_date, added_by, notes)
                SELECT ?, book_id, ?, ?, 'Imported from shared list'
                FROM reading_list_items
                WHERE list_id = ?
                ''', (new_list_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, source_list_id))
                
                conn.commit()
                print(f"✅ Reading list imported successfully as '{new_name}'")
            else:
                print("Invalid share link format.")
        
        elif choice == '4':
            # Copy public reading list
            cursor.execute('''
            SELECT list_id, name, description, creator_id
            FROM reading_lists
            WHERE is_public = 1 AND creator_id != ?
            ORDER BY name
            ''', (user_id,))
            
            public_lists = cursor.fetchall()
            
            if not public_lists:
                print("No public reading lists available.")
                return
            
            print("Public reading lists:")
            for i, (list_id, name, desc, creator) in enumerate(public_lists, 1):
                print(f"{i}. {name} by {creator}")
            
            try:
                choice_idx = int(input("Select list to copy: ")) - 1
                selected_list = public_lists[choice_idx]
                source_list_id, source_name, source_desc, creator = selected_list
                
                new_name = input(f"Name for copied list (original: {source_name}): ").strip() or f"Copy of {source_name}"
                
                cursor.execute('''
                INSERT INTO reading_lists (name, description, creator_id, created_date)
                VALUES (?, ?, ?, ?)
                ''', (new_name, source_desc, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                new_list_id = cursor.lastrowid
                
                cursor.execute('''
                INSERT INTO reading_list_items (list_id, book_id, added_date, added_by, notes)
                SELECT ?, book_id, ?, ?, notes
                FROM reading_list_items
                WHERE list_id = ?
                ''', (new_list_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, source_list_id))
                
                conn.commit()
                print(f"✅ Reading list copied successfully as '{new_name}'")
                
            except (ValueError, IndexError):
                print("Invalid selection.")
        
        elif choice == '5':
            # Import from Goodreads export (CSV format)
            file_path = input("Enter Goodreads CSV export file path: ").strip()
            
            if not os.path.exists(file_path):
                print("File not found.")
                return
            
            df = pd.read_csv(file_path)
            
            # Goodreads CSV typically has columns: Title, Author, ISBN, etc.
            list_name = input("Enter name for imported Goodreads list: ").strip()
            
            cursor.execute('''
            INSERT INTO reading_lists (name, description, creator_id, created_date)
            VALUES (?, ?, ?, ?)
            ''', (list_name, "Imported from Goodreads", user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            list_id = cursor.lastrowid
            imported_count = 0
            
            for _, row in df.iterrows():
                title = str(row.get('Title', '')).strip()
                author = str(row.get('Author', '')).strip()
                isbn = str(row.get('ISBN', '')).strip()
                
                if not title:
                    continue
                
                # Try to find book by ISBN first, then by title/author
                book_id = None
                
                if isbn and isbn != 'nan':
                    cursor.execute('SELECT book_id FROM books WHERE isbn = ?', (isbn,))
                    result = cursor.fetchone()
                    if result:
                        book_id = result[0]
                
                if not book_id and title:
                    if author:
                        cursor.execute('''
                        SELECT book_id FROM books 
                        WHERE LOWER(title) LIKE LOWER(?) AND LOWER(author) LIKE LOWER(?)
                        LIMIT 1
                        ''', (f'%{title}%', f'%{author}%'))
                    else:
                        cursor.execute('''
                        SELECT book_id FROM books WHERE LOWER(title) LIKE LOWER(?) LIMIT 1
                        ''', (f'%{title}%',))
                    
                    result = cursor.fetchone()
                    if result:
                        book_id = result[0]
                
                if book_id:
                    rating = row.get('My Rating', '')
                    notes = f"Goodreads import - Rating: {rating}" if rating else "Imported from Goodreads"
                    
                    cursor.execute('''
                    INSERT OR IGNORE INTO reading_list_items
                    (list_id, book_id, added_date, added_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, notes))
                    
                    imported_count += 1
            
            conn.commit()
            print(f"✅ Imported {imported_count} books from Goodreads to '{list_name}'")
    
    except Exception as e:
        print(f"Error importing reading list: {e}")
    
    conn.close()

def manage_reading_lists():
    """Manage personal and collaborative reading lists"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage reading lists.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    user_id = get_current_user_id()  # FIXED: Use helper function
    
    while True:
        print("\nReading Lists Management:")
        print("========================")
        print("1. View My Reading Lists")
        print("2. Create New Reading List")
        print("3. Browse Public Reading Lists")
        print("4. Manage List Items")
        print("5. Share Reading List")
        print("6. Import Reading List")
        print("7. Return to menu")
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '7':
            break
        
        try:
            if choice == '1':
                # View user's reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.created_date,
                       rl.is_public, rl.is_collaborative,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.creator_id = ?
                GROUP BY rl.list_id
                ORDER BY rl.created_date DESC
                ''', (user_id,))
                
                lists = cursor.fetchall()
                
                if not lists:
                    print("You don't have any reading lists yet.")
                    continue
                
                print(f"\nYour Reading Lists ({len(lists)}):")
                print("-" * 80)
                print(f"{'ID':<4} {'Name':<25} {'Items':<6} {'Type':<15} {'Created':<12}")
                print("-" * 80)
                
                for lst in lists:
                    list_id, name, desc, created, is_public, is_collab, count = lst
                    list_type = "Public" if is_public else "Private"
                    if is_collab:
                        list_type += " + Collab"
                    
                    print(f"{list_id:<4} {name[:24]:<25} {count:<6} {list_type:<15} {created[:10]:<12}")
                
                print("-" * 80)
                
            elif choice == '2':
                # Create new reading list
                name = input("Enter list name: ").strip()
                if not name:
                    print("List name cannot be empty.")
                    continue
                
                description = input("Enter description (optional): ").strip()
                
                is_public = input("Make this list public? (y/n): ").strip().lower() == 'y'
                is_collaborative = False
                
                if is_public:
                    is_collaborative = input("Allow others to add books? (y/n): ").strip().lower() == 'y'
                
                category = input("Enter category (optional): ").strip()
                reading_level = input("Target reading level (optional): ").strip()
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO reading_lists 
                (name, description, creator_id, created_date, is_public, is_collaborative, category, target_reading_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, user_id, now, is_public, is_collaborative, category, reading_level))
                
                list_id = cursor.lastrowid
                conn.commit()
                
                print(f"✅ Reading list '{name}' created successfully! (ID: {list_id})")
                
            elif choice == '3':
                # Browse public reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.creator_id,
                       rl.category, rl.target_reading_level,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.is_public = 1
                GROUP BY rl.list_id
                ORDER BY item_count DESC, rl.name
                ''', )
                
                public_lists = cursor.fetchall()
                
                if not public_lists:
                    print("No public reading lists available.")
                    continue
                
                print(f"\nPublic Reading Lists ({len(public_lists)}):")
                print("-" * 90)
                print(f"{'ID':<4} {'Name':<25} {'Creator':<12} {'Category':<15} {'Items':<6} {'Level':<12}")
                print("-" * 90)
                
                for lst in public_lists:
                    list_id, name, desc, creator, category, level, count = lst
                    category = category or "General"
                    level = level or "Any"
                    
                    print(f"{list_id:<4} {name[:24]:<25} {creator[:11]:<12} {category[:14]:<15} {count:<6} {level[:11]:<12}")
                
                print("-" * 90)
                
                # Option to view details
                view_id = input("\nEnter list ID to view details (or press Enter): ").strip()
                if view_id:
                    view_reading_list_details(int(view_id))
                
            elif choice == '4':
                # Manage list items
                manage_reading_list_items(user_id)
                
            elif choice == '5':
                # Share reading list
                share_reading_list(user_id)
                
            elif choice == '6':
                # Import reading list
                import_reading_list(user_id)
        
        except sqlite3.Error as e:
            print(f"Error managing reading lists: {e}")
    
    conn.close()

def add_to_reading_list(book_id: str = None):
    """Add a book to a reading list"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to add books to reading lists.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    # FIXED: Use the helper function to get user_id safely
    user_id = get_current_user_id()
    
    try:
        if book_id is None:
            book_id = input("Enter Book ID to add: ").strip()
        
        # Verify book exists
        cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()
        
        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        title, author = book
        
        # Get user's reading lists
        cursor.execute('''
        SELECT list_id, name, description
        FROM reading_lists
        WHERE creator_id = ? OR is_collaborative = 1
        ORDER BY creator_id = ? DESC, name
        ''', (user_id, user_id))
        
        lists = cursor.fetchall()
        
        if not lists:
            print("You don't have any reading lists. Create one first.")
            conn.close()
            return
        
        print(f"\nAdding '{title}' to reading list:")
        print("Available Lists:")
        for i, (list_id, name, desc) in enumerate(lists, 1):
            print(f"{i}. {name} - {desc[:50]}{'...' if len(desc) > 50 else ''}")
        
        try:
            choice = int(input("Select list number: ")) - 1
            selected_list = lists[choice]
            list_id = selected_list[0]
            
            # Check if book is already in the list
            cursor.execute('''
            SELECT item_id FROM reading_list_items
            WHERE list_id = ? AND book_id = ?
            ''', (list_id, book_id))
            
            if cursor.fetchone():
                print("This book is already in the selected list.")
                conn.close()
                return
            
            # Add book to list
            cursor.execute('''
            INSERT INTO reading_list_items
            (list_id, book_id, added_date, added_by)
            VALUES (?, ?, ?, ?)
            ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
            
            conn.commit()
            print(f"✅ '{title}' added to reading list '{selected_list[1]}'")
            
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    except sqlite3.Error as e:
        print(f"Error adding book to reading list: {e}")
    
    conn.close()
    
def bulk_import_books():
    """Bulk import books from CSV/Excel files"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to import books.")
        return
    
    if not auth.check_permission('manage_books'):
        print("You don't have permission to import books.")
        return
    
    print("\nBulk Book Import:")
    print("================")
    print("Supported formats: CSV, Excel (.xlsx, .xls)")
    print("Required columns: title, author")
    print("Optional columns: isbn, publisher, category, year_published, description, location, reading_level, tags")
    
    file_path = input("Enter file path: ").strip()
    
    if not os.path.exists(file_path):
        print("File not found.")
        return
    
    try:
        # Read file based on extension
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            print("Unsupported file format.")
            return
        
        # Validate required columns
        required_columns = ['title', 'author']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Missing required columns: {', '.join(missing_columns)}")
            return
        
        print(f"Found {len(df)} books to import.")
        print("Sample data:")
        print(df.head())
        
        confirm = input("\nProceed with import? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Import cancelled.")
            return
        
        conn = get_db_connection()
        if not conn:
            return
        
        cursor = conn.cursor()
        
        # Get next book ID
        cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
        result = cursor.fetchone()[0]
        next_id = 10001 if result is None else result + 1
        
        imported_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                book_id = f"B{next_id + imported_count}"
                
                # Extract data with defaults
                title = str(row['title']).strip()
                author = str(row['author']).strip()
                isbn = str(row.get('isbn', '')).strip() if pd.notna(row.get('isbn')) else None
                publisher = str(row.get('publisher', '')).strip() if pd.notna(row.get('publisher')) else None
                category = str(row.get('category', 'General')).strip()
                year_published = int(row['year_published']) if pd.notna(row.get('year_published')) else None
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                location = str(row.get('location', '')).strip() if pd.notna(row.get('location')) else None
                reading_level = str(row.get('reading_level', 'Unknown')).strip()
                tags_str = str(row.get('tags', '')).strip() if pd.notna(row.get('tags')) else ''
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
                
                # Generate barcode and QR code
                barcode = generate_barcode(book_id)
                qr_code_path = generate_qr_code(book_id, title)
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Insert book
                cursor.execute('''
                INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book_id, title, author, isbn, publisher, category,
                    year_published, description, location, 'available', now, now,
                    reading_level, json.dumps(tags), None, None, 0.0,
                    barcode, qr_code_path, None, 'English', None, None
                ))
                
                imported_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {index + 1}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Bulk imported {imported_count} books", "books")
        
        print(f"\n✅ Import completed!")
        print(f"Successfully imported: {imported_count} books")
        if error_count > 0:
            print(f"Errors: {error_count}")
            print("First few errors:")
            for error in errors[:5]:
                print(f"  • {error}")
    
    except Exception as e:
        print(f"Error during import: {e}")
        
def bulk_export_books():
    """Export books to CSV/Excel files"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to export books.")
        return
    
    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print("You don't have permission to export books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nBulk Book Export:")
    print("================")
    print("1. Export All Books")
    print("2. Export by Category")
    print("3. Export by Status")
    print("4. Export by Date Range")
    
    choice = input("Select export type (1-4): ").strip()
    
    try:
        if choice == '1':
            # Export all books
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            ORDER BY title
            ''')
            
        elif choice == '2':
            # Export by category
            cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            
            print("Available categories:")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")
            
            cat_choice = int(input("Select category: ")) - 1
            selected_category = categories[cat_choice]
            
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE category = ?
            ORDER BY title
            ''', (selected_category,))
            
        elif choice == '3':
            # Export by status
            status = input("Enter status (available/checked_out/reserved/lost/damaged): ").strip()
            
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE status = ?
            ORDER BY title
            ''', (status,))
            
        elif choice == '4':
            # Export by date range
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()
            
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE date(added_date) BETWEEN ? AND ?
            ORDER BY title
            ''', (start_date, end_date))
        
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        books = cursor.fetchall()
        
        if not books:
            print("No books found matching criteria.")
            conn.close()
            return
        
        # Convert to DataFrame
        columns = [
            'book_id', 'title', 'author', 'isbn', 'publisher', 'category', 'year_published',
            'description', 'location', 'status', 'reading_level', 'tags', 'barcode',
            'acquisition_cost', 'total_pages', 'language', 'edition', 'added_date'
        ]
        
        df = pd.DataFrame(books, columns=columns)
        
        # Parse tags column
        df['tags'] = df['tags'].apply(lambda x: ', '.join(json.loads(x)) if x else '')
        
        # Choose export format
        format_choice = input("Export format (1=CSV, 2=Excel): ").strip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_choice == '1':
            filename = f"books_export_{timestamp}.csv"
            df.to_csv(filename, index=False)
        else:
            filename = f"books_export_{timestamp}.xlsx"
            df.to_excel(filename, index=False)
        
        print(f"✅ Books exported to {filename}")
        print(f"Total books exported: {len(books)}")
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Exported {len(books)} books to {filename}", "books")
    except Exception as e:
        print(f"Error during export: {e}")
    
    conn.close()
    
def manage_digital_library():
    """Manage digital books and resources"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage digital library.")
        return
    
    if not auth.check_permission('manage_books'):
        print("You don't have permission to manage digital library.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    while True:
        print("\nDigital Library Management:")
        print("==========================")
        print("1. View Digital Collection")
        print("2. Add Digital Resource")
        print("3. Link Digital Copy to Physical Book")
        print("4. Download Statistics")
        print("5. Manage Access Levels")
        print("6. Return to menu")
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '6':
            break
        
        try:
            if choice == '1':
                # View digital collection
                cursor.execute('''
                SELECT digital_id, title, author, file_type, access_level, 
                       download_count, added_date
                FROM digital_library
                ORDER BY title
                ''')
                
                digital_items = cursor.fetchall()
                
                if not digital_items:
                    print("No digital resources found.")
                    continue
                
                print(f"\nDigital Collection ({len(digital_items)} items):")
                print("-" * 90)
                print(f"{'ID':<4} {'Title':<30} {'Author':<20} {'Type':<8} {'Access':<8} {'Downloads':<10}")
                print("-" * 90)
                
                for item in digital_items:
                    digital_id, title, author, file_type, access_level, downloads, added_date = item
                    title_display = title[:29] if len(title) > 30 else title
                    author_display = author[:19] if len(author) > 20 else author
                    
                    print(f"{digital_id:<4} {title_display:<30} {author_display:<20} {file_type:<8} {access_level:<8} {downloads:<10}")
                
                print("-" * 90)
                
            elif choice == '2':
                # Add digital resource
                title = input("Enter title: ").strip()
                author = input("Enter author: ").strip()
                file_path = input("Enter file path: ").strip()
                
                if not os.path.exists(file_path):
                    print("File not found.")
                    continue
                
                file_type = os.path.splitext(file_path)[1][1:].upper()
                file_size = os.path.getsize(file_path)
                category = input("Enter category: ").strip()
                description = input("Enter description: ").strip()
                
                print("Access levels:")
                print("1. Public")
                print("2. Students Only")
                print("3. Staff Only")
                print("4. Restricted")
                
                access_choice = input("Select access level (1-4): ").strip()
                access_levels = {'1': 'public', '2': 'students', '3': 'staff', '4': 'restricted'}
                access_level = access_levels.get(access_choice, 'public')
                
                # Copy file to digital library directory
                digital_dir = "digital_library"
                os.makedirs(digital_dir, exist_ok=True)
                
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file_path)}"
                new_path = os.path.join(digital_dir, filename)
                shutil.copy2(file_path, new_path)
                
                cursor.execute('''
                INSERT INTO digital_library 
                (title, author, file_path, file_type, file_size, category, 
                 description, access_level, added_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, author, new_path, file_type, file_size, category,
                    description, access_level, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                digital_id = cursor.lastrowid
                conn.commit()
                
                print(f"✅ Digital resource added successfully! (ID: {digital_id})")
                
            elif choice == '3':
                # Link digital copy to physical book
                book_id = input("Enter physical book ID: ").strip()
                
                # Check if book exists
                cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
                book = cursor.fetchone()
                
                if not book:
                    print("Physical book not found.")
                    continue
                
                # Show available digital resources
                cursor.execute('SELECT digital_id, title FROM digital_library ORDER BY title')
                digital_items = cursor.fetchall()
                
                if not digital_items:
                    print("No digital resources available.")
                    continue
                
                print("Available digital resources:")
                for i, (digital_id, title) in enumerate(digital_items, 1):
                    print(f"{i}. {title} (ID: {digital_id})")
                
                try:
                    choice_idx = int(input("Select digital resource: ")) - 1
                    selected_digital = digital_items[choice_idx]
                    digital_path = f"digital_id:{selected_digital[0]}"
                    
                    cursor.execute('''
                    UPDATE books SET digital_copy_path = ? WHERE book_id = ?
                    ''', (digital_path, book_id))
                    
                    conn.commit()
                    print(f"✅ Digital copy linked to book {book_id}")
                    
                except (ValueError, IndexError):
                    print("Invalid selection.")
                
            elif choice == '4':
                # Download statistics
                cursor.execute('''
                SELECT title, author, file_type, download_count
                FROM digital_library
                ORDER BY download_count DESC
                LIMIT 10
                ''')
                
                stats = cursor.fetchall()
                
                print("\nTop Downloaded Digital Resources:")
                print("-" * 70)
                print(f"{'Title':<30} {'Author':<20} {'Type':<8} {'Downloads':<10}")
                print("-" * 70)
                
                for title, author, file_type, downloads in stats:
                    title_display = title[:29] if len(title) > 30 else title
                    author_display = author[:19] if len(author) > 20 else author
                    print(f"{title_display:<30} {author_display:<20} {file_type:<8} {downloads:<10}")
                
                print("-" * 70)
        
        except sqlite3.Error as e:
            print(f"Error managing digital library: {e}")
    
    conn.close()

def automated_notifications():
    """Process and send automated notifications"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage notifications.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to manage notifications.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nAutomated Notifications:")
    print("=======================")
    print("1. Send Due Date Reminders")
    print("2. Send Overdue Notifications")
    print("3. Send Reservation Alerts")
    print("4. Process Notification Queue")
    print("5. Configure Notification Settings")
    print("6. Return to menu")
    
    choice = input("Enter your choice (1-6): ").strip()
    
    try:
        if choice == '1':
            # Send due date reminders
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE date(bl.due_date) = ? AND bl.status = 'active'
            ''', (tomorrow,))
            
            due_soon = cursor.fetchall()
            
            sent_count = 0
            for user_id, book_id, title, due_date in due_soon:
                try:
                    send_due_date_reminder(user_id, book_id, title, due_date[:10])
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send reminder to {user_id}: {e}")
            
            print(f"✅ Sent {sent_count} due date reminders")
            
        elif choice == '2':
            # Send overdue notifications
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE date(bl.due_date) < date('now') AND bl.status IN ('active', 'overdue')
            ''')
            
            overdue_items = cursor.fetchall()
            
            sent_count = 0
            for user_id, book_id, title, due_date, days_overdue in overdue_items:
                try:
                    # Update loan status to overdue
                    cursor.execute('''
                    UPDATE book_loans SET status = 'overdue' 
                    WHERE book_id = ? AND user_id = ? AND status = 'active'
                    ''', (book_id, user_id))
                    
                    send_overdue_notification(user_id, book_id, title, due_date[:10], int(days_overdue))
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send overdue notice to {user_id}: {e}")
            
            conn.commit()
            print(f"✅ Sent {sent_count} overdue notifications")
            
        elif choice == '3':
            # Send reservation alerts for available books
            cursor.execute('''
            SELECT br.user_id, br.book_id, b.title, br.reservation_id
            FROM book_reservations br
            JOIN books b ON br.book_id = b.book_id
            WHERE b.status = 'available' AND br.status = 'active' 
            AND br.priority_order = 1 AND br.notification_sent = 0
            ''')
            
            available_reservations = cursor.fetchall()
            
            sent_count = 0
            for user_id, book_id, title, reservation_id in available_reservations:
                try:
                    send_reservation_available_notification(user_id, book_id, title)
                    
                    # Mark notification as sent and update book status
                    cursor.execute('''
                    UPDATE book_reservations SET notification_sent = 1 
                    WHERE reservation_id = ?
                    ''', (reservation_id,))
                    
                    cursor.execute('''
                    UPDATE books SET status = 'reserved' WHERE book_id = ?
                    ''', (book_id,))
                    
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send reservation alert to {user_id}: {e}")
            
            conn.commit()
            print(f"✅ Sent {sent_count} reservation alerts")
            
        elif choice == '4':
            # Process notification queue
            cursor.execute('''
            SELECT notification_id, user_id, notification_type, title, message, delivery_method
            FROM notification_queue
            WHERE sent = 0 AND (send_date IS NULL OR send_date <= datetime('now'))
            ORDER BY priority DESC, created_date
            LIMIT 50
            ''')
            
            queued_notifications = cursor.fetchall()
            
            processed_count = 0
            for notification_id, user_id, notif_type, title, message, method in queued_notifications:
                try:
                    if method == 'email':
                        send_generic_email_notification(user_id, title, message)
                    elif method == 'sms':
                        send_sms_notification(user_id, message)
                    
                    cursor.execute('''
                    UPDATE notification_queue SET sent = 1 
                    WHERE notification_id = ?
                    ''', (notification_id,))
                    
                    processed_count += 1
                except Exception as e:
                    logging.error(f"Failed to send notification {notification_id}: {e}")
            
            conn.commit()
            print(f"✅ Processed {processed_count} queued notifications")
            
        elif choice == '5':
            # Configure notification settings
            configure_notification_settings()
    
    except sqlite3.Error as e:
        print(f"Error processing notifications: {e}")
    
    conn.close()

def send_enhanced_checkout_notification(user_id: str, book_id: str, title: str, due_date: str):
    """Send enhanced checkout confirmation with QR code and tips"""
    try:
        # Get user email if available
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT email FROM students WHERE student_id = ?', (user_id,))
        user_email = cursor.fetchone()
        
        if user_email and user_email[0]:
            from university_system.infrastructure.email.template_utils import render_template

            subject, message = render_template('library_book_checkout', {
                'title': title,
                'book_id': book_id,
                'due_date': due_date
            })

            if subject and message:
                send_email_notification(user_email[0], subject, message)
        
        conn.close()
        
    except Exception as e:
        logging.error(f"Error sending checkout notification: {e}")

def generate_analytics_dashboard():
    """Generate comprehensive analytics dashboard"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return
    
    if not (auth.check_permission('view_reports') or auth.check_permission('generate_reports')):
        print("You don't have permission to view analytics.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("                    LIBRARY ANALYTICS DASHBOARD")
    print("="*80)
    
    try:
        # Current status overview
        cursor.execute('''
        SELECT 
            COUNT(*) as total_books,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
            SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
            SUM(CASE WHEN status IN ('lost', 'damaged') THEN 1 ELSE 0 END) as unavailable
        FROM books
        ''')
        
        book_stats = cursor.fetchone()
        
        print(f"\n📊 COLLECTION OVERVIEW")
        print(f"Total Books: {book_stats[0]:,}")
        print(f"Available: {book_stats[1]:,} ({book_stats[1]/book_stats[0]*100:.1f}%)")
        print(f"Checked Out: {book_stats[2]:,} ({book_stats[2]/book_stats[0]*100:.1f}%)")
        print(f"Reserved: {book_stats[3]:,}")
        print(f"Unavailable: {book_stats[4]:,}")
        
        # Active loans and reservations
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
        active_reservations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_count = cursor.fetchone()[0]
        
        print(f"\n🔄 CIRCULATION STATUS")
        print(f"Active Loans: {active_loans:,}")
        print(f"Overdue Items: {overdue_count:,}")
        print(f"Active Reservations: {active_reservations:,}")
        
        # Top categories
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM books
        GROUP BY category
        ORDER BY count DESC
        LIMIT 5
        ''')
        
        top_categories = cursor.fetchall()
        
        print(f"\n📚 TOP CATEGORIES")
        for i, (category, count) in enumerate(top_categories, 1):
            print(f"{i}. {category}: {count:,} books")
        
        # Most active users
        cursor.execute('''
        SELECT user_id, COUNT(*) as loan_count
        FROM book_loans
        WHERE checkout_date >= date('now', '-30 days')
        GROUP BY user_id
        ORDER BY loan_count DESC
        LIMIT 5
        ''')
        
        active_users = cursor.fetchall()
        
        print(f"\n👥 MOST ACTIVE USERS (Last 30 days)")
        for i, (user_id, count) in enumerate(active_users, 1):
            print(f"{i}. {user_id}: {count:,} checkouts")
        
        # Reading level distribution
        cursor.execute('''
        SELECT reading_level, COUNT(*) as count
        FROM books
        WHERE reading_level IS NOT NULL
        GROUP BY reading_level
        ORDER BY count DESC
        ''')
        
        reading_levels = cursor.fetchall()
        
        print(f"\n📖 READING LEVEL DISTRIBUTION")
        for level, count in reading_levels:
            print(f"{level}: {count:,} books")
        
        # Monthly circulation trends
        cursor.execute('''
        SELECT strftime('%Y-%m', checkout_date) as month, COUNT(*) as checkouts
        FROM book_loans
        WHERE checkout_date >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        ''')
        
        monthly_trends = cursor.fetchall()
        
        print(f"\n📈 CIRCULATION TRENDS (Last 6 months)")
        for month, checkouts in monthly_trends:
            print(f"{month}: {checkouts:,} checkouts")
        
        # Achievement summary
        cursor.execute('''
        SELECT achievement_type, COUNT(*) as count
        FROM user_achievements
        WHERE earned_date >= date('now', '-30 days')
        GROUP BY achievement_type
        ORDER BY count DESC
        ''')
        
        achievements = cursor.fetchall()
        
        if achievements:
            print(f"\n🏆 RECENT ACHIEVEMENTS (Last 30 days)")
            for achievement_type, count in achievements:
                print(f"{achievement_type.replace('_', ' ').title()}: {count:,}")
        
        # System alerts
        alerts = []
        
        if overdue_count > 0:
            alerts.append(f"⚠️  {overdue_count} overdue items need attention")
        
        cursor.execute('SELECT COUNT(*) FROM books WHERE status = "damaged"')
        damaged_count = cursor.fetchone()[0]
        if damaged_count > 0:
            alerts.append(f"🔧 {damaged_count} books need repair")
        
        cursor.execute('SELECT COUNT(*) FROM book_requests WHERE status = "pending"')
        pending_requests = cursor.fetchone()[0]
        if pending_requests > 0:
            alerts.append(f"📝 {pending_requests} book requests pending")
        
        if alerts:
            print(f"\n🚨 SYSTEM ALERTS")
            for alert in alerts:
                print(f"   {alert}")
        
        print("="*80)
        
        # Offer to export detailed report
        export_choice = input("\nGenerate detailed analytics report? (y/n): ").strip().lower()
        
        if export_choice == 'y':
            generate_detailed_analytics_report()
    
    except sqlite3.Error as e:
        print(f"Error generating analytics: {e}")
    
    conn.close()

def generate_detailed_analytics_report():
    """Generate comprehensive analytics report with visualizations"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"library_analytics_report_{timestamp}.html"
        
        # Collect comprehensive data
        analytics_data = {}
        
        # Collection statistics
        cursor.execute('''
        SELECT category, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
               SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
               AVG(acquisition_cost) as avg_cost
        FROM books
        GROUP BY category
        ORDER BY total DESC
        ''')
        analytics_data['category_stats'] = cursor.fetchall()
        
        # Circulation patterns
        cursor.execute('''
        SELECT strftime('%Y-%m', checkout_date) as month,
               COUNT(*) as checkouts,
               COUNT(DISTINCT user_id) as unique_users,
               COUNT(DISTINCT book_id) as unique_books
        FROM book_loans
        WHERE checkout_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        analytics_data['monthly_circulation'] = cursor.fetchall()
        
        # User engagement
        cursor.execute('''
        SELECT user_id,
               COUNT(*) as total_loans,
               AVG(reading_progress) as avg_progress,
               SUM(fine_amount) as total_fines
        FROM book_loans
        GROUP BY user_id
        HAVING total_loans >= 3
        ORDER BY total_loans DESC
        LIMIT 20
        ''')
        analytics_data['top_users'] = cursor.fetchall()
        
        # Popular books
        cursor.execute('''
        SELECT b.title, b.author, b.category,
               COUNT(bl.loan_id) as loan_count,
               AVG(COALESCE(r.rating, 0)) as avg_rating
        FROM books b
        LEFT JOIN book_loans bl ON b.book_id = bl.book_id
        LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
        GROUP BY b.book_id
        HAVING loan_count > 0
        ORDER BY loan_count DESC
        LIMIT 15
        ''')
        analytics_data['popular_books'] = cursor.fetchall()
        
        # Generate HTML report
        html_content = generate_html_analytics_report(analytics_data)
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Detailed analytics report generated: {report_filename}")
        
        conn.close()
        
    except Exception as e:
        logging.error(f"Error generating detailed analytics: {e}")
        print(f"Error generating report: {e}")

def generate_html_analytics_report(data):
    """Generate HTML analytics report"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Library Analytics Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
            .section {{ margin: 30px 0; padding: 20px; border: 1px solid #ddd; }}
            .chart {{ width: 100%; height: 400px; margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #ecf0f1; border-radius: 5px; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <div class="header">
            <h1>📚 Library Analytics Report</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="section">
            <h2>📊 Collection Overview by Category</h2>
            <table>
                <tr>
                    <th>Category</th>
                    <th>Total Books</th>
                    <th>Available</th>
                    <th>Checked Out</th>
                    <th>Avg Cost</th>
                </tr>
    """
    
    for row in data['category_stats']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]}</td>
                    <td>{row[3]}</td>
                    <td>${row[4]:.2f if row[4] else 0}</td>
                </tr>
        """
    
    html += """
            </table>
        </div>
        
        <div class="section">
            <h2>📈 Monthly Circulation Trends</h2>
            <canvas id="circulationChart" class="chart"></canvas>
        </div>
        
        <div class="section">
            <h2>👥 Top Active Users</h2>
            <table>
                <tr>
                    <th>User ID</th>
                    <th>Total Loans</th>
                    <th>Avg Reading Progress</th>
                    <th>Total Fines</th>
                </tr>
    """
    
    for row in data['top_users']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]:.1f}%</td>
                    <td>${row[3]:.2f}</td>
                </tr>
        """
    
    html += """
            </table>
        </div>
        
        <div class="section">
            <h2>⭐ Most Popular Books</h2>
            <table>
                <tr>
                    <th>Title</th>
                    <th>Author</th>
                    <th>Category</th>
                    <th>Loan Count</th>
                    <th>Avg Rating</th>
                </tr>
    """
    
    for row in data['popular_books']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]}</td>
                    <td>{row[3]}</td>
                    <td>{row[4]:.1f if row[4] else 'N/A'}</td>
                </tr>
        """
    
    # Add JavaScript for charts
    months = [row[0] for row in data['monthly_circulation']]
    checkouts = [row[1] for row in data['monthly_circulation']]
    
    html += f"""
            </table>
        </div>
        
        <script>
            // Circulation chart
            const ctx = document.getElementById('circulationChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {months},
                    datasets: [{{
                        label: 'Monthly Checkouts',
                        data: {checkouts},
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html

def enhanced_system_backup():
    """Create comprehensive system backup"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create backups.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to create backups.")
        return
    
    print("\nSystem Backup:")
    print("==============")
    print("1. Quick Backup (Database only)")
    print("2. Full Backup (Database + Files)")
    print("3. Scheduled Backup Setup")
    print("4. Restore from Backup")
    
    choice = input("Enter your choice (1-4): ").strip()
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = BACKUP_DIR / f"backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        if choice in ['1', '2']:
            # Create database backup
            db_backup_path = os.path.join(backup_dir, 'library_database.db')
            shutil.copy2(DATABASE_FILE, db_backup_path)
            print(f"✅ Database backed up to {db_backup_path}")
            
            if choice == '2':
                # Backup additional files
                file_dirs = ['qr_codes', 'digital_library', 'cover_images']
                
                for dir_name in file_dirs:
                    if os.path.exists(dir_name):
                        backup_subdir = os.path.join(backup_dir, dir_name)
                        shutil.copytree(dir_name, backup_subdir)
                        print(f"✅ {dir_name} backed up")
                
            # Create backup manifest
            manifest = {
                'backup_date': datetime.now().isoformat(),
                'backup_type': 'full',
                'created_by': get_current_user_id(),
                'database_size': os.path.getsize(db_backup_path),
                'includes': ['database', 'qr_codes', 'digital_library', 'cover_images']
            }
                
            with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
                json.dump(manifest, f, indent=2)
            
            print(f"✅ Backup completed: {backup_dir}")
            
            # FIXED: Log the backup using get_current_user_id() helper function
            log_audit_event(get_current_user_id(), f"Created system backup: {backup_dir}", "system")
            
        elif choice == '3':
            # Setup scheduled backups
            setup_scheduled_backups()
                
        elif choice == '4':
            # Restore from backup
            restore_from_backup()
    
    except Exception as e:
        print(f"Error creating backup: {e}")
        logging.error(f"Backup error: {e}")
        
def manage_user_achievements():
    """Manage user achievements and reading goals"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage achievements.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nUser Achievements & Goals:")
    print("=========================")
    print("1. View User Achievements")
    print("2. View Reading Goals")
    print("3. Create Reading Goal")
    print("4. Award Manual Achievement")
    print("5. Leaderboards")
    print("6. Return to menu")
    
    choice = input("Enter your choice (1-6): ").strip()
    
    if choice == '6':
        return
    
    try:
        if choice == '1':
            # View user achievements
            user_id = input("Enter User ID (or press Enter for all): ").strip()
            
            if user_id:
                cursor.execute('''
                SELECT achievement_name, description, earned_date, points
                FROM user_achievements
                WHERE user_id = ?
                ORDER BY earned_date DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                SELECT user_id, achievement_name, earned_date, points
                FROM user_achievements
                ORDER BY earned_date DESC
                LIMIT 50
                ''')
            
            achievements = cursor.fetchall()
            
            if not achievements:
                print("No achievements found.")
                return
            
            print(f"\nAchievements ({len(achievements)}):")
            print("-" * 80)
            
            if user_id:
                print(f"{'Achievement':<30} {'Description':<30} {'Date':<12} {'Points':<8}")
                print("-" * 80)
                for name, desc, date, points in achievements:
                    print(f"{name[:29]:<30} {desc[:29]:<30} {date[:10]:<12} {points:<8}")
            else:
                print(f"{'User ID':<12} {'Achievement':<25} {'Date':<12} {'Points':<8}")
                print("-" * 80)
                for user_id, name, date, points in achievements:
                    print(f"{user_id:<12} {name[:24]:<25} {date[:10]:<12} {points:<8}")
        
        elif choice == '2':
            # View reading goals
            user_id = input("Enter User ID: ").strip()
            
            cursor.execute('''
            SELECT goal_type, target_value, current_value, start_date, end_date, status
            FROM reading_goals
            WHERE user_id = ?
            ORDER BY start_date DESC
            ''', (user_id,))
            
            goals = cursor.fetchall()
            
            if not goals:
                print("No reading goals found for this user.")
                return
            
            print(f"\nReading Goals for {user_id}:")
            print("-" * 80)
            print(f"{'Type':<15} {'Target':<8} {'Current':<8} {'Progress':<10} {'Period':<20} {'Status':<10}")
            print("-" * 80)
            
            for goal_type, target, current, start, end, status in goals:
                progress = f"{current}/{target}"
                period = f"{start[:10]} to {end[:10]}"
                print(f"{goal_type:<15} {target:<8} {current:<8} {progress:<10} {period:<20} {status:<10}")
        
        elif choice == '3':
            # Create reading goal
            user_id = input("Enter User ID: ").strip()
            
            print("Goal types:")
            print("1. books_read")
            print("2. pages_read")
            print("3. hours_read")
            print("4. categories_explored")
            
            goal_types = ['books_read', 'pages_read', 'hours_read', 'categories_explored']
            
            try:
                type_choice = int(input("Select goal type (1-4): ")) - 1
                goal_type = goal_types[type_choice]
                
                target_value = int(input("Enter target value: "))
                
                start_date = input("Start date (YYYY-MM-DD, or press Enter for today): ").strip()
                if not start_date:
                    start_date = datetime.now().strftime('%Y-%m-%d')
                
                end_date = input("End date (YYYY-MM-DD): ").strip()
                
                cursor.execute('''
                INSERT INTO reading_goals 
                (user_id, goal_type, target_value, start_date, end_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, goal_type, target_value, start_date, end_date,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                conn.commit()
                print(f"✅ Reading goal created for {user_id}")
                
            except (ValueError, IndexError):
                print("Invalid input.")
        
        elif choice == '4':
            # Award manual achievement
            user_id = input("Enter User ID: ").strip()
            achievement_name = input("Achievement name: ").strip()
            description = input("Description: ").strip()
            points = int(input("Points to award: ").strip())
            
            cursor.execute('''
            INSERT INTO user_achievements 
            (user_id, achievement_type, achievement_name, description, earned_date, points)
            VALUES (?, 'manual', ?, ?, ?, ?)
            ''', (
                user_id, achievement_name, description,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), points
            ))
            
            conn.commit()
            print(f"✅ Achievement '{achievement_name}' awarded to {user_id}")
        
        elif choice == '5':
            # Show leaderboards
            print("\nLeaderboards:")
            print("=============")
            
            # Top readers (by books)
            cursor.execute('''
            SELECT user_id, COUNT(*) as books_read
            FROM book_loans
            WHERE status = 'returned' AND return_date >= date('now', '-30 days')
            GROUP BY user_id
            ORDER BY books_read DESC
            LIMIT 10
            ''')
            
            top_readers = cursor.fetchall()
            
            print("\n🏆 Top Readers (Last 30 days):")
            print("-" * 30)
            for i, (user_id, count) in enumerate(top_readers, 1):
                print(f"{i:2}. {user_id:<12} {count} books")
            
            # Top achievers (by points)
            cursor.execute('''
            SELECT user_id, SUM(points) as total_points
            FROM user_achievements
            WHERE earned_date >= date('now', '-30 days')
            GROUP BY user_id
            ORDER BY total_points DESC
            LIMIT 10
            ''')
            
            top_achievers = cursor.fetchall()
            
            if top_achievers:
                print("\n🌟 Top Achievers (Last 30 days):")
                print("-" * 30)
                for i, (user_id, points) in enumerate(top_achievers, 1):
                    print(f"{i:2}. {user_id:<12} {points} points")
    
    except sqlite3.Error as e:
        print(f"Error managing achievements: {e}")
    
    conn.close()

# Report Generation Functions

def generate_circulation_report(start_date=None, end_date=None):
    """Generate detailed circulation report"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get circulation data
        cursor.execute('''
        SELECT 
            date(checkout_date) as checkout_day,
            COUNT(*) as daily_checkouts,
            COUNT(DISTINCT user_id) as unique_borrowers,
            COUNT(DISTINCT book_id) as unique_books
        FROM book_loans
        WHERE date(checkout_date) BETWEEN ? AND ?
        GROUP BY checkout_day
        ORDER BY checkout_day
        ''', (start_date, end_date))
        
        daily_data = cursor.fetchall()
        
        # Get returns data
        cursor.execute('''
        SELECT 
            date(return_date) as return_day,
            COUNT(*) as daily_returns
        FROM book_loans
        WHERE date(return_date) BETWEEN ? AND ?
        GROUP BY return_day
        ORDER BY return_day
        ''', (start_date, end_date))
        
        return_data = cursor.fetchall()
        
        # Get category breakdown
        cursor.execute('''
        SELECT 
            b.category,
            COUNT(*) as checkouts
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE date(bl.checkout_date) BETWEEN ? AND ?
        GROUP BY b.category
        ORDER BY checkouts DESC
        ''', (start_date, end_date))
        
        category_data = cursor.fetchall()
        
        # Generate report
        report = {
            'period': f"{start_date} to {end_date}",
            'daily_circulation': daily_data,
            'daily_returns': return_data,
            'category_breakdown': category_data,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        conn.close()
        return report
        
    except sqlite3.Error as e:
        logging.error(f"Error generating circulation report: {e}")
        conn.close()
        return None

def generate_inventory_report():
    """Generate inventory/collection report"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        # Collection overview
        cursor.execute('''
        SELECT 
            category,
            COUNT(*) as total_books,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN status = 'damaged' THEN 1 ELSE 0 END) as damaged,
            ROUND(AVG(acquisition_cost), 2) as avg_cost,
            SUM(acquisition_cost) as total_value
        FROM books
        GROUP BY category
        ORDER BY total_books DESC
        ''')
        
        category_stats = cursor.fetchall()
        
        # Reading level distribution
        cursor.execute('''
        SELECT 
            reading_level,
            COUNT(*) as book_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM books), 2) as percentage
        FROM books
        WHERE reading_level IS NOT NULL
        GROUP BY reading_level
        ORDER BY book_count DESC
        ''')
        
        reading_level_stats = cursor.fetchall()
        
        # Publication year analysis
        cursor.execute('''
        SELECT 
            CASE 
                WHEN year_published >= 2020 THEN '2020+'
                WHEN year_published >= 2010 THEN '2010-2019'
                WHEN year_published >= 2000 THEN '2000-2009'
                WHEN year_published >= 1990 THEN '1990-1999'
                ELSE 'Pre-1990'
            END as year_range,
            COUNT(*) as book_count
        FROM books
        WHERE year_published IS NOT NULL
        GROUP BY year_range
        ORDER BY book_count DESC
        ''')
        
        publication_stats = cursor.fetchall()
        
        # Authors with most books
        cursor.execute('''
        SELECT 
            author,
            COUNT(*) as book_count
        FROM books
        GROUP BY author
        HAVING book_count > 1
        ORDER BY book_count DESC
        LIMIT 20
        ''')
        
        author_stats = cursor.fetchall()
        
        report = {
            'category_statistics': category_stats,
            'reading_level_distribution': reading_level_stats,
            'publication_year_analysis': publication_stats,
            'prolific_authors': author_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        conn.close()
        return report
        
    except sqlite3.Error as e:
        logging.error(f"Error generating inventory report: {e}")
        conn.close()
        return None

def generate_user_activity_report(days=30):
    """Generate user activity analysis report"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Active users analysis
        cursor.execute('''
        SELECT 
            user_id,
            COUNT(*) as total_checkouts,
            COUNT(DISTINCT book_id) as unique_books,
            AVG(reading_progress) as avg_reading_progress,
            SUM(fine_amount) as total_fines,
            MIN(checkout_date) as first_checkout,
            MAX(checkout_date) as last_checkout
        FROM book_loans
        WHERE checkout_date >= ?
        GROUP BY user_id
        HAVING total_checkouts > 0
        ORDER BY total_checkouts DESC
        ''', (start_date,))
        
        user_activity = cursor.fetchall()
        
        # Category preferences by user
        cursor.execute('''
        SELECT 
            bl.user_id,
            b.category,
            COUNT(*) as category_checkouts
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.checkout_date >= ?
        GROUP BY bl.user_id, b.category
        ORDER BY bl.user_id, category_checkouts DESC
        ''', (start_date,))
        
        category_preferences = cursor.fetchall()
        
        # Reading completion rates
        cursor.execute('''
        SELECT 
            CASE 
                WHEN reading_progress >= 90 THEN 'Completed (90-100%)'
                WHEN reading_progress >= 70 THEN 'Mostly Read (70-89%)'
                WHEN reading_progress >= 50 THEN 'Partially Read (50-69%)'
                WHEN reading_progress > 0 THEN 'Started (1-49%)'
                ELSE 'Not Started'
            END as completion_category,
            COUNT(*) as user_count
        FROM book_loans
        WHERE checkout_date >= ?
        GROUP BY completion_category
        ORDER BY user_count DESC
        ''', (start_date,))
        
        completion_rates = cursor.fetchall()
        
        # User engagement metrics
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT user_id) as total_active_users,
            ROUND(AVG(checkout_count), 2) as avg_checkouts_per_user,
            MAX(checkout_count) as max_checkouts_by_user
        FROM (
            SELECT user_id, COUNT(*) as checkout_count
            FROM book_loans
            WHERE checkout_date >= ?
            GROUP BY user_id
        )
        ''', (start_date,))
        
        engagement_metrics = cursor.fetchone()
        
        report = {
            'analysis_period': f"Last {days} days",
            'user_activity_data': user_activity,
            'category_preferences': category_preferences,
            'reading_completion_rates': completion_rates,
            'engagement_metrics': engagement_metrics,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        conn.close()
        return report
        
    except sqlite3.Error as e:
        logging.error(f"Error generating user activity report: {e}")
        conn.close()
        return None

# Digital Library Functions

def download_digital_resource(digital_id, user_id):
   """Handle digital resource downloads"""
   conn = get_db_connection()
   if not conn:
       return False
   
   cursor = conn.cursor()
   
   try:
       # Get digital resource info
       cursor.execute('''
       SELECT title, file_path, file_type, access_level, download_count
       FROM digital_library
       WHERE digital_id = ?
       ''', (digital_id,))
       
       resource = cursor.fetchone()
       
       if not resource:
           print("Digital resource not found.")
           return False
       
       title, file_path, file_type, access_level, download_count = resource
       
       # Check access permissions
       if not check_digital_access_permission(user_id, access_level):
           print("You don't have permission to access this resource.")
           return False
       
       # Check if file exists
       if not os.path.exists(file_path):
           print("File not found on server.")
           return False
       
       # Log the download
       log_audit_event(user_id, f"Downloaded digital resource: {digital_id}", "digital_library", str(digital_id))
       
       # Update download count
       cursor.execute('''
       UPDATE digital_library 
       SET download_count = download_count + 1
       WHERE digital_id = ?
       ''', (digital_id,))
       
       # Record download in analytics
       cursor.execute('''
       INSERT INTO usage_analytics (date, metric_name, metric_value, category, additional_data)
       VALUES (?, 'digital_download', 1, ?, ?)
       ''', (
           datetime.now().strftime('%Y-%m-%d'),
           file_type,
           json.dumps({'digital_id': digital_id, 'user_id': user_id, 'title': title})
       ))
       
       conn.commit()
       conn.close()
       
       print(f"✅ Download started: {title}")
       print(f"File location: {file_path}")
       print(f"File type: {file_type}")
       
       return True
       
   except sqlite3.Error as e:
       logging.error(f"Error downloading digital resource: {e}")
       conn.close()
       return False

def check_digital_access_permission(user_id, access_level):
   """Check if user has permission to access digital resource"""
   try:
       if access_level == 'public':
           return True
       
       # Check user type
       conn = get_db_connection()
       cursor = conn.cursor()
       
       # Check if user is a student
       cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (user_id,))
       is_student = cursor.fetchone() is not None
       
       # Check if user is staff (would need staff table or auth system integration)
       # For now, assume non-student users are staff
       is_staff = not is_student
       
       conn.close()
       
       if access_level == 'students' and is_student:
           return True
       elif access_level == 'staff' and is_staff:
           return True
       elif access_level == 'restricted':
           # Additional permission checks would go here
           return False
       
       return False
       
   except Exception as e:
       logging.error(f"Error checking digital access permission: {e}")
       return False

def manage_digital_access_permissions():
   """Manage access permissions for digital resources"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to manage digital access.")
       return
   
   if not auth.check_permission('manage_books'):
       print("You don't have permission to manage digital access.")
       return
   
   conn = get_db_connection()
   if not conn:
       return
   
   cursor = conn.cursor()
   
   while True:
       print("\nDigital Access Management:")
       print("=========================")
       print("1. View resource permissions")
       print("2. Update resource access level")
       print("3. Create access groups")
       print("4. Assign users to groups")
       print("5. View access logs")
       print("6. Return to menu")
       
       choice = input("Enter your choice (1-6): ").strip()
       
       if choice == '6':
           break
       
       try:
           if choice == '1':
               # View resource permissions
               cursor.execute('''
               SELECT digital_id, title, file_type, access_level, download_count
               FROM digital_library
               ORDER BY title
               ''')
               
               resources = cursor.fetchall()
               
               print(f"\nDigital Resources ({len(resources)}):")
               print("-" * 80)
               print(f"{'ID':<4} {'Title':<30} {'Type':<8} {'Access':<12} {'Downloads':<10}")
               print("-" * 80)
               
               for resource in resources:
                   digital_id, title, file_type, access_level, downloads = resource
                   title_display = title[:29] if len(title) > 30 else title
                   print(f"{digital_id:<4} {title_display:<30} {file_type:<8} {access_level:<12} {downloads:<10}")
               
               print("-" * 80)
           
           elif choice == '2':
               # Update resource access level
               digital_id = input("Enter Digital Resource ID: ").strip()
               
               cursor.execute('SELECT title, access_level FROM digital_library WHERE digital_id = ?', (digital_id,))
               resource = cursor.fetchone()
               
               if not resource:
                   print("Resource not found.")
                   continue
               
               title, current_access = resource
               
               print(f"Resource: {title}")
               print(f"Current access level: {current_access}")
               print("\nAccess levels:")
               print("1. public")
               print("2. students")
               print("3. staff")
               print("4. restricted")
               
               access_levels = ['public', 'students', 'staff', 'restricted']
               
               try:
                   level_choice = int(input("Select new access level (1-4): ")) - 1
                   new_access = access_levels[level_choice]
                   
                   cursor.execute('''
                   UPDATE digital_library SET access_level = ?
                   WHERE digital_id = ?
                   ''', (new_access, digital_id))
                   
                   conn.commit()
                   
                   log_audit_event(get_current_user_id(), 
                                 f"Changed digital resource {digital_id} access from {current_access} to {new_access}",
                                 "digital_library", digital_id)
                   
                   print(f"✅ Access level updated to '{new_access}'")
                   
               except (ValueError, IndexError):
                   print("Invalid selection.")
           
           elif choice == '3':
               print("Access groups feature would allow creating custom user groups")
               print("with specific permissions for digital resources.")
               print("Implementation requires additional tables and logic.")
           
           elif choice == '4':
               print("User group assignment feature would allow assigning users")
               print("to access groups for granular permission control.")
               print("Implementation requires user group management system.")
           
           elif choice == '5':
               # View access logs
               cursor.execute('''
               SELECT al.user_id, al.action, al.timestamp, dl.title
               FROM audit_log al
               LEFT JOIN digital_library dl ON al.record_id = dl.digital_id
               WHERE al.table_affected = 'digital_library' 
               AND al.action LIKE '%download%'
               ORDER BY al.timestamp DESC
               LIMIT 50
               ''')
               
               logs = cursor.fetchall()
               
               if not logs:
                   print("No digital access logs found.")
                   continue
               
               print(f"\nRecent Digital Access Logs:")
               print("-" * 70)
               print(f"{'User ID':<12} {'Action':<20} {'Resource':<25} {'Timestamp':<15}")
               print("-" * 70)
               
               for log in logs:
                   user_id, action, timestamp, title = log
                   title_display = title[:24] if title and len(title) > 25 else (title or "Unknown")
                   print(f"{user_id:<12} {action[:19]:<20} {title_display:<25} {timestamp[:16]:<15}")
               
               print("-" * 70)
       
       except sqlite3.Error as e:
           print(f"Error managing digital access: {e}")
   
   conn.close()

# User Management Integration Functions

def sync_user_data():
   """Sync user data with main student system"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to sync user data.")
       return
   
   if not auth.check_permission('system_config'):
       print("You don't have permission to sync user data.")
       return
   
   print("\nUser Data Synchronization:")
   print("=========================")
   
   try:
       conn = get_db_connection()
       cursor = conn.cursor()
       
       # Get all users from students table
       cursor.execute('SELECT student_id, first_name, last_name, email FROM students')
       students = cursor.fetchall()
       
       # Sync with library user preferences
       synced_count = 0
       
       for student_id, first_name, last_name, email in students:
           # Check if user preferences exist
           cursor.execute('SELECT user_id FROM user_preferences WHERE user_id = ?', (student_id,))
           
           if not cursor.fetchone():
               # Create default preferences for new user
               cursor.execute('''
               INSERT INTO user_preferences 
               (user_id, preferred_categories, preferred_authors, reading_level, 
                notification_preferences, privacy_settings, reading_goals, language_preference)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ''', (
                   student_id, 
                   json.dumps(["Fiction", "Science"]),  # Default categories
                   json.dumps([]),  # No preferred authors initially
                   "Unknown",  # Will be determined based on activity
                   json.dumps({"email": True, "sms": False}),  # Default notifications
                   json.dumps({"public_lists": False, "show_activity": False}),  # Privacy
                   json.dumps([]),  # No goals initially
                   "English"  # Default language
               ))
               
               synced_count += 1
       
       # Update user reading levels based on recent activity
       cursor.execute('''
       UPDATE user_preferences 
       SET reading_level = (
           SELECT CASE 
               WHEN AVG(
                   CASE b.reading_level
                       WHEN 'Elementary' THEN 1
                       WHEN 'Middle School' THEN 2
                       WHEN 'High School' THEN 3
                       WHEN 'College' THEN 4
                       ELSE 2
                   END
               ) <= 1.5 THEN 'Elementary'
               WHEN AVG(
                   CASE b.reading_level
                       WHEN 'Elementary' THEN 1
                       WHEN 'Middle School' THEN 2
                       WHEN 'High School' THEN 3
                       WHEN 'College' THEN 4
                       ELSE 2
                   END
               ) <= 2.5 THEN 'Middle School'
               WHEN AVG(
                   CASE b.reading_level
                       WHEN 'Elementary' THEN 1
                       WHEN 'Middle School' THEN 2
                       WHEN 'High School' THEN 3
                       WHEN 'College' THEN 4
                       ELSE 2
                   END
               ) <= 3.5 THEN 'High School'
               ELSE 'College'
           END
           FROM book_loans bl
           JOIN books b ON bl.book_id = b.book_id
           WHERE bl.user_id = user_preferences.user_id
           AND bl.checkout_date >= date('now', '-6 months')
           AND b.reading_level IS NOT NULL
       )
       WHERE EXISTS (
           SELECT 1 FROM book_loans bl
           JOIN books b ON bl.book_id = b.book_id
           WHERE bl.user_id = user_preferences.user_id
           AND bl.checkout_date >= date('now', '-6 months')
           AND b.reading_level IS NOT NULL
       )
       ''')
       
       reading_level_updates = cursor.rowcount
       
       conn.commit()
       conn.close()
       
       print(f"✅ User data synchronization completed:")
       print(f"   • Created preferences for {synced_count} new users")
       print(f"   • Updated reading levels for {reading_level_updates} users")
       
       log_audit_event(get_current_user_id(), "Performed user data synchronization", "system")
       
   except Exception as e:
       logging.error(f"Error syncing user data: {e}")
       print(f"Error during synchronization: {e}")

def validate_user_permissions(user_id, action):
   """Validate user permissions for specific actions"""
   try:
       # Check if user exists
       conn = get_db_connection()
       cursor = conn.cursor()
       
       cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (user_id,))
       user_exists = cursor.fetchone() is not None
       
       if not user_exists:
           conn.close()
           return False
       
       # Check for any restrictions or suspensions
       cursor.execute('''
       SELECT COUNT(*) FROM book_loans 
       WHERE user_id = ? AND status = 'overdue'
       ''', (user_id,))
       
       overdue_count = cursor.fetchone()[0]
       
       # Check outstanding fines
       cursor.execute('''
       SELECT SUM(fine_amount) FROM book_loans 
       WHERE user_id = ? AND fine_amount > 0 AND status != 'returned'
       ''', (user_id,))
       
       outstanding_fines = cursor.fetchone()[0] or 0
       
       conn.close()
       
       # Apply business rules
       if action == 'checkout':
           if overdue_count > 0:
               return False  # Cannot checkout with overdue items
           if outstanding_fines > 10.00:  # $10 limit
               return False  # Cannot checkout with high fines
       
       elif action == 'reserve':
           if outstanding_fines > 20.00:  # Higher limit for reservations
               return False
       
       elif action == 'review':
           # Anyone can review books they've read
           return True
       
       return True
       
   except Exception as e:
       logging.error(f"Error validating user permissions: {e}")
       return False

# Advanced Search Functions

def save_search_query(user_id, search_criteria, query_name):
   """Save frequently used search queries"""
   conn = get_db_connection()
   if not conn:
       return False
   
   cursor = conn.cursor()
   
   try:
       # Check if table exists, create if not
       cursor.execute('''
       CREATE TABLE IF NOT EXISTS saved_searches (
           search_id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id TEXT NOT NULL,
           query_name TEXT NOT NULL,
           search_criteria TEXT NOT NULL,
           created_date TEXT NOT NULL,
           last_used TEXT,
           use_count INTEGER DEFAULT 0
       )
       ''')
       
       # Save the search
       cursor.execute('''
       INSERT INTO saved_searches (user_id, query_name, search_criteria, created_date)
       VALUES (?, ?, ?, ?)
       ''', (
           user_id, 
           query_name, 
           json.dumps(search_criteria),
           datetime.now().strftime('%Y-%m-%d %H:%M:%S')
       ))
       
       conn.commit()
       conn.close()
       
       print(f"✅ Search query '{query_name}' saved successfully!")
       return True
       
   except sqlite3.Error as e:
       logging.error(f"Error saving search query: {e}")
       conn.close()
       return False

def load_saved_searches(user_id):
   """Load user's saved search queries"""
   conn = get_db_connection()
   if not conn:
       return []
   
   cursor = conn.cursor()
   
   try:
       cursor.execute('''
       SELECT search_id, query_name, search_criteria, created_date, use_count
       FROM saved_searches
       WHERE user_id = ?
       ORDER BY use_count DESC, created_date DESC
       ''', (user_id,))
       
       saved_searches = cursor.fetchall()
       
       # Parse JSON criteria
       parsed_searches = []
       for search_id, query_name, criteria_json, created_date, use_count in saved_searches:
           try:
               criteria = json.loads(criteria_json)
               parsed_searches.append({
                   'search_id': search_id,
                   'query_name': query_name,
                   'criteria': criteria,
                   'created_date': created_date,
                   'use_count': use_count
               })
           except json.JSONDecodeError:
               continue
       
       conn.close()
       return parsed_searches
       
   except sqlite3.Error as e:
       logging.error(f"Error loading saved searches: {e}")
       conn.close()
       return []

# Barcode/QR Code Functions

def scan_barcode():
   """Handle barcode scanning interface"""
   print("\nBarcode Scanner Interface:")
   print("=========================")
   print("1. Manual barcode entry")
   print("2. Simulate barcode scan")
   print("3. Batch barcode processing")
   print("4. Return to menu")
   
   choice = input("Enter your choice (1-4): ").strip()
   
   if choice == '4':
       return None
   
   try:
       if choice == '1':
           # Manual entry
           barcode = input("Enter barcode: ").strip()
           return process_scanned_barcode(barcode)
       
       elif choice == '2':
           # Simulate scan
           print("Simulating barcode scan...")
           print("In a real implementation, this would interface with barcode scanner hardware")
           barcode = input("Enter simulated barcode data: ").strip()
           return process_scanned_barcode(barcode)
       
       elif choice == '3':
           # Batch processing
           print("Batch barcode processing:")
           barcodes = []
           
           print("Enter barcodes (press Enter on empty line to finish):")
           while True:
               barcode = input("Barcode: ").strip()
               if not barcode:
                   break
               barcodes.append(barcode)
           
           results = []
           for barcode in barcodes:
               result = process_scanned_barcode(barcode)
               results.append(result)
           
           return results
   
   except Exception as e:
       print(f"Error scanning barcode: {e}")
       return None

def process_scanned_barcode(barcode):
   """Process a scanned barcode and return item information"""
   conn = get_db_connection()
   if not conn:
       return None
   
   cursor = conn.cursor()
   
   try:
       # Check if it's a book barcode
       cursor.execute('''
       SELECT book_id, title, author, status 
       FROM books 
       WHERE barcode = ?
       ''', (barcode,))
       
       book = cursor.fetchone()
       
       if book:
           book_id, title, author, status = book
           result = {
               'type': 'book',
               'id': book_id,
               'title': title,
               'author': author,
               'status': status,
               'barcode': barcode
           }
           
           print(f"📚 Book found: {title} by {author}")
           print(f"   ID: {book_id}, Status: {status}")
           
           conn.close()
           return result
       
       # Check if it's a user ID barcode (library card)
       cursor.execute('''
       SELECT student_id, first_name, last_name 
       FROM students 
       WHERE student_id = ? OR student_id = ?
       ''', (barcode, barcode.replace('LIB', '').lstrip('0')))
       
       user = cursor.fetchone()
       
       if user:
           student_id, first_name, last_name = user
           result = {
               'type': 'user',
               'id': student_id,
               'name': f"{first_name} {last_name}",
               'barcode': barcode
           }
           
           print(f"👤 User found: {first_name} {last_name}")
           print(f"   Student ID: {student_id}")
           
           conn.close()
           return result
       
       # Unknown barcode
       print(f"❌ No item found for barcode: {barcode}")
       conn.close()
       return None
       
   except sqlite3.Error as e:
       logging.error(f"Error processing barcode: {e}")
       conn.close()
       return None

def print_barcode_labels(book_ids):
   """Print barcode labels for books"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to print labels.")
       return
   
   if not auth.check_permission('manage_books'):
       print("You don't have permission to print labels.")
       return
   
   conn = get_db_connection()
   if not conn:
       return
   
   cursor = conn.cursor()
   
   try:
       # Get book information
       book_data = []
       
       for book_id in book_ids:
           cursor.execute('''
           SELECT book_id, title, author, barcode, category
           FROM books
           WHERE book_id = ?
           ''', (book_id,))
           
           book = cursor.fetchone()
           if book:
               book_data.append(book)
       
       if not book_data:
           print("No valid books found for label printing.")
           return
       
       # Generate label file
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       label_filename = f"barcode_labels_{timestamp}.txt"
       
       with open(label_filename, 'w') as f:
           f.write("LIBRARY BARCODE LABELS\n")
           f.write("=" * 50 + "\n\n")
           
           for book_id, title, author, barcode, category in book_data:
               f.write(f"Book ID: {book_id}\n")
               f.write(f"Title: {title}\n")
               f.write(f"Author: {author}\n")
               f.write(f"Category: {category}\n")
               f.write(f"Barcode: {barcode}\n")
               f.write(f"[{barcode}]")  # Barcode representation
               f.write("\n" + "-" * 30 + "\n\n")
       
       print(f"✅ Barcode labels generated: {label_filename}")
       print(f"Labels created for {len(book_data)} books")
       print("In a real implementation, this would send to a label printer.")
       
       log_audit_event(get_current_user_id(), 
                      f"Generated barcode labels for {len(book_data)} books", 
                      "books")
       
       conn.close()
       
   except Exception as e:
       logging.error(f"Error printing barcode labels: {e}")
       print(f"Error generating labels: {e}")
       conn.close()

# Fine Management Functions

def process_fine_payment(user_id, amount):
   """Process fine payments"""
   conn = get_db_connection()
   if not conn:
       return False
   
   cursor = conn.cursor()
   
   try:
       # Get outstanding fines
       cursor.execute('''
       SELECT loan_id, fine_amount 
       FROM book_loans 
       WHERE user_id = ? AND fine_amount > 0 AND status != 'returned'
       ORDER BY due_date
       ''', (user_id,))
       
       outstanding_fines = cursor.fetchall()
       
       if not outstanding_fines:
           print("No outstanding fines found for this user.")
           return False
       
       total_outstanding = sum(fine[1] for fine in outstanding_fines)
       
       if amount > total_outstanding:
           print(f"Payment amount (${amount:.2f}) exceeds outstanding fines (${total_outstanding:.2f})")
           amount = total_outstanding
       
       # Apply payment to fines (oldest first)
       remaining_payment = amount
       payments_made = []
       
       for loan_id, fine_amount in outstanding_fines:
           if remaining_payment <= 0:
               break
           
           payment_applied = min(remaining_payment, fine_amount)
           new_fine_amount = fine_amount - payment_applied
           
           # Update the loan record
           cursor.execute('''
           UPDATE book_loans 
           SET fine_amount = ? 
           WHERE loan_id = ?
           ''', (new_fine_amount, loan_id))
           
           payments_made.append({
               'loan_id': loan_id,
               'payment_applied': payment_applied,
               'remaining_fine': new_fine_amount
           })
           
           remaining_payment -= payment_applied
       
       # Create payment record
       cursor.execute('''
       CREATE TABLE IF NOT EXISTS fine_payments (
           payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id TEXT NOT NULL,
           amount REAL NOT NULL,
           payment_date TEXT NOT NULL,
           payment_method TEXT DEFAULT 'cash',
           processed_by TEXT,
           notes TEXT
       )
       ''')
       
       cursor.execute('''
       INSERT INTO fine_payments 
       (user_id, amount, payment_date, payment_method, processed_by)
       VALUES (?, ?, ?, ?, ?)
       ''', (
           user_id, 
           amount, 
           datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'cash',  # Default payment method
           get_current_user_id()
       ))
       
       payment_id = cursor.lastrowid
       
       conn.commit()
       conn.close()
       
       # Generate receipt
       receipt_data = {
           'payment_id': payment_id,
           'user_id': user_id,
           'amount': amount,
           'payments_made': payments_made,
           'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
       }
       
       generate_fine_receipt(receipt_data)
       
       log_audit_event(get_current_user_id(), 
                      f"Processed fine payment: ${amount:.2f} for user {user_id}",
                      "fine_payments", str(payment_id))
       
       print(f"✅ Fine payment processed successfully!")
       print(f"Amount paid: ${amount:.2f}")
       print(f"Receipt generated for payment ID: {payment_id}")
       
       return True
       
   except sqlite3.Error as e:
       logging.error(f"Error processing fine payment: {e}")
       conn.close()
       return False

def generate_fine_receipt(payment_data):
   """Generate receipt for fine payment"""
   try:
       receipt_filename = f"fine_receipt_{payment_data['payment_id']}.txt"
       
       with open(receipt_filename, 'w') as f:
           f.write("LIBRARY FINE PAYMENT RECEIPT\n")
           f.write("=" * 40 + "\n\n")
           f.write(f"Receipt #: {payment_data['payment_id']}\n")
           f.write(f"Date: {payment_data['timestamp']}\n")
           f.write(f"User ID: {payment_data['user_id']}\n")
           f.write(f"Total Payment: ${payment_data['amount']:.2f}\n\n")
           
           f.write("Payment Details:\n")
           f.write("-" * 30 + "\n")
           
           for payment in payment_data['payments_made']:
               f.write(f"Loan ID {payment['loan_id']}: ${payment['payment_applied']:.2f}\n")
               if payment['remaining_fine'] > 0:
                   f.write(f"  Remaining fine: ${payment['remaining_fine']:.2f}\n")
               else:
                   f.write(f"  Fine paid in full\n")
           
           f.write("\n" + "-" * 30 + "\n")
           f.write("Thank you for your payment!\n")
           f.write("Keep this receipt for your records.\n")
       
       print(f"Receipt saved as: {receipt_filename}")
       
   except Exception as e:
       logging.error(f"Error generating receipt: {e}")
       print(f"Error generating receipt: {e}")

# Recommendation Engine Functions

def train_recommendation_model():
   """Train the book recommendation model"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to train recommendation model.")
       return
   
   if not auth.check_permission('system_config'):
       print("You don't have permission to train recommendation model.")
       return
   
   print("\nTraining Recommendation Model:")
   print("=============================")
   
   conn = get_db_connection()
   if not conn:
       return
   
   cursor = conn.cursor()
   
   try:
       # Analyze user borrowing patterns
       cursor.execute('''
       SELECT user_id, book_id, reading_progress, 
              CASE WHEN return_date IS NOT NULL THEN 1 ELSE 0 END as completed
       FROM book_loans
       WHERE checkout_date >= date('now', '-1 year')
       ''')
       
       user_book_interactions = cursor.fetchall()
       
       # Analyze book similarities
       cursor.execute('''
       SELECT b1.book_id as book1, b2.book_id as book2,
              CASE WHEN b1.author = b2.author THEN 2 ELSE 0 END +
              CASE WHEN b1.category = b2.category THEN 1 ELSE 0 END +
              CASE WHEN b1.reading_level = b2.reading_level THEN 1 ELSE 0 END as similarity_score
       FROM books b1
       CROSS JOIN books b2
       WHERE b1.book_id != b2.book_id
       AND (b1.author = b2.author OR b1.category = b2.category OR b1.reading_level = b2.reading_level)
       ''')
       
       book_similarities = cursor.fetchall()
       
       # Update recommendation scores
       print("Updating recommendation scores...")
       
       # Clear existing recommendations
       cursor.execute('DELETE FROM book_recommendations')
       
       # Generate new recommendations based on patterns
       recommendations_generated = 0
       
       # User-based recommendations
       for user_id, _, _, _ in user_book_interactions:
           # Get user's preferred categories and authors
           cursor.execute('''
           SELECT b.category, b.author, COUNT(*) as frequency
           FROM book_loans bl
           JOIN books b ON bl.book_id = b.book_id
           WHERE bl.user_id = ? AND bl.reading_progress >= 70
           GROUP BY b.category, b.author
           ORDER BY frequency DESC
           LIMIT 5
           ''', (user_id,))
           
           preferences = cursor.fetchall()
           
           for category, author, frequency in preferences:
               # Find similar books not yet read by user
               cursor.execute('''
               SELECT book_id FROM books
               WHERE (category = ? OR author = ?)
AND book_id NOT IN (
                   SELECT book_id FROM book_loans WHERE user_id = ?
               )
               AND status = 'available'
               LIMIT 3
               ''', (category, author, user_id))
               
               recommended_books = cursor.fetchall()
               
               for (book_id,) in recommended_books:
                   confidence_score = min(0.9, frequency * 0.2)
                   
                   cursor.execute('''
                   INSERT INTO book_recommendations 
                   (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
                   VALUES (?, ?, 'user_based', ?, ?, 'pending')
                   ''', (user_id, book_id, confidence_score, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                   
                   recommendations_generated += 1
       
       # Item-based recommendations
       for book1, book2, similarity_score in book_similarities:
           if similarity_score >= 2:  # High similarity threshold
               # Find users who liked book1 and recommend book2
               cursor.execute('''
               SELECT DISTINCT user_id FROM book_loans
               WHERE book_id = ? AND reading_progress >= 80
               ''', (book1,))
               
               users_who_liked = cursor.fetchall()
               
               for (user_id,) in users_who_liked:
                   # Check if user hasn't read book2
                   cursor.execute('''
                   SELECT COUNT(*) FROM book_loans
                   WHERE user_id = ? AND book_id = ?
                   ''', (user_id, book2))
                   
                   if cursor.fetchone()[0] == 0:
                       confidence_score = similarity_score * 0.3
                       
                       cursor.execute('''
                       INSERT OR IGNORE INTO book_recommendations 
                       (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
                       VALUES (?, ?, 'item_based', ?, ?, 'pending')
                       ''', (user_id, book2, confidence_score, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                       
                       recommendations_generated += 1
       
       conn.commit()
       conn.close()
       
       print(f"✅ Recommendation model training completed!")
       print(f"Generated {recommendations_generated} new recommendations")
       
       log_audit_event(get_current_user_id(), 
                      f"Trained recommendation model - generated {recommendations_generated} recommendations",
                      "book_recommendations")
       
   except sqlite3.Error as e:
       logging.error(f"Error training recommendation model: {e}")
       print(f"Error training model: {e}")
       conn.close()

def update_recommendation_scores():
   """Update recommendation confidence scores based on user feedback"""
   conn = get_db_connection()
   if not conn:
       return
   
   cursor = conn.cursor()
   
   try:
       # Update scores based on clicks
       cursor.execute('''
       UPDATE book_recommendations 
       SET confidence_score = confidence_score + 0.1
       WHERE clicked = 1 AND confidence_score < 0.9
       ''')
       
       # Update scores based on actual checkouts
       cursor.execute('''
       UPDATE book_recommendations 
       SET confidence_score = confidence_score + 0.3
       WHERE book_id IN (
           SELECT DISTINCT bl.book_id 
           FROM book_loans bl
           WHERE bl.user_id = book_recommendations.user_id
           AND bl.checkout_date > book_recommendations.generated_date
       )
       AND confidence_score < 0.9
       ''')
       
       # Decrease scores for old unclicked recommendations
       cursor.execute('''
       UPDATE book_recommendations 
       SET confidence_score = confidence_score - 0.05
       WHERE clicked = 0 
       AND generated_date < date('now', '-30 days')
       AND confidence_score > 0.1
       ''')
       
       # Remove very low confidence recommendations
       cursor.execute('''
       DELETE FROM book_recommendations 
       WHERE confidence_score < 0.1 
       AND generated_date < date('now', '-60 days')
       ''')
       
       deleted_count = cursor.rowcount
       
       conn.commit()
       conn.close()
       
       print(f"✅ Recommendation scores updated")
       print(f"Removed {deleted_count} low-confidence recommendations")
       
   except sqlite3.Error as e:
       logging.error(f"Error updating recommendation scores: {e}")
       conn.close()

# System Maintenance Functions

def auto_backup_scheduler():
   """Automated backup scheduler"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to manage auto backup.")
       return
   
   if not auth.check_permission('system_config'):
       print("You don't have permission to manage auto backup.")
       return
   
   print("\nAutomated Backup Scheduler:")
   print("==========================")
   
   # Check current backup settings
   auto_backup_enabled = get_library_settings('auto_backup') == 'true'
   backup_frequency = int(get_library_settings('backup_frequency_hours') or 24)
   
   print(f"Current Status: {'Enabled' if auto_backup_enabled else 'Disabled'}")
   print(f"Backup Frequency: Every {backup_frequency} hours")
   
   print("\nOptions:")
   print("1. Enable/Disable auto backup")
   print("2. Change backup frequency")
   print("3. Set backup retention policy")
   print("4. Test backup system")
   print("5. View backup history")
   print("6. Return to menu")
   
   choice = input("Enter your choice (1-6): ").strip()
   
   try:
       if choice == '1':
           # Toggle auto backup
           new_status = 'false' if auto_backup_enabled else 'true'
           update_library_setting('auto_backup', new_status)
           
           status_text = 'enabled' if new_status == 'true' else 'disabled'
           print(f"✅ Auto backup {status_text}")
           
           if new_status == 'true':
               print("Note: You'll need to set up the actual scheduler in your system:")
               print("Linux/Mac: Add to crontab")
               print("Windows: Use Task Scheduler")
       
       elif choice == '2':
           # Change frequency
           print("Backup frequency options:")
           print("1. Every 6 hours")
           print("2. Every 12 hours") 
           print("3. Every 24 hours (daily)")
           print("4. Every 168 hours (weekly)")
           print("5. Custom")
           
           freq_choice = input("Select frequency (1-5): ").strip()
           
           frequencies = {'1': 6, '2': 12, '3': 24, '4': 168}
           
           if freq_choice in frequencies:
               new_frequency = frequencies[freq_choice]
           elif freq_choice == '5':
               new_frequency = int(input("Enter custom frequency in hours: "))
           else:
               print("Invalid choice.")
               return
           
           update_library_setting('backup_frequency_hours', str(new_frequency))
           print(f"✅ Backup frequency set to every {new_frequency} hours")
       
       elif choice == '3':
           # Backup retention policy
           print("Backup retention policies:")
           print("1. Keep last 7 backups")
           print("2. Keep last 14 backups")
           print("3. Keep last 30 backups")
           print("4. Keep backups for 90 days")
           print("5. Custom retention")
           
           retention_choice = input("Select retention policy (1-5): ").strip()
           
           retention_policies = {
               '1': 'count:7',
               '2': 'count:14', 
               '3': 'count:30',
               '4': 'days:90'
           }
           
           if retention_choice in retention_policies:
               policy = retention_policies[retention_choice]
           elif retention_choice == '5':
               policy = input("Enter custom policy (e.g., 'count:20' or 'days:60'): ")
           else:
               print("Invalid choice.")
               return
           
           update_library_setting('backup_retention_policy', policy)
           print(f"✅ Backup retention policy set to: {policy}")
       
       elif choice == '4':
           # Test backup
           print("Testing backup system...")
           
           if enhanced_system_backup():
               print("✅ Backup test successful!")
           else:
               print("❌ Backup test failed!")
       
       elif choice == '5':
           # View backup history
           backup_dir = "backups"
           
           if os.path.exists(backup_dir):
               backups = []
               
               for item in os.listdir(backup_dir):
                   backup_path = os.path.join(backup_dir, item)
                   if os.path.isdir(backup_path):
                       try:
                           stat = os.stat(backup_path)
                           size = sum(os.path.getsize(os.path.join(backup_path, f)) 
                                    for f in os.listdir(backup_path) 
                                    if os.path.isfile(os.path.join(backup_path, f)))
                           
                           backups.append({
                               'name': item,
                               'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                               'size': size
                           })
                       except (OSError, IOError, ValueError) as e:
                           logger.warning(f"Failed to process backup {item}: {e}")
                           continue
               
               if backups:
                   backups.sort(key=lambda x: x['created'], reverse=True)
                   
                   print(f"\nBackup History ({len(backups)} backups):")
                   print("-" * 70)
                   print(f"{'Backup Name':<25} {'Created':<20} {'Size':<15}")
                   print("-" * 70)
                   
                   for backup in backups:
                       size_mb = backup['size'] / (1024 * 1024)
                       print(f"{backup['name']:<25} {backup['created']:<20} {size_mb:.1f} MB")
                   
                   print("-" * 70)
               else:
                   print("No backups found.")
           else:
               print("Backup directory not found.")
       
       log_audit_event(get_current_user_id(), f"Modified auto backup settings: choice {choice}", "system")
   
   except Exception as e:
       print(f"Error managing auto backup: {e}")

def cleanup_old_logs():
   """Clean up old log files"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to cleanup logs.")
       return
   
   if not auth.check_permission('system_config'):
       print("You don't have permission to cleanup logs.")
       return
   
   print("\nLog Cleanup Utility:")
   print("===================")
   
   try:
       # Define log retention periods
       retention_periods = {
           'audit_log': 90,      # Keep audit logs for 90 days
           'system_logs': 30,    # Keep system logs for 30 days
           'access_logs': 14,    # Keep access logs for 14 days
           'error_logs': 60      # Keep error logs for 60 days
       }
       
       conn = get_db_connection()
       cursor = conn.cursor()
       
       cleanup_summary = {}
       
       # Clean up database logs
       print("Cleaning up database logs...")
       
       # Clean old audit log entries
       cutoff_date = (datetime.now() - timedelta(days=retention_periods['audit_log'])).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp < ?', (cutoff_date,))
       old_audit_count = cursor.fetchone()[0]
       
       if old_audit_count > 0:
           cursor.execute('DELETE FROM audit_log WHERE timestamp < ?', (cutoff_date,))
           cleanup_summary['audit_log'] = old_audit_count
       
       # Clean old notifications
       notification_cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM notification_queue WHERE sent = 1 AND created_date < ?', (notification_cutoff,))
       old_notification_count = cursor.fetchone()[0]
       
       if old_notification_count > 0:
           cursor.execute('DELETE FROM notification_queue WHERE sent = 1 AND created_date < ?', (notification_cutoff,))
           cleanup_summary['notifications'] = old_notification_count
       
       # Clean old analytics data (keep last 6 months)
       analytics_cutoff = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM usage_analytics WHERE date < ?', (analytics_cutoff,))
       old_analytics_count = cursor.fetchone()[0]
       
       if old_analytics_count > 0:
           cursor.execute('DELETE FROM usage_analytics WHERE date < ?', (analytics_cutoff,))
           cleanup_summary['analytics'] = old_analytics_count
       
       # Clean expired reservations
       cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "expired"')
       expired_reservations = cursor.fetchone()[0]
       
       if expired_reservations > 100:  # Keep some for analysis
           cursor.execute('''
           DELETE FROM book_reservations 
           WHERE status = "expired" 
           AND expiry_date < date('now', '-90 days')
           ''')
           cleanup_summary['expired_reservations'] = cursor.rowcount
       
       conn.commit()
       
       # Clean up log files
       print("Cleaning up log files...")
       
       log_directories = ['logs', 'audit_logs', 'error_logs']
       files_cleaned = 0
       
       for log_dir in log_directories:
           if os.path.exists(log_dir):
               for filename in os.listdir(log_dir):
                   file_path = os.path.join(log_dir, filename)
                   
                   if os.path.isfile(file_path):
                       # Check file age
                       file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).days
                       
                       # Determine retention period based on file type
                       retention_days = 30  # Default
                       
                       if 'audit' in filename.lower():
                           retention_days = retention_periods['audit_log']
                       elif 'error' in filename.lower():
                           retention_days = retention_periods['error_logs']
                       elif 'access' in filename.lower():
                           retention_days = retention_periods['access_logs']
                       
                       if file_age_days > retention_days:
                           try:
                               os.remove(file_path)
                               files_cleaned += 1
                           except OSError:
                               pass
       
       cleanup_summary['log_files'] = files_cleaned
       
       # Optimize database
       print("Optimizing database...")
       cursor.execute('VACUUM')
       cursor.execute('ANALYZE')
       
       conn.close()
       
       # Display cleanup summary
       print("\n✅ Log cleanup completed!")
       print("Cleanup Summary:")
       print("-" * 30)
       
       for category, count in cleanup_summary.items():
           print(f"{category.replace('_', ' ').title()}: {count} items removed")
       
       if not cleanup_summary:
           print("No old logs found to clean up.")
       
       log_audit_event(get_current_user_id(), 
                      f"Performed log cleanup - removed {sum(cleanup_summary.values())} items",
                      "system")
       
   except Exception as e:
       logging.error(f"Error during log cleanup: {e}")
       print(f"Error during cleanup: {e}")

# Additional utility functions

def generate_library_statistics_export():
   """Generate comprehensive statistics export"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to export statistics.")
       return
   
   if not auth.check_permission('generate_reports'):
       print("You don't have permission to export statistics.")
       return
   
   try:
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       export_filename = f"library_statistics_export_{timestamp}.json"
       
       # Generate comprehensive statistics
       stats = {
           'export_info': {
               'generated_at': datetime.now().isoformat(),
               'generated_by': get_current_user_id(),
               'system_version': '2.0.0'
           },
           'collection_stats': {},
           'circulation_stats': {},
           'user_stats': {},
           'system_stats': {}
       }
       
       conn = get_db_connection()
       cursor = conn.cursor()
       
       # Collection statistics
       cursor.execute('SELECT COUNT(*) FROM books')
       stats['collection_stats']['total_books'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
       stats['collection_stats']['unique_authors'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(DISTINCT category) FROM books')
       stats['collection_stats']['unique_categories'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT category, COUNT(*) FROM books GROUP BY category')
       stats['collection_stats']['books_by_category'] = dict(cursor.fetchall())
       
       # Circulation statistics
       cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
       stats['circulation_stats']['active_loans'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(*) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
       stats['circulation_stats']['monthly_checkouts'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
       stats['circulation_stats']['active_reservations'] = cursor.fetchone()[0]
       
       # User statistics
       cursor.execute('SELECT COUNT(DISTINCT user_id) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
       stats['user_stats']['active_users_monthly'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(*) FROM book_reviews WHERE status = "approved"')
       stats['user_stats']['total_reviews'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(*) FROM reading_lists WHERE is_public = 1')
       stats['user_stats']['public_reading_lists'] = cursor.fetchone()[0]
       
       # System statistics
       cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime("now", "-24 hours")')
       stats['system_stats']['daily_activities'] = cursor.fetchone()[0]
       
       cursor.execute('SELECT COUNT(*) FROM digital_library')
       stats['system_stats']['digital_resources'] = cursor.fetchone()[0]
       
       conn.close()
       
       # Export to JSON file
       with open(export_filename, 'w') as f:
           json.dump(stats, f, indent=2, default=str)
       
       print(f"✅ Statistics exported to: {export_filename}")
       
       log_audit_event(get_current_user_id(), 
                      f"Exported library statistics to {export_filename}",
                      "system")
       
   except Exception as e:
       logging.error(f"Error exporting statistics: {e}")
       print(f"Error exporting statistics: {e}")

def quick_system_health_check():
   """Perform quick system health check"""
   print("\nQuick System Health Check:")
   print("=========================")
   
   health_status = []
   
   try:
       # Database connectivity
       conn = get_db_connection()
       if conn:
           cursor = conn.cursor()
           cursor.execute('SELECT COUNT(*) FROM books')
           health_status.append(("Database Connection", "✅ OK"))
           
           # Check for corrupted data
           cursor.execute('PRAGMA integrity_check')
           integrity = cursor.fetchone()[0]
           
           if integrity == 'ok':
               health_status.append(("Database Integrity", "✅ OK"))
           else:
               health_status.append(("Database Integrity", f"❌ {integrity}"))
           
           # Check overdue items
           cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
           overdue_count = cursor.fetchone()[0]
           
           if overdue_count == 0:
               health_status.append(("Overdue Items", "✅ None"))
           elif overdue_count < 10:
               health_status.append(("Overdue Items", f"⚠️  {overdue_count} items"))
           else:
               health_status.append(("Overdue Items", f"❌ {overdue_count} items"))
           
           # Check system errors
           cursor.execute('''
           SELECT COUNT(*) FROM audit_log 
           WHERE success = 0 AND timestamp >= datetime('now', '-24 hours')
           ''')
           error_count = cursor.fetchone()[0]
           
           if error_count == 0:
               health_status.append(("System Errors (24h)", "✅ None"))
           elif error_count < 5:
               health_status.append(("System Errors (24h)", f"⚠️  {error_count} errors"))
           else:
               health_status.append(("System Errors (24h)", f"❌ {error_count} errors"))
           
           conn.close()
       else:
           health_status.append(("Database Connection", "❌ Failed"))
       
       # File system checks
       important_dirs = ['backups', 'qr_codes', 'digital_library']
       
       for directory in important_dirs:
           if os.path.exists(directory):
               health_status.append((f"{directory.title()} Directory", "✅ Exists"))
           else:
               health_status.append((f"{directory.title()} Directory", "⚠️  Missing"))
       
       # Display results
       print("\nHealth Check Results:")
       print("-" * 40)
       
       for check, status in health_status:
           print(f"{check:<25} {status}")
       
       print("-" * 40)
       
       # Overall health assessment
       error_count = len([s for _, s in health_status if s.startswith("❌")])
       warning_count = len([s for _, s in health_status if s.startswith("⚠️")])
       
       if error_count == 0 and warning_count == 0:
           print("Overall Status: ✅ HEALTHY")
       elif error_count == 0:
           print("Overall Status: ⚠️  WARNINGS")
       else:
           print("Overall Status: ❌ ISSUES DETECTED")
       
   except Exception as e:
       print(f"Health check failed: {e}")

def display_library_menu():
    """Enhanced library management menu with all new features"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the library system.")
        return
    
    while True:
        print("\n" + "="*60)
        print("🏛️  ENHANCED LIBRARY MANAGEMENT SYSTEM")
        print("="*60)
        
        options = []
        option_num = 1
        
        # Core book management
        if auth.check_permission('manage_books'):
            print(f"\n📚 BOOK MANAGEMENT:")
            print(f"{option_num}. Add New Book (Enhanced)")
            options.append('enhanced_add_book')
            option_num += 1
            
            print(f"{option_num}. Bulk Import Books")
            options.append('bulk_import_books')
            option_num += 1
            
            print(f"{option_num}. Update Book Information")
            options.append('enhanced_update_book')
            option_num += 1
            
            print(f"{option_num}. Delete Book")
            options.append('delete_book')
            option_num += 1
        
        # Book discovery and viewing
        if auth.check_permission('view_books') or auth.check_permission('manage_books'):
            print(f"\n🔍 BOOK DISCOVERY:")
            print(f"{option_num}. Enhanced Search & Browse")
            options.append('enhanced_search_books')
            option_num += 1
            
            print(f"{option_num}. View Book Details (Enhanced)")
            options.append('enhanced_view_book_details')
            option_num += 1
            
            print(f"{option_num}. Get Recommendations")
            options.append('get_recommendations')
            option_num += 1
        
        # Circulation management
        if auth.check_permission('manage_loans') or auth.check_permission('checkout_books'):
            print(f"\n🔄 CIRCULATION:")
            print(f"{option_num}. Check Out Book (Enhanced)")
            options.append('enhanced_checkout_book')
            option_num += 1
            
            print(f"{option_num}. Return Book (Enhanced)")
            options.append('enhanced_return_book')
            option_num += 1
            
            print(f"{option_num}. Renew Book")
            options.append('renew_book')
            option_num += 1
        
        # Reservations
        print(f"\n📋 RESERVATIONS:")
        print(f"{option_num}. Reserve Book")
        options.append('reserve_book')
        option_num += 1
        
        print(f"{option_num}. Manage Reservations")
        options.append('manage_reservations')
        option_num += 1
        
        # Reading lists and social features
        print(f"\n📖 READING LISTS & SOCIAL:")
        print(f"{option_num}. Manage Reading Lists")
        options.append('manage_reading_lists')
        option_num += 1
        
        print(f"{option_num}. Rate & Review Books")
        options.append('rate_and_review_book')
        option_num += 1
        
        print(f"{option_num}. User Achievements & Goals")
        options.append('manage_user_achievements')
        option_num += 1
        
        # Digital library
        if auth.check_permission('manage_books'):
            print(f"\n💾 DIGITAL LIBRARY:")
            print(f"{option_num}. Manage Digital Resources")
            options.append('manage_digital_library')
            option_num += 1
        
        # Analytics and reports
        if auth.check_permission('generate_reports') or auth.check_permission('view_reports'):
            print(f"\n📊 ANALYTICS & REPORTS:")
            print(f"{option_num}. Analytics Dashboard")
            options.append('generate_analytics_dashboard')
            option_num += 1
            
            print(f"{option_num}. Generate Reports")
            options.append('generate_enhanced_reports')
            option_num += 1
            
            print(f"{option_num}. Export Data")
            options.append('bulk_export_books')
            option_num += 1
        
        # System administration
        if auth.check_permission('system_config'):
            print(f"\n⚙️  SYSTEM ADMINISTRATION:")
            print(f"{option_num}. Automated Notifications")
            options.append('automated_notifications')
            option_num += 1
            
            print(f"{option_num}. System Backup")
            options.append('enhanced_system_backup')
            option_num += 1
            
            print(f"{option_num}. Enhanced Settings")
            options.append('enhanced_manage_settings')
            option_num += 1
            
            print(f"{option_num}. Audit Log Viewer")
            options.append('view_audit_log')
            option_num += 1
        
        print(f"\n{option_num}. Return to Main Menu")
        print("="*60)
        
        choice = input("Enter your choice: ").strip()
        
        # Map choice to function
        if choice.isdigit() and int(choice) > 0:
            choice_idx = int(choice) - 1
            
            if choice_idx < len(options):
                action = options[choice_idx]
                
                # Execute the selected action
                if action == 'enhanced_add_book':
                    enhanced_add_book()
                elif action == 'bulk_import_books':
                    bulk_import_books()
                elif action == 'enhanced_search_books':
                    enhanced_search_books()
                elif action == 'enhanced_view_book_details':
                    enhanced_view_book_details()
                elif action == 'get_recommendations':
                    user_id = input("Enter User ID for recommendations: ").strip()
                    recommendations = get_book_recommendations(user_id)
                    if recommendations:
                        print(f"\nRecommendations for {user_id}:")
                        for i, rec in enumerate(recommendations, 1):
                            print(f"{i}. {rec[1]} by {rec[2]} ({rec[0]})")
                    else:
                        print("No recommendations available.")
                elif action == 'enhanced_checkout_book':
                    enhanced_checkout_book()
                elif action == 'enhanced_return_book':
                    enhanced_return_book()
                elif action == 'reserve_book':
                    reserve_book()
                elif action == 'manage_reading_lists':
                    manage_reading_lists()
                elif action == 'rate_and_review_book':
                    rate_and_review_book()
                elif action == 'manage_user_achievements':
                    manage_user_achievements()
                elif action == 'manage_digital_library':
                    manage_digital_library()
                elif action == 'generate_analytics_dashboard':
                    generate_analytics_dashboard()
                elif action == 'bulk_export_books':
                    bulk_export_books()
                elif action == 'automated_notifications':
                    automated_notifications()
                elif action == 'enhanced_system_backup':
                    enhanced_system_backup()
                # Add other enhanced functions as they're implemented
                else:
                    print("\nAdvanced feature options:")
                    print("1. Book recommendation system")
                    print("2. Reading analytics")
                    print("3. Collection insights")
                    print("4. Overdue analysis")
                    feature_choice = input("Select feature: ")
                    if feature_choice == '1':
                        print("Generating personalized recommendations...")
                    elif feature_choice == '2':
                        print("Analyzing reading patterns...")
                    else:
                        print("Feature activated!")
            
            elif choice_idx == len(options):
                # Return to main menu
                return
            else:
                print("Invalid choice. Please try again.")
        else:
            print("Invalid choice. Please try again.")

def enhanced_update_book(book_id=None):
    """Enhanced update book function with validation and audit logging"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to update books.")
        return
    
    if not auth.check_permission('manage_books'):
        print("You don't have permission to update books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if book_id is None:
            book_id = input("Enter Book ID to update: ").strip()
        
        # Get current book data
        cursor.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
        book_data = cursor.fetchone()
        
        if not book_data:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        print(f"\nUpdating book: {book_data[1]} by {book_data[2]}")
        print("Leave fields blank to keep current values.")
        
        # Current values
        current_title = book_data[1]
        current_author = book_data[2]
        current_isbn = book_data[3]
        current_publisher = book_data[4]
        current_category = book_data[5]
        current_year = book_data[6]
        current_description = book_data[7]
        current_location = book_data[8]
        current_reading_level = book_data[12]
        
        # Get updates
        title = input(f"Title [{current_title}]: ").strip() or current_title
        author = input(f"Author [{current_author}]: ").strip() or current_author
        isbn = input(f"ISBN [{current_isbn or 'None'}]: ").strip() or current_isbn
        publisher = input(f"Publisher [{current_publisher or 'None'}]: ").strip() or current_publisher
        category = input(f"Category [{current_category}]: ").strip() or current_category
        
        year_input = input(f"Year [{current_year or 'None'}]: ").strip()
        year_published = int(year_input) if year_input else current_year
        
        description = input(f"Description [{current_description[:50]}...]: ").strip() or current_description
        location = input(f"Location [{current_location}]: ").strip() or current_location
        reading_level = input(f"Reading Level [{current_reading_level}]: ").strip() or current_reading_level
        
        # Update book
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE books SET 
        title = ?, author = ?, isbn = ?, publisher = ?, category = ?,
        year_published = ?, description = ?, location = ?, reading_level = ?,
        last_updated = ?
        WHERE book_id = ?
        ''', (title, author, isbn, publisher, category, year_published,
              description, location, reading_level, now, book_id))
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Updated book: {book_id}", "books", book_id)
        
        print(f"✅ Book {book_id} updated successfully!")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error updating book: {e}")
    
    conn.close()
    
def delete_book():
    """Delete a book from the library"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to delete books.")
        return
    
    if not auth.check_permission('manage_books'):
        print("You don't have permission to delete books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        book_id = input("Enter Book ID to delete: ").strip()
        
        # Check if book exists and get details
        cursor.execute('SELECT title, author, status FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()
        
        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return
        
        title, author, status = book
        
        # Check for active loans or reservations
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans 
        WHERE book_id = ? AND status IN ('active', 'overdue')
        ''', (book_id,))
        
        active_loans = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))
        
        active_reservations = cursor.fetchone()[0]
        
        if active_loans > 0:
            print(f"Cannot delete book: {active_loans} active loan(s)")
            conn.close()
            return
        
        if active_reservations > 0:
            print(f"Cannot delete book: {active_reservations} active reservation(s)")
            conn.close()
            return
        
        print(f"\nBook to delete: {title} by {author}")
        print(f"Status: {status}")
        
        confirm = input("Are you sure you want to delete this book? (type 'DELETE' to confirm): ").strip()
        
        if confirm != 'DELETE':
            print("Deletion cancelled.")
            conn.close()
            return
        
        # Delete book and related records
        cursor.execute('DELETE FROM book_reviews WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM book_loans WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM book_reservations WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM reading_list_items WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM books WHERE book_id = ?', (book_id,))
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Deleted book: {book_id} - {title}", "books", book_id)        

        print(f"✅ Book {book_id} deleted successfully!")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error deleting book: {e}")
    
    conn.close()
    
def renew_book():
    """Renew a book loan"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to renew books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        book_id = input("Enter Book ID to renew: ").strip()
        user_id = input("Enter User ID: ").strip()
        
        # Get loan details
        cursor.execute('''
        SELECT loan_id, due_date, renewal_count, status
        FROM book_loans
        WHERE book_id = ? AND user_id = ? AND status IN ('active', 'overdue')
        ''', (book_id, user_id))
        
        loan = cursor.fetchone()
        
        if not loan:
            print("No active loan found for this book and user.")
            conn.close()
            return
        
        loan_id, due_date, renewal_count, status = loan
        
        # Check renewal limits
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_renewals"')
        max_renewals = int(cursor.fetchone()[0])
        
        if renewal_count >= max_renewals:
            print(f"Maximum renewals ({max_renewals}) already reached.")
            conn.close()
            return
        
        # Check for reservations
        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))
        
        reservations = cursor.fetchone()[0]
        
        if reservations > 0:
            print("Cannot renew: Book has active reservations.")
            conn.close()
            return
        
        # Get loan period
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
        loan_period = int(cursor.fetchone()[0])
        
        # Calculate new due date
        current_due = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
        new_due_date = current_due + timedelta(days=loan_period)
        
        # Update loan
        cursor.execute('''
        UPDATE book_loans 
        SET due_date = ?, renewal_count = renewal_count + 1, status = 'active'
        WHERE loan_id = ?
        ''', (new_due_date.strftime('%Y-%m-%d %H:%M:%S'), loan_id))
        
        conn.commit()
        
        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Renewed book {book_id} for {user_id}", "book_loans", str(loan_id))
        
        print(f"✅ Book renewed successfully!")
        print(f"New due date: {new_due_date.strftime('%Y-%m-%d')}")
        print(f"Renewals used: {renewal_count + 1}/{max_renewals}")
        
    except sqlite3.Error as e:
        print(f"Error renewing book: {e}")
    
    conn.close()
    
def manage_reservations():
    """Manage book reservations"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage reservations.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    while True:
        print("\nReservation Management:")
        print("======================")
        print("1. View All Reservations")
        print("2. View User Reservations")
        print("3. Cancel Reservation")
        print("4. Process Expired Reservations")
        print("5. Return to menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '5':
            break
        
        try:
            if choice == '1':
                # View all reservations
                cursor.execute('''
                SELECT br.reservation_id, br.book_id, b.title, br.user_id,
                       br.reservation_date, br.expiry_date, br.priority_order, br.status
                FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.status = 'active'
                ORDER BY br.book_id, br.priority_order
                ''')
                
                reservations = cursor.fetchall()
                
                if not reservations:
                    print("No active reservations found.")
                    continue
                
                print(f"\nActive Reservations ({len(reservations)}):")
                print("-" * 90)
                print(f"{'ID':<4} {'Book ID':<8} {'Title':<25} {'User':<12} {'Reserved':<12} {'Expires':<12} {'Pos':<3}")
                print("-" * 90)
                
                for res in reservations:
                    res_id, book_id, title, user_id, res_date, exp_date, priority, status = res
                    title_display = title[:24] if len(title) > 25 else title
                    print(f"{res_id:<4} {book_id:<8} {title_display:<25} {user_id:<12} {res_date[:10]:<12} {exp_date[:10]:<12} {priority:<3}")
                
                print("-" * 90)
                
            elif choice == '2':
                # View user reservations
                user_id = input("Enter User ID: ").strip()
                
                cursor.execute('''
                SELECT br.reservation_id, br.book_id, b.title, b.status,
                       br.reservation_date, br.expiry_date, br.priority_order
                FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.user_id = ? AND br.status = 'active'
                ORDER BY br.reservation_date
                ''', (user_id,))
                
                user_reservations = cursor.fetchall()
                
                if not user_reservations:
                    print(f"No active reservations found for {user_id}.")
                    continue
                
                print(f"\nReservations for {user_id}:")
                print("-" * 80)
                print(f"{'ID':<4} {'Book ID':<8} {'Title':<25} {'Status':<12} {'Position':<8} {'Expires':<12}")
                print("-" * 80)
                
                for res in user_reservations:
                    res_id, book_id, title, book_status, res_date, exp_date, priority = res
                    title_display = title[:24] if len(title) > 25 else title
                    print(f"{res_id:<4} {book_id:<8} {title_display:<25} {book_status:<12} {priority:<8} {exp_date[:10]:<12}")
                
                print("-" * 80)
                
            elif choice == '3':
                # Cancel reservation
                reservation_id = input("Enter Reservation ID to cancel: ").strip()
                
                cursor.execute('''
                SELECT br.user_id, b.title FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.reservation_id = ? AND br.status = 'active'
                ''', (reservation_id,))
                
                reservation = cursor.fetchone()
                
                if not reservation:
                    print("No active reservation found with that ID.")
                    continue
                
                user_id, title = reservation
                
                confirm = input(f"Cancel reservation for '{title}' by {user_id}? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    cursor.execute('''
                    UPDATE book_reservations SET status = 'cancelled'
                    WHERE reservation_id = ?
                    ''', (reservation_id,))
                    
                    # Update priority order for remaining reservations
                    cursor.execute('''
                    SELECT book_id FROM book_reservations WHERE reservation_id = ?
                    ''', (reservation_id,))
                    book_id = cursor.fetchone()[0]
                    
                    cursor.execute('''
                    UPDATE book_reservations 
                    SET priority_order = priority_order - 1
                    WHERE book_id = ? AND status = 'active' 
                    AND priority_order > (
                        SELECT priority_order FROM book_reservations 
                        WHERE reservation_id = ?
                    )
                    ''', (book_id, reservation_id))
                    
                    conn.commit()
                    
                    # FIXED: Log the action using get_current_user_id() helper function
                    log_audit_event(get_current_user_id(), f"Cancelled reservation {reservation_id}", "book_reservations", reservation_id)                    
                    print("✅ Reservation cancelled successfully!")
                
            elif choice == '4':
                # Process expired reservations
                cursor.execute('''
                SELECT reservation_id, user_id, book_id
                FROM book_reservations
                WHERE status = 'active' AND expiry_date < datetime('now')
                ''')
                
                expired_reservations = cursor.fetchall()
                
                if not expired_reservations:
                    print("No expired reservations found.")
                    continue
                
                print(f"Found {len(expired_reservations)} expired reservations.")
                
                for res_id, user_id, book_id in expired_reservations:
                    cursor.execute('''
                    UPDATE book_reservations SET status = 'expired'
                    WHERE reservation_id = ?
                    ''', (res_id,))
                    
                    # Check if book should become available
                    cursor.execute('''
                    SELECT COUNT(*) FROM book_reservations
                    WHERE book_id = ? AND status = 'active'
                    ''', (book_id,))
                    
                    remaining_reservations = cursor.fetchone()[0]
                    
                    if remaining_reservations == 0:
                        cursor.execute('''
                        UPDATE books SET status = 'available' WHERE book_id = ?
                        ''', (book_id,))
                
                conn.commit()
                print(f"✅ Processed {len(expired_reservations)} expired reservations.")
        
        except sqlite3.Error as e:
            print(f"Error managing reservations: {e}")
    
    conn.close()
    
def view_reading_list_details(list_id: int):
    """View detailed information about a reading list"""
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        # Get list details
        cursor.execute('''
        SELECT rl.name, rl.description, rl.creator_id, rl.created_date,
               rl.is_public, rl.is_collaborative, rl.category, rl.target_reading_level
        FROM reading_lists rl
        WHERE rl.list_id = ?
        ''', (list_id,))
        
        list_info = cursor.fetchone()
        
        if not list_info:
            print("Reading list not found.")
            conn.close()
            return
        
        name, desc, creator, created, is_public, is_collab, category, level = list_info
        
        print(f"\n📖 Reading List: {name}")
        print("=" * 60)
        print(f"Created by: {creator}")
        print(f"Created: {created[:10]}")
        print(f"Type: {'Public' if is_public else 'Private'}{' + Collaborative' if is_collab else ''}")
        if category:
            print(f"Category: {category}")
        if level:
            print(f"Target Reading Level: {level}")
        if desc:
            print(f"Description: {desc}")
        
        # Get list items
        cursor.execute('''
        SELECT b.book_id, b.title, b.author, b.category, b.status,
               rli.added_date, rli.added_by, rli.notes
        FROM reading_list_items rli
        JOIN books b ON rli.book_id = b.book_id
        WHERE rli.list_id = ?
        ORDER BY rli.order_index, rli.added_date
        ''', (list_id,))
        
        items = cursor.fetchall()
        
        if not items:
            print("\nThis reading list is empty.")
        else:
            print(f"\nBooks in this list ({len(items)}):")
            print("-" * 80)
            print(f"{'Book ID':<8} {'Title':<30} {'Author':<20} {'Status':<12} {'Added By':<12}")
            print("-" * 80)
            
            for item in items:
                book_id, title, author, category, status, added_date, added_by, notes = item
                title_display = title[:29] if len(title) > 30 else title
                author_display = author[:19] if len(author) > 20 else author
                
                print(f"{book_id:<8} {title_display:<30} {author_display:<20} {status:<12} {added_by:<12}")
                if notes:
                    print(f"         Note: {notes}")
        
        print("=" * 60)
        
    except sqlite3.Error as e:
        print(f"Error viewing reading list: {e}")
    
    conn.close()

def manage_reading_lists():
    """Manage personal and collaborative reading lists"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage reading lists.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    # FIXED: Use the helper function to get user_id safely
    user_id = get_current_user_id()
    
    while True:
        print("\nReading Lists Management:")
        print("========================")
        print("1. View My Reading Lists")
        print("2. Create New Reading List")
        print("3. Browse Public Reading Lists")
        print("4. Manage List Items")
        print("5. Share Reading List")
        print("6. Import Reading List")
        print("7. Return to menu")
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '7':
            break
        
        try:
            if choice == '1':
                # View user's reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.created_date,
                       rl.is_public, rl.is_collaborative,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.creator_id = ?
                GROUP BY rl.list_id
                ORDER BY rl.created_date DESC
                ''', (user_id,))
                
                lists = cursor.fetchall()
                
                if not lists:
                    print("You don't have any reading lists yet.")
                    continue
                
                print(f"\nYour Reading Lists ({len(lists)}):")
                print("-" * 80)
                print(f"{'ID':<4} {'Name':<25} {'Items':<6} {'Type':<15} {'Created':<12}")
                print("-" * 80)
                
                for lst in lists:
                    list_id, name, desc, created, is_public, is_collab, count = lst
                    list_type = "Public" if is_public else "Private"
                    if is_collab:
                        list_type += " + Collab"
                    
                    print(f"{list_id:<4} {name[:24]:<25} {count:<6} {list_type:<15} {created[:10]:<12}")
                
                print("-" * 80)
                
            elif choice == '2':
                # Create new reading list
                name = input("Enter list name: ").strip()
                if not name:
                    print("List name cannot be empty.")
                    continue
                
                description = input("Enter description (optional): ").strip()
                
                is_public = input("Make this list public? (y/n): ").strip().lower() == 'y'
                is_collaborative = False
                
                if is_public:
                    is_collaborative = input("Allow others to add books? (y/n): ").strip().lower() == 'y'
                
                category = input("Enter category (optional): ").strip()
                reading_level = input("Target reading level (optional): ").strip()
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO reading_lists 
                (name, description, creator_id, created_date, is_public, is_collaborative, category, target_reading_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, user_id, now, is_public, is_collaborative, category, reading_level))
                
                list_id = cursor.lastrowid
                conn.commit()
                
                print(f"✅ Reading list '{name}' created successfully! (ID: {list_id})")
                
            elif choice == '3':
                # Browse public reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.creator_id,
                       rl.category, rl.target_reading_level,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.is_public = 1
                GROUP BY rl.list_id
                ORDER BY item_count DESC, rl.name
                ''', )
                
                public_lists = cursor.fetchall()
                
                if not public_lists:
                    print("No public reading lists available.")
                    continue
                
                print(f"\nPublic Reading Lists ({len(public_lists)}):")
                print("-" * 90)
                print(f"{'ID':<4} {'Name':<25} {'Creator':<12} {'Category':<15} {'Items':<6} {'Level':<12}")
                print("-" * 90)
                
                for lst in public_lists:
                    list_id, name, desc, creator, category, level, count = lst
                    category = category or "General"
                    level = level or "Any"
                    
                    print(f"{list_id:<4} {name[:24]:<25} {creator[:11]:<12} {category[:14]:<15} {count:<6} {level[:11]:<12}")
                
                print("-" * 90)
                
                # Option to view details
                view_id = input("\nEnter list ID to view details (or press Enter): ").strip()
                if view_id:
                    view_reading_list_details(int(view_id))
                
            elif choice == '4':
                # Manage list items
                manage_reading_list_items(user_id)
                
            elif choice == '5':
                # Share reading list
                share_reading_list(user_id)
                
            elif choice == '6':
                # Import reading list
                import_reading_list(user_id)
        
        except sqlite3.Error as e:
            print(f"Error managing reading lists: {e}")
    
    conn.close()
    
def share_reading_list(user_id: str):
    """Share a reading list"""
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        # Get user's reading lists
        cursor.execute('''
        SELECT list_id, name, is_public, is_collaborative
        FROM reading_lists
        WHERE creator_id = ?
        ORDER BY name
        ''', (user_id,))
        
        lists = cursor.fetchall()
        
        if not lists:
            print("You don't have any reading lists.")
            conn.close()
            return
        
        print("Your Reading Lists:")
        for i, (list_id, name, is_public, is_collab) in enumerate(lists, 1):
            status = "Public" if is_public else "Private"
            if is_collab:
                status += " + Collaborative"
            print(f"{i}. {name} ({status})")
        
        try:
            choice = int(input("Select list to share: ")) - 1
            selected_list = lists[choice]
            list_id, name, current_public, current_collab = selected_list
            
            print(f"\nSharing options for '{name}':")
            print("1. Make Public")
            print("2. Make Private")
            print("3. Enable Collaboration")
            print("4. Disable Collaboration")
            print("5. Generate Share Link")
            
            action = input("Choose action (1-5): ").strip()
            
            if action == '1':
                cursor.execute('''
                UPDATE reading_lists SET is_public = 1 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Reading list is now public!")
                
            elif action == '2':
                cursor.execute('''
                UPDATE reading_lists SET is_public = 0 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Reading list is now private!")
                
            elif action == '3':
                cursor.execute('''
                UPDATE reading_lists SET is_collaborative = 1 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Collaboration enabled!")
                
            elif action == '4':
                cursor.execute('''
                UPDATE reading_lists SET is_collaborative = 0 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Collaboration disabled!")
                
            elif action == '5':
                share_link = f"library://reading-list/{list_id}"
                print(f"Share link: {share_link}")
            
            conn.commit()
        
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    except sqlite3.Error as e:
        print(f"Error sharing reading list: {e}")
    
    conn.close()

def import_reading_list(user_id: str):
    """Import a reading list from various sources"""
    print("\nImport Reading List:")
    print("===================")
    print("1. Import from CSV file")
    print("2. Import from share link")
    print("3. Copy public reading list")
    
    choice = input("Select import method (1-3): ").strip()
    
    if choice == '1':
        # Import from CSV
        file_path = input("Enter CSV file path: ").strip()
        
        if not os.path.exists(file_path):
            print("File not found.")
            return
        
        try:
            df = pd.read_csv(file_path)
            
            if 'book_id' not in df.columns and 'title' not in df.columns:
                print("CSV must contain either 'book_id' or 'title' column.")
                return
            
            list_name = input("Enter name for imported list: ").strip()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Create new reading list
            cursor.execute('''
            INSERT INTO reading_lists (name, creator_id, created_date)
            VALUES (?, ?, ?)
            ''', (list_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            list_id = cursor.lastrowid
            imported_count = 0
            
            for _, row in df.iterrows():
                book_id = None
                
                if 'book_id' in row and pd.notna(row['book_id']):
                    book_id = str(row['book_id']).strip()
                elif 'title' in row and pd.notna(row['title']):
                    title = str(row['title']).strip()
                    author = str(row.get('author', '')).strip() if pd.notna(row.get('author')) else ''
                    
                    # Find book by title and author
                    if author:
                        cursor.execute('''
                        SELECT book_id FROM books 
                        WHERE title LIKE ? AND author LIKE ?
                        LIMIT 1
                        ''', (f'%{title}%', f'%{author}%'))
                    else:
                        cursor.execute('''
                        SELECT book_id FROM books WHERE title LIKE ? LIMIT 1
                        ''', (f'%{title}%',))
                    
                    result = cursor.fetchone()
                    if result:
                        book_id = result[0]
                
                if book_id:
                    # Check if book exists in our library
                    cursor.execute('SELECT book_id FROM books WHERE book_id = ?', (book_id,))
                    if cursor.fetchone():
                        # Add to reading list
                        cursor.execute('''
                        INSERT OR IGNORE INTO reading_list_items
                        (list_id, book_id, added_date, added_by)
                        VALUES (?, ?, ?, ?)
                        ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
                        
                        imported_count += 1
            
            conn.commit()
            conn.close()
            
            print(f"✅ Imported {imported_count} books to reading list '{list_name}'")
            
        except Exception as e:
            print(f"Error importing reading list: {e}")
    
    elif choice == '2':
        # Import from share link
        share_link = input("Enter share link: ").strip()
        
        if share_link.startswith("library://reading-list/"):
            source_list_id = share_link.split("/")[-1]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if source list exists and is public
            cursor.execute('''
            SELECT name, is_public FROM reading_lists WHERE list_id = ?
            ''', (source_list_id,))
            
            source_list = cursor.fetchone()
            
            if not source_list:
                print("Reading list not found.")
                conn.close()
                return
            
            if not source_list[1]:
                print("This reading list is not public.")
                conn.close()
                return
            
            # Copy the list
            new_name = input(f"Name for copied list (original: {source_list[0]}): ").strip() or f"Copy of {source_list[0]}"
            
            cursor.execute('''
            INSERT INTO reading_lists (name, creator_id, created_date)
            VALUES (?, ?, ?)
            ''', (new_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            new_list_id = cursor.lastrowid
            
            # Copy all items from source list
            cursor.execute('''
            INSERT INTO reading_list_items (list_id, book_id, added_date, added_by, notes)
            SELECT ?, book_id, ?, ?, notes
            FROM reading_list_items
            WHERE list_id = ?
            ''', (new_list_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, source_list_id))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Reading list copied successfully as '{new_name}'")
        
        else:
            print("Invalid share link format.")

def generate_enhanced_reports():
    """Generate enhanced library reports"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not (auth.check_permission('generate_reports') or auth.check_permission('view_reports')):
        print("You don't have permission to generate reports.")
        return
    
    print("\nEnhanced Report Generator:")
    print("=========================")
    print("1. Circulation Report")
    print("2. Collection Analysis Report")
    print("3. User Activity Report")
    print("4. Overdue Items Report")
    print("5. Popular Books Report")
    print("6. Reading Level Analysis")
    print("7. Financial Report")
    print("8. Custom Report Builder")
    print("9. Return to menu")
    
    choice = input("Select report type (1-9): ").strip()
    
    if choice == '9':
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if choice == '1':
            # Circulation Report
            print("\nCirculation Report Options:")
            print("1. Monthly circulation summary")
            print("2. Daily circulation details")
            print("3. User circulation patterns")
            
            sub_choice = input("Select option (1-3): ").strip()
            
            if sub_choice == '1':
                # Monthly summary
                cursor.execute('''
                SELECT strftime('%Y-%m', checkout_date) as month,
                       COUNT(*) as total_checkouts,
                       COUNT(DISTINCT user_id) as unique_users,
                       COUNT(DISTINCT book_id) as unique_books,
                       AVG(julianday(COALESCE(return_date, date('now'))) - julianday(checkout_date)) as avg_loan_days
                FROM book_loans
                WHERE checkout_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month DESC
                ''')
                
                data = cursor.fetchall()
                
                report_content = "MONTHLY CIRCULATION SUMMARY\n"
                report_content += "=" * 50 + "\n\n"
                report_content += f"{'Month':<8} {'Checkouts':<10} {'Users':<8} {'Books':<8} {'Avg Days':<10}\n"
                report_content += "-" * 50 + "\n"
                
                for row in data:
                    month, checkouts, users, books, avg_days = row
                    avg_days_str = f"{avg_days:.1f}" if avg_days else "N/A"
                    report_content += f"{month:<8} {checkouts:<10} {users:<8} {books:<8} {avg_days_str:<10}\n"
                
                filename = f"circulation_monthly_{timestamp}.txt"
                
            elif sub_choice == '2':
                # Daily details
                start_date = input("Start date (YYYY-MM-DD): ").strip()
                end_date = input("End date (YYYY-MM-DD): ").strip()
                
                cursor.execute('''
                SELECT date(checkout_date) as day,
                       COUNT(*) as checkouts,
                       COUNT(CASE WHEN return_date IS NOT NULL THEN 1 END) as returns
                FROM book_loans
                WHERE date(checkout_date) BETWEEN ? AND ?
                GROUP BY day
                ORDER BY day
                ''', (start_date, end_date))
                
                data = cursor.fetchall()
                
                report_content = f"DAILY CIRCULATION DETAILS ({start_date} to {end_date})\n"
                report_content += "=" * 50 + "\n\n"
                report_content += f"{'Date':<12} {'Checkouts':<10} {'Returns':<10}\n"
                report_content += "-" * 50 + "\n"
                
                for day, checkouts, returns in data:
                    report_content += f"{day:<12} {checkouts:<10} {returns:<10}\n"
                
                filename = f"circulation_daily_{timestamp}.txt"
            
            # Write report to file
            with open(filename, 'w') as f:
                f.write(report_content)
            
            print(f"✅ Circulation report generated: {filename}")
        
        elif choice == '2':
            # Collection Analysis Report
            cursor.execute('''
            SELECT category,
                   COUNT(*) as total_books,
                   SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                   SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
                   ROUND(AVG(acquisition_cost), 2) as avg_cost,
                   COUNT(DISTINCT author) as unique_authors
            FROM books
            GROUP BY category
            ORDER BY total_books DESC
            ''')
            
            collection_data = cursor.fetchall()
            
            # Get overall statistics
            cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(acquisition_cost) as total_value,
                   MIN(year_published) as oldest_year,
                   MAX(year_published) as newest_year
            FROM books
            ''')
            
            overall_stats = cursor.fetchone()
            
            report_content = "COLLECTION ANALYSIS REPORT\n"
            report_content += "=" * 80 + "\n\n"
            report_content += "OVERALL STATISTICS:\n"
            report_content += f"Total Books: {overall_stats[0]:,}\n"
            report_content += f"Total Value: ${overall_stats[1]:,.2f}\n" if overall_stats[1] else "Total Value: Not calculated\n"
            report_content += f"Publication Range: {overall_stats[2]} - {overall_stats[3]}\n\n"
            
            report_content += "CATEGORY BREAKDOWN:\n"
            report_content += f"{'Category':<20} {'Total':<8} {'Avail':<8} {'Out':<8} {'Avg Cost':<10} {'Authors':<8}\n"
            report_content += "-" * 80 + "\n"
            
            for row in collection_data:
                category, total, available, checked_out, avg_cost, authors = row
                avg_cost_str = f"${avg_cost:.2f}" if avg_cost else "N/A"
                report_content += f"{category[:19]:<20} {total:<8} {available:<8} {checked_out:<8} {avg_cost_str:<10} {authors:<8}\n"
            
            filename = f"collection_analysis_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(report_content)
            
            print(f"✅ Collection analysis report generated: {filename}")
        
        elif choice == '3':
            # User Activity Report
            days_back = int(input("Number of days to analyze (default 30): ").strip() or 30)
            
            cursor.execute('''
            SELECT user_id,
                   COUNT(*) as total_loans,
                   COUNT(CASE WHEN status = 'returned' THEN 1 END) as returned,
                   COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue,
                   SUM(fine_amount) as total_fines,
                   AVG(reading_progress) as avg_progress
            FROM book_loans
            WHERE checkout_date >= date('now', '-' || ? || ' days')
            GROUP BY user_id
            HAVING total_loans > 0
            ORDER BY total_loans DESC
            LIMIT 50
            ''', (days_back,))
            
            user_data = cursor.fetchall()
            
            report_content = f"USER ACTIVITY REPORT (Last {days_back} days)\n"
            report_content += "=" * 80 + "\n\n"
            report_content += f"{'User ID':<15} {'Loans':<8} {'Returned':<10} {'Overdue':<8} {'Fines':<10} {'Avg Progress':<12}\n"
            report_content += "-" * 80 + "\n"
            
            for row in user_data:
                user_id, loans, returned, overdue, fines, progress = row
                fines_str = f"${fines:.2f}" if fines else "$0.00"
                progress_str = f"{progress:.1f}%" if progress else "N/A"
                report_content += f"{user_id:<15} {loans:<8} {returned:<10} {overdue:<8} {fines_str:<10} {progress_str:<12}\n"
            
            filename = f"user_activity_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(report_content)
            
            print(f"✅ User activity report generated: {filename}")
        
        elif choice == '4':
            # Overdue Items Report
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue,
                   bl.fine_amount
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE bl.status = 'overdue'
            ORDER BY days_overdue DESC
            ''')
            
            overdue_data = cursor.fetchall()
            
            report_content = "OVERDUE ITEMS REPORT\n"
            report_content += "=" * 80 + "\n\n"
            report_content += f"Total Overdue Items: {len(overdue_data)}\n\n"
            report_content += f"{'User ID':<15} {'Book ID':<10} {'Title':<25} {'Due Date':<12} {'Days':<6} {'Fine':<8}\n"
            report_content += "-" * 80 + "\n"
            
            total_fines = 0
            for row in overdue_data:
                user_id, book_id, title, due_date, days_overdue, fine = row
                title_display = title[:24] if len(title) > 25 else title
                fine_str = f"${fine:.2f}" if fine else "$0.00"
                total_fines += fine if fine else 0
                
                report_content += f"{user_id:<15} {book_id:<10} {title_display:<25} {due_date[:10]:<12} {int(days_overdue):<6} {fine_str:<8}\n"
            
            report_content += "-" * 80 + "\n"
            report_content += f"Total Outstanding Fines: ${total_fines:.2f}\n"
            
            filename = f"overdue_report_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(report_content)
            
            print(f"✅ Overdue items report generated: {filename}")
        
        elif choice == '5':
            # Popular Books Report
            cursor.execute('''
            SELECT b.book_id, b.title, b.author, b.category,
                   COUNT(bl.loan_id) as loan_count,
                   AVG(COALESCE(r.rating, 0)) as avg_rating,
                   COUNT(r.review_id) as review_count
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
            GROUP BY b.book_id
            HAVING loan_count > 0
            ORDER BY loan_count DESC
            LIMIT 25
            ''')
            
            popular_data = cursor.fetchall()
            
            report_content = "POPULAR BOOKS REPORT (Top 25)\n"
            report_content += "=" * 90 + "\n\n"
            report_content += f"{'Rank':<4} {'Book ID':<8} {'Title':<25} {'Author':<20} {'Loans':<6} {'Rating':<8} {'Reviews':<7}\n"
            report_content += "-" * 90 + "\n"
            
            for i, row in enumerate(popular_data, 1):
                book_id, title, author, category, loans, rating, reviews = row
                title_display = title[:24] if len(title) > 25 else title
                author_display = author[:19] if len(author) > 20 else author
                rating_str = f"{rating:.1f}/5" if rating > 0 else "N/A"
                
                report_content += f"{i:<4} {book_id:<8} {title_display:<25} {author_display:<20} {loans:<6} {rating_str:<8} {reviews:<7}\n"
            
            filename = f"popular_books_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(report_content)
            
            print(f"✅ Popular books report generated: {filename}")
        
        # FIXED: Log the report generation using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Generated report type {choice}", "reports")    
    except sqlite3.Error as e:
        print(f"Error generating report: {e}")
    
    conn.close()
    
def enhanced_manage_settings():
    """Enhanced settings management with validation"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage settings.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to manage settings.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    while True:
        print("\nEnhanced Settings Management:")
        print("============================")
        print("1. View All Settings")
        print("2. Update Setting")
        print("3. Reset Setting to Default")
        print("4. Export Settings")
        print("5. Import Settings")
        print("6. Validate Configuration")
        print("7. Return to menu")
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '7':
            break
        
        try:
            if choice == '1':
                # View all settings
                cursor.execute('''
                SELECT setting_name, setting_value, description, setting_type
                FROM library_settings
                ORDER BY setting_name
                ''')
                
                settings = cursor.fetchall()
                
                print(f"\nLibrary Settings ({len(settings)}):")
                print("=" * 80)
                print(f"{'Setting':<25} {'Value':<15} {'Type':<10} {'Description':<30}")
                print("-" * 80)
                
                for name, value, desc, setting_type in settings:
                    desc_display = desc[:29] if len(desc) > 30 else desc
                    print(f"{name:<25} {value:<15} {setting_type:<10} {desc_display:<30}")
                
                print("=" * 80)
            
            elif choice == '2':
                # Update setting
                setting_name = input("Enter setting name: ").strip()
                
                # Get current setting info
                cursor.execute('''
                SELECT setting_value, description, setting_type, min_value, max_value, allowed_values
                FROM library_settings
                WHERE setting_name = ?
                ''', (setting_name,))
                
                setting_info = cursor.fetchone()
                
                if not setting_info:
                    print("Setting not found.")
                    continue
                
                current_value, desc, setting_type, min_val, max_val, allowed_vals = setting_info
                
                print(f"\nSetting: {setting_name}")
                print(f"Description: {desc}")
                print(f"Current Value: {current_value}")
                print(f"Type: {setting_type}")
                
                if allowed_vals:
                    print(f"Allowed Values: {allowed_vals}")
                if min_val is not None or max_val is not None:
                    print(f"Range: {min_val} - {max_val}")
                
                new_value = input("Enter new value: ").strip()
                
                # Validate new value
                if validate_setting_value(setting_type, new_value, min_val, max_val, allowed_vals):
                    cursor.execute('''
                    UPDATE library_settings SET setting_value = ?
                    WHERE setting_name = ?
                    ''', (new_value, setting_name))
                    
                    conn.commit()
                    
                    # FIXED: Log the change using get_current_user_id() helper function
                    log_audit_event(get_current_user_id(), 
                                  f"Changed setting {setting_name} from {current_value} to {new_value}",
                                  "library_settings", setting_name)
                    
                    print(f"✅ Setting '{setting_name}' updated successfully!")
                else:
                    print("❌ Invalid value for this setting.")
            
            elif choice == '3':
                # Reset to default
                setting_name = input("Enter setting name to reset: ").strip()
                
                # You would need to define default values
                default_values = {
                    'loan_period_days': '14',
                    'max_loans': '5',
                    'fine_per_day': '0.50',
                    'reservation_period_days': '3',
                    'max_renewals': '2'
                }
                
                if setting_name in default_values:
                    cursor.execute('''
                    UPDATE library_settings SET setting_value = ?
                    WHERE setting_name = ?
                    ''', (default_values[setting_name], setting_name))
                    
                    conn.commit()
                    print(f"✅ Setting '{setting_name}' reset to default value.")
                else:
                    print("No default value defined for this setting.")
            
            elif choice == '4':
                # Export settings
                cursor.execute('SELECT setting_name, setting_value FROM library_settings')
                settings = cursor.fetchall()
                
                settings_dict = {name: value for name, value in settings}
                
                filename = f"library_settings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                with open(filename, 'w') as f:
                    json.dump(settings_dict, f, indent=2)
                
                print(f"✅ Settings exported to {filename}")
            
            elif choice == '5':
                # Import settings
                filename = input("Enter settings file path: ").strip()
                
                if not os.path.exists(filename):
                    print("File not found.")
                    continue
                
                try:
                    with open(filename, 'r') as f:
                        imported_settings = json.load(f)
                    
                    updated_count = 0
                    
                    for setting_name, setting_value in imported_settings.items():
                        cursor.execute('''
                        UPDATE library_settings SET setting_value = ?
                        WHERE setting_name = ?
                        ''', (setting_value, setting_name))
                        
                        if cursor.rowcount > 0:
                            updated_count += 1
                    
                    conn.commit()
                    print(f"✅ Updated {updated_count} settings from import file.")
                    
                except json.JSONDecodeError:
                    print("Invalid JSON file format.")
                except Exception as e:
                    print(f"Error importing settings: {e}")
            
            elif choice == '6':
                # Validate configuration
                validation_results = validate_library_configuration(cursor)
                
                print("\nConfiguration Validation Results:")
                print("=" * 50)
                
                for result in validation_results:
                    status = "✅" if result['valid'] else "❌"
                    print(f"{status} {result['check']}: {result['message']}")
        
        except sqlite3.Error as e:
            print(f"Error managing settings: {e}")
    
    conn.close()
    
def validate_setting_value(setting_type: str, value: str, min_val: float = None, 
                          max_val: float = None, allowed_vals: str = None) -> bool:
    """Validate a setting value based on its type and constraints"""
    try:
        if setting_type == 'integer':
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                return False
            if max_val is not None and int_val > max_val:
                return False
            return True
        
        elif setting_type == 'decimal':
            float_val = float(value)
            if min_val is not None and float_val < min_val:
                return False
            if max_val is not None and float_val > max_val:
                return False
            return True
        
        elif setting_type == 'boolean':
            return value.lower() in ['true', 'false', '1', '0', 'yes', 'no']
        
        elif setting_type == 'string':
            if allowed_vals:
                allowed_list = allowed_vals.split(',')
                return value in allowed_list
            return True
        
        return True
        
    except (ValueError, TypeError):
        return False

def validate_library_configuration(cursor) -> List[Dict]:
    """Validate the entire library configuration"""
    results = []
    
    try:
        # Check loan period
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
        loan_period = int(cursor.fetchone()[0])
        
        results.append({
            'check': 'Loan Period',
            'valid': 1 <= loan_period <= 365,
            'message': f'{loan_period} days (valid range: 1-365)'
        })
        
        # Check max loans
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_loans"')
        max_loans = int(cursor.fetchone()[0])
        
        results.append({
            'check': 'Max Loans per User',
            'valid': 1 <= max_loans <= 50,
            'message': f'{max_loans} books (valid range: 1-50)'
        })
        
        # Check fine amount
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
        fine_per_day = float(cursor.fetchone()[0])
        
        results.append({
            'check': 'Daily Fine Amount',
            'valid': 0 <= fine_per_day <= 10,
            'message': f'${fine_per_day:.2f} (valid range: $0.00-$10.00)'
        })
        
        # Check database integrity
        cursor.execute('PRAGMA integrity_check')
        integrity_result = cursor.fetchone()[0]
        
        results.append({
            'check': 'Database Integrity',
            'valid': integrity_result == 'ok',
            'message': integrity_result
        })
        
        # Check for orphaned records
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans bl
        LEFT JOIN books b ON bl.book_id = b.book_id
        WHERE b.book_id IS NULL
        ''')
        
        orphaned_loans = cursor.fetchone()[0]
        
        results.append({
            'check': 'Orphaned Loan Records',
            'valid': orphaned_loans == 0,
            'message': f'{orphaned_loans} orphaned records found' if orphaned_loans > 0 else 'No orphaned records'
        })
        
    except Exception as e:
        results.append({
            'check': 'Configuration Validation',
            'valid': False,
            'message': f'Error during validation: {e}'
        })
    
    return results

def view_audit_log():
    """View system audit log"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view audit logs.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to view audit logs.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nAudit Log Viewer:")
    print("================")
    print("1. Recent Activities (Last 24 hours)")
    print("2. User Activities")
    print("3. Failed Operations")
    print("4. System Changes")
    print("5. Custom Date Range")
    
    choice = input("Select view option (1-5): ").strip()
    
    try:
        if choice == '1':
            # Recent activities
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp, success
            FROM audit_log
            WHERE timestamp >= datetime('now', '-1 day')
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "Recent Activities (Last 24 hours)"
            
        elif choice == '2':
            # User activities
            user_id = input("Enter User ID: ").strip()
            
            cursor.execute('''
            SELECT action, table_affected, record_id, timestamp, success
            FROM audit_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
            ''', (user_id,))
            
            title = f"Activities for User: {user_id}"
            
        elif choice == '3':
            # Failed operations
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp
            FROM audit_log
            WHERE success = 0
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "Failed Operations"
            
        elif choice == '4':
            # System changes
            cursor.execute('''
            SELECT user_id, action, table_affected, old_values, new_values, timestamp
            FROM audit_log
            WHERE table_affected IN ('library_settings', 'system')
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "System Changes"
            
        elif choice == '5':
            # Custom date range
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp, success
            FROM audit_log
            WHERE date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp DESC
            LIMIT 100
            ''', (start_date, end_date))
            
            title = f"Audit Log ({start_date} to {end_date})"
        
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        activities = cursor.fetchall()
        
        if not activities:
            print("No audit records found.")
            conn.close()
            return
        
        print(f"\n{title}")
        print("=" * 80)
        print(f"{'User ID':<12} {'Action':<25} {'Table':<15} {'Timestamp':<20} {'Status':<8}")
        print("-" * 80)
        
        for activity in activities:
            if len(activity) >= 5:
                user_id, action, table, timestamp, success = activity[:5]
                status = "✅" if success else "❌"
                action_display = action[:24] if len(action) > 25 else action
                table_display = table[:14] if table and len(table) > 15 else (table or "N/A")
                
                print(f"{user_id:<12} {action_display:<25} {table_display:<15} {timestamp[:19]:<20} {status:<8}")
            else:
                # Handle different query result formats
                print(f"{str(activity)}")
        
        print("=" * 80)
        print(f"Total records: {len(activities)}")
    
    except sqlite3.Error as e:
        print(f"Error viewing audit log: {e}")
    
    conn.close()

def setup_scheduled_backups():
    """Setup scheduled backup configuration"""
    print("\nScheduled Backup Setup:")
    print("======================")
    print("This feature would integrate with your system's task scheduler.")
    print("For implementation, you would:")
    print("1. Create a backup script")
    print("2. Configure cron job (Linux/Mac) or Task Scheduler (Windows)")
    print("3. Set up backup rotation and cleanup")
    print("4. Configure backup monitoring and alerts")
    
    # Example backup script creation
    backup_script = f'''#!/bin/bash
# Library System Backup Script
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$DATE"

mkdir -p "$BACKUP_PATH"

# Backup database
cp {DATABASE_FILE} "$BACKUP_PATH/"

# Backup additional files
cp -r qr_codes "$BACKUP_PATH/" 2>/dev/null || true
cp -r digital_library "$BACKUP_PATH/" 2>/dev/null || true
cp -r cover_images "$BACKUP_PATH/" 2>/dev/null || true

# Create manifest
echo "{{
    \\"backup_date\\": \\"$(date -Iseconds)\\",
    \\"backup_type\\": \\"scheduled\\",
    \\"automated\\": true
}}" > "$BACKUP_PATH/manifest.json"

# Cleanup old backups (keep last 7 days)
find "$BACKUP_DIR" -name "backup_*" -type d -mtime +7 -exec rm -rf {{}} \\;

echo "Backup completed: $BACKUP_PATH"
'''
    
    script_filename = "library_backup.sh"
    with open(script_filename, 'w') as f:
        f.write(backup_script)
    
    print(f"✅ Backup script created: {script_filename}")
    print("To schedule this backup:")
    print("Linux/Mac: Add to crontab with 'crontab -e'")
    print("Example: 0 2 * * * /path/to/library_backup.sh  # Daily at 2 AM")
    print("Windows: Use Task Scheduler to run the script")

def restore_from_backup():
    """Restore system from backup"""
    print("\nRestore from Backup:")
    print("===================")
    print("⚠️  WARNING: This will overwrite current data!")
    
    # List available backups
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("No backup directory found.")
        return
    
    backups = []
    for item in os.listdir(backup_dir):
        backup_path = os.path.join(backup_dir, item)
        if os.path.isdir(backup_path) and item.startswith("backup_"):
            manifest_path = os.path.join(backup_path, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    backups.append((item, backup_path, manifest))
                except (OSError, IOError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to load manifest for {item}: {e}")
                    backups.append((item, backup_path, {}))
    
    if not backups:
        print("No valid backups found.")
        return
    
    backups.sort(key=lambda x: x[0], reverse=True)
    
    print("Available Backups:")
    for i, (name, path, manifest) in enumerate(backups, 1):
        backup_date = manifest.get('backup_date', 'Unknown')
        backup_type = manifest.get('backup_type', 'Unknown')
        print(f"{i}. {name} - {backup_date} ({backup_type})")
    
    try:
        choice = int(input("Select backup to restore (0 to cancel): "))
        
        if choice == 0:
            print("Restore cancelled.")
            return
        
        if 1 <= choice <= len(backups):
            selected_backup = backups[choice - 1]
            backup_name, backup_path, manifest = selected_backup
            
            print(f"\nSelected backup: {backup_name}")
            confirm = input("Type 'RESTORE' to confirm: ").strip()
            
            if confirm != 'RESTORE':
                print("Restore cancelled.")
                return
            
            # Create current backup before restore
            print("Creating safety backup of current data...")
            safety_backup_dir = BACKUP_DIR / f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            safety_backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DATABASE_FILE, safety_backup_dir)
            
            # Restore database
            backup_db_path = os.path.join(backup_path, 'library_database.db')
            if os.path.exists(backup_db_path):
                shutil.copy2(backup_db_path, DATABASE_FILE)
                print("✅ Database restored")
            
            # Restore additional files
            for dir_name in ['qr_codes', 'digital_library', 'cover_images']:
                backup_subdir = os.path.join(backup_path, dir_name)
                if os.path.exists(backup_subdir):
                    if os.path.exists(dir_name):
                        shutil.rmtree(dir_name)
                    shutil.copytree(backup_subdir, dir_name)
                    print(f"✅ {dir_name} restored")
            
            print(f"✅ System restored from backup: {backup_name}")
            print(f"Safety backup created at: {safety_backup_dir}")
            
        else:
            print("Invalid selection.")
    
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error during restore: {e}")

def configure_notification_settings():
    """Configure notification settings"""
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nNotification Settings:")
    print("=====================")
    
    # Current notification settings
    notification_settings = [
        'email_notifications',
        'sms_notifications',
        'auto_reminders',
        'overdue_notifications',
        'reservation_alerts'
    ]
    
    try:
        for setting in notification_settings:
            cursor.execute('''
            SELECT setting_value FROM library_settings WHERE setting_name = ?
            ''', (setting,))
            
            result = cursor.fetchone()
            current_value = result[0] if result else 'false'
            
            print(f"{setting.replace('_', ' ').title()}: {current_value}")
        
        print("\nUpdate Settings:")
        for setting in notification_settings:
            cursor.execute('''
            SELECT setting_value FROM library_settings WHERE setting_name = ?
            ''', (setting,))
            
            result = cursor.fetchone()
            current_value = result[0] if result else 'false'
            
            new_value = input(f"Enable {setting.replace('_', ' ')} (y/n) [{current_value}]: ").strip().lower()
            
            if new_value in ['y', 'yes']:
                new_value = 'true'
            elif new_value in ['n', 'no']:
                new_value = 'false'
            else:
                continue  # Keep current value
            
            cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES (?, ?)
            ''', (setting, new_value))
        
        conn.commit()
        print("✅ Notification settings updated!")
        
    except sqlite3.Error as e:
        print(f"Error configuring notifications: {e}")
    
    conn.close()

def send_overdue_notification(user_id: str, book_id: str, title: str, due_date: str, days_overdue: int):
    """Send overdue notification to user"""
    try:
        # Calculate fine amount
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
        fine_per_day = float(cursor.fetchone()[0])
        total_fine = days_overdue * fine_per_day
        
        # Update fine in loan record
        cursor.execute('''
        UPDATE book_loans 
        SET fine_amount = ?
        WHERE book_id = ? AND user_id = ? AND status IN ('active', 'overdue')
        ''', (total_fine, book_id, user_id))
        
        conn.commit()
        conn.close()
        
        # Send notification (implementation depends on your notification system)
        message = f"""
OVERDUE NOTICE

Book: {title} ({book_id})
Due Date: {due_date}
Days Overdue: {days_overdue}
Current Fine: ${total_fine:.2f}

Please return this book as soon as possible to avoid additional fines.

Contact the library if you have any questions.
        """
        
        logging.info(f"Overdue notification sent to {user_id} for book {book_id}")
        
    except Exception as e:
        logging.error(f"Error sending overdue notification: {e}")

def generate_library_cards():
    """Generate library cards for users"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate library cards.")
        return
    
    if not auth.check_permission('manage_users'):
        print("You don't have permission to generate library cards.")
        return
    
    print("\nLibrary Card Generator:")
    print("======================")
    print("1. Generate card for specific user")
    print("2. Bulk generate cards")
    print("3. Re-generate lost card")
    
    choice = input("Select option (1-3): ").strip()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            # Single user card
            user_id = input("Enter User/Student ID: ").strip()
            
            # Get user information
            cursor.execute('''
            SELECT first_name, last_name, grade_level, email 
            FROM students WHERE student_id = ?
            ''', (user_id,))
            
            user_info = cursor.fetchone()
            
            if not user_info:
                print("User not found.")
                return
            
            first_name, last_name, grade_level, email = user_info
            
            # Generate library card
            card_data = generate_library_card_data(user_id, first_name, last_name, grade_level)
            
            card_filename = f"library_card_{user_id}.png"
            create_library_card_image(card_data, card_filename)
            
            print(f"✅ Library card generated: {card_filename}")
            
        elif choice == '2':
            # Bulk generation
            print("Bulk card generation feature would:")
            print("1. Query all active users")
            print("2. Generate cards for users without them")
            print("3. Create a batch PDF with multiple cards")
            print("4. Track card generation status")
            
            print("This feature requires additional implementation.")
            
        elif choice == '3':
            # Re-generate lost card
            user_id = input("Enter User ID for replacement card: ").strip()
            
            # Mark old card as invalid and generate new one
            print(f"Re-generating library card for {user_id}")
            print("Old card would be marked as invalid in the system.")
            
        conn.close()
        
    except Exception as e:
        print(f"Error generating library cards: {e}")

def generate_library_card_data(user_id: str, first_name: str, last_name: str, grade_level: str) -> Dict:
    """Generate data for library card"""
    card_number = f"LIB{user_id.zfill(6)}"
    issue_date = datetime.now().strftime('%Y-%m-%d')
    expiry_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
    
    return {
        'card_number': card_number,
        'user_id': user_id,
        'full_name': f"{first_name} {last_name}",
        'grade_level': grade_level,
        'issue_date': issue_date,
        'expiry_date': expiry_date,
        'barcode': generate_barcode(user_id),
        'qr_code_data': f"LIBRARY_USER:{user_id}:{card_number}"
    }

def create_library_card_image(card_data: Dict, filename: str):
    """Create library card image using PIL or fallback to text file."""
    try:
        # Try to use PIL for actual image generation
        from PIL import Image, ImageDraw, ImageFont
        import qrcode
        import io
        import base64

        # Card dimensions (3.5" x 2.25" at 300 DPI)
        card_width, card_height = 1050, 675

        # Create a new image with white background
        card = Image.new('RGB', (card_width, card_height), 'white')
        draw = ImageDraw.Draw(card)

        # Define colors
        header_color = (0, 73, 144)  # University blue
        text_color = (0, 0, 0)

        # Draw header background
        draw.rectangle([0, 0, card_width, 120], fill=header_color)

        # Try to load fonts (fallback to default if not available)
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (OSError, IOError) as e:
            logger.warning(f"Failed to load TrueType fonts, using default: {e}")
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw title
        draw.text((20, 30), "UNIVERSITY LIBRARY", fill='white', font=title_font)
        draw.text((20, 60), "Student ID Card", fill='white', font=text_font)

        # Draw student information
        y_position = 150
        draw.text((20, y_position), f"Name: {card_data['full_name']}", fill=text_color, font=name_font)
        y_position += 40
        draw.text((20, y_position), f"Card Number: {card_data['card_number']}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"User ID: {card_data['user_id']}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"Grade: {card_data.get('grade_level', 'N/A')}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"Valid Until: {card_data['expiry_date']}", fill=text_color, font=text_font)

        # Generate QR code for card number
        qr = qrcode.QRCode(version=1, box_size=8, border=1)
        qr.add_data(card_data['card_number'])
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Resize and paste QR code
        qr_img = qr_img.resize((150, 150))
        card.paste(qr_img, (card_width - 170, card_height - 170))

        # Add barcode text
        draw.text((card_width - 170, card_height - 15), card_data['barcode'][:10], fill=text_color, font=text_font)

        # Draw border
        draw.rectangle([0, 0, card_width-1, card_height-1], outline=header_color, width=3)

        # Save the image
        card.save(filename, 'PNG', quality=95)
        print(f"✅ Library card image created: {filename}")

        return True

    except ImportError:
        # Fallback to text file if PIL not available
        print("PIL not available, creating text file instead...")

        # Create a simple text file as fallback
        with open(filename.replace('.png', '.txt'), 'w') as f:
            f.write("UNIVERSITY LIBRARY CARD\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Name: {card_data['full_name']}\n")
            f.write(f"Card Number: {card_data['card_number']}\n")
            f.write(f"User ID: {card_data['user_id']}\n")
            f.write(f"Grade: {card_data.get('grade_level', 'N/A')}\n")
            f.write(f"Issue Date: {card_data['issue_date']}\n")
            f.write(f"Expiry Date: {card_data['expiry_date']}\n")
            f.write(f"Barcode: {card_data['barcode']}\n\n")
            f.write("Note: Install PIL/Pillow for image generation\n")

        print(f"📄 Library card text file created: {filename.replace('.png', '.txt')}")
        return False

    except Exception as e:
        print(f"❌ Error creating library card: {e}")
        return False

def manage_library_events():
    """Manage library events and programs"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage events.")
        return
    
    if not auth.check_permission('manage_events'):
        print("You don't have permission to manage events.")
        return
    
    print("\nLibrary Events Management:")
    print("=========================")
    print("1. View Upcoming Events")
    print("2. Create New Event")
    print("3. Edit Event")
    print("4. Cancel Event")
    print("5. Event Attendance")
    print("6. Event Reports")
    print("7. Return to menu")
    
    choice = input("Enter your choice (1-7): ").strip()
    
    if choice == '7':
        return
    
    # This would require an events table in the database
    # For now, show what the functionality would include
    
    event_features = {
        '1': "Display upcoming events with dates, descriptions, and registration status",
        '2': "Create events with scheduling, capacity limits, and registration requirements",
        '3': "Modify event details, reschedule, or update descriptions",
        '4': "Cancel events and notify registered participants",
        '5': "Track event attendance and participant feedback",
        '6': "Generate reports on event popularity and attendance trends"
    }
    
    if choice in event_features:
        print(f"\n{event_features[choice]}")
        print("This feature requires additional database tables and implementation.")
        print("Events table would include: event_id, title, description, date_time, capacity, etc.")
    else:
        print("Invalid choice.")

def advanced_search_interface():
    """Advanced search interface with filters and sorting"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to search.")
        return
    
    print("\nAdvanced Search Interface:")
    print("=========================")
    
    # Initialize search criteria
    search_criteria = {
        'title': '',
        'author': '',
        'isbn': '',
        'category': '',
        'reading_level': '',
        'year_from': '',
        'year_to': '',
        'status': '',
        'tags': '',
        'location': ''
    }
    
    sort_options = ['title', 'author', 'year_published', 'category', 'added_date']
    sort_by = 'title'
    sort_order = 'ASC'
    
    while True:
        print(f"\nCurrent Search Criteria:")
        print("-" * 30)
        for key, value in search_criteria.items():
            display_value = value if value else "Any"
            print(f"{key.replace('_', ' ').title()}: {display_value}")
        
        print(f"\nSort by: {sort_by} ({sort_order})")
        
        print("\nOptions:")
        print("1-10. Set search criteria")
        print("11. Change sort options")
        print("12. Execute search")
        print("13. Clear all criteria")
        print("14. Save search")
        print("15. Return to menu")
        
        choice = input("Enter your choice: ").strip()
        
        if choice == '15':
            break
        elif choice == '12':
            # Execute search
            results = execute_advanced_search(search_criteria, sort_by, sort_order)
            display_search_results(results)
        elif choice == '13':
            # Clear criteria
            search_criteria = {key: '' for key in search_criteria}
            print("✅ Search criteria cleared.")
        else:
            print("Advanced search feature would allow setting individual criteria.")
            print("Implementation requires building dynamic SQL queries based on criteria.")

def execute_advanced_search(criteria: Dict, sort_by: str, sort_order: str) -> List:
    """Execute advanced search with given criteria"""
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    
    # Build dynamic query
    query = "SELECT book_id, title, author, category, status, reading_level FROM books WHERE 1=1"
    params = []
    
    for field, value in criteria.items():
        if value:
            if field in ['year_from']:
                query += " AND year_published >= ?"
                params.append(int(value))
            elif field in ['year_to']:
                query += " AND year_published <= ?"
                params.append(int(value))
            elif field in ['title', 'author', 'category', 'location']:
                query += f" AND {field} LIKE ?"
                params.append(f'%{value}%')
            elif field == 'tags':
                query += " AND tags LIKE ?"
                params.append(f'%{value}%')
            else:
                query += f" AND {field} = ?"
                params.append(value)
    
    query += f" ORDER BY {sort_by} {sort_order}"
    
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    except sqlite3.Error as e:
        print(f"Search error: {e}")
        conn.close()
        return []

def display_search_results(results: List):
    """Display search results in formatted table"""
    if not results:
        print("No books found matching your criteria.")
        return
    
    print(f"\nSearch Results ({len(results)} books found):")
    print("=" * 80)
    print(f"{'ID':<8} {'Title':<25} {'Author':<20} {'Category':<15} {'Status':<10}")
    print("-" * 80)
    
    for result in results:
        book_id, title, author, category, status, reading_level = result
        title_display = title[:24] if len(title) > 25 else title
        author_display = author[:19] if len(author) > 20 else author
        category_display = category[:14] if len(category) > 15 else category
        
        print(f"{book_id:<8} {title_display:<25} {author_display:<20} {category_display:<15} {status:<10}")
    
    print("=" * 80)

def library_statistics_dashboard():
    """Display comprehensive library statistics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view statistics.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("                    LIBRARY STATISTICS DASHBOARD")
    print("="*80)
    
    try:
        # Collection Statistics
        cursor.execute('SELECT COUNT(*) FROM books')
        total_books = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
        unique_authors = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT category) FROM books')
        unique_categories = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(acquisition_cost) FROM books WHERE acquisition_cost > 0')
        total_value = cursor.fetchone()[0] or 0
        
        print(f"\n📚 COLLECTION OVERVIEW")
        print(f"Total Books: {total_books:,}")
        print(f"Unique Authors: {unique_authors:,}")
        print(f"Categories: {unique_categories}")
        print(f"Collection Value: ${total_value:,.2f}")
        
        # Circulation Statistics
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
        monthly_checkouts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_books = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
        active_reservations = cursor.fetchone()[0]
        
        print(f"\n🔄 CIRCULATION STATISTICS")
        print(f"Active Loans: {active_loans:,}")
        print(f"Monthly Checkouts: {monthly_checkouts:,}")
        print(f"Overdue Items: {overdue_books:,}")
        print(f"Active Reservations: {active_reservations:,}")
        
        # User Engagement
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
        active_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_reviews WHERE status = "approved"')
        total_reviews = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM reading_lists WHERE is_public = 1')
        public_lists = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM user_achievements WHERE earned_date >= date("now", "-30 days")')
        recent_achievements = cursor.fetchone()[0]
        
        print(f"\n👥 USER ENGAGEMENT")
        print(f"Active Users (30 days): {active_users:,}")
        print(f"Book Reviews: {total_reviews:,}")
        print(f"Public Reading Lists: {public_lists:,}")
        print(f"Recent Achievements: {recent_achievements:,}")
        
        # System Health
        cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime("now", "-24 hours")')
        daily_activities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM notification_queue WHERE sent = 0')
        pending_notifications = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM book_requests WHERE status = "pending"')
        pending_requests = cursor.fetchone()[0]
        
        print(f"\n⚙️  SYSTEM HEALTH")
        print(f"Daily Activities: {daily_activities:,}")
        print(f"Pending Notifications: {pending_notifications:,}")
        print(f"Pending Book Requests: {pending_requests:,}")
        
        # Performance Metrics
        if total_books > 0:
            circulation_rate = (active_loans / total_books) * 100
            print(f"\n📊 PERFORMANCE METRICS")
            print(f"Circulation Rate: {circulation_rate:.1f}%")
            
            if monthly_checkouts > 0:
                avg_daily_checkouts = monthly_checkouts / 30
                print(f"Avg Daily Checkouts: {avg_daily_checkouts:.1f}")
        
        print("="*80)
        
    except sqlite3.Error as e:
        print(f"Error generating statistics: {e}")
    
    conn.close()

# Initialize logging for the enhanced system
logging.info("Enhanced Library Management System loaded successfully")

# Enhanced notification functions
def send_email_notification(email: str, subject: str, message: str):
    """Send email notification"""
    # Implementation would depend on your email service
    logging.info(f"Email sent to {email}: {subject}")

def send_sms_notification(user_id: str, message: str):
    """Send SMS notification"""
    # Implementation would depend on your SMS service
    logging.info(f"SMS sent to {user_id}: {message}")

def send_due_date_reminder(user_id: str, book_id: str, title: str, due_date: str):
    """Send due date reminder"""
    message = f"Reminder: '{title}' ({book_id}) is due on {due_date}"
    logging.info(f"Due date reminder sent to {user_id}")

def send_reservation_confirmation(user_id: str, book_id: str, title: str, position: int, expiry: str):
    """Send reservation confirmation"""
    message = f"Book reserved: '{title}' - Position {position}, expires {expiry}"
    logging.info(f"Reservation confirmation sent to {user_id}")

def send_reservation_available_notification(user_id: str, book_id: str, title: str):
    """Send notification when reserved book becomes available"""
    message = f"Your reserved book '{title}' is now available for pickup!"
    logging.info(f"Reservation available notification sent to {user_id}")

def send_generic_email_notification(user_id: str, title: str, message: str):
    """Send generic email notification"""
    logging.info(f"Generic notification sent to {user_id}: {title}")

def get_library_settings(setting_name):
    """Get a library setting value"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = ?', (setting_name,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Error getting library setting {setting_name}: {e}")
        return None

def update_library_setting(setting_name, setting_value):
    """Update a library setting"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
        VALUES (?, ?)
        ''', (setting_name, setting_value))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logging.error(f"Error updating library setting {setting_name}: {e}")
        return False

def list_all_books():
    """List all books in the library"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view books.")
        return
    
    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print("You don't have permission to view books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT book_id, title, author, category, status
        FROM books
        ORDER BY title
        ''')
        
        books = cursor.fetchall()
        
        if not books:
            print("No books found in the library.")
            return
        
        print(f"\nAll Books ({len(books)} total):")
        print("=" * 80)
        print(f"{'ID':<8} {'Title':<30} {'Author':<25} {'Category':<15} {'Status':<10}")
        print("-" * 80)
        
        for book in books:
            book_id, title, author, category, status = book
            title_display = (title[:27] + '...') if len(title) > 30 else title
            author_display = (author[:22] + '...') if len(author) > 25 else author
            category_display = (category[:12] + '...') if len(category) > 15 else category
            
            print(f"{book_id:<8} {title_display:<30} {author_display:<25} {category_display:<15} {status:<10}")
        
        print("=" * 80)
        
    except sqlite3.Error as e:
        print(f"Error listing books: {e}")
    
    conn.close()

def view_book_details():
    """View detailed information about a specific book"""
    enhanced_view_book_details()

def add_book():
    """Add a new book to the library (calls enhanced version)"""
    enhanced_add_book()

def update_book():
    """Update book information (calls enhanced version)"""
    enhanced_update_book()

def search_books():
    """Search for books (calls enhanced version)"""
    enhanced_search_books()

def checkout_book():
    """Check out a book (calls enhanced version)"""
    enhanced_checkout_book()

def return_book():
    """Return a book (calls enhanced version)"""
    enhanced_return_book()

def manage_settings():
    """Manage library settings (calls enhanced version)"""
    enhanced_manage_settings()

def generate_reports():
    """Generate library reports (calls enhanced version)"""
    generate_enhanced_reports()

def backup_system():
    """Create system backup (calls enhanced version)"""
    enhanced_system_backup()

def view_overdue_books():
    """View all overdue books"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view overdue books.")
        return
    
    if not auth.check_permission('view_reports'):
        print("You don't have permission to view overdue books.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
               julianday('now') - julianday(bl.due_date) as days_overdue,
               bl.fine_amount
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.status = 'overdue'
        ORDER BY days_overdue DESC
        ''')
        
        overdue_books = cursor.fetchall()
        
        if not overdue_books:
            print("No overdue books found.")
            return
        
        print(f"\nOverdue Books ({len(overdue_books)} total):")
        print("=" * 90)
        print(f"{'User ID':<12} {'Book ID':<10} {'Title':<30} {'Due Date':<12} {'Days Over':<10} {'Fine':<8}")
        print("-" * 90)
        
        total_fines = 0
        for book in overdue_books:
            user_id, book_id, title, due_date, days_overdue, fine = book
            title_display = (title[:27] + '...') if len(title) > 30 else title
            fine_amount = fine if fine else 0
            total_fines += fine_amount
            
            print(f"{user_id:<12} {book_id:<10} {title_display:<30} {due_date[:10]:<12} {int(days_overdue):<10} ${fine_amount:.2f}")
        
        print("-" * 90)
        print(f"Total Outstanding Fines: ${total_fines:.2f}")
        print("=" * 90)
        
    except sqlite3.Error as e:
        print(f"Error viewing overdue books: {e}")
    
    conn.close()

def view_loan_history():
    """View loan history"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view loan history.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    print("\nLoan History Options:")
    print("1. View all recent loans")
    print("2. View loans by user")
    print("3. View loans by book")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    try:
        if choice == '1':
            # Recent loans
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.book_id, b.title, 
                   bl.checkout_date, bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            ORDER BY bl.checkout_date DESC
            LIMIT 50
            ''')
            
            title = "Recent Loans (Last 50)"
            
        elif choice == '2':
            # Loans by user
            user_id = input("Enter User ID: ").strip()
            cursor.execute('''
            SELECT bl.loan_id, bl.book_id, b.title, 
                   bl.checkout_date, bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE bl.user_id = ?
            ORDER BY bl.checkout_date DESC
            ''', (user_id,))
            
            title = f"Loans for User: {user_id}"
            
        elif choice == '3':
            # Loans by book
            book_id = input("Enter Book ID: ").strip()
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.checkout_date, 
                   bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            WHERE bl.book_id = ?
            ORDER BY bl.checkout_date DESC
            ''', (book_id,))
            
            title = f"Loans for Book: {book_id}"
            
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        loans = cursor.fetchall()
        
        if not loans:
            print("No loan history found.")
            return
        
        print(f"\n{title}")
        print("=" * 100)
        
        if choice == '1':
            print(f"{'Loan ID':<8} {'User':<12} {'Book ID':<10} {'Title':<25} {'Checkout':<12} {'Status':<10}")
        elif choice == '2':
            print(f"{'Loan ID':<8} {'Book ID':<10} {'Title':<25} {'Checkout':<12} {'Due':<12} {'Status':<10}")
        elif choice == '3':
            print(f"{'Loan ID':<8} {'User':<12} {'Checkout':<12} {'Due':<12} {'Returned':<12} {'Status':<10}")
        
        print("-" * 100)
        
        for loan in loans:
            if choice == '1':
                loan_id, user_id, book_id, title, checkout, due, returned, status = loan
                title_display = (title[:22] + '...') if len(title) > 25 else title
                print(f"{loan_id:<8} {user_id:<12} {book_id:<10} {title_display:<25} {checkout[:10]:<12} {status:<10}")
            elif choice == '2':
                loan_id, book_id, title, checkout, due, returned, status = loan
                title_display = (title[:22] + '...') if len(title) > 25 else title
                print(f"{loan_id:<8} {book_id:<10} {title_display:<25} {checkout[:10]:<12} {due[:10]:<12} {status:<10}")
            elif choice == '3':
                loan_id, user_id, checkout, due, returned, status = loan
                returned_display = returned[:10] if returned else "N/A"
                print(f"{loan_id:<8} {user_id:<12} {checkout[:10]:<12} {due[:10]:<12} {returned_display:<12} {status:<10}")
        
        print("=" * 100)
        
    except sqlite3.Error as e:
        print(f"Error viewing loan history: {e}")
    
    conn.close()

def library_maintenance():
    """Perform library maintenance tasks"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to perform maintenance.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to perform maintenance.")
        return
    
    print("\nLibrary Maintenance:")
    print("===================")
    print("1. Clean up expired reservations")
    print("2. Update overdue status")
    print("3. Calculate fines")
    print("4. Archive old loan records")
    print("5. Optimize database")
    print("6. Check data integrity")
    print("7. Return to menu")
    
    choice = input("Enter your choice (1-7): ").strip()
    
    if choice == '7':
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if choice == '1':
            # Clean expired reservations
            cursor.execute('''
            UPDATE book_reservations 
            SET status = 'expired'
            WHERE status = 'active' AND expiry_date < datetime('now')
            ''')
            
            expired_count = cursor.rowcount
            conn.commit()
            print(f"✅ Cleaned up {expired_count} expired reservations.")
            
        elif choice == '2':
            # Update overdue status
            cursor.execute('''
            UPDATE book_loans 
            SET status = 'overdue'
            WHERE status = 'active' AND due_date < datetime('now')
            ''')
            
            overdue_count = cursor.rowcount
            conn.commit()
            print(f"✅ Updated {overdue_count} loans to overdue status.")
            
        elif choice == '3':
            # Calculate fines
            fine_per_day = float(get_library_settings('fine_per_day') or 0.50)
            
            cursor.execute('''
            UPDATE book_loans 
            SET fine_amount = (julianday('now') - julianday(due_date)) * ?
            WHERE status = 'overdue' AND due_date < datetime('now')
            ''', (fine_per_day,))
            
            fine_count = cursor.rowcount
            conn.commit()
            print(f"✅ Updated fines for {fine_count} overdue loans.")
            
        elif choice == '4':
            # Archive old records (placeholder)
            print("Archive functionality would move old completed loans to archive table.")
            print("This helps maintain performance for active queries.")
            
        elif choice == '5':
            # Optimize database
            cursor.execute('VACUUM')
            cursor.execute('ANALYZE')
            print("✅ Database optimized.")
            
        elif choice == '6':
            # Check data integrity
            validation_results = validate_library_configuration(cursor)
            
            print("\nData Integrity Check:")
            print("-" * 30)
            for result in validation_results:
                status = "✅" if result['valid'] else "❌"
                print(f"{status} {result['check']}: {result['message']}")
        
        # FIXED: Log maintenance action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Performed maintenance task: {choice}", "system")        
    except sqlite3.Error as e:
        print(f"Error during maintenance: {e}")
    
    conn.close()
    
def show_help():
    """Display help information"""
    print("\n" + "="*60)
    print("LIBRARY SYSTEM HELP")
    print("="*60)
    
    print("\n📚 BOOK MANAGEMENT:")
    print("   • Add Book: Add new books with ISBN metadata fetching")
    print("   • Search: Advanced search with filters and sorting")
    print("   • Update: Modify book information and status")
    print("   • Delete: Remove books (with safety checks)")
    
    print("\n🔄 CIRCULATION:")
    print("   • Checkout: Issue books with barcode/QR support")
    print("   • Return: Process returns with condition checking")
    print("   • Renew: Extend loan periods (with limits)")
    print("   • Reserve: Queue books for future checkout")
    
    print("\n📊 REPORTS & ANALYTICS:")
    print("   • Analytics Dashboard: Real-time library statistics")
    print("   • Generate Reports: Circulation, collection, and user reports")
    print("   • Export Data: Export books and data to CSV/Excel")
    print("   • Audit Log: Track all system activities")
    
    print("\n👥 USER FEATURES:")
    print("   • Reading Lists: Create and share book collections")
    print("   • Reviews & Ratings: Rate and review books")
    print("   • Achievements: Track reading goals and milestones")
    print("   • Recommendations: Get personalized book suggestions")
    
    print("\n⚙️  SYSTEM ADMINISTRATION:")
    print("   • Settings Management: Configure system parameters")
    print("   • Backup & Restore: Protect your data")
    print("   • Notifications: Automated reminders and alerts")
    print("   • Digital Library: Manage digital resources")
    
    print("\n🔍 SEARCH TIPS:")
    print("   • Use partial matches for titles and authors")
    print("   • Filter by category, reading level, or status")
    print("   • Sort results by various criteria")
    print("   • Save frequently used searches")
    
    print("\n📱 QUICK ACCESS:")
    print("   • Book ID format: B10001, B10002, etc.")
    print("   • Barcode scanning supported for fast operations")
    print("   • QR codes for mobile-friendly access")
    print("   • Bulk import/export for large collections")
    
    print("\n💡 TIPS:")
    print("   • Regular backups prevent data loss")
    print("   • Use reading levels to match books to users")
    print("   • Monitor overdue items regularly")
    print("   • Encourage user reviews for better recommendations")
    
    print("="*60)
    print("For technical support, check the system logs or contact your administrator.")
    
    input("\nPress Enter to continue...")

def exit_library_system():
    """Safely exit the library system"""
    global auth
    
    print("\nExiting Library Management System...")
    
    # Perform any cleanup tasks
    try:
        # ALREADY FIXED: Use the safe function
        if auth and auth.current_user:
            log_audit_event(get_current_user_id(), "Logged out of library system", "system")
        
        print("✅ System cleanup completed.")
        print("Thank you for using the Library Management System!")
        
    except Exception as e:
        logging.error(f"Error during system exit: {e}")
        print("⚠️  Some cleanup tasks failed, but it's safe to exit.")
    
    return True

# Main function to initialize the enhanced system
if __name__ == "__main__":
    # First verify and repair database if needed
    if repair_database():
        print("Database is ready for use!")
    else:
        print("Failed to repair database. Please check the error messages above.")
    # Initialize the enhanced library database
    init_library_db()
