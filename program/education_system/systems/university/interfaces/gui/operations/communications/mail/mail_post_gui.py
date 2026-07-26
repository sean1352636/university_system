"""
Mail/Post System GUI

Comprehensive GUI for university mail room providing package receiving,
tracking, PO box rentals, and forwarding services with email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.domain.operations.communications.mail.services.mail_post_core import (
    PackageManager, POBoxManager, ForwardingManager, TransactionManager, ReportManager,
    init_mail_db, PACKAGE_TYPES, PACKAGE_STATUSES, STORAGE_FEES, FORWARDING_FEES, PO_BOX_MONTHLY_FEE
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import internationalization (i18n)
try:
    from education_system.systems.university.infrastructure.i18n import (
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
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        print("Email service not available")
        return False

# Import finance integration
try:
    from education_system.systems.university.domain.finance.core.finance_db_operations import (
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


class MailPostGUI:
    """Main Mail/Post System GUI with comprehensive package management"""

    def __init__(self, root, auth):
        """Initialize the Mail/Post System GUI"""
        self.root = root
        self.auth = auth

        # Authentication check
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("mail.errors.login_required", default="You must be logged in to access Mail Services")
            )
            return

        self.current_user = auth.current_user
        self.user_role = self.current_user.get('role', 'student')
        self.user_id = self.current_user.get('id', self.current_user.get('username'))

        # Use passed window (root is already a Toplevel from the launcher)
        self.window = root
        self.window.title(_t("mail.window_title", default="University Mail Services"))
        self.window.geometry("1200x800")
        self.window.minsize(1000, 650)

        # Initialize data
        self.packages_data = []
        self.selected_package = None
        self.admin_email = "admin@university.edu"

        # Initialize database
        self._init_database()

        # Create UI
        self.create_widgets()

        # Log access
        log_activity('Accessed Mail/Post GUI', user=self.current_user.get('username'))
        print("Mail/Post GUI opened successfully")

    def _init_database(self):
        """Initialize database tables for mail services"""
        try:
            result = init_mail_db()
            if not result:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("mail.warnings.db_init", default="Database initialization had issues")
                )
        except Exception as e:
            print(f"Warning: Database initialization error: {e}")

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
            text=_t("mail.title", default="University Mail Services"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

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
            text=_t("common.refresh", default="Refresh"),
            command=self.refresh_all_data
        ).pack(side=tk.RIGHT, pady=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create all tabs
        self.create_packages_tab()
        self.create_my_mail_tab()
        self.create_po_box_tab()
        self.create_forwarding_tab()

        # Admin tab for staff
        if self.user_role in ['admin', 'staff']:
            self.create_admin_tab()

    def return_to_homescreen(self):
        """Close the window and return to homescreen"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        try:
            self.load_packages()
            self.load_my_packages()
            self.load_po_box_info()
            messagebox.showinfo(
                _t("common.success", default="Success"),
                _t("mail.messages.data_refreshed", default="All data refreshed successfully")
            )
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def create_packages_tab(self):
        """Create package management tab (staff/admin)"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("mail.tabs.packages", default="Packages"))

        # Split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Packages list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("mail.pending_packages", default="Pending Packages"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Search
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text=_t("mail.labels.search", default="Search") + ":").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t("common.search", default="Search"), command=self.search_packages).pack(side=tk.LEFT)
        ttk.Button(search_frame, text=_t("common.refresh", default="Refresh"), command=self.load_packages).pack(side=tk.RIGHT)

        # Packages treeview
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('id', 'tracking', 'recipient', 'type', 'status', 'received')
        self.packages_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.packages_tree.heading('id', text='ID')
        self.packages_tree.heading('tracking', text=_t("mail.labels.tracking", default="Tracking"))
        self.packages_tree.heading('recipient', text=_t("mail.labels.recipient", default="Recipient"))
        self.packages_tree.heading('type', text=_t("mail.labels.type", default="Type"))
        self.packages_tree.heading('status', text=_t("mail.labels.status", default="Status"))
        self.packages_tree.heading('received', text=_t("mail.labels.received", default="Received"))

        self.packages_tree.column('id', width=40)
        self.packages_tree.column('tracking', width=150)
        self.packages_tree.column('recipient', width=120)
        self.packages_tree.column('type', width=80)
        self.packages_tree.column('status', width=80)
        self.packages_tree.column('received', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.packages_tree.yview)
        self.packages_tree.configure(yscrollcommand=scrollbar.set)

        self.packages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.packages_tree.bind('<<TreeviewSelect>>', self.on_package_select)

        # Right: Package details/actions
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # Receive new package
        if self.user_role in ['admin', 'staff']:
            receive_frame = ttk.LabelFrame(right_frame, text=_t("mail.receive_package", default="Receive New Package"), padding="10")
            receive_frame.pack(fill=tk.X, padx=5, pady=5)

            fields = [
                ("recipient_id", _t("mail.labels.recipient_id", default="Recipient ID")),
                ("recipient_name", _t("mail.labels.recipient_name", default="Recipient Name")),
                ("recipient_email", _t("mail.labels.email", default="Email")),
                ("sender_name", _t("mail.labels.sender", default="Sender")),
                ("storage_location", _t("mail.labels.location", default="Storage Location"))
            ]

            self.receive_entries = {}
            for i, (field, label) in enumerate(fields):
                ttk.Label(receive_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
                entry = ttk.Entry(receive_frame, width=25)
                entry.grid(row=i, column=1, pady=2, padx=5)
                self.receive_entries[field] = entry

            row = len(fields)
            ttk.Label(receive_frame, text=_t("mail.labels.package_type", default="Package Type") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
            self.package_type_combo = ttk.Combobox(receive_frame, values=PACKAGE_TYPES, state='readonly', width=22)
            self.package_type_combo.set('small_parcel')
            self.package_type_combo.grid(row=row, column=1, pady=2, padx=5)

            row += 1
            btn_frame = ttk.Frame(receive_frame)
            btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

            ttk.Button(btn_frame, text=_t("mail.btn.receive", default="Receive Package"), command=self.receive_package).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("common.clear", default="Clear"), command=self.clear_receive_form).pack(side=tk.LEFT, padx=5)

        # Selected package actions
        actions_frame = ttk.LabelFrame(right_frame, text=_t("mail.package_actions", default="Package Actions"), padding="10")
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.selected_pkg_var = tk.StringVar(value=_t("mail.select_package", default="Select a package"))
        ttk.Label(actions_frame, textvariable=self.selected_pkg_var, font=('Arial', 10, 'bold'), wraplength=300).pack(pady=5)

        action_btns = ttk.Frame(actions_frame)
        action_btns.pack(fill=tk.X, pady=10)

        if self.user_role in ['admin', 'staff']:
            ttk.Button(action_btns, text=_t("mail.btn.mark_collected", default="Mark Collected"), command=self.mark_collected).pack(fill=tk.X, pady=2)
            ttk.Button(action_btns, text=_t("mail.btn.update_status", default="Update Status"), command=self.update_package_status).pack(fill=tk.X, pady=2)
            ttk.Button(action_btns, text=_t("mail.btn.send_notification", default="Send Notification"), command=self.send_notification).pack(fill=tk.X, pady=2)
            ttk.Button(action_btns, text=_t("mail.btn.calculate_fees", default="Calculate Fees"), command=self.calculate_fees).pack(fill=tk.X, pady=2)

        ttk.Button(action_btns, text=_t("mail.btn.view_details", default="View Details"), command=self.view_package_details).pack(fill=tk.X, pady=2)

        # Load packages
        self.load_packages()

    def create_my_mail_tab(self):
        """Create my mail tab for students"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("mail.tabs.my_mail", default="My Mail"))

        # Header
        ttk.Label(
            tab,
            text=_t("mail.my_packages", default="My Packages"),
            font=('Arial', 14, 'bold')
        ).pack(pady=10)

        # My packages treeview
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('tracking', 'type', 'sender', 'status', 'received', 'fees')
        self.my_packages_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.my_packages_tree.heading('tracking', text=_t("mail.labels.tracking", default="Tracking"))
        self.my_packages_tree.heading('type', text=_t("mail.labels.type", default="Type"))
        self.my_packages_tree.heading('sender', text=_t("mail.labels.sender", default="Sender"))
        self.my_packages_tree.heading('status', text=_t("mail.labels.status", default="Status"))
        self.my_packages_tree.heading('received', text=_t("mail.labels.received", default="Received"))
        self.my_packages_tree.heading('fees', text=_t("mail.labels.fees", default="Fees"))

        self.my_packages_tree.column('tracking', width=150)
        self.my_packages_tree.column('type', width=100)
        self.my_packages_tree.column('sender', width=120)
        self.my_packages_tree.column('status', width=80)
        self.my_packages_tree.column('received', width=100)
        self.my_packages_tree.column('fees', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.my_packages_tree.yview)
        self.my_packages_tree.configure(yscrollcommand=scrollbar.set)

        self.my_packages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("common.refresh", default="Refresh"), command=self.load_my_packages).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("mail.btn.track_package", default="Track Package"), command=self.track_package).pack(side=tk.LEFT, padx=5)

        # Load my packages
        self.load_my_packages()

    def create_po_box_tab(self):
        """Create PO Box management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("mail.tabs.po_box", default="PO Box"))

        # Current PO Box status
        status_frame = ttk.LabelFrame(tab, text=_t("mail.po_box_status", default="Your PO Box"), padding="15")
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.po_box_status_var = tk.StringVar(value=_t("mail.checking", default="Checking..."))
        ttk.Label(status_frame, textvariable=self.po_box_status_var, font=('Arial', 11)).pack(pady=5)

        po_btn_frame = ttk.Frame(status_frame)
        po_btn_frame.pack(pady=10)

        ttk.Button(po_btn_frame, text=_t("mail.btn.rent_box", default="Rent PO Box"), command=self.rent_po_box).pack(side=tk.LEFT, padx=5)
        ttk.Button(po_btn_frame, text=_t("mail.btn.release_box", default="Release Box"), command=self.release_po_box).pack(side=tk.LEFT, padx=5)
        ttk.Button(po_btn_frame, text=_t("common.refresh", default="Refresh"), command=self.load_po_box_info).pack(side=tk.LEFT, padx=5)

        # Available PO Boxes (for staff)
        if self.user_role in ['admin', 'staff']:
            avail_frame = ttk.LabelFrame(tab, text=_t("mail.available_boxes", default="Available PO Boxes"), padding="10")
            avail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            columns = ('box_id', 'number', 'size', 'fee', 'status')
            self.boxes_tree = ttk.Treeview(avail_frame, columns=columns, show='headings', height=10)

            self.boxes_tree.heading('box_id', text='ID')
            self.boxes_tree.heading('number', text=_t("mail.labels.box_number", default="Box Number"))
            self.boxes_tree.heading('size', text=_t("mail.labels.size", default="Size"))
            self.boxes_tree.heading('fee', text=_t("mail.labels.monthly_fee", default="Monthly Fee"))
            self.boxes_tree.heading('status', text=_t("mail.labels.status", default="Status"))

            self.boxes_tree.column('box_id', width=40)
            self.boxes_tree.column('number', width=100)
            self.boxes_tree.column('size', width=80)
            self.boxes_tree.column('fee', width=100)
            self.boxes_tree.column('status', width=80)

            self.boxes_tree.pack(fill=tk.BOTH, expand=True)
            self.load_available_boxes()

        # Load PO box info
        self.load_po_box_info()

    def create_forwarding_tab(self):
        """Create mail forwarding tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("mail.tabs.forwarding", default="Forwarding"))

        # Current forwarding status
        status_frame = ttk.LabelFrame(tab, text=_t("mail.forwarding_status", default="Mail Forwarding Status"), padding="15")
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.forwarding_status_var = tk.StringVar(value=_t("mail.no_forwarding", default="No active forwarding"))
        ttk.Label(status_frame, textvariable=self.forwarding_status_var, font=('Arial', 11)).pack(pady=5)

        # Setup forwarding
        setup_frame = ttk.LabelFrame(tab, text=_t("mail.setup_forwarding", default="Setup Mail Forwarding"), padding="15")
        setup_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(setup_frame, text=_t("mail.labels.forward_address", default="Forward Address") + ":").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.forward_address_entry = ttk.Entry(setup_frame, width=40)
        self.forward_address_entry.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(setup_frame, text=_t("mail.labels.forward_type", default="Type") + ":").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.forward_type_combo = ttk.Combobox(setup_frame, values=['domestic', 'international'], state='readonly', width=37)
        self.forward_type_combo.set('domestic')
        self.forward_type_combo.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(setup_frame, text=_t("mail.labels.start_date", default="Start Date") + ":").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.forward_start_entry = ttk.Entry(setup_frame, width=40)
        self.forward_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.forward_start_entry.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(setup_frame, text=_t("mail.labels.end_date", default="End Date (optional)") + ":").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.forward_end_entry = ttk.Entry(setup_frame, width=40)
        self.forward_end_entry.grid(row=3, column=1, pady=5, padx=5)

        # Fee display
        fee_frame = ttk.Frame(setup_frame)
        fee_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Label(fee_frame, text=f"Domestic: GBP {FORWARDING_FEES['domestic']:.2f} | International: GBP {FORWARDING_FEES['international']:.2f}").pack()

        btn_frame = ttk.Frame(setup_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("mail.btn.setup_forwarding", default="Setup Forwarding"), command=self.setup_forwarding).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("mail.btn.cancel_forwarding", default="Cancel Forwarding"), command=self.cancel_forwarding).pack(side=tk.LEFT, padx=5)

        self.load_forwarding_info()

    def create_admin_tab(self):
        """Create admin tab for staff/admin users"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("mail.tabs.admin", default="Admin"))

        # Reports section
        report_frame = ttk.LabelFrame(tab, text=_t("mail.reports", default="Reports"), padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Date selector
        date_frame = ttk.Frame(report_frame)
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text=_t("mail.labels.report_date", default="Date") + ":").pack(side=tk.LEFT, padx=5)
        self.report_date_entry = ttk.Entry(date_frame, width=12)
        self.report_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.report_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(date_frame, text=_t("mail.btn.daily_report", default="Daily Report"), command=self.generate_daily_report).pack(side=tk.LEFT, padx=10)
        ttk.Button(date_frame, text=_t("mail.btn.email_report", default="Email Report"), command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Additional report / payment actions
        actions_frame = ttk.Frame(report_frame)
        actions_frame.pack(fill=tk.X, pady=5)

        ttk.Button(actions_frame, text=_t("mail.btn.monthly_summary", default="Monthly Summary"), command=self.generate_monthly_summary).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text=_t("mail.btn.pending_notifications", default="Pending Notifications"), command=self.show_pending_notifications).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text=_t("mail.btn.record_payment", default="Record Payment"), command=self.record_payment_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text=_t("mail.btn.user_transactions", default="User Transactions"), command=self.view_user_transactions).pack(side=tk.LEFT, padx=5)

        # Report display
        self.admin_report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD, font=('Courier', 10))
        self.admin_report_text.pack(fill=tk.BOTH, expand=True, pady=10)

    # =========================================================================
    # Package Management Functions
    # =========================================================================

    def load_packages(self):
        """Load pending packages"""
        try:
            for item in self.packages_tree.get_children():
                self.packages_tree.delete(item)

            packages = PackageManager.get_pending_packages()
            self.packages_data = packages

            for pkg in packages:
                self.packages_tree.insert('', tk.END, values=(
                    pkg['package_id'],
                    pkg['tracking_number'],
                    pkg['recipient_name'],
                    pkg['package_type'],
                    pkg['status'],
                    pkg['received_date'][:10] if pkg['received_date'] else ''
                ))
        except Exception as e:
            print(f"Error loading packages: {e}")

    def search_packages(self):
        """Search packages"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            self.load_packages()
            return

        try:
            for item in self.packages_tree.get_children():
                self.packages_tree.delete(item)

            packages = PackageManager.search_packages(search_term)
            self.packages_data = packages

            for pkg in packages:
                self.packages_tree.insert('', tk.END, values=(
                    pkg['package_id'],
                    pkg['tracking_number'],
                    pkg['recipient_name'],
                    pkg['package_type'],
                    pkg['status'],
                    pkg['received_date'][:10] if pkg['received_date'] else ''
                ))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def on_package_select(self, event):
        """Handle package selection"""
        selected = self.packages_tree.selection()
        if selected:
            item = self.packages_tree.item(selected[0])
            package_id = item['values'][0]
            self.selected_package = next((p for p in self.packages_data if p['package_id'] == package_id), None)

            if self.selected_package:
                self.selected_pkg_var.set(
                    f"Tracking: {self.selected_package['tracking_number']}\n"
                    f"Recipient: {self.selected_package['recipient_name']}\n"
                    f"Status: {self.selected_package['status'].upper()}"
                )

    def receive_package(self):
        """Receive a new package"""
        try:
            recipient_id = self.receive_entries['recipient_id'].get().strip()
            recipient_name = self.receive_entries['recipient_name'].get().strip()
            recipient_email = self.receive_entries['recipient_email'].get().strip()
            package_type = self.package_type_combo.get()

            if not all([recipient_id, recipient_name, package_type]):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("mail.errors.fill_required", default="Please fill all required fields")
                )
                return

            result = PackageManager.receive_package(
                recipient_id=recipient_id,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                package_type=package_type,
                sender_name=self.receive_entries['sender_name'].get().strip(),
                storage_location=self.receive_entries['storage_location'].get().strip(),
                created_by=self.current_user.get('username')
            )

            if result:
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("mail.messages.package_received", default="Package received!\nTracking: {tracking}").format(
                        tracking=result['tracking_number']
                    )
                )
                self.clear_receive_form()
                self.load_packages()

                # Send notification email
                if recipient_email:
                    self.send_arrival_notification(result['tracking_number'], recipient_email, recipient_name)
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.receive_failed", default="Failed to receive package"))

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def clear_receive_form(self):
        """Clear the receive form"""
        for entry in self.receive_entries.values():
            entry.delete(0, tk.END)
        self.package_type_combo.set('small_parcel')

    def mark_collected(self):
        """Mark package as collected"""
        if not self.selected_package:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_package", default="Please select a package"))
            return

        collected_by = simpledialog.askstring(
            _t("mail.collected_by", default="Collected By"),
            _t("mail.prompts.collected_by", default="Enter name of person collecting:"),
            initialvalue=self.selected_package['recipient_name']
        )

        if collected_by:
            if PackageManager.mark_collected(self.selected_package['package_id'], collected_by):
                messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.marked_collected", default="Package marked as collected"))
                self.load_packages()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.update_failed", default="Failed to update package"))

    def send_notification(self):
        """Send collection notification"""
        if not self.selected_package:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_package", default="Please select a package"))
            return

        email = self.selected_package.get('recipient_email')
        if not email:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.no_email", default="No email address for recipient"))
            return

        self.send_arrival_notification(
            self.selected_package['tracking_number'],
            email,
            self.selected_package['recipient_name']
        )
        messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.notification_sent", default="Notification sent"))

    def send_arrival_notification(self, tracking: str, email: str, name: str):
        """Send package arrival notification email"""
        if not EMAIL_AVAILABLE or not email or '@' not in email:
            logger.info(f"Arrival notification skipped - invalid email: {email}")
            return

        body = f"""
Dear {name},

You have a package waiting for collection at the University Mail Room.

Tracking Number: {tracking}
Location: University Mail Room, Main Campus

Please bring your student ID when collecting your package.
Packages not collected within 7 days may incur storage fees.

Thank you,
University Mail Services
"""
        send_email(email, f"Package Arrived - {tracking}", body)
        logger.info(f"Arrival notification sent to {email}")

    def send_rental_receipt(self, box_number: str, fee: float, months: int, payment_method: str, email: str, name: str):
        """Send PO Box rental receipt email"""
        if not EMAIL_AVAILABLE or not email or '@' not in email:
            logger.info(f"Rental receipt skipped - invalid email: {email}")
            return

        body = f"""
Dear {name},

Thank you for renting a PO Box at University Mail Services.

{'='*50}
                    PO BOX RENTAL RECEIPT
{'='*50}

Box Number:       {box_number}
Rental Period:    {months} month(s)
Payment Method:   {payment_method}
Total Fee:        £{fee:.2f}

Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*50}

Your PO Box is now active. Please use Box {box_number} when receiving mail.

Thank you,
University Mail Services
"""
        send_email(email, f"PO Box Rental Confirmation - {box_number}", body)
        logger.info(f"Rental receipt sent to {email}")

    def send_forwarding_receipt(self, forward_address: str, forward_type: str, fee: float, payment_method: str, email: str, name: str):
        """Send mail forwarding receipt email"""
        if not EMAIL_AVAILABLE or not email or '@' not in email:
            logger.info(f"Forwarding receipt skipped - invalid email: {email}")
            return

        body = f"""
Dear {name},

Thank you for setting up mail forwarding at University Mail Services.

{'='*50}
                    MAIL FORWARDING RECEIPT
{'='*50}

Forward To:       {forward_address}
Type:             {forward_type.title()}
Payment Method:   {payment_method}
Setup Fee:        £{fee:.2f}

Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*50}

Your mail forwarding is now active.

Thank you,
University Mail Services
"""
        send_email(email, "Mail Forwarding Confirmation", body)
        logger.info(f"Forwarding receipt sent to {email}")

    def calculate_fees(self):
        """Calculate storage fees for selected package"""
        if not self.selected_package:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_package", default="Please select a package"))
            return

        fees = PackageManager.calculate_storage_fees(self.selected_package['package_id'])
        messagebox.showinfo(
            _t("mail.storage_fees", default="Storage Fees"),
            f"Storage fees for {self.selected_package['tracking_number']}:\nGBP {fees:.2f}"
        )

    def view_package_details(self):
        """View detailed package information"""
        if not self.selected_package:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_package", default="Please select a package"))
            return

        pkg = self.selected_package
        details = f"""
PACKAGE DETAILS
{'='*40}

Tracking Number: {pkg['tracking_number']}
Status: {pkg['status'].upper()}

RECIPIENT
Recipient ID: {pkg['recipient_id']}
Name: {pkg['recipient_name']}
Email: {pkg.get('recipient_email', 'N/A')}

PACKAGE INFO
Type: {pkg['package_type']}
Sender: {pkg.get('sender_name', 'Unknown')}
Weight: {pkg.get('weight_kg', 'N/A')} kg
Location: {pkg.get('storage_location', 'N/A')}

DATES
Received: {pkg['received_date']}
Collected: {pkg.get('collected_date', 'Not collected')}

FEES
Storage Fee: GBP {pkg.get('storage_fee', 0):.2f}
Total Charges: GBP {pkg.get('total_charges', 0):.2f}
Payment Status: {pkg.get('payment_status', 'N/A').upper()}
"""

        dialog = tk.Toplevel(self.window)
        dialog.title(f"Package {pkg['tracking_number']}")
        dialog.geometry("450x500")
        dialog.transient(self.window)

        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', details)
        text.config(state='disabled')

        ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

    # =========================================================================
    # My Mail Functions
    # =========================================================================

    def load_my_packages(self):
        """Load current user's packages"""
        try:
            for item in self.my_packages_tree.get_children():
                self.my_packages_tree.delete(item)

            packages = PackageManager.get_packages_for_recipient(self.user_id)

            for pkg in packages:
                fees = PackageManager.calculate_storage_fees(pkg['package_id'])
                self.my_packages_tree.insert('', tk.END, values=(
                    pkg['tracking_number'],
                    pkg['package_type'],
                    pkg.get('sender_name', 'Unknown'),
                    pkg['status'],
                    pkg['received_date'][:10] if pkg['received_date'] else '',
                    f"GBP {fees:.2f}"
                ))
        except Exception as e:
            print(f"Error loading my packages: {e}")

    def track_package(self):
        """Track a package by tracking number"""
        tracking = simpledialog.askstring(
            _t("mail.track_package", default="Track Package"),
            _t("mail.prompts.tracking_number", default="Enter tracking number:")
        )

        if tracking:
            pkg = PackageManager.get_package(tracking_number=tracking)
            if pkg:
                self.selected_package = pkg
                self.view_package_details()
            else:
                messagebox.showinfo(_t("common.info", default="Info"), _t("mail.messages.package_not_found", default="Package not found"))

    # =========================================================================
    # PO Box Functions
    # =========================================================================

    def load_po_box_info(self):
        """Load user's PO box information"""
        try:
            box = POBoxManager.get_user_box(self.user_id)
            if box:
                self.po_box_status_var.set(
                    f"Box Number: {box['box_number']}\n"
                    f"Size: {box['size'].title()}\n"
                    f"Monthly Fee: GBP {box['monthly_fee']:.2f}\n"
                    f"Rental Period: {box['rental_start']} to {box['rental_end']}"
                )
                self.user_po_box = box
            else:
                self.po_box_status_var.set(_t("mail.no_po_box", default="You don't have a PO box.\nRent one to receive mail at a dedicated address."))
                self.user_po_box = None
        except Exception as e:
            print(f"Error loading PO box info: {e}")

    def load_available_boxes(self):
        """Load available PO boxes (admin)"""
        if not hasattr(self, 'boxes_tree'):
            return

        try:
            for item in self.boxes_tree.get_children():
                self.boxes_tree.delete(item)

            boxes = POBoxManager.get_available_boxes()
            for box in boxes:
                self.boxes_tree.insert('', tk.END, values=(
                    box['box_id'],
                    box['box_number'],
                    box['size'],
                    f"GBP {box['monthly_fee']:.2f}",
                    box['status']
                ))
        except Exception as e:
            print(f"Error loading available boxes: {e}")

    def rent_po_box(self):
        """Rent a PO box"""
        boxes = POBoxManager.get_available_boxes()
        if not boxes:
            messagebox.showinfo(_t("common.info", default="Info"), _t("mail.messages.no_boxes_available", default="No PO boxes available"))
            return

        # Get user details and student account balance - try student_id, then username, then user_id
        user_name, user_email = self._get_user_details_from_db()
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = get_student_finance_account_balance(student_id)

        # Simple selection
        box_options = [f"{b['box_number']} ({b['size']}) - GBP {b['monthly_fee']:.2f}/month" for b in boxes]
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("mail.rent_po_box", default="Rent PO Box"))
        dialog.geometry("450x500")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("mail.rent_po_box", default="Rent PO Box"), font=('Arial', 14, 'bold')).pack(pady=5)
        ttk.Label(dialog, text=f"User: {user_name}", font=('Arial', 10)).pack(pady=2)

        ttk.Label(dialog, text=_t("mail.select_box", default="Select a PO Box:"), font=('Arial', 11, 'bold')).pack(pady=(10, 5))

        listbox = tk.Listbox(dialog, height=6, width=45)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        box_map = {}
        for i, (opt, box) in enumerate(zip(box_options, boxes)):
            listbox.insert(tk.END, opt)
            box_map[i] = box

        ttk.Label(dialog, text=_t("mail.labels.months", default="Rental Period (months)") + ":").pack(pady=(10, 0))
        months_entry = ttk.Entry(dialog, width=10)
        months_entry.insert(0, "1")
        months_entry.pack(pady=5)

        # Payment method
        ttk.Label(dialog, text=_t("mail.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))
        payment_method_var = tk.StringVar(value="Cash")
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(pady=5)

        ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
        ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

        student_frame = ttk.Frame(methods_frame)
        student_frame.pack(anchor=tk.W)
        ttk.Radiobutton(student_frame, text=_t("common.payment_methods.student_account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
        balance_text = f" (Balance: £{student_balance:.2f})" if student_balance else " (No account)"
        ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

        def confirm_rental():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_box", default="Please select a box"))
                return

            try:
                months = int(months_entry.get())
            except ValueError:
                months = 1

            box = box_map[selection[0]]
            rental_fee = box['monthly_fee'] * months
            payment_method = payment_method_var.get()

            # Handle Student Account payment
            if payment_method == "Student Account":
                if student_balance < rental_fee:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        f"Insufficient balance. Current balance: £{student_balance:.2f}, Fee: £{rental_fee:.2f}"
                    )
                    return
                payment_result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=rental_fee,
                    description=f"PO Box {box['box_number']} rental",
                    transaction_source="MailPost",
                    transaction_ref=f"pobox_{box['box_id']}",
                    processed_by=self.current_user.get('username', 'System')
                )
                if not payment_result.get('success'):
                    messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                    return

            result = POBoxManager.rent_box(
                box_id=box['box_id'],
                holder_id=self.user_id,
                holder_name=user_name,
                holder_email=user_email,
                months=months
            )

            if result:
                # Record revenue in central finance system
                record_payment_to_finance(
                    student_id=student_id,
                    amount=rental_fee,
                    payment_method=payment_method,
                    transaction_source='MailServices',
                    transaction_ref=f"POBOX-{result['box_number']}",
                    notes=f"PO Box {result['box_number']} rental - {months} month(s)",
                    created_by=self.current_user.get('username')
                )
                logger.info(f"Revenue recorded: £{rental_fee:.2f} for PO Box rental")

                # Send receipt email
                self.send_rental_receipt(result['box_number'], rental_fee, months, payment_method, user_email, user_name)

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("mail.messages.box_rented", default="PO Box {box} rented until {end_date}!\nFee: GBP {fee:.2f}").format(
                        box=result['box_number'],
                        fee=result['rental_fee'],
                        end_date=result['end_date']
                    )
                )
                dialog.destroy()
                self.load_po_box_info()
                if hasattr(self, 'boxes_tree'):
                    self.load_available_boxes()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.rental_failed", default="Failed to rent box"))

        ttk.Button(dialog, text=_t("mail.btn.rent", default="Rent"), command=confirm_rental).pack(pady=15)

    def release_po_box(self):
        """Release user's PO box"""
        if not hasattr(self, 'user_po_box') or not self.user_po_box:
            messagebox.showinfo(_t("common.info", default="Info"), _t("mail.messages.no_box_to_release", default="You don't have a PO box to release"))
            return

        if messagebox.askyesno(_t("common.confirm", default="Confirm"), _t("mail.confirm.release_box", default="Are you sure you want to release your PO box?")):
            if POBoxManager.release_box(self.user_po_box['box_id']):
                messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.box_released", default="PO box released"))
                self.load_po_box_info()
                if hasattr(self, 'boxes_tree'):
                    self.load_available_boxes()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.release_failed", default="Failed to release box"))

    # =========================================================================
    # Forwarding Functions
    # =========================================================================

    def load_forwarding_info(self):
        """Load user's forwarding information"""
        try:
            forwarding = ForwardingManager.get_user_forwarding(self.user_id)
            if forwarding:
                self.forwarding_status_var.set(
                    f"Status: ACTIVE\n"
                    f"Forward To: {forwarding['forward_address']}\n"
                    f"Type: {forwarding['forward_type'].title()}\n"
                    f"Started: {forwarding['start_date']}"
                )
                self.user_forwarding = forwarding
            else:
                self.forwarding_status_var.set(_t("mail.no_forwarding", default="No active mail forwarding"))
                self.user_forwarding = None
        except Exception as e:
            print(f"Error loading forwarding info: {e}")

    def setup_forwarding(self):
        """Setup mail forwarding"""
        address = self.forward_address_entry.get().strip()
        if not address:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.enter_address", default="Please enter a forwarding address"))
            return

        # Get user details and student account balance - try student_id, then username, then user_id
        user_name, user_email = self._get_user_details_from_db()
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = get_student_finance_account_balance(student_id)

        forward_type = self.forward_type_combo.get()
        forwarding_fee = FORWARDING_FEES.get(forward_type, 5.00)

        # Show payment dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("mail.setup_forwarding", default="Setup Mail Forwarding"))
        dialog.geometry("400x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("mail.setup_forwarding", default="Setup Mail Forwarding"), font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"User: {user_name}", font=('Arial', 10)).pack(pady=2)
        ttk.Label(dialog, text=f"Forward To: {address}", font=('Arial', 10)).pack(pady=2)
        ttk.Label(dialog, text=f"Type: {forward_type.title()}", font=('Arial', 10)).pack(pady=2)
        ttk.Label(dialog, text=f"Fee: £{forwarding_fee:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)

        # Payment method
        ttk.Label(dialog, text=_t("mail.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))
        payment_method_var = tk.StringVar(value="Cash")
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(pady=5)

        ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
        ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

        student_frame = ttk.Frame(methods_frame)
        student_frame.pack(anchor=tk.W)
        ttk.Radiobutton(student_frame, text=_t("common.payment_methods.student_account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
        balance_text = f" (Balance: £{student_balance:.2f})" if student_balance else " (No account)"
        ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

        def confirm_setup():
            payment_method = payment_method_var.get()

            # Handle Student Account payment
            if payment_method == "Student Account":
                if student_balance < forwarding_fee:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        f"Insufficient balance. Current balance: £{student_balance:.2f}"
                    )
                    return
                payment_result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=forwarding_fee,
                    description=f"Mail forwarding - {forward_type}",
                    transaction_source="MailPost",
                    transaction_ref=f"forwarding_{self.user_id}",
                    processed_by=self.current_user.get('username', 'System')
                )
                if not payment_result.get('success'):
                    messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                    return

            result = ForwardingManager.setup_forwarding(
                user_id=self.user_id,
                user_name=user_name,
                forward_address=address,
                forward_type=forward_type,
                start_date=self.forward_start_entry.get().strip() or None,
                end_date=self.forward_end_entry.get().strip() or None
            )

            if result:
                # Record revenue in central finance system
                record_payment_to_finance(
                    student_id=student_id,
                    amount=forwarding_fee,
                    payment_method=payment_method,
                    transaction_source='MailServices',
                    transaction_ref=f"FWD-{result.get('forwarding_id', 'NEW')}",
                    notes=f"Mail forwarding setup - {forward_type}",
                    created_by=self.current_user.get('username')
                )
                logger.info(f"Revenue recorded: £{forwarding_fee:.2f} for mail forwarding")

                # Send receipt email
                self.send_forwarding_receipt(address, forward_type, forwarding_fee, payment_method, user_email, user_name)

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("mail.messages.forwarding_setup", default="Mail forwarding set up!\nFee: GBP {fee:.2f}").format(fee=result['fee'])
                )
                dialog.destroy()
                self.load_forwarding_info()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.setup_failed", default="Failed to setup forwarding"))

        ttk.Button(dialog, text=_t("mail.btn.setup", default="Setup Forwarding"), command=confirm_setup).pack(pady=20)

    def cancel_forwarding(self):
        """Cancel mail forwarding"""
        if not hasattr(self, 'user_forwarding') or not self.user_forwarding:
            messagebox.showinfo(_t("common.info", default="Info"), _t("mail.messages.no_forwarding_to_cancel", default="No active forwarding to cancel"))
            return

        if messagebox.askyesno(_t("common.confirm", default="Confirm"), _t("mail.confirm.cancel_forwarding", default="Cancel mail forwarding?")):
            if ForwardingManager.cancel_forwarding(self.user_forwarding['forwarding_id']):
                messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.forwarding_cancelled", default="Mail forwarding cancelled"))
                self.load_forwarding_info()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.cancel_failed", default="Failed to cancel forwarding"))

    # =========================================================================
    # Admin Functions
    # =========================================================================

    def generate_daily_report(self):
        """Generate daily operations report"""
        try:
            date = self.report_date_entry.get().strip()
            report_data = ReportManager.get_daily_report(date)

            report = f"""
MAIL SERVICES DAILY REPORT
{'='*50}
Date: {report_data.get('date', date)}

PACKAGES
Received: {report_data.get('packages_received', 0)}
Collected: {report_data.get('packages_collected', 0)}

REVENUE
Storage Fees: GBP {report_data.get('storage_fees', 0):.2f}
Total Revenue: GBP {report_data.get('total_revenue', 0):.2f}

{'='*50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

            self.admin_report_text.delete('1.0', tk.END)
            self.admin_report_text.insert('1.0', report)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def email_admin_report(self):
        """Email the admin report"""
        report = self.admin_report_text.get('1.0', tk.END).strip()
        if not report:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.warnings.generate_report_first", default="Please generate a report first"))
            return

        admin_email = simpledialog.askstring(
            _t("mail.btn.email_report", default="Email Report"),
            _t("mail.prompts.admin_email", default="Enter admin email:"),
            initialvalue=self.admin_email
        )

        if admin_email and EMAIL_AVAILABLE:
            result = send_email(admin_email, f"Mail Services Report - {datetime.now().strftime('%Y-%m-%d')}", report)
            if result:
                messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.report_emailed", default="Report sent successfully"))
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.email_failed", default="Failed to send email"))

    def update_package_status(self):
        """Update the selected package to an arbitrary status."""
        if not self.selected_package:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("mail.errors.select_package", default="Please select a package"))
            return

        status = simpledialog.askstring(
            _t("mail.btn.update_status", default="Update Status"),
            f"New status ({', '.join(PACKAGE_STATUSES)}):",
            initialvalue=self.selected_package.get('status', ''),
        )
        if not status:
            return
        status = status.strip()

        notes = simpledialog.askstring(
            _t("mail.btn.update_status", default="Update Status"),
            _t("mail.prompts.status_notes", default="Notes (optional):"),
        )

        try:
            if PackageManager.update_package_status(self.selected_package['package_id'], status, notes or None):
                messagebox.showinfo(_t("common.success", default="Success"), _t("mail.messages.status_updated", default="Package status updated"))
                self.load_packages()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("mail.errors.update_failed", default="Failed to update package"))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def generate_monthly_summary(self):
        """Generate a monthly revenue summary report."""
        try:
            year = simpledialog.askinteger(_t("mail.btn.monthly_summary", default="Monthly Summary"), "Year (Cancel for current):")
            month = simpledialog.askinteger(_t("mail.btn.monthly_summary", default="Monthly Summary"), "Month 1-12 (Cancel for current):")

            report_data = ReportManager.get_monthly_summary(year, month)
            if not report_data:
                self.admin_report_text.delete('1.0', tk.END)
                self.admin_report_text.insert('1.0', "No data available.")
                return

            lines = [
                "MAIL SERVICES MONTHLY SUMMARY",
                "=" * 50,
                f"Period:          {report_data.get('year', '')}-{report_data.get('month', 0):02d}",
                f"Total Revenue:   GBP {report_data.get('total_revenue', 0):.2f}",
                f"Active PO Boxes: {report_data.get('active_po_boxes', 0)}",
                "",
            ]
            by_type = report_data.get('packages_by_type', {})
            if by_type:
                lines.append("Packages by Type:")
                for ptype, info in by_type.items():
                    lines.append(f"  {ptype}: {info['count']} packages, GBP {info['revenue']:.2f}")
            lines.append("")
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

            self.admin_report_text.delete('1.0', tk.END)
            self.admin_report_text.insert('1.0', "\n".join(lines))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def show_pending_notifications(self):
        """Show packages awaiting recipient notification."""
        try:
            packages = ReportManager.get_pending_notifications()
            lines = ["PACKAGES PENDING NOTIFICATION", "=" * 50]
            if not packages:
                lines.append("No pending notifications.")
            else:
                lines.append(f"{'ID':<6}{'Tracking #':<22}{'Recipient':<20}{'Email':<25}")
                lines.append("-" * 73)
                for p in packages:
                    lines.append(
                        f"{p['package_id']:<6}{p['tracking_number']:<22}"
                        f"{p['recipient_name']:<20}{p.get('recipient_email', 'N/A'):<25}"
                    )
            self.admin_report_text.delete('1.0', tk.END)
            self.admin_report_text.insert('1.0', "\n".join(lines))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def record_payment_dialog(self):
        """Open a dialog to record a mail service payment."""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("mail.btn.record_payment", default="Record Payment"))
        dialog.geometry("380x300")
        dialog.transient(self.window)
        dialog.grab_set()

        frm = ttk.Frame(dialog, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=4)
        user_entry = ttk.Entry(frm, width=24)
        user_entry.grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="Transaction Type:").grid(row=1, column=0, sticky=tk.W, pady=4)
        type_combo = ttk.Combobox(frm, values=["storage_fee", "po_box_rental", "forwarding", "collection"], state="readonly", width=22)
        type_combo.set("storage_fee")
        type_combo.grid(row=1, column=1, pady=4)

        ttk.Label(frm, text="Amount:").grid(row=2, column=0, sticky=tk.W, pady=4)
        amount_entry = ttk.Entry(frm, width=24)
        amount_entry.grid(row=2, column=1, pady=4)

        ttk.Label(frm, text="Payment Method:").grid(row=3, column=0, sticky=tk.W, pady=4)
        method_combo = ttk.Combobox(frm, values=["card", "cash", "transfer"], state="readonly", width=22)
        method_combo.set("card")
        method_combo.grid(row=3, column=1, pady=4)

        ttk.Label(frm, text="Package ID (optional):").grid(row=4, column=0, sticky=tk.W, pady=4)
        pkg_entry = ttk.Entry(frm, width=24)
        pkg_entry.grid(row=4, column=1, pady=4)

        def _submit():
            user_id = user_entry.get().strip()
            if not user_id:
                messagebox.showwarning(_t("common.warning", default="Warning"), "User ID is required", parent=dialog)
                return
            try:
                amount = float(amount_entry.get().strip())
            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Amount must be a number", parent=dialog)
                return
            pkg_raw = pkg_entry.get().strip()
            package_id = int(pkg_raw) if pkg_raw else None
            try:
                result = TransactionManager.record_payment(
                    user_id, type_combo.get(), amount, method_combo.get(), package_id,
                    processed_by=self.current_user.get('username'),
                )
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), str(e), parent=dialog)
                return
            if result:
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    f"Payment recorded!\nTransaction ID: {result['transaction_id']}\nReference: {result['reference']}",
                    parent=dialog,
                )
                dialog.destroy()
                self.load_packages()
            else:
                messagebox.showerror(_t("common.error", default="Error"), "Failed to record payment", parent=dialog)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text=_t("mail.btn.record_payment", default="Record Payment"), command=_submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_user_transactions(self):
        """Display a user's transaction history in the report panel."""
        user_id = simpledialog.askstring(
            _t("mail.btn.user_transactions", default="User Transactions"),
            _t("mail.prompts.user_id", default="Enter user ID:"),
        )
        if not user_id:
            return
        try:
            transactions = TransactionManager.get_user_transactions(user_id.strip())
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            return

        lines = [f"TRANSACTIONS FOR {user_id.strip()}", "=" * 50]
        if not transactions:
            lines.append("No transactions found.")
        else:
            for t in transactions:
                lines.append(
                    f"  [{t.get('transaction_id')}] {t.get('transaction_type', 'N/A')} | "
                    f"GBP {t.get('amount', 0):.2f} | {t.get('payment_method', 'N/A')} | "
                    f"Ref: {t.get('reference_number', 'N/A')}"
                )
        self.admin_report_text.delete('1.0', tk.END)
        self.admin_report_text.insert('1.0', "\n".join(lines))


def launch_mail_post_gui(root, auth):
    """Launch the Mail/Post System GUI"""
    try:
        MailPostGUI(root, auth)
    except Exception as e:
        messagebox.showerror(
            _t("common.error", default="Error"),
            _t("mail.errors.launch_failed", default="Failed to launch Mail Services: {error}").format(error=str(e))
        )
        print(f"Mail/Post GUI error: {traceback.format_exc()}")


__all__ = ['MailPostGUI', 'launch_mail_post_gui']
