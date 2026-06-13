"""
Legal Services GUI

Comprehensive GUI for university legal aid center providing case management,
consultations, document management, billing, and reporting with full
email and finance integration.
"""

from education_system.university_system.modules.domain.operations.legal.gui._imports import (
    tk, ttk, messagebox, traceback,
    get_connection,
    init_legal_services_db,
    log_activity,
    _t, logger,
)
from education_system.university_system.modules.domain.operations.legal.gui.case_management import CaseManagementMixin
from education_system.university_system.modules.domain.operations.legal.gui.consultations import ConsultationsMixin
from education_system.university_system.modules.domain.operations.legal.gui.documents import DocumentsMixin
from education_system.university_system.modules.domain.operations.legal.gui.billing import BillingMixin
from education_system.university_system.modules.domain.operations.legal.gui.reports import ReportsMixin
from education_system.university_system.modules.domain.operations.legal.gui.refunds import RefundsMixin


class LegalServicesGUI(
    CaseManagementMixin,
    ConsultationsMixin,
    DocumentsMixin,
    BillingMixin,
    ReportsMixin,
    RefundsMixin,
):
    """Main Legal Services Platform GUI with full case management, consultations,
    documents, billing, reports, and refunds."""

    def __init__(self, root, auth):
        """Initialize the Legal Services GUI"""
        self.root = root
        self.auth = auth

        # Authentication check
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("legal.errors.login_required", default="You must be logged in to access Legal Services")
            )
            return

        self.current_user = auth.current_user
        self.user_role = self.current_user.get('role', 'student')

        # Use passed window. ``root`` may be a Toplevel (legacy launcher
        # path) or a workspace tab Frame (``open_in_workspace``); Frames
        # have no ``wm_title`` so skip the window-chrome calls.
        self.window = root
        if hasattr(self.window, "wm_title"):
            self.window.title(_t("legal.window_title", default="Legal Services Center"))
            self.window.geometry("1200x800")
            self.window.minsize(1000, 650)

        # Initialize data storage
        self.cases_data = []
        self.consultations_data = []
        self.documents_data = []
        self.selected_case = None
        self.selected_consultation = None

        # Admin email for reports
        self.admin_email = "admin@university.edu"

        # Initialize database
        self._init_database()

        # Create UI
        self.create_widgets()

        # Log access
        log_activity('Accessed Legal Services GUI', user=self.current_user.get('username'))
        print("Legal Services GUI opened successfully")

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title bar
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            title_frame,
            text=_t("legal.title", default="University Legal Aid Center"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        ttk.Label(
            title_frame,
            text=_t("legal.user_role_display", default="User: {username} | Role: {role}").format(
                username=self.current_user.get('username'), role=self.user_role
            ),
            font=('Arial', 10)
        ).pack(side=tk.RIGHT)

        # Bottom button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text=_t("common.return_to_main_menu", default="Return to Homescreen"),
            command=self.return_to_homescreen
        ).pack(side=tk.LEFT, pady=5)

        ttk.Button(
            button_frame,
            text=_t("common.refresh", default="Refresh All Data"),
            command=self.refresh_all_data
        ).pack(side=tk.RIGHT, pady=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create all tabs
        self.create_case_management_tab()
        self.create_consultations_tab()
        self.create_documents_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

    def _init_database(self):
        """Initialize database tables for legal services"""
        try:
            result = init_legal_services_db()
            if not result:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.db_init", default="Database initialization had issues")
                )
        except Exception as e:
            print(f"Warning: Database initialization error: {e}")
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.warnings.db_init_error", default="Database initialization error: {error}").format(error=str(e))
            )

    def _get_user_details_from_db(self):
        """Fetch user name and email from the users table"""
        try:
            user_id = self.current_user.get('id')
            username = self.current_user.get('username')
            with get_connection() as conn:
                cursor = conn.execute(
                    """SELECT first_name, last_name, email
                       FROM users WHERE id = ? OR username = ?""",
                    (user_id, username)
                )
                row = cursor.fetchone()
            if row:
                first_name = row[0] or ''
                last_name = row[1] or ''
                email = row[2] or ''
                full_name = f"{first_name} {last_name}".strip() or username or 'Unknown'
                return full_name, email
            else:
                return username or 'Unknown', ''
        except Exception as e:
            logger.error(f"Error fetching user details: {e}")
            return self.current_user.get('username', 'Unknown'), ''

    def return_to_homescreen(self):
        """Close the window and return to homescreen"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        try:
            self.load_cases()
            self.load_consultations()
            messagebox.showinfo(
                _t("common.success", default="Success"),
                _t("legal.messages.data_refreshed", default="All data refreshed successfully")
            )
        except Exception as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("legal.errors.refresh_failed", default="Failed to refresh data: {error}").format(error=str(e))
            )


def launch_legal_services_gui(root, auth):
    """Launch the Legal Services GUI"""
    try:
        LegalServicesGUI(root, auth)
    except Exception as e:
        messagebox.showerror(
            _t("common.error", default="Error"),
            _t("legal.errors.launch_failed", default="Failed to launch Legal Services GUI: {error}").format(error=str(e))
        )
        print(f"Legal Services GUI error: {traceback.format_exc()}")


__all__ = ['LegalServicesGUI', 'launch_legal_services_gui']
