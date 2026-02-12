"""
Legal Services GUI

Comprehensive GUI for university legal aid center providing case management,
consultations, document management, billing, and reporting with full
email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback
import os

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.domain.legal.services.legal_services_core import (
    CaseManager, ConsultationManager, DocumentManager, PaymentManager,
    init_legal_services_db, calculate_service_fee, generate_invoice_text,
    CASE_TYPES, CASE_STATUSES, CONSULTATION_STATUSES, PAYMENT_STATUSES, SERVICE_FEES
)
from university_system.modules.shared.utils.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        print("Email service not available")
        return False
    render_template = None

# Import finance integration
try:
    from university_system.modules.domain.finance.core.finance_db_operations import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def record_payment_to_finance(*args, **kwargs):
        return None
    def get_student_finance_account_balance(*args, **kwargs):
        return 0.0
    def process_student_finance_account_payment(*args, **kwargs):
        return False

import logging
logger = logging.getLogger(__name__)


class LegalServicesGUI:
    """Main Legal Services Platform GUI with 25 fully implemented functions"""

    # =========================================================================
    # FUNCTION 1: __init__ - Initialize GUI, auth check, database init
    # =========================================================================
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

        # Use passed window (root is already a Toplevel from the launcher)
        self.window = root
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

    # =========================================================================
    # FUNCTION 2: create_widgets - Build main UI with notebook tabs
    # =========================================================================
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

    # =========================================================================
    # FUNCTION 3: _init_database - Initialize legal services database tables
    # =========================================================================
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

    # =========================================================================
    # FUNCTION 4: return_to_homescreen - Close window and return to main menu
    # =========================================================================
    def return_to_homescreen(self):
        """Close the window and return to homescreen"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")

    # =========================================================================
    # FUNCTION 5: refresh_all_data - Reload all lists and data
    # =========================================================================
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

    # =========================================================================
    # FUNCTION 6: create_case_management_tab - Tab for managing legal cases
    # =========================================================================
    def create_case_management_tab(self):
        """Create case management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.case_management", default="Case Management"))

        # Split into left (list) and right (form/details)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Case listings
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("legal.active_cases", default="Active Cases"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Filters
        filter_frame = ttk.LabelFrame(left_frame, text=_t("legal.filters", default="Filters"), padding="5")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("legal.labels.status", default="Status") + ":").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.case_status_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + [_t(f"legal.status.{s}", default=s) for s in CASE_STATUSES],
            state='readonly', width=15
        )
        self.case_status_filter.set(_t("common.all", default="All"))
        self.case_status_filter.grid(row=0, column=1, padx=2)
        self.case_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_cases())

        ttk.Label(filter_frame, text=_t("legal.labels.case_type", default="Type") + ":").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.case_type_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + [_t(f"legal.case_types.{t}", default=t) for t in CASE_TYPES],
            state='readonly', width=18
        )
        self.case_type_filter.set(_t("common.all", default="All"))
        self.case_type_filter.grid(row=0, column=3, padx=2)
        self.case_type_filter.bind('<<ComboboxSelected>>', lambda e: self.load_cases())

        # Search
        ttk.Label(filter_frame, text=_t("common.search", default="Search") + ":").grid(row=1, column=0, sticky=tk.W, padx=2, pady=5)
        self.case_search_entry = ttk.Entry(filter_frame, width=30)
        self.case_search_entry.grid(row=1, column=1, columnspan=2, padx=2, pady=5, sticky=tk.EW)
        ttk.Button(filter_frame, text=_t("common.search", default="Search"), command=self.load_cases).grid(row=1, column=3, padx=5, pady=5)

        # Cases list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for cases
        columns = ('case_number', 'client', 'type', 'status', 'priority')
        self.cases_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.cases_tree.heading('case_number', text=_t("legal.labels.case_number", default="Case #"))
        self.cases_tree.heading('client', text=_t("legal.labels.client_name", default="Client"))
        self.cases_tree.heading('type', text=_t("legal.labels.case_type", default="Type"))
        self.cases_tree.heading('status', text=_t("legal.labels.status", default="Status"))
        self.cases_tree.heading('priority', text=_t("legal.labels.priority", default="Priority"))

        self.cases_tree.column('case_number', width=150)
        self.cases_tree.column('client', width=120)
        self.cases_tree.column('type', width=100)
        self.cases_tree.column('status', width=80)
        self.cases_tree.column('priority', width=70)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=scrollbar.set)

        self.cases_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.cases_tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Action buttons for cases
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t("legal.btn.view_details", default="View Details"), command=self.view_case_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.update_case", default="Update Case"), command=self.update_case_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.close_case", default="Close Case"), command=self.close_case).pack(side=tk.LEFT, padx=2)

        # Right: Case creation form (for staff/admin)
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        if self.user_role in ['admin', 'staff', 'lawyer']:
            form_frame = ttk.LabelFrame(right_frame, text=_t("legal.create_new_case", default="Create New Case"), padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Get current user details
            user_name, user_email = self._get_user_details_from_db()
            user_id = self.current_user.get('student_id') or self.current_user.get('username', '')

            # Client Name
            ttk.Label(form_frame, text=_t("legal.labels.client_name", default="Client Name") + " *:").grid(row=0, column=0, sticky=tk.W, pady=3)
            self.client_name_entry = ttk.Entry(form_frame, width=35)
            self.client_name_entry.insert(0, user_name)
            self.client_name_entry.grid(row=0, column=1, pady=3, sticky=tk.EW)

            # Client ID
            ttk.Label(form_frame, text=_t("legal.labels.client_id", default="Client ID") + " *:").grid(row=1, column=0, sticky=tk.W, pady=3)
            self.client_id_entry = ttk.Entry(form_frame, width=35)
            self.client_id_entry.insert(0, user_id)
            self.client_id_entry.grid(row=1, column=1, pady=3, sticky=tk.EW)

            # Client Email
            ttk.Label(form_frame, text=_t("legal.labels.client_email", default="Client Email") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
            self.client_email_entry = ttk.Entry(form_frame, width=35)
            self.client_email_entry.insert(0, user_email)
            self.client_email_entry.grid(row=2, column=1, pady=3, sticky=tk.EW)

            # Case Type
            ttk.Label(form_frame, text=_t("legal.labels.case_type", default="Case Type") + " *:").grid(row=3, column=0, sticky=tk.W, pady=3)
            self.case_type_combo = ttk.Combobox(form_frame, values=CASE_TYPES, state='readonly', width=33)
            self.case_type_combo.set('consultation')
            self.case_type_combo.grid(row=3, column=1, pady=3, sticky=tk.EW)

            # Case Title
            ttk.Label(form_frame, text=_t("legal.labels.case_title", default="Case Title") + " *:").grid(row=4, column=0, sticky=tk.W, pady=3)
            self.case_title_entry = ttk.Entry(form_frame, width=35)
            self.case_title_entry.grid(row=4, column=1, pady=3, sticky=tk.EW)

            # Description
            ttk.Label(form_frame, text=_t("legal.labels.description", default="Description") + ":").grid(row=5, column=0, sticky=tk.NW, pady=3)
            self.case_desc_text = scrolledtext.ScrolledText(form_frame, width=35, height=5)
            self.case_desc_text.grid(row=5, column=1, pady=3, sticky=tk.EW)

            # Priority
            ttk.Label(form_frame, text=_t("legal.labels.priority", default="Priority") + ":").grid(row=6, column=0, sticky=tk.W, pady=3)
            self.priority_combo = ttk.Combobox(form_frame, values=['low', 'normal', 'high', 'urgent'], state='readonly', width=33)
            self.priority_combo.set('normal')
            self.priority_combo.grid(row=6, column=1, pady=3, sticky=tk.EW)

            # Assigned Lawyer
            ttk.Label(form_frame, text=_t("legal.labels.assigned_lawyer", default="Assigned Lawyer") + ":").grid(row=7, column=0, sticky=tk.W, pady=3)
            self.lawyer_entry = ttk.Entry(form_frame, width=35)
            self.lawyer_entry.grid(row=7, column=1, pady=3, sticky=tk.EW)

            form_frame.columnconfigure(1, weight=1)

            ttk.Button(
                form_frame,
                text=_t("legal.btn.create_case", default="Create Case"),
                command=self.create_new_case
            ).grid(row=8, column=1, pady=15, sticky=tk.E)

        else:
            # Student view - case details
            details_frame = ttk.LabelFrame(right_frame, text=_t("legal.case_details", default="Case Details"), padding="10")
            details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.case_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, state='disabled')
            self.case_details_text.pack(fill=tk.BOTH, expand=True)

        # Load cases
        self.load_cases()

    # =========================================================================
    # FUNCTION 7: create_new_case - Create new legal case with client intake
    # =========================================================================
    def create_new_case(self):
        """Create a new legal case"""
        try:
            # Get form values
            client_name = self.client_name_entry.get().strip()
            client_id = self.client_id_entry.get().strip()
            client_email = self.client_email_entry.get().strip()
            case_type = self.case_type_combo.get()
            case_title = self.case_title_entry.get().strip()
            case_description = self.case_desc_text.get('1.0', tk.END).strip()
            priority = self.priority_combo.get()
            assigned_lawyer = self.lawyer_entry.get().strip()

            # Validation
            if not all([client_name, client_id, case_type, case_title]):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.fill_required", default="Please fill all required fields")
                )
                return

            # Create case
            case_id = CaseManager.create_case(
                client_id=client_id,
                client_name=client_name,
                client_email=client_email,
                case_type=case_type,
                case_title=case_title,
                case_description=case_description,
                priority=priority,
                assigned_lawyer=assigned_lawyer if assigned_lawyer else None,
                created_by=self.current_user.get('username')
            )

            if case_id:
                # Get case number for display
                case = CaseManager.get_case(case_id)
                case_number = case['case_number'] if case else str(case_id)

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.case_created", default="Legal case created successfully. Case #: {case_number}").format(case_number=case_number)
                )

                # Clear form
                self.client_name_entry.delete(0, tk.END)
                self.client_id_entry.delete(0, tk.END)
                self.client_email_entry.delete(0, tk.END)
                self.case_title_entry.delete(0, tk.END)
                self.case_desc_text.delete('1.0', tk.END)
                self.lawyer_entry.delete(0, tk.END)
                self.case_type_combo.set('consultation')
                self.priority_combo.set('normal')

                # Reload cases
                self.load_cases()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.create_case_failed", default="Failed to create case")
                )

        except Exception as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("legal.errors.create_case_failed", default="Failed to create case: {error}").format(error=str(e))
            )
            print(f"Error creating case: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 8: update_case_status - Update case progress and status
    # =========================================================================
    def update_case_status(self):
        """Update the selected case status"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            # Create update dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.update_case", default="Update Case"))
            dialog.geometry("400x300")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Case: {self.selected_case['case_number']}", font=('Arial', 12, 'bold')).pack(pady=10)

            # Status
            ttk.Label(dialog, text=_t("legal.labels.status", default="Status") + ":").pack(anchor=tk.W, padx=20)
            status_combo = ttk.Combobox(dialog, values=CASE_STATUSES, state='readonly', width=30)
            status_combo.set(self.selected_case.get('status', 'open'))
            status_combo.pack(pady=5)

            # Priority
            ttk.Label(dialog, text=_t("legal.labels.priority", default="Priority") + ":").pack(anchor=tk.W, padx=20)
            priority_combo = ttk.Combobox(dialog, values=['low', 'normal', 'high', 'urgent'], state='readonly', width=30)
            priority_combo.set(self.selected_case.get('priority', 'normal'))
            priority_combo.pack(pady=5)

            # Assigned Lawyer
            ttk.Label(dialog, text=_t("legal.labels.assigned_lawyer", default="Assigned Lawyer") + ":").pack(anchor=tk.W, padx=20)
            lawyer_entry = ttk.Entry(dialog, width=33)
            lawyer_entry.insert(0, self.selected_case.get('assigned_lawyer', '') or '')
            lawyer_entry.pack(pady=5)

            def save_updates():
                updates = {
                    'status': status_combo.get(),
                    'priority': priority_combo.get(),
                    'assigned_lawyer': lawyer_entry.get().strip() or None
                }

                if CaseManager.update_case(self.selected_case['case_id'], **updates):
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.case_updated", default="Case updated successfully")
                    )
                    dialog.destroy()
                    self.load_cases()
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.update_failed", default="Failed to update case")
                    )

            ttk.Button(dialog, text=_t("common.save", default="Save"), command=save_updates).pack(pady=20)

        except Exception as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                str(e)
            )

    # =========================================================================
    # FUNCTION 9: view_case_details - Display full case information
    # =========================================================================
    def view_case_details(self):
        """Display full case details in a dialog"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case = CaseManager.get_case(self.selected_case['case_id'])
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Get related data
            consultations = ConsultationManager.get_all_consultations({'case_id': case['case_id']}) if case.get('case_id') else []
            documents = DocumentManager.get_case_documents(case['case_id']) if case.get('case_id') else []
            payments = PaymentManager.get_all_payments({'case_id': case['case_id']}) if case.get('case_id') else []

            # Create details window
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Case Details - {case['case_number']}")
            dialog.geometry("700x600")
            dialog.transient(self.window)

            # Notebook for sections
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Overview tab
            overview_tab = ttk.Frame(notebook)
            notebook.add(overview_tab, text=_t("common.overview"))

            details_text = scrolledtext.ScrolledText(overview_tab, wrap=tk.WORD)
            details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            details = f"""
CASE DETAILS
{'='*60}

Case Number:     {case['case_number']}
Status:          {case['status'].upper()}
Priority:        {case['priority'].upper()}

CLIENT INFORMATION
{'-'*40}
Name:            {case['client_name']}
ID:              {case['client_id']}
Email:           {case.get('client_email', 'N/A')}

CASE INFORMATION
{'-'*40}
Type:            {case['case_type']}
Title:           {case['case_title']}

Description:
{case.get('case_description', 'No description provided')}

ASSIGNMENT
{'-'*40}
Assigned Lawyer: {case.get('assigned_lawyer', 'Not assigned')}
Created By:      {case.get('created_by', 'Unknown')}
Created At:      {case.get('created_at', 'Unknown')}
Updated At:      {case.get('updated_at', 'Unknown')}

FINANCIAL SUMMARY
{'-'*40}
Total Fees:      GBP {case.get('total_fees', 0):.2f}
Amount Paid:     GBP {case.get('amount_paid', 0):.2f}
Balance Due:     GBP {(case.get('total_fees', 0) - case.get('amount_paid', 0)):.2f}
"""
            details_text.insert('1.0', details)
            details_text.config(state='disabled')

            # Consultations tab
            consult_tab = ttk.Frame(notebook)
            notebook.add(consult_tab, text=f"Consultations ({len(consultations)})")

            consult_text = scrolledtext.ScrolledText(consult_tab, wrap=tk.WORD)
            consult_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if consultations:
                consult_info = "CONSULTATIONS\n" + "="*60 + "\n\n"
                for c in consultations:
                    consult_info += f"Date: {c['scheduled_date']} at {c['scheduled_time']}\n"
                    consult_info += f"Type: {c['consultation_type']} | Duration: {c['duration_minutes']} min\n"
                    consult_info += f"Fee: GBP {c['fee']:.2f} | Payment: {c['payment_status']}\n"
                    consult_info += f"Status: {c['status']}\n"
                    consult_info += "-"*40 + "\n\n"
            else:
                consult_info = "No consultations scheduled for this case."
            consult_text.insert('1.0', consult_info)
            consult_text.config(state='disabled')

            # Documents tab
            docs_tab = ttk.Frame(notebook)
            notebook.add(docs_tab, text=f"Documents ({len(documents)})")

            docs_text = scrolledtext.ScrolledText(docs_tab, wrap=tk.WORD)
            docs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if documents:
                docs_info = "DOCUMENTS\n" + "="*60 + "\n\n"
                for d in documents:
                    docs_info += f"Name: {d['document_name']}\n"
                    docs_info += f"Type: {d['document_type']} | Version: {d['version']}\n"
                    docs_info += f"Created: {d['created_at']} by {d.get('created_by', 'Unknown')}\n"
                    docs_info += "-"*40 + "\n\n"
            else:
                docs_info = "No documents attached to this case."
            docs_text.insert('1.0', docs_info)
            docs_text.config(state='disabled')

            # Payments tab
            payments_tab = ttk.Frame(notebook)
            notebook.add(payments_tab, text=f"Payments ({len(payments)})")

            payments_text = scrolledtext.ScrolledText(payments_tab, wrap=tk.WORD)
            payments_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if payments:
                payments_info = "PAYMENT HISTORY\n" + "="*60 + "\n\n"
                for p in payments:
                    payments_info += f"Date: {p['created_at']}\n"
                    payments_info += f"Amount: GBP {p['amount']:.2f} | Method: {p['payment_method']}\n"
                    payments_info += f"Type: {p['payment_type']} | Status: {p['status']}\n"
                    payments_info += f"Reference: {p['transaction_reference']}\n"
                    payments_info += "-"*40 + "\n\n"
            else:
                payments_info = "No payments recorded for this case."
            payments_text.insert('1.0', payments_info)
            payments_text.config(state='disabled')

            # Close button
            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error viewing case details: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 10: close_case - Close case and generate final report
    # =========================================================================
    def close_case(self):
        """Close the selected case"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        if self.selected_case.get('status') == 'closed':
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.case_already_closed", default="This case is already closed")
            )
            return

        # Confirm closure
        if not messagebox.askyesno(
            _t("common.confirm", default="Confirm"),
            _t("legal.confirm.close_case", default="Are you sure you want to close case {case_number}?").format(
                case_number=self.selected_case['case_number']
            )
        ):
            return

        try:
            if CaseManager.close_case(self.selected_case['case_id'], closed_by=self.current_user.get('username')):
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.case_closed", default="Case closed successfully")
                )
                self.load_cases()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.close_failed", default="Failed to close case")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 11: create_consultations_tab - Tab for appointment scheduling
    # =========================================================================
    def create_consultations_tab(self):
        """Create consultations tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.consultations", default="Consultations"))

        # Split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Consultations list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("legal.scheduled_consultations", default="Scheduled Consultations"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Filter frame
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("legal.labels.status", default="Status") + ":").pack(side=tk.LEFT, padx=2)
        self.consult_status_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + CONSULTATION_STATUSES,
            state='readonly', width=12
        )
        self.consult_status_filter.set(_t("common.all", default="All"))
        self.consult_status_filter.pack(side=tk.LEFT, padx=2)
        self.consult_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_consultations())

        ttk.Button(filter_frame, text=_t("common.refresh", default="Refresh"), command=self.load_consultations).pack(side=tk.RIGHT, padx=5)

        # Consultations treeview
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('id', 'client', 'date', 'time', 'type', 'fee', 'payment', 'status')
        self.consult_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.consult_tree.heading('id', text='ID')
        self.consult_tree.heading('client', text=_t("legal.labels.client_name", default="Client"))
        self.consult_tree.heading('date', text=_t("legal.labels.scheduled_date", default="Date"))
        self.consult_tree.heading('time', text=_t("legal.labels.scheduled_time", default="Time"))
        self.consult_tree.heading('type', text=_t("legal.labels.case_type", default="Type"))
        self.consult_tree.heading('fee', text=_t("legal.labels.fee", default="Fee"))
        self.consult_tree.heading('payment', text=_t("legal.labels.payment_status", default="Payment"))
        self.consult_tree.heading('status', text=_t("legal.labels.status", default="Status"))

        self.consult_tree.column('id', width=40)
        self.consult_tree.column('client', width=100)
        self.consult_tree.column('date', width=90)
        self.consult_tree.column('time', width=60)
        self.consult_tree.column('type', width=100)
        self.consult_tree.column('fee', width=70)
        self.consult_tree.column('payment', width=80)
        self.consult_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.consult_tree.yview)
        self.consult_tree.configure(yscrollcommand=scrollbar.set)

        self.consult_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.consult_tree.bind('<<TreeviewSelect>>', self.on_consultation_select)

        # Action buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t("legal.btn.process_payment", default="Process Payment"), command=self.process_consultation_payment).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.send_receipt", default="Send Receipt"), command=self.send_consultation_receipt).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.cancel_consultation", default="Cancel"), command=self.cancel_consultation).pack(side=tk.LEFT, padx=2)

        # Right: Schedule new consultation
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        form_frame = ttk.LabelFrame(right_frame, text=_t("legal.btn.schedule_consultation", default="Schedule Consultation"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Get current user details
        user_name, user_email = self._get_user_details_from_db()
        user_id = self.current_user.get('student_id') or self.current_user.get('username', '')

        # Client Name
        ttk.Label(form_frame, text=_t("legal.labels.client_name", default="Client Name") + " *:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.consult_client_name = ttk.Entry(form_frame, width=30)
        self.consult_client_name.insert(0, user_name)
        self.consult_client_name.grid(row=0, column=1, pady=3, sticky=tk.EW)

        # Client ID
        ttk.Label(form_frame, text=_t("legal.labels.client_id", default="Client ID") + " *:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.consult_client_id = ttk.Entry(form_frame, width=30)
        self.consult_client_id.insert(0, user_id)
        self.consult_client_id.grid(row=1, column=1, pady=3, sticky=tk.EW)

        # Client Email
        ttk.Label(form_frame, text=_t("legal.labels.client_email", default="Client Email") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.consult_client_email = ttk.Entry(form_frame, width=30)
        self.consult_client_email.insert(0, user_email)
        self.consult_client_email.grid(row=2, column=1, pady=3, sticky=tk.EW)

        # Consultation Type
        ttk.Label(form_frame, text=_t("legal.labels.consultation_type", default="Type") + " *:").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.consult_type_combo = ttk.Combobox(form_frame, values=CASE_TYPES, state='readonly', width=28)
        self.consult_type_combo.set('consultation')
        self.consult_type_combo.grid(row=3, column=1, pady=3, sticky=tk.EW)
        self.consult_type_combo.bind('<<ComboboxSelected>>', self.update_fee_display)

        # Date
        ttk.Label(form_frame, text=_t("legal.labels.scheduled_date", default="Date") + " *:").grid(row=4, column=0, sticky=tk.W, pady=3)
        self.consult_date = ttk.Entry(form_frame, width=30)
        self.consult_date.insert(0, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
        self.consult_date.grid(row=4, column=1, pady=3, sticky=tk.EW)

        # Time
        ttk.Label(form_frame, text=_t("legal.labels.scheduled_time", default="Time") + " *:").grid(row=5, column=0, sticky=tk.W, pady=3)
        self.consult_time = ttk.Combobox(form_frame, values=[
            '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30'
        ], width=28)
        self.consult_time.set('10:00')
        self.consult_time.grid(row=5, column=1, pady=3, sticky=tk.EW)

        # Duration
        ttk.Label(form_frame, text=_t("legal.labels.duration", default="Duration") + ":").grid(row=6, column=0, sticky=tk.W, pady=3)
        self.consult_duration = ttk.Combobox(form_frame, values=['30', '60', '90', '120'], state='readonly', width=28)
        self.consult_duration.set('30')
        self.consult_duration.grid(row=6, column=1, pady=3, sticky=tk.EW)
        self.consult_duration.bind('<<ComboboxSelected>>', self.update_fee_display)

        # Lawyer
        ttk.Label(form_frame, text=_t("legal.labels.assigned_lawyer", default="Lawyer") + ":").grid(row=7, column=0, sticky=tk.W, pady=3)
        self.consult_lawyer = ttk.Entry(form_frame, width=30)
        self.consult_lawyer.grid(row=7, column=1, pady=3, sticky=tk.EW)

        # Fee display
        ttk.Label(form_frame, text=_t("legal.labels.fee", default="Fee") + ":").grid(row=8, column=0, sticky=tk.W, pady=3)
        self.fee_display_var = tk.StringVar(value="GBP 25.00")
        ttk.Label(form_frame, textvariable=self.fee_display_var, font=('Arial', 11, 'bold')).grid(row=8, column=1, sticky=tk.W, pady=3)

        # Notes
        ttk.Label(form_frame, text=_t("legal.labels.notes", default="Notes") + ":").grid(row=9, column=0, sticky=tk.NW, pady=3)
        self.consult_notes = scrolledtext.ScrolledText(form_frame, width=30, height=3)
        self.consult_notes.grid(row=9, column=1, pady=3, sticky=tk.EW)

        form_frame.columnconfigure(1, weight=1)

        ttk.Button(
            form_frame,
            text=_t("legal.btn.schedule_consultation", default="Schedule Consultation"),
            command=self.schedule_consultation
        ).grid(row=10, column=1, pady=15, sticky=tk.E)

        # Load consultations
        self.load_consultations()

    # =========================================================================
    # FUNCTION 12: schedule_consultation - Book legal consultation with fee
    # =========================================================================
    def schedule_consultation(self):
        """Schedule a new consultation"""
        try:
            client_name = self.consult_client_name.get().strip()
            client_id = self.consult_client_id.get().strip()
            client_email = self.consult_client_email.get().strip()
            consult_type = self.consult_type_combo.get()
            scheduled_date = self.consult_date.get().strip()
            scheduled_time = self.consult_time.get().strip()
            duration = int(self.consult_duration.get())
            lawyer_name = self.consult_lawyer.get().strip()
            notes = self.consult_notes.get('1.0', tk.END).strip()

            # Validation
            if not all([client_name, client_id, consult_type, scheduled_date, scheduled_time]):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.fill_required", default="Please fill all required fields")
                )
                return

            # Validate date format
            try:
                datetime.strptime(scheduled_date, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.invalid_date", default="Please enter date in YYYY-MM-DD format")
                )
                return

            consultation_id = ConsultationManager.schedule_consultation(
                client_id=client_id,
                client_name=client_name,
                client_email=client_email,
                consultation_type=consult_type,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                duration_minutes=duration,
                lawyer_name=lawyer_name if lawyer_name else None,
                notes=notes
            )

            if consultation_id:
                fee = calculate_service_fee(consult_type, duration)
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.consultation_scheduled", default="Consultation scheduled for {date} at {time}. Fee: GBP {fee:.2f}").format(
                        date=scheduled_date, time=scheduled_time, fee=fee
                    )
                )

                # Clear form
                self.consult_client_name.delete(0, tk.END)
                self.consult_client_id.delete(0, tk.END)
                self.consult_client_email.delete(0, tk.END)
                self.consult_lawyer.delete(0, tk.END)
                self.consult_notes.delete('1.0', tk.END)

                self.load_consultations()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.schedule_failed", default="Failed to schedule consultation")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error scheduling consultation: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 13: process_consultation_payment - Process payment via finance
    # =========================================================================
    def process_consultation_payment(self):
        """Process payment for selected consultation"""
        if not self.selected_consultation:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
            )
            return

        if self.selected_consultation.get('payment_status') == 'paid':
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.already_paid", default="This consultation has already been paid")
            )
            return

        try:
            consultation = ConsultationManager.get_consultation(self.selected_consultation['consultation_id'])
            if not consultation:
                messagebox.showerror(_t("common.error", default="Error"), "Consultation not found")
                return

            fee = consultation.get('fee', 0)
            client_id = consultation['client_id']

            # Check student account balance
            student_balance = get_student_finance_account_balance(client_id)

            # Payment method dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.process_payment", default="Process Payment"))
            dialog.geometry("400x350")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Client: {consultation['client_name']}", font=('Arial', 11)).pack(pady=5)
            ttk.Label(dialog, text=f"Amount Due: £{fee:.2f}", font=('Arial', 12, 'bold')).pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

            # Payment method radio buttons
            payment_method_var = tk.StringVar(value="Cash")
            methods_frame = ttk.Frame(dialog)
            methods_frame.pack(pady=5)

            ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
            ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

            # Student Account option with balance display
            student_frame = ttk.Frame(methods_frame)
            student_frame.pack(anchor=tk.W)
            ttk.Radiobutton(student_frame, text=_t("common.payment_methods.student_account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
            balance_text = f" (Balance: £{student_balance:.2f})" if student_balance else " (No account)"
            ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

            def confirm_payment():
                payment_method = payment_method_var.get()

                # Handle Student Account payment
                if payment_method == "Student Account":
                    if student_balance < fee:
                        messagebox.showerror(
                            _t("common.error", default="Error"),
                            f"Insufficient balance. Current balance: £{student_balance:.2f}"
                        )
                        return
                    # Process student account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=client_id,
                        amount=fee,
                        description=f"Legal consultation - {consultation['consultation_type']}",
                        transaction_source="LegalServices",
                        transaction_ref=str(consultation['consultation_id']),
                        processed_by=self.current_user.get('username', 'System')
                    )
                    if not payment_result.get('success'):
                        messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                        return

                payment_id = PaymentManager.record_payment(
                    client_id=client_id,
                    client_email=consultation.get('client_email', ''),
                    amount=fee,
                    payment_type='consultation_fee',
                    payment_method=payment_method,
                    consultation_id=consultation['consultation_id'],
                    case_id=consultation.get('case_id'),
                    processed_by=self.current_user.get('username')
                )

                if payment_id:
                    # Record revenue in central finance system
                    record_payment_to_finance(
                        student_id=client_id,
                        amount=fee,
                        payment_method=payment_method,
                        transaction_source='LegalServices',
                        transaction_ref=f"CONSULT-{consultation['consultation_id']}",
                        notes=f"Legal consultation fee - {consultation['consultation_type']}",
                        created_by=self.current_user.get('username')
                    )
                    logger.info(f"Revenue recorded: £{fee:.2f} for consultation {consultation['consultation_id']}")

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.payment_processed", default="Payment of GBP {amount:.2f} processed successfully").format(amount=fee)
                    )
                    dialog.destroy()
                    self.load_consultations()

                    # Ask to send receipt
                    client_email = consultation.get('client_email', '')
                    if client_email and '@' in client_email and messagebox.askyesno(
                        _t("common.confirm", default="Confirm"),
                        _t("legal.confirm.send_receipt", default="Send receipt to {email}?").format(email=client_email)
                    ):
                        self.send_consultation_receipt(consultation_id=consultation['consultation_id'])
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.payment_failed", default="Payment processing failed")
                    )

            ttk.Button(dialog, text=_t("legal.btn.process_payment", default="Process Payment"), command=confirm_payment).pack(pady=20)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error processing payment: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 14: send_consultation_receipt - Email receipt to client
    # =========================================================================
    def send_consultation_receipt(self, consultation_id: int = None):
        """Send email receipt to client after payment"""
        if consultation_id is None:
            if not self.selected_consultation:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
                )
                return
            consultation_id = self.selected_consultation['consultation_id']

        try:
            consultation = ConsultationManager.get_consultation(consultation_id)
            if not consultation:
                messagebox.showerror(_t("common.error", default="Error"), "Consultation not found")
                return

            if consultation.get('payment_status') != 'paid':
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.payment_required", default="Please process payment before sending receipt")
                )
                return

            client_email = consultation.get('client_email', '')
            if not client_email or '@' not in client_email:
                logger.info(f"Receipt email skipped - invalid email format: {client_email}")
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.no_email", default="Client email not available")
                )
                return

            # Get payment details
            payments = PaymentManager.get_all_payments({'consultation_id': consultation_id})
            payment = payments[0] if payments else None

            if not payment:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.no_payment_found", default="No payment record found")
                )
                return

            # Generate receipt - try to use template
            subject = None
            receipt_body = None
            if render_template:
                subject, receipt_body = render_template('commerce/legal/payment_receipt', {
                    'client_name': consultation['client_name'],
                    'receipt_number': payment['transaction_reference'],
                    'payment_date': payment['created_at'][:10],
                    'payment_method': payment['payment_method'],
                    'consultation_type': consultation['consultation_type'].replace('_', ' ').title(),
                    'scheduled_date': consultation['scheduled_date'],
                    'scheduled_time': consultation['scheduled_time'],
                    'duration': consultation['duration_minutes'],
                    'lawyer_name': consultation.get('lawyer_name', 'To be assigned'),
                    'service_fee': f"GBP {consultation['fee']:.2f}",
                    'amount_paid': f"GBP {payment['amount']:.2f}"
                })

            # Fallback if template not found
            if not subject or not receipt_body:
                receipt_body = f"""
Dear {consultation['client_name']},

Thank you for your payment. This email confirms your legal consultation payment.

{'='*60}
                    PAYMENT RECEIPT
{'='*60}

Receipt Number:     {payment['transaction_reference']}
Payment Date:       {payment['created_at'][:10]}
Payment Method:     {payment['payment_method']}

{'='*60}
CONSULTATION DETAILS
{'='*60}

Consultation Type:  {consultation['consultation_type'].replace('_', ' ').title()}
Scheduled Date:     {consultation['scheduled_date']}
Scheduled Time:     {consultation['scheduled_time']}
Duration:           {consultation['duration_minutes']} minutes
Lawyer:             {consultation.get('lawyer_name', 'To be assigned')}

{'='*60}
PAYMENT DETAILS
{'='*60}

Service Fee:        GBP {consultation['fee']:.2f}
Amount Paid:        GBP {payment['amount']:.2f}

{'='*60}

If you need to reschedule or cancel your consultation, please contact us
at least 24 hours in advance.

Thank you for using University Legal Aid Center.

Best regards,
University Legal Services
legal@university.edu
"""
                subject = f"Legal Services Receipt - {payment['transaction_reference']}"

            if EMAIL_AVAILABLE:
                result = send_email(
                    recipient_email=client_email,
                    subject=subject,
                    body=receipt_body
                )

                if result:
                    PaymentManager.mark_receipt_sent(payment['payment_id'])
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.receipt_sent", default="Receipt sent to {email}").format(email=client_email)
                    )
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.email_failed", default="Failed to send email")
                    )
            else:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.email_unavailable", default="Email service not available. Receipt not sent.")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error sending receipt: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 15: cancel_consultation - Cancel and process refund if applicable
    # =========================================================================
    def cancel_consultation(self):
        """Cancel a scheduled consultation"""
        if not self.selected_consultation:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
            )
            return

        if self.selected_consultation.get('status') in ['cancelled', 'completed']:
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.cannot_cancel", default="This consultation cannot be cancelled")
            )
            return

        reason = simpledialog.askstring(
            _t("legal.btn.cancel_consultation", default="Cancel Consultation"),
            _t("legal.prompts.cancel_reason", default="Enter cancellation reason:")
        )

        if reason is None:
            return

        try:
            # Check if refund is needed
            if self.selected_consultation.get('payment_status') == 'paid':
                if messagebox.askyesno(
                    _t("common.confirm", default="Confirm"),
                    _t("legal.confirm.process_refund", default="This consultation was paid. Process refund?")
                ):
                    # Get payment and process refund
                    payments = PaymentManager.get_all_payments({'consultation_id': self.selected_consultation['consultation_id']})
                    if payments:
                        PaymentManager.process_refund(
                            payments[0]['payment_id'],
                            reason=reason,
                            processed_by=self.current_user.get('username')
                        )

            if ConsultationManager.cancel_consultation(self.selected_consultation['consultation_id'], reason):
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.consultation_cancelled", default="Consultation cancelled successfully")
                )
                self.load_consultations()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.cancel_failed", default="Failed to cancel consultation")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 16: create_documents_tab - Tab for legal document management
    # =========================================================================
    def create_documents_tab(self):
        """Create documents tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.documents", default="Documents"))

        # Top section: Case selector and document list
        top_frame = ttk.Frame(tab)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Case selector
        selector_frame = ttk.Frame(top_frame)
        selector_frame.pack(fill=tk.X, pady=5)

        ttk.Label(selector_frame, text=_t("legal.select_case", default="Select Case") + ":").pack(side=tk.LEFT, padx=5)
        self.doc_case_combo = ttk.Combobox(selector_frame, state='readonly', width=40)
        self.doc_case_combo.pack(side=tk.LEFT, padx=5)
        self.doc_case_combo.bind('<<ComboboxSelected>>', self.load_case_documents)

        ttk.Button(selector_frame, text=_t("common.refresh", default="Refresh"), command=self.refresh_document_cases).pack(side=tk.LEFT, padx=5)

        # Documents list
        list_frame = ttk.LabelFrame(top_frame, text=_t("legal.case_documents", default="Case Documents"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('id', 'name', 'type', 'version', 'created_by', 'created_at')
        self.docs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        self.docs_tree.heading('id', text='ID')
        self.docs_tree.heading('name', text=_t("legal.labels.document_name", default="Document Name"))
        self.docs_tree.heading('type', text=_t("legal.labels.document_type", default="Type"))
        self.docs_tree.heading('version', text=_t("legal.labels.version", default="Version"))
        self.docs_tree.heading('created_by', text=_t("legal.labels.created_by", default="Created By"))
        self.docs_tree.heading('created_at', text=_t("legal.labels.created_at", default="Created At"))

        self.docs_tree.column('id', width=40)
        self.docs_tree.column('name', width=200)
        self.docs_tree.column('type', width=120)
        self.docs_tree.column('version', width=60)
        self.docs_tree.column('created_by', width=100)
        self.docs_tree.column('created_at', width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        self.docs_tree.configure(yscrollcommand=scrollbar.set)

        self.docs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom: Action buttons and forms
        bottom_frame = ttk.Frame(tab)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)

        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("legal.btn.generate_document", default="Generate Document"), command=self.generate_legal_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.upload_document", default="Upload Document"), command=self.upload_case_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.view_history", default="View History"), command=self.view_document_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.generate_invoice", default="Generate Invoice"), command=self.generate_invoice).pack(side=tk.RIGHT, padx=5)

        # Initialize case list
        self.refresh_document_cases()

    # =========================================================================
    # FUNCTION 17: generate_legal_document - Create legal documents from templates
    # =========================================================================
    def generate_legal_document(self):
        """Generate a legal document from template"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Document type dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.generate_document", default="Generate Document"))
            dialog.geometry("450x400")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Case: {case['case_number']}", font=('Arial', 11, 'bold')).pack(pady=10)

            ttk.Label(dialog, text=_t("legal.labels.document_type", default="Document Type") + ":").pack(pady=5)
            doc_types = ['Engagement Letter', 'Legal Opinion', 'Case Summary', 'Client Agreement', 'Cease and Desist', 'Demand Letter', 'Affidavit', 'Power of Attorney']
            type_combo = ttk.Combobox(dialog, values=doc_types, state='readonly', width=35)
            type_combo.set('Engagement Letter')
            type_combo.pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.document_name", default="Document Name") + ":").pack(pady=5)
            name_entry = ttk.Entry(dialog, width=38)
            name_entry.insert(0, f"{case['case_number']}_engagement_letter")
            name_entry.pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.additional_notes", default="Additional Notes") + ":").pack(pady=5)
            notes_text = scrolledtext.ScrolledText(dialog, width=40, height=6)
            notes_text.pack(pady=5)

            def generate():
                doc_type = type_combo.get()
                doc_name = name_entry.get().strip()
                notes = notes_text.get('1.0', tk.END).strip()

                if not doc_name:
                    messagebox.showwarning(_t("common.warning", default="Warning"), "Please enter a document name")
                    return

                # Generate document content based on type
                content = self._generate_document_content(case, doc_type, notes)

                doc_id = DocumentManager.create_document(
                    case_id=case['case_id'],
                    document_type=doc_type,
                    document_name=doc_name,
                    file_content=content,
                    created_by=self.current_user.get('username'),
                    notes=notes
                )

                if doc_id:
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.document_generated", default="Document generated successfully")
                    )
                    dialog.destroy()
                    self.load_case_documents(None)
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Failed to generate document")

            ttk.Button(dialog, text=_t("legal.btn.generate_document", default="Generate"), command=generate).pack(pady=20)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error generating document: {traceback.format_exc()}")

    def _generate_document_content(self, case: Dict, doc_type: str, notes: str) -> str:
        """Generate document content based on type"""
        date = datetime.now().strftime('%Y-%m-%d')

        if doc_type == 'Engagement Letter':
            return f"""
UNIVERSITY LEGAL AID CENTER
ENGAGEMENT LETTER

Date: {date}
Case Number: {case['case_number']}

Dear {case['client_name']},

This letter confirms our engagement to provide legal services regarding:

Case Type: {case['case_type'].replace('_', ' ').title()}
Matter: {case['case_title']}

SCOPE OF SERVICES:
{case.get('case_description', 'To be discussed during initial consultation.')}

We look forward to working with you on this matter.

Sincerely,
University Legal Aid Center

{'Additional Notes: ' + notes if notes else ''}
"""
        elif doc_type == 'Case Summary':
            return f"""
CASE SUMMARY

Case Number: {case['case_number']}
Date: {date}

CLIENT INFORMATION:
Name: {case['client_name']}
ID: {case['client_id']}
Email: {case.get('client_email', 'N/A')}

CASE DETAILS:
Type: {case['case_type'].replace('_', ' ').title()}
Title: {case['case_title']}
Priority: {case['priority']}
Status: {case['status']}
Assigned Lawyer: {case.get('assigned_lawyer', 'Not assigned')}

DESCRIPTION:
{case.get('case_description', 'No description provided.')}

{'NOTES: ' + notes if notes else ''}

Prepared by: {self.current_user.get('username', 'Legal Staff')}
"""
        else:
            return f"""
{doc_type.upper()}

Case Number: {case['case_number']}
Client: {case['client_name']}
Date: {date}

[Document content to be completed]

{notes if notes else ''}

Prepared by: University Legal Aid Center
"""

    # =========================================================================
    # FUNCTION 18: upload_case_document - Upload supporting documents to case
    # =========================================================================
    def upload_case_document(self):
        """Upload a document to the selected case"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # File selection
            file_path = filedialog.askopenfilename(
                title=_t("legal.btn.upload_document", default="Select Document"),
                filetypes=[
                    ("All Files", "*.*"),
                    ("PDF Files", "*.pdf"),
                    ("Word Documents", "*.docx"),
                    ("Text Files", "*.txt"),
                    ("Images", "*.png *.jpg *.jpeg")
                ]
            )

            if not file_path:
                return

            file_name = os.path.basename(file_path)

            # Ask for document type
            doc_type = simpledialog.askstring(
                _t("legal.labels.document_type", default="Document Type"),
                _t("legal.prompts.document_type", default="Enter document type (e.g., Evidence, Contract, ID):"),
                initialvalue="Supporting Document"
            )

            if not doc_type:
                return

            doc_id = DocumentManager.create_document(
                case_id=case['case_id'],
                document_type=doc_type,
                document_name=file_name,
                file_path=file_path,
                created_by=self.current_user.get('username')
            )

            if doc_id:
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.document_uploaded", default="Document uploaded successfully")
                )
                self.load_case_documents(None)
            else:
                messagebox.showerror(_t("common.error", default="Error"), "Failed to upload document")

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error uploading document: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 19: view_document_history - View document revision history
    # =========================================================================
    def view_document_history(self):
        """View version history for a document"""
        selected = self.docs_tree.selection()
        if not selected:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_document_selected", default="Please select a document first")
            )
            return

        try:
            item = self.docs_tree.item(selected[0])
            doc_id = item['values'][0]
            doc_name = item['values'][1]

            case_selection = self.doc_case_combo.get()
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)

            if not case:
                return

            history = DocumentManager.get_document_history(doc_name, case['case_id'])

            if not history:
                messagebox.showinfo(
                    _t("common.info", default="Info"),
                    _t("legal.messages.no_history", default="No version history available")
                )
                return

            # Show history dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Document History - {doc_name}")
            dialog.geometry("500x400")
            dialog.transient(self.window)

            ttk.Label(dialog, text=f"Version History for: {doc_name}", font=('Arial', 11, 'bold')).pack(pady=10)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            history_text = ""
            for doc in history:
                history_text += f"""
Version {doc['version']}
{'='*40}
Created: {doc['created_at']}
Created By: {doc.get('created_by', 'Unknown')}
Type: {doc['document_type']}
Notes: {doc.get('notes', 'None')}

"""

            text.insert('1.0', history_text)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 20: calculate_service_fees - Calculate fees based on service type
    # =========================================================================
    def calculate_service_fees(self, service_type: str, duration: int = 30) -> float:
        """Calculate fees for a given service type"""
        return calculate_service_fee(service_type, duration)

    def update_fee_display(self, event=None):
        """Update the fee display based on selected type and duration"""
        try:
            service_type = self.consult_type_combo.get()
            duration = int(self.consult_duration.get())
            fee = self.calculate_service_fees(service_type, duration)
            self.fee_display_var.set(f"GBP {fee:.2f}")
        except Exception:
            self.fee_display_var.set("GBP 25.00")

    # =========================================================================
    # FUNCTION 21: record_payment_transaction - Record payment in finance system
    # =========================================================================
    def record_payment_transaction(self, client_id: str, amount: float, description: str, payment_method: str):
        """Record payment transaction in finance system to add to revenue"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Try to record in the main payments table
                try:
                    cursor.execute('''
                        INSERT INTO payments
                        (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                    ''', (client_id, amount, payment_method, datetime.now().strftime('%Y-%m-%d'),
                          description, self.current_user.get('username'), datetime.now().isoformat()))
                except Exception:
                    pass  # payments table may not exist

                # Try to update student finance account
                try:
                    cursor.execute('''
                        SELECT account_id FROM student_finance_accounts WHERE student_id = ?
                    ''', (client_id,))
                    account = cursor.fetchone()

                    if account:
                        cursor.execute('''
                            INSERT INTO student_finance_transactions
                            (account_id, student_id, transaction_type, amount, description, processed_by, created_at)
                            VALUES (?, ?, 'legal_service', ?, ?, ?, ?)
                        ''', (account[0], client_id, amount, description,
                              self.current_user.get('username'), datetime.now().isoformat()))
                except Exception:
                    pass  # Finance tables may not exist

            log_activity('record_payment', 'legal_services', details={
                'client_id': client_id,
                'amount': amount,
                'description': description
            })

            return True

        except Exception as e:
            print(f"Error recording payment transaction: {e}")
            return False

    # =========================================================================
    # FUNCTION 22: generate_invoice - Generate invoice for legal services
    # =========================================================================
    def generate_invoice(self):
        """Generate invoice for the selected case"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Get payments and services
            payments = PaymentManager.get_all_payments({'case_id': case['case_id']})
            consultations = ConsultationManager.get_all_consultations({'case_id': case['case_id']}) if case.get('case_id') else []

            services = []
            for c in consultations:
                services.append(f"{c['consultation_type']} consultation ({c['duration_minutes']} min) - GBP {c['fee']:.2f}")

            invoice_text = generate_invoice_text(case, payments, services if services else ['Legal services as per agreement'])

            # Show invoice dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Invoice - {case['case_number']}")
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text.insert('1.0', invoice_text)
            text.config(state='disabled')

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, pady=10)

            def save_invoice():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                    initialfilename=f"invoice_{case['case_number']}.txt"
                )
                if file_path:
                    with open(file_path, 'w') as f:
                        f.write(invoice_text)
                    messagebox.showinfo(_t("common.success", default="Success"), "Invoice saved successfully")

            def email_invoice():
                client_email = case.get('client_email', '')
                if client_email and '@' in client_email:
                    if EMAIL_AVAILABLE:
                        result = send_email(
                            recipient_email=client_email,
                            subject=f"Invoice - {case['case_number']}",
                            body=invoice_text
                        )
                        if result:
                            logger.info(f"Invoice email sent to {client_email}")
                            messagebox.showinfo(_t("common.success", default="Success"), "Invoice sent successfully")
                        else:
                            messagebox.showerror(_t("common.error", default="Error"), "Failed to send invoice")
                    else:
                        messagebox.showwarning(_t("common.warning", default="Warning"), "Email service not available")
                else:
                    logger.info(f"Invoice email skipped - invalid email format: {client_email}")
                    messagebox.showwarning(_t("common.warning", default="Warning"), "No valid client email available")

            ttk.Button(btn_frame, text=_t("common.save_invoice"), command=save_invoice).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Email Invoice", command=email_invoice).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text=_t("common.close", default="Close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error generating invoice: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 23: create_reports_tab - Tab for reports and analytics
    # =========================================================================
    def create_reports_tab(self):
        """Create reports and analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.reports", default="Reports & Analytics"))

        # Report options
        options_frame = ttk.LabelFrame(tab, text=_t("legal.reports.title", default="Report Options"), padding="10")
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        ttk.Label(options_frame, text=_t("legal.labels.start_date", default="Start Date") + ":").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.report_start = ttk.Entry(options_frame, width=15)
        self.report_start.insert(0, (datetime.now().replace(day=1)).strftime('%Y-%m-%d'))
        self.report_start.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(options_frame, text=_t("legal.labels.end_date", default="End Date") + ":").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.report_end = ttk.Entry(options_frame, width=15)
        self.report_end.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.report_end.grid(row=0, column=3, padx=5, pady=5)

        # Report type
        ttk.Label(options_frame, text=_t("legal.labels.report_type", default="Report Type") + ":").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.report_type = ttk.Combobox(options_frame, values=[
            _t("legal.reports.monthly_summary", default="Monthly Summary"),
            _t("legal.reports.case_statistics", default="Case Statistics"),
            _t("legal.reports.revenue_report", default="Revenue Report"),
            _t("legal.reports.lawyer_performance", default="Lawyer Performance")
        ], state='readonly', width=20)
        self.report_type.set(_t("legal.reports.monthly_summary", default="Monthly Summary"))
        self.report_type.grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(options_frame, text=_t("legal.btn.generate_report", default="Generate Report"), command=self.generate_admin_report).grid(row=0, column=6, padx=10, pady=5)

        # Report display
        report_frame = ttk.LabelFrame(tab, text=_t("legal.report_output", default="Report Output"), padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD, font=('Courier', 10))
        self.report_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("legal.btn.email_report", default="Email Report to Admin"), command=self.email_admin_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.save", default="Save Report"), command=self.save_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear", default="Clear"), command=lambda: self.report_text.delete('1.0', tk.END)).pack(side=tk.RIGHT, padx=5)

    # =========================================================================
    # FUNCTION 24: generate_admin_report - Generate comprehensive admin report
    # =========================================================================
    def generate_admin_report(self):
        """Generate comprehensive report for admin"""
        try:
            start_date = self.report_start.get().strip()
            end_date = self.report_end.get().strip()
            report_type = self.report_type.get()

            # Clear previous report
            self.report_text.delete('1.0', tk.END)

            # Get statistics
            case_stats = CaseManager.get_case_statistics()
            revenue_stats = PaymentManager.get_revenue_statistics(start_date, end_date)
            upcoming = ConsultationManager.get_upcoming_consultations(7)

            report = f"""
{'='*70}
            UNIVERSITY LEGAL AID CENTER - {report_type.upper()}
{'='*70}

Report Period: {start_date} to {end_date}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Generated By: {self.current_user.get('username', 'Admin')}

{'='*70}
                        CASE STATISTICS
{'='*70}

Total Cases: {case_stats.get('total_cases', 0)}
Cases This Month: {case_stats.get('cases_this_month', 0)}

By Status:
"""
            for status, count in case_stats.get('by_status', {}).items():
                report += f"  - {status.title()}: {count}\n"

            report += f"""
By Type:
"""
            for case_type, count in case_stats.get('by_type', {}).items():
                report += f"  - {case_type.replace('_', ' ').title()}: {count}\n"

            report += f"""
{'='*70}
                        FINANCIAL SUMMARY
{'='*70}

Total Revenue:        GBP {revenue_stats.get('total_revenue', 0):.2f}
Total Refunds:        GBP {revenue_stats.get('total_refunds', 0):.2f}
Net Revenue:          GBP {revenue_stats.get('net_revenue', 0):.2f}

By Payment Type:
"""
            for ptype, data in revenue_stats.get('by_payment_type', {}).items():
                report += f"  - {ptype.replace('_', ' ').title()}: GBP {data['total']:.2f} ({data['count']} transactions)\n"

            report += f"""
By Payment Method:
"""
            for method, data in revenue_stats.get('by_payment_method', {}).items():
                if method:
                    report += f"  - {method}: GBP {data['total']:.2f} ({data['count']} transactions)\n"

            report += f"""
{'='*70}
                    UPCOMING CONSULTATIONS (Next 7 Days)
{'='*70}

"""
            if upcoming:
                for consult in upcoming[:10]:
                    report += f"  {consult['scheduled_date']} at {consult['scheduled_time']} - {consult['client_name']} ({consult['consultation_type']})\n"
            else:
                report += "  No upcoming consultations scheduled.\n"

            report += f"""
{'='*70}
                              END OF REPORT
{'='*70}
"""

            self.report_text.insert('1.0', report)

            messagebox.showinfo(
                _t("common.success", default="Success"),
                _t("legal.messages.report_generated", default="Report generated successfully")
            )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error generating report: {traceback.format_exc()}")

    # =========================================================================
    # FUNCTION 25: email_admin_report - Email report to admin/management
    # =========================================================================
    def email_admin_report(self):
        """Email the generated report to admin"""
        report_content = self.report_text.get('1.0', tk.END).strip()

        if not report_content:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.warnings.generate_report_first", default="Please generate a report first")
            )
            return

        # Get admin email
        admin_email = simpledialog.askstring(
            _t("legal.btn.email_report", default="Email Report"),
            _t("legal.prompts.admin_email", default="Enter admin email address:"),
            initialvalue=self.admin_email
        )

        if not admin_email:
            return

        if '@' not in admin_email:
            logger.info(f"Report email skipped - invalid email format: {admin_email}")
            messagebox.showwarning(_t("common.warning", default="Warning"), "Invalid email address")
            return

        try:
            report_type = self.report_type.get()
            subject = f"Legal Services Report - {report_type} - {datetime.now().strftime('%Y-%m-%d')}"

            if EMAIL_AVAILABLE:
                result = send_email(
                    recipient_email=admin_email,
                    subject=subject,
                    body=report_content
                )

                if result:
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.report_emailed", default="Report sent to admin successfully")
                    )
                    log_activity('email_report', 'legal_services', details={
                        'recipient': admin_email,
                        'report_type': report_type
                    })
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.email_failed", default="Failed to send email")
                    )
            else:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.email_unavailable", default="Email service not available")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error emailing report: {traceback.format_exc()}")

    # =========================================================================
    # Helper Methods
    # =========================================================================
    def load_cases(self):
        """Load cases into the treeview"""
        try:
            # Clear existing items
            for item in self.cases_tree.get_children():
                self.cases_tree.delete(item)

            # Build filters
            filters = {}
            status_filter = self.case_status_filter.get()
            type_filter = self.case_type_filter.get()
            search = self.case_search_entry.get().strip()

            if status_filter != _t("common.all", default="All"):
                # Map display value back to database value
                for s in CASE_STATUSES:
                    if _t(f"legal.status.{s}", default=s) == status_filter:
                        filters['status'] = s
                        break

            if type_filter != _t("common.all", default="All"):
                for t in CASE_TYPES:
                    if _t(f"legal.case_types.{t}", default=t) == type_filter:
                        filters['case_type'] = t
                        break

            if search:
                filters['search'] = search

            # Get cases
            self.cases_data = CaseManager.get_all_cases(filters)

            # Populate treeview
            for case in self.cases_data:
                self.cases_tree.insert('', tk.END, values=(
                    case['case_number'],
                    case['client_name'],
                    case['case_type'],
                    case['status'],
                    case['priority']
                ))

        except Exception as e:
            print(f"Error loading cases: {e}")

    def on_case_select(self, event):
        """Handle case selection"""
        selected = self.cases_tree.selection()
        if selected:
            item = self.cases_tree.item(selected[0])
            case_number = item['values'][0]
            self.selected_case = next((c for c in self.cases_data if c['case_number'] == case_number), None)

    def load_consultations(self):
        """Load consultations into the treeview"""
        try:
            for item in self.consult_tree.get_children():
                self.consult_tree.delete(item)

            filters = {}
            status_filter = self.consult_status_filter.get()
            if status_filter != _t("common.all", default="All"):
                filters['status'] = status_filter

            self.consultations_data = ConsultationManager.get_all_consultations(filters)

            for consult in self.consultations_data:
                self.consult_tree.insert('', tk.END, values=(
                    consult['consultation_id'],
                    consult['client_name'],
                    consult['scheduled_date'],
                    consult['scheduled_time'],
                    consult['consultation_type'],
                    f"GBP {consult['fee']:.2f}",
                    consult['payment_status'],
                    consult['status']
                ))

        except Exception as e:
            print(f"Error loading consultations: {e}")

    def on_consultation_select(self, event):
        """Handle consultation selection"""
        selected = self.consult_tree.selection()
        if selected:
            item = self.consult_tree.item(selected[0])
            consult_id = item['values'][0]
            self.selected_consultation = next((c for c in self.consultations_data if c['consultation_id'] == consult_id), None)

    def refresh_document_cases(self):
        """Refresh case list for document selector"""
        try:
            cases = CaseManager.get_all_cases()
            case_options = [f"{c['case_number']} - {c['client_name']}" for c in cases]
            self.doc_case_combo['values'] = case_options
            if case_options:
                self.doc_case_combo.set(case_options[0])
                self.load_case_documents(None)
        except Exception as e:
            print(f"Error refreshing document cases: {e}")

    def load_case_documents(self, event):
        """Load documents for the selected case"""
        try:
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)

            case_selection = self.doc_case_combo.get()
            if not case_selection:
                return

            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)

            if case:
                documents = DocumentManager.get_case_documents(case['case_id'])
                for doc in documents:
                    self.docs_tree.insert('', tk.END, values=(
                        doc['document_id'],
                        doc['document_name'],
                        doc['document_type'],
                        doc['version'],
                        doc.get('created_by', 'Unknown'),
                        doc['created_at'][:19] if doc['created_at'] else ''
                    ))

        except Exception as e:
            print(f"Error loading case documents: {e}")

    def save_report(self):
        """Save the current report to file"""
        report_content = self.report_text.get('1.0', tk.END).strip()
        if not report_content:
            messagebox.showwarning(_t("common.warning", default="Warning"), "No report to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfilename=f"legal_report_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        if file_path:
            with open(file_path, 'w') as f:
                f.write(report_content)
            messagebox.showinfo(_t("common.success", default="Success"), "Report saved successfully")

    # =========================================================================
    # REFUNDS TAB - Manage refunds for legal services
    # =========================================================================
    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.refunds", default="Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(10, 10), padx=10)

        ttk.Label(header_frame, text=_t("legal.refunds.title", default="Legal Services Refunds"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("common.search", default="Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(search_frame, text=_t("common.search_label", default="Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=10)

        # Create treeview with 7 columns
        columns = ('payment_id', 'date', 'client', 'amount', 'payment_type', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('payment_id', text=_t('legal.refunds.payment_id', default='Payment ID'))
        self.refunds_tree.heading('date', text=_t('common.date', default='Date'))
        self.refunds_tree.heading('client', text=_t('legal.common.client', default='Client'))
        self.refunds_tree.heading('amount', text=_t('common.amount', default='Amount'))
        self.refunds_tree.heading('payment_type', text=_t('legal.refunds.payment_type', default='Service Type'))
        self.refunds_tree.heading('payment_method', text=_t('common.payment_method', default='Payment Method'))
        self.refunds_tree.heading('status', text=_t('common.status', default='Status'))

        self.refunds_tree.column('payment_id', width=100)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('client', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_type', width=120)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.refunds_tree.xview)
        self.refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.refunds_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Buttons frame
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text=_t("legal.refunds.process", default="Process Refund"),
                  command=self.process_legal_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.view_details", default="View Details"),
                  command=self.view_legal_payment_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.refresh", default="Refresh"),
                  command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.export_csv", default="Export to CSV"),
                  command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()

            with get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        p.payment_id,
                        p.created_at,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference
                    FROM legal_payments p
                    ORDER BY p.created_at DESC
                """

                cursor.execute(query)
                payments = cursor.fetchall()

                for payment in payments:
                    payment_id, date, client_id, client_email, amount, payment_type, payment_method, status, reference = payment

                    # Apply search filter
                    if search_term:
                        searchable = f"{payment_id} {client_id} {client_email or ''} {payment_type} {status} {reference or ''}".lower()
                        if search_term not in searchable:
                            continue

                    # Format date
                    if date:
                        try:
                            date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, TypeError):
                            formatted_date = date
                    else:
                        formatted_date = ''

                    # Color code by status
                    tag = 'refunded' if status == 'refunded' else 'completed'

                    self.refunds_tree.insert('', tk.END, values=(
                        payment_id,
                        formatted_date,
                        client_email or client_id,
                        f"£{amount:.2f}",
                        payment_type or 'N/A',
                        payment_method or 'N/A',
                        status or 'completed'
                    ), tags=(tag,))

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def process_legal_refund(self):
        """Process a refund for a legal service payment"""
        # Get selected payment
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("legal.refunds.select_payment", default="Please select a payment to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        payment_id = values[0]
        amount_str = values[3]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("legal.refunds.already_refunded", default="Already Refunded"),
                                  _t("legal.refunds.already_refunded_msg", default="This payment has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except (ValueError, TypeError):
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("legal.refunds.confirm", default="Confirm Refund"),
                                   f"Refund £{amount:.2f} for Payment #{payment_id}?"):
            return

        try:
            # Get client ID
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT client_id, client_email FROM legal_payments WHERE payment_id = ?",
                             (payment_id,))
                result = cursor.fetchone()
                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("legal.refunds.payment_not_found", default="Payment not found."))
                    return
                client_id, client_email = result

            # Show refund method dialog
            self.show_legal_refund_method_dialog(payment_id, amount, client_id, client_email)

        except Exception as e:
            logger.error(f"Error processing legal refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_legal_refund_method_dialog(self, payment_id, amount, client_id, client_email):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("legal.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("legal.refunds.select_method", default="Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if client_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(client_id)
                ttk.Label(dialog, text=f"Current Student Account Balance: £{current_balance:.2f}",
                         foreground='blue').pack(pady=5)
                new_balance = current_balance + amount
                ttk.Label(dialog, text=f"New Balance After Refund: £{new_balance:.2f}",
                         foreground='green').pack(pady=5)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        # Buttons frame
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(pady=20, fill=tk.BOTH, expand=True)

        def refund_cash():
            dialog.destroy()
            self._complete_legal_refund(payment_id, amount, 'cash', client_id, client_email)

        def refund_card():
            dialog.destroy()
            self._complete_legal_refund(payment_id, amount, 'card', client_id, client_email)

        def refund_student_account():
            if not FINANCE_AVAILABLE:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("common.finance_unavailable", default="Finance system not available."))
                return
            dialog.destroy()
            self.add_legal_refund_to_student_account(payment_id, amount, client_id, client_email)

        # Create buttons
        cash_btn = ttk.Button(buttons_frame, text=_t("common.refund_cash", default="💵 Refund as Cash"),
                             command=refund_cash, width=30)
        cash_btn.pack(pady=10)

        card_btn = ttk.Button(buttons_frame, text=_t("common.refund_card", default="💳 Refund to Card"),
                             command=refund_card, width=30)
        card_btn.pack(pady=10)

        account_btn = ttk.Button(buttons_frame, text=_t("common.refund_account", default="🏦 Refund to Student Account"),
                                command=refund_student_account, width=30)
        account_btn.pack(pady=10)

        if not FINANCE_AVAILABLE:
            account_btn.config(state='disabled')

        ttk.Button(buttons_frame, text=_t("common.cancel", default="Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)

    def _complete_legal_refund(self, payment_id, amount, refund_method, client_id, client_email):
        """Complete the refund process (for cash/card)"""
        try:
            # Generate refund reference
            refund_ref = f"LEGAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update payment status
                cursor.execute("""
                    UPDATE legal_payments
                    SET status = 'refunded',
                        transaction_reference = ?
                    WHERE payment_id = ?
                """, (refund_ref, payment_id))

                # Create refund record in legal_refunds table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS legal_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER,
                        client_id TEXT,
                        client_email TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        FOREIGN KEY (payment_id) REFERENCES legal_payments(payment_id)
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO legal_refunds
                    (payment_id, client_id, client_email, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (payment_id, client_id, client_email, amount, refund_method, refund_ref, processed_by))

            # Log activity
            log_activity('refund', 'legal_payment',
                        payment_id=payment_id,
                        amount=amount,
                        details={'method': refund_method, 'reference': refund_ref})

            # Send receipt
            self.send_legal_refund_receipt(client_email, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_legal_finance_gui(payment_id, amount, refund_method, refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing legal refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")

    def add_legal_refund_to_student_account(self, payment_id, amount, client_id, client_email):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.finance_unavailable", default="Finance system not available."))
            return

        try:
            from university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(client_id)

            # Generate refund reference
            refund_ref = f"LEGAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update payment status
                cursor.execute("""
                    UPDATE legal_payments
                    SET status = 'refunded',
                        transaction_reference = ?
                    WHERE payment_id = ?
                """, (refund_ref, payment_id))

                # Create refund record
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS legal_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER,
                        client_id TEXT,
                        client_email TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        FOREIGN KEY (payment_id) REFERENCES legal_payments(payment_id)
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO legal_refunds
                    (payment_id, client_id, client_email, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (payment_id, client_id, client_email, amount, 'student_account', refund_ref, processed_by))

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, client_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (client_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in student_finance_transactions
                cursor.execute("""
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES (?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, client_id, amount, new_balance, f'Legal services refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Log activity
            log_activity('refund', 'legal_payment',
                        details={'payment_id': payment_id, 'amount': amount, 'method': 'student_account', 'reference': refund_ref, 'new_balance': new_balance})

            # Send receipt
            self.send_legal_refund_receipt(client_email, amount, 'student_account', refund_ref, new_balance)

            # Notify finance GUI
            self.notify_legal_finance_gui(payment_id, amount, 'student_account', refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding legal refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_legal_refund_receipt(self, client_email, amount, refund_method, refund_ref, new_balance=None):
        """Send refund receipt email to client"""
        if not EMAIL_AVAILABLE or not client_email:
            logger.info("Email service not available or no email address, skipping receipt")
            return

        try:
            # Get client name
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT full_name FROM students WHERE student_id = (SELECT client_id FROM legal_payments WHERE transaction_reference = ?)",
                             (refund_ref,))
                result = cursor.fetchone()

                client_name = result[0] if result else client_email

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text
            balance_text = ""
            if new_balance is not None:
                balance_text = f"\nYour new student account balance is: £{new_balance:.2f}"

            # Try to render from template
            subject = None
            email_body = None
            if render_template:
                subject, email_body = render_template('commerce/legal/refund_receipt', {
                    'client_name': client_name,
                    'refund_amount': f"£{amount:.2f}",
                    'refund_method': method_display,
                    'refund_ref': refund_ref,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'balance_text': balance_text
                })

            # Fallback if template not found
            if not subject or not email_body:
                subject = f"Legal Services Refund Receipt - {refund_ref}"
                email_body = f"""
Dear {client_name},

This is to confirm that your legal services refund has been processed successfully.

Refund Details:
- Refund Amount: £{amount:.2f}
- Refund Method: {method_display}
- Reference Number: {refund_ref}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{balance_text}

If you have any questions about this refund, please contact the Legal Services Center.

Best regards,
University Legal Services Center
"""

            # Send email
            send_email(
                to_email=client_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {client_email}")

        except Exception as e:
            logger.error(f"Error sending legal refund receipt: {e}")

    def notify_legal_finance_gui(self, payment_id, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Create finance_refunds table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        refund_reference TEXT UNIQUE,
                        department TEXT,
                        transaction_id TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        notes TEXT
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                # Insert refund record
                cursor.execute("""
                    INSERT INTO finance_refunds
                    (refund_reference, department, transaction_id, amount, refund_method, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (refund_ref, 'Legal Services', str(payment_id), amount, refund_method, processed_by,
                     'Legal services payment refund'))

            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_legal_payment_details(self):
        """View detailed information about a payment"""
        # Get selected payment
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("legal.refunds.select_payment_view", default="Please select a payment to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        payment_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get payment details
                cursor.execute("""
                    SELECT
                        p.payment_id,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference,
                        p.created_at,
                        p.processed_by,
                        p.case_id,
                        p.consultation_id
                    FROM legal_payments p
                    WHERE p.payment_id = ?
                """, (payment_id,))

                payment = cursor.fetchone()

                if not payment:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("legal.refunds.payment_not_found", default="Payment not found."))
                    return

                (pid, client_id, client_email, amount, payment_type, payment_method,
                 status, reference, created_at, processed_by, case_id, consultation_id) = payment

                # Get case/consultation details
                service_details = ""
                if case_id:
                    cursor.execute("SELECT case_number, case_type FROM legal_cases WHERE case_id = ?", (case_id,))
                    case = cursor.fetchone()
                    if case:
                        service_details = f"\nCase Number: {case[0]}\nCase Type: {case[1]}"
                elif consultation_id:
                    cursor.execute("SELECT scheduled_date, scheduled_time FROM legal_consultations WHERE consultation_id = ?",
                                 (consultation_id,))
                    consultation = cursor.fetchone()
                    if consultation:
                        service_details = f"\nConsultation Date: {consultation[0]}\nConsultation Time: {consultation[1]}"

                # Create details window
                details_window = tk.Toplevel(self.window)
                details_window.title(_t("legal.refunds.payment_details", default="Payment Details"))
                details_window.geometry("600x600")
                details_window.transient(self.window)

                # Create scrollable text widget
                text_frame = ttk.Frame(details_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=35)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Build details text
                details = f"""
LEGAL SERVICES PAYMENT DETAILS
{'=' * 50}

Payment Information:
  Payment ID: {pid}
  Status: {status}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Client Information:
  Client ID: {client_id}
  Email: {client_email or 'N/A'}

Service Details:
  Payment Type: {payment_type}{service_details}

Financial Details:
  Amount: £{amount:.2f}
  Payment Method: {payment_method or 'N/A'}

{'=' * 50}
"""

                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                # Close button
                ttk.Button(details_window, text=_t("common.close", default="Close"),
                          command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing payment details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")

    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'legal_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        p.payment_id,
                        p.created_at,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference
                    FROM legal_payments p
                    ORDER BY p.created_at DESC
                """)

                payments = cursor.fetchall()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Payment ID', 'Date', 'Client ID', 'Client Email',
                               'Amount', 'Payment Type', 'Payment Method', 'Status', 'Reference'])

                # Write data
                for payment in payments:
                    payment_id, date, client_id, client_email, amount, payment_type, payment_method, status, reference = payment
                    writer.writerow([
                        payment_id,
                        date or '',
                        client_id,
                        client_email or '',
                        f'{amount:.2f}' if amount else '0.00',
                        payment_type or '',
                        payment_method or '',
                        status or 'completed',
                        reference or ''
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")


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
