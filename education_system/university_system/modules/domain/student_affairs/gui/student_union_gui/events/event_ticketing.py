import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class EventTicketingDialog:
    """Dialog for event ticketing system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Ticketing System")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🎫 Event Ticketing System",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Event:").pack(side='left', padx=(0, 10))
        event_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        event_combo['values'] = ('Annual Gala 2025', 'Spring Festival', 'Tech Conference')
        event_combo.pack(side='left', fill='x', expand=True)
        event_combo.current(0)

        # Ticket types
        types_frame = ttk.LabelFrame(main_frame, text="Ticket Types")
        types_frame.pack(fill='x', pady=(0, 15))

        columns = ('Type', 'Price', 'Available', 'Sold', 'Revenue')
        tree = ttk.Treeview(types_frame, columns=columns, show='tree headings', height=6)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample ticket types
        tickets = [
            ("General Admission", "£10.00", "200/300", "100", "£1,000"),
            ("VIP", "£25.00", "40/50", "10", "£250"),
            ("Student", "£5.00", "450/500", "50", "£250"),
            ("Early Bird", "£8.00", "0/100", "100", "£800")
        ]

        for ticket in tickets:
            tree.insert('', 'end', values=ticket)

        # Sales summary
        summary_frame = ttk.LabelFrame(main_frame, text="Sales Summary")
        summary_frame.pack(fill='both', expand=True, pady=(0, 15))

        summary_text = scrolledtext.ScrolledText(summary_frame, height=12, wrap=tk.WORD, font=('Courier', 10))
        summary_text.pack(fill='both', expand=True, padx=5, pady=5)

        summary = """TICKET SALES SUMMARY

Total Tickets Available: 950
Total Tickets Sold: 260 (27.4%)
Total Revenue: £2,300

SALES BY TYPE:
- General Admission: 100 sold (£1,000)
- VIP: 10 sold (£250)
- Student: 50 sold (£250)
- Early Bird: 100 sold (£800) [SOLD OUT]

WAITLIST:
- General Admission: 15 people
- VIP: 5 people

SALES TREND:
Week 1: 45 tickets
Week 2: 78 tickets
Week 3: 92 tickets
Week 4: 45 tickets

PROJECTED FINAL SALES: 420 tickets (44% capacity)
"""
        summary_text.insert(1.0, summary)
        summary_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create Ticket Type", command=self.create_ticket_type).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Process Refund", command=self.process_refund).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Manage Waitlist", command=self.manage_waitlist).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_ticket_type(self):
        dialog = CreateTicketTypeDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def process_refund(self):
        dialog = ProcessRefundDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_waitlist(self):
        dialog = ManageWaitlistDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class CreateTicketTypeDialog:
    """Dialog for creating a new ticket type"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Ticket Type")
        self.dialog.geometry("550x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Create New Ticket Type", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event selection
        ttk.Label(main_frame, text="Event:").pack(anchor='w', pady=(0, 5))
        self.event_var = tk.StringVar()
        event_combo = ttk.Combobox(main_frame, textvariable=self.event_var, width=47)
        event_combo['values'] = ('Annual Gala 2025', 'Spring Festival', 'Tech Conference', 'Charity Ball')
        event_combo.pack(fill='x', pady=(0, 10))
        event_combo.current(0)

        # Ticket type name
        ttk.Label(main_frame, text="Ticket Type Name:").pack(anchor='w', pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, width=50)
        self.name_entry.pack(fill='x', pady=(0, 10))
        self.name_entry.insert(0, "General Admission")

        # Price
        ttk.Label(main_frame, text="Price (£):").pack(anchor='w', pady=(0, 5))
        self.price_entry = ttk.Entry(main_frame, width=50)
        self.price_entry.pack(fill='x', pady=(0, 10))
        self.price_entry.insert(0, "10.00")

        # Quantity
        ttk.Label(main_frame, text="Total Quantity Available:").pack(anchor='w', pady=(0, 5))
        self.quantity_entry = ttk.Entry(main_frame, width=50)
        self.quantity_entry.pack(fill='x', pady=(0, 10))
        self.quantity_entry.insert(0, "100")

        # Sale dates
        dates_frame = ttk.Frame(main_frame)
        dates_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(dates_frame, text="Sale Start:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.start_entry = ttk.Entry(dates_frame, width=20)
        self.start_entry.grid(row=0, column=1, sticky='w', padx=(5, 10))
        self.start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(dates_frame, text="Sale End:").grid(row=0, column=2, sticky='w', pady=(0, 5))
        self.end_entry = ttk.Entry(dates_frame, width=20)
        self.end_entry.grid(row=0, column=3, sticky='w', padx=(5, 0))
        self.end_entry.insert(0, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 15))
        self.description_text.insert(1.0, "Standard entry to the event...")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create", command=self.create_type).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create_type(self):
        event = self.event_var.get()
        name = self.name_entry.get().strip()
        price = self.price_entry.get().strip()
        quantity = self.quantity_entry.get().strip()
        start_date = self.start_entry.get().strip()
        end_date = self.end_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()

        if not all([event, name, price, quantity, start_date, end_date]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            price_float = float(price)
            quantity_int = int(quantity)
            if price_float < 0 or quantity_int <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Warning", "Please enter valid price and quantity values.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_ticket_types (
                ticket_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                type_name TEXT NOT NULL,
                price REAL NOT NULL,
                total_quantity INTEGER NOT NULL,
                sold_quantity INTEGER DEFAULT 0,
                sale_start_date TEXT,
                sale_end_date TEXT,
                description TEXT,
                created_by TEXT,
                created_date TEXT
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            created_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO event_ticket_types (
                event_name, type_name, price, total_quantity, sold_quantity,
                sale_start_date, sale_end_date, description, created_by, created_date
            ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            ''', (event, name, price_float, quantity_int, start_date, end_date,
                  description, created_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Ticket type '{name}' created successfully!\n\nPrice: £{price_float:.2f}\nQuantity: {quantity_int}")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create ticket type: {str(e)}")



class ProcessRefundDialog:
    """Dialog for processing ticket refunds"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Refund")
        self.dialog.geometry("650x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Process Ticket Refund", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Ticket/Order search
        search_frame = ttk.LabelFrame(main_frame, text="Find Ticket/Order")
        search_frame.pack(fill='x', pady=(0, 15))

        form = ttk.Frame(search_frame)
        form.pack(padx=15, pady=15, fill='x')

        ttk.Label(form, text="Ticket/Order ID:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.ticket_id_entry = ttk.Entry(form, width=25)
        self.ticket_id_entry.grid(row=0, column=1, sticky='w', pady=(0, 5), padx=(5, 10))

        ttk.Button(form, text="Search", command=self.search_ticket).grid(row=0, column=2, pady=(0, 5))

        ttk.Label(form, text="Customer Email:").grid(row=1, column=0, sticky='w', pady=(0, 5))
        self.email_entry = ttk.Entry(form, width=25)
        self.email_entry.grid(row=1, column=1, sticky='w', pady=(0, 5), padx=(5, 10))

        # Ticket details
        details_frame = ttk.LabelFrame(main_frame, text="Ticket Details")
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.details_text.insert(1.0, "Enter ticket ID or email and click Search to load ticket details...")
        self.details_text.config(state='disabled')

        # Refund options
        refund_frame = ttk.LabelFrame(main_frame, text="Refund Options")
        refund_frame.pack(fill='x', pady=(0, 15))

        options = ttk.Frame(refund_frame)
        options.pack(padx=15, pady=15, fill='x')

        ttk.Label(options, text="Refund Amount:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.refund_amount_entry = ttk.Entry(options, width=15)
        self.refund_amount_entry.grid(row=0, column=1, sticky='w', pady=(0, 5), padx=(5, 10))
        self.refund_amount_entry.insert(0, "0.00")

        ttk.Label(options, text="Refund Method:").grid(row=1, column=0, sticky='w', pady=(0, 5))
        self.method_var = tk.StringVar(value="Original Payment Method")
        method_combo = ttk.Combobox(options, textvariable=self.method_var, width=23, state='readonly')
        method_combo['values'] = ('Original Payment Method', 'Bank Transfer', 'Store Credit', 'Cash')
        method_combo.grid(row=1, column=1, sticky='w', pady=(0, 5), padx=(5, 10))

        ttk.Label(options, text="Reason:").grid(row=2, column=0, sticky='w', pady=(0, 5))
        self.reason_var = tk.StringVar()
        reason_combo = ttk.Combobox(options, textvariable=self.reason_var, width=23)
        reason_combo['values'] = ('Event Cancelled', 'Customer Request', 'Duplicate Purchase',
                                  'Unable to Attend', 'Other')
        reason_combo.grid(row=2, column=1, sticky='w', pady=(0, 5), padx=(5, 10))
        reason_combo.current(0)

        # Notes
        ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        self.notes_text.pack(fill='x', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Process Refund", command=self.process_refund).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def search_ticket(self):
        ticket_id = self.ticket_id_entry.get().strip()
        email = self.email_entry.get().strip()

        if not ticket_id and not email:
            messagebox.showwarning("Warning", "Please enter a Ticket ID or Email to search.")
            return

        # Simulate search result
        sample_details = f"""TICKET FOUND

Ticket ID: {ticket_id if ticket_id else "TKT-12345"}
Event: Annual Gala 2025
Ticket Type: VIP
Purchase Date: 2025-03-15
Customer: john.doe@email.com
Original Price: £25.00
Status: Active

This ticket is eligible for a full refund.
"""
        self.details_text.config(state='normal')
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, sample_details)
        self.details_text.config(state='disabled')

        self.refund_amount_entry.delete(0, tk.END)
        self.refund_amount_entry.insert(0, "25.00")

    def process_refund(self):
        refund_amount = self.refund_amount_entry.get().strip()
        method = self.method_var.get()
        reason = self.reason_var.get()
        notes = self.notes_text.get(1.0, tk.END).strip()

        if not all([refund_amount, method, reason]):
            messagebox.showwarning("Warning", "Please fill in all refund details.")
            return

        try:
            amount_float = float(refund_amount)
            if amount_float <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid refund amount.")
            return

        # In a real system, this would process the refund in the database
        messagebox.showinfo("Success", f"Refund Processed!\n\nAmount: £{amount_float:.2f}\nMethod: {method}\n\nThe customer will be notified via email.")
        self.dialog.destroy()



class ManageWaitlistDialog:
    """Dialog for managing event waitlists"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Waitlist")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Event Waitlist Management", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event and ticket type selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Event:").pack(side='left', padx=(0, 10))
        event_combo = ttk.Combobox(select_frame, width=25, state='readonly')
        event_combo['values'] = ('Annual Gala 2025', 'Spring Festival', 'Tech Conference')
        event_combo.pack(side='left', padx=(0, 20))
        event_combo.current(0)

        ttk.Label(select_frame, text="Ticket Type:").pack(side='left', padx=(0, 10))
        ticket_combo = ttk.Combobox(select_frame, width=20, state='readonly')
        ticket_combo['values'] = ('General Admission', 'VIP', 'Student')
        ticket_combo.pack(side='left')
        ticket_combo.current(0)

        # Waitlist
        list_frame = ttk.LabelFrame(main_frame, text="Waitlist (15 people)")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Position', 'Name', 'Email', 'Added', 'Status')
        self.waitlist_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.waitlist_tree.heading(col, text=col)
            if col == 'Email':
                self.waitlist_tree.column(col, width=200)
            else:
                self.waitlist_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.waitlist_tree.yview)
        self.waitlist_tree.configure(yscrollcommand=scrollbar.set)

        self.waitlist_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Sample waitlist data
        waitlist_entries = [
            ("1", "Alice Johnson", "alice@email.com", "2025-03-10", "Waiting"),
            ("2", "Bob Smith", "bob@email.com", "2025-03-11", "Waiting"),
            ("3", "Carol Davis", "carol@email.com", "2025-03-12", "Waiting"),
            ("4", "David Wilson", "david@email.com", "2025-03-13", "Waiting"),
            ("5", "Emma Brown", "emma@email.com", "2025-03-14", "Waiting")
        ]

        for entry in waitlist_entries:
            self.waitlist_tree.insert('', 'end', values=entry)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Notify Next Person", command=self.notify_next).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Remove from Waitlist", command=self.remove_from_waitlist).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Notify All", command=self.notify_all).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def notify_next(self):
        messagebox.showinfo("Success", "Email sent to Alice Johnson notifying them that tickets are available!\n\nThey have 24 hours to purchase.")

    def remove_from_waitlist(self):
        selection = self.waitlist_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a person to remove.")
            return

        if messagebox.askyesno("Confirm", "Remove selected person from waitlist?"):
            self.waitlist_tree.delete(selection[0])
            messagebox.showinfo("Success", "Person removed from waitlist.")

    def notify_all(self):
        if messagebox.askyesno("Confirm", "Send notification emails to all 15 people on the waitlist?"):
            messagebox.showinfo("Success", "Notification emails sent to all waitlist members!")



def open_event_ticketing_dialog(self):
    """Open event ticketing system"""
    dialog = EventTicketingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


