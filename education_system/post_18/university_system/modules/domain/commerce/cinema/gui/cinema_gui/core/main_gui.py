"""
Cinema Booking System - Main GUI Application
Core CinemaApp class with method attachments from submodules.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import random
import string
import csv
import os
import json
import glob

# i18n support
try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE, init_database
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import (
    TICKET_TYPES, SNACKS_MENU, MEMBERSHIP_TIERS, DYNAMIC_PRICING,
    GROUP_DISCOUNTS, EARLY_BIRD_DISCOUNTS, SEASON_PASSES, SEAT_TYPES,
    SNACK_DIETARY, SNACK_COMBOS, AGE_RESTRICTED_RATINGS, STAFF_ROLES,
    REFERRAL_REWARD, BIRTHDAY_REWARD_TICKET, SEAT_HOLD_TIMEOUT,
    THEMED_NIGHTS, QR_AVAILABLE,
)

# University system integrations
try:
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def get_auth():
        return None

try:
    from education_system.post_18.university_system.infrastructure.email import send_email
    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        return False
    render_template = None

try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        record_payment_to_finance
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def process_student_finance_account_payment(*args, **kwargs):
        return {'success': False, 'message': 'Finance integration not available'}
    def get_student_finance_account_balance(*args, **kwargs):
        return None
    def record_payment_to_finance(*args, **kwargs):
        return None

try:
    from education_system.post_18.university_system.infrastructure.auth import hash_password
    HASH_AVAILABLE = True
except ImportError:
    HASH_AVAILABLE = False
    import hashlib
    def hash_password(password):
        # Use PBKDF2 for password hashing when main auth module unavailable
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), b'cinema-fallback-salt', 100000)
        return dk.hex()

class CinemaApp:
    def __init__(self, root):
        self.root = root
        self.root.title(_t("cinema.window_title", default="Cinema Booking System"))
        self.root.geometry("1400x950")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#2c3e50")

        self.selected_seats = []
        self.current_screening = None
        self.ticket_types = {}  # seat_id -> ticket_type
        self.selected_snacks = {}  # snack_name -> quantity
        self.applied_promo = None
        self.current_booking_ref = None  # For finance integration
        self.booking_student_id = None  # For student account payment

        self.setup_styles()
        self.create_main_layout()
        self.show_dashboard()

    def setup_styles(self):
        """Configure ttk styles to match university system."""
        style = ttk.Style()

        # Sidebar styles
        style.configure('Sidebar.TFrame', background='#2c3e50')
        style.configure('Content.TFrame', background='#ecf0f1')

        # Title and subtitle labels
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"),
                       background="#ecf0f1", foreground="#2c3e50")
        style.configure("Subtitle.TLabel", font=("Helvetica", 14),
                       background="#ecf0f1", foreground="#34495e")
        style.configure("Info.TLabel", font=("Helvetica", 11),
                       background="#ecf0f1", foreground="#2c3e50")

        # Button styles
        style.configure("Primary.TButton", font=("Helvetica", 11, "bold"),
                       padding=10)
        style.configure("Secondary.TButton", font=("Helvetica", 10),
                       padding=8)
        style.configure("Danger.TButton", font=("Helvetica", 10),
                       padding=8)
        style.configure("Success.TButton", font=("Helvetica", 10),
                       padding=8)

        # Card frame style
        style.configure("Card.TFrame", background="#ffffff")

        # Treeview style
        style.configure("Treeview", font=("Helvetica", 10), rowheight=30,
                       background="#ffffff", foreground="#2c3e50", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"),
                       background="#34495e", foreground="white")
        style.map("Treeview", background=[('selected', '#3498db')])

    def get_current_user_info(self):
        """Get current logged-in user details from university auth system."""
        try:
            auth = get_auth()
            if auth and auth.current_user:
                user = auth.current_user
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                name = f"{first_name} {last_name}".strip()
                if not name:
                    name = user.get('username', '')
                email = user.get('email', '')
                student_id = user.get('student_id', user.get('id', ''))

                # If email not in auth object, try to get it from database
                if not email and student_id:
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("SELECT email FROM students WHERE student_id = ?", (student_id,))
                        result = cursor.fetchone()
                        if result:
                            email = result[0]
                        conn.close()
                    except Exception:
                        pass

                return {
                    'name': name,
                    'email': email,
                    'student_id': str(student_id) if student_id else '',
                    'role': user.get('role', '')
                }
        except Exception:
            pass
        return None

    def send_booking_receipt(self, booking_ref, customer_email, customer_name,
                             movie_title, show_time, seats, total, payment_method):
        """Send email receipt to customer after successful booking."""
        if not customer_email or not EMAIL_AVAILABLE:
            return False
        try:
            # Render email from template
            subject, body = render_template('commerce/cinema/booking_confirmation', {
                'customer_name': customer_name,
                'booking_ref': booking_ref,
                'movie_title': movie_title,
                'show_time': show_time,
                'seats': seats,
                'total_amount': f"£{total:.2f}",
                'payment_method': payment_method
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Cinema Booking Confirmation - {booking_ref}"
                body = f"""Dear {customer_name},

Thank you for your booking at University Cinema!

Booking Reference: {booking_ref}
Movie: {movie_title}
Show Time: {show_time}
Seats: {seats}
Total Paid: £{total:.2f}
Payment Method: {payment_method}

Please present this confirmation or your booking reference at the cinema.

We look forward to seeing you!

Best regards,
University Cinema
"""
            send_email(customer_email, subject, body)
            return True
        except Exception:
            return False

    def create_main_layout(self):
        """Create the main application layout with sidebar navigation."""
        # Main container - horizontal split
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar with scrollbar
        sidebar_container = ttk.Frame(main_container, style='Sidebar.TFrame')
        sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)

        # Canvas for scrollable sidebar
        self.sidebar_canvas = tk.Canvas(sidebar_container, width=250, bg='#2c3e50',
                                        highlightthickness=0)
        self.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical",
                                               command=self.sidebar_canvas.yview)
        self.scrollable_sidebar = tk.Frame(self.sidebar_canvas, bg='#2c3e50')

        self.scrollable_sidebar.bind(
            "<Configure>",
            lambda e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        )

        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.scrollable_sidebar, anchor="nw")
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)

        # Bind canvas configure to update sidebar width
        def on_sidebar_canvas_configure(event):
            self.sidebar_canvas.itemconfigure(self.sidebar_window, width=event.width)
        self.sidebar_canvas.bind("<Configure>", on_sidebar_canvas_configure)

        self.sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux scroll support
        self.sidebar_canvas.bind_all("<Button-4>", lambda e: self.sidebar_canvas.yview_scroll(-1, "units"))
        self.sidebar_canvas.bind_all("<Button-5>", lambda e: self.sidebar_canvas.yview_scroll(1, "units"))

        # Right content area
        content_container = ttk.Frame(main_container, style='Content.TFrame')
        content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Content frame
        self.content_frame = content_container

        # Status bar
        self.status_label = ttk.Label(self.root, text=_t("cinema.status_ready", default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Build sidebar navigation
        self.build_sidebar_navigation()

    def add_sidebar_header(self, text):
        """Add a category header to sidebar"""
        header = tk.Label(self.scrollable_sidebar, text=text,
                         bg='#34495e', fg='white', font=('Arial', 11, 'bold'),
                         anchor='w', padx=15, pady=8)
        header.pack(fill=tk.X, pady=(10, 0))

    def add_sidebar_button(self, text, command):
        """Add a button to sidebar"""
        btn = tk.Button(self.scrollable_sidebar, text=text,
                       command=command, bg='#2c3e50', fg='white',
                       activebackground='#3498db', activeforeground='white',
                       font=('Arial', 10), bd=0, padx=20, pady=10,
                       anchor='w', cursor='hand2')
        btn.pack(fill=tk.X, padx=5, pady=2)
        # Hover effects
        btn.bind('<Enter>', lambda e: btn.config(bg='#3498db'))
        btn.bind('<Leave>', lambda e: btn.config(bg='#2c3e50'))

    def add_sidebar_separator(self):
        """Add a visual separator in sidebar"""
        sep = tk.Frame(self.scrollable_sidebar, height=1, bg='#34495e')
        sep.pack(fill=tk.X, padx=10, pady=5)

    def build_sidebar_navigation(self):
        """Build the complete sidebar navigation"""
        # Title
        title = tk.Label(self.scrollable_sidebar, text=_t("cinema.sidebar_title", default="Cinema"),
                        bg='#2c3e50', fg='#3498db', font=('Arial', 16, 'bold'),
                        anchor='w', padx=15, pady=15)
        title.pack(fill=tk.X)

        # Main Section
        self.add_sidebar_header(_t("cinema.nav.categories.main", default="Main"))
        self.add_sidebar_button(_t("cinema.nav.items.dashboard", default="Dashboard"), self.show_dashboard)
        self.add_sidebar_button(_t("cinema.nav.items.now_showing", default="Now Showing"), self.show_movies_page)
        self.add_sidebar_button(_t("cinema.nav.items.coming_soon", default="Coming Soon"), self.show_coming_soon_page)
        self.add_sidebar_button(_t("cinema.nav.items.my_bookings", default="My Bookings"), self.show_bookings_page)

        # Booking Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.booking", default="Booking"))
        self.add_sidebar_button(_t("cinema.nav.items.book_now", default="Book Now"), self.show_movies_page)
        self.add_sidebar_button(_t("cinema.nav.items.manage_bookings", default="Manage Bookings"), self.show_ticket_management)
        self.add_sidebar_button(_t("cinema.nav.items.screenings", default="Screenings"), self.show_screening_management)
        self.add_sidebar_button(_t("cinema.nav.items.gift_cards", default="Gift Cards"), self.show_gift_cards_page)
        self.add_sidebar_button(_t("cinema.nav.items.season_passes", default="Season Passes"), self.show_season_passes_page)

        # Features Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.features", default="Features"))
        self.add_sidebar_button(_t("cinema.nav.items.snacks_drinks", default="Snacks & Drinks"), self.show_snacks_only_page)
        self.add_sidebar_button(_t("cinema.nav.items.members_club", default="Members Club"), self.show_members_page)
        self.add_sidebar_button(_t("cinema.nav.items.reviews", default="Reviews"), self.show_reviews_page)
        self.add_sidebar_button(_t("cinema.nav.items.waitlist", default="Waitlist"), self.show_waitlist_page)
        self.add_sidebar_button(_t("cinema.nav.items.polls_voting", default="Polls & Voting"), self.show_polls_page)

        # Events Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.events", default="Events"))
        self.add_sidebar_button(_t("cinema.nav.items.special_events", default="Special Events"), self.show_events_page)
        self.add_sidebar_button(_t("cinema.nav.items.private_rentals", default="Private Rentals"), self.show_rentals_page)
        self.add_sidebar_button(_t("cinema.nav.items.corporate_bookings", default="Corporate Bookings"), self.show_corporate_page)

        # Management Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.management", default="Management"))
        self.add_sidebar_button(_t("cinema.nav.items.movie_management", default="Movie Management"), self.show_movie_management)
        self.add_sidebar_button(_t("cinema.nav.items.promo_codes", default="Promo Codes"), self.show_promo_management)
        self.add_sidebar_button(_t("cinema.nav.items.staff", default="Staff"), self.show_staff_page)
        self.add_sidebar_button(_t("cinema.nav.items.inventory", default="Inventory"), self.show_inventory_page)
        self.add_sidebar_button(_t("cinema.nav.items.maintenance", default="Maintenance"), self.show_maintenance_page)
        self.add_sidebar_button(_t("cinema.nav.items.theatre_layout", default="Theatre Layout"), self.show_theatre_layout_page)
        self.add_sidebar_button(_t("cinema.nav.items.refunds", default="Refunds"), self.show_refunds_page)

        # Analytics Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.analytics", default="Analytics"))
        self.add_sidebar_button(_t("cinema.nav.items.reports", default="Reports"), self.show_reports_page)
        self.add_sidebar_button(_t("cinema.nav.items.analytics", default="Analytics"), self.show_analytics_page)
        self.add_sidebar_button(_t("cinema.nav.items.seat_heatmap", default="Seat Heatmap"), self.show_heatmap_page)
        self.add_sidebar_button(_t("cinema.nav.items.audit_log", default="Audit Log"), self.show_audit_log_page)

        # Customer Section
        self.add_sidebar_separator()
        self.add_sidebar_header(_t("cinema.nav.categories.customers", default="Customers"))
        self.add_sidebar_button(_t("cinema.nav.items.customer_profiles", default="Customer Profiles"), self.show_profiles_page)
        self.add_sidebar_button(_t("cinema.nav.items.referrals", default="Referrals"), self.show_referrals_page)
        self.add_sidebar_button(_t("cinema.nav.items.movie_series", default="Movie Series"), self.show_series_page)
        self.add_sidebar_button(_t("cinema.nav.items.accessible_seating", default="Accessible Seating"), self.show_accessible_page)

        # Force scrollregion update
        self.scrollable_sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def clear_content(self):
        """Clear the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

# ==================== METHOD ATTACHMENTS ====================
# Import functions from submodules and attach to CinemaApp class

# --- Helpers ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.helpers import (
    calculate_dynamic_price,
    calculate_group_discount,
    calculate_early_bird_discount,
    get_member_discount,
    verify_age,
)
CinemaApp.calculate_dynamic_price = calculate_dynamic_price
CinemaApp.calculate_group_discount = calculate_group_discount
CinemaApp.calculate_early_bird_discount = calculate_early_bird_discount
CinemaApp.get_member_discount = get_member_discount
CinemaApp.verify_age = verify_age

# --- Reports: Dashboard ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.dashboard import show_dashboard
CinemaApp.show_dashboard = show_dashboard

# --- Booking: Movie Browser ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.booking.movie_browser import (
    show_movies_page,
    create_movie_card,
    show_screenings,
)
CinemaApp.show_movies_page = show_movies_page
CinemaApp.create_movie_card = create_movie_card
CinemaApp.show_screenings = show_screenings

# --- Booking: Seat Selection ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.booking.seat_selection import (
    show_seat_selection,
    toggle_seat,
)
CinemaApp.show_seat_selection = show_seat_selection
CinemaApp.toggle_seat = toggle_seat

# --- Booking: Snacks ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.booking.snacks import (
    show_snacks_page,
    update_snacks_total,
    show_snacks_only_page,
    create_snack_order,
)
CinemaApp.show_snacks_page = show_snacks_page
CinemaApp.update_snacks_total = update_snacks_total
CinemaApp.show_snacks_only_page = show_snacks_only_page
CinemaApp.create_snack_order = create_snack_order

# --- Booking: Payment ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.booking.payment import (
    show_payment_page,
    print_ticket,
)
CinemaApp.show_payment_page = show_payment_page
CinemaApp.print_ticket = print_ticket

# --- Management: Screening Management ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.management.screening_management import (
    show_screening_management,
    show_add_screening_form,
    edit_selected_screening,
    cancel_selected_screening,
)
CinemaApp.show_screening_management = show_screening_management
CinemaApp.show_add_screening_form = show_add_screening_form
CinemaApp.edit_selected_screening = edit_selected_screening
CinemaApp.cancel_selected_screening = cancel_selected_screening

# --- Management: Movie Management ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.management.movie_management import (
    show_movie_management,
    refresh_movie_list,
    show_add_movie_form,
    show_movie_form,
    edit_selected_movie,
    delete_selected_movie,
)
CinemaApp.show_movie_management = show_movie_management
CinemaApp.refresh_movie_list = refresh_movie_list
CinemaApp.show_add_movie_form = show_add_movie_form
CinemaApp.show_movie_form = show_movie_form
CinemaApp.edit_selected_movie = edit_selected_movie
CinemaApp.delete_selected_movie = delete_selected_movie

# --- Management: Ticket Management ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.management.ticket_management import (
    show_ticket_management,
    print_selected_ticket,
    edit_selected_ticket,
    cancel_selected_ticket,
    delete_selected_ticket,
    reactivate_selected_ticket,
)
CinemaApp.show_ticket_management = show_ticket_management
CinemaApp.print_selected_ticket = print_selected_ticket
CinemaApp.edit_selected_ticket = edit_selected_ticket
CinemaApp.cancel_selected_ticket = cancel_selected_ticket
CinemaApp.delete_selected_ticket = delete_selected_ticket
CinemaApp.reactivate_selected_ticket = reactivate_selected_ticket

# --- Management: Promo Management ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.management.promo_management import (
    show_promo_management,
    refresh_promo_list,
    show_add_promo_form,
    edit_selected_promo,
    deactivate_selected_promo,
)
CinemaApp.show_promo_management = show_promo_management
CinemaApp.refresh_promo_list = refresh_promo_list
CinemaApp.show_add_promo_form = show_add_promo_form
CinemaApp.edit_selected_promo = edit_selected_promo
CinemaApp.deactivate_selected_promo = deactivate_selected_promo

# --- Management: Bookings ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.management.bookings import show_bookings_page
CinemaApp.show_bookings_page = show_bookings_page

# --- Loyalty: Members ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.loyalty.members import (
    show_members_page,
    show_add_member_form,
    show_member_lookup,
    view_member_details,
    edit_selected_member,
    add_member_points,
    deactivate_member,
)
CinemaApp.show_members_page = show_members_page
CinemaApp.show_add_member_form = show_add_member_form
CinemaApp.show_member_lookup = show_member_lookup
CinemaApp.view_member_details = view_member_details
CinemaApp.edit_selected_member = edit_selected_member
CinemaApp.add_member_points = add_member_points
CinemaApp.deactivate_member = deactivate_member

# --- Loyalty: Gift Cards ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.loyalty.gift_cards import (
    show_gift_cards_page,
    refresh_gift_cards,
    create_gift_card,
    check_gift_card_balance,
    view_gift_card_details,
    deactivate_gift_card,
)
CinemaApp.show_gift_cards_page = show_gift_cards_page
CinemaApp.refresh_gift_cards = refresh_gift_cards
CinemaApp.create_gift_card = create_gift_card
CinemaApp.check_gift_card_balance = check_gift_card_balance
CinemaApp.view_gift_card_details = view_gift_card_details
CinemaApp.deactivate_gift_card = deactivate_gift_card

# --- Loyalty: Profiles ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.loyalty.profiles import (
    show_profiles_page,
    create_profile,
    edit_profile,
    view_profile_history,
    set_favorite_seats,
    show_birthday_rewards,
)
CinemaApp.show_profiles_page = show_profiles_page
CinemaApp.create_profile = create_profile
CinemaApp.edit_profile = edit_profile
CinemaApp.view_profile_history = view_profile_history
CinemaApp.set_favorite_seats = set_favorite_seats
CinemaApp.show_birthday_rewards = show_birthday_rewards

# --- Loyalty: Referrals ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.loyalty.referrals import (
    show_referrals_page,
    create_referral,
    use_referral,
    give_referral_reward,
)
CinemaApp.show_referrals_page = show_referrals_page
CinemaApp.create_referral = create_referral
CinemaApp.use_referral = use_referral
CinemaApp.give_referral_reward = give_referral_reward

# --- Loyalty: Season Passes ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.loyalty.season_passes import (
    show_season_passes_page,
    sell_pass,
    verify_pass,
)
CinemaApp.show_season_passes_page = show_season_passes_page
CinemaApp.sell_pass = sell_pass
CinemaApp.verify_pass = verify_pass

# --- Community: Waitlist ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.community.waitlist import (
    show_waitlist_page,
    notify_waitlist_customer,
    mark_waitlist_fulfilled,
    remove_waitlist_entry,
)
CinemaApp.show_waitlist_page = show_waitlist_page
CinemaApp.notify_waitlist_customer = notify_waitlist_customer
CinemaApp.mark_waitlist_fulfilled = mark_waitlist_fulfilled
CinemaApp.remove_waitlist_entry = remove_waitlist_entry

# --- Community: Reviews ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.community.reviews import (
    show_reviews_page,
    add_review,
    view_full_review,
    update_review_status,
)
CinemaApp.show_reviews_page = show_reviews_page
CinemaApp.add_review = add_review
CinemaApp.view_full_review = view_full_review
CinemaApp.update_review_status = update_review_status

# --- Community: Coming Soon ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.community.coming_soon import (
    show_coming_soon_page,
    add_coming_soon,
    watch_trailer,
    notify_me,
    activate_movie,
    delete_coming,
)
CinemaApp.show_coming_soon_page = show_coming_soon_page
CinemaApp.add_coming_soon = add_coming_soon
CinemaApp.watch_trailer = watch_trailer
CinemaApp.notify_me = notify_me
CinemaApp.activate_movie = activate_movie
CinemaApp.delete_coming = delete_coming

# --- Community: Series ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.community.series import (
    show_series_page,
    on_series_select,
    create_series,
    link_movie_to_series,
)
CinemaApp.show_series_page = show_series_page
CinemaApp.on_series_select = on_series_select
CinemaApp.create_series = create_series
CinemaApp.link_movie_to_series = link_movie_to_series

# --- Community: Polls ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.community.polls import (
    show_polls_page,
    create_poll,
    view_results,
    cast_vote,
)
CinemaApp.show_polls_page = show_polls_page
CinemaApp.create_poll = create_poll
CinemaApp.view_results = view_results
CinemaApp.cast_vote = cast_vote

# --- Operations: Staff Management ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.staff_management import (
    show_staff_page,
    _hash_staff_password,
    _send_staff_welcome_email,
    add_staff,
)
CinemaApp.show_staff_page = show_staff_page
CinemaApp._hash_staff_password = _hash_staff_password
CinemaApp._send_staff_welcome_email = _send_staff_welcome_email
CinemaApp.add_staff = add_staff

# --- Operations: Inventory ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.inventory import (
    show_inventory_page,
    add_inv_item,
    restock_inv,
)
CinemaApp.show_inventory_page = show_inventory_page
CinemaApp.add_inv_item = add_inv_item
CinemaApp.restock_inv = restock_inv

# --- Operations: Maintenance ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.maintenance import (
    show_maintenance_page,
    schedule_maint,
    complete_maint,
)
CinemaApp.show_maintenance_page = show_maintenance_page
CinemaApp.schedule_maint = schedule_maint
CinemaApp.complete_maint = complete_maint

# --- Operations: Equipment ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.equipment import (
    show_equipment_page,
    add_equipment,
    log_equipment_maintenance,
    update_equipment_hours,
    view_equipment_history,
    edit_equipment,
    mark_equipment_out_of_service,
    show_maintenance_schedule,
)
CinemaApp.show_equipment_page = show_equipment_page
CinemaApp.add_equipment = add_equipment
CinemaApp.log_equipment_maintenance = log_equipment_maintenance
CinemaApp.update_equipment_hours = update_equipment_hours
CinemaApp.view_equipment_history = view_equipment_history
CinemaApp.edit_equipment = edit_equipment
CinemaApp.mark_equipment_out_of_service = mark_equipment_out_of_service
CinemaApp.show_maintenance_schedule = show_maintenance_schedule

# --- Operations: Rentals ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.rentals import (
    show_rentals_page,
    create_rental,
    confirm_rental,
    cancel_rental,
)
CinemaApp.show_rentals_page = show_rentals_page
CinemaApp.create_rental = create_rental
CinemaApp.confirm_rental = confirm_rental
CinemaApp.cancel_rental = cancel_rental

# --- Operations: Shift Scheduling ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.shift_scheduling import (
    show_shift_scheduling_page,
    add_shift,
    edit_shift,
    show_staff_availability,
    request_shift_swap,
    show_swap_requests,
    auto_schedule_shifts,
)
CinemaApp.show_shift_scheduling_page = show_shift_scheduling_page
CinemaApp.add_shift = add_shift
CinemaApp.edit_shift = edit_shift
CinemaApp.show_staff_availability = show_staff_availability
CinemaApp.request_shift_swap = request_shift_swap
CinemaApp.show_swap_requests = show_swap_requests
CinemaApp.auto_schedule_shifts = auto_schedule_shifts

# --- Operations: Events ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.events import (
    show_events_page,
    create_event,
)
CinemaApp.show_events_page = show_events_page
CinemaApp.create_event = create_event

# --- Operations: Corporate ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.corporate import (
    show_corporate_page,
    add_corporate,
)
CinemaApp.show_corporate_page = show_corporate_page
CinemaApp.add_corporate = add_corporate

# --- Operations: Lost & Found ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.operations.lost_found import (
    show_lost_found_page,
    set_lf_filter,
    log_found_item,
    search_lost_items,
    process_claim,
    view_lf_details,
    dispose_lf_item,
)
CinemaApp.show_lost_found_page = show_lost_found_page
CinemaApp.set_lf_filter = set_lf_filter
CinemaApp.log_found_item = log_found_item
CinemaApp.search_lost_items = search_lost_items
CinemaApp.process_claim = process_claim
CinemaApp.view_lf_details = view_lf_details
CinemaApp.dispose_lf_item = dispose_lf_item

# --- Reports: Sales Reports ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.sales_reports import (
    show_reports_page,
    generate_sales_summary,
    generate_revenue_by_movie,
    generate_daily_sales,
    generate_occupancy_report,
    generate_payment_methods_report,
    generate_booking_status_report,
    create_bar_chart,
    create_line_chart,
    create_pie_chart,
    export_report_csv,
    save_report_txt,
    email_report_to_admin,
    open_report_in_window,
)
CinemaApp.show_reports_page = show_reports_page
CinemaApp.generate_sales_summary = generate_sales_summary
CinemaApp.generate_revenue_by_movie = generate_revenue_by_movie
CinemaApp.generate_daily_sales = generate_daily_sales
CinemaApp.generate_occupancy_report = generate_occupancy_report
CinemaApp.generate_payment_methods_report = generate_payment_methods_report
CinemaApp.generate_booking_status_report = generate_booking_status_report
CinemaApp.create_bar_chart = create_bar_chart
CinemaApp.create_line_chart = create_line_chart
CinemaApp.create_pie_chart = create_pie_chart
CinemaApp.export_report_csv = export_report_csv
CinemaApp.save_report_txt = save_report_txt
CinemaApp.email_report_to_admin = email_report_to_admin
CinemaApp.open_report_in_window = open_report_in_window

# --- Reports: Analytics ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.analytics import show_analytics_page
CinemaApp.show_analytics_page = show_analytics_page

# --- Reports: Audit Log ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.audit_log import (
    load_audit_from_logs,
    show_audit_log_page,
    export_audit,
)
CinemaApp.load_audit_from_logs = load_audit_from_logs
CinemaApp.show_audit_log_page = show_audit_log_page
CinemaApp.export_audit = export_audit

# --- Reports: Incidents ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.incidents import (
    show_incidents_page,
    set_incident_filter,
    report_incident,
    view_incident_details,
    update_incident,
    show_incident_stats,
    export_incident_report,
)
CinemaApp.show_incidents_page = show_incidents_page
CinemaApp.set_incident_filter = set_incident_filter
CinemaApp.report_incident = report_incident
CinemaApp.view_incident_details = view_incident_details
CinemaApp.update_incident = update_incident
CinemaApp.show_incident_stats = show_incident_stats
CinemaApp.export_incident_report = export_incident_report

# --- Reports: Refunds ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.refunds import (
    show_refunds_page,
    refresh_cinema_refunds_list,
    process_cinema_refund,
    show_cinema_refund_method_dialog,
    _complete_cinema_refund,
    add_cinema_refund_to_student_account,
    send_cinema_refund_receipt,
    notify_cinema_finance_gui,
    view_cinema_booking_details,
    export_cinema_refunds_to_csv,
)
CinemaApp.show_refunds_page = show_refunds_page
CinemaApp.refresh_cinema_refunds_list = refresh_cinema_refunds_list
CinemaApp.process_cinema_refund = process_cinema_refund
CinemaApp.show_cinema_refund_method_dialog = show_cinema_refund_method_dialog
CinemaApp._complete_cinema_refund = _complete_cinema_refund
CinemaApp.add_cinema_refund_to_student_account = add_cinema_refund_to_student_account
CinemaApp.send_cinema_refund_receipt = send_cinema_refund_receipt
CinemaApp.notify_cinema_finance_gui = notify_cinema_finance_gui
CinemaApp.view_cinema_booking_details = view_cinema_booking_details
CinemaApp.export_cinema_refunds_to_csv = export_cinema_refunds_to_csv

# --- Special Features: Accessibility ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.special_features.accessibility import (
    show_accessible_page,
    configure_accessible_seats,
    view_accessible_bookings,
)
CinemaApp.show_accessible_page = show_accessible_page
CinemaApp.configure_accessible_seats = configure_accessible_seats
CinemaApp.view_accessible_bookings = view_accessible_bookings

# --- Special Features: Heatmap ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.special_features.heatmap import show_heatmap_page
CinemaApp.show_heatmap_page = show_heatmap_page

# --- Special Features: Theatre Layout ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.special_features.theatre_layout import show_theatre_layout_page
CinemaApp.show_theatre_layout_page = show_theatre_layout_page

# --- Special Features: Occupancy ---
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.special_features.occupancy import (
    show_occupancy_dashboard,
    toggle_occupancy_refresh,
    schedule_occupancy_refresh,
    refresh_occupancy_display,
    show_occupancy_seat_map,
)
CinemaApp.show_occupancy_dashboard = show_occupancy_dashboard
CinemaApp.toggle_occupancy_refresh = toggle_occupancy_refresh
CinemaApp.schedule_occupancy_refresh = schedule_occupancy_refresh
CinemaApp.refresh_occupancy_display = refresh_occupancy_display
CinemaApp.show_occupancy_seat_map = show_occupancy_seat_map
