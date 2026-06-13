"""
Cafe System - Point of Sale tab mixin
Handles POS UI, order building, and payment processing
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.commerce.gui.cafe_common import get_db_connection, FINANCE_ACCOUNT_AVAILABLE, EMAIL_SERVICE_AVAILABLE

try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        record_payment_to_finance
    )
except ImportError:
    pass


class CafePOSMixin:
    """Mixin for Point of Sale tab functionality"""

    def create_pos_tab(self):
        """Create Point of Sale tab"""
        pos_frame = ttk.Frame(self.notebook)
        self.notebook.add(pos_frame, text=_t("cafe.tab_pos"))

        # Configure grid
        pos_frame.columnconfigure(0, weight=1)
        pos_frame.columnconfigure(1, weight=1)
        pos_frame.rowconfigure(0, weight=1)

        # Left side - Menu items
        left_frame = ttk.LabelFrame(pos_frame, text=_t("cafe.pos.menu_items"), padding="10")
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)

        # Category filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("cafe.pos.category")).pack(side=tk.LEFT, padx=5)
        self.category_filter = ttk.Combobox(filter_frame, state='readonly')
        self.category_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', lambda e: self.load_menu_items_for_pos())

        ttk.Button(filter_frame, text=_t("cafe.pos.all"), command=lambda: self.reset_category_filter()).pack(side=tk.LEFT, padx=5)

        # Menu items list with scrollbar
        items_frame = ttk.Frame(left_frame)
        items_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(items_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.menu_items_listbox = tk.Listbox(
            items_frame,
            yscrollcommand=scrollbar.set,
            font=('Courier', 10),
            height=20
        )
        self.menu_items_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.menu_items_listbox.yview)

        # Double-click to add item
        self.menu_items_listbox.bind('<Double-Button-1>', lambda e: self.add_item_to_order())

        # Add button
        ttk.Button(left_frame, text=_t("cafe.pos.add_to_order"), command=self.add_item_to_order).pack(pady=5)

        # Right side - Current order (using grid for proper layout control)
        right_frame = ttk.LabelFrame(pos_frame, text=_t("cafe.pos.current_order"), padding="10")
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 10), pady=10)

        # Configure right_frame grid - row 1 (order tree) expands, others don't
        right_frame.rowconfigure(0, weight=0)  # User info
        right_frame.rowconfigure(1, weight=1)  # Order tree - expands
        right_frame.rowconfigure(2, weight=0)  # Controls
        right_frame.rowconfigure(3, weight=0)  # Total
        right_frame.rowconfigure(4, weight=0)  # Payment buttons
        right_frame.columnconfigure(0, weight=1)

        # Row 0: Current user info display (read-only, from userauth)
        user_info_frame = ttk.LabelFrame(right_frame, text=_t("cafe.pos.customer_info"), padding="5")
        user_info_frame.grid(row=0, column=0, sticky='ew', pady=(0, 5))

        user_display = self.get_current_user_display_info()
        self.user_info_label = ttk.Label(
            user_info_frame,
            text=user_display,
            font=('Helvetica', 10)
        )
        self.user_info_label.pack(anchor='w', padx=5, pady=2)

        # Row 1: Order items tree (this one expands)
        tree_frame = ttk.Frame(right_frame)
        tree_frame.grid(row=1, column=0, sticky='nsew', pady=5)

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.order_tree = ttk.Treeview(
            tree_frame,
            columns=('Item', 'Qty', 'Price', 'Subtotal'),
            show='headings',
            yscrollcommand=tree_scroll.set,
            height=8
        )
        tree_scroll.config(command=self.order_tree.yview)

        self.order_tree.heading('Item', text=_t("cafe.columns.item"))
        self.order_tree.heading('Qty', text=_t("cafe.columns.qty"))
        self.order_tree.heading('Price', text=_t("cafe.columns.price"))
        self.order_tree.heading('Subtotal', text=_t("cafe.columns.subtotal"))

        self.order_tree.column('Item', width=180)
        self.order_tree.column('Qty', width=50)
        self.order_tree.column('Price', width=70)
        self.order_tree.column('Subtotal', width=70)

        self.order_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Row 2: Order controls
        controls_frame = ttk.Frame(right_frame)
        controls_frame.grid(row=2, column=0, sticky='ew', pady=5)

        ttk.Button(controls_frame, text=_t("cafe.pos.remove_selected"), command=self.remove_order_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_t("cafe.pos.clear_order"), command=self.clear_order).pack(side=tk.LEFT, padx=5)

        # Row 3: Total display
        total_frame = ttk.Frame(right_frame)
        total_frame.grid(row=3, column=0, sticky='ew', pady=5)

        ttk.Label(total_frame, text=_t("cafe.pos.total"), font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT, padx=5)
        self.total_label = ttk.Label(total_frame, text=_t("cafe.info.initial_total"), font=('Helvetica', 14, 'bold'))
        self.total_label.pack(side=tk.LEFT, padx=5)

        # Row 4: Payment buttons frame
        payment_frame = ttk.LabelFrame(right_frame, text=_t("cafe.pos.payment_method"), padding="8")
        payment_frame.grid(row=4, column=0, sticky='ew', pady=(5, 0))

        # Configure payment grid columns
        payment_frame.columnconfigure(0, weight=1)
        payment_frame.columnconfigure(1, weight=1)

        ttk.Button(
            payment_frame,
            text=_t("cafe.pos.finance_account"),
            command=lambda: self.process_payment('finance_account')
        ).grid(row=0, column=0, padx=3, pady=4, sticky='ew')

        ttk.Button(
            payment_frame,
            text=_t("cafe.pos.cash"),
            command=lambda: self.process_payment('cash')
        ).grid(row=0, column=1, padx=3, pady=4, sticky='ew')

        ttk.Button(
            payment_frame,
            text=_t("cafe.pos.debit_card"),
            command=lambda: self.process_payment('debit_card')
        ).grid(row=1, column=0, padx=3, pady=4, sticky='ew')

        ttk.Button(
            payment_frame,
            text=_t("cafe.pos.credit_card"),
            command=lambda: self.process_payment('credit_card')
        ).grid(row=1, column=1, padx=3, pady=4, sticky='ew')

        # Load initial data
        self.load_categories()
        self.load_menu_items_for_pos()

    def load_categories(self):
        """Load available categories for filtering"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'cafe' ORDER BY category")
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()

            self.category_filter['values'] = ['All'] + categories
            self.category_filter.set('All')
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_categories", error=str(e)))

    def load_menu_items_for_pos(self):
        """Load menu items for POS display"""
        try:
            self.menu_items_listbox.delete(0, tk.END)
            self.menu_item_map.clear()

            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            category = self.category_filter.get()
            if category and category != 'All':
                cursor.execute(
                    "SELECT product_id, name, price, is_available FROM products WHERE source_type = 'cafe' AND category = ? AND is_available = 1 ORDER BY name",
                    (category,)
                )
            else:
                cursor.execute("SELECT product_id, name, price, is_available FROM products WHERE source_type = 'cafe' AND is_available = 1 ORDER BY category, name")

            items = cursor.fetchall()
            conn.close()

            for idx, item in enumerate(items):
                item_id, name, price, available = item
                display_text = f"{name:<30} £{price:>6.2f}"
                self.menu_items_listbox.insert(tk.END, display_text)
                # Store item_id in dictionary mapping (Listbox doesn't support tags)
                self.menu_item_map[idx] = {'item_id': item_id, 'name': name, 'price': price}

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.load_menu_items", error=str(e)))

    def reset_category_filter(self):
        """Reset category filter to show all items"""
        self.category_filter.set('All')
        self.load_menu_items_for_pos()

    def add_item_to_order(self):
        """Add selected menu item to current order"""
        try:
            selection = self.menu_items_listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_add"))
                return

            index = selection[0]

            # Get item details from the mapping dictionary
            if index not in self.menu_item_map:
                messagebox.showerror(_t("common.error"), _t("cafe.messages.item_not_found"))
                return

            item_data = self.menu_item_map[index]
            item_id = item_data['item_id']
            name = item_data['name']
            price = item_data['price']

            # Ask for quantity
            quantity = simpledialog.askinteger(_t("cafe.columns.quantity"), f"Enter quantity for {name}:", minvalue=1, initialvalue=1)
            if not quantity:
                return

            # Check if item already in order
            for child in self.order_tree.get_children():
                values = self.order_tree.item(child, 'values')
                if values[0] == name:
                    # Update quantity
                    old_qty = int(values[1])
                    new_qty = old_qty + quantity
                    subtotal = price * new_qty
                    self.order_tree.item(child, values=(name, new_qty, f'£{price:.2f}', f'£{subtotal:.2f}'))
                    self.update_order_total()
                    return

            # Add new item
            subtotal = price * quantity
            self.order_tree.insert('', tk.END, values=(
                name, quantity, f'£{price:.2f}', f'£{subtotal:.2f}'
            ), tags=(str(item_id),))

            self.update_order_total()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.add_item_fail", error=str(e)))

    def remove_order_item(self):
        """Remove selected item from order"""
        selection = self.order_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.select_item_remove"))
            return

        for item in selection:
            self.order_tree.delete(item)

        self.update_order_total()

    def clear_order(self):
        """Clear all items from current order"""
        if messagebox.askyesno(_t("common.confirm"), _t("cafe.messages.confirm_clear")):
            for item in self.order_tree.get_children():
                self.order_tree.delete(item)
            self.update_order_total()

    def update_order_total(self):
        """Update the order total display"""
        total = 0.0
        for item in self.order_tree.get_children():
            values = self.order_tree.item(item, 'values')
            subtotal_text = values[3].replace('£', '')
            total += float(subtotal_text)

        self.total_label.config(text=f'£{total:.2f}')

    def send_cafe_receipt_email(self, order_id, student_id, customer_name, total, payment_method, order_items):
        """Send email receipt for cafe purchase"""
        if not EMAIL_SERVICE_AVAILABLE:
            return False

        from education_system.university_system.infrastructure.email.email_service import send_email

        # Get email from current user (already fetched from users table)
        email_address = None
        student_name = customer_name

        # First try current user's email (most reliable, already fetched from DB)
        if self.current_user:
            email_address = self.current_user.get('email')
            if self.current_user.get('full_name'):
                student_name = self.current_user.get('full_name')

        # Fallback: try to get from student_info if still no email
        if not email_address and student_id and FINANCE_ACCOUNT_AVAILABLE:
            student_info = get_student_info(student_id)
            if student_info:
                email_address = student_info.get('email')
                if not student_name or student_name == customer_name:
                    student_name = student_info.get('full_name', customer_name)

        if not email_address:
            print(f"No email address found for order #{order_id}")
            return False

        # Build order items list for receipt
        items_text = ""
        for item in order_items:
            item_name, qty, unit_price, subtotal = item
            items_text += f"  {item_name:<25} x{qty}  £{unit_price:.2f}  =  £{subtotal:.2f}\n"

        # Format payment method for display
        payment_display = {
            'finance_account': 'Student Finance Account',
            'cash': 'Cash',
            'debit_card': 'Debit Card',
            'credit_card': 'Credit Card',
            'student_account': 'Student Finance Account'
        }.get(payment_method, payment_method.replace('_', ' ').title())

        # Prepare template variables
        from education_system.university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': student_name,
            'order_id': order_id,
            'order_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'customer_name': customer_name,
            'payment_display': payment_display,
            'items_text': items_text,
            'total': f"{total:.2f}"
        }

        subject, body = render_template('commerce/cafe_receipt', template_vars)
        if not subject or not body:
            print("Failed to render email template")
            return False

        try:
            result = send_email(email_address, subject, body)
            if result:
                print(f"Receipt email sent to {email_address} for order #{order_id}")
            return result
        except Exception as e:
            print(f"Failed to send receipt email: {e}")
            return False

    def process_payment(self, payment_method):
        """Process payment for current order with finance integration and email receipt"""
        # Check if order has items
        if not self.order_tree.get_children():
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_items_order"))
            return

        # Get total
        total_text = self.total_label.cget('text').replace('£', '')
        total = float(total_text)

        # Get customer info from current authenticated user
        if not self.current_user:
            messagebox.showerror(_t("common.error"), _t("cafe.messages.no_user_login"))
            return

        # Use student_id if available, otherwise use username as account identifier
        student_id = self.current_user.get('student_id')
        if not student_id:
            # For non-students (admin, staff), use username as the account identifier
            student_id = self.current_user.get('username', '')

        user_id = str(self.current_user.get('id', ''))

        # Get customer name from user info
        customer_name = self.current_user.get('full_name')
        if not customer_name:
            first = self.current_user.get('first_name', '')
            last = self.current_user.get('last_name', '')
            if first or last:
                customer_name = f"{first} {last}".strip()
            else:
                customer_name = self.current_user.get('username', 'Unknown')

        # Collect order items for receipt
        order_items_data = []
        for item in self.order_tree.get_children():
            values = self.order_tree.item(item, 'values')
            item_name = values[0]
            quantity = int(values[1])
            unit_price = float(values[2].replace('£', ''))
            subtotal = float(values[3].replace('£', ''))
            order_items_data.append((item_name, quantity, unit_price, subtotal))

        conn = None
        try:
            # Process finance account payment (deducts from user balance)
            if payment_method in ('finance_account', 'student_account'):
                if not student_id:
                    messagebox.showerror(_t("common.error"), _t("cafe.messages.student_id_required"))
                    return

                if not FINANCE_ACCOUNT_AVAILABLE:
                    messagebox.showerror(_t("common.error"), _t("cafe.messages.finance_not_available"))
                    return

                # Check if account exists, create if not
                balance = get_student_finance_account_balance(student_id)
                if balance is None:
                    # Auto-create finance account for this user
                    self._ensure_finance_account_exists(student_id)
                    balance = get_student_finance_account_balance(student_id)
                    if balance is None:
                        messagebox.showerror(_t("common.error"), f"Could not create finance account for {student_id}")
                        return
                    messagebox.showinfo(_t("common.info"), _t("cafe.messages.account_created", name=customer_name, balance=f"{balance:.2f}"))

                if balance < total:
                    messagebox.showerror(_t("common.error"), _t("cafe.messages.insufficient_balance", balance=f"{balance:.2f}", required=f"{total:.2f}"))
                    return

                # Generate order reference for this transaction
                order_ref = f"CAFE-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Process payment through finance system (this also records to payments table)
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=total,
                    description="Cafe Purchase",
                    transaction_source="Cafe",
                    transaction_ref=order_ref,
                    processed_by=self.current_user.get('username', 'System') if self.current_user else 'System'
                )

                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), _t("cafe.messages.payment_failed", error=result.get('message', 'Unknown error')))
                    return

            # Save order to unified orders table
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Map payment method for display
            payment_method_display = {
                'finance_account': 'Finance Account',
                'student_account': 'Finance Account',
                'cash': 'Cash',
                'debit_card': 'Debit Card',
                'credit_card': 'Credit Card'
            }.get(payment_method, payment_method)

            # Insert order
            cursor.execute('''
                INSERT INTO orders (source_type, student_id, customer_name, total_amount, payment_method, order_status)
                VALUES ('cafe', ?, ?, ?, ?, 'completed')
            ''', (student_id or None, customer_name, total, payment_method_display))

            order_id = cursor.lastrowid

            # Insert order items and update inventory
            for item_name, quantity, unit_price, subtotal in order_items_data:
                # Get item_id
                cursor.execute("SELECT product_id FROM products WHERE source_type = 'cafe' AND name = ?", (item_name,))
                result = cursor.fetchone()
                if result:
                    item_id = result[0]

                    # Insert order item
                    cursor.execute('''
                        INSERT INTO order_items (source_type, source_order_id, product_id, item_name, quantity, unit_price, subtotal)
                        VALUES ('cafe', ?, ?, ?, ?, ?, ?)
                    ''', (order_id, item_id, item_name, quantity, unit_price, subtotal))

                    # Update inventory
                    cursor.execute('''
                        UPDATE products
                        SET stock_quantity = stock_quantity - ?
                        WHERE product_id = ? AND source_type = 'cafe'
                    ''', (quantity, item_id))

                    # Log inventory transaction
                    cursor.execute('''
                        INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes)
                        VALUES ('cafe_inventory', ?, 'item', ?, 'sale', ?)
                    ''', (item_id, -quantity, f'Order #{order_id}'))

            conn.commit()

            # Record payment to finance system for non-finance-account payments
            # (Finance account payments are already recorded by process_student_finance_account_payment)
            if payment_method not in ('finance_account', 'student_account') and FINANCE_ACCOUNT_AVAILABLE:
                # Record to main finance payments table for revenue tracking
                record_payment_to_finance(
                    student_id=student_id or 'WALK-IN',
                    amount=total,
                    payment_method=payment_method_display,
                    transaction_source='Cafe',
                    transaction_ref=f'ORDER-{order_id}',
                    currency='GBP',
                    status='completed',
                    notes=f'Cafe order #{order_id} - {len(order_items_data)} item(s)',
                    created_by=self.current_user.get('username', 'System') if self.current_user else 'System'
                )

            conn.close()

            # Send email receipt
            receipt_sent = self.send_cafe_receipt_email(
                order_id=order_id,
                student_id=student_id,
                customer_name=customer_name,
                total=total,
                payment_method=payment_method,
                order_items=order_items_data
            )

            # Show success message
            receipt_msg = "\n" + _t("cafe.messages.receipt_sent") if receipt_sent else ""
            messagebox.showinfo(
                _t("common.success"),
                _t("cafe.messages.order_completed",
                   id=order_id,
                   total=f"{total:.2f}",
                   payment=payment_method_display,
                   receipt=receipt_msg)
            )

            # Clear order
            for item in self.order_tree.get_children():
                self.order_tree.delete(item)
            self.update_order_total()

            # Refresh orders tab
            self.load_orders()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.process_payment", error=str(e)))
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
