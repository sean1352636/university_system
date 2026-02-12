"""Barber Shop GUI Module

Provides a comprehensive GUI for barber shop operations including
appointments, services, staff, and reporting with email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import csv
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict

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
    from university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None
    render_template = None

logger = logging.getLogger(__name__)


class BarberGUI:
    """Main GUI class for Barber Shop operations"""

    def __init__(self, parent: tk.Toplevel, auth=None):
        """Initialize the Barber Shop GUI - Function 1"""
        self.parent = parent
        self.auth = auth

        # Try to get auth from shared context if not provided
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check authentication
        if not self._check_authentication():
            return

        self.parent.title(_t("barber.window_title"))
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Initialize database
        self._init_database()

        # Create main interface
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

        log_activity('access', 'barber_shop')

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("barber.window_title"),
                "You must be logged in to access the Barber Shop module.\n\n"
                "Please log in through the main GUI first."
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("barber.window_title"),
                "You must be logged in to access the Barber Shop module.\n\n"
                "Please launch this module from the main GUI after logging in."
            )
            if self.parent:
                self.parent.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("barber.window_title"),
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

        ttk.Label(header_frame, text=_t("barber.title"),
                 font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        user_info = f"{self.current_user.get('username')} ({self.current_user.get('role')})"
        ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_appointments_tab()
        self.create_customers_tab()
        self.create_services_tab()
        self.create_staff_tab()
        self.create_finance_tab()
        self.create_analytics_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

        # Bottom buttons
        btn_frame = ttk.Frame(self.parent, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("common.refresh"),
                  command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("barber.btn.return_home"),
                  command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Initialize database tables - Function 3"""
        from university_system.modules.domain.barber.services.barber_core import (
            init_barber_db, init_extended_barber_db
        )
        try:
            init_barber_db()
            init_extended_barber_db()
        except Exception as e:
            logger.error(f"Failed to initialize barber database: {e}")

    def return_to_homescreen(self):
        """Return to the main homescreen - Function 4"""
        if messagebox.askyesno(_t("common.confirm"), _t("barber.confirm.exit")):
            self.parent.destroy()

    def refresh_all_data(self):
        """Refresh all data in the GUI - Function 5"""
        try:
            self._load_appointments()
            self._load_services()
            self._load_staff()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")

    def create_appointments_tab(self):
        """Create the appointments management tab - Function 6"""
        appointments_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(appointments_frame, text=_t("barber.tabs.appointments"))

        # Top - Book new appointment
        book_frame = ttk.LabelFrame(appointments_frame, text=_t("barber.labels.book_appointment"), padding="10")
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

        ttk.Label(cust_frame, text="Booking for:", font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_name, font=('Helvetica', 10)).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text="Email:").pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_email if user_email else "Not set",
                 foreground='gray' if not user_email else 'black').pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text="ID:").pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_id if user_id else "N/A").pack(side=tk.LEFT, padx=5)

        # Service and scheduling row
        sched_frame = ttk.Frame(book_frame)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text=_t("barber.labels.service") + ":").pack(side=tk.LEFT)
        self.appt_service_combo = ttk.Combobox(sched_frame, state="readonly", width=25)
        self.appt_service_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.barber") + ":").pack(side=tk.LEFT)
        self.appt_staff_combo = ttk.Combobox(sched_frame, state="readonly", width=20)
        self.appt_staff_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.date") + ":").pack(side=tk.LEFT)
        self.appt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(sched_frame, textvariable=self.appt_date_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.time") + ":").pack(side=tk.LEFT)
        self.appt_time_combo = ttk.Combobox(sched_frame, state="readonly", width=10)
        self.appt_time_combo['values'] = self._get_time_slots()
        self.appt_time_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(sched_frame, text=_t("barber.btn.book_appointment"),
                  command=self.book_appointment).pack(side=tk.LEFT, padx=20)

        # Today's appointments
        today_frame = ttk.LabelFrame(appointments_frame, text=_t("barber.labels.todays_appointments"), padding="5")
        today_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('number', 'time', 'customer', 'service', 'barber', 'status', 'payment')
        self.appointments_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=12)

        self.appointments_tree.heading('number', text=_t("barber.labels.appt_number"))
        self.appointments_tree.heading('time', text=_t("barber.labels.time"))
        self.appointments_tree.heading('customer', text=_t("barber.labels.customer"))
        self.appointments_tree.heading('service', text=_t("barber.labels.service"))
        self.appointments_tree.heading('barber', text=_t("barber.labels.barber"))
        self.appointments_tree.heading('status', text=_t("barber.labels.status"))
        self.appointments_tree.heading('payment', text=_t("barber.labels.payment_status"))

        self.appointments_tree.column('number', width=120)
        self.appointments_tree.column('time', width=70)
        self.appointments_tree.column('customer', width=150)
        self.appointments_tree.column('service', width=150)
        self.appointments_tree.column('barber', width=120)
        self.appointments_tree.column('status', width=100)
        self.appointments_tree.column('payment', width=100)

        scrollbar = ttk.Scrollbar(today_frame, orient=tk.VERTICAL, command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons - Row 1
        action_frame = ttk.Frame(appointments_frame)
        action_frame.pack(fill=tk.X, pady=(5, 2))

        ttk.Button(action_frame, text=_t("barber.btn.check_in"),
                  command=self.check_in_customer).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.start_service"),
                  command=self.start_service).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.complete_service"),
                  command=self.complete_service).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.process_payment"),
                  command=self.process_payment).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.cancel_appointment"),
                  command=self.cancel_appointment).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.reschedule"),
                  command=self.reschedule_appointment).pack(side=tk.LEFT, padx=3)

        # Action buttons - Row 2 (Additional features)
        action_frame2 = ttk.Frame(appointments_frame)
        action_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(action_frame2, text="Mark No-Show",
                  command=self.mark_no_show).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Set Reminder",
                  command=self.set_appointment_reminder).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="View History",
                  command=self.view_appointment_history).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Weekly Calendar",
                  command=self.show_weekly_calendar).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Bulk Cancel",
                  command=self.bulk_cancel_appointments).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="View Waitlist",
                  command=self.view_waitlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Add to Waitlist",
                  command=self.add_to_waitlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Block Time Slot",
                  command=self.block_time_slot).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Recurring Appt",
                  command=self.recurring_appointment).pack(side=tk.LEFT, padx=3)

    def create_services_tab(self):
        """Create the services management tab - Function 7"""
        services_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(services_frame, text=_t("barber.tabs.services"))

        # Left - Services list
        list_frame = ttk.LabelFrame(services_frame, text=_t("barber.labels.service_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ('id', 'name', 'type', 'duration', 'price')
        self.services_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.services_tree.heading('id', text='ID')
        self.services_tree.heading('name', text=_t("barber.labels.service_name"))
        self.services_tree.heading('type', text=_t("barber.labels.type"))
        self.services_tree.heading('duration', text=_t("barber.labels.duration"))
        self.services_tree.heading('price', text=_t("barber.labels.price"))

        self.services_tree.column('id', width=50)
        self.services_tree.column('name', width=150)
        self.services_tree.column('type', width=120)
        self.services_tree.column('duration', width=80)
        self.services_tree.column('price', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.services_tree.yview)
        self.services_tree.configure(yscrollcommand=scrollbar.set)

        self.services_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add/Edit service
        edit_frame = ttk.LabelFrame(services_frame, text=_t("barber.labels.add_service"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("barber.labels.service_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.service_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.service_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.type") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.service_type_combo = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.service_type_combo['values'] = list(self._get_service_types().values())
        self.service_type_combo.grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.duration") + " (min):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.service_duration_var = tk.StringVar(value="30")
        ttk.Entry(edit_frame, textvariable=self.service_duration_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.price") + " (£):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.service_price_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.service_price_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.description") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.service_desc_text = tk.Text(edit_frame, width=25, height=3)
        self.service_desc_text.grid(row=4, column=1, pady=2)

        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("barber.btn.add_service"),
                  command=self.add_service).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("barber.btn.update_service"),
                  command=self.update_service).pack(side=tk.LEFT, padx=2)

    def create_staff_tab(self):
        """Create the staff management tab - Function 8"""
        staff_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(staff_frame, text=_t("barber.tabs.staff"))

        # Left - Staff list
        list_frame = ttk.LabelFrame(staff_frame, text=_t("barber.labels.staff_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ('id', 'name', 'employee_id', 'specialties', 'status')
        self.staff_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.staff_tree.heading('id', text='ID')
        self.staff_tree.heading('name', text=_t("barber.labels.name"))
        self.staff_tree.heading('employee_id', text=_t("barber.labels.employee_id"))
        self.staff_tree.heading('specialties', text=_t("barber.labels.specialties"))
        self.staff_tree.heading('status', text=_t("barber.labels.status"))

        self.staff_tree.column('id', width=50)
        self.staff_tree.column('name', width=150)
        self.staff_tree.column('employee_id', width=100)
        self.staff_tree.column('specialties', width=200)
        self.staff_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=scrollbar.set)

        self.staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add staff
        edit_frame = ttk.LabelFrame(staff_frame, text=_t("barber.labels.add_staff"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("barber.labels.name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.staff_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.employee_id") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.staff_emp_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_emp_id_var, width=25).grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.specialties") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.staff_specialties_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_specialties_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.phone") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.staff_phone_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_phone_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.email") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.staff_email_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_email_var, width=25).grid(row=4, column=1, pady=2)

        ttk.Button(edit_frame, text=_t("barber.btn.add_staff"),
                  command=self.add_staff).grid(row=5, column=0, columnspan=2, pady=10)

    def create_reports_tab(self):
        """Create the reports tab - Function 9"""
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text=_t("barber.tabs.reports"))

        # Report options
        options_frame = ttk.LabelFrame(reports_frame, text=_t("barber.labels.report_options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text=_t("barber.labels.date_from") + ":").pack(side=tk.LEFT)
        self.report_from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text=_t("barber.labels.date_to") + ":").pack(side=tk.LEFT)
        self.report_to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(options_frame, text=_t("barber.btn.generate_report"),
                  command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(options_frame, text=_t("barber.btn.email_report"),
                  command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display = ttk.LabelFrame(reports_frame, text=_t("barber.labels.report_output"), padding="5")
        report_display.pack(fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(report_display, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_display, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_customers_tab(self):
        """Create the customers management tab"""
        customers_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(customers_frame, text="Customers")

        # Search frame
        search_frame = ttk.LabelFrame(customers_frame, text="Search Customers", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.customer_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.customer_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.search_customers).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Show All", command=self._load_customers).pack(side=tk.LEFT, padx=5)

        # Customer list
        list_frame = ttk.LabelFrame(customers_frame, text="Customer List", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'name', 'email', 'phone', 'visits', 'last_visit', 'favorite')
        self.customers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.customers_tree.heading('id', text='ID')
        self.customers_tree.heading('name', text='Name')
        self.customers_tree.heading('email', text='Email')
        self.customers_tree.heading('phone', text='Phone')
        self.customers_tree.heading('visits', text='Visits')
        self.customers_tree.heading('last_visit', text='Last Visit')
        self.customers_tree.heading('favorite', text='Favorite')

        self.customers_tree.column('id', width=50)
        self.customers_tree.column('name', width=150)
        self.customers_tree.column('email', width=180)
        self.customers_tree.column('phone', width=120)
        self.customers_tree.column('visits', width=60)
        self.customers_tree.column('last_visit', width=100)
        self.customers_tree.column('favorite', width=70)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.customers_tree.yview)
        self.customers_tree.configure(yscrollcommand=scrollbar.set)

        self.customers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        action_frame = ttk.Frame(customers_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="Create Profile", command=self.create_customer_profile).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Details", command=self.view_customer_details).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Add Notes", command=self.add_customer_notes).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Favorites", command=self.view_favorite_customers).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Send Message", command=self.send_customer_message).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Feedback", command=self.view_customer_feedback).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Merge Profiles", command=self.merge_customer_profiles).pack(side=tk.LEFT, padx=3)

        # Import/Export buttons
        action_frame2 = ttk.Frame(customers_frame)
        action_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(action_frame2, text="Export List", command=self.export_customer_list).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Import Customers", command=self.import_customers).pack(side=tk.LEFT, padx=3)

    def create_finance_tab(self):
        """Create the finance management tab"""
        finance_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(finance_frame, text="Finance")

        # Daily summary frame
        summary_frame = ttk.LabelFrame(finance_frame, text="Daily Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        self.daily_sales_label = ttk.Label(summary_frame, text="Today's Sales: £0.00", font=('Helvetica', 12, 'bold'))
        self.daily_sales_label.pack(side=tk.LEFT, padx=20)

        self.cash_drawer_label = ttk.Label(summary_frame, text="Cash Drawer: £0.00")
        self.cash_drawer_label.pack(side=tk.LEFT, padx=20)

        self.outstanding_label = ttk.Label(summary_frame, text="Outstanding: £0.00")
        self.outstanding_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(summary_frame, text="Refresh", command=self._update_finance_summary).pack(side=tk.RIGHT, padx=5)

        # Transactions list
        trans_frame = ttk.LabelFrame(finance_frame, text="Recent Transactions", padding="5")
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'date', 'customer', 'service', 'amount', 'method', 'status')
        self.finance_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=10)

        self.finance_tree.heading('id', text='ID')
        self.finance_tree.heading('date', text='Date')
        self.finance_tree.heading('customer', text='Customer')
        self.finance_tree.heading('service', text='Service')
        self.finance_tree.heading('amount', text='Amount')
        self.finance_tree.heading('method', text='Method')
        self.finance_tree.heading('status', text='Status')

        self.finance_tree.column('id', width=50)
        self.finance_tree.column('date', width=100)
        self.finance_tree.column('customer', width=150)
        self.finance_tree.column('service', width=150)
        self.finance_tree.column('amount', width=80)
        self.finance_tree.column('method', width=100)
        self.finance_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.finance_tree.yview)
        self.finance_tree.configure(yscrollcommand=scrollbar.set)

        self.finance_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        action_frame = ttk.Frame(finance_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="Apply Discount", command=self.apply_discount).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Issue Refund", command=self.issue_refund).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Daily Sales", command=self.view_daily_sales).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Financial Report", command=self.generate_financial_report).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Cash Drawer", command=self.track_cash_drawer).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Create Gift Card", command=self.create_gift_card).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Redeem Gift Card", command=self.redeem_gift_card).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Outstanding Payments", command=self.view_outstanding_payments).pack(side=tk.LEFT, padx=3)

    def create_analytics_tab(self):
        """Create the analytics tab"""
        analytics_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(analytics_frame, text="Analytics")

        # Dashboard summary
        dashboard_frame = ttk.LabelFrame(analytics_frame, text="Dashboard", padding="10")
        dashboard_frame.pack(fill=tk.X, pady=(0, 10))

        # Summary metrics
        metrics_frame = ttk.Frame(dashboard_frame)
        metrics_frame.pack(fill=tk.X)

        self.metric_appointments = ttk.Label(metrics_frame, text="Today's Appointments: 0", font=('Helvetica', 10, 'bold'))
        self.metric_appointments.pack(side=tk.LEFT, padx=20)

        self.metric_revenue = ttk.Label(metrics_frame, text="This Week's Revenue: £0.00", font=('Helvetica', 10, 'bold'))
        self.metric_revenue.pack(side=tk.LEFT, padx=20)

        self.metric_customers = ttk.Label(metrics_frame, text="New Customers: 0", font=('Helvetica', 10, 'bold'))
        self.metric_customers.pack(side=tk.LEFT, padx=20)

        ttk.Button(dashboard_frame, text="Show Full Dashboard", command=self.show_dashboard).pack(pady=10)

        # Reports section
        reports_frame = ttk.LabelFrame(analytics_frame, text="Analytics Reports", padding="10")
        reports_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Report buttons
        btn_frame = ttk.Frame(reports_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Peak Hours Report", command=self.generate_peak_hours_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Customer Retention", command=self.customer_retention_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export PDF", command=self.export_report_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Schedule Reports", command=self.schedule_automated_reports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Audit Log", command=self.view_audit_log).pack(side=tk.LEFT, padx=5)

        # Report output
        self.analytics_text = tk.Text(reports_frame, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(reports_frame, orient=tk.VERTICAL, command=self.analytics_text.yview)
        self.analytics_text.configure(yscrollcommand=scrollbar.set)

        self.analytics_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_time_slots(self) -> list:
        """Get available time slots - Function 10"""
        from university_system.modules.domain.barber.services.barber_core import TIME_SLOTS
        return TIME_SLOTS

    def _get_service_types(self) -> dict:
        """Get service types - Function 11"""
        from university_system.modules.domain.barber.services.barber_core import SERVICE_TYPES
        return SERVICE_TYPES

    def _load_appointments(self):
        """Load appointments into the treeview - Function 12"""
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)

        try:
            from university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appointments = AppointmentManager.get_todays_appointments()

            for appt in appointments:
                self.appointments_tree.insert('', tk.END, values=(
                    appt['appointment_number'],
                    appt['appointment_time'],
                    appt['customer_name'],
                    appt['service_name'],
                    appt.get('staff_name', 'Any'),
                    appt['status'],
                    appt['payment_status']
                ))
        except Exception as e:
            logger.error(f"Error loading appointments: {e}")

    def _load_services(self):
        """Load services into the treeview - Function 13"""
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)

        try:
            from university_system.modules.domain.barber.services.barber_core import ServiceManager
            services = ServiceManager.get_all_services()

            service_types = self._get_service_types()
            service_list = []
            for svc in services:
                type_name = service_types.get(svc['service_type'], svc['service_type'])
                self.services_tree.insert('', tk.END, values=(
                    svc['service_id'],
                    svc['name'],
                    type_name,
                    f"{svc['duration_minutes']} min",
                    f"£{svc['price']:.2f}"
                ))
                service_list.append(f"{svc['service_id']}: {svc['name']} (£{svc['price']:.2f})")

            self.appt_service_combo['values'] = service_list

        except Exception as e:
            logger.error(f"Error loading services: {e}")

    def _load_staff(self):
        """Load staff into the treeview - Function 14"""
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        try:
            from university_system.modules.domain.barber.services.barber_core import StaffManager
            staff = StaffManager.get_all_staff()

            staff_list = ['Any']
            for s in staff:
                status = 'Active' if s.get('is_active', 1) else 'Inactive'
                self.staff_tree.insert('', tk.END, values=(
                    s['staff_id'],
                    s['name'],
                    s.get('employee_id', ''),
                    s.get('specialties', ''),
                    status
                ))
                staff_list.append(f"{s['staff_id']}: {s['name']}")

            self.appt_staff_combo['values'] = staff_list
            self.appt_staff_combo.set('Any')

        except Exception as e:
            logger.error(f"Error loading staff: {e}")

    def book_appointment(self):
        """Book a new appointment - Function 15"""
        # Use current user details - build full name from first/last if available
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            customer_name = f"{first_name} {last_name}"
        else:
            customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        customer_email = self.current_user.get('email', '')
        customer_phone = self.current_user.get('phone', '')
        # Use student_id, then username, then id as fallback for customer_id
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', 'guest')))

        service_str = self.appt_service_combo.get()
        staff_str = self.appt_staff_combo.get()
        appt_date = self.appt_date_var.get().strip()
        appt_time = self.appt_time_combo.get()

        if not service_str or not appt_date or not appt_time:
            messagebox.showerror(_t("common.error"), "Please select a service, date and time.")
            return

        try:
            service_id = int(service_str.split(':')[0])
            staff_id = None
            if staff_str != 'Any':
                staff_id = int(staff_str.split(':')[0])

            from university_system.modules.domain.barber.services.barber_core import AppointmentManager

            appt_id, appt_number = AppointmentManager.book_appointment(
                customer_id=customer_id,
                customer_name=customer_name,
                service_id=service_id,
                appointment_date=appt_date,
                appointment_time=appt_time,
                staff_id=staff_id,
                customer_email=customer_email,
                customer_phone=customer_phone
            )

            log_activity('create', 'barber_appointment',
                        details={'appointment_id': appt_id})

            messagebox.showinfo(_t("common.success"),
                              _t("barber.messages.appointment_booked").format(appointment_number=appt_number))

            self._clear_appointment_form()
            self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.booking_failed").format(error=str(e)))

    def _clear_appointment_form(self):
        """Clear appointment form - Function 16"""
        self.appt_service_combo.set("")
        self.appt_staff_combo.set("Any")
        self.appt_time_combo.set("")

    def check_in_customer(self):
        """Check in customer for appointment - Function 17"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'checked_in',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.checked_in"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def start_service(self):
        """Mark service as started - Function 18"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'in_progress',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.service_started"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def complete_service(self):
        """Mark service as completed - Function 19"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'completed',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.service_completed"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment for appointment - Function 20"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]
        payment_status = item['values'][6]

        if payment_status == 'paid':
            messagebox.showinfo(_t("common.info"), _t("barber.messages.already_paid"))
            return

        from university_system.modules.domain.barber.services.barber_core import AppointmentManager, TransactionManager
        appt = AppointmentManager.get_appointment_by_number(appt_number)

        if not appt:
            return

        # Get customer details
        customer_id = appt.get('customer_id', self.current_user.get('user_id', 'guest'))
        customer_email = appt.get('customer_email') or self.current_user.get('email', '')
        customer_name = appt.get('customer_name') or self.current_user.get('full_name', '')

        # Payment dialog
        payment_window = tk.Toplevel(self.parent)
        payment_window.title("Process Payment")
        payment_window.geometry("500x500")
        payment_window.transient(self.parent)
        payment_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(payment_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text="Payment Details",
                 font=('Helvetica', 16, 'bold')).pack(pady=(0, 15))

        # Appointment info frame
        info_frame = ttk.LabelFrame(main_frame, text="Appointment Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text=f"Appointment: {appt_number}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Customer: {customer_name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Service: {appt['service_name']}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Price: £{appt['price']:.2f}",
                 font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Tip frame
        tip_frame = ttk.Frame(main_frame)
        tip_frame.pack(fill=tk.X, pady=10)
        ttk.Label(tip_frame, text="Add Tip (£):").pack(side=tk.LEFT)
        tip_var = tk.StringVar(value="0")
        ttk.Entry(tip_frame, textvariable=tip_var, width=10).pack(side=tk.LEFT, padx=10)

        # Payment method frame
        method_frame = ttk.LabelFrame(main_frame, text="Select Payment Method", padding="10")
        method_frame.pack(fill=tk.X, pady=10)

        payment_method_var = tk.StringVar(value="card")

        # Cash option
        ttk.Radiobutton(method_frame, text="💵 Cash", variable=payment_method_var,
                       value="cash").pack(anchor=tk.W, pady=2)

        # Card option
        ttk.Radiobutton(method_frame, text="💳 Card", variable=payment_method_var,
                       value="card").pack(anchor=tk.W, pady=2)

        # Student Account option with balance
        student_balance = 0.0
        balance_text = "Balance: Not available"
        if FINANCE_AVAILABLE:
            try:
                ensure_student_finance_account_exists(customer_id)
                student_balance = get_student_finance_account_balance(customer_id) or 0.0
                balance_text = f"Balance: £{student_balance:.2f}"
            except Exception as e:
                logger.error(f"Error getting student balance: {e}")

        student_frame = ttk.Frame(method_frame)
        student_frame.pack(anchor=tk.W, fill=tk.X)
        ttk.Radiobutton(student_frame, text="🎓 Student Account",
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
                total = appt['price'] + tip
                total_label.config(text=f"Total: £{total:.2f}")
            except ValueError:
                pass

        tip_var.trace('w', update_total)
        total_label = ttk.Label(total_frame, text=f"Total: £{appt['price']:.2f}",
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
                messagebox.showerror("Error", "Invalid tip amount.")
                return

            total_amount = appt['price'] + tip

            # Process based on payment method
            try:
                transaction_ref = f"BARBER-{appt['appointment_id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                if method == 'student_account':
                    # Check if finance integration available
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror("Error", "Student account payment is not available.")
                        return

                    # Check balance
                    if student_balance < total_amount:
                        messagebox.showerror("Insufficient Balance",
                            f"Your account balance (£{student_balance:.2f}) is insufficient.\n"
                            f"Required: £{total_amount:.2f}")
                        return

                    # Process student account payment
                    result = process_student_finance_account_payment(
                        student_id=customer_id,
                        amount=total_amount,
                        description=f"Barber service: {appt['service_name']}",
                        transaction_source="Barber",
                        transaction_ref=transaction_ref,
                        processed_by=self.current_user.get('username', 'system')
                    )

                    if not result.get('success'):
                        messagebox.showerror("Payment Failed", result.get('message', 'Unknown error'))
                        return

                    payment_id = result.get('transaction_id')

                else:
                    # Cash or Card payment - record to central finance
                    if FINANCE_AVAILABLE:
                        payment_id = record_payment_to_finance(
                            student_id=customer_id,
                            amount=total_amount,
                            payment_method=method.title(),
                            transaction_source="Barber",
                            transaction_ref=transaction_ref,
                            notes=f"Service: {appt['service_name']}" + (f", Tip: £{tip:.2f}" if tip > 0 else ""),
                            created_by=self.current_user.get('username', 'system')
                        )
                    else:
                        payment_id = None

                # Record in barber transactions table
                local_trans_id = TransactionManager.process_payment(
                    appointment_id=appt['appointment_id'],
                    amount=appt['price'],
                    payment_method=method,
                    customer_id=customer_id,
                    tip_amount=tip,
                    processed_by=self.current_user.get('username')
                )

                # Send receipt email if requested
                if send_receipt_var.get() and customer_email and EMAIL_AVAILABLE:
                    self._send_payment_receipt(
                        appt=appt,
                        total_amount=total_amount,
                        tip=tip,
                        payment_method=method,
                        transaction_ref=transaction_ref,
                        customer_email=customer_email,
                        customer_name=customer_name
                    )

                log_activity('payment', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id'],
                                   'amount': total_amount,
                                   'method': method})

                messagebox.showinfo("Success",
                    f"Payment of £{total_amount:.2f} processed successfully!\n\n"
                    f"Method: {method.replace('_', ' ').title()}\n"
                    f"Reference: {transaction_ref}")
                payment_window.destroy()
                self._load_appointments()

            except Exception as e:
                logger.error(f"Payment processing error: {e}")
                messagebox.showerror("Error", f"Payment failed: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text="Confirm Payment",
                  command=confirm_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _send_payment_receipt(self, appt: dict, total_amount: float, tip: float,
                              payment_method: str, transaction_ref: str,
                              customer_email: str, customer_name: str):
        """Send payment receipt email to customer."""
        try:
            # Render email from template
            subject, body = render_template('commerce/barber/payment_receipt', {
                'customer_name': customer_name,
                'appointment_number': appt['appointment_number'],
                'service_name': appt['service_name'],
                'barber_name': appt.get('staff_name', 'Any available'),
                'appointment_date': appt.get('appointment_date', datetime.now().strftime('%Y-%m-%d')),
                'appointment_time': appt.get('appointment_time', ''),
                'service_price': f"£{appt['price']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total_amount:.2f}",
                'payment_method': payment_method.replace('_', ' ').title(),
                'transaction_ref': transaction_ref
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Barber Shop Receipt - {appt['appointment_number']}"
                body = f"Dear {customer_name},\n\nThank you for your payment of £{total_amount:.2f}.\nReference: {transaction_ref}"

            # Try to send email
            try:
                from university_system.infrastructure.email.email_service import send_email as send_email_func
                send_email_func(customer_email, subject, body)
                logger.info(f"Receipt sent to {customer_email}")
            except ImportError:
                logger.warning("Email service not available - receipt not sent")
            except Exception as email_err:
                logger.error(f"Email sending failed: {email_err}")

        except Exception as e:
            logger.error(f"Failed to prepare receipt email: {e}")

    def send_receipt_email(self, appointment: dict, transaction_id: int, tip: float = 0):
        """Send receipt email to customer - Function 21"""
        try:
            from university_system.infrastructure.email.email_service import send_email

            total = appointment['price'] + tip
            subject = _t("barber.email.receipt_subject").format(appointment_number=appointment['appointment_number'])

            body = _t("barber.email.receipt_body").format(
                customer_name=appointment['customer_name'],
                appointment_number=appointment['appointment_number'],
                service=appointment['service_name'],
                barber=appointment.get('staff_name', 'N/A'),
                service_price=f"£{appointment['price']:.2f}",
                tip=f"£{tip:.2f}",
                total=f"£{total:.2f}",
                date=datetime.now().strftime('%Y-%m-%d %H:%M')
            )

            send_email(
                recipient_email=appointment['customer_email'],
                subject=subject,
                body=body
            )

            from university_system.modules.domain.barber.services.barber_core import TransactionManager
            TransactionManager.mark_receipt_sent(transaction_id)

            logger.info(f"Receipt sent to {appointment['customer_email']}")

        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def cancel_appointment(self):
        """Cancel an appointment - Function 22"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        if not messagebox.askyesno(_t("common.confirm"), _t("barber.confirm.cancel_appointment")):
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.cancel_appointment(appt['appointment_id'], 'Cancelled by user')
                log_activity('cancel', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("barber.messages.appointment_cancelled"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def reschedule_appointment(self):
        """Reschedule an appointment - Function 23"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        from university_system.modules.domain.barber.services.barber_core import AppointmentManager
        appt = AppointmentManager.get_appointment_by_number(appt_number)

        if not appt:
            return

        # Reschedule dialog
        resched_window = tk.Toplevel(self.parent)
        resched_window.title(_t("barber.labels.reschedule"))
        resched_window.geometry("350x200")
        resched_window.transient(self.parent)
        resched_window.grab_set()

        ttk.Label(resched_window, text=f"{_t('barber.labels.appointment')}: {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(resched_window)
        frame.pack(pady=10)

        ttk.Label(frame, text=_t("barber.labels.new_date") + ":").grid(row=0, column=0, pady=5)
        new_date_var = tk.StringVar(value=appt['appointment_date'])
        ttk.Entry(frame, textvariable=new_date_var, width=12).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("barber.labels.new_time") + ":").grid(row=1, column=0, pady=5)
        new_time_combo = ttk.Combobox(frame, state="readonly", width=10)
        new_time_combo['values'] = self._get_time_slots()
        new_time_combo.set(appt['appointment_time'])
        new_time_combo.grid(row=1, column=1, pady=5)

        def confirm_reschedule():
            new_date = new_date_var.get().strip()
            new_time = new_time_combo.get()

            try:
                AppointmentManager.reschedule_appointment(appt['appointment_id'], new_date, new_time)
                log_activity('reschedule', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})

                # Send email confirmation to customer
                if appt.get('customer_email') and EMAIL_AVAILABLE:
                    try:
                        from university_system.infrastructure.email.email_service import send_email

                        # Format the date nicely
                        from datetime import datetime as dt
                        try:
                            date_obj = dt.strptime(new_date, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%A, %B %d, %Y')
                        except (ValueError, TypeError):
                            formatted_date = new_date

                        # Get old date/time for reference
                        try:
                            old_date_obj = dt.strptime(appt['appointment_date'], '%Y-%m-%d')
                            old_formatted_date = old_date_obj.strftime('%A, %B %d, %Y')
                        except (ValueError, TypeError):
                            old_formatted_date = appt['appointment_date']

                        # Render email from template
                        subject, body = render_template('commerce/barber/appointment_rescheduled', {
                            'customer_name': appt['customer_name'],
                            'old_date': old_formatted_date,
                            'old_time': appt['appointment_time'],
                            'new_date': formatted_date,
                            'new_time': new_time,
                            'barber_name': appt.get('staff_name', 'Any available')
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = "Appointment Rescheduled - Barber Shop"
                            body = f"Dear {appt['customer_name']},\n\nYour appointment has been rescheduled to {formatted_date} at {new_time}."

                        send_email(
                            recipient_email=appt['customer_email'],
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Reschedule confirmation email sent to {appt['customer_email']}")
                    except Exception as email_err:
                        logger.warning(f"Failed to send reschedule email: {email_err}")
                        # Don't fail the whole reschedule if email fails

                messagebox.showinfo(_t("common.success"),
                                  _t("barber.messages.appointment_rescheduled") + "\n" +
                                  ("Email confirmation sent!" if appt.get('customer_email') and EMAIL_AVAILABLE else ""))
                resched_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror(_t("common.error"), str(e))

        ttk.Button(resched_window, text=_t("barber.btn.confirm_reschedule"),
                  command=confirm_reschedule).pack(pady=20)

    def add_service(self):
        """Add a new service - Function 24"""
        name = self.service_name_var.get().strip()
        service_type_display = self.service_type_combo.get()
        duration_str = self.service_duration_var.get().strip()
        price_str = self.service_price_var.get().strip()
        description = self.service_desc_text.get("1.0", tk.END).strip()

        if not name or not service_type_display or not price_str:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 30
            price = float(price_str)

            service_types = self._get_service_types()
            service_type = next((k for k, v in service_types.items() if v == service_type_display), 'haircut')

            from university_system.modules.domain.barber.services.barber_core import ServiceManager
            service_id = ServiceManager.add_service(
                name=name, service_type=service_type, price=price,
                duration_minutes=duration, description=description
            )

            log_activity('create', 'barber_service',
                        user_id=self.current_user.get('user_id'),
                        details={'service_id': service_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.service_added"))
            self._clear_service_form()
            self._load_services()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("barber.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_service(self):
        """Update selected service - Function 25"""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_service"))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]

        name = self.service_name_var.get().strip()
        service_type_display = self.service_type_combo.get()
        duration_str = self.service_duration_var.get().strip()
        price_str = self.service_price_var.get().strip()

        if not name or not price_str:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 30
            price = float(price_str)

            service_types = self._get_service_types()
            service_type = next((k for k, v in service_types.items() if v == service_type_display), 'haircut')

            from university_system.modules.domain.barber.services.barber_core import ServiceManager
            ServiceManager.update_service(
                service_id, name=name, service_type=service_type,
                price=price, duration_minutes=duration
            )

            log_activity('update', 'barber_service',
                        user_id=self.current_user.get('user_id'),
                        details={'service_id': service_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.service_updated"))
            self._load_services()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("barber.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_service_form(self):
        """Clear service form"""
        self.service_name_var.set("")
        self.service_type_combo.set("")
        self.service_duration_var.set("30")
        self.service_price_var.set("")
        self.service_desc_text.delete("1.0", tk.END)

    def add_staff(self):
        """Add a new staff member"""
        name = self.staff_name_var.get().strip()
        emp_id = self.staff_emp_id_var.get().strip()
        specialties = self.staff_specialties_var.get().strip()
        phone = self.staff_phone_var.get().strip()
        email = self.staff_email_var.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import StaffManager
            staff_id = StaffManager.add_staff(
                name=name, employee_id=emp_id, specialties=specialties,
                phone=phone, email=email
            )

            log_activity('create', 'barber_staff',
                        user_id=self.current_user.get('user_id'),
                        details={'staff_id': staff_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.staff_added"))
            self._clear_staff_form()
            self._load_staff()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_staff_form(self):
        """Clear staff form"""
        self.staff_name_var.set("")
        self.staff_emp_id_var.set("")
        self.staff_specialties_var.set("")
        self.staff_phone_var.set("")
        self.staff_email_var.set("")

    def generate_admin_report(self):
        """Generate admin report"""
        try:
            from university_system.modules.domain.barber.services.barber_core import ReportManager
            report = ReportManager.generate_admin_report()

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.report_failed").format(error=str(e)))

    def email_admin_report(self):
        """Email admin report"""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content:
            self.generate_admin_report()
            report_content = self.report_text.get("1.0", tk.END).strip()

        try:
            from university_system.infrastructure.email.email_service import send_email

            with get_db_connection() as conn:
                admin = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                ).fetchone()

            if admin and admin['email']:
                send_email(
                    recipient_email=admin['email'],
                    subject=f"Barber Shop Admin Report - {datetime.now().strftime('%Y-%m-%d')}",
                    body=report_content
                )

                log_activity('email', 'barber_report', user_id=self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("barber.errors.no_admin_email"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.email_failed").format(error=str(e)))

    # ==================== APPOINTMENT MANAGEMENT FUNCTIONS (1-10) ====================

    def view_appointment_history(self):
        """Function 1: View appointment history for selected customer or all"""
        history_window = tk.Toplevel(self.parent)
        history_window.title("Appointment History")
        history_window.geometry("800x500")
        history_window.transient(self.parent)

        # Filter frame
        filter_frame = ttk.Frame(history_window, padding="10")
        filter_frame.pack(fill=tk.X)

        ttk.Label(filter_frame, text="Customer ID:").pack(side=tk.LEFT)
        customer_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=customer_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT, padx=(20, 5))
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=from_var, width=12).pack(side=tk.LEFT)

        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(10, 5))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=to_var, width=12).pack(side=tk.LEFT)

        # History list
        columns = ('date', 'time', 'customer', 'service', 'barber', 'status', 'amount')
        tree = ttk.Treeview(history_window, columns=columns, show='headings', height=18)

        for col in columns:
            tree.heading(col, text=col.title())
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_history():
            for item in tree.get_children():
                tree.delete(item)
            try:
                with get_db_connection() as conn:
                    query = """
                        SELECT a.appointment_date, a.appointment_time, a.customer_name,
                               s.name as service_name, st.name as staff_name, a.status,
                               COALESCE(t.amount, s.price) as amount
                        FROM barber_appointments a
                        LEFT JOIN barber_services s ON a.service_id = s.service_id
                        LEFT JOIN barber_staff st ON a.staff_id = st.staff_id
                        LEFT JOIN barber_transactions t ON a.appointment_id = t.appointment_id
                        WHERE a.appointment_date BETWEEN ? AND ?
                    """
                    params = [from_var.get(), to_var.get()]
                    if customer_var.get().strip():
                        query += " AND a.customer_id = ?"
                        params.append(customer_var.get().strip())
                    query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"

                    rows = conn.execute(query, params).fetchall()
                    for row in rows:
                        tree.insert('', tk.END, values=(
                            row['appointment_date'], row['appointment_time'],
                            row['customer_name'], row['service_name'] or 'N/A',
                            row['staff_name'] or 'Any', row['status'],
                            f"£{row['amount']:.2f}" if row['amount'] else 'N/A'
                        ))
            except Exception as e:
                logger.error(f"Error loading history: {e}")

        ttk.Button(filter_frame, text="Search", command=load_history).pack(side=tk.LEFT, padx=20)
        load_history()

    def show_weekly_calendar(self):
        """Function 2: Show weekly calendar view of appointments"""
        cal_window = tk.Toplevel(self.parent)
        cal_window.title("Weekly Calendar")
        cal_window.geometry("1000x600")
        cal_window.transient(self.parent)

        # Week navigation
        nav_frame = ttk.Frame(cal_window, padding="10")
        nav_frame.pack(fill=tk.X)

        current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_var = tk.StringVar(value=current_week_start.strftime('%Y-%m-%d'))

        def prev_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') - timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_week()

        def next_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') + timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_week()

        ttk.Button(nav_frame, text="< Prev", command=prev_week).pack(side=tk.LEFT)
        ttk.Label(nav_frame, textvariable=week_var, font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Button(nav_frame, text="Next >", command=next_week).pack(side=tk.LEFT)

        # Calendar grid
        cal_frame = ttk.Frame(cal_window, padding="10")
        cal_frame.pack(fill=tk.BOTH, expand=True)

        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_frames = []

        for i, day in enumerate(days):
            col_frame = ttk.LabelFrame(cal_frame, text=day, padding="5")
            col_frame.grid(row=0, column=i, sticky='nsew', padx=2, pady=2)
            cal_frame.columnconfigure(i, weight=1)
            day_frames.append(col_frame)

        cal_frame.rowconfigure(0, weight=1)

        def load_week():
            for frame in day_frames:
                for widget in frame.winfo_children():
                    widget.destroy()

            start = datetime.strptime(week_var.get(), '%Y-%m-%d')
            try:
                with get_db_connection() as conn:
                    for i in range(7):
                        day_date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                        appointments = conn.execute("""
                            SELECT appointment_time, customer_name, status
                            FROM barber_appointments
                            WHERE appointment_date = ?
                            ORDER BY appointment_time
                        """, (day_date,)).fetchall()

                        ttk.Label(day_frames[i], text=day_date, font=('Helvetica', 8)).pack()
                        for appt in appointments:
                            color = 'green' if appt['status'] == 'completed' else 'blue'
                            lbl = ttk.Label(day_frames[i],
                                          text=f"{appt['appointment_time']}\n{appt['customer_name'][:15]}",
                                          foreground=color)
                            lbl.pack(pady=2)
            except Exception as e:
                logger.error(f"Error loading week: {e}")

        load_week()

    def bulk_cancel_appointments(self):
        """Function 3: Bulk cancel appointments"""
        cancel_window = tk.Toplevel(self.parent)
        cancel_window.title("Bulk Cancel Appointments")
        cancel_window.geometry("500x400")
        cancel_window.transient(self.parent)
        cancel_window.grab_set()

        ttk.Label(cancel_window, text="Bulk Cancel Appointments",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        # Options
        options_frame = ttk.LabelFrame(cancel_window, text="Cancel Options", padding="10")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(options_frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(options_frame, text="Staff ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        staff_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=staff_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(options_frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Staff unavailable")
        ttk.Entry(options_frame, textvariable=reason_var, width=30).grid(row=2, column=1, pady=5)

        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Notify customers via email",
                       variable=notify_var).grid(row=3, column=0, columnspan=2, pady=5)

        result_text = tk.Text(cancel_window, height=10, width=50)
        result_text.pack(padx=20, pady=10)

        def execute_cancel():
            if not messagebox.askyesno("Confirm", "Are you sure you want to cancel these appointments?"):
                return
            try:
                with transaction() as conn:
                    query = """
                        SELECT appointment_id, customer_name, customer_email, appointment_time
                        FROM barber_appointments
                        WHERE appointment_date = ? AND status IN ('scheduled', 'checked_in')
                    """
                    params = [date_var.get()]
                    if staff_var.get().strip():
                        query += " AND staff_id = ?"
                        params.append(int(staff_var.get()))

                    appointments = conn.execute(query, params).fetchall()

                    cancelled = 0
                    for appt in appointments:
                        conn.execute("""
                            UPDATE barber_appointments
                            SET status = 'cancelled', cancellation_reason = ?
                            WHERE appointment_id = ?
                        """, (reason_var.get(), appt['appointment_id']))
                        cancelled += 1

                        if notify_var.get() and appt['customer_email'] and EMAIL_AVAILABLE:
                            try:
                                from university_system.infrastructure.email.email_service import send_email
                                from university_system.infrastructure.email.template_utils import render_template

                                subject, body = render_template('commerce/barber/appointment_cancelled', {
                                    'customer_name': appt['customer_name'],
                                    'appointment_date': date_var.get(),
                                    'appointment_time': appt['appointment_time'],
                                    'cancellation_reason': reason_var.get()
                                })

                                if not subject or not body:
                                    subject = "Appointment Cancelled"
                                    body = f"Dear {appt['customer_name']},\n\nYour appointment has been cancelled.\nReason: {reason_var.get()}"

                                send_email(appt['customer_email'], subject, body)
                            except Exception:
                                pass

                    log_activity('bulk_cancel', 'barber_appointments',
                                details={'count': cancelled, 'date': date_var.get()})

                result_text.delete('1.0', tk.END)
                result_text.insert('1.0', f"Successfully cancelled {cancelled} appointments.")
                self._load_appointments()

            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(cancel_window, text="Cancel Appointments", command=execute_cancel).pack(pady=10)

    def set_appointment_reminder(self):
        """Function 4: Set reminder for appointment"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        reminder_window = tk.Toplevel(self.parent)
        reminder_window.title("Set Reminder")
        reminder_window.geometry("400x300")
        reminder_window.transient(self.parent)
        reminder_window.grab_set()

        ttk.Label(reminder_window, text=f"Set Reminder for {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(reminder_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Reminder Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_var = tk.StringVar(value="email")
        ttk.Radiobutton(frame, text="Email", variable=type_var, value="email").grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(frame, text="SMS", variable=type_var, value="sms").grid(row=1, column=1, sticky=tk.W)

        ttk.Label(frame, text="Hours Before:").grid(row=2, column=0, sticky=tk.W, pady=5)
        hours_var = tk.StringVar(value="24")
        ttk.Combobox(frame, textvariable=hours_var, values=['1', '2', '4', '12', '24', '48'],
                    width=10).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(frame, text="Message:").grid(row=3, column=0, sticky=tk.W, pady=5)
        msg_text = tk.Text(frame, height=4, width=30)
        msg_text.grid(row=3, column=1, pady=5)
        msg_text.insert('1.0', "Don't forget your appointment!")

        def save_reminder():
            try:
                from university_system.modules.domain.barber.services.barber_core import (
                    AppointmentManager, ReminderManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    # Calculate send_at time (appointment datetime minus hours_before)
                    appt_datetime = datetime.strptime(
                        f"{appt['appointment_date']} {appt['appointment_time']}",
                        '%Y-%m-%d %H:%M'
                    )
                    send_at = appt_datetime - timedelta(hours=int(hours_var.get()))
                    send_at_str = send_at.strftime('%Y-%m-%d %H:%M:%S')

                    ReminderManager.schedule_reminder(
                        appointment_id=appt['appointment_id'],
                        reminder_type=type_var.get(),
                        send_at=send_at_str,
                        channel='email'
                    )
                    messagebox.showinfo("Success", "Reminder scheduled successfully!")
                    reminder_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(reminder_window, text="Save Reminder", command=save_reminder).pack(pady=10)

    def mark_no_show(self):
        """Function 5: Mark appointment as no-show"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Mark appointment {appt_number} as no-show?"):
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import (
                AppointmentManager, NoShowManager
            )
            appt = AppointmentManager.get_appointment_by_number(appt_number)
            if appt:
                # Get current user for marked_by parameter
                marked_by = self.current_user.get('username', 'admin')

                NoShowManager.mark_no_show(
                    appointment_id=appt['appointment_id'],
                    marked_by=marked_by,
                    add_to_watchlist=False
                )
                log_activity('no_show', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo("Success", "Appointment marked as no-show.")
                self._load_appointments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def view_waitlist(self):
        """Function 6: View waitlist"""
        waitlist_window = tk.Toplevel(self.parent)
        waitlist_window.title("Waitlist")
        waitlist_window.geometry("700x400")
        waitlist_window.transient(self.parent)

        columns = ('id', 'customer', 'service', 'preferred_date', 'preferred_time', 'status', 'added')
        tree = ttk.Treeview(waitlist_window, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col.replace('_', ' ').title())
            tree.column(col, width=90)

        scrollbar = ttk.Scrollbar(waitlist_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_waitlist():
            for item in tree.get_children():
                tree.delete(item)
            try:
                from university_system.modules.domain.barber.services.barber_core import WaitlistManager
                # get_waitlist() filters to status='waiting' by default
                entries = WaitlistManager.get_waitlist()
                for entry in entries:
                    tree.insert('', tk.END, values=(
                        entry['waitlist_id'], entry['customer_name'],
                        entry.get('service_name', 'Any'), entry['preferred_date'],
                        entry.get('preferred_time', 'Any'), entry['status'], entry['created_at'][:10]
                    ))
            except Exception as e:
                logger.error(f"Error loading waitlist: {e}")

        btn_frame = ttk.Frame(waitlist_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Refresh", command=load_waitlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Notify Selected", command=lambda: self._notify_waitlist_entry(tree)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected", command=lambda: self._remove_waitlist_entry(tree, load_waitlist)).pack(side=tk.LEFT, padx=5)

        load_waitlist()

    def _notify_waitlist_entry(self, tree):
        """Helper to notify waitlist entry"""
        selected = tree.selection()
        if not selected:
            return
        item = tree.item(selected[0])
        waitlist_id = item['values'][0]

        # Prompt for available slot
        slot_window = tk.Toplevel(self.parent)
        slot_window.title("Available Slot")
        slot_window.geometry("300x150")
        slot_window.transient(self.parent)
        slot_window.grab_set()

        ttk.Label(slot_window, text="Enter available slot:").pack(pady=10)

        slot_frame = ttk.Frame(slot_window, padding="10")
        slot_frame.pack()

        ttk.Label(slot_frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(slot_frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(slot_frame, text="Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(slot_frame, values=self._get_time_slots(), width=12)
        time_combo.grid(row=1, column=1, pady=5)

        def confirm_notify():
            if not time_combo.get():
                messagebox.showerror("Error", "Please select a time.")
                return

            available_slot = f"{date_var.get()} {time_combo.get()}"
            try:
                from university_system.modules.domain.barber.services.barber_core import WaitlistManager

                # Get customer details from waitlist entry
                with get_db_connection() as conn:
                    waitlist_entry = conn.execute('''
                        SELECT w.*, s.name as service_name
                        FROM barber_waitlist w
                        LEFT JOIN barber_services s ON w.service_id = s.service_id
                        WHERE w.waitlist_id = ?
                    ''', (waitlist_id,)).fetchone()

                if not waitlist_entry:
                    messagebox.showerror("Error", "Waitlist entry not found.")
                    return

                # Update waitlist status
                WaitlistManager.notify_waitlist(waitlist_id, available_slot)

                # Send notification email
                customer_email = waitlist_entry['customer_email']
                customer_name = waitlist_entry['customer_name']
                service_name = waitlist_entry['service_name'] or 'Your requested service'

                if customer_email:
                    try:
                        from university_system.infrastructure.email.email_service import send_email
                        from university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('commerce/barber/waitlist_availability', {
                            'customer_name': customer_name,
                            'available_date': date_var.get(),
                            'available_time': time_combo.get(),
                            'barber_name': 'Any available',
                            'service_name': service_name
                        })

                        if not subject or not body:
                            subject = "Barber Shop - Appointment Slot Available!"
                            body = f"Dear {customer_name},\n\nAn appointment slot is available on {date_var.get()} at {time_combo.get()}."

                        send_email(
                            recipient_email=customer_email,
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Availability notification email sent to {customer_email}")
                    except Exception as e:
                        logger.error(f"Failed to send availability notification email: {e}")
                        # Don't fail the whole operation if email fails

                messagebox.showinfo("Success", f"Customer notified of available slot: {available_slot}\nEmail sent to: {customer_email if customer_email else 'No email on file'}")
                slot_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(slot_window, text="Notify", command=confirm_notify).pack(pady=10)

    def _remove_waitlist_entry(self, tree, reload_func):
        """Helper to remove waitlist entry"""
        selected = tree.selection()
        if not selected:
            return
        item = tree.item(selected[0])
        waitlist_id = item['values'][0]
        try:
            from university_system.modules.domain.barber.services.barber_core import WaitlistManager
            WaitlistManager.remove_from_waitlist(waitlist_id)
            reload_func()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_to_waitlist(self):
        """Function 7: Add customer to waitlist"""
        waitlist_window = tk.Toplevel(self.parent)
        waitlist_window.title("Add to Waitlist")
        waitlist_window.geometry("400x350")
        waitlist_window.transient(self.parent)
        waitlist_window.grab_set()

        ttk.Label(waitlist_window, text="Add to Waitlist",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(waitlist_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Use current user
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', '')))
        customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        ttk.Label(frame, text=f"Customer: {customer_name}").grid(row=0, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Service:").grid(row=1, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, state="readonly", width=25)
        service_combo['values'] = self.appt_service_combo['values']
        service_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Preferred Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=date_var, width=15).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        time_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=4, column=0, sticky=tk.W, pady=5)
        notes_text = tk.Text(frame, height=3, width=25)
        notes_text.grid(row=4, column=1, pady=5)

        def add_entry():
            try:
                service_id = None
                service_name = "Any Service"
                if service_combo.get():
                    service_id = int(service_combo.get().split(':')[0])
                    service_name = service_combo.get().split(':', 1)[1].strip()

                # Get customer email and phone from current user
                customer_email = self.current_user.get('email', '')
                customer_phone = self.current_user.get('phone', '')

                from university_system.modules.domain.barber.services.barber_core import WaitlistManager
                WaitlistManager.add_to_waitlist(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    preferred_date=date_var.get(),
                    preferred_time=time_combo.get(),
                    service_id=service_id,
                    notes=notes_text.get('1.0', tk.END).strip()
                )

                # Send confirmation email
                if customer_email:
                    try:
                        from university_system.infrastructure.email.email_service import send_email
                        from university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('commerce/barber/waitlist_confirmation', {
                            'customer_name': customer_name,
                            'service_name': service_name,
                            'preferred_barber': 'Any available',
                            'waitlist_position': 'Next available'
                        })

                        if not subject or not body:
                            subject = "Barber Shop - Added to Waitlist"
                            body = f"Dear {customer_name},\n\nYou have been added to our waitlist for {service_name}."

                        send_email(
                            recipient_email=customer_email,
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Waitlist confirmation email sent to {customer_email}")
                    except Exception as e:
                        logger.error(f"Failed to send waitlist confirmation email: {e}")
                        # Don't fail the whole operation if email fails

                messagebox.showinfo("Success", "Added to waitlist! Confirmation email sent.")
                waitlist_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(waitlist_window, text="Add to Waitlist", command=add_entry).pack(pady=10)

    def notify_waitlist_availability(self):
        """Function 8: Notify waitlist about availability"""
        try:
            from university_system.modules.domain.barber.services.barber_core import WaitlistManager
            count = WaitlistManager.notify_available_slots()
            messagebox.showinfo("Success", f"Notified {count} customers about availability.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def block_time_slot(self):
        """Function 9: Block time slot"""
        block_window = tk.Toplevel(self.parent)
        block_window.title("Block Time Slot")
        block_window.geometry("400x350")
        block_window.transient(self.parent)
        block_window.grab_set()

        ttk.Label(block_window, text="Block Time Slot",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(block_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Start Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        start_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="End Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        end_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Staff (optional):").grid(row=3, column=0, sticky=tk.W, pady=5)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        staff_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=4, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Break")
        ttk.Entry(frame, textvariable=reason_var, width=25).grid(row=4, column=1, pady=5)

        def block_slot():
            try:
                staff_id = None
                if staff_combo.get() and staff_combo.get() != 'Any':
                    staff_id = int(staff_combo.get().split(':')[0])

                from university_system.modules.domain.barber.services.barber_core import BlockedSlotManager
                # Get current user for blocked_by parameter
                blocked_by = self.current_user.get('username', 'admin')

                BlockedSlotManager.block_slot(
                    staff_id=staff_id,
                    date=date_var.get(),
                    start_time=start_combo.get(),
                    end_time=end_combo.get(),
                    reason=reason_var.get(),
                    blocked_by=blocked_by
                )
                messagebox.showinfo("Success", "Time slot blocked!")
                block_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(block_window, text="Block Slot", command=block_slot).pack(pady=10)

    def recurring_appointment(self):
        """Function 10: Create recurring appointment"""
        recurring_window = tk.Toplevel(self.parent)
        recurring_window.title("Recurring Appointment")
        recurring_window.geometry("450x450")
        recurring_window.transient(self.parent)
        recurring_window.grab_set()

        ttk.Label(recurring_window, text="Create Recurring Appointment",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(recurring_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')
        ttk.Label(frame, text=f"Customer: {customer_name}").grid(row=0, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Service:").grid(row=1, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, state="readonly", width=25)
        service_combo['values'] = self.appt_service_combo['values']
        service_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Staff:").grid(row=2, column=0, sticky=tk.W, pady=5)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        staff_combo.set('Any')
        staff_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Day:").grid(row=3, column=0, sticky=tk.W, pady=5)
        day_combo = ttk.Combobox(frame, values=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], width=15)
        day_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Preferred Time:").grid(row=4, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        time_combo.grid(row=4, column=1, pady=5)

        ttk.Label(frame, text="Frequency:").grid(row=5, column=0, sticky=tk.W, pady=5)
        freq_combo = ttk.Combobox(frame, values=['weekly', 'biweekly', 'monthly'], width=15)
        freq_combo.set('monthly')
        freq_combo.grid(row=5, column=1, pady=5)

        ttk.Label(frame, text="Number of Occurrences:").grid(row=6, column=0, sticky=tk.W, pady=5)
        count_var = tk.StringVar(value="6")
        ttk.Entry(frame, textvariable=count_var, width=10).grid(row=6, column=1, pady=5)

        def create_recurring():
            try:
                if not service_combo.get():
                    messagebox.showerror("Error", "Please select a service.")
                    return

                if not day_combo.get():
                    messagebox.showerror("Error", "Please select a day of the week.")
                    return

                if not time_combo.get():
                    messagebox.showerror("Error", "Please select a time.")
                    return

                customer_id = (self.current_user.get('student_id') or
                              self.current_user.get('username') or
                              str(self.current_user.get('id', '')))
                service_id = int(service_combo.get().split(':')[0])
                staff_id = None
                if staff_combo.get() and staff_combo.get() != 'Any':
                    staff_id = int(staff_combo.get().split(':')[0])

                # Convert day name to number (0=Monday, 6=Sunday)
                day_map = {
                    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
                    'Friday': 4, 'Saturday': 5, 'Sunday': 6
                }
                day_of_week = day_map.get(day_combo.get())
                if day_of_week is None:
                    messagebox.showerror("Error", "Invalid day selected.")
                    return

                from university_system.modules.domain.barber.services.barber_core import RecurringAppointmentManager
                # Get customer email from current user
                customer_email = self.current_user.get('email', '')
                # Calculate start and end dates
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=int(count_var.get()) * 7)).strftime('%Y-%m-%d')

                RecurringAppointmentManager.create_recurring(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    service_id=service_id,
                    staff_id=staff_id,
                    day_of_week=day_of_week,
                    time=time_combo.get(),
                    frequency=freq_combo.get(),
                    start_date=start_date,
                    end_date=end_date
                )
                messagebox.showinfo("Success", "Recurring appointment created!")
                recurring_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(recurring_window, text="Create Recurring", command=create_recurring).pack(pady=10)

    # ==================== CUSTOMER MANAGEMENT FUNCTIONS (11-20) ====================

    def _load_customers(self):
        """Load customers into the customers tree"""
        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)
        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager
            customers = CustomerManager.get_all_customers()
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('visit_count', 0),
                    cust.get('last_visit', 'N/A'),
                    'Yes' if cust.get('is_favorite') else 'No'
                ))
        except Exception as e:
            logger.error(f"Error loading customers: {e}")

    def create_customer_profile(self):
        """Function 11: Create customer profile"""
        profile_window = tk.Toplevel(self.parent)
        profile_window.title("Create Customer Profile")
        profile_window.geometry("400x400")
        profile_window.transient(self.parent)
        profile_window.grab_set()

        ttk.Label(profile_window, text="Create Customer Profile",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(profile_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=email_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=phone_var, width=30).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Barber:").grid(row=3, column=0, sticky=tk.W, pady=5)
        barber_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        barber_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=4, column=0, sticky=tk.W, pady=5)
        notes_text = tk.Text(frame, height=4, width=25)
        notes_text.grid(row=4, column=1, pady=5)

        def save_profile():
            if not name_var.get().strip():
                messagebox.showerror("Error", "Name is required.")
                return
            try:
                preferred_staff = None
                if barber_combo.get() and barber_combo.get() != 'Any':
                    preferred_staff = int(barber_combo.get().split(':')[0])

                from university_system.modules.domain.barber.services.barber_core import CustomerManager
                # Note: create_profile doesn't accept customer_id initially, will be set by system
                # For now, use a placeholder or let the system generate one
                customer_id = name_var.get().strip().replace(' ', '_').lower()[:20]

                # Build preferences string with preferred staff
                prefs = f"Preferred staff: {preferred_staff}" if preferred_staff else ""

                CustomerManager.create_profile(
                    customer_id=customer_id,
                    name=name_var.get().strip(),
                    email=email_var.get().strip(),
                    phone=phone_var.get().strip(),
                    preferences=prefs,
                    notes=notes_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo("Success", "Customer profile created!")
                profile_window.destroy()
                self._load_customers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(profile_window, text="Save Profile", command=save_profile).pack(pady=10)

    def view_customer_details(self):
        """Function 12: View customer details"""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]

        details_window = tk.Toplevel(self.parent)
        details_window.title("Customer Details")
        details_window.geometry("600x500")
        details_window.transient(self.parent)

        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager
            customer = CustomerManager.get_customer(customer_id)

            if not customer:
                messagebox.showerror("Error", "Customer not found.")
                details_window.destroy()
                return

            # Customer info
            info_frame = ttk.LabelFrame(details_window, text="Customer Information", padding="10")
            info_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Label(info_frame, text=f"Name: {customer['name']}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Email: {customer.get('email', 'N/A')}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Phone: {customer.get('phone', 'N/A')}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Total Visits: {customer.get('visit_count', 0)}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Last Visit: {customer.get('last_visit', 'N/A')}").pack(anchor=tk.W)

            # Notes
            notes_frame = ttk.LabelFrame(details_window, text="Notes", padding="10")
            notes_frame.pack(fill=tk.X, padx=20, pady=10)

            notes_text = tk.Text(notes_frame, height=5, width=50)
            notes_text.pack(fill=tk.X)
            notes_text.insert('1.0', customer.get('notes', ''))
            notes_text.config(state='disabled')

            # Recent appointments
            appt_frame = ttk.LabelFrame(details_window, text="Recent Appointments", padding="10")
            appt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            columns = ('date', 'service', 'barber', 'status')
            tree = ttk.Treeview(appt_frame, columns=columns, show='headings', height=6)
            for col in columns:
                tree.heading(col, text=col.title())
                tree.column(col, width=120)
            tree.pack(fill=tk.BOTH, expand=True)

            appointments = CustomerManager.get_customer_appointments(customer_id, limit=10)
            for appt in appointments:
                tree.insert('', tk.END, values=(
                    appt['appointment_date'], appt.get('service_name', 'N/A'),
                    appt.get('staff_name', 'Any'), appt['status']
                ))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_customer_notes(self):
        """Function 13: Add customer notes"""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]
        customer_name = item['values'][1]

        notes_window = tk.Toplevel(self.parent)
        notes_window.title(f"Notes for {customer_name}")
        notes_window.geometry("400x300")
        notes_window.transient(self.parent)
        notes_window.grab_set()

        ttk.Label(notes_window, text=f"Add Note for {customer_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        notes_text = tk.Text(notes_window, height=8, width=45)
        notes_text.pack(padx=20, pady=10)

        def save_note():
            note = notes_text.get('1.0', tk.END).strip()
            if not note:
                return
            try:
                from university_system.modules.domain.barber.services.barber_core import CustomerManager
                CustomerManager.add_note(
                    customer_id=customer_id,
                    note=note,
                    created_by=self.current_user.get('username')
                )
                messagebox.showinfo("Success", "Note added!")
                notes_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(notes_window, text="Save Note", command=save_note).pack(pady=10)

    def search_customers(self):
        """Function 14: Search customers"""
        search_term = self.customer_search_var.get().strip()
        if not search_term:
            self._load_customers()
            return

        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)

        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager
            customers = CustomerManager.search_customers(search_term)
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('visit_count', 0),
                    cust.get('last_visit', 'N/A'),
                    'Yes' if cust.get('is_favorite') else 'No'
                ))
        except Exception as e:
            logger.error(f"Error searching customers: {e}")

    def view_favorite_customers(self):
        """Function 15: View favorite customers"""
        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)

        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager
            # Use get_vip_customers() instead of get_favorite_customers()
            customers = CustomerManager.get_vip_customers()
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('total_visits', 0),
                    cust.get('last_visit', 'N/A'), 'Yes'
                ))
        except Exception as e:
            logger.error(f"Error loading favorites: {e}")

    def send_customer_message(self):
        """Function 16: Send message to customer"""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]
        customer_name = item['values'][1]
        customer_email = item['values'][2]

        if not customer_email:
            messagebox.showerror("Error", "Customer has no email address.")
            return

        msg_window = tk.Toplevel(self.parent)
        msg_window.title(f"Message to {customer_name}")
        msg_window.geometry("450x350")
        msg_window.transient(self.parent)
        msg_window.grab_set()

        ttk.Label(msg_window, text=f"Send Message to {customer_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(msg_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"To: {customer_email}").pack(anchor=tk.W)

        ttk.Label(frame, text="Subject:").pack(anchor=tk.W, pady=(10, 0))
        subject_var = tk.StringVar(value="Message from Barber Shop")
        ttk.Entry(frame, textvariable=subject_var, width=40).pack(fill=tk.X)

        ttk.Label(frame, text="Message:").pack(anchor=tk.W, pady=(10, 0))
        msg_text = tk.Text(frame, height=8, width=40)
        msg_text.pack(fill=tk.BOTH, expand=True)

        def send_message():
            if not EMAIL_AVAILABLE:
                messagebox.showerror("Error", "Email service not available.")
                return
            try:
                from university_system.infrastructure.email.email_service import send_email
                send_email(
                    customer_email,
                    subject_var.get(),
                    msg_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo("Success", "Message sent!")
                msg_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(msg_window, text="Send", command=send_message).pack(pady=10)

    def view_customer_feedback(self):
        """Function 17: View customer feedback"""
        selected = self.customers_tree.selection()
        customer_id = None
        if selected:
            item = self.customers_tree.item(selected[0])
            customer_id = item['values'][0]

        feedback_window = tk.Toplevel(self.parent)
        feedback_window.title("Customer Feedback")
        feedback_window.geometry("700x450")
        feedback_window.transient(self.parent)

        columns = ('id', 'date', 'customer', 'rating', 'comments')
        tree = ttk.Treeview(feedback_window, columns=columns, show='headings', height=15)

        tree.heading('id', text='ID')
        tree.heading('date', text='Date')
        tree.heading('customer', text='Customer')
        tree.heading('rating', text='Rating')
        tree.heading('comments', text='Comments')

        tree.column('id', width=50)
        tree.column('date', width=100)
        tree.column('customer', width=150)
        tree.column('rating', width=80)
        tree.column('comments', width=300)

        scrollbar = ttk.Scrollbar(feedback_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from university_system.modules.domain.barber.services.barber_core import FeedbackManager
            # Use get_customer_feedback() instead of get_feedback()
            feedback_list = FeedbackManager.get_customer_feedback(customer_id=customer_id)
            for fb in feedback_list:
                tree.insert('', tk.END, values=(
                    fb['feedback_id'], fb['created_at'][:10],
                    fb.get('customer_id', ''), f"{fb['rating']}/5", fb.get('comment', '')
                ))
        except Exception as e:
            logger.error(f"Error loading feedback: {e}")

    def merge_customer_profiles(self):
        """Function 18: Merge customer profiles"""
        merge_window = tk.Toplevel(self.parent)
        merge_window.title("Merge Customer Profiles")
        merge_window.geometry("400x300")
        merge_window.transient(self.parent)
        merge_window.grab_set()

        ttk.Label(merge_window, text="Merge Customer Profiles",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(merge_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Primary Customer ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        primary_var = tk.StringVar()
        ttk.Entry(frame, textvariable=primary_var, width=20).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Secondary Customer ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        secondary_var = tk.StringVar()
        ttk.Entry(frame, textvariable=secondary_var, width=20).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="(Secondary will be merged into Primary)").grid(row=2, column=0, columnspan=2, pady=10)

        def merge():
            if not primary_var.get() or not secondary_var.get():
                messagebox.showerror("Error", "Please enter both customer IDs.")
                return
            if not messagebox.askyesno("Confirm", "Are you sure you want to merge these profiles? This cannot be undone."):
                return
            try:
                from university_system.modules.domain.barber.services.barber_core import CustomerManager
                CustomerManager.merge_profiles(primary_var.get(), secondary_var.get())
                messagebox.showinfo("Success", "Profiles merged!")
                merge_window.destroy()
                self._load_customers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(merge_window, text="Merge Profiles", command=merge).pack(pady=10)

    def export_customer_list(self):
        """Function 19: Export customer list"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="Export Customer List"
        )
        if not file_path:
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager
            customers = CustomerManager.get_all_customers()

            if file_path.endswith('.json'):
                with open(file_path, 'w') as f:
                    json.dump(customers, f, indent=2, default=str)
            else:
                with open(file_path, 'w', newline='') as f:
                    if customers:
                        writer = csv.DictWriter(f, fieldnames=customers[0].keys())
                        writer.writeheader()
                        writer.writerows(customers)

            messagebox.showinfo("Success", f"Exported {len(customers)} customers to {file_path}")
            log_activity('export', 'barber_customers', details={'count': len(customers)})

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_customers(self):
        """Function 20: Import customers"""
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="Import Customers"
        )
        if not file_path:
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import CustomerManager

            customers = []
            if file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    customers = json.load(f)
            else:
                with open(file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    customers = list(reader)

            imported = 0
            for cust in customers:
                try:
                    CustomerManager.create_profile(
                        name=cust.get('name', ''),
                        email=cust.get('email', ''),
                        phone=cust.get('phone', '')
                    )
                    imported += 1
                except Exception:
                    pass

            messagebox.showinfo("Success", f"Imported {imported} customers.")
            log_activity('import', 'barber_customers', details={'count': imported})
            self._load_customers()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== SERVICE ENHANCEMENT FUNCTIONS (21-28) ====================

    def create_service_package(self):
        """Function 21: Create service package"""
        pkg_window = tk.Toplevel(self.parent)
        pkg_window.title("Create Service Package")
        pkg_window.geometry("450x450")
        pkg_window.transient(self.parent)
        pkg_window.grab_set()

        ttk.Label(pkg_window, text="Create Service Package",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(pkg_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Package Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
        desc_text = tk.Text(frame, height=3, width=25)
        desc_text.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Package Price (£):").grid(row=2, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(frame, textvariable=price_var, width=15).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Select Services:").grid(row=3, column=0, sticky=tk.W, pady=5)

        services_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=6, width=30)
        services_listbox.grid(row=3, column=1, pady=5)

        for svc in self.appt_service_combo['values']:
            services_listbox.insert(tk.END, svc)

        def save_package():
            if not name_var.get().strip() or not price_var.get().strip():
                messagebox.showerror("Error", "Please fill in all required fields.")
                return
            try:
                selected_indices = services_listbox.curselection()
                service_ids = []
                for idx in selected_indices:
                    svc_str = services_listbox.get(idx)
                    service_ids.append(int(svc_str.split(':')[0]))

                from university_system.modules.domain.barber.services.barber_core import ServicePackageManager
                ServicePackageManager.create_package(
                    name=name_var.get().strip(),
                    description=desc_text.get('1.0', tk.END).strip(),
                    price=float(price_var.get()),
                    service_ids=service_ids
                )
                messagebox.showinfo("Success", "Package created!")
                pkg_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(pkg_window, text="Create Package", command=save_package).pack(pady=10)

    def set_service_availability(self):
        """Function 22: Set service availability"""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a service.")
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        avail_window = tk.Toplevel(self.parent)
        avail_window.title(f"Availability - {service_name}")
        avail_window.geometry("400x350")
        avail_window.transient(self.parent)
        avail_window.grab_set()

        ttk.Label(avail_window, text=f"Set Availability for {service_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(avail_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Available Days:").pack(anchor=tk.W)
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_vars = {}
        for day in days:
            var = tk.BooleanVar(value=True)
            day_vars[day] = var
            ttk.Checkbutton(frame, text=day, variable=var).pack(anchor=tk.W)

        ttk.Label(frame, text="Available Hours:").pack(anchor=tk.W, pady=(10, 0))
        hours_frame = ttk.Frame(frame)
        hours_frame.pack(fill=tk.X)

        ttk.Label(hours_frame, text="From:").pack(side=tk.LEFT)
        from_combo = ttk.Combobox(hours_frame, values=self._get_time_slots(), width=8)
        from_combo.set('09:00')
        from_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(hours_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        to_combo = ttk.Combobox(hours_frame, values=self._get_time_slots(), width=8)
        to_combo.set('17:00')
        to_combo.pack(side=tk.LEFT, padx=5)

        def save_availability():
            try:
                available_days = [day for day, var in day_vars.items() if var.get()]
                from university_system.modules.domain.barber.services.barber_core import ServiceManager
                ServiceManager.set_availability(
                    service_id=service_id,
                    available_days=available_days,
                    start_time=from_combo.get(),
                    end_time=to_combo.get()
                )
                messagebox.showinfo("Success", "Availability updated!")
                avail_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(avail_window, text="Save", command=save_availability).pack(pady=10)

    def add_service_addon(self):
        """Function 23: Add service addon"""
        addon_window = tk.Toplevel(self.parent)
        addon_window.title("Add Service Addon")
        addon_window.geometry("400x350")
        addon_window.transient(self.parent)
        addon_window.grab_set()

        ttk.Label(addon_window, text="Add Service Addon",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(addon_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Addon Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=25).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Price (£):").grid(row=1, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(frame, textvariable=price_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Duration (min):").grid(row=2, column=0, sticky=tk.W, pady=5)
        duration_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=duration_var, width=10).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="For Service:").grid(row=3, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, values=['All Services'] + list(self.appt_service_combo['values']), width=25)
        service_combo.set('All Services')
        service_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Description:").grid(row=4, column=0, sticky=tk.W, pady=5)
        desc_text = tk.Text(frame, height=3, width=25)
        desc_text.grid(row=4, column=1, pady=5)

        def save_addon():
            if not name_var.get().strip() or not price_var.get().strip():
                messagebox.showerror("Error", "Name and price are required.")
                return
            try:
                service_id = None
                if service_combo.get() != 'All Services':
                    service_id = int(service_combo.get().split(':')[0])

                from university_system.modules.domain.barber.services.barber_core import ServiceAddonManager
                ServiceAddonManager.add_addon(
                    name=name_var.get().strip(),
                    price=float(price_var.get()),
                    duration=int(duration_var.get()),
                    service_id=service_id,
                    description=desc_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo("Success", "Addon created!")
                addon_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(addon_window, text="Save Addon", command=save_addon).pack(pady=10)

    def duplicate_service(self):
        """Function 24: Duplicate service"""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a service to duplicate.")
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]

        try:
            from university_system.modules.domain.barber.services.barber_core import ServiceManager
            new_id = ServiceManager.duplicate_service(service_id)
            messagebox.showinfo("Success", f"Service duplicated! New ID: {new_id}")
            self._load_services()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def archive_service(self):
        """Function 25: Archive service"""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a service to archive.")
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        if not messagebox.askyesno("Confirm", f"Archive service '{service_name}'?"):
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import ServiceManager
            ServiceManager.archive_service(service_id)
            messagebox.showinfo("Success", "Service archived!")
            self._load_services()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_seasonal_pricing(self):
        """Function 26: Set seasonal pricing"""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a service.")
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        pricing_window = tk.Toplevel(self.parent)
        pricing_window.title(f"Seasonal Pricing - {service_name}")
        pricing_window.geometry("400x350")
        pricing_window.transient(self.parent)
        pricing_window.grab_set()

        ttk.Label(pricing_window, text=f"Set Seasonal Pricing for {service_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(pricing_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Season:").grid(row=0, column=0, sticky=tk.W, pady=5)
        season_combo = ttk.Combobox(frame, values=['Spring', 'Summer', 'Autumn', 'Winter', 'Holiday', 'Custom'], width=15)
        season_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Start Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=start_var, width=12).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="End Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_var = tk.StringVar(value=(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=end_var, width=12).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Price Adjustment (%):").grid(row=3, column=0, sticky=tk.W, pady=5)
        adjust_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=adjust_var, width=10).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="(Positive = increase, Negative = discount)").grid(row=4, column=0, columnspan=2, pady=5)

        def save_pricing():
            try:
                from university_system.modules.domain.barber.services.barber_core import ServiceManager
                ServiceManager.set_seasonal_pricing(
                    service_id=service_id,
                    season=season_combo.get(),
                    start_date=start_var.get(),
                    end_date=end_var.get(),
                    adjustment_percent=float(adjust_var.get())
                )
                messagebox.showinfo("Success", "Seasonal pricing set!")
                pricing_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(pricing_window, text="Save", command=save_pricing).pack(pady=10)

    def view_service_popularity(self):
        """Function 27: View service popularity"""
        pop_window = tk.Toplevel(self.parent)
        pop_window.title("Service Popularity")
        pop_window.geometry("600x400")
        pop_window.transient(self.parent)

        columns = ('rank', 'service', 'bookings', 'revenue', 'avg_rating')
        tree = ttk.Treeview(pop_window, columns=columns, show='headings', height=15)

        tree.heading('rank', text='Rank')
        tree.heading('service', text='Service')
        tree.heading('bookings', text='Bookings')
        tree.heading('revenue', text='Revenue')
        tree.heading('avg_rating', text='Avg Rating')

        tree.column('rank', width=50)
        tree.column('service', width=200)
        tree.column('bookings', width=100)
        tree.column('revenue', width=120)
        tree.column('avg_rating', width=100)

        scrollbar = ttk.Scrollbar(pop_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            popularity = AnalyticsManager.get_service_popularity()
            for i, svc in enumerate(popularity, 1):
                tree.insert('', tk.END, values=(
                    i, svc['name'], svc['booking_count'],
                    f"£{svc['total_revenue']:.2f}", f"{svc['avg_rating']:.1f}/5"
                ))
        except Exception as e:
            logger.error(f"Error loading popularity: {e}")

    def reorder_services(self):
        """Function 28: Reorder services display order"""
        reorder_window = tk.Toplevel(self.parent)
        reorder_window.title("Reorder Services")
        reorder_window.geometry("400x450")
        reorder_window.transient(self.parent)
        reorder_window.grab_set()

        ttk.Label(reorder_window, text="Drag to Reorder Services",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        listbox = tk.Listbox(reorder_window, height=15, width=40)
        listbox.pack(padx=20, pady=10)

        for svc in self.appt_service_combo['values']:
            listbox.insert(tk.END, svc)

        btn_frame = ttk.Frame(reorder_window)
        btn_frame.pack(pady=5)

        def move_up():
            idx = listbox.curselection()
            if idx and idx[0] > 0:
                item = listbox.get(idx[0])
                listbox.delete(idx[0])
                listbox.insert(idx[0] - 1, item)
                listbox.selection_set(idx[0] - 1)

        def move_down():
            idx = listbox.curselection()
            if idx and idx[0] < listbox.size() - 1:
                item = listbox.get(idx[0])
                listbox.delete(idx[0])
                listbox.insert(idx[0] + 1, item)
                listbox.selection_set(idx[0] + 1)

        ttk.Button(btn_frame, text="Move Up", command=move_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Move Down", command=move_down).pack(side=tk.LEFT, padx=5)

        def save_order():
            try:
                from university_system.modules.domain.barber.services.barber_core import ServiceManager
                order = []
                for i in range(listbox.size()):
                    svc_str = listbox.get(i)
                    service_id = int(svc_str.split(':')[0])
                    order.append((service_id, i + 1))
                ServiceManager.update_display_order(order)
                messagebox.showinfo("Success", "Order saved!")
                reorder_window.destroy()
                self._load_services()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(reorder_window, text="Save Order", command=save_order).pack(pady=10)

    # ==================== STAFF MANAGEMENT FUNCTIONS (29-36) ====================

    def set_staff_schedule(self):
        """Function 29: Set staff schedule"""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a staff member.")
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        sched_window = tk.Toplevel(self.parent)
        sched_window.title(f"Schedule - {staff_name}")
        sched_window.geometry("500x450")
        sched_window.transient(self.parent)
        sched_window.grab_set()

        ttk.Label(sched_window, text=f"Set Schedule for {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(sched_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        schedule_entries = {}

        for i, day in enumerate(days):
            ttk.Label(frame, text=day).grid(row=i, column=0, sticky=tk.W, pady=2)

            working_var = tk.BooleanVar(value=True if i < 5 else False)
            ttk.Checkbutton(frame, text="Working", variable=working_var).grid(row=i, column=1, padx=5)

            start_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=8)
            start_combo.set('09:00')
            start_combo.grid(row=i, column=2, padx=2)

            end_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=8)
            end_combo.set('17:00')
            end_combo.grid(row=i, column=3, padx=2)

            schedule_entries[day] = {'working': working_var, 'start': start_combo, 'end': end_combo}

        def save_schedule():
            try:
                schedule = []
                for day, entries in schedule_entries.items():
                    if entries['working'].get():
                        schedule.append({
                            'day': day,
                            'start_time': entries['start'].get(),
                            'end_time': entries['end'].get()
                        })

                from university_system.modules.domain.barber.services.barber_core import StaffScheduleManager
                StaffScheduleManager.set_schedule(staff_id, schedule)
                messagebox.showinfo("Success", "Schedule saved!")
                sched_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(sched_window, text="Save Schedule", command=save_schedule).pack(pady=10)

    def view_staff_performance(self):
        """Function 30: View staff performance"""
        perf_window = tk.Toplevel(self.parent)
        perf_window.title("Staff Performance")
        perf_window.geometry("700x450")
        perf_window.transient(self.parent)

        columns = ('name', 'appointments', 'revenue', 'avg_rating', 'no_shows', 'retention')
        tree = ttk.Treeview(perf_window, columns=columns, show='headings', height=15)

        tree.heading('name', text='Staff')
        tree.heading('appointments', text='Appointments')
        tree.heading('revenue', text='Revenue')
        tree.heading('avg_rating', text='Avg Rating')
        tree.heading('no_shows', text='No-Shows')
        tree.heading('retention', text='Retention %')

        for col in columns:
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(perf_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            performance = AnalyticsManager.get_staff_performance()
            for staff in performance:
                tree.insert('', tk.END, values=(
                    staff['name'], staff['appointment_count'],
                    f"£{staff['total_revenue']:.2f}", f"{staff['avg_rating']:.1f}/5",
                    staff['no_show_count'], f"{staff['retention_rate']:.0f}%"
                ))
        except Exception as e:
            logger.error(f"Error loading performance: {e}")

    def assign_staff_to_appointment(self):
        """Function 31: Assign staff to appointment"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        assign_window = tk.Toplevel(self.parent)
        assign_window.title("Assign Staff")
        assign_window.geometry("350x200")
        assign_window.transient(self.parent)
        assign_window.grab_set()

        ttk.Label(assign_window, text=f"Assign Staff to {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(assign_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select Staff:").pack(anchor=tk.W)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=25)
        staff_combo.pack(fill=tk.X, pady=10)

        def assign():
            if not staff_combo.get() or staff_combo.get() == 'Any':
                messagebox.showerror("Error", "Please select a staff member.")
                return
            try:
                staff_id = int(staff_combo.get().split(':')[0])
                from university_system.modules.domain.barber.services.barber_core import AppointmentManager
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    AppointmentManager.assign_staff(appt['appointment_id'], staff_id)
                    messagebox.showinfo("Success", "Staff assigned!")
                    assign_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(assign_window, text="Assign", command=assign).pack(pady=10)

    def set_staff_commission(self):
        """Function 32: Set staff commission"""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a staff member.")
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        comm_window = tk.Toplevel(self.parent)
        comm_window.title(f"Commission - {staff_name}")
        comm_window.geometry("400x300")
        comm_window.transient(self.parent)
        comm_window.grab_set()

        ttk.Label(comm_window, text=f"Set Commission for {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(comm_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Commission Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['percentage', 'flat_rate'], width=15)
        type_combo.set('percentage')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Rate (% or £):").grid(row=1, column=0, sticky=tk.W, pady=5)
        rate_var = tk.StringVar(value="20")
        ttk.Entry(frame, textvariable=rate_var, width=10).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="For Service (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, values=['All Services'] + list(self.appt_service_combo['values']), width=25)
        service_combo.set('All Services')
        service_combo.grid(row=2, column=1, pady=5)

        def save_commission():
            try:
                service_id = None
                if service_combo.get() != 'All Services':
                    service_id = int(service_combo.get().split(':')[0])

                from university_system.modules.domain.barber.services.barber_core import CommissionManager
                CommissionManager.set_commission(
                    staff_id=staff_id,
                    commission_type=type_combo.get(),
                    rate=float(rate_var.get()),
                    service_id=service_id
                )
                messagebox.showinfo("Success", "Commission saved!")
                comm_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(comm_window, text="Save", command=save_commission).pack(pady=10)

    def view_staff_calendar(self):
        """Function 33: View staff calendar"""
        selected = self.staff_tree.selection()
        staff_id = None
        staff_name = "All Staff"
        if selected:
            item = self.staff_tree.item(selected[0])
            staff_id = item['values'][0]
            staff_name = item['values'][1]

        cal_window = tk.Toplevel(self.parent)
        cal_window.title(f"Calendar - {staff_name}")
        cal_window.geometry("800x500")
        cal_window.transient(self.parent)

        # Week navigation
        nav_frame = ttk.Frame(cal_window, padding="10")
        nav_frame.pack(fill=tk.X)

        current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_var = tk.StringVar(value=current_week_start.strftime('%Y-%m-%d'))

        def prev_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') - timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_calendar()

        def next_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') + timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_calendar()

        ttk.Button(nav_frame, text="< Prev", command=prev_week).pack(side=tk.LEFT)
        ttk.Label(nav_frame, textvariable=week_var, font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Button(nav_frame, text="Next >", command=next_week).pack(side=tk.LEFT)

        # Calendar display
        columns = ('time', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
        tree = ttk.Treeview(cal_window, columns=columns, show='headings', height=18)

        tree.heading('time', text='Time')
        for i, day in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
            tree.heading(columns[i + 1], text=day)
            tree.column(columns[i + 1], width=90)
        tree.column('time', width=60)

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load_calendar():
            for item in tree.get_children():
                tree.delete(item)

            start = datetime.strptime(week_var.get(), '%Y-%m-%d')
            time_slots = self._get_time_slots()

            try:
                with get_db_connection() as conn:
                    for time_slot in time_slots:
                        row = [time_slot]
                        for i in range(7):
                            day_date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                            query = """
                                SELECT customer_name FROM barber_appointments
                                WHERE appointment_date = ? AND appointment_time = ?
                            """
                            params = [day_date, time_slot]
                            if staff_id:
                                query += " AND staff_id = ?"
                                params.append(staff_id)

                            appt = conn.execute(query, params).fetchone()
                            row.append(appt['customer_name'][:12] if appt else '')

                        tree.insert('', tk.END, values=row)
            except Exception as e:
                logger.error(f"Error loading calendar: {e}")

        load_calendar()

    def toggle_staff_availability(self):
        """Function 34: Toggle staff availability"""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a staff member.")
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]
        current_status = item['values'][4]

        new_status = 'Inactive' if current_status == 'Active' else 'Active'
        if not messagebox.askyesno("Confirm", f"Set {staff_name} to {new_status}?"):
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import StaffManager
            StaffManager.set_availability(staff_id, new_status == 'Active')
            messagebox.showinfo("Success", f"{staff_name} is now {new_status}.")
            self._load_staff()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_staff_photo(self):
        """Function 35: Add staff photo"""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a staff member.")
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]

        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")],
            title="Select Staff Photo"
        )
        if not file_path:
            return

        try:
            from university_system.modules.domain.barber.services.barber_core import StaffManager
            StaffManager.add_photo(staff_id, file_path)
            messagebox.showinfo("Success", "Photo added!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def send_staff_notification(self):
        """Function 36: Send staff notification"""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a staff member.")
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        notif_window = tk.Toplevel(self.parent)
        notif_window.title(f"Notify {staff_name}")
        notif_window.geometry("400x300")
        notif_window.transient(self.parent)
        notif_window.grab_set()

        ttk.Label(notif_window, text=f"Send Notification to {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(notif_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Subject:").pack(anchor=tk.W)
        subject_var = tk.StringVar(value="Schedule Update")
        ttk.Entry(frame, textvariable=subject_var, width=40).pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Message:").pack(anchor=tk.W)
        msg_text = tk.Text(frame, height=6, width=40)
        msg_text.pack(fill=tk.BOTH, expand=True, pady=5)

        def send():
            try:
                from university_system.modules.domain.barber.services.barber_core import StaffManager
                staff = StaffManager.get_staff(staff_id)
                if staff and staff.get('email') and EMAIL_AVAILABLE:
                    from university_system.infrastructure.email.email_service import send_email
                    send_email(
                        staff['email'],
                        subject_var.get(),
                        msg_text.get('1.0', tk.END).strip()
                    )
                    messagebox.showinfo("Success", "Notification sent!")
                    notif_window.destroy()
                else:
                    messagebox.showerror("Error", "Staff has no email or email service unavailable.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(notif_window, text="Send", command=send).pack(pady=10)

    # ==================== FINANCIAL & PAYMENTS FUNCTIONS (37-44) ====================

    def _update_finance_summary(self):
        """Update finance summary labels"""
        try:
            from university_system.modules.domain.barber.services.barber_core import TransactionManager
            today = datetime.now().strftime('%Y-%m-%d')

            # Use get_daily_revenue() which returns a dict with revenue info
            daily_revenue = TransactionManager.get_daily_revenue(today)
            total_sales = daily_revenue.get('total_revenue') or 0
            self.daily_sales_label.config(text=f"Today's Sales: £{total_sales:.2f}")

            # Cash drawer balance - simplified (show today's cash transactions)
            cash_revenue = daily_revenue.get('service_revenue') or 0
            self.cash_drawer_label.config(text=f"Cash Revenue: £{cash_revenue:.2f}")

            # Outstanding - show pending/unpaid appointments count
            # Note: TransactionManager doesn't have get_outstanding_total, so we'll show 0 for now
            self.outstanding_label.config(text=f"Outstanding: £0.00")

        except Exception as e:
            logger.error(f"Error updating finance summary: {e}")

    def apply_discount(self):
        """Function 37: Apply discount to transaction"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        discount_window = tk.Toplevel(self.parent)
        discount_window.title("Apply Discount")
        discount_window.geometry("350x250")
        discount_window.transient(self.parent)
        discount_window.grab_set()

        ttk.Label(discount_window, text=f"Apply Discount to {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(discount_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Discount Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['percentage', 'fixed_amount'], width=15)
        type_combo.set('percentage')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Value (% or £):").grid(row=1, column=0, sticky=tk.W, pady=5)
        value_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=value_var, width=10).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Loyalty discount")
        ttk.Entry(frame, textvariable=reason_var, width=25).grid(row=2, column=1, pady=5)

        def apply():
            try:
                from university_system.modules.domain.barber.services.barber_core import (
                    AppointmentManager, DiscountManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    DiscountManager.apply_discount(
                        appointment_id=appt['appointment_id'],
                        discount_type=type_combo.get(),
                        value=float(value_var.get()),
                        reason=reason_var.get(),
                        applied_by=self.current_user.get('username')
                    )
                    messagebox.showinfo("Success", "Discount applied!")
                    discount_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(discount_window, text="Apply Discount", command=apply).pack(pady=10)

    def issue_refund(self):
        """Function 38: Issue refund"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        refund_window = tk.Toplevel(self.parent)
        refund_window.title("Issue Refund")
        refund_window.geometry("400x300")
        refund_window.transient(self.parent)
        refund_window.grab_set()

        ttk.Label(refund_window, text=f"Issue Refund for {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(refund_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Refund Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['full', 'partial'], width=15)
        type_combo.set('full')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Amount (for partial):").grid(row=1, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_text = tk.Text(frame, height=3, width=25)
        reason_text.grid(row=2, column=1, pady=5)

        def process_refund():
            try:
                from university_system.modules.domain.barber.services.barber_core import (
                    AppointmentManager, RefundManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    amount = None
                    if type_combo.get() == 'partial':
                        amount = float(amount_var.get())

                    RefundManager.issue_refund(
                        appointment_id=appt['appointment_id'],
                        refund_type=type_combo.get(),
                        amount=amount,
                        reason=reason_text.get('1.0', tk.END).strip(),
                        processed_by=self.current_user.get('username')
                    )
                    messagebox.showinfo("Success", "Refund processed!")
                    refund_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(refund_window, text="Process Refund", command=process_refund).pack(pady=10)

    def view_daily_sales(self):
        """Function 39: View daily sales"""
        sales_window = tk.Toplevel(self.parent)
        sales_window.title("Daily Sales Report")
        sales_window.geometry("600x450")
        sales_window.transient(self.parent)

        # Date selection
        date_frame = ttk.Frame(sales_window, padding="10")
        date_frame.pack(fill=tk.X)

        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(date_frame, textvariable=date_var, width=12).pack(side=tk.LEFT, padx=5)

        # Sales display
        sales_text = tk.Text(sales_window, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(sales_window, orient=tk.VERTICAL, command=sales_text.yview)
        sales_text.configure(yscrollcommand=scrollbar.set)

        sales_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_sales():
            sales_text.delete('1.0', tk.END)
            try:
                from university_system.modules.domain.barber.services.barber_core import TransactionManager
                # Use get_daily_revenue() which returns a dict
                revenue_data = TransactionManager.get_daily_revenue(date_var.get())

                # Format as text report
                report = f"=== Daily Sales Report ===\n"
                report += f"Date: {date_var.get()}\n\n"
                report += f"Transactions: {revenue_data['transaction_count'] or 0}\n"
                report += f"Service Revenue: £{(revenue_data['service_revenue'] or 0):.2f}\n"
                report += f"Tips: £{(revenue_data['tips'] or 0):.2f}\n"
                report += f"Total Revenue: £{(revenue_data['total_revenue'] or 0):.2f}\n"

                sales_text.insert('1.0', report)
            except Exception as e:
                sales_text.insert('1.0', f"Error: {e}")

        ttk.Button(date_frame, text="Load", command=load_sales).pack(side=tk.LEFT, padx=10)
        load_sales()

    def generate_financial_report(self):
        """Function 40: Generate financial report"""
        report_window = tk.Toplevel(self.parent)
        report_window.title("Financial Report")
        report_window.geometry("700x500")
        report_window.transient(self.parent)

        # Options
        options_frame = ttk.Frame(report_window, padding="10")
        options_frame.pack(fill=tk.X)

        ttk.Label(options_frame, text="From:").pack(side=tk.LEFT)
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=to_var, width=12).pack(side=tk.LEFT, padx=5)

        # Report display
        report_text = tk.Text(report_window, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=report_text.yview)
        report_text.configure(yscrollcommand=scrollbar.set)

        report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def generate():
            report_text.delete('1.0', tk.END)
            try:
                from university_system.modules.domain.barber.services.barber_core import ReportManager

                # Use generate_sales_report which returns a dictionary
                sales_data = ReportManager.generate_sales_report(from_var.get(), to_var.get())

                # Format as text report
                report = "=== Financial Report ===\n\n"
                report += f"Period: {sales_data['period']['start']} to {sales_data['period']['end']}\n"
                report += f"Generated: {sales_data['generated_at']}\n\n"

                # Summary section
                summary = sales_data.get('summary', {})
                report += "SUMMARY:\n"
                report += f"  Total Appointments: {summary.get('total_appointments') or 0}\n"
                report += f"  Service Revenue: ${(summary.get('service_revenue') or 0):.2f}\n"
                report += f"  Total Tips: ${(summary.get('total_tips') or 0):.2f}\n"
                report += f"  Avg Service Value: ${(summary.get('avg_service_value') or 0):.2f}\n"
                total = (summary.get('service_revenue') or 0) + (summary.get('total_tips') or 0)
                report += f"  TOTAL REVENUE: ${total:.2f}\n\n"

                # Revenue by service
                report += "REVENUE BY SERVICE:\n"
                by_service = sales_data.get('by_service', [])
                if by_service:
                    for svc in by_service:
                        service_name = svc.get('service_name', 'Unknown')
                        count = svc.get('count') or 0
                        revenue = svc.get('revenue') or 0
                        report += f"  {service_name}: {count} bookings, ${revenue:.2f}\n"
                else:
                    report += "  No service data available\n"

                # Revenue by staff
                report += "\nREVENUE BY STAFF:\n"
                by_staff = sales_data.get('by_staff', [])
                if by_staff:
                    for staff in by_staff:
                        staff_name = staff.get('staff_name', 'Unknown')
                        appointments = staff.get('appointments') or 0
                        revenue = staff.get('revenue') or 0
                        tips = staff.get('tips') or 0
                        report += f"  {staff_name}: {appointments} appointments, "
                        report += f"${revenue:.2f} revenue, ${tips:.2f} tips\n"
                else:
                    report += "  No staff data available\n"

                report_text.insert('1.0', report)
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"Error generating financial report: {e}\n{error_detail}")
                report_text.insert('1.0', f"Error generating report: {e}")

        ttk.Button(options_frame, text="Generate", command=generate).pack(side=tk.LEFT, padx=20)
        generate()

    def track_cash_drawer(self):
        """Function 41: Track cash drawer"""
        drawer_window = tk.Toplevel(self.parent)
        drawer_window.title("Cash Drawer")
        drawer_window.geometry("500x400")
        drawer_window.transient(self.parent)
        drawer_window.grab_set()

        ttk.Label(drawer_window, text="Cash Drawer Management",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        # Current balance
        try:
            from university_system.modules.domain.barber.services.barber_core import CashDrawerManager
            balance = CashDrawerManager.get_balance()
        except Exception:
            balance = 0.0

        balance_label = ttk.Label(drawer_window, text=f"Current Balance: £{balance:.2f}",
                                 font=('Helvetica', 12, 'bold'))
        balance_label.pack(pady=10)

        # Actions
        frame = ttk.Frame(drawer_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Action:").grid(row=0, column=0, sticky=tk.W, pady=5)
        action_combo = ttk.Combobox(frame, values=['add', 'remove', 'count'], width=15)
        action_combo.set('add')
        action_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Amount (£):").grid(row=1, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Note:").grid(row=2, column=0, sticky=tk.W, pady=5)
        note_var = tk.StringVar()
        ttk.Entry(frame, textvariable=note_var, width=30).grid(row=2, column=1, pady=5)

        def execute_action():
            try:
                from university_system.modules.domain.barber.services.barber_core import CashDrawerManager
                action = action_combo.get()
                amount = float(amount_var.get()) if amount_var.get() else 0

                # Note: CashDrawerManager only has open_drawer() and close_drawer() methods
                # For add/remove/count operations, we need to use open/close drawer workflow
                if action == 'add':
                    # Open a drawer session with initial amount
                    drawer_id = CashDrawerManager.open_drawer(
                        opening_amount=amount,
                        opened_by=self.current_user.get('username', 'System')
                    )
                    messagebox.showinfo("Success", f"Drawer opened with £{amount:.2f}\nNote: {note_var.get()}")
                elif action == 'remove':
                    messagebox.showinfo("Info", "Use 'Close Drawer' function to reconcile cash at end of shift")
                elif action == 'count':
                    messagebox.showinfo("Info", "Use 'Close Drawer' function to record final count")

                balance_label.config(text=f"Current Balance: £{amount:.2f}")
                self._update_finance_summary()

            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Execute", command=execute_action).grid(row=3, column=0, columnspan=2, pady=20)

    def create_gift_card(self):
        """Function 42: Create gift card"""
        gift_window = tk.Toplevel(self.parent)
        gift_window.title("Create Gift Card")
        gift_window.geometry("400x350")
        gift_window.transient(self.parent)
        gift_window.grab_set()

        ttk.Label(gift_window, text="Create Gift Card",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(gift_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Value (£):").grid(row=0, column=0, sticky=tk.W, pady=5)
        value_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=value_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Recipient Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=25).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Recipient Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=email_var, width=25).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Message:").grid(row=3, column=0, sticky=tk.W, pady=5)
        msg_text = tk.Text(frame, height=3, width=25)
        msg_text.grid(row=3, column=1, pady=5)

        def create():
            try:
                from university_system.modules.domain.barber.services.barber_core import GiftCardManager
                card_code = GiftCardManager.create_card(
                    value=float(value_var.get()),
                    recipient_name=name_var.get().strip(),
                    recipient_email=email_var.get().strip(),
                    message=msg_text.get('1.0', tk.END).strip(),
                    created_by=self.current_user.get('username')
                )
                messagebox.showinfo("Success", f"Gift card created!\nCode: {card_code}")
                gift_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(gift_window, text="Create Gift Card", command=create).pack(pady=10)

    def redeem_gift_card(self):
        """Function 43: Redeem gift card"""
        redeem_window = tk.Toplevel(self.parent)
        redeem_window.title("Redeem Gift Card")
        redeem_window.geometry("400x250")
        redeem_window.transient(self.parent)
        redeem_window.grab_set()

        ttk.Label(redeem_window, text="Redeem Gift Card",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(redeem_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Gift Card Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        code_var = tk.StringVar()
        ttk.Entry(frame, textvariable=code_var, width=20).grid(row=0, column=1, pady=5)

        balance_label = ttk.Label(frame, text="Balance: --")
        balance_label.grid(row=1, column=0, columnspan=2, pady=10)

        def check_balance():
            try:
                from university_system.modules.domain.barber.services.barber_core import GiftCardManager
                # Use get_gift_card() instead of get_card()
                card = GiftCardManager.get_gift_card(code_var.get().strip())
                if card:
                    balance_label.config(text=f"Balance: £{card['current_balance']:.2f}")
                else:
                    balance_label.config(text="Invalid card code")
            except Exception as e:
                balance_label.config(text=f"Error: {e}")

        ttk.Button(frame, text="Check Balance", command=check_balance).grid(row=2, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Amount to Redeem (£):").grid(row=3, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=3, column=1, pady=5)

        def redeem():
            try:
                from university_system.modules.domain.barber.services.barber_core import GiftCardManager
                # Use redeem_gift_card() instead of redeem()
                success, message = GiftCardManager.redeem_gift_card(
                    code=code_var.get().strip(),
                    amount=float(amount_var.get()),
                    redeemed_by=self.current_user.get('username')
                )
                if success:
                    messagebox.showinfo("Success", message)
                    redeem_window.destroy()
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Redeem", command=redeem).grid(row=4, column=0, columnspan=2, pady=10)

    def view_outstanding_payments(self):
        """Function 44: View outstanding payments"""
        outstanding_window = tk.Toplevel(self.parent)
        outstanding_window.title("Outstanding Payments")
        outstanding_window.geometry("700x400")
        outstanding_window.transient(self.parent)

        columns = ('appt', 'date', 'customer', 'service', 'amount', 'status')
        tree = ttk.Treeview(outstanding_window, columns=columns, show='headings', height=15)

        tree.heading('appt', text='Appointment')
        tree.heading('date', text='Date')
        tree.heading('customer', text='Customer')
        tree.heading('service', text='Service')
        tree.heading('amount', text='Amount')
        tree.heading('status', text='Status')

        for col in columns:
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(outstanding_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            # Query unpaid appointments directly since TransactionManager doesn't have get_outstanding_payments()
            from university_system.infrastructure.database.db import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT appointment_id, appointment_date, customer_name, service_name, price, payment_status
                    FROM barber_appointments
                    WHERE payment_status IN ('pending', 'unpaid') AND status != 'cancelled'
                    ORDER BY appointment_date DESC
                ''')
                for row in cursor.fetchall():
                    tree.insert('', tk.END, values=(
                        row[0], row[1], row[2], row[3],
                        f"£{row[4]:.2f}", row[5]
                    ))
        except Exception as e:
            logger.error(f"Error loading outstanding: {e}")

    # ==================== ANALYTICS & REPORTING FUNCTIONS (45-50) ====================

    def show_dashboard(self):
        """Function 45: Show analytics dashboard"""
        dash_window = tk.Toplevel(self.parent)
        dash_window.title("Analytics Dashboard")
        dash_window.geometry("900x600")
        dash_window.transient(self.parent)

        # Summary cards
        cards_frame = ttk.Frame(dash_window, padding="10")
        cards_frame.pack(fill=tk.X)

        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            stats = AnalyticsManager.get_dashboard_stats()

            metrics = [
                ("Today's Appointments", stats.get('today_appointments', 0)),
                ("This Week's Revenue", f"£{(stats.get('week_revenue') or 0):.2f}"),
                ("New Customers", stats.get('new_customers', 0)),
                ("Average Rating", f"{stats.get('avg_rating', 0):.1f}/5"),
                ("Completion Rate", f"{stats.get('completion_rate', 0):.0f}%"),
                ("No-Show Rate", f"{stats.get('no_show_rate', 0):.0f}%")
            ]

            for i, (label, value) in enumerate(metrics):
                card = ttk.LabelFrame(cards_frame, text=label, padding="10")
                card.grid(row=0, column=i, padx=5, pady=5)
                ttk.Label(card, text=str(value), font=('Helvetica', 16, 'bold')).pack()

        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")

        # Charts section (text-based)
        charts_frame = ttk.LabelFrame(dash_window, text="Recent Trends", padding="10")
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.dashboard_text = tk.Text(charts_frame, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(charts_frame, orient=tk.VERTICAL, command=self.dashboard_text.yview)
        self.dashboard_text.configure(yscrollcommand=scrollbar.set)

        self.dashboard_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            stats = AnalyticsManager.get_dashboard_stats()

            # Format dashboard statistics as text report
            report = "=== Barber Shop Dashboard ===\n\n"
            report += "TODAY'S SUMMARY:\n"
            report += f"  Total Appointments: {stats['today']['total_appointments'] or 0}\n"
            report += f"  Completed: {stats['today']['completed'] or 0}\n"
            report += f"  Scheduled: {stats['today']['scheduled'] or 0}\n"
            report += f"  No-Shows: {stats['today']['no_shows'] or 0}\n"
            report += f"  Revenue: ${(stats['today']['revenue'] or 0):.2f}\n"
            report += f"  Tips: ${(stats['today']['tips'] or 0):.2f}\n\n"
            report += f"ACTIVE STAFF: {stats['active_staff'] or 0}\n\n"
            report += "THIS MONTH:\n"
            report += f"  Appointments: {stats['monthly']['appointments'] or 0}\n"
            report += f"  Revenue: ${(stats['monthly']['revenue'] or 0):.2f}\n"

            self.dashboard_text.insert('1.0', report)
        except Exception as e:
            self.dashboard_text.insert('1.0', f"Error loading trends: {e}")

    def generate_peak_hours_report(self):
        """Function 46: Generate peak hours report"""
        self.analytics_text.delete('1.0', tk.END)
        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            from datetime import datetime, timedelta

            # Use last 30 days as default date range
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            peak_hours = AnalyticsManager.get_peak_hours(start_date, end_date)

            # Format as text report
            report = f"=== Peak Hours Report ===\n"
            report += f"Period: {start_date} to {end_date}\n\n"

            if peak_hours:
                report += "Time         | Appointments\n"
                report += "-" * 30 + "\n"
                for hour in peak_hours:
                    time_str = hour['appointment_time'] if hour['appointment_time'] else 'N/A'
                    count = hour['count'] if hour['count'] else 0
                    report += f"{time_str:12} | {count}\n"
            else:
                report += "No appointment data available for this period.\n"

            self.analytics_text.insert('1.0', report)
        except Exception as e:
            self.analytics_text.insert('1.0', f"Error: {e}")

    def customer_retention_report(self):
        """Function 47: Generate customer retention report"""
        self.analytics_text.delete('1.0', tk.END)
        try:
            from university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            from datetime import datetime, timedelta

            # Use last 90 days as default date range
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

            retention = AnalyticsManager.get_customer_retention(start_date, end_date)

            # Format as text report
            report = f"=== Customer Retention Report ===\n"
            report += f"Period: {start_date} to {end_date}\n\n"
            report += f"Total Unique Customers: {retention.get('total_customers') or 0}\n"
            report += f"New Customers: {retention.get('new_customers') or 0}\n"
            report += f"Returning Customers: {retention.get('returning_customers') or 0}\n"
            report += f"Retention Rate: {(retention.get('retention_rate') or 0):.1f}%\n"

            self.analytics_text.insert('1.0', report)
        except Exception as e:
            self.analytics_text.insert('1.0', f"Error: {e}")

    def export_report_pdf(self):
        """Function 48: Export report to PDF (currently exports as text file)"""
        report_content = self.analytics_text.get('1.0', tk.END).strip()
        if not report_content:
            messagebox.showwarning("Warning", "No report to export. Generate a report first.")
            return

        # Note: Currently exports as PDF using reportlab
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Report"
        )
        if not file_path:
            return

        try:
            # Try to use reportlab for PDF export
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.units import inch

                # Create PDF
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()

                # Add title
                title = Paragraph("Barber Shop Report", styles['Title'])
                story.append(title)
                story.append(Spacer(1, 0.2*inch))

                # Add report content (preserve formatting)
                from datetime import datetime
                timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
                story.append(timestamp)
                story.append(Spacer(1, 0.3*inch))

                # Split content into lines and add as paragraphs
                for line in report_content.split('\n'):
                    if line.strip():
                        p = Paragraph(line.replace('<', '&lt;').replace('>', '&gt;'), styles['Normal'])
                        story.append(p)
                    else:
                        story.append(Spacer(1, 0.1*inch))

                doc.build(story)
                messagebox.showinfo("Success", f"Report exported to:\n{file_path}")

            except ImportError:
                # Fallback to text export if reportlab not available
                if not file_path.endswith('.txt'):
                    file_path = file_path.rsplit('.', 1)[0] + '.txt'

                with open(file_path, 'w') as f:
                    f.write(f"Barber Shop Report\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(report_content)

            messagebox.showinfo("Success", f"Report exported to {file_path}")
            log_activity('export', 'barber_report', details={'file': file_path})
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def schedule_automated_reports(self):
        """Function 49: Schedule automated reports"""
        sched_window = tk.Toplevel(self.parent)
        sched_window.title("Schedule Reports")
        sched_window.geometry("450x400")
        sched_window.transient(self.parent)
        sched_window.grab_set()

        ttk.Label(sched_window, text="Schedule Automated Reports",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(sched_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Report Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['daily_sales', 'weekly_summary', 'monthly_performance', 'customer_retention'], width=20)
        type_combo.set('daily_sales')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Frequency:").grid(row=1, column=0, sticky=tk.W, pady=5)
        freq_combo = ttk.Combobox(frame, values=['daily', 'weekly', 'monthly'], width=15)
        freq_combo.set('daily')
        freq_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=['06:00', '08:00', '10:00', '12:00', '18:00', '20:00'], width=10)
        time_combo.set('08:00')
        time_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Send to Email:").grid(row=3, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar(value=self.current_user.get('email', ''))
        ttk.Entry(frame, textvariable=email_var, width=30).grid(row=3, column=1, pady=5)

        # Existing schedules
        ttk.Label(frame, text="Existing Schedules:").grid(row=4, column=0, sticky=tk.W, pady=(20, 5))

        listbox = tk.Listbox(frame, height=6, width=40)
        listbox.grid(row=5, column=0, columnspan=2, pady=5)

        try:
            from university_system.modules.domain.barber.services.barber_core import ScheduledReportManager
            schedules = ScheduledReportManager.get_scheduled_reports()
            for sched in schedules:
                freq_text = sched.get('frequency', 'N/A')
                report_type = sched.get('report_type', 'Unknown')
                listbox.insert(tk.END, f"{report_type} - {freq_text}")
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")

        def save_schedule():
            try:
                from university_system.modules.domain.barber.services.barber_core import ScheduledReportManager

                # Build parameters dict with frequency and time
                params_dict = {
                    'time': time_combo.get()
                }
                import json
                params_str = json.dumps(params_dict)

                ScheduledReportManager.schedule_report(
                    report_type=type_combo.get(),
                    frequency=freq_combo.get(),
                    recipients=email_var.get().strip(),
                    created_by=self.current_user.get('username', 'System'),
                    params=params_str
                )
                messagebox.showinfo("Success", "Report schedule created!")
                sched_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                logger.error(f"Error creating schedule: {e}")

        ttk.Button(sched_window, text="Save Schedule", command=save_schedule).pack(pady=10)

    def view_audit_log(self):
        """Function 50: View audit log"""
        audit_window = tk.Toplevel(self.parent)
        audit_window.title("Audit Log")
        audit_window.geometry("900x500")
        audit_window.transient(self.parent)

        # Filter
        filter_frame = ttk.Frame(audit_window, padding="10")
        filter_frame.pack(fill=tk.X)

        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT)
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Action:").pack(side=tk.LEFT, padx=(10, 0))
        action_combo = ttk.Combobox(filter_frame, values=['All', 'create', 'update', 'delete', 'payment', 'refund'], width=12)
        action_combo.set('All')
        action_combo.pack(side=tk.LEFT, padx=5)

        columns = ('timestamp', 'user', 'action', 'entity', 'entity_id', 'details')
        tree = ttk.Treeview(audit_window, columns=columns, show='headings', height=18)

        tree.heading('timestamp', text='Timestamp')
        tree.heading('user', text='User')
        tree.heading('action', text='Action')
        tree.heading('entity', text='Entity')
        tree.heading('entity_id', text='Entity ID')
        tree.heading('details', text='Details')

        tree.column('timestamp', width=150)
        tree.column('user', width=100)
        tree.column('action', width=80)
        tree.column('entity', width=100)
        tree.column('entity_id', width=100)
        tree.column('details', width=300)

        scrollbar = ttk.Scrollbar(audit_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_log():
            for item in tree.get_children():
                tree.delete(item)
            try:
                from university_system.modules.domain.barber.services.barber_core import AuditLogManager
                action_filter = None if action_combo.get() == 'All' else action_combo.get()

                # Use correct method name and parameters
                logs = AuditLogManager.get_audit_log(
                    start_date=from_var.get(),
                    end_date=to_var.get(),
                    action_type=action_filter,
                    limit=500
                )

                for log in logs:
                    # Map barber_audit_log columns to tree view
                    tree.insert('', tk.END, values=(
                        log.get('created_at', ''),
                        log.get('user_id', ''),
                        log.get('action_type', ''),
                        log.get('entity_type', ''),
                        log.get('entity_id', ''),
                        log.get('details', '')[:50]
                    ))
            except Exception as e:
                logger.error(f"Error loading audit log: {e}")
                messagebox.showerror("Error", f"Failed to load audit log: {e}")

        ttk.Button(filter_frame, text="Search", command=load_log).pack(side=tk.LEFT, padx=20)
        load_log()

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("Refunds", "Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("Barber Shop Refunds", "Barber Shop Refunds"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("Search", "Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("Search:", "Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with 7 columns
        columns = ('transaction_id', 'date', 'customer', 'amount', 'payment_method', 'status', 'reference')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('transaction_id', text=_t('Transaction ID', 'Transaction ID'))
        self.refunds_tree.heading('date', text=_t('Date', 'Date'))
        self.refunds_tree.heading('customer', text=_t('Customer', 'Customer'))
        self.refunds_tree.heading('amount', text=_t('Amount', 'Amount'))
        self.refunds_tree.heading('payment_method', text=_t('Payment Method', 'Payment Method'))
        self.refunds_tree.heading('status', text=_t('Status', 'Status'))
        self.refunds_tree.heading('reference', text=_t('Reference', 'Reference'))

        self.refunds_tree.column('transaction_id', width=100)
        self.refunds_tree.column('date', width=120)
        self.refunds_tree.column('customer', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)
        self.refunds_tree.column('reference', width=150)

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
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text=_t("Process Refund", "Process Refund"),
                  command=self.process_barber_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("View Details", "View Details"),
                  command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("Refresh", "Refresh"),
                  command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("Export to CSV", "Export to CSV"),
                  command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        logger.info("Refreshing barber shop refunds list")

        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()
            logger.debug(f"Search term: '{search_term}'")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        bt.transaction_id,
                        bt.created_at,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number
                    FROM barber_transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    WHERE bt.transaction_type = 'service'
                    ORDER BY bt.created_at DESC
                """

                logger.debug("Executing refunds query")
                cursor.execute(query)
                transactions = cursor.fetchall()
                logger.info(f"Loaded {len(transactions)} transactions")

                displayed_count = 0
                for trans in transactions:
                    try:
                        transaction_id, date, customer_id, customer_name, amount, tip_amount, payment_method, status, reference = trans

                        # Calculate total amount
                        total_amount = (amount or 0) + (tip_amount or 0)

                        # Apply search filter
                        if search_term:
                            searchable = f"{transaction_id} {customer_id} {customer_name or ''} {status} {reference or ''}".lower()
                            if search_term not in searchable:
                                continue

                        # Format date
                        if date:
                            try:
                                date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                            except Exception as date_err:
                                logger.warning(f"Error parsing date '{date}': {date_err}")
                                formatted_date = date
                        else:
                            formatted_date = ''

                        # Color code by status
                        tag = 'refunded' if status == 'refunded' else 'completed'

                        self.refunds_tree.insert('', tk.END, values=(
                            transaction_id,
                            formatted_date,
                            customer_name or customer_id,
                            f"£{total_amount:.2f}",
                            payment_method or 'N/A',
                            status or 'completed',
                            reference or ''
                        ), tags=(tag,))
                        displayed_count += 1

                    except Exception as trans_err:
                        logger.error(f"Error processing transaction {transaction_id if 'transaction_id' in locals() else 'unknown'}: {trans_err}")
                        # Continue processing other transactions
                        continue

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

                logger.info(f"Displayed {displayed_count} transactions after filtering")

        except Exception as e:
            error_msg = f"Failed to load refunds list: {str(e)}"
            logger.error(f"Error refreshing refunds list: {e}", exc_info=True)
            messagebox.showerror("Database Error", error_msg)

    def process_barber_refund(self):
        """Process a refund for a barber shop transaction"""
        logger.info("Starting barber shop refund process")

        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            logger.warning("No transaction selected for refund")
            messagebox.showwarning("No Selection", "Please select a transaction to refund.")
            return

        try:
            item = self.refunds_tree.item(selection[0])
            values = item['values']
            transaction_id = values[0]
            amount_str = values[3]
            status = values[5]

            logger.info(f"Processing refund for transaction {transaction_id}, current status: {status}")

            # Check if already refunded
            if status == 'refunded':
                logger.warning(f"Transaction {transaction_id} already refunded")
                messagebox.showwarning("Already Refunded", "This transaction has already been refunded.")
                return

            # Parse amount
            try:
                amount = float(amount_str.replace('£', '').replace(',', ''))
                logger.debug(f"Parsed refund amount: £{amount:.2f}")
            except Exception as parse_err:
                logger.error(f"Error parsing amount '{amount_str}': {parse_err}")
                messagebox.showerror("Invalid Amount", f"Cannot parse amount '{amount_str}'. Please contact support.")
                return

            # Confirm refund
            if not messagebox.askyesno("Confirm Refund", f"Refund £{amount:.2f} for Transaction #{transaction_id}?"):
                logger.info(f"Refund cancelled by user for transaction {transaction_id}")
                return

            # Get customer ID
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT customer_id FROM barber_transactions WHERE transaction_id = ?",
                             (transaction_id,))
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Transaction {transaction_id} not found in database")
                    messagebox.showerror("Transaction Not Found", f"Transaction #{transaction_id} could not be found in the database.")
                    return
                customer_id = result[0]
                logger.info(f"Found customer ID: {customer_id}")

            # Show refund method dialog
            self.show_barber_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            error_msg = f"Failed to process refund: {str(e)}"
            logger.error(f"Error processing barber refund: {e}", exc_info=True)
            messagebox.showerror("Refund Error", error_msg)

    def show_barber_refund_method_dialog(self, transaction_id, amount, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("Select Refund Method", "Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("Select Refund Method", "Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if customer_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
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
            self._complete_barber_refund(transaction_id, amount, 'cash', customer_id)

        def refund_card():
            dialog.destroy()
            self._complete_barber_refund(transaction_id, amount, 'card', customer_id)

        def refund_student_account():
            if not FINANCE_AVAILABLE:
                messagebox.showerror(_t("Error", "Error"),
                                   _t("Finance system not available.", "Finance system not available."))
                return
            dialog.destroy()
            self.add_barber_refund_to_student_account(transaction_id, amount, customer_id)

        # Create buttons
        cash_btn = ttk.Button(buttons_frame, text=_t("💵 Refund as Cash", "💵 Refund as Cash"),
                             command=refund_cash, width=30)
        cash_btn.pack(pady=10)

        card_btn = ttk.Button(buttons_frame, text=_t("💳 Refund to Card", "💳 Refund to Card"),
                             command=refund_card, width=30)
        card_btn.pack(pady=10)

        account_btn = ttk.Button(buttons_frame, text=_t("🏦 Refund to Student Account", "🏦 Refund to Student Account"),
                                command=refund_student_account, width=30)
        account_btn.pack(pady=10)

        if not FINANCE_AVAILABLE:
            account_btn.config(state='disabled')

        ttk.Button(buttons_frame, text=_t("Cancel", "Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)

    def _complete_barber_refund(self, transaction_id, amount, refund_method, customer_id):
        """Complete the refund process (for cash/card)"""
        logger.info(f"Completing refund: Transaction {transaction_id}, Amount £{amount:.2f}, Method: {refund_method}")

        try:
            # Generate refund reference
            refund_ref = f"BARBER-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.debug(f"Generated refund reference: {refund_ref}")

            # Get processed_by
            processed_by = 'System'
            try:
                user = self.current_user or {}
                processed_by = user.get('username', 'System')
            except Exception as auth_err:
                logger.warning(f"Could not get authenticated user: {auth_err}")

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction reference
                logger.debug(f"Updating transaction {transaction_id} reference")
                cursor.execute("""
                    UPDATE barber_transactions
                    SET reference_number = ?
                    WHERE transaction_id = ?
                """, (refund_ref, transaction_id))

                if cursor.rowcount == 0:
                    raise Exception(f"Transaction {transaction_id} not found or could not be updated")

                # Use RefundManager to create refund record properly
                logger.debug(f"Creating refund record via RefundManager, processed by: {processed_by}")
                from university_system.modules.domain.barber.services.barber_core import RefundManager
                RefundManager.issue_refund(
                    transaction_id=transaction_id,
                    amount=amount,
                    reason=f'Refund via {refund_method}',
                    refund_type=refund_method,
                    processed_by=processed_by
                )

            logger.info(f"Transaction {transaction_id} refunded successfully")

            # Log activity
            try:
                log_activity('refund', 'barber_transaction',
                            details={
                                'transaction_id': transaction_id,
                                'amount': amount,
                                'method': refund_method,
                                'reference': refund_ref
                            })
                logger.debug("Activity logged successfully")
            except Exception as log_err:
                logger.warning(f"Failed to log activity: {log_err}")

            # Send receipt
            try:
                self.send_barber_refund_receipt(customer_id, amount, refund_method, refund_ref)
                logger.info("Refund receipt email sent")
            except Exception as email_err:
                logger.warning(f"Failed to send refund receipt: {email_err}")
                # Don't fail the whole refund if email fails

            # Notify finance GUI
            try:
                self.notify_barber_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)
                logger.debug("Finance system notified")
            except Exception as finance_err:
                logger.warning(f"Failed to notify finance system: {finance_err}")

            # Refresh list
            try:
                self.refresh_refunds_list()
            except Exception as refresh_err:
                logger.warning(f"Failed to refresh refunds list: {refresh_err}")

            logger.info(f"Refund completed successfully: {refund_ref}")
            messagebox.showinfo("Success", f"Refund processed successfully!\n\nReference: {refund_ref}\nAmount: £{amount:.2f}\nMethod: {refund_method.title()}")

        except Exception as e:
            error_msg = f"Failed to complete refund: {str(e)}"
            logger.error(f"Error completing barber refund for transaction {transaction_id}: {e}", exc_info=True)
            messagebox.showerror("Refund Failed", error_msg)

    def add_barber_refund_to_student_account(self, transaction_id, amount, customer_id):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("Error", "Error"),
                               _t("Finance system not available.", "Finance system not available."))
            return

        try:
            # Ensure student account exists
            ensure_student_finance_account_exists(customer_id)

            # Generate refund reference
            refund_ref = f"BARBER-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Get processed_by
            processed_by = 'System'
            try:
                user = self.current_user or {}
                processed_by = user.get('username', 'System')
            except Exception as auth_err:
                logger.warning(f"Could not get authenticated user: {auth_err}")

            # First, create refund in barber system (uses its own transaction)
            from university_system.modules.domain.barber.services.barber_core import RefundManager
            RefundManager.issue_refund(
                transaction_id=transaction_id,
                amount=amount,
                reason='Refunded to student account',
                refund_type='student_account',
                processed_by=processed_by
            )

            # Then update student account and transaction reference (separate transaction)
            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction reference
                cursor.execute("""
                    UPDATE barber_transactions
                    SET reference_number = ?
                    WHERE transaction_id = ?
                """, (refund_ref, transaction_id))

                # Get account_id and balance before update
                cursor.execute("""
                    SELECT account_id, balance
                    FROM student_finance_accounts
                    WHERE student_id = ?
                """, (customer_id,))
                account_row = cursor.fetchone()

                if not account_row:
                    raise Exception(f"No finance account found for student {customer_id}")

                account_id = account_row[0]
                balance_before = account_row[1]
                balance_after = balance_before + amount

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                """, (amount, customer_id))

                # Log transaction in student_finance_transactions with all required fields
                cursor.execute("""
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_before, balance_after, description, reference_id)
                    VALUES (?, ?, 'credit', ?, ?, ?, ?, ?)
                """, (account_id, customer_id, amount, balance_before, balance_after, f'Barber shop refund', refund_ref))

                # Use the calculated balance
                new_balance = balance_after

            # Log activity
            log_activity('refund', 'barber_transaction',
                        details={
                            'transaction_id': transaction_id,
                            'amount': amount,
                            'method': 'student_account',
                            'reference': refund_ref,
                            'new_balance': new_balance
                        })

            # Send receipt
            self.send_barber_refund_receipt(customer_id, amount, 'student_account', refund_ref, new_balance)

            # Notify finance GUI
            self.notify_barber_finance_gui(transaction_id, amount, 'student_account', refund_ref, customer_id)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("Success", "Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding barber refund to student account: {e}")
            messagebox.showerror(_t("Error", "Error"), f"Failed to add refund to account: {str(e)}")

    def send_barber_refund_receipt(self, customer_id, amount, refund_method, refund_ref, new_balance=None):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            logger.info("Email service not available, skipping receipt")
            return

        try:
            # Get customer email - check multiple tables
            customer_email = None
            customer_name = None

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Try students table first (by student_id)
                cursor.execute("""
                    SELECT email_address, first_name || ' ' || last_name
                    FROM students
                    WHERE student_id = ?
                """, (customer_id,))
                result = cursor.fetchone()

                if result and result[0]:
                    customer_email = result[0]
                    customer_name = result[1] or customer_id
                else:
                    # Try users table (by username)
                    cursor.execute("""
                        SELECT email, first_name || ' ' || last_name
                        FROM users
                        WHERE username = ?
                    """, (customer_id,))
                    result = cursor.fetchone()

                    if result and result[0]:
                        customer_email = result[0]
                        customer_name = result[1] or customer_id
                    else:
                        # Try staff table (by username)
                        cursor.execute("""
                            SELECT email, name
                            FROM staff
                            WHERE username = ?
                        """, (customer_id,))
                        result = cursor.fetchone()

                        if result and result[0]:
                            customer_email = result[0]
                            customer_name = result[1] or customer_id

            if not customer_email:
                logger.warning(f"No email found for customer {customer_id} in any table (students/users/staff)")
                return

            if not customer_name:
                customer_name = customer_id

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text
            balance_text = ""
            if new_balance is not None:
                balance_text = f"Your new student account balance is: £{new_balance:.2f}"

            # Render email from template
            from university_system.infrastructure.email.template_utils import render_template
            subject, email_body = render_template('commerce/barber/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'original_transaction': str(transaction_id),
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method_display,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'balance_text': balance_text
            })

            # Fallback if template not found
            if not subject or not email_body:
                subject = f"Barber Shop Refund Receipt - {refund_ref}"
                email_body = f"Dear {customer_name},\n\nYour refund of £{amount:.2f} has been processed.\nReference: {refund_ref}"

            # Send email
            send_email(
                to_email=customer_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending barber refund receipt: {e}")

    def notify_barber_finance_gui(self, transaction_id, amount, refund_method, refund_ref, customer_id=None):
        """Notify finance system about the refund - integrates with main finance GUI"""
        try:
            conn = get_db_connection()
            if not conn:
                logger.warning("Could not get database connection for finance notification")
                return

            cursor = conn.cursor()

            try:
                # Create finance_refunds table if not exists (matches other GUIs schema)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        refund_reference TEXT UNIQUE,
                        department TEXT,
                        amount REAL,
                        refund_method TEXT,
                        refund_date TEXT,
                        refund_time TEXT,
                        transaction_reference TEXT,
                        processed_by TEXT,
                        notes TEXT
                    )
                ''')

                # Migrate finance_refunds table to ensure all columns exist
                cursor.execute("PRAGMA table_info(finance_refunds)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add missing columns if needed (for backward compatibility)
                if 'transaction_reference' not in columns:
                    cursor.execute('ALTER TABLE finance_refunds ADD COLUMN transaction_reference TEXT')
                    logger.info("Migration: Added transaction_reference column to finance_refunds table")

                if 'refund_time' not in columns:
                    cursor.execute('ALTER TABLE finance_refunds ADD COLUMN refund_time TEXT')
                    logger.info("Migration: Added refund_time column to finance_refunds table")

                if 'notes' not in columns:
                    cursor.execute('ALTER TABLE finance_refunds ADD COLUMN notes TEXT')
                    logger.info("Migration: Added notes column to finance_refunds table")

                # Get processed_by
                processed_by = 'System'
                try:
                    user = self.current_user or {}
                    processed_by = user.get('username', 'System')
                except Exception as auth_err:
                    logger.warning(f"Could not get authenticated user: {auth_err}")

                # Build notes with customer info
                notes = f'Barber Shop Service Refund - Transaction #{transaction_id}'
                if customer_id:
                    notes += f' - Customer: {customer_id}'

                # Insert into finance_refunds table (main refunds table for finance GUI)
                cursor.execute('''
                    INSERT INTO finance_refunds
                    (refund_reference, department, amount, refund_method,
                     refund_date, refund_time, transaction_reference, processed_by, notes)
                    VALUES (?, ?, ?, ?, date('now'), time('now'), ?, ?, ?)
                ''', (refund_ref, 'Barber Shop', amount, refund_method,
                      f'barber_transaction_{transaction_id}', processed_by, notes))

                conn.commit()
                logger.info(f"[Barber Shop] Refund recorded in finance system: {refund_ref}")

            except Exception as e:
                # Log error but don't fail the refund
                logger.warning(f"Could not notify finance system: {e}")
                # Don't raise - refund already processed

            conn.close()

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information about a transaction"""
        logger.info("Viewing transaction details")

        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            logger.warning("No transaction selected")
            messagebox.showwarning("No Selection", "Please select a transaction to view.")
            return

        try:
            item = self.refunds_tree.item(selection[0])
            values = item['values']
            transaction_id = values[0]
            logger.info(f"Loading details for transaction {transaction_id}")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get transaction details with appointment info
                logger.debug("Fetching transaction details from database")
                cursor.execute("""
                    SELECT
                        bt.transaction_id,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        s.email_address,
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number,
                        bt.created_at,
                        bt.processed_by,
                        bt.appointment_id,
                        ba.appointment_date,
                        ba.appointment_time,
                        ba.status as appointment_status
                    FROM barber_transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    LEFT JOIN barber_appointments ba ON bt.appointment_id = ba.appointment_id
                    WHERE bt.transaction_id = ?
                """, (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    logger.error(f"Transaction {transaction_id} not found in database")
                    messagebox.showerror("Not Found", f"Transaction #{transaction_id} could not be found.")
                    return

                logger.debug("Transaction data retrieved successfully")

                (trans_id, customer_id, customer_name, customer_email, amount, tip_amount,
                 payment_method, status, reference, created_at, processed_by,
                 appointment_id, appt_date, appt_time, appt_status) = trans

                # Get service details for this appointment
                services_text = ""
                if appointment_id:
                    cursor.execute("""
                        SELECT
                            ba.service_name,
                            bs.service_type,
                            ba.duration_minutes,
                            ba.price
                        FROM barber_appointments ba
                        LEFT JOIN barber_services bs ON ba.service_id = bs.service_id
                        WHERE ba.appointment_id = ?
                    """, (appointment_id,))

                    service_row = cursor.fetchone()
                    if service_row:
                        service_name, service_type, duration, price = service_row
                        services_text = "\nService:\n"
                        services_text += f"\n{service_name}"
                        if service_type:
                            services_text += f" ({service_type})"
                        services_text += f"\n  Duration: {duration} mins | Price: £{price:.2f}\n"

                # Calculate totals
                service_total = amount or 0
                tip_total = tip_amount or 0
                grand_total = service_total + tip_total

                # Create details window
                details_window = tk.Toplevel(self.parent)
                details_window.title(_t("Transaction Details", "Transaction Details"))
                details_window.geometry("600x700")
                details_window.transient(self.parent)

                # Create scrollable text widget
                text_frame = ttk.Frame(details_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=40)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Build details text
                details = f"""
BARBER SHOP TRANSACTION DETAILS
{'=' * 50}

Transaction Information:
  Transaction ID: {trans_id}
  Status: {status}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Customer Information:
  Customer ID: {customer_id}
  Name: {customer_name or 'N/A'}
  Email: {customer_email or 'N/A'}

Appointment Information:
  Appointment ID: {appointment_id or 'N/A'}
  Date: {appt_date or 'N/A'}
  Time: {appt_time or 'N/A'}
  Status: {appt_status or 'N/A'}
{services_text}

Financial Details:
  Service Amount: £{service_total:.2f}
  Tip Amount: £{tip_total:.2f}
  {'─' * 30}
  Total Amount: £{grand_total:.2f}

  Payment Method: {payment_method or 'N/A'}

{'=' * 50}
"""

                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                # Close button
                ttk.Button(details_window, text=_t("Close", "Close"),
                          command=details_window.destroy).pack(pady=10)

                logger.info(f"Transaction details displayed successfully for {transaction_id}")

        except Exception as e:
            error_msg = f"Failed to load transaction details: {str(e)}"
            logger.error(f"Error viewing transaction details for {transaction_id if 'transaction_id' in locals() else 'unknown'}: {e}", exc_info=True)
            messagebox.showerror("View Details Error", error_msg)

    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        logger.info("Starting CSV export of refunds")

        try:
            # Ask for file location
            default_filename = f'barber_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=default_filename
            )

            if not file_path:
                logger.info("CSV export cancelled by user")
                return

            logger.info(f"Exporting refunds to: {file_path}")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                logger.debug("Fetching transactions from database")
                cursor.execute("""
                    SELECT
                        bt.transaction_id,
                        bt.created_at,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number
                    FROM barber_transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    WHERE bt.transaction_type = 'service'
                    ORDER BY bt.created_at DESC
                """)

                transactions = cursor.fetchall()
                logger.info(f"Found {len(transactions)} transactions to export")

            # Write to CSV
            logger.debug("Writing data to CSV file")
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Date', 'Customer ID', 'Customer Name',
                               'Service Amount', 'Tip Amount', 'Total Amount', 'Payment Method',
                               'Status', 'Reference'])

                # Write data
                rows_written = 0
                for trans in transactions:
                    try:
                        transaction_id, date, customer_id, customer_name, amount, tip_amount, payment_method, status, reference = trans
                        total = (amount or 0) + (tip_amount or 0)
                        writer.writerow([
                            transaction_id,
                            date or '',
                            customer_id,
                            customer_name or '',
                            f'{amount:.2f}' if amount else '0.00',
                            f'{tip_amount:.2f}' if tip_amount else '0.00',
                            f'{total:.2f}',
                            payment_method or '',
                            status or 'completed',
                            reference or ''
                        ])
                        rows_written += 1
                    except Exception as row_err:
                        logger.warning(f"Error writing transaction {transaction_id if 'transaction_id' in locals() else 'unknown'}: {row_err}")
                        continue

            logger.info(f"Successfully exported {rows_written} transactions to {file_path}")
            messagebox.showinfo("Export Successful", f"Refunds exported successfully!\n\nFile: {file_path}\nRecords: {rows_written}")

        except Exception as e:
            error_msg = f"Failed to export refunds: {str(e)}"
            logger.error(f"Error exporting refunds to CSV: {e}", exc_info=True)
            messagebox.showerror("Export Error", error_msg)


def launch_barber_gui(parent=None, auth=None):
    """Launch the Barber Shop GUI"""
    return BarberGUI(parent, auth)
