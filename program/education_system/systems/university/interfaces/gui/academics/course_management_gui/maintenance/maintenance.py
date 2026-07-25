# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_table_name
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure import paths

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
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.systems.university.domain.academics.services.course_management import (
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
    from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.systems.university.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_system_maintenance(self):
    """Show system maintenance dialog (already exists as MaintenanceDialog)"""
    dialog = MaintenanceDialog(self.root, self.auth)
    if dialog.result:
        self.update_status(_("course_management.status.maintenance_completed"))


def show_maintenance(self):
    """Show system maintenance dialog"""
    dialog = MaintenanceDialog(self.root, self.auth)
    if dialog.result:
        self.update_status("Maintenance task completed")


def system_maintenance_wrapper(self):
    """System maintenance operations. Calls existing show_maintenance()."""
    self.show_maintenance()


class MaintenanceDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("System Maintenance")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="System Maintenance", font=("Arial", 12, "bold")).pack(pady=10)

        # Maintenance options
        options_frame = ttk.LabelFrame(main_frame, text="Maintenance Tasks", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Button(options_frame, text="Database Integrity Check",
                  command=self.integrity_check).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Clean Orphaned Records",
                  command=self.clean_orphaned).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Recalculate Enrollment Numbers",
                  command=self.recalculate_enrollment).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Database Statistics",
                  command=self.show_db_stats).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Optimize Database",
                  command=self.optimize_db).pack(fill=tk.X, pady=2)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = ScrolledText(results_frame, wrap=tk.WORD, height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

    def integrity_check(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            results = "DATABASE INTEGRITY CHECK\n"
            results += "=" * 40 + "\n\n"

            issues = []

            # Check for courses with invalid enrollment
            cursor.execute("""
            SELECT course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
            """)
            over_enrolled = cursor.fetchall()

            if over_enrolled:
                issues.append(f"Found {len(over_enrolled)} courses with enrollment over capacity")
                results += "Courses over capacity:\n"
                for code, current, max_val in over_enrolled:
                    results += f"  - {code}: {current}/{max_val}\n"
                results += "\n"

            # Check for negative enrollments
            cursor.execute("SELECT course_code FROM courses WHERE COALESCE(current_enrollment, 0) < 0")
            negative_enrollments = cursor.fetchall()

            if negative_enrollments:
                issues.append(f"Found {len(negative_enrollments)} courses with negative enrollment")
                results += "Courses with negative enrollment:\n"
                for (code,) in negative_enrollments:
                    results += f"  - {code}\n"
                results += "\n"

            if not issues:
                results += "✓ No integrity issues found.\n"
            else:
                results += f"⚠ Found {len(issues)} types of issues:\n"
                for issue in issues:
                    results += f"  - {issue}\n"

            conn.close()

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Integrity check failed: {e}")

    def clean_orphaned(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            results = "CLEANING ORPHANED RECORDS\n"
            results += "=" * 40 + "\n\n"

            total_deleted = 0

            # Clean orphaned prerequisites
            if self.table_exists(cursor, 'course_prerequisites'):
                cursor.execute("""
                DELETE FROM course_prerequisites
                WHERE course_id NOT IN (SELECT id FROM courses)
                   OR prerequisite_course_id NOT IN (SELECT id FROM courses)
                """)
                deleted_prereqs = cursor.rowcount
                total_deleted += deleted_prereqs
                results += f"Removed {deleted_prereqs} orphaned prerequisites\n"

            # Clean orphaned schedules
            if self.table_exists(cursor, 'course_schedule'):
                cursor.execute("DELETE FROM course_schedule WHERE course_id NOT IN (SELECT id FROM courses)")
                deleted_schedules = cursor.rowcount
                total_deleted += deleted_schedules
                results += f"Removed {deleted_schedules} orphaned schedules\n"

            # Clean orphaned waitlists
            if self.table_exists(cursor, 'course_waitlist'):
                cursor.execute("DELETE FROM course_waitlist WHERE course_id NOT IN (SELECT id FROM courses)")
                deleted_waitlists = cursor.rowcount
                total_deleted += deleted_waitlists
                results += f"Removed {deleted_waitlists} orphaned waitlist entries\n"

            conn.commit()
            conn.close()

            results += f"\n✓ Cleanup completed. Total records removed: {total_deleted}\n"

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Cleanup failed: {e}")

    def recalculate_enrollment(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            results = "RECALCULATING ENROLLMENT NUMBERS\n"
            results += "=" * 40 + "\n\n"

            # Find courses with invalid enrollment
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE COALESCE(current_enrollment, 0) < 0
               OR COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
            """)

            invalid_enrollments = cursor.fetchall()

            if invalid_enrollments:
                results += f"Found {len(invalid_enrollments)} courses with invalid enrollment:\n"
                for course_id, code, current, max_val in invalid_enrollments:
                    results += f"  - {code}: {current}/{max_val}\n"

                if messagebox.askyesno("Reset Enrollments", "Reset invalid enrollments to 0?"):
                    cursor.execute("""
                    UPDATE courses
                    SET current_enrollment = 0
                    WHERE COALESCE(current_enrollment, 0) < 0
                       OR COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
                    """)

                    updated = cursor.rowcount
                    conn.commit()
                    results += f"\n✓ Reset {updated} invalid enrollments to 0\n"
                else:
                    results += "\nNo changes made.\n"
            else:
                results += "✓ All enrollment numbers are valid.\n"

            conn.close()

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Recalculation failed: {e}")

    def show_db_stats(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            results = "DATABASE STATISTICS\n"
            results += "=" * 40 + "\n\n"

            # Table counts
            tables = ['courses', 'course_prerequisites', 'course_schedule', 'instructors']
            for table in tables:
                if self.table_exists(cursor, table):
                    safe_table = validate_table_name(table)
                    cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                    count = cursor.fetchone()[0]
                    results += f"{table}: {count} records\n"
                else:
                    results += f"{table}: Table not found\n"

            # Database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            db_size_mb = (page_count * page_size) / (1024 * 1024)
            results += f"\nDatabase size: {db_size_mb:.2f} MB\n"

            # Additional stats
            cursor.execute(
                "SELECT COUNT(*) FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active'"
            )
            active_courses = cursor.fetchone()[0]
            results += f"Active courses: {active_courses}\n"

            cursor.execute(
                "SELECT SUM(COALESCE(current_enrollment, 0)) FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active'"
            )
            total_enrollment = cursor.fetchone()[0] or 0
            results += f"Total enrollment: {total_enrollment}\n"

            conn.close()

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Statistics failed: {e}")

    def optimize_db(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            results = "DATABASE OPTIMIZATION\n"
            results += "=" * 40 + "\n\n"

            # Vacuum database
            results += "Running VACUUM...\n"
            cursor.execute("VACUUM")

            # Analyze database
            results += "Running ANALYZE...\n"
            cursor.execute("ANALYZE")

            conn.commit()
            conn.close()

            results += "\n✓ Database optimization completed.\n"

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Optimization failed: {e}")

    def table_exists(self, cursor, table_name):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
