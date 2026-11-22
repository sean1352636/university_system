"""Office Hours Management GUI - Coordinator.

Provides a tabbed Tkinter Toplevel window for managing instructor office
hours and student bookings. Delegates to InstructorManager and BookingManager
sub-components depending on the authenticated user's role.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.systems.university.domains.teaching.domain.office_hours.office_hours_service import (
    OfficeHoursService,
)

logger = logging.getLogger(__name__)


class OfficeHoursGUI:
    """Main coordinator for Office Hours Management GUI."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.service = OfficeHoursService()

        self.window = parent
        # When ``parent`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip
        # window-chrome. Same shape as Library/Student Records.
        if hasattr(self.window, "wm_title"):
            self.window.title(_t('gui.academics.office_hours.office_hours.windows.office_hours_management', default="Office Hours Management"))
            self.window.geometry("900x600")

        self._setup_ui()

    def _setup_ui(self):
        """Setup the main UI with notebook tabs."""
        # Title
        title = ttk.Label(
            self.window,
            text=_t('gui.academics.office_hours.office_hours.labels.office_hours_management', default="Office Hours Management"),
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
        from education_system.systems.university.domains.teaching.interfaces.gui.office_hours.booking_manager import (
            BookingManager,
        )

        if role in ('admin', 'instructor', 'staff'):
            from education_system.systems.university.domains.teaching.interfaces.gui.office_hours.instructor_manager import (
                InstructorManager,
            )
            instructor_frame = ttk.Frame(self.notebook)
            self.notebook.add(instructor_frame, text=_t('gui.academics.office_hours.office_hours.tabs.manage_office_hours', default="Manage Office Hours"))
            self.instructor_manager = InstructorManager(
                instructor_frame, self.service, self.auth,
            )

        if role in ('admin', 'staff'):
            reports_frame = ttk.Frame(self.notebook)
            self.notebook.add(reports_frame, text="Reports")
            self._build_reports(reports_frame)

        # Booking tab for students (and admin)
        booking_frame = ttk.Frame(self.notebook)
        self.notebook.add(booking_frame, text=_t('gui.academics.office_hours.office_hours.tabs.book_appointments', default="Book Appointments"))
        self.booking_manager = BookingManager(
            booking_frame, self.service, self.auth,
        )

    def _build_reports(self, frame):
        """Demand, how full sessions are and no-shows, by member of staff."""
        from datetime import date, timedelta

        from education_system.systems.university.application.teaching import office_hours as rules
        from education_system.systems.university.domains.teaching.interfaces.gui.office_hours._rules_ui import (  # noqa: E501
            PAD, call, fill, tree,
        )
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, **PAD)
        since = tk.StringVar(value=(date.today() - timedelta(days=90)).isoformat())
        until = tk.StringVar(value=date.today().isoformat())
        for label, var in (("From", since), ("To", until)):
            ttk.Label(bar, text=label).pack(side=tk.LEFT)
            ttk.Entry(bar, textvariable=var, width=11).pack(side=tk.LEFT, padx=4)
        view = tree(frame, [("who", "Staff"), ("offered", "Places offered"), ("booked", "Booked"),
                            ("fill", "% full"), ("attended", "Attended"), ("no_show", "No-shows"),
                            ("ns", "No-show %"), ("cancelled", "Cancelled"),
                            ("modules", "Bookings by module")],
                    [100, 100, 70, 60, 70, 70, 80, 80, 260], height=14)

        def load():
            rows = call(rules.report, since.get(), until.get(), parent=frame) or []
            fill(view, rows, lambda r: (
                r["instructor"], r["offered"], r["booked"],
                "—" if r["fill_pct"] is None else f"{r['fill_pct']}%", r["attended"], r["no_show"],
                "—" if r["no_show_pct"] is None else f"{r['no_show_pct']}%", r["cancelled"],
                ", ".join(f"{m} {n}" for m, n in r["modules"].items())), lambda r: r["instructor"])
        ttk.Button(bar, text="Show", command=load).pack(side=tk.LEFT)
        load()
