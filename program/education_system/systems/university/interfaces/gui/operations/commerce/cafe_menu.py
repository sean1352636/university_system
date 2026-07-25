"""
Cafe System - Menu management tab mixin
Handles menu item CRUD operations
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.operations.commerce.cafe_common import get_db_connection


class CafeMenuMixin:
    """Mixin for menu management tab functionality"""

    def create_menu_management_tab(self):
        """Create menu management tab"""
        menu_frame = ttk.Frame(self.notebook)
        self.notebook.add(menu_frame, text=_t("cafe.tab_menu_management"))

        # Top controls
        controls_frame = ttk.Frame(menu_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.add_new_item"), command=self.add_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.edit_item"), command=self.edit_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.delete_item"), command=self.delete_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.refresh"), command=self.load_menu_items).pack(side=tk.LEFT, padx=5)

        # Menu items tree
        tree_frame = ttk.Frame(menu_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.menu_tree = ttk.Treeview(
            tree_frame,
            columns=('ID', 'Name', 'Category', 'Price', 'Stock', 'Available'),
            show='headings',
            yscrollcommand=tree_scroll.set
        )
        tree_scroll.config(command=self.menu_tree.yview)

        self.menu_tree.heading('ID', text=_t("cafe.columns.id"))
        self.menu_tree.heading('Name', text=_t("cafe.columns.name"))
        self.menu_tree.heading('Category', text=_t("cafe.columns.category"))
        self.menu_tree.heading('Price', text=_t("cafe.columns.price"))
        self.menu_tree.heading('Stock', text=_t("cafe.columns.stock"))
        self.menu_tree.heading('Available', text=_t("cafe.columns.available"))

        self.menu_tree.column('ID', width=50)
        self.menu_tree.column('Name', width=200)
        self.menu_tree.column('Category', width=150)
        self.menu_tree.column('Price', width=80)
        self.menu_tree.column('Stock', width=80)
        self.menu_tree.column('Available', width=80)

        self.menu_tree.pack(fill=tk.BOTH, expand=True)

        # Load menu items
        self.load_menu_items()

    def load_menu_items(self):
        """Load menu items for management tab"""
        try:
            # Clear existing items
            for item in self.menu_tree.get_children():
                self.menu_tree.delete(item)

            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT product_id, name, category, price, stock_quantity, is_available
                FROM products
                WHERE source_type = 'cafe'
                ORDER BY category, name
            ''')

            items = cursor.fetchall()
            conn.close()

            for item in items:
                item_id, name, category, price, stock, available = item
                available_text = _t('cafe.stock_status.yes') if available else _t('cafe.stock_status.no')
                self.menu_tree.insert('', tk.END, values=(
                    item_id, name, category, f'£{price:.2f}', stock, available_text
                ))

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_menu_items", error=str(e)))

    def add_menu_item(self):
        """Add new menu item"""
        dialog = tk.Toplevel(self.cafe_window)
        dialog.title(_t("cafe.dialogs.add_item_title"))
        dialog.geometry("400x400")

        ttk.Label(dialog, text=_t("cafe.dialogs.item_name")).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.columns.category") + ":").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        category_combo = ttk.Combobox(dialog, values=[_t('cafe.categories.hot_drinks'), _t('cafe.categories.cold_drinks'), _t('cafe.categories.pastries'), _t('cafe.categories.food')], width=28)
        category_combo.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.description")).grid(row=2, column=0, sticky='w', padx=10, pady=5)
        desc_entry = ttk.Entry(dialog, width=30)
        desc_entry.grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.price_label")).grid(row=3, column=0, sticky='w', padx=10, pady=5)
        price_entry = ttk.Entry(dialog, width=30)
        price_entry.grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.initial_stock")).grid(row=4, column=0, sticky='w', padx=10, pady=5)
        stock_entry = ttk.Entry(dialog, width=30)
        stock_entry.insert(0, "0")
        stock_entry.grid(row=4, column=1, padx=10, pady=5)

        def save_item():
            name = name_entry.get().strip()
            category = category_combo.get().strip()
            description = desc_entry.get().strip()

            try:
                price = float(price_entry.get().strip())
                stock = int(stock_entry.get().strip())
            except ValueError:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.invalid_price_stock"))
                return

            if not name or not category:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.name_category_required"))
                return

            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO products (source_type, name, category, description, price, stock_quantity, is_available)
                    VALUES ('cafe', ?, ?, ?, ?, ?, 1)
                ''', (name, category, description, price, stock))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t("common.success"), _t("cafe.messages.item_added"))
                dialog.destroy()
                self.load_menu_items()
                self.load_menu_items_for_pos()
                self.load_categories()

            except sqlite3.Error as e:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.add_item_fail", error=str(e)))

        ttk.Button(dialog, text=_t("cafe.dialogs.save"), command=save_item).grid(row=5, column=0, columnspan=2, pady=20)

    def edit_menu_item(self):
        """Edit selected menu item"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_edit"))
            return

        item_values = self.menu_tree.item(selection[0], 'values')
        item_id = item_values[0]

        # Create edit dialog (similar to add, but pre-filled)
        dialog = tk.Toplevel(self.cafe_window)
        dialog.title(_t("cafe.dialogs.edit_item_title"))
        dialog.geometry("400x450")

        ttk.Label(dialog, text=_t("cafe.dialogs.item_name")).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.insert(0, item_values[1])
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.columns.category") + ":").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        category_combo = ttk.Combobox(dialog, values=[_t('cafe.categories.hot_drinks'), _t('cafe.categories.cold_drinks'), _t('cafe.categories.pastries'), _t('cafe.categories.food')], width=28)
        category_combo.set(item_values[2])
        category_combo.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.price_label")).grid(row=2, column=0, sticky='w', padx=10, pady=5)
        price_entry = ttk.Entry(dialog, width=30)
        price_entry.insert(0, item_values[3].replace('£', ''))
        price_entry.grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.stock_label")).grid(row=3, column=0, sticky='w', padx=10, pady=5)
        stock_entry = ttk.Entry(dialog, width=30)
        stock_entry.insert(0, item_values[4])
        stock_entry.grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("cafe.dialogs.available_label")).grid(row=4, column=0, sticky='w', padx=10, pady=5)
        available_var = tk.BooleanVar(value=(item_values[5] == 'Yes'))
        ttk.Checkbutton(dialog, text=_t("cafe.dialogs.item_available_sale"), variable=available_var).grid(row=4, column=1, sticky='w', padx=10, pady=5)

        def update_item():
            name = name_entry.get().strip()
            category = category_combo.get().strip()

            try:
                price = float(price_entry.get().strip())
                stock = int(stock_entry.get().strip())
            except ValueError:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.invalid_price_stock"))
                return

            available = 1 if available_var.get() else 0

            if not name or not category:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.name_category_required"))
                return

            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE products
                    SET name = ?, category = ?, price = ?, stock_quantity = ?, is_available = ?
                    WHERE product_id = ? AND source_type = 'cafe'
                ''', (name, category, price, stock, available, item_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t("common.success"), _t("cafe.messages.item_updated"))
                dialog.destroy()
                self.load_menu_items()
                self.load_menu_items_for_pos()

            except sqlite3.Error as e:
                messagebox.showerror(_t("common.error"), _t("cafe.errors.update_item_fail", error=str(e)))

        ttk.Button(dialog, text=_t("cafe.dialogs.update"), command=update_item).grid(row=5, column=0, columnspan=2, pady=20)

    def delete_menu_item(self):
        """Delete selected menu item"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_delete"))
            return

        item_values = self.menu_tree.item(selection[0], 'values')
        item_id = item_values[0]
        item_name = item_values[1]

        if not messagebox.askyesno(_t("common.confirm"), _t("cafe.messages.confirm_delete", item=item_name)):
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE product_id = ? AND source_type = 'cafe'", (item_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("cafe.messages.item_deleted"))
            self.load_menu_items()
            self.load_menu_items_for_pos()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.delete_item_fail", error=str(e)))
