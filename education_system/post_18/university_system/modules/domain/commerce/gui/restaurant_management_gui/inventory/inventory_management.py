from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

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

# Import custom exceptions for proper error handling
from education_system.post_18.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def view_inventory_gui(self):
    """Display inventory in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT item_id, name, quantity, unit, cost_per_unit, reorder_level
            FROM restaurant_inventory
            ORDER BY name
        ''')
        items = cursor.fetchall()

        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)

        for item in items:
            cost_str = f"£{item[4]:.2f}" if item[4] else "N/A"
            reorder_str = f"{item[5]:.1f}" if item[5] else "N/A"

            self.inventory_tree.insert('', 'end', values=(
                item[0], item[1], f"{item[2]:.1f}", item[3], cost_str, reorder_str
            ))

        conn.close()
        messagebox.showinfo("Success", f"Loaded {len(items)} inventory items")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load inventory: {str(e)}")


def inventory_transactions(self):
    """Display detailed inventory transaction log"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Create transactions table if doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                transaction_type TEXT,
                quantity REAL,
                transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                notes TEXT
            )
        ''')
        conn.commit()
        # Get recent transactions
        cursor.execute('''
            SELECT t.transaction_id, t.item_id, i.name, t.transaction_type,
                   t.quantity, t.transaction_date, t.notes
            FROM inventory_transactions t
            LEFT JOIN restaurant_inventory i ON t.item_id = i.item_id
            ORDER BY t.transaction_date DESC
            LIMIT 100
        ''')
        transactions = cursor.fetchall()
        conn.close()
        # Display transactions
        trans_dialog = tk.Toplevel(self.root)
        trans_dialog.title("Inventory Transactions Log")
        trans_dialog.geometry("1000x600")
        trans_dialog.transient(self.root)
        main_frame = ttk.Frame(trans_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Inventory Transactions Log (Last 100)",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Create treeview
        columns = ('Trans ID', 'Item ID', 'Item Name', 'Type', 'Quantity', 'Date', 'Notes')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=25)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        for trans in transactions:
            tree.insert('', 'end', values=trans)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Button(main_frame, text="Close",
                  command=trans_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load transactions:\n{str(e)}")

def low_stock_alerts(self):
    """Show automated low stock alerts"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get low stock items
        cursor.execute('''
            SELECT item_id, name, quantity, reorder_level, unit
            FROM restaurant_inventory
            WHERE quantity <= reorder_level
            ORDER BY (quantity / NULLIF(reorder_level, 0))
        ''')
        low_stock = cursor.fetchall()
        conn.close()
        # Display alerts
        alerts_dialog = tk.Toplevel(self.root)
        alerts_dialog.title("Low Stock Alerts")
        alerts_dialog.geometry("700x500")
        alerts_dialog.transient(self.root)
        main_frame = ttk.Frame(alerts_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        if not low_stock:
            ttk.Label(main_frame, text="✓ No Low Stock Alerts",
                     font=('Arial', 14, 'bold'), foreground='green').pack(pady=20)
            ttk.Label(main_frame, text="All inventory levels are adequate.",
                     font=('Arial', 12)).pack(pady=10)
        else:
            ttk.Label(main_frame, text=f"⚠ {len(low_stock)} Low Stock Alerts",
                     font=('Arial', 14, 'bold'), foreground='orange').pack(pady=20)
            # Create treeview for alerts
            columns = ('Item ID', 'Item Name', 'Current Qty', 'Reorder Level', 'Status')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)
            for item_id, name, qty, reorder, unit in low_stock:
                status = "CRITICAL" if qty < (reorder * 0.5) else "LOW"
                tree.insert('', 'end', values=(item_id, name, f"{qty:.1f} {unit}",
                                              f"{reorder:.1f} {unit}", status),
                           tags=(status,))
            # Color code by status
            tree.tag_configure('CRITICAL', background='#ffcccc')
            tree.tag_configure('LOW', background='#ffffcc')
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            def send_alert_email():
                messagebox.showinfo("Email Alert",
                                   "Low stock alert email would be sent to procurement team.\n\n" +
                                   f"{len(low_stock)} items require reordering.")
            ttk.Button(button_frame, text="Send Email Alert",
                      command=send_alert_email).pack(side='left', padx=5)
        ttk.Button(main_frame, text="Close",
                  command=alerts_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load low stock alerts:\n{str(e)}")

def waste_tracking_dialog(self):
    """Launch the Waste Tracking management GUI"""
    try:
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.waste_tracking_gui import (
            WasteTrackingGUI,
            init_waste_tracking_tables
        )

        # Initialize tables if needed
        init_waste_tracking_tables()

        # Create and show the Waste Tracking GUI
        waste_window = tk.Toplevel(self.root)
        waste_window.title("Waste Tracking & Analysis")
        waste_window.geometry("1200x700")
        waste_window.transient(self.root)

        # Launch the GUI
        WasteTrackingGUI(waste_window)

    except ImportError as e:
        messagebox.showerror("Error", f"Failed to load Waste Tracking module:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Waste Tracking:\n{str(e)}")

