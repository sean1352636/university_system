"""Grades Breakdown by Module GUI (Feature 34).

Displays a per-module breakdown of assignment scores with averages and
letter grades for the currently logged-in student.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class GradesBreakdownGUI:
    """Toplevel window showing grades broken down by enrolled module."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Grades Breakdown by Module")
        self.window.geometry("1000x650")
        self.window.transient(parent)

        self._setup_ui()
        self._load_modules()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the two-panel layout."""
        ttk.Label(
            self.window,
            text="Grades Breakdown by Module",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- Left panel: module list ----
        left_frame = ttk.LabelFrame(main_frame, text="Enrolled Modules", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        self.module_listbox = tk.Listbox(left_frame, width=30, font=('Arial', 11))
        self.module_listbox.pack(fill=tk.BOTH, expand=True)
        self.module_listbox.bind('<<ListboxSelect>>', self._on_module_select)

        lb_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.module_listbox.yview)
        self.module_listbox.configure(yscrollcommand=lb_scroll.set)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Right panel: assignment scores ----
        right_frame = ttk.LabelFrame(main_frame, text="Assignment Scores", padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ('title', 'score', 'max_score', 'type', 'due_date')
        self.tree = ttk.Treeview(right_frame, columns=cols, show='headings', height=18)
        self.tree.heading('title', text='Assignment')
        self.tree.heading('score', text='Score')
        self.tree.heading('max_score', text='Max Score')
        self.tree.heading('type', text='Type')
        self.tree.heading('due_date', text='Due Date')

        self.tree.column('title', width=220)
        self.tree.column('score', width=80, anchor='center')
        self.tree.column('max_score', width=90, anchor='center')
        self.tree.column('type', width=100, anchor='center')
        self.tree.column('due_date', width=120, anchor='center')

        tree_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Bottom summary ----
        summary_frame = ttk.Frame(self.window)
        summary_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.avg_var = tk.StringVar(value="Module Average: --")
        self.letter_var = tk.StringVar(value="Letter Grade: --")

        ttk.Label(summary_frame, textvariable=self.avg_var, font=('Arial', 12, 'bold')).pack(
            side=tk.LEFT, padx=20
        )
        ttk.Label(summary_frame, textvariable=self.letter_var, font=('Arial', 12, 'bold')).pack(
            side=tk.LEFT, padx=20
        )

        # Internal mapping: listbox index -> module_code
        self._modules = []

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_modules(self):
        """Populate the module listbox with enrolled modules."""
        self.module_listbox.delete(0, tk.END)
        self._modules = []

        if not self.student_id:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT m.module_code, m.module_name "
                    "FROM student_modules sm "
                    "INNER JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE sm.student_id = ? AND LOWER(sm.status) = 'enrolled' "
                    "ORDER BY m.module_code",
                    (self.student_id,),
                ).fetchall()

                for row in rows or []:
                    code = row['module_code']
                    name = row['module_name']
                    self._modules.append(code)
                    self.module_listbox.insert(tk.END, f"{code} - {name}")
        except Exception as e:
            logger.error(f"Error loading enrolled modules: {e}")
            messagebox.showerror("Error", f"Failed to load modules: {e}", parent=self.window)

    def _on_module_select(self, event):
        """Handle module selection from the listbox."""
        selection = self.module_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self._modules):
            self._load_assignments(self._modules[idx])

    def _load_assignments(self, module_code):
        """Load assignment scores for the selected module and compute averages."""
        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.avg_var.set("Module Average: --")
        self.letter_var.set("Letter Grade: --")

        if not self.student_id:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT a.title, s.grade, a.max_marks, a.assignment_type, a.due_date "
                    "FROM assignments a "
                    "LEFT JOIN assignment_submissions s "
                    "  ON a.id = s.assignment_id AND s.student_id = ? "
                    "WHERE a.module_code = ? "
                    "ORDER BY a.due_date",
                    (self.student_id, module_code),
                ).fetchall()

                scores = []
                for row in rows or []:
                    title = row['title'] or ''
                    grade = row['grade']
                    max_score = row['max_marks'] or 100
                    atype = row['assignment_type'] or ''
                    due_date = row['due_date'] or ''

                    score_display = str(grade) if grade is not None else '--'
                    self.tree.insert('', tk.END, values=(
                        title, score_display, max_score, atype, due_date,
                    ))

                    if grade is not None:
                        scores.append(float(grade))

                # Compute average and letter grade
                if scores:
                    avg = round(sum(scores) / len(scores), 1)
                    letter = self._score_to_letter(avg)
                    self.avg_var.set(f"Module Average: {avg}")
                    self.letter_var.set(f"Letter Grade: {letter}")
                else:
                    self.avg_var.set("Module Average: No graded assignments")
                    self.letter_var.set("Letter Grade: --")

        except Exception as e:
            logger.error(f"Error loading assignments for {module_code}: {e}")
            messagebox.showerror(
                "Error", f"Failed to load assignments: {e}", parent=self.window
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
