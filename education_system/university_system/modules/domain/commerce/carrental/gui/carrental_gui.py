"""Car Rental System GUI Module"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, timedelta

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection, transaction
from education_system.university_system.modules.domain.commerce.carrental.services.carrental_core import (
    VehicleManager, RentalManager, TransactionManager, ReportManager,
    init_carrental_db, VEHICLE_CATEGORIES, RENTAL_STATUSES, VEHICLE_STATUSES
)
from education_system.university_system.modules.shared.utils.finance_integration import (
    record_payment_to_finance,
    process_student_finance_account_payment,
    get_student_finance_account_balance,
    get_student_info
)

logger = logging.getLogger(__name__)


class CarRentalGUI:
    """Car Rental System GUI - 25 functions"""

    def __init__(self, root, auth):
        """Initialize the Car Rental GUI"""
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if not self.current_user:
            messagebox.showerror(_t("carrental.window_title"), _t("carrental.errors.login_required"))
            root.destroy()
            return

        self.root.title(_t("carrental.window_title"))
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

        ttk.Label(header_frame, text=_t("carrental.title"),
                  font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("common.refresh"),
                   command=self.refresh_all_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.back"),
                   command=self.return_to_homescreen).pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_vehicles_tab()
        self.create_rentals_tab()
        self.create_returns_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

    def _init_database(self):
        """Initialize the car rental database"""
        try:
            init_carrental_db()
            logger.info("Car rental database initialized")
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
        self._load_vehicles()
        self._load_rentals()
        self._load_active_rentals()

    def create_vehicles_tab(self):
        """Create the vehicles management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.vehicles"))

        # Left panel - Vehicle list
        left_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.vehicle_list"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("carrental.labels.category") + ":").pack(side=tk.LEFT)
        self.vehicle_category_filter = ttk.Combobox(filter_frame, values=['All'] + VEHICLE_CATEGORIES, width=15)
        self.vehicle_category_filter.set('All')
        self.vehicle_category_filter.pack(side=tk.LEFT, padx=5)
        self.vehicle_category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_vehicles())

        # Treeview
        columns = ('id', 'reg', 'make', 'model', 'category', 'daily_rate', 'status')
        self.vehicles_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=20)

        self.vehicles_tree.heading('id', text=_t('carrental.columns.id'))
        self.vehicles_tree.heading('reg', text=_t("carrental.labels.registration"))
        self.vehicles_tree.heading('make', text=_t("carrental.labels.make"))
        self.vehicles_tree.heading('model', text=_t("carrental.labels.model"))
        self.vehicles_tree.heading('category', text=_t("carrental.labels.category"))
        self.vehicles_tree.heading('daily_rate', text=_t("carrental.labels.daily_rate"))
        self.vehicles_tree.heading('status', text=_t("carrental.labels.status"))

        self.vehicles_tree.column('id', width=50)
        self.vehicles_tree.column('reg', width=100)
        self.vehicles_tree.column('make', width=100)
        self.vehicles_tree.column('model', width=100)
        self.vehicles_tree.column('category', width=80)
        self.vehicles_tree.column('daily_rate', width=80)
        self.vehicles_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.vehicles_tree.yview)
        self.vehicles_tree.configure(yscrollcommand=scrollbar.set)

        self.vehicles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel - Add vehicle form
        right_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.add_vehicle"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Form fields
        fields = [
            ("registration", _t("carrental.labels.registration")),
            ("make", _t("carrental.labels.make")),
            ("model", _t("carrental.labels.model")),
            ("year", _t("carrental.labels.year")),
            ("daily_rate", _t("carrental.labels.daily_rate")),
            ("color", _t("carrental.labels.color")),
            ("seats", _t("carrental.labels.seats")),
            ("mileage", _t("carrental.labels.mileage"))
        ]

        self.vehicle_entries = {}
        for i, (field, label) in enumerate(fields):
            ttk.Label(right_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(right_frame, width=20)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.vehicle_entries[field] = entry

        # Category dropdown
        row = len(fields)
        ttk.Label(right_frame, text=_t("carrental.labels.category") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.vehicle_category_combo = ttk.Combobox(right_frame, values=VEHICLE_CATEGORIES, width=17)
        self.vehicle_category_combo.grid(row=row, column=1, pady=2, padx=5)

        # Transmission dropdown
        row += 1
        ttk.Label(right_frame, text=_t("carrental.labels.transmission") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.vehicle_transmission_combo = ttk.Combobox(right_frame, values=['automatic', 'manual'], width=17)
        self.vehicle_transmission_combo.set('automatic')
        self.vehicle_transmission_combo.grid(row=row, column=1, pady=2, padx=5)

        # Fuel type dropdown
        row += 1
        ttk.Label(right_frame, text=_t("carrental.labels.fuel_type") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.vehicle_fuel_combo = ttk.Combobox(right_frame, values=['petrol', 'diesel', 'electric', 'hybrid'], width=17)
        self.vehicle_fuel_combo.set('petrol')
        self.vehicle_fuel_combo.grid(row=row, column=1, pady=2, padx=5)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("carrental.btn.add_vehicle"),
                   command=self.add_vehicle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("carrental.btn.update_vehicle"),
                   command=self.update_vehicle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"),
                   command=self._clear_vehicle_form).pack(side=tk.LEFT, padx=5)

        self.vehicles_tree.bind('<Double-1>', self._on_vehicle_select)

    def create_rentals_tab(self):
        """Create the rentals booking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.rentals"))

        # Left panel - Available vehicles
        left_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.available_vehicles"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        columns = ('id', 'vehicle', 'category', 'daily_rate')
        self.available_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)

        self.available_tree.heading('id', text=_t('carrental.columns.id'))
        self.available_tree.heading('vehicle', text=_t("carrental.labels.vehicle"))
        self.available_tree.heading('category', text=_t("carrental.labels.category"))
        self.available_tree.heading('daily_rate', text=_t("carrental.labels.daily_rate"))

        self.available_tree.column('id', width=50)
        self.available_tree.column('vehicle', width=200)
        self.available_tree.column('category', width=100)
        self.available_tree.column('daily_rate', width=80)

        self.available_tree.pack(fill=tk.BOTH, expand=True)
        self.available_tree.bind('<Double-1>', self._select_vehicle_for_rental)

        # Right panel - Booking form
        right_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.book_rental"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Selected vehicle
        ttk.Label(right_frame, text=_t("carrental.labels.selected_vehicle") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.selected_vehicle_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.selected_vehicle_var, font=('Helvetica', 10, 'bold')).grid(row=0, column=1, pady=2)
        self.selected_vehicle_id = None

        # Current user details (read-only display)
        user_info_frame = ttk.LabelFrame(right_frame, text=_t("carrental.labels.customer_details"), padding="5")
        user_info_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=5)

        # Fetch user details from database
        user_name, user_email = self._get_user_details_from_db()

        # Display email or "Not set" for display purposes
        display_email = user_email if user_email and '@' in user_email else 'Not set'

        ttk.Label(user_info_frame, text=f"Name: {user_name}", font=('Helvetica', 9)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(user_info_frame, text=f"Email: {display_email}", font=('Helvetica', 9)).grid(row=1, column=0, sticky=tk.W)

        # Store user details for booking (only store valid email)
        self.rental_customer_name = user_name
        self.rental_customer_email = user_email if user_email and '@' in user_email else None

        # Rental details (editable)
        rental_fields = [
            ("license_number", _t("carrental.labels.license_number")),
            ("pickup_date", _t("carrental.labels.pickup_date") + " (YYYY-MM-DD)"),
            ("pickup_time", _t("carrental.labels.pickup_time") + " (HH:MM)"),
            ("return_date", _t("carrental.labels.return_date") + " (YYYY-MM-DD)"),
            ("return_time", _t("carrental.labels.return_time") + " (HH:MM)")
        ]

        self.rental_entries = {}
        for i, (field, label) in enumerate(rental_fields, start=2):
            ttk.Label(right_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(right_frame, width=25)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.rental_entries[field] = entry

        # Set default dates
        today = datetime.now()
        self.rental_entries['pickup_date'].insert(0, today.strftime('%Y-%m-%d'))
        self.rental_entries['pickup_time'].insert(0, '10:00')
        tomorrow = today + timedelta(days=1)
        self.rental_entries['return_date'].insert(0, tomorrow.strftime('%Y-%m-%d'))
        self.rental_entries['return_time'].insert(0, '10:00')

        # Cost display
        row = len(rental_fields) + 2  # +2 for user info frame
        self.rental_cost_var = tk.StringVar(value="$0.00")
        ttk.Label(right_frame, text=_t("carrental.labels.estimated_cost") + ":").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Label(right_frame, textvariable=self.rental_cost_var, font=('Helvetica', 12, 'bold')).grid(row=row, column=1, pady=5)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("carrental.btn.calculate_cost"),
                   command=self._calculate_rental_cost).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("carrental.btn.book_rental"),
                   command=self.book_rental).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"),
                   command=self._clear_rental_form).pack(side=tk.LEFT, padx=5)

    def create_returns_tab(self):
        """Create the vehicle returns tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.returns"))

        # Active rentals list
        left_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.active_rentals"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        columns = ('id', 'rental_num', 'customer', 'vehicle', 'return_date', 'amount')
        self.active_rentals_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)

        self.active_rentals_tree.heading('id', text=_t('carrental.columns.id'))
        self.active_rentals_tree.heading('rental_num', text=_t("carrental.labels.rental_number"))
        self.active_rentals_tree.heading('customer', text=_t("carrental.labels.customer"))
        self.active_rentals_tree.heading('vehicle', text=_t("carrental.labels.vehicle"))
        self.active_rentals_tree.heading('return_date', text=_t("carrental.labels.due_date"))
        self.active_rentals_tree.heading('amount', text=_t("carrental.labels.amount"))

        self.active_rentals_tree.column('id', width=50)
        self.active_rentals_tree.column('rental_num', width=120)
        self.active_rentals_tree.column('customer', width=150)
        self.active_rentals_tree.column('vehicle', width=150)
        self.active_rentals_tree.column('return_date', width=100)
        self.active_rentals_tree.column('amount', width=80)

        self.active_rentals_tree.pack(fill=tk.BOTH, expand=True)

        # Return form
        right_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.process_return"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Return fields
        ttk.Label(right_frame, text=_t("carrental.labels.return_mileage") + ":").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.return_mileage_entry = ttk.Entry(right_frame, width=20)
        self.return_mileage_entry.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("carrental.labels.fuel_level") + ":").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.return_fuel_combo = ttk.Combobox(right_frame, values=['Full', '3/4', '1/2', '1/4', 'Empty'], width=17)
        self.return_fuel_combo.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("carrental.labels.fuel_fee") + " ($):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.fuel_fee_entry = ttk.Entry(right_frame, width=20)
        self.fuel_fee_entry.insert(0, "0")
        self.fuel_fee_entry.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("carrental.labels.late_fee") + " ($):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.late_fee_entry = ttk.Entry(right_frame, width=20)
        self.late_fee_entry.insert(0, "0")
        self.late_fee_entry.grid(row=3, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text=_t("carrental.labels.damage_fee") + " ($):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.damage_fee_entry = ttk.Entry(right_frame, width=20)
        self.damage_fee_entry.insert(0, "0")
        self.damage_fee_entry.grid(row=4, column=1, pady=5, padx=5)

        # Buttons
        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("carrental.btn.return_vehicle_pay"),
                   command=self.return_vehicle_with_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("carrental.btn.cancel_rental"),
                   command=self.cancel_rental).pack(side=tk.LEFT, padx=5)

        # Add refund button below the active rentals list
        refund_btn_frame = tk.Frame(left_frame, bg='#f9f9f9', relief='ridge', borderwidth=2)
        refund_btn_frame.pack(fill=tk.X, pady=10, padx=5)

        tk.Label(refund_btn_frame, text=_t("carrental.labels.need_refund"),
                font=('Arial', 10, 'italic'), bg='#f9f9f9', fg='#555').pack(pady=(8, 5))

        tk.Button(refund_btn_frame, text=_t("carrental.btn.process_refund_selected"),
                 command=self.refund_from_returns_tab,
                 font=('Arial', 11, 'bold'), bg='#e74c3c', fg='white',
                 activebackground='#c0392b', activeforeground='white',
                 relief='raised', padx=20, pady=10, cursor='hand2',
                 borderwidth=3).pack(pady=(0, 8))

    def create_reports_tab(self):
        """Create the reports and analytics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.reports"))

        # Left panel - Report options
        left_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.report_options"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Button(left_frame, text=_t("carrental.btn.fleet_summary"),
                   command=self.show_fleet_summary, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.revenue_report"),
                   command=self.show_revenue_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.popular_vehicles"),
                   command=self.show_popular_vehicles, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.generate_admin_report"),
                   command=self.generate_admin_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.email_admin_report"),
                   command=self.email_admin_report, width=25).pack(pady=5)

        # Right panel - Report display
        right_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.report_output"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(right_frame, wrap=tk.WORD, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_categories(self):
        """Get vehicle categories"""
        return VEHICLE_CATEGORIES

    def _load_vehicles(self):
        """Load vehicles into the treeview"""
        for item in self.vehicles_tree.get_children():
            self.vehicles_tree.delete(item)

        category = self.vehicle_category_filter.get()
        vehicles = VehicleManager.get_all_vehicles()

        for v in vehicles:
            if category == 'All' or v['category'] == category:
                self.vehicles_tree.insert('', tk.END, values=(
                    v['vehicle_id'], v['registration_number'], v['make'],
                    v['model'], v['category'], f"${v['daily_rate']:.2f}", v['status']
                ))

        # Also update available vehicles for rentals
        self._load_available_vehicles()

    def _load_available_vehicles(self):
        """Load available vehicles for rental tab"""
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)

        vehicles = VehicleManager.get_available_vehicles()
        for v in vehicles:
            self.available_tree.insert('', tk.END, values=(
                v['vehicle_id'],
                f"{v['make']} {v['model']} ({v['registration_number']})",
                v['category'],
                f"${v['daily_rate']:.2f}"
            ))

    def _load_rentals(self):
        """Load rentals data"""
        pass  # Rentals are loaded in _load_active_rentals

    def _load_active_rentals(self):
        """Load active rentals into the returns tab"""
        for item in self.active_rentals_tree.get_children():
            self.active_rentals_tree.delete(item)

        rentals = RentalManager.get_rentals_by_status('active')
        rentals += RentalManager.get_rentals_by_status('reserved')

        for r in rentals:
            self.active_rentals_tree.insert('', tk.END, values=(
                r['rental_id'], r['rental_number'], r['customer_name'],
                f"{r['make']} {r['model']}", r['return_date'],
                f"${r['total_amount']:.2f}"
            ))

    def add_vehicle(self):
        """Add a new vehicle to the fleet"""
        try:
            reg = self.vehicle_entries['registration'].get().strip()
            make = self.vehicle_entries['make'].get().strip()
            model = self.vehicle_entries['model'].get().strip()
            year = self.vehicle_entries['year'].get().strip()
            daily_rate = self.vehicle_entries['daily_rate'].get().strip()
            category = self.vehicle_category_combo.get()

            if not all([reg, make, model, year, daily_rate, category]):
                messagebox.showerror(_t("common.error"), _t("carrental.errors.fill_required"))
                return

            vehicle_id = VehicleManager.add_vehicle(
                registration_number=reg,
                make=make,
                model=model,
                year=int(year),
                category=category,
                daily_rate=float(daily_rate),
                color=self.vehicle_entries['color'].get().strip() or None,
                seats=int(self.vehicle_entries['seats'].get() or 5),
                mileage=int(self.vehicle_entries['mileage'].get() or 0),
                transmission=self.vehicle_transmission_combo.get(),
                fuel_type=self.vehicle_fuel_combo.get()
            )

            if vehicle_id:
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.vehicle_added").format(reg=reg))
                self._clear_vehicle_form()
                self._load_vehicles()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.add_failed"))
        except ValueError as e:
            messagebox.showerror(_t("common.error"), _t("carrental.errors.invalid_input"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_vehicle(self):
        """Update selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_vehicle_selected"))
            return

        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]

        try:
            updates = {}
            if self.vehicle_entries['daily_rate'].get():
                updates['daily_rate'] = float(self.vehicle_entries['daily_rate'].get())
            if self.vehicle_entries['mileage'].get():
                updates['mileage'] = int(self.vehicle_entries['mileage'].get())
            if self.vehicle_entries['color'].get():
                updates['color'] = self.vehicle_entries['color'].get()

            if VehicleManager.update_vehicle(vehicle_id, **updates):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.vehicle_updated"))
                self._load_vehicles()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.update_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_vehicle_form(self):
        """Clear the vehicle form"""
        for entry in self.vehicle_entries.values():
            entry.delete(0, tk.END)
        self.vehicle_category_combo.set('')
        self.vehicle_transmission_combo.set('automatic')
        self.vehicle_fuel_combo.set('petrol')

    def _on_vehicle_select(self, event):
        """Handle vehicle selection"""
        selected = self.vehicles_tree.selection()
        if selected:
            values = self.vehicles_tree.item(selected[0])['values']
            self.vehicle_entries['registration'].delete(0, tk.END)
            self.vehicle_entries['registration'].insert(0, values[1])
            self.vehicle_entries['make'].delete(0, tk.END)
            self.vehicle_entries['make'].insert(0, values[2])
            self.vehicle_entries['model'].delete(0, tk.END)
            self.vehicle_entries['model'].insert(0, values[3])
            self.vehicle_category_combo.set(values[4])
            self.vehicle_entries['daily_rate'].delete(0, tk.END)
            self.vehicle_entries['daily_rate'].insert(0, values[5].replace('$', ''))

    def _select_vehicle_for_rental(self, event):
        """Select vehicle for rental booking"""
        selected = self.available_tree.selection()
        if selected:
            values = self.available_tree.item(selected[0])['values']
            self.selected_vehicle_id = values[0]
            self.selected_vehicle_var.set(f"{values[1]} - {values[3]}/day")
            self._calculate_rental_cost()

    def _calculate_rental_cost(self):
        """Calculate estimated rental cost"""
        if not self.selected_vehicle_id:
            return

        try:
            vehicle = VehicleManager.get_vehicle(self.selected_vehicle_id)
            if not vehicle:
                return

            pickup_date = datetime.strptime(self.rental_entries['pickup_date'].get(), '%Y-%m-%d')
            return_date = datetime.strptime(self.rental_entries['return_date'].get(), '%Y-%m-%d')
            days = max(1, (return_date - pickup_date).days)

            total = vehicle['daily_rate'] * days
            self.rental_cost_var.set(f"${total:.2f} ({days} days)")
        except Exception:
            pass

    def _clear_rental_form(self):
        """Clear the rental form"""
        for entry in self.rental_entries.values():
            entry.delete(0, tk.END)
        self.selected_vehicle_id = None
        self.selected_vehicle_var.set("")
        self.rental_cost_var.set("$0.00")

        # Reset default dates
        today = datetime.now()
        self.rental_entries['pickup_date'].insert(0, today.strftime('%Y-%m-%d'))
        self.rental_entries['pickup_time'].insert(0, '10:00')
        tomorrow = today + timedelta(days=1)
        self.rental_entries['return_date'].insert(0, tomorrow.strftime('%Y-%m-%d'))
        self.rental_entries['return_time'].insert(0, '10:00')

    def book_rental(self):
        """Book a new rental"""
        if not self.selected_vehicle_id:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_vehicle_selected"))
            return

        try:
            # Use stored customer details from current user
            customer_name = self.rental_customer_name
            customer_email = self.rental_customer_email
            license_number = self.rental_entries['license_number'].get().strip()
            pickup_date = self.rental_entries['pickup_date'].get().strip()
            return_date = self.rental_entries['return_date'].get().strip()

            if not all([license_number, pickup_date, return_date]):
                messagebox.showerror(_t("common.error"), _t("carrental.errors.fill_required"))
                return

            vehicle = VehicleManager.get_vehicle(self.selected_vehicle_id)

            # Get customer_id from current user
            customer_id = (self.current_user.get('student_id') or
                          self.current_user.get('username') or
                          self.current_user.get('id') or 'GUEST')

            rental_id = RentalManager.create_rental(
                vehicle_id=self.selected_vehicle_id,
                customer_id=customer_id,
                customer_name=customer_name,
                license_number=license_number,
                pickup_date=pickup_date,
                pickup_time=self.rental_entries['pickup_time'].get() or '10:00',
                return_date=return_date,
                return_time=self.rental_entries['return_time'].get() or '10:00',
                daily_rate=vehicle['daily_rate'],
                customer_email=customer_email,
                created_by=self.current_user.get('username')
            )

            if rental_id:
                rental = RentalManager.get_rental(rental_id)
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.rental_booked").format(
                        rental_num=rental['rental_number'],
                        amount=rental['total_amount']
                    ))
                self._clear_rental_form()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.booking_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def return_vehicle_with_payment(self):
        """Return vehicle and process payment in one flow"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
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
            return_mileage = int(self.return_mileage_entry.get() or 0)
            fuel_level = self.return_fuel_combo.get() or 'Full'
            fuel_fee = float(self.fuel_fee_entry.get() or 0)
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)
        except ValueError:
            messagebox.showerror(_t("common.error"), "Invalid fee values")
            return

        # Calculate total amount
        total_amount = base_amount + fuel_fee + late_fee + damage_fee

        # Create payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.windows.return_payment"))
        dialog.geometry("400x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Vehicle info
        ttk.Label(dialog, text=_t("carrental.labels.vehicle_return_summary"), font=('Helvetica', 14, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X, padx=20)

        ttk.Label(info_frame, text=f"Rental: {rental.get('rental_number', 'N/A')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Vehicle: {rental.get('make', '')} {rental.get('model', '')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Return Mileage: {return_mileage}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Fuel Level: {fuel_level}").pack(anchor=tk.W)

        # Fees breakdown
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        fees_frame = ttk.Frame(dialog, padding="10")
        fees_frame.pack(fill=tk.X, padx=20)

        ttk.Label(fees_frame, text=f"Base Rental: ${base_amount:.2f}").pack(anchor=tk.W)
        if fuel_fee > 0:
            ttk.Label(fees_frame, text=f"Fuel Fee: ${fuel_fee:.2f}").pack(anchor=tk.W)
        if late_fee > 0:
            ttk.Label(fees_frame, text=f"Late Fee: ${late_fee:.2f}").pack(anchor=tk.W)
        if damage_fee > 0:
            ttk.Label(fees_frame, text=f"Damage Fee: ${damage_fee:.2f}").pack(anchor=tk.W)

        ttk.Label(fees_frame, text=f"TOTAL: ${total_amount:.2f}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(10, 0))

        # Payment method
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        payment_frame = ttk.Frame(dialog, padding="10")
        payment_frame.pack(fill=tk.X, padx=20)

        ttk.Label(payment_frame, text=_t("carrental.labels.payment_method")).pack(anchor=tk.W)

        # Check student finance account balance
        student_id = rental.get('customer_id')
        balance = get_student_finance_account_balance(student_id) if student_id else None

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
                    student_id=student_id,
                    amount=total_amount,
                    description=f"Car rental return - {rental.get('rental_number', '')}",
                    transaction_source='CarRental',
                    transaction_ref=rental.get('rental_number', str(rental_id)),
                    processed_by=self.current_user.get('username')
                )
                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), result.get('message', 'Payment failed'))
                    return

            # Complete the return
            if not RentalManager.complete_rental(
                rental_id=rental_id,
                return_mileage=return_mileage,
                fuel_level=fuel_level,
                fuel_fee=fuel_fee,
                late_fee=late_fee,
                damage_fee=damage_fee
            ):
                messagebox.showerror(_t("common.error"), "Failed to complete return")
                return

            # Record payment in rental system
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                customer_id=student_id,
                amount=total_amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username')
            )

            # Record revenue to central finance
            self.record_revenue_to_finance(rental_id, total_amount, actual_method)

            # Send receipt email
            self.send_receipt_email(rental_id)

            messagebox.showinfo(_t("common.success"),
                f"Vehicle returned and payment of ${total_amount:.2f} processed successfully!")
            dialog.destroy()
            self.refresh_all_data()

            # Clear return form
            self.return_mileage_entry.delete(0, tk.END)
            self.return_fuel_combo.set('')
            self.fuel_fee_entry.delete(0, tk.END)
            self.fuel_fee_entry.insert(0, "0")
            self.late_fee_entry.delete(0, tk.END)
            self.late_fee_entry.insert(0, "0")
            self.damage_fee_entry.delete(0, tk.END)
            self.damage_fee_entry.insert(0, "0")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("carrental.btn.confirm_pay"), command=confirm_return_and_payment).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("carrental.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def complete_return(self):
        """Complete a vehicle return (legacy - use return_vehicle_with_payment instead)"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        try:
            return_mileage = int(self.return_mileage_entry.get() or 0)
            fuel_level = self.return_fuel_combo.get()
            fuel_fee = float(self.fuel_fee_entry.get() or 0)
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)

            if RentalManager.complete_rental(
                rental_id=rental_id,
                return_mileage=return_mileage,
                fuel_level=fuel_level,
                fuel_fee=fuel_fee,
                late_fee=late_fee,
                damage_fee=damage_fee
            ):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.return_completed"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.return_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment for a rental with finance integration"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        values = self.active_rentals_tree.item(selected[0])['values']
        rental_id = values[0]
        amount = float(values[5].replace('$', ''))

        rental = RentalManager.get_rental(rental_id)
        if not rental:
            return

        # Payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.labels.process_payment"))
        dialog.geometry("350x280")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Amount: ${amount:.2f}", font=('Helvetica', 12, 'bold')).pack(pady=10)

        # Check student finance account balance if available
        student_id = rental.get('customer_id')
        balance = get_student_finance_account_balance(student_id) if student_id else None
        balance_text = f" (Balance: £{balance:.2f})" if balance is not None else ""

        ttk.Label(dialog, text=_t("carrental.labels.payment_method") + ":").pack(pady=5)
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
                        _t("carrental.errors.insufficient_balance"))
                    return

                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=amount,
                    description=f"Car rental payment - {rental.get('rental_number', '')}",
                    transaction_source='CarRental',
                    transaction_ref=rental.get('rental_number', str(rental_id)),
                    processed_by=self.current_user.get('username')
                )
                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), result.get('message', 'Payment failed'))
                    return

            # Record payment in rental system
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                customer_id=student_id,
                amount=amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username')
            )

            # Record revenue to central finance system
            self.record_revenue_to_finance(rental_id, amount, actual_method)

            if trans_id:
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.payment_processed").format(amount=amount))
                dialog.destroy()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.payment_failed"))

        ttk.Button(dialog, text=_t("carrental.btn.confirm_payment"),
                   command=confirm_payment).pack(pady=20)

    def record_revenue_to_finance(self, rental_id: int, amount: float, payment_method: str):
        """Record car rental revenue to the central finance system"""
        try:
            rental = RentalManager.get_rental(rental_id)
            if not rental:
                return

            payment_id = record_payment_to_finance(
                student_id=rental.get('customer_id', 'EXTERNAL'),
                amount=amount,
                payment_method=payment_method,
                transaction_source='CarRental',
                transaction_ref=rental.get('rental_number', str(rental_id)),
                notes=f"Car rental: {rental.get('make', '')} {rental.get('model', '')}",
                created_by=self.current_user.get('username')
            )
            if payment_id:
                logger.info(f"Revenue recorded to finance: ${amount:.2f} for rental {rental.get('rental_number')}")
            return payment_id
        except Exception as e:
            logger.error(f"Failed to record revenue to finance: {e}")
            return None

    def cancel_rental(self):
        """Cancel a rental"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        if messagebox.askyesno(_t("common.confirm"), _t("carrental.confirm.cancel_rental")):
            if RentalManager.cancel_rental(rental_id, "Cancelled by user"):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.rental_cancelled"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.cancel_failed"))

    def send_receipt_email(self, rental_id: int):
        """Send receipt email to customer"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            rental = RentalManager.get_rental(rental_id)
            if not rental:
                return

            # Check for valid email (must contain @ symbol)
            customer_email = rental.get('customer_email')
            if not customer_email or '@' not in customer_email:
                logger.info(f"No valid email for rental {rental.get('rental_number', rental_id)} - skipping receipt")
                return

            subject = _t("carrental.email.receipt_subject").format(rental_num=rental['rental_number'])
            body = _t("carrental.email.receipt_body").format(
                customer=rental['customer_name'],
                rental_num=rental['rental_number'],
                vehicle=f"{rental['make']} {rental['model']}",
                pickup=rental['pickup_date'],
                return_date=rental['return_date'],
                amount=rental['total_amount']
            )

            send_email(customer_email, subject, body)
            logger.info(f"Receipt email sent for rental {rental['rental_number']}")
        except Exception as e:
            logger.error(f"Failed to send receipt email: {e}")

    def show_fleet_summary(self):
        """Show fleet summary report"""
        summary = ReportManager.get_fleet_summary()
        report = f"""
FLEET SUMMARY
=============

Total Vehicles: {summary.get('total_vehicles', 0)}
Available: {summary.get('available', 0)}
Currently Rented: {summary.get('rented', 0)}
In Maintenance: {summary.get('maintenance', 0)}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_revenue_report(self):
        """Show revenue report"""
        revenue = ReportManager.get_revenue_report()
        # Handle None values safely
        total_rentals = revenue.get('total_rentals') or 0
        completed_rentals = revenue.get('completed_rentals') or 0
        total_revenue = revenue.get('total_revenue') or 0
        avg_rental_value = revenue.get('avg_rental_value') or 0
        report = f"""
REVENUE REPORT
==============

Total Rentals: {total_rentals}
Completed Rentals: {completed_rentals}
Total Revenue: ${total_revenue:.2f}
Average Rental Value: ${avg_rental_value:.2f}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_popular_vehicles(self):
        """Show popular vehicles report"""
        vehicles = ReportManager.get_popular_vehicles(10)
        report = "TOP 10 VEHICLES BY RENTALS\n" + "=" * 30 + "\n\n"

        for i, v in enumerate(vehicles, 1):
            report += f"{i}. {v['make']} {v['model']} ({v['category']})\n"
            report += f"   Rentals: {v['rental_count']} | Revenue: ${v['total_revenue'] or 0:.2f}\n\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def generate_admin_report(self):
        """Generate comprehensive admin report"""
        report = ReportManager.generate_admin_report()
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def email_admin_report(self):
        """Email admin report"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            report = ReportManager.generate_admin_report()

            # Get admin email
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                )
                result = cursor.fetchone()

            if result and result[0]:
                send_email(
                    result[0],
                    _t("carrental.email.admin_report_subject"),
                    report
                )
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_admin_email"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.refunds", default="Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("carrental.refunds.title", default="Car Rental Refunds"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("common.search", default="Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("common.search_label", default="Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with 7 columns
        columns = ('transaction_id', 'date', 'customer', 'amount', 'transaction_type', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('transaction_id', text=_t('carrental.refunds.transaction_id', default='Transaction ID'))
        self.refunds_tree.heading('date', text=_t('common.date', default='Date'))
        self.refunds_tree.heading('customer', text=_t('carrental.common.customer', default='Customer'))
        self.refunds_tree.heading('amount', text=_t('common.amount', default='Amount'))
        self.refunds_tree.heading('transaction_type', text=_t('carrental.refunds.type', default='Type'))
        self.refunds_tree.heading('payment_method', text=_t('common.payment_method', default='Payment Method'))
        self.refunds_tree.heading('status', text=_t('common.status', default='Status'))

        self.refunds_tree.column('transaction_id', width=100)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('transaction_type', width=120)
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

        # Buttons frame - Make buttons more prominent and visible
        buttons_frame = tk.Frame(tab, bg='#f0f0f0', relief='raised', borderwidth=2)
        buttons_frame.pack(fill=tk.X, pady=15, padx=10)

        # Add instruction label
        tk.Label(buttons_frame, text=_t("carrental.labels.select_transaction_action"),
                font=('Arial', 10, 'italic'), bg='#f0f0f0', fg='#555').pack(pady=(10, 5))

        # Button container for centering
        btn_container = tk.Frame(buttons_frame, bg='#f0f0f0')
        btn_container.pack(pady=(0, 10))

        # Large, prominent refund button
        tk.Button(btn_container, text="💸 " + _t("carrental.refunds.process", default="Process Refund"),
                 command=self.process_carrental_refund,
                 font=('Arial', 12, 'bold'), bg='#e74c3c', fg='white',
                 activebackground='#c0392b', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="📋 " + _t("common.view_details", default="View Details"),
                 command=self.view_carrental_transaction_details,
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="🔄 " + _t("common.refresh", default="Refresh"),
                 command=self.refresh_refunds_list,
                 font=('Arial', 11, 'bold'), bg='#95a5a6', fg='white',
                 activebackground='#7f8c8d', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="📊 " + _t("common.export_csv", default="Export to CSV"),
                 command=self.export_refunds_to_csv,
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()

            with get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        t.transaction_id,
                        t.created_at,
                        t.customer_id,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number
                    FROM transactions t
                    WHERE t.source_type = 'car_rental'
                    ORDER BY t.created_at DESC
                """

                cursor.execute(query)
                transactions = cursor.fetchall()

                for trans in transactions:
                    transaction_id, date, customer_id, amount, transaction_type, payment_method, status, reference = trans

                    # Apply search filter
                    if search_term:
                        searchable = f"{transaction_id} {customer_id} {transaction_type} {status} {reference or ''}".lower()
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
                        transaction_id,
                        formatted_date,
                        customer_id,
                        f"£{amount:.2f}",
                        transaction_type or 'N/A',
                        payment_method or 'N/A',
                        status or 'completed'
                    ), tags=(tag,))

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def refund_from_returns_tab(self):
        """Process a refund from the Returns tab by finding the transaction for the selected rental"""
        # Get selected rental
        selection = self.active_rentals_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                  "Please select a rental to refund.")
            return

        item = self.active_rentals_tree.item(selection[0])
        values = item['values']
        rental_id = values[0]
        rental_number = values[1]
        customer_name = values[2]
        amount_str = values[5]

        try:
            # Find the transaction for this rental
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT transaction_id, amount, customer_id, payment_method, status
                    FROM transactions
                    WHERE source_type = 'car_rental' AND reference_id = ? AND reference_type = 'rental'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (rental_id,))
                result = cursor.fetchone()

                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       f"No transaction found for rental {rental_number}.\n\n"
                                       "The rental may not have been paid yet.")
                    return

                transaction_id, amount, customer_id, payment_method, status = result

                # Check if already refunded
                if status == 'refunded':
                    messagebox.showwarning(_t("carrental.refunds.already_refunded", default="Already Refunded"),
                                          f"Rental {rental_number} has already been refunded.")
                    return

            # Confirm refund
            if not messagebox.askyesno(_t("carrental.refunds.confirm", default="Confirm Refund"),
                                       f"Process refund for Rental {rental_number}?\n\n"
                                       f"Customer: {customer_name}\n"
                                       f"Amount: £{amount:.2f}\n"
                                       f"Payment Method: {payment_method}"):
                return

            # Show refund method dialog
            self.show_carrental_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            logger.error(f"Error processing refund from returns tab: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                               f"Failed to process refund: {str(e)}")

    def process_carrental_refund(self):
        """Process a refund for a car rental transaction"""
        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("carrental.refunds.select_transaction", default="Please select a transaction to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]
        amount_str = values[3]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("carrental.refunds.already_refunded", default="Already Refunded"),
                                  _t("carrental.refunds.already_refunded_msg", default="This transaction has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except (ValueError, TypeError):
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("carrental.refunds.confirm", default="Confirm Refund"),
                                   f"Refund £{amount:.2f} for Transaction #{transaction_id}?"):
            return

        try:
            # Get customer ID
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT customer_id FROM transactions WHERE transaction_id = ? AND source_type = 'car_rental'",
                             (transaction_id,))
                result = cursor.fetchone()
                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("carrental.refunds.transaction_not_found", default="Transaction not found."))
                    return
                customer_id = result[0]

            # Show refund method dialog
            self.show_carrental_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            logger.error(f"Error processing car rental refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_carrental_refund_method_dialog(self, transaction_id, amount, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("carrental.refunds.select_method", default="Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if customer_id:
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
            self._complete_carrental_refund(transaction_id, amount, 'cash', customer_id)

        def refund_card():
            dialog.destroy()
            self._complete_carrental_refund(transaction_id, amount, 'card', customer_id)

        def refund_student_account():
            dialog.destroy()
            self.add_carrental_refund_to_student_account(transaction_id, amount, customer_id)

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

        ttk.Button(buttons_frame, text=_t("common.cancel", default="Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)

    def _complete_carrental_refund(self, transaction_id, amount, refund_method, customer_id):
        """Complete the refund process (for cash/card)"""
        try:
            # Generate refund reference
            refund_ref = f"CARRENTAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute("""
                    UPDATE transactions
                    SET status = 'refunded',
                        reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'car_rental'
                """, (refund_ref, transaction_id))

                # Create refund record in unified_refunds table
                # Get processed_by
                processed_by = None
                if self.current_user:
                    processed_by = self.current_user.get('username') or self.current_user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, student_id, amount,
                     refund_method, refund_reference, refund_date, processed_by)
                    VALUES ('car_rental', ?, 'transaction', ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (str(transaction_id), customer_id, amount, refund_method, refund_ref, processed_by))

            # Send receipt
            self.send_carrental_refund_receipt(customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_carrental_finance_gui(transaction_id, amount, refund_method, refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing car rental refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")

    def add_carrental_refund_to_student_account(self, transaction_id, amount, customer_id):
        """Add refund amount to student finance account"""
        try:
            from education_system.university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(customer_id)

            # Generate refund reference
            refund_ref = f"CARRENTAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute("""
                    UPDATE transactions
                    SET status = 'refunded',
                        reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'car_rental'
                """, (refund_ref, transaction_id))

                # Create refund record in unified_refunds table
                # Get processed_by
                processed_by = None
                if self.current_user:
                    processed_by = self.current_user.get('username') or self.current_user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, student_id, amount,
                     refund_method, refund_reference, refund_date, processed_by)
                    VALUES ('car_rental', ?, 'transaction', ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (str(transaction_id), customer_id, amount, 'student_account', refund_ref, processed_by))

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, customer_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (customer_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in transactions table
                cursor.execute("""
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, customer_id, amount, new_balance, f'Car rental refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Send receipt
            self.send_carrental_refund_receipt(customer_id, amount, 'student_account', refund_ref, new_balance)

            # Notify finance GUI
            self.notify_carrental_finance_gui(transaction_id, amount, 'student_account', refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding car rental refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_carrental_refund_receipt(self, customer_id, amount, refund_method, refund_ref, new_balance=None):
        """Send refund receipt email to customer"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Get customer email - check students table first, then users table
            customer_email = None
            customer_name = customer_id

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Try students table first
                cursor.execute("SELECT email_address, first_name, last_name FROM students WHERE student_id = ?", (customer_id,))
                result = cursor.fetchone()

                if result and result[0]:
                    customer_email = result[0]
                    first_name = result[1] or ''
                    last_name = result[2] or ''
                    customer_name = f"{first_name} {last_name}".strip() or customer_id
                else:
                    # Fall back to users table (for admin/staff accounts)
                    cursor.execute("SELECT email, first_name, last_name, username FROM users WHERE username = ? OR id = ?",
                                 (customer_id, customer_id))
                    result = cursor.fetchone()

                    if result and result[0]:
                        customer_email = result[0]
                        first_name = result[1] or ''
                        last_name = result[2] or ''
                        username = result[3] or customer_id
                        customer_name = f"{first_name} {last_name}".strip() or username

                if not customer_email:
                    logger.warning(f"No email found for customer {customer_id} in students or users table")
                    return

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text if applicable
            balance_text = ""
            if new_balance is not None:
                balance_text = f"Your new student account balance is: £{new_balance:.2f}"

            # Use JSON template for email
            from education_system.university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/carrental/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'rental_number': 'N/A',
                'vehicle_info': 'N/A',
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method_display,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'balance_text': balance_text
            })

            # Send email
            send_email(
                recipient_email=customer_email,
                subject=subject,
                body=body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending car rental refund receipt: {e}")

    def notify_carrental_finance_gui(self, transaction_id, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            # Finance refund data is now recorded in unified_refunds table
            # This method retains notification logic only
            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_carrental_transaction_details(self):
        """View detailed information about a transaction"""
        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("carrental.refunds.select_transaction_view", default="Please select a transaction to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get transaction details with rental info
                cursor.execute("""
                    SELECT
                        t.transaction_id,
                        t.customer_id,
                        TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) as customer_name,
                        s.email_address,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number,
                        t.created_at,
                        t.processed_by,
                        t.reference_id as rental_id,
                        r.start_date,
                        r.end_date,
                        r.vehicle_id,
                        v.make,
                        v.model,
                        v.registration
                    FROM transactions t
                    LEFT JOIN students s ON t.customer_id = s.student_id
                    LEFT JOIN carrental_rentals r ON t.reference_id = r.rental_id AND t.reference_type = 'rental'
                    LEFT JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                    WHERE t.source_type = 'car_rental' AND t.transaction_id = ?
                """, (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("carrental.refunds.transaction_not_found", default="Transaction not found."))
                    return

                (trans_id, customer_id, customer_name, customer_email, amount, transaction_type,
                 payment_method, status, reference, created_at, processed_by, rental_id,
                 start_date, end_date, vehicle_id, make, model, registration) = trans

                # If customer info not found in students table, check users table
                if not customer_name or not customer_email:
                    cursor.execute("""
                        SELECT
                            TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) as name,
                            email,
                            username
                        FROM users
                        WHERE username = ? OR id = ?
                    """, (customer_id, customer_id))
                    user_result = cursor.fetchone()

                    if user_result:
                        user_name, user_email, username = user_result
                        if not customer_name:
                            customer_name = user_name or username or customer_id
                        if not customer_email:
                            customer_email = user_email or 'Not available'

                # Ensure we have some value for customer_name
                if not customer_name:
                    customer_name = customer_id

                # Build rental details text
                rental_details = ""
                if rental_id:
                    rental_details = f"""
Rental Information:
  Rental ID: {rental_id}
  Start Date: {start_date or 'N/A'}
  End Date: {end_date or 'N/A'}
  Vehicle: {make or 'N/A'} {model or 'N/A'}
  Registration: {registration or 'N/A'}
"""

                # Create details window
                details_window = tk.Toplevel(self.root)
                details_window.title(_t("carrental.refunds.transaction_details", default="Transaction Details"))
                details_window.geometry("600x700")
                details_window.transient(self.root)

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
CAR RENTAL TRANSACTION DETAILS
{'=' * 50}

Transaction Information:
  Transaction ID: {trans_id}
  Status: {status}
  Type: {transaction_type}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Customer Information:
  Customer ID: {customer_id}
  Name: {customer_name or 'N/A'}
  Email: {customer_email or 'N/A'}
{rental_details}
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
            logger.error(f"Error viewing transaction details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")

    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'carrental_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        t.transaction_id,
                        t.created_at,
                        t.customer_id,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number
                    FROM transactions t
                    WHERE t.source_type = 'car_rental'
                    ORDER BY t.created_at DESC
                """)

                transactions = cursor.fetchall()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Date', 'Customer ID', 'Amount',
                               'Transaction Type', 'Payment Method', 'Status', 'Reference'])

                # Write data
                for trans in transactions:
                    transaction_id, date, customer_id, amount, transaction_type, payment_method, status, reference = trans
                    writer.writerow([
                        transaction_id,
                        date or '',
                        customer_id,
                        f'{amount:.2f}' if amount else '0.00',
                        transaction_type or '',
                        payment_method or '',
                        status or 'completed',
                        reference or ''
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")


def launch_carrental_gui(parent=None, auth=None):
    """Launch the Car Rental GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = CarRentalGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
