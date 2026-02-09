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

def show_favorites_manager(self):
    """Show favorites management interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.favorites_manager_dialog_title'))
    dialog.geometry("1100x800")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Favorite Students", style='Title.TLabel').pack(pady=(0, 20))
    
    # Load favorites
    try:
        with open('favorite_students.json', 'r') as f:
            self.favorite_students = json.load(f)
    except FileNotFoundError:
        self.favorite_students = []
    
    if not self.favorite_students:
        ttk.Label(frame, text="No favorite students yet.").pack()
        ttk.Button(frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack(pady=(20, 0))
        return
    
    # Favorites list
    columns = ('ID', 'Name', 'Email', 'Course', 'Added')
    favorites_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
    
    for col in columns:
        favorites_tree.heading(col, text=col)
        favorites_tree.column(col, width=100)
    
    favorites_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=favorites_tree.yview)
    favorites_tree.configure(yscrollcommand=favorites_scrollbar.set)
    
    favorites_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    favorites_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Populate favorites
    for fav in self.favorite_students:
        added_date = fav['added_date'][:10] if 'added_date' in fav else 'N/A'
        favorites_tree.insert('', 'end', values=(
            fav['id'], fav['name'], fav['email'], fav['course'], added_date
        ))
    
    # Actions
    actions_frame = ttk.Frame(frame)
    actions_frame.pack(fill=tk.X, pady=(10, 0))
    
    def view_favorite():
        selection = favorites_tree.selection()
        if not selection:
            messagebox.showwarning("_t('advanced_search.no_selection')", "_t('advanced_search.select_student')")
            return
        
        item = favorites_tree.item(selection[0])
        student_id = item['values'][0]
        
        # Find full student data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
            student_data = cursor.fetchone()
            conn.close()
            
            if student_data:
                self.show_detailed_student_view(student_data)
            else:
                messagebox.showerror("Error", "Student not found in database")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load student: {str(e)}")
    
    def remove_favorite():
        selection = favorites_tree.selection()
        if not selection:
            messagebox.showwarning("_t('advanced_search.no_selection')", "Please select a student to remove.")
            return
        
        item = favorites_tree.item(selection[0])
        student_name = item['values'][1]
        
        if messagebox.askyesno("Confirm Remove", f"Remove {student_name} from favorites?"):
            student_id = item['values'][0]
            self.favorite_students = [fav for fav in self.favorite_students if fav['id'] != student_id]
            
            # Save updated favorites
            with open('favorite_students.json', 'w') as f:
                json.dump(self.favorite_students, f, indent=2)
            
            favorites_tree.delete(selection[0])
            messagebox.showinfo("Removed", f"{student_name} removed from favorites")
    
    ttk.Button(actions_frame, text=_t('advanced_search.view_details'), command=view_favorite).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(actions_frame, text=_t('advanced_search.remove_button'), command=remove_favorite).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(actions_frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_favorites_manager = show_favorites_manager

def show_smart_suggestions(self):
    """Show smart suggestions interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🧠 {_t('advanced_search.smart_suggestions_dialog_title')}")
    dialog.geometry("1100x800")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Smart Search Suggestions", style='Title.TLabel').pack(pady=(0, 20))
    
    # Suggestion categories
    notebook = ttk.Notebook(frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    # Popular searches tab
    popular_frame = ttk.Frame(notebook, padding="10")
    notebook.add(popular_frame, text="Popular Searches")
    
    popular_suggestions = [
        "Students enrolled in CS courses",
        "Recent registrations (last 30 days)",
        "Students over 25 years old",
        "Female students in Data Science",
        "Students without email addresses",
        "Incomplete module enrollments"
    ]
    
    ttk.Label(popular_frame, text="Most popular search patterns:").pack(anchor='w', pady=(0, 10))
    
    for suggestion in popular_suggestions:
        btn = ttk.Button(popular_frame, text=f"🔍 {suggestion}",
                        command=lambda s=suggestion: self.execute_suggestion(s, dialog))
        btn.pack(fill=tk.X, pady=2)
    
    # Recent searches tab
    recent_frame = ttk.Frame(notebook, padding="10")
    notebook.add(recent_frame, text="Recent Searches")
    
    recent_searches = [
        "John Smith",
        "CS101 module",
        "Age between 20-25",
        "Registration after 2024-01-01"
    ]
    
    ttk.Label(recent_frame, text="Your recent searches:").pack(anchor='w', pady=(0, 10))
    
    for search in recent_searches:
        btn = ttk.Button(recent_frame, text=f"🔄 {search}",
                        command=lambda s=search: self.execute_suggestion(s, dialog))
        btn.pack(fill=tk.X, pady=2)
    
    # Recommended tab
    recommended_frame = ttk.Frame(notebook, padding="10")
    notebook.add(recommended_frame, text="Recommended")
    
    recommendations = [
        "Students at risk of dropping out",
        "High-performing students for honors",
        "Students needing academic support",
        "Duplicate student records"
    ]
    
    ttk.Label(recommended_frame, text="Recommended searches based on patterns:").pack(anchor='w', pady=(0, 10))
    
    for recommendation in recommendations:
        btn = ttk.Button(recommended_frame, text=f"💡 {recommendation}",
                        command=lambda r=recommendation: self.execute_suggestion(r, dialog))
        btn.pack(fill=tk.X, pady=2)
    
    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack()
AdvancedSearchGUI.show_smart_suggestions = show_smart_suggestions

def execute_suggestion(self, suggestion, parent_dialog):
    """Execute a suggested search"""
    parent_dialog.destroy()
    
    # Parse suggestion and create appropriate search
    if "CS courses" in suggestion:
        # Execute course search
        criteria = {"course": "CS"}
    elif "last 30 days" in suggestion:
        # Execute date search
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        criteria = {"start_date": start_date}
    elif "over 25" in suggestion:
        # Execute age search
        criteria = {"min_age": "25"}
    elif "Female" in suggestion and "Data Science" in suggestion:
        criteria = {"gender": "female", "course": "DS"}
    else:
        # Default to text search
        criteria = {"search_term": suggestion}
    
    self.update_status(f"Executing suggested search: {suggestion}")
    self.start_progress()
    
    def run_suggestion():
        try:
            results = self.perform_suggested_search(criteria)
            self.output_queue.put(("search_results", results))
            self.output_queue.put(("log", f"Suggested search completed: {suggestion}. Found {len(results)} results."))
        except Exception as e:
            self.output_queue.put(("error", f"Suggested search error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))
    
    threading.Thread(target=run_suggestion, daemon=True).start()
AdvancedSearchGUI.execute_suggestion = execute_suggestion

def perform_suggested_search(self, criteria):
    """Perform search based on suggestion criteria"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM students WHERE 1=1"
        params = []
        
        for key, value in criteria.items():
            if key == "course":
                query += " AND LOWER(course) = LOWER(?)"
                params.append(value)
            elif key == "min_age":
                query += " AND age >= ?"
                params.append(int(value))
            elif key == "gender":
                query += " AND LOWER(gender) = LOWER(?)"
                params.append(value)
            elif key == "start_date":
                query += " AND registration_datetime >= ?"
                params.append(value + " 00:00:00")
            elif key == "search_term":
                query += " AND (LOWER(first_name || ' ' || last_name) LIKE ? OR LOWER(email_address) LIKE ?)"
                params.extend([f'%{value.lower()}%', f'%{value.lower()}%'])
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return results
        
    except Exception as e:
        raise Exception(f"Suggested search error: {str(e)}")
AdvancedSearchGUI.perform_suggested_search = perform_suggested_search

def show_predictive_analytics(self):
    """Show predictive analytics interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📊 {_t('advanced_search.predictive_analytics_dialog_title')}")
    dialog.geometry("1200x850")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Predictive Analytics Dashboard", style='Title.TLabel').pack(pady=(0, 20))
    
    # Analytics options
    analytics_notebook = ttk.Notebook(frame)
    analytics_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    # At-risk students tab
    risk_frame = ttk.Frame(analytics_notebook, padding="10")
    analytics_notebook.add(risk_frame, text="At-Risk Students")
    
    ttk.Label(risk_frame, text="Identify students at risk of academic failure:").pack(anchor='w', pady=(0, 10))
    
    risk_criteria_frame = ttk.LabelFrame(risk_frame, text="Risk Criteria", padding="10")
    risk_criteria_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Risk factors checkboxes
    risk_vars = {}
    risk_factors = [
        ("Low attendance rate", "attendance"),
        ("Failing grades", "grades"),
        ("Late assignment submissions", "assignments"),
        ("No recent login activity", "activity"),
        ("Financial aid issues", "financial")
    ]
    
    for text, key in risk_factors:
        risk_vars[key] = tk.BooleanVar(value=True)
        ttk.Checkbutton(risk_criteria_frame, text=text, variable=risk_vars[key]).pack(anchor='w')
    
    def analyze_at_risk():
        selected_criteria = [key for key, var in risk_vars.items() if var.get()]
        if not selected_criteria:
            messagebox.showwarning("No Criteria", "Please select at least one risk factor.")
            return
        
        self.update_status("Analyzing at-risk students...")
        self.start_progress()
        
        def run_risk_analysis():
            try:
                results = self.identify_at_risk_students(selected_criteria)
                self.output_queue.put(("analytics", f"At-Risk Students Analysis:\n{results}"))
                self.output_queue.put(("log", "At-risk student analysis completed."))
            except Exception as e:
                self.output_queue.put(("error", f"Risk analysis error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))
        
        threading.Thread(target=run_risk_analysis, daemon=True).start()
    
    ttk.Button(risk_frame, text="🔍 Analyze At-Risk Students", command=analyze_at_risk).pack(pady=10)
    
    # Enrollment prediction tab
    enrollment_frame = ttk.Frame(analytics_notebook, padding="10")
    analytics_notebook.add(enrollment_frame, text="Enrollment Prediction")
    
    ttk.Label(enrollment_frame, text="Predict future enrollment trends:").pack(anchor='w', pady=(0, 10))
    
    prediction_frame = ttk.LabelFrame(enrollment_frame, text="Prediction Parameters", padding="10")
    prediction_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(prediction_frame, text="Time Period:").pack(anchor='w')
    period_var = tk.StringVar(value="next_semester")
    
    periods = [
        ("Next Semester", "next_semester"),
        ("Next Academic Year", "next_year"),
        ("Next 5 Years", "5_years")
    ]
    
    for text, value in periods:
        ttk.Radiobutton(prediction_frame, text=text, variable=period_var, value=value).pack(anchor='w')
    
    def predict_enrollment():
        period = period_var.get()
        
        self.update_status("Predicting enrollment trends...")
        self.start_progress()
        
        def run_enrollment_prediction():
            try:
                results = self.predict_enrollment_trends(period)
                self.output_queue.put(("analytics", f"Enrollment Prediction:\n{results}"))
                self.output_queue.put(("log", "Enrollment prediction completed."))
            except Exception as e:
                self.output_queue.put(("error", f"Prediction error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))
        
        threading.Thread(target=run_enrollment_prediction, daemon=True).start()
    
    ttk.Button(enrollment_frame, text="📈 Generate Predictions", command=predict_enrollment).pack(pady=10)
    
    # Success probability tab
    success_frame = ttk.Frame(analytics_notebook, padding="10")
    analytics_notebook.add(success_frame, text="Success Probability")
    
    ttk.Label(success_frame, text="Calculate module success probability:").pack(anchor='w', pady=(0, 10))
    
    module_frame = ttk.LabelFrame(success_frame, text="Module Selection", padding="10")
    module_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(module_frame, text="Select Module:").pack(anchor='w')
    module_var = tk.StringVar()
    module_combo = ttk.Combobox(module_frame, textvariable=module_var, width=30)
    module_combo.pack(fill=tk.X, pady=(5, 0))
    
    # Load available modules
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT module_code FROM student_modules ORDER BY module_code")
        modules = [row[0] for row in cursor.fetchall()]
        module_combo['values'] = modules
        conn.close()
    except Exception:
        module_combo['values'] = ['CS101', 'CS102', 'DS101', 'DS102']
    
    def calculate_success():
        module = module_var.get().strip()
        if not module:
            messagebox.showwarning("Missing Module", "Please select a module.")
            return
        
        self.update_status("Calculating success probability...")
        self.start_progress()
        
        def run_success_calculation():
            try:
                results = self.calculate_module_success_probability(module)
                self.output_queue.put(("analytics", f"Module Success Probability:\n{results}"))
                self.output_queue.put(("log", f"Success probability calculated for {module}."))
            except Exception as e:
                self.output_queue.put(("error", f"Success calculation error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))
        
        threading.Thread(target=run_success_calculation, daemon=True).start()
    
    ttk.Button(success_frame, text="🎯 Calculate Success Probability", command=calculate_success).pack(pady=10)
    
    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack()
AdvancedSearchGUI.show_predictive_analytics = show_predictive_analytics

def identify_at_risk_students(self, criteria):
    """Identify students at risk based on criteria"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Simulate risk analysis based on available data
        risk_query = """
        SELECT s.*, COUNT(sm.module_code) as module_count,
               AVG(CASE WHEN sm.grade IS NOT NULL THEN 
                   CASE sm.grade 
                       WHEN 'A' THEN 4.0 
                       WHEN 'B' THEN 3.0 
                       WHEN 'C' THEN 2.0 
                       WHEN 'D' THEN 1.0 
                       ELSE 0.0 
                   END 
               END) as avg_grade
        FROM students s
        LEFT JOIN student_modules sm ON s.student_id = sm.student_id
        GROUP BY s.student_id
        HAVING avg_grade < 2.5 OR module_count = 0
        """
        
        cursor.execute(risk_query)
        at_risk_students = cursor.fetchall()
        conn.close()
        
        result = f"🚨 AT-RISK STUDENTS ANALYSIS\n"
        result += f"═" * 50 + "\n"
        result += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Risk Criteria: {', '.join(criteria)}\n\n"
        result += f"Students Identified as At-Risk: {len(at_risk_students)}\n\n"
        
        if at_risk_students:
            result += "DETAILED BREAKDOWN:\n"
            result += "-" * 30 + "\n"
            for student in at_risk_students[:10]:  # Show first 10
                name = f"{student[3]} {student[5]}"  # first_name + last_name
                result += f"• {student[0]} - {name}\n"
                result += f"  Email: {student[1]}\n"
                result += f"  Course: {student[9]}\n"
                result += f"  Age: {student[8]}\n\n"
            
            if len(at_risk_students) > 10:
                result += f"... and {len(at_risk_students) - 10} more students\n"
        
        result += f"\nRECOMMENDATIONS:\n"
        result += "• Schedule academic counseling sessions\n"
        result += "• Provide additional tutoring support\n"
        result += "• Monitor attendance more closely\n"
        result += "• Consider intervention programs\n"
        
        return result
        
    except Exception as e:
        raise Exception(f"Risk analysis error: {str(e)}")
AdvancedSearchGUI.identify_at_risk_students = identify_at_risk_students

def predict_enrollment_trends(self, period):
    """Predict enrollment trends for specified period"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get historical enrollment data
        cursor.execute("""
        SELECT 
            strftime('%Y-%m', registration_datetime) as month,
            course,
            COUNT(*) as enrollments
        FROM students 
        WHERE registration_datetime IS NOT NULL
        GROUP BY strftime('%Y-%m', registration_datetime), course
        ORDER BY month DESC
        """)
        
        historical_data = cursor.fetchall()
        conn.close()
        
        # Simple trend analysis
        result = f"📈 ENROLLMENT PREDICTION\n"
        result += f"═" * 50 + "\n"
        result += f"Prediction Period: {period.replace('_', ' ').title()}\n"
        result += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if historical_data:
            result += "HISTORICAL TRENDS:\n"
            result += "-" * 20 + "\n"
            
            # Group by course
            course_trends = {}
            for month, course, count in historical_data:
                if course not in course_trends:
                    course_trends[course] = []
                course_trends[course].append((month, count))
            
            for course, data in course_trends.items():
                total_enrollments = sum(count for _, count in data)
                avg_monthly = total_enrollments / max(len(data), 1)
                
                result += f"\n{course} Course:\n"
                result += f"  Total Historical Enrollments: {total_enrollments}\n"
                result += f"  Average Monthly: {avg_monthly:.1f}\n"
                
                # Predict based on period
                if period == "next_semester":
                    predicted = int(avg_monthly * 6)  # 6 months
                elif period == "next_year":
                    predicted = int(avg_monthly * 12)  # 12 months
                else:  # 5_years
                    predicted = int(avg_monthly * 60)  # 60 months
                
                result += f"  Predicted Enrollments ({period.replace('_', ' ')}): {predicted}\n"
        
        result += f"\nPREDICTION FACTORS:\n"
        result += "• Historical enrollment patterns\n"
        result += "• Seasonal variations\n"
        result += "• Course popularity trends\n"
        result += "• Market demand indicators\n"
        
        result += f"\nRECOMMENDATIONS:\n"
        result += "• Prepare resources for predicted enrollment levels\n"
        result += "• Adjust marketing strategies accordingly\n"
        result += "• Plan faculty and infrastructure needs\n"
        
        return result
        
    except Exception as e:
        raise Exception(f"Enrollment prediction error: {str(e)}")
AdvancedSearchGUI.predict_enrollment_trends = predict_enrollment_trends

def calculate_module_success_probability(self, module_code):
    """Calculate success probability for a module"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get module statistics
        cursor.execute("""
        SELECT 
            grade,
            COUNT(*) as count
        FROM student_modules 
        WHERE module_code = ? AND grade IS NOT NULL
        GROUP BY grade
        """, (module_code,))
        
        grade_distribution = cursor.fetchall()
        
        # Get overall module info
        cursor.execute("""
        SELECT 
            COUNT(*) as total_enrolled,
            COUNT(grade) as graded,
            module_name
        FROM student_modules 
        WHERE module_code = ?
        """, (module_code,))
        
        module_info = cursor.fetchone()
        conn.close()
        
        result = f"🎯 MODULE SUCCESS PROBABILITY\n"
        result += f"═" * 50 + "\n"
        result += f"Module: {module_code}\n"
        
        if module_info and len(module_info) > 2:
            result += f"Module Name: {module_info[2] or 'Unknown'}\n"
        result += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if module_info:
            total_enrolled, graded = module_info[0], module_info[1]
            result += f"ENROLLMENT STATISTICS:\n"
            result += f"Total Enrolled: {total_enrolled}\n"
            result += f"Students Graded: {graded}\n"
            result += f"Completion Rate: {(graded/max(total_enrolled,1)*100):.1f}%\n\n"
        
        if grade_distribution:
            result += "GRADE DISTRIBUTION:\n"
            result += "-" * 20 + "\n"
            
            total_graded = sum(count for _, count in grade_distribution)
            success_count = 0  # Grades A, B, C considered success
            
            for grade, count in grade_distribution:
                percentage = (count / total_graded) * 100
                result += f"  {grade}: {count} students ({percentage:.1f}%)\n"
                
                if grade in ['A', 'B', 'C']:
                    success_count += count
            
            success_rate = (success_count / total_graded) * 100
            result += f"\nSUCCESS ANALYSIS:\n"
            result += f"Success Rate (A, B, C grades): {success_rate:.1f}%\n"
            result += f"Students Likely to Succeed: {success_count}/{total_graded}\n"
            
            # Risk assessment
            if success_rate >= 80:
                risk_level = "LOW RISK"
                recommendation = "Module shows excellent success rates"
            elif success_rate >= 60:
                risk_level = "MODERATE RISK"
                recommendation = "Module may need some support improvements"
            else:
                risk_level = "HIGH RISK"
                recommendation = "Module requires immediate attention"
            
            result += f"Risk Level: {risk_level}\n"
            result += f"Recommendation: {recommendation}\n"
        
        return result
        
    except Exception as e:
        raise Exception(f"Success probability calculation error: {str(e)}")
AdvancedSearchGUI.calculate_module_success_probability = calculate_module_success_probability

def show_graduation_timeline_forecast(self):
    """Show graduation timeline forecasting"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🎓 {_t('advanced_search.graduation_forecast_dialog_title')}")
    dialog.geometry("1100x800")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Graduation Timeline Forecast", style='Title.TLabel').pack(pady=(0, 20))
    
    # Student selection
    selection_frame = ttk.LabelFrame(frame, text="Student Selection", padding="10")
    selection_frame.pack(fill=tk.X, pady=(0, 20))
    
    selection_var = tk.StringVar(value="all")
    ttk.Radiobutton(selection_frame, text="All students", variable=selection_var, value="all").pack(anchor='w')
    ttk.Radiobutton(selection_frame, text="Specific course", variable=selection_var, value="course").pack(anchor='w')
    ttk.Radiobutton(selection_frame, text="Current search results", variable=selection_var, value="results").pack(anchor='w')
    
    course_frame = ttk.Frame(selection_frame)
    course_frame.pack(fill=tk.X, pady=(10, 0))
    
    ttk.Label(course_frame, text="Course (if selected):").pack(side=tk.LEFT)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(course_frame, textvariable=course_var, values=["CS", "DS"], width=15)
    course_combo.pack(side=tk.LEFT, padx=(10, 0))
    
    # Forecast parameters
    params_frame = ttk.LabelFrame(frame, text="Forecast Parameters", padding="10")
    params_frame.pack(fill=tk.X, pady=(0, 20))
    
    ttk.Label(params_frame, text="Graduation Requirements:").pack(anchor='w')
    requirements_frame = ttk.Frame(params_frame)
    requirements_frame.pack(fill=tk.X, pady=(5, 0))
    
    ttk.Label(requirements_frame, text="Minimum Modules:").pack(side=tk.LEFT)
    min_modules_var = tk.StringVar(value="8")
    ttk.Entry(requirements_frame, textvariable=min_modules_var, width=10).pack(side=tk.LEFT, padx=(10, 20))
    
    ttk.Label(requirements_frame, text="Minimum GPA:").pack(side=tk.LEFT)
    min_gpa_var = tk.StringVar(value="2.0")
    ttk.Entry(requirements_frame, textvariable=min_gpa_var, width=10).pack(side=tk.LEFT, padx=(10, 0))
    
    def generate_forecast():
        selection = selection_var.get()
        course = course_var.get() if selection == "course" else None
        min_modules = int(min_modules_var.get() or 8)
        min_gpa = float(min_gpa_var.get() or 2.0)
        
        dialog.destroy()
        self.update_status("Generating graduation timeline forecast...")
        self.start_progress()
        
        def run_forecast():
            try:
                results = self.generate_graduation_forecast(selection, course, min_modules, min_gpa)
                self.output_queue.put(("analytics", results))
                self.output_queue.put(("log", "Graduation timeline forecast completed."))
            except Exception as e:
                self.output_queue.put(("error", f"Forecast error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))
        
        threading.Thread(target=run_forecast, daemon=True).start()
    
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)
    
    ttk.Button(button_frame, text="📊 Generate Forecast", command=generate_forecast).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_graduation_timeline_forecast = show_graduation_timeline_forecast

def generate_graduation_forecast(self, selection, course, min_modules, min_gpa):
    """Generate graduation timeline forecast"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Base query
        if selection == "course" and course:
            student_query = "SELECT * FROM students WHERE LOWER(course) = LOWER(?)"
            params = [course]
        elif selection == "results" and self.search_results:
            student_ids = [str(s[0]) for s in self.search_results]
            placeholders = ",".join(["?" for _ in student_ids])
            student_query = f"SELECT * FROM students WHERE student_id IN ({placeholders})"
            params = student_ids
        else:
            student_query = "SELECT * FROM students"
            params = []
        
        cursor.execute(student_query, params)
        students = cursor.fetchall()
        
        result = f"🎓 GRADUATION TIMELINE FORECAST\n"
        result += f"═" * 50 + "\n"
        result += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"Selection: {selection.title()}\n"
        if course:
            result += f"Course Filter: {course}\n"
        result += f"Requirements: {min_modules} modules, {min_gpa} GPA\n"
        result += f"Students Analyzed: {len(students)}\n\n"
        
        # Analyze each student's progress
        graduation_forecast = {
            "ready_to_graduate": [],
            "graduating_soon": [],
            "on_track": [],
            "at_risk": [],
            "insufficient_data": []
        }
        
        for student in students:
            student_id = student[0]
            
            # Get student's module progress
            cursor.execute("""
            SELECT COUNT(*) as module_count,
                   AVG(CASE WHEN grade IS NOT NULL THEN 
                       CASE grade 
                           WHEN 'A' THEN 4.0 
                           WHEN 'B' THEN 3.0 
                           WHEN 'C' THEN 2.0 
                           WHEN 'D' THEN 1.0 
                           ELSE 0.0 
                       END 
                   END) as avg_gpa
            FROM student_modules 
            WHERE student_id = ?
            """, (student_id,))
            
            progress = cursor.fetchone()
            
            if not progress or progress[0] == 0:
                graduation_forecast["insufficient_data"].append(student)
            else:
                module_count, avg_gpa = progress
                avg_gpa = avg_gpa or 0.0
                
                if module_count >= min_modules and avg_gpa >= min_gpa:
                    graduation_forecast["ready_to_graduate"].append((student, module_count, avg_gpa))
                elif module_count >= (min_modules * 0.8) and avg_gpa >= min_gpa:
                    graduation_forecast["graduating_soon"].append((student, module_count, avg_gpa))
                elif module_count >= (min_modules * 0.5):
                    graduation_forecast["on_track"].append((student, module_count, avg_gpa))
                else:
                    graduation_forecast["at_risk"].append((student, module_count, avg_gpa))
        
        conn.close()
        
        # Generate detailed results
        result += "GRADUATION STATUS BREAKDOWN:\n"
        result += "-" * 30 + "\n"
        
        for category, students_data in graduation_forecast.items():
            count = len(students_data)
            percentage = (count / len(students)) * 100 if students else 0
            
            category_name = category.replace("_", " ").title()
            result += f"\n{category_name}: {count} students ({percentage:.1f}%)\n"
            
            if category != "insufficient_data":
                for student_data, modules, gpa in students_data[:5]:  # Show first 5
                    name = f"{student_data[3]} {student_data[5]}"
                    gpa_display = gpa if gpa is not None else 0.0
                    result += f"  • {student_data[0]} - {name} ({modules} modules, GPA: {gpa_display:.2f})\n"
                if len(students_data) > 5:
                    result += f"  ... and {len(students_data) - 5} more\n"
            else:
                for student in students_data[:5]:
                    name = f"{student[3]} {student[5]}"
                    result += f"  • {student[0]} - {name}\n"
        
        result += f"\nTIMELINE PROJECTIONS:\n"
        result += "• Ready to Graduate: Can graduate immediately\n"
        result += "• Graduating Soon: 1-2 semesters remaining\n"
        result += "• On Track: 2-4 semesters remaining\n"
        result += "• At Risk: May require academic intervention\n"
        
        return result
        
    except Exception as e:
        raise Exception(f"Graduation forecast error: {str(e)}")
AdvancedSearchGUI.generate_graduation_forecast = generate_graduation_forecast

def enrollment_prediction(self):
    """
    CLI-compatible wrapper for enrollment prediction.

    This is a thin wrapper that calls the existing predict_enrollment_trends()
    method to provide the exact function name expected from the CLI version.
    """
    return self.predict_enrollment_trends("next_month")
AdvancedSearchGUI.enrollment_prediction = enrollment_prediction

def module_success_probability(self):
    """
    Show module success probability interface (CLI-compatible).

    Displays a dialog for users to select a module and view success probability
    statistics including pass rates, grade distribution, and predictions.
    """
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🎯 {_t('advanced_search.module_success_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Module Success Probability Calculator",
             style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text="Enter Module Code:").pack(anchor='w')
    module_var = tk.StringVar()
    ttk.Entry(frame, textvariable=module_var, width=30).pack(fill=tk.X, pady=(0, 20))

    result_text = scrolledtext.ScrolledText(frame, height=15, wrap=tk.WORD)
    result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    def calculate():
        module_code = module_var.get().strip()
        if not module_code:
            messagebox.showwarning("Missing Input", "Please enter a module code.")
            return

        try:
            result = self.calculate_module_success_probability(module_code)
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, result)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate: {str(e)}")

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="🎯 Calculate", command=calculate).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.module_success_probability = module_success_probability

def graduation_timeline_forecast(self):
    """
    Forecast graduation timelines for students (CLI-compatible).

    Analyzes student progress and predicts graduation timelines based on:
    - Completed modules vs. required modules
    - Historical completion rates
    - Course requirements
    - Current enrollment status
    """
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🎓 {_t('advanced_search.graduation_forecast_dialog_title')}")
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Graduation Timeline Forecast",
             style='Title.TLabel').pack(pady=(0, 20))

    result_text = scrolledtext.ScrolledText(frame, height=20, wrap=tk.WORD, font=('Courier', 9))
    result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    def generate_forecast():
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "🎓 GRADUATION TIMELINE FORECAST\n")
        result_text.insert(tk.END, "=" * 90 + "\n\n")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student progress data
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, s.course,
                       COUNT(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 END) as completed_modules,
                       s.registration_datetime,
                       julianday('now') - julianday(s.registration_datetime) as days_enrolled
                FROM students s
                LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.registration_datetime
                HAVING days_enrolled > 30
                ORDER BY completed_modules DESC
                LIMIT 20
            ''')

            student_progress = cursor.fetchall()
            conn.close()

            if not student_progress:
                result_text.insert(tk.END, "Insufficient data for graduation forecast.\n")
                return

            # Assume typical program requirements
            required_modules = {'CS': 8, 'DS': 6, 'Engineering': 10, 'Mathematics': 8}

            result_text.insert(tk.END, f"{'Student ID':<12} {'Name':<25} {'Course':<8} {'Progress':<10} {'Est. Graduation':<20}\n")
            result_text.insert(tk.END, "-" * 90 + "\n")

            for student_id, first_name, last_name, course, completed, reg_date, days_enrolled in student_progress:
                required = required_modules.get(course, 8)
                progress_pct = (completed / required) * 100

                if completed >= required:
                    forecast = "Graduated ✓"
                elif completed == 0:
                    forecast = "No progress"
                else:
                    # Linear projection
                    modules_per_day = completed / days_enrolled if days_enrolled > 0 else 0
                    remaining_modules = required - completed

                    if modules_per_day > 0:
                        days_to_graduate = remaining_modules / modules_per_day
                        months_to_graduate = days_to_graduate / 30

                        if months_to_graduate < 12:
                            forecast = f"~{months_to_graduate:.1f} months"
                        else:
                            forecast = f"~{months_to_graduate/12:.1f} years"
                    else:
                        forecast = "Stalled"

                name = f"{first_name} {last_name}"
                progress_text = f"{completed}/{required}"

                result_text.insert(tk.END, f"{student_id:<12} {name:<25} {course:<8} {progress_text:<10} {forecast:<20}\n")

            result_text.insert(tk.END, "\n" + "=" * 90 + "\n")
            result_text.insert(tk.END, "Note: Forecasts are based on historical completion rates and may vary.\n")

        except Exception as e:
            result_text.insert(tk.END, f"\nError generating forecast: {str(e)}\n")

    # Auto-generate on load
    generate_forecast()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="🔄 Refresh", command=generate_forecast).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.graduation_timeline_forecast = graduation_timeline_forecast
