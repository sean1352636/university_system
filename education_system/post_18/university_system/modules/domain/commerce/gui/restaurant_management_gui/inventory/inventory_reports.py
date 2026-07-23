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


def inventory_reports(self):
    """Show comprehensive inventory reports menu"""
    reports_dialog = tk.Toplevel(self.root)
    reports_dialog.title("Inventory Reports")
    reports_dialog.geometry("450x500")
    reports_dialog.transient(self.root)
    reports_dialog.grab_set()
    main_frame = ttk.Frame(reports_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Inventory Reports",
             font=('Arial', 14, 'bold')).pack(pady=20)
    ttk.Button(main_frame, text="Inventory Valuation Report",
              command=lambda: [reports_dialog.destroy(), self.inventory_valuation_report()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="Stock Movement Report",
              command=lambda: [reports_dialog.destroy(), self.stock_movement_report()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="Low Stock Report",
              command=lambda: [reports_dialog.destroy(), self.low_stock_report()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="Expiry Report",
              command=lambda: [reports_dialog.destroy(), self.expiry_report()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="ABC Analysis",
              command=lambda: [reports_dialog.destroy(), self.abc_analysis()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="Inventory Transactions Log",
              command=lambda: [reports_dialog.destroy(), self.inventory_transactions()],
              width=35).pack(pady=5)
    ttk.Button(main_frame, text="Close",
              command=reports_dialog.destroy,
              width=35).pack(pady=20)

def inventory_valuation_report(self):
    """Calculate total inventory value"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get inventory valuation by category/item
        cursor.execute('''
            SELECT item_id, name, quantity, unit, cost_per_unit,
                   (quantity * cost_per_unit) as total_value
            FROM restaurant_inventory
            ORDER BY total_value DESC
        ''')
        items = cursor.fetchall()
        conn.close()
        # Display report
        report_dialog = tk.Toplevel(self.root)
        report_dialog.title("Inventory Valuation Report")
        report_dialog.geometry("900x600")
        report_dialog.transient(self.root)
        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Inventory Valuation Report",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=30, width=100)
        report_text.pack(fill='both', expand=True)
        report = "INVENTORY VALUATION REPORT\n"
        report += "=" * 90 + "\n\n"
        report += f"{'Item ID':<10} {'Item Name':<30} {'Quantity':<12} {'Unit':<10} {'Cost/Unit':<12} {'Total Value':<15}\n"
        report += "-" * 90 + "\n"
        total_value = 0
        for item_id, name, qty, unit, cost, value in items:
            total_value += value if value else 0
            report += f"{item_id:<10} {name:<30} {qty:<12.1f} {unit:<10} £{cost:<11.2f if cost else 0:<11.2f} £{value:<14.2f if value else 0:<14.2f}\n"
        report += "-" * 90 + "\n"
        report += f"{'TOTAL INVENTORY VALUE:':<64} £{total_value:<14.2f}\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=report_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate valuation report:\n{str(e)}")

def stock_movement_report(self):
    """Track inventory movements (received, used, waste)"""
    try:
        start_date = simpledialog.askstring("Stock Movement", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Stock Movement", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get movements data (purchases, waste)
        cursor.execute('''
            SELECT 'Purchase' as type, po.order_date as date, poi.item_id,
                   i.name, poi.quantity, 'Received' as movement
            FROM restaurant_purchase_order_items poi
            JOIN restaurant_purchase_orders po ON poi.order_id = po.order_id
            JOIN restaurant_inventory i ON poi.item_id = i.item_id
            WHERE po.order_date BETWEEN ? AND ?
            UNION ALL
            SELECT 'Waste' as type, w.waste_date as date, NULL as item_id,
                   w.item_name as name, w.quantity, 'Waste' as movement
            FROM restaurant_waste w
            WHERE w.waste_date BETWEEN ? AND ?
            ORDER BY date DESC
        ''', (start_date, end_date, start_date, end_date))
        movements = cursor.fetchall()
        conn.close()
        # Display report
        report_dialog = tk.Toplevel(self.root)
        report_dialog.title("Stock Movement Report")
        report_dialog.geometry("900x600")
        report_dialog.transient(self.root)
        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text=f"Stock Movement Report\n{start_date} to {end_date}",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=30, width=100)
        report_text.pack(fill='both', expand=True)
        report = "STOCK MOVEMENT REPORT\n"
        report += "=" * 90 + "\n\n"
        report += f"{'Date':<12} {'Type':<12} {'Item':<30} {'Quantity':<12} {'Movement':<15}\n"
        report += "-" * 90 + "\n"
        total_received = 0
        total_waste = 0
        for mov_type, date, item_id, name, qty, movement in movements:
            report += f"{date:<12} {mov_type:<12} {name:<30} {qty:<12.1f} {movement:<15}\n"
            if movement == 'Received':
                total_received += qty if qty else 0
            elif movement == 'Waste':
                total_waste += qty if qty else 0
        report += "\n" + "=" * 90 + "\n"
        report += f"Total Received: {total_received:.1f} units\n"
        report += f"Total Waste: {total_waste:.1f} units\n"
        report += f"Net Movement: {total_received - total_waste:.1f} units\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=report_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate stock movement report:\n{str(e)}")

def low_stock_report(self):
    """Report on items below reorder level"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get low stock items
        cursor.execute('''
            SELECT item_id, name, quantity, unit, reorder_level,
                   cost_per_unit, (reorder_level - quantity) as reorder_qty,
                   ((reorder_level - quantity) * cost_per_unit) as reorder_cost
            FROM restaurant_inventory
            WHERE quantity <= reorder_level
            ORDER BY (reorder_level - quantity) DESC
        ''')
        low_stock = cursor.fetchall()
        conn.close()
        if not low_stock:
            messagebox.showinfo("Low Stock", "No items are currently low on stock!")
            return
        # Display report
        report_dialog = tk.Toplevel(self.root)
        report_dialog.title("Low Stock Report")
        report_dialog.geometry("1000x600")
        report_dialog.transient(self.root)
        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Low Stock Report",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=30, width=110)
        report_text.pack(fill='both', expand=True)
        report = "LOW STOCK REPORT\n"
        report += "=" * 105 + "\n\n"
        report += f"{'ID':<6} {'Item':<25} {'Current':<10} {'Reorder':<10} {'Unit':<8} {'Shortage':<10} {'Cost/Unit':<12} {'Restock Cost':<15} {'Priority':<10}\n"
        report += "-" * 105 + "\n"
        total_restock_cost = 0
        for item_id, name, qty, unit, reorder, cost, reorder_qty, restock_cost in low_stock:
            total_restock_cost += restock_cost if restock_cost else 0
            shortage = reorder - qty
            priority = "CRITICAL" if qty < (reorder * 0.3) else "WARNING"
            report += f"{item_id:<6} {name:<25} {qty:<10.1f} {reorder:<10.1f} {unit:<8} "
            report += f"{shortage:<10.1f} £{cost:<11.2f if cost else 0:<11.2f} £{restock_cost:<14.2f if restock_cost else 0:<14.2f} {priority:<10}\n"
        report += "\n" + "=" * 105 + "\n"
        report += f"Total Items Low on Stock: {len(low_stock)}\n"
        report += f"Total Restock Cost: £{total_restock_cost:.2f}\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=report_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate low stock report:\n{str(e)}")

def expiry_report(self):
    """Track expiring inventory"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Add expiry_date column if it doesn't exist
        try:
            cursor.execute('''
                ALTER TABLE restaurant_inventory ADD COLUMN expiry_date DATE
            ''')
            conn.commit()
        except sqlite3.Error:
            pass  # Column already exists
        # Get expiring items (next 7, 14, 30 days)
        cursor.execute('''
            SELECT item_id, name, quantity, unit, expiry_date,
                   julianday(expiry_date) - julianday('now') as days_until_expiry,
                   cost_per_unit, (quantity * cost_per_unit) as value_at_risk
            FROM restaurant_inventory
            WHERE expiry_date IS NOT NULL
            ORDER BY expiry_date
        ''')
        expiring_items = cursor.fetchall()
        conn.close()
        # Display report
        report_dialog = tk.Toplevel(self.root)
        report_dialog.title("Expiry Report")
        report_dialog.geometry("1000x600")
        report_dialog.transient(self.root)
        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Inventory Expiry Report",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=30, width=110)
        report_text.pack(fill='both', expand=True)
        report = "INVENTORY EXPIRY REPORT\n"
        report += "=" * 105 + "\n\n"
        expired = []
        expires_7_days = []
        expires_14_days = []
        expires_30_days = []
        for item in expiring_items:
            days_left = item[5]
            if days_left < 0:
                expired.append(item)
            elif days_left <= 7:
                expires_7_days.append(item)
            elif days_left <= 14:
                expires_14_days.append(item)
            elif days_left <= 30:
                expires_30_days.append(item)
        # Expired items
        report += "EXPIRED ITEMS (Immediate Action Required):\n"
        report += "-" * 105 + "\n"
        if expired:
            report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Ago':<12} {'Value Lost':<15}\n"
            report += "-" * 105 + "\n"
            for item_id, name, qty, unit, expiry, days, cost, value in expired:
                report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {abs(days):<12.0f} £{value:<14.2f if value else 0:<14.2f}\n"
        else:
            report += "No expired items.\n"
        # Expiring in 7 days
        report += "\n\nEXPIRING WITHIN 7 DAYS (Critical):\n"
        report += "-" * 105 + "\n"
        if expires_7_days:
            report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Left':<12} {'Value at Risk':<15}\n"
            report += "-" * 105 + "\n"
            for item_id, name, qty, unit, expiry, days, cost, value in expires_7_days:
                report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {days:<12.0f} £{value:<14.2f if value else 0:<14.2f}\n"
        else:
            report += "No items expiring within 7 days.\n"
        # Expiring in 14 days
        report += "\n\nEXPIRING WITHIN 14 DAYS (Warning):\n"
        report += "-" * 105 + "\n"
        if expires_14_days:
            report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Left':<12}\n"
            report += "-" * 105 + "\n"
            for item_id, name, qty, unit, expiry, days, cost, value in expires_14_days:
                report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {days:<12.0f}\n"
        else:
            report += "No items expiring within 14 days.\n"
        # Summary
        report += "\n\nSUMMARY:\n"
        report += "-" * 105 + "\n"
        report += f"Expired Items: {len(expired)}\n"
        report += f"Expiring in 7 Days: {len(expires_7_days)}\n"
        report += f"Expiring in 14 Days: {len(expires_14_days)}\n"
        report += f"Expiring in 30 Days: {len(expires_30_days)}\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=report_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate expiry report:\n{str(e)}")

def abc_analysis(self):
    """ABC analysis for inventory optimization"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get inventory value data
        cursor.execute('''
            SELECT item_id, name, quantity, cost_per_unit,
                   (quantity * cost_per_unit) as total_value
            FROM restaurant_inventory
            WHERE quantity > 0 AND cost_per_unit > 0
            ORDER BY total_value DESC
        ''')
        items = cursor.fetchall()
        conn.close()
        if not items:
            messagebox.showinfo("No Data", "No inventory data available for ABC analysis")
            return
        # Perform ABC analysis
        total_value = sum(item[4] for item in items)
        cumulative_value = 0
        a_items = []
        b_items = []
        c_items = []
        for item in items:
            cumulative_value += item[4]
            cumulative_percent = (cumulative_value / total_value) * 100
            if cumulative_percent <= 80:  # A items: top 80% of value
                a_items.append(item)
            elif cumulative_percent <= 95:  # B items: next 15% of value
                b_items.append(item)
            else:  # C items: remaining 5% of value
                c_items.append(item)
        # Display report
        report_dialog = tk.Toplevel(self.root)
        report_dialog.title("ABC Analysis")
        report_dialog.geometry("900x700")
        report_dialog.transient(self.root)
        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="ABC Inventory Analysis",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=35, width=100)
        report_text.pack(fill='both', expand=True)
        report = "ABC INVENTORY ANALYSIS\n"
        report += "=" * 90 + "\n\n"
        report += "CATEGORY A ITEMS (High Value - Top 80%):\n"
        report += f"Items: {len(a_items)} ({len(a_items)/len(items)*100:.1f}% of items)\n"
        report += f"Value: £{sum(item[4] for item in a_items):.2f} (~80% of total value)\n"
        report += "-" * 90 + "\n"
        report += f"{'ID':<6} {'Item Name':<30} {'Quantity':<12} {'Value':<15}\n"
        report += "-" * 90 + "\n"
        for item_id, name, qty, cost, value in a_items[:10]:
            report += f"{item_id:<6} {name:<30} {qty:<12.1f} £{value:<14.2f}\n"
        if len(a_items) > 10:
            report += f"... and {len(a_items) - 10} more items\n"
        report += "\n\nCATEGORY B ITEMS (Moderate Value - Next 15%):\n"
        report += f"Items: {len(b_items)} ({len(b_items)/len(items)*100:.1f}% of items)\n"
        report += f"Value: £{sum(item[4] for item in b_items):.2f} (~15% of total value)\n"
        report += "-" * 90 + "\n"
        report += f"{'ID':<6} {'Item Name':<30} {'Quantity':<12} {'Value':<15}\n"
        report += "-" * 90 + "\n"
        for item_id, name, qty, cost, value in b_items[:10]:
            report += f"{item_id:<6} {name:<30} {qty:<12.1f} £{value:<14.2f}\n"
        if len(b_items) > 10:
            report += f"... and {len(b_items) - 10} more items\n"
        report += "\n\nCATEGORY C ITEMS (Low Value - Remaining 5%):\n"
        report += f"Items: {len(c_items)} ({len(c_items)/len(items)*100:.1f}% of items)\n"
        report += f"Value: £{sum(item[4] for item in c_items):.2f} (~5% of total value)\n"
        report += "\n\nRECOMMENDATIONS:\n"
        report += "-" * 90 + "\n"
        report += "Category A Items:\n"
        report += "  • Tight inventory control and frequent monitoring\n"
        report += "  • Accurate demand forecasting\n"
        report += "  • Strong supplier relationships\n"
        report += "  • Priority reordering\n\n"
        report += "Category B Items:\n"
        report += "  • Moderate control and periodic review\n"
        report += "  • Standard reorder procedures\n\n"
        report += "Category C Items:\n"
        report += "  • Simple controls and bulk ordering\n"
        report += "  • Consider reducing stock variety\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=report_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate ABC analysis:\n{str(e)}")

