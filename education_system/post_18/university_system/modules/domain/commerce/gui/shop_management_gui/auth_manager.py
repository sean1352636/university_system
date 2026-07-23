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


