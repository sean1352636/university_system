import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.post_18.university_system.modules.domain.commerce.services.shop_management import (
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
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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

def show_progress(self):
    """Show progress bar"""
    self.progress_bar.grid()


def hide_progress(self):
    """Hide progress bar"""
    self.progress_bar.grid_remove()

# Additional utility functions for CLI compatibility

