# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.constants import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import os
import logging

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from university_system.modules.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def run_gui_application():
    """Main function to run the GUI application"""
    root = tk.Tk()
    app = CourseManagementGUI(root)
    
    # Create backwards compatibility wrapper
    if ORIGINAL_MODULE_AVAILABLE:
        compat_wrapper = BackwardsCompatibilityWrapper(app)
        
        # Override original functions to use GUI (optional)
        # This allows existing code to seamlessly use the GUI
        import sys
        if 'course_management' in sys.modules:
            course_management = sys.modules['course_management']
            course_management.display_enhanced_course_menu = compat_wrapper.display_enhanced_course_menu
            course_management.create_enhanced_course = compat_wrapper.create_enhanced_course
            course_management.view_all_courses = compat_wrapper.view_all_courses
            course_management.search_courses = compat_wrapper.search_courses
            course_management.generate_course_analytics = compat_wrapper.generate_course_analytics
    
    # Run the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n" + _("course_management.cli.terminated_by_user"))
    except Exception as e:
        print(_("course_management.errors.application", error=str(e)))
        messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")


def cli_interface():
    """Command line interface for backwards compatibility"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Course Management System')
    parser.add_argument('--gui', action='store_true', help='Launch GUI interface (default)')
    parser.add_argument('--cli', action='store_true', help='Use original CLI interface')
    parser.add_argument('--import-csv', type=str, help='Import courses from CSV file')
    parser.add_argument('--export-csv', type=str, help='Export courses to CSV file')
    parser.add_argument('--backup', type=str, help='Create database backup')
    
    args = parser.parse_args()
    
    if args.cli and ORIGINAL_MODULE_AVAILABLE:
        # Use original CLI interface
        print(_("course_management.cli.launching_cli"))
        try:
            # Use centralized authentication system
            auth = get_auth()
            if auth is None:
                from university_system.infrastructure.auth import UserAuth
                auth = UserAuth()
            display_enhanced_course_menu(auth)
        except NameError:
            print(_("course_management.cli.cli_not_available"))
            run_gui_application()
    
    elif args.import_csv:
        # Handle CSV import
        print(_("course_management.cli.importing_courses", file=args.import_csv))
        if not os.path.exists(args.import_csv):
            print(_("course_management.errors.file_not_found", file=args.import_csv))
            return 1

        try:
            imported_count = 0
            error_count = 0

            with open(args.import_csv, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    print(_("course_management.errors.csv_missing_columns", columns=', '.join(required_fields)))
                    return 1

                conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for row_num, row in enumerate(reader, 1):
                    try:
                        course_code = row['course_code'].strip().upper()
                        course_name = row['course_name'].strip()
                        department = row['department'].strip()

                        if not course_code or not course_name:
                            print("  " + _("course_management.cli.import_row_warning", row=row_num))
                            error_count += 1
                            continue

                        # Check for duplicates
                        cursor.execute("SELECT id FROM courses WHERE code = ?", (course_code,))
                        if cursor.fetchone():
                            print("  " + _("course_management.cli.import_course_exists", code=course_code))
                            error_count += 1
                            continue

                        # Prepare optional fields
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()

                        import uuid
                        course_id = str(uuid.uuid4())

                        # Insert course
                        cursor.execute('''
                        INSERT INTO courses (
                            id, code, name, credits, date_added,
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                              course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))

                        imported_count += 1
                        print("  " + _("course_management.cli.import_course_success", code=course_code, name=course_name))

                    except (ValueError, sqlite3.Error) as e:
                        print("  " + _("course_management.cli.import_row_error", row=row_num, error=str(e)))
                        error_count += 1
                        continue

                conn.commit()
                conn.close()

            print("\n" + _("course_management.cli.import_completed"))
            print("  " + _("course_management.cli.import_success_count", count=imported_count))
            print("  " + _("course_management.cli.import_error_count", count=error_count))
            return 0

        except Exception as e:
            print(_("course_management.errors.import_failed", error=str(e)))
            return 1

    elif args.export_csv:
        # Handle CSV export
        print(_("course_management.cli.exporting_courses", file=args.export_csv))

        try:
            conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM courses ORDER BY course_code")
            courses = cursor.fetchall()

            if not courses:
                print(_("course_management.cli.no_courses_found"))
                conn.close()
                return 1

            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]

            with open(args.export_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)

            conn.close()

            print(_("course_management.cli.export_success", count=len(courses), file=args.export_csv))
            return 0

        except Exception as e:
            print(_("course_management.errors.export_failed", error=str(e)))
            return 1

    elif args.backup:
        # Handle backup
        print(_("course_management.cli.creating_backup", file=args.backup))

        try:
            conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))

            if args.backup.endswith('.sql'):
                # SQL dump backup
                with open(args.backup, 'w') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
                print(_("course_management.cli.backup_sql_created", file=args.backup))
            else:
                # Binary database copy
                backup_conn = sqlite3.connect(args.backup)
                conn.backup(backup_conn)
                backup_conn.close()
                print(_("course_management.cli.backup_binary_created", file=args.backup))

            conn.close()
            print(_("course_management.cli.backup_completed"))
            return 0

        except Exception as e:
            print(_("course_management.errors.backup_failed", error=str(e)))
            return 1
        
    else:
        # Default to GUI
        run_gui_application()


def init_gui_mode():
    """Initialize GUI mode - can be called from original module"""
    global _gui_app_instance
    if '_gui_app_instance' not in globals():
        root = tk.Tk()
        _gui_app_instance = CourseManagementGUI(root)
        
        # Start GUI in a separate thread to avoid blocking
        import threading
        gui_thread = threading.Thread(target=root.mainloop, daemon=True)
        gui_thread.start()
    
    return _gui_app_instance


def show_gui():
    """Show the GUI interface"""
    run_gui_application()


def create_course_gui(auth=None):
    """Create course using GUI"""
    app = init_gui_mode()
    app.show_create_course()


def view_courses_gui(auth=None):
    """View courses using GUI"""
    app = init_gui_mode()
    app.refresh_course_list()


def search_courses_gui(auth=None):
    """Search courses using GUI"""
    app = init_gui_mode()
    app.show_search_dialog()


def analytics_gui(auth=None):
    """Show analytics using GUI"""
    app = init_gui_mode()
    app.generate_analytics()


def print_usage():
    """Print usage information"""
    print("""
Enhanced Course Management System - GUI Version

USAGE:
    python gui_course_management.py [options]

OPTIONS:
    --gui           Launch GUI interface (default)
    --cli           Use original CLI interface (if available)
    --import-csv    Import courses from CSV file
    --export-csv    Export courses to CSV file
    --backup        Create database backup

GUI FEATURES:
    • Tabbed interface for easy navigation
    • Advanced search and filtering
    • Course creation and editing dialogs
    • Real-time analytics and reporting
    • Instructor management
    • Prerequisites handling
    • Import/Export capabilities
    • System maintenance tools

BACKWARDS COMPATIBILITY:
    This GUI version is fully backwards compatible with the original
    CLI-based course management system. All original functions are
    supported and can be accessed through the GUI interface.

INTEGRATION:
    The GUI can be integrated with existing code by importing this
    module and calling the appropriate functions:
    
    from gui_course_management import show_gui
    show_gui()

For more information, see the Help menu in the GUI application.
""")
