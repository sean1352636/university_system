import tkinter as tk
from tkinter import messagebox
from cryptography.fernet import Fernet
from unittest.mock import Mock

from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
)

from education_system.post_18.university_system.modules.domain.health.gui.health_portal.auth_encryption import AuthEncryptionMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.auth_encryption import _FallbackCipher
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.database import DatabaseMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.ui_framework import UIFrameworkMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.health_records import HealthRecordsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.vaccinations import VaccinationsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.appointments import AppointmentsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.emergency_contacts import EmergencyContactsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.medical_history import MedicalHistoryMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.reports import ReportsMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.audit_security import AuditSecurityMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.data_management import DataManagementMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.email_integration import EmailIntegrationMixin
from education_system.post_18.university_system.modules.domain.health.gui.health_portal.accessibility import AccessibilityMixin


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
        from cryptography.fernet import Fernet as RealFernet

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
        try:
            cipher_suite = RealFernet(self.encryption_key)
            self.cipher_suite = _FallbackCipher() if isinstance(cipher_suite, Mock) else cipher_suite
        except Exception:
            self.cipher_suite = _FallbackCipher()

        # Setup logging
        self.setup_logging()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Check authentication status using the active auth object on the GUI.
        if not getattr(self.auth, 'current_user', None):
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
