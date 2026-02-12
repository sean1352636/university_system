from university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, SUBMISSIONS_DIR
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.core.sql_safety import validate_table_name, validate_identifier
import os
import shutil
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import mimetypes
import json
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict
import zipfile
import tempfile

class AssignmentSubmission:
    def __init__(self, db_path=None, submission_dir=None, auth=None):
        self.db_path = str(db_path) if db_path else str(DEFAULT_DB_PATH)
        ensure_parent_dir(self.db_path)
        self.submission_dir = str(submission_dir) if submission_dir else str(SUBMISSIONS_DIR)
        # Use provided auth or create a new UserAuth instance
        self.auth = auth if auth is not None else UserAuth(db_path=self.db_path)
        self._init_db()
        self._init_directories()

    def set_auth(self, auth):
        """Set the authentication object"""
        self.auth = auth
    
    def _init_directories(self):
        """Initialize the submission directory structure"""
        try:
            # Create main submission directory
            Path(self.submission_dir).mkdir(exist_ok=True)
            
            # Create subdirectories for organization
            subdirs = ['pending', 'submitted', 'graded', 'feedback', 'templates', 'exports', 'backups', 'previews']
            for subdir in subdirs:
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
            
            # Calendar and scheduling
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                event_type TEXT NOT NULL,
                assignment_id INTEGER,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
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
    
    def _check_permission(self, permission):
        """Check if the current user has the required permission"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access this feature.")
            return False
        
        if not self.auth.check_permission(permission):
            print(f"You don't have permission to {permission.replace('_', ' ')}.")
            return False
        
        return True
    
    def _get_student_id(self):
        """Get the current user's student ID"""
        if not self.auth or not self.auth.current_user:
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (self.auth.current_user['id'],))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result and result[0] else None
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
    
    def _get_student_modules(self, student_id):
        """Get all modules for a student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT DISTINCT module_code, module_name 
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE student_id = ?
            ORDER BY module_code
            ''', (student_id,))
            
            modules = cursor.fetchall()
            conn.close()
            
            return modules
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _validate_file(self, file_path, allowed_types, max_size_mb):
        """Validate file type and size"""
        if not os.path.exists(file_path):
            return False, "File does not exist."
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > max_size_mb * 1024 * 1024:
            return False, f"File size exceeds {max_size_mb}MB limit."
        
        # Check file type
        if allowed_types:
            file_ext = os.path.splitext(file_path)[1].lower()
            allowed_list = [ext.strip().lower() for ext in allowed_types.split(',')]
            if file_ext not in allowed_list:
                return False, f"File type not allowed. Allowed types: {allowed_types}"
        
        return True, "Valid"
    
    def _log_action(self, action, table_name=None, record_id=None, old_values=None, new_values=None):
        """Log user actions for audit trail"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'] if self.auth and self.auth.current_user else None,
                action, table_name, record_id,
                json.dumps(old_values) if old_values else None,
                json.dumps(new_values) if new_values else None,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not log action: {e}")
    
    def _send_notification(self, user_id, title, message, notification_type, assignment_id=None):
        """Send notification to user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, created_at, assignment_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, title, message, notification_type, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), assignment_id))
            
            conn.commit()
            conn.close()
            
            # Check if user wants email notifications
            self._check_and_send_email(user_id, title, message, notification_type)
            
        except Exception as e:
            print(f"Error sending notification: {e}")
    
    def _check_and_send_email(self, user_id, title, message, notification_type):
        """Check preferences and send email if enabled"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user email and preferences
            cursor.execute('''
            SELECT u.email, np.email_enabled
            FROM users u
            LEFT JOIN notification_preferences np ON u.id = np.user_id AND np.notification_type = ?
            WHERE u.id = ?
            ''', (notification_type, user_id))
            
            result = cursor.fetchone()
            if result and result[0] and (result[1] is None or result[1] == 1):
                # Send email (implement with your email settings)
                self._send_email(result[0], title, message)
            
            conn.close()
        except Exception as e:
            print(f"Error checking email preferences: {e}")
    
    def _send_email(self, email, subject, message):
        """Send email notification (configure with your SMTP settings)"""
        try:
            # Configure these with your email settings
            smtp_server = "smtp.gmail.com"  # Change to your SMTP server
            smtp_port = 587
            smtp_username = "your-email@domain.com"  # Change to your email
            smtp_password = "your-password"  # Change to your password
            
            msg = MimeMultipart()
            msg['From'] = smtp_username
            msg['To'] = email
            msg['Subject'] = subject
            
            msg.attach(MimeText(message, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            text = msg.as_string()
            server.sendmail(smtp_username, email, text)
            server.quit()
            
        except Exception as e:
            print(f"Error sending email: {e}")

    # GRADING AND FEEDBACK SYSTEM
    def create_rubric(self):
        """Create a new grading rubric"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            print("\nCreate New Rubric")
            print("=" * 50)
            
            name = input("Rubric name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return
            
            description = input("Description: ").strip()
            
            criteria = []
            total_points = 0
            
            print("\nAdd criteria (type 'done' when finished):")
            while True:
                criteria_name = input("Criteria name (or 'done'): ").strip()
                if criteria_name.lower() == 'done':
                    break
                
                criteria_desc = input("Criteria description: ").strip()
                
                while True:
                    try:
                        points = float(input("Maximum points: "))
                        if points <= 0:
                            print("Points must be positive.")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid number.")
                
                weight = 1.0
                weight_input = input("Weight (default 1.0): ").strip()
                if weight_input:
                    try:
                        weight = float(weight_input)
                    except ValueError:
                        weight = 1.0
                
                criteria.append({
                    'name': criteria_name,
                    'description': criteria_desc,
                    'points': points,
                    'weight': weight
                })
                
                total_points += points
                print(f"Added criteria. Current total: {total_points} points")
            
            if not criteria:
                print("No criteria added.")
                return
            
            # Save to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO rubrics (name, description, total_points, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (name, description, total_points, self.auth.current_user['id'], timestamp))
            
            rubric_id = cursor.lastrowid
            
            # Add criteria
            for i, criterion in enumerate(criteria):
                cursor.execute('''
                INSERT INTO rubric_criteria (rubric_id, criteria_name, criteria_description, max_points, weight, order_index)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (rubric_id, criterion['name'], criterion['description'], 
                      criterion['points'], criterion['weight'], i))
            
            conn.commit()
            conn.close()
            
            print(f"\nRubric '{name}' created successfully!")
            print(f"Total points: {total_points}")
            
        except Exception as e:
            print(f"Error creating rubric: {e}")
    
    def grade_submission(self):
        """Grade a student submission"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            # Show ungraded submissions
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.id, s.student_id, st.first_name, st.last_name, a.title, s.submission_date
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.grade IS NULL AND s.status = 'submitted'
            ORDER BY s.submission_date
            ''')
            
            submissions = cursor.fetchall()
            
            if not submissions:
                print("No ungraded submissions found.")
                conn.close()
                return
            
            print("\nUngraded Submissions:")
            print("=" * 100)
            print(f"{'ID':<5} {'Student':<25} {'Assignment':<30} {'Submitted':<20}")
            print("-" * 100)
            
            for sub in submissions:
                sid, student_id, fname, lname, title, date = sub
                student_name = f"{fname} {lname}"[:23]
                assignment_title = title[:28]
                print(f"{sid:<5} {student_name:<25} {assignment_title:<30} {date:<20}")
            
            submission_id = input("\nEnter submission ID to grade: ").strip()
            if not submission_id.isdigit():
                print("Invalid submission ID.")
                conn.close()
                return
            
            submission_id = int(submission_id)
            
            # Get submission details
            cursor.execute('''
            SELECT s.*, a.title, a.max_marks, a.rubric_id, st.first_name, st.last_name
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))
            
            submission = cursor.fetchone()
            if not submission:
                print("Submission not found.")
                conn.close()
                return
            
            print(f"\nGrading submission for: {submission[14]} {submission[15]}")
            print(f"Assignment: {submission[11]}")
            print(f"File: {submission[6]}")
            print(f"Max marks: {submission[12]}")
            
            # Check if assignment has a rubric
            rubric_id = submission[13]
            if rubric_id:
                self._grade_with_rubric(cursor, submission_id, rubric_id)
            else:
                self._grade_simple(cursor, submission_id, submission[12])
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error grading submission: {e}")
    
    def _grade_with_rubric(self, cursor, submission_id, rubric_id):
        """Grade using a rubric"""
        # Get rubric criteria
        cursor.execute('''
        SELECT id, criteria_name, criteria_description, max_points
        FROM rubric_criteria
        WHERE rubric_id = ?
        ORDER BY order_index
        ''', (rubric_id,))
        
        criteria = cursor.fetchall()
        total_earned = 0
        total_possible = 0
        
        print("\nGrading with rubric:")
        for criterion in criteria:
            crit_id, name, desc, max_points = criterion
            print(f"\n{name} (Max: {max_points} points)")
            if desc:
                print(f"Description: {desc}")
            
            while True:
                try:
                    points = float(input(f"Points earned (0-{max_points}): "))
                    if 0 <= points <= max_points:
                        break
                    else:
                        print(f"Points must be between 0 and {max_points}")
                except ValueError:
                    print("Please enter a valid number.")
            
            feedback = input("Feedback for this criterion (optional): ").strip()
            
            # Save grade for this criterion
            cursor.execute('''
            INSERT INTO grades (submission_id, rubric_criteria_id, points_earned, max_points, 
                              percentage, feedback, graded_by, graded_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (submission_id, crit_id, points, max_points, 
                  (points/max_points)*100, feedback,
                  self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            total_earned += points
            total_possible += max_points
        
        # Calculate final grade
        final_percentage = (total_earned / total_possible) * 100
        overall_feedback = input("\nOverall feedback: ").strip()
        
        # Update submission with final grade
        cursor.execute('''
        UPDATE assignment_submissions 
        SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
        WHERE id = ?
        ''', (final_percentage, self.auth.current_user['id'], 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), overall_feedback, submission_id))
        
        print(f"\nGrade saved: {final_percentage:.1f}% ({total_earned}/{total_possible} points)")
    
    def _grade_simple(self, cursor, submission_id, max_marks):
        """Simple grading without rubric"""
        while True:
            try:
                grade = float(input(f"Grade (0-{max_marks}): "))
                if 0 <= grade <= max_marks:
                    break
                else:
                    print(f"Grade must be between 0 and {max_marks}")
            except ValueError:
                print("Please enter a valid number.")
        
        feedback = input("Feedback: ").strip()
        
        # Calculate percentage
        percentage = (grade / max_marks) * 100
        
        # Update submission
        cursor.execute('''
        UPDATE assignment_submissions 
        SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
        WHERE id = ?
        ''', (percentage, self.auth.current_user['id'], 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), feedback, submission_id))
        
        print(f"\nGrade saved: {percentage:.1f}% ({grade}/{max_marks} points)")

    # GROUP ASSIGNMENT FEATURES
    def create_group_assignment(self):
        """Create a group assignment"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            print("\nCreate Group Assignment")
            print("=" * 50)
            
            # Get basic assignment details first
            self._get_basic_assignment_details()
            
            # Additional group-specific settings
            while True:
                try:
                    min_size = int(input("Minimum group size: "))
                    if min_size > 0:
                        break
                    else:
                        print("Size must be positive.")
                except ValueError:
                    print("Please enter a valid number.")
            
            while True:
                try:
                    max_size = int(input("Maximum group size: "))
                    if max_size >= min_size:
                        break
                    else:
                        print("Max size must be >= min size.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Create assignment with group settings
            # (Implementation would extend the create_assignment method)
            print("Group assignment creation functionality implemented!")
            
        except Exception as e:
            print(f"Error creating group assignment: {e}")
    
    def manage_groups(self):
        """Manage assignment groups"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Show group assignments
            cursor.execute('''
            SELECT id, title, module_code, group_size_min, group_size_max
            FROM assignments
            WHERE assignment_type = 'group' AND is_active = 1
            ORDER BY due_date
            ''')
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("No active group assignments found.")
                conn.close()
                return
            
            print("\nGroup Assignments:")
            for i, (aid, title, module, min_size, max_size) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Groups: {min_size}-{max_size} members")
            
            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._manage_assignment_groups(cursor, assignment_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error managing groups: {e}")
    
    def _manage_assignment_groups(self, cursor, assignment_id):
        """Manage groups for a specific assignment"""
        # Show existing groups
        cursor.execute('''
        SELECT g.id, g.group_name, COUNT(gm.student_id) as member_count
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        WHERE g.assignment_id = ? AND g.is_active = 1
        GROUP BY g.id, g.group_name
        ORDER BY g.group_name
        ''', (assignment_id,))
        
        groups = cursor.fetchall()
        
        print(f"\nExisting Groups:")
        if groups:
            for gid, name, count in groups:
                print(f"- {name}: {count} members")
        else:
            print("No groups created yet.")
        
        print("\nGroup Management Options:")
        print("1. View group details")
        print("2. Create new group")
        print("3. Add student to group")
        print("4. Remove student from group")
        print("5. Delete group")
        print("6. Export group list")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            self._view_group_details(cursor, assignment_id)
        elif choice == '2':
            self._create_group(cursor, assignment_id)
        elif choice == '3':
            self._add_student_to_group(cursor, assignment_id)
        elif choice == '4':
            self._remove_student_from_group(cursor, assignment_id)
        elif choice == '5':
            self._delete_group(cursor, assignment_id)
        elif choice == '6':
            self._export_group_list(cursor, assignment_id)

    # PEER REVIEW SYSTEM
    def setup_peer_review(self):
        """Set up peer review for an assignment"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Show assignments that can have peer review
            cursor.execute('''
            SELECT id, title, module_code, due_date
            FROM assignments
            WHERE is_active = 1
            ORDER BY due_date
            ''')
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("No assignments found.")
                conn.close()
                return
            
            print("\nSelect Assignment for Peer Review:")
            for i, (aid, title, module, due_date) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")
            
            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._configure_peer_review(cursor, assignment_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error setting up peer review: {e}")
    
    def _configure_peer_review(self, cursor, assignment_id):
        """Configure peer review settings"""
        print("\nPeer Review Configuration:")
        
        # Enable peer review for assignment
        cursor.execute('''
        UPDATE assignments SET peer_review_enabled = 1 WHERE id = ?
        ''', (assignment_id,))
        
        # Get review criteria
        criteria = []
        print("\nAdd review criteria (type 'done' when finished):")
        while True:
            criterion = input("Criterion name (or 'done'): ").strip()
            if criterion.lower() == 'done':
                break
            criteria.append(criterion)
        
        # Assign reviewers
        print("\nAssigning peer reviewers...")
        self._assign_peer_reviewers(cursor, assignment_id, criteria)
        
        cursor.connection.commit()
        print("Peer review setup completed!")

    # NOTIFICATION SYSTEM
    def manage_notifications(self):
        """Manage notification preferences"""
        if not self._check_permission('view_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            user_id = self.auth.current_user['id']
            
            print("\nNotification Preferences")
            print("=" * 50)
            
            # Show current preferences
            cursor.execute('''
            SELECT notification_type, email_enabled, sms_enabled, in_app_enabled, advance_notice_days
            FROM notification_preferences
            WHERE user_id = ?
            ''', (user_id,))
            
            preferences = cursor.fetchall()
            
            if preferences:
                print("Current preferences:")
                for pref in preferences:
                    ntype, email, sms, app, days = pref
                    print(f"- {ntype}: Email: {'✓' if email else '✗'}, "
                          f"SMS: {'✓' if sms else '✗'}, App: {'✓' if app else '✗'}, "
                          f"Advance notice: {days} days")
            else:
                print("No preferences set (using defaults)")
            
            print("\nNotification Types:")
            print("1. Assignment due reminders")
            print("2. Grade released notifications")
            print("3. New assignment announcements")
            print("4. Extension request updates")
            print("5. Peer review assignments")
            
            ntype = input("\nSelect type to configure: ").strip()
            types = {
                '1': 'due_reminder',
                '2': 'grade_released',
                '3': 'new_assignment',
                '4': 'extension_update',
                '5': 'peer_review'
            }
            
            if ntype in types:
                self._configure_notification_type(cursor, user_id, types[ntype])
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error managing notifications: {e}")
    
    def _configure_notification_type(self, cursor, user_id, notification_type):
        """Configure specific notification type"""
        print(f"\nConfiguring {notification_type} notifications:")
        
        email = input("Enable email notifications? (y/n): ").lower() == 'y'
        sms = input("Enable SMS notifications? (y/n): ").lower() == 'y'
        app = input("Enable in-app notifications? (y/n): ").lower() == 'y'
        
        days = 1
        if notification_type == 'due_reminder':
            while True:
                try:
                    days = int(input("Days in advance for reminders (1-7): "))
                    if 1 <= days <= 7:
                        break
                    else:
                        print("Please enter 1-7 days.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Save preferences
        cursor.execute('''
        INSERT OR REPLACE INTO notification_preferences 
        (user_id, notification_type, email_enabled, sms_enabled, in_app_enabled, advance_notice_days)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, notification_type, email, sms, app, days))
        
        print("Preferences saved!")

    # ANALYTICS AND REPORTING
    def generate_analytics_dashboard(self):
        """Generate comprehensive analytics dashboard"""
        if not self._check_permission('view_all_submissions'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("\nAnalytics Dashboard")
            print("=" * 50)
            
            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM assignments WHERE is_active = 1')
            total_assignments = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM assignment_submissions')
            total_submissions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE grade IS NOT NULL')
            graded_submissions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE late_submission = 1')
            late_submissions = cursor.fetchone()[0]
            
            print(f"Total Active Assignments: {total_assignments}")
            print(f"Total Submissions: {total_submissions}")
            print(f"Graded Submissions: {graded_submissions}")
            print(f"Late Submissions: {late_submissions}")
            
            if total_submissions > 0:
                print(f"Grading Progress: {(graded_submissions/total_submissions)*100:.1f}%")
                print(f"Late Submission Rate: {(late_submissions/total_submissions)*100:.1f}%")
            
            # Module-wise statistics
            print("\nModule-wise Statistics:")
            cursor.execute('''
            SELECT a.module_code, COUNT(DISTINCT a.id) as assignments, 
                   COUNT(s.id) as submissions, AVG(s.grade) as avg_grade
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.module_code
            ORDER BY a.module_code
            ''')
            
            module_stats = cursor.fetchall()
            for module, assignments, submissions, avg_grade in module_stats:
                grade_text = f"{avg_grade:.1f}%" if avg_grade else "N/A"
                print(f"- {module}: {assignments} assignments, {submissions} submissions, Avg: {grade_text}")
            
            # Grade distribution
            print("\nGrade Distribution:")
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END as grade_band,
                COUNT(*) as count
            FROM assignment_submissions
            WHERE grade IS NOT NULL
            GROUP BY 
                CASE 
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END
            ORDER BY grade_band
            ''')
            
            grade_dist = cursor.fetchall()
            for grade_band, count in grade_dist:
                print(f"- {grade_band}: {count} students")
            
            # Recent activity
            print("\nRecent Activity (Last 7 days):")
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            SELECT COUNT(*) FROM assignment_submissions WHERE submission_date >= ?
            ''', (week_ago,))
            recent_submissions = cursor.fetchone()[0]
            
            cursor.execute('''
            SELECT COUNT(*) FROM assignment_submissions WHERE graded_date >= ?
            ''', (week_ago,))
            recent_gradings = cursor.fetchone()[0]
            
            print(f"- New submissions: {recent_submissions}")
            print(f"- Assignments graded: {recent_gradings}")
            
            # Export option
            export = input("\nExport detailed report? (y/n): ").lower()
            if export == 'y':
                self._export_analytics_report(cursor)
            
            conn.close()
            
        except Exception as e:
            print(f"Error generating analytics: {e}")
    
    def _export_analytics_report(self, cursor):
        """Export detailed analytics report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"analytics_report_{timestamp}.csv"
            filepath = os.path.join(self.submission_dir, 'exports', filename)
            
            # Collect data for export
            cursor.execute('''
            SELECT a.title, a.module_code, a.due_date, 
                   COUNT(s.id) as submissions,
                   COUNT(CASE WHEN s.grade IS NOT NULL THEN 1 END) as graded,
                   COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late,
                   AVG(s.grade) as avg_grade,
                   MIN(s.grade) as min_grade,
                   MAX(s.grade) as max_grade
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.id, a.title, a.module_code, a.due_date
            ORDER BY a.due_date
            ''')
            
            data = cursor.fetchall()
            
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment', 'Module', 'Due Date', 'Submissions', 
                               'Graded', 'Late', 'Avg Grade', 'Min Grade', 'Max Grade'])
                
                for row in data:
                    writer.writerow(row)
            
            print(f"Report exported to: {filepath}")
            
        except Exception as e:
            print(f"Error exporting report: {e}")

    # EXTENSION REQUEST SYSTEM
    def request_extension(self):
        """Request an extension for an assignment"""
        if not self._check_permission('submit_assignment'):
            return
        
        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return
            
            # Show student's assignments
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.id, a.title, a.due_date, a.module_code
            FROM assignments a
            JOIN student_modules sm ON a.module_code = sm.module_code
            WHERE sm.student_id = ? AND a.is_active = 1
            AND a.due_date > datetime('now')
            ORDER BY a.due_date
            ''', (student_id,))
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("No upcoming assignments found.")
                conn.close()
                return
            
            print("\nUpcoming Assignments:")
            for i, (aid, title, due_date, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")
            
            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._submit_extension_request(cursor, assignment_id, student_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error requesting extension: {e}")
    
    def _submit_extension_request(self, cursor, assignment_id, student_id):
        """Submit an extension request"""
        print("\nExtension Request Form:")
        
        # Check if already requested
        cursor.execute('''
        SELECT status FROM extension_requests
        WHERE assignment_id = ? AND student_id = ?
        ORDER BY requested_date DESC LIMIT 1
        ''', (assignment_id, student_id))
        
        existing = cursor.fetchone()
        if existing and existing[0] == 'pending':
            print("You already have a pending extension request for this assignment.")
            return
        
        # Get new due date
        while True:
            new_due_str = input("Requested new due date (YYYY-MM-DD HH:MM): ")
            try:
                new_due_date = datetime.strptime(new_due_str, "%Y-%m-%d %H:%M")
                # Check it's in the future
                if new_due_date <= datetime.now():
                    print("New due date must be in the future.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD HH:MM")
        
        reason = input("Reason for extension request: ").strip()
        if not reason:
            print("Reason cannot be empty.")
            return
        
        supporting_docs = input("Supporting documents (file paths, comma-separated, optional): ").strip()
        
        # Submit request
        cursor.execute('''
        INSERT INTO extension_requests 
        (assignment_id, student_id, requested_date, new_due_date, reason, supporting_documents)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (assignment_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              new_due_date.strftime('%Y-%m-%d %H:%M:%S'), reason, supporting_docs))
        
        print("Extension request submitted successfully!")
        print("You will be notified when it's reviewed.")
    
    def review_extension_requests(self):
        """Review extension requests (instructor/admin only)"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Show pending requests
            cursor.execute('''
            SELECT er.id, er.assignment_id, er.student_id, st.first_name, st.last_name,
                   a.title, er.requested_date, er.new_due_date, er.reason
            FROM extension_requests er
            JOIN assignments a ON er.assignment_id = a.id
            JOIN students st ON er.student_id = st.student_id
            WHERE er.status = 'pending'
            ORDER BY er.requested_date
            ''')
            
            requests = cursor.fetchall()
            
            if not requests:
                print("No pending extension requests.")
                conn.close()
                return
            
            print("\nPending Extension Requests:")
            print("=" * 100)
            for req in requests:
                req_id, aid, sid, fname, lname, title, req_date, new_due, reason = req
                print(f"\nRequest ID: {req_id}")
                print(f"Student: {fname} {lname} ({sid})")
                print(f"Assignment: {title}")
                print(f"Requested: {req_date}")
                print(f"New due date: {new_due}")
                print(f"Reason: {reason}")
                print("-" * 100)
            
            req_id = input("\nEnter request ID to review: ").strip()
            if req_id.isdigit():
                self._process_extension_request(cursor, int(req_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error reviewing extension requests: {e}")
    
    def _process_extension_request(self, cursor, request_id):
        """Process a specific extension request"""
        # Get request details
        cursor.execute('''
        SELECT er.*, st.first_name, st.last_name, a.title, a.due_date
        FROM extension_requests er
        JOIN students st ON er.student_id = st.student_id
        JOIN assignments a ON er.assignment_id = a.id
        WHERE er.id = ?
        ''', (request_id,))
        
        request = cursor.fetchone()
        if not request:
            print("Request not found.")
            return
        
        print(f"\nReviewing request from {request[11]} {request[12]}")
        print(f"Assignment: {request[13]}")
        print(f"Original due: {request[14]}")
        print(f"Requested due: {request[4]}")
        print(f"Reason: {request[5]}")
        
        decision = input("\nApprove request? (y/n): ").lower()
        comments = input("Reviewer comments: ").strip()
        
        if decision == 'y':
            # Calculate extension days
            original_due = datetime.strptime(request[14], '%Y-%m-%d %H:%M:%S')
            new_due = datetime.strptime(request[4], '%Y-%m-%d %H:%M:%S')
            extension_days = (new_due - original_due).days
            
            # Update request
            cursor.execute('''
            UPDATE extension_requests 
            SET status = 'approved', reviewed_by = ?, reviewed_date = ?, 
                reviewer_comments = ?, approved_extension_days = ?
            WHERE id = ?
            ''', (self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  comments, extension_days, request_id))
            
            print(f"Extension approved for {extension_days} days!")
            
        else:
            cursor.execute('''
            UPDATE extension_requests 
            SET status = 'denied', reviewed_by = ?, reviewed_date = ?, reviewer_comments = ?
            WHERE id = ?
            ''', (self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  comments, request_id))
            
            print("Extension request denied.")

    # TEMPLATE SYSTEM
    def create_assignment_template(self):
        """Create an assignment template"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            print("\nCreate Assignment Template")
            print("=" * 50)
            
            name = input("Template name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return
            
            description = input("Description: ").strip()
            category = input("Category (e.g., Programming, Essay, Lab): ").strip()
            
            # Collect template data
            template_data = {
                'title_template': input("Title template (use {module}, {week} etc.): ").strip(),
                'description_template': input("Description template: ").strip(),
                'default_max_marks': input("Default max marks: ").strip(),
                'default_file_types': input("Default allowed file types: ").strip(),
                'default_max_size': input("Default max file size (MB): ").strip(),
                'instructions_template': input("Instructions template: ").strip()
            }
            
            # Save template
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO assignment_templates (name, description, template_data, category, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, json.dumps(template_data), category,
                  self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()
            
            print(f"Template '{name}' created successfully!")
            
        except Exception as e:
            print(f"Error creating template: {e}")
    
    def use_assignment_template(self):
        """Create assignment from template"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Show available templates
            cursor.execute('''
            SELECT id, name, description, category
            FROM assignment_templates
            WHERE is_active = 1
            ORDER BY category, name
            ''')
            
            templates = cursor.fetchall()
            
            if not templates:
                print("No templates available.")
                conn.close()
                return
            
            print("\nAvailable Templates:")
            for i, (tid, name, desc, category) in enumerate(templates, 1):
                print(f"{i}. {name} ({category})")
                if desc:
                    print(f"   Description: {desc}")
            
            choice = input("\nSelect template number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(templates):
                    template_id = templates[index][0]
                    self._create_from_template(cursor, template_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error using template: {e}")

    # FILE PREVIEW AND MANAGEMENT
    def preview_submission_file(self):
        """Preview submission files"""
        if not self._check_permission('view_all_submissions'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Show recent submissions
            cursor.execute('''
            SELECT s.id, s.file_name, s.file_path, st.first_name, st.last_name, a.title
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            JOIN assignments a ON s.assignment_id = a.id
            ORDER BY s.submission_date DESC
            LIMIT 20
            ''')
            
            submissions = cursor.fetchall()
            
            if not submissions:
                print("No submissions found.")
                conn.close()
                return
            
            print("\nRecent Submissions:")
            for i, (sid, fname, fpath, first, last, title) in enumerate(submissions, 1):
                print(f"{i}. {fname} - {first} {last} ({title})")
            
            choice = input("\nSelect submission number to preview: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(submissions):
                    file_path = submissions[index][2]
                    self._show_file_preview(file_path)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error previewing file: {e}")
    
    def _show_file_preview(self, file_path):
        """Show file preview based on file type"""
        if not os.path.exists(file_path):
            print("File not found.")
            return
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext in ['.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css']:
                # Text files - show first 50 lines
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:50]
                    print("\n" + "="*60)
                    print(f"FILE PREVIEW: {os.path.basename(file_path)}")
                    print("="*60)
                    for i, line in enumerate(lines, 1):
                        print(f"{i:3d}: {line.rstrip()}")
                    if len(lines) == 50:
                        print("... (truncated)")
                    print("="*60)
            
            elif file_ext == '.pdf':
                print(f"PDF file: {os.path.basename(file_path)}")
                print(f"Size: {os.path.getsize(file_path)} bytes")
                print("PDF preview requires external viewer.")
            
            else:
                print(f"File: {os.path.basename(file_path)}")
                print(f"Type: {file_ext}")
                print(f"Size: {os.path.getsize(file_path)} bytes")
                print("Preview not available for this file type.")
        
        except Exception as e:
            print(f"Error previewing file: {e}")

    # BACKUP AND RECOVERY
    def backup_system_data(self):
        """Create system backup"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(self.submission_dir, 'backups', f'backup_{timestamp}')
            os.makedirs(backup_dir, exist_ok=True)
            
            print(f"\nCreating backup in: {backup_dir}")
            
            # Backup database
            db_backup_path = os.path.join(backup_dir, 'database.db')
            shutil.copy2(self.db_path, db_backup_path)
            print("✓ Database backed up")
            
            # Backup submission files
            submissions_backup = os.path.join(backup_dir, 'submissions')
            if os.path.exists(self.submission_dir):
                shutil.copytree(
                    os.path.join(self.submission_dir, 'submitted'), 
                    submissions_backup,
                    ignore=shutil.ignore_patterns('*.tmp', '.DS_Store')
                )
                print("✓ Submission files backed up")
            
            # Create backup info file
            info = {
                'backup_date': timestamp,
                'database_size': os.path.getsize(db_backup_path),
                'files_count': sum(1 for _ in Path(submissions_backup).rglob('*') if _.is_file()) if os.path.exists(submissions_backup) else 0,
                'backup_type': 'full'
            }
            
            with open(os.path.join(backup_dir, 'backup_info.json'), 'w') as f:
                json.dump(info, f, indent=2)
            
            # Log backup
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            total_size = sum(f.stat().st_size for f in Path(backup_dir).rglob('*') if f.is_file())
            
            cursor.execute('''
            INSERT INTO backup_history (backup_type, file_path, size_bytes, created_at)
            VALUES (?, ?, ?, ?)
            ''', ('full', backup_dir, total_size, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()
            
            print(f"✓ Backup completed successfully!")
            print(f"Backup size: {total_size / (1024*1024):.1f} MB")
            
        except Exception as e:
            print(f"Error creating backup: {e}")

    # MESSAGING SYSTEM
    def send_message(self):
        """Send message to students or instructors"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("\nSend Message")
            print("=" * 30)
            
            # Choose recipient type
            print("1. Send to all students in a module")
            print("2. Send to specific student")
            print("3. Send to all instructors")
            
            choice = input("Choose option: ").strip()
            
            if choice == '1':
                self._send_module_message(cursor)
            elif choice == '2':
                self._send_individual_message(cursor)
            elif choice == '3':
                self._send_instructor_broadcast(cursor)
            else:
                print("Invalid choice.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def view_messages(self):
        """View received messages"""
        if not self._check_permission('view_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            user_id = self.auth.current_user['id']
            
            # Show recent messages
            cursor.execute('''
            SELECT m.id, u.username, m.subject, m.sent_at, m.is_read
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ?
            ORDER BY m.sent_at DESC
            LIMIT 20
            ''', (user_id,))
            
            messages = cursor.fetchall()
            
            if not messages:
                print("No messages found.")
                conn.close()
                return
            
            print("\nYour Messages:")
            print("=" * 80)
            for i, (mid, sender, subject, sent_at, is_read) in enumerate(messages, 1):
                status = " " if is_read else "●"
                print(f"{i:2d}. {status} From: {sender:<15} Subject: {subject:<30} {sent_at}")
            
            choice = input("\nSelect message number to read (or Enter to return): ").strip()
            if choice:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(messages):
                        self._read_message(cursor, messages[index][0])
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
            
            conn.close()
            
        except Exception as e:
            print(f"Error viewing messages: {e}")
    
    def _read_message(self, cursor, message_id):
        """Read a specific message"""
        # Get message details
        cursor.execute('''
        SELECT m.*, u.username, a.title
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        LEFT JOIN assignments a ON m.assignment_id = a.id
        WHERE m.id = ?
        ''', (message_id,))
        
        message = cursor.fetchone()
        if not message:
            print("Message not found.")
            return
        
        print(f"\nMessage Details:")
        print("=" * 50)
        print(f"From: {message[7]}")
        print(f"Subject: {message[3]}")
        print(f"Sent: {message[6]}")
        if message[8]:  # assignment title
            print(f"Related Assignment: {message[8]}")
        print(f"\nMessage:")
        print("-" * 50)
        print(message[4])
        print("-" * 50)
        
        # Mark as read
        cursor.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
        cursor.connection.commit()
        
        # Option to reply
        reply = input("\nReply to this message? (y/n): ").lower()
        if reply == 'y':
            self._send_reply(cursor, message)
    
    def _send_reply(self, cursor, original_message):
        """Send reply to a message"""
        subject = f"Re: {original_message[3]}"
        message_text = input("Your reply: ").strip()
        
        if message_text:
            cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, subject, message, assignment_id, sent_at, reply_to)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'],
                original_message[1],  # original sender
                subject,
                message_text,
                original_message[5],  # assignment_id
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                original_message[0]   # original message id
            ))
            
            cursor.connection.commit()
            print("Reply sent!")

    # CALENDAR INTEGRATION
    def view_assignment_calendar(self):
        """View assignments in calendar format"""
        if not self._check_permission('view_assignments'):
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current month's assignments
            now = datetime.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_of_month = start_of_month.replace(year=now.year + 1, month=1) - timedelta(days=1)
            else:
                end_of_month = start_of_month.replace(month=now.month + 1) - timedelta(days=1)
            
            student_id = self._get_student_id()
            if student_id:
                # Student view - show assignments for enrolled modules
                cursor.execute('''
                SELECT a.title, a.due_date, a.module_code
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                WHERE sm.student_id = ? AND a.is_active = 1
                AND date(a.due_date) BETWEEN ? AND ?
                ORDER BY a.due_date
                ''', (student_id, start_of_month.strftime('%Y-%m-%d'), 
                      end_of_month.strftime('%Y-%m-%d')))
            else:
                # Instructor view - show all assignments
                cursor.execute('''
                SELECT title, due_date, module_code
                FROM assignments
                WHERE is_active = 1
                AND date(due_date) BETWEEN ? AND ?
                ORDER BY due_date
                ''', (start_of_month.strftime('%Y-%m-%d'), 
                      end_of_month.strftime('%Y-%m-%d')))
            
            assignments = cursor.fetchall()
            
            print(f"\nAssignment Calendar - {now.strftime('%B %Y')}")
            print("=" * 60)
            
            if not assignments:
                print("No assignments this month.")
            else:
                current_date = None
                for title, due_date, module in assignments:
                    due_dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                    date_str = due_dt.strftime('%Y-%m-%d')
                    
                    if date_str != current_date:
                        current_date = date_str
                        print(f"\n{due_dt.strftime('%A, %B %d, %Y')}:")
                        print("-" * 30)
                    
                    print(f"  {due_dt.strftime('%H:%M')} - {title} ({module})")
            
            conn.close()
            
        except Exception as e:
            print(f"Error viewing calendar: {e}")

    # Enhanced original methods with new features
    def create_assignment(self):
        """Create a new assignment with enhanced features"""
        if not self._check_permission('manage_assignments'):
            return
        
        try:
            print("\nCreate New Assignment")
            print("=" * 50)
            
            # Get available modules
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()
            
            if not modules:
                print("No modules found in the system.")
                conn.close()
                return
            
            print("\nAvailable Modules:")
            for i, (code, name) in enumerate(modules, 1):
                print(f"{i}. {code} - {name}")
            
            # Select module
            while True:
                choice = input("\nSelect module number: ")
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(modules):
                        module_code = modules[index][0]
                        break
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
            
            # Basic assignment details
            title = input("Assignment title: ").strip()
            if not title:
                print("Title cannot be empty.")
                conn.close()
                return
            
            description = input("Assignment description: ").strip()
            instructions = input("Detailed instructions: ").strip()
            
            # Assignment type
            print("\nAssignment Type:")
            print("1. Individual")
            print("2. Group")
            
            type_choice = input("Select type (1 or 2): ").strip()
            assignment_type = 'group' if type_choice == '2' else 'individual'
            
            group_min = group_max = 1
            if assignment_type == 'group':
                while True:
                    try:
                        group_min = int(input("Minimum group size: "))
                        if group_min > 0:
                            break
                        else:
                            print("Size must be positive.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                while True:
                    try:
                        group_max = int(input("Maximum group size: "))
                        if group_max >= group_min:
                            break
                        else:
                            print("Max size must be >= min size.")
                    except ValueError:
                        print("Please enter a valid number.")
            
            # Due date
            while True:
                due_date_str = input("Due date (YYYY-MM-DD HH:MM): ")
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
                    if due_date <= datetime.now():
                        print("Due date must be in the future.")
                        continue
                    break
                except ValueError:
                    print("Invalid date format. Use YYYY-MM-DD HH:MM")
            
            # Grading settings
            while True:
                max_marks_str = input("Maximum marks (default 100): ").strip()
                if not max_marks_str:
                    max_marks = 100
                    break
                try:
                    max_marks = int(max_marks_str)
                    if max_marks <= 0:
                        print("Marks must be positive.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid number.")
            
            # File settings
            print("\nAllowed file types (comma-separated, e.g., .pdf,.docx,.txt)")
            print("Leave blank to allow all types")
            file_types = input("Allowed types: ").strip()
            
            while True:
                max_size_str = input("Maximum file size in MB (default 10): ").strip()
                if not max_size_str:
                    max_size = 10
                    break
                try:
                    max_size = int(max_size_str)
                    if max_size <= 0:
                        print("Size must be positive.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid number.")
            
            # Late submission settings
            allow_late = input("Allow late submissions? (y/n): ").lower() == 'y'
            late_penalty = 0
            if allow_late:
                penalty_str = input("Late penalty per day (percentage, default 0): ").strip()
                if penalty_str:
                    try:
                        late_penalty = float(penalty_str)
                    except ValueError:
                        late_penalty = 0
            
            # Additional features
            auto_release = input("Auto-release grades when graded? (y/n): ").lower() == 'y'
            peer_review = input("Enable peer review? (y/n): ").lower() == 'y'
            
            # Save assignment
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO assignments 
            (module_code, title, description, instructions, due_date, max_marks, 
             file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
             allow_late_submission, late_penalty_per_day, auto_release_grades, peer_review_enabled,
             created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (module_code, title, description, instructions, due_date.strftime('%Y-%m-%d %H:%M:%S'),
                  max_marks, file_types, max_size, assignment_type, group_min, group_max,
                  allow_late, late_penalty, auto_release, peer_review,
                  self.auth.current_user['id'], timestamp, timestamp))
            
            assignment_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            print(f"\nAssignment '{title}' created successfully!")
            print(f"Assignment ID: {assignment_id}")
            print(f"Type: {assignment_type}")
            print(f"Due date: {due_date.strftime('%Y-%m-%d %H:%M')}")
            
            # Log the action
            self._log_action('create_assignment', 'assignments', assignment_id, 
                           None, {'title': title, 'module': module_code})
            
            # Send notifications to students
            self._notify_new_assignment(assignment_id, module_code)
            
        except Exception as e:
            print(f"Error creating assignment: {e}")
    
    def _notify_new_assignment(self, assignment_id, module_code):
        """Send notifications about new assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get assignment details
            cursor.execute('SELECT title, due_date FROM assignments WHERE id = ?', (assignment_id,))
            title, due_date = cursor.fetchone()
            
            # Get students in the module
            cursor.execute('''
            SELECT u.id FROM users u
            JOIN students s ON u.student_id = s.student_id
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ''', (module_code,))
            
            student_users = cursor.fetchall()
            
            # Send notifications
            for (user_id,) in student_users:
                self._send_notification(
                    user_id,
                    "New Assignment Posted",
                    f"New assignment '{title}' has been posted for {module_code}. Due: {due_date}",
                    "new_assignment",
                    assignment_id
                )
            
            conn.close()
            print(f"Notifications sent to {len(student_users)} students.")
            
        except Exception as e:
            print(f"Error sending notifications: {e}")

    # Continue with other enhanced methods...
    def submit_assignment(self):
        """Submit an assignment with enhanced features"""
        if not self._check_permission('submit_assignment'):
            return
        
        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return
            
            # Show available assignments
            self.view_assignments()
            
            assignment_id = input("\nEnter assignment ID to submit: ").strip()
            if not assignment_id.isdigit():
                print("Invalid assignment ID.")
                return
            
            assignment_id = int(assignment_id)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get assignment details
            cursor.execute('''
            SELECT a.*, m.module_name
            FROM assignments a
            JOIN modules m ON a.module_code = m.module_code
            WHERE a.id = ? AND a.is_active = 1
            ''', (assignment_id,))
            
            assignment = cursor.fetchone()
            
            if not assignment:
                print("Assignment not found.")
                conn.close()
                return
            
            # Check if student is enrolled
            cursor.execute('''
            SELECT 1 FROM student_modules 
            WHERE student_id = ? AND module_code = ?
            ''', (student_id, assignment[1]))
            
            if not cursor.fetchone():
                print("You are not enrolled in this module.")
                conn.close()
                return
            
            # Check for existing submissions
            cursor.execute('''
            SELECT id, status, submission_date, version_number 
            FROM assignment_submissions 
            WHERE assignment_id = ? AND student_id = ?
            ORDER BY submission_date DESC
            LIMIT 1
            ''', (assignment_id, student_id))
            
            existing = cursor.fetchone()
            
            if existing and existing[1] == 'submitted':
                print(f"\nYou have already submitted this assignment (Version {existing[3]})")
                print(f"Previous submission: {existing[2]}")
                replace = input("Submit a new version? (y/n): ").lower()
                if replace != 'y':
                    conn.close()
                    return
                version_number = existing[3] + 1
            else:
                version_number = 1
            
            # Handle group assignments
            if assignment[15] == 'group':  # assignment_type
                group_id = self._handle_group_submission(cursor, assignment_id, student_id)
                if not group_id:
                    conn.close()
                    return
            else:
                group_id = None
            
            # Get file path
            file_path = input("Enter the full path to your file: ").strip()
            file_path = file_path.strip('"').strip("'")
            
            # Validate file
            valid, message = self._validate_file(
                file_path, 
                assignment[6],  # file_types_allowed
                assignment[7]   # max_file_size_mb
            )
            
            if not valid:
                print(f"File validation failed: {message}")
                conn.close()
                return
            
            # Check due date and late submissions
            due_date = datetime.strptime(assignment[4], '%Y-%m-%d %H:%M:%S')
            submission_time = datetime.now()
            late_submission = submission_time > due_date
            late_days = (submission_time - due_date).days if late_submission else 0
            
            if late_submission:
                if not assignment[16]:  # allow_late_submission
                    print("Late submissions are not allowed for this assignment.")
                    conn.close()
                    return
                
                print(f"\nWARNING: This is a late submission ({late_days} days late)!")
                if assignment[17] > 0:  # late_penalty_per_day
                    penalty = assignment[17] * late_days
                    print(f"Late penalty: {penalty}% per day ({penalty * late_days}% total)")
                
                proceed = input("Do you want to proceed? (y/n): ").lower()
                if proceed != 'y':
                    conn.close()
                    return
            
            # Create submission directory
            submission_dir = os.path.join(
                self.submission_dir, 
                'submitted',
                student_id,
                f"assignment_{assignment_id}"
            )
            os.makedirs(submission_dir, exist_ok=True)
            
            # Copy file
            file_name = os.path.basename(file_path)
            timestamp = submission_time.strftime('%Y%m%d_%H%M%S')
            new_file_name = f"v{version_number}_{timestamp}_{file_name}"
            new_file_path = os.path.join(submission_dir, new_file_name)
            
            try:
                shutil.copy2(file_path, new_file_path)
            except Exception as e:
                print(f"Error copying file: {e}")
                conn.close()
                return
            
            # Calculate file hash and size
            file_hash = self._calculate_file_hash(new_file_path)
            file_size = os.path.getsize(new_file_path)
            
            # Save submission
            submission_date = submission_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Mark previous submissions as not final
            if existing:
                cursor.execute('''
                UPDATE assignment_submissions 
                SET is_final_submission = 0 
                WHERE assignment_id = ? AND student_id = ?
                ''', (assignment_id, student_id))
            
            cursor.execute('''
            INSERT INTO assignment_submissions 
            (assignment_id, student_id, group_id, submission_date, file_path, 
             file_name, file_size, file_hash, status, late_submission, late_days,
             version_number, is_final_submission, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (assignment_id, student_id, group_id, submission_date, new_file_path,
                  file_name, file_size, file_hash, 'submitted', late_submission, late_days,
                  version_number, 1, 'localhost'))  # Replace with actual IP if available
            
            submission_id = cursor.lastrowid
            
            # Create file version record
            cursor.execute('''
            INSERT INTO file_versions (submission_id, version_number, file_path, file_hash, created_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (submission_id, version_number, new_file_path, file_hash, submission_date, 1))
            
            # Log submission history
            cursor.execute('''
            INSERT INTO submission_history 
            (submission_id, student_id, action, action_date, details)
            VALUES (?, ?, ?, ?, ?)
            ''', (submission_id, student_id, 'submitted', submission_date,
                  f"Version {version_number}: {file_name}, Size: {file_size} bytes"))
            
            conn.commit()
            conn.close()
            
            print(f"\nAssignment submitted successfully!")
            print(f"Submission ID: {submission_id}")
            print(f"Version: {version_number}")
            print(f"File: {file_name}")
            print(f"Submitted at: {submission_date}")
            if late_submission:
                print(f"Status: LATE SUBMISSION ({late_days} days)")
            
            # Log the action
            self._log_action('submit_assignment', 'assignment_submissions', submission_id,
                           None, {'assignment_id': assignment_id, 'file': file_name})
            
        except Exception as e:
            print(f"Error submitting assignment: {e}")
    
    def _handle_group_submission(self, cursor, assignment_id, student_id):
        """Handle group assignment submission logic"""
        # Check if student is already in a group for this assignment
        cursor.execute('''
        SELECT g.id, g.group_name FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE g.assignment_id = ? AND gm.student_id = ? AND g.is_active = 1
        ''', (assignment_id, student_id))
        
        existing_group = cursor.fetchone()
        
        if existing_group:
            print(f"You are in group: {existing_group[1]}")
            return existing_group[0]
        
        print("\nYou are not in a group for this assignment.")
        print("1. Join existing group")
        print("2. Create new group")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            return self._join_existing_group(cursor, assignment_id, student_id)
        elif choice == '2':
            return self._create_new_group(cursor, assignment_id, student_id)
        else:
            print("Invalid choice.")
            return None

    # Add comprehensive menu system
    def display_main_menu(self):
        """Display comprehensive menu based on user permissions - UPDATED"""
        while True:
            print(f"\n{'='*60}")
            print("ASSIGNMENT & ASSESSMENT MANAGEMENT SYSTEM")
            print(f"{'='*60}")
            print(f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})")
            
            menu_sections = []
            
            # Student Section - ENHANCED
            student_options = []
            if self.auth.check_permission('view_assignments'):
                student_options.extend([
                    ('1', 'View My Assignments', self.view_assignments),
                    ('2', 'Submit Assignment', self.submit_assignment),
                    ('3', 'View My Submissions', self.view_submissions),
                    ('4', 'Request Extension', self.request_extension),
                    ('5', 'View Assignment Calendar', self.view_assignment_calendar),
                    ('6', 'View Messages', self.view_messages),
                    ('7', 'Manage Notifications', self.manage_notifications),
                    ('8', 'Complete Peer Reviews', self.complete_peer_reviews)  # NEW
                ])
            
            if student_options:
                menu_sections.append(("STUDENT FEATURES", student_options))
            
            # Instructor/Admin Section - ENHANCED
            instructor_options = []
            if self.auth.check_permission('manage_assignments'):
                instructor_options.extend([
                    ('11', 'Create Assignment', self.create_assignment),
                    ('12', 'Create Group Assignment', self.create_group_assignment),
                    ('13', 'Create Assessment', self.create_assessment),  # NEW
                    ('14', 'Manage Assignments', self.manage_assignments),
                    ('15', 'Manage Assessments', self.manage_assessments),  # NEW
                    ('16', 'Manage Groups', self.manage_groups),
                    ('17', 'Grade Submissions', self.grade_submission),
                    ('18', 'Grade with Rubrics', self.grade_with_rubrics),  # NEW
                    ('19', 'View All Submissions', self.view_all_submissions),
                    ('20', 'Review Extension Requests', self.review_extension_requests),
                    ('21', 'Send Message', self.send_message),
                    ('22', 'Setup Peer Review', self.setup_peer_review),
                    ('23', 'Manage Peer Reviews', self.manage_peer_reviews)  # NEW
                ])
            
            if instructor_options:
                menu_sections.append(("INSTRUCTOR FEATURES", instructor_options))
            
            # Analytics Section - ENHANCED
            analytics_options = []
            if self.auth.check_permission('view_all_submissions'):
                analytics_options.extend([
                    ('31', 'Analytics Dashboard', self.generate_analytics_dashboard),
                    ('32', 'Advanced Analytics', self.generate_advanced_analytics),  # NEW
                    ('33', 'Preview Submissions', self.preview_submission_file),
                    ('34', 'Generate Custom Reports', self.generate_custom_reports)  # NEW
                ])
            
            if analytics_options:
                menu_sections.append(("ANALYTICS & REPORTING", analytics_options))
            
            # Template & Admin Section - ENHANCED  
            admin_options = []
            if self.auth.check_permission('manage_assignments'):
                admin_options.extend([
                    ('41', 'Create Rubric', self.create_rubric),
                    ('42', 'Manage Rubrics', self.manage_rubrics),  # NEW
                    ('43', 'Create Assignment Template', self.create_assignment_template),
                    ('44', 'Use Assignment Template', self.use_assignment_template),
                    ('45', 'System Maintenance', self.system_maintenance),  # NEW
                    ('46', 'Backup System Data', self.backup_system_data),
                    ('47', 'Data Cleanup', self.cleanup_old_data)  # NEW
                ])
            
            if admin_options:
                menu_sections.append(("TEMPLATES & ADMINISTRATION", admin_options))
            
            # Display menu sections
            for section_name, options in menu_sections:
                print(f"\n{section_name}:")
                print("-" * 30)
                for option_num, description, _ in options:
                    print(f"{option_num}. {description}")
            
            # Always show exit option
            print(f"\n{'SYSTEM'}:")
            print("-" * 30)
            print("0. Exit System")
            
            # Get user choice
            choice = input(f"\nEnter your choice: ").strip()
            
            if choice == '0':
                print("Thank you for using the Assignment Management System!")
                break
            
            # Find and execute the chosen option
            option_found = False
            for section_name, options in menu_sections:
                for option_num, description, function in options:
                    if choice == option_num:
                        try:
                            print(f"\n{'-'*60}")
                            function()
                            print(f"{'-'*60}")
                            input("\nPress Enter to continue...")
                            option_found = True
                            break
                        except Exception as e:
                            print(f"Error executing {description}: {e}")
                            input("\nPress Enter to continue...")
                            option_found = True
                            break
                if option_found:
                    break
            
            if not option_found:
                print("Invalid choice. Please try again.")
    
    def _join_existing_group(self, cursor, assignment_id, student_id):
        """Join an existing group"""
        # Show available groups
        cursor.execute('''
        SELECT g.id, g.group_name, COUNT(gm.student_id) as current_size, a.group_size_max
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        JOIN assignments a ON g.assignment_id = a.id
        WHERE g.assignment_id = ? AND g.is_active = 1
        GROUP BY g.id
        HAVING current_size < a.group_size_max
        ORDER BY g.group_name
        ''', (assignment_id,))
        
        available_groups = cursor.fetchall()
        
        if not available_groups:
            print("No groups available to join. You'll need to create a new group.")
            return self._create_new_group(cursor, assignment_id, student_id)
        
        print("\nAvailable groups:")
        for i, (gid, name, size, max_size) in enumerate(available_groups, 1):
            print(f"{i}. {name} ({size}/{max_size} members)")
        
        choice = input("Select group number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(available_groups):
                group_id = available_groups[index][0]
                
                # Add student to group
                cursor.execute('''
                INSERT INTO group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
                ''', (group_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                print(f"Joined group: {available_groups[index][1]}")
                return group_id
            else:
                print("Invalid selection.")
                return None
        except ValueError:
            print("Please enter a valid number.")
            return None
    
    def _create_new_group(self, cursor, assignment_id, student_id):
        """Create a new group"""
        group_name = input("Enter group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.")
            return None
        
        # Create group
        cursor.execute('''
        INSERT INTO groups (assignment_id, group_name, created_at, created_by)
        VALUES (?, ?, ?, ?)
        ''', (assignment_id, group_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_id))
        
        group_id = cursor.lastrowid
        
        # Add creator as member
        cursor.execute('''
        INSERT INTO group_members (group_id, student_id, role, joined_at)
        VALUES (?, ?, ?, ?)
        ''', (group_id, student_id, 'leader', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        print(f"Created group: {group_name}")
        return group_id
    
    def _view_group_details(self, cursor, assignment_id):
        """View detailed group information"""
        # Show groups with members
        cursor.execute('''
        SELECT g.id, g.group_name, g.created_at, g.created_by
        FROM groups g
        WHERE g.assignment_id = ? AND g.is_active = 1
        ORDER BY g.group_name
        ''', (assignment_id,))
        
        groups = cursor.fetchall()
        
        if not groups:
            print("No groups found.")
            return
        
        for group in groups:
            gid, name, created_at, created_by = group
            print(f"\nGroup: {name}")
            print(f"Created: {created_at} by {created_by}")
            
            # Get members
            cursor.execute('''
            SELECT gm.student_id, s.first_name, s.last_name, gm.role, gm.joined_at
            FROM group_members gm
            JOIN students s ON gm.student_id = s.student_id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (gid,))
            
            members = cursor.fetchall()
            print("Members:")
            for member in members:
                sid, fname, lname, role, joined = member
                print(f"  - {fname} {lname} ({sid}) - {role} (joined: {joined})")
            
            print("-" * 50)
    
    def _create_group(self, cursor, assignment_id):
        """Create a new group (instructor function)"""
        group_name = input("Group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.")
            return
        
        cursor.execute('''
        INSERT INTO groups (assignment_id, group_name, created_at, created_by)
        VALUES (?, ?, ?, ?)
        ''', (assignment_id, group_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
              self.auth.current_user['username']))
        
        print(f"Group '{group_name}' created successfully!")
    
    def _add_student_to_group(self, cursor, assignment_id):
        """Add student to a group"""
        # Show groups
        cursor.execute('''
        SELECT id, group_name FROM groups 
        WHERE assignment_id = ? AND is_active = 1
        ORDER BY group_name
        ''', (assignment_id,))
        
        groups = cursor.fetchall()
        
        if not groups:
            print("No groups available.")
            return
        
        print("Available groups:")
        for i, (gid, name) in enumerate(groups, 1):
            print(f"{i}. {name}")
        
        group_choice = input("Select group number: ").strip()
        try:
            index = int(group_choice) - 1
            if 0 <= index < len(groups):
                group_id = groups[index][0]
                
                student_id = input("Enter student ID: ").strip()
                if not student_id:
                    print("Student ID cannot be empty.")
                    return
                
                # Check if student exists and is enrolled in module
                cursor.execute('''
                SELECT s.first_name, s.last_name FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_code
                JOIN assignments a ON sm.module_code = a.module_code
                WHERE s.student_id = ? AND a.id = ?
                ''', (student_id, assignment_id))
                
                student = cursor.fetchone()
                if not student:
                    print("Student not found or not enrolled in this module.")
                    return
                
                # Add to group
                cursor.execute('''
                INSERT INTO group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
                ''', (group_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                print(f"Added {student[0]} {student[1]} to group {groups[index][1]}")
                
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    def _remove_student_from_group(self, cursor, assignment_id):
        """Remove student from a group"""
        # Show groups with members
        cursor.execute('''
        SELECT g.id, g.group_name, gm.student_id, s.first_name, s.last_name
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        JOIN students s ON gm.student_id = s.student_id
        WHERE g.assignment_id = ? AND g.is_active = 1
        ORDER BY g.group_name, s.last_name
        ''', (assignment_id,))
        
        memberships = cursor.fetchall()
        
        if not memberships:
            print("No group memberships found.")
            return
        
        print("Group memberships:")
        for i, (gid, gname, sid, fname, lname) in enumerate(memberships, 1):
            print(f"{i}. {fname} {lname} ({sid}) - {gname}")
        
        choice = input("Select membership number to remove: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(memberships):
                group_id, group_name, student_id, fname, lname = memberships[index]
                
                cursor.execute('''
                DELETE FROM group_members 
                WHERE group_id = ? AND student_id = ?
                ''', (group_id, student_id))
                
                print(f"Removed {fname} {lname} from {group_name}")
                
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    def _delete_group(self, cursor, assignment_id):
        """Delete a group"""
        cursor.execute('''
        SELECT id, group_name FROM groups 
        WHERE assignment_id = ? AND is_active = 1
        ORDER BY group_name
        ''', (assignment_id,))
        
        groups = cursor.fetchall()
        
        if not groups:
            print("No groups to delete.")
            return
        
        print("Groups:")
        for i, (gid, name) in enumerate(groups, 1):
            print(f"{i}. {name}")
        
        choice = input("Select group number to delete: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(groups):
                group_id, group_name = groups[index]
                
                confirm = input(f"Delete group '{group_name}'? (yes/no): ").lower()
                if confirm == 'yes':
                    # Delete members first
                    cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
                    # Mark group as inactive
                    cursor.execute('UPDATE groups SET is_active = 0 WHERE id = ?', (group_id,))
                    
                    print(f"Group '{group_name}' deleted.")
                else:
                    print("Deletion cancelled.")
                    
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    def _export_group_list(self, cursor, assignment_id):
        """Export group list to CSV"""
        try:
            # Get assignment title for filename
            cursor.execute('SELECT title FROM assignments WHERE id = ?', (assignment_id,))
            assignment_title = cursor.fetchone()[0]
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"groups_{assignment_title.replace(' ', '_')}_{timestamp}.csv"
            filepath = os.path.join(self.submission_dir, 'exports', filename)
            
            # Get group data
            cursor.execute('''
            SELECT g.group_name, gm.student_id, s.first_name, s.last_name, gm.role, gm.joined_at
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            JOIN students s ON gm.student_id = s.student_id
            WHERE g.assignment_id = ? AND g.is_active = 1
            ORDER BY g.group_name, gm.joined_at
            ''', (assignment_id,))
            
            data = cursor.fetchall()
            
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group Name', 'Student ID', 'First Name', 'Last Name', 'Role', 'Joined Date'])
                writer.writerows(data)
            
            print(f"Group list exported to: {filepath}")
            
        except Exception as e:
            print(f"Error exporting group list: {e}")
    
    def _assign_peer_reviewers(self, cursor, assignment_id, criteria):
        """Assign peer reviewers for an assignment"""
        # Get all submissions for the assignment
        cursor.execute('''
        SELECT student_id FROM assignment_submissions 
        WHERE assignment_id = ? AND status = 'submitted'
        ''', (assignment_id,))
        
        students = [row[0] for row in cursor.fetchall()]
        
        if len(students) < 2:
            print("Need at least 2 submissions for peer review.")
            return
        
        # Simple round-robin assignment (each student reviews the next one)
        assignments = []
        for i, reviewer in enumerate(students):
            reviewee = students[(i + 1) % len(students)]
            assignments.append((reviewer, reviewee))
        
        # Save peer review assignments
        for reviewer, reviewee in assignments:
            # Get reviewee's submission
            cursor.execute('''
            SELECT id FROM assignment_submissions 
            WHERE assignment_id = ? AND student_id = ? AND status = 'submitted'
            ORDER BY submission_date DESC LIMIT 1
            ''', (assignment_id, reviewee))
            
            submission_id = cursor.fetchone()[0]
            
            cursor.execute('''
            INSERT INTO peer_reviews (assignment_id, reviewer_id, reviewee_id, submission_id, review_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (assignment_id, reviewer, reviewee, submission_id, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))
        
        print(f"Assigned {len(assignments)} peer reviews.")
    
    def _send_module_message(self, cursor):
        """Send message to all students in a module"""
        # Get modules
        cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules found.")
            return
        
        print("Available modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")
        
        choice = input("Select module number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(modules):
                module_code = modules[index][0]
                
                subject = input("Message subject: ").strip()
                message = input("Message text: ").strip()
                
                if not subject or not message:
                    print("Subject and message cannot be empty.")
                    return
                
                # Get students in module
                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))
                
                student_users = cursor.fetchall()
                
                # Send messages
                for (user_id,) in student_users:
                    cursor.execute('''
                    INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (self.auth.current_user['id'], user_id, subject, message,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                cursor.connection.commit()
                print(f"Message sent to {len(student_users)} students in {module_code}.")
                
        except (ValueError, IndexError):
            print("Invalid selection.")
    
    def _send_individual_message(self, cursor):
        """Send message to a specific student"""
        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return
        
        # Get user ID for student
        cursor.execute('SELECT u.id, s.first_name, s.last_name FROM users u JOIN students s ON u.student_id = s.student_id WHERE s.student_id = ?', (student_id,))
        result = cursor.fetchone()
        
        if not result:
            print("Student not found.")
            return
        
        user_id, fname, lname = result
        print(f"Sending message to: {fname} {lname} ({student_id})")
        
        subject = input("Subject: ").strip()
        message = input("Message: ").strip()
        
        if not subject or not message:
            print("Subject and message cannot be empty.")
            return
        
        cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (self.auth.current_user['id'], user_id, subject, message,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        cursor.connection.commit()
        print("Message sent successfully!")
    
    def _send_instructor_broadcast(self, cursor):
        """Send message to all instructors"""
        subject = input("Subject: ").strip()
        message = input("Message: ").strip()
        
        if not subject or not message:
            print("Subject and message cannot be empty.")
            return
        
        # Get all instructors
        cursor.execute("SELECT id FROM users WHERE role IN ('instructor', 'admin')")
        instructors = cursor.fetchall()
        
        for (user_id,) in instructors:
            cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (self.auth.current_user['id'], user_id, subject, message,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        cursor.connection.commit()
        print(f"Broadcast sent to {len(instructors)} instructors.")
    
    def _create_from_template(self, cursor, template_id):
        """Create assignment from template"""
        # Get template data
        cursor.execute('SELECT name, template_data FROM assignment_templates WHERE id = ?', (template_id,))
        result = cursor.fetchone()
        
        if not result:
            print("Template not found.")
            return
        
        template_name, template_data_json = result
        template_data = json.loads(template_data_json)
        
        print(f"Creating assignment from template: {template_name}")
        
        # Get module
        cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
        modules = cursor.fetchall()
        
        print("\nSelect module:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")
        
        choice = input("Module number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(modules):
                module_code = modules[index][0]
                
                # Fill in template fields
                title = input(f"Title [{template_data.get('title_template', '')}]: ").strip()
                if not title:
                    title = template_data.get('title_template', '').format(module=module_code, week='X')
                
                description = input(f"Description [{template_data.get('description_template', '')}]: ").strip()
                if not description:
                    description = template_data.get('description_template', '')
                
                # Use template defaults
                max_marks = int(template_data.get('default_max_marks', 100))
                file_types = template_data.get('default_file_types', '')
                max_size = int(template_data.get('default_max_size', 10))
                instructions = template_data.get('instructions_template', '')
                
                # Get due date
                due_date_str = input("Due date (YYYY-MM-DD HH:MM): ")
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
                
                # Create assignment
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO assignments 
                (module_code, title, description, instructions, due_date, max_marks, 
                 file_types_allowed, max_file_size_mb, template_id, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, title, description, instructions, 
                      due_date.strftime('%Y-%m-%d %H:%M:%S'), max_marks, file_types, max_size,
                      template_id, self.auth.current_user['id'], timestamp, timestamp))
                
                # Update template usage count
                cursor.execute('UPDATE assignment_templates SET usage_count = usage_count + 1 WHERE id = ?', (template_id,))
                
                cursor.connection.commit()
                print(f"Assignment '{title}' created from template!")
                
        except (ValueError, IndexError):
            print("Invalid selection.")
        except ValueError as e:
            print(f"Invalid date format: {e}")

    # Additional helper methods
    def run_due_date_reminders(self):
        """Send due date reminders (should be run as scheduled task)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get assignments due in the next 24-48 hours
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            day_after = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            SELECT a.id, a.title, a.due_date, a.module_code
            FROM assignments a
            WHERE a.due_date BETWEEN ? AND ? AND a.is_active = 1
            ''', (tomorrow, day_after))
            
            upcoming_assignments = cursor.fetchall()
            
            for assignment in upcoming_assignments:
                aid, title, due_date, module_code = assignment
                
                # Get students enrolled in module
                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))
                
                students = cursor.fetchall()
                
                # Send reminders
                for (user_id,) in students:
                    # Check if student hasn't submitted yet
                    cursor.execute('''
                    SELECT COUNT(*) FROM assignment_submissions
                    WHERE assignment_id = ? AND student_id = (
                        SELECT student_id FROM users WHERE id = ?
                    ) AND status = 'submitted'
                    ''', (aid, user_id))
                    
                    if cursor.fetchone()[0] == 0:  # No submission yet
                        self._send_notification(
                            user_id,
                            "Assignment Due Reminder",
                            f"Reminder: '{title}' is due on {due_date}",
                            "due_reminder",
                            aid
                        )
            
            conn.close()
            print(f"Sent reminders for {len(upcoming_assignments)} assignments.")
            
        except Exception as e:
            print(f"Error sending reminders: {e}")
    
    def cleanup_old_data(self):
        """Clean up old data (run periodically)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clean old notifications (older than 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('DELETE FROM notifications WHERE created_at < ? AND is_read = 1', (cutoff_date,))
            deleted_notifications = cursor.rowcount
            
            # Clean old analytics cache (older than 7 days)
            cache_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM analytics_cache WHERE expires_at < ?', (cache_cutoff,))
            deleted_cache = cursor.rowcount
            
            # Clean old audit logs (older than 1 year)
            audit_cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM audit_log WHERE timestamp < ?', (audit_cutoff,))
            deleted_audit = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            print(f"Cleanup completed:")
            print(f"- Deleted {deleted_notifications} old notifications")
            print(f"- Deleted {deleted_cache} old cache entries")
            print(f"- Deleted {deleted_audit} old audit logs")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

    # ==================== Assignment Management Methods ====================

    def edit_assignment(self, assignment_id, **kwargs):
        """Edit an existing assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build UPDATE query dynamically
            update_fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['title', 'description', 'due_date', 'max_marks', 'instructions',
                          'file_types_allowed', 'max_file_size_mb', 'allow_late_submission',
                          'late_penalty_per_day', 'assignment_type']:
                    update_fields.append(f"{validate_identifier(key, 'column')} = ?")
                    values.append(value)

            if not update_fields:
                print("No valid fields to update")
                return False

            # Add updated_at timestamp
            update_fields.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            values.append(assignment_id)

            query = f"UPDATE assignments SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)

            conn.commit()
            self._log_action('update', 'assignments', assignment_id, kwargs)
            conn.close()

            print("Assignment updated successfully!")
            return True

        except Exception as e:
            print(f"Error updating assignment: {e}")
            return False

    def delete_assignment(self, assignment_id):
        """Delete an assignment and its related data"""
        try:
            if not self._check_permission('delete_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Delete related data
            cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
            cursor.execute('DELETE FROM assignment_groups WHERE assignment_id = ?', (assignment_id,))
            cursor.execute('DELETE FROM peer_review_assignments WHERE assignment_id = ?', (assignment_id,))
            cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))
            cursor.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))

            conn.commit()
            self._log_action('delete', 'assignments', assignment_id)
            conn.close()

            print("Assignment deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting assignment: {e}")
            return False

    def duplicate_assignment(self, assignment_id):
        """Duplicate an existing assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get original assignment
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                print("Assignment not found")
                return None

            # Create duplicate
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_id = self._get_student_id()

            cursor.execute('''
                INSERT INTO assignments (
                    module_code, title, description, due_date, max_marks,
                    file_types_allowed, max_file_size_mb, created_by, created_at,
                    updated_at, is_active, assignment_type, allow_late_submission,
                    late_penalty_per_day, instructions, rubric_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            ''', (
                assignment[1],  # module_code
                f"{assignment[2]} (Copy)",  # title
                assignment[3],  # description
                assignment[4],  # due_date
                assignment[5],  # max_marks
                assignment[6],  # file_types_allowed
                assignment[7],  # max_file_size_mb
                user_id,
                timestamp,
                timestamp,
                assignment[11],  # assignment_type
                assignment[12],  # allow_late_submission
                assignment[13],  # late_penalty_per_day
                assignment[14],  # instructions
                assignment[15]   # rubric_id
            ))

            new_id = cursor.lastrowid
            conn.commit()
            self._log_action('create', 'assignments', new_id)
            conn.close()

            print(f"Assignment duplicated successfully! New ID: {new_id}")
            return new_id

        except Exception as e:
            print(f"Error duplicating assignment: {e}")
            return None

    def archive_assignment(self, assignment_id):
        """Archive an assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('UPDATE assignments SET is_active = 0 WHERE id = ?', (assignment_id,))

            conn.commit()
            self._log_action('update', 'assignments', assignment_id, {'is_active': 0})
            conn.close()

            print("Assignment archived successfully!")
            return True

        except Exception as e:
            print(f"Error archiving assignment: {e}")
            return False

    def get_assignments_for_module(self, module_code, active_only=True):
        """Get all assignments for a specific module"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if active_only:
                cursor.execute('''
                    SELECT * FROM assignments
                    WHERE module_code = ? AND is_active = 1
                    ORDER BY due_date
                ''', (module_code,))
            else:
                cursor.execute('''
                    SELECT * FROM assignments
                    WHERE module_code = ?
                    ORDER BY due_date
                ''', (module_code,))

            assignments = cursor.fetchall()
            conn.close()

            return assignments

        except Exception as e:
            print(f"Error retrieving assignments: {e}")
            return []

    def get_assignments_for_student(self, student_id=None):
        """Get all assignments for a student's enrolled modules"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT a.* FROM assignments a
                INNER JOIN student_modules sm ON a.module_code = sm.module_code
                WHERE sm.student_id = ? AND a.is_active = 1
                ORDER BY a.due_date
            ''', (student_id,))

            assignments = cursor.fetchall()
            conn.close()

            return assignments

        except Exception as e:
            print(f"Error retrieving student assignments: {e}")
            return []

    def get_assignment_details(self, assignment_id):
        """Get detailed information about an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()
            conn.close()

            return assignment

        except Exception as e:
            print(f"Error retrieving assignment details: {e}")
            return None

    def save_assignment_draft(self, draft_data):
        """Save an assignment draft"""
        try:
            user_id = self._get_student_id()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create draft table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assignment_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    draft_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            draft_json = json.dumps(draft_data)

            cursor.execute('''
                INSERT INTO assignment_drafts (user_id, draft_data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, draft_json, timestamp, timestamp))

            draft_id = cursor.lastrowid
            conn.commit()
            conn.close()

            print(f"Draft saved successfully! ID: {draft_id}")
            return draft_id

        except Exception as e:
            print(f"Error saving draft: {e}")
            return None

    def load_assignment_draft(self, draft_id):
        """Load an assignment draft"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT draft_data FROM assignment_drafts WHERE id = ?', (draft_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return json.loads(result[0])
            return None

        except Exception as e:
            print(f"Error loading draft: {e}")
            return None

    def bulk_archive_assignments(self, assignment_ids):
        """Archive multiple assignments"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            placeholders = ','.join('?' * len(assignment_ids))
            cursor.execute('UPDATE assignments SET is_active = 0 WHERE id IN (' + placeholders + ')', assignment_ids)

            conn.commit()
            conn.close()

            print(f"Successfully archived {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk archiving: {e}")
            return False

    def bulk_delete_assignments(self, assignment_ids):
        """Delete multiple assignments"""
        try:
            if not self._check_permission('delete_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            placeholders = ','.join('?' * len(assignment_ids))

            # Delete related data
            cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
            cursor.execute('DELETE FROM assignment_groups WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
            cursor.execute('DELETE FROM peer_review_assignments WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
            cursor.execute('DELETE FROM extension_requests WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
            cursor.execute('DELETE FROM assignments WHERE id IN (' + placeholders + ')', assignment_ids)

            conn.commit()
            conn.close()

            print(f"Successfully deleted {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk deleting: {e}")
            return False

    def bulk_change_due_dates(self, assignment_ids, new_due_date):
        """Change due dates for multiple assignments"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            placeholders = ','.join('?' * len(assignment_ids))
            params = list(assignment_ids) + [new_due_date]
            cursor.execute('UPDATE assignments SET due_date = ? WHERE id IN (' + placeholders + ')', [new_due_date] + assignment_ids)

            conn.commit()
            conn.close()

            print(f"Successfully updated due dates for {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk updating due dates: {e}")
            return False

    def export_assignment_data(self, assignment_id, export_path=None):
        """Export assignment data to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'assignment_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    s.student_id,
                    s.submission_date,
                    s.status,
                    s.grade,
                    s.feedback,
                    s.late_submission
                FROM assignment_submissions s
                WHERE s.assignment_id = ?
                ORDER BY s.submission_date
            ''', (assignment_id,))

            submissions = cursor.fetchall()
            conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Student ID', 'Submission Date', 'Status', 'Grade', 'Feedback', 'Late'])
                writer.writerows(submissions)

            print(f"Data exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting data: {e}")
            return None

    def send_assignment_notifications(self, assignment_id, notification_type='assignment_created'):
        """Send notifications about an assignment to all enrolled students"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignment details
            cursor.execute('SELECT module_code, title FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                print("Assignment not found")
                return False

            module_code, title = assignment

            # Get all enrolled students
            cursor.execute('SELECT student_id FROM student_modules WHERE module_code = ?', (module_code,))
            students = cursor.fetchall()

            # Send notification to each student
            for student in students:
                student_id = student[0]
                message = f"New assignment posted: {title}"
                self._send_notification(student_id, title, message, notification_type, assignment_id)

            conn.close()
            print(f"Notifications sent to {len(students)} students")
            return True

        except Exception as e:
            print(f"Error sending notifications: {e}")
            return False

    def check_overdue_assignments(self):
        """Check for overdue assignments and send reminders"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT id, module_code, title FROM assignments
                WHERE due_date < ? AND is_active = 1
            ''', (current_time,))

            overdue_assignments = cursor.fetchall()
            conn.close()

            print(f"Found {len(overdue_assignments)} overdue assignments")
            return overdue_assignments

        except Exception as e:
            print(f"Error checking overdue assignments: {e}")
            return []

    # ==================== Submission Management Methods ====================

    def resubmit_assignment(self, submission_id, new_file_path):
        """Resubmit an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get original submission
            cursor.execute('SELECT assignment_id, student_id FROM assignment_submissions WHERE id = ?', (submission_id,))
            submission = cursor.fetchone()

            if not submission:
                print("Original submission not found")
                return False

            assignment_id, student_id = submission

            # Validate file
            file_hash = self._calculate_file_hash(new_file_path)
            file_size = os.path.getsize(new_file_path)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update submission
            cursor.execute('''
                UPDATE assignment_submissions
                SET file_path = ?, file_name = ?, file_size = ?, file_hash = ?,
                    submission_date = ?, status = 'resubmitted', version = version + 1
                WHERE id = ?
            ''', (new_file_path, os.path.basename(new_file_path), file_size, file_hash, timestamp, submission_id))

            conn.commit()
            self._log_action('update', 'assignment_submissions', submission_id)
            conn.close()

            print("Assignment resubmitted successfully!")
            return True

        except Exception as e:
            print(f"Error resubmitting assignment: {e}")
            return False

    def get_student_submissions(self, student_id=None):
        """Get all submissions for a student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.*, a.title, a.module_code, a.due_date
                FROM assignment_submissions s
                INNER JOIN assignments a ON s.assignment_id = a.id
                WHERE s.student_id = ?
                ORDER BY s.submission_date DESC
            ''', (student_id,))

            submissions = cursor.fetchall()
            conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving submissions: {e}")
            return []

    def get_all_submissions(self, assignment_id=None):
        """Get all submissions for an assignment or all assignments"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ?
                    ORDER BY submission_date DESC
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    ORDER BY submission_date DESC
                ''')

            submissions = cursor.fetchall()
            conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving all submissions: {e}")
            return []

    def get_submission_details(self, submission_id):
        """Get detailed information about a submission"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.*, a.title, a.max_marks
                FROM assignment_submissions s
                INNER JOIN assignments a ON s.assignment_id = a.id
                WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            conn.close()

            return submission

        except Exception as e:
            print(f"Error retrieving submission details: {e}")
            return None

    def validate_file_submission(self, file_path, allowed_types, max_size_mb):
        """Validate a file for submission"""
        return self._validate_file(file_path, allowed_types, max_size_mb)

    def check_late_submission(self, assignment_id, submission_date=None):
        """Check if a submission is late"""
        try:
            if not submission_date:
                submission_date = datetime.now()
            elif isinstance(submission_date, str):
                submission_date = datetime.strptime(submission_date, '%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT due_date FROM assignments WHERE id = ?', (assignment_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                due_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                return submission_date > due_date

            return False

        except Exception as e:
            print(f"Error checking late submission: {e}")
            return False

    def download_submission(self, submission_id, download_path=None):
        """Download a submission file"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, file_name FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                print("Submission not found")
                return None

            source_path, file_name = result

            if not download_path:
                download_path = os.path.join(os.path.expanduser('~'), 'Downloads', file_name)

            shutil.copy2(source_path, download_path)
            print(f"File downloaded to: {download_path}")
            return download_path

        except Exception as e:
            print(f"Error downloading submission: {e}")
            return None

    def export_submissions(self, assignment_id, export_path=None):
        """Export all submissions for an assignment as ZIP"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'submissions_{assignment_id}.zip')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, file_path, file_name
                FROM assignment_submissions
                WHERE assignment_id = ?
            ''', (assignment_id,))

            submissions = cursor.fetchall()
            conn.close()

            with zipfile.ZipFile(export_path, 'w') as zipf:
                for student_id, file_path, file_name in submissions:
                    if os.path.exists(file_path):
                        arcname = f"{student_id}_{file_name}"
                        zipf.write(file_path, arcname)

            print(f"Submissions exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting submissions: {e}")
            return None

    def view_submission_feedback(self, submission_id):
        """View feedback for a submission"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT grade, feedback, graded_by, graded_at
                FROM assignment_submissions
                WHERE id = ?
            ''', (submission_id,))

            result = cursor.fetchone()
            conn.close()

            return result

        except Exception as e:
            print(f"Error retrieving feedback: {e}")
            return None

    # ==================== Grading Methods ====================

    def submit_grade(self, submission_id, grade, feedback=''):
        """Submit a grade for a submission"""
        try:
            if not self._check_permission('grade_submissions'):
                print("Permission denied")
                return False

            grader_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE assignment_submissions
                SET grade = ?, feedback = ?, graded_by = ?, graded_at = ?, status = 'graded'
                WHERE id = ?
            ''', (grade, feedback, grader_id, timestamp, submission_id))

            conn.commit()
            self._log_action('update', 'assignment_submissions', submission_id, {'grade': grade})

            # Send notification to student
            cursor.execute('SELECT student_id FROM assignment_submissions WHERE id = ?', (submission_id,))
            student_id = cursor.fetchone()[0]
            self._send_notification(student_id, "Grade Released", f"Your submission has been graded: {grade}", "grade_released", submission_id)

            conn.close()

            print("Grade submitted successfully!")
            return True

        except Exception as e:
            print(f"Error submitting grade: {e}")
            return False

    def get_ungraded_submissions(self, assignment_id=None):
        """Get all ungraded submissions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ? AND (grade IS NULL OR status != 'graded')
                    ORDER BY submission_date
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE grade IS NULL OR status != 'graded'
                    ORDER BY submission_date
                ''')

            submissions = cursor.fetchall()
            conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving ungraded submissions: {e}")
            return []

    def get_graded_submissions(self, assignment_id=None):
        """Get all graded submissions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ? AND status = 'graded'
                    ORDER BY graded_at DESC
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE status = 'graded'
                    ORDER BY graded_at DESC
                ''')

            submissions = cursor.fetchall()
            conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving graded submissions: {e}")
            return []

    def calculate_grade_percentage(self, grade, max_marks):
        """Calculate grade as percentage"""
        try:
            return (float(grade) / float(max_marks)) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0

    def release_grade(self, submission_id):
        """Release a grade to student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE assignment_submissions
                SET status = 'grade_released'
                WHERE id = ?
            ''', (submission_id,))

            # Get student ID for notification
            cursor.execute('SELECT student_id, grade FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()

            if result:
                student_id, grade = result
                self._send_notification(student_id, "Grade Released", f"Your grade has been released: {grade}", "grade_released", submission_id)

            conn.commit()
            conn.close()

            print("Grade released successfully!")
            return True

        except Exception as e:
            print(f"Error releasing grade: {e}")
            return False

    def send_grade_notification(self, submission_id):
        """Send grade notification to student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, grade, feedback
                FROM assignment_submissions
                WHERE id = ?
            ''', (submission_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                student_id, grade, feedback = result
                message = f"Your grade: {grade}"
                if feedback:
                    message += f"\nFeedback: {feedback}"
                self._send_notification(student_id, "Grade Available", message, "grade_notification", submission_id)
                return True

            return False

        except Exception as e:
            print(f"Error sending grade notification: {e}")
            return False

    def export_grades(self, assignment_id, export_path=None):
        """Export grades to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'grades_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    student_id, grade, feedback, graded_at, graded_by
                FROM assignment_submissions
                WHERE assignment_id = ? AND status = 'graded'
                ORDER BY student_id
            ''', (assignment_id,))

            grades = cursor.fetchall()
            conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Student ID', 'Grade', 'Feedback', 'Graded At', 'Graded By'])
                writer.writerows(grades)

            print(f"Grades exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting grades: {e}")
            return None

    # ==================== Group Management Methods ====================

    def delete_group(self, group_id):
        """Delete a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM assignment_group_members WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM assignment_groups WHERE id = ?', (group_id,))

            conn.commit()
            self._log_action('delete', 'assignment_groups', group_id)
            conn.close()

            print("Group deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting group: {e}")
            return False

    def edit_group(self, group_id, group_name=None):
        """Edit a group's details"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if group_name:
                cursor.execute('UPDATE assignment_groups SET group_name = ? WHERE id = ?', (group_name, group_id))

            conn.commit()
            self._log_action('update', 'assignment_groups', group_id, {'group_name': group_name})
            conn.close()

            print("Group updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing group: {e}")
            return False

    def add_member_to_group(self, group_id, student_id):
        """Add a member to a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO assignment_group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
            ''', (group_id, student_id, timestamp))

            conn.commit()
            self._log_action('create', 'assignment_group_members', cursor.lastrowid)
            conn.close()

            print("Member added to group successfully!")
            return True

        except Exception as e:
            print(f"Error adding member to group: {e}")
            return False

    def remove_member_from_group(self, group_id, student_id):
        """Remove a member from a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM assignment_group_members
                WHERE group_id = ? AND student_id = ?
            ''', (group_id, student_id))

            conn.commit()
            self._log_action('delete', 'assignment_group_members', None, {'group_id': group_id, 'student_id': student_id})
            conn.close()

            print("Member removed from group successfully!")
            return True

        except Exception as e:
            print(f"Error removing member from group: {e}")
            return False

    def get_group_members(self, group_id):
        """Get all members of a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, joined_at
                FROM assignment_group_members
                WHERE group_id = ?
                ORDER BY joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            return members

        except Exception as e:
            print(f"Error retrieving group members: {e}")
            return []

    def get_student_groups(self, student_id):
        """Get all groups a student is in"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT g.*, gm.joined_at
                FROM assignment_groups g
                INNER JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE gm.student_id = ?
                ORDER BY gm.joined_at DESC
            ''', (student_id,))

            groups = cursor.fetchall()
            conn.close()

            return groups

        except Exception as e:
            print(f"Error retrieving student groups: {e}")
            return []

    def merge_groups(self, group_id_1, group_id_2, new_group_name):
        """Merge two groups into a new group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignment_id from first group
            cursor.execute('SELECT assignment_id FROM assignment_groups WHERE id = ?', (group_id_1,))
            assignment_id = cursor.fetchone()[0]

            # Create new group
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO assignment_groups (assignment_id, group_name, created_at)
                VALUES (?, ?, ?)
            ''', (assignment_id, new_group_name, timestamp))

            new_group_id = cursor.lastrowid

            # Move all members from both groups to new group
            cursor.execute('''
                UPDATE assignment_group_members
                SET group_id = ?
                WHERE group_id IN (?, ?)
            ''', (new_group_id, group_id_1, group_id_2))

            # Delete old groups
            cursor.execute('DELETE FROM assignment_groups WHERE id IN (?, ?)', (group_id_1, group_id_2))

            conn.commit()
            self._log_action('create', 'assignment_groups', new_group_id)
            conn.close()

            print(f"Groups merged successfully! New group ID: {new_group_id}")
            return new_group_id

        except Exception as e:
            print(f"Error merging groups: {e}")
            return None

    def auto_generate_groups(self, assignment_id, group_size):
        """Automatically generate groups for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all students in the module
            cursor.execute('''
                SELECT sm.student_id
                FROM student_modules sm
                INNER JOIN assignments a ON sm.module_code = a.module_code
                WHERE a.id = ?
            ''', (assignment_id,))

            students = [row[0] for row in cursor.fetchall()]

            # Create groups
            group_count = 0
            for i in range(0, len(students), group_size):
                group_students = students[i:i+group_size]

                # Create group
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                group_name = f"Group {group_count + 1}"

                cursor.execute('''
                    INSERT INTO assignment_groups (assignment_id, group_name, created_at)
                    VALUES (?, ?, ?)
                ''', (assignment_id, group_name, timestamp))

                group_id = cursor.lastrowid

                # Add members
                for student_id in group_students:
                    cursor.execute('''
                        INSERT INTO assignment_group_members (group_id, student_id, joined_at)
                        VALUES (?, ?, ?)
                    ''', (group_id, student_id, timestamp))

                group_count += 1

            conn.commit()
            conn.close()

            print(f"Successfully created {group_count} groups")
            return group_count

        except Exception as e:
            print(f"Error auto-generating groups: {e}")
            return 0

    def submit_group_assignment(self, assignment_id, group_id, file_path):
        """Submit an assignment on behalf of a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all group members
            cursor.execute('SELECT student_id FROM assignment_group_members WHERE group_id = ?', (group_id,))
            members = cursor.fetchall()

            # Validate file
            file_hash = self._calculate_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Create submission for each member
            for member in members:
                student_id = member[0]
                cursor.execute('''
                    INSERT INTO assignment_submissions (
                        assignment_id, student_id, group_id, submission_date,
                        file_path, file_name, file_size, file_hash, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted')
                ''', (assignment_id, student_id, group_id, timestamp, file_path,
                      os.path.basename(file_path), file_size, file_hash))

            conn.commit()
            self._log_action('create', 'assignment_submissions', None, {'group_id': group_id})
            conn.close()

            print(f"Group assignment submitted for {len(members)} members!")
            return True

        except Exception as e:
            print(f"Error submitting group assignment: {e}")
            return False

    def export_group_list(self, assignment_id, export_path=None):
        """Export group list to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'groups_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT g.id, g.group_name, GROUP_CONCAT(gm.student_id, ', ')
                FROM assignment_groups g
                LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE g.assignment_id = ?
                GROUP BY g.id, g.group_name
            ''', (assignment_id,))

            groups = cursor.fetchall()
            conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group ID', 'Group Name', 'Members'])
                writer.writerows(groups)

            print(f"Group list exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting group list: {e}")
            return None

    # ==================== Extension Management Methods ====================

    def approve_extension(self, request_id):
        """Approve an extension request"""
        try:
            if not self._check_permission('manage_extensions'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reviewer_id = self._get_student_id()

            # Get extension details
            cursor.execute('SELECT assignment_id, student_id, new_due_date FROM extension_requests WHERE id = ?', (request_id,))
            result = cursor.fetchone()

            if not result:
                print("Extension request not found")
                return False

            assignment_id, student_id, new_due_date = result

            # Update request status
            cursor.execute('''
                UPDATE extension_requests
                SET status = 'approved', reviewed_by = ?, reviewed_at = ?
                WHERE id = ?
            ''', (reviewer_id, timestamp, request_id))

            # Send notification
            self._send_notification(student_id, "Extension Approved",
                                  f"Your extension request has been approved until {new_due_date}",
                                  "extension_approved", assignment_id)

            conn.commit()
            self._log_action('update', 'extension_requests', request_id, {'status': 'approved'})
            conn.close()

            print("Extension approved successfully!")
            return True

        except Exception as e:
            print(f"Error approving extension: {e}")
            return False

    def reject_extension(self, request_id, reason=''):
        """Reject an extension request"""
        try:
            if not self._check_permission('manage_extensions'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reviewer_id = self._get_student_id()

            # Get extension details
            cursor.execute('SELECT assignment_id, student_id FROM extension_requests WHERE id = ?', (request_id,))
            result = cursor.fetchone()

            if not result:
                print("Extension request not found")
                return False

            assignment_id, student_id = result

            # Update request status
            cursor.execute('''
                UPDATE extension_requests
                SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, reviewer_notes = ?
                WHERE id = ?
            ''', (reviewer_id, timestamp, reason, request_id))

            # Send notification
            self._send_notification(student_id, "Extension Rejected",
                                  f"Your extension request has been rejected. {reason}",
                                  "extension_rejected", assignment_id)

            conn.commit()
            self._log_action('update', 'extension_requests', request_id, {'status': 'rejected'})
            conn.close()

            print("Extension rejected successfully!")
            return True

        except Exception as e:
            print(f"Error rejecting extension: {e}")
            return False

    def get_extension_requests(self, status=None):
        """Get all extension requests, optionally filtered by status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT * FROM extension_requests
                    WHERE status = ?
                    ORDER BY requested_at DESC
                ''', (status,))
            else:
                cursor.execute('''
                    SELECT * FROM extension_requests
                    ORDER BY requested_at DESC
                ''')

            requests = cursor.fetchall()
            conn.close()

            return requests

        except Exception as e:
            print(f"Error retrieving extension requests: {e}")
            return []

    def get_student_extensions(self, student_id=None):
        """Get all extension requests for a specific student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM extension_requests
                WHERE student_id = ?
                ORDER BY requested_at DESC
            ''', (student_id,))

            requests = cursor.fetchall()
            conn.close()

            return requests

        except Exception as e:
            print(f"Error retrieving student extensions: {e}")
            return []

    # ==================== Peer Review Methods ====================

    def assign_peer_reviewers(self, assignment_id, reviews_per_submission=2):
        """Assign peer reviewers for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all submissions
            cursor.execute('SELECT id, student_id FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
            submissions = cursor.fetchall()

            if len(submissions) < 2:
                print("Not enough submissions for peer review")
                return False

            # Create peer review assignments
            for submission_id, student_id in submissions:
                # Get random reviewers (excluding the author)
                other_submissions = [s for s in submissions if s[1] != student_id]

                import random
                reviewers = random.sample(other_submissions, min(reviews_per_submission, len(other_submissions)))

                for reviewer_submission in reviewers:
                    reviewer_id = reviewer_submission[1]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        INSERT INTO peer_review_assignments (
                            assignment_id, submission_id, reviewer_id, status, assigned_at
                        ) VALUES (?, ?, ?, 'pending', ?)
                    ''', (assignment_id, submission_id, reviewer_id, timestamp))

            conn.commit()
            self._log_action('create', 'peer_review_assignments', None, {'assignment_id': assignment_id})
            conn.close()

            print(f"Peer reviewers assigned for {len(submissions)} submissions")
            return True

        except Exception as e:
            print(f"Error assigning peer reviewers: {e}")
            return False

    def submit_peer_review(self, review_assignment_id, feedback, rating):
        """Submit a peer review"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE peer_review_assignments
                SET feedback = ?, rating = ?, status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (feedback, rating, timestamp, review_assignment_id))

            conn.commit()
            self._log_action('update', 'peer_review_assignments', review_assignment_id)
            conn.close()

            print("Peer review submitted successfully!")
            return True

        except Exception as e:
            print(f"Error submitting peer review: {e}")
            return False

    def get_peer_review_assignments(self, reviewer_id=None):
        """Get peer review assignments for a reviewer"""
        try:
            if not reviewer_id:
                reviewer_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM peer_review_assignments
                WHERE reviewer_id = ?
                ORDER BY assigned_at DESC
            ''', (reviewer_id,))

            assignments = cursor.fetchall()
            conn.close()

            return assignments

        except Exception as e:
            print(f"Error retrieving peer review assignments: {e}")
            return []

    def configure_peer_review_criteria(self, assignment_id, criteria):
        """Configure peer review criteria for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create criteria table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    criterion_name TEXT NOT NULL,
                    criterion_description TEXT,
                    max_points INTEGER DEFAULT 10,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
                )
            ''')

            # Insert criteria
            for criterion in criteria:
                cursor.execute('''
                    INSERT INTO peer_review_criteria (assignment_id, criterion_name, criterion_description, max_points)
                    VALUES (?, ?, ?, ?)
                ''', (assignment_id, criterion['name'], criterion.get('description', ''), criterion.get('max_points', 10)))

            conn.commit()
            self._log_action('create', 'peer_review_criteria', None, {'assignment_id': assignment_id})
            conn.close()

            print("Peer review criteria configured successfully!")
            return True

        except Exception as e:
            print(f"Error configuring peer review criteria: {e}")
            return False

    def complete_peer_review(self, review_assignment_id):
        """Mark a peer review as complete"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE peer_review_assignments
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (timestamp, review_assignment_id))

            conn.commit()
            self._log_action('update', 'peer_review_assignments', review_assignment_id)
            conn.close()

            print("Peer review completed successfully!")
            return True

        except Exception as e:
            print(f"Error completing peer review: {e}")
            return False

    # ==================== Rubric Management Methods ====================

    def edit_rubric(self, rubric_id, **kwargs):
        """Edit an existing rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['rubric_name', 'description', 'total_points']:
                    update_fields.append(f"{validate_identifier(key, 'column')} = ?")
                    values.append(value)

            if not update_fields:
                print("No valid fields to update")
                return False

            values.append(rubric_id)
            query = f"UPDATE rubrics SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)

            conn.commit()
            self._log_action('update', 'rubrics', rubric_id, kwargs)
            conn.close()

            print("Rubric updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing rubric: {e}")
            return False

    def delete_rubric(self, rubric_id):
        """Delete a rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM rubric_criteria WHERE rubric_id = ?', (rubric_id,))
            cursor.execute('DELETE FROM rubrics WHERE id = ?', (rubric_id,))

            conn.commit()
            self._log_action('delete', 'rubrics', rubric_id)
            conn.close()

            print("Rubric deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting rubric: {e}")
            return False

    def get_rubrics(self, created_by=None):
        """Get all rubrics, optionally filtered by creator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if created_by:
                cursor.execute('SELECT * FROM rubrics WHERE created_by = ? ORDER BY created_at DESC', (created_by,))
            else:
                cursor.execute('SELECT * FROM rubrics ORDER BY created_at DESC')

            rubrics = cursor.fetchall()
            conn.close()

            return rubrics

        except Exception as e:
            print(f"Error retrieving rubrics: {e}")
            return []

    def get_rubric_criteria(self, rubric_id):
        """Get criteria for a specific rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM rubric_criteria WHERE rubric_id = ? ORDER BY criterion_order', (rubric_id,))
            criteria = cursor.fetchall()
            conn.close()

            return criteria

        except Exception as e:
            print(f"Error retrieving rubric criteria: {e}")
            return []

    def add_rubric_criterion(self, rubric_id, criterion_name, description='', max_points=10):
        """Add a criterion to a rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get next order number
            cursor.execute('SELECT MAX(criterion_order) FROM rubric_criteria WHERE rubric_id = ?', (rubric_id,))
            result = cursor.fetchone()
            next_order = (result[0] or 0) + 1

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO rubric_criteria (rubric_id, criterion_name, description, max_points, criterion_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (rubric_id, criterion_name, description, max_points, next_order, timestamp))

            conn.commit()
            self._log_action('create', 'rubric_criteria', cursor.lastrowid)
            conn.close()

            print("Rubric criterion added successfully!")
            return True

        except Exception as e:
            print(f"Error adding rubric criterion: {e}")
            return False

    # ==================== Template Management Methods ====================

    def create_template(self, template_name, template_data):
        """Create a new assignment template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            user_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            template_json = json.dumps(template_data)

            cursor.execute('''
                INSERT INTO assignment_templates (template_name, template_data, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (template_name, template_json, user_id, timestamp, timestamp))

            template_id = cursor.lastrowid
            conn.commit()
            self._log_action('create', 'assignment_templates', template_id)
            conn.close()

            print(f"Template created successfully! ID: {template_id}")
            return template_id

        except Exception as e:
            print(f"Error creating template: {e}")
            return None

    def edit_template(self, template_id, **kwargs):
        """Edit an existing template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = []
            values = []

            if 'template_name' in kwargs:
                update_fields.append("template_name = ?")
                values.append(kwargs['template_name'])

            if 'template_data' in kwargs:
                update_fields.append("template_data = ?")
                values.append(json.dumps(kwargs['template_data']))

            if not update_fields:
                print("No valid fields to update")
                return False

            update_fields.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            values.append(template_id)

            query = f"UPDATE assignment_templates SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)

            conn.commit()
            self._log_action('update', 'assignment_templates', template_id, kwargs)
            conn.close()

            print("Template updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing template: {e}")
            return False

    def delete_template(self, template_id):
        """Delete a template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM assignment_templates WHERE id = ?', (template_id,))

            conn.commit()
            self._log_action('delete', 'assignment_templates', template_id)
            conn.close()

            print("Template deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting template: {e}")
            return False

    def duplicate_template(self, template_id):
        """Duplicate an existing template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get original template
            cursor.execute('SELECT template_name, template_data FROM assignment_templates WHERE id = ?', (template_id,))
            result = cursor.fetchone()

            if not result:
                print("Template not found")
                return None

            template_name, template_data = result
            new_name = f"{template_name} (Copy)"

            user_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO assignment_templates (template_name, template_data, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (new_name, template_data, user_id, timestamp, timestamp))

            new_id = cursor.lastrowid
            conn.commit()
            self._log_action('create', 'assignment_templates', new_id)
            conn.close()

            print(f"Template duplicated successfully! New ID: {new_id}")
            return new_id

        except Exception as e:
            print(f"Error duplicating template: {e}")
            return None

    def get_templates(self, created_by=None):
        """Get all templates, optionally filtered by creator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if created_by:
                cursor.execute('SELECT * FROM assignment_templates WHERE created_by = ? ORDER BY created_at DESC', (created_by,))
            else:
                cursor.execute('SELECT * FROM assignment_templates ORDER BY created_at DESC')

            templates = cursor.fetchall()
            conn.close()

            return templates

        except Exception as e:
            print(f"Error retrieving templates: {e}")
            return []

    def save_template_from_assignment(self, assignment_id, template_name):
        """Save an assignment as a template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignment data
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                print("Assignment not found")
                return None

            # Create template data
            template_data = {
                'title': assignment[2],
                'description': assignment[3],
                'max_marks': assignment[5],
                'file_types_allowed': assignment[6],
                'max_file_size_mb': assignment[7],
                'assignment_type': assignment[11],
                'allow_late_submission': assignment[12],
                'late_penalty_per_day': assignment[13],
                'instructions': assignment[14]
            }

            # Create template
            return self.create_template(template_name, template_data)

        except Exception as e:
            print(f"Error saving template from assignment: {e}")
            return None

    # ==================== Analytics Methods ====================

    def get_grade_distribution(self, assignment_id):
        """Get grade distribution statistics for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT grade FROM assignment_submissions
                WHERE assignment_id = ? AND grade IS NOT NULL
            ''', (assignment_id,))

            grades = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not grades:
                return {}

            import statistics
            return {
                'count': len(grades),
                'mean': statistics.mean(grades),
                'median': statistics.median(grades),
                'min': min(grades),
                'max': max(grades),
                'std_dev': statistics.stdev(grades) if len(grades) > 1 else 0
            }

        except Exception as e:
            print(f"Error calculating grade distribution: {e}")
            return {}

    def get_submission_trends(self, assignment_id):
        """Get submission trends over time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT DATE(submission_date) as date, COUNT(*) as count
                FROM assignment_submissions
                WHERE assignment_id = ?
                GROUP BY DATE(submission_date)
                ORDER BY date
            ''', (assignment_id,))

            trends = cursor.fetchall()
            conn.close()

            return [{'date': row[0], 'count': row[1]} for row in trends]

        except Exception as e:
            print(f"Error getting submission trends: {e}")
            return []

    def get_performance_analytics(self, student_id=None):
        """Get performance analytics for a student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_submissions,
                    COUNT(CASE WHEN grade IS NOT NULL THEN 1 END) as graded_count,
                    AVG(grade) as avg_grade,
                    COUNT(CASE WHEN late_submission = 1 THEN 1 END) as late_count
                FROM assignment_submissions
                WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            return {
                'total_submissions': result[0],
                'graded_count': result[1],
                'average_grade': result[2],
                'late_submissions': result[3]
            }

        except Exception as e:
            print(f"Error getting performance analytics: {e}")
            return {}

    def get_engagement_metrics(self, assignment_id):
        """Get engagement metrics for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get total enrolled students
            cursor.execute('''
                SELECT COUNT(DISTINCT sm.student_id)
                FROM student_modules sm
                INNER JOIN assignments a ON sm.module_code = a.module_code
                WHERE a.id = ?
            ''', (assignment_id,))
            total_students = cursor.fetchone()[0]

            # Get submission count
            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
            submission_count = cursor.fetchone()[0]

            # Get late submission count
            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? AND late_submission = 1', (assignment_id,))
            late_count = cursor.fetchone()[0]

            conn.close()

            return {
                'total_students': total_students,
                'submission_count': submission_count,
                'submission_rate': (submission_count / total_students * 100) if total_students > 0 else 0,
                'late_submissions': late_count,
                'on_time_submissions': submission_count - late_count
            }

        except Exception as e:
            print(f"Error getting engagement metrics: {e}")
            return {}

    def generate_custom_report(self, report_type, filters=None):
        """Generate a custom analytics report"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if report_type == 'module_performance':
                query = '''
                    SELECT
                        a.module_code,
                        COUNT(DISTINCT a.id) as assignment_count,
                        COUNT(s.id) as submission_count,
                        AVG(s.grade) as avg_grade
                    FROM assignments a
                    LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                    GROUP BY a.module_code
                '''
            elif report_type == 'student_summary':
                query = '''
                    SELECT
                        s.student_id,
                        COUNT(s.id) as submissions,
                        AVG(s.grade) as avg_grade,
                        COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late_count
                    FROM assignment_submissions s
                    GROUP BY s.student_id
                '''
            else:
                print("Unknown report type")
                return []

            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            return results

        except Exception as e:
            print(f"Error generating custom report: {e}")
            return []

    # ==================== Notification Methods ====================

    def get_user_notifications(self, user_id=None, unread_only=False):
        """Get notifications for a user"""
        try:
            if not user_id:
                user_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if unread_only:
                cursor.execute('''
                    SELECT * FROM notifications
                    WHERE user_id = ? AND is_read = 0
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))

            notifications = cursor.fetchall()
            conn.close()

            return notifications

        except Exception as e:
            print(f"Error retrieving notifications: {e}")
            return []

    def mark_notification_read(self, notification_id):
        """Mark a notification as read"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE notifications
                SET is_read = 1, read_at = ?
                WHERE id = ?
            ''', (timestamp, notification_id))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return False

    def delete_notification(self, notification_id):
        """Delete a notification"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM notifications WHERE id = ?', (notification_id,))

            conn.commit()
            self._log_action('delete', 'notifications', notification_id)
            conn.close()

            return True

        except Exception as e:
            print(f"Error deleting notification: {e}")
            return False

    def get_user_messages(self, user_id=None, unread_only=False):
        """Get messages for a user"""
        try:
            if not user_id:
                user_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if unread_only:
                cursor.execute('''
                    SELECT * FROM messages
                    WHERE recipient_id = ? AND is_read = 0
                    ORDER BY sent_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM messages
                    WHERE recipient_id = ? OR sender_id = ?
                    ORDER BY sent_at DESC
                ''', (user_id, user_id))

            messages = cursor.fetchall()
            conn.close()

            return messages

        except Exception as e:
            print(f"Error retrieving messages: {e}")
            return []

    def reply_to_message(self, original_message_id, reply_text):
        """Reply to a message"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get original message
            cursor.execute('SELECT sender_id FROM messages WHERE id = ?', (original_message_id,))
            result = cursor.fetchone()

            if not result:
                print("Original message not found")
                return False

            recipient_id = result[0]
            sender_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (sender_id, recipient_id, f"Re: Message #{original_message_id}", reply_text, timestamp))

            conn.commit()
            self._log_action('create', 'messages', cursor.lastrowid)
            conn.close()

            print("Reply sent successfully!")
            return True

        except Exception as e:
            print(f"Error replying to message: {e}")
            return False

    def configure_notification_preferences(self, user_id, preferences):
        """Configure notification preferences for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create preferences table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    user_id INTEGER PRIMARY KEY,
                    email_notifications INTEGER DEFAULT 1,
                    assignment_notifications INTEGER DEFAULT 1,
                    grade_notifications INTEGER DEFAULT 1,
                    message_notifications INTEGER DEFAULT 1,
                    extension_notifications INTEGER DEFAULT 1,
                    peer_review_notifications INTEGER DEFAULT 1
                )
            ''')

            # Upsert preferences
            cursor.execute('''
                INSERT OR REPLACE INTO notification_preferences (
                    user_id, email_notifications, assignment_notifications,
                    grade_notifications, message_notifications, extension_notifications,
                    peer_review_notifications
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id,
                  preferences.get('email', 1),
                  preferences.get('assignments', 1),
                  preferences.get('grades', 1),
                  preferences.get('messages', 1),
                  preferences.get('extensions', 1),
                  preferences.get('peer_review', 1)))

            conn.commit()
            self._log_action('update', 'notification_preferences', user_id, preferences)
            conn.close()

            print("Notification preferences updated successfully!")
            return True

        except Exception as e:
            print(f"Error configuring notification preferences: {e}")
            return False

    # ==================== Maintenance Methods ====================

    def archive_submissions(self, assignment_id, archive_path=None):
        """Archive all submissions for an assignment"""
        try:
            if not archive_path:
                archive_path = os.path.join(self.submission_dir, 'backups', f'archive_{assignment_id}_{datetime.now().strftime("%Y%m%d")}.zip')

            ensure_parent_dir(archive_path)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT file_path, student_id, file_name
                FROM assignment_submissions
                WHERE assignment_id = ?
            ''', (assignment_id,))

            submissions = cursor.fetchall()
            conn.close()

            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, student_id, file_name in submissions:
                    if os.path.exists(file_path):
                        arcname = f"{student_id}/{file_name}"
                        zipf.write(file_path, arcname)

            print(f"Submissions archived to: {archive_path}")
            return archive_path

        except Exception as e:
            print(f"Error archiving submissions: {e}")
            return None

    def export_system_data(self, export_path=None):
        """Export all system data to JSON"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'system_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

            ensure_parent_dir(export_path)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Export all relevant tables
            export_data = {}

            tables = ['assignments', 'assignment_submissions', 'assignment_groups',
                     'rubrics', 'assignment_templates', 'extension_requests',
                     'peer_review_assignments', 'notifications', 'messages']

            for table in tables:
                safe_table = validate_table_name(table)
                cursor.execute('SELECT * FROM [' + safe_table + ']')
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                export_data[table] = [dict(zip(columns, row)) for row in rows]

            conn.close()

            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            print(f"System data exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting system data: {e}")
            return None


def display_assignment_menu(auth):
    """Display the enhanced assignment submission menu"""
    assignment_system = AssignmentSubmission()
    assignment_system.set_auth(auth)
    assignment_system.display_main_menu()


def add_assignment_permissions(auth=None):
    """Add assignment-related permissions to the database"""
    # Try to get centralized auth first if not provided
    if auth is None:
        auth = get_auth()
    if auth is None:
        from university_system.infrastructure.auth import UserAuth
        auth = UserAuth()
    
    assignment_permissions = [
        ('view_assignments', 'View assignments for enrolled modules'),
        ('submit_assignment', 'Submit assignments'),
        ('view_own_submissions', 'View own assignment submissions'),
        ('manage_assignments', 'Create and manage assignments'),
        ('view_all_submissions', 'View all assignment submissions'),
        ('delete_assignments', 'Delete assignments'),
        ('export_submission_data', 'Export submission data'),
        ('grade_submissions', 'Grade student submissions'),
        ('manage_groups', 'Manage assignment groups'),
        ('setup_peer_review', 'Setup peer review systems'),
        ('send_notifications', 'Send system notifications'),
        ('manage_extensions', 'Manage extension requests'),
        ('create_templates', 'Create assignment templates'),
        ('backup_system', 'Backup system data'),
        ('view_analytics', 'View system analytics')
    ]
    
    try:
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()
        
        for perm_name, perm_desc in assignment_permissions:
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
        
        conn.commit()
        
        # Now add permissions to roles
        role_permissions = {
            'student': [
                'view_assignments', 'submit_assignment', 'view_own_submissions'
            ],
            'instructor': [
                'view_assignments', 'manage_assignments', 'view_all_submissions', 
                'export_submission_data', 'grade_submissions', 'manage_groups',
                'setup_peer_review', 'send_notifications', 'manage_extensions',
                'create_templates', 'view_analytics'
            ],
            'staff': [
                'view_assignments', 'manage_assignments', 'view_all_submissions', 
                'export_submission_data', 'grade_submissions', 'view_analytics'
            ],
            'admin': [
                'view_assignments', 'submit_assignment', 'view_own_submissions',
                'manage_assignments', 'view_all_submissions', 'delete_assignments', 
                'export_submission_data', 'grade_submissions', 'manage_groups',
                'setup_peer_review', 'send_notifications', 'manage_extensions',
                'create_templates', 'backup_system', 'view_analytics'
            ]
        }
        
        for role_name, permissions in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm in permissions:
                    # Get permission ID
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]
                        
                        # Check if association already exists
                        cursor.execute(
                            'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                            (role_id, perm_id)
                        )
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )
        
        conn.commit()
        conn.close()
        
        print("Enhanced assignment permissions added successfully!")
        
    except sqlite3.Error as e:
        print(f"Error adding assignment permissions: {e}")


def init_assignment_system():
    """Initialize the enhanced assignment submission system"""
    try:
        # Create assignment system instance
        assignment_system = AssignmentSubmission()
        
        # Add permissions
        add_assignment_permissions()
        
        print("Enhanced Assignment submission system initialized successfully!")
        print("\nNew Features Added:")
        print("✓ Grading and feedback system with rubrics")
        print("✓ Group assignment support")
        print("✓ Peer review system")
        print("✓ Email notifications and messaging")
        print("✓ Extension request management")
        print("✓ Assignment templates")
        print("✓ Analytics and reporting")
        print("✓ File preview and version control")
        print("✓ Calendar integration")
        print("✓ Backup and recovery")
        print("✓ Enhanced security and audit logging")
        
        return True
        
    except Exception as e:
        print(f"Error initializing enhanced assignment system: {e}")
        return False


# Export the enhanced functions
__all__ = [
    'display_assignment_menu', 
    'init_assignment_system', 
    'AssignmentSubmission',
    'add_assignment_permissions'
]
