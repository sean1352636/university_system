import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.paths import DEFAULT_DB_PATH
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
from education_system.university_system.core.i18n import (
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


def _send_shop_order_confirmation_email(self, transaction_id, customer_name, customer_email, total_amount, payment_method):
    """Send order confirmation email to customer"""
    try:
        if not customer_email:
            return

        from education_system.university_system.infrastructure.email.template_utils import render_template

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

        # Send via email service (not GUI to avoid geometry manager conflicts)
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            send_email(customer_email, subject, message)
            print(f"Shop order confirmation sent to {customer_name} ({customer_email})")
        except Exception as email_error:
            print(f"Failed to send email via service: {email_error}")
            # Fallback: show email details
            self._show_shop_email_fallback(customer_name, customer_email, subject, message)

    except Exception as e:
        print(f"Failed to send shop order confirmation email: {e}")

# Removed _send_email_via_gui method - caused geometry manager conflicts
# Now using email service directly instead of GUI to avoid pack/grid mixing errors


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


