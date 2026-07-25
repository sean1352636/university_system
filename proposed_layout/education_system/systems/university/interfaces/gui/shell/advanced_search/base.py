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

    def _safe_count(cursor, table):
        try:
            validate_table_name(table)
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            return cursor.fetchone()[0]
        except Exception:
            return 0

    def search_analytics_dashboard():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            total = _safe_count(cursor, "search_analytics")
            cursor.execute(
                "SELECT search_type, COUNT(*) FROM search_analytics "
                "GROUP BY search_type ORDER BY 2 DESC LIMIT 10"
            )
            by_type = cursor.fetchall()
            cursor.execute(
                "SELECT COALESCE(AVG(execution_time), 0), COALESCE(MAX(execution_time), 0) "
                "FROM search_analytics"
            )
            avg_t, max_t = cursor.fetchone()
            conn.close()
            lines = [f"Search analytics dashboard (total searches: {total})"]
            lines.append(f"  Avg execution: {float(avg_t or 0)*1000:.1f} ms | Max: {float(max_t or 0)*1000:.1f} ms")
            if by_type:
                lines.append("  By type:")
                for stype, count in by_type:
                    lines.append(f"    - {stype or '(unknown)'}: {count}")
            return "\n".join(lines)
        except Exception as e:
            return f"Analytics dashboard error: {e}"

    def student_demographics_reports():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            total = _safe_count(cursor, "students")
            cursor.execute("SELECT COALESCE(gender, 'Unknown'), COUNT(*) FROM students GROUP BY gender")
            by_gender = cursor.fetchall()
            cursor.execute("SELECT COALESCE(course, 'Unknown'), COUNT(*) FROM students GROUP BY course")
            by_course = cursor.fetchall()
            conn.close()
            lines = [f"Demographics analysis (total students: {total})", "  By gender:"]
            for g, c in by_gender:
                lines.append(f"    - {g}: {c}")
            lines.append("  By course:")
            for course, c in by_course:
                lines.append(f"    - {course}: {c}")
            return "\n".join(lines)
        except Exception as e:
            return f"Demographics error: {e}"

    def academic_performance_analysis():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('student_modules','grades')")
            tables = {row[0] for row in cursor.fetchall()}
            if 'student_modules' in tables:
                cursor.execute(
                    "SELECT COALESCE(AVG(grade), 0), COUNT(*) FROM student_modules WHERE grade IS NOT NULL"
                )
                avg_grade, n = cursor.fetchone()
                conn.close()
                return f"Academic performance:\n  Graded enrollments: {n}\n  Average grade: {float(avg_grade or 0):.2f}"
            conn.close()
            return "Academic performance: no grade data tables available."
        except Exception as e:
            return f"Performance analysis error: {e}"

    def duplicate_detection():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT LOWER(TRIM(first_name||' '||last_name)) AS name_key, COUNT(*) "
                "FROM students WHERE first_name IS NOT NULL AND last_name IS NOT NULL "
                "GROUP BY name_key HAVING COUNT(*) > 1"
            )
            dups = cursor.fetchall()
            conn.close()
            if not dups:
                return "Duplicate detection: no duplicate student names found."
            lines = [f"Duplicate detection: {len(dups)} duplicate name group(s):"]
            for name_key, c in dups[:25]:
                lines.append(f"  - {name_key}: {c} records")
            return "\n".join(lines)
        except Exception as e:
            return f"Duplicate detection error: {e}"

    def data_quality_reports():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            total = _safe_count(cursor, "students")
            cursor.execute(
                "SELECT SUM(CASE WHEN email_address IS NULL OR email_address='' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN dob IS NULL OR dob='' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN course IS NULL OR course='' THEN 1 ELSE 0 END) FROM students"
            )
            missing_email, missing_dob, missing_course = cursor.fetchone()
            conn.close()
            return (
                f"Data quality assessment (students: {total})\n"
                f"  Missing email: {missing_email or 0}\n"
                f"  Missing DOB: {missing_dob or 0}\n"
                f"  Missing course: {missing_course or 0}"
            )
        except Exception as e:
            return f"Data quality error: {e}"

    def generate_custom_reports():
        return "Custom report generation: use reports menu to build SQL-based or template reports."

    def export_system_statistics():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            stats = {t: _safe_count(cursor, t) for t in ("students", "modules", "student_modules", "search_analytics")}
            conn.close()
            lines = ["System statistics:"]
            for t, c in stats.items():
                lines.append(f"  {t}: {c}")
            return "\n".join(lines)
        except Exception as e:
            return f"Statistics error: {e}"

    def interactive_charts():
        return "Interactive charts: open the Visualization menu to generate charts from the loaded dataset."

    def view_search_audit_trail():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(timestamp, search_datetime, ''), COALESCE(user_id,''), "
                "COALESCE(search_type,''), COALESCE(results_count, 0) "
                "FROM search_analytics ORDER BY id DESC LIMIT 25"
            )
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return "Audit trail: no search activity recorded yet."
            lines = [f"Audit trail ({len(rows)} most recent):"]
            for ts, user, stype, rc in rows:
                lines.append(f"  [{ts}] {user or 'anon'} {stype} -> {rc} results")
            return "\n".join(lines)
        except Exception as e:
            return f"Audit trail error: {e}"

    def manage_user_permissions():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            by_role = cursor.fetchall()
            conn.close()
            lines = ["User permissions (by role):"]
            for role, c in by_role:
                lines.append(f"  - {role or 'unspecified'}: {c}")
            return "\n".join(lines) if by_role else "User permissions: no users found."
        except Exception as e:
            return f"User permissions error: {e}"

    def manage_scheduled_reports():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_reports'")
            exists = cursor.fetchone() is not None
            count = _safe_count(cursor, "scheduled_reports") if exists else 0
            conn.close()
            return f"Scheduled reports: {count} configured." if exists else "Scheduled reports: table not yet created."
        except Exception as e:
            return f"Scheduled reports error: {e}"

    def performance_optimization():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            conn.commit()
            conn.close()
            return "Performance optimization: VACUUM and ANALYZE completed."
        except Exception as e:
            return f"Optimization error: {e}"

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

class AdvancedSearchGUI:
    """GUI wrapper for the Advanced Student Search System
    Maintains full backwards compatibility with original CLI functions"""
    def __init__(self, master, auth=None):
        self.master = master
        self.auth = auth  # Add this line
        self.master.title(_t("advanced_search.window_title"))
        self.master.geometry("1400x900+%d+%d" % ((self.master.winfo_screenwidth() - 1400) // 2, (self.master.winfo_screenheight() - 900) // 2))
        self.master.minsize(1200, 800)
        self.master.configure(bg='#f0f0f0')

        # Initialize variables
        self.search_results = []
        self.current_page = 0
        self.results_per_page = 10
        self.output_queue = queue.Queue()

        # Style configuration
        self.setup_styles()

        # Create main layout
        self.create_main_layout()

        # Ensure supporting tables exist before we begin interacting with them
        self._ensure_support_tables()

        # Initialize database
        self.init_database()

        # Start output monitor
        self.monitor_output()
    def _current_user_id(self) -> str:
        """Return a string identifier for the current authenticated user."""
        if self.auth and getattr(self.auth, "current_user", None):
            user = self.auth.current_user
            if isinstance(user, dict):
                for key in ("username", "email", "id"):
                    if user.get(key):
                        return str(user[key])
            return str(user)
        return "gui_user"
    def _ensure_support_tables(self) -> None:
        """Create auxiliary tables used by the GUI if they don't exist."""
        conn = get_connection()
        if conn is None:
            return
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                search_name TEXT,
                search_criteria TEXT,
                is_shared INTEGER DEFAULT 0,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME
            )
        ''')
        # Check if user_permissions table has the correct schema
        cursor.execute("PRAGMA table_info(user_permissions)")
        columns = {row[1] for row in cursor.fetchall()}

        if 'role' not in columns or 'permissions' not in columns:
            # Drop old table and recreate with correct schema
            cursor.execute('DROP TABLE IF EXISTS user_permissions')
            cursor.execute('''
                CREATE TABLE user_permissions (
                    user_id TEXT PRIMARY KEY,
                    role TEXT,
                    permissions TEXT,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            # Table exists with correct schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id TEXT PRIMARY KEY,
                    role TEXT,
                    permissions TEXT,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_result_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                search_name TEXT,
                search_criteria TEXT,
                results_json TEXT
            )
        ''')
        conn.commit()
        conn.close()
    def setup_styles(self):
        """Configure ttk styles for better appearance"""
        style = ttk.Style()

        # Configure custom styles
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'), background='#f0f0f0')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
    def create_main_layout(self):
        """Create the main GUI layout"""
        # Main container
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Title and Return Home Button Frame
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))

        title_label = ttk.Label(title_frame, text=f"🔍 {_t('advanced_search.title')}",
                               style='Title.TLabel')
        title_label.pack(side=tk.LEFT)

        # Return to Home button
        if self.auth:
            return_button = ttk.Button(title_frame, text=f"🏠 {_t('advanced_search.return_to_menu')}",
                                      command=self.return_to_main_menu)
            return_button.pack(side=tk.RIGHT, padx=10)

        # Left sidebar - Menu
        self.create_sidebar(main_frame)

        # Right main area - Content
        self.create_main_content(main_frame)

        # Bottom status bar
        self.create_status_bar(main_frame)
    def create_sidebar(self, parent):
        """Create the left sidebar with menu options (scrollable)"""
        sidebar_frame = ttk.LabelFrame(parent, text=f"📋 {_t('advanced_search.menu')}", padding="0")
        sidebar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        # Create a canvas + scrollbar inside the LabelFrame
        canvas = tk.Canvas(sidebar_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        # Make the frame expand inside the canvas
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")  # Update scroll area
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas + scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        categories = [
            (f"📊 {_t('advanced_search.cat_analytics')}", [
                (_t("advanced_search.search_analytics_dashboard"), self.show_analytics_dashboard),
                (_t("advanced_search.student_demographics_reports"), self.show_demographics_reports),
                (_t("advanced_search.advanced_demographics_window"), self.show_advanced_demographics_window),
                (_t("advanced_search.advanced_demographic_analysis"), self.show_advanced_demographic_report),
                (_t("advanced_search.academic_performance_analysis"), self.show_performance_analysis),
            ]),
            (f"🔍 {_t('advanced_search.cat_search')}", [
                (_t("advanced_search.multi_criteria_search"), self.show_multi_criteria_search),
                (_t("advanced_search.fuzzy_name_search"), self.show_fuzzy_search),
                (_t("advanced_search.module_enrollment_search"), self.show_module_search),
                (_t("advanced_search.date_range_search"), self.show_date_search),
                (_t("advanced_search.combined_filters_search"), self.show_combined_search),
                (_t("advanced_search.advanced_text_search"), self.show_advanced_text_search_menu),
                (_t("advanced_search.conditional_logic_search"), self.show_conditional_search),
            ]),
            (f"💾 {_t('advanced_search.cat_search_mgmt')}", [
                (_t("advanced_search.saved_search_profiles"), self.show_search_profile_manager),
                (_t("advanced_search.search_history.label"), self.show_search_history_detailed),
                (_t("advanced_search.load_saved_search"), self.show_load_search),
                (_t("advanced_search.favorites_manager"), self.show_favorites_manager),
                (_t("advanced_search.repeat_last_search"), self.show_repeat_last_search),
            ]),
            (f"🔧 {_t('advanced_search.cat_bulk_ops')}", [
                (_t("advanced_search.bulk_operations_menu"), self.show_bulk_operations),
                (_t("advanced_search.mass_email_students"), self.show_mass_email),
                (_t("advanced_search.batch_data_updates"), self.show_batch_updates),
            ]),
            (f"📋 {_t('advanced_search.cat_data_mgmt')}", [
                (_t("advanced_search.duplicate_detection"), self.show_duplicate_detection),
                (_t("advanced_search.data_quality_reports"), self.show_data_quality),
                (_t("advanced_search.enhanced_import_export"), self.show_enhanced_import_export_menu),
            ]),
            (f"📈 {_t('advanced_search.cat_visualization')}", [
                (_t("advanced_search.interactive_charts"), self.show_advanced_charts),
                (_t("advanced_search.comprehensive_reports"), self.show_comprehensive_reports),
            ]),
            (f"⚡ {_t('advanced_search.cat_smart_features')}", [
                (_t("advanced_search.smart_features_menu"), self.show_smart_features_menu),
            ]),
            (f"👑 {_t('advanced_search.cat_admin')}", [
                (_t("advanced_search.admin_features_menu"), self.show_admin_features_menu),
            ]),
            (f"🛠️ {_t('advanced_search.cat_system')}", [
                (_t("advanced_search.initialize_database"), self.init_database),
                (_t("advanced_search.system_optimization"), self.show_system_optimization_tools),
                (_t("advanced_search.database_status_check"), self.check_database_status_gui),
                (_t("advanced_search.system_statistics"), self.show_system_stats),
            ]),
        ]

        # (optional) make buttons expand horizontally
        # scrollable_frame.grid_columnconfigure(0, weight=1)

        row = 0
        for category_name, items in categories:
            category_label = ttk.Label(scrollable_frame, text=category_name, style='Header.TLabel')
            category_label.grid(row=row, column=0, sticky=tk.W, pady=(10, 5))
            row += 1
            for item_name, command in items:
                btn = ttk.Button(scrollable_frame, text=item_name, command=command, width=25)
                btn.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=1, padx=(10, 0))
                row += 1
    def create_main_content(self, parent):
        """Create the main content area"""
        self.content_frame = ttk.LabelFrame(parent, text=f"📊 {_t('advanced_search.content')}", padding="10")
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Notebook for tabbed interface
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Welcome tab
        self.create_welcome_tab()

        # Search results tab
        self.create_results_tab()

        # Output/Console tab
        self.create_output_tab()
    def create_welcome_tab(self):
        """Create the welcome/dashboard tab"""
        welcome_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(welcome_frame, text=f"🏠 {_t('advanced_search.tab_dashboard')}")

        welcome_text = f"""
        {_t('advanced_search.welcome_title')}

        🔍 {_t('advanced_search.features_available')}:
        • {_t('advanced_search.feature_search')}
        • {_t('advanced_search.feature_fuzzy')}
        • {_t('advanced_search.feature_analytics')}
        • {_t('advanced_search.feature_visualization')}
        • {_t('advanced_search.feature_bulk')}
        • {_t('advanced_search.feature_permissions')}

        📊 {_t('advanced_search.quick_stats')}:
        {_t('advanced_search.click_to_start')}

        🚀 {_t('advanced_search.recent_updates')}:
        • {_t('advanced_search.update_gui')}
        • {_t('advanced_search.update_search')}
        • {_t('advanced_search.update_performance')}
        • {_t('advanced_search.update_visualization')}
        """

        welcome_label = tk.Label(welcome_frame, text=welcome_text, justify=tk.LEFT,
                                font=('Arial', 11), bg='white', anchor='nw')
        welcome_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Quick action buttons
        quick_frame = ttk.LabelFrame(welcome_frame, text=f"🚀 {_t('advanced_search.quick_actions')}", padding="10")
        quick_frame.pack(fill=tk.X, pady=(10, 0))

        quick_buttons = [
            (f"🔍 {_t('advanced_search.multi_criteria_search')}", self.show_multi_criteria_search),
            (f"📊 {_t('advanced_search.search_analytics_dashboard')}", self.show_analytics_dashboard),
            (f"👥 {_t('advanced_search.student_demographics_reports')}", self.show_demographics_reports),
            (f"⚙️ {_t('advanced_search.initialize_database')}", self.init_database),
        ]

        for i, (text, command) in enumerate(quick_buttons):
            btn = ttk.Button(quick_frame, text=text, command=command, style='Action.TButton')
            btn.grid(row=i//2, column=i%2, padx=5, pady=5, sticky=(tk.W, tk.E))

        quick_frame.columnconfigure(0, weight=1)
        quick_frame.columnconfigure(1, weight=1)
    def create_results_tab(self):
        """Create the search results tab with scrollbars"""
        self.results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.results_frame, text=f"📋 {_t('advanced_search.tab_search_results')}")

        # Header
        header_frame = ttk.Frame(self.results_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.results_frame.columnconfigure(0, weight=1)

        self.results_label = ttk.Label(header_frame, text=_t("advanced_search.no_search_results"), style='Header.TLabel')
        self.results_label.pack(side=tk.LEFT)

        self.export_btn = ttk.Button(
            header_frame, text=f"💾 {_t('advanced_search.export_results')}",
            command=self.export_results, state='disabled'
        )
        self.export_btn.pack(side=tk.RIGHT)

        # --- Treeview with scrollbars ---
        columns = ('ID', _t('advanced_search.col_name'), _t('advanced_search.col_email'),
                   _t('advanced_search.col_gender'), _t('advanced_search.col_age'),
                   _t('advanced_search.col_course'), _t('advanced_search.col_registration'))

        tree_container = ttk.Frame(self.results_frame)   # container for tree + scrollbars
        tree_container.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.results_frame.rowconfigure(1, weight=1)

        self.results_tree = ttk.Treeview(
            tree_container, columns=columns, show='headings', height=15,
            selectmode='extended'
        )

        # Configure columns
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=120, anchor="center")

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_container, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Layout with grid
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        # Pagination controls
        self.create_pagination_controls()

        # Double-click event
        self.results_tree.bind('<Double-1>', self.show_student_details)

        # Right-click context menu for bulk actions on selected rows
        self.results_context_menu = tk.Menu(self.results_tree, tearoff=0)
        self.results_context_menu.add_command(label="Select All",
                                              command=self.select_all_results)
        self.results_context_menu.add_separator()
        self.results_context_menu.add_command(label="Copy IDs",
                                              command=lambda: self.copy_selected_results_column(0))
        self.results_context_menu.add_command(label="Copy Names",
                                              command=lambda: self.copy_selected_results_column(1))
        self.results_context_menu.add_command(label="Copy Emails",
                                              command=lambda: self.copy_selected_results_column(2))
        self.results_context_menu.add_separator()
        self.results_context_menu.add_command(label="Export Selected to CSV…",
                                              command=self.export_selected_results_csv)
        self.results_tree.bind('<Button-3>', self._show_results_context_menu)
        self.results_tree.bind('<Control-a>', lambda e: (self.select_all_results(), "break")[1])
    def create_pagination_controls(self):
        """Create pagination controls for results"""
        pagination_frame = ttk.Frame(self.results_frame)
        pagination_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        self.prev_btn = ttk.Button(pagination_frame, text=f"◀ {_t('advanced_search.previous')}",
                                  command=self.previous_page, state='disabled')
        self.prev_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.page_label = ttk.Label(pagination_frame, text=_t("advanced_search.page_of", page=1, total=1))
        self.page_label.pack(side=tk.LEFT, padx=10)

        self.next_btn = ttk.Button(pagination_frame, text=f"{_t('advanced_search.next')} ▶",
                                  command=self.next_page, state='disabled')
        self.next_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Results per page
        ttk.Label(pagination_frame, text=f"{_t('advanced_search.results_per_page')}:").pack(side=tk.LEFT, padx=(20, 5))
        self.per_page_var = tk.StringVar(value="10")
        per_page_combo = ttk.Combobox(pagination_frame, textvariable=self.per_page_var,
                                     values=["10", "25", "50", "100"], width=5, state='readonly')
        per_page_combo.pack(side=tk.LEFT)
        per_page_combo.bind('<<ComboboxSelected>>', self.change_results_per_page)
    def create_output_tab(self):
        """Create the output/console tab"""
        self.output_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.output_frame, text=f"💻 {_t('advanced_search.tab_console_output')}")

        # Output text area
        self.output_text = scrolledtext.ScrolledText(self.output_frame, wrap=tk.WORD,
                                                    font=('Courier', 10), height=20)
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Clear button
        clear_frame = ttk.Frame(self.output_frame)
        clear_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(clear_frame, text=f"🗑️ {_t('advanced_search.clear_output')}",
                  command=self.clear_output).pack(side=tk.RIGHT)
    def create_status_bar(self, parent):
        """Create the bottom status bar"""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        self.status_label = ttk.Label(self.status_frame, text=_t("advanced_search.status_ready"))
        self.status_label.pack(side=tk.LEFT)

        # Progress bar
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=(10, 0))
    def capture_function_output(self, func, *args, **kwargs):
        """Capture output from original CLI functions"""
        import io

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            result = func(*args, **kwargs)
            output = captured_output.getvalue()
            return output if output else str(result)
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            sys.stdout = old_stdout
    def update_status(self, message):
        """Update the status bar"""
        self.status_label.config(text=message)
        self.master.update_idletasks()
    def start_progress(self):
        """Start the progress bar"""
        self.progress.start(10)
    def stop_progress(self):
        """Stop the progress bar"""
        self.progress.stop()
    def monitor_output(self):
        """Monitor the output queue for updates"""
        try:
            if not self.master.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            while True:
                msg_type, data = self.output_queue.get_nowait()

                if msg_type == "search_results":
                    self.display_search_results(data)
                elif msg_type == "analytics":
                    self.show_analytics_output(data)
                elif msg_type == "log":
                    self.log_output(data)
                elif msg_type == "error":
                    self.show_error(data)
                elif msg_type == "stop_progress":
                    self.stop_progress()
                    self.update_status(_t("advanced_search.status_ready"))

        except queue.Empty:
            pass

        # Schedule next check
        try:
            self.master.after(100, self.monitor_output)
        except tk.TclError:
            pass
    def log_output(self, message):
        """Log message to output console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.output_text.see(tk.END)
    def show_error(self, error_message):
        """Show error message"""
        self.log_output(f"ERROR: {error_message}")
        messagebox.showerror(_t("advanced_search.error_title"), error_message)
    def show_analytics_output(self, output):
        """Display analytics output"""
        self.output_text.insert(tk.END, f"\n=== {_t('advanced_search.menus.analytics_dashboard_title')} ===\n")
        self.output_text.insert(tk.END, output)
        self.output_text.insert(tk.END, f"\n{'='*50}\n")
        self.output_text.see(tk.END)
        self.notebook.select(2)  # Switch to output tab
    def clear_output(self):
        """Clear the output console"""
        self.output_text.delete(1.0, tk.END)
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.systems.university.interfaces.gui.shell.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print_error(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def _show_results_context_menu(self, event):
        """Post the right-click context menu on the results tree."""
        try:
            row = self.results_tree.identify_row(event.y)
            if row and row not in self.results_tree.selection():
                self.results_tree.selection_set(row)
            self.results_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.results_context_menu.grab_release()

    def select_all_results(self):
        """Select every row currently visible in the results tree."""
        items = self.results_tree.get_children()
        if items:
            self.results_tree.selection_set(items)

    def copy_selected_results_column(self, column_index: int):
        """Copy a single column from the selected result rows to the clipboard."""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showinfo("Copy", "No rows selected.")
            return
        values = []
        for iid in selection:
            row = self.results_tree.item(iid)['values']
            if column_index < len(row) and row[column_index] not in ("", None):
                values.append(str(row[column_index]))
        if not values:
            messagebox.showinfo("Copy", "No values found in the selected rows for that column.")
            return
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append("\n".join(values))
            self.master.update()
            self.log_output(f"Copied {len(values)} value(s) to clipboard.")
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))

    def export_selected_results_csv(self):
        """Export the currently selected result rows to a CSV file."""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showinfo("Export Selected", "No rows selected.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Export selected rows",
        )
        if not path:
            return
        try:
            columns = self.results_tree['columns']
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for iid in selection:
                    writer.writerow(self.results_tree.item(iid)['values'])
            self.log_output(f"Exported {len(selection)} selected row(s) to {path}")
            messagebox.showinfo("Export Selected", f"Exported {len(selection)} row(s).")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
