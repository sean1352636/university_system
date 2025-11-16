import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import time
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

try:
    from university_system.modules.domain.commerce.services.shop_management import (
        auth, add_to_shopping_cart, browse_products, checkout_process,
        display_product_management_menu, display_shop_menu,
        get_customer_analytics, get_inventory_valuation, init_shop_db,
        print_product_labels, search_products, set_auth,
        toggle_discount_status, toggle_product_status, view_purchase_history
    )
except Exception:
    try:
        from shop_management import (
            auth, add_to_shopping_cart, browse_products, checkout_process,
            display_product_management_menu, display_shop_menu,
            get_customer_analytics, get_inventory_valuation, init_shop_db,
            print_product_labels, search_products, set_auth,
            toggle_discount_status, toggle_product_status, view_purchase_history
        )
    except Exception:
        # If running standalone, we'll define the essential functions
        pass

try:
    from university_system.modules.domain.commerce.services.shop_management import (
        get_customer_analytics, get_inventory_valuation, 
        print_product_labels, get_low_stock_items
    )
except ImportError:
    # Fallback functions if shop_management is not available
    def get_customer_analytics():
        return None
    
    def get_inventory_valuation():
        return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}
    
    def print_product_labels(product_ids=None):
        print("Label printing functionality not available")
    
    def get_low_stock_items():
        return []

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

class UniversityShopGUI:
    def __init__(self, root, auth=None):
        """
        Initialize University Shop GUI.

        Args:
            root: Tkinter root window
            auth: Authentication instance (if None, will use get_auth())

        Raises:
            RuntimeError: If authentication system is not available
        """
        self.root = root

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                "Authentication Required",
                "Authentication system not available. Shop Management GUI cannot start."
            )
            root.destroy()
            return

        # Don't set title and geometry if this is a Toplevel window (integrated mode)
        if not isinstance(root, tk.Toplevel):
            self.root.title("University Shop Management System")
            self.root.geometry("1200x800")
            self.root.minsize(1000, 600)

        # Configure style
        self.setup_styles()
        
        # Initialize variables
        self.current_user = None
        self.cart_items = []

        # Initialize the original CLI system
        self.initialize_backend()

        # Create GUI components
        self.create_widgets()

        # Check if user is already authenticated via central auth system
        self.setup_current_user()

        # SECURITY: Require central authentication - no standalone login
        if not self.current_user:
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui"
            )
            root.destroy()
            return

        # Show main interface for authenticated users
        self.show_main_interface()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                # auth_user is already a dictionary from UserAuth system
                if isinstance(auth_user, dict):
                    self.current_user = {
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', [])
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', [])
                    }

                print(f"✓ University Shop GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = None
                print("ℹ University Shop GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = None

    def set_auth(self, auth_system):
        """Set the authentication system from the main application"""
        self.auth = auth_system
        if auth_system and auth_system.current_user:
            self.current_user = auth_system.current_user
            # Update user display and show main interface
            self.show_main_interface()

    def get_user_role(self):
        """Get the current user's role"""
        try:
            if self.current_user and isinstance(self.current_user, dict):
                return self.current_user.get('role', '').lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff or shop manager"""
        role = self.get_user_role()
        return role in ['staff', 'shop_manager']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def setup_styles(self):
        """Configure GUI styles and themes"""
        style = ttk.Style()
        
        # Configure colors and fonts
        self.colors = {
            'primary': '#2E3440',
            'secondary': '#3B4252',
            'accent': '#88C0D0',
            'success': '#A3BE8C',
            'warning': '#EBCB8B',
            'error': '#BF616A',
            'background': '#ECEFF4',
            'text': '#2E3440'
        }
        
        # Configure styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground=self.colors['primary'])
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), foreground=self.colors['primary'])
        style.configure('Success.TLabel', foreground=self.colors['success'])
        style.configure('Warning.TLabel', foreground=self.colors['warning'])
        style.configure('Error.TLabel', foreground=self.colors['error'])
        
        # Configure button styles
        style.configure('Primary.TButton', background=self.colors['accent'])
        style.configure('Success.TButton', background=self.colors['success'])
        style.configure('Warning.TButton', background=self.colors['warning'])
        style.configure('Danger.TButton', background=self.colors['error'])
        
    def initialize_backend(self):
        """Initialize the backend CLI system for compatibility"""
        try:
            # Initialize database
            if 'init_shop_db' in globals():
                init_shop_db()

            # Initialize centralized authentication system
            if self.auth is None:  # Only create if not passed from parent
                self.auth = UserAuth()

        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize backend: {e}")
            
    def create_widgets(self):
        """Create main GUI widgets"""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
        # Header frame
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Title
        self.title_label = ttk.Label(self.header_frame, text="University Shop Management System", 
                                   style='Title.TLabel')
        self.title_label.grid(row=0, column=0, sticky=tk.W)
        
        # User info and logout
        self.user_frame = ttk.Frame(self.header_frame)
        self.user_frame.grid(row=0, column=1, sticky=tk.E)
        
        self.user_label = ttk.Label(self.user_frame, text="Not logged in")
        self.user_label.grid(row=0, column=0, padx=(0, 10))
        
        self.logout_btn = ttk.Button(self.user_frame, text="🏠 Return to Main Menu", command=self.return_to_main_menu)
        self.logout_btn.grid(row=0, column=1)
        self.logout_btn.configure(state='disabled')
        
        self.header_frame.columnconfigure(1, weight=1)
        
        # Create scrollable sidebar for navigation
        sidebar_container = ttk.LabelFrame(self.main_frame, text="Navigation", padding="5")
        sidebar_container.grid(row=1, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 10))

        # Canvas + scrollbar for sidebar
        self.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, bg='#f0f0f0', width=200)
        self.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar_frame = ttk.Frame(self.sidebar_canvas)

        # Put sidebar frame inside canvas
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.sidebar_frame, anchor="nw")

        # Wire up scrolling
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.sidebar_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Configure grid weights for sidebar container
        sidebar_container.rowconfigure(0, weight=1)
        sidebar_container.columnconfigure(0, weight=1)

        # Keep sidebar width in sync with canvas width
        def _on_sidebar_canvas_configure(event):
            self.sidebar_canvas.itemconfig(self.sidebar_window, width=event.width)
        self.sidebar_canvas.bind("<Configure>", _on_sidebar_canvas_configure)

        # Update scrollregion whenever sidebar content changes
        self.sidebar_frame.bind(
            "<Configure>",
            lambda e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        )

        # Bind mouse wheel scrolling for sidebar
        self._bind_sidebar_scroll_events()

    def _bind_sidebar_scroll_events(self):
        """Bind mouse wheel and keys to sidebar scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
                if event.delta:  # Windows
                    self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:            # Linux
                    if event.num == 4:
                        self.sidebar_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        self.sidebar_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.sidebar_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.sidebar_canvas.yview_scroll(-10, "units")
                elif event.keysym == 'Page_Down':
                    self.sidebar_canvas.yview_scroll(10, "units")

        # Bind to sidebar and its children
        if hasattr(self, 'sidebar_canvas'):
            self.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
            self.sidebar_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
            self.sidebar_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
            self.sidebar_canvas.bind("<KeyPress>", _on_keypress)
            self.sidebar_canvas.focus_set()

        # Main content area with scrollbar
        content_container = ttk.Frame(self.main_frame, padding="10")
        content_container.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create canvas and scrollbar for content area
        self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_frame = ttk.Frame(self.content_canvas)

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        )

        self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        content_container.columnconfigure(0, weight=1)
        content_container.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)
        
        # Status bar
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Progress bar (hidden by default)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.status_frame, variable=self.progress_var)
        self.progress_bar.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
        self.progress_bar.grid_remove()
        
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()
        
    def show_main_interface(self):
        """Display main shop interface after login"""
        # Update user info
        user_info = f"Logged in as: {self.current_user['username']} ({self.current_user.get('role', 'user')})"
        self.user_label.config(text=user_info)
        self.logout_btn.configure(state='normal')
        
        # Create navigation menu
        self.create_navigation_menu()
        
        # Show dashboard by default
        self.show_dashboard()
        
        # Unbind Enter key
        self.root.unbind('<Return>')
        
    def create_navigation_menu(self):
        """Create navigation sidebar with role-based filtering"""
        # Clear existing navigation
        for widget in self.sidebar_frame.winfo_children():
            widget.destroy()

        # Get user role for filtering
        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # Customer options (available to all)
        ttk.Label(self.sidebar_frame, text="Shopping", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        ttk.Button(self.sidebar_frame, text="🏠 Dashboard",
                  command=self.show_dashboard, width=20).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Button(self.sidebar_frame, text="🛍️ Browse Products",
                  command=self.show_browse_products, width=20).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Button(self.sidebar_frame, text="🛒 Shopping Cart",
                  command=self.show_shopping_cart, width=20).grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Button(self.sidebar_frame, text="📋 Order History",
                  command=self.show_order_history, width=20).grid(row=4, column=0, sticky=tk.W, pady=2)

        row_counter = 5

        # Admin/Staff management options
        if is_admin or is_staff:
            ttk.Separator(self.sidebar_frame, orient='horizontal').grid(row=row_counter, column=0, sticky=(tk.W, tk.E), pady=10)
            row_counter += 1

            ttk.Label(self.sidebar_frame, text="Management", style='Heading.TLabel').grid(row=row_counter, column=0, sticky=tk.W, pady=(0, 5))
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="📦 Manage Products",
                      command=self.show_manage_products, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="📊 Inventory",
                      command=self.show_manage_inventory, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="💰 Transactions",
                      command=self.show_all_transactions, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="🎯 Discounts",
                      command=self.show_manage_discounts, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="📈 Reports",
                      command=self.show_reports, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="📊 Analytics",
                      command=self.show_analytics_dashboard, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(self.sidebar_frame, text="🏷️ Print Labels",
                      command=self.show_print_labels_dialog, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

        # Utility options
        ttk.Separator(self.sidebar_frame, orient='horizontal').grid(row=row_counter, column=0, sticky=(tk.W, tk.E), pady=10)
        row_counter += 1

        ttk.Label(self.sidebar_frame, text="Utilities", style='Heading.TLabel').grid(row=row_counter, column=0, sticky=tk.W, pady=(0, 5))
        row_counter += 1

        ttk.Button(self.sidebar_frame, text="🖥️ CLI Mode",
                  command=self.launch_cli_mode, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        ttk.Button(self.sidebar_frame, text="ℹ️ About",
                  command=self.show_about, width=20).grid(row=row_counter, column=0, sticky=tk.W, pady=2)

        # Force scroll region update after all content is added
        self.sidebar_frame.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

    def show_analytics_dashboard(self):
        """Display analytics dashboard"""
        self.clear_content()
        self.update_status("Loading analytics...")
        
        # Check permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
            ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
            return
        
        # Title
        ttk.Label(self.content_frame, text="Analytics Dashboard", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))
        
        # Create main dashboard frame
        dash_frame = ttk.Frame(self.content_frame)
        dash_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        dash_frame.columnconfigure((0, 1), weight=1)
        
        # Sales analytics
        sales_frame = ttk.LabelFrame(dash_frame, text="Sales Analytics", padding="10")
        sales_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))
        
        try:
            analytics = get_customer_analytics()
            if analytics and analytics['overview']:
                overview = analytics['overview']
                ttk.Label(sales_frame, text=f"Revenue (30 days): £{overview.get('total_revenue', 0):.2f}").grid(row=0, column=0, sticky=tk.W, pady=2)
                ttk.Label(sales_frame, text=f"Total Customers: {overview.get('total_customers', 0)}").grid(row=1, column=0, sticky=tk.W, pady=2)
                ttk.Label(sales_frame, text=f"Avg Order Value: £{overview.get('avg_order_value', 0):.2f}").grid(row=2, column=0, sticky=tk.W, pady=2)
        except Exception:
            ttk.Label(sales_frame, text="Analytics data unavailable").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Inventory analytics
        inventory_frame = ttk.LabelFrame(dash_frame, text="Inventory Analytics", padding="10")
        inventory_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))
        
        try:
            valuation = get_inventory_valuation()
            ttk.Label(inventory_frame, text=f"Total Inventory Value: £{valuation['total_value']:.2f}").grid(row=0, column=0, sticky=tk.W, pady=2)
            ttk.Label(inventory_frame, text=f"Total Products: {valuation['product_count']}").grid(row=1, column=0, sticky=tk.W, pady=2)
            ttk.Label(inventory_frame, text=f"Total Items: {valuation['total_quantity']}").grid(row=2, column=0, sticky=tk.W, pady=2)
            
            # Low stock alert
            low_stock_count = len(self.get_low_stock_items())
            if low_stock_count > 0:
                ttk.Label(inventory_frame, text=f"⚠️ Low Stock Items: {low_stock_count}", 
                         style='Warning.TLabel').grid(row=3, column=0, sticky=tk.W, pady=2)
        except Exception:
            ttk.Label(inventory_frame, text="Inventory data unavailable").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Action buttons
        action_frame = ttk.Frame(dash_frame)
        action_frame.grid(row=1, column=0, columnspan=2, pady=20)
        
        ttk.Button(action_frame, text="View Customer Analytics",
                  command=self.show_customer_analytics).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="Generate Reports", 
                  command=self.show_reports).grid(row=0, column=1, padx=5)
        ttk.Button(action_frame, text="Bulk Operations", 
                  command=self.show_bulk_operations).grid(row=0, column=2, padx=5)
        
        self.update_status("Analytics dashboard loaded")

    def show_customer_analytics(self):
        """Display customer analytics"""
        try:
            # Get customer analytics data
            analytics = get_customer_analytics()

            if not analytics:
                messagebox.showinfo("Customer Analytics",
                                  "No customer analytics data available.\n"
                                  "This feature requires customer transaction history.")
                return

            # Create analytics window
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Customer Analytics")
            analytics_window.geometry("800x600")
            analytics_window.transient(self.root)

            main_frame = ttk.Frame(analytics_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Customer Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Display analytics data
            from tkinter.scrolledtext import ScrolledText
            text_widget = ScrolledText(main_frame, height=25, width=90, font=('Courier', 9))
            text_widget.pack(fill='both', expand=True, pady=10)

            # Format analytics as text
            analytics_text = "CUSTOMER ANALYTICS REPORT\n"
            analytics_text += "=" * 80 + "\n\n"

            if isinstance(analytics, dict):
                for key, value in analytics.items():
                    analytics_text += f"{key}: {value}\n"
            else:
                analytics_text += str(analytics)

            text_widget.insert('1.0', analytics_text)
            text_widget.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=analytics_window.destroy).pack(pady=10)

            analytics_window.update_idletasks()
            analytics_window.grab_set()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customer analytics:\n{str(e)}")

    def show_print_labels_dialog(self):
        """Show dialog for printing product labels"""
        # Create print labels window
        labels_window = tk.Toplevel(self.root)
        labels_window.title("Print Product Labels")
        labels_window.geometry("400x300")
        labels_window.resizable(False, False)
        
        # Make it modal
        labels_window.transient(self.root)
        labels_window.grab_set()
        
        main_frame = ttk.Frame(labels_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        ttk.Label(main_frame, text="Print Product Labels", style='Title.TLabel').grid(row=0, column=0, pady=(0, 20))
        
        # Options
        print_option = tk.StringVar(value="all")
        
        ttk.Radiobutton(main_frame, text="Print all products", 
                       variable=print_option, value="all").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text="Print by category", 
                       variable=print_option, value="category").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text="Print low stock items only", 
                       variable=print_option, value="low_stock").grid(row=3, column=0, sticky=tk.W, pady=5)
        
        # Category selection (initially disabled)
        category_frame = ttk.Frame(main_frame)
        category_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(category_frame, text="Category:").grid(row=0, column=0, sticky=tk.W)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(category_frame, textvariable=category_var, 
                                     values=[], state="disabled", width=25)
        category_combo.grid(row=0, column=1, padx=(10, 0))
        
        # Load categories
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
                categories = [row[0] for row in cursor.fetchall()]
                category_combo.configure(values=categories)
                conn.close()
        except Exception:
            pass
        
        def on_option_change():
            if print_option.get() == "category":
                category_combo.configure(state="readonly")
            else:
                category_combo.configure(state="disabled")
        
        # Bind option change
        for widget in main_frame.winfo_children():
            if isinstance(widget, ttk.Radiobutton):
                widget.configure(command=on_option_change)
        
        def print_labels():
            try:
                option = print_option.get()
                
                if option == "all":
                    print_product_labels()
                elif option == "category":
                    if not category_var.get():
                        messagebox.showerror("Error", "Please select a category")
                        return
                    # Get products by category and print labels
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT product_id FROM shop_products WHERE category = ? AND is_active = 1", 
                                  [category_var.get()])
                    product_ids = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    print_product_labels(product_ids)
                elif option == "low_stock":
                    # Get low stock product IDs
                    low_stock_items = self.get_low_stock_items()
                    product_ids = [item['product_id'] for item in low_stock_items]
                    print_product_labels(product_ids)
                
                labels_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to print labels: {e}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, pady=20)
        
        ttk.Button(button_frame, text="Print Labels", command=print_labels, 
                  style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=labels_window.destroy).grid(row=0, column=1, padx=5)

    def show_bulk_operations(self):
        """Show bulk operations dialog"""
        # Create bulk operations window
        bulk_window = tk.Toplevel(self.root)
        bulk_window.title("Bulk Operations")
        bulk_window.geometry("350x250")
        bulk_window.resizable(False, False)
        
        # Make it modal
        bulk_window.transient(self.root)
        bulk_window.grab_set()
        
        main_frame = ttk.Frame(bulk_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        ttk.Label(main_frame, text="Bulk Operations", style='Title.TLabel').grid(row=0, column=0, pady=(0, 20))
        
        # Operation buttons
        ttk.Button(main_frame, text="Bulk Price Update", 
                  command=lambda: [bulk_window.destroy(), self.bulk_price_update()], 
                  width=25).grid(row=1, column=0, pady=5)
        
        ttk.Button(main_frame, text="Bulk Restock", 
                  command=lambda: [bulk_window.destroy(), self.bulk_restock()], 
                  width=25).grid(row=2, column=0, pady=5)
        
        ttk.Button(main_frame, text="Import Products", 
                  command=lambda: [bulk_window.destroy(), self.import_products()], 
                  width=25).grid(row=3, column=0, pady=5)
        
        ttk.Button(main_frame, text="Export Products", 
                  command=lambda: [bulk_window.destroy(), self.export_products()], 
                  width=25).grid(row=4, column=0, pady=5)
        
        ttk.Button(main_frame, text="Cancel", 
                  command=bulk_window.destroy, width=25).grid(row=5, column=0, pady=15)
        
    def clear_content(self):
        """Clear the main content area"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
    def show_dashboard(self):
        """Display dashboard with key metrics"""
        self.clear_content()
        self.update_status("Loading dashboard...")
        
        # Title
        ttk.Label(self.content_frame, text="Dashboard", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))
        
        # Create main dashboard frame
        dash_frame = ttk.Frame(self.content_frame)
        dash_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        dash_frame.columnconfigure(1, weight=1)
        
        # Quick stats cards
        stats_frame = ttk.LabelFrame(dash_frame, text="Quick Stats", padding="10")
        stats_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        try:
            # Get stats from backend if available
            stats = self.get_dashboard_stats()
            
            # Display stats in a grid
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.grid(row=0, column=0, sticky=(tk.W, tk.E))
            stats_grid.columnconfigure((0, 1, 2, 3), weight=1)
            
            # Total Products
            self.create_stat_card(stats_grid, "Total Products", stats.get('total_products', 'N/A'), 0, 0)
            
            # Low Stock Items
            low_stock = stats.get('low_stock', 0)
            self.create_stat_card(stats_grid, "Low Stock Items", low_stock, 0, 1, 
                                'Warning' if low_stock > 0 else 'Success')
            
            # Recent Sales
            self.create_stat_card(stats_grid, "Sales (30 days)", stats.get('recent_sales', 'N/A'), 0, 2)
            
            # Cart Items
            cart_count = len(self.cart_items)
            self.create_stat_card(stats_grid, "Cart Items", cart_count, 0, 3, 
                                'Success' if cart_count > 0 else None)
            
        except Exception as e:
            ttk.Label(stats_frame, text=f"Error loading stats: {e}", style='Error.TLabel').grid(row=0, column=0)
        
        # Recent activity / Quick actions
        actions_frame = ttk.LabelFrame(dash_frame, text="Quick Actions", padding="10")
        actions_frame.grid(row=1, column=0, sticky=(tk.W, tk.N), padx=(0, 10))
        
        ttk.Button(actions_frame, text="Browse Products", command=self.show_browse_products, 
                  style='Primary.TButton', width=20).grid(row=0, column=0, pady=5)
        ttk.Button(actions_frame, text="View Cart", command=self.show_shopping_cart, width=20).grid(row=1, column=0, pady=5)
        ttk.Button(actions_frame, text="Order History", command=self.show_order_history, width=20).grid(row=2, column=0, pady=5)
        
        # Admin quick actions
        if self.current_user.get('role') in ['admin', 'staff', 'shop_manager']:
            ttk.Separator(actions_frame, orient='horizontal').grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
            ttk.Button(actions_frame, text="Add Product", command=self.show_add_product_dialog, 
                      style='Success.TButton', width=20).grid(row=4, column=0, pady=5)
            ttk.Button(actions_frame, text="View Reports", command=self.show_reports, width=20).grid(row=5, column=0, pady=5)
        
        # News/Alerts
        alerts_frame = ttk.LabelFrame(dash_frame, text="Alerts & News", padding="10")
        alerts_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        alerts_frame.columnconfigure(0, weight=1)
        alerts_frame.rowconfigure(0, weight=1)
        
        # Scrollable text widget for alerts
        alerts_text = tk.Text(alerts_frame, height=10, wrap=tk.WORD, state='disabled')
        alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient='vertical', command=alerts_text.yview)
        alerts_text.configure(yscrollcommand=alerts_scrollbar.set)
        
        alerts_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        alerts_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Add sample alerts
        alerts_text.configure(state='normal')
        alerts_text.insert(tk.END, "📢 Welcome to the University Shop!\n\n")
        
        if stats.get('low_stock', 0) > 0:
            alerts_text.insert(tk.END, f"⚠️ {stats['low_stock']} products are running low on stock.\n\n")
        
        alerts_text.insert(tk.END, "🎉 Check out our latest products in the browse section!\n\n")
        alerts_text.insert(tk.END, "💡 Tip: Use the search function to quickly find products.\n\n")
        alerts_text.configure(state='disabled')
        
        self.update_status("Dashboard loaded")
        
    def create_stat_card(self, parent, title, value, row, col, style=None):
        """Create a statistics card widget"""
        card_frame = ttk.Frame(parent, relief='ridge', borderwidth=1, padding="10")
        card_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(card_frame, text=title, font=('Arial', 10)).grid(row=0, column=0)
        
        value_style = f'{style}.TLabel' if style else 'TLabel'
        ttk.Label(card_frame, text=str(value), font=('Arial', 14, 'bold'), 
                 style=value_style).grid(row=1, column=0)
        
    def show_club_merchandise_selection(self):
        """Display page to select which club to buy merchandise for"""
        self.clear_content()
        self.update_status("Loading club merchandise selection...")

        # Title
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 20))

        ttk.Label(title_frame, text="Club Merchandise", style='Title.TLabel').pack(side='left')
        ttk.Label(title_frame, text="Select a club to browse merchandise",
                 font=('Arial', 10), foreground='gray').pack(side='left', padx=20)

        # Main content frame
        main_frame = ttk.Frame(self.content_frame)
        main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        main_frame.columnconfigure(0, weight=1)

        # Instructions
        instructions_frame = ttk.LabelFrame(main_frame, text="Instructions", padding="15")
        instructions_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))

        ttk.Label(instructions_frame, text="Select a student club below to view and purchase their official merchandise.",
                 wraplength=600).pack()

        # Club selection frame
        clubs_frame = ttk.LabelFrame(main_frame, text="Available Clubs", padding="15")
        clubs_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        clubs_frame.columnconfigure(0, weight=1)
        clubs_frame.rowconfigure(1, weight=1)

        # Search frame
        search_frame = ttk.Frame(clubs_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side='left', padx=5)

        # Clubs list
        list_frame = ttk.Frame(clubs_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create treeview for clubs
        columns = ('club_id', 'club_name', 'category', 'members')
        clubs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        clubs_tree.heading('club_id', text='ID')
        clubs_tree.heading('club_name', text='Club Name')
        clubs_tree.heading('category', text='Category')
        clubs_tree.heading('members', text='Members')

        clubs_tree.column('club_id', width=60)
        clubs_tree.column('club_name', width=250)
        clubs_tree.column('category', width=150)
        clubs_tree.column('members', width=100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=clubs_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=clubs_tree.xview)
        clubs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        clubs_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Load clubs from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT club_id, club_name, category, member_count
                FROM student_clubs
                WHERE status = 'active'
                ORDER BY club_name
            ''')
            clubs = cursor.fetchall()

            for club in clubs:
                clubs_tree.insert('', tk.END, values=club)

            conn.close()

            # Update instructions with club count
            ttk.Label(instructions_frame,
                     text=f"({len(clubs)} active clubs available)",
                     font=('Arial', 9), foreground='gray').pack()

        except Exception as e:
            ttk.Label(list_frame, text=f"Error loading clubs: {e}",
                     foreground='red').grid(row=0, column=0, pady=20)

        # Action buttons
        button_frame = ttk.Frame(clubs_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(15, 0))

        def view_club_merchandise():
            selection = clubs_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a club to view merchandise.")
                return

            item = clubs_tree.item(selection[0])
            club_id = item['values'][0]
            club_name = item['values'][1]

            # Filter products by club category or tag
            self.show_browse_products()  # Show regular browse with filter option
            self.update_status(f"Showing merchandise for: {club_name}")
            messagebox.showinfo("Club Merchandise",
                               f"Browsing merchandise for {club_name}\n\n"
                               f"Tip: Products tagged with '{club_name}' will appear in the list.")

        ttk.Button(button_frame, text="View Merchandise", command=view_club_merchandise,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='left', padx=5)

        # Search functionality
        def search_clubs(*args):
            search_term = search_var.get().lower()
            clubs_tree.delete(*clubs_tree.get_children())

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT club_id, club_name, category, member_count
                    FROM student_clubs
                    WHERE status = 'active'
                    AND (LOWER(club_name) LIKE ? OR LOWER(category) LIKE ?)
                    ORDER BY club_name
                ''', (f'%{search_term}%', f'%{search_term}%'))
                clubs = cursor.fetchall()

                for club in clubs:
                    clubs_tree.insert('', tk.END, values=club)

                conn.close()
            except Exception as e:
                print(f"Error searching clubs: {e}")

        search_var.trace('w', search_clubs)

        # Double-click to view merchandise
        clubs_tree.bind('<Double-1>', lambda e: view_club_merchandise())

        self.update_status("Club merchandise selection loaded")

    def get_dashboard_stats(self):
        """Get dashboard statistics from backend"""
        try:
            # Use original functions if available
            stats = {}
            
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                # Total products
                cursor.execute("SELECT COUNT(*) FROM shop_products WHERE is_active = 1")
                stats['total_products'] = cursor.fetchone()[0]
                
                # Low stock items
                cursor.execute("""
                    SELECT COUNT(*) FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold
                """)
                stats['low_stock'] = cursor.fetchone()[0]
                
                # Recent sales (30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM shop_transactions
                    WHERE transaction_date >= date('now', '-30 days')
                """)
                stats['recent_sales'] = cursor.fetchone()[0]
                
                conn.close()
            else:
                # Fallback stats
                stats = {
                    'total_products': 10,
                    'low_stock': 2,
                    'recent_sales': 15
                }
                
            return stats
            
        except Exception as e:
            return {'error': str(e)}
            
    def show_browse_products(self):
        """Display product browsing interface"""
        self.clear_content()
        self.update_status("Loading products...")
        
        # Title and search
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(title_frame, text="Browse Products", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        # Search and filter frame
        search_frame = ttk.Frame(title_frame)
        search_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(search_frame, text="🔍 Search", command=self.search_products).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="🔄 Refresh", command=self.refresh_products).grid(row=0, column=3, padx=5)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(self.content_frame, text="Filters", padding="10")
        filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, padx=(0, 5))
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, 
                                          values=["All"], state="readonly", width=15)
        self.category_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(filter_frame, text="Price Range:").grid(row=0, column=2, padx=(10, 5))
        self.min_price_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.min_price_var, width=10).grid(row=0, column=3, padx=2)
        ttk.Label(filter_frame, text="to").grid(row=0, column=4, padx=2)
        self.max_price_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.max_price_var, width=10).grid(row=0, column=5, padx=2)
        
        ttk.Button(filter_frame, text="Apply Filters", command=self.apply_filters).grid(row=0, column=6, padx=10)
        
        # Products display area
        products_frame = ttk.LabelFrame(self.content_frame, text="Products", padding="10")
        products_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        products_frame.columnconfigure(0, weight=1)
        products_frame.rowconfigure(0, weight=1)
        
        # Create treeview for products
        columns = ('ID', 'Name', 'Category', 'Price', 'Stock', 'Description')
        self.products_tree = ttk.Treeview(products_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.products_tree.heading('ID', text='Product ID')
        self.products_tree.heading('Name', text='Name')
        self.products_tree.heading('Category', text='Category')
        self.products_tree.heading('Price', text='Price (£)')
        self.products_tree.heading('Stock', text='Stock')
        self.products_tree.heading('Description', text='Description')
        
        # Configure column widths
        self.products_tree.column('ID', width=80)
        self.products_tree.column('Name', width=200)
        self.products_tree.column('Category', width=120)
        self.products_tree.column('Price', width=80)
        self.products_tree.column('Stock', width=60)
        self.products_tree.column('Description', width=300)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(products_frame, orient='vertical', command=self.products_tree.yview)
        h_scrollbar = ttk.Scrollbar(products_frame, orient='horizontal', command=self.products_tree.xview)
        self.products_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Double-click to view details
        self.products_tree.bind('<Double-1>', self.on_product_double_click)
        
        # Context menu
        self.create_product_context_menu()
        
        # Action buttons
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="Add to Cart", command=self.add_selected_to_cart, 
                  style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="View Details", command=self.view_product_details).grid(row=0, column=1, padx=5)
        
        # Load initial data
        self.load_products()
        self.update_status("Products loaded")
        
    def create_product_context_menu(self):
        """Create context menu for product tree"""
        self.product_context_menu = tk.Menu(self.root, tearoff=0)
        self.product_context_menu.add_command(label="Add to Cart", command=self.add_selected_to_cart)
        self.product_context_menu.add_command(label="View Details", command=self.view_product_details)
        
        if self.current_user.get('role') in ['admin', 'staff', 'shop_manager']:
            self.product_context_menu.add_separator()
            self.product_context_menu.add_command(label="Edit Product", command=self.edit_selected_product)
            self.product_context_menu.add_command(label="Update Stock", command=self.update_selected_stock)
        
        # Bind right-click
        self.products_tree.bind('<Button-3>', self.show_product_context_menu)
        
    def show_product_context_menu(self, event):
        """Show context menu for products"""
        item = self.products_tree.identify_row(event.y)
        if item:
            self.products_tree.selection_set(item)
            self.product_context_menu.post(event.x_root, event.y_root)
            
    def load_products(self):
        """Load products into the treeview"""
        try:
            # Clear existing items
            for item in self.products_tree.get_children():
                self.products_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.is_active = 1
                    ORDER BY p.category, p.name
                """)
                
                products = cursor.fetchall()
                categories = set()
                
                for product in products:
                    # Format price
                    price_str = f"£{product['price']:.2f}"
                    
                    # Insert into tree
                    self.products_tree.insert('', 'end', values=(
                        product['product_id'],
                        product['name'],
                        product['category'],
                        price_str,
                        product['quantity'],
                        product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                    ))
                    
                    categories.add(product['category'])
                
                # Update category filter
                category_list = ["All"] + sorted(list(categories))
                self.category_combo.configure(values=category_list)
                
                conn.close()
                
            else:
                # Fallback sample data
                sample_products = [
                    ("P001", "University Hoodie", "Clothing", "£29.99", "50", "Comfortable hoodie with logo"),
                    ("P002", "University T-Shirt", "Clothing", "£19.99", "75", "Cotton t-shirt with logo"),
                    ("P003", "Notebook Pack", "Stationery", "£12.99", "30", "Set of 3 branded notebooks"),
                ]
                
                for product in sample_products:
                    self.products_tree.insert('', 'end', values=product)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load products: {e}")
            
    def search_products(self):
        """Search products based on search term"""
        search_term = self.search_var.get().strip()
        if not search_term:
            self.load_products()
            return
            
        try:
            # Clear existing items
            for item in self.products_tree.get_children():
                self.products_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.is_active = 1 
                    AND (p.name LIKE ? OR p.description LIKE ? OR p.product_id LIKE ?)
                    ORDER BY p.category, p.name
                """, [f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'])
                
                products = cursor.fetchall()
                
                for product in products:
                    price_str = f"£{product['price']:.2f}"
                    self.products_tree.insert('', 'end', values=(
                        product['product_id'],
                        product['name'],
                        product['category'],
                        price_str,
                        product['quantity'],
                        product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                    ))
                
                conn.close()
                
            self.update_status(f"Found {len(self.products_tree.get_children())} products matching '{search_term}'")
            
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

    def show_manage_discounts(self):
        """Show discount management interface"""
        # Clear content area
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Title
        title_label = ttk.Label(self.content_frame, text="Manage Discounts", style='Heading.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 20))

        # Button frame
        button_frame = ttk.Frame(self.content_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(button_frame, text="Add New Discount", command=self.create_new_discount).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_selected_discount).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Toggle Status", command=self.toggle_discount_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_discounts).pack(side=tk.LEFT, padx=5)

        # Discounts frame
        discounts_frame = ttk.LabelFrame(self.content_frame, text="Current Discounts", padding="10")
        discounts_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Create Treeview for discounts
        tree_frame = ttk.Frame(discounts_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.discounts_tree = ttk.Treeview(tree_frame,
                                         columns=('Type', 'Value', 'Status', 'Start Date', 'End Date', 'Description'),
                                         show='tree headings')
        self.discounts_tree.heading('#0', text='Discount ID')
        self.discounts_tree.heading('Type', text='Type')
        self.discounts_tree.heading('Value', text='Value')
        self.discounts_tree.heading('Status', text='Status')
        self.discounts_tree.heading('Start Date', text='Start Date')
        self.discounts_tree.heading('End Date', text='End Date')
        self.discounts_tree.heading('Description', text='Description')

        self.discounts_tree.column('#0', width=100)
        self.discounts_tree.column('Type', width=80)
        self.discounts_tree.column('Value', width=80)
        self.discounts_tree.column('Status', width=80)
        self.discounts_tree.column('Start Date', width=100)
        self.discounts_tree.column('End Date', width=100)
        self.discounts_tree.column('Description', width=200)

        scrollbar_v = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.discounts_tree.yview)
        scrollbar_h = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.discounts_tree.xview)
        self.discounts_tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)

        self.discounts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind double-click to edit
        self.discounts_tree.bind('<Double-1>', lambda e: self.edit_selected_discount())

        # Configure grid weights
        self.content_frame.grid_rowconfigure(2, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Load discounts
        self.load_discounts()

    def load_discounts(self):
        """Load and display all discounts"""
        # Clear existing items
        for item in self.discounts_tree.get_children():
            self.discounts_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM shop_discounts
                ORDER BY is_active DESC, end_date, start_date
            ''')

            discounts = cursor.fetchall()

            for discount in discounts:
                status = "Active" if discount['is_active'] else "Inactive"
                discount_type = "Percentage" if discount['discount_type'] == 'percentage' else "Fixed Amount"
                value_display = f"{discount['discount_value']}%" if discount['discount_type'] == 'percentage' else f"£{discount['discount_value']}"

                self.discounts_tree.insert('', 'end',
                                         text=discount['discount_id'],
                                         values=(discount_type,
                                               value_display,
                                               status,
                                               discount['start_date'] or 'N/A',
                                               discount['end_date'] or 'N/A',
                                               discount['description'] or ''))
            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load discounts: {str(e)}")

    def create_new_discount(self):
        """Open dialog to create a new discount"""
        dialog = DiscountEditDialog(self.root, None)
        if dialog.result:
            self.load_discounts()

    def edit_selected_discount(self):
        """Edit the selected discount"""
        selection = self.discounts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a discount to edit.")
            return

        discount_id = self.discounts_tree.item(selection[0])['text']
        dialog = DiscountEditDialog(self.root, discount_id)
        if dialog.result:
            self.load_discounts()

    def toggle_discount_status(self):
        """Toggle the status of the selected discount"""
        selection = self.discounts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a discount to toggle status.")
            return

        discount_id = self.discounts_tree.item(selection[0])['text']
        current_status = self.discounts_tree.item(selection[0])['values'][2]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            new_status = 0 if current_status == "Active" else 1
            cursor.execute('''
                UPDATE shop_discounts
                SET is_active = ?
                WHERE discount_id = ?
            ''', (new_status, discount_id))

            conn.commit()
            conn.close()

            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"Discount {discount_id} has been {status_text}.")
            self.load_discounts()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update discount status: {str(e)}")

    def show_monthly_report(self):
        """Show monthly sales report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        # Report title and month selection
        title_frame = ttk.Frame(self.report_display_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(title_frame, text="Monthly Sales Report", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        # Month/Year selection
        today = datetime.now()
        month_frame = ttk.Frame(title_frame)
        month_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Label(month_frame, text="Year:").grid(row=0, column=0, padx=(0, 5))
        year_var = tk.StringVar(value=str(today.year))
        year_combo = ttk.Combobox(month_frame, textvariable=year_var, width=6,
                                 values=[str(y) for y in range(2020, today.year + 2)])
        year_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(month_frame, text="Month:").grid(row=0, column=2, padx=(10, 5))
        month_var = tk.StringVar(value=str(today.month))
        month_combo = ttk.Combobox(month_frame, textvariable=month_var, width=6,
                                  values=[str(m) for m in range(1, 13)])
        month_combo.grid(row=0, column=3, padx=5)
        
        def generate_monthly_report():
            try:
                year = int(year_var.get())
                month = int(month_var.get())
                
                # Generate monthly stats using existing backend function
                stats = self.get_monthly_stats(year, month)
                
                # Clear previous results
                for widget in self.report_display_frame.winfo_children()[1:]:
                    widget.destroy()
                
                # Display monthly stats
                stats_frame = ttk.Frame(self.report_display_frame)
                stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
                stats_frame.columnconfigure((0, 1, 2, 3), weight=1)
                
                month_name = datetime(year, month, 1).strftime('%B %Y')
                ttk.Label(stats_frame, text=f"Report for {month_name}", 
                         style='Heading.TLabel').grid(row=0, column=0, columnspan=4, pady=(0, 10))
                
                self.create_stat_card(stats_frame, "Total Sales", f"£{stats.get('total_sales', 0):.2f}", 1, 0)
                self.create_stat_card(stats_frame, "Transactions", stats.get('transaction_count', 0), 1, 1)
                self.create_stat_card(stats_frame, "Avg Order", f"£{stats.get('avg_order', 0):.2f}", 1, 2)
                self.create_stat_card(stats_frame, "Items Sold", stats.get('items_sold', 0), 1, 3)
                
                # Weekly breakdown
                if stats.get('weekly_breakdown'):
                    weekly_frame = ttk.LabelFrame(self.report_display_frame, text="Weekly Breakdown", padding="10")
                    weekly_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
                    
                    for i, week_data in enumerate(stats['weekly_breakdown']):
                        week_label = f"Week {i+1}"
                        ttk.Label(weekly_frame, text=f"{week_label}: £{week_data['amount']:.2f} ({week_data['count']} orders)").grid(
                            row=i, column=0, sticky=tk.W, pady=2)
                
            except ValueError:
                messagebox.showerror("Error", "Please enter valid year and month")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate monthly report: {e}")
        
        ttk.Button(month_frame, text="Generate", command=generate_monthly_report).grid(row=0, column=4, padx=10)

    def show_weekly_report(self):
        """Show weekly sales report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        # Report title
        ttk.Label(self.report_display_frame, text="Weekly Sales Report", 
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        try:
            # Get weekly stats
            stats = self.get_weekly_stats()
            
            # Stats display
            stats_frame = ttk.Frame(self.report_display_frame)
            stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
            stats_frame.columnconfigure((0, 1, 2, 3), weight=1)
            
            self.create_stat_card(stats_frame, "Total Sales", f"£{stats.get('total_sales', 0):.2f}", 0, 0)
            self.create_stat_card(stats_frame, "Transactions", stats.get('transaction_count', 0), 0, 1)
            self.create_stat_card(stats_frame, "Avg Order", f"£{stats.get('avg_order', 0):.2f}", 0, 2)
            self.create_stat_card(stats_frame, "Items Sold", stats.get('items_sold', 0), 0, 3)
            
            # Daily breakdown
            if stats.get('daily_breakdown'):
                daily_frame = ttk.LabelFrame(self.report_display_frame, text="Daily Breakdown", padding="10")
                daily_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
                
                for day, data in stats['daily_breakdown'].items():
                    day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A, %b %d')
                    ttk.Label(daily_frame, text=f"{day_name}: £{data['amount']:.2f} ({data['count']} orders)").grid(
                        row=len(daily_frame.winfo_children()), column=0, sticky=tk.W, pady=2)
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading weekly report: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_monthly_stats(self, year, month):
        """Get monthly sales statistics"""
        try:
            if 'get_connection' not in globals():
                return {'total_sales': 0, 'transaction_count': 0, 'avg_order': 0, 'items_sold': 0}
            
            # Calculate month boundaries
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            start_str = first_day.strftime('%Y-%m-%d 00:00:00')
            end_str = last_day.strftime('%Y-%m-%d 23:59:59')
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Basic stats
            cursor.execute("""
                SELECT COUNT(*) as transaction_count, 
                       SUM(total_amount) as total_sales,
                       AVG(total_amount) as avg_order
                FROM shop_transactions
                WHERE transaction_date BETWEEN ? AND ?
            """, [start_str, end_str])
            
            basic_stats = cursor.fetchone()
            
            # Items sold
            cursor.execute("""
                SELECT SUM(ti.quantity) as items_sold
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
            """, [start_str, end_str])
            
            items_result = cursor.fetchone()
            
            # Weekly breakdown
            weekly_breakdown = []
            current_week = first_day
            week_num = 1
            
            while current_week <= last_day:
                week_end = min(current_week + timedelta(days=6), last_day)
                
                cursor.execute("""
                    SELECT COUNT(*) as count, SUM(total_amount) as amount
                    FROM shop_transactions
                    WHERE transaction_date BETWEEN ? AND ?
                """, [current_week.strftime('%Y-%m-%d 00:00:00'), 
                      week_end.strftime('%Y-%m-%d 23:59:59')])
                
                week_data = cursor.fetchone()
                weekly_breakdown.append({
                    'week': week_num,
                    'count': week_data['count'] or 0,
                    'amount': week_data['amount'] or 0
                })
                
                current_week = week_end + timedelta(days=1)
                week_num += 1
            
            conn.close()
            
            return {
                'total_sales': basic_stats['total_sales'] or 0,
                'transaction_count': basic_stats['transaction_count'] or 0,
                'avg_order': basic_stats['avg_order'] or 0,
                'items_sold': items_result['items_sold'] or 0,
                'weekly_breakdown': weekly_breakdown
            }
            
        except Exception as e:
            return {'error': str(e)}

    def get_weekly_stats(self):
        """Get current week's sales statistics"""
        try:
            if 'get_connection' not in globals():
                return {'total_sales': 0, 'transaction_count': 0, 'avg_order': 0, 'items_sold': 0}
            
            # Calculate week boundaries (Monday to Sunday)
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            start_str = start_of_week.strftime('%Y-%m-%d 00:00:00')
            end_str = end_of_week.strftime('%Y-%m-%d 23:59:59')
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Basic stats
            cursor.execute("""
                SELECT COUNT(*) as transaction_count, 
                       SUM(total_amount) as total_sales,
                       AVG(total_amount) as avg_order
                FROM shop_transactions
                WHERE transaction_date BETWEEN ? AND ?
            """, [start_str, end_str])
            
            basic_stats = cursor.fetchone()
            
            # Items sold
            cursor.execute("""
                SELECT SUM(ti.quantity) as items_sold
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
            """, [start_str, end_str])
            
            items_result = cursor.fetchone()
            
            # Daily breakdown
            daily_breakdown = {}
            current_day = start_of_week
            
            while current_day <= end_of_week:
                day_str = current_day.strftime('%Y-%m-%d')
                
                cursor.execute("""
                    SELECT COUNT(*) as count, SUM(total_amount) as amount
                    FROM shop_transactions
                    WHERE DATE(transaction_date) = ?
                """, [day_str])
                
                day_data = cursor.fetchone()
                daily_breakdown[day_str] = {
                    'count': day_data['count'] or 0,
                    'amount': day_data['amount'] or 0
                }
                
                current_day += timedelta(days=1)
            
            conn.close()
            
            return {
                'total_sales': basic_stats['total_sales'] or 0,
                'transaction_count': basic_stats['transaction_count'] or 0,
                'avg_order': basic_stats['avg_order'] or 0,
                'items_sold': items_result['items_sold'] or 0,
                'daily_breakdown': daily_breakdown
            }
            
        except Exception as e:
            return {'error': str(e)}

    def show_top_products_report(self):
        """Show top products report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        # Report title
        ttk.Label(self.report_display_frame, text="Top Products Report", 
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        try:
            # Get top products
            top_products = self.get_top_products_data()
            
            if not top_products:
                ttk.Label(self.report_display_frame, text="No product sales data available", 
                         style='Warning.TLabel').grid(row=1, column=0, pady=20)
                return
            
            # Top products table
            products_frame = ttk.Frame(self.report_display_frame)
            products_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            products_frame.columnconfigure(0, weight=1)
            products_frame.rowconfigure(0, weight=1)
            
            # Create treeview
            columns = ('Rank', 'Product ID', 'Name', 'Category', 'Quantity Sold', 'Revenue', 'Avg Price')
            products_tree = ttk.Treeview(products_frame, columns=columns, show='headings', height=15)
            
            for col in columns:
                products_tree.heading(col, text=col)
            
            products_tree.column('Rank', width=50)
            products_tree.column('Product ID', width=100)
            products_tree.column('Name', width=200)
            products_tree.column('Category', width=120)
            products_tree.column('Quantity Sold', width=100)
            products_tree.column('Revenue', width=100)
            products_tree.column('Avg Price', width=100)
            
            # Scrollbar
            products_scrollbar = ttk.Scrollbar(products_frame, orient='vertical', command=products_tree.yview)
            products_tree.configure(yscrollcommand=products_scrollbar.set)
            
            products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            products_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Populate data
            for i, product in enumerate(top_products, 1):
                avg_price = product['total_revenue'] / product['total_quantity'] if product['total_quantity'] > 0 else 0
                products_tree.insert('', 'end', values=(
                    i,
                    product['product_id'],
                    product['name'],
                    product['category'],
                    product['total_quantity'],
                    f"£{product['total_revenue']:.2f}",
                    f"£{avg_price:.2f}"
                ))
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading top products: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_top_products_data(self, limit=20, days=30):
        """Get top products data"""
        try:
            if 'get_connection' not in globals():
                return []
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.product_id, p.name, p.category,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date >= ?
                GROUP BY p.product_id
                ORDER BY total_revenue DESC
                LIMIT ?
            """, [start_date.strftime('%Y-%m-%d %H:%M:%S'), limit])
            
            products = cursor.fetchall()
            conn.close()
            
            return [dict(product) for product in products]
            
        except Exception as e:
            return []

    def bulk_restock(self):
        """Bulk restock low stock items"""
        try:
            # Get low stock items
            low_stock_items = self.get_low_stock_items()
            
            if not low_stock_items:
                messagebox.showinfo("Info", "No items need restocking at this time.")
                return
            
            # Create bulk restock window
            restock_window = tk.Toplevel(self.root)
            restock_window.title("Bulk Restock")
            restock_window.geometry("600x500")
            restock_window.resizable(True, True)
            
            # Make it modal
            restock_window.transient(self.root)
            restock_window.grab_set()
            
            main_frame = ttk.Frame(restock_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(1, weight=1)
            
            # Title
            ttk.Label(main_frame, text="Bulk Restock Low Stock Items", 
                     style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))
            
            # Items list
            items_frame = ttk.LabelFrame(main_frame, text="Items to Restock", padding="10")
            items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            items_frame.columnconfigure(0, weight=1)
            items_frame.rowconfigure(0, weight=1)
            
            # Create treeview
            columns = ('Product ID', 'Name', 'Current Stock', 'Threshold', 'Suggested Restock')
            items_tree = ttk.Treeview(items_frame, columns=columns, show='headings')
            
            for col in columns:
                items_tree.heading(col, text=col)
            
            # Scrollbar
            items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
            items_tree.configure(yscrollcommand=items_scrollbar.set)
            
            items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Populate items with suggested restock amounts
            restock_data = {}
            for item in low_stock_items:
                suggested = max(item['restock_threshold'] * 2 - item['quantity'], item['restock_threshold'])
                items_tree.insert('', 'end', values=(
                    item['product_id'],
                    item['name'],
                    item['quantity'],
                    item['restock_threshold'],
                    suggested
                ))
                restock_data[item['product_id']] = {
                    'current': item['quantity'],
                    'suggested': suggested
                }
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=2, column=0, pady=20)
            
            def execute_restock():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    updated_count = 0
                    
                    for product_id, data in restock_data.items():
                        new_stock = data['current'] + data['suggested']
                        cursor.execute("""
                            UPDATE shop_inventory
                            SET quantity = ?, last_restock_date = ?
                            WHERE product_id = ?
                        """, [new_stock, now, product_id])
                        updated_count += 1
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Success", f"Restocked {updated_count} products successfully!")
                    restock_window.destroy()
                    
                    # Refresh inventory view if it's currently shown
                    if hasattr(self, 'inventory_tree'):
                        self.load_inventory_data()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to restock items: {e}")
            
            ttk.Button(button_frame, text="Execute Restock", command=execute_restock, 
                      style='Success.TButton').grid(row=0, column=0, padx=5)
            ttk.Button(button_frame, text="Cancel", command=restock_window.destroy).grid(row=0, column=1, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to prepare bulk restock: {e}")

    def set_restock_threshold(self):
        """Set restock threshold for selected product"""
        if not hasattr(self, 'inventory_tree'):
            return
            
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product")
            return
        
        item = self.inventory_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        product_name = values[1]
        current_threshold = values[4]
        
        # Ask for new threshold
        new_threshold = simpledialog.askinteger("Set Restock Threshold", 
                                               f"Enter new restock threshold for {product_name}:",
                                               initialvalue=current_threshold, minvalue=0, maxvalue=1000)
        
        if new_threshold is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id = ?
                """, [new_threshold, product_id])
                
                conn.commit()
                conn.close()
                
                # Refresh inventory display
                self.load_inventory_data()
                self.update_status(f"Updated restock threshold for {product_id}: {new_threshold}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update threshold: {e}")

    def restock_selected_item(self):
        """Restock selected inventory item"""
        if not hasattr(self, 'inventory_tree'):
            return
            
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product")
            return
        
        item = self.inventory_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        product_name = values[1]
        current_stock = values[3]
        threshold = values[4]
        
        # Calculate suggested restock amount
        suggested = max(threshold * 2 - current_stock, threshold)
        
        # Ask for restock amount
        restock_amount = simpledialog.askinteger("Restock Item", 
                                               f"Enter amount to add to {product_name} stock:\n"
                                               f"Current stock: {current_stock}\n"
                                               f"Suggested amount: {suggested}",
                                               initialvalue=suggested, minvalue=1, maxvalue=10000)
        
        if restock_amount:
            try:
                new_stock = current_stock + restock_amount
                
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE shop_inventory
                    SET quantity = ?, last_restock_date = ?
                    WHERE product_id = ?
                """, [new_stock, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])
                
                conn.commit()
                conn.close()
                
                # Refresh inventory display
                self.load_inventory_data()
                self.update_status(f"Restocked {product_id}: +{restock_amount} (new total: {new_stock})")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to restock item: {e}")

    def generate_custom_report(self):
        """Generate custom report based on user selection"""
        report_type = self.report_type_var.get()
        start_date = self.report_start_date.get()
        end_date = self.report_end_date.get()
        
        try:
            # Validate dates
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            
            # Clear report display
            for widget in self.report_display_frame.winfo_children():
                widget.destroy()
            
            # Show loading
            ttk.Label(self.report_display_frame, text="Generating custom report...", 
                     style='Heading.TLabel').grid(row=0, column=0, pady=20)
            self.root.update()
            
            if report_type == "sales_summary":
                self.show_sales_summary_report(start_date, end_date)
            elif report_type == "product_performance":
                self.show_product_performance_report(start_date, end_date)
            elif report_type == "category_analysis":
                self.show_category_analysis_report(start_date, end_date)
            elif report_type == "customer_analysis":
                self.show_customer_analysis_report(start_date, end_date)
            elif report_type == "payment_methods":
                self.show_payment_methods_report(start_date, end_date)
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid dates in YYYY-MM-DD format")
        except Exception as e:
            # Clear and show error
            for widget in self.report_display_frame.winfo_children():
                widget.destroy()
            ttk.Label(self.report_display_frame, text=f"Error generating report: {e}", 
                     style='Error.TLabel').grid(row=0, column=0, pady=20)

    def show_sales_summary_report(self, start_date, end_date):
        """Show sales summary report for date range"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get sales data
            sales_data = self.get_sales_summary_data(start_date, end_date)
            
            # Report title
            ttk.Label(self.report_display_frame, text=f"Sales Summary: {start_date} to {end_date}", 
                     style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            
            # Summary stats
            stats_frame = ttk.Frame(self.report_display_frame)
            stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
            stats_frame.columnconfigure((0, 1, 2, 3), weight=1)
            
            self.create_stat_card(stats_frame, "Total Revenue", f"£{sales_data.get('total_revenue', 0):.2f}", 0, 0)
            self.create_stat_card(stats_frame, "Transactions", sales_data.get('transaction_count', 0), 0, 1)
            self.create_stat_card(stats_frame, "Avg Order", f"£{sales_data.get('avg_order_value', 0):.2f}", 0, 2)
            self.create_stat_card(stats_frame, "Items Sold", sales_data.get('total_items', 0), 0, 3)
            
            # Daily trend if available
            if sales_data.get('daily_trend'):
                trend_frame = ttk.LabelFrame(self.report_display_frame, text="Daily Sales Trend", padding="10")
                trend_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
                
                for date, amount in sales_data['daily_trend'].items():
                    ttk.Label(trend_frame, text=f"{date}: £{amount:.2f}").grid(
                        row=len(trend_frame.winfo_children()), column=0, sticky=tk.W, pady=1)
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading sales summary: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_sales_summary_data(self, start_date, end_date):
        """Get sales summary data for the inclusive date range [start_date, end_date]."""
        conn = None
        try:
            # Get a DB connection
            if hasattr(self, "get_connection") and callable(getattr(self, "get_connection")):
                conn = self.get_connection()
            elif "get_connection" in globals() and callable(globals()["get_connection"]):
                conn = globals()["get_connection"]()
            else:
                return {"error": "get_connection() not available"}

            if conn is None:
                return {"error": "get_connection() returned None"}

            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Basic summary
            cursor.execute(
                """
                SELECT 
                    COUNT(*) AS transaction_count,
                    COALESCE(SUM(total_amount), 0) AS total_revenue,
                    COALESCE(AVG(total_amount), 0) AS avg_order_value
                FROM shop_transactions
                WHERE DATE(transaction_date) BETWEEN ? AND ?
                """,
                (start_date, end_date),
            )
            summary_row = cursor.fetchone()
            summary = dict(summary_row) if summary_row else {}

            # Total items sold
            cursor.execute(
                """
                SELECT COALESCE(SUM(ti.quantity), 0) AS total_items
                FROM shop_transaction_items ti
                JOIN shop_transactions t 
                  ON ti.transaction_id = t.transaction_id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                """,
                (start_date, end_date),
            )
            items_row = cursor.fetchone()
            items_result = dict(items_row) if items_row else {}

            # Daily trend
            cursor.execute(
                """
                SELECT 
                    DATE(transaction_date) AS d, 
                    COALESCE(SUM(total_amount), 0) AS daily_total
                FROM shop_transactions
                WHERE DATE(transaction_date) BETWEEN ? AND ?
                GROUP BY DATE(transaction_date)
                ORDER BY d
                """,
                (start_date, end_date),
            )
            daily_trend = {row["d"]: row["daily_total"] for row in cursor.fetchall()}

            return {
                "transaction_count": summary.get("transaction_count", 0),
                "total_revenue": summary.get("total_revenue", 0),
                "avg_order_value": summary.get("avg_order_value", 0),
                "total_items": items_result.get("total_items", 0),
                "daily_trend": daily_trend,
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            if conn:
                conn.close()

    def show_product_performance_report(self, start_date, end_date):
        """Show product performance report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get product performance data
            performance_data = self.get_product_performance_data(start_date, end_date)
            
            # Report title
            ttk.Label(self.report_display_frame, text=f"Product Performance: {start_date} to {end_date}", 
                     style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            
            # Performance table
            performance_frame = ttk.Frame(self.report_display_frame)
            performance_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            performance_frame.columnconfigure(0, weight=1)
            performance_frame.rowconfigure(0, weight=1)
            
            columns = ('Product ID', 'Name', 'Category', 'Units Sold', 'Revenue', 'Avg Price', 'Performance')
            perf_tree = ttk.Treeview(performance_frame, columns=columns, show='headings', height=15)
            
            for col in columns:
                perf_tree.heading(col, text=col)
            
            perf_scrollbar = ttk.Scrollbar(performance_frame, orient='vertical', command=perf_tree.yview)
            perf_tree.configure(yscrollcommand=perf_scrollbar.set)
            
            perf_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            perf_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Populate performance data
            for product in performance_data:
                avg_price = product['revenue'] / product['units_sold'] if product['units_sold'] > 0 else 0
                performance_rating = "High" if product['revenue'] > 100 else "Medium" if product['revenue'] > 50 else "Low"
                
                perf_tree.insert('', 'end', values=(
                    product['product_id'],
                    product['name'],
                    product['category'],
                    product['units_sold'],
                    f"£{product['revenue']:.2f}",
                    f"£{avg_price:.2f}",
                    performance_rating
                ))
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading product performance: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_product_performance_data(self, start_date, end_date):
        """Get product performance data"""
        try:
            if 'get_connection' not in globals():
                return []
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.product_id, p.name, p.category,
                       SUM(ti.quantity) as units_sold,
                       SUM(ti.subtotal) as revenue
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                GROUP BY p.product_id
                ORDER BY revenue DESC
            """, [start_date, end_date])
            
            products = cursor.fetchall()
            conn.close()
            
            return [dict(product) for product in products]
            
        except Exception as e:
            return []

    def show_category_analysis_report(self, start_date, end_date):
        """Show category analysis report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get category data
            category_data = self.get_category_analysis_data(start_date, end_date)
            
            # Report title
            ttk.Label(self.report_display_frame, text=f"Category Analysis: {start_date} to {end_date}", 
                     style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            
            # Category table
            category_frame = ttk.Frame(self.report_display_frame)
            category_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            category_frame.columnconfigure(0, weight=1)
            category_frame.rowconfigure(0, weight=1)
            
            columns = ('Category', 'Products', 'Units Sold', 'Revenue', 'Avg per Product', 'Market Share %')
            cat_tree = ttk.Treeview(category_frame, columns=columns, show='headings', height=10)
            
            for col in columns:
                cat_tree.heading(col, text=col)
            
            cat_scrollbar = ttk.Scrollbar(category_frame, orient='vertical', command=cat_tree.yview)
            cat_tree.configure(yscrollcommand=cat_scrollbar.set)
            
            cat_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            cat_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Calculate total revenue for market share
            total_revenue = sum(cat['revenue'] for cat in category_data)
            
            # Populate category data
            for category in category_data:
                avg_per_product = category['revenue'] / category['product_count'] if category['product_count'] > 0 else 0
                market_share = (category['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
                
                cat_tree.insert('', 'end', values=(
                    category['category'],
                    category['product_count'],
                    category['units_sold'],
                    f"£{category['revenue']:.2f}",
                    f"£{avg_per_product:.2f}",
                    f"{market_share:.1f}%"
                ))
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading category analysis: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_category_analysis_data(self, start_date, end_date):
        """Get category analysis data"""
        try:
            if 'get_connection' not in globals():
                return []
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.category,
                       COUNT(DISTINCT p.product_id) as product_count,
                       SUM(ti.quantity) as units_sold,
                       SUM(ti.subtotal) as revenue
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY revenue DESC
            """, [start_date, end_date])
            
            categories = cursor.fetchall()
            conn.close()
            
            return [dict(category) for category in categories]
            
        except Exception as e:
            return []

    def show_customer_analysis_report(self, start_date, end_date):
        """Show customer analysis report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get customer data
            customer_data = self.get_customer_analysis_data(start_date, end_date)
            
            # Report title
            ttk.Label(self.report_display_frame, text=f"Customer Analysis: {start_date} to {end_date}", 
                     style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            
            # Summary stats
            stats_frame = ttk.Frame(self.report_display_frame)
            stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
            stats_frame.columnconfigure((0, 1, 2), weight=1)
            
            self.create_stat_card(stats_frame, "Total Customers", customer_data.get('total_customers', 0), 0, 0)
            self.create_stat_card(stats_frame, "Avg Orders/Customer", f"{customer_data.get('avg_orders_per_customer', 0):.1f}", 0, 1)
            self.create_stat_card(stats_frame, "Avg Spend/Customer", f"£{customer_data.get('avg_spend_per_customer', 0):.2f}", 0, 2)
            
            # Top customers table
            if customer_data.get('top_customers'):
                customers_frame = ttk.LabelFrame(self.report_display_frame, text="Top Customers", padding="10")
                customers_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
                customers_frame.columnconfigure(0, weight=1)
                customers_frame.rowconfigure(0, weight=1)
                
                columns = ('Username', 'Student ID', 'Orders', 'Total Spent', 'Avg Order')
                cust_tree = ttk.Treeview(customers_frame, columns=columns, show='headings', height=10)
                
                for col in columns:
                    cust_tree.heading(col, text=col)
                
                cust_scrollbar = ttk.Scrollbar(customers_frame, orient='vertical', command=cust_tree.yview)
                cust_tree.configure(yscrollcommand=cust_scrollbar.set)
                
                cust_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
                cust_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
                
                # Populate customer data
                for customer in customer_data['top_customers']:
                    avg_order = customer['total_spent'] / customer['order_count'] if customer['order_count'] > 0 else 0
                    cust_tree.insert('', 'end', values=(
                        customer['username'],
                        customer['student_id'] or 'N/A',
                        customer['order_count'],
                        f"£{customer['total_spent']:.2f}",
                        f"£{avg_order:.2f}"
                    ))
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading customer analysis: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_customer_analysis_data(self, start_date, end_date):
        """Get customer analysis data"""
        try:
            if 'get_connection' not in globals():
                return {}
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Customer summary
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as total_customers,
                       AVG(orders_per_customer) as avg_orders_per_customer,
                       AVG(spend_per_customer) as avg_spend_per_customer
                FROM (
                    SELECT user_id,
                           COUNT(*) as orders_per_customer,
                           SUM(total_amount) as spend_per_customer
                    FROM shop_transactions
                    WHERE DATE(transaction_date) BETWEEN ? AND ?
                    GROUP BY user_id
                )
            """, [start_date, end_date])
            
            summary = cursor.fetchone()
            
            # Top customers
            cursor.execute("""
                SELECT u.username, u.student_id,
                       COUNT(t.transaction_id) as order_count,
                       SUM(t.total_amount) as total_spent
                FROM shop_transactions t
                JOIN users u ON t.user_id = u.id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                GROUP BY u.id
                ORDER BY total_spent DESC
                LIMIT 10
            """, [start_date, end_date])
            
            top_customers = cursor.fetchall()
            conn.close()
            
            return {
                'total_customers': summary['total_customers'] or 0,
                'avg_orders_per_customer': summary['avg_orders_per_customer'] or 0,
                'avg_spend_per_customer': summary['avg_spend_per_customer'] or 0,
                'top_customers': [dict(customer) for customer in top_customers]
            }
            
        except Exception as e:
            return {'error': str(e)}

    def show_payment_methods_report(self, start_date, end_date):
        """Show payment methods analysis report"""
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get payment methods data
            payment_data = self.get_payment_methods_data(start_date, end_date)
            
            # Report title
            ttk.Label(self.report_display_frame, text=f"Payment Methods Analysis: {start_date} to {end_date}", 
                     style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            
            # Payment methods table
            payment_frame = ttk.Frame(self.report_display_frame)
            payment_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
            payment_frame.columnconfigure(0, weight=1)
            payment_frame.rowconfigure(0, weight=1)
            
            columns = ('Payment Method', 'Transactions', 'Total Amount', 'Avg Transaction', 'Usage %', 'Revenue %')
            pay_tree = ttk.Treeview(payment_frame, columns=columns, show='headings', height=8)
            
            for col in columns:
                pay_tree.heading(col, text=col)
            
            pay_scrollbar = ttk.Scrollbar(payment_frame, orient='vertical', command=pay_tree.yview)
            pay_tree.configure(yscrollcommand=pay_scrollbar.set)
            
            pay_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            pay_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Calculate totals for percentages
            total_transactions = sum(method['transaction_count'] for method in payment_data)
            total_amount = sum(method['total_amount'] for method in payment_data)
            
            # Populate payment data
            for method in payment_data:
                avg_transaction = method['total_amount'] / method['transaction_count'] if method['transaction_count'] > 0 else 0
                usage_pct = (method['transaction_count'] / total_transactions * 100) if total_transactions > 0 else 0
                revenue_pct = (method['total_amount'] / total_amount * 100) if total_amount > 0 else 0
                
                pay_tree.insert('', 'end', values=(
                    method['payment_method'],
                    method['transaction_count'],
                    f"£{method['total_amount']:.2f}",
                    f"£{avg_transaction:.2f}",
                    f"{usage_pct:.1f}%",
                    f"{revenue_pct:.1f}%"
                ))
            
        except Exception as e:
            ttk.Label(self.report_display_frame, text=f"Error loading payment methods: {e}", 
                     style='Error.TLabel').grid(row=1, column=0)

    def get_payment_methods_data(self, start_date, end_date):
        """Get payment methods data"""
        try:
            if 'get_connection' not in globals():
                return []
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT payment_method,
                       COUNT(*) as transaction_count,
                       SUM(total_amount) as total_amount
                FROM shop_transactions
                WHERE DATE(transaction_date) BETWEEN ? AND ?
                GROUP BY payment_method
                ORDER BY total_amount DESC
            """, [start_date, end_date])
            
            methods = cursor.fetchall()
            conn.close()
            
            return [dict(method) for method in methods]
            
        except Exception as e:
            return []

    def view_product_sales(self):
        """View sales data for selected product"""
        if not hasattr(self, 'mgmt_products_tree'):
            return
            
        selection = self.mgmt_products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product")
            return
        
        item = self.mgmt_products_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        product_name = values[1]
        
        # Create sales window
        sales_window = tk.Toplevel(self.root)
        sales_window.title(f"Sales Data - {product_name}")
        sales_window.geometry("700x500")
        sales_window.resizable(True, True)
        
        # Make it modal
        sales_window.transient(self.root)
        sales_window.grab_set()
        
        main_frame = ttk.Frame(sales_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        ttk.Label(main_frame, text=f"Sales Data: {product_name} ({product_id})", 
                 style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))
        
        try:
            # Get sales data
            sales_data = self.get_product_sales_data(product_id)
            
            if not sales_data:
                ttk.Label(main_frame, text="No sales data found for this product").grid(row=1, column=0)
            else:
                # Sales table
                sales_frame = ttk.Frame(main_frame)
                sales_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
                sales_frame.columnconfigure(0, weight=1)
                sales_frame.rowconfigure(0, weight=1)
                
                columns = ('Date', 'Transaction ID', 'Quantity', 'Price', 'Subtotal')
                sales_tree = ttk.Treeview(sales_frame, columns=columns, show='headings')
                
                for col in columns:
                    sales_tree.heading(col, text=col)
                
                sales_scrollbar = ttk.Scrollbar(sales_frame, orient='vertical', command=sales_tree.yview)
                sales_tree.configure(yscrollcommand=sales_scrollbar.set)
                
                sales_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
                sales_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
                
                # Populate sales data
                total_quantity = 0
                total_revenue = 0
                
                for sale in sales_data:
                    sales_tree.insert('', 'end', values=(
                        sale['transaction_date'],
                        sale['transaction_id'],
                        sale['quantity'],
                        f"£{sale['price_per_item']:.2f}",
                        f"£{sale['subtotal']:.2f}"
                    ))
                    total_quantity += sale['quantity']
                    total_revenue += sale['subtotal']
                
                # Summary
                summary_frame = ttk.Frame(main_frame)
                summary_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
                
                ttk.Label(summary_frame, text=f"Total Sales: {len(sales_data)} transactions, "
                                             f"{total_quantity} units, £{total_revenue:.2f} revenue",
                         font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
        
        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading sales data: {e}").grid(row=1, column=0)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=sales_window.destroy).grid(row=3, column=0, pady=10)

    def get_product_sales_data(self, product_id):
        """Get sales data for a specific product"""
        try:
            if 'get_connection' not in globals():
                return []
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.transaction_date, t.transaction_id,
                       ti.quantity, ti.price_per_item, ti.subtotal
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE ti.product_id = ?
                ORDER BY t.transaction_date DESC
            """, [product_id])
            
            sales = cursor.fetchall()
            conn.close()
            
            return [dict(sale) for sale in sales]
            
        except Exception as e:
            return []

    def bulk_price_update(self):
        """Bulk update prices for selected products"""
        # Create bulk price update window
        update_window = tk.Toplevel(self.root)
        update_window.title("Bulk Price Update")
        update_window.geometry("400x300")
        update_window.resizable(False, False)
        
        # Make it modal
        update_window.transient(self.root)
        update_window.grab_set()
        
        main_frame = ttk.Frame(update_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        ttk.Label(main_frame, text="Bulk Price Update", style='Title.TLabel').grid(row=0, column=0, pady=(0, 20))
        
        # Update options
        ttk.Label(main_frame, text="Update Method:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        update_method = tk.StringVar(value="percentage")
        ttk.Radiobutton(main_frame, text="Percentage change", variable=update_method, 
                       value="percentage").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(main_frame, text="Fixed amount change", variable=update_method, 
                       value="fixed").grid(row=3, column=0, sticky=tk.W, pady=2)
        
        # Value input
        ttk.Label(main_frame, text="Value:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        value_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=value_var, width=20).grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Label(main_frame, text="(Use negative values for decreases)", 
                 font=('Arial', 8)).grid(row=6, column=0, sticky=tk.W, pady=2)
        
        # Category filter
        ttk.Label(main_frame, text="Apply to Category:", font=('Arial', 10, 'bold')).grid(row=7, column=0, sticky=tk.W, pady=(10, 5))
        
        category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(main_frame, textvariable=category_var, 
                                     values=["All"], state="readonly", width=17)
        category_combo.grid(row=8, column=0, sticky=tk.W, pady=2)
        
        # Load categories
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
                categories = ["All"] + [row[0] for row in cursor.fetchall()]
                category_combo.configure(values=categories)
                conn.close()
        except Exception:
            pass
        
        def execute_update():
            try:
                value = float(value_var.get())
                method = update_method.get()
                category = category_var.get()
                
                if method == "percentage":
                    multiplier = 1 + (value / 100)
                else:
                    multiplier = None
                    fixed_change = value
                
                conn = get_connection()
                cursor = conn.cursor()
                
                # Build query
                if category == "All":
                    if method == "percentage":
                        cursor.execute("""
                            UPDATE shop_products 
                            SET price = price * ?, updated_at = ?
                            WHERE is_active = 1
                        """, [multiplier, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                    else:
                        cursor.execute("""
                            UPDATE shop_products 
                            SET price = MAX(0.01, price + ?), updated_at = ?
                            WHERE is_active = 1
                        """, [fixed_change, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                else:
                    if method == "percentage":
                        cursor.execute("""
                            UPDATE shop_products 
                            SET price = price * ?, updated_at = ?
                            WHERE category = ? AND is_active = 1
                        """, [multiplier, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category])
                    else:
                        cursor.execute("""
                            UPDATE shop_products 
                            SET price = MAX(0.01, price + ?), updated_at = ?
                            WHERE category = ? AND is_active = 1
                        """, [fixed_change, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category])
                
                affected_rows = cursor.rowcount
                conn.commit()
                conn.close()
                
                update_window.destroy()
                self.load_products_for_management()
                
                change_desc = f"{value:+.1f}%" if method == "percentage" else f"£{value:+.2f}"
                scope = category if category != "All" else "all products"
                messagebox.showinfo("Success", f"Updated {affected_rows} products in {scope} by {change_desc}")
                
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid numeric value")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update prices: {e}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, pady=20)
        
        ttk.Button(button_frame, text="Update Prices", command=execute_update, 
                  style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=update_window.destroy).grid(row=0, column=1, padx=5)

    def import_products(self):
        """Import products from CSV file"""
        try:
            # Ask for file
            filename = filedialog.askopenfilename(
                title="Import Products",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # Show progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Importing Products")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_frame = ttk.Frame(progress_window, padding="20")
            progress_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            ttk.Label(progress_frame, text="Importing products...").grid(row=0, column=0, pady=10)
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
            progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
            
            status_label = ttk.Label(progress_frame, text="Reading file...")
            status_label.grid(row=2, column=0, pady=5)
            
            progress_window.update()
            
            # Read CSV file
            import csv
            imported_count = 0
            error_count = 0
            
            with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                total_rows = len(rows)
                
                conn = get_connection()
                cursor = conn.cursor()
                
                for i, row in enumerate(rows):
                    try:
                        # Update progress
                        progress = (i / total_rows) * 100
                        progress_var.set(progress)
                        status_label.config(text=f"Processing row {i+1} of {total_rows}")
                        progress_window.update()
                        
                        # Validate required fields
                        if not all([row.get('name'), row.get('price'), row.get('category')]):
                            error_count += 1
                            continue
                        
                        # Generate product ID
                        cursor.execute("SELECT MAX(SUBSTR(product_id, 2)) FROM shop_products WHERE product_id LIKE 'P%'")
                        result = cursor.fetchone()
                        
                        try:
                            if result[0]:
                                next_id = int(result[0]) + 1
                            else:
                                next_id = 1
                            product_id = f"P{next_id:03d}"
                        except (ValueError, TypeError):
                            product_id = f"P{int(time.time())}{i}"
                        
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Insert product
                        cursor.execute("""
                            INSERT INTO shop_products
                            (product_id, name, description, price, category, created_at, updated_at, tax_rate, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            product_id,
                            row['name'],
                            row.get('description', ''),
                            float(row['price']),
                            row['category'],
                            now, now,
                            float(row.get('tax_rate', 0.2)),
                            1
                        ])
                        
                        # Insert inventory
                        initial_stock = int(row.get('stock', 10))
                        threshold = int(row.get('threshold', 5))
                        
                        cursor.execute("""
                            INSERT INTO shop_inventory
                            (product_id, quantity, last_restock_date, restock_threshold)
                            VALUES (?, ?, ?, ?)
                        """, [product_id, initial_stock, now, threshold])
                        
                        imported_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        continue
                
                conn.commit()
                conn.close()
            
            progress_window.destroy()
            
            # Show results
            message = f"Import completed!\n\nImported: {imported_count} products\nErrors: {error_count} rows"
            messagebox.showinfo("Import Results", message)
            
            # Refresh products view
            self.load_products_for_management()
            
        except Exception as e:
            if 'progress_window' in locals():
                progress_window.destroy()
            messagebox.showerror("Import Error", f"Failed to import products: {e}")

    def export_products(self):
        """Export products to CSV file"""
        try:
            # Ask for file location
            filename = filedialog.asksaveasfilename(
                title="Export Products",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # Get products data
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.*, i.quantity, i.restock_threshold
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                ORDER BY p.category, p.name
            """)
            
            products = cursor.fetchall()
            conn.close()
            
            # Write to CSV
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['product_id', 'name', 'description', 'price', 'category', 
                             'tax_rate', 'stock', 'threshold', 'is_active', 'created_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in products:
                    writer.writerow({
                        'product_id': product['product_id'],
                        'name': product['name'],
                        'description': product['description'],
                        'price': product['price'],
                        'category': product['category'],
                        'tax_rate': product['tax_rate'],
                        'stock': product['quantity'],
                        'threshold': product['restock_threshold'],
                        'is_active': product['is_active'],
                        'created_at': product['created_at']
                    })
            
            messagebox.showinfo("Export Complete", f"Exported {len(products)} products to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export products: {e}")
            
    def apply_filters(self):
        """Apply category and price filters"""
        category = self.category_var.get()
        min_price = self.min_price_var.get().strip()
        max_price = self.max_price_var.get().strip()
        
        try:
            # Clear existing items
            for item in self.products_tree.get_children():
                self.products_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Build query
                query = """
                    SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.is_active = 1
                """
                params = []
                
                if category != "All":
                    query += " AND p.category = ?"
                    params.append(category)
                
                if min_price:
                    query += " AND p.price >= ?"
                    params.append(float(min_price))
                
                if max_price:
                    query += " AND p.price <= ?"
                    params.append(float(max_price))
                
                query += " ORDER BY p.category, p.name"
                
                cursor.execute(query, params)
                products = cursor.fetchall()
                
                for product in products:
                    price_str = f"£{product['price']:.2f}"
                    self.products_tree.insert('', 'end', values=(
                        product['product_id'],
                        product['name'],
                        product['category'],
                        price_str,
                        product['quantity'],
                        product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                    ))
                
                conn.close()
                
            self.update_status(f"Applied filters - {len(self.products_tree.get_children())} products shown")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid price range")
        except Exception as e:
            messagebox.showerror("Error", f"Filter failed: {e}")
            
    def refresh_products(self):
        """Refresh product list"""
        self.category_var.set("All")
        self.min_price_var.set("")
        self.max_price_var.set("")
        self.search_var.set("")
        self.load_products()
        self.update_status("Products refreshed")
        
    def on_product_double_click(self, event):
        """Handle double-click on product"""
        self.view_product_details()
        
    def view_product_details(self):
        """Show detailed product information"""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product first")
            return
        
        item = self.products_tree.item(selection[0])
        values = item['values']
        
        if not values:
            return
        
        product_id = values[0]
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Product Details - {product_id}")
        details_window.geometry("500x400")
        details_window.resizable(False, False)

        # Make it modal (set transient first)
        details_window.transient(self.root)

        # Create content
        main_frame = ttk.Frame(details_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Product info
        info_frame = ttk.LabelFrame(main_frame, text="Product Information", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        try:
            product_data = self.get_product_details(product_id)
            
            if product_data:
                ttk.Label(info_frame, text="Product ID:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=2)
                ttk.Label(info_frame, text=product_data.get('product_id', 'N/A')).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)
                
                ttk.Label(info_frame, text="Name:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=2)
                ttk.Label(info_frame, text=product_data.get('name', 'N/A')).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)
                
                ttk.Label(info_frame, text="Category:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=2)
                ttk.Label(info_frame, text=product_data.get('category', 'N/A')).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)
                
                ttk.Label(info_frame, text="Price:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=2)
                ttk.Label(info_frame, text=f"£{product_data.get('price', 0):.2f}").grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=2)
                
                ttk.Label(info_frame, text="Stock:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=2)
                stock_color = 'red' if product_data.get('quantity', 0) <= product_data.get('restock_threshold', 5) else 'green'
                stock_label = ttk.Label(info_frame, text=str(product_data.get('quantity', 0)), foreground=stock_color)
                stock_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=2)
                
                ttk.Label(info_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky=(tk.W, tk.N), pady=2)
                
                # Description text widget
                desc_text = tk.Text(info_frame, height=4, width=40, wrap=tk.WORD, state='disabled')
                desc_text.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
                desc_text.configure(state='normal')
                desc_text.insert('1.0', product_data.get('description', 'No description available'))
                desc_text.configure(state='disabled')
            
        except Exception as e:
            ttk.Label(info_frame, text=f"Error loading details: {e}", style='Error.TLabel').grid(row=0, column=0, columnspan=2)
        
        # Add to cart section
        cart_frame = ttk.LabelFrame(main_frame, text="Add to Cart", padding="10")
        cart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(cart_frame, text="Quantity:").grid(row=0, column=0, sticky=tk.W)
        quantity_var = tk.IntVar(value=1)
        quantity_spin = ttk.Spinbox(cart_frame, from_=1, to=100, textvariable=quantity_var, width=10)
        quantity_spin.grid(row=0, column=1, padx=(10, 0))
        
        def add_to_cart_action():
            try:
                self.add_to_cart(product_id, quantity_var.get())
                details_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add to cart: {e}")
        
        ttk.Button(cart_frame, text="Add to Cart", command=add_to_cart_action,
                  style='Primary.TButton').grid(row=0, column=2, padx=10)

        # Close button
        ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)

        # Now that window is fully created, make it modal
        details_window.update_idletasks()  # Ensure window is rendered
        details_window.grab_set()  # Now safe to grab focus
        
    def get_product_details(self, product_id):
        """Get detailed product information"""
        try:
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT p.*, i.quantity, i.restock_threshold
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.product_id = ?
            """, [product_id])

            result = cursor.fetchone()
            conn.close()

            if result:
                return dict(result)

            # If no result found, log and return None
            print(f"Warning: Product {product_id} not found in database")
            return None

        except Exception as e:
            print(f"Error getting product details for {product_id}: {e}")
            raise Exception(f"Database error: {e}")
            
    def add_selected_to_cart(self):
        """Add selected product to cart"""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product first")
            return
        
        item = self.products_tree.item(selection[0])
        values = item['values']
        
        if not values:
            return
        
        product_id = values[0]
        
        # Ask for quantity
        quantity = simpledialog.askinteger("Quantity", "Enter quantity to add to cart:", 
                                         initialvalue=1, minvalue=1, maxvalue=100)
        
        if quantity:
            try:
                self.add_to_cart(product_id, quantity)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add to cart: {e}")
                
    def add_to_cart(self, product_id, quantity):
        """Add product to shopping cart"""
        try:
            # Get product details
            product_details = self.get_product_details(product_id)

            if not product_details:
                raise Exception(f"Product not found (ID: {product_id}). The product may not exist in inventory.")

            # Check stock
            if quantity > product_details['quantity']:
                raise Exception(f"Insufficient stock. Only {product_details['quantity']} available.")

            # Check if already in cart
            for item in self.cart_items:
                if item['product_id'] == product_id:
                    item['quantity'] += quantity
                    item['subtotal'] = item['price'] * item['quantity']
                    break
            else:
                # Add new item to cart
                cart_item = {
                    'product_id': product_id,
                    'name': product_details['name'],
                    'price': product_details['price'],
                    'quantity': quantity,
                    'subtotal': product_details['price'] * quantity
                }
                self.cart_items.append(cart_item)

            # Update status
            self.update_status(f"Added {quantity} x {product_details['name']} to cart")
            messagebox.showinfo("Success", f"Added {quantity} x {product_details['name']} to cart")

        except Exception as e:
            print(f"Error in add_to_cart: {e}")
            raise Exception(f"Failed to add to cart: {e}")
            
    def show_shopping_cart(self):
        """Display shopping cart interface"""
        self.clear_content()
        self.update_status("Loading shopping cart...")
        
        # Title
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(title_frame, text="Shopping Cart", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        # Cart summary
        summary_label = ttk.Label(title_frame, text=f"Items in cart: {len(self.cart_items)}")
        summary_label.grid(row=0, column=1, sticky=tk.E)
        
        if not self.cart_items:
            # Empty cart message
            empty_frame = ttk.Frame(self.content_frame)
            empty_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            ttk.Label(empty_frame, text="Your cart is empty", style='Heading.TLabel').grid(row=0, column=0, pady=20)
            ttk.Label(empty_frame, text="Browse products to add items to your cart").grid(row=1, column=0, pady=10)
            ttk.Button(empty_frame, text="Browse Products", command=self.show_browse_products, 
                      style='Primary.TButton').grid(row=2, column=0, pady=10)
        else:
            # Cart items
            cart_frame = ttk.LabelFrame(self.content_frame, text="Cart Items", padding="10")
            cart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
            cart_frame.columnconfigure(0, weight=1)
            cart_frame.rowconfigure(0, weight=1)
            
            # Create treeview for cart items
            cart_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
            self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns, show='headings', height=10)
            
            # Configure columns
            for col in cart_columns:
                self.cart_tree.heading(col, text=col)
            
            self.cart_tree.column('Product ID', width=100)
            self.cart_tree.column('Name', width=250)
            self.cart_tree.column('Price', width=80)
            self.cart_tree.column('Quantity', width=80)
            self.cart_tree.column('Subtotal', width=100)
            
            # Scrollbar
            cart_scrollbar = ttk.Scrollbar(cart_frame, orient='vertical', command=self.cart_tree.yview)
            self.cart_tree.configure(yscrollcommand=cart_scrollbar.set)
            
            self.cart_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            cart_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Populate cart
            total = 0
            for item in self.cart_items:
                self.cart_tree.insert('', 'end', values=(
                    item['product_id'],
                    item['name'],
                    f"£{item['price']:.2f}",
                    item['quantity'],
                    f"£{item['subtotal']:.2f}"
                ))
                total += item['subtotal']
            
            # Cart actions
            action_frame = ttk.Frame(self.content_frame)
            action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
            
            ttk.Button(action_frame, text="Update Quantity", command=self.update_cart_quantity).grid(row=0, column=0, padx=5)
            ttk.Button(action_frame, text="Remove Item", command=self.remove_cart_item, 
                      style='Warning.TButton').grid(row=0, column=1, padx=5)
            ttk.Button(action_frame, text="Clear Cart", command=self.clear_cart, 
                      style='Danger.TButton').grid(row=0, column=2, padx=5)
            
            # Total and checkout
            total_frame = ttk.LabelFrame(self.content_frame, text="Order Summary", padding="10")
            total_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
            
            ttk.Label(total_frame, text=f"Total: £{total:.2f}", font=('Arial', 14, 'bold')).grid(row=0, column=0, sticky=tk.W)
            
            checkout_frame = ttk.Frame(total_frame)
            checkout_frame.grid(row=0, column=1, sticky=tk.E)
            
            ttk.Button(checkout_frame, text="Continue Shopping", command=self.show_browse_products).grid(row=0, column=0, padx=5)
            ttk.Button(checkout_frame, text="Checkout", command=self.show_checkout, 
                      style='Success.TButton').grid(row=0, column=1, padx=5)
        
        self.update_status("Cart loaded")
        
    def update_cart_quantity(self):
        """Update quantity of selected cart item"""
        if not hasattr(self, 'cart_tree'):
            return
            
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to update")
            return
        
        item = self.cart_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        
        # Find item in cart
        cart_item = None
        for item in self.cart_items:
            if item['product_id'] == product_id:
                cart_item = item
                break
        
        if not cart_item:
            return
        
        # Ask for new quantity
        new_quantity = simpledialog.askinteger("Update Quantity", 
                                             f"Enter new quantity for {cart_item['name']}:", 
                                             initialvalue=cart_item['quantity'], 
                                             minvalue=1, maxvalue=100)
        
        if new_quantity:
            try:
                # Check stock
                product_details = self.get_product_details(product_id)
                if new_quantity > product_details['quantity']:
                    messagebox.showerror("Error", f"Insufficient stock. Only {product_details['quantity']} available.")
                    return
                
                cart_item['quantity'] = new_quantity
                cart_item['subtotal'] = cart_item['price'] * new_quantity
                
                self.show_shopping_cart()  # Refresh display
                self.update_status(f"Updated quantity for {cart_item['name']}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update quantity: {e}")
                
    def remove_cart_item(self):
        """Remove selected item from cart"""
        if not hasattr(self, 'cart_tree'):
            return
            
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to remove")
            return
        
        item = self.cart_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        
        # Find and remove item from cart
        for i, cart_item in enumerate(self.cart_items):
            if cart_item['product_id'] == product_id:
                if messagebox.askyesno("Confirm", f"Remove {cart_item['name']} from cart?"):
                    del self.cart_items[i]
                    self.show_shopping_cart()  # Refresh display
                    self.update_status(f"Removed {cart_item['name']} from cart")
                break
                
    def clear_cart(self):
        """Clear all items from cart"""
        if self.cart_items and messagebox.askyesno("Confirm", "Clear all items from cart?"):
            self.cart_items.clear()
            self.show_shopping_cart()  # Refresh display
            self.update_status("Cart cleared")
            
    def show_checkout(self):
        """Display checkout interface"""
        if not self.cart_items:
            messagebox.showwarning("Warning", "Cart is empty")
            return
        
        # Create checkout window
        checkout_window = tk.Toplevel(self.root)
        checkout_window.title("Checkout")
        checkout_window.geometry("600x500")
        checkout_window.resizable(False, False)
        
        # Make it modal
        checkout_window.transient(self.root)
        checkout_window.grab_set()
        
        main_frame = ttk.Frame(checkout_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Order summary
        summary_frame = ttk.LabelFrame(main_frame, text="Order Summary", padding="10")
        summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        total = 0
        for i, item in enumerate(self.cart_items):
            ttk.Label(summary_frame, text=f"{item['name']} x {item['quantity']}").grid(row=i, column=0, sticky=tk.W)
            ttk.Label(summary_frame, text=f"£{item['subtotal']:.2f}").grid(row=i, column=1, sticky=tk.E)
            total += item['subtotal']
        
        ttk.Separator(summary_frame, orient='horizontal').grid(row=len(self.cart_items), column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(summary_frame, text="Total:", font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=0, sticky=tk.W)
        ttk.Label(summary_frame, text=f"£{total:.2f}", font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=1, sticky=tk.E)
        
        summary_frame.columnconfigure(0, weight=1)
        
        # Payment method
        payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="10")
        payment_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        payment_var = tk.StringVar(value="Credit/Debit Card")
        ttk.Radiobutton(payment_frame, text="Credit/Debit Card", variable=payment_var, 
                       value="Credit/Debit Card").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(payment_frame, text="Student Account", variable=payment_var, 
                       value="Student Account").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(payment_frame, text="PayPal", variable=payment_var, 
                       value="PayPal").grid(row=2, column=0, sticky=tk.W, pady=2)
        
        # Customer info
        info_frame = ttk.LabelFrame(main_frame, text="Customer Information", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        name_var = tk.StringVar(value=self.current_user.get('username', ''))
        ttk.Entry(info_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=2)
        
        ttk.Label(info_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=2)
        email_var = tk.StringVar(value=self.current_user.get('email', ''))
        ttk.Entry(info_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=20)
        
        def complete_checkout():
            try:
                # Process checkout
                transaction_id = self.process_checkout(payment_var.get(), name_var.get(), email_var.get())
                
                checkout_window.destroy()
                self.cart_items.clear()
                
                messagebox.showinfo("Success", f"Order completed successfully!\nTransaction ID: {transaction_id}")
                self.show_order_history()
                
            except Exception as e:
                messagebox.showerror("Error", f"Checkout failed: {e}")
        
        ttk.Button(button_frame, text="Complete Order", command=complete_checkout, 
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=checkout_window.destroy).grid(row=0, column=1, padx=5)
        
    def process_checkout(self, payment_method, customer_name, customer_email):
        """Process the checkout and create transaction"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                # Generate transaction ID
                transaction_id = f"T{int(time.time())}"
                transaction_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate total
                total = sum(item['subtotal'] for item in self.cart_items)
                
                # Process Student Account payment via finance system
                if payment_method == "Student Account":
                    student_id = self.current_user.get('student_id')
                    if student_id:
                        success = self._process_student_account_payment(student_id, total, transaction_id, customer_name)
                        if not success:
                            raise Exception("Student account payment failed")

                # Create transaction
                cursor.execute("""
                    INSERT INTO shop_transactions
                    (transaction_id, user_id, student_id, total_amount, transaction_date, payment_method, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    transaction_id,
                    self.current_user.get('id', 1),
                    self.current_user.get('student_id'),
                    total,
                    transaction_date,
                    payment_method,
                    "Completed",
                    f"GUI Checkout - {customer_name}"
                ])
                
                # Create transaction items and update inventory
                for item in self.cart_items:
                    cursor.execute("""
                        INSERT INTO shop_transaction_items
                        (transaction_id, product_id, quantity, price_per_item, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, [
                        transaction_id,
                        item['product_id'],
                        item['quantity'],
                        item['price'],
                        item['subtotal']
                    ])
                    
                    # Update inventory
                    cursor.execute("""
                        UPDATE shop_inventory
                        SET quantity = quantity - ?
                        WHERE product_id = ?
                    """, [item['quantity'], item['product_id']])
                
                conn.commit()
                conn.close()

                # Send order confirmation email
                self._send_shop_order_confirmation_email(transaction_id, customer_name, customer_email, total, payment_method)

                return transaction_id
            else:
                # Fallback - just return a mock transaction ID
                return f"T{int(time.time())}"
                
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Checkout processing failed: {e}")
            
    def show_order_history(self):
        """Display order history interface"""
        self.clear_content()
        self.update_status("Loading order history...")
        
        # Title
        ttk.Label(self.content_frame, text="Order History", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))
        
        # Orders list
        orders_frame = ttk.LabelFrame(self.content_frame, text="Your Orders", padding="10")
        orders_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        orders_frame.columnconfigure(0, weight=1)
        orders_frame.rowconfigure(0, weight=1)
        
        # Create treeview for orders
        order_columns = ('Transaction ID', 'Date', 'Total', 'Payment Method', 'Status')
        self.orders_tree = ttk.Treeview(orders_frame, columns=order_columns, show='headings', height=15)
        
        # Configure columns
        for col in order_columns:
            self.orders_tree.heading(col, text=col)
        
        self.orders_tree.column('Transaction ID', width=150)
        self.orders_tree.column('Date', width=150)
        self.orders_tree.column('Total', width=100)
        self.orders_tree.column('Payment Method', width=150)
        self.orders_tree.column('Status', width=100)
        
        # Scrollbar
        orders_scrollbar = ttk.Scrollbar(orders_frame, orient='vertical', command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=orders_scrollbar.set)
        
        self.orders_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        orders_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Double-click to view details
        self.orders_tree.bind('<Double-1>', self.view_order_details)
        
        # Load orders
        self.load_order_history()
        
        # Action buttons
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="View Details", command=self.view_order_details).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="Refresh", command=self.load_order_history).grid(row=0, column=1, padx=5)
        
        self.update_status("Order history loaded")
        
    def load_order_history(self):
        """Load order history from database"""
        try:
            # Clear existing items
            for item in self.orders_tree.get_children():
                self.orders_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT transaction_id, transaction_date, total_amount, payment_method, status
                    FROM shop_transactions
                    WHERE user_id = ?
                    ORDER BY transaction_date DESC
                """, [self.current_user.get('id', 1)])
                
                orders = cursor.fetchall()
                
                for order in orders:
                    self.orders_tree.insert('', 'end', values=(
                        order['transaction_id'],
                        order['transaction_date'],
                        f"£{order['total_amount']:.2f}",
                        order['payment_method'],
                        order['status']
                    ))
                
                conn.close()
            else:
                # Sample data
                sample_orders = [
                    ("T1234567890", "2024-01-15 14:30:00", "£45.98", "Credit Card", "Completed"),
                    ("T1234567891", "2024-01-10 10:15:00", "£29.99", "PayPal", "Completed"),
                ]
                
                for order in sample_orders:
                    self.orders_tree.insert('', 'end', values=order)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load order history: {e}")
            
    def view_order_details(self, event=None):
        """View detailed order information"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an order first")
            return
        
        item = self.orders_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Order Details - {transaction_id}")
        details_window.geometry("600x500")
        details_window.resizable(True, True)
        
        # Make it modal
        details_window.transient(self.root)
        details_window.grab_set()
        
        main_frame = ttk.Frame(details_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Order info
        info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        try:
            order_data = self.get_order_details(transaction_id)
            
            if order_data:
                ttk.Label(info_frame, text=f"Transaction ID: {order_data['transaction']['transaction_id']}").grid(row=0, column=0, sticky=tk.W)
                ttk.Label(info_frame, text=f"Date: {order_data['transaction']['transaction_date']}").grid(row=1, column=0, sticky=tk.W)
                ttk.Label(info_frame, text=f"Total: £{order_data['transaction']['total_amount']:.2f}").grid(row=2, column=0, sticky=tk.W)
                ttk.Label(info_frame, text=f"Payment: {order_data['transaction']['payment_method']}").grid(row=3, column=0, sticky=tk.W)
                ttk.Label(info_frame, text=f"Status: {order_data['transaction']['status']}").grid(row=4, column=0, sticky=tk.W)
        
        except Exception as e:
            ttk.Label(info_frame, text=f"Error loading order details: {e}", style='Error.TLabel').grid(row=0, column=0)
        
        # Items list
        items_frame = ttk.LabelFrame(main_frame, text="Order Items", padding="10")
        items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)
        
        # Create treeview for items
        item_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
        items_tree = ttk.Treeview(items_frame, columns=item_columns, show='headings')
        
        for col in item_columns:
            items_tree.heading(col, text=col)
        
        items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
        items_tree.configure(yscrollcommand=items_scrollbar.set)
        
        items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Load items
        try:
            if order_data and 'items' in order_data:
                for item in order_data['items']:
                    items_tree.insert('', 'end', values=(
                        item['product_id'],
                        item['name'],
                        f"£{item['price_per_item']:.2f}",
                        item['quantity'],
                        f"£{item['subtotal']:.2f}"
                    ))
        except Exception as e:
            pass
        
        # Close button
        ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)
        
    def get_order_details(self, transaction_id):
        """Get detailed order information"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get transaction
                cursor.execute("""
                    SELECT * FROM shop_transactions
                    WHERE transaction_id = ?
                """, [transaction_id])
                
                transaction = cursor.fetchone()
                
                if not transaction:
                    return None
                
                # Get items
                cursor.execute("""
                    SELECT ti.*, p.name
                    FROM shop_transaction_items ti
                    JOIN shop_products p ON ti.product_id = p.product_id
                    WHERE ti.transaction_id = ?
                """, [transaction_id])
                
                items = cursor.fetchall()
                
                conn.close()
                
                return {
                    'transaction': dict(transaction),
                    'items': [dict(item) for item in items]
                }
            
            return None
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            raise Exception(f"Database error: {e}")
            
    # Management interfaces (for admin/staff users)
    def show_manage_products(self):
        """Display product management interface"""
        self.clear_content()
        self.update_status("Loading product management...")
        
        # Check permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
            ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
            ttk.Label(self.content_frame, text="You don't have permission to manage products").grid(row=1, column=0)
            return
        
        # Title and actions
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(title_frame, text="Product Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        action_frame = ttk.Frame(title_frame)
        action_frame.grid(row=0, column=1, sticky=tk.E)

        ttk.Button(action_frame, text="Quick Add", command=self.show_quick_add_product_dialog,
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="Add Product", command=self.show_add_product_dialog,
                  style='Success.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(action_frame, text="Import Products", command=self.import_products).grid(row=0, column=2, padx=5)
        ttk.Button(action_frame, text="Export Products", command=self.export_products).grid(row=0, column=3, padx=5)
        ttk.Button(action_frame, text="Backup DB", command=self.backup_shop_database).grid(row=0, column=4, padx=5)
        ttk.Button(action_frame, text="Cleanup Discounts", command=self.cleanup_expired_discounts).grid(row=0, column=5, padx=5)
        
        # Products table with management features
        products_frame = ttk.LabelFrame(self.content_frame, text="Products", padding="10")
        products_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        products_frame.columnconfigure(0, weight=1)
        products_frame.rowconfigure(0, weight=1)
        
        # Enhanced treeview with more columns
        mgmt_columns = ('ID', 'Name', 'Category', 'Price', 'Stock', 'Status', 'Created', 'Updated')
        self.mgmt_products_tree = ttk.Treeview(products_frame, columns=mgmt_columns, show='headings', height=15)
        
        # Configure columns
        for col in mgmt_columns:
            self.mgmt_products_tree.heading(col, text=col)
        
        self.mgmt_products_tree.column('ID', width=80)
        self.mgmt_products_tree.column('Name', width=200)
        self.mgmt_products_tree.column('Category', width=120)
        self.mgmt_products_tree.column('Price', width=80)
        self.mgmt_products_tree.column('Stock', width=60)
        self.mgmt_products_tree.column('Status', width=80)
        self.mgmt_products_tree.column('Created', width=100)
        self.mgmt_products_tree.column('Updated', width=100)
        
        # Scrollbars
        v_scroll_mgmt = ttk.Scrollbar(products_frame, orient='vertical', command=self.mgmt_products_tree.yview)
        h_scroll_mgmt = ttk.Scrollbar(products_frame, orient='horizontal', command=self.mgmt_products_tree.xview)
        self.mgmt_products_tree.configure(yscrollcommand=v_scroll_mgmt.set, xscrollcommand=h_scroll_mgmt.set)
        
        self.mgmt_products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scroll_mgmt.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scroll_mgmt.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Context menu for management
        self.create_mgmt_context_menu()
        
        # Management action buttons
        mgmt_action_frame = ttk.Frame(self.content_frame)
        mgmt_action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(mgmt_action_frame, text="Edit Product", command=self.edit_selected_product).grid(row=0, column=0, padx=5)
        ttk.Button(mgmt_action_frame, text="Toggle Status", command=self.toggle_product_status, 
                  style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(mgmt_action_frame, text="Delete Product", command=self.delete_selected_product, 
                  style='Danger.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(mgmt_action_frame, text="Bulk Price Update", command=self.bulk_price_update).grid(row=0, column=3, padx=5)
        
        # Load products for management
        self.load_products_for_management()
        self.update_status("Product management loaded")
        
    def create_mgmt_context_menu(self):
        """Create context menu for product management"""
        self.mgmt_context_menu = tk.Menu(self.root, tearoff=0)
        self.mgmt_context_menu.add_command(label="Edit Product", command=self.edit_selected_product)
        self.mgmt_context_menu.add_command(label="Toggle Status", command=self.toggle_product_status)
        self.mgmt_context_menu.add_separator()
        self.mgmt_context_menu.add_command(label="Update Stock", command=self.update_selected_stock)
        self.mgmt_context_menu.add_command(label="View Sales", command=self.view_product_sales)
        self.mgmt_context_menu.add_separator()
        self.mgmt_context_menu.add_command(label="Delete Product", command=self.delete_selected_product)
        
        # Bind right-click
        self.mgmt_products_tree.bind('<Button-3>', self.show_mgmt_context_menu)
        
    def show_mgmt_context_menu(self, event):
        """Show management context menu"""
        item = self.mgmt_products_tree.identify_row(event.y)
        if item:
            self.mgmt_products_tree.selection_set(item)
            self.mgmt_context_menu.post(event.x_root, event.y_root)
            
    def load_products_for_management(self):
        """Load products for management view"""
        try:
            # Clear existing items
            for item in self.mgmt_products_tree.get_children():
                self.mgmt_products_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT p.*, i.quantity
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    ORDER BY p.created_at DESC
                """)
                
                products = cursor.fetchall()
                
                for product in products:
                    status = "Active" if product['is_active'] else "Inactive"
                    created = product['created_at'][:10] if product['created_at'] else 'N/A'
                    updated = product['updated_at'][:10] if product['updated_at'] else 'N/A'
                    
                    self.mgmt_products_tree.insert('', 'end', values=(
                        product['product_id'],
                        product['name'],
                        product['category'],
                        f"£{product['price']:.2f}",
                        product['quantity'],
                        status,
                        created,
                        updated
                    ))
                
                conn.close()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load products: {e}")
            
    def show_add_product_dialog(self):
        """Show dialog for adding new product"""
        # Create add product window
        add_window = tk.Toplevel(self.root)
        add_window.title("Add New Product")
        add_window.geometry("500x600")
        add_window.resizable(False, False)
        
        # Make it modal
        add_window.transient(self.root)
        add_window.grab_set()
        
        main_frame = ttk.Frame(add_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Form fields
        ttk.Label(main_frame, text="Product Name*:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=5)
        desc_text = tk.Text(main_frame, height=4, width=40)
        desc_text.grid(row=1, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Price (£)*:").grid(row=2, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=price_var, width=40).grid(row=2, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Category*:").grid(row=3, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar()
        category_entry = ttk.Entry(main_frame, textvariable=category_var, width=40)
        category_entry.grid(row=3, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Initial Stock*:").grid(row=4, column=0, sticky=tk.W, pady=5)
        stock_var = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=stock_var, width=40).grid(row=4, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Restock Threshold:").grid(row=5, column=0, sticky=tk.W, pady=5)
        threshold_var = tk.StringVar(value="5")
        ttk.Entry(main_frame, textvariable=threshold_var, width=40).grid(row=5, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Tax Rate (%):").grid(row=6, column=0, sticky=tk.W, pady=5)
        tax_var = tk.StringVar(value="20")
        ttk.Entry(main_frame, textvariable=tax_var, width=40).grid(row=6, column=1, pady=5, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        def save_product():
            try:
                # Validate inputs
                if not all([name_var.get().strip(), price_var.get().strip(), 
                           category_var.get().strip(), stock_var.get().strip()]):
                    messagebox.showerror("Error", "Please fill in all required fields (*)")
                    return
                
                # Create product
                product_data = {
                    'name': name_var.get().strip(),
                    'description': desc_text.get('1.0', 'end-1c').strip(),
                    'price': float(price_var.get()),
                    'category': category_var.get().strip(),
                    'initial_stock': int(stock_var.get()),
                    'restock_threshold': int(threshold_var.get()),
                    'tax_rate': float(tax_var.get()) / 100
                }
                
                self.create_product(product_data)
                add_window.destroy()
                self.load_products_for_management()
                messagebox.showinfo("Success", "Product added successfully!")
                
            except ValueError as e:
                messagebox.showerror("Error", "Please enter valid numeric values")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add product: {e}")
        
        ttk.Button(button_frame, text="Save Product", command=save_product, 
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=add_window.destroy).grid(row=0, column=1, padx=5)
        
    def create_product(self, product_data):
        """Create a new product in the database"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                # Generate product ID
                cursor.execute("SELECT MAX(SUBSTR(product_id, 2)) FROM shop_products WHERE product_id LIKE 'P%'")
                result = cursor.fetchone()
                
                try:
                    if result[0]:
                        next_id = int(result[0]) + 1
                    else:
                        next_id = 1
                    product_id = f"P{next_id:03d}"
                except (ValueError, TypeError):
                    product_id = f"P{int(time.time())}"
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Insert product
                cursor.execute("""
                    INSERT INTO shop_products
                    (product_id, name, description, price, category, created_at, updated_at, tax_rate, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    product_id,
                    product_data['name'],
                    product_data['description'],
                    product_data['price'],
                    product_data['category'],
                    now,
                    now,
                    product_data['tax_rate'],
                    1
                ])
                
                # Insert inventory
                cursor.execute("""
                    INSERT INTO shop_inventory
                    (product_id, quantity, last_restock_date, restock_threshold)
                    VALUES (?, ?, ?, ?)
                """, [
                    product_id,
                    product_data['initial_stock'],
                    now,
                    product_data['restock_threshold']
                ])
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Database error: {e}")

    def show_quick_add_product_dialog(self):
        """Show quick add product dialog with minimal inputs"""
        # Create quick add window
        quick_window = tk.Toplevel(self.root)
        quick_window.title("Quick Add Product")
        quick_window.geometry("400x350")
        quick_window.resizable(False, False)

        # Make it modal
        quick_window.transient(self.root)
        quick_window.grab_set()

        main_frame = ttk.Frame(quick_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        ttk.Label(main_frame, text="Quick Add Product", style='Heading.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15))

        # Info label
        info_label = ttk.Label(main_frame,
            text="Streamlined product entry with auto-filled defaults",
            foreground='gray', font=('Arial', 9, 'italic'))
        info_label.grid(row=1, column=0, columnspan=2, pady=(0, 15))

        # Form fields - minimal inputs
        ttk.Label(main_frame, text="Product Name*:").grid(row=2, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=name_var, width=30).grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(main_frame, text="Price (£)*:").grid(row=3, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=price_var, width=30).grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(main_frame, text="Category:").grid(row=4, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar(value="General")
        ttk.Entry(main_frame, textvariable=category_var, width=30).grid(row=4, column=1, pady=5, padx=(10, 0))

        ttk.Label(main_frame, text="Initial Stock:").grid(row=5, column=0, sticky=tk.W, pady=5)
        stock_var = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=stock_var, width=30).grid(row=5, column=1, pady=5, padx=(10, 0))

        # Defaults info
        defaults_label = ttk.Label(main_frame,
            text="Auto-defaults: Description='Quick-added', Tax=20%, Threshold=auto",
            foreground='gray', font=('Arial', 8))
        defaults_label.grid(row=6, column=0, columnspan=2, pady=(15, 5))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        def quick_save_product():
            try:
                # Validate minimal required inputs
                if not name_var.get().strip() or not price_var.get().strip():
                    messagebox.showerror("Error", "Please fill in Product Name and Price")
                    return

                price = float(price_var.get())
                stock = int(stock_var.get())

                if price < 0:
                    messagebox.showerror("Error", "Price must be >= 0")
                    return
                if stock < 0:
                    messagebox.showerror("Error", "Stock must be >= 0")
                    return

                # Create product with auto-defaults
                product_data = {
                    'name': name_var.get().strip(),
                    'description': f"Quick-added product: {name_var.get().strip()}",
                    'price': price,
                    'category': category_var.get().strip() or "General",
                    'initial_stock': stock,
                    'restock_threshold': max(5, stock // 4),  # Auto-calculated
                    'tax_rate': 0.20  # Default 20%
                }

                self.create_product(product_data)
                quick_window.destroy()
                self.load_products_for_management()
                messagebox.showinfo("Success", f"Product '{product_data['name']}' added quickly!")

            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers for Price and Stock")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to quick add product: {e}")

        ttk.Button(button_frame, text="Quick Save", command=quick_save_product,
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=quick_window.destroy).grid(row=0, column=1, padx=5)

    def backup_shop_database(self):
        """Create timestamped backup of shop database"""
        try:
            import shutil
            from datetime import datetime

            # Generate timestamped backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"shop_backup_{timestamp}.db"

            # Get the current database path
            from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH as DB_PATH
            db_path = str(DB_PATH)

            # Let user choose save location
            from tkinter import filedialog
            save_path = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                initialfile=backup_filename,
                title="Save Database Backup"
            )

            if not save_path:
                return  # User cancelled

            # Perform backup
            shutil.copy2(db_path, save_path)

            messagebox.showinfo("Backup Complete",
                f"Database backed up successfully!\n\nBackup saved to:\n{save_path}\n\nSize: {os.path.getsize(save_path) / 1024:.2f} KB")

        except Exception as e:
            messagebox.showerror("Backup Failed", f"Failed to backup database: {e}")

    def cleanup_expired_discounts(self):
        """Deactivate all expired discounts"""
        try:
            from datetime import datetime

            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()

                # Get current datetime
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Find expired discounts
                cursor.execute("""
                    SELECT discount_id, code, end_date
                    FROM shop_discounts
                    WHERE end_date < ? AND is_active = 1
                """, (now,))

                expired_discounts = cursor.fetchall()

                if not expired_discounts:
                    messagebox.showinfo("Cleanup Complete", "No expired discounts found.")
                    conn.close()
                    return

                # Deactivate expired discounts
                cursor.execute("""
                    UPDATE shop_discounts
                    SET is_active = 0
                    WHERE end_date < ? AND is_active = 1
                """, (now,))

                count = cursor.rowcount
                conn.commit()
                conn.close()

                # Show details
                discount_list = "\n".join([f"- {d[1]} (expired: {d[2]})" for d in expired_discounts[:5]])
                if len(expired_discounts) > 5:
                    discount_list += f"\n... and {len(expired_discounts) - 5} more"

                messagebox.showinfo("Cleanup Complete",
                    f"Deactivated {count} expired discount(s):\n\n{discount_list}")

                # Refresh discounts view if visible
                if hasattr(self, 'load_discounts'):
                    self.load_discounts()

        except Exception as e:
            messagebox.showerror("Cleanup Failed", f"Failed to cleanup expired discounts: {e}")

    def launch_cli_mode(self):
        """Launch the original CLI mode in a separate window"""
        try:
            # Create CLI window
            cli_window = tk.Toplevel(self.root)
            cli_window.title("CLI Mode - University Shop")
            cli_window.geometry("800x600")
            
            # Create text widget for CLI output
            cli_frame = ttk.Frame(cli_window, padding="10")
            cli_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            cli_frame.columnconfigure(0, weight=1)
            cli_frame.rowconfigure(0, weight=1)
            
            cli_text = tk.Text(cli_frame, wrap=tk.WORD, state='disabled', 
                              bg='black', fg='green', font=('Consolas', 10))
            cli_scrollbar = ttk.Scrollbar(cli_frame, orient='vertical', command=cli_text.yview)
            cli_text.configure(yscrollcommand=cli_scrollbar.set)
            
            cli_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            cli_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Configure window grid
            cli_window.columnconfigure(0, weight=1)
            cli_window.rowconfigure(0, weight=1)
            
            # Add message about CLI mode
            cli_text.configure(state='normal')
            cli_text.insert(tk.END, "CLI Mode Integration\n")
            cli_text.insert(tk.END, "=" * 50 + "\n\n")
            cli_text.insert(tk.END, "The original CLI functions are available and can be called programmatically.\n")
            cli_text.insert(tk.END, "To use the full CLI interface, run:\n")
            cli_text.insert(tk.END, "python university_system/modules/domain/commerce/services/shop_management.py\n\n")
            cli_text.insert(tk.END, "Available CLI functions:\n")
            cli_text.insert(tk.END, "- browse_products()\n")
            cli_text.insert(tk.END, "- add_to_shopping_cart()\n")
            cli_text.insert(tk.END, "- checkout_process()\n")
            cli_text.insert(tk.END, "- view_purchase_history()\n")
            cli_text.insert(tk.END, "- display_product_management_menu()\n")
            cli_text.insert(tk.END, "- generate_sales_reports()\n")
            cli_text.insert(tk.END, "- And many more...\n\n")
            cli_text.insert(tk.END, "All original functionality is preserved for backward compatibility.\n")
            cli_text.configure(state='disabled')
            
            # Button to launch actual CLI
            button_frame = ttk.Frame(cli_window)
            button_frame.grid(row=1, column=0, pady=10)
            
            def launch_external_cli():
                try:
                    import subprocess
                    import sys
                    import os
                    # Get the correct path to shop_management.py
                    shop_cli_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "services",
                        "shop_management.py"
                    )
                    if os.path.exists(shop_cli_path):
                        subprocess.Popen([sys.executable, shop_cli_path])
                        messagebox.showinfo("CLI Launched", "Original CLI mode launched in separate process")
                    else:
                        messagebox.showerror("Error", f"CLI file not found at:\n{shop_cli_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to launch CLI: {e}")
            
            ttk.Button(button_frame, text="Launch External CLI", 
                      command=launch_external_cli).grid(row=0, column=0, padx=5)
            ttk.Button(button_frame, text="Close", 
                      command=cli_window.destroy).grid(row=0, column=1, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch CLI mode: {e}")
            
    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.geometry("600x500")
        about_window.resizable(True, True)

        # Make it modal
        about_window.transient(self.root)
        
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # About content
        ttk.Label(main_frame, text="University Shop Management System", 
                 style='Title.TLabel').grid(row=0, column=0, pady=10)
        
        ttk.Label(main_frame, text="GUI Version with CLI Compatibility").grid(row=1, column=0, pady=5)
        ttk.Label(main_frame, text="Built with Python & Tkinter").grid(row=2, column=0, pady=5)
        
        info_text = """
This GUI application provides a modern interface for the 
University Shop Management System while maintaining full 
backward compatibility with the original CLI version.

Features:
• Product browsing and shopping cart
• Order management and history
• Admin product management
• Inventory tracking
• Sales reporting
• Discount management
• Full CLI function integration

All original CLI functions remain available and can be 
called directly for automation or scripting purposes.
        """
        
        text_widget = tk.Text(main_frame, height=15, width=60, wrap=tk.WORD, state='disabled')
        text_widget.grid(row=3, column=0, pady=10)
        text_widget.configure(state='normal')
        text_widget.insert('1.0', info_text.strip())
        text_widget.configure(state='disabled')

        ttk.Button(main_frame, text="Close", command=about_window.destroy).grid(row=4, column=0, pady=10)

        # Now that window is fully created, make it modal
        about_window.update_idletasks()
        about_window.grab_set()
        
    # Additional management functions
    def edit_selected_product(self):
        """Edit the selected product"""
        if not hasattr(self, 'mgmt_products_tree'):
            return
            
        selection = self.mgmt_products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product to edit")
            return
        
        item = self.mgmt_products_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        
        # Get current product data
        try:
            product_data = self.get_product_details(product_id)
            if not product_data:
                messagebox.showerror("Error", "Product not found")
                return
            
            # Create edit window
            edit_window = tk.Toplevel(self.root)
            edit_window.title(f"Edit Product - {product_id}")
            edit_window.geometry("500x600")
            edit_window.resizable(False, False)
            
            # Make it modal
            edit_window.transient(self.root)
            edit_window.grab_set()
            
            main_frame = ttk.Frame(edit_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Form fields with current values
            ttk.Label(main_frame, text="Product ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
            ttk.Label(main_frame, text=product_id, font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
            
            ttk.Label(main_frame, text="Product Name*:").grid(row=1, column=0, sticky=tk.W, pady=5)
            name_var = tk.StringVar(value=product_data.get('name', ''))
            ttk.Entry(main_frame, textvariable=name_var, width=40).grid(row=1, column=1, pady=5, padx=(10, 0))
            
            ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
            desc_text = tk.Text(main_frame, height=4, width=40)
            desc_text.grid(row=2, column=1, pady=5, padx=(10, 0))
            desc_text.insert('1.0', product_data.get('description', ''))
            
            ttk.Label(main_frame, text="Price (£)*:").grid(row=3, column=0, sticky=tk.W, pady=5)
            price_var = tk.StringVar(value=str(product_data.get('price', '')))
            ttk.Entry(main_frame, textvariable=price_var, width=40).grid(row=3, column=1, pady=5, padx=(10, 0))
            
            ttk.Label(main_frame, text="Category*:").grid(row=4, column=0, sticky=tk.W, pady=5)
            category_var = tk.StringVar(value=product_data.get('category', ''))
            ttk.Entry(main_frame, textvariable=category_var, width=40).grid(row=4, column=1, pady=5, padx=(10, 0))
            
            ttk.Label(main_frame, text="Tax Rate (%):").grid(row=5, column=0, sticky=tk.W, pady=5)
            tax_rate = product_data.get('tax_rate', 0.2) * 100
            tax_var = tk.StringVar(value=str(tax_rate))
            ttk.Entry(main_frame, textvariable=tax_var, width=40).grid(row=5, column=1, pady=5, padx=(10, 0))
            
            # Status
            ttk.Label(main_frame, text="Status:").grid(row=6, column=0, sticky=tk.W, pady=5)
            status_var = tk.BooleanVar(value=product_data.get('is_active', True))
            ttk.Checkbutton(main_frame, text="Active", variable=status_var).grid(row=6, column=1, sticky=tk.W, padx=(10, 0), pady=5)
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=7, column=0, columnspan=2, pady=20)
            
            def save_changes():
                try:
                    # Validate inputs
                    if not all([name_var.get().strip(), price_var.get().strip(), category_var.get().strip()]):
                        messagebox.showerror("Error", "Please fill in all required fields (*)")
                        return
                    
                    # Update product
                    updated_data = {
                        'name': name_var.get().strip(),
                        'description': desc_text.get('1.0', 'end-1c').strip(),
                        'price': float(price_var.get()),
                        'category': category_var.get().strip(),
                        'tax_rate': float(tax_var.get()) / 100,
                        'is_active': status_var.get()
                    }
                    
                    self.update_product(product_id, updated_data)
                    edit_window.destroy()
                    self.load_products_for_management()
                    messagebox.showinfo("Success", "Product updated successfully!")
                    
                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numeric values")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update product: {e}")
            
            ttk.Button(button_frame, text="Save Changes", command=save_changes, 
                      style='Success.TButton').grid(row=0, column=0, padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_window.destroy).grid(row=0, column=1, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load product for editing: {e}")
            
    def update_product(self, product_id, updated_data):
        """Update product in database"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    UPDATE shop_products
                    SET name = ?, description = ?, price = ?, category = ?, 
                        tax_rate = ?, is_active = ?, updated_at = ?
                    WHERE product_id = ?
                """, [
                    updated_data['name'],
                    updated_data['description'],
                    updated_data['price'],
                    updated_data['category'],
                    updated_data['tax_rate'],
                    updated_data['is_active'],
                    now,
                    product_id
                ])
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Database error: {e}")
            
    def toggle_product_status(self):
        """Toggle active status of selected product"""
        if not hasattr(self, 'mgmt_products_tree'):
            return
            
        selection = self.mgmt_products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product")
            return
        
        item = self.mgmt_products_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        current_status = values[5]
        
        new_status = "Inactive" if current_status == "Active" else "Active"
        
        if messagebox.askyesno("Confirm", f"Change product status to {new_status}?"):
            try:
                self.update_product_status(product_id, new_status == "Active")
                self.load_products_for_management()
                self.update_status(f"Product {product_id} status changed to {new_status}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {e}")
                
    def update_product_status(self, product_id, is_active):
        """Update product active status"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE shop_products
                    SET is_active = ?, updated_at = ?
                    WHERE product_id = ?
                """, [is_active, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Database error: {e}")
            
    def delete_selected_product(self):
        """Delete selected product (with confirmation)"""
        if not hasattr(self, 'mgmt_products_tree'):
            return
            
        selection = self.mgmt_products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product to delete")
            return
        
        item = self.mgmt_products_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        product_name = values[1]
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Are you sure you want to delete product '{product_name}' ({product_id})?\n\n"
                              "This action cannot be undone!"):
            try:
                self.delete_product(product_id)
                self.load_products_for_management()
                messagebox.showinfo("Success", f"Product {product_id} deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete product: {e}")
                
    def delete_product(self, product_id):
        """Delete product from database"""
        try:
            if 'get_connection' in globals():
                conn = get_connection()
                cursor = conn.cursor()
                
                # Check if product has transactions
                cursor.execute("""
                    SELECT COUNT(*) FROM shop_transaction_items WHERE product_id = ?
                """, [product_id])
                
                if cursor.fetchone()[0] > 0:
                    raise Exception("Cannot delete product with existing transactions. Consider deactivating instead.")
                
                # Delete inventory first (foreign key constraint)
                cursor.execute("DELETE FROM shop_inventory WHERE product_id = ?", [product_id])
                
                # Delete product
                cursor.execute("DELETE FROM shop_products WHERE product_id = ?", [product_id])
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Database error: {e}")
            
    def update_selected_stock(self):
        """Update stock for selected product"""
        if not hasattr(self, 'mgmt_products_tree'):
            return
            
        selection = self.mgmt_products_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a product")
            return
        
        item = self.mgmt_products_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        current_stock = int(values[4])
        
        new_stock = simpledialog.askinteger("Update Stock", 
                                           f"Enter new stock level for {values[1]}:",
                                           initialvalue=current_stock, minvalue=0, maxvalue=10000)
        
        if new_stock is not None:
            try:
                self.update_product_stock(product_id, new_stock)
                self.load_products_for_management()
                self.update_status(f"Stock updated for {product_id}: {new_stock}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update stock: {e}")
                
    def update_product_stock(self, product_id, new_stock):
        """Update product stock in database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shop_inventory
                SET quantity = ?, last_restock_date = ?
                WHERE product_id = ?
            """, [new_stock, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Stock updated successfully for {product_id}")

        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"Database error: {e}")
            
    def show_manage_inventory(self):
        """Display inventory management interface"""
        self.clear_content()
        self.update_status("Loading inventory management...")
        
        # Check permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
            ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
            return
        
        # Title and quick actions
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(title_frame, text="Inventory Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        quick_frame = ttk.Frame(title_frame)
        quick_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Button(quick_frame, text="Bulk Restock", command=self.bulk_restock, 
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(quick_frame, text="Low Stock Report", command=self.show_low_stock_report, 
                  style='Warning.TButton').grid(row=0, column=1, padx=5)
        
        # Inventory table
        inventory_frame = ttk.LabelFrame(self.content_frame, text="Inventory Status", padding="10")
        inventory_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        inventory_frame.columnconfigure(0, weight=1)
        inventory_frame.rowconfigure(0, weight=1)
        
        # Create treeview for inventory
        inv_columns = ('Product ID', 'Name', 'Category', 'Current Stock', 'Threshold', 'Status', 'Last Restock')
        self.inventory_tree = ttk.Treeview(inventory_frame, columns=inv_columns, show='headings', height=15)
        
        # Configure columns
        for col in inv_columns:
            self.inventory_tree.heading(col, text=col)
        
        self.inventory_tree.column('Product ID', width=100)
        self.inventory_tree.column('Name', width=200)
        self.inventory_tree.column('Category', width=120)
        self.inventory_tree.column('Current Stock', width=100)
        self.inventory_tree.column('Threshold', width=80)
        self.inventory_tree.column('Status', width=80)
        self.inventory_tree.column('Last Restock', width=120)
        
        # Scrollbars
        inv_v_scroll = ttk.Scrollbar(inventory_frame, orient='vertical', command=self.inventory_tree.yview)
        inv_h_scroll = ttk.Scrollbar(inventory_frame, orient='horizontal', command=self.inventory_tree.xview)
        self.inventory_tree.configure(yscrollcommand=inv_v_scroll.set, xscrollcommand=inv_h_scroll.set)
        
        self.inventory_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        inv_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        inv_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Load inventory data
        self.load_inventory_data()
        
        # Action buttons
        inv_action_frame = ttk.Frame(self.content_frame)
        inv_action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(inv_action_frame, text="Update Stock", command=self.update_selected_stock).grid(row=0, column=0, padx=5)
        ttk.Button(inv_action_frame, text="Set Threshold", command=self.set_restock_threshold).grid(row=0, column=1, padx=5)
        ttk.Button(inv_action_frame, text="Restock Item", command=self.restock_selected_item, 
                  style='Success.TButton').grid(row=0, column=2, padx=5)
        
        self.update_status("Inventory management loaded")
        
    def load_inventory_data(self):
        """Load inventory data into treeview"""
        try:
            # Clear existing items
            for item in self.inventory_tree.get_children():
                self.inventory_tree.delete(item)
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold, i.last_restock_date
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.is_active = 1
                    ORDER BY (i.quantity <= i.restock_threshold) DESC, p.category, p.name
                """)
                
                items = cursor.fetchall()
                
                for item in items:
                    # Determine status
                    if item['quantity'] <= item['restock_threshold']:
                        status = "Low Stock"
                        tag = "low_stock"
                    elif item['quantity'] <= item['restock_threshold'] * 1.5:
                        status = "Warning"
                        tag = "warning"
                    else:
                        status = "OK"
                        tag = "ok"
                    
                    last_restock = item['last_restock_date'][:10] if item['last_restock_date'] else 'Never'
                    
                    item_id = self.inventory_tree.insert('', 'end', values=(
                        item['product_id'],
                        item['name'],
                        item['category'],
                        item['quantity'],
                        item['restock_threshold'],
                        status,
                        last_restock
                    ), tags=(tag,))
                
                # Configure tags for coloring
                self.inventory_tree.tag_configure('low_stock', background='#ffcccc')
                self.inventory_tree.tag_configure('warning', background='#ffffcc')
                self.inventory_tree.tag_configure('ok', background='#ccffcc')
                
                conn.close()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inventory: {e}")
            
    def show_all_transactions(self):
        """Display all transactions interface"""
        self.clear_content()
        self.update_status("Loading transactions...")
        
        # Check permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
            ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
            return
        
        # Title and filters
        title_frame = ttk.Frame(self.content_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(title_frame, text="Transaction Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        # Quick stats
        stats_frame = ttk.Frame(title_frame)
        stats_frame.grid(row=0, column=1, sticky=tk.E)
        
        self.transaction_stats_label = ttk.Label(stats_frame, text="Loading...")
        self.transaction_stats_label.grid(row=0, column=0)
        
        # Filters
        filter_frame = ttk.LabelFrame(self.content_frame, text="Filters", padding="10")
        filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(filter_frame, text="Date Range:").grid(row=0, column=0)
        self.trans_start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=self.trans_start_date, width=12).grid(row=0, column=1, padx=5)
        ttk.Label(filter_frame, text="to").grid(row=0, column=2)
        self.trans_end_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=self.trans_end_date, width=12).grid(row=0, column=3, padx=5)
        
        ttk.Button(filter_frame, text="Apply Filter", command=self.load_transactions).grid(row=0, column=4, padx=10)
        ttk.Button(filter_frame, text="Export", command=self.export_transactions).grid(row=0, column=5, padx=5)
        
        # Transactions table
        trans_frame = ttk.LabelFrame(self.content_frame, text="Transactions", padding="10")
        trans_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        trans_frame.columnconfigure(0, weight=1)
        trans_frame.rowconfigure(0, weight=1)
        
        # Create treeview
        trans_columns = ('Transaction ID', 'Date', 'Customer', 'Total', 'Payment Method', 'Status')
        self.trans_tree = ttk.Treeview(trans_frame, columns=trans_columns, show='headings', height=15)
        
        for col in trans_columns:
            self.trans_tree.heading(col, text=col)
        
        self.trans_tree.column('Transaction ID', width=150)
        self.trans_tree.column('Date', width=150)
        self.trans_tree.column('Customer', width=120)
        self.trans_tree.column('Total', width=100)
        self.trans_tree.column('Payment Method', width=120)
        self.trans_tree.column('Status', width=80)
        
        # Scrollbars
        trans_v_scroll = ttk.Scrollbar(trans_frame, orient='vertical', command=self.trans_tree.yview)
        self.trans_tree.configure(yscrollcommand=trans_v_scroll.set)
        
        self.trans_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        trans_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Double-click to view details
        self.trans_tree.bind('<Double-1>', self.view_transaction_details)
        
        # Load initial data
        self.load_transactions()
        
        self.update_status("Transactions loaded")
        
    def load_transactions(self):
        """Load transactions based on filters"""
        try:
            # Clear existing items
            for item in self.trans_tree.get_children():
                self.trans_tree.delete(item)
            
            start_date = self.trans_start_date.get()
            end_date = self.trans_end_date.get()
            
            if 'get_connection' in globals():
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT t.transaction_id, t.transaction_date, u.username, t.total_amount, 
                           t.payment_method, t.status
                    FROM shop_transactions t
                    LEFT JOIN users u ON t.user_id = u.id
                    WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                    ORDER BY t.transaction_date DESC
                """, [start_date, end_date])
                
                transactions = cursor.fetchall()
                
                total_amount = 0
                for trans in transactions:
                    self.trans_tree.insert('', 'end', values=(
                        trans['transaction_id'],
                        trans['transaction_date'],
                        trans['username'] or 'Unknown',
                        f"£{trans['total_amount']:.2f}",
                        trans['payment_method'],
                        trans['status']
                    ))
                    total_amount += trans['total_amount']
                
                # Update stats
                stats_text = f"Transactions: {len(transactions)} | Total: £{total_amount:.2f}"
                self.transaction_stats_label.config(text=stats_text)
                
                conn.close()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transactions: {e}")
            
    def view_transaction_details(self, event=None):
        """View detailed transaction information"""
        selection = self.trans_tree.selection()
        if not selection:
            return
        
        item = self.trans_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]
        
        # Use the existing order details function
        self.view_order_details_by_id(transaction_id)
        
    def view_order_details_by_id(self, transaction_id):
        """View order details by transaction ID (for admin use)"""
        try:
            order_data = self.get_order_details(transaction_id)
            
            if not order_data:
                messagebox.showerror("Error", "Transaction not found")
                return
            
            # Create details window (reuse existing code)
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Transaction Details - {transaction_id}")
            details_window.geometry("600x500")
            details_window.resizable(True, True)
            
            # Make it modal
            details_window.transient(self.root)
            details_window.grab_set()
            
            main_frame = ttk.Frame(details_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(1, weight=1)
            
            # Transaction info
            info_frame = ttk.LabelFrame(main_frame, text="Transaction Information", padding="10")
            info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            
            transaction = order_data['transaction']
            ttk.Label(info_frame, text=f"Transaction ID: {transaction['transaction_id']}").grid(row=0, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Date: {transaction['transaction_date']}").grid(row=1, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Total: £{transaction['total_amount']:.2f}").grid(row=2, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Payment: {transaction['payment_method']}").grid(row=3, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Status: {transaction['status']}").grid(row=4, column=0, sticky=tk.W)
            
            # Items list
            items_frame = ttk.LabelFrame(main_frame, text="Transaction Items", padding="10")
            items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            items_frame.columnconfigure(0, weight=1)
            items_frame.rowconfigure(0, weight=1)
            
            # Create treeview for items
            item_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
            items_tree = ttk.Treeview(items_frame, columns=item_columns, show='headings')
            
            for col in item_columns:
                items_tree.heading(col, text=col)
            
            items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
            items_tree.configure(yscrollcommand=items_scrollbar.set)
            
            items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Load items
            for item in order_data['items']:
                items_tree.insert('', 'end', values=(
                    item['product_id'],
                    item['name'],
                    f"£{item['price_per_item']:.2f}",
                    item['quantity'],
                    f"£{item['subtotal']:.2f}"
                ))
            
            # Close button
            ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transaction details: {e}")
            
    def show_report_window(self, title, report_content):
        """
        Display a report in a new window with export and email buttons.

        Args:
            title: Window title and report name
            report_content: The text content of the report
        """
        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("900x700")
        report_window.transient(self.root)

        main_frame = ttk.Frame(report_window, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=10)

        # Report display area
        report_frame = ttk.LabelFrame(main_frame, text="Report", padding=10)
        report_frame.pack(fill='both', expand=True, pady=10)

        from tkinter.scrolledtext import ScrolledText
        report_text = ScrolledText(report_frame, height=25, width=100, font=('Courier', 9))
        report_text.pack(fill='both', expand=True)
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')  # Make read-only

        # Buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        def export_as_txt():
            """Export report to a text file"""
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                # Clean title for filename
                clean_title = title.replace(' ', '_').replace('/', '_').replace('\\', '_')
                filename = f"{clean_title}_{timestamp}.txt"
                filepath = os.path.join(os.getcwd(), filename)

                with open(filepath, 'w') as f:
                    f.write(report_content)

                messagebox.showinfo("Export Success",
                                  f"Report exported successfully!\n\n"
                                  f"File: {filename}\n"
                                  f"Location: {filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report:\n{str(e)}")

        def email_to_admin():
            """Email report to admin"""
            try:
                # Get admin email from database
                conn = get_connection()
                if not conn:
                    messagebox.showerror("Database Error", "Could not connect to database")
                    return

                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
                result = cursor.fetchone()
                conn.close()

                if not result or not result[0]:
                    messagebox.showerror("Email Error",
                                       "No admin email found in database.\n"
                                       "Please configure an admin email address first.")
                    return

                admin_email = result[0]

                # Import email service
                try:
                    from university_system.infrastructure.email.email_service import send_email
                except ImportError:
                    messagebox.showerror("Email Error",
                                       "Email service not available.\n"
                                       "Please check your email configuration.")
                    return

                # Send the email
                subject = f"Shop Report: {title}"
                body = f"Please find the {title} below:\n\n{report_content}"

                send_email(admin_email, subject, body)

                messagebox.showinfo("Email Sent",
                                  f"Report has been sent to admin email:\n{admin_email}")

            except Exception as e:
                messagebox.showerror("Email Error", f"Failed to send email:\n{str(e)}")

        ttk.Button(btn_frame, text="Export as TXT", command=export_as_txt).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Email to Admin", command=email_to_admin).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=report_window.destroy).pack(side='left', padx=5)

        # Now that window is fully created, make it modal
        report_window.update_idletasks()
        report_window.grab_set()

    def show_reports(self):
        """Display reports interface"""
        self.clear_content()
        self.update_status("Loading reports...")
        
        # Check permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
            ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
            return
        
        # Title
        ttk.Label(self.content_frame, text="Sales Reports", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))
        
        # Report categories
        reports_frame = ttk.Frame(self.content_frame)
        reports_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        reports_frame.columnconfigure((0, 1), weight=1)
        
        # Quick Reports
        quick_frame = ttk.LabelFrame(reports_frame, text="Quick Reports", padding="15")
        quick_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))
        
        ttk.Button(quick_frame, text="📊 Daily Sales", command=lambda: self.generate_quick_report('daily'), 
                  width=20).grid(row=0, column=0, pady=5, sticky=tk.W)
        ttk.Button(quick_frame, text="📈 Weekly Sales", command=lambda: self.generate_quick_report('weekly'), 
                  width=20).grid(row=1, column=0, pady=5, sticky=tk.W)
        ttk.Button(quick_frame, text="📅 Monthly Sales", command=lambda: self.generate_quick_report('monthly'), 
                  width=20).grid(row=2, column=0, pady=5, sticky=tk.W)
        ttk.Button(quick_frame, text="🏆 Top Products", command=lambda: self.generate_quick_report('top_products'), 
                  width=20).grid(row=3, column=0, pady=5, sticky=tk.W)
        ttk.Button(quick_frame, text="📦 Low Stock", command=self.show_low_stock_report, 
                  width=20).grid(row=4, column=0, pady=5, sticky=tk.W)
        
        # Custom Reports
        custom_frame = ttk.LabelFrame(reports_frame, text="Custom Reports", padding="15")
        custom_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))
        
        # Date range selector
        ttk.Label(custom_frame, text="Date Range:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        date_frame = ttk.Frame(custom_frame)
        date_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(date_frame, text="From:").grid(row=0, column=0)
        self.report_start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(date_frame, textvariable=self.report_start_date, width=12).grid(row=0, column=1, padx=5)
        
        ttk.Label(date_frame, text="To:").grid(row=0, column=2, padx=(10, 0))
        self.report_end_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(date_frame, textvariable=self.report_end_date, width=12).grid(row=0, column=3, padx=5)
        
        # Report type selector
        ttk.Label(custom_frame, text="Report Type:").grid(row=2, column=0, sticky=tk.W, pady=(10, 5))
        self.report_type_var = tk.StringVar(value="sales_summary")
        
        report_types = [
            ("Sales Summary", "sales_summary"),
            ("Product Performance", "product_performance"),
            ("Category Analysis", "category_analysis"),
            ("Customer Analysis", "customer_analysis"),
            ("Payment Methods", "payment_methods")
        ]
        
        for i, (label, value) in enumerate(report_types):
            ttk.Radiobutton(custom_frame, text=label, variable=self.report_type_var, 
                           value=value).grid(row=3+i, column=0, sticky=tk.W, pady=2)
        
        # Generate button
        ttk.Button(custom_frame, text="Generate Custom Report", 
                  command=self.generate_custom_report, style='Primary.TButton').grid(row=10, column=0, pady=20)
        
        # Report display area
        self.report_display_frame = ttk.LabelFrame(self.content_frame, text="Report Results", padding="10")
        self.report_display_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=20)
        self.report_display_frame.columnconfigure(0, weight=1)
        self.report_display_frame.rowconfigure(0, weight=1)
        
        # Initial message
        ttk.Label(self.report_display_frame, text="Select a report type above to generate a report", 
                 style='Heading.TLabel').grid(row=0, column=0, pady=50)
        
        self.update_status("Reports interface loaded")
        
    def generate_quick_report(self, report_type):
        """Generate a quick report"""
        try:
            # Clear report display
            for widget in self.report_display_frame.winfo_children():
                widget.destroy()
            
            # Show loading
            ttk.Label(self.report_display_frame, text="Generating report...", 
                     style='Heading.TLabel').grid(row=0, column=0, pady=20)
            self.root.update()
            
            # Generate report based on type
            if report_type == 'daily':
                self.show_daily_report()
            elif report_type == 'weekly':
                self.show_weekly_report()
            elif report_type == 'monthly':
                self.show_monthly_report()
            elif report_type == 'top_products':
                self.show_top_products_report()
            
        except Exception as e:
            # Clear and show error
            for widget in self.report_display_frame.winfo_children():
                widget.destroy()
            ttk.Label(self.report_display_frame, text=f"Error generating report: {e}", 
                     style='Error.TLabel').grid(row=0, column=0, pady=20)
            
    def show_daily_report(self):
        """Show daily sales report"""
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            # Get daily stats
            stats = self.get_daily_stats(today)

            # Generate report content as text
            report = f"DAILY SALES REPORT - {today}\n"
            report += "=" * 80 + "\n\n"
            report += "SUMMARY:\n"
            report += "-" * 80 + "\n"
            report += f"Total Sales:       £{stats.get('total_sales', 0):.2f}\n"
            report += f"Transactions:      {stats.get('transaction_count', 0)}\n"
            report += f"Average Order:     £{stats.get('avg_order', 0):.2f}\n"
            report += f"Items Sold:        {stats.get('items_sold', 0)}\n\n"

            # Top products today
            if stats.get('top_products'):
                report += "TOP PRODUCTS TODAY:\n"
                report += "-" * 80 + "\n"
                for i, product in enumerate(stats['top_products'][:5], 1):
                    report += f"{i}. {product['name']:<40} {product['quantity']:>5} sold\n"
                report += "\n"

            report += "=" * 80 + "\n"

            # Show in new window with export/email buttons
            self.show_report_window(f"Daily Sales Report - {today}", report)

        except Exception as e:
            messagebox.showerror("Report Error", f"Error loading daily report:\n{str(e)}")
            
    def get_daily_stats(self, date):
        """Get daily sales statistics"""
        try:
            
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Basic stats
            cursor.execute("""
                SELECT COUNT(*) as transaction_count, 
                       SUM(total_amount) as total_sales,
                       AVG(total_amount) as avg_order
                FROM shop_transactions
                WHERE DATE(transaction_date) = ?
            """, [date])
            
            basic_stats = cursor.fetchone()
            
            # Items sold
            cursor.execute("""
                SELECT SUM(ti.quantity) as items_sold
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE DATE(t.transaction_date) = ?
            """, [date])
            
            items_result = cursor.fetchone()
            
            # Top products
            cursor.execute("""
                SELECT p.name, SUM(ti.quantity) as quantity
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                JOIN shop_products p ON ti.product_id = p.product_id
                WHERE DATE(t.transaction_date) = ?
                GROUP BY p.product_id
                ORDER BY quantity DESC
                LIMIT 5
            """, [date])
            
            top_products = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_sales': basic_stats['total_sales'] or 0,
                'transaction_count': basic_stats['transaction_count'] or 0,
                'avg_order': basic_stats['avg_order'] or 0,
                'items_sold': items_result['items_sold'] or 0,
                'top_products': [dict(product) for product in top_products]
            }
            
        except Exception as e:
            return {'error': str(e)}
            
    def show_low_stock_report(self):
        """Show low stock report"""
        try:
            # Get low stock items
            low_stock_items = self.get_low_stock_items()

            if not low_stock_items:
                messagebox.showinfo("Low Stock Report",
                                  "✅ All products are adequately stocked!")
                return

            # Generate report content as text
            report = "LOW STOCK REPORT\n"
            report += "=" * 80 + "\n\n"

            critical_count = len([item for item in low_stock_items if item['quantity'] == 0])
            urgent_count = len([item for item in low_stock_items if 0 < item['quantity'] <= item['restock_threshold']])

            report += f"⚠️ {len(low_stock_items)} products need attention\n"
            if critical_count > 0:
                report += f"🔴 {critical_count} products are OUT OF STOCK\n"
            if urgent_count > 0:
                report += f"🟡 {urgent_count} products need immediate restocking\n"
            report += "\n"

            report += f"{'Product ID':<15} {'Name':<30} {'Category':<15} {'Stock':<8} {'Threshold':<10} {'Action':<15}\n"
            report += "-" * 80 + "\n"

            for item in low_stock_items:
                if item['quantity'] == 0:
                    action = "OUT OF STOCK"
                elif item['quantity'] <= item['restock_threshold']:
                    action = "RESTOCK NOW"
                else:
                    action = "Monitor"

                report += f"{item['product_id']:<15} {item['name']:<30} {item['category']:<15} {item['quantity']:<8} {item['restock_threshold']:<10} {action:<15}\n"

            report += "\n" + "=" * 80 + "\n"

            # Show in new window with export/email buttons
            self.show_report_window("Low Stock Report", report)

        except Exception as e:
            messagebox.showerror("Report Error", f"Error loading low stock report:\n{str(e)}")
            
    def get_low_stock_items(self):
        """Get list of low stock items"""
        try:
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold * 1.2
                ORDER BY (i.quantity * 1.0 / i.restock_threshold), p.name
            """)
            
            items = cursor.fetchall()
            conn.close()
            
            return [dict(item) for item in items]
            
        except Exception as e:
            return []
            
    def export_transactions(self):
        """Export transactions to CSV"""
        try:
            # Get date range
            start_date = self.trans_start_date.get()
            end_date = self.trans_end_date.get()
            
            # Ask for file location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Transactions"
            )
            
            if not filename:
                return
            
            if 'get_connection' not in globals():
                messagebox.showwarning("Warning", "Database not available for export")
                return
            
            # Get transaction data
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.transaction_id, t.transaction_date, u.username, u.email,
                       t.total_amount, t.payment_method, t.status, t.notes
                FROM shop_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                ORDER BY t.transaction_date DESC
            """, [start_date, end_date])
            
            transactions = cursor.fetchall()
            conn.close()
            
            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header
                writer.writerow(['Transaction ID', 'Date', 'Customer', 'Email', 'Total', 'Payment Method', 'Status', 'Notes'])
                
                # Data
                for trans in transactions:
                    writer.writerow([
                        trans['transaction_id'],
                        trans['transaction_date'],
                        trans['username'] or 'Unknown',
                        trans['email'] or '',
                        trans['total_amount'],
                        trans['payment_method'],
                        trans['status'],
                        trans['notes'] or ''
                    ])
            
            messagebox.showinfo("Success", f"Transactions exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export transactions: {e}")
            
    def update_status(self, message):
        """Update the status bar"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def show_progress(self):
        """Show progress bar"""
        self.progress_bar.grid()
        
    def hide_progress(self):
        """Hide progress bar"""
        self.progress_bar.grid_remove()
        
    # Additional utility functions for CLI compatibility
    def get_cli_functions(self):
        """Return a dictionary of CLI functions for backward compatibility"""
        cli_functions = {}
        
        # Try to import all original CLI functions
        try:
            if 'browse_products' in globals():
                cli_functions['browse_products'] = browse_products
            if 'add_to_shopping_cart' in globals():
                cli_functions['add_to_shopping_cart'] = add_to_shopping_cart
            if 'checkout_process' in globals():
                cli_functions['checkout_process'] = checkout_process
            if 'view_purchase_history' in globals():
                cli_functions['view_purchase_history'] = view_purchase_history
            if 'display_product_management_menu' in globals():
                cli_functions['display_product_management_menu'] = display_product_management_menu
            if 'generate_sales_reports' in globals():
                cli_functions['generate_sales_reports'] = generate_sales_reports
            # Add more as needed
        except Exception as e:
            print(f"Note: Some CLI functions not available: {e}")
        
        return cli_functions
        
    def call_cli_function(self, function_name, *args, **kwargs):
        """Call a CLI function programmatically"""
        cli_functions = self.get_cli_functions()
        
        if function_name in cli_functions:
            try:
                return cli_functions[function_name](*args, **kwargs)
            except Exception as e:
                raise Exception(f"CLI function error: {e}")
        else:
            raise Exception(f"CLI function '{function_name}' not available")

    def _process_student_account_payment(self, student_id, total_amount, transaction_id, customer_name):
        """Process payment through student's finance account"""
        try:
            # Get student details
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", f"Student ID {student_id} not found in system")
                conn.close()
                return False

            first_name, last_name, email = student_result

            # Add charge to student's finance account
            fee_id = f"SHOP_{transaction_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO student_fees
                (fee_id, student_id, fee_type, amount, due_date, description, paid_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fee_id, student_id, 'Shop Purchase', total_amount, current_date,
                f'Shop purchase #{transaction_id} for {first_name} {last_name}', 'Paid', current_date
            ))

            # Record payment
            try:
                payment_id = f"PAY_{fee_id}"
                cursor.execute('''
                    INSERT INTO payments
                    (payment_id, student_id, amount, payment_method, payment_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payment_id, student_id, total_amount, 'Student Account', current_date, 'completed',
                    f'Shop payment for transaction #{transaction_id}'
                ))
            except sqlite3.Error:
                # Payments table might not exist, continue anyway
                pass

            conn.commit()
            conn.close()

            print(f"Shop payment of £{total_amount:.2f} charged to {first_name} {last_name}'s student account")
            return True

        except Exception as e:
            print(f"Failed to process student account payment: {e}")
            return False

    def _send_shop_order_confirmation_email(self, transaction_id, customer_name, customer_email, total_amount, payment_method):
        """Send order confirmation email to customer"""
        try:
            if not customer_email:
                return

            from university_system.infrastructure.email.template_utils import render_template

            # Get order items for the email
            items_text = ""
            for item in self.cart_items:
                items_text += f"• {item['name']} x {item['quantity']} - £{item['subtotal']:.2f}\n"

            payment_text = ""
            if payment_method == "Student Account":
                payment_text = "Your order has been charged to your student account."
            else:
                payment_text = f"Payment processed via {payment_method}."

            subject, message = render_template('shop_order_confirmation', {
                'customer_name': customer_name,
                'transaction_id': transaction_id,
                'items_text': items_text,
                'total_amount': f'{total_amount:.2f}',
                'payment_method': payment_method,
                'signature': 'University Shop Team'
            })

            if not (subject and message):
                print("Failed to load shop order confirmation template")
                return

            # Try to send via email GUI
            success = self._send_email_via_gui(customer_email, subject, message)

            if success:
                print(f"Shop order confirmation sent to {customer_name} ({customer_email})")
            else:
                # Fallback: show email details
                self._show_shop_email_fallback(customer_name, customer_email, subject, message)

        except Exception as e:
            print(f"Failed to send shop order confirmation email: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            from university_system.infrastructure.database.db import DEFAULT_DB_PATH
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI
            email_gui = EmailGUI(self.root, None)  # May need auth parameter
            email_gui.send_email(to_email=to_email, subject=subject, message=message)
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_shop_email_fallback(self, customer_name, email, subject, message):
        """Show fallback dialog for shop email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title("Shop Order Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Shop order confirmation for {customer_name} - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show shop email fallback: {e}")

    def open_finance_gui_for_payment(self, transaction_id=None, amount=None):
        """Open finance GUI for payment processing"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI

            finance_window = tk.Toplevel(self.root)
            finance_window.title("Finance System - Shop Payment")
            finance_window.geometry("1000x700")

            # Initialize finance GUI
            finance_gui = FinanceGUI(finance_window, auth=self.auth if hasattr(self, 'auth') else None)

            # Pre-populate shop payment information if methods exist
            if transaction_id and amount and hasattr(finance_gui, 'prepopulate_shop_payment'):
                finance_gui.prepopulate_shop_payment(transaction_id, amount)

            messagebox.showinfo("Finance System", "Finance system opened for payment processing")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def add_finance_payment_option_to_checkout(self):
        """Add finance system option to checkout dialog"""
        try:
            # This method can be enhanced to add a "Finance System" button to checkout
            # For now, the existing Student Account payment already integrates with finance
            pass
        except Exception as e:
            print(f"Could not add finance payment option: {e}")

# Backward compatibility functions
def run_gui_mode():
    """Run the GUI version of the shop system"""
    root = tk.Tk()
    app = UniversityShopGUI(root)
    root.mainloop()

def run_cli_mode():
    """Run the original CLI version (if available)"""
    try:
        if 'display_shop_menu' in globals():
            display_shop_menu()
        else:
            print("CLI mode not available. Please ensure shop_management.py is properly imported.")
    except Exception as e:
        print(f"Error running CLI mode: {e}")

# Main execution
if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        run_cli_mode()
    else:
        run_gui_mode()

# Integration function for main.py
def integrate_gui_with_main():
    """
    Integration function to be called from main.py
    This allows the GUI to be launched from the main system
    """
    def launch_shop_gui():
        """Launch the shop GUI"""
        try:
            root = tk.Tk()
            app = UniversityShopGUI(root)
            root.mainloop()
        except Exception as e:
            print(f"Error launching shop GUI: {e}")
    
    return launch_shop_gui


class DiscountEditDialog:
    def __init__(self, parent, discount_id=None):
        self.dialog = tk.Toplevel(parent)
        self.discount_id = discount_id
        self.result = False

        title = "Edit Discount" if discount_id else "Create New Discount"
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if discount_id:
            self.load_discount_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Discount name
        ttk.Label(main_frame, text="Discount Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor=tk.W)
        self.description_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.description_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Discount type
        ttk.Label(main_frame, text="Discount Type:").pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="percentage")
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(type_frame, text="Percentage (%)", variable=self.type_var, value="percentage").pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text="Fixed Amount (£)", variable=self.type_var, value="fixed").pack(side=tk.LEFT, padx=(20, 0))

        # Discount value
        ttk.Label(main_frame, text="Discount Value:").pack(anchor=tk.W)
        self.value_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.value_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Start date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD, optional):").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # End date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD, optional):").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Minimum purchase amount
        ttk.Label(main_frame, text="Minimum Purchase Amount (£):").pack(anchor=tk.W)
        self.min_purchase_var = tk.StringVar(value="0")
        ttk.Entry(main_frame, textvariable=self.min_purchase_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Applicable products
        ttk.Label(main_frame, text="Applicable Products (comma-separated IDs, leave empty for all):").pack(anchor=tk.W)
        self.products_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.products_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Active status
        self.active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Active", variable=self.active_var).pack(anchor=tk.W, pady=(0, 20))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Save", command=self.save_discount).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_discount_data(self):
        """Load existing discount data"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM shop_discounts WHERE discount_id = ?', (self.discount_id,))
            discount = cursor.fetchone()

            if discount:
                self.name_var.set(discount['name'])
                self.description_var.set(discount['description'] or '')
                self.type_var.set(discount['discount_type'])
                self.value_var.set(str(discount['discount_value']))
                self.start_date_var.set(discount['start_date'] or '')
                self.end_date_var.set(discount['end_date'] or '')
                self.min_purchase_var.set(str(discount['min_purchase_amount']))
                self.products_var.set(discount['applicable_products'] or '')
                self.active_var.set(bool(discount['is_active']))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load discount: {str(e)}")

    def save_discount(self):
        """Save the discount"""
        name = self.name_var.get().strip()
        description = self.description_var.get().strip()
        discount_type = self.type_var.get()
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()
        products = self.products_var.get().strip()

        if not name:
            messagebox.showerror("Validation Error", "Discount name is required.")
            return

        try:
            discount_value = float(self.value_var.get())
            min_purchase = float(self.min_purchase_var.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Discount value and minimum purchase must be valid numbers.")
            return

        if discount_type == 'percentage' and (discount_value < 0 or discount_value > 100):
            messagebox.showerror("Validation Error", "Percentage discount must be between 0 and 100.")
            return

        if discount_value < 0:
            messagebox.showerror("Validation Error", "Discount value cannot be negative.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if self.discount_id:
                # Update existing discount
                cursor.execute('''
                    UPDATE shop_discounts
                    SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                        start_date = ?, end_date = ?, is_active = ?, applicable_products = ?,
                        min_purchase_amount = ?
                    WHERE discount_id = ?
                ''', (name, description, discount_type, discount_value, start_date or None,
                     end_date or None, self.active_var.get(), products or None, min_purchase, self.discount_id))
            else:
                # Create new discount
                # Generate discount ID
                cursor.execute("SELECT MAX(SUBSTR(discount_id, 2)) FROM shop_discounts WHERE discount_id LIKE 'D%'")
                result = cursor.fetchone()

                try:
                    if result[0]:
                        next_id = int(result[0]) + 1
                    else:
                        next_id = 1
                    discount_id = f"D{next_id:03d}"
                except (ValueError, TypeError):
                    discount_id = f"D{int(time.time())}"

                cursor.execute('''
                    INSERT INTO shop_discounts
                    (discount_id, name, description, discount_type, discount_value, start_date,
                     end_date, is_active, applicable_products, min_purchase_amount, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (discount_id, name, description, discount_type, discount_value, start_date or None,
                     end_date or None, self.active_var.get(), products or None, min_purchase,
                     datetime.now().isoformat()))

            conn.commit()
            conn.close()

            action = "updated" if self.discount_id else "created"
            messagebox.showinfo("Success", f"Discount {action} successfully.")
            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save discount: {str(e)}")


# Export important classes and functions for external use
__all__ = [
    'UniversityShopGUI',
    'DiscountEditDialog',
    'run_gui_mode',
    'run_cli_mode',
    'integrate_gui_with_main'
]
