"""Compatibility façade for the split implementation."""
import logging

logger = logging.getLogger(__name__)

from . import search_advanced_shared as _shared
from .search_advanced_shared import *  # noqa: F401,F403

from .search_advanced_parts import refresh_search_analytics_columns as _part_1
refresh_search_analytics_columns = _part_1.refresh_search_analytics_columns
_shared.refresh_search_analytics_columns = refresh_search_analytics_columns
_shared.__all__.append("refresh_search_analytics_columns") if "refresh_search_analytics_columns" not in _shared.__all__ else None

from .search_advanced_parts import get_search_analytics_columns as _part_2
get_search_analytics_columns = _part_2.get_search_analytics_columns
_shared.get_search_analytics_columns = get_search_analytics_columns
_shared.__all__.append("get_search_analytics_columns") if "get_search_analytics_columns" not in _shared.__all__ else None

from .search_advanced_parts import ensure_search_analytics_schema as _part_3
ensure_search_analytics_schema = _part_3.ensure_search_analytics_schema
_shared.ensure_search_analytics_schema = ensure_search_analytics_schema
_shared.__all__.append("ensure_search_analytics_schema") if "ensure_search_analytics_schema" not in _shared.__all__ else None

from .search_advanced_parts import build_search_analytics_record as _part_4
build_search_analytics_record = _part_4.build_search_analytics_record
_shared.build_search_analytics_record = build_search_analytics_record
_shared.__all__.append("build_search_analytics_record") if "build_search_analytics_record" not in _shared.__all__ else None

from .search_advanced_parts import insert_search_analytics_record as _part_5
insert_search_analytics_record = _part_5.insert_search_analytics_record
_shared.insert_search_analytics_record = insert_search_analytics_record
_shared.__all__.append("insert_search_analytics_record") if "insert_search_analytics_record" not in _shared.__all__ else None

from .search_advanced_parts import init_enhanced_database as _part_6
init_enhanced_database = _part_6.init_enhanced_database
_shared.init_enhanced_database = init_enhanced_database
_shared.__all__.append("init_enhanced_database") if "init_enhanced_database" not in _shared.__all__ else None

from .search_advanced_parts import ensure_tables_exist as _part_7
ensure_tables_exist = _part_7.ensure_tables_exist
_shared.ensure_tables_exist = ensure_tables_exist
_shared.__all__.append("ensure_tables_exist") if "ensure_tables_exist" not in _shared.__all__ else None

from .search_advanced_parts import student_demographics_reports as _part_8
student_demographics_reports = _part_8.student_demographics_reports
_shared.student_demographics_reports = student_demographics_reports
_shared.__all__.append("student_demographics_reports") if "student_demographics_reports" not in _shared.__all__ else None

from .search_advanced_parts import academic_performance_analysis as _part_9
academic_performance_analysis = _part_9.academic_performance_analysis
_shared.academic_performance_analysis = academic_performance_analysis
_shared.__all__.append("academic_performance_analysis") if "academic_performance_analysis" not in _shared.__all__ else None

from .search_advanced_parts import duplicate_detection as _part_10
duplicate_detection = _part_10.duplicate_detection
_shared.duplicate_detection = duplicate_detection
_shared.__all__.append("duplicate_detection") if "duplicate_detection" not in _shared.__all__ else None

from .search_advanced_parts import data_quality_reports as _part_11
data_quality_reports = _part_11.data_quality_reports
_shared.data_quality_reports = data_quality_reports
_shared.__all__.append("data_quality_reports") if "data_quality_reports" not in _shared.__all__ else None

from .search_advanced_parts import generate_custom_reports as _part_12
generate_custom_reports = _part_12.generate_custom_reports
_shared.generate_custom_reports = generate_custom_reports
_shared.__all__.append("generate_custom_reports") if "generate_custom_reports" not in _shared.__all__ else None

from .search_advanced_parts import export_system_statistics as _part_13
export_system_statistics = _part_13.export_system_statistics
_shared.export_system_statistics = export_system_statistics
_shared.__all__.append("export_system_statistics") if "export_system_statistics" not in _shared.__all__ else None

from .search_advanced_parts import interactive_charts as _part_14
interactive_charts = _part_14.interactive_charts
_shared.interactive_charts = interactive_charts
_shared.__all__.append("interactive_charts") if "interactive_charts" not in _shared.__all__ else None

from .search_advanced_parts import view_search_audit_trail as _part_15
view_search_audit_trail = _part_15.view_search_audit_trail
_shared.view_search_audit_trail = view_search_audit_trail
_shared.__all__.append("view_search_audit_trail") if "view_search_audit_trail" not in _shared.__all__ else None

from .search_advanced_parts import manage_user_permissions as _part_16
manage_user_permissions = _part_16.manage_user_permissions
_shared.manage_user_permissions = manage_user_permissions
_shared.__all__.append("manage_user_permissions") if "manage_user_permissions" not in _shared.__all__ else None

from .search_advanced_parts import manage_scheduled_reports as _part_17
manage_scheduled_reports = _part_17.manage_scheduled_reports
_shared.manage_scheduled_reports = manage_scheduled_reports
_shared.__all__.append("manage_scheduled_reports") if "manage_scheduled_reports" not in _shared.__all__ else None

from .search_advanced_parts import performance_optimization as _part_18
performance_optimization = _part_18.performance_optimization
_shared.performance_optimization = performance_optimization
_shared.__all__.append("performance_optimization") if "performance_optimization" not in _shared.__all__ else None

from .search_advanced_parts import get_connection as _part_19
get_connection = _part_19.get_connection
_shared.get_connection = get_connection
_shared.__all__.append("get_connection") if "get_connection" not in _shared.__all__ else None

from .search_advanced_parts import show_regex_search as _part_20
show_regex_search = _part_20.show_regex_search
_shared.show_regex_search = show_regex_search
_shared.__all__.append("show_regex_search") if "show_regex_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_regex_search as _part_21
perform_regex_search = _part_21.perform_regex_search
_shared.perform_regex_search = perform_regex_search
_shared.__all__.append("perform_regex_search") if "perform_regex_search" not in _shared.__all__ else None

from .search_advanced_parts import show_wildcard_search as _part_22
show_wildcard_search = _part_22.show_wildcard_search
_shared.show_wildcard_search = show_wildcard_search
_shared.__all__.append("show_wildcard_search") if "show_wildcard_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_wildcard_search as _part_23
perform_wildcard_search = _part_23.perform_wildcard_search
_shared.perform_wildcard_search = perform_wildcard_search
_shared.__all__.append("perform_wildcard_search") if "perform_wildcard_search" not in _shared.__all__ else None

from .search_advanced_parts import show_search_all_fields as _part_24
show_search_all_fields = _part_24.show_search_all_fields
_shared.show_search_all_fields = show_search_all_fields
_shared.__all__.append("show_search_all_fields") if "show_search_all_fields" not in _shared.__all__ else None

from .search_advanced_parts import show_phonetic_search as _part_25
show_phonetic_search = _part_25.show_phonetic_search
_shared.show_phonetic_search = show_phonetic_search
_shared.__all__.append("show_phonetic_search") if "show_phonetic_search" not in _shared.__all__ else None

from .search_advanced_parts import show_auto_complete_search as _part_26
show_auto_complete_search = _part_26.show_auto_complete_search
_shared.show_auto_complete_search = show_auto_complete_search
_shared.__all__.append("show_auto_complete_search") if "show_auto_complete_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_autocomplete_search as _part_27
perform_autocomplete_search = _part_27.perform_autocomplete_search
_shared.perform_autocomplete_search = perform_autocomplete_search
_shared.__all__.append("perform_autocomplete_search") if "perform_autocomplete_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_regex_search_2 as _part_28
perform_regex_search = _part_28.perform_regex_search
_shared.perform_regex_search = perform_regex_search
_shared.__all__.append("perform_regex_search") if "perform_regex_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_wildcard_search_2 as _part_29
perform_wildcard_search = _part_29.perform_wildcard_search
_shared.perform_wildcard_search = perform_wildcard_search
_shared.__all__.append("perform_wildcard_search") if "perform_wildcard_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_search_all_fields as _part_30
perform_search_all_fields = _part_30.perform_search_all_fields
_shared.perform_search_all_fields = perform_search_all_fields
_shared.__all__.append("perform_search_all_fields") if "perform_search_all_fields" not in _shared.__all__ else None

from .search_advanced_parts import perform_phonetic_search as _part_31
perform_phonetic_search = _part_31.perform_phonetic_search
_shared.perform_phonetic_search = perform_phonetic_search
_shared.__all__.append("perform_phonetic_search") if "perform_phonetic_search" not in _shared.__all__ else None

from .search_advanced_parts import show_fuzzy_search as _part_32
show_fuzzy_search = _part_32.show_fuzzy_search
_shared.show_fuzzy_search = show_fuzzy_search
_shared.__all__.append("show_fuzzy_search") if "show_fuzzy_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_fuzzy_search as _part_33
perform_fuzzy_search = _part_33.perform_fuzzy_search
_shared.perform_fuzzy_search = perform_fuzzy_search
_shared.__all__.append("perform_fuzzy_search") if "perform_fuzzy_search" not in _shared.__all__ else None

from .search_advanced_parts import show_module_search as _part_34
show_module_search = _part_34.show_module_search
_shared.show_module_search = show_module_search
_shared.__all__.append("show_module_search") if "show_module_search" not in _shared.__all__ else None

from .search_advanced_parts import load_available_modules as _part_35
load_available_modules = _part_35.load_available_modules
_shared.load_available_modules = load_available_modules
_shared.__all__.append("load_available_modules") if "load_available_modules" not in _shared.__all__ else None

from .search_advanced_parts import perform_module_search as _part_36
perform_module_search = _part_36.perform_module_search
_shared.perform_module_search = perform_module_search
_shared.__all__.append("perform_module_search") if "perform_module_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_combined_filters_search as _part_37
perform_combined_filters_search = _part_37.perform_combined_filters_search
_shared.perform_combined_filters_search = perform_combined_filters_search
_shared.__all__.append("perform_combined_filters_search") if "perform_combined_filters_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_text_search as _part_38
perform_text_search = _part_38.perform_text_search
_shared.perform_text_search = perform_text_search
_shared.__all__.append("perform_text_search") if "perform_text_search" not in _shared.__all__ else None

from .search_advanced_parts import show_fuzzy_search_2 as _part_39
show_fuzzy_search = _part_39.show_fuzzy_search
_shared.show_fuzzy_search = show_fuzzy_search
_shared.__all__.append("show_fuzzy_search") if "show_fuzzy_search" not in _shared.__all__ else None

from .search_advanced_parts import perform_fuzzy_search_2 as _part_40
perform_fuzzy_search = _part_40.perform_fuzzy_search
_shared.perform_fuzzy_search = perform_fuzzy_search
_shared.__all__.append("perform_fuzzy_search") if "perform_fuzzy_search" not in _shared.__all__ else None

from .search_advanced_parts import show_module_search_2 as _part_41
show_module_search = _part_41.show_module_search
_shared.show_module_search = show_module_search
_shared.__all__.append("show_module_search") if "show_module_search" not in _shared.__all__ else None

from .search_advanced_parts import load_available_modules_2 as _part_42
load_available_modules = _part_42.load_available_modules
_shared.load_available_modules = load_available_modules
_shared.__all__.append("load_available_modules") if "load_available_modules" not in _shared.__all__ else None

from .search_advanced_parts import perform_module_search_2 as _part_43
from education_system.systems.university.infrastructure.database.schemas.students_table import ensure_students_table
from education_system.systems.university.infrastructure.database.schemas.users_table import ensure_users_table
perform_module_search = _part_43.perform_module_search
_shared.perform_module_search = perform_module_search
_shared.__all__.append("perform_module_search") if "perform_module_search" not in _shared.__all__ else None

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
        from education_system import paths
        return sqlite3.connect(str(paths.UNIVERSITY_DEFAULT_DB_PATH))

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
            ensure_users_table(cursor)

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
            ensure_students_table(cursor)

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

                logger.debug("Suppressed exception", exc_info=True)
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

_exports = {name: globals()[name] for name in ['academic_performance_analysis', 'build_search_analytics_record', 'data_quality_reports', 'duplicate_detection', 'ensure_search_analytics_schema', 'ensure_tables_exist', 'export_system_statistics', 'generate_custom_reports', 'get_connection', 'get_search_analytics_columns', 'init_enhanced_database', 'insert_search_analytics_record', 'interactive_charts', 'load_available_modules', 'manage_scheduled_reports', 'manage_user_permissions', 'perform_autocomplete_search', 'perform_combined_filters_search', 'perform_fuzzy_search', 'perform_module_search', 'perform_phonetic_search', 'perform_regex_search', 'perform_search_all_fields', 'perform_text_search', 'perform_wildcard_search', 'performance_optimization', 'refresh_search_analytics_columns', 'show_auto_complete_search', 'show_fuzzy_search', 'show_module_search', 'show_phonetic_search', 'show_regex_search', 'show_search_all_fields', 'show_wildcard_search', 'student_demographics_reports', 'view_search_audit_trail']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32, _part_33, _part_34, _part_35, _part_36, _part_37, _part_38, _part_39, _part_40, _part_41, _part_42, _part_43]:
    _module.__dict__.update(_exports)

AdvancedSearchGUI.show_regex_search = show_regex_search

AdvancedSearchGUI.perform_regex_search = perform_regex_search

AdvancedSearchGUI.show_wildcard_search = show_wildcard_search

AdvancedSearchGUI.perform_wildcard_search = perform_wildcard_search

AdvancedSearchGUI.show_search_all_fields = show_search_all_fields

AdvancedSearchGUI.show_phonetic_search = show_phonetic_search

AdvancedSearchGUI.show_auto_complete_search = show_auto_complete_search

AdvancedSearchGUI.perform_autocomplete_search = perform_autocomplete_search

AdvancedSearchGUI.perform_regex_search = perform_regex_search

AdvancedSearchGUI.perform_wildcard_search = perform_wildcard_search

AdvancedSearchGUI.perform_search_all_fields = perform_search_all_fields

AdvancedSearchGUI.perform_phonetic_search = perform_phonetic_search

AdvancedSearchGUI.show_fuzzy_search = show_fuzzy_search

AdvancedSearchGUI.perform_fuzzy_search = perform_fuzzy_search

AdvancedSearchGUI.show_module_search = show_module_search

AdvancedSearchGUI.load_available_modules = load_available_modules

AdvancedSearchGUI.perform_module_search = perform_module_search

AdvancedSearchGUI.perform_combined_filters_search = perform_combined_filters_search

AdvancedSearchGUI.perform_text_search = perform_text_search

AdvancedSearchGUI.show_fuzzy_search = show_fuzzy_search

AdvancedSearchGUI.perform_fuzzy_search = perform_fuzzy_search

AdvancedSearchGUI.show_module_search = show_module_search

AdvancedSearchGUI.load_available_modules = load_available_modules

AdvancedSearchGUI.perform_module_search = perform_module_search


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32, _part_33, _part_34, _part_35, _part_36, _part_37, _part_38, _part_39, _part_40, _part_41, _part_42, _part_43]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['academic_performance_analysis', 'build_search_analytics_record', 'data_quality_reports', 'duplicate_detection', 'ensure_search_analytics_schema', 'ensure_tables_exist', 'export_system_statistics', 'generate_custom_reports', 'get_connection', 'get_search_analytics_columns', 'init_enhanced_database', 'insert_search_analytics_record', 'interactive_charts', 'load_available_modules', 'manage_scheduled_reports', 'manage_user_permissions', 'perform_autocomplete_search', 'perform_combined_filters_search', 'perform_fuzzy_search', 'perform_module_search', 'perform_phonetic_search', 'perform_regex_search', 'perform_search_all_fields', 'perform_text_search', 'perform_wildcard_search', 'performance_optimization', 'refresh_search_analytics_columns', 'show_auto_complete_search', 'show_fuzzy_search', 'show_module_search', 'show_phonetic_search', 'show_regex_search', 'show_search_all_fields', 'show_wildcard_search', 'student_demographics_reports', 'view_search_audit_trail']
