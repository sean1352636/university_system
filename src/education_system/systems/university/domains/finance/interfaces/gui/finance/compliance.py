"""Collections and compliance management"""
from education_system.systems.university.shell.gui import report_view as _rv

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from education_system.systems.university.infrastructure.i18n import get_text as _
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
import sys
import io
import os
import csv
from datetime import datetime, timedelta
import json
import threading
import warnings
from pathlib import Path
from cryptography.fernet import Fernet
import logging
from io import BytesIO
import base64
from education_system.systems.university.domains.finance.interfaces.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import database utilities - use centralized connection management
from education_system.systems.university.infrastructure.database.db import get_connection

# Import optional modules with fallbacks for non-critical functionality
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
except ImportError:
    def send_email(*args, **kwargs):
        """Fallback stub when email service is unavailable."""
        return True

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    def configure_logging(name=None):
        """Fallback logging configuration."""
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        """Fallback log file path resolution."""
        from education_system import paths
        return str(paths.UNIVERSITY_LOG_DIR / name)

# Import finance functions from common_imports module (explicit imports)
from education_system.systems.university.domains.finance.interfaces.gui.finance.common_imports import (
    # Collection management
    add_collection_agency,
    agency_performance_report,
    aging_analysis_report,
    assign_to_collection_agency,
    collection_case_status_report,
    collection_performance_summary,
    create_collection_case,
    deactivate_collection_agency,
    edit_collection_agency,
    manage_collection_agencies,
    recovery_rate_analysis,
    send_arrangement_confirmation,
    send_collection_notice,
    setup_collection_workflows,
    track_collection_progress,
    update_collection_case_status,
    view_collection_agencies,
    view_overdue_accounts,
    view_student_collection_detail,
    # Payment arrangements
    create_payment_arrangement,
    # System utilities
    check_required_packages,
    create_approval_workflow,
)

# Non-interactive collections API. The names imported above are the CLI menu
# wrappers: they prompt on stdin and print, so a GUI button must not call them.
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collections import (
    CASE_STATUSES,
    assign_case as assign_collection_case,
    format_collection_progress,
    list_active_agencies,
    list_unassigned_cases,
    set_case_status as set_collection_case_status,
)
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.agencies import (
    run_collection_workflow,
    save_collection_workflow,
)

# Configure logging
log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')




class CollectionsManager:
    """Collections management (overdue accounts, collection cases, agencies, aging/recovery reports)."""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        self.finance_system = vars(gui).get('finance_system')

    def update_status(self, message):
        """Forward status updates to the owning GUI when available."""
        if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
            self.gui.layout.update_status(message)
        elif hasattr(self.gui, 'update_status'):
            self.gui.update_status(message)

    def create_collections_tab(self):
        """Create collections management tab"""
        collections_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['collections'] = collections_frame

        # Collections toolbar
        toolbar = tk.Frame(collections_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar, text=_("finance_gui.compliance.btn_view_overdue"), command=self.view_overdue_accounts,
                 bg=self.colors['danger'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.compliance.btn_create_case"), command=self.create_collection_case,
                 bg=self.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.compliance.btn_manage_agencies"), command=self.manage_agencies,
                 bg=self.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.compliance.btn_track_progress"), command=self.track_collections,
                 bg=self.colors['success'], fg='white').pack(side='left', padx=5)

        # Additional toolbar buttons (second row if needed)
        toolbar2 = tk.Frame(collections_frame, bg='white')
        toolbar2.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar2, text=_("finance_gui.compliance.btn_track_progress"), command=self.gui_track_collection_progress,
                 bg=self.colors['info'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text=_("finance_gui.compliance.btn_update_case_status"), command=self.gui_update_collection_case_status,
                 bg=self.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text=_("finance_gui.compliance.btn_create_arrangement"), command=self.gui_create_payment_arrangement,
                 bg=self.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text=_("finance_gui.compliance.btn_assign_to_agency"), command=self.gui_assign_to_collection_agency,
                 bg=self.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text=_("finance_gui.compliance.btn_send_notice"), command=self.gui_send_collection_notice,
                 bg=self.colors['danger'], fg='white').pack(side='left', padx=5)

        # Collections content
        content_frame = tk.PanedWindow(collections_frame, orient='horizontal')
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Left panel - Overdue accounts
        left_panel = tk.LabelFrame(content_frame, text=_("finance_gui.compliance.overdue_accounts_frame"), font=('Arial', 12, 'bold'))
        content_frame.add(left_panel, minsize=400)

        self.overdue_tree = ttk.Treeview(left_panel, columns=('student_id', 'name', 'amount', 'days'), show='headings')
        self.overdue_tree.heading('student_id', text=_("finance_gui.compliance.column_student_id"))
        self.overdue_tree.heading('name', text=_("finance_gui.compliance.column_name"))
        self.overdue_tree.heading('amount', text=_("finance_gui.compliance.column_amount"))
        self.overdue_tree.heading('days', text=_("finance_gui.compliance.column_days_overdue"))
        self.overdue_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Right panel - Collection cases
        right_panel = tk.LabelFrame(content_frame, text=_("finance_gui.compliance.collection_cases_frame"), font=('Arial', 12, 'bold'))
        content_frame.add(right_panel, minsize=400)

        self.cases_tree = ttk.Treeview(right_panel, columns=('case_id', 'student', 'status', 'agency'), show='headings')
        self.cases_tree.heading('case_id', text=_("finance_gui.compliance.column_case_id"))
        self.cases_tree.heading('student', text=_("finance_gui.compliance.column_student"))
        self.cases_tree.heading('status', text=_("finance_gui.compliance.column_status"))
        self.cases_tree.heading('agency', text=_("finance_gui.compliance.column_agency"))
        self.cases_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Load collections data
        self.refresh_collections()


    def view_overdue_accounts(self):
        """View overdue accounts"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            view_overdue_accounts()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            # Show in a new window
            self.show_text_window(_("finance_gui.compliance.overdue_accounts_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_view_overdue").format(error=str(e)))


    def create_collection_case(self):
        """Create new collection case"""
        case_name = simpledialog.askstring(_("finance_gui.compliance.collection_case_title"), _("finance_gui.compliance.enter_case_name"))
        if case_name:
            student_id = simpledialog.askstring(_("finance_gui.compliance.collection_case_title"), _("finance_gui.compliance.enter_student_id"))
            if student_id:
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.case_created").format(name=case_name, student_id=student_id))
                # Here you would save to database
                self.refresh_collections()


    def manage_agencies(self):
        """Manage collection agencies (real ``collection_agencies`` rows).

        The previous dialog showed three hard-coded sample agencies and only
        edited its own Treeview. It now lives in ``agencies_dialog.py`` on
        the same agencies API the collections CLI uses.
        """
        from education_system.systems.university.domains.finance.interfaces.gui.finance.agencies_dialog import (
            open_manage_agencies,
        )
        try:
            open_manage_agencies(self.root, on_change=self.refresh_collections)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_manage_agencies").format(error=e))


    def track_collections(self):
        """Track collection progress"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            track_collection_progress()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window(_("finance_gui.compliance.collection_progress_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_track_collections").format(error=str(e)))

    # ==================== FINANCIAL AID METHODS ====================


    def refresh_collections(self):
        """Refresh collections data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get overdue accounts
                cursor.execute('''
                SELECT sf.student_id, s.first_name || ' ' || s.last_name as name,
                       SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as amount,
                       MAX(julianday('now') - julianday(sf.due_date)) as days_overdue
                FROM student_fees sf
                JOIN students s ON sf.student_id = s.student_id
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                WHERE sf.status IN ('unpaid', 'partial') AND date(sf.due_date) < date('now')
                GROUP BY sf.student_id
                HAVING (SUM(sf.amount) - COALESCE(SUM(pa.amount), 0)) > 0
                ORDER BY days_overdue DESC
                ''')

                overdue_accounts = cursor.fetchall()

                # Get collection cases
                cursor.execute('''
                SELECT cc.case_id, s.first_name || ' ' || s.last_name as student_name,
                       cc.case_status, COALESCE(ca.agency_name, 'Unassigned') as agency
                FROM collection_cases cc
                JOIN students s ON cc.student_id = s.student_id
                LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
                WHERE cc.case_status NOT IN ('resolved', 'closed')
                ORDER BY cc.created_at DESC
                ''')

                collection_cases = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_collections_data(overdue_accounts, collection_cases))

            except Exception as e:
                print(f"Error refreshing collections: {e}")

        refresh_thread()


    def update_collections_data(self, overdue_accounts, collection_cases):
        """Update collections data in UI"""
        # Update overdue accounts
        for item in self.overdue_tree.get_children():
            self.overdue_tree.delete(item)

        for account in overdue_accounts:
            student_id, name, amount, days_overdue = account
            display_data = (student_id, name, f"\u00a3{amount:.2f}", f"{int(days_overdue)}")
            self.overdue_tree.insert('', 'end', values=display_data)

        # Update collection cases
        for item in self.cases_tree.get_children():
            self.cases_tree.delete(item)

        for case in collection_cases:
            self.cases_tree.insert('', 'end', values=case)


    def gui_view_overdue_accounts(self):
        """GUI wrapper for view_overdue_accounts"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.overdue_accounts_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            view_overdue_accounts()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = _rv.TextReportView(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_view_overdue").format(error=e))


    def gui_create_collection_case(self):
        """GUI wrapper for create_collection_case"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.create_case_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.case_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Case notes
        ttk.Label(form_frame, text=_("finance_gui.compliance.case_notes_label")).pack(anchor='w', pady=5)
        notes_text = tk.Text(form_frame, height=6, width=50)
        notes_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def create_case():
            try:
                student_id = student_id_var.get().strip()
                notes = notes_text.get("1.0", tk.END).strip()

                if not student_id:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.student_id_required"))
                    return

                create_collection_case(student_id, notes)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.case_created_success"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_create_case").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_create_case"), command=create_case).pack(pady=20)


    def gui_manage_collection_agencies(self):
        """GUI wrapper for manage_collection_agencies"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.manage_agencies_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            manage_collection_agencies()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = _rv.TextReportView(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_manage_agencies").format(error=e))


    def gui_add_collection_agency(self):
        """GUI wrapper for add_collection_agency"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.add_agency_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.agency_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Agency name
        ttk.Label(form_frame, text=_("finance_gui.compliance.agency_name_label") + ":").pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # Contact email
        ttk.Label(form_frame, text=_("finance_gui.compliance.contact_email_label")).pack(anchor='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)

        # Phone
        ttk.Label(form_frame, text=_("finance_gui.compliance.phone_label") + ":").pack(anchor='w', pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=phone_var).pack(anchor='w', fill='x', pady=5)

        # Commission rate
        ttk.Label(form_frame, text=_("finance_gui.compliance.commission_rate_label")).pack(anchor='w', pady=5)
        commission_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=commission_var).pack(anchor='w', fill='x', pady=5)

        def add_agency():
            try:
                name = name_var.get().strip()
                email = email_var.get().strip()
                phone = phone_var.get().strip()
                commission = float(commission_var.get())

                if not all([name, email, phone, commission >= 0]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.all_fields_required"))
                    return

                add_collection_agency(name, email, phone, commission)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.agency_added_success"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_commission_rate"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_add_agency").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_add_agency"), command=add_agency).pack(pady=20)


    def gui_edit_collection_agency(self):
        """GUI wrapper for edit_collection_agency"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.edit_agency_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.edit_agency_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Agency ID
        ttk.Label(form_frame, text=_("finance_gui.compliance.agency_id_label")).pack(anchor='w', pady=5)
        agency_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=agency_id_var).pack(anchor='w', fill='x', pady=5)

        # New name
        ttk.Label(form_frame, text=_("finance_gui.compliance.new_name_label")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # New email
        ttk.Label(form_frame, text=_("finance_gui.compliance.new_email_label")).pack(anchor='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)

        # New commission rate
        ttk.Label(form_frame, text=_("finance_gui.compliance.new_commission_label")).pack(anchor='w', pady=5)
        commission_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=commission_var).pack(anchor='w', fill='x', pady=5)

        def edit_agency():
            try:
                agency_id = int(agency_id_var.get())
                new_name = name_var.get().strip()
                new_email = email_var.get().strip()
                new_commission = float(commission_var.get()) if commission_var.get().strip() else None

                if not agency_id:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.agency_id_required"))
                    return

                edit_collection_agency(agency_id, new_name, new_email, new_commission)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.agency_updated"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_agency_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_edit_agency").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_update_agency"), command=edit_agency).pack(pady=20)


    def gui_deactivate_collection_agency(self):
        """GUI wrapper for deactivate_collection_agency"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.deactivate_agency_title"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.deactivate_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Agency ID
        ttk.Label(form_frame, text=_("finance_gui.compliance.agency_id_deactivate")).pack(anchor='w', pady=5)
        agency_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=agency_id_var).pack(anchor='w', fill='x', pady=5)

        def deactivate_agency():
            try:
                agency_id = int(agency_id_var.get())

                if messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.compliance.confirm_deactivate").format(id=agency_id)):
                    deactivate_collection_agency(agency_id)
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.agency_deactivated"))
                    dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_agency_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_deactivate").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_deactivate"), command=deactivate_agency).pack(pady=20)


    def gui_view_collection_agencies(self):
        """GUI wrapper for view_collection_agencies"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.view_agencies_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            view_collection_agencies()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = _rv.TextReportView(dialog, height=25, width=80, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_view_agencies").format(error=e))


    def gui_assign_to_collection_agency(self):
        """GUI wrapper for assigning a collection case to an agency."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.assign_to_agency_title"))
        dialog.geometry("560x360")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.assignment_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        try:
            cases = list_unassigned_cases()
            agencies = list_active_agencies()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"),
                                 _("finance_gui.compliance.failed_assign_case").format(error=e),
                                 parent=dialog)
            dialog.destroy()
            return

        # Case — picked from the unassigned cases rather than typed as a raw id
        ttk.Label(form_frame, text=_("finance_gui.compliance.case_id_label")).pack(anchor='w', pady=5)
        case_var = tk.StringVar()
        case_labels = {
            f"#{c['case_id']} - {c['first_name']} {c['last_name']} (£{c['total_debt']:,.2f})": c['case_id']
            for c in cases
        }
        ttk.Combobox(form_frame, textvariable=case_var, values=list(case_labels),
                     state='readonly').pack(anchor='w', fill='x', pady=5)

        ttk.Label(form_frame, text=_("finance_gui.compliance.agency_id_label")).pack(anchor='w', pady=5)
        agency_var = tk.StringVar()
        agency_labels = {
            f"#{a['agency_id']} - {a['agency_name']} ({a['commission_rate']}%)": a['agency_id']
            for a in agencies
        }
        ttk.Combobox(form_frame, textvariable=agency_var, values=list(agency_labels),
                     state='readonly').pack(anchor='w', fill='x', pady=5)

        if not cases or not agencies:
            ttk.Label(
                form_frame,
                text=_("finance_gui.compliance.no_cases_or_agencies",
                       default="No unassigned cases, or no active agencies to assign them to."),
                foreground='red', wraplength=460, justify='left',
            ).pack(anchor='w', pady=10)

        def assign_case():
            case_id = case_labels.get(case_var.get())
            agency_id = agency_labels.get(agency_var.get())
            if case_id is None or agency_id is None:
                messagebox.showerror(_("finance_gui.messages.error"),
                                     _("finance_gui.compliance.case_and_agency_required",
                                       default="Select both a case and an agency."),
                                     parent=dialog)
                return
            try:
                result = assign_collection_case(case_id, agency_id)
                messagebox.showinfo(_("finance_gui.messages.success"),
                                    _("finance_gui.compliance.case_assigned_to",
                                      default="Case #{case_id} assigned to {agency}.",
                                      case_id=result['case_id'], agency=result['agency_name']),
                                    parent=dialog)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"),
                                     _("finance_gui.compliance.failed_assign_case").format(error=e),
                                     parent=dialog)

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_assign_case"), command=assign_case).pack(pady=20)


    def gui_track_collection_progress(self):
        """GUI wrapper for collection progress tracking.

        Calls the report builder directly. The CLI entry point of the same name
        prompts on stdin for a case to update, which would hang the Tk loop.
        """
        try:
            output = format_collection_progress()

            self.show_text_window(_("finance_gui.compliance.collection_progress_tracking"), output)
            self.update_status(_("finance_gui.compliance.tracking_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_track_progress").format(error=e))


    def gui_update_collection_case_status(self):
        """GUI wrapper for update_collection_case_status"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.update_status_title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.status_update_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Case ID
        ttk.Label(form_frame, text=_("finance_gui.compliance.case_id_update")).pack(anchor='w', pady=5)
        case_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=case_id_var).pack(anchor='w', fill='x', pady=5)

        # New status — the statuses the domain actually accepts
        ttk.Label(form_frame, text=_("finance_gui.compliance.new_status_label")).pack(anchor='w', pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                   values=list(CASE_STATUSES), state='readonly')
        status_combo.pack(anchor='w', fill='x', pady=5)

        # Amount collected — recorded when a case is resolved or closed
        ttk.Label(form_frame, text=_("finance_gui.compliance.amount_collected_label",
                                     default="Amount Collected (£):")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Notes
        ttk.Label(form_frame, text=_("finance_gui.compliance.update_notes_label")).pack(anchor='w', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=50)
        notes_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def update_status():
            try:
                case_id = int(case_id_var.get())
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_case_id"), parent=dialog)
                return

            new_status = status_var.get()
            if not new_status:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.case_status_required"), parent=dialog)
                return

            amount_collected = None
            if amount_var.get().strip():
                try:
                    amount_collected = float(amount_var.get())
                except ValueError:
                    messagebox.showerror(_("finance_gui.messages.error"),
                                         _("finance_gui.compliance.invalid_amount_collected",
                                           default="Amount collected must be a number."),
                                         parent=dialog)
                    return

            try:
                set_collection_case_status(case_id, new_status,
                                           notes_text.get("1.0", tk.END).strip(),
                                           amount_collected)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.status_updated"), parent=dialog)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_update_status").format(error=e), parent=dialog)

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_update_status"), command=update_status).pack(pady=20)


    def gui_create_payment_arrangement(self):
        """GUI wrapper for create_payment_arrangement"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.payment_arrangement_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.payment_arrangement_frame"), padding=20)

        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Total amount
        ttk.Label(form_frame, text=_("finance_gui.compliance.total_amount_label")).pack(anchor='w', pady=5)
        total_amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=total_amount_var).pack(anchor='w', fill='x', pady=5)

        # Monthly payment
        ttk.Label(form_frame, text=_("finance_gui.compliance.monthly_payment_label")).pack(anchor='w', pady=5)
        monthly_payment_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=monthly_payment_var).pack(anchor='w', fill='x', pady=5)

        # Start date
        ttk.Label(form_frame, text=_("finance_gui.compliance.start_date_label")).pack(anchor='w', pady=5)
        start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=start_date_var).pack(anchor='w', fill='x', pady=5)

        # Terms
        ttk.Label(form_frame, text=_("finance_gui.compliance.terms_label")).pack(anchor='w', pady=5)
        terms_text = tk.Text(form_frame, height=4, width=50)
        terms_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def create_arrangement():
            try:
                student_id = student_id_var.get().strip()
                total_amount = float(total_amount_var.get())
                monthly_payment = float(monthly_payment_var.get())
                start_date = start_date_var.get().strip()
                terms = terms_text.get("1.0", tk.END).strip()

                if not all([student_id, total_amount > 0, monthly_payment > 0, start_date]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.required_fields"))
                    return

                create_payment_arrangement(student_id, total_amount, monthly_payment, start_date, terms)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.arrangement_created"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_amount_values"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_create_arrangement").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_create_arrangement"), command=create_arrangement).pack(pady=20)


    def gui_send_arrangement_confirmation(self):
        """GUI wrapper for send_arrangement_confirmation"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.send_confirmation_title"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.send_confirmation_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Arrangement ID
        ttk.Label(form_frame, text=_("finance_gui.compliance.arrangement_id_label")).pack(anchor='w', pady=5)
        arrangement_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=arrangement_id_var).pack(anchor='w', fill='x', pady=5)

        def send_confirmation():
            try:
                arrangement_id = int(arrangement_id_var.get())

                send_arrangement_confirmation(arrangement_id)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.confirmation_sent"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.invalid_arrangement_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_send_confirmation").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_send_confirmation"), command=send_confirmation).pack(pady=20)


    def gui_setup_collection_workflows(self):
        """GUI wrapper for collection workflow setup.

        Collects the thresholds in a form and saves them. The CLI entry point of
        the same name prompts for each value on stdin, which would hang the GUI.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.setup_workflows_title", default="Collection Workflow Setup"))
        dialog.geometry("520x420")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.workflow_details_frame",
                                                   default="Workflow Details"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(form_frame, text=_("finance_gui.compliance.workflow_name_label",
                                     default="Workflow Name:")).pack(anchor='w', pady=5)
        name_var = tk.StringVar(value=_("finance_gui.compliance.default_workflow_name",
                                        default="Default overdue workflow"))
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        ttk.Label(form_frame, text=_("finance_gui.compliance.minimum_debt_label",
                                     default="Minimum Overdue Debt (£):")).pack(anchor='w', pady=5)
        min_debt_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=min_debt_var).pack(anchor='w', fill='x', pady=5)

        ttk.Label(form_frame, text=_("finance_gui.compliance.reminder_days_label",
                                     default="Reminder Interval (days):")).pack(anchor='w', pady=5)
        reminder_var = tk.StringVar(value="14")
        ttk.Entry(form_frame, textvariable=reminder_var).pack(anchor='w', fill='x', pady=5)

        ttk.Label(form_frame, text=_("finance_gui.compliance.escalation_days_label",
                                     default="Escalate After (days):")).pack(anchor='w', pady=5)
        escalation_var = tk.StringVar(value="30")
        ttk.Entry(form_frame, textvariable=escalation_var).pack(anchor='w', fill='x', pady=5)

        auto_assign_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, variable=auto_assign_var,
                        text=_("finance_gui.compliance.auto_assign_label",
                               default="Automatically assign an eligible agency")).pack(anchor='w', pady=5)

        run_now_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, variable=run_now_var,
                        text=_("finance_gui.compliance.run_workflow_now_label",
                               default="Run the workflow immediately")).pack(anchor='w', pady=5)

        def save_workflow():
            try:
                minimum_debt = float(min_debt_var.get())
                reminder_days = int(reminder_var.get())
                escalation_days = int(escalation_var.get())
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"),
                                     _("finance_gui.compliance.invalid_workflow_values",
                                       default="Thresholds and day counts must be numbers."),
                                     parent=dialog)
                return

            try:
                workflow_id = save_collection_workflow(
                    name_var.get().strip() or _("finance_gui.compliance.default_workflow_name",
                                                default="Default overdue workflow"),
                    minimum_debt, reminder_days, escalation_days, auto_assign_var.get(),
                )

                summary = _("finance_gui.compliance.workflow_saved",
                            default="Workflow saved (ID: {workflow_id}).", workflow_id=workflow_id)
                if run_now_var.get():
                    result = run_collection_workflow(workflow_id)
                    summary += "\n" + _("finance_gui.compliance.workflow_run_result",
                                        default="Created {created} case(s); assigned {assigned} case(s).",
                                        created=result['created'], assigned=result['assigned'])

                messagebox.showinfo(_("finance_gui.messages.success"), summary, parent=dialog)
                self.update_status(_("finance_gui.compliance.workflows_configured"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"),
                                     _("finance_gui.compliance.failed_setup_workflows").format(error=e),
                                     parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text=_("finance_gui.compliance.btn_save_workflow",
                                        default="Save Workflow"), command=save_workflow).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy).pack(side='left', padx=5)


    def gui_send_collection_notice(self):
        """GUI wrapper for send_collection_notice"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.send_notice_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.collection_notice_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Notice type
        ttk.Label(form_frame, text=_("finance_gui.compliance.notice_type_label")).pack(anchor='w', pady=5)
        notice_type_var = tk.StringVar(value=_t('gui.finance.finance.compliance.values.first_notice', default="first_notice"))
        notice_combo = ttk.Combobox(form_frame, textvariable=notice_type_var,
                                   values=["first_notice", "second_notice", "final_notice"])
        notice_combo.pack(anchor='w', fill='x', pady=5)

        # Custom message
        ttk.Label(form_frame, text=_("finance_gui.compliance.custom_message_label")).pack(anchor='w', pady=5)
        message_text = tk.Text(form_frame, height=6, width=50)
        message_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def send_notice():
            try:
                student_id = student_id_var.get().strip()
                notice_type = notice_type_var.get()
                custom_message = message_text.get("1.0", tk.END).strip()

                if not student_id:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.student_id_required"))
                    return

                send_collection_notice(student_id, notice_type, custom_message)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.notice_sent"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_send_notice").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_send_notice"), command=send_notice).pack(pady=20)


    def gui_recovery_rate_analysis(self):
        """GUI wrapper for recovery_rate_analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            recovery_rate_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.compliance.recovery_analysis_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_recovery_analysis").format(error=e))


    def gui_agency_performance_report(self):
        """GUI wrapper for agency_performance_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            agency_performance_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.compliance.agency_performance_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_agency_performance").format(error=e))


    def gui_collection_performance_summary(self):
        """GUI wrapper for collection_performance_summary"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            collection_performance_summary()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.compliance.collection_summary_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_collection_summary").format(error=e))

    # Add these to handle missing core functions that might not have been implemented

    def gui_aging_analysis_report(self):
        """GUI wrapper for aging_analysis_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            aging_analysis_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.compliance.aging_analysis_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_aging_analysis").format(error=e))


    def gui_collection_case_status_report(self):
        """GUI wrapper for collection_case_status_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            collection_case_status_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.compliance.case_status_report_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_case_status_report").format(error=e))


    def gui_view_student_collection_detail(self):
        """GUI wrapper for view_student_collection_detail"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.student_details_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.common_labels.student_id")).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)

        def show_details():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.student_id_required"))
                return

            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                view_student_collection_detail(student_id)

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                details_text.delete('1.0', tk.END)
                details_text.insert('1.0', output)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_view_details").format(error=e))

        ttk.Button(input_frame, text=_("finance_gui.compliance.view_details"), command=show_details).pack(side='left', padx=10)

        # Details display
        details_text = _rv.TextReportView(dialog, height=20, width=80, font=('Courier', 10))
        details_text.pack(fill='both', expand=True, padx=10, pady=10)


    def gui_manage_collections(self):
        """Switch to collections tab"""
        # Switch to collections tab
        self.show_tab('collections')


    def gui_view_audit_logs(self):
        """GUI for viewing audit logs"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.audit_logs_title"))
        dialog.geometry("1000x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Date range selection
        filter_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.filter_options_frame"), padding=15)
        filter_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(filter_frame, text=_("finance_gui.compliance.start_date_label")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=start_date_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(filter_frame, text=_("finance_gui.compliance.end_date_label")).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=end_date_var, width=12).grid(row=0, column=3, padx=5, pady=5)

        def load_audit_logs():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT user_id, action, table_name, record_id, new_values, timestamp
                FROM audit_log
                WHERE date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp DESC
                LIMIT 1000
                ''', (start_date_var.get(), end_date_var.get()))

                logs = cursor.fetchall()

                # Clear existing items
                for item in audit_tree.get_children():
                    audit_tree.delete(item)

                # Add log data
                for log in logs:
                    user_id, action, table_name, record_id, details, timestamp = log
                    details_summary = str(details)[:50] + "..." if len(str(details)) > 50 else str(details)

                    audit_tree.insert('', 'end', values=(
                        timestamp, user_id, action, table_name, record_id, details_summary
                    ))

                status_label.config(text=_("finance_gui.compliance.loaded_entries").format(count=len(logs)))
                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_load_audit").format(error=e))

        ttk.Button(filter_frame, text=_("finance_gui.compliance.btn_load_logs"), command=load_audit_logs).grid(row=0, column=4, padx=10, pady=5)

        def open_audit_report():
            # CLI core menu option 21: same text report + CSV export, by date range.
            from education_system.systems.university.domains.finance.interfaces.gui.finance.audit_report_dialog import open_audit_report_dialog
            open_audit_report_dialog(dialog, start_date_var.get(), end_date_var.get())

        ttk.Button(filter_frame, text=_("finance_gui.compliance.btn_audit_report", default="Audit report…"),
                   command=open_audit_report).grid(row=0, column=5, padx=5, pady=5)

        # Audit logs display
        logs_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.audit_entries_frame"), padding=15)
        logs_frame.pack(fill='both', expand=True, padx=20, pady=10)

        column_keys = ['column_timestamp', 'column_user', 'column_action', 'column_table', 'column_record_id', 'column_details']
        columns = [_("finance_gui.compliance." + key) for key in column_keys]
        column_ids = ('Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Details')
        audit_tree = ttk.Treeview(logs_frame, columns=column_ids, show='headings', height=15)

        for col_id, col in zip(column_ids, columns):
            audit_tree.heading(col_id, text=col)
            width = 200 if col_id == 'Details' else 120 if col_id == 'Timestamp' else 100
            audit_tree.column(col_id, width=width, anchor='center')

        # Scrollbars
        audit_v_scroll = ttk.Scrollbar(logs_frame, orient='vertical', command=audit_tree.yview)
        audit_h_scroll = ttk.Scrollbar(logs_frame, orient='horizontal', command=audit_tree.xview)
        audit_tree.configure(yscrollcommand=audit_v_scroll.set, xscrollcommand=audit_h_scroll.set)

        audit_tree.pack(side='left', fill='both', expand=True)
        audit_v_scroll.pack(side='right', fill='y')
        audit_h_scroll.pack(side='bottom', fill='x')

        # Status
        status_label = ttk.Label(dialog, text=_("finance_gui.compliance.click_load_logs"))
        status_label.pack(pady=10)

        # Load initial data
        load_audit_logs()


    def gui_check_required_packages(self):
        """GUI wrapper for check_required_packages"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            check_required_packages()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window(_("finance_gui.compliance.package_check_title"), output)
            self.update_status(_("finance_gui.compliance.package_check_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_package_check").format(error=e))


    def gui_create_approval_workflow(self):
        """GUI wrapper for create_approval_workflow"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.compliance.create_workflow_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.compliance.workflow_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Workflow type
        ttk.Label(form_frame, text=_("finance_gui.compliance.workflow_type_label")).pack(anchor='w', pady=5)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                 values=["payment", "refund", "budget", "aid_application"])
        type_combo.pack(anchor='w', fill='x', pady=5)

        # Entity ID
        ttk.Label(form_frame, text=_("finance_gui.compliance.entity_id_label")).pack(anchor='w', pady=5)
        entity_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=entity_id_var).pack(anchor='w', fill='x', pady=5)

        # Notes
        ttk.Label(form_frame, text=_("finance_gui.common_labels.notes")).pack(anchor='w', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=50)
        notes_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def create_workflow():
            try:
                workflow_type = type_var.get().strip()
                entity_id = entity_id_var.get().strip()
                notes = notes_text.get("1.0", tk.END).strip()

                if not all([workflow_type, entity_id]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.workflow_type_required"))
                    return

                create_approval_workflow(workflow_type, entity_id, notes)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.compliance.workflow_created"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.compliance.failed_create_workflow").format(error=e))

        ttk.Button(form_frame, text=_("finance_gui.compliance.btn_create_workflow"), command=create_workflow).pack(pady=20)
