"""Methods __init__ through create_technicians_tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
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
                _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_init.dialogs.you_must_be_logged_in_to_access_the_nail_bar_module_please_log_i', default="You must be logged in to access the Nail Bar module.\n\n"
                "Please log in through the main GUI first.")
            )
            if self.parent:
                self.parent.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("nailbar.window_title"),
                _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_init.dialogs.you_must_be_logged_in_to_access_the_nail_bar_module_please_launc', default="You must be logged in to access the Nail Bar module.\n\n"
                "Please launch this module from the main GUI after logging in.")
            )
            if self.parent:
                self.parent.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("nailbar.window_title"),
                _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_init.dialogs.you_are_not_currently_logged_in_please_log_in_through_the_main_g', default="You are not currently logged in.\n\n"
                "Please log in through the main GUI to access this module.")
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
        from education_system.systems.university.domain.operations.commerce.nailbar.services.nailbar_core import init_nailbar_db
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
