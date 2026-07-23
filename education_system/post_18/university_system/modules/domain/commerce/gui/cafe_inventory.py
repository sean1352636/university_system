"""
Cafe System - Inventory management tab mixin
Handles stock tracking, additions, removals, and transaction history
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.commerce.gui.cafe_common import get_db_connection


class CafeInventoryMixin:
    """Mixin for inventory management tab functionality"""

    def create_inventory_tab(self):
        """Create inventory management tab"""
        inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(inventory_frame, text=_t("cafe.tab_inventory"))

        # Top controls
        controls_frame = ttk.Frame(inventory_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(controls_frame, text=_t("cafe.inventory.add_stock"), command=self.add_stock).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.inventory.remove_stock"), command=self.remove_stock).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.inventory.view_transactions"), command=self.view_inventory_transactions).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.refresh"), command=self.load_menu_items).pack(side=tk.LEFT, padx=5)

        # Inventory tree (reuses menu tree data with focus on stock)
        tree_frame = ttk.Frame(inventory_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.inventory_tree = ttk.Treeview(
            tree_frame,
            columns=('ID', 'Item', 'Category', 'Stock', 'Status'),
            show='headings',
            yscrollcommand=tree_scroll.set
        )
        tree_scroll.config(command=self.inventory_tree.yview)

        self.inventory_tree.heading('ID', text=_t("cafe.columns.id"))
        self.inventory_tree.heading('Item', text=_t("cafe.columns.item"))
        self.inventory_tree.heading('Category', text=_t("cafe.columns.category"))
        self.inventory_tree.heading('Stock', text=_t("cafe.inventory.current_stock"))
        self.inventory_tree.heading('Status', text=_t("cafe.columns.status"))

        self.inventory_tree.column('ID', width=60)
        self.inventory_tree.column('Item', width=250)
        self.inventory_tree.column('Category', width=150)
        self.inventory_tree.column('Stock', width=120)
        self.inventory_tree.column('Status', width=120)

        self.inventory_tree.pack(fill=tk.BOTH, expand=True)

        # Load inventory
        self.load_inventory()

    def load_inventory(self):
        """Load inventory data"""
        try:
            # Clear existing items
            for item in self.inventory_tree.get_children():
                self.inventory_tree.delete(item)

            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT product_id, name, category, stock_quantity
                FROM products
                WHERE source_type = 'cafe'
                ORDER BY stock_quantity ASC, name
            ''')

            items = cursor.fetchall()
            conn.close()

            for item in items:
                item_id, name, category, stock = item

                # Determine status based on stock level
                if stock == 0:
                    status = _t('cafe.inventory.out_of_stock')
                elif stock < 10:
                    status = _t('cafe.inventory.low_stock')
                elif stock < 20:
                    status = _t('cafe.inventory.moderate')
                else:
                    status = _t('cafe.inventory.good')

                self.inventory_tree.insert('', tk.END, values=(
                    item_id, name, category, stock, status
                ))

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_inventory", error=str(e)))

    def add_stock(self):
        """Add stock to selected item"""
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_inventory"))
            return

        item_values = self.inventory_tree.item(selection[0], 'values')
        item_id = item_values[0]
        item_name = item_values[1]

        quantity = simpledialog.askinteger(_t("cafe.inventory.add_stock"), f"Enter quantity to add for {item_name}:", minvalue=1)
        if not quantity:
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE products
                SET stock_quantity = stock_quantity + ?
                WHERE product_id = ? AND source_type = 'cafe'
            ''', (quantity, item_id))

            cursor.execute('''
                INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes)
                VALUES ('cafe_inventory', ?, 'item', ?, 'restock', 'Manual stock addition')
            ''', (item_id, quantity))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("cafe.messages.stock_added", quantity=quantity, item=item_name))
            self.load_inventory()
            self.load_menu_items()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.add_stock_fail", error=str(e)))

    def remove_stock(self):
        """Remove stock from selected item"""
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_inventory"))
            return

        item_values = self.inventory_tree.item(selection[0], 'values')
        item_id = item_values[0]
        item_name = item_values[1]
        current_stock = int(item_values[3])

        quantity = simpledialog.askinteger(
            _t("cafe.inventory.remove_stock"),
            f"Enter quantity to remove for {item_name} (Current: {current_stock}):",
            minvalue=1,
            maxvalue=current_stock
        )
        if not quantity:
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE product_id = ? AND source_type = 'cafe'
            ''', (quantity, item_id))

            cursor.execute('''
                INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes)
                VALUES ('cafe_inventory', ?, 'item', ?, 'adjustment', 'Manual stock removal')
            ''', (item_id, -quantity))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("cafe.messages.stock_removed", quantity=quantity, item=item_name))
            self.load_inventory()
            self.load_menu_items()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.remove_stock_fail", error=str(e)))

    def view_inventory_transactions(self):
        """View inventory transaction history"""
        dialog = tk.Toplevel(self.cafe_window)
        dialog.title(_t("cafe.dialogs.inventory_transactions"))
        dialog.geometry("800x600")

        # Transaction tree
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        trans_tree = ttk.Treeview(
            tree_frame,
            columns=('ID', 'Item', 'Quantity', 'Type', 'Date', 'Notes'),
            show='headings',
            yscrollcommand=tree_scroll.set
        )
        tree_scroll.config(command=trans_tree.yview)

        trans_tree.heading('ID', text=_t("cafe.columns.id"))
        trans_tree.heading('Item', text=_t("cafe.columns.item"))
        trans_tree.heading('Quantity', text=_t("cafe.columns.change"))
        trans_tree.heading('Type', text=_t("cafe.columns.type"))
        trans_tree.heading('Date', text=_t("cafe.columns.date"))
        trans_tree.heading('Notes', text=_t("cafe.columns.notes"))

        trans_tree.column('ID', width=60)
        trans_tree.column('Item', width=200)
        trans_tree.column('Quantity', width=80)
        trans_tree.column('Type', width=100)
        trans_tree.column('Date', width=150)
        trans_tree.column('Notes', width=200)

        trans_tree.pack(fill=tk.BOTH, expand=True)

        # Load transactions
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.transaction_id, m.name, t.quantity_change, t.transaction_type, t.created_at, t.notes
                FROM transactions t
                JOIN products m ON t.reference_id = m.id AND m.source_type = 'cafe' AND t.reference_type = 'item'
                WHERE t.source_type = 'cafe_inventory'
                ORDER BY t.created_at DESC
                LIMIT 500
            ''')

            transactions = cursor.fetchall()
            conn.close()

            for trans in transactions:
                trans_tree.insert('', tk.END, values=trans)

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_transactions", error=str(e)))
