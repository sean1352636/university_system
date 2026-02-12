"""
Takeaway System GUI for University Management System
Campus food ordering and delivery interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from university_system.infrastructure.database.db import sqlite3
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection

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

from university_system.modules.domain.commerce.services.takeaway.takeaway_service import (
    init_takeaway_db,
    get_restaurants,
    get_menu_items,
    add_to_cart,
    view_cart,
    clear_cart,
    place_order,
    get_order_history,
    get_order_details,
    rate_order,
)

# Email integration
from university_system.infrastructure.email.email_service import send_email

# Finance integration for account details and revenue recording
from university_system.modules.shared.utils.finance_integration import (
    get_student_info,
    get_student_finance_account_balance,
    process_student_finance_account_payment,
    record_revenue_to_finance,
)

# Housing integration for delivery address
from university_system.modules.shared.constants import paths

class TakeawayGUI:
    """Takeaway ordering system GUI"""

    def __init__(self, root, auth=None, return_to_main=None):
        self.root = root
        self.return_to_main = return_to_main

        # Initialize i18n for multi-language support
        init_i18n()

        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("takeaway.auth_required_title"),
                _t("takeaway.auth_not_available")
            )
            return

        if not init_takeaway_db():
            messagebox.showerror(_t("common.error"), _t("takeaway.db_init_failed"))
            return

        self.current_user = None
        self.setup_current_user()
        self.current_restaurant = None

    def setup_current_user(self):
        """Setup current user from auth"""
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self.current_user = self.auth.current_user
        else:
            self.current_user = {'id': 0, 'username': 'Guest', 'role': 'guest'}

    def get_student_housing_address(self, student_id):
        """
        Get student's housing assignment address for delivery.
        Returns dict with building and room info, or None if not found.
        """
        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get active housing assignment for the student
            cursor.execute('''
                SELECT b.building_name, b.address, r.room_number, r.floor_number
                FROM housing_assignments a
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE a.student_id = ? AND a.status = 'active'
                ORDER BY a.move_in_date DESC
                LIMIT 1
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                building_name, address, room_number, floor_number = result
                room_label = _t("takeaway.room_label")
                return {
                    'building': building_name,
                    'address': address,
                    'room': room_number,
                    'floor': floor_number,
                    'full_address': f"{building_name}, {room_label} {room_number}"
                }
            return None

        except sqlite3.Error as e:
            print(f"Error getting housing address: {e}")
            return None

    def send_order_receipt_email(self, order_id, user_id, order_details, items):
        """
        Send order receipt email to the student.

        Args:
            order_id: The order ID
            user_id: Student/user ID
            order_details: Dict with order info (restaurant_name, total_amount, delivery_address, etc.)
            items: List of order items
        """
        try:
            # Get student info
            student_info = get_student_info(user_id)
            if not student_info or not student_info.get('email'):
                print(f"Cannot send receipt: No email found for user {user_id}")
                return False

            student_email = student_info['email']
            student_name = student_info.get('full_name', 'Valued Customer')

            # Format items list
            items_text = ""
            for item in items:
                line_total = item['price'] * item['quantity']
                items_text += f"  - {item['name']} x{item['quantity']} - £{line_total:.2f}\n"

            # Build email body with translations
            na_text = _t("takeaway.na")
            subject = _t("takeaway.email_subject", order_id=order_id)
            body = f"""{_t("takeaway.email_greeting", name=student_name)}

{_t("takeaway.email_thank_you")}

═══════════════════════════════════════════════════════
              {_t("takeaway.email_header")}
═══════════════════════════════════════════════════════

{_t("takeaway.email_order_details")}
--------------
{_t("takeaway.email_order_id")}           {order_id}
{_t("takeaway.email_date_time")}        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{_t("takeaway.email_restaurant")}         {order_details.get('restaurant_name', na_text)}

{_t("takeaway.email_items_ordered")}
{items_text}
{_t("takeaway.email_subtotal")}           £{order_details.get('subtotal', 0):.2f}
{_t("takeaway.email_delivery_fee")}       £{order_details.get('delivery_fee', 0):.2f}
═══════════════════════════════════════════════════════
{_t("takeaway.email_total")}              £{order_details.get('total_amount', 0):.2f}
═══════════════════════════════════════════════════════

{_t("takeaway.email_delivery_type")}      {order_details.get('delivery_type', na_text).title()}
{_t("takeaway.email_delivery_address")}   {order_details.get('delivery_address', na_text)}
{_t("takeaway.email_payment_method")}     {order_details.get('payment_method', na_text).replace('_', ' ').title()}

{_t("takeaway.email_preparing")}

{_t("takeaway.email_contact")}

{_t("takeaway.email_regards")}
{_t("takeaway.email_signature")}

---
{_t("takeaway.email_footer")}
"""

            result = send_email(student_email, subject, body)
            if result:
                print(f"Receipt email sent to {student_email}")
                return True
            else:
                print(f"Failed to send receipt email to {student_email}")
                return False

        except Exception as e:
            print(f"Error sending receipt email: {e}")
            return False

    def get_user_finance_balance(self, user_id):
        """Get user's finance account balance for display."""
        balance = get_student_finance_account_balance(user_id)
        return balance if balance is not None else 0.0

    def get_user_identifier(self):
        """
        Get the correct identifier for finance/housing lookups.
        Uses student_id if available, otherwise username.
        """
        # Try student_id first (for student users)
        student_id = self.current_user.get('student_id')
        if student_id:
            return str(student_id)

        # Fall back to username (for admin/staff users)
        username = self.current_user.get('username')
        if username:
            return username

        # Last resort: use numeric id
        return str(self.current_user.get('id', 0))

    def open_takeaway_gui(self):
        """Open the takeaway ordering window"""
        self.takeaway_window = tk.Toplevel(self.root)
        self.takeaway_window.title(_t("takeaway.window_title"))
        self.takeaway_window.geometry("900x700")
        self.takeaway_window.transient(self.root)

        # Main container
        main_frame = ttk.Frame(self.takeaway_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = ttk.Label(header_frame, text=_t("takeaway.header_title"), font=('Arial', 18, 'bold'))
        self.title_label.pack(side=tk.LEFT)

        # Cart button
        self.cart_btn = ttk.Button(header_frame, text=_t("takeaway.cart", count=0), command=self.show_cart)
        self.cart_btn.pack(side=tk.RIGHT, padx=5)

        self.order_history_btn = ttk.Button(header_frame, text=_t("takeaway.order_history"), command=self.show_order_history)
        self.order_history_btn.pack(side=tk.RIGHT, padx=5)

        # Language button
        self.lang_btn = ttk.Button(
            header_frame,
            text=f"{_t('menu.language')}: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Restaurants tab
        self.restaurants_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.restaurants_frame, text=_t("takeaway.tab_restaurants"))

        # Menu tab (initially hidden, shown when restaurant selected)
        self.menu_frame = ttk.Frame(self.notebook)

        # Refunds tab
        self.create_refunds_tab()

        self.setup_restaurants_tab()
        self.update_cart_count()

    def change_language(self):
        """Open language selector and refresh UI on change"""
        old_lang = get_current_language()
        show_gui_language_selector(self.takeaway_window)
        new_lang = get_current_language()
        if old_lang != new_lang:
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change"""
        # Close and reopen the window to apply language changes
        self.takeaway_window.destroy()
        self.open_takeaway_gui()

    def setup_restaurants_tab(self):
        """Setup the restaurants listing"""
        # Search/filter frame
        filter_frame = ttk.Frame(self.restaurants_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text=_t("takeaway.filter_by_cuisine")).pack(side=tk.LEFT, padx=5)
        self.cuisine_values = [
            _t("takeaway.cuisine_all"),
            _t("takeaway.cuisine_italian"),
            _t("takeaway.cuisine_chinese"),
            _t("takeaway.cuisine_american"),
            _t("takeaway.cuisine_indian"),
            _t("takeaway.cuisine_japanese"),
            _t("takeaway.cuisine_mediterranean")
        ]
        self.cuisine_filter = ttk.Combobox(filter_frame, values=self.cuisine_values)
        self.cuisine_filter.set(self.cuisine_values[0])
        self.cuisine_filter.pack(side=tk.LEFT, padx=5)
        self.cuisine_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_restaurants())

        ttk.Button(filter_frame, text=_t("common.refresh"), command=self.refresh_restaurants).pack(side=tk.RIGHT, padx=5)

        # Restaurants list
        list_frame = ttk.Frame(self.restaurants_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('name', 'cuisine', 'rating', 'delivery_fee', 'min_order', 'time', 'status')
        self.restaurant_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.restaurant_tree.heading('name', text=_t("takeaway.col_restaurant"))
        self.restaurant_tree.heading('cuisine', text=_t("takeaway.col_cuisine"))
        self.restaurant_tree.heading('rating', text=_t("takeaway.col_rating"))
        self.restaurant_tree.heading('delivery_fee', text=_t("takeaway.col_delivery"))
        self.restaurant_tree.heading('min_order', text=_t("takeaway.col_min_order"))
        self.restaurant_tree.heading('time', text=_t("takeaway.col_est_time"))
        self.restaurant_tree.heading('status', text=_t("takeaway.col_status"))

        self.restaurant_tree.column('name', width=150)
        self.restaurant_tree.column('cuisine', width=100)
        self.restaurant_tree.column('rating', width=80)
        self.restaurant_tree.column('delivery_fee', width=80)
        self.restaurant_tree.column('min_order', width=80)
        self.restaurant_tree.column('time', width=80)
        self.restaurant_tree.column('status', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.restaurant_tree.yview)
        self.restaurant_tree.configure(yscrollcommand=scrollbar.set)

        self.restaurant_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.restaurant_tree.bind('<Double-1>', self.on_restaurant_select)

        # Buttons
        btn_frame = ttk.Frame(self.restaurants_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text=_t("takeaway.view_menu"), command=self.view_selected_menu).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.close"), command=self.takeaway_window.destroy).pack(side=tk.RIGHT, padx=5)

        self.refresh_restaurants()

    def refresh_restaurants(self):
        """Refresh the restaurants list"""
        for item in self.restaurant_tree.get_children():
            self.restaurant_tree.delete(item)

        restaurants = get_restaurants()
        cuisine_filter = self.cuisine_filter.get()
        all_text = _t("takeaway.cuisine_all")

        for r in restaurants:
            if cuisine_filter != all_text and r['cuisine_type'] != cuisine_filter:
                continue

            status = _t("takeaway.status_open") if r['is_open'] else _t("takeaway.status_closed")
            rating = f"{'*' * int(r['rating'])} ({r['rating']:.1f})"

            self.restaurant_tree.insert('', tk.END, values=(
                r['name'],
                r['cuisine_type'],
                rating,
                f"${r['delivery_fee']:.2f}",
                f"${r['min_order_amount']:.2f}",
                f"{r['estimated_delivery_time']} min",
                status
            ), tags=(r['restaurant_id'],))

    def on_restaurant_select(self, event):
        """Handle restaurant double-click"""
        self.view_selected_menu()

    def view_selected_menu(self):
        """View the menu for selected restaurant"""
        selection = self.restaurant_tree.selection()
        if not selection:
            messagebox.showinfo(_t("takeaway.select_restaurant_title"), _t("takeaway.select_restaurant_msg"))
            return

        item = self.restaurant_tree.item(selection[0])
        restaurant_id = item['tags'][0]
        restaurant_name = item['values'][0]

        # Get restaurant details
        restaurants = get_restaurants()
        self.current_restaurant = next((r for r in restaurants if r['restaurant_id'] == restaurant_id), None)

        if self.current_restaurant:
            self.show_menu(restaurant_id, restaurant_name)

    def show_menu(self, restaurant_id, restaurant_name):
        """Show menu for a restaurant"""
        # Clear and setup menu frame
        for widget in self.menu_frame.winfo_children():
            widget.destroy()

        # Add menu tab if not exists (should be 3rd tab after Restaurants and Refunds)
        if len(self.notebook.tabs()) < 3:
            self.notebook.add(self.menu_frame, text=f"{_t('takeaway.tab_menu')} - {restaurant_name}")
        else:
            # Update the menu tab (index 2) with the restaurant name
            self.notebook.tab(2, text=f"{_t('takeaway.tab_menu')} - {restaurant_name}")

        # Select the menu tab (index 2: Restaurants=0, Refunds=1, Menu=2)
        self.notebook.select(2)

        # Header
        header = ttk.Frame(self.menu_frame)
        header.pack(fill=tk.X, pady=5)

        ttk.Label(header, text=restaurant_name, font=('Arial', 14, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text=_t("takeaway.back_to_restaurants"), command=lambda: self.notebook.select(0)).pack(side=tk.RIGHT)

        # Menu items
        menu_items = get_menu_items(restaurant_id)

        # Group by category
        categories = {}
        for item in menu_items:
            cat = item['category'] or _t("takeaway.category_other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        # Scrollable menu
        canvas = tk.Canvas(self.menu_frame)
        scrollbar = ttk.Scrollbar(self.menu_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for category, items in categories.items():
            cat_frame = ttk.LabelFrame(scrollable_frame, text=category, padding=10)
            cat_frame.pack(fill=tk.X, pady=5, padx=5)

            for item in items:
                self.create_menu_item_widget(cat_frame, item, restaurant_id)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_menu_item_widget(self, parent, item, restaurant_id):
        """Create a widget for a menu item"""
        item_frame = ttk.Frame(parent)
        item_frame.pack(fill=tk.X, pady=2)

        # Item info
        info_frame = ttk.Frame(item_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        name_text = item['name']
        dietary = []
        if item['is_vegetarian']:
            dietary.append(_t("takeaway.dietary_vegetarian"))
        if item['is_vegan']:
            dietary.append(_t("takeaway.dietary_vegan"))
        if item['is_gluten_free']:
            dietary.append(_t("takeaway.dietary_gluten_free"))
        if dietary:
            name_text += f" [{', '.join(dietary)}]"

        ttk.Label(info_frame, text=name_text, font=('Arial', 10, 'bold')).pack(anchor='w')
        if item['description']:
            ttk.Label(info_frame, text=item['description'], foreground='gray').pack(anchor='w')

        # Price and add button
        action_frame = ttk.Frame(item_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Label(action_frame, text=f"${item['price']:.2f}", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)

        qty_var = tk.StringVar(value="1")
        qty_spinbox = ttk.Spinbox(action_frame, from_=1, to=10, width=3, textvariable=qty_var)
        qty_spinbox.pack(side=tk.LEFT, padx=2)

        add_btn = ttk.Button(action_frame, text=_t("common.add"),
                            command=lambda i=item, q=qty_var: self.add_item_to_cart(restaurant_id, i, q))
        add_btn.pack(side=tk.LEFT, padx=2)

    def add_item_to_cart(self, restaurant_id, item, qty_var):
        """Add item to cart"""
        try:
            quantity = int(qty_var.get())
        except ValueError:
            quantity = 1

        user_id = self.current_user.get('id', 0)

        if add_to_cart(user_id, restaurant_id, item['item_id'], quantity):
            messagebox.showinfo(_t("takeaway.added_title"), _t("takeaway.added_msg", quantity=quantity, name=item['name']))
            self.update_cart_count()
        else:
            messagebox.showerror(_t("common.error"), _t("takeaway.add_failed"))

    def update_cart_count(self):
        """Update cart button count"""
        user_id = self.current_user.get('id', 0)
        items, _, _ = view_cart(user_id)
        total_items = sum(item['quantity'] for item in items)
        self.cart_btn.config(text=_t("takeaway.cart", count=total_items))

    def show_cart(self):
        """Show shopping cart"""
        user_id = self.current_user.get('id', 0)
        items, subtotal, restaurant_name = view_cart(user_id)

        cart_window = tk.Toplevel(self.takeaway_window)
        cart_window.title(_t("takeaway.your_cart"))
        cart_window.geometry("500x500")
        cart_window.transient(self.takeaway_window)

        main_frame = ttk.Frame(cart_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        if not items:
            ttk.Label(main_frame, text=_t("takeaway.cart_empty"), font=('Arial', 14)).pack(pady=50)
            ttk.Button(main_frame, text=_t("common.close"), command=cart_window.destroy).pack()
            return

        ttk.Label(main_frame, text=_t("takeaway.order_from", restaurant=restaurant_name), font=('Arial', 12, 'bold')).pack(anchor='w')

        # Items list
        items_frame = ttk.Frame(main_frame)
        items_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        delivery_fee = items[0]['delivery_fee']
        min_order = items[0]['min_order_amount']

        for item in items:
            item_frame = ttk.Frame(items_frame)
            item_frame.pack(fill=tk.X, pady=2)

            line_total = item['price'] * item['quantity']
            ttk.Label(item_frame, text=f"{item['name']} x{item['quantity']}").pack(side=tk.LEFT)
            ttk.Label(item_frame, text=f"${line_total:.2f}").pack(side=tk.RIGHT)

        # Totals
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        totals_frame = ttk.Frame(main_frame)
        totals_frame.pack(fill=tk.X)

        ttk.Label(totals_frame, text=_t("takeaway.subtotal")).pack(side=tk.LEFT)
        ttk.Label(totals_frame, text=f"${subtotal:.2f}").pack(side=tk.RIGHT)

        fee_frame = ttk.Frame(main_frame)
        fee_frame.pack(fill=tk.X)
        ttk.Label(fee_frame, text=_t("takeaway.delivery_fee")).pack(side=tk.LEFT)
        ttk.Label(fee_frame, text=f"${delivery_fee:.2f}").pack(side=tk.RIGHT)

        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=5)
        ttk.Label(total_frame, text=_t("takeaway.total"), font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        ttk.Label(total_frame, text=f"${subtotal + delivery_fee:.2f}", font=('Arial', 11, 'bold')).pack(side=tk.RIGHT)

        if subtotal < min_order:
            ttk.Label(main_frame, text=_t("takeaway.min_order_warning", min_order=min_order, needed=(min_order - subtotal)),
                     foreground='red').pack()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        checkout_btn = ttk.Button(btn_frame, text=_t("takeaway.checkout"),
                                 command=lambda: self.checkout(cart_window),
                                 state=tk.NORMAL if subtotal >= min_order else tk.DISABLED)
        checkout_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text=_t("takeaway.clear_cart"),
                  command=lambda: self.clear_cart_action(cart_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.close"), command=cart_window.destroy).pack(side=tk.RIGHT, padx=5)

    def clear_cart_action(self, window):
        """Clear the cart"""
        if messagebox.askyesno(_t("takeaway.clear_cart"), _t("takeaway.clear_cart_confirm")):
            user_id = self.current_user.get('id', 0)
            clear_cart(user_id)
            self.update_cart_count()
            window.destroy()

    def checkout(self, cart_window):
        """Process checkout with finance and housing integration"""
        # Get cart info before closing cart window
        user_id = self.current_user.get('id', 0)
        cart_items, subtotal, restaurant_name = view_cart(user_id)

        if not cart_items:
            messagebox.showerror(_t("common.error"), _t("takeaway.cart_empty"))
            return

        delivery_fee = cart_items[0]['delivery_fee'] if cart_items else 0
        total_amount = subtotal + delivery_fee

        cart_window.destroy()

        checkout_window = tk.Toplevel(self.takeaway_window)
        checkout_window.title(_t("takeaway.checkout"))
        checkout_window.geometry("480x600")
        checkout_window.transient(self.takeaway_window)

        # Create scrollable container
        container = ttk.Frame(checkout_window)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding=15)

        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Unbind mousewheel when window closes
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            checkout_window.destroy()

        checkout_window.protocol("WM_DELETE_WINDOW", on_close)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(main_frame, text=_t("takeaway.checkout"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Order summary
        summary_frame = ttk.LabelFrame(main_frame, text=_t("takeaway.order_summary"), padding=5)
        summary_frame.pack(fill=tk.X, pady=5)
        ttk.Label(summary_frame, text=_t("takeaway.restaurant_name").format(name=restaurant_name)).pack(anchor='w')
        ttk.Label(summary_frame, text=_t("takeaway.subtotal_amount").format(amount=subtotal)).pack(anchor='w')
        ttk.Label(summary_frame, text=_t("takeaway.delivery_fee_amount").format(amount=delivery_fee)).pack(anchor='w')
        ttk.Label(summary_frame, text=_t("takeaway.total_amount").format(amount=total_amount), font=('Arial', 10, 'bold')).pack(anchor='w')

        # Delivery type
        type_frame = ttk.LabelFrame(main_frame, text=_t("takeaway.delivery_type"), padding=10)
        type_frame.pack(fill=tk.X, pady=5)

        delivery_type = tk.StringVar(value="delivery")
        ttk.Radiobutton(type_frame, text=_t("takeaway.delivery"), variable=delivery_type, value="delivery").pack(anchor='w')
        ttk.Radiobutton(type_frame, text=_t("takeaway.collection"), variable=delivery_type, value="collection").pack(anchor='w')

        # Address with auto-populate from housing
        address_frame = ttk.LabelFrame(main_frame, text=_t("takeaway.delivery_address"), padding=10)
        address_frame.pack(fill=tk.X, pady=5)

        # Building entry row with auto-fill button
        building_row = ttk.Frame(address_frame)
        building_row.pack(fill=tk.X)
        ttk.Label(building_row, text=_t("takeaway.building_hall")).pack(anchor='w')

        building_entry = ttk.Entry(address_frame, width=40)
        building_entry.pack(fill=tk.X)

        ttk.Label(address_frame, text=_t("takeaway.room_optional")).pack(anchor='w')
        room_entry = ttk.Entry(address_frame, width=40)
        room_entry.pack(fill=tk.X)

        def auto_fill_housing_address():
            """Auto-fill address from housing accommodation"""
            # Get the correct user identifier
            user_identifier = self.get_user_identifier()
            housing_address = self.get_student_housing_address(user_identifier)

            if housing_address:
                building_entry.delete(0, tk.END)
                building_entry.insert(0, housing_address['building'])
                room_entry.delete(0, tk.END)
                room_entry.insert(0, housing_address['room'])
                messagebox.showinfo(_t("takeaway.address_found"), _t("takeaway.address_autofilled").format(address=housing_address['full_address']))
            else:
                messagebox.showinfo(_t("takeaway.no_housing_found"), _t("takeaway.no_housing_msg"))

        ttk.Button(address_frame, text=_t("takeaway.use_housing_address"), command=auto_fill_housing_address).pack(anchor='w', pady=5)

        # Payment with finance account balance display
        payment_frame = ttk.LabelFrame(main_frame, text=_t("takeaway.payment_method"), padding=10)
        payment_frame.pack(fill=tk.X, pady=5)

        payment_method = tk.StringVar(value="card")

        # Get student finance balance using correct identifier
        user_identifier = self.get_user_identifier()
        finance_balance = self.get_user_finance_balance(user_identifier)

        ttk.Radiobutton(payment_frame, text=_t("takeaway.payment_card"), variable=payment_method, value="card").pack(anchor='w')
        student_acc_text = _t("takeaway.student_account_balance").format(balance=finance_balance)
        if finance_balance < total_amount:
            student_acc_text += " - " + _t("takeaway.insufficient_funds")
        ttk.Radiobutton(payment_frame, text=student_acc_text, variable=payment_method, value="student_account").pack(anchor='w')
        ttk.Radiobutton(payment_frame, text=_t("takeaway.cash_on_delivery"), variable=payment_method, value="cash").pack(anchor='w')

        # Notes
        ttk.Label(main_frame, text=_t("takeaway.order_notes")).pack(anchor='w')
        notes_entry = ttk.Entry(main_frame, width=50)
        notes_entry.pack(fill=tk.X, pady=5)

        def process_order():
            building = building_entry.get().strip()
            room = room_entry.get().strip()

            if delivery_type.get() == "delivery" and not building:
                messagebox.showerror(_t("common.error"), _t("takeaway.enter_address"))
                return

            room_label = _t("takeaway.room_label")
            address = building + (f", {room_label} {room}" if room else "")
            selected_payment = payment_method.get()

            # If using student account, process payment first
            if selected_payment == "student_account":
                # Check balance
                current_balance = self.get_user_finance_balance(user_identifier)
                if current_balance < total_amount:
                    messagebox.showerror(
                        _t("takeaway.insufficient_balance_title"),
                        _t("takeaway.insufficient_balance_msg").format(balance=current_balance, total=total_amount)
                    )
                    return

                # Process payment from student finance account
                payment_result = process_student_finance_account_payment(
                    student_id=user_identifier,
                    amount=total_amount,
                    description=_t("takeaway.order_description").format(restaurant=restaurant_name),
                    transaction_source="Takeaway",
                    transaction_ref=f"TO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=self.current_user.get('username', 'System')
                )

                if not payment_result.get('success'):
                    messagebox.showerror(_t("takeaway.payment_failed"), payment_result.get('message', _t("takeaway.payment_process_failed")))
                    return

            # Place the order
            order_id = place_order(
                user_id,
                address,
                delivery_type.get(),
                selected_payment,
                notes_entry.get().strip()
            )

            if order_id:
                # Record revenue to finance system
                record_revenue_to_finance(
                    student_id=user_identifier,
                    amount=total_amount,
                    revenue_category="Takeaway Sales",
                    transaction_source="Takeaway",
                    transaction_ref=order_id,
                    payment_method=selected_payment.replace('_', ' ').title(),
                    notes=_t("takeaway.order_from_restaurant", restaurant=restaurant_name)
                )

                # Send receipt email
                order_details = {
                    'restaurant_name': restaurant_name,
                    'subtotal': subtotal,
                    'delivery_fee': delivery_fee,
                    'total_amount': total_amount,
                    'delivery_type': delivery_type.get(),
                    'delivery_address': address if delivery_type.get() == 'delivery' else _t("takeaway.collection_label"),
                    'payment_method': selected_payment
                }
                self.send_order_receipt_email(order_id, user_identifier, order_details, cart_items)

                on_close()
                self.update_cart_count()

                success_msg = _t("takeaway.order_success").format(order_id=order_id)
                if selected_payment == "student_account":
                    new_balance = payment_result.get('new_balance', 0)
                    success_msg += "\n\n" + _t("takeaway.payment_deducted").format(amount=total_amount, balance=new_balance)
                success_msg += "\n\n" + _t("takeaway.receipt_sent_email")

                messagebox.showinfo(_t("takeaway.order_placed"), success_msg)
            else:
                messagebox.showerror(_t("common.error"), _t("takeaway.order_failed"))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text=_t("takeaway.place_order"), command=process_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=on_close).pack(side=tk.RIGHT, padx=5)

    def show_order_history(self):
        """Show order history"""
        user_id = self.current_user.get('id', 0)
        orders = get_order_history(user_id)

        history_window = tk.Toplevel(self.takeaway_window)
        history_window.title(_t("takeaway.order_history"))
        history_window.geometry("600x400")
        history_window.transient(self.takeaway_window)

        main_frame = ttk.Frame(history_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("takeaway.order_history"), font=('Arial', 14, 'bold')).pack(pady=5)

        if not orders:
            ttk.Label(main_frame, text=_t("takeaway.no_orders")).pack(pady=50)
            ttk.Button(main_frame, text=_t("common.close"), command=history_window.destroy).pack()
            return

        columns = ('order_id', 'restaurant', 'date', 'total', 'status')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

        tree.heading('order_id', text=_t("takeaway.col_order_id"))
        tree.heading('restaurant', text=_t("takeaway.col_restaurant"))
        tree.heading('date', text=_t("takeaway.col_date"))
        tree.heading('total', text=_t("takeaway.col_total"))
        tree.heading('status', text=_t("takeaway.col_status"))

        tree.column('order_id', width=120)
        tree.column('restaurant', width=150)
        tree.column('date', width=140)
        tree.column('total', width=80)
        tree.column('status', width=80)

        for order in orders:
            tree.insert('', tk.END, values=(
                order['order_id'],
                order['restaurant_name'],
                order['order_date'],
                f"${order['total_amount']:.2f}",
                order['order_status'].upper()
            ))

        tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(main_frame, text=_t("common.close"), command=history_window.destroy).pack(pady=10)

    def create_refunds_tab(self):
        """Create payment refunds management tab"""
        refunds_frame = ttk.Frame(self.notebook)
        self.notebook.add(refunds_frame, text="Refunds")

        # Configure grid
        refunds_frame.columnconfigure(0, weight=1)
        refunds_frame.rowconfigure(2, weight=1)

        # Header
        header_label = ttk.Label(refunds_frame, text="Takeaway Order Refunds", font=('Arial', 16, 'bold'))
        header_label.grid(row=0, column=0, pady=10, padx=10, sticky='w')

        # Search frame
        search_frame = ttk.LabelFrame(refunds_frame, text="Search Orders", padding=10)
        search_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

        ttk.Label(search_frame, text="Search by Order ID, Customer or Restaurant:").pack(side=tk.LEFT, padx=5)
        self.refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Search", command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="Show All", command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=2)

        # Orders table
        table_frame = ttk.Frame(refunds_frame)
        table_frame.grid(row=2, column=0, padx=10, pady=5, sticky='nsew')

        columns = ('order_id', 'order_date', 'customer', 'restaurant', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        self.refunds_tree.heading('order_id', text='Order ID')
        self.refunds_tree.heading('order_date', text='Order Date')
        self.refunds_tree.heading('customer', text='Customer')
        self.refunds_tree.heading('restaurant', text='Restaurant')
        self.refunds_tree.heading('amount', text='Amount')
        self.refunds_tree.heading('payment_method', text='Payment Method')
        self.refunds_tree.heading('status', text='Status')

        self.refunds_tree.column('order_id', width=150)
        self.refunds_tree.column('order_date', width=150)
        self.refunds_tree.column('customer', width=120)
        self.refunds_tree.column('restaurant', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        # Buttons
        button_frame = ttk.Frame(refunds_frame)
        button_frame.grid(row=3, column=0, padx=10, pady=10, sticky='ew')

        ttk.Button(button_frame, text="Process Refund", command=self.process_takeaway_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details", command=self.view_order_details_for_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export to CSV", command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with all orders"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            search_term = self.refunds_search_var.get().strip()

            if search_term:
                # Search by order_id, student_id, or restaurant name
                query = '''
                    SELECT o.order_id, o.order_date, o.student_id, o.user_id,
                           o.total_amount, o.payment_method, o.payment_status,
                           r.name as restaurant_name
                    FROM takeaway_orders o
                    LEFT JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
                    WHERE o.order_id LIKE ? OR o.student_id LIKE ? OR r.name LIKE ?
                    ORDER BY o.order_date DESC
                    LIMIT 500
                '''
                search_pattern = f'%{search_term}%'
                cursor.execute(query, (search_pattern, search_pattern, search_pattern))
            else:
                # Get all orders
                query = '''
                    SELECT o.order_id, o.order_date, o.student_id, o.user_id,
                           o.total_amount, o.payment_method, o.payment_status,
                           r.name as restaurant_name
                    FROM takeaway_orders o
                    LEFT JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
                    ORDER BY o.order_date DESC
                    LIMIT 500
                '''
                cursor.execute(query)

            orders = cursor.fetchall()

            for order in orders:
                order_id, order_date, student_id, user_id, amount, payment_method, status, restaurant_name = order

                # Format customer identifier
                customer_display = student_id if student_id else f"User {user_id}"

                # Format payment method
                payment_display = payment_method.replace('_', ' ').title() if payment_method else 'N/A'

                # Format status
                status_display = status.upper() if status else 'PENDING'

                self.refunds_tree.insert('', tk.END, values=(
                    order_id,
                    order_date,
                    customer_display,
                    restaurant_name or 'N/A',
                    f"£{amount:.2f}",
                    payment_display,
                    status_display
                ))

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading orders: {e}")
            try:
                if 'conn' in locals():
                    conn.close()
            except Exception:
                pass

    def process_takeaway_refund(self):
        """Process a refund for selected takeaway order"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to refund.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror("Error", "Invalid order data.")
            return

        order_id = values[0]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid amount format.")
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo("Already Refunded", "This order has already been refunded.")
            return

        # Confirm refund
        if not messagebox.askyesno("Confirm Refund", f"Process refund of £{amount:.2f} for order {order_id}?"):
            return

        # Get order details to find user_id
        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT user_id, payment_method
                FROM takeaway_orders
                WHERE order_id = ?
            ''', (order_id,))

            order_data = cursor.fetchone()
            conn.close()

            if not order_data:
                messagebox.showerror("Error", "Order not found in database.")
                return

            user_id, payment_method = order_data

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error fetching order details: {e}")
            return

        # Show refund method dialog
        refund_method = self.show_takeaway_refund_method_dialog(amount, order_id, user_id)

        if not refund_method:
            return

        # Process based on method
        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Update order status to refunded
            cursor.execute('''
                UPDATE takeaway_orders
                SET payment_status = 'refunded'
                WHERE order_id = ?
            ''', (order_id,))

            # Generate unique refund reference
            refund_ref = f"TAKEAWAY-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Create takeaway_refunds table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS takeaway_refunds (
                    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    refund_date TEXT NOT NULL,
                    refund_amount REAL NOT NULL,
                    refund_method TEXT NOT NULL,
                    refund_reference TEXT UNIQUE,
                    user_id INTEGER,
                    processed_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (order_id) REFERENCES takeaway_orders (order_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            # Migrate from old schema (student_id) to new schema (user_id)
            cursor.execute("PRAGMA table_info(takeaway_refunds)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'student_id' in columns and 'user_id' not in columns:
                # Add user_id column
                cursor.execute('ALTER TABLE takeaway_refunds ADD COLUMN user_id INTEGER')
                print("Migration: Added user_id column to takeaway_refunds table")

            # Insert refund record
            cursor.execute('''
                INSERT INTO takeaway_refunds
                (order_id, refund_date, refund_amount, refund_method, refund_reference, user_id, processed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                  refund_ref, user_id, self.current_user.get('username', 'System')))

            conn.commit()
            conn.close()

            # If student account refund, add to their account
            if refund_method == 'Student Account':
                success = self.add_takeaway_refund_to_student_account(user_id, amount, refund_ref)
                if not success:
                    messagebox.showwarning("Partial Success",
                                         "Refund recorded but failed to credit student account. Please credit manually.")

            # Send refund receipt email
            self.send_takeaway_refund_receipt(order_id, user_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_takeaway_finance_gui(order_id, amount, refund_method, refund_ref, user_id)

            messagebox.showinfo("Refund Processed",
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

            # Refresh the list
            self.refresh_refunds_list()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error processing refund: {e}")
            try:
                if 'conn' in locals():
                    conn.close()
            except Exception:
                pass

    def show_takeaway_refund_method_dialog(self, amount, order_id, user_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.takeaway_window)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(self.takeaway_window)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Order ID: {order_id}").pack(pady=5)

        # Get student_id from users table if available
        student_id = None
        if user_id:
            try:
                conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
                result_row = cursor.fetchone()
                conn.close()
                if result_row and result_row[0]:
                    student_id = result_row[0]
            except Exception as e:
                print(f"Error getting student_id from user: {e}")

        # Show student account balance if student_id available
        if student_id:
            try:
                current_balance = get_student_finance_account_balance(student_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text="Student Finance Account", padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                print(f"Error getting balance: {e}")

        ttk.Label(dialog, text="Select refund method:", font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not student_id:
                messagebox.showerror("Error", "No student ID associated with this user account.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text="Cash Refund", command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text="Card Refund", command=select_card, width=20).pack(pady=5)

        if student_id:
            ttk.Button(button_frame, text="Student Finance Account", command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_takeaway_refund_to_student_account(self, user_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get student_id from users table
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
            user_row = cursor.fetchone()

            if not user_row or not user_row[0]:
                print(f"No student_id found for user_id {user_id}")
                conn.close()
                return False

            student_id = user_row[0]

            # Check if student finance account exists
            cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            account = cursor.fetchone()

            if not account:
                # Create account with refund amount
                cursor.execute('''
                    INSERT INTO student_finance_accounts (student_id, balance)
                    VALUES (?, ?)
                ''', (student_id, amount))
                account_id = cursor.lastrowid
                balance_before = 0.00
                balance_after = amount
            else:
                # Update existing account
                account_id, balance_before = account
                balance_after = balance_before + amount
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ?
                ''', (balance_after, account_id))

            # Record transaction
            cursor.execute('''
                INSERT INTO student_finance_transactions
                (account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, reference_id, processed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, student_id, 'credit', amount, balance_before, balance_after,
                  'Takeaway Order Refund', refund_ref, self.current_user.get('username', 'System')))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            print(f"Error adding refund to student account: {e}")
            try:
                if 'conn' in locals():
                    conn.close()
            except Exception:
                pass
            return False

    def send_takeaway_refund_receipt(self, order_id, user_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        try:
            # Get user info from users table
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email, student_id
                FROM users WHERE id = ?
            ''', (user_id,))
            user_row = cursor.fetchone()
            conn.close()

            if not user_row or not user_row[2]:
                print(f"No email found for user_id {user_id}")
                return

            first_name, last_name, customer_email, student_id = user_row
            customer_name = f"{first_name} {last_name}"

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account' and student_id:
                try:
                    new_balance = get_student_finance_account_balance(student_id)
                    if new_balance is not None:
                        balance_text = f"\n\nYour updated account balance is: £{new_balance:.2f}"
                except Exception:
                    pass

            # Prepare template variables
            from university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'customer_name': customer_name,
                'order_id': order_id,
                'amount': f"{amount:.2f}",
                'method': method,
                'refund_ref': refund_ref,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            }

            subject, body = render_template('commerce/takeaway_order_refund', template_vars)
            if not subject or not body:
                print("Failed to render email template")
                return

            result = send_email(customer_email, subject, body)
            if result:
                print(f"Refund receipt sent to {customer_email}")
            else:
                print(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            print(f"Error sending refund receipt: {e}")

    def notify_takeaway_finance_gui(self, order_id, amount, method, refund_ref, user_id):
        """Notify finance GUI about the refund"""
        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get user information from users table
            cursor.execute('''
                SELECT first_name, last_name, student_id
                FROM users WHERE id = ?
            ''', (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                first_name, last_name, student_id = user_row
                user_info = f"User: {first_name} {last_name} (ID: {user_id})"
                if student_id:
                    user_info += f", Student ID: {student_id}"
            else:
                user_info = f"User ID: {user_id}"

            # Create finance_refunds table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    refund_reference TEXT UNIQUE,
                    department TEXT,
                    amount REAL,
                    refund_method TEXT,
                    refund_date TEXT,
                    refund_time TEXT,
                    transaction_reference TEXT,
                    processed_by TEXT,
                    notes TEXT
                )
            ''')

            # Migrate finance_refunds table to ensure all columns exist
            cursor.execute("PRAGMA table_info(finance_refunds)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add missing columns if needed
            if 'transaction_reference' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN transaction_reference TEXT')
                print("Migration: Added transaction_reference column to finance_refunds table")

            if 'refund_time' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN refund_time TEXT')
                print("Migration: Added refund_time column to finance_refunds table")

            if 'notes' not in columns:
                cursor.execute('ALTER TABLE finance_refunds ADD COLUMN notes TEXT')
                print("Migration: Added notes column to finance_refunds table")

            # Insert into finance_refunds table
            cursor.execute('''
                INSERT INTO finance_refunds
                (refund_reference, department, amount, refund_method, refund_date,
                 refund_time, transaction_reference, processed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (refund_ref, 'Takeaway', amount, method,
                  datetime.now().strftime('%Y-%m-%d'),
                  datetime.now().strftime('%H:%M:%S'),
                  f'order_{order_id}',
                  self.current_user.get('username', 'System'),
                  f'Takeaway Order #{order_id} Refund - {user_info}'))

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            print(f"Error notifying finance GUI: {e}")
            try:
                if 'conn' in locals():
                    conn.close()
            except Exception:
                pass

    def view_order_details_for_refund(self):
        """View detailed information for selected order"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to view details.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror("Error", "Invalid order data.")
            return

        order_id = values[0]

        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get order details
            cursor.execute('''
                SELECT o.*, r.name as restaurant_name
                FROM takeaway_orders o
                LEFT JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
                WHERE o.order_id = ?
            ''', (order_id,))

            order = cursor.fetchone()

            if not order:
                messagebox.showerror("Error", "Order not found.")
                conn.close()
                return

            # Get order items
            cursor.execute('''
                SELECT item_name, quantity, unit_price, subtotal
                FROM takeaway_order_items
                WHERE order_id = ?
            ''', (order_id,))

            items = cursor.fetchall()
            conn.close()

            # Create details window
            details_window = tk.Toplevel(self.takeaway_window)
            details_window.title(f"Order Details - {order_id}")
            details_window.geometry("500x600")
            details_window.transient(self.takeaway_window)

            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Order information
            info_text = scrolledtext.ScrolledText(main_frame, width=60, height=30, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)

            # Format order details
            details = f"""ORDER DETAILS
═══════════════════════════════════════════════════════

Order ID:           {order[0]}
Order Date:         {order[4]}
Restaurant:         {order[-1]}

Customer ID:        {order[1] if order[1] else 'N/A'}
Student ID:         {order[2] if order[2] else 'N/A'}

Delivery Type:      {order[6].title() if order[6] else 'N/A'}
Delivery Address:   {order[5] if order[5] else 'N/A'}

Payment Method:     {order[10].replace('_', ' ').title() if order[10] else 'N/A'}
Payment Status:     {order[11].upper() if order[11] else 'N/A'}
Order Status:       {order[12].upper() if order[12] else 'N/A'}

═══════════════════════════════════════════════════════
ORDER ITEMS
═══════════════════════════════════════════════════════
"""

            for item in items:
                item_name, quantity, unit_price, subtotal = item
                details += f"\n{item_name}\n"
                details += f"  Quantity: {quantity} x £{unit_price:.2f} = £{subtotal:.2f}\n"

            details += f"""
═══════════════════════════════════════════════════════
TOTALS
═══════════════════════════════════════════════════════

Subtotal:           £{order[7]:.2f}
Delivery Fee:       £{order[8]:.2f}
───────────────────────────────────────────────────────
TOTAL:              £{order[9]:.2f}

═══════════════════════════════════════════════════════

Notes:              {order[15] if order[15] else 'None'}

Estimated Delivery: {order[13] if order[13] else 'N/A'}
Actual Delivery:    {order[14] if order[14] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text="Close", command=details_window.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading order details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"takeaway_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Order ID', 'Order Date', 'Customer', 'Restaurant',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for item in self.refunds_tree.get_children():
                    values = self.refunds_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Export Successful", f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting data: {e}")
