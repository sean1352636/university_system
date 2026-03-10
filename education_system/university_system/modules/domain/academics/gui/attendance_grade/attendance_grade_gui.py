"""Attendance-to-Grade Integration GUI (Feature 27)."""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class AttendanceGradeConfigGUI:
    """Toplevel window for configuring attendance-to-grade weights."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Attendance-Grade Configuration")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self._ensure_table()
        self._setup_ui()
        self._load_courses()

    def _ensure_table(self):
        """Create attendance_grade_config table if it doesn't exist."""
        try:
            with transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS attendance_grade_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT NOT NULL UNIQUE,
                        attendance_weight REAL NOT NULL DEFAULT 10.0,
                        min_attendance_pct REAL NOT NULL DEFAULT 75.0,
                        created_by TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except Exception as e:
            logger.error(f"Error creating attendance_grade_config table: {e}")

    def _setup_ui(self):
        """Build the configuration UI."""
        ttk.Label(
            self.window, text="Module Attendance & Grades",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Module selector
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Label(top_frame, text="Module:").pack(side=tk.LEFT, padx=(0, 5))
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            top_frame, textvariable=self.course_var,
            state='readonly', width=40
        )
        self.course_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.course_combo.bind('<<ComboboxSelected>>', lambda e: self._load_config())

        # Configuration
        config_frame = ttk.LabelFrame(self.window, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, padx=15, pady=5)

        weight_row = ttk.Frame(config_frame)
        weight_row.pack(fill=tk.X, pady=5)
        ttk.Label(weight_row, text="Attendance Weight (%):").pack(side=tk.LEFT, padx=(0, 10))
        self.weight_var = tk.DoubleVar(value=10.0)
        self.weight_spin = ttk.Spinbox(
            weight_row, from_=0, to=100, increment=1,
            textvariable=self.weight_var, width=10
        )
        self.weight_spin.pack(side=tk.LEFT)

        min_row = ttk.Frame(config_frame)
        min_row.pack(fill=tk.X, pady=5)
        ttk.Label(min_row, text="Minimum Attendance (%):").pack(side=tk.LEFT, padx=(0, 10))
        self.min_att_var = tk.DoubleVar(value=75.0)
        self.min_att_spin = ttk.Spinbox(
            min_row, from_=0, to=100, increment=1,
            textvariable=self.min_att_var, width=10
        )
        self.min_att_spin.pack(side=tk.LEFT)

        btn_row = ttk.Frame(config_frame)
        btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="Save Configuration", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Calculate Grades", command=self._calculate_preview).pack(side=tk.LEFT, padx=5)

        # Student grades table
        preview_frame = ttk.LabelFrame(self.window, text="Student Grades", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('student_id', 'name', 'avg_grade', 'assignments_graded', 'attendance_pct')
        self.tree = ttk.Treeview(preview_frame, columns=cols, show='headings')
        self.tree.heading('student_id', text='Student ID')
        self.tree.heading('name', text='Name')
        self.tree.heading('avg_grade', text='Avg Grade')
        self.tree.heading('assignments_graded', text='Graded')
        self.tree.heading('attendance_pct', text='Attendance %')
        self.tree.column('student_id', width=120)
        self.tree.column('name', width=200)
        self.tree.column('avg_grade', width=100, anchor='center')
        self.tree.column('assignments_graded', width=80, anchor='center')
        self.tree.column('attendance_pct', width=120, anchor='center')

        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="Select a module to view grades.")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor="w", padx=15, pady=5)

    def _load_courses(self):
        """Load modules based on user role."""
        try:
            role = ''
            if self.auth and self.auth.current_user:
                role = self.auth.current_user.get('role', '')

            with get_connection() as conn:
                if role in ('staff', 'admin'):
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules ORDER BY module_code"
                    ).fetchall()
                else:
                    user_id = (
                        self.auth.current_user.get('id', '')
                        if self.auth and self.auth.current_user else ''
                    )
                    rows = conn.execute(
                        "SELECT DISTINCT m.module_code, m.module_name FROM modules m "
                        "INNER JOIN module_schedule ms ON m.module_code = ms.module_code "
                        "WHERE ms.instructor_id = ? ORDER BY m.module_code",
                        (user_id,)
                    ).fetchall()
                courses = [f"{r['module_code']} - {r['module_name']}" for r in (rows or [])]
                self.course_combo['values'] = courses
        except Exception as e:
            logger.error(f"Error loading modules: {e}")

    def _load_config(self):
        """Load existing config for the selected course."""
        selection = self.course_var.get()
        if not selection:
            return
        module_code = selection.split(' - ')[0].strip()

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT attendance_weight, min_attendance_pct "
                    "FROM attendance_grade_config WHERE module_code = ?",
                    (module_code,)
                ).fetchone()
                if row:
                    self.weight_var.set(row['attendance_weight'])
                    self.min_att_var.set(row['min_attendance_pct'])
                else:
                    self.weight_var.set(10.0)
                    self.min_att_var.set(75.0)
        except Exception as e:
            logger.error(f"Error loading config: {e}")

        self._calculate_preview()

    def _save_config(self):
        """Save the attendance-grade configuration."""
        selection = self.course_var.get()
        if not selection:
            messagebox.showwarning("No Course", "Please select a course.", parent=self.window)
            return
        module_code = selection.split(' - ')[0].strip()

        try:
            with transaction() as conn:
                existing = conn.execute(
                    "SELECT id FROM attendance_grade_config WHERE module_code = ?",
                    (module_code,)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE attendance_grade_config SET attendance_weight = ?, "
                        "min_attendance_pct = ?, updated_at = datetime('now') "
                        "WHERE module_code = ?",
                        (self.weight_var.get(), self.min_att_var.get(), module_code)
                    )
                else:
                    conn.execute(
                        "INSERT INTO attendance_grade_config "
                        "(module_code, attendance_weight, min_attendance_pct, created_by) "
                        "VALUES (?, ?, ?, ?)",
                        (module_code, self.weight_var.get(), self.min_att_var.get(), self.instructor_id)
                    )

            try:
                uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
                role = self.auth.current_user.get('role', '') if self.auth and self.auth.current_user else ''
                log_activity(
                    uid, self.instructor_id, role,
                    'save_attendance_config', 'attendance_grade',
                    details=f"Saved config for {module_code}: weight={self.weight_var.get()}%"
                )
            except Exception:
                pass

            self.status_var.set(f"Configuration saved for {module_code}.")
            messagebox.showinfo("Saved", "Configuration saved successfully.", parent=self.window)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            messagebox.showerror("Error", f"Failed to save: {e}", parent=self.window)

    def _calculate_preview(self):
        """Load student grades and attendance for the selected module."""
        selection = self.course_var.get()
        if not selection:
            return
        module_code = selection.split(' - ')[0].strip()

        self.tree.delete(*self.tree.get_children())
        try:
            with get_connection() as conn:
                # Get enrolled students with their grade averages
                rows = conn.execute(
                    "SELECT sm.student_id, "
                    "s.first_name || ' ' || s.last_name as name "
                    "FROM student_modules sm "
                    "JOIN students s ON sm.student_id = s.student_id "
                    "WHERE sm.module_code = ? AND sm.status IN ('Enrolled', 'enrolled') "
                    "ORDER BY s.last_name, s.first_name",
                    (module_code,)
                ).fetchall()

                for r in (rows or []):
                    sid = r['student_id']

                    # Get grade average for this student in this module
                    grade_row = conn.execute(
                        "SELECT ROUND(AVG(sub.grade), 1) as avg_grade, "
                        "COUNT(sub.id) as graded_count "
                        "FROM assignment_submissions sub "
                        "JOIN assignments a ON sub.assignment_id = a.id "
                        "WHERE a.module_code = ? AND sub.student_id = ? "
                        "AND sub.grade IS NOT NULL",
                        (module_code, sid)
                    ).fetchone()
                    avg_grade = grade_row['avg_grade'] if grade_row and grade_row['avg_grade'] is not None else None
                    graded_count = grade_row['graded_count'] if grade_row else 0

                    # Get attendance percentage (table is per-student, not per-module)
                    att_row = conn.execute(
                        "SELECT attendance_percentage FROM attendance_analytics "
                        "WHERE student_id = ?",
                        (sid,)
                    ).fetchone()
                    att_pct = att_row['attendance_percentage'] if att_row and att_row['attendance_percentage'] is not None else None

                    self.tree.insert('', tk.END, values=(
                        sid,
                        r['name'],
                        f"{avg_grade:.1f}" if avg_grade is not None else 'N/A',
                        graded_count,
                        f"{att_pct:.1f}%" if att_pct is not None else 'N/A',
                    ))

                self.status_var.set(f"{len(rows or [])} enrolled students in {module_code}.")
        except Exception as e:
            logger.error(f"Error loading student grades: {e}")
            self.status_var.set("Error loading grade data.")
