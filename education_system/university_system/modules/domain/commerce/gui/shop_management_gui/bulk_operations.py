import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
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


def show_bulk_operations(self):
    """Show bulk operations dialog"""
    # Create bulk operations window
    bulk_window = tk.Toplevel(self.root)
    bulk_window.title(_t("shop_management.titles.bulk_operations"))
    bulk_window.geometry("350x250")
    bulk_window.resizable(False, False)

    # Make it modal
    bulk_window.transient(self.root)
    bulk_window.grab_set()

    main_frame = ttk.Frame(bulk_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Title
    ttk.Label(main_frame, text=_t("shop_management.titles.bulk_operations"), style='Title.TLabel').grid(row=0, column=0, pady=(0, 20))

    # Operation buttons
    ttk.Button(main_frame, text=_t("shop_management.buttons.bulk_price_update"),
              command=lambda: [bulk_window.destroy(), self.bulk_price_update()],
              width=25).grid(row=1, column=0, pady=5)

    ttk.Button(main_frame, text=_t("shop_management.buttons.bulk_restock"),
              command=lambda: [bulk_window.destroy(), self.bulk_restock()],
              width=25).grid(row=2, column=0, pady=5)

    ttk.Button(main_frame, text=_t("shop_management.buttons.import_products"),
              command=lambda: [bulk_window.destroy(), self.import_products()],
              width=25).grid(row=3, column=0, pady=5)

    ttk.Button(main_frame, text=_t("shop_management.buttons.export_products"),
              command=lambda: [bulk_window.destroy(), self.export_products()],
              width=25).grid(row=4, column=0, pady=5)

    ttk.Button(main_frame, text=_t("common.cancel"),
              command=bulk_window.destroy, width=25).grid(row=5, column=0, pady=15)


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
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY category")
            categories = ["All"] + [row[0] for row in cursor.fetchall()]
            category_combo.configure(values=categories)
            conn.close()
    except Exception as e:
        logger.error(f"Failed to load categories for bulk price update: {e}")
        # Keep default "All" option as fallback
        category_combo.configure(values=["All"])

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
                        UPDATE products
                        SET price = price * ?, updated_at = ?
                        WHERE source_type = 'shop' AND is_active = 1
                    """, [multiplier, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                else:
                    cursor.execute("""
                        UPDATE products
                        SET price = MAX(0.01, price + ?), updated_at = ?
                        WHERE source_type = 'shop' AND is_active = 1
                    """, [fixed_change, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            else:
                if method == "percentage":
                    cursor.execute("""
                        UPDATE products
                        SET price = price * ?, updated_at = ?
                        WHERE source_type = 'shop' AND category = ? AND is_active = 1
                    """, [multiplier, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category])
                else:
                    cursor.execute("""
                        UPDATE products
                        SET price = MAX(0.01, price + ?), updated_at = ?
                        WHERE source_type = 'shop' AND category = ? AND is_active = 1
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
                    cursor.execute("SELECT MAX(SUBSTR(source_product_id, 2)) FROM products WHERE source_type = 'shop' AND source_product_id LIKE 'P%'")
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
                        INSERT INTO products
                        (source_product_id, source_type, name, description, price, category, created_at, updated_at, tax_rate, is_active)
                        VALUES (?, 'shop', ?, ?, ?, ?, ?, ?, ?, ?)
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
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop'
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


def backup_shop_database(self):
    """Create timestamped backup of shop database"""
    try:
        import shutil
        from datetime import datetime

        # Generate timestamped backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"shop_backup_{timestamp}.db"

        # Get the current database path
        from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH as DB_PATH
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


