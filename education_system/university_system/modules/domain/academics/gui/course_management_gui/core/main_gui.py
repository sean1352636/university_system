# gui_course_management.py
#
# Composes CourseManagementGUI from focused mixin modules.
# Each mixin lives in its own file under this ``core`` package.

from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import _, tk, ttk, UserAuth, get_auth

from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.db import DatabaseMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.ui_setup import UISetupMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.course_operations import CourseOperationsMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.search_filter import SearchFilterMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.analytics import AnalyticsMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.visualization import VisualizationMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.instructors import InstructorsMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.data_io import DataIOMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.dialogs import DialogsMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.lms_tab import LMSTabMixin
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.academic_tabs import (
    DegreeAuditTabMixin, CourseEvalTabMixin,
)


# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


class CourseManagementGUI(
    DatabaseMixin,
    UISetupMixin,
    CourseOperationsMixin,
    SearchFilterMixin,
    AnalyticsMixin,
    VisualizationMixin,
    InstructorsMixin,
    DataIOMixin,
    DialogsMixin,
    LMSTabMixin,
    DegreeAuditTabMixin,
    CourseEvalTabMixin,
):
    def __init__(self, parent, auth_system=None):
        self.root = parent
        self._is_embedded = not isinstance(parent, (tk.Tk, tk.Toplevel))

        if not self._is_embedded:
            self.root.title(_("course_management.title"))
            self.root.geometry("1200x800")
            self.root.configure(bg='#f0f0f0')

        # Initialize authentication - accept passed auth or use centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()

        # Create status bar FIRST so update_status() is safe during init
        self.status_var = tk.StringVar(value=_("course_management.status.initializing"))
        if not self._is_embedded:
            self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
            self.status_label.pack(side="bottom", fill="x")

        # Now it's safe to touch the DB and call update_status()
        self.init_database()

        # Build the rest of the UI
        if not self._is_embedded:
            self.create_menu()
        self.create_main_interface()

    def update_status(self, message, error=False):
        # Defensive: if someone calls this very early, ensure widgets exist
        if not hasattr(self, "status_var"):
            self.status_var = tk.StringVar(value="")
        if not hasattr(self, "status_label"):
            if not getattr(self, '_is_embedded', False):
                self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
                self.status_label.pack(side="bottom", fill="x")

        self.status_var.set(message)
        try:
            if hasattr(self, 'status_label'):
                self.status_label.configure(foreground=("red" if error else "black"))
        except Exception:
            pass
        self.root.update_idletasks()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            # Check if auth has current_user attribute and it's not None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user = self.auth.current_user
                # Handle both dict and object formats
                if isinstance(user, dict):
                    role = user.get('role', None)
                    if role:
                        return role.lower()
                elif hasattr(user, 'role'):
                    return user.role.lower()
            return None
        except Exception as e:
            print(_("course_management.errors.user_role", error=str(e)))
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'
