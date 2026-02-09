"""
Restaurant Order Placement Module

Provides comprehensive order placement functionality including:
- Menu browsing with categories and search
- Shopping cart with item quantities
- Customer selection/creation
- Tax calculation
- Order submission
- Optional immediate payment processing
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from typing import Optional, Dict, List
import uuid

# Import database connection
from university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection

# Import finance integration
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        record_payment_to_finance
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False


def init_order_items_table():
    """Initialize restaurant_order_items table if it doesn't exist"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                special_instructions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id),
                FOREIGN KEY (item_id) REFERENCES menu_items(item_id)
            )
        ''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing order_items table: {e}")
        return False


class PlaceOrderWindow:
    """Window for placing new restaurant orders"""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.window = tk.Toplevel(parent)
        self.window.title("Place New Order")
        self.window.geometry("1200x800")

        # Initialize order_items table
        init_order_items_table()

        # Cart storage
        self.cart = []  # List of {item_id, name, price, quantity, special_instructions}
        self.selected_customer_id = None
        self.selected_customer_name = "Walk-in Customer"

        # Get current user details
        self.current_user = None
        self.current_user_email = None
        self.current_student_id = None
        self.load_current_user()

        # Tax rate (20% VAT in UK)
        self.tax_rate = 0.20

        self.create_widgets()
        self.load_menu_items()

        # Auto-select current user as customer if logged in
        self.auto_select_current_user()

    def load_current_user(self):
        """Load current user details from auth system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                current_user = self.auth.current_user

                if isinstance(current_user, dict):
                    self.current_user = current_user
                    username = current_user.get('username', '')
                    student_id = current_user.get('student_id', '')
                    user_id = current_user.get('id', '')

                    # Try to get email from users table
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()

                        # Try by student_id first
                        if student_id:
                            self.current_student_id = student_id
                            cursor.execute('''
                                SELECT email, first_name, last_name
                                FROM students
                                WHERE student_id = ?
                            ''', (student_id,))
                            result = cursor.fetchone()

                            if result and result[0]:
                                self.current_user_email = result[0]
                                first_name = result[1] or ''
                                last_name = result[2] or ''
                                self.selected_customer_name = f"{first_name} {last_name}".strip() or student_id

                        # Fallback to users table
                        if not self.current_user_email:
                            cursor.execute('''
                                SELECT email FROM users
                                WHERE username = ? OR id = ?
                            ''', (username, user_id))
                            result = cursor.fetchone()
                            if result and result[0]:
                                self.current_user_email = result[0]

                        conn.close()

                    print(f"✓ Loaded current user: {self.selected_customer_name} ({self.current_user_email or 'no email'})")

        except Exception as e:
            print(f"Warning: Could not load current user details: {e}")

    def auto_select_current_user(self):
        """Automatically select current user as customer if logged in"""
        if self.current_user and self.current_student_id:
            # Try to find or create customer record for current user
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Check if customer exists (using student_id as name)
                    cursor.execute('''
                        SELECT customer_id, name FROM restaurant_customers
                        WHERE name = ?
                    ''', (self.current_student_id,))

                    result = cursor.fetchone()

                    if result:
                        # Customer exists
                        self.selected_customer_id = result[0]
                        print(f"✓ Auto-selected existing customer: {self.selected_customer_name}")
                    else:
                        # Create customer record
                        cursor.execute('''
                            INSERT INTO restaurant_customers (name, email)
                            VALUES (?, ?)
                        ''', (self.current_student_id, self.current_user_email))
                        self.selected_customer_id = cursor.lastrowid
                        conn.commit()
                        print(f"✓ Created and auto-selected customer: {self.selected_customer_name}")

                    conn.close()

                    # Update UI
                    if hasattr(self, 'customer_label'):
                        self.customer_label.config(
                            text=f"Customer: {self.selected_customer_name} (You)",
                            foreground='green'
                        )
            except Exception as e:
                print(f"Warning: Could not auto-select current user: {e}")

    def create_widgets(self):
        """Create all UI widgets"""
        # Main container with two panels
        main_pane = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Menu items
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=2)

        # Menu header
        menu_header = ttk.Frame(left_frame)
        menu_header.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(menu_header, text="Menu Items", font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search and filter
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_menu())
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="Category:").pack(side=tk.LEFT, padx=(20, 5))
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(search_frame, textvariable=self.category_var,
                                          values=["All"], width=15, state='readonly')
        self.category_combo.pack(side=tk.LEFT, padx=5)
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_menu())

        ttk.Checkbutton(search_frame, text="Vegetarian Only",
                       variable=tk.BooleanVar(), command=self.filter_menu).pack(side=tk.LEFT, padx=10)

        # Menu items treeview
        menu_frame = ttk.Frame(left_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'name', 'category', 'price', 'veg', 'available')
        self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show='headings', height=20)

        self.menu_tree.heading('id', text='ID')
        self.menu_tree.heading('name', text='Item Name')
        self.menu_tree.heading('category', text='Category')
        self.menu_tree.heading('price', text='Price (£)')
        self.menu_tree.heading('veg', text='V/VG')
        self.menu_tree.heading('available', text='Available')

        self.menu_tree.column('id', width=40)
        self.menu_tree.column('name', width=200)
        self.menu_tree.column('category', width=100)
        self.menu_tree.column('price', width=80)
        self.menu_tree.column('veg', width=60)
        self.menu_tree.column('available', width=80)

        scrollbar = ttk.Scrollbar(menu_frame, orient=tk.VERTICAL, command=self.menu_tree.yview)
        self.menu_tree.configure(yscrollcommand=scrollbar.set)

        self.menu_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to add to cart
        self.menu_tree.bind('<Double-1>', lambda e: self.add_to_cart())

        # Add to cart button
        ttk.Button(left_frame, text="Add to Cart",
                  command=self.add_to_cart).pack(pady=10)

        # Right panel - Order details and cart
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        # Customer selection
        customer_frame = ttk.LabelFrame(right_frame, text="Customer Information", padding="10")
        customer_frame.pack(fill=tk.X, pady=(0, 10))

        self.customer_label = ttk.Label(customer_frame, text=f"Customer: {self.selected_customer_name}",
                                       font=('Arial', 10, 'bold'))
        self.customer_label.pack(anchor=tk.W)

        # Show email if available
        if self.current_user_email:
            self.email_label = ttk.Label(customer_frame,
                                         text=f"Email: {self.current_user_email}",
                                         font=('Arial', 9),
                                         foreground='gray')
            self.email_label.pack(anchor=tk.W)

        btn_frame = ttk.Frame(customer_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(btn_frame, text="Select Different Customer",
                  command=self.select_customer).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Walk-in",
                  command=self.set_walkin).pack(side=tk.LEFT, padx=5)

        # Cart
        cart_frame = ttk.LabelFrame(right_frame, text="Order Cart", padding="10")
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cart_columns = ('name', 'qty', 'price', 'total')
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns, show='headings', height=12)

        self.cart_tree.heading('name', text='Item')
        self.cart_tree.heading('qty', text='Qty')
        self.cart_tree.heading('price', text='Price')
        self.cart_tree.heading('total', text='Total')

        self.cart_tree.column('name', width=150)
        self.cart_tree.column('qty', width=50)
        self.cart_tree.column('price', width=60)
        self.cart_tree.column('total', width=60)

        cart_scroll = ttk.Scrollbar(cart_frame, orient=tk.VERTICAL, command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)

        self.cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cart_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Cart buttons
        cart_btn_frame = ttk.Frame(cart_frame)
        cart_btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(cart_btn_frame, text="Remove Item",
                  command=self.remove_from_cart).pack(side=tk.LEFT, padx=5)
        ttk.Button(cart_btn_frame, text="Update Qty",
                  command=self.update_quantity).pack(side=tk.LEFT, padx=5)
        ttk.Button(cart_btn_frame, text="Clear Cart",
                  command=self.clear_cart).pack(side=tk.LEFT, padx=5)

        # Order summary
        summary_frame = ttk.LabelFrame(right_frame, text="Order Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        self.subtotal_label = ttk.Label(summary_frame, text="Subtotal: £0.00")
        self.subtotal_label.pack(anchor=tk.W)

        self.tax_label = ttk.Label(summary_frame, text=f"Tax (20%): £0.00")
        self.tax_label.pack(anchor=tk.W)

        self.total_label = ttk.Label(summary_frame, text="Total: £0.00",
                                    font=('Arial', 12, 'bold'))
        self.total_label.pack(anchor=tk.W, pady=(5, 0))

        # Action buttons
        action_frame = ttk.Frame(right_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(action_frame, text="Place Order",
                  command=self.place_order, style='Accent.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="Place Order & Pay",
                  command=self.place_order_and_pay).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="Cancel",
                  command=self.window.destroy).pack(fill=tk.X, pady=2)

    def load_menu_items(self):
        """Load menu items from database"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_id, name, category, price, vegetarian, vegan, available
                FROM menu_items
                WHERE available = 1
                ORDER BY category, name
            ''')

            self.menu_items = cursor.fetchall()

            # Get unique categories
            cursor.execute('''
                SELECT DISTINCT category FROM menu_items
                WHERE category IS NOT NULL AND category != ''
                ORDER BY category
            ''')
            categories = ['All'] + [row[0] for row in cursor.fetchall()]
            self.category_combo['values'] = categories

            conn.close()

            self.display_menu_items(self.menu_items)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load menu: {e}")

    def display_menu_items(self, items):
        """Display menu items in treeview"""
        for item in self.menu_tree.get_children():
            self.menu_tree.delete(item)

        for item in items:
            item_id, name, category, price, vegetarian, vegan, available = item

            # Vegetarian/Vegan indicator
            veg_indicator = ""
            if vegan:
                veg_indicator = "VG"
            elif vegetarian:
                veg_indicator = "V"

            available_text = "Yes" if available else "No"

            self.menu_tree.insert('', tk.END, values=(
                item_id, name, category or 'N/A', f"{price:.2f}",
                veg_indicator, available_text
            ))

    def filter_menu(self):
        """Filter menu items by search and category"""
        search_term = self.search_var.get().lower()
        category = self.category_var.get()

        filtered = []
        for item in self.menu_items:
            item_id, name, item_cat, price, veg, vegan, available = item

            # Category filter
            if category != "All" and item_cat != category:
                continue

            # Search filter
            if search_term and search_term not in name.lower():
                continue

            filtered.append(item)

        self.display_menu_items(filtered)

    def add_to_cart(self):
        """Add selected menu item to cart"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a menu item to add")
            return

        values = self.menu_tree.item(selection[0])['values']
        item_id = values[0]
        item_name = values[1]
        item_price = float(values[3])

        # Ask for quantity
        quantity = simpledialog.askinteger("Quantity",
                                          f"How many '{item_name}'?",
                                          initialvalue=1, minvalue=1, maxvalue=99)
        if not quantity:
            return

        # Ask for special instructions
        instructions = simpledialog.askstring("Special Instructions",
                                             f"Any special instructions for '{item_name}'?\n(Leave empty if none)")

        # Check if item already in cart
        for cart_item in self.cart:
            if cart_item['item_id'] == item_id and cart_item['special_instructions'] == instructions:
                cart_item['quantity'] += quantity
                self.update_cart_display()
                return

        # Add new item to cart
        self.cart.append({
            'item_id': item_id,
            'name': item_name,
            'price': item_price,
            'quantity': quantity,
            'special_instructions': instructions or ""
        })

        self.update_cart_display()
        messagebox.showinfo("Added", f"Added {quantity}x {item_name} to cart")

    def remove_from_cart(self):
        """Remove selected item from cart"""
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a cart item to remove")
            return

        item_index = self.cart_tree.index(selection[0])
        item_name = self.cart[item_index]['name']

        if messagebox.askyesno("Confirm", f"Remove '{item_name}' from cart?"):
            del self.cart[item_index]
            self.update_cart_display()

    def update_quantity(self):
        """Update quantity of selected cart item"""
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a cart item to update")
            return

        item_index = self.cart_tree.index(selection[0])
        cart_item = self.cart[item_index]

        new_qty = simpledialog.askinteger("Update Quantity",
                                         f"New quantity for '{cart_item['name']}':",
                                         initialvalue=cart_item['quantity'],
                                         minvalue=1, maxvalue=99)
        if new_qty:
            cart_item['quantity'] = new_qty
            self.update_cart_display()

    def clear_cart(self):
        """Clear all items from cart"""
        if self.cart and messagebox.askyesno("Confirm", "Clear all items from cart?"):
            self.cart.clear()
            self.update_cart_display()

    def update_cart_display(self):
        """Update cart treeview and totals"""
        # Clear cart display
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        # Calculate totals
        subtotal = 0

        # Display cart items
        for cart_item in self.cart:
            item_total = cart_item['price'] * cart_item['quantity']
            subtotal += item_total

            display_name = cart_item['name']
            if cart_item['special_instructions']:
                display_name += f" *"

            self.cart_tree.insert('', tk.END, values=(
                display_name,
                cart_item['quantity'],
                f"£{cart_item['price']:.2f}",
                f"£{item_total:.2f}"
            ))

        # Calculate tax and total
        tax = subtotal * self.tax_rate
        total = subtotal + tax

        # Update labels
        self.subtotal_label.config(text=f"Subtotal: £{subtotal:.2f}")
        self.tax_label.config(text=f"Tax (20%): £{tax:.2f}")
        self.total_label.config(text=f"Total: £{total:.2f}")

    def select_customer(self):
        """Show dialog to select existing customer"""
        dialog = CustomerSelectionDialog(self.window)
        if dialog.result:
            self.selected_customer_id = dialog.result['customer_id']
            self.selected_customer_name = dialog.result['name']
            self.customer_label.config(text=f"Customer: {self.selected_customer_name}")

    def create_customer(self):
        """Show dialog to create new customer"""
        dialog = NewCustomerDialog(self.window)
        if dialog.result:
            self.selected_customer_id = dialog.result['customer_id']
            self.selected_customer_name = dialog.result['name']
            self.customer_label.config(text=f"Customer: {self.selected_customer_name}")

    def set_walkin(self):
        """Set customer as walk-in"""
        self.selected_customer_id = None
        self.selected_customer_name = "Walk-in Customer"
        self.customer_label.config(text=f"Customer: {self.selected_customer_name}")

    def send_order_receipt_email(self, order_id, total, payment_method=None, order_items=None):
        """Send email receipt to current user"""
        if not self.current_user_email:
            print("No email address available for receipt")
            return False

        try:
            from university_system.infrastructure.email.email_service import send_email
            from university_system.infrastructure.email.template_utils import render_template

            # Build order items text
            items_text = ""
            if order_items:
                items_text = "\n".join([
                    f"  {item['quantity']}x {item['name']} - £{item['price']:.2f} each = £{item['price'] * item['quantity']:.2f}" +
                    (f"\n     Note: {item['special_instructions']}" if item['special_instructions'] else "")
                    for item in order_items
                ])

            # Determine status text
            status_text = f"Paid via {payment_method}" if payment_method else "Pending Payment"

            # Calculate subtotal and tax
            subtotal = total / (1 + self.tax_rate)
            tax = total - subtotal

            # Build payment method text
            payment_method_text = f"Payment Method: {payment_method}" if payment_method else "Please pay at the restaurant to complete your order."

            # Render email from template
            subject, body = render_template('commerce/restaurant_order_confirmation',
                customer_name=self.selected_customer_name,
                order_id=order_id,
                order_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                status_text=status_text,
                items_text=items_text,
                subtotal=f"{subtotal:.2f}",
                tax=f"{tax:.2f}",
                total=f"{total:.2f}",
                payment_method_text=payment_method_text
            )

            success = send_email(
                recipient_email=self.current_user_email,
                subject=subject,
                body=body
            )

            if success:
                print(f"✓ Order receipt sent to {self.current_user_email}")
                return True
            else:
                print(f"✗ Failed to send receipt to {self.current_user_email}")
                return False

        except Exception as e:
            print(f"✗ Error sending receipt email: {e}")
            return False

    def place_order(self):
        """Place order without payment"""
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Please add items to cart before placing order")
            return

        if not messagebox.askyesno("Confirm Order",
                                  f"Place order for {self.selected_customer_name}?"):
            return

        try:
            # Calculate totals
            subtotal = sum(item['price'] * item['quantity'] for item in self.cart)
            tax = subtotal * self.tax_rate
            total = subtotal + tax

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create order
            cursor.execute('''
                INSERT INTO restaurant_orders
                (customer_id, order_time, total_price, tax_amount, status, payment_method)
                VALUES (?, ?, ?, ?, 'Pending', NULL)
            ''', (self.selected_customer_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  total, tax))

            order_id = cursor.lastrowid

            # Create order items
            for cart_item in self.cart:
                item_subtotal = cart_item['price'] * cart_item['quantity']
                cursor.execute('''
                    INSERT INTO restaurant_order_items
                    (order_id, item_id, item_name, quantity, unit_price, subtotal, special_instructions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (order_id, cart_item['item_id'], cart_item['name'],
                      cart_item['quantity'], cart_item['price'], item_subtotal,
                      cart_item['special_instructions']))

            # Update customer total spent if applicable
            if self.selected_customer_id:
                cursor.execute('''
                    UPDATE restaurant_customers
                    SET total_spent = total_spent + ?
                    WHERE customer_id = ?
                ''', (total, self.selected_customer_id))

            conn.commit()
            conn.close()

            # Send email receipt
            receipt_sent = self.send_order_receipt_email(order_id, total, order_items=self.cart)

            success_message = f"Order #{order_id} placed successfully!\n\n" \
                            f"Total: £{total:.2f}\n" \
                            f"Status: Pending Payment"

            if receipt_sent:
                success_message += f"\n\n✓ Receipt emailed to {self.current_user_email}"
            elif self.current_user_email:
                success_message += f"\n\n⚠ Could not send email receipt"

            messagebox.showinfo("Success", success_message)

            # Clear cart and close window
            self.cart.clear()
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to place order:\n{e}")

    def place_order_and_pay(self):
        """Place order and immediately process payment"""
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Please add items to cart before placing order")
            return

        # Calculate totals first
        subtotal = sum(item['price'] * item['quantity'] for item in self.cart)
        tax = subtotal * self.tax_rate
        total = subtotal + tax

        # Show payment method dialog
        payment_dialog = PaymentMethodDialog(self.window, total, self.selected_customer_id,
                                             self.current_student_id)
        if not payment_dialog.result:
            return  # User cancelled

        payment_method = payment_dialog.result['method']

        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create order
            cursor.execute('''
                INSERT INTO restaurant_orders
                (customer_id, order_time, total_price, tax_amount, status, payment_method)
                VALUES (?, ?, ?, ?, 'Paid', ?)
            ''', (self.selected_customer_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  total, tax, payment_method))

            order_id = cursor.lastrowid

            # Create order items
            for cart_item in self.cart:
                item_subtotal = cart_item['price'] * cart_item['quantity']
                cursor.execute('''
                    INSERT INTO restaurant_order_items
                    (order_id, item_id, item_name, quantity, unit_price, subtotal, special_instructions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (order_id, cart_item['item_id'], cart_item['name'],
                      cart_item['quantity'], cart_item['price'], item_subtotal,
                      cart_item['special_instructions']))

            # Update customer total spent if applicable
            if self.selected_customer_id:
                cursor.execute('''
                    UPDATE restaurant_customers
                    SET total_spent = total_spent + ?,
                        loyalty_points = loyalty_points + ?
                    WHERE customer_id = ?
                ''', (total, int(total), self.selected_customer_id))

            # Process student account payment if applicable
            if payment_method == 'Student Account' and FINANCE_AVAILABLE:
                # Use current student ID or get from customer
                student_id = self.current_student_id
                if not student_id:
                    cursor.execute('SELECT name FROM restaurant_customers WHERE customer_id = ?',
                                 (self.selected_customer_id,))
                    result_row = cursor.fetchone()
                    student_id = result_row[0] if result_row else None

                if student_id:
                    result = process_student_finance_account_payment(
                        student_id=student_id,
                        amount=total,
                        description=f"Restaurant Order #{order_id}",
                        transaction_source='Restaurant',
                        transaction_ref=f"ORDER-{order_id}",
                        processed_by=self.auth.current_user.get('username') if self.auth and hasattr(self.auth, 'current_user') else 'system'
                    )

                    if not result.get('success'):
                        conn.rollback()
                        conn.close()
                        messagebox.showerror("Payment Failed", result.get('message', 'Payment failed'))
                        return

            conn.commit()
            conn.close()

            # Send email receipt
            receipt_sent = self.send_order_receipt_email(order_id, total, payment_method, self.cart)

            success_message = f"Order #{order_id} placed and paid!\n\n" \
                            f"Total: £{total:.2f}\n" \
                            f"Payment: {payment_method}\n" \
                            f"Status: Paid"

            if receipt_sent:
                success_message += f"\n\n✓ Receipt emailed to {self.current_user_email}"
            elif self.current_user_email:
                success_message += f"\n\n⚠ Could not send email receipt"

            messagebox.showinfo("Success", success_message)

            # Clear cart and close window
            self.cart.clear()
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to place order:\n{e}")


class CustomerSelectionDialog:
    """Dialog for selecting existing customer"""

    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Customer")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Search
        search_frame = ttk.Frame(self.dialog, padding="10")
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=search_var, width=30).pack(side=tk.LEFT, padx=10)
        ttk.Button(search_frame, text="Search",
                  command=lambda: self.load_customers(search_var.get())).pack(side=tk.LEFT)

        # Customer list
        list_frame = ttk.Frame(self.dialog, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'name', 'email', 'phone', 'tier')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings')

        self.tree.heading('id', text='ID')
        self.tree.heading('name', text='Name')
        self.tree.heading('email', text='Email')
        self.tree.heading('phone', text='Phone')
        self.tree.heading('tier', text='Tier')

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', lambda e: self.select())

        # Buttons
        btn_frame = ttk.Frame(self.dialog, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Select", command=self.select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

        self.load_customers()

    def load_customers(self, search_term=""):
        """Load customers from database"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if search_term:
                cursor.execute('''
                    SELECT customer_id, name, email, phone, loyalty_tier
                    FROM restaurant_customers
                    WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
                    ORDER BY name
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT customer_id, name, email, phone, loyalty_tier
                    FROM restaurant_customers
                    ORDER BY name
                    LIMIT 100
                ''')

            for item in self.tree.get_children():
                self.tree.delete(item)

            for row in cursor.fetchall():
                self.tree.insert('', tk.END, values=row)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {e}")

    def select(self):
        """Select customer"""
        selection = self.tree.selection()
        if not selection:
            return

        values = self.tree.item(selection[0])['values']
        self.result = {
            'customer_id': values[0],
            'name': values[1]
        }
        self.dialog.destroy()


class NewCustomerDialog:
    """Dialog for creating new customer"""

    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Customer")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5)

        # Email
        ttk.Label(frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=30).grid(row=1, column=1, pady=5)

        # Phone
        ttk.Label(frame, text="Phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.phone_var, width=30).grid(row=2, column=1, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Create", command=self.create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def create(self):
        """Create new customer"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter customer name")
            return

        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO restaurant_customers (name, email, phone)
                VALUES (?, ?, ?)
            ''', (name, self.email_var.get().strip(), self.phone_var.get().strip()))

            customer_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.result = {
                'customer_id': customer_id,
                'name': name
            }
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create customer:\n{e}")


class PaymentMethodDialog:
    """Dialog for selecting payment method"""

    def __init__(self, parent, amount, customer_id=None, student_id=None):
        self.result = None
        self.amount = amount
        self.customer_id = customer_id
        self.student_id = student_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Payment Method")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Amount
        ttk.Label(frame, text=f"Amount: £{amount:.2f}",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Payment methods
        self.method_var = tk.StringVar(value="Cash")

        methods = [
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("Student Account", "Student Account")
        ]

        for text, value in methods:
            ttk.Radiobutton(frame, text=text, variable=self.method_var,
                          value=value).pack(anchor=tk.W, pady=5)

        # Show student balance if student_id provided
        if student_id and FINANCE_AVAILABLE:
            try:
                balance = get_student_finance_account_balance(student_id)
                if balance is not None:
                    balance_color = 'green' if balance >= amount else 'red'
                    ttk.Label(frame, text=f"Your Student Account Balance: £{balance:.2f}",
                            font=('Arial', 10, 'bold'),
                            foreground=balance_color).pack(pady=10)

                    if balance < amount:
                        ttk.Label(frame, text="⚠ Insufficient funds for Student Account payment",
                                font=('Arial', 9),
                                foreground='red').pack()
                else:
                    ttk.Label(frame, text="Student Account: Not found",
                            font=('Arial', 9),
                            foreground='orange').pack(pady=10)
            except Exception as e:
                print(f"Could not check balance: {e}")
        elif customer_id and FINANCE_AVAILABLE:
            # Fallback to old method if no student_id
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT name FROM restaurant_customers WHERE customer_id = ?',
                             (customer_id,))
                row = cursor.fetchone()
                conn.close()

                if row:
                    balance = get_student_finance_account_balance(row[0])
                    if balance is not None:
                        balance_color = 'green' if balance >= amount else 'red'
                        ttk.Label(frame, text=f"Student Account Balance: £{balance:.2f}",
                                font=('Arial', 9),
                                foreground=balance_color).pack(pady=5)
            except:
                pass

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Confirm", command=self.confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def confirm(self):
        """Confirm payment method"""
        method = self.method_var.get()

        # Validate student account has sufficient funds
        if method == "Student Account" and self.student_id and FINANCE_AVAILABLE:
            try:
                balance = get_student_finance_account_balance(self.student_id)
                if balance is None:
                    messagebox.showerror("Error", "Student account not found", parent=self.dialog)
                    return
                if balance < self.amount:
                    if not messagebox.askyesno("Insufficient Funds",
                                              f"Your balance (£{balance:.2f}) is less than the order total (£{self.amount:.2f}).\n\n"
                                              "Continue anyway?",
                                              parent=self.dialog):
                        return
            except Exception as e:
                messagebox.showerror("Error", f"Could not verify balance: {e}", parent=self.dialog)
                return

        self.result = {'method': method}
        self.dialog.destroy()


def create_place_order_tab(self, parent):
    """Create place order tab in restaurant GUI"""
    order_frame = ttk.Frame(parent)
    order_frame.pack(fill=tk.BOTH, expand=True)  # Pack the frame into parent!

    # Header
    header_frame = ttk.Frame(order_frame)
    header_frame.pack(fill=tk.X, pady=10, padx=10)

    ttk.Label(header_frame, text="Place New Order",
             font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

    ttk.Button(header_frame, text="Open Order Window",
              command=lambda: PlaceOrderWindow(self.root, self.auth)).pack(side=tk.RIGHT)

    # Instructions
    instructions = """
Welcome to the Order Placement System!

Click "Open Order Window" to:
• Browse menu items by category
• Add items to cart with quantities
• Select or create customers
• Review order with tax calculation
• Place orders for kitchen preparation
• Optionally process payment immediately

Features:
✓ Real-time menu filtering and search
✓ Shopping cart with quantity management
✓ Customer selection and creation
✓ Automatic tax calculation (20% VAT)
✓ Special instructions for each item
✓ Multiple payment methods (Cash, Card, Student Account)
✓ Loyalty points for registered customers
"""

    text_widget = tk.Text(order_frame, wrap=tk.WORD, height=20, font=('Arial', 10))
    text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    text_widget.insert('1.0', instructions)
    text_widget.config(state='disabled')

    return order_frame
