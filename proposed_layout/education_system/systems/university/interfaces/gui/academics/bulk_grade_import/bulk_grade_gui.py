"""Bulk Grade Import GUI (Feature 25)."""

import csv
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class BulkGradeImportGUI:
    """Toplevel window for bulk importing grades from CSV files."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Bulk Grade Import")
        self.window.geometry("1000x700")
        self.window.transient(parent)

        self.parsed_data = []
        self.valid_students = set()

        self._setup_ui()
        self._load_assignments()

    def _setup_ui(self):
        """Build the bulk grade import UI."""
        ttk.Label(
            self.window, text="Bulk Grade Import",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Top: assignment selector + file selector
        top_frame = ttk.LabelFrame(self.window, text="Import Settings", padding="10")
        top_frame.pack(fill=tk.X, padx=15, pady=5)

        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Assignment:").pack(side=tk.LEFT, padx=(0, 5))
        self.assignment_var = tk.StringVar()
        self.assignment_combo = ttk.Combobox(
            row1, textvariable=self.assignment_var,
            state='readonly', width=50
        )
        self.assignment_combo.pack(side=tk.LEFT, padx=(0, 15))

        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="CSV File:").pack(side=tk.LEFT, padx=(0, 5))
        self.file_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.file_var, width=50, state='readonly').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="Browse...", command=self._browse_file).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Button(row2, text="Preview & Validate", command=self._preview_data).pack(side=tk.LEFT)

        # Column mapping
        map_frame = ttk.LabelFrame(self.window, text="Column Mapping", padding="10")
        map_frame.pack(fill=tk.X, padx=15, pady=5)

        map_row = ttk.Frame(map_frame)
        map_row.pack(fill=tk.X)
        ttk.Label(map_row, text="Student ID Column:").pack(side=tk.LEFT, padx=(0, 5))
        self.sid_col_var = tk.StringVar()
        self.sid_col_combo = ttk.Combobox(map_row, textvariable=self.sid_col_var, state='readonly', width=20)
        self.sid_col_combo.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(map_row, text="Grade Column:").pack(side=tk.LEFT, padx=(0, 5))
        self.grade_col_var = tk.StringVar()
        self.grade_col_combo = ttk.Combobox(map_row, textvariable=self.grade_col_var, state='readonly', width=20)
        self.grade_col_combo.pack(side=tk.LEFT)

        # Preview table
        tree_frame = ttk.LabelFrame(self.window, text="Preview", padding="5")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('student_id', 'grade', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        self.tree.heading('student_id', text='Student ID')
        self.tree.heading('grade', text='Grade')
        self.tree.heading('status', text='Validation Status')
        self.tree.column('student_id', width=200)
        self.tree.column('grade', width=150)
        self.tree.column('status', width=300)
        self.tree.tag_configure('valid', background='#d4edda')
        self.tree.tag_configure('invalid', background='#f8d7da')

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom: import button
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        self.import_btn = ttk.Button(btn_frame, text="Import Grades", command=self._import_grades)
        self.import_btn.pack(side=tk.RIGHT)
        self.status_var = tk.StringVar(value="Select an assignment and CSV file.")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.LEFT)

    def _load_assignments(self):
        """Load assignments for instructor's courses.

        Uses a role-based approach: staff/admin users see all assignments,
        while instructors see modules they are assigned to via the
        ``modules.instructor`` column or the ``module_schedule`` table.
        """
        try:
            role = ''
            if self.auth and self.auth.current_user:
                role = self.auth.current_user.get('role', '')

            with get_connection() as conn:
                if role in ('admin', 'staff'):
                    rows = conn.execute(
                        "SELECT a.id, a.title, a.module_code FROM assignments a "
                        "ORDER BY a.due_date DESC",
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT a.id, a.title, a.module_code FROM assignments a "
                        "JOIN modules m ON a.module_code = m.module_code "
                        "WHERE m.instructor = ? OR m.module_code IN "
                        "(SELECT module_code FROM module_schedule WHERE instructor_id = ?) "
                        "ORDER BY a.due_date DESC",
                        (self.instructor_id, self.instructor_id)
                    ).fetchall()
                items = [f"{r['id']} - {r['module_code']} - {r['title']}" for r in (rows or [])]
                self.assignment_combo['values'] = items

                # Cache valid students per assignment
                self.valid_students = set()
        except Exception as e:
            logger.error(f"Error loading assignments: {e}")

    def _browse_file(self):
        """Open file dialog to select CSV."""
        filepath = filedialog.askopenfilename(
            parent=self.window,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filepath:
            self.file_var.set(filepath)
            self._detect_columns(filepath)

    def _detect_columns(self, filepath):
        """Detect CSV columns and populate mapping dropdowns."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
            self.sid_col_combo['values'] = headers
            self.grade_col_combo['values'] = headers
            # Auto-detect common column names
            for h in headers:
                hl = h.lower().strip()
                if hl in ('student_id', 'studentid', 'id', 'student'):
                    self.sid_col_var.set(h)
                elif hl in ('grade', 'score', 'mark', 'marks'):
                    self.grade_col_var.set(h)
        except Exception as e:
            logger.error(f"Error reading CSV headers: {e}")

    def _preview_data(self):
        """Parse CSV and validate data."""
        filepath = self.file_var.get()
        sid_col = self.sid_col_var.get()
        grade_col = self.grade_col_var.get()
        assignment_sel = self.assignment_var.get()

        if not filepath or not sid_col or not grade_col or not assignment_sel:
            messagebox.showwarning(
                "Missing Info",
                "Please select an assignment, CSV file, and map columns.",
                parent=self.window
            )
            return

        assignment_id = int(assignment_sel.split(' - ')[0])

        # Load valid students for this assignment's course
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT module_code FROM assignments WHERE id = ?", (assignment_id,)
                ).fetchone()
                if row:
                    students = conn.execute(
                        "SELECT student_id FROM student_modules "
                        "WHERE module_code = ? AND status = 'Enrolled'",
                        (row['module_code'],)
                    ).fetchall()
                    self.valid_students = {s['student_id'] for s in (students or [])}
        except Exception:
            self.valid_students = set()

        # Parse CSV
        self.parsed_data = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    student_id = row.get(sid_col, '').strip()
                    grade_str = row.get(grade_col, '').strip()
                    self.parsed_data.append({
                        'student_id': student_id,
                        'grade_str': grade_str,
                    })
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse CSV: {e}", parent=self.window)
            return

        # Validate and display
        self.tree.delete(*self.tree.get_children())
        valid_count = 0
        for entry in self.parsed_data:
            issues = []
            if not entry['student_id']:
                issues.append("Missing student ID")
            elif entry['student_id'] not in self.valid_students:
                issues.append("Student not enrolled")

            try:
                grade_val = float(entry['grade_str'])
                if grade_val < 0 or grade_val > 100:
                    issues.append("Grade out of range (0-100)")
                entry['grade'] = grade_val
            except (ValueError, TypeError):
                issues.append("Invalid grade value")
                entry['grade'] = None

            entry['valid'] = len(issues) == 0
            status_text = "Valid" if entry['valid'] else "; ".join(issues)
            tag = 'valid' if entry['valid'] else 'invalid'
            if entry['valid']:
                valid_count += 1

            self.tree.insert('', tk.END, values=(
                entry['student_id'], entry['grade_str'], status_text
            ), tags=(tag,))

        self.status_var.set(f"{valid_count}/{len(self.parsed_data)} entries valid. Ready to import.")

    def _import_grades(self):
        """Import validated grades into the database."""
        assignment_sel = self.assignment_var.get()
        if not assignment_sel:
            messagebox.showwarning("No Assignment", "Please select an assignment.", parent=self.window)
            return

        valid_entries = [e for e in self.parsed_data if e.get('valid')]
        if not valid_entries:
            messagebox.showwarning("No Valid Data", "No valid entries to import.", parent=self.window)
            return

        assignment_id = int(assignment_sel.split(' - ')[0])

        if not messagebox.askyesno(
            "Confirm Import",
            f"Import grades for {len(valid_entries)} students?",
            parent=self.window
        ):
            return

        imported = 0
        try:
            with transaction() as conn:
                for entry in valid_entries:
                    conn.execute(
                        "UPDATE assignment_submissions SET grade = ?, graded_by = ?, "
                        "graded_date = datetime('now') "
                        "WHERE assignment_id = ? AND student_id = ? AND grade IS NULL",
                        (entry['grade'], self.instructor_id, assignment_id, entry['student_id'])
                    )
                    if conn.execute("SELECT changes()").fetchone()[0] > 0:
                        imported += 1

            try:
                log_activity(
                    self.instructor_id, self.instructor_id, 'instructor',
                    'bulk_grade_import', 'bulk_grade_import',
                    details=f"Imported {imported} grades for assignment {assignment_id}"
                )
            except Exception:
                pass

            messagebox.showinfo(
                "Import Complete",
                f"Successfully imported {imported} grades.",
                parent=self.window
            )
            self.status_var.set(f"Imported {imported} grades.")
        except Exception as e:
            logger.error(f"Error importing grades: {e}")
            messagebox.showerror("Error", f"Import failed: {e}", parent=self.window)
