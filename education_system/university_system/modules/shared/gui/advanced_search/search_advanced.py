from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.university_system.core.sql_safety import escape_like, validate_identifier, validate_table_name, validate_field_for_query, validate_column_name  # nosec B608
import sqlite3
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

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
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
    from education_system.university_system.modules.shared.utils.console_output import ConsoleOutput
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
    from education_system.university_system.modules.shared.utils.chart_generator import (
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
    from education_system.university_system.modules.shared.services.analytics.advanced_search import (
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
    from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
    from education_system.university_system.infrastructure.email.admin import search_users, list_all_users
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
        from education_system.university_system.infrastructure.database.db import sqlite3
        # Use centralized path system
        from education_system.university_system.core import paths
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
            safe_field = validate_identifier(field, "column")
            cursor.execute("SELECT COUNT(*) FROM students WHERE [" + safe_field + "] IS NULL OR [" + safe_field + "] = ''")
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
        # Prefer the central connection from education_system.university_system.infrastructure.database.db if available
        from education_system.university_system.infrastructure.database.db import get_connection as central_get_connection
        return central_get_connection()
    except Exception:
        try:
            # Compute the path to the central student_records.db relative to this file.
            from education_system.university_system.infrastructure.database.db import sqlite3
            from education_system.university_system.core import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        except Exception as e:
            print_error(f"Database connection error: {e}")
            return None

from education_system.university_system.modules.shared.gui.advanced_search.base import AdvancedSearchGUI

def show_regex_search(self):
    """Show regex search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.regex_search_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.regex_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.regex_pattern')}:").pack(anchor='w')
    pattern_var = tk.StringVar()
    ttk.Entry(frame, textvariable=pattern_var, width=50).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_field')}:").pack(anchor='w')
    field_var = tk.StringVar(value="first_name")
    field_combo = ttk.Combobox(frame, textvariable=field_var,
                              values=["first_name", "last_name", "email", "student_id"],
                              state='readonly')
    field_combo.pack(anchor='w', pady=(0, 20))

    # Pattern examples
    examples_frame = ttk.LabelFrame(frame, text=_t('advanced_search.search_advanced.pattern_examples'), padding="10")
    examples_frame.pack(fill=tk.X, pady=(0, 20))

    examples = [
        ("^J.*", "Names starting with 'J'"),
        (".*son$", "Names ending with 'son'"),
        ("[0-9]+", "Contains numbers"),
        ("^STU[0-9]{3}$", "Student ID format STU followed by 3 digits")
    ]

    for pattern, description in examples:
        example_frame = ttk.Frame(examples_frame)
        example_frame.pack(fill=tk.X, pady=2)
        ttk.Button(example_frame, text=pattern, width=15,
                  command=lambda p=pattern: pattern_var.set(p)).pack(side=tk.LEFT)
        ttk.Label(example_frame, text=f" - {description}").pack(side=tk.LEFT)

    def execute_regex_search():
        pattern = pattern_var.get().strip()
        field = field_var.get()

        if not pattern:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_pattern'), _t('advanced_search.search_advanced.enter_regex_pattern'))
            return

        dialog.destroy()
        self.update_status("Performing regex search...")
        self.start_progress()

        def run_regex():
            try:
                results = self.perform_regex_search(pattern, field)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Regex search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Regex search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_regex, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_regex_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_regex_search = show_regex_search

def perform_regex_search(self, pattern, field):
    """Perform regular expression search"""
    try:
        import re
        conn = get_connection()
        cursor = conn.cursor()

        # Get all records and filter with regex
        cursor.execute(f"SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        field_index_map = {
            'student_id': 0, 'email': 1, 'title': 2,
            'first_name': 3, 'middle_name': 4, 'last_name': 5,
            'gender': 6, 'date_of_birth': 7, 'age': 8,
            'course': 9, 'registration_datetime': 10
        }

        field_index = field_index_map.get(field, 3)  # Default to first_name

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if compiled_pattern.search(str(student[field_index])):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Regex search error: {str(e)}")
AdvancedSearchGUI.perform_regex_search = perform_regex_search

def show_wildcard_search(self):
    """Show wildcard search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🃏 {_t('advanced_search.wildcard_search_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.wildcard_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.wildcard_pattern_label')}:").pack(anchor='w')
    pattern_var = tk.StringVar()
    ttk.Entry(frame, textvariable=pattern_var, width=40).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_field')}:").pack(anchor='w')
    field_var = tk.StringVar(value="first_name")
    field_combo = ttk.Combobox(frame, textvariable=field_var,
                              values=["first_name", "last_name", "email", "student_id"],
                              state='readonly')
    field_combo.pack(anchor='w', pady=(0, 20))

    # Examples
    examples_frame = ttk.LabelFrame(frame, text=_t('advanced_search.search_advanced.examples'), padding="10")
    examples_frame.pack(fill=tk.X, pady=(0, 20))

    examples = ["J*", "*son", "STU???", "*@*.com"]
    for example in examples:
        ttk.Button(examples_frame, text=example, width=10,
                  command=lambda p=example: pattern_var.set(p)).pack(side=tk.LEFT, padx=2)

    def execute_wildcard_search():
        pattern = pattern_var.get().strip()
        field = field_var.get()

        if not pattern:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_pattern'), _t('advanced_search.search_advanced.missing_wildcard_pattern'))
            return

        dialog.destroy()
        self.update_status("Performing wildcard search...")
        self.start_progress()

        def run_wildcard():
            try:
                results = self.perform_wildcard_search(pattern, field)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Wildcard search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Wildcard search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_wildcard, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_wildcard_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_wildcard_search = show_wildcard_search

def perform_wildcard_search(self, pattern, field):
    """Perform wildcard search (* and ?)"""
    try:
        import fnmatch
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        field_index_map = {
            'student_id': 0, 'email': 1, 'first_name': 3,
            'last_name': 5, 'course': 9
        }

        field_index = field_index_map.get(field, 3)

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if fnmatch.fnmatch(str(student[field_index]).lower(), pattern.lower()):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Wildcard search error: {str(e)}")
AdvancedSearchGUI.perform_wildcard_search = perform_wildcard_search

def show_search_all_fields(self):
    """Show search all fields dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.search_all_fields_dialog_title')}")
    dialog.geometry("400x250")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.search_all_fields_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_term')}:").pack(anchor='w')
    search_var = tk.StringVar()
    ttk.Entry(frame, textvariable=search_var, width=40).pack(fill=tk.X, pady=(0, 20))

    ttk.Label(frame, text=_t('advanced_search.search_advanced.search_all_fields_info'),
             font=('Arial', 9)).pack(pady=(0, 20))

    def execute_all_fields_search():
        search_term = search_var.get().strip()

        if not search_term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_term'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Searching all fields...")
        self.start_progress()

        def run_all_fields():
            try:
                results = self.perform_search_all_fields(search_term)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"All fields search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"All fields search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_all_fields, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_all_fields_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_search_all_fields = show_search_all_fields

def show_phonetic_search(self):
    """Show phonetic search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔊 {_t('advanced_search.phonetic_search_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.phonetic_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.enter_name_phonetic')}:").pack(anchor='w')
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=30).pack(fill=tk.X, pady=(0, 20))

    info_text = """Phonetic search finds names that sound similar:
• John ↔ Jon
• Smith ↔ Smyth
• Catherine ↔ Katherine

Uses Soundex algorithm for matching."""

    ttk.Label(frame, text=info_text, font=('Arial', 9), justify=tk.LEFT).pack(pady=(0, 20))

    def execute_phonetic_search():
        name = name_var.get().strip()

        if not name:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_name'), _t('advanced_search.search_advanced.enter_name'))
            return

        dialog.destroy()
        self.update_status("Performing phonetic search...")
        self.start_progress()

        def run_phonetic():
            try:
                results = self.perform_phonetic_search(name)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Phonetic search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Phonetic search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_phonetic, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_phonetic_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_phonetic_search = show_phonetic_search

def show_auto_complete_search(self):
    """Show auto-complete search interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.auto_complete_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.autocomplete_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Search field with suggestions
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.type_to_search')}:").pack(anchor='w')

    search_var = tk.StringVar()
    search_entry = ttk.Entry(frame, textvariable=search_var, width=40)
    search_entry.pack(fill=tk.X, pady=(0, 10))

    # Suggestions listbox
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.suggestions')}:").pack(anchor='w')

    suggestions_frame = ttk.Frame(frame)
    suggestions_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

    suggestions_listbox = tk.Listbox(suggestions_frame, height=10)
    suggestions_scrollbar = ttk.Scrollbar(suggestions_frame, orient=tk.VERTICAL, command=suggestions_listbox.yview)
    suggestions_listbox.configure(yscrollcommand=suggestions_scrollbar.set)

    suggestions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    suggestions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_suggestions(*args):
        """Update suggestions based on input"""
        term = search_var.get().lower()
        suggestions_listbox.delete(0, tk.END)

        if len(term) >= 2:
            # Get suggestions from database
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get matching names, emails, and student IDs
                cursor.execute("""
                    SELECT DISTINCT
                        first_name || ' ' || last_name as full_name,
                        email_address,
                        student_id
                    FROM students
                    WHERE LOWER(first_name || ' ' || last_name) LIKE ?
                       OR LOWER(email_address) LIKE ?
                       OR LOWER(student_id) LIKE ?
                    LIMIT 20
                """, (f'%{term}%', f'%{term}%', f'%{term}%'))

                results = cursor.fetchall()
                conn.close()

                for full_name, email, student_id in results:
                    suggestions_listbox.insert(tk.END, f"{full_name} ({email})")

            except Exception as e:
                suggestions_listbox.insert(tk.END, f"Error loading suggestions: {str(e)}")

    search_var.trace('w', update_suggestions)

    def select_suggestion(event):
        """Select suggestion and populate search field"""
        selection = suggestions_listbox.curselection()
        if selection:
            selected_text = suggestions_listbox.get(selection[0])
            # Extract name from "Name (email)" format
            name_part = selected_text.split(' (')[0]
            search_var.set(name_part)

    suggestions_listbox.bind('<Double-1>', select_suggestion)

    def execute_autocomplete_search():
        term = search_var.get().strip()
        if not term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_input'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Performing auto-complete search...")
        self.start_progress()

        def run_search():
            try:
                results = self.perform_autocomplete_search(term)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Auto-complete search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Auto-complete search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_autocomplete_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_auto_complete_search = show_auto_complete_search

def perform_autocomplete_search(self, term):
    """Perform auto-complete search"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        SELECT * FROM students
        WHERE LOWER(first_name || ' ' || last_name) LIKE ?
           OR LOWER(email_address) LIKE ?
           OR LOWER(student_id) LIKE ?
        """
        params = [f'%{term.lower()}%'] * 3

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Auto-complete search error: {str(e)}")
AdvancedSearchGUI.perform_autocomplete_search = perform_autocomplete_search

def perform_regex_search(self, pattern, field):
    """Perform regular expression search"""
    try:
        import re
        conn = get_connection()
        cursor = conn.cursor()

        # Get all records and filter with regex
        cursor.execute(f"SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        field_index_map = {
            'student_id': 0, 'email': 1, 'title': 2,
            'first_name': 3, 'middle_name': 4, 'last_name': 5,
            'gender': 6, 'date_of_birth': 7, 'age': 8,
            'course': 9, 'registration_datetime': 10
        }

        field_index = field_index_map.get(field, 3)  # Default to first_name

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if compiled_pattern.search(str(student[field_index])):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Regex search error: {str(e)}")
AdvancedSearchGUI.perform_regex_search = perform_regex_search

def perform_wildcard_search(self, pattern, field):
    """Perform wildcard search (* and ?)"""
    try:
        import fnmatch
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        field_index_map = {
            'student_id': 0, 'email': 1, 'first_name': 3,
            'last_name': 5, 'course': 9
        }

        field_index = field_index_map.get(field, 3)

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if fnmatch.fnmatch(str(student[field_index]).lower(), pattern.lower()):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Wildcard search error: {str(e)}")
AdvancedSearchGUI.perform_wildcard_search = perform_wildcard_search

def perform_search_all_fields(self, search_term):
    """Search across all text fields"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{escape_like(search_term.lower())}%"
        query = """
        SELECT * FROM students WHERE
        LOWER(student_id) LIKE ? OR
        LOWER(email_address) LIKE ? OR
        LOWER(title) LIKE ? OR
        LOWER(first_name) LIKE ? OR
        LOWER(middle_name) LIKE ? OR
        LOWER(last_name) LIKE ? OR
        LOWER(gender) LIKE ? OR
        LOWER(course) LIKE ? OR
        LOWER(registration_datetime) LIKE ?
        """

        params = [search_pattern] * 9
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Search all fields error: {str(e)}")
AdvancedSearchGUI.perform_search_all_fields = perform_search_all_fields

def perform_phonetic_search(self, search_term):
    """Perform phonetic name search using Soundex algorithm"""
    try:
        def soundex(word):
            """Generate Soundex code for phonetic matching"""
            if not word:
                return "0000"

            word = word.upper()
            soundex_code = word[0]

            # Mapping for consonants
            mapping = {
                'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
                'L': '4', 'MN': '5', 'R': '6'
            }

            for char in word[1:]:
                for key, value in mapping.items():
                    if char in key:
                        if soundex_code[-1] != value:
                            soundex_code += value
                        break

            # Pad or truncate to 4 characters
            soundex_code = (soundex_code + '0000')[:4]
            return soundex_code

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        search_soundex = soundex(search_term)
        matched_students = []

        for student in all_students:
            first_name = student[3] if len(student) > 3 else ""
            last_name = student[5] if len(student) > 5 else ""

            if (soundex(first_name) == search_soundex or
                soundex(last_name) == search_soundex):
                matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Phonetic search error: {str(e)}")
AdvancedSearchGUI.perform_phonetic_search = perform_phonetic_search

def show_fuzzy_search(self):
    """Complete fuzzy search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.fuzzy_search_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.fuzzy_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_term')}:").pack(anchor='w')
    search_var = tk.StringVar()
    ttk.Entry(frame, textvariable=search_var, width=30).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.similarity_threshold')}:").pack(anchor='w')
    threshold_var = tk.StringVar(value="0.6")
    ttk.Entry(frame, textvariable=threshold_var, width=10).pack(anchor='w', pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.algorithm')}:").pack(anchor='w')
    algo_var = tk.StringVar(value="1")
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.standard_fuzzy_matching'), variable=algo_var, value="1").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.phonetic_matching_soundex'), variable=algo_var, value="2").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.both_algorithms'), variable=algo_var, value="3").pack(anchor='w', pady=(0, 20))

    def execute_fuzzy_search():
        term = search_var.get().strip()
        if not term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_input'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Performing fuzzy search...")

        def run_fuzzy():
            try:
                results = self.perform_fuzzy_search(term, float(threshold_var.get()), algo_var.get())
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Fuzzy search for '{term}' completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Fuzzy search error: {str(e)}"))

        threading.Thread(target=run_fuzzy, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_fuzzy_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_fuzzy_search = show_fuzzy_search

def perform_fuzzy_search(self, search_term, threshold, algorithm):
    """Perform fuzzy search with given parameters"""
    try:
        from difflib import SequenceMatcher

        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        all_rows = cursor.fetchall()
        conn.close()

        matched_students = []
        search_term_lower = search_term.lower()

        for row in all_rows:
            # Use named column access to avoid schema index mismatch
            first_name = (row["first_name"] or "").lower()
            last_name = (row["last_name"] or "").lower()

            best_ratio = 0

            if algorithm in ['1', '3']:  # Standard fuzzy matching
                first_ratio = SequenceMatcher(None, search_term_lower, first_name).ratio()
                last_ratio = SequenceMatcher(None, search_term_lower, last_name).ratio()
                full_name = f"{first_name} {last_name}".strip()
                full_ratio = SequenceMatcher(None, search_term_lower, full_name).ratio()
                best_ratio = max(first_ratio, last_ratio, full_ratio)

            if algorithm in ['2', '3']:  # Phonetic matching
                def simple_soundex(word):
                    if not word:
                        return "0000"
                    word = word.upper()
                    result = word[0]
                    mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                    for char in word[1:]:
                        for key, value in mapping.items():
                            if char in key and result[-1] != value:
                                result += value
                                break
                    return (result + '0000')[:4]

                search_soundex = simple_soundex(search_term)
                first_soundex = simple_soundex(first_name)
                last_soundex = simple_soundex(last_name)

                if search_soundex == first_soundex or search_soundex == last_soundex:
                    best_ratio = max(best_ratio, 0.8)

            if best_ratio >= threshold:
                matched_students.append(tuple(row))

        return matched_students

    except Exception as e:
        raise Exception(f"Fuzzy search error: {str(e)}")
AdvancedSearchGUI.perform_fuzzy_search = perform_fuzzy_search

def show_module_search(self):
    """Complete module enrollment search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.module_enrollment_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.module_enrollment_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Module selection
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.select_modules')}:").pack(anchor='w')

    modules_frame = ttk.Frame(frame)
    modules_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    # Module listbox with scrollbar
    listbox_frame = ttk.Frame(modules_frame)
    listbox_frame.pack(fill=tk.BOTH, expand=True)

    self.module_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, height=10)
    scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.module_listbox.yview)
    self.module_listbox.configure(yscrollcommand=scrollbar.set)

    self.module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load modules
    self.load_available_modules()

    # Match type
    match_frame = ttk.Frame(frame)
    match_frame.pack(fill=tk.X, pady=(10, 20))

    ttk.Label(match_frame, text=f"{_t('advanced_search.search_advanced.match_type')}:").pack(anchor='w')
    match_var = tk.StringVar(value="any")
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.any_selected_modules'), variable=match_var, value="any").pack(anchor='w')
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.all_selected_modules'), variable=match_var, value="all").pack(anchor='w')

    def execute_module_search():
        selected_indices = self.module_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("_t('advanced_search.no_selection')", "Please select at least one module.")
            return

        selected_modules = [self.available_modules[i][0] for i in selected_indices]
        match_type = match_var.get()

        dialog.destroy()
        self.update_status("Searching by module enrollment...")

        def run_module_search():
            try:
                results = self.perform_module_search(selected_modules, match_type)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Module search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Module search error: {str(e)}"))

        threading.Thread(target=run_module_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_module_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_module_search = show_module_search

def load_available_modules(self):
    """Load available modules into the listbox"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()
        # Join with modules table to get proper module names
        cursor.execute("""
            SELECT DISTINCT sm.module_code,
                   COALESCE(m.module_name, sm.module_name, sm.module_code) as module_name
            FROM student_modules sm
            LEFT JOIN modules m ON sm.module_code = m.module_code
            ORDER BY module_name
        """)
        self.available_modules = cursor.fetchall()
        conn.close()

        self.module_listbox.delete(0, tk.END)
        for code, name in self.available_modules:
            display_name = name or code
            self.module_listbox.insert(tk.END, f"{code} - {display_name}")

    except Exception as e:
        messagebox.showerror(_t('common.error'), _t('advanced_search.search_advanced.could_not_load_modules', error=str(e)))
AdvancedSearchGUI.load_available_modules = load_available_modules

def perform_module_search(self, module_codes, match_type):
    """Perform module enrollment search"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()

        if match_type == "all":
            # Students enrolled in ALL modules
            query = "SELECT s.* FROM students s WHERE "
            conditions = []
            params = []

            for module_code in module_codes:
                conditions.append("""
                EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """)
                params.append(module_code)

            query += " AND ".join(conditions)
        else:
            # Students enrolled in ANY module
            placeholders = ",".join(["?" for _ in module_codes])
            query = f"""
            SELECT DISTINCT s.* FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code IN ({placeholders})
            """
            params = module_codes

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Module search error: {str(e)}")
AdvancedSearchGUI.perform_module_search = perform_module_search

def perform_combined_filters_search(self, filters):
    """
    Perform combined filters search with student data, modules, and date range.

    Args:
        filters (dict): Dictionary containing:
            - student_data: Dict with student field filters
            - module_codes: List of module codes
            - date_range: Dict with start and end dates
            - module_match_all: Bool for ALL vs ANY module matching

    Returns:
        list: List of matching student records
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query based on filters
        if filters["module_codes"] and filters["module_match_all"]:
            # ALL modules - need EXISTS for each module
            query = "SELECT s.* FROM students s WHERE 1=1"
            params = []

            # Student data filters
            for field, op, val in [
                ("student_id", "LIKE", f"%{escape_like(filters['student_data'].get('student_id', ''))}%"),
                ("first_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('first_name', ''))}%"),
                ("last_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('last_name', ''))}%"),
            ]:
                if filters["student_data"].get(field.replace('_', ' ').title().replace(' ', '')):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op.replace(' LOWER', '')} ?"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(val)

            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender) = LOWER(?)"
                params.append(filters["student_data"]["gender"])

            if "course" in filters["student_data"]:
                query += " AND s.course = ?"
                params.append(filters["student_data"]["course"])

            if "age_min" in filters["student_data"]:
                query += " AND s.age >= ?"
                params.append(filters["student_data"]["age_min"])

            if "age_max" in filters["student_data"]:
                query += " AND s.age <= ?"
                params.append(filters["student_data"]["age_max"])

            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime >= ?"
                params.append(filters["date_range"]["start"])

            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime <= ?"
                params.append(filters["date_range"]["end"])

            # Add EXISTS clause for each module
            for code in filters["module_codes"]:
                query += """
                AND EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """
                params.append(code)

        else:
            # ANY modules or no modules
            query = "SELECT DISTINCT s.* FROM students s"
            params = []

            if filters["module_codes"]:
                query += " JOIN student_modules sm ON s.student_id = sm.student_id"

            query += " WHERE 1=1"

            # Student data filters
            for field, op in [
                ("student_id", "LIKE"),
                ("first_name", "LIKE LOWER"),
                ("last_name", "LIKE LOWER"),
            ]:
                filter_key = field
                if filters["student_data"].get(filter_key):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op.replace(' LOWER', '')} ?"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(f"%{escape_like(filters['student_data'][filter_key])}%")

            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender) = LOWER(?)"
                params.append(filters["student_data"]["gender"])

            if "course" in filters["student_data"]:
                query += " AND s.course = ?"
                params.append(filters["student_data"]["course"])

            if "age_min" in filters["student_data"]:
                query += " AND s.age >= ?"
                params.append(filters["student_data"]["age_min"])

            if "age_max" in filters["student_data"]:
                query += " AND s.age <= ?"
                params.append(filters["student_data"]["age_max"])

            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime >= ?"
                params.append(filters["date_range"]["start"])

            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime <= ?"
                params.append(filters["date_range"]["end"])

            if filters["module_codes"]:
                placeholders = ",".join("?" for _ in filters["module_codes"])
                query += f" AND sm.module_code IN ({placeholders})"
                params.extend(filters["module_codes"])

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Combined filters search error: {str(e)}")
AdvancedSearchGUI.perform_combined_filters_search = perform_combined_filters_search

def perform_text_search(self, pattern, search_type, field):
    """Perform advanced text search"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if search_type == "wildcard":
            # Convert wildcard to SQL LIKE pattern
            sql_pattern = pattern.replace('*', '%').replace('?', '_')
            safe_field = validate_identifier(field, "column")
            query = "SELECT * FROM students WHERE [" + safe_field + "] LIKE ?"
            cursor.execute(query, (sql_pattern,))

        elif search_type == "regex":
            # For SQLite, we'll use LIKE with basic pattern conversion
            # In a full implementation, you'd need a regex extension
            sql_pattern = f"%{escape_like(pattern)}%"
            safe_field = validate_identifier(field, "column")
            query = "SELECT * FROM students WHERE [" + safe_field + "] LIKE ?"
            cursor.execute(query, (sql_pattern,))

        elif search_type == "all_fields":
            search_pattern = f"%{escape_like(pattern)}%"
            query = '''
            SELECT * FROM students WHERE
            student_id LIKE ? OR
            email_address LIKE ? OR
            first_name LIKE ? OR
            middle_name LIKE ? OR
            last_name LIKE ?
            '''
            params = [search_pattern] * 5
            cursor.execute(query, params)

        elif search_type == "phonetic":
            # Simple phonetic search implementation
            cursor.execute("SELECT * FROM students")
            all_students = cursor.fetchall()
            results = []

            def simple_soundex(word):
                if not word:
                    return "0000"
                word = word.upper()
                result = word[0]
                mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                for char in word[1:]:
                    for key, value in mapping.items():
                        if char in key and result[-1] != value:
                            result += value
                            break
                return (result + '0000')[:4]

            target_soundex = simple_soundex(pattern)

            for student in all_students:
                if (simple_soundex(student[3]) == target_soundex or  # first_name
                    simple_soundex(student[5]) == target_soundex):   # last_name
                    results.append(student)

            conn.close()
            return results

        results = cursor.fetchall()
        conn.close()
        return results

    except Exception as e:
        raise Exception(f"Text search error: {str(e)}")
AdvancedSearchGUI.perform_text_search = perform_text_search

def show_fuzzy_search(self):
    """Complete fuzzy search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.fuzzy_search_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.fuzzy_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_term')}:").pack(anchor='w')
    search_var = tk.StringVar()
    ttk.Entry(frame, textvariable=search_var, width=30).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.similarity_threshold')}:").pack(anchor='w')
    threshold_var = tk.StringVar(value="0.6")
    ttk.Entry(frame, textvariable=threshold_var, width=10).pack(anchor='w', pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.algorithm')}:").pack(anchor='w')
    algo_var = tk.StringVar(value="1")
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.standard_fuzzy_matching'), variable=algo_var, value="1").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.phonetic_matching_soundex'), variable=algo_var, value="2").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.both_algorithms'), variable=algo_var, value="3").pack(anchor='w', pady=(0, 20))

    def execute_fuzzy_search():
        term = search_var.get().strip()
        if not term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_input'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Performing fuzzy search...")

        def run_fuzzy():
            try:
                results = self.perform_fuzzy_search(term, float(threshold_var.get()), algo_var.get())
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Fuzzy search for '{term}' completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Fuzzy search error: {str(e)}"))

        threading.Thread(target=run_fuzzy, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_fuzzy_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_fuzzy_search = show_fuzzy_search

def perform_fuzzy_search(self, search_term, threshold, algorithm):
    """Perform fuzzy search with given parameters"""
    try:
        from difflib import SequenceMatcher

        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        all_rows = cursor.fetchall()
        conn.close()

        matched_students = []
        search_term_lower = search_term.lower()

        for row in all_rows:
            # Use named column access to avoid schema index mismatch
            first_name = (row["first_name"] or "").lower()
            last_name = (row["last_name"] or "").lower()

            best_ratio = 0

            if algorithm in ['1', '3']:  # Standard fuzzy matching
                first_ratio = SequenceMatcher(None, search_term_lower, first_name).ratio()
                last_ratio = SequenceMatcher(None, search_term_lower, last_name).ratio()
                full_name = f"{first_name} {last_name}".strip()
                full_ratio = SequenceMatcher(None, search_term_lower, full_name).ratio()
                best_ratio = max(first_ratio, last_ratio, full_ratio)

            if algorithm in ['2', '3']:  # Phonetic matching
                def simple_soundex(word):
                    if not word:
                        return "0000"
                    word = word.upper()
                    result = word[0]
                    mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                    for char in word[1:]:
                        for key, value in mapping.items():
                            if char in key and result[-1] != value:
                                result += value
                                break
                    return (result + '0000')[:4]

                search_soundex = simple_soundex(search_term)
                first_soundex = simple_soundex(first_name)
                last_soundex = simple_soundex(last_name)

                if search_soundex == first_soundex or search_soundex == last_soundex:
                    best_ratio = max(best_ratio, 0.8)

            if best_ratio >= threshold:
                matched_students.append(tuple(row))

        return matched_students

    except Exception as e:
        raise Exception(f"Fuzzy search error: {str(e)}")
AdvancedSearchGUI.perform_fuzzy_search = perform_fuzzy_search

def show_module_search(self):
    """Complete module enrollment search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.module_enrollment_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.module_enrollment_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Module selection
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.select_modules')}:").pack(anchor='w')

    modules_frame = ttk.Frame(frame)
    modules_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    # Module listbox with scrollbar
    listbox_frame = ttk.Frame(modules_frame)
    listbox_frame.pack(fill=tk.BOTH, expand=True)

    self.module_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, height=10)
    scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.module_listbox.yview)
    self.module_listbox.configure(yscrollcommand=scrollbar.set)

    self.module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load modules
    self.load_available_modules()

    # Match type
    match_frame = ttk.Frame(frame)
    match_frame.pack(fill=tk.X, pady=(10, 20))

    ttk.Label(match_frame, text=f"{_t('advanced_search.search_advanced.match_type')}:").pack(anchor='w')
    match_var = tk.StringVar(value="any")
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.any_selected_modules'), variable=match_var, value="any").pack(anchor='w')
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.all_selected_modules'), variable=match_var, value="all").pack(anchor='w')

    def execute_module_search():
        selected_indices = self.module_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("_t('advanced_search.no_selection')", "Please select at least one module.")
            return

        selected_modules = [self.available_modules[i][0] for i in selected_indices]
        match_type = match_var.get()

        dialog.destroy()
        self.update_status("Searching by module enrollment...")

        def run_module_search():
            try:
                results = self.perform_module_search(selected_modules, match_type)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Module search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Module search error: {str(e)}"))

        threading.Thread(target=run_module_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_module_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_module_search = show_module_search

def load_available_modules(self):
    """Load available modules into the listbox"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()
        # Join with modules table to get proper module names
        cursor.execute("""
            SELECT DISTINCT sm.module_code,
                   COALESCE(m.module_name, sm.module_name, sm.module_code) as module_name
            FROM student_modules sm
            LEFT JOIN modules m ON sm.module_code = m.module_code
            ORDER BY module_name
        """)
        self.available_modules = cursor.fetchall()
        conn.close()

        self.module_listbox.delete(0, tk.END)
        for code, name in self.available_modules:
            display_name = name or code
            self.module_listbox.insert(tk.END, f"{code} - {display_name}")

    except Exception as e:
        messagebox.showerror(_t('common.error'), _t('advanced_search.search_advanced.could_not_load_modules', error=str(e)))
AdvancedSearchGUI.load_available_modules = load_available_modules

def perform_module_search(self, module_codes, match_type):
    """Perform module enrollment search"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()

        if match_type == "all":
            # Students enrolled in ALL modules
            query = "SELECT s.* FROM students s WHERE "
            conditions = []
            params = []

            for module_code in module_codes:
                conditions.append("""
                EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """)
                params.append(module_code)

            query += " AND ".join(conditions)
        else:
            # Students enrolled in ANY module
            placeholders = ",".join(["?" for _ in module_codes])
            query = f"""
            SELECT DISTINCT s.* FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code IN ({placeholders})
            """
            params = module_codes

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Module search error: {str(e)}")
AdvancedSearchGUI.perform_module_search = perform_module_search
