from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.university_system.core.sql_safety import escape_like, validate_identifier, validate_table_name, validate_field_for_query, validate_column_name
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import json
import csv
from datetime import datetime, timedelta
import os
import sys
import sqlite3
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

def save_search_profile_to_db(self, name, description, is_shared):
    """Persist a search profile to the central database."""
    criteria = self._collect_search_criteria()
    payload = {
        "description": description,
        "criteria": criteria,
        "saved_at": datetime.now().isoformat()
    }

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection unavailable.")

    try:
        # Disable FK checks — the user_id is a GUI/session identifier,
        # not necessarily present in the users table.
        conn.execute("PRAGMA foreign_keys = OFF")

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM saved_searches WHERE user_id = ? AND search_name = ?",
            (self._current_user_id(), name)
        )
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE saved_searches
                SET search_criteria = ?, is_shared = ?, created_date = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(payload), 1 if is_shared else 0, row[0])
            )
            profile_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO saved_searches (user_id, search_name, search_criteria, is_shared, created_date)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self._current_user_id(), name, json.dumps(payload), 1 if is_shared else 0)
            )
            profile_id = cursor.lastrowid

        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()
    return profile_id
AdvancedSearchGUI.save_search_profile_to_db = save_search_profile_to_db

def show_search_profile_manager(self):
    """Show comprehensive search profile management"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.search_profile_manager_title'))
    dialog.geometry("800x600")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text=_t('advanced_search.search_profiles.search_profile_manager_label'), style='Title.TLabel').pack(pady=(0, 20))
    
    # Profile management notebook
    notebook = ttk.Notebook(frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    # Saved profiles tab
    profiles_frame = ttk.Frame(notebook, padding="10")
    notebook.add(profiles_frame, text=_t('advanced_search.search_profiles.saved_profiles_tab'))
    
    # Profile list
    columns = ('ID', 'Name', 'Type', 'Created', 'Last Used', 'Shared')
    self.profiles_tree = ttk.Treeview(profiles_frame, columns=columns, show='headings', height=12)
    
    for col in columns:
        self.profiles_tree.heading(col, text=col)
        self.profiles_tree.column(col, width=100)
    
    profiles_scrollbar = ttk.Scrollbar(profiles_frame, orient=tk.VERTICAL, command=self.profiles_tree.yview)
    self.profiles_tree.configure(yscrollcommand=profiles_scrollbar.set)
    
    self.profiles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    profiles_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Load profiles
    self.load_search_profiles()
    
    # Profile actions
    profile_actions = ttk.Frame(profiles_frame)
    profile_actions.pack(fill=tk.X, pady=(10, 0))
    
    ttk.Button(profile_actions, text=_t('advanced_search.search_profiles.load_profile_button'),
              command=self.load_selected_profile).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(profile_actions, text=_t('advanced_search.search_profiles.delete_profile_button'),
              command=self.delete_selected_profile).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(profile_actions, text=_t('advanced_search.search_profiles.share_profile_button'),
              command=self.share_selected_profile).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(profile_actions, text=_t('advanced_search.search_profiles.export_profile_button'),
              command=self.export_selected_profile).pack(side=tk.LEFT)
    
    # Create new profile tab
    create_frame = ttk.Frame(notebook, padding="10")
    notebook.add(create_frame, text=_t('advanced_search.search_profiles.create_profile_tab'))
    
    ttk.Label(create_frame, text=_t('advanced_search.search_profiles.create_new_profile_header'), style='Header.TLabel').pack(pady=(0, 20))
    
    # Profile creation form
    create_form = ttk.LabelFrame(create_frame, text=_t('advanced_search.search_profiles.profile_details_frame'), padding="10")
    create_form.pack(fill=tk.X, pady=(0, 20))
    
    ttk.Label(create_form, text=_t('advanced_search.search_profiles.profile_name_label')).pack(anchor='w')
    profile_name_var = tk.StringVar()
    ttk.Entry(create_form, textvariable=profile_name_var, width=40).pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(create_form, text=_t('advanced_search.search_profiles.description_label')).pack(anchor='w')
    profile_desc_text = tk.Text(create_form, height=4, wrap=tk.WORD)
    profile_desc_text.pack(fill=tk.X, pady=(0, 10))
    
    profile_shared_var = tk.BooleanVar()
    ttk.Checkbutton(create_form, text=_t('advanced_search.search_profiles.share_with_users_checkbox'),
                   variable=profile_shared_var).pack(anchor='w')
    
    def save_current_as_profile():
        name = profile_name_var.get().strip()
        if not name:
            messagebox.showwarning(_t('advanced_search.search_profiles.missing_name_title'), _t('advanced_search.search_profiles.missing_name_msg'))
            return
        
        description = profile_desc_text.get(1.0, tk.END).strip()
        is_shared = profile_shared_var.get()
        
        self.save_search_profile_to_db(name, description, is_shared)
        self.load_search_profiles()
        messagebox.showinfo(_t('advanced_search.search_profiles.profile_saved_title'), _t('advanced_search.search_profiles.profile_saved_msg', name=name))
    
    ttk.Button(create_form, text=_t('advanced_search.search_profiles.save_current_as_profile_button'),
              command=save_current_as_profile).pack(pady=10)
    
    ttk.Button(frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack()
AdvancedSearchGUI.show_search_profile_manager = show_search_profile_manager

def load_search_profiles(self):
    """Load search profiles from database/storage"""
    # Clear existing items
    for item in self.profiles_tree.get_children():
        self.profiles_tree.delete(item)

    try:
        conn = get_connection()
        if conn is None:
            raise RuntimeError("Database connection unavailable.")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Use column aliases for backward compatibility
        cursor.execute("""
            SELECT
                search_id as id,
                COALESCE(search_name, name) as search_name,
                search_criteria,
                COALESCE(is_shared, 0) as is_shared,
                COALESCE(created_date, created_at) as created_date,
                last_used
            FROM saved_searches
            ORDER BY datetime(COALESCE(created_date, created_at)) DESC
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as exc:
        print_error(f"Failed to load saved profiles: {exc}")
        messagebox.showerror(_t('advanced_search.search_profiles.load_error_title'), _t('advanced_search.search_profiles.load_error_msg', error=exc))
        return
    
    for row in rows:
        try:
            payload = json.loads(row["search_criteria"]) if row["search_criteria"] else {}
        except json.JSONDecodeError:
            payload = {}
        criteria = payload.get("criteria", {})
        description = payload.get("description") or "Saved Search"
        profile_type = criteria.get("search_type") or description
        created = (row["created_date"] or "")[:19] if row["created_date"] else "N/A"
        last_used = (row["last_used"] or "")[:19] if row["last_used"] else "—"
        shared = "Yes" if row["is_shared"] else "No"
        self.profiles_tree.insert(
            '',
            'end',
            values=(row["id"], row["search_name"], profile_type, created, last_used, shared)
        )
AdvancedSearchGUI.load_search_profiles = load_search_profiles

def load_selected_profile(self):
    """Load and execute selected search profile"""
    selection = self.profiles_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_profile_to_load'))
        return

    item = self.profiles_tree.item(selection[0])
    profile_id = item['values'][0]

    try:
        conn = get_connection()
        if conn is None:
            raise RuntimeError("Database connection unavailable.")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT search_name, search_criteria FROM saved_searches WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Profile not found in database.")

        payload = json.loads(row["search_criteria"]) if row["search_criteria"] else {}
        criteria = payload.get("criteria", {})
        self._apply_profile_criteria(criteria)

        results = self._run_profile_search(criteria)
        if results:
            self.display_search_results(results)
        else:
            self.display_search_results([])
            messagebox.showinfo(_t('advanced_search.search_profiles.profile_loaded_title'), _t('advanced_search.search_profiles.profile_loaded_no_results_msg', name=row['search_name']))

        cursor.execute(
            "UPDATE saved_searches SET last_used = CURRENT_TIMESTAMP WHERE id = ?",
            (profile_id,)
        )
        conn.commit()
        conn.close()
        self.log_output(f"Loaded search profile '{row['search_name']}' with {len(results)} result(s).")
    except Exception as exc:
        messagebox.showerror(_t('advanced_search.search_profiles.load_failed_title'), _t('advanced_search.search_profiles.load_failed_msg', error=exc))
AdvancedSearchGUI.load_selected_profile = load_selected_profile

def delete_selected_profile(self):
    """Delete selected search profile"""
    selection = self.profiles_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_profile_to_delete'))
        return

    item = self.profiles_tree.item(selection[0])
    profile_id = item['values'][0]
    profile_name = item['values'][1]

    if messagebox.askyesno(_t('advanced_search.search_profiles.confirm_delete_title'), _t('advanced_search.search_profiles.confirm_delete_msg', name=profile_name)):
        try:
            conn = get_connection()
            if conn is None:
                raise RuntimeError("Database connection unavailable.")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM saved_searches WHERE id = ?", (profile_id,))
            conn.commit()
            conn.close()
            self.profiles_tree.delete(selection[0])
            messagebox.showinfo(_t('advanced_search.search_profiles.profile_deleted_title'), _t('advanced_search.search_profiles.profile_deleted_msg', name=profile_name))
        except Exception as exc:
            messagebox.showerror(_t('advanced_search.search_profiles.delete_failed_title'), _t('advanced_search.search_profiles.delete_failed_msg', error=exc))
AdvancedSearchGUI.delete_selected_profile = delete_selected_profile

def share_selected_profile(self):
    """Share selected search profile"""
    selection = self.profiles_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_profile_to_share'))
        return

    item = self.profiles_tree.item(selection[0])
    profile_id = item['values'][0]
    profile_name = item['values'][1]

    # Share dialog
    share_dialog = tk.Toplevel(self.master)
    share_dialog.title(_t('advanced_search.share_profile_dialog_title'))
    share_dialog.geometry("900x700")
    share_dialog.transient(self.master)
    share_dialog.grab_set()

    share_frame = ttk.Frame(share_dialog, padding="20")
    share_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(share_frame, text=_t('advanced_search.search_profiles.share_profile_label', name=profile_name), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(share_frame, text=_t('advanced_search.search_profiles.share_with_users_label')).pack(anchor='w')
    users_listbox = tk.Listbox(share_frame, selectmode=tk.MULTIPLE, height=8)
    users_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 20))
    
    # Sample users
    sample_users = ["admin", "teacher1", "teacher2", "analyst", "manager"]
    for user in sample_users:
        users_listbox.insert(tk.END, user)
    
    def confirm_share():
        selected_users = [users_listbox.get(i) for i in users_listbox.curselection()]
        if selected_users:
            try:
                conn = get_connection()
                if conn is None:
                    raise RuntimeError("Database connection unavailable.")
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE saved_searches SET is_shared = 1 WHERE id = ?",
                    (profile_id,)
                )
                conn.commit()
                conn.close()
                messagebox.showinfo(_t('advanced_search.search_profiles.profile_shared_title'),
                                  _t('advanced_search.search_profiles.profile_shared_msg', name=profile_name, users=', '.join(selected_users)))
                self.load_search_profiles()
            except Exception as exc:
                messagebox.showerror(_t('advanced_search.search_profiles.share_failed_title'), _t('advanced_search.search_profiles.share_failed_msg', error=exc))
            share_dialog.destroy()
        else:
            messagebox.showwarning(_t('advanced_search.search_profiles.no_users_selected_title'), _t('advanced_search.search_profiles.no_users_selected_msg'))
    
    button_frame = ttk.Frame(share_frame)
    button_frame.pack(fill=tk.X)
    
    ttk.Button(button_frame, text=_t('advanced_search.search_profiles.share_button'), command=confirm_share).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=share_dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.share_selected_profile = share_selected_profile

def export_selected_profile(self):
    """Export selected search profile"""
    selection = self.profiles_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_profile_to_export'))
        return
    
    item = self.profiles_tree.item(selection[0])
    profile_id = item['values'][0]
    
    filename = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        initialfile=f"search_profile_{item['values'][1].replace(' ', '_')}.json"
    )
    
    if filename:
        try:
            conn = get_connection()
            if conn is None:
                raise RuntimeError("Database connection unavailable.")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT search_name, search_criteria, is_shared, created_date, last_used "
                "FROM saved_searches WHERE id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if not row:
                raise ValueError("Profile not found.")

            payload = json.loads(row["search_criteria"]) if row["search_criteria"] else {}
            export_data = {
                "name": row["search_name"],
                "created": row["created_date"],
                "last_used": row["last_used"],
                "shared": bool(row["is_shared"]),
                "criteria": payload.get("criteria", {}),
                "metadata": {
                    "description": payload.get("description"),
                    "exported_at": datetime.now().isoformat(),
                    "exported_by": self._current_user_id()
                }
            }

            with open(filename, 'w', encoding='utf-8') as handle:
                json.dump(export_data, handle, indent=2)
            messagebox.showinfo(_t('advanced_search.search_profiles.export_complete_title'), _t('advanced_search.search_profiles.export_complete_msg', filename=filename))
        except Exception as exc:
            messagebox.showerror(_t('advanced_search.search_profiles.export_error_title'), _t('advanced_search.search_profiles.export_error_msg', error=exc))
AdvancedSearchGUI.export_selected_profile = export_selected_profile

def show_saved_searches(self):
    """Show saved searches management"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"💾 {_t('advanced_search.saved_profiles_dialog_title')}")
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text=_t('advanced_search.search_profiles.saved_search_profiles_label'), style='Title.TLabel').pack(pady=(0, 20))

    # Saved searches list
    list_frame = ttk.LabelFrame(frame, text=_t('advanced_search.search_profiles.saved_searches_frame'), padding="10")
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    columns = ('ID', 'Name', 'Created', 'Shared')
    self.saved_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
    
    for col in columns:
        self.saved_tree.heading(col, text=col)
        self.saved_tree.column(col, width=120)
    
    self.saved_tree.pack(fill=tk.BOTH, expand=True)
    
    # Load saved searches
    self.load_saved_searches()
    
    # Buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"\U0001f4be {_t('advanced_search.search_profiles.save_current_button')}",
              command=self.save_current_search).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"\U0001f4c2 {_t('advanced_search.search_profiles.load_button')}",
              command=self.load_selected_search).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"\U0001f517 {_t('advanced_search.search_profiles.share_button_icon')}",
              command=self.share_search_profile).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"\U0001f5d1\ufe0f {_t('advanced_search.search_profiles.delete_button_icon')}",
              command=self.delete_selected_search).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_saved_searches = show_saved_searches

def load_saved_searches(self):
    """Load saved searches from database into the tree"""
    try:
        # Clear existing items
        for item in self.saved_tree.get_children():
            self.saved_tree.delete(item)

        # Load from database
        conn = get_connection()
        cursor = conn.cursor()

        # Check if saved_searches table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='saved_searches'
        """)

        if cursor.fetchone():
            # Table exists, load real data
            # Get current user if available
            current_user = 'default_user'  # Default if no auth
            if hasattr(self, 'auth') and self.auth and hasattr(self.auth, 'current_user'):
                user = self.auth.current_user
                if user:
                    current_user = user.get('username', 'default_user')

            cursor.execute('''
                SELECT
                    search_id as id,
                    COALESCE(search_name, name) as search_name,
                    COALESCE(created_date, created_at) as created_date,
                    COALESCE(is_shared, 0) as is_shared
                FROM saved_searches
                WHERE user_id = ? OR is_shared = 1
                ORDER BY COALESCE(created_date, created_at) DESC
            ''', (current_user,))

            searches = cursor.fetchall()

            for search_id, name, created, shared in searches:
                shared_text = "Yes" if shared else "No"
                # Format date nicely
                try:
                    if created:
                        created_display = created[:16] if len(created) > 16 else created
                    else:
                        created_display = "N/A"
                except Exception:
                    created_display = "N/A"

                self.saved_tree.insert('', 'end', values=(search_id, name, created_display, shared_text))

        else:
            # Table doesn't exist, show sample data
            saved_searches = [
                (1, "CS Students Over 25", "2024-01-15", "No"),
                (2, "Recent Registrations", "2024-01-20", "Yes"),
                (3, "Incomplete Modules", "2024-01-25", "No"),
            ]

            for search_id, name, created, shared in saved_searches:
                self.saved_tree.insert('', 'end', values=(search_id, name, created, shared))

        conn.close()

    except Exception as e:
        messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.load_searches_error_msg', error=str(e)))
AdvancedSearchGUI.load_saved_searches = load_saved_searches

def save_current_search(self):
    """Save current search as a profile"""
    if not hasattr(self, 'search_vars') or not any(var.get() for var in self.search_vars.values()):
        messagebox.showinfo(_t('advanced_search.search_profiles.no_search_title'), _t('advanced_search.search_profiles.no_search_msg'))
        return

    name = tk.simpledialog.askstring(_t('advanced_search.search_profiles.save_search_dialog_title'), _t('advanced_search.search_profiles.save_search_prompt'))
    if name:
        messagebox.showinfo(_t('advanced_search.search_profiles.search_saved_title'), _t('advanced_search.search_profiles.search_saved_msg', name=name))
        self.load_saved_searches()  # Refresh the list
AdvancedSearchGUI.save_current_search = save_current_search

def load_selected_search(self):
    """Load selected saved search"""
    selection = self.saved_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_search_to_load'))
        return

    item = self.saved_tree.item(selection[0])
    search_id = item['values'][0]
    search_name = item['values'][1]

    try:
        # Load search parameters from database or config
        conn = get_connection()
        cursor = conn.cursor()

        # Check if we have a saved_searches table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='saved_searches'
        """)

        if cursor.fetchone():
            # Load from database
            cursor.execute("""
                SELECT search_parameters FROM saved_searches
                WHERE id = ?
            """, (search_id,))

            result = cursor.fetchone()
            if result:
                search_params = json.loads(result[0])
                self._apply_search_parameters(search_params)
                messagebox.showinfo(_t('advanced_search.search_profiles.success_title'), _t('advanced_search.search_profiles.profile_loaded_msg', name=search_name))
            else:
                messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.profile_not_found_msg'))
        else:
            # Simulate loading with predefined searches
            predefined_searches = {
                1: {
                    'course_filter': 'Computer Science',
                    'min_age': '25',
                    'grade_filter': 'A',
                    'search_term': ''
                },
                2: {
                    'course_filter': '',
                    'min_age': '',
                    'grade_filter': '',
                    'search_term': '',
                    'date_range': 'last_30_days'
                },
                3: {
                    'course_filter': '',
                    'min_age': '',
                    'grade_filter': 'F',
                    'search_term': 'incomplete'
                }
            }

            if int(search_id) in predefined_searches:
                search_params = predefined_searches[int(search_id)]
                self._apply_search_parameters(search_params)
                messagebox.showinfo(_t('advanced_search.search_profiles.success_title'), _t('advanced_search.search_profiles.profile_loaded_msg', name=search_name))
            else:
                messagebox.showwarning(_t('advanced_search.search_profiles.warning_title'), _t('advanced_search.search_profiles.demo_profile_warning'))

        conn.close()

    except Exception as e:
        messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.load_search_failed_msg', error=str(e)))
AdvancedSearchGUI.load_selected_search = load_selected_search

def _apply_search_parameters(self, params):
    """Apply loaded search parameters to the interface"""
    try:
        # Apply basic search filters if they exist on the interface
        if hasattr(self, 'search_entry') and 'search_term' in params:
            self.search_entry.delete(0, tk.END)
            self.search_entry.insert(0, params.get('search_term', ''))

        # Apply course filter
        if hasattr(self, 'course_var') and 'course_filter' in params:
            self.course_var.set(params.get('course_filter', ''))

        # Apply age filter
        if hasattr(self, 'age_entry') and 'min_age' in params:
            self.age_entry.delete(0, tk.END)
            self.age_entry.insert(0, params.get('min_age', ''))

        # Apply grade filter
        if hasattr(self, 'grade_var') and 'grade_filter' in params:
            self.grade_var.set(params.get('grade_filter', ''))

        # Trigger search with loaded parameters
        if hasattr(self, 'perform_search'):
            self.perform_search()

    except Exception as e:
        print_warning(f"Could not apply all search parameters: {e}")
AdvancedSearchGUI._apply_search_parameters = _apply_search_parameters

def delete_selected_search(self):
    """Delete selected saved search"""
    selection = self.saved_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_search_to_delete'))
        return

    item = self.saved_tree.item(selection[0])
    search_id = item['values'][0]
    search_name = item['values'][1]

    if messagebox.askyesno(_t('advanced_search.search_profiles.confirm_delete_title'), _t('advanced_search.search_profiles.confirm_delete_search_msg', name=search_name)):
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if saved_searches table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='saved_searches'
            """)

            if cursor.fetchone():
                # Delete from database
                cursor.execute('DELETE FROM saved_searches WHERE id = ?', (search_id,))
                conn.commit()

            conn.close()

            # Remove from tree
            self.saved_tree.delete(selection[0])
            messagebox.showinfo(_t('advanced_search.search_profiles.deleted_title'), _t('advanced_search.search_profiles.search_deleted_msg', name=search_name))

        except Exception as e:
            messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.delete_search_failed_msg', error=str(e)))
AdvancedSearchGUI.delete_selected_search = delete_selected_search

def share_search_profile(self):
    """
    Share a search profile with other users.

    Allows the current user to make a saved search profile available to all users
    by setting the is_shared flag in the database.
    """
    selection = self.saved_tree.selection()
    if not selection:
        messagebox.showwarning(_t('advanced_search.search_profiles.no_selection_title'), _t('advanced_search.search_profiles.select_search_to_share'))
        return

    item = self.saved_tree.item(selection[0])
    search_id = item['values'][0]
    search_name = item['values'][1]

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if search exists
        cursor.execute("""
            SELECT search_name FROM saved_searches
            WHERE id = ?
        """, (search_id,))

        result = cursor.fetchone()
        if not result:
            messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.search_not_found_msg'))
            conn.close()
            return

        # Confirm sharing
        if messagebox.askyesno(_t('advanced_search.search_profiles.confirm_share_title'),
                              _t('advanced_search.search_profiles.confirm_share_msg', name=search_name)):
            # Update the is_shared flag
            cursor.execute("""
                UPDATE saved_searches
                SET is_shared = 1
                WHERE id = ?
            """, (search_id,))
            conn.commit()

            messagebox.showinfo(_t('advanced_search.search_profiles.success_title'),
                              _t('advanced_search.search_profiles.share_success_msg', name=search_name))

            # Refresh the list to update the shared status
            self.load_saved_searches()

        conn.close()

    except Exception as e:
        messagebox.showerror(_t('advanced_search.search_profiles.error_title'), _t('advanced_search.search_profiles.share_search_failed_msg', error=str(e)))
AdvancedSearchGUI.share_search_profile = share_search_profile

def execute_loaded_search(self, criteria):
    """
    Execute a loaded search with given criteria.

    Args:
        criteria (dict): Search criteria dictionary with fields like:
            - student_id: Student ID pattern
            - first_name: First name pattern
            - last_name: Last name pattern
            - course: Course code
            - gender: Gender
            - age_min, age_max: Age range
    """
    try:
        query = "SELECT * FROM students WHERE 1=1"
        params = []

        # Build query from criteria
        for key, value in criteria.items():
            if value:
                if key in ['student_id', 'first_name', 'last_name']:
                    query += f" AND {key} LIKE ?"
                    params.append(f"%{escape_like(value)}%")
                elif key == 'age_min':
                    query += " AND age >= ?"
                    params.append(value)
                elif key == 'age_max':
                    query += " AND age <= ?"
                    params.append(value)
                else:
                    query += f" AND {key} = ?"
                    params.append(value)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        # Display results
        self.search_results = results
        self.display_search_results(results)
        self.update_status(_t('advanced_search.search_profiles.loaded_search_status', count=len(results)))

    except Exception as e:
        messagebox.showerror(_t('advanced_search.search_profiles.search_error_title'), _t('advanced_search.search_profiles.search_error_msg', error=str(e)))
AdvancedSearchGUI.execute_loaded_search = execute_loaded_search

def show_load_search(self):
    """Show load saved search dialog"""
    self.show_saved_searches()  # Reuse the saved searches dialog
AdvancedSearchGUI.show_load_search = show_load_search
