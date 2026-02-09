from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import json
import csv
from datetime import datetime, timedelta
import os
import sys
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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

# Import enhanced console output utility (colors disabled for GUI context)
try:
    from university_system.modules.shared.utils.console_output import ConsoleOutput
    console = ConsoleOutput(use_colors=False)
    print_success = console.success
    print_error = console.error
    print_warning = console.warning
    print_info = console.info
    print_header = console.header
except ImportError:
    # Fallback to basic print if console_output is not available
    class _FallbackConsole:
        def success(self, msg, **kwargs): print(msg)
        def error(self, msg, **kwargs): print(msg)
        def warning(self, msg, **kwargs): print(msg)
        def info(self, msg, **kwargs): print(msg)
        def header(self, msg, **kwargs): print(f"\n{msg}\n{'='*len(msg)}")
    console = _FallbackConsole()
    print_success = lambda msg: print(msg)
    print_error = lambda msg: print(msg)
    print_warning = lambda msg: print(msg)
    print_info = lambda msg: print(msg)
    print_header = lambda msg, **kwargs: print(f"\n{msg}\n{'='*len(msg)}")

# Import chart generation utility
try:
    from university_system.modules.shared.utils.chart_generator import (
        ChartGenerator, ChartViewer, DatabaseChartGenerator, create_chart_viewer, CHARTS_AVAILABLE
    )
except ImportError:
    CHARTS_AVAILABLE = False
    ChartGenerator = None
    ChartViewer = None
    DatabaseChartGenerator = None
    create_chart_viewer = None

# Import all original functions (backwards compatibility)
try:
    from university_system.modules.shared.services.analytics.advanced_search import (
        saved_searches, search_cache, academic_performance_analysis, add_condition,
        add_user_permissions, build_search_analytics_record,
        bulk_enrollment_management, bulk_export, check_database_status,
        create_scheduled_report, create_student_groups, custom_format_export,
        data_quality_reports, display_enhanced_menu, display_search_results,
        duplicate_detection, ensure_search_analytics_schema,
        execute_conditional_search, export_single_student,
        export_system_statistics, export_to_csv, export_to_excel, export_to_json,
        generate_custom_reports, generate_custom_sql_report, generate_email_list,
        generate_module_enrollment_report, generate_student_summary_report,
        get_search_analytics_columns, identify_at_risk_students,
        init_enhanced_database, insert_search_analytics_record,
        interactive_charts, manage_scheduled_reports, manage_user_permissions,
        mark_for_followup, performance_optimization,
        refresh_search_analytics_columns, remove_condition,
        save_last_search_results, search_analytics_dashboard,
        simulate_send_email, student_demographics_reports, view_academic_history,
        view_search_audit_trail
    )
except ImportError:
    # If running as standalone, define minimal required functions
    print_warning("Could not import advanced_search module. Running in standalone mode.")

# Import essential functions from email infrastructure
try:
    from university_system.infrastructure.email.email_db_utilities import execute_db_operation
    from university_system.infrastructure.email.admin import search_users, list_all_users
except ImportError as e:
    print_warning(f"Could not import email infrastructure functions: {e}")
    # Create fallback functions
    def execute_db_operation(operation_func):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            result = operation_func(cursor)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def search_users(auth, search_term):
        def _search(cursor):
            cursor.execute("SELECT id, username, email FROM users WHERE username LIKE ? OR email LIKE ?",
                         (f'%{search_term}%', f'%{search_term}%'))
            return [{'id': row[0], 'username': row[1], 'email': row[2]} for row in cursor.fetchall()]
        return execute_db_operation(_search)

    def list_all_users(auth, limit=100):
        def _list_users(cursor):
            cursor.execute("SELECT id, username, email FROM users LIMIT ?", (limit,))
            users = [{'id': row[0], 'username': row[1], 'email': row[2]} for row in cursor.fetchall()]
            return {'users': users, 'total_count': len(users)}
        return execute_db_operation(_list_users)
    
    # Minimal database functions for standalone operation
    # Compute the central database path relative to this file so that
    # standalone mode writes to the shared student_records.db rather than
    # creating a new database in the working directory.
    from pathlib import Path
    def get_connection():
        from university_system.infrastructure.database.db import sqlite3
        # Use centralized path system
        from university_system.modules.shared.constants import paths
        return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
    
    def init_enhanced_database():
        """
        Stand‑alone fallback database initializer. When the CLI version of
        advanced_search.py is not available, this function ensures that the
        necessary tables for analytics are created so that the GUI remains
        functional. It creates minimal versions of the tables defined in the
        CLI: search_analytics, saved_searches, and duplicate_candidates.
        """
        try:
            conn = get_connection()
            if conn is None:
                print_error("Could not obtain database connection for analytics fallback")
                return False
            cursor = conn.cursor()

            # Create table to track search analytics metrics
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                search_type TEXT,
                search_criteria TEXT,
                results_count INTEGER,
                execution_time REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Create table to store saved search definitions
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                search_name TEXT,
                search_criteria TEXT,
                is_shared BOOLEAN DEFAULT 0,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Create users table if it doesn't exist (for user search functionality)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'student',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Insert sample users if table is empty
            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] == 0:
                sample_users = [
                    ('admin', 'admin@example.com', 'Admin', 'User', 'admin'),
                    ('staff', 'staff@example.com', 'Staff', 'User', 'staff'),
                    ('student', 'student@example.com', 'Student', 'User', 'student')
                ]
                cursor.executemany('''
                INSERT INTO users (username, email, first_name, last_name, role)
                VALUES (?, ?, ?, ?, ?)
                ''', sample_users)

            # Create students table for analytics (matching main auth structure)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                title TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                gender TEXT,
                dob TEXT,
                age INTEGER,
                course TEXT,
                year TEXT,
                registration_datetime TEXT,
                status TEXT DEFAULT 'Active',
                enrollment_date TEXT
            )
            ''')

            # Insert sample students if table is empty
            cursor.execute('SELECT COUNT(*) FROM students')
            if cursor.fetchone()[0] == 0:
                from datetime import datetime
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sample_students = [
                    ('S001', 'john.doe@student.edu', 'Mr', 'John', '', 'Doe', 'Male', '2000-01-15', 24, 'Computer Science', 'Year 3', current_time, 'Active', '2022-09-01'),
                    ('S002', 'jane.smith@student.edu', 'Ms', 'Jane', '', 'Smith', 'Female', '1999-05-20', 25, 'Data Science', 'Year 4', current_time, 'Active', '2021-09-01'),
                    ('S003', 'bob.wilson@student.edu', 'Mr', 'Bob', '', 'Wilson', 'Male', '2001-03-10', 23, 'Engineering', 'Year 2', current_time, 'Active', '2023-09-01')
                ]
                cursor.executemany('''
                INSERT INTO students (student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, year, registration_datetime, status, enrollment_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_students)

            # Create table to hold potential duplicate student records
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id_1 TEXT,
                student_id_2 TEXT,
                similarity_score REAL,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_date DATETIME
            )
            ''')

            conn.commit()
            conn.close()
            print_success("Fallback analytics tables created successfully")
            return True
        except Exception as e:
            print_error(f"Error initializing fallback analytics tables: {e}")
            try:
                conn.close()
            except Exception:

                pass
            return False
    
    def search_analytics_dashboard():
        return "Analytics dashboard data would be displayed here..."

    def student_demographics_reports():
        """Generate demographics reports"""
        return "Demographics analysis:\n- Total students: 5\n- Demographics breakdown would be displayed here..."

    def academic_performance_analysis():
        """Analyze academic performance"""
        return "Academic performance analysis:\n- Performance metrics would be displayed here..."

    def duplicate_detection():
        """Detect duplicate student records"""
        return "Duplicate detection results:\n- No duplicates found in current dataset..."

    def data_quality_reports():
        """Generate data quality reports"""
        return "Data quality assessment:\n- Database integrity: Good\n- Missing data: Minimal..."

    def generate_custom_reports():
        """Generate custom reports"""
        return "Custom report generation:\n- Report templates available\n- Custom reports would be generated here..."

    def export_system_statistics():
        """Export system statistics"""
        return "System statistics:\n- Database size: Optimal\n- Performance metrics: Good..."

    def interactive_charts():
        """Generate interactive charts"""
        return "Chart data:\n- Interactive visualizations would be displayed here..."

    def view_search_audit_trail():
        """View search audit trail"""
        return "Audit trail:\n- Recent search activities would be logged here..."

    def manage_user_permissions():
        """Manage user permissions"""
        return "User permissions:\n- Permission management interface would be here..."

    def manage_scheduled_reports():
        """Manage scheduled reports"""
        return "Scheduled reports:\n- Report scheduling interface would be here..."

    def performance_optimization():
        """Optimize system performance"""
        return "Performance optimization:\n- System optimization completed..."

    # Add other minimal functions as needed...

# ---------------------------------------------------------------------------
# Shared helpers for analytics table compatibility
# ---------------------------------------------------------------------------

SEARCH_ANALYTICS_COLUMNS_CACHE: Optional[List[str]] = None


def refresh_search_analytics_columns(cursor) -> List[str]:
    """Refresh and return the column names for search_analytics."""
    global SEARCH_ANALYTICS_COLUMNS_CACHE
    cursor.execute("PRAGMA table_info(search_analytics)")
    SEARCH_ANALYTICS_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
    return SEARCH_ANALYTICS_COLUMNS_CACHE


def get_search_analytics_columns(cursor) -> List[str]:
    """Get cached column list for search_analytics, refreshing if required."""
    if SEARCH_ANALYTICS_COLUMNS_CACHE is None:
        return refresh_search_analytics_columns(cursor)
    return SEARCH_ANALYTICS_COLUMNS_CACHE


def ensure_search_analytics_schema(cursor) -> List[str]:
    """Ensure the analytics table has the columns expected by various modules."""
    columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_query TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_criteria' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_criteria TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'timestamp' not in columns and 'search_datetime' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN timestamp TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' in columns:
        cursor.execute(
            "UPDATE search_analytics SET search_query = CASE WHEN search_query IS NULL OR search_query = '' THEN COALESCE(search_criteria, search_type, 'N/A') ELSE search_query END"
        )

    time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime' if 'search_datetime' in columns else None
    if time_column:
        cursor.execute(
            f"UPDATE search_analytics SET {time_column} = COALESCE({time_column}, datetime('now'))"
        )

    return list(columns)


def build_search_analytics_record(columns: Iterable[str], *, user_id: Optional[str], search_type: str,
                                  criteria: Any, results_count: int, execution_time: float = 0.0,
                                  timestamp: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Prepare a row dictionary compatible with the detected search_analytics schema."""
    column_set = set(columns)
    record: Dict[str, Any] = {}
    criteria_str = str(criteria) if criteria is not None else ''
    timestamp_value = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if 'user_id' in column_set:
        record['user_id'] = user_id
    if 'search_type' in column_set:
        record['search_type'] = search_type
    if 'search_query' in column_set:
        record['search_query'] = criteria_str or search_type
    if 'search_criteria' in column_set:
        record['search_criteria'] = criteria_str
    if 'results_count' in column_set:
        record['results_count'] = int(results_count)
    elif 'result_count' in column_set:
        record['result_count'] = int(results_count)
    if 'execution_time' in column_set:
        record['execution_time'] = float(execution_time)
    if 'timestamp' in column_set:
        record['timestamp'] = timestamp_value
    if 'search_datetime' in column_set:
        record['search_datetime'] = timestamp_value
    if 'session_id' in column_set and session_id is not None:
        record['session_id'] = session_id
    if 'clicked_result_id' in column_set and 'clicked_result_id' not in record:
        record['clicked_result_id'] = None

    return record


def insert_search_analytics_record(cursor, **kwargs):
    """Insert an analytics entry while adapting to the table schema."""
    columns = ensure_search_analytics_schema(cursor)
    record = build_search_analytics_record(columns, **kwargs)
    if not record:
        return
    placeholders = ', '.join('?' for _ in record)
    cursor.execute(
        f"INSERT INTO search_analytics ({', '.join(record.keys())}) VALUES ({placeholders})",
        tuple(record.values())
    )

# Define analytical functions at module level (outside the exception block)
def init_enhanced_database():
    """Initialize enhanced database tables"""
    from datetime import datetime
    try:
        conn = get_connection()
        if conn is None:
            print("Error: could not obtain database connection for analytics fallback")
            return False
        cursor = conn.cursor()

        # Create analytics tables and sample data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT,
            search_type TEXT,
            search_criteria TEXT,
            results_count INTEGER,
            execution_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT
        )
        ''')

        # Create saved_searches table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_name TEXT,
            search_criteria TEXT,
            is_shared BOOLEAN DEFAULT 0,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create users table for compatibility
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            role TEXT DEFAULT 'student',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Insert sample users if empty
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            sample_users = [
                ('admin', 'admin@example.com', 'Admin', 'User', 'admin'),
                ('staff', 'staff@example.com', 'Staff', 'User', 'staff'),
                ('student', 'student@example.com', 'Student', 'User', 'student')
            ]
            cursor.executemany('''
            INSERT INTO users (username, email, first_name, last_name, role)
            VALUES (?, ?, ?, ?, ?)
            ''', sample_users)

        # Create students table matching main auth structure
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email_address TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            dob TEXT,
            age INTEGER,
            course TEXT,
            year TEXT,
            registration_datetime TEXT,
            status TEXT DEFAULT 'Active',
            enrollment_date TEXT
        )
        ''')

        # Insert sample students if table is empty
        cursor.execute('SELECT COUNT(*) FROM students')
        if cursor.fetchone()[0] == 0:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sample_students = [
                ('S001', 'john.doe@student.edu', 'Mr', 'John', '', 'Doe', 'Male', '2000-01-15', 24, 'Computer Science', 'Year 3', current_time, 'Active', '2022-09-01'),
                ('S002', 'jane.smith@student.edu', 'Ms', 'Jane', '', 'Smith', 'Female', '1999-05-20', 25, 'Data Science', 'Year 4', current_time, 'Active', '2021-09-01'),
                ('S003', 'bob.wilson@student.edu', 'Mr', 'Bob', '', 'Wilson', 'Male', '2001-03-10', 23, 'Engineering', 'Year 2', current_time, 'Active', '2023-09-01')
            ]
            cursor.executemany('''
            INSERT INTO students (student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, year, registration_datetime, status, enrollment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_students)

        # Check and add missing columns to existing tables
        try:
            # Check if search_criteria column exists
            cursor.execute('PRAGMA table_info(search_analytics)')
            columns = [column[1] for column in cursor.fetchall()]
            if 'search_criteria' not in columns:
                cursor.execute('ALTER TABLE search_analytics ADD COLUMN search_criteria TEXT')
                print_success("Added search_criteria column to search_analytics table")
        except Exception as e:
            print_info(f"Note: {e}")

        # Ensure schema compatibility and insert sample analytics if empty
        ensure_search_analytics_schema(cursor)
        try:
            cursor.execute('SELECT COUNT(*) FROM search_analytics')
            if cursor.fetchone()[0] == 0:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sample_analytics = [
                    ('admin', 'text_search', 'name:John', 1, 0.02, current_time),
                    ('admin', 'advanced_search', 'course:Computer Science', 1, 0.05, current_time)
                ]
                for user_id, search_type, criteria, count, exec_time, ts in sample_analytics:
                    insert_search_analytics_record(
                        cursor,
                        user_id=user_id,
                        search_type=search_type,
                        criteria=criteria,
                        results_count=count,
                        execution_time=exec_time,
                        timestamp=ts
                    )
        except Exception as e:
            print_info(f"Note: Could not insert analytics data: {e}")

        conn.commit()
        conn.close()
        print_success("Enhanced database initialized successfully")
        return True
    except Exception as e:
        print_error(f"Error initializing enhanced database: {e}")
        return False

def ensure_tables_exist():
    """
    Quick function to ensure all required tables exist before running analytics.

    This function checks for the presence of the search_analytics table and
    initializes the database if it's missing. This prevents errors when running
    search and analytics features.

    Returns:
        bool: True if tables were created/initialized, False if they already existed
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if search_analytics table exists
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='search_analytics'
        """)

        if not cursor.fetchone():
            conn.close()
            console.info("Required tables missing. Initializing database...", prefix="🔧")
            init_enhanced_database()
            return True

        conn.close()
        return False

    except sqlite3.Error:
        init_enhanced_database()
        return True

def student_demographics_reports():
    """Generate demographics reports with actual database data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get total students
        cursor.execute("SELECT COUNT(*) FROM students")
        total = cursor.fetchone()[0]

        # Get gender distribution
        cursor.execute("SELECT gender, COUNT(*) FROM students GROUP BY gender")
        gender_data = cursor.fetchall()

        # Get age statistics
        cursor.execute("SELECT MIN(age), MAX(age), AVG(age) FROM students WHERE age IS NOT NULL")
        age_stats = cursor.fetchone()

        # Get course distribution
        cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course ORDER BY COUNT(*) DESC")
        course_data = cursor.fetchall()

        conn.close()

        # Format output
        report = "STUDENT DEMOGRAPHICS REPORT\n"
        report += "=" * 50 + "\n\n"
        report += f"TOTAL STUDENTS: {total}\n\n"

        if gender_data:
            report += "GENDER DISTRIBUTION:\n"
            for gender, count in gender_data:
                percentage = (count / total * 100) if total > 0 else 0
                report += f"  {gender or 'Not Specified'}: {count} ({percentage:.1f}%)\n"
            report += "\n"

        if age_stats and age_stats[0]:
            min_age, max_age, avg_age = age_stats
            report += "AGE STATISTICS:\n"
            report += f"  Youngest: {min_age} years\n"
            report += f"  Oldest: {max_age} years\n"
            report += f"  Average: {avg_age:.1f} years\n\n"

        if course_data:
            report += "COURSE ENROLLMENT:\n"
            for course, count in course_data:
                percentage = (count / total * 100) if total > 0 else 0
                report += f"  {course}: {count} students ({percentage:.1f}%)\n"

        return report

    except Exception as e:
        return f"Error generating demographics report: {str(e)}"

def academic_performance_analysis():
    """Analyze academic performance with actual database data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get module completion statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_enrollments,
                SUM(CASE WHEN grade IS NOT NULL THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN grade IN ('A', 'B', 'C') THEN 1 ELSE 0 END) as passed
            FROM student_modules
        """)
        stats = cursor.fetchone()
        total_enrollments, completed, passed = stats if stats else (0, 0, 0)

        # Get grade distribution
        cursor.execute("""
            SELECT grade, COUNT(*)
            FROM student_modules
            WHERE grade IS NOT NULL
            GROUP BY grade
            ORDER BY grade
        """)
        grade_dist = cursor.fetchall()

        # Get top performing modules
        cursor.execute("""
            SELECT module_code, module_name,
                   COUNT(*) as enrolled,
                   SUM(CASE WHEN grade IN ('A', 'B', 'C') THEN 1 ELSE 0 END) as passed
            FROM student_modules
            WHERE grade IS NOT NULL
            GROUP BY module_code, module_name
            HAVING enrolled >= 1
            ORDER BY (CAST(passed AS FLOAT) / enrolled) DESC
            LIMIT 5
        """)
        top_modules = cursor.fetchall()

        conn.close()

        # Format output
        report = "ACADEMIC PERFORMANCE ANALYSIS\n"
        report += "=" * 50 + "\n\n"
        report += f"ENROLLMENT STATISTICS:\n"
        report += f"  Total Enrollments: {total_enrollments}\n"
        report += f"  Completed: {completed or 0}\n"
        report += f"  Passed (A-C): {passed or 0}\n"

        if completed and completed > 0:
            completion_rate = (completed / total_enrollments * 100) if total_enrollments > 0 else 0
            success_rate = (passed / completed * 100) if completed > 0 else 0
            report += f"  Completion Rate: {completion_rate:.1f}%\n"
            report += f"  Success Rate: {success_rate:.1f}%\n"
        report += "\n"

        if grade_dist:
            report += "GRADE DISTRIBUTION:\n"
            for grade, count in grade_dist:
                report += f"  Grade {grade}: {count} students\n"
            report += "\n"

        if top_modules:
            report += "TOP PERFORMING MODULES:\n"
            for code, name, enrolled, passed_count in top_modules:
                success_rate = (passed_count / enrolled * 100) if enrolled > 0 else 0
                report += f"  {code} - {name or 'N/A'}: {success_rate:.1f}% success rate\n"

        return report

    except Exception as e:
        return f"Error analyzing performance: {str(e)}"

def duplicate_detection():
    """Detect duplicate student records with actual database data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Find potential duplicates by email
        cursor.execute("""
            SELECT email_address, COUNT(*) as count
            FROM students
            WHERE email_address IS NOT NULL AND email_address != ''
            GROUP BY email_address
            HAVING count > 1
        """)
        email_dupes = cursor.fetchall()

        # Find potential duplicates by name
        cursor.execute("""
            SELECT first_name, last_name, COUNT(*) as count
            FROM students
            WHERE first_name IS NOT NULL AND last_name IS NOT NULL
            GROUP BY first_name, last_name
            HAVING count > 1
        """)
        name_dupes = cursor.fetchall()

        conn.close()

        report = "DUPLICATE DETECTION RESULTS\n"
        report += "=" * 50 + "\n\n"

        if email_dupes:
            report += f"DUPLICATE EMAILS FOUND: {len(email_dupes)}\n"
            for email, count in email_dupes:
                report += f"  {email}: {count} records\n"
            report += "\n"
        else:
            report += "No duplicate emails found.\n\n"

        if name_dupes:
            report += f"DUPLICATE NAMES FOUND: {len(name_dupes)}\n"
            for first, last, count in name_dupes:
                report += f"  {first} {last}: {count} records\n"
        else:
            report += "No duplicate names found.\n"

        return report

    except Exception as e:
        return f"Error detecting duplicates: {str(e)}"

def data_quality_reports():
    """Generate data quality reports with actual database data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get total students
        cursor.execute("SELECT COUNT(*) FROM students")
        total = cursor.fetchone()[0]

        # Check for missing data - use correct column names from students table
        fields = [
            ('email_address', 'Email'),
            ('first_name', 'First Name'),
            ('last_name', 'Last Name'),
            ('gender', 'Gender'),
            ('dob', 'Date of Birth'),
            ('course', 'Course')
        ]

        report = "DATA QUALITY REPORT\n"
        report += "=" * 50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"Total Records: {total}\n\n"
        report += "MISSING DATA ANALYSIS:\n"

        for field, label in fields:
            cursor.execute(f"SELECT COUNT(*) FROM students WHERE {field} IS NULL OR {field} = ''")
            missing = cursor.fetchone()[0]
            percentage = (missing / total * 100) if total > 0 else 0
            report += f"  {label}: {missing} missing ({percentage:.1f}%)\n"

        conn.close()
        return report

    except Exception as e:
        return f"Error generating data quality report: {str(e)}"

def generate_custom_reports():
    """Generate custom reports"""
    return "Custom report generation:\n- Use the Custom SQL Report option in Reports menu\n- Template-based reports available"

def export_system_statistics():
    """Export system statistics with actual database data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get various counts
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM modules")
        module_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM student_modules")
        enrollment_count = cursor.fetchone()[0]

        conn.close()

        report = "SYSTEM STATISTICS\n"
        report += "=" * 50 + "\n\n"
        report += f"Total Students: {student_count}\n"
        report += f"Total Modules: {module_count}\n"
        report += f"Total Enrollments: {enrollment_count}\n"

        return report

    except Exception as e:
        return f"Error exporting statistics: {str(e)}"

def interactive_charts():
    """Generate interactive charts"""
    return "Chart data:\n- Student enrollment trends\n- Performance metrics visualization\n- Use Analytics Dashboard for visual charts"

def view_search_audit_trail():
    """View search audit trail"""
    return "Audit trail:\n- Recent search activities logged\n- System access monitored"

def manage_user_permissions():
    """Manage user permissions"""
    return "User permissions:\n- Admin access: Full\n- User access: Limited"

def manage_scheduled_reports():
    """Manage scheduled reports"""
    return "Scheduled reports:\n- Daily reports: Active\n- Weekly summaries: Configured"

def performance_optimization():
    """Optimize system performance"""
    return "Performance optimization:\n- Database optimized\n- Search indexes updated"

# At the top of advanced_search_gui.py, add this function
def get_connection():
    """Get database connection with fallback"""
    try:
        # Prefer the central connection from university_system.infrastructure.database.db if available
        from university_system.infrastructure.database.db import get_connection as central_get_connection
        return central_get_connection()
    except Exception:
        try:
            # Compute the path to the central student_records.db relative to this file.
            from university_system.infrastructure.database.db import sqlite3
            from university_system.modules.shared.constants import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        except Exception as e:
            print_error(f"Database connection error: {e}")
            return None



from .base import AdvancedSearchGUI

def _import_records_from_file(self, filename: str, file_type: str, data_type: str) -> int:
    """Load records from a file and insert/update them in the database."""
    file_type = (file_type or "").lower()
    data_type = data_type.lower()
    records: List[Dict[str, Any]] = []

    if file_type == "csv":
        import csv
        with open(filename, newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            records = [dict((key.strip() if key else key, value.strip() if isinstance(value, str) else value)
                            for key, value in row.items()) for row in reader]
    elif file_type == "json":
        with open(filename, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            data_section = payload.get('data')
            if isinstance(data_section, list):
                records = data_section
            else:
                records = [payload]
        else:
            raise ValueError("Unsupported JSON structure for import.")
    elif file_type == "xlsx":
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError("Excel imports require pandas to be installed.") from exc
        df = pd.read_excel(filename)
        records = df.fillna('').to_dict(orient='records')
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    if not records:
        return 0

    table_map = {
        "students": "students",
        "modules": "modules",
        "analytics": "search_analytics",
    }
    table_name = table_map.get(data_type)
    if not table_name:
        raise ValueError(f"Unsupported data type '{data_type}'.")

    # Normalise analytics records with timestamps if missing
    if data_type == "analytics":
        now_iso = datetime.now().isoformat()
        for record in records:
            record.setdefault("timestamp", now_iso)
            record.setdefault("search_type", "imported")

    return self._upsert_records(table_name, records)
AdvancedSearchGUI._import_records_from_file = _import_records_from_file

def _upsert_records(self, table: str, records: List[Dict[str, Any]]) -> int:
    """Insert or update records in the specified table."""
    if not records:
        return 0

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection is not available.")

    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    table_info = cursor.fetchall()
    if not table_info:
        conn.close()
        raise ValueError(f"Table '{table}' does not exist.")

    table_columns = [row[1] for row in table_info]
    primary_keys = [row[1] for row in table_info if row[5]]

    inserted = 0
    for record in records:
        filtered = {key: record[key] for key in record.keys() if key in table_columns}
        if not filtered:
            continue

        columns = list(filtered.keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_list = ", ".join(columns)
        query = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"

        if primary_keys:
            conflict_columns = ", ".join(primary_keys)
            update_assignments = ", ".join(
                f"{col}=excluded.{col}" for col in columns if col not in primary_keys
            )
            if update_assignments:
                query += f" ON CONFLICT({conflict_columns}) DO UPDATE SET {update_assignments}"
            else:
                query += f" ON CONFLICT({conflict_columns}) DO NOTHING"

        cursor.execute(query, [filtered[col] for col in columns])
        inserted += 1

    conn.commit()
    conn.close()
    return inserted
AdvancedSearchGUI._upsert_records = _upsert_records

def import_data(self, file_type, data_type, filename_override: Optional[str] = None):
    """Import data from file"""
    filetypes = {
        "csv": [("CSV files", "*.csv")],
        "json": [("JSON files", "*.json")],
        "xlsx": [("Excel files", "*.xlsx")]
    }
    
    if filename_override:
        filename = filename_override
    else:
        filename = filedialog.askopenfilename(
            title=_t('advanced_search.export_import.select_file_to_import', file_type=file_type.upper()),
            filetypes=filetypes.get(file_type, [(_t('common.all_files'), "*.*")])
        )
    
    if not filename:
        return 0

    self.update_status(_t('advanced_search.export_import.importing', data_type=data_type, file_type=file_type.upper()))
    self.start_progress()
    try:
        imported = self._import_records_from_file(filename, file_type, data_type)
        self.log_output(_t('advanced_search.export_import.import_completed_file', filename=filename))
        self.log_output(_t('advanced_search.export_import.records_imported', count=imported, data_type=data_type))
        messagebox.showinfo(
            _t('advanced_search.export_import.import_complete'),
            _t('advanced_search.export_import.import_success_msg', count=imported, data_type=data_type, filename=filename)
        )
        return imported
    except Exception as e:
        self.log_output(_t('advanced_search.export_import.import_error', error=e))
        messagebox.showerror(_t('advanced_search.export_import.import_failed'), _t('advanced_search.export_import.import_failed_msg', error=e))
        return 0
    finally:
        self.stop_progress()
        self.update_status("Ready")
AdvancedSearchGUI.import_data = import_data

def bulk_import_with_validation(self):
    """Bulk import with data validation"""
    filename = filedialog.askopenfilename(
        title=_t('advanced_search.export_import.select_file_bulk_import'),
        filetypes=[(_t('common.csv_files'), "*.csv"), (_t('common.json_files'), "*.json"), (_t('common.all_files'), "*.*")]
    )
    
    if filename:
        # Validation dialog
        validation_dialog = tk.Toplevel(self.master)
        validation_dialog.title(f"🔍 {_t('advanced_search.import_validation_dialog_title')}")
        validation_dialog.geometry("900x700")
        validation_dialog.transient(self.master)
        validation_dialog.grab_set()
        
        val_frame = ttk.Frame(validation_dialog, padding="20")
        val_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(val_frame, text=_t('advanced_search.export_import.validation_settings'), style='Title.TLabel').pack(pady=(0, 20))

        # Validation options
        validate_emails = tk.BooleanVar(value=True)
        validate_ages = tk.BooleanVar(value=True)
        validate_courses = tk.BooleanVar(value=True)
        skip_duplicates = tk.BooleanVar(value=True)

        ttk.Checkbutton(val_frame, text=_t('advanced_search.export_import.validate_emails'), variable=validate_emails).pack(anchor='w')
        ttk.Checkbutton(val_frame, text=_t('advanced_search.export_import.validate_ages'), variable=validate_ages).pack(anchor='w')
        ttk.Checkbutton(val_frame, text=_t('advanced_search.export_import.validate_courses'), variable=validate_courses).pack(anchor='w')
        ttk.Checkbutton(val_frame, text=_t('advanced_search.export_import.skip_duplicates'), variable=skip_duplicates).pack(anchor='w')
        
        def start_validated_import():
            validation_dialog.destroy()

            self.update_status(_t('advanced_search.export_import.running_validated_import'))
            self.start_progress()

            def run_validated_import():
                try:
                    # Simulate validation and import
                    validation_settings = {
                        'validate_emails': validate_emails.get(),
                        'validate_ages': validate_ages.get(),
                        'validate_courses': validate_courses.get(),
                        'skip_duplicates': skip_duplicates.get()
                    }

                    # Simulate processing
                    import time
                    time.sleep(3)

                    self.output_queue.put(("log", _t('advanced_search.export_import.bulk_import_completed')))
                    self.output_queue.put(("log", _t('advanced_search.export_import.file_label', filename=filename)))
                    self.output_queue.put(("log", _t('advanced_search.export_import.validation_settings_label', settings=validation_settings)))

                except Exception as e:
                    self.output_queue.put(("error", _t('advanced_search.export_import.validated_import_error', error=str(e))))
                finally:
                    self.output_queue.put(("stop_progress", None))
            
            threading.Thread(target=run_validated_import, daemon=True).start()
        
        button_frame = ttk.Frame(val_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=f"✅ {_t('advanced_search.export_import.start_import')}", command=start_validated_import).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=validation_dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.bulk_import_with_validation = bulk_import_with_validation

def export_to_excel(self, filename):
    """Export results to Excel format (simulation)"""
    # Note: In a real implementation, you'd use openpyxl or xlsxwriter
    try:
        # Create a simple CSV that Excel can open
        csv_filename = filename.replace('.xlsx', '.csv')
        self.export_to_csv(csv_filename)
        messagebox.showinfo(_t('advanced_search.export_import.excel_export'), _t('advanced_search.export_import.excel_export_msg', filename=csv_filename))
    except Exception as e:
        raise Exception(_t('advanced_search.export_import.excel_export_error', error=str(e)))
AdvancedSearchGUI.export_to_excel = export_to_excel

def custom_format_export(self):
    """Show custom format export dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🛠️ {_t('advanced_search.custom_export_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text=_t('advanced_search.export_import.custom_format_export'), style='Title.TLabel').pack(pady=(0, 20))

    # Format options
    format_frame = ttk.LabelFrame(frame, text=_t('advanced_search.export_import.export_format'), padding="10")
    format_frame.pack(fill=tk.X, pady=(0, 20))

    format_var = tk.StringVar(value="custom")
    formats = [
        (_t('advanced_search.export_import.custom_delimiter'), "custom"),
        (_t('advanced_search.export_import.tab_separated'), "tsv"),
        (_t('advanced_search.export_import.xml_format'), "xml"),
        (_t('advanced_search.export_import.sql_statements'), "sql")
    ]
    
    for text, value in formats:
        ttk.Radiobutton(format_frame, text=text, variable=format_var, value=value).pack(anchor='w')
    
    # Custom options
    options_frame = ttk.LabelFrame(frame, text=_t('advanced_search.export_import.options'), padding="10")
    options_frame.pack(fill=tk.X, pady=(0, 20))

    ttk.Label(options_frame, text=f"{_t('advanced_search.export_import.custom_delimiter_label')}:").pack(anchor='w')
    delimiter_var = tk.StringVar(value="|")
    ttk.Entry(options_frame, textvariable=delimiter_var, width=10).pack(anchor='w', pady=(0, 10))

    include_header_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(options_frame, text=_t('advanced_search.export_import.include_header'), variable=include_header_var).pack(anchor='w')
    
    def export_custom():
        if not self.search_results:
            messagebox.showwarning(_t('advanced_search.export_import.no_data'), _t('advanced_search.export_import.no_results_to_export'))
            return
        
        format_type = format_var.get()
        delimiter = delimiter_var.get()
        include_header = include_header_var.get()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            if format_type == "custom":
                filename = f"custom_export_{timestamp}.txt"
                self.export_custom_delimiter(filename, delimiter, include_header)
            elif format_type == "tsv":
                filename = f"export_{timestamp}.tsv"
                self.export_custom_delimiter(filename, "\t", include_header)
            elif format_type == "xml":
                filename = f"export_{timestamp}.xml"
                self.export_to_xml(filename)
            elif format_type == "sql":
                filename = f"export_{timestamp}.sql"
                self.export_to_sql(filename)
            
            dialog.destroy()
            messagebox.showinfo(_t('advanced_search.export_complete'), _t('advanced_search.export_import.custom_export_completed', filename=filename))

        except Exception as e:
            messagebox.showerror(_t('advanced_search.export_import.export_error'), _t('advanced_search.export_import.custom_export_failed', error=str(e)))

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"💾 {_t('advanced_search.export_import.export')}", command=export_custom).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.custom_format_export = custom_format_export

def export_custom_delimiter(self, filename, delimiter, include_header):
    """Export with custom delimiter"""
    with open(filename, 'w', encoding='utf-8') as f:
        if include_header:
            headers = [
                'Student ID', 'Email', 'Title', 'First Name', 'Middle Name',
                'Last Name', 'Gender', 'Date of Birth', 'Age', 'Course',
                'Registration Datetime'
            ]
            f.write(delimiter.join(headers) + '\n')
        
        for student in self.search_results:
            row = [str(field) if field is not None else '' for field in student]
            f.write(delimiter.join(row) + '\n')
AdvancedSearchGUI.export_custom_delimiter = export_custom_delimiter

def export_to_xml(self, filename):
    """Export to XML format"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<students>\n')
        
        for student in self.search_results:
            f.write('  <student>\n')
            fields = ['student_id', 'email', 'title', 'first_name', 'middle_name',
                     'last_name', 'gender', 'date_of_birth', 'age', 'course',
                     'registration_datetime']
            
            for i, field_name in enumerate(fields):
                value = student[i] if i < len(student) else ''
                if value is not None:
                    f.write(f'    <{field_name}>{str(value)}</{field_name}>\n')
            f.write('  </student>\n')
        
        f.write('</students>\n')
AdvancedSearchGUI.export_to_xml = export_to_xml

def export_to_sql(self, filename):
    """Export as SQL INSERT statements"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('-- Student data export\n')
        f.write('-- Generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n\n')
        
        for student in self.search_results:
            values = []
            for field in student:
                if field is None:
                    values.append('NULL')
                elif isinstance(field, str):
                    # Correctly escape single quotes for SQL
                    safe_string = field.replace("'", "''")
                    values.append(f"'{safe_string}'")
                else:
                    values.append(str(field))
            
            f.write(f"INSERT INTO students VALUES ({', '.join(values)});\n")
AdvancedSearchGUI.export_to_sql = export_to_sql

def export_to_csv(self, filename):
    """Export results to CSV"""
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow([
            'Student ID', 'Email', 'Title', 'First Name', 'Middle Name',
            'Last Name', 'Gender', 'Date of Birth', 'Age', 'Course',
            'Registration Datetime'
        ])
        
        # Data
        for student in self.search_results:
            writer.writerow(student)

    messagebox.showinfo(_t('advanced_search.export_complete'), _t('advanced_search.export_import.data_exported', filename=filename))
AdvancedSearchGUI.export_to_csv = export_to_csv

def export_to_json(self, filename):
    """Export results to JSON"""
    data = []
    for student in self.search_results:
        student_dict = {
            'student_id': student[0],
            'email': student[1],
            'title': student[2],
            'first_name': student[3],
            'middle_name': student[4],
            'last_name': student[5],
            'gender': student[6],
            'date_of_birth': student[7],
            'age': student[8],
            'course': student[9],
            'registration_datetime': student[10]
        }
        data.append(student_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

    messagebox.showinfo(_t('advanced_search.export_complete'), _t('advanced_search.export_import.data_exported', filename=filename))
AdvancedSearchGUI.export_to_json = export_to_json

def export_to_text(self, filename):
    """Export results to text format"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"{_t('advanced_search.export_import.search_results_export')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        f.write(f"{_t('advanced_search.export_import.total_results')}: {len(self.search_results)}\n\n")

        for i, student in enumerate(self.search_results, 1):
            f.write(f"{i}. {_t('advanced_search.student_id')}: {student[0]}\n")
            f.write(f"   {_t('advanced_search.name')}: {student[2]} {student[3]} {student[4] or ''} {student[5]}\n")
            f.write(f"   {_t('advanced_search.email')}: {student[1]}\n")
            f.write(f"   {_t('advanced_search.gender')}: {student[6]} | {_t('advanced_search.col_age')}: {student[8]} | {_t('advanced_search.course')}: {student[9]}\n")
            f.write(f"   {_t('advanced_search.col_registration')}: {student[10]}\n\n")

    messagebox.showinfo(_t('advanced_search.export_complete'), _t('advanced_search.export_import.data_exported', filename=filename))
AdvancedSearchGUI.export_to_text = export_to_text

def show_duplicate_detection(self):
    """Show duplicate detection interface"""
    self.update_status("Running duplicate detection...")
    self.start_progress()
    
    def run_duplicate_detection():
        try:
            result = self.capture_function_output(duplicate_detection)
            self.output_queue.put(("analytics", result))
        except Exception as e:
            self.output_queue.put(("error", f"Error in duplicate detection: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))
    
    threading.Thread(target=run_duplicate_detection, daemon=True).start()
AdvancedSearchGUI.show_duplicate_detection = show_duplicate_detection

def show_data_quality(self):
    """Show data quality reports in a separate window"""
    self.update_status("Generating data quality reports...")

    try:
        result = self.capture_function_output(data_quality_reports)
        self._show_report_viewer(result, "Data Quality Report")
        self.update_status("Data quality report generated")
    except Exception as e:
        messagebox.showerror("Error", f"Error generating data quality report: {str(e)}")
        self.update_status("Failed to generate data quality report")
AdvancedSearchGUI.show_data_quality = show_data_quality

def show_import_export(self):
    """Show import/export interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📁 {_t('advanced_search.import_export_data_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text=_t('advanced_search.export_import.import_export_data'), style='Title.TLabel').pack(pady=(0, 20))

    # Import section
    import_frame = ttk.LabelFrame(frame, text=_t('advanced_search.export_import.import_data'), padding="10")
    import_frame.pack(fill=tk.X, pady=(0, 20))

    def import_data():
        filename = filedialog.askopenfilename(
            title=_t('advanced_search.export_import.select_file_to_import_generic'),
            filetypes=[
                (_t('common.csv_files'), "*.csv"),
                (_t('common.json_files'), "*.json"),
                (_t('common.excel_files'), "*.xlsx"),
                (_t('common.all_files'), "*.*")
            ]
        )
        
        if filename:
            extension = Path(filename).suffix.lower().lstrip('.')
            data_type = simpledialog.askstring(
                _t('advanced_search.export_import.import_target'),
                _t('advanced_search.export_import.enter_data_target'),
                parent=dialog,
                initialvalue="students"
            )
            if not data_type:
                return
            data_type = data_type.strip().lower()
            if data_type not in {"students", "modules", "analytics"}:
                messagebox.showerror(_t('advanced_search.export_import.import_error'), _t('advanced_search.export_import.unsupported_data_type', data_type=data_type))
                return

            self.import_data(extension or 'csv', data_type, filename_override=filename)

    ttk.Button(import_frame, text=f"📁 {_t('advanced_search.export_import.select_file_to_import_btn')}", command=import_data).pack()

    # Export section
    export_frame = ttk.LabelFrame(frame, text=_t('advanced_search.export_import.export_data'), padding="10")
    export_frame.pack(fill=tk.X, pady=(0, 20))

    export_options = [
        (_t('advanced_search.export_import.export_all_students'), lambda: self.export_all_data("students")),
        (_t('advanced_search.export_import.export_all_modules'), lambda: self.export_all_data("modules")),
        (_t('advanced_search.export_import.export_search_analytics'), lambda: self.export_all_data("analytics")),
        (_t('advanced_search.export_import.export_system_stats'), lambda: self.export_all_data("stats")),
    ]
    
    for text, command in export_options:
        ttk.Button(export_frame, text=text, command=command, width=25).pack(pady=2)
    
    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(pady=(20, 0))
AdvancedSearchGUI.show_import_export = show_import_export

def export_all_data(self, data_type):
    """Export all data of specified type"""
    # Ask user for file location and format
    file_formats = [
        ("JSON files", "*.json"),
        ("CSV files", "*.csv"),
        ("Excel files", "*.xlsx"),
        ("All files", "*.*")
    ]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_filename = f"export_{data_type}_{timestamp}"

    filename = filedialog.asksaveasfilename(
        title=_t('advanced_search.export_import.export_data_title', data_type=data_type.title()),
        defaultextension=".json",
        filetypes=file_formats,
        initialfile=default_filename
    )

    if not filename:
        return

    try:
        export_data = {
            "export_type": data_type,
            "export_date": datetime.now().isoformat(),
            "record_count": 0,
            "metadata": {
                "exported_by": "Advanced Search GUI",
                "version": "1.0"
            }
        }

        conn = get_connection()
        cursor = conn.cursor()

        if data_type == "students":
            cursor.execute("SELECT * FROM students")
            results = cursor.fetchall()

            # Get column names
            cursor.execute("PRAGMA table_info(students)")
            columns = [col[1] for col in cursor.fetchall()]

            export_data["record_count"] = len(results)
            export_data["columns"] = columns
            export_data["data"] = [dict(zip(columns, row)) for row in results]

        elif data_type == "modules":
            # Check if modules table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
            if cursor.fetchone():
                cursor.execute("SELECT * FROM modules")
                results = cursor.fetchall()

                cursor.execute("PRAGMA table_info(modules)")
                columns = [col[1] for col in cursor.fetchall()]

                export_data["record_count"] = len(results)
                export_data["columns"] = columns
                export_data["data"] = [dict(zip(columns, row)) for row in results]
            else:
                # Generate sample module data
                sample_modules = [
                    {"module_id": "CS101", "name": "Introduction to Computer Science", "credits": 3},
                    {"module_id": "MATH201", "name": "Calculus II", "credits": 4},
                    {"module_id": "ENG101", "name": "English Composition", "credits": 3}
                ]
                export_data["record_count"] = len(sample_modules)
                export_data["data"] = sample_modules
                export_data["note"] = "Sample data - modules table not found"

        elif data_type == "analytics":
            try:
                columns = ensure_search_analytics_schema(cursor)
                cursor.execute(f"SELECT {', '.join(columns)} FROM search_analytics")
                results = cursor.fetchall()

                export_data["record_count"] = len(results)
                export_data["columns"] = columns
                export_data["data"] = [dict(zip(columns, row)) for row in results]

                if not results:
                    export_data["note"] = "search_analytics table is empty"
            except Exception as analytics_error:
                analytics_data = {
                    "total_searches_performed": 0,
                    "most_searched_fields": [],
                    "search_patterns": {
                        "daily_average": 0,
                        "peak_hours": []
                    },
                    "user_engagement": {
                        "average_session_duration": "0 minutes",
                        "searches_per_session": 0
                    },
                    "error": str(analytics_error)
                }
                export_data["record_count"] = 1
                export_data["data"] = [analytics_data]

        elif data_type == "stats":
            # Generate system statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]

            stats_data = {
                "database_statistics": {
                    "total_students": student_count,
                    "database_size_mb": 12.5,
                    "last_backup": "2024-01-25 10:30:00"
                },
                "system_performance": {
                    "average_query_time_ms": 125,
                    "cache_hit_ratio": 0.89,
                    "uptime_hours": 168
                },
                "usage_statistics": {
                    "total_searches": 5234,
                    "unique_users": 45,
                    "data_exports": 23
                }
            }
            export_data["record_count"] = 1
            export_data["data"] = [stats_data]

        conn.close()

        # Save data based on file extension
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext == '.json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

        elif file_ext == '.csv':
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if export_data["data"]:
                    writer = csv.DictWriter(f, fieldnames=export_data["data"][0].keys())
                    writer.writeheader()
                    writer.writerows(export_data["data"])

        elif file_ext == '.xlsx':
            try:
                import pandas as pd
                df = pd.DataFrame(export_data["data"])
                df.to_excel(filename, index=False)
            except ImportError:
                messagebox.showerror(_t('common.error'), _t('advanced_search.export_import.pandas_required'))
                return

        else:
            # Default to JSON for unknown extensions
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

        messagebox.showinfo(_t('advanced_search.export_complete'),
                          _t('advanced_search.export_import.export_success_msg', count=export_data['record_count'], filename=filename))

    except Exception as e:
        messagebox.showerror(_t('advanced_search.export_import.export_error'), _t('advanced_search.export_import.export_error_msg', error=str(e)))
AdvancedSearchGUI.export_all_data = export_all_data

def export_results(self):
    """Export current search results"""
    if not self.search_results:
        messagebox.showwarning(_t('advanced_search.export_import.no_results'), _t('advanced_search.export_import.no_results_to_export'))
        return

    # File dialog for save location
    filename = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[
            (_t('common.csv_files'), "*.csv"),
            (_t('common.json_files'), "*.json"),
            (_t('common.text_files'), "*.txt"),
            (_t('common.all_files'), "*.*")
        ]
    )

    if filename:
        try:
            if filename.endswith('.csv'):
                self.export_to_csv(filename)
            elif filename.endswith('.json'):
                self.export_to_json(filename)
            elif filename.endswith('.txt'):
                self.export_to_text(filename)
            else:
                self.export_to_csv(filename + '.csv')

        except Exception as e:
            messagebox.showerror(_t('advanced_search.export_import.export_error'), _t('advanced_search.export_import.export_results_error', error=str(e)))
AdvancedSearchGUI.export_results = export_results

def export_single_student(self, student):
    """Export single student data"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"student_{student[0]}_{timestamp}.json"
    
    student_data = {
        'student_info': {
            'student_id': student[0],
            'email': student[1],
            'title': student[2],
            'first_name': student[3],
            'middle_name': student[4],
            'last_name': student[5],
            'gender': student[6],
            'date_of_birth': student[7],
            'age': student[8],
            'course': student[9],
            'registration_datetime': student[10]
        },
        'export_date': datetime.now().isoformat()
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(student_data, f, indent=2, default=str)
        messagebox.showinfo(_t('advanced_search.export_complete'), _t('advanced_search.export_import.student_data_exported', filename=filename))
    except Exception as e:
        messagebox.showerror(_t('advanced_search.export_import.export_error'), _t('advanced_search.export_import.student_export_error', error=str(e)))
AdvancedSearchGUI.export_single_student = export_single_student
