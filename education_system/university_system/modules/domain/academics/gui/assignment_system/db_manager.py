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
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.core import paths
from collections import deque
from education_system.university_system.core.sql_safety import (
    safe_alter_table_add_column,
    SQLIdentifierError
)



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
            self.migrate_assignments_table(cursor)
            self.create_new_feature_tables(cursor)
            self.migrate_ta_assignments_table(cursor)
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
                    try:
                        # Use safe_alter_table_add_column to prevent SQL injection
                        safe_alter_table_add_column(
                            table_name='assessments',
                            column_name=column,
                            column_type=definition,
                            conn=cursor.connection,
                            if_not_exists=True
                        )
                    except (SQLIdentifierError, sqlite3.Error) as e:
                        print(f"Could not add column {column}: {e}")
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
                'created_date': 'DATETIME'
            }

            for column_name, column_def in required_columns.items():
                if column_name not in columns:
                    missing_columns.append((column_name, column_def))

            # Add missing columns
            for column_name, column_def in missing_columns:
                try:
                    # Use safe_alter_table_add_column to prevent SQL injection
                    safe_alter_table_add_column(
                        table_name='notifications',
                        column_name=column_name,
                        column_type=column_def,
                        conn=cursor.connection,
                        if_not_exists=True
                    )
                    # For created_date, set default value with UPDATE for existing rows
                    if column_name == 'created_date':
                        cursor.execute("UPDATE notifications SET created_date = CURRENT_TIMESTAMP WHERE created_date IS NULL")
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
                    try:
                        # Use safe_alter_table_add_column to prevent SQL injection
                        safe_alter_table_add_column(
                            table_name='messages',
                            column_name=name,
                            column_type=definition,
                            conn=cursor.connection,
                            if_not_exists=True
                        )
                    except (SQLIdentifierError, sqlite3.Error) as e:
                        print(f"Could not add column {name}: {e}")

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
                cursor.execute('ALTER TABLE peer_review_assignments ADD COLUMN created_at TIMESTAMP')
                cursor.execute('UPDATE peer_review_assignments SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')

            cursor.execute('PRAGMA table_info(peer_reviews)')
            pr_columns = {col[1] for col in cursor.fetchall()}
            if 'reviewee_id' not in pr_columns:
                cursor.execute('ALTER TABLE peer_reviews ADD COLUMN reviewee_id TEXT')
            if 'created_at' not in pr_columns:
                cursor.execute('ALTER TABLE peer_reviews ADD COLUMN created_at TIMESTAMP')
                cursor.execute('UPDATE peer_reviews SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')

        except sqlite3.OperationalError as e:
            print(f"Peer review migration warning: {e}")
        except Exception as e:
            print(f"Error migrating peer review tables: {e}")

    def migrate_assignments_table(self, cursor):
        """Ensure assignments table has template_id column for template tracking"""
        try:
            cursor.execute("PRAGMA table_info(assignments)")
            columns = {col[1] for col in cursor.fetchall()}

            # Add template_id column if it doesn't exist
            if 'template_id' not in columns:
                cursor.execute('ALTER TABLE assignments ADD COLUMN template_id INTEGER')
                print("Added template_id column to assignments table")

        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Warning: Could not add template_id column: {e}")
        except Exception as e:
            print(f"Error migrating assignments table: {e}")

    def migrate_ta_assignments_table(self, cursor):
        """Ensure ta_assignments table has hours_per_week column"""
        try:
            cursor.execute("PRAGMA table_info(ta_assignments)")
            columns = {col[1] for col in cursor.fetchall()}
            if not columns:
                return
            if 'hours_per_week' not in columns:
                cursor.execute('ALTER TABLE ta_assignments ADD COLUMN hours_per_week REAL DEFAULT 0')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Warning: Could not add hours_per_week column: {e}")
        except Exception:
            pass

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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            due_date TEXT NOT NULL,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            submission_date TEXT NOT NULL,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            assignment_id INTEGER,
            recipient_type TEXT,
            recipient_id TEXT,
            notification_type TEXT DEFAULT 'info',
            sent BOOLEAN DEFAULT 0,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
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
            requested_date TEXT DEFAULT CURRENT_TIMESTAMP,
            new_due_date TEXT NOT NULL,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
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
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Database tables created - ready to use existing data
        # Note: Sample data insertion removed - using actual database data only

    def create_new_feature_tables(self, cursor):
        """Create tables for new assignment/grading features"""

        # ── Auto-Grading & Question Banks ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            module_code TEXT,
            description TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_id INTEGER NOT NULL,
            question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'fill_blank', 'coding')),
            question_text TEXT NOT NULL,
            options_json TEXT,
            correct_answer TEXT,
            points REAL DEFAULT 1.0,
            difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
            topic TEXT,
            time_limit_seconds INTEGER,
            test_cases_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bank_id) REFERENCES question_banks (id) ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            submission_id INTEGER,
            answer_text TEXT,
            is_correct INTEGER DEFAULT 0,
            points_earned REAL DEFAULT 0,
            time_spent_seconds INTEGER,
            answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
        )
        ''')

        # ── Exam Integrity ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_integrity_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            randomize_questions INTEGER DEFAULT 0,
            randomize_answers INTEGER DEFAULT 0,
            question_count INTEGER,
            time_limit_minutes INTEGER,
            auto_submit INTEGER DEFAULT 1,
            browser_lockdown INTEGER DEFAULT 0,
            proctoring_provider TEXT,
            ip_restriction_enabled INTEGER DEFAULT 0,
            allowed_ips_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_integrity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data_json TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # ── Student Experience ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS submission_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            content TEXT,
            version INTEGER DEFAULT 1,
            file_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS submission_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            assignment_title TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            receipt_hash TEXT,
            email_sent INTEGER DEFAULT 0,
            confirmation_code TEXT,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accessibility_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            extended_time REAL DEFAULT 1.0,
            high_contrast INTEGER DEFAULT 0,
            screen_reader INTEGER DEFAULT 0,
            font_size INTEGER DEFAULT 12,
            extra_settings_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # ── Grade Disputes ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_disputes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER,
            student_id TEXT NOT NULL,
            assignment_id INTEGER NOT NULL,
            original_grade REAL,
            requested_action TEXT,
            reason TEXT NOT NULL,
            evidence_path TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'under_review', 'approved', 'denied')),
            reviewer_id INTEGER,
            reviewer_comments TEXT,
            new_grade REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id)
        )
        ''')

        # ── Late Policies ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS late_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            penalty_type TEXT DEFAULT 'percentage' CHECK (penalty_type IN ('percentage', 'fixed', 'none')),
            penalty_per_day REAL DEFAULT 10.0,
            max_late_days INTEGER DEFAULT 7,
            grace_period_hours INTEGER DEFAULT 0,
            min_grade_floor REAL DEFAULT 0,
            is_default INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_late_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            policy_id INTEGER NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (policy_id) REFERENCES late_policies (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS late_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assignment_id INTEGER,
            used INTEGER DEFAULT 0,
            granted_by INTEGER,
            granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (granted_by) REFERENCES users (id)
        )
        ''')

        # ── Annotations ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS submission_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            line_number INTEGER,
            position_start INTEGER,
            position_end INTEGER,
            comment TEXT NOT NULL,
            category TEXT DEFAULT 'suggestion' CHECK (category IN ('praise', 'suggestion', 'correction', 'question')),
            student_response TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS annotation_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT DEFAULT 'suggestion',
            created_by INTEGER,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # ── Multi-Stage Assignments ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            stage_number INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            description TEXT,
            weight_percent REAL DEFAULT 0,
            deadline TEXT,
            feedback_required INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stage_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            content TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'reviewed', 'approved')),
            feedback TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            FOREIGN KEY (stage_id) REFERENCES assignment_stages (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            url TEXT NOT NULL,
            link_type TEXT DEFAULT 'other' CHECK (link_type IN ('github', 'google_docs', 'figma', 'other')),
            is_validated INTEGER DEFAULT 0,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # ── Admin Tools ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sis_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT,
            records_synced INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            synced_by INTEGER,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
            details_json TEXT,
            FOREIGN KEY (synced_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integrity_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assignment_id INTEGER,
            case_type TEXT DEFAULT 'other' CHECK (case_type IN ('plagiarism', 'cheating', 'collusion', 'other')),
            description TEXT,
            evidence_path TEXT,
            status TEXT DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'dismissed')),
            outcome TEXT,
            penalty TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER,
            student_id TEXT,
            assignment_id INTEGER,
            old_grade REAL,
            new_grade REAL,
            changed_by INTEGER,
            reason TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (changed_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_accommodations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            accommodation_type TEXT DEFAULT 'other' CHECK (accommodation_type IN ('extended_time', 'alt_format', 'screen_reader', 'large_text', 'other')),
            details TEXT,
            time_multiplier REAL DEFAULT 1.0,
            is_active INTEGER DEFAULT 1,
            approved_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (approved_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ta_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            section_id TEXT,
            module_code TEXT,
            role TEXT DEFAULT 'ta' CHECK (role IN ('ta', 'lead_ta', 'grader', 'co_instructor')),
            hours_per_week REAL DEFAULT 0,
            can_grade INTEGER DEFAULT 1,
            can_create_assignments INTEGER DEFAULT 0,
            can_view_analytics INTEGER DEFAULT 1,
            assigned_by INTEGER,
            assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (assigned_by) REFERENCES users (id)
        )
        ''')

        # ── AI-Assisted Features ──

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_feedback_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assignment_id INTEGER,
            draft_text TEXT,
            feedback_json TEXT,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS practice_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT,
            source_material TEXT,
            question_text TEXT NOT NULL,
            answer TEXT,
            question_type TEXT DEFAULT 'mcq',
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collusion_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id_1 TEXT NOT NULL,
            student_id_2 TEXT NOT NULL,
            similarity_score REAL,
            analysis_json TEXT,
            flagged INTEGER DEFAULT 0,
            reviewed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id_1) REFERENCES students (student_id),
            FOREIGN KEY (student_id_2) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS late_pass_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assignment_id INTEGER,
            recommendation TEXT DEFAULT 'deny' CHECK (recommendation IN ('grant', 'deny')),
            confidence_score REAL,
            reasoning_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
        ''')

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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    assignment_id INTEGER,
                    recipient_type TEXT,
                    recipient_id TEXT,
                    notification_type TEXT DEFAULT 'info',
                    sent BOOLEAN DEFAULT 0,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
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
                            # Use safe_alter_table_add_column to prevent SQL injection
                            safe_alter_table_add_column(
                                table_name='notifications',
                                column_name=col_name,
                                column_type=col_def,
                                conn=cursor.connection,
                                if_not_exists=True
                            )
                        except (SQLIdentifierError, sqlite3.Error) as e:
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

