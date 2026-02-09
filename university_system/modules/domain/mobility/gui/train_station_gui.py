#!/usr/bin/env python3
"""
Train Station GUI Application
Features:
- Purchase tickets with payment receipt
- View all train services
- View all purchased tickets
- Multiple payment methods (Cash, Card, Student Account)
- SQLite database storage (integrated with university system)
- Email confirmation for bookings
- Integration with student finance accounts
- i18n support for multiple languages
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import sqlite3
import random
import string
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
        self.create_tables()
        self.populate_sample_services()

    def get_connection(self):
        """Get database connection"""
        return get_db_connection()

    def create_tables(self):
        """Create necessary database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Train station services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_number TEXT UNIQUE NOT NULL,
                departure_station TEXT NOT NULL,
                arrival_station TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                price REAL NOT NULL,
                available_seats INTEGER NOT NULL
            )
        ''')

        # Train station tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                passenger_name TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                price_paid REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                FOREIGN KEY (service_id) REFERENCES train_station_services (id)
            )
        ''')

        # Train station receipts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_number TEXT UNIQUE NOT NULL,
                ticket_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES train_station_tickets (id)
            )
        ''')

        # Train refunds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT NOT NULL,
                student_id TEXT,
                amount DECIMAL(10,2) NOT NULL,
                refund_method TEXT NOT NULL,
                refund_reference TEXT,
                refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def populate_sample_services(self):
        """Add sample train services if table is empty"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM train_station_services")
        if cursor.fetchone()[0] == 0:
            services = [
                ("EXP001", "London Kings Cross", "Edinburgh", "06:00", "10:30", 89.50, 150),
                ("EXP002", "London Euston", "Manchester", "07:15", "09:30", 65.00, 200),
                ("EXP003", "London Paddington", "Bristol", "08:00", "09:45", 45.00, 180),
                ("EXP004", "London Victoria", "Brighton", "09:30", "10:30", 25.00, 250),
                ("EXP005", "London St Pancras", "Paris", "10:00", "13:00", 120.00, 300),
                ("REG001", "Birmingham", "Liverpool", "11:00", "13:15", 35.00, 120),
                ("REG002", "Leeds", "Sheffield", "12:30", "13:15", 18.50, 100),
                ("REG003", "Glasgow", "Edinburgh", "14:00", "15:00", 22.00, 90),
                ("EXP006", "Newcastle", "London Kings Cross", "15:30", "18:45", 95.00, 175),
                ("REG004", "Cardiff", "Swansea", "16:00", "17:00", 15.00, 80),
            ]
            cursor.executemany('''
                INSERT INTO train_station_services
                (service_number, departure_station, arrival_station, departure_time, arrival_time, price, available_seats)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', services)
            conn.commit()
        conn.close()

    def get_all_services(self):
        """Retrieve all train services"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, service_number, departure_station, arrival_station,
                   departure_time, arrival_time, price, available_seats
            FROM train_station_services
        ''')
        result = cursor.fetchall()
        conn.close()
        return result

    def get_service_by_id(self, service_id):
        """Get a specific service by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM train_station_services WHERE id = ?", (service_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def purchase_ticket(self, service_id, passenger_name, payment_method, price_paid):
        """Create a new ticket purchase"""
        conn = self.get_connection()
        cursor = conn.cursor()

        ticket_number = "TKT" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO train_station_tickets (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date))

        ticket_id = cursor.lastrowid

        # Update available seats
        cursor.execute('''
            UPDATE train_station_services SET available_seats = available_seats - 1 WHERE id = ?
        ''', (service_id,))

        # Create receipt
        receipt_number = "RCP" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute('''
            INSERT INTO train_station_receipts (receipt_number, ticket_id, total_amount, payment_method, transaction_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (receipt_number, ticket_id, price_paid, payment_method, purchase_date))

        conn.commit()
        conn.close()
        return ticket_number, receipt_number

    def get_all_tickets(self):
        """Retrieve all purchased tickets with service details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.ticket_number, t.passenger_name, ts.service_number,
                   ts.departure_station, ts.arrival_station, ts.departure_time,
                   t.payment_method, t.price_paid, t.purchase_date
            FROM train_station_tickets t
            JOIN train_station_services ts ON t.service_id = ts.id
            ORDER BY t.purchase_date DESC
        ''')
        result = cursor.fetchall()
        conn.close()
        return result

    def get_receipt(self, ticket_number):
        """Get receipt for a specific ticket"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.receipt_number, r.total_amount, r.payment_method, r.transaction_date,
                   t.ticket_number, t.passenger_name, ts.service_number,
                   ts.departure_station, ts.arrival_station, ts.departure_time, ts.arrival_time
            FROM train_station_receipts r
            JOIN train_station_tickets t ON r.ticket_id = t.id
            JOIN train_station_services ts ON t.service_id = ts.id
            WHERE t.ticket_number = ?
        ''', (ticket_number,))
        result = cursor.fetchone()
        conn.close()
        return result

    def close(self):
        """Close database connection (no-op for connection-per-query pattern)"""
        pass


class TrainStationApp:
    """Main application class"""

    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("train.title"))
        self.root.geometry("1000x700")
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
        style.theme_use("clam")
        
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

        self.payment_var = tk.StringVar(value="Card")
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
    
    def complete_purchase(self):
        """Process the ticket purchase"""
        name = self.name_entry.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("train.error.enter_passenger_name"))
            return

        if self.service_combo.current() < 0:
            messagebox.showerror(_t("common.error"), _t("train.error.select_service"))
            return

        service_idx = self.service_combo.current()
        service = self.services[service_idx]

        if service[7] <= 0:
            messagebox.showerror(_t("common.error"), _t("train.error.no_seats"))
            return

        # Calculate price
        base_price = service[6]
        payment_method = self.payment_var.get()
        if payment_method == "Student Account":
            final_price = base_price * 0.7
        else:
            final_price = base_price

        # Process student account payment if selected
        if payment_method == "Student Account" and FINANCE_AVAILABLE:
            student_id = self._get_current_user_student_id()
            if not student_id:
                messagebox.showerror(_t("train.error.payment_error"), _t("train.error.no_student_account"))
                return

            # Check balance and process payment
            balance = get_student_finance_account_balance(student_id)
            if balance is None:
                messagebox.showerror(_t("train.error.payment_error"), _t("train.error.account_not_found"))
                return

            if balance < final_price:
                messagebox.showerror(
                    _t("train.error.payment_error"),
                    _t("train.error.insufficient_balance", balance=balance, required=final_price)
                )
                return

        # Confirm purchase
        confirm = messagebox.askyesno(_t("train.purchase.confirm_title"),
            f"{_t('train.purchase.confirm_message')}\n\n"
            f"{_t('train.purchase.passenger_name')}: {name}\n"
            f"{_t('train.services.service_no')}: {service[1]}\n"
            f"{_t('train.purchase.route')}: {service[2]} → {service[3]}\n"
            f"{_t('train.services.departure')}: {service[4]}\n"
            f"{_t('train.purchase.payment_method')}: {payment_method}\n"
            f"{_t('train.purchase.total_price')}: £{final_price:.2f}")

        if confirm:
            # Process student account payment
            if payment_method == "Student Account" and FINANCE_AVAILABLE:
                student_id = self._get_current_user_student_id()
                payment_result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=final_price,
                    description=f"Train ticket: {service[2]} to {service[3]}",
                    transaction_source="TrainStation",
                    transaction_ref=f"TRAIN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=self.current_user.get('username', 'System') if self.current_user else 'System'
                )

                if not payment_result.get('success'):
                    messagebox.showerror(
                        _t("train.error.payment_error"),
                        payment_result.get('message', _t("train.error.payment_failed"))
                    )
                    return

            ticket_num, receipt_num = self.db.purchase_ticket(
                service[0], name, payment_method, final_price
            )

            # Send confirmation email
            ticket_data = {
                'ticket_number': ticket_num,
                'receipt_number': receipt_num,
                'passenger_name': name,
                'service_number': service[1],
                'departure_station': service[2],
                'arrival_station': service[3],
                'departure_time': service[4],
                'arrival_time': service[5],
                'payment_method': payment_method,
                'price_paid': final_price,
                'purchase_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            email_sent = self._send_booking_confirmation_email(ticket_data)

            self.show_receipt(ticket_num, email_sent=email_sent)
    
    def show_receipt(self, ticket_number, email_sent=False):
        """Display payment receipt"""
        receipt_data = self.db.get_receipt(ticket_number)

        if not receipt_data:
            messagebox.showerror(_t("common.error"), _t("train.error.receipt_not_found"))
            return

        # Create receipt window
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title(_t("train.receipt.title"))
        receipt_window.geometry("450x600")
        receipt_window.configure(bg="white")
        receipt_window.resizable(False, False)

        # Receipt content
        receipt_frame = tk.Frame(receipt_window, bg="white", padx=30, pady=20)
        receipt_frame.pack(fill="both", expand=True)

        # Header
        tk.Label(receipt_frame, text=f"🚂 {_t('train.app_name').upper()}",
                font=("Helvetica", 18, "bold"),
                bg="white", fg="#1a365d").pack()
        tk.Label(receipt_frame, text=_t("train.receipt.payment_receipt"),
                font=("Helvetica", 14),
                bg="white", fg="#4a5568").pack()

        # Divider
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)

        # Receipt details
        details = [
            (f"{_t('train.receipt.receipt_no')}:", receipt_data[0]),
            (f"{_t('train.receipt.date')}:", receipt_data[3]),
            ("", ""),
            (f"{_t('train.receipt.ticket_no')}:", receipt_data[4]),
            (f"{_t('train.receipt.passenger')}:", receipt_data[5]),
            (f"{_t('train.receipt.service')}:", receipt_data[6]),
            ("", ""),
            (f"{_t('train.receipt.from')}:", receipt_data[7]),
            (f"{_t('train.receipt.to')}:", receipt_data[8]),
            (f"{_t('train.receipt.departure')}:", receipt_data[9]),
            (f"{_t('train.receipt.arrival')}:", receipt_data[10]),
            ("", ""),
            (f"{_t('train.receipt.payment_method')}:", receipt_data[2]),
        ]

        for label, value in details:
            if label == "":
                tk.Frame(receipt_frame, height=5, bg="white").pack()
                continue
            row = tk.Frame(receipt_frame, bg="white")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=("Helvetica", 11),
                    bg="white", fg="#4a5568", width=15, anchor="e").pack(side="left")
            tk.Label(row, text=value, font=("Helvetica", 11, "bold"),
                    bg="white", fg="#1a365d").pack(side="left", padx=10)

        # Total
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)
        total_row = tk.Frame(receipt_frame, bg="white")
        total_row.pack(fill="x")
        tk.Label(total_row, text=f"{_t('train.receipt.total_paid')}:",
                font=("Helvetica", 14, "bold"),
                bg="white", fg="#1a365d").pack(side="left")
        tk.Label(total_row, text=f"£{receipt_data[1]:.2f}",
                font=("Helvetica", 18, "bold"),
                bg="white", fg="#2f855a").pack(side="right")

        # Email confirmation status
        if email_sent:
            tk.Label(receipt_frame, text=f"📧 {_t('train.receipt.email_sent')}",
                    font=("Helvetica", 10), bg="white", fg="#2f855a").pack(pady=5)

        # Footer
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)
        tk.Label(receipt_frame, text=_t("train.receipt.thank_you"),
                font=("Helvetica", 11, "italic"),
                bg="white", fg="#718096").pack()

        # Close button
        close_btn = tk.Button(receipt_frame, text=_t("common.close"),
                             font=("Helvetica", 11),
                             bg="#4a5568", fg="white",
                             relief="flat", padx=30, pady=8,
                             cursor="hand2",
                             command=receipt_window.destroy)
        close_btn.pack(pady=20)

        # Refresh services to update seat count
        self.services = self.db.get_all_services()
        messagebox.showinfo(_t("common.success"), _t("train.purchase.success", ticket_number=ticket_number))
    
    def show_tickets(self):
        """Display all purchased tickets"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.tickets.title"),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 15))

        # Create treeview with scrollbar
        tree_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=False, pady=(0, 10))

        columns = ("Ticket", "Passenger", "Service", "From", "To", "Time", "Payment", "Price", "Date", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        # Configure columns
        tree.heading("Ticket", text=_t("train.tickets.ticket_no"))
        tree.heading("Passenger", text=_t("train.tickets.passenger"))
        tree.heading("Service", text=_t("train.tickets.service"))
        tree.heading("From", text=_t("train.tickets.from"))
        tree.heading("To", text=_t("train.tickets.to"))
        tree.heading("Time", text=_t("train.tickets.departure"))
        tree.heading("Payment", text=_t("train.tickets.payment"))
        tree.heading("Price", text=_t("train.tickets.price"))
        tree.heading("Date", text=_t("train.tickets.purchase_date"))
        tree.heading("Status", text=_t("train.tickets.status", default="Status"))

        tree.column("Ticket", width=100, anchor="center")
        tree.column("Passenger", width=120)
        tree.column("Service", width=80, anchor="center")
        tree.column("From", width=130)
        tree.column("To", width=130)
        tree.column("Time", width=70, anchor="center")
        tree.column("Payment", width=100, anchor="center")
        tree.column("Price", width=70, anchor="center")
        tree.column("Date", width=110, anchor="center")
        tree.column("Status", width=80, anchor="center")

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        # Populate data with refund status
        tickets = self.db.get_all_tickets()

        # Get refund status for all tickets
        refunded_tickets = set()
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_number FROM train_refunds")
            refunded_tickets = set(row[0] for row in cursor.fetchall())
            conn.close()
        except Exception as e:
            logger.warning(f"Could not load refund status: {e}")
            # Continue without refund status

        for ticket in tickets:
            ticket_number = ticket[0]
            status = "Refunded" if ticket_number in refunded_tickets else "Active"
            tag = "refunded" if ticket_number in refunded_tickets else "active"

            tree.insert("", "end", values=(
                ticket_number,  # ticket_number
                ticket[1],  # passenger_name
                ticket[2],  # service_number
                ticket[3],  # departure_station
                ticket[4],  # arrival_station
                ticket[5],  # departure_time
                ticket[6],  # payment_method
                f"£{ticket[7]:.2f}",  # price_paid
                ticket[8],   # purchase_date
                status
            ), tags=(tag,))
        
        # Store tree reference for receipt viewing
        self.tickets_tree = tree
        
        # Buttons frame - make it more prominent
        btn_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        btn_frame.pack(pady=20, fill=tk.X)

        # Create inner frame to center buttons
        inner_btn_frame = tk.Frame(btn_frame, bg="#f0f4f8")
        inner_btn_frame.pack()

        view_receipt_btn = tk.Button(inner_btn_frame, text=f"📄 {_t('train.tickets.view_receipt')}",
                                    font=("Helvetica", 12, "bold"),
                                    bg="#3182ce", fg="white",
                                    activebackground="#2b6cb0",
                                    relief="flat", padx=25, pady=12,
                                    cursor="hand2",
                                    command=self.view_selected_receipt)
        view_receipt_btn.pack(side=tk.LEFT, padx=10)

        refund_btn = tk.Button(inner_btn_frame, text=f"💸 {_t('train.tickets.request_refund', default='Request Refund')}",
                              font=("Helvetica", 12, "bold"),
                              bg="#e53e3e", fg="white",
                              activebackground="#c53030",
                              relief="flat", padx=25, pady=12,
                              cursor="hand2",
                              command=self.request_ticket_refund)
        refund_btn.pack(side=tk.LEFT, padx=10)

        # Configure row colors based on status
        tree.tag_configure("refunded", background="#ffcccc", foreground="#7f0000")
        tree.tag_configure("active", background="#ccffcc", foreground="#005500")

        # Show count
        count_label = tk.Label(self.content_frame,
                              text=_t("train.tickets.total_count", count=len(tickets)),
                              font=("Helvetica", 10),
                              bg="#f0f4f8", fg="#718096")
        count_label.pack()
    
    def view_selected_receipt(self):
        """View receipt for selected ticket"""
        selection = self.tickets_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("train.tickets.select_ticket"))
            return

        item = self.tickets_tree.item(selection[0])
        ticket_number = item["values"][0]
        self.show_receipt(ticket_number)

    def request_ticket_refund(self):
        """Request refund for selected ticket"""
        selection = self.tickets_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                  _t("train.tickets.select_ticket", default="Please select a ticket."))
            return

        item = self.tickets_tree.item(selection[0])
        ticket_number = item["values"][0]
        passenger_name = item["values"][1]
        price_str = item["values"][7]  # Format: £XX.XX
        amount = float(price_str.replace('£', ''))

        # Check if already refunded
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT refund_id FROM train_refunds WHERE ticket_number = ?
            """, (ticket_number,))
            existing_refund = cursor.fetchone()
            conn.close()

            if existing_refund:
                messagebox.showwarning(_t("train.refunds.already_refunded", default="Already Refunded"),
                                      _t("train.refunds.already_refunded_msg", default="This ticket has already been refunded."))
                return

        except Exception as e:
            logger.error(f"Error checking refund status: {e}")

        # Confirm refund
        if not messagebox.askyesno(_t("train.refunds.confirm", default="Confirm Refund"),
                                  f"Process refund for ticket {ticket_number}?\n\nPassenger: {passenger_name}\nAmount: £{amount:.2f}"):
            return

        # Get student ID
        student_id = None
        if self.current_user:
            student_id = self.current_user.get('student_id') or self.current_user.get('id', '')

        # Show refund method dialog
        self.show_train_refund_method_dialog(ticket_number, amount, passenger_name)

    def show_refunds(self):
        """Display refunds management interface"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.refunds.title", default="Train Ticket Refunds"),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 15))

        # Search frame
        search_frame = tk.Frame(self.content_frame, bg="#ffffff", relief="solid", borderwidth=1)
        search_frame.pack(fill="x", pady=(0, 10), padx=10)

        tk.Label(search_frame, text=_t("common.search", default="Search:"),
                font=("Helvetica", 10), bg="#ffffff").pack(side="left", padx=10, pady=10)

        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = tk.Entry(search_frame, textvariable=self.refund_search_var, width=40, font=("Helvetica", 10))
        search_entry.pack(side="left", padx=10, pady=10)

        # Table frame
        tree_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=True)

        # Create treeview with 7 columns
        columns = ("Ticket", "Date", "Passenger", "Route", "Amount", "Payment Method", "Status")
        self.refunds_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure columns
        self.refunds_tree.heading("Ticket", text=_t("train.refunds.ticket_number", default="Ticket Number"))
        self.refunds_tree.heading("Date", text=_t("common.date", default="Date"))
        self.refunds_tree.heading("Passenger", text=_t("train.refunds.passenger", default="Passenger"))
        self.refunds_tree.heading("Route", text=_t("train.refunds.route", default="Route"))
        self.refunds_tree.heading("Amount", text=_t("common.amount", default="Amount"))
        self.refunds_tree.heading("Payment Method", text=_t("common.payment_method", default="Payment Method"))
        self.refunds_tree.heading("Status", text=_t("common.status", default="Status"))

        self.refunds_tree.column("Ticket", width=120, anchor="center")
        self.refunds_tree.column("Date", width=120, anchor="center")
        self.refunds_tree.column("Passenger", width=150)
        self.refunds_tree.column("Route", width=200)
        self.refunds_tree.column("Amount", width=100, anchor="center")
        self.refunds_tree.column("Payment Method", width=120, anchor="center")
        self.refunds_tree.column("Status", width=100, anchor="center")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons frame
        buttons_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        buttons_frame.pack(fill="x", pady=10)

        tk.Button(buttons_frame, text=_t("train.refunds.process", default="Process Refund"),
                 command=self.process_train_refund,
                 font=("Helvetica", 10, "bold"),
                 bg="#3182ce", fg="white",
                 activebackground="#2c5aa0",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.view_details", default="View Details"),
                 command=self.view_train_ticket_details,
                 font=("Helvetica", 10, "bold"),
                 bg="#38a169", fg="white",
                 activebackground="#2f855a",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.refresh", default="Refresh"),
                 command=self.refresh_refunds_list,
                 font=("Helvetica", 10, "bold"),
                 bg="#718096", fg="white",
                 activebackground="#4a5568",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.export_csv", default="Export to CSV"),
                 command=self.export_train_refunds_to_csv,
                 font=("Helvetica", 10, "bold"),
                 bg="#805ad5", fg="white",
                 activebackground="#6b46c1",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower() if hasattr(self, 'refund_search_var') else ''

            conn = self.db.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    t.ticket_number,
                    t.purchase_date,
                    t.passenger_name,
                    s.departure_station || ' → ' || s.arrival_station as route,
                    t.price_paid,
                    t.payment_method,
                    CASE WHEN r.refund_id IS NOT NULL THEN 'refunded' ELSE 'active' END as status
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN train_refunds r ON t.ticket_number = r.ticket_number
                ORDER BY t.purchase_date DESC
            """

            cursor.execute(query)
            tickets = cursor.fetchall()
            conn.close()

            for ticket in tickets:
                ticket_number, date, passenger, route, amount, payment_method, status = ticket

                # Apply search filter
                if search_term:
                    searchable = f"{ticket_number} {passenger} {route} {status}".lower()
                    if search_term not in searchable:
                        continue

                # Color code by status
                if status == 'refunded':
                    self.refunds_tree.insert("", "end", values=(
                        ticket_number, date, passenger, route,
                        f"£{amount:.2f}", payment_method, status
                    ), tags=('refunded',))
                else:
                    self.refunds_tree.insert("", "end", values=(
                        ticket_number, date, passenger, route,
                        f"£{amount:.2f}", payment_method, status
                    ), tags=('active',))

            # Configure tags
            self.refunds_tree.tag_configure('refunded', background='#ffcccc')
            self.refunds_tree.tag_configure('active', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def process_train_refund(self):
        """Process a refund for a train ticket"""
        # Get selected ticket
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("train.refunds.select_ticket", default="Please select a ticket to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_number = values[0]
        amount_str = values[4]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("train.refunds.already_refunded", default="Already Refunded"),
                                  _t("train.refunds.already_refunded_msg", default="This ticket has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("train.refunds.confirm", default="Confirm Refund"),
                                   f"Refund £{amount:.2f} for Ticket {ticket_number}?"):
            return

        try:
            # Get passenger name for student ID lookup
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT passenger_name FROM train_station_tickets WHERE ticket_number = ?",
                         (ticket_number,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("train.refunds.ticket_not_found", default="Ticket not found."))
                return

            passenger_name = result[0]

            # Show refund method dialog
            self.show_train_refund_method_dialog(ticket_number, amount, passenger_name)

        except Exception as e:
            logger.error(f"Error processing train refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_train_refund_method_dialog(self, ticket_number, amount, passenger_name):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("train.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#f0f4f8")

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        header_frame = tk.Frame(dialog, bg="#1a365d", height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text=_t("train.refunds.select_method", default="Select Refund Method"),
                font=("Helvetica", 14, "bold"), bg="#1a365d", fg="white").pack(pady=15)

        # Content
        content_frame = tk.Frame(dialog, bg="#f0f4f8")
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(content_frame, text=f"Refund Amount: £{amount:.2f}",
                font=("Helvetica", 12, "bold"), bg="#f0f4f8", fg="#1a365d").pack(pady=10)

        # Try to get student ID from passenger name
        student_id = self._get_student_id_from_passenger_name(passenger_name)

        # Get current balance if finance is available
        current_balance = None
        if student_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(student_id)
                tk.Label(content_frame, text=f"Current Student Account Balance: £{current_balance:.2f}",
                        font=("Helvetica", 10), bg="#f0f4f8", fg="#3182ce").pack(pady=5)
                new_balance = current_balance + amount
                tk.Label(content_frame, text=f"New Balance After Refund: £{new_balance:.2f}",
                        font=("Helvetica", 10, "bold"), bg="#f0f4f8", fg="#38a169").pack(pady=5)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        # Buttons
        tk.Button(content_frame, text="💵 Refund as Cash",
                 command=lambda: [dialog.destroy(), self._complete_train_refund(ticket_number, amount, 'cash', student_id)],
                 font=("Helvetica", 11, "bold"),
                 bg="#4a5568", fg="white",
                 activebackground="#2d3748",
                 relief="flat", padx=20, pady=12,
                 cursor="hand2", width=25).pack(pady=8)

        tk.Button(content_frame, text="💳 Refund to Card",
                 command=lambda: [dialog.destroy(), self._complete_train_refund(ticket_number, amount, 'card', student_id)],
                 font=("Helvetica", 11, "bold"),
                 bg="#4a5568", fg="white",
                 activebackground="#2d3748",
                 relief="flat", padx=20, pady=12,
                 cursor="hand2", width=25).pack(pady=8)

        account_btn = tk.Button(content_frame, text="🏦 Refund to Student Account",
                               command=lambda: [dialog.destroy(), self.add_train_refund_to_student_account(ticket_number, amount, student_id)],
                               font=("Helvetica", 11, "bold"),
                               bg="#3182ce", fg="white",
                               activebackground="#2c5aa0",
                               relief="flat", padx=20, pady=12,
                               cursor="hand2", width=25)
        account_btn.pack(pady=8)

        if not (student_id and FINANCE_AVAILABLE):
            account_btn.config(state='disabled', bg="#a0aec0")

        tk.Button(content_frame, text=_t("common.cancel", default="Cancel"),
                 command=dialog.destroy,
                 font=("Helvetica", 10),
                 bg="#e53e3e", fg="white",
                 activebackground="#c53030",
                 relief="flat", padx=20, pady=10,
                 cursor="hand2", width=25).pack(pady=8)

    def _get_student_id_from_passenger_name(self, passenger_name):
        """Try to get student ID from passenger name"""
        # First check if current user matches
        if self.current_user and self.current_user.get('full_name', '').lower() == passenger_name.lower():
            return self._get_current_user_student_id()

        # Try to match with students table
        try:
            from university_system.infrastructure.database.db import get_db_connection as get_central_db
            with get_central_db() as conn:
                cursor = conn.cursor()
                # Query using concatenated first_name and last_name since full_name column doesn't exist
                cursor.execute("""
                    SELECT student_id FROM students
                    WHERE TRIM(first_name || ' ' || last_name) = ?
                       OR TRIM(first_name || ' ' || COALESCE(middle_name, '') || ' ' || last_name) = ?
                """, (passenger_name.strip(), passenger_name.strip()))
                result = cursor.fetchone()
                if result:
                    return result[0]
        except Exception as e:
            logger.warning(f"Could not lookup student ID: {e}")

        return None

    def _complete_train_refund(self, ticket_number, amount, refund_method, student_id):
        """Complete the refund process (for cash/card)"""
        try:
            from university_system.infrastructure.database.db import get_db_connection as get_central_db, transaction as central_transaction

            # Generate refund reference
            refund_ref = f"TRAIN-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Update ticket in local database
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Add status column if it doesn't exist (optional - status is now derived from train_refunds)
            try:
                cursor.execute("ALTER TABLE train_station_tickets ADD COLUMN status TEXT DEFAULT 'active'")
            except:
                pass

            # Update status if column exists (optional - status is now derived from train_refunds)
            try:
                cursor.execute("""
                    UPDATE train_station_tickets
                    SET status = 'refunded'
                    WHERE ticket_number = ?
                """, (ticket_number,))
            except:
                pass  # Column doesn't exist, status will be derived from train_refunds table

            # Get processed_by info
            processed_by = None
            if self.current_user:
                processed_by = self.current_user.get('username') or self.current_user.get('id', '')

            # Insert refund record into local database
            cursor.execute("""
                INSERT INTO train_refunds
                (ticket_number, student_id, amount, refund_method, refund_reference, processed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_number, student_id, amount, refund_method, refund_ref, processed_by))

            conn.commit()
            conn.close()

            # Also create refund record in central database for reporting
            with central_transaction() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS train_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_number TEXT,
                        student_id TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT
                    )
                """)

                cursor.execute("""
                    INSERT INTO train_refunds
                    (ticket_number, student_id, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticket_number, student_id, amount, refund_method, refund_ref, processed_by))

            # Send receipt
            self.send_train_refund_receipt(student_id, amount, refund_method, refund_ref, ticket_number)

            # Notify finance GUI
            self.notify_train_finance_gui(ticket_number, amount, refund_method, refund_ref)

            # Refresh list if refunds view is active
            if hasattr(self, 'refunds_tree'):
                try:
                    self.refresh_refunds_list()
                except:
                    pass  # Refunds view not currently active

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing train refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")

    def add_train_refund_to_student_account(self, ticket_number, amount, student_id):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.finance_unavailable", default="Finance system not available."))
            return

        if not student_id:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("train.refunds.no_student_id", default="Could not determine student ID."))
            return

        try:
            from university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists
            from university_system.infrastructure.database.db import get_db_connection as get_central_db, transaction as central_transaction

            # Ensure student account exists
            ensure_student_finance_account_exists(student_id)

            # Generate refund reference
            refund_ref = f"TRAIN-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Update ticket in local database
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Add status column if it doesn't exist (optional - status is now derived from train_refunds)
            try:
                cursor.execute("ALTER TABLE train_station_tickets ADD COLUMN status TEXT DEFAULT 'active'")
            except:
                pass

            # Update status if column exists (optional - status is now derived from train_refunds)
            try:
                cursor.execute("""
                    UPDATE train_station_tickets
                    SET status = 'refunded'
                    WHERE ticket_number = ?
                """, (ticket_number,))
            except:
                pass  # Column doesn't exist, status will be derived from train_refunds table

            # Get processed_by info
            processed_by = None
            if self.current_user:
                processed_by = self.current_user.get('username') or self.current_user.get('id', '')

            # Insert refund record into local database
            cursor.execute("""
                INSERT INTO train_refunds
                (ticket_number, student_id, amount, refund_method, refund_reference, processed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_number, student_id, amount, 'student_account', refund_ref, processed_by))

            conn.commit()
            conn.close()

            # Process in central database
            with central_transaction() as conn:
                cursor = conn.cursor()

                # Create refund record in central database
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS train_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_number TEXT,
                        student_id TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT
                    )
                """)

                cursor.execute("""
                    INSERT INTO train_refunds
                    (ticket_number, student_id, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticket_number, student_id, amount, 'student_account', refund_ref, processed_by))

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, student_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (student_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in student_finance_transactions
                cursor.execute("""
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES (?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, student_id, amount, new_balance, f'Train ticket refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Send receipt
            self.send_train_refund_receipt(student_id, amount, 'student_account', refund_ref, ticket_number, new_balance)

            # Notify finance GUI
            self.notify_train_finance_gui(ticket_number, amount, 'student_account', refund_ref)

            # Refresh list if refunds view is active
            if hasattr(self, 'refunds_tree'):
                try:
                    self.refresh_refunds_list()
                except:
                    pass  # Refunds view not currently active

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding train refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_train_refund_receipt(self, student_id, amount, refund_method, refund_ref, ticket_number, new_balance=None):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            logger.info("Email service not available, skipping receipt")
            return

        try:
            # Get customer email
            customer_email = None
            customer_name = None

            if self.current_user and self.current_user.get('student_id') == student_id:
                customer_email = self.current_user.get('email')
                customer_name = self.current_user.get('full_name')
            elif student_id:
                customer_email = get_student_email(student_id)
                # Get name from students table
                from university_system.infrastructure.database.db import get_db_connection as get_central_db
                with get_central_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                    result = cursor.fetchone()
                    if result:
                        first_name, last_name = result
                        customer_name = f"{first_name} {last_name}".strip() if first_name or last_name else None

            if not customer_email:
                logger.warning(f"No email found for student {student_id}")
                return

            if not customer_name:
                customer_name = student_id

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build email body
            try:
                if TEMPLATE_AVAILABLE:
                    subject, email_body = render_template('train_refund_receipt', {
                        'customer_name': customer_name,
                        'booking_id': ticket_number,
                        'refund_amount': f"{amount:.2f}",
                        'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'payment_method': method_display,
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using fallback email.")
                # Fallback email
                subject = f"Train Ticket Refund Receipt - {refund_ref}"
                email_body = f"""
Dear {customer_name},

This is to confirm that your train ticket refund has been processed successfully.

Refund Details:
- Ticket Number: {ticket_number}
- Refund Amount: £{amount:.2f}
- Refund Method: {method_display}
- Reference Number: {refund_ref}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

                if new_balance is not None:
                    email_body += f"\nYour new student account balance is: £{new_balance:.2f}\n"

                email_body += """
If you have any questions about this refund, please contact the train station.

Best regards,
University Train Station
"""

            # Send email
            send_email(
                recipient_email=customer_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending train refund receipt: {e}")

    def notify_train_finance_gui(self, ticket_number, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            from university_system.infrastructure.database.db import get_db_connection as get_central_db, transaction as central_transaction

            with central_transaction() as conn:
                cursor = conn.cursor()

                # Create finance_refunds table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        refund_reference TEXT UNIQUE,
                        department TEXT,
                        transaction_id TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        notes TEXT
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.current_user:
                    processed_by = self.current_user.get('username') or self.current_user.get('id', '')

                # Insert refund record
                cursor.execute("""
                    INSERT INTO finance_refunds
                    (refund_reference, department, transaction_id, amount, refund_method, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (refund_ref, 'Train Station', ticket_number, amount, refund_method, processed_by,
                     'Train ticket refund'))

            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_train_ticket_details(self):
        """View detailed information about a ticket"""
        # Get selected ticket
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("train.refunds.select_ticket_view", default="Please select a ticket to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_number = values[0]

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Get ticket details with service info
            cursor.execute("""
                SELECT
                    t.ticket_number,
                    t.passenger_name,
                    t.price_paid,
                    t.payment_method,
                    t.purchase_date,
                    CASE WHEN r.refund_id IS NOT NULL THEN 'refunded' ELSE 'active' END as status,
                    s.service_number,
                    s.departure_station,
                    s.arrival_station,
                    s.departure_time,
                    s.arrival_time
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN train_refunds r ON t.ticket_number = r.ticket_number
                WHERE t.ticket_number = ?
            """, (ticket_number,))

            ticket = cursor.fetchone()
            conn.close()

            if not ticket:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("train.refunds.ticket_not_found", default="Ticket not found."))
                return

            (ticket_num, passenger, amount, payment_method, purchase_date, status,
             service_number, dep_station, arr_station, dep_time, arr_time) = ticket

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(_t("train.refunds.ticket_details", default="Ticket Details"))
            details_window.geometry("600x650")
            details_window.transient(self.root)
            details_window.configure(bg="#f0f4f8")

            # Header
            header_frame = tk.Frame(details_window, bg="#1a365d", height=60)
            header_frame.pack(fill="x")
            header_frame.pack_propagate(False)

            tk.Label(header_frame, text="🎫 Train Ticket Details",
                    font=("Helvetica", 16, "bold"), bg="#1a365d", fg="white").pack(pady=12)

            # Scrollable content
            canvas = tk.Canvas(details_window, bg="#f0f4f8", highlightthickness=0)
            scrollbar = tk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Build details
            details = f"""
═══════════════════════════════════════════════════════

TICKET INFORMATION
───────────────────────────────────────────────────────
  Ticket Number: {ticket_num}
  Status: {status.upper()}
  Purchase Date: {purchase_date}

PASSENGER INFORMATION
───────────────────────────────────────────────────────
  Passenger Name: {passenger}

JOURNEY DETAILS
───────────────────────────────────────────────────────
  Service Number: {service_number}
  From: {dep_station}
  To: {arr_station}
  Departure Time: {dep_time}
  Arrival Time: {arr_time}

FINANCIAL DETAILS
───────────────────────────────────────────────────────
  Amount: £{amount:.2f}
  Payment Method: {payment_method}

═══════════════════════════════════════════════════════
"""

            text_widget = tk.Text(scrollable_frame, wrap="word", width=70, height=25,
                                font=("Courier", 10), bg="#ffffff", relief="flat", padx=20, pady=20)
            text_widget.insert('1.0', details)
            text_widget.config(state='disabled')
            text_widget.pack(padx=20, pady=20)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Close button
            tk.Button(details_window, text=_t("common.close", default="Close"),
                     command=details_window.destroy,
                     font=("Helvetica", 10, "bold"),
                     bg="#e53e3e", fg="white",
                     activebackground="#c53030",
                     relief="flat", padx=20, pady=10,
                     cursor="hand2").pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing ticket details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")

    def export_train_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'train_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    t.ticket_number,
                    t.purchase_date,
                    t.passenger_name,
                    s.departure_station || ' → ' || s.arrival_station as route,
                    t.price_paid,
                    t.payment_method,
                    CASE WHEN r.refund_id IS NOT NULL THEN 'refunded' ELSE 'active' END as status
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN train_refunds r ON t.ticket_number = r.ticket_number
                ORDER BY t.purchase_date DESC
            """)

            tickets = cursor.fetchall()
            conn.close()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Ticket Number', 'Date', 'Passenger', 'Route',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for ticket in tickets:
                    ticket_number, date, passenger, route, amount, payment_method, status = ticket
                    writer.writerow([
                        ticket_number,
                        date,
                        passenger,
                        route,
                        f'{amount:.2f}',
                        payment_method,
                        status
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")

    def on_closing(self):
        """Handle application closing"""
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TrainStationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
