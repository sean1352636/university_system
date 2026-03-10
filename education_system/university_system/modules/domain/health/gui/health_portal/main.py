import tkinter as tk
from tkinter import messagebox
from cryptography.fernet import Fernet

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
)

from .auth_encryption import AuthEncryptionMixin
from .database import DatabaseMixin
from .ui_framework import UIFrameworkMixin
from .health_records import HealthRecordsMixin
from .vaccinations import VaccinationsMixin
from .appointments import AppointmentsMixin
from .emergency_contacts import EmergencyContactsMixin
from .medical_history import MedicalHistoryMixin
from .reports import ReportsMixin
from .audit_security import AuditSecurityMixin
from .data_management import DataManagementMixin
from .email_integration import EmailIntegrationMixin
from .accessibility import AccessibilityMixin


class HealthPortalGUI(
    AuthEncryptionMixin,
    DatabaseMixin,
    UIFrameworkMixin,
    HealthRecordsMixin,
    VaccinationsMixin,
    AppointmentsMixin,
    EmergencyContactsMixin,
    MedicalHistoryMixin,
    ReportsMixin,
    AuditSecurityMixin,
    DataManagementMixin,
    EmailIntegrationMixin,
    AccessibilityMixin,
):
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("health_portal.title"))
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication - use provided auth system or centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()

        # Initialize encryption
        self.encryption_key = self.get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

        # Setup logging
        self.setup_logging()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Check authentication status - require login through main system
        from education_system.university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if not auth.current_user:
            messagebox.showerror(_t("health_portal.messages.auth_required"),
                _t("health_portal.messages.auth_required_detail"))
            self.root.destroy()
            return

        # Show main interface
        self.create_main_interface()

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Application Error", f"An error occurred: {str(e)}")


def launch_health_portal_gui(auth=None):
    """Launch Health Portal GUI for integration with university system"""
    root = tk.Tk()
    app = HealthPortalGUI(root, auth_system=auth)
    app.run()


# Main execution
if __name__ == "__main__":
    root = tk.Tk()
    app = HealthPortalGUI(root)
    app.run()
