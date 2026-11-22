
import tkinter as tk

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
)

from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.auth_encryption import AuthEncryptionMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.database import DatabaseMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.ui_framework import UIFrameworkMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.health_records import HealthRecordsMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.vaccinations import VaccinationsMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.appointments import AppointmentsMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.emergency_contacts import EmergencyContactsMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.medical_history import MedicalHistoryMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.reports import ReportsMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.audit_security import AuditSecurityMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.data_management import DataManagementMixin, IntegrationManagementMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.email_integration import EmailIntegrationMixin
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.accessibility import AccessibilityMixin


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
    IntegrationManagementMixin,
    EmailIntegrationMixin,
    AccessibilityMixin,
):
    #: Main window size (the GUI convention), clamped to the screen.
    WINDOW_SIZE = (1400, 900)
    WINDOW_MINSIZE = (1200, 800)

    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("health_portal.title"))
        window_sizing.install()
        window_sizing.center(self.root, *self.WINDOW_SIZE, minsize=self.WINDOW_MINSIZE)
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication - use provided auth system or centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()

        # Sensitive fields are sealed with the one managed key
        # (infrastructure/health/field_crypto); the window holds no key, and
        # the cryptography package is only loaded the first time a field is
        # sealed or opened (see ``cipher_suite``).

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

    @property
    def cipher_suite(self):
        """The field cipher, created on first use so opening the portal does
        not import ``cryptography``."""
        cipher = self.__dict__.get("_cipher_suite")
        if cipher is None:
            from education_system.systems.university.domains.health.infrastructure.health import (
                field_crypto,
            )
            cipher = self.__dict__["_cipher_suite"] = field_crypto.cipher()
        return cipher

    @cipher_suite.setter
    def cipher_suite(self, value):
        self.__dict__["_cipher_suite"] = value

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.main.dialogs.application_error', default="Application Error"), f"An error occurred: {str(e)}")


def launch_health_portal_gui(auth=None):
    """Launch Health Portal GUI for integration with university system.

    Pass the signed-in ``auth``; without one the session's shared auth is
    used, and the portal refuses to open when nobody is signed in."""
    root = tk.Tk()
    app = HealthPortalGUI(root, auth_system=auth or get_auth())
    app.run()


# Main execution
if __name__ == "__main__":
    launch_health_portal_gui()
