"""
Cafe System - Orders history tab mixin
Handles order history display and order details viewing
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from .cafe_system_gui import get_db_connection


class CafeOrdersMixin:
    """Mixin for orders history tab functionality"""

    def create_orders_tab(self):
        """Create orders history tab"""
        orders_frame = ttk.Frame(self.notebook)
        self.notebook.add(orders_frame, text=_t("cafe.tab_order_history"))

        # Top controls
        controls_frame = ttk.Frame(orders_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(controls_frame, text=_t("cafe.orders.filter")).pack(side=tk.LEFT, padx=5)

        self.order_filter = ttk.Combobox(
            controls_frame,
            values=[_t("cafe.orders.all"), _t("cafe.orders.today"), _t("cafe.orders.this_week"), _t("cafe.orders.this_month")],
            state='readonly'
        )
        self.order_filter.set(_t("cafe.orders.today"))
        self.order_filter.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text=_t("cafe.menu_mgmt.refresh"), command=self.load_orders).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.orders.view_details"), command=self.view_order_details).pack(side=tk.LEFT, padx=5)

        # Orders tree
        tree_frame = ttk.Frame(orders_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.orders_tree = ttk.Treeview(
            tree_frame,
            columns=('Order ID', 'Date', 'Customer', 'Items', 'Total', 'Payment', 'Status'),
            show='headings',
            yscrollcommand=tree_scroll.set
        )
        tree_scroll.config(command=self.orders_tree.yview)

        self.orders_tree.heading('Order ID', text=_t("cafe.columns.order_id"))
        self.orders_tree.heading('Date', text=_t("cafe.columns.date"))
        self.orders_tree.heading('Customer', text=_t("cafe.columns.customer"))
        self.orders_tree.heading('Items', text=_t("cafe.columns.items"))
        self.orders_tree.heading('Total', text=_t("cafe.columns.total"))
        self.orders_tree.heading('Payment', text=_t("cafe.columns.payment"))
        self.orders_tree.heading('Status', text=_t("cafe.columns.status"))

        self.orders_tree.column('Order ID', width=80)
        self.orders_tree.column('Date', width=150)
        self.orders_tree.column('Customer', width=150)
        self.orders_tree.column('Items', width=60)
        self.orders_tree.column('Total', width=100)
        self.orders_tree.column('Payment', width=120)
        self.orders_tree.column('Status', width=100)

        self.orders_tree.pack(fill=tk.BOTH, expand=True)

        # Load orders
        self.load_orders()

    def load_orders(self):
        """Load order history"""
        try:
            # Clear existing items
            for item in self.orders_tree.get_children():
                self.orders_tree.delete(item)

            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get date filter
            filter_type = self.order_filter.get()
            date_filter = ''

            if filter_type == 'Today':
                date_filter = "WHERE DATE(order_date) = DATE('now')"
            elif filter_type == 'This Week':
                date_filter = "WHERE DATE(order_date) >= DATE('now', '-7 days')"
            elif filter_type == 'This Month':
                date_filter = "WHERE DATE(order_date) >= DATE('now', 'start of month')"

            query = f'''
                SELECT
                    o.order_id,
                    o.order_date,
                    COALESCE(o.customer_name, o.student_id, 'Walk-in'),
                    COUNT(oi.id),
                    o.total_amount,
                    o.payment_method,
                    o.status
                FROM cafe_orders o
                LEFT JOIN cafe_order_items oi ON o.order_id = oi.order_id
                {date_filter}
                GROUP BY o.order_id
                ORDER BY o.order_date DESC
            '''

            cursor.execute(query)
            orders = cursor.fetchall()
            conn.close()

            for order in orders:
                order_id, date, customer, items, total, payment, status = order
                self.orders_tree.insert('', tk.END, values=(
                    order_id,
                    date,
                    customer,
                    items,
                    f'£{total:.2f}',
                    payment or 'N/A',
                    status
                ))

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_orders", error=str(e)))

    def view_order_details(self):
        """View details of selected order"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_order_view"))
            return

        order_values = self.orders_tree.item(selection[0], 'values')
        order_id = order_values[0]

        dialog = tk.Toplevel(self.cafe_window)
        dialog.title(_t("cafe.dialogs.order_details_title", id=order_id))
        dialog.geometry("600x500")

        # Order info
        info_frame = ttk.LabelFrame(dialog, text=_t("cafe.dialogs.order_information"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=_t("cafe.refunds.order_id_label") + f" {order_values[0]}").pack(anchor='w')
        ttk.Label(info_frame, text=_t("cafe.refunds.date_label") + f" {order_values[1]}").pack(anchor='w')
        ttk.Label(info_frame, text=_t("cafe.refunds.customer_label") + f" {order_values[2]}").pack(anchor='w')
        ttk.Label(info_frame, text=_t("cafe.refunds.total_label") + f" {order_values[4]}").pack(anchor='w')
        ttk.Label(info_frame, text=_t("cafe.refunds.payment_method_label") + f" {order_values[5]}").pack(anchor='w')
        ttk.Label(info_frame, text=_t("cafe.refunds.status_label") + f" {order_values[6]}").pack(anchor='w')

        # Order items
        items_frame = ttk.LabelFrame(dialog, text=_t("cafe.dialogs.order_items"), padding="10")
        items_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        items_tree = ttk.Treeview(
            items_frame,
            columns=('Item', 'Qty', 'Price', 'Subtotal'),
            show='headings'
        )

        items_tree.heading('Item', text=_t("cafe.columns.item"))
        items_tree.heading('Qty', text=_t("cafe.columns.qty"))
        items_tree.heading('Price', text=_t("cafe.dialogs.unit_price"))
        items_tree.heading('Subtotal', text=_t("cafe.columns.subtotal"))

        items_tree.pack(fill=tk.BOTH, expand=True)

        # Load order items
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_name, quantity, unit_price, subtotal
                FROM cafe_order_items
                WHERE order_id = ?
            ''', (order_id,))

            items = cursor.fetchall()
            conn.close()

            for item in items:
                item_name, qty, price, subtotal = item
                items_tree.insert('', tk.END, values=(
                    item_name, qty, f'£{price:.2f}', f'£{subtotal:.2f}'
                ))

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_order_items", error=str(e)))
