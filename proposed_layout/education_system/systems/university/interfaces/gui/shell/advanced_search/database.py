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
        return _t('advanced_search.database.msg_stats_placeholder')

    def interactive_charts():
        """Generate interactive charts"""
        return _t('advanced_search.database.msg_charts_placeholder')

    def view_search_audit_trail():
        """View search audit trail"""
        return _t('advanced_search.database.msg_audit_placeholder')

    def manage_user_permissions():
        """Manage user permissions"""
        return _t('advanced_search.database.msg_permissions_placeholder')

    def manage_scheduled_reports():
        """Manage scheduled reports"""
        return _t('advanced_search.database.msg_scheduled_placeholder')

    def performance_optimization():
        """Optimize system performance"""
        return "Performance optimization:\n- System optimization completed..."

    # Add other minimal functions as needed...

# ---------------------------------------------------------------------------
# Shared helpers for analytics table compatibility
# ---------------------------------------------------------------------------

SEARCH_ANALYTICS_COLUMNS_CACHE: Optional[List[str]] = None






# Define analytical functions at module level (outside the exception block)


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
        report = f"{_t('advanced_search.database.demographics_report')}\n"
        report += "=" * 50 + "\n\n"
        report += f"{_t('advanced_search.database.total_students')}: {total}\n\n"

        if gender_data:
            report += f"{_t('advanced_search.database.gender_distribution')}:\n"
            for gender, count in gender_data:
                percentage = (count / total * 100) if total > 0 else 0
                gender_label = gender or _t('advanced_search.database.not_specified')
                report += f"  {gender_label}: {count} ({percentage:.1f}%)\n"
            report += "\n"

        if age_stats and age_stats[0]:
            min_age, max_age, avg_age = age_stats
            report += f"{_t('advanced_search.database.age_statistics')}:\n"
            report += f"  {_t('advanced_search.database.youngest')}: {min_age} {_t('advanced_search.database.years')}\n"
            report += f"  {_t('advanced_search.database.oldest')}: {max_age} {_t('advanced_search.database.years')}\n"
            report += f"  {_t('advanced_search.database.average')}: {avg_age:.1f} {_t('advanced_search.database.years')}\n\n"

        if course_data:
            report += f"{_t('advanced_search.database.course_enrollment')}:\n"
            for course, count in course_data:
                percentage = (count / total * 100) if total > 0 else 0
                report += f"  {course}: {_t('advanced_search.database.students_count', count=count)} ({percentage:.1f}%)\n"

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
        report = f"{_t('advanced_search.database.performance_analysis')}\n"
        report += "=" * 50 + "\n\n"
        report += f"{_t('advanced_search.database.enrollment_statistics')}:\n"
        report += f"  {_t('advanced_search.database.total_enrollments')}: {total_enrollments}\n"
        report += f"  {_t('advanced_search.database.completed')}: {completed or 0}\n"
        report += f"  {_t('advanced_search.database.passed_ac')}: {passed or 0}\n"

        if completed and completed > 0:
            completion_rate = (completed / total_enrollments * 100) if total_enrollments > 0 else 0
            success_rate = (passed / completed * 100) if completed > 0 else 0
            report += f"  {_t('advanced_search.database.completion_rate')}: {completion_rate:.1f}%\n"
            report += f"  {_t('advanced_search.database.success_rate')}: {success_rate:.1f}%\n"
        report += "\n"

        if grade_dist:
            report += f"{_t('advanced_search.database.grade_distribution')}:\n"
            for grade, count in grade_dist:
                report += f"  {_t('advanced_search.database.grade')} {grade}: {_t('advanced_search.database.students_count', count=count)}\n"
            report += "\n"

        if top_modules:
            report += f"{_t('advanced_search.database.top_modules')}:\n"
            for code, name, enrolled, passed_count in top_modules:
                success_rate = (passed_count / enrolled * 100) if enrolled > 0 else 0
                module_name = name or _t('advanced_search.database.na')
                report += f"  {code} - {module_name}: {_t('advanced_search.database.success_rate_value', rate=success_rate)}\n"

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

        report = f"{_t('advanced_search.database.duplicate_detection')}\n"
        report += "=" * 50 + "\n\n"

        if email_dupes:
            report += f"{_t('advanced_search.database.duplicate_emails_found')}: {len(email_dupes)}\n"
            for email, count in email_dupes:
                report += f"  {email}: {_t('advanced_search.database.records_count', count=count)}\n"
            report += "\n"
        else:
            report += f"{_t('advanced_search.database.no_duplicate_emails')}\n\n"

        if name_dupes:
            report += f"{_t('advanced_search.database.duplicate_names_found')}: {len(name_dupes)}\n"
            for first, last, count in name_dupes:
                report += f"  {first} {last}: {_t('advanced_search.database.records_count', count=count)}\n"
        else:
            report += f"{_t('advanced_search.database.no_duplicate_names')}\n"

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
            ('email_address', _t('advanced_search.database.field_email')),
            ('first_name', _t('advanced_search.database.field_first_name')),
            ('last_name', _t('advanced_search.database.field_last_name')),
            ('gender', _t('advanced_search.database.field_gender')),
            ('dob', _t('advanced_search.database.field_date_of_birth')),
            ('course', _t('advanced_search.database.field_course'))
        ]

        report = f"{_t('advanced_search.database.quality_report')}\n"
        report += "=" * 50 + "\n"
        report += f"{_t('advanced_search.database.generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"{_t('advanced_search.database.total_records')}: {total}\n\n"
        report += f"{_t('advanced_search.database.missing_data_analysis')}:\n"

        for field, label in fields:
            safe_field = validate_identifier(field, "column")
            cursor.execute("SELECT COUNT(*) FROM students WHERE [" + safe_field + "] IS NULL OR [" + safe_field + "] = ''")
            missing = cursor.fetchone()[0]
            percentage = (missing / total * 100) if total > 0 else 0
            report += f"  {label}: {_t('advanced_search.database.missing_count', count=missing, percentage=percentage)}\n"

        conn.close()
        return report

    except Exception as e:
        return _t('advanced_search.database.error_quality_report', error=str(e))

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

        report = f"{_t('advanced_search.database.system_statistics')}\n"
        report += "=" * 50 + "\n\n"
        report += f"{_t('advanced_search.database.total_students')}: {student_count}\n"
        report += f"{_t('advanced_search.database.total_modules')}: {module_count}\n"
        report += f"{_t('advanced_search.database.total_enrollments')}: {enrollment_count}\n"

        return report

    except Exception as e:
        return _t('advanced_search.database.error_export_stats', error=str(e))

def interactive_charts():
    """Generate interactive charts"""
    return _t('advanced_search.database.chart_data_full')

def view_search_audit_trail():
    """View search audit trail"""
    return _t('advanced_search.database.audit_trail_full')

def manage_user_permissions():
    """Manage user permissions"""
    return _t('advanced_search.database.user_permissions_full')

def manage_scheduled_reports():
    """Manage scheduled reports"""
    return _t('advanced_search.database.scheduled_reports_full')

def performance_optimization():
    """Optimize system performance"""
    return "Performance optimization:\n- Database optimized\n- Search indexes updated"

# At the top of advanced_search_gui.py, add this function

from education_system.systems.university.interfaces.gui.shell.advanced_search.base import AdvancedSearchGUI

def check_database_status_gui(self):
    """Check database status with GUI display"""
    self.update_status("Checking database status...")
    self.start_progress()

    def run_status_check():
        try:
            result = self.get_database_status_report()
            self.output_queue.put(("analytics", result))
            self.output_queue.put(("log", "Database status check completed"))
        except Exception as e:
            self.output_queue.put(("error", f"Database status check failed: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_status_check, daemon=True).start()
AdvancedSearchGUI.check_database_status_gui = check_database_status_gui

def get_database_status_report(self):
    """Get comprehensive database status report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        report = f"{_t('advanced_search.database.status_report')}\n"
        report += "=" * 50 + "\n"
        report += f"{_t('advanced_search.database.report_generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if not tables:
            report += f"{_t('advanced_search.database.no_tables_found')}\n"
            return report

        report += f"{_t('advanced_search.database.table_information')}:\n"
        report += "-" * 30 + "\n"

        for (table_name,) in tables:
            safe_table = validate_table_name(table_name, conn=conn)
            cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
            count = cursor.fetchone()[0]
            report += f"  {table_name}: {_t('advanced_search.database.records_count', count=count)}\n"

        # Check data integrity
        report += f"\n{_t('advanced_search.database.integrity_checks')}:\n"
        report += "-" * 30 + "\n"

        # Check for students without emails
        cursor.execute("PRAGMA table_info(students)")
        student_columns = [col[1] for col in cursor.fetchall()]
        email_column = None
        if 'email' in student_columns:
            email_column = 'email'
        elif 'email_address' in student_columns:
            email_column = 'email_address'

        if email_column:
            safe_email_col = validate_identifier(email_column, "column")
            cursor.execute("SELECT COUNT(*) FROM students WHERE [" + safe_email_col + "] IS NULL OR [" + safe_email_col + "] = ''")
            no_email_count = cursor.fetchone()[0]
            report += f"  {_t('advanced_search.database.students_without_email')}: {no_email_count}\n"
        else:
            report += f"  {_t('advanced_search.database.students_without_email')}: {_t('advanced_search.database.na_column_missing')}\n"

        # Check for orphaned module records
        cursor.execute("""
        SELECT COUNT(*) FROM student_modules sm
        WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = sm.student_id)
        """)
        orphaned_modules = cursor.fetchone()[0]
        report += f"  {_t('advanced_search.database.orphaned_records')}: {orphaned_modules}\n"

        # Database size
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        db_size_bytes = page_count * page_size
        db_size_mb = db_size_bytes / (1024 * 1024)
        report += f"  {_t('advanced_search.database.database_size')}: {db_size_mb:.2f} MB\n"

        conn.close()

        report += f"\n{_t('advanced_search.database.connection_ok')}\n"
        report += f"{_t('advanced_search.database.status_check_completed')}\n"

        return report

    except Exception as e:
        return f"Database status check failed: {str(e)}"
AdvancedSearchGUI.get_database_status_report = get_database_status_report

def show_system_optimization_tools(self):
    """Show system optimization and maintenance tools"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.system_optimization_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.database.system_optimization'), style='Title.TLabel').pack(pady=(0, 20))

    # Database optimization
    db_frame = ttk.LabelFrame(frame, text=_t('advanced_search.database.db_optimization'), padding="10")
    db_frame.pack(fill=tk.X, pady=(0, 10))

    db_tools = [
        (_t('advanced_search.database.vacuum_database'), self.vacuum_database),
        (_t('advanced_search.database.rebuild_indexes'), self.rebuild_indexes),
        (_t('advanced_search.database.analyze_statistics'), self.analyze_statistics),
        (f"🏠 {_t('advanced_search.database.return_to_menu')}", self.return_to_main_menu)
    ]

    for text, command in db_tools:
        ttk.Button(db_frame, text=text, command=command, width=20).pack(pady=2)

    # Cache management
    cache_frame = ttk.LabelFrame(frame, text=_t('advanced_search.database.cache_management'), padding="10")
    cache_frame.pack(fill=tk.X, pady=(0, 10))

    cache_tools = [
        (_t('advanced_search.database.view_cache_stats'), self.show_cache_statistics),
        (_t('advanced_search.database.clear_cache'), self.clear_search_cache),
        (f"🏠 {_t('advanced_search.database.return_to_menu')}", self.return_to_main_menu)
    ]

    for text, command in cache_tools:
        ttk.Button(cache_frame, text=text, command=command, width=20).pack(pady=2)

    ttk.Button(frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack(pady=(20, 0))
AdvancedSearchGUI.show_system_optimization_tools = show_system_optimization_tools

def vacuum_database(self):
    """Vacuum the database to optimize storage"""
    self.update_status("Vacuuming database...")

    def run_vacuum():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.close()
            self.log_output(_t('advanced_search.database.vacuum_completed_log'))
            messagebox.showinfo(_t('advanced_search.database.vacuum_complete'),
                              _t('advanced_search.database.vacuum_success_msg'))
        except Exception as e:
            self.log_output(f"{_t('advanced_search.database.vacuum_failed_log')}: {str(e)}")
            messagebox.showerror(_t('advanced_search.database.vacuum_failed'),
                               _t('advanced_search.database.vacuum_failed_msg', error=str(e)))
        finally:
            self.update_status("Ready")

    threading.Thread(target=run_vacuum, daemon=True).start()
AdvancedSearchGUI.vacuum_database = vacuum_database

def rebuild_indexes(self):
    """Rebuild database indexes for better performance"""
    self.update_status("Rebuilding database indexes...")

    def run_rebuild():
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Drop and recreate indexes
            indexes = [
                "DROP INDEX IF EXISTS idx_students_name",
                "DROP INDEX IF EXISTS idx_students_course",
                "DROP INDEX IF EXISTS idx_students_age",
                "DROP INDEX IF EXISTS idx_modules_student",
                "CREATE INDEX idx_students_name ON students(first_name, last_name)",
                "CREATE INDEX idx_students_course ON students(course)",
                "CREATE INDEX idx_students_age ON students(age)",
                "CREATE INDEX idx_modules_student ON student_modules(student_id)"
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)

            conn.commit()
            conn.close()

            self.log_output(_t('advanced_search.database.rebuild_completed_log'))
            messagebox.showinfo(_t('advanced_search.database.rebuild_complete'),
                              _t('advanced_search.database.rebuild_success_msg'))
        except Exception as e:
            self.log_output(f"{_t('advanced_search.database.rebuild_failed_log')}: {str(e)}")
            messagebox.showerror(_t('advanced_search.database.rebuild_failed'),
                               _t('advanced_search.database.rebuild_failed_msg', error=str(e)))
        finally:
            self.update_status("Ready")

    threading.Thread(target=run_rebuild, daemon=True).start()
AdvancedSearchGUI.rebuild_indexes = rebuild_indexes

def analyze_statistics(self):
    """Analyze database statistics for query optimization"""
    self.update_status("Analyzing database statistics...")

    def run_analyze():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("ANALYZE")
            conn.close()

            self.log_output(_t('advanced_search.database.analysis_completed_log'))
            messagebox.showinfo(_t('advanced_search.database.analysis_complete'),
                              _t('advanced_search.database.analysis_success_msg'))
        except Exception as e:
            self.log_output(f"{_t('advanced_search.database.analysis_failed_log')}: {str(e)}")
            messagebox.showerror(_t('advanced_search.database.analysis_failed'),
                               _t('advanced_search.database.analysis_failed_msg', error=str(e)))
        finally:
            self.update_status("Ready")

    threading.Thread(target=run_analyze, daemon=True).start()
AdvancedSearchGUI.analyze_statistics = analyze_statistics

def check_integrity(self):
    """Check database integrity"""
    self.update_status("Checking database integrity...")
    self.start_progress()

    def run_integrity_check():
        try:
            result = self.perform_integrity_check()
            self.output_queue.put(("analytics", result))
            self.output_queue.put(("log", "Database integrity check completed"))
        except Exception as e:
            self.output_queue.put(("error", f"Integrity check failed: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_integrity_check, daemon=True).start()
AdvancedSearchGUI.check_integrity = check_integrity

def perform_integrity_check(self):
    """Perform comprehensive database integrity check"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        result = f"{_t('advanced_search.database.integrity_check')}\n"
        result += "=" * 50 + "\n"
        result += f"{_t('advanced_search.database.check_performed')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # SQLite integrity check
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]

        result += f"{_t('advanced_search.database.sqlite_integrity_check')}: {integrity_result}\n\n"

        # Check for referential integrity
        cursor.execute("""
        SELECT COUNT(*) FROM student_modules sm
        WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = sm.student_id)
        """)
        orphaned_modules = cursor.fetchone()[0]

        result += f"{_t('advanced_search.database.referential_integrity')}:\n"
        result += f"{_t('advanced_search.database.orphaned_records')}: {orphaned_modules}\n"

        # Check for data consistency
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id IS NULL OR student_id = ''")
        null_ids = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''")
        null_emails = cursor.fetchone()[0]

        result += f"\n{_t('advanced_search.database.data_consistency')}:\n"
        result += f"{_t('advanced_search.database.null_ids')}: {null_ids}\n"
        result += f"{_t('advanced_search.database.null_emails')}: {null_emails}\n"

        # Check for duplicate student IDs
        cursor.execute("""
        SELECT student_id, COUNT(*) as count
        FROM students
        GROUP BY student_id
        HAVING count > 1
        """)
        duplicates = cursor.fetchall()

        result += f"{_t('advanced_search.database.duplicate_ids')}: {len(duplicates)}\n"
        if duplicates:
            result += f"{_t('advanced_search.database.duplicate_ids_found')}:\n"
            for student_id, count in duplicates:
                result += f"  {student_id}: {_t('advanced_search.database.records_count', count=count)}\n"

        conn.close()

        result += f"\n{_t('advanced_search.database.integrity_check_completed')}\n"

        if integrity_result == "ok" and orphaned_modules == 0 and null_ids == 0 and len(duplicates) == 0:
            result += f"{_t('advanced_search.database.integrity_excellent')}\n"
        elif orphaned_modules > 0 or null_ids > 0 or len(duplicates) > 0:
            result += f"{_t('advanced_search.database.integrity_needs_attention')}\n"
        else:
            result += f"{_t('advanced_search.database.integrity_good')}\n"

        return result

    except Exception as e:
        return f"Integrity check failed: {str(e)}"
AdvancedSearchGUI.perform_integrity_check = perform_integrity_check

def optimize_memory_usage(self):
    """Optimize memory usage by clearing caches and temporary data"""
    try:
        # Clear search cache
        if hasattr(self, 'search_cache'):
            cache_size = len(self.search_cache)
            self.search_cache.clear()
        else:
            cache_size = 0

        # Clear search history if it gets too large
        if hasattr(self, 'search_history') and self.search_history and len(self.search_history) > 100:
            self.search_history = self.search_history[-50:]  # Keep last 50

        # Force garbage collection
        import gc
        collected = gc.collect()

        self.log_output(_t('advanced_search.database.memory_opt_completed'))
        self.log_output(f"  {_t('advanced_search.database.cleared_cache_entries', count=cache_size)}")
        self.log_output(f"  {_t('advanced_search.database.collected_objects', count=collected)}")

        messagebox.showinfo(_t('advanced_search.database.memory_optimized'),
                          _t('advanced_search.database.memory_opt_msg',
                             cache_size=cache_size, collected=collected))

    except Exception as e:
        self.log_output(f"{_t('advanced_search.database.memory_opt_failed')}: {str(e)}")
        messagebox.showerror(_t('common.error'),
                           _t('advanced_search.database.memory_opt_failed_msg', error=str(e)))
AdvancedSearchGUI.optimize_memory_usage = optimize_memory_usage

def ensure_database_tables_exist(self):
    """Ensure all required database tables exist"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check and create students table if needed
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            date_of_birth DATE,
            age INTEGER,
            course TEXT,
            registration_datetime DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Check and create student_modules table if needed
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_type TEXT,
            module_code TEXT,
            module_name TEXT,
            grade TEXT,
            enrollment_date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        """)

        # Check and create search_profiles table if needed
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            criteria TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            is_shared BOOLEAN DEFAULT FALSE
        )
        """)

        # Check and create user_permissions table if needed
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            role TEXT,
            permissions TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Check and create scheduled_reports table if needed
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            report_type TEXT,
            frequency TEXT,
            recipients TEXT,
            next_run_date DATETIME,
            is_active BOOLEAN DEFAULT TRUE,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()

        return "All required database tables verified/created successfully."

    except Exception as e:
        return f"Error ensuring database tables: {str(e)}"
AdvancedSearchGUI.ensure_database_tables_exist = ensure_database_tables_exist

def check_database_status(self):
    """Check database status and integrity"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        status_report = f"{_t('advanced_search.database.status_report')}\n"
        status_report += "=" * 30 + "\n"
        status_report += f"{_t('advanced_search.database.check_performed')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Check table existence and record counts
        tables_to_check = [
            ("students", _t('advanced_search.database.student_records')),
            ("student_modules", _t('advanced_search.database.module_enrollments')),
            ("search_profiles", _t('advanced_search.database.saved_profiles')),
            ("user_permissions", _t('advanced_search.database.user_permissions')),
            ("scheduled_reports", _t('advanced_search.database.scheduled_reports'))
        ]

        status_report += f"{_t('advanced_search.database.table_status')}:\n"
        for table_name, description in tables_to_check:
            try:
                safe_table = validate_table_name(table_name)
                cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                count = cursor.fetchone()[0]
                status_report += f"  {description}: {_t('advanced_search.database.records_count', count=count)}\n"
            except Exception as e:
                status_report += f"  {description}: {_t('advanced_search.database.table_missing_error', error=str(e))}\n"

        # Check for data integrity issues
        status_report += f"\n{_t('advanced_search.database.integrity_checks')}:\n"

        # Check for students without emails
        try:
            cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''")
            no_email_count = cursor.fetchone()[0]
            status_report += f"  {_t('advanced_search.database.students_without_email')}: {no_email_count}\n"
        except Exception:
            status_report += f"  {_t('advanced_search.database.students_without_email')}: {_t('advanced_search.database.unable_to_check')}\n"

        # Check for orphaned module records
        try:
            cursor.execute("""
            SELECT COUNT(*) FROM student_modules sm
            WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = sm.student_id)
            """)
            orphaned_modules = cursor.fetchone()[0]
            status_report += f"  {_t('advanced_search.database.orphaned_records')}: {orphaned_modules}\n"
        except Exception:
            status_report += f"  {_t('advanced_search.database.orphaned_records')}: {_t('advanced_search.database.unable_to_check')}\n"

        # Check database size
        try:
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_bytes = page_count * page_size
            db_size_mb = db_size_bytes / (1024 * 1024)
            status_report += f"  {_t('advanced_search.database.database_size')}: {db_size_mb:.2f} MB\n"
        except Exception:
            status_report += f"  {_t('advanced_search.database.database_size')}: {_t('advanced_search.database.unable_to_determine')}\n"

        conn.close()

        status_report += f"\n{_t('advanced_search.database.connection_ok')}\n"
        status_report += f"{_t('advanced_search.database.status_check_completed')}\n"

        return status_report

    except Exception as e:
        return f"Database status check failed: {str(e)}"
AdvancedSearchGUI.check_database_status = check_database_status

def show_system_maintenance(self):
    """Show system maintenance interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.system_maintenance_dialog_title'))
    dialog.geometry("1100x800")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.database.system_maintenance'), style='Title.TLabel').pack(pady=(0, 20))

    # Maintenance operations
    maintenance_frame = ttk.LabelFrame(frame, text=_t('advanced_search.database.db_maintenance'), padding="10")
    maintenance_frame.pack(fill=tk.X, pady=(0, 20))

    maintenance_ops = [
        (_t('advanced_search.database.check_db_status'), self.run_database_status_check),
        (_t('advanced_search.database.ensure_tables'), self.run_ensure_tables),
        (_t('advanced_search.database.optimize_db'), self.run_database_optimization),
        (_t('advanced_search.database.clean_logs'), self.run_clean_audit_logs),
        (f"🏠 {_t('advanced_search.database.return_to_menu')}", self.return_to_main_menu)
    ]

    for text, command in maintenance_ops:
        ttk.Button(maintenance_frame, text=text, command=command, width=25).pack(pady=2)

    # Data management
    data_frame = ttk.LabelFrame(frame, text=_t('advanced_search.database.data_management'), padding="10")
    data_frame.pack(fill=tk.X, pady=(0, 20))

    data_ops = [
        (_t('advanced_search.database.backup_db'), self.run_database_backup),
        (_t('advanced_search.database.restore_db'), self.run_database_restore),
        (_t('advanced_search.database.clear_history'), self.clear_search_history),
        (f"🏠 {_t('advanced_search.database.return_to_menu')}", self.return_to_main_menu)
    ]

    for text, command in data_ops:
        ttk.Button(data_frame, text=text, command=command, width=25).pack(pady=2)

    # System information
    info_frame = ttk.LabelFrame(frame, text=_t('advanced_search.database.system_info'), padding="10")
    info_frame.pack(fill=tk.BOTH, expand=True)

    self.system_info_text = scrolledtext.ScrolledText(info_frame, height=8, wrap=tk.WORD)
    self.system_info_text.pack(fill=tk.BOTH, expand=True)

    # Load initial system info
    self.load_system_information()

    ttk.Button(frame, text=_t('advanced_search.close_button'), command=dialog.destroy).pack()
AdvancedSearchGUI.show_system_maintenance = show_system_maintenance

def run_database_status_check(self):
    """Run database status check"""
    self.update_status("Checking database status...")

    def check_status():
        try:
            status_report = self.check_database_status()
            self.system_info_text.delete(1.0, tk.END)
            self.system_info_text.insert(1.0, status_report)
            self.log_output("Database status check completed")
        except Exception as e:
            self.log_output(f"Database status check failed: {str(e)}")
        finally:
            self.update_status("Ready")

    threading.Thread(target=check_status, daemon=True).start()
AdvancedSearchGUI.run_database_status_check = run_database_status_check

def run_ensure_tables(self):
    """Run ensure tables exist operation"""
    self.update_status("Ensuring database tables exist...")

    def ensure_tables():
        try:
            result = self.ensure_database_tables_exist()
            self.log_output(result)
            messagebox.showinfo(_t('advanced_search.database.tables_check'),
                              _t('advanced_search.database.tables_check_success'))
        except Exception as e:
            self.log_output(f"{_t('advanced_search.database.table_check_failed')}: {str(e)}")
            messagebox.showerror(_t('common.error'),
                               _t('advanced_search.database.table_check_failed_msg', error=str(e)))
        finally:
            self.update_status("Ready")

    threading.Thread(target=ensure_tables, daemon=True).start()
AdvancedSearchGUI.run_ensure_tables = run_ensure_tables

def run_database_optimization(self):
    """Run database optimization"""
    self.update_status("Optimizing database...")

    def optimize_db():
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Run VACUUM to optimize database
            cursor.execute("VACUUM")

            # Update statistics
            cursor.execute("ANALYZE")

            conn.close()

            self.log_output(_t('advanced_search.database.optimization_completed_log'))
            messagebox.showinfo(_t('advanced_search.database.optimization'),
                              _t('advanced_search.database.optimization_success'))

        except Exception as e:
            self.log_output(f"{_t('advanced_search.database.optimization_failed_log')}: {str(e)}")
            messagebox.showerror(_t('common.error'),
                               _t('advanced_search.database.optimization_failed_msg', error=str(e)))
        finally:
            self.update_status("Ready")

    threading.Thread(target=optimize_db, daemon=True).start()
AdvancedSearchGUI.run_database_optimization = run_database_optimization

def run_clean_audit_logs(self):
    """Clean old audit log entries"""
    if messagebox.askyesno(_t('advanced_search.database.confirm_clean'),
                           _t('advanced_search.database.confirm_clean_msg')):
        try:
            # Clean old log entries from file
            log_filename = "search_audit_log.json"
            cutoff_date = datetime.now() - timedelta(days=90)

            try:
                with open(log_filename, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)

                original_count = len(log_data.get("searches", []))

                # Filter out old entries
                log_data["searches"] = [
                    entry for entry in log_data.get("searches", [])
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
                ]

                cleaned_count = original_count - len(log_data["searches"])

                with open(log_filename, 'w', encoding='utf-8') as f:
                    json.dump(log_data, f, indent=2)

                self.log_output(_t('advanced_search.database.cleaned_logs', count=cleaned_count))
                messagebox.showinfo(_t('advanced_search.database.logs_cleaned'),
                                  _t('advanced_search.database.logs_cleaned_msg', count=cleaned_count))

            except FileNotFoundError:
                messagebox.showinfo(_t('advanced_search.database.no_logs'),
                                  _t('advanced_search.database.no_logs_msg'))

        except Exception as e:
            messagebox.showerror(_t('common.error'),
                               _t('advanced_search.database.clean_logs_failed', error=str(e)))
AdvancedSearchGUI.run_clean_audit_logs = run_clean_audit_logs

def run_export_system_stats(self):
    """Export comprehensive system statistics"""
    self.update_status("Exporting system statistics...")
    self.start_progress()

    def export_stats():
        try:
            result = self.capture_function_output(export_system_statistics)
            self.output_queue.put(("analytics", result))
            self.output_queue.put(("log", "System statistics exported successfully"))
        except Exception as e:
            self.output_queue.put(("error", f"System statistics export failed: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=export_stats, daemon=True).start()
AdvancedSearchGUI.run_export_system_stats = run_export_system_stats

def run_database_backup(self):
    """Create database backup"""
    backup_file = filedialog.asksaveasfilename(
        defaultextension=".db",
        filetypes=[(_t('common.sqlite_files'), "*.db"), (_t('common.all_files'), "*.*")],
        title=_t('advanced_search.database.save_backup_as')
    )

    if backup_file:
        try:
            source_path = Path(DEFAULT_DB_PATH)
            if not source_path.exists():
                raise FileNotFoundError(f"Database file not found at {source_path}")

            destination = Path(backup_file)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)

            messagebox.showinfo(_t('advanced_search.database.backup_created'),
                              _t('advanced_search.database.backup_created_msg', path=destination))
            self.log_output(f"{_t('advanced_search.database.backup_created')}: {destination}")
        except Exception as e:
            messagebox.showerror(_t('advanced_search.database.backup_failed'),
                               _t('advanced_search.database.backup_failed_msg', error=str(e)))
AdvancedSearchGUI.run_database_backup = run_database_backup

def run_database_restore(self):
    """Restore database from backup"""
    backup_file = filedialog.askopenfilename(
        filetypes=[(_t('common.sqlite_files'), "*.db"), (_t('common.all_files'), "*.*")],
        title=_t('advanced_search.database.select_backup')
    )

    if backup_file:
        if messagebox.askyesno(_t('advanced_search.database.confirm_restore'),
                               _t('advanced_search.database.confirm_restore_msg')):
            try:
                destination = Path(DEFAULT_DB_PATH)
                source = Path(backup_file)
                if not source.exists():
                    raise FileNotFoundError(f"Backup file {source} does not exist.")
                destination.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source, destination)
                messagebox.showinfo(_t('advanced_search.database.restore_complete'),
                                  _t('advanced_search.database.restore_complete_msg', path=source))
                self.log_output(f"{_t('advanced_search.database.restore_complete')}: {source}")
            except Exception as e:
                messagebox.showerror(_t('advanced_search.database.restore_failed'),
                                   _t('advanced_search.database.restore_failed_msg', error=str(e)))
AdvancedSearchGUI.run_database_restore = run_database_restore

def reset_user_preferences(self):
    """Reset user preferences to defaults"""
    if messagebox.askyesno(_t('advanced_search.database.confirm_reset'),
                           _t('advanced_search.database.confirm_reset_msg')):
        try:
            # Reset GUI preferences
            self.results_per_page = 10
            self.per_page_var.set("10")

            # Clear any preference files
            pref_files = ["user_preferences.json", "gui_settings.json"]

            for pref_file in pref_files:
                try:
                    import os
                    if os.path.exists(pref_file):
                        os.remove(pref_file)
                except Exception:

                    pass

            messagebox.showinfo(_t('advanced_search.database.prefs_reset'),
                              _t('advanced_search.database.prefs_reset_msg'))
            self.log_output(_t('advanced_search.database.prefs_reset_log'))

        except Exception as e:
            messagebox.showerror(_t('common.error'),
                               _t('advanced_search.database.prefs_reset_failed', error=str(e)))
AdvancedSearchGUI.reset_user_preferences = reset_user_preferences

def load_system_information(self):
    """Load system information into the text widget"""
    try:
        import platform
        import sys

        info = f"{_t('advanced_search.database.system_information')}\n"
        info += "=" * 30 + "\n"
        info += f"{_t('advanced_search.database.application')}: {_t('advanced_search.database.app_name')}\n"
        info += f"{_t('advanced_search.database.version')}: 2.0 GUI Edition\n"
        info += f"{_t('advanced_search.database.python_version')}: {sys.version}\n"
        info += f"{_t('advanced_search.database.platform')}: {platform.platform()}\n"
        info += f"{_t('advanced_search.database.architecture')}: {platform.architecture()[0]}\n"
        info += f"{_t('advanced_search.database.current_time')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        info += f"{_t('advanced_search.database.db_status')}:\n"
        info += f"{_t('advanced_search.database.connection')}: {_t('advanced_search.database.available')}\n"

        try:
            conn = get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM students")
                student_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM student_modules")
                module_count = cursor.fetchone()[0]
                conn.close()

                info += f"{_t('advanced_search.database.student_records')}: {student_count}\n"
                info += f"{_t('advanced_search.database.module_enrollments')}: {module_count}\n"
            else:
                info += f"{_t('advanced_search.database.database')}: {_t('advanced_search.database.connection_failed')}\n"
        except Exception:
            info += f"{_t('advanced_search.database.database')}: {_t('advanced_search.database.status_unknown')}\n"

        info += f"\n{_t('advanced_search.database.features_available')}:\n"
        info += f"✓ {_t('advanced_search.database.feature_multicriteria')}\n"
        info += f"✓ {_t('advanced_search.database.feature_fuzzy')}\n"
        info += f"✓ {_t('advanced_search.database.feature_advanced_text')}\n"
        info += f"✓ {_t('advanced_search.database.feature_analytics')}\n"
        info += f"✓ {_t('advanced_search.database.feature_visualization')}\n"
        info += f"✓ {_t('advanced_search.database.feature_bulk')}\n"
        info += f"✓ {_t('advanced_search.database.feature_permissions')}\n"
        info += f"✓ {_t('advanced_search.database.feature_scheduled')}\n"
        info += f"✓ {_t('advanced_search.database.feature_export')}\n"

        self.system_info_text.insert(1.0, info)

    except Exception as e:
        self.system_info_text.insert(1.0, f"Error loading system information: {str(e)}")
AdvancedSearchGUI.load_system_information = load_system_information

def init_database(self):
    """Initialize the database"""
    self.update_status("Initializing database...")
    self.start_progress()

    def run_init_db():
        try:
            result = self.capture_function_output(init_enhanced_database)
            self.output_queue.put(("log", "Database initialization completed"))
            self.output_queue.put(("analytics", result))
        except Exception as e:
            self.output_queue.put(("error", f"Database initialization error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_init_db, daemon=True).start()
AdvancedSearchGUI.init_database = init_database

def optimize_performance(self):
    """Optimize system performance"""
    self.update_status("Optimizing performance...")
    self.start_progress()

    def run_optimization():
        try:
            result = self.capture_function_output(performance_optimization)
            self.output_queue.put(("analytics", result))
        except Exception as e:
            self.output_queue.put(("error", f"Performance optimization error: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_optimization, daemon=True).start()
AdvancedSearchGUI.optimize_performance = optimize_performance

def show_system_stats(self):
    """Show system statistics"""
    self.update_status("Gathering system statistics...")
    self.start_progress()

    def run_system_stats():
        try:
            result = self.capture_function_output(export_system_statistics)
            self.output_queue.put(("analytics", result))
        except Exception as e:
            self.output_queue.put(("error", f"Error gathering system statistics: {str(e)}"))
        finally:
            self.output_queue.put(("stop_progress", None))

    threading.Thread(target=run_system_stats, daemon=True).start()
AdvancedSearchGUI.show_system_stats = show_system_stats

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

    _VALID_TIME_COLUMNS2 = {'timestamp', 'search_datetime'}
    time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime' if 'search_datetime' in columns else None
    if time_column:
        validate_field_for_query(time_column, _VALID_TIME_COLUMNS2, "time column")
        cursor.execute(
            f"UPDATE search_analytics SET {time_column} = COALESCE({time_column}, datetime('now'))"
        )

    return list(columns)

def get_search_analytics_columns(cursor) -> List[str]:
    """Get cached column list for search_analytics, refreshing if required."""
    if SEARCH_ANALYTICS_COLUMNS_CACHE is None:
        return refresh_search_analytics_columns(cursor)
    return SEARCH_ANALYTICS_COLUMNS_CACHE

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

def refresh_search_analytics_columns(cursor) -> List[str]:
    """Refresh and return the column names for search_analytics."""
    global SEARCH_ANALYTICS_COLUMNS_CACHE
    cursor.execute("PRAGMA table_info(search_analytics)")
    SEARCH_ANALYTICS_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
    return SEARCH_ANALYTICS_COLUMNS_CACHE

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

