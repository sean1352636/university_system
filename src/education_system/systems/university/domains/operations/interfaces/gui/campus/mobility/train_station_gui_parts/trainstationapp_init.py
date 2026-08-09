"""Methods __init__ through update_price."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TrainStationApp:
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("train.title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self.root.configure(bg="#f0f4f8")

        # Initialize authentication - use provided auth system or centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = get_auth()

        # Get current user info
        self.current_user = None
        self._load_current_user()

        # Initialize database
        self.db = Database()

        # Configure styles
        self.setup_styles()

        # Create main interface
        self.create_widgets()

    def _load_current_user(self):
        """Load current user information from auth system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user = self.auth.current_user
                self.current_user = {
                    'id': user.get('id') or user.get('user_id'),
                    'username': user.get('username', ''),
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'email': user.get('email', ''),
                    'student_id': user.get('student_id', ''),
                    'role': user.get('role', 'user'),
                }
                # Get full name
                if self.current_user['first_name'] and self.current_user['last_name']:
                    self.current_user['full_name'] = f"{self.current_user['first_name']} {self.current_user['last_name']}"
                else:
                    self.current_user['full_name'] = self.current_user['username']
        except Exception as e:
            logger.warning(f"Could not load current user: {e}")
            self.current_user = None

    def _get_current_user_student_id(self):
        """Get student ID from current user"""
        if self.current_user:
            return self.current_user.get('student_id') or self.current_user.get('username')
        return None

    def _send_booking_confirmation_email(self, ticket_data):
        """Send booking confirmation email to the user"""
        if not EMAIL_AVAILABLE:
            logger.warning(_t("train.email.service_unavailable"))
            return False

        try:
            # Get user email
            user_email = None
            student_id = self._get_current_user_student_id()

            if self.current_user and self.current_user.get('email'):
                user_email = self.current_user['email']
            elif student_id and FINANCE_AVAILABLE:
                user_email = get_student_email(student_id)

            if not user_email:
                logger.warning(_t("train.email.no_email_found"))
                return False

            # Build email content
            passenger_name = ticket_data.get('passenger_name', _t("train.email.valued_customer"))

            # Try to use template first, fall back to i18n-based email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('train_booking_confirmation', {
                        'customer_name': passenger_name,
                        'booking_id': ticket_data['ticket_number'],
                        'departure_station': ticket_data['departure_station'],
                        'arrival_station': ticket_data['arrival_station'],
                        'departure_date': ticket_data['purchase_date'],
                        'departure_time': ticket_data['departure_time'],
                        'ticket_type': ticket_data.get('ticket_type', 'Standard'),
                        'price': f"{ticket_data['price_paid']:.2f}",
                        'payment_method': ticket_data['payment_method']
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using i18n-based email.")
                # Fallback to i18n-based email
                subject = _t("train.email.subject", ticket_number=ticket_data['ticket_number'])
                body = f"""{_t("train.email.greeting", name=passenger_name)}

{_t("train.email.confirmation_message")}

═══════════════════════════════════════════════════════
                    {_t("train.email.booking_details")}
═══════════════════════════════════════════════════════

{_t("train.email.ticket_number")}: {ticket_data['ticket_number']}
{_t("train.email.receipt_number")}: {ticket_data['receipt_number']}
{_t("train.email.booking_date")}: {ticket_data['purchase_date']}

{_t("train.email.journey_details")}:
────────────────────────────────────────
{_t("train.email.service")}: {ticket_data['service_number']}
{_t("train.email.from_station")}: {ticket_data['departure_station']}
{_t("train.email.to_station")}: {ticket_data['arrival_station']}
{_t("train.email.departure_time")}: {ticket_data['departure_time']}
{_t("train.email.arrival_time")}: {ticket_data['arrival_time']}

{_t("train.email.payment_details")}:
────────────────────────────────────────
{_t("train.email.payment_method")}: {ticket_data['payment_method']}
{_t("train.email.total_fare")}: £{ticket_data['price_paid']:.2f}

═══════════════════════════════════════════════════════

{_t("train.email.thank_you")}

{_t("train.email.signature")}
{_t("train.app_name")}

---
{_t("train.email.auto_message")}
"""

            result = send_email(user_email, subject, body)
            if result:
                logger.info(f"Booking confirmation email sent to {user_email}")
                return True
            else:
                logger.warning(f"Failed to send booking confirmation email to {user_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending booking confirmation email: {e}")
            return False

    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()

        # Button styles
        style.configure("Primary.TButton",
                       font=("Helvetica", 11, "bold"),
                       padding=10)

        style.configure("TLabel",
                       font=("Helvetica", 10),
                       background="#f0f4f8")

        style.configure("Header.TLabel",
                       font=("Helvetica", 24, "bold"),
                       background="#f0f4f8",
                       foreground="#1a365d")

        style.configure("Treeview",
                       font=("Helvetica", 10),
                       rowheight=30)

        style.configure("Treeview.Heading",
                       font=("Helvetica", 10, "bold"))

    def create_widgets(self):
        """Create the main interface"""
        # Header
        header_frame = tk.Frame(self.root, bg="#1a365d", height=80)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        title_label = tk.Label(header_frame,
                              text=f"🚂 {_t('train.header_title')}",
                              font=("Helvetica", 22, "bold"),
                              bg="#1a365d", fg="white")
        title_label.pack(pady=10)

        # Show current user if logged in
        if self.current_user:
            user_info = f"👤 {self.current_user.get('full_name', '')}"
            if FINANCE_AVAILABLE:
                student_id = self._get_current_user_student_id()
                if student_id:
                    balance = get_student_finance_account_balance(student_id)
                    if balance is not None:
                        user_info += f" | 💰 {_t('train.balance')}: £{balance:.2f}"
            user_label = tk.Label(header_frame, text=user_info,
                                  font=("Helvetica", 10),
                                  bg="#1a365d", fg="#a0aec0")
            user_label.pack()

        # Navigation buttons
        nav_frame = tk.Frame(self.root, bg="#2d3748", height=50)
        nav_frame.pack(fill="x")
        nav_frame.pack_propagate(False)

        buttons = [
            (f"📋 {_t('train.nav.view_services')}", self.show_services),
            (f"🎫 {_t('train.nav.purchase_ticket')}", self.show_purchase),
            (f"🎟️ {_t('train.nav.view_tickets')}", self.show_tickets),
            (f"💸 {_t('train.nav.refunds', default='Refunds')}", self.show_refunds),
        ]

        for text, command in buttons:
            btn = tk.Button(nav_frame, text=text, command=command,
                          font=("Helvetica", 11, "bold"),
                          bg="#4a5568", fg="white",
                          activebackground="#718096",
                          activeforeground="white",
                          relief="flat", padx=20, pady=10,
                          cursor="hand2")
            btn.pack(side="left", padx=5, pady=8)

        # Main content area
        self.content_frame = tk.Frame(self.root, bg="#f0f4f8")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Show services by default
        self.show_services()

    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_services(self):
        """Display all train services"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.services.title"),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 15))

        # Create treeview with scrollbar
        tree_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=True)

        columns = ("Service", "From", "To", "Departure", "Arrival", "Price", "Seats")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure columns
        tree.heading("Service", text=_t("train.services.service_no"))
        tree.heading("From", text=_t("train.services.departure_station"))
        tree.heading("To", text=_t("train.services.arrival_station"))
        tree.heading("Departure", text=_t("train.services.departure"))
        tree.heading("Arrival", text=_t("train.services.arrival"))
        tree.heading("Price", text=_t("train.services.price"))
        tree.heading("Seats", text=_t("train.services.available"))

        tree.column("Service", width=100, anchor="center")
        tree.column("From", width=180)
        tree.column("To", width=180)
        tree.column("Departure", width=80, anchor="center")
        tree.column("Arrival", width=80, anchor="center")
        tree.column("Price", width=80, anchor="center")
        tree.column("Seats", width=80, anchor="center")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate data
        services = self.db.get_all_services()
        for service in services:
            tree.insert("", "end", values=(
                service[1],  # service_number
                service[2],  # departure_station
                service[3],  # arrival_station
                service[4],  # departure_time
                service[5],  # arrival_time
                f"£{service[6]:.2f}",  # price
                service[7]   # available_seats
            ))

        # Add alternating row colors
        tree.tag_configure("oddrow", background="#e2e8f0")
        for i, item in enumerate(tree.get_children()):
            if i % 2:
                tree.item(item, tags=("oddrow",))

    def show_purchase(self):
        """Show ticket purchase interface"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.purchase.title"),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 20))

        # Main purchase frame
        purchase_frame = tk.Frame(self.content_frame, bg="white",
                                 relief="solid", bd=1)
        purchase_frame.pack(fill="both", expand=True, padx=50)

        inner_frame = tk.Frame(purchase_frame, bg="white")
        inner_frame.pack(pady=30, padx=40)

        # Passenger name - auto-populated if logged in
        tk.Label(inner_frame, text=f"{_t('train.purchase.passenger_name')}:",
                font=("Helvetica", 12), bg="white").grid(row=0, column=0, sticky="e", pady=10, padx=10)
        self.name_entry = tk.Entry(inner_frame, font=("Helvetica", 12), width=30)
        self.name_entry.grid(row=0, column=1, pady=10, padx=10)

        # Auto-populate passenger name from current user
        if self.current_user and self.current_user.get('full_name'):
            self.name_entry.insert(0, self.current_user['full_name'])
            self.name_entry.config(state='readonly')

        # Service selection
        tk.Label(inner_frame, text=f"{_t('train.purchase.select_service')}:",
                font=("Helvetica", 12), bg="white").grid(row=1, column=0, sticky="e", pady=10, padx=10)

        self.services = self.db.get_all_services()
        service_options = [f"{s[1]} | {s[2]} → {s[3]} | {s[4]} | £{s[6]:.2f}" for s in self.services]

        self.service_var = tk.StringVar()
        self.service_combo = ttk.Combobox(inner_frame, textvariable=self.service_var,
                                         values=service_options, width=50, state="readonly")
        self.service_combo.grid(row=1, column=1, pady=10, padx=10)
        self.service_combo.bind("<<ComboboxSelected>>", self.update_price)

        # Payment method
        tk.Label(inner_frame, text=f"{_t('train.purchase.payment_method')}:",
                font=("Helvetica", 12), bg="white").grid(row=2, column=0, sticky="e", pady=10, padx=10)

        self.payment_var = tk.StringVar(value=_t('gui.operations.campus.mobility.train_station_gui_parts.trainstationapp_init.values.card', default="Card"))
        payment_frame = tk.Frame(inner_frame, bg="white")
        payment_frame.grid(row=2, column=1, sticky="w", pady=10, padx=10)

        payments = [
            (f"💳 {_t('train.payment.card')}", "Card"),
            (f"💵 {_t('train.payment.cash')}", "Cash"),
            (f"🎓 {_t('train.payment.student_account')}", "Student Account")
        ]

        # Show student account balance if available
        if FINANCE_AVAILABLE and self.current_user:
            student_id = self._get_current_user_student_id()
            if student_id:
                balance = get_student_finance_account_balance(student_id)
                if balance is not None:
                    payments[2] = (f"🎓 {_t('train.payment.student_account')} (£{balance:.2f})", "Student Account")

        for text, value in payments:
            rb = tk.Radiobutton(payment_frame, text=text, variable=self.payment_var,
                              value=value, font=("Helvetica", 11), bg="white",
                              command=self.update_price)
            rb.pack(side="left", padx=15)

        # Price display
        tk.Label(inner_frame, text=f"{_t('train.purchase.total_price')}:",
                font=("Helvetica", 12, "bold"), bg="white").grid(row=3, column=0, sticky="e", pady=20, padx=10)

        self.price_label = tk.Label(inner_frame, text="£0.00",
                                   font=("Helvetica", 18, "bold"),
                                   bg="white", fg="#2f855a")
        self.price_label.grid(row=3, column=1, sticky="w", pady=20, padx=10)

        # Student discount note
        self.discount_label = tk.Label(inner_frame, text="",
                                       font=("Helvetica", 10, "italic"),
                                       bg="white", fg="#718096")
        self.discount_label.grid(row=4, column=1, sticky="w", padx=10)

        # Purchase button
        purchase_btn = tk.Button(inner_frame, text=f"🎫 {_t('train.purchase.complete_purchase')}",
                                font=("Helvetica", 14, "bold"),
                                bg="#2f855a", fg="white",
                                activebackground="#276749",
                                relief="flat", padx=30, pady=15,
                                cursor="hand2",
                                command=self.complete_purchase)
        purchase_btn.grid(row=5, column=0, columnspan=2, pady=30)

    def update_price(self, event=None):
        """Update displayed price based on selection"""
        if not self.service_combo.current() >= 0:
            return

        service_idx = self.service_combo.current()
        base_price = self.services[service_idx][6]

        if self.payment_var.get() == "Student Account":
            price = base_price * 0.7  # 30% student discount
            self.discount_label.config(text=_t("train.purchase.student_discount_applied"))
        else:
            price = base_price
            self.discount_label.config(text="")

        self.price_label.config(text=f"£{price:.2f}")
