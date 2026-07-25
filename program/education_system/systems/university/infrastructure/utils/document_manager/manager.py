"""
DocumentManager - Core class that composes all mixin functionality.

This was originally a single 6800-line file. It has been split into
feature-specific mixins, all composed here via multiple inheritance.
"""
import sys
import getpass

from education_system.systems.university.infrastructure.utils.document_manager._common import (
    _t, get_current_user, get_auth,
    EMAIL_SYSTEM_AVAILABLE,
)

# Import all mixins
from education_system.systems.university.infrastructure.utils.document_manager.database import DatabaseMixin
from education_system.systems.university.infrastructure.utils.document_manager.upload import UploadMixin
from education_system.systems.university.infrastructure.utils.document_manager.status import StatusMixin
from education_system.systems.university.infrastructure.utils.document_manager.search import SearchMixin
from education_system.systems.university.infrastructure.utils.document_manager.dashboard import DashboardMixin
from education_system.systems.university.infrastructure.utils.document_manager.bulk_operations import BulkOperationsMixin
from education_system.systems.university.infrastructure.utils.document_manager.reports import ReportsMixin
from education_system.systems.university.infrastructure.utils.document_manager.notifications import NotificationsMixin
from education_system.systems.university.infrastructure.utils.document_manager.versioning import VersioningMixin
from education_system.systems.university.infrastructure.utils.document_manager.workflows import WorkflowMixin
from education_system.systems.university.infrastructure.utils.document_manager.document_types import DocumentTypeMixin
from education_system.systems.university.infrastructure.utils.document_manager.import_export import ImportExportMixin
from education_system.systems.university.infrastructure.utils.document_manager.settings import SettingsMixin
from education_system.systems.university.infrastructure.utils.document_manager.backup import BackupMixin
from education_system.systems.university.infrastructure.utils.document_manager.ocr import OCRMixin
from education_system.systems.university.infrastructure.utils.document_manager.api_server import APIServerMixin
from education_system.systems.university.infrastructure.utils.document_manager.web_interface import WebInterfaceMixin
from education_system.systems.university.infrastructure.utils.document_manager.viewing import ViewingMixin
from education_system.systems.university.infrastructure.utils.document_manager.student_self_service import StudentSelfServiceMixin


class DocumentManager(
    DatabaseMixin,
    UploadMixin,
    StatusMixin,
    SearchMixin,
    DashboardMixin,
    BulkOperationsMixin,
    ReportsMixin,
    NotificationsMixin,
    VersioningMixin,
    WorkflowMixin,
    DocumentTypeMixin,
    ImportExportMixin,
    SettingsMixin,
    BackupMixin,
    OCRMixin,
    APIServerMixin,
    WebInterfaceMixin,
    ViewingMixin,
    StudentSelfServiceMixin,
):
    """Enhanced Document Management System with versioning, workflows, and notifications."""

    def __init__(self, auth=None):
        """Initialize DocumentManager"""
        self.auth = auth
        self.current_user = None
        self.user_role = None

        # Try to get current user from centralized auth
        try:
            current_user = get_current_user()
            if current_user:
                self.current_user = current_user.get('username', 'admin')
                self.user_role = current_user.get('role', 'admin')
        except Exception:
            self.current_user = 'admin'
            self.user_role = 'admin'

        # Initialize database
        self.init_enhanced_db()

    def check_authentication(self):
        """Verify user is authenticated"""
        try:
            current_user = get_current_user()
            if current_user:
                self.current_user = current_user.get('username', 'admin')
                self.user_role = current_user.get('role', 'admin')
                return True
        except Exception:
            pass

        return self.current_user is not None

    def display_main_menu(self):
        """Display the main menu based on user role"""
        if not self.check_authentication():
            print(_t("shared.utils.document_manager.auth_required", default="Authentication required. Please log in."))
            return

        while True:
            print(_t("shared.utils.document_manager.main_menu_header", default="\n📄 DOCUMENT MANAGEMENT SYSTEM"))
            print(f"Logged in as: {self.current_user} ({self.user_role})")

            if self.user_role in ('admin', 'staff', 'registrar'):
                self.display_admin_menu()
            else:
                self.display_student_menu()

    def display_admin_menu(self):
        """Display admin/staff menu"""
        print(_t("shared.utils.document_manager.admin_menu_header", default="\n--- ADMIN MENU ---"))
        print(_t("shared.utils.document_manager.menu_upload_doc", default="1. Upload Student Document"))
        print(_t("shared.utils.document_manager.menu_view_student_docs", default="2. View Student Documents"))
        print(_t("shared.utils.document_manager.menu_update_status", default="3. Update Document Status"))
        print(_t("shared.utils.document_manager.menu_check_expiry", default="4. Check Document Expiry"))
        print(_t("shared.utils.document_manager.menu_advanced_search", default="5. Advanced Search"))
        print(_t("shared.utils.document_manager.menu_dashboard", default="6. Dashboard"))
        print(_t("shared.utils.document_manager.menu_bulk_ops", default="7. Bulk Operations"))
        print(_t("shared.utils.document_manager.menu_reports", default="8. Reports"))
        print(_t("shared.utils.document_manager.menu_doc_templates", default="9. Document Templates"))
        print(_t("shared.utils.document_manager.menu_doc_versioning", default="10. Document Versioning"))
        print(_t("shared.utils.document_manager.menu_workflows", default="11. Workflow Management"))
        print(_t("shared.utils.document_manager.menu_notifications", default="12. Notification Center"))
        print(_t("shared.utils.document_manager.menu_import", default="13. Import Documents"))
        print(_t("shared.utils.document_manager.menu_export", default="14. Export Data"))
        print(_t("shared.utils.document_manager.menu_ocr", default="15. OCR Integration"))
        print(_t("shared.utils.document_manager.menu_api_server", default="16. API Server"))
        print(_t("shared.utils.document_manager.menu_web_interface", default="17. Web Interface"))
        print(_t("shared.utils.document_manager.menu_doc_types", default="18. Document Type Management"))
        print(_t("shared.utils.document_manager.menu_system_settings", default="19. System Settings"))
        print(_t("shared.utils.document_manager.menu_backup", default="20. Backup System"))
        print(_t("shared.utils.document_manager.menu_exit", default="21. Exit"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option", default="\nChoose option: ")).strip()
        self.handle_admin_choice(choice)

    def display_student_menu(self):
        """Display student self-service menu"""
        print(_t("shared.utils.document_manager.student_menu_header", default="\n--- STUDENT MENU ---"))
        print(_t("shared.utils.document_manager.menu_view_my_docs", default="1. View My Documents"))
        print(_t("shared.utils.document_manager.menu_upload_my_doc", default="2. Upload Document"))
        print(_t("shared.utils.document_manager.menu_my_dashboard", default="3. My Dashboard"))
        print(_t("shared.utils.document_manager.menu_check_requirements", default="4. Check Requirements"))
        print(_t("shared.utils.document_manager.menu_my_status", default="5. Document Status"))
        print(_t("shared.utils.document_manager.menu_my_notifications", default="6. My Notifications"))
        print(_t("shared.utils.document_manager.menu_exit", default="7. Exit"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option", default="\nChoose option: ")).strip()
        self.handle_student_choice(choice)

    def handle_admin_choice(self, choice):
        """Route admin menu selections"""
        if choice == '1':
            self.upload_student_document()
        elif choice == '2':
            self.view_student_documents()
        elif choice == '3':
            self.update_document_status()
        elif choice == '4':
            self.check_document_expiry()
        elif choice == '5':
            self.advanced_search()
        elif choice == '6':
            self.display_dashboard()
        elif choice == '7':
            self.bulk_operations_menu()
        elif choice == '8':
            self.generate_reports_menu()
        elif choice == '9':
            self.manage_document_templates()
        elif choice == '10':
            self.document_versioning_menu()
        elif choice == '11':
            self.workflow_management()
        elif choice == '12':
            self.notification_center()
        elif choice == '13':
            self.bulk_import_documents()
        elif choice == '14':
            self.export_data_menu()
        elif choice == '15':
            self.ocr_integration_menu()
        elif choice == '16':
            self.api_server_menu()
        elif choice == '17':
            self.web_interface_menu()
        elif choice == '18':
            self.document_type_management()
        elif choice == '19':
            self.system_settings()
        elif choice == '20':
            self.backup_system()
        elif choice == '21':
            print(_t("shared.utils.document_manager.goodbye", default="Goodbye!"))
            return
        else:
            print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))

    def handle_student_choice(self, choice):
        """Route student menu selections"""
        if choice == '1':
            self.view_my_documents()
        elif choice == '2':
            self.student_upload_document()
        elif choice == '3':
            self.student_dashboard()
        elif choice == '4':
            self.check_my_requirements()
        elif choice == '5':
            self.my_document_status()
        elif choice == '6':
            self.my_notifications()
        elif choice == '7':
            print(_t("shared.utils.document_manager.goodbye", default="Goodbye!"))
            return
        else:
            print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))


def display_document_management_menu():
    """Standalone function to start the document management system"""
    print("🚀 Starting Enhanced Document Management System...")

    # Initialize the system
    doc_manager = DocumentManager()

    try:
        # Start the main application loop
        doc_manager.display_main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 System shutdown requested. Goodbye!")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        print("Please contact system administrator.")


def main():
    from education_system.systems.university.infrastructure.auth import (
        UserAuth, set_auth_instance, get_current_user as _get_current_user
    )

    def ensure_login():
        cu = _get_current_user()
        if cu:
            return None  # already logged in

        auth = get_auth()
        if auth is None:
            auth = UserAuth()

        # Try common interactive auth entrypoints your UserAuth might have
        for method in ("run_authentication_menu", "login_console", "login_menu", "run_console_interface", "run"):
            if hasattr(auth, method):
                try:
                    getattr(auth, method)()
                except Exception:
                    pass
                if getattr(auth, "current_user", None):
                    set_auth_instance(auth)
                    return auth

        # Fallback: prompt + direct login()
        if hasattr(auth, "login"):
            username = input("Username: ").strip()
            password = getpass.getpass("Password: ")
            try:
                ok = auth.login(username, password)
            except TypeError:
                ok = auth.login(username, password)

            if ok and getattr(auth, "current_user", None):
                set_auth_instance(auth)
                return auth

        if not _get_current_user():
            print("❌ Login failed or not completed. The Document Manager requires an authenticated session.")
            sys.exit(1)

        set_auth_instance(auth)
        return auth

    # 1) Ensure login (populates global current_user used by DocumentManager.check_authentication)
    auth_instance = ensure_login()

    # 2) Start Document Manager
    dm = DocumentManager()

    # 3) Give email subsystem the auth context if available
    try:
        from education_system.systems.university.infrastructure.utils.document_manager._common import set_auth as _set_auth_context
        if auth_instance is not None:
            _set_auth_context(auth_instance)
    except (ImportError, NameError):
        if auth_instance is not None:
            dm.auth = auth_instance

    # 4) Run
    dm.display_main_menu()
