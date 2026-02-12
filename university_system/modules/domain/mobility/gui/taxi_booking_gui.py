"""
Taxi Booking System - A Modern GUI Application
Features:
- Purchase tickets with payment receipts
- View all taxi services
- View all purchased tickets
- Multiple payment methods (Cash, Card, Student Account)
- SQLite database storage (integrated with university system)
- Email confirmation for bookings
- Integration with student finance accounts
- i18n support for multiple languages
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import random
import string
from pathlib import Path
import logging

# Import university system database infrastructure
from university_system.modules.shared.constants import paths
from university_system.infrastructure.database.db import get_db_connection

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)

# Import authentication
from university_system.infrastructure.shared_context import get_auth, get_current_user

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import email template utilities
try:
    from university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Import finance integration for student account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        get_student_finance_account_balance,
        process_student_finance_account_payment,
        get_student_info,
        get_student_email,
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)

class Database:
    """Handle all database operations using university system database"""

    def __init__(self):
        self.db_path = paths.DEFAULT_DB_PATH
        self.init_database()

    def get_connection(self):
        return get_db_connection()
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create taxi booking services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taxi_booking_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                price_per_km REAL NOT NULL,
                base_fare REAL NOT NULL,
                description TEXT,
                available INTEGER DEFAULT 1
            )
        ''')

        # Create taxi booking tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taxi_booking_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                pickup_location TEXT NOT NULL,
                dropoff_location TEXT NOT NULL,
                distance_km REAL NOT NULL,
                total_fare REAL NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT DEFAULT 'Completed',
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                FOREIGN KEY (service_id) REFERENCES taxi_booking_services (id)
            )
        ''')

        # Insert default taxi services if none exist
        cursor.execute("SELECT COUNT(*) FROM taxi_booking_services")
        if cursor.fetchone()[0] == 0:
            default_services = [
                ("City Express", "Sedan", 4, 2.50, 5.00, "Comfortable city rides with AC"),
                ("Premium Luxury", "SUV", 6, 4.00, 10.00, "Luxury SUV for premium travel"),
                ("Budget Saver", "Hatchback", 4, 1.75, 3.00, "Affordable rides for short trips"),
                ("Family Van", "Minivan", 8, 3.50, 8.00, "Spacious van for family outings"),
                ("Eco Green", "Electric", 4, 2.00, 4.00, "Eco-friendly electric vehicle"),
                ("Executive Class", "Luxury Sedan", 4, 5.00, 15.00, "Top-tier business class service"),
                ("Airport Shuttle", "Van", 10, 3.00, 20.00, "Dedicated airport transfers"),
                ("Night Owl", "Sedan", 4, 3.00, 7.00, "24/7 night service with safety features"),
            ]
            cursor.executemany('''
                INSERT INTO taxi_booking_services (service_name, vehicle_type, capacity, price_per_km, base_fare, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', default_services)

        conn.commit()
        conn.close()
    
    def get_all_services(self):
        """Get all available taxi services"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM taxi_booking_services WHERE available = 1")
        services = cursor.fetchall()
        conn.close()
        return services

    def get_service_by_id(self, service_id):
        """Get a specific service by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM taxi_booking_services WHERE id = ?", (service_id,))
        service = cursor.fetchone()
        conn.close()
        return service

    def create_ticket(self, service_id, customer_name, pickup, dropoff, distance, total_fare, payment_method):
        """Create a new ticket"""
        conn = self.get_connection()
        cursor = conn.cursor()

        ticket_number = self.generate_ticket_number()
        now = datetime.now()

        cursor.execute('''
            INSERT INTO taxi_booking_tickets (ticket_number, service_id, customer_name, pickup_location,
                               dropoff_location, distance_km, total_fare, payment_method,
                               booking_date, booking_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_number, service_id, customer_name, pickup, dropoff, distance,
              total_fare, payment_method, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")))

        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return ticket_id, ticket_number

    def get_all_tickets(self):
        """Get all tickets with service details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.service_name, s.vehicle_type
            FROM taxi_booking_tickets t
            JOIN taxi_booking_services s ON t.service_id = s.id
            ORDER BY t.id DESC
        ''')
        tickets = cursor.fetchall()
        conn.close()
        return tickets

    def get_ticket_by_id(self, ticket_id):
        """Get a specific ticket with full details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.service_name, s.vehicle_type, s.description
            FROM taxi_booking_tickets t
            JOIN taxi_booking_services s ON t.service_id = s.id
            WHERE t.id = ?
        ''', (ticket_id,))
        ticket = cursor.fetchone()
        conn.close()
        return ticket
    
    @staticmethod
    def generate_ticket_number():
        """Generate a unique ticket number"""
        prefix = "TXI"
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}-{timestamp}-{random_suffix}"

class ModernStyle:
    """Modern styling configuration"""
    
    # Color palette - Warm amber and slate theme
    BG_PRIMARY = "#1a1a2e"
    BG_SECONDARY = "#16213e"
    BG_CARD = "#0f3460"
    ACCENT = "#e94560"
    ACCENT_HOVER = "#ff6b6b"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0aec0"
    SUCCESS = "#48bb78"
    WARNING = "#f6ad55"
    BORDER = "#2d3748"
    
    # Fonts
    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = (FONT_FAMILY, 24, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_SMALL = (FONT_FAMILY, 10)
    FONT_BUTTON = (FONT_FAMILY, 11, "bold")

class TaxiBookingApp:
    """Main application class"""

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
        style.theme_use('clam')
        
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

        self.payment_var = tk.StringVar(value="Cash")
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

            # Process the payment
            payment_result = process_student_finance_account_payment(
                student_id=student_id,
                amount=total,
                description=f"Taxi booking: {pickup} to {dropoff}",
                transaction_source="TaxiBooking",
                transaction_ref=f"TAXI-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=self.current_user.get('username', 'System') if self.current_user else 'System'
            )

            if not payment_result.get('success'):
                messagebox.showerror(
                    _t("taxi.error.payment_error"),
                    payment_result.get('message', _t("taxi.error.payment_failed"))
                )
                return

        # Create ticket
        ticket_id, ticket_number = self.db.create_ticket(
            service_id, name, pickup, dropoff, distance, total, payment
        )

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
    
    def show_receipt(self, ticket_id, email_sent=False):
        """Show the payment receipt"""
        ticket = self.db.get_ticket_by_id(ticket_id)

        if not ticket:
            messagebox.showerror(_t("common.error"), _t("taxi.error.ticket_not_found"))
            return

        # Unpack ticket data
        (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
         total, payment, status, date, time, service_name, vehicle, desc) = ticket

        # Create receipt window
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title(_t("taxi.receipt.title"))
        receipt_window.geometry("500x700")
        receipt_window.configure(bg=ModernStyle.BG_PRIMARY)
        receipt_window.resizable(False, False)

        # Receipt container
        receipt_frame = tk.Frame(receipt_window, bg="white", padx=30, pady=30)
        receipt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        tk.Label(receipt_frame, text=f"🚕 {_t('taxi.app_name')}", font=("Segoe UI", 24, "bold"),
                bg="white", fg=ModernStyle.BG_SECONDARY).pack()
        tk.Label(receipt_frame, text=_t("taxi.receipt.payment_receipt"), font=("Segoe UI", 12),
                bg="white", fg="gray").pack()

        # Separator
        tk.Frame(receipt_frame, bg="#e0e0e0", height=2).pack(fill=tk.X, pady=15)

        # Ticket number
        tk.Label(receipt_frame, text=f"{_t('taxi.receipt.ticket')}: {ticket_num}", font=("Courier", 14, "bold"),
                bg="white", fg=ModernStyle.BG_SECONDARY).pack()

        # Date/Time
        tk.Label(receipt_frame, text=f"{date} {_t('taxi.email.at')} {time}", font=("Segoe UI", 10),
                bg="white", fg="gray").pack(pady=(0, 15))

        # Details
        details = [
            (_t("taxi.receipt.customer"), customer),
            (_t("taxi.receipt.service"), f"{service_name} ({vehicle})"),
            (_t("taxi.receipt.pickup"), pickup),
            (_t("taxi.receipt.dropoff"), dropoff),
            (_t("taxi.receipt.distance"), f"{distance:.1f} km"),
            (_t("taxi.receipt.payment"), payment),
            (_t("taxi.receipt.status"), status),
        ]

        for label, value in details:
            row = tk.Frame(receipt_frame, bg="white")
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 10), bg="white",
                    fg="gray", width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                    bg="white", fg="#333").pack(side=tk.LEFT)

        # Separator
        tk.Frame(receipt_frame, bg="#e0e0e0", height=2).pack(fill=tk.X, pady=15)

        # Total
        total_frame = tk.Frame(receipt_frame, bg="white")
        total_frame.pack(fill=tk.X)
        tk.Label(total_frame, text=_t("taxi.receipt.total_paid"), font=("Segoe UI", 12),
                bg="white", fg="gray").pack(side=tk.LEFT)
        tk.Label(total_frame, text=f"£{total:.2f}", font=("Segoe UI", 24, "bold"),
                bg="white", fg=ModernStyle.SUCCESS).pack(side=tk.RIGHT)

        if payment == "Student Account":
            tk.Label(receipt_frame, text=_t("taxi.booking.student_discount_applied"),
                    font=("Segoe UI", 10), bg="white", fg=ModernStyle.WARNING).pack(pady=5)

        # Email confirmation status
        if email_sent:
            tk.Label(receipt_frame, text=f"📧 {_t('taxi.receipt.email_sent')}",
                    font=("Segoe UI", 10), bg="white", fg=ModernStyle.SUCCESS).pack(pady=5)

        # Thank you message
        tk.Label(receipt_frame, text=_t("taxi.receipt.thank_you"),
                font=("Segoe UI", 11, "italic"), bg="white", fg="gray").pack(pady=20)

        # Buttons
        btn_frame = tk.Frame(receipt_frame, bg="white")
        btn_frame.pack(fill=tk.X, pady=10)

        # Save receipt button
        save_btn = tk.Button(btn_frame, text=f"💾 {_t('taxi.receipt.save_receipt')}", font=ModernStyle.FONT_BUTTON,
                            bg=ModernStyle.ACCENT, fg="white", bd=0, padx=20, pady=10,
                            cursor="hand2", command=lambda: self.save_receipt(ticket))
        save_btn.pack(side=tk.LEFT, expand=True, padx=5)

        # Close button
        close_btn = tk.Button(btn_frame, text=_t("common.close"), font=ModernStyle.FONT_BUTTON,
                             bg=ModernStyle.BG_CARD, fg="white", bd=0, padx=20, pady=10,
                             cursor="hand2", command=receipt_window.destroy)
        close_btn.pack(side=tk.RIGHT, expand=True, padx=5)
    
    def save_receipt(self, ticket):
        """Save receipt to a text file"""
        (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
         total, payment, status, date, time, service_name, vehicle, desc) = ticket

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_t("taxi.file.text_files"), "*.txt")],
            initialfile=f"TaxiGo_Receipt_{ticket_num}.txt"
        )

        if filename:
            receipt_text = f"""
╔══════════════════════════════════════════════════════════╗
║                    🚕 {_t('taxi.app_name'):<36}║
║                  {_t('taxi.receipt.payment_receipt'):<40}║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.ticket_number')}: {ticket_num:<40} ║
║  {_t('common.date')}: {date:<49} ║
║  {_t('common.time')}: {time:<49} ║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.trip_details'):<54} ║
║  {_t('taxi.receipt.customer')}:    {customer:<42} ║
║  {_t('taxi.receipt.service')}:     {service_name} ({vehicle}){' ' * (42 - len(service_name) - len(vehicle) - 3)}║
║  {_t('taxi.receipt.pickup')}:      {pickup:<42} ║
║  {_t('taxi.receipt.dropoff')}:     {dropoff:<42} ║
║  {_t('taxi.receipt.distance')}:    {distance:.1f} km{' ' * (39 - len(f'{distance:.1f}'))}║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.payment_section'):<54} ║
║  {_t('taxi.receipt.method')}:      {payment:<42} ║
║  {_t('taxi.receipt.status')}:      {status:<42} ║
║                                                           ║
║  {_t('taxi.receipt.total_paid')}:  £{total:.2f}{' ' * (40 - len(f'{total:.2f}'))}║
╠══════════════════════════════════════════════════════════╣
║         {_t('taxi.receipt.thank_you'):<47} ║
║              {_t('taxi.receipt.safe_journey')} 🚕                       ║
╚══════════════════════════════════════════════════════════╝
"""
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(receipt_text)

            messagebox.showinfo(_t("common.success"), _t("taxi.receipt.saved_to", filename=filename))
    
    def show_tickets_view(self):
        """Display all purchased tickets"""
        self.clear_content()

        self.create_header(_t("taxi.tickets.title"), _t("taxi.tickets.subtitle"))

        # Tickets table container
        table_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_CARD)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Create Treeview
        columns = ("ticket", "service", "customer", "route", "distance", "fare", "payment", "date")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                           style="Custom.Treeview", height=20)

        # Define headings
        headings = {
            "ticket": (_t("taxi.tickets.ticket_num"), 150),
            "service": (_t("taxi.tickets.service"), 120),
            "customer": (_t("taxi.tickets.customer"), 120),
            "route": (_t("taxi.tickets.route"), 200),
            "distance": (_t("taxi.tickets.distance"), 80),
            "fare": (_t("taxi.tickets.fare"), 80),
            "payment": (_t("taxi.tickets.payment"), 120),
            "date": (_t("taxi.tickets.date"), 100)
        }
        
        for col, (heading, width) in headings.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center")
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Load tickets
        tickets = self.db.get_all_tickets()

        for ticket in tickets:
            (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
             total, payment, status, date, time, service_name, vehicle) = ticket

            route = f"{pickup[:15]}... → {dropoff[:15]}..." if len(pickup) > 15 or len(dropoff) > 15 else f"{pickup} → {dropoff}"

            tree.insert("", "end", values=(
                ticket_num,
                service_name,
                customer,
                route,
                f"{distance:.1f} km",
                f"£{total:.2f}",
                payment,
                date
            ), tags=(str(t_id),))

        # Bind double-click to view receipt
        tree.bind("<Double-1>", lambda e: self.view_ticket_receipt(tree))

        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        v_scrollbar.grid(row=0, column=1, sticky="ns", pady=10)
        h_scrollbar.grid(row=1, column=0, sticky="ew", padx=10)

        # Configure grid weights
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Info label
        info_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_PRIMARY)
        info_frame.pack(fill=tk.X, pady=10)

        tk.Label(info_frame, text=f"💡 {_t('taxi.tickets.double_click_hint')}",
                font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_PRIMARY,
                fg=ModernStyle.TEXT_SECONDARY).pack()

        # Stats
        if tickets:
            total_spent = sum(t[7] for t in tickets)
            stats_label = tk.Label(info_frame,
                                   text=f"📊 {_t('taxi.tickets.total_bookings')}: {len(tickets)} | {_t('taxi.tickets.total_spent')}: £{total_spent:.2f}",
                                   font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_PRIMARY,
                                   fg=ModernStyle.ACCENT)
            stats_label.pack(pady=5)

        self.tickets_tree = tree
    
    def view_ticket_receipt(self, tree):
        """View receipt for selected ticket"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            ticket_num = item['values'][0]
            
            # Find ticket by number
            tickets = self.db.get_all_tickets()
            for ticket in tickets:
                if ticket[1] == ticket_num:
                    full_ticket = self.db.get_ticket_by_id(ticket[0])
                    self.show_receipt(ticket[0])
                    break

    def show_refunds_view(self):
        """Display refunds management interface"""
        self.clear_content()

        self.create_header(_t("taxi.refunds.title", default="Taxi Booking Refunds"),
                           _t("taxi.refunds.subtitle", default="Process refunds for taxi bookings"))

        # Table container
        table_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_CARD, padx=10, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Search frame
        search_frame = tk.Frame(table_frame, bg=ModernStyle.BG_CARD)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(search_frame, text="🔍", font=("Segoe UI", 14),
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY).pack(side=tk.LEFT, padx=(0, 5))

        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var,
                                font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                                fg=ModernStyle.TEXT_PRIMARY, insertbackground=ModernStyle.TEXT_PRIMARY)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)

        # Buttons frame
        buttons_frame = tk.Frame(table_frame, bg=ModernStyle.BG_CARD)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))

        refresh_btn = self.create_button(buttons_frame, _t("common.refresh", default="Refresh"),
                                          self.refresh_refunds_list)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))

        refund_btn = self.create_button(buttons_frame, _t("taxi.refunds.process_refund", default="Process Refund"),
                                         self.process_taxi_refund, "success")
        refund_btn.pack(side=tk.LEFT, padx=(0, 10))

        export_btn = self.create_button(buttons_frame, _t("common.export", default="Export to CSV"),
                                         self.export_taxi_refunds_to_csv)
        export_btn.pack(side=tk.LEFT)

        # Create Treeview with 8 columns
        columns = ('ticket_id', 'ticket_number', 'date', 'customer', 'route', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                         style="Custom.Treeview", height=20)

        # Define headings and column widths
        headings = {
            'ticket_id': (_t("taxi.refunds.ticket_id", default="Ticket ID"), 80),
            'ticket_number': (_t("taxi.refunds.ticket_number", default="Ticket Number"), 150),
            'date': (_t("common.date", default="Date"), 100),
            'customer': (_t("taxi.refunds.customer", default="Customer"), 120),
            'route': (_t("taxi.refunds.route", default="Route"), 180),
            'amount': (_t("taxi.refunds.amount", default="Amount"), 100),
            'payment_method': (_t("taxi.refunds.payment_method", default="Payment Method"), 130),
            'status': (_t("taxi.refunds.status", default="Status"), 100)
        }

        for col, (heading, width) in headings.items():
            self.refunds_tree.heading(col, text=heading)
            self.refunds_tree.column(col, width=width, anchor='center' if col != 'route' else 'w')

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to view details
        self.refunds_tree.bind('<Double-1>', lambda e: self.view_taxi_ticket_details())

        # Info label
        info_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_PRIMARY)
        info_frame.pack(fill=tk.X, pady=10)

        tk.Label(info_frame, text=f"💡 {_t('taxi.refunds.hint', default='Double-click to view ticket details')}",
                font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_PRIMARY,
                fg=ModernStyle.TEXT_SECONDARY).pack()

        # Search functionality
        def search_refunds(*args):
            search_term = search_var.get().lower()
            for item in self.refunds_tree.get_children():
                values = self.refunds_tree.item(item)['values']
                if search_term in str(values).lower():
                    self.refunds_tree.item(item, tags=())
                else:
                    self.refunds_tree.item(item, tags=('hidden',))
            self.refunds_tree.tag_configure('hidden', foreground='')

        search_var.trace('w', search_refunds)

        # Load refunds
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list from database"""
        if not hasattr(self, 'refunds_tree'):
            return

        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Get all tickets with their status (using payment_status as status indicator)
            cursor.execute('''
                SELECT
                    t.id,
                    t.ticket_number,
                    t.booking_date,
                    t.customer_name,
                    t.pickup_location,
                    t.dropoff_location,
                    t.total_fare,
                    t.payment_method,
                    COALESCE(t.payment_status, 'Completed') as status
                FROM taxi_booking_tickets t
                ORDER BY t.id DESC
            ''')

            tickets = cursor.fetchall()
            conn.close()

            for ticket in tickets:
                ticket_id, ticket_number, date, customer, pickup, dropoff, amount, payment_method, status = ticket

                # Format route
                route = f"{pickup[:20]}... → {dropoff[:20]}..." if len(pickup) > 20 or len(dropoff) > 20 else f"{pickup} → {dropoff}"

                # Determine display status
                display_status = status if status else 'Completed'

                # Color coding based on status
                tag = 'refunded' if 'refund' in display_status.lower() else 'active'

                self.refunds_tree.insert('', 'end', values=(
                    ticket_id,
                    ticket_number,
                    date,
                    customer,
                    route,
                    f"£{amount:.2f}",
                    payment_method,
                    display_status
                ), tags=(tag,))

            # Configure tags for color coding
            self.refunds_tree.tag_configure('active', foreground=ModernStyle.SUCCESS)
            self.refunds_tree.tag_configure('refunded', foreground=ModernStyle.ACCENT)

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_loading", default=f"Error loading tickets: {str(e)}"))

    def process_taxi_refund(self):
        """Process a refund for selected taxi ticket"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.select_ticket", default="Please select a ticket to refund"))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_id = values[0]
        ticket_number = values[1]
        amount_str = values[5]
        status = values[7]

        # Check if already refunded
        if 'refund' in status.lower():
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.already_refunded", default="This ticket has already been refunded"))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except ValueError:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.invalid_amount", default="Invalid amount format"))
            return

        # Show refund method dialog
        self.show_taxi_refund_method_dialog(ticket_id, ticket_number, amount)

    def show_taxi_refund_method_dialog(self, ticket_id, ticket_number, amount):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("taxi.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x450")
        dialog.configure(bg=ModernStyle.BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"500x450+{x}+{y}")

        # Grab focus after window is positioned
        dialog.grab_set()

        # Content frame
        content_frame = tk.Frame(dialog, bg=ModernStyle.BG_CARD, padx=30, pady=30)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        tk.Label(content_frame, text="💸 " + _t("taxi.refunds.process_refund", default="Process Refund"),
                font=ModernStyle.FONT_TITLE, bg=ModernStyle.BG_CARD,
                fg=ModernStyle.TEXT_PRIMARY).pack(pady=(0, 20))

        # Ticket info
        info_frame = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=15)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(info_frame, text=_t("taxi.refunds.ticket_number", default="Ticket Number") + f": {ticket_number}",
                font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY).pack(anchor='w')
        tk.Label(info_frame, text=_t("taxi.refunds.refund_amount", default="Refund Amount") + f": £{amount:.2f}",
                font=("Segoe UI", 14, "bold"), bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.SUCCESS).pack(anchor='w', pady=(5, 0))

        # Instructions
        tk.Label(content_frame, text=_t("taxi.refunds.select_method_instruction", default="Select refund method:"),
                font=ModernStyle.FONT_SUBTITLE, bg=ModernStyle.BG_CARD,
                fg=ModernStyle.TEXT_PRIMARY).pack(anchor='w', pady=(0, 10))

        # Get student account balance if available
        student_balance = None
        student_id = None
        if FINANCE_AVAILABLE and self.current_user:
            student_id = self._get_current_user_student_id()
            if student_id:
                student_balance = get_student_finance_account_balance(student_id)

        # Refund method buttons
        def select_cash():
            dialog.destroy()
            self._complete_taxi_refund(ticket_id, ticket_number, amount, "Cash", student_id)

        def select_card():
            dialog.destroy()
            self._complete_taxi_refund(ticket_id, ticket_number, amount, "Card", student_id)

        def select_student_account():
            dialog.destroy()
            self.add_taxi_refund_to_student_account(ticket_id, ticket_number, amount, student_id)

        # Cash button
        cash_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        cash_btn.pack(fill=tk.X, pady=5)
        tk.Label(cash_btn, text="💵 " + _t("taxi.refunds.cash", default="Cash Refund"),
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()
        cash_btn.bind("<Button-1>", lambda e: select_cash())

        # Card button
        card_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        card_btn.pack(fill=tk.X, pady=5)
        tk.Label(card_btn, text="💳 " + _t("taxi.refunds.card", default="Card Refund"),
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()
        card_btn.bind("<Button-1>", lambda e: select_card())

        # Student account button
        student_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        student_btn.pack(fill=tk.X, pady=5)

        student_text = _t("taxi.refunds.student_account", default="Student Finance Account")
        if student_balance is not None:
            student_text += f" (£{student_balance:.2f})"

        tk.Label(student_btn, text="🎓 " + student_text,
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()

        if student_id and FINANCE_AVAILABLE:
            student_btn.bind("<Button-1>", lambda e: select_student_account())
        else:
            student_btn.configure(bg=ModernStyle.BORDER)
            tk.Label(student_btn, text=_t("taxi.refunds.student_account_unavailable", default="(Not available)"),
                    font=ModernStyle.FONT_SMALL, bg=ModernStyle.BORDER,
                    fg=ModernStyle.TEXT_SECONDARY).pack()

        # Cancel button
        cancel_btn = self.create_button(content_frame, _t("common.cancel", default="Cancel"), dialog.destroy)
        cancel_btn.pack(fill=tk.X, pady=(20, 0))

    def _complete_taxi_refund(self, ticket_id, ticket_number, amount, refund_method, student_id):
        """Complete cash or card refund"""
        try:
            # Generate refund reference
            refund_ref = f"TAXI-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Update ticket status in database
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Update payment_status to indicate refund
            cursor.execute('''
                UPDATE taxi_booking_tickets
                SET payment_status = ?
                WHERE id = ?
            ''', ('Refunded', ticket_id))

            # Create refund record in central database
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS taxi_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    ticket_number TEXT,
                    refund_reference TEXT,
                    amount REAL,
                    refund_method TEXT,
                    refund_date TEXT,
                    refund_time TEXT,
                    processed_by TEXT,
                    student_id TEXT
                )
            ''')

            now = datetime.now()
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'

            cursor.execute('''
                INSERT INTO taxi_refunds (ticket_id, ticket_number, refund_reference, amount,
                                         refund_method, refund_date, refund_time, processed_by, student_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket_id, ticket_number, refund_ref, amount, refund_method,
                  now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), processed_by, student_id))

            conn.commit()
            conn.close()

            # Send refund receipt email
            self.send_taxi_refund_receipt(ticket_number, refund_ref, amount, refund_method, None, None)

            # Notify finance GUI
            self.notify_taxi_finance_gui(refund_ref, amount, refund_method, ticket_number)

            # Show success message
            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.success_message", default=f"Refund processed successfully!\n\nRefund Reference: {refund_ref}\nAmount: £{amount:.2f}\nMethod: {refund_method}"))

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            logger.error(f"Error processing taxi refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_processing", default=f"Error processing refund: {str(e)}"))

    def add_taxi_refund_to_student_account(self, ticket_id, ticket_number, amount, student_id):
        """Add refund to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.finance_unavailable", default="Student finance system is not available"))
            return

        if not student_id:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.no_student_id", default="Student ID not found"))
            return

        try:
            # Generate refund reference
            refund_ref = f"TAXI-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Get current balance
            old_balance = get_student_finance_account_balance(student_id)
            if old_balance is None:
                old_balance = 0.0

            new_balance = old_balance + amount

            # Import finance integration functions
            from university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists

            # Ensure account exists
            ensure_student_finance_account_exists(student_id)

            # Add refund to student account
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Update student account balance
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = balance + ?
                WHERE student_id = ?
            ''', (amount, student_id))

            # Get account_id and new balance
            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?
            ''', (student_id,))
            result = cursor.fetchone()
            if result:
                account_id, new_balance = result
            else:
                account_id, new_balance = None, amount

            # Log transaction
            cursor.execute('''
                INSERT INTO student_finance_transactions
                (account_id, student_id, transaction_type, amount, balance_after, description,
                 reference_id, processed_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, student_id, 'credit', amount, new_balance,
                  f'Taxi booking refund - {refund_ref}',
                  refund_ref,
                  self.current_user.get('username', 'System') if self.current_user else 'System',
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # Update ticket status
            cursor.execute('''
                UPDATE taxi_booking_tickets
                SET payment_status = ?
                WHERE id = ?
            ''', ('Refunded', ticket_id))

            # Create refund record
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS taxi_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    ticket_number TEXT,
                    refund_reference TEXT,
                    amount REAL,
                    refund_method TEXT,
                    refund_date TEXT,
                    refund_time TEXT,
                    processed_by TEXT,
                    student_id TEXT
                )
            ''')

            now = datetime.now()
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'

            cursor.execute('''
                INSERT INTO taxi_refunds (ticket_id, ticket_number, refund_reference, amount,
                                         refund_method, refund_date, refund_time, processed_by, student_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket_id, ticket_number, refund_ref, amount, 'Student Account',
                  now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), processed_by, student_id))

            conn.commit()
            conn.close()

            # Send refund receipt email
            self.send_taxi_refund_receipt(ticket_number, refund_ref, amount, 'Student Account',
                                          old_balance, new_balance)

            # Notify finance GUI
            self.notify_taxi_finance_gui(refund_ref, amount, 'Student Account', ticket_number)

            # Show success message
            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.student_account_success", default=f"Refund added to student account!\n\nRefund Reference: {refund_ref}\nAmount: £{amount:.2f}\n\nOld Balance: £{old_balance:.2f}\nNew Balance: £{new_balance:.2f}"))

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            logger.error(f"Error adding taxi refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_student_account", default=f"Error adding refund to student account: {str(e)}"))

    def send_taxi_refund_receipt(self, ticket_number, refund_ref, amount, refund_method, old_balance, new_balance):
        """Send refund receipt via email"""
        if not EMAIL_AVAILABLE:
            logger.warning("Email service not available")
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
                logger.warning("No email address found for refund receipt")
                return False

            # Build email content
            customer_name = self.current_user.get('full_name', 'Valued Customer') if self.current_user else 'Valued Customer'

            # Try to use template first, fall back to i18n-based email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('taxi_refund_receipt', {
                        'customer_name': customer_name,
                        'booking_id': ticket_number,
                        'refund_amount': f"{amount:.2f}",
                        'refund_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'payment_method': refund_method,
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using i18n-based email.")
                # Fallback to i18n-based email
                subject = _t("taxi.refunds.email_subject", default=f"Taxi Booking Refund Receipt - {refund_ref}")
                body = f"""{_t("common.dear", default="Dear")} {customer_name},

{_t("taxi.refunds.email_intro", default="Your taxi booking refund has been processed successfully.")}

═══════════════════════════════════════════════════════
                {_t("taxi.refunds.email_details", default="REFUND DETAILS")}
═══════════════════════════════════════════════════════

{_t("taxi.refunds.refund_reference", default="Refund Reference")}: {refund_ref}
{_t("taxi.refunds.ticket_number", default="Ticket Number")}: {ticket_number}
{_t("taxi.refunds.refund_amount", default="Refund Amount")}: £{amount:.2f}
{_t("taxi.refunds.refund_method", default="Refund Method")}: {refund_method}
{_t("common.date", default="Date")}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

                if old_balance is not None and new_balance is not None:
                    body += f"""
{_t("taxi.refunds.email_balance_section", default="ACCOUNT BALANCE")}:
────────────────────────────────────────
{_t("taxi.refunds.previous_balance", default="Previous Balance")}: £{old_balance:.2f}
{_t("taxi.refunds.refund_amount", default="Refund Amount")}: £{amount:.2f}
{_t("taxi.refunds.new_balance", default="New Balance")}: £{new_balance:.2f}
"""

                body += f"""
═══════════════════════════════════════════════════════

{_t("taxi.refunds.email_footer", default="If you have any questions about this refund, please contact our support team.")}

{_t("common.thank_you", default="Thank you")},
TaxiGo - {_t("taxi.subtitle", default="Your Campus Ride")}

---
{_t("common.auto_message", default="This is an automated message. Please do not reply.")}
"""

            result = send_email(user_email, subject, body)
            if result:
                logger.info(f"Refund receipt email sent to {user_email}")
                return True
            else:
                logger.warning(f"Failed to send refund receipt email to {user_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending refund receipt email: {e}")
            return False

    def notify_taxi_finance_gui(self, refund_ref, amount, refund_method, ticket_number):
        """Notify finance GUI about the refund"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Create finance_refunds table if not exists (matching actual schema)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    refund_reference TEXT,
                    department TEXT,
                    transaction_id TEXT,
                    amount DECIMAL(10,2),
                    refund_method TEXT,
                    refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    notes TEXT
                )
            ''')

            now = datetime.now()
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'

            cursor.execute('''
                INSERT INTO finance_refunds (refund_reference, department, transaction_id, amount,
                                            refund_method, refund_date, processed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (refund_ref, 'Taxi Booking', ticket_number, amount,
                  refund_method, now.strftime("%Y-%m-%d %H:%M:%S"),
                  processed_by, f'Taxi booking refund for ticket {ticket_number}'))

            conn.commit()
            conn.close()

            logger.info(f"Finance GUI notified about refund: {refund_ref}")
            return True

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")
            return False

    def view_taxi_ticket_details(self):
        """View detailed information about selected ticket"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.select_ticket_details", default="Please select a ticket to view details"))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_id = values[0]

        try:
            # Get full ticket details
            ticket = self.db.get_ticket_by_id(ticket_id)
            if not ticket:
                messagebox.showerror(_t("common.error", default="Error"),
                                     _t("taxi.refunds.ticket_not_found", default="Ticket not found"))
                return

            # Unpack ticket data
            (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
             total, payment, status, date, time, service_name, vehicle, desc) = ticket

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(_t("taxi.refunds.ticket_details", default="Ticket Details"))
            details_window.geometry("600x700")
            details_window.configure(bg=ModernStyle.BG_PRIMARY)
            details_window.transient(self.root)

            # Center window
            details_window.update_idletasks()
            x = (details_window.winfo_screenwidth() // 2) - (600 // 2)
            y = (details_window.winfo_screenheight() // 2) - (700 // 2)
            details_window.geometry(f"600x700+{x}+{y}")

            # Create scrollable frame
            canvas = tk.Canvas(details_window, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
            scrollbar = tk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Content frame
            content_frame = tk.Frame(scrollable_frame, bg=ModernStyle.BG_CARD, padx=30, pady=30)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            tk.Label(content_frame, text="🚕 " + _t("taxi.refunds.ticket_details", default="Ticket Details"),
                    font=ModernStyle.FONT_TITLE, bg=ModernStyle.BG_CARD,
                    fg=ModernStyle.TEXT_PRIMARY).pack(pady=(0, 20))

            # Ticket information
            details_data = [
                (_t("taxi.refunds.ticket_number", default="Ticket Number"), ticket_num),
                (_t("common.date", default="Date"), f"{date} {time}"),
                (_t("taxi.refunds.customer", default="Customer"), customer),
                ("", ""),  # Separator
                (_t("taxi.refunds.trip_info", default="TRIP INFORMATION"), ""),
                (_t("taxi.refunds.service", default="Service"), f"{service_name} ({vehicle})"),
                (_t("taxi.refunds.description", default="Description"), desc or "N/A"),
                (_t("taxi.refunds.pickup", default="Pickup Location"), pickup),
                (_t("taxi.refunds.dropoff", default="Dropoff Location"), dropoff),
                (_t("taxi.refunds.distance", default="Distance"), f"{distance:.1f} km"),
                ("", ""),  # Separator
                (_t("taxi.refunds.payment_info", default="PAYMENT INFORMATION"), ""),
                (_t("taxi.refunds.total_fare", default="Total Fare"), f"£{total:.2f}"),
                (_t("taxi.refunds.payment_method", default="Payment Method"), payment),
                (_t("taxi.refunds.status", default="Status"), status),
            ]

            for label, value in details_data:
                if label == "":
                    # Separator
                    tk.Frame(content_frame, bg=ModernStyle.BORDER, height=1).pack(fill=tk.X, pady=10)
                elif value == "":
                    # Section header
                    tk.Label(content_frame, text=label, font=ModernStyle.FONT_SUBTITLE,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.ACCENT).pack(anchor='w', pady=(10, 5))
                else:
                    # Regular field
                    row = tk.Frame(content_frame, bg=ModernStyle.BG_CARD)
                    row.pack(fill=tk.X, pady=3)
                    tk.Label(row, text=label + ":", font=ModernStyle.FONT_BODY,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY,
                            width=20, anchor='w').pack(side=tk.LEFT)
                    tk.Label(row, text=value, font=ModernStyle.FONT_BODY,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
                            wraplength=350, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Close button
            close_btn = self.create_button(content_frame, _t("common.close", default="Close"),
                                            details_window.destroy)
            close_btn.pack(fill=tk.X, pady=(20, 0))

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Bind mousewheel
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        except Exception as e:
            logger.error(f"Error viewing ticket details: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_viewing_details", default=f"Error viewing details: {str(e)}"))

    def export_taxi_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[(_t("common.csv_files", default="CSV Files"), "*.csv")],
                initialfile=f"Taxi_Refunds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            import csv

            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    t.id,
                    t.ticket_number,
                    t.booking_date,
                    t.booking_time,
                    t.customer_name,
                    t.pickup_location,
                    t.dropoff_location,
                    t.distance_km,
                    t.total_fare,
                    t.payment_method,
                    COALESCE(t.payment_status, 'Completed') as status,
                    s.service_name,
                    s.vehicle_type
                FROM taxi_booking_tickets t
                LEFT JOIN taxi_booking_services s ON t.service_id = s.id
                ORDER BY t.id DESC
            ''')

            tickets = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    _t("taxi.refunds.ticket_id", default="Ticket ID"),
                    _t("taxi.refunds.ticket_number", default="Ticket Number"),
                    _t("common.date", default="Date"),
                    _t("common.time", default="Time"),
                    _t("taxi.refunds.customer", default="Customer"),
                    _t("taxi.refunds.pickup", default="Pickup Location"),
                    _t("taxi.refunds.dropoff", default="Dropoff Location"),
                    _t("taxi.refunds.distance", default="Distance (km)"),
                    _t("taxi.refunds.amount", default="Amount"),
                    _t("taxi.refunds.payment_method", default="Payment Method"),
                    _t("taxi.refunds.status", default="Status"),
                    _t("taxi.refunds.service", default="Service"),
                    _t("taxi.refunds.vehicle_type", default="Vehicle Type")
                ])

                # Write data
                for ticket in tickets:
                    writer.writerow(ticket)

            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.export_success", default=f"Refunds exported successfully to:\n{filename}"))

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.export_error", default=f"Error exporting to CSV: {str(e)}"))

def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Center window on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 1200) // 2
    y = (screen_height - 800) // 2
    root.geometry(f"1200x800+{x}+{y}")
    
    app = TaxiBookingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
