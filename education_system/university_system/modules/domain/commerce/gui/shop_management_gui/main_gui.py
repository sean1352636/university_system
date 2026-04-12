import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.core.sql_safety import escape_like
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.university_system.modules.domain.commerce.services.shop_management import (
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
        # If running standalone, we'll define the essential fallback functions
        def get_customer_analytics():
            return None

        def get_inventory_valuation():
            return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

        def print_product_labels(product_ids=None):
            print("Label printing functionality not available")

        # Note: get_low_stock_items is implemented as a class method in UniversityShopGUI

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

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

# Initialize logger
logger = logging.getLogger(__name__)


class UniversityShopGUI:
    """Main University Shop GUI Application"""

    def __init__(self, root, auth=None):
        """
        Initialize University Shop GUI.

        Args:
            root: Tkinter root window
            auth: Authentication instance (if None, will use get_auth())

        Raises:
            RuntimeError: If authentication system is not available
        """
        # Initialize i18n for language support
        init_i18n()

        self.root = root

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("common.error"),
                _t("university_shop.error.auth_not_available")
            )
            root.destroy()
            return

        # Don't set title and geometry if this is a Toplevel window (integrated mode)
        if not isinstance(root, tk.Toplevel):
            self.root.title(_t("university_shop.title"))
            self.root.geometry("1200x800")
            self.root.minsize(1000, 600)

        # Configure style
        self.setup_styles()

        # Initialize variables
        self.current_user = None
        self.cart_items = []
        self.content_frame = None  # Set by _bind_sidebar_scroll_events in create_widgets
        self.status_label = None   # Set by _bind_sidebar_scroll_events in create_widgets

        # Initialize the original CLI system
        self.initialize_backend()

        # Create GUI components
        self.create_widgets()

        # Check if user is already authenticated via central auth system
        self.setup_current_user()

        # SECURITY: Require central authentication - no standalone login
        if not self.current_user:
            messagebox.showerror(
                _t("shop_management.auth_required"),
                _t("shop_management.auth_required_detail")
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
                        "permissions": auth_user.get('permissions', []),
                        "student_id": auth_user.get('student_id'),
                        "id": auth_user.get('id'),
                        "email": auth_user.get('email')
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "student_id": getattr(auth_user, 'student_id', None),
                        "id": getattr(auth_user, 'id', None),
                        "email": getattr(auth_user, 'email', None)
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
            # Initialise textbook tables
            if hasattr(self, 'init_textbook_db'):
                self.init_textbook_db()

            # Initialize centralized authentication system
            if self.auth is None:  # Only create if not passed from parent
                self.auth = get_auth()
                if self.auth is None:
                    self.auth = UserAuth()

        except Exception as e:
            messagebox.showerror(
                _t("shop_management.init_error"),
                f"{_t('shop_management.init_failed')}: {e}"
            )


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
        self.title_label = ttk.Label(self.header_frame, text=_t("university_shop.header_title"),
                               style='Title.TLabel')
        self.title_label.grid(row=0, column=0, sticky=tk.W)

        # User info and logout
        self.user_frame = ttk.Frame(self.header_frame)
        self.user_frame.grid(row=0, column=1, sticky=tk.E)

        self.user_label = ttk.Label(self.user_frame, text=_t("university_shop.not_logged_in"))
        self.user_label.grid(row=0, column=0, padx=(0, 10))

        self.logout_btn = ttk.Button(self.user_frame, text=_t("common.return_to_main_menu"), command=self.return_to_main_menu)
        self.logout_btn.grid(row=0, column=1)
        self.logout_btn.configure(state='disabled')

        self.header_frame.columnconfigure(1, weight=1)

        # Create scrollable sidebar for navigation
        sidebar_container = ttk.LabelFrame(self.main_frame, text=_t("shop_management.navigation"), padding="5")
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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
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
        ttk.Label(
            self.sidebar_frame,
            text=_t("shop_management.sections.shopping"),
            style='Heading.TLabel'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        ttk.Button(
            self.sidebar_frame, text="🏠 " + _t("shop_management.buttons.dashboard"),
            command=self.show_dashboard, width=20
        ).grid(row=1, column=0, sticky=tk.W, pady=2)

        ttk.Button(
            self.sidebar_frame, text="🛍️ " + _t("shop_management.buttons.browse_products"),
            command=self.show_browse_products, width=20
        ).grid(row=2, column=0, sticky=tk.W, pady=2)

        ttk.Button(
            self.sidebar_frame, text="🛒 " + _t("shop_management.buttons.shopping_cart"),
            command=self.show_shopping_cart, width=20
        ).grid(row=3, column=0, sticky=tk.W, pady=2)

        ttk.Button(
            self.sidebar_frame, text="📋 " + _t("shop_management.buttons.order_history"),
            command=self.show_order_history, width=20
        ).grid(row=4, column=0, sticky=tk.W, pady=2)

        row_counter = 5

        # Textbooks section (available to all)
        ttk.Separator(self.sidebar_frame, orient='horizontal').grid(
            row=row_counter, column=0, sticky=(tk.W, tk.E), pady=10
        )
        row_counter += 1

        ttk.Label(
            self.sidebar_frame, text="Textbooks",
            style='Heading.TLabel'
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=(0, 5))
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="Browse Textbooks",
            command=self.show_textbooks_browse, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="Used Book Exchange",
            command=self.show_textbooks_exchange, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="Sell a Book",
            command=self.show_textbooks_sell, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="Textbook Orders",
            command=self.show_textbooks_orders, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        # Admin/Staff management options
        if is_admin or is_staff:
            ttk.Separator(self.sidebar_frame, orient='horizontal').grid(
                row=row_counter, column=0, sticky=(tk.W, tk.E), pady=10
            )
            row_counter += 1

            ttk.Label(
                self.sidebar_frame,
                text=_t("shop_management.sections.management"),
                style='Heading.TLabel'
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=(0, 5))
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="📦 " + _t("shop_management.buttons.manage_products"),
                command=self.show_manage_products, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="📊 " + _t("shop_management.buttons.inventory"),
                command=self.show_manage_inventory, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="💰 " + _t("shop_management.buttons.transactions"),
                command=self.show_all_transactions, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="💸 Refunds",
                command=self.show_refunds, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="🎯 " + _t("shop_management.buttons.discounts"),
                command=self.show_manage_discounts, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="📈 " + _t("shop_management.buttons.reports"),
                command=self.show_reports, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="📊 " + _t("shop_management.buttons.analytics"),
                command=self.show_analytics_dashboard, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

            ttk.Button(
                self.sidebar_frame, text="🏷️ " + _t("shop_management.buttons.print_labels"),
                command=self.show_print_labels_dialog, width=20
            ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
            row_counter += 1

        # Utility options
        ttk.Separator(self.sidebar_frame, orient='horizontal').grid(
            row=row_counter, column=0, sticky=(tk.W, tk.E), pady=10
        )
        row_counter += 1

        ttk.Label(
            self.sidebar_frame,
            text=_t("shop_management.sections.utilities"),
            style='Heading.TLabel'
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=(0, 5))
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="🖥️ " + _t("shop_management.buttons.cli_mode"),
            command=self.launch_cli_mode, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)
        row_counter += 1

        ttk.Button(
            self.sidebar_frame, text="ℹ️ " + _t("shop_management.buttons.about"),
            command=self.show_about, width=20
        ).grid(row=row_counter, column=0, sticky=tk.W, pady=2)

        # Force scroll region update after all content is added
        self.sidebar_frame.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

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

            cli_text = tk.Text(
                cli_frame,
                wrap=tk.WORD,
                state='disabled',
                bg='black',
                fg='green',
                font=('Consolas', 10)
            )
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
            cli_text.insert(tk.END, "To use the full CLI interface, run from project root:\n")
            cli_text.insert(tk.END, "python -m education_system.university_system.modules.domain.commerce.services.shop_management\n\n")
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

                    # Find project root (parent of education_system/)
                    current_file = os.path.abspath(__file__)
                    # Navigate up 8 levels: shop_management_gui -> gui -> commerce -> domain -> modules -> university_system -> education_system -> project_root
                    project_root = current_file
                    for _ in range(8):
                        project_root = os.path.dirname(project_root)

                    # Set up environment with PYTHONPATH
                    env = os.environ.copy()
                    env['PYTHONPATH'] = project_root

                    # Launch as module to avoid import issues
                    subprocess.Popen(
                        [sys.executable, "-m", "education_system.university_system.modules.domain.commerce.services.shop_management"],
                        cwd=project_root,
                        env=env
                    )
                    messagebox.showinfo(
                        "CLI Launched",
                        "Shop Management CLI launched in separate process.\n"
                        "Check your terminal for the CLI interface."
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to launch CLI: {e}")

            ttk.Button(
                button_frame,
                text="Launch External CLI",
                command=launch_external_cli
            ).grid(row=0, column=0, padx=5)

            ttk.Button(
                button_frame,
                text="Close",
                command=cli_window.destroy
            ).grid(row=0, column=1, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch CLI mode: {e}")


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


# Import and bind methods from manager modules to UniversityShopGUI class
# This allows the refactored functions to be called as instance methods
try:
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import dashboard_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import product_browser
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import product_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import cart_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import checkout_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import order_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import inventory_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import discount_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import refund_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import report_manager
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import bulk_operations
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import utils
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import ui_components
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui import textbook_manager

    # Bind dashboard methods
    if hasattr(dashboard_manager, 'show_dashboard'):
        UniversityShopGUI.show_dashboard = dashboard_manager.show_dashboard
    if hasattr(dashboard_manager, 'create_stat_card'):
        UniversityShopGUI.create_stat_card = dashboard_manager.create_stat_card
    if hasattr(dashboard_manager, 'get_dashboard_stats'):
        UniversityShopGUI.get_dashboard_stats = dashboard_manager.get_dashboard_stats
    if hasattr(dashboard_manager, 'show_analytics_dashboard'):
        UniversityShopGUI.show_analytics_dashboard = dashboard_manager.show_analytics_dashboard
    if hasattr(dashboard_manager, 'show_customer_analytics'):
        UniversityShopGUI.show_customer_analytics = dashboard_manager.show_customer_analytics
    if hasattr(dashboard_manager, 'show_club_merchandise_selection'):
        UniversityShopGUI.show_club_merchandise_selection = dashboard_manager.show_club_merchandise_selection
    if hasattr(dashboard_manager, 'get_monthly_stats'):
        UniversityShopGUI.get_monthly_stats = dashboard_manager.get_monthly_stats
    if hasattr(dashboard_manager, 'get_weekly_stats'):
        UniversityShopGUI.get_weekly_stats = dashboard_manager.get_weekly_stats
    if hasattr(dashboard_manager, 'get_daily_stats'):
        UniversityShopGUI.get_daily_stats = dashboard_manager.get_daily_stats
    if hasattr(dashboard_manager, 'update_status'):
        UniversityShopGUI.update_status = dashboard_manager.update_status
    if hasattr(dashboard_manager, 'show_low_stock_report'):
        UniversityShopGUI.show_low_stock_report = dashboard_manager.show_low_stock_report
    if hasattr(dashboard_manager, 'toggle_discount_status'):
        UniversityShopGUI.toggle_discount_status = dashboard_manager.toggle_discount_status
    if hasattr(dashboard_manager, 'toggle_product_status'):
        UniversityShopGUI.toggle_product_status = dashboard_manager.toggle_product_status

    # Bind product browser methods
    if hasattr(product_browser, 'show_browse_products'):
        UniversityShopGUI.show_browse_products = product_browser.show_browse_products
    if hasattr(product_browser, 'search_products'):
        UniversityShopGUI.search_products = product_browser.search_products
    if hasattr(product_browser, 'view_product_details'):
        UniversityShopGUI.view_product_details = product_browser.view_product_details
    if hasattr(product_browser, 'apply_filters'):
        UniversityShopGUI.apply_filters = product_browser.apply_filters
    if hasattr(product_browser, 'refresh_products'):
        UniversityShopGUI.refresh_products = product_browser.refresh_products
    if hasattr(product_browser, 'on_product_double_click'):
        UniversityShopGUI.on_product_double_click = product_browser.on_product_double_click
    if hasattr(product_browser, 'get_product_details'):
        UniversityShopGUI.get_product_details = product_browser.get_product_details

    # Bind product manager methods
    if hasattr(product_manager, 'show_manage_products'):
        UniversityShopGUI.show_manage_products = product_manager.show_manage_products
    if hasattr(product_manager, 'show_add_product_dialog'):
        UniversityShopGUI.show_add_product_dialog = product_manager.show_add_product_dialog
    if hasattr(product_manager, 'create_product'):
        UniversityShopGUI.create_product = product_manager.create_product
    if hasattr(product_manager, 'update_product'):
        UniversityShopGUI.update_product = product_manager.update_product
    if hasattr(product_manager, 'delete_product'):
        UniversityShopGUI.delete_product = product_manager.delete_product
    if hasattr(product_manager, 'create_product_context_menu'):
        UniversityShopGUI.create_product_context_menu = product_manager.create_product_context_menu
    if hasattr(product_manager, 'create_mgmt_context_menu'):
        UniversityShopGUI.create_mgmt_context_menu = product_manager.create_mgmt_context_menu
    if hasattr(product_manager, 'show_mgmt_context_menu'):
        UniversityShopGUI.show_mgmt_context_menu = product_manager.show_mgmt_context_menu
    if hasattr(product_manager, 'load_products_for_management'):
        UniversityShopGUI.load_products_for_management = product_manager.load_products_for_management
    if hasattr(product_manager, 'show_quick_add_product_dialog'):
        UniversityShopGUI.show_quick_add_product_dialog = product_manager.show_quick_add_product_dialog

    # Bind cart methods
    if hasattr(cart_manager, 'show_shopping_cart'):
        UniversityShopGUI.show_shopping_cart = cart_manager.show_shopping_cart
    if hasattr(cart_manager, 'add_to_cart'):
        UniversityShopGUI.add_to_cart = cart_manager.add_to_cart
    if hasattr(cart_manager, 'add_selected_to_cart'):
        UniversityShopGUI.add_selected_to_cart = cart_manager.add_selected_to_cart
    if hasattr(cart_manager, 'update_cart_quantity'):
        UniversityShopGUI.update_cart_quantity = cart_manager.update_cart_quantity
    if hasattr(cart_manager, 'remove_cart_item'):
        UniversityShopGUI.remove_cart_item = cart_manager.remove_cart_item
    if hasattr(cart_manager, 'clear_cart'):
        UniversityShopGUI.clear_cart = cart_manager.clear_cart

    # Bind checkout methods
    if hasattr(checkout_manager, 'show_checkout'):
        UniversityShopGUI.show_checkout = checkout_manager.show_checkout
    if hasattr(checkout_manager, 'process_checkout'):
        UniversityShopGUI.process_checkout = checkout_manager.process_checkout
    if hasattr(checkout_manager, 'show_payment_methods_report'):
        UniversityShopGUI.show_payment_methods_report = checkout_manager.show_payment_methods_report
    if hasattr(checkout_manager, 'get_payment_methods_data'):
        UniversityShopGUI.get_payment_methods_data = checkout_manager.get_payment_methods_data
    if hasattr(checkout_manager, 'open_finance_gui_for_payment'):
        UniversityShopGUI.open_finance_gui_for_payment = checkout_manager.open_finance_gui_for_payment

    # Bind order methods
    if hasattr(order_manager, 'show_order_history'):
        UniversityShopGUI.show_order_history = order_manager.show_order_history
    if hasattr(order_manager, 'load_order_history'):
        UniversityShopGUI.load_order_history = order_manager.load_order_history
    if hasattr(order_manager, 'view_order_details'):
        UniversityShopGUI.view_order_details = order_manager.view_order_details
    if hasattr(order_manager, 'get_order_details'):
        UniversityShopGUI.get_order_details = order_manager.get_order_details
    if hasattr(order_manager, 'show_all_transactions'):
        UniversityShopGUI.show_all_transactions = order_manager.show_all_transactions
    if hasattr(order_manager, 'load_transactions'):
        UniversityShopGUI.load_transactions = order_manager.load_transactions
    if hasattr(order_manager, 'export_transactions'):
        UniversityShopGUI.export_transactions = order_manager.export_transactions
    if hasattr(order_manager, 'view_refund_transaction_details'):
        UniversityShopGUI.view_refund_transaction_details = order_manager.view_refund_transaction_details
    if hasattr(order_manager, 'view_transaction_details'):
        UniversityShopGUI.view_transaction_details = order_manager.view_transaction_details

    # Bind inventory methods
    if hasattr(inventory_manager, 'show_manage_inventory'):
        UniversityShopGUI.show_manage_inventory = inventory_manager.show_manage_inventory
    if hasattr(inventory_manager, 'bulk_restock'):
        UniversityShopGUI.bulk_restock = inventory_manager.bulk_restock
    if hasattr(inventory_manager, 'set_restock_threshold'):
        UniversityShopGUI.set_restock_threshold = inventory_manager.set_restock_threshold
    if hasattr(inventory_manager, 'restock_selected_item'):
        UniversityShopGUI.restock_selected_item = inventory_manager.restock_selected_item
    if hasattr(inventory_manager, 'update_selected_stock'):
        UniversityShopGUI.update_selected_stock = inventory_manager.update_selected_stock
    if hasattr(inventory_manager, 'load_inventory_data'):
        UniversityShopGUI.load_inventory_data = inventory_manager.load_inventory_data

    # Bind discount methods
    if hasattr(discount_manager, 'show_manage_discounts'):
        UniversityShopGUI.show_manage_discounts = discount_manager.show_manage_discounts
    if hasattr(discount_manager, 'load_discounts'):
        UniversityShopGUI.load_discounts = discount_manager.load_discounts
    if hasattr(discount_manager, 'create_new_discount'):
        UniversityShopGUI.create_new_discount = discount_manager.create_new_discount
    if hasattr(discount_manager, 'edit_selected_discount'):
        UniversityShopGUI.edit_selected_discount = discount_manager.edit_selected_discount
    if hasattr(discount_manager, 'cleanup_expired_discounts'):
        UniversityShopGUI.cleanup_expired_discounts = discount_manager.cleanup_expired_discounts

    # Bind refund methods
    if hasattr(refund_manager, 'show_refunds'):
        UniversityShopGUI.show_refunds = refund_manager.show_refunds
    if hasattr(refund_manager, 'refresh_refunds_list'):
        UniversityShopGUI.refresh_refunds_list = refund_manager.refresh_refunds_list
    if hasattr(refund_manager, 'process_shop_refund'):
        UniversityShopGUI.process_shop_refund = refund_manager.process_shop_refund
    if hasattr(refund_manager, 'show_shop_refund_method_dialog'):
        UniversityShopGUI.show_shop_refund_method_dialog = refund_manager.show_shop_refund_method_dialog
    if hasattr(refund_manager, 'send_shop_refund_receipt'):
        UniversityShopGUI.send_shop_refund_receipt = refund_manager.send_shop_refund_receipt
    if hasattr(refund_manager, 'export_refunds_to_csv'):
        UniversityShopGUI.export_refunds_to_csv = refund_manager.export_refunds_to_csv

    # Bind report methods
    if hasattr(report_manager, 'show_reports'):
        UniversityShopGUI.show_reports = report_manager.show_reports
    if hasattr(report_manager, 'show_monthly_report'):
        UniversityShopGUI.show_monthly_report = report_manager.show_monthly_report
    if hasattr(report_manager, 'show_weekly_report'):
        UniversityShopGUI.show_weekly_report = report_manager.show_weekly_report
    if hasattr(report_manager, 'show_top_products_report'):
        UniversityShopGUI.show_top_products_report = report_manager.show_top_products_report
    if hasattr(report_manager, 'get_top_products_data'):
        UniversityShopGUI.get_top_products_data = report_manager.get_top_products_data
    if hasattr(report_manager, 'generate_custom_report'):
        UniversityShopGUI.generate_custom_report = report_manager.generate_custom_report

    # Bind bulk operation methods
    if hasattr(bulk_operations, 'show_bulk_operations'):
        UniversityShopGUI.show_bulk_operations = bulk_operations.show_bulk_operations
    if hasattr(bulk_operations, 'import_products'):
        UniversityShopGUI.import_products = bulk_operations.import_products
    if hasattr(bulk_operations, 'export_products'):
        UniversityShopGUI.export_products = bulk_operations.export_products
    if hasattr(bulk_operations, 'backup_shop_database'):
        UniversityShopGUI.backup_shop_database = bulk_operations.backup_shop_database

    # Bind utility methods
    if hasattr(utils, 'clear_content'):
        UniversityShopGUI.clear_content = utils.clear_content
    if hasattr(utils, 'load_products'):
        UniversityShopGUI.load_products = utils.load_products
    if hasattr(utils, 'show_print_labels_dialog'):
        UniversityShopGUI.show_print_labels_dialog = utils.show_print_labels_dialog
    if hasattr(utils, 'display_product_labels_gui'):
        UniversityShopGUI.display_product_labels_gui = utils.display_product_labels_gui
    if hasattr(utils, '_print_labels_to_printer'):
        UniversityShopGUI._print_labels_to_printer = utils._print_labels_to_printer
    if hasattr(utils, '_export_labels_to_pdf'):
        UniversityShopGUI._export_labels_to_pdf = utils._export_labels_to_pdf
    if hasattr(utils, '_export_labels_to_file'):
        UniversityShopGUI._export_labels_to_file = utils._export_labels_to_file
    if hasattr(utils, '_bind_sidebar_scroll_events'):
        UniversityShopGUI._bind_sidebar_scroll_events = utils._bind_sidebar_scroll_events
    if hasattr(utils, 'show_product_context_menu'):
        UniversityShopGUI.show_product_context_menu = utils.show_product_context_menu
    if hasattr(utils, 'edit_selected_product'):
        UniversityShopGUI.edit_selected_product = utils.edit_selected_product
    if hasattr(utils, 'delete_selected_product'):
        UniversityShopGUI.delete_selected_product = utils.delete_selected_product
    if hasattr(utils, 'view_product_sales'):
        UniversityShopGUI.view_product_sales = utils.view_product_sales
    if hasattr(utils, 'get_product_sales_data'):
        UniversityShopGUI.get_product_sales_data = utils.get_product_sales_data

    # Bind UI component methods
    if hasattr(ui_components, 'show_about'):
        UniversityShopGUI.show_about = ui_components.show_about
    if hasattr(ui_components, 'show_progress'):
        UniversityShopGUI.show_progress = ui_components.show_progress
    if hasattr(ui_components, 'hide_progress'):
        UniversityShopGUI.hide_progress = ui_components.hide_progress
    if hasattr(ui_components, 'update_status'):
        UniversityShopGUI.update_status = ui_components.update_status

    # Bind textbook methods
    if hasattr(textbook_manager, 'init_textbook_db'):
        UniversityShopGUI.init_textbook_db = textbook_manager.init_textbook_db
    if hasattr(textbook_manager, 'show_textbooks_browse'):
        UniversityShopGUI.show_textbooks_browse = textbook_manager.show_textbooks_browse
    if hasattr(textbook_manager, 'show_textbooks_exchange'):
        UniversityShopGUI.show_textbooks_exchange = textbook_manager.show_textbooks_exchange
    if hasattr(textbook_manager, 'show_textbooks_sell'):
        UniversityShopGUI.show_textbooks_sell = textbook_manager.show_textbooks_sell
    if hasattr(textbook_manager, 'show_textbooks_orders'):
        UniversityShopGUI.show_textbooks_orders = textbook_manager.show_textbooks_orders
    if hasattr(textbook_manager, '_tb_do_search'):
        UniversityShopGUI._tb_do_search = textbook_manager._tb_do_search
    if hasattr(textbook_manager, '_tb_load_exchange'):
        UniversityShopGUI._tb_load_exchange = textbook_manager._tb_load_exchange
    if hasattr(textbook_manager, '_tb_load_orders'):
        UniversityShopGUI._tb_load_orders = textbook_manager._tb_load_orders
    if hasattr(textbook_manager, '_tb_view_details'):
        UniversityShopGUI._tb_view_details = textbook_manager._tb_view_details
    if hasattr(textbook_manager, '_tb_find_used'):
        UniversityShopGUI._tb_find_used = textbook_manager._tb_find_used
    if hasattr(textbook_manager, '_tb_buy_used'):
        UniversityShopGUI._tb_buy_used = textbook_manager._tb_buy_used
    if hasattr(textbook_manager, '_tb_list_for_sale'):
        UniversityShopGUI._tb_list_for_sale = textbook_manager._tb_list_for_sale
    if hasattr(textbook_manager, '_get_textbook_user_id'):
        UniversityShopGUI._get_textbook_user_id = textbook_manager._get_textbook_user_id

except ImportError as e:
    print(f"Warning: Could not bind some methods from manager modules: {e}")


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

