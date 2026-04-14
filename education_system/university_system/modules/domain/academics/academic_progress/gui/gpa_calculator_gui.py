"""What-If GPA Calculator GUI (Feature 37).

Allows students to enter hypothetical letter grades for enrolled modules
and see how their projected GPA would change.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.services.dashboard.student_services import StudentDashboardService

logger = logging.getLogger(__name__)


class GPACalculatorGUI:
    """Toplevel window for what-if GPA calculation."""

    GRADE_CHOICES = ['-- Keep Current --', 'A', 'B', 'C', 'D', 'F']

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("What-If GPA Calculator")
        self.window.geometry("800x550")
        self.window.transient(parent)

        # Will hold (module_code, current_grade_label, combobox) tuples
        self._module_rows = []

        self._setup_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the calculator layout."""
        ttk.Label(
            self.window,
            text="What-If GPA Calculator",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # Current GPA display
        gpa_frame = ttk.Frame(self.window)
        gpa_frame.pack(fill=tk.X, padx=15, pady=5)

        self.current_gpa_var = tk.StringVar(value="Current GPA: --")
        ttk.Label(
            gpa_frame, textvariable=self.current_gpa_var, font=('Arial', 13, 'bold')
        ).pack(side=tk.LEFT)

        # Scrollable module rows
        canvas_frame = ttk.LabelFrame(self.window, text="Enrolled Modules", padding="5")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            '<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Header row
        header = ttk.Frame(self.scrollable_frame)
        header.pack(fill=tk.X, padx=5, pady=(0, 3))
        ttk.Label(header, text="Module", font=('Arial', 10, 'bold'), width=20).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(header, text="Current Grade", font=('Arial', 10, 'bold'), width=15).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(header, text="Hypothetical", font=('Arial', 10, 'bold'), width=18).pack(
            side=tk.LEFT, padx=5
        )

        # Bottom: Calculate button + result
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        ttk.Button(bottom_frame, text="Calculate Projected GPA", command=self._calculate).pack(
            side=tk.LEFT, padx=10
        )

        self.result_var = tk.StringVar(value="")
        self.result_label = ttk.Label(
            bottom_frame, textvariable=self.result_var, font=('Arial', 13, 'bold')
        )
        self.result_label.pack(side=tk.LEFT, padx=10)

        self.delta_var = tk.StringVar(value="")
        self.delta_label = ttk.Label(
            bottom_frame, textvariable=self.delta_var, font=('Arial', 12)
        )
        self.delta_label.pack(side=tk.LEFT, padx=10)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        """Load current GPA and enrolled modules with current grades."""
        if not self.student_id:
            self.current_gpa_var.set("Current GPA: -- (not logged in)")
            return

        try:
            # Fetch current GPA via the service
            progress = StudentDashboardService.get_degree_progress_summary(self.student_id)
            gpa = progress.get('gpa')
            if gpa is not None:
                self.current_gpa_var.set(f"Current GPA: {gpa:.2f}")
            else:
                self.current_gpa_var.set("Current GPA: N/A")

            # Fetch enrolled modules and their average grades
            grades_data = StudentDashboardService.get_grades_by_module(self.student_id)

            for mod in grades_data:
                mc = mod['module_code']
                avg = mod.get('average_score')
                if avg is not None:
                    letter = self._score_to_letter(avg)
                    current_display = f"{letter} ({avg:.1f})"
                else:
                    current_display = "No grades"

                self._add_module_row(mc, current_display)

        except Exception as e:
            logger.error(f"Error loading GPA calculator data: {e}")
            messagebox.showerror("Error", f"Failed to load data: {e}", parent=self.window)

    def _add_module_row(self, module_code, current_display):
        """Add a row for a module in the scrollable frame."""
        row_frame = ttk.Frame(self.scrollable_frame)
        row_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row_frame, text=module_code, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(row_frame, text=current_display, width=15).pack(side=tk.LEFT, padx=5)

        combo = ttk.Combobox(
            row_frame, values=self.GRADE_CHOICES, state='readonly', width=16
        )
        combo.set('-- Keep Current --')
        combo.pack(side=tk.LEFT, padx=5)

        self._module_rows.append((module_code, current_display, combo))

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    def _calculate(self):
        """Collect hypothetical grades and compute projected GPA."""
        if not self.student_id:
            messagebox.showwarning("Warning", "No student logged in.", parent=self.window)
            return

        hypothetical_grades = {}
        for module_code, _display, combo in self._module_rows:
            selected = combo.get()
            if selected and selected != '-- Keep Current --':
                hypothetical_grades[module_code] = selected

        try:
            result = StudentDashboardService.simulate_gpa(self.student_id, hypothetical_grades)

            projected = result.get('projected_gpa')
            current = result.get('current_gpa')
            delta = result.get('delta', 0.0)

            if projected is not None:
                self.result_var.set(f"Projected GPA: {projected:.2f}")
            else:
                self.result_var.set("Projected GPA: N/A")

            if delta != 0.0 and current is not None and projected is not None:
                sign = '+' if delta > 0 else ''
                self.delta_var.set(f"({sign}{delta:.2f})")
                if delta > 0:
                    self.delta_label.configure(foreground='green')
                elif delta < 0:
                    self.delta_label.configure(foreground='red')
                else:
                    self.delta_label.configure(foreground='black')
            else:
                self.delta_var.set("")

        except Exception as e:
            logger.error(f"Error calculating projected GPA: {e}")
            messagebox.showerror(
                "Error", f"Failed to calculate GPA: {e}", parent=self.window
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_letter(score):
        """Convert a numeric score to a letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        return 'F'
