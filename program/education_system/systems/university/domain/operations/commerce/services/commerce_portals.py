"""Staff + Student portals for the unified commerce surfaces (cafe, bar,
takeaway).

Cafe, Bar, and Takeaway share the same `products` / `orders` /
`order_items` tables with a `source_type` discriminator ('cafe' / 'bar' /
'takeaway'). These two classes are parameterised by that discriminator so
the three features reuse a single implementation; feature-specific
launchers at the bottom of the file thinly wrap them.

Admins retain the full CafeSystemGUI / BarGUI / TakeawayGUI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_ORDER_STATUSES = ['pending', 'preparing', 'ready', 'delivered', 'cancelled']


_PALETTE = {
    'cafe':     {'bg': '#6e4c2b', 'accent': '#4a3420',
                 'singular': 'item',
                 'student_title': 'Cafe — Menu & My Orders'},
    'bar':      {'bg': '#7b241c', 'accent': '#4e1711',
                 'singular': 'drink',
                 'student_title': 'Bar — Menu & My Orders'},
    'takeaway': {'bg': '#2c7a47', 'accent': '#1e5231',
                 'singular': 'item',
                 'student_title': 'Takeaway — Menu & My Orders'},
}


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class CommerceStaffPortal:
    """Orders queue + product/stock view for cafe/bar/takeaway staff."""

    def __init__(self, parent, auth, source_type, feature_label):
        self.auth = auth
        self.source_type = source_type
        self.feature_label = feature_label
        self._pal = _PALETTE.get(source_type, _PALETTE['cafe'])

        self.window = tk.Toplevel(parent)
        self.window.title(f"{feature_label} — Staff Portal")
        self.window.geometry("1150x720")
        self.window.minsize(960, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.scope_var = tk.StringVar(value='Open')
        self.info_var = tk.StringVar(value="")

        self._build_ui()
        self._load_orders()
        self._load_products()

    def _build_ui(self):
        header = tk.Frame(self.window, bg=self._pal['bg'], height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"{self.feature_label} — Staff",
                 font=('Arial', 14, 'bold'),
                 bg=self._pal['bg'], fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_orders_tab(nb)
        self._build_products_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_orders_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Orders")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Filter:").pack(side='left', padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.scope_var, state='readonly',
                     values=['Open', 'Today', 'All'], width=10
                     ).pack(side='left', padx=(0, 12))
        ttk.Button(bar, text="Apply",
                   command=self._load_orders).pack(side='left')
        ttk.Button(bar, text="Refresh",
                   command=self._load_orders).pack(side='right')

        action_bar = ttk.Frame(frame)
        action_bar.pack(fill='x', pady=(0, 6))
        ttk.Label(action_bar, text="Advance selected order:").pack(side='left')
        for status in ['preparing', 'ready', 'delivered', 'cancelled']:
            ttk.Button(action_bar, text=status.title(),
                       command=lambda s=status: self._set_status(s)
                       ).pack(side='left', padx=2)

        paned = ttk.PanedWindow(frame, orient='horizontal')
        paned.pack(fill='both', expand=True)

        orders_frame = ttk.Frame(paned)
        paned.add(orders_frame, weight=2)
        o_cols = ('order_id', 'number', 'customer', 'date', 'total', 'status')
        self.orders_tree = ttk.Treeview(orders_frame, columns=o_cols,
                                        show='headings', selectmode='browse')
        for key, title, width in [
            ('order_id', 'ID', 60), ('number', 'Order #', 120),
            ('customer', 'Customer', 180), ('date', 'Placed', 140),
            ('total', 'Total', 90), ('status', 'Status', 110),
        ]:
            self.orders_tree.heading(key, text=title)
            self.orders_tree.column(key, width=width,
                                    anchor='w' if key == 'customer'
                                                  else 'center')
        o_vsb = ttk.Scrollbar(orders_frame, orient='vertical',
                              command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=o_vsb.set)
        self.orders_tree.pack(side='left', fill='both', expand=True)
        o_vsb.pack(side='right', fill='y')
        self.orders_tree.bind('<<TreeviewSelect>>', self._load_order_items)
        self.orders_tree.tag_configure('pending', background='#fef9e7')
        self.orders_tree.tag_configure('ready', background='#d5f5e3')
        self.orders_tree.tag_configure('cancelled', foreground='#888')

        items_frame = ttk.LabelFrame(paned, text="Items in selected order",
                                     padding=4)
        paned.add(items_frame, weight=1)
        i_cols = ('item_name', 'qty', 'unit', 'subtotal')
        self.items_tree = ttk.Treeview(items_frame, columns=i_cols,
                                       show='headings', height=14)
        for key, title, width in [
            ('item_name', 'Item', 180), ('qty', 'Qty', 60),
            ('unit', 'Unit £', 80), ('subtotal', 'Subtotal', 100),
        ]:
            self.items_tree.heading(key, text=title)
            self.items_tree.column(key, width=width,
                                   anchor='w' if key == 'item_name'
                                                 else 'center')
        i_vsb = ttk.Scrollbar(items_frame, orient='vertical',
                              command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=i_vsb.set)
        self.items_tree.pack(side='left', fill='both', expand=True)
        i_vsb.pack(side='right', fill='y')

    def _build_products_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Menu / Stock")

        ttk.Label(frame, text=f"Available {self._pal['singular']}s for "
                              f"this {self.feature_label.lower()}.",
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('name', 'category', 'price', 'stock', 'available')
        self.prod_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Name', 300), ('category', 'Category', 150),
            ('price', 'Price £', 110), ('stock', 'Stock', 100),
            ('available', 'Available', 110),
        ]:
            self.prod_tree.heading(key, text=title)
            self.prod_tree.column(key, width=width,
                                  anchor='w' if key in ('name', 'category')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.prod_tree.yview)
        self.prod_tree.configure(yscrollcommand=vsb.set)
        self.prod_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.prod_tree.tag_configure('low', background='#fde5e0')

    # ------------------------------------------------------------------

    def _load_orders(self):
        for i in self.orders_tree.get_children():
            self.orders_tree.delete(i)
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)

        clauses = ["source_type = ?"]
        params = [self.source_type]
        scope = self.scope_var.get()
        if scope == 'Open':
            clauses.append("order_status IN ('pending', 'preparing', 'ready')")
        elif scope == 'Today':
            today = datetime.now().date().isoformat()
            clauses.append("date(order_date) = ?")
            params.append(today)

        sql = (
            "SELECT order_id, order_number, "
            "       COALESCE(customer_name, student_id, customer_id, ''), "
            "       order_date, total_amount, order_status "
            "FROM orders WHERE " + " AND ".join(clauses) +
            " ORDER BY order_date DESC LIMIT 500"
        )
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for oid, num, cust, date, total, status in rows:
            tag = ()
            if status == 'pending':
                tag = ('pending',)
            elif status == 'ready':
                tag = ('ready',)
            elif status == 'cancelled':
                tag = ('cancelled',)
            total_str = f"{total:.2f}" if total is not None else ''
            self.orders_tree.insert('', 'end', iid=str(oid), values=(
                oid, num or '', cust or '',
                (date or '')[:16], total_str, status or ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} order(s).")

    def _load_order_items(self, _event=None):
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        sel = self.orders_tree.selection()
        if not sel:
            return
        oid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT item_name, quantity, unit_price, subtotal "
                    "FROM order_items WHERE order_id = ? "
                    "ORDER BY item_id",
                    (oid,)
                )
                for row in cur.fetchall():
                    up = f"{row[2]:.2f}" if row[2] is not None else ''
                    sub = f"{row[3]:.2f}" if row[3] is not None else ''
                    self.items_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or 0, up, sub
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _set_status(self, new_status):
        sel = self.orders_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an order first.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE orders SET order_status = ?, updated_at = ? "
                    "WHERE order_id = ? AND source_type = ?",
                    (new_status,
                     datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]), self.source_type)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self.info_var.set(f"Order {sel[0]} → {new_status}.")
        self._load_orders()

    def _load_products(self):
        for i in self.prod_tree.get_children():
            self.prod_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, category, price, stock_quantity, "
                    "       min_stock_level, is_available, is_active "
                    "FROM products WHERE source_type = ? "
                    "ORDER BY category, name LIMIT 500",
                    (self.source_type,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for name, cat, price, stock, minstock, avail, active in rows:
            tag = ()
            if stock is not None and minstock and stock <= minstock:
                tag = ('low',)
            price_str = f"{price:.2f}" if price is not None else ''
            avail_label = ('Yes' if (avail and active) else 'No')
            self.prod_tree.insert('', 'end', values=(
                name or '', cat or '', price_str,
                stock if stock is not None else '',
                avail_label
            ), tags=tag)


class CommerceStudentPortal:
    """Browse menu, build cart, place an order, see my orders."""

    def __init__(self, parent, auth, source_type, feature_label):
        self.auth = auth
        self.source_type = source_type
        self.feature_label = feature_label
        self._pal = _PALETTE.get(source_type, _PALETTE['cafe'])

        user = (auth.current_user if auth else None) or {}
        self.student_id = str(user.get('student_id') or user.get('username')
                              or user.get('user_id') or '')
        self.user_id = user.get('id') or user.get('user_id')
        self.customer_name = user.get('display_name') or user.get('username', '')
        self.customer_email = user.get('email', '')

        self.window = tk.Toplevel(parent)
        self.window.title(self._pal['student_title'])
        self.window.geometry("1080x700")
        self.window.minsize(920, 580)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.cart = {}  # product_id -> {'name', 'price', 'qty'}
        self.search_var = tk.StringVar()
        self.info_var = tk.StringVar(value="")

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg=self._pal['bg'], height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"{self.feature_label} — "
                              f"{self.customer_name}",
                 font=('Arial', 14, 'bold'),
                 bg=self._pal['bg'], fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg=self._pal['accent'], fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg=self._pal['accent'], fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_menu_tab(nb)
        self._build_cart_tab(nb)
        self._build_orders_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_menu_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Menu")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_menu())
        ttk.Button(bar, text="Search",
                   command=self._load_menu).pack(side='left')
        ttk.Button(bar, text="Add to Cart",
                   command=self._add_to_cart).pack(side='right')

        cols = ('name', 'category', 'price', 'stock')
        self.menu_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Name', 340),
            ('category', 'Category', 160),
            ('price', 'Price £', 110),
            ('stock', 'In stock', 120),
        ]:
            self.menu_tree.heading(key, text=title)
            self.menu_tree.column(key, width=width,
                                  anchor='w' if key in ('name', 'category')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.menu_tree.yview)
        self.menu_tree.configure(yscrollcommand=vsb.set)
        self.menu_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _build_cart_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Cart")

        ttk.Label(frame, text="Items in your cart",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('name', 'price', 'qty', 'subtotal')
        self.cart_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Item', 340), ('price', 'Price £', 110),
            ('qty', 'Qty', 80), ('subtotal', 'Subtotal £', 120),
        ]:
            self.cart_tree.heading(key, text=title)
            self.cart_tree.column(key, width=width,
                                  anchor='w' if key == 'name' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=vsb.set)
        self.cart_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=(6, 0))
        ttk.Button(actions, text="Remove Selected",
                   command=self._remove_from_cart).pack(side='left')
        ttk.Button(actions, text="Clear Cart",
                   command=self._clear_cart).pack(side='left', padx=4)
        self.total_var = tk.StringVar(value="Total: £0.00")
        ttk.Label(actions, textvariable=self.total_var,
                  font=('Arial', 11, 'bold')).pack(side='left', padx=16)
        ttk.Button(actions, text="Place Order",
                   command=self._place_order).pack(side='right')

    def _build_orders_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Orders")

        ttk.Label(frame, text="My past and current orders",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('number', 'date', 'total', 'status')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('number', 'Order #', 160), ('date', 'Placed', 160),
            ('total', 'Total £', 120), ('status', 'Status', 120),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width, anchor='center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_menu()
        self._load_mine()
        self._refresh_cart()

    def _load_menu(self):
        for i in self.menu_tree.get_children():
            self.menu_tree.delete(i)
        query = self.search_var.get().strip()
        clauses = ["source_type = ?",
                   "COALESCE(is_active, 1) = 1",
                   "COALESCE(is_available, 1) = 1"]
        params = [self.source_type]
        if query:
            like = f"%{query}%"
            clauses.append("(name LIKE ? OR category LIKE ? "
                           " OR description LIKE ?)")
            params.extend([like, like, like])
        sql = ("SELECT product_id, name, category, price, stock_quantity "
               "FROM products WHERE " + " AND ".join(clauses) +
               " ORDER BY category, name LIMIT 500")
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for pid, name, cat, price, stock in rows:
            price_str = f"{price:.2f}" if price is not None else ''
            self.menu_tree.insert('', 'end', iid=str(pid), values=(
                name or '', cat or '', price_str,
                stock if stock is not None else 'n/a'
            ))
        self.info_var.set(f"{len(rows)} available item(s).")

    def _add_to_cart(self):
        sel = self.menu_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Pick an item first.",
                                parent=self.window)
            return
        pid = int(sel[0])
        vals = self.menu_tree.item(sel[0], 'values')
        name = vals[0]
        try:
            price = float(vals[2] or 0)
        except ValueError:
            price = 0.0

        qty = tk.simpledialog.askinteger(
            "Quantity",
            f"How many '{name}'?",
            parent=self.window, minvalue=1, maxvalue=99, initialvalue=1,
        )
        if not qty:
            return
        if pid in self.cart:
            self.cart[pid]['qty'] += qty
        else:
            self.cart[pid] = {'name': name, 'price': price, 'qty': qty}
        self._refresh_cart()

    def _remove_from_cart(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        self.cart.pop(pid, None)
        self._refresh_cart()

    def _clear_cart(self):
        self.cart.clear()
        self._refresh_cart()

    def _refresh_cart(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        total = 0.0
        for pid, entry in self.cart.items():
            sub = entry['price'] * entry['qty']
            total += sub
            self.cart_tree.insert('', 'end', iid=str(pid), values=(
                entry['name'], f"{entry['price']:.2f}",
                entry['qty'], f"{sub:.2f}"
            ))
        self.total_var.set(f"Total: £{total:.2f}")

    def _place_order(self):
        if not self.cart:
            messagebox.showinfo("Empty Cart",
                                "Add items before placing an order.",
                                parent=self.window)
            return
        total = sum(e['price'] * e['qty'] for e in self.cart.values())
        order_number = (f"{self.source_type[:3].upper()}-"
                        f"{datetime.now().strftime('%Y%m%d%H%M%S')}")
        now = datetime.now().isoformat(timespec='seconds')

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO orders "
                    "(source_type, order_number, customer_id, customer_name, "
                    " customer_email, student_id, user_id, "
                    " order_date, subtotal, total_amount, "
                    " payment_status, order_status, "
                    " created_by, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "        'pending', 'pending', ?, ?, ?)",
                    (self.source_type, order_number,
                     self.user_id, self.customer_name,
                     self.customer_email, self.student_id, self.user_id,
                     now, total, total,
                     self.user_id, now, now)
                )
                oid = cur.lastrowid
                for pid, entry in self.cart.items():
                    sub = entry['price'] * entry['qty']
                    cur.execute(
                        "INSERT INTO order_items "
                        "(source_type, order_id, product_id, item_name, "
                        " quantity, unit_price, subtotal, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (self.source_type, oid, pid, entry['name'],
                         entry['qty'], entry['price'], sub, now)
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Order Failed", str(e),
                                 parent=self.window)
            return

        messagebox.showinfo("Order Placed",
                            f"Order {order_number} placed. "
                            f"Total £{total:.2f}.",
                            parent=self.window)
        self.cart.clear()
        self._refresh_all()

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        ids = [x for x in [self.student_id, str(self.user_id)] if x]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT order_number, order_date, total_amount, "
                    f"       order_status "
                    f"FROM orders WHERE source_type = ? "
                    f"  AND (student_id IN ({placeholders}) "
                    f"       OR user_id IN ({placeholders})) "
                    f"ORDER BY order_date DESC LIMIT 500",
                    [self.source_type, *ids, *ids]
                )
                for row in cur.fetchall():
                    total_str = (f"{row[2]:.2f}"
                                 if row[2] is not None else '')
                    self.mine_tree.insert('', 'end', values=(
                        row[0] or '', (row[1] or '')[:16],
                        total_str, row[3] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)


# tkinter.simpledialog is needed for the qty prompt.
import tkinter.simpledialog  # noqa: E402
tk.simpledialog = tkinter.simpledialog  # so the portal can use tk.simpledialog


# ----------------------------------------------------------------------
# Feature-specific launchers
# ----------------------------------------------------------------------


def launch_cafe_staff_portal(parent, auth):
    return CommerceStaffPortal(parent, auth, 'cafe', 'Cafe')


def launch_cafe_student_portal(parent, auth):
    return CommerceStudentPortal(parent, auth, 'cafe', 'Cafe')


def launch_bar_staff_portal(parent, auth):
    return CommerceStaffPortal(parent, auth, 'bar', 'Bar')


def launch_bar_student_portal(parent, auth):
    return CommerceStudentPortal(parent, auth, 'bar', 'Bar')


def launch_takeaway_staff_portal(parent, auth):
    return CommerceStaffPortal(parent, auth, 'takeaway', 'Takeaway')


def launch_takeaway_student_portal(parent, auth):
    return CommerceStudentPortal(parent, auth, 'takeaway', 'Takeaway')
