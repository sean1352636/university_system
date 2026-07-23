"""Comparative Semester Analytics GUI (Feature 29)."""

import logging
import tkinter as tk
from tkinter import ttk

from education_system.post_18.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService

logger = logging.getLogger(__name__)


class SemesterAnalyticsGUI:
    """Toplevel window for comparing metrics across semesters."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Semester Analytics")
        self.window.geometry("1100x800")
        self.window.transient(parent)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Build the semester analytics UI."""
        ttk.Label(
            self.window, text="Comparative Semester Analytics",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Refresh
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(top_frame, text="Refresh", command=self._load_data).pack(side=tk.RIGHT)

        # Side-by-side comparison
        self.comparison_frame = ttk.Frame(self.window)
        self.comparison_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self.comparison_frame.columnconfigure(0, weight=1)
        self.comparison_frame.columnconfigure(1, weight=1)

        # Metrics table
        metrics_frame = ttk.LabelFrame(self.window, text="Metrics Comparison", padding="10")
        metrics_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('metric', 'current', 'previous', 'change')
        self.tree = ttk.Treeview(metrics_frame, columns=cols, show='headings', height=6)
        self.tree.heading('metric', text='Metric')
        self.tree.heading('current', text='Current Semester')
        self.tree.heading('previous', text='Previous Semester')
        self.tree.heading('change', text='Change')
        self.tree.column('metric', width=200)
        self.tree.column('current', width=200)
        self.tree.column('previous', width=200)
        self.tree.column('change', width=200)

        self.tree.tag_configure('positive', foreground='#155724')
        self.tree.tag_configure('negative', foreground='#721c24')
        self.tree.tag_configure('neutral', foreground='#383d41')

        self.tree.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Loading...")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor="w", padx=15, pady=5)

    def _load_data(self):
        """Load semester comparison data."""
        try:
            data = DashboardService.get_semester_comparison_data(self.instructor_id)
        except Exception as e:
            logger.error(f"Error loading semester data: {e}")
            data = {'current': {}, 'previous': {},
                    'current_label': 'Current', 'previous_label': 'Previous'}

        current = data.get('current', {})
        previous = data.get('previous', {})
        curr_label = data.get('current_label', 'Current')
        prev_label = data.get('previous_label', 'Previous')

        # Build side-by-side cards
        for w in self.comparison_frame.winfo_children():
            w.destroy()

        # Current semester card
        curr_card = ttk.LabelFrame(self.comparison_frame, text=curr_label, padding="15")
        curr_card.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        self._build_semester_card(curr_card, current)

        # Previous semester card
        prev_card = ttk.LabelFrame(self.comparison_frame, text=prev_label, padding="15")
        prev_card.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        self._build_semester_card(prev_card, previous)

        # Update comparison tree
        self.tree.delete(*self.tree.get_children())
        self.tree.heading('current', text=curr_label)
        self.tree.heading('previous', text=prev_label)

        metrics = [
            ('Enrollment Count', 'enrollment_count', '{:,}'),
            ('Average Grade', 'avg_grade', '{:.1f}'),
            ('Attendance Rate (%)', 'attendance_rate', '{:.1f}%'),
            ('Submission Rate (%)', 'submission_rate', '{:.1f}%'),
        ]

        for label, key, fmt in metrics:
            curr_val = current.get(key)
            prev_val = previous.get(key)

            curr_str = fmt.format(curr_val) if curr_val is not None else "N/A"
            prev_str = fmt.format(prev_val) if prev_val is not None else "N/A"

            # Calculate change
            change_str = "N/A"
            tag = 'neutral'
            if curr_val is not None and prev_val is not None and prev_val != 0:
                diff = curr_val - prev_val
                pct_change = (diff / prev_val) * 100
                if diff > 0:
                    change_str = f"+{pct_change:.1f}%"
                    tag = 'positive'
                elif diff < 0:
                    change_str = f"{pct_change:.1f}%"
                    tag = 'negative'
                else:
                    change_str = "0%"

            self.tree.insert('', tk.END, values=(
                label, curr_str, prev_str, change_str
            ), tags=(tag,))

        self.status_var.set(f"Comparing {curr_label} vs {prev_label}")

    def _build_semester_card(self, parent, data):
        """Build a summary card for one semester."""
        metrics = [
            ('Enrollment', data.get('enrollment_count', 0)),
            ('Avg Grade', data.get('avg_grade', 'N/A')),
            ('Attendance', f"{data.get('attendance_rate', 'N/A')}%" if data.get('attendance_rate') is not None else 'N/A'),
            ('Submissions', f"{data.get('submission_rate', 'N/A')}%" if data.get('submission_rate') is not None else 'N/A'),
        ]
        for label, value in metrics:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=f"{label}:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row, text=str(value), font=('Arial', 10)).pack(side=tk.RIGHT)
