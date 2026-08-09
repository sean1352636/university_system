"""Methods __init__ through show_services_view."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TaxiBookingApp:
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("taxi.title"))
        self.root.geometry("1400x800")
        self.root.minsize(1000, 700)
        self.root.configure(bg=ModernStyle.BG_PRIMARY)

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

        # Selected service for booking
        self.selected_service = None

        # Configure styles
        self.configure_styles()

        # Build UI
        self.build_ui()

        # Show services view by default
        self.show_services_view()

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
            logger.warning(_t("taxi.email.service_unavailable"))
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
                logger.warning(_t("taxi.email.no_email_found"))
                return False

            # Build email content
            customer_name = ticket_data.get('customer_name', _t("taxi.email.valued_customer"))

            # Try to use template first, fall back to i18n-based email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('taxi_booking_confirmation', {
                        'customer_name': customer_name,
                        'booking_id': ticket_data['ticket_number'],
                        'pickup_location': ticket_data['pickup'],
                        'destination': ticket_data['dropoff'],
                        'pickup_date': ticket_data['date'],
                        'pickup_time': ticket_data['time'],
                        'fare': f"{ticket_data['total_fare']:.2f}",
                        'payment_method': ticket_data['payment_method'],
                        'driver_name': ticket_data.get('driver_name', 'TBD'),
                        'vehicle_reg': ticket_data.get('vehicle_reg', 'TBD')
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using i18n-based email.")
                # Fallback to i18n-based email
                subject = _t("taxi.email.subject", ticket_number=ticket_data['ticket_number'])
                body = f"""{_t("taxi.email.greeting", name=customer_name)}

{_t("taxi.email.confirmation_message")}

═══════════════════════════════════════════════════════
                    {_t("taxi.email.booking_details")}
═══════════════════════════════════════════════════════

{_t("taxi.email.ticket_number")}: {ticket_data['ticket_number']}
{_t("taxi.email.booking_date")}: {ticket_data['date']} {_t("taxi.email.at")} {ticket_data['time']}

{_t("taxi.email.trip_details")}:
────────────────────────────────────────
{_t("taxi.email.service")}: {ticket_data['service_name']} ({ticket_data['vehicle_type']})
{_t("taxi.email.pickup")}: {ticket_data['pickup']}
{_t("taxi.email.dropoff")}: {ticket_data['dropoff']}
{_t("taxi.email.distance")}: {ticket_data['distance']:.1f} km

{_t("taxi.email.payment_details")}:
────────────────────────────────────────
{_t("taxi.email.payment_method")}: {ticket_data['payment_method']}
{_t("taxi.email.total_fare")}: £{ticket_data['total_fare']:.2f}
{_t("taxi.email.status")}: {ticket_data['status']}

═══════════════════════════════════════════════════════

{_t("taxi.email.thank_you")}

{_t("taxi.email.signature")}
TaxiGo - {_t("taxi.subtitle")}

---
{_t("taxi.email.auto_message")}
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

    def configure_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()

        # Configure Treeview
        style.configure("Custom.Treeview",
                        background=ModernStyle.BG_CARD,
                        foreground=ModernStyle.TEXT_PRIMARY,
                        fieldbackground=ModernStyle.BG_CARD,
                        borderwidth=0,
                        font=ModernStyle.FONT_BODY)
        style.configure("Custom.Treeview.Heading",
                        background=ModernStyle.BG_SECONDARY,
                        foreground=ModernStyle.ACCENT,
                        font=ModernStyle.FONT_SUBTITLE,
                        borderwidth=0)
        style.map("Custom.Treeview",
                  background=[('selected', ModernStyle.ACCENT)],
                  foreground=[('selected', ModernStyle.TEXT_PRIMARY)])

    def build_ui(self):
        """Build the main user interface"""
        # Main container
        self.main_container = tk.Frame(self.root, bg=ModernStyle.BG_PRIMARY)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.build_sidebar()

        # Content area
        self.content_frame = tk.Frame(self.main_container, bg=ModernStyle.BG_PRIMARY)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)

    def build_sidebar(self):
        """Build the navigation sidebar"""
        sidebar = tk.Frame(self.main_container, bg=ModernStyle.BG_SECONDARY, width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Logo/Title section
        logo_frame = tk.Frame(sidebar, bg=ModernStyle.BG_SECONDARY)
        logo_frame.pack(fill=tk.X, pady=30)

        logo_label = tk.Label(logo_frame, text="🚕", font=("Segoe UI", 48),
                              bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.ACCENT)
        logo_label.pack()

        title_label = tk.Label(logo_frame, text=_t("taxi.app_name"), font=ModernStyle.FONT_TITLE,
                               bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY)
        title_label.pack()

        subtitle_label = tk.Label(logo_frame, text=_t("taxi.subtitle"), font=ModernStyle.FONT_SMALL,
                                  bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY)
        subtitle_label.pack()

        # Show current user if logged in
        if self.current_user:
            user_frame = tk.Frame(sidebar, bg=ModernStyle.BG_SECONDARY)
            user_frame.pack(fill=tk.X, pady=5)
            user_label = tk.Label(user_frame,
                                  text=f"👤 {self.current_user.get('full_name', '')}",
                                  font=ModernStyle.FONT_SMALL,
                                  bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.SUCCESS)
            user_label.pack()

            # Show student account balance if available
            if FINANCE_AVAILABLE:
                student_id = self._get_current_user_student_id()
                if student_id:
                    balance = get_student_finance_account_balance(student_id)
                    if balance is not None:
                        balance_label = tk.Label(user_frame,
                                                 text=f"💰 {_t('taxi.balance')}: £{balance:.2f}",
                                                 font=ModernStyle.FONT_SMALL,
                                                 bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.WARNING)
                        balance_label.pack()

        # Separator
        sep = tk.Frame(sidebar, bg=ModernStyle.BORDER, height=1)
        sep.pack(fill=tk.X, padx=20, pady=20)

        # Navigation buttons
        nav_buttons = [
            (f"📋  {_t('taxi.nav.view_services')}", self.show_services_view),
            (f"🎫  {_t('taxi.nav.book_ride')}", self.show_booking_view),
            (f"📜  {_t('taxi.nav.my_tickets')}", self.show_tickets_view),
            (f"💸  {_t('taxi.nav.refunds', default='Refunds')}", self.show_refunds_view),
        ]

        self.nav_btn_frames = []
        for text, command in nav_buttons:
            btn_frame = tk.Frame(sidebar, bg=ModernStyle.BG_SECONDARY)
            btn_frame.pack(fill=tk.X, padx=15, pady=5)

            btn = tk.Label(btn_frame, text=text, font=ModernStyle.FONT_BUTTON,
                          bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY,
                          cursor="hand2", pady=12, padx=15, anchor="w")
            btn.pack(fill=tk.X)

            # Bind hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=ModernStyle.BG_CARD))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=ModernStyle.BG_SECONDARY))
            btn.bind("<Button-1>", lambda e, cmd=command: cmd())

            self.nav_btn_frames.append(btn_frame)

        # Footer
        footer_frame = tk.Frame(sidebar, bg=ModernStyle.BG_SECONDARY)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        footer_text = tk.Label(footer_frame, text=_t("taxi.footer"),
                               font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_SECONDARY,
                               fg=ModernStyle.TEXT_SECONDARY, justify=tk.CENTER)
        footer_text.pack()

    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def create_header(self, title, subtitle=""):
        """Create a header section"""
        header_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_PRIMARY)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        title_label = tk.Label(header_frame, text=title, font=ModernStyle.FONT_TITLE,
                               bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY)
        title_label.pack(anchor="w")

        if subtitle:
            subtitle_label = tk.Label(header_frame, text=subtitle, font=ModernStyle.FONT_BODY,
                                      bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY)
            subtitle_label.pack(anchor="w")

        return header_frame

    def create_button(self, parent, text, command, style="primary"):
        """Create a styled button"""
        if style == "primary":
            bg = ModernStyle.ACCENT
            fg = ModernStyle.TEXT_PRIMARY
            hover_bg = ModernStyle.ACCENT_HOVER
        elif style == "success":
            bg = ModernStyle.SUCCESS
            fg = ModernStyle.TEXT_PRIMARY
            hover_bg = "#38a169"
        else:
            bg = ModernStyle.BG_CARD
            fg = ModernStyle.TEXT_PRIMARY
            hover_bg = ModernStyle.BG_SECONDARY

        btn = tk.Label(parent, text=text, font=ModernStyle.FONT_BUTTON,
                      bg=bg, fg=fg, cursor="hand2", pady=10, padx=20)
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        btn.bind("<Button-1>", lambda e: command())

        return btn

    def show_services_view(self):
        """Display all available taxi services"""
        self.clear_content()

        self.create_header(_t("taxi.services.title"), _t("taxi.services.subtitle"))

        # Services container with scrollable frame
        canvas = tk.Canvas(self.content_frame, bg=ModernStyle.BG_PRIMARY,
                          highlightthickness=0)
        scrollbar = tk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Grid of service cards
        services = self.db.get_all_services()

        for i, service in enumerate(services):
            row = i // 2
            col = i % 2

            self.create_service_card(scrollable_frame, service, row, col)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
