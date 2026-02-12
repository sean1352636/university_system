"""Degree Progress Tracker GUI (Feature 35).

Displays a visual progress bar, summary statistics, and a colour-coded
requirements checklist for the currently logged-in student.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.simple_activity_logger import log_activity
from university_system.modules.shared.services.dashboard.student_services import StudentDashboardService

logger = logging.getLogger(__name__)


class DegreeProgressGUI:
    """Toplevel window showing degree progress for a student."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Degree Progress Tracker")
        self.window.geometry("900x650")
        self.window.transient(parent)

        self._setup_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the degree progress layout."""
        ttk.Label(
            self.window,
            text="Degree Progress Tracker",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # ---- Progress bar section ----
        progress_frame = ttk.Frame(self.window)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            length=600,
            mode='determinate',
            variable=self.progress_var,
            maximum=100,
        )
        self.progress_bar.pack(fill=tk.X)

        self.progress_label_var = tk.StringVar(value="0% Complete")
        ttk.Label(
            progress_frame,
            textvariable=self.progress_label_var,
            font=('Arial', 11),
        ).pack(pady=(3, 0))

        # ---- Stat cards row ----
        cards_frame = ttk.Frame(self.window)
        cards_frame.pack(fill=tk.X, padx=20, pady=5)

        self.credits_var = tk.StringVar(value="Credits: --/--")
        self.gpa_var = tk.StringVar(value="GPA: --")
        self.grad_var = tk.StringVar(value="Est. Graduation: --")

        self._create_stat_card(cards_frame, self.credits_var, 0)
        self._create_stat_card(cards_frame, self.gpa_var, 1)
        self._create_stat_card(cards_frame, self.grad_var, 2)

        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.columnconfigure(2, weight=1)

        # ---- Requirements checklist ----
        req_frame = ttk.LabelFrame(self.window, text="Requirements Checklist", padding="5")
        req_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 10))

        cols = (
            'requirement_name', 'type', 'status',
            'credits_needed', 'credits_completed',
        )
        self.tree = ttk.Treeview(req_frame, columns=cols, show='headings', height=14)
        self.tree.heading('requirement_name', text='Requirement')
        self.tree.heading('type', text='Type')
        self.tree.heading('status', text='Status')
        self.tree.heading('credits_needed', text='Credits Needed')
        self.tree.heading('credits_completed', text='Credits Completed')

        self.tree.column('requirement_name', width=250)
        self.tree.column('type', width=120, anchor='center')
        self.tree.column('status', width=120, anchor='center')
        self.tree.column('credits_needed', width=120, anchor='center')
        self.tree.column('credits_completed', width=140, anchor='center')

        # Color tags for status
        self.tree.tag_configure('completed', background='#d4edda')      # green
        self.tree.tag_configure('in_progress', background='#fff3cd')    # yellow
        self.tree.tag_configure('not_started', background='#e2e3e5')    # gray

        tree_scroll = ttk.Scrollbar(req_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_var = tk.StringVar(value="Loading...")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor='w', padx=20, pady=(0, 5))

    def _create_stat_card(self, parent, text_var, column):
        """Create a small stat card widget inside a grid."""
        card = ttk.LabelFrame(parent, text="", padding="10")
        card.grid(row=0, column=column, padx=10, pady=5, sticky='nsew')
        ttk.Label(card, textvariable=text_var, font=('Arial', 12, 'bold')).pack()

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        """Load degree progress from database / service."""
        if not self.student_id:
            self.status_var.set("No student logged in.")
            return

        try:
            # Try requirement_completion table first
            requirements = self._load_requirements_from_db()

            # Get summary from service (covers credits, GPA, progress_pct)
            summary = StudentDashboardService.get_degree_progress_summary(self.student_id)

            # Populate progress bar
            pct = summary.get('progress_pct', 0.0)
            self.progress_var.set(pct)
            self.progress_label_var.set(f"{pct}% Complete")

            # Populate stat cards
            earned = summary.get('credits_earned', 0)
            required = summary.get('credits_required', 120)
            self.credits_var.set(f"Credits: {earned}/{required}")

            gpa = summary.get('gpa')
            self.gpa_var.set(f"GPA: {gpa:.2f}" if gpa is not None else "GPA: N/A")

            grad = summary.get('estimated_graduation')
            self.grad_var.set(f"Est. Graduation: {grad}" if grad else "Est. Graduation: --")

            # Populate requirements tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Fall back to service data if no direct DB rows
            if not requirements:
                requirements = summary.get('requirements', [])

            for req in requirements:
                name = req.get('requirement_name', '')
                rtype = req.get('requirement_type', req.get('type', ''))
                status = req.get('status', 'not_started')
                needed = req.get('credits_needed', '')
                completed = req.get('credits_completed', '')

                tag = self._status_tag(status)
                self.tree.insert('', tk.END, values=(
                    name, rtype, status, needed, completed,
                ), tags=(tag,))

            count = len(requirements)
            if count == 0 and pct == 0.0 and gpa is None:
                self.status_var.set(
                    "No degree progress data found. "
                    "Your degree progress may not yet be configured."
                )
            else:
                self.status_var.set(f"Loaded {count} requirement(s).")

        except Exception as e:
            logger.error(f"Error loading degree progress: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror(
                "Error", f"Failed to load degree progress: {e}", parent=self.window
            )

    def _load_requirements_from_db(self):
        """Attempt to load requirement_completion rows directly.

        Joins with degree_requirements to get human-readable names.
        Also tries a numeric student_id since student_degree_progress
        may store '5' instead of 'S12345'.
        """
        requirements = []
        try:
            numeric_id = ''.join(c for c in self.student_id if c.isdigit())
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT dr.requirement_name, dr.requirement_type, "
                    "rc.is_completed, dr.credits_required AS credits_needed, "
                    "rc.credits_earned AS credits_completed "
                    "FROM requirement_completion rc "
                    "JOIN degree_requirements dr ON rc.requirement_id = dr.requirement_id "
                    "WHERE rc.student_id = ? OR rc.student_id = ? "
                    "ORDER BY dr.requirement_type, dr.requirement_name",
                    (self.student_id, numeric_id),
                ).fetchall()
                if rows:
                    for r in rows:
                        req_dict = dict(r)
                        req_dict['status'] = (
                            'completed' if req_dict.get('is_completed')
                            else 'in_progress'
                        )
                        requirements.append(req_dict)
        except Exception:
            # Table may not exist; that is fine, we fall back to the service.
            pass
        return requirements

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_tag(status):
        """Map a status string to a treeview tag name."""
        status_lower = (status or '').lower().replace(' ', '_')
        if status_lower in ('completed', 'complete'):
            return 'completed'
        elif status_lower in ('in_progress', 'in progress', 'enrolled'):
            return 'in_progress'
        return 'not_started'
