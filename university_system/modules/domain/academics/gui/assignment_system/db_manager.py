"""Database schema and migration management"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths
from collections import deque



class DatabaseManager:
    """Database schema and migration management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def ensure_database_exists(self):
        """Ensure database tables exist, create them if they don't"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if core tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['users', 'students', 'modules', 'assignments', 'assignment_submissions']

            # Always ensure latest schema is applied
            self.create_database_tables(cursor)
            self.migrate_notifications_table(cursor)
            self.migrate_peer_review_tables(cursor)
            self.migrate_messages_table(cursor)
            self.ensure_assessment_schema(cursor)
            conn.commit()

            conn.close()

        except Exception as e:
            print(f"Error initializing database: {e}")

    def ensure_assessment_schema(self, cursor):
        """Ensure assessments table contains required columns."""
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT NOT NULL,
                assessment_type TEXT NOT NULL,
                module_code TEXT NOT NULL,
                max_points REAL NOT NULL,
                weight REAL NOT NULL,
                due_date TEXT,
                date_created TEXT DEFAULT (datetime('now')),
                description TEXT,
                rubric TEXT
            )
            ''')

            cursor.execute("PRAGMA table_info(assessments)")
            columns = {col[1] for col in cursor.fetchall()}

            column_defs = {
                'duration_minutes': 'INTEGER DEFAULT 0',
                'status': "TEXT DEFAULT 'Active'",
                'updated_at': "TEXT DEFAULT (datetime('now'))"
            }

            for column, definition in column_defs.items():
                if column not in columns:
                    cursor.execute(f"ALTER TABLE assessments ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                print(f"Assessment schema update warning: {exc}")

    def migrate_notifications_table(self, cursor):
        """Migrate notifications table to add missing columns for module management compatibility"""
        try:
            # Check if notifications table exists and has the required columns
            cursor.execute("PRAGMA table_info(notifications)")
            columns = [column[1] for column in cursor.fetchall()]

            missing_columns = []
            required_columns = {
                'assignment_id': 'INTEGER',
                'recipient_type': 'TEXT',
                'recipient_id': 'TEXT',
                'notification_type': 'TEXT DEFAULT "info"',
                'sent': 'BOOLEAN DEFAULT 0',
                'created_date': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }

            for column_name, column_def in required_columns.items():
                if column_name not in columns:
                    missing_columns.append((column_name, column_def))

            # Add missing columns
            for column_name, column_def in missing_columns:
                try:
                    cursor.execute(f'ALTER TABLE notifications ADD COLUMN {column_name} {column_def}')
                    print(f"Added column {column_name} to notifications table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        print(f"Warning: Could not add column {column_name}: {e}")

        except Exception as e:
            print(f"Error migrating notifications table: {e}")

    def migrate_messages_table(self, cursor):
        """Ensure messages table includes required columns."""
        try:
            cursor.execute("PRAGMA table_info(messages)")
            columns = {column[1] for column in cursor.fetchall()}

            if not columns:
                return

            required_columns = {
                'is_read': 'INTEGER DEFAULT 0',
                'is_archived': 'INTEGER DEFAULT 0',
                'is_deleted_by_sender': 'INTEGER DEFAULT 0',
                'is_deleted_by_recipient': 'INTEGER DEFAULT 0',
                'sent_at': "TEXT DEFAULT datetime('now')",
                'read_at': 'TEXT'
            }

            for name, definition in required_columns.items():
                if name not in columns:
                    cursor.execute(f'ALTER TABLE messages ADD COLUMN {name} {definition}')

        except Exception as e:
            print(f"Error migrating messages table: {e}")

    def migrate_peer_review_tables(self, cursor):
        """Ensure peer review tables contain necessary columns."""
        try:
            cursor.execute('PRAGMA table_info(peer_review_assignments)')
            pra_columns = {col[1] for col in cursor.fetchall()}

            if 'reviewee_id' not in pra_columns:
                cursor.execute('ALTER TABLE peer_review_assignments ADD COLUMN reviewee_id TEXT')
            if 'submission_id' not in pra_columns:
                cursor.execute('ALTER TABLE peer_review_assignments ADD COLUMN submission_id INTEGER')
            if 'created_at' not in pra_columns:
                cursor.execute('ALTER TABLE peer_review_assignments ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

            cursor.execute('PRAGMA table_info(peer_reviews)')
            pr_columns = {col[1] for col in cursor.fetchall()}
            if 'reviewee_id' not in pr_columns:
                cursor.execute('ALTER TABLE peer_reviews ADD COLUMN reviewee_id TEXT')
            if 'created_at' not in pr_columns:
                cursor.execute('ALTER TABLE peer_reviews ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        except sqlite3.OperationalError as e:
            print(f"Peer review migration warning: {e}")
        except Exception as e:
            print(f"Error migrating peer review tables: {e}")

    def create_database_tables(self, cursor):
        """Create all required database tables"""
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student', 'instructor', 'admin')),
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            user_id INTEGER UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            enrollment_date DATE,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Modules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT NOT NULL,
            description TEXT,
            credits INTEGER DEFAULT 0,
            instructor_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (instructor_id) REFERENCES users (id)
        )
        ''')
        
        # Student modules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            enrollment_date DATE DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'enrolled',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            UNIQUE(student_id, module_code)
        )
        ''')
        
        # Assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            instructions TEXT,
            due_date TIMESTAMP NOT NULL,
            max_marks INTEGER NOT NULL,
            file_types_allowed TEXT,
            max_file_size_mb INTEGER DEFAULT 10,
            assignment_type TEXT DEFAULT 'individual',
            group_size_min INTEGER DEFAULT 1,
            group_size_max INTEGER DEFAULT 1,
            allow_late_submission BOOLEAN DEFAULT 1,
            late_penalty_per_day REAL DEFAULT 0,
            auto_release_grades BOOLEAN DEFAULT 0,
            peer_review_enabled BOOLEAN DEFAULT 0,
            rubric_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Assignment submissions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            submission_date TIMESTAMP NOT NULL,
            file_path TEXT,
            file_name TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            status TEXT DEFAULT 'submitted',
            grade REAL,
            feedback TEXT,
            late_submission BOOLEAN DEFAULT 0,
            late_days INTEGER DEFAULT 0,
            version_number INTEGER DEFAULT 1,
            is_final_submission BOOLEAN DEFAULT 1,
            graded_by INTEGER,
            graded_date TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (graded_by) REFERENCES users (id)
        )
        ''')
        
        # Notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assignment_id INTEGER,
            recipient_type TEXT,
            recipient_id TEXT,
            notification_type TEXT DEFAULT 'info',
            sent BOOLEAN DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
        ''')
        
        # Extension requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS extension_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            new_due_date TIMESTAMP NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            reviewed_date TIMESTAMP,
            review_comments TEXT,
            approved_extension_days INTEGER DEFAULT 0,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (reviewed_by) REFERENCES users (id)
        )
        ''')
    
        # Peer reviews table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewee_id TEXT NOT NULL,
            overall_score REAL,
            review_text TEXT,
            status TEXT DEFAULT 'pending',
            review_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
            FOREIGN KEY (reviewee_id) REFERENCES students (student_id)
        )
        ''')
    
        # Peer review criteria table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_review_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            criteria_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT,
            FOREIGN KEY (review_id) REFERENCES peer_reviews (id)
        )
        ''')
    
        # Peer review assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_review_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewee_id TEXT NOT NULL,
            submission_id INTEGER,
            due_date TIMESTAMP,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
            FOREIGN KEY (reviewee_id) REFERENCES students (student_id),
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
        )
        ''')
    
        # Rubrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            total_points REAL NOT NULL DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
    
        # Rubric criteria table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubric_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric_id INTEGER NOT NULL,
            criteria_name TEXT NOT NULL,
            description TEXT,
            max_points REAL NOT NULL,
            weight REAL DEFAULT 1.0,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (rubric_id) REFERENCES rubrics (id) ON DELETE CASCADE
        )
        ''')
    
        # Messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            message TEXT,
            content TEXT,
            attachment_path TEXT,
            assignment_id INTEGER,
            is_read INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            is_deleted_by_sender INTEGER DEFAULT 0,
            is_deleted_by_recipient INTEGER DEFAULT 0,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            read_at TEXT,
            reply_to INTEGER,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reply_to) REFERENCES messages (id)
        )
        ''')
    
        # Analytics cache table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            cache_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
        ''')
    
        # Audit log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
    
        # Database tables created - ready to use existing data
        # Note: Sample data insertion removed - using actual database data only
    

    def insert_sample_data(self, cursor):
        """Insert sample data for testing"""
        
        # Sample users
        cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, email, password_hash, role, first_name, last_name)
        VALUES (1, 'admin', 'admin@university.edu', 'admin_hash', 'admin', 'System', 'Administrator')
        ''')
        
        cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, email, password_hash, role, first_name, last_name)
        VALUES (2, 'instructor1', 'instructor1@university.edu', 'inst_hash', 'instructor', 'John', 'Smith')
        ''')
        
        # Sample students
        cursor.execute('''
        INSERT OR IGNORE INTO students (student_id, user_id, first_name, last_name, email, enrollment_date)
        VALUES ('STU001', 1, 'Test', 'Student', 'student@university.edu', '2024-01-15')
        ''')
        
        # Sample modules
        cursor.execute('''
        INSERT OR IGNORE INTO modules (module_code, module_name, description, credits, instructor_id)
        VALUES ('CS101', 'Introduction to Computer Science', 'Basic programming concepts', 3, 2)
        ''')
        
        cursor.execute('''
        INSERT OR IGNORE INTO modules (module_code, module_name, description, credits, instructor_id)
        VALUES ('CS201', 'Data Structures', 'Advanced programming topics', 4, 2)
        ''')
        
        # Sample enrollment
        cursor.execute('''
        INSERT OR IGNORE INTO student_modules (student_id, module_code)
        VALUES ('STU001', 'CS101')
        ''')
        
        cursor.execute('''
        INSERT OR IGNORE INTO student_modules (student_id, module_code)
        VALUES ('STU001', 'CS201')
        ''')
    

    def _ensure_notifications_table(self):
        """Ensure notifications table exists and has required columns"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                # Create new table with standard schema
                cursor.execute('''
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    message TEXT NOT NULL,
                    type TEXT DEFAULT 'info',
                    is_read BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assignment_id INTEGER,
                    recipient_type TEXT,
                    recipient_id TEXT,
                    notification_type TEXT DEFAULT 'info',
                    sent BOOLEAN DEFAULT 0,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
                )
                ''')
            else:
                # Ensure all required columns exist (for legacy tables)
                cursor.execute("PRAGMA table_info(notifications)")
                columns = {col[1] for col in cursor.fetchall()}

                # Map old column names to new ones with aliases or add missing columns
                if 'notification_id' in columns and 'id' not in columns:
                    # Legacy schema - add id column as alias or just note to use notification_id
                    print("Note: notifications table uses notification_id instead of id")

                required_columns = {
                    'type': 'TEXT DEFAULT "info"',
                    'is_read': 'BOOLEAN DEFAULT 0',
                    'assignment_id': 'INTEGER',
                    'recipient_type': 'TEXT',
                    'recipient_id': 'TEXT',
                    'notification_type': 'TEXT DEFAULT "info"',
                    'sent': 'BOOLEAN DEFAULT 0'
                }

                for col_name, col_def in required_columns.items():
                    if col_name not in columns:
                        try:
                            cursor.execute(f'ALTER TABLE notifications ADD COLUMN {col_name} {col_def}')
                        except Exception as e:
                            print(f"Could not add column {col_name}: {e}")

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error ensuring notifications table: {e}")
    

    def _ensure_messages_table(self):
        """Ensure messages table exists in the database"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                message TEXT,
                content TEXT,
                attachment_path TEXT,
                assignment_id INTEGER,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_deleted_by_sender INTEGER DEFAULT 0,
                is_deleted_by_recipient INTEGER DEFAULT 0,
                sent_at TEXT NOT NULL,
                read_at TEXT,
                reply_to INTEGER,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id),
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (reply_to) REFERENCES messages (id)
            )
            ''')
    
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error ensuring messages table: {e}")
    
