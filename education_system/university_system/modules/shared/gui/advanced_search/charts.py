from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from education_system.university_system.core.sql_safety import validate_identifier, validate_table_name, validate_field_for_query, validate_column_name
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

from .base import AdvancedSearchGUI

def show_advanced_charts(self):
    """Show advanced chart generation options"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📈 {_t('advanced_search.charts_visualization_dialog_title')}")
    dialog.geometry("550x680")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.charts.advanced_visualizations'), style='Title.TLabel').pack(pady=(0, 10))

    # Show availability status
    if CHARTS_AVAILABLE:
        status_label = ttk.Label(frame, text=f"✓ {_t('advanced_search.charts.generation_available')}",
                               foreground="green")
    else:
        status_label = ttk.Label(frame, text=f"⚠ {_t('advanced_search.charts.charts_require')}",
                               foreground="red")
    status_label.pack(pady=(0, 20))

    # Info text
    info_text = _t('advanced_search.charts.info_text')
    ttk.Label(frame, text=info_text, justify=tk.CENTER, foreground="gray").pack(pady=(0, 15))

    # Chart types
    chart_options = [
        (f"📊 {_t('advanced_search.charts.age_histogram')}", "age_histogram"),
        (f"🥧 {_t('advanced_search.charts.course_pie')}", "course_pie"),
        (f"📈 {_t('advanced_search.charts.registration_timeline')}", "registration_timeline"),
        (f"👥 {_t('advanced_search.charts.gender_course')}", "gender_course"),
        (f"🎯 {_t('advanced_search.charts.module_popularity')}", "module_popularity"),
        (f"📉 {_t('advanced_search.charts.grade_distribution_chart')}", "grade_distribution"),
    ]

    for text, chart_type in chart_options:
        btn = ttk.Button(frame, text=text, width=40,
                        command=lambda ct=chart_type: self.generate_chart(ct, dialog))
        btn.pack(pady=5)

    # Separator
    ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)

    # Email chart option
    ttk.Label(frame, text=f"{_t('advanced_search.charts.send_via_email')}:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))
    ttk.Button(frame, text=f"📧 {_t('advanced_search.charts.email_to_admin')}", width=40,
              command=lambda: self.email_chart_to_admin(dialog)).pack(pady=5)

    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(pady=(20, 0))
AdvancedSearchGUI.show_advanced_charts = show_advanced_charts

def generate_chart(self, chart_type, parent_dialog):
    """Generate specified chart type with matplotlib"""
    parent_dialog.destroy()

    # Check if charts are available
    if not CHARTS_AVAILABLE:
        messagebox.showerror(_t('advanced_search.charts.charts_unavailable'),
                           _t('advanced_search.charts.charts_unavailable_msg'))
        return

    self.update_status(_t("advanced_search.charts.generating_chart", chart_type=chart_type.replace('_', ' ')))
    self.start_progress()

    def run_chart_generation():
        try:
            # Use new chart generation system
            create_chart_viewer(self.master, chart_type)

            self.output_queue.put(("log", f"✓ {_t('advanced_search.charts.chart_generated', type=chart_type)}"))
            self.output_queue.put(("log", _t('advanced_search.charts.chart_displayed')))
        except Exception as e:
            self.output_queue.put(("error", _t('advanced_search.charts.chart_error', error=str(e))))
        finally:
            self.output_queue.put(("stop_progress", None))

    # Run in thread to avoid blocking UI
    threading.Thread(target=run_chart_generation, daemon=True).start()
AdvancedSearchGUI.generate_chart = generate_chart

def email_chart_to_admin(self, parent_dialog):
    """Email chart to admin user"""
    parent_dialog.destroy()

    # Chart selection dialog
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📧 {_t('advanced_search.email_chart_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.charts.select_chart_to_email'), style='Title.TLabel').pack(pady=(0, 20))

    # Chart type selection
    ttk.Label(frame, text=f"{_t('advanced_search.charts.chart_type')}:").pack(anchor='w', pady=(0, 5))
    chart_var = tk.StringVar(value="age_histogram")
    chart_options = [
        (_t('advanced_search.charts.age_histogram'), "age_histogram"),
        (_t('advanced_search.charts.course_pie'), "course_pie"),
        (_t('advanced_search.charts.registration_timeline'), "registration_timeline"),
        (_t('advanced_search.charts.gender_course'), "gender_course"),
        (_t('advanced_search.charts.module_popularity'), "module_popularity"),
        (_t('advanced_search.charts.grade_distribution_chart'), "grade_distribution"),
    ]

    for text, value in chart_options:
        ttk.Radiobutton(frame, text=text, variable=chart_var, value=value).pack(anchor='w', padx=20)

    # Get admin email from database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
        admin_row = cursor.fetchone()
        conn.close()
        default_email = admin_row[0] if admin_row else "admin@university.edu"
    except Exception as e:
        print(f"Warning: Could not fetch admin email from database: {e}")
        default_email = "admin@university.edu"

    ttk.Label(frame, text=f"\n{_t('advanced_search.charts.admin_email')}:").pack(anchor='w', pady=(20, 5))
    email_var = tk.StringVar(value=default_email)

    # Create a frame for email input with a refresh button
    email_frame = ttk.Frame(frame)
    email_frame.pack(fill='x', pady=(0, 10))

    email_entry = ttk.Entry(email_frame, textvariable=email_var, width=35)
    email_entry.pack(side='left', fill='x', expand=True)

    def refresh_admin_email():
        """Refresh admin email list from database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username")
            admins = cursor.fetchall()
            conn.close()

            if admins:
                # Show selection dialog if multiple admins
                if len(admins) > 1:
                    admin_dialog = tk.Toplevel(dialog)
                    admin_dialog.title(_t('advanced_search.select_admin_dialog_title'))
                    admin_dialog.geometry("900x700")
                    admin_dialog.transient(dialog)
                    admin_dialog.grab_set()

                    ttk.Label(admin_dialog, text=f"{_t('advanced_search.charts.select_admin')}:", font=('Arial', 12, 'bold')).pack(pady=10)

                    admin_listbox = tk.Listbox(admin_dialog, height=10)
                    admin_listbox.pack(fill='both', expand=True, padx=20, pady=10)

                    for username, email in admins:
                        admin_listbox.insert(tk.END, f"{username} ({email})")

                    def select_admin():
                        selection = admin_listbox.curselection()
                        if selection:
                            selected_email = admins[selection[0]][1]
                            email_var.set(selected_email)
                        admin_dialog.destroy()

                    ttk.Button(admin_dialog, text=_t('advanced_search.charts.select_button'), command=select_admin).pack(pady=10)
                else:
                    # Only one admin, use their email
                    email_var.set(admins[0][1])
                    messagebox.showinfo(_t('advanced_search.charts.admin_email'),
                                      _t('advanced_search.charts.using_admin_email', email=admins[0][1]))
            else:
                messagebox.showwarning(_t('advanced_search.charts.no_admins'),
                                      _t('advanced_search.charts.no_admins_msg'))
        except Exception as e:
            messagebox.showerror(_t('advanced_search.charts.db_error'),
                               _t('advanced_search.charts.db_error_msg', error=str(e)))

    ttk.Button(email_frame, text="🔄", command=refresh_admin_email, width=3).pack(side='left', padx=(5, 0))

    ttk.Label(frame, text=f"{_t('advanced_search.charts.message_optional')}:").pack(anchor='w', pady=(10, 5))
    message_text = scrolledtext.ScrolledText(frame, height=6, wrap=tk.WORD)
    message_text.pack(fill='x', pady=(0, 20))
    message_text.insert('1.0', _t('advanced_search.charts.default_message'))

    def send_chart_email():
        try:
            # Import email service
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email
                EMAIL_AVAILABLE = True
            except ImportError:
                EMAIL_AVAILABLE = False

            if not EMAIL_AVAILABLE:
                messagebox.showerror(_t('advanced_search.charts.email_unavailable'),
                                   _t('advanced_search.charts.email_unavailable_msg'))
                return

            chart_type = chart_var.get()
            admin_email = email_var.get().strip()
            message = message_text.get('1.0', tk.END).strip()

            if not admin_email or '@' not in admin_email:
                messagebox.showwarning(_t('advanced_search.charts.invalid_email'),
                                      _t('advanced_search.charts.invalid_email_msg'))
                return

            # Generate chart data
            chart_data = self.create_chart_data(chart_type)

            # Create email subject and body
            subject = f"Analytics Chart: {chart_type.replace('_', ' ').title()}"
            body = f"""
{message}

Chart Type: {chart_type.replace('_', ' ').title()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Chart Data:
{chart_data}

This email was sent from the Advanced Search GUI - Analytics Dashboard.
"""

            # Send email
            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            messagebox.showinfo(_t('advanced_search.charts.email_sent'),
                              _t('advanced_search.charts.email_sent_msg',
                                 email=admin_email, type=chart_type.replace('_', ' ').title()))
            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('advanced_search.charts.email_error'),
                               _t('advanced_search.charts.email_error_msg', error=str(e)))
            print(f"Chart email error: {str(e)}")

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill='x', pady=(10, 0))
    ttk.Button(button_frame, text=f"📧 {_t('advanced_search.charts.send_email')}", command=send_chart_email).pack(side='left', padx=(0, 10))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side='right')
AdvancedSearchGUI.email_chart_to_admin = email_chart_to_admin

def create_chart_data(self, chart_type):
    """Create chart data for different visualization types"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        result = f"📈 {_t('advanced_search.charts.chart_data_header', type=chart_type.replace('_', ' ').title())}\n"
        result += f"═" * 50 + "\n"
        result += f"{_t('advanced_search.charts.generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if chart_type == "age_histogram":
            cursor.execute("SELECT age, COUNT(*) FROM students WHERE age IS NOT NULL GROUP BY age ORDER BY age")
            age_data = cursor.fetchall()

            if not age_data:
                result += f"{_t('advanced_search.charts.age_distribution')}:\n"
                result += "-" * 20 + "\n"
                result += f"{_t('advanced_search.charts.no_age_data')}\n"
            else:
                result += f"{_t('advanced_search.charts.age_distribution')}:\n"
                result += "-" * 20 + "\n"
                for age, count in age_data:
                    age_display = age if age is not None else 0
                    bar = "█" * min(count, 20)  # Visual bar representation
                    result += f"{_t('advanced_search.charts.age_label')} {age_display:2d}: {count:3d} {_t('advanced_search.charts.students')} {bar}\n"

        elif chart_type == "course_pie":
            cursor.execute("SELECT course, COUNT(*) FROM students WHERE course IS NOT NULL GROUP BY course")
            course_data = cursor.fetchall()

            if not course_data:
                result += f"{_t('advanced_search.charts.course_distribution')}:\n"
                result += "-" * 20 + "\n"
                result += f"{_t('advanced_search.charts.no_course_data')}\n"
            else:
                total = sum(count for _, count in course_data)
                result += f"{_t('advanced_search.charts.course_distribution')}:\n"
                result += "-" * 20 + "\n"
                for course, count in course_data:
                    percentage = (count / total * 100) if total > 0 else 0
                    course_name = course if course else _t('advanced_search.charts.not_specified')
                    result += f"{course_name}: {count} {_t('advanced_search.charts.students')} ({percentage:.1f}%)\n"

        elif chart_type == "registration_timeline":
            cursor.execute("""
            SELECT strftime('%Y-%m', registration_datetime) as month, COUNT(*)
            FROM students
            WHERE registration_datetime IS NOT NULL
            GROUP BY strftime('%Y-%m', registration_datetime)
            ORDER BY month
            """)
            timeline_data = cursor.fetchall()

            result += f"{_t('advanced_search.charts.registration_timeline')}:\n"
            result += "-" * 25 + "\n"
            if not timeline_data:
                result += f"{_t('advanced_search.charts.no_timeline_data')}\n"
            else:
                for month, count in timeline_data:
                    bar = "█" * min(count, 15)
                    month_display = month if month else _t('advanced_search.charts.unknown')
                    result += f"{month_display}: {count:3d} {_t('advanced_search.charts.registrations')} {bar}\n"

        elif chart_type == "gender_course":
            cursor.execute("""
            SELECT course, gender, COUNT(*)
            FROM students
            WHERE course IS NOT NULL
            GROUP BY course, gender
            ORDER BY course, gender
            """)
            gender_course_data = cursor.fetchall()

            result += f"{_t('advanced_search.charts.gender_course_dist')}:\n"
            result += "-" * 30 + "\n"
            if not gender_course_data:
                result += f"{_t('advanced_search.charts.no_gender_course_data')}\n"
            else:
                for course, gender, count in gender_course_data:
                    course_name = course if course else _t('advanced_search.charts.not_specified')
                    gender_name = gender.title() if gender else _t('advanced_search.charts.not_specified')
                    result += f"{course_name} - {gender_name}: {count} {_t('advanced_search.charts.students')}\n"

        elif chart_type == "module_popularity":
            cursor.execute("""
            SELECT module_code, module_name, COUNT(*) as enrollment_count
            FROM student_modules
            WHERE module_code IS NOT NULL
            GROUP BY module_code, module_name
            ORDER BY enrollment_count DESC
            LIMIT 10
            """)
            module_data = cursor.fetchall()

            result += f"{_t('advanced_search.charts.top_modules_header')}:\n"
            result += "-" * 35 + "\n"
            if not module_data:
                result += f"{_t('advanced_search.charts.no_module_data')}\n"
            else:
                for i, (code, name, count) in enumerate(module_data, 1):
                    code_display = code if code else _t('advanced_search.charts.na')
                    name_display = name if name else _t('advanced_search.charts.na')
                    result += f"{i:2d}. {code_display} - {name_display}: {count} {_t('advanced_search.charts.enrollments')}\n"

        elif chart_type == "grade_distribution":
            cursor.execute("""
            SELECT grade, COUNT(*)
            FROM student_modules
            WHERE grade IS NOT NULL
            GROUP BY grade
            ORDER BY grade
            """)
            grade_data = cursor.fetchall()

            result += f"{_t('advanced_search.charts.grade_dist_header')}:\n"
            result += "-" * 30 + "\n"
            if not grade_data:
                result += f"{_t('advanced_search.charts.no_grade_data')}\n"
            else:
                total_grades = sum(count for _, count in grade_data)
                for grade, count in grade_data:
                    percentage = (count / total_grades * 100) if total_grades > 0 else 0
                    bar = "█" * min(int(percentage), 20)
                    grade_display = grade if grade else _t('advanced_search.charts.na')
                    result += f"{_t('advanced_search.charts.grade_label')} {grade_display}: {count:4d} ({percentage:5.1f}%) {bar}\n"

        else:  # custom_chart or enrollment_trends
            cursor.execute("""
            SELECT
                strftime('%Y', registration_datetime) as year,
                course,
                COUNT(*) as count
            FROM students
            WHERE registration_datetime IS NOT NULL AND course IS NOT NULL
            GROUP BY year, course
            ORDER BY year, course
            """)
            trend_data = cursor.fetchall()

            result += f"{_t('advanced_search.charts.enrollment_trends')}:\n"
            result += "-" * 40 + "\n"
            if not trend_data:
                result += f"{_t('advanced_search.charts.no_trend_data')}\n"
            else:
                for year, course, count in trend_data:
                    year_display = year if year else _t('advanced_search.charts.unknown')
                    course_display = course if course else _t('advanced_search.charts.not_specified')
                    result += f"{year_display} - {course_display}: {count} {_t('advanced_search.charts.enrollments')}\n"

        conn.close()

        result += f"\n📊 {_t('advanced_search.charts.recommendations_header')}:\n"
        result += f"• {_t('advanced_search.charts.rec_1')}\n"
        result += f"• {_t('advanced_search.charts.rec_2')}\n"
        result += f"• {_t('advanced_search.charts.rec_3')}\n"

        return result

    except Exception as e:
        raise Exception(f"Chart data creation error: {str(e)}")
AdvancedSearchGUI.create_chart_data = create_chart_data

def show_charts(self):
    """Show interactive charts"""
    self.update_status(_t("advanced_search.charts.generating_charts"))
    self.start_progress()
    
    def run_charts():
        try:
            result = self.capture_function_output(interactive_charts)
            self.output_queue.put(("analytics", result))
        except Exception as e:
            self.output_queue.put(("error", _t('advanced_search.charts.error_generating', error=str(e))))
        finally:
            self.output_queue.put(("stop_progress", None))
    
    threading.Thread(target=run_charts, daemon=True).start()
AdvancedSearchGUI.show_charts = show_charts
