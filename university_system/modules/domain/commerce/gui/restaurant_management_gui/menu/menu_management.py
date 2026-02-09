from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
from university_system.infrastructure.exceptions import (
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
    from university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def view_menu_items(self):
    """Display menu items in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("common.database_connection_failed"))
            return
            
        cursor = conn.cursor()
        cursor.execute('''
            SELECT item_id, name, category, price, available, vegetarian, vegan 
            FROM menu_items 
            ORDER BY category, name
        ''')
        items = cursor.fetchall()
        
        for item in self.menu_tree.get_children():
            self.menu_tree.delete(item)
            
        for item in items:
            available = "Yes" if item[4] else "No"
            vegetarian = "Yes" if item[5] else "No"
            vegan = "Yes" if item[6] else "No"
            
            self.menu_tree.insert('', 'end', values=(
                item[0], item[1], item[2], f"£{item[3]:.2f}", 
                available, vegetarian, vegan
            ))
            
        conn.close()
        messagebox.showinfo(_t("common.success"), _t("commerce.menu.loaded_items", count=len(items)))

    except sqlite3.Error as e:
        messagebox.showerror(_t("common.error"), _t("commerce.menu.load_failed", error=str(e)))

def add_menu_item_dialog(self):
    """Show dialog to add new menu item"""
    dialog = MenuItemDialog(self.root, _t("commerce.menu.add_menu_item"))
    if dialog.result:
        self.view_menu_items()

def update_menu_item_dialog(self):
    """Show dialog to update menu item"""
    selection = self.menu_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.no_selection"), _t("commerce.menu.select_item_to_update"))
        return

    item_values = self.menu_tree.item(selection[0])['values']
    item_id = item_values[0]

    dialog = MenuItemDialog(self.root, _t("commerce.menu.update_menu_item"), item_id)
    if dialog.result:
        self.view_menu_items()

def show_menu_analytics(self):
    """Show menu analytics in a new window"""
    try:
        analytics_window = tk.Toplevel(self.root)
        analytics_window.title(_t("commerce.menu.menu_analytics"))
        analytics_window.geometry("800x600")
        
        text_area = ScrolledText(analytics_window, height=30, width=80)
        text_area.pack(fill='both', expand=True, padx=10, pady=10)
        
        analytics_text = self.generate_menu_analytics_text()
        text_area.insert('1.0', analytics_text)
        text_area.config(state='disabled')

    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror(_t("common.error"), _t("commerce.menu.analytics_failed", error=str(e)))

def generate_menu_analytics_text(self):
    """Generate menu analytics as text"""
    try:
        conn = get_db_connection()
        if not conn:
            return _t("common.database_connection_failed")

        cursor = conn.cursor()

        text = _t("commerce.menu.analytics_header") + "\n"
        text += "=" * 50 + "\n\n"

        cursor.execute('''
            SELECT category, COUNT(*) as count, AVG(price) as avg_price
            FROM menu_items
            GROUP BY category
            ORDER BY count DESC
        ''')

        categories = cursor.fetchall()

        text += _t("commerce.menu.items_by_category") + "\n"
        text += "-" * 30 + "\n"
        for cat in categories:
            text += f"{cat[0]}: {cat[1]} items, Avg Price: £{cat[2]:.2f}\n"

        conn.close()
        return text

    except sqlite3.Error as e:
        return _t("commerce.menu.analytics_error", error=str(e))

class MenuItemDialog:
    def __init__(self, parent, title, item_id=None):
        self.result = False
        self.item_id = item_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
        if item_id:
            self.load_item_data()
            
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("commerce.menu.name")).grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.menu.description")).grid(row=1, column=0, sticky='nw', pady=5)
        self.desc_text = tk.Text(main_frame, height=3, width=40)
        self.desc_text.grid(row=1, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.menu.price")).grid(row=2, column=0, sticky='w', pady=5)
        self.price_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.price_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.menu.category")).grid(row=3, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var,
                                     values=['Main', 'Side', 'Dessert', 'Beverage'])
        category_combo.grid(row=3, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.menu.allergens")).grid(row=4, column=0, sticky='w', pady=5)
        self.allergens_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.allergens_var, width=40).grid(row=4, column=1, pady=5)

        self.vegetarian_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t("commerce.menu.vegetarian"), variable=self.vegetarian_var).grid(row=5, column=1, sticky='w', pady=5)

        self.vegan_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t("commerce.menu.vegan"), variable=self.vegan_var).grid(row=6, column=1, sticky='w', pady=5)

        self.available_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text=_t("commerce.menu.available"), variable=self.available_var).grid(row=7, column=1, sticky='w', pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("common.save"), command=self.save).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.cancel).pack(side='left', padx=10)
        
    def load_item_data(self):
        """Load existing item data for editing"""
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM menu_items WHERE item_id = ?', (self.item_id,))
            item = cursor.fetchone()
            
            if item:
                self.name_var.set(item[1])
                self.desc_text.insert(1.0, item[2] or '')
                self.price_var.set(str(item[3]))
                self.category_var.set(item[4])
                self.allergens_var.set(item[5] or '')
                self.vegetarian_var.set(bool(item[6]))
                self.vegan_var.set(bool(item[7]))
                self.available_var.set(bool(item[8]))
                
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("commerce.menu.load_item_failed", error=str(e)))
            
    def save(self):
        """Save the menu item"""
        try:
            if not self.name_var.get().strip():
                messagebox.showerror(_t("common.error"), _t("commerce.menu.name_required"))
                return

            try:
                price = float(self.price_var.get())
            except ValueError:
                messagebox.showerror(_t("common.error"), _t("commerce.menu.invalid_price"))
                return
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                description = self.desc_text.get(1.0, tk.END).strip()
                
                if self.item_id:
                    cursor.execute('''
                        UPDATE menu_items 
                        SET name=?, description=?, price=?, category=?, allergens=?, 
                            vegetarian=?, vegan=?, available=?
                        WHERE item_id=?
                    ''', (self.name_var.get(), description, price, self.category_var.get(),
                          self.allergens_var.get(), self.vegetarian_var.get(),
                          self.vegan_var.get(), self.available_var.get(), self.item_id))
                else:
                    cursor.execute('''
                        INSERT INTO menu_items (name, description, price, category, allergens, 
                                              vegetarian, vegan, available)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (self.name_var.get(), description, price, self.category_var.get(),
                          self.allergens_var.get(), self.vegetarian_var.get(),
                          self.vegan_var.get(), self.available_var.get()))
                
                conn.commit()
                conn.close()
            
            messagebox.showinfo(_t("common.success"), _t("commerce.menu.item_saved"))
            self.result = True
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("commerce.menu.save_failed", error=str(e)))
            
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()

