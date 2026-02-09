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
from university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
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
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()


class PaymentDialog:
    """Dialog for recording payments"""
    def __init__(self, parent, main_app, payment_id=None):
        self.parent = parent
        self.main_app = main_app
        self.payment_id = payment_id
        self.result = False
        self.create_dialog()
    
    def create_dialog(self):
        """Create payment dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.payment.record_payment") if not self.payment_id else _("finance_reporting.payment.edit_payment"))
        self.dialog.geometry("600x500")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.payment.dialog_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.save"), command=self.save_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)
    
    def save_payment(self):
        """Save payment data"""
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class RefundDialog:
    """Dialog for processing refunds"""
    def __init__(self, parent, payment_id, student_id, amount):
        self.parent = parent
        self.payment_id = payment_id
        self.student_id = student_id
        self.amount = amount
        self.result = False
        self.create_dialog()
    
    def create_dialog(self):
        """Create refund dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.windows.process_refund"))
        self.dialog.geometry("500x400")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.refund.dialog_pending", payment_id=self.payment_id)).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.process"), command=self.process_refund).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)
    
    def process_refund(self):
        """Process refund"""
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class FeeTypeDialog:
    """Dialog for managing fee types"""
    def __init__(self, parent, fee_type_id=None):
        self.parent = parent
        self.fee_type_id = fee_type_id
        self.result = False
        self.create_dialog()
    
    def create_dialog(self):
        """Create fee type dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.fee_type.add") if not self.fee_type_id else _("finance_reporting.fee_type.edit"))
        self.dialog.geometry("500x400")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.fee_type.dialog_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.save"), command=self.save_fee_type).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)
    
    def save_fee_type(self):
        """Save fee type"""
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class AssignFeeDialog:
    """Dialog for assigning fees to students"""
    def __init__(self, parent):
        self.parent = parent
        self.result = False
        self.create_dialog()
    
    def create_dialog(self):
        """Create assign fee dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.windows.assign_fee"))
        self.dialog.geometry("500x400")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.assign_fee.dialog_pending")).pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.assign"), command=self.assign_fee).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.cancel).pack(side='left', padx=10)
    
    def assign_fee(self):
        """Assign fee"""
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = False
        self.dialog.destroy()


class PaymentDetailsDialog:
    """Dialog for viewing payment details"""
    def __init__(self, parent, payment_id):
        self.parent = parent
        self.payment_id = payment_id
        self.create_dialog()
    
    def create_dialog(self):
        """Create payment details dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("finance_reporting.payment.details_title", payment_id=self.payment_id))
        self.dialog.geometry("500x400")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Add dialog content here
        ttk.Label(self.dialog, text=_("finance_reporting.payment.details_pending", payment_id=self.payment_id)).pack(pady=20)

        ttk.Button(self.dialog, text=_("common.close"), command=self.dialog.destroy).pack(pady=20)


