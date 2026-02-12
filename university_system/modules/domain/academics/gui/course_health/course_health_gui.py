"""Course Health Dashboard GUI (Feature 28)."""

import logging
import tkinter as tk
from tkinter import ttk

from university_system.modules.shared.services.dashboard.dashboard_service import DashboardService

logger = logging.getLogger(__name__)


class CourseHealthDashboardGUI:
    """Toplevel window displaying health metrics for instructor's courses."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        self.user_role = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')
            self.user_role = auth.current_user.get('role', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Course Health Dashboard")
        self.window.geometry("1200x800")
        self.window.transient(parent)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Build the course health dashboard UI."""
        ttk.Label(
            self.window, text="Course Health Dashboard",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Refresh button
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(top_frame, text="Refresh", command=self._load_data).pack(side=tk.RIGHT)

        # Summary cards frame
        self.cards_frame = ttk.LabelFrame(self.window, text="Course Overview", padding="10")
        self.cards_frame.pack(fill=tk.X, padx=15, pady=5)

        # Detail table
        detail_frame = ttk.LabelFrame(self.window, text="Detailed Metrics", padding="5")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('module_code', 'module_name', 'enrolled', 'capacity',
                'avg_grade', 'attendance', 'submission', 'at_risk')
        self.tree = ttk.Treeview(detail_frame, columns=cols, show='headings')
        self.tree.heading('module_code', text='Code')
        self.tree.heading('module_name', text='Course Name')
        self.tree.heading('enrolled', text='Enrolled')
        self.tree.heading('capacity', text='Capacity')
        self.tree.heading('avg_grade', text='Avg Grade')
        self.tree.heading('attendance', text='Attendance %')
        self.tree.heading('submission', text='Submission %')
        self.tree.heading('at_risk', text='At-Risk')
        self.tree.column('module_code', width=100)
        self.tree.column('module_name', width=250)
        self.tree.column('enrolled', width=80)
        self.tree.column('capacity', width=80)
        self.tree.column('avg_grade', width=90)
        self.tree.column('attendance', width=100)
        self.tree.column('submission', width=100)
        self.tree.column('at_risk', width=70)

        self.tree.tag_configure('warning', background='#fff3cd')
        self.tree.tag_configure('danger', background='#f8d7da')

        scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="Loading...")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor="w", padx=15, pady=5)

    def _load_data(self):
        """Load course health data from the service."""
        try:
            data = DashboardService.get_course_health_data(self.instructor_id, role=self.user_role)
        except Exception as e:
            logger.error(f"Error loading course health data: {e}")
            data = []

        # Clear and rebuild cards
        for w in self.cards_frame.winfo_children():
            w.destroy()

        if data:
            row_frame = ttk.Frame(self.cards_frame)
            row_frame.pack(fill=tk.X)
            for i in range(min(4, len(data))):
                row_frame.columnconfigure(i, weight=1)

            for idx, course in enumerate(data[:4]):
                card = ttk.Frame(row_frame, relief="groove", borderwidth=1)
                card.grid(row=0, column=idx, padx=5, pady=5, sticky="nsew")
                ttk.Label(card, text=course['module_code'],
                          font=('Arial', 11, 'bold')).pack(pady=(5, 2))
                ttk.Label(card, text=f"{course['enrolled']}/{course['capacity']} enrolled",
                          font=('Arial', 9)).pack()
                avg_g = course.get('avg_grade')
                ttk.Label(card, text=f"Avg: {avg_g if avg_g is not None else 'N/A'}",
                          font=('Arial', 9)).pack()
                att = course.get('attendance_rate')
                ttk.Label(card, text=f"Att: {att if att is not None else 'N/A'}%",
                          font=('Arial', 9)).pack(pady=(0, 5))

        # Populate detail tree
        self.tree.delete(*self.tree.get_children())
        for course in data:
            avg_g = course.get('avg_grade')
            att = course.get('attendance_rate')
            sub = course.get('submission_rate')
            at_risk = course.get('at_risk_count', 0)

            tags = ()
            if at_risk > 3:
                tags = ('danger',)
            elif at_risk > 0:
                tags = ('warning',)

            self.tree.insert('', tk.END, values=(
                course['module_code'],
                course['module_name'],
                course['enrolled'],
                course['capacity'],
                f"{avg_g}" if avg_g is not None else "N/A",
                f"{att}%" if att is not None else "N/A",
                f"{sub}%" if sub is not None else "N/A",
                at_risk,
            ), tags=tags)

        self.status_var.set(f"{len(data)} courses loaded.")
