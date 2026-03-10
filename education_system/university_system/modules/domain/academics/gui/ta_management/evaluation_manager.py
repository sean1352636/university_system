"""TA Performance Evaluation Manager (Feature 30)."""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class EvaluationManager:
    """Manages the Performance Evaluation tab in TA Management GUI."""

    def __init__(self, parent_frame, service, auth=None):
        self.parent = parent_frame
        self.service = service
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self._ensure_table()
        self._setup_ui()
        self._load_evaluations()

    def _ensure_table(self):
        """Create ta_evaluations table if it doesn't exist."""
        try:
            with transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ta_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ta_id TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        evaluation_period TEXT,
                        hours_logged REAL DEFAULT 0,
                        avg_grading_turnaround_days REAL DEFAULT 0,
                        submissions_graded INTEGER DEFAULT 0,
                        feedback_score REAL,
                        evaluator_id TEXT,
                        evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except Exception as e:
            logger.error(f"Error creating ta_evaluations table: {e}")

    def _setup_ui(self):
        """Build the evaluation tab UI."""
        ttk.Label(
            self.parent, text="TA Performance Evaluation",
            font=('Arial', 12, 'bold')
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Buttons
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_evaluations).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Calculate Metrics", command=self._calculate_metrics).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ('ta_id', 'module_code', 'avg_turnaround', 'hours_allocated',
                'hours_logged', 'submissions_graded', 'feedback_score')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        self.tree.heading('ta_id', text='TA ID')
        self.tree.heading('module_code', text='Module')
        self.tree.heading('avg_turnaround', text='Avg Turnaround (days)')
        self.tree.heading('hours_allocated', text='Hours Allocated')
        self.tree.heading('hours_logged', text='Hours Logged')
        self.tree.heading('submissions_graded', text='Submissions Graded')
        self.tree.heading('feedback_score', text='Feedback Score')
        self.tree.column('ta_id', width=100)
        self.tree.column('module_code', width=100)
        self.tree.column('avg_turnaround', width=140)
        self.tree.column('hours_allocated', width=110)
        self.tree.column('hours_logged', width=100)
        self.tree.column('submissions_graded', width=130)
        self.tree.column('feedback_score', width=110)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.parent, textvariable=self.status_var).pack(anchor="w", padx=10, pady=5)

    def _load_evaluations(self):
        """Load TA evaluation data."""
        self.tree.delete(*self.tree.get_children())
        try:
            with get_connection() as conn:
                # Get TAs for instructor's courses with their allocated hours
                rows = conn.execute(
                    "SELECT ta.student_id as ta_id, ta.module_code, ta.hours_per_week, "
                    "ev.avg_grading_turnaround_days, ev.hours_logged, "
                    "ev.submissions_graded, ev.feedback_score "
                    "FROM teaching_assistants ta "
                    "LEFT JOIN ta_evaluations ev ON ta.student_id = ev.ta_id "
                    "  AND ta.module_code = ev.module_code "
                    "WHERE ta.instructor_id = ? AND ta.status = 'active' "
                    "ORDER BY ta.module_code, ta.student_id",
                    (self.instructor_id,)
                ).fetchall()

                for r in (rows or []):
                    turnaround = r['avg_grading_turnaround_days']
                    hours_logged = r['hours_logged']
                    graded = r['submissions_graded']
                    feedback = r['feedback_score']
                    self.tree.insert('', tk.END, values=(
                        r['ta_id'],
                        r['module_code'],
                        f"{turnaround:.1f}" if turnaround is not None else "N/A",
                        r['hours_per_week'] or "N/A",
                        f"{hours_logged:.1f}" if hours_logged is not None else "N/A",
                        graded if graded is not None else "N/A",
                        f"{feedback:.1f}" if feedback is not None else "N/A",
                    ))

                self.status_var.set(f"{len(rows or [])} TAs loaded.")
        except Exception as e:
            logger.error(f"Error loading evaluations: {e}")
            self.status_var.set("Error loading evaluation data.")

    def _calculate_metrics(self):
        """Calculate grading turnaround and submission counts from DB data."""
        try:
            with get_connection() as conn:
                # Get TAs for instructor's courses
                tas = conn.execute(
                    "SELECT student_id, module_code FROM teaching_assistants "
                    "WHERE instructor_id = ? AND status = 'active'",
                    (self.instructor_id,)
                ).fetchall()

                if not tas:
                    self.status_var.set("No active TAs found.")
                    return

            calculated = 0
            with transaction() as conn:
                for ta in tas:
                    ta_id = ta['student_id']
                    mc = ta['module_code']

                    # Count submissions graded by this TA
                    graded_row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM assignment_submissions "
                        "WHERE graded_by = ? AND assignment_id IN "
                        "(SELECT id FROM assignments WHERE module_code = ?)",
                        (ta_id, mc)
                    ).fetchone()
                    graded_count = graded_row['cnt'] if graded_row else 0

                    # Average turnaround: graded_date - due_date
                    turn_row = conn.execute(
                        "SELECT AVG(julianday(sub.graded_date) - julianday(a.due_date)) as avg_days "
                        "FROM assignment_submissions sub "
                        "JOIN assignments a ON sub.assignment_id = a.id "
                        "WHERE sub.graded_by = ? AND a.module_code = ? "
                        "AND sub.graded_date IS NOT NULL AND a.due_date IS NOT NULL",
                        (ta_id, mc)
                    ).fetchone()
                    avg_turn = round(turn_row['avg_days'], 1) if turn_row and turn_row['avg_days'] is not None else 0

                    # Upsert evaluation record
                    existing = conn.execute(
                        "SELECT id FROM ta_evaluations WHERE ta_id = ? AND module_code = ?",
                        (ta_id, mc)
                    ).fetchone()

                    if existing:
                        conn.execute(
                            "UPDATE ta_evaluations SET avg_grading_turnaround_days = ?, "
                            "submissions_graded = ?, evaluator_id = ?, "
                            "evaluated_at = datetime('now') "
                            "WHERE ta_id = ? AND module_code = ?",
                            (avg_turn, graded_count, self.instructor_id, ta_id, mc)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO ta_evaluations "
                            "(ta_id, module_code, avg_grading_turnaround_days, "
                            "submissions_graded, evaluator_id) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (ta_id, mc, avg_turn, graded_count, self.instructor_id)
                        )
                    calculated += 1

            try:
                log_activity(
                    self.instructor_id, self.instructor_id, 'instructor',
                    'calculate_ta_metrics', 'ta_evaluation',
                    details=f"Calculated metrics for {calculated} TAs"
                )
            except Exception:
                pass

            self.status_var.set(f"Metrics calculated for {calculated} TAs.")
            self._load_evaluations()

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            messagebox.showerror(
                "Error", f"Failed to calculate metrics: {e}",
                parent=self.parent.winfo_toplevel()
            )
