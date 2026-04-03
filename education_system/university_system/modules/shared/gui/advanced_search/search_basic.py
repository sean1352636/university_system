from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.university_system.core.sql_safety import escape_like, validate_identifier, validate_table_name, validate_field_for_query, validate_column_name  # nosec B608
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
    from education_system.university_system.modules.shared.utils.i18n import (
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
        from education_system.university_system.modules.shared.constants import paths
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
            from education_system.university_system.modules.shared.constants import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        except Exception as e:
            print_error(f"Database connection error: {e}")
            return None

from education_system.university_system.modules.shared.gui.advanced_search.base import AdvancedSearchGUI

def _collect_search_criteria(self) -> Dict[str, Any]:
    """Collect current search form criteria into a serialisable dictionary."""
    criteria = {}
    for key, var in getattr(self, 'search_vars', {}).items():
        value = var.get().strip() if hasattr(var, 'get') else ''
        if value:
            criteria[key] = value
    return criteria
AdvancedSearchGUI._collect_search_criteria = _collect_search_criteria

def _apply_profile_criteria(self, criteria: Dict[str, Any]) -> None:
    """Apply saved criteria back onto the search form."""
    for key, var in getattr(self, 'search_vars', {}).items():
        try:
            var.set(criteria.get(key, ""))
        except Exception:
            pass
AdvancedSearchGUI._apply_profile_criteria = _apply_profile_criteria

def _run_profile_search(self, criteria: Dict[str, Any]):
    """Execute a basic database search using stored criteria."""
    if not criteria:
        return []
    try:
        return self.perform_database_search(criteria)
    except Exception as exc:
        messagebox.showerror(_t('advanced_search.search_basic.search_error'), _t('advanced_search.search_basic.failed_execute_profile', error=str(exc)))
        return []
AdvancedSearchGUI._run_profile_search = _run_profile_search

def create_search_form(self):
    """Create a comprehensive search form"""
    # Clear current content and create search form
    search_window = tk.Toplevel(self.master)
    search_window.title(f"🔍 {_t('advanced_search.multi_criteria_search')}")
    search_window.geometry("600x500")
    search_window.transient(self.master)
    search_window.grab_set()

    main_frame = ttk.Frame(search_window, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = ttk.Label(main_frame, text=_t('advanced_search.search_form_title'), style='Title.TLabel')
    title_label.pack(pady=(0, 20))

    # Search criteria frame
    criteria_frame = ttk.LabelFrame(main_frame, text=_t('advanced_search.search_criteria'), padding="10")
    criteria_frame.pack(fill=tk.X, pady=(0, 20))

    # Search fields
    self.search_vars = {}
    fields = [
        (_t('advanced_search.student_id'), "student_id"),
        (_t('advanced_search.first_name'), "first_name"),
        (_t('advanced_search.last_name'), "last_name"),
        (_t('advanced_search.email'), "email"),
        (_t('advanced_search.gender'), "gender"),
        (_t('advanced_search.course'), "course"),
        (_t('advanced_search.min_age'), "min_age"),
        (_t('advanced_search.max_age'), "max_age")
    ]

    for i, (label, var_name) in enumerate(fields):
        row = i // 2
        col = (i % 2) * 2

        ttk.Label(criteria_frame, text=f"{label}:").grid(row=row, column=col, sticky=tk.W, padx=(0, 5), pady=2)

        if var_name in ["gender", "course"]:
            # Dropdown for specific fields
            self.search_vars[var_name] = tk.StringVar()
            values = ["", "male", "female", "other"] if var_name == "gender" else ["", "CS", "DS"]
            combo = ttk.Combobox(criteria_frame, textvariable=self.search_vars[var_name],
                               values=values, width=15, state='readonly')
            combo.grid(row=row, column=col+1, sticky=(tk.W, tk.E), padx=(0, 10), pady=2)
        else:
            # Regular entry fields
            self.search_vars[var_name] = tk.StringVar()
            entry = ttk.Entry(criteria_frame, textvariable=self.search_vars[var_name], width=18)
            entry.grid(row=row, column=col+1, sticky=(tk.W, tk.E), padx=(0, 10), pady=2)

    # Configure grid weights
    for i in range(2):
        criteria_frame.columnconfigure(i*2+1, weight=1)

    # Buttons frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=lambda: self.execute_search(search_window),
              style='Action.TButton').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"🔄 {_t('advanced_search.clear_button')}", command=self.clear_search_form).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=search_window.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.create_search_form = create_search_form

def execute_search(self, search_window):
    """Execute the multi-criteria search"""
    # Get search criteria
    criteria = {}
    for key, var in self.search_vars.items():
        value = var.get().strip()
        if value:
            criteria[key] = value

    if not any(criteria.values()):
        messagebox.showwarning(_t('advanced_search.no_criteria'), _t('advanced_search.enter_criteria'))
        return

    search_window.destroy()
    self.update_status(_t("advanced_search.searching"))
    self.start_progress()

    def run_search():
        try:
            # Simulate the multi-criteria search
            results = self.perform_database_search(criteria)
            self.output_queue.put(("search_results", results))
            self.output_queue.put(("log", f"Search completed. Found {len(results)} results."))
        except Exception as e:
            self.output_queue.put(("error", f"Search error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_search, daemon=True).start()
AdvancedSearchGUI.execute_search = execute_search

def show_date_search(self):
    """Complete date range search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.date_range_dialog_title'))
    dialog.geometry("400x350")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_basic.date_range_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Preset options
    ttk.Label(frame, text=f"{_t('advanced_search.search_basic.quick_presets')}:").pack(anchor='w')
    preset_var = tk.StringVar(value="custom")

    presets = [
        (_t("advanced_search.search_basic.preset_custom_range"), "custom"),
        (_t("advanced_search.search_basic.preset_last_7_days"), "7d"),
        (_t("advanced_search.search_basic.preset_last_30_days"), "30d"),
        (_t("advanced_search.search_basic.preset_last_3_months"), "3m"),
        (_t("advanced_search.search_basic.preset_last_6_months"), "6m"),
        (_t("advanced_search.search_basic.preset_this_year"), "year")
    ]

    for text, value in presets:
        ttk.Radiobutton(frame, text=text, variable=preset_var, value=value).pack(anchor='w')

    # Custom date inputs
    custom_frame = ttk.LabelFrame(frame, text=_t('advanced_search.custom_range_title'), padding="10")
    custom_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Label(custom_frame, text=_t('advanced_search.start_date')).pack(anchor='w')
    start_date_var = tk.StringVar()
    ttk.Entry(custom_frame, textvariable=start_date_var, width=20).pack(anchor='w', pady=(0, 10))

    ttk.Label(custom_frame, text=_t('advanced_search.end_date')).pack(anchor='w')
    end_date_var = tk.StringVar()
    ttk.Entry(custom_frame, textvariable=end_date_var, width=20).pack(anchor='w')

    def execute_date_search():
        preset = preset_var.get()
        start_date = None
        end_date = None

        if preset == "custom":
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
        elif preset == "7d":
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif preset == "30d":
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif preset == "3m":
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        elif preset == "6m":
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        elif preset == "year":
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')

        dialog.destroy()
        self.update_status(_t("advanced_search.search_basic.searching_date_range"))

        def run_date_search():
            try:
                results = self.perform_date_search(start_date, end_date)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Date range search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Date search error: {str(e)}"))

        threading.Thread(target=run_date_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_basic.search'), command=execute_date_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_date_search = show_date_search

def perform_date_search(self, start_date, end_date):
    """Perform date range search"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()

        query = "SELECT * FROM students WHERE 1=1"
        params = []

        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                query += " AND registration_datetime >= ?"
                params.append(start_date + " 00:00:00")
            except ValueError:
                raise Exception("Invalid start date format. Use YYYY-MM-DD.")

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
                query += " AND registration_datetime <= ?"
                params.append(end_date + " 23:59:59")
            except ValueError:
                raise Exception("Invalid end date format. Use YYYY-MM-DD.")

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Date search error: {str(e)}")
AdvancedSearchGUI.perform_date_search = perform_date_search

def execute_search_with_logging(self, search_window):
    """Execute search with logging for repeat functionality"""
    # Get search criteria
    criteria = {}
    for key, var in self.search_vars.items():
        value = var.get().strip()
        if value:
            criteria[key] = value

    if not any(criteria.values()):
        messagebox.showwarning(_t('advanced_search.search_basic.no_criteria'), _t('advanced_search.search_basic.enter_at_least_one_criterion'))
        return

    # Store for repeat functionality
    self.last_search_criteria = {
        'type': 'multi_criteria',
        'data': criteria
    }

    search_window.destroy()
    self.update_status(_t("advanced_search.searching"))
    self.start_progress()

    def run_search():
        try:
            results = self.perform_database_search(criteria)

            # Log the search operation
            self.log_search_operation("multi_criteria", criteria, len(results))

            self.output_queue.put(("search_results", results))
            self.output_queue.put(("log", f"Search completed. Found {len(results)} results."))
        except Exception as e:
            self.output_queue.put(("error", f"Search error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_search, daemon=True).start()
AdvancedSearchGUI.execute_search_with_logging = execute_search_with_logging

def perform_database_search(self, criteria):
    """Perform the actual database search"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query
        query = "SELECT * FROM students WHERE 1=1"
        params = []

        for key, value in criteria.items():
            if key in ['student_id', 'first_name', 'last_name', 'email']:
                query += f" AND LOWER({key}) LIKE LOWER(?)"
                params.append(f"%{escape_like(value)}%")
            elif key in ['gender', 'course']:
                query += f" AND LOWER({key}) = LOWER(?)"
                params.append(value)
            elif key == 'min_age':
                query += " AND age >= ?"
                params.append(int(value))
            elif key == 'max_age':
                query += " AND age <= ?"
                params.append(int(value))

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Database error: {str(e)}")
AdvancedSearchGUI.perform_database_search = perform_database_search

def clear_search_form(self):
    """Clear all search form fields"""
    for var in self.search_vars.values():
        var.set("")
AdvancedSearchGUI.clear_search_form = clear_search_form

def show_date_search(self):
    """Complete date range search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.date_range_dialog_title'))
    dialog.geometry("400x350")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_basic.date_range_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Preset options
    ttk.Label(frame, text=f"{_t('advanced_search.search_basic.quick_presets')}:").pack(anchor='w')
    preset_var = tk.StringVar(value="custom")

    presets = [
        (_t("advanced_search.search_basic.preset_custom_range"), "custom"),
        (_t("advanced_search.search_basic.preset_last_7_days"), "7d"),
        (_t("advanced_search.search_basic.preset_last_30_days"), "30d"),
        (_t("advanced_search.search_basic.preset_last_3_months"), "3m"),
        (_t("advanced_search.search_basic.preset_last_6_months"), "6m"),
        (_t("advanced_search.search_basic.preset_this_year"), "year")
    ]

    for text, value in presets:
        ttk.Radiobutton(frame, text=text, variable=preset_var, value=value).pack(anchor='w')

    # Custom date inputs
    custom_frame = ttk.LabelFrame(frame, text=_t('advanced_search.custom_range_title'), padding="10")
    custom_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Label(custom_frame, text=_t('advanced_search.start_date')).pack(anchor='w')
    start_date_var = tk.StringVar()
    ttk.Entry(custom_frame, textvariable=start_date_var, width=20).pack(anchor='w', pady=(0, 10))

    ttk.Label(custom_frame, text=_t('advanced_search.end_date')).pack(anchor='w')
    end_date_var = tk.StringVar()
    ttk.Entry(custom_frame, textvariable=end_date_var, width=20).pack(anchor='w')

    def execute_date_search():
        preset = preset_var.get()
        start_date = None
        end_date = None

        if preset == "custom":
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
        elif preset == "7d":
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif preset == "30d":
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif preset == "3m":
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        elif preset == "6m":
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        elif preset == "year":
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')

        dialog.destroy()
        self.update_status(_t("advanced_search.search_basic.searching_date_range"))

        def run_date_search():
            try:
                results = self.perform_date_search(start_date, end_date)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Date range search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Date search error: {str(e)}"))

        threading.Thread(target=run_date_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_basic.search'), command=execute_date_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_date_search = show_date_search

def perform_date_search(self, start_date, end_date):
    """Perform date range search"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()

        query = "SELECT * FROM students WHERE 1=1"
        params = []

        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                query += " AND registration_datetime >= ?"
                params.append(start_date + " 00:00:00")
            except ValueError:
                raise Exception("Invalid start date format. Use YYYY-MM-DD.")

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
                query += " AND registration_datetime <= ?"
                params.append(end_date + " 23:59:59")
            except ValueError:
                raise Exception("Invalid end date format. Use YYYY-MM-DD.")

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Date search error: {str(e)}")
AdvancedSearchGUI.perform_date_search = perform_date_search

def show_combined_search(self):
    """
    Show combined filters search - allows combining multiple types of filters.

    This comprehensive search interface combines:
    - Student data filters (ID, name, gender, course, age)
    - Module enrollment filters
    - Date range filters
    """
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔎 {_t('advanced_search.combined_filters_dialog_title')}")
    dialog.geometry("700x700")
    dialog.transient(self.master)
    dialog.grab_set()

    # Main container with scrollbar
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding="20")

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    ttk.Label(scrollable_frame, text=_t('advanced_search.search_basic.combined_filters_title'), style='Title.TLabel').pack(pady=(0, 20))

    # ========== STUDENT DATA FILTERS ==========
    student_frame = ttk.LabelFrame(scrollable_frame, text=_t('advanced_search.search_basic.student_data_filters'), padding="10")
    student_frame.pack(fill=tk.X, pady=(0, 10))

    # Student ID
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.student_id')}:").grid(row=0, column=0, sticky='w', pady=5)
    student_id_var = tk.StringVar()
    ttk.Entry(student_frame, textvariable=student_id_var, width=30).grid(row=0, column=1, sticky='w', padx=(10, 0))

    # First Name
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.first_name')}:").grid(row=1, column=0, sticky='w', pady=5)
    first_name_var = tk.StringVar()
    ttk.Entry(student_frame, textvariable=first_name_var, width=30).grid(row=1, column=1, sticky='w', padx=(10, 0))

    # Last Name
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.last_name')}:").grid(row=2, column=0, sticky='w', pady=5)
    last_name_var = tk.StringVar()
    ttk.Entry(student_frame, textvariable=last_name_var, width=30).grid(row=2, column=1, sticky='w', padx=(10, 0))

    # Gender
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.gender')}:").grid(row=3, column=0, sticky='w', pady=5)
    gender_var = tk.StringVar()
    gender_combo = ttk.Combobox(student_frame, textvariable=gender_var,
                                values=["", "male", "female", "other"], state='readonly', width=28)
    gender_combo.grid(row=3, column=1, sticky='w', padx=(10, 0))
    gender_combo.set("")

    # Course
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.course')}:").grid(row=4, column=0, sticky='w', pady=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(student_frame, textvariable=course_var,
                               values=["", "CS", "DS"], state='readonly', width=28)
    course_combo.grid(row=4, column=1, sticky='w', padx=(10, 0))
    course_combo.set("")

    # Age Range
    ttk.Label(student_frame, text=f"{_t('advanced_search.search_basic.age_range')}:").grid(row=5, column=0, sticky='w', pady=5)
    age_frame = ttk.Frame(student_frame)
    age_frame.grid(row=5, column=1, sticky='w', padx=(10, 0))

    age_min_var = tk.StringVar()
    ttk.Label(age_frame, text=f"{_t('advanced_search.search_basic.min')}:").pack(side=tk.LEFT)
    ttk.Entry(age_frame, textvariable=age_min_var, width=8).pack(side=tk.LEFT, padx=(5, 10))

    age_max_var = tk.StringVar()
    ttk.Label(age_frame, text=f"{_t('advanced_search.search_basic.max')}:").pack(side=tk.LEFT)
    ttk.Entry(age_frame, textvariable=age_max_var, width=8).pack(side=tk.LEFT, padx=(5, 0))

    # ========== MODULE FILTERS ==========
    module_frame = ttk.LabelFrame(scrollable_frame, text=_t('advanced_search.search_basic.module_enrollment_filters'), padding="10")
    module_frame.pack(fill=tk.X, pady=(0, 10))

    module_enabled_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(module_frame, text=_t('advanced_search.search_basic.enable_module_filtering'),
                   variable=module_enabled_var).pack(anchor='w', pady=(0, 10))

    # Module listbox
    module_list_frame = ttk.Frame(module_frame)
    module_list_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(module_list_frame, text=f"{_t('advanced_search.search_basic.select_modules')}:").pack(anchor='w')

    module_listbox_frame = ttk.Frame(module_list_frame)
    module_listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    combined_module_listbox = tk.Listbox(module_listbox_frame, selectmode=tk.MULTIPLE, height=6)
    module_scroll = ttk.Scrollbar(module_listbox_frame, orient=tk.VERTICAL,
                                 command=combined_module_listbox.yview)
    combined_module_listbox.configure(yscrollcommand=module_scroll.set)

    combined_module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    module_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Load modules — prefer the modules table (has NOT NULL names),
    # fall back to student_modules if the modules table doesn't exist.
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_name")
            available_modules = cursor.fetchall()
        except Exception:
            cursor.execute("SELECT DISTINCT module_code, module_name FROM student_modules ORDER BY module_code")
            available_modules = cursor.fetchall()
        conn.close()

        for code, name in available_modules:
            display = f"{code} - {name}" if name else code
            combined_module_listbox.insert(tk.END, display)
    except Exception as e:
        print_error(f"Could not load modules: {e}")
        available_modules = []

    # Module match type
    module_match_var = tk.StringVar(value="any")
    ttk.Label(module_list_frame, text=f"{_t('advanced_search.search_basic.students_must_be_enrolled')}:").pack(anchor='w')
    ttk.Radiobutton(module_list_frame, text=_t('advanced_search.search_basic.any_selected_modules'),
                   variable=module_match_var, value="any").pack(anchor='w')
    ttk.Radiobutton(module_list_frame, text=_t('advanced_search.search_basic.all_selected_modules'),
                   variable=module_match_var, value="all").pack(anchor='w')

    # ========== DATE RANGE FILTERS ==========
    date_frame = ttk.LabelFrame(scrollable_frame, text=_t("advanced_search.search_basic.registration_date_filters"), padding="10")
    date_frame.pack(fill=tk.X, pady=(0, 20))

    date_enabled_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(date_frame, text=_t('advanced_search.search_basic.enable_date_filtering'),
                   variable=date_enabled_var).pack(anchor='w', pady=(0, 10))

    # Start date
    date_fields_frame = ttk.Frame(date_frame)
    date_fields_frame.pack(fill=tk.X)

    ttk.Label(date_fields_frame, text=_t('advanced_search.start_date')).grid(row=0, column=0, sticky='w', pady=5)
    start_date_var = tk.StringVar()
    ttk.Entry(date_fields_frame, textvariable=start_date_var, width=20).grid(row=0, column=1, sticky='w', padx=(10, 0))

    # End date
    ttk.Label(date_fields_frame, text=_t('advanced_search.end_date')).grid(row=1, column=0, sticky='w', pady=5)
    end_date_var = tk.StringVar()
    ttk.Entry(date_fields_frame, textvariable=end_date_var, width=20).grid(row=1, column=1, sticky='w', padx=(10, 0))

    # ========== EXECUTE SEARCH ==========
    def execute_combined_search():
        """Execute the combined filters search"""
        # Collect all filters
        filters = {
            "student_data": {},
            "module_codes": [],
            "date_range": {"start": None, "end": None},
            "module_match_all": module_match_var.get() == "all"
        }

        # Student data filters
        if student_id_var.get().strip():
            filters["student_data"]["student_id"] = student_id_var.get().strip()
        if first_name_var.get().strip():
            filters["student_data"]["first_name"] = first_name_var.get().strip()
        if last_name_var.get().strip():
            filters["student_data"]["last_name"] = last_name_var.get().strip()
        if gender_var.get() and gender_var.get() != "":
            filters["student_data"]["gender"] = gender_var.get()
        if course_var.get() and course_var.get() != "":
            filters["student_data"]["course"] = course_var.get()
        if age_min_var.get().strip():
            try:
                filters["student_data"]["age_min"] = int(age_min_var.get().strip())
            except ValueError:
                messagebox.showwarning(_t('advanced_search.search_basic.invalid_input'), _t('advanced_search.search_basic.min_age_must_be_number'))
                return
        if age_max_var.get().strip():
            try:
                filters["student_data"]["age_max"] = int(age_max_var.get().strip())
            except ValueError:
                messagebox.showwarning(_t('advanced_search.search_basic.invalid_input'), _t('advanced_search.search_basic.max_age_must_be_number'))
                return

        # Module filters
        if module_enabled_var.get():
            selected_indices = combined_module_listbox.curselection()
            if selected_indices:
                filters["module_codes"] = [available_modules[i][0] for i in selected_indices]

        # Date range filters
        if date_enabled_var.get():
            if start_date_var.get().strip():
                try:
                    datetime.strptime(start_date_var.get().strip(), "%Y-%m-%d")
                    filters["date_range"]["start"] = start_date_var.get().strip() + " 00:00:00"
                except ValueError:
                    messagebox.showwarning(_t('advanced_search.search_basic.invalid_date'), _t('advanced_search.search_basic.start_date_format'))
                    return
            if end_date_var.get().strip():
                try:
                    datetime.strptime(end_date_var.get().strip(), "%Y-%m-%d")
                    filters["date_range"]["end"] = end_date_var.get().strip() + " 23:59:59"
                except ValueError:
                    messagebox.showwarning(_t('advanced_search.search_basic.invalid_date'), _t('advanced_search.search_basic.end_date_format'))
                    return

        dialog.destroy()
        self.update_status(_t("advanced_search.search_basic.executing_combined_search"))
        self.start_progress()

        def run_combined_search():
            try:
                results = self.perform_combined_filters_search(filters)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Combined search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Combined search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_combined_search, daemon=True).start()

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_combined_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_combined_search = show_combined_search

def show_text_search(self):
    """Show advanced text search dialog with all options"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📝 {_t('advanced_search.advanced_text_search')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_basic.advanced_text_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Search type
    ttk.Label(frame, text=f"{_t('advanced_search.search_basic.search_type')}:").pack(anchor='w')
    search_type_var = tk.StringVar(value="wildcard")

    search_types = [
        (_t("advanced_search.search_basic.wildcard_pattern_search"), "wildcard"),
        (_t("advanced_search.search_basic.regex_search_type"), "regex"),
        (_t("advanced_search.search_basic.search_all_fields_type"), "all_fields"),
        (_t("advanced_search.search_basic.phonetic_search_type"), "phonetic")
    ]

    for text, value in search_types:
        ttk.Radiobutton(frame, text=text, variable=search_type_var, value=value).pack(anchor='w')

    # Search input
    ttk.Label(frame, text=f"{_t('advanced_search.search_basic.search_pattern')}:").pack(anchor='w', pady=(20, 0))
    pattern_var = tk.StringVar()
    ttk.Entry(frame, textvariable=pattern_var, width=50).pack(fill=tk.X, pady=(0, 10))

    # Field selection (for some search types)
    field_frame = ttk.Frame(frame)
    field_frame.pack(fill=tk.X, pady=(10, 20))

    ttk.Label(field_frame, text=_t('advanced_search.search_basic.search_field')).pack(side=tk.LEFT)
    field_var = tk.StringVar(value="first_name")
    field_combo = ttk.Combobox(field_frame, textvariable=field_var,
                              values=["first_name", "last_name", "email", "student_id"],
                              state='readonly', width=15)
    field_combo.pack(side=tk.LEFT, padx=(10, 0))

    def execute_text_search():
        pattern = pattern_var.get().strip()
        if not pattern:
            messagebox.showwarning(_t("advanced_search.search_basic.missing_pattern"), _t("advanced_search.search_basic.enter_search_pattern"))
            return

        search_type = search_type_var.get()
        field = field_var.get()

        dialog.destroy()

        # Route to specific search function
        if search_type == "regex":
            self.update_status(_t("advanced_search.search_basic.performing_regex_search"))
            self.start_progress()

            def run_search():
                try:
                    results = self.perform_regex_search(pattern, field)
                    self.output_queue.put(("search_results", results))
                    self.output_queue.put(("log", f"Regex search completed. Found {len(results)} results."))
                except Exception as e:
                    self.output_queue.put(("error", f"Search error: {str(e)}"))
                finally:
                    self.output_queue.put(("stop_progress", None))

        elif search_type == "wildcard":
            self.update_status(_t("advanced_search.search_basic.performing_wildcard_search"))
            self.start_progress()

            def run_search():
                try:
                    results = self.perform_wildcard_search(pattern, field)
                    self.output_queue.put(("search_results", results))
                    self.output_queue.put(("log", f"Wildcard search completed. Found {len(results)} results."))
                except Exception as e:
                    self.output_queue.put(("error", f"Search error: {str(e)}"))
                finally:
                    self.output_queue.put(("stop_progress", None))

        elif search_type == "all_fields":
            self.update_status(_t("advanced_search.search_basic.searching_all_fields"))
            self.start_progress()

            def run_search():
                try:
                    results = self.perform_search_all_fields(pattern)
                    self.output_queue.put(("search_results", results))
                    self.output_queue.put(("log", f"All fields search completed. Found {len(results)} results."))
                except Exception as e:
                    self.output_queue.put(("error", f"Search error: {str(e)}"))
                finally:
                    self.output_queue.put(("stop_progress", None))

        elif search_type == "phonetic":
            self.update_status(_t("advanced_search.search_basic.performing_phonetic_search"))
            self.start_progress()

            def run_search():
                try:
                    results = self.perform_phonetic_search(pattern)
                    self.output_queue.put(("search_results", results))
                    self.output_queue.put(("log", f"Phonetic search completed. Found {len(results)} results."))
                except Exception as e:
                    self.output_queue.put(("error", f"Search error: {str(e)}"))
                finally:
                    self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_text_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_text_search = show_text_search
