"""
StudentGradesPortal - Main class composing all mixin functionality.

Uses a tabbed notebook to present Dashboard, Grades, and Transcript views
for the currently authenticated student.
"""

from tkinter import ttk

from education_system.university_system.modules.domain.academics.gui.student_grades.common_imports import get_auth, get_student_id
from education_system.university_system.modules.domain.academics.gui.student_grades.dashboard import DashboardMixin
from education_system.university_system.modules.domain.academics.gui.student_grades.grades import GradesMixin, TranscriptMixin


class StudentGradesPortal(DashboardMixin, GradesMixin, TranscriptMixin):
    """Student-facing portal for viewing grades and transcripts."""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize student grades portal.

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance (uses get_auth() if None)
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.student_id = get_student_id(self.auth)
        self.setup_notebook()

    def setup_notebook(self):
        """Create the tabbed notebook with Dashboard, Grades, and Transcript tabs."""
        self.notebook = ttk.Notebook(self.parent_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Dashboard tab
        dash_frame = ttk.Frame(self.notebook)
        self.notebook.add(dash_frame, text='Dashboard')
        self.show_dashboard(dash_frame)

        # Grades tab
        grades_frame = ttk.Frame(self.notebook)
        self.notebook.add(grades_frame, text='My Grades')
        self.show_grades_table(grades_frame)

        # Transcript tab
        transcript_frame = ttk.Frame(self.notebook)
        self.notebook.add(transcript_frame, text='Transcript')
        self.show_transcript(transcript_frame)
