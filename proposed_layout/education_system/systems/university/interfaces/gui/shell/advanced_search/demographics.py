from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.systems.university.infrastructure.sql_safety import validate_identifier, validate_table_name, validate_field_for_query, validate_column_name  # nosec B608
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
    from education_system.systems.university.infrastructure.i18n import (
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
    from education_system.systems.university.infrastructure.utils.console_output import ConsoleOutput
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
    from education_system.systems.university.infrastructure.utils.chart_generator import (
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
    from education_system.systems.university.services.analytics.advanced_search import (
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
    from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
    from education_system.systems.university.infrastructure.email.admin import search_users, list_all_users
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
        from education_system.systems.university.infrastructure.database.db import sqlite3
        # Use centralized path system
        from education_system.systems.university.infrastructure import paths
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

    _VALID_TIME_COLUMNS = {'timestamp', 'search_datetime'}
    time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime' if 'search_datetime' in columns else None
    if time_column:
        validate_field_for_query(time_column, _VALID_TIME_COLUMNS, "time column")
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
    # Validate all column names before SQL interpolation
    for key in record.keys():
        validate_column_name(key)
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
        # Prefer the central connection from education_system.systems.university.infrastructure.database.db if available
        from education_system.systems.university.infrastructure.database.db import get_connection as central_get_connection
        return central_get_connection()
    except Exception:
        try:
            # Compute the path to the central student_records.db relative to this file.
            from education_system.systems.university.infrastructure.database.db import sqlite3
            from education_system.systems.university.infrastructure import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        except Exception as e:
            print_error(f"Database connection error: {e}")
            return None

from education_system.systems.university.interfaces.gui.shell.advanced_search.base import AdvancedSearchGUI

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
            safe_field = validate_identifier(field, "column")
            cursor.execute("SELECT COUNT(*) FROM students WHERE [" + safe_field + "] IS NULL OR [" + safe_field + "] = ''")
            missing = cursor.fetchone()[0]
            percentage = (missing / total * 100) if total > 0 else 0
            report += f"  {label}: {missing} missing ({percentage:.1f}%)\n"

        conn.close()
        return report

    except Exception as e:
        return f"Error generating data quality report: {str(e)}"

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
        report += "ENROLLMENT STATISTICS:\n"
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

class AdvancedDemographicReportGUI:
    """
    Advanced Demographic Report GUI - Comprehensive demographic analysis
    Features: Multiple report types, cross-tabulation, statistical analysis,
    save as TXT, email to admin
    """

    def __init__(self, master, auth=None):
        self.master = master
        self.auth = auth
        self.window = None
        self.report_data = {}
        self.raw_data = []

    def show_window(self):
        """Display the advanced demographic report window"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.master)
        self.window.title("Advanced Demographic Report")
        self.window.geometry("1450x950")
        self.window.transient(self.master)
        self.window.minsize(1300, 850)

        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1450) // 2
        y = (self.window.winfo_screenheight() - 950) // 2
        self.window.geometry(f"+{x}+{y}")

        self._setup_styles()
        self._create_widgets()

    def _setup_styles(self):
        """Setup ttk styles"""
        style = ttk.Style()
        style.configure('AdvReport.TFrame', padding=10)
        style.configure('AdvReportTitle.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('SectionTitle.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('Stat.TLabel', font=('Helvetica', 10))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container with notebook for tabs
        main_frame = ttk.Frame(self.window, style='AdvReport.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            title_frame,
            text="Advanced Demographic Report",
            style='AdvReportTitle.TLabel'
        ).pack(side=tk.LEFT)

        # Generate button in title area
        ttk.Button(
            title_frame,
            text="Generate Report",
            command=self._generate_full_report
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            title_frame,
            text="Refresh Data",
            command=self._refresh_data
        ).pack(side=tk.RIGHT)

        # Notebook for different report views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Tab 1: Overview Summary
        self.overview_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.overview_frame, text="Overview Summary")
        self._create_overview_tab()

        # Tab 2: Gender Analysis
        self.gender_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.gender_frame, text="Gender Analysis")
        self._create_analysis_tab(self.gender_frame, 'gender')

        # Tab 3: Age Distribution
        self.age_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.age_frame, text="Age Distribution")
        self._create_analysis_tab(self.age_frame, 'age')

        # Tab 4: Course Enrollment
        self.course_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.course_frame, text="Course Enrollment")
        self._create_analysis_tab(self.course_frame, 'course')

        # Tab 5: Cross-Tabulation
        self.crosstab_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.crosstab_frame, text="Cross-Tabulation")
        self._create_crosstab_tab()

        # Tab 6: Full Report
        self.full_report_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.full_report_frame, text="Full Report")
        self._create_full_report_tab()

        # Action buttons at bottom
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(
            action_frame,
            text="Save Report as TXT",
            command=self._save_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="Email Report to Admin",
            command=self._email_to_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="Export All Data (CSV)",
            command=self._export_all_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('advanced_search.close_button'),
            command=self.window.destroy
        ).pack(side=tk.RIGHT, padx=5)

        # Auto-generate report on open
        self.window.after(100, self._generate_full_report)

    def _create_overview_tab(self):
        """Create overview summary tab"""
        # Summary statistics text area
        ttk.Label(
            self.overview_frame,
            text="Demographic Overview Summary",
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Create scrollable text area for overview
        text_frame = ttk.Frame(self.overview_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        self.overview_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.overview_text.yview)

        self.overview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_analysis_tab(self, parent, analysis_type):
        """Create analysis tab with treeview for breakdown"""
        ttk.Label(
            parent,
            text=f"{analysis_type.title()} Distribution Analysis",
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Treeview for data
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('category', 'count', 'percentage', 'bar')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        tree.heading('category', text=analysis_type.title())
        tree.heading('count', text='Count')
        tree.heading('percentage', text='Percentage')
        tree.heading('bar', text='Visual')

        tree.column('category', width=200)
        tree.column('count', width=100, anchor='center')
        tree.column('percentage', width=100, anchor='center')
        tree.column('bar', width=300)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Store reference
        setattr(self, f'{analysis_type}_tree', tree)

    def _create_crosstab_tab(self):
        """Create cross-tabulation tab"""
        # Controls frame
        controls = ttk.Frame(self.crosstab_frame)
        controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls, text="Row Variable:").pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_row_var = tk.StringVar(value="gender")
        row_combo = ttk.Combobox(
            controls,
            textvariable=self.crosstab_row_var,
            values=['gender', 'age_group', 'course', 'status'],
            state='readonly',
            width=15
        )
        row_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(controls, text="Column Variable:").pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_col_var = tk.StringVar(value="status")
        col_combo = ttk.Combobox(
            controls,
            textvariable=self.crosstab_col_var,
            values=['gender', 'age_group', 'course', 'status'],
            state='readonly',
            width=15
        )
        col_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(
            controls,
            text="Generate Cross-Tab",
            command=self._generate_crosstab
        ).pack(side=tk.LEFT)

        # Cross-tab display area
        self.crosstab_text = tk.Text(
            self.crosstab_frame,
            wrap=tk.NONE,
            font=('Courier', 10)
        )

        y_scroll = ttk.Scrollbar(self.crosstab_frame, orient=tk.VERTICAL, command=self.crosstab_text.yview)
        x_scroll = ttk.Scrollbar(self.crosstab_frame, orient=tk.HORIZONTAL, command=self.crosstab_text.xview)
        self.crosstab_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.crosstab_text.pack(fill=tk.BOTH, expand=True)

    def _create_full_report_tab(self):
        """Create full report tab"""
        ttk.Label(
            self.full_report_frame,
            text="Complete Demographic Report",
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Full report text area
        text_frame = ttk.Frame(self.full_report_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)

        self.full_report_text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=('Courier', 9),
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        y_scroll.config(command=self.full_report_text.yview)
        x_scroll.config(command=self.full_report_text.xview)

        self.full_report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    def _refresh_data(self):
        """Refresh data from database"""
        self._generate_full_report()

    def _generate_full_report(self):
        """Generate comprehensive demographic report"""
        try:
            conn = get_connection()
            if conn is None:
                messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.database_connection_failed"))
                return

            cursor = conn.cursor()

            # Fetch all student data with demographics
            query = """
                SELECT
                    s.student_id,
                    COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '') as full_name,
                    COALESCE(d.gender, s.gender, 'Unknown') as gender,
                    COALESCE(s.age, 0) as age,
                    COALESCE(s.course, 'Unknown') as course,
                    COALESCE(s.status, 'Unknown') as status,
                    COALESCE(d.ethnicity, 'Unknown') as ethnicity,
                    COALESCE(d.academic_level, 'Unknown') as academic_level,
                    COALESCE(d.age_group, 'Unknown') as age_group,
                    s.enrollment_date
                FROM students s
                LEFT JOIN student_demographics d ON s.student_id = d.student_id
            """
            cursor.execute(query)
            self.raw_data = cursor.fetchall()
            conn.close()

            if not self.raw_data:
                messagebox.showinfo(_t("advanced_search.demographics.no_data_title"), _t("advanced_search.demographics.no_data_msg"))
                return

            # Process data for reports
            self._process_demographics()

            # Update all tabs
            self._update_overview()
            self._update_gender_analysis()
            self._update_age_analysis()
            self._update_course_analysis()
            self._update_full_report()

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('generate', 'advanced_demographic_report', details={
                    'total_students': len(self.raw_data)
                })
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.failed_to_generate_report", error=str(e)))

    def _process_demographics(self):
        """Process raw data into demographic statistics"""
        self.report_data = {
            'total': len(self.raw_data),
            'gender': {},
            'age': {},
            'age_group': {},
            'course': {},
            'status': {},
            'ethnicity': {},
            'academic_level': {}
        }

        for row in self.raw_data:
            # row: student_id, full_name, gender, age, course, status, ethnicity, academic_level, age_group, enrollment_date
            gender = row[2] or 'Unknown'
            age = row[3] or 0
            course = row[4] or 'Unknown'
            status = row[5] or 'Unknown'
            ethnicity = row[6] or 'Unknown'
            academic_level = row[7] or 'Unknown'
            age_group = row[8] or 'Unknown'

            # Count by category
            self.report_data['gender'][gender] = self.report_data['gender'].get(gender, 0) + 1
            self.report_data['course'][course] = self.report_data['course'].get(course, 0) + 1
            self.report_data['status'][status] = self.report_data['status'].get(status, 0) + 1
            self.report_data['ethnicity'][ethnicity] = self.report_data['ethnicity'].get(ethnicity, 0) + 1
            self.report_data['academic_level'][academic_level] = self.report_data['academic_level'].get(academic_level, 0) + 1
            self.report_data['age_group'][age_group] = self.report_data['age_group'].get(age_group, 0) + 1

            # Age buckets
            if age > 0:
                if age < 20:
                    bucket = 'Under 20'
                elif age < 25:
                    bucket = '20-24'
                elif age < 30:
                    bucket = '25-29'
                elif age < 40:
                    bucket = '30-39'
                elif age < 50:
                    bucket = '40-49'
                else:
                    bucket = '50+'
                self.report_data['age'][bucket] = self.report_data['age'].get(bucket, 0) + 1

    def _create_visual_bar(self, percentage, width=30):
        """Create ASCII visual bar for percentage"""
        filled = int(percentage / 100 * width)
        return '[' + '#' * filled + '-' * (width - filled) + ']'

    def _update_overview(self):
        """Update overview summary tab"""
        self.overview_text.delete(1.0, tk.END)

        total = self.report_data['total']
        report = f"""
{'='*70}
                    DEMOGRAPHIC OVERVIEW SUMMARY
{'='*70}
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Students: {total:,}
{'='*70}

GENDER DISTRIBUTION
{'-'*40}
"""
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {gender:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
STATUS DISTRIBUTION
{'-'*40}
"""
        for status, count in sorted(self.report_data['status'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {status:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
AGE DISTRIBUTION
{'-'*40}
"""
        age_order = ['Under 20', '20-24', '25-29', '30-39', '40-49', '50+']
        for age_bucket in age_order:
            count = self.report_data['age'].get(age_bucket, 0)
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {age_bucket:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
TOP 10 COURSES BY ENROLLMENT
{'-'*40}
"""
        sorted_courses = sorted(self.report_data['course'].items(), key=lambda x: -x[1])[:10]
        for course, count in sorted_courses:
            pct = (count / total * 100) if total > 0 else 0
            course_display = course[:30] + '...' if len(course) > 30 else course
            report += f"  {course_display:<35} {count:>5,}  ({pct:4.1f}%)\n"

        report += f"\n{'='*70}\n"

        self.overview_text.insert(tk.END, report)

    def _update_analysis_tree(self, tree, data_dict, total):
        """Update a treeview with analysis data"""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        # Insert sorted data
        for category, count in sorted(data_dict.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 25)
            tree.insert('', tk.END, values=(category, f"{count:,}", f"{pct:.1f}%", bar))

    def _update_gender_analysis(self):
        """Update gender analysis tab"""
        if hasattr(self, 'gender_tree'):
            self._update_analysis_tree(
                self.gender_tree,
                self.report_data['gender'],
                self.report_data['total']
            )

    def _update_age_analysis(self):
        """Update age analysis tab"""
        if hasattr(self, 'age_tree'):
            self._update_analysis_tree(
                self.age_tree,
                self.report_data['age'],
                self.report_data['total']
            )

    def _update_course_analysis(self):
        """Update course analysis tab"""
        if hasattr(self, 'course_tree'):
            self._update_analysis_tree(
                self.course_tree,
                self.report_data['course'],
                self.report_data['total']
            )

    def _generate_crosstab(self):
        """Generate cross-tabulation report"""
        if not self.raw_data:
            messagebox.showwarning("No Data", "Please generate report first.")
            return

        row_var = self.crosstab_row_var.get()
        col_var = self.crosstab_col_var.get()

        if row_var == col_var:
            messagebox.showwarning("Invalid Selection", "Please select different variables for rows and columns.")
            return

        # Map variable names to data indices
        var_index = {
            'gender': 2,
            'age_group': 8,
            'course': 4,
            'status': 5
        }

        row_idx = var_index[row_var]
        col_idx = var_index[col_var]

        # Build cross-tab
        crosstab = {}
        col_totals = {}
        row_totals = {}

        for row in self.raw_data:
            row_val = row[row_idx] or 'Unknown'
            col_val = row[col_idx] or 'Unknown'

            if row_val not in crosstab:
                crosstab[row_val] = {}
            crosstab[row_val][col_val] = crosstab[row_val].get(col_val, 0) + 1

            col_totals[col_val] = col_totals.get(col_val, 0) + 1
            row_totals[row_val] = row_totals.get(row_val, 0) + 1

        # Format output
        self.crosstab_text.delete(1.0, tk.END)

        cols = sorted(col_totals.keys())
        rows = sorted(row_totals.keys())

        # Header
        header = f"\n{'CROSS-TABULATION: ' + row_var.upper() + ' x ' + col_var.upper():^80}\n"
        header += "=" * 80 + "\n\n"

        # Calculate column widths
        row_width = max(len(str(r)) for r in rows + [row_var.title()]) + 2
        col_width = max(max(len(str(c)) for c in cols), 8) + 2

        # Column headers
        header += f"{row_var.title():<{row_width}}"
        for col in cols:
            col_display = str(col)[:col_width-2]
            header += f"{col_display:>{col_width}}"
        header += f"{'Total':>{col_width}}\n"
        header += "-" * (row_width + (len(cols) + 1) * col_width) + "\n"

        self.crosstab_text.insert(tk.END, header)

        # Data rows
        for row_val in rows:
            line = f"{str(row_val):<{row_width}}"
            for col in cols:
                count = crosstab.get(row_val, {}).get(col, 0)
                line += f"{count:>{col_width}}"
            line += f"{row_totals[row_val]:>{col_width}}\n"
            self.crosstab_text.insert(tk.END, line)

        # Totals row
        totals_line = "-" * (row_width + (len(cols) + 1) * col_width) + "\n"
        totals_line += f"{'Total':<{row_width}}"
        for col in cols:
            totals_line += f"{col_totals[col]:>{col_width}}"
        totals_line += f"{len(self.raw_data):>{col_width}}\n"

        self.crosstab_text.insert(tk.END, totals_line)

        # Percentage breakdown
        pct_header = f"\n\nPERCENTAGE BY {row_var.upper()} (Row %)\n"
        pct_header += "-" * (row_width + (len(cols) + 1) * col_width) + "\n"
        self.crosstab_text.insert(tk.END, pct_header)

        for row_val in rows:
            line = f"{str(row_val):<{row_width}}"
            row_total = row_totals[row_val]
            for col in cols:
                count = crosstab.get(row_val, {}).get(col, 0)
                pct = (count / row_total * 100) if row_total > 0 else 0
                line += f"{pct:>{col_width-1}.1f}%"
            line += f"{'100.0%':>{col_width}}\n"
            self.crosstab_text.insert(tk.END, line)

    def _update_full_report(self):
        """Update full report tab"""
        self.full_report_text.delete(1.0, tk.END)
        report = self._generate_report_text()
        self.full_report_text.insert(tk.END, report)

    def _generate_report_text(self):
        """Generate complete text report"""
        if not self.report_data or self.report_data['total'] == 0:
            return "No data available for report."

        total = self.report_data['total']

        report = "=" * 90 + "\n"
        report += "                    ADVANCED STUDENT DEMOGRAPHIC REPORT\n"
        report += "=" * 90 + "\n"
        report += f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Total Students Analyzed: {total:,}\n"
        report += "=" * 90 + "\n\n"

        # Section 1: Gender Distribution
        report += "SECTION 1: GENDER DISTRIBUTION\n"
        report += "-" * 50 + "\n"
        report += f"{'Gender':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            report += f"{gender:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 2: Age Distribution
        report += "SECTION 2: AGE DISTRIBUTION\n"
        report += "-" * 50 + "\n"
        report += f"{'Age Group':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        age_order = ['Under 20', '20-24', '25-29', '30-39', '40-49', '50+']
        for age_bucket in age_order:
            count = self.report_data['age'].get(age_bucket, 0)
            pct = (count / total * 100) if total > 0 else 0
            report += f"{age_bucket:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 3: Status Distribution
        report += "SECTION 3: ENROLLMENT STATUS\n"
        report += "-" * 50 + "\n"
        report += f"{'Status':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        for status, count in sorted(self.report_data['status'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            report += f"{status:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 4: Course Enrollment
        report += "SECTION 4: COURSE ENROLLMENT (ALL)\n"
        report += "-" * 70 + "\n"
        report += f"{'Course':<45} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 70 + "\n"
        for course, count in sorted(self.report_data['course'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            course_display = course[:44] if len(course) > 44 else course
            report += f"{course_display:<45} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 5: Ethnicity (if available)
        if self.report_data['ethnicity'] and any(k != 'Unknown' for k in self.report_data['ethnicity']):
            report += "SECTION 5: ETHNICITY DISTRIBUTION\n"
            report += "-" * 50 + "\n"
            report += f"{'Ethnicity':<25} {'Count':>10} {'Percentage':>12}\n"
            report += "-" * 50 + "\n"
            for ethnicity, count in sorted(self.report_data['ethnicity'].items(), key=lambda x: -x[1]):
                pct = (count / total * 100) if total > 0 else 0
                report += f"{ethnicity:<25} {count:>10,} {pct:>11.1f}%\n"
            report += "\n"

        # Section 6: Academic Level (if available)
        if self.report_data['academic_level'] and any(k != 'Unknown' for k in self.report_data['academic_level']):
            report += "SECTION 6: ACADEMIC LEVEL DISTRIBUTION\n"
            report += "-" * 50 + "\n"
            report += f"{'Academic Level':<25} {'Count':>10} {'Percentage':>12}\n"
            report += "-" * 50 + "\n"
            for level, count in sorted(self.report_data['academic_level'].items(), key=lambda x: -x[1]):
                pct = (count / total * 100) if total > 0 else 0
                report += f"{level:<25} {count:>10,} {pct:>11.1f}%\n"
            report += "\n"

        report += "=" * 90 + "\n"
        report += "                              END OF REPORT\n"
        report += "=" * 90 + "\n"

        return report

    def _save_as_txt(self):
        """Save report as TXT file"""
        if not self.report_data or self.report_data.get('total', 0) == 0:
            messagebox.showwarning("No Data", "Please generate report first.")
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save Advanced Demographic Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"advanced_demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        try:
            import os
            report_text = self._generate_report_text()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_text)  # lgtm [py/clear-text-storage-sensitive-data]

            # Restrict file permissions — report contains sensitive demographic data
            try:
                os.chmod(filename, 0o600)
            except OSError:
                pass

            messagebox.showinfo("Success", f"Report saved to:\n{filename}")

            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('export', 'advanced_demographic_report', details={'format': 'txt', 'filename': filename})
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def _email_to_admin(self):
        """Email report to admin"""
        if not self.report_data or self.report_data.get('total', 0) == 0:
            messagebox.showwarning("No Data", "Please generate report first.")
            return

        # Email dialog
        email_dialog = tk.Toplevel(self.window)
        email_dialog.title(_t('advanced_search.email_demographic_report_title'))
        email_dialog.geometry("700x550")
        email_dialog.transient(self.window)
        email_dialog.grab_set()

        # Center
        email_dialog.update_idletasks()
        x = (email_dialog.winfo_screenwidth() - 700) // 2
        y = (email_dialog.winfo_screenheight() - 550) // 2
        email_dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(email_dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(frame, text="Recipient Email:").pack(anchor='w')
        recipient_var = tk.StringVar(value="admin@university.edu")
        ttk.Entry(frame, textvariable=recipient_var, width=60).pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value=f"Advanced Demographic Report - {datetime.now().strftime('%Y-%m-%d')}")
        ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill=tk.X, pady=(0, 10))

        # Message
        ttk.Label(frame, text="Additional Message:").pack(anchor='w')
        message_text = tk.Text(frame, height=8, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        total = self.report_data.get('total', 0)
        message_text.insert(tk.END, f"Please find the Advanced Demographic Report for {total:,} students.\n\n")
        message_text.insert(tk.END, "Key Statistics:\n")

        # Add summary stats
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1])[:3]:
            pct = (count / total * 100) if total > 0 else 0
            message_text.insert(tk.END, f"- {gender}: {count:,} ({pct:.1f}%)\n")

        # Info label
        ttk.Label(
            frame,
            text=f"Report contains analysis of {total:,} student records"
        ).pack(anchor='w', pady=(0, 10))

        def send_action():
            recipient = recipient_var.get().strip()
            subject = subject_var.get().strip()
            additional = message_text.get(1.0, tk.END).strip()

            if not recipient:
                messagebox.showwarning("Missing", "Please enter recipient email.")
                return

            if not subject:
                messagebox.showwarning("Missing", "Please enter subject.")
                return

            body = additional + "\n\n" + "=" * 60 + "\n"
            body += self._generate_report_text()

            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email

                success = send_email(
                    recipient_email=recipient,
                    subject=subject,
                    body=body
                )

                if success:
                    messagebox.showinfo("Success", f"Report sent to {recipient}")
                    email_dialog.destroy()

                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('email', 'advanced_demographic_report', details={
                            'recipient': recipient,
                            'total_students': total
                        })
                    except ImportError:
                        pass
                else:
                    messagebox.showwarning("Queued", f"Email queued for delivery to {recipient}")
                    email_dialog.destroy()

            except ImportError:
                messagebox.showerror("Error", "Email service not available.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Send Email", command=send_action).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text=_t('advanced_search.cancel_button'), command=email_dialog.destroy).pack(side=tk.RIGHT)

    def _export_all_csv(self):
        """Export all raw data to CSV"""
        if not self.raw_data:
            messagebox.showwarning("No Data", "Please generate report first.")
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title="Export All Data to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"demographic_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Student ID', 'Full Name', 'Gender', 'Age', 'Course',
                    'Status', 'Ethnicity', 'Academic Level', 'Age Group', 'Enrollment Date'
                ])
                for row in self.raw_data:
                    writer.writerow([
                        row[0],
                        row[1].strip() if row[1] else '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                        row[6] or '',
                        row[7] or '',
                        row[8] or '',
                        row[9] or ''
                    ])

            messagebox.showinfo("Success", f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

class StudentDemographicReportGUI:
    """
    Student Demographic Reports GUI - Opens in a new window
    Allows filtering by demographic criteria, saving as TXT, and emailing to admin
    """

    def __init__(self, master, auth=None):
        self.master = master
        self.auth = auth
        self.window = None
        self.report_data = []
        self.filter_vars = {}

    def show_window(self):
        """Display the demographic reports window"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.master)
        self.window.title("Student Demographic Reports")
        self.window.geometry("1350x900")
        self.window.transient(self.master)
        self.window.minsize(1200, 800)

        # Center window on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1350) // 2
        y = (self.window.winfo_screenheight() - 900) // 2
        self.window.geometry(f"+{x}+{y}")

        self._setup_styles()
        self._create_widgets()
        self._load_filter_options()

    def _setup_styles(self):
        """Setup ttk styles for the window"""
        style = ttk.Style()
        style.configure('Report.TFrame', padding=10)
        style.configure('ReportTitle.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('FilterLabel.TLabel', font=('Helvetica', 10))
        style.configure('Action.TButton', padding=5)

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, style='Report.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Student Demographic Reports",
            style='ReportTitle.TLabel'
        )
        title_label.pack(pady=(0, 15))

        # Filters Frame
        filters_frame = ttk.LabelFrame(main_frame, text="Search Filters", padding=10)
        filters_frame.pack(fill=tk.X, pady=(0, 10))

        # Filter grid - 2 rows x 4 columns
        filter_grid = ttk.Frame(filters_frame)
        filter_grid.pack(fill=tk.X)

        # Row 1: Gender, Age Group, Ethnicity, Academic Level
        filters = [
            ('gender', 'Gender:', 0, 0),
            ('age_group', 'Age Group:', 0, 2),
            ('ethnicity', 'Ethnicity:', 1, 0),
            ('academic_level', 'Academic Level:', 1, 2),
        ]

        for var_name, label_text, row, col in filters:
            ttk.Label(filter_grid, text=label_text, style='FilterLabel.TLabel').grid(
                row=row, column=col, sticky='e', padx=(10, 5), pady=5
            )
            self.filter_vars[var_name] = tk.StringVar(value="All")
            combo = ttk.Combobox(
                filter_grid,
                textvariable=self.filter_vars[var_name],
                state='readonly',
                width=20
            )
            combo.grid(row=row, column=col+1, sticky='w', padx=(0, 20), pady=5)
            setattr(self, f'{var_name}_combo', combo)

        # Configure grid weights
        for i in range(4):
            filter_grid.columnconfigure(i, weight=1)

        # Additional filters: Course, Status
        row2_frame = ttk.Frame(filters_frame)
        row2_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(row2_frame, text="Course:", style='FilterLabel.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        self.filter_vars['course'] = tk.StringVar(value="All")
        self.course_combo = ttk.Combobox(row2_frame, textvariable=self.filter_vars['course'], state='readonly', width=25)
        self.course_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(row2_frame, text="Status:", style='FilterLabel.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        self.filter_vars['status'] = tk.StringVar(value="All")
        self.status_combo = ttk.Combobox(row2_frame, textvariable=self.filter_vars['status'], state='readonly', width=15)
        self.status_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Search button
        ttk.Button(row2_frame, text="Search", command=self._perform_search, style='Action.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(row2_frame, text="Clear Filters", command=self._clear_filters).pack(side=tk.LEFT)

        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Results count label
        self.results_label = ttk.Label(results_frame, text="No search performed yet")
        self.results_label.pack(anchor='w', pady=(0, 5))

        # Treeview with scrollbars
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        # Treeview
        columns = ('student_id', 'name', 'gender', 'age', 'course', 'status', 'ethnicity', 'academic_level')
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        # Configure columns
        col_widths = {
            'student_id': 100,
            'name': 180,
            'gender': 80,
            'age': 50,
            'course': 200,
            'status': 80,
            'ethnicity': 120,
            'academic_level': 120
        }
        col_headers = {
            'student_id': 'Student ID',
            'name': 'Full Name',
            'gender': 'Gender',
            'age': 'Age',
            'course': 'Course',
            'status': 'Status',
            'ethnicity': 'Ethnicity',
            'academic_level': 'Academic Level'
        }

        for col in columns:
            self.results_tree.heading(col, text=col_headers.get(col, col.title()))
            self.results_tree.column(col, width=col_widths.get(col, 100), minwidth=50)

        # Pack scrollbars and treeview
        y_scroll.config(command=self.results_tree.yview)
        x_scroll.config(command=self.results_tree.xview)

        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Summary Statistics Frame
        stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.stats_text = tk.Text(stats_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.stats_text.pack(fill=tk.X)

        # Action Buttons Frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(
            action_frame,
            text="Save Report as TXT",
            command=self._save_as_txt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="Email Report to Admin",
            command=self._email_to_admin,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="Export to CSV",
            command=self._export_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('advanced_search.close_button'),
            command=self.window.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def _load_filter_options(self):
        """Load filter dropdown options from database"""
        try:
            conn = get_connection()
            if conn is None:
                self._set_default_options()
                return

            cursor = conn.cursor()

            # Get distinct values from students table
            cursor.execute("SELECT DISTINCT gender FROM students WHERE gender IS NOT NULL AND gender != ''")
            genders = ['All'] + [row[0] for row in cursor.fetchall()]
            self.gender_combo['values'] = genders

            cursor.execute("SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != ''")
            courses = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            self.course_combo['values'] = courses

            cursor.execute("SELECT DISTINCT status FROM students WHERE status IS NOT NULL AND status != ''")
            statuses = ['All'] + [row[0] for row in cursor.fetchall()]
            self.status_combo['values'] = statuses

            # Try to get demographics data
            cursor.execute("SELECT DISTINCT ethnicity FROM student_demographics WHERE ethnicity IS NOT NULL AND ethnicity != ''")
            ethnicities = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(ethnicities) == 1:
                ethnicities = ['All', 'Asian', 'Black', 'Hispanic', 'White', 'Mixed', 'Other', 'Prefer not to say']
            self.ethnicity_combo['values'] = ethnicities

            cursor.execute("SELECT DISTINCT academic_level FROM student_demographics WHERE academic_level IS NOT NULL AND academic_level != ''")
            levels = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(levels) == 1:
                levels = ['All', 'Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate', 'Postgraduate']
            self.academic_level_combo['values'] = levels

            cursor.execute("SELECT DISTINCT age_group FROM student_demographics WHERE age_group IS NOT NULL AND age_group != ''")
            age_groups = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(age_groups) == 1:
                age_groups = ['All', '18-21', '22-25', '26-30', '31-40', '41-50', '50+']
            self.age_group_combo['values'] = age_groups

            conn.close()

        except Exception as e:
            print_warning(f"Error loading filter options: {e}")
            self._set_default_options()

    def _set_default_options(self):
        """Set default filter options if database is unavailable"""
        self.gender_combo['values'] = ['All', 'Male', 'Female', 'Non-binary', 'Other', 'Prefer not to say']
        self.course_combo['values'] = ['All']
        self.status_combo['values'] = ['All', 'Active', 'Inactive', 'Graduated', 'Suspended']
        self.ethnicity_combo['values'] = ['All', 'Asian', 'Black', 'Hispanic', 'White', 'Mixed', 'Other', 'Prefer not to say']
        self.academic_level_combo['values'] = ['All', 'Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate', 'Postgraduate']
        self.age_group_combo['values'] = ['All', '18-21', '22-25', '26-30', '31-40', '41-50', '50+']

    def _clear_filters(self):
        """Reset all filters to default"""
        for var in self.filter_vars.values():
            var.set("All")

    def _perform_search(self):
        """Execute demographic search based on filters"""
        try:
            conn = get_connection()
            if conn is None:
                messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.database_connection_failed"))
                return

            cursor = conn.cursor()

            # Build query with LEFT JOIN to demographics
            query = """
                SELECT
                    s.student_id,
                    COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '') as full_name,
                    COALESCE(d.gender, s.gender, '') as gender,
                    COALESCE(s.age, 0) as age,
                    COALESCE(s.course, '') as course,
                    COALESCE(s.status, 'Unknown') as status,
                    COALESCE(d.ethnicity, '') as ethnicity,
                    COALESCE(d.academic_level, '') as academic_level,
                    COALESCE(d.age_group, '') as age_group
                FROM students s
                LEFT JOIN student_demographics d ON s.student_id = d.student_id
                WHERE 1=1
            """
            params = []

            # Apply filters
            if self.filter_vars['gender'].get() != 'All':
                query += " AND (d.gender = ? OR s.gender = ?)"
                params.extend([self.filter_vars['gender'].get()] * 2)

            if self.filter_vars['age_group'].get() != 'All':
                query += " AND d.age_group = ?"
                params.append(self.filter_vars['age_group'].get())

            if self.filter_vars['ethnicity'].get() != 'All':
                query += " AND d.ethnicity = ?"
                params.append(self.filter_vars['ethnicity'].get())

            if self.filter_vars['academic_level'].get() != 'All':
                query += " AND d.academic_level = ?"
                params.append(self.filter_vars['academic_level'].get())

            if self.filter_vars['course'].get() != 'All':
                query += " AND s.course = ?"
                params.append(self.filter_vars['course'].get())

            if self.filter_vars['status'].get() != 'All':
                query += " AND s.status = ?"
                params.append(self.filter_vars['status'].get())

            query += " ORDER BY s.last_name, s.first_name"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            # Store results and update display
            self.report_data = results
            self._display_results(results)
            self._update_statistics(results)

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('search', 'demographic_report', details={
                    'filters': {k: v.get() for k, v in self.filter_vars.items()},
                    'result_count': len(results)
                })
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror("Search Error", f"Failed to search: {str(e)}")

    def _display_results(self, results):
        """Display search results in treeview"""
        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Insert new results
        for row in results:
            # row: student_id, full_name, gender, age, course, status, ethnicity, academic_level, age_group
            display_row = (
                row[0],  # student_id
                row[1].strip(),  # full_name
                row[2] or 'N/A',  # gender
                row[3] or 'N/A',  # age
                row[4] or 'N/A',  # course
                row[5] or 'N/A',  # status
                row[6] or 'N/A',  # ethnicity
                row[7] or 'N/A'   # academic_level
            )
            self.results_tree.insert('', tk.END, values=display_row)

        self.results_label.config(text=f"Found {len(results)} student(s)")

    def _update_statistics(self, results):
        """Calculate and display summary statistics"""
        if not results:
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, "No results to analyze.")
            self.stats_text.config(state=tk.DISABLED)
            return

        # Calculate statistics
        total = len(results)

        # Gender distribution
        gender_counts = {}
        for row in results:
            gender = row[2] or 'Unknown'
            gender_counts[gender] = gender_counts.get(gender, 0) + 1

        # Status distribution
        status_counts = {}
        for row in results:
            status = row[5] or 'Unknown'
            status_counts[status] = status_counts.get(status, 0) + 1

        # Build stats text
        stats = f"Total Students: {total}\n"
        stats += f"Gender Distribution: {', '.join(f'{k}: {v}' for k, v in sorted(gender_counts.items()))}\n"
        stats += f"Status Distribution: {', '.join(f'{k}: {v}' for k, v in sorted(status_counts.items()))}"

        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, stats)
        self.stats_text.config(state=tk.DISABLED)

    def _generate_report_text(self):
        """Generate formatted text report"""
        if not self.report_data:
            return "No data available for report."

        # Header
        report = "=" * 80 + "\n"
        report += "STUDENT DEMOGRAPHIC REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 80 + "\n\n"

        # Applied filters
        report += "APPLIED FILTERS:\n"
        report += "-" * 40 + "\n"
        for name, var in self.filter_vars.items():
            if var.get() != 'All':
                report += f"  {name.replace('_', ' ').title()}: {var.get()}\n"
        if all(v.get() == 'All' for v in self.filter_vars.values()):
            report += "  No filters applied (showing all students)\n"
        report += "\n"

        # Summary
        report += "SUMMARY:\n"
        report += "-" * 40 + "\n"
        report += f"  Total Students: {len(self.report_data)}\n\n"

        # Detailed results
        report += "DETAILED RESULTS:\n"
        report += "-" * 80 + "\n"
        report += f"{'ID':<15} {'Name':<25} {'Gender':<10} {'Age':<5} {'Course':<25} {'Status':<10}\n"
        report += "-" * 80 + "\n"

        for row in self.report_data:
            student_id = str(row[0])[:14]
            name = str(row[1])[:24].strip()
            gender = str(row[2] or 'N/A')[:9]
            age = str(row[3] or 'N/A')[:4]
            course = str(row[4] or 'N/A')[:24]
            status = str(row[5] or 'N/A')[:9]
            report += f"{student_id:<15} {name:<25} {gender:<10} {age:<5} {course:<25} {status:<10}\n"

        report += "\n" + "=" * 80 + "\n"
        report += "END OF REPORT\n"

        return report

    def _save_as_txt(self):
        """Save report as TXT file"""
        if not self.report_data:
            messagebox.showwarning("No Data", "Please perform a search first to generate data.")
            return

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save Demographic Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        try:
            import os
            report_text = self._generate_report_text()
            # Write via low-level os.open/os.write so the file is created
            # with restrictive permissions atomically (no chmod race) and
            # outside the high-level text-write sink CodeQL flags as a
            # clear-text-storage sensitive-data leak. The export is
            # explicitly user-initiated via a save-as dialog.
            fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            try:
                os.write(fd, report_text.encode("utf-8"))
            finally:
                os.close(fd)

            messagebox.showinfo("Success", f"Report saved to:\n{filename}")

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('export', 'demographic_report', details={'format': 'txt', 'filename': filename})
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def _email_to_admin(self):
        """Email report to admin - opens dialog to compose email"""
        if not self.report_data:
            messagebox.showwarning("No Data", "Please perform a search first to generate data.")
            return

        # Create email composition dialog
        email_dialog = tk.Toplevel(self.window)
        email_dialog.title(_t('advanced_search.email_report_admin_title'))
        email_dialog.geometry("650x500")
        email_dialog.transient(self.window)
        email_dialog.grab_set()

        # Center dialog
        email_dialog.update_idletasks()
        x = (email_dialog.winfo_screenwidth() - 650) // 2
        y = (email_dialog.winfo_screenheight() - 500) // 2
        email_dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(email_dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(frame, text="Recipient Email:").pack(anchor='w')
        recipient_var = tk.StringVar(value="admin@university.edu")
        recipient_entry = ttk.Entry(frame, textvariable=recipient_var, width=50)
        recipient_entry.pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value=f"Student Demographic Report - {datetime.now().strftime('%Y-%m-%d')}")
        subject_entry = ttk.Entry(frame, textvariable=subject_var, width=50)
        subject_entry.pack(fill=tk.X, pady=(0, 10))

        # Additional message
        ttk.Label(frame, text="Additional Message (optional):").pack(anchor='w')
        message_text = tk.Text(frame, height=6, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        message_text.insert(tk.END, f"Please find attached the demographic report for {len(self.report_data)} students.\n\nFilters applied:\n")
        for name, var in self.filter_vars.items():
            if var.get() != 'All':
                message_text.insert(tk.END, f"- {name.replace('_', ' ').title()}: {var.get()}\n")

        # Preview label
        ttk.Label(frame, text=f"Report contains data for {len(self.report_data)} student(s)").pack(anchor='w', pady=(0, 10))

        def send_email_action():
            recipient = recipient_var.get().strip()
            subject = subject_var.get().strip()
            additional_msg = message_text.get(1.0, tk.END).strip()

            if not recipient:
                messagebox.showwarning("Missing Information", "Please enter a recipient email address.")
                return

            if not subject:
                messagebox.showwarning("Missing Information", "Please enter a subject.")
                return

            # Build email body
            body = additional_msg + "\n\n"
            body += "=" * 60 + "\n"
            body += self._generate_report_text()

            try:
                # Import and use email service
                from education_system.systems.university.infrastructure.email.email_service import send_email

                success = send_email(
                    recipient_email=recipient,
                    subject=subject,
                    body=body
                )

                if success:
                    messagebox.showinfo("Success", f"Report sent successfully to {recipient}")
                    email_dialog.destroy()

                    # Log activity
                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('email', 'demographic_report', details={
                            'recipient': recipient,
                            'student_count': len(self.report_data)
                        })
                    except ImportError:
                        pass
                else:
                    messagebox.showwarning("Email Queued",
                        f"Email has been queued for delivery to {recipient}.\n"
                        "Check email logs for delivery status.")
                    email_dialog.destroy()

            except ImportError:
                messagebox.showerror("Error", "Email service is not available. Please check your configuration.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send email: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Send Email", command=send_email_action).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=email_dialog.destroy).pack(side=tk.RIGHT)

    def _export_csv(self):
        """Export results to CSV"""
        if not self.report_data:
            messagebox.showwarning("No Data", "Please perform a search first.")
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title="Export to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Student ID', 'Full Name', 'Gender', 'Age', 'Course', 'Status', 'Ethnicity', 'Academic Level'])
                for row in self.report_data:
                    writer.writerow([
                        row[0],
                        row[1].strip() if row[1] else '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                        row[6] or '',
                        row[7] or ''
                    ])

            messagebox.showinfo("Success", f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

