"""Equipment Rental System GUI Module"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import logging
from datetime import datetime, timedelta

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection, transaction
from education_system.university_system.modules.domain.campus.equipment.services.equipment_core import (
    EquipmentManager, RentalManager, TransactionManager, ReportManager,
    init_equipment_db, EQUIPMENT_CATEGORIES, RENTAL_STATUSES, EQUIPMENT_CONDITIONS
)
from education_system.university_system.modules.shared.utils.finance_integration import (
    record_payment_to_finance,
    process_student_finance_account_payment,
    get_student_finance_account_balance,
    get_student_info
)

# Email template import
try:
    from education_system.university_system.infrastructure.email.template_utils import render_template
except ImportError:
    render_template = None

logger = logging.getLogger(__name__)


class EquipmentRentalGUI:
    """Equipment Rental System GUI - 25 functions"""

    def __init__(self, root, auth):
        """Initialize the Equipment Rental GUI"""
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if not self.current_user:
            messagebox.showerror(_t("equipment.window_title"), _t("equipment.errors.login_required"))
            root.destroy()
            return

        self.root.title(_t("equipment.window_title"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Initialize database
        self._init_database()

        # Create widgets
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

    def create_widgets(self):
        """Create the main GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("equipment.title"),
                  font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("common.refresh"),
                   command=self.refresh_all_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.back"),
                   command=self.return_to_homescreen).pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_inventory_tab()
        self.create_rentals_tab()
        self.create_returns_tab()
        self.create_reports_tab()

    def _init_database(self):
        """Initialize the equipment rental database"""
        try:
            init_equipment_db()
            logger.info("Equipment rental database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            messagebox.showerror(_t("common.error"), str(e))

    def _get_user_details_from_db(self):
        """Fetch user name and email from the users table"""
        try:
            user_id = self.current_user.get('id')
            username = self.current_user.get('username')

            with get_db_connection() as conn:
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

    def return_to_homescreen(self):
        """Return to the main homescreen"""
        self.root.destroy()

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self._load_inventory()
        self._load_available_items()
        self._load_active_rentals()

    def create_inventory_tab(self):
        """Create the inventory management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("equipment.tabs.inventory"))

        # Left panel - Inventory list
        left_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.inventory_list"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("equipment.labels.category") + ":").pack(side=tk.LEFT)
        self.inventory_category_filter = ttk.Combobox(filter_frame, values=['All'] + EQUIPMENT_CATEGORIES, width=15)
        self.inventory_category_filter.set('All')
        self.inventory_category_filter.pack(side=tk.LEFT, padx=5)
        self.inventory_category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_inventory())

        # Treeview
        columns = ('id', 'code', 'name', 'category', 'daily_rate', 'available', 'condition')
        self.inventory_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=18)

        self.inventory_tree.heading('id', text=_t('equipment.columns.id'))
        self.inventory_tree.heading('code', text=_t("equipment.labels.item_code"))
        self.inventory_tree.heading('name', text=_t("equipment.labels.name"))
        self.inventory_tree.heading('category', text=_t("equipment.labels.category"))
        self.inventory_tree.heading('daily_rate', text=_t("equipment.labels.daily_rate"))
        self.inventory_tree.heading('available', text=_t("equipment.labels.available"))
        self.inventory_tree.heading('condition', text=_t("equipment.labels.condition"))

        self.inventory_tree.column('id', width=40)
        self.inventory_tree.column('code', width=80)
        self.inventory_tree.column('name', width=150)
        self.inventory_tree.column('category', width=100)
        self.inventory_tree.column('daily_rate', width=80)
        self.inventory_tree.column('available', width=70)
        self.inventory_tree.column('condition', width=80)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.inventory_tree.yview)
        self.inventory_tree.configure(yscrollcommand=scrollbar.set)

        self.inventory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel - Add item form
        right_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.add_item"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Form fields
        fields = [
            ("item_code", _t("equipment.labels.item_code")),
            ("name", _t("equipment.labels.name")),
            ("brand", _t("equipment.labels.brand")),
            ("model", _t("equipment.labels.model")),
            ("daily_rate", _t("equipment.labels.daily_rate")),
            ("deposit", _t("equipment.labels.deposit")),
            ("quantity", _t("equipment.labels.quantity")),
            ("location", _t("equipment.labels.location"))
        ]

        self.item_entries = {}
        for i, (field, label) in enumerate(fields):
            ttk.Label(right_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(right_frame, width=20)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.item_entries[field] = entry

        # Category dropdown
        row = len(fields)
        ttk.Label(right_frame, text=_t("equipment.labels.category") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.item_category_combo = ttk.Combobox(right_frame, values=EQUIPMENT_CATEGORIES, width=17)
        self.item_category_combo.grid(row=row, column=1, pady=2, padx=5)

        # Condition dropdown
        row += 1
        ttk.Label(right_frame, text=_t("equipment.labels.condition") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.item_condition_combo = ttk.Combobox(right_frame, values=EQUIPMENT_CONDITIONS, width=17)
        self.item_condition_combo.set('good')
        self.item_condition_combo.grid(row=row, column=1, pady=2, padx=5)

        # Description
        row += 1
        ttk.Label(right_frame, text=_t("equipment.labels.description") + ":").grid(row=row, column=0, sticky=tk.NW, pady=2)
        self.item_description = tk.Text(right_frame, width=20, height=3)
        self.item_description.grid(row=row, column=1, pady=2, padx=5)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("equipment.btn.add_item"),
                   command=self.add_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("equipment.btn.update_item"),
                   command=self.update_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"),
                   command=self._clear_item_form).pack(side=tk.LEFT, padx=5)

        self.inventory_tree.bind('<Double-1>', self._on_item_select)

    def create_rentals_tab(self):
        """Create the rentals booking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("equipment.tabs.rentals"))

        # Left panel - Available items
        left_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.available_items"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        columns = ('id', 'item', 'category', 'daily_rate', 'available')
        self.available_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)

        self.available_tree.heading('id', text=_t('equipment.columns.id'))
        self.available_tree.heading('item', text=_t("equipment.labels.item"))
        self.available_tree.heading('category', text=_t("equipment.labels.category"))
        self.available_tree.heading('daily_rate', text=_t("equipment.labels.daily_rate"))
        self.available_tree.heading('available', text=_t("equipment.labels.available"))

        self.available_tree.column('id', width=40)
        self.available_tree.column('item', width=200)
        self.available_tree.column('category', width=100)
        self.available_tree.column('daily_rate', width=80)
        self.available_tree.column('available', width=70)

        self.available_tree.pack(fill=tk.BOTH, expand=True)
        self.available_tree.bind('<Double-1>', self._select_item_for_rental)

        # Right panel - Booking form
        right_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.book_rental"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Selected item
        ttk.Label(right_frame, text=_t("equipment.labels.selected_item") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.selected_item_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.selected_item_var, font=('Helvetica', 10, 'bold')).grid(row=0, column=1, pady=2)
        self.selected_item_id = None

        # Current user details (read-only display)
        user_info_frame = ttk.LabelFrame(right_frame, text=_t("equipment.labels.borrower_details"), padding="5")
        user_info_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=5)

        # Fetch user details from database
        user_name, user_email = self._get_user_details_from_db()
        display_email = user_email if user_email and '@' in user_email else 'Not set'

        ttk.Label(user_info_frame, text=f"Name: {user_name}", font=('Helvetica', 9)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(user_info_frame, text=f"Email: {display_email}", font=('Helvetica', 9)).grid(row=1, column=0, sticky=tk.W)

        # Store user details for booking
        self.rental_borrower_name = user_name
        self.rental_borrower_email = user_email if user_email and '@' in user_email else None

        # Rental details (editable)
        rental_fields = [
            ("department", _t("equipment.labels.department")),
            ("quantity", _t("equipment.labels.quantity")),
            ("checkout_date", _t("equipment.labels.checkout_date") + " (YYYY-MM-DD)"),
            ("checkout_time", _t("equipment.labels.checkout_time") + " (HH:MM)"),
            ("due_date", _t("equipment.labels.due_date") + " (YYYY-MM-DD)"),
            ("due_time", _t("equipment.labels.due_time") + " (HH:MM)")
        ]

        self.rental_entries = {}
        for i, (field, label) in enumerate(rental_fields, start=2):
            ttk.Label(right_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(right_frame, width=25)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.rental_entries[field] = entry

        # Set defaults
        self.rental_entries['quantity'].insert(0, '1')
        today = datetime.now()
        self.rental_entries['checkout_date'].insert(0, today.strftime('%Y-%m-%d'))
        self.rental_entries['checkout_time'].insert(0, '09:00')
        next_week = today + timedelta(days=7)
        self.rental_entries['due_date'].insert(0, next_week.strftime('%Y-%m-%d'))
        self.rental_entries['due_time'].insert(0, '17:00')

        # Purpose
        row = len(rental_fields) + 2  # +2 for user info frame
        ttk.Label(right_frame, text=_t("equipment.labels.purpose") + ":").grid(row=row, column=0, sticky=tk.NW, pady=2)
        self.rental_purpose = tk.Text(right_frame, width=25, height=2)
        self.rental_purpose.grid(row=row, column=1, pady=2, padx=5)

        # Cost display
        row += 1
        self.rental_cost_var = tk.StringVar(value="$0.00")
        ttk.Label(right_frame, text=_t("equipment.labels.estimated_cost") + ":").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Label(right_frame, textvariable=self.rental_cost_var, font=('Helvetica', 12, 'bold')).grid(row=row, column=1, pady=5)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("equipment.btn.calculate_cost"),
                   command=self._calculate_rental_cost).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("equipment.btn.book_rental"),
                   command=self.book_rental).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"),
                   command=self._clear_rental_form).pack(side=tk.LEFT, padx=5)

    def create_returns_tab(self):
        """Create the returns tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("equipment.tabs.returns"))

        # Active rentals list
        left_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.active_rentals"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        columns = ('id', 'rental_num', 'borrower', 'item', 'due_date', 'amount')
        self.active_rentals_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)

        self.active_rentals_tree.heading('id', text=_t('equipment.columns.id'))
        self.active_rentals_tree.heading('rental_num', text=_t("equipment.labels.rental_number"))
        self.active_rentals_tree.heading('borrower', text=_t("equipment.labels.borrower"))
        self.active_rentals_tree.heading('item', text=_t("equipment.labels.item"))
        self.active_rentals_tree.heading('due_date', text=_t("equipment.labels.due_date"))
        self.active_rentals_tree.heading('amount', text=_t("equipment.labels.amount"))

        self.active_rentals_tree.column('id', width=40)
        self.active_rentals_tree.column('rental_num', width=120)
        self.active_rentals_tree.column('borrower', width=150)
        self.active_rentals_tree.column('item', width=150)
        self.active_rentals_tree.column('due_date', width=100)
        self.active_rentals_tree.column('amount', width=80)

        self.active_rentals_tree.pack(fill=tk.BOTH, expand=True)

        # Return form
        right_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.process_return"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Return condition
        ttk.Label(right_frame, text=_t("equipment.labels.return_condition") + ":").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.return_condition_combo = ttk.Combobox(right_frame, values=EQUIPMENT_CONDITIONS, width=17)
        self.return_condition_combo.set('good')
        self.return_condition_combo.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("equipment.labels.late_fee") + " ($):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.late_fee_entry = ttk.Entry(right_frame, width=20)
        self.late_fee_entry.insert(0, "0")
        self.late_fee_entry.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("equipment.labels.damage_fee") + " ($):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.damage_fee_entry = ttk.Entry(right_frame, width=20)
        self.damage_fee_entry.insert(0, "0")
        self.damage_fee_entry.grid(row=2, column=1, pady=5, padx=5)

        # Buttons
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("equipment.btn.checkout_item"),
                   command=self.checkout_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("equipment.btn.return_pay"),
                   command=self.return_with_payment).pack(side=tk.LEFT, padx=5)

        btn_frame2 = ttk.Frame(right_frame)
        btn_frame2.grid(row=4, column=0, columnspan=2, pady=5)

        ttk.Button(btn_frame2, text=_t("equipment.btn.extend_rental"),
                   command=self.extend_rental).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame2, text=_t("equipment.btn.cancel_rental"),
                   command=self.cancel_rental).pack(side=tk.LEFT, padx=5)

    def create_reports_tab(self):
        """Create the reports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("equipment.tabs.reports"))

        # Left panel - Report options
        left_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.report_options"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Quick view buttons (show in main tab)
        ttk.Label(left_frame, text=_t("equipment.labels.quick_view"), font=('Arial', 10, 'bold')).pack(pady=(0, 5))
        ttk.Button(left_frame, text=_t("equipment.btn.inventory_summary"),
                   command=self.show_inventory_summary, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.revenue_report"),
                   command=self.show_revenue_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.popular_items"),
                   command=self.show_popular_items, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.overdue_rentals"),
                   command=self.show_overdue_rentals, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.generate_admin_report"),
                   command=self.generate_admin_report, width=25).pack(pady=5)

        # Separator
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # New window buttons (open in separate window with export/email options)
        ttk.Label(left_frame, text=_t("equipment.labels.open_in_new_window"), font=('Arial', 10, 'bold')).pack(pady=(0, 5))
        ttk.Button(left_frame, text=_t("equipment.btn.inventory_summary_icon"),
                   command=lambda: self.open_report_window("Inventory Summary",
                                                           self._generate_inventory_report()),
                   width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.revenue_report_icon"),
                   command=lambda: self.open_report_window("Revenue Report",
                                                           self._generate_revenue_report()),
                   width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.popular_items_icon"),
                   command=lambda: self.open_report_window("Popular Items Report",
                                                           self._generate_popular_items_report()),
                   width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.overdue_rentals_icon"),
                   command=lambda: self.open_report_window("Overdue Rentals Report",
                                                           self._generate_overdue_report()),
                   width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("equipment.btn.full_admin_report_icon"),
                   command=lambda: self.open_report_window("Equipment Rental Admin Report",
                                                           ReportManager.generate_admin_report()),
                   width=25).pack(pady=5)

        # Right panel - Report display
        right_frame = ttk.LabelFrame(tab, text=_t("equipment.labels.report_output"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(right_frame, wrap=tk.WORD, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_categories(self):
        """Get equipment categories"""
        return EQUIPMENT_CATEGORIES

    def _load_inventory(self):
        """Load inventory into the treeview"""
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)

        category = self.inventory_category_filter.get()
        items = EquipmentManager.get_all_items()

        for item in items:
            if category == 'All' or item['category'] == category:
                self.inventory_tree.insert('', tk.END, values=(
                    item['item_id'], item['item_code'], item['name'],
                    item['category'], f"${item['daily_rate']:.2f}",
                    f"{item['quantity_available']}/{item['quantity_total']}",
                    item['condition']
                ))

    def _load_available_items(self):
        """Load available items for rental tab"""
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)

        items = EquipmentManager.get_available_items()
        for item in items:
            self.available_tree.insert('', tk.END, values=(
                item['item_id'],
                f"{item['name']} ({item['item_code']})",
                item['category'],
                f"${item['daily_rate']:.2f}",
                item['quantity_available']
            ))

    def _load_active_rentals(self):
        """Load active rentals"""
        for item in self.active_rentals_tree.get_children():
            self.active_rentals_tree.delete(item)

        rentals = RentalManager.get_rentals_by_status('checked_out')
        rentals += RentalManager.get_rentals_by_status('reserved')

        for r in rentals:
            self.active_rentals_tree.insert('', tk.END, values=(
                r['rental_id'], r['rental_number'], r['borrower_name'],
                r['item_name'], r['due_date'], f"${r['total_amount']:.2f}"
            ))

    def add_item(self):
        """Add a new equipment item"""
        try:
            code = self.item_entries['item_code'].get().strip()
            name = self.item_entries['name'].get().strip()
            category = self.item_category_combo.get()
            daily_rate = self.item_entries['daily_rate'].get().strip()

            if not all([code, name, category, daily_rate]):
                messagebox.showerror(_t("common.error"), _t("equipment.errors.fill_required"))
                return

            item_id = EquipmentManager.add_item(
                item_code=code,
                name=name,
                category=category,
                daily_rate=float(daily_rate),
                brand=self.item_entries['brand'].get().strip() or None,
                model=self.item_entries['model'].get().strip() or None,
                deposit_required=float(self.item_entries['deposit'].get() or 0),
                quantity_total=int(self.item_entries['quantity'].get() or 1),
                location=self.item_entries['location'].get().strip() or None,
                condition=self.item_condition_combo.get(),
                description=self.item_description.get(1.0, tk.END).strip() or None
            )

            if item_id:
                messagebox.showinfo(_t("common.success"),
                    _t("equipment.messages.item_added").format(name=name))
                self._clear_item_form()
                self._load_inventory()
                self._load_available_items()  # Also refresh available items
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.add_failed"))
        except ValueError as e:
            messagebox.showerror(_t("common.error"),
                f"Invalid input: Please enter valid numbers for daily rate, deposit, and quantity.\n\n{str(e)}")
        except Exception as e:
            error_msg = str(e)
            # Handle UNIQUE constraint error specifically
            if "UNIQUE constraint failed: equipment_items.item_code" in error_msg:
                messagebox.showerror(_t("common.error"),
                    f"Item code '{code}' already exists!\n\n"
                    f"Please use a different item code or update the existing item.")
            else:
                messagebox.showerror(_t("common.error"), f"Failed to add item:\n{error_msg}")
            logger.error(f"Failed to add equipment item: {e}")

    def update_item(self):
        """Update selected item"""
        selected = self.inventory_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_item_selected"))
            return

        item_id = self.inventory_tree.item(selected[0])['values'][0]

        try:
            updates = {}
            if self.item_entries['daily_rate'].get():
                updates['daily_rate'] = float(self.item_entries['daily_rate'].get())
            if self.item_entries['location'].get():
                updates['location'] = self.item_entries['location'].get()
            if self.item_condition_combo.get():
                updates['condition'] = self.item_condition_combo.get()

            if EquipmentManager.update_item(item_id, **updates):
                messagebox.showinfo(_t("common.success"), _t("equipment.messages.item_updated"))
                self._load_inventory()
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.update_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_item_form(self):
        """Clear the item form"""
        for entry in self.item_entries.values():
            entry.delete(0, tk.END)
        self.item_category_combo.set('')
        self.item_condition_combo.set('good')
        self.item_description.delete(1.0, tk.END)

    def _on_item_select(self, event):
        """Handle item selection"""
        selected = self.inventory_tree.selection()
        if selected:
            values = self.inventory_tree.item(selected[0])['values']
            self.item_entries['item_code'].delete(0, tk.END)
            self.item_entries['item_code'].insert(0, values[1])
            self.item_entries['name'].delete(0, tk.END)
            self.item_entries['name'].insert(0, values[2])
            self.item_category_combo.set(values[3])
            self.item_entries['daily_rate'].delete(0, tk.END)
            self.item_entries['daily_rate'].insert(0, values[4].replace('$', ''))
            self.item_condition_combo.set(values[6])

    def _select_item_for_rental(self, event):
        """Select item for rental"""
        selected = self.available_tree.selection()
        if selected:
            values = self.available_tree.item(selected[0])['values']
            self.selected_item_id = values[0]
            self.selected_item_var.set(f"{values[1]} - {values[3]}/day")
            self._calculate_rental_cost()

    def _calculate_rental_cost(self):
        """Calculate estimated rental cost"""
        if not self.selected_item_id:
            return

        try:
            item = EquipmentManager.get_item(self.selected_item_id)
            if not item:
                return

            checkout = datetime.strptime(self.rental_entries['checkout_date'].get(), '%Y-%m-%d')
            due = datetime.strptime(self.rental_entries['due_date'].get(), '%Y-%m-%d')
            days = max(1, (due - checkout).days)
            quantity = int(self.rental_entries['quantity'].get() or 1)

            total = item['daily_rate'] * days * quantity
            self.rental_cost_var.set(f"${total:.2f} ({days} days x {quantity})")
        except Exception:
            pass

    def _clear_rental_form(self):
        """Clear the rental form"""
        for entry in self.rental_entries.values():
            entry.delete(0, tk.END)
        self.rental_purpose.delete(1.0, tk.END)
        self.selected_item_id = None
        self.selected_item_var.set("")
        self.rental_cost_var.set("$0.00")

        # Reset defaults
        self.rental_entries['quantity'].insert(0, '1')
        today = datetime.now()
        self.rental_entries['checkout_date'].insert(0, today.strftime('%Y-%m-%d'))
        self.rental_entries['checkout_time'].insert(0, '09:00')
        next_week = today + timedelta(days=7)
        self.rental_entries['due_date'].insert(0, next_week.strftime('%Y-%m-%d'))
        self.rental_entries['due_time'].insert(0, '17:00')

    def book_rental(self):
        """Book a new rental"""
        if not self.selected_item_id:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_item_selected"))
            return

        try:
            # Use stored borrower details from current user
            borrower_name = self.rental_borrower_name
            borrower_email = self.rental_borrower_email
            checkout_date = self.rental_entries['checkout_date'].get().strip()
            due_date = self.rental_entries['due_date'].get().strip()

            if not all([checkout_date, due_date]):
                messagebox.showerror(_t("common.error"), _t("equipment.errors.fill_required"))
                return

            item = EquipmentManager.get_item(self.selected_item_id)
            quantity = int(self.rental_entries['quantity'].get() or 1)

            if quantity > item['quantity_available']:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.insufficient_quantity"))
                return

            # Get borrower_id from current user
            borrower_id = (self.current_user.get('student_id') or
                          self.current_user.get('username') or
                          self.current_user.get('id') or 'GUEST')

            rental_id = RentalManager.create_rental(
                item_id=self.selected_item_id,
                borrower_id=borrower_id,
                borrower_name=borrower_name,
                checkout_date=checkout_date,
                checkout_time=self.rental_entries['checkout_time'].get() or '09:00',
                due_date=due_date,
                due_time=self.rental_entries['due_time'].get() or '17:00',
                daily_rate=item['daily_rate'],
                quantity=quantity,
                borrower_email=borrower_email,
                borrower_department=self.rental_entries['department'].get(),
                purpose=self.rental_purpose.get(1.0, tk.END).strip(),
                deposit_amount=item.get('deposit_required', 0),
                created_by=self.current_user.get('username')
            )

            if rental_id:
                rental = RentalManager.get_rental(rental_id)
                messagebox.showinfo(_t("common.success"),
                    _t("equipment.messages.rental_booked").format(
                        rental_num=rental['rental_number'],
                        amount=rental['total_amount']
                    ))
                self._clear_rental_form()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.booking_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def checkout_item(self):
        """Check out equipment (start rental)"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]
        condition = self.return_condition_combo.get()

        if RentalManager.checkout_item(rental_id, condition):
            messagebox.showinfo(_t("common.success"), _t("equipment.messages.checked_out"))
            self.refresh_all_data()
        else:
            messagebox.showerror(_t("common.error"), _t("equipment.errors.checkout_failed"))

    def return_with_payment(self):
        """Return equipment and process payment in one flow"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        values = self.active_rentals_tree.item(selected[0])['values']
        rental_id = values[0]
        base_amount = float(str(values[5]).replace('$', '').replace('£', ''))

        rental = RentalManager.get_rental(rental_id)
        if not rental:
            messagebox.showerror(_t("common.error"), "Rental not found")
            return

        # Get return details from form
        try:
            condition = self.return_condition_combo.get() or 'good'
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)
        except ValueError:
            messagebox.showerror(_t("common.error"), "Invalid fee values")
            return

        # Calculate total amount
        total_amount = base_amount + late_fee + damage_fee

        # Create payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Return Equipment & Payment")
        dialog.geometry("400x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Equipment info
        ttk.Label(dialog, text=_t("equipment.labels.equipment_return_summary"), font=('Helvetica', 14, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X, padx=20)

        ttk.Label(info_frame, text=f"Rental: {rental.get('rental_number', 'N/A')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Item: {rental.get('item_name', '')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Condition: {condition}").pack(anchor=tk.W)

        # Fees breakdown
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        fees_frame = ttk.Frame(dialog, padding="10")
        fees_frame.pack(fill=tk.X, padx=20)

        ttk.Label(fees_frame, text=f"Base Rental: ${base_amount:.2f}").pack(anchor=tk.W)
        if late_fee > 0:
            ttk.Label(fees_frame, text=f"Late Fee: ${late_fee:.2f}").pack(anchor=tk.W)
        if damage_fee > 0:
            ttk.Label(fees_frame, text=f"Damage Fee: ${damage_fee:.2f}").pack(anchor=tk.W)

        ttk.Label(fees_frame, text=f"TOTAL: ${total_amount:.2f}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(10, 0))

        # Payment method
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        payment_frame = ttk.Frame(dialog, padding="10")
        payment_frame.pack(fill=tk.X, padx=20)

        ttk.Label(payment_frame, text=_t("equipment.labels.payment_method")).pack(anchor=tk.W)

        # Check student finance account balance
        borrower_id = rental.get('borrower_id')
        balance = get_student_finance_account_balance(borrower_id) if borrower_id else None

        payment_options = ['Cash', 'Card']
        if balance is not None:
            balance_text = f"Student Account (Balance: £{balance:.2f})"
            payment_options.append(balance_text)

        payment_method_var = tk.StringVar(value='Card')
        for option in payment_options:
            ttk.Radiobutton(payment_frame, text=option, variable=payment_method_var, value=option).pack(anchor=tk.W)

        def confirm_return_and_payment():
            method = payment_method_var.get()
            actual_method = 'finance_account' if 'Student Account' in method else method.lower()

            # Check balance for student account
            if actual_method == 'finance_account':
                if balance is None or balance < total_amount:
                    messagebox.showerror(_t("common.error"), "Insufficient balance in student account")
                    return

                # Process student account payment
                result = process_student_finance_account_payment(
                    student_id=borrower_id,
                    amount=total_amount,
                    description=f"Equipment return - {rental.get('rental_number', '')}",
                    transaction_source='EquipmentRental',
                    transaction_ref=rental.get('rental_number', str(rental_id)),
                    processed_by=self.current_user.get('username')
                )
                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), result.get('message', 'Payment failed'))
                    return

            # Complete the return
            if not RentalManager.return_item(rental_id, condition, late_fee, damage_fee):
                messagebox.showerror(_t("common.error"), "Failed to complete return")
                return

            # Record payment in rental system
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                borrower_id=borrower_id,
                amount=total_amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username')
            )

            # Record revenue to central finance
            self.record_revenue_to_finance(rental_id, total_amount, actual_method)

            # Send receipt email
            self.send_receipt_email(rental_id)

            messagebox.showinfo(_t("common.success"),
                f"Equipment returned and payment of ${total_amount:.2f} processed successfully!")
            dialog.destroy()
            self.refresh_all_data()

            # Clear return form
            self.return_condition_combo.set('good')
            self.late_fee_entry.delete(0, tk.END)
            self.late_fee_entry.insert(0, "0")
            self.damage_fee_entry.delete(0, tk.END)
            self.damage_fee_entry.insert(0, "0")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("equipment.btn.confirm_pay"), command=confirm_return_and_payment).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("equipment.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def return_item(self):
        """Return equipment (legacy - use return_with_payment instead)"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        try:
            condition = self.return_condition_combo.get()
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)

            if RentalManager.return_item(rental_id, condition, late_fee, damage_fee):
                messagebox.showinfo(_t("common.success"), _t("equipment.messages.item_returned"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.return_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment for a rental with finance integration"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        values = self.active_rentals_tree.item(selected[0])['values']
        rental_id = values[0]
        amount = float(values[5].replace('$', ''))

        rental = RentalManager.get_rental(rental_id)
        if not rental:
            return

        # Payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("equipment.labels.process_payment"))
        dialog.geometry("350x280")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Amount: ${amount:.2f}", font=('Helvetica', 12, 'bold')).pack(pady=10)

        # Check student finance account balance if available
        borrower_id = rental.get('borrower_id')
        balance = get_student_finance_account_balance(borrower_id) if borrower_id else None
        balance_text = f" (Balance: £{balance:.2f})" if balance is not None else ""

        ttk.Label(dialog, text=_t("equipment.labels.payment_method") + ":").pack(pady=5)
        payment_options = ['cash', 'card']
        if balance is not None:
            payment_options.append(f'finance_account{balance_text}')
        payment_method = ttk.Combobox(dialog, values=payment_options, width=30)
        payment_method.set('card')
        payment_method.pack(pady=5)

        def confirm_payment():
            method = payment_method.get()
            actual_method = 'finance_account' if 'finance_account' in method else method

            # Process payment via finance account if selected
            if actual_method == 'finance_account':
                if balance is None or balance < amount:
                    messagebox.showerror(_t("common.error"),
                        _t("equipment.errors.insufficient_balance"))
                    return

                result = process_student_finance_account_payment(
                    student_id=borrower_id,
                    amount=amount,
                    description=f"Equipment rental payment - {rental.get('rental_number', '')}",
                    transaction_source='EquipmentRental',
                    transaction_ref=rental.get('rental_number', str(rental_id)),
                    processed_by=self.current_user.get('username')
                )
                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), result.get('message', 'Payment failed'))
                    return

            # Record payment in rental system
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                borrower_id=borrower_id,
                amount=amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username')
            )

            # Record revenue to central finance system
            self.record_revenue_to_finance(rental_id, amount, actual_method)

            if trans_id:
                messagebox.showinfo(_t("common.success"),
                    _t("equipment.messages.payment_processed").format(amount=amount))
                dialog.destroy()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.payment_failed"))

        ttk.Button(dialog, text=_t("equipment.btn.confirm_payment"),
                   command=confirm_payment).pack(pady=20)

    def record_revenue_to_finance(self, rental_id: int, amount: float, payment_method: str):
        """Record equipment rental revenue to the central finance system"""
        try:
            rental = RentalManager.get_rental(rental_id)
            if not rental:
                return

            payment_id = record_payment_to_finance(
                student_id=rental.get('borrower_id', 'EXTERNAL'),
                amount=amount,
                payment_method=payment_method,
                transaction_source='EquipmentRental',
                transaction_ref=rental.get('rental_number', str(rental_id)),
                notes=f"Equipment rental: {rental.get('item_name', '')}",
                created_by=self.current_user.get('username')
            )
            if payment_id:
                logger.info(f"Revenue recorded to finance: ${amount:.2f} for rental {rental.get('rental_number')}")
            return payment_id
        except Exception as e:
            logger.error(f"Failed to record revenue to finance: {e}")
            return None

    def extend_rental(self):
        """Extend rental due date"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        # Extension dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("equipment.labels.extend_rental"))
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("equipment.labels.new_due_date") + " (YYYY-MM-DD):").pack(pady=10)
        new_date_entry = ttk.Entry(dialog, width=20)
        new_date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        new_date_entry.pack(pady=5)

        def confirm_extend():
            if RentalManager.extend_rental(rental_id, new_date_entry.get(), '17:00'):
                messagebox.showinfo(_t("common.success"), _t("equipment.messages.rental_extended"))
                dialog.destroy()
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.extend_failed"))

        ttk.Button(dialog, text=_t("common.confirm"), command=confirm_extend).pack(pady=15)

    def cancel_rental(self):
        """Cancel a rental"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("equipment.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        if messagebox.askyesno(_t("common.confirm"), _t("equipment.confirm.cancel_rental")):
            if RentalManager.cancel_rental(rental_id, "Cancelled by user"):
                messagebox.showinfo(_t("common.success"), _t("equipment.messages.rental_cancelled"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("equipment.errors.cancel_failed"))

    def send_receipt_email(self, rental_id: int):
        """Send receipt email to borrower"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            rental = RentalManager.get_rental(rental_id)
            if not rental:
                return

            # Check for valid email (must contain @ symbol)
            borrower_email = rental.get('borrower_email')
            if not borrower_email or '@' not in borrower_email:
                logger.info(f"No valid email for rental {rental.get('rental_number', rental_id)} - skipping receipt")
                return

            subject = _t("equipment.email.receipt_subject").format(rental_num=rental['rental_number'])
            body = _t("equipment.email.receipt_body").format(
                borrower=rental['borrower_name'],
                rental_num=rental['rental_number'],
                item=rental['item_name'],
                checkout=rental['checkout_date'],
                due_date=rental['due_date'],
                amount=rental['total_amount']
            )

            send_email(borrower_email, subject, body)
            logger.info(f"Receipt email sent for rental {rental['rental_number']}")
        except Exception as e:
            logger.error(f"Failed to send receipt email: {e}")

    def open_report_window(self, title, report_content):
        """Open a report in a new window with export and email options"""
        # Create new window
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("900x700")

        # Main frame
        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Report content area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                               width=80, height=30, font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True)
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Export buttons
        ttk.Label(button_frame, text=_t("equipment.labels.export_as"), font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text=_t("equipment.btn.save_txt"), width=12,
                  command=lambda: self.export_report_as_txt(title, report_content, report_window)).pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=15)

        # Send to admin button
        ttk.Button(button_frame, text=_t("equipment.btn.email_admin"), width=15,
                  command=lambda: self.send_report_to_admin(title, report_content, report_window)).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text=_t("equipment.btn.close"), width=10,
                  command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

    def export_report_as_txt(self, title, content, parent_window):
        """Export report as TXT file"""
        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as TXT",
            defaultextension=".txt",
            initialfile=f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo(_t("equipment.msg_titles.success"), f"Report exported to:\n{filename}", parent=parent_window)
                logger.info(f"Report '{title}' exported to {filename}")
            except Exception as e:
                messagebox.showerror(_t("equipment.msg_titles.error"), f"Failed to export report:\n{str(e)}", parent=parent_window)
                logger.error(f"Failed to export report: {e}")

    def send_report_to_admin(self, title, content, parent_window):
        """Send report to admin via email"""
        try:
            # Get admin email from database
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT email, first_name, last_name
                    FROM users
                    WHERE (role = 'admin' OR role = 'staff')
                    AND email IS NOT NULL
                    AND email != ''
                    ORDER BY
                        CASE
                            WHEN id = 1 THEN 1
                            WHEN role = 'admin' THEN 2
                            WHEN role = 'staff' THEN 3
                            ELSE 4
                        END
                    LIMIT 1
                ''')
                admin = cursor.fetchone()

            if not admin:
                messagebox.showerror(_t("equipment.msg_titles.error"),
                                   "No administrator email found in database.\n"
                                   "Please ensure an administrator account exists.",
                                   parent=parent_window)
                return

            admin_email = admin[0]
            admin_name = f"{admin[1]} {admin[2]}"

            # Get current user info
            sender_name = "Equipment Rental System"
            try:
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    current_user = self.auth.current_user
                    if isinstance(current_user, dict):
                        first_name = current_user.get('first_name', '')
                        last_name = current_user.get('last_name', '')
                        if first_name or last_name:
                            sender_name = f"{first_name} {last_name}".strip()
            except Exception as e:
                logger.warning(f"Could not get current user info: {e}")

            # Prepare email
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Try to render from template
            email_subject = None
            email_body = None
            if render_template:
                email_subject, email_body = render_template('commerce/equipment/admin_report', {
                    'admin_name': admin_name,
                    'report_title': title,
                    'sender_name': sender_name,
                    'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'report_content': content
                })

            # Fallback if template not found
            if not email_subject or not email_body:
                email_subject = f"Equipment Rental Report: {title}"
                email_body = f"""
Dear {admin_name},

This is an automated report from the Equipment Rental System.

Report: {title}
Generated by: {sender_name}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}

{content}

{'='*60}

This report was generated automatically by the Equipment Rental Management System.
"""

            # Send email
            success = send_email(
                recipient_email=admin_email,
                subject=email_subject,
                body=email_body
            )

            if success:
                messagebox.showinfo(_t("equipment.msg_titles.success"),
                                  f"Report sent successfully to:\n{admin_name} ({admin_email})",
                                  parent=parent_window)
                logger.info(f"Report '{title}' emailed to {admin_email}")
            else:
                messagebox.showerror(_t("equipment.msg_titles.error"),
                                   "Failed to send email. Please check email configuration.",
                                   parent=parent_window)

        except Exception as e:
            messagebox.showerror(_t("equipment.msg_titles.error"), f"Failed to send report to admin:\n{str(e)}", parent=parent_window)
            logger.error(f"Failed to send report to admin: {e}")

    def _generate_inventory_report(self):
        """Generate inventory summary report as text"""
        summary = ReportManager.get_inventory_summary()
        return f"""
INVENTORY SUMMARY
=================

Total Items: {summary.get('total_items', 0)}
Total Quantity: {summary.get('total_quantity', 0)}
Available: {summary.get('available_quantity', 0)}
Currently Rented: {summary.get('rented_quantity', 0)}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _generate_revenue_report(self):
        """Generate revenue report as text"""
        revenue = ReportManager.get_revenue_report()
        total_rentals = revenue.get('total_rentals') or 0
        total_revenue = revenue.get('total_revenue') or 0
        avg_rental_value = revenue.get('avg_rental_value') or 0
        total_late_fees = revenue.get('total_late_fees') or 0
        total_damage_fees = revenue.get('total_damage_fees') or 0

        return f"""
REVENUE REPORT
==============

Total Rentals: {total_rentals}
Total Revenue: ${total_revenue:.2f}
Average Rental Value: ${avg_rental_value:.2f}
Late Fees Collected: ${total_late_fees:.2f}
Damage Fees Collected: ${total_damage_fees:.2f}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _generate_popular_items_report(self):
        """Generate popular items report as text"""
        items = ReportManager.get_popular_items(10)
        report = "TOP 10 MOST RENTED ITEMS\n" + "=" * 30 + "\n\n"

        for i, item in enumerate(items, 1):
            report += f"{i}. {item['name']} ({item['category']})\n"
            report += f"   Rentals: {item['rental_count']} | Revenue: ${item['total_revenue'] or 0:.2f}\n\n"

        report += f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return report

    def _generate_overdue_report(self):
        """Generate overdue rentals report as text"""
        overdue = ReportManager.get_overdue_rentals()
        report = f"OVERDUE RENTALS ({len(overdue)})\n" + "=" * 30 + "\n\n"

        for r in overdue:
            report += f"Rental: {r['rental_number']}\n"
            report += f"Borrower: {r['borrower_name']}\n"
            report += f"Item: {r['item_name']}\n"
            report += f"Due Date: {r['due_date']}\n"
            report += f"Amount: ${r['total_amount']:.2f}\n"
            report += "-" * 30 + "\n"

        report += f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return report

    def show_inventory_summary(self):
        """Show inventory summary"""
        summary = ReportManager.get_inventory_summary()
        report = f"""
INVENTORY SUMMARY
=================

Total Items: {summary.get('total_items', 0)}
Total Quantity: {summary.get('total_quantity', 0)}
Available: {summary.get('available_quantity', 0)}
Currently Rented: {summary.get('rented_quantity', 0)}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_revenue_report(self):
        """Show revenue report"""
        revenue = ReportManager.get_revenue_report()
        # Handle None values safely
        total_rentals = revenue.get('total_rentals') or 0
        total_revenue = revenue.get('total_revenue') or 0
        avg_rental_value = revenue.get('avg_rental_value') or 0
        total_late_fees = revenue.get('total_late_fees') or 0
        total_damage_fees = revenue.get('total_damage_fees') or 0
        report = f"""
REVENUE REPORT
==============

Total Rentals: {total_rentals}
Total Revenue: ${total_revenue:.2f}
Average Rental Value: ${avg_rental_value:.2f}
Late Fees Collected: ${total_late_fees:.2f}
Damage Fees Collected: ${total_damage_fees:.2f}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_popular_items(self):
        """Show popular items report"""
        items = ReportManager.get_popular_items(10)
        report = "TOP 10 MOST RENTED ITEMS\n" + "=" * 30 + "\n\n"

        for i, item in enumerate(items, 1):
            report += f"{i}. {item['name']} ({item['category']})\n"
            report += f"   Rentals: {item['rental_count']} | Revenue: ${item['total_revenue'] or 0:.2f}\n\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_overdue_rentals(self):
        """Show overdue rentals"""
        overdue = ReportManager.get_overdue_rentals()
        report = f"OVERDUE RENTALS ({len(overdue)})\n" + "=" * 30 + "\n\n"

        for r in overdue:
            report += f"Rental: {r['rental_number']}\n"
            report += f"Borrower: {r['borrower_name']}\n"
            report += f"Item: {r['item_name']}\n"
            report += f"Due Date: {r['due_date']}\n"
            report += f"Amount: ${r['total_amount']:.2f}\n"
            report += "-" * 30 + "\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def generate_admin_report(self):
        """Generate admin report"""
        report = ReportManager.generate_admin_report()
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def email_admin_report(self):
        """Email admin report (legacy method - redirects to new window)"""
        # Redirect to new window implementation
        self.open_report_window("Equipment Rental Admin Report", ReportManager.generate_admin_report())


def launch_equipment_gui(parent=None, auth=None):
    """Launch the Equipment Rental GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = EquipmentRentalGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
