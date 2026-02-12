"""TA Management GUI - Coordinator."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from university_system.modules.domain.academics.services.ta_management.ta_service import TAService

logger = logging.getLogger(__name__)


class TAManagementGUI:
    """Main coordinator for TA Management GUI."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.service = TAService()

        self.window = tk.Toplevel(parent)
        self.window.title("Teaching Assistant Management")
        self.window.geometry("950x650")
        self.window.transient(parent)

        self._setup_ui()

    def _setup_ui(self):
        """Build the main UI with a tabbed notebook."""
        title = ttk.Label(
            self.window,
            text="Teaching Assistant Management",
            font=('Arial', 16, 'bold'),
        )
        title.pack(pady=(10, 5))

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        role = ''
        if self.auth and self.auth.current_user:
            role = self.auth.current_user.get('role', '')

        from university_system.modules.domain.academics.gui.ta_management.assignment_manager import (
            AssignmentManager,
        )
        from university_system.modules.domain.academics.gui.ta_management.permissions_manager import (
            PermissionsManager,
        )

        # Assignment tab (manage/view TAs)
        assign_frame = ttk.Frame(self.notebook)
        self.notebook.add(assign_frame, text="TA Assignments")
        self.assignment_manager = AssignmentManager(assign_frame, self.service, self.auth)

        # Permissions tab (admin/instructor only)
        if role in ('admin', 'instructor'):
            perm_frame = ttk.Frame(self.notebook)
            self.notebook.add(perm_frame, text="TA Permissions")
            self.permissions_manager = PermissionsManager(perm_frame, self.service, self.auth)

            # Performance Evaluation tab (admin/instructor only)
            from university_system.modules.domain.academics.gui.ta_management.evaluation_manager import (
                EvaluationManager,
            )
            eval_frame = ttk.Frame(self.notebook)
            self.notebook.add(eval_frame, text="Performance Evaluation")
            self.evaluation_manager = EvaluationManager(eval_frame, self.service, self.auth)
