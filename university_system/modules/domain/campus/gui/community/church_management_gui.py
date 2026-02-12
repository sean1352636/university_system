#!/usr/bin/env python3
"""
Church Management System - A comprehensive GUI application
Features: Help requests, donations, events, members management with user auth,
          payment integration, email receipts, and finance system integration.
Uses the central database for data persistence.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import json
import random
import logging

from university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

# Database schema for church management tables
CHURCH_MANAGEMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS church_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    join_date TEXT,
    membership_type TEXT,
    status TEXT DEFAULT 'Active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_name TEXT,
    donor_email TEXT,
    amount REAL,
    donation_type TEXT,
    payment_method TEXT,
    transaction_ref TEXT,
    date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    date TEXT,
    time TEXT,
    location TEXT,
    event_type TEXT,
    capacity INTEGER,
    registered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_prayer_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_name TEXT,
    request TEXT,
    category TEXT,
    status TEXT DEFAULT 'Pending',
    date TEXT,
    is_anonymous INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_sermons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    speaker TEXT,
    date TEXT,
    scripture TEXT,
    summary TEXT,
    video_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    date TEXT,
    priority TEXT,
    expires TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    ministry TEXT,
    availability TEXT,
    skills TEXT,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_date TEXT,
    service_type TEXT,
    attendance_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_small_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    leader TEXT,
    meeting_day TEXT,
    meeting_time TEXT,
    location TEXT,
    description TEXT,
    members TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    amount REAL,
    category TEXT,
    date TEXT,
    vendor TEXT,
    approved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_church_database():
    """Initialize church management database tables."""
    try:
        from university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            conn.executescript(CHURCH_MANAGEMENT_SCHEMA)
            conn.commit()
        logger.info("Church management database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize church database: {e}")
        return False


def get_current_user():
    """Get the current authenticated user from the system."""
    try:
        from university_system.infrastructure.shared_context import get_current_user as get_user
        user = get_user()
        if user:
            return user
    except ImportError:
        pass
    return None


def get_student_account_balance(student_id):
    """Get student's finance account balance."""
    try:
        from university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
        return get_student_finance_account_balance(student_id)
    except ImportError:
        return None


def process_student_payment(student_id, amount, description, transaction_ref):
    """Process payment from student account."""
    try:
        from university_system.modules.shared.utils.finance_integration import process_student_finance_account_payment
        return process_student_finance_account_payment(
            student_id=student_id,
            amount=amount,
            description=description,
            transaction_source="Church",
            transaction_ref=transaction_ref
        )
    except ImportError:
        return {'success': False, 'message': 'Finance integration not available'}


def record_revenue(student_id, amount, category, transaction_ref, payment_method, notes=None):
    """Record revenue to the central finance system."""
    try:
        from university_system.modules.shared.utils.finance_integration import record_revenue_to_finance
        return record_revenue_to_finance(
            student_id=student_id or "EXTERNAL",
            amount=amount,
            revenue_category=category,
            transaction_source="Church",
            transaction_ref=transaction_ref,
            payment_method=payment_method,
            notes=notes
        )
    except ImportError:
        logger.warning("Finance integration not available for revenue recording")
        return None


def send_receipt_email(recipient_email, recipient_name, amount, donation_type, transaction_ref, payment_method):
    """Send a donation receipt email."""
    # Validate email address before attempting to send
    if not recipient_email or not isinstance(recipient_email, str):
        logger.debug("No recipient email provided, skipping receipt")
        return False

    recipient_email = recipient_email.strip()
    if not recipient_email or '@' not in recipient_email:
        logger.debug(f"Invalid email address: {recipient_email}, skipping receipt")
        return False

    try:
        from university_system.infrastructure.email.email_service import send_email

        # Use email template
        try:
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template("church_donation_receipt", {
                "recipient_name": recipient_name,
                "transaction_ref": transaction_ref,
                "donation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "donation_type": donation_type,
                "payment_method": payment_method,
                "amount": f"{amount:.2f}"
            })
        except Exception as template_error:
            # Fallback to hardcoded email
            subject = f"Donation Receipt - Grace Community Church"
            body = f"""Dear {recipient_name},

Thank you for your generous donation to Grace Community Church!

════════════════════════════════════════════════════════
                    DONATION RECEIPT
════════════════════════════════════════════════════════

Transaction Details:
--------------------
Receipt Number:     {transaction_ref}
Date & Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Donation Type:      {donation_type}
Payment Method:     {payment_method}

Amount:             £{amount:.2f}

════════════════════════════════════════════════════════

"Each of you should give what you have decided in your heart to give,
not reluctantly or under compulsion, for God loves a cheerful giver."
- 2 Corinthians 9:7

Your contribution helps support our church's mission and community programs.
This receipt may be used for tax purposes.

If you have any questions about your donation, please contact us at:
Email: info@gracechurch.org
Phone: 555-0100

God bless you!

Grace Community Church
---
This is an automated receipt. Please keep this for your records.
"""
        result = send_email(recipient_email, subject, body)
        if result:
            logger.info(f"Donation receipt sent to {recipient_email}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to send receipt email: {e}")
        return False


class PaymentDialog(tk.Toplevel):
    """Dialog for selecting payment method and processing payment."""

    def __init__(self, parent, amount, description, current_user):
        super().__init__(parent)
        self.title(_t("church.payment.title"))
        self.geometry("450x400")
        self.configure(bg="white")
        self.resizable(False, False)
        self.transient(parent)

        self.amount = amount
        self.description = description
        self.current_user = current_user
        self.result = None
        self.student_balance = None

        # Get student identifier - use student_id if available, otherwise use username
        self.student_identifier = None
        if current_user:
            self.student_identifier = current_user.get('student_id') or current_user.get('username')

        # Get student balance if logged in
        if self.student_identifier:
            self.student_balance = get_student_account_balance(self.student_identifier)

        self.setup_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg="#4a4a8a", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="💰 " + _t("church.payment.select_method"), font=("Georgia", 16, "bold"),
                bg="#4a4a8a", fg="white").pack(pady=20)

        # Amount display
        amount_frame = tk.Frame(self, bg="white")
        amount_frame.pack(fill=tk.X, pady=20, padx=30)

        tk.Label(amount_frame, text=_t("church.payment.amount_due"), font=("Arial", 12),
                bg="white").pack(anchor="w")
        tk.Label(amount_frame, text=f"£{self.amount:.2f}", font=("Arial", 24, "bold"),
                bg="white", fg="#27ae60").pack(anchor="w")
        tk.Label(amount_frame, text=self.description, font=("Arial", 10),
                bg="white", fg="gray").pack(anchor="w")

        # Payment options
        options_frame = tk.Frame(self, bg="white")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        self.payment_var = tk.StringVar(value="cash")

        # Cash option
        cash_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        cash_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(cash_frame, text="💵 " + _t("church.payment.cash"), variable=self.payment_var, value="cash",
                      font=("Arial", 12), bg="#f5f5f5", activebackground="#f5f5f5",
                      cursor="hand2").pack(anchor="w", padx=15, pady=10)

        # Card option
        card_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        card_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(card_frame, text="💳 " + _t("church.payment.card"), variable=self.payment_var, value="card",
                      font=("Arial", 12), bg="#f5f5f5", activebackground="#f5f5f5",
                      cursor="hand2").pack(anchor="w", padx=15, pady=10)

        # Student Account option (available for all logged in users)
        if self.current_user and self.student_identifier:
            account_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
            account_frame.pack(fill=tk.X, pady=5)

            account_text = "🎓 " + _t("church.payment.student_account")
            if self.student_balance is not None:
                account_text += f" ({_t('church.payment.balance', amount=f'£{self.student_balance:.2f}')})"
                if self.student_balance < self.amount:
                    account_text += " - " + _t("church.payment.insufficient")
            else:
                account_text += " (" + _t("church.payment.no_account") + ")"

            rb = tk.Radiobutton(account_frame, text=account_text, variable=self.payment_var,
                               value="student_account", font=("Arial", 12), bg="#f5f5f5",
                               activebackground="#f5f5f5", cursor="hand2")
            rb.pack(anchor="w", padx=15, pady=10)

            # Disable if no account or insufficient balance
            if self.student_balance is None or self.student_balance < self.amount:
                rb.config(state=tk.DISABLED)

        # Buttons
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(fill=tk.X, padx=30, pady=20)

        tk.Button(btn_frame, text=_t("church.payment.cancel"), command=self.destroy,
                 bg="#e74c3c", fg="white", font=("Arial", 11), width=12,
                 cursor="hand2").pack(side=tk.RIGHT)

        tk.Button(btn_frame, text=_t("church.payment.pay_now"), command=self.process_payment,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"), width=12,
                 cursor="hand2").pack(side=tk.RIGHT, padx=10)

    def process_payment(self):
        payment_method = self.payment_var.get()
        transaction_ref = f"CHURCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if payment_method == "student_account":
            # Process through student finance account
            result = process_student_payment(self.student_identifier, self.amount, self.description, transaction_ref)

            if result.get('success'):
                self.result = {
                    'success': True,
                    'payment_method': 'Student Account',
                    'transaction_ref': transaction_ref,
                    'new_balance': result.get('new_balance')
                }
            else:
                messagebox.showerror(_t("church.payment.payment_failed"), result.get('message', _t("common.unknown_error")))
                return
        else:
            # Cash or card - just record it
            self.result = {
                'success': True,
                'payment_method': payment_method.title(),
                'transaction_ref': transaction_ref
            }

        self.destroy()


class ChurchManagementSystem:
    def __init__(self, root, current_user=None):
        self.root = root
        self.root.title(_t("church.window_title"))
        self.root.geometry("1200x800")
        self.root.configure(bg="#f5f5dc")

        # Get current user - require login
        self.current_user = current_user or get_current_user()

        if not self.current_user:
            messagebox.showerror(_t("church.errors.access_denied"),
                               _t("church.errors.login_required"))
            self.root.destroy()
            return

        # Data storage
        self.members = []
        self.donations = []
        self.events = []
        self.prayer_requests = []
        self.sermons = []
        self.announcements = []
        self.volunteers = []
        self.attendance_records = []
        self.small_groups = []
        self.expenses = []

        # Load existing data
        self.load_data()

        # Create main UI
        self.create_header()
        self.create_navigation()
        self.create_main_content()
        self.create_footer()

        # Show dashboard by default
        self.show_dashboard()

    def get_user_display_name(self):
        """Get display name for current user."""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            return name or self.current_user.get('username', 'User')
        return 'Guest'

    def get_user_email(self):
        """Get email for current user."""
        if self.current_user:
            return self.current_user.get('email', '')
        return ''

    def create_header(self):
        """Create the application header with church name and user info."""
        header_frame = tk.Frame(self.root, bg="#4a4a8a", height=100)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        # Church icon (cross symbol)
        cross_label = tk.Label(
            header_frame,
            text="✝",
            font=("Arial", 48),
            fg="gold",
            bg="#4a4a8a"
        )
        cross_label.pack(side=tk.LEFT, padx=20)

        # Church name
        title_label = tk.Label(
            header_frame,
            text=_t("church.church_name"),
            font=("Georgia", 28, "bold"),
            fg="white",
            bg="#4a4a8a"
        )
        title_label.pack(side=tk.LEFT, padx=10)

        # Right side - user info and time
        right_frame = tk.Frame(header_frame, bg="#4a4a8a")
        right_frame.pack(side=tk.RIGHT, padx=20)

        # User info
        user_name = self.get_user_display_name()
        user_role = self.current_user.get('role', 'member').title()
        tk.Label(right_frame, text=_t("church.common.welcome", name=user_name), font=("Arial", 11, "bold"),
                fg="white", bg="#4a4a8a").pack(anchor="e")
        tk.Label(right_frame, text=f"({user_role})", font=("Arial", 9),
                fg="#d0d0d0", bg="#4a4a8a").pack(anchor="e")

        # Current date/time
        self.time_label = tk.Label(
            right_frame,
            text="",
            font=("Arial", 10),
            fg="white",
            bg="#4a4a8a"
        )
        self.time_label.pack(anchor="e", pady=(5, 0))
        self.update_time()

    def update_time(self):
        """Update the time display in the header."""
        current_time = datetime.now().strftime("%A, %B %d, %Y | %I:%M %p")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def create_navigation(self):
        """Create the side navigation menu."""
        self.nav_frame = tk.Frame(self.root, bg="#6a6aaa", width=200)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.nav_frame.pack_propagate(False)

        nav_buttons = [
            (_t("church.nav.dashboard"), self.show_dashboard),
            (_t("church.nav.members"), self.show_members),
            (_t("church.nav.donations"), self.show_donations),
            (_t("church.nav.events"), self.show_events),
            (_t("church.nav.prayer_requests"), self.show_prayer_requests),
            (_t("church.nav.sermons"), self.show_sermons),
            (_t("church.nav.announcements"), self.show_announcements),
            (_t("church.nav.volunteers"), self.show_volunteers),
            (_t("church.nav.attendance"), self.show_attendance),
            (_t("church.nav.small_groups"), self.show_small_groups),
            (_t("church.nav.expenses"), self.show_expenses),
            (_t("church.nav.reports"), self.show_reports),
        ]

        for text, command in nav_buttons:
            btn = tk.Button(
                self.nav_frame,
                text=text,
                font=("Arial", 11),
                bg="#5a5a9a",
                fg="white",
                activebackground="#7a7aba",
                activeforeground="white",
                relief=tk.FLAT,
                anchor="w",
                padx=15,
                pady=10,
                command=command,
                cursor="hand2"
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#7a7aba"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#5a5a9a"))

    def create_main_content(self):
        """Create the main content area."""
        self.main_frame = tk.Frame(self.root, bg="#f5f5dc")
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.content_frame = tk.Frame(self.main_frame, bg="white", relief=tk.RAISED, bd=2)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def create_footer(self):
        """Create the application footer."""
        footer_frame = tk.Frame(self.root, bg="#4a4a8a", height=30)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        footer_label = tk.Label(
            footer_frame,
            text=_t("church.footer_text"),
            font=("Arial", 9),
            fg="white",
            bg="#4a4a8a"
        )
        footer_label.pack(pady=5)

    def clear_content(self):
        """Clear the main content area."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        """Display the main dashboard with statistics."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.dashboard.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Statistics frame
        stats_frame = tk.Frame(self.content_frame, bg="white")
        stats_frame.pack(pady=20)

        stats = [
            (_t("church.dashboard.total_members"), len(self.members), "#3498db"),
            (_t("church.dashboard.total_donations"), f"£{sum(d['amount'] for d in self.donations):,.2f}", "#27ae60"),
            (_t("church.dashboard.upcoming_events"), len([e for e in self.events if e.get('date', '') >= datetime.now().strftime('%Y-%m-%d')]), "#e74c3c"),
            (_t("church.dashboard.prayer_requests"), len(self.prayer_requests), "#9b59b6"),
            (_t("church.dashboard.active_volunteers"), len(self.volunteers), "#f39c12"),
            (_t("church.dashboard.small_groups"), len(self.small_groups), "#1abc9c"),
        ]

        for i, (label, value, color) in enumerate(stats):
            row, col = divmod(i, 3)
            stat_card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, bd=2)
            stat_card.grid(row=row, column=col, padx=15, pady=15, ipadx=30, ipady=20)

            tk.Label(stat_card, text=label, font=("Arial", 12), bg=color, fg="white").pack()
            tk.Label(stat_card, text=str(value), font=("Arial", 24, "bold"), bg=color, fg="white").pack()

        # Quick verse
        verses = [
            '"For where two or three gather in my name, there am I with them." - Matthew 18:20',
            '"Love one another as I have loved you." - John 13:34',
            '"The Lord is my shepherd; I shall not want." - Psalm 23:1',
            '"I can do all things through Christ who strengthens me." - Philippians 4:13',
        ]
        verse_frame = tk.Frame(self.content_frame, bg="#fff8dc", relief=tk.GROOVE, bd=2)
        verse_frame.pack(pady=30, padx=50, fill=tk.X)
        tk.Label(
            verse_frame,
            text=_t("church.dashboard.verse_of_the_day"),
            font=("Georgia", 14, "bold"),
            bg="#fff8dc",
            fg="#8b4513"
        ).pack(pady=10)
        tk.Label(
            verse_frame,
            text=random.choice(verses),
            font=("Georgia", 12, "italic"),
            bg="#fff8dc",
            fg="#5d4037",
            wraplength=600
        ).pack(pady=10)

    def show_members(self):
        """Display member management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.members.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Buttons frame
        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.members.add_member"), command=self.add_member,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.members.edit_member"), command=self.edit_member,
                  bg="#3498db", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.members.delete_member"), command=self.delete_member,
                  bg="#e74c3c", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Members list
        columns = ("ID", "Name", "Email", "Phone", "Join Date", "Status")
        self.member_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.member_tree.heading(col, text=col)
            self.member_tree.column(col, width=120)

        for i, member in enumerate(self.members, 1):
            self.member_tree.insert("", tk.END, values=(
                i, member['name'], member['email'], member['phone'],
                member['join_date'], member['status']
            ))

        scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.member_tree.yview)
        self.member_tree.configure(yscrollcommand=scrollbar.set)

        self.member_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def add_member(self):
        """Add a new member - auto-fill with current user info."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.members.add_new_member"))
        dialog.geometry("400x400")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        # Pre-fill with current user info
        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        fields = [
            ("Name:", default_name),
            ("Email:", default_email),
            ("Phone:", ""),
            ("Address:", ""),
        ]
        entries = {}

        for i, (field, default) in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        # Status dropdown
        tk.Label(dialog, text=_t("church.members.fields.status"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        status_combo = ttk.Combobox(dialog, values=["Active", "Inactive", "Visitor"], width=27)
        status_combo.set("Active")
        status_combo.grid(row=4, column=1, padx=20, pady=10)
        entries["Status:"] = status_combo

        def save():
            member = {
                'name': entries["Name:"].get(),
                'email': entries["Email:"].get(),
                'phone': entries["Phone:"].get(),
                'address': entries["Address:"].get(),
                'status': entries["Status:"].get(),
                'join_date': datetime.now().strftime("%Y-%m-%d"),
                'added_by': self.current_user.get('username', 'Unknown')
            }
            if member['name']:
                self.members.append(member)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.members.success_added", name=member['name']))
                dialog.destroy()
                self.show_members()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.name_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=5, column=0, columnspan=2, pady=20)

    def edit_member(self):
        """Edit an existing member's information."""
        selection = self.member_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_member"))
            return

        item = self.member_tree.item(selection[0])
        idx = int(item['values'][0]) - 1
        member = self.members[idx]

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.members.edit_member_title"))
        dialog.geometry("400x400")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = [("Name:", member['name']), ("Email:", member['email']),
                  ("Phone:", member['phone']), ("Address:", member.get('address', ''))]
        entries = {}

        for i, (field, value) in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.insert(0, value)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        tk.Label(dialog, text=_t("church.members.fields.status"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        status_combo = ttk.Combobox(dialog, values=["Active", "Inactive", "Visitor"], width=27)
        status_combo.set(member['status'])
        status_combo.grid(row=4, column=1, padx=20, pady=10)
        entries["Status:"] = status_combo

        def save():
            self.members[idx] = {
                'name': entries["Name:"].get(),
                'email': entries["Email:"].get(),
                'phone': entries["Phone:"].get(),
                'address': entries["Address:"].get(),
                'status': entries["Status:"].get(),
                'join_date': member['join_date']
            }
            self.save_data()
            messagebox.showinfo(_t("church.common.success"), _t("church.members.success_updated"))
            dialog.destroy()
            self.show_members()

        tk.Button(dialog, text=_t("church.common.save_changes"), command=save, bg="#3498db", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=5, column=0, columnspan=2, pady=20)

    def delete_member(self):
        """Delete a member from the church."""
        selection = self.member_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_member_delete"))
            return

        item = self.member_tree.item(selection[0])
        idx = int(item['values'][0]) - 1
        name = self.members[idx]['name']

        if messagebox.askyesno(_t("church.common.confirm_delete"), _t("church.members.confirm_delete", name=name)):
            del self.members[idx]
            self.save_data()
            messagebox.showinfo(_t("church.common.success"), _t("church.members.success_deleted"))
            self.show_members()

    def show_donations(self):
        """Display donation management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.donations.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Total donations
        total = sum(d['amount'] for d in self.donations)
        tk.Label(
            self.content_frame,
            text=_t("church.donations.total_donations", amount=f"£{total:,.2f}"),
            font=("Arial", 18, "bold"),
            bg="white",
            fg="#27ae60"
        ).pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.donations.record_donation"), command=self.add_donation,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Donations list
        columns = ("ID", "Donor", "Amount", "Date", "Type", "Payment Method")
        self.donation_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.donation_tree.heading(col, text=col)
            self.donation_tree.column(col, width=120)

        for i, donation in enumerate(self.donations, 1):
            self.donation_tree.insert("", tk.END, values=(
                i, donation['donor'], f"£{donation['amount']:,.2f}",
                donation['date'], donation['type'], donation.get('payment_method', 'Cash')
            ))

        self.donation_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_donation(self):
        """Record a new donation with payment processing."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.donations.record_title"))
        dialog.geometry("450x450")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        # Pre-fill with current user info
        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        tk.Label(dialog, text=_t("church.donations.record_title"), font=("Georgia", 16, "bold"),
                bg="white", fg="#4a4a8a").pack(pady=15)

        form_frame = tk.Frame(dialog, bg="white")
        form_frame.pack(padx=30, fill=tk.X)

        # Donor info (read-only, from current user)
        tk.Label(form_frame, text=_t("church.donations.fields.donor"), bg="white", font=("Arial", 11)).grid(row=0, column=0, pady=10, sticky="e")
        donor_label = tk.Label(form_frame, text=default_name, bg="#f0f0f0", font=("Arial", 11),
                              padx=10, pady=5, anchor="w", width=25)
        donor_label.grid(row=0, column=1, pady=10, padx=10, sticky="w")

        tk.Label(form_frame, text=_t("church.donations.fields.email"), bg="white", font=("Arial", 11)).grid(row=1, column=0, pady=10, sticky="e")
        email_label = tk.Label(form_frame, text=default_email or "Not provided", bg="#f0f0f0",
                              font=("Arial", 11), padx=10, pady=5, anchor="w", width=25)
        email_label.grid(row=1, column=1, pady=10, padx=10, sticky="w")

        # Amount
        tk.Label(form_frame, text=_t("church.donations.fields.amount"), bg="white", font=("Arial", 11)).grid(row=2, column=0, pady=10, sticky="e")
        amount_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        amount_entry.grid(row=2, column=1, pady=10, padx=10)

        # Type
        tk.Label(form_frame, text=_t("church.donations.fields.type"), bg="white", font=("Arial", 11)).grid(row=3, column=0, pady=10, sticky="e")
        type_combo = ttk.Combobox(form_frame, values=["Tithe", "Offering", "Building Fund", "Missions", "Other"], width=27)
        type_combo.set("Tithe")
        type_combo.grid(row=3, column=1, pady=10, padx=10)

        # Notes
        tk.Label(form_frame, text=_t("church.donations.fields.notes"), bg="white", font=("Arial", 11)).grid(row=4, column=0, pady=10, sticky="e")
        notes_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        notes_entry.grid(row=4, column=1, pady=10, padx=10)

        def process_donation():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    messagebox.showerror("Error", "Please enter a valid amount!")
                    return

                # Open payment dialog
                payment_dialog = PaymentDialog(dialog, amount, f"{type_combo.get()} Donation", self.current_user)
                dialog.wait_window(payment_dialog)

                if payment_dialog.result and payment_dialog.result.get('success'):
                    transaction_ref = payment_dialog.result['transaction_ref']
                    payment_method = payment_dialog.result['payment_method']

                    # Record donation
                    donation = {
                        'donor': default_name,
                        'donor_email': default_email,
                        'donor_id': self.current_user.get('student_id') or self.current_user.get('username'),
                        'amount': amount,
                        'type': type_combo.get(),
                        'notes': notes_entry.get(),
                        'date': datetime.now().strftime("%Y-%m-%d"),
                        'payment_method': payment_method,
                        'transaction_ref': transaction_ref
                    }
                    self.donations.append(donation)
                    self.save_data()

                    # Record to finance system
                    record_revenue(
                        student_id=self.current_user.get('student_id'),
                        amount=amount,
                        category=f"Church {type_combo.get()}",
                        transaction_ref=transaction_ref,
                        payment_method=payment_method,
                        notes=f"Donation from {default_name}"
                    )

                    # Send receipt email
                    if default_email:
                        send_receipt_email(default_email, default_name, amount,
                                         type_combo.get(), transaction_ref, payment_method)

                    # Show success with balance update if student account
                    success_msg = _t("church.donations.success_recorded", amount=f"£{amount:.2f}", receipt=transaction_ref)
                    if 'new_balance' in payment_dialog.result:
                        success_msg += _t("church.donations.new_balance", balance=f"£{payment_dialog.result['new_balance']:.2f}")

                    messagebox.showinfo(_t("church.common.success"), success_msg)
                    dialog.destroy()
                    self.show_donations()

            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_amount"))

        tk.Button(dialog, text=_t("church.donations.continue_payment"), command=process_donation,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"), width=20,
                 cursor="hand2").pack(pady=25)

    def show_events(self):
        """Display event management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.events.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.events.add_event"), command=self.add_event,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Events list
        columns = ("ID", "Event Name", "Date", "Time", "Location", "Description")
        self.event_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.event_tree.heading(col, text=col)
            self.event_tree.column(col, width=130)

        for i, event in enumerate(self.events, 1):
            self.event_tree.insert("", tk.END, values=(
                i, event['name'], event['date'], event['time'],
                event['location'], event.get('description', '')[:30]
            ))

        self.event_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_event(self):
        """Add a new church event."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.events.add_new_event"))
        dialog.geometry("400x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = ["Event Name:", "Date (YYYY-MM-DD):", "Time:", "Location:", "Description:"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            event = {
                'name': entries["Event Name:"].get(),
                'date': entries["Date (YYYY-MM-DD):"].get(),
                'time': entries["Time:"].get(),
                'location': entries["Location:"].get(),
                'description': entries["Description:"].get(),
                'created_by': self.current_user.get('username', 'Unknown')
            }
            if event['name'] and event['date']:
                self.events.append(event)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.events.success_added"))
                dialog.destroy()
                self.show_events()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.event_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)

    def show_prayer_requests(self):
        """Display prayer requests interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.prayer_requests.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.prayer_requests.add_request"), command=self.add_prayer_request,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.prayer_requests.mark_answered"), command=self.mark_prayer_answered,
                  bg="#9b59b6", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Prayer requests list
        columns = ("ID", "Requested By", "Request", "Date", "Status")
        self.prayer_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.prayer_tree.heading(col, text=col)
            self.prayer_tree.column(col, width=150)

        for i, prayer in enumerate(self.prayer_requests, 1):
            self.prayer_tree.insert("", tk.END, values=(
                i, prayer['requested_by'], prayer['request'][:40],
                prayer['date'], prayer['status']
            ))

        self.prayer_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_prayer_request(self):
        """Add a new prayer request - uses current user."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.prayer_requests.add_title"))
        dialog.geometry("450x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        default_name = self.get_user_display_name()

        tk.Label(dialog, text=_t("church.prayer_requests.fields.requester"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        name_label = tk.Label(dialog, text=default_name, bg="#f0f0f0", font=("Arial", 11),
                             padx=10, pady=5, width=30, anchor="w")
        name_label.grid(row=0, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.prayer_requests.fields.request"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="ne")
        request_text = tk.Text(dialog, width=35, height=8)
        request_text.grid(row=1, column=1, padx=20, pady=10)

        def save():
            prayer = {
                'requested_by': default_name,
                'requester_id': self.current_user.get('username'),
                'request': request_text.get("1.0", tk.END).strip(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'status': "Active"
            }
            if prayer['request']:
                self.prayer_requests.append(prayer)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.prayer_requests.success_added"))
                dialog.destroy()
                self.show_prayer_requests()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.prayer_required"))

        tk.Button(dialog, text=_t("church.prayer_requests.submit_request"), command=save, bg="#9b59b6", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=2, column=0, columnspan=2, pady=20)

    def mark_prayer_answered(self):
        """Mark a prayer request as answered."""
        selection = self.prayer_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_prayer"))
            return

        item = self.prayer_tree.item(selection[0])
        idx = int(item['values'][0]) - 1

        self.prayer_requests[idx]['status'] = "Answered"
        self.save_data()
        messagebox.showinfo(_t("church.prayer_requests.praise_god"), _t("church.prayer_requests.success_answered"))
        self.show_prayer_requests()

    def show_sermons(self):
        """Display sermon management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.sermons.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.sermons.add_sermon"), command=self.add_sermon,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Sermons list
        columns = ("ID", "Title", "Speaker", "Date", "Scripture", "Series")
        self.sermon_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.sermon_tree.heading(col, text=col)
            self.sermon_tree.column(col, width=130)

        for i, sermon in enumerate(self.sermons, 1):
            self.sermon_tree.insert("", tk.END, values=(
                i, sermon['title'], sermon['speaker'],
                sermon['date'], sermon['scripture'], sermon.get('series', '')
            ))

        self.sermon_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_sermon(self):
        """Add a new sermon to the archive."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.sermons.add_title"))
        dialog.geometry("400x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = ["Title:", "Speaker:", "Date (YYYY-MM-DD):", "Scripture:", "Series:"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            sermon = {
                'title': entries["Title:"].get(),
                'speaker': entries["Speaker:"].get(),
                'date': entries["Date (YYYY-MM-DD):"].get(),
                'scripture': entries["Scripture:"].get(),
                'series': entries["Series:"].get()
            }
            if sermon['title']:
                self.sermons.append(sermon)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.sermons.success_added"))
                dialog.destroy()
                self.show_sermons()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.title_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)

    def show_announcements(self):
        """Display church announcements."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.announcements.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.announcements.add_announcement"), command=self.add_announcement,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Announcements display
        announcements_frame = tk.Frame(self.content_frame, bg="white")
        announcements_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(announcements_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(announcements_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for announcement in self.announcements:
            ann_frame = tk.Frame(scrollable_frame, bg="#fff8dc", relief=tk.RAISED, bd=1)
            ann_frame.pack(fill=tk.X, pady=5, padx=10)

            tk.Label(ann_frame, text=announcement['title'], font=("Arial", 12, "bold"),
                    bg="#fff8dc", fg="#8b4513").pack(anchor="w", padx=10, pady=5)
            tk.Label(ann_frame, text=announcement['content'], font=("Arial", 10),
                    bg="#fff8dc", fg="#5d4037", wraplength=600, justify="left").pack(anchor="w", padx=10)
            tk.Label(ann_frame, text=f"Posted: {announcement['date']} by {announcement.get('posted_by', 'Admin')}",
                    font=("Arial", 8), bg="#fff8dc", fg="gray").pack(anchor="e", padx=10, pady=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def add_announcement(self):
        """Add a new church announcement."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.announcements.add_title"))
        dialog.geometry("500x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text=_t("church.announcements.fields.title"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        title_entry = tk.Entry(dialog, width=40)
        title_entry.grid(row=0, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.announcements.fields.content"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="ne")
        content_text = tk.Text(dialog, width=40, height=8)
        content_text.grid(row=1, column=1, padx=20, pady=10)

        def save():
            announcement = {
                'title': title_entry.get(),
                'content': content_text.get("1.0", tk.END).strip(),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'posted_by': self.get_user_display_name()
            }
            if announcement['title'] and announcement['content']:
                self.announcements.insert(0, announcement)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.announcements.success_posted"))
                dialog.destroy()
                self.show_announcements()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.fill_all_fields"))

        tk.Button(dialog, text=_t("church.announcements.post_announcement"), command=save, bg="#e74c3c", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=2, column=0, columnspan=2, pady=20)

    def show_volunteers(self):
        """Display volunteer management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.volunteers.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.volunteers.add_volunteer"), command=self.add_volunteer,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Volunteers list
        columns = ("ID", "Name", "Ministry", "Role", "Phone", "Email", "Availability")
        self.volunteer_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.volunteer_tree.heading(col, text=col)
            self.volunteer_tree.column(col, width=110)

        for i, vol in enumerate(self.volunteers, 1):
            self.volunteer_tree.insert("", tk.END, values=(
                i, vol['name'], vol['ministry'], vol['role'],
                vol['phone'], vol['email'], vol['availability']
            ))

        self.volunteer_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_volunteer(self):
        """Add a new volunteer - uses current user info."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.volunteers.add_title"))
        dialog.geometry("450x450")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        entries = {}

        tk.Label(dialog, text=_t("church.volunteers.fields.name"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        name_entry = tk.Entry(dialog, width=30)
        name_entry.insert(0, default_name)
        name_entry.grid(row=0, column=1, padx=20, pady=10)
        entries["Name:"] = name_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.ministry"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="e")
        ministry_combo = ttk.Combobox(dialog, values=["Worship", "Children's", "Youth", "Hospitality", "Tech", "Missions", "Other"], width=27)
        ministry_combo.set("Worship")
        ministry_combo.grid(row=1, column=1, padx=20, pady=10)
        entries["Ministry:"] = ministry_combo

        tk.Label(dialog, text=_t("church.volunteers.fields.role"), bg="white", font=("Arial", 11)).grid(row=2, column=0, padx=20, pady=10, sticky="e")
        role_entry = tk.Entry(dialog, width=30)
        role_entry.grid(row=2, column=1, padx=20, pady=10)
        entries["Role:"] = role_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.phone"), bg="white", font=("Arial", 11)).grid(row=3, column=0, padx=20, pady=10, sticky="e")
        phone_entry = tk.Entry(dialog, width=30)
        phone_entry.grid(row=3, column=1, padx=20, pady=10)
        entries["Phone:"] = phone_entry

        tk.Label(dialog, text=_t("church.donations.fields.email"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        email_entry = tk.Entry(dialog, width=30)
        email_entry.insert(0, default_email)
        email_entry.grid(row=4, column=1, padx=20, pady=10)
        entries["Email:"] = email_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.availability"), bg="white", font=("Arial", 11)).grid(row=5, column=0, padx=20, pady=10, sticky="e")
        avail_combo = ttk.Combobox(dialog, values=["Sundays", "Weekdays", "Weekends", "Flexible"], width=27)
        avail_combo.set("Sundays")
        avail_combo.grid(row=5, column=1, padx=20, pady=10)
        entries["Availability:"] = avail_combo

        def save():
            volunteer = {
                'name': entries["Name:"].get(),
                'ministry': entries["Ministry:"].get(),
                'role': entries["Role:"].get(),
                'phone': entries["Phone:"].get(),
                'email': entries["Email:"].get(),
                'availability': entries["Availability:"].get()
            }
            if volunteer['name']:
                self.volunteers.append(volunteer)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.volunteers.success_added"))
                dialog.destroy()
                self.show_volunteers()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.name_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=6, column=0, columnspan=2, pady=20)

    def show_attendance(self):
        """Display attendance tracking interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.attendance.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        tk.Label(self.content_frame, text=_t("church.attendance.description"),
                font=("Arial", 12), bg="white", fg="gray").pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=_t("church.attendance.record_attendance"),
                  command=self.record_attendance,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Attendance history
        columns = ("Date", "Service", "Adults", "Children", "Total", "Notes")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        for record in self.attendance_records:
            tree.insert("", tk.END, values=(
                record['date'], record['service'], record['adults'],
                record['children'], record['adults'] + record['children'], record.get('notes', '')
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def record_attendance(self):
        """Record attendance for a service."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.attendance.record_title"))
        dialog.geometry("400x300")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text=_t("church.attendance.fields.service"), bg="white").grid(row=0, column=0, padx=20, pady=10)
        service = ttk.Combobox(dialog, values=["Sunday Morning", "Sunday Evening", "Wednesday", "Special Event"])
        service.grid(row=0, column=1, padx=20, pady=10)
        service.set("Sunday Morning")

        tk.Label(dialog, text=_t("church.attendance.fields.adults"), bg="white").grid(row=1, column=0, padx=20, pady=10)
        adults = tk.Entry(dialog)
        adults.grid(row=1, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.attendance.fields.children"), bg="white").grid(row=2, column=0, padx=20, pady=10)
        children = tk.Entry(dialog)
        children.grid(row=2, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.donations.fields.notes"), bg="white").grid(row=3, column=0, padx=20, pady=10)
        notes = tk.Entry(dialog, width=30)
        notes.grid(row=3, column=1, padx=20, pady=10)

        def save():
            try:
                record = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'service': service.get(),
                    'adults': int(adults.get() or 0),
                    'children': int(children.get() or 0),
                    'notes': notes.get(),
                    'recorded_by': self.current_user.get('username', 'Unknown')
                }
                self.attendance_records.append(record)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.attendance.success_recorded"))
                dialog.destroy()
                self.show_attendance()
            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_numbers"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                 cursor="hand2").grid(row=4, column=0, columnspan=2, pady=20)

    def show_small_groups(self):
        """Display small groups management."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.small_groups.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.small_groups.add_group"),
                  command=self.add_small_group,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        columns = ("ID", "Group Name", "Leader", "Meeting Day", "Location", "Members")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        for i, group in enumerate(self.small_groups, 1):
            tree.insert("", tk.END, values=(
                i, group['name'], group['leader'], group['meeting_day'],
                group['location'], group.get('member_count', 0)
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_small_group(self):
        """Add a new small group."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.small_groups.add_title"))
        dialog.geometry("400+350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"400x350+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = ["Group Name:", "Leader:", "Meeting Day:", "Location:", "Member Count:"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field, bg="white").grid(row=i, column=0, padx=20, pady=10, sticky="e")
            if field == "Meeting Day:":
                entry = ttk.Combobox(dialog, values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            else:
                entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            group = {
                'name': entries["Group Name:"].get(),
                'leader': entries["Leader:"].get(),
                'meeting_day': entries["Meeting Day:"].get(),
                'location': entries["Location:"].get(),
                'member_count': int(entries["Member Count:"].get() or 0)
            }
            if group['name']:
                self.small_groups.append(group)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.small_groups.success_added"))
                dialog.destroy()
                self.show_small_groups()

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                 cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)

    def show_expenses(self):
        """Display expense tracking."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.expenses.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        total = sum(e['amount'] for e in self.expenses)
        tk.Label(self.content_frame, text=_t("church.expenses.total_expenses", amount=f"£{total:,.2f}"),
                font=("Arial", 18, "bold"), bg="white", fg="#e74c3c").pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.expenses.add_expense"),
                  command=self.add_expense,
                  bg="#e74c3c", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        columns = ("ID", "Description", "Amount", "Category", "Date", "Approved By")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        for i, expense in enumerate(self.expenses, 1):
            tree.insert("", tk.END, values=(
                i, expense['description'], f"£{expense['amount']:,.2f}",
                expense['category'], expense['date'], expense.get('approved_by', '')
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def add_expense(self):
        """Add a new expense."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.expenses.add_title"))
        dialog.geometry("400x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = {
            "Description:": None,
            "Amount (£):": None,
            "Category:": ["Utilities", "Supplies", "Salaries", "Maintenance", "Missions", "Events", "Other"],
            "Approved By:": None
        }
        entries = {}

        for i, (field, options) in enumerate(fields.items()):
            tk.Label(dialog, text=field, bg="white").grid(row=i, column=0, padx=20, pady=10, sticky="e")
            if options:
                entry = ttk.Combobox(dialog, values=options, width=27)
                entry.set(options[0])
            else:
                entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            try:
                expense = {
                    'description': entries["Description:"].get(),
                    'amount': float(entries["Amount (£):"].get()),
                    'category': entries["Category:"].get(),
                    'approved_by': entries["Approved By:"].get() or self.get_user_display_name(),
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'recorded_by': self.current_user.get('username', 'Unknown')
                }
                self.expenses.append(expense)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.expenses.success_recorded"))
                dialog.destroy()
                self.show_expenses()
            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_amount"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#e74c3c", fg="white",
                 cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)

    def show_reports(self):
        """Display reports overview with option to view full report in new window."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.reports.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Quick Stats Overview
        stats_frame = tk.Frame(self.content_frame, bg="white")
        stats_frame.pack(pady=20)

        total_donations = sum(d['amount'] for d in self.donations)
        total_expenses = sum(e['amount'] for e in self.expenses)
        balance = total_donations - total_expenses

        stats = [
            (_t("church.reports.total_donations", amount=""), f"£{total_donations:,.2f}", "#27ae60"),
            (_t("church.reports.total_expenses", amount=""), f"£{total_expenses:,.2f}", "#e74c3c"),
            (_t("church.reports.net_balance", amount=""), f"£{balance:,.2f}", "#27ae60" if balance >= 0 else "#e74c3c"),
            (_t("church.reports.total_members", count=""), str(len(self.members)), "#3498db"),
        ]

        for i, (label, value, color) in enumerate(stats):
            stat_card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, bd=2)
            stat_card.grid(row=0, column=i, padx=10, pady=10, ipadx=20, ipady=15)
            tk.Label(stat_card, text=label.replace(": ", "").replace(":", ""), font=("Arial", 10), bg=color, fg="white").pack()
            tk.Label(stat_card, text=value, font=("Arial", 18, "bold"), bg=color, fg="white").pack()

        # Description
        tk.Label(self.content_frame, text=_t("church.reports.view_full_description"),
                font=("Arial", 11), bg="white", fg="gray").pack(pady=20)

        # Button to open full report in new window
        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=_t("church.reports.view_full_report"), command=self.open_report_window,
                  bg="#4a4a8a", fg="white", font=("Arial", 12, "bold"), width=25, height=2,
                  cursor="hand2").pack()

    def open_report_window(self):
        """Open the full report in a separate window with save and send options."""
        report_window = tk.Toplevel(self.root)
        report_window.title(_t("church.reports.window_title"))
        report_window.geometry("800x700")
        report_window.configure(bg="white")

        # Header
        header = tk.Frame(report_window, bg="#4a4a8a", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="✝ " + _t("church.reports.report_header"),
                font=("Georgia", 18, "bold"), bg="#4a4a8a", fg="white").pack(pady=20)

        # Report content in scrollable text area
        content_frame = tk.Frame(report_window, bg="white")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        text_scrollbar = ttk.Scrollbar(content_frame)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text = tk.Text(content_frame, wrap=tk.WORD, font=("Courier", 11),
                                   yscrollcommand=text_scrollbar.set, bg="#f9f9f9")
        self.report_text.pack(fill=tk.BOTH, expand=True)
        text_scrollbar.config(command=self.report_text.yview)

        # Generate report content
        report_content = self.generate_report_text()
        self.report_text.insert(tk.END, report_content)
        self.report_text.config(state=tk.DISABLED)

        # Buttons frame
        btn_frame = tk.Frame(report_window, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Button(btn_frame, text=_t("church.reports.save_as_txt"), command=self.save_report_as_txt,
                  bg="#27ae60", fg="white", font=("Arial", 11), width=18,
                  cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text=_t("church.reports.send_to_admin"), command=self.send_report_to_admin,
                  bg="#3498db", fg="white", font=("Arial", 11), width=18,
                  cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text=_t("church.common.close"), command=report_window.destroy,
                  bg="#95a5a6", fg="white", font=("Arial", 11), width=12,
                  cursor="hand2").pack(side=tk.RIGHT, padx=5)

        # Store reference for save/send functions
        self.report_window = report_window

    def generate_report_text(self):
        """Generate the full report text content."""
        total_donations = sum(d['amount'] for d in self.donations)
        total_expenses = sum(e['amount'] for e in self.expenses)
        balance = total_donations - total_expenses

        active = len([m for m in self.members if m['status'] == 'Active'])
        inactive = len([m for m in self.members if m['status'] == 'Inactive'])
        visitors = len([m for m in self.members if m['status'] == 'Visitor'])
        answered_prayers = len([p for p in self.prayer_requests if p['status'] == 'Answered'])

        # Donation breakdown by type
        donation_types = {}
        for d in self.donations:
            dtype = d.get('type', 'Other')
            donation_types[dtype] = donation_types.get(dtype, 0) + d['amount']

        report = []
        report.append("=" * 60)
        report.append("GRACE COMMUNITY CHURCH - REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Generated by: {self.get_user_display_name()}")
        report.append("=" * 60)
        report.append("")
        report.append("FINANCIAL SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Donations:    £{total_donations:,.2f}")
        report.append(f"Total Expenses:     £{total_expenses:,.2f}")
        report.append(f"Net Balance:        £{balance:,.2f}")
        report.append("")

        if donation_types:
            report.append("Donation Breakdown by Type:")
            for dtype, amount in donation_types.items():
                report.append(f"  - {dtype}: £{amount:,.2f}")
            report.append("")

        report.append("MEMBERSHIP SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Members:      {len(self.members)}")
        report.append(f"  - Active:         {active}")
        report.append(f"  - Inactive:       {inactive}")
        report.append(f"  - Visitors:       {visitors}")
        report.append("")

        report.append("MINISTRY SUMMARY")
        report.append("-" * 40)
        report.append(f"Active Volunteers:  {len(self.volunteers)}")
        report.append(f"Small Groups:       {len(self.small_groups)}")
        report.append(f"Prayer Requests:    {len(self.prayer_requests)} ({answered_prayers} answered)")
        report.append(f"Sermons Archived:   {len(self.sermons)}")
        report.append(f"Upcoming Events:    {len(self.events)}")
        report.append("")

        # Recent donations
        if self.donations:
            report.append("RECENT DONATIONS (Last 10)")
            report.append("-" * 40)
            for d in self.donations[:10]:
                report.append(f"  {d.get('date', 'N/A')}: £{d['amount']:,.2f} - {d.get('type', 'N/A')} ({d.get('donor', 'Anonymous')})")
            report.append("")

        report.append("=" * 60)
        report.append("End of Report")
        report.append("=" * 60)

        return "\n".join(report)

    def save_report_as_txt(self):
        """Save the report to a text file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"church_report_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        if filename:
            report_content = self.generate_report_text()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            messagebox.showinfo(_t("church.common.success"), _t("church.reports.export_success", filename=filename))

    def send_report_to_admin(self):
        """Send the report to admin via email."""
        try:
            from university_system.infrastructure.email.email_service import send_email

            # Get admin email - try to find admin users
            admin_email = None
            try:
                from university_system.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                    )
                    result = cursor.fetchone()
                    if result:
                        admin_email = result[0]
            except Exception:
                pass

            if not admin_email:
                # Fallback to asking for email
                admin_email = simpledialog.askstring(
                    _t("church.reports.admin_email_title"),
                    _t("church.reports.admin_email_prompt"),
                    parent=self.report_window
                )

            if not admin_email:
                return

            report_content = self.generate_report_text()

            # Use email template
            try:
                from university_system.infrastructure.email.template_utils import render_template
                subject, body = render_template("church_report", {
                    "report_date": datetime.now().strftime('%Y-%m-%d'),
                    "report_content": report_content,
                    "generated_by": self.get_user_display_name()
                })
            except Exception as template_error:
                # Fallback to hardcoded email
                subject = f"Church Report - {datetime.now().strftime('%Y-%m-%d')}"
                body = f"""Dear Admin,

Please find the Church Report below.

{report_content}

This report was generated by {self.get_user_display_name()}.

Best regards,
Grace Community Church Management System
"""
            result = send_email(admin_email, subject, body)
            if result:
                messagebox.showinfo(_t("church.common.success"),
                                   _t("church.reports.send_success", email=admin_email))
            else:
                messagebox.showerror(_t("church.common.error"),
                                    _t("church.reports.send_failed"))
        except Exception as e:
            logger.error(f"Failed to send report to admin: {e}")
            messagebox.showerror(_t("church.common.error"),
                                _t("church.reports.send_failed"))

    def save_data(self):
        """Save data is handled immediately on each operation."""
        pass

    def load_data(self):
        """Load data from database."""
        init_church_database()
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Load members
                cursor = conn.execute("SELECT * FROM church_members ORDER BY name")
                self.members = [dict(row) for row in cursor.fetchall()]

                # Load donations
                cursor = conn.execute("SELECT * FROM church_donations ORDER BY date DESC")
                self.donations = [dict(row) for row in cursor.fetchall()]

                # Load events
                cursor = conn.execute("SELECT * FROM church_events ORDER BY date DESC")
                self.events = [dict(row) for row in cursor.fetchall()]

                # Load prayer requests
                cursor = conn.execute("SELECT * FROM church_prayer_requests ORDER BY date DESC")
                self.prayer_requests = [dict(row) for row in cursor.fetchall()]

                # Load sermons
                cursor = conn.execute("SELECT * FROM church_sermons ORDER BY date DESC")
                self.sermons = [dict(row) for row in cursor.fetchall()]

                # Load announcements
                cursor = conn.execute("SELECT * FROM church_announcements ORDER BY date DESC")
                self.announcements = [dict(row) for row in cursor.fetchall()]

                # Load volunteers
                cursor = conn.execute("SELECT * FROM church_volunteers ORDER BY name")
                self.volunteers = [dict(row) for row in cursor.fetchall()]

                # Load attendance records
                cursor = conn.execute("SELECT * FROM church_attendance ORDER BY service_date DESC")
                self.attendance_records = [dict(row) for row in cursor.fetchall()]

                # Load small groups
                cursor = conn.execute("SELECT * FROM church_small_groups ORDER BY name")
                rows = cursor.fetchall()
                self.small_groups = []
                for row in rows:
                    group = dict(row)
                    # Parse members JSON if stored as string
                    if group.get('members') and isinstance(group['members'], str):
                        try:
                            group['members'] = json.loads(group['members'])
                        except (ValueError, json.JSONDecodeError):
                            group['members'] = []
                    self.small_groups.append(group)

                # Load expenses
                cursor = conn.execute("SELECT * FROM church_expenses ORDER BY date DESC")
                self.expenses = [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error loading church data: {e}")
            # Initialize empty lists if database load fails
            self.members = []
            self.donations = []
            self.events = []
            self.prayer_requests = []
            self.sermons = []
            self.announcements = []
            self.volunteers = []
            self.attendance_records = []
            self.small_groups = []
            self.expenses = []

    def _db_save_member(self, member):
        """Save a member to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if member.get('id'):
                    conn.execute("""
                        UPDATE church_members SET name=?, email=?, phone=?, address=?,
                        join_date=?, membership_type=?, status=?, notes=? WHERE id=?
                    """, (member.get('name'), member.get('email'), member.get('phone'),
                          member.get('address'), member.get('join_date'), member.get('membership_type'),
                          member.get('status'), member.get('notes'), member['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO church_members (name, email, phone, address, join_date,
                        membership_type, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (member.get('name'), member.get('email'), member.get('phone'),
                          member.get('address'), member.get('join_date'), member.get('membership_type'),
                          member.get('status', 'Active'), member.get('notes')))
                    member['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save member: {e}")
            return False

    def _db_save_donation(self, donation):
        """Save a donation to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_donations (donor_name, donor_email, amount, donation_type,
                    payment_method, transaction_ref, date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (donation.get('donor_name'), donation.get('donor_email'), donation.get('amount'),
                      donation.get('donation_type'), donation.get('payment_method'),
                      donation.get('transaction_ref'), donation.get('date'), donation.get('notes')))
                donation['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save donation: {e}")
            return False

    def _db_save_event(self, event):
        """Save an event to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if event.get('id'):
                    conn.execute("""
                        UPDATE church_events SET title=?, description=?, date=?, time=?,
                        location=?, event_type=?, capacity=?, registered=? WHERE id=?
                    """, (event.get('title'), event.get('description'), event.get('date'),
                          event.get('time'), event.get('location'), event.get('event_type'),
                          event.get('capacity'), event.get('registered', 0), event['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO church_events (title, description, date, time, location,
                        event_type, capacity, registered) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event.get('title'), event.get('description'), event.get('date'),
                          event.get('time'), event.get('location'), event.get('event_type'),
                          event.get('capacity'), event.get('registered', 0)))
                    event['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save event: {e}")
            return False

    def _db_save_prayer_request(self, request):
        """Save a prayer request to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_prayer_requests (requester_name, request, category,
                    status, date, is_anonymous) VALUES (?, ?, ?, ?, ?, ?)
                """, (request.get('requester_name'), request.get('request'), request.get('category'),
                      request.get('status', 'Pending'), request.get('date'),
                      1 if request.get('is_anonymous') else 0))
                request['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save prayer request: {e}")
            return False

    def _db_save_sermon(self, sermon):
        """Save a sermon to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_sermons (title, speaker, date, scripture, summary, video_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sermon.get('title'), sermon.get('speaker'), sermon.get('date'),
                      sermon.get('scripture'), sermon.get('summary'), sermon.get('video_url')))
                sermon['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save sermon: {e}")
            return False

    def _db_save_volunteer(self, volunteer):
        """Save a volunteer to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if volunteer.get('id'):
                    conn.execute("""
                        UPDATE church_volunteers SET name=?, email=?, phone=?, ministry=?,
                        availability=?, skills=?, status=? WHERE id=?
                    """, (volunteer.get('name'), volunteer.get('email'), volunteer.get('phone'),
                          volunteer.get('ministry'), volunteer.get('availability'),
                          volunteer.get('skills'), volunteer.get('status'), volunteer['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO church_volunteers (name, email, phone, ministry, availability,
                        skills, status) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (volunteer.get('name'), volunteer.get('email'), volunteer.get('phone'),
                          volunteer.get('ministry'), volunteer.get('availability'),
                          volunteer.get('skills'), volunteer.get('status', 'Active')))
                    volunteer['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save volunteer: {e}")
            return False

    def _db_save_expense(self, expense):
        """Save an expense to the database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_expenses (description, amount, category, date, vendor, approved_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (expense.get('description'), expense.get('amount'), expense.get('category'),
                      expense.get('date'), expense.get('vendor'), expense.get('approved_by')))
                expense['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save expense: {e}")
            return False


def main():
    """Main entry point for the application."""
    root = tk.Tk()
    app = ChurchManagementSystem(root)
    if hasattr(app, 'root') and app.root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()
