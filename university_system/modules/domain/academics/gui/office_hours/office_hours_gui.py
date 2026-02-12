"""Office Hours Management GUI - Coordinator.

Provides a tabbed Tkinter Toplevel window for managing instructor office
hours and student bookings. Delegates to InstructorManager and BookingManager
sub-components depending on the authenticated user's role.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from university_system.modules.domain.academics.services.office_hours.office_hours_service import (
    OfficeHoursService,
)

logger = logging.getLogger(__name__)


class OfficeHoursGUI:
    """Main coordinator for Office Hours Management GUI."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.service = OfficeHoursService()

        self.window = tk.Toplevel(parent)
        self.window.title("Office Hours Management")
        self.window.geometry("900x600")
        self.window.transient(parent)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the main UI with notebook tabs."""
        # Title
        title = ttk.Label(
            self.window,
            text="Office Hours Management",
            font=('Arial', 16, 'bold'),
        )
        title.pack(pady=(10, 5))

        # Create notebook
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        role = ''
        if self.auth and self.auth.current_user:
            role = self.auth.current_user.get('role', '')

        # Import and create tab managers
        from university_system.modules.domain.academics.gui.office_hours.booking_manager import (
            BookingManager,
        )

        if role in ('admin', 'instructor', 'staff'):
            from university_system.modules.domain.academics.gui.office_hours.instructor_manager import (
                InstructorManager,
            )
            instructor_frame = ttk.Frame(self.notebook)
            self.notebook.add(instructor_frame, text="Manage Office Hours")
            self.instructor_manager = InstructorManager(
                instructor_frame, self.service, self.auth,
            )

        # Booking tab for students (and admin)
        booking_frame = ttk.Frame(self.notebook)
        self.notebook.add(booking_frame, text="Book Appointments")
        self.booking_manager = BookingManager(
            booking_frame, self.service, self.auth,
        )
