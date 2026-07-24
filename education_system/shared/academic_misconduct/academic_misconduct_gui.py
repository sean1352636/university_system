#!/usr/bin/env python3
"""
Academic Misconduct Panel - Case Management System
A professional GUI application for managing academic integrity cases.
"""

from education_system.shared.academic_misconduct._imports import (
    tk, messagebox, _t,
    AUTH_AVAILABLE, get_auth, _DummyAuth,
)
from education_system.shared.academic_misconduct.database import MisconductDatabaseMixin, init_misconduct_tables
from education_system.shared.academic_misconduct.styles import MisconductStylesMixin
from education_system.shared.academic_misconduct.sidebar import MisconductSidebarMixin
from education_system.shared.academic_misconduct.dashboard import MisconductDashboardMixin
from education_system.shared.academic_misconduct.case_list import MisconductCaseListMixin
from education_system.shared.academic_misconduct.case_details import MisconductCaseDetailsMixin
from education_system.shared.academic_misconduct.case_overview import MisconductOverviewMixin
from education_system.shared.academic_misconduct.case_dialogs import MisconductCaseDialogsMixin
from education_system.shared.academic_misconduct.case_update import MisconductCaseUpdateMixin
from education_system.shared.academic_misconduct.student_lookup import MisconductStudentLookupMixin
from education_system.shared.academic_misconduct.evidence import MisconductEvidenceMixin
from education_system.shared.academic_misconduct.decisions import MisconductDecisionsMixin
from education_system.shared.academic_misconduct.hearings import MisconductHearingsMixin
from education_system.shared.academic_misconduct.notifications import MisconductNotificationsMixin
from education_system.shared.academic_misconduct.history import MisconductHistoryMixin
from education_system.shared.academic_misconduct.analytics import MisconductAnalyticsMixin
from education_system.shared.academic_misconduct.superadmin_dashboard import MisconductSuperAdminMixin

# Valid system keys
VALID_SYSTEM_KEYS = ('university', 'sixth_form', 'secondary', 'primary')

SYSTEM_DISPLAY_NAMES = {
    'university': 'University',
    'sixth_form': 'College',
    'secondary': 'Secondary School',
    'primary': 'Primary School',
}


class AcademicMisconductPanel(
    MisconductDatabaseMixin,
    MisconductStylesMixin,
    MisconductSidebarMixin,
    MisconductDashboardMixin,
    MisconductCaseListMixin,
    MisconductCaseDetailsMixin,
    MisconductOverviewMixin,
    MisconductCaseDialogsMixin,
    MisconductCaseUpdateMixin,
    MisconductStudentLookupMixin,
    MisconductEvidenceMixin,
    MisconductDecisionsMixin,
    MisconductHearingsMixin,
    MisconductNotificationsMixin,
    MisconductHistoryMixin,
    MisconductAnalyticsMixin,
    MisconductSuperAdminMixin,
):
    """Main application class for the Academic Misconduct Panel."""

    def __init__(self, root, auth=None, system_key=None):
        self.root = root

        # System key determines which system's cases to show
        # None or 'all' means superadmin view (all systems)
        self.system_key = system_key if system_key in VALID_SYSTEM_KEYS else None
        self.is_superadmin = self.system_key is None

        # Authentication setup
        self.auth = auth
        self.current_user = None

        # Try to get auth from shared context if not provided
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check if user is logged in
        if not self._check_authentication():
            return

        # Build window title with system name
        if self.system_key:
            system_name = SYSTEM_DISPLAY_NAMES.get(self.system_key, self.system_key.title())
            title = f"Academic Misconduct Panel - {system_name}"
        else:
            title = "Academic Misconduct Panel - All Systems (Super Admin)"
        self.root.title(title)
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Color scheme - Matches standard program theme
        self.colors = {
            'primary': '#2c3e50',      # Dark blue-gray
            'secondary': '#3498db',     # Blue
            'success': '#27ae60',       # Green
            'warning': '#f39c12',       # Orange
            'danger': '#e74c3c',        # Red
            'light': '#ecf0f1',         # Light gray
            'dark': '#34495e',          # Dark gray
            'info': '#17a2b8',          # Cyan
            'white': '#ffffff',         # White
            'border': '#bdc3c7',        # Gray border
            'text_dark': '#2c3e50',     # Dark text
            'text_muted': '#7f8c8d',    # Muted text
            'bg_header': '#2c3e50',     # Header background
            'bg_sidebar': '#34495e',    # Sidebar background
            'accent': '#3498db',        # Accent color
        }

        self.root.configure(bg=self.colors['light'])

        # Initialize database tables
        init_misconduct_tables()

        # Load cases from database
        self.cases = []
        self.load_cases_from_db()

        self.selected_case = None
        self.setup_styles()
        self.create_widgets()

        # Honor optional prefill hints set by the launcher (e.g. the
        # Disciplinary Portal sets prefill_case_id on the Toplevel
        # before calling this constructor). The actual navigation is
        # encapsulated in goto_case / goto_student_cases so callers
        # don't depend on internal tab/tree wiring.
        prefill_case_id = getattr(self.root, 'prefill_case_id', None)
        prefill_student_id = getattr(self.root, 'prefill_student_id', None)
        if prefill_case_id:
            self.goto_case(prefill_case_id)
        elif prefill_student_id:
            self.goto_student_cases(prefill_student_id)

    # ------------------------------------------------------------------
    # Public navigation API. External callers (e.g. the Disciplinary
    # Portal) drive the panel through these instead of poking at tabs,
    # search vars and treeviews directly. Refactors of the case-list
    # / overview internals only need to update these two methods.
    # ------------------------------------------------------------------

    def goto_case(self, case_id):
        """Navigate to the Cases view and select the given case.

        Returns True on success, False if the case isn't loaded.
        """
        if not case_id:
            return False
        target = next((c for c in self.cases
                       if c.get('id') == case_id), None)
        if target is None:
            return False
        self._show_cases_view()
        self.selected_case = target
        # Narrow the case list to this one row, then select+see it.
        if hasattr(self, 'search_var'):
            try:
                self.search_var.set(case_id)
            except Exception:
                pass
        if hasattr(self, 'populate_tree'):
            try:
                self.populate_tree()
            except Exception:
                pass
        if hasattr(self, 'tree'):
            try:
                for item in self.tree.get_children():
                    vals = self.tree.item(item, 'values')
                    if vals and vals[0] == case_id:
                        self.tree.selection_set(item)
                        self.tree.see(item)
                        break
            except Exception:
                pass
        # Render the overview section against the newly-set case.
        if hasattr(self, 'show_overview_section'):
            try:
                self.show_overview_section()
            except Exception:
                pass
        if hasattr(self, 'create_overview_fields'):
            try:
                self.create_overview_fields()
            except Exception:
                pass
        return True

    def goto_student_cases(self, student_id):
        """Navigate to the Cases view, filtered to one student.

        No specific case is selected — useful when the caller knows
        a student_id but not which (if any) case to focus on.
        """
        if not student_id:
            return
        self._show_cases_view()
        if hasattr(self, 'search_var'):
            try:
                self.search_var.set(str(student_id))
            except Exception:
                pass
        if hasattr(self, 'populate_tree'):
            try:
                self.populate_tree()
            except Exception:
                pass

    def _show_cases_view(self):
        if hasattr(self, 'show_view'):
            try:
                self.show_view('cases')
            except Exception:
                pass

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("misconduct.auth.required_title", "Authentication Required"),
                _t("misconduct.auth.required_message", "You must be logged in to access the Academic Misconduct Panel.\n\nPlease log in through the main GUI first.")
            )
            self.root.destroy()
            return False

        # Don't gate on the auth type — gate on whether a real user is
        # bound. The original ``isinstance(self.auth, _DummyAuth)``
        # check was redundant (the dummy class has no current_user, so
        # the next check rejects it anyway) and was fragile when
        # callers passed valid non-UserAuth shims (e.g. the env-bridge
        # SimpleNamespace from the Disciplinary Portal subprocess).
        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("misconduct.auth.not_logged_in_title", "Not Logged In"),
                _t("misconduct.auth.not_logged_in_message", "You are not currently logged in.\n\nPlease log in through the main GUI to access this panel.")
            )
            self.root.destroy()
            return False

        # Store current user info
        self.current_user = self.auth.current_user

        # Check if user has appropriate role (admin, staff, or instructor)
        user_role = self.current_user.get('role', '').lower()
        allowed_roles = ['admin', 'staff', 'instructor', 'administrator']

        if user_role not in allowed_roles:
            messagebox.showerror(
                _t("misconduct.auth.access_denied_title", "Access Denied"),
                _t("misconduct.auth.access_denied_message", "You do not have permission to access the Academic Misconduct Panel.\n\nYour role: {role}\nRequired roles: Admin, Staff, or Instructor", role=user_role)
            )
            self.root.destroy()
            return False

        return True

    def create_widgets(self):
        """Create and layout all widgets."""
        # Create main sidebar on far left
        self.create_main_sidebar()

        # Create header
        self.create_header()

        # Create main content area
        self.main_content_frame = tk.Frame(self.root, bg=self.colors['light'])
        self.main_content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create all view frames (hidden by default)
        self.views = {}
        self.current_view = None

        # Dashboard view
        self.create_dashboard_view()

        # Cases view (original case list + details)
        self.create_cases_view()

        # Analytics view
        self.create_analytics_view()

        # Evidence management view (top-level)
        self._create_evidence_view()

        # Superadmin cross-system dashboard (only for superadmin mode)
        if self.is_superadmin:
            self.create_superadmin_view()

        # Show dashboard by default
        self.show_view('dashboard')

    def _create_evidence_view(self):
        """Create a top-level evidence management view."""
        evidence_view = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['evidence'] = evidence_view

        # Reuse create_evidence_tab but at the top level
        self.evidence_parent = evidence_view
        self.evidence_frame = tk.Frame(evidence_view, bg=self.colors['light'])
        self.evidence_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.refresh_evidence_tab()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = AcademicMisconductPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
