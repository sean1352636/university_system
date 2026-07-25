# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.interfaces.gui.learners.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _safe_set_combobox, _safe_entry_insert

def manage_student_grades(self, student_id, first_name, last_name):
    """Display and manage student grades with assignments/assessments table"""
    try:
        grades_window = tk.Toplevel(self.root)
        _install_clean_close(grades_window)
        grades_window.title(f"Manage Grades - {first_name} {last_name} ({student_id})")
        grades_window.geometry("1000x600")
        grades_window.transient(self.root)

        main_frame = ttk.Frame(grades_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Grades for {first_name} {last_name}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview for grades
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Type", "Module", "Assignment", "Submitted", "Grade", "Max Grade", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Fetch grades from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            grades_window.destroy()
            return

        cursor = conn.cursor()

        # Get assignments and grades
        cursor.execute("""
            SELECT 'Assignment' as type, a.module_code, a.title,
                   CASE WHEN s.submission_date IS NOT NULL THEN 'Yes' ELSE 'No' END as submitted,
                   COALESCE(s.grade, 'Not Graded') as grade,
                   COALESCE(a.max_marks, 100) as max_marks,
                   CASE
                       WHEN s.grade IS NOT NULL THEN 'Graded'
                       WHEN s.submission_date IS NOT NULL THEN 'Submitted'
                       ELSE 'Not Submitted'
                   END as status
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
            ORDER BY a.module_code, a.due_date DESC
        """, (student_id,))

        assignments = cursor.fetchall()

        # Convert Row objects to tuples and insert into tree
        for assignment in assignments:
            tree.insert('', tk.END, values=tuple(assignment))

        # Get assessments if table exists
        assessments = []
        try:
            cursor.execute("""
                SELECT 'Assessment' as type, a.module_code, a.assessment_name,
                       'N/A' as submitted,
                       COALESCE(g.score, 'Not Graded') as score,
                       COALESCE(a.max_points, 100) as max_points,
                       CASE WHEN g.score IS NOT NULL THEN 'Graded' ELSE 'Pending' END as status
                FROM assessments a
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = ?
                WHERE a.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
                ORDER BY a.module_code
            """, (student_id, student_id))

            assessments = cursor.fetchall()
            for assessment in assessments:
                tree.insert('', tk.END, values=tuple(assessment))
        except Exception as e:
            print(f"Could not load assessments: {e}")  # For debugging

        conn.close()

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        # Calculate totals from both assignments and assessments
        all_items = list(assignments) + list(assessments)
        total_items = len(all_items)
        submitted = sum(1 for item in all_items if len(item) > 3 and item[3] == 'Yes')
        graded = sum(1 for item in all_items if len(item) > 6 and 'Graded' in str(item[6]))

        ttk.Label(summary_frame, text=f"Total Assignments: {total_items}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Submitted: {submitted}").grid(row=0, column=1, padx=10)
        ttk.Label(summary_frame, text=f"Graded: {graded}").grid(row=0, column=2, padx=10)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"), command=grades_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_grades", error=str(e)))
        if 'grades_window' in locals():
            grades_window.destroy()
