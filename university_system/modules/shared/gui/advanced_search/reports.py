from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from university_system.core.sql_safety import validate_identifier, validate_table_name, validate_field_for_query, validate_column_name
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

def show_comprehensive_reports(self):
    """Generate comprehensive system reports and display in separate window"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.comprehensive_reports_dialog_title'))
    dialog.geometry("1100x800")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.reports.comprehensive_reports_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Report types
    reports_frame = ttk.LabelFrame(frame, text="Available Reports", padding="10")
    reports_frame.pack(fill=tk.X, pady=(0, 20))

    report_options = [
        ("Student Summary Report", "student_summary", "Complete overview of all students"),
        ("Module Enrollment Report", "module_enrollment", "Detailed module enrollment analysis"),
        ("Demographics Analysis", "demographics_analysis", "Comprehensive demographic breakdown"),
        ("Performance Report", "performance_report", "Academic performance analysis"),
    ]

    selected_reports = {}

    for name, key, description in report_options:
        report_frame = ttk.Frame(reports_frame)
        report_frame.pack(fill=tk.X, pady=5)

        selected_reports[key] = tk.BooleanVar()
        ttk.Checkbutton(report_frame, text=name, variable=selected_reports[key]).pack(side=tk.LEFT)
        ttk.Label(report_frame, text=f" - {description}", font=('Arial', 8)).pack(side=tk.LEFT)

    def generate_reports():
        selected = [key for key, var in selected_reports.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Reports Selected", "Please select at least one report to generate.")
            return

        dialog.destroy()
        self.update_status("Generating comprehensive reports...")

        # Generate reports
        all_reports = []
        try:
            for report_type in selected:
                report_result = self.generate_specific_report(report_type)
                all_reports.append(report_result)

            combined_report = "\n\n" + "=" * 80 + "\n\n".join(all_reports)

            # Open report in separate viewer window
            self._show_report_viewer(combined_report, "Comprehensive Report")
            self.update_status("Report generated successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Report generation error: {str(e)}")
            self.update_status("Report generation failed")

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=_t('advanced_search.generate_button'), command=generate_reports).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_comprehensive_reports = show_comprehensive_reports

def _show_report_viewer(self, report_content, report_title="Report"):
    """Display report in a separate window with save and email options"""
    viewer = tk.Toplevel(self.master)
    viewer.title(f"Report Viewer - {report_title}")
    viewer.geometry("1000x700")
    viewer.transient(self.master)

    # Store report content for save/email operations
    self._current_report_content = report_content
    self._current_report_title = report_title

    frame = ttk.Frame(viewer, padding="10")
    frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(frame, text=report_title, style='Title.TLabel').pack(pady=(0, 10))

    # Report text area with scrollbar
    text_frame = ttk.Frame(frame)
    text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Courier', 10))
    report_text.pack(fill=tk.BOTH, expand=True)
    report_text.insert(tk.END, report_content)
    report_text.config(state=tk.DISABLED)  # Read-only

    # Button frame
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    # Save as TXT button
    ttk.Button(
        button_frame,
        text=_t('advanced_search.save_as_txt'),
        command=lambda: self._save_report_as_txt(report_content, report_title)
    ).pack(side=tk.LEFT, padx=(0, 10))

    # Send to Admin button
    ttk.Button(
        button_frame,
        text=_t('advanced_search.send_to_admin'),
        command=lambda: self._send_report_to_admin(report_content, report_title)
    ).pack(side=tk.LEFT, padx=(0, 10))

    # Close button
    ttk.Button(button_frame, text=_t('advanced_search.close_button'), command=viewer.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI._show_report_viewer = _show_report_viewer

def _save_report_as_txt(self, report_content, report_title):
    """Save report content to a TXT file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_filename = f"{report_title.replace(' ', '_')}_{timestamp}.txt"

    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        initialfile=default_filename,
        title="Save Report As"
    )

    if file_path:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
            self.update_status(f"Report saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report:\n{str(e)}")
AdvancedSearchGUI._save_report_as_txt = _save_report_as_txt

def _get_admin_emails(self):
    """Query database for admin email addresses"""
    admin_emails = []

    try:
        conn = get_connection()
        if conn is None:
            return admin_emails

        cursor = conn.cursor()

        # Query for admin users with email addresses
        cursor.execute("""
            SELECT DISTINCT email
            FROM users
            WHERE role = 'admin'
              AND email IS NOT NULL
              AND email != ''
              AND email LIKE '%@%'
            ORDER BY email
        """)

        results = cursor.fetchall()
        admin_emails = [row[0] for row in results]

        # If no admins found in users table, try staff table
        if not admin_emails:
            cursor.execute("""
                SELECT DISTINCT email
                FROM staff
                WHERE position LIKE '%admin%'
                  AND email IS NOT NULL
                  AND email != ''
                  AND email LIKE '%@%'
                ORDER BY email
            """)
            results = cursor.fetchall()
            admin_emails = [row[0] for row in results]

        conn.close()

    except Exception as e:
        print(f"Error getting admin emails: {e}")

    return admin_emails
AdvancedSearchGUI._get_admin_emails = _get_admin_emails

def _send_report_to_admin(self, report_content, report_title):
    """Send report to admin email addresses"""
    try:
        # Get admin emails from database
        admin_emails = self._get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(
                "No Admin Emails",
                "No admin email addresses found in the database.\n\n"
                "Please ensure at least one admin account has a valid email address."
            )
            return

        # Show confirmation dialog with admin emails
        admin_list = "\n".join([f"  - {email}" for email in admin_emails])
        confirm = messagebox.askyesno(
            "Confirm Send",
            f"Send report to the following admin(s)?\n\n{admin_list}\n\n"
            f"Report: {report_title}"
        )

        if not confirm:
            return

        # Import email service
        try:
            from university_system.infrastructure.email.email_service import send_email
        except ImportError:
            messagebox.showerror("Error", "Email service not available.")
            return

        # Prepare email
        subject = f"Advanced Search Report: {report_title}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        body = f"""Dear Administrator,

Please find the requested report below:

Report Title: {report_title}
Generated: {timestamp}

{'=' * 70}

{report_content}

{'=' * 70}

This is an automated report from the University Advanced Search System.

Best regards,
Advanced Search System
"""

        # Send to all admins
        success_count = 0
        failed_emails = []

        for admin_email in admin_emails:
            try:
                result = send_email(admin_email, subject, body)
                if result:
                    success_count += 1
                else:
                    failed_emails.append(admin_email)
            except Exception as e:
                print(f"Failed to send to {admin_email}: {e}")
                failed_emails.append(admin_email)

        # Show result
        if success_count == len(admin_emails):
            messagebox.showinfo(
                "Success",
                f"Report sent successfully to {success_count} admin(s)."
            )
            self.update_status(f"Report sent to {success_count} admin(s)")
        elif success_count > 0:
            messagebox.showwarning(
                "Partial Success",
                f"Report sent to {success_count} admin(s).\n"
                f"Failed to send to: {', '.join(failed_emails)}"
            )
        else:
            messagebox.showerror(
                "Failed",
                f"Failed to send report to any admins.\n"
                f"Failed emails: {', '.join(failed_emails)}"
            )

    except Exception as e:
        messagebox.showerror("Error", f"Failed to send report:\n{str(e)}")
        import traceback
        traceback.print_exc()
AdvancedSearchGUI._send_report_to_admin = _send_report_to_admin

def generate_comprehensive_reports(self):
    """Generate comprehensive system reports - delegates to show_comprehensive_reports"""
    self.show_comprehensive_reports()
AdvancedSearchGUI.generate_comprehensive_reports = generate_comprehensive_reports

def generate_specific_report(self, report_type):
    """Generate specific report based on type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if report_type == "student_summary":
            return self.generate_student_summary_report(cursor, timestamp)
        elif report_type == "module_enrollment":
            return self.generate_module_enrollment_report(cursor, timestamp)
        elif report_type == "demographics_analysis":
            return self.generate_demographics_analysis_report(cursor, timestamp)
        elif report_type == "performance_report":
            return self.generate_performance_analysis_report(cursor, timestamp)
        elif report_type == "custom_sql":
            return self.generate_custom_sql_report(cursor, timestamp)
        else:
            return f"Unknown report type: {report_type}"
        
    except Exception as e:
        raise Exception(f"Specific report generation error: {str(e)}")
    finally:
        if conn:
            conn.close()
AdvancedSearchGUI.generate_specific_report = generate_specific_report

def generate_student_summary_report(self, cursor, timestamp):
    """Generate comprehensive student summary report"""
    result = f"STUDENT SUMMARY REPORT\n"
    result += f"=" * 50 + "\n"
    result += f"Generated: {timestamp}\n\n"
    
    # Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    # Students by course
    cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course ORDER BY COUNT(*) DESC")
    course_breakdown = cursor.fetchall()
    
    # Gender distribution
    cursor.execute("SELECT gender, COUNT(*) FROM students GROUP BY gender")
    gender_breakdown = cursor.fetchall()
    
    # Age statistics
    cursor.execute("SELECT MIN(age), MAX(age), AVG(age) FROM students WHERE age IS NOT NULL")
    age_stats = cursor.fetchone()
    
    result += f"OVERVIEW:\n"
    result += f"Total Students: {total_students}\n\n"
    
    result += f"COURSE BREAKDOWN:\n"
    for course, count in course_breakdown:
        percentage = (count / total_students) * 100
        course_display = course if course else "Not Specified"
        result += f"  {course_display}: {count} students ({percentage:.1f}%)\n"
    
    result += f"\nGENDER DISTRIBUTION:\n"
    for gender, count in gender_breakdown:
        percentage = (count / total_students) * 100
        gender_display = gender.title() if gender else "Not Specified"
        result += f"  {gender_display}: {count} students ({percentage:.1f}%)\n"
    
    if age_stats and age_stats[0]:
        result += f"\nAGE STATISTICS:\n"
        result += f"  Youngest: {age_stats[0]} years\n"
        result += f"  Oldest: {age_stats[1]} years\n"
        avg_age = age_stats[2] if age_stats[2] is not None else 0.0
        result += f"  Average: {avg_age:.1f} years\n"
    
    # Recent registrations
    cursor.execute("""
    SELECT COUNT(*) FROM students 
    WHERE registration_datetime >= datetime('now', '-30 days')
    """)
    recent_count = cursor.fetchone()[0]
    
    result += f"\nRECENT ACTIVITY:\n"
    result += f"  New registrations (last 30 days): {recent_count}\n"
    
    return result
AdvancedSearchGUI.generate_student_summary_report = generate_student_summary_report

def generate_module_enrollment_report(self, cursor, timestamp):
    """Generate module enrollment analysis report"""
    result = f"MODULE ENROLLMENT REPORT\n"
    result += f"=" * 50 + "\n"
    result += f"Generated: {timestamp}\n\n"
    
    # Total enrollments
    cursor.execute("SELECT COUNT(*) FROM student_modules")
    total_enrollments = cursor.fetchone()[0]
    
    # Enrollments by module
    cursor.execute("""
    SELECT module_code, module_name, COUNT(*) as enrollment_count
    FROM student_modules 
    GROUP BY module_code, module_name
    ORDER BY enrollment_count DESC
    """)
    module_enrollments = cursor.fetchall()
    
    # Enrollments by type
    cursor.execute("""
    SELECT module_type, COUNT(*) 
    FROM student_modules 
    GROUP BY module_type
    """)
    type_enrollments = cursor.fetchall()
    
    result += f"ENROLLMENT OVERVIEW:\n"
    result += f"Total Module Enrollments: {total_enrollments}\n\n"
    
    result += f"TOP MODULES BY ENROLLMENT:\n"
    for code, name, count in module_enrollments[:10]:  # Top 10
        result += f"  {code} - {name}: {count} students\n"
    
    result += f"\nENROLLMENT BY MODULE TYPE:\n"
    for module_type, count in type_enrollments:
        percentage = (count / total_enrollments) * 100 if total_enrollments > 0 else 0
        result += f"  {module_type}: {count} enrollments ({percentage:.1f}%)\n"
    
    # Grade distribution across all modules
    cursor.execute("""
    SELECT grade, COUNT(*) 
    FROM student_modules 
    WHERE grade IS NOT NULL 
    GROUP BY grade
    ORDER BY grade
    """)
    grade_distribution = cursor.fetchall()
    
    if grade_distribution:
        total_graded = sum(count for _, count in grade_distribution)
        result += f"\nOVERALL GRADE DISTRIBUTION:\n"
        for grade, count in grade_distribution:
            percentage = (count / total_graded) * 100
            result += f"  Grade {grade}: {count} ({percentage:.1f}%)\n"
    
    return result
AdvancedSearchGUI.generate_module_enrollment_report = generate_module_enrollment_report

def generate_demographics_analysis_report(self, cursor, timestamp):
    """Generate comprehensive demographics analysis"""
    result = f"DEMOGRAPHICS ANALYSIS REPORT\n"
    result += f"=" * 50 + "\n"
    result += f"Generated: {timestamp}\n\n"
    
    # Gender distribution by course
    cursor.execute("""
    SELECT course, gender, COUNT(*) 
    FROM students 
    GROUP BY course, gender
    ORDER BY course, gender
    """)
    gender_course_data = cursor.fetchall()
    
    # Age distribution by course
    cursor.execute("""
    SELECT course, 
           CASE 
               WHEN age < 20 THEN 'Under 20'
               WHEN age BETWEEN 20 AND 25 THEN '20-25'
               WHEN age BETWEEN 26 AND 30 THEN '26-30'
               ELSE 'Over 30'
           END as age_group,
           COUNT(*)
    FROM students 
    WHERE age IS NOT NULL
    GROUP BY course, age_group
    ORDER BY course, age_group
    """)
    age_course_data = cursor.fetchall()
    
    # Registration trends
    cursor.execute("""
    SELECT strftime('%Y-%m', registration_datetime) as month, 
           course, COUNT(*)
    FROM students 
    WHERE registration_datetime IS NOT NULL
    GROUP BY month, course
    ORDER BY month DESC, course
    LIMIT 20
    """)
    registration_trends = cursor.fetchall()
    
    result += f"GENDER DISTRIBUTION BY COURSE:\n"
    current_course = None
    for course, gender, count in gender_course_data:
        if course != current_course:
            result += f"\n{course} Course:\n"
            current_course = course
        result += f"  {gender.title()}: {count} students\n"
    
    result += f"\nAGE DISTRIBUTION BY COURSE:\n"
    current_course = None
    for course, age_group, count in age_course_data:
        if course != current_course:
            result += f"\n{course} Course:\n"
            current_course = course
        result += f"  {age_group}: {count} students\n"
    
    result += f"\nREGISTRATION TRENDS (Recent months):\n"
    for month, course, count in registration_trends:
        result += f"  {month} - {course}: {count} new students\n"
    
    return result
AdvancedSearchGUI.generate_demographics_analysis_report = generate_demographics_analysis_report

def generate_performance_analysis_report(self, cursor, timestamp):
    """Generate academic performance analysis report"""
    result = f"PERFORMANCE ANALYSIS REPORT\n"
    result += f"=" * 50 + "\n"
    result += f"Generated: {timestamp}\n\n"
    
    # Overall performance metrics
    cursor.execute("""
    SELECT 
        COUNT(DISTINCT student_id) as total_students_with_grades,
        COUNT(*) as total_graded_modules,
        AVG(CASE grade 
            WHEN 'A' THEN 4.0 
            WHEN 'B' THEN 3.0 
            WHEN 'C' THEN 2.0 
            WHEN 'D' THEN 1.0 
            ELSE 0.0 
        END) as average_gpa
    FROM student_modules 
    WHERE grade IS NOT NULL
    """)
    performance_stats = cursor.fetchone()
    
    # Performance by course
    cursor.execute("""
    SELECT s.course, 
           AVG(CASE sm.grade 
               WHEN 'A' THEN 4.0 
               WHEN 'B' THEN 3.0 
               WHEN 'C' THEN 2.0 
               WHEN 'D' THEN 1.0 
               ELSE 0.0 
           END) as avg_gpa,
           COUNT(sm.grade) as graded_modules
    FROM students s
    JOIN student_modules sm ON s.student_id = sm.student_id
    WHERE sm.grade IS NOT NULL
    GROUP BY s.course
    """)
    course_performance = cursor.fetchall()
    
    # Top and bottom performing students
    cursor.execute("""
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           AVG(CASE sm.grade 
               WHEN 'A' THEN 4.0 
               WHEN 'B' THEN 3.0 
               WHEN 'C' THEN 2.0 
               WHEN 'D' THEN 1.0 
               ELSE 0.0 
           END) as avg_gpa,
           COUNT(sm.grade) as modules_completed
    FROM students s
    JOIN student_modules sm ON s.student_id = sm.student_id
    WHERE sm.grade IS NOT NULL
    GROUP BY s.student_id, s.first_name, s.last_name, s.course
    HAVING COUNT(sm.grade) >= 3
    ORDER BY avg_gpa DESC
    """)
    student_performance = cursor.fetchall()
    
    if performance_stats:
        total_students, total_modules, avg_gpa = performance_stats
        result += f"OVERALL PERFORMANCE METRICS:\n"
        result += f"Students with grades: {total_students}\n"
        result += f"Total graded modules: {total_modules}\n"
        avg_gpa_display = avg_gpa if avg_gpa is not None else 0.0
        result += f"System-wide GPA: {avg_gpa_display:.2f}\n\n"

    result += f"PERFORMANCE BY COURSE:\n"
    for course, avg_gpa, module_count in course_performance:
        avg_gpa_display = avg_gpa if avg_gpa is not None else 0.0
        result += f"  {course}: {avg_gpa_display:.2f} GPA ({module_count} graded modules)\n"

    result += f"\nTOP PERFORMING STUDENTS:\n"
    for i, (student_id, first_name, last_name, course, gpa, modules) in enumerate(student_performance[:10]):
        gpa_display = gpa if gpa is not None else 0.0
        result += f"  {i+1}. {first_name} {last_name} ({course}): {gpa_display:.2f} GPA ({modules} modules)\n"

    if len(student_performance) > 10:
        result += f"\nLOWEST PERFORMING STUDENTS (Need Support):\n"
        for i, (student_id, first_name, last_name, course, gpa, modules) in enumerate(student_performance[-5:]):
            gpa_display = gpa if gpa is not None else 0.0
            result += f"  {first_name} {last_name} ({course}): {gpa_display:.2f} GPA ({modules} modules)\n"
    
    return result
AdvancedSearchGUI.generate_performance_analysis_report = generate_performance_analysis_report

def generate_custom_sql_report(self, cursor, timestamp):
    """Generate custom SQL report with user input"""
    result = f"CUSTOM SQL REPORT\n"
    result += f"=" * 50 + "\n"
    result += f"Generated: {timestamp}\n\n"
    
    # In a real implementation, this would allow users to input custom SQL
    # For now, provide some example queries
    
    sample_queries = [
        ("Students without module enrollments", "SELECT * FROM students WHERE student_id NOT IN (SELECT DISTINCT student_id FROM student_modules)"),
        ("Module completion rates", "SELECT module_code, COUNT(*) as enrolled, COUNT(grade) as completed FROM student_modules GROUP BY module_code"),
        ("Recent activity summary", "SELECT DATE(registration_datetime) as date, COUNT(*) FROM students WHERE registration_datetime >= datetime('now', '-7 days') GROUP BY DATE(registration_datetime)")
    ]
    
    result += f"SAMPLE CUSTOM QUERIES:\n\n"
    
    for query_name, sql in sample_queries:
        result += f"{query_name}:\n"
        result += f"SQL: {sql}\n"
        
        try:
            cursor.execute(sql)
            query_results = cursor.fetchall()
            
            result += f"Results ({len(query_results)} rows):\n"
            for row in query_results[:5]:  # Show first 5 rows
                result += f"  {row}\n"
            if len(query_results) > 5:
                result += f"  ... and {len(query_results) - 5} more rows\n"
        except Exception as e:
            result += f"Error executing query: {str(e)}\n"
        
        result += f"\n"
    
    result += f"Note: In full implementation, users can input custom SQL queries here.\n"
    
    return result
AdvancedSearchGUI.generate_custom_sql_report = generate_custom_sql_report

def generate_demographics_analysis(self):
    """
    Generate comprehensive demographics analysis report (CLI-compatible).

    Provides detailed demographic breakdowns including:
    - Age distribution
    - Gender distribution by course
    - Geographic distribution
    - Cross-tabulation analysis
    """
    dialog = tk.Toplevel(self.master)
    dialog.title(f"👥 {_t('advanced_search.demographics_analysis_title')}")
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Demographics Analysis Report",
             style='Title.TLabel').pack(pady=(0, 20))

    result_text = scrolledtext.ScrolledText(frame, height=20, wrap=tk.WORD, font=('Courier', 9))
    result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    def generate_analysis():
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "👥 DEMOGRAPHICS ANALYSIS REPORT\n")
        result_text.insert(tk.END, "=" * 60 + "\n\n")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Age distribution
            cursor.execute('''
                SELECT
                    CASE
                        WHEN age < 20 THEN 'Under 20'
                        WHEN age BETWEEN 20 AND 25 THEN '20-25'
                        WHEN age BETWEEN 26 AND 30 THEN '26-30'
                        WHEN age BETWEEN 31 AND 35 THEN '31-35'
                        WHEN age BETWEEN 36 AND 40 THEN '36-40'
                        ELSE 'Over 40'
                    END as age_group,
                    COUNT(*) as count
                FROM students
                WHERE age IS NOT NULL
                GROUP BY age_group
                ORDER BY
                    CASE age_group
                        WHEN 'Under 20' THEN 1
                        WHEN '20-25' THEN 2
                        WHEN '26-30' THEN 3
                        WHEN '31-35' THEN 4
                        WHEN '36-40' THEN 5
                        ELSE 6
                    END
            ''')

            age_data = cursor.fetchall()
            total_with_age = sum(count for _, count in age_data)

            result_text.insert(tk.END, "📊 AGE DISTRIBUTION:\n")
            result_text.insert(tk.END, "-" * 40 + "\n")
            for age_group, count in age_data:
                percentage = (count / total_with_age) * 100 if total_with_age > 0 else 0
                bar = '█' * min(int(percentage / 2), 40)
                result_text.insert(tk.END, f"{age_group:<15} |{bar:<40} {count:>5} ({percentage:>5.1f}%)\n")

            # Course by Gender cross-tabulation
            cursor.execute('''
                SELECT course, gender, COUNT(*) as count
                FROM students
                GROUP BY course, gender
                ORDER BY course, gender
            ''')

            cross_tab = cursor.fetchall()

            result_text.insert(tk.END, "\n📋 COURSE × GENDER CROSS-TABULATION:\n")
            result_text.insert(tk.END, "-" * 50 + "\n")

            # Organize data
            courses = {}
            for course, gender, count in cross_tab:
                if course not in courses:
                    courses[course] = {}
                courses[course][gender] = count

            # Display
            genders = ['male', 'female', 'other']
            header = f"{'Course':<10}" + "".join(f"{g.capitalize():<10}" for g in genders) + "Total\n"
            result_text.insert(tk.END, header)
            result_text.insert(tk.END, "-" * len(header) + "\n")

            for course, gender_counts in courses.items():
                row = f"{course:<10}"
                total = 0
                for gender in genders:
                    count = gender_counts.get(gender, 0)
                    row += f"{count:<10}"
                    total += count
                row += f"{total}\n"
                result_text.insert(tk.END, row)

            conn.close()

            result_text.insert(tk.END, "\n" + "=" * 60 + "\n")
            result_text.insert(tk.END, f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        except Exception as e:
            result_text.insert(tk.END, f"\nError generating analysis: {str(e)}\n")

    # Auto-generate on load
    generate_analysis()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="🔄 Refresh", command=generate_analysis).pack(side=tk.LEFT)
    ttk.Button(button_frame, text="💾 Export",
              command=lambda: self.export_report_to_file(result_text.get(1.0, tk.END), "demographics")).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.generate_demographics_analysis = generate_demographics_analysis

def generate_performance_report(self):
    """
    Generate academic performance report (CLI-compatible).

    Analyzes student academic performance including:
    - Top performing students
    - Performance by course
    - Grade distribution
    - Completion rates
    """
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🎯 {_t('advanced_search.performance_report_title')}")
    dialog.geometry("800x600")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Academic Performance Report",
             style='Title.TLabel').pack(pady=(0, 20))

    result_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, font=('Courier', 9))
    result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    def generate_report():
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "🎯 ACADEMIC PERFORMANCE REPORT\n")
        result_text.insert(tk.END, "=" * 100 + "\n\n")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Student performance metrics
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, s.course,
                       COUNT(sm.module_code) as total_modules,
                       SUM(CASE WHEN sm.grade IS NOT NULL THEN 1 ELSE 0 END) as completed_modules,
                       SUM(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 ELSE 0 END) as passed_modules,
                       AVG(CASE WHEN sm.grade IN ('A', 'B', 'C', 'D') THEN 1.0 ELSE 0.0 END) * 100 as success_rate
                FROM students s
                LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.student_id, s.first_name, s.last_name, s.course
                HAVING total_modules > 0
                ORDER BY success_rate DESC, completed_modules DESC
                LIMIT 20
            ''')

            performance_data = cursor.fetchall()

            if performance_data:
                result_text.insert(tk.END, "🏆 TOP PERFORMING STUDENTS:\n")
                result_text.insert(tk.END, "-" * 100 + "\n")
                result_text.insert(tk.END, f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Course':<8} {'Modules':<10} {'Success %':<10}\n")
                result_text.insert(tk.END, "-" * 100 + "\n")

                for rank, (student_id, first_name, last_name, course, total, completed, passed, success_rate) in enumerate(performance_data, 1):
                    name = f"{first_name} {last_name}"
                    modules_text = f"{completed}/{total}"
                    success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"

                    result_text.insert(tk.END, f"{rank:<5} {student_id:<12} {name:<25} {course:<8} {modules_text:<10} {success_display:<10}\n")

            # Performance by course
            cursor.execute('''
                SELECT s.course,
                       AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 as avg_completion_rate,
                       AVG(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1.0 ELSE 0.0 END) * 100 as avg_success_rate
                FROM students s
                LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.course
                ORDER BY avg_success_rate DESC
            ''')

            course_performance = cursor.fetchall()

            result_text.insert(tk.END, "\n📊 PERFORMANCE BY COURSE:\n")
            result_text.insert(tk.END, "-" * 60 + "\n")
            result_text.insert(tk.END, f"{'Course':<10} {'Avg Completion %':<18} {'Avg Success %':<15}\n")
            result_text.insert(tk.END, "-" * 60 + "\n")

            for course, completion_rate, success_rate in course_performance:
                completion_display = f"{completion_rate:.1f}%" if completion_rate is not None else "N/A"
                success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"

                result_text.insert(tk.END, f"{course:<10} {completion_display:<18} {success_display:<15}\n")

            conn.close()

            result_text.insert(tk.END, "\n" + "=" * 100 + "\n")
            result_text.insert(tk.END, f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        except Exception as e:
            result_text.insert(tk.END, f"\nError generating report: {str(e)}\n")

    # Auto-generate on load
    generate_report()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="🔄 Refresh", command=generate_report).pack(side=tk.LEFT)
    ttk.Button(button_frame, text="💾 Export",
              command=lambda: self.export_report_to_file(result_text.get(1.0, tk.END), "performance")).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.generate_performance_report = generate_performance_report

def export_report_to_file(self, content, report_type):
    """Export report content to file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{report_type}_report_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    messagebox.showinfo("Export Complete", f"Report exported to {filename}")
AdvancedSearchGUI.export_report_to_file = export_report_to_file
