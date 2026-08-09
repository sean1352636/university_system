"""Methods __init__ through create_returns_tab."""

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
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
        self.rental_cost_var = tk.StringVar(value="£0.00")
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

        # Status filter - allows listing rentals by any status (not just active/reserved)
        status_filter_frame = ttk.Frame(left_frame)
        status_filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(status_filter_frame, text=_t("carrental.labels.status") + ":").pack(side=tk.LEFT)
        self.rental_status_filter = ttk.Combobox(status_filter_frame, state="readonly", width=20)
        self.rental_status_filter['values'] = ['Active + Reserved', 'All'] + RENTAL_STATUSES
        self.rental_status_filter.set('Active + Reserved')
        self.rental_status_filter.pack(side=tk.LEFT, padx=5)
        self.rental_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_active_rentals())

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
