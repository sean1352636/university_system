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
from education_system.post_18.university_system.core import paths
matplotlib.use('TkAgg')
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.post_18.university_system.infrastructure.auth import get_current_user, set_auth_instance
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
    from education_system.post_18.university_system.infrastructure.auth import UserAuth
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()


class AidApplicationDialog:
    """Dialog for financial aid applications"""
    def __init__(self, parent):
        self.parent = parent
        self.result = False
        self.create_dialog()

    def create_dialog(self):
        """Create aid application dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.windows.financial_aid_application"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.aid_application_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.submit"), command=self.submit_application).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def submit_application(self):
        """Submit application"""
        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class BudgetPlanDialog:
    """Dialog for budget planning"""
    def __init__(self, parent, budget_id=None):
        self.parent = parent
        self.budget_id = budget_id
        self.result = False
        self.create_dialog()

    def create_dialog(self):
        """Create budget plan dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.dialogs.create_budget") if not self.budget_id else _("finance_reporting.dialogs.edit_budget"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.budget_plan_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.save"), command=self.save_budget).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def save_budget(self):
        """Save budget plan"""
        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class AidDisbursementDialog:
    """Dialog for aid disbursement"""
    def __init__(self, parent):
        self.parent = parent
        self.result = False
        self.create_dialog()

    def create_dialog(self):
        """Create aid disbursement dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.dialogs.disburse_aid"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.dialogs.disbursement_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_reporting.dialogs.disburse"), command=self.disburse_aid).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def disburse_aid(self):
        """Disburse aid"""
        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


