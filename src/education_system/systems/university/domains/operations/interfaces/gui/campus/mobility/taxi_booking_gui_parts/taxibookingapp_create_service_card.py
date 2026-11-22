"""Methods create_service_card through process_booking."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TaxiBookingApp:
    def create_service_card(self, parent, service, row, col):
        """Create a service card widget"""
        service_id, name, vehicle, capacity, price_km, base_fare, desc, available = service

        card = tk.Frame(parent, bg=ModernStyle.BG_CARD, padx=20, pady=20)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Configure grid weights
        parent.grid_columnconfigure(col, weight=1, minsize=350)

        # Service icon based on vehicle type
        icons = {
            "Sedan": "🚗", "SUV": "🚙", "Hatchback": "🚕", "Minivan": "🚐",
            "Electric": "⚡", "Luxury Sedan": "🏎️", "Van": "🚌"
        }
        icon = icons.get(vehicle, "🚗")

        # Header row
        header_frame = tk.Frame(card, bg=ModernStyle.BG_CARD)
        header_frame.pack(fill=tk.X)

        icon_label = tk.Label(header_frame, text=icon, font=("Segoe UI", 32),
                              bg=ModernStyle.BG_CARD, fg=ModernStyle.ACCENT)
        icon_label.pack(side=tk.LEFT)

        name_label = tk.Label(header_frame, text=name, font=ModernStyle.FONT_SUBTITLE,
                              bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY)
        name_label.pack(side=tk.LEFT, padx=10)

        # Vehicle type badge
        badge = tk.Label(header_frame, text=vehicle, font=ModernStyle.FONT_SMALL,
                        bg=ModernStyle.ACCENT, fg=ModernStyle.TEXT_PRIMARY, padx=8, pady=2)
        badge.pack(side=tk.RIGHT)

        # Description
        desc_label = tk.Label(card, text=desc, font=ModernStyle.FONT_BODY,
                              bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY,
                              wraplength=300, justify=tk.LEFT)
        desc_label.pack(fill=tk.X, pady=10)

        # Details frame
        details_frame = tk.Frame(card, bg=ModernStyle.BG_CARD)
        details_frame.pack(fill=tk.X)

        # Capacity
        cap_frame = tk.Frame(details_frame, bg=ModernStyle.BG_CARD)
        cap_frame.pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(cap_frame, text=f"👥 {_t('taxi.services.capacity')}", font=ModernStyle.FONT_SMALL,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY).pack(anchor="w")
        tk.Label(cap_frame, text=_t("taxi.services.passengers", count=capacity), font=ModernStyle.FONT_BODY,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w")

        # Pricing
        price_frame = tk.Frame(details_frame, bg=ModernStyle.BG_CARD)
        price_frame.pack(side=tk.LEFT)
        tk.Label(price_frame, text=f"💰 {_t('taxi.services.pricing')}", font=ModernStyle.FONT_SMALL,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY).pack(anchor="w")
        tk.Label(price_frame, text=_t("taxi.services.price_format", base=base_fare, per_km=price_km),
                font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_CARD,
                fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w")

        # Book button
        book_btn = self.create_button(card, _t("taxi.services.book_now"),
                                      lambda s=service: self.select_service_and_book(s))
        book_btn.pack(fill=tk.X, pady=(15, 0))

    def select_service_and_book(self, service):
        """Select a service and show booking view"""
        self.selected_service = service
        self.show_booking_view()

    def show_booking_view(self):
        """Display the booking form"""
        self.clear_content()

        self.create_header(_t("taxi.booking.title"), _t("taxi.booking.subtitle"))

        # Scrollable container
        canvas = tk.Canvas(self.content_frame, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mousewheel for scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        # For Linux
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Main booking container
        booking_frame = tk.Frame(scrollable_frame, bg=ModernStyle.BG_CARD, padx=30, pady=30)
        booking_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left column - Form
        form_frame = tk.Frame(booking_frame, bg=ModernStyle.BG_CARD)
        form_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        # Customer Name - auto-populated if logged in
        self.create_form_field(form_frame, _t("taxi.booking.customer_name"), "name_entry")
        # Auto-populate customer name from current user
        if self.current_user and self.current_user.get('full_name'):
            self.name_entry.insert(0, self.current_user['full_name'])
            self.name_entry.config(state='readonly')  # Make it read-only if auto-filled

        # Service Selection
        tk.Label(form_frame, text=_t("taxi.booking.select_service"), font=ModernStyle.FONT_SUBTITLE,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w", pady=(15, 5))

        services = self.db.get_all_services()
        service_names = [f"{s[1]} ({s[2]}) - £{s[4]:.2f}/km" for s in services]

        self.service_var = tk.StringVar()
        self.service_combo = ttk.Combobox(form_frame, values=service_names,
                                          font=ModernStyle.FONT_BODY, state="readonly")
        self.service_combo.pack(fill=tk.X, pady=(0, 10), ipady=8)

        # Pre-select if coming from service card
        if self.selected_service:
            idx = next((i for i, s in enumerate(services) if s[0] == self.selected_service[0]), 0)
            self.service_combo.current(idx)
        else:
            self.service_combo.current(0)

        self.services_list = services

        # Pickup Location
        self.create_form_field(form_frame, _t("taxi.booking.pickup_location"), "pickup_entry")

        # Dropoff Location
        self.create_form_field(form_frame, _t("taxi.booking.dropoff_location"), "dropoff_entry")

        # Distance
        tk.Label(form_frame, text=_t("taxi.booking.distance_km"), font=ModernStyle.FONT_SUBTITLE,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w", pady=(15, 5))

        self.distance_var = tk.StringVar()
        self.distance_var.trace('w', self.update_fare_estimate)
        self.distance_entry = tk.Entry(form_frame, font=ModernStyle.FONT_BODY,
                                       bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY,
                                       insertbackground=ModernStyle.TEXT_PRIMARY,
                                       textvariable=self.distance_var)
        self.distance_entry.pack(fill=tk.X, ipady=10)

        # Payment Method
        tk.Label(form_frame, text=_t("taxi.booking.payment_method"), font=ModernStyle.FONT_SUBTITLE,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w", pady=(15, 5))

        self.payment_var = tk.StringVar(value=_t('gui.operations.campus.mobility.taxi_booking_gui_parts.taxibookingapp_create_service_card.values.cash', default="Cash"))
        payment_frame = tk.Frame(form_frame, bg=ModernStyle.BG_CARD)
        payment_frame.pack(fill=tk.X, pady=5)

        payments = [
            ("💵 Cash", "Cash", _t('taxi.payment.cash')),
            ("💳 Card", "Card", _t('taxi.payment.card')),
            ("🎓 Student", "Student Account", _t('taxi.payment.student_account'))
        ]

        # Show student account balance if available
        student_balance_text = ""
        if FINANCE_AVAILABLE and self.current_user:
            student_id = self._get_current_user_student_id()
            if student_id:
                balance = get_student_finance_account_balance(student_id)
                if balance is not None:
                    student_balance_text = f" (£{balance:.2f})"

        for idx, (icon_text, value, label) in enumerate(payments):
            # Create a frame for each payment option - stack vertically for better visibility
            option_frame = tk.Frame(payment_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=10)
            option_frame.pack(fill=tk.X, pady=5)

            display_text = label
            if value == "Student Account" and student_balance_text:
                display_text = f"{label}{student_balance_text}"

            rb = tk.Radiobutton(
                option_frame,
                text=f"{icon_text.split()[0]} {display_text}",
                variable=self.payment_var,
                value=value,
                font=ModernStyle.FONT_BODY,
                bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY,
                selectcolor=ModernStyle.ACCENT,
                activebackground=ModernStyle.BG_SECONDARY,
                activeforeground=ModernStyle.TEXT_PRIMARY,
                highlightthickness=0,
                bd=0,
                indicatoron=True,
                cursor="hand2"
            )
            rb.pack(anchor="w")

        # Right column - Summary
        summary_frame = tk.Frame(booking_frame, bg=ModernStyle.BG_SECONDARY, padx=25, pady=25, width=300)
        summary_frame.pack(side=tk.RIGHT, fill=tk.Y)
        summary_frame.pack_propagate(False)

        tk.Label(summary_frame, text=_t("taxi.booking.fare_summary"), font=ModernStyle.FONT_SUBTITLE,
                bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.ACCENT).pack(anchor="w")

        sep = tk.Frame(summary_frame, bg=ModernStyle.BORDER, height=1)
        sep.pack(fill=tk.X, pady=15)

        # Base fare
        self.base_fare_label = tk.Label(summary_frame, text=f"{_t('taxi.booking.base_fare')}: £0.00",
                                        font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                                        fg=ModernStyle.TEXT_SECONDARY)
        self.base_fare_label.pack(anchor="w", pady=5)

        # Distance fare
        self.distance_fare_label = tk.Label(summary_frame, text=f"{_t('taxi.booking.distance')}: £0.00",
                                            font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                                            fg=ModernStyle.TEXT_SECONDARY)
        self.distance_fare_label.pack(anchor="w", pady=5)

        sep2 = tk.Frame(summary_frame, bg=ModernStyle.BORDER, height=1)
        sep2.pack(fill=tk.X, pady=15)

        # Total
        self.total_label = tk.Label(summary_frame, text=f"{_t('taxi.booking.total')}: £0.00",
                                    font=("Segoe UI", 18, "bold"), bg=ModernStyle.BG_SECONDARY,
                                    fg=ModernStyle.SUCCESS)
        self.total_label.pack(anchor="w", pady=5)

        # Student discount note
        self.discount_label = tk.Label(summary_frame, text="",
                                       font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_SECONDARY,
                                       fg=ModernStyle.WARNING)
        self.discount_label.pack(anchor="w", pady=5)

        # Bind combo change
        self.service_combo.bind("<<ComboboxSelected>>", self.update_fare_estimate)
        self.payment_var.trace('w', lambda *args: self.update_fare_estimate())

        # Book button
        book_btn = self.create_button(summary_frame, f"✓ {_t('taxi.booking.confirm_booking')}", self.process_booking, "success")
        book_btn.pack(fill=tk.X, pady=(30, 0))

        # Initial fare calculation
        self.update_fare_estimate()

    def create_form_field(self, parent, label, attr_name):
        """Create a form field with label and entry"""
        tk.Label(parent, text=label, font=ModernStyle.FONT_SUBTITLE,
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY).pack(anchor="w", pady=(15, 5))

        entry = tk.Entry(parent, font=ModernStyle.FONT_BODY,
                        bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY,
                        insertbackground=ModernStyle.TEXT_PRIMARY)
        entry.pack(fill=tk.X, ipady=10)
        setattr(self, attr_name, entry)

    def update_fare_estimate(self, *args):
        """Update the fare estimate in the summary"""
        try:
            idx = self.service_combo.current()
            if idx >= 0 and hasattr(self, 'services_list'):
                service = self.services_list[idx]
                base_fare = service[5]
                price_km = service[4]

                distance = float(self.distance_var.get()) if self.distance_var.get() else 0
                distance_cost = distance * price_km
                total = base_fare + distance_cost

                # Apply student discount
                discount = 0
                if self.payment_var.get() == "Student Account":
                    discount = total * 0.15
                    total -= discount
                    self.discount_label.config(text=_t("taxi.booking.student_discount_applied"))
                else:
                    self.discount_label.config(text="")

                self.base_fare_label.config(text=f"{_t('taxi.booking.base_fare')}: £{base_fare:.2f}")
                self.distance_fare_label.config(text=f"{_t('taxi.booking.distance')} ({distance:.1f} km): £{distance_cost:.2f}")
                self.total_label.config(text=f"{_t('taxi.booking.total')}: £{total:.2f}")
        except ValueError:
            pass

    def process_booking(self):
        """Process the booking and create a ticket"""
        # Validate inputs
        name = self.name_entry.get().strip()
        pickup = self.pickup_entry.get().strip()
        dropoff = self.dropoff_entry.get().strip()
        distance_str = self.distance_var.get().strip()
        payment = self.payment_var.get()

        if not all([name, pickup, dropoff, distance_str]):
            messagebox.showerror(_t("taxi.error.validation_error"), _t("taxi.error.fill_all_fields"))
            return

        try:
            distance = float(distance_str)
            if distance <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror(_t("taxi.error.validation_error"), _t("taxi.error.valid_distance"))
            return

        # Get selected service
        idx = self.service_combo.current()
        service = self.services_list[idx]
        service_id = service[0]
        service_name = service[1]
        vehicle_type = service[2]

        # Calculate fare
        base_fare = service[5]
        price_km = service[4]
        total = base_fare + (distance * price_km)

        if payment == "Student Account":
            total *= 0.85  # 15% discount

        # Process student account payment if selected
        if payment == "Student Account" and FINANCE_AVAILABLE:
            student_id = self._get_current_user_student_id()
            if not student_id:
                messagebox.showerror(_t("taxi.error.payment_error"), _t("taxi.error.no_student_account"))
                return

            # Check balance and process payment
            balance = get_student_finance_account_balance(student_id)
            if balance is None:
                messagebox.showerror(_t("taxi.error.payment_error"), _t("taxi.error.account_not_found"))
                return

            if balance < total:
                messagebox.showerror(
                    _t("taxi.error.payment_error"),
                    _t("taxi.error.insufficient_balance", balance=balance, required=total)
                )
                return

        # Create ticket — the domain service takes the fare (student account
        # draw-down or cash/card posting) and writes the booking.
        try:
            ticket_id, ticket_number = self.db.create_ticket(
                service_id, name, pickup, dropoff, distance, total, payment,
                student_id=self._get_current_user_student_id(),
                processed_by=self.current_user.get('username', 'System') if self.current_user else 'System',
            )
        except Exception as exc:
            messagebox.showerror(_t("taxi.error.payment_error"),
                                 _t("taxi.error.payment_failed", default=str(exc)))
            return

        # Send confirmation email
        now = datetime.now()
        ticket_data = {
            'ticket_number': ticket_number,
            'customer_name': name,
            'service_name': service_name,
            'vehicle_type': vehicle_type,
            'pickup': pickup,
            'dropoff': dropoff,
            'distance': distance,
            'total_fare': total,
            'payment_method': payment,
            'status': _t("taxi.status.completed"),
            'date': now.strftime("%Y-%m-%d"),
            'time': now.strftime("%H:%M:%S"),
        }
        email_sent = self._send_booking_confirmation_email(ticket_data)

        # Show receipt
        self.show_receipt(ticket_id, email_sent=email_sent)
