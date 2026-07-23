"""
Lost & Found GUI Interface

Full-featured GUI for lost and found item management with image upload.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from typing import Optional, List, Dict
import os
from PIL import Image, ImageTk

from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.modules.domain.campus.lost_found.services.lost_found_service import LostFoundService


class LostFoundGUI:
    """Main GUI for Lost & Found System"""

    # Item categories
    CATEGORIES = [
        'Electronics',
        'Clothing',
        'Books',
        'Keys',
        'Bags',
        'Wallets',
        'Jewelry',
        'Sports Equipment',
        'Documents',
        'Other'
    ]

    def __init__(self, parent, auth=None):
        self.root = tk.Toplevel(parent)
        self.root.title("Lost & Found System")
        self.root.geometry("1400x900")

        self.auth = auth or get_auth()
        self.service = LostFoundService()

        # Store selected photo path
        self.selected_photo_path = None
        self.current_item_type = None
        self.current_item_id = None

        self.create_widgets()
        self.refresh_all_tabs()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="Lost & Found System",
                         font=('Arial', 20, 'bold'))
        title.pack(pady=10)

        # User info
        user = self.auth.get_current_user()
        if user:
            user_label = ttk.Label(main_frame,
                                  text=f"User: {user.get('username', 'Unknown')} | "
                                       f"Role: {user.get('role', 'student').capitalize()}",
                                  font=('Arial', 10))
            user_label.pack()

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create tabs
        self.create_lost_items_tab()
        self.create_found_items_tab()
        self.create_my_reports_tab()
        self.create_claims_tab()
        self.create_matches_tab()
        self.create_statistics_tab()

    def create_lost_items_tab(self):
        """Create Lost Items tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Lost Items")

        # Top frame for report form
        form_frame = ttk.LabelFrame(tab, text="Report Lost Item", padding="10")
        form_frame.pack(fill=tk.X, padx=5, pady=5)

        # Item details in grid
        row = 0

        ttk.Label(form_frame, text="Item Name:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.lost_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_name_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Category:*").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.lost_category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.lost_category_var,
                                      values=self.CATEGORIES, state='readonly', width=20)
        category_combo.grid(row=row, column=3, pady=3, sticky=tk.W, padx=5)
        category_combo.current(0)

        row += 1
        ttk.Label(form_frame, text="Description:*").grid(row=row, column=0, sticky=tk.NW, pady=3)
        self.lost_description = tk.Text(form_frame, width=30, height=3)
        self.lost_description.grid(row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Distinctive Features:").grid(
            row=row, column=2, sticky=tk.NW, pady=3, padx=(15, 0))
        self.lost_features = tk.Text(form_frame, width=25, height=3)
        self.lost_features.grid(row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Lost Date:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.lost_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=self.lost_date_var, width=15).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Lost Time:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.lost_time_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_time_var, width=10).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Lost Location:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.lost_location_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_location_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Color:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.lost_color_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_color_var, width=15).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Brand:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.lost_brand_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_brand_var, width=20).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Estimated Value ($):").grid(
            row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.lost_value_var = tk.StringVar(value="0.00")
        ttk.Entry(form_frame, textvariable=self.lost_value_var, width=10).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Contact Email:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.lost_email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_email_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Contact Phone:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.lost_phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.lost_phone_var, width=20).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        # Buttons
        row += 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=10)

        ttk.Button(button_frame, text="Report Lost Item",
                  command=self.report_lost_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_lost_form).pack(side=tk.LEFT, padx=5)

        # Search and list frame
        list_frame = ttk.LabelFrame(tab, text="Lost Items List", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Search controls
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.lost_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.lost_search_var, width=30).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Search",
                  command=lambda: self.search_items('lost')).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Show All",
                  command=self.load_lost_items).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Refresh",
                  command=self.load_lost_items).pack(side=tk.LEFT, padx=5)

        # Treeview for lost items
        columns = ('ID', 'Name', 'Category', 'Date', 'Location', 'Status')
        self.lost_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.lost_tree.heading(col, text=col)
            self.lost_tree.column(col, width=100)

        self.lost_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.lost_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lost_tree.configure(yscrollcommand=scrollbar.set)

        # Buttons for selected item
        action_frame = ttk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="View Details",
                  command=lambda: self.view_item_details('lost')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Update Status",
                  command=lambda: self.update_item_status_dialog('lost')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="View Matches",
                  command=lambda: self.view_item_matches('lost')).pack(side=tk.LEFT, padx=5)

    def create_found_items_tab(self):
        """Create Found Items tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Found Items")

        # Top frame for report form
        form_frame = ttk.LabelFrame(tab, text="Report Found Item", padding="10")
        form_frame.pack(fill=tk.X, padx=5, pady=5)

        # Item details in grid
        row = 0

        ttk.Label(form_frame, text="Item Name:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_name_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Category:*").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.found_category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.found_category_var,
                                      values=self.CATEGORIES, state='readonly', width=20)
        category_combo.grid(row=row, column=3, pady=3, sticky=tk.W, padx=5)
        category_combo.current(0)

        row += 1
        ttk.Label(form_frame, text="Description:*").grid(row=row, column=0, sticky=tk.NW, pady=3)
        self.found_description = tk.Text(form_frame, width=30, height=3)
        self.found_description.grid(row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Distinctive Features:").grid(
            row=row, column=2, sticky=tk.NW, pady=3, padx=(15, 0))
        self.found_features = tk.Text(form_frame, width=25, height=3)
        self.found_features.grid(row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Found Date:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=self.found_date_var, width=15).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Found Time:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.found_time_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_time_var, width=10).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Found Location:*").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_location_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_location_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Color:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.found_color_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_color_var, width=15).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Brand:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_brand_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_brand_var, width=20).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Current Location:").grid(
            row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.found_current_location_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_current_location_var, width=25).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Storage Info:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_storage_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_storage_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        row += 1
        ttk.Label(form_frame, text="Contact Email:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_email_var, width=30).grid(
            row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Label(form_frame, text="Contact Phone:").grid(row=row, column=2, sticky=tk.W, pady=3, padx=(15, 0))
        self.found_phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.found_phone_var, width=20).grid(
            row=row, column=3, pady=3, sticky=tk.W, padx=5)

        # Photo upload
        row += 1
        ttk.Label(form_frame, text="Photo:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.found_photo_label = ttk.Label(form_frame, text="No photo selected")
        self.found_photo_label.grid(row=row, column=1, pady=3, sticky=tk.W, padx=5)

        ttk.Button(form_frame, text="Select Photo",
                  command=lambda: self.select_photo('found')).grid(
            row=row, column=2, pady=3, sticky=tk.W, padx=(15, 0))

        # Buttons
        row += 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=10)

        ttk.Button(button_frame, text="Report Found Item",
                  command=self.report_found_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_found_form).pack(side=tk.LEFT, padx=5)

        # Search and list frame
        list_frame = ttk.LabelFrame(tab, text="Found Items List", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Search controls
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.found_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.found_search_var, width=30).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Search",
                  command=lambda: self.search_items('found')).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Show All",
                  command=self.load_found_items).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Refresh",
                  command=self.load_found_items).pack(side=tk.LEFT, padx=5)

        # Treeview for found items
        columns = ('ID', 'Name', 'Category', 'Date', 'Location', 'Status')
        self.found_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.found_tree.heading(col, text=col)
            self.found_tree.column(col, width=100)

        self.found_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.found_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.found_tree.configure(yscrollcommand=scrollbar.set)

        # Buttons for selected item
        action_frame = ttk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="View Details",
                  command=lambda: self.view_item_details('found')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Update Status",
                  command=lambda: self.update_item_status_dialog('found')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Submit Claim",
                  command=self.submit_claim_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="View Matches",
                  command=lambda: self.view_item_matches('found')).pack(side=tk.LEFT, padx=5)

    def create_my_reports_tab(self):
        """Create My Reports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="My Reports")

        # Lost items section
        lost_frame = ttk.LabelFrame(tab, text="My Lost Items", padding="10")
        lost_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Controls
        control_frame = ttk.Frame(lost_frame)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Button(control_frame, text="Refresh",
                  command=self.load_my_lost_items).pack(side=tk.LEFT, padx=5)

        # Treeview
        columns = ('ID', 'Name', 'Category', 'Date', 'Location', 'Status')
        self.my_lost_tree = ttk.Treeview(lost_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.my_lost_tree.heading(col, text=col)
            self.my_lost_tree.column(col, width=100)

        self.my_lost_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(lost_frame, orient=tk.VERTICAL, command=self.my_lost_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.my_lost_tree.configure(yscrollcommand=scrollbar.set)

        # Found items section
        found_frame = ttk.LabelFrame(tab, text="My Found Items", padding="10")
        found_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Controls
        control_frame = ttk.Frame(found_frame)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Button(control_frame, text="Refresh",
                  command=self.load_my_found_items).pack(side=tk.LEFT, padx=5)

        # Treeview
        self.my_found_tree = ttk.Treeview(found_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.my_found_tree.heading(col, text=col)
            self.my_found_tree.column(col, width=100)

        self.my_found_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(found_frame, orient=tk.VERTICAL, command=self.my_found_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.my_found_tree.configure(yscrollcommand=scrollbar.set)

    def create_claims_tab(self):
        """Create Claims tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Claims")

        # Controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text="Filter by Status:").pack(side=tk.LEFT, padx=5)
        self.claims_status_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(control_frame, textvariable=self.claims_status_var,
                                    values=['All', 'Pending', 'Approved', 'Rejected'],
                                    state='readonly', width=15)
        status_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Refresh",
                  command=self.load_claims).pack(side=tk.LEFT, padx=5)

        user = self.auth.get_current_user()
        if user and user.get('role', '').lower() in ['admin', 'staff']:
            ttk.Button(control_frame, text="Review Claims",
                      command=self.review_claim_dialog).pack(side=tk.LEFT, padx=5)

        # Treeview for claims
        columns = ('Claim ID', 'Item ID', 'Claimant', 'Status', 'Submitted', 'Reviewed')
        self.claims_tree = ttk.Treeview(tab, columns=columns, show='headings', height=15)

        for col in columns:
            self.claims_tree.heading(col, text=col)
            self.claims_tree.column(col, width=100)

        self.claims_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.claims_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.claims_tree.configure(yscrollcommand=scrollbar.set)

        # Details button
        ttk.Button(tab, text="View Claim Details",
                  command=self.view_claim_details).pack(pady=5)

    def create_matches_tab(self):
        """Create Matches tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Potential Matches")

        # Instructions
        ttk.Label(tab, text="Select an item type and ID to view potential matches:",
                 font=('Arial', 11)).pack(pady=10)

        # Input frame
        input_frame = ttk.Frame(tab)
        input_frame.pack(fill=tk.X, pady=10)

        ttk.Label(input_frame, text="Item Type:").pack(side=tk.LEFT, padx=5)
        self.match_type_var = tk.StringVar(value="lost")
        ttk.Radiobutton(input_frame, text="Lost", variable=self.match_type_var,
                       value="lost").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(input_frame, text="Found", variable=self.match_type_var,
                       value="found").pack(side=tk.LEFT, padx=5)

        ttk.Label(input_frame, text="Item ID:").pack(side=tk.LEFT, padx=(20, 5))
        self.match_item_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.match_item_id_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(input_frame, text="Find Matches",
                  command=self.load_matches).pack(side=tk.LEFT, padx=10)

        # Matches display
        matches_frame = ttk.LabelFrame(tab, text="Matches", padding="10")
        matches_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview
        columns = ('Score', 'Item Name', 'Description', 'Location', 'Date', 'Reasons')
        self.matches_tree = ttk.Treeview(matches_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.matches_tree.heading(col, text=col)
            if col == 'Description':
                self.matches_tree.column(col, width=200)
            elif col == 'Reasons':
                self.matches_tree.column(col, width=250)
            else:
                self.matches_tree.column(col, width=100)

        self.matches_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(matches_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

    def create_statistics_tab(self):
        """Create Statistics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Statistics")

        # Title
        ttk.Label(tab, text="Lost & Found Statistics",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Scrolled text for statistics
        self.stats_text = scrolledtext.ScrolledText(tab, width=100, height=30,
                                                     font=('Courier', 10))
        self.stats_text.pack(fill=tk.BOTH, expand=True, pady=10)

        # Refresh button
        ttk.Button(tab, text="Refresh Statistics",
                  command=self.load_statistics).pack(pady=5)

    # ====================
    # Helper Methods
    # ====================

    def select_photo(self, item_type: str):
        """Select a photo file"""
        file_path = filedialog.askopenfilename(
            title="Select Photo",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.selected_photo_path = file_path
            filename = os.path.basename(file_path)

            if item_type == 'found':
                self.found_photo_label.config(text=filename)
            else:
                # For future lost item photo support
                pass

            messagebox.showinfo("Photo Selected", f"Selected: {filename}")

    def report_lost_item(self):
        """Report a lost item"""
        user = self.auth.get_current_user()
        if not user:
            messagebox.showerror("Error", "User not found.")
            return

        # Validate required fields
        if not self.lost_name_var.get().strip():
            messagebox.showerror("Error", "Item name is required.")
            return

        if not self.lost_description.get("1.0", tk.END).strip():
            messagebox.showerror("Error", "Description is required.")
            return

        if not self.lost_location_var.get().strip():
            messagebox.showerror("Error", "Lost location is required.")
            return

        try:
            estimated_value = float(self.lost_value_var.get() or "0")
        except ValueError:
            messagebox.showerror("Error", "Invalid estimated value.")
            return

        try:
            item_id = self.service.report_lost_item(
                reporter_id=user['username'],
                item_name=self.lost_name_var.get().strip(),
                category=self.lost_category_var.get(),
                description=self.lost_description.get("1.0", tk.END).strip(),
                lost_date=self.lost_date_var.get().strip(),
                lost_location=self.lost_location_var.get().strip(),
                lost_time=self.lost_time_var.get().strip(),
                distinctive_features=self.lost_features.get("1.0", tk.END).strip(),
                color=self.lost_color_var.get().strip(),
                brand=self.lost_brand_var.get().strip(),
                estimated_value=estimated_value,
                contact_email=self.lost_email_var.get().strip(),
                contact_phone=self.lost_phone_var.get().strip()
            )

            messagebox.showinfo("Success",
                              f"Lost item reported successfully!\n"
                              f"Item ID: {item_id}\n"
                              f"The system will search for potential matches.")

            self.clear_lost_form()
            self.load_lost_items()
            self.load_my_lost_items()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to report lost item:\n{str(e)}")

    def report_found_item(self):
        """Report a found item"""
        user = self.auth.get_current_user()
        if not user:
            messagebox.showerror("Error", "User not found.")
            return

        # Validate required fields
        if not self.found_name_var.get().strip():
            messagebox.showerror("Error", "Item name is required.")
            return

        if not self.found_description.get("1.0", tk.END).strip():
            messagebox.showerror("Error", "Description is required.")
            return

        if not self.found_location_var.get().strip():
            messagebox.showerror("Error", "Found location is required.")
            return

        try:
            item_id = self.service.report_found_item(
                finder_id=user['username'],
                item_name=self.found_name_var.get().strip(),
                category=self.found_category_var.get(),
                description=self.found_description.get("1.0", tk.END).strip(),
                found_date=self.found_date_var.get().strip(),
                found_location=self.found_location_var.get().strip(),
                found_time=self.found_time_var.get().strip(),
                distinctive_features=self.found_features.get("1.0", tk.END).strip(),
                color=self.found_color_var.get().strip(),
                brand=self.found_brand_var.get().strip(),
                current_location=self.found_current_location_var.get().strip(),
                storage_info=self.found_storage_var.get().strip(),
                contact_email=self.found_email_var.get().strip(),
                contact_phone=self.found_phone_var.get().strip()
            )

            # Upload photo if selected
            if self.selected_photo_path and os.path.exists(self.selected_photo_path):
                try:
                    with open(self.selected_photo_path, 'rb') as f:
                        photo_data = f.read()
                    self.service.add_item_photo('found', item_id, photo_data,
                                               caption="Item photo")
                except Exception as e:
                    messagebox.showwarning("Photo Upload",
                                         f"Item reported but photo upload failed:\n{str(e)}")

            messagebox.showinfo("Success",
                              f"Found item reported successfully!\n"
                              f"Item ID: {item_id}\n"
                              f"The system will search for potential matches.")

            self.clear_found_form()
            self.load_found_items()
            self.load_my_found_items()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to report found item:\n{str(e)}")

    def clear_lost_form(self):
        """Clear the lost item form"""
        self.lost_name_var.set("")
        self.lost_category_var.set(self.CATEGORIES[0])
        self.lost_description.delete("1.0", tk.END)
        self.lost_features.delete("1.0", tk.END)
        self.lost_date_var.set(datetime.now().strftime('%Y-%m-%d'))
        self.lost_time_var.set("")
        self.lost_location_var.set("")
        self.lost_color_var.set("")
        self.lost_brand_var.set("")
        self.lost_value_var.set("0.00")
        self.lost_email_var.set("")
        self.lost_phone_var.set("")

    def clear_found_form(self):
        """Clear the found item form"""
        self.found_name_var.set("")
        self.found_category_var.set(self.CATEGORIES[0])
        self.found_description.delete("1.0", tk.END)
        self.found_features.delete("1.0", tk.END)
        self.found_date_var.set(datetime.now().strftime('%Y-%m-%d'))
        self.found_time_var.set("")
        self.found_location_var.set("")
        self.found_color_var.set("")
        self.found_brand_var.set("")
        self.found_current_location_var.set("")
        self.found_storage_var.set("")
        self.found_email_var.set("")
        self.found_phone_var.set("")
        self.selected_photo_path = None
        self.found_photo_label.config(text="No photo selected")

    def load_lost_items(self):
        """Load all lost items"""
        try:
            items = self.service.get_lost_items(status='Active')
            self._populate_tree(self.lost_tree, items, 'lost')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load lost items:\n{str(e)}")

    def load_found_items(self):
        """Load all found items"""
        try:
            items = self.service.get_found_items(status='Available')
            self._populate_tree(self.found_tree, items, 'found')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load found items:\n{str(e)}")

    def load_my_lost_items(self):
        """Load user's lost items"""
        user = self.auth.get_current_user()
        if not user:
            return

        try:
            items = self.service.get_lost_items(reporter_id=user['username'])
            self._populate_tree(self.my_lost_tree, items, 'lost')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load your lost items:\n{str(e)}")

    def load_my_found_items(self):
        """Load user's found items"""
        user = self.auth.get_current_user()
        if not user:
            return

        try:
            items = self.service.get_found_items(finder_id=user['username'])
            self._populate_tree(self.my_found_tree, items, 'found')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load your found items:\n{str(e)}")

    def _populate_tree(self, tree, items, item_type):
        """Populate a treeview with items"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        # Add items
        date_field = 'lost_date' if item_type == 'lost' else 'found_date'
        location_field = 'lost_location' if item_type == 'lost' else 'found_location'

        for item in items:
            tree.insert('', tk.END, values=(
                item['item_id'],
                item['item_name'],
                item['category'],
                item[date_field],
                item[location_field][:30],
                item['status']
            ))

    def search_items(self, item_type: str):
        """Search for items"""
        search_var = self.lost_search_var if item_type == 'lost' else self.found_search_var
        search_term = search_var.get().strip()

        if not search_term:
            messagebox.showinfo("Info", "Please enter a search term.")
            return

        try:
            items = self.service.search_items(item_type, search_term)
            tree = self.lost_tree if item_type == 'lost' else self.found_tree
            self._populate_tree(tree, items, item_type)

            messagebox.showinfo("Search Results", f"Found {len(items)} matching items.")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed:\n{str(e)}")

    def view_item_details(self, item_type: str):
        """View detailed information about an item"""
        tree = self.lost_tree if item_type == 'lost' else self.found_tree
        selection = tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select an item to view.")
            return

        item_id = tree.item(selection[0])['values'][0]

        try:
            if item_type == 'lost':
                item = self.service.get_lost_item(item_id)
            else:
                item = self.service.get_found_item(item_id)

            if not item:
                messagebox.showerror("Error", "Item not found.")
                return

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"{item_type.capitalize()} Item Details")
            details_window.geometry("600x700")

            # Scrollable frame
            canvas = tk.Canvas(details_window)
            scrollbar = ttk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Details text
            text = scrolledtext.ScrolledText(scrollable_frame, width=70, height=35,
                                            font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Format details
            details_text = self._format_item_details(item, item_type)
            text.insert('1.0', details_text)
            text.config(state=tk.DISABLED)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item details:\n{str(e)}")

    def _format_item_details(self, item: dict, item_type: str) -> str:
        """Format item details as text"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"{item_type.upper()} ITEM DETAILS")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"Item ID: {item['item_id']}")
        lines.append(f"Name: {item['item_name']}")
        lines.append(f"Category: {item['category']}")
        lines.append(f"Status: {item['status']}")
        lines.append("")

        date_field = 'lost_date' if item_type == 'lost' else 'found_date'
        location_field = 'lost_location' if item_type == 'lost' else 'found_location'
        time_field = 'lost_time' if item_type == 'lost' else 'found_time'

        lines.append(f"Date: {item[date_field]}")
        if item.get(time_field):
            lines.append(f"Time: {item[time_field]}")
        lines.append(f"Location: {item[location_field]}")
        lines.append("")

        lines.append("Description:")
        lines.append(item['description'])
        lines.append("")

        if item.get('distinctive_features'):
            lines.append("Distinctive Features:")
            lines.append(item['distinctive_features'])
            lines.append("")

        if item.get('color'):
            lines.append(f"Color: {item['color']}")
        if item.get('brand'):
            lines.append(f"Brand: {item['brand']}")

        if item_type == 'lost' and item.get('estimated_value'):
            lines.append(f"Estimated Value: £{item['estimated_value']:.2f}")

        if item_type == 'found':
            if item.get('current_location'):
                lines.append(f"Current Location: {item['current_location']}")
            if item.get('storage_info'):
                lines.append(f"Storage Info: {item['storage_info']}")

        lines.append("")

        if item.get('contact_email'):
            lines.append(f"Contact Email: {item['contact_email']}")
        if item.get('contact_phone'):
            lines.append(f"Contact Phone: {item['contact_phone']}")

        lines.append("")
        lines.append(f"Reported: {item['reported_at']}")
        lines.append(f"Last Updated: {item['updated_at']}")

        if item.get('photos'):
            lines.append("")
            lines.append(f"Photos: {len(item['photos'])} attached")
            for photo in item['photos']:
                lines.append(f"  - {photo['photo_path']}")

        if item_type == 'found' and item.get('verification_questions'):
            lines.append("")
            lines.append("Verification Questions:")
            for q in item['verification_questions']:
                lines.append(f"  - {q['question_text']}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def update_item_status_dialog(self, item_type: str):
        """Show dialog to update item status"""
        tree = self.lost_tree if item_type == 'lost' else self.found_tree
        selection = tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select an item to update.")
            return

        item_id = tree.item(selection[0])['values'][0]

        # Status options
        if item_type == 'lost':
            statuses = ['Active', 'Found', 'Closed']
        else:
            statuses = ['Available', 'Claimed', 'Donated', 'Discarded']

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Item Status")
        dialog.geometry("400x250")

        ttk.Label(dialog, text=f"Update status for Item ID: {item_id}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text="New Status:").pack(pady=5)

        status_var = tk.StringVar(value=statuses[0])
        for status in statuses:
            ttk.Radiobutton(dialog, text=status, variable=status_var,
                          value=status).pack(pady=2)

        ttk.Label(dialog, text="Notes (optional):").pack(pady=5)
        notes_text = tk.Text(dialog, width=40, height=3)
        notes_text.pack(pady=5)

        def update():
            try:
                if item_type == 'lost':
                    self.service.update_lost_item_status(
                        item_id, status_var.get(),
                        notes_text.get("1.0", tk.END).strip()
                    )
                else:
                    self.service.update_found_item_status(
                        item_id, status_var.get(),
                        notes_text.get("1.0", tk.END).strip()
                    )

                messagebox.showinfo("Success", f"Item status updated to: {status_var.get()}")
                dialog.destroy()

                # Refresh lists
                if item_type == 'lost':
                    self.load_lost_items()
                    self.load_my_lost_items()
                else:
                    self.load_found_items()
                    self.load_my_found_items()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status:\n{str(e)}")

        ttk.Button(dialog, text="Update", command=update).pack(pady=10)

    def view_item_matches(self, item_type: str):
        """View potential matches for an item"""
        tree = self.lost_tree if item_type == 'lost' else self.found_tree
        selection = tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select an item to view matches.")
            return

        item_id = tree.item(selection[0])['values'][0]

        try:
            matches = self.service.get_matches(item_type, item_id)

            if not matches:
                messagebox.showinfo("No Matches", "No potential matches found for this item.")
                return

            # Create matches window
            matches_window = tk.Toplevel(self.root)
            matches_window.title(f"Potential Matches for Item {item_id}")
            matches_window.geometry("900x600")

            ttk.Label(matches_window, text=f"Potential Matches ({len(matches)} found)",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Treeview for matches
            columns = ('Score', 'Item Name', 'Description', 'Location', 'Date')
            match_tree = ttk.Treeview(matches_window, columns=columns, show='headings')

            for col in columns:
                match_tree.heading(col, text=col)
                if col == 'Description':
                    match_tree.column(col, width=250)
                else:
                    match_tree.column(col, width=120)

            match_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Populate matches
            import json
            for match in matches:
                location_field = 'found_location' if item_type == 'lost' else 'lost_location'
                date_field = 'found_date' if item_type == 'lost' else 'lost_date'

                desc = match['description'][:100] + "..." if len(match['description']) > 100 else match['description']

                match_tree.insert('', tk.END, values=(
                    f"{match['match_score']:.1f}%",
                    match['item_name'],
                    desc,
                    match[location_field],
                    match[date_field]
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load matches:\n{str(e)}")

    def submit_claim_dialog(self):
        """Show dialog to submit a claim for a found item"""
        selection = self.found_tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select a found item to claim.")
            return

        item_id = self.found_tree.item(selection[0])['values'][0]

        user = self.auth.get_current_user()
        if not user:
            messagebox.showerror("Error", "User not found.")
            return

        # Get item details
        try:
            item = self.service.get_found_item(item_id)
            if not item:
                messagebox.showerror("Error", "Item not found.")
                return

            # Create claim dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Submit Claim")
            dialog.geometry("600x600")

            ttk.Label(dialog, text=f"Submit Claim for: {item['item_name']}",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            ttk.Label(dialog, text=f"Found at: {item['found_location']} on {item['found_date']}").pack()

            # Claim description
            ttk.Label(dialog, text="Why do you believe this is your item?*",
                     font=('Arial', 10, 'bold')).pack(pady=(20, 5))
            claim_desc = tk.Text(dialog, width=60, height=4)
            claim_desc.pack(pady=5)

            # Verification questions
            verification_answers = {}
            if item.get('verification_questions'):
                ttk.Label(dialog, text="Verification Questions:",
                         font=('Arial', 10, 'bold')).pack(pady=(20, 5))

                questions_frame = ttk.Frame(dialog)
                questions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

                canvas = tk.Canvas(questions_frame)
                scrollbar = ttk.Scrollbar(questions_frame, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)

                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )

                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)

                for q in item['verification_questions']:
                    ttk.Label(scrollable_frame, text=q['question_text']).pack(anchor=tk.W, pady=2)
                    answer_entry = ttk.Entry(scrollable_frame, width=50)
                    answer_entry.pack(anchor=tk.W, pady=5)
                    verification_answers[q['question_id']] = answer_entry

                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")

            # Supporting evidence
            ttk.Label(dialog, text="Additional Supporting Evidence (optional):").pack(pady=(10, 5))
            evidence_text = tk.Text(dialog, width=60, height=3)
            evidence_text.pack(pady=5)

            def submit():
                claim_description = claim_desc.get("1.0", tk.END).strip()
                if not claim_description:
                    messagebox.showerror("Error", "Claim description is required.")
                    return

                # Get verification answers
                answers = {}
                for qid, entry_widget in verification_answers.items():
                    answers[qid] = entry_widget.get()

                try:
                    claim_id = self.service.submit_claim(
                        found_item_id=item_id,
                        claimant_id=user['username'],
                        claim_description=claim_description,
                        verification_answers=answers if answers else None,
                        supporting_evidence=evidence_text.get("1.0", tk.END).strip()
                    )

                    messagebox.showinfo("Success",
                                      f"Claim submitted successfully!\n"
                                      f"Claim ID: {claim_id}\n"
                                      f"Your claim will be reviewed by staff.")
                    dialog.destroy()
                    self.load_claims()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to submit claim:\n{str(e)}")

            ttk.Button(dialog, text="Submit Claim", command=submit).pack(pady=20)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item details:\n{str(e)}")

    def load_claims(self):
        """Load claims"""
        try:
            status_filter = self.claims_status_var.get()
            if status_filter == 'All':
                status_filter = None

            user = self.auth.get_current_user()
            user_role = user.get('role', '').lower() if user else 'student'

            # Staff can see all claims, students only see their own
            if user_role in ['admin', 'staff']:
                claims = self.service.get_claims(status=status_filter)
            else:
                claims = self.service.get_claims(claimant_id=user['username'], status=status_filter)

            # Clear existing
            for item in self.claims_tree.get_children():
                self.claims_tree.delete(item)

            # Populate
            for claim in claims:
                self.claims_tree.insert('', tk.END, values=(
                    claim['claim_id'],
                    claim['found_item_id'],
                    claim['claimant_id'],
                    claim['status'],
                    claim['submitted_at'][:16],
                    claim['reviewed_at'][:16] if claim.get('reviewed_at') else 'N/A'
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load claims:\n{str(e)}")

    def view_claim_details(self):
        """View details of a selected claim"""
        selection = self.claims_tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select a claim to view.")
            return

        claim_id = self.claims_tree.item(selection[0])['values'][0]

        try:
            claims = self.service.get_claims()
            claim = next((c for c in claims if c['claim_id'] == claim_id), None)

            if not claim:
                messagebox.showerror("Error", "Claim not found.")
                return

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Claim Details - {claim_id}")
            details_window.geometry("600x500")

            text = scrolledtext.ScrolledText(details_window, width=70, height=25,
                                            font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Format details
            lines = []
            lines.append("=" * 70)
            lines.append("CLAIM DETAILS")
            lines.append("=" * 70)
            lines.append("")
            lines.append(f"Claim ID: {claim['claim_id']}")
            lines.append(f"Found Item ID: {claim['found_item_id']}")
            lines.append(f"Claimant: {claim['claimant_id']}")
            lines.append(f"Status: {claim['status']}")
            lines.append(f"Submitted: {claim['submitted_at']}")
            lines.append("")
            lines.append("Claim Description:")
            lines.append(claim['claim_description'])
            lines.append("")

            if claim.get('verification_answers'):
                import json
                lines.append("Verification Answers:")
                answers = json.loads(claim['verification_answers'])
                for qid, answer in answers.items():
                    lines.append(f"  Q{qid}: {answer}")
                lines.append("")

            if claim.get('supporting_evidence'):
                lines.append("Supporting Evidence:")
                lines.append(claim['supporting_evidence'])
                lines.append("")

            if claim.get('reviewed_at'):
                lines.append(f"Reviewed: {claim['reviewed_at']}")
                lines.append(f"Reviewed By: {claim.get('reviewed_by', 'N/A')}")
                if claim.get('resolution_notes'):
                    lines.append("Resolution Notes:")
                    lines.append(claim['resolution_notes'])

            lines.append("")
            lines.append("=" * 70)

            text.insert('1.0', "\n".join(lines))
            text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load claim details:\n{str(e)}")

    def review_claim_dialog(self):
        """Review a claim (staff only)"""
        user = self.auth.get_current_user()
        if not user or user.get('role', '').lower() not in ['admin', 'staff']:
            messagebox.showerror("Access Denied", "Only staff can review claims.")
            return

        selection = self.claims_tree.selection()

        if not selection:
            messagebox.showinfo("Info", "Please select a claim to review.")
            return

        claim_id = self.claims_tree.item(selection[0])['values'][0]

        # Create review dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Review Claim")
        dialog.geometry("400x300")

        ttk.Label(dialog, text=f"Review Claim ID: {claim_id}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text="Decision:").pack(pady=5)

        decision_var = tk.StringVar(value="approve")
        ttk.Radiobutton(dialog, text="Approve", variable=decision_var,
                       value="approve").pack(pady=2)
        ttk.Radiobutton(dialog, text="Reject", variable=decision_var,
                       value="reject").pack(pady=2)

        ttk.Label(dialog, text="Resolution Notes:").pack(pady=10)
        notes_text = tk.Text(dialog, width=40, height=5)
        notes_text.pack(pady=5)

        def submit_review():
            notes = notes_text.get("1.0", tk.END).strip()
            if not notes:
                messagebox.showerror("Error", "Resolution notes are required.")
                return

            approved = (decision_var.get() == "approve")

            try:
                self.service.review_claim(
                    claim_id=claim_id,
                    reviewer_id=user['username'],
                    approved=approved,
                    resolution_notes=notes
                )

                status = "approved" if approved else "rejected"
                messagebox.showinfo("Success", f"Claim {status} successfully!")
                dialog.destroy()
                self.load_claims()
                self.load_found_items()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to review claim:\n{str(e)}")

        ttk.Button(dialog, text="Submit Review", command=submit_review).pack(pady=20)

    def load_matches(self):
        """Load potential matches"""
        item_type = self.match_type_var.get()
        item_id_str = self.match_item_id_var.get().strip()

        if not item_id_str:
            messagebox.showinfo("Info", "Please enter an item ID.")
            return

        try:
            item_id = int(item_id_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid item ID.")
            return

        try:
            matches = self.service.get_matches(item_type, item_id)

            # Clear existing
            for item in self.matches_tree.get_children():
                self.matches_tree.delete(item)

            if not matches:
                messagebox.showinfo("No Matches", "No potential matches found.")
                return

            # Populate
            import json
            for match in matches:
                location_field = 'found_location' if item_type == 'lost' else 'lost_location'
                date_field = 'found_date' if item_type == 'lost' else 'lost_date'

                desc = match['description'][:80] + "..." if len(match['description']) > 80 else match['description']

                reasons = json.loads(match['match_reasons']) if match.get('match_reasons') else []
                reasons_str = "; ".join(reasons)

                self.matches_tree.insert('', tk.END, values=(
                    f"{match['match_score']:.1f}%",
                    match['item_name'],
                    desc,
                    match[location_field],
                    match[date_field],
                    reasons_str
                ))

            messagebox.showinfo("Matches Found", f"Found {len(matches)} potential matches.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load matches:\n{str(e)}")

    def load_statistics(self):
        """Load system statistics"""
        try:
            stats = self.service.get_statistics()
            category_stats = self.service.get_category_breakdown()

            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete('1.0', tk.END)

            lines = []
            lines.append("=" * 80)
            lines.append(" " * 25 + "LOST & FOUND STATISTICS")
            lines.append("=" * 80)
            lines.append("")

            lines.append("LOST ITEMS:")
            lines.append("-" * 80)
            if stats.get('lost_items'):
                lost = stats['lost_items']
                lines.append(f"  Total Lost Items:    {lost.get('total') or 0:>6}")
                lines.append(f"  Active Reports:      {lost.get('active') or 0:>6}")
                lines.append(f"  Items Found:         {lost.get('found') or 0:>6}")
            lines.append("")

            lines.append("FOUND ITEMS:")
            lines.append("-" * 80)
            if stats.get('found_items'):
                found = stats['found_items']
                lines.append(f"  Total Found Items:   {found.get('total') or 0:>6}")
                lines.append(f"  Available:           {found.get('available') or 0:>6}")
                lines.append(f"  Claimed:             {found.get('claimed') or 0:>6}")
            lines.append("")

            lines.append("CLAIMS:")
            lines.append("-" * 80)
            if stats.get('claims'):
                claims = stats['claims']
                lines.append(f"  Total Claims:        {claims.get('total') or 0:>6}")
                lines.append(f"  Pending:             {claims.get('pending') or 0:>6}")
                lines.append(f"  Approved:            {claims.get('approved') or 0:>6}")
                lines.append(f"  Rejected:            {claims.get('rejected') or 0:>6}")
            lines.append("")

            lines.append("MATCHING:")
            lines.append("-" * 80)
            if stats.get('matches'):
                matches = stats['matches']
                lines.append(f"  Total Matches:       {matches.get('total_matches') or 0:>6}")
                avg_score = matches.get('avg_score')
                if avg_score is not None:
                    lines.append(f"  Avg Match Score:     {float(avg_score):>6.1f}%")
            lines.append("")

            lines.append("CATEGORY BREAKDOWN:")
            lines.append("-" * 80)

            lines.append("\nLost Items by Category:")
            if category_stats.get('lost'):
                for cat in category_stats['lost']:
                    category_name = cat['category'] if cat['category'] else 'Unknown'
                    lines.append(f"  {category_name:<25} {cat['count']:>5}")

            lines.append("\nFound Items by Category:")
            if category_stats.get('found'):
                for cat in category_stats['found']:
                    category_name = cat['category'] if cat['category'] else 'Unknown'
                    lines.append(f"  {category_name:<25} {cat['count']:>5}")

            lines.append("")
            lines.append("=" * 80)
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("=" * 80)

            self.stats_text.insert('1.0', "\n".join(lines))
            self.stats_text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics:\n{str(e)}")

    def refresh_all_tabs(self):
        """Refresh all data in tabs"""
        self.load_lost_items()
        self.load_found_items()
        self.load_my_lost_items()
        self.load_my_found_items()
        self.load_claims()
        self.load_statistics()


def launch_lost_found_gui(parent=None):
    """Launch the Lost & Found GUI"""
    if parent is None:
        root = tk.Tk()
        root.withdraw()
        parent = root

    app = LostFoundGUI(parent)
    return app
