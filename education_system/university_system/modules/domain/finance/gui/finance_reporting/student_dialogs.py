import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from education_system.university_system.core import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.core.i18n import get_text as _, init_i18n
init_i18n()


class CollectionCaseDialog:
    """Dialog for managing collection cases"""
    def __init__(self, parent):
        self.parent = parent
        self.result = False
        self.create_dialog()

    def create_dialog(self):
        """Create collection case dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.windows.collection_case"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.collection_case_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.create"), command=self.create_case).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def create_case(self):
        """Create collection case"""
        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class StudentDialog:
    """Dialog for managing students"""
    def __init__(self, parent, main_app, student_id=None):
        self.parent = parent
        self.main_app = main_app
        self.student_id = student_id
        self.result = False
        self.create_dialog()

    def create_dialog(self):
        """Create student dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.dialogs.add_student") if not self.student_id else _("finance_reporting.dialogs.edit_student"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.student_dialog_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.save"), command=self.save_student).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def save_student(self):
        """Save student data"""
        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class StudentFinancesDialog:
    """Dialog for viewing student financial details"""
    def __init__(self, parent, student_id):
        self.parent = parent
        self.student_id = student_id
        self.create_dialog()

    def create_dialog(self):
        """Create student finances dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.dialogs.student_finances_title", student_id=self.student_id))
        self.dialog.geometry("800x600")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.student_finances_pending", student_id=self.student_id)).pack(pady=20)

        ttk.Button(self.dialog, text=_("common.close"), command=self.dialog.destroy).pack(pady=20)


class CollectionAgenciesDialog:
    """Dialog for managing collection agencies"""
    def __init__(self, parent):
        self.parent = parent
        self.create_dialog()

    def create_dialog(self):
        """Create collection agencies dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.windows.manage_agencies"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.collection_agencies_pending")).pack(pady=20)

        ttk.Button(self.dialog, text=_("common.close"), command=self.dialog.destroy).pack(pady=20)


