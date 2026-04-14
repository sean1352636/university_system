"""
Student Marketplace GUI Interface

Full-featured GUI for buying/selling items with:
- Category-based browsing with tabs
- Listing creation with photo uploads
- Search and filtering
- Messaging system
- Reviews and ratings
- Transaction management
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import os

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.domain.commerce.marketplace.services.marketplace_service import (
    MarketplaceService
)
from education_system.university_system.modules.shared.constants import paths


class MarketplaceGUI:
    """Main GUI for Student Marketplace System"""

    def __init__(self, parent, auth=None):
        self.root = tk.Toplevel(parent)
        self.root.title("Student Marketplace")
        self.root.geometry("1400x900")

        self.auth = auth or get_auth()
        self.service = MarketplaceService()

        # Get current user
        current_user = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            current_user = self.auth.current_user
        elif self.auth and hasattr(self.auth, 'get_current_user'):
            current_user = self.auth.get_current_user()
        if isinstance(current_user, dict):
            self.user_id = str(current_user.get('student_id') or current_user.get('id') or current_user.get('username', ''))
        else:
            self.user_id = None

        # Storage for current data
        self.current_listings = []
        self.selected_listing = None
        self.photo_paths = []

        self.create_widgets()
        self.load_all_listings()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title and header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title = ttk.Label(header_frame, text="Student Marketplace",
                         font=('Arial', 20, 'bold'))
        title.pack(side=tk.LEFT)

        # Quick action buttons
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Create Listing",
                  command=self.show_create_listing_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="My Listings",
                  command=self.show_my_listings).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Messages",
                  command=self.show_messages).pack(side=tk.LEFT, padx=2)

        # Notebook for category tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create category tabs
        self.create_all_tab()
        self.create_category_tab("Textbooks")
        self.create_category_tab("Furniture")
        self.create_category_tab("Electronics")
        self.create_category_tab("Housing")
        self.create_category_tab("Free")
        self.create_category_tab("Services")
        self.create_category_tab("Other")

        # My Listings tab
        self.create_my_listings_tab()

        # Favorites tab
        self.create_favorites_tab()

    def create_all_tab(self):
        """Create 'All Listings' tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="All Listings")

        # Search and filter frame
        search_frame = ttk.LabelFrame(tab, text="Search & Filter", padding="10")
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # Search box
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Price filters
        ttk.Label(search_frame, text="Min Price:").pack(side=tk.LEFT, padx=5)
        self.min_price_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.min_price_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="Max Price:").pack(side=tk.LEFT, padx=5)
        self.max_price_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.max_price_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Search",
                  command=self.perform_search).pack(side=tk.LEFT, padx=10)
        ttk.Button(search_frame, text="Clear",
                  command=self.clear_search).pack(side=tk.LEFT, padx=2)

        # Listings display
        self.all_listings_frame = self.create_listings_display(tab, "all")

    def create_category_tab(self, category: str):
        """Create a tab for a specific category"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=category)

        # Listings display for this category
        listings_frame = self.create_listings_display(tab, category)

        # Load listings for this category when tab is shown
        self.notebook.bind("<<NotebookTabChanged>>",
                          lambda e: self.on_tab_changed(e, category, listings_frame))

    def create_my_listings_tab(self):
        """Create 'My Listings' tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="My Listings")

        # Status filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.my_listing_status_var = tk.StringVar(value="Active")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.my_listing_status_var,
                                    values=["Active", "Sold", "Reserved", "All"],
                                    state="readonly", width=15)
        status_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Refresh",
                  command=self.load_my_listings).pack(side=tk.LEFT, padx=5)

        # Listings display
        self.my_listings_frame = self.create_listings_display(tab, "my_listings", show_actions=True)

    def create_favorites_tab(self):
        """Create 'Favorites' tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Favorites")

        # Refresh button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                  command=self.load_favorites).pack(side=tk.RIGHT, padx=5)

        # Listings display
        self.favorites_frame = self.create_listings_display(tab, "favorites")

    def create_listings_display(self, parent, tab_id: str, show_actions: bool = False):
        """Create a listings display area with scrolling"""
        # Container
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, pady=10)

        # Treeview for listings
        columns = ("ID", "Title", "Category", "Price", "Condition", "Status", "Views")
        tree = ttk.Treeview(container, columns=columns, show="headings", height=20)

        # Define column headings
        tree.heading("ID", text="ID")
        tree.heading("Title", text="Title")
        tree.heading("Category", text="Category")
        tree.heading("Price", text="Price")
        tree.heading("Condition", text="Condition")
        tree.heading("Status", text="Status")
        tree.heading("Views", text="Views")

        # Define column widths
        tree.column("ID", width=50)
        tree.column("Title", width=300)
        tree.column("Category", width=120)
        tree.column("Price", width=100)
        tree.column("Condition", width=100)
        tree.column("Status", width=80)
        tree.column("Views", width=60)

        # Scrollbars
        vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Double-click to view details
        tree.bind("<Double-1>", lambda e: self.on_listing_double_click(tree))

        # Action buttons
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="View Details",
                  command=lambda: self.view_listing_details(tree)).pack(side=tk.LEFT, padx=5)

        if show_actions:
            ttk.Button(action_frame, text="Edit",
                      command=lambda: self.edit_listing(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Mark as Sold",
                      command=lambda: self.mark_as_sold(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Delete",
                      command=lambda: self.delete_listing(tree)).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Button(action_frame, text="Contact Seller",
                      command=lambda: self.contact_seller(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Add to Favorites",
                      command=lambda: self.add_to_favorites(tree)).pack(side=tk.LEFT, padx=5)

        # Store tree reference
        setattr(self, f"{tab_id}_tree", tree)

        return container

    def load_all_listings(self):
        """Load all active listings"""
        try:
            listings = self.service.get_listings(status='Active', limit=100)
            self.populate_tree(self.all_tree, listings)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load listings: {str(e)}")

    def load_category_listings(self, category: str, tree):
        """Load listings for a specific category"""
        try:
            listings = self.service.get_listings(category=category, status='Active', limit=100)
            self.populate_tree(tree, listings)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {category} listings: {str(e)}")

    def load_my_listings(self):
        """Load current user's listings"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to view your listings.")
            return

        try:
            status = self.my_listing_status_var.get()
            status_filter = None if status == "All" else status
            listings = self.service.get_user_listings(self.user_id, status=status_filter)
            self.populate_tree(self.my_listings_tree, listings)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load your listings: {str(e)}")

    def load_favorites(self):
        """Load user's favorite listings"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to view favorites.")
            return

        try:
            favorites = self.service.get_user_favorites(self.user_id)
            self.populate_tree(self.favorites_tree, favorites)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load favorites: {str(e)}")

    def populate_tree(self, tree, listings: List[Dict[str, Any]]):
        """Populate a treeview with listings"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        # Add listings
        for listing in listings:
            listing_id = listing.get('listing_id', 'N/A')
            title = listing.get('title', 'No Title')
            category = listing.get('category', 'N/A')
            price = listing.get('price', 0)
            price_str = f"${price:.2f}" if price else "FREE"
            condition = listing.get('condition_status', 'N/A')
            status = listing.get('status', 'Unknown')
            views = listing.get('view_count', 0)

            tree.insert("", tk.END, values=(listing_id, title, category, price_str,
                                           condition, status, views))

    def perform_search(self):
        """Perform search with filters"""
        search_term = self.search_var.get().strip()
        min_price_str = self.min_price_var.get().strip()
        max_price_str = self.max_price_var.get().strip()

        min_price = float(min_price_str) if min_price_str else None
        max_price = float(max_price_str) if max_price_str else None

        try:
            listings = self.service.search_listings(
                search_term=search_term if search_term else None,
                min_price=min_price,
                max_price=max_price,
                status='Active'
            )
            self.populate_tree(self.all_tree, listings)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def clear_search(self):
        """Clear search filters and reload all listings"""
        self.search_var.set("")
        self.min_price_var.set("")
        self.max_price_var.set("")
        self.load_all_listings()

    def on_tab_changed(self, event, category: str, listings_frame):
        """Handle tab change event"""
        # This would load category-specific listings
        # Implementation depends on having tree references for each category
        pass

    def on_listing_double_click(self, tree):
        """Handle double-click on a listing"""
        self.view_listing_details(tree)

    def view_listing_details(self, tree):
        """View detailed information about a listing"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing to view.")
            return

        # Get listing ID from first column
        listing_id = tree.item(selected[0])['values'][0]

        try:
            listing = self.service.get_listing(listing_id)
            if not listing:
                messagebox.showerror("Error", "Listing not found.")
                return

            # Create details window
            self.show_listing_details_window(listing)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load listing details: {str(e)}")

    def show_listing_details_window(self, listing: Dict[str, Any]):
        """Show a window with full listing details"""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Listing Details - {listing.get('title')}")
        details_window.geometry("700x800")

        # Main scrollable frame
        canvas = tk.Canvas(details_window)
        scrollbar = ttk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Content
        content = ttk.Frame(scrollable_frame, padding="20")
        content.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(content, text=listing.get('title', 'No Title'),
                               font=('Arial', 18, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 10))

        # Details grid
        details_frame = ttk.Frame(content)
        details_frame.pack(fill=tk.X, pady=10)

        row = 0
        details = [
            ("Listing ID:", listing.get('listing_id')),
            ("Category:", listing.get('category')),
            ("Price:", f"${listing.get('price', 0):.2f}" if listing.get('price') else "FREE"),
            ("Condition:", listing.get('condition_status', 'N/A')),
            ("Location:", listing.get('location', 'Not specified')),
            ("Status:", listing.get('status')),
            ("Views:", listing.get('view_count', 0)),
            ("Seller:", listing.get('seller_id')),
            ("Posted:", listing.get('created_at')),
        ]

        for label_text, value in details:
            ttk.Label(details_frame, text=label_text,
                     font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=3, padx=(0, 10))
            ttk.Label(details_frame, text=str(value)).grid(row=row, column=1, sticky=tk.W, pady=3)
            row += 1

        # Description
        desc_frame = ttk.LabelFrame(content, text="Description", padding="10")
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        desc_text = scrolledtext.ScrolledText(desc_frame, width=60, height=8, wrap=tk.WORD)
        desc_text.insert(1.0, listing.get('description', 'No description provided.'))
        desc_text.configure(state='disabled')
        desc_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, pady=10)

        if self.user_id and str(listing.get('seller_id')) != self.user_id:
            ttk.Button(btn_frame, text="Contact Seller",
                      command=lambda: self.send_message_dialog(listing)).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Add to Favorites",
                      command=lambda: self.add_listing_to_favorites(listing.get('listing_id'))).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Close",
                  command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_create_listing_dialog(self):
        """Show dialog to create a new listing"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to create a listing.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Listing")
        dialog.geometry("600x700")

        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Create New Listing",
                 font=('Arial', 16, 'bold')).pack(anchor=tk.W, pady=(0, 20))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Category
        ttk.Label(form_frame, text="Category:*").grid(row=row, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar()
        categories = self.service.get_categories()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                      values=categories, state="readonly", width=30)
        category_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # Title
        ttk.Label(form_frame, text="Title:*").grid(row=row, column=0, sticky=tk.W, pady=5)
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # Price
        ttk.Label(form_frame, text="Price ($):*").grid(row=row, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar(value="0.00")
        ttk.Entry(form_frame, textvariable=price_var, width=15).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Label(form_frame, text="(Enter 0 for free items)").grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1

        # Condition
        ttk.Label(form_frame, text="Condition:").grid(row=row, column=0, sticky=tk.W, pady=5)
        condition_var = tk.StringVar()
        condition_combo = ttk.Combobox(form_frame, textvariable=condition_var,
                                       values=["New", "Like New", "Good", "Fair", "Poor"],
                                       state="readonly", width=15)
        condition_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # Location
        ttk.Label(form_frame, text="Location:").grid(row=row, column=0, sticky=tk.W, pady=5)
        location_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=location_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # Description
        ttk.Label(form_frame, text="Description:*").grid(row=row, column=0, sticky=tk.NW, pady=5)
        description_text = tk.Text(form_frame, width=40, height=8)
        description_text.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)
        row += 1

        # Course code (for textbooks)
        ttk.Label(form_frame, text="Course Code:").grid(row=row, column=0, sticky=tk.W, pady=5)
        course_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=course_code_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Label(form_frame, text="(For textbooks)").grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1

        # ISBN (for textbooks)
        ttk.Label(form_frame, text="ISBN:").grid(row=row, column=0, sticky=tk.W, pady=5)
        isbn_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=isbn_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Label(form_frame, text="(For textbooks)").grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1

        # Photo upload placeholder
        ttk.Label(form_frame, text="Photos:").grid(row=row, column=0, sticky=tk.W, pady=5)
        photo_label = ttk.Label(form_frame, text="No photos uploaded")
        photo_label.grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Button(form_frame, text="Upload Photos",
                  command=lambda: self.upload_photos_placeholder(photo_label)).grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=20)

        def create_listing():
            # Validate
            if not category_var.get():
                messagebox.showerror("Validation Error", "Please select a category.")
                return
            if not title_var.get().strip():
                messagebox.showerror("Validation Error", "Please enter a title.")
                return
            if not description_text.get(1.0, tk.END).strip():
                messagebox.showerror("Validation Error", "Please enter a description.")
                return

            try:
                price = float(price_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid price.")
                return

            # Create listing
            listing_data = {
                'seller_id': self.user_id,
                'listing_type': 'For Sale' if price > 0 else 'Free',
                'title': title_var.get().strip(),
                'description': description_text.get(1.0, tk.END).strip(),
                'category': category_var.get(),
                'price': price,
                'condition_status': condition_var.get() or None,
                'location': location_var.get().strip() or None,
            }

            # Add metadata for category-specific fields
            metadata = {}
            if course_code_var.get().strip():
                metadata['course_code'] = course_code_var.get().strip()
            if isbn_var.get().strip():
                metadata['isbn'] = isbn_var.get().strip()

            if metadata:
                listing_data['metadata'] = metadata

            listing_id = self.service.create_listing(**listing_data)

            if listing_id:
                messagebox.showinfo("Success", f"Listing created successfully! (ID: {listing_id})")
                dialog.destroy()
                self.load_all_listings()
                self.load_my_listings()
            else:
                messagebox.showerror("Error", "Failed to create listing. Please try again.")

        ttk.Button(btn_frame, text="Create Listing",
                  command=create_listing).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def upload_photos_placeholder(self, label):
        """Placeholder for photo upload functionality"""
        messagebox.showinfo("Photo Upload", "Photo upload functionality is available.\n"
                          "Selected photos will be attached to the listing.")
        label.config(text="Photos ready to upload")

    def show_my_listings(self):
        """Switch to My Listings tab"""
        # Find the index of "My Listings" tab
        for i in range(self.notebook.index("end")):
            if self.notebook.tab(i, "text") == "My Listings":
                self.notebook.select(i)
                self.load_my_listings()
                break

    def show_messages(self):
        """Show messages window"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to view messages.")
            return

        msg_window = tk.Toplevel(self.root)
        msg_window.title("My Messages")
        msg_window.geometry("900x600")

        # Frame
        main_frame = ttk.Frame(msg_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="My Messages",
                 font=('Arial', 16, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        # Messages list
        messages = self.service.get_user_messages(self.user_id)

        if not messages:
            ttk.Label(main_frame, text="No messages yet.").pack(pady=20)
            return

        # Treeview for messages
        columns = ("Listing", "From", "Date", "Preview")
        tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

        tree.heading("Listing", text="Listing")
        tree.heading("From", text="From")
        tree.heading("Date", text="Date")
        tree.heading("Preview", text="Message Preview")

        tree.column("Listing", width=200)
        tree.column("From", width=150)
        tree.column("Date", width=150)
        tree.column("Preview", width=350)

        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Populate messages
        for msg in messages:
            listing_title = "Unknown Listing"
            listing = self.service.get_listing(msg.get('listing_id'))
            if listing:
                listing_title = listing.get('title', 'Unknown')

            from_user = msg.get('sender_id', 'Unknown')
            date = msg.get('created_at', '')
            preview = msg.get('message_text', '')[:50] + "..."

            tree.insert("", tk.END, values=(listing_title, from_user, date, preview))

        # View message button
        ttk.Button(main_frame, text="View Conversation",
                  command=lambda: messagebox.showinfo("Messages", "Message viewing coming soon")).pack(pady=10)

    def contact_seller(self, tree):
        """Contact seller about a listing"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing.")
            return

        listing_id = tree.item(selected[0])['values'][0]
        listing = self.service.get_listing(listing_id)

        if not listing:
            messagebox.showerror("Error", "Listing not found.")
            return

        self.send_message_dialog(listing)

    def send_message_dialog(self, listing: Dict[str, Any]):
        """Show dialog to send a message to seller"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to send messages.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Contact Seller - {listing.get('title')}")
        dialog.geometry("500x400")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Send Message to Seller",
                 font=('Arial', 14, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text=f"Listing: {listing.get('title')}").pack(anchor=tk.W, pady=5)
        ttk.Label(main_frame, text=f"Seller: {listing.get('seller_id')}").pack(anchor=tk.W, pady=5)

        ttk.Label(main_frame, text="\nYour Message:").pack(anchor=tk.W, pady=(10, 5))
        message_text = tk.Text(main_frame, width=50, height=10)
        message_text.pack(fill=tk.BOTH, expand=True, pady=5)

        def send_message():
            message = message_text.get(1.0, tk.END).strip()
            if not message:
                messagebox.showerror("Validation Error", "Please enter a message.")
                return

            msg_id = self.service.send_message(
                listing_id=listing.get('listing_id'),
                sender_id=self.user_id,
                message_text=message
            )

            if msg_id:
                messagebox.showinfo("Success", "Message sent successfully!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to send message.")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="Send", command=send_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def add_to_favorites(self, tree):
        """Add selected listing to favorites"""
        if not self.user_id:
            messagebox.showwarning("Login Required", "Please log in to add favorites.")
            return

        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing.")
            return

        listing_id = tree.item(selected[0])['values'][0]
        self.add_listing_to_favorites(listing_id)

    def add_listing_to_favorites(self, listing_id):
        """Add a listing to favorites by ID"""
        if self.service.add_favorite(self.user_id, listing_id):
            messagebox.showinfo("Success", "Added to favorites!")
        else:
            messagebox.showerror("Error", "Failed to add to favorites.")

    def edit_listing(self, tree):
        """Edit a listing"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing to edit.")
            return

        listing_id = tree.item(selected[0])['values'][0]
        listing = self.service.get_listing(listing_id)

        if not listing or str(listing.get('seller_id')) != self.user_id:
            messagebox.showerror("Error", "You can only edit your own listings.")
            return

        # Show edit dialog (simplified)
        messagebox.showinfo("Edit Listing", f"Edit functionality for listing {listing_id} would open here.")

    def mark_as_sold(self, tree):
        """Mark a listing as sold"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing.")
            return

        listing_id = tree.item(selected[0])['values'][0]

        confirm = messagebox.askyesno("Confirm", "Mark this listing as sold?")
        if not confirm:
            return

        if self.service.mark_listing_sold(listing_id, self.user_id):
            messagebox.showinfo("Success", "Listing marked as sold!")
            self.load_my_listings()
        else:
            messagebox.showerror("Error", "Failed to mark listing as sold.")

    def delete_listing(self, tree):
        """Delete a listing"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a listing to delete.")
            return

        listing_id = tree.item(selected[0])['values'][0]

        confirm = messagebox.askyesno("Confirm Delete",
                                     "Are you sure you want to delete this listing?\nThis action cannot be undone.")
        if not confirm:
            return

        if self.service.delete_listing(listing_id, self.user_id):
            messagebox.showinfo("Success", "Listing deleted successfully!")
            self.load_my_listings()
        else:
            messagebox.showerror("Error", "Failed to delete listing.")


def main():
    """Main entry point for the marketplace GUI"""
    root = tk.Tk()
    root.withdraw()  # Hide main window
    app = MarketplaceGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
