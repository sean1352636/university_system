# gui_course_management.py
#
# Composes CourseManagementGUI from focused mixin modules.
# Each mixin lives in its own file under this ``core`` package.

from ._imports import _, tk, ttk, UserAuth, get_auth

from .db import DatabaseMixin
from .ui_setup import UISetupMixin
from .course_operations import CourseOperationsMixin
from .search_filter import SearchFilterMixin
from .analytics import AnalyticsMixin
from .visualization import VisualizationMixin
from .instructors import InstructorsMixin
from .data_io import DataIOMixin
from .dialogs import DialogsMixin


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
):
    def __init__(self, parent, auth_system=None):
        self.root = parent
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
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
        self.status_label.pack(side="bottom", fill="x")

        # Now it's safe to touch the DB and call update_status()
        self.init_database()

        # Build the rest of the UI
        self.create_menu()
        self.create_main_interface()

    def update_status(self, message, error=False):
        # Defensive: if someone calls this very early, ensure widgets exist
        if not hasattr(self, "status_var"):
            self.status_var = tk.StringVar(value="")
            self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
            self.status_label.pack(side="bottom", fill="x")

        self.status_var.set(message)
        try:
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
