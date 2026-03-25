"""
Student Dashboard Portal

Unified home page that aggregates data from multiple backends into a single
scrollable dashboard view for students.
"""

import tkinter as tk
from tkinter import ttk

from education_system.university_system.modules.domain.academics.gui.student_dashboard.common_imports import get_auth, get_student_id, get_student_name
from education_system.university_system.modules.domain.academics.gui.student_dashboard.overview import OverviewMixin
from education_system.university_system.modules.domain.academics.gui.student_dashboard.quick_actions import QuickActionsMixin


class StudentDashboardPortal(OverviewMixin, QuickActionsMixin):
    def __init__(self, parent_frame, auth_instance=None, main_gui=None):
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.main_gui = main_gui  # Reference to UnifiedManagementGUI for navigation
        self.student_id = get_student_id(self.auth)
        self.student_name = get_student_name(self.auth)
        self.build_dashboard()

    def build_dashboard(self):
        """Build the main scrollable dashboard layout."""
        # Main scrollable frame
        canvas = tk.Canvas(self.parent_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent_frame, orient='vertical', command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.show_overview(self.scroll_frame)
        self.create_quick_actions(self.scroll_frame)
