from education_system.systems.university.infrastructure.database.db import sqlite3, ensure_parent_dir
from education_system.systems.university.infrastructure.sql_safety import validate_table_name, validate_identifier  # nosec B608
from education_system.systems.university.domain.academics.services.assignments.core.constants import SUBMISSION_SUBDIRS
from pathlib import Path
import os


class DatabaseMixin:
    """Mixin providing database initialization and directory setup."""

    def _init_directories(self):
        """Initialize the submission directory structure"""
        try:
            # Create main submission directory
            Path(self.submission_dir).mkdir(exist_ok=True)

            # Create subdirectories for organization
            for subdir in SUBMISSION_SUBDIRS:
                Path(os.path.join(self.submission_dir, subdir)).mkdir(exist_ok=True)

        except Exception as e:
            print(f"Error creating directories: {e}")

    def _init_db(self):
        """Initialize database tables for assignment submission with all new features"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Original assignments table (enhanced)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT NOT NULL,
                max_marks INTEGER DEFAULT 100,
                file_types_allowed TEXT,
                max_file_size_mb INTEGER DEFAULT 10,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                assignment_type TEXT DEFAULT 'individual',
                allow_late_submission INTEGER DEFAULT 1,
                late_penalty_per_day REAL DEFAULT 0,
                instructions TEXT,
                rubric_id INTEGER,
                auto_release_grades INTEGER DEFAULT 0,
                peer_review_enabled INTEGER DEFAULT 0,
                group_size_min INTEGER DEFAULT 1,
                group_size_max INTEGER DEFAULT 1,
                template_id INTEGER,
                FOREIGN KEY (module_code) REFERENCES modules (module_code),
                FOREIGN KEY (created_by) REFERENCES users (id),
                FOREIGN KEY (rubric_id) REFERENCES rubrics (id),
                FOREIGN KEY (template_id) REFERENCES assignment_templates (id)
            )
            ''')

            # Enhanced submissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                group_id INTEGER,
                submission_date TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_hash TEXT NOT NULL,
                status TEXT DEFAULT 'submitted',
                late_submission INTEGER DEFAULT 0,
                late_days INTEGER DEFAULT 0,
                grade REAL,
                graded_by INTEGER,
                graded_date TEXT,
                feedback TEXT,
                is_final_submission INTEGER DEFAULT 1,
                version_number INTEGER DEFAULT 1,
                ip_address TEXT,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (graded_by) REFERENCES users (id)
            )
            ''')

            # Grading and feedback tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rubrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                total_points REAL NOT NULL,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rubric_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rubric_id INTEGER NOT NULL,
                criteria_name TEXT NOT NULL,
                criteria_description TEXT,
                max_points REAL NOT NULL,
                weight REAL DEFAULT 1.0,
                order_index INTEGER DEFAULT 0,
                FOREIGN KEY (rubric_id) REFERENCES rubrics (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                rubric_criteria_id INTEGER,
                assessment_id INTEGER,
                points_earned REAL NOT NULL,
                max_points REAL NOT NULL,
                percentage REAL NOT NULL,
                feedback TEXT,
                graded_by INTEGER,
                graded_date TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
                FOREIGN KEY (rubric_criteria_id) REFERENCES rubric_criteria (id),
                FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
                FOREIGN KEY (graded_by) REFERENCES users (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Group assignment tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (created_by) REFERENCES students (student_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TEXT NOT NULL,
                contribution_score REAL DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

            # Peer review tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS peer_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL,
                reviewee_id TEXT NOT NULL,
                submission_id INTEGER NOT NULL,
                review_date TEXT NOT NULL,
                overall_score REAL,
                review_text TEXT,
                is_anonymous INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
                FOREIGN KEY (reviewee_id) REFERENCES students (student_id),
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS peer_review_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                criteria_name TEXT NOT NULL,
                score REAL NOT NULL,
                comment TEXT,
                FOREIGN KEY (review_id) REFERENCES peer_reviews (id)
            )
            ''')

            # Notification system tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                scheduled_for TEXT,
                assignment_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (assignment_id) REFERENCES assignments (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                email_enabled INTEGER DEFAULT 1,
                sms_enabled INTEGER DEFAULT 0,
                in_app_enabled INTEGER DEFAULT 1,
                advance_notice_days INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Extension request system
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS extension_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                requested_date TEXT NOT NULL,
                new_due_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                supporting_documents TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                reviewed_date TEXT,
                reviewer_comments TEXT,
                approved_extension_days INTEGER DEFAULT 0,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (reviewed_by) REFERENCES users (id)
            )
            ''')

            # Template system
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                template_data TEXT NOT NULL,
                category TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Calendar and scheduling: calendar_events (Schema A) removed —
            # folded into the single canonical academic_calendar_events table.

            # Analytics and reporting
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                parameters TEXT,
                data TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            ''')

            # Audit and security
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id INTEGER,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
            )
            ''')

            # Messages and communication
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                assignment_id INTEGER,
                is_read INTEGER DEFAULT 0,
                sent_at TEXT NOT NULL,
                reply_to INTEGER,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id),
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (reply_to) REFERENCES messages (id)
            )
            ''')

            # Backup and recovery
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                size_bytes INTEGER,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'completed',
                error_message TEXT
            )
            ''')

            # Update existing tables with missing columns
            self._update_existing_tables(cursor)

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            print(f"Database initialization error: {e}")

    def _update_existing_tables(self, cursor):
        """Update existing tables with new columns"""
        updates = [
            ('assignments', 'assignment_type', 'TEXT DEFAULT "individual"'),
            ('assignments', 'allow_late_submission', 'INTEGER DEFAULT 1'),
            ('assignments', 'late_penalty_per_day', 'REAL DEFAULT 0'),
            ('assignments', 'instructions', 'TEXT'),
            ('assignments', 'rubric_id', 'INTEGER'),
            ('assignments', 'auto_release_grades', 'INTEGER DEFAULT 0'),
            ('assignments', 'peer_review_enabled', 'INTEGER DEFAULT 0'),
            ('assignments', 'group_size_min', 'INTEGER DEFAULT 1'),
            ('assignments', 'group_size_max', 'INTEGER DEFAULT 1'),
            ('assignment_submissions', 'group_id', 'INTEGER'),
            ('assignment_submissions', 'late_days', 'INTEGER DEFAULT 0'),
            ('assignment_submissions', 'grade', 'REAL'),
            ('assignment_submissions', 'graded_by', 'INTEGER'),
            ('assignment_submissions', 'graded_date', 'TEXT'),
            ('assignment_submissions', 'feedback', 'TEXT'),
            ('assignment_submissions', 'is_final_submission', 'INTEGER DEFAULT 1'),
            ('assignment_submissions', 'version_number', 'INTEGER DEFAULT 1'),
            ('assignment_submissions', 'ip_address', 'TEXT'),
        ]

        for table, column, definition in updates:
            try:
                safe_table = validate_table_name(table)
                safe_column = validate_identifier(column, "column")
                cursor.execute("ALTER TABLE [" + safe_table + "] ADD COLUMN [" + safe_column + "] " + definition)
            except sqlite3.Error:
                # Column might already exist
                pass
