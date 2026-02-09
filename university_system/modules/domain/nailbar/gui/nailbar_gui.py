"""Nail Bar/Salon GUI Module

Provides a comprehensive GUI for nail bar/salon operations including
treatments, appointments, technicians, and reporting with email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from university_system.modules.shared.utils.i18n import get_text as _t
from university_system.infrastructure.database.db import get_db_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

# Authentication imports
try:
    from university_system.infrastructure.shared_context import get_auth, _DummyAuth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None
    _DummyAuth = None

# Finance integration imports
try:
    from university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment,
        ensure_student_finance_account_exists
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    record_payment_to_finance = None

# Email imports
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

logger = logging.getLogger(__name__)


class NailBarGUI:
    """Main GUI class for Nail Bar/Salon operations"""

    def __init__(self, parent: tk.Toplevel, auth=None):
        """Initialize the Nail Bar GUI - Function 1"""
        self.parent = parent
        self.auth = auth

        # Try to get auth from shared context if not provided
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check authentication
        if not self._check_authentication():
            return

        self.parent.title(_t("nailbar.window_title"))
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Selected treatments for booking
        self.selected_treatments = []

        # Initialize database
        self._init_database()

        # Create main interface
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

        log_activity('access', 'nailbar')

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("nailbar.window_title"),
                "You must be logged in to access the Nail Bar module.\n\n"
                "Please log in through the main GUI first."
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("nailbar.window_title"),
                "You must be logged in to access the Nail Bar module.\n\n"
                "Please launch this module from the main GUI after logging in."
            )
            if self.parent:
                self.parent.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("nailbar.window_title"),
                "You are not currently logged in.\n\n"
                "Please log in through the main GUI to access this module."
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Store current user info
        self.current_user = self.auth.current_user
        return True

    def create_widgets(self):
        """Create the main GUI widgets - Function 2"""
        # Header frame
        header_frame = ttk.Frame(self.parent, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(header_frame, text=_t("nailbar.title"),
                 font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        user_info = f"{self.current_user.get('username')} ({self.current_user.get('role')})"
        ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_appointments_tab()
        self.create_treatments_tab()
        self.create_technicians_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

        # Bottom buttons
        btn_frame = ttk.Frame(self.parent, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("common.refresh"),
                  command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("nailbar.btn.return_home"),
                  command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Initialize database tables - Function 3"""
        from university_system.modules.domain.nailbar.services.nailbar_core import init_nailbar_db
        try:
            init_nailbar_db()
        except Exception as e:
            logger.error(f"Failed to initialize nailbar database: {e}")

    def return_to_homescreen(self):
        """Return to the main homescreen - Function 4"""
        if messagebox.askyesno(_t("common.confirm"), _t("nailbar.confirm.exit")):
            self.parent.destroy()

    def refresh_all_data(self):
        """Refresh all data in the GUI - Function 5"""
        try:
            self._load_appointments()
            self._load_treatments()
            self._load_technicians()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")

    def create_appointments_tab(self):
        """Create the appointments management tab - Function 6"""
        appointments_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(appointments_frame, text=_t("nailbar.tabs.appointments"))

        # Top - Book new appointment
        book_frame = ttk.LabelFrame(appointments_frame, text=_t("nailbar.labels.book_appointment"), padding="10")
        book_frame.pack(fill=tk.X, pady=(0, 10))

        # Customer details row - Using current logged-in user
        cust_frame = ttk.Frame(book_frame)
        cust_frame.pack(fill=tk.X, pady=5)

        # Get user details from current session
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            user_name = f"{first_name} {last_name}"
        else:
            user_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')
        user_email = self.current_user.get('email', '')
        user_id = (self.current_user.get('student_id') or
                  self.current_user.get('username') or
                  str(self.current_user.get('id', '')))

        ttk.Label(cust_frame, text=_t("nailbar.labels.booking_for"), font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_name, font=('Helvetica', 10)).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text=_t("nailbar.labels.email")).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_email if user_email else "Not set",
                 foreground='gray' if not user_email else 'black').pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text=_t("nailbar.labels.id")).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_id if user_id else "N/A").pack(side=tk.LEFT, padx=5)

        # Treatment selection
        treat_frame = ttk.Frame(book_frame)
        treat_frame.pack(fill=tk.X, pady=5)

        ttk.Label(treat_frame, text=_t("nailbar.labels.treatment") + ":").pack(side=tk.LEFT)
        self.appt_treatment_combo = ttk.Combobox(treat_frame, state="readonly", width=30)
        self.appt_treatment_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(treat_frame, text=_t("nailbar.btn.add_treatment"),
                  command=self.add_treatment_to_booking).pack(side=tk.LEFT, padx=5)

        # Selected treatments list
        self.selected_treatments_tree = ttk.Treeview(treat_frame, columns=('name', 'duration', 'price'),
                                                     show='headings', height=3)
        self.selected_treatments_tree.heading('name', text=_t("nailbar.labels.treatment"))
        self.selected_treatments_tree.heading('duration', text=_t("nailbar.labels.duration"))
        self.selected_treatments_tree.heading('price', text=_t("nailbar.labels.price"))
        self.selected_treatments_tree.column('name', width=180)
        self.selected_treatments_tree.column('duration', width=80)
        self.selected_treatments_tree.column('price', width=80)
        self.selected_treatments_tree.pack(side=tk.LEFT, padx=10)

        ttk.Button(treat_frame, text=_t("nailbar.btn.remove_treatment"),
                  command=self.remove_treatment_from_booking).pack(side=tk.LEFT, padx=5)

        # Scheduling row
        sched_frame = ttk.Frame(book_frame)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text=_t("nailbar.labels.technician") + ":").pack(side=tk.LEFT)
        self.appt_tech_combo = ttk.Combobox(sched_frame, state="readonly", width=20)
        self.appt_tech_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("nailbar.labels.date") + ":").pack(side=tk.LEFT)
        self.appt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(sched_frame, textvariable=self.appt_date_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("nailbar.labels.time") + ":").pack(side=tk.LEFT)
        self.appt_time_combo = ttk.Combobox(sched_frame, state="readonly", width=10)
        self.appt_time_combo['values'] = self._get_time_slots()
        self.appt_time_combo.pack(side=tk.LEFT, padx=5)

        self.booking_total_var = tk.StringVar(value="£0.00")
        ttk.Label(sched_frame, text=_t("nailbar.labels.total") + ":",
                 font=('Helvetica', 11, 'bold')).pack(side=tk.LEFT, padx=10)
        ttk.Label(sched_frame, textvariable=self.booking_total_var,
                 font=('Helvetica', 11, 'bold')).pack(side=tk.LEFT)

        ttk.Button(sched_frame, text=_t("nailbar.btn.book_appointment"),
                  command=self.book_appointment).pack(side=tk.RIGHT, padx=10)
        ttk.Button(sched_frame, text=_t("nailbar.btn.clear_booking"),
                  command=self.clear_booking).pack(side=tk.RIGHT, padx=5)

        # Today's appointments
        today_frame = ttk.LabelFrame(appointments_frame, text=_t("nailbar.labels.todays_appointments"), padding="5")
        today_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('reference', 'time', 'customer', 'treatments', 'technician', 'status', 'payment')
        self.appointments_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=10)

        self.appointments_tree.heading('reference', text=_t("nailbar.labels.booking_ref"))
        self.appointments_tree.heading('time', text=_t("nailbar.labels.time"))
        self.appointments_tree.heading('customer', text=_t("nailbar.labels.customer"))
        self.appointments_tree.heading('treatments', text=_t("nailbar.labels.treatments"))
        self.appointments_tree.heading('technician', text=_t("nailbar.labels.technician"))
        self.appointments_tree.heading('status', text=_t("nailbar.labels.status"))
        self.appointments_tree.heading('payment', text=_t("nailbar.labels.payment_status"))

        self.appointments_tree.column('reference', width=120)
        self.appointments_tree.column('time', width=70)
        self.appointments_tree.column('customer', width=130)
        self.appointments_tree.column('treatments', width=200)
        self.appointments_tree.column('technician', width=100)
        self.appointments_tree.column('status', width=90)
        self.appointments_tree.column('payment', width=90)

        scrollbar = ttk.Scrollbar(today_frame, orient=tk.VERTICAL, command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        action_frame = ttk.Frame(appointments_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(action_frame, text=_t("nailbar.btn.check_in"),
                  command=self.check_in_customer).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("nailbar.btn.start_treatment"),
                  command=self.start_treatment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("nailbar.btn.complete_treatment"),
                  command=self.complete_treatment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("nailbar.btn.process_payment"),
                  command=self.process_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("nailbar.btn.cancel_appointment"),
                  command=self.cancel_appointment).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("nailbar.btn.reschedule"),
                  command=self.reschedule_appointment).pack(side=tk.LEFT, padx=5)

    def create_treatments_tab(self):
        """Create the treatments management tab - Function 7"""
        treatments_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(treatments_frame, text=_t("nailbar.tabs.treatments"))

        # Left - Treatments list
        list_frame = ttk.LabelFrame(treatments_frame, text=_t("nailbar.labels.treatment_menu"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Category filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text=_t("nailbar.labels.category") + ":").pack(side=tk.LEFT)
        self.treatment_filter = ttk.Combobox(filter_frame, state="readonly", width=20)
        self.treatment_filter['values'] = ['All'] + list(self._get_categories().values())
        self.treatment_filter.set('All')
        self.treatment_filter.pack(side=tk.LEFT, padx=5)
        self.treatment_filter.bind('<<ComboboxSelected>>', lambda e: self._load_treatments())

        columns = ('id', 'name', 'category', 'duration', 'price')
        self.treatments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.treatments_tree.heading('id', text=_t('nailbar.columns.id'))
        self.treatments_tree.heading('name', text=_t("nailbar.labels.treatment_name"))
        self.treatments_tree.heading('category', text=_t("nailbar.labels.category"))
        self.treatments_tree.heading('duration', text=_t("nailbar.labels.duration"))
        self.treatments_tree.heading('price', text=_t("nailbar.labels.price"))

        self.treatments_tree.column('id', width=50)
        self.treatments_tree.column('name', width=180)
        self.treatments_tree.column('category', width=120)
        self.treatments_tree.column('duration', width=80)
        self.treatments_tree.column('price', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.treatments_tree.yview)
        self.treatments_tree.configure(yscrollcommand=scrollbar.set)

        self.treatments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add/Edit treatment
        edit_frame = ttk.LabelFrame(treatments_frame, text=_t("nailbar.labels.add_treatment"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("nailbar.labels.treatment_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.treatment_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.treatment_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.category") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.treatment_category_combo = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.treatment_category_combo['values'] = list(self._get_categories().values())
        self.treatment_category_combo.grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.duration") + " (min):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.treatment_duration_var = tk.StringVar(value="45")
        ttk.Entry(edit_frame, textvariable=self.treatment_duration_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.price") + " (£):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.treatment_price_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.treatment_price_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.description") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.treatment_desc_text = tk.Text(edit_frame, width=25, height=3)
        self.treatment_desc_text.grid(row=4, column=1, pady=2)

        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("nailbar.btn.add_treatment"),
                  command=self.add_treatment).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("nailbar.btn.update_treatment"),
                  command=self.update_treatment).pack(side=tk.LEFT, padx=2)

    def create_technicians_tab(self):
        """Create the technicians management tab - Function 8"""
        tech_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tech_frame, text=_t("nailbar.tabs.technicians"))

        # Left - Technicians list
        list_frame = ttk.LabelFrame(tech_frame, text=_t("nailbar.labels.technician_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ('id', 'name', 'employee_id', 'specialties', 'certification', 'status')
        self.technicians_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.technicians_tree.heading('id', text=_t('nailbar.columns.id'))
        self.technicians_tree.heading('name', text=_t("nailbar.labels.name"))
        self.technicians_tree.heading('employee_id', text=_t("nailbar.labels.employee_id"))
        self.technicians_tree.heading('specialties', text=_t("nailbar.labels.specialties"))
        self.technicians_tree.heading('certification', text=_t("nailbar.labels.certification"))
        self.technicians_tree.heading('status', text=_t("nailbar.labels.status"))

        self.technicians_tree.column('id', width=50)
        self.technicians_tree.column('name', width=120)
        self.technicians_tree.column('employee_id', width=100)
        self.technicians_tree.column('specialties', width=180)
        self.technicians_tree.column('certification', width=100)
        self.technicians_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.technicians_tree.yview)
        self.technicians_tree.configure(yscrollcommand=scrollbar.set)

        self.technicians_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add technician
        edit_frame = ttk.LabelFrame(tech_frame, text=_t("nailbar.labels.add_technician"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("nailbar.labels.name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.tech_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.employee_id") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.tech_emp_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_emp_id_var, width=25).grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.specialties") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.tech_specialties_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_specialties_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.certification") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.tech_cert_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_cert_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.phone") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.tech_phone_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_phone_var, width=25).grid(row=4, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("nailbar.labels.email") + ":").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.tech_email_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.tech_email_var, width=25).grid(row=5, column=1, pady=2)

        ttk.Button(edit_frame, text=_t("nailbar.btn.add_technician"),
                  command=self.add_technician).grid(row=6, column=0, columnspan=2, pady=10)

    def create_reports_tab(self):
        """Create the reports tab - Function 9"""
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text=_t("nailbar.tabs.reports"))

        # Report options
        options_frame = ttk.LabelFrame(reports_frame, text=_t("nailbar.labels.report_options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text=_t("nailbar.labels.date_from") + ":").pack(side=tk.LEFT)
        self.report_from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text=_t("nailbar.labels.date_to") + ":").pack(side=tk.LEFT)
        self.report_to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(options_frame, text=_t("nailbar.btn.generate_report"),
                  command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(options_frame, text=_t("nailbar.btn.email_report"),
                  command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display = ttk.LabelFrame(reports_frame, text=_t("nailbar.labels.report_output"), padding="5")
        report_display.pack(fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(report_display, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_display, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_time_slots(self) -> list:
        """Get available time slots - Function 10"""
        from university_system.modules.domain.nailbar.services.nailbar_core import TIME_SLOTS
        return TIME_SLOTS

    def _get_categories(self) -> dict:
        """Get treatment categories - Function 11"""
        from university_system.modules.domain.nailbar.services.nailbar_core import TREATMENT_CATEGORIES
        return TREATMENT_CATEGORIES

    def _load_appointments(self):
        """Load appointments into the treeview - Function 12"""
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
            appointments = AppointmentManager.get_todays_appointments()

            for appt in appointments:
                # Get treatments for this appointment
                full_appt = AppointmentManager.get_appointment(appt['appointment_id'])
                treatments = ', '.join(t['treatment_name'] for t in full_appt.get('treatments', []))

                self.appointments_tree.insert('', tk.END, values=(
                    appt['booking_reference'],
                    appt['appointment_time'],
                    appt['customer_name'],
                    treatments[:40] + '...' if len(treatments) > 40 else treatments,
                    appt.get('technician_name', 'Any'),
                    appt['status'],
                    appt['payment_status']
                ))
        except Exception as e:
            logger.error(f"Error loading appointments: {e}")

    def _load_treatments(self):
        """Load treatments into the treeview - Function 13"""
        for item in self.treatments_tree.get_children():
            self.treatments_tree.delete(item)

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import TreatmentManager

            category_filter = self.treatment_filter.get()
            category = None
            if category_filter != 'All':
                categories = self._get_categories()
                category = next((k for k, v in categories.items() if v == category_filter), None)

            treatments = TreatmentManager.get_all_treatments(category=category)

            treatment_list = []
            categories_dict = self._get_categories()
            for t in treatments:
                cat_name = categories_dict.get(t['category'], t['category'])
                self.treatments_tree.insert('', tk.END, values=(
                    t['treatment_id'],
                    t['name'],
                    cat_name,
                    f"{t['duration_minutes']} min",
                    f"£{t['price']:.2f}"
                ))
                treatment_list.append(f"{t['treatment_id']}: {t['name']} (£{t['price']:.2f})")

            self.appt_treatment_combo['values'] = treatment_list

        except Exception as e:
            logger.error(f"Error loading treatments: {e}")

    def _load_technicians(self):
        """Load technicians into the treeview - Function 14"""
        for item in self.technicians_tree.get_children():
            self.technicians_tree.delete(item)

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import TechnicianManager
            technicians = TechnicianManager.get_all_technicians()

            tech_list = ['Any']
            for t in technicians:
                status = 'Active' if t.get('is_active', 1) else 'Inactive'
                self.technicians_tree.insert('', tk.END, values=(
                    t['technician_id'],
                    t['name'],
                    t.get('employee_id', ''),
                    t.get('specialties', ''),
                    t.get('certification', ''),
                    status
                ))
                tech_list.append(f"{t['technician_id']}: {t['name']}")

            self.appt_tech_combo['values'] = tech_list
            self.appt_tech_combo.set('Any')

        except Exception as e:
            logger.error(f"Error loading technicians: {e}")

    def add_treatment_to_booking(self):
        """Add treatment to current booking - Function 15"""
        treatment_str = self.appt_treatment_combo.get()
        if not treatment_str:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment"))
            return

        try:
            treatment_id = int(treatment_str.split(':')[0])

            with get_db_connection() as conn:
                treatment = conn.execute(
                    'SELECT * FROM nailbar_treatments WHERE treatment_id = ?',
                    (treatment_id,)
                ).fetchone()

                if treatment:
                    self.selected_treatments.append({
                        'treatment_id': treatment_id,
                        'name': treatment['name'],
                        'duration': treatment['duration_minutes'],
                        'price': treatment['price']
                    })

                    self.selected_treatments_tree.insert('', tk.END, values=(
                        treatment['name'],
                        f"{treatment['duration_minutes']} min",
                        f"£{treatment['price']:.2f}"
                    ))

                    self._update_booking_total()

        except (ValueError, IndexError):
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_selection"))

    def remove_treatment_from_booking(self):
        """Remove treatment from current booking - Function 16"""
        selected = self.selected_treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment_to_remove"))
            return

        index = self.selected_treatments_tree.index(selected[0])
        self.selected_treatments.pop(index)
        self.selected_treatments_tree.delete(selected[0])
        self._update_booking_total()

    def _update_booking_total(self):
        """Update booking total display - Function 17"""
        total = sum(t['price'] for t in self.selected_treatments)
        self.booking_total_var.set(f"£{total:.2f}")

    def clear_booking(self):
        """Clear current booking - Function 18"""
        self.selected_treatments = []
        for item in self.selected_treatments_tree.get_children():
            self.selected_treatments_tree.delete(item)
        self._update_booking_total()

    def book_appointment(self):
        """Book a new appointment - Function 19"""
        if not self.selected_treatments:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.no_treatments"))
            return

        # Use current user details
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            customer_name = f"{first_name} {last_name}"
        else:
            customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        customer_email = self.current_user.get('email', '')
        customer_phone = self.current_user.get('phone', '')
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', 'guest')))

        tech_str = self.appt_tech_combo.get()
        appt_date = self.appt_date_var.get().strip()
        appt_time = self.appt_time_combo.get()

        if not appt_date or not appt_time:
            messagebox.showerror(_t("common.error"), "Please select a date and time.")
            return

        try:
            technician_id = None
            if tech_str != 'Any':
                technician_id = int(tech_str.split(':')[0])

            treatment_ids = [t['treatment_id'] for t in self.selected_treatments]

            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager

            appt_id, booking_ref = AppointmentManager.create_appointment(
                customer_id=customer_id,
                customer_name=customer_name,
                appointment_date=appt_date,
                appointment_time=appt_time,
                treatment_ids=treatment_ids,
                technician_id=technician_id,
                customer_email=customer_email,
                customer_phone=customer_phone
            )

            log_activity('create', 'nailbar_appointment',
                        details={'appointment_id': appt_id})

            messagebox.showinfo(_t("common.success"),
                              _t("nailbar.messages.appointment_booked").format(booking_reference=booking_ref))

            self.clear_booking()
            self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.booking_failed").format(error=str(e)))

    def check_in_customer(self):
        """Check in customer - Function 20"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'checked_in',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.checked_in"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def start_treatment(self):
        """Mark treatment as started - Function 21"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'in_progress',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_started"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def complete_treatment(self):
        """Mark treatment as completed - Function 22"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'completed',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_completed"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment - Function 23"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]
        payment_status = item['values'][6]

        if payment_status == 'paid':
            messagebox.showinfo(_t("common.info"), _t("nailbar.messages.already_paid"))
            return

        from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager, TransactionManager
        appt = AppointmentManager.get_appointment_by_reference(booking_ref)

        if not appt:
            return

        # Get customer details
        customer_id = appt.get('customer_id', self.current_user.get('student_id', 'guest'))
        customer_email = appt.get('customer_email') or self.current_user.get('email', '')
        customer_name = appt.get('customer_name') or self.current_user.get('full_name', '')

        # Payment dialog
        payment_window = tk.Toplevel(self.parent)
        payment_window.title("Process Payment")
        payment_window.geometry("500x550")
        payment_window.transient(self.parent)
        payment_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(payment_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text=_t("nailbar.labels.payment_details"),
                 font=('Helvetica', 16, 'bold')).pack(pady=(0, 15))

        # Appointment info frame
        info_frame = ttk.LabelFrame(main_frame, text=_t("nailbar.labels.appointment_info"), padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text=f"Booking: {booking_ref}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Customer: {customer_name}").pack(anchor=tk.W)

        # Treatments list
        treatments = appt.get('treatments', [])
        treatments_text = ', '.join(t['treatment_name'] for t in treatments)
        ttk.Label(info_frame, text=f"Treatments: {treatments_text[:50]}{'...' if len(treatments_text) > 50 else ''}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Technician: {appt.get('technician_name', 'Any')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Service Total: £{appt['total_amount']:.2f}",
                 font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Tip frame
        tip_frame = ttk.Frame(main_frame)
        tip_frame.pack(fill=tk.X, pady=10)
        ttk.Label(tip_frame, text=_t("nailbar.labels.add_tip")).pack(side=tk.LEFT)
        tip_var = tk.StringVar(value="0")
        ttk.Entry(tip_frame, textvariable=tip_var, width=10).pack(side=tk.LEFT, padx=10)

        # Payment method frame
        method_frame = ttk.LabelFrame(main_frame, text=_t("nailbar.labels.select_payment_method"), padding="10")
        method_frame.pack(fill=tk.X, pady=10)

        payment_method_var = tk.StringVar(value="card")

        # Cash option
        ttk.Radiobutton(method_frame, text=_t("nailbar.labels.cash"), variable=payment_method_var,
                       value="cash").pack(anchor=tk.W, pady=2)

        # Card option
        ttk.Radiobutton(method_frame, text=_t("nailbar.labels.card"), variable=payment_method_var,
                       value="card").pack(anchor=tk.W, pady=2)

        # Student Account option with balance
        student_balance = 0.0
        balance_text=_t("nailbar.labels.balance_not_available")
        if FINANCE_AVAILABLE:
            try:
                ensure_student_finance_account_exists(customer_id)
                student_balance = get_student_finance_account_balance(customer_id) or 0.0
                balance_text = f"Balance: £{student_balance:.2f}"
            except Exception as e:
                logger.error(f"Error getting student balance: {e}")

        student_frame = ttk.Frame(method_frame)
        student_frame.pack(anchor=tk.W, fill=tk.X)
        ttk.Radiobutton(student_frame, text=_t("nailbar.labels.student_account"),
                       variable=payment_method_var, value="student_account").pack(side=tk.LEFT)
        balance_label = ttk.Label(student_frame, text=balance_text,
                                 foreground='green' if student_balance > 0 else 'gray')
        balance_label.pack(side=tk.LEFT, padx=10)

        # Total display
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=10)

        def update_total(*args):
            try:
                tip = float(tip_var.get() or 0)
                total = appt['total_amount'] + tip
                total_label.config(text=f"Total: £{total:.2f}")
            except ValueError:
                pass

        tip_var.trace('w', update_total)
        total_label = ttk.Label(total_frame, text=f"Total: £{appt['total_amount']:.2f}",
                               font=('Helvetica', 14, 'bold'))
        total_label.pack()

        # Email receipt option
        send_receipt_var = tk.BooleanVar(value=True if customer_email else False)
        receipt_frame = ttk.Frame(main_frame)
        receipt_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(receipt_frame, text=f"Send receipt to: {customer_email}",
                       variable=send_receipt_var,
                       state='normal' if customer_email else 'disabled').pack(anchor=tk.W)

        def confirm_payment():
            method = payment_method_var.get()
            try:
                tip = float(tip_var.get() or 0)
            except ValueError:
                messagebox.showerror(_t("nailbar.msg_titles.error"), "Invalid tip amount.")
                return

            total_amount = appt['total_amount'] + tip

            try:
                transaction_ref = f"NAILBAR-{appt['appointment_id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                if method == 'student_account':
                    # Check if finance integration available
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror(_t("nailbar.msg_titles.error"), "Student account payment is not available.")
                        return

                    # Check balance
                    if student_balance < total_amount:
                        messagebox.showerror(_t("nailbar.msg_titles.insufficient_balance"),
                            f"Your account balance (£{student_balance:.2f}) is insufficient.\n"
                            f"Required: £{total_amount:.2f}")
                        return

                    # Process student account payment
                    result = process_student_finance_account_payment(
                        student_id=customer_id,
                        amount=total_amount,
                        description=f"Nail Bar: {treatments_text[:30]}",
                        transaction_source="NailBar",
                        transaction_ref=transaction_ref,
                        processed_by=self.current_user.get('username', 'system')
                    )

                    if not result.get('success'):
                        messagebox.showerror(_t("nailbar.msg_titles.payment_failed"), result.get('message', 'Unknown error'))
                        return

                    payment_id = result.get('transaction_id')

                else:
                    # Cash or Card payment - record to central finance
                    if FINANCE_AVAILABLE:
                        payment_id = record_payment_to_finance(
                            student_id=customer_id,
                            amount=total_amount,
                            payment_method=method.title(),
                            transaction_source="NailBar",
                            transaction_ref=transaction_ref,
                            notes=f"Treatments: {treatments_text[:50]}" + (f", Tip: £{tip:.2f}" if tip > 0 else ""),
                            created_by=self.current_user.get('username', 'system')
                        )
                    else:
                        payment_id = None

                # Record in nailbar transactions table
                local_trans_id = TransactionManager.process_payment(
                    appointment_id=appt['appointment_id'],
                    amount=appt['total_amount'],
                    payment_method=method,
                    customer_id=customer_id,
                    tip_amount=tip,
                    processed_by=self.current_user.get('username')
                )

                # Send receipt email if requested
                if send_receipt_var.get() and customer_email:
                    self._send_payment_receipt(
                        appt=appt,
                        total_amount=total_amount,
                        tip=tip,
                        payment_method=method,
                        transaction_ref=transaction_ref,
                        customer_email=customer_email,
                        customer_name=customer_name
                    )

                log_activity('payment', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id'],
                                   'amount': total_amount,
                                   'method': method})

                messagebox.showinfo(_t("nailbar.msg_titles.success"),
                    f"Payment of £{total_amount:.2f} processed successfully!\n\n"
                    f"Method: {method.replace('_', ' ').title()}\n"
                    f"Reference: {transaction_ref}")
                payment_window.destroy()
                self._load_appointments()

            except Exception as e:
                logger.error(f"Payment processing error: {e}")
                messagebox.showerror(_t("nailbar.msg_titles.error"), f"Payment failed: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text=_t("nailbar.btn.confirm_payment"),
                  command=confirm_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("nailbar.btn.cancel"),
                  command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _send_payment_receipt(self, appt: dict, total_amount: float, tip: float,
                              payment_method: str, transaction_ref: str,
                              customer_email: str, customer_name: str):
        """Send payment receipt email to customer."""
        try:
            treatments = appt.get('treatments', [])
            treatments_text = '\n'.join(f"  - {t['treatment_name']}: £{t['price']:.2f}"
                                       for t in treatments)

            # Use JSON template for email
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/nailbar/payment_receipt', {
                'customer_name': customer_name,
                'booking_reference': appt['booking_reference'],
                'appointment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'technician_name': appt.get('technician_name', 'Any available'),
                'treatments_list': treatments_text,
                'subtotal': f"£{appt['total_amount']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total_amount:.2f}",
                'payment_method': payment_method.replace('_', ' ').title(),
                'transaction_ref': transaction_ref
            })

            # Try to send email - import directly to ensure it works
            try:
                from university_system.infrastructure.email.email_service import send_email as send_email_func
                send_email_func(customer_email, subject, body)
                logger.info(f"Receipt sent to {customer_email}")

                # Mark receipt as sent
                from university_system.modules.domain.nailbar.services.nailbar_core import TransactionManager
                TransactionManager.mark_receipt_sent(appt['appointment_id'])
            except ImportError:
                logger.warning("Email service not available - receipt not sent")
            except Exception as email_err:
                logger.error(f"Email sending failed: {email_err}")

        except Exception as e:
            logger.error(f"Failed to prepare receipt email: {e}")

    def send_receipt_email(self, appointment: dict, transaction_id: int, tip: float = 0):
        """Send receipt email - Function 24 (legacy method)"""
        try:
            if not EMAIL_AVAILABLE:
                logger.warning("Email service not available")
                return

            total = appointment['total_amount'] + tip
            treatments_text = '\n'.join(f"  - {t['treatment_name']}: £{t['price']:.2f}"
                                       for t in appointment.get('treatments', []))

            # Use JSON template for email
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/nailbar/payment_receipt', {
                'customer_name': appointment['customer_name'],
                'booking_reference': appointment['booking_reference'],
                'appointment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'technician_name': appointment.get('technician_name', 'N/A'),
                'treatments_list': treatments_text,
                'subtotal': f"£{appointment['total_amount']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total:.2f}",
                'payment_method': 'N/A',
                'transaction_ref': str(transaction_id)
            })

            send_email(
                recipient_email=appointment['customer_email'],
                subject=subject,
                body=body
            )

            from university_system.modules.domain.nailbar.services.nailbar_core import TransactionManager
            TransactionManager.mark_receipt_sent(transaction_id)

            logger.info(f"Receipt sent to {appointment['customer_email']}")

        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def cancel_appointment(self):
        """Cancel appointment - Function 25"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        if not messagebox.askyesno(_t("common.confirm"), _t("nailbar.confirm.cancel_appointment")):
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.cancel_appointment(appt['appointment_id'], 'Cancelled by user')
                log_activity('cancel', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.appointment_cancelled"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def reschedule_appointment(self):
        """Reschedule appointment"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        from university_system.modules.domain.nailbar.services.nailbar_core import AppointmentManager
        appt = AppointmentManager.get_appointment_by_reference(booking_ref)

        if not appt:
            return

        resched_window = tk.Toplevel(self.parent)
        resched_window.title(_t("nailbar.labels.reschedule"))
        resched_window.geometry("350x200")
        resched_window.transient(self.parent)
        resched_window.grab_set()

        ttk.Label(resched_window, text=f"{_t('nailbar.labels.booking_ref')}: {booking_ref}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(resched_window)
        frame.pack(pady=10)

        ttk.Label(frame, text=_t("nailbar.labels.new_date") + ":").grid(row=0, column=0, pady=5)
        new_date_var = tk.StringVar(value=appt['appointment_date'])
        ttk.Entry(frame, textvariable=new_date_var, width=12).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("nailbar.labels.new_time") + ":").grid(row=1, column=0, pady=5)
        new_time_combo = ttk.Combobox(frame, state="readonly", width=10)
        new_time_combo['values'] = self._get_time_slots()
        new_time_combo.set(appt['appointment_time'])
        new_time_combo.grid(row=1, column=1, pady=5)

        def confirm_reschedule():
            new_date = new_date_var.get().strip()
            new_time = new_time_combo.get()

            try:
                AppointmentManager.reschedule_appointment(appt['appointment_id'], new_date, new_time)
                log_activity('reschedule', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.appointment_rescheduled"))
                resched_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror(_t("common.error"), str(e))

        ttk.Button(resched_window, text=_t("nailbar.btn.confirm_reschedule"),
                  command=confirm_reschedule).pack(pady=20)

    def add_treatment(self):
        """Add a new treatment"""
        name = self.treatment_name_var.get().strip()
        category_display = self.treatment_category_combo.get()
        duration_str = self.treatment_duration_var.get().strip()
        price_str = self.treatment_price_var.get().strip()
        description = self.treatment_desc_text.get("1.0", tk.END).strip()

        if not name or not category_display or not price_str:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 45
            price = float(price_str)

            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'manicure')

            from university_system.modules.domain.nailbar.services.nailbar_core import TreatmentManager
            treatment_id = TreatmentManager.add_treatment(
                name=name, category=category, price=price,
                duration_minutes=duration, description=description
            )

            log_activity('create', 'nailbar_treatment', treatment_id=treatment_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_added"))
            self._clear_treatment_form()
            self._load_treatments()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_treatment(self):
        """Update selected treatment"""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment"))
            return

        item = self.treatments_tree.item(selected[0])
        treatment_id = item['values'][0]

        name = self.treatment_name_var.get().strip()
        category_display = self.treatment_category_combo.get()
        duration_str = self.treatment_duration_var.get().strip()
        price_str = self.treatment_price_var.get().strip()

        if not name or not price_str:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 45
            price = float(price_str)

            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'manicure')

            from university_system.modules.domain.nailbar.services.nailbar_core import TreatmentManager
            TreatmentManager.update_treatment(
                treatment_id, name=name, category=category,
                price=price, duration_minutes=duration
            )

            log_activity('update', 'nailbar_treatment', treatment_id=treatment_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_updated"))
            self._load_treatments()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_treatment_form(self):
        """Clear treatment form"""
        self.treatment_name_var.set("")
        self.treatment_category_combo.set("")
        self.treatment_duration_var.set("45")
        self.treatment_price_var.set("")
        self.treatment_desc_text.delete("1.0", tk.END)

    def add_technician(self):
        """Add a new technician"""
        name = self.tech_name_var.get().strip()
        emp_id = self.tech_emp_id_var.get().strip()
        specialties = self.tech_specialties_var.get().strip()
        certification = self.tech_cert_var.get().strip()
        phone = self.tech_phone_var.get().strip()
        email = self.tech_email_var.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import TechnicianManager
            tech_id = TechnicianManager.add_technician(
                name=name, employee_id=emp_id, specialties=specialties,
                certification=certification, phone=phone, email=email
            )

            log_activity('create', 'nailbar_technician', technician_id=tech_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.technician_added"))
            self._clear_technician_form()
            self._load_technicians()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_technician_form(self):
        """Clear technician form"""
        self.tech_name_var.set("")
        self.tech_emp_id_var.set("")
        self.tech_specialties_var.set("")
        self.tech_cert_var.set("")
        self.tech_phone_var.set("")
        self.tech_email_var.set("")

    def generate_admin_report(self):
        """Generate admin report"""
        try:
            from university_system.modules.domain.nailbar.services.nailbar_core import ReportManager
            report = ReportManager.generate_admin_report()

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.report_failed").format(error=str(e)))

    def email_admin_report(self):
        """Email admin report"""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content:
            self.generate_admin_report()
            report_content = self.report_text.get("1.0", tk.END).strip()

        try:
            from university_system.infrastructure.email.email_service import send_email
            from university_system.infrastructure.email.template_utils import render_template

            with get_db_connection() as conn:
                admin = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                ).fetchone()

            if admin and admin['email']:
                # Use JSON template for email
                subject, body = render_template('commerce/nailbar/admin_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'report_content': report_content
                })

                send_email(
                    recipient_email=admin['email'],
                    subject=subject,
                    body=body
                )

                log_activity('email', 'nailbar_report', user_id=self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.no_admin_email"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.email_failed").format(error=str(e)))

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("nailbar.labels.refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("nailbar.labels.transaction_refunds"),
                 font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("nailbar.labels.search_transactions"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("nailbar.labels.search_by")).pack(side=tk.LEFT, padx=5)
        self.refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text=_t("nailbar.btn.search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text=_t("nailbar.btn.show_all"), command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=2)

        # Transactions table
        trans_frame = ttk.Frame(tab)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'appointment_id', 'date', 'customer', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        self.refunds_tree.heading('transaction_id', text=_t('nailbar.columns.transaction_id'))
        self.refunds_tree.heading('appointment_id', text=_t('nailbar.columns.appointment_id'))
        self.refunds_tree.heading('date', text=_t('nailbar.columns.date'))
        self.refunds_tree.heading('customer', text=_t('nailbar.columns.customer'))
        self.refunds_tree.heading('amount', text=_t('nailbar.columns.amount'))
        self.refunds_tree.heading('payment_method', text=_t('nailbar.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('nailbar.columns.status'))

        self.refunds_tree.column('transaction_id', width=120)
        self.refunds_tree.column('appointment_id', width=120)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=120)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("nailbar.btn.process_refund"), command=self.process_nailbar_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.view_details"), command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.export_csv"), command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.refresh"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with all transactions"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            with get_db_connection() as conn:
                search_term = self.refunds_search_var.get().strip()

                if search_term:
                    query = '''
                        SELECT transaction_id, appointment_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM nailbar_transactions
                        WHERE transaction_id LIKE ? OR appointment_id LIKE ? OR customer_id LIKE ?
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, appointment_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM nailbar_transactions
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    cursor = conn.execute(query)

                transactions = cursor.fetchall()

                for trans in transactions:
                    trans_id, appt_id, created_at, customer_id, amount, payment_method, status = trans

                    # Format payment method
                    payment_display = payment_method.replace('_', ' ').title() if payment_method else 'N/A'

                    # Format status
                    status_display = status.upper() if status else 'COMPLETED'

                    self.refunds_tree.insert('', tk.END, values=(
                        trans_id,
                        appt_id or 'N/A',
                        created_at,
                        customer_id or 'N/A',
                        f"£{amount:.2f}",
                        payment_display,
                        status_display
                    ))

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error loading transactions: {e}")
            logger.error(f"Error loading transactions: {e}")

    def process_nailbar_refund(self):
        """Process a refund for selected nail bar transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("nailbar.msg_titles.no_selection"), "Please select a transaction to refund.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("nailbar.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        appointment_id = values[1]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror(_t("nailbar.msg_titles.error"), "Invalid amount format.")
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo(_t("nailbar.msg_titles.already_refunded"), "This transaction has already been refunded.")
            return

        # Confirm refund
        if not messagebox.askyesno(_t("nailbar.msg_titles.confirm_refund"), f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
            return

        # Get transaction details
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT customer_id, payment_method
                    FROM nailbar_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans_data = cursor.fetchone()

                if not trans_data:
                    messagebox.showerror(_t("nailbar.msg_titles.error"), "Transaction not found in database.")
                    return

                customer_id = trans_data[0]
                payment_method = trans_data[1]

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error fetching transaction details: {e}")
            return

        # Show refund method dialog
        refund_method = self.show_nailbar_refund_method_dialog(amount, transaction_id, customer_id)

        if not refund_method:
            return

        # Process refund
        try:
            with get_db_connection() as conn:
                # Update transaction status to refunded
                conn.execute('''
                    UPDATE nailbar_transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"NAILBAR-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create refunds table if it doesn't exist
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id INTEGER NOT NULL,
                        appointment_id INTEGER,
                        refund_date TEXT NOT NULL,
                        refund_amount REAL NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_reference TEXT UNIQUE,
                        customer_id TEXT,
                        processed_by TEXT,
                        notes TEXT,
                        FOREIGN KEY (transaction_id) REFERENCES nailbar_transactions (transaction_id)
                    )
                ''')

                # Insert refund record
                processed_by = self.current_user.get('username', 'System')
                conn.execute('''
                    INSERT INTO nailbar_refunds
                    (transaction_id, appointment_id, refund_date, refund_amount, refund_method, refund_reference, customer_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, appointment_id if appointment_id != 'N/A' else None,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, customer_id, processed_by))

                conn.commit()

            # If student account refund, add to their account
            if refund_method == 'Student Account':
                success = self.add_nailbar_refund_to_student_account(customer_id, amount, refund_ref)
                if not success:
                    messagebox.showwarning(_t("nailbar.msg_titles.partial_success"),
                                         "Refund recorded but failed to credit student account. Please credit manually.")

            # Send refund receipt email
            self.send_nailbar_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_nailbar_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

            log_activity('refund', 'nailbar_transaction', details={'transaction_id': transaction_id, 'amount': amount})

            messagebox.showinfo(_t("nailbar.msg_titles.refund_processed"),
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error processing refund: {e}")
            logger.error(f"Error processing refund: {e}")

    def show_nailbar_refund_method_dialog(self, amount, transaction_id, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

        # Show student account balance if customer_id available and finance integration enabled
        if customer_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text=_t("nailbar.labels.student_finance_account"), padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text=_t("nailbar.labels.select_refund_method"), font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not customer_id:
                messagebox.showerror(_t("nailbar.msg_titles.error"), "No customer ID associated with this transaction.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("nailbar.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id and FINANCE_AVAILABLE:
            ttk.Button(button_frame, text=_t("nailbar.labels.student_finance_account"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("nailbar.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_nailbar_refund_to_student_account(self, customer_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            return False

        try:
            with get_db_connection() as conn:
                # Check if student finance account exists
                cursor = conn.execute(
                    'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                    (customer_id,)
                )
                account = cursor.fetchone()

                if not account:
                    # Create account with refund amount
                    conn.execute('''
                        INSERT INTO student_finance_accounts (student_id, balance, created_at)
                        VALUES (?, ?, ?)
                    ''', (customer_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    # Get the new account_id
                    cursor = conn.execute(
                        'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                        (customer_id,)
                    )
                    account = cursor.fetchone()
                    account_id = account[0]
                    balance_before = 0
                    balance_after = amount
                else:
                    # Update existing account
                    account_id = account[0]
                    balance_before = account[1]
                    balance_after = balance_before + amount

                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = balance + ?
                        WHERE student_id = ?
                    ''', (amount, customer_id))

                # Record transaction
                processed_by = self.current_user.get('username', 'System')
                conn.execute('''
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, reference_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, customer_id, 'credit', amount, balance_before, balance_after,
                      'Nail Bar/Salon Service Refund', refund_ref, processed_by))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def send_nailbar_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            return

        try:
            from university_system.modules.shared.utils.finance_integration import get_student_info
            from university_system.infrastructure.email.template_utils import render_template

            # Get customer email
            customer_info = get_student_info(customer_id)
            if not customer_info or not customer_info.get('email'):
                logger.warning(f"No email found for customer {customer_id}")
                return

            customer_email = customer_info['email']
            customer_name = customer_info.get('full_name', 'Valued Customer')

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account' and FINANCE_AVAILABLE:
                try:
                    new_balance = get_student_finance_account_balance(customer_id)
                    if new_balance is not None:
                        balance_text = f"Your updated account balance is: £{new_balance:.2f}"
                except:
                    pass

            # Use JSON template for email
            subject, body = render_template('commerce/nailbar/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'original_transaction': str(transaction_id),
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            })

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Refund receipt sent to {customer_email}")
            else:
                logger.warning(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending refund receipt: {e}")

    def notify_nailbar_finance_gui(self, transaction_id, amount, method, refund_ref, customer_id):
        """Notify finance GUI about the refund"""
        try:
            with get_db_connection() as conn:
                # Insert into finance_refunds table (table already exists)
                processed_by = self.current_user.get('username', 'System')
                conn.execute('''
                    INSERT INTO finance_refunds
                    (transaction_id, refund_reference, department, amount, refund_method,
                     refund_date, student_id, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (str(transaction_id), refund_ref, 'Nail Bar/Salon', amount, method,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), customer_id, processed_by,
                      'Nail Bar/Salon service refund'))

                conn.commit()

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information for selected transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("nailbar.msg_titles.no_selection"), "Please select a transaction to view details.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("nailbar.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        appointment_id = values[1]

        try:
            with get_db_connection() as conn:
                # Get transaction details
                cursor = conn.execute('''
                    SELECT t.*, a.appointment_date, a.appointment_time, a.technician_id, a.status as appt_status
                    FROM nailbar_transactions t
                    LEFT JOIN nailbar_appointments a ON t.appointment_id = a.appointment_id
                    WHERE t.transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("nailbar.msg_titles.error"), "Transaction not found.")
                    return

                # Get appointment treatments if appointment exists
                treatments_text = ""
                if appointment_id and appointment_id != 'N/A':
                    cursor = conn.execute('''
                        SELECT at.treatment_id, t.name, t.category, t.duration_minutes, t.price
                        FROM nailbar_appointment_treatments at
                        LEFT JOIN nailbar_treatments t ON at.treatment_id = t.treatment_id
                        WHERE at.appointment_id = ?
                    ''', (appointment_id,))

                    treatments = cursor.fetchall()
                    if treatments:
                        for treatment in treatments:
                            treat_id, name, category, duration_minutes, price = treatment
                            treatments_text += f"\n{name} ({category})\n"
                            treatments_text += f"  Duration: {duration_minutes} mins | Price: £{price:.2f}\n"

            # Create details window
            details_window = tk.Toplevel(self.parent)
            details_window.title(f"Transaction Details - {transaction_id}")
            details_window.geometry("600x600")
            details_window.transient(self.parent)

            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Transaction information
            from tkinter.scrolledtext import ScrolledText
            info_text = ScrolledText(main_frame, width=70, height=30, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)

            details = f"""TRANSACTION DETAILS
═══════════════════════════════════════════════════════

Transaction ID:     {trans[0]}
Appointment ID:     {trans[1] if trans[1] else 'N/A'}
Customer ID:        {trans[2]}
Payment Method:     {trans[4]}
Transaction Type:   {trans[5]}
Reference Number:   {trans[7] or 'N/A'}
Status:             {trans[8].upper()}
Processed By:       {trans[11] or 'System'}
Date:               {trans[10]}

Appointment Date:   {trans[12] if len(trans) > 12 and trans[12] else 'N/A'}
Appointment Time:   {trans[13] if len(trans) > 13 and trans[13] else 'N/A'}
Appointment Status: {trans[15].upper() if len(trans) > 15 and trans[15] else 'N/A'}

═══════════════════════════════════════════════════════
TREATMENTS/SERVICES
═══════════════════════════════════════════════════════
{treatments_text if treatments_text else 'No treatments recorded'}

═══════════════════════════════════════════════════════
PAYMENT BREAKDOWN
═══════════════════════════════════════════════════════

Service Amount:     £{trans[3]:.2f}
Tip Amount:         £{trans[6]:.2f}
───────────────────────────────────────────────────────
TOTAL:              £{(trans[3] + trans[6]):.2f}

═══════════════════════════════════════════════════════
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text=_t("nailbar.btn.close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error loading transaction details: {e}")
            logger.error(f"Error loading transaction details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"nailbar_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Appointment ID', 'Date', 'Customer',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for item in self.refunds_tree.get_children():
                    values = self.refunds_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo(_t("nailbar.msg_titles.export_successful"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.export_error"), f"Error exporting data: {e}")
            logger.error(f"Error exporting data: {e}")


def launch_nailbar_gui(parent=None, auth=None):
    """Launch the Nail Bar GUI"""
    return NailBarGUI(parent, auth)
