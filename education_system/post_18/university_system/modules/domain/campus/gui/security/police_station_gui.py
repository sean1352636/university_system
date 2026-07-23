"""
Campus Public Safety Management System
A comprehensive GUI application for university campus police and security operations.
Handles student incidents, campus emergencies, patrol logs, and safety complaints.
Integrated with university student records and email notifications.
Uses the central database for data persistence.
"""

import tkinter as tk
from tkinter import messagebox

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.campus.gui.security.utils import get_current_user
from education_system.post_18.university_system.modules.domain.campus.gui.security.database import DatabaseMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs import (
    BaseMixin, DashboardMixin, CasesMixin, OfficersMixin,
    ComplaintsMixin, PatrolLogsMixin, CriminalsMixin,
    EvidenceMixin, ReportsMixin,
)

# Re-export constants and helpers for backward compatibility
from education_system.post_18.university_system.modules.domain.campus.gui.security.constants import (  # noqa: F401
    CAMPUS_LOCATIONS, CAMPUS_INCIDENT_TYPES, CAMPUS_COMPLAINT_TYPES,
    CAMPUS_EMERGENCY_TYPES, CAMPUS_OFFICER_RANKS,
)
from education_system.post_18.university_system.modules.domain.campus.gui.security.database import POLICE_STATION_SCHEMA, init_police_database  # noqa: F401
from education_system.post_18.university_system.modules.domain.campus.gui.security.utils import send_notification_email, get_admin_emails, get_officer_email  # noqa: F401
from education_system.post_18.university_system.modules.domain.campus.gui.security.widgets import ScrollableFrame  # noqa: F401
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs import (  # noqa: F401
    CaseDetailsDialog, WitnessDialog, ComplaintFormDialog,
    EmergencyAlertDialog, PatrolLogDialog, ReportPreviewDialog,
    OfficerDialog, CriminalDialog, EvidenceDialog,
)


class PoliceStationApp(
    BaseMixin, DatabaseMixin, DashboardMixin, CasesMixin,
    OfficersMixin, ComplaintsMixin, PatrolLogsMixin,
    CriminalsMixin, EvidenceMixin, ReportsMixin,
):
    def __init__(self, root, current_user=None):
        self.root = root
        self.root.title(_t("police_station.title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self.root.configure(bg="#1a1a2e")

        # Get current user - require login
        self.current_user = current_user or get_current_user()

        if not self.current_user:
            messagebox.showerror(_t("police_station.access_denied"),
                               _t("police_station.login_required"))
            self.root.destroy()
            return

        # Data storage
        self.load_data()

        # Setup UI
        self.setup_styles()
        self.create_header()
        self.create_sidebar()
        self.create_main_content()

        # Show dashboard by default
        self.show_dashboard()


if __name__ == "__main__":
    root = tk.Tk()
    app = PoliceStationApp(root)
    root.mainloop()
