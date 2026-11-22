
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domains.learners.domain.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.domains.learners.interfaces.gui.parent_portal.base import ParentPortalGUI
from education_system.systems.university.domains.learners.interfaces.gui.parent_portal.dialogs import ParentPortalCompat

class DataExportDialog:
    """Dialog for exporting student data"""

    def __init__(self, parent, children):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.parent_portal.misc.windows.export_student_data', default="Export Student Data"))
        self.dialog.geometry("550x600")
        self.dialog.minsize(500, 500)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Create scrollable canvas
        canvas_container = ttk.Frame(self.dialog)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_container)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding=20)

        main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(main_frame, text=_t('gui.academics.parent_portal.misc.labels.export_student_data', default="Export Student Data"), font=('Arial', 16, 'bold')).pack(pady=10)

        # Child selection
        child_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.select_student', default="Select Student"), padding=10)
        child_frame.pack(fill=tk.X, pady=10)

        self.child_var = tk.StringVar()
        for child in children:
            rb = ttk.Radiobutton(child_frame, text=f"{child[1]} {child[3]} (ID: {child[0]})",
                                variable=self.child_var, value=child[0])
            rb.pack(anchor='w')

        if children:
            self.child_var.set(children[0][0])

        # Data type selection
        data_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.select_data_types', default="Select Data Types"), padding=10)
        data_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.data_types = {}
        data_options = [
            ("grades", "Academic Grades"),
            ("attendance", "Attendance Records"),
            ("assignments", "Assignments"),
            ("behavior", "Conduct Reports"),
            ("medical", "Medical Information"),
            ("fees", "Fee Records"),
            ("activities", "Extracurricular Activities")
        ]

        for key, label in data_options:
            var = tk.BooleanVar(value=True)
            self.data_types[key] = var
            cb = ttk.Checkbutton(data_frame, text=label, variable=var)
            cb.pack(anchor='w')

        # Export format
        format_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.export_format', default="Export Format"), padding=10)
        format_frame.pack(fill=tk.X, pady=10)

        self.format_var = tk.StringVar(value=_t('gui.academics.parent_portal.misc.values.json', default="json"))
        ttk.Radiobutton(format_frame, text=_t('gui.academics.parent_portal.misc.buttons.json', default="JSON"), variable=self.format_var, value="json").pack(anchor='w')
        ttk.Radiobutton(format_frame, text=_t('gui.academics.parent_portal.misc.buttons.csv', default="CSV"), variable=self.format_var, value="csv").pack(anchor='w')
        ttk.Radiobutton(format_frame, text=_t('gui.academics.parent_portal.misc.buttons.pdf_report', default="PDF Report"), variable=self.format_var, value="pdf").pack(anchor='w')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.export', default="Export"), command=self.export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.cancel', default="Cancel"), command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.children = children
        self.dialog.wait_window()

    def export_data(self):
        selected_child = self.child_var.get()
        selected_types = [key for key, var in self.data_types.items() if var.get()]
        export_format = self.format_var.get()

        if not selected_child or not selected_types:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.selection_required', default="Selection Required"), _t('gui.academics.parent_portal.misc.dialogs.please_select_a_child_and_at_least_one_data_type', default="Please select a child and at least one data type."))
            return

        self.result = {
            'child_id': selected_child,
            'data_types': selected_types,
            'format': export_format
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()


class TwoFactorDialog:
    """Dialog for enabling two-factor authentication"""

    def __init__(self, parent):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.parent_portal.misc.windows.enable_two_factor_authentication', default="Enable Two-Factor Authentication"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.academics.parent_portal.misc.labels.enable_two_factor_authentication', default="Enable Two-Factor Authentication"), font=('Arial', 16, 'bold')).pack(pady=10)

        info_text = """Two-factor authentication adds an extra layer of security to your account.

You'll need an authenticator app like:
- Google Authenticator
- Microsoft Authenticator
- Authy

After enabling, you'll need to enter a code from your authenticator app each time you log in."""

        ttk.Label(main_frame, text=info_text, wraplength=450).pack(pady=10)

        # QR code placeholder
        qr_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.scan_qr_code_with_authenticator_app', default="Scan QR Code with Authenticator App"), padding=10)
        qr_frame.pack(fill=tk.X, pady=10)

        ttk.Label(qr_frame, text=_t('gui.academics.parent_portal.misc.labels.qr_code_would_appear_here', default="[QR Code would appear here]"),
                 font=('Arial', 12), background='lightgray',
                 relief='sunken', padding=50).pack()

        # Secret key
        secret_frame = ttk.Frame(main_frame)
        secret_frame.pack(fill=tk.X, pady=10)

        ttk.Label(secret_frame, text=_t('gui.academics.parent_portal.misc.labels.manual_entry_key', default="Manual Entry Key:")).pack(anchor='w')
        secret_var = tk.StringVar(value=_t('gui.academics.parent_portal.misc.values.abcd_efgh_ijkl_mnop', default="ABCD EFGH IJKL MNOP"))
        secret_entry = ttk.Entry(secret_frame, textvariable=secret_var, state='readonly')
        secret_entry.pack(fill=tk.X, pady=5)

        # Verification
        verify_frame = ttk.Frame(main_frame)
        verify_frame.pack(fill=tk.X, pady=10)

        ttk.Label(verify_frame, text=_t('gui.academics.parent_portal.misc.labels.enter_verification_code_from_your_app', default="Enter verification code from your app:")).pack(anchor='w')
        self.code_entry = ttk.Entry(verify_frame, width=20)
        self.code_entry.pack(pady=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.enable_2fa', default="Enable 2FA"), command=self.enable).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.cancel', default="Cancel"), command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.dialog.wait_window()

    def enable(self):
        code = self.code_entry.get().strip()
        if not code:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.missing_code', default="Missing Code"), _t('gui.academics.parent_portal.misc.dialogs.please_enter_the_verification_code', default="Please enter the verification code."))
            return

        # In real implementation, would verify the code
        if len(code) == 6 and code.isdigit():
            self.result = True
            self.dialog.destroy()
        else:
            messagebox.showerror(_t('gui.academics.parent_portal.misc.dialogs.invalid_code', default="Invalid Code"), _t('gui.academics.parent_portal.misc.dialogs.please_enter_a_valid_6_digit_code', default="Please enter a valid 6-digit code."))

    def cancel(self):
        self.dialog.destroy()


class DonationDialog:
    """Dialog for making donations to fundraising campaigns"""

    def __init__(self, parent, children):
        self.result = None
        self.children = children

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.parent_portal.misc.windows.make_donation', default="Make Donation"))
        self.dialog.geometry("550x600")
        self.dialog.minsize(500, 500)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Create scrollable canvas
        canvas_container = ttk.Frame(self.dialog)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_container)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding=20)

        main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(main_frame, text=_t('gui.academics.parent_portal.misc.labels.make_a_donation', default="Make a Donation"), font=('Arial', 16, 'bold')).pack(pady=10)

        # Campaign selection
        campaign_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.select_campaign', default="Select Campaign"), padding=10)
        campaign_frame.pack(fill=tk.X, pady=10)

        self.campaign_var = tk.StringVar()
        campaigns = ["University Library Fund", "Sports Equipment Drive", "Arts Program Support"]

        for campaign in campaigns:
            rb = ttk.Radiobutton(campaign_frame, text=campaign, variable=self.campaign_var, value=campaign)
            rb.pack(anchor='w')

        if campaigns:
            self.campaign_var.set(campaigns[0])

        # Amount
        amount_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.donation_amount', default="Donation Amount"), padding=10)
        amount_frame.pack(fill=tk.X, pady=10)

        ttk.Label(amount_frame, text=_t('gui.academics.parent_portal.misc.labels.amount', default="Amount (£):")).pack(anchor='w')
        self.amount_entry = ttk.Entry(amount_frame, width=20)
        self.amount_entry.pack(pady=5)

        # Child selection (optional)
        if children:
            child_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.misc.labels.donate_on_behalf_of_optional', default="Donate on behalf of (optional)"), padding=10)
            child_frame.pack(fill=tk.X, pady=10)

            self.child_var = tk.StringVar()

            rb = ttk.Radiobutton(child_frame, text=_t('gui.academics.parent_portal.misc.buttons.anonymous_donation', default="Anonymous donation"), variable=self.child_var, value="anonymous")
            rb.pack(anchor='w')

            for child in children:
                rb = ttk.Radiobutton(child_frame, text=f"{child[1]} {child[3]}",
                                   variable=self.child_var, value=f"{child[0]}")
                rb.pack(anchor='w')

            self.child_var.set("anonymous")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.donate', default="Donate"), command=self.donate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.cancel', default="Cancel"), command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.dialog.wait_window()

    def donate(self):
        campaign = self.campaign_var.get()
        amount_str = self.amount_entry.get().strip()

        if not campaign:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.missing_selection', default="Missing Selection"), _t('gui.academics.parent_portal.misc.dialogs.please_select_a_campaign', default="Please select a campaign."))
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.invalid_amount', default="Invalid Amount"), _t('gui.academics.parent_portal.misc.dialogs.please_enter_a_valid_donation_amount', default="Please enter a valid donation amount."))
            return

        child = None
        if hasattr(self, 'child_var'):
            child_selection = self.child_var.get()
            if child_selection != "anonymous":
                for child_data in self.children:
                    if child_data[0] == child_selection:
                        child = child_data
                        break

        self.result = (campaign, amount, child)
        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()


class QRCodeDialog:
    """Dialog for generating QR codes"""

    def __init__(self, parent, children):
        self.result = None
        self.children = children
        self.qr_image_label = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.parent_portal.misc.windows.generate_qr_code', default="Generate QR Code"))
        self.dialog.geometry("550x650")
        self.dialog.minsize(500, 550)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Create scrollable canvas
        canvas_container = ttk.Frame(self.dialog)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_container)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        self.main_frame = ttk.Frame(canvas, padding=20)

        self.main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(self.main_frame, text=_t('gui.academics.parent_portal.misc.labels.generate_qr_code', default="Generate QR Code"), font=('Arial', 16, 'bold')).pack(pady=10)

        ttk.Label(self.main_frame, text=_t('gui.academics.parent_portal.misc.labels.select_child_for_qr_code_generation', default="Select child for QR code generation:")).pack(anchor='w', pady=10)

        # Child selection
        self.child_var = tk.StringVar()
        for i, child in enumerate(children):
            rb = ttk.Radiobutton(self.main_frame, text=f"{child[1]} {child[3]} (ID: {child[0]})",
                               variable=self.child_var, value=str(i))
            rb.pack(anchor='w')

        if children:
            self.child_var.set("0")

        # Purpose selection
        purpose_frame = ttk.LabelFrame(self.main_frame, text=_t('gui.academics.parent_portal.misc.labels.qr_code_purpose', default="QR Code Purpose"), padding=10)
        purpose_frame.pack(fill=tk.X, pady=10)

        self.purpose_var = tk.StringVar()
        purposes = ["Student Identification", "Emergency Contact", "Identification"]

        for purpose in purposes:
            rb = ttk.Radiobutton(purpose_frame, text=purpose, variable=self.purpose_var, value=purpose)
            rb.pack(anchor='w')

        if purposes:
            self.purpose_var.set(purposes[0])

        # QR Code preview frame
        self.preview_frame = ttk.LabelFrame(self.main_frame, text=_t('gui.academics.parent_portal.misc.labels.qr_code_preview', default="QR Code Preview"), padding=10)
        self.preview_frame.pack(fill=tk.X, pady=10)
        self.preview_label = ttk.Label(self.preview_frame, text=_t('gui.academics.parent_portal.misc.labels.click_generate_to_create_qr_code', default="Click 'Generate' to create QR code"))
        self.preview_label.pack(pady=20)

        # Buttons
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.generate_save', default="Generate & Save"), command=self.generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.misc.buttons.cancel', default="Cancel"), command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.dialog.wait_window()

    def generate(self):
        child_index = self.child_var.get()
        purpose = self.purpose_var.get()

        if not child_index or not purpose:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.missing_selection', default="Missing Selection"), _t('gui.academics.parent_portal.misc.dialogs.please_select_a_child_and_purpose', default="Please select a child and purpose."))
            return

        try:
            index = int(child_index)
            if 0 <= index < len(self.children):
                child = self.children[index]
                qr_path = self._generate_qr_code(child, purpose)
                self.result = {
                    'child': child,
                    'purpose': purpose,
                    'qr_path': qr_path
                }
                self.dialog.destroy()
        except ValueError:
            messagebox.showerror(_t('gui.academics.parent_portal.misc.dialogs.error', default="Error"), _t('gui.academics.parent_portal.misc.dialogs.invalid_selection', default="Invalid selection."))

    def _generate_qr_code(self, child, purpose):
        """Actually generate the QR code and save it to the qr_codes directory"""
        try:
            import qrcode
            from education_system import paths
            import json

            # Create QR codes directory if it doesn't exist
            qr_dir = paths.UNIVERSITY_QR_CODES_DIR
            qr_dir.mkdir(parents=True, exist_ok=True)

            # Create QR code data
            student_id = child[0]
            first_name = child[1]
            last_name = child[3]
            course = child[4] if len(child) > 4 else "N/A"

            qr_data = {
                "type": purpose,
                "student_id": str(student_id),
                "name": f"{first_name} {last_name}",
                "course": course,
                "generated": datetime.datetime.now().isoformat()
            }

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Save QR code
            safe_name = f"{student_id}_{first_name}_{last_name}".replace(" ", "_").replace("/", "_")
            filename = f"qr_{safe_name}_{purpose.replace(' ', '_').lower()}.png"
            filepath = qr_dir / filename
            img.save(str(filepath))

            return str(filepath)

        except ImportError:
            messagebox.showwarning(_t('gui.academics.parent_portal.misc.dialogs.qr_code_library', default="QR Code Library"),
                                 _t('gui.academics.parent_portal.misc.dialogs.qr_code_library_not_installed_install_with_pip_install_qrcode_pi', default="QR code library not installed.\n"
                                 "Install with: pip install qrcode[pil]"))
            return None
        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.misc.dialogs.error', default="Error"), f"Failed to generate QR code: {str(e)}")
            return None

    def cancel(self):
        self.dialog.destroy()


class DatabaseManager:
    """Simplified database manager for GUI operations"""

    @staticmethod
    def get_connection():
        """Get database connection"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            # Use centralized path system
            from education_system import paths
            db_path = paths.UNIVERSITY_DEFAULT_DB_PATH
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.execute("PRAGMA busy_timeout = 30000")
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    @staticmethod
    def execute_query(query, params=None):
        """Execute a query and return results"""
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            if not conn:
                return None

            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount

        except Exception as e:
            print(f"Database query error: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()


def initialize_gui_parent_portal(auth=None):
    """Initialize the GUI version of the parent portal"""
    return ParentPortalCompat(auth)


def run_parent_portal(auth=None, prefer_gui=True):
    """
    Run the parent portal with automatic GUI/CLI selection.

    Args:
        auth: Authentication object
        prefer_gui: Whether to prefer GUI over CLI (default: True)
    """
    portal = ParentPortalCompat(auth)
    portal.display_parent_portal_menu(auth, use_gui=prefer_gui)


def create_tooltip(widget, text):
    """Create a tooltip for a widget"""
    def on_enter(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

        label = tk.Label(tooltip, text=text, background="#ffffe0",
                        relief="solid", borderwidth=1, font=("Arial", 9))
        label.pack()

        widget.tooltip = tooltip

    def on_leave(event):
        if hasattr(widget, 'tooltip'):
            widget.tooltip.destroy()
            del widget.tooltip

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def validate_email(email):
    """Simple email validation - delegates to centralized validator"""
    from education_system.systems.university.infrastructure.utils.input_validation import is_valid_email
    return is_valid_email(email)


def validate_phone(phone):
    """Simple phone validation - delegates to centralized validator"""
    from education_system.systems.university.infrastructure.utils.input_validation import is_valid_phone
    return is_valid_phone(phone, min_digits=10)


def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"


def format_date(date_string):
    """Format date string for display"""
    try:
        date_obj = datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_string

