import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class EquipmentBrowseDialog:
    """Dialog for browsing available equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Browse Equipment")
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Equipment Catalog", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 10))
        self.category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=20)
        category_combo['values'] = ('All', 'AV Equipment', 'Sports Gear', 'Tech Devices', 'Event Supplies')
        category_combo.pack(side='left')
        category_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Available Equipment")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Equipment", command=self.view_my_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            category_filter = self.category_var.get()
            if category_filter == "All":
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available'
                ORDER BY equipment_name
                ''')
            else:
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available' AND category = ?
                ORDER BY equipment_name
                ''', (category_filter,))

            equipment = cursor.fetchall()
            for item in equipment:
                self.equipment_tree.insert('', 'end', values=item)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load equipment: {str(e)}")

    def checkout(self):
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select equipment to check out.")
            return

        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]
        equipment_name = item['values'][1]

        dialog = EquipmentCheckoutDialog(self.dialog, self.auth, equipment_id, equipment_name)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def view_my_equipment(self):
        dialog = MyEquipmentDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class BrowseAvailableEquipmentDialog:
    """Dialog for browsing available equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Browse Equipment")
        self.dialog.geometry("1100x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📋 Browse Available Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Category filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 10))
        category_combo = ttk.Combobox(filter_frame, width=25, state='readonly')
        category_combo['values'] = ('All Categories', 'Audio Equipment', 'Video Equipment',
                                     'Lighting', 'Computers', 'Sports Equipment', 'Event Supplies')
        category_combo.current(0)
        category_combo.pack(side='left', padx=(0, 20))

        ttk.Label(filter_frame, text="Status:").pack(side='left', padx=(0, 10))
        status_combo = ttk.Combobox(filter_frame, width=20, state='readonly')
        status_combo['values'] = ('All Status', 'Available', 'Checked Out', 'Maintenance')
        status_combo.current(1)  # Available
        status_combo.pack(side='left')

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Available Equipment")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status', 'Last Checkout')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=200)
            elif col == 'Category':
                tree.column(col, width=120)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample equipment
        equipment = [
            ("EQ001", "Professional Camera (Canon EOS R5)", "Video Equipment", "Excellent", "Media Room A", "Available", "2025-03-20"),
            ("EQ002", "Wireless Microphone System", "Audio Equipment", "Good", "Audio Store", "Available", "2025-03-25"),
            ("EQ003", "LED Light Panel (3-pack)", "Lighting", "Excellent", "Lighting Storage", "Available", "Never"),
            ("EQ004", "Tripod (Manfrotto Pro)", "Video Equipment", "Good", "Media Room A", "Available", "2025-03-18"),
            ("EQ005", "Laptop (Dell XPS 15)", "Computers", "Excellent", "Tech Office", "Available", "2025-03-22"),
            ("EQ006", "Portable Speaker (JBL)", "Audio Equipment", "Good", "Events Store", "Available", "2025-03-15"),
            ("EQ007", "Projector (Epson 4K)", "Video Equipment", "Excellent", "AV Room", "Available", "2025-03-10"),
            ("EQ008", "Green Screen Kit", "Video Equipment", "Good", "Media Room B", "Available", "2025-03-12")
        ]

        for item in equipment:
            tree.insert('', 'end', values=item)

        tree.bind('<Double-1>', lambda e: self.view_details())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Details", command=self.view_details).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Check Out Selected", command=self.checkout_selected).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Reserve", command=self.reserve_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def view_details(self):
        dialog = ViewEquipmentDetailsDialog(self.dialog, self.auth)

    def checkout_selected(self):
        messagebox.showinfo("Check Out", "Proceeding to check out Professional Camera (Canon EOS R5).\n\nYou will be asked to:\n- Confirm your details\n- Agree to terms\n- Select return date")

    def reserve_equipment(self):
        messagebox.showinfo("Reserve", "Reserve equipment for future date:\n\nSelect:\n- Pickup date\n- Return date\n- Reason for use\n\nReservation will be confirmed via email.")



class ViewEquipmentDetailsDialog:
    """Dialog for viewing equipment details"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Equipment Details")
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Professional Camera (Canon EOS R5)",
                 font=('Arial', 13, 'bold')).pack(pady=(0, 15))

        # Equipment info
        info_frame = ttk.LabelFrame(main_frame, text="Equipment Information")
        info_frame.pack(fill='both', expand=True, pady=(0, 15))

        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill='both', padx=15, pady=10)

        info_data = [
            ("Equipment ID:", "EQ001"),
            ("Category:", "Video Equipment"),
            ("Manufacturer:", "Canon"),
            ("Model:", "EOS R5"),
            ("Serial Number:", "CN-R5-2023-001"),
            ("Condition:", "Excellent"),
            ("Purchase Date:", "2023-09-15"),
            ("Value:", "£3,500"),
            ("Location:", "Media Room A, Shelf 3"),
            ("Status:", "Available"),
            ("Last Checkout:", "2025-03-20 by John Smith"),
            ("Times Borrowed:", "23"),
            ("Next Maintenance:", "2025-06-01")
        ]

        for i, (label, value) in enumerate(info_data):
            ttk.Label(info_grid, text=label, font=('Arial', 9, 'bold')).grid(row=i, column=0, sticky='w', pady=2)
            ttk.Label(info_grid, text=value).grid(row=i, column=1, sticky='w', padx=10, pady=2)

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Description & Included Items")
        desc_frame.pack(fill='x', pady=(0, 15))

        desc_text = """Professional full-frame mirrorless camera with 45MP sensor,
ideal for video production, photography, and live streaming.

INCLUDED ACCESSORIES:
✓ 2x Batteries (LP-E6NH)
✓ Battery Charger
✓ Camera Strap
✓ USB-C Cable
✓ Body Cap
✓ Protective Case

COMPATIBLE LENSES (Available Separately):
- RF 24-70mm f/2.8
- RF 50mm f/1.2
- RF 70-200mm f/2.8"""

        ttk.Label(desc_frame, text=desc_text, justify='left', font=('Arial', 9)).pack(padx=15, pady=10)

        # Usage notes
        notes_frame = ttk.LabelFrame(main_frame, text="Usage Notes & Restrictions")
        notes_frame.pack(fill='x', pady=(0, 15))

        notes_text = """⚠️ Training required before checkout
⚠️ Maximum checkout: 7 days
⚠️ Late return fee: £10/day
✓ Insurance covered up to £3,500
✓ User manual available in case"""

        ttk.Label(notes_frame, text=notes_text, justify='left', font=('Arial', 9)).pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Reserve", command=self.reserve).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View History", command=self.view_history).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def checkout(self):
        messagebox.showinfo("Check Out", "Proceed to check out this equipment?\n\nMaximum loan period: 7 days\nYou will be responsible for any damage.\n\nContinue to checkout form...")

    def reserve(self):
        messagebox.showinfo("Reserve", "Reserve this equipment:\n\nSelect dates and purpose.\nYou'll receive confirmation email.")

    def view_history(self):
        messagebox.showinfo("Checkout History",
                          "Recent Checkouts (Last 10):\n\n" +
                          "1. 2025-03-20 - John Smith (3 days)\n" +
                          "2. 2025-03-15 - Sarah Jones (5 days)\n" +
                          "3. 2025-03-08 - Mike Chen (2 days)\n" +
                          "4. 2025-02-28 - Emma Wilson (7 days)\n" +
                          "5. 2025-02-18 - David Lee (4 days)\n\n" +
                          "All returns on time: Yes\n" +
                          "Damage reports: None")



class SearchEquipmentDialog:
    """Dialog for searching equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Search Equipment")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🔍 Search Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Search criteria
        search_frame = ttk.LabelFrame(main_frame, text="Search Criteria")
        search_frame.pack(fill='x', pady=(0, 15))

        search_content = ttk.Frame(search_frame)
        search_content.pack(fill='x', padx=15, pady=10)

        # Search text
        ttk.Label(search_content, text="Keyword:").grid(row=0, column=0, sticky='w', pady=5)
        search_entry = ttk.Entry(search_content, width=40)
        search_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        # Category
        ttk.Label(search_content, text="Category:").grid(row=1, column=0, sticky='w', pady=5)
        category_combo = ttk.Combobox(search_content, width=38, state='readonly')
        category_combo['values'] = ('Any', 'Audio Equipment', 'Video Equipment', 'Lighting', 'Computers', 'Sports Equipment')
        category_combo.current(0)
        category_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        # Status
        ttk.Label(search_content, text="Status:").grid(row=2, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(search_content, width=38, state='readonly')
        status_combo['values'] = ('Any', 'Available', 'Checked Out', 'Maintenance', 'Reserved')
        status_combo.current(0)
        status_combo.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        # Condition
        ttk.Label(search_content, text="Condition:").grid(row=3, column=0, sticky='w', pady=5)
        condition_combo = ttk.Combobox(search_content, width=38, state='readonly')
        condition_combo['values'] = ('Any', 'Excellent', 'Good', 'Fair')
        condition_combo.current(0)
        condition_combo.grid(row=3, column=1, sticky='ew', padx=10, pady=5)

        ttk.Button(search_content, text="Search", command=self.search, width=15).grid(row=4, column=1, sticky='e', padx=10, pady=10)

        search_content.columnconfigure(1, weight=1)

        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Search Results (12 items found)")
        results_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status')
        tree = ttk.Treeview(results_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=250)
            elif col == 'Category':
                tree.column(col, width=130)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample results
        results = [
            ("EQ001", "Professional Camera (Canon EOS R5)", "Video Equipment", "Excellent", "Media Room A", "Available"),
            ("EQ004", "Tripod (Manfrotto Pro)", "Video Equipment", "Good", "Media Room A", "Available"),
            ("EQ007", "Projector (Epson 4K)", "Video Equipment", "Excellent", "AV Room", "Available"),
            ("EQ008", "Green Screen Kit", "Video Equipment", "Good", "Media Room B", "Available")
        ]

        for item in results:
            tree.insert('', 'end', values=item)

        tree.bind('<Double-1>', lambda e: self.view_details())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Details", command=self.view_details).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Save Search", command=self.save_search).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def search(self):
        messagebox.showinfo("Search", "Searching equipment database...\n\nFound 4 items matching 'camera'")

    def view_details(self):
        dialog = ViewEquipmentDetailsDialog(self.dialog, self.auth)

    def checkout(self):
        dialog = CheckOutEquipmentDialog(self.dialog, self.auth)

    def save_search(self):
        messagebox.showinfo("Save Search", "Save search criteria for quick access?\n\nYou'll be notified when matching equipment becomes available.")



def open_browse_available_equipment_dialog(self):
    """Open browse available equipment"""
    dialog = BrowseAvailableEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_view_equipment_details_dialog(self):
    """Open view equipment details"""
    dialog = ViewEquipmentDetailsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_search_equipment_dialog(self):
    """Open search equipment"""
    dialog = SearchEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def create_equipment_tab(self):
    """Create equipment management tab"""
    equipment_frame = ttk.Frame(self.notebook)
    self.notebook.add(equipment_frame, text="Equipment")
    
    # Left panel
    left_panel = ttk.LabelFrame(equipment_frame, text="Equipment Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
    
    ttk.Button(left_panel, text="Browse Equipment", 
              command=self.browse_available_equipment).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Check Out Equipment", 
              command=self.check_out_equipment_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Return Equipment", 
              command=self.return_equipment_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="My Checkouts", 
              command=self.view_my_equipment_checkouts).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Search Equipment", 
              command=self.search_equipment_gui).pack(fill='x', pady=2)
    
    # Right panel
    right_panel = ttk.LabelFrame(equipment_frame, text="Equipment Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
    
    self.equipment_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                   height=30, width=80)
    self.equipment_text.pack(fill='both', expand=True, padx=5, pady=5)


def browse_available_equipment(self):
    """Browse available equipment"""
    try:
        dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def search_equipment_gui(self):
    """Search equipment"""
    try:
        dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


