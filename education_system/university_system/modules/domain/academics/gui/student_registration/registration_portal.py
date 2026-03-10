"""
Student Registration Portal

Main entry point that composes the browse and enrollment mixins
into a tabbed notebook interface.
"""

from .common_imports import *
from .browse_modules import BrowseModulesMixin
from .enrollment import EnrollmentMixin


class StudentRegistrationPortal(BrowseModulesMixin, EnrollmentMixin):
    """Portal for students to browse modules, enroll, and drop."""

    def __init__(self, parent_frame, auth_instance=None):
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.student_id = get_student_id(self.auth)
        self.setup_notebook()

    def setup_notebook(self):
        """Create the tabbed notebook with dashboard, browse, and enrollment tabs."""
        self.notebook = ttk.Notebook(self.parent_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Dashboard
        dash_frame = ttk.Frame(self.notebook)
        self.notebook.add(dash_frame, text='Registration Dashboard')
        self.show_registration_dashboard(dash_frame)

        # Browse Modules
        browse_frame = ttk.Frame(self.notebook)
        self.notebook.add(browse_frame, text='Available Modules')
        self.show_available_modules(browse_frame)

        # My Enrollment
        enroll_frame = ttk.Frame(self.notebook)
        self.notebook.add(enroll_frame, text='My Enrollment')
        self.show_my_enrollment(enroll_frame)
