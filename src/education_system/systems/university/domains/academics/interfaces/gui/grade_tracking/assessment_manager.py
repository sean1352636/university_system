"""Assessment management"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, filedialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking._dialogs import messagebox
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking._dialogs import make_toplevel
import tkinter.scrolledtext as scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import math
from datetime import datetime, timedelta
import json
from education_system import paths
from education_system.systems.university.domains.academics.domain.services.assessment_service import AssessmentAssignmentService
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.utils import ensure_column_exists
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.utils import ensure_column_exists_safe
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.utils import attr_alive
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_modules_table
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_student_modules_table
from education_system.systems.university.infrastructure.database.schemas.students_table import ensure_students_table

# Mirror grade_manager's immutable-audit pattern so assessment
# mutations (create / update / delete) leave the same trail FERPA
# expects for grade mutations.
try:
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Module logger. This is the system's logging, not a private one: the
# rotating app.log handler is attached to the *root* logger by
# infrastructure/logs.py at import, and named loggers propagate up to it —
# which is why entries appear in var/logs/university/app.log tagged with the
# module path. Every sibling in this package does the same. A module must not
# call configure_logging() itself; that belongs to the entry point.
logger = logging.getLogger(__name__)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


# Database connection setup

_original_sqlite3_connect_grade = sqlite3.connect

def _patched_sqlite3_connect_grade(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "student_grading_system.db"):
            return _original_sqlite3_connect_grade(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return _original_sqlite3_connect_grade(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite3_connect_grade

# Import the database connection
try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    def get_connection():
        """Fallback database connection function"""
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        return sqlite3.connect(str(DEFAULT_DB_PATH))

# Global variables for grade systems
GRADE_SYSTEMS = {
    "letter": {
        "A+": 4.3, "A": 4.0, "A-": 3.7,
        "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7,
        "D+": 1.3, "D": 1.0, "D-": 0.7,
        "F": 0.0
    },
    "percentage": {
        "range": (0, 100),
        "conversion": {
        (90, 100): "A+", (85, 89.99): "A", (80, 84.99): "A-",
        (75, 79.99): "B+", (70, 74.99): "B", (65, 69.99): "B-",
        (60, 64.99): "C+", (55, 59.99): "C", (50, 54.99): "C-",
        (45, 49.99): "D+", (40, 44.99): "D", (35, 39.99): "D-",
        (0, 34.99): "F"
        }
    }
}

def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        min_score, max_score = score_range
        if min_score <= percentage <= max_score:
            return letter
    return 'F'

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage score (midpoint of range)"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        if letter == letter_grade:
            min_score, max_score = score_range
        return (min_score + max_score) / 2
    return 0

def letter_to_gpa(letter_grade):
    """Convert a letter grade to a GPA value"""
    if letter_grade in GRADE_SYSTEMS["letter"]:
        return GRADE_SYSTEMS["letter"][letter_grade]
    return 0

def init_basic_database():
    """Initialize the basic database tables that are missing"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create students table
        ensure_students_table(cursor)

        # Create modules table
        ensure_modules_table(cursor)

        # Create student_modules table (enrollment)
        ensure_student_modules_table(cursor)

        # Create assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_name TEXT NOT NULL,
        assessment_type TEXT NOT NULL,
        module_code TEXT NOT NULL,
        max_points REAL NOT NULL,
        weight REAL NOT NULL,
        due_date TEXT,
        date_created TEXT DEFAULT (datetime('now')),
        description TEXT,
        rubric TEXT,
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Ensure rubric column exists for legacy databases.
        ensure_column_exists(cursor, 'assessments', 'rubric', 'TEXT')

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Database error: {e}")
        return False

def init_enhanced_grades_db():
    """Initialize the enhanced grades database with all required tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create base grade tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        assessment_id INTEGER,
        score REAL,
        letter_grade TEXT,
        submission_date TEXT,
        comments TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        final_score REAL,
        final_grade TEXT,
        completion_date TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Enhanced tables for statistics and analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_statistics (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER,
        mean REAL,
        median REAL,
        std_dev REAL,
        min_score REAL,
        max_score REAL,
        q1 REAL,
        q3 REAL,
        skewness REAL,
        kurtosis REAL,
        date_calculated TEXT,
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS normalized_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade_id INTEGER,
        z_score REAL,
        percentile REAL,
        curved_score REAL,
        curved_letter TEXT,
        FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
        )
        ''')

        # Predictive analytics tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_factors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        factor_name TEXT,
        factor_value REAL,
        assessment_id INTEGER,
        date_calculated TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_factor_id INTEGER,
        detail TEXT,
        weight REAL,
        created_at TEXT,
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        risk_factor_id INTEGER,
        intervention_type_id INTEGER,
        recommended_date TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id),
        FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
        )
        ''')

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Database error: {e}")
        return False

def safe_grab_set(dialog):
    """Safely set grab on dialog window, handling TclError exceptions"""
    try:
        # Ensure dialog is visible first
        dialog.update_idletasks()
        dialog.grab_set()
    except tk.TclError:
        # If grab fails, continue without modal behavior
        pass

def safe_combo_update(obj, combo_attr, values):
    """Safely update combobox values, handling widget destruction"""
    try:
        if hasattr(obj, combo_attr):
            combo = getattr(obj, combo_attr)
        if combo and combo.winfo_exists():
            combo['values'] = values
            return True
    except (tk.TclError, AttributeError):
        # Widget no longer exists or is invalid
        pass
    return False

def _merge_assessment_sources(assessments, assignments, exams):
    """One row per real piece of work, across the three tables.

    The same item can exist in all three: an exam is copied into
    ``assessments`` by the exam sync, and an assessment is copied into
    ``assignments`` by the assignment sync. Neither copy records where it came
    from, so they are matched on module code, title and the date part of the
    due date — the same three fields the syncs themselves compare.

    An exam wins over an assessment, which wins over an assignment: the
    further from the copy, the more authoritative. Rows are returned in the
    order they were given, so the existing sort is preserved.
    """
    def key(row):
        module = str(row[3] or "").strip().lower()
        name = str(row[1] or "").strip().lower()
        due = str(row[6] or "")[:10]
        return (module, name, due)

    seen = {}
    order = []
    # Highest precedence first, so the first row to claim a key is the winner.
    for source in (exams, assessments, assignments):
        for row in source:
            k = key(row)
            if k in seen:
                continue
            seen[k] = row
            order.append(row)
    return order


class AssessmentManager:
    """Assessment management"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None

    def create_assessment_content(self):
        """Create assessment management content"""
        # Assessment management controls
        control_frame = ttk.Frame(self.content_frame)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(control_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.add_assessment', default="Add Assessment"),
                  command=self.add_assessment_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.edit_assessment', default="Edit Assessment"),
                  command=self.edit_assessment_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.delete_assessment', default="Delete Assessment"),
                  command=self.delete_assessment).pack(side='left', padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.copy_assessment', default="Copy Assessment"),
                  command=self.copy_assessment).pack(side='left', padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.refresh', default="Refresh"),
                  command=self.refresh_assessments).pack(side='left', padx=5)
        # No "Load from …" buttons any more. Assignments and exams are read
        # live by refresh_assessments, so there is nothing to import: the
        # buttons used to copy rows between tables, which is what created the
        # duplicate entries this list now shows as one.
        ttk.Label(control_frame, text=_t(
            'gui.academics.grade_tracking.assessment_manager.labels.live_sources',
            default="Includes assignments and exams automatically.")).pack(
            side='right', padx=5)

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.academics.grade_tracking.assessment_manager.labels.filter_by_module', default="Filter by Module:")).pack(side='left', padx=5)
        self.assessment_module_filter_var = tk.StringVar()
        self.assessment_module_combo = ttk.Combobox(filter_frame,
                                                   textvariable=self.assessment_module_filter_var,
                                                   width=20, state='readonly')
        self.assessment_module_combo.pack(side='left', padx=5)
        self.assessment_module_combo.bind('<<ComboboxSelected>>', self.filter_assessments)

        # Assessment list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('ID', 'Name', 'Type', 'Module', 'Max Points', 'Weight %', 'Due Date')
        self.assessment_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=25)

        for col in columns:
            self.assessment_tree.heading(col, text=col)
            self.assessment_tree.column(col, width=120, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.assessment_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.assessment_tree.xview)
        self.assessment_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.assessment_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Load assessment data
        self.refresh_assessments()

        # Populate filter combos now that they exist
        self.populate_filter_combos()


    def generate_assessment_analysis(self):
        """Generate assessment analysis"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                a.assessment_id,
                a.assessment_name,
                a.module_code,
                a.assessment_type,
                a.max_points,
                COUNT(g.grade_id) AS submissions,
                AVG(
                    CASE
                        WHEN a.max_points IS NOT NULL AND a.max_points > 0
                        THEN (g.score / a.max_points) * 100
                    END
                ) AS avg_percentage,
                SUM(CASE WHEN g.letter_grade = 'F' THEN 1 ELSE 0 END) AS fail_count
            FROM assessments a
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            GROUP BY a.assessment_id, a.assessment_name, a.module_code, a.assessment_type, a.max_points
            ''')
            assessment_rows = cursor.fetchall()

            if not assessment_rows:
                self._display_report(
                    "Assessment Analysis Report",
                    [("Summary", ["No assessments have been recorded."])],
                    None
                )
                return

            summary_lines = [
                f"Total Assessments: {len(assessment_rows)}",
                f"Assessments With Submitted Grades: {sum(1 for row in assessment_rows if row[5] > 0)}",
                f"Average Submission Count: "
                f"{(sum(row[5] for row in assessment_rows) / len(assessment_rows)):.1f}",
                f"Average Assessment Score: "
                f"{(sum(row[6] for row in assessment_rows if row[6] is not None) / max(1, sum(1 for row in assessment_rows if row[6] is not None))):.1f}%"
                if any(row[6] is not None for row in assessment_rows) else "Average Assessment Score: N/A"
            ]

            top_assessments = sorted(
                [row for row in assessment_rows if row[6] is not None],
                key=lambda r: r[6],
                reverse=True
            )[:5]

            top_lines = [
                f"{idx + 1}. {row[1]} [{row[2]}] - Avg Score {row[6]:.1f}% "
                f"(Submissions: {row[5]})"
                for idx, row in enumerate(top_assessments)
            ]

            challenging_assessments = sorted(
                [row for row in assessment_rows if row[6] is not None and row[5] > 0],
                key=lambda r: (r[6], -r[5])
            )[:5]

            challenging_lines = [
                f"{idx + 1}. {row[1]} [{row[2]}] - Avg Score {row[6]:.1f}% "
                f"(Fail Count: {row[7]})"
                for idx, row in enumerate(challenging_assessments)
            ]

            missing_lines = [
                f"{row[1]} [{row[2]}] - No submissions recorded"
                for row in assessment_rows if row[5] == 0
            ][:5]

            sections = [
                ("Assessment Overview", summary_lines),
                ("High Performing Assessments", top_lines),
                ("Assessments Requiring Review", challenging_lines),
                ("Assessments Awaiting Grades", missing_lines)
            ]

            footer = (
                "Consider reviewing assessments with low average scores or high failure counts to adjust support "
                "resources or re-examine assessment design."
            )

            self._display_report("Assessment Analysis Report", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Failed to generate assessment analysis: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.error', default="Error"), f"Failed to generate assessment analysis: {e}")
        finally:
            if conn:
                conn.close()

    def add_assessment_dialog(self):
        """Open dialog to add a new assessment (matches Create Assessment form)"""
        dialog = make_toplevel(self.root)
        dialog.title(_t('gui.academics.grade_tracking.assessment_manager.windows.add_assessment', default="Add Assessment"))
        dialog.geometry("600x750")
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Assessment name
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.title', default="Title:")).grid(row=0, column=0, padx=10, pady=8, sticky='w')
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=8)

        # Module selection
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.module', default="Module:")).grid(row=1, column=0, padx=10, pady=8, sticky='w')
        module_var = tk.StringVar()
        module_combo = ttk.Combobox(dialog, textvariable=module_var, width=38, state='readonly')
        module_combo.grid(row=1, column=1, padx=10, pady=8)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            module_combo['values'] = [f"{m[0]} - {m[1]}" for m in modules]
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error loading modules: {e}")
            dialog.destroy()
            return

        # Assessment type
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.assessment_type', default="Assessment Type:")).grid(row=2, column=0, padx=10, pady=8, sticky='w')
        type_var = tk.StringVar(value=_t('gui.academics.grade_tracking.assessment_manager.values.exam', default="exam"))
        type_combo = ttk.Combobox(dialog, textvariable=type_var, width=38, state='readonly',
                                  values=["exam", "quiz", "test", "project", "presentation", "practical"])
        type_combo.grid(row=2, column=1, padx=10, pady=8)

        # Due date and time
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.due_date', default="Due Date:")).grid(row=3, column=0, padx=10, pady=8, sticky='w')
        date_frame = ttk.Frame(dialog)
        date_frame.grid(row=3, column=1, padx=10, pady=8, sticky='w')
        due_date_var = tk.StringVar(value=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(date_frame, textvariable=due_date_var, width=14).pack(side='left')
        ttk.Label(date_frame, text=_t('gui.academics.grade_tracking.assessment_manager.labels.time', default="Time:")).pack(side='left', padx=(10, 5))
        due_time_var = tk.StringVar(value="23:59")
        ttk.Entry(date_frame, textvariable=due_time_var, width=8).pack(side='left')

        # Duration
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.duration_minutes', default="Duration (minutes):")).grid(row=4, column=0, padx=10, pady=8, sticky='w')
        duration_var = tk.StringVar(value="120")
        ttk.Entry(dialog, textvariable=duration_var, width=10).grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Max points
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.max_points', default="Max Points:")).grid(row=5, column=0, padx=10, pady=8, sticky='w')
        max_points_var = tk.StringVar(value="100")
        ttk.Entry(dialog, textvariable=max_points_var, width=10).grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Weight
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.weight', default="Weight (%):")).grid(row=6, column=0, padx=10, pady=8, sticky='w')
        weight_var = tk.StringVar(value="25")
        ttk.Entry(dialog, textvariable=weight_var, width=10).grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Status
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.status', default="Status:")).grid(row=7, column=0, padx=10, pady=8, sticky='w')
        status_var = tk.StringVar(value=_t('gui.academics.grade_tracking.assessment_manager.values.active', default="Active"))
        ttk.Combobox(dialog, textvariable=status_var, width=20, state='readonly',
                     values=["Active", "Draft", "Archived"]).grid(row=7, column=1, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.description', default="Description:")).grid(row=8, column=0, padx=10, pady=8, sticky='nw')
        description_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
        description_text.grid(row=8, column=1, padx=10, pady=8)

        # Rubric
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.rubric', default="Rubric:")).grid(row=9, column=0, padx=10, pady=8, sticky='nw')
        rubric_text = scrolledtext.ScrolledText(dialog, width=38, height=4)
        rubric_text.grid(row=9, column=1, padx=10, pady=8)

        def save_assessment():
            name = name_var.get().strip()
            assessment_type = type_var.get()
            module = module_var.get()
            max_points = max_points_var.get().strip()
            weight = weight_var.get().strip()
            due_date = due_date_var.get().strip()
            due_time = due_time_var.get().strip()
            duration = duration_var.get().strip()
            status = status_var.get()
            description = description_text.get('1.0', 'end-1c').strip()
            rubric = rubric_text.get('1.0', 'end-1c').strip()

            if not name:
                messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.please_enter_an_assessment_name', default="Please enter an assessment name"), parent=dialog)
                return
            if not module:
                messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.please_select_a_module', default="Please select a module"), parent=dialog)
                return

            try:
                max_points_float = float(max_points) if max_points else 100
                weight_float = float(weight) if weight else 0
                duration_int = int(duration) if duration else None

                if max_points_float <= 0:
                    messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.max_points_must_be_greater_than_0', default="Max points must be greater than 0"), parent=dialog)
                    return

                module_code = module.split(' - ')[0]
                full_due = f"{due_date} {due_time}" if due_date else None

                # Written through the shared service, which also mirrors the
                # new assessment into the assignments table so it appears in
                # the Assignment GUI as well. Previously each screen only
                # ever saw what it had itself created.
                created_by = 0
                try:
                    current = getattr(self.auth, 'current_user', None) or {}
                    created_by = int(current.get('id') or 0)
                except (TypeError, ValueError):
                    created_by = 0
                new_assessment_id = AssessmentAssignmentService.create_assessment(
                    name=name, assessment_type=assessment_type,
                    module_code=module_code, max_points=max_points_float,
                    weight=weight_float, due_date=full_due,
                    duration_minutes=duration_int, status=status,
                    description=description, rubric=rubric,
                    created_by=created_by)

                if IMMUTABLE_AUDIT_AVAILABLE:
                    user_id, session_id = get_gui_context()
                    safe_log_security_event(
                        action=AuditAction.RECORD_CREATE,
                        user_id=user_id,
                        resource_type='assessment',
                        resource_id=str(new_assessment_id),
                        session_id=session_id,
                        details={
                            'assessment_name': name,
                            'assessment_type': assessment_type,
                            'module_code': module_code,
                            'max_points': max_points_float,
                            'weight': weight_float,
                            'due_date': full_due,
                        },
                    )

                # Mirror the due date into the academic calendar so it
                # shows up in the calendar view alongside lecture events.
                try:
                    from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.integrations import (
                        sync_assessment_to_calendar,
                    )
                    if full_due:
                        sync_assessment_to_calendar(
                            assessment_id=new_assessment_id,
                            name=name,
                            due_date=full_due,
                            module_code=module_code,
                        )
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

                messagebox.showinfo(_t('gui.academics.grade_tracking.assessment_manager.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.assessment_added_successfully', default="Assessment added successfully!"))
                dialog.destroy()
                self.refresh_assessments()
                if hasattr(self.app, 'populate_filter_combos'):
                    self.app.populate_filter_combos()

            except ValueError:
                messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.max_points_weight_and_duration_must_be_valid_numbers', default="Max points, weight, and duration must be valid numbers"), parent=dialog)
            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error saving assessment: {e}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=10, column=0, columnspan=2, pady=15)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.save_assessment', default="Save Assessment"), command=save_assessment).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def edit_assessment_dialog(self):
        """Open dialog to edit an existing assessment (supports both assessments and assignments tables)"""
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.grade_tracking.assessment_manager.dialogs.no_selection', default="No Selection"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.please_select_an_assessment_to_edit', default="Please select an assessment to edit"))
            return

        item = self.assessment_tree.item(selection[0])
        raw_id = str(item['values'][0])
        is_assignment = raw_id.startswith('A')

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            if is_assignment:
                real_id = int(raw_id[1:])
                cursor.execute("""
                    SELECT title, assignment_type, module_code, COALESCE(max_marks, 100),
                           0, due_date, description, instructions
                    FROM assignments WHERE id = ?
                """, (real_id,))
            else:
                real_id = raw_id
                cursor.execute("""
                    SELECT assessment_name, assessment_type, module_code, max_points,
                           weight, due_date, description, rubric
                    FROM assessments WHERE assessment_id = ?
                """, (real_id,))

            assessment_data = cursor.fetchone()

            if not assessment_data:
                messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.error', default="Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.assessment_not_found', default="Assessment not found"))
                return

            dialog = make_toplevel(self.root)
            dialog.title(_t('gui.academics.grade_tracking.assessment_manager.windows.edit_assessment', default="Edit Assessment"))
            dialog.geometry("600x700")
            dialog.transient(self.root)
            safe_grab_set(dialog)

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.title', default="Title:")).grid(row=0, column=0, padx=10, pady=8, sticky='w')
            name_var = tk.StringVar(value=assessment_data[0])
            ttk.Entry(dialog, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=8)

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.assessment_type', default="Assessment Type:")).grid(row=1, column=0, padx=10, pady=8, sticky='w')
            type_var = tk.StringVar(value=assessment_data[1] or '')
            ttk.Combobox(dialog, textvariable=type_var, width=38, state='readonly',
                        values=["exam", "quiz", "test", "project", "presentation", "practical",
                                "assignment", "individual", "group"]).grid(row=1, column=1, padx=10, pady=8)

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.module', default="Module:")).grid(row=2, column=0, padx=10, pady=8, sticky='w')
            module_var = tk.StringVar()
            module_combo = ttk.Combobox(dialog, textvariable=module_var, width=38, state='readonly')
            module_combo.grid(row=2, column=1, padx=10, pady=8)

            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            module_combo['values'] = [f"{m[0]} - {m[1]}" for m in modules]
            for m in modules:
                if m[0] == assessment_data[2]:
                    module_var.set(f"{m[0]} - {m[1]}")
                    break

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.max_points', default="Max Points:")).grid(row=3, column=0, padx=10, pady=8, sticky='w')
            max_points_var = tk.StringVar(value=str(assessment_data[3] or 100))
            ttk.Entry(dialog, textvariable=max_points_var, width=10).grid(row=3, column=1, padx=10, pady=8, sticky='w')

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.weight', default="Weight (%):")).grid(row=4, column=0, padx=10, pady=8, sticky='w')
            weight_var = tk.StringVar(value=str(assessment_data[4] or 0))
            ttk.Entry(dialog, textvariable=weight_var, width=10).grid(row=4, column=1, padx=10, pady=8, sticky='w')

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.due_date', default="Due Date:")).grid(row=5, column=0, padx=10, pady=8, sticky='w')
            due_date_var = tk.StringVar(value=assessment_data[5] or '')
            ttk.Entry(dialog, textvariable=due_date_var, width=30).grid(row=5, column=1, padx=10, pady=8, sticky='w')

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.description', default="Description:")).grid(row=6, column=0, padx=10, pady=8, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
            description_text.grid(row=6, column=1, padx=10, pady=8)
            description_text.insert('1.0', assessment_data[6] or '')

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.assessment_manager.labels.rubric_instructions', default="Rubric/Instructions:")).grid(row=7, column=0, padx=10, pady=8, sticky='nw')
            rubric_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
            rubric_text.grid(row=7, column=1, padx=10, pady=8)
            rubric_text.insert('1.0', assessment_data[7] or '')

            def update_assessment():
                name = name_var.get().strip()
                assessment_type = type_var.get()
                module = module_var.get()
                if not name or not module:
                    messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.title_and_module_are_required', default="Title and module are required"), parent=dialog)
                    return

                try:
                    max_pts = float(max_points_var.get() or 100)
                    wt = float(weight_var.get() or 0)
                    module_code = module.split(' - ')[0]
                    due = due_date_var.get().strip()
                    desc = description_text.get('1.0', 'end-1c').strip()
                    rubric = rubric_text.get('1.0', 'end-1c').strip()

                    update_conn = get_connection()
                    try:
                        uc = update_conn.cursor()
                        if is_assignment:
                            uc.execute("""
                                UPDATE assignments
                                SET title = ?, assignment_type = ?, module_code = ?,
                                    max_marks = ?, due_date = ?, description = ?,
                                    instructions = ?, updated_at = datetime('now')
                                WHERE id = ?
                            """, (name, assessment_type, module_code, int(max_pts),
                                  due, desc, rubric, real_id))
                        else:
                            uc.execute("""
                                UPDATE assessments
                                SET assessment_name = ?, assessment_type = ?, module_code = ?,
                                    max_points = ?, weight = ?, due_date = ?,
                                    description = ?, rubric = ?, updated_at = datetime('now')
                                WHERE assessment_id = ?
                            """, (name, assessment_type, module_code, max_pts, wt,
                                  due, desc, rubric, real_id))
                        update_conn.commit()
                    finally:
                        update_conn.close()

                    if IMMUTABLE_AUDIT_AVAILABLE:
                        user_id, session_id = get_gui_context()
                        safe_log_security_event(
                            action=AuditAction.RECORD_UPDATE,
                            user_id=user_id,
                            resource_type='assessment',
                            resource_id=str(real_id),
                            session_id=session_id,
                            details={
                                'assessment_name': name,
                                'assessment_type': assessment_type,
                                'module_code': module_code,
                                'max_points': max_pts,
                                'due_date': due,
                            },
                        )

                    messagebox.showinfo(_t('gui.academics.grade_tracking.assessment_manager.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.assessment_updated_successfully', default="Assessment updated successfully!"))
                    dialog.destroy()
                    self.refresh_assessments()
                except ValueError:
                    messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.max_points_and_weight_must_be_valid_numbers', default="Max points and weight must be valid numbers"), parent=dialog)
                except sqlite3.Error as e:
                    messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error updating assessment: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.grid(row=8, column=0, columnspan=2, pady=15)
            ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.update', default="Update"), command=update_assessment).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.assessment_manager.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error loading assessment: {e}")
        finally:
            if conn:
                conn.close()

    def delete_assessment(self):
        """Delete the selected assessment or assignment.

        Which table the row lives in is the service's problem — this list
        merges assessments, assignments and exams.
        """
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.grade_tracking.assessment_manager.dialogs.no_selection', default="No Selection"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.please_select_an_assessment_to_delete', default="Please select an assessment to delete"))
            return

        item = self.assessment_tree.item(selection[0])
        raw_id = str(item['values'][0])
        assessment_name = item['values'][1]

        if not messagebox.askyesno(_t('gui.academics.grade_tracking.assessment_manager.dialogs.confirm_deletion', default="Confirm Deletion"),
                                   f"Are you sure you want to delete '{assessment_name}'?\n\n"
                                   "This will also delete all associated grades/submissions!"):
            return

        try:
            AssessmentAssignmentService.delete_item(raw_id)
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error deleting assessment: {e}")
            return

        if IMMUTABLE_AUDIT_AVAILABLE:
            user_id, session_id = get_gui_context()
            safe_log_security_event(
                action=AuditAction.RECORD_DELETE,
                user_id=user_id,
                resource_type='assessment',
                resource_id=str(raw_id),
                session_id=session_id,
                details={'raw_id': str(raw_id), 'cascade': True},
            )

        messagebox.showinfo(_t('gui.academics.grade_tracking.assessment_manager.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.assessment_deleted_successfully', default="Assessment deleted successfully!"))
        self.refresh_assessments()
        if hasattr(self.app, 'populate_filter_combos'):
            self.app.populate_filter_combos()


    def copy_assessment(self):
        """Duplicate the selected assessment or assignment."""
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.grade_tracking.assessment_manager.dialogs.no_selection', default="No Selection"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.please_select_an_assessment_to_copy', default="Please select an assessment to copy"))
            return

        raw_id = str(self.assessment_tree.item(selection[0])['values'][0])
        try:
            new_name = AssessmentAssignmentService.copy_item(raw_id)
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Error copying assessment: {e}")
            return

        if not new_name:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.error', default="Error"), _t('gui.academics.grade_tracking.assessment_manager.dialogs.assessment_not_found', default="Assessment not found"))
            return

        messagebox.showinfo(_t('gui.academics.grade_tracking.assessment_manager.dialogs.success', default="Success"), f"Assessment copied as '{new_name}'!")
        self.refresh_assessments()
        if hasattr(self.app, 'populate_filter_combos'):
            self.app.populate_filter_combos()


    def refresh_assessments(self):
        """Refresh the assessments list from database (includes both assessments and assignments)"""
        # The tree is destroyed whenever the user navigates to another view;
        # a stale reference here is normal, not an error.
        if not attr_alive(self, 'assessment_tree'):
            return

        conn = None
        try:
            # Clear existing items
            for item in self.assessment_tree.get_children():
                self.assessment_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Get filter value if it exists
            filter_module = None
            if hasattr(self, 'assessment_module_filter_var'):
                filter_value = self.assessment_module_filter_var.get()
                if filter_value and filter_value != 'All':
                    filter_module = filter_value

            # Build query with optional filter for assessments table
            if filter_module:
                cursor.execute('''
                    SELECT assessment_id, assessment_name, assessment_type, module_code,
                           max_points, weight, due_date
                    FROM assessments
                    WHERE module_code = ?
                    ORDER BY due_date DESC, assessment_name
                ''', (filter_module,))
            else:
                cursor.execute('''
                    SELECT assessment_id, assessment_name, assessment_type, module_code,
                           max_points, weight, due_date
                    FROM assessments
                    ORDER BY due_date DESC, assessment_name
                ''')

            assessments_from_assessments = cursor.fetchall()

            # Build query for assignments table (created via assignment GUI)
            if filter_module:
                cursor.execute('''
                    SELECT 'A' || id as assessment_id, title as assessment_name,
                           'assignment' as assessment_type, module_code,
                           COALESCE(max_marks, 100) as max_points, 0 as weight, due_date
                    FROM assignments
                    WHERE module_code = ?
                    ORDER BY due_date DESC, title
                ''', (filter_module,))
            else:
                cursor.execute('''
                    SELECT 'A' || id as assessment_id, title as assessment_name,
                           'assignment' as assessment_type, module_code,
                           COALESCE(max_marks, 100) as max_points, 0 as weight, due_date
                    FROM assignments
                    ORDER BY due_date DESC, title
                ''')

            assessments_from_assignments = cursor.fetchall()

            # Exams, read live from the exam system.
            #
            # This used to require pressing "Load from Exam Scheduling", which
            # *copied* each exam into `assessments`. Copying is what produced
            # the duplicates: one exam ended up as an exams row, an assessments
            # row and — once the assignment sync ran over that — an assignments
            # row too. Reading the three tables live shows the same information
            # with nothing written, so nothing can drift or double up.
            assessments_from_exams = []
            try:
                params = [filter_module] if filter_module else []
                # db-audit: ignore[DBW001] - literal fragment
                cursor.execute(f'''
                    SELECT 'E' || e.id as assessment_id,
                           COALESCE(NULLIF(e.exam_name, ''),
                                    e.module_code || ' exam') as assessment_name,
                           'exam' as assessment_type, e.module_code,
                           100 as max_points, 0 as weight, e.date as due_date
                    FROM exams e
                    {"WHERE e.module_code = ?" if filter_module else ""}
                    ORDER BY e.date DESC
                ''', params)
                assessments_from_exams = cursor.fetchall()
            except sqlite3.Error as exc:
                # `exams` is created lazily by the Exam Scheduling GUI.
                logger.debug("Exams unavailable for the assessment list: %s", exc)

            all_assessments = _merge_assessment_sources(
                assessments_from_assessments,
                assessments_from_assignments,
                assessments_from_exams,
            )

            for row in all_assessments:
                assessment_id, name, atype, module, max_points, weight, due_date = row
                self.assessment_tree.insert('', 'end', values=(
                    assessment_id,
                    name,
                    atype or 'N/A',
                    module,
                    max_points or 0,
                    f"{weight or 0}%",
                    due_date or 'N/A'
                ))

        except tk.TclError:
            # Widget torn down mid-refresh (view switched / window closed).
            return

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.database_error', default="Database Error"), f"Failed to load assessments: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.assessment_manager.dialogs.error', default="Error"), f"Failed to load assessments: {e}")
        finally:
            if conn:
                conn.close()

    def filter_assessments(self, event=None):
        """Filter assessments by selected module"""
        self.refresh_assessments()

    def populate_filter_combos(self):
        """Populate filter comboboxes with current data"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Load modules for assessment filter
            if attr_alive(self, 'assessment_module_combo'):
                cursor.execute("""
                    SELECT DISTINCT module_code
                    FROM modules
                    WHERE module_code IS NOT NULL AND module_code != ''
                    ORDER BY module_code
                """)
                module_results = cursor.fetchall()
                modules = ['All'] + [row[0] for row in module_results if row[0]]
                safe_combo_update(self, 'assessment_module_combo', modules)

                # Set default to 'All' if not already set
                if not self.assessment_module_filter_var.get():
                    self.assessment_module_filter_var.set('All')

        except sqlite3.Error:
            # Silent fail - filter combos are optional
            pass
        finally:
            if conn:
                conn.close()
