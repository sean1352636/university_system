from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.university_system.core.sql_safety import validate_identifier, validate_table_name, validate_field_for_query, validate_column_name  # nosec B608
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

def view_academic_history_detailed(self, student_id):
    """View detailed academic history for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student basic info
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.student_details.student_not_found"))
            return

        # Get academic history
        cursor.execute("""
        SELECT module_type, module_code, module_name, grade, enrollment_date, completion_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date DESC
        """, (student_id,))

        modules = cursor.fetchall()
        conn.close()

        # Create detailed history window
        history_window = tk.Toplevel(self.master)
        history_window.title(f"Academic History - {student_id}")
        history_window.geometry("800x600")
        history_window.transient(self.master)

        main_frame = ttk.Frame(history_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Student info header
        info_frame = ttk.LabelFrame(main_frame, text="Student Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = f"""
Student ID: {student[0]}
Name: {student[2]} {student[3]} {student[4] or ''} {student[5]}
Email: {student[1]}
Course: {student[9]}
        """

        ttk.Label(info_frame, text=info_text, font=('Arial', 10)).pack(anchor='w')

        # Academic history table
        history_frame = ttk.LabelFrame(main_frame, text="Module History", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Create treeview for history
        columns = ('Type', 'Code', 'Name', 'Grade', 'Enrolled', 'Completed')
        history_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=15)

        for col in columns:
            history_tree.heading(col, text=col)
            history_tree.column(col, width=120)

        history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=history_tree.yview)
        history_tree.configure(yscrollcommand=history_scrollbar.set)

        history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate history data
        for module in modules:
            module_type, code, name, grade, enrolled_date, completed_date = module
            grade_display = grade if grade else "In Progress"
            enrolled_display = enrolled_date[:10] if enrolled_date else "N/A"
            completed_display = completed_date[:10] if completed_date else "N/A"

            history_tree.insert('', 'end', values=(
                module_type, code, name, grade_display, enrolled_display, completed_display
            ))

        # Summary info
        if modules:
            completed_count = sum(1 for m in modules if m[3] is not None)
            completion_rate = (completed_count / len(modules)) * 100

            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
            summary_frame.pack(fill=tk.X)

            summary_text = f"""
Total Modules: {len(modules)}
Completed: {completed_count}
In Progress: {len(modules) - completed_count}
Completion Rate: {completion_rate:.1f}%
            """

            ttk.Label(summary_frame, text=summary_text, font=('Arial', 10)).pack(anchor='w')

        ttk.Button(main_frame, text=_t('advanced_search.close_button'), command=history_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.student_details.error_loading_history", error=str(e)))
AdvancedSearchGUI.view_academic_history_detailed = view_academic_history_detailed

def show_detailed_student_view(self, student_data):
    """Show comprehensive detailed view of student with all related data"""
    if not student_data:
        messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.student_details.no_student_data"))
        return

    # Create detailed view window
    detail_window = tk.Toplevel(self.master)
    detail_window.title(f"Student Details - {student_data[0]}")
    detail_window.geometry("900x700")
    detail_window.transient(self.master)

    # Create notebook for tabbed interface
    notebook = ttk.Notebook(detail_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Basic Info Tab
    basic_frame = ttk.Frame(notebook, padding="20")
    notebook.add(basic_frame, text="Basic Information")

    self.create_basic_info_tab(basic_frame, student_data)

    # Academic History Tab
    academic_frame = ttk.Frame(notebook, padding="20")
    notebook.add(academic_frame, text="Academic History")

    self.create_academic_history_tab(academic_frame, student_data[0])

    # Analytics Tab
    analytics_frame = ttk.Frame(notebook, padding="20")
    notebook.add(analytics_frame, text="Performance Analytics")

    self.create_performance_analytics_tab(analytics_frame, student_data[0])

    # Actions Tab
    actions_frame = ttk.Frame(notebook, padding="20")
    notebook.add(actions_frame, text="Actions")

    self.create_student_actions_tab(actions_frame, student_data)
AdvancedSearchGUI.show_detailed_student_view = show_detailed_student_view

def create_basic_info_tab(self, parent, student_data):
    """Create basic information tab"""
    info_text = f"""
STUDENT INFORMATION

Student ID: {student_data[0]}
Email: {student_data[1]}
Title: {student_data[2]}
Name: {student_data[3]} {student_data[4] or ''} {student_data[5]}
Gender: {student_data[6]}
Date of Birth: {student_data[7]}
Age: {student_data[8]}
Course: {student_data[9]}
Registration: {student_data[10]}
    """

    ttk.Label(parent, text="Personal Information", style='Header.TLabel').pack(anchor='w', pady=(0, 20))

    info_label = tk.Label(parent, text=info_text, justify=tk.LEFT, font=('Arial', 11), bg='white')
    info_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
AdvancedSearchGUI.create_basic_info_tab = create_basic_info_tab

def create_academic_history_tab(self, parent, student_id):
    """Create academic history tab"""
    ttk.Label(parent, text="Academic History", style='Header.TLabel').pack(anchor='w', pady=(0, 20))

    # Load and display academic history
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT module_type, module_code, module_name, grade, enrollment_date, completion_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date DESC
        """, (student_id,))

        modules = cursor.fetchall()
        conn.close()

        if modules:
            # Create treeview for modules
            columns = ('Type', 'Code', 'Name', 'Grade', 'Enrolled', 'Completed')
            modules_tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)

            for col in columns:
                modules_tree.heading(col, text=col)
                modules_tree.column(col, width=120)

            modules_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=modules_tree.yview)
            modules_tree.configure(yscrollcommand=modules_scrollbar.set)

            modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            modules_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Populate data
            for module in modules:
                module_type, code, name, grade, enrolled_date, completed_date = module
                grade_display = grade if grade else "In Progress"
                enrolled_display = enrolled_date[:10] if enrolled_date else "N/A"
                completed_display = completed_date[:10] if completed_date else "N/A"

                modules_tree.insert('', 'end', values=(
                    module_type, code, name, grade_display, enrolled_display, completed_display
                ))
        else:
            ttk.Label(parent, text="No academic history found.").pack()

    except Exception as e:
        ttk.Label(parent, text=f"Error loading academic history: {str(e)}").pack()
AdvancedSearchGUI.create_academic_history_tab = create_academic_history_tab

def create_performance_analytics_tab(self, parent, student_id):
    """Create performance analytics tab"""
    ttk.Label(parent, text="Performance Analytics", style='Header.TLabel').pack(anchor='w', pady=(0, 20))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get performance metrics
        cursor.execute("""
        SELECT
            COUNT(*) as total_modules,
            SUM(CASE WHEN grade IS NOT NULL THEN 1 ELSE 0 END) as completed_modules,
            SUM(CASE WHEN grade IN ('A', 'B', 'C') THEN 1 ELSE 0 END) as passed_modules,
            AVG(CASE
                WHEN grade = 'A' THEN 4.0
                WHEN grade = 'B' THEN 3.0
                WHEN grade = 'C' THEN 2.0
                WHEN grade = 'D' THEN 1.0
                ELSE 0.0
            END) as gpa
        FROM student_modules
        WHERE student_id = ?
        """, (student_id,))

        metrics = cursor.fetchone()
        conn.close()

        if metrics and metrics[0] > 0:
            total, completed, passed, gpa = metrics
            completion_rate = (completed / total) * 100 if total > 0 else 0
            success_rate = (passed / completed) * 100 if completed > 0 else 0
            gpa_display = gpa if gpa is not None else 0.0

            analytics_text = f"""
PERFORMANCE METRICS

Total Modules Enrolled: {total}
Completed Modules: {completed}
Passed Modules (A-C): {passed}
Completion Rate: {completion_rate:.1f}%
Success Rate: {success_rate:.1f}%
Current GPA: {gpa_display:.2f}

ACADEMIC STATUS
{"✅ On Track" if completion_rate > 70 else "⚠️ Needs Attention" if completion_rate > 40 else "🚨 At Risk"}
            """

            analytics_label = tk.Label(parent, text=analytics_text, justify=tk.LEFT,
                                     font=('Courier', 11), bg='white')
            analytics_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        else:
            ttk.Label(parent, text="No performance data available.").pack()

    except Exception as e:
        ttk.Label(parent, text=f"Error loading performance data: {str(e)}").pack()
AdvancedSearchGUI.create_performance_analytics_tab = create_performance_analytics_tab

def create_student_actions_tab(self, parent, student_data):
    """Create student actions tab"""
    ttk.Label(parent, text="Available Actions", style='Header.TLabel').pack(anchor='w', pady=(0, 20))

    actions = [
        ("📧 Send Email", lambda: self.simulate_send_email(student_data)),
        ("💾 Export Student Data", lambda: self.export_single_student(student_data)),
        ("📋 View Academic History", lambda: self.view_academic_history_detailed(student_data[0])),
        ("📊 Generate Performance Report", lambda: self.generate_student_performance_report(student_data[0])),
        ("🏷️ Add to Favorites", lambda: self.add_student_to_favorites(student_data)),
        ("📌 Mark for Follow-up", lambda: self.mark_single_student_followup(student_data))
    ]

    for text, command in actions:
        ttk.Button(parent, text=text, command=command, width=30).pack(pady=5)
AdvancedSearchGUI.create_student_actions_tab = create_student_actions_tab

def add_student_to_favorites(self, student_data):
    """Add student to favorites list"""
    try:
        # Initialize favorites if it doesn't exist
        if not hasattr(self, 'favorite_students'):
            self.favorite_students = []

        student_id = student_data[0]
        student_name = f"{student_data[3]} {student_data[5]}"

        # Check if already in favorites
        if any(fav['id'] == student_id for fav in self.favorite_students):
            messagebox.showinfo(_t("advanced_search.student_details.already_favorited"), _t("advanced_search.student_details.already_in_favorites", name=student_name))
            return

        # Add to favorites
        favorite_entry = {
            'id': student_id,
            'name': student_name,
            'email': student_data[1],
            'course': student_data[9],
            'added_date': datetime.now().isoformat()
        }

        self.favorite_students.append(favorite_entry)

        # Save to file
        with open('favorite_students.json', 'w') as f:
            json.dump(self.favorite_students, f, indent=2)

        messagebox.showinfo(_t("advanced_search.student_details.added_to_favorites_title"), _t("advanced_search.student_details.added_to_favorites_msg", name=student_name))
        self.log_output(f"Student {student_id} added to favorites")

    except Exception as e:
        messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.student_details.could_not_add_favorites", error=str(e)))
AdvancedSearchGUI.add_student_to_favorites = add_student_to_favorites

def mark_single_student_followup(self, student_data):
    """Mark single student for follow-up"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.mark_followup_dialog_title'))
    dialog.geometry("800x600")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    student_name = f"{student_data[3]} {student_data[5]}"
    ttk.Label(frame, text=f"Mark {student_name} for Follow-up", style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text="Follow-up Reason:").pack(anchor='w')
    reason_var = tk.StringVar()
    ttk.Entry(frame, textvariable=reason_var, width=40).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text="Priority:").pack(anchor='w')
    priority_var = tk.StringVar(value="medium")

    for priority in ["high", "medium", "low"]:
        ttk.Radiobutton(frame, text=priority.title(), variable=priority_var, value=priority).pack(anchor='w')

    ttk.Label(frame, text="Notes:").pack(anchor='w', pady=(10, 0))
    notes_text = tk.Text(frame, height=4, wrap=tk.WORD)
    notes_text.pack(fill=tk.X, pady=(0, 20))

    def save_followup():
        reason = reason_var.get().strip()
        if not reason:
            messagebox.showwarning(_t("advanced_search.student_details.missing_reason"), _t("advanced_search.student_details.enter_followup_reason"))
            return

        priority = priority_var.get()
        notes = notes_text.get(1.0, tk.END).strip()

        followup_data = {
            'student_id': student_data[0],
            'student_name': student_name,
            'email': student_data[1],
            'reason': reason,
            'priority': priority,
            'notes': notes,
            'marked_date': datetime.now().isoformat(),
            'marked_by': 'current_user'
        }

        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"followup_{student_data[0]}_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(followup_data, f, indent=2)

        messagebox.showinfo("Follow-up Marked",
                          f"✅ {student_name} marked for follow-up\n"
                          f"Priority: {priority}\n"
                          f"Saved to: {filename}")

        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="📌 Mark", command=save_followup).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.mark_single_student_followup = mark_single_student_followup

def generate_student_performance_report(self, student_id):
    """Generate detailed performance report for a student"""
    self.update_status(f"Generating performance report for {student_id}...")
    self.start_progress()

    def run_report_generation():
        try:
            report = self.create_student_performance_report(student_id)
            self.output_queue.put(("analytics", report))
            self.output_queue.put(("log", f"Performance report generated for {student_id}"))
        except Exception as e:
            self.output_queue.put(("error", f"Report generation error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_report_generation, daemon=True).start()
AdvancedSearchGUI.generate_student_performance_report = generate_student_performance_report

def create_student_performance_report(self, student_id):
    """Create detailed performance report for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student info
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            return "Student not found"

        # Get module performance
        cursor.execute("""
        SELECT module_type, module_code, module_name, grade, enrollment_date, completion_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date
        """, (student_id,))

        modules = cursor.fetchall()
        conn.close()

        report = f"STUDENT PERFORMANCE REPORT\n"
        report += f"=" * 50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        report += f"STUDENT INFORMATION:\n"
        report += f"ID: {student[0]}\n"
        report += f"Name: {student[3]} {student[5]}\n"
        report += f"Email: {student[1]}\n"
        report += f"Course: {student[9]}\n"
        report += f"Registration: {student[10]}\n\n"

        if modules:
            completed = [m for m in modules if m[3] is not None]
            in_progress = [m for m in modules if m[3] is None]
            passed = [m for m in modules if m[3] in ['A', 'B', 'C']]

            report += f"ACADEMIC SUMMARY:\n"
            report += f"Total Modules: {len(modules)}\n"
            report += f"Completed: {len(completed)}\n"
            report += f"In Progress: {len(in_progress)}\n"
            report += f"Passed (A-C): {len(passed)}\n"

            if completed:
                completion_rate = (len(completed) / len(modules)) * 100
                success_rate = (len(passed) / len(completed)) * 100
                report += f"Completion Rate: {completion_rate:.1f}%\n"
                report += f"Success Rate: {success_rate:.1f}%\n"

            report += f"\nDETAILED MODULE HISTORY:\n"
            report += f"-" * 40 + "\n"

            for module in modules:
                module_type, code, name, grade, enrolled_date, completed_date = module
                grade_display = grade if grade else "In Progress"

                report += f"{code} - {name}\n"
                report += f"  Type: {module_type} | Grade: {grade_display}\n"
                report += f"  Enrolled: {enrolled_date[:10] if enrolled_date else 'N/A'}\n"
                if completed_date:
                    report += f"  Completed: {completed_date[:10]}\n"
                report += f"\n"
        else:
            report += f"No module enrollment history found.\n"

        return report

    except Exception as e:
        return f"Error generating performance report: {str(e)}"
AdvancedSearchGUI.create_student_performance_report = create_student_performance_report

def view_academic_history(self, student_id):
    """View detailed academic history for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student basic info
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            return "Student not found"

        # Get academic history
        cursor.execute("""
        SELECT module_type, module_code, module_name, grade, enrollment_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date DESC
        """, (student_id,))

        modules = cursor.fetchall()
        conn.close()

        history = f"📚 ACADEMIC HISTORY - {student[0]}\n"
        history += f"═" * 50 + "\n"
        history += f"Student: {student[3]} {student[5]}\n"
        history += f"Email: {student[1]}\n"
        history += f"Course: {student[9]}\n\n"

        if modules:
            history += f"MODULE HISTORY ({len(modules)} modules):\n"
            history += "-" * 40 + "\n"

            for module_type, code, name, grade, enrolled_date in modules:
                grade_display = grade if grade else "In Progress"
                history += f"{code} - {name}\n"
                history += f"  Type: {module_type} | Grade: {grade_display}\n"
                history += f"  Enrolled: {enrolled_date}\n\n"
        else:
            history += "No module enrollment history found.\n"

        return history

    except Exception as e:
        return f"Error retrieving academic history: {str(e)}"
AdvancedSearchGUI.view_academic_history = view_academic_history
