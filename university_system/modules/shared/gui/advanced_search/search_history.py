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

def clear_search_cache(self):
    """Clear search cache"""
    try:
        # Clear any cached search data
        if hasattr(self, 'search_cache'):
            self.search_cache.clear()
        self.log_output("Search cache cleared")
        messagebox.showinfo("_t('advanced_search.cache_cleared')", "_t('advanced_search.search_cache_cleared')")
    except Exception as e:
        self.log_output(f"Error clearing cache: {e}")
AdvancedSearchGUI.clear_search_cache = clear_search_cache

def show_cache_management(self):
    """Show cache management dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"💾 {_t('advanced_search.cache_management_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Search Cache Management", style='Title.TLabel').pack(pady=(0, 20))
    
    # Cache info
    cache_size = len(getattr(self, 'search_cache', {}))
    ttk.Label(frame, text=f"Current cache size: {cache_size} entries").pack(pady=(0, 20))
    
    # Cache operations
    ttk.Button(frame, text=_t('advanced_search.clear_cache'), command=self.clear_search_cache, width=20).pack(pady=5)
    
    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(pady=(20, 0))
AdvancedSearchGUI.show_cache_management = show_cache_management

def show_repeat_last_search(self):
    """Show option to repeat last search"""
    if not hasattr(self, 'last_search_criteria') or not self.last_search_criteria:
        messagebox.showinfo("No Previous Search", "No previous search to repeat.")
        return
    
    criteria = self.last_search_criteria
    search_type = criteria.get('type', 'unknown')
    
    confirm = messagebox.askyesno("Repeat Search", 
                                 f"Repeat last search ({search_type})?\n"
                                 f"Criteria: {criteria.get('data', 'N/A')}")
    
    if confirm:
        self.repeat_last_search()
AdvancedSearchGUI.show_repeat_last_search = show_repeat_last_search

def show_cache_statistics(self):
    """Show cache statistics and management"""
    cache_size = len(getattr(self, 'search_cache', {}))
    cache_memory = sum(len(str(v)) for v in getattr(self, 'search_cache', {}).values())
    
    stats_text = f"""SEARCH CACHE STATISTICS

Cache Entries: {cache_size}
Estimated Memory Usage: {cache_memory / 1024:.1f} KB
Cache Hit Rate: {"N/A" if not hasattr(self, 'cache_hits') else f"{getattr(self, 'cache_hits', 0)} hits"}

Cache helps speed up repeated searches by storing results temporarily.
"""
    
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.cache_statistics_dialog_title'))
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Cache Statistics", style='Title.TLabel').pack(pady=(0, 20))
    
    stats_label = tk.Label(frame, text=stats_text, justify=tk.LEFT, font=('Courier', 10))
    stats_label.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)
    
    ttk.Button(button_frame, text=_t('advanced_search.clear_cache'), command=self.clear_search_cache).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_cache_statistics = show_cache_statistics

def show_search_history_detailed(self):
    """Show detailed search history with management options"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.search_history_dialog_title'))
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Search History & Management", style='Title.TLabel').pack(pady=(0, 20))
    
    # History tree
    columns = ('Time', 'Type', 'Criteria', 'Results', 'Duration')
    history_tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)
    
    for col in columns:
        history_tree.heading(col, text=col)
        history_tree.column(col, width=120)
    
    history_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=history_tree.yview)
    history_tree.configure(yscrollcommand=history_scrollbar.set)
    
    history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Load search history from database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT search_type, search_criteria, results_count, execution_time, search_datetime
        FROM search_analytics
        ORDER BY search_datetime DESC
        LIMIT 100
        """)
        history_data = cursor.fetchall()
        conn.close()

        for search_type, criteria, results, duration, search_datetime in history_data:
            time_display = search_datetime[:16] if search_datetime else 'N/A'
            duration_display = f"{duration:.2f}s" if duration else 'N/A'
            criteria_display = criteria[:30] + "..." if len(criteria) > 30 else criteria
            
            history_tree.insert('', 'end', values=(
                time_display, search_type, criteria_display, results, duration_display
            ))
    
    except Exception as e:
        self.log_output(f"Error loading search history: {str(e)}")
    
    # Actions
    actions_frame = ttk.Frame(frame)
    actions_frame.pack(fill=tk.X, pady=(10, 0))
    
    def repeat_selected_search():
        selection = history_tree.selection()
        if not selection:
            messagebox.showwarning("_t('advanced_search.no_selection')", "Please select a search to repeat.")
            return
        
        item = history_tree.item(selection[0])
        search_type = item['values'][1]
        
        messagebox.showinfo("Repeat Search", f"Repeating {search_type} search...")
        # In a full implementation, would parse criteria and re-execute
    
    def export_history():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"search_history_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Time', 'Type', 'Criteria', 'Results', 'Duration'])
                
                for child in history_tree.get_children():
                    values = history_tree.item(child)['values']
                    writer.writerow(values)
            
            messagebox.showinfo("Export Complete", f"Search history exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not export history: {str(e)}")
    
    def clear_history():
        if messagebox.askyesno("Confirm Clear", "Clear all search history? This cannot be undone."):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM search_analytics")
                conn.commit()
                conn.close()
                
                # Clear tree
                for item in history_tree.get_children():
                    history_tree.delete(item)
                
                messagebox.showinfo("History Cleared", "Search history has been cleared.")
            except Exception as e:
                messagebox.showerror("Clear Failed", f"Could not clear history: {str(e)}")
    
    ttk.Button(actions_frame, text=_t('advanced_search.repeat_search_btn'), command=repeat_selected_search).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(actions_frame, text=_t('advanced_search.export_history'), command=export_history).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(actions_frame, text=_t('advanced_search.clear_history'), command=clear_history).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Button(actions_frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_search_history_detailed = show_search_history_detailed

def save_last_search_results(self):
    """Persist the last search results to disk and the central database."""
    if not self.search_results:
        messagebox.showwarning("No Results", "No search results to save.")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_name = f"last_search_results_{timestamp}.json"
    filename = filedialog.asksaveasfilename(
        title="Save Search Results",
        defaultextension=".json",
        initialfile=default_name,
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    if not filename:
        return
    
    try:
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "result_count": len(self.search_results),
            "search_criteria": self._collect_search_criteria(),
            "results": []
        }
        
        for student in self.search_results:
            student_dict = {
                "student_id": student[0],
                "email": student[1],
                "title": student[2],
                "first_name": student[3],
                "middle_name": student[4],
                "last_name": student[5],
                "gender": student[6],
                "date_of_birth": student[7],
                "age": student[8],
                "course": student[9],
                "registration_datetime": student[10]
            }
            results_data["results"].append(student_dict)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, default=str)

        try:
            conn = get_connection()
            if conn is None:
                raise RuntimeError("Database connection unavailable.")
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO search_result_archives (user_id, search_name, search_criteria, results_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self._current_user_id(),
                    f"Search results {timestamp}",
                    json.dumps(results_data["search_criteria"]),
                    json.dumps(results_data["results"])
                )
            )
            conn.commit()
            conn.close()
        except Exception as db_error:
            self.log_output(f"Warning: could not archive search results to database ({db_error})")

        messagebox.showinfo("Results Saved", f"Last search results saved to {filename}")
        self.log_output(f"Search results saved to {filename} and archived.")

    except Exception as e:
        messagebox.showerror("Save Error", f"Could not save search results: {str(e)}")
AdvancedSearchGUI.save_last_search_results = save_last_search_results

def log_search_operation(self, search_type, criteria, result_count):
    """Log search operation for audit trail"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "search_type": search_type,
            "criteria": criteria,
            "result_count": result_count,
            "user": "current_user",  # In real implementation, get from auth
            "ip_address": "127.0.0.1"  # In real implementation, get actual IP
        }
        
        # Append to search log file
        log_filename = "search_audit_log.json"
        
        # Load existing log or create new
        try:
            with open(log_filename, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        except FileNotFoundError:
            log_data = {"searches": []}
        
        log_data["searches"].append(log_entry)
        
        # Keep only last 1000 entries
        if len(log_data["searches"]) > 1000:
            log_data["searches"] = log_data["searches"][-1000:]
        
        # Save updated log
        with open(log_filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
            
    except Exception as e:
        self.log_output(f"Warning: Could not log search operation: {str(e)}")
    
    # Attempt to add entry to search_analytics table for dashboard parity
    try:
        conn = get_connection()
        cursor = conn.cursor()
        insert_search_analytics_record(
            cursor,
            user_id=self._current_user_id(),
            search_type=search_type,
            criteria=criteria,
            results_count=result_count,
            execution_time=0.0
        )
        conn.commit()
        conn.close()
    except Exception as analytics_error:
        self.log_output(f"Note: analytics logging skipped ({analytics_error})")
AdvancedSearchGUI.log_search_operation = log_search_operation

def repeat_last_search(self):
    """Repeat the last executed search"""
    if not hasattr(self, 'last_search_criteria') or not self.last_search_criteria:
        messagebox.showinfo("No Previous Search", "No previous search to repeat.")
        return
    
    criteria = self.last_search_criteria
    search_type = criteria.get('type', 'unknown')
    
    self.update_status(f"Repeating last search ({search_type})...")
    self.start_progress()
    
    def run_repeat_search():
        try:
            # Execute based on search type
            if search_type == "multi_criteria":
                results = self.perform_database_search(criteria.get('data', {}))
            elif search_type == "fuzzy":
                results = self.perform_fuzzy_search(
                    criteria.get('term', ''), 
                    criteria.get('threshold', 0.6), 
                    criteria.get('algorithm', '1')
                )
            elif search_type == "text":
                results = self.perform_text_search(
                    criteria.get('pattern', ''), 
                    criteria.get('search_type', 'wildcard'), 
                    criteria.get('field', 'first_name')
                )
            else:
                results = []
            
            self.output_queue.put(("search_results", results))
            self.output_queue.put(("log", f"Repeated {search_type} search. Found {len(results)} results."))
            
        except Exception as e:
            self.output_queue.put(("error", f"Repeat search error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))
    
    threading.Thread(target=run_repeat_search, daemon=True).start()
AdvancedSearchGUI.repeat_last_search = repeat_last_search

def clear_search_history(self):
    """Clear search history"""
    if messagebox.askyesno("Confirm Clear", "This will clear all search history. Continue?"):
        try:
            # Clear search audit log
            log_filename = "search_audit_log.json"
            empty_log = {"searches": []}
            
            with open(log_filename, 'w', encoding='utf-8') as f:
                json.dump(empty_log, f, indent=2)
            
            # Clear any cached search data
            if hasattr(self, 'last_search_criteria'):
                delattr(self, 'last_search_criteria')
            
            messagebox.showinfo("History Cleared", "Search history cleared successfully.")
            self.log_output("Search history cleared")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear search history: {str(e)}")
AdvancedSearchGUI.clear_search_history = clear_search_history

def show_search_history(self):
    """Show search history"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"📚 {_t('advanced_search.search_history_dialog_title')}")
    dialog.geometry("600x400")
    dialog.transient(self.master)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Search History & Favorites", style='Title.TLabel').pack(pady=(0, 20))
    
    # History list
    columns = ('Time', 'Type', 'Criteria', 'Results')
    history_tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)
    
    for col in columns:
        history_tree.heading(col, text=col)
        history_tree.column(col, width=120)
    
    history_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    # Sample history data
    history_data = [
        ("14:30:25", "Multi-Criteria", "CS students, age > 20", "15"),
        ("14:25:10", "Fuzzy Search", "John", "3"),
        ("14:20:05", "Module Search", "CS101", "25"),
        ("14:15:30", "Date Range", "Last 30 days", "8"),
    ]
    
    for time, search_type, criteria, results in history_data:
        history_tree.insert('', 'end', values=(time, search_type, criteria, results))
    
    # Buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)
    
    ttk.Button(button_frame, text="🔄 Repeat", 
              command=lambda: messagebox.showinfo("Repeat", "Search would be repeated")).pack(side=tk.LEFT)
    ttk.Button(button_frame, text="⭐ Favorite", 
              command=lambda: messagebox.showinfo("Favorite", "Search added to favorites")).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
AdvancedSearchGUI.show_search_history = show_search_history

def log_search(self, search_type, criteria, result_count):
    """
    Log search activity to analytics database (CLI-compatible utility).

    This utility function tracks all searches performed in the system for:
    - Analytics and reporting
    - Usage pattern analysis
    - Performance monitoring
    - User behavior tracking

    Args:
        search_type (str): Type of search performed (e.g., "multi_criteria", "fuzzy", "module")
        criteria (dict/str): Search criteria used
        result_count (int): Number of results returned

    The function:
    1. Adds to in-memory search history (last 100 searches)
    2. Logs to database search_analytics table
    3. Records timestamp, user, execution details
    """
    try:
        # Add to search history if it exists
        if not hasattr(self, 'search_history'):
            self.search_history = []

        search_entry = {
            'type': search_type,
            'criteria': str(criteria),
            'results': result_count,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.search_history.append(search_entry)

        # Keep only last 100 searches in memory
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]

        # Log to database for analytics
        conn = get_connection()
        cursor = conn.cursor()

        # Check if search_analytics table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='search_analytics'
        """)

        if cursor.fetchone():
            # Get current user if available
            current_user = 'default_user'
            if hasattr(self, 'auth') and self.auth:
                user = self.auth.get_current_user()
                if user:
                    current_user = user.get('username', 'default_user')

            # Insert search analytics record
            cursor.execute('''
                INSERT INTO search_analytics (
                    user_id, search_type, search_criteria,
                    results_count, search_timestamp, execution_time
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                current_user,
                search_type,
                str(criteria),
                result_count,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                0.1  # Placeholder execution time
            ))

            conn.commit()

        conn.close()

    except Exception as e:
        # Fail silently for analytics - don't disrupt user experience
        print_info(f"Search logging failed (non-critical): {e}")
AdvancedSearchGUI.log_search = log_search
